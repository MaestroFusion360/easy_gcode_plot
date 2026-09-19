"""Conversions from internal interpreter models to the public kernel API."""

from __future__ import annotations

from ..frontend.model import Motion
from .types import TraceMotion


def trace_motion(motion: Motion) -> TraceMotion:
    """Convert a native turning motion into the stable, flat public shape."""
    return TraceMotion(
        move=motion.move,
        start_x=motion.start.x,
        start_z=motion.start.z,
        end_x=motion.end.x,
        end_z=motion.end.z,
        radius=motion.radius,
        feed=motion.feed,
        i=motion.i,
        k=motion.k,
        source_block=motion.source_block,
        source_nlabel=motion.source_nlabel,
        source_raw=motion.source_raw,
        source_kind=motion.source_kind,
        compensation_mode=motion.compensation_mode,
        tool=motion.tool,
        compensation_applied=motion.compensation_applied,
        plane=18,
        cycle_generated=motion.source_kind == "cycle",
        playback_group=motion.playback_group,
    )
