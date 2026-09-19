"""G90 longitudinal turning-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from .common import add_motion, add_motion_with_meta


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
