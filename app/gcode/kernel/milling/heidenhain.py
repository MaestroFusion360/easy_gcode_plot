"""Native Klartext execution for resolved three-axis CAM paths.

The immutable source AST is consumed directly. Unsupported controller features
stop the trace at their source block; no intermediate ISO program is generated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from ..api.resources import SemanticError, active_budget, checkpoint
from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, MachineSignal, TraceMotion
from ..frontend.heidenhain import parse_heidenhain_program
from ..frontend.heidenhain_syntax import HeidenhainSyntax
from ..geometry.arcs import resolve_arc
from ..geometry.matrix import IDENTITY, rotation, transform_vector, transpose
from ..geometry.transform import CoordinateTransform
from ..runtime.diagnostics import diagnostic_from_exception
from ..runtime.execution import semantic_instructions
from .heidenhain_contour import approach_departure
from .heidenhain_cycles import DRILLING_CYCLES, execute_cycle
from .heidenhain_values import scalar

_PLANES = {"Z": (17, (0, 1)), "Y": (18, (0, 2)), "X": (19, (1, 2))}

# Machine functions with defined native execution semantics. Other M words are
# parsed as native facts but have no runtime model, so execution stops instead
# of silently dropping them.
_MODELED_M_FUNCTIONS = frozenset({0, 1, 2, 3, 4, 5, 6, 8, 9, 13, 14, 30, 89, 90, 91, 99, 140})


def _unsupported(message):
    raise SemanticError("UNSUPPORTED_HEIDENHAIN_EXECUTION", message, "unsupported")


@dataclass
class _State:
    position: tuple[float, float, float]
    offset: tuple[float, float, float]
    wcs_offsets: dict = field(default_factory=dict)
    frame: CoordinateTransform = field(default_factory=lambda: CoordinateTransform(spatial_rotation=IDENTITY))
    local_shift: tuple = (0.0, 0.0, 0.0)
    rotation_degrees: float = 0.0
    home: tuple = (0.0, 0.0, 0.0)
    emulate_home: bool = False
    tool_axis_declared: bool = False
    home_retract_warned: bool = False
    scale: float = 1.0
    feed: float | None = None
    rapid: bool = True
    tool: str | None = None
    spindle_axis: str = "Z"
    plane: int = 17
    spindle_rpm: float | None = None
    spindle_running: bool = False
    center: tuple[float, float, float] | None = None
    tolerance_warned: bool = False
    arc_tolerance: float = 0.01
    ended: str | None = None
    compensation_mode: int = 40
    clockwise: bool = False
    cycle_code: int | None = None
    cycle_modal: bool = False
    polar_angle: float = 0.0
    polar_radius: float = 0.0
    parameters: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)
    program: Any = None
    pc: int = 0
    cycle_subvalues: dict = field(default_factory=dict)
    cycle_rapid_parameters: set[str] = field(default_factory=set)
    motions: list = field(default_factory=list)
    trace_motions: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    events: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    def controls(self, syntax, values, block):
        codes = tuple(scalar(function.code, self.parameters) for function in syntax.machine_functions)
        unsupported = {word.address for word in syntax.positioning_words} - {
            "X",
            "Y",
            "Z",
            "IX",
            "IY",
            "IZ",
            "F",
            "FMAX",
            "S",
            "M",
            "R0",
            "RL",
            "RR",
            "FAUTO",
            "PA",
            "IPA",
            "PR",
            "IPR",
            "DR+",
            "DR-",
            "R",
            "LEN",
            "CCA",
        }
        if unsupported:
            _unsupported("Unsupported Klartext addresses: " + ", ".join(sorted(unsupported)))
        self.feed_controls(syntax, values, block)
        self.modal_controls(syntax)
        self.spindle_control(values)
        for code in codes:
            self.machine_function(int(code), block)
        return 91 in codes

    def feed_controls(self, syntax, values, block):
        addresses = {word.address for word in syntax.positioning_words}
        if syntax.kind in {"motion", "contour"}:
            self.rapid = False
        if "F" in values:
            if values["F"] < 0:
                raise SemanticError("INVALID_FEED", "Klartext feed must be nonnegative")
            if values["F"] == 0:
                self.diagnostics.append(
                    Diagnostic(
                        "HEIDENHAIN_ZERO_FEED",
                        "F0: geometric path retained; feed duration is undefined",
                        "warning",
                        "unverified",
                        block.index + 1,
                        block.raw,
                    )
                )
            self.feed, self.rapid = values["F"] * self.scale, False
        if "FMAX" in addresses:
            self.rapid = True
        if "FAUTO" in addresses:
            self.rapid = False

    def modal_controls(self, syntax):
        for address, mode in (("R0", 40), ("RL", 41), ("RR", 42)):
            if syntax.word(address) is not None:
                self.compensation_mode = mode
        if syntax.word("DR+") is not None:
            self.clockwise = False
        if syntax.word("DR-") is not None:
            self.clockwise = True

    def spindle_control(self, values):
        if "S" in values:
            if values["S"] < 0:
                raise SemanticError("INVALID_SPINDLE_SPEED", "Spindle speed must be nonnegative")
            self.spindle_rpm = values["S"]

    def machine_function(self, code, block):
        if code not in _MODELED_M_FUNCTIONS:
            _unsupported(f"Klartext M function is parsed but not executable: M{code}")
        if code in {3, 4, 13, 14, 5}:
            self.spindle_running = code != 5
        if code in {2, 30}:
            self.ended = f"M{code}"
            self.events.append(ExecutionEvent("program_end", block.index, self.ended))
        if code == 89:
            self.cycle_modal = True
        elif code in {90, 99}:
            self.cycle_modal = False
        kinds = {
            0: "stop",
            1: "optional_stop",
            3: "spindle_cw",
            4: "spindle_ccw",
            5: "spindle_stop",
            8: "coolant_flood",
            9: "coolant_off",
            13: "spindle_cw",
            14: "spindle_ccw",
        }
        if code in kinds:
            self.signals.append(MachineSignal(kinds[code], block.index, f"M{code}"))
        elif code not in {2, 30, 89, 90, 91, 99, 140}:
            self.signals.append(MachineSignal("machine_function", block.index, f"M{code}"))

    def target(self, values, *, machine=False):
        if machine:
            if any("I" + axis in values for axis in "XYZ"):
                _unsupported("Incremental coordinates with M91 are not modeled")
            target = list(self.machine(self.position))
            for index, axis in enumerate("XYZ"):
                if axis in values:
                    target[index] = values[axis] * self.scale
            return self.programmed(tuple(target))
        target = list(self.position)
        for index, axis in enumerate("XYZ"):
            if axis in values:
                target[index] = values[axis] * self.scale
            elif "I" + axis in values:
                target[index] += values["I" + axis] * self.scale
        return tuple(target)

    def motion(self, syntax, values, block, machine):
        if syntax.command not in {"L", "LP", "C", "CR", "CP", "CT"}:
            _unsupported("Klartext motion is parsed but not executable: " + syntax.command)
        target = self.target(values, machine=machine)
        if syntax.command in {"C", "CR", "CT"}:
            explicit_axes = frozenset(axis for axis in "XYZ" if axis in values or "I" + axis in values)
            self.plane = {frozenset("XY"): 17, frozenset("XZ"): 18, frozenset("YZ"): 19}.get(explicit_axes, self.plane)
        plane = self.plane
        axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}[plane]
        turns = 0
        if syntax.command in {"LP", "CP"}:
            target, turns = self.polar_target(syntax, values, target, axes)
        move, radius, delta = (0 if self.rapid else 1), None, (None, None, None)
        if syntax.command in {"C", "CR", "CP", "CT"}:
            if machine:
                _unsupported("Circular M91 positioning is not modeled")
            clockwise = self.clockwise
            move = 2 if clockwise != (plane == 18) else 3
            if syntax.command == "CR":
                radius = values["R"] * self.scale
            elif syntax.command == "CT":
                delta, clockwise = self.tangent_center(target, axes)
                move = 2 if clockwise != (plane == 18) else 3
            else:
                if self.center is None:
                    raise SemanticError("MISSING_HEIDENHAIN_CENTER", "C requires an executed CC definition")
                delta = tuple(self.center[i] - self.position[i] if i in axes else 0.0 for i in range(3))
        if target == self.position and move not in {2, 3}:
            return
        motion = TraceMotion(
            move,
            self.position[0],
            self.position[2],
            target[0],
            target[2],
            radius,
            feed=self.feed,
            start_y=self.position[1],
            end_y=target[1],
            i=delta[0],
            j=delta[1],
            k=delta[2],
            plane=plane,
            tool=self.tool,
            source_block=block.index,
            source_nlabel=block.nlabel,
            source_raw=block.raw,
            source_arc_type=1,
            spindle_rpm=self.spindle_rpm,
            spindle_running=self.spindle_running,
            compensation_mode=self.compensation_mode,
            additional_turns=turns,
        )
        # Validate before advancing state so invalid geometry preserves the valid prefix.
        motion = resolve_arc(motion, source_arc_type=1, tolerance=self.arc_tolerance)
        checkpoint("generated_motions")
        self.record_motion(motion)
        self.position = target

    def polar_target(self, syntax, values, target, axes):
        if self.center is None:
            raise SemanticError("MISSING_HEIDENHAIN_CENTER", "Polar motion requires CC")
        a, b = axes
        start_angle = math.degrees(math.atan2(self.position[b] - self.center[b], self.position[a] - self.center[a]))
        if syntax.command == "CP":
            radius = math.hypot(self.position[a] - self.center[a], self.position[b] - self.center[b])
            angle = values.get("PA", start_angle + values.get("IPA", 0.0))
        else:
            radius = values.get("PR", self.polar_radius / self.scale) * self.scale
            radius += values.get("IPR", 0.0) * self.scale
            angle = values.get("PA", self.polar_angle + values.get("IPA", 0.0))
        self.polar_angle, self.polar_radius = angle, radius
        point = list(target)
        point[a] = self.center[a] + radius * math.cos(math.radians(angle))
        point[b] = self.center[b] + radius * math.sin(math.radians(angle))
        sweep = abs(values.get("IPA", angle - start_angle))
        turns = max(0, int(math.ceil(sweep / 360 - 1e-10)) - 1)
        return tuple(point), turns

    def tangent_center(self, target, axes):
        a, b = axes
        previous = next(
            (
                motion
                for motion in reversed(self.trace_motions)
                if motion.arc is not None
                and motion.arc.plane == self.plane
                or math.hypot(
                    (motion.end_x, motion.end_y, motion.end_z)[a] - (motion.start_x, motion.start_y, motion.start_z)[a],
                    (motion.end_x, motion.end_y, motion.end_z)[b] - (motion.start_x, motion.start_y, motion.start_z)[b],
                )
                > 1e-12
            ),
            None,
        )
        if previous is None:
            raise SemanticError("MISSING_HEIDENHAIN_TANGENT", "CT requires a preceding contour motion")
        start = self.machine(self.position)
        target = self.machine(target)
        if previous.arc is not None:
            radial = (start[a] - previous.arc.center[a], start[b] - previous.arc.center[b])
            tangent = (radial[1], -radial[0]) if previous.arc.clockwise else (-radial[1], radial[0])
        else:
            before = (previous.start_x, previous.start_y, previous.start_z)
            tangent = (start[a] - before[a], start[b] - before[b])
        normal = (-tangent[1], tangent[0])
        chord = (target[a] - start[a], target[b] - start[b])
        denominator = 2 * (chord[0] * normal[0] + chord[1] * normal[1])
        if abs(denominator) <= 1e-12:
            raise SemanticError("INVALID_HEIDENHAIN_TANGENT", "CT tangent and endpoint cannot define a circle")
        factor = (chord[0] ** 2 + chord[1] ** 2) / denominator
        delta = [0.0, 0.0, 0.0]
        delta[a], delta[b] = normal[0] * factor, normal[1] * factor
        return transform_vector(transpose(self.frame.spatial_rotation), tuple(delta)), factor < 0

    def machine(self, point):
        return self.frame.apply(point)

    def programmed(self, point):
        return self.frame.inverse(point)

    def change_frame(self, *, offset=None, shift=None, degrees=None):
        """Change coordinates while keeping the machine position and CC center fixed."""
        machine = self.machine(self.position)
        center = self.machine(self.center) if self.center is not None else None
        self.offset = self.offset if offset is None else offset
        self.local_shift = self.local_shift if shift is None else shift
        self.rotation_degrees = self.rotation_degrees if degrees is None else degrees
        self.frame = CoordinateTransform(
            translation=tuple(self.offset[i] + self.local_shift[i] for i in range(3)),
            spatial_rotation=rotation((0.0, 0.0, 1.0), self.rotation_degrees),
        )
        self.position = self.programmed(machine)
        if center is not None:
            self.center = self.programmed(center)

    def record_motion(self, motion):
        """Keep contour geometry in work coordinates and publish a machine-space trace."""
        if motion.arc is not None and motion.plane != 17 and self.rotation_degrees % 360 != 0:
            _unsupported("Cycle 10 rotated circular motion currently supports the XY plane only")
        self.motions.append(motion)
        start = self.machine((motion.start_x, motion.start_y, motion.start_z))
        end = self.machine((motion.end_x, motion.end_y, motion.end_z))
        arc = replace(motion.arc, center=self.machine(motion.arc.center)) if motion.arc is not None else None
        vector = (motion.i, motion.j, motion.k)
        if arc is not None and any(value is not None for value in vector):
            vector = self.frame.apply_vector(tuple(value or 0.0 for value in vector))
        self.trace_motions.append(
            replace(
                motion,
                start_x=start[0],
                start_y=start[1],
                start_z=start[2],
                end_x=end[0],
                end_y=end[1],
                end_z=end[2],
                arc=arc,
                i=vector[0],
                j=vector[1],
                k=vector[2],
                orientation_offset=self.frame.translation,
            )
        )

    def select_datum(self, number, block):
        """Map preset entries 1..6 onto the application's configured G54..G59 table."""
        if not number.is_integer() or not 1 <= number <= 6:
            _unsupported("Cycle 247 Q339 supports preset entries 1..6 mapped to G54..G59")
        code = 53 + int(number)
        offset = tuple(self.wcs_offsets.get(code, (0.0, 0.0, 0.0)))
        self.change_frame(offset=offset)
        self.events.append(ExecutionEvent("wcs_change", block.index, f"G{code}"))

    def linear(self, target, block, *, move=0, feed=None, cycle=False):
        if target == self.position:
            return
        checkpoint("generated_motions")
        self.record_motion(
            TraceMotion(
                move,
                self.position[0],
                self.position[2],
                target[0],
                target[2],
                start_y=self.position[1],
                end_y=target[1],
                feed=feed,
                tool=self.tool,
                plane=self.plane,
                cycle_generated=cycle,
                source_block=block.index,
                source_nlabel=block.nlabel,
                source_raw=block.raw,
                compensation_mode=self.compensation_mode,
                spindle_rpm=self.spindle_rpm,
                spindle_running=self.spindle_running,
                source_arc_type=1,
            )
        )
        self.position = tuple(target)

    def arc_motion(self, target, block, *, move, plane, delta, feed=None, cycle=False):
        motion = TraceMotion(
            move,
            self.position[0],
            self.position[2],
            target[0],
            target[2],
            start_y=self.position[1],
            end_y=target[1],
            feed=feed,
            i=delta[0],
            j=delta[1],
            k=delta[2],
            tool=self.tool,
            plane=plane,
            cycle_generated=cycle,
            source_block=block.index,
            source_nlabel=block.nlabel,
            source_raw=block.raw,
            source_arc_type=1,
            compensation_mode=self.compensation_mode,
        )
        motion = resolve_arc(motion, source_arc_type=1, tolerance=self.arc_tolerance)
        checkpoint("generated_motions")
        self.record_motion(motion)
        self.position = tuple(target)

    def tool_call(self, syntax, block):
        if syntax.tool is None:
            tool = self.tool
        elif isinstance(syntax.tool, str):
            tool = syntax.tool
        else:
            number = scalar(syntax.tool, self.parameters)
            if number < 0 or not number.is_integer():
                raise SemanticError("INVALID_TOOL", "TOOL CALL requires a nonnegative integer or name")
            tool = f"T{int(number)}"
        if syntax.tool is not None:
            self.events.append(
                ExecutionEvent("tool_change", block.index, "TOOL CALL", tool=tool, previous_tool=self.tool)
            )
        self.tool = tool
        if syntax.spindle_axis:
            self.tool_axis_declared = True
            self.spindle_axis = syntax.spindle_axis
            self.plane = _PLANES[self.spindle_axis][0]
            self.center = None

    def cycle(self, syntax, values, block):
        if syntax.cycle_code in {7, 10} and syntax.command == "CYCL DEF":
            self.coordinate_cycle(syntax, values, block)
            return
        if syntax.command.startswith("CYCL CALL"):
            self.controls(syntax, values, block)
            if syntax.command == "CYCL CALL POS":
                self.linear(self.target(values), block, move=0 if self.rapid else 1, feed=self.feed)
            execute_cycle(self, block)
            return
        if syntax.cycle_code == 247:
            if {parameter.name for parameter in syntax.cycle_parameters} != {"Q339"}:
                raise SemanticError("INVALID_HEIDENHAIN_DATUM", "Cycle 247 requires only Q339 preset selection")
            return
        if syntax.cycle_code not in DRILLING_CYCLES | {9, 32}:
            raise SemanticError(
                "UNSUPPORTED_HEIDENHAIN_CYCLE",
                f"Cycle {syntax.cycle_code} has no execution implementation; its effect cannot be ignored",
                "unsupported",
            )
        if syntax.cycle_code != 32:
            self.define_cycle(syntax, values)
            return
        if values.get("T", 0) < 0:
            raise SemanticError("INVALID_HEIDENHAIN_TOLERANCE", "Cycle 32 tolerance must be nonnegative")
        if not self.tolerance_warned:
            self.diagnostics.append(
                Diagnostic(
                    "HEIDENHAIN_SMOOTHING_NOT_SIMULATED",
                    "Cycle 32 is retained as metadata; the plot shows the programmed "
                    "contour without controller smoothing",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                )
            )
            self.tolerance_warned = True

    def coordinate_cycle(self, syntax, values, block):
        if syntax.cycle_parameters:
            _unsupported("Coordinate cycles 7/10 require axis/ROT subdefinitions, not Q cycle parameters")
        if syntax.cycle_subcode in {None, 0}:
            return
        if syntax.cycle_code == 7:
            if not values:
                raise SemanticError("INVALID_HEIDENHAIN_DATUM", "Cycle 7 requires a datum-shift axis")
            shift = list(self.local_shift)
            for index, axis in enumerate("XYZ"):
                if axis in values:
                    shift[index] = values[axis] * self.scale
                elif "I" + axis in values:
                    shift[index] += values["I" + axis] * self.scale
            self.change_frame(shift=tuple(shift))
        else:
            if "ROT" not in values:
                raise SemanticError("INVALID_HEIDENHAIN_ROTATION", "Cycle 10 requires ROT angle")
            self.change_frame(degrees=values["ROT"])
        self.events.append(ExecutionEvent("coordinate_transform", block.index, f"CYCL {syntax.cycle_code}"))

    def define_cycle(self, syntax, values):
        """Keep drilling definitions separate from datum selection and smoothing."""
        if syntax.cycle_subcode in {None, 0}:
            self.cycle_code = syntax.cycle_code
            self.cycle_subvalues.clear()
            self.cycle_rapid_parameters.clear()
        else:
            self.cycle_subvalues[syntax.cycle_subcode] = values.get("VALUE", 0.0)
            aliases = {1: {1: 200, 2: 201, 3: 202, 4: 211, 5: 206}, 2: {1: 200, 2: 201, 3: 211, 4: 206}}
            number = aliases.get(syntax.cycle_code, {}).get(syntax.cycle_subcode)
            if number is not None:
                self.parameters[f"Q{number}"] = values.get("VALUE", 0.0)

    def block(self, block, syntax):
        if not isinstance(syntax, HeidenhainSyntax):
            raise SemanticError("INVALID_HEIDENHAIN_AST", "Execution requires a native Klartext AST")
        values = {
            word.address: scalar(word.expression, self.parameters)
            for word in syntax.positioning_words
            if word.expression is not None
        }
        for warning in syntax.warnings:
            self.diagnostics.append(
                Diagnostic("HEIDENHAIN_PROGRAM_METADATA", warning, "warning", "unverified", block.index + 1, block.raw)
            )
        self.dispatch_block(syntax, values, block)
        return values

    def dispatch_block(self, syntax, values, block):
        if syntax.kind in {"empty", "comment", "stock", "label"} or syntax.command == "TOOL DEF":
            return
        handlers = {
            "program": self.program_block,
            "cycle": self.cycle,
            "parameter": self.parameter_block,
            "contour": self.contour_block,
            "motion": self.position_block,
            "center": self.position_block,
            "control": self.position_block,
            "tool": self.position_block,
        }
        handler = handlers.get(syntax.kind)
        if handler is None:
            _unsupported("Klartext command is parsed but not executable: " + syntax.command)
        handler(syntax, values, block)

    def program_block(self, syntax, _values, _block):
        if syntax.units is not None:
            self.scale = 25.4 if syntax.units == "INCH" else 1.0

    def parameter_block(self, syntax, _values, _block):
        if syntax.assignment is not None:
            name, expression = syntax.assignment
            if expression.kind == "cycle_feed":
                if syntax.cycle_code not in {202, 203}:
                    _unsupported(f"Cycle {syntax.cycle_code} does not support {name}=MAX")
                self.cycle_rapid_parameters.add(name)
                self.parameters.pop(name, None)
                return
            self.cycle_rapid_parameters.discard(name)
            self.parameters[name] = scalar(expression, self.parameters)
            if syntax.cycle_code == 247 and name == "Q339":
                self.select_datum(self.parameters[name], _block)

    def contour_block(self, syntax, values, block):
        if not syntax.command.startswith(("APPR ", "DEP ")):
            _unsupported("Klartext command is parsed but not executable: " + syntax.command)
        entry_move, entry_feed = (0 if self.rapid else 1), self.feed
        self.controls(syntax, values, block)
        approach_departure(self, syntax, values, block, entry_move=entry_move, entry_feed=entry_feed)

    def position_block(self, syntax, values, block):
        machine = self.controls(syntax, values, block)
        self.retract_tool(syntax, block, machine=machine)
        if syntax.kind == "tool":
            self.tool_call(syntax, block)
        elif syntax.kind == "center":
            self.center = self.target(values)
            axes = frozenset(axis[-1] for axis in values if axis[-1:] in "XYZ")
            self.plane = {frozenset("XY"): 17, frozenset("XZ"): 18, frozenset("YZ"): 19}.get(axes, self.plane)
        elif syntax.kind == "motion":
            self.motion(syntax, values, block, machine)
            call = any(int(scalar(function.code, self.parameters)) == 99 for function in syntax.machine_functions)
            positioned = any(axis in values or "I" + axis in values for axis in "XYZ")
            if call or (self.cycle_modal and positioned):
                execute_cycle(self, block)

    def retract_tool(self, syntax, block, *, machine):
        for function in syntax.machine_functions:
            if scalar(function.code, self.parameters) != 140:
                continue
            if not self.tool_axis_declared:
                _unsupported("M140 requires a preceding TOOL CALL with an explicit tool axis")
            if machine or (syntax.kind == "motion" and syntax.command != "L"):
                _unsupported("M140 is supported only in straight work-coordinate positioning blocks")
            parameters = {word.address: word for word in function.parameters}
            # The application's M140 preview models a vertical three-axis machine.
            axis = 2
            target = list(self.position)
            if "MB MAX" in parameters:
                target[axis] = self.home_retract_target(axis, block)
            elif "MB" in parameters:
                target[axis] += scalar(parameters["MB"].expression, self.parameters) * self.scale
            else:
                raise SemanticError("INVALID_HEIDENHAIN_RETRACT", "M140 requires MB distance or MB MAX")
            feed = self.retraction_feed(parameters)
            self.linear(tuple(target), block, move=0 if feed is None else 1, feed=feed)
            self.signals.append(MachineSignal("tool_axis_retract", block.index, "M140"))

    def retraction_feed(self, parameters):
        if "FAUTO" in parameters:
            _unsupported("M140 FAUTO retraction feed is not modeled")
        if "F" not in parameters:
            return None
        feed = scalar(parameters["F"].expression, self.parameters) * self.scale
        if feed <= 0:
            raise SemanticError("INVALID_FEED", "M140 retraction feed must be positive")
        return feed

    def home_retract_target(self, axis, block):
        if not self.emulate_home:
            _unsupported("M140 MB MAX requires configured Home emulation; machine travel limits are unavailable")
        if not self.home_retract_warned:
            self.diagnostics.append(
                Diagnostic(
                    "HEIDENHAIN_M140_HOME_EMULATION",
                    "M140 MB MAX is previewed using the configured machine Home, not a physical travel limit; "
                    "only positive machine-Z retraction is modeled for the vertical three-axis machine",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                )
            )
            self.home_retract_warned = True
        return max(self.position[axis], self.home[axis] - self.frame.translation[axis])


