"""Polyline clipping and cycle entry search for turning profiles."""

from __future__ import annotations

import math

from ..frontend.model import Point2, ProfileSegment
from .profile_arcs import arc_progress01, is_point_on_arc, try_get_arc_geometry


def intersect_at_x(a: Point2, b: Point2, x: float) -> Point2:
    dx = b.x - a.x
    if abs(dx) <= 1e-9:
        return Point2(x, a.z)
    t = max(0.0, min(1.0, (x - a.x) / dx))
    return Point2(x, a.z + (b.z - a.z) * t)


def clip_polyline_max_x(polyline: list[Point2], max_x: float) -> list[Point2]:
    if not polyline:
        return []
    out: list[Point2] = []
    prev = polyline[0]
    prev_in = prev.x <= max_x + 1e-5
    if prev_in:
        out.append(prev)
    for curr in polyline[1:]:
        curr_in = curr.x <= max_x + 1e-5
        if prev_in and curr_in:
            out.append(curr)
        elif prev_in and not curr_in:
            hit = intersect_at_x(prev, curr, max_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
        elif not prev_in and curr_in:
            hit = intersect_at_x(prev, curr, max_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
            out.append(curr)
        prev = curr
        prev_in = curr_in
    return out


def clip_polyline_min_x(polyline: list[Point2], min_x: float) -> list[Point2]:
    if not polyline:
        return []
    out: list[Point2] = []
    prev = polyline[0]
    prev_in = prev.x >= min_x - 1e-5
    if prev_in:
        out.append(prev)
    for curr in polyline[1:]:
        curr_in = curr.x >= min_x - 1e-5
        if prev_in and curr_in:
            out.append(curr)
        elif prev_in and not curr_in:
            hit = intersect_at_x(prev, curr, min_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
        elif not prev_in and curr_in:
            hit = intersect_at_x(prev, curr, min_x)
            if not out or abs(out[-1].x - hit.x) > 1e-5 or abs(out[-1].z - hit.z) > 1e-5:
                out.append(hit)
            out.append(curr)
        prev = curr
        prev_in = curr_in
    return out


def try_find_entry_on_profile(profile: list[ProfileSegment], pass_x: float) -> tuple[int, Point2] | None:
    best: tuple[int, Point2] | None = None
    best_z = float("inf")

    for i, seg in enumerate(profile):
        if seg.move in (2, 3):
            g = try_get_arc_geometry(seg)
            if g is None:
                continue
            sx = seg.start.x * g.x_scale
            cx = g.center.x * g.x_scale
            pass_x_scaled = pass_x * g.x_scale
            r = math.hypot(sx - cx, seg.start.z - g.center.z)
            dx = pass_x_scaled - cx
            disc = r * r - dx * dx
            if disc < -1e-6:
                continue
            disc = max(0.0, disc)
            root = math.sqrt(disc)
            cands = [Point2(pass_x_scaled / g.x_scale, g.center.z + root)]
            if root > 1e-6:
                cands.append(Point2(pass_x_scaled / g.x_scale, g.center.z - root))

            best_arc: Point2 | None = None
            best_prog = float("-inf")
            for p in cands:
                if not is_point_on_arc(seg, g, p):
                    continue
                prog = arc_progress01(seg, g, p)
                if prog > best_prog:
                    best_prog = prog
                    best_arc = p
            if best_arc is not None and best_arc.z < best_z:
                best_z = best_arc.z
                best = (i, best_arc)
            continue

        x1, z1 = seg.start.x, seg.start.z
        x2, z2 = seg.end.x, seg.end.z
        if pass_x < min(x1, x2) - 1e-5 or pass_x > max(x1, x2) + 1e-5:
            continue
        if abs(x2 - x1) <= 1e-8:
            z = min(z1, z2)
        else:
            t = (pass_x - x1) / (x2 - x1)
            if t < -1e-5 or t > 1.00001:
                continue
            t = max(0.0, min(1.0, t))
            z = z1 + (z2 - z1) * t
        if z < best_z:
            best_z = z
            best = (i, Point2(pass_x, z))

    return best
