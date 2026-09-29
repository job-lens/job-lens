import hashlib
from io import BytesIO
from unittest.mock import patch

import pytest
from app.core.errors import AppError
from app.infrastructure.scanning import ClamAVScanner
from app.infrastructure.storage import LocalBlobStore


def test_private_storage_roundtrip_and_cleanup(tmp_path):
    store = LocalBlobStore(tmp_path)
    blob = store.put(BytesIO(b"example"), 100)
    assert blob.sha256 == hashlib.sha256(b"example").hexdigest()
    assert blob.size == 7 and blob.key.startswith("quarantine/")
    with store.open(blob.key) as file:
        assert file.read() == b"example"
    assert (tmp_path / blob.key).stat().st_mode & 0o777 == 0o600
    store.delete(blob.key)
    store.delete(blob.key)
    for content, limit in [(b"", 100), (b"too big", 2)]:
        with pytest.raises(ValueError):
            store.put(BytesIO(content), limit)
    assert list((tmp_path / "quarantine").iterdir()) == []


@pytest.mark.parametrize(
    "key",
    [
        "../secret",
        "/etc/passwd",
        "ready/../../secret",
        "ready/anything.png",
        "quarantine/" + "a" * 32 + "/suffix",
    ],
)
def test_path_traversal_is_rejected(tmp_path, key):
    with pytest.raises(ValueError):
        with LocalBlobStore(tmp_path).open(key):
            pass


def test_symlink_is_rejected(tmp_path):
    store = LocalBlobStore(tmp_path / "private")
    secret = tmp_path / "secret"
    secret.write_text("secret")
    (store.root / "ready" / ("a" * 32)).symlink_to(secret)
    with pytest.raises(ValueError):
        with store.open("ready/" + "a" * 32):
            pass


@pytest.mark.parametrize(
    "reply,expected",
    [
        (b"stream: OK\0", "clean"),
        (b"stream: Eicar-Test-Signature FOUND\0", "rejected"),
        (b"ERROR\0", None),
        (b"", None),
    ],
)
def test_scanner_protocol_fails_closed(reply, expected):
    with patch("socket.create_connection") as connect:
        sock = connect.return_value.__enter__.return_value
        sock.recv.return_value = reply
        if expected:
            assert ClamAVScanner("clamav").scan(BytesIO(b"test")) == expected
        else:
            with pytest.raises(AppError):
                ClamAVScanner("clamav").scan(BytesIO(b"test"))


def test_scanner_unavailable():
    with patch("socket.create_connection", side_effect=OSError("offline")):
        with pytest.raises(AppError) as exc:
            ClamAVScanner("clamav").scan(BytesIO(b"test"))
        assert exc.value.status == 503
