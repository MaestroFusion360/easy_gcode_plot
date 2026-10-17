"""POCKET3/4, Siemens Cycles 01/2008, classic positional interface."""

import math
from dataclasses import dataclass, field, replace
from itertools import islice

from ...compensation.milling.offset import _tool_radius
from ...geometry.pockets import equal_steps, rectangle_contour
from ...machine.cycles import CycleContext, CycleOutcome
from ...resources import SemanticError, checkpoint
from ..emitter import _motion
from ..sinumerik_parameters import parameter_value
from ..state import MillState


def unsupported(message):
    raise SemanticError("UNSUPPORTED_SINUMERIK_MILLING_CYCLE", message, "unsupported")


def arguments(syntax, state, minimum, maximum):
    args = syntax.cycle_args
    if not minimum <= len(args) <= maximum:
        unsupported(f"{syntax.kind.upper()} requires {minimum}..{maximum} positional parameters (01/2008)")
    trees = dict(syntax.scalar_expressions)
    values = tuple(
        parameter_value(arg, state.siemens_parameters, state.siemens_variables, trees.get(arg)) if arg else None
        for arg in args
    )
    if any(v is None for v in values[:minimum]) or any(v is not None and not math.isfinite(v) for v in values):
        unsupported("Required parameters must be explicit finite numbers")
    return values + (None,) * (maximum - len(values))


def cutter_radius(state):
    radius = _tool_radius(state.tools.get(state.active_tool))
    if radius is None:
        unsupported("Provide an active milling cutter diameter through milling_tools/tool_resolver")
    if state.plane != 17 or state.cutter_comp != 40 or state.cycle != 80 or state.native_cycle is not None:
        unsupported("Milling cycle subset requires G17, G40, G80 and no active MCALL")
    if state.tcp_control or state.polar_active or state.cip_mode:
        unsupported("TCP, polar and CIP execution are outside the milling-cycle subset")
    if state.feed_mode != "per_minute":
        unsupported("Milling cycles require feed per minute")
    return radius / state.unit_scale


@dataclass
class PocketPath:
    context: CycleContext
    state: MillState = field(init=False)
    motions: list = field(default_factory=list)

    def __post_init__(self):
        self.state = replace(
            self.context.machine_state, absolute=True, source_arc_type=1, native_spindle_semantics=False
        )

    def add(self, move, end, *, center=None, feed=None, turns=0):
        self.state.move, self.state.feed = move, feed
        words = dict(zip("XYZ", end, strict=True))
        if center is not None:
            start = (self.state.x, self.state.y, self.state.z)
            words.update({key: center[i] - start[i] / self.state.unit_scale for i, key in enumerate("IJK")})
            words["TURN"] = turns
        checkpoint("generated_motions")
        motion = _motion(
            self.context.block, self.state, words, wcs_offsets=self.context.coordinate_context, source_kind="cycle"
        )
        if motion is not None:
            self.motions.append(motion)

    def outcome(self):
        return CycleOutcome(
            True,
            tuple(self.motions),
            position_update=(("x", self.state.x), ("y", self.state.y), ("z", self.state.z)),
        )


def execute_pocket(context, syntax):
    state = context.machine_state
    tool = cutter_radius(state)
    rectangular = syntax.kind == "pocket3"
    p = arguments(syntax, state, 17 if rectangular else 14, 23 if rectangular else 19)
    offset = 3 if rectangular else 0
    mid, allowance, floor, feed, plunge, direction, mode = p[7 + offset : 14 + offset]
    direction = _direction(direction, state)
    _validate_mode(p, rectangular, mode)
    rtp, rfp, safety, depth = p[:4]
    if safety < 0 or depth >= rfp or rtp < rfp + safety or min(mid, allowance, floor) < 0 or min(feed, plunge) <= 0:
        unsupported("Require downward depth, valid clearances/allowances and positive milling/plunging feeds")
    if floor >= rfp - depth:
        unsupported("Floor allowance must be smaller than pocket depth")
    path = PocketPath(context)
    plan = _Plan(path, p, tool, rectangular, direction)
    plan.validate()
    if mode % 10 == 1:
        plan.rough()
    else:
        plan.finish()
    return path.outcome()


def _direction(value, state):
    if value in {2, 3}:
        return int(value)
    if value not in {0, 1} or state.spindle_direction not in {3, 4}:
        unsupported("CDIR must be 2/3, or 0/1 with a known M3/M4 spindle direction")
    return 3 if (value == 0) == (state.spindle_direction == 3) else 2


