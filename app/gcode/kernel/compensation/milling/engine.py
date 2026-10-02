"""State machine for Fanuc-style milling cutter compensation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

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


@dataclass
class _CompensationRun:
    motions: list[TraceMotion]
    tools: dict[str, dict[str, object]]
    geometry_tolerance: float
    output: list[TraceMotion] = field(default_factory=list)
    owners: list[int] = field(default_factory=list)
    previous_steady: _ProjectedMotion | None = None
    previous_index: int = -1
    align_entry: bool = False
    radius: float = 0.0
    mode: int = 0

    def append(self, motion, owner):
        self.output.append(motion)
        self.owners.append(owner)

    def reset_steady(self):
        self.previous_steady = None
        self.previous_index = -1

    def enter(self, index, current, owner, mode):
        self.mode = mode
        self.radius = _tool_radius(self.tools.get(current.tool or "")) or 0.0
        self.reset_steady()
        self.align_entry = False
        if self.radius <= EPS:
            self.append(_mark_unverified(current), owner)
            return
        reference = _find_entry_reference(self.motions, index, self.mode) or current
        entry = _solve_entry(current, reference, self.mode, self.radius, self.geometry_tolerance)
        if entry is None:
            self.radius = 0.0
            self.append(_mark_unverified(current), owner)
            return
        self.append(entry, owner)
        self.align_entry = True

    def exit(self, current, owner):
        self.append(_solve_exit(current, self.output[-1]) if self.output else current, owner)
        self.reset_steady()
        self.align_entry = False
        self.radius = 0.0
        self.mode = 0

    def join(self, solved, mode):
        if self.align_entry and self.output:
            previous = _project_motion(self.output[-1])
            if previous is not None:
                solved = _retarget_start(solved, previous.end, previous.end_w)
            self.align_entry = False
        elif self.previous_steady is not None:
            joined = _join_steady_motion(self.previous_steady, solved, mode, self.radius, self.geometry_tolerance)
            if joined is not None:
                previous, solved, transition = joined
                self.output[self.previous_index] = _projected_to_motion(previous, comp_mode=mode)
                if transition is not None:
                    self.append(transition, self.owners[self.previous_index])
        return solved

    def steady(self, current, owner, mode):
        if self.radius <= EPS or mode != self.mode:
            self.append(_mark_unverified(current), owner)
            self.reset_steady()
            return
        solved = _solve_standalone(current, mode, self.radius, self.geometry_tolerance)
        if solved is None:
            fallback, self.align_entry = _fallback_active_motion(current, self.output[-1] if self.output else None)
            self.append(fallback, owner)
            self.previous_steady = None
            return
        solved = self.join(solved, mode)
        self.append(_projected_to_motion(solved, comp_mode=mode), owner)
        self.previous_steady = solved
        self.previous_index = len(self.output) - 1

    def process(self, index, current, owner):
        previous = _normalize_comp_mode(self.motions[index - 1].compensation_mode) if index > 0 else 0
        mode = _normalize_comp_mode(current.compensation_mode)
        if mode != 0 and previous != mode:
            self.enter(index, current, owner, mode)
        elif mode == 0 and previous != 0:
            self.exit(current, owner)
        elif mode == 0:
            self.append(current, owner)
        else:
            self.steady(current, owner, mode)


def _apply_milling_cutter_compensation(
    motions: list[TraceMotion],
    tools: dict[str, dict[str, object]],
    motion_owners: list[int],
    *,
    geometry_tolerance: float = _GEOMETRY_TOLERANCE,
) -> tuple[list[TraceMotion], list[int]]:
    """Resolve entry, steady joins and exit with state local to one execution."""
    if len(motion_owners) != len(motions):
        raise ValueError("Each compensated milling motion must have one owner")
    if not motions:
        return motions, []
    run = _CompensationRun(motions, tools, geometry_tolerance)
    for index, (current, owner) in enumerate(zip(motions, motion_owners)):
        run.process(index, current, owner)
    return run.output, run.owners


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
