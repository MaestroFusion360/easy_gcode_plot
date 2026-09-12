"""Axisymmetric turning stock removal driven by resolved kernel motions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.gcode.kernel import TraceMotion
from app.gcode.trace_tools import sample_motion
from app.gcode.turning_tool_geometry import (
    EPS,
    canonical_turning_tool_type,
    positive_float,
    turning_tool_polygon,
)
from app.gcode.turning_tool_geometry import TURNING_INSERT_TYPES as _TURNING_INSERT_TYPES
from app.gcode.turning_tool_geometry import TURNING_TOOL_LABELS as _TURNING_TOOL_LABELS

_EPS = EPS
TURNING_INSERT_TYPES = _TURNING_INSERT_TYPES
TURNING_TOOL_LABELS = _TURNING_TOOL_LABELS
MAX_TURN_PROFILE_POINTS = 20_000
MAX_MOTION_SAMPLES = 20_000


@dataclass(frozen=True)
class TurningStockSpec:
    """Axisymmetric stock whose front face is at ``front_z``."""

    outer_diameter: float = 50.0
    length: float = 100.0
    inner_diameter: float = 0.0
    resolution: float = 0.5
    front_z: float = 0.0

    def validate(self) -> None:
        values = (self.outer_diameter, self.length, self.inner_diameter, self.resolution, self.front_z)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Turning stock values must be finite")
        if self.outer_diameter <= 0.0 or self.length <= 0.0 or self.resolution <= 0.0:
            raise ValueError("Turning stock diameter, length and resolution must be positive")
        if self.inner_diameter < 0.0 or self.inner_diameter >= self.outer_diameter:
            raise ValueError("Turning stock inner diameter must be smaller than outer diameter")
        point_count = int(math.ceil(self.length / self.resolution)) + 1
        if point_count > MAX_TURN_PROFILE_POINTS:
            raise ValueError(
                f"Turning stock resolution creates {point_count:,} profile points; limit is {MAX_TURN_PROFILE_POINTS:,}"
            )


@dataclass(frozen=True)
class TurningDelta:
    """Reversible profile changes plus exact axial discontinuities for one motion."""

    changes: tuple[
        tuple[
            int,
            float,
            float,
            float,
            float,
            tuple[tuple[float, float], ...],
            tuple[tuple[float, float], ...],
        ],
        ...,
    ]
    breaks: tuple[float, ...] = ()


def _positive_float(spec: dict[str, object], key: str, default: float = 0.0) -> float:
    return positive_float(spec, key, default)


def _horizontal_span(
    points: tuple[tuple[float, float], ...],
    z_value: float,
) -> tuple[float, float] | None:
    """Intersect a convex X/Z cutter polygon with one stock-profile Z slice."""
    intersections: list[float] = []
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        x0, z0 = first
        x1, z1 = second
        if abs(z1 - z0) <= _EPS:
            if abs(z_value - z0) <= _EPS:
                intersections.extend((x0, x1))
            continue
        low = min(z0, z1) - _EPS
        high = max(z0, z1) + _EPS
        if not low <= z_value <= high:
            continue
        progress = (z_value - z0) / (z1 - z0)
        if -_EPS <= progress <= 1.0 + _EPS:
            intersections.append(x0 + progress * (x1 - x0))
    if not intersections:
        return None
    return min(intersections), max(intersections)


def _radial_groove_breaks(
    motion: TraceMotion,
    footprint: tuple[tuple[float, float], ...] | None,
    tool_type: str,
) -> tuple[float, ...]:
    """Return exact Z walls for a radial OD/ID groove plunge.

    The sampled stock profile is continuous between Z nodes.  A rectangular
    groove cutter, however, creates true discontinuities at both cutting-edge
    corners.  Keep those exact Z locations so the renderer can draw vertical
    walls instead of interpolating a false bevel across one profile cell.
    """
    if tool_type not in {"od_groove", "id_groove"} or not footprint:
        return ()
    if abs(float(motion.end_z) - float(motion.start_z)) > _EPS:
        return ()

    breaks: set[float] = set()
    for index, first in enumerate(footprint):
        second = footprint[(index + 1) % len(footprint)]
        if abs(first[1] - second[1]) <= _EPS < abs(first[0] - second[0]):
            breaks.add(float(motion.end_z) + float(first[1]))
    return tuple(sorted(breaks))


def profile_interval_mesh_spans(
    z0: float,
    z1: float,
    inner0: float,
    outer0: float,
    inner1: float,
    outer1: float,
    breaks: tuple[float, ...] | list[float],
) -> tuple[tuple[float, float, float, float, float, float], ...]:
    """Split one sampled profile interval at exact discontinuities.

    Each returned tuple is ``(za, zb, ia, oa, ib, ob)``.  Normal profile
    intervals remain linearly interpolated.  At a recorded groove wall the
    two sides meet at the same Z with independent radii, producing a vertical
    wall rather than a diagonal interpolation wedge.
    """
    if z1 <= z0 + _EPS:
        return ()

    inside = sorted({float(value) for value in breaks if z0 + _EPS < value < z1 - _EPS})
    at_start = any(abs(float(value) - z0) <= _EPS for value in breaks)
    at_end = any(abs(float(value) - z1) <= _EPS for value in breaks)

    if inside:
        # A radial groove wall can fall between two sampling nodes.  The left
        # and right limits are represented by the two endpoint profile values.
        # Multiple breaks inside one resolution cell are collapsed in order;
        # this still avoids inventing a bevel between distinct material states.
        spans: list[tuple[float, float, float, float, float, float]] = []
        left_z = z0
        left_inner, left_outer = inner0, outer0
        for wall_z in inside:
            spans.append((left_z, wall_z, left_inner, left_outer, left_inner, left_outer))
            left_z = wall_z
            left_inner, left_outer = inner1, outer1
        spans.append((left_z, z1, left_inner, left_outer, inner1, outer1))
        return tuple(spans)

    if at_start and at_end:
        # Both sample nodes are exact groove-wall locations.  Each node value
        # includes the material removed on the cutting side of its own wall,
        # so swapping both endpoints would draw a false diagonal wedge across
        # the whole cell.  Keep the less-removed state through the cell and let
        # the recorded breaks provide the two vertical discontinuities.
        thickness0 = max(0.0, outer0 - inner0)
        thickness1 = max(0.0, outer1 - inner1)
        if thickness0 >= thickness1:
            inner, outer = inner0, outer0
        else:
            inner, outer = inner1, outer1
        return ((z0, z1, inner, outer, inner, outer),)

    start_inner, start_outer = (inner1, outer1) if at_start else (inner0, outer0)
    end_inner, end_outer = (inner0, outer0) if at_end else (inner1, outer1)
    return ((z0, z1, start_inner, start_outer, end_inner, end_outer),)


def _convex_hull(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Return the convex hull of 2D points in counter-clockwise order."""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return tuple(unique)

    def cross(origin, first, second) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= _EPS:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= _EPS:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])


