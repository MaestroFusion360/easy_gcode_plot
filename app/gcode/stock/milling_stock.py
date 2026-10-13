"""Three-axis trajectory replay and export of GPU stock readback. Units are mm."""

from __future__ import annotations

import logging
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from app.gcode.file_io import atomic_export
from app.gcode.stock.milling_stock_compact_mesh import compact_triangle_batches
from app.gcode.stock.milling_stock_mesh import triangle_batches
from app.gcode.stock.milling_stock_stl import _bilinear_height, limit_edges
from app.gcode.stock.milling_stock_sweep import CutterSweep
from app.gcode.trace_tools import _arc_extreme_coordinates
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.tools.milling_geometry import milling_tool_profile

# Keep exported stock well below the importer's two-million-facet limit.
MAX_STOCK_STL_TRIANGLES = 500_000
LOGGER = logging.getLogger(__name__)


class _StockMeshBudgetExceeded(ValueError):
    """Retry with a smaller detached export surface, never change simulation."""


@dataclass(frozen=True)
class MillingStockSpec:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    resolution: float = 1.0

    def validate(self):
        values = (self.x_min, self.x_max, self.y_min, self.y_max, self.z_min, self.z_max, self.resolution)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Stock bounds and resolution must be finite")
        if not (self.x_min < self.x_max and self.y_min < self.y_max and self.z_min < self.z_max):
            raise ValueError("Stock must have positive X, Y and Z dimensions")
        if self.resolution <= 0:
            raise ValueError("Stock resolution must be positive")

    @property
    def bounds(self):
        return ((self.x_min, self.x_max), (self.y_min, self.y_max), (self.z_min, self.z_max))


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


@dataclass(frozen=True)
class MillingStockSnapshot:
    spec: MillingStockSpec
    height: np.ndarray
    rapid: np.ndarray
    dx: float
    dy: float
    sweeps: tuple = ()
    motions: tuple = ()

    @property
    def nx(self):
        return self.height.shape[1] - 1

    @property
    def ny(self):
        return self.height.shape[0] - 1


def milling_stock_triangles(timeline):
    """Iterate the surface triangles of a detached GPU stock readback."""
    timeline = timeline.snapshot() if hasattr(timeline, "snapshot") else timeline
    for triangles, _normal, _cut, _rapid in triangle_batches(timeline, bottom=True):
        yield from triangles


def milling_stock_mesh_triangles(snapshot, *, cancelled=None, max_triangles=2_000_000):
    """Build an in-memory snapshot mesh without resampling the simulated surface."""
    batches = []
    count = 0
    for triangles, _normal, _cut, _rapid in compact_triangle_batches(snapshot, cancelled):
        if cancelled is not None and cancelled():
            raise InterruptedError("Stock mesh insertion cancelled")
        count += len(triangles)
        if count > max_triangles:
            raise ValueError("Stock mesh exceeds the plot's two-million-triangle limit")
        batches.append(triangles.copy())
    if cancelled is not None and cancelled():
        raise InterruptedError("Stock mesh insertion cancelled")
    if not batches:
        raise ValueError("The current stock contains no remaining material")
    return np.concatenate(batches)


def write_milling_stock_stl(path: str | Path, timeline, *, cancelled=None, precise=True, options=None, report=None):
    """Vectorized binary STL from a detached playback snapshot, atomically saved."""

    timeline = timeline.snapshot() if hasattr(timeline, "snapshot") else timeline
    if options is not None:
        options.validate()
        timeline = _export_snapshot(timeline, options, cancelled)
    triangle_dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
    count = 0
    simplified = False

    def write(temporary):
        nonlocal count
        count = 0
        with temporary.open("wb") as stream:
            stream.write(b"Easy G-Code Plot milling stock".ljust(80, b"\0"))
            stream.write(struct.pack("<I", 0))
            if simplified or (options is not None and options.calculated):
                batches = compact_triangle_batches(timeline, cancelled)
            else:
                batches = _export_batches(
                    _stock_stl_batches(timeline, precise, tagged=options is not None), timeline, options, cancelled
                )
            for triangles, normal, _cut, _rapid in batches:
                if cancelled is not None and cancelled():
                    raise InterruptedError("Stock STL export cancelled")
                if count + len(triangles) > MAX_STOCK_STL_TRIANGLES:
                    raise _StockMeshBudgetExceeded()
                records = np.zeros(len(triangles), dtype=triangle_dtype)
                records["normal"] = normal
                scale = options.scale if options is not None and (simplified or options.calculated) else 1.0
                records["vertices"] = triangles * scale
                stream.write(records.tobytes())
                count += len(records)
            stream.seek(80)
            stream.write(struct.pack("<I", count))

    try:
        atomic_export(path, write, cancelled=cancelled)
    except _StockMeshBudgetExceeded:
        timeline = _bounded_export_surface(timeline, cancelled)
        simplified = True
        atomic_export(path, write, cancelled=cancelled)
        LOGGER.warning(
            "stock_stl_mesh_simplified path=%s triangles=%d grid=%dx%d", path, count, timeline.nx, timeline.ny
        )
    if report is not None:
        report.update(simplified=simplified, triangles=count)
    return count


def _bounded_export_surface(stock, cancelled):
    """Resample only the detached readback; retain bounds and physical units."""
    if cancelled is not None and cancelled():
        raise InterruptedError("Stock STL export cancelled")
    # A mixed cell needs at most four top and four bottom facets. Reserve
    # additional faces for conforming patch boundaries and the outer walls.
    max_cells = MAX_STOCK_STL_TRIANGLES // 16
    factor = max(1.0, math.sqrt(stock.nx * stock.ny / max_cells))
    nx, ny = max(1, int(stock.nx / factor)), max(1, int(stock.ny / factor))
    while nx * ny > max_cells:
        if nx >= ny:
            nx -= 1
        else:
            ny -= 1
    dx = (stock.spec.x_max - stock.spec.x_min) / nx
    dy = (stock.spec.y_max - stock.spec.y_min) / ny
    x, y = np.meshgrid(stock.spec.x_min + np.arange(nx + 1) * dx, stock.spec.y_min + np.arange(ny + 1) * dy)
    height = _bilinear_height(stock, np.stack((x, y), axis=-1)).astype(np.float32)
    return MillingStockSnapshot(stock.spec, height, np.zeros_like(height, dtype=bool), dx, dy)


def _export_snapshot(stock, options, cancelled):
    # Export tessellates a detached GPU readback. It never replays removal.
    if cancelled is not None and cancelled():
        raise InterruptedError("Stock STL export cancelled")
    return stock.snapshot() if hasattr(stock, "snapshot") else stock


def _export_batches(source, stock, options, cancelled):
    for item in source:
        triangles, normal, cut, rapid = item[:4]
        if options is None:
            yield triangles, normal, cut, rapid
            continue
        top_surface = item[4]
        for batch in limit_edges(
            triangles,
            options.edge_length,
            cancelled,
            stock=stock if top_surface else None,
            options=options if top_surface else None,
        ):
            normals = np.cross(batch[:, 1] - batch[:, 0], batch[:, 2] - batch[:, 0])
            norms = np.linalg.norm(normals, axis=1)
            valid = norms > 1e-16
            if not np.any(valid):
                continue
            batch = batch[valid]
            normals = normals[valid] / norms[valid, None]
            yield batch * options.scale, normals, False, False


def _stock_stl_batches(timeline, precise, *, tagged=False):
    # "precise" is kept for source compatibility. STL tessellation accuracy
    # is controlled by StockStlOptions against the GPU-sampled surface.
    yield from triangle_batches(timeline, bottom=True, tagged=tagged)
