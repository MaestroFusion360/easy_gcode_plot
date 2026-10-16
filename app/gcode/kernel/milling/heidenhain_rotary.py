"""Klartext tilted planes and table TCP using the shared rotary profile model.

Like FANUC/SINUMERIK, this models a logical tool tip about the WCS origin,
without OEM pivot lengths, travel limits or controller compensation tables.
"""

from dataclasses import dataclass, field

from ..api.resources import SemanticError
from ..api.types import Diagnostic, ExecutionEvent
from ..geometry.matrix import IDENTITY, multiply, rotation, transform_vector, transpose
from ..geometry.transform import CoordinateTransform
from .heidenhain_values import scalar
from .kinematics import MachineKinematics, effective_orientation, point_orientation, rotary_limit_violations
from .twp import solve_table_orientation, supports_twp_kinematics


@dataclass
class RotaryContext:
    profile: MachineKinematics | None = None
    angles: dict = field(default_factory=lambda: dict.fromkeys("ABC", 0.0))
    plane: tuple | None = None
    plane_angles: tuple | None = None
    tcp: bool = False
    shortest: bool = False
    start_orientation: tuple | None = None
    changed: bool = False

    def orientation(self):
        return effective_orientation(self.profile, self.angles) if self.profile is not None else None

    def coordinate_rotation(self):
        if self.plane is not None:
            return self.plane
        if self.profile is not None and not self.tcp:
            return point_orientation(self.profile, self.angles)
        return IDENTITY


def _require_profile(state, addresses=()):
    profile = state.rotary.profile
    if profile is None:
        raise SemanticError(
            "ROTARY_KINEMATICS_REQUIRED", "Select rotary kinematics for Klartext rotary/TCP motion", "unsupported"
        )
    if set(addresses) - profile.addresses:
        raise SemanticError(
            "UNCONFIGURED_ROTARY_AXIS", "Rotary address is not configured in the selected profile", "unsupported"
        )
    return profile


def _capture(state):
    return state.machine(state.position), state.machine(state.center) if state.center is not None else None


def set_tcp(state, enabled, block):
    if enabled:
        profile = _require_profile(state)
        if not profile.tcp_table_supported or state.rotary.plane is not None or state.spindle_axis != "Z":
            raise SemanticError(
                "UNSUPPORTED_HEIDENHAIN_TCP", "M128/TCPM requires an AC/BC table and PLANE RESET", "unsupported"
            )
    if state.rotary.tcp == enabled:
        return
    point, center = _capture(state)
    state.rotary.tcp = enabled
    state.change_frame(machine_point=point, machine_center=center)
    state.events.append(
        ExecutionEvent(
            "TCP_CONTROL_ON" if enabled else "TCP_CONTROL_OFF",
            block.index,
            code="M128" if enabled else "M129",
            kinematics_profile=state.rotary.profile.id,
        )
    )


def machine_control(state, code, block):
    if code in {128, 129}:
        set_tcp(state, code == 128, block)
    elif code in {126, 127}:
        state.rotary.shortest = code == 126
    elif code == 94:
        # M94 reduces the displayed rotary coordinates; it does not move a joint.
        state.rotary.angles = {axis: angle % 360 for axis, angle in state.rotary.angles.items()}


def spatial_angles(angles):
    """Fixed-axis SPA/SPB/SPC rotations: Rz(SPC) Ry(SPB) Rx(SPA)."""
    result = IDENTITY
    for axis, angle in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), angles, strict=True):
        result = multiply(rotation(axis, angle), result)
    return result


def plane_block(state, syntax, values, block):
    if syntax.command.startswith("FUNCTION"):
        set_tcp(state, syntax.command != "FUNCTION RESET TCPM", block)
        return
    profile = _require_profile(state)
    if not supports_twp_kinematics(profile) or state.rotary.tcp or state.spindle_axis != "Z":
        raise SemanticError(
            "UNSUPPORTED_HEIDENHAIN_PLANE", "PLANE requires two rotary joints and inactive TCP", "unsupported"
        )
    options = syntax.plane
    if options.positioning == "MOVE" or options.table_rotation == "COORD":
        raise SemanticError("UNSUPPORTED_HEIDENHAIN_PLANE", "PLANE MOVE and TABLE COORD are not modeled", "unsupported")
    reset = syntax.command == "PLANE RESET"
    angles = tuple(values.get(axis, 0.0) for axis in ("SPA", "SPB", "SPC"))
    matrix = spatial_angles(angles)
    point, center = _capture(state)
    if options.positioning == "TURN":
        solved = solve_table_orientation(profile, matrix, state.rotary.angles, direction=options.sequence)
        point = _index_plane(state, solved, point, block)
    state.rotary.plane = None if reset else matrix
    state.rotary.plane_angles = None if reset else angles
    state.change_frame(machine_point=point, machine_center=center)
    state.events.append(
        ExecutionEvent(
            "TILTED_WORK_PLANE_OFF" if reset else "TILTED_WORK_PLANE_ON",
            block.index,
            code=syntax.command,
            kinematics_profile=profile.id,
            twp_angles=None if reset else angles,
            twp_origin=state.frame.translation,
            twp_orientation=state.rotary.plane,
        )
    )


