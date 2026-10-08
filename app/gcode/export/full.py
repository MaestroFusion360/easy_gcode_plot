"""Source and execution map to a safe source-preserving NC program."""

from __future__ import annotations

import re
from dataclasses import replace

from app.gcode.source_mode import SINUMERIK_MODE_SIEMENS, sinumerik_initial_mode

from ..comments import (
    DEFAULT_COMMENT_STYLE,
    SEMICOLON,
    extract_comments,
    format_comment,
    normalize_comment_style,
    strip_comments,
)
from ..kernel import ExecutionResult, TraceMotion
from ..kernel.geometry.coordinates import extended_wcs_id
from ..kernel.runtime.events import PROGRAM_END, PROGRAM_START, SUBPROGRAM_END, SUBPROGRAM_START
from .common import (
    ExportOptions,
    _check_cancelled,
    _execution_slices,
    _expanded_word,
    _require_continuous_motions,
    motion_line,
)


def is_native_full_program(result):
    return result.source_dialect == "sinumerik" and (
        sinumerik_initial_mode("\n".join(block.raw for block in result.program.blocks)) == SINUMERIK_MODE_SIEMENS
        or any(event.kind == "SINUMERIK_NATIVE_OPERATION" for event in result.events)
    )


def _dangerous_source(result):
    """Flow and label-dependent cycles must never survive renumbering."""
    return any(event.kind in {SUBPROGRAM_START, SUBPROGRAM_END} for event in result.events) or any(
        block.flow_node is not None
        or re.search(r"#|\b(?:IF|GOTO[FB]?|WHILE|END)\b|\bM0?(?:98|99)\b|\bG0?65\b", _strip_comments(block.raw), re.I)
        or result.language == "fanuc_turn"
        and _g_codes(_strip_comments(block.raw)) & set(range(70, 77))
        for block in result.program.blocks
    )


def normalize_full_program(result, source, options=None, *, cancelled=None):
    """Retain ordinary source blocks; unfold unsafe constructs in execution order."""
    _require_complete_export(result, "FULL requires a valid and complete execution result", cancelled)
    if result.program is None or not result.execution_steps:
        raise ValueError("FULL requires source blocks and a complete execution map")
    if source.splitlines() != [block.raw.rstrip("\r") for block in result.program.blocks]:
        raise ValueError("FULL source does not match the executed program")
    options = options or ExportOptions()
    # Validate the map even when no blocks need expansion.
    steps = list(_cancellable(_execution_slices(result), cancelled))
    native = is_native_full_program(result)
    if not _dangerous_source(result):
        return format_full_program_source(source, options, native=native, cancelled=cancelled)
    _require_continuous_motions(result, allow_source_rapids=True, allow_rotary_index_gaps=True)
    if native:
        raise ValueError("Unsafe native control flow cannot be normalized with an ISO execution map")
    # Geometry expansion while retaining a source transform would apply it twice.
    if result.language == "fanuc_turn" and any(
        _g_codes(_strip_comments(block.raw)) & {51, 52, 68} for block in result.program.blocks
    ):
        raise ValueError("FULL cannot safely expand turning cycles under source coordinate transforms")
    lines = _full_execution_lines(result, steps, options, cancelled)
    source_lines = source.splitlines()
    if source_lines and source_lines[0].strip() == "%":
        lines.insert(0, "%")
    if source_lines and source_lines[-1].strip() == "%":
        lines.append("%")
    return format_full_program_source("\n".join(lines) + "\n", options, cancelled=cancelled)


def _full_execution_lines(result, steps, options, cancelled):
    lines = []
    number = _program_number(result, options)
    if number:
        lines.append(number)
    compensated_cycles = result.language == "fanuc_turn" and any(m.compensation_applied for m in result.motions)
    if compensated_cycles:
        lines.append("G40")
    for step, block, motions in _cancellable(steps, cancelled):
        lines.extend(_full_execution_block(result, step, block, motions, options, compensated_cycles, cancelled))
    lines.append(_program_end_event_code(result))
    return lines


