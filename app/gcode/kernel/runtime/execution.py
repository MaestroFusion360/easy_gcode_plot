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

from ..api.resources import SemanticError, active_budget, checkpoint
from ..api.types import ExecutionEvent, SemanticInstruction
from ..frontend.lang import eval_condition, evaluate_expression
from ..frontend.program import EvaluatedWords, eval_words
from .events import program_flow_events
from .signals import signals_for_words

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
    all_g: tuple[int | float, ...]
    all_m: tuple[int | float, ...]
    gcode: int | float | None
    mcode: int | float | None


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


@dataclass(frozen=True)
class EvaluatedBlock:
    words: EvaluatedWords
    codes: BlockCodes
    values: tuple[tuple[str, float], ...]
    signals: tuple[object, ...]


@dataclass(frozen=True)
class ProgramFlowDispatch:
    dispatch: SubprogramDispatch
    events: tuple[ExecutionEvent, ...]


@dataclass
class ProgramRuntime:
    """Mutable control-flow data shared by every machine-mode executor."""

    index: ProgramExecutionIndex
    variables: dict[str, float]
    call_stack: list[tuple[int, int, int]]
    max_call_depth: int = 64
    pc: int = 0
    guard: int = 0

    @classmethod
    def create(cls, program: object, *, variables: dict[str, float] | None = None) -> ProgramRuntime:
        return cls(build_program_execution_index(program), variables if variables is not None else {}, [])

    def next_block(
        self,
        blocks: tuple[object, ...] | list[object],
        *,
        guard_limit: int = 500_000,
        guard_message: str = "Program execution guard reached",
    ) -> object:
        """Return the current source block while applying the shared execution budget/guard."""
        checkpoint("executed_blocks")
        self.guard += 1
        if self.guard > guard_limit:
            raise RuntimeError(guard_message)
        return blocks[self.pc]

    def advance(self) -> None:
        self.pc += 1

    def jump(self, pc: int) -> None:
        self.pc = pc

    def dispatch_macro(self, block: object, pc: int, blocks: tuple[object, ...] | list[object]) -> FlowDispatch:
        return dispatch_macro_flow(
            block=block,
            pc=pc,
            blocks=blocks,
            variables=self.variables,
            label_to_index=self.index.label_to_index,
            while_to_end=self.index.while_to_end,
            end_to_while=self.index.end_to_while,
        )

    def evaluate(self, block: object) -> EvaluatedWords:
        return eval_words(block.parsed_words, self.variables)

    def evaluate_block(self, block: object) -> EvaluatedBlock:
        words = self.evaluate(block)
        return EvaluatedBlock(
            words,
            classify_block_codes(words),
            tuple((key, value) for key in words for value in words.all(key)),
            signals_for_words(block.index, words),
        )

    def dispatch_subprogram(self, mcode: int | float | None, words: dict[str, float], pc: int) -> SubprogramDispatch:
        result = dispatch_subprogram_flow(
            mcode=mcode,
            words=words,
            pc=pc,
            olabel_to_index=self.index.olabel_to_index,
            call_stack=self.call_stack,
            max_call_depth=self.max_call_depth,
        )
        self.call_stack = result.call_stack
        return result

    def dispatch_program_flow(
        self,
        *,
        codes: BlockCodes,
        words: EvaluatedWords,
        pc: int,
        program: object,
        block: object,
        program_number: int | None,
    ) -> ProgramFlowDispatch:
        """Dispatch M98/M99/M2/M30 and build the corresponding shared events."""
        flow_mcode = flow_control_mcode(codes.all_m, codes.mcode)
        call_stack_before = list(self.call_stack)
        dispatch = self.dispatch_subprogram(flow_mcode, words, pc)
        return ProgramFlowDispatch(
            dispatch,
            program_flow_events(flow_mcode, dispatch, words, program, block, program_number, call_stack_before),
        )


def semantic_instructions(program: object | None) -> tuple[SemanticInstruction, ...]:
    """Build the public, immutable instruction stream from the shared AST."""
    ast = getattr(program, "ast", None)
    if ast is None:
        return ()
    return tuple(
        SemanticInstruction(
            node.kind,
            node.block_index,
            node.raw,
            tuple((word.letter, word.expr) for word in node.words),
            tuple(code for word in node.words if word.letter == "G" and (code := word.int_code) is not None),
            tuple(code for word in node.words if word.letter == "M" and (code := word.int_code) is not None),
            node.nlabel,
            node.olabel,
        )
        for node in ast.nodes
    )


def apply_unit_mode(state: object, gcodes: tuple[int | float, ...] | list[int | float]) -> None:
    """Apply the shared G20/G21 unit modal state without machine-specific semantics."""
    if 20 in gcodes:
        state.unit_scale = 25.4
    if 21 in gcodes:
        state.unit_scale = 1.0


def flow_control_mcode(all_m: tuple[int | float, ...], fallback: int | float | None = None) -> int | float | None:
    """Select program-flow M code independently of source word order."""
    for code in (98, 99, 30, 2):
        if code in all_m:
            return code
    return fallback


def classify_block_codes(words: object) -> BlockCodes:
    """Return all evaluated G/M codes plus the effective execution G/M code."""

    def code_value(value: float) -> int | float:
        numeric = float(value)
        return int(numeric) if numeric.is_integer() else numeric

    all_getter = getattr(words, "all", None)
    all_g = tuple(code_value(v) for v in all_getter("G")) if callable(all_getter) else ()
    all_m = tuple(code_value(v) for v in all_getter("M")) if callable(all_getter) else ()
    if not all_g and isinstance(words, dict) and "G" in words:
        all_g = (code_value(words["G"]),)
    if not all_m and isinstance(words, dict) and "M" in words:
        all_m = (code_value(words["M"]),)

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
    all_g: tuple[int | float, ...],
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
        checkpoint("macro_iterations")
        if pc not in while_to_end:
            raise ValueError(f"WHILE has no matching END at line {line}: {raw}")
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
        checkpoint("macro_iterations")
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
    mcode: int | float | None,
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
        budget = active_budget.get()
        if budget is not None:
            max_call_depth = budget.limits.call_depth
        if not float(words["P"]).is_integer() or words["P"] <= 0:
            raise ValueError("M98 P must be a positive integer")
        if not float(words.get("L", 1)).is_integer() or words.get("L", 1) <= 0:
            raise ValueError("M98 L must be a positive integer")
        target_o = int(words["P"])
        target_idx = olabel_to_index.get(target_o)
        if target_idx is None:
            raise ValueError(f"M98 targets missing O{target_o}")
        if len(stack) >= max_call_depth:
            raise ValueError(f"M98 call depth exceeds limit {max_call_depth}")
        repeat = max(1, int(words.get("L", 1.0)))
        checkpoint("subprogram_calls")
        stack.append((pc + 1, target_idx, repeat))
        return SubprogramDispatch(True, target_idx, False, stack)

    if mcode == 99:
        if "P" in words:
            raise SemanticError(
                "UNSUPPORTED_M99_P",
                "M99 P requires an explicit controller profile",
                "controller_dependent",
            )
        if stack:
            ret_pc, sub_pc, remaining = stack[-1]
            if remaining > 1:
                checkpoint("subprogram_calls")
                stack[-1] = (ret_pc, sub_pc, remaining - 1)
                return SubprogramDispatch(True, sub_pc, False, stack)
            stack.pop()
            return SubprogramDispatch(True, ret_pc, False, stack)
        return SubprogramDispatch(True, pc, True, stack)

    if mcode in (2, 30):
        return SubprogramDispatch(True, pc, True, stack)

    return SubprogramDispatch(False, pc, False, stack)
