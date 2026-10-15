"""Capability and geometry checks shared by resolved NC output backends."""

from __future__ import annotations

import json
import math

from ..kernel import ExecutionResult
from ..kernel.milling.kinematics import (
    MachineKinematics,
    RotaryAxis,
    point_orientation,
    profile_from_snapshot,
    transform_point,
)
from .common import ExportLimitation, ExportOptions, _execution_slices, _require_continuous_motions


def _uses_y_axis(result: ExecutionResult) -> bool:
    return any(
        abs(motion.start_y) > 1e-12 or abs(motion.end_y) > 1e-12 or motion.plane in (17, 19)
        for motion in result.motions
    )


def _check_supports(result: ExecutionResult, profile: dict, options: ExportOptions) -> None:
    """Declared post capabilities fail closed before any output is written."""
    supports = profile.get("supports")
    if not supports:
        return
    _check_supports_axes(result, supports)
    _check_supports_arcs(result, supports, options)
    _check_supports_feed(result, supports)


def _check_supports_axes(result: ExecutionResult, supports: dict) -> None:
    axes = set(supports.get("axes", ("X", "Y", "Z")))
    rotary_axes = {axis for event in result.events for axis in event.axes if event.kind.startswith("ROTARY_")}
    if not {"X", "Z"} <= axes or ("Y" not in axes and _uses_y_axis(result)) or not rotary_axes <= axes:
        raise ExportLimitation(
            "Selected post supports only axes " + ", ".join(sorted(axes)),
            code="UNSUPPORTED_AXIS_EXPANDED_EXPORT",
        )


def _check_supports_arcs(result: ExecutionResult, supports: dict, options: ExportOptions) -> None:
    multi_turn = any(motion.arc is not None and motion.arc.sweep > math.tau + 1e-10 for motion in result.motions)
    if not supports.get("multiTurnArcs", True) and options.multi_turn_arcs and multi_turn:
        raise ExportLimitation(
            "Selected post cannot emit multi-turn arcs",
            code="UNSUPPORTED_MULTITURN_ARC_EXPANDED_EXPORT",
        )
    if not supports.get("absoluteArcCenters", True) and options.arc_mode == 1:
        raise ExportLimitation(
            "Selected post does not support absolute arc centers",
            code="UNSUPPORTED_ABSOLUTE_ARC_EXPANDED_EXPORT",
        )


def _check_supports_feed(result: ExecutionResult, supports: dict) -> None:
    inverse_time = any(motion.feed_mode == "inverse_time" for motion in result.motions)
    if not supports.get("inverseTime", True) and inverse_time:
        raise ExportLimitation(
            "Selected post cannot represent inverse-time feed (G93)",
            code="UNSUPPORTED_INVERSE_TIME_EXPANDED_EXPORT",
        )


def _profile_axes(profile: dict) -> tuple[str, ...]:
    """Return the axes a post profile declares it supports (default XYZ)."""
    supports = profile.get("supports") or {}
    return tuple(supports.get("axes", ["X", "Y", "Z"]))


def _uses_rotary_geometry(result: ExecutionResult) -> bool:
    """Reject actual rotary/TWP/TCP use, not merely a selected kinematics profile."""
    rotary_events = {"ROTARY_INDEX", "ROTARY_MOTION", "TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"}
    if any(event.kind in rotary_events for event in result.events):
        return True
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for motion in result.motions:
        if motion.orientation is None:
            continue
        if any(
            abs(motion.orientation[row][column] - identity[row][column]) > 1e-9
            for row in range(3)
            for column in range(3)
        ):
            return True
    return False


def _inverse_orientation_point(matrix, point):
    """Map one physical point back into the indexed table frame."""
    return tuple(sum(matrix[j][i] * point[j] for j in range(3)) for i in range(3))


def _has_unreconstructable_non_tcp_rotary_motion(result: ExecutionResult) -> bool:
    executed_profile = profile_from_snapshot(result.kinematics_definition)
    continuous_c = executed_profile is not None and executed_profile.continuous_c_table
    tcp_active = False
    for step in result.execution_steps:
        for event in step.events:
            if event.kind == "TCP_CONTROL_ON":
                tcp_active = True
            elif event.kind == "TCP_CONTROL_OFF":
                tcp_active = False
            elif event.kind == "ROTARY_MOTION" and not tcp_active and not continuous_c:
                return True
    return False


def _require_reconstructable_index_origin(result):
    """Zero-offset output cannot preserve an index about a displaced WCS origin."""
    offsets = {m.orientation_offset for m in result.motions if any(abs(v) > 1e-9 for v in m.orientation_offset)}
    if not offsets:
        return
    definition = json.loads(result.kinematics_definition) if result.kinematics_definition else None
    table = (
        None
        if definition is None
        else MachineKinematics(
            "resolved",
            "resolved",
            tuple(RotaryAxis(joint["address"], tuple(joint["axis"])) for joint in definition["table_rotary_axes"]),
            (),
        )
    )
    indexed = any(
        event.kind == "ROTARY_INDEX" and any(_index_moves_offset(event, table, offset) for offset in offsets)
        for event in result.events
    )
    if indexed:
        raise ExportLimitation(
            "Indexed rotary export with a displaced WCS requires target frame-offset reconstruction",
            code="UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT",
        )


