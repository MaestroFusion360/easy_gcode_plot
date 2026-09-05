"""FANUC turning, grooving, drilling, tapping, and threading cycle expansion."""

# ruff: noqa: F403,F405

from __future__ import annotations

# The cycle builders form one cohesive donor subsystem; star imports preserve
# its tested internal surface until the next behavior-preserving cleanup pass.
# pylint: disable=wildcard-import,unused-wildcard-import,unnecessary-list-index-lookup,chained-comparison
import math

from .model import *  # noqa: F403
from .profile import *  # noqa: F403
from .program import radius_to_diameter
from .resources import SemanticError, checkpoint, require_progress


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


def add_g90_longitudinal_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    feed: float,
    first_block_with_z: bool = False,
) -> None:
    start = Point2(start_x, start_z)
    if first_block_with_z:
        entry = Point2(target_x, target_z)
        add_motion(motions, 0, start, entry)
        add_motion(motions, 0, entry, Point2(start_x, target_z))
        add_motion(motions, 0, Point2(start_x, target_z), start)
        return
    x_in = Point2(target_x, start_z)
    z_cut = Point2(target_x, target_z)
    add_motion(motions, 0, start, x_in)
    add_motion_with_meta(motions, 1, x_in, z_cut, None, feed if feed > 0 else None)
    add_motion(motions, 0, z_cut, Point2(start_x, target_z))
    add_motion(motions, 0, Point2(start_x, target_z), start)


def add_g94_facing_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    feed: float,
    first_block_with_z: bool = False,
) -> None:
    start = Point2(start_x, start_z)
    if first_block_with_z:
        entry = Point2(target_x, target_z)
        add_motion(motions, 0, start, entry)
        add_motion(motions, 0, entry, Point2(target_x, start_z))
        add_motion(motions, 0, Point2(target_x, start_z), start)
        return
    z_in = Point2(start_x, target_z)
    cut_end = Point2(target_x, target_z)
    add_motion(motions, 0, start, z_in)
    add_motion_with_meta(motions, 1, z_in, cut_end, None, feed if feed > 0 else None)
    add_motion(motions, 0, cut_end, Point2(target_x, start_z))
    add_motion(motions, 0, Point2(target_x, start_z), start)


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
) -> list[Motion]:
    motions: list[Motion] = []
    if not profile:
        return motions
    cycle_start = Point2(stock_x, stock_z)
    step_dia = abs(depth_u) * 2.0
    if step_dia <= 1e-9:
        return motions
    retract_dia = abs(retract_r) * 2.0
    min_x = min(min(s.start.x, s.end.x) for s in profile)
    max_x = max(max(s.start.x, s.end.x) for s in profile)
    # Keep cycle rapid plane at cycle start Z to match common expanded output.
    safe_z = stock_z

    limit_x = max_x if boring_mode else min_x
    pass_x = min(stock_x + step_dia, limit_x) if boring_mode else max(stock_x - step_dia, limit_x)
    tool = Point2(stock_x, stock_z)

    guard = 0
    while (pass_x <= max_x + 1e-4) if boring_mode else (pass_x >= min_x - 1e-4):
        checkpoint("cycle_iterations")
        guard += 1
        checkpoint("cycle_iterations")
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
            # rough pass is parallel to Z and terminates at the P-Q profile.
            # The R retract is a short diagonal away from the material, followed
            # by a rapid return on the cycle-start Z plane.
            retreat_x = entry_pt.x - retract_dia if boring_mode else entry_pt.x + retract_dia
            retreat_z = entry_pt.z + (abs(retract_r) if stock_z >= entry_pt.z else -abs(retract_r))
            retreat = Point2(retreat_x, retreat_z)
            add_motion_with_meta(motions, 1, entry_pt, retreat, None, feed if feed > 0 else None)
            tool = Point2(retreat.x, safe_z)
            add_motion(motions, 0, retreat, tool)
            pass_x = pass_x + step_dia if boring_mode else pass_x - step_dia
            continue

        # Type II permits pockets/non-monotonic contours.  Follow the clipped
        # profile conservatively; the analyzer separately marks Type-II use as
        # controller-dependent/unverified unless explicitly configured.
        prev = entry_pt
        pass_done = False
        for i in range(seg_idx, len(profile)):
            seg = profile[i]
            sraw = entry_pt if i == seg_idx else seg.start
            eraw = seg.end
            raw = segment_points(seg, sraw, eraw)
            clipped = clip_polyline_min_x(raw, pass_x) if boring_mode else clip_polyline_max_x(raw, pass_x)
            if len(clipped) < 2:
                continue
            if abs(prev.x - clipped[0].x) > 1e-5 or abs(prev.z - clipped[0].z) > 1e-5:
                add_feed_orthogonal(motions, prev, clipped[0], feed)
                prev = clipped[0]
            for idx_pair, (a, b) in enumerate(zip(clipped, clipped[1:])):
                crosses_next = (a.x - next_pass_x) * (b.x - next_pass_x) <= 0.0 and abs(b.x - a.x) > 1e-8
                if crosses_next:
                    t = (next_pass_x - a.x) / (b.x - a.x)
                    t = max(0.0, min(1.0, t))
                    hit = Point2(next_pass_x, a.z + (b.z - a.z) * t)
                    add_motion_with_meta(motions, 1, prev, hit, None, feed if feed > 0 else None)
                    prev = hit
                    pass_done = True
                    break
                # Follow the sampled P-Q contour directly. Splitting every
                # chord into X/Z legs turns G02/G03 profiles into a staircase.
                _ = idx_pair, sraw, eraw, seg
                add_motion_with_meta(motions, 1, prev, b, None, feed if feed > 0 else None)
                prev = b
            if pass_done:
                break

        retreat_x = prev.x - retract_dia if boring_mode else prev.x + retract_dia
        retreat = Point2(retreat_x, prev.z + abs(retract_r))
        add_motion_with_meta(motions, 1, prev, retreat, None, feed if feed > 0 else None)
        tool = Point2(retreat.x, safe_z)
        add_motion(motions, 0, retreat, tool)
        if abs(pass_x - limit_x) <= 1e-9:
            break
        pass_x = min(pass_x + step_dia, limit_x) if boring_mode else max(pass_x - step_dia, limit_x)

    # Return to the cycle start point once, after all roughing passes are completed.
    ensure_cycle_return(motions, cycle_start, first_axis="x")

    return motions


