"""Shared execution helpers used by cycle compilation and source-trace replay.

This module contains control-flow and block-classification mechanics only.  It
intentionally does not build geometry or implement individual FANUC cycles.
Keeping these mechanics shared prevents the compile and trace paths from
silently drifting on Macro B flow, subprogram dispatch, and G/M-code selection.
"""

from __future__ import annotations

# Interpreter dispatch exits early for each explicit CNC control-flow opcode.
# pylint: disable=too-many-return-statements
from dataclasses import dataclass

from .lang import eval_condition, evaluate_expression

MOTION_CODES = frozenset({0, 1, 2, 3, 32, 33})
CYCLE_CODES = frozenset({70, 71, 72, 73, 74, 75, 76, 80, 83, 84, 90, 92, 94})
POSITION_NEUTRAL_GCODES = frozenset(
    {
        4,
        18,
        20,
        21,
        40,
        41,
        42,
        54,
        55,
        56,
        57,
        58,
        59,
        80,
        96,
        97,
        98,
        99,
        190,
        191,
    }
)


@dataclass(frozen=True)
class BlockCodes:
    all_g: tuple[int, ...]
    all_m: tuple[int, ...]
    gcode: int | None
    mcode: int | None


@dataclass(frozen=True)
class ProgramExecutionIndex:
    label_to_index: dict[int, int]
    olabel_to_index: dict[int, int]
    while_to_end: dict[int, int]
    end_to_while: dict[int, int]


@dataclass(frozen=True)
class FlowDispatch:
    handled: bool
    next_pc: int


@dataclass(frozen=True)
class SubprogramDispatch:
    handled: bool
    next_pc: int
    stop: bool
    call_stack: list[tuple[int, int, int]]


def classify_block_codes(words: object) -> BlockCodes:
    """Return all evaluated G/M codes plus the effective execution G/M code."""
    all_getter = getattr(words, "all", None)
    all_g = tuple(int(round(v)) for v in all_getter("G")) if callable(all_getter) else ()
    all_m = tuple(int(round(v)) for v in all_getter("M")) if callable(all_getter) else ()
    if not all_g and isinstance(words, dict) and "G" in words:
        all_g = (int(round(words["G"])),)
    if not all_m and isinstance(words, dict) and "M" in words:
        all_m = (int(round(words["M"])),)

    cycle_gcodes = [g for g in all_g if g in CYCLE_CODES]
    motion_gcodes = [g for g in all_g if g in MOTION_CODES]
    gcode = (
        cycle_gcodes[-1] if cycle_gcodes else (motion_gcodes[-1] if motion_gcodes else (all_g[-1] if all_g else None))
    )
    return BlockCodes(
        all_g=all_g,
        all_m=all_m,
        gcode=gcode,
        mcode=all_m[-1] if all_m else None,
    )


def retain_modal_turning_cycles(
    all_g: tuple[int, ...],
    *,
    active_g90: bool,
    active_g92: bool,
    active_g94: bool,
) -> tuple[bool, bool, bool]:
    """Apply the shared G90/G92/G94 cancellation rule for one block.

    Non-motion modal G codes such as G96/G97 do not cancel these lathe cycles.
    Any explicit motion/cycle code does, unless the same cycle is explicitly
    present in the block.
    """
    explicit_motion_or_cycle = tuple(code for code in all_g if code in MOTION_CODES or code in CYCLE_CODES)
    if not explicit_motion_or_cycle:
        return active_g90, active_g92, active_g94
    return (
        active_g90 and 90 in explicit_motion_or_cycle,
        active_g92 and 92 in explicit_motion_or_cycle,
        active_g94 and 94 in explicit_motion_or_cycle,
    )


def build_program_execution_index(program: object) -> ProgramExecutionIndex:
    """Build label/subprogram and WHILE/END maps once for an execution pass."""
    blocks = tuple(getattr(program, "blocks", ()))
    ast = getattr(program, "ast", None)
    if ast is not None:
        label_to_index = dict(getattr(ast, "nlabel_to_index", {}))
        olabel_to_index = dict(getattr(ast, "olabel_to_index", {}))
    else:
        label_to_index: dict[int, int] = {}
        olabel_to_index: dict[int, int] = {}
        for i, block in enumerate(blocks):
            nlabel = getattr(block, "nlabel", None)
            olabel = getattr(block, "olabel", None)
            if nlabel is not None and nlabel not in label_to_index:
                label_to_index[int(nlabel)] = i
            if olabel is not None and olabel not in olabel_to_index:
                olabel_to_index[int(olabel)] = i

    while_stack: dict[int, list[int]] = {}
    while_to_end: dict[int, int] = {}
    end_to_while: dict[int, int] = {}
    for i, block in enumerate(blocks):
        flow = getattr(block, "flow_node", None)
        loop_id = getattr(flow, "loop_id", None) if flow is not None else None
        if loop_id is None:
            continue
        loop_id = int(loop_id)
        if flow.kind == "while":
            while_stack.setdefault(loop_id, []).append(i)
        elif flow.kind == "end":
            stack = while_stack.get(loop_id)
            if stack:
                while_index = stack.pop()
                while_to_end[while_index] = i
                end_to_while[i] = while_index

    return ProgramExecutionIndex(
        label_to_index=label_to_index,
        olabel_to_index=olabel_to_index,
        while_to_end=while_to_end,
        end_to_while=end_to_while,
    )


