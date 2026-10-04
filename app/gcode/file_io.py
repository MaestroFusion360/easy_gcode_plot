"""Shared output preflight and atomic file commits."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def same_file(first, second) -> bool:
    left, right = Path(first).resolve(), Path(second).resolve()
    return left == right or (left.exists() and right.exists() and left.samefile(right))


def protect_source(output, source) -> None:
    if source and same_file(output, source):
        raise ValueError("Output must differ from the source file")


def validate_output_paths(source, *outputs) -> None:
    paths = [path for path in outputs if path is not None]
    for index, path in enumerate(paths):
        protect_source(path, source)
        if any(same_file(path, other) for other in paths[:index]):
            raise ValueError("Output paths must differ from each other")


def atomic_export(path, write, *, cancelled=None) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        if cancelled is not None and cancelled():
            raise InterruptedError("Export cancelled")
        write(temporary)
        size = temporary.stat().st_size
        if cancelled is not None and cancelled():
            raise InterruptedError("Export cancelled")
        temporary.replace(target)
        return size
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path, text, *, encoding="utf-8") -> int:
    return atomic_export(path, lambda temporary: temporary.write_text(text, encoding=encoding))
