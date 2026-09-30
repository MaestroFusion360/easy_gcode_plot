"""Mutable milling state plus machine-coordinate helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..api.resources import SemanticError
from ..api.types import ExecutionStep
from ..geometry.coordinates import extended_wcs_from_gcode, programmed_wcs_id, rebase_work_position
from ..geometry.transform import CoordinateTransform, TransformState
from ..runtime.execution import apply_unit_mode
from ..runtime.state import MachineRuntimeState
from .kinematics import MachineKinematics, _transpose, point_orientation, transform_point, transform_vector
from .polar import activate_polar, cancel_polar, resolve_polar_endpoint, select_polar_plane
from .twp import TiltedWorkPlane, solve_table_orientation, supports_twp_kinematics


@dataclass
class MillState(MachineRuntimeState):
    kinematics: MachineKinematics | None = None
    rotary_angles: dict[str, float] = field(default_factory=lambda: {"A": 0.0, "B": 0.0, "C": 0.0})
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    absolute: bool = True
    plane: int = 17
    move: int = 0
    transform: TransformState = field(default_factory=TransformState)
    twp: TiltedWorkPlane = field(default_factory=TiltedWorkPlane)
    cycle: int = 80
    cycle_z: float | None = None
    cycle_r: float | None = None
    cycle_q: float | None = None
    cycle_feed: float = 0.0
    cycle_p: float = 0.0
    g73_retract_distance: float = 1.0
    return_initial: bool = False
    cycle_initial_z: float | None = None
    cutter_comp: int = 40
    tool_length_comp: bool = False
    tool_length_h: int | None = None
    tcp_control: bool = False
    rigid_tapping_ready: bool = False
    selected_tool: str | None = None
    selected_tool_block: int | None = None
    unknown_axes: set[str] = field(default_factory=set)
    polar_active: bool = False
    polar_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    polar_radius: float = 0.0
    polar_angle: float = 0.0
    polar_plane: int = 17


def _xyz(words, state: MillState) -> tuple[float, float, float]:
    if state.polar_active:
        return resolve_polar_endpoint(words, state)

    def resolve(letter: str, current: float) -> float:
        if letter not in words:
            return current
        value = words[letter] * state.unit_scale
        return value if state.absolute else current + value

    return resolve("X", state.x), resolve("Y", state.y), resolve("Z", state.z)


def _wcs_offset(wcs_offsets: dict[int, tuple[float, float, float]] | None, code: int) -> tuple[float, float, float]:
    return (wcs_offsets or {}).get(code, (0.0, 0.0, 0.0))


def _coordinate_transform(state: MillState) -> CoordinateTransform:
    return state.transform.build()


def _machine(point: tuple[float, float, float], state: MillState, wcs_offsets) -> tuple[float, float, float]:
    transform_state = state.transform
    if (
        transform_state.translation == (0.0, 0.0, 0.0)
        and not transform_state.rotation_active
        and not transform_state.scaling_active
    ):
        ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
        oriented = _orient_point(point, state)
        return oriented[0] + ox, oriented[1] + oy, oriented[2] + oz
    work = _coordinate_transform(state).apply(point)
    work = _orient_point(work, state)
    ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
    return work[0] + ox, work[1] + oy, work[2] + oz


def _orient_point(point: tuple[float, float, float], state: MillState) -> tuple[float, float, float]:
    if state.tcp_control:
        return point
    if state.twp.active:
        return state.twp.apply(point)
    if state.kinematics is None:
        return point
    return transform_point(point_orientation(state.kinematics, state.rotary_angles), point)


def _orient_vector(vector: tuple[float, float, float], state: MillState) -> tuple[float, float, float]:
    if state.tcp_control:
        return vector
    if state.twp.active:
        return state.twp.vector(vector)
    if state.kinematics is None:
        return vector
    return transform_vector(point_orientation(state.kinematics, state.rotary_angles), vector)


def _unorient_point(point: tuple[float, float, float], state: MillState) -> tuple[float, float, float]:
    if state.tcp_control:
        return point
    if state.twp.active:
        return state.twp.inverse(point)
    if state.kinematics is not None:
        orientation = point_orientation(state.kinematics, state.rotary_angles)
        point = tuple(sum(orientation[j][i] * point[j] for j in range(3)) for i in range(3))
    return point


def _cancel_tcp(state: MillState) -> None:
    """Disable TCP while keeping the current tool-center position fixed."""
    if not state.tcp_control:
        return
    point = _coordinate_transform(state).apply((state.x, state.y, state.z))
    if state.kinematics is not None:
        orientation = point_orientation(state.kinematics, state.rotary_angles)
        point = transform_vector(_transpose(orientation), point)
    state.x, state.y, state.z = _coordinate_transform(state).inverse(point)
    state.tcp_control = False


def _activate_tcp(state: MillState) -> None:
    """Enable TCP without changing the current physical machine point."""
    transform = _coordinate_transform(state)
    point = transform.apply((state.x, state.y, state.z))
    point = _orient_point(point, state)
    state.x, state.y, state.z = transform.inverse(point)
    state.tcp_control = True


def _set_twp(state: MillState, words, block_index: int) -> None:
    if state.kinematics is None or not supports_twp_kinematics(state.kinematics):
        raise SemanticError("TWP_KINEMATICS_REQUIRED", "G68.2 requires two distinct rotary axes", "unsupported")
    if state.twp.active or state.transform.rotation_active:
        raise SemanticError(
            "UNSUPPORTED_TWP_COMPOSITION", "G68.2 cannot combine with G68 or another G68.2", "unsupported"
        )
    required = ("X", "Y", "Z", "I", "J", "K")
    if any(letter not in words for letter in required):
        raise SemanticError("INVALID_G68_2_WORDS", "G68.2 requires X/Y/Z origin and I/J/K Euler angles")
    work_position = _orient_point(_coordinate_transform(state).apply((state.x, state.y, state.z)), state)
    origin = tuple(words[axis] * state.unit_scale for axis in ("X", "Y", "Z"))
    angles = tuple(float(words[axis]) for axis in ("I", "J", "K"))
    state.twp.configure(origin, angles, block_index)
    state.x, state.y, state.z = _coordinate_transform(state).inverse(state.twp.inverse(work_position))


def _cancel_twp(state: MillState) -> None:
    if not state.twp.active:
        return
    work_position = _orient_point(_coordinate_transform(state).apply((state.x, state.y, state.z)), state)
    state.twp.clear()
    state.x, state.y, state.z = _coordinate_transform(state).inverse(_unorient_point(work_position, state))


def _preserve_work_position(state: MillState, work_position: tuple[float, float, float]) -> None:
    state.x, state.y, state.z = _coordinate_transform(state).inverse(work_position)


def _set_g52_shift(state: MillState, words) -> None:
    if not any(axis in words for axis in ("X", "Y", "Z")):
        return
    work_position = _coordinate_transform(state).apply((state.x, state.y, state.z))
    shift = list(state.transform.translation)
    for index, axis in enumerate(("X", "Y", "Z")):
        if axis in words:
            shift[index] = words[axis] * state.unit_scale
    state.transform.translation = (shift[0], shift[1], shift[2])
    _preserve_work_position(state, work_position)


def _set_g68_rotation(state: MillState, words) -> None:
    work_position = _coordinate_transform(state).apply((state.x, state.y, state.z))
    local_center = [state.x, state.y, state.z]
    plane_axes = {17: ((0, "X"), (1, "Y")), 18: ((0, "X"), (2, "Z")), 19: ((1, "Y"), (2, "Z"))}
    for index, axis in plane_axes.get(state.plane, plane_axes[17]):
        if axis in words:
            value = words[axis] * state.unit_scale
            local_center[index] = value if state.absolute else local_center[index] + value
    translated_center = CoordinateTransform(translation=state.transform.translation).apply(tuple(local_center))
    state.transform.rotation_center = translated_center
    state.transform.rotation_degrees = float(words.get("R", 0.0))
    state.transform.rotation_plane = state.plane
    state.transform.rotation_active = True
    _preserve_work_position(state, work_position)


def _cancel_g68_rotation(state: MillState) -> None:
    if not state.transform.rotation_active:
        return
    work_position = _coordinate_transform(state).apply((state.x, state.y, state.z))
    state.transform.rotation_active = False
    state.transform.rotation_degrees = 0.0
    _preserve_work_position(state, work_position)


def _set_g51_scaling(state: MillState, words) -> None:
    work_position = _coordinate_transform(state).apply((state.x, state.y, state.z))
    axis_factor_words = tuple(axis for axis in ("I", "J", "K") if axis in words)
    if "P" in words and axis_factor_words:
        raise ValueError("G51 cannot combine uniform P scaling with axis-specific I/J/K scaling")
    if "P" in words:
        factor = float(words["P"]) / 1000.0
        if factor <= 0.0:
            raise ValueError("G51 P must define a positive uniform scale")
        factors = (factor, factor, factor)
    elif axis_factor_words:
        factors = tuple(float(words.get(axis, 1000.0)) / 1000.0 for axis in ("I", "J", "K"))
        if any(abs(factor) <= 1e-12 for factor in factors):
            raise ValueError("G51 I/J/K scale factors must be non-zero")
    else:
        raise ValueError("G51 requires P or I/J/K because no controller default scaling parameter is configured")

    local_center = [state.x, state.y, state.z]
    for index, axis in enumerate(("X", "Y", "Z")):
        if axis in words:
            local_center[index] = words[axis] * state.unit_scale
    state.transform.scale_center = state.transform.build_without_scaling().apply(tuple(local_center))
    state.transform.scale_factors = factors
    state.transform.scaling_active = True
    _preserve_work_position(state, work_position)


def _cancel_g51_scaling(state: MillState) -> None:
    if not state.transform.scaling_active:
        return
    work_position = _coordinate_transform(state).apply((state.x, state.y, state.z))
    state.transform.scaling_active = False
    state.transform.scale_factors = (1.0, 1.0, 1.0)
    _preserve_work_position(state, work_position)


def _program_wcs_offset(state: MillState, words, *, wcs_offsets) -> None:
    target = programmed_wcs_id(words)
    current_machine = _machine((state.x, state.y, state.z), state, wcs_offsets)
    offset = list(_wcs_offset(wcs_offsets, target))
    for index, axis in enumerate(("X", "Y", "Z")):
        if axis in words:
            value = words[axis] * state.unit_scale
            offset[index] = value if state.absolute else offset[index] + value
    wcs_offsets[target] = (offset[0], offset[1], offset[2])
    if target == state.active_wcs:
        work = (
            current_machine[0] - offset[0],
            current_machine[1] - offset[1],
            current_machine[2] - offset[2],
        )
        state.x, state.y, state.z = _coordinate_transform(state).inverse(_unorient_point(work, state))


def _execution_step(
    state: MillState,
    block,
    emitted_count: int,
    occurrence: int,
    *,
    words: tuple[tuple[str, float], ...] = (),
    signals=(),
    events=(),
    stop: bool = False,
    wcs_offsets=None,
    variables: tuple[tuple[str, float], ...] = (),
) -> ExecutionStep:
    return ExecutionStep(
        source_block=block.index,
        emitted_count=emitted_count,
        unit_scale=state.unit_scale,
        x_is_diameter=False,
        absolute=state.absolute,
        stop=stop,
        words=words,
        signals=tuple(signals),
        occurrence=occurrence,
        events=tuple(events),
        position=None if state.unknown_axes else _machine((state.x, state.y, state.z), state, wcs_offsets),
        active_wcs=state.active_wcs,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
        variables=variables,
        rotary_angles=tuple(
            (axis, state.rotary_angles[axis])
            for axis in ("A", "B", "C")
            if (state.kinematics is not None and axis in state.kinematics.addresses)
        ),
        twp_origin=state.twp.origin if state.twp.active else None,
        twp_orientation=state.twp.orientation if state.twp.active else None,
        tool_axis_control=state.twp.tool_axis_control,
    )


def _apply_coordinate_modal_state(state: MillState, g, words, *, wcs_offsets, block_index: int) -> bool:
    if g == 10:
        _program_wcs_offset(state, words, wcs_offsets=wcs_offsets)
    elif g == 52:
        _set_g52_shift(state, words)
    elif g == 50:
        _cancel_g51_scaling(state)
    elif g == 51:
        _set_g51_scaling(state, words)
    elif g == 68:
        if state.twp.active:
            raise SemanticError("UNSUPPORTED_TWP_COMPOSITION", "G68 cannot combine with G68.2", "unsupported")
        _set_g68_rotation(state, words)
    elif g == 68.2:
        _set_twp(state, words, block_index)
    elif g == 53.1:
        state.rotary_angles.update(
            solve_table_orientation(state.kinematics, state.twp.orientation, state.rotary_angles)
        )
        state.twp.tool_axis_control = True
    elif g == 69:
        _cancel_g68_rotation(state)
        _cancel_twp(state)
    elif (extended_wcs := extended_wcs_from_gcode(g, words)) is not None or (isinstance(g, int) and 54 <= g <= 59):
        selected_wcs = extended_wcs if extended_wcs is not None else g
        transform = _coordinate_transform(state)
        work_position = _orient_point(transform.apply((state.x, state.y, state.z)), state)
        rebased = rebase_work_position(
            work_position,
            _wcs_offset(wcs_offsets, state.active_wcs),
            _wcs_offset(wcs_offsets, selected_wcs),
        )
        state.active_wcs = selected_wcs
        state.x, state.y, state.z = transform.inverse(_unorient_point(rebased, state))
    else:
        return False
    return True


def _apply_polar_modal_state(state: MillState, g, *, effective_plane: int, effective_absolute: bool) -> bool:
    if g in (17, 18, 19):
        state.plane = g
        select_polar_plane(state, g)
    elif g == 15:
        cancel_polar(state)
    elif g == 16:
        activate_polar(state, plane=effective_plane, absolute=effective_absolute)
    else:
        return False
    return True


def _apply_milling_spindle_state(state: MillState, gcodes, all_m, words) -> None:
    if 94 in gcodes:
        state.feed_mode = "per_minute"
    if 95 in gcodes:
        state.feed_mode = "per_revolution"
    if 29 in all_m:
        state.rigid_tapping_ready = True
    if "S" in words and 19 not in all_m:
        state.spindle_rpm = words["S"]
    if 5 in all_m:
        state.spindle_rpm = None
    if "F" in words:
        state.feed = words["F"] * state.unit_scale


def _apply_pre_flow_modal_state(state: MillState, gcodes, all_m, words, *, wcs_offsets, block_index: int) -> None:
    """Apply state-only modal words before an M98/M99 control transfer."""
    apply_unit_mode(state, gcodes)
    effective_plane = next((g for g in reversed(gcodes) if g in (17, 18, 19)), state.plane)
    effective_absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    for g in gcodes:
        if g in (20, 21):
            continue
        if _apply_polar_modal_state(
            state,
            g,
            effective_plane=effective_plane,
            effective_absolute=effective_absolute,
        ):
            pass
        elif g == 90:
            state.absolute = True
        elif g == 91:
            state.absolute = False
        elif _apply_coordinate_modal_state(state, g, words, wcs_offsets=wcs_offsets, block_index=block_index):
            pass
        elif g in (40, 41, 42):
            state.cutter_comp = g
        elif g == 43:
            state.tool_length_comp = True
            state.tcp_control = False
            if "H" in words:
                h_value = words["H"]
                state.tool_length_h = int(h_value) if float(h_value).is_integer() else None
        elif g == 43.4:
            # FANUC Type 1 enables TCP after the activation block executes.
            state.tool_length_comp = True
            state.tcp_control = False
            if "H" in words:
                h_value = words["H"]
                state.tool_length_h = int(h_value) if float(h_value).is_integer() else None
        elif g == 49:
            state.tool_length_comp = False
            state.tool_length_h = None
            _cancel_tcp(state)
        elif g == 98:
            state.return_initial = True
        elif g == 99:
            state.return_initial = False

    _apply_milling_spindle_state(state, gcodes, all_m, words)
