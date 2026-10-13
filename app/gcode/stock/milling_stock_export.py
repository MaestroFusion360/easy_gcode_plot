"""Mesh construction and atomic STL output from detached stock snapshots."""

from __future__ import annotations

import logging
import math
import struct
from pathlib import Path

import numpy as np

from app.gcode.file_io import atomic_export
from app.gcode.stock.milling_stock_compact_mesh import compact_triangle_batches
from app.gcode.stock.milling_stock_mesh import triangle_batches
from app.gcode.stock.milling_stock_stl import _bilinear_height, limit_edges

from .milling_stock_types import MillingStockSnapshot

LOGGER = logging.getLogger(__name__)


MAX_STOCK_STL_TRIANGLES = 500_000


class _StockMeshBudgetExceeded(ValueError):
    """Retry with a smaller detached export surface, never change simulation."""


def milling_stock_triangles(timeline):
    """Iterate the surface triangles of a detached GPU stock readback."""
    timeline = timeline.snapshot() if hasattr(timeline, "snapshot") else timeline
    for triangles, _normal, _cut, _rapid in triangle_batches(timeline, bottom=True):
        yield from triangles


def milling_stock_mesh_triangles(snapshot, *, cancelled=None, max_triangles=2_000_000, simplify=False, report=None):
    """Build a detached mesh, optionally resampling a copy when the budget is exceeded."""
    simplified = False
    try:
        triangles = _mesh_triangles(snapshot, cancelled, max_triangles)
    except _StockMeshBudgetExceeded:
        if not simplify or max_triangles < 16:
            raise
        surface = _bounded_export_surface(snapshot, cancelled, max_triangles=max_triangles)
        triangles = _mesh_triangles(surface, cancelled, max_triangles)
        simplified = True
    if report is not None:
        report.update(simplified=simplified, triangles=len(triangles))
    return triangles


def _mesh_triangles(snapshot, cancelled, max_triangles):
    batches = []
    count = 0
    for triangles, _normal, _cut, _rapid in compact_triangle_batches(snapshot, cancelled):
        if cancelled is not None and cancelled():
            raise InterruptedError("Stock mesh insertion cancelled")
        count += len(triangles)
        if count > max_triangles:
            batches.clear()
            raise _StockMeshBudgetExceeded(f"Stock mesh exceeds the {max_triangles:,}-triangle limit")
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


def _bounded_export_surface(stock, cancelled, *, max_triangles=None):
    """Resample only the detached readback; retain bounds and physical units."""
    if cancelled is not None and cancelled():
        raise InterruptedError("Stock STL export cancelled")
    # A mixed cell needs at most four top and four bottom facets. Reserve
    # additional faces for conforming patch boundaries and the outer walls.
    max_cells = (MAX_STOCK_STL_TRIANGLES if max_triangles is None else max_triangles) // 16
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
