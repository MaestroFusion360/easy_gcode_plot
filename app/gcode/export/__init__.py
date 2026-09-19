"""G-code and DXF export built on the authoritative kernel execution result.

DXF symbols resolve lazily so callers that only emit G-code never load the
``ezdxf`` document layer.
"""

from __future__ import annotations

from .dispatch import export_pgm, export_program
from .formatting import motion_line
from .mill import export_full_mill_program
from .options import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
    ExportOptions,
    _window_export_options,
)
from .trace import export_result
from .turn import export_cycle_groups, export_full_program

__all__ = [
    "DXF_MODE",
    "EXPANDED_EXECUTION_MODE",
    "ExportOptions",
    "MILL_FULL_PROGRAM_MODE",
    "PLOT_DATA_MODE",
    "TURN_FULL_PROGRAM_MODE",
    "_window_export_options",
    "export_cycle_groups",
    "export_full_mill_program",
    "export_full_program",
    "export_pgm",
    "export_program",
    "export_result",
    "motion_line",
]

_DXF_EXPORTS = frozenset({"CUT_LAYER", "RAPID_LAYER", "build_dxf_document", "export_dxf"})


def __getattr__(name: str):
    if name in _DXF_EXPORTS:
        from . import dxf  # pylint: disable=import-outside-toplevel

        return getattr(dxf, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
