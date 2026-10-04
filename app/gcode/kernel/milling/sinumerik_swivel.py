"""CYCLE800 rigid frames: local Siemens programming manual, pp. 1140–1143.

Only axis-by-axis rotations and the fixed AC/BC table profiles are modeled.
OEM retract trajectories are outside the logical geometry model.
"""

import math
from dataclasses import dataclass

from ..api.resources import SemanticError
from ..api.types import ExecutionEvent
from .kinematics import IDENTITY, TCP_TABLE_PROFILES, _multiply, _rotation, transform_vector
from .sinumerik_parameters import parameter_value
from .state import _cancel_twp, _orient_twp_tool_axis, configure_tilted_frame
from .twp import solve_table_orientation


@dataclass(frozen=True)
class SwivelFrame:
    origin: tuple[float, float, float]
    angles: tuple[float, float, float]
    orientation: tuple
    rotary: dict | None
    retract_mode: int = 0
    reset: bool = False


def _unsupported(message):
    raise SemanticError("UNSUPPORTED_SINUMERIK_CYCLE800", message, "unsupported")


def _validate_options(values, state):
    fr, _, st, mode = values[:4]
    direction, retract, display = values[13:]
    states = (0, 110000, 200000) if values[1] == "0" else (0, 200000, 200001)
    if fr not in (0, 1, 2) or st not in states or display not in (0, 1):
        _unsupported("CYCLE800 models FR0/1/2, ST200000/200001 and DMODE0/1 only")
    if direction not in (-1, 0, 1) or retract != 0 or mode not in (57, 54, 39, 27, 30, 45):
        _unsupported("CYCLE800 requires an axis-by-axis XYZ permutation, DIR-1/0/1 and no FR_I")
    if state.tcp_control or state.native_cycle is not None or state.cycle != 80 or state.cutter_comp != 40:
        _unsupported("Cancel TCP, cycles and cutter compensation before CYCLE800")
    transform = state.transform
    if transform.rotation_active or transform.scaling_active or transform.translation != (0.0, 0.0, 0.0):
        _unsupported("CYCLE800 composition with programmed transforms is not modeled")
    if values[1] != "0" and (state.kinematics is None or state.kinematics.id not in TCP_TABLE_PROFILES):
        raise SemanticError("TWP_KINEMATICS_REQUIRED", "CYCLE800 requires an angled AC/BC table profile", "unsupported")
    if st == 200001 and not state.twp.active:
        _unsupported("Additive CYCLE800 requires an active tilted frame")


def compile_swivel(syntax, state):
    args = syntax.cycle_args
    values = tuple(
        0.0 if not arg else parameter_value(arg, state.siemens_parameters, state.siemens_variables)
        for i, arg in enumerate(args)
        if i != 1
    )
    # Keep documented parameter positions, including the quoted data-set name.
    values = values[:1] + (args[1][1:-1],) + values[1:]
    _validate_options(values, state)
    if values[1] == "0":
        if any(values[i] for i in range(4, 13)):
            _unsupported("CYCLE800 data-set cancellation requires a new zero frame")
        return SwivelFrame((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), IDENTITY, None, int(values[0]), True)
    if values[1] not in ("", "TISCH", "R_DATA"):
        _unsupported("Only the selected fixed table profile / TISCH data set is modeled")
    angles = tuple(values[7:10])
    matrix = IDENTITY
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    mode = int(values[3])
    for index, angle in enumerate(angles):
        axis = ((mode >> (index * 2)) & 3) - 1
        matrix = _multiply(matrix, _rotation(axes[axis], angle))
    before = tuple(value * state.unit_scale for value in values[4:7])
    after = transform_vector(matrix, tuple(value * state.unit_scale for value in values[10:13]))
    origin = tuple(before[i] + after[i] for i in range(3))
    if values[2] == 200001:
        origin = state.twp.apply(origin)
        matrix = _multiply(state.twp.orientation, matrix)
    if not all(math.isfinite(value) for value in origin):
        _unsupported("CYCLE800 frame offset exceeds finite geometry")
    rotary = (
        None
        if values[13] == 0
        else solve_table_orientation(state.kinematics, matrix, state.rotary_angles, direction=int(values[13]))
    )
    return SwivelFrame(origin, angles, matrix, rotary, int(values[0]))


def apply_swivel(block, frame, state, events):
    if frame is not None and frame.retract_mode:
        events.append(
            ExecutionEvent(
                "MACHINE_RETRACT_REQUEST",
                block.index,
                code=f"CYCLE800_FR{frame.retract_mode}",
                axes=("Z",) if frame.retract_mode == 1 else ("Z", "X", "Y"),
            )
        )
    if frame is None or frame.reset:
        _cancel_twp(state)
        events.append(ExecutionEvent("TILTED_WORK_PLANE_OFF", block.index, code="CYCLE800"))
        return
    old = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
    configure_tilted_frame(state, frame.origin, frame.angles, frame.orientation, block.index)
    events.append(
        ExecutionEvent(
            "TILTED_WORK_PLANE_ON",
            block.index,
            code="CYCLE800",
            twp_origin=frame.origin,
            twp_angles=frame.angles,
            twp_orientation=frame.orientation,
        )
    )
    if frame.rotary is not None:
        _orient_twp_tool_axis(state, solved=frame.rotary)
        new = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
        for kind in ("TOOL_AXIS_ORIENT", "ROTARY_INDEX"):
            events.append(
                ExecutionEvent(
                    kind,
                    block.index,
                    code="CYCLE800",
                    old_abc=old,
                    new_abc=new,
                    twp_orientation=frame.orientation,
                    kinematics_profile=state.kinematics.id,
                )
            )
