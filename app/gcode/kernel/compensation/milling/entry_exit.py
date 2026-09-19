"""Entry and exit transition solving for milling cutter compensation."""

from __future__ import annotations

from dataclasses import replace

from ...api.types import TraceMotion
from .joins import _get_progress
from .offset import _solve_standalone
from .projection import (
    _project_motion,
    _projected_to_motion,
    _retarget_end,
    _retarget_start,
    _unproject,
)

_GEOMETRY_TOLERANCE = 0.01


def _find_entry_reference(motions: list[TraceMotion], event_index: int, comp_mode: int) -> TraceMotion | None:
    for motion in motions[event_index + 1 :]:
        if motion.compensation_mode != comp_mode:
            break
        if motion.move in (1, 2, 3) and _project_motion(motion) is not None:
            return motion
    return None


def _solve_entry(
    event_motion: TraceMotion,
    reference_motion: TraceMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> TraceMotion | None:
    reference_offset = _solve_standalone(reference_motion, comp_mode, tool_radius, geometry_tolerance)
    if reference_offset is None:
        return None

    projected_event = _project_motion(event_motion) if event_motion.move in (1, 2, 3) else None
    if projected_event is not None:
        solved = _retarget_end(projected_event, reference_offset.start)
        if solved.is_arc:
            progress = _get_progress(solved, solved.end, geometry_tolerance)
            if progress is None:
                return None
        return _projected_to_motion(
            solved,
            comp_mode=comp_mode,
            source_kind="cutter_compensation_entry",
        )

    x, y, z = _unproject(reference_offset.plane, reference_offset.start, reference_offset.start_w)
    return replace(
        event_motion,
        end_x=x,
        end_y=y,
        end_z=z,
        compensation_mode=comp_mode,
        compensation_applied=True,
        compensation_status="APPLIED",
        source_kind="cutter_compensation_entry",
    )


def _solve_exit(exit_motion: TraceMotion, previous_compensated: TraceMotion) -> TraceMotion:
    projected_exit = _project_motion(exit_motion) if exit_motion.move in (1, 2, 3) else None
    projected_previous = _project_motion(previous_compensated)
    if projected_exit is not None and projected_previous is not None:
        retargeted = _retarget_start(projected_exit, projected_previous.end, projected_previous.end_w)
        if retargeted.is_arc and _get_progress(retargeted, retargeted.start, _GEOMETRY_TOLERANCE) is None:
            return replace(
                exit_motion,
                start_x=previous_compensated.end_x,
                start_y=previous_compensated.end_y,
                start_z=previous_compensated.end_z,
                source_kind="cutter_compensation_exit",
            )
        solved = _projected_to_motion(
            retargeted,
            comp_mode=40,
            source_kind="cutter_compensation_exit",
        )
        return replace(solved, compensation_applied=False, compensation_status="NOT_APPLIED")
    return replace(
        exit_motion,
        start_x=previous_compensated.end_x,
        start_y=previous_compensated.end_y,
        start_z=previous_compensated.end_z,
        source_kind="cutter_compensation_exit",
    )


def _mark_unverified(motion: TraceMotion) -> TraceMotion:
    return replace(motion, compensation_applied=False, compensation_status="UNVERIFIED")


def _normalize_comp_mode(mode: int) -> int:
    return mode if mode in (41, 42) else 0
