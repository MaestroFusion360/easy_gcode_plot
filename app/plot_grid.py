"""Pure helpers for keeping the lathe grid readable at every zoom level."""

from __future__ import annotations

import math


def adaptive_grid_step(world_units_per_pixel: float, target_pixels: float = 60.0) -> float:
    """Return the next 1/2/5 world step at least ``target_pixels`` apart."""
    scale = max(float(world_units_per_pixel), 1e-9)
    raw_step = max(target_pixels * scale, 1e-9)
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    for multiplier in (1.0, 2.0, 5.0, 10.0):
        candidate = multiplier * magnitude
        if candidate >= raw_step:
            return candidate
    return 10.0 * magnitude


def adaptive_grid_geometry(
    camera_distance: float,
    field_of_view_degrees: float,
    viewport_height: int,
    *,
    viewport_width: int | None = None,
    max_lines: int = 200,
) -> tuple[float, float]:
    """Return ``(spacing, size)`` for a bounded grid covering the viewport."""
    height = max(1, int(viewport_height))
    half_angle = math.radians(max(0.01, float(field_of_view_degrees))) * 0.5
    visible_height = max(1e-9, 2.0 * max(float(camera_distance), 1e-9) * math.tan(half_angle))
    world_units_per_pixel = visible_height / height
    visible_span = world_units_per_pixel * max(height, int(viewport_width or height))
    step = adaptive_grid_step(world_units_per_pixel)
    line_count = min(max_lines, max(4, math.ceil(visible_span / step) + 4))
    return step, step * line_count
