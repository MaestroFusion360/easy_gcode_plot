"""Analytical arc resolution in physical millimetres, owned by the kernel."""

import math
from dataclasses import replace

from .api_types import ArcGeometry
from .resources import SemanticError


def resolve_arc(motion, *, source_arc_type=1):
    if motion.move not in (2, 3):
        return motion
    axes = {17: (0, 1, 2), 18: (0, 2, 1), 19: (1, 2, 0)}
    if motion.plane not in axes:
        raise SemanticError("INVALID_GEOMETRY", "Unknown arc plane", "invalid_geometry")
    a, b, _ = axes[motion.plane]
    start = (motion.start_x * motion.x_scale, motion.start_y, motion.start_z)
    end = (motion.end_x * motion.x_scale, motion.end_y, motion.end_z)
    offsets = (None if motion.i is None else motion.i * motion.x_scale, motion.j, motion.k)
    clockwise = (motion.move == 2) != (motion.plane == 18)
    full = math.hypot(end[a] - start[a], end[b] - start[b]) <= 1e-10

    def sweep(center):
        a0 = math.atan2(start[b] - center[b], start[a] - center[a])
        a1 = math.atan2(end[b] - center[b], end[a] - center[a])
        return 2 * math.pi if full else ((a0 - a1) if clockwise else (a1 - a0)) % (2 * math.pi)

    if source_arc_type != 3 and (offsets[a] is not None or offsets[b] is not None):
        center = list(start)
        center[a] = (offsets[a] or 0.0) + (0 if source_arc_type == 2 else start[a])
        center[b] = (offsets[b] or 0.0) + (0 if source_arc_type == 2 else start[b])
        radius = math.hypot(start[a] - center[a], start[b] - center[b])
        r_end = math.hypot(end[a] - center[a], end[b] - center[b])
        if radius <= 1e-10 or abs(radius - r_end) > max(0.002, radius * 1e-5):
            raise SemanticError("INVALID_GEOMETRY", "Arc IJK radii disagree or radius is zero", "invalid_geometry")
    elif motion.radius is not None:
        radius = abs(motion.radius)
        dx, dy = end[a] - start[a], end[b] - start[b]
        chord = math.hypot(dx, dy)
        if full or radius <= 0 or chord > 2 * radius + 1e-9:
            raise SemanticError("INVALID_GEOMETRY", "Arc R cannot span its endpoints", "invalid_geometry")
        h = math.sqrt(max(0, radius * radius - chord * chord / 4))
        candidates = []
        for sign in (-1, 1):
            c = list(start)
            c[a] = (start[a] + end[a]) / 2 - sign * dy * h / chord
            c[b] = (start[b] + end[b]) / 2 + sign * dx * h / chord
            candidates.append(c)
        center = next((c for c in candidates if (sweep(c) <= math.pi + 1e-10) == (motion.radius >= 0)), candidates[0])
    else:
        raise SemanticError("INVALID_GEOMETRY", "Arc requires IJK or R", "invalid_geometry")
    return replace(motion, arc=ArcGeometry(tuple(center), radius, sweep(center), motion.plane, clockwise, full))
