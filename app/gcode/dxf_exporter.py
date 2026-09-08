"""DXF consumer for the kernel's already-resolved motion trace."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import units
from ezdxf.math import OCS

from .kernel import ExecutionResult, TraceMotion
from .trace_tools import RenderPoint, sample_motion

RAPID_LAYER = "TOOLPATH_RAPID"
CUT_LAYER = "TOOLPATH_CUT"
_EPSILON = 1e-8


def _is_turning(result: ExecutionResult, turning: bool | None) -> bool:
    if turning is not None:
        return turning
    return result.language == "fanuc_turn"


def _motion_point(motion: TraceMotion, *, end: bool, turning: bool) -> tuple[float, float, float]:
    x = (motion.end_x if end else motion.start_x) * motion.x_scale
    y = motion.end_y if end else motion.start_y
    z = motion.end_z if end else motion.start_z
    # Match the lathe Plot orientation: CNC Z is horizontal and physical
    # radius-X is vertical. DXF's drawing plane is therefore (Z, X) -> (X, Y).
    return (z, x, 0.0) if turning else (x, y, z)


def _arc_center(motion: TraceMotion, *, turning: bool) -> tuple[float, float, float]:
    assert motion.arc is not None
    x, y, z = motion.arc.center
    return (z, x, 0.0) if turning else (x, y, z)


def _validate_point(point: tuple[float, float, float], description: str) -> None:
    if not all(math.isfinite(value) for value in point):
        raise ValueError(f"DXF export cannot write non-finite {description}")


def _normal_candidates(plane: int, turning: bool) -> tuple[tuple[float, float, float], ...]:
    if turning:
        return ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
    axis = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}.get(plane)
    if axis is None:
        raise ValueError(f"Unsupported trace arc plane G{plane}")
    return (axis, tuple(-value for value in axis))


def _arc_ocs(
    motion: TraceMotion,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    center: tuple[float, float, float],
    *,
    turning: bool,
):
    """Choose the OCS normal whose CCW sweep matches the resolved trace sweep."""
    assert motion.arc is not None
    expected_sweep = math.degrees(motion.arc.sweep)
    choices = []
    for normal in _normal_candidates(motion.arc.plane, turning):
        ocs = OCS(normal)
        ocs_start = ocs.from_wcs(start)
        ocs_end = ocs.from_wcs(end)
        ocs_center = ocs.from_wcs(center)
        if max(abs(ocs_start.z - ocs_center.z), abs(ocs_end.z - ocs_center.z)) > _EPSILON:
            continue
        start_angle = math.degrees(math.atan2(ocs_start.y - ocs_center.y, ocs_start.x - ocs_center.x)) % 360.0
        end_angle = math.degrees(math.atan2(ocs_end.y - ocs_center.y, ocs_end.x - ocs_center.x)) % 360.0
        ccw_sweep = (end_angle - start_angle) % 360.0
        choices.append((abs(ccw_sweep - expected_sweep), normal, ocs_center, start_angle, end_angle))
    if not choices:
        return None
    _, normal, ocs_center, start_angle, end_angle = min(choices, key=lambda choice: choice[0])
    return normal, ocs_center, start_angle, end_angle


def _same_point(left: tuple[float, float, float], right: tuple[float, float, float]) -> bool:
    return all(math.isclose(a, b, abs_tol=_EPSILON) for a, b in zip(left, right, strict=True))


def _helix_points(
    motion: TraceMotion,
    motion_index: int,
    render_points: dict[int, list[RenderPoint]],
) -> list[tuple[float, float, float]]:
    start = _motion_point(motion, end=False, turning=False)
    sampled = render_points.get(motion_index)
    if sampled is None:
        sampled = sample_motion(motion, motion_index)
    points = [start]
    for point in sampled:
        current = (point.x, point.y, point.z)
        if not _same_point(points[-1], current):
            points.append(current)
    return points


def _add_arc_or_circle(modelspace, motion: TraceMotion, layer: str, *, turning: bool) -> bool:
    """Add a planar analytical arc; return False for a non-planar helix."""
    assert motion.arc is not None
    start = _motion_point(motion, end=False, turning=turning)
    end = _motion_point(motion, end=True, turning=turning)
    center = _arc_center(motion, turning=turning)
    for point, description in ((start, "arc start"), (end, "arc end"), (center, "arc center")):
        _validate_point(point, description)
    if not math.isfinite(motion.arc.radius) or motion.arc.radius <= 0 or not math.isfinite(motion.arc.sweep):
        raise ValueError("DXF export cannot write invalid resolved arc geometry")

    resolved = _arc_ocs(motion, start, end, center, turning=turning)
    if resolved is None:
        return False
    normal, ocs_center, start_angle, end_angle = resolved
    attributes = {"layer": layer, "extrusion": normal}
    if motion.arc.full_circle:
        modelspace.add_circle(ocs_center, motion.arc.radius, dxfattribs=attributes)
    else:
        modelspace.add_arc(
            ocs_center,
            motion.arc.radius,
            start_angle,
            end_angle,
            dxfattribs=attributes,
        )
    return True


def build_dxf_document(
    result: ExecutionResult,
    *,
    turning: bool | None = None,
    render_points: Iterable[RenderPoint] | None = None,
):
    """Build a DXF document from one completed kernel execution result."""
    if result is None or not result.ok or not result.complete:
        raise ValueError("No valid complete CNC execution result is available for DXF export")

    turning = _is_turning(result, turning)
    points_by_motion: dict[int, list[RenderPoint]] = defaultdict(list)
    if render_points is not None:
        for point in render_points:
            points_by_motion[point.motion_index].append(point)

    document = ezdxf.new("R2010")
    document.units = units.MM
    document.layers.add(RAPID_LAYER, color=1, linetype="CONTINUOUS")
    document.layers.add(CUT_LAYER, color=5, linetype="CONTINUOUS")
    modelspace = document.modelspace()

    for motion_index, motion in enumerate(result.motions):
        layer = RAPID_LAYER if motion.move == 0 else CUT_LAYER
        if motion.move in (2, 3) and motion.arc is not None:
            if _add_arc_or_circle(modelspace, motion, layer, turning=turning):
                continue
            if turning:
                raise ValueError("Turning trace contains an arc outside the X/Z export plane")
            helix = _helix_points(motion, motion_index, points_by_motion)
            if len(helix) < 2:
                raise ValueError("DXF export cannot represent incomplete helical trace geometry")
            modelspace.add_polyline3d(helix, dxfattribs={"layer": layer})
            continue

        start = _motion_point(motion, end=False, turning=turning)
        end = _motion_point(motion, end=True, turning=turning)
        _validate_point(start, "line start")
        _validate_point(end, "line end")
        modelspace.add_line(start, end, dxfattribs={"layer": layer})

    return document


def export_dxf(
    result: ExecutionResult,
    path: str | Path,
    *,
    turning: bool | None = None,
    render_points: Iterable[RenderPoint] | None = None,
) -> None:
    """Write the resolved toolpath to *path* as a millimetre DXF file."""
    document = build_dxf_document(result, turning=turning, render_points=render_points)
    document.saveas(path)