def _arc_sample_positions(motion: TraceMotion, chord_error: float) -> list[tuple[float, float]]:
    """Sample an arc centre path by geometric error instead of profile spacing."""
    if motion.arc is None:
        return [(motion.start_x * 0.5, motion.start_z), (motion.end_x * 0.5, motion.end_z)]
    radius = max(float(motion.arc.radius), 1e-9)
    sweep = max(float(motion.arc.sweep), 1e-12)
    error = min(max(float(chord_error), 1e-6), radius * 2.0)
    segment_angle = 4.0 * math.asin(math.sqrt(error / (2.0 * radius)))
    count = MAX_MOTION_SAMPLES if segment_angle <= 0.0 else int(math.ceil(sweep / segment_angle))
    count = min(MAX_MOTION_SAMPLES, max(1, count))
    points_per_circle = max(4, int(math.ceil(count * 2.0 * math.pi / sweep)))
    sampled = sample_motion(motion, 0, arc_points_per_circle=points_per_circle, lathe_radius_view=True)
    return [(motion.start_x * 0.5, motion.start_z), *((point.x, point.z) for point in sampled)]


class TurningStockTimeline:
    """Lazy, reversible OD/ID material-removal timeline for turning."""

    def __init__(
        self,
        motions,
        spec: TurningStockSpec,
        tools: dict[str, dict[str, object]] | None = None,
    ):
        spec.validate()
        self.spec = spec
        self.tools = tools or {}
        self.motions = tuple(motions)
        segment_count = max(1, int(math.ceil(spec.length / spec.resolution)))
        self.step = spec.length / segment_count
        back_z = spec.front_z - spec.length
        self.z = [back_z + self.step * index for index in range(segment_count + 1)]
        self.initial_inner = [spec.inner_diameter * 0.5] * len(self.z)
        self.initial_outer = [spec.outer_diameter * 0.5] * len(self.z)
        self.inner = self.initial_inner.copy()
        self.outer = self.initial_outer.copy()
        initial_interval = ((spec.inner_diameter * 0.5, spec.outer_diameter * 0.5),)
        self.initial_material_intervals = [initial_interval] * len(self.z)
        self.material_intervals = self.initial_material_intervals.copy()
        self.deltas: list[TurningDelta | None] = [None] * len(self.motions)
        self.motion_count = 0
        self.revision = 0
        self._active_break_counts: dict[float, int] = {}
        self._profile_breaks_cache: tuple[float, ...] = ()
        self._profile_breaks_dirty = False

    def _profile_index(self, z_value: float) -> int:
        return max(0, min(len(self.z) - 1, int(round((z_value - self.z[0]) / self.step))))

    def _motion_side(self, motion: TraceMotion, tool_type: str) -> str:
        if tool_type in {"drill", "id_80", "id_35", "id_groove"}:
            return "id"
        if tool_type in {"face_groove", "od_80", "od_35", "od_groove"}:
            return "od"
        index = self._profile_index(motion.start_z)
        start_radius = abs(motion.start_x * 0.5)
        inner_distance = abs(start_radius - self.inner[index])
        outer_distance = abs(start_radius - self.outer[index])
        return "id" if start_radius <= self.inner[index] + self.step or inner_distance < outer_distance else "od"

    def _remember(self, changes, index: int, new_inner: float, new_outer: float) -> None:
        old = changes.get(index)
        if old is None:
            old_inner = self.inner[index]
            old_outer = self.outer[index]
            old_intervals = self.material_intervals[index]
        else:
            old_inner = old[0]
            old_outer = old[2]
            old_intervals = old[4]
        new_inner = max(self.inner[index], min(new_inner, new_outer))
        new_outer = min(self.outer[index], max(new_outer, new_inner))
        if new_inner > self.inner[index] + _EPS or new_outer < self.outer[index] - _EPS:
            clipped = tuple(
                (max(start, new_inner), min(end, new_outer))
                for start, end in self.material_intervals[index]
                if min(end, new_outer) > max(start, new_inner) + _EPS
            )
            self.inner[index] = new_inner
            self.outer[index] = new_outer
            self.material_intervals[index] = clipped
            changes[index] = (old_inner, new_inner, old_outer, new_outer, old_intervals, clipped)

    def _subtract_local_interval(self, changes, index: int, minimum_x: float, maximum_x: float) -> None:
        """Remove one bounded radial interval while retaining material on both sides."""
        minimum_x = max(0.0, float(minimum_x))
        maximum_x = max(minimum_x, float(maximum_x))
        old_intervals = self.material_intervals[index]
        result: list[tuple[float, float]] = []
        for start, end in old_intervals:
            if maximum_x <= start + _EPS or minimum_x >= end - _EPS:
                result.append((start, end))
                continue
            if minimum_x > start + _EPS:
                result.append((start, min(minimum_x, end)))
            if maximum_x < end - _EPS:
                result.append((max(maximum_x, start), end))
        new_intervals = tuple(result)
        if new_intervals == old_intervals:
            return
        old = changes.get(index)
        old_inner = self.inner[index] if old is None else old[0]
        old_outer = self.outer[index] if old is None else old[2]
        original_intervals = old_intervals if old is None else old[4]
        if new_intervals:
            new_inner = new_intervals[0][0]
            new_outer = new_intervals[-1][1]
        else:
            new_inner = new_outer = self.inner[index]
        self.material_intervals[index] = new_intervals
        self.inner[index] = new_inner
        self.outer[index] = new_outer
        changes[index] = (old_inner, new_inner, old_outer, new_outer, original_intervals, new_intervals)

    def _apply_swept_footprint(
        self,
        changes,
        start: tuple[float, float],
        end: tuple[float, float],
        footprint: tuple[tuple[float, float], ...],
        side: str,
    ) -> None:
        """Subtract the exact linear sweep of a convex X/Z cutter silhouette."""
        if not footprint:
            return
        start_x, start_z = start
        end_x, end_z = end
        swept = _convex_hull(
            [
                *((abs(float(start_x)) + x_value, float(start_z) + z_value) for x_value, z_value in footprint),
                *((abs(float(end_x)) + x_value, float(end_z) + z_value) for x_value, z_value in footprint),
            ]
        )
        if len(swept) < 3:
            return
        minimum_z = min(point[1] for point in swept)
        maximum_z = max(point[1] for point in swept)
        first = max(0, int(math.floor((minimum_z - self.z[0]) / self.step)))
        last = min(len(self.z) - 1, int(math.ceil((maximum_z - self.z[0]) / self.step)))
        for index in range(first, last + 1):
            span = _horizontal_span(swept, self.z[index])
            if span is None:
                continue
            minimum_x, maximum_x = span
            if side == "id":
                candidate = maximum_x
                if candidate <= self.inner[index] + _EPS:
                    continue
                self._remember(changes, index, min(candidate, self.outer[index]), self.outer[index])
            else:
                candidate = minimum_x
                if candidate >= self.outer[index] - _EPS:
                    continue
                self._remember(changes, index, self.inner[index], max(candidate, self.inner[index]))

    def _apply_local_swept_footprint(
        self,
        changes,
        start: tuple[float, float],
        end: tuple[float, float],
        footprint: tuple[tuple[float, float], ...],
    ) -> None:
        """Subtract a bounded swept cutter footprint for axial face grooving."""
        start_x, start_z = start
        end_x, end_z = end
        swept = _convex_hull(
            [
                *((abs(float(start_x)) + x, float(start_z) + z) for x, z in footprint),
                *((abs(float(end_x)) + x, float(end_z) + z) for x, z in footprint),
            ]
        )
        if len(swept) < 3:
            return
        minimum_z = min(point[1] for point in swept)
        maximum_z = max(point[1] for point in swept)
        first = max(0, int(math.floor((minimum_z - self.z[0]) / self.step)))
        last = min(len(self.z) - 1, int(math.ceil((maximum_z - self.z[0]) / self.step)))
        for index in range(first, last + 1):
            span = _horizontal_span(swept, self.z[index])
            if span is not None:
                self._subtract_local_interval(changes, index, *span)

    def _apply_drill_sample(self, changes, tip_z: float, spec) -> None:
        diameter = _positive_float(spec, "diameter")
        if diameter <= _EPS:
            return
        tip_angle = _positive_float(spec, "tipAngle", 118.0)
        tip_angle = min(179.0, max(1.0, tip_angle))
        full_radius = diameter * 0.5
        tangent = math.tan(math.radians(tip_angle * 0.5))
        cone_length = full_radius / max(tangent, _EPS)
        first = max(0, int(math.ceil((tip_z - self.z[0]) / self.step)))
        for index in range(first, len(self.z)):
            axial = self.z[index] - tip_z
            if axial < -_EPS:
                continue
            cutter_radius = full_radius if axial >= cone_length else max(0.0, axial * tangent)
            if cutter_radius <= self.inner[index] + _EPS:
                continue
            self._remember(changes, index, min(cutter_radius, self.outer[index]), self.outer[index])

    def _compute_delta(self, motion: TraceMotion) -> TurningDelta:
        changes: dict[int, tuple[float, float, float, float]] = {}
        if motion.move not in (1, 2, 3):
            return TurningDelta(())
        spec = self.tools.get(motion.tool or "")
        if not isinstance(spec, dict):
            return TurningDelta(())
        tool_type = canonical_turning_tool_type(spec.get("type"))
        side = self._motion_side(motion, tool_type)
        footprint = turning_tool_polygon(spec, self.spec.outer_diameter, stock_scope=True)
        breaks = _radial_groove_breaks(motion, footprint, tool_type)
        if motion.move in (2, 3) and motion.arc is not None:
            chord_error = min(0.05, max(0.005, self.step * 0.25))
            positions = _arc_sample_positions(motion, chord_error)
        else:
            positions = [(motion.start_x * 0.5, motion.start_z), (motion.end_x * 0.5, motion.end_z)]

        if tool_type == "drill":
            self._apply_drill_sample(changes, min(position[1] for position in positions), spec)
        elif footprint is not None:
            for start, end in zip(positions, positions[1:], strict=False):
                if tool_type == "face_groove":
                    self._apply_local_swept_footprint(changes, start, end, footprint)
                else:
                    self._apply_swept_footprint(changes, start, end, footprint, side)
        return TurningDelta(
            tuple(
                (index, old_inner, new_inner, old_outer, new_outer, old_intervals, new_intervals)
                for index, (old_inner, new_inner, old_outer, new_outer, old_intervals, new_intervals) in sorted(
                    changes.items()
                )
            ),
            breaks,
        )

    def _activate_breaks(self, breaks: tuple[float, ...]) -> None:
        if not breaks:
            return
        for value in breaks:
            self._active_break_counts[value] = self._active_break_counts.get(value, 0) + 1
        self._profile_breaks_dirty = True

    def _deactivate_breaks(self, breaks: tuple[float, ...]) -> None:
        if not breaks:
            return
        for value in breaks:
            count = self._active_break_counts.get(value, 0) - 1
            if count > 0:
                self._active_break_counts[value] = count
            else:
                self._active_break_counts.pop(value, None)
        self._profile_breaks_dirty = True

    def set_motion_count(self, count: int) -> None:
        target = max(0, min(int(count), len(self.motions)))
        changed = False
        if target > self.motion_count:
            for index in range(self.motion_count, target):
                delta = self.deltas[index]
                if delta is None:
                    delta = self._compute_delta(self.motions[index])
                    self.deltas[index] = delta
                else:
                    for (
                        profile_index,
                        _old_inner,
                        new_inner,
                        _old_outer,
                        new_outer,
                        _old_intervals,
                        new_intervals,
                    ) in delta.changes:
                        self.inner[profile_index] = new_inner
                        self.outer[profile_index] = new_outer
                        self.material_intervals[profile_index] = new_intervals
                self._activate_breaks(delta.breaks)
                changed = changed or bool(delta.changes or delta.breaks)
        elif target < self.motion_count:
            for index in range(self.motion_count - 1, target - 1, -1):
                delta = self.deltas[index]
                if delta is None:
                    continue
                for (
                    profile_index,
                    old_inner,
                    _new_inner,
                    old_outer,
                    _new_outer,
                    old_intervals,
                    _new_intervals,
                ) in reversed(delta.changes):
                    self.inner[profile_index] = old_inner
                    self.outer[profile_index] = old_outer
                    self.material_intervals[profile_index] = old_intervals
                self._deactivate_breaks(delta.breaks)
                changed = changed or bool(delta.changes or delta.breaks)
        self.motion_count = target
        if changed:
            self.revision += 1

    @property
    def profile_breaks(self) -> tuple[float, ...]:
        """Exact axial discontinuities contributed by completed motions."""
        if self._profile_breaks_dirty:
            self._profile_breaks_cache = tuple(sorted(self._active_break_counts))
            self._profile_breaks_dirty = False
        return self._profile_breaks_cache

    @property
    def bounds(self):
        outer = self.spec.outer_diameter * 0.5
        return ((-outer, outer), (0.0, 0.0), (self.z[0], self.z[-1]))
