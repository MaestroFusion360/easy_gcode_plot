"""Milling drilling-cycle expansion using shared axial-cycle mechanics."""

from __future__ import annotations

from dataclasses import dataclass

from ..api.resources import checkpoint
from ..api.types import TraceMotion
from ..runtime.drilling import axial_cycle_moves
from .state import MillState, _machine, _xyz


@dataclass(frozen=True)
class _DrillBehavior:
    peck: bool = False
    high_speed_peck: bool = False
    feed_return: bool = False


# This table describes the geometry that the kernel already models. It does
# not claim controller-side dwell/spindle semantics that are not represented
# in the backplot yet.
_DRILL_BEHAVIOR = {
    73: _DrillBehavior(peck=True, high_speed_peck=True),
    81: _DrillBehavior(),
    82: _DrillBehavior(),
    83: _DrillBehavior(peck=True),
    84: _DrillBehavior(),
    85: _DrillBehavior(feed_return=True),
    86: _DrillBehavior(),
}


def _update_cycle_parameters(state: MillState, words) -> None:
    if "Z" in words:
        state.cycle_z = words["Z"] * state.unit_scale if state.absolute else state.z + words["Z"] * state.unit_scale
    if "R" in words:
        state.cycle_r = words["R"] * state.unit_scale if state.absolute else state.z + words["R"] * state.unit_scale
    if "Q" in words:
        state.cycle_q = abs(words["Q"] * state.unit_scale)
    if "F" in words:
        state.cycle_feed = words["F"] * state.unit_scale


def _drill(block, state: MillState, words, *, wcs_offsets) -> list[TraceMotion]:
    """Expand the currently active milling drill cycle without changing its semantics."""
    out: list[TraceMotion] = []
    x, y, _ = _xyz(words, state)
    _update_cycle_parameters(state, words)
    if state.cycle_z is None:
        return out

    r = state.cycle_r if state.cycle_r is not None else state.z
    start = (state.x, state.y, state.z)
    feed = state.cycle_feed or state.feed
    behavior = _DRILL_BEHAVIOR[state.cycle]

    def add(kind: int, a, b, motion_feed=None):
        am = _machine(a, state, wcs_offsets)
        bm = _machine(b, state, wcs_offsets)
        if am == bm:
            return
        checkpoint("generated_motions")
        out.append(
            TraceMotion(
                kind,
                am[0],
                am[2],
                bm[0],
                bm[2],
                feed=motion_feed,
                start_y=am[1],
                end_y=bm[1],
                plane=state.plane,
                source_block=block.index,
                source_nlabel=block.nlabel,
                source_raw=block.raw,
                source_kind="cycle",
                cycle_generated=True,
                compensation_mode=state.cutter_comp,
                compensation_applied=False,
                tool=state.active_tool,
            )
        )

    add(0, start, (x, y, start[2]))
    add(0, (x, y, start[2]), (x, y, r))
    return_z = start[2] if state.return_initial else r
    step = state.cycle_q if behavior.peck and state.cycle_q and state.cycle_q > 1e-12 else None
    for segment in axial_cycle_moves(
        r,
        state.cycle_z,
        step=step,
        retract_distance=1.0,
        full_retract=not behavior.high_speed_peck,
        retract_after_final=False,
        return_to=return_z,
        return_feed=behavior.feed_return,
        tolerance=1e-9,
    ):
        add(segment.move, (x, y, segment.start), (x, y, segment.end), None if segment.move == 0 else feed)

    state.x, state.y, state.z = x, y, return_z
    return out
