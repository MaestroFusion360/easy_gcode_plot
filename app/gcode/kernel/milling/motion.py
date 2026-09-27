"""Milling motion construction from evaluated words and state."""

from __future__ import annotations

from ..api.resources import checkpoint
from ..api.types import TraceMotion
from ..runtime.cycles import CycleContext, apply_cycle_outcome
from ..runtime.home import reference_return
from .cycles import execute_milling_cycle
from .kinematics import effective_orientation, point_orientation, transform_point
from .state import MillState, _coordinate_transform, _machine, _orient_point, _orient_vector, _wcs_offset, _xyz


def _raw_machine_position(state: MillState, wcs_offsets) -> tuple[float, float, float]:
    """Current XYZ before indexed display orientation, in machine coordinates."""
    work = _coordinate_transform(state).apply((state.x, state.y, state.z))
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    return tuple(work[i] + offset[i] for i in range(3))


def _display_machine_position(position, state: MillState, wcs_offsets) -> tuple[float, float, float]:
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    work = tuple(position[i] - offset[i] for i in range(3))
    oriented = _orient_point(work, state)
    return tuple(oriented[i] + offset[i] for i in range(3))


def _set_raw_machine_position(state: MillState, position, wcs_offsets) -> None:
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    work = tuple(position[i] - offset[i] for i in range(3))
    state.x, state.y, state.z = _coordinate_transform(state).inverse(work)


def _continuous_c_changed(state: MillState, words, rotary_start_angles) -> bool:
    return (
        state.kinematics is not None
        and state.kinematics.id == "4ax_table_c"
        and "C" in words
        and rotary_start_angles is not None
        and rotary_start_angles["C"] != state.rotary_angles["C"]
    )


def _motion(
    block,
    state: MillState,
    words,
    *,
    wcs_offsets,
    source_kind="motion",
    rotary_start_angles=None,
) -> TraceMotion | None:
    end = _xyz(words, state)
    continuous_c = _continuous_c_changed(state, words, rotary_start_angles)
    if continuous_c:
        work = _coordinate_transform(state).apply((state.x, state.y, state.z))
        offset = _wcs_offset(wcs_offsets, state.active_wcs)
        rotated = transform_point(point_orientation(state.kinematics, rotary_start_angles), work)
        start_m = tuple(rotated[index] + offset[index] for index in range(3))
    else:
        start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    end_m = _machine(end, state, wcs_offsets)
    arc_vector = (0.0, 0.0, 0.0)
    plane_scales = (1.0, 1.0)
    if state.move in (2, 3):
        transform = _coordinate_transform(state)
        arc_vector = _orient_vector(
            transform.apply_vector(tuple(words.get(axis, 0.0) * state.unit_scale for axis in ("I", "J", "K"))), state
        )
        plane_scales = transform.plane_scale_factors(state.plane)
        if abs(plane_scales[0] - plane_scales[1]) > 1e-12:
            raise ValueError("G51 axis-specific scaling of arcs requires spiral interpolation, which is not modeled")
    state.x, state.y, state.z = end
    has_arc_definition = state.move in (2, 3) and any(key in words for key in ("I", "J", "K", "R"))
    if start_m == end_m and not has_arc_definition:
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end_m[0],
        end_y=end_m[1],
        end_z=end_m[2],
        radius=(words.get("R") * state.unit_scale * abs(plane_scales[0]) if "R" in words else None),
        feed=(None if state.move == 0 else state.feed),
        i=(
            arc_vector[0]
            if (state.kinematics is not None and any(a in words for a in ("I", "J", "K"))) or "I" in words
            else None
        ),
        j=(
            arc_vector[1]
            if (state.kinematics is not None and any(a in words for a in ("I", "J", "K"))) or "J" in words
            else None
        ),
        k=(
            arc_vector[2]
            if (state.kinematics is not None and any(a in words for a in ("I", "J", "K"))) or "K" in words
            else None
        ),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind=source_kind,
        plane=state.plane,
        cycle_generated=source_kind == "cycle",
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
        compensation_status="UNVERIFIED" if state.cutter_comp in (41, 42) else "NOT_APPLIED",
        orientation=(
            point_orientation(state.kinematics, state.rotary_angles) if state.kinematics and not continuous_c else None
        ),
        orientation_offset=_wcs_offset(wcs_offsets, state.active_wcs),
        tool_orientation=(effective_orientation(state.kinematics, state.rotary_angles) if state.kinematics else None),
    )


