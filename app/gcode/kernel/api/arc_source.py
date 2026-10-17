"""Select source arc conventions and preflight turning profile arcs."""

from __future__ import annotations

import math
from dataclasses import replace

from ..frontend.program import eval_words, resolve_cycle_profile_indices
from ..geometry.direct import build_profile_segments
from ..types import Diagnostic, TraceMotion
from .arc_validation import _ijk_radius_mismatch
from .trace_geometry import _compensation_frame


def _autodetect_arc_type(
    motions: tuple[TraceMotion, ...], *, tolerance: float, fallback: int, turning: bool = False
) -> int:
    tolerance = max(0.0, float(tolerance))
    for motion in motions:
        if motion.orientation is not None:
            motion = _compensation_frame(motion, local=True)
        if turning:
            # Detection runs before per-step geometry metadata is attached.
            # Native turning X/I values are diameters; compare physical radii.
            motion = replace(motion, x_scale=0.5)
        relative_error = _ijk_radius_mismatch(motion, 1)
        absolute_error = _ijk_radius_mismatch(motion, 2)
        if relative_error is None and absolute_error is None:
            continue
        relative_valid = relative_error is not None and relative_error <= tolerance
        absolute_valid = absolute_error is not None and absolute_error <= tolerance
        if relative_valid != absolute_valid:
            return 1 if relative_valid else 2
    return fallback


def _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type):
    if result.source_dialect == "sinumerik":
        return source_arc_type
    if language not in ("fanuc_mill", "fanuc_turn") or not autodetect_arc_type:
        return source_arc_type
    return _autodetect_arc_type(
        result.motions,
        tolerance=arc_tolerance,
        fallback=source_arc_type,
        turning=language == "fanuc_turn",
    )


def _profile_arc_diagnostic(segment, blocks, variables, step, source_arc_type, tolerance):
    if segment.move not in (2, 3):
        return None
    if source_arc_type == 3:
        if segment.has_radius:
            return None
        code = "TURNING_ARC_REQUIRES_R"
        message = "Radius arc mode requires an R word in the P/Q profile"
    elif not segment.has_center:
        return None
    else:
        if source_arc_type == 1:
            center_x, center_z = segment.center.x * 0.5, segment.center.z
        else:
            arc_words = eval_words(blocks[segment.block].parsed_words, variables)
            center_x = arc_words.get("I", 0.0) * step.unit_scale
            center_z = arc_words.get("K", 0.0) * step.unit_scale
        start_radius = math.hypot(segment.start.x * 0.5 - center_x, segment.start.z - center_z)
        end_radius = math.hypot(segment.end.x * 0.5 - center_x, segment.end.z - center_z)
        mismatch = abs(start_radius - end_radius)
        if mismatch <= max(0.0, float(tolerance)):
            return None
        code = "INVALID_TURNING_ARC_CENTER"
        message = f"P/Q arc center does not fit the endpoints in the selected mode (radius mismatch {mismatch:.4g} mm)"
    return Diagnostic(code, message, "error", "invalid_geometry", segment.block + 1, blocks[segment.block].raw)


def _invalid_turning_profile_cycles(result, source_arc_type: int, tolerance: float, gcode_system: str = "A"):
    """Preflight P/Q arc words before publishing any motions from their cycles."""
    if result.program is None or source_arc_type not in (1, 2, 3):
        return {}
    blocks = result.program.blocks
    invalid = {}
    for step_index, step in enumerate(result.execution_steps):
        words = dict(step.words)
        gcode = words.get("G")
        if gcode not in (70, 71, 72, 73) or "P" not in words or "Q" not in words or not step.emitted_count:
            continue
        bounds = resolve_cycle_profile_indices(
            blocks, step.source_block, int(words["P"]), int(words["Q"]), prefer_preceding=gcode == 70
        )
        if bounds is None or step.position is None:
            continue
        variables = dict(step.variables)
        profile = build_profile_segments(
            blocks,
            *bounds,
            step.position[0],
            step.position[2],
            variables,
            x_is_diameter=step.x_is_diameter,
            unit_scale=step.unit_scale,
            gcode_system=gcode_system,
            distance_absolute=step.absolute,
        )
        for segment in profile:
            diagnostic = _profile_arc_diagnostic(segment, blocks, variables, step, source_arc_type, tolerance)
            if diagnostic is not None:
                invalid[step_index] = diagnostic
                break
    return invalid
