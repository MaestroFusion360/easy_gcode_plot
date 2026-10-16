"""Conservative tool discovery from literal NC words and human comments.

Only executable T words create candidates. Comments supply geometry, never
execute expressions. Dimensions follow the units active at the T word.
"""

import math
import re
from copy import deepcopy
from functools import lru_cache, partial
from io import StringIO

from app.gcode.kernel.frontend.heidenhain import parse_heidenhain_program
from app.gcode.kernel.frontend.lang import lex_words, strip_comments
from app.gcode.kernel.frontend.program import parse_program
from app.gcode.kernel.frontend.sinumerik import parse_sinumerik_program
from app.gcode.kernel.frontend.sinumerik_turning import parse_sinumerik_turning_program
from app.native import extension, native_symbol
from app.tools.definitions import (
    DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION,
    DEFAULT_MILLING_TOOL,
    DEFAULT_TURNING_TOOL,
    MILLING_TOOL_TYPES,
    TURNING_TOOL_TYPES,
)
from app.tools.discovery_patterns import hint_text as _hint_text
from app.tools.discovery_patterns import is_tool_comment as _is_tool_comment
from app.tools.discovery_patterns import type_hint as _type_hint
from app.tools.discovery_rules import DEFAULT_DIMENSIONS, default_profile, validate_profile
from app.tools.validation import normalized_program_milling_tools, normalized_tools

_native_scan_source = native_symbol("discovery", "scan_source")
if getattr(extension("discovery").module, "COMMENT_HINTS_VERSION", 0) < 2:
    _native_scan_source = None

_COMMENTS = re.compile(r"\(([^()]*)\)|;([^\r\n]*)")
_COMMENT_TOOL = re.compile(r"\bT\s*(\d+)\b", re.IGNORECASE)
_NUMBER = r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)"
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
    return [" ".join((match[1] if match[1] is not None else match[2]).split()) for match in _COMMENTS.finditer(line)]


@lru_cache(maxsize=128)
def _dimension_pattern(names):
    return re.compile(rf"(?<![A-Z0-9_])(?:{names})\s*[=:]?\s*({_NUMBER})(?=$|[^\w.]|MM\b|IN\b|DEG\b)")


def _dimension(description, names, default, scale, *, allow_zero=False, dimensions=None):
    aliases = (dimensions or DEFAULT_DIMENSIONS)[names]
    match = _dimension_pattern(aliases).search(description.upper())
    if match is None:
        return default
    value = float(match[1].replace(",", ".")) * scale
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return default
    return value


def _turning_spec(description, scale, operation_kind=None, rules=None):
    dimension = partial(_dimension, dimensions=rules["dimensions"])
    spec = deepcopy(DEFAULT_TURNING_TOOL)
    kind = operation_kind or _type_hint(description, tuple(tuple(entry) for entry in rules["types"]))
    if kind in TURNING_TOOL_TYPES:
        spec["type"] = kind
    application = "id" if re.search(r"\bID\b", _hint_text(description)) else "od"
    if kind == "groove" and re.search(r"\bFACE\b", _hint_text(description)):
        application = "face"
    spec["applications"] = [application]
    spec["tipOrientation"] = DEFAULT_AUTO_TIP_ORIENTATION_BY_DIRECTION.get(spec["type"], {}).get(application, 3)
    spec["noseRadius"] = dimension(description, "nose_radius", 0.4, scale)
    if kind == "groove":
        spec["width"] = dimension(description, "groove_width", 3.0, scale)
        spec["noseRadius"] = dimension(description, "nose_radius", 0.0, scale, allow_zero=True)
    if kind in {"drill", "tap"}:
        spec.update(diameter=dimension(description, "turning_diameter", 10.0, scale), length=50.0, tipAngle=118.0)
    return spec


