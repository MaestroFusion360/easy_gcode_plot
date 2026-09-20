"""Mutable milling state plus machine-coordinate helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..api.types import ExecutionStep
from ..geometry.coordinates import rebase_work_position
from ..geometry.transform import CoordinateTransform, TransformState
from ..runtime.execution import apply_unit_mode
from ..runtime.state import MachineRuntimeState


@dataclass
class MillState(MachineRuntimeState):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    absolute: bool = True
    plane: int = 17
    move: int = 0
    transform: TransformState = field(default_factory=TransformState)
    cycle: int = 80
    cycle_z: float | None = None
    cycle_r: float | None = None
    cycle_q: float | None = None
    cycle_feed: float = 0.0
    return_initial: bool = False
    cycle_initial_z: float | None = None
    cutter_comp: int = 40
    tool_length_comp: bool = False
    tool_length_h: int | None = None
    selected_tool: str | None = None
    selected_tool_block: int | None = None
    unknown_axes: set[str] = field(default_factory=set)


def _xyz(words, state: MillState) -> tuple[float, float, float]:
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
        return point[0] + ox, point[1] + oy, point[2] + oz
    work = _coordinate_transform(state).apply(point)
    ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
    return work[0] + ox, work[1] + oy, work[2] + oz


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
    )


def _apply_coordinate_modal_state(state: MillState, g, words, *, wcs_offsets) -> bool:
    if g == 52:
        _set_g52_shift(state, words)
    elif g == 50:
        _cancel_g51_scaling(state)
    elif g == 51:
        _set_g51_scaling(state, words)
    elif g == 68:
        _set_g68_rotation(state, words)
    elif g == 69:
        _cancel_g68_rotation(state)
    elif isinstance(g, int) and 54 <= g <= 59:
        transform = _coordinate_transform(state)
        work_position = transform.apply((state.x, state.y, state.z))
        rebased = rebase_work_position(
            work_position,
            _wcs_offset(wcs_offsets, state.active_wcs),
            _wcs_offset(wcs_offsets, g),
        )
        state.active_wcs = g
        state.x, state.y, state.z = transform.inverse(rebased)
    else:
        return False
    return True


def _apply_pre_flow_modal_state(state: MillState, gcodes, all_m, words, *, wcs_offsets) -> None:
    """Apply state-only modal words before an M98/M99 control transfer."""
    apply_unit_mode(state, gcodes)
    for g in gcodes:
        if g in (20, 21):
            continue
        if g in (17, 18, 19):
            state.plane = g
        elif g == 90:
            state.absolute = True
        elif g == 91:
            state.absolute = False
        elif _apply_coordinate_modal_state(state, g, words, wcs_offsets=wcs_offsets):
            pass
        elif g in (40, 41, 42):
            state.cutter_comp = g
        elif g == 43:
            state.tool_length_comp = True
            if "H" in words:
                h_value = words["H"]
                state.tool_length_h = int(h_value) if float(h_value).is_integer() else None
        elif g == 49:
            state.tool_length_comp = False
            state.tool_length_h = None
        elif g == 98:
            state.return_initial = True
        elif g == 99:
            state.return_initial = False

    if 94 in gcodes:
        state.feed_mode = "per_minute"
    if 95 in gcodes:
        state.feed_mode = "per_revolution"
    if "S" in words:
        state.spindle_rpm = words["S"]
    if 5 in all_m:
        state.spindle_rpm = None
    if "F" in words:
        state.feed = words["F"] * state.unit_scale
