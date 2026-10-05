"""Milling motion construction from evaluated words and state."""

from __future__ import annotations

from ..api.resources import checkpoint
from ..api.types import TraceMotion
from ..runtime.cycles import CycleContext, apply_cycle_outcome
from ..runtime.home import reference_return
from .cycles import execute_milling_cycle
from .kinematics import TCP_TABLE_PROFILES, effective_orientation, point_orientation, transform_point
from .state import MillState, _coordinate_transform, _machine, _orient_vector, _wcs_offset, _xyz


def _reference_orientation(state: MillState):
    """Current rotary frame around WCS for reference motion, including after G49.

    Resolve reference coordinates in that frame, then display the return using
    the same orientation as the approach instead of an implicit ABC=0 frame.
    """
    if state.kinematics is None:
        return None
    return point_orientation(state.kinematics, state.rotary_angles)


def _raw_machine_position(state: MillState, wcs_offsets) -> tuple[float, float, float]:
    position = _machine((state.x, state.y, state.z), state, wcs_offsets)
    return _reference_machine_position(position, state, wcs_offsets)


def _reference_machine_position(position, state: MillState, wcs_offsets) -> tuple[float, float, float]:
    orientation = _reference_orientation(state)
    if orientation is None:
        return tuple(position)
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    work = tuple(position[i] - offset[i] for i in range(3))
    unrotated = tuple(sum(orientation[j][i] * work[j] for j in range(3)) for i in range(3))
    return tuple(unrotated[i] + offset[i] for i in range(3))


def _display_machine_position(position, state: MillState, wcs_offsets) -> tuple[float, float, float]:
    orientation = _reference_orientation(state)
    if orientation is None:
        return tuple(position)
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    work = tuple(position[i] - offset[i] for i in range(3))
    oriented = transform_point(orientation, work)
    return tuple(oriented[i] + offset[i] for i in range(3))


def _validate_reference_retract(state: MillState, start, end, words, wcs_offsets) -> None:
    """Do not synthesize a table Z return through the WCS centre plane."""
    if state.kinematics is None or "Z" not in words or "X" in words or "Y" in words:
        return
    centre_z = _wcs_offset(wcs_offsets, state.active_wcs)[2]
    start_distance, end_distance = start[2] - centre_z, end[2] - centre_z
    if abs(start_distance) > 1e-8 and start_distance * end_distance <= 0:
        raise ValueError("Unsafe reference retract crosses the WCS centre plane; check machine home Z and WCS offset")


def _validate_reference_path(state: MillState, segments, words, wcs_offsets) -> None:
    # Validate the complete path before emitting any portion of an unsafe return.
    for start, end in segments:
        _validate_reference_retract(state, start, end, words, wcs_offsets)


def _set_raw_machine_position(state: MillState, position, wcs_offsets) -> None:
    _set_machine_position(state, _display_machine_position(position, state, wcs_offsets), wcs_offsets)


def _set_machine_position(state: MillState, position, wcs_offsets) -> None:
    """Store a physical machine-space point in the active programmed frame."""
    offset = _wcs_offset(wcs_offsets, state.active_wcs)
    work = tuple(position[i] - offset[i] for i in range(3))
    if state.twp.active:
        work = state.twp.inverse(work)
    elif not state.tcp_control and state.kinematics is not None:
        orientation = point_orientation(state.kinematics, state.rotary_angles)
        work = tuple(sum(orientation[j][i] * work[j] for j in range(3)) for i in range(3))
    state.x, state.y, state.z = _coordinate_transform(state).inverse(work)


def _continuous_c_changed(state: MillState, words, rotary_start_angles) -> bool:
    return (
        state.kinematics is not None
        and state.kinematics.id == "4ax_table_c"
        and "C" in words
        and rotary_start_angles is not None
        and rotary_start_angles["C"] != state.rotary_angles["C"]
    )


def _tcp_rotary_changed(state: MillState, words, rotary_start_angles) -> bool:
    return (
        state.tcp_control
        and state.kinematics is not None
        and state.kinematics.id in TCP_TABLE_PROFILES
        and rotary_start_angles is not None
        and any(
            axis in words and rotary_start_angles[axis] != state.rotary_angles[axis]
            for axis in state.kinematics.addresses
        )
    )


