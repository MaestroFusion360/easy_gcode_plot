"""G-code and DXF export built on the authoritative kernel execution result.

DXF symbols resolve lazily so callers that only emit G-code never load the
``ezdxf`` document layer.
"""

from __future__ import annotations

from dataclasses import replace

from ..post_profiles import load_post_profile
from .common import (
    DXF_MODE,
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
    ExportOptions,
    _window_export_options,
    motion_line,
)
from .expanded import convert_resolved_program, export_result
from .full import export_full_mill_program, export_full_program, is_native_full_program, normalize_full_program

__all__ = [
    "DXF_MODE",
    "EXPANDED_EXECUTION_MODE",
    "ExportOptions",
    "MILL_FULL_PROGRAM_MODE",
    "TURN_FULL_PROGRAM_MODE",
    "_window_export_options",
    "export_full_mill_program",
    "export_full_program",
    "export_pgm",
    "export_program",
    "export_result",
    "convert_resolved_program",
    "load_post_profile",
    "motion_line",
    "normalize_full_program",
]


def export_program(
    result, source, *, mode, lathe_mode, options, export_arc_mode=0, cancelled=None, target=None, sinumerik_840d_sl=None
):
    if mode in (TURN_FULL_PROGRAM_MODE, MILL_FULL_PROGRAM_MODE):
        if (mode == TURN_FULL_PROGRAM_MODE) != lathe_mode:
            raise ValueError("Full Program export mode must match the source machine")
        return normalize_full_program(result, source, options, cancelled=cancelled)
    if mode == EXPANDED_EXECUTION_MODE:
        return export_result(
            result,
            replace(options, arc_mode=int(export_arc_mode)),
            cancelled=cancelled,
            target=target,
            sinumerik_840d_sl=sinumerik_840d_sl,
        )
    if mode == DXF_MODE:
        raise ValueError("DXF export requires a file target")
    raise ValueError(f"Unknown export mode: {mode}")


def export_pgm(window):
    return export_program(
        getattr(window, "execution_result", None),
        str(window.ui.editor.text()),
        mode=int(window.exportMode),
        lathe_mode=bool(window.latheMode),
        options=_window_export_options(window, arc_mode=0),
        export_arc_mode=int(window.exportArcMode),
        target=_window_target_post(window),
        sinumerik_840d_sl=getattr(window, "sinumerik840dSl", True),
    )


def _window_target_post(window):
    if int(window.exportMode) != EXPANDED_EXECUTION_MODE:
        return None
    turning = bool(window.latheMode)
    target = int(getattr(window, "exportTargetCnc", 0))
    if target == 0:
        return _window_auto_post(window)
    return {
        1: "fanuc_lathe_a" if turning else "fanuc_mill",
        2: "fanuc_lathe_b" if turning else "sinumerik_iso",
        3: "sinumerik_840d",
        4: "fanuc_mill_multiaxis",
        5: "sinumerik_840d_multiaxis",
    }.get(target)


def _window_auto_post(window):
    result = getattr(window, "execution_result", None)
    if result is None or result.language == "fanuc_turn" or result.source_dialect != "sinumerik":
        return None
    return "sinumerik_840d" if is_native_full_program(result) else "sinumerik_iso"


_DXF_EXPORTS = frozenset({"CUT_LAYER", "RAPID_LAYER", "build_dxf_document", "export_dxf"})


def __getattr__(name: str):
    if name in _DXF_EXPORTS:
        from . import dxf  # pylint: disable=import-outside-toplevel

        return getattr(dxf, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