def _outward_normal_radius(prev: Point2, curr: Point2, nxt: Point2, prefer_positive_x: bool) -> Point2:
    px = prev.x * 0.5
    pz = prev.z
    nx = nxt.x * 0.5
    nz = nxt.z
    dx = nx - px
    dz = nz - pz
    ln = math.hypot(dx, dz)
    if ln <= 1e-9:
        return Point2(1.0, 0.0)
    tx = dx / ln
    tz = dz / ln
    c1 = Point2(tz, -tx)
    c2 = Point2(-tz, tx)
    if prefer_positive_x:
        return c1 if c1.x >= c2.x else c2
    return c1 if c1.x <= c2.x else c2


def build_offset_profile(
    profile: list[ProfileSegment],
    finish_u: float,
    finish_w: float,
    prefer_positive_x: bool,
) -> list[ProfileSegment]:
    if not profile:
        return []
    # U and W are independent finish allowances in the machine X and Z
    # directions.  Project that allowance vector onto the local outward normal
    # instead of collapsing both values to max(U/2, W), which over-offsets
    # tapers/arcs and can create large false Z displacements.
    radial_allow = finish_u * 0.5
    axial_allow = finish_w
    if abs(radial_allow) <= 1e-9 and abs(axial_allow) <= 1e-9:
        return profile

    dense: list[Point2] = []
    for seg in profile:
        pts = segment_points(seg, seg.start, seg.end)
        if dense and pts:
            pts = pts[1:]
        dense.extend(pts)

    if len(dense) < 2:
        return profile

    shifted: list[Point2] = []
    for i, curr in enumerate(dense):
        prev = dense[i - 1] if i > 0 else dense[i]
        nxt = dense[i + 1] if i + 1 < len(dense) else dense[i]
        n = _outward_normal_radius(prev, curr, nxt, prefer_positive_x)
        cxr = curr.x * 0.5
        offset_dist = n.x * radial_allow + n.z * axial_allow
        sxr = cxr + (n.x * offset_dist)
        sz = curr.z + (n.z * offset_dist)
        shifted.append(Point2(sxr * 2.0, sz))

    out: list[ProfileSegment] = []
    for a, b in zip(shifted, shifted[1:]):
        if abs(a.x - b.x) <= 1e-6 and abs(a.z - b.z) <= 1e-6:
            continue
        out.append(
            ProfileSegment(
                block=-1,
                move=1,
                start=a,
                end=b,
                has_radius=False,
                radius=0.0,
                has_center=False,
                center=Point2(0.0, 0.0),
            )
        )
    return out if out else profile


