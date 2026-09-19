"""Milling drilling-cycle (G81-G86) expansion."""

from __future__ import annotations

from ..api.resources import checkpoint, require_progress
from ..api.types import TraceMotion
from .state import MillState, _machine, _xyz


def _peck_drill(state: MillState, x: float, y: float, r: float, add, *, high_speed: bool) -> None:
    direction = 1.0 if state.cycle_z > r else -1.0
    current = r
    feed_start = r
    retract_clearance = 1.0

    while (state.cycle_z - current) * direction > 1e-9:
        nxt = current + direction * state.cycle_q
        if (state.cycle_z - nxt) * direction < 0:
            nxt = state.cycle_z
        require_progress(current, nxt)
        checkpoint("cycle_iterations")
        plunge_start = feed_start if high_speed else r
        add(1, (x, y, plunge_start), (x, y, nxt), state.cycle_feed or state.feed)
        if abs(nxt - state.cycle_z) > 1e-9:
            retract = r
            if high_speed:
                # Real controls use a machine-parameter retract for G73. The
                # kernel cannot know it, so approximate with a fixed 1 mm
                # clearance in the kernel's internal metric coordinates.
                retract = nxt - direction * retract_clearance
                if (retract - r) * direction < 0.0:
                    retract = r
                feed_start = retract
            add(0, (x, y, nxt), (x, y, retract))
        current = nxt


def _drill(block, state: MillState, words, *, wcs_offsets) -> list[TraceMotion]:
    # Modal XY location + Z/R/Q parameters.  Logical cycle expansion is kept as
    # a small set of machine motions; no render sampling occurs here.
    out: list[TraceMotion] = []
    x, y, _ = _xyz(words, state)
    if "Z" in words:
        state.cycle_z = words["Z"] * state.unit_scale if state.absolute else state.z + words["Z"] * state.unit_scale
    if "R" in words:
        state.cycle_r = words["R"] * state.unit_scale if state.absolute else state.z + words["R"] * state.unit_scale
    if "Q" in words:
        state.cycle_q = abs(words["Q"] * state.unit_scale)
    if "F" in words:
        state.cycle_feed = words["F"] * state.unit_scale
    if state.cycle_z is None:
        return out
    r = state.cycle_r if state.cycle_r is not None else state.z
    start = (state.x, state.y, state.z)

    def add(kind: int, a, b, feed=None):
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
                feed=feed,
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
    if state.cycle in (73, 83) and state.cycle_q and state.cycle_q > 1e-12:
        _peck_drill(state, x, y, r, add, high_speed=state.cycle == 73)
    else:
        add(1, (x, y, r), (x, y, state.cycle_z), state.cycle_feed or state.feed)
    return_z = start[2] if state.return_initial else r
    return_move = 1 if state.cycle == 85 else 0
    add(return_move, (x, y, state.cycle_z), (x, y, return_z), state.cycle_feed or state.feed)
    state.x, state.y, state.z = x, y, return_z
    return out
