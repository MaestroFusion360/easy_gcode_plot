"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

import math

from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, TraceMotion
from ..frontend.program import parse_program
from ..runtime.diagnostics import modal_conflict_diagnostics
from ..runtime.events import home_return_event, main_program_location, program_end_code, program_start_event
from ..runtime.execution import ProgramRuntime, semantic_instructions
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic
from .drilling import _cycle_signals
from .motion import _emit_milling_motions, _g53_home_axes
from .state import MillState, _apply_pre_flow_modal_state, _execution_step, _wcs_offset

try:
    from ._native_executor import execute_simple_blocks as _execute_simple_blocks
except ImportError:
    _execute_simple_blocks = None


def _report_unknown_g_codes(diagnostics, unknown_g, position_words, block) -> None:
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


def _validate_g73_retract_distance(value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("G73 retract distance must be finite and non-negative")


def _record_executed_motion_block(motions, executed, block) -> None:
    if motions and (not executed or executed[-1] != block.index):
        executed.append(block.index)


def _append_cycle_signals(block, state, words, occurrence_signals, signals):
    generated = _cycle_signals(block, state, words)
    signals.extend(generated)
    return occurrence_signals + generated


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
    g73_retract_distance: float = 1.0,
    include_instructions: bool = True,
):

    program = parse_program(source)
    program_start_block, program_number = main_program_location(program)
    program_started = False
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        x=home[0] - ox,
        y=home[1] - oy,
        z=home[2] - oz,
        unit_scale=float(default_unit_scale),
        g73_retract_distance=float(g73_retract_distance),
    )
    motions: list[TraceMotion] = []
    diagnostics: list[Diagnostic] = []
    executed: list[int] = []
    steps: list[ExecutionStep] = []
    signals = []
    events: list[ExecutionEvent] = []
    runtime = ProgramRuntime.create(program)
    recognized = {
        0,
        1,
        2,
        3,
        4,
        10,
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
        54.1,
        54,
        55,
        56,
        57,
        58,
        59,
        65,
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
    instructions = semantic_instructions(program) if include_instructions else ()

    def record_step(
        block,
        occurrence_events,
        *,
        emitted_count: int = 0,
        words=(),
        signals=(),
        stop: bool = False,
    ) -> None:
        events.extend(occurrence_events)
        steps.append(
            _execution_step(
                state,
                block,
                emitted_count,
                len(steps),
                words=words,
                signals=signals,
                events=occurrence_events,
                stop=stop,
                wcs_offsets=wcs_offsets,
            )
        )

    try:
        _validate_g73_retract_distance(state.g73_retract_distance)
        while 0 <= runtime.pc < len(program.blocks):
            if _execute_simple_blocks is not None and _execute_simple_blocks(
                program, runtime, state, motions, executed, steps, wcs_offsets
            ):
                continue
            block = runtime.next_block(program.blocks)
            occurrence_events: list[ExecutionEvent] = []
            if not program_started and block.index == program_start_block:
                occurrence_events.append(program_start_event(block, program_number))
                program_started = True
            if block.optional_skip and skip_optional_blocks:
                runtime.advance()
                continue

            flow = runtime.dispatch_macro(block, runtime.pc, program.blocks)
            if flow.handled:
                record_step(block, occurrence_events)
                runtime.jump(flow.next_pc)
                continue

            evaluated_block = runtime.evaluate_block(block)
            words = evaluated_block.words
            if words.errors:
                token, error = words.errors[0]
                raise ValueError(
                    f"{error} at line {block.index + 1}: {block.raw} ({token.letter}{token.expr})"
                ) from error
            codes = evaluated_block.codes
            gcodes = codes.all_g
            evaluated = evaluated_block.values

            conflict_diagnostics = modal_conflict_diagnostics(gcodes, "fanuc_mill", block)
            if conflict_diagnostics:
                diagnostics.extend(conflict_diagnostics)
                record_step(block, occurrence_events, words=evaluated)
                runtime.advance()
                continue

            g65_flow = runtime.dispatch_g65(
                block=block,
                words=words,
                codes=codes,
                pc=runtime.pc,
                program=program,
            )
            if g65_flow.dispatch.handled:
                occurrence_events.extend(g65_flow.events)
                record_step(block, occurrence_events, words=evaluated)
                runtime.jump(g65_flow.dispatch.next_pc)
                continue

            occurrence_signals = evaluated_block.signals
            signals.extend(occurrence_signals)

            unknown_g = tuple(g for g in gcodes if g not in recognized)
            position_words = any(letter in words for letter in ("X", "Y", "Z"))
            _report_unknown_g_codes(diagnostics, unknown_g, position_words, block)
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
                record_step(block, occurrence_events, words=evaluated, signals=occurrence_signals)
                runtime.advance()
                continue

            _apply_milling_tool_change(block, state, words, codes, diagnostics, occurrence_events, runtime.call_stack)

            _apply_pre_flow_modal_state(state, gcodes, codes.all_m, words, wcs_offsets=wcs_offsets)
            if state.unknown_axes:
                if state.absolute:
                    for letter in tuple(state.unknown_axes):
                        if letter in words:
                            setattr(state, letter.lower(), words[letter] * state.unit_scale)
                            state.unknown_axes.remove(letter)
                record_step(block, occurrence_events, words=evaluated, signals=occurrence_signals)
                runtime.advance()
                continue
            if 28 in gcodes:
                occurrence_events.append(
                    home_return_event(
                        block,
                        "G28",
                        tuple(axis for axis in ("X", "Y", "Z") if axis in words),
                        len(runtime.call_stack),
                    )
                )
            if 53 in gcodes:
                home_axes = _g53_home_axes(state, words, home, wcs_offsets=wcs_offsets)
                if home_axes:
                    occurrence_events.append(home_return_event(block, "G53", home_axes, len(runtime.call_stack)))

            program_flow = runtime.dispatch_program_flow(
                codes=codes,
                words=words,
                pc=runtime.pc,
                program=program,
                block=block,
                program_number=program_number,
            )
            occurrence_events.extend(program_flow.events)

            if program_flow.dispatch.handled:
                if program_flow.dispatch.stop:
                    record_step(block, occurrence_events, words=evaluated, signals=occurrence_signals, stop=True)
                    break
                record_step(block, occurrence_events, words=evaluated, signals=occurrence_signals)
                runtime.jump(program_flow.dispatch.next_pc)
                continue

            motion_start = len(motions)

            _emit_milling_motions(block, state, words, gcodes, motions, home, wcs_offsets)
            occurrence_signals = _append_cycle_signals(block, state, words, occurrence_signals, signals)

            _record_executed_motion_block(motions, executed, block)
            record_step(
                block,
                occurrence_events,
                emitted_count=len(motions) - motion_start,
                words=evaluated,
                signals=occurrence_signals,
            )
            runtime.advance()
    except Exception as exc:
        diagnostics.append(_execution_diagnostic(exc, program))
        return ExecutionResult(
            False,
            program,
            instructions,
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
        instructions=instructions,
        motions=tuple(motions),
        diagnostics=tuple(diagnostics),
        executed_blocks=tuple(executed),
        signals=signals,
        program_end=program_end_code(event_tuple),
        execution_steps=tuple(steps),
        events=event_tuple,
    )
