"""G75 radial grooving / peck-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from ..frontend.program import radius_to_diameter
from .common import _linspace_steps, add_motion, append_turning_pecks, ensure_cycle_return


def _append_peck_x_turning(
    motions: list[Motion],
    start: Point2,
    target_x: float,
    retract_r: float,
    step_x_radius: float,
    feed: float,
) -> Point2:
    """Turning-style X peck: feed in X, rapid out by R after every peck, no rapid-in back move."""
    return append_turning_pecks(
        motions,
        start,
        target_x,
        radius_to_diameter(abs(step_x_radius)),
        radius_to_diameter(retract_r),
        feed,
        axis="x",
    )


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
    if step_p <= 1e-9 < abs(target_x_eff - stock_x):
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
