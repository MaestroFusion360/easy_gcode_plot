"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

from ..api.resources import checkpoint
from ..api.types import (
    Diagnostic,
    ExecutionEvent,
    ExecutionResult,
    ExecutionStep,
    SemanticInstruction,
    TraceMotion,
)
from ..frontend.program import eval_words, parse_program
from ..runtime.events import HOME_RETURN, PROGRAM_START, main_program_location, program_end_code
from ..runtime.execution import (
    build_program_execution_index,
    classify_block_codes,
    dispatch_macro_flow,
    dispatch_subprogram_flow,
    flow_control_mcode,
)
from ..runtime.signals import signals_for_words
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic, _record_milling_flow_events
from .motion import _emit_milling_motions, _g53_home_axes
from .state import MillState, _apply_pre_flow_modal_state, _execution_step, _wcs_offset


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
):

    program = parse_program(source.splitlines())
    program_start_block, program_number = main_program_location(program)
    program_started = False
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        x=home[0] - ox,
        y=home[1] - oy,
        z=home[2] - oz,
        unit_scale=float(default_unit_scale),
    )
    motions: list[TraceMotion] = []
    diagnostics: list[Diagnostic] = []
    executed: list[int] = []
    steps: list[ExecutionStep] = []
    signals = []
    events: list[ExecutionEvent] = []
    variables: dict[str, float] = {}
    call_stack: list[tuple[int, int, int]] = []
    recognized = {
        0,
        1,
        2,
        3,
        4,
        17,
        18,
        19,
        20,
        21,
        28,
        40,
        41,
        42,
        43,
        49,
        50,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        58,
        59,
        68,
        69,
        73,
        80,
        81,
        82,
        83,
        84,
        85,
        86,
        90,
        91,
        94,
        95,
        98,
        99,
    }
    recognized_m = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 30, 98, 99}
    index = build_program_execution_index(program)

    instructions = []
    for node in program.ast.nodes if program.ast else ():
        g_codes = tuple(code for w in node.words if w.letter == "G" and (code := w.int_code) is not None)
        m_codes = tuple(code for w in node.words if w.letter == "M" and (code := w.int_code) is not None)
        instructions.append(
            SemanticInstruction(
                node.kind,
                node.block_index,
                node.raw,
                tuple((w.letter, w.expr) for w in node.words),
                g_codes,
                m_codes,
                node.nlabel,
                node.olabel,
            )
        )

    pc = 0
    guard = 0
    try:
        while 0 <= pc < len(program.blocks):
            checkpoint("executed_blocks")
            guard += 1
            if guard > 500_000:
                raise RuntimeError("Program execution guard reached")
            block = program.blocks[pc]
            occurrence_events: list[ExecutionEvent] = []
            if not program_started and block.index == program_start_block:
                occurrence_events.append(
                    ExecutionEvent(
                        PROGRAM_START,
                        block.index,
                        code=(f"O{program_number}" if program_number is not None else None),
                        program_number=program_number,
                    )
                )
                program_started = True
            if block.optional_skip and skip_optional_blocks:
                pc += 1
                continue

            flow = dispatch_macro_flow(
                block=block,
                pc=pc,
                blocks=program.blocks,
                variables=variables,
                label_to_index=index.label_to_index,
                while_to_end=index.while_to_end,
                end_to_while=index.end_to_while,
            )
            if flow.handled:
                events.extend(occurrence_events)
                steps.append(
                    _execution_step(state, block, 0, len(steps), events=occurrence_events, wcs_offsets=wcs_offsets)
                )
                pc = flow.next_pc
                continue

            words = eval_words(block.parsed_words, variables)
            if words.errors:
                token, error = words.errors[0]
                raise ValueError(
                    f"{error} at line {block.index + 1}: {block.raw} ({token.letter}{token.expr})"
                ) from error
            codes = classify_block_codes(words)
            gcodes = codes.all_g
            occurrence_signals = signals_for_words(block.index, words)
            signals.extend(occurrence_signals)
            evaluated = tuple((k, v) for k in words for v in words.all(k))

            unknown_g = tuple(g for g in gcodes if g not in recognized)
            position_words = any(letter in words for letter in ("X", "Y", "Z"))
            for g in unknown_g:
                diagnostics.append(
                    Diagnostic(
                        "UNSUPPORTED_G_CODE",
                        (
                            f"G{g} is not modeled for fanuc_mill; execution stops before this position block"
                            if position_words
                            else f"G{g} is not modeled for fanuc_mill; ignored for trace execution"
                        ),
                        "error" if position_words else "warning",
                        "unsupported" if position_words else "unverified",
                        block.index + 1,
                        block.raw,
                    )
                )
            for m in codes.all_m:
                if 0 <= m <= 199 and m not in recognized_m:
                    diagnostics.append(
                        Diagnostic(
                            "UNSUPPORTED_M_CODE",
                            f"M{m} is not modeled for fanuc_mill; ignored for trace execution",
                            "warning",
                            "unverified",
                            block.index + 1,
                            block.raw,
                        )
                    )
            if unknown_g and position_words:
                _apply_pre_flow_modal_state(state, gcodes, codes.all_m, words, wcs_offsets=wcs_offsets)
                state.unknown_axes.update(letter for letter in ("X", "Y", "Z") if letter in words)
                events.extend(occurrence_events)
                steps.append(
                    _execution_step(
                        state,
                        block,
                        0,
                        len(steps),
                        words=evaluated,
                        signals=occurrence_signals,
                        events=occurrence_events,
                        wcs_offsets=wcs_offsets,
                    )
                )
                pc += 1
                continue

            _apply_milling_tool_change(block, state, words, codes, diagnostics, occurrence_events, call_stack)

            _apply_pre_flow_modal_state(state, gcodes, codes.all_m, words, wcs_offsets=wcs_offsets)
            if state.unknown_axes:
                if state.absolute:
                    for letter in tuple(state.unknown_axes):
                        if letter in words:
                            setattr(state, letter.lower(), words[letter] * state.unit_scale)
                            state.unknown_axes.remove(letter)
                events.extend(occurrence_events)
                steps.append(
                    _execution_step(
                        state,
                        block,
                        0,
                        len(steps),
                        words=evaluated,
                        signals=occurrence_signals,
                        events=occurrence_events,
                        wcs_offsets=wcs_offsets,
                    )
                )
                pc += 1
                continue
            if 28 in gcodes:
                occurrence_events.append(
                    ExecutionEvent(
                        HOME_RETURN,
                        block.index,
                        code="G28",
                        axes=tuple(axis for axis in ("X", "Y", "Z") if axis in words),
                        call_depth=len(call_stack),
                    )
                )
            if 53 in gcodes:
                home_axes = _g53_home_axes(state, words, home, wcs_offsets=wcs_offsets)
                if home_axes:
                    occurrence_events.append(
                        ExecutionEvent(
                            HOME_RETURN,
                            block.index,
                            code="G53",
                            axes=home_axes,
                            call_depth=len(call_stack),
                        )
                    )

            flow_mcode = flow_control_mcode(codes.all_m, codes.mcode)
            call_stack_before = list(call_stack)
            sub = dispatch_subprogram_flow(
                mcode=flow_mcode,
                words=words,
                pc=pc,
                olabel_to_index=index.olabel_to_index,
                call_stack=call_stack,
            )
            call_stack = sub.call_stack
            _record_milling_flow_events(
                flow_mcode, sub, words, program, block, program_number, call_stack, call_stack_before, occurrence_events
            )

            if sub.handled:
                if sub.stop:
                    events.extend(occurrence_events)
                    steps.append(
                        _execution_step(
                            state,
                            block,
                            0,
                            len(steps),
                            words=evaluated,
                            signals=occurrence_signals,
                            events=occurrence_events,
                            stop=True,
                            wcs_offsets=wcs_offsets,
                        )
                    )
                    break
                events.extend(occurrence_events)
                steps.append(
                    _execution_step(
                        state,
                        block,
                        0,
                        len(steps),
                        words=evaluated,
                        signals=occurrence_signals,
                        events=occurrence_events,
                        wcs_offsets=wcs_offsets,
                    )
                )
                pc = sub.next_pc
                continue

            motion_start = len(motions)

            _emit_milling_motions(block, state, words, gcodes, motions, home, wcs_offsets)

            if motions and (not executed or executed[-1] != block.index):
                executed.append(block.index)
            events.extend(occurrence_events)
            steps.append(
                _execution_step(
                    state,
                    block,
                    len(motions) - motion_start,
                    len(steps),
                    words=evaluated,
                    signals=occurrence_signals,
                    events=occurrence_events,
                    wcs_offsets=wcs_offsets,
                )
            )
            pc += 1
    except Exception as exc:
        diagnostics.append(_execution_diagnostic(exc, program))
        return ExecutionResult(
            False,
            program,
            tuple(instructions),
            tuple(motions),
            tuple(diagnostics),
            tuple(executed),
            signals=tuple(signals),
            execution_steps=tuple(steps),
            complete=False,
            events=tuple(events),
        )

    signals = tuple(signals)
    event_tuple = tuple(events)
    return ExecutionResult(
        ok=not any(d.severity == "error" for d in diagnostics),
        program=program,
        instructions=tuple(instructions),
        motions=tuple(motions),
        diagnostics=tuple(diagnostics),
        executed_blocks=tuple(executed),
        signals=signals,
        program_end=program_end_code(event_tuple),
        execution_steps=tuple(steps),
        events=event_tuple,
    )
