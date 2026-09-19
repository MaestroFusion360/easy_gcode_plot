"""Projection between XYZ trace motions and active-plane compensation geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ...api.types import ArcGeometry, TraceMotion
from ..common import EPS

_Point2 = tuple[float, float]


@dataclass(frozen=True)
class _ProjectedMotion:
    source: TraceMotion
    plane: int
    start: _Point2
    end: _Point2
    start_w: float
    end_w: float
    center: _Point2 | None = None
    radius: float | None = None

    @property
    def is_line(self) -> bool:
        return self.center is None

    @property
    def is_arc(self) -> bool:
        return self.center is not None and self.radius is not None

    @property
    def is_helix(self) -> bool:
        return abs(self.end_w - self.start_w) > EPS


def _dist2(a: _Point2, b: _Point2) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _normalize_ccw_delta(start: float, end: float) -> float:
    return (end - start) % (2.0 * math.pi)


def _project_xyz(plane: int, x: float, y: float, z: float) -> tuple[_Point2, float]:
    if plane == 18:
        return (x, z), y
    if plane == 19:
        return (y, z), x
    return (x, y), z


def _unproject(plane: int, point: _Point2, w: float) -> tuple[float, float, float]:
    if plane == 18:
        return point[0], w, point[1]
    if plane == 19:
        return w, point[0], point[1]
    return point[0], point[1], w


def _project_center(plane: int, center: tuple[float, float, float]) -> _Point2:
    if plane == 18:
        return center[0], center[2]
    if plane == 19:
        return center[1], center[2]
    return center[0], center[1]


def _unproject_center(plane: int, center: _Point2, source: TraceMotion) -> tuple[float, float, float]:
    source_center = source.arc.center if source.arc is not None else (source.start_x, source.start_y, source.start_z)
    if plane == 18:
        return center[0], source_center[1], center[1]
    if plane == 19:
        return source_center[0], center[0], center[1]
    return center[0], center[1], source_center[2]


def _project_motion(motion: TraceMotion) -> _ProjectedMotion | None:
    plane = motion.plane if motion.plane in (17, 18, 19) else 17
    start, start_w = _project_xyz(plane, motion.start_x, motion.start_y, motion.start_z)
    end, end_w = _project_xyz(plane, motion.end_x, motion.end_y, motion.end_z)

    if motion.move == 1:
        if _dist2(start, end) <= 1e-18:
            return None
        return _ProjectedMotion(motion, plane, start, end, start_w, end_w)

    if motion.move not in (2, 3) or motion.arc is None:
        return None

    center = _project_center(plane, motion.arc.center)
    radius = float(motion.arc.radius)
    if radius <= EPS:
        return None

    return _ProjectedMotion(motion, plane, start, end, start_w, end_w, center, radius)


def _retarget_start(motion: _ProjectedMotion, start: _Point2, w: float | None = None) -> _ProjectedMotion:
    return replace(motion, start=start, start_w=motion.start_w if w is None else w)


def _retarget_end(motion: _ProjectedMotion, end: _Point2, w: float | None = None) -> _ProjectedMotion:
    return replace(motion, end=end, end_w=motion.end_w if w is None else w)


def _arc_sweep(motion: _ProjectedMotion) -> float:
    assert motion.center is not None
    if _dist2(motion.start, motion.end) <= 1e-18:
        return 2.0 * math.pi
    start_angle = math.atan2(motion.start[1] - motion.center[1], motion.start[0] - motion.center[0])
    end_angle = math.atan2(motion.end[1] - motion.center[1], motion.end[0] - motion.center[0])
    if motion.source.move == 3:
        return _normalize_ccw_delta(start_angle, end_angle)
    return _normalize_ccw_delta(end_angle, start_angle)


def _projected_to_motion(
    projected: _ProjectedMotion,
    *,
    comp_mode: int,
    source_kind: str = "cutter_compensation",
) -> TraceMotion:
    source = projected.source
    sx, sy, sz = _unproject(projected.plane, projected.start, projected.start_w)
    ex, ey, ez = _unproject(projected.plane, projected.end, projected.end_w)

    if projected.is_line:
        return replace(
            source,
            move=1,
            start_x=sx,
            start_y=sy,
            start_z=sz,
            end_x=ex,
            end_y=ey,
            end_z=ez,
            radius=None,
            i=None,
            j=None,
            k=None,
            arc=None,
            compensation_mode=comp_mode,
            compensation_applied=True,
            compensation_status="APPLIED",
            source_kind=source_kind,
        )

    assert projected.center is not None and projected.radius is not None
    center3 = _unproject_center(projected.plane, projected.center, source)
    full_circle = _dist2(projected.start, projected.end) <= 1e-18
    arc = ArcGeometry(
        center=center3,
        radius=projected.radius,
        sweep=_arc_sweep(projected),
        plane=projected.plane,
        clockwise=source.move == 2,
        full_circle=full_circle,
    )
    i = j = k = None
    if projected.plane == 18:
        i = center3[0] - sx
        k = center3[2] - sz
    elif projected.plane == 19:
        j = center3[1] - sy
        k = center3[2] - sz
    else:
        i = center3[0] - sx
        j = center3[1] - sy

    return replace(
        source,
        start_x=sx,
        start_y=sy,
        start_z=sz,
        end_x=ex,
        end_y=ey,
        end_z=ez,
        radius=projected.radius,
        i=i,
        j=j,
        k=k,
        arc=arc,
        plane=projected.plane,
        compensation_mode=comp_mode,
        compensation_applied=True,
        compensation_status="APPLIED",
        source_kind=source_kind,
    )
