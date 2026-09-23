"""G92 threading-cycle expansion."""

from __future__ import annotations

from ...frontend.model import Motion, Point2
from .common import add_rectangular_pass


def add_g92_thread_pass(
    motions: list[Motion],
    start_x: float,
    start_z: float,
    target_x: float,
    target_z: float,
    lead: float,
) -> None:
    add_rectangular_pass(
        motions,
        Point2(start_x, start_z),
        Point2(target_x, target_z),
        lead,
        feed_axis="z",
    )
