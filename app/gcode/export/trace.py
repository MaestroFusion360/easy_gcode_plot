"""Trace-based expanded execution export."""

from __future__ import annotations

from dataclasses import replace

from ..kernel import ExecutionResult, TraceMotion
from ..kernel.events import PROGRAM_END, PROGRAM_START, SUBPROGRAM_END, SUBPROGRAM_START, TOOL_CHANGE
from .common import (
    _check_cancelled,
    _execution_slices,
    _motion_in_active_wcs,
    _program_end_event_code,
    _require_valid_trace_export,
)
from .formatting import (
    _append_blank_line,
    _event_tool_change_line,
    _expanded_word,
    _format_comment,
    _integer_code,
    _linearized_lines,
    _number_lines,
    _subprogram_label,
    motion_line,
)
from .options import ExportOptions

_EXPANDED_STATE_G_CODES = {17, 18, 19, 50, 54, 55, 56, 57, 58, 59, 94, 95, 96, 97}
_EXPANDED_MACHINE_M_CODES = {3, 4, 5, 8, 9}


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


def export_result(result: ExecutionResult, options: ExportOptions | None = None, *, cancelled=None) -> str:
    _check_cancelled(cancelled)
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
            _check_cancelled(cancelled)
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
                _check_cancelled(cancelled)
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
            _check_cancelled(cancelled)
            _append_expanded_motion(lines, motion, options, motion_index, turning=turning)

    if options.include_execution_events:
        _append_blank_line(lines)
    if options.end_program.strip():
        lines.extend(line for line in options.end_program.strip().splitlines() if line.strip())
    else:
        lines.append(_program_end_event_code(result))
    return "\n".join(_number_lines(lines, options)) + "\n"
