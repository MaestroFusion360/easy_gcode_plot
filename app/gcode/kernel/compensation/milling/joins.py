"""Intersection and transition geometry for compensated milling motions."""

from __future__ import annotations

import math
from dataclasses import replace

from ...api.types import TraceMotion
from ..common import EPS
from .projection import (
    _dist2,
    _normalize_ccw_delta,
    _Point2,
    _projected_to_motion,
    _ProjectedMotion,
    _retarget_end,
    _retarget_start,
)


def _line_line_intersection(a: _ProjectedMotion, b: _ProjectedMotion) -> list[_Point2]:
    avx, avy = a.end[0] - a.start[0], a.end[1] - a.start[1]
    bvx, bvy = b.end[0] - b.start[0], b.end[1] - b.start[1]
    det = avx * bvy - avy * bvx
    if abs(det) <= EPS:
        return []
    dx, dy = b.start[0] - a.start[0], b.start[1] - a.start[1]
    t = (dx * bvy - dy * bvx) / det
    return [(a.start[0] + t * avx, a.start[1] + t * avy)]


def _line_arc_intersections(line: _ProjectedMotion, arc: _ProjectedMotion) -> list[_Point2]:
    assert arc.center is not None and arc.radius is not None
    vx, vy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    aa = vx * vx + vy * vy
    if aa <= EPS:
        return []
    ox, oy = line.start[0] - arc.center[0], line.start[1] - arc.center[1]
    bb = 2.0 * (vx * ox + vy * oy)
    cc = ox * ox + oy * oy - arc.radius * arc.radius
    disc = bb * bb - 4.0 * aa * cc
    if disc < -EPS:
        return []
    root = math.sqrt(max(0.0, disc))
    t1 = (-bb - root) / (2.0 * aa)
    t2 = (-bb + root) / (2.0 * aa)
    out = [(line.start[0] + t1 * vx, line.start[1] + t1 * vy)]
    if abs(t2 - t1) > 1e-10:
        out.append((line.start[0] + t2 * vx, line.start[1] + t2 * vy))
    return out


def _arc_arc_intersections(a: _ProjectedMotion, b: _ProjectedMotion) -> list[_Point2]:
    assert a.center is not None and b.center is not None
    assert a.radius is not None and b.radius is not None
    dx, dy = b.center[0] - a.center[0], b.center[1] - a.center[1]
    distance = math.hypot(dx, dy)
    if distance <= EPS:
        return []
    if distance > a.radius + b.radius + EPS:
        return []
    if distance < abs(a.radius - b.radius) - EPS:
        return []

    along = (a.radius * a.radius - b.radius * b.radius + distance * distance) / (2.0 * distance)
    h2 = a.radius * a.radius - along * along
    if h2 < -EPS:
        return []
    height = math.sqrt(max(0.0, h2))
    mid_x = a.center[0] + along * dx / distance
    mid_y = a.center[1] + along * dy / distance
    rx, ry = -dy * height / distance, dx * height / distance
    out = [(mid_x + rx, mid_y + ry)]
    if height > 1e-10:
        out.append((mid_x - rx, mid_y - ry))
    return out


