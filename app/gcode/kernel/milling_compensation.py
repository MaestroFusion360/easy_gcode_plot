"""Fanuc-style cutter-radius compensation for resolved milling motions.

The implementation mirrors the compensation pipeline used by CncKernelCli:
entry transition -> steady offset motions -> stitched corners -> exit transition.
It consumes only kernel-resolved motion/arc geometry and configured milling tools.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .api_types import ArcGeometry, TraceMotion

_EPS = 1e-9
_GEOMETRY_TOLERANCE = 0.01

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
        return abs(self.end_w - self.start_w) > _EPS


def _dist2(a: _Point2, b: _Point2) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _normalize_ccw_delta(start: float, end: float) -> float:
    return (end - start) % (2.0 * math.pi)


def _tool_radius(tool: dict[str, object] | None) -> float | None:
    if not isinstance(tool, dict):
        return None
    tool_type = str(tool.get("type", "")).lower()
    if tool_type not in {"mill_flat", "mill_bull", "mill_ball"}:
        return None
    try:
        diameter = float(tool.get("diameter", 0.0))
    except (TypeError, ValueError):
        return None
    return diameter * 0.5 if diameter > 0.0 else None


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
    if radius <= _EPS:
        return None

    planar_closed = _dist2(start, end) <= 1e-18
    if planar_closed and abs(end_w - start_w) <= _EPS:
        # Keep parity with CncKernelCli: a planar full circle has no unique
        # entry/exit stitching point for the compensation state machine.
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


def _offset_line(projected: _ProjectedMotion, distance: float) -> _ProjectedMotion | None:
    dx = projected.end[0] - projected.start[0]
    dy = projected.end[1] - projected.start[1]
    length = math.hypot(dx, dy)
    if length <= _EPS:
        return None
    nx, ny = -dy / length, dx / length
    shift = nx * distance, ny * distance
    return replace(
        projected,
        start=(projected.start[0] + shift[0], projected.start[1] + shift[1]),
        end=(projected.end[0] + shift[0], projected.end[1] + shift[1]),
    )


def _offset_arc(
    projected: _ProjectedMotion,
    distance: float,
    geometry_tolerance: float,
) -> _ProjectedMotion | None:
    assert projected.center is not None and projected.radius is not None
    center = projected.center
    rsx, rsy = projected.start[0] - center[0], projected.start[1] - center[1]
    rex, rey = projected.end[0] - center[0], projected.end[1] - center[1]
    r_start = math.hypot(rsx, rsy)
    r_end = math.hypot(rex, rey)
    if r_start <= _EPS or r_end <= _EPS:
        return None
    if abs(r_start - r_end) > max(geometry_tolerance, 1e-6):
        return None

    radius = 0.5 * (r_start + r_end)
    offset_radius = radius - distance if projected.source.move == 3 else radius + distance
    if offset_radius <= _EPS:
        return None

    start_scale = offset_radius / r_start
    end_scale = offset_radius / r_end
    start = center[0] + rsx * start_scale, center[1] + rsy * start_scale
    end = center[0] + rex * end_scale, center[1] + rey * end_scale
    return replace(projected, start=start, end=end, radius=offset_radius)


def _solve_standalone(
    motion: TraceMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> _ProjectedMotion | None:
    if tool_radius <= _EPS or comp_mode not in (41, 42):
        return None
    projected = _project_motion(motion)
    if projected is None:
        return None
    signed_offset = tool_radius if comp_mode == 41 else -tool_radius
    if projected.is_line:
        return _offset_line(projected, signed_offset)
    return _offset_arc(projected, signed_offset, geometry_tolerance)


def _line_line_intersection(a: _ProjectedMotion, b: _ProjectedMotion) -> list[_Point2]:
    avx, avy = a.end[0] - a.start[0], a.end[1] - a.start[1]
    bvx, bvy = b.end[0] - b.start[0], b.end[1] - b.start[1]
    det = avx * bvy - avy * bvx
    if abs(det) <= _EPS:
        return []
    dx, dy = b.start[0] - a.start[0], b.start[1] - a.start[1]
    t = (dx * bvy - dy * bvx) / det
    return [(a.start[0] + t * avx, a.start[1] + t * avy)]


def _line_arc_intersections(line: _ProjectedMotion, arc: _ProjectedMotion) -> list[_Point2]:
    assert arc.center is not None and arc.radius is not None
    vx, vy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    aa = vx * vx + vy * vy
    if aa <= _EPS:
        return []
    ox, oy = line.start[0] - arc.center[0], line.start[1] - arc.center[1]
    bb = 2.0 * (vx * ox + vy * oy)
    cc = ox * ox + oy * oy - arc.radius * arc.radius
    disc = bb * bb - 4.0 * aa * cc
    if disc < -_EPS:
        return []
    root = math.sqrt(max(0.0, disc))
    t1 = (-bb - root) / (2.0 * aa)
    t2 = (-bb + root) / (2.0 * aa)
    out = [(line.start[0] + t1 * vx, line.start[1] + t1 * vy)]
    if abs(t2 - t1) > 1e-10:
        out.append((line.start[0] + t2 * vx, line.start[1] + t2 * vy))
    return out


def _arc_arc_intersections(a: _ProjectedMotion, b: _ProjectedMotion) -> list[_Point2]:
    assert a.center is not None and b.center is not None
    assert a.radius is not None and b.radius is not None
    dx, dy = b.center[0] - a.center[0], b.center[1] - a.center[1]
    distance = math.hypot(dx, dy)
    if distance <= _EPS:
        return []
    if distance > a.radius + b.radius + _EPS:
        return []
    if distance < abs(a.radius - b.radius) - _EPS:
        return []

    along = (a.radius * a.radius - b.radius * b.radius + distance * distance) / (2.0 * distance)
    h2 = a.radius * a.radius - along * along
    if h2 < -_EPS:
        return []
    height = math.sqrt(max(0.0, h2))
    mid_x = a.center[0] + along * dx / distance
    mid_y = a.center[1] + along * dy / distance
    rx, ry = -dy * height / distance, dx * height / distance
    out = [(mid_x + rx, mid_y + ry)]
    if height > 1e-10:
        out.append((mid_x - rx, mid_y - ry))
    return out


def _point_on_line(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    vx, vy = motion.end[0] - motion.start[0], motion.end[1] - motion.start[1]
    length2 = vx * vx + vy * vy
    if length2 <= _EPS:
        return None
    length = math.sqrt(length2)
    wx, wy = point[0] - motion.start[0], point[1] - motion.start[1]
    t = (wx * vx + wy * vy) / length2
    projected = motion.start[0] + t * vx, motion.start[1] + t * vy
    if _dist2(projected, point) > tolerance * tolerance:
        return None
    return t * length, length


def _point_on_arc(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    assert motion.center is not None and motion.radius is not None
    if motion.radius <= _EPS:
        return None
    px, py = point[0] - motion.center[0], point[1] - motion.center[1]
    point_radius = math.hypot(px, py)
    if abs(point_radius - motion.radius) > tolerance:
        return None

    start_angle = math.atan2(motion.start[1] - motion.center[1], motion.start[0] - motion.center[0])
    end_angle = math.atan2(motion.end[1] - motion.center[1], motion.end[0] - motion.center[0])
    point_angle = math.atan2(py, px)
    if motion.source.move == 3:
        sweep = _normalize_ccw_delta(start_angle, end_angle)
        point_sweep = _normalize_ccw_delta(start_angle, point_angle)
    else:
        sweep = _normalize_ccw_delta(end_angle, start_angle)
        point_sweep = _normalize_ccw_delta(point_angle, start_angle)
    if sweep <= _EPS:
        sweep = 2.0 * math.pi
    if point_sweep > sweep + 1e-6:
        return None
    return point_sweep * motion.radius, sweep * motion.radius


def _get_progress(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> tuple[float, float] | None:
    if motion.is_line:
        return _point_on_line(motion, point, tolerance)
    return _point_on_arc(motion, point, tolerance)


def _join_offset_primitives(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    tolerance: float,
) -> _Point2 | None:
    if previous.is_line and current.is_line:
        candidates = _line_line_intersection(previous, current)
    elif previous.is_line:
        candidates = _line_arc_intersections(previous, current)
    elif current.is_line:
        candidates = _line_arc_intersections(current, previous)
    else:
        candidates = _arc_arc_intersections(previous, current)
    if not candidates:
        return None

    valid: list[tuple[float, _Point2]] = []
    for candidate in candidates:
        progress_a = _get_progress(previous, candidate, tolerance)
        progress_b = _get_progress(current, candidate, tolerance)
        if progress_a is None or progress_b is None:
            continue
        if progress_a[0] < -1e-6 or progress_b[0] < -1e-6:
            continue
        score = _dist2(candidate, previous.end) + _dist2(candidate, current.start)
        valid.append((score, candidate))
    if valid:
        return min(valid, key=lambda item: item[0])[1]
    return min(
        candidates,
        key=lambda point: _dist2(point, previous.end) + _dist2(point, current.start),
    )


def _out_of_plane_at(
    motion: _ProjectedMotion,
    point: _Point2,
    tolerance: float,
) -> float | None:
    if abs(motion.end_w - motion.start_w) <= _EPS:
        return motion.start_w
    progress = _get_progress(motion, point, tolerance)
    if progress is None or progress[1] <= _EPS:
        return None
    t = max(0.0, min(1.0, progress[0] / progress[1]))
    return motion.start_w + (motion.end_w - motion.start_w) * t


def _unit_tangent(motion: _ProjectedMotion) -> _Point2 | None:
    dx, dy = motion.end[0] - motion.start[0], motion.end[1] - motion.start[1]
    length = math.hypot(dx, dy)
    if length <= _EPS:
        return None
    return dx / length, dy / length


def _line_line_transition_compatible(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> bool:
    same_geometry = previous.is_line and current.is_line and previous.plane == current.plane
    usable_offset = tool_radius > _EPS and abs(signed_offset) > _EPS
    same_level = abs(previous.end_w - current.start_w) <= 1e-6
    return same_geometry and usable_offset and same_level


def _line_line_transition_basis(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> tuple[_Point2, _Point2, float, _Point2] | None:
    if not _line_line_transition_compatible(previous, current, signed_offset, tool_radius):
        return None

    ta = _unit_tangent(previous)
    tb = _unit_tangent(current)
    if ta is None or tb is None:
        return None

    cross = ta[0] * tb[1] - ta[1] * tb[0]
    if abs(cross) <= 1e-6 or cross * signed_offset >= 0.0:
        return None

    corners = _line_line_intersection(previous, current)
    return (ta, tb, cross, corners[0]) if corners else None


def _line_line_transition_geometry(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    ta: _Point2,
    tb: _Point2,
    corner: _Point2,
    tool_radius: float,
) -> tuple[_Point2, _Point2, _Point2, float] | None:
    dot = max(-1.0, min(1.0, ta[0] * tb[0] + ta[1] * tb[1]))
    angle = math.acos(dot)
    if angle <= 1e-6 or abs(math.pi - angle) <= 1e-6:
        return None

    trim = tool_radius * math.tan(angle * 0.5)
    previous_length = math.sqrt(_dist2(previous.start, previous.end))
    current_length = math.sqrt(_dist2(current.start, current.end))
    invalid_trim = trim <= _EPS or trim > previous_length + 1e-6
    invalid_trim = invalid_trim or trim > current_length + 1e-6
    if invalid_trim:
        return None

    t1 = corner[0] - ta[0] * trim, corner[1] - ta[1] * trim
    t2 = corner[0] + tb[0] * trim, corner[1] + tb[1] * trim
    n1 = -ta[1], ta[0]
    n2 = -tb[1], tb[0]
    normal_a = _ProjectedMotion(previous.source, previous.plane, t1, (t1[0] + n1[0], t1[1] + n1[1]), 0, 0)
    normal_b = _ProjectedMotion(current.source, current.plane, t2, (t2[0] + n2[0], t2[1] + n2[1]), 0, 0)
    centers = _line_line_intersection(normal_a, normal_b)
    if not centers:
        return None

    center = centers[0]
    radius = math.sqrt(_dist2(t1, center))
    if radius <= _EPS:
        return None
    return t1, t2, center, radius


def _build_line_line_transition(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    signed_offset: float,
    tool_radius: float,
) -> tuple[_ProjectedMotion, _ProjectedMotion, TraceMotion] | None:
    basis = _line_line_transition_basis(previous, current, signed_offset, tool_radius)
    if basis is None:
        return None
    ta, tb, cross, corner = basis

    geometry = _line_line_transition_geometry(previous, current, ta, tb, corner, tool_radius)
    if geometry is None:
        return None
    t1, t2, center, radius = geometry

    stitched_previous = _retarget_end(previous, t1, previous.end_w)
    stitched_current = _retarget_start(current, t2, current.start_w)
    transition_projected = _ProjectedMotion(
        source=replace(previous.source, move=3 if cross > 0.0 else 2),
        plane=previous.plane,
        start=t1,
        end=t2,
        start_w=previous.end_w,
        end_w=previous.end_w,
        center=center,
        radius=radius,
    )
    transition = _projected_to_motion(
        transition_projected,
        comp_mode=previous.source.compensation_mode,
        source_kind="cutter_compensation_transition",
    )
    return stitched_previous, stitched_current, transition


def _join_steady_motion(
    previous: _ProjectedMotion,
    current: _ProjectedMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> tuple[_ProjectedMotion, _ProjectedMotion, TraceMotion | None] | None:
    signed_offset = tool_radius if comp_mode == 41 else -tool_radius
    fillet = _build_line_line_transition(previous, current, signed_offset, tool_radius)
    if fillet is not None:
        return fillet

    join = _join_offset_primitives(previous, current, geometry_tolerance)
    if join is None:
        return None
    join_w = _out_of_plane_at(current, join, geometry_tolerance)
    if join_w is None:
        join_w = _out_of_plane_at(previous, join, geometry_tolerance)
    if join_w is None:
        join_w = current.start_w
    return _retarget_end(previous, join, join_w), _retarget_start(current, join, join_w), None


def _find_entry_reference(motions: list[TraceMotion], event_index: int, comp_mode: int) -> TraceMotion | None:
    for motion in motions[event_index + 1 :]:
        if motion.compensation_mode != comp_mode:
            break
        if motion.move in (1, 2, 3):
            return motion
    return None


def _solve_entry(
    event_motion: TraceMotion,
    reference_motion: TraceMotion,
    comp_mode: int,
    tool_radius: float,
    geometry_tolerance: float,
) -> TraceMotion | None:
    reference_offset = _solve_standalone(reference_motion, comp_mode, tool_radius, geometry_tolerance)
    if reference_offset is None:
        return None

    projected_event = _project_motion(event_motion) if event_motion.move in (1, 2, 3) else None
    if projected_event is not None:
        solved = _retarget_end(projected_event, reference_offset.start, reference_offset.start_w)
        if solved.is_arc:
            progress = _get_progress(solved, solved.end, geometry_tolerance)
            if progress is None:
                return None
        return _projected_to_motion(
            solved,
            comp_mode=comp_mode,
            source_kind="cutter_compensation_entry",
        )

    x, y, z = _unproject(reference_offset.plane, reference_offset.start, reference_offset.start_w)
    return replace(
        event_motion,
        end_x=x,
        end_y=y,
        end_z=z,
        compensation_mode=comp_mode,
        compensation_applied=True,
        compensation_status="APPLIED",
        source_kind="cutter_compensation_entry",
    )


def _solve_exit(exit_motion: TraceMotion, previous_compensated: TraceMotion) -> TraceMotion:
    projected_exit = _project_motion(exit_motion) if exit_motion.move in (1, 2, 3) else None
    projected_previous = _project_motion(previous_compensated)
    if projected_exit is not None and projected_previous is not None:
        retargeted = _retarget_start(projected_exit, projected_previous.end, projected_previous.end_w)
        if retargeted.is_arc and _get_progress(retargeted, retargeted.start, _GEOMETRY_TOLERANCE) is None:
            return replace(
                exit_motion,
                start_x=previous_compensated.end_x,
                start_y=previous_compensated.end_y,
                start_z=previous_compensated.end_z,
                source_kind="cutter_compensation_exit",
            )
        solved = _projected_to_motion(
            retargeted,
            comp_mode=40,
            source_kind="cutter_compensation_exit",
        )
        return replace(solved, compensation_applied=False, compensation_status="NOT_APPLIED")
    return replace(
        exit_motion,
        start_x=previous_compensated.end_x,
        start_y=previous_compensated.end_y,
        start_z=previous_compensated.end_z,
        source_kind="cutter_compensation_exit",
    )


def _mark_unverified(motion: TraceMotion) -> TraceMotion:
    return replace(motion, compensation_applied=False, compensation_status="UNVERIFIED")


def _normalize_comp_mode(mode: int) -> int:
    return mode if mode in (41, 42) else 0


def apply_milling_cutter_compensation(
    motions: list[TraceMotion],
    tools: dict[str, dict[str, object]],
    *,
    geometry_tolerance: float = _GEOMETRY_TOLERANCE,
) -> list[TraceMotion]:
    """Apply Fanuc-style cutter compensation using configured milling tool diameters.

    G41/G42 is treated as a state machine.  The command block is an entry
    transition, following line/arc/helix motions are offset and stitched, and
    the first G40 motion is retargeted from the final compensated endpoint.
    """
    if not motions:
        return motions

    output: list[TraceMotion] = []
    previous_steady: _ProjectedMotion | None = None
    previous_steady_output_index = -1
    align_next_active_to_entry = False
    active_tool_radius = 0.0
    active_comp_mode = 0

    for index, current in enumerate(motions):
        previous_comp = _normalize_comp_mode(motions[index - 1].compensation_mode) if index > 0 else 0
        current_comp = _normalize_comp_mode(current.compensation_mode)
        current_active = current_comp != 0
        entry_event = current_active and previous_comp != current_comp
        exit_event = current_comp == 0 and previous_comp != 0

        if entry_event:
            active_comp_mode = current_comp
            active_tool_radius = _tool_radius(tools.get(current.tool or "")) or 0.0
            previous_steady = None
            previous_steady_output_index = -1
            align_next_active_to_entry = False
            if active_tool_radius <= _EPS:
                output.append(_mark_unverified(current))
                continue

            reference = _find_entry_reference(motions, index, active_comp_mode) or current
            solved_entry = _solve_entry(
                current,
                reference,
                active_comp_mode,
                active_tool_radius,
                geometry_tolerance,
            )
            if solved_entry is None:
                active_tool_radius = 0.0
                output.append(_mark_unverified(current))
                continue

            output.append(solved_entry)
            align_next_active_to_entry = True
            continue

        if exit_event:
            output.append(_solve_exit(current, output[-1]) if output else current)
            previous_steady = None
            previous_steady_output_index = -1
            align_next_active_to_entry = False
            active_tool_radius = 0.0
            active_comp_mode = 0
            continue

        if not current_active:
            output.append(current)
            continue

        if active_tool_radius <= _EPS or current_comp != active_comp_mode:
            output.append(_mark_unverified(current))
            previous_steady = None
            previous_steady_output_index = -1
            continue

        solved_steady = _solve_standalone(current, current_comp, active_tool_radius, geometry_tolerance)
        if solved_steady is None:
            output.append(_mark_unverified(current))
            previous_steady = None
            previous_steady_output_index = -1
            continue

        if align_next_active_to_entry and output:
            previous_output = _project_motion(output[-1])
            if previous_output is not None:
                solved_steady = _retarget_start(solved_steady, previous_output.end, previous_output.end_w)
            align_next_active_to_entry = False
        elif previous_steady is not None:
            joined = _join_steady_motion(
                previous_steady,
                solved_steady,
                current_comp,
                active_tool_radius,
                geometry_tolerance,
            )
            if joined is not None:
                stitched_previous, solved_steady, transition = joined
                output[previous_steady_output_index] = _projected_to_motion(
                    stitched_previous,
                    comp_mode=current_comp,
                )
                if transition is not None:
                    output.append(transition)

        solved_trace = _projected_to_motion(solved_steady, comp_mode=current_comp)
        output.append(solved_trace)
        previous_steady = solved_steady
        previous_steady_output_index = len(output) - 1

    return output