def _full_execution_block(result, step, block, motions, options, compensated_cycles, cancelled):
    if step.contour_definition:
        return []
    comments = (
        [_format_comment(c, options.comment_style) for c in _extract_comments(block.raw)]
        if options.include_comments
        else []
    )
    if block.flow_node is not None or any(e.kind == SUBPROGRAM_START and e.code == "G65" for e in step.events):
        return comments
    code = _without_sequence_number(_strip_comments(block.raw).strip())
    code = re.sub(r"^/\s*", "", code)
    if "#" in code:
        code = _full_evaluated_code(result, step, options)
    code = re.sub(r"\bO\d+\b", "", _strip_flow_event_words(code, step), flags=re.I).strip()
    cycle = result.language == "fanuc_turn" and (
        bool(_g_codes(code) & set(range(70, 77))) or any(m.cycle_generated for m in motions)
    )
    if cycle or compensated_cycles and motions:
        return comments + _full_turn_geometry(result, step, code, motions, options, cancelled)
    if result.language == "fanuc_turn" and motions and motions[0].move != 0 and motions[0].feed is not None:
        # Expanded cycle moves may have replaced the controller's modal feed.
        if not any(match.group(1).upper() == "F" for match in _WORD_RE.finditer(code)):
            code += " " + _expanded_word("F", motions[0].feed / step.unit_scale, options)
    if code and code != "%":
        return [code + (" " + " ".join(comments) if comments else "")]
    return comments


def _full_turn_geometry(result, step, code, motions, options, cancelled):
    type_b = result.lathe_gcode_system == "B"
    codes = (_TURN_GEOMETRY_G_CODES - {90, 92, 94}) | {77, 78, 79} if type_b else _TURN_GEOMETRY_G_CODES
    controls = _geometry_block_controls(code, suppress_compensation=True, geometry_g_codes=codes)
    lines = [controls] if controls else []
    options = replace(options, incremental=not step.absolute)
    for motion in motions:
        _check_cancelled(cancelled)
        motion = _motion_in_active_wcs(motion, step, result, turning=True)
        scaled = _scale_turn_motion(motion, unit_scale=step.unit_scale, x_is_diameter=step.x_is_diameter)
        lines.append(
            motion_line(scaled, options, override_move=33)
            if type_b and motion.threading
            else _turn_motion_line(scaled, options)
        )
    if motions and step.modal_move in {0, 1, 2, 3, 32, 33}:
        move = 33 if type_b and step.modal_move == 32 else step.modal_move
        lines.append(_expanded_word("G", move, options))
    return lines


def _full_evaluated_code(result, step, options):
    type_b = result.language == "fanuc_turn" and result.lathe_gcode_system == "B"
    words = []
    for letter, value in step.words:
        if letter == "N":
            continue
        if type_b and letter == "G":
            value = {32: 33, 90: 77, 92: 78, 94: 79, 50: 92, 98: 94, 99: 95}.get(value, value)
        if type_b and not step.absolute:
            letter = {"U": "X", "W": "Z"}.get(letter, letter)
        words.append(_expanded_word(letter, value, options))
    if type_b:
        words.insert(0, "G90" if step.absolute else "G91")
    return " ".join(words)


def export_full_mill_program(result, source_lines, options=None, *, cancelled=None):
    return normalize_full_program(result, "\n".join(source_lines) + "\n", options, cancelled=cancelled)


def export_full_program(result, source_lines, options=None, *, cancelled=None):
    return normalize_full_program(result, "\n".join(source_lines) + "\n", options, cancelled=cancelled)


def format_full_program_source(
    source: str, options: ExportOptions, *, native: bool = False, uppercase_comments: bool = False, cancelled=None
) -> str:
    """Apply formatting-only options to source blocks without rebuilding geometry."""
    _check_cancelled(cancelled)
    source = _apply_full_program_text_options(source, options, native=native)
    has_jump_flow = re.search(r"\bGOTO[FB]?\b", source, flags=re.IGNORECASE) is not None
    has_sequence_labels = re.search(r"(?im)^\s*/?\s*N\d+\b", source) is not None
    if has_jump_flow and (options.sequence_numbers or has_sequence_labels):
        raise ValueError("Sequence numbers cannot be changed in a program that uses GOTO labels")

    output: list[str] = []
    sequence = options.sequence_start
    for raw_line in _cancellable(source.splitlines(keepends=True), cancelled):
        raw_line = _format_source_comments(raw_line, options, native=native, uppercase_comments=uppercase_comments)
        line_ending = _line_ending(raw_line)
        line = raw_line[: -len(line_ending)] if line_ending else raw_line
        code, comment = _split_full_program_comment(line, native=native)
        if not code.strip():
            output.append(raw_line)
            continue

        comment_separator = " " if comment and code and code[-1].isspace() else ""
        indentation = code[: len(code) - len(code.lstrip())]
        body = code.strip()
        block_skip = ""
        if body.startswith("/"):
            body = body[1:].lstrip()
            block_skip = "/"
        body = _without_sequence_number(body)
        if not body:
            output.append(indentation + block_skip + comment + line_ending)
            continue
        if body.startswith("%") or re.match(r"^O\d+\b", body, flags=re.IGNORECASE):
            output.append(indentation + block_skip + body + comment_separator + comment + line_ending)
            continue

        body = _format_source_addresses(body, options)
        if options.sequence_numbers:
            spacer = " " if options.sequence_spacing or options.delimiter else ""
            body = f"N{sequence}{spacer}{body}"
            sequence += options.sequence_increment
        output.append(indentation + block_skip + body + comment_separator + comment + line_ending)
    return "".join(output)


