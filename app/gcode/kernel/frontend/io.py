"""Deterministic text loading for NC source files."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_NC_ENCODINGS = ("utf-8", "cp1251")


class NCTextDecodeError(UnicodeError):
    """Raised when an NC source file cannot be decoded with the selected encoding."""


def read_nc_text(path: str | Path, *, encoding: str = "utf-8") -> str:
    """Read NC text using the same explicit encoding contract for GUI and CLI."""
    if encoding not in SUPPORTED_NC_ENCODINGS:
        raise ValueError(f"Unsupported NC text encoding: {encoding}")

    source = Path(path)
    data = source.read_bytes()
    codec = "utf-8-sig" if encoding == "utf-8" else encoding
    try:
        return data.decode(codec)
    except UnicodeDecodeError as exc:
        raise NCTextDecodeError(
            f"NC file cannot be decoded as {encoding}: {source} (invalid byte at offset {exc.start})."
        ) from exc


def read_nc_lines(path: str | Path, *, encoding: str = "utf-8") -> list[str]:
    """Read an NC file and return logical source lines."""
    return read_nc_text(path, encoding=encoding).splitlines()