def _index_plane(state, solved, point, block):
    old = point_orientation(state.rotary.profile, state.rotary.angles)
    raw = transform_vector(transpose(old), tuple(point[i] - state.offset[i] for i in range(3)))
    before = dict(state.rotary.angles)
    state.rotary.angles.update(solved)
    rotated = transform_vector(point_orientation(state.rotary.profile, solved), raw)
    point = tuple(rotated[i] + state.offset[i] for i in range(3))
    _rotary_event(state, before, block, "TOOL_AXIS_ORIENT")
    _check_limits(state, block)
    return point


def position_rotary(state, syntax, values, block):
    addresses = {axis for axis in "ABC" if axis in values or "I" + axis in values}
    if not addresses:
        return
    _require_profile(state, addresses)
    before = dict(state.rotary.angles)
    target = _rotary_target(state, values, addresses)
    changed = any(abs(target[axis] - before[axis]) > 1e-10 for axis in addresses)
    _validate_rotary_motion(state, syntax, values, changed)
    state.rotary.angles = target
    state.rotary.changed = changed
    # A bare index keeps programmed machine XYZ, changing its displayed orientation.
    state.frame = CoordinateTransform(
        translation=state.frame.translation,
        spatial_rotation=multiply(state.rotary.coordinate_rotation(), rotation((0, 0, 1), state.rotation_degrees)),
    )
    _rotary_event(state, before, block, "ROTARY_MOTION" if state.rotary.tcp else "ROTARY_INDEX")
    _check_limits(state, block)


def _rotary_target(state, values, addresses):
    before = state.rotary.angles
    target = dict(before)
    for axis in addresses:
        target[axis] = values.get(axis, before[axis] + values.get("I" + axis, 0.0))
        if state.rotary.shortest:
            target[axis] += 360 * round((before[axis] - target[axis]) / 360)
    return target


def _validate_rotary_motion(state, syntax, values, changed):
    if syntax.kind != "motion":
        raise SemanticError(
            "UNSUPPORTED_HEIDENHAIN_EXECUTION", "Rotary addresses require an L positioning block", "unsupported"
        )
    if not state.rotary.tcp and changed:
        if not state.rapid or any(axis in values or "I" + axis in values for axis in "XYZ"):
            raise SemanticError(
                "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION",
                "Klartext simultaneous/feed rotary motion requires M128/TCPM",
                "unsupported",
            )
    if state.rotary.tcp and syntax.command != "L":
        raise SemanticError("UNSUPPORTED_HEIDENHAIN_TCP", "TCP rotary interpolation requires L blocks", "unsupported")


def _check_limits(state, block):
    for axis, value, minimum, maximum in rotary_limit_violations(state.rotary.profile, state.rotary.angles):
        state.diagnostics.append(
            Diagnostic(
                "ROTARY_LIMIT_EXCEEDED",
                f"{axis}{value:g} exceeds [{minimum:g}, {maximum:g}]",
                "warning",
                "unverified",
                block.index + 1,
                block.raw,
            )
        )


def _rotary_event(state, before, block, kind):
    state.events.append(
        ExecutionEvent(
            kind,
            block.index,
            code="PLANE" if kind == "TOOL_AXIS_ORIENT" else "L",
            axes=tuple(sorted(state.rotary.profile.addresses)),
            old_abc=tuple(before[axis] for axis in "ABC"),
            new_abc=tuple(state.rotary.angles[axis] for axis in "ABC"),
            kinematics_profile=state.rotary.profile.id,
        )
    )


def machine_target(state, values):
    displayed = state.machine(state.position)
    matrix = point_orientation(state.rotary.profile, state.rotary.angles)
    raw = list(transform_vector(transpose(matrix), tuple(displayed[i] - state.offset[i] for i in range(3))))
    for index, axis in enumerate("XYZ"):
        if axis in values:
            raw[index] = values[axis] * state.scale - state.offset[index]
    displayed = transform_vector(matrix, tuple(raw))
    return state.programmed(tuple(displayed[i] + state.offset[i] for i in range(3)))


def rotary_retract(state, parameters, block):
    """Retract along physical machine +Z, even with an active tilted frame."""
    displayed = state.machine(state.position)
    matrix = point_orientation(state.rotary.profile, state.rotary.angles)
    raw = list(transform_vector(transpose(matrix), tuple(displayed[i] - state.offset[i] for i in range(3))))
    if "MB MAX" in parameters:
        state.home_retract_target(2, block)  # shared Home opt-in and warning
        raw[2] = max(raw[2], state.home[2] - state.offset[2])
    else:
        raw[2] += scalar(parameters["MB"].expression, state.parameters) * state.scale
    displayed = transform_vector(matrix, tuple(raw))
    return state.programmed(tuple(displayed[i] + state.offset[i] for i in range(3)))
