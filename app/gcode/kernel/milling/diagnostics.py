"""Milling execution diagnostics, tool changes and subprogram events."""

from __future__ import annotations

from ..api.types import Diagnostic, ExecutionEvent
from ..runtime.diagnostics import diagnostic_from_exception
from ..runtime.events import TOOL_CHANGE


def _execution_diagnostic(exc: Exception, program) -> Diagnostic:
    return diagnostic_from_exception(exc, program)


def _apply_milling_tool_change(block, state, words, codes, diagnostics, occurrence_events, call_stack):
    if "T" in words:
        tool_value = words["T"]
        if float(tool_value).is_integer() and 1 <= int(tool_value) <= 99:
            state.selected_tool = f"T{int(tool_value)}"
            state.selected_tool_block = block.index
        else:
            state.selected_tool = None
            state.selected_tool_block = None
            diagnostics.append(
                Diagnostic(
                    "UNSUPPORTED_TOOL_NUMBER",
                    "Milling tool number must be in the T1-T99 range",
                    "warning",
                    "unsupported",
                    block.index + 1,
                    block.raw,
                )
            )
    if 6 in codes.all_m:
        previous_tool = state.active_tool
        changed_tool = state.selected_tool
        if changed_tool is not None:
            state.active_tool = changed_tool
        occurrence_events.append(
            ExecutionEvent(
                TOOL_CHANGE,
                block.index,
                code="M06",
                tool=changed_tool,
                previous_tool=previous_tool,
                call_depth=len(call_stack),
                related_block=state.selected_tool_block,
            )
        )
