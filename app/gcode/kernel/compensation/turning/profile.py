"""Compensation of canned-cycle P-Q profile segments."""

from __future__ import annotations

from dataclasses import replace

from ...frontend.model import Motion, Point2, ProfileSegment
from .nose import apply_tool_nose_compensation, to_point
from .nose import arc_center as resolve_arc_center


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
        resolved_center = resolve_arc_center(motion) if has_center else None
        center = to_point(resolved_center) if resolved_center is not None else Point2(0.0, 0.0)
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