def is_boring_cycle(profile: list[ProfileSegment], finish_u: float, stock_x: float) -> bool:
    if finish_u < -1e-9:
        return True
    if not profile:
        return False

    min_x = min(min(seg.start.x, seg.end.x) for seg in profile)
    max_x = max(max(seg.start.x, seg.end.x) for seg in profile)
    stock_near_low_side = abs(stock_x - min_x) < abs(stock_x - max_x)

    direction_up = False
    prev = profile[0].start
    for seg in profile:
        curr = seg.end
        dx = curr.x - prev.x
        if abs(dx) > 1e-5:
            direction_up = dx > 0.0
            break
        prev = curr
    else:
        total_dx = sum(seg.end.x - seg.start.x for seg in profile)
        direction_up = total_dx > 1e-5

    return stock_near_low_side and direction_up


def build_finish_contour(profile: list[ProfileSegment]) -> list[Motion]:
    motions: list[Motion] = []
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


def _profile_intersections_at_z(profile: list[ProfileSegment], pass_z: float) -> list[float]:
    xs: list[float] = []
    for seg in profile:
        raw = segment_points(seg, seg.start, seg.end)
        for a, b in zip(raw, raw[1:]):
            za = a.z - pass_z
            zb = b.z - pass_z
            if abs(za) <= 1e-8 and abs(zb) <= 1e-8:
                xs.extend([a.x, b.x])
                continue
            if za * zb > 0.0:
                continue
            dz = b.z - a.z
            if abs(dz) <= 1e-9:
                xs.append(a.x)
                continue
            t = (pass_z - a.z) / dz
            if t < -1e-6 or t > 1.000001:
                continue
            t = max(0.0, min(1.0, t))
            xs.append(a.x + (b.x - a.x) * t)
    return xs