def _format_source_addresses(body, options):
    fragments = re.split(r'("(?:[^"]|"")*")', body)
    for index in range(0, len(fragments), 2):
        code = _normalize_numeric_addresses(fragments[index], options)
        if options.delimiter:
            code = _ADDRESS_BOUNDARY_RE.sub(" ", code)
        elif not re.match(r"(?:TRANS|ATRANS|ROT|AROT)\b", body, re.I):
            code = re.sub(r"(?<=[0-9.\]#])\s+(?=[A-Z](?=[+\-]?(?:\d|\.|#|\[)))", "", code, flags=re.IGNORECASE)
        fragments[index] = code
    return "".join(fragments)


def _normalize_numeric_addresses(code, options):
    def normalize(match):
        letter, number = match.groups()
        value = float(number)
        if letter.upper() in {"G", "M", "T", "H", "D"} and value.is_integer():
            integer = int(value)
            number = f"{integer:02d}" if options.leading_zero and 0 <= integer < 10 else str(integer)
        else:
            number = format(value, ".12f").rstrip("0").rstrip(".") if value else "0"
        return letter + number

    return re.sub(r"(?<![A-Z_])([A-Z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?![0-9_.])", normalize, code, flags=re.I)


def _format_source_comments(line: str, options: ExportOptions, *, native=False, uppercase_comments=False) -> str:
    ending = _line_ending(line)
    body = line[: -len(ending)] if ending else line
    if native:
        code, _comment = _split_full_program_comment(body, native=True)
        return line if options.include_comments else code.rstrip() + ending
    code, separator, tail = body.partition(";")
    comments = []

    def remove(match):
        comments.append(match.group(1))
        return " "

    code = re.sub(r"\(([^()]*)\)", remove, code)
    if separator:
        comments.append(tail.strip())
    if not comments:
        return line
    if not options.include_comments:
        return code.rstrip() + ending
    if uppercase_comments:
        comments = [comment.upper() for comment in comments]
    if normalize_comment_style(options.comment_style) == SEMICOLON:
        comment = format_comment(" | ".join(comments), SEMICOLON)
    else:
        comment = " ".join(
            format_comment(c.replace("(", "[").replace(")", "]"), options.comment_style) for c in comments
        )
    return code.rstrip() + (" " if code.strip() and comment else "") + comment + ending


def _line_ending(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""


def _program_header_index(lines: list[str]) -> int | None:
    return next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s*(?:O\d+\b|;?\s*%_N_[A-Z0-9_]+_(?:MPF|SPF)\b)", line, re.IGNORECASE)
        ),
        None,
    )


def _replace_program_header(lines: list[str], header: list[str], newline: str) -> None:
    index = _program_header_index(lines)
    if index is None:
        index = next((i + 1 for i, line in enumerate(lines) if line.strip() == "%"), 0)
        lines[index:index] = [line + newline for line in header]
        return
    ending = _line_ending(lines[index])
    lines[index : index + 1] = [line + (newline if i < len(header) - 1 else ending) for i, line in enumerate(header)]


def _insert_safety_line(lines: list[str], newline: str, *, native=False) -> None:
    mode_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^\s*(?:N\d+\s*)?G\s*291\b", line, re.IGNORECASE)),
        None,
    )
    preceding_header = max((i for i in (mode_index, _program_header_index(lines)) if i is not None), default=-1)
    if preceding_header >= 0 and not _line_ending(lines[preceding_header]):
        lines[preceding_header] += newline
    safety = ["G17 G40 G90"] if native else ["G80", "G0 G17 G40 G49 G90"]
    lines[preceding_header + 1 : preceding_header + 1] = [line + newline for line in safety]


def _replace_program_end(lines: list[str], end: list[str], newline: str) -> None:
    index = next(
        (i for i in range(len(lines) - 1, -1, -1) if re.match(r"^\s*(?:N\d+\s*)?M(?:2|30)\b", lines[i], re.IGNORECASE)),
        None,
    )
    if index is not None:
        ending = _line_ending(lines[index])
        lines[index : index + 1] = [line + (newline if i < len(end) - 1 else ending) for i, line in enumerate(end)]
        return
    index = len(lines) - 1 if lines and lines[-1].strip() == "%" else len(lines)
    if index and not _line_ending(lines[index - 1]):
        lines[index - 1] += newline
    lines[index:index] = [line + newline for line in end]


