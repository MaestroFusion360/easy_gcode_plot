"""Shared comment names for Python and native tool discovery."""

import re

_TYPE_HINTS = (
    (r"\bTAP(?:PING)?\b|\bМЕТЧИК\b", "tap"),
    (r"\bTHREAD(?:ING)?\b", "thread"),
    (r"\bGROOV(?:E|ING)\b", "groove"),
    (r"\bDRILL(?:ING)?\b|\bСВЕРЛО\b", "drill"),
    (r"\bTAPER(?:ED)?\s+BALL(?:\s*NOSE)?\b|\bTAPER(?:ED)?\s+SPHERICAL\b", "taper_ball_mill"),
    (r"\bBULL(?:\s*NOSE)?\b|\bCORNER\s+RADIUS\b|\bRADIUS\s+END\s*MILL\b|\bTOROIDAL\b|\bMILL\s+BULL\b", "mill_bull"),
    (r"\bBALL(?:\s*NOSE)?\b|\bSPHER(?:ICAL)?\b|\bШАРОВАЯ\b|\bСФЕРИЧЕСКАЯ\b", "mill_ball"),
    (r"\b(?:FACE|SHELL)\s*MILL(?:ING)?\b|\bMILL\s+FACE\b|\bТОРЦЕВАЯ\b", "face_mill"),
    (
        r"\b(?:SLOT|DISC|DISK)\s*(?:MILL|CUTTER)\b|\bT\s+SLOT\b|\bWOODRUFF\b|"
        r"\bKEYSEAT\s+CUTTER\b|\bSLITTING\s+SAW\b|\bДИСКОВАЯ\b",
        "slot_mill",
    ),
    (r"\bCHAMFER\b|\bCOUNTER\s*SINK\b|\bCSINK\b|\bV\s+(?:BIT|MILL)\b|\bФАСОЧНАЯ\b", "chamfer_mill"),
    (r"\b(?:FLAT|SQUARE)(?:\s+END)?\s*MILL\b|\bEND\s*MILL\b|\bMILL\s+FLAT\b|\bКОНЦЕВАЯ\b", "mill_flat"),
)


def hint_text(description):
    return re.sub(r"[_\-–—]+", " ", description.upper())


def type_hint(description):
    text = hint_text(description)
    return next((kind for pattern, kind in _TYPE_HINTS if re.search(pattern, text)), None)


def is_tool_comment(description):
    return bool(type_hint(description) or re.search(r"\b(?:TOOL|OD|ID)\b", hint_text(description)))
