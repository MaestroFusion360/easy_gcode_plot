"""Milling target serialization from resolved execution, never source rewriting."""

from dataclasses import replace

from ..kernel.runtime.events import TOOL_CHANGE
from .common import _check_cancelled, _execution_slices, _require_valid_trace_export
from .formatting import _event_tool_change_line, _expanded_word, _number_lines
from .options import ExportOptions
from .trace import _append_expanded_motion

MILLING_TARGETS = ("fanuc_mill", "sinumerik_iso", "sinumerik_native")


def convert_resolved_program(result, target="fanuc_mill", options=None, *, cancelled=None):
    """Flatten cycles/variables/transforms into physical XYZ motion and controls.

    Coordinates use one G54 frame with zero offsets; controller offset tables
    and source structure are deliberately absent from this resolved program.
    """
    _require_valid_trace_export(result)
    if result.language != "fanuc_mill" or target not in MILLING_TARGETS:
        raise ValueError("Resolved conversion requires milling and a supported milling target")
    if result.rotary_axes or any(m.orientation is not None for m in result.motions):
        raise ValueError("Resolved dialect conversion currently requires three-axis XYZ geometry")
    options = options or ExportOptions()
    options = replace(
        options,
        incremental=False,
        force_addresses=True,
        resolved_target=target,
        arc_mode=1
        if target == "sinumerik_native" and options.arc_mode != 3
        else 0
        if options.arc_mode == 1
        else options.arc_mode,
    )
    lines = ["G291"] if target == "sinumerik_iso" else []
    lines.append("G17 G90 G94 G40 G49 G54 " + ("G20" if options.output_unit_scale == 25.4 else "G21"))
    motion_index, feed_mode, spindle_direction, plane = 0, "per_minute", 3, 17
    for step, _block, motions in _execution_slices(result):
        _check_cancelled(cancelled)
        for event in step.events:
            if event.kind == TOOL_CHANGE:
                line = _event_tool_change_line(event, options)
                if line:
                    lines.append(line)
        controls = [
            _expanded_word(letter, value, options)
            for letter, value in step.words
            if letter == "S" or letter == "M" and value in (0, 1, 3, 4, 5, 7, 8, 9)
        ]
        if controls:
            lines.append(" ".join(controls))
        spindle_direction = _step_spindle_direction(lines, step, spindle_direction)
        motion_index, feed_mode, plane = _append_step_motions(
            lines, step, motions, options, motion_index, feed_mode, spindle_direction, cancelled, plane
        )
    lines.append("M30")
    return "\n".join(_number_lines(lines, options)) + "\n"


def _step_spindle_direction(lines, step, previous):
    direction = next(
        (int(value) for letter, value in reversed(step.words) if letter == "M" and value in (3, 4)), previous
    )
    native_tap = any(signal.code == "CYCLE84" and signal.kind == "spindle_reverse" for signal in step.signals)
    if native_tap and direction != 3:
        lines.append("M3")
        direction = 3
    return direction


def _append_step_motions(lines, step, motions, options, motion_index, feed_mode, direction, cancelled, plane):
    dwell = sum(signal.value or 0 for signal in step.signals if signal.kind == "dwell")
    reverse = any(signal.kind == "spindle_reverse" for signal in step.signals)
    feeds = 0
    for motion in motions:
        _check_cancelled(cancelled)
        if motion.plane != plane:
            lines.append(f"G{motion.plane}")
            plane = motion.plane
        if motion.feed_mode != feed_mode:
            lines.append("G95" if motion.feed_mode == "per_revolution" else "G94")
            feed_mode = motion.feed_mode
        if motion.move == 1 and reverse and feeds == 1:
            lines.append("M4" if direction == 3 else "M3")
        _append_expanded_motion(lines, motion, options, motion_index, cancelled=cancelled)
        motion_index += 1
        if motion.move == 1:
            feeds += 1
        if feeds == 1 and dwell:
            lines.append(_dwell_line(dwell, options))
            dwell = 0
        if reverse and feeds == 2:
            lines.append(f"M{direction}")
            reverse = False
    if dwell:
        lines.append(_dwell_line(dwell, options))
    return motion_index, feed_mode, plane


def _dwell_line(seconds, options):
    if options.resolved_target == "sinumerik_native":
        return "G4 " + _expanded_word("F", seconds, options)
    return "G4 " + _expanded_word("P", seconds * 1000, options)
