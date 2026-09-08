"""Deterministic execution-event helpers shared by CNC resolvers and exporters."""

from __future__ import annotations

from .api_types import ExecutionEvent

PROGRAM_START = "program_start"
PROGRAM_END = "program_end"
SUBPROGRAM_START = "subprogram_start"
SUBPROGRAM_END = "subprogram_end"
TOOL_CHANGE = "tool_change"
HOME_RETURN = "home_return"


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
