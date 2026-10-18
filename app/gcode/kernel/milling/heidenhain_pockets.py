import math
from dataclasses import dataclass
from typing import Any

from ..compensation.milling.offset import _tool_radius
from ..geometry.pockets import rectangle_contour
from ..resources import SemanticError, checkpoint

POCKET_CYCLES = frozenset({251, 252})
_COMMON = {200, 201, 202, 203, 204, 206, 207, 215, 338, 351, 366, 368, 369, 370, 385}
_PARAMETERS = {251: _COMMON | {218, 219, 220, 224, 367}, 252: _COMMON | {223}}


def _error(message, *, unsupported=False):
    raise SemanticError(
        "UNSUPPORTED_HEIDENHAIN_POCKET" if unsupported else "INVALID_HEIDENHAIN_POCKET",
        message,
        "unsupported" if unsupported else "malformed",
    )


def validate_pocket_definition(syntax):
    if syntax.cycle_code in POCKET_CYCLES:
        if {p.name for p in syntax.cycle_parameters} != {f"Q{n}" for n in _PARAMETERS[syntax.cycle_code]}:
            _error("Specify the documented pocket Q parameters explicitly")


@dataclass
class _Pocket:
    state: Any
    block: Any
    q: dict
    tool: float
    center: tuple
    a: float
    b: float
    corner: float
    angle: float
    move: int

    def point(self, x, y, z):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return self.center[0] + c * x - s * y, self.center[1] + s * x + c * y, z

    def line(self, point, move=1, feed=None):
        self.state.linear(point, self.block, move=move, feed=feed, cycle=True)

    def arc(self, point, center, feed):
        delta = tuple(center[i] - self.state.position[i] for i in range(3))
        self.state.arc_motion(point, self.block, move=self.move, plane=17, delta=delta, feed=feed, cycle=True)

    def contour(self, z, allowance, feed):
        if self.state.cycle_code == 252:
            radius = self.a - self.tool - allowance
            rim = self.point(radius, 0, z)
            self.line(rim, feed=feed)
            if radius > 1e-10:
                self.arc(rim, self.point(0, 0, z), feed)
            return
        a, b = self.a - self.tool - allowance, self.b - self.tool - allowance
        r = max(0, self.corner - self.tool - allowance)
        for end, center in rectangle_contour(a, b, r, self.move == 2):
            point = self.point(*end, z)
            if center is None:
                self.line(point, feed=feed)
            else:
                self.arc(point, self.point(*center, z), feed)

    def clear(self, z, allowance, feed):
        extent = min(self.a, self.b) - self.tool - allowance
        step = self.q["Q370"] * self.tool
        count = max(1, math.ceil(extent / step))
        for index in range(count, -1, -1):
            checkpoint("cycle_iterations")
            if index == 0:
                self.wall(z, allowance, feed)
            else:
                self.contour(z, allowance + extent * index / count, feed)

    def wall(self, z, allowance, feed):
        a, b = self.a - self.tool - allowance, self.b - self.tool - allowance
        lead = min(self.tool, a, b)
        sign = 1 if self.move == 3 else -1
        self.line(self.point(a - lead, -sign * lead, z), feed=feed)
        self.arc(self.point(a, 0, z), self.point(a - lead, 0, z), feed)
        if self.state.cycle_code == 252:
            self.arc(self.point(a, 0, z), self.point(0, 0, z), feed)
        else:
            radius = max(0, self.corner - self.tool - allowance)
            contour = list(rectangle_contour(a, b, radius, self.move == 2))
            contour[-1] = ((a, 0), None)
            for end, center in contour:
                point = self.point(*end, z)
                if center is None:
                    self.line(point, feed=feed)
                else:
                    self.arc(point, self.point(*center, z), feed)
        self.arc(self.point(a - lead, sign * lead, z), self.point(a - lead, 0, z), feed)

    def plunge(self, z, feed):
        strategy = self.q["Q366"]
        if strategy == 0:
            self.line(self.point(0, 0, z), feed=feed)
        elif strategy == 1:
            self._helix(z, feed)
        else:
            self._oscillate(z, feed)

    def _helix(self, z, feed):
        radius = min(self.tool, min(self.a, self.b) - self.tool - self.q["Q368"] * self.state.scale)
        pitch = math.tau * radius * math.tan(math.radians(_plunge_angle(self.state)))
        height = self.state.position[2]
        turns = max(1, math.ceil((height - z) / pitch))
        self.line(self.point(radius, 0, height), feed=feed)
        center = self.point(0, 0, height)
        delta = tuple(center[i] - self.state.position[i] for i in range(3))
        self.state.arc_motion(
            self.point(radius, 0, z),
            self.block,
            move=self.move,
            plane=17,
            delta=delta,
            feed=feed,
            cycle=True,
            additional_turns=turns - 1,
        )
        self.line(self.point(0, 0, z), feed=feed)

    def _oscillate(self, z, feed):
        half = self.a - self.tool - self.q["Q368"] * self.state.scale
        slope = math.tan(math.radians(_plunge_angle(self.state)))
        height, distance, x = self.state.position[2], half, half
        while height - z > 1e-9:
            checkpoint("cycle_iterations")
            height = max(z, height - distance * slope)
            self.line(self.point(x, 0, height), feed=feed)
            x, distance = -x, 2 * half
        self.line(self.point(0, 0, z), feed=feed)

    def retract(self, z):
        self.line((*self.state.position[:2], z), 0)
        self.line(self.point(0, 0, z), 0)


