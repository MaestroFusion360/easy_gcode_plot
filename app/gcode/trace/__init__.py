"""Pure consumers of the kernel's already-resolved logical motion trace.

Arc semantics belong to the kernel.  Rendering, statistics, and export may
sample or serialize a resolved arc, but must not choose an alternative IJK/R
interpretation after execution.
"""

from __future__ import annotations

from app.gcode.formatting import format_tool_list, format_trace_statistics
from app.gcode.trace.geometry import RenderPoint, arc_geometry, motion_length
from app.gcode.trace.sampling import RenderLimitExceeded, render_trace, sample_motion
from app.gcode.trace.statistics import trace_statistics

__all__ = [
    "RenderLimitExceeded",
    "RenderPoint",
    "arc_geometry",
    "format_tool_list",
    "format_trace_statistics",
    "motion_length",
    "render_trace",
    "sample_motion",
    "trace_statistics",
]