def _arc_center_vector(block, words, state):
    absolute = block.native_syntax.absolute_center if block.native_syntax is not None else ()
    return tuple(
        words.get(axis, 0.0) * state.unit_scale - (current if axis in absolute else 0.0)
        for axis, current in zip(("I", "J", "K"), (state.x, state.y, state.z), strict=True)
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
    tcp_rotary = _tcp_rotary_changed(state, words, rotary_start_angles)
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
    absolute_center_axes = (
        {17: ("I", "J"), 18: ("I", "K"), 19: ("J", "K")}[state.plane]
        if state.source_arc_type == 2 and any(axis in words for axis in ("I", "J", "K"))
        else ()
    )
    if state.move in (2, 3):
        transform = _coordinate_transform(state)
        arc_vector = _orient_vector(transform.apply_vector(_arc_center_vector(block, words, state)), state)
        plane_scales = transform.plane_scale_factors(state.plane)
        if abs(plane_scales[0] - plane_scales[1]) > 1e-12:
            raise ValueError("G51 axis-specific scaling of arcs requires spiral interpolation, which is not modeled")
    state.x, state.y, state.z = end
    if state.source_arc_type == 2:
        offset = _wcs_offset(wcs_offsets, state.active_wcs)
        arc_vector = tuple(arc_vector[i] + offset[i] for i in range(3))
    has_arc_definition = state.move in (2, 3) and any(key in words for key in ("I", "J", "K", "R"))
    if start_m == end_m and not has_arc_definition and not tcp_rotary:
        return None
    return TraceMotion(
        move=state.move,
        source_arc_type=state.source_arc_type,
        additional_turns=int(words.get("TURN", 0)),
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
            if ((state.kinematics is not None or state.twp.active) and any(a in words for a in ("I", "J", "K")))
            or "I" in words
            or "I" in absolute_center_axes
            else None
        ),
        j=(
            arc_vector[1]
            if ((state.kinematics is not None or state.twp.active) and any(a in words for a in ("I", "J", "K")))
            or "J" in words
            or "J" in absolute_center_axes
            else None
        ),
        k=(
            arc_vector[2]
            if ((state.kinematics is not None or state.twp.active) and any(a in words for a in ("I", "J", "K")))
            or "K" in words
            or "K" in absolute_center_axes
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
            state.twp.orientation
            if state.twp.active
            else point_orientation(state.kinematics, state.rotary_angles)
            if state.kinematics and not continuous_c and not state.tcp_control
            else None
        ),
        orientation_offset=tuple(
            _wcs_offset(wcs_offsets, state.active_wcs)[i] + (state.twp.origin[i] if state.twp.active else 0.0)
            for i in range(3)
        ),
        tool_orientation=(effective_orientation(state.kinematics, state.rotary_angles) if state.kinematics else None),
        start_tool_orientation=(
            effective_orientation(state.kinematics, rotary_start_angles)
            if state.kinematics is not None and rotary_start_angles is not None
            else effective_orientation(state.kinematics, state.rotary_angles)
            if state.kinematics is not None
            else None
        ),
    )


def _machine_coordinate_motion(block, state: MillState, words, *, home, wcs_offsets) -> TraceMotion | None:
    """Resolve G53/SUPA using the application's configured reference zero."""
    start_machine = _raw_machine_position(state, wcs_offsets)
    end_machine = list(start_machine)
    supa = block.native_syntax is not None and block.native_syntax.supa
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        value = words[letter] * state.unit_scale
        if supa or state.absolute:
            end_machine[index] = home[index] if value == 0.0 else value
        else:
            end_machine[index] = start_machine[index] + value

    if not supa or words.get("Z") == 0.0:
        _validate_reference_retract(state, start_machine, end_machine, words, wcs_offsets)
    _set_raw_machine_position(state, end_machine, wcs_offsets)
    if start_machine == tuple(end_machine):
        return None
    start_trace = _display_machine_position(start_machine, state, wcs_offsets)
    end_trace = _display_machine_position(end_machine, state, wcs_offsets)
    return TraceMotion(
        move=state.move,
        start_x=start_trace[0],
        start_y=start_trace[1],
        start_z=start_trace[2],
        end_x=end_trace[0],
        end_y=end_trace[1],
        end_z=end_trace[2],
        feed=(None if state.move == 0 else state.feed),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind="supa" if supa else "g53",
        start_tool_orientation=(
            effective_orientation(state.kinematics, state.rotary_angles) if state.kinematics else None
        ),
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
            if target == 0.0:
                target = home[index]
        else:
            target = start_m[index] + words[letter] * state.unit_scale
        if abs(target - home[index]) > 1e-9:
            return ()
        axes.append(letter)
    return tuple(axes)


def _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets, rotary_start_angles):
    if not gcodes and state.cycle == 80:
        if (
            any(axis in words for axis in ("X", "Y", "Z"))
            or _continuous_c_changed(state, words, rotary_start_angles)
            or _tcp_rotary_changed(state, words, rotary_start_angles)
        ):
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
    if cycle_outcome.handled:
        motions.extend(cycle_outcome.motions)
        return cycle_outcome.signals

    if 4 in gcodes or any(g in gcodes for g in (10, 50, 51, 52, 53.1, 68, 68.2, 69)):
        pass
    elif 53 in gcodes:
        m = _machine_coordinate_motion(block, state, words, home=home, wcs_offsets=wcs_offsets)
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
