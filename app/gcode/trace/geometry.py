"""Resolved motion geometry, physical lengths and analytical bounds."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from app.gcode.kernel import TraceMotion
from app.gcode.kernel.geometry.spatial_arc import axial_travel, extreme_points


@dataclass(frozen=True)
class RenderPoint:
    x: float
    y: float
    z: float
    feed: float | None
    source_block: int | None
    motion_index: int
    i: float | None = None
    j: float | None = None
    k: float | None = None


def _local_oriented_arc(motion: TraceMotion) -> TraceMotion:
    """Project an indexed arc back into its programmed plane for sampling."""
    matrix = motion.orientation
    origin = motion.orientation_offset

    def inverse(point):
        shifted = tuple(point[i] - origin[i] for i in range(3))
        return tuple(sum(matrix[j][i] * shifted[j] for j in range(3)) for i in range(3))

    start = inverse((motion.start_x, motion.start_y, motion.start_z))
    end = inverse((motion.end_x, motion.end_y, motion.end_z))
    arc = replace(motion.arc, center=inverse(motion.arc.center))
    return replace(
        motion,
        start_x=start[0],
        start_y=start[1],
        start_z=start[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        arc=arc,
        orientation=None,
    )


def _forward_oriented_point(motion: TraceMotion, point: RenderPoint) -> RenderPoint:
    matrix = motion.orientation
    origin = motion.orientation_offset
    xyz = (point.x, point.y, point.z)
    transformed = tuple(sum(matrix[i][j] * xyz[j] for j in range(3)) + origin[i] for i in range(3))
    return replace(point, x=transformed[0], y=transformed[1], z=transformed[2])


def _motion_z_min(motion: TraceMotion) -> float:
    """Return the exact minimum Z reached by one resolved motion."""
    minimum = min(motion.start_z, motion.end_z)
    if motion.arc is not None and motion.arc.normal is not None:
        return min([minimum, *(point[2] for point in extreme_points(motion))])
    geometry = arc_geometry(motion)
    if geometry is None or motion.plane == 17:
        return minimum
    _start, _end, _orth0, _orth1, center, a0, sweep, radius = geometry
    plot_move = _plot_move_for_plane(motion.move, motion.plane)
    for angle in (math.pi / 2.0, 3.0 * math.pi / 2.0):
        delta = ((a0 - angle) % (2.0 * math.pi)) if plot_move == 2 else ((angle - a0) % (2.0 * math.pi))
        if delta <= sweep + 1e-12:
            minimum = min(minimum, center[1] + radius * math.sin(angle))
    return minimum


def _plot_move_for_plane(move: int, plane: int) -> int:
    """Map controller G2/G3 to the 2D plotting orientation of a plane.

    G18 is XZ, whose handedness is opposite to XY/YZ when represented as the
    usual 2D (first-axis, second-axis) plotting plane. Swap G2/G3 accordingly.
    """
    if plane == 18:
        if move == 2:
            return 3
        if move == 3:
            return 2
    return move


def _plane_coordinates(m: TraceMotion, x_scale: float = 1.0):
    if m.plane == 18:
        return (m.start_x * x_scale, m.start_z), (m.end_x * x_scale, m.end_z), m.start_y, m.end_y
    if m.plane == 19:
        return (m.start_y, m.start_z), (m.end_y, m.end_z), m.start_x, m.end_x
    return (m.start_x, m.start_y), (m.end_x, m.end_y), m.start_z, m.end_z


def arc_geometry(
    m: TraceMotion,
    *,
    lathe_radius_view: bool = False,
):
    """Resolve one logical arc in its controller plane."""
    if m.move not in (2, 3) or m.plane not in (17, 18, 19):
        return None

    if m.arc is None:
        return None
    start, end, orth0, orth1 = _plane_coordinates(m, m.x_scale)
    c = m.arc.center
    center = (c[0], c[2]) if m.plane == 18 else ((c[1], c[2]) if m.plane == 19 else (c[0], c[1]))
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    return start, end, orth0, orth1, center, a0, m.arc.sweep, m.arc.radius


def _xyz_from_plane(plane: int, a: float, b: float, orth: float):
    if plane == 18:
        return a, orth, b
    if plane == 19:
        return orth, a, b
    return a, b, orth


def motion_length(
    m: TraceMotion,
    *,
    lathe_radius_view: bool = False,
) -> float:
    """Return physical tool-centre length in millimetres.

    ``lathe_radius_view`` is retained for API compatibility but display mode must
    not change physical statistics.  Turning traces carry ``x_scale=0.5`` when
    their programmed X is diameter-space.
    """
    del lathe_radius_view
    if m.arc is not None and m.arc.normal is not None:
        return math.hypot(m.arc.radius * m.arc.sweep, axial_travel(m))
    sx = m.start_x * m.x_scale
    ex = m.end_x * m.x_scale
    if m.move in (2, 3):
        if m.orientation is not None and m.arc is not None:
            return motion_length(_local_oriented_arc(m))
        geom = arc_geometry(m)
        if geom:
            _, _, orth0, orth1, _, _, sweep, radius = geom
            return math.hypot(radius * sweep, orth1 - orth0)
    return math.sqrt((ex - sx) ** 2 + (m.end_y - m.start_y) ** 2 + (m.end_z - m.start_z) ** 2)


def _arc_extreme_coordinates(m: TraceMotion, display_x_scale: float) -> list[tuple[float, float, float]]:
    """Return circle quadrant extremes lying on one arc, in the caller's display X-space."""
    if m.arc is not None and m.arc.normal is not None:
        return [(point[0] * display_x_scale, point[1], point[2]) for point in extreme_points(m)]
    geom = arc_geometry(m)
    if geom is None:
        return []
    _start, _end, orth0, orth1, center, a0, sweep, radius = geom
    plot_move = _plot_move_for_plane(m.move, m.plane)
    points = []
    for angle in (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
        delta = ((a0 - angle) % (2.0 * math.pi)) if plot_move == 2 else ((angle - a0) % (2.0 * math.pi))
        if delta <= sweep + 1e-12:
            t = 0.0 if sweep <= 1e-12 else delta / sweep
            orth = orth0 + (orth1 - orth0) * t
            a = center[0] + radius * math.cos(angle)
            b = center[1] + radius * math.sin(angle)
            x, y, z = _xyz_from_plane(m.plane, a, b, orth)
            # Arc geometry is physical; bounds use the same X-space
            # requested by the caller as the endpoint coordinates.
            x *= display_x_scale / m.x_scale
            points.append((x, y, z))
    return points