def _validate_mode(p, rectangular, mode):
    allowed = (
        {1, 2, 11, 12, 21, 22, 31, 32} if rectangular else {1, 2, 11, 12, 21, 22, 1001, 1002, 1011, 1012, 1021, 1022}
    )
    if mode not in allowed:
        unsupported("Invalid VARI machining/insertion strategy")
    start = 18 if rectangular else 15
    count = 3 if rectangular else 2
    if any(value not in {None, 0} for value in p[start : start + count]):
        unsupported("Preformed blank dimensions AP1/AP2/AD are not modeled")


@dataclass
class _Plan:
    path: PocketPath
    p: tuple
    tool: float
    rectangular: bool
    move: int

    def __post_init__(self):
        offset = 3 if self.rectangular else 0
        self.mid, self.side, self.floor, self.feed, self.plunge, _, self.mode = self.p[7 + offset : 14 + offset]
        self.width = self.p[14 + offset] or 1.6 * self.tool
        self.radius, self.pitch = self.p[-2] or 0, self.p[-1] or 0
        self.x, self.y = self.p[7:9] if self.rectangular else self.p[5:7]
        self.angle = math.radians(self.p[9]) if self.rectangular else 0
        self.a, self.b = (self.p[4] / 2, self.p[5] / 2) if self.rectangular else (self.p[4], self.p[4])
        self.corner = max(self.tool, self.p[6]) if self.rectangular else self.a

    def validate(self):
        if self.width <= 0 or min(self.a, self.b) - self.tool - self.side <= 0:
            unsupported("Cutter and allowance must fit inside positive pocket dimensions")
        extent = min(self.a, self.b) - self.tool - self.side
        width = extent / max(1, math.ceil(extent / self.width))
        limit = (1.6 if self.rectangular else 2) * self.tool
        if self.mode % 10 == 1 and width > limit + 1e-9:
            unsupported("MIDA leaves unmodeled material between clearing contours; reduce the infeed width")
        if self.rectangular and (self.corner > min(self.a, self.b) or not 0 <= self.p[9] < 180):
            unsupported("Invalid pocket corner radius or STA angle")
        if self.mode // 10 % 10 == 2 and self.mode % 10 == 1:
            if not 0 < self.radius <= min(self.tool, min(self.a, self.b) - self.tool - self.side) or self.pitch <= 0:
                unsupported("Helical insertion requires fitting RAD1>0 and DP1>0")
        if self.mode // 10 % 10 == 3 and not 0 < self.radius < 90:
            unsupported("Oscillating insertion requires a RAD1 angle between 0 and 90 degrees")
        if self.mode >= 1000 and self.mode % 10 == 1 and self.a - self.tool - self.side > self.tool:
            unsupported("Helical roughing requires the cutter sweep to cover the pocket center")

    def point(self, x, y, z):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return self.x + c * x - s * y, self.y + s * x + c * y, z

    def add(self, move, x, y, z, *, center=None, plunge=False, turns=0):
        self.path.add(
            move,
            self.point(x, y, z),
            center=self.point(*center, z) if center is not None else None,
            feed=(self.plunge if plunge else self.feed) * self.path.state.native_feed_scale,
            turns=turns,
        )

    def contour(self, z, allowance):
        a, b = self.a - self.tool - allowance, self.b - self.tool - allowance
        if not self.rectangular:
            self.add(1, a, 0, z)
            if a > 1e-10:
                self.add(self.move, a, 0, z, center=(0, 0))
            return
        radius = max(0, self.corner - self.tool - allowance)
        for end, center in rectangle_contour(a, b, radius, self.move == 2):
            self.add(self.move if center else 1, *end, z, center=center)

    def clear(self, z, allowance):
        extent = min(self.a, self.b) - self.tool - allowance
        count = max(1, math.ceil(extent / self.width))
        for index in range(count, -1, -1):
            checkpoint("cycle_iterations")
            self.contour(z, allowance + extent * index / count)

    def rough(self):
        rtp, rfp, safety, depth = self.p[:4]
        self.add(0, 0, 0, rtp)
        self.add(0, 0, 0, rfp + safety)
        if self.mode >= 1000:
            self._helical_wall(rfp, depth + self.floor)
        else:
            for infeed in equal_steps(rfp + safety - depth - self.floor, self.mid):
                checkpoint("cycle_iterations")
                z = rfp + safety - infeed
                self.insert(z)
                self.clear(z, self.side)
                self.add(1, 0, 0, z)
        self.add(0, 0, 0, rtp)

    def insert(self, z):
        strategy = self.mode // 10 % 10
        if strategy in {0, 1}:
            self.add(strategy, 0, 0, z, plunge=True)
        elif strategy == 2:
            height = self.path.state.z / self.path.state.unit_scale
            self.add(1, self.radius, 0, height, plunge=True)
            turns = max(1, math.ceil((height - z) / self.pitch))
            self.add(self.move, self.radius, 0, z, center=(0, 0), plunge=True, turns=turns - 1)
            self.add(self.move, self.radius, 0, z, center=(0, 0), plunge=True)
            self.add(1, 0, 0, z, plunge=True)
        else:
            self._oscillate(z)

    def _oscillate(self, z):
        height = self.path.state.z / self.path.state.unit_scale
        half = self.a - self.tool - self.side
        slope = math.tan(math.radians(self.radius))
        distance, x = half, half
        while height - z > 1e-9:
            checkpoint("cycle_iterations")
            height = max(z, height - distance * slope)
            self.add(1, x, 0, height, plunge=True)
            x, distance = -x, 2 * half
        self.add(1, x, 0, z, plunge=True)
        self.add(1, 0, 0, z, plunge=True)

    def _helical_wall(self, surface, depth):
        radius = self.a - self.tool - self.side
        self.add(1, radius, 0, surface, plunge=True)
        turns = max(1, math.ceil((surface - depth) / self.mid)) if self.mid else 1
        self.add(self.move, radius, 0, depth, center=(0, 0), turns=turns - 1)
        self.add(self.move, radius, 0, depth, center=(0, 0))
        lead = min(2 / self.path.state.unit_scale, radius)
        sign = 1 if self.move == 3 else -1
        self.path.add(
            self.move,
            self.point(radius - lead, sign * lead, depth + self.p[2]),
            center=self.point(radius - lead, 0, depth),
            feed=self.feed * self.path.state.native_feed_scale,
        )
        self.add(0, 0, 0, depth + self.p[2])

    def finish(self):
        depth = self.p[3]
        if self.side:
            if self.mode >= 1000:
                self.add(0, 0, 0, self.p[0])
                self.add(0, 0, 0, self.p[1] + self.p[2])
                self.side = 0
                self._helical_wall(self.p[1], depth + self.floor)
                self.add(0, 0, 0, self.p[0])
            else:
                wall = list(self.p)
                wall[3] += self.floor
                (_rectangle if self.rectangular else _circle)(self.path, wall, self.tool, self.feed, self.move)
        if self.floor:
            self.add(0, 0, 0, self.p[0])
            self.add(0, 0, 0, depth + self.floor + self.p[2])
            self.add(1, 0, 0, depth, plunge=True)
            self.clear(depth, 0)
            self.add(1, 0, 0, depth)
            self.add(0, 0, 0, self.p[0])


