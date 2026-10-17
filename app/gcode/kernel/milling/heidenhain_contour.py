"""Geometric approach/departure construction for native Klartext contours."""

import math
from dataclasses import dataclass

from ..geometry.arcs import resolve_arc
from ..resources import SemanticError, checkpoint
from ..types import TraceMotion
from .heidenhain_values import scalar

_AXES = {17: (0, 1), 18: (0, 2), 19: (1, 2)}


def _unit(vector):
    length = math.hypot(*vector)
    if length <= 1e-12:
        raise SemanticError("MISSING_HEIDENHAIN_TANGENT", "Contour approach/departure requires a planar tangent")
    return tuple(value / length for value in vector)


def _point(values, origin, scale):
    result = list(origin)
    for index, axis in enumerate("XYZ"):
        if axis in values:
            result[index] = values[axis] * scale
        elif "I" + axis in values:
            result[index] += values["I" + axis] * scale
    return tuple(result)


def _arc_tangent(center, point, axes, clockwise):
    a, b = axes
    x, y = point[a] - center[a], point[b] - center[b]
    return _unit((y, -x) if clockwise else (-y, x))


def _previous_tangent(state, axes):
    a, b = axes
    for motion in reversed(state.trace_motions):
        start = state.programmed((motion.start_x, motion.start_y, motion.start_z))
        end = state.programmed((motion.end_x, motion.end_y, motion.end_z))
        if motion.arc is not None and motion.arc.plane == state.plane:
            return _arc_tangent(state.programmed(motion.arc.center), end, axes, motion.arc.clockwise)
        delta = (end[a] - start[a], end[b] - start[b])
        if math.hypot(*delta) > 1e-12:
            return _unit(delta)
    raise SemanticError("MISSING_HEIDENHAIN_TANGENT", "DEP requires a preceding planar contour movement")


def _next_tangent(state, first, axes):
    center = state.center
    parameters = dict(state.parameters)
    a, b = axes
    for block in state.program.blocks[state.pc + 1 :]:
        checkpoint()
        syntax = block.native_syntax
        if syntax.assignment is not None:
            name, expression = syntax.assignment
            parameters[name] = scalar(expression, parameters)
        values = {
            word.address: scalar(word.expression, parameters) for word in syntax.words if word.expression is not None
        }
        if syntax.kind == "center":
            center = _point(values, first, state.scale)
            continue
        if syntax.kind != "motion":
            continue
        target = _point(values, first, state.scale)
        clockwise = syntax.word("DR-") is not None if syntax.word("DR-") or syntax.word("DR+") else state.clockwise
        if syntax.command in {"C", "CP"} and center is not None:
            return _arc_tangent(center, first, axes, clockwise)
        if syntax.command == "CR":
            move = 2 if clockwise != (state.plane == 18) else 3
            motion = TraceMotion(
                move,
                first[0],
                first[2],
                target[0],
                target[2],
                values["R"] * state.scale,
                start_y=first[1],
                end_y=target[1],
                plane=state.plane,
            )
            circle = resolve_arc(motion, tolerance=state.arc_tolerance).arc
            return _arc_tangent(circle.center, first, axes, circle.clockwise)
        if math.hypot(target[a] - first[a], target[b] - first[b]) > 1e-12:
            return _unit((target[a] - first[a], target[b] - first[b]))
    raise SemanticError("MISSING_HEIDENHAIN_TANGENT", "APPR requires a following planar contour movement")


def _emit_arc(state, target, center, sign, block):
    axes = _AXES[state.plane]
    delta = tuple(center[i] - state.position[i] if i in axes else 0.0 for i in range(3))
    move = 2 if (sign < 0) != (state.plane == 18) else 3
    state.arc_motion(tuple(target), block, move=move, plane=state.plane, delta=delta, feed=state.feed)


def _tangent_contact(external, center, radius, sign, axes, *, approach):
    a, b = axes
    vx, vy = external[a] - center[a], external[b] - center[b]
    square = vx * vx + vy * vy
    if square < radius * radius - 1e-10:
        raise SemanticError("INVALID_HEIDENHAIN_APPROACH", "LCT endpoint lies inside the transition circle")
    if square <= 1e-20:
        raise SemanticError("INVALID_HEIDENHAIN_APPROACH", "LCT transition circle has no tangent from its endpoint")
    projection = radius * radius / square
    height = radius * math.sqrt(max(0.0, square - radius * radius)) / square
    candidates = []
    for branch in (-1, 1):
        point = list(external)
        point[a] = center[a] + projection * vx - branch * height * vy
        point[b] = center[b] + projection * vy + branch * height * vx
        line = (
            (point[a] - external[a], point[b] - external[b])
            if approach
            else (external[a] - point[a], external[b] - point[b])
        )
        tangent = _arc_tangent(center, point, axes, sign < 0)
        alignment = tangent[0] * line[0] + tangent[1] * line[1]
        candidates.append((alignment, tuple(point)))
    return max(candidates, key=lambda item: item[0])[1]


