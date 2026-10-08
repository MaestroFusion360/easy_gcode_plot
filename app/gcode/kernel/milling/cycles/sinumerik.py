"""Native modal CYCLE81/82/83/84 using the common drilling geometry emitter.

Positional parameters follow Siemens G-code programming manual 03/2009,
sections 1.2, 1.3, 1.5. Automatic CYCLE83 reentry clearance follows the
Siemens 808D ADVANCED milling manual 07/2018 (DIS1).
No text conversion or FANUC canned-cycle dispatch is used for native cycles.
"""

import math
import re
from dataclasses import dataclass, replace

from ...api.resources import SemanticError, checkpoint, require_progress
from ...api.types import MachineSignal
from ...frontend.ast import NativeMillingSyntax
from ...runtime.cycles import CycleOutcome
from ...runtime.drilling import AxialMove
from ..sinumerik_parameters import parameter_value
from ..state import _xyz
from .drilling import _DRILL_BEHAVIOR, _expand_drilling_cycle, _ResolvedDrillingCycle
from .events import drilling_event


@dataclass(frozen=True)
class NativeDrillingCycle:
    code: int
    return_z: float
    reference_z: float
    safety_z: float
    target_z: float
    first_depth: float | None = None
    degression: float = 0.0
    minimum_step: float = 0.0
    full_retract: bool = True
    retract_distance: float = 1.0
    clearance: float = 0.0
    feed_factor: float = 1.0
    dwell: float = 0.0
    tapping_feed: float | None = None
    tapping_rpm: float | None = None
    parameter_syntax: NativeMillingSyntax | None = None


def _unsupported(message):
    raise SemanticError("UNSUPPORTED_SINUMERIK_CYCLE", message, "unsupported")


def _arguments(syntax, parameters, variables=None, *, solution_line=True):
    count = {83: 20, 84: 24}.get(syntax.cycle_code, 9)
    maximum = count if solution_line else {81: 5, 82: 6, 83: 17, 84: 18}.get(syntax.cycle_code, 0)
    args = syntax.cycle_args
    trees = dict(syntax.scalar_expressions)
    # Some CAM calls omit DTB and end with AMODE=10/12. A shortened SL
    # declaration instead ends with DMODE, so its dwell must not be shifted.
    if (
        solution_line
        and syntax.cycle_code == 81
        and len(args) == 8
        and args[-1]
        and parameter_value(args[-1], parameters, variables, trees.get(args[-1])) in (10, 12)
    ):
        args = args[:5] + ("",) + args[5:]
    minimum = 4 if syntax.cycle_code == 81 else 5
    if syntax.cycle_code not in (81, 82, 83, 84) or not minimum <= len(args) <= maximum:
        generation = "840D Extended cycles (03/2009)" if solution_line else "classic (01/2008)"
        _unsupported(f"Cycle signature is outside the selected {generation} interface")
    values = tuple(parameter_value(arg, parameters, variables, trees.get(arg)) if arg else None for arg in args) + (
        None,
    ) * (count - len(args))
    if any(value is not None and not math.isfinite(value) for value in values):
        _unsupported("Cycle arguments must be finite numeric literals")
    if any(values[index] is None for index in (0, 1, 2)):
        _unsupported("RTP, RFP and SDIS must be specified")
    return values


def _depth(values, reference):
    if values[3] is not None:
        return values[3]
    if values[4] is not None and values[4] > 0:
        return reference - values[4]
    _unsupported("Specify absolute DP or positive relative DPR")


def _mode_checks(values, code, state):
    if state.plane != 17 or state.cutter_comp != 40 or state.cycle != 80:
        _unsupported("Native drilling requires G17, G40 and no active ISO canned cycle")
    if code == 84:
        return
    gmode, dmode, amode = (values[index] or 0 for index in ((17, 18, 19) if code == 83 else (6, 7, 8)))
    if gmode != 0 or dmode not in (0, 1) or amode not in ((0, 1001110) if code == 83 else (0, 2, 10, 12)):
        _unsupported("Cycle geometry/axis/alternative modes are outside the modeled subset")
    if code != 83 and amode in (2, 12) and values[3] is None:
        _unsupported("Absolute drilling mode requires explicit DP")


