"""Geometry and timing statistics over the resolved execution trace."""

from __future__ import annotations

import math

from app.gcode.kernel import ExecutionResult, TraceMotion
from app.gcode.trace.geometry import (
    _arc_extreme_coordinates,
    _motion_z_min,
    _plot_move_for_plane,
    _xyz_from_plane,
    arc_geometry,
    motion_length,
)


def _css_time_minutes(m: TraceMotion, length: float) -> float | None:
    """Integrate deterministic G96 feed-per-revolution time over one resolved motion."""
    speed = m.surface_speed_m_min
    feed = m.feed
    if speed is None or speed <= 0 or feed is None or feed <= 0:
        return None
    limit = m.spindle_limit_rpm if m.spindle_limit_rpm is not None and m.spindle_limit_rpm > 0 else None

    def rpm_for_radius(radius_x: float) -> float:
        diameter = 2.0 * abs(radius_x)
        if diameter <= 1e-12:
            return limit if limit is not None else math.inf
        rpm = 1000.0 * speed / (math.pi * diameter)
        return min(rpm, limit) if limit is not None else rpm

    if m.move not in (2, 3) or m.arc is None:
        sx = m.start_x * m.x_scale
        ex = m.end_x * m.x_scale
        if length <= 1e-15:
            return 0.0

        def integrand(t: float) -> float:
            rpm = rpm_for_radius(sx + (ex - sx) * t)
            return 0.0 if math.isinf(rpm) else length / (feed * rpm)
    else:
        geom = arc_geometry(m)
        if geom is None:
            return None
        _start, _end, orth0, orth1, center, a0, sweep, radius = geom
        direction = -1.0 if _plot_move_for_plane(m.move, m.plane) == 2 else 1.0
        ds_dt = math.hypot(radius * sweep, orth1 - orth0)

        def integrand(t: float) -> float:
            angle = a0 + direction * sweep * t
            a = center[0] + radius * math.cos(angle)
            b = center[1] + radius * math.sin(angle)
            orth = orth0 + (orth1 - orth0) * t
            x, _y, _z = _xyz_from_plane(m.plane, a, b, orth)
            rpm = rpm_for_radius(x)
            return 0.0 if math.isinf(rpm) else ds_dt / (feed * rpm)

    def simpson(a: float, b: float, fa: float, fm: float, fb: float) -> float:
        return (b - a) * (fa + 4.0 * fm + fb) / 6.0

    def integrate(a: float, b: float, fa: float, fm: float, fb: float, whole: float, depth: int) -> float:
        mid = (a + b) * 0.5
        lm, rm = (a + mid) * 0.5, (mid + b) * 0.5
        flm, frm = integrand(lm), integrand(rm)
        left = simpson(a, mid, fa, flm, fm)
        right = simpson(mid, b, fm, frm, fb)
        total = left + right
        if depth <= 0 or abs(total - whole) <= max(1e-12, abs(total) * 1e-9):
            return total + (total - whole) / 15.0
        return integrate(a, mid, fa, flm, fm, left, depth - 1) + integrate(mid, b, fm, frm, fb, right, depth - 1)

    fa, fm, fb = integrand(0.0), integrand(0.5), integrand(1.0)
    return integrate(0.0, 1.0, fa, fm, fb, simpson(0.0, 1.0, fa, fm, fb), 12)


def _motion_time_minutes(m, length, rapid_feed):
    if m.move != 0 and m.feed_mode == "inverse_time":
        time = 1.0 / m.feed if m.feed is not None and m.feed > 0 else None
    elif length <= 1e-15:
        time = 0.0
    elif m.move == 0:
        time = length / rapid_feed if rapid_feed > 0 else None
    elif m.feed is None or m.feed <= 0:
        time = None
    elif m.feed_mode == "per_revolution":
        if m.spindle_mode == "css":
            time = _css_time_minutes(m, length)
        else:
            rpm = m.spindle_rpm
            time = length / (m.feed * rpm) if rpm is not None and rpm > 0 else None
    else:
        time = length / m.feed
    return time