@dataclass
class _Flow:
    program: Any
    state: _State
    calls: list = field(default_factory=list)
    repetitions: dict = field(default_factory=dict)

    def label(self, syntax):
        if syntax.label_expression is None:
            return syntax.label
        value = scalar(syntax.label_expression, self.state.parameters)
        if not value.is_integer():
            raise SemanticError("INVALID_HEIDENHAIN_LABEL", "A computed label must be an integer")
        return int(value)

    def jump(self, label):
        target = self.program.ast.heidenhain_label_to_index.get(label)
        if target is None:
            raise SemanticError("UNDEFINED_HEIDENHAIN_LABEL", f"Undefined Klartext label: {label}")
        return target + 1

    def local_parameters(self):
        return {name: value for name, value in self.state.parameters.items() if name.startswith("QL")}

    def restore_locals(self, values):
        for name in tuple(self.state.parameters):
            if name.startswith("QL"):
                del self.state.parameters[name]
        self.state.parameters.update(values)

    def advance(self, pc, syntax):
        if syntax.kind != "label":
            return pc + 1
        label = self.label(syntax)
        if syntax.condition is not None:
            return self.jump(label) if scalar(syntax.condition, self.state.parameters) else pc + 1
        if syntax.command == "LBL":
            return self.return_label(pc, label)
        if syntax.command != "CALL LBL":
            return pc + 1
        return self.call_label(pc, syntax, label)

    def return_label(self, pc, label):
        if label != 0 or not self.calls:
            return pc + 1
        return_pc, target, remaining, locals_before = self.calls.pop()
        self.restore_locals(locals_before)
        if remaining:
            self.calls.append((return_pc, target, remaining - 1, locals_before))
            self.restore_locals({})
            return target
        return return_pc

    def call_label(self, pc, syntax, label):
        target = self.jump(label)
        repetitions = 1
        if syntax.repeat is not None:
            value = scalar(syntax.repeat, self.state.parameters)
            if value < 0 or not value.is_integer():
                raise SemanticError("INVALID_HEIDENHAIN_REPEAT", "REP requires a nonnegative integer")
            repetitions = int(value)
            if target <= pc:
                return self.repeat_section(pc, target, repetitions)
        if repetitions == 0:
            return pc + 1
        checkpoint("subprogram_calls")
        budget = active_budget.get()
        if budget is not None and len(self.calls) >= budget.limits.call_depth:
            raise SemanticError("RESOURCE_LIMIT", "Klartext call depth limit exceeded", "resource_limit")
        self.calls.append((pc + 1, target, repetitions - 1, self.local_parameters()))
        self.restore_locals({})
        return target

    def repeat_section(self, pc, target, repetitions):
        key = (pc, len(self.calls))
        remaining = self.repetitions.get(key, repetitions)
        if not remaining:
            self.repetitions.pop(key, None)
            return pc + 1
        checkpoint("macro_iterations")
        self.repetitions[key] = remaining - 1
        return target