def _distinct_in_profile_order(values: list[float], tolerance: float = 1e-3) -> list[float]:
    result: list[float] = []
    for value in values:
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def build_g72_facing(
    profile: list[ProfileSegment],
    stock_x: float,
    stock_z: float,
    depth_w: float,
    retract_r: float,
    finish_u: float,
    finish_w: float,
    feed: float,
    cycle_return_z: float | None = None,
    type_ii: bool = False,
) -> list[Motion]:
    del (
        finish_u,
        finish_w,
        cycle_return_z,
    )  # allowances are already applied into the incoming rough profile.
    if not profile:
        return []
    motions: list[Motion] = []
    z_min = min(min(s.start.z, s.end.z) for s in profile)
    z_max = max(max(s.start.z, s.end.z) for s in profile)
    if abs(depth_w) <= 1e-9:
        return motions

    step_z = abs(depth_w)
    pass_dir = -1.0 if stock_z >= 0.5 * (z_min + z_max) else 1.0
    limit_z = z_min if pass_dir < 0.0 else z_max
    pass_z = stock_z + (pass_dir * step_z)
    pass_z = max(pass_z, limit_z) if pass_dir < 0.0 else min(pass_z, limit_z)
    retract_z_signed = -pass_dir * abs(retract_r)

    x_min = min(min(s.start.x, s.end.x) for s in profile)
    x_max = max(max(s.start.x, s.end.x) for s in profile)
    boring_mode = abs(stock_x - x_min) < abs(stock_x - x_max)
    retract_dia = radius_to_diameter(abs(retract_r))
    tool = Point2(stock_x, stock_z)
    saw_closed_span = False

    guard = 0
    while (pass_z >= limit_z - 1e-6) if pass_dir < 0.0 else (pass_z <= limit_z + 1e-6):
        checkpoint("cycle_iterations")
        guard += 1
        checkpoint("cycle_iterations")
        if guard > 10000:
            raise SemanticError("RESOURCE_LIMIT", "Cycle exceeds 10000 passes", "resource_limit")
        cand = _distinct_in_profile_order(_profile_intersections_at_z(profile, pass_z))
        if not cand:
            stock_side_of_profile = (pass_dir < 0.0 and pass_z > z_max + 1e-8) or (
                pass_dir > 0.0 and pass_z < z_min - 1e-8
            )
            if not type_ii and stock_side_of_profile:
                # G72 Type I faces every W plane between the saved cycle start
                # and the P-Q contour. Before a plane reaches the contour's Z
                # range, Q's programmed X is the deterministic inner limit;
                # absence of a geometric intersection does not cancel a pass.
                cand = [profile[-1].end.x]
            else:
                if abs(pass_z - limit_z) <= 1e-9:
                    break
                next_z = pass_z + pass_dir * step_z
                pass_z = max(next_z, limit_z) if pass_dir < 0.0 else min(next_z, limit_z)
                continue
        if not type_ii:
            cut_start_x = stock_x
            cut_end_x = min(cand) if boring_mode else max(cand)
            return_x = stock_x
        elif saw_closed_span and len(cand) == 1:
            # A closed Type-II span degenerates to one crossing only at a
            # tangent profile limit; there is no finite-width cut to emit.
            # A lone crossing inside the scan range is not a valid closed span.
            if abs(pass_z - limit_z) <= 1e-9:
                break
            return []
        elif len(cand) == 1:
            cut_start_x = stock_x
            cut_end_x = cand[0]
            return_x = stock_x
        elif len(cand) == 2:
            # Profile order is authoritative: the first boundary is reached
            # before the second while traversing P through Q.  This preserves
            # programmed OD/ID direction without inferring it from coordinates.
            # The two crossings also define a closed Type-II cutting span, so
            # its local return plane is the first profile boundary.  Returning
            # every pass to stock_x would leave the programmed groove.
            cut_start_x, cut_end_x = cand
            if type_ii:
                return_x = cut_start_x
                saw_closed_span = True
            else:
                return_x = stock_x
        else:
            # Multiple disjoint spans require controller-specific Type II
            # material-side semantics.  Do not invent a traversal order.
            return []
        safe_pt = Point2(cut_start_x, pass_z + retract_z_signed)
        cut_start = Point2(cut_start_x, pass_z)
        cut_end = Point2(cut_end_x, pass_z)
        if type_ii:
            add_rapid_orthogonal(motions, tool, safe_pt, first_axis="z")
        else:
            add_motion(motions, 0, tool, safe_pt)
        add_motion(motions, 0, safe_pt, cut_start)
        add_motion_with_meta(motions, 1, cut_start, cut_end, None, feed if feed > 0 else None)
        tool = Point2(return_x, pass_z + retract_z_signed)
        if type_ii and len(cand) == 2:
            # G72 Type II must leave the cut axially before traversing back
            # across a pocket. A diagonal X/Z retract can cross the profile.
            axial_retract = Point2(cut_end.x, pass_z + retract_z_signed)
            add_motion(motions, 0, cut_end, axial_retract)
            add_motion(motions, 0, axial_retract, tool)
        else:
            cut_direction = 1.0 if cut_end.x > cut_start.x else -1.0
            retreat_x = cut_end.x - (cut_direction * retract_dia)
            retract_pt = Point2(retreat_x, pass_z + retract_z_signed)
            add_motion(motions, 0, cut_end, retract_pt)
            add_motion(motions, 0, retract_pt, tool)
        if abs(pass_z - limit_z) <= 1e-9:
            break
        next_z = pass_z + pass_dir * step_z
        pass_z = max(next_z, limit_z) if pass_dir < 0.0 else min(next_z, limit_z)

    # Add one contour-following pass on the rough profile (with U/W allowances applied),
    # matching the preview style expected from longitudinal roughing behavior.
    if profile:
        contour_start = profile[0].start
        contour_rapid = Point2(stock_x, contour_start.z)
        if type_ii:
            add_rapid_orthogonal(motions, tool, contour_rapid, first_axis="z")
        else:
            add_motion(motions, 0, tool, contour_rapid)
        add_motion(motions, 0, contour_rapid, contour_start)
        # Keep contour pass geometry faithful to the programmed profile.
        _append_profile_trace(motions, profile, feed)
        tool = motions[-1].end

    ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="z")
    return motions


