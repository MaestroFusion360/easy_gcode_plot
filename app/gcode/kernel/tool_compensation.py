"""Deterministic two-axis lathe tool-nose radius compensation."""

from __future__ import annotations

# Geometric candidate iteration deliberately uses a set to remove duplicates.
# pylint: disable=use-sequence-for-iteration
import math
from dataclasses import dataclass, replace

from .model import Motion, Point2, ProfileSegment
from .profile import arc_center_from_r
from .program import move_for_xz_plot

_EPS = 1e-9


class ToolCompensationError(ValueError):
    """Raised when an active compensation run cannot be constructed exactly."""


@dataclass(frozen=True)
class _Vec:
    x: float  # radial X, not programmed diameter X
    z: float


@dataclass(frozen=True)
class _Primitive:
    motion: Motion
    start: _Vec
    end: _Vec
    center: _Vec | None = None


# FANUC imaginary tool-tip direction numbers in the X/Z plane.  Values are
# center-to-imaginary-tip directions; 9 represents a round tool referenced at
# the nose center.
_TIP_DIRECTIONS: dict[int, tuple[int, int]] = {
    1: (1, 1),
    2: (1, -1),
    3: (-1, -1),
    4: (-1, 1),
    5: (0, 1),
    6: (1, 0),
    7: (0, -1),
    8: (-1, 0),
    9: (0, 0),
}


