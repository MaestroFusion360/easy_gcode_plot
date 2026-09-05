"""Pure consumers of the kernel's already-resolved logical motion trace.

Arc semantics belong to the kernel.  Rendering, statistics, and export may
sample or serialize a resolved arc, but must not choose an alternative IJK/R
interpretation after execution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .kernel import ExecutionResult, TraceMotion

ARC_RELATIVE = 1
ARC_ABSOLUTE = 2
ARC_RADIUS = 3


class RenderLimitExceeded(ValueError):
    """Raised when trace sampling would exceed an explicit point budget."""


@dataclass(frozen=True)
class RenderPoint:
    x: float
    y: float
    z: float
    feed: float | None
    source_block: int | None
    motion_index: int
    i: float | None = None
    j: float | None = None
    k: float | None = None


def _plot_move_for_plane(move: int, plane: int) -> int:
    """Map controller G2/G3 to the 2D plotting orientation of a plane.

    G18 is XZ, whose handedness is opposite to XY/YZ when represented as the
    usual 2D (first-axis, second-axis) plotting plane.  CncKernelCli and
    fanuc_plot both swap G2/G3 here.
    """
    if plane == 18:
        if move == 2:
            return 3
        if move == 3:
            return 2
    return move


def _plane_coordinates(m: TraceMotion, x_scale: float = 1.0):
    if m.plane == 18:
        return (m.start_x * x_scale, m.start_z), (m.end_x * x_scale, m.end_z), m.start_y, m.end_y
    if m.plane == 19:
        return (m.start_y, m.start_z), (m.end_y, m.end_z), m.start_x, m.end_x
    return (m.start_x, m.start_y), (m.end_x, m.end_y), m.start_z, m.end_z


def arc_geometry(
    m: TraceMotion,
    *,
    arc_type: int = ARC_RELATIVE,
    lathe_radius_view: bool = False,
):
    """Resolve one logical arc using the same plane semantics as CncKernelCli."""
    if m.move not in (2, 3) or m.plane not in (17, 18, 19):
        return None

    if m.arc is None:
        return None
    start, end, orth0, orth1 = _plane_coordinates(m, m.x_scale)
    c = m.arc.center
    center = (c[0], c[2]) if m.plane == 18 else ((c[1], c[2]) if m.plane == 19 else (c[0], c[1]))
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    return start, end, orth0, orth1, center, a0, m.arc.sweep, m.arc.radius


def _xyz_from_plane(plane: int, a: float, b: float, orth: float):
    if plane == 18:
        return a, orth, b
    if plane == 19:
        return orth, a, b
    return a, b, orth


def sample_motion(
    m: TraceMotion,
    motion_index: int,
    *,
    arc_points_per_circle: int = 314,
    lathe_radius_view: bool = False,
    arc_type: int = ARC_RELATIVE,
    max_points: int | None = None,
) -> list[RenderPoint]:
    scale_x = 0.5 if lathe_radius_view else 1.0
    if m.move not in (2, 3):
        if max_points is not None and max_points < 1:
            raise RenderLimitExceeded("Trace render point limit exceeded")
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    geom = arc_geometry(m, arc_type=arc_type, lathe_radius_view=lathe_radius_view)
    if geom is None:
        if max_points is not None and max_points < 1:
            raise RenderLimitExceeded("Trace render point limit exceeded")
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    _, _, orth0, orth1, center, a0, sweep, radius = geom
    count = max(1, int(round(arc_points_per_circle * sweep / (2.0 * math.pi))))
    if max_points is not None and count > max_points:
        raise RenderLimitExceeded("Trace render point limit exceeded")
    plot_move = _plot_move_for_plane(m.move, m.plane)
    out: list[RenderPoint] = []
    for n in range(1, count + 1):
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


def render_trace(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    arc_points_per_circle: int = 314,
    arc_type: int = ARC_RELATIVE,
    max_points: int | None = None,
) -> list[RenderPoint]:
    if max_points is not None and (not isinstance(max_points, int) or max_points <= 0):
        raise ValueError("max_points must be a positive integer")
    out: list[RenderPoint] = []
    for idx, m in enumerate(result.motions):
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
                lathe_radius_view=lathe_radius_view,
                arc_type=arc_type,
                max_points=remaining,
            )
        )
    return out


def motion_length(
    m: TraceMotion,
    *,
    lathe_radius_view: bool = False,
    arc_type: int = ARC_RELATIVE,
) -> float:
    """Return physical tool-centre length in millimetres.

    ``lathe_radius_view`` is retained for API compatibility but display mode must
    not change physical statistics.  Turning traces carry ``x_scale=0.5`` when
    their programmed X is diameter-space.
    """
    del lathe_radius_view
    sx = m.start_x * m.x_scale
    ex = m.end_x * m.x_scale
    if m.move in (2, 3):
        geom = arc_geometry(m, arc_type=arc_type)
        if geom:
            _, _, orth0, orth1, _, _, sweep, radius = geom
            return math.hypot(radius * sweep, orth1 - orth0)
    return math.sqrt((ex - sx) ** 2 + (m.end_y - m.start_y) ** 2 + (m.end_z - m.start_z) ** 2)


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


def trace_statistics(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    rapid_feed: float = 10000.0,
    arc_type: int = ARC_RELATIVE,
) -> dict[str, object]:
    """Derive geometry and time only from the executed logical trace.

    Feed-per-revolution motions require a known spindle RPM.  When execution
    cannot establish a numeric feed rate (for example active CSS without a
    resolved spindle speed), timing is explicitly partial instead of silently
    treating F as mm/min.
    """
    lengths: list[float] = []
    times: list[float | None] = []
    known_time = 0.0
    unknown_time_motion_count = 0

    for m in result.motions:
        length = motion_length(m, arc_type=arc_type)
        lengths.append(length)
        if length <= 1e-15:
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
        times.append(time)
        if time is None:
            unknown_time_motion_count += 1
        else:
            known_time += time

    coords: list[tuple[float, float, float]] = []
    display_x_scale = 0.5 if lathe_radius_view else 1.0
    for m in result.motions:
        coords.extend(
            (
                (m.start_x * display_x_scale, m.start_y, m.start_z),
                (m.end_x * display_x_scale, m.end_y, m.end_z),
            )
        )
        if m.move in (2, 3):
            geom = arc_geometry(m, arc_type=arc_type)
            if geom is not None:
                _start, _end, orth0, orth1, center, a0, sweep, radius = geom
                plot_move = _plot_move_for_plane(m.move, m.plane)
                for angle in (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
                    delta = ((a0 - angle) % (2.0 * math.pi)) if plot_move == 2 else ((angle - a0) % (2.0 * math.pi))
                    if delta <= sweep + 1e-12:
                        t = 0.0 if sweep <= 1e-12 else delta / sweep
                        orth = orth0 + (orth1 - orth0) * t
                        a = center[0] + radius * math.cos(angle)
                        b = center[1] + radius * math.sin(angle)
                        x, y, z = _xyz_from_plane(m.plane, a, b, orth)
                        # Arc geometry is physical; bounds use the same X-space
                        # requested by the caller as the endpoint coordinates.
                        x *= display_x_scale / m.x_scale
                        coords.append((x, y, z))

    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    zs = [p[2] for p in coords]
    time_complete = unknown_time_motion_count == 0
    return {
        "lengths": lengths,
        "times": times,
        "total_length": sum(lengths),
        "total_time_min": known_time if time_complete else None,
        "known_time_min": known_time,
        "time_complete": time_complete,
        "unknown_time_motion_count": unknown_time_motion_count,
        "bounds": ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))) if xs else None,
        "motion_count": len(result.motions),
        "rapid_count": sum(m.move == 0 for m in result.motions),
        "arc_count": sum(m.move in (2, 3) for m in result.motions),
        "cycle_count": sum(m.cycle_generated for m in result.motions),
    }
