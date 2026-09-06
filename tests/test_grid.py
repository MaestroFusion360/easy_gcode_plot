from __future__ import annotations

import pytest

from app.ui.plot_grid import adaptive_grid_geometry, adaptive_grid_step


@pytest.mark.parametrize(
    ("world_units_per_pixel", "expected"),
    [(0.01, 1.0), (0.02, 2.0), (0.05, 5.0), (0.1, 10.0), (1.0, 100.0)],
)
def test_adaptive_grid_uses_exact_1_2_5_steps(world_units_per_pixel, expected):
    assert adaptive_grid_step(world_units_per_pixel) == pytest.approx(expected)


def test_adaptive_grid_changes_step_with_zoom_and_bounds_line_count():
    near_step, _ = adaptive_grid_geometry(100, 60, 600)
    far_step, _ = adaptive_grid_geometry(1000, 60, 600)
    assert near_step < far_step

    step, size = adaptive_grid_geometry(1e12, 60, 1, viewport_width=10_000, max_lines=200)
    assert size / step <= 200