def _shift_profile(profile: list[ProfileSegment], dx: float, dz: float) -> list[ProfileSegment]:
    out: list[ProfileSegment] = []
    for seg in profile:
        out.append(
            ProfileSegment(
                block=seg.block,
                move=seg.move,
                start=Point2(seg.start.x + dx, seg.start.z + dz),
                end=Point2(seg.end.x + dx, seg.end.z + dz),
                has_radius=seg.has_radius,
                radius=seg.radius,
                has_center=seg.has_center,
                center=Point2(seg.center.x + dx, seg.center.z + dz),
            )
        )
    return out


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
            )


def build_g73_pattern(
    rough_profile: list[ProfileSegment],
    stock_x: float,
    stock_z: float,
    total_u_x: float,
    total_w_z: float,
    passes: int,
    feed: float,
) -> list[Motion]:
    motions: list[Motion] = []
    if not rough_profile:
        return motions
    passes = max(1, passes)

    tool = Point2(stock_x, stock_z)
    for i in range(passes, 0, -1):
        checkpoint("cycle_iterations")
        k = i / passes
        # U/W carry the programmed pattern displacement.  Preserve their signs;
        # inferring direction from the average contour position makes identical
        # profiles expand differently solely because of the approach point.
        dx = total_u_x * k
        dz = total_w_z * k
        pass_profile = _shift_profile(rough_profile, dx, dz)
        if not pass_profile:
            continue
        add_motion(motions, 0, tool, pass_profile[0].start)
        _append_profile_trace(motions, pass_profile, feed)
        tool = motions[-1].end
    ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="x")
    return motions


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


def _append_peck_x(
    motions: list[Motion],
    start: Point2,
    target_x: float,
    retract_r: float,
    step_x_radius: float,
    feed: float,
) -> Point2:
    step_dia = max(radius_to_diameter(abs(step_x_radius)), 1e-9)
    retract_dia = radius_to_diameter(max(abs(retract_r), 0.0))
    direction = 1.0 if target_x > start.x else -1.0
    curr = start
    while (target_x - curr.x) * direction > 1e-7:
        checkpoint("cycle_iterations")
        nx = curr.x + (direction * step_dia)
        require_progress(curr.x, nx)
        if (target_x - nx) * direction < 0.0:
            nx = target_x
        hit = Point2(nx, curr.z)
        add_motion_with_meta(motions, 1, curr, hit, None, feed if feed > 0 else None)
        curr = hit
        if (target_x - curr.x) * direction > 1e-7:
            retreat = Point2(curr.x - (direction * retract_dia), curr.z)
            add_motion(motions, 0, curr, retreat)
            add_motion(motions, 0, retreat, curr)
    return curr


def _append_peck_z(
    motions: list[Motion],
    start: Point2,
    target_z: float,
    retract_r: float,
    step_z: float,
    feed: float,
) -> Point2:
    step = max(abs(step_z), 1e-9)
    retract = max(abs(retract_r), 0.0)
    direction = 1.0 if target_z > start.z else -1.0
    curr = start
    while (target_z - curr.z) * direction > 1e-7:
        checkpoint("cycle_iterations")
        nz = curr.z + (direction * step)
        require_progress(curr.z, nz)
        if (target_z - nz) * direction < 0.0:
            nz = target_z
        hit = Point2(curr.x, nz)
        add_motion_with_meta(motions, 1, curr, hit, None, feed if feed > 0 else None)
        curr = hit
        if (target_z - curr.z) * direction > 1e-7:
            retreat = Point2(curr.x, curr.z - (direction * retract))
            add_motion(motions, 0, curr, retreat)
            add_motion(motions, 0, retreat, curr)
    return curr


def _append_peck_x_turning(
    motions: list[Motion],
    start: Point2,
    target_x: float,
    retract_r: float,
    step_x_radius: float,
    feed: float,
) -> Point2:
    """Turning-style X peck: feed in X, rapid out by R after every peck, no rapid-in back move."""
    step_dia = max(radius_to_diameter(abs(step_x_radius)), 1e-9)
    retract_dia = radius_to_diameter(max(abs(retract_r), 0.0))
    direction = 1.0 if target_x > start.x else -1.0
    curr = start
    last_cut_x = start.x
    while (target_x - last_cut_x) * direction > 1e-7:
        checkpoint("cycle_iterations")
        nx = last_cut_x + (direction * step_dia)
        if (target_x - nx) * direction < 0.0:
            nx = target_x
        hit = Point2(nx, curr.z)
        add_motion_with_meta(motions, 1, curr, hit, None, feed if feed > 0 else None)
        last_cut_x = nx
        reached_target = abs(hit.x - target_x) <= 1e-7
        retreat = Point2(hit.x - (direction * retract_dia), hit.z)
        add_motion(motions, 0, hit, retreat)
        curr = retreat
        if reached_target:
            break
    return curr


