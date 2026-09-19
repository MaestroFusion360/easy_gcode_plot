"""Temporary program tool assignments, independent of the persistent library."""

from copy import deepcopy

from app.tools.discovery import discover_tools


def refresh_setup(source, current, previous, *, turning, default_unit_scale=1.0, cancelled=None):
    """Refresh inferred geometry while retaining manual assignments in this document."""
    inferred = discover_tools(
        source,
        turning=turning,
        default_unit_scale=default_unit_scale,
        cancelled=cancelled,
    )
    overrides = {key: deepcopy(spec) for key, spec in current.items() if key in inferred and spec != previous.get(key)}
    current.clear()
    current.update(deepcopy(inferred))
    current.update(overrides)
    return inferred


def reset_program_setup(window):
    """Start a fresh setup only when New/Open successfully changes the document."""
    window.tools = {}
    window.millingTools = {}
    window.program_tool_inference = {}
    for name in ("toolLibraryDlg",):
        dialog = getattr(window, name, None)
        if dialog is not None:
            dialog.reject()
