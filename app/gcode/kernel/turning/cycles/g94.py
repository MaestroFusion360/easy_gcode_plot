"""G94 facing-cycle expansion."""

from __future__ import annotations

from ...frontend.model import Motion, Point2
from .common import add_rectangular_pass


def add_g94_facing_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    feed: float,
    first_block_with_z: bool = False,
) -> None:
    add_rectangular_pass(
        motions,
        Point2(start_x, start_z),
        Point2(target_x, target_z),
        feed,
        feed_axis="x",
        first_block_direct=first_block_with_z,
    )