def _apply_full_program_text_options(source: str, options: ExportOptions, *, native=False) -> str:
    """Apply editable program wrappers to a source-preserving full program."""
    lines = source.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in source else "\n"
    header = [line for line in options.start_program.strip().splitlines() if line.strip()]
    if header:
        _replace_program_header(lines, header, newline)
    if options.safety_line:
        _insert_safety_line(lines, newline, native=native)
    end = [line for line in options.end_program.strip().splitlines() if line.strip()]
    if end:
        _replace_program_end(lines, end, newline)
    return "".join(lines)


def _split_full_program_comment(line: str, *, native=False) -> tuple[str, str]:
    if native:
        for match in re.finditer(r'"(?:[^"]|"")*"|;', line):
            if match[0] == ";":
                return line[: match.start()], line[match.start() :]
        return line, ""
    for index, character in enumerate(line):
        if character in "(;":
            return line[:index], line[index:]
    return line, ""


def _scale_turn_motion(motion: TraceMotion, *, unit_scale: float, x_is_diameter: bool) -> TraceMotion:
    scale = unit_scale if abs(unit_scale) > 1e-12 else 1.0
    programmed_x_scale = scale if x_is_diameter else scale * 2.0
    # ``TraceMotion.arc`` is resolved in physical radial-X/Z millimetres, while
    # programmed turning X may be diameter or radius.  Keep the serialized
    # motion's x_scale consistent with the coordinates we emit.
    serialized_x_scale = 0.5 if x_is_diameter else 1.0
    return replace(
        motion,
        start_x=motion.start_x / programmed_x_scale,
        end_x=motion.end_x / programmed_x_scale,
        start_y=motion.start_y / scale,
        end_y=motion.end_y / scale,
        start_z=motion.start_z / scale,
        end_z=motion.end_z / scale,
        radius=None if motion.radius is None else motion.radius / scale,
        feed=None if motion.feed is None else motion.feed / scale,
        i=None if motion.i is None else motion.i / programmed_x_scale,
        j=None if motion.j is None else motion.j / scale,
        k=None if motion.k is None else motion.k / scale,
        arc=_scaled_arc(motion, x_scale=scale, y_scale=scale, z_scale=scale),
        x_scale=serialized_x_scale,
    )


def _turn_motion_line(motion: TraceMotion, options: ExportOptions) -> str:
    if motion.move == 1 and motion.threading:
        return motion_line(motion, options, override_move=32)
    raw = (motion.source_raw or "").lstrip().upper()
    if motion.move == 1:
        if re.match(r"G32(?:\D|$)", raw):
            return motion_line(motion, options, override_move=32)
        if re.match(r"G33(?:\D|$)", raw):
            return motion_line(motion, options, override_move=33)
        if motion.cycle_generated and re.match(r"G(?:76|92)(?:\D|$)", raw):
            return motion_line(motion, options, override_move=32)
    return motion_line(motion, options)


_TURN_CYCLE_G_CODES = {70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92, 94}

_TURN_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, 30, 32, 33, *_TURN_CYCLE_G_CODES}

