"""Small deterministic 2D geometry primitives used by compensation code."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..frontend.model import Motion
from ..geometry.intersections import line_circle_points
from .common import EPS


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class TurningPrimitive:
    motion: Motion
    start: Vec2
    end: Vec2
    center: Vec2 | None = None


def line_intersection(a: TurningPrimitive, b: TurningPrimitive) -> list[Vec2]:
    avx, avy = a.end.x - a.start.x, a.end.y - a.start.y
    bvx, bvy = b.end.x - b.start.x, b.end.y - b.start.y
    determinant = avx * bvy - avy * bvx
    lengths = math.hypot(avx, avy) * math.hypot(bvx, bvy)
    if lengths <= EPS * EPS or abs(determinant) <= EPS * lengths:
        if math.hypot(a.end.x - b.start.x, a.end.y - b.start.y) <= 1e-7:
            return [a.end]
        return []
    dx, dy = b.start.x - a.start.x, b.start.y - a.start.y
    progress = (dx * bvy - dy * bvx) / determinant
    return [Vec2(a.start.x + progress * avx, a.start.y + progress * avy)]


def line_circle_intersections(line: TurningPrimitive, arc: TurningPrimitive) -> list[Vec2]:
    assert arc.center is not None
    radius = math.hypot(arc.start.x - arc.center.x, arc.start.y - arc.center.y)
    return [
        Vec2(*point)
        for point in line_circle_points(
            (line.start.x, line.start.y), (line.end.x, line.end.y), (arc.center.x, arc.center.y), radius
        )
    ]


def circle_circle_intersections(a: TurningPrimitive, b: TurningPrimitive) -> list[Vec2]:
    assert a.center is not None and b.center is not None
    ar = math.hypot(a.start.x - a.center.x, a.start.y - a.center.y)
    br = math.hypot(b.start.x - b.center.x, b.start.y - b.center.y)
    dx, dy = b.center.x - a.center.x, b.center.y - a.center.y
    distance = math.hypot(dx, dy)
    if distance <= EPS or distance > ar + br + EPS or distance < abs(ar - br) - EPS:
        return []
    along = (ar * ar - br * br + distance * distance) / (2.0 * distance)
    height_sq = ar * ar - along * along
    if height_sq < -EPS:
        return []
    height = math.sqrt(max(0.0, height_sq))
    mx = a.center.x + along * dx / distance
    my = a.center.y + along * dy / distance
    rx, ry = -dy * height / distance, dx * height / distance
    return [Vec2(mx + rx, my + ry), Vec2(mx - rx, my - ry)]