def execute_heidenhain(
    source,
    *,
    parsed_program=None,
    default_unit_scale=1.0,
    home=(0.0, 0.0, 0.0),
    emulate_home=False,
    wcs_offsets=None,
    skip_optional_blocks=False,
    tool_resolver=None,
    include_instructions=True,
    arc_tolerance=0.01,
):
    """Publish the native three-axis trace through the shared kernel contracts."""
    offset = tuple((wcs_offsets or {}).get(54, (0.0, 0.0, 0.0)))
    state = _State(
        tuple(home[i] - offset[i] for i in range(3)),
        offset,
        wcs_offsets=dict(wcs_offsets or {}),
        frame=CoordinateTransform(translation=offset, spatial_rotation=IDENTITY),
        home=home,
        emulate_home=emulate_home,
        scale=default_unit_scale,
        arc_tolerance=arc_tolerance,
    )
    program = None
    block = None
    failed = False
    try:
        program = parsed_program if parsed_program is not None else parse_heidenhain_program(source)
        state.program = program
        declared_units = next(
            (
                node.native_syntax.units
                for node in program.ast.nodes
                if node.native_syntax.kind == "program" and node.native_syntax.units is not None
            ),
            None,
        )
        if declared_units is not None:
            state.scale = 25.4 if declared_units == "INCH" else 1.0
        if tool_resolver is not None:
            state.tools = tool_resolver(program) or {}
        flow = _Flow(program, state)
        pc = 0
        occurrence = {}
        while 0 <= pc < len(program.blocks):
            block = program.blocks[pc]
            state.pc = pc
            checkpoint("executed_blocks")
            if block.optional_skip and skip_optional_blocks:
                pc += 1
                continue
            count, event_count, signal_count = len(state.motions), len(state.events), len(state.signals)
            syntax = program.ast.nodes[pc].native_syntax
            values = state.block(block, syntax)
            state.steps.append(
                ExecutionStep(
                    block.index,
                    len(state.motions) - count,
                    unit_scale=state.scale,
                    x_is_diameter=False,
                    words=tuple(values.items()),
                    position=state.machine(state.position),
                    programmed_position=state.position,
                    spindle_rpm=state.spindle_rpm,
                    spindle_running=state.spindle_running,
                    modal_move=state.motions[-1].move if state.motions else 0,
                    events=tuple(state.events[event_count:]),
                    signals=tuple(state.signals[signal_count:]),
                    occurrence=occurrence.get(block.index, 0),
                    variables=tuple(sorted(state.parameters.items())),
                )
            )
            occurrence[block.index] = occurrence.get(block.index, 0) + 1
            if state.ended is not None:
                break
            pc = flow.advance(pc, syntax)
    except Exception as exc:
        diagnostic = diagnostic_from_exception(exc, program)
        if diagnostic.line is None and block is not None:
            diagnostic = replace(diagnostic, line=block.index + 1, raw=block.raw)
        state.diagnostics.append(diagnostic)
        failed = True
    return ExecutionResult(
        ok=not failed,
        program=program,
        instructions=semantic_instructions(program) if include_instructions else (),
        motions=tuple(state.trace_motions),
        diagnostics=tuple(state.diagnostics),
        executed_blocks=tuple(step.source_block for step in state.steps),
        complete=not failed,
        language="fanuc_mill",
        source_dialect="heidenhain",
        execution_steps=tuple(state.steps),
        events=tuple(state.events),
        signals=tuple(state.signals),
        program_end=state.ended,
    )
