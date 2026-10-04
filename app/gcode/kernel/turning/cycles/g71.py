"""G71 longitudinal roughing-cycle expansion."""

from __future__ import annotations

from ...api.resources import SemanticError, checkpoint
from ...frontend.model import Motion, Point2, ProfileSegment
from ...geometry import (
    clip_polyline_max_x,
    clip_polyline_min_x,
    segment_points,
    try_find_entry_on_profile,
    try_get_arc_geometry,
)
from .common import _append_profile_trace, add_feed_orthogonal, add_motion, add_motion_with_meta, ensure_cycle_return


def _follow_type_ii_profile(motions, profile, seg_idx, entry_pt, pass_x, next_pass_x, boring_mode, feed):
    """Follow one clipped Type II contour until the next depth boundary."""
    previous = entry_pt
    for index in range(seg_idx, len(profile)):
        segment = profile[index]
        start = entry_pt if index == seg_idx else segment.start
        points = segment_points(segment, start, segment.end)
        clipped = clip_polyline_min_x(points, pass_x) if boring_mode else clip_polyline_max_x(points, pass_x)
        if len(clipped) < 2:
            continue
        if abs(previous.x - clipped[0].x) > 1e-5 or abs(previous.z - clipped[0].z) > 1e-5:
            add_feed_orthogonal(motions, previous, clipped[0], feed)
            previous = clipped[0]
        for start_point, end_point in zip(clipped, clipped[1:]):
            crosses_next = (start_point.x - next_pass_x) * (end_point.x - next_pass_x) <= 0.0 and abs(
                end_point.x - start_point.x
            ) > 1e-8
            if crosses_next:
                fraction = (next_pass_x - start_point.x) / (end_point.x - start_point.x)
                fraction = max(0.0, min(1.0, fraction))
                end_point = Point2(next_pass_x, start_point.z + (end_point.z - start_point.z) * fraction)
            add_motion_with_meta(
                motions,
                1,
                previous,
                end_point,
                None,
                feed if feed > 0 else None,
                playback_group=segment.playback_group,
            )
            previous = end_point
            if crosses_next:
                return previous
    return previous


def _follow_type_i_profile(motions, profile, seg_idx, entry, boundary_x, feed):
    previous = entry
    for segment in profile[seg_idx:]:
        end = segment.end
        hit = None
        if abs(end.x - previous.x) > 1e-9 and (previous.x - boundary_x) * (end.x - boundary_x) <= 0:
            hit = try_find_entry_on_profile([segment], boundary_x)
        if hit is not None:
            end = hit[1]
        geometry = try_get_arc_geometry(segment) if segment.move in (2, 3) else None
        center = geometry.center if geometry is not None else None
        add_motion_with_meta(
            motions,
            segment.move if segment.move in (2, 3) else 1,
            previous,
            end,
            segment.radius if segment.has_radius else None,
            feed if feed > 0 else None,
            i=center.x - previous.x if center is not None else None,
            k=center.z - previous.z if center is not None else None,
            playback_group=segment.playback_group,
        )
        previous = end
        if hit is not None:
            break
    return previous


def _finish_roughing(motions, profile, tool, feed, type_ii, cycle_start, retract_r, boring_mode):
    if not type_ii:
        add_motion(motions, 0, tool, profile[0].start)
        _append_profile_trace(motions, profile, feed)
        end = motions[-1].end
        retract = abs(retract_r)
        retreat = Point2(
            end.x + (-2.0 * retract if boring_mode else 2.0 * retract),
            end.z + (retract if cycle_start.z >= end.z else -retract),
        )
        add_motion_with_meta(motions, 1, end, retreat, None, feed if feed > 0 else None)
    ensure_cycle_return(motions, cycle_start, first_axis="z")


