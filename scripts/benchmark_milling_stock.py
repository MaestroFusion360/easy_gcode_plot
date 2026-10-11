"""Bounded stock benchmark: python -m scripts.benchmark_milling_stock --width 200 --height 150.

Reports actual CPU array sizes and timings, without machine-dependent pass/fail thresholds.
The VBO payload equals vertex_bytes; driver allocation overhead is not measured.
"""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np

from app.gcode.kernel import TraceMotion
from app.gcode.program_execution import execute_program
from app.gcode.stock.milling_stock import (
    MillingStockSpec,
    MillingStockTimeline,
    auto_milling_stock,
    write_milling_stock_stl,
)
from app.ui.plot.milling_stock_overlay import MillingStockOverlayItem


def benchmark(
    width=200,
    height=150,
    scenario="capsule",
    *,
    source=None,
    arc_type=1,
    tool_type=None,
    diameter=10,
    precise=False,
    motion_count=10_000,
    stock_box=None,
    render_every=10,
):
    moves = []
    if scenario == "capsule":
        moves = [TraceMotion(1, width / 4, -4, width * 3 / 4, -4, start_y=height / 2, end_y=height / 2, tool="T1")]
    elif scenario == "pocket":
        moves = [
            TraceMotion(1, width / 4, -4, width * 3 / 4, -4, start_y=y, end_y=y, tool="T1")
            for y in range(height // 4, height * 3 // 4, 2)
        ]
    elif scenario == "raster":
        moves = [
            TraceMotion(
                1, i % width, -4, (i + 1) % width, -4, start_y=i // width % height, end_y=i // width % height, tool="T1"
            )
            for i in range(motion_count)
        ]
    stock = MillingStockTimeline(
        moves,
        MillingStockSpec(0, width, 0, height, -10, 0, 1),
        {"T1": {"type": "mill_flat", "diameter": 10, "length": 30}},
    )
    if source is not None:
        result, tools, _ = execute_program(
            Path(source).read_text(encoding="utf-8-sig"), language="fanuc_mill", source_arc_type=arc_type
        )
        if not result.complete or result.diagnostics:
            raise ValueError("Benchmark source has execution diagnostics; check its arc mode")
        if tool_type is not None:
            tools = {m.tool: {"type": tool_type, "diameter": diameter, "length": 30} for m in result.motions}
        moves = result.motions
        spec = MillingStockSpec(*stock_box) if stock_box else auto_milling_stock(moves, tools=tools)
        stock = MillingStockTimeline(moves, spec, tools)
        scenario = str(source)
    item = MillingStockOverlayItem()
    started = perf_counter()
    item.set_frame(stock)
    initial_frame_seconds = perf_counter() - started
    removal_seconds, mesh_seconds, frame_ms = 0, 0, []
    for count in range(1, len(moves) + 1):
        started = perf_counter()
        stock.set_motion_count(count)
        removed = perf_counter()
        removal_seconds += removed - started
        if count % max(1, render_every) and count != len(moves):
            continue
        item.set_frame(stock)
        finished = perf_counter()
        mesh_seconds += finished - removed
        frame_ms.append((finished - started) * 1000)
    if scenario == "grid":
        # Original same-map baseline retained explicitly; this is not the new mesher.
        stock.height[height * 4 // 15 : height * 2 // 3, width // 4 : width * 3 // 4] = -4
        item.set_frame(stock)
    with TemporaryDirectory(prefix="milling_stock_benchmark_") as temporary:
        path = Path(temporary) / "stock.stl"
        started = perf_counter()
        triangles = write_milling_stock_stl(path, stock.snapshot(), precise=precise)
        stl_seconds = perf_counter() - started
        stl_bytes = path.stat().st_size
    return {
        "scenario": scenario,
        "motions": len(moves),
        "precise_export": precise,
        "render_every": render_every,
        "stock_bounds": stock.bounds,
        "removed_cells": int(np.count_nonzero(stock.height < stock.spec.z_max - 1e-7)),
        "removed_volume_mm3": float(np.sum(stock.spec.z_max - stock.height) * stock.dx * stock.dy),
        "initial_frame_ms": initial_frame_seconds * 1000,
        "cpu_frame_p95_ms": float(np.percentile(frame_ms, 95)) if frame_ms else 0,
        "cpu_frame_max_ms": max(frame_ms, default=0),
        "tools": stock.tools,
        "cells": stock.nx * stock.ny,
        "requested_resolution": stock.spec.resolution,
        "cache_spacing_mm": [stock.dx, stock.dy],
        "vertex_bytes": item.buffer_bytes,
        "height_and_mask_bytes": stock.height.nbytes + stock.rapid.nbytes,
        "checkpoint_bytes": stock.checkpoint_bytes,
        "mesh_seconds": mesh_seconds,
        "removal_seconds": removal_seconds,
        "stl_seconds": stl_seconds,
        "triangles": triangles,
        "stl_bytes": stl_bytes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=200)
    parser.add_argument("--height", type=int, default=150)
    parser.add_argument("--scenario", choices=("capsule", "pocket", "grid", "raster"), default="capsule")
    parser.add_argument("--motions", type=int, default=10_000)
    parser.add_argument("--precise", action="store_true", help="Run the optional continuous STL mesher")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--arc-type", choices=(1, 2), type=int, default=1)
    parser.add_argument("--tool-type", choices=("mill_flat", "mill_ball"), help="Override the inferred program tools")
    parser.add_argument("--diameter", type=float, default=10)
    parser.add_argument("--stock-box", type=float, nargs=6, metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"))
    parser.add_argument("--render-every", type=int, default=10)
    args = parser.parse_args()
    print(
        json.dumps(
            benchmark(
                args.width,
                args.height,
                args.scenario,
                source=args.input,
                arc_type=args.arc_type,
                tool_type=args.tool_type,
                diameter=args.diameter,
                precise=args.precise,
                motion_count=args.motions,
                stock_box=args.stock_box,
                render_every=args.render_every,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
