"""Circle through three Cartesian points, independent of the active ISO plane."""

import math

from ..api.resources import SemanticError
from ..api.types import ArcGeometry


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def through_three_points(start, intermediate, end):
    u = tuple(intermediate[i] - start[i] for i in range(3))
    v = tuple(end[i] - start[i] for i in range(3))
    normal = cross(u, v)
    squared = sum(value * value for value in normal)
    uu, vv = sum(value * value for value in u), sum(value * value for value in v)
    if not all(math.isfinite(value) for point in (start, intermediate, end) for value in point):
        raise SemanticError("INVALID_SINUMERIK_CIP", "CIP points must be finite", "invalid_geometry")
    if min(uu, vv) <= 1e-20 or squared <= 1e-24 * uu * vv:
        raise SemanticError("INVALID_SINUMERIK_CIP", "CIP points are coincident or collinear", "invalid_geometry")
    first, second = cross(v, normal), cross(normal, u)
    center = tuple(start[i] + (uu * first[i] + vv * second[i]) / (2 * squared) for i in range(3))
    normal = tuple(value / math.sqrt(squared) for value in normal)
    a, b = tuple(start[i] - center[i] for i in range(3)), tuple(end[i] - center[i] for i in range(3))
    sine = sum(normal[i] * cross(a, b)[i] for i in range(3))
    cosine = sum(a[i] * b[i] for i in range(3))
    sweep = math.atan2(sine, cosine) % math.tau
    return ArcGeometry(center, math.sqrt(sum(value * value for value in a)), sweep, 17, False, False, normal)


def arc_basis(motion):
    arc = motion.arc
    if not math.isfinite(arc.sweep) or arc.sweep <= 0:
        raise SemanticError("INVALID_GEOMETRY", "Arc sweep must be finite and positive", "invalid_geometry")
    start = (motion.start_x, motion.start_y, motion.start_z)
    first = tuple((start[i] - arc.center[i]) / arc.radius for i in range(3))
    second = cross(arc.normal, first)
    if arc.clockwise != (arc.plane == 18):
        second = tuple(-value for value in second)
    return first, second


def point_at(motion, angle):
    first, second = arc_basis(motion)
    travel = axial_travel(motion) * angle / motion.arc.sweep
    return tuple(
        motion.arc.center[i]
        + motion.arc.radius * (first[i] * math.cos(angle) + second[i] * math.sin(angle))
        + motion.arc.normal[i] * travel
        for i in range(3)
    )


def axial_travel(motion):
    delta = (motion.end_x - motion.start_x, motion.end_y - motion.start_y, motion.end_z - motion.start_z)
    return sum(motion.arc.normal[i] * delta[i] for i in range(3))


def extreme_points(motion):
    first, second = arc_basis(motion)
    travel, arc = axial_travel(motion), motion.arc
    angles = []
    for index in range(3):
        amplitude = arc.radius * math.hypot(first[index], second[index])
        slope = travel * arc.normal[index] / arc.sweep
        if amplitude <= 1e-15 or abs(slope) > amplitude:
            continue
        phase = math.atan2(first[index], second[index])
        angle = math.acos(max(-1.0, min(1.0, -slope / amplitude)))
        for base in (angle - phase, -angle - phase):
            initial = base % math.tau
            count = max(0, math.floor((arc.sweep - initial + 1e-12) / math.tau) + 1)
            angles.extend(initial + turn * math.tau for turn in range(count))
    return [point_at(motion, angle) for angle in angles]
