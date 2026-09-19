"""G74 face grooving / peck-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from ..frontend.program import radius_to_diameter
from .common import _linspace_steps, add_motion, append_turning_pecks, ensure_cycle_return


def _append_peck_z_turning(
    motions: list[Motion],
    start: Point2,
    target_z: float,
    retract_r: float,
    step_z: float,
    feed: float,
) -> Point2:
    """Turning-style Z peck: feed in Z, rapid out by R after every peck, no rapid-in back move."""
    return append_turning_pecks(motions, start, target_z, step_z, retract_r, feed, axis="z")


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
        if step_q <= 1e-9 < abs(tz - stock_z):
            return motions
        tool = Point2(stock_x, stock_z)
        tool = _append_peck_z_turning(motions, tool, tz, retract_r, step_q, feed)
        ensure_cycle_return(motions, Point2(stock_x, stock_z), first_axis="z")
        return motions

    if target_x is None:
        return motions
    direction = 1.0 if tx > stock_x else -1.0
    tx -= direction * radius_to_diameter(abs(bottom_allow_r))
    if step_p <= 1e-9 < abs(tx - stock_x):
        return motions
    if step_q <= 1e-9 < abs(tz - stock_z):
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