_WORD_RE = re.compile(r"([A-Z])([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)

_ADDRESS_BOUNDARY_RE = re.compile(r"(?<=[0-9.\]#])(?=[A-Z](?=[+\-]?(?:\d|\.|#|\[)))", re.IGNORECASE)


def _format_comment(text: str, style: str = DEFAULT_COMMENT_STYLE) -> str:
    return format_comment(text, style)


def _strip_comments(line: str) -> str:
    return strip_comments(line)


def _extract_comments(line: str) -> list[str]:
    return extract_comments(line)


def _without_sequence_number(line: str) -> str:
    return re.sub(r"^N[+\-]?\d+(?:\.\d+)?\s*", "", line, count=1, flags=re.IGNORECASE).strip()


def _g_codes(line: str) -> set[int]:
    values: set[int] = set()
    for value in re.findall(r"G([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", line, flags=re.IGNORECASE):
        try:
            number = float(value)
        except ValueError:
            continue
        if number.is_integer():
            values.add(int(number))
    return values


def _remove_m_code(line: str, code: str | None) -> str:
    if not code or not code.upper().startswith("M"):
        return line
    try:
        target = int(code[1:])
    except ValueError:
        return line

    def repl(match: re.Match[str]) -> str:
        try:
            number = float(match.group(1))
        except ValueError:
            return match.group(0)
        if number.is_integer() and int(number) == target:
            return ""
        return match.group(0)

    return " ".join(re.sub(r"M([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", repl, line, flags=re.IGNORECASE).split())


def _strip_flow_event_words(line: str, step) -> str:
    if any(event.kind == SUBPROGRAM_START and event.code == "G65" for event in step.events):
        return ""

    out = line
    for event in step.events:
        if event.kind == PROGRAM_END:
            out = _remove_m_code(out, event.code)
        elif event.kind in {SUBPROGRAM_START, SUBPROGRAM_END}:
            out = _remove_m_code(out, "M98" if event.kind == SUBPROGRAM_START else "M99")
    if any(event.kind == SUBPROGRAM_START and event.code and event.code.startswith("O") for event in step.events):
        out = re.sub(r"[PL][+\-]?(?:\d+(?:\.\d*)?|\.\d+)", "", out, flags=re.IGNORECASE)
    return " ".join(out.split())


def _geometry_block_controls(
    line: str,
    *,
    suppress_compensation: bool,
    geometry_g_codes: set[int] | None = None,
) -> str:
    """Return only controller-state words that share a block with generated geometry."""
    geometry_codes = _TURN_GEOMETRY_G_CODES if geometry_g_codes is None else geometry_g_codes
    words: list[str] = []
    for match in _WORD_RE.finditer(line):
        letter = match.group(1).upper()
        value = match.group(2)
        token = f"{letter}{value}"
        if letter in {"N", "O", "X", "Y", "Z", "U", "V", "W", "I", "J", "K", "R", "F", "P", "Q", "A", "C"}:
            continue
        if letter == "G":
            try:
                code = int(float(value))
            except ValueError:
                continue
            if code in geometry_codes:
                continue
            if suppress_compensation and code in {40, 41, 42}:
                continue
        words.append(token)
    return " ".join(words)


def _require_complete_export(result: ExecutionResult, message: str, cancelled) -> None:
    _check_cancelled(cancelled)
    if result is None or not result.ok or not result.complete:
        raise ValueError(message)


def _cancellable(items, cancelled):
    for item in items:
        _check_cancelled(cancelled)
        yield item


def _motion_in_active_wcs(
    motion: TraceMotion,
    step,
    result: ExecutionResult,
    *,
    turning: bool = False,
) -> TraceMotion:
    offsets = dict(result.wcs_offsets)
    offsets.update({extended_wcs_id(p_number): value for p_number, value in result.extended_wcs_offsets})
    offset = offsets.get(step.active_wcs, (0.0, 0.0, 0.0))
    if not any(abs(value) > 1e-12 for value in offset):
        return motion
    ox, oy, oz = offset
    arc = motion.arc
    if arc is not None:
        cx, cy, cz = arc.center
        arc = replace(arc, center=(cx - (ox * 0.5 if turning else ox), cy - oy, cz - oz))
    return replace(
        motion,
        start_x=motion.start_x - ox,
        start_y=motion.start_y - oy,
        start_z=motion.start_z - oz,
        end_x=motion.end_x - ox,
        end_y=motion.end_y - oy,
        end_z=motion.end_z - oz,
        arc=arc,
    )


def _scaled_arc(motion: TraceMotion, *, x_scale: float, y_scale: float, z_scale: float):
    """Scale resolved kernel arc geometry together with serialized motion coordinates."""
    if motion.arc is None:
        return None
    cx, cy, cz = motion.arc.center
    # Radius is measured in the active interpolation plane.  The exporter only
    # uses non-uniform scaling for turning X, where the resolved arc already
    # lives in physical radial-X/Z space; its physical radius therefore follows
    # the Z/unit scale, not programmed diameter-X.
    radius_scale = z_scale if motion.plane == 18 else (y_scale if motion.plane == 17 else z_scale)
    return replace(
        motion.arc,
        center=(cx / x_scale, cy / y_scale, cz / z_scale),
        radius=motion.arc.radius / radius_scale,
    )


def _program_number(result: ExecutionResult, options: ExportOptions) -> str:
    start_event = next((event for event in result.events if event.kind == PROGRAM_START), None)
    if start_event is not None and start_event.program_number is not None:
        return f"O{start_event.program_number}"
    match = re.search(r"\bO(\d+)\b", options.start_program.upper())
    if match:
        return f"O{match.group(1)}"
    return ""


def _program_end_event_code(result: ExecutionResult) -> str:
    return next(
        (event.code for event in reversed(result.events) if event.kind == PROGRAM_END and event.code),
        result.program_end or "M30",
    )
