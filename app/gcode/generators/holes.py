"""Circular and rectangular hole-pattern geometry and coordinate blocks."""

from __future__ import annotations

import math

from .formatting import _number
from .types import Point


def hole_circle_points(*, diameter, start_angle, center_x, center_y, count, ccw=True) -> list[Point]:
    radius = diameter / 2.0
    direction = 1.0 if ccw else -1.0
    return [
        (
            center_x + radius * math.cos(math.radians(start_angle) + direction * math.tau * index / count),
            center_y + radius * math.sin(math.radians(start_angle) + direction * math.tau * index / count),
        )
        for index in range(count)
    ]


def hole_circle(*, diameter, start_angle, center_x, center_y, count, ccw=True) -> str:
    return "\n".join(
        f"X{_number(x_value)} Y{_number(y_value)}"
        for x_value, y_value in hole_circle_points(
            diameter=diameter,
            start_angle=start_angle,
            center_x=center_x,
            center_y=center_y,
            count=count,
            ccw=ccw,
        )
    )


def hole_grid_points(*, start_x, start_y, step_x, step_y, count_x, count_y) -> list[Point]:
    points = []
    for row in range(count_y):
        columns = range(count_x) if row % 2 == 0 else range(count_x - 1, -1, -1)
        for column in columns:
            points.append((start_x + column * step_x, start_y + row * step_y))
    return points


def hole_grid(*, start_x, start_y, step_x, step_y, count_x, count_y) -> str:
    return "\n".join(
        f"X{_number(x_value)} Y{_number(y_value)}"
        for x_value, y_value in hole_grid_points(
            start_x=start_x,
            start_y=start_y,
            step_x=step_x,
            step_y=step_y,
            count_x=count_x,
            count_y=count_y,
        )
    )
