"""Pure helpers extracted from the GUI layer for deterministic testing."""

from math import sqrt
from typing import Sequence


def format_gcode_number(value: float | int | None) -> str:
    """Format a numeric value exactly as the application emits G-code numbers."""
    if value is None:
        return ""
    if value == 0:
        return "0"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def last_index(values: Sequence[object], target: object) -> int | None:
    """Return the last index of target, or None when it is absent."""
    for index in reversed(range(len(values))):
        if values[index] == target:
            return index
    return None


def has_motion(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
) -> bool:
    """Return whether the coordinate sequence contains any non-zero motion."""
    points = list(zip(x_values, y_values, z_values))
    total_length = 0.0

    for index in range(1, len(points)):
        total_length += sqrt(
            (points[index][0] - points[index - 1][0]) ** 2
            + (points[index][1] - points[index - 1][1]) ** 2
            + (points[index][2] - points[index - 1][2]) ** 2
        )
        if total_length > 0:
            return True

    return False


def calculate_toolpath_metrics(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
    feeds: Sequence[float],
) -> tuple[list[float], list[float], bool]:
    """Calculate segment lengths and times using the application's existing rules."""
    points = list(zip(x_values, y_values, z_values, feeds))
    lengths: list[float] = []
    times: list[float] = []

    for index in range(1, len(points)):
        length = sqrt(
            (points[index][0] - points[index - 1][0]) ** 2
            + (points[index][1] - points[index - 1][1]) ** 2
            + (points[index][2] - points[index - 1][2]) ** 2
        )
        feed = points[index][3]
        segment_time = length / feed if feed > 0 else 0
        lengths.append(length)
        times.append(segment_time)

    return lengths, times, bool(points)


def calculate_scene_geometry(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
) -> tuple[tuple[float, float, float], float]:
    """Return plot center and distance scale using the application's existing formula."""
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    z_min, z_max = min(z_values), max(z_values)

    center = (
        x_min + (x_max - x_min) / 2,
        y_min + (y_max - y_min) / 2,
        z_min + (z_max - z_min) / 2,
    )
    diagonal = int(sqrt((x_max - x_min) ** 2 + (y_max - y_min) ** 2))
    distance = diagonal + diagonal * 0.5
    return center, distance
