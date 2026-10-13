"""Shared comment names for Python and native tool discovery."""

import re
from functools import lru_cache

DEFAULT_TYPE_HINTS = (
    (r"\bTAP(?:PING)?\b", "tap"),
    (r"\bTHREAD(?:ING)?\b", "thread"),
    (r"\bGROOV(?:E|ING)\b", "groove"),
    (r"\bDRILL(?:ING)?\b", "drill"),
    (r"\bTAPER(?:ED)?\s+BALL(?:\s*NOSE)?\b|\bTAPER(?:ED)?\s+SPHERICAL\b", "taper_ball_mill"),
    (r"\bBULL(?:\s*NOSE)?\b|\bCORNER\s+RADIUS\b|\bRADIUS\s+END\s*MILL\b|\bTOROIDAL\b|\bMILL\s+BULL\b", "mill_bull"),
    (r"\bBALL(?:\s*NOSE)?\b|\bSPHER(?:ICAL)?\b", "mill_ball"),
    (r"\b(?:FACE|SHELL)\s*MILL(?:ING)?\b|\bMILL\s+FACE\b", "face_mill"),
    (
        r"\b(?:SLOT|DISC|DISK)\s*(?:MILL|CUTTER)\b|\bT\s+SLOT\b|\bWOODRUFF\b|"
        r"\bKEYSEAT\s+CUTTER\b|\bSLITTING\s+SAW\b",
        "slot_mill",
    ),
    (r"\bCHAMFER\b|\bCOUNTER\s*SINK\b|\bCSINK\b|\bV\s+(?:BIT|MILL)\b", "chamfer_mill"),
    (r"\b(?:FLAT|SQUARE)(?:\s+END)?\s*MILL\b|\bEND\s*MILL\b|\bMILL\s+FLAT\b", "mill_flat"),
)


def hint_text(description):
    return re.sub(r"[_\-–—]+", " ", description.upper())


@lru_cache(maxsize=64)
def compiled_hints(hints):
    return tuple((re.compile(pattern), kind) for pattern, kind in hints if pattern)


def type_hint(description, hints=DEFAULT_TYPE_HINTS):
    text = hint_text(description)
    return next((kind for pattern, kind in compiled_hints(hints) if pattern.search(text)), None)


def is_tool_comment(description, hints=DEFAULT_TYPE_HINTS):
    return bool(type_hint(description, hints) or re.search(r"\b(?:TOOL|OD|ID)\b", hint_text(description)))
