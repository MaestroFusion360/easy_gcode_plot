"""Bounded rendering samples from resolved logical motions."""

from __future__ import annotations

import math

from app.gcode.kernel import ExecutionResult, TraceMotion
from app.gcode.kernel.geometry.spatial_arc import point_at
from app.gcode.trace.geometry import (
    RenderPoint,
    _forward_oriented_point,
    _local_oriented_arc,
    _plot_move_for_plane,
    _xyz_from_plane,
    arc_geometry,
)


class RenderLimitExceeded(ValueError):
    """Raised when trace sampling would exceed an explicit point budget."""


def _check_cancelled(cancelled) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError("Trace rendering cancelled")


def _check_cancelled_periodically(cancelled, index: int) -> None:
    if index == 1 or index % 256 == 0:
        _check_cancelled(cancelled)


def _validate_arc_sampling_limits(maximum_radius, minimum_radius, minimum_chord):
    for name, value, allow_zero in (
        ("maximum_circular_radius", maximum_radius, False),
        ("minimum_circular_radius", minimum_radius, True),
        ("minimum_chord_length", minimum_chord, True),
    ):
        if value is not None and (not math.isfinite(value) or value < 0 or (not allow_zero and value == 0)):
            requirement = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{name} must be a {requirement} finite value")


def _arc_sample_count(
    *,
    radius,
    sweep,
    full_circle,
    arc_points_per_circle,
    chord_error,
    maximum_circular_radius,
    minimum_circular_radius,
    minimum_chord_length,
):
    _validate_arc_sampling_limits(maximum_circular_radius, minimum_circular_radius, minimum_chord_length)
    if minimum_circular_radius is not None and radius < minimum_circular_radius:
        count = 1
    elif chord_error is None:
        count = max(1, int(round(arc_points_per_circle * sweep / (2.0 * math.pi))))
    elif not math.isfinite(chord_error) or chord_error <= 0:
        raise ValueError("chord_error must be a positive finite value")
    elif radius <= 0 or sweep <= 0:
        count = 1
    else:
        sampling_radius = min(radius, maximum_circular_radius) if maximum_circular_radius is not None else radius
        effective_error = min(chord_error, sampling_radius * 2.0)
        segment_angle = 4.0 * math.asin(math.sqrt(effective_error / (2.0 * sampling_radius)))
        count = 1 if segment_angle <= 0 else int(math.ceil(sweep / segment_angle))
        if minimum_chord_length:
            count = min(count, max(1, int(math.floor(radius * sweep / minimum_chord_length))))
    return max(4, count) if full_circle else count


