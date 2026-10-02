"""Source-container detection and lightweight SINUMERIK mode inspection."""

from __future__ import annotations

import re
from pathlib import Path

from .comments import strip_comments

SOURCE_DIALECT_FANUC = "fanuc"
SOURCE_DIALECT_SINUMERIK = "sinumerik"
SINUMERIK_MODE_SIEMENS = "siemens"
SINUMERIK_MODE_ISO = "iso"

_SINUMERIK_SUFFIXES = frozenset({".mpf", ".spf"})
_MODE_RE = re.compile(r"(?<![A-Z0-9_])G\s*(290|291)(?![0-9.])", re.IGNORECASE)


def source_dialect_for_path(path: str | Path | None, source: str | None = None) -> str:
    """Select the source container; MPF/SPF always starts in native mode.

    Contents never override the container. G290/G291 are runtime switches.
    """
    if path and Path(str(path)).suffix.lower() in _SINUMERIK_SUFFIXES:
        return SOURCE_DIALECT_SINUMERIK
    return SOURCE_DIALECT_FANUC


def sinumerik_initial_mode(source: str) -> str:
    """Return the first explicit SINUMERIK language mode, defaulting to G290.

    MPF/SPF files are native SINUMERIK containers.  If the first explicit
    language switch is G291, the document starts its executable section in ISO
    dialect; otherwise native Siemens syntax remains the document default.
    """
    for raw in str(source).splitlines():
        code = strip_comments(raw)
        match = _MODE_RE.search(code)
        if match is None:
            continue
        return SINUMERIK_MODE_ISO if int(match.group(1)) == 291 else SINUMERIK_MODE_SIEMENS
    return SINUMERIK_MODE_SIEMENS
