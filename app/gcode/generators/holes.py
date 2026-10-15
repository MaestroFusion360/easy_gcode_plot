"""Circular and rectangular hole-pattern geometry and coordinate blocks."""

from __future__ import annotations

import math

from .formatting import _number, _signed_number
from .types import Point


def _validate_finite(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite.")


def _validate_count(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def hole_circle_points(
    *,
    diameter: float,
    start_angle: float,
    center_x: float,
    center_y: float,
    count: int,
    ccw: bool = True,
) -> list[Point]:
    _validate_finite(
        diameter=diameter,
        start_angle=start_angle,
        center_x=center_x,
        center_y=center_y,
    )
    _validate_count("count", count)
    if diameter <= 0:
        raise ValueError("diameter must be positive.")

    radius = diameter / 2.0
    angle = math.radians(start_angle)
    direction = 1.0 if ccw else -1.0
    return [
        (
            center_x + radius * math.cos(angle + direction * math.tau * index / count),
            center_y + radius * math.sin(angle + direction * math.tau * index / count),
        )
        for index in range(count)
    ]


def _hole_lines(points: list[Point], source_dialect: str) -> str:
    """ISO keeps bare coordinates; Klartext positions a *signed* L block per hole."""
    if source_dialect == "heidenhain":
        return "\n".join(f"L X{_signed_number(x)} Y{_signed_number(y)} FMAX M99" for x, y in points)
    return "\n".join(f"X{_number(x)} Y{_number(y)}" for x, y in points)


def hole_circle(
    *,
    diameter: float,
    start_angle: float,
    center_x: float,
    center_y: float,
    count: int,
    ccw: bool = True,
    source_dialect: str = "fanuc",
) -> str:
    return _hole_lines(
        hole_circle_points(
            diameter=diameter,
            start_angle=start_angle,
            center_x=center_x,
            center_y=center_y,
            count=count,
            ccw=ccw,
        ),
        source_dialect,
    )


def hole_grid_points(
    *,
    start_x: float,
    start_y: float,
    step_x: float,
    step_y: float,
    count_x: int,
    count_y: int,
) -> list[Point]:
    _validate_finite(start_x=start_x, start_y=start_y, step_x=step_x, step_y=step_y)
    _validate_count("count_x", count_x)
    _validate_count("count_y", count_y)

    points: list[Point] = []
    for row in range(count_y):
        columns = range(count_x) if row % 2 == 0 else range(count_x - 1, -1, -1)
        for column in columns:
            points.append((start_x + column * step_x, start_y + row * step_y))
    return points


def hole_grid(
    *,
    start_x: float,
    start_y: float,
    step_x: float,
    step_y: float,
    count_x: int,
    count_y: int,
    source_dialect: str = "fanuc",
) -> str:
    return _hole_lines(
        hole_grid_points(
            start_x=start_x,
            start_y=start_y,
            step_x=step_x,
            step_y=step_y,
            count_x=count_x,
            count_y=count_y,
        ),
        source_dialect,
    )
