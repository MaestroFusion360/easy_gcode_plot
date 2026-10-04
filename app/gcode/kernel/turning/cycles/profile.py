"""Profile preparation helpers shared by FANUC turning cycles."""

from __future__ import annotations

import math
from dataclasses import replace

from ...frontend.model import Motion, Point2, ProfileSegment
from ...geometry import segment_points


def build_offset_profile(profile, finish_u, finish_w, prefer_positive_x):
    """Offset exact lines/circles; never offset individual sampled arc points."""
    if not profile or (abs(finish_u) <= 1e-9 and abs(finish_w) <= 1e-9):
        return profile
    from ...compensation.turning.joins import join_primitives  # pylint: disable=import-outside-toplevel
    from ...compensation.turning.nose import offset_motion, to_point  # pylint: disable=import-outside-toplevel

    radial = finish_u * 0.5
    side = 1.0 if prefer_positive_x else -1.0
    distance = math.copysign(min(abs(radial), abs(finish_w)), radial * side)
    translation = Point2((radial - side * distance) * 2, finish_w - distance)
    cutting = [segment for segment in profile if segment.move != 0]
    primitives = []
    for segment in cutting:
        motion = Motion(
            segment.move,
            segment.start,
            segment.end,
            segment.radius if segment.has_radius else None,
            None,
            i=segment.center.x - segment.start.x if segment.has_center else None,
            k=segment.center.z - segment.start.z if segment.has_center else None,
            compensation_mode=42 if prefer_positive_x else 41,
        )
        primitives.append(offset_motion(motion, distance, 9))
    for index in range(len(primitives) - 1):
        try:
            join = join_primitives(primitives[index], primitives[index + 1])
        except ValueError:
            left, right = primitives[index], primitives[index + 1]
            if math.hypot(left.end.x - right.start.x, left.end.y - right.start.y) > 0.002:
                raise
            join = left.end if left.center is not None else right.start
        primitives[index] = replace(primitives[index], end=join)
        primitives[index + 1] = replace(primitives[index + 1], start=join)
    output = []

    def translated(point):
        value = to_point(point)
        return Point2(value.x + translation.x, value.z + translation.z)

    for segment, primitive in zip(cutting, primitives):
        center = translated(primitive.center) if primitive.center is not None else Point2(0, 0)
        output.append(
            replace(
                segment,
                start=translated(primitive.start),
                end=translated(primitive.end),
                has_center=primitive.center is not None,
                center=center,
                has_radius=False,
                radius=0.0,
            )
        )
    if output and profile[0].move == 0:
        output.insert(0, replace(profile[0], end=output[0].start))
    return output or profile


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
    """Keep first crossings, including when a closed contour repeats one later."""
    result: list[float] = []
    for value in values:
        if all(abs(value - previous) > tolerance for previous in result):
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
