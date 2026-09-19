"""Turning G84 tapping-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from .common import add_motion, add_motion_with_meta


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
    del retract_r, step_q, dwell_p
    motions: list[Motion] = []
    tool = Point2(stock_x, stock_z)
    if abs(target_x - stock_x) > 1e-9:
        add_motion(motions, 0, tool, Point2(target_x, stock_z))
        tool = Point2(target_x, stock_z)
    bottom = Point2(target_x, target_z)
    add_motion_with_meta(motions, 1, tool, bottom, None, feed if feed > 0 else None)
    add_motion_with_meta(motions, 1, bottom, Point2(target_x, stock_z), None, feed if feed > 0 else None)
    if abs(target_x - stock_x) > 1e-9:
        add_motion(motions, 0, Point2(target_x, stock_z), Point2(stock_x, stock_z))
    return motions
