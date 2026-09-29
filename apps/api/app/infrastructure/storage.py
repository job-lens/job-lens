import hashlib
import os
import re
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Protocol
from uuid import uuid4

import boto3

from app.core.config import Settings

_KEY = re.compile(r"(quarantine|ready)/[a-f0-9]{32}")


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    sha256: str


class BlobStore(Protocol):
    def put(self, source: BinaryIO, max_bytes: int) -> StoredObject: ...
    def open(self, key: str) -> AbstractContextManager[BinaryIO]: ...
    def delete(self, key: str) -> None: ...


def validate_key(key: str) -> None:
    if not _KEY.fullmatch(key):
        raise ValueError("invalid storage key")


class ByteWriter(Protocol):
    def write(self, data: bytes, /) -> int: ...


def copy_checked(source: BinaryIO, target: ByteWriter, max_bytes: int) -> tuple[int, str]:
    if not 1 <= max_bytes <= 20 * 1024 * 1024:
        raise ValueError("invalid upload limit")
    size = 0
    digest = hashlib.sha256()
    while chunk := source.read(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("file exceeds upload limit")
        digest.update(chunk)
        target.write(chunk)
    if size == 0:
        raise ValueError("empty file")
    return size, digest.hexdigest()


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for area in ("quarantine", "ready"):
            (self.root / area).mkdir(mode=0o700, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = self.root / key
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ValueError("storage path escapes private root")
        return path

    def put(self, source: BinaryIO, max_bytes: int) -> StoredObject:
        key = f"quarantine/{uuid4().hex}"
        path = self._path(key)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as target:
                size, digest = copy_checked(source, target, max_bytes)
                target.flush()
                os.fsync(target.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StoredObject(key, size, digest)

    @contextmanager
    def open(self, key: str) -> Iterator[BinaryIO]:
        fd = os.open(self._path(key), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            yield source

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3BlobStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise ValueError("private bucket required")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint, region_name=settings.s3_region
        )

    def put(self, source: BinaryIO, max_bytes: int) -> StoredObject:
        key = f"quarantine/{uuid4().hex}"
        with SpooledTemporaryFile(max_size=1024 * 1024) as file:
            size, digest = copy_checked(source, file, max_bytes)
            file.seek(0)
            self.client.upload_fileobj(
                file,
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": "application/octet-stream",
                    "ServerSideEncryption": "AES256",
                },
            )
        return StoredObject(key, size, digest)

    @contextmanager
    def open(self, key: str) -> Iterator[BinaryIO]:
        validate_key(key)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            yield response["Body"]
        finally:
            response["Body"].close()

    def delete(self, key: str) -> None:
        validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)
