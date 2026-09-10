"""Trace-based G-code export used by the GUI and CLI.

The exporter consumes the authoritative :class:`ExecutionResult`.  It never
re-parses source G-code or reconstructs modal state from legacy UI arrays.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .core import format_gcode_number
from .kernel import ExecutionResult, TraceMotion
from .kernel.events import (
    HOME_RETURN,
    PROGRAM_END,
    PROGRAM_START,
    SUBPROGRAM_END,
    SUBPROGRAM_START,
    TOOL_CHANGE,
    event_blocks,
)
from .trace_tools import arc_geometry, sample_motion


@dataclass(frozen=True)
class ExportOptions:
    # 0: relative IJK, 1: absolute IJK, 2: R arcs, 3: linearized arcs,
    # 4: plot-data style (all logical motions emitted as point-to-point moves).
    arc_mode: int = 0
    incremental: bool = False
    force_addresses: bool = False
    sequence_numbers: bool = False
    sequence_start: int = 1
    sequence_increment: int = 1
    sequence_spacing: bool = False
    delimiter: bool = False
    leading_zero: bool = False
    start_program: str = ""
    end_program: str = ""
    safety_line: bool = False
    analysis_banner: bool = True
    linearization_tolerance: float = 0.0005
    include_execution_events: bool = True


def _g(move: int, leading_zero: bool) -> str:
    return f"G{move:02d}" if leading_zero else f"G{move}"


def _word(letter: str, value: float | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return f"{letter}0"
    return f"{letter}{value:.6f}".rstrip("0").rstrip(".")


def _linearized_word(letter: str, value: float | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return f"{letter}0"
    return f"{letter}{value:.6f}".rstrip("0").rstrip(".")


def _axis_values(m: TraceMotion, options: ExportOptions) -> tuple[float, float, float]:
    if options.incremental:
        return m.end_x - m.start_x, m.end_y - m.start_y, m.end_z - m.start_z
    return m.end_x, m.end_y, m.end_z


def _center_words(m: TraceMotion, options: ExportOptions) -> list[str]:
    geom = arc_geometry(m)

    if options.arc_mode == 2:
        if geom is not None:
            *_, sweep, radius = geom
            signed_radius = -radius if sweep > 3.141592653589793 + 1e-12 else radius
            word = _word("R", signed_radius)
            return [word] if word else []
        if m.radius is not None:
            word = _word("R", m.radius)
            return [word] if word else []

    if geom is not None:
        center = geom[4]
        if m.plane == 18:
            absolute = (("I", center[0]), ("K", center[1]))
            relative = (("I", center[0] - (m.start_x * m.x_scale)), ("K", center[1] - m.start_z))
        elif m.plane == 19:
            absolute = (("J", center[0]), ("K", center[1]))
            relative = (("J", center[0] - m.start_y), ("K", center[1] - m.start_z))
        else:
            absolute = (("I", center[0]), ("J", center[1]))
            relative = (("I", center[0] - m.start_x), ("J", center[1] - m.start_y))
        values = absolute if options.arc_mode == 1 else relative
        return [word for letter, value in values if (word := _word(letter, value))]

    if options.arc_mode == 1:
        if m.plane == 18:
            values = (("I", m.i), ("K", m.k))
        elif m.plane == 19:
            values = (("J", m.j), ("K", m.k))
        else:
            values = (("I", m.i), ("J", m.j))
        return [word for letter, value in values if (word := _word(letter, value))]

    return [word for letter, value in (("I", m.i), ("J", m.j), ("K", m.k)) if (word := _word(letter, value))]


def motion_line(m: TraceMotion, options: ExportOptions, *, override_move: int | None = None) -> str:
    move = m.move if override_move is None else override_move
    x, y, z = _axis_values(m, options)
    words: list[str] = [_g(move, options.leading_zero)]

    show_y = options.force_addresses or abs(y) > 1e-12 or abs(m.start_y) > 1e-12 or abs(m.end_y) > 1e-12
    axis_words = (
        _word("X", x),
        _word("Y", y if show_y else None),
        _word("Z", z),
    )
    words.extend(word for word in axis_words if word)

    if m.move in (2, 3) and move in (2, 3):
        words.extend(_center_words(m, options))

    if move != 0 and m.feed is not None:
        feed_word = _word("F", m.feed)
        if feed_word:
            words.append(feed_word)

    sep = " " if options.delimiter else ""
    return sep.join(words)


def _require_valid_trace_export(result: ExecutionResult) -> None:
    if not result.ok or not result.complete:
        raise ValueError("Trace export requires a valid and complete execution result")


def _linearized_motion_line(m: TraceMotion, options: ExportOptions, *, override_move: int) -> str:
    x, y, z = _axis_values(m, options)
    words: list[str] = [_g(override_move, options.leading_zero)]
    show_y = options.force_addresses or abs(y) > 1e-12 or abs(m.start_y) > 1e-12 or abs(m.end_y) > 1e-12
    words.extend(
        word
        for word in (
            _linearized_word("X", x),
            _linearized_word("Y", y if show_y else None),
            _linearized_word("Z", z),
        )
        if word
    )
    if override_move != 0 and m.feed is not None:
        feed_word = _word("F", m.feed)
        if feed_word:
            words.append(feed_word)
    sep = " " if options.delimiter else ""
    return sep.join(words)


def _linearized_lines(
    m: TraceMotion, options: ExportOptions, motion_index: int, *, all_moves: bool = False
) -> list[str]:
    if m.move not in (2, 3) and not all_moves:
        return [motion_line(m, options)]

    if m.move in (2, 3) and arc_geometry(m) is None:
        raise ValueError("Linearized arc export requires resolved arc geometry")
    points = sample_motion(m, motion_index, chord_error=float(options.linearization_tolerance))
    lines: list[str] = []
    previous = (m.start_x, m.start_y, m.start_z)
    linear_move = 0 if all_moves and m.move == 0 else 1
    for point in points:
        temp = TraceMotion(
            linear_move,
            previous[0],
            previous[2],
            point.x,
            point.z,
            feed=m.feed,
            start_y=previous[1],
            end_y=point.y,
            source_block=m.source_block,
        )
        lines.append(_linearized_motion_line(temp, options, override_move=linear_move))
        previous = (point.x, point.y, point.z)
    return lines


def _number_lines(lines: list[str], options: ExportOptions) -> list[str]:
    if not options.sequence_numbers:
        return lines
    out: list[str] = []
    seq = options.sequence_start
    spacer = " " if options.sequence_spacing else ""
    for line in lines:
        if not line or line == "%" or line.startswith("(") or line.lstrip().upper().startswith("O"):
            out.append(line)
            continue
        out.append(f"N{seq}{spacer}{line}")
        seq += options.sequence_increment
    return out


def _append_blank_line(lines: list[str]) -> None:
    if lines and lines[-1]:
        lines.append("")


def _event_tool_change_line(event, options: ExportOptions) -> str:
    words: list[str] = []
    if event.tool:
        words.append(event.tool.upper())
    if event.code and event.code.upper() not in words:
        words.append(event.code.upper())
    return (" " if options.delimiter else "").join(words)


def _subprogram_label(event) -> str:
    if event.program_number is not None:
        return f"O{event.program_number}"
    if event.code and event.code.upper().startswith("O"):
        return event.code.upper()
    return "UNKNOWN"


def _append_expanded_event(
    lines: list[str],
    event,
    options: ExportOptions,
    call_counts: dict[str, int],
    active_calls: dict[int, tuple[str, int]],
) -> None:
    if event.kind == TOOL_CHANGE:
        tool_line = _event_tool_change_line(event, options)
        if tool_line:
            _append_blank_line(lines)
            lines.append(tool_line)
            lines.append("")
        return

    if event.kind == SUBPROGRAM_START:
        label = _subprogram_label(event)
        call_counts[label] = call_counts.get(label, 0) + 1
        occurrence = call_counts[label]
        active_calls[event.call_depth] = (label, occurrence)
        _append_blank_line(lines)
        lines.append(_format_comment(f"SUBPROGRAM {label} START - CALL {occurrence}"))
        return

    if event.kind == SUBPROGRAM_END:
        label = _subprogram_label(event)
        active_label, occurrence = active_calls.pop(event.call_depth, (label, call_counts.get(label, 1)))
        lines.append(_format_comment(f"SUBPROGRAM {active_label} END - CALL {occurrence}"))
        lines.append("")
        return

    # Home-return blocks are serialized as executable G28/G53 step controls,
    # not as comments plus a second generated movement.


_EXPANDED_STATE_G_CODES = {17, 18, 19, 50, 54, 55, 56, 57, 58, 59, 94, 95, 96, 97}
_EXPANDED_MACHINE_M_CODES = {3, 4, 5, 8, 9}


def _integer_code(value: float) -> int | None:
    number = int(value)
    return number if abs(value - number) <= 1e-9 else None


def _expanded_word(letter: str, value: float, options: ExportOptions) -> str:
    code = _integer_code(value) if letter in {"G", "M"} else None
    if code is not None:
        if options.leading_zero and 0 <= code < 10:
            return f"{letter}{code:02d}"
        return f"{letter}{code}"
    return f"{letter}{format_gcode_number(value)}"


def _expanded_step_control(step, options: ExportOptions) -> tuple[str, bool]:
    """Return non-geometric execution controls and whether they replace step motions."""
    gcodes = {code for letter, value in step.words if letter == "G" and (code := _integer_code(value)) is not None}
    home_or_machine_move = bool(gcodes & {28, 30, 53})
    dwell = 4 in gcodes
    tokens: list[str] = []

    for letter, value in step.words:
        letter = letter.upper()
        code = _integer_code(value) if letter in {"G", "M"} else None
        keep = False
        if home_or_machine_move:
            keep = letter not in {"N", "O", "T"} and not (letter == "M" and code in {2, 6, 30, 98, 99})
        elif dwell:
            keep = (letter == "G" and code == 4) or letter in {"P", "X"}
            keep = keep or (letter == "M" and code in _EXPANDED_MACHINE_M_CODES) or letter == "S"
        elif letter == "G":
            keep = code in _EXPANDED_STATE_G_CODES
        elif letter == "M":
            keep = code in _EXPANDED_MACHINE_M_CODES
        elif letter == "S":
            keep = True
        if keep:
            tokens.append(_expanded_word(letter, value, options))

    return (" " if options.delimiter else "").join(tokens), home_or_machine_move or dwell


def _motion_in_active_wcs(
    motion: TraceMotion,
    step,
    result: ExecutionResult,
    *,
    turning: bool = False,
) -> TraceMotion:
    offsets = dict(result.wcs_offsets)
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


def _append_expanded_motion(
    lines: list[str],
    motion: TraceMotion,
    options: ExportOptions,
    index: int,
    *,
    override_move: int | None = None,
    turning: bool = False,
) -> None:
    def append_line(line: str) -> None:
        if turning and options.incremental:
            line = line.replace("X", "U").replace("Z", "W")
        lines.append(line)

    if options.arc_mode == 2 and motion.arc is not None and motion.arc.full_circle:
        axes = {17: (0, 1, 2), 18: (0, 2, 1), 19: (1, 2, 0)}
        a, b, other = axes[motion.plane]
        start = [motion.start_x * motion.x_scale, motion.start_y, motion.start_z]
        end = [motion.end_x * motion.x_scale, motion.end_y, motion.end_z]
        center = motion.arc.center
        midpoint = list(start)
        midpoint[a] = 2.0 * center[a] - start[a]
        midpoint[b] = 2.0 * center[b] - start[b]
        midpoint[other] = (start[other] + end[other]) / 2.0
        midpoint_x = midpoint[0] / motion.x_scale
        half_arc = replace(motion.arc, sweep=3.141592653589793, full_circle=False)
        first = replace(
            motion,
            end_x=midpoint_x,
            end_y=midpoint[1],
            end_z=midpoint[2],
            arc=half_arc,
        )
        second = replace(
            motion,
            start_x=midpoint_x,
            start_y=midpoint[1],
            start_z=midpoint[2],
            arc=half_arc,
        )
        append_line(motion_line(first, options, override_move=override_move))
        append_line(motion_line(second, options, override_move=override_move))
        return
    if options.arc_mode == 3 and motion.move in (2, 3):
        for line in _linearized_lines(motion, options, index):
            append_line(line)
    elif options.arc_mode == 4:
        for line in _linearized_lines(motion, options, index, all_moves=True):
            append_line(line)
    else:
        append_line(motion_line(motion, options, override_move=override_move))


def export_result(result: ExecutionResult, options: ExportOptions | None = None) -> str:
    _require_valid_trace_export(result)
    options = options or ExportOptions()
    lines: list[str] = []
    if options.start_program.strip():
        lines.extend(line for line in options.start_program.strip().splitlines() if line.strip())
    elif options.include_execution_events:
        start_event = next((event for event in result.events if event.kind == PROGRAM_START), None)
        if start_event is not None and start_event.code:
            lines.append(start_event.code.upper())
    if options.analysis_banner:
        lines.append("(EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY)")
    if options.safety_line:
        lines.append("G00 G17 G40 G49 G80 G90" if options.delimiter else "G00G17G40G49G80G90")
    turning = result.language == "fanuc_turn"
    if options.incremental and not turning:
        lines.append("G91")

    motion_index = 0
    if options.include_execution_events and result.program is not None and result.execution_steps:
        call_counts: dict[str, int] = {}
        active_calls: dict[int, tuple[str, int]] = {}
        for step, _block, motions in _execution_slices(result):
            for event in step.events:
                if event.kind not in {PROGRAM_START, PROGRAM_END}:
                    _append_expanded_event(lines, event, options, call_counts, active_calls)
            control, replaces_motions = _expanded_step_control(step, options)
            if control:
                lines.append(control)
            step_gcodes = {
                code for letter, value in step.words if letter == "G" and (code := _integer_code(value)) is not None
            }
            threading_code = next((code for code in (32, 33) if code in step_gcodes), None)
            for motion in motions:
                if not replaces_motions:
                    _append_expanded_motion(
                        lines,
                        _motion_in_active_wcs(motion, step, result, turning=turning),
                        options,
                        motion_index,
                        override_move=threading_code,
                        turning=turning,
                    )
                motion_index += 1
    else:
        for motion_index, motion in enumerate(result.motions):
            _append_expanded_motion(lines, motion, options, motion_index, turning=turning)

    if options.include_execution_events:
        _append_blank_line(lines)
    if options.end_program.strip():
        lines.extend(line for line in options.end_program.strip().splitlines() if line.strip())
    else:
        lines.append(_program_end_event_code(result))
    return "\n".join(_number_lines(lines, options)) + "\n"


TURN_FULL_PROGRAM_MODE = 0
MILL_FULL_PROGRAM_MODE = 1
EXPANDED_EXECUTION_MODE = 2
PLOT_DATA_MODE = 3
DXF_MODE = 4
_TURN_CYCLE_G_CODES = {70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92, 94}
_TURN_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, 30, 32, 33, *_TURN_CYCLE_G_CODES}
_MILL_CYCLE_G_CODES = {81, 82, 83, 84, 85, 86}
_MILL_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, *_MILL_CYCLE_G_CODES}
_WORD_RE = re.compile(r"([A-Z])([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)


def _strip_comments(line: str) -> str:
    out = line
    while "(" in out and ")" in out:
        start = out.find("(")
        end = out.find(")", start + 1)
        if end < 0:
            break
        out = out[:start] + out[end + 1 :]
    if ";" in out:
        out = out.split(";", 1)[0]
    return out


def _extract_comments(line: str) -> list[str]:
    comments = [match.group(1).strip() for match in re.finditer(r"\((.*?)\)", line) if match.group(1).strip()]
    semi = line.find(";")
    if semi >= 0:
        text = line[semi + 1 :].strip()
        if text:
            comments.append(text)
    return comments


def _format_comment(text: str) -> str:
    body = text.strip()
    return f"({body})" if body else ""


def _normalize_words_line(line: str) -> str:
    return " ".join(_strip_comments(line).strip().upper().split())


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


def _program_number(result: ExecutionResult, options: ExportOptions) -> str:
    start_event = next((event for event in result.events if event.kind == PROGRAM_START), None)
    if start_event is not None and start_event.program_number is not None:
        return f"O{start_event.program_number}"
    match = re.search(r"\bO(\d+)\b", options.start_program.upper())
    if match:
        return f"O{match.group(1)}"
    return "O0001"


def _event_kinds(step) -> set[str]:
    return {event.kind for event in step.events}


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
    out = line
    for event in step.events:
        if event.kind == PROGRAM_END:
            out = _remove_m_code(out, event.code)
        elif event.kind in {SUBPROGRAM_START, SUBPROGRAM_END}:
            out = _remove_m_code(out, "M98" if event.kind == SUBPROGRAM_START else "M99")
    if any(event.kind == SUBPROGRAM_START and event.code and event.code.startswith("O") for event in step.events):
        out = re.sub(r"\b[PL][+\-]?(?:\d+(?:\.\d*)?|\.\d+)\b", "", out, flags=re.IGNORECASE)
    return " ".join(out.split())


def _program_end_event_code(result: ExecutionResult) -> str:
    return next(
        (event.code for event in reversed(result.events) if event.kind == PROGRAM_END and event.code),
        result.program_end or "M30",
    )


def _remove_g_codes(line: str, codes: set[int]) -> str:
    if not codes:
        return line

    def repl(match: re.Match[str]) -> str:
        try:
            number = float(match.group(1))
        except ValueError:
            return match.group(0)
        if number.is_integer() and int(number) in codes:
            return ""
        return match.group(0)

    return " ".join(re.sub(r"G([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", repl, line, flags=re.IGNORECASE).split())


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


def _turn_program_options(options: ExportOptions | None) -> ExportOptions:
    base = options or ExportOptions()
    return replace(
        base,
        arc_mode=2,
        incremental=False,
        force_addresses=False,
        analysis_banner=False,
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
    raw = (motion.source_raw or "").lstrip().upper()
    if motion.move == 1:
        if re.match(r"G32(?:\D|$)", raw):
            return motion_line(motion, options, override_move=32)
        if re.match(r"G33(?:\D|$)", raw):
            return motion_line(motion, options, override_move=33)
        if motion.cycle_generated and re.match(r"G(?:76|92)(?:\D|$)", raw):
            return motion_line(motion, options, override_move=32)
    return motion_line(motion, options)


def _number_full_program_lines(lines: list[str], options: ExportOptions) -> list[str]:
    numbered: list[str] = []
    sequence = options.sequence_start
    spacer = " " if options.sequence_spacing else ""
    for line in lines:
        stripped = line.strip()
        structural = not stripped or stripped == "%" or stripped.startswith("O") or stripped.startswith("(")
        output = line if options.delimiter or structural else line.replace(" ", "")
        if not options.sequence_numbers or structural:
            numbered.append(output)
            continue
        numbered.append(f"N{sequence}{spacer}{output}")
        sequence += options.sequence_increment
    return numbered


def _execution_slices(result: ExecutionResult):
    if result.program is None or not result.execution_steps:
        raise ValueError("Expanded program export requires execution steps")
    blocks = {block.index: block for block in result.program.blocks}
    cursor = 0
    for step in result.execution_steps:
        block = blocks.get(step.source_block)
        if block is None:
            raise ValueError(f"Execution step references missing source block {step.source_block}")
        end = cursor + step.emitted_count
        if end > len(result.motions):
            raise ValueError("Execution step motion counts do not match the trace")
        motions = result.motions[cursor:end]
        cursor = end
        yield step, block, motions
    if cursor != len(result.motions):
        raise ValueError("Execution step motion counts do not consume the complete trace")


def _append_motion_chunk(
    lines: list[str],
    motions: tuple[TraceMotion, ...],
    *,
    step,
    options: ExportOptions,
    previous_end_mm: tuple[float, float] | None,
    result: ExecutionResult,
) -> tuple[float, float] | None:
    for motion in motions:
        motion = _motion_in_active_wcs(motion, step, result, turning=True)
        start_mm = (motion.start_x, motion.start_z)
        if previous_end_mm is not None and (
            abs(previous_end_mm[0] - start_mm[0]) > 1e-6 or abs(previous_end_mm[1] - start_mm[1]) > 1e-6
        ):
            reposition = TraceMotion(
                move=0,
                start_x=previous_end_mm[0],
                start_z=previous_end_mm[1],
                end_x=motion.start_x,
                end_z=motion.start_z,
                plane=18,
            )
            lines.append(
                motion_line(
                    _scale_turn_motion(
                        reposition,
                        unit_scale=step.unit_scale,
                        x_is_diameter=step.x_is_diameter,
                    ),
                    options,
                )
            )
        scaled = _scale_turn_motion(
            motion,
            unit_scale=step.unit_scale,
            x_is_diameter=step.x_is_diameter,
        )
        lines.append(_turn_motion_line(scaled, options))
        previous_end_mm = (motion.end_x, motion.end_z)
    return previous_end_mm


def export_full_program(
    result: ExecutionResult,
    source_lines: list[str],
    options: ExportOptions | None = None,
) -> str:
    """Export one flattened FANUC turning program in actual execution order.

    Source blocks provide controller state and comments. Geometry comes from the
    authoritative trace. Execution-step boundaries keep G72/G73 profile provenance
    separate from the block that invoked a cycle and also flatten M98/M99 calls
    without reconstructing source order from ``TraceMotion.source_block``.
    """
    if not result.ok or not result.complete:
        raise ValueError("Expanded turn program export requires a valid and complete turning execution result")

    del source_lines
    options = _turn_program_options(options)
    compensated_geometry = any(motion.compensation_applied for motion in result.motions)
    steps = list(_execution_slices(result))
    executed_unit_mode = any(_g_codes(_normalize_words_line(block.raw)) & {20, 21} for _, block, _ in steps)

    safety = ["G18", "G80"]
    if not executed_unit_mode:
        safety.append("G21")
    if compensated_geometry:
        safety.append("G40")

    lines: list[str] = ["%", _program_number(result, options), " ".join(safety)]
    lines.append(_format_comment("EXPANDED TURN PROGRAM"))
    previous_end_mm: tuple[float, float] | None = None
    program_start_blocks = event_blocks(result.events, PROGRAM_START)
    subprogram_target_blocks = {
        event.target_block
        for event in result.events
        if event.kind == SUBPROGRAM_START and event.target_block is not None
    }

    for step, block, motions in steps:
        raw = block.raw
        clean = _without_sequence_number(_normalize_words_line(raw))
        clean = _strip_flow_event_words(clean, step)
        event_kinds = _event_kinds(step)

        if not clean or clean == "%":
            continue
        if step.contour_definition:
            continue

        for comment in _extract_comments(raw):
            lines.append(_format_comment(comment))

        if block.index in program_start_blocks or block.index in subprogram_target_blocks:
            clean = re.sub(r"\bO\d+\b", "", clean, count=1, flags=re.IGNORECASE).strip()
            if not clean:
                continue
        if block.flow_node is not None:
            continue
        gcodes = _g_codes(clean)
        if HOME_RETURN in event_kinds:
            source_reference = _remove_g_codes(clean, {40, 41, 42}) if compensated_geometry else clean
            if source_reference:
                lines.append(source_reference)
            if motions:
                previous_end_mm = (motions[-1].end_x, motions[-1].end_z)
            continue

        if not motions:
            if block.cycle_node is not None:
                control = _geometry_block_controls(clean, suppress_compensation=compensated_geometry)
            elif 4 in gcodes or 50 in gcodes:
                control = clean
            elif block.motion_node is None:
                control = clean
            else:
                control = _geometry_block_controls(clean, suppress_compensation=compensated_geometry)
            if compensated_geometry:
                control = _remove_g_codes(control, {40, 41, 42})
            if control:
                lines.append(control)
            continue

        controls = _geometry_block_controls(clean, suppress_compensation=compensated_geometry)
        if controls:
            lines.append(controls)

        if any(motion.cycle_generated for motion in motions):
            label = "FINISH CONTOUR" if 70 in gcodes else "EXPANDED TURN CYCLE"
            source = clean or block.raw.strip()
            lines.append(_format_comment(f"{label}: {source}"))

        previous_end_mm = _append_motion_chunk(
            lines,
            motions,
            step=step,
            options=options,
            previous_end_mm=previous_end_mm,
            result=result,
        )

    lines.extend([_program_end_event_code(result), "%"])
    return "\n".join(_number_full_program_lines(lines, options)) + "\n"


def _mill_program_options(options: ExportOptions | None) -> ExportOptions:
    base = options or ExportOptions()
    return replace(
        base,
        arc_mode=0,
        incremental=False,
        force_addresses=False,
        analysis_banner=False,
    )


def _scale_mill_motion(motion: TraceMotion, *, unit_scale: float) -> TraceMotion:
    scale = unit_scale if abs(unit_scale) > 1e-12 else 1.0
    return replace(
        motion,
        start_x=motion.start_x / scale,
        start_y=motion.start_y / scale,
        start_z=motion.start_z / scale,
        end_x=motion.end_x / scale,
        end_y=motion.end_y / scale,
        end_z=motion.end_z / scale,
        radius=None if motion.radius is None else motion.radius / scale,
        feed=None if motion.feed is None else motion.feed / scale,
        i=None if motion.i is None else motion.i / scale,
        j=None if motion.j is None else motion.j / scale,
        k=None if motion.k is None else motion.k / scale,
        arc=_scaled_arc(motion, x_scale=scale, y_scale=scale, z_scale=scale),
    )


def _append_mill_motion_chunk(
    lines: list[str],
    motions: tuple[TraceMotion, ...],
    *,
    step,
    options: ExportOptions,
    result: ExecutionResult,
) -> None:
    step_options = replace(options, incremental=not step.absolute)
    for motion in motions:
        motion = _motion_in_active_wcs(motion, step, result)
        lines.append(
            motion_line(
                _scale_mill_motion(motion, unit_scale=step.unit_scale),
                step_options,
            )
        )


def export_full_mill_program(
    result: ExecutionResult,
    source_lines: list[str],
    options: ExportOptions | None = None,
) -> str:
    """Export one flattened FANUC milling program in actual execution order.

    Source blocks retain controller state, comments, tools and auxiliary M/S/H
    words. Geometry comes from the authoritative milling trace. Execution-step
    order expands canned cycles and repeated M98/M99 subprogram calls without
    using ``TraceMotion.source_block`` as a runtime sequence.
    """
    if not result.ok or not result.complete:
        raise ValueError("Expanded mill program export requires a valid and complete milling execution result")

    del source_lines
    options = _mill_program_options(options)
    steps = list(_execution_slices(result))
    compensated_geometry = any(motion.compensation_applied for motion in result.motions)
    executed_unit_mode = any(_g_codes(_normalize_words_line(block.raw)) & {20, 21} for _, block, _ in steps)

    safety = ["G17", "G40", "G49", "G80", "G90"]
    if not executed_unit_mode:
        safety.append("G21")

    lines: list[str] = ["%", _program_number(result, options), " ".join(safety)]
    lines.append(_format_comment("EXPANDED MILL PROGRAM"))
    program_start_blocks = event_blocks(result.events, PROGRAM_START)
    subprogram_target_blocks = {
        event.target_block
        for event in result.events
        if event.kind == SUBPROGRAM_START and event.target_block is not None
    }

    for step, block, motions in steps:
        raw = block.raw
        comments = _extract_comments(raw)
        clean = _without_sequence_number(_normalize_words_line(raw))
        clean = _strip_flow_event_words(clean, step)
        event_kinds = _event_kinds(step)

        for comment in comments:
            lines.append(_format_comment(comment))

        if not clean or clean == "%":
            continue
        if block.index in program_start_blocks or block.index in subprogram_target_blocks:
            clean = re.sub(r"\bO\d+\b", "", clean, count=1, flags=re.IGNORECASE).strip()
            if not clean:
                continue
        if block.flow_node is not None:
            continue
        if not clean and event_kinds & {SUBPROGRAM_START, SUBPROGRAM_END, PROGRAM_END}:
            continue
        if HOME_RETURN in event_kinds:
            if clean:
                lines.append(clean)
            continue

        if not motions:
            gcodes = _g_codes(clean)
            geometry_words = any(
                match.group(1).upper() in {"X", "Y", "Z", "I", "J", "K", "R"} for match in _WORD_RE.finditer(clean)
            )
            if gcodes & _MILL_GEOMETRY_G_CODES or geometry_words:
                controls = _geometry_block_controls(
                    clean,
                    suppress_compensation=compensated_geometry,
                    geometry_g_codes=_MILL_GEOMETRY_G_CODES,
                )
            else:
                controls = clean
            if controls:
                lines.append(controls)
            continue

        controls = _geometry_block_controls(
            clean,
            suppress_compensation=compensated_geometry,
            geometry_g_codes=_MILL_GEOMETRY_G_CODES,
        )
        if controls:
            lines.append(controls)

        if any(motion.cycle_generated for motion in motions):
            source = clean or block.raw.strip()
            lines.append(_format_comment(f"EXPANDED MILL CYCLE: {source}"))

        _append_mill_motion_chunk(
            lines,
            motions,
            step=step,
            options=options,
            result=result,
        )

    lines.extend([_program_end_event_code(result), "%"])
    return "\n".join(_number_full_program_lines(lines, options)) + "\n"


def export_cycle_groups(result: ExecutionResult, options: ExportOptions | None = None) -> str:
    """Export one group per executed turning-cycle block, including G72/G73."""
    if not result.ok or not result.complete:
        raise ValueError("Expanded turn cycle export requires a valid and complete turning execution result")
    options = _turn_program_options(options)
    lines: list[str] = ["G18"]
    previous_unit: tuple[float, bool] | None = None
    group_index = 0

    for step, block, motions in _execution_slices(result):
        if not motions or not any(motion.cycle_generated for motion in motions):
            continue
        group_index += 1
        clean = _without_sequence_number(_normalize_words_line(block.raw))
        gcodes = _g_codes(clean)
        prefix = "FINISH CONTOUR" if 70 in gcodes else "EXPANDED TURN CYCLE"
        lines.append(_format_comment(f"{prefix} {group_index}: {clean or block.raw.strip()}"))

        unit_key = (step.unit_scale, step.x_is_diameter)
        if unit_key != previous_unit:
            lines.append("G20" if abs(step.unit_scale - 25.4) < 1e-9 else "G21")
            lines.append("G190" if step.x_is_diameter else "G191")
            previous_unit = unit_key

        _append_motion_chunk(
            lines,
            motions,
            step=step,
            options=options,
            previous_end_mm=None,
            result=result,
        )

    return "\n".join(_number_full_program_lines(lines, options)) + ("\n" if lines else "")


def _window_export_options(window, *, arc_mode: int) -> ExportOptions:
    return ExportOptions(
        arc_mode=arc_mode,
        incremental=bool(window.incrMode),
        force_addresses=bool(window.forceAdr),
        sequence_numbers=bool(window.seqNum),
        sequence_start=int(window.seqNumStart),
        sequence_increment=int(window.seqNumIncr),
        sequence_spacing=bool(window.seqNumSpacing),
        delimiter=bool(window.delim),
        leading_zero=bool(window.leadingZero),
        start_program=str(window.startPgmExp or ""),
        end_program=str(window.endPgmExp or ""),
        safety_line=bool(window.safLine),
    )


def export_pgm(window) -> str:
    """Compatibility entry point for the existing MainWindow export action."""
    result = getattr(window, "execution_result", None)
    if result is None or not result.ok or not result.complete:
        raise ValueError("No valid CNC execution result is available for export")

    mode = int(window.exportMode)
    if mode == TURN_FULL_PROGRAM_MODE:
        if not bool(window.latheMode):
            raise ValueError("Turn Full Program export requires Lathe Mode")
        return export_full_program(
            result,
            str(window.ui.editor.text()).splitlines(),
            _window_export_options(window, arc_mode=2),
        )

    if mode == MILL_FULL_PROGRAM_MODE:
        if bool(window.latheMode):
            raise ValueError("Mill Full Program export requires Milling Mode")
        return export_full_mill_program(
            result,
            str(window.ui.editor.text()).splitlines(),
            _window_export_options(window, arc_mode=0),
        )

    if mode == EXPANDED_EXECUTION_MODE:
        return export_result(result, _window_export_options(window, arc_mode=int(window.exportArcMode)))

    if mode == PLOT_DATA_MODE:
        return export_result(
            result,
            replace(
                _window_export_options(window, arc_mode=4),
                incremental=False,
                include_execution_events=False,
            ),
        )

    if mode == DXF_MODE:
        raise ValueError("DXF export requires a file target")

    raise ValueError(f"Unknown export mode: {mode}")
