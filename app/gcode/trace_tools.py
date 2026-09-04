"""Pure helpers that consume kernel logical traces for rendering and statistics.

Arc interpretation follows the working CncKernelCli ArcMath contract:
IJK can be interpreted relative to the arc start, as absolute centre
coordinates, or ignored in favour of R.  The logical trace keeps source IJK/R
unchanged; only consumers choose how to interpret them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .kernel import ExecutionResult, TraceMotion

ARC_RELATIVE = 1
ARC_ABSOLUTE = 2
ARC_RADIUS = 3
_EPS = 1e-9


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


def _normalize_sweep(move: int, start_angle: float, end_angle: float) -> float:
    sweep = end_angle - start_angle
    if move == 2 and sweep > 0.0:
        sweep -= 2.0 * math.pi
    elif move == 3 and sweep < 0.0:
        sweep += 2.0 * math.pi
    return sweep


def _center_valid(start, end, center) -> bool:
    r0 = math.hypot(start[0] - center[0], start[1] - center[1])
    r1 = math.hypot(end[0] - center[0], end[1] - center[1])
    return r0 > _EPS and r1 > _EPS and abs(r0 - r1) <= max(1e-6, r0 * 1e-3)


def _center_score(start, end, center, plot_move: int) -> float:
    r0 = math.hypot(start[0] - center[0], start[1] - center[1])
    r1 = math.hypot(end[0] - center[0], end[1] - center[1])
    if r0 <= _EPS or r1 <= _EPS:
        return math.inf
    return (
        abs(r0 - r1)
        + abs(
            _normalize_sweep(
                plot_move,
                math.atan2(start[1] - center[1], start[0] - center[0]),
                math.atan2(end[1] - center[1], end[0] - center[0]),
            )
        )
        * 0.0
    )


def _center_from_offsets(
    m: TraceMotion,
    arc_type: int,
    start,
    end,
    *,
    x_scale: float,
    lathe_radius_view: bool,
):
    center = None
    if arc_type == ARC_RADIUS:
        return center

    if m.plane == 18:
        has_offsets = m.i is not None or m.k is not None
    elif m.plane == 19:
        has_offsets = m.j is not None or m.k is not None
    else:
        has_offsets = m.i is not None or m.j is not None

    if has_offsets:
        i_val = 0.0 if m.i is None else float(m.i)
        j_val = 0.0 if m.j is None else float(m.j)
        k_val = 0.0 if m.k is None else float(m.k)

        if arc_type == ARC_ABSOLUTE:
            if m.plane == 18:
                center = (i_val * x_scale, k_val)
            elif m.plane == 19:
                center = (j_val, k_val)
            else:
                center = (i_val, j_val)
        elif lathe_radius_view and m.plane == 18:
            # fanuc_plot accepts traces where I has historically appeared either
            # in diameter-space or radius-space.  Keep its deterministic best-fit
            # choice instead of guessing globally.
            plot_move = _plot_move_for_plane(m.move, m.plane)
            candidates = (
                (start[0] + i_val * x_scale, start[1] + k_val),
                (start[0] + i_val, start[1] + k_val),
            )
            valid = [(c, _center_score(start, end, c, plot_move)) for c in candidates]
            valid = [(c, score) for c, score in valid if math.isfinite(score)]
            if valid:
                center = min(valid, key=lambda item: item[1])[0]

        if center is None:
            if m.plane == 18:
                center = (start[0] + i_val * x_scale, start[1] + k_val)
            elif m.plane == 19:
                center = (start[0] + j_val, start[1] + k_val)
            else:
                center = (start[0] + i_val, start[1] + j_val)

    return center


def _center_from_radius(start, end, radius: float, plot_move: int):
    r = abs(radius)
    if r <= 1e-12:
        return None

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    chord = math.hypot(dx, dy)
    if chord <= 1e-12 or r < chord * 0.5 - 1e-9:
        return None

    mx = (start[0] + end[0]) * 0.5
    my = (start[1] + end[1]) * 0.5
    ux, uy = dx / chord, dy / chord
    nx, ny = -uy, ux
    h = math.sqrt(max(0.0, r * r - (chord * 0.5) ** 2))
    candidates = ((mx + nx * h, my + ny * h), (mx - nx * h, my - ny * h))

    def sweep(center):
        return abs(
            _normalize_sweep(
                plot_move,
                math.atan2(start[1] - center[1], start[0] - center[0]),
                math.atan2(end[1] - center[1], end[0] - center[0]),
            )
        )

    s1, s2 = sweep(candidates[0]), sweep(candidates[1])
    choose_large = radius < 0.0
    m1 = s1 > math.pi if choose_large else s1 <= math.pi
    m2 = s2 > math.pi if choose_large else s2 <= math.pi
    if m1 and not m2:
        return candidates[0]
    if m2 and not m1:
        return candidates[1]
    return candidates[0] if s1 <= s2 else candidates[1]


def arc_geometry(
    m: TraceMotion,
    *,
    arc_type: int = ARC_RELATIVE,
    lathe_radius_view: bool = False,
):
    """Resolve one logical arc using the same plane semantics as CncKernelCli."""
    if m.move not in (2, 3) or m.plane not in (17, 18, 19):
        return None

    x_scale = 0.5 if lathe_radius_view and m.plane == 18 else 1.0
    start, end, orth0, orth1 = _plane_coordinates(m, x_scale)
    center = _center_from_offsets(
        m,
        arc_type,
        start,
        end,
        x_scale=x_scale,
        lathe_radius_view=lathe_radius_view,
    )
    if center is not None and not _center_valid(start, end, center):
        center = None

    if center is None and m.radius is not None:
        center = _center_from_radius(start, end, m.radius, _plot_move_for_plane(m.move, m.plane))
    if center is None:
        return None

    radius = math.hypot(start[0] - center[0], start[1] - center[1])
    if radius <= _EPS:
        return None

    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    plot_move = _plot_move_for_plane(m.move, m.plane)
    full_circle = math.hypot(start[0] - end[0], start[1] - end[1]) <= _EPS
    sweep_signed = (
        (-2.0 * math.pi if plot_move == 2 else 2.0 * math.pi) if full_circle else _normalize_sweep(plot_move, a0, a1)
    )
    return start, end, orth0, orth1, center, a0, abs(sweep_signed), radius


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
) -> list[RenderPoint]:
    scale_x = 0.5 if lathe_radius_view else 1.0
    if m.move not in (2, 3):
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    geom = arc_geometry(m, arc_type=arc_type, lathe_radius_view=lathe_radius_view)
    if geom is None:
        return [RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)]

    _, _, orth0, orth1, center, a0, sweep, radius = geom
    count = max(1, int(round(arc_points_per_circle * sweep / (2.0 * math.pi))))
    plot_move = _plot_move_for_plane(m.move, m.plane)
    out: list[RenderPoint] = []
    for n in range(1, count + 1):
        t = n / count
        angle = a0 + (-sweep if plot_move == 2 else sweep) * t
        a = center[0] + radius * math.cos(angle)
        b = center[1] + radius * math.sin(angle)
        orth = orth0 + (orth1 - orth0) * t
        x, y, z = _xyz_from_plane(m.plane, a, b, orth)
        # G18 x is already radius-scaled inside arc_geometry for lathe view.
        if lathe_radius_view and m.plane != 18:
            x *= scale_x
        out.append(RenderPoint(x, y, z, m.feed, m.source_block, motion_index, m.i, m.j, m.k))

    out[-1] = RenderPoint(m.end_x * scale_x, m.end_y, m.end_z, m.feed, m.source_block, motion_index, m.i, m.j, m.k)
    return out


def render_trace(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    arc_points_per_circle: int = 314,
    arc_type: int = ARC_RELATIVE,
) -> list[RenderPoint]:
    out: list[RenderPoint] = []
    for idx, m in enumerate(result.motions):
        if not out:
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
        out.extend(
            sample_motion(
                m,
                idx,
                arc_points_per_circle=arc_points_per_circle,
                lathe_radius_view=lathe_radius_view,
                arc_type=arc_type,
            )
        )
    return out


def motion_length(
    m: TraceMotion,
    *,
    lathe_radius_view: bool = False,
    arc_type: int = ARC_RELATIVE,
) -> float:
    sx = m.start_x * (0.5 if lathe_radius_view else 1.0)
    ex = m.end_x * (0.5 if lathe_radius_view else 1.0)
    if m.move in (2, 3):
        geom = arc_geometry(m, arc_type=arc_type, lathe_radius_view=lathe_radius_view)
        if geom:
            _, _, orth0, orth1, _, _, sweep, radius = geom
            return math.hypot(radius * sweep, orth1 - orth0)
    return math.sqrt((ex - sx) ** 2 + (m.end_y - m.start_y) ** 2 + (m.end_z - m.start_z) ** 2)


def trace_statistics(
    result: ExecutionResult,
    *,
    lathe_radius_view: bool = False,
    rapid_feed: float = 10000.0,
    arc_type: int = ARC_RELATIVE,
) -> dict[str, object]:
    lengths: list[float] = []
    times: list[float] = []
    for m in result.motions:
        length = motion_length(m, lathe_radius_view=lathe_radius_view, arc_type=arc_type)
        feed = rapid_feed if m.move == 0 else (m.feed or 0.0)
        lengths.append(length)
        times.append(length / feed if feed > 0 else 0.0)

    coords: list[tuple[float, float, float]] = []
    scale_x = 0.5 if lathe_radius_view else 1.0
    for m in result.motions:
        coords.extend(
            (
                (m.start_x * scale_x, m.start_y, m.start_z),
                (m.end_x * scale_x, m.end_y, m.end_z),
            )
        )
        if m.move in (2, 3):
            geom = arc_geometry(m, arc_type=arc_type, lathe_radius_view=lathe_radius_view)
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
                        if lathe_radius_view and m.plane != 18:
                            x *= scale_x
                        coords.append((x, y, z))

    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    zs = [p[2] for p in coords]
    return {
        "lengths": lengths,
        "times": times,
        "total_length": sum(lengths),
        "total_time_min": sum(times),
        "bounds": ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))) if xs else None,
        "motion_count": len(result.motions),
        "rapid_count": sum(m.move == 0 for m in result.motions),
        "arc_count": sum(m.move in (2, 3) for m in result.motions),
        "cycle_count": sum(m.cycle_generated for m in result.motions),
    }
