"""Join construction for compensated lathe primitives."""

from __future__ import annotations

import math

from ..common import ToolCompensationError
from ..geometry import (
    TurningPrimitive,
    Vec2,
    circle_circle_intersections,
    line_circle_intersections,
    line_intersection,
)

_COINCIDENT_ENDPOINT_TOLERANCE = 0.002


def _endpoint_gap(a: TurningPrimitive, b: TurningPrimitive) -> float:
    return math.hypot(a.end.x - b.start.x, a.end.y - b.start.y)


def _circular_endpoint(a: TurningPrimitive, b: TurningPrimitive) -> Vec2:
    """Keep the endpoint that belongs to the arc, not the line."""
    return a.end if a.center is not None else b.start


def _join_candidates(a: TurningPrimitive, b: TurningPrimitive) -> list[Vec2]:
    if a.center is None and b.center is None:
        return line_intersection(a, b)
    if a.center is None:
        return line_circle_intersections(a, b)
    if b.center is None:
        return line_circle_intersections(b, a)
    return circle_circle_intersections(a, b)


def join_primitives(a: TurningPrimitive, b: TurningPrimitive) -> Vec2:
    nearly_joined = _endpoint_gap(a, b) <= _COINCIDENT_ENDPOINT_TOLERANCE
    # Rounded CAM endpoints near tangency can create two spurious circle/line
    # intersections far from the intended join. Preserve the circular endpoint.
    if (a.center is None) != (b.center is None) and nearly_joined:
        return _circular_endpoint(a, b)
    candidates = _join_candidates(a, b)
    if not candidates and nearly_joined:
        return _circular_endpoint(a, b)
    if not candidates:
        raise ToolCompensationError("Adjacent compensated segments do not intersect.")
    return min(
        candidates,
        key=lambda point: (
            math.hypot(point.x - a.end.x, point.y - a.end.y) + math.hypot(point.x - b.start.x, point.y - b.start.y)
        ),
    )