def _plan(state, block):
    q = {f"Q{n}": state.parameters[f"Q{n}"] for n in _PARAMETERS[state.cycle_code]}
    if not all(math.isfinite(v) and abs(v) <= 99999.9999 for v in q.values()):
        _error("Pocket values must be finite and within their documented numeric ranges")
    if state.plane != 17 or state.spindle_axis != "Z" or state.compensation_mode != 40:
        _error("Pocket cycles currently require XY/Z and R0", unsupported=True)
    if q["Q201"] > 0:
        _error("Positive depth depends on the OEM MP7441 policy", unsupported=True)
    _check_parameters(q)
    tool = _tool_radius(state.cycle_tool())
    if tool is None:
        _error("Supply a milling cutter diameter through milling_tools/tool_resolver", unsupported=True)
    if state.spindle_direction not in {3, 4}:
        _error("Specify the spindle direction with M3/M4", unsupported=True)
    pocket = _shape(state, block, q, tool)
    _check_insertion(pocket)
    return pocket


def _plunge_angle(state):
    tool = state.tools.get(state.tool, {})
    value = tool.get("ANGLE", tool.get("plunge_angle", 3.0))
    if "ANGLE" not in tool and "plunge_angle" not in tool and not state.plunge_angle_warned:
        state.warning(
            "HEIDENHAIN_DEFAULT_PLUNGE_ANGLE",
            "Pocket insertion uses an assumed plunge angle of 3 degrees",
            state.program.blocks[state.pc],
        )
        state.plunge_angle_warned = True
    try:
        angle = float(value)
    except (TypeError, ValueError):
        _error("Helical/reciprocating insertion requires the cutter ANGLE in milling_tools", unsupported=True)
    if not math.isfinite(angle) or not 0 < angle < 90:
        _error("Cutter ANGLE must be finite and between 0 and 90 degrees")
    return angle


def _check_insertion(pocket):
    strategy = pocket.q["Q366"]
    if strategy not in {0, 1, 2} or (pocket.state.cycle_code == 252 and strategy == 2):
        _error("Invalid Q366 plunging strategy")
    if strategy and pocket.q["Q215"] != 2:
        angle = _plunge_angle(pocket.state)
        reach = min(pocket.tool, min(pocket.a, pocket.b) - pocket.tool - pocket.q["Q368"] * pocket.state.scale)
        if reach * math.tan(math.radians(angle)) < 1e-9:
            _error("Cutter ANGLE produces no representable depth progress")
    if strategy == 2 and pocket.q["Q215"] != 2:
        available = 2 * (pocket.a - pocket.tool - pocket.q["Q368"] * pocket.state.scale)
        if available < 4 * pocket.tool:
            _error("Reciprocating insertion needs at least two cutter diameters of travel")


