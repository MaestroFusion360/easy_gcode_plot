"""G94 facing-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from .common import add_motion, add_motion_with_meta


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
