"""State machine for Fanuc-style milling cutter compensation."""

from __future__ import annotations

from dataclasses import replace

from ...api.types import TraceMotion
from ..common import EPS
from .entry_exit import (
    _find_entry_reference,
    _mark_unverified,
    _normalize_comp_mode,
    _solve_entry,
    _solve_exit,
)
from .joins import _join_steady_motion
from .offset import _solve_standalone, _tool_radius
from .projection import _project_motion, _projected_to_motion, _ProjectedMotion, _retarget_start

_GEOMETRY_TOLERANCE = 0.01


def _carry_out_of_plane_motion(current: TraceMotion, previous: TraceMotion) -> TraceMotion | None:
    if current.move != 1 or _project_motion(current) is not None:
        return None
    updates = {
        "compensation_applied": True,
        "compensation_status": "APPLIED",
        "source_kind": "cutter_compensation",
    }
    if current.plane == 18:
        updates.update(start_x=previous.end_x, end_x=previous.end_x, start_z=previous.end_z, end_z=previous.end_z)
    elif current.plane == 19:
        updates.update(start_y=previous.end_y, end_y=previous.end_y, start_z=previous.end_z, end_z=previous.end_z)
    else:
        updates.update(start_x=previous.end_x, end_x=previous.end_x, start_y=previous.end_y, end_y=previous.end_y)
    return replace(current, **updates)


def _fallback_active_motion(current: TraceMotion, previous: TraceMotion | None) -> tuple[TraceMotion, bool]:
    carried = _carry_out_of_plane_motion(current, previous) if previous is not None else None
    return (carried, True) if carried is not None else (_mark_unverified(current), False)


def _apply_milling_cutter_compensation(
    motions: list[TraceMotion],
    tools: dict[str, dict[str, object]],
    motion_owners: list[int],
    *,
    geometry_tolerance: float = _GEOMETRY_TOLERANCE,
) -> tuple[list[TraceMotion], list[int]]:
    """Apply Fanuc-style cutter compensation using configured milling tool diameters.

    G41/G42 is treated as a state machine.  The command block is an entry
    transition, following line/arc/helix motions are offset and stitched, and
    the first G40 motion is retargeted from the final compensated endpoint.
    """
    if len(motion_owners) != len(motions):
        raise ValueError("Each compensated milling motion must have one owner")
    if not motions:
        return motions, []

    output: list[TraceMotion] = []
    output_owners: list[int] = []
    previous_steady: _ProjectedMotion | None = None
    previous_steady_output_index = -1
    align_next_active_to_entry = False
    active_tool_radius = 0.0
    active_comp_mode = 0

    for index, current in enumerate(motions):
        current_owner = motion_owners[index]
        previous_comp = _normalize_comp_mode(motions[index - 1].compensation_mode) if index > 0 else 0
        current_comp = _normalize_comp_mode(current.compensation_mode)
        current_active = current_comp != 0
        entry_event = current_active and previous_comp != current_comp
        exit_event = current_comp == 0 and previous_comp != 0

        if entry_event:
            active_comp_mode = current_comp
            active_tool_radius = _tool_radius(tools.get(current.tool or "")) or 0.0
            previous_steady = None
            previous_steady_output_index = -1
            align_next_active_to_entry = False
            if active_tool_radius <= EPS:
                output.append(_mark_unverified(current))
                output_owners.append(current_owner)
                continue

            reference = _find_entry_reference(motions, index, active_comp_mode) or current
            solved_entry = _solve_entry(
                current,
                reference,
                active_comp_mode,
                active_tool_radius,
                geometry_tolerance,
            )
            if solved_entry is None:
                active_tool_radius = 0.0
                output.append(_mark_unverified(current))
                output_owners.append(current_owner)
                continue

            output.append(solved_entry)
            output_owners.append(current_owner)
            align_next_active_to_entry = True
            continue

        if exit_event:
            output.append(_solve_exit(current, output[-1]) if output else current)
            output_owners.append(current_owner)
            previous_steady = None
            previous_steady_output_index = -1
            align_next_active_to_entry = False
            active_tool_radius = 0.0
            active_comp_mode = 0
            continue

        if not current_active:
            output.append(current)
            output_owners.append(current_owner)
            continue

        if active_tool_radius <= EPS or current_comp != active_comp_mode:
            output.append(_mark_unverified(current))
            output_owners.append(current_owner)
            previous_steady = None
            previous_steady_output_index = -1
            continue

        solved_steady = _solve_standalone(current, current_comp, active_tool_radius, geometry_tolerance)
        if solved_steady is None:
            fallback, align_next_active_to_entry = _fallback_active_motion(current, output[-1] if output else None)
            output.append(fallback)
            output_owners.append(current_owner)
            previous_steady = None
            continue

        if align_next_active_to_entry and output:
            previous_output = _project_motion(output[-1])
            if previous_output is not None:
                solved_steady = _retarget_start(solved_steady, previous_output.end, previous_output.end_w)
            align_next_active_to_entry = False
        elif previous_steady is not None:
            joined = _join_steady_motion(
                previous_steady,
                solved_steady,
                current_comp,
                active_tool_radius,
                geometry_tolerance,
            )
            if joined is not None:
                stitched_previous, solved_steady, transition = joined
                output[previous_steady_output_index] = _projected_to_motion(
                    stitched_previous,
                    comp_mode=current_comp,
                )
                if transition is not None:
                    output.append(transition)
                    output_owners.append(output_owners[previous_steady_output_index])

        solved_trace = _projected_to_motion(solved_steady, comp_mode=current_comp)
        output.append(solved_trace)
        output_owners.append(current_owner)
        previous_steady = solved_steady
        previous_steady_output_index = len(output) - 1

    return output, output_owners


def apply_milling_cutter_compensation(
    motions: list[TraceMotion],
    tools: dict[str, dict[str, object]],
    *,
    geometry_tolerance: float = _GEOMETRY_TOLERANCE,
) -> list[TraceMotion]:
    """Apply compensation while preserving the established list-only API."""
    output, _owners = _apply_milling_cutter_compensation(
        motions,
        tools,
        list(range(len(motions))),
        geometry_tolerance=geometry_tolerance,
    )
    return output


def apply_milling_cutter_compensation_with_owners(
    motions: list[TraceMotion],
    tools: dict[str, dict[str, object]],
    motion_owners: list[int],
    *,
    geometry_tolerance: float = _GEOMETRY_TOLERANCE,
) -> tuple[list[TraceMotion], list[int]]:
    """Apply compensation and propagate execution-step ownership to inserted motions."""
    return _apply_milling_cutter_compensation(
        motions,
        tools,
        motion_owners,
        geometry_tolerance=geometry_tolerance,
    )
