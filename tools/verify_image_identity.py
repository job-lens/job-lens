#!/usr/bin/env python3
"""Verify saved config and every rootfs layer; engine .Id may be an OCI index."""

import gzip
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def sha(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def archive_identity(path, tag=None):
    with tarfile.open(path, "r:*") as archive:
        entries = json.load(archive.extractfile("manifest.json"))
        selected = [item for item in entries if tag is None or tag in (item.get("RepoTags") or [])]
        if len(selected) != 1:
            raise ValueError("Archive must contain exactly one selected image")
        item = selected[0]
        raw = archive.extractfile(item["Config"]).read()
        cfg = json.loads(raw)
        if (cfg.get("os"), cfg.get("architecture")) != ("linux", "amd64"):
            raise ValueError("Image platform must be linux/amd64")
        diff_ids = cfg["rootfs"]["diff_ids"]
        if len(diff_ids) != len(item["Layers"]):
            raise ValueError("Layer count mismatch")
        for name, expected in zip(item["Layers"], diff_ids, strict=True):
            with archive.extractfile(name) as stream:
                magic = stream.read(2)
                stream.seek(0)
                actual = sha(gzip.GzipFile(fileobj=stream) if magic == b"\x1f\x8b" else stream)
            if actual != expected:
                raise ValueError("Layer content digest mismatch")
        return {
            "config_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "diff_ids": diff_ids,
            "os": cfg["os"],
            "architecture": cfg["architecture"],
            "revision": (cfg.get("config", {}).get("Labels") or {}).get(
                "org.opencontainers.image.revision"
            ),
        }


def inspect(ref, platform=False):
    command = ["docker", "image", "inspect", ref]
    if platform:
        command += ["--platform", "linux/amd64"]
    result = subprocess.run(command, check=True, capture_output=True)
    (info,) = json.loads(result.stdout)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", info["Id"]):
        raise ValueError("Invalid engine identity")
    return info


def verify(meta, producer_id):
    if meta["producer_id"] != producer_id:
        raise ValueError("Producer ID is not the recorded release identity")
    info = inspect(meta["tag"])
    if info["RootFS"]["Layers"] != meta["canonical"]["diff_ids"]:
        raise ValueError("Loaded rootfs identity mismatch")
    actual_id = info["Id"]
    # Export by immutable engine identity, never execute an unverified tag.
    with tempfile.NamedTemporaryFile(suffix=".tar") as saved:
        subprocess.run(["docker", "image", "save", actual_id], stdout=saved, check=True)
        saved.flush()
        canonical = archive_identity(saved.name)
    if canonical != meta["canonical"]:
        raise ValueError("Loaded config or layer identity mismatch")
    return actual_id


def main():
    mode, metadata_path, *args = sys.argv[1:]
    path = Path(metadata_path)
    if mode == "record":
        directory, revision = args
        records = []
        for kind in ("api", "web", "postgres"):
            tag = f"joblens-{kind}:{revision}"
            archive = Path(directory) / f"{kind}.tar.gz"
            canonical = archive_identity(archive, tag)
            info = inspect(tag)
            if info["RootFS"]["Layers"] != canonical["diff_ids"]:
                raise ValueError("Producer rootfs does not match exported artifact")
            if kind != "postgres" and canonical["revision"] != revision:
                raise ValueError("Application source revision mismatch")
            records.append({"tag": tag, "producer_id": info["Id"], "canonical": canonical})
        path.write_text(json.dumps(records, indent=2) + "\n")
    elif mode == "verify":
        tag, producer_id = args
        matches = [item for item in json.loads(path.read_text()) if item["tag"] == tag]
        if len(matches) != 1:
            raise ValueError("Image absent or duplicated in release metadata")
        actual = verify(matches[0], producer_id)
        print(actual)
    else:
        raise ValueError("Unknown mode")


if __name__ == "__main__":
    main()
