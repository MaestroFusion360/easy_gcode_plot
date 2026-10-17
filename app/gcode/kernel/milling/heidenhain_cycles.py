"""Native iTNC drilling, boring and tapping expansion in physical coordinates."""

import math
from dataclasses import dataclass
from typing import Any

from ..resources import SemanticError, checkpoint, require_progress
from ..types import ExecutionEvent, MachineSignal, ResolvedDrillingOperation
from .heidenhain_pockets import POCKET_CYCLES, execute_pocket
from .heidenhain_thread import execute_thread

DRILLING_CYCLES = frozenset({1, 2, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 240, 241})


@dataclass(frozen=True)
class _DrillPlan:
    surface: float
    depth: float
    safety: float
    returned: float
    feed: float
    direction: int
    tapping: bool
    peck: bool
    start: tuple[float, float, float]


@dataclass
class _Drill:
    state: Any
    block: Any
    code: int

    def q(self, number, default=0.0):
        # Cycle 200 uses fixed Q202 pecks and Q200 re-entry clearance.
        # Unrelated global Q variables remain available to the part program.
        if self.code == 200 and number in {205, 212, 258}:
            return default
        return self.state.parameters.get(f"Q{number}", default)

    @property
    def axis(self):
        return "XYZ".index(self.state.spindle_axis)

    def signal(self, kind, value=None):
        self.state.signals.append(MachineSignal(kind, self.block.index, f"CYCL {self.code}", value))

    def dwell(self, number):
        duration = self.q(number)
        if duration > 0:
            self.signal("dwell", duration)

    def axial(self, depth, move=0, feed=None):
        point = list(self.state.position)
        point[self.axis] = depth
        self.state.linear(tuple(point), self.block, move=move, feed=feed, cycle=True)

    def retract_feed(self, plunge_feed):
        """Keep a cycle's symbolic MAX distinct from zero (use plunge feed)."""
        if "Q208" in self.state.cycle_rapid_parameters:
            return 0, None
        feed = self.q(208) * self.state.scale or plunge_feed
        return 1, feed

    def preposition(self, depth, default_feed=0.0):
        """Q253 MAX/FMAX is rapid positioning, never a zero cutting feed."""
        if "Q253" in self.state.cycle_rapid_parameters:
            self.axial(depth, move=0)
        else:
            self.axial(depth, move=1, feed=self.q(253, default_feed) * self.state.scale)

    def offset(self, point, distance):
        result = list(point)
        axes = [index for index in range(3) if index != self.axis]
        direction = int(self.q(214, 1))
        axis = axes[0] if direction in {1, 2} else axes[1]
        result[axis] += distance * (-1 if direction in {1, 3} else 1)
        return tuple(result)

    def pecks(self, surface, depth, safety, feed):
        direction = -1 if depth < surface else 1
        total = abs(depth - surface)
        step = abs(self.q(202, total)) or total
        reduction = abs(self.q(212))
        minimum = abs(self.q(205))
        chip_stroke = abs(self.q(256)) * self.state.scale
        break_count = max(0, int(self.q(213))) if self.code == 203 else 0
        step *= self.state.scale
        reduction *= self.state.scale
        minimum *= self.state.scale
        cut, peck = surface, 0
        while direction * (depth - cut) > 1e-9:
            checkpoint("cycle_iterations")
            target = cut + direction * min(step, abs(depth - cut))
            require_progress(cut, target)
            self.axial(target, 1, feed)
            cut, peck = target, peck + 1
            if direction * (depth - cut) <= 1e-9:
                break
            chip_only = break_count > 0 and peck % break_count != 0
            if chip_only:
                self.axial(cut - direction * min(chip_stroke, abs(cut - surface)))
            else:
                move, retract_feed = self.retract_feed(feed) if self.code == 203 else (0, None)
                self.axial(safety, move, retract_feed)
                self.dwell(210)
                clearance = abs(self.q(258, self.q(200))) * self.state.scale
                if self.code == 205:
                    clearance = min(clearance, abs(self.q(259, clearance / self.state.scale)) * self.state.scale)
                self.axial(cut - direction * min(clearance, abs(cut - surface)))
            step = max(minimum, step - reduction)
            if step <= 1e-9:
                step = abs(depth - cut)

    def back_boring(self):
        scale = self.state.scale
        surface = self.q(203) * scale
        thickness = abs(self.q(250)) * scale
        clearance = abs(self.q(200)) * scale
        edge_height = abs(self.q(252)) * scale
        underside = surface - thickness
        target = underside + self.q(249) * scale - edge_height
        through = underside - clearance - edge_height
        start = tuple(self.state.position)
        self.axial(surface + clearance)
        centered = tuple(self.state.position)
        shift = abs(self.q(251)) * scale
        self.signal("spindle_orient", self.q(336))
        self.state.linear(self.offset(centered, shift), self.block, cycle=True)
        self.preposition(through, (self.state.feed or 0) / scale)
        at_depth = list(centered)
        at_depth[self.axis] = through
        self.state.linear(tuple(at_depth), self.block, cycle=True)
        self.signal("spindle_cw")
        self.axial(target, 1, self.q(254, self.state.feed or 0) * scale)
        self.dwell(255)
        self.preposition(through, (self.state.feed or 0) / scale)
        self.signal("spindle_orient", self.q(336))
        self.state.linear(self.offset(self.state.position, shift), self.block, cycle=True)
        self.preposition(surface + abs(self.q(204, self.q(200))) * scale)
        returned = list(start)
        returned[self.axis] = self.state.position[self.axis]
        self.state.linear(tuple(returned), self.block, cycle=True)

    def bore_milling(self, surface, depth, safety, returned, feed):
        axis = self.axis
        plane, axes = {2: (17, (0, 1)), 1: (18, (0, 2)), 0: (19, (1, 2))}[axis]
        tool = self.state.tools.get(self.state.tool, {})
        diameter = self.q(335) * self.state.scale
        tool_diameter = float(tool.get("diameter", 0))
        radius = (diameter - tool_diameter) / 2
        if radius <= 0:
            raise SemanticError("INVALID_BORE_DIAMETER", "Cycle 208 bore diameter must exceed the cutter diameter")
        center = list(self.state.position)
        center[axis] = surface
        self.axial(safety)
        rim = list(center)
        rim[axis] = safety
        rim[axes[0]] += radius
        self.state.linear(tuple(rim), self.block, cycle=True)
        self.axial(surface, 1, feed)
        pitch = abs(self.q(334, abs(depth - surface) / self.state.scale)) * self.state.scale
        if pitch <= 1e-9:
            raise SemanticError("INVALID_BORE_PITCH", "Cycle 208 requires a nonzero infeed per helix")
        direction = -1 if depth < surface else 1
        while direction * (depth - self.state.position[axis]) > 1e-9:
            checkpoint("cycle_iterations")
            target = list(self.state.position)
            target[axis] += direction * min(pitch, abs(depth - target[axis]))
            delta = [0.0, 0.0, 0.0]
            delta[axes[0]] = -radius
            self.state.arc_motion(
                tuple(target),
                self.block,
                move=2 if plane == 18 else 3,
                plane=plane,
                delta=tuple(delta),
                feed=feed,
                cycle=True,
            )
        self.axial(returned)
        center[axis] = returned
        self.state.linear(tuple(center), self.block, cycle=True)

    def execute(self):
        if self.code == 204:
            self.back_boring()
            return
        plan = self.resolve()
        self.axial(plan.safety)
        if self.code == 208:
            self.bore_milling(plan.surface, plan.depth, plan.safety, plan.returned, plan.feed)
            return
        self.begin_signals(plan)
        self.dwell(210)
        self.plunge(plan)
        self.dwell(211)
        self.retract(plan)
        self.publish_operation(plan)

    def resolve(self):
        scale = self.state.scale
        surface = self.q(203) * scale
        depth_value = self.q(201)
        if self.code == 240 and self.q(343) != 0:
            angle = self.q(345, 90)
            depth_value = -abs(self.q(344)) / (2 * math.tan(math.radians(angle / 2)))
        depth = surface + depth_value * scale
        direction = -1 if depth <= surface else 1
        safety = surface - direction * abs(self.q(200)) * scale
        returned = surface - direction * max(abs(self.q(204, self.q(200))), abs(self.q(200))) * scale
        feed = self.q(206, (self.state.feed or 0) / scale) * scale
        tapping = self.code in {2, 206, 207, 209}
        if tapping and "Q239" in self.state.parameters:
            feed = abs(self.q(239)) * scale * abs(self.state.spindle_rpm or 0)
        peck = self.code in {1, 200, 203, 205, 241} and abs(self.q(202)) > 0
        return _DrillPlan(surface, depth, safety, returned, feed, direction, tapping, peck, tuple(self.state.position))

    def begin_signals(self, plan):
        if self.code == 241:
            self.signal("coolant_on", self.q(430))
            self.signal("spindle_speed", self.q(428, self.state.spindle_rpm or 0))
        if plan.tapping:
            self.signal("spindle_sync")
            if self.code in {207, 209}:
                self.signal("rigid_tapping")

    def plunge(self, plan):
        if plan.peck:
            self.pecks(plan.surface, plan.depth, plan.safety, plan.feed)
        elif self.code == 209 and abs(self.q(257)) > 0:
            self.tapping_pecks(plan)
        else:
            self.axial(plan.depth, 1, plan.feed)

    def tapping_pecks(self, plan):
        step = abs(self.q(257)) * self.state.scale
        cut = plan.surface
        while plan.direction * (plan.depth - cut) > 1e-9:
            checkpoint("cycle_iterations")
            target = cut + plan.direction * min(step, abs(plan.depth - cut))
            require_progress(cut, target)
            self.axial(target, 1, plan.feed)
            cut = target
            self.signal("spindle_reverse")
            withdrawal = plan.safety if self.q(256) == 0 else cut - plan.direction * abs(self.q(256)) * self.state.scale
            self.axial(withdrawal, 1, plan.feed * abs(self.q(403, 1)))
            if plan.direction * (plan.depth - cut) > 1e-9:
                self.signal("spindle_reverse")
                self.axial(cut, 1, plan.feed)

    def retract(self, plan):
        if plan.tapping:
            self.signal("spindle_reverse")
        if self.code == 202:
            self.signal("spindle_orient", self.q(336))
        feed_return = self.code == 201 or plan.tapping
        scale = self.state.scale
        retract_feed = self.q(208, plan.feed / scale) * scale if self.code == 201 else plan.feed
        if self.code == 202 and self.q(208) not in {0, 99999}:
            feed_return, retract_feed = True, self.q(208) * scale
        move = 1 if feed_return else 0
        if self.code == 203:
            move, retract_feed = self.retract_feed(plan.feed)
        self.axial(plan.safety, move, retract_feed)
        self.axial(plan.returned)
        if plan.tapping:
            self.signal("spindle_reverse")
        if self.code == 241:
            self.signal("coolant_off", self.q(431))

    def publish_operation(self, plan):
        scale = self.state.scale
        reference = list(plan.start)
        reference[self.axis] = plan.surface
        bottom = list(reference)
        bottom[self.axis] = plan.depth
        safe = list(reference)
        safe[self.axis] = plan.safety
        kind = (
            "tapLeft"
            if plan.tapping and self.q(239, 1) < 0
            else "tap"
            if plan.tapping
            else "peckDrill"
            if plan.peck
            else "drill"
        )
        operation = ResolvedDrillingOperation(
            kind,
            self.state.machine(plan.start),
            self.state.machine(bottom),
            self.state.machine(safe),
            self.state.machine(reference),
            self.state.machine(self.state.position),
            plan.feed,
            "per_minute",
            dwell_bottom=max(0, self.q(211)),
            peck_first=abs(self.q(202)) * scale,
            peck_reduction=abs(self.q(212)) * scale,
            peck_minimum=abs(self.q(205)) * scale,
            spindle_speed=self.state.spindle_rpm or 0,
            rigid_tapping=self.code in {207, 209},
        )
        self.state.events.append(ExecutionEvent("drilling", self.block.index, f"CYCL {self.code}", drilling=operation))


def execute_cycle(state, block):
    code = state.cycle_code
    if code in POCKET_CYCLES:
        execute_pocket(state, block)
        return
    if code == 262:
        execute_thread(state, block)
        return
    if code is None:
        raise SemanticError("MISSING_HEIDENHAIN_CYCLE", "CYCL CALL requires an executed CYCL DEF")
    if code == 9:
        state.signals.append(MachineSignal("dwell", block.index, "CYCL 9", state.cycle_subvalues.get(1, 0)))
        return
    if code not in DRILLING_CYCLES:
        raise SemanticError(
            "UNSUPPORTED_HEIDENHAIN_CYCLE", f"Cycle {code} has no geometry implementation", "unsupported"
        )
    _Drill(state, block, code).execute()