def build_g71_roughing(
    profile: list[ProfileSegment],
    stock_x: float,
    stock_z: float,
    depth_u: float,
    retract_r: float,
    finish_w: float,
    feed: float,
    boring_mode: bool,
    type_ii: bool = False,
    stock_limit_x: float | None = None,
) -> list[Motion]:
    motions: list[Motion] = []
    if not profile:
        raise SemanticError("INVALID_G71_PROFILE", "G71 profile is empty", "invalid_input")
    cycle_start = Point2(stock_x, stock_z)
    step_dia = abs(depth_u) * 2.0
    if step_dia <= 1e-9:
        raise SemanticError("INVALID_G71_DEPTH", "G71 pass depth must be nonzero", "invalid_input")
    retract_dia = abs(retract_r) * 2.0
    min_x = min(min(s.start.x, s.end.x) for s in profile)
    max_x = max(max(s.start.x, s.end.x) for s in profile)
    # Keep cycle rapid plane at cycle start Z to match common expanded output.
    safe_z = stock_z

    limit_x = max_x if boring_mode else min_x
    cutting_stock = stock_x
    if stock_limit_x is not None:
        cutting_stock = max(stock_x, stock_limit_x) if boring_mode else min(stock_x, stock_limit_x)
    pass_x = min(cutting_stock + step_dia, limit_x) if boring_mode else max(cutting_stock - step_dia, limit_x)
    tool = Point2(stock_x, stock_z)

    guard = 0
    while (pass_x <= max_x + 1e-4) if boring_mode else (pass_x >= min_x - 1e-4):
        checkpoint("cycle_iterations")
        guard += 1
        if guard > 10000:
            raise SemanticError("RESOURCE_LIMIT", "Cycle exceeds 10000 passes", "resource_limit")
        entry = try_find_entry_on_profile(profile, pass_x)
        if entry is None:
            if abs(pass_x - limit_x) <= 1e-9:
                break
            pass_x = min(pass_x + step_dia, limit_x) if boring_mode else max(pass_x - step_dia, limit_x)
            continue

        seg_idx, entry_pt = entry
        next_pass_x = pass_x - step_dia if boring_mode else pass_x + step_dia
        rapid_x = pass_x - retract_dia if boring_mode else pass_x + retract_dia
        add_motion(motions, 0, tool, Point2(rapid_x, safe_z))
        add_motion(motions, 0, Point2(rapid_x, safe_z), Point2(pass_x, safe_z))
        add_feed_orthogonal(motions, Point2(pass_x, safe_z), entry_pt, feed)

        if not type_ii:
            # FANUC G71 Type I is a monotonic longitudinal roughing cycle: each
            # rough pass approaches parallel to Z, then follows the exact
            # contour up to the previous depth boundary.
            # The R retract is a short diagonal away from the material, followed
            # by a rapid return on the cycle-start Z plane.
            end = _follow_type_i_profile(motions, profile, seg_idx, entry_pt, next_pass_x, feed)
            retreat_x = end.x - retract_dia if boring_mode else end.x + retract_dia
            retreat_z = end.z + (abs(retract_r) if stock_z >= end.z else -abs(retract_r))
            retreat = Point2(retreat_x, retreat_z)
            add_motion_with_meta(motions, 1, end, retreat, None, feed if feed > 0 else None)
            tool = Point2(retreat.x, safe_z)
            add_motion(motions, 0, retreat, tool)
            if abs(pass_x - limit_x) <= 1e-9:
                break
            pass_x = min(pass_x + step_dia, limit_x) if boring_mode else max(pass_x - step_dia, limit_x)
            continue

        # Type II permits pockets/non-monotonic contours.  Follow the clipped
        # profile conservatively; the analyzer separately marks Type-II use as
        # controller-dependent/unverified unless explicitly configured.
        prev = _follow_type_ii_profile(motions, profile, seg_idx, entry_pt, pass_x, next_pass_x, boring_mode, feed)

        retreat_x = prev.x - retract_dia if boring_mode else prev.x + retract_dia
        retreat = Point2(retreat_x, prev.z + abs(retract_r))
        add_motion_with_meta(motions, 1, prev, retreat, None, feed if feed > 0 else None)
        tool = Point2(retreat.x, safe_z)
        add_motion(motions, 0, retreat, tool)
        if abs(pass_x - limit_x) <= 1e-9:
            break
        pass_x = min(pass_x + step_dia, limit_x) if boring_mode else max(pass_x - step_dia, limit_x)

    # Type I ends with one complete pass along the roughing profile.  The
    # incoming profile already includes the signed U/W finish allowances, so
    # this pass must not reuse the original finishing contour.
    _finish_roughing(motions, profile, tool, feed, type_ii, cycle_start, retract_r, boring_mode)

    return motions
