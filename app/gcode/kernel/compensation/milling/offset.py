"""Standalone line/arc offset construction for milling cutter compensation."""

from __future__ import annotations

import math
from dataclasses import replace

from ...api.types import TraceMotion
from ..common import EPS
from .projection import _project_motion, _ProjectedMotion


def _tool_radius(tool: dict[str, object] | None) -> float | None:
    if not isinstance(tool, dict):
        return None
    tool_type = str(tool.get("type", "")).lower()
    if tool_type not in {"mill_flat", "mill_bull", "mill_ball"}:
        return None
    try:
        diameter = float(tool.get("diameter", 0.0))
    except (TypeError, ValueError):
        return None
    return diameter * 0.5 if diameter > 0.0 else None


def _offset_line(projected: _ProjectedMotion, distance: float) -> _ProjectedMotion | None:
    dx = projected.end[0] - projected.start[0]
    dy = projected.end[1] - projected.start[1]
    length = math.hypot(dx, dy)
    if length <= EPS:
        return None
    nx, ny = -dy / length, dx / length
    shift = nx * distance, ny * distance
    return replace(
        projected,
        start=(projected.start[0] + shift[0], projected.start[1] + shift[1]),
        end=(projected.end[0] + shift[0], projected.end[1] + shift[1]),
    )


def _offset_arc(
    projected: _ProjectedMotion,
    distance: float,
    geometry_tolerance: float,
) -> _ProjectedMotion | None:
    assert projected.center is not None and projected.radius is not None
    center = projected.center
    rsx, rsy = projected.start[0] - center[0], projected.start[1] - center[1]
    rex, rey = projected.end[0] - center[0], projected.end[1] - center[1]
    r_start = math.hypot(rsx, rsy)
    r_end = math.hypot(rex, rey)
    if r_start <= EPS or r_end <= EPS:
        return None
    if abs(r_start - r_end) > max(geometry_tolerance, 1e-6):
        return None

    radius = 0.5 * (r_start + r_end)
    offset_radius = radius - distance if projected.source.move == 3 else radius + distance
    if offset_radius <= EPS:
        return None

    start_scale = offset_radius / r_start
    end_scale = offset_radius / r_end
    start = center[0] + rsx * start_scale, center[1] + rsy * start_scale
    end = center[0] + rex * end_scale, center[1] + rey * end_scale
    return replace(projected, start=start, end=end, radius=offset_radius)


def _solve_standalone(
    motion: TraceMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> _ProjectedMotion | None:
    if tool_radius <= EPS or comp_mode not in (41, 42):
        return None
    projected = _project_motion(motion)
    if projected is None:
        return None
    signed_offset = tool_radius if comp_mode == 41 else -tool_radius
    if projected.is_line:
        return _offset_line(projected, signed_offset)
    return _offset_arc(projected, signed_offset, geometry_tolerance)