def _append_peck_z_turning(
    motions: list[Motion],
    start: Point2,
    target_z: float,
    retract_r: float,
    step_z: float,
    feed: float,
) -> Point2:
    """Turning-style Z peck: feed in Z, rapid out by R after every peck, no rapid-in back move."""
    step = max(abs(step_z), 1e-9)
    retract = max(abs(retract_r), 0.0)
    direction = 1.0 if target_z > start.z else -1.0
    curr = start
    last_cut_z = start.z
    while (target_z - last_cut_z) * direction > 1e-7:
        checkpoint("cycle_iterations")
        nz = last_cut_z + (direction * step)
        if (target_z - nz) * direction < 0.0:
            nz = target_z
        hit = Point2(curr.x, nz)
        add_motion_with_meta(motions, 1, curr, hit, None, feed if feed > 0 else None)
        last_cut_z = nz
        reached_target = abs(hit.z - target_z) <= 1e-7
        retreat = Point2(hit.x, hit.z - (direction * retract))
        add_motion(motions, 0, hit, retreat)
        curr = retreat
        if reached_target:
            break
    return curr


def build_g74_cycle(
    stock_x: float,
    stock_z: float,
    target_x: float | None,
    target_z: float | None,
    retract_r: float,
    step_p: float,
    step_q: float,
    bottom_allow_r: float,
    feed: float,
) -> list[Motion]:
    motions: list[Motion] = []
    tx = target_x if target_x is not None else stock_x
    tz = target_z if target_z is not None else stock_z
    # G74 drilling-style usage (no X target): peck only along Z at the current X.
    if target_x is None and target_z is not None:
        if step_q <= 1e-9 and abs(tz - stock_z) > 1e-9:
            return motions
        tool = Point2(stock_x, stock_z)
        tool = _append_peck_z_turning(motions, tool, tz, retract_r, step_q, feed)
        ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="z")
        return motions

    if target_x is None:
        return motions
    direction = 1.0 if tx > stock_x else -1.0
    tx -= direction * radius_to_diameter(abs(bottom_allow_r))
    if step_p <= 1e-9 and abs(tx - stock_x) > 1e-9:
        return motions
    if step_q <= 1e-9 and abs(tz - stock_z) > 1e-9:
        return motions
    x_steps = _linspace_steps(stock_x, tx, abs(radius_to_diameter(step_p)))
    tool = Point2(stock_x, stock_z)
    for x_pass in x_steps:
        pass_start = Point2(x_pass, stock_z)
        if abs(tool.x - pass_start.x) > 1e-9 or abs(tool.z - pass_start.z) > 1e-9:
            add_motion(motions, 0, tool, pass_start)
        tool = _append_peck_z_turning(motions, pass_start, tz, retract_r, step_q, feed)
        add_motion(motions, 0, tool, Point2(x_pass, stock_z))
        tool = Point2(x_pass, stock_z)
    ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="z")
    return motions


def build_g75_cycle(
    stock_x: float,
    stock_z: float,
    target_x: float,
    target_z: float | None,
    retract_r: float,
    step_p: float,
    step_q: float,
    bottom_allow_r: float,
    feed: float,
) -> list[Motion]:
    motions: list[Motion] = []
    direction = 1.0 if target_x > stock_x else -1.0
    target_x_eff = target_x - direction * radius_to_diameter(abs(bottom_allow_r))
    z_work = target_z if target_z is not None else stock_z
    if step_p <= 1e-9 and abs(target_x_eff - stock_x) > 1e-9:
        return motions
    # Q repeats the groove along Z.  Without Q, Z/W selects one groove
    # location rather than defining an invalid zero-step repetition.
    z_steps = _linspace_steps(stock_z, z_work, abs(step_q)) if step_q > 1e-9 else [z_work]
    tool = Point2(stock_x, stock_z)
    for pass_z in z_steps:
        pass_start = Point2(stock_x, pass_z)
        if tool != pass_start:
            add_motion(motions, 0, tool, pass_start)
        tool = _append_peck_x_turning(motions, pass_start, target_x_eff, retract_r, step_p, feed)
        add_motion(motions, 0, tool, pass_start)
        tool = pass_start
    ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="x")
    return motions


