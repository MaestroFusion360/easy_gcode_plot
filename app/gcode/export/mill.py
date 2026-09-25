"""Flattened FANUC milling program export."""

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
    _MILL_GEOMETRY_G_CODES,
    _WORD_RE,
    _extract_comments,
    _format_comment,
    _g_codes,
    _geometry_block_controls,
    _normalize_words_line,
    _number_full_program_lines,
    _strip_flow_event_words,
    _without_sequence_number,
    motion_line,
)
from .options import ExportOptions, _mill_program_options


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
        if motion.source_kind == "g53":
            # G53 is non-modal and its axes are machine coordinates. Keep it on
            # the same block as the generated move, without WCS projection.
            scaled = _scale_mill_motion(motion, unit_scale=step.unit_scale)
            lines.append("G53 " + motion_line(scaled, step_options))
            continue

        motion = _motion_in_active_wcs(motion, step, result)
        lines.append(
            motion_line(
                _scale_mill_motion(motion, unit_scale=step.unit_scale),
                step_options,
            )
        )


def _prepare_mill_block(
    lines: list[str],
    *,
    step,
    block,
    options: ExportOptions,
    program_start_blocks: set[int],
    subprogram_target_blocks: set[int],
) -> str | None:
    raw = block.raw

    if options.include_comments:
        for comment in _extract_comments(raw):
            lines.append(_format_comment(comment, options.comment_style))

    clean = _without_sequence_number(_normalize_words_line(raw))
    clean = _strip_flow_event_words(clean, step)

    if not clean or clean == "%":
        return None

    if block.index in program_start_blocks or block.index in subprogram_target_blocks:
        clean = re.sub(r"\bO\d+\b", "", clean, count=1, flags=re.IGNORECASE).strip()
        if not clean:
            return None

    if block.flow_node is not None:
        return None

    event_kinds = _event_kinds(step)
    if HOME_RETURN in event_kinds and 53 not in _g_codes(clean):
        lines.append(clean)
        return None

    return clean


def _append_mill_non_motion_block(
    lines: list[str],
    clean: str,
    *,
    compensated_geometry: bool,
    emitted_motion_before_wcs_change: bool,
) -> None:
    gcodes = _g_codes(clean)

    if 10 in gcodes:
        # G10 X/Y/Z/P are WCS-setting operands, not path geometry.
        # ExecutionResult exposes only final WCS offsets. Earlier motions
        # cannot be projected faithfully after an in-program WCS change.
        if emitted_motion_before_wcs_change:
            raise ValueError("Cannot export a program that changes WCS offsets after motion")
        lines.append(clean)
        return

    geometry_words = any(
        match.group(1).upper() in {"X", "Y", "Z", "I", "J", "K", "R"} for match in _WORD_RE.finditer(clean)
    )

    if gcodes & {50, 51, 52, 68, 69}:
        # The trace already contains these coordinate transforms.
        controls = _geometry_block_controls(
            clean,
            suppress_compensation=compensated_geometry,
        )
        controls = re.sub(r"\bG(?:50|51|52|68|69)\b", "", controls).strip()
    elif gcodes & _MILL_GEOMETRY_G_CODES or geometry_words:
        controls = _geometry_block_controls(
            clean,
            suppress_compensation=compensated_geometry,
            geometry_g_codes=_MILL_GEOMETRY_G_CODES,
        )
    else:
        controls = clean

    if controls:
        lines.append(controls)


def _append_mill_motion_block(
    lines: list[str],
    clean: str,
    motions: tuple[TraceMotion, ...],
    *,
    step,
    block,
    options: ExportOptions,
    result: ExecutionResult,
    compensated_geometry: bool,
) -> None:
    controls = _geometry_block_controls(
        clean,
        suppress_compensation=compensated_geometry,
        geometry_g_codes=_MILL_GEOMETRY_G_CODES,
    )
    controls = re.sub(r"\bG(?:50|51|52|68|69|53)\b", "", controls).strip()

    if controls:
        lines.append(controls)

    if options.include_comments and any(motion.cycle_generated for motion in motions):
        source = clean or block.raw.strip()
        lines.append(
            _format_comment(
                f"EXPANDED MILL CYCLE: {source}",
                options.comment_style,
            )
        )

    _append_mill_motion_chunk(
        lines,
        motions,
        step=step,
        options=options,
        result=result,
    )


def export_full_mill_program(
    result: ExecutionResult,
    source_lines: list[str],
    options: ExportOptions | None = None,
    *,
    cancelled=None,
) -> str:
    """Export one flattened FANUC milling program in actual execution order.

    Source blocks retain controller state, comments, tools and auxiliary M/S/H
    words. Geometry comes from the authoritative milling trace. Execution-step
    order expands canned cycles and repeated M98/M99 subprogram calls without
    using ``TraceMotion.source_block`` as a runtime sequence.
    """
    _require_complete_export(
        result,
        "Expanded mill program export requires a valid and complete milling execution result",
        cancelled,
    )

    del source_lines
    options = _mill_program_options(options)
    steps = list(_execution_slices(result))

    compensated_geometry = any(motion.compensation_applied for motion in result.motions)
    executed_unit_mode = any(_g_codes(_normalize_words_line(block.raw)) & {20, 21} for _, block, _ in steps)

    safety = ["G17", "G40", "G49", "G80", "G90"]
    if not executed_unit_mode:
        safety.append("G21")

    lines: list[str] = [
        "%",
        _program_number(result, options),
        " ".join(safety),
    ]
    if options.include_comments:
        lines.append(_format_comment("EXPANDED MILL PROGRAM", options.comment_style))

    program_start_blocks = event_blocks(result.events, PROGRAM_START)
    subprogram_target_blocks = {
        event.target_block
        for event in result.events
        if event.kind == SUBPROGRAM_START and event.target_block is not None
    }

    emitted_motion_before_wcs_change = False

    for step, block, motions in _cancellable(steps, cancelled):
        if motions:
            emitted_motion_before_wcs_change = True

        clean = _prepare_mill_block(
            lines,
            step=step,
            block=block,
            options=options,
            program_start_blocks=program_start_blocks,
            subprogram_target_blocks=subprogram_target_blocks,
        )
        if clean is None:
            continue

        if not motions:
            _append_mill_non_motion_block(
                lines,
                clean,
                compensated_geometry=compensated_geometry,
                emitted_motion_before_wcs_change=emitted_motion_before_wcs_change,
            )
            continue

        _append_mill_motion_block(
            lines,
            clean,
            motions,
            step=step,
            block=block,
            options=options,
            result=result,
            compensated_geometry=compensated_geometry,
        )

    lines.extend([_program_end_event_code(result), "%"])
    return "\n".join(_number_full_program_lines(lines, options)) + "\n"
