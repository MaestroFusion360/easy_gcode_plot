"""Milling block motion dispatch over primitive emission and cycle outcomes."""

from ..machine.cycles import CycleContext, apply_cycle_outcome
from ..machine.home import reference_return
from ..resources import checkpoint
from ..types import TraceMotion
from .cycles import execute_milling_cycle
from .emitter import (
    _continuous_c_changed,
    _display_machine_position,
    _emit_simple_modal_motion,
    _machine,
    _machine_coordinate_motion,
    _motion,
    _raw_machine_position,
    _reference_machine_position,
    _reference_orientation,
    _set_raw_machine_position,
    _tcp_rotary_changed,
    _validate_reference_path,
    _wcs_offset,
    _xyz,
)
from .kinematics import effective_orientation
from .reference import append_reference_event


def _append_cycle_events(events, outcome):
    if events is not None:
        events.extend(outcome.events)


def _emit_milling_motions(
    block, state, words, gcodes, motions, home, wcs_offsets, *, rotary_start_angles=None, events=None, call_depth=0
):
    if _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets, rotary_start_angles):
        return ()

    action_g = None
    for g in gcodes:
        if g in (0, 1, 2, 3, 28, 53, 73, 74, 76, 80, 81, 82, 83, 84, 85, 86, 87, 89):
            action_g = g
    if action_g is not None and action_g not in (73, 74, 76, 80, 81, 82, 83, 84, 85, 86, 87, 89):
        # An explicit motion/reference command ends
        # a modal drilling cycle even without a separate G80 block.
        state.cycle = 80

    for g in gcodes:
        if g in (0, 1, 2, 3):
            state.move = g

    cycle_geometry_blocked = any(g in gcodes for g in (4, 10, 28, 50, 51, 52, 53, 53.1, 68, 68.2, 69))
    cycle_outcome = execute_milling_cycle(
        CycleContext(
            block=block,
            words=words,
            codes=tuple(gcodes),
            machine_state=state,
            modal_cycle_state=state,
            coordinate_context=wcs_offsets,
        ),
        emit_geometry=not cycle_geometry_blocked,
    )
    apply_cycle_outcome(state, cycle_outcome)
    _append_cycle_events(events, cycle_outcome)
    if cycle_outcome.handled:
        motions.extend(cycle_outcome.motions)
        return cycle_outcome.signals

    if 4 in gcodes or any(g in gcodes for g in (10, 50, 51, 52, 53.1, 68, 68.2, 69)):
        pass
    elif 53 in gcodes:
        m = _machine_coordinate_motion(
            block, state, words, home=home, wcs_offsets=wcs_offsets, events=events, call_depth=call_depth
        )
        if m:
            checkpoint("generated_motions")
            motions.append(m)
    elif 28 in gcodes:
        mid = _xyz(words, state)
        start_machine = _raw_machine_position(state, wcs_offsets)
        intermediate_machine = _reference_machine_position(_machine(mid, state, wcs_offsets), state, wcs_offsets)
        path = reference_return(
            start_machine,
            intermediate_machine,
            home,
            tuple(axis in words for axis in ("X", "Y", "Z")),
        )
        _validate_reference_path(state, path.segments, words, wcs_offsets)
        append_reference_event(
            events,
            block,
            state,
            words,
            home,
            start_machine,
            path.target,
            path.segments,
            code="G28",
            intermediate=tuple(intermediate_machine),
            orientation=_reference_orientation(state),
            offset=_wcs_offset(wcs_offsets, state.active_wcs),
            call_depth=call_depth,
        )
        for machine_start, machine_end in path.segments:
            segment_start = _display_machine_position(machine_start, state, wcs_offsets)
            segment_end = _display_machine_position(machine_end, state, wcs_offsets)
            checkpoint("generated_motions")
            motions.append(
                TraceMotion(
                    0,
                    segment_start[0],
                    segment_start[2],
                    segment_end[0],
                    segment_end[2],
                    start_y=segment_start[1],
                    end_y=segment_end[1],
                    plane=state.plane,
                    source_block=block.index,
                    source_nlabel=block.nlabel,
                    source_raw=block.raw,
                    source_kind="g28",
                    orientation=_reference_orientation(state),
                    orientation_offset=tuple(_wcs_offset(wcs_offsets, state.active_wcs)),
                    start_tool_orientation=(
                        effective_orientation(state.kinematics, state.rotary_angles) if state.kinematics else None
                    ),
                    tool=state.active_tool,
                )
            )
        _set_raw_machine_position(state, path.target, wcs_offsets)
    elif state.cycle == 80 and (
        any(k in words for k in ("X", "Y", "Z"))
        or any(g in (0, 1, 2, 3) for g in gcodes)
        or _continuous_c_changed(state, words, rotary_start_angles)
        or _tcp_rotary_changed(state, words, rotary_start_angles)
    ):
        m = _motion(block, state, words, wcs_offsets=wcs_offsets, rotary_start_angles=rotary_start_angles)
        if m:
            checkpoint("generated_motions")
            motions.append(m)
    return ()
