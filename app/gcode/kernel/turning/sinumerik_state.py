"""Siemens XZ state in physical radii; public turning traces use diameter X."""

import math
from dataclasses import dataclass, field, replace

from ..conversion import trace_motion
from ..frontend.model import Motion, Point2
from ..geometry.arcs import resolve_arc
from ..resources import SemanticError, checkpoint
from ..types import ExecutionEvent, MachineSignal


def unsupported(message, code="UNSUPPORTED_SINUMERIK_TURNING"):
    raise SemanticError(code, message, "unsupported")


@dataclass
class TurningState:
    position: Point2 = field(default_factory=lambda: Point2(0, 0))
    offsets: dict = field(default_factory=dict)
    shift: Point2 = field(default_factory=lambda: Point2(0, 0))
    active_wcs: int = 54
    unit_scale: float = 1.0
    feed_scale: float = 1.0
    diameter_mode: str = "DIAMON"
    absolute: bool = True
    native: bool = True
    iso_system: str = "A"
    modal_move: int = 0
    feed: float | None = None
    feed_mode: str = "per_minute"
    spindle_mode: str = "rpm"
    spindle_speed: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False
    cutter_comp: int = 40
    tool: str | None = None
    edge: int = 0
    home: Point2 = field(default_factory=lambda: Point2(0, 0))
    emulate_home: bool = False
    tolerance: float = 0.01
    sinumerik_840d_sl: bool = True
    siemens_parameters: dict = field(default_factory=dict)
    siemens_variables: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)
    motions: list = field(default_factory=list)
    threading: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    events: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    ended: str | None = None
    program: object = None

    @property
    def offset(self):
        x, z = self.offsets.get(self.active_wcs, (0.0, 0.0))
        return Point2(x / 2 + self.shift.x, z + self.shift.z)

    @property
    def spindle_rpm(self):
        if self.spindle_mode == "rpm":
            return self.spindle_speed
        diameter = abs(2 * self.position.x)
        if not diameter or self.spindle_speed is None:
            return self.spindle_limit_rpm
        rpm = self.spindle_speed * 1000 / (math.pi * diameter)
        return min(rpm, self.spindle_limit_rpm) if self.spindle_limit_rpm else rpm

    def machine(self, point):
        return Point2(point.x + self.offset.x, point.z + self.offset.z)

    def programmed(self, point):
        return Point2(point.x - self.offset.x, point.z - self.offset.z)

    def rebase(self, *, wcs=None, shift=None):
        point = self.machine(self.position)
        if wcs is not None:
            self.active_wcs = wcs
        if shift is not None:
            self.shift = shift
        self.position = self.programmed(point)

    def x_value(self, value, *, incremental=False):
        diameter = self.diameter_mode == "DIAMON" or self.diameter_mode == "DIAM90" and not incremental
        return value * self.unit_scale / (2 if diameter else 1)

    def target(self, words, syntax, *, machine=False):
        start = self.machine(self.position) if machine else self.position
        result = [start.x, start.z]
        for index, axis in enumerate("XZ"):
            if axis in words:
                increment = not self.absolute or axis in syntax.incremental_linear
                if machine:
                    increment = False
                value = (
                    self.x_value(words[axis], incremental=increment) if axis == "X" else words[axis] * self.unit_scale
                )
                if machine and self.emulate_home and value == 0:
                    value = self.home.x if axis == "X" else self.home.z
                result[index] = result[index] + value if increment else value
        if not self.native:
            result[0] += self.x_value(words.get("U", 0), incremental=True)
            result[1] += words.get("W", 0) * self.unit_scale
        point = Point2(*result)
        return self.programmed(point) if machine else point

    def emit(self, target, block, *, move=0, feed=None, radius=None, i=None, k=None, cycle=False, threading=False):
        if target == self.position and move not in (2, 3):
            return
        start, end = self.machine(self.position), self.machine(target)
        motion = Motion(
            move,
            Point2(2 * start.x, start.z),
            Point2(2 * end.x, end.z),
            radius,
            feed,
            i=None if i is None else 2 * i,
            k=k,
            source_block=block.index,
            source_nlabel=block.nlabel,
            source_raw=block.raw,
            source_kind="cycle" if cycle else "motion",
            compensation_mode=self.cutter_comp,
            tool=self.tool,
        )
        resolve_arc(replace(trace_motion(motion), x_scale=0.5), source_arc_type=1, tolerance=self.tolerance)
        checkpoint("generated_motions")
        self.motions.append(motion)
        self.threading.append(threading)
        self.position = target

    def select_tool(self, words, syntax, block):
        if syntax.named_tool:
            unsupported("Named turning tools require a controller tool-table mapping")
        if "T" in words:
            number = words["T"]
            if number < 0 or not number.is_integer() or number > 9999:
                raise SemanticError("INVALID_TOOL", "Turning T must be an integer within 0..9999")
            selected = f"T{int(number):04d}" if number else None
            self.events.append(ExecutionEvent("tool_change", block.index, "T", tool=selected, previous_tool=self.tool))
            self.tool = selected
        if "D" in words:
            if words["D"] < 0 or not words["D"].is_integer():
                raise SemanticError("INVALID_SINUMERIK_TOOL_EDGE", "D requires a nonnegative cutting-edge number")
            self.edge = int(words["D"])
            self.events.append(ExecutionEvent("tool_edge_select", block.index, f"D{self.edge}", tool=self.tool))

    def spindle(self, words, codes):
        current_rpm = self.spindle_rpm
        if 96 in codes:
            self.spindle_mode = "css"
        elif 97 in codes:
            self.spindle_mode = "rpm"
            if "S" not in words:
                self.spindle_speed = current_rpm
        if "LIMS" in words:
            if words["LIMS"] <= 0:
                raise SemanticError("INVALID_SPINDLE_LIMIT", "LIMS must be positive")
            self.spindle_limit_rpm = words["LIMS"]
        if "S" in words:
            if words["S"] < 0:
                raise SemanticError("INVALID_SPINDLE_SPEED", "S must be nonnegative")
            self.spindle_speed = words["S"]
            if self.spindle_mode == "css" and self.feed_scale == 25.4:
                self.spindle_speed *= 0.3048

    def machine_functions(self, words, block):
        kinds = {
            0: "stop",
            1: "optional_stop",
            3: "spindle_cw",
            4: "spindle_ccw",
            5: "spindle_stop",
            8: "coolant_on",
            9: "coolant_off",
            19: "spindle_orient",
        }
        for value in words.get("_M", ()):
            if value not in {*kinds, 2, 6, 30}:
                unsupported(f"Turning machine function M{value:g} is not modeled")
            number = int(value)
            if number in (3, 4, 5):
                self.spindle_running = number != 5
            if number in kinds:
                self.signals.append(MachineSignal(kinds[number], block.index, f"M{number}"))
            if number in (2, 30):
                self.ended = f"M{number}"
                self.events.append(ExecutionEvent("program_end", block.index, self.ended))
