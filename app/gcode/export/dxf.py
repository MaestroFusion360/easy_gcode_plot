"""DXF consumer for the kernel's already-resolved motion trace."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterable

import ezdxf
from ezdxf import units

from ..kernel import ExecutionResult
from ..trace_tools import RenderPoint
from .dxf_geometry import _add_arc_or_circle, _helix_points, _motion_point, _validate_point
from .units import MM_PER_INCH, scale_motion

RAPID_LAYER = "TOOLPATH_RAPID"
CUT_LAYER = "TOOLPATH_CUT"
_METADATA_LOCK = Lock()


@contextmanager
def _fixed_metadata():
    """Scope ezdxf's fixed metadata to one deterministic CLI write."""
    with _METADATA_LOCK:
        previous = ezdxf.options.write_fixed_meta_data_for_testing
        ezdxf.options.write_fixed_meta_data_for_testing = True
        try:
            yield
        finally:
            ezdxf.options.write_fixed_meta_data_for_testing = previous


def _check_cancelled(cancelled) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError("Export cancelled")


def _is_turning(result: ExecutionResult, turning: bool | None) -> bool:
    if turning is not None:
        return turning
    return result.language == "fanuc_turn"


def build_dxf_document(
    result: ExecutionResult,
    *,
    turning: bool | None = None,
    render_points: Iterable[RenderPoint] | None = None,
    output_units: str = "mm",
    cancelled=None,
):
    """Build a DXF document from one completed kernel execution result."""
    _check_cancelled(cancelled)
    if result is None or not result.ok or not result.complete:
        raise ValueError("No valid complete CNC execution result is available for DXF export")

    turning = _is_turning(result, turning)
    points_by_motion: dict[int, list[RenderPoint]] = defaultdict(list)
    if render_points is not None:
        for point in render_points:
            _check_cancelled(cancelled)
            points_by_motion[point.motion_index].append(point)

    document = ezdxf.new("R2010")
    if output_units not in {"mm", "inch"}:
        raise ValueError(f"Unsupported DXF units: {output_units}")
    unit_scale = MM_PER_INCH if output_units == "inch" else 1.0
    document.units = units.IN if output_units == "inch" else units.MM
    document.layers.add(RAPID_LAYER, color=1, linetype="CONTINUOUS")
    document.layers.add(CUT_LAYER, color=5, linetype="CONTINUOUS")
    modelspace = document.modelspace()

    for motion_index, original_motion in enumerate(result.motions):
        _check_cancelled(cancelled)
        motion = scale_motion(original_motion, unit_scale)
        layer = RAPID_LAYER if motion.move == 0 else CUT_LAYER
        if motion.move in (2, 3) and motion.arc is not None:
            if _add_arc_or_circle(modelspace, motion, layer, turning=turning):
                continue
            if turning:
                raise ValueError("Turning trace contains an arc outside the X/Z export plane")
            helix = _helix_points(motion, motion_index, {} if unit_scale != 1.0 else points_by_motion)
            if len(helix) < 2:
                raise ValueError("DXF export cannot represent incomplete helical trace geometry")
            modelspace.add_polyline3d(helix, dxfattribs={"layer": layer})
            continue

        start = _motion_point(motion, end=False, turning=turning)
        end = _motion_point(motion, end=True, turning=turning)
        _validate_point(start, "line start")
        _validate_point(end, "line end")
        modelspace.add_line(start, end, dxfattribs={"layer": layer})

    return document


def export_dxf(
    result: ExecutionResult,
    path: str | Path,
    *,
    turning: bool | None = None,
    render_points: Iterable[RenderPoint] | None = None,
    output_units: str = "mm",
    deterministic: bool = False,
    cancelled=None,
) -> None:
    """Write the resolved toolpath to *path* as a millimetre DXF file."""
    if deterministic:
        with _fixed_metadata():
            document = build_dxf_document(
                result, turning=turning, render_points=render_points, output_units=output_units, cancelled=cancelled
            )
            _check_cancelled(cancelled)
            document.saveas(path)
    else:
        document = build_dxf_document(
            result, turning=turning, render_points=render_points, output_units=output_units, cancelled=cancelled
        )
        _check_cancelled(cancelled)
        document.saveas(path)