def _point_on_line(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    vx, vy = motion.end[0] - motion.start[0], motion.end[1] - motion.start[1]
    length2 = vx * vx + vy * vy
    if length2 <= EPS:
        return None
    length = math.sqrt(length2)
    wx, wy = point[0] - motion.start[0], point[1] - motion.start[1]
    t = (wx * vx + wy * vy) / length2
    projected = motion.start[0] + t * vx, motion.start[1] + t * vy
    if _dist2(projected, point) > tolerance * tolerance:
        return None
    return t * length, length


def _point_on_arc(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    assert motion.center is not None and motion.radius is not None
    if motion.radius <= EPS:
        return None
    px, py = point[0] - motion.center[0], point[1] - motion.center[1]
    point_radius = math.hypot(px, py)
    if abs(point_radius - motion.radius) > tolerance:
        return None

    start_angle = math.atan2(motion.start[1] - motion.center[1], motion.start[0] - motion.center[0])
    end_angle = math.atan2(motion.end[1] - motion.center[1], motion.end[0] - motion.center[0])
    point_angle = math.atan2(py, px)
    if motion.source.move == 3:
        sweep = _normalize_ccw_delta(start_angle, end_angle)
        point_sweep = _normalize_ccw_delta(start_angle, point_angle)
    else:
        sweep = _normalize_ccw_delta(end_angle, start_angle)
        point_sweep = _normalize_ccw_delta(point_angle, start_angle)
    if sweep <= EPS:
        sweep = 2.0 * math.pi
    if point_sweep > sweep + 1e-6:
        return None
    return point_sweep * motion.radius, sweep * motion.radius


def _get_progress(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    if motion.is_line:
        return _point_on_line(motion, point, tolerance)
    return _point_on_arc(motion, point, tolerance)


def _join_offset_primitives(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    tolerance: float,
) -> _Point2 | None:
    if previous.is_line and current.is_line:
        candidates = _line_line_intersection(previous, current)
    elif previous.is_line:
        candidates = _line_arc_intersections(previous, current)
    elif current.is_line:
        candidates = _line_arc_intersections(current, previous)
    else:
        candidates = _arc_arc_intersections(previous, current)
    if not candidates:
        return None

    valid: list[tuple[float, _Point2]] = []
    for candidate in candidates:
        progress_a = _get_progress(previous, candidate, tolerance)
        progress_b = _get_progress(current, candidate, tolerance)
        if progress_a is None or progress_b is None:
            continue
        if progress_a[0] < -1e-6 or progress_b[0] < -1e-6:
            continue
        score = _dist2(candidate, previous.end) + _dist2(candidate, current.start)
        valid.append((score, candidate))
    if valid:
        return min(valid, key=lambda item: item[0])[1]
    return min(
        candidates,
        key=lambda point: _dist2(point, previous.end) + _dist2(point, current.start),
    )


def _out_of_plane_at(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> float | None:
    if abs(motion.end_w - motion.start_w) <= EPS:
        return motion.start_w
    progress = _get_progress(motion, point, tolerance)
    if progress is None or progress[1] <= EPS:
        return None
    t = max(0.0, min(1.0, progress[0] / progress[1]))
    return motion.start_w + (motion.end_w - motion.start_w) * t


def _unit_tangent(motion: _ProjectedMotion) -> _Point2 | None:
    dx, dy = motion.end[0] - motion.start[0], motion.end[1] - motion.start[1]
    length = math.hypot(dx, dy)
    if length <= EPS:
        return None
    return dx / length, dy / length


def _line_line_transition_compatible(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> bool:
    same_geometry = previous.is_line and current.is_line and previous.plane == current.plane
    usable_offset = tool_radius > EPS and abs(signed_offset) > EPS
    same_level = abs(previous.end_w - current.start_w) <= 1e-6
    return same_geometry and usable_offset and same_level


def _line_line_transition_basis(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> tuple[_Point2, _Point2, float, _Point2] | None:
    if not _line_line_transition_compatible(previous, current, signed_offset, tool_radius):
        return None

    ta = _unit_tangent(previous)
    tb = _unit_tangent(current)
    if ta is None or tb is None:
        return None

    cross = ta[0] * tb[1] - ta[1] * tb[0]
    if abs(cross) <= 1e-6 or cross * signed_offset >= 0.0:
        return None

    corners = _line_line_intersection(previous, current)
    return (ta, tb, cross, corners[0]) if corners else None


def _line_line_transition_geometry(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    ta: _Point2,
    tb: _Point2,
    corner: _Point2,
    tool_radius: float,
) -> tuple[_Point2, _Point2, _Point2, float] | None:
    dot = max(-1.0, min(1.0, ta[0] * tb[0] + ta[1] * tb[1]))
    angle = math.acos(dot)
    if angle <= 1e-6 or abs(math.pi - angle) <= 1e-6:
        return None

    trim = tool_radius * math.tan(angle * 0.5)
    previous_length = math.sqrt(_dist2(previous.start, previous.end))
    current_length = math.sqrt(_dist2(current.start, current.end))
    invalid_trim = trim <= EPS or trim > previous_length + 1e-6
    invalid_trim = invalid_trim or trim > current_length + 1e-6
    if invalid_trim:
        return None

    t1 = corner[0] - ta[0] * trim, corner[1] - ta[1] * trim
    t2 = corner[0] + tb[0] * trim, corner[1] + tb[1] * trim
    n1 = -ta[1], ta[0]
    n2 = -tb[1], tb[0]
    normal_a = _ProjectedMotion(previous.source, previous.plane, t1, (t1[0] + n1[0], t1[1] + n1[1]), 0, 0)
    normal_b = _ProjectedMotion(current.source, current.plane, t2, (t2[0] + n2[0], t2[1] + n2[1]), 0, 0)
    centers = _line_line_intersection(normal_a, normal_b)
    if not centers:
        return None

    center = centers[0]
    radius = math.sqrt(_dist2(t1, center))
    if radius <= EPS:
        return None
    return t1, t2, center, radius


def _build_line_line_transition(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> tuple[_ProjectedMotion, _ProjectedMotion, TraceMotion] | None:
    basis = _line_line_transition_basis(previous, current, signed_offset, tool_radius)
    if basis is None:
        return None
    ta, tb, cross, corner = basis

    geometry = _line_line_transition_geometry(previous, current, ta, tb, corner, tool_radius)
    if geometry is None:
        return None
    t1, t2, center, radius = geometry

    stitched_previous = _retarget_end(previous, t1, previous.end_w)
    stitched_current = _retarget_start(current, t2, current.start_w)
    transition_projected = _ProjectedMotion(
        source=replace(previous.source, move=3 if cross > 0.0 else 2),
        plane=previous.plane,
        start=t1,
        end=t2,
        start_w=previous.end_w,
        end_w=previous.end_w,
        center=center,
        radius=radius,
    )
    transition = _projected_to_motion(
        transition_projected,
        comp_mode=previous.source.compensation_mode,
        source_kind="cutter_compensation_transition",
    )
    return stitched_previous, stitched_current, transition


def _join_steady_motion(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> tuple[_ProjectedMotion, _ProjectedMotion, TraceMotion | None] | None:
    signed_offset = tool_radius if comp_mode == 41 else -tool_radius
    fillet = _build_line_line_transition(previous, current, signed_offset, tool_radius)
    if fillet is not None:
        return fillet

    join = _join_offset_primitives(previous, current, geometry_tolerance)
    if join is None:
        return None
    join_w = _out_of_plane_at(current, join, geometry_tolerance)
    if join_w is None:
        join_w = _out_of_plane_at(previous, join, geometry_tolerance)
    if join_w is None:
        join_w = current.start_w
    return _retarget_end(previous, join, join_w), _retarget_start(current, join, join_w), None