def _milling_spec(description, scale, operation_kind=None, rules=None):
    dimension = partial(_dimension, dimensions=rules["dimensions"])
    spec = deepcopy(DEFAULT_MILLING_TOOL)
    kind = (
        operation_kind
        if operation_kind in {"drill", "tap"}
        else _type_hint(description, tuple(tuple(entry) for entry in rules["types"])) or operation_kind
    )
    if kind in MILLING_TOOL_TYPES:
        spec["type"] = kind
    spec["diameter"] = dimension(description, "milling_diameter", 10.0, scale)
    radius = dimension(description, "corner_radius", 0.0, scale, allow_zero=True)
    if 0 < radius <= spec["diameter"] / 2 and spec["type"] in {"mill_flat", "mill_bull"}:
        spec.update(type="mill_bull", cornerRadius=radius)
    lengths = _milling_comment_lengths(description, scale, dimension)
    spec.update(lengths)
    if "fluteLength" not in lengths:
        spec.pop("fluteLength", None)
        spec.pop("bodyLength", None)
    spec.update(_milling_shape_fields(description, scale, spec["type"], dimension))
    return spec


def _milling_shape_fields(description, scale, kind, dimension):
    fields = {}
    angle = {
        "taper_ball_mill": ("taperAngle", "taper_angle", 6.0),
        "drill": ("tipAngle", "tip_angle", 118.0),
        "chamfer_mill": ("chamferAngle", "chamfer_angle", 90.0),
    }.get(kind)
    if angle is not None:
        field, names, default = angle
        fields[field] = dimension(description, names, default, 1.0)
    if kind == "chamfer_mill":
        tip = dimension(description, "tip_diameter", None, scale, allow_zero=True)
        if tip is not None:
            fields["tipDiameter"] = tip
    if kind in {"face_mill", "slot_mill"}:
        shank = dimension(description, "shank_diameter", None, scale)
        if shank is not None:
            fields["shankDiameter"] = shank
    return fields


def _milling_comment_lengths(description, scale, dimension):
    """Use explicit FL/BL pairs; a total alone retains the unsplit legacy shape."""
    flute_names = "flute_length"
    body_names = "body_length"
    flute = dimension(description, flute_names, None, scale)
    body = dimension(description, body_names, None, scale, allow_zero=True)
    if flute is not None and body is not None:
        return {"fluteLength": flute, "bodyLength": body, "length": flute + body}
    total = dimension(description, "total_length", None, scale)
    if total is not None or flute is not None or body is not None:
        return {"length": total if total is not None else 50.0}
    return {key: DEFAULT_MILLING_TOOL[key] for key in ("fluteLength", "bodyLength", "length")}


def _cancel_checkpoint(index, cancelled):
    if index % 256 == 0 and cancelled is not None and cancelled():
        raise InterruptedError("Tool discovery cancelled")


def _remember_tool_headers(headers, comments, turning):
    for comment in comments:
        for match in _COMMENT_TOOL.finditer(comment):
            key = _tool_key(match[1], turning)
            if key is not None:
                headers.setdefault(key, comment)


def _next_nearby_comment(previous, previous_line, index, words, comments, inline, comment_test):
    if any(word.letter == "T" for word in words):
        return "", previous_line
    if comments and not _COMMENT_TOOL.search(inline) and (not words or comment_test(inline)):
        return inline, index
    if any(word.letter in {"X", "Y", "Z"} for word in words):
        return "", previous_line
    return previous, previous_line


def _scan_source_python(source, turning, default_unit_scale, cancelled=None, comment_test=_is_tool_comment):
    """Collect tool headers, selections, and operation hints in one source pass."""
    headers = {}
    occurrences = []
    operations = {}
    active_tool = None
    selected_tool = None
    previous = ""
    previous_line = -100
    scale = default_unit_scale
    for index, line in enumerate(StringIO(source)):
        _cancel_checkpoint(index, cancelled)
        comments = _comments(line)
        _remember_tool_headers(headers, comments, turning)

        words = lex_words(strip_comments(line).upper())
        g65_call = _is_g65_call(words)
        if not g65_call:
            scale = _block_scale(words, scale)
        selected = () if g65_call else tuple(_literal_tools(words, turning))
        if any(word.letter == "O" for word in words):
            active_tool, selected_tool = None, None
        if not g65_call and any(word.letter == "T" for word in words):
            selected_tool = selected[-1] if selected else None
            if turning:
                active_tool = selected_tool
        if not turning and not g65_call and _has_tool_change(words):
            active_tool = selected_tool

        kind = None if g65_call else _operation_kind(words, turning)
        if active_tool is not None and kind is not None:
            operations.setdefault(active_tool, kind)

        inline = " ".join(comments)
        nearby = previous if index - previous_line <= 8 else ""
        for key in selected:
            occurrences.append((key, inline, nearby, scale))

        context_words = tuple(word for word in words if word.letter == "G") if g65_call else words
        previous, previous_line = _next_nearby_comment(
            previous, previous_line, index, context_words, comments, inline, comment_test
        )

    return headers, occurrences, operations


