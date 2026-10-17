"""DEF-active patterns: iTNC 530 34049x-06, Cycles manual pp. 172-177."""

import math

from ..resources import SemanticError, checkpoint
from .heidenhain_cycles import DRILLING_CYCLES, execute_cycle

PATTERN_CYCLES = frozenset({220, 221})
_COMMON = {"Q200", "Q203", "Q204", "Q301"}
_PARAMETERS = {
    220: _COMMON | {"Q216", "Q217", "Q244", "Q245", "Q246", "Q247", "Q241", "Q365"},
    221: _COMMON | {"Q225", "Q226", "Q237", "Q238", "Q242", "Q243", "Q224"},
}


def begin_pattern(state, syntax):
    names = {p.name for p in syntax.cycle_parameters}
    if names != _PARAMETERS[syntax.cycle_code]:
        raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Specify all documented pattern parameters explicitly")
    if state.cycle_code not in DRILLING_CYCLES | {251, 252, 262}:
        raise SemanticError("MISSING_HEIDENHAIN_CYCLE", "Define a machining cycle before the DEF-active pattern")
    if state.compensation_mode != 40:
        raise SemanticError("UNSUPPORTED_HEIDENHAIN_PATTERN", "Patterns require radius compensation R0", "unsupported")
    state.pending_pattern = syntax


def finish_pattern_definition(state, block):
    syntax = state.pending_pattern
    if syntax is None or block.index != syntax.cycle_parameters[-1].block_index:
        return
    state.pending_pattern = None
    values = {p.name: state.parameters[p.name] for p in syntax.cycle_parameters}
    _validate(values, syntax.cycle_code)
    _execute(state, syntax.cycle_code, values, block)


def _integer(values, name):
    value = values[name]
    if not value.is_integer() or not 1 <= value <= 99999:
        raise SemanticError("INVALID_HEIDENHAIN_PATTERN", f"{name} must be an integer within 1..99999")
    return int(value)


def _validate(q, code):
    if not all(math.isfinite(value) for value in q.values()):
        raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Pattern parameters must be finite")
    if any(not 0 <= q[name] <= 99999.9999 for name in ("Q200", "Q204")) or q["Q301"] not in {0, 1}:
        raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Invalid clearance or Q301; use numeric 0/1")
    if code == 220:
        _integer(q, "Q241")
        if q["Q244"] < 0 or q["Q365"] not in {0, 1} or any(abs(q[n]) > 360 for n in ("Q245", "Q246", "Q247")):
            raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Invalid pitch circle, angle or Q365")
        if q["Q365"] == 1 and q["Q244"] == 0:
            raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Circular transfer requires a positive pitch diameter")
        if q["Q247"] == 0 and q["Q245"] == q["Q246"]:
            raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Specify distinct starting/stopping angles")
    else:
        _integer(q, "Q242")
        _integer(q, "Q243")
        if abs(q["Q224"]) > 360:
            raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Q224 must be within -360..360")


def _positions(q, code):
    if code == 220:
        count = int(q["Q241"])
        span = q["Q246"] - q["Q245"]
        divisor = count if abs(span) == 360 else max(1, count - 1)
        step = q["Q247"] or span / divisor
        for index in range(count):
            angle = math.radians(q["Q245"] + index * step)
            yield q["Q216"] + q["Q244"] / 2 * math.cos(angle), q["Q217"] + q["Q244"] / 2 * math.sin(angle)
    else:
        c, s = math.cos(math.radians(q["Q224"])), math.sin(math.radians(q["Q224"]))
        for row in range(int(q["Q243"])):
            columns = range(int(q["Q242"]))
            for col in reversed(columns) if row % 2 else columns:
                x, y = col * q["Q237"], row * q["Q238"]
                yield q["Q225"] + c * x - s * y, q["Q226"] + s * x + c * y


def _execute(state, code, q, block):
    axis = "XYZ".index(state.spindle_axis)
    u, v = {17: (0, 1), 18: (2, 0), 19: (1, 2)}[state.plane]
    scale = state.scale
    safe = (q["Q203"] + q["Q200"]) * scale
    clear = (q["Q203"] + max(q["Q200"], q["Q204"])) * scale
    point = list(state.position)
    point[axis] = clear
    state.linear(tuple(point), block, cycle=True)
    for index, (x, y) in enumerate(_positions(q, code)):
        checkpoint("cycle_iterations")
        point = list(state.position)
        point[axis] = clear if index == 0 or q["Q301"] else safe
        state.linear(tuple(point), block, cycle=True)
        point[u], point[v] = x * scale, y * scale
        _transfer(state, code, q, block, tuple(point), index, u, v)
        point[axis] = safe
        state.linear(tuple(point), block, cycle=True)
        saved = state.parameters["Q204"]
        try:
            state.parameters["Q204"] = q["Q204"] if q["Q301"] else q["Q200"]
            execute_cycle(state, block)
        finally:
            state.parameters["Q204"] = saved


def _transfer(state, code, q, block, target, index, u, v):
    if code != 220 or not index or q["Q365"] == 0:
        state.linear(target, block, cycle=True)
        return
    if q["Q244"] <= 0:
        raise SemanticError("INVALID_HEIDENHAIN_PATTERN", "Circular transfer requires a positive pitch diameter")
    center = list(state.position)
    center[u], center[v] = q["Q216"] * state.scale, q["Q217"] * state.scale
    delta = tuple(center[i] - state.position[i] for i in range(3))
    direction = q["Q247"] or q["Q246"] - q["Q245"]
    state.arc_motion(target, block, move=3 if direction > 0 else 2, plane=state.plane, delta=delta, cycle=True)
