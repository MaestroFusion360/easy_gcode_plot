"""Siemens turning cycle expansion from typed native positional arguments.

Classic interfaces: Siemens 840D PGK 10/2000; CYCLE93/95 also follow Siemens
808D Turning 09/2017 compatibility-cycle parameter descriptions. Unsupported
technology variants fail before emitting their geometry.
"""

import math
from types import SimpleNamespace

from ..frontend.model import Point2
from ..milling.cycles.sinumerik import _native_axial_moves, compile_native_cycle
from ..resources import SemanticError, checkpoint
from ..types import ExecutionEvent, MachineSignal
from .sinumerik_roughing import roughing_cycle
from .sinumerik_state import unsupported
from .sinumerik_values import arguments, integer, nonnegative, positive


def execute_cycle(state, syntax, block):
    if state.cutter_comp != 40:
        unsupported("Native turning cycles require G40", "UNSUPPORTED_SINUMERIK_CYCLE")
    count = len(state.motions)
    if syntax.cycle_code == 95:
        roughing_cycle(state, syntax, block)
    elif syntax.cycle_code == 97:
        threading_cycle(state, syntax, block)
    elif syntax.cycle_code == 93:
        grooving_cycle(state, syntax, block)
    elif syntax.cycle_code in {81, 82, 83, 84, 85, 89}:
        drilling_cycle(state, syntax, block)
    else:
        unsupported(f"CYCLE{syntax.cycle_code} is not implemented for turning", "UNSUPPORTED_SINUMERIK_CYCLE")
    state.events.append(ExecutionEvent("cycle_call", block.index, f"CYCLE{syntax.cycle_code}"))
    if len(state.motions) == count:
        raise SemanticError("INVALID_SINUMERIK_CYCLE", "Cycle generated no machining geometry")


def threading_cycle(state, syntax, block):
    pit, mpit, spl, fpl, dm1, dm2, app, rop, depth, allowance, angle, phase, passes, idle, variant, starts = arguments(
        state, syntax, 16, 16
    )
    positive(pit, dm1, dm2, depth)
    nonnegative(app, rop, allowance)
    passes, idle = integer(passes, 1, 10000, "NRC"), integer(idle, 0, 10000, "NID")
    variant = integer(variant, 1, 4, "VARI")
    if any((mpit, angle, phase, starts != 1, spl == fpl, allowance >= depth)):
        unsupported(
            "CYCLE97 currently requires explicit PIT, IANG=NSP=0, NUMTH=1, FAL<TDEP and a longitudinal thread",
            "UNSUPPORTED_SINUMERIK_CYCLE",
        )
    if state.spindle_mode != "rpm" or not state.spindle_running or not state.spindle_rpm:
        unsupported("CYCLE97 requires a running spindle with fixed positive RPM (G97)", "UNSUPPORTED_SINUMERIK_CYCLE")
    scale = state.unit_scale
    sign = 1 if fpl > spl else -1
    start_z, end_z = (spl - sign * app) * scale, (fpl + sign * rop) * scale
    slope = (dm2 - dm1) / (2 * (fpl - spl))
    start_x = (dm1 / 2 - sign * app * slope) * scale
    end_x = (dm2 / 2 + sign * rop * slope) * scale
    side = 1 if variant in {2, 4} else -1
    layers = [
        (depth - allowance) * (math.sqrt(i / passes) if variant in {3, 4} else i / passes) * scale
        for i in range(1, passes + 1)
    ]
    if allowance:
        layers.append(depth * scale)
    layers.extend([depth * scale] * idle)
    origin = state.position
    safe = max(origin.x, start_x, end_x) + scale if side < 0 else min(origin.x, start_x, end_x) - scale
    state.signals.append(MachineSignal("spindle_sync", block.index, "CYCLE97", pit * scale))
    for layer in layers:
        checkpoint("cycle_iterations")
        state.emit(Point2(safe, state.position.z), block, cycle=True)
        state.emit(Point2(safe, start_z), block, cycle=True)
        state.emit(Point2(start_x + side * layer, start_z), block, cycle=True)
        state.emit(Point2(end_x + side * layer, end_z), block, move=1, feed=pit * scale, cycle=True, threading=True)
        state.emit(Point2(safe, end_z), block, cycle=True)
    state.emit(Point2(safe, origin.z), block, cycle=True)
    state.emit(origin, block, cycle=True)