def build_g83_cycle(
    stock_x: float,
    stock_z: float,
    target_x: float,
    target_z: float,
    retract_r: float,
    step_q: float,
    dwell_p: float,
    feed: float,
) -> list[Motion]:
    del dwell_p  # Dwell has no geometry contribution in backplot.
    motions: list[Motion] = []
    tool = Point2(stock_x, stock_z)
    if abs(target_x - stock_x) > 1e-9:
        add_motion(motions, 0, tool, Point2(target_x, stock_z))
        tool = Point2(target_x, stock_z)
    tool = _append_peck_z_turning(motions, tool, target_z, retract_r, max(abs(step_q), 0.05), feed)
    add_motion(motions, 0, tool, Point2(target_x, stock_z))
    add_motion(motions, 0, Point2(target_x, stock_z), Point2(stock_x, stock_z))
    return motions


def build_g84_cycle(
    stock_x: float,
    stock_z: float,
    target_x: float,
    target_z: float,
    retract_r: float,
    step_q: float,
    dwell_p: float,
    feed: float,
) -> list[Motion]:
    # Geometry stays equivalent to G83 in this backplot model.
    return build_g83_cycle(
        stock_x,
        stock_z,
        target_x,
        target_z,
        retract_r,
        step_q,
        dwell_p,
        feed,
    )


def add_g92_thread_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    lead: float,
) -> None:
    start = Point2(start_x, start_z)
    pass_start = Point2(target_x, start_z)
    pass_end = Point2(target_x, target_z)
    add_motion(motions, 0, start, pass_start)
    add_motion_with_meta(motions, 1, pass_start, pass_end, None, lead if lead > 0 else None)
    add_motion(motions, 0, pass_end, Point2(start_x, target_z))
    add_motion(motions, 0, Point2(start_x, target_z), start)


