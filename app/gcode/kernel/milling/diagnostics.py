"""Milling execution diagnostics, tool changes and subprogram events."""

from __future__ import annotations

import re

from ..api.resources import SemanticError
from ..api.types import Diagnostic, ExecutionEvent
from ..frontend.lang import UndefinedMacroVariableError
from ..runtime.events import (
    PROGRAM_END,
    SUBPROGRAM_END,
    SUBPROGRAM_START,
    TOOL_CHANGE,
    subprogram_number,
)

_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def _exception_chain_contains(exc: Exception, exc_type: type[BaseException]) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, exc_type):
            return True
        current = current.__cause__ or current.__context__
    return False


def _execution_diagnostic(exc: Exception, program) -> Diagnostic:
    message = str(exc)
    code = "UNDEFINED_MACRO" if _exception_chain_contains(exc, UndefinedMacroVariableError) else "EXECUTION_ERROR"
    status = "malformed"
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, SemanticError):
            code = current.code
            status = current.status
            break
        current = current.__cause__ or current.__context__

    lowered = message.lower()
    if code == "EXECUTION_ERROR":
        if "missing goto target" in lowered or "missing if/goto target" in lowered:
            code = "FLOW_TARGET_MISSING"
        elif "m98 targets missing" in lowered:
            code = "SUBPROGRAM_MISSING"
        elif "call depth exceeds" in lowered:
            code = "CALL_DEPTH_EXCEEDED"

    line = None
    match = _LINE_RE.search(message)
    if match is not None:
        line = int(match.group(1))
    raw = None
    if line is not None and 1 <= line <= len(program.blocks):
        raw = program.blocks[line - 1].raw
    return Diagnostic(code=code, message=message, status=status, line=line, raw=raw)


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


def _record_milling_flow_events(
    flow_mcode, sub, words, program, block, program_number, call_stack, call_stack_before, occurrence_events
):
    if flow_mcode == 98 and sub.handled and not sub.stop:
        target_block = sub.next_pc
        occurrence_events.append(
            ExecutionEvent(
                SUBPROGRAM_START,
                block.index,
                code=(f"O{int(words['P'])}" if "P" in words else None),
                program_number=subprogram_number(program, target_block),
                call_depth=len(call_stack),
                target_block=target_block,
            )
        )
    elif flow_mcode == 99 and sub.handled:
        if call_stack_before:
            current_target = call_stack_before[-1][1]
            current_program = subprogram_number(program, current_target)
            occurrence_events.append(
                ExecutionEvent(
                    SUBPROGRAM_END,
                    block.index,
                    code="M99",
                    program_number=current_program,
                    call_depth=len(call_stack_before),
                    target_block=current_target,
                )
            )
            if sub.next_pc == current_target and len(call_stack) == len(call_stack_before):
                occurrence_events.append(
                    ExecutionEvent(
                        SUBPROGRAM_START,
                        block.index,
                        code=(f"O{current_program}" if current_program is not None else None),
                        program_number=current_program,
                        call_depth=len(call_stack),
                        target_block=current_target,
                    )
                )
        else:
            occurrence_events.append(
                ExecutionEvent(
                    PROGRAM_END,
                    block.index,
                    code="M99",
                    program_number=program_number,
                )
            )
    elif flow_mcode in (2, 30) and sub.handled:
        occurrence_events.append(
            ExecutionEvent(
                PROGRAM_END,
                block.index,
                code=f"M{int(flow_mcode):02d}",
                program_number=program_number,
            )
        )
