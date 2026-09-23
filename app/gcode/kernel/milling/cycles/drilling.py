"""Milling drilling-cycle expansion using shared axial-cycle mechanics."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ...api.resources import checkpoint
from ...api.types import MachineSignal, TraceMotion
from ...runtime.cycles import CycleContext, CycleOutcome, apply_cycle_outcome
from ...runtime.drilling import axial_cycle_moves
from ..state import MillState, _machine, _xyz


@dataclass(frozen=True)
class _DrillBehavior:
    peck: bool = False
    high_speed_peck: bool = False
    feed_return: bool = False


@dataclass(frozen=True)
class _ResolvedDrillingCycle:
    x: float
    y: float
    retract_z: float
    target_z: float
    return_z: float
    feed: float
    step: float | None
    behavior: _DrillBehavior


# This table describes the geometry that the kernel already models. It does
# not claim controller-side dwell/spindle semantics that are not represented
# in the backplot yet.
_DRILL_BEHAVIOR = {
    73: _DrillBehavior(peck=True, high_speed_peck=True),
    81: _DrillBehavior(),
    82: _DrillBehavior(),
    83: _DrillBehavior(peck=True),
    # Tapping remains synchronized with the spindle on withdrawal, so its
    # return is cutting/feed motion rather than a rapid retract.
    84: _DrillBehavior(feed_return=True),
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
    if "P" in words:
        if words["P"] < 0:
            raise ValueError("Milling canned-cycle P dwell must not be negative")
        state.cycle_p = words["P"] / 1000.0


def _drilling_cycle_signals(block, state: MillState, words) -> tuple[MachineSignal, ...]:
    """Describe controller actions associated with one emitted canned cycle."""
    if state.cycle not in _DRILL_BEHAVIOR or not any(key in words for key in ("X", "Y", "Z", "R")):
        return ()
    if state.cycle == 82 and state.cycle_p > 0.0:
        return (MachineSignal("dwell", block.index, "G82", state.cycle_p),)
    if state.cycle == 84:
        return (
            MachineSignal("spindle_sync", block.index, "G84"),
            MachineSignal("spindle_reverse", block.index, "G84"),
        )
    if state.cycle == 86:
        return (MachineSignal("spindle_stop", block.index, "G86"),)
    return ()


def _cycle_modal_updates(state: MillState, gcodes) -> tuple[tuple[str, object], ...]:
    cycle = state.cycle
    initial_z = state.cycle_initial_z
    for gcode in gcodes:
        if gcode not in (73, 80, 81, 82, 83, 84, 85, 86):
            continue
        if gcode != 80 and cycle == 80:
            initial_z = state.z
        cycle = int(gcode)
    return (("cycle", cycle), ("cycle_initial_z", initial_z))


def _cycle_parameter_updates(state: MillState) -> tuple[tuple[str, object], ...]:
    return tuple(
        (attribute, getattr(state, attribute))
        for attribute in (
            "cycle_z",
            "cycle_r",
            "cycle_q",
            "cycle_feed",
            "cycle_p",
            "polar_radius",
            "polar_angle",
        )
    )


def _resolve_drilling_cycle(state: MillState, words) -> _ResolvedDrillingCycle | None:
    """Resolve modal cycle parameters and the programmed hole position."""
    x, y, _ = _xyz(words, state)
    if state.cycle_z is None:
        return None
    retract_z = state.cycle_r if state.cycle_r is not None else state.z
    feed = state.cycle_feed or state.feed
    behavior = _DRILL_BEHAVIOR[state.cycle]
    return_z = state.z if state.return_initial else retract_z
    return _ResolvedDrillingCycle(
        x=x,
        y=y,
        retract_z=retract_z,
        target_z=state.cycle_z,
        return_z=return_z,
        feed=feed,
        step=state.cycle_q if behavior.peck and state.cycle_q and state.cycle_q > 1e-12 else None,
        behavior=behavior,
    )


def _expand_drilling_cycle(
    context: CycleContext,
    state: MillState,
    resolved: _ResolvedDrillingCycle,
) -> tuple[TraceMotion, ...]:
    """Build drilling geometry without committing the machine position."""
    block = context.block
    wcs_offsets = context.coordinate_context
    out: list[TraceMotion] = []

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

    start = (state.x, state.y, state.z)
    x, y = resolved.x, resolved.y
    add(0, start, (x, y, start[2]))
    add(0, (x, y, start[2]), (x, y, resolved.retract_z))
    for segment in axial_cycle_moves(
        resolved.retract_z,
        resolved.target_z,
        step=resolved.step,
        retract_distance=state.g73_retract_distance,
        full_retract=not resolved.behavior.high_speed_peck,
        retract_after_final=False,
        return_to=resolved.return_z,
        return_feed=resolved.behavior.feed_return,
        tolerance=1e-9,
    ):
        add(
            segment.move,
            (x, y, segment.start),
            (x, y, segment.end),
            None if segment.move == 0 else resolved.feed,
        )

    return tuple(out)


def execute_milling_cycle(context: CycleContext, *, emit_geometry: bool = True) -> CycleOutcome:
    """Resolve one milling canned-cycle block and return all of its effects."""
    state = context.machine_state
    if not isinstance(state, MillState):
        raise TypeError("Milling cycle context requires MillState")

    cycle_codes = tuple(g for g in context.codes if g in (73, 80, 81, 82, 83, 84, 85, 86))
    has_position = any(key in context.words for key in ("X", "Y", "Z", "R"))
    modal_updates = _cycle_modal_updates(state, cycle_codes)
    trial_state = replace(state)
    apply_cycle_outcome(trial_state, CycleOutcome(modal_updates=modal_updates))

    explicit_cycle = bool(cycle_codes)
    should_expand = emit_geometry and trial_state.cycle != 80 and has_position
    handled = emit_geometry and (explicit_cycle or should_expand)
    if not should_expand:
        return CycleOutcome(handled=handled, modal_updates=modal_updates)

    _update_cycle_parameters(trial_state, context.words)
    resolved = _resolve_drilling_cycle(trial_state, context.words)
    if resolved is None:
        return CycleOutcome(
            handled=True,
            modal_updates=modal_updates + _cycle_parameter_updates(trial_state),
        )
    motions = _expand_drilling_cycle(context, trial_state, resolved)
    return CycleOutcome(
        handled=True,
        motions=motions,
        signals=_drilling_cycle_signals(context.block, trial_state, context.words),
        modal_updates=modal_updates + _cycle_parameter_updates(trial_state),
        position_update=(("x", resolved.x), ("y", resolved.y), ("z", resolved.return_z)),
    )
