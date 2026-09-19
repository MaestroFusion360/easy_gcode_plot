"""Export mode dispatch used by the GUI and CLI."""

from __future__ import annotations

from dataclasses import replace

from ..kernel import ExecutionResult
from .common import _check_cancelled
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
from .turn import export_full_program


def export_program(
    result: ExecutionResult,
    source: str,
    *,
    mode: int,
    lathe_mode: bool,
    options: ExportOptions,
    export_arc_mode: int = 0,
    cancelled=None,
) -> str:
    """Export from an immutable GUI snapshot without touching Qt objects."""
    _check_cancelled(cancelled)
    if result is None or not result.ok or not result.complete:
        raise ValueError("No valid CNC execution result is available for export")

    if mode == TURN_FULL_PROGRAM_MODE:
        if not lathe_mode:
            raise ValueError("Turn Full Program export requires Lathe Mode")
        return export_full_program(result, source.splitlines(), replace(options, arc_mode=2), cancelled=cancelled)

    if mode == MILL_FULL_PROGRAM_MODE:
        if lathe_mode:
            raise ValueError("Mill Full Program export requires Milling Mode")
        return export_full_mill_program(result, source.splitlines(), replace(options, arc_mode=0), cancelled=cancelled)

    if mode == EXPANDED_EXECUTION_MODE:
        return export_result(result, replace(options, arc_mode=int(export_arc_mode)), cancelled=cancelled)

    if mode == PLOT_DATA_MODE:
        return export_result(
            result,
            replace(
                options,
                arc_mode=4,
                incremental=False,
                include_execution_events=False,
            ),
            cancelled=cancelled,
        )

    if mode == DXF_MODE:
        raise ValueError("DXF export requires a file target")

    raise ValueError(f"Unknown export mode: {mode}")


def export_pgm(window) -> str:
    """Compatibility entry point for the existing MainWindow export action."""
    return export_program(
        getattr(window, "execution_result", None),
        str(window.ui.editor.text()),
        mode=int(window.exportMode),
        lathe_mode=bool(window.latheMode),
        options=_window_export_options(window, arc_mode=0),
        export_arc_mode=int(window.exportArcMode),
    )
