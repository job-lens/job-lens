import warnings
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.core.errors import AppError
from app.core.types import JsonObject
from app.infrastructure.db import Database
from app.infrastructure.models import FileAsset
from app.infrastructure.notifications import append_notifications
from app.infrastructure.scanning import Scanner
from app.infrastructure.storage import BlobStore

MIME_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
Image.MAX_IMAGE_PIXELS = 20_000_000


def inspect_file(store: BlobStore, key: str) -> tuple[str, int | None, int | None]:
    with store.open(key) as stream:
        if stream.read(16).startswith(b"%PDF-"):
            return "application/pdf", None, None
    try:
        with store.open(key) as stream, warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                mime = MIME_FORMATS.get(image.format or "")
                width, height = image.size
                if (
                    mime is None
                    or not (1 <= width <= 20000 and 1 <= height <= 20000)
                    or width * height > 20_000_000
                ):
                    raise AppError(415, "UNSUPPORTED_FILE", "请选择 PNG、JPEG、WebP 图片或 PDF")
                image.verify()
                return mime, width, height
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise AppError(415, "UNSUPPORTED_FILE", "文件格式无法校验") from None


class FileJobs:
    def __init__(self, database: Database, store: BlobStore, scanner: Scanner) -> None:
        self.database, self.store, self.scanner = database, store, scanner

    def scan(self, payload: JsonObject) -> None:
        identifier = UUID(str(payload["asset_id"]))
        with self.database.transaction() as s:
            row = s.get(FileAsset, identifier)
            if row is None or row.state not in {"quarantined", "scanning"}:
                return
            key, version = row.storage_key, row.version
        # External detection does not hold a DB transaction. Failure stays private
        # and the durable worker retries it; no timeout is treated as clean.
        with self.store.open(key) as source:
            result = self.scanner.scan(source)
        metadata = None
        if result == "clean":
            try:
                metadata = inspect_file(self.store, key)
            except AppError:
                result = "rejected"
        with self.database.transaction() as s:
            row = s.scalar(select(FileAsset).where(FileAsset.id == identifier).with_for_update())
            if (
                row is None
                or row.version != version
                or row.state not in {"quarantined", "scanning"}
            ):
                return
            row.state = "ready" if result == "clean" else "rejected"
            row.reason = None if result == "clean" else "文件未通过检测，请重新选择"
            if metadata:
                row.mime_type, row.width, row.height = metadata
            row.version += 1
            append_notifications(s, {row.uploader_id}, "files." + row.state, "file", row.id)

    def delete(self, payload: JsonObject) -> None:
        identifier = UUID(str(payload["asset_id"]))
        with self.database.transaction() as s:
            row = s.get(FileAsset, identifier)
            if row is None or row.state != "deleted":
                return
            key = row.storage_key
        self.store.delete(key)
