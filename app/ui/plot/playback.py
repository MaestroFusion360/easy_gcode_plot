"""Logical playback mapping over the detailed execution trace."""

from __future__ import annotations

from dataclasses import dataclass

from app.gcode.trace_tools import sample_motion


@dataclass(frozen=True)
class PlaybackMovement:
    """Half-open range of detailed motions forming one CNC movement."""

    motion_start: int
    motion_end: int


def build_playback_movements(motions) -> tuple[tuple[PlaybackMovement, ...], tuple[int, ...]]:
    """Group only explicitly tagged approximation chords; keep all real moves."""
    ranges: list[PlaybackMovement] = []
    motion_to_playback: list[int] = []
    index = 0
    while index < len(motions):
        group = getattr(motions[index], "playback_group", None)
        end = index + 1
        if group is not None:
            while end < len(motions) and getattr(motions[end], "playback_group", None) == group:
                end += 1
        playback_index = len(ranges)
        ranges.append(PlaybackMovement(index, end))
        motion_to_playback.extend([playback_index] * (end - index))
        index = end
    return tuple(ranges), tuple(motion_to_playback)


PLAYBACK_ARC_POINTS_PER_CIRCLE = 24
PLAYBACK_ARC_MIN_FRAMES = 8
PLAYBACK_VISUAL_FRAME_MIN_MS = 8


def arc_playback_samples(motion, motion_index: int, *, max_frames: int | None = None):
    """Return deterministic visual samples for one analytical arc.

    Playback remains indexed by logical CNC motions; these samples are only
    transient cursor/tool positions used while Play is running.  Sampling is
    independent of the render tessellation settings so changing plot quality
    cannot change the logical slider range.
    """
    if motion.move not in (2, 3) or motion.arc is None:
        return ()
    points = tuple(
        sample_motion(
            motion,
            motion_index,
            arc_points_per_circle=PLAYBACK_ARC_POINTS_PER_CIRCLE,
        )
    )
    if len(points) <= 1 or max_frames is None or len(points) <= max_frames:
        return points

    limit = max(1, int(max_frames))
    if limit == 1:
        return (points[-1],)
    count = len(points)
    # Pick the end of each equal slice.  The last visual frame is therefore
    # always the exact analytical motion endpoint.
    return tuple(points[((slot + 1) * count + limit - 1) // limit - 1] for slot in range(limit))
