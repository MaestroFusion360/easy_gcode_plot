"""Auto-sized turning stock bounds from resolved execution motions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from app.gcode.kernel import TraceMotion
from app.gcode.trace_tools import _plot_move_for_plane, arc_geometry

_TWO_PI = 2.0 * math.pi
_EPS = 1e-12


@dataclass(frozen=True)
class TurningStockSuggestion:
    """Minimal outside stock envelope inferred from cutting motions."""

    outer_diameter: float
    inner_diameter: float
    length: float


def _normalize_positive(angle: float) -> float:
    return angle % _TWO_PI


def _angle_on_sweep(start: float, target: float, sweep: float, direction: float) -> bool:
    if sweep >= _TWO_PI - _EPS:
        return True
    if direction >= 0.0:
        delta = (_normalize_positive(target) - _normalize_positive(start)) % _TWO_PI
    else:
        delta = (_normalize_positive(start) - _normalize_positive(target)) % _TWO_PI
    return delta <= sweep + _EPS


def _cutting_points(motion: TraceMotion) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = [
        (motion.start_x * motion.x_scale, motion.start_z),
        (motion.end_x * motion.x_scale, motion.end_z),
    ]
    if motion.move not in (2, 3) or motion.arc is None or motion.plane != 18:
        return tuple(points)
    geometry = arc_geometry(motion)
    if geometry is None:
        return tuple(points)
    _start, _end, _orth0, _orth1, center, start_angle, sweep, radius = geometry
    plot_move = _plot_move_for_plane(motion.move, motion.plane)
    direction = -1.0 if plot_move == 2 else 1.0
    for angle in (0.0, math.pi, math.pi * 1.5):
        if _angle_on_sweep(start_angle, angle, sweep, direction):
            points.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    return tuple(points)


def auto_turning_stock_suggestion(motions: Iterable[TraceMotion] | None) -> TurningStockSuggestion | None:
    """Infer minimal OD and length from resolved G1/G2/G3 cutting motions only."""
    maximum_radius = 0.0
    minimum_z: float | None = None
    saw_cutting_motion = False
    for motion in motions or ():
        if motion.move not in (1, 2, 3):
            continue
        saw_cutting_motion = True
        for radius_value, z_value in _cutting_points(motion):
            maximum_radius = max(maximum_radius, abs(float(radius_value)))
            minimum_z = float(z_value) if minimum_z is None else min(minimum_z, float(z_value))
    if not saw_cutting_motion or minimum_z is None:
        return None
    return TurningStockSuggestion(
        outer_diameter=maximum_radius * 2.0,
        inner_diameter=0.0,
        length=max(0.0, -minimum_z),
    )


def stock_outline_bounds(spec) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Return an X/Y/Z bounds tuple for the visible turning stock outline."""
    outer = float(spec.outer_diameter) * 0.5
    return ((-outer, outer), (0.0, 0.0), (float(spec.front_z) - float(spec.length), float(spec.front_z)))
