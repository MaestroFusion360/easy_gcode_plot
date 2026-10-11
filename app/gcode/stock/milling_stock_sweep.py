"""Immutable cutter trajectories supplied to GPU stock removal."""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.gcode.trace_tools import _arc_extreme_coordinates, sample_motion

CONTOUR_ERROR = 0.02


@lru_cache(maxsize=128)
def compact_profile(profile):
    """Remove collinear radial spans without changing the cutter envelope."""
    vertices = []
    # Once the maximum radius is reached, later (higher) axial sections cannot
    # lower this three-axis cutter envelope, including a narrower shank.
    stop = max(range(len(profile)), key=lambda i: profile[i][1]) + 1
    for point in profile[:stop]:
        while len(vertices) >= 2:
            a, b = vertices[-2], vertices[-1]
            cross = (b[0] - a[0]) * (point[1] - b[1]) - (b[1] - a[1]) * (point[0] - b[0])
            if abs(cross) > 1e-12 or point[0] < b[0] or point[1] < b[1]:
                break
            vertices.pop()
        vertices.append(point)
    result = np.ascontiguousarray(vertices, dtype=np.float64)
    result.flags.writeable = False
    return result


@dataclass(frozen=True)
class CutterSweep:
    points: tuple
    profile: tuple
    tool: dict
    rapid: bool
    order: int = 0
    planar_arc: tuple | None = None
    contour_error: float = CONTOUR_ERROR
    bounds: tuple = ()

    @classmethod
    def from_motion(cls, motion, tool, profile, order=0, *, contour_error=CONTOUR_ERROR):
        first = (motion.start_x, motion.start_y, motion.start_z)
        last = (motion.end_x, motion.end_y, motion.end_z)
        arc = motion.arc
        planar = None
        if arc is not None and arc.plane == 17 and arc.normal is None and first[2] == last[2]:
            planar = (*arc.center[:2], arc.sweep, arc.clockwise)
            points = (first, last)
        else:
            sampled = sample_motion(motion, 0, chord_error=contour_error / 2)
            points = (first,) + tuple((p.x, p.y, p.z) for p in sampled)
        extremes = [first, last]
        if arc is not None:
            extremes.extend(_arc_extreme_coordinates(motion, 1.0))
        xy = np.asarray(extremes)[:, :2]
        radius = max(r for _, r in profile)
        bounds = xy.min(axis=0) - radius, xy.max(axis=0) + radius
        return cls(points, tuple(profile), dict(tool), motion.move == 0, order, planar, contour_error, bounds)
