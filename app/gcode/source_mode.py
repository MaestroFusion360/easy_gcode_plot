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
_MODE_RE = re.compile(r"(?<![A-Z_])G\s*(290|291)(?![0-9.])", re.IGNORECASE)
_NATIVE_RE = re.compile(
    r"(?<![A-Z_])(?:SUPA|CIP|TRANS|ATRANS|ROT|AROT|RPL|SCALE|ASCALE|MIRROR|AMIRROR|MCALL|"
    r"TRAORI|TRAFOOF|WORKPIECE|CYCLE\d+|POCKET[1-4]|HOLES[12]|LONGHOLE|SLOT[12])\b",
    re.I,
)


def source_dialect_for_path(path: str | Path | None, source: str | None = None) -> str:
    """Select the source container; MPF/SPF always starts in native mode.

    Named files retain their container contract. Unnamed text uses native signatures.
    """
    if path and Path(str(path)).suffix.lower() in _SINUMERIK_SUFFIXES:
        return SOURCE_DIALECT_SINUMERIK
    if not path and source and has_sinumerik_signature(source):
        return SOURCE_DIALECT_SINUMERIK
    return SOURCE_DIALECT_FANUC


def has_sinumerik_signature(source: str) -> bool:
    """Recognize executable native keywords, excluding strings and comments."""
    for raw in str(source).splitlines():
        code = strip_comments(re.sub(r'"(?:[^"\n]|"")*"', "", raw))
        if _NATIVE_RE.search(code) or _MODE_RE.search(code):
            return True
    return False


def language_for_path(path: str | Path, language: str | None = None) -> str:
    """Respect an explicit machine type, otherwise use the source container."""
    if language is not None:
        return language
    return "fanuc_mill" if source_dialect_for_path(path) == SOURCE_DIALECT_SINUMERIK else "fanuc_turn"


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
