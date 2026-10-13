"""Numerically stable intersections of infinite lines and circles."""

from __future__ import annotations

import math


def line_circle_points(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> list[tuple[float, float]]:
    """Return ordered secant points or one tangent point, independent of line length.

    Project onto a unit direction instead of subtracting quadratic discriminant
    terms. Only roundoff at the input coordinate scale is treated as tangency;
    a genuinely separated line must not acquire an intersection.
    """
    vx, vy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(vx, vy)
    if length == 0.0:
        return []
    ux, uy = vx / length, vy / length
    ox, oy = start[0] - center[0], start[1] - center[1]
    signed_distance = ux * oy - uy * ox
    distance = abs(signed_distance)
    scale = max(*(abs(value) for value in (*start, *end, *center)), radius, length)
    tolerance = 16.0 * math.ulp(scale)
    if distance > radius + tolerance:
        return []
    # The closest point expressed relative to the center avoids cancellation
    # between a distant line start and a large projection along the line.
    foot = center[0] - uy * signed_distance, center[1] + ux * signed_distance
    if abs(distance - radius) <= tolerance:
        return [foot]
    half_chord = math.sqrt(max(0.0, (radius - distance) * (radius + distance)))
    return [
        (foot[0] - half_chord * ux, foot[1] - half_chord * uy),
        (foot[0] + half_chord * ux, foot[1] + half_chord * uy),
    ]
