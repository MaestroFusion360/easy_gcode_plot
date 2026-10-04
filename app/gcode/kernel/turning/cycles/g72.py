"""G72 facing roughing-cycle expansion."""

from __future__ import annotations

from ...api.resources import SemanticError, checkpoint
from ...frontend.model import Motion, Point2, ProfileSegment
from ...frontend.program import radius_to_diameter
from .common import _append_profile_trace, add_motion, add_motion_with_meta, add_rapid_orthogonal, ensure_cycle_return
from .profile import _distinct_in_profile_order, _profile_intersections_at_z


def _unsupported_type_ii_spans() -> list[Motion]:
    raise SemanticError(
        "UNSUPPORTED_G72_TYPE_II_SPANS",
        "G72 Type II profile produces multiple disjoint spans on one facing plane",
        "unsupported",
    )


def _facing_span(cand, stock_x, boring_mode, saw_closed_span, pass_z, limit_z, type_ii):
    if not type_ii:
        return stock_x, min(cand) if boring_mode else max(cand), stock_x, saw_closed_span
    if saw_closed_span and len(cand) == 1:
        if abs(pass_z - limit_z) <= 1e-9:
            return None
        raise SemanticError(
            "AMBIGUOUS_G72_TYPE_II_PROFILE",
            "G72 Type II closed span has a lone interior crossing",
            "unsupported",
        )
    if len(cand) == 1:
        return stock_x, cand[0], stock_x, saw_closed_span
    if len(cand) == 2:
        return cand[0], cand[1], cand[0], True
    _unsupported_type_ii_spans()


def _emit_facing_pass(
    motions, tool, cut_start_x, cut_end_x, return_x, pass_z, retract_z, retract_dia, feed, type_ii, crossings
):
    safe_pt = Point2(cut_start_x, pass_z + retract_z)
    cut_start = Point2(cut_start_x, pass_z)
    cut_end = Point2(cut_end_x, pass_z)
    if type_ii:
        add_rapid_orthogonal(motions, tool, safe_pt, first_axis="z")
    else:
        add_motion(motions, 0, tool, safe_pt)
    add_motion(motions, 0, safe_pt, cut_start)
    add_motion_with_meta(motions, 1, cut_start, cut_end, None, feed if feed > 0 else None)
    tool = Point2(return_x, pass_z + retract_z)
    if type_ii and crossings == 2:
        axial_retract = Point2(cut_end.x, pass_z + retract_z)
        add_motion(motions, 0, cut_end, axial_retract)
        add_motion(motions, 0, axial_retract, tool)
    else:
        cut_direction = 1.0 if cut_end.x > cut_start.x else -1.0
        retreat_x = cut_end.x - (cut_direction * retract_dia)
        retract_pt = Point2(retreat_x, pass_z + retract_z)
        add_motion(motions, 0, cut_end, retract_pt)
        add_motion(motions, 0, retract_pt, tool)
    return tool


def _facing_candidates(profile, pass_z, pass_dir, z_min, z_max, type_ii):
    """Find contour crossings or the Type I stock-side fallback."""
    candidates = _distinct_in_profile_order(_profile_intersections_at_z(profile, pass_z))
    if candidates:
        return candidates
    stock_side = (pass_dir < 0.0 and pass_z > z_max + 1e-8) or (pass_dir > 0.0 and pass_z < z_min - 1e-8)
    if not type_ii and stock_side:
        # Before a facing plane reaches the P-Q contour, Q's programmed X
        # remains the deterministic inner limit for a Type I pass.
        return [profile[-1].end.x]
    return []


def _append_facing_contour(motions, profile, stock_x, tool, feed, type_ii):
    """Add the final rough-profile pass."""
    contour_start = profile[0].start
    contour_rapid = Point2(stock_x, contour_start.z)
    if type_ii:
        add_rapid_orthogonal(motions, tool, contour_rapid, first_axis="z")
    else:
        add_motion(motions, 0, tool, contour_rapid)
    add_motion(motions, 0, contour_rapid, contour_start)
    _append_profile_trace(motions, profile, feed)


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
        raise SemanticError("INVALID_G72_PROFILE", "G72 profile is empty", "invalid_input")
    motions: list[Motion] = []
    z_min = min(min(s.start.z, s.end.z) for s in profile)
    z_max = max(max(s.start.z, s.end.z) for s in profile)
    if abs(depth_w) <= 1e-9:
        raise SemanticError("INVALID_G72_DEPTH", "G72 pass depth must be nonzero", "invalid_input")

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
        cand = _facing_candidates(profile, pass_z, pass_dir, z_min, z_max, type_ii)
        if not cand:
            if abs(pass_z - limit_z) <= 1e-9:
                break
            next_z = pass_z + pass_dir * step_z
            pass_z = max(next_z, limit_z) if pass_dir < 0.0 else min(next_z, limit_z)
            continue
        span = _facing_span(cand, stock_x, boring_mode, saw_closed_span, pass_z, limit_z, type_ii)
        if span is None:
            break
        cut_start_x, cut_end_x, return_x, saw_closed_span = span
        tool = _emit_facing_pass(
            motions,
            tool,
            cut_start_x,
            cut_end_x,
            return_x,
            pass_z,
            retract_z_signed,
            retract_dia,
            feed,
            type_ii,
            len(cand),
        )
        if abs(pass_z - limit_z) <= 1e-9:
            break
        next_z = pass_z + pass_dir * step_z
        pass_z = max(next_z, limit_z) if pass_dir < 0.0 else min(next_z, limit_z)

    if type_ii and not motions:
        raise SemanticError(
            "AMBIGUOUS_G72_TYPE_II_PROFILE",
            "G72 Type II profile has no cuttable facing span",
            "unsupported",
        )

    # Add one contour-following pass on the rough profile (with U/W allowances applied),
    # matching the preview style expected from longitudinal roughing behavior.
    _append_facing_contour(motions, profile, stock_x, tool, feed, type_ii)

    end = motions[-1].end
    retreat = Point2(
        end.x + (-retract_dia if boring_mode else retract_dia),
        end.z + retract_z_signed,
    )
    add_motion(motions, 0, end, retreat)
    ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="z")
    return motions
