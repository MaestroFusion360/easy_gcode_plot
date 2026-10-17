"""G70 finishing-cycle contour expansion."""

from __future__ import annotations

from ...frontend.model import Motion, Point2, ProfileSegment
from .common import add_motion, add_motion_with_meta, profile_arc_words


def build_finish_contour(
    profile: list[ProfileSegment],
    *,
    entry_start: Point2 | None = None,
    feeds_by_block: dict[int, float | None] | None = None,
) -> list[Motion]:
    motions: list[Motion] = []
    if profile and entry_start is not None:
        add_motion(motions, 0, entry_start, profile[0].start)
    for seg in profile:
        feed = (feeds_by_block or {}).get(seg.block)
        if seg.move in (2, 3):
            r, i, k = profile_arc_words(seg)
            add_motion_with_meta(motions, seg.move, seg.start, seg.end, r, feed, i=i, k=k)
        else:
            add_motion_with_meta(motions, 1, seg.start, seg.end, None, feed)
    return motions
