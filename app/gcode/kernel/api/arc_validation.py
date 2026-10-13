"""Validate IJK center geometry against resolved endpoints."""

from __future__ import annotations

import math

from .resources import SemanticError
from .types import TraceMotion


def _ijk_radius_mismatch(motion: TraceMotion, source_arc_type: int) -> float | None:
    axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}
    plane_axes = axes.get(motion.plane)
    if motion.move not in (2, 3) or plane_axes is None:
        return None
    start = (motion.start_x * motion.x_scale, motion.start_y, motion.start_z)
    end = (motion.end_x * motion.x_scale, motion.end_y, motion.end_z)
    offsets = (None if motion.i is None else motion.i * motion.x_scale, motion.j, motion.k)
    first_axis, second_axis = plane_axes
    if offsets[first_axis] is None and offsets[second_axis] is None:
        return None
    center_first = offsets[first_axis] or 0.0
    center_second = offsets[second_axis] or 0.0
    if source_arc_type == 1:
        center_first += start[first_axis]
        center_second += start[second_axis]
    elif motion.source_arc_type is None:
        center_offset = motion.absolute_center_offset or motion.orientation_offset
        center_first += center_offset[first_axis] * (motion.x_scale if first_axis == 0 else 1)
        center_second += center_offset[second_axis]
    start_radius = math.hypot(start[first_axis] - center_first, start[second_axis] - center_second)
    if start_radius <= 1e-10:
        return None
    end_radius = math.hypot(end[first_axis] - center_first, end[second_axis] - center_second)
    return abs(start_radius - end_radius)


def _validate_turning_arc_source(motion, source_arc_type: int, tolerance: float) -> None:
    """Reject an I/K arc that cannot represent the selected turning center mode."""
    if motion.move not in (2, 3) or motion.radius is not None and source_arc_type == 3:
        return
    if source_arc_type == 3:
        raise SemanticError("TURNING_ARC_REQUIRES_R", "Radius arc mode requires an R word", "invalid_geometry")
    mismatch = _ijk_radius_mismatch(motion, source_arc_type)
    if mismatch is not None and mismatch > max(0.0, float(tolerance)):
        raise SemanticError(
            "INVALID_TURNING_ARC_CENTER",
            f"I/K center does not fit the arc endpoints in the selected mode (radius mismatch {mismatch:.4g} mm)",
            "invalid_geometry",
        )