@dataclass(frozen=True)
class _Transition:
    approach: bool
    form: str
    axes: tuple[int, int]
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    tangent: tuple[float, float]
    side: int

    @property
    def normal(self):
        return -self.tangent[1], self.tangent[0]

    @property
    def point(self):
        return self.end if self.approach else self.start


def _straight_transition(state, transition, values, block, entry_move, entry_feed):
    a, b = transition.axes
    distance = abs(values["LEN"] * state.scale)
    vector = (
        tuple(-v for v in transition.tangent) if transition.approach and transition.form == "LT" else transition.tangent
    )
    if transition.form == "LN":
        vector = tuple(transition.side * v for v in transition.normal)
    auxiliary = list(transition.point)
    auxiliary[a] += distance * vector[0]
    auxiliary[b] += distance * vector[1]
    if transition.approach:
        auxiliary[3 - a - b] = transition.start[3 - a - b]
    state.linear(
        tuple(auxiliary),
        block,
        move=entry_move if transition.approach else 1,
        feed=entry_feed if transition.approach else state.feed,
    )
    if transition.approach:
        state.linear(transition.end, block, move=1, feed=state.feed)


def _circular_transition(state, transition, values, block, center, sign, entry_move, entry_feed):
    a, b = transition.axes
    point = transition.point
    angle = sign * math.radians(abs(values["CCA"])) * (-1 if transition.approach else 1)
    x, y = point[a] - center[a], point[b] - center[b]
    auxiliary = list(point)
    auxiliary[a] = center[a] + x * math.cos(angle) - y * math.sin(angle)
    auxiliary[b] = center[b] + x * math.sin(angle) + y * math.cos(angle)
    if transition.approach:
        auxiliary[3 - a - b] = transition.start[3 - a - b]
        state.linear(tuple(auxiliary), block, move=entry_move, feed=entry_feed)
        _emit_arc(state, transition.end, center, sign, block)
    else:
        _emit_arc(state, auxiliary, center, sign, block)


def _tangent_transition(state, transition, block, center, radius, sign):
    external = transition.start if transition.approach else transition.end
    contact = _tangent_contact(external, center, radius, sign, transition.axes, approach=transition.approach)
    if transition.approach:
        state.linear(contact, block, move=1, feed=state.feed)
        _emit_arc(state, transition.end, center, sign, block)
    else:
        _emit_arc(state, contact, center, sign, block)
        state.linear(transition.end, block, move=1, feed=state.feed)


def _curved_transition(state, transition, values, block, entry_move, entry_feed):
    a, b = transition.axes
    radius = abs(values["R"] * state.scale)
    if radius <= 1e-12:
        raise SemanticError("INVALID_HEIDENHAIN_APPROACH", "Contour transition radius must be nonzero")
    sign = transition.side * (-1 if values["R"] < 0 else 1)
    center = list(transition.point)
    center[a] += sign * radius * transition.normal[0]
    center[b] += sign * radius * transition.normal[1]
    if transition.form == "CT":
        _circular_transition(state, transition, values, block, center, sign, entry_move, entry_feed)
    else:
        _tangent_transition(state, transition, block, center, radius, sign)


def approach_departure(state, syntax, values, block, *, entry_move=1, entry_feed=None):
    command, form = syntax.command.split()
    approach = command == "APPR"
    axes = _AXES[state.plane]
    end = state.target(values)
    tangent = _next_tangent(state, end, axes) if approach else _previous_tangent(state, axes)
    transition = _Transition(
        approach, form, axes, tuple(state.position), end, tangent, -1 if state.compensation_mode == 42 else 1
    )
    if form in {"LT", "LN"}:
        _straight_transition(state, transition, values, block, entry_move, entry_feed)
    else:
        _curved_transition(state, transition, values, block, entry_move, entry_feed)
    if not approach:
        state.compensation_mode = 40
