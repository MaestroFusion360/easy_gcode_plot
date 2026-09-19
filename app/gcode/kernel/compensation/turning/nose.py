"""Tool-nose compensation for resolved lathe motions."""

from __future__ import annotations

import math
from dataclasses import replace

from ...frontend.model import Motion, Point2
from ...frontend.program import move_for_xz_plot
from ...geometry import arc_center_from_r
from ..common import EPS, ToolCompensationError
from ..geometry import TurningPrimitive, Vec2
from .joins import join_primitives

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


def to_vec(point: Point2) -> Vec2:
    return Vec2(point.x * 0.5, point.z)


def to_point(point: Vec2) -> Point2:
    return Point2(point.x * 2.0, point.y)


def tip_orientation_vector(orientation: int, radius: float) -> tuple[float, float]:
    """Return the reference-point translation in radial-X/Z coordinates."""
    try:
        dx, dz = _TIP_DIRECTIONS[int(orientation)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolCompensationError("Tool tip orientation must be in the range 1-9.") from exc
    return dx * radius, dz * radius


def arc_center(motion: Motion) -> Vec2 | None:
    if motion.i is not None or motion.k is not None:
        i_value = float(motion.i or 0.0)
        k_value = float(motion.k or 0.0)
        start = to_vec(motion.start)
        end = to_vec(motion.end)
        center = Vec2(start.x + i_value * 0.5, start.y + k_value)
        r0 = math.hypot(start.x - center.x, start.y - center.y)
        r1 = math.hypot(end.x - center.x, end.y - center.y)
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
    return to_vec(center) if center is not None else None


def offset_motion(motion: Motion, radius: float, orientation: int) -> TurningPrimitive:
    start = to_vec(motion.start)
    end = to_vec(motion.end)
    tip_x, tip_z = tip_orientation_vector(orientation, radius)
    # In the X/Z turning plane the trace's handedness is opposite to the
    # conventional XY cutter-compensation view: FANUC G42 offsets to the left
    # of increasing contour order here, while G41 offsets to the right.
    side = -1.0 if motion.compensation_mode == 41 else 1.0

    if motion.move in (0, 1):
        dx = end.x - start.x
        dz = end.y - start.y
        length = math.hypot(dx, dz)
        if length <= EPS:
            shift = Vec2(tip_x, tip_z)
        else:
            shift = Vec2((-dz / length) * side * radius + tip_x, (dx / length) * side * radius + tip_z)
        return TurningPrimitive(
            motion,
            Vec2(start.x + shift.x, start.y + shift.y),
            Vec2(end.x + shift.x, end.y + shift.y),
        )

    if motion.move not in (2, 3):
        raise ToolCompensationError(f"G{motion.move} is not supported during G41/G42.")
    center = arc_center(motion)
    if center is None:
        raise ToolCompensationError("An active G41/G42 arc has no deterministic center.")
    base_radius = math.hypot(start.x - center.x, start.y - center.y)
    mapped_move = move_for_xz_plot(motion.move)
    offset_radius = base_radius + (side * radius if mapped_move == 2 else -side * radius)
    if offset_radius <= EPS:
        raise ToolCompensationError("Tool nose radius collapses the compensated arc.")

    def shifted(point: Vec2) -> Vec2:
        vx = point.x - center.x
        vz = point.y - center.y
        length = math.hypot(vx, vz)
        if length <= EPS:
            raise ToolCompensationError("Invalid zero-radius arc during compensation.")
        return Vec2(
            center.x + vx * offset_radius / length + tip_x,
            center.y + vz * offset_radius / length + tip_z,
        )

    shifted_center = Vec2(center.x + tip_x, center.y + tip_z)
    return TurningPrimitive(motion, shifted(start), shifted(end), shifted_center)


def motion_from_primitive(primitive: TurningPrimitive) -> Motion:
    center = primitive.center
    return replace(
        primitive.motion,
        start=to_point(primitive.start),
        end=to_point(primitive.end),
        radius=None if center is not None else primitive.motion.radius,
        i=(center.x - primitive.start.x) if center is not None else primitive.motion.i,
        k=(center.y - primitive.start.y) if center is not None else primitive.motion.k,
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
        if str(tool.get("type", "")).lower() not in {
            "diamond_80",
            "diamond_35",
            "square",
            "round",
            "triangle",
            "groove",
        }:
            raise ToolCompensationError(f"G41/G42 requires a turning tool, got {tool.get('type')!r}.")
        try:
            radius = float(tool["noseRadius"])
            orientation = int(tool["tipOrientation"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolCompensationError(f"{motion.tool} requires noseRadius and tipOrientation 1-9.") from exc
        if radius <= 0.0:
            raise ToolCompensationError(f"{motion.tool} nose radius must be positive.")

        primitives = [offset_motion(item, radius, orientation) for item in run]
        entry_transition = index == 0 or motions[index - 1].compensation_mode not in (41, 42)
        join_start = 1 if entry_transition and len(primitives) > 1 else 0
        for pos in range(join_start, len(primitives) - 1):
            join = join_primitives(primitives[pos], primitives[pos + 1])
            primitives[pos] = replace(primitives[pos], end=join)
            primitives[pos + 1] = replace(primitives[pos + 1], start=join)
        if entry_transition and primitives:
            # The activation block is a transition from the current reference
            # point to the compensated start of the following cutting segment.
            # It is not itself part of the contour offset calculation.
            entry_end = primitives[1].start if len(primitives) > 1 else primitives[0].end
            primitives[0] = replace(
                primitives[0],
                start=to_vec(run[0].start),
                end=entry_end,
                center=None,
            )
        result.extend(motion_from_primitive(item) for item in primitives)
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
