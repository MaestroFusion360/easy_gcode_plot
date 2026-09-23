"""G73 pattern-repeat roughing-cycle expansion."""

from __future__ import annotations

from ...api.resources import checkpoint
from ...frontend.model import Motion, Point2, ProfileSegment
from .common import _append_profile_trace, add_motion, ensure_cycle_return
from .profile import _shift_profile


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