def compile_native_cycle(syntax, state):
    """Validate the complete declaration before committing modal cycle state."""
    cycle = _compile_native_cycle(syntax, state)
    if any(re.search(r"\bR\d+\b|_[A-Z][A-Z0-9_]*", arg, re.I) for arg in syntax.cycle_args):
        cycle = replace(cycle, parameter_syntax=syntax)
    return cycle


def _compile_native_cycle(syntax, state):
    values = _arguments(
        syntax, state.siemens_parameters, state.siemens_variables, solution_line=state.sinumerik_840d_sl
    )
    _mode_checks(values, syntax.cycle_code, state)
    rtp, rfp, sdis = values[:3]
    depth = _depth(values, rfp)
    if sdis < 0 or depth >= rfp or rtp < rfp + sdis:
        _unsupported("Modeled drilling requires downward depth and RTP at/above RFP+SDIS")
    scale = state.unit_scale
    common = {
        "code": syntax.cycle_code,
        "return_z": rtp * scale,
        "reference_z": rfp * scale,
        "safety_z": (rfp + sdis) * scale,
        "target_z": depth * scale,
    }
    if syntax.cycle_code == 83:
        return _compile_peck_cycle(values, common, scale)
    if syntax.cycle_code == 84:
        return _compile_tapping_cycle(values, common, state)
    dwell = values[5] or 0.0
    if dwell < 0:
        _unsupported("Dwell in spindle revolutions is not modeled")
    return NativeDrillingCycle(**common, dwell=dwell)


def _compile_tapping_cycle(values, common, state):
    """CAM subset of Siemens 03/2009 section 1.7: metric RH, one cut.

    SST is rpm, not feed. Keep cycle speeds equal to the programmed S so
    the shared execution-step spindle metadata remains authoritative.
    """
    if state.feed_mode != "per_minute" or state.unit_scale != 1:
        _unsupported("CYCLE84 currently requires metric geometry and G94")
    if (values[6] or 0) != 3 or (values[8] or 0) <= 0 or (values[13] or 0) not in (0, 1):
        _unsupported("CYCLE84 requires SDAC=3 and positive explicit PIT in mm (_PITA=0/1)")
    if (values[12] or 0) not in (0, 3) or (values[22] or 0) not in (0, 1):
        _unsupported("CYCLE84 requires Z tool axis and G17")
    if any(values[index] for index in (7, 9, 14, 15, 16, 17, 18, 19, 20, 21)):
        _unsupported("CYCLE84 thread tables, orientation, technology and deep tapping are not modeled")
    amode = values[23] or 0
    if amode not in (0, 2, 1001002) or amode and values[3] is None:
        _unsupported("CYCLE84 requires compatibility depth or the CAM absolute-depth/right-hand mode")
    rpm = values[10]
    retract_rpm = values[11] or rpm
    if rpm is None or rpm <= 0 or rpm != state.spindle_rpm or retract_rpm != rpm:
        _unsupported("CYCLE84 requires explicit positive SST matching S, with equal SST1 (or zero/omitted)")
    dwell = values[5] or 0
    if dwell < 0:
        _unsupported("CYCLE84 dwell must be in nonnegative seconds")
    feed = values[8] * rpm
    if not math.isfinite(feed):
        _unsupported("CYCLE84 calculated tapping feed must be finite")
    return NativeDrillingCycle(**common, dwell=dwell, tapping_feed=feed, tapping_rpm=rpm)


def _compile_peck_cycle(values, common, scale):
    first = values[5] if values[5] is not None else common["reference_z"] / scale - (values[6] or 0)
    dam, dtb, dts, factor, vari, axis, minimum, vrt, dtd, dis = (value or 0 for value in values[7:17])
    if first >= common["reference_z"] / scale or dam < 0 or vari not in (0, 1) or axis not in (0, 3):
        _unsupported("CYCLE83 requires positive amount degression, downward FDEP/FDPR and Z tool axis")
    if any(value < 0 for value in (minimum, vrt, dis)) or not 0 <= factor <= 1 or any((dtb, dts, dtd)):
        _unsupported("CYCLE83 dwell and the requested peck options are not modeled")
    return NativeDrillingCycle(
        **common,
        first_depth=first * scale,
        degression=dam * scale,
        minimum_step=minimum * scale,
        full_retract=bool(vari),
        retract_distance=(vrt or 1) * scale,
        clearance=dis * scale,
        feed_factor=factor or 1,
    )


