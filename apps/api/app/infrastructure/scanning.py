import socket
import struct
from typing import BinaryIO, Literal, Protocol

from app.core.errors import AppError

type ScanResult = Literal["clean", "rejected"]


class Scanner(Protocol):
    def scan(self, source: BinaryIO) -> ScanResult: ...


class ClamAVScanner:
    def __init__(self, host: str, port: int = 3310, timeout: float = 15) -> None:
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, source: BinaryIO) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(b"zINSTREAM\0")
                while data := source.read(64 * 1024):
                    sock.sendall(struct.pack("!I", len(data)) + data)
                sock.sendall(struct.pack("!I", 0))
                result = bytearray()
                while b"\0" not in result and len(result) <= 4096:
                    data = sock.recv(1024)
                    if not data:
                        break
                    result.extend(data)
        except OSError as exc:
            raise AppError(503, "SCAN_UNAVAILABLE", "文件检测暂不可用") from exc
        response = bytes(result).rstrip(b"\0\n")
        if response == b"stream: OK":
            return "clean"
        if response.startswith(b"stream: ") and response.endswith(b" FOUND"):
            return "rejected"
        raise AppError(503, "SCAN_UNAVAILABLE", "文件检测暂不可用")
