"""Internal thread milling, iTNC 530 34049x-06 cycle 262."""

import math

from ..compensation.milling.offset import _tool_radius
from ..resources import SemanticError, checkpoint

THREAD_PARAMETERS = frozenset({"Q335", "Q239", "Q201", "Q355", "Q253", "Q351", "Q200", "Q203", "Q204", "Q207"})


def _unsupported(message):
    raise SemanticError("UNSUPPORTED_HEIDENHAIN_THREAD", message, "unsupported")


def validate_thread_definition(syntax):
    if syntax.cycle_code == 262 and {p.name for p in syntax.cycle_parameters} != THREAD_PARAMETERS:
        _unsupported("Cycle 262 requires all ten Q parameters in its definition; unrelated globals are not defaults")


def thread_plan(state):
    q = dict(state.parameters)
    rapid = "Q253" in state.cycle_rapid_parameters
    if rapid:
        q["Q253"] = 0
    if not THREAD_PARAMETERS <= q.keys():
        _unsupported("Cycle 262 requires all ten explicit numeric Q parameters")
    if not all(math.isfinite(q[name]) for name in THREAD_PARAMETERS):
        raise SemanticError("INVALID_HEIDENHAIN_THREAD", "Thread parameters must be finite")
    if state.plane != 17 or state.spindle_axis != "Z" or state.compensation_mode != 40:
        _unsupported("Cycle 262 currently requires XY/Z and R0")
    if not q["Q355"].is_integer() or not 0 <= q["Q355"] <= 99999 or q["Q201"] > 0:
        _unsupported("Q355 must be a nonnegative integer; positive depth depends on OEM MP7441 policy")
    if q["Q351"] not in {-1, 1} or state.spindle_direction not in {3, 4}:
        _unsupported("Specify Q351=+1/-1 and spindle direction M3/M4")
    _check_ranges(q, rapid)
    tool_radius = _tool_radius(state.cycle_tool())
    diameter = q["Q335"] * state.scale
    if tool_radius is None:
        _unsupported("Cycle 262 requires a milling cutter diameter from milling_tools/tool_resolver")
    if not diameter / 8 <= tool_radius < diameter / 2:
        _unsupported("Cutter must fit the thread and have diameter >= one quarter of nominal diameter")
    return q, diameter / 2 - tool_radius


def _check_ranges(q, rapid):
    valid = (
        0.0001 <= abs(q["Q239"]) <= 99.9999
        and -99999.9999 <= q["Q201"] <= -0.0001
        and 0 < q["Q335"] <= 99999.9999
        and all(0 <= q[n] <= 99999.9999 for n in ("Q200", "Q204"))
        and abs(q["Q203"]) <= 99999.9999
        and 0 < q["Q207"] <= 99999.999
        and (rapid or 0 < q["Q253"] <= 99999.999)
    )
    if not valid:
        raise SemanticError("INVALID_HEIDENHAIN_THREAD", "Invalid thread pitch, diameter, depth, clearance or feed")


def execute_thread(state, block):
    if state.parameters.get("Q201") == 0:
        return
    q, radius = thread_plan(state)
    scale = state.scale
    center = state.position[:2]
    surface, bottom = q["Q203"] * scale, (q["Q203"] + q["Q201"]) * scale
    ccw = (q["Q351"] == 1) == (state.spindle_direction == 3)
    move = 3 if ccw else 2
    direction = (1 if ccw else -1) * (1 if q["Q239"] > 0 else -1)
    pitch = abs(q["Q239"]) * scale
    state.linear((*center, surface + q["Q200"] * scale), block, cycle=True)
    for low, high in _bands(bottom, surface, pitch, int(q["Q355"]), direction):
        checkpoint("cycle_iterations")
        start, end = (low, high) if direction > 0 else (high, low)
        _thread_pass(state, block, q, radius, center, start, end, pitch, move)
    state.linear((*center, surface + max(q["Q200"], q["Q204"]) * scale), block, cycle=True)


def _bands(bottom, surface, pitch, count, direction):
    if count == 1:
        yield bottom, surface
    elif count == 0:
        yield bottom, bottom + pitch
    else:
        steps = math.ceil((surface - bottom) / (count * pitch))
        order = range(steps) if direction > 0 else reversed(range(steps))
        for index in order:
            low = bottom + index * count * pitch
            yield low, low + pitch


def _thread_pass(state, block, q, radius, center, start, end, pitch, move):
    ccw = move == 3
    direction = 1 if end > start else -1
    feed, prefeed = q["Q207"] * state.scale, q["Q253"] * state.scale
    premove = 0 if "Q253" in state.cycle_rapid_parameters else 1
    state.linear((*center, start), block, move=premove, feed=prefeed or None, cycle=True)
    state.linear((*center, start - direction * pitch / 2), block, move=premove, feed=prefeed or None, cycle=True)
    state.arc_motion(
        (center[0] + radius, center[1], start),
        block,
        move=move,
        plane=17,
        delta=(radius / 2, 0, 0),
        feed=feed,
        cycle=True,
    )
    revolutions = abs(end - start) / pitch
    remainder = revolutions % 1
    if min(remainder, 1 - remainder) * math.tau * radius <= 1e-10:
        remainder = 0
        revolutions = round(revolutions)
    angle = remainder * math.tau * (1 if ccw else -1)
    x, y = radius * math.cos(angle), radius * math.sin(angle)
    # A complete revolution is represented by the base full circle, with
    # further turns stored explicitly. Fractional revolutions keep their end.
    turns = max(0, math.ceil(revolutions) - 1)
    state.arc_motion(
        (center[0] + x, center[1] + y, end),
        block,
        move=move,
        plane=17,
        delta=(-radius, 0, 0),
        feed=feed,
        cycle=True,
        additional_turns=turns,
    )
    state.arc_motion(
        (*center, end + direction * pitch / 2),
        block,
        move=move,
        plane=17,
        delta=(-x / 2, -y / 2, 0),
        feed=feed,
        cycle=True,
    )
