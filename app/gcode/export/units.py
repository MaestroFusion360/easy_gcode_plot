"""Scale resolved millimetre geometry at the export boundary."""

from __future__ import annotations

from dataclasses import replace

from ..kernel import TraceMotion

MM_PER_INCH = 25.4


def scale_motion(motion: TraceMotion, unit_scale: float) -> TraceMotion:
    """Return a motion expressed in units whose size is *unit_scale* mm."""
    if unit_scale == 1.0:
        return motion
    arc = motion.arc
    if arc is not None:
        arc = replace(
            arc,
            center=tuple(value / unit_scale for value in arc.center),
            radius=arc.radius / unit_scale,
        )
    return replace(
        motion,
        start_x=motion.start_x / unit_scale,
        start_y=motion.start_y / unit_scale,
        start_z=motion.start_z / unit_scale,
        end_x=motion.end_x / unit_scale,
        end_y=motion.end_y / unit_scale,
        end_z=motion.end_z / unit_scale,
        radius=None if motion.radius is None else motion.radius / unit_scale,
        feed=None if motion.feed is None else motion.feed / unit_scale,
        i=None if motion.i is None else motion.i / unit_scale,
        j=None if motion.j is None else motion.j / unit_scale,
        k=None if motion.k is None else motion.k / unit_scale,
        arc=arc,
    )
