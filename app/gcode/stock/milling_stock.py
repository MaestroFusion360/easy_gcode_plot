"""Three-axis trajectory replay and export of GPU stock readback. Units are mm."""

from __future__ import annotations

import math
from time import perf_counter

import numpy as np

from app.gcode.stock.milling_stock_sweep import CutterSweep
from app.gcode.trace.geometry import _arc_extreme_coordinates
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.tools.milling_geometry import milling_tool_profile

from .milling_stock_types import MillingStockSpec


def motion_bounds(motion):
    """Conservative physical bounds, including the complete resolved arc."""
    low = np.minimum(
        (motion.start_x, motion.start_y, motion.start_z), (motion.end_x, motion.end_y, motion.end_z)
    ).astype(float)
    high = np.maximum(
        (motion.start_x, motion.start_y, motion.start_z), (motion.end_x, motion.end_y, motion.end_z)
    ).astype(float)
    if motion.arc is not None:
        for point in _arc_extreme_coordinates(motion, 1.0):
            low, high = np.minimum(low, point), np.maximum(high, point)
    return low, high


def auto_milling_stock(motions, allowance=3.0, resolution=1.0, *, tools=None, wcs_origin=(0, 0, 0)):
    """Physical XY cutter envelope; Z top defaults to the selected WCS zero."""
    if not math.isfinite(allowance) or allowance < 0 or not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Stock allowance/resolution must be finite and non-negative/positive")
    cutting = [m for m in motions if m.move != 0] or list(motions)
    if not cutting:
        return None
    bounds = map(motion_bounds, cutting)
    radius = max(
        max(r for _, r in _tool_profile((tools or {}).get(tool, DEFAULT_MILLING_TOOL)))
        for tool in {m.tool for m in cutting}
    )
    low, high = next(bounds)
    for lower, upper in bounds:
        low, high = np.minimum(low, lower), np.maximum(high, upper)
    margin = max(allowance, resolution)
    top = float(wcs_origin[2])
    return MillingStockSpec(
        low[0] - radius - margin,
        high[0] + radius + margin,
        low[1] - radius - margin,
        high[1] + radius + margin,
        min(low[2], top) - margin,
        top,
        resolution,
    )


def merge_bounds(first, second):
    if first is None:
        return second
    if second is None:
        return first
    return min(first[0], second[0]), max(first[1], second[1]), min(first[2], second[2]), max(first[3], second[3])


def _reject_rotary(motions):
    for index, motion in enumerate(motions):
        for field in ("orientation", "tool_orientation", "start_tool_orientation"):
            if getattr(motion, field, None) is not None:
                raise ValueError(f"3-axis stock only: rotary/TCP motion {index + 1} ({field})")


def _tool_profile(tool):
    profile = milling_tool_profile(tool)
    if len(profile) < 2:
        raise ValueError(f"Unknown or invalid milling tool geometry: {tool!r}")
    # The entire cutter head/profile is represented; the axial radial profile
    # is supplied by the application's existing milling-tool library.
    return tuple((float(z), float(r)) for z, r in profile)


class MillingStockTimeline:
    """Trajectory replay only. Remaining material lives in the GPU renderer."""

    def __init__(self, motions, spec: MillingStockSpec, tools=None):
        spec.validate()
        self.motions = tuple(motions)
        _reject_rotary(self.motions)
        self.spec = spec
        self.tools = {key: dict(tool) for key, tool in (tools or {}).items()}
        self.missing_tools = tuple(dict.fromkeys(m.tool for m in self.motions if m.tool not in self.tools))
        self.motion_count = 0
        self.revision = 0
        self.surface_error = 0.01
        self._profiles = {}
        self._sweeps = {}
        self.snapshot_reader = self._unattached_snapshot

    @property
    def bounds(self):
        return self.spec.bounds

    @property
    def sweeps(self):
        return tuple(self._sweeps[i] for i in sorted(self._sweeps) if i < self.motion_count)

    def sweep_at(self, index):
        return self._sweeps.get(index)

    def _motion_tool(self, motion):
        if motion.tool not in self._profiles:
            self._profiles[motion.tool] = _tool_profile(self.tools.get(motion.tool, DEFAULT_MILLING_TOOL))
        return self._profiles[motion.tool], self.tools.get(motion.tool, DEFAULT_MILLING_TOOL)

    def preflight(self):
        # Tool geometry is validated as each motion enters the replay. There is
        # no CPU stamp-work estimate and no CPU removal backend.
        return

    def set_motion_count(self, count, *, time_budget=None):
        count = max(0, min(int(count), len(self.motions)))
        if count == self.motion_count:
            return
        if count < self.motion_count:
            self.motion_count = count
            self.revision += 1
            return
        deadline = None if time_budget is None else perf_counter() + max(0, time_budget)
        try:
            while self.motion_count < count:
                index = self.motion_count
                motion = self.motions[index]
                if index not in self._sweeps:
                    profile, tool = self._motion_tool(motion)
                    low, high = motion_bounds(motion)
                    radius = max(r for _, r in profile)
                    if (
                        low[2] + min(z for z, _ in profile) < self.spec.z_max
                        and low[0] - radius < self.spec.x_max
                        and high[0] + radius > self.spec.x_min
                        and low[1] - radius < self.spec.y_max
                        and high[1] + radius > self.spec.y_min
                    ):
                        self._sweeps[index] = CutterSweep.from_motion(
                            motion,
                            tool,
                            profile,
                            index,
                            contour_error=self.surface_error,
                        )
                self.motion_count += 1
                if deadline is not None and perf_counter() >= deadline:
                    break
        finally:
            self.revision += 1

    def acknowledge_frame(self, revision):
        # The overlay retains immutable frames; GPU state is consumed in paint.
        return

    def snapshot(self, *, cancelled=None):
        """Read the actual GPU material state on its owning OpenGL thread."""
        if cancelled is None:
            return self.snapshot_reader(self)
        return self.snapshot_reader(self, cancelled=cancelled)

    @staticmethod
    def _unattached_snapshot(_timeline, *, cancelled=None):
        raise ValueError("Stock snapshot requires an attached GPU renderer")