def grooving_cycle(state, syntax, block):
    values = arguments(state, syntax, 16, 17)
    _, _, width, depth, angle, a1, a2, r1, r2, r3, r4, leave1, leave2, step, dwell, variant, retract = values
    positive(width, depth, step)
    nonnegative(leave1, leave2, dwell, retract)
    variant = integer(variant, 1, 18, "VARI") % 10
    if variant not in range(1, 9) or any((a1, a2, r1, r2, r3, r4)):
        unsupported(
            "CYCLE93 currently supports rectangular grooves without flank angles, radii or chamfers",
            "UNSUPPORTED_SINUMERIK_CYCLE",
        )
    longitudinal = bool(variant % 2)
    if angle not in ({0, 180} if longitudinal else {90}):
        unsupported("CYCLE93 supports axis-aligned grooves only", "UNSUPPORTED_SINUMERIK_CYCLE")
    tool = state.tools.get(state.tool, {})
    cutter_width = float(tool.get("width", 0))
    if (
        tool.get("type") != "groove"
        or not cutter_width
        or cutter_width > width * state.unit_scale
        or tool.get("noseRadius", 0)
        or not state.edge
    ):
        unsupported(
            "CYCLE93 requires active D and a configured square groove tool with valid width and zero corner radius",
            "UNSUPPORTED_SINUMERIK_CYCLE",
        )
    if not state.feed or leave1 >= depth or 2 * leave2 + cutter_width / state.unit_scale > width:
        raise SemanticError("INVALID_SINUMERIK_CYCLE", "Invalid groove allowance, tool width or missing feed")
    _rectangular_groove(state, block, values, longitudinal, variant, cutter_width)


def _rectangular_groove(state, block, values, longitudinal, variant, cutter_width):
    spd, spl, width, depth, _, _, _, _, _, _, _, leave1, leave2, step, dwell, _, retract = values
    scale = state.unit_scale
    start = Point2(state.x_value(spd), spl * scale)
    width_sign = 1 if variant in ({1, 3} if longitudinal else {4, 8}) else -1
    depth_sign = (-1 if variant in {1, 5} else 1) if longitudinal else (1 if variant in {2, 4} else -1)

    def point(across, down):
        return Point2(
            start.x + (depth_sign * down if longitudinal else width_sign * across),
            start.z + (width_sign * across if longitudinal else depth_sign * down),
        )

    span = width * scale - cutter_width - 2 * leave2 * scale
    stations = math.ceil(span / (0.95 * cutter_width))
    levels = math.ceil((depth - leave1) / step)
    origin = state.position
    for index in range(stations + 1):
        across = leave2 * scale + span * index / max(1, stations)
        state.emit(point(across, -(retract or 1) * scale), block, cycle=True)
        for layer in range(1, levels + 1):
            checkpoint("cycle_iterations")
            down = (depth - leave1) * scale * layer / levels
            state.emit(point(across, down), block, move=1, feed=state.feed, cycle=True)
            state.emit(point(across, max(0, down - scale)), block, cycle=True)
        if dwell:
            state.signals.append(MachineSignal("dwell", block.index, "CYCLE93", dwell))
        state.emit(point(across, -(retract or 1) * scale), block, cycle=True)
    # Final walls and base, using the selected first cutting edge as reference.
    state.emit(point(0, 0), block, cycle=True)
    state.emit(point(0, depth * scale), block, move=1, feed=state.feed, cycle=True)
    state.emit(point(width * scale - cutter_width, depth * scale), block, move=1, feed=state.feed, cycle=True)
    state.emit(point(width * scale - cutter_width, 0), block, move=1, feed=state.feed, cycle=True)
    state.emit(point(width * scale - cutter_width, -(retract or 1) * scale), block, cycle=True)
    state.emit(origin, block, cycle=True)


def drilling_cycle(state, syntax, block):
    if abs(state.position.x) > 1e-9:
        unsupported("Turning drilling cycles require the spindle centerline X0", "UNSUPPORTED_SINUMERIK_CYCLE")
    adapted = SimpleNamespace(
        plane=17,
        cutter_comp=40,
        cycle=80,
        unit_scale=state.unit_scale,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
        siemens_parameters=state.siemens_parameters,
        siemens_variables=state.siemens_variables,
        sinumerik_840d_sl=state.sinumerik_840d_sl,
    )
    cycle = compile_native_cycle(syntax, adapted)
    moves = _native_axial_moves(cycle, adapted)
    if moves is None:
        from ..machine.drilling import AxialMove  # pylint: disable=import-outside-toplevel

        moves = (AxialMove(1, cycle.safety_z, cycle.target_z), AxialMove(0, cycle.target_z, cycle.return_z))
    state.emit(Point2(0, cycle.return_z), block, cycle=True)
    state.emit(Point2(0, cycle.safety_z), block, cycle=True)
    for index, move in enumerate(moves):
        feed = cycle.tapping_feed or cycle.cutting_feed or state.feed
        if cycle.code == 84 and feed:
            feed /= cycle.tapping_rpm
        elif move.move and move.end > move.start and cycle.retract_feed:
            feed = cycle.retract_feed
        if index == 0 and feed:
            feed *= cycle.feed_factor
        state.emit(
            Point2(0, move.end),
            block,
            move=move.move,
            feed=feed if move.move else None,
            cycle=True,
            threading=cycle.code == 84 and move.move == 1,
        )
    if cycle.dwell:
        state.signals.append(MachineSignal("dwell", block.index, f"CYCLE{cycle.code}", cycle.dwell))
    if cycle.code == 84:
        state.signals.extend(
            MachineSignal(kind, block.index, "CYCLE84") for kind in ("rigid_tapping", "spindle_sync", "spindle_reverse")
        )