def _check_parameters(q):
    if q["Q215"] not in {0, 1, 2} or q["Q351"] not in {-1, 1} or not 0.1 <= q["Q370"] <= 1.414:
        _error("Invalid machining operation, milling direction or path overlap")
    if any(q[f"Q{n}"] < 0 for n in (200, 204, 338, 368, 369)) or q["Q202"] <= 0:
        _error("Clearances and allowances must be nonnegative, Q202 positive")
    if any(q[f"Q{n}"] <= 0 for n in (206, 207, 385)) or q["Q369"] >= -q["Q201"]:
        _error("Feeds must be positive and floor allowance less than the pocket depth")


def _shape(state, block, q, tool):
    scale = state.scale
    if state.cycle_code == 251:
        a, b = q["Q218"] * scale / 2, q["Q219"] * scale / 2
        corner = q["Q220"] * scale or tool
        angle = q["Q224"]
        position = q["Q367"]
        if position not in {0, 1, 2, 3, 4} or abs(angle) > 360 or not tool <= corner <= min(a, b):
            _error("Invalid pocket reference, rotation or corner/cutter radius")
        dx, dy = {0: (0, 0), 1: (a, b), 2: (-a, b), 3: (-a, -b), 4: (a, -b)}[position]
    else:
        a = b = q["Q223"] * scale / 2
        corner, angle, dx, dy = a, 0, 0, 0
    if min(a, b) - tool - q["Q368"] * scale <= 1e-10:
        _error("Cutter and wall allowance must fit inside the pocket")
    angle = math.radians(angle)
    c, s = math.cos(angle), math.sin(angle)
    center = state.position[0] + c * dx - s * dy, state.position[1] + s * dx + c * dy
    ccw = (q["Q351"] == 1) == (state.spindle_direction == 3)
    return _Pocket(state, block, q, tool, center, a, b, corner, angle, 3 if ccw else 2)


def _depths(surface, depth, step):
    current = surface
    while current - depth > 1e-9:
        checkpoint("cycle_iterations")
        current = max(depth, current - step)
        yield current


def execute_pocket(state, block):
    if state.parameters.get("Q201") == 0:
        return
    if state.parameters.get("Q215") == 2 and state.parameters.get("Q368") == state.parameters.get("Q369") == 0:
        state.warning(
            "HEIDENHAIN_POCKET_NO_FINISHING_ALLOWANCE",
            "Finishing-only pocket has Q368=Q369=0; no cutting passes are generated",
            block,
        )
        return
    pocket = _plan(state, block)
    q, scale = pocket.q, state.scale
    start = state.position
    surface, depth = q["Q203"] * scale, (q["Q203"] + q["Q201"]) * scale
    safe = surface + q["Q200"] * scale
    returned = surface + max(q["Q200"], q["Q204"]) * scale
    pocket.line((*start[:2], returned), 0)
    pocket.line(pocket.point(0, 0, returned), 0)
    pocket.line(pocket.point(0, 0, safe), 0)
    if q["Q215"] != 2:
        _rough(pocket, surface, depth, scale)
    if q["Q215"] != 1:
        _finish(pocket, surface, depth, scale)
    pocket.retract(returned)
    pocket.line((*start[:2], returned), 0)


def _rough(pocket, surface, depth, scale):
    q = pocket.q
    for z in _depths(surface, depth + q["Q369"] * scale, q["Q202"] * scale):
        pocket.plunge(z, q["Q206"] * scale)
        pocket.clear(z, q["Q368"] * scale, q["Q207"] * scale)
        pocket.retract(z + q["Q200"] * scale)


def _finish(pocket, surface, depth, scale):
    q = pocket.q
    feed = q["Q385"] * scale
    if q["Q368"] > 0:
        step = q["Q338"] * scale or surface - depth
        for z in _depths(surface, depth + q["Q369"] * scale, step):
            pocket.line(pocket.point(0, 0, z), 0)
            pocket.wall(z, 0, feed)
            pocket.retract(z + q["Q200"] * scale)
    if q["Q369"] > 0:
        pocket.line(pocket.point(0, 0, depth + q["Q369"] * scale + q["Q200"] * scale), 0)
        pocket.line(pocket.point(0, 0, depth), feed=q["Q206"] * scale)
        pocket.clear(depth, 0, feed)
