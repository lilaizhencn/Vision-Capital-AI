from __future__ import annotations


def validate_file_signature(filename: str, data: bytes) -> None:
    """Reject common extension spoofing before a document reaches a parser."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    signatures = {
        "pdf": (b"%PDF-",),
        "png": (b"\x89PNG\r\n\x1a\n",),
        "jpg": (b"\xff\xd8\xff",),
        "jpeg": (b"\xff\xd8\xff",),
        "webp": (b"RIFF",),
        "docx": (b"PK\x03\x04",),
        "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        "xlsx": (b"PK\x03\x04",),
        "xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    }
    expected = signatures.get(suffix)
    if expected and not any(data.startswith(prefix) for prefix in expected):
        raise ValueError(f"File signature does not match .{suffix} extension")
