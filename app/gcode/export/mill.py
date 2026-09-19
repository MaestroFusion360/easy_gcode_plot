"""Flattened FANUC milling program export."""

from __future__ import annotations

import re
from dataclasses import replace

from ..kernel import ExecutionResult, TraceMotion
from ..kernel.events import HOME_RETURN, PROGRAM_END, PROGRAM_START, SUBPROGRAM_END, SUBPROGRAM_START, event_blocks
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

    lines: list[str] = ["%", _program_number(result, options), " ".join(safety)]
    lines.append(_format_comment("EXPANDED MILL PROGRAM"))
    program_start_blocks = event_blocks(result.events, PROGRAM_START)
    subprogram_target_blocks = {
        event.target_block
        for event in result.events
        if event.kind == SUBPROGRAM_START and event.target_block is not None
    }

    for step, block, motions in _cancellable(steps, cancelled):
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
