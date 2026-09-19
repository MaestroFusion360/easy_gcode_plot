"""G72 facing roughing-cycle expansion."""

from __future__ import annotations

from ..api.resources import SemanticError, checkpoint
from ..frontend.model import Motion, Point2, ProfileSegment
from ..frontend.program import radius_to_diameter
from .common import _append_profile_trace, add_motion, add_motion_with_meta, add_rapid_orthogonal, ensure_cycle_return
from .profile import _distinct_in_profile_order, _profile_intersections_at_z


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
