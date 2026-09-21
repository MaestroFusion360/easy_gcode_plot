"""Deterministic execution-event helpers shared by CNC resolvers and exporters."""

from __future__ import annotations

from ..api.types import ExecutionEvent

PROGRAM_START = "program_start"
PROGRAM_END = "program_end"
SUBPROGRAM_START = "subprogram_start"
SUBPROGRAM_END = "subprogram_end"
TOOL_CHANGE = "tool_change"
HOME_RETURN = "home_return"


def program_start_event(block, program_number: int | None) -> ExecutionEvent:
    """Build the shared main-program start event."""
    return ExecutionEvent(
        PROGRAM_START,
        block.index,
        code=(f"O{program_number}" if program_number is not None else None),
        program_number=program_number,
    )


def home_return_event(block, code: str, axes: tuple[str, ...], call_depth: int) -> ExecutionEvent:
    """Build the shared G28/G30/G53 reference-return event."""
    return ExecutionEvent(HOME_RETURN, block.index, code=code, axes=axes, call_depth=call_depth)


def main_program_location(program) -> tuple[int, int | None]:
    """Return the main-program source block and O number without reparsing source text."""
    for block in program.blocks:
        if block.olabel is not None:
            return block.index, block.olabel
    return (program.blocks[0].index if program.blocks else 0), None


def subprogram_number(program, target_block: int | None) -> int | None:
    if target_block is None or not 0 <= target_block < len(program.blocks):
        return None
    return program.blocks[target_block].olabel


def g65_call_event(block, program, target_block: int, call_depth: int) -> ExecutionEvent:
    """Describe a G65 macro call using the existing subprogram boundary event contract."""
    return ExecutionEvent(
        SUBPROGRAM_START,
        block.index,
        code="G65",
        program_number=subprogram_number(program, target_block),
        call_depth=call_depth,
        target_block=target_block,
    )


def program_end_code(events: tuple[ExecutionEvent, ...]) -> str | None:
    return next((event.code for event in reversed(events) if event.kind == PROGRAM_END and event.code), None)


def event_blocks(events: tuple[ExecutionEvent, ...], kind: str) -> set[int]:
    """Source and target blocks owned by one structural event kind."""
    blocks: set[int] = set()
    for event in events:
        if event.kind != kind:
            continue
        blocks.add(event.source_block)
        if event.target_block is not None:
            blocks.add(event.target_block)
    return blocks


def program_flow_events(
    flow_mcode,
    dispatch,
    words,
    program,
    block,
    program_number: int | None,
    call_stack_before: list[tuple[int, int, int]],
) -> tuple[ExecutionEvent, ...]:
    """Describe shared M98/M99/M2/M30 control flow for either machine mode."""
    events: list[ExecutionEvent] = []
    if flow_mcode == 98 and dispatch.handled and not dispatch.stop:
        target_block = dispatch.next_pc
        events.append(
            ExecutionEvent(
                SUBPROGRAM_START,
                block.index,
                code=(f"O{int(words['P'])}" if "P" in words else None),
                program_number=subprogram_number(program, target_block),
                call_depth=len(dispatch.call_stack),
                target_block=target_block,
            )
        )
    elif flow_mcode == 99 and dispatch.handled:
        if call_stack_before:
            current_target = call_stack_before[-1][1]
            current_program = subprogram_number(program, current_target)
            events.append(
                ExecutionEvent(
                    SUBPROGRAM_END,
                    block.index,
                    code="M99",
                    program_number=current_program,
                    call_depth=len(call_stack_before),
                    target_block=current_target,
                )
            )
            if dispatch.next_pc == current_target and len(dispatch.call_stack) == len(call_stack_before):
                events.append(
                    ExecutionEvent(
                        SUBPROGRAM_START,
                        block.index,
                        code=(f"O{current_program}" if current_program is not None else None),
                        program_number=current_program,
                        call_depth=len(dispatch.call_stack),
                        target_block=current_target,
                    )
                )
        else:
            events.append(ExecutionEvent(PROGRAM_END, block.index, code="M99", program_number=program_number))
    elif flow_mcode in (2, 30) and dispatch.handled:
        events.append(
            ExecutionEvent(PROGRAM_END, block.index, code=f"M{int(flow_mcode):02d}", program_number=program_number)
        )
    return tuple(events)
