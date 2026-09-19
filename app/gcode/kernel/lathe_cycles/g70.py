"""G70 finishing-cycle contour expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2, ProfileSegment
from ..geometry import try_compute_signed_arc_radius_from_center
from .common import add_motion, add_motion_with_meta


def build_finish_contour(
    profile: list[ProfileSegment],
    *,
    entry_start: Point2 | None = None,
) -> list[Motion]:
    motions: list[Motion] = []
    if profile and entry_start is not None:
        add_motion(motions, 0, entry_start, profile[0].start)
    for seg in profile:
        if seg.move in (2, 3):
            r = seg.radius if seg.has_radius else None
            if r is None and seg.has_center:
                r = try_compute_signed_arc_radius_from_center(seg.move, seg.start, seg.end, seg.center)
            i = (seg.center.x - seg.start.x) if seg.has_center else None
            k = (seg.center.z - seg.start.z) if seg.has_center else None
            add_motion_with_meta(motions, seg.move, seg.start, seg.end, r, None, i=i, k=k)
        else:
            add_motion_with_meta(motions, 1, seg.start, seg.end, None, None)
    return motions