def _scan_source(source, turning, default_unit_scale, cancelled=None, comment_test=None):
    if comment_test is None:
        if _native_scan_source is not None:
            return _native_scan_source(source, turning, default_unit_scale, cancelled)
        return _scan_source_python(source, turning, default_unit_scale, cancelled)
    if _native_scan_source is not None and getattr(extension("discovery").module, "COMMENT_HINTS_VERSION", 0) >= 3:
        return _native_scan_source(source, turning, default_unit_scale, cancelled, comment_test)
    return _scan_source_python(source, turning, default_unit_scale, cancelled, comment_test)


def _is_g65_call(words) -> bool:
    for word in words:
        if word.letter != "G":
            continue
        try:
            if float(word.expr) == 65.0:
                return True
        except ValueError:
            continue
    return False


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


def _native_modal_kind(syntax, previous):
    if syntax is None:
        return previous
    if syntax.kind == "cycle":
        return {81: "drill", 82: "drill", 83: "drill", 84: "tap"}.get(syntax.cycle_code)
    return None if syntax.kind == "cycle_cancel" else previous


def _native_node_operation(node, modal_kind):
    if node.native_syntax is not None and node.native_syntax.kind == "cycle":
        return modal_kind
    if modal_kind and any(word.letter in {"X", "Y", "Z"} for word in node.words):
        return modal_kind
    return _operation_kind(node.words, False)


def _operation_tool_selection(node, turning, active_tool, selected_tool):
    # A subprogram header starts an independent source context. Milling T words
    # remain selections here too; only M6 activates the selected tool.
    header = any(word.letter == "O" for word in node.words)
    if header:
        active_tool, selected_tool = None, None
    for word in node.words:
        if word.letter == "T":
            selected_tool = _tool_key(word.expr, turning)
            if turning:
                active_tool = selected_tool
    syntax = node.native_syntax
    if syntax is not None and syntax.named_tool is not None:
        selected_tool = None if turning else syntax.named_tool
    if not turning and _has_tool_change(node.words):
        active_tool = selected_tool
    return active_tool, selected_tool


def _has_tool_change(words):
    return any(word.letter == "M" and re.fullmatch(r"\+?0*6(?:\.0*)?", word.expr) for word in words)


def _program_operation_hints(program, turning, cancelled):
    """Classify operations from the shared controller AST, never comment text."""
    operations = {}
    active_tool, selected_tool, modal_kind = None, None, None
    for index, node in enumerate(program.ast.nodes):
        _cancel_checkpoint(index, cancelled)
        if _is_g65_call(node.words):
            continue
        active_tool, selected_tool = _operation_tool_selection(node, turning, active_tool, selected_tool)
        syntax = node.native_syntax
        modal_kind = _native_modal_kind(syntax, modal_kind)
        kind = _operation_kind(node.words, True) if turning else _native_node_operation(node, modal_kind)
        if turning and syntax is not None and syntax.kind == "turning_cycle":
            kind = {81: "drill", 82: "drill", 83: "drill", 84: "tap", 93: "groove", 97: "thread"}.get(syntax.cycle_code)
        if active_tool is not None and kind is not None:
            operations.setdefault(active_tool, kind)
    return operations


def _milling_tool_occurrences(program, default_unit_scale, cancelled, comment_test=_is_tool_comment):
    """Commit a numeric or named selection only when M6 installs it."""
    scale = default_unit_scale
    previous = ""
    previous_block = -100
    pending = None
    for index, node in enumerate(program.ast.nodes):
        _cancel_checkpoint(index, cancelled)
        if _is_g65_call(node.words):
            continue
        scale = _block_scale(node.words, scale)
        for word in node.words:
            if word.letter == "G" and word.expr in {"700", "710"}:
                scale = 25.4 if word.expr == "700" else 1.0
        inline = " ".join(_comments(node.raw))
        syntax = node.native_syntax
        if any(word.letter == "O" for word in node.words):
            pending = None
        has_selection = any(word.letter == "T" for word in node.words) or (
            syntax is not None and syntax.named_tool is not None
        )
        if has_selection:
            _, key = _operation_tool_selection(node, False, None, None)
            nearby = previous if node.block_index - previous_block <= 8 else ""
            pending = (key, inline, nearby, scale) if key is not None else None
            previous = ""
        elif inline and (not node.words or comment_test(inline)):
            previous, previous_block = inline, node.block_index
        elif any(word.letter in {"T", "X", "Y", "Z"} for word in node.words):
            previous = ""
        if _has_tool_change(node.words) and pending is not None:
            key, selected_inline, nearby, selected_scale = pending
            yield key, selected_inline or inline, nearby, selected_scale


