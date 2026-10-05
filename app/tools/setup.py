"""Temporary program tool assignments, independent of the persistent library."""

from copy import deepcopy

from app.tools.discovery import discover_tools
from app.tools.validation import normalized_milling_tools, normalized_tools


def refresh_setup(
    source,
    current,
    previous,
    *,
    turning,
    default_unit_scale=1.0,
    cancelled=None,
    library_tools=None,
    source_dialect="fanuc",
    program=None,
):
    """Refresh inferred geometry while retaining manual assignments in this document."""
    inferred = discover_tools(
        source,
        turning=turning,
        default_unit_scale=default_unit_scale,
        cancelled=cancelled,
        source_dialect=source_dialect,
        program=program,
    )
    normalize = normalized_tools if turning else normalized_milling_tools
    library = normalize(library_tools or {})
    for key in inferred.keys() & library.keys():
        inferred[key] = deepcopy(library[key])
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
