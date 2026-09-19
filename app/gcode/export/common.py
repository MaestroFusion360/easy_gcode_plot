"""Shared export validation, execution slicing and WCS projection helpers."""

from __future__ import annotations

import re
from dataclasses import replace

from ..kernel import ExecutionResult, TraceMotion
from ..kernel.events import PROGRAM_END, PROGRAM_START
from .options import ExportOptions


def _check_cancelled(cancelled) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError("Export cancelled")


def _require_complete_export(result: ExecutionResult, message: str, cancelled) -> None:
    _check_cancelled(cancelled)
    if not result.ok or not result.complete:
        raise ValueError(message)


def _cancellable(items, cancelled):
    for item in items:
        _check_cancelled(cancelled)
        yield item


def _require_valid_trace_export(result: ExecutionResult) -> None:
    if not result.ok or not result.complete:
        raise ValueError("Trace export requires a valid and complete execution result")


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


def _program_end_event_code(result: ExecutionResult) -> str:
    return next(
        (event.code for event in reversed(result.events) if event.kind == PROGRAM_END and event.code),
        result.program_end or "M30",
    )