def _motion_timings(motions, rapid_feed: float):
    """Return per-motion lengths and times plus the known-time total and unknown-time count."""
    lengths: list[float] = []
    times: list[float | None] = []
    known_time = 0.0
    unknown_time_motion_count = 0
    for m in motions:
        length = motion_length(m)
        lengths.append(length)
        time = _motion_time_minutes(m, length, rapid_feed)
        times.append(time)
        if time is None:
            unknown_time_motion_count += 1
        else:
            known_time += time
    return lengths, times, known_time, unknown_time_motion_count


def _motion_bounds(motions, display_x_scale):
    """Retain per-motion bounds without retaining every intermediate coordinate."""
    for motion in motions:
        points = [
            (motion.start_x * display_x_scale, motion.start_y, motion.start_z),
            (motion.end_x * display_x_scale, motion.end_y, motion.end_z),
        ]
        if motion.move in (2, 3):
            points.extend(_arc_extreme_coordinates(motion, display_x_scale))
        yield tuple((min(p[axis] for p in points), max(p[axis] for p in points)) for axis in range(3))


def _summarize_motions(motions, indices, lengths, times, motion_bounds) -> dict[str, object]:
    """Aggregate counts, bounds, lengths and times for the motions selected by ``indices``."""
    rapid = [i for i in indices if motions[i].move == 0]
    feed = [i for i in indices if motions[i].move != 0]
    rapid_time = sum(times[i] for i in rapid if times[i] is not None)
    feed_time = sum(times[i] for i in feed if times[i] is not None)
    feed_complete = all(times[i] is not None for i in feed)
    feed_length = sum(lengths[i] for i in feed)
    return {
        "motion_count": len(indices),
        "rapid_count": len(rapid),
        "arc_count": sum(motions[i].move in (2, 3) for i in indices),
        "cycle_count": sum(motions[i].cycle_generated for i in indices),
        "bounds": tuple(
            (min(motion_bounds[i][axis][0] for i in indices), max(motion_bounds[i][axis][1] for i in indices))
            for axis in range(3)
        )
        if indices
        else None,
        "z_min": min((_motion_z_min(motions[i]) for i in indices), default=None),
        "total_length": sum(lengths[i] for i in indices),
        "rapid_length": sum(lengths[i] for i in rapid),
        "feed_length": feed_length,
        "known_time_min": rapid_time + feed_time,
        "rapid_time_min": rapid_time if all(times[i] is not None for i in rapid) else None,
        "feed_time_min": feed_time if feed_complete else None,
        "average_feed_mm_min": feed_length / feed_time if feed_complete and feed_time > 0 else None,
        "unknown_time_motion_count": sum(times[i] is None for i in indices),
    }


def _execution_status(result: ExecutionResult, warning_count: int) -> str:
    if not result.ok or not result.complete:
        return "ERRORS"
    return "WARNINGS" if warning_count else "CLEAN"


def trace_statistics(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    rapid_feed: float = 10000.0,
) -> dict[str, object]:
    """Derive geometry and time only from the executed logical trace.

    Feed-per-revolution motions require a known spindle RPM.  When execution
    cannot establish a numeric feed rate (for example active CSS without a
    resolved spindle speed), timing is explicitly partial instead of silently
    treating F as mm/min.
    """
    motions = result.motions
    lengths, times, known_time, unknown_time_motion_count = _motion_timings(motions, rapid_feed)
    motion_bounds = list(_motion_bounds(motions, 0.5 if lathe_radius_view else 1.0))
    time_complete = unknown_time_motion_count == 0 and result.ok and result.complete

    by_tool: dict[str, list[int]] = {}
    for index, motion in enumerate(motions):
        by_tool.setdefault(motion.tool or "unknown", []).append(index)
    warning_count = sum(d.severity == "warning" for d in result.diagnostics)
    summary = _summarize_motions(motions, range(len(motions)), lengths, times, motion_bounds)
    return {
        **summary,
        "per_tool": {
            tool: _summarize_motions(motions, indices, lengths, times, motion_bounds)
            for tool, indices in by_tool.items()
        },
        "execution_complete": result.ok and result.complete,
        "warning_count": warning_count,
        "execution_status": _execution_status(result, warning_count),
        "executed_step_count": len(result.execution_steps),
        "rapid_feed_mm_min": rapid_feed,
        "lengths": lengths,
        "times": times,
        "total_time_min": known_time if time_complete else None,
        "known_time_min": known_time,
        "time_complete": time_complete,
        "unknown_time_motion_count": unknown_time_motion_count,
    }
