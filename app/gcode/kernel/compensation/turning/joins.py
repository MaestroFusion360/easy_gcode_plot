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


def join_primitives(a: TurningPrimitive, b: TurningPrimitive) -> Vec2:
    if a.center is None and b.center is None:
        candidates = line_intersection(a, b)
    elif a.center is None:
        candidates = line_circle_intersections(a, b)
    elif b.center is None:
        candidates = line_circle_intersections(b, a)
    else:
        candidates = circle_circle_intersections(a, b)
    if not candidates:
        raise ToolCompensationError("Adjacent compensated segments do not intersect.")
    return min(
        candidates,
        key=lambda point: (
            math.hypot(point.x - a.end.x, point.y - a.end.y) + math.hypot(point.x - b.start.x, point.y - b.start.y)
        ),
    )
