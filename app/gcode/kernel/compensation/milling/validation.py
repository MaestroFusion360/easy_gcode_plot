"""Analytic planar cutter clearance; never certify an impossible offset run."""

from __future__ import annotations

import heapq
import math

from ..common import EPS
from .joins import _arc_arc_intersections, _get_progress, _line_arc_intersections, _line_line_intersection
from .projection import _dist2, _project_motion


def _contains(motion, point):
    if motion.is_arc and motion.source.additional_turns:
        # Every point on the circle is visited before the final partial turn.
        return abs(math.hypot(point[0] - motion.center[0], point[1] - motion.center[1]) - motion.radius) <= 1e-7
    progress = _get_progress(motion, point, 1e-7)
    return progress is not None and -EPS <= progress[0] <= progress[1] + EPS


def _point_distance(point, motion):
    if motion.is_line:
        dx, dy = motion.end[0] - motion.start[0], motion.end[1] - motion.start[1]
        length2 = dx * dx + dy * dy
        t = ((point[0] - motion.start[0]) * dx + (point[1] - motion.start[1]) * dy) / length2
        t = max(0.0, min(1.0, t))
        return math.hypot(point[0] - motion.start[0] - t * dx, point[1] - motion.start[1] - t * dy)
    dx, dy = point[0] - motion.center[0], point[1] - motion.center[1]
    length = math.hypot(dx, dy)
    if length > EPS:
        radial = motion.center[0] + dx * motion.radius / length, motion.center[1] + dy * motion.radius / length
        if _contains(motion, radial):
            return abs(length - motion.radius)
    return math.sqrt(min(_dist2(point, motion.start), _dist2(point, motion.end)))


def _stationary_pairs(a, b):
    """Interior distance extrema of a finite line/circle or two circles."""
    if a.is_line and b.is_line:
        return [(p, p) for p in _line_line_intersection(a, b)]
    if b.is_line:
        return [(q, p) for p, q in _stationary_pairs(a=b, b=a)]
    if a.is_line:
        pairs = [(p, p) for p in _line_arc_intersections(a, b)]
        dx, dy = a.end[0] - a.start[0], a.end[1] - a.start[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        for sign in (-1, 1):
            q = b.center[0] + sign * b.radius * nx, b.center[1] + sign * b.radius * ny
            along = ((q[0] - a.start[0]) * dx + (q[1] - a.start[1]) * dy) / (length * length)
            pairs.append(((a.start[0] + along * dx, a.start[1] + along * dy), q))
        return pairs
    pairs = [(p, p) for p in _arc_arc_intersections(a, b)]
    dx, dy = b.center[0] - a.center[0], b.center[1] - a.center[1]
    length = math.hypot(dx, dy)
    if length > EPS:
        for sa in (-1, 1):
            for sb in (-1, 1):
                pairs.append(
                    (
                        (a.center[0] + sa * a.radius * dx / length, a.center[1] + sa * a.radius * dy / length),
                        (b.center[0] + sb * b.radius * dx / length, b.center[1] + sb * b.radius * dy / length),
                    )
                )
    return pairs


def _distance(a, b):
    minimum = min(_point_distance(p, b) for p in (a.start, a.end))
    minimum = min(minimum, *(_point_distance(p, a) for p in (b.start, b.end)))
    for p, q in _stationary_pairs(a, b):
        if _contains(a, p) and _contains(b, q):
            minimum = min(minimum, math.sqrt(_dist2(p, q)))
    return minimum


def _bounds(motion, margin):
    if motion.is_line:
        xs, ys = (motion.start[0], motion.end[0]), (motion.start[1], motion.end[1])
    else:
        xs = motion.center[0] - motion.radius, motion.center[0] + motion.radius
        ys = motion.center[1] - motion.radius, motion.center[1] + motion.radius
    return min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin


def _nearby_pairs(nominal, solved, radius):
    """Sweep bounding boxes to avoid comparing every pair in large programs."""
    events = []
    for kind, motions in enumerate((nominal, solved)):
        for index, motion in enumerate(motions):
            left, right, bottom, top = _bounds(motion, radius if kind == 0 else 0)
            events.append((left, kind, index, right, bottom, top, motion))
    active, expiry = ({}, {}), []
    for left, kind, index, right, bottom, top, motion in sorted(events):
        while expiry and expiry[0][0] < left:
            _, old_kind, old_index = heapq.heappop(expiry)
            active[old_kind].pop(old_index, None)
        for other_bottom, other_top, other in active[1 - kind].values():
            if bottom <= other_top and other_bottom <= top:
                yield (motion, other) if kind == 0 else (other, motion)
        active[kind][index] = bottom, top, motion
        heapq.heappush(expiry, (right, kind, index))


def has_invalid_line_direction(nominal, solved, source_indices):
    for motion, index in zip(solved, source_indices):
        if motion.source_kind != "cutter_compensation":
            continue
        original = _project_motion(nominal[index])
        if original is None or not original.is_line:
            continue
        actual = _project_motion(motion)
        if actual is None:
            return True
        dx, dy = original.end[0] - original.start[0], original.end[1] - original.start[1]
        along = (actual.end[0] - actual.start[0]) * dx + (actual.end[1] - actual.start[1]) * dy
        if along <= EPS * math.hypot(dx, dy):
            return True
    return False


def has_planar_gouging(nominal, solved, sources, radius, tolerance, lead_blocks=frozenset()):
    """Check steady geometry against the whole nominal contour, including remote walls.

    Entry/exit leads are excluded. Clearance is certified here only between
    coplanar planar primitives; helical/rotary swept volumes need a 3D oracle.
    """
    originals = [_project_motion(m) for m in nominal[1:] if m.source_block not in lead_blocks]
    originals = [m for m in originals if m is not None and not m.is_helix]
    resolved, origins = [], {}
    for motion, source in zip(solved, sources):
        projected = _project_motion(motion)
        if projected is not None and not projected.is_helix:
            if motion.source_kind != "cutter_compensation_entry" and motion.source_block not in lead_blocks:
                resolved.append(projected)
                origins[id(projected)] = _project_motion(source)
    for a, b in _nearby_pairs(originals, resolved, radius):
        if a.plane == b.plane and abs(a.start_w - b.start_w) <= EPS:
            origin = origins[id(b)]
            # Closure/overlap leads can meet inside another nominal element
            # (a T-junction), rather than sharing its endpoint. These local
            # joins are not remote walls; separated neck walls still are.
            if origin is not None and _distance(a, origin) <= EPS:
                continue
            if _distance(a, b) < radius - max(EPS, tolerance):
                return True
    return False
