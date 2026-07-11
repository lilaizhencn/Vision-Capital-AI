from __future__ import annotations

import socket
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings


class VirusScannerUnavailable(ConnectionError):
    """Transient scanner outage that Celery may safely retry."""


class VirusScanner:
    """Small ClamAV INSTREAM client with a safe disabled-local fallback."""

    def scan_bytes(self, data: bytes) -> str:
        return self.scan_chunks((data,))

    def scan_file(self, path: Path) -> str:
        with path.open("rb") as source:
            return self.scan_chunks(iter(lambda: source.read(1024 * 1024), b""))

    def scan_chunks(self, chunks: Iterable[bytes]) -> str:
        if not settings.virus_scan_enabled:
            return "skipped"
        try:
            with socket.create_connection(
                (settings.virus_scan_host, settings.virus_scan_port),
                timeout=settings.virus_scan_timeout_seconds,
            ) as connection:
                connection.sendall(b"zINSTREAM\0")
                for chunk in chunks:
                    if not chunk:
                        continue
                    connection.sendall(len(chunk).to_bytes(4, "big"))
                    connection.sendall(chunk)
                connection.sendall((0).to_bytes(4, "big"))
                response = connection.recv(4096).decode("utf-8", errors="replace").replace("\x00", "").strip()
        except OSError as exc:
            raise VirusScannerUnavailable("Virus scanner is unavailable") from exc
        if not response.endswith("OK"):
            raise ValueError(f"Virus scan rejected the file: {response or 'unknown result'}")
        return response
