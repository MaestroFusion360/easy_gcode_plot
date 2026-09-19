"""Shared motion-building helpers for FANUC canned-cycle expansion."""

from __future__ import annotations

from ..api.resources import SemanticError, checkpoint, require_progress
from ..frontend.model import Motion, Point2, ProfileSegment
from ..geometry import arc_center_from_r, try_compute_signed_arc_radius_from_center


def add_motion(
    motions: list[Motion],
    move: int,
    s: Point2,
    e: Point2,
    *,
    source_block: int | None = None,
    source_nlabel: int | None = None,
    source_raw: str | None = None,
    source_kind: str = "motion",
    playback_group: int | None = None,
) -> None:
    if abs(s.x - e.x) <= 1e-6 and abs(s.z - e.z) <= 1e-6:
        return
    checkpoint("generated_motions")
    motions.append(
        Motion(
            move=move,
            start=s,
            end=e,
            source_block=source_block,
            source_nlabel=source_nlabel,
            source_raw=source_raw,
            source_kind=source_kind,
            playback_group=playback_group,
        )
    )


def add_motion_with_meta(
    motions: list[Motion],
    move: int,
    s: Point2,
    e: Point2,
    radius: float | None,
    feed: float | None,
    i: float | None = None,
    k: float | None = None,
    *,
    source_block: int | None = None,
    source_nlabel: int | None = None,
    source_raw: str | None = None,
    source_kind: str = "motion",
    playback_group: int | None = None,
) -> None:
    if s == e and move not in (2, 3):
        return
    arc_i = i
    arc_k = k
    if move in (2, 3) and arc_i is None and arc_k is None and radius is not None:
        center = arc_center_from_r(s, e, radius, move, x_scale=0.5)
        if center is None:
            raise SemanticError("INVALID_GEOMETRY", "Invalid cycle R arc", "invalid_geometry")
        if center is not None:
            arc_i = center.x - s.x
            arc_k = center.z - s.z
    checkpoint("generated_motions")
    motions.append(
        Motion(
            move=move,
            start=s,
            end=e,
            radius=radius,
            feed=feed,
            i=arc_i,
            k=arc_k,
            source_block=source_block,
            source_nlabel=source_nlabel,
            source_raw=source_raw,
            source_kind=source_kind,
            playback_group=playback_group,
        )
    )


def add_feed_orthogonal(motions: list[Motion], s: Point2, e: Point2, feed: float) -> None:
    """Add feed motion using orthogonal X/Z legs (no diagonal feed segments)."""
    if abs(s.x - e.x) <= 1e-6 and abs(s.z - e.z) <= 1e-6:
        return
    f = feed if feed > 0 else None
    if abs(s.x - e.x) > 1e-6 and abs(s.z - e.z) > 1e-6:
        mid = Point2(e.x, s.z)
        add_motion_with_meta(motions, 1, s, mid, None, f)
        add_motion_with_meta(motions, 1, mid, e, None, f)
        return
    add_motion_with_meta(motions, 1, s, e, None, f)


def ensure_cycle_return(motions: list[Motion], target: Point2, *, first_axis: str | None = None) -> None:
    """Return a completed cycle to its saved call position in an explicit axis order.

    This is authoritative FANUC turning behavior in fanuc_plot, not a
    geometric inference. G72/G74 callers use Z then X; G71/G73/G75 callers use
    X then Z. G70/G76 currently use X then Z as the safe longitudinal order.
    """
    if not motions:
        return
    current = motions[-1].end
    if first_axis == "x":
        add_rapid_orthogonal(motions, current, target, first_axis="x")
        return
    if first_axis == "z":
        add_rapid_orthogonal(motions, current, target, first_axis="z")
        return
    add_motion(motions, 0, current, target)


def add_rapid_orthogonal(motions: list[Motion], start: Point2, end: Point2, *, first_axis: str) -> None:
    """Add an axis-ordered rapid without an X/Z diagonal."""
    middle = Point2(end.x, start.z) if first_axis == "x" else Point2(start.x, end.z)
    add_motion(motions, 0, start, middle)
    add_motion(motions, 0, middle, end)


def _append_profile_trace(motions: list[Motion], profile: list[ProfileSegment], feed: float) -> None:
    if not profile:
        return
    add_motion(
        motions,
        0,
        motions[-1].end if motions else profile[0].start,
        profile[0].start,
        source_block=profile[0].block,
        source_kind="cycle",
    )
    for seg in profile:
        if seg.move in (2, 3):
            r = seg.radius if seg.has_radius else None
            if r is None and seg.has_center:
                r = try_compute_signed_arc_radius_from_center(seg.move, seg.start, seg.end, seg.center)
            i = (seg.center.x - seg.start.x) if seg.has_center else None
            k = (seg.center.z - seg.start.z) if seg.has_center else None
            add_motion_with_meta(
                motions,
                seg.move,
                seg.start,
                seg.end,
                r,
                feed if feed > 0 else None,
                i=i,
                k=k,
                source_block=seg.block,
                source_kind="cycle",
                playback_group=seg.playback_group,
            )
        else:
            add_motion_with_meta(
                motions,
                1,
                seg.start,
                seg.end,
                None,
                feed if feed > 0 else None,
                source_block=seg.block,
                source_kind="cycle",
                playback_group=seg.playback_group,
            )


def _linspace_steps(start: float, end: float, step: float) -> list[float]:
    if abs(end - start) <= 1e-9:
        return [end]
    if step <= 1e-9:
        return [end]
    vals: list[float] = [start]
    cur = start
    direction = 1.0 if end > start else -1.0
    while (end - cur) * direction > step:
        checkpoint("cycle_iterations")
        require_progress(cur, cur + direction * step)
        cur += direction * step
        vals.append(cur)
    if abs(vals[-1] - end) > 1e-9:
        vals.append(end)
    return vals
