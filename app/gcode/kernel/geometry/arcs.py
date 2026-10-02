"""Analytical arc resolution in physical millimetres, owned by the kernel."""

import math
from dataclasses import replace

from ..api.resources import SemanticError
from ..api.types import ArcGeometry


def _resolve_oriented_arc(motion, source_arc_type):
    matrix = motion.orientation
    origin = motion.orientation_offset

    def inverse(point, *, direction=False):
        shifted = point if direction else tuple(point[i] - origin[i] for i in range(3))
        return tuple(sum(matrix[j][i] * shifted[j] for j in range(3)) for i in range(3))

    def forward(point, *, direction=False):
        rotated = tuple(sum(matrix[i][j] * point[j] for j in range(3)) for i in range(3))
        return rotated if direction else tuple(rotated[i] + origin[i] for i in range(3))

    start = inverse((motion.start_x, motion.start_y, motion.start_z))
    end = inverse((motion.end_x, motion.end_y, motion.end_z))
    delta = inverse((motion.i or 0.0, motion.j or 0.0, motion.k or 0.0), direction=True)
    has_ijk = any(v is not None for v in (motion.i, motion.j, motion.k))
    local = replace(
        motion,
        start_x=start[0],
        start_y=start[1],
        start_z=start[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        i=delta[0] if has_ijk else None,
        j=delta[1] if has_ijk else None,
        k=delta[2] if has_ijk else None,
        orientation=None,
    )
    resolved = resolve_arc(local, source_arc_type=source_arc_type)
    normal = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}[motion.plane]
    return replace(
        motion, arc=replace(resolved.arc, center=forward(resolved.arc.center), normal=forward(normal, direction=True))
    )


def resolve_arc(motion, *, source_arc_type=1):
    if motion.move not in (2, 3):
        return motion
    if motion.orientation is not None:
        return _resolve_oriented_arc(motion, source_arc_type)
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

    has_ijk = offsets[a] is not None or offsets[b] is not None
    use_ijk = has_ijk and (source_arc_type != 3 or motion.radius is None)
    if use_ijk:
        center = list(start)
        center[a] = (offsets[a] or 0.0) + (0 if source_arc_type == 2 else start[a])
        center[b] = (offsets[b] or 0.0) + (0 if source_arc_type == 2 else start[b])
        radius = math.hypot(start[a] - center[a], start[b] - center[b])
        if radius <= 1e-10:
            raise SemanticError("INVALID_GEOMETRY", "Arc IJK radius is zero", "invalid_geometry")
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
    total_sweep = sweep(center) + motion.additional_turns * 2 * math.pi
    return replace(motion, arc=ArcGeometry(tuple(center), radius, total_sweep, motion.plane, clockwise, full))
