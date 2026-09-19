"""G92 threading-cycle expansion."""

from __future__ import annotations

from ..frontend.model import Motion, Point2
from .common import add_motion, add_motion_with_meta


def add_g92_thread_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    lead: float,
) -> None:
    start = Point2(start_x, start_z)
    pass_start = Point2(target_x, start_z)
    pass_end = Point2(target_x, target_z)
    add_motion(motions, 0, start, pass_start)
    add_motion_with_meta(motions, 1, pass_start, pass_end, None, lead if lead > 0 else None)
    add_motion(motions, 0, pass_end, Point2(start_x, target_z))
    add_motion(motions, 0, Point2(start_x, target_z), start)