def _index_moves_offset(event, table, offset):
    if table is None or event.old_abc is None or event.new_abc is None:
        return True
    old = point_orientation(table, dict(zip("ABC", event.old_abc, strict=True)))
    new = point_orientation(table, dict(zip("ABC", event.new_abc, strict=True)))
    moved = transform_point(new, _inverse_orientation_point(old, offset))
    return any(abs(a - b) > 1e-9 for a, b in zip(moved, offset, strict=True))


def _require_valid_trace_export(result: ExecutionResult, profile: dict, *, allow_inverse_time=False) -> None:
    if result is None or not result.ok or not result.complete:
        raise ValueError("EXPANDED requires a valid and complete execution result")
    supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
    if any(event.kind == "TCP_CONTROL_ON" for event in result.events) and not supports_tcp:
        raise ExportLimitation(
            "Selected post cannot preserve G43.4 TCP rotary commands / TRAORI or reconstruct resolved TCP motion",
            code="UNSUPPORTED_TCP_EXPANDED_EXPORT",
        )
    _require_supported_twp(result, profile)
    if _has_unreconstructable_non_tcp_rotary_motion(result):
        raise ExportLimitation(
            "Expanded multiaxis export cannot reconstruct this non-TCP continuous rotary interpolation",
            code="UNSUPPORTED_CONTINUOUS_ROTARY_EXPANDED_EXPORT",
        )
    if not any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events):
        _require_reconstructable_index_origin(result)
    _require_continuous_motions(result, allow_reference_rapids=True, allow_rotary_index_gaps=True)
    if not allow_inverse_time and any(m.feed_mode == "inverse_time" for m in result.motions):
        raise ExportLimitation(
            "Selected post cannot represent inverse-time feed (G93)",
            code="UNSUPPORTED_INVERSE_TIME_EXPANDED_EXPORT",
        )
    if any(step.spindle_mode == "css" for step in result.execution_steps) and result.source_dialect == "sinumerik":
        raise ExportLimitation(
            "Native CSS reference axis and instantaneous RPM are unavailable",
            code="UNSUPPORTED_SINUMERIK_CSS_EXPANDED_EXPORT",
        )
    ignored_native = {
        "HEIDENHAIN_M140_HOME_EMULATION",
        "IGNORED_SINUMERIK_DIAMETER_MODE",
        "UNMODELED_SINUMERIK_CHF",
        "UNMODELED_SINUMERIK_CHR",
        "UNMODELED_SINUMERIK_RND",
        "UNMODELED_SINUMERIK_RNDM",
        "UNMODELED_SINUMERIK_FRC",
        "UNMODELED_SINUMERIK_FRCM",
        "UNVERIFIED_CUTTER_COMPENSATION",
        "UNVERIFIED_SINUMERIK_EDGE_OFFSETS",
        "UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION",
    }
    blockers = [
        d.code for d in result.diagnostics if d.code in ignored_native or d.code == "UNMODELED_SINUMERIK_NATIVE"
    ]
    if blockers:
        message = (
            "NC trace export cannot preserve ignored SINUMERIK diameter/corner/feed commands"
            if any("SINUMERIK" in code for code in blockers)
            else "NC trace export cannot preserve unverified geometry"
        )
        raise ExportLimitation(
            message + ": " + ", ".join(sorted(set(blockers))),
            code="UNSUPPORTED_UNVERIFIED_GEOMETRY_EXPANDED_EXPORT",
        )


def _require_supported_twp(result, profile):
    frames = [e for e in result.events if e.kind == "TILTED_WORK_PLANE_ON"]
    if not frames:
        return
    executed_profile = profile_from_snapshot(result.kinematics_definition)
    supported = (
        executed_profile is not None
        and executed_profile.tcp_table_supported
        and profile["id"] in {"fanuc_mill_multiaxis", "sinumerik_840d_multiaxis"}
        and all(e.twp_orientation is not None and e.twp_origin is not None for e in frames)
        and not result.extended_wcs_offsets
        and not any(("G", 10.0) in step.words for step in result.execution_steps)
    )
    # Each frame must have a resolved tool-axis index. Curves and cycle segments
    # already carry resolved geometry in that fixed local frame.
    for frame in frames:
        orient = next(
            (
                e
                for e in result.events
                if e.kind == "TOOL_AXIS_ORIENT" and e.source_block in (frame.source_block, frame.source_block + 1)
            ),
            None,
        )
        supported = supported and orient is not None
    supported = supported and all(
        m.move in (0, 1, 2, 3)
        and (m.source_kind in {"motion", "cycle"} or m.source_kind.startswith("cutter_compensation"))
        for step, _, motions in _execution_slices(result)
        if step.twp_orientation is not None
        for m in motions
    )
    if not supported:
        raise ExportLimitation(
            "G68.2/CYCLE800 export requires a resolved AC/BC table index and G54-G59 work frames",
            code="UNSUPPORTED_TWP_EXPANDED_EXPORT",
        )
