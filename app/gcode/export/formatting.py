"""Low-level G-code line formatting and word parsing for exports."""

from __future__ import annotations

import re

from ..core import format_gcode_number
from ..kernel import TraceMotion
from ..kernel.events import PROGRAM_END, SUBPROGRAM_END, SUBPROGRAM_START
from ..trace_tools import arc_geometry, sample_motion
from .options import ExportOptions

_TURN_CYCLE_G_CODES = {70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92, 94}
_TURN_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, 30, 32, 33, *_TURN_CYCLE_G_CODES}
_MILL_CYCLE_G_CODES = {81, 82, 83, 84, 85, 86}
_MILL_GEOMETRY_G_CODES = {0, 1, 2, 3, 28, *_MILL_CYCLE_G_CODES}
_WORD_RE = re.compile(r"([A-Z])([+\-]?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)


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
        values = absolute if options.arc_mode == 1 and not options.incremental else relative
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
    spacer = " " if options.sequence_spacing or options.delimiter else ""
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


def _format_comment(text: str) -> str:
    body = text.strip()
    return f"({body})" if body else ""


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


def _number_full_program_lines(lines: list[str], options: ExportOptions) -> list[str]:
    numbered: list[str] = []
    sequence = options.sequence_start
    spacer = " " if options.sequence_spacing or options.delimiter else ""
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
