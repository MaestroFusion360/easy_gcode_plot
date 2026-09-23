"""Flattened FANUC turning program export."""

from __future__ import annotations

import re
from dataclasses import replace

from ..kernel import ExecutionResult, TraceMotion
from ..kernel.events import HOME_RETURN, PROGRAM_START, SUBPROGRAM_START, event_blocks
from .common import (
    _cancellable,
    _event_kinds,
    _execution_slices,
    _motion_in_active_wcs,
    _program_end_event_code,
    _program_number,
    _require_complete_export,
    _scaled_arc,
)
from .formatting import (
    _extract_comments,
    _format_comment,
    _g_codes,
    _geometry_block_controls,
    _normalize_words_line,
    _number_full_program_lines,
    _remove_g_codes,
    _strip_flow_event_words,
    _without_sequence_number,
    motion_line,
)
from .options import ExportOptions, _turn_program_options


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
    *,
    cancelled=None,
) -> str:
    """Export one flattened FANUC turning program in actual execution order.

    Source blocks provide controller state and comments. Geometry comes from the
    authoritative trace. Execution-step boundaries keep G72/G73 profile provenance
    separate from the block that invoked a cycle and also flatten M98/M99 calls
    without reconstructing source order from ``TraceMotion.source_block``.
    """
    _require_complete_export(
        result,
        "Expanded turn program export requires a valid and complete turning execution result",
        cancelled,
    )

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
    lines.append(_format_comment("EXPANDED TURN PROGRAM", options.comment_style))
    previous_end_mm: tuple[float, float] | None = None
    program_start_blocks = event_blocks(result.events, PROGRAM_START)
    subprogram_target_blocks = {
        event.target_block
        for event in result.events
        if event.kind == SUBPROGRAM_START and event.target_block is not None
    }

    for step, block, motions in _cancellable(steps, cancelled):
        raw = block.raw
        clean = _without_sequence_number(_normalize_words_line(raw))
        clean = _strip_flow_event_words(clean, step)
        event_kinds = _event_kinds(step)

        if not clean or clean == "%":
            continue
        if step.contour_definition:
            continue

        for comment in _extract_comments(raw):
            lines.append(_format_comment(comment, options.comment_style))

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
            lines.append(_format_comment(f"{label}: {source}", options.comment_style))

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
        lines.append(_format_comment(f"{prefix} {group_index}: {clean or block.raw.strip()}", options.comment_style))

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