def discover_tools(
    source, *, turning, default_unit_scale=1.0, cancelled=None, source_dialect="fanuc", program=None, rules=None
):
    """Return source tool candidates and operation-based fallback geometry."""
    rules = default_profile() if rules is None else validate_profile(rules)
    if not turning and source_dialect == "heidenhain":
        return _heidenhain_tools(program or parse_heidenhain_program(source), default_unit_scale, cancelled, rules)
    comment_test = partial(_is_tool_comment, hints=tuple(tuple(entry) for entry in rules["types"]))
    if rules == default_profile():
        headers, occurrences, operations = _scan_source(source, turning, default_unit_scale, cancelled)
    else:
        headers, occurrences, operations = _scan_source(source, turning, default_unit_scale, cancelled, comment_test)
    if program is None:
        program = _discovery_program(source, turning, source_dialect)
    if program is not None:
        operations = _program_operation_hints(program, turning, cancelled)
        if not turning:
            occurrences = _milling_tool_occurrences(program, default_unit_scale, cancelled, comment_test)
    descriptions = {}
    for key, inline, nearby, scale in occurrences:
        description = inline or headers.get(key, "") or nearby
        if key not in descriptions or (not descriptions[key][0] and description):
            descriptions[key] = description, scale
    tools = {}
    for key, (description, scale) in descriptions.items():
        operation_kind = operations.get(key)
        spec = (
            _turning_spec(description, scale, operation_kind, rules)
            if turning
            else _milling_spec(description, scale, operation_kind, rules)
        )
        if description:
            spec["description"] = description
        tools[key] = spec
    return normalized_tools(tools) if turning else normalized_program_milling_tools(tools)


def _discovery_program(source, turning, source_dialect):
    if source_dialect == "sinumerik":
        parser = parse_sinumerik_turning_program if turning else parse_sinumerik_program
        return parser(source)
    return parse_program(source)


def _heidenhain_tool_headers(program):
    """Map tool keys to the comment documenting them anywhere in the program."""
    headers = {}
    for block in program.blocks:
        description = block.native_syntax.comment or ""
        match = _COMMENT_TOOL.search(description)
        if match is None:
            continue
        key = _tool_key(match[1], False)
        if key is not None:
            headers[key] = description
    return headers


def _heidenhain_call_key(syntax):
    """Resolve a TOOL CALL name or numeric/Q expression to its tool key."""
    if syntax.tool is None:
        return None
    if isinstance(syntax.tool, str):
        return syntax.tool
    return _tool_key(syntax.tool.source, False)


def _heidenhain_tools(program, scale, cancelled, rules):
    """Use native TOOL CALL ownership and nearby comments without scanning ISO words."""
    tools = {}
    headers = _heidenhain_tool_headers(program)
    for index, block in enumerate(program.blocks):
        _cancel_checkpoint(index, cancelled)
        syntax = block.native_syntax
        if syntax.units is not None:
            scale = 25.4 if syntax.units == "INCH" else 1.0
        if syntax.command != "TOOL CALL":
            continue
        key = _heidenhain_call_key(syntax)
        if key is None:
            continue
        comments = [syntax.comment or headers.get(key, "")]
        for following in program.blocks[index + 1 : index + 9]:
            if following.native_syntax.command == "TOOL CALL":
                break
            comments.append(following.native_syntax.comment or "")
        description = " ".join(comments).strip()
        spec = _milling_spec(description, scale, None, rules)
        if description:
            spec["description"] = description
        tools[key] = spec
    return normalized_program_milling_tools(tools)
