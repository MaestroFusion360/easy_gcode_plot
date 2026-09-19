"""Arc geometry for turning profile segments: center, sweep and sampling."""

from __future__ import annotations

import math

from ..frontend.model import ArcGeom, Point2, ProfileSegment
from ..frontend.program import move_for_xz_plot


def normalize_sweep(gcode: int, start_a: float, end_a: float) -> float:
    gcode = move_for_xz_plot(gcode)
    sweep = end_a - start_a
    if gcode == 2 and sweep > 0:
        sweep -= 2.0 * math.pi
    if gcode == 3 and sweep < 0:
        sweep += 2.0 * math.pi
    return sweep


def score_center_candidate(seg: ProfileSegment, center: Point2, x_scale: float) -> float:
    sx = seg.start.x * x_scale
    sz = seg.start.z
    ex = seg.end.x * x_scale
    ez = seg.end.z
    cx = center.x * x_scale
    cz = center.z

    r0 = math.hypot(sx - cx, sz - cz)
    r1 = math.hypot(ex - cx, ez - cz)
    if r0 <= 1e-9 or r1 <= 1e-9:
        return float("inf")

    score = abs(r0 - r1)
    a0 = math.atan2(sz - cz, sx - cx)
    a1 = math.atan2(ez - cz, ex - cx)
    sw = normalize_sweep(seg.move, a0, a1)
    plot_move = move_for_xz_plot(seg.move)
    dir_ok = sw <= 0 if plot_move == 2 else sw >= 0
    if not dir_ok:
        score += 10.0
    return score


def arc_center_from_r(start: Point2, end: Point2, radius: float, move: int, x_scale: float = 1.0) -> Point2 | None:
    # Use ConvertPlot.CircMove(type==2) center selection logic.
    signed_r = radius
    rr = abs(signed_r)
    if rr <= 1e-12:
        return None

    sx = start.x * x_scale
    sy = start.z
    ex = end.x * x_scale
    ey = end.z
    dx = sx - ex
    dy = sy - ey
    d = math.hypot(dx, dy)
    if d <= 1e-12 or rr < (d * 0.5):
        return None

    half_d = d * 0.5
    h = math.sqrt(max(0.0, (rr * rr) - (half_d * half_d)))
    mapped_move = move_for_xz_plot(move)

    if signed_r > 0.0:
        if mapped_move == 2:
            cx = sx + (ex - sx) * 0.5 + h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 - h * (ex - sx) / d
        else:
            cx = sx + (ex - sx) * 0.5 - h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 + h * (ex - sx) / d
    else:
        if mapped_move == 2:
            cx = sx + (ex - sx) * 0.5 - h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 + h * (ex - sx) / d
        else:
            cx = sx + (ex - sx) * 0.5 + h * (ey - sy) / d
            cy = sy + (ey - sy) * 0.5 - h * (ex - sx) / d

    return Point2(cx / x_scale, cy)


def try_get_arc_geometry(seg: ProfileSegment) -> ArcGeom | None:
    if seg.has_center:
        r0 = math.hypot((seg.start.x - seg.center.x) * 0.5, seg.start.z - seg.center.z)
        r1 = math.hypot((seg.end.x - seg.center.x) * 0.5, seg.end.z - seg.center.z)
        if r0 > 1e-10 and abs(r0 - r1) <= max(0.002, r0 * 1e-5):
            return ArcGeom(seg.center, 0.5)
        raise ValueError("Invalid profile I/K arc geometry")
    if seg.has_radius:
        center = arc_center_from_r(seg.start, seg.end, seg.radius, seg.move, x_scale=0.5)
        if center is not None:
            return ArcGeom(center, 0.5)
        raise ValueError("Invalid profile R arc geometry")

    return None


def try_compute_signed_arc_radius_from_center(move: int, start: Point2, end: Point2, center: Point2) -> float | None:
    sx = start.x * 0.5
    ex = end.x * 0.5
    cx = center.x * 0.5
    rr = math.hypot(sx - cx, start.z - center.z)
    if rr <= 1e-9:
        return None
    a0 = math.atan2(start.z - center.z, sx - cx)
    a1 = math.atan2(end.z - center.z, ex - cx)
    sw = normalize_sweep(move, a0, a1)
    return rr if abs(sw) <= math.pi + 1e-6 else -rr


def arc_progress01(seg: ProfileSegment, geom: ArcGeom, p: Point2) -> float:
    sx = seg.start.x * geom.x_scale
    sy = seg.start.z
    ex = seg.end.x * geom.x_scale
    ey = seg.end.z
    px = p.x * geom.x_scale
    py = p.z
    cx = geom.center.x * geom.x_scale
    cy = geom.center.z

    rad = math.hypot(sx - cx, sy - cy)
    if rad <= 1e-9:
        return 0.0
    mapped_move = move_for_xz_plot(seg.move)

    st_ang = math.atan2(cy - sy, cx - sx) - math.atan2(0.0, -rad)
    if st_ang < 0.0:
        st_ang += 2.0 * math.pi

    if mapped_move == 2:
        full = math.atan2(cy - sy, cx - sx) - math.atan2(cy - ey, cx - ex)
        part = math.atan2(cy - sy, cx - sx) - math.atan2(cy - py, cx - px)
    else:
        full = math.atan2(cy - ey, cx - ex) - math.atan2(cy - sy, cx - sx)
        part = math.atan2(cy - py, cx - px) - math.atan2(cy - sy, cx - sx)

    if full <= 0.0:
        full += 2.0 * math.pi
    if part <= 0.0:
        part += 2.0 * math.pi
    if mapped_move == 2:
        full = -abs(full)
        part = -abs(part)
    if abs(full) <= 1e-12:
        return 0.0
    return part / full


def is_point_on_arc(seg: ProfileSegment, geom: ArcGeom, p: Point2) -> bool:
    t = arc_progress01(seg, geom, p)
    return -1e-4 <= t <= 1.0001


def segment_points(seg: ProfileSegment, s: Point2, e: Point2) -> list[Point2]:
    pts = [s]
    if seg.move in (2, 3):
        g = try_get_arc_geometry(seg)
        if g is not None:
            sx = s.x * g.x_scale
            sy = s.z
            ex = e.x * g.x_scale
            ey = e.z
            cx = g.center.x * g.x_scale
            cy = g.center.z
            r = math.hypot(sx - cx, sy - cy)
            if r <= 1e-9:
                pts.append(e)
                return pts
            mapped_move = move_for_xz_plot(seg.move)
            st_ang = math.atan2(cy - sy, cx - sx) - math.atan2(0.0, -r)
            if st_ang < 0.0:
                st_ang += 2.0 * math.pi
            if mapped_move == 2:
                sw = math.atan2(cy - sy, cx - sx) - math.atan2(cy - ey, cx - ex)
            else:
                sw = math.atan2(cy - ey, cx - ex) - math.atan2(cy - sy, cx - sx)
            if sw <= 0.0:
                sw += 2.0 * math.pi
            if mapped_move == 2:
                sw = -abs(sw)
            count = max(48, int(math.ceil(abs(sw) / (math.pi / 64.0))))
            for i in range(1, count):
                t = i / count
                a = st_ang + sw * t
                x_scaled = cx + r * math.cos(a)
                z = cy + r * math.sin(a)
                pts.append(Point2(x_scaled / g.x_scale, z))
    pts.append(e)
    return pts
