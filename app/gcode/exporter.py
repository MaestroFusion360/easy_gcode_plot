"""Trace-based G-code export used by the GUI and CLI.

The exporter consumes the authoritative :class:`ExecutionResult`.  It never
re-parses source G-code or reconstructs modal state from legacy UI arrays.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .core import format_gcode_number
from .kernel import ExecutionResult, TraceMotion
from .trace_tools import arc_geometry, sample_motion


@dataclass(frozen=True)
class ExportOptions:
    # 0: relative IJK, 1: absolute IJK, 2: R arcs, 3: linearized arcs,
    # 4: plot-data style (all logical motions emitted as point-to-point moves).
    arc_mode: int = 0
    source_arc_type: int = 1
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


def _g(move: int, leading_zero: bool) -> str:
    return f"G{move:02d}" if leading_zero else f"G{move}"


def _word(letter: str, value: float | None) -> str | None:
    if value is None:
        return None
    return f"{letter}{format_gcode_number(value)}"


def _axis_values(m: TraceMotion, options: ExportOptions) -> tuple[float, float, float]:
    if options.incremental:
        return m.end_x - m.start_x, m.end_y - m.start_y, m.end_z - m.start_z
    return m.end_x, m.end_y, m.end_z


def _center_words(m: TraceMotion, options: ExportOptions) -> list[str]:
    geom = arc_geometry(m, arc_type=options.source_arc_type)

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
            relative = (("I", center[0] - m.start_x), ("K", center[1] - m.start_z))
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


def _linearized_lines(
    m: TraceMotion, options: ExportOptions, motion_index: int, *, all_moves: bool = False
) -> list[str]:
    if m.move not in (2, 3) and not all_moves:
        return [motion_line(m, options)]

    points = sample_motion(
        m,
        motion_index,
        arc_points_per_circle=314,
        arc_type=options.source_arc_type,
    )
    lines: list[str] = []
    previous = (m.start_x, m.start_y, m.start_z)
    linear_move = 0 if all_moves and m.move == 0 else 1
    for point in points:
        if options.incremental:
            dx, dy, dz = point.x - previous[0], point.y - previous[1], point.z - previous[2]
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
            # ``motion_line`` computes the same incremental delta from temp.
            del dx, dy, dz
        else:
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
        lines.append(motion_line(temp, options, override_move=linear_move))
        previous = (point.x, point.y, point.z)
    return lines


def _number_lines(lines: list[str], options: ExportOptions) -> list[str]:
    if not options.sequence_numbers:
        return lines
    out: list[str] = []
    seq = options.sequence_start
    spacer = " " if options.sequence_spacing else ""
    for line in lines:
        if not line or line == "%" or line.startswith("("):
            out.append(line)
            continue
        out.append(f"N{seq}{spacer}{line}")
        seq += options.sequence_increment
    return out


def export_result(result: ExecutionResult, options: ExportOptions | None = None) -> str:
    options = options or ExportOptions()
    lines: list[str] = []
    if options.analysis_banner:
        lines.append("(EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY)")
    if options.start_program.strip():
        lines.extend(line for line in options.start_program.strip().splitlines() if line.strip())
    if options.safety_line:
        lines.append("G00 G17 G40 G49 G80 G90" if options.delimiter else "G00G17G40G49G80G90")
    if options.incremental:
        lines.append("G91")

    for index, motion in enumerate(result.motions):
        if options.arc_mode == 3 and motion.move in (2, 3):
            lines.extend(_linearized_lines(motion, options, index))
        elif options.arc_mode == 4:
            lines.extend(_linearized_lines(motion, options, index, all_moves=True))
        else:
            lines.append(motion_line(motion, options))

    if options.end_program.strip():
        lines.extend(line for line in options.end_program.strip().splitlines() if line.strip())
    else:
        lines.append(result.program_end or "M30")
    return "\n".join(_number_lines(lines, options)) + "\n"


EXPANDED_TURN_PROGRAM_MODE = 5
EXPANDED_MILL_PROGRAM_MODE = 6
_TURN_CYCLE_G_CODES = {70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92, 94}
_TURN_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, 30, 32, 33, *_TURN_CYCLE_G_CODES}
_MILL_CYCLE_G_CODES = {81, 82, 83, 84, 85, 86}
_MILL_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, *_MILL_CYCLE_G_CODES}
_TRAILER_RE = re.compile(r"M(?:0?2|30)(?=[A-Z]|\s|$)", re.IGNORECASE)
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


def _m_codes(line: str) -> set[int]:
    values: set[int] = set()
    for value in re.findall(r"M([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", line, flags=re.IGNORECASE):
        try:
            number = float(value)
        except ValueError:
            continue
        if number.is_integer():
            values.add(int(number))
    return values


def _program_number(source_lines: list[str], options: ExportOptions) -> str:
    for raw in source_lines:
        clean = _normalize_words_line(raw)
        match = re.match(r"^O(\d+)(?=\s|$)", clean)
        if match:
            return f"O{match.group(1)}"
    match = re.search(r"\bO(\d+)\b", options.start_program.upper())
    if match:
        return f"O{match.group(1)}"
    return "O0001"


def _split_trailer(line: str) -> tuple[str | None, str]:
    match = _TRAILER_RE.search(line)
    if match is None:
        return None, line
    trailer = match.group(0).upper()
    remainder = (line[: match.start()] + line[match.end() :]).strip()
    return trailer, " ".join(remainder.split())


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
        if letter == "M":
            try:
                code = int(float(value))
            except ValueError:
                continue
            if code in {2, 30, 98, 99}:
                continue
        words.append(token)
    return " ".join(words)


def _turn_program_options(options: ExportOptions | None) -> ExportOptions:
    base = options or ExportOptions()
    return replace(
        base,
        arc_mode=2,
        source_arc_type=1,
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
) -> tuple[float, float] | None:
    for motion in motions:
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
    if not result.ok:
        raise ValueError("Expanded turn program export requires a valid turning execution result")

    options = _turn_program_options(options)
    compensated_geometry = any(motion.compensation_applied for motion in result.motions)
    steps = list(_execution_slices(result))
    executed_unit_mode = any(_g_codes(_normalize_words_line(block.raw)) & {20, 21} for _, block, _ in steps)

    safety = ["G18", "G80"]
    if not executed_unit_mode:
        safety.append("G21")
    if compensated_geometry:
        safety.append("G40")

    lines: list[str] = ["%", _program_number(source_lines, options), " ".join(safety)]
    lines.append(_format_comment("EXPANDED TURN PROGRAM"))
    previous_end_mm: tuple[float, float] | None = None
    trailer: str | None = None

    for step, block, motions in steps:
        raw = block.raw
        clean = _without_sequence_number(_normalize_words_line(raw))
        detected_trailer, clean = _split_trailer(clean)
        if detected_trailer is not None:
            trailer = detected_trailer

        if not clean or clean == "%":
            continue
        if step.contour_definition:
            continue

        for comment in _extract_comments(raw):
            lines.append(_format_comment(comment))

        if block.olabel is not None and re.match(r"^O\d+(?=\s|$)", clean):
            continue
        if block.flow_node is not None:
            continue
        if _m_codes(clean) & {98, 99}:
            continue

        gcodes = _g_codes(clean)
        if gcodes & {28, 30}:
            source_reference = _remove_g_codes(clean, {40, 41, 42}) if compensated_geometry else clean
            if source_reference:
                lines.append(source_reference)
            if motions:
                previous_end_mm = (motions[-1].end_x, motions[-1].end_z)
            continue

        if not motions:
            if block.cycle_node is not None:
                continue
            if 4 in gcodes or 50 in gcodes:
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
        )

    if trailer is None:
        trailer = result.program_end or "M30"
    lines.extend([trailer, "%"])
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
) -> None:
    step_options = replace(options, incremental=not step.absolute)
    for motion in motions:
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
    if not result.ok:
        raise ValueError("Expanded mill program export requires a valid milling execution result")

    options = _mill_program_options(options)
    steps = list(_execution_slices(result))
    executed_unit_mode = any(_g_codes(_normalize_words_line(block.raw)) & {20, 21} for _, block, _ in steps)

    safety = ["G17", "G40", "G49", "G80", "G90"]
    if not executed_unit_mode:
        safety.append("G21")

    lines: list[str] = ["%", _program_number(source_lines, options), " ".join(safety)]
    lines.append(_format_comment("EXPANDED MILL PROGRAM"))
    trailer: str | None = None

    for step, block, motions in steps:
        raw = block.raw
        comments = _extract_comments(raw)
        clean = _without_sequence_number(_normalize_words_line(raw))
        detected_trailer, clean = _split_trailer(clean)
        if detected_trailer is not None:
            trailer = detected_trailer

        for comment in comments:
            lines.append(_format_comment(comment))

        if not clean or clean == "%":
            continue
        if block.olabel is not None and re.match(r"^O\d+(?=\s|$)", clean):
            continue
        if block.flow_node is not None:
            continue
        if _m_codes(clean) & {98, 99}:
            continue

        if not motions:
            gcodes = _g_codes(clean)
            geometry_words = any(
                match.group(1).upper() in {"X", "Y", "Z", "I", "J", "K", "R"} for match in _WORD_RE.finditer(clean)
            )
            if gcodes & _MILL_GEOMETRY_G_CODES or geometry_words:
                controls = _geometry_block_controls(
                    clean,
                    suppress_compensation=False,
                    geometry_g_codes=_MILL_GEOMETRY_G_CODES,
                )
            else:
                controls = clean
            if controls:
                lines.append(controls)
            continue

        controls = _geometry_block_controls(
            clean,
            suppress_compensation=False,
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
        )

    if trailer is None:
        trailer = result.program_end or "M30"
    lines.extend([trailer, "%"])
    return "\n".join(_number_full_program_lines(lines, options)) + "\n"


def export_cycle_groups(result: ExecutionResult, options: ExportOptions | None = None) -> str:
    """Export one group per executed turning-cycle block, including G72/G73."""
    if not result.ok:
        raise ValueError("Expanded turn cycle export requires a valid turning execution result")
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
        )

    return "\n".join(_number_full_program_lines(lines, options)) + ("\n" if lines else "")


def _window_export_options(window, *, arc_mode: int) -> ExportOptions:
    return ExportOptions(
        arc_mode=arc_mode,
        source_arc_type=int(window.arc_type),
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
    if result is None or not result.ok:
        raise ValueError("No valid CNC execution result is available for export")

    mode = int(window.lang)
    if mode == EXPANDED_TURN_PROGRAM_MODE:
        if not bool(window.latheMode):
            raise ValueError("Expanded turn program export requires Lathe Mode")
        return export_full_program(
            result,
            str(window.ui.editor.text()).splitlines(),
            _window_export_options(window, arc_mode=2),
        )

    if mode == EXPANDED_MILL_PROGRAM_MODE:
        if bool(window.latheMode):
            raise ValueError("Expanded mill program export requires Milling Mode")
        return export_full_mill_program(
            result,
            str(window.ui.editor.text()).splitlines(),
            _window_export_options(window, arc_mode=0),
        )

    return export_result(result, _window_export_options(window, arc_mode=mode))