def _peck_depths(cycle):
    step = cycle.reference_z - cycle.first_depth
    depth = max(cycle.first_depth, cycle.target_z)
    minimum = cycle.minimum_step or min(step, cycle.degression or step)
    while True:
        checkpoint("cycle_iterations")
        yield depth
        if depth <= cycle.target_z:
            return
        step = max(minimum, step - cycle.degression)
        next_depth = max(cycle.target_z, depth - step)
        require_progress(depth, next_depth)
        depth = next_depth


def _reentry(cycle, depth, scale):
    if not cycle.full_retract:
        return min(cycle.safety_z, depth + cycle.retract_distance)
    distance = cycle.clearance or min(7 * scale, max(0.6 * scale, (cycle.safety_z - depth) / 50))
    return min(cycle.safety_z, depth + distance)


def _peck_moves(cycle, scale):
    moves, position = [], cycle.safety_z
    for depth in _peck_depths(cycle):
        moves.append(AxialMove(1, position, depth))
        if depth == cycle.target_z:
            break
        retract = cycle.return_z if cycle.full_retract else _reentry(cycle, depth, scale)
        moves.append(AxialMove(0, depth, retract))
        position = _reentry(cycle, depth, scale)
        if position != retract:
            moves.append(AxialMove(0, retract, position))
    moves.append(AxialMove(0, cycle.target_z, cycle.return_z))
    return tuple(moves)


def execute_native_cycle(context):
    state = context.machine_state
    cycle = state.native_cycle
    if cycle is None or not any(axis in context.words for axis in ("X", "Y")):
        return CycleOutcome()
    if cycle.parameter_syntax is not None:
        cycle = _compile_native_cycle(cycle.parameter_syntax, state)
    x, y, _ = _xyz(context.words, state)
    resolved = _ResolvedDrillingCycle(
        x,
        y,
        cycle.safety_z,
        cycle.target_z,
        cycle.return_z,
        cycle.tapping_feed or state.feed,
        None,
        _DRILL_BEHAVIOR[81],
    )
    moves = _native_axial_moves(cycle, state)
    motions = _expand_drilling_cycle(context, state, resolved, axial_moves=moves)
    if cycle.code == 83 and motions:
        motions = _first_feed_factor(motions, cycle.feed_factor)
    signals = (MachineSignal("dwell", context.block.index, f"CYCLE{cycle.code}", cycle.dwell),) if cycle.dwell else ()
    if cycle.code == 84:
        signals += tuple(
            MachineSignal(kind, context.block.index, "CYCLE84")
            for kind in ("rigid_tapping", "spindle_sync", "spindle_reverse")
        )
    return CycleOutcome(
        True,
        motions,
        signals,
        position_update=(("x", x), ("y", y), ("z", cycle.return_z)),
        events=(drilling_event(context, state, resolved, motions, native=cycle),),
    )


def _native_axial_moves(cycle, state):
    if cycle.code == 83:
        return _peck_moves(cycle, state.unit_scale)
    if cycle.code != 84:
        return None
    if state.feed_mode != "per_minute" or state.spindle_rpm != cycle.tapping_rpm:
        _unsupported("CYCLE84 spindle speed/feed mode changed after declaration")
    return (
        AxialMove(1, cycle.safety_z, cycle.target_z),
        AxialMove(1, cycle.target_z, cycle.safety_z),
        AxialMove(0, cycle.safety_z, cycle.return_z),
    )


def _first_feed_factor(motions, factor):
    result, first = [], True
    for motion in motions:
        if motion.move == 1 and first:
            motion = replace(motion, feed=None if motion.feed is None else motion.feed * factor)
            first = False
        result.append(motion)
    return tuple(result)
