"""Profile preparation helpers shared by FANUC turning cycles."""

from __future__ import annotations

import math

from ...frontend.model import Point2, ProfileSegment
from ...geometry import segment_points


def _outward_normal_radius(prev: Point2, curr: Point2, nxt: Point2, prefer_positive_x: bool) -> Point2:
    px = prev.x * 0.5
    pz = prev.z
    nx = nxt.x * 0.5
    nz = nxt.z
    dx = nx - px
    dz = nz - pz
    ln = math.hypot(dx, dz)
    if ln <= 1e-9:
        return Point2(1.0, 0.0)
    tx = dx / ln
    tz = dz / ln
    c1 = Point2(tz, -tx)
    c2 = Point2(-tz, tx)
    if prefer_positive_x:
        return c1 if c1.x >= c2.x else c2
    return c1 if c1.x <= c2.x else c2


def build_offset_profile(
    profile: list[ProfileSegment],
    finish_u: float,
    finish_w: float,
    prefer_positive_x: bool,
) -> list[ProfileSegment]:
    if not profile:
        return []
    # U and W are independent finish allowances in the machine X and Z
    # directions.  Project that allowance vector onto the local outward normal
    # instead of collapsing both values to max(U/2, W), which over-offsets
    # tapers/arcs and can create large false Z displacements.
    radial_allow = finish_u * 0.5
    axial_allow = finish_w
    if abs(radial_allow) <= 1e-9 and abs(axial_allow) <= 1e-9:
        return profile

    dense: list[Point2] = []
    dense_groups: list[int] = []
    for group, seg in enumerate(profile):
        pts = segment_points(seg, seg.start, seg.end)
        if dense and pts:
            pts = pts[1:]
        dense.extend(pts)
        dense_groups.extend([group] * len(pts))

    if len(dense) < 2:
        return profile

    shifted: list[Point2] = []
    for i, curr in enumerate(dense):
        prev = dense[i - 1] if i > 0 else curr
        nxt = dense[i + 1] if i + 1 < len(dense) else curr
        n = _outward_normal_radius(prev, curr, nxt, prefer_positive_x)
        cxr = curr.x * 0.5
        offset_dist = n.x * radial_allow + n.z * axial_allow
        sxr = cxr + (n.x * offset_dist)
        sz = curr.z + (n.z * offset_dist)
        shifted.append(Point2(sxr * 2.0, sz))

    out: list[ProfileSegment] = []
    for index, (a, b) in enumerate(zip(shifted, shifted[1:])):
        if abs(a.x - b.x) <= 1e-6 and abs(a.z - b.z) <= 1e-6:
            continue
        out.append(
            ProfileSegment(
                block=-1,
                move=1,
                start=a,
                end=b,
                has_radius=False,
                radius=0.0,
                has_center=False,
                center=Point2(0.0, 0.0),
                playback_group=dense_groups[index + 1],
            )
        )
    return out if out else profile


def is_boring_cycle(profile: list[ProfileSegment], finish_u: float, stock_x: float) -> bool:
    if finish_u < -1e-9:
        return True
    if not profile:
        return False

    min_x = min(min(seg.start.x, seg.end.x) for seg in profile)
    max_x = max(max(seg.start.x, seg.end.x) for seg in profile)
    stock_near_low_side = abs(stock_x - min_x) < abs(stock_x - max_x)

    direction_up = False
    prev = profile[0].start
    for seg in profile:
        curr = seg.end
        dx = curr.x - prev.x
        if abs(dx) > 1e-5:
            direction_up = dx > 0.0
            break
        prev = curr
    else:
        total_dx = sum(seg.end.x - seg.start.x for seg in profile)
        direction_up = total_dx > 1e-5

    return stock_near_low_side and direction_up


def _profile_intersections_at_z(profile: list[ProfileSegment], pass_z: float) -> list[float]:
    xs: list[float] = []
    for seg in profile:
        raw = segment_points(seg, seg.start, seg.end)
        for a, b in zip(raw, raw[1:]):
            za = a.z - pass_z
            zb = b.z - pass_z
            if abs(za) <= 1e-8 and abs(zb) <= 1e-8:
                xs.extend([a.x, b.x])
                continue
            if za * zb > 0.0:
                continue
            dz = b.z - a.z
            if abs(dz) <= 1e-9:
                xs.append(a.x)
                continue
            t = (pass_z - a.z) / dz
            if t < -1e-6 or t > 1.000001:
                continue
            t = max(0.0, min(1.0, t))
            xs.append(a.x + (b.x - a.x) * t)
    return xs


def _distinct_in_profile_order(values: list[float], tolerance: float = 1e-3) -> list[float]:
    result: list[float] = []
    for value in values:
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def _shift_profile(profile: list[ProfileSegment], dx: float, dz: float) -> list[ProfileSegment]:
    out: list[ProfileSegment] = []
    for seg in profile:
        out.append(
            ProfileSegment(
                block=seg.block,
                move=seg.move,
                start=Point2(seg.start.x + dx, seg.start.z + dz),
                end=Point2(seg.end.x + dx, seg.end.z + dz),
                has_radius=seg.has_radius,
                radius=seg.radius,
                has_center=seg.has_center,
                center=Point2(seg.center.x + dx, seg.center.z + dz),
                playback_group=seg.playback_group,
            )
        )
    return out
