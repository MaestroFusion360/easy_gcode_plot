"""Conservative tool discovery from literal NC words and human comments.

Only executable T words create candidates. Comments supply geometry, never
execute expressions. Dimensions follow the units active at the T word.
"""

import math
import re
from copy import deepcopy

from app.gcode.kernel.lang import lex_words, strip_comments
from app.tools.definitions import (
    DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION,
    DEFAULT_MILLING_TOOL,
    DEFAULT_TURNING_TOOL,
)
from app.tools.validation import normalized_milling_tools, normalized_tools

_COMMENTS = re.compile(r"\(([^()]*)\)|;([^\r\n]*)")
_COMMENT_TOOL = re.compile(r"\bT\s*(\d+)\b", re.IGNORECASE)
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_TYPE_HINTS = (
    (r"\bTAP(?:PING)?\b", "tap"),
    (r"\bTHREAD(?:ING)?\b", "thread"),
    (r"\bGROOV(?:E|ING)\b", "groove"),
    (r"\bDRILL(?:ING)?\b", "drill"),
    (r"\bBALL\b", "mill_ball"),
    (r"\bFACE MILL\b", "face_mill"),
    (r"\bSLOT MILL\b", "slot_mill"),
    (r"\bCHAMFER\b", "chamfer_mill"),
    (r"\bBULL\b", "mill_bull"),
    (r"\bFLAT(?: END)? MILL\b", "mill_flat"),
)
_DRILL_CYCLES = frozenset({"81", "82", "83"})
_TAP_CYCLES = frozenset({"84"})
_TURNING_THREAD_CYCLES = frozenset({"32", "33", "76", "92"})


def _tool_key(value, turning):
    if not re.fullmatch(r"[+-]?\d+(?:\.0*)?", value):
        return None
    number = float(value)
    if turning:
        number = abs(number)
    if not 1 <= number <= (9999 if turning else 99):
        return None
    return f"T{int(number):04d}" if turning else f"T{int(number)}"


def _comments(line):
    return [" ".join((match[1] or match[2]).split()) for match in _COMMENTS.finditer(line)]


def _hint_text(description):
    return description.upper().replace("_", " ")


def _type_hint(description):
    text = _hint_text(description)
    return next((kind for pattern, kind in _TYPE_HINTS if re.search(pattern, text)), None)


def _is_tool_comment(description):
    return bool(_type_hint(description) or re.search(r"\b(?:TOOL|OD|ID)\b", _hint_text(description)))


def _dimension(description, names, default, scale, *, allow_zero=False):
    match = re.search(rf"(?<![A-Z0-9_])(?:{names})\s*=?\s*({_NUMBER})(?![\w.])", description.upper())
    if match is None:
        return default
    value = float(match[1]) * scale
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return default
    return value


def _turning_spec(description, scale, operation_kind=None):
    spec = deepcopy(DEFAULT_TURNING_TOOL)
    kind = _type_hint(description) or operation_kind
    if kind in {"groove", "thread", "drill", "tap"}:
        spec["type"] = kind
    application = "id" if re.search(r"\bID\b", _hint_text(description)) else "od"
    if kind == "groove" and re.search(r"\bFACE\b", _hint_text(description)):
        application = "face"
    spec["applications"] = [application]
    spec["tipOrientation"] = DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION.get(spec["type"], {}).get(application, 3)
    spec["noseRadius"] = _dimension(description, "R|NR", 0.4, scale)
    if kind == "groove":
        spec["width"] = _dimension(description, "H|W|WIDTH", 3.0, scale)
        spec["noseRadius"] = _dimension(description, "R|NR", 0.0, scale, allow_zero=True)
    if kind in {"drill", "tap"}:
        spec.update(diameter=_dimension(description, "D|DIA|DIAMETER", 10.0, scale), length=50.0, tipAngle=118.0)
    return spec


def _milling_spec(description, scale, operation_kind=None):
    spec = deepcopy(DEFAULT_MILLING_TOOL)
    kind = _type_hint(description) or operation_kind
    if kind not in {None, "thread", "groove"}:
        spec["type"] = kind
    spec["diameter"] = _dimension(description, "D|DIA|DIAMETER", 10.0, scale)
    radius = _dimension(description, "CR", 0.0, scale, allow_zero=True)
    if 0 < radius <= spec["diameter"] / 2 and spec["type"] in {"mill_flat", "mill_bull"}:
        spec.update(type="mill_bull", cornerRadius=radius)
    return spec


def _header_comments(lines, turning):
    headers = {}
    for line in lines:
        for comment in _comments(line):
            for match in _COMMENT_TOOL.finditer(comment):
                key = _tool_key(match[1], turning)
                if key is not None:
                    headers.setdefault(key, comment)
    return headers


def _tool_occurrences(lines, turning, default_unit_scale):
    """Pair literal selections with nearby comments without leaking between operations."""
    headers = _header_comments(lines, turning)
    previous = ""
    previous_line = -100
    scale = default_unit_scale
    for index, line in enumerate(lines):
        comments = _comments(line)
        words = lex_words(strip_comments(line).upper())
        scale = _block_scale(words, scale)
        inline = " ".join(comments)
        nearby = previous if index - previous_line <= 8 else ""
        for key in _literal_tools(words, turning):
            yield key, inline or headers.get(key, "") or nearby, scale
        if any(word.letter == "T" for word in words):
            previous = ""
        elif comments and not _COMMENT_TOOL.search(inline) and (not words or _is_tool_comment(inline)):
            previous, previous_line = inline, index
        elif any(word.letter in {"X", "Y", "Z"} for word in words):
            previous = ""


def _block_scale(words, scale):
    for word in words:
        if word.letter == "G" and word.expr in {"20", "21"}:
            scale = 25.4 if word.expr == "20" else 1.0
    return scale


def _literal_tools(words, turning):
    for word in words:
        if word.letter == "T":
            key = _tool_key(word.expr, turning)
            if key is not None:
                yield key


def _operation_kind(words, turning):
    codes = {word.expr for word in words if word.letter == "G"}
    if codes & _DRILL_CYCLES:
        return "drill"
    if codes & _TAP_CYCLES:
        return "tap"
    if turning and codes & _TURNING_THREAD_CYCLES:
        return "thread"
    return None


def _tool_operations(lines, turning):
    """Infer geometry from the first typed cycle executed by each active tool."""
    active_tool = None
    operations = {}
    for line in lines:
        words = lex_words(strip_comments(line).upper())
        selected = tuple(_literal_tools(words, turning))
        if selected:
            active_tool = selected[-1]
        kind = _operation_kind(words, turning)
        if active_tool is not None and kind is not None:
            operations.setdefault(active_tool, kind)
    return operations


def discover_tools(source, *, turning, default_unit_scale=1.0):
    """Return inferred definitions; callers must insert only absent library keys."""
    lines = source.splitlines()
    operations = _tool_operations(lines, turning)
    descriptions = {}
    for key, description, scale in _tool_occurrences(lines, turning, default_unit_scale):
        if key not in descriptions or (not descriptions[key][0] and description):
            descriptions[key] = description, scale
    tools = {}
    for key, (description, scale) in descriptions.items():
        operation_kind = operations.get(key)
        spec = (
            _turning_spec(description, scale, operation_kind)
            if turning
            else _milling_spec(description, scale, operation_kind)
        )
        if description:
            spec["description"] = description
        tools[key] = spec
    return normalized_tools(tools) if turning else normalized_milling_tools(tools)