def _parse_g76_packed_p(packed_p: int) -> tuple[int, int, int]:
    """Decode FANUC two-line G76 P(m)(r)(a): finish passes, chamfer, angle."""
    value = abs(int(packed_p))
    finish_passes = max(0, min(99, value // 10000))
    chamfer_tenths = max(0, min(99, (value // 100) % 100))
    tool_angle = max(0, min(99, value % 100))
    return finish_passes, chamfer_tenths, tool_angle


def _parse_g76_finish_passes(packed_p: int) -> int:
    return _parse_g76_packed_p(packed_p)[0]


def _g76_constant_area_depths(
    total_rad: float,
    first_rad: float,
    min_increment_rad: float,
    finish_allow_rad: float,
    finish_passes: int,
) -> list[float]:
    """Return monotonically increasing radial depths for a FANUC-style G76.

    FANUC's multi-pass threading cycle uses a decreasing depth of cut / roughly
    constant chip-area progression.  The commonly documented relationship is
    based on ``Q(first) * sqrt(pass_no)`` with the first-block Q acting as the
    minimum radial increment.  The final R allowance is removed at the finish
    depth and P's leading digits request spring/finish passes.
    """
    total = max(0.0, float(total_rad))
    if total <= 1e-12:
        return []
    first = max(1e-9, min(abs(float(first_rad)), total))
    min_inc = max(0.0, abs(float(min_increment_rad)))
    finish_allow = max(0.0, min(abs(float(finish_allow_rad)), total))
    rough_target = max(0.0, total - finish_allow)

    depths: list[float] = []
    if rough_target > 1e-12:
        depth = min(first, rough_target)
        depths.append(depth)
        pass_no = 2
        while depth < rough_target - 1e-9:
            checkpoint("cycle_iterations")
            checkpoint("cycle_iterations")
            if pass_no >= 10000:
                raise SemanticError("RESOURCE_LIMIT", "G76 exceeds 10000 passes", "resource_limit")
            nominal = first * math.sqrt(float(pass_no))
            candidate = max(nominal, depth + min_inc) if min_inc > 0 else nominal
            candidate = min(rough_target, candidate)
            require_progress(depth, candidate)
            depths.append(candidate)
            depth = candidate
            pass_no += 1

    # The commanded X is the final thread diameter. FANUC P(m) is the total
    # repetitive count of the final finishing cycle; when m=0 the control still
    # performs one final cycle.  Do not add an extra uncommanded spring pass.
    if not depths or depths[-1] < total - 1e-9:
        depths.append(total)
    requested_final_count = max(1, int(finish_passes))
    existing_final_count = 0
    for value in reversed(depths):
        if abs(value - total) <= 1e-9:
            existing_final_count += 1
        else:
            break
    if existing_final_count < requested_final_count:
        depths.extend([total] * (requested_final_count - existing_final_count))
    return depths


def build_g76_threading(
    stock_x: float,
    stock_z: float,
    target_x: float,
    target_z: float,
    packed_p: int,
    q_min_microns: float,
    r_finish_microns: float,
    p_height_microns: float,
    q_first_microns: float,
    lead: float,
    taper_r: float = 0.0,
) -> list[Motion]:
    """Expand a FANUC two-line G76 into XZ primitives.

    Despite the legacy parameter names, all Q/P/R depth arguments received by
    this function are millimetres in radius.  Conversion from FANUC integer
    least-input increments is performed by the runtime before this call.
    ``target_x`` is the authoritative final thread diameter from the second G76
    block; P controls pass-depth distribution and is expected to agree with it.
    """
    motions: list[Motion] = []
    total_rad = abs(float(p_height_microns))
    first_rad = abs(float(q_first_microns))
    q_min_rad = abs(float(q_min_microns))
    finish_rad = abs(float(r_finish_microns))
    if total_rad <= 1e-12 or first_rad <= 1e-12:
        return motions

    finish_passes, chamfer_tenths, _tool_angle = _parse_g76_packed_p(packed_p)
    pass_depths = _g76_constant_area_depths(
        total_rad,
        first_rad,
        q_min_rad,
        finish_rad,
        finish_passes,
    )
    if not pass_depths:
        return motions

    direction_x = 1.0 if target_x >= stock_x else -1.0
    direction_z = 1.0 if target_z >= stock_z else -1.0
    feed = lead if lead > 0 else None

    # P is the radial thread height; therefore X plus P defines the crest/root
    # geometry independently of the clearance X from which G76 was called.
    # Example: X12.916 P542 implies an external crest diameter of 14.000 mm even
    # when the tool starts at X14.6 for clearance.
    crest_end_x = target_x - direction_x * radius_to_diameter(total_rad)
    taper_start_dia = 2.0 * float(taper_r)
    crest_start_x = crest_end_x + taper_start_dia
    chamfer_len = max(0.0, (chamfer_tenths / 10.0) * abs(float(lead)))
    thread_len = abs(target_z - stock_z)
    chamfer_len = min(chamfer_len, thread_len)

    def q(v: float) -> float:
        return round(v, 6)

    def point(x: float, z: float) -> Point2:
        return Point2(q(x), q(z))

    tool = Point2(stock_x, stock_z)
    for index, depth_rad in enumerate(pass_depths):
        actual_rad = min(total_rad, max(0.0, depth_rad))
        x_end = crest_end_x + direction_x * radius_to_diameter(actual_rad)
        x_start = crest_start_x + direction_x * radius_to_diameter(actual_rad)
        if depth_rad >= total_rad - 1e-9:
            x_end = target_x
            x_start = target_x + taper_start_dia
        pass_start = point(x_start, stock_z)
        pass_end = point(x_end, target_z)
        retract_end = point(stock_x, target_z)

        add_motion(motions, 0, tool, pass_start)
        if chamfer_len > 1e-12 and thread_len > chamfer_len + 1e-12:
            z_chamfer = target_z - direction_z * chamfer_len
            t = (z_chamfer - stock_z) / (target_z - stock_z)
            x_chamfer = x_start + (x_end - x_start) * t
            chamfer_start = point(x_chamfer, z_chamfer)
            add_motion_with_meta(motions, 1, pass_start, chamfer_start, None, feed)
            add_motion_with_meta(motions, 1, chamfer_start, pass_end, None, feed)
        else:
            add_motion_with_meta(motions, 1, pass_start, pass_end, None, feed)
        add_motion(motions, 0, pass_end, retract_end)

        if index < len(pass_depths) - 1:
            return_start = point(stock_x, stock_z)
            add_motion(motions, 0, retract_end, return_start)
            tool = return_start
        else:
            tool = retract_end

    return motions