def _circle(path, p, tool, feed, move):
    rtp, _, _, depth, pocket, x, y = p[:7]
    radius = pocket - tool
    if radius <= 0:
        unsupported("Pocket radius must exceed cutter radius for wall finishing")
    lead = min(2 / path.state.unit_scale, radius)
    if math.hypot(radius - lead, lead) > radius - p[8]:
        unsupported("Finishing approach must fit inside the pre-roughed pocket before the quadrant entry")
    sign = 1 if move == 3 else -1
    path.add(0, (x, y, rtp))
    path.add(0, (x, y, depth))
    path.add(0, (x + radius - lead, y - sign * lead, depth))
    path.add(
        move, (x + radius, y, depth), center=(x + radius - lead, y, depth), feed=feed * path.state.native_feed_scale
    )
    path.add(move, (x + radius, y, depth), center=(x, y, depth), feed=feed * path.state.native_feed_scale)
    path.add(0, (x, y, depth))
    path.add(0, (x, y, rtp))


def _rectangle(path, p, tool, feed, move):
    rtp, _, _, depth, length, width, corner, x, y, angle = p[:10]
    corner = max(tool, corner)
    if min(length, width) <= 2 * tool or corner > min(length, width) / 2 or not 0 <= angle < 180:
        unsupported("Require positive dimensions, fitting cutter/corner radius and 0 <= STA < 180")
    a, b, radius = length / 2 - tool, width / 2 - tool, corner - tool
    lead = min(max(2 / path.state.unit_scale, p[11]), radius)
    sign = 1 if move == 3 else -1
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def point(u, v):
        v *= sign
        return x + c * u - s * v, y + s * u + c * v, depth

    path.add(0, (x, y, rtp))
    path.add(0, (x, y, depth))
    path.add(0, point(a - lead, b - radius - lead))
    if lead > 1e-10:
        path.add(
            move, point(a, b - radius), center=point(a - lead, b - radius), feed=feed * path.state.native_feed_scale
        )
    for end, center in islice(rectangle_contour(a, b, radius), 1, None):
        path.add(
            move if center and radius > 1e-10 else 1,
            point(*end),
            center=point(*center) if center and radius > 1e-10 else None,
            feed=feed * path.state.native_feed_scale,
        )
    path.add(0, (x, y, depth))
    path.add(0, (x, y, rtp))