def tip_orientation_vector(orientation: int, radius: float) -> tuple[float, float]:
    """Return the reference-point translation in radial-X/Z coordinates."""
    try:
        dx, dz = _TIP_DIRECTIONS[int(orientation)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolCompensationError("Tool tip orientation must be in the range 1-9.") from exc
    return dx * radius, dz * radius


def _to_vec(point: Point2) -> _Vec:
    return _Vec(point.x * 0.5, point.z)


def _to_point(point: _Vec) -> Point2:
    return Point2(point.x * 2.0, point.z)


def _arc_center(motion: Motion) -> _Vec | None:
    if motion.i is not None or motion.k is not None:
        i_value = float(motion.i or 0.0)
        k_value = float(motion.k or 0.0)
        start = _to_vec(motion.start)
        end = _to_vec(motion.end)
        center = _Vec(start.x + i_value * 0.5, start.z + k_value)
        r0 = math.hypot(start.x - center.x, start.z - center.z)
        r1 = math.hypot(end.x - center.x, end.z - center.z)
        if r0 <= 1e-10 or abs(r0 - r1) > max(0.002, r0 * 1e-5):
            raise ToolCompensationError("Invalid tool compensation arc")
        return center
    if motion.radius is None:
        return None
    center = arc_center_from_r(
        motion.start,
        motion.end,
        float(motion.radius),
        motion.move,
        x_scale=0.5,
    )
    return _to_vec(center) if center is not None else None


def _offset_motion(motion: Motion, radius: float, orientation: int) -> _Primitive:
    start = _to_vec(motion.start)
    end = _to_vec(motion.end)
    tip_x, tip_z = tip_orientation_vector(orientation, radius)
    # In the X/Z turning plane the trace's handedness is opposite to the
    # conventional XY cutter-compensation view: FANUC G42 offsets to the left
    # of increasing contour order here, while G41 offsets to the right.
    side = -1.0 if motion.compensation_mode == 41 else 1.0

    if motion.move in (0, 1):
        dx = end.x - start.x
        dz = end.z - start.z
        length = math.hypot(dx, dz)
        if length <= _EPS:
            shift = _Vec(tip_x, tip_z)
        else:
            shift = _Vec((-dz / length) * side * radius + tip_x, (dx / length) * side * radius + tip_z)
        return _Primitive(
            motion,
            _Vec(start.x + shift.x, start.z + shift.z),
            _Vec(end.x + shift.x, end.z + shift.z),
        )

    if motion.move not in (2, 3):
        raise ToolCompensationError(f"G{motion.move} is not supported during G41/G42.")
    center = _arc_center(motion)
    if center is None:
        raise ToolCompensationError("An active G41/G42 arc has no deterministic center.")
    base_radius = math.hypot(start.x - center.x, start.z - center.z)
    mapped_move = move_for_xz_plot(motion.move)
    offset_radius = base_radius + (side * radius if mapped_move == 2 else -side * radius)
    if offset_radius <= _EPS:
        raise ToolCompensationError("Tool nose radius collapses the compensated arc.")

    def shifted(point: _Vec) -> _Vec:
        vx = point.x - center.x
        vz = point.z - center.z
        length = math.hypot(vx, vz)
        if length <= _EPS:
            raise ToolCompensationError("Invalid zero-radius arc during compensation.")
        return _Vec(
            center.x + vx * offset_radius / length + tip_x,
            center.z + vz * offset_radius / length + tip_z,
        )

    shifted_center = _Vec(center.x + tip_x, center.z + tip_z)
    return _Primitive(motion, shifted(start), shifted(end), shifted_center)


def _line_intersection(a: _Primitive, b: _Primitive) -> list[_Vec]:
    avx, avz = a.end.x - a.start.x, a.end.z - a.start.z
    bvx, bvz = b.end.x - b.start.x, b.end.z - b.start.z
    determinant = avx * bvz - avz * bvx
    if abs(determinant) <= _EPS:
        if math.hypot(a.end.x - b.start.x, a.end.z - b.start.z) <= 1e-7:
            return [a.end]
        return []
    dx, dz = b.start.x - a.start.x, b.start.z - a.start.z
    progress = (dx * bvz - dz * bvx) / determinant
    return [_Vec(a.start.x + progress * avx, a.start.z + progress * avz)]


def _line_circle(line: _Primitive, arc: _Primitive) -> list[_Vec]:
    assert arc.center is not None
    vx, vz = line.end.x - line.start.x, line.end.z - line.start.z
    ox, oz = line.start.x - arc.center.x, line.start.z - arc.center.z
    aa = vx * vx + vz * vz
    if aa <= _EPS:
        return []
    radius = math.hypot(arc.start.x - arc.center.x, arc.start.z - arc.center.z)
    bb = 2.0 * (vx * ox + vz * oz)
    cc = ox * ox + oz * oz - radius * radius
    discriminant = bb * bb - 4.0 * aa * cc
    if discriminant < -_EPS:
        return []
    root = math.sqrt(max(0.0, discriminant))
    return [
        _Vec(line.start.x + t * vx, line.start.z + t * vz)
        for t in {(-bb - root) / (2.0 * aa), (-bb + root) / (2.0 * aa)}
    ]


def _circle_circle(a: _Primitive, b: _Primitive) -> list[_Vec]:
    assert a.center is not None and b.center is not None
    ar = math.hypot(a.start.x - a.center.x, a.start.z - a.center.z)
    br = math.hypot(b.start.x - b.center.x, b.start.z - b.center.z)
    dx, dz = b.center.x - a.center.x, b.center.z - a.center.z
    distance = math.hypot(dx, dz)
    if distance <= _EPS or distance > ar + br + _EPS or distance < abs(ar - br) - _EPS:
        return []
    along = (ar * ar - br * br + distance * distance) / (2.0 * distance)
    height_sq = ar * ar - along * along
    if height_sq < -_EPS:
        return []
    height = math.sqrt(max(0.0, height_sq))
    mx = a.center.x + along * dx / distance
    mz = a.center.z + along * dz / distance
    rx, rz = -dz * height / distance, dx * height / distance
    return [_Vec(mx + rx, mz + rz), _Vec(mx - rx, mz - rz)]


def _join(a: _Primitive, b: _Primitive) -> _Vec:
    if a.center is None and b.center is None:
        candidates = _line_intersection(a, b)
    elif a.center is None:
        candidates = _line_circle(a, b)
    elif b.center is None:
        candidates = _line_circle(b, a)
    else:
        candidates = _circle_circle(a, b)
    if not candidates:
        raise ToolCompensationError("Adjacent compensated segments do not intersect.")
    return min(
        candidates,
        key=lambda point: (
            math.hypot(point.x - a.end.x, point.z - a.end.z) + math.hypot(point.x - b.start.x, point.z - b.start.z)
        ),
    )


def _motion_from_primitive(primitive: _Primitive) -> Motion:
    center = primitive.center
    return replace(
        primitive.motion,
        start=_to_point(primitive.start),
        end=_to_point(primitive.end),
        radius=None if center is not None else primitive.motion.radius,
        i=(center.x - primitive.start.x) if center is not None else primitive.motion.i,
        k=(center.z - primitive.start.z) if center is not None else primitive.motion.k,
        source_kind="tool_compensation",
        compensation_applied=True,
    )


def apply_tool_nose_compensation(motions: list[Motion], tools: dict[str, dict[str, object]]) -> list[Motion]:
    """Apply configured G41/G42 geometry to the authoritative Motion Trace."""
    if not motions or not tools:
        return motions

    result: list[Motion] = []
    index = 0
    while index < len(motions):
        motion = motions[index]
        if motion.compensation_applied:
            result.append(motion)
            index += 1
            continue
        if motion.compensation_mode not in (41, 42):
            if result and result[-1].compensation_mode in (41, 42):
                motion = replace(motion, start=result[-1].end, source_kind="tool_compensation_exit")
            result.append(motion)
            index += 1
            continue

        end = index
        while (
            end < len(motions)
            and motions[end].compensation_mode == motion.compensation_mode
            and motions[end].tool == motion.tool
        ):
            end += 1
        run = motions[index:end]
        tool = tools.get(motion.tool or "")
        if not isinstance(tool, dict):
            # A partial tool table must not make unrelated programs impossible
            # to view. The UI detects this nominal run, disables correction for
            # the document and reports the missing T code before rebuilding.
            result.extend(run)
            index = end
            continue
        if str(tool.get("type", "")).lower() != "turning":
            raise ToolCompensationError(f"G41/G42 requires a turning tool, got {tool.get('type')!r}.")
        try:
            radius = float(tool["noseRadius"])
            orientation = int(tool["tipOrientation"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolCompensationError(f"{motion.tool} requires noseRadius and tipOrientation 1-9.") from exc
        if radius <= 0.0:
            raise ToolCompensationError(f"{motion.tool} nose radius must be positive.")

        primitives = [_offset_motion(item, radius, orientation) for item in run]
        entry_transition = index == 0 or motions[index - 1].compensation_mode not in (41, 42)
        join_start = 1 if entry_transition and len(primitives) > 1 else 0
        for pos in range(join_start, len(primitives) - 1):
            join = _join(primitives[pos], primitives[pos + 1])
            primitives[pos] = replace(primitives[pos], end=join)
            primitives[pos + 1] = replace(primitives[pos + 1], start=join)
        if entry_transition and primitives:
            # The activation block is a transition from the current reference
            # point to the compensated start of the following cutting segment.
            # It is not itself part of the contour offset calculation.
            entry_end = primitives[1].start if len(primitives) > 1 else primitives[0].end
            primitives[0] = replace(
                primitives[0],
                start=_to_vec(run[0].start),
                end=entry_end,
                center=None,
            )
        result.extend(_motion_from_primitive(item) for item in primitives)
        index = end
    return result


def missing_compensation_tools(motions: list[Motion], tools: dict[str, dict[str, object]]) -> tuple[str, ...]:
    """Return active G41/G42 tool codes that have no tool-table entry."""
    missing = {
        motion.tool or "<no active T>"
        for motion in motions
        if motion.compensation_mode in (41, 42) and not isinstance(tools.get(motion.tool or ""), dict)
    }
    return tuple(sorted(missing))


def compensate_profile_segments(
    profile: list[ProfileSegment],
    *,
    compensation_mode: int,
    compensation_modes: dict[int, int] | None = None,
    tool_code: str | None,
    tools: dict[str, dict[str, object]],
) -> list[ProfileSegment]:
    """Offset one exact P-Q contour before canned-cycle pass generation."""
    modes = compensation_modes or {}
    if not profile or not any(modes.get(segment.block, compensation_mode) in (41, 42) for segment in profile):
        return profile
    motions: list[Motion] = []
    for segment in profile:
        motions.append(
            Motion(
                move=segment.move,
                start=segment.start,
                end=segment.end,
                radius=segment.radius if segment.has_radius else None,
                i=(segment.center.x - segment.start.x) if segment.has_center else None,
                k=(segment.center.z - segment.start.z) if segment.has_center else None,
                source_block=segment.block,
                compensation_mode=modes.get(segment.block, compensation_mode),
                tool=tool_code,
            )
        )
    compensated = apply_tool_nose_compensation(motions, tools)

    output: list[ProfileSegment] = []
    for original, motion in zip(profile, compensated):
        has_center = motion.i is not None or motion.k is not None
        arc_center = _arc_center(motion) if has_center else None
        center = _to_point(arc_center) if arc_center is not None else Point2(0.0, 0.0)
        output.append(
            replace(
                original,
                start=motion.start,
                end=motion.end,
                has_radius=motion.radius is not None,
                radius=float(motion.radius or 0.0),
                has_center=has_center,
                center=center,
            )
        )
    return output