def dispatch_macro_flow(
    *,
    block: object,
    pc: int,
    blocks: tuple[object, ...] | list[object],
    variables: dict[str, float],
    label_to_index: dict[int, int],
    while_to_end: dict[int, int],
    end_to_while: dict[int, int],
) -> FlowDispatch:
    """Execute one parsed Macro B flow node and return the next program counter."""
    flow = getattr(block, "flow_node", None)
    if flow is None:
        return FlowDispatch(False, pc)

    line = int(getattr(block, "index", pc)) + 1
    raw = str(getattr(block, "raw", ""))

    if flow.kind == "assign":
        if flow.var_key is not None and flow.value_expr is not None:
            try:
                value = evaluate_expression(flow.value_expr, variables)
            except Exception as exc:
                raise ValueError(f"Cannot evaluate assignment at line {line}: {raw}: {exc}") from exc
            key = flow.var_key if flow.var_key.isdigit() else flow.var_key.upper()
            variables[key] = value
        return FlowDispatch(True, pc + 1)

    if flow.kind == "goto":
        target = label_to_index.get(flow.target_label or -1)
        if target is None:
            raise ValueError(f"Missing GOTO target N{flow.target_label} at line {line}: {raw}")
        return FlowDispatch(True, target)

    if flow.kind == "if_goto":
        try:
            take = eval_condition(flow.condition or "0", variables)
        except Exception as exc:
            raise ValueError(f"Cannot evaluate IF at line {line}: {raw}: {exc}") from exc
        if not take:
            return FlowDispatch(True, pc + 1)
        target = label_to_index.get(flow.target_label or -1)
        if target is None:
            raise ValueError(f"Missing IF/GOTO target N{flow.target_label} at line {line}: {raw}")
        return FlowDispatch(True, target)

    if flow.kind == "while":
        try:
            take = eval_condition(flow.condition or "0", variables)
        except Exception as exc:
            raise ValueError(f"Cannot evaluate WHILE at line {line}: {raw}: {exc}") from exc
        if take:
            return FlowDispatch(True, pc + 1)
        end_index = while_to_end.get(pc)
        if end_index is None:
            raise ValueError(f"WHILE DO{flow.loop_id} has no matching END{flow.loop_id} at line {line}: {raw}")
        return FlowDispatch(True, end_index + 1)

    if flow.kind == "end":
        while_index = end_to_while.get(pc)
        if while_index is None:
            raise ValueError(f"END{flow.loop_id} has no matching WHILE DO{flow.loop_id} at line {line}: {raw}")
        while_flow = getattr(blocks[while_index], "flow_node", None)
        try:
            take = while_flow is not None and eval_condition(while_flow.condition or "0", variables)
        except Exception as exc:
            raise ValueError(f"Cannot evaluate END loop at line {line}: {raw}: {exc}") from exc
        return FlowDispatch(True, (while_index + 1) if take else (pc + 1))

    return FlowDispatch(False, pc)


def dispatch_subprogram_flow(
    *,
    mcode: int | None,
    words: dict[str, float],
    pc: int,
    olabel_to_index: dict[int, int],
    call_stack: list[tuple[int, int, int]],
    max_call_depth: int = 64,
) -> SubprogramDispatch:
    """Execute M98/M99/M2/M30 program flow without interpreting geometry."""
    stack = list(call_stack)
    if mcode == 98:
        if "P" not in words:
            raise ValueError("M98 requires a P subprogram target")
        target_o = int(words["P"])
        target_idx = olabel_to_index.get(target_o)
        if target_idx is None:
            raise ValueError(f"M98 targets missing O{target_o}")
        if len(stack) >= max_call_depth:
            raise ValueError(f"M98 call depth exceeds limit {max_call_depth}")
        repeat = max(1, int(words.get("L", 1.0)))
        stack.append((pc + 1, target_idx, repeat))
        return SubprogramDispatch(True, target_idx, False, stack)

    if mcode == 99:
        if stack:
            ret_pc, sub_pc, remaining = stack[-1]
            if remaining > 1:
                stack[-1] = (ret_pc, sub_pc, remaining - 1)
                if "P" in words:
                    target_o = int(words["P"])
                    target_idx = olabel_to_index.get(target_o)
                    if target_idx is not None:
                        return SubprogramDispatch(True, target_idx, False, stack)
                return SubprogramDispatch(True, sub_pc, False, stack)
            stack.pop()
            return SubprogramDispatch(True, ret_pc, False, stack)
        return SubprogramDispatch(True, pc, True, stack)

    if mcode in (2, 30):
        return SubprogramDispatch(True, pc, True, stack)

    return SubprogramDispatch(False, pc, False, stack)
