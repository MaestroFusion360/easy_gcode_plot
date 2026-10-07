"""Keep resolved drilling semantics alongside the plotting geometry."""

from ...api.types import ExecutionEvent, ResolvedDrillingOperation
from ..kinematics import point_orientation
from ..state import _machine


def drilling_event(context, state, resolved, motions, *, native=None):
    code = native.code if native is not None else state.cycle
    kind = {73: "peckDrill", 81: "drill", 82: "drillDwell", 83: "peckDrill", 84: "tap", 85: "boreFeed", 86: "boreStop"}[
        code
    ]
    if native is not None and code == 81 and native.dwell:
        kind = "drillDwell"

    def point(z):
        return _machine((resolved.x, resolved.y, z), state, context.coordinate_context)

    parameters = _native_parameters(native) if native is not None else _iso_parameters(state, resolved)
    depth_span = resolved.retract_z - resolved.target_z
    axial_scale = abs(point(resolved.retract_z)[2] - point(resolved.target_z)[2]) / depth_span if depth_span else 1.0
    for name in ("peck_first", "peck_reduction", "peck_minimum", "reentry_clearance", "retract_distance"):
        if name in parameters:
            parameters[name] *= axial_scale
    return ExecutionEvent(
        "DRILLING_CYCLE",
        context.block.index,
        code=f"CYCLE{code}" if native is not None else f"G{code}",
        drilling=ResolvedDrillingOperation(
            kind=kind,
            start=_machine((state.x, state.y, state.z), state, context.coordinate_context),
            position=point(resolved.target_z),
            safety=point(resolved.retract_z),
            reference=point(native.reference_z if native is not None else resolved.retract_z),
            returned=point(resolved.return_z),
            feed=resolved.feed,
            feed_mode=state.feed_mode,
            spindle_speed=state.spindle_rpm or 0.0,
            emitted_count=len(motions),
            orientation=drilling_orientation(state),
            peck_return_height=point(native.return_z if native is not None else resolved.retract_z)[2],
            feed_return_height=point(resolved.retract_z)[2],
            **parameters,
        ),
    )


def drilling_orientation(state):
    if state.twp.active:
        return state.twp.orientation
    if state.kinematics is not None and not state.tcp_control:
        return point_orientation(state.kinematics, state.rotary_angles)
    return None


def _iso_parameters(state, resolved):
    return {
        "dwell_bottom": state.cycle_p if state.cycle in (82, 84) else 0.0,
        "peck_first": resolved.step or 0.0,
        "full_retract": state.cycle != 73,
        "reentry_clearance": state.g83_clearance,
        "retract_distance": state.g73_retract_distance,
        "rigid_tapping": state.rigid_tapping_ready,
    }


def _native_parameters(cycle):
    return {
        "dwell_bottom": cycle.dwell,
        "peck_first": cycle.reference_z - cycle.first_depth if cycle.first_depth is not None else 0.0,
        "peck_reduction": cycle.degression,
        "peck_minimum": cycle.minimum_step,
        "full_retract": cycle.full_retract,
        "reentry_clearance": cycle.clearance,
        "retract_distance": cycle.retract_distance,
        "first_feed_factor": cycle.feed_factor,
        "rigid_tapping": cycle.code == 84,
    }