def sample_motion(
    m: TraceMotion,
    motion_index: int,
    *,
    arc_points_per_circle: int = 314,
    chord_error: float | None = None,
    maximum_circular_radius: float | None = None,
    minimum_circular_radius: float | None = None,
    minimum_chord_length: float | None = None,
    lathe_radius_view: bool = False,
    max_points: int | None = None,
    cancelled=None,
) -> list[RenderPoint]:
    _check_cancelled(cancelled)
    if m.arc is not None and m.arc.normal is not None:
        count = _arc_sample_count(
            radius=m.arc.radius,
            sweep=m.arc.sweep,
            full_circle=m.arc.full_circle,
            arc_points_per_circle=arc_points_per_circle,
            chord_error=chord_error,
            maximum_circular_radius=maximum_circular_radius,
            minimum_circular_radius=minimum_circular_radius,
            minimum_chord_length=minimum_chord_length,
        )
        return _sample_spatial_arc(m, motion_index, count, max_points, cancelled)
    if m.orientation is not None and m.move in (2, 3) and m.arc is not None:
        local_points = sample_motion(
            _local_oriented_arc(m),
            motion_index,
            arc_points_per_circle=arc_points_per_circle,
            chord_error=chord_error,
            maximum_circular_radius=maximum_circular_radius,
            minimum_circular_radius=minimum_circular_radius,
            minimum_chord_length=minimum_chord_length,
            lathe_radius_view=lathe_radius_view,
            max_points=max_points,
            cancelled=cancelled,
        )
        return [_forward_oriented_point(m, point) for point in local_points]
    scale_x = 0.5 if lathe_radius_view else 1.0
    if m.move not in (2, 3):
        if max_points is not None and max_points < 1:
            raise RenderLimitExceeded("Trace render point limit exceeded")
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    geom = arc_geometry(m, lathe_radius_view=lathe_radius_view)
    if geom is None:
        if max_points is not None and max_points < 1:
            raise RenderLimitExceeded("Trace render point limit exceeded")
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    _, _, orth0, orth1, center, a0, sweep, radius = geom
    count = _arc_sample_count(
        radius=radius,
        sweep=sweep,
        full_circle=m.arc is not None and m.arc.full_circle,
        arc_points_per_circle=arc_points_per_circle,
        chord_error=chord_error,
        maximum_circular_radius=maximum_circular_radius,
        minimum_circular_radius=minimum_circular_radius,
        minimum_chord_length=minimum_chord_length,
    )
    if max_points is not None and count > max_points:
        raise RenderLimitExceeded("Trace render point limit exceeded")
    plot_move = _plot_move_for_plane(m.move, m.plane)
    out: list[RenderPoint] = []
    for n in range(1, count + 1):
        _check_cancelled_periodically(cancelled, n)
        t = n / count
        angle = a0 + (-sweep if plot_move == 2 else sweep) * t
        a = center[0] + radius * math.cos(angle)
        b = center[1] + radius * math.sin(angle)
        orth = orth0 + (orth1 - orth0) * t
        x, y, z = _xyz_from_plane(m.plane, a, b, orth)
        x *= scale_x / m.x_scale
        out.append(RenderPoint(x, y, z, m.feed, m.source_block, motion_index, m.i, m.j, m.k))

    out[-1] = RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)
    return out


def _sample_spatial_arc(motion, motion_index, count, max_points, cancelled):
    if max_points is not None and count > max_points:
        raise RenderLimitExceeded("Trace render point limit exceeded")
    points = []
    for index in range(1, count + 1):
        _check_cancelled_periodically(cancelled, index)
        xyz = point_at(motion, motion.arc.sweep * index / count)
        if index == count:
            xyz = (motion.end_x, motion.end_y, motion.end_z)
        points.append(RenderPoint(*xyz, motion.feed, motion.source_block, motion_index))
    return points


def render_trace(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    arc_points_per_circle: int = 314,
    chord_error: float | None = None,
    maximum_circular_radius: float | None = None,
    minimum_circular_radius: float | None = None,
    minimum_chord_length: float | None = None,
    max_points: int | None = None,
    cancelled=None,
) -> list[RenderPoint]:
    _check_cancelled(cancelled)
    if max_points is not None and (not isinstance(max_points, int) or max_points <= 0):
        raise ValueError("max_points must be a positive integer")
    out: list[RenderPoint] = []
    for idx, m in enumerate(result.motions):
        _check_cancelled(cancelled)
        if not out:
            if max_points is not None and len(out) >= max_points:
                raise RenderLimitExceeded("Trace render point limit exceeded")
            out.append(
                RenderPoint(
                    m.start_x * (0.5 if lathe_radius_view else 1.0),
                    m.start_y,
                    m.start_z,
                    m.feed,
                    m.source_block,
                    idx,
                    m.i,
                    m.j,
                    m.k,
                )
            )
        remaining = None if max_points is None else max_points - len(out)
        out.extend(
            sample_motion(
                m,
                idx,
                arc_points_per_circle=arc_points_per_circle,
                chord_error=chord_error,
                maximum_circular_radius=maximum_circular_radius,
                minimum_circular_radius=minimum_circular_radius,
                minimum_chord_length=minimum_chord_length,
                lathe_radius_view=lathe_radius_view,
                max_points=remaining,
                cancelled=cancelled,
            )
        )
    return out
