"""Deterministic text loading for NC source files."""

from __future__ import annotations

from pathlib import Path


class NCTextDecodeError(UnicodeError):
    """Raised when an NC source file is not valid UTF-8/UTF-8-SIG text."""


def read_nc_text(path: str | Path) -> str:
    """Read NC text without silently discarding undecodable source bytes."""
    source = Path(path)
    data = source.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NCTextDecodeError(
            f"NC file is not valid UTF-8/UTF-8-SIG: {source} (invalid byte at offset {exc.start})."
        ) from exc


def read_nc_lines(path: str | Path) -> list[str]:
    """Read an NC file and return logical source lines."""
    return read_nc_text(path).splitlines()
