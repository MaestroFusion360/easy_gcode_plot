"""Compensation of canned-cycle P-Q profile segments."""

from __future__ import annotations

from dataclasses import replace

from ...frontend.model import Motion, Point2, ProfileSegment
from .nose import apply_tool_nose_compensation, to_point
from .nose import arc_center as resolve_arc_center


def _segment_motion(segment: ProfileSegment, mode: int, tool_code: str | None) -> Motion:
    return Motion(
        move=segment.move,
        start=segment.start,
        end=segment.end,
        radius=segment.radius if segment.has_radius else None,
        i=(segment.center.x - segment.start.x) if segment.has_center else None,
        k=(segment.center.z - segment.start.z) if segment.has_center else None,
        source_block=segment.block,
        compensation_mode=mode,
        tool=tool_code,
    )


def _compensated_segment(original: ProfileSegment, motion: Motion) -> ProfileSegment:
    has_center = motion.i is not None or motion.k is not None
    resolved_center = resolve_arc_center(motion) if has_center else None
    center = to_point(resolved_center) if resolved_center is not None else Point2(0.0, 0.0)
    return replace(
        original,
        start=motion.start,
        end=motion.end,
        has_radius=motion.radius is not None,
        radius=float(motion.radius or 0.0),
        has_center=has_center,
        center=center,
    )


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
    motions = [_segment_motion(segment, modes.get(segment.block, compensation_mode), tool_code) for segment in profile]
    compensated = apply_tool_nose_compensation(motions, tools)
    return [_compensated_segment(original, motion) for original, motion in zip(profile, compensated)]
