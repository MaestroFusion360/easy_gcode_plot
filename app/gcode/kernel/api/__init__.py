"""Public facade for the native FANUC CNC kernel."""

from __future__ import annotations

__all__ = ["SUPPORTED_LANGUAGES", "execute"]  # pylint: disable=undefined-all-variable


def __getattr__(name: str):
    if name == "execute":
        from .engine import execute  # pylint: disable=import-outside-toplevel

        return execute
    if name == "SUPPORTED_LANGUAGES":
        from .engine import SUPPORTED_LANGUAGES  # pylint: disable=import-outside-toplevel

        return SUPPORTED_LANGUAGES
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
