"""Turning G84 tapping-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from ..runtime.drilling import axial_cycle_moves
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
    for segment in axial_cycle_moves(stock_z, target_z, return_to=stock_z, return_feed=True):
        begin = Point2(target_x, segment.start)
        end = Point2(target_x, segment.end)
        add_motion_with_meta(motions, segment.move, begin, end, None, feed if feed > 0 else None)
    if abs(target_x - stock_x) > 1e-9:
        add_motion(motions, 0, Point2(target_x, stock_z), Point2(stock_x, stock_z))
    return motions
