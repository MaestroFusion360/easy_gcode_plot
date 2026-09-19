"""Turning G83 peck-drilling-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from .common import add_motion, add_motion_with_meta
from .g74 import _append_peck_z_turning


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
    if abs(step_q) > 1e-9:
        tool = _append_peck_z_turning(motions, tool, target_z, retract_r, abs(step_q), feed)
    else:
        add_motion_with_meta(motions, 1, tool, Point2(target_x, target_z), None, feed if feed > 0 else None)
        tool = Point2(target_x, target_z)
    add_motion(motions, 0, tool, Point2(target_x, stock_z))
    add_motion(motions, 0, Point2(target_x, stock_z), Point2(stock_x, stock_z))
    return motions