def _machine_coordinate_motion(block, state: MillState, words, *, wcs_offsets) -> TraceMotion | None:
    """Execute a non-modal G53 move directly in machine coordinates."""
    start_raw = _raw_machine_position(state, wcs_offsets)
    end_raw = list(start_raw)
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        value = words[letter] * state.unit_scale
        end_raw[index] = value if state.absolute else start_raw[index] + value

    start_m = _display_machine_position(start_raw, state, wcs_offsets)
    end = _display_machine_position(end_raw, state, wcs_offsets)
    _set_raw_machine_position(state, end_raw, wcs_offsets)
    if start_raw == tuple(end_raw):
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        feed=(None if state.move == 0 else state.feed),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind="g53",
        plane=state.plane,
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
    )


def _g53_home_axes(
    state: MillState,
    words,
    home: tuple[float, float, float],
    *,
    wcs_offsets,
) -> tuple[str, ...]:
    """Return addressed G53 axes that deterministically target configured home."""
    start_m = _raw_machine_position(state, wcs_offsets)
    axes: list[str] = []
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        if state.absolute:
            target = words[letter] * state.unit_scale
        else:
            target = start_m[index] + words[letter] * state.unit_scale
        if abs(target - home[index]) > 1e-9:
            return ()
        axes.append(letter)
    return tuple(axes)


def _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets, rotary_start_angles):
    if not gcodes and state.cycle == 80:
        if any(axis in words for axis in ("X", "Y", "Z")) or _continuous_c_changed(state, words, rotary_start_angles):
            m = _motion(block, state, words, wcs_offsets=wcs_offsets, rotary_start_angles=rotary_start_angles)
            if m:
                checkpoint("generated_motions")
                motions.append(m)
        return True
    return False


def _emit_milling_motions(block, state, words, gcodes, motions, home, wcs_offsets, *, rotary_start_angles=None):
    if _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets, rotary_start_angles):
        return ()

    action_g = None
    for g in gcodes:
        if g in (0, 1, 2, 3, 28, 53, 73, 80, 81, 82, 83, 84, 85, 86):
            action_g = g
    if action_g is not None and action_g not in (73, 80, 81, 82, 83, 84, 85, 86):
        # Match CncKernelCli: an explicit motion/reference command ends
        # a modal drilling cycle even without a separate G80 block.
        state.cycle = 80

    for g in gcodes:
        if g in (0, 1, 2, 3):
            state.move = g

    cycle_geometry_blocked = any(g in gcodes for g in (4, 10, 28, 50, 51, 52, 53, 68, 69))
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
    if cycle_outcome.handled:
        motions.extend(cycle_outcome.motions)
        return cycle_outcome.signals

    if 4 in gcodes or any(g in gcodes for g in (10, 50, 51, 52, 68, 69)):
        pass
    elif 53 in gcodes:
        m = _machine_coordinate_motion(block, state, words, wcs_offsets=wcs_offsets)
        if m:
            checkpoint("generated_motions")
            motions.append(m)
    elif 28 in gcodes:
        mid = _xyz(words, state)
        start_machine = _raw_machine_position(state, wcs_offsets)
        offset = _wcs_offset(wcs_offsets, state.active_wcs)
        mid_work = _coordinate_transform(state).apply(mid)
        intermediate_machine = tuple(mid_work[i] + offset[i] for i in range(3))
        path = reference_return(
            start_machine,
            intermediate_machine,
            home,
            tuple(axis in words for axis in ("X", "Y", "Z")),
        )
        for segment_start, segment_end in path.segments:
            display_start = _display_machine_position(segment_start, state, wcs_offsets)
            display_end = _display_machine_position(segment_end, state, wcs_offsets)
            checkpoint("generated_motions")
            motions.append(
                TraceMotion(
                    0,
                    display_start[0],
                    display_start[2],
                    display_end[0],
                    display_end[2],
                    start_y=display_start[1],
                    end_y=display_end[1],
                    plane=state.plane,
                    source_block=block.index,
                    source_nlabel=block.nlabel,
                    source_raw=block.raw,
                    source_kind="g28",
                    tool=state.active_tool,
                )
            )
        _set_raw_machine_position(state, path.target, wcs_offsets)
    elif state.cycle == 80 and (
        any(k in words for k in ("X", "Y", "Z"))
        or any(g in (0, 1, 2, 3) for g in gcodes)
        or _continuous_c_changed(state, words, rotary_start_angles)
    ):
        m = _motion(block, state, words, wcs_offsets=wcs_offsets, rotary_start_angles=rotary_start_angles)
        if m:
            checkpoint("generated_motions")
            motions.append(m)
    return ()
