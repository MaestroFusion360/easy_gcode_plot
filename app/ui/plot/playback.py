"""Logical playback mapping over the detailed execution trace."""

from __future__ import annotations

from dataclasses import dataclass


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
