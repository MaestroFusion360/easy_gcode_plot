"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .api_types import Diagnostic, ExecutionResult, ExecutionStep, SemanticInstruction, TraceMotion
from .execution import (
    build_program_execution_index,
    classify_block_codes,
    dispatch_macro_flow,
    dispatch_subprogram_flow,
    flow_control_mcode,
)
from .lang import UndefinedMacroVariableError
from .program import eval_words, parse_program
from .resources import SemanticError, checkpoint, require_progress
from .signals import program_end_code, signals_for_words

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


@dataclass
class MillState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    feed: float = 0.0
    unit_scale: float = 1.0
    absolute: bool = True
    plane: int = 17
    move: int = 0
    active_wcs: int = 54
    cycle: int = 80
    cycle_z: float | None = None
    cycle_r: float | None = None
    cycle_q: float | None = None
    cycle_feed: float = 0.0
    return_initial: bool = False
    cycle_initial_z: float | None = None
    cutter_comp: int = 40
    tool_length_comp: bool = False
    tool_length_h: int | None = None
    active_tool: str | None = None
    feed_mode: str = "per_minute"
    spindle_rpm: float | None = None


def _xyz(words, state: MillState) -> tuple[float, float, float]:
    def resolve(letter: str, current: float) -> float:
        if letter not in words:
            return current
        value = words[letter] * state.unit_scale
        return value if state.absolute else current + value

    return resolve("X", state.x), resolve("Y", state.y), resolve("Z", state.z)


def _wcs_offset(wcs_offsets: dict[int, tuple[float, float, float]] | None, code: int) -> tuple[float, float, float]:
    return (wcs_offsets or {}).get(code, (0.0, 0.0, 0.0))


def _machine(point: tuple[float, float, float], state: MillState, wcs_offsets) -> tuple[float, float, float]:
    ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
    return point[0] + ox, point[1] + oy, point[2] + oz


def _execution_step(
    state: MillState,
    block,
    emitted_count: int,
    occurrence: int,
    *,
    words: tuple[tuple[str, float], ...] = (),
    signals=(),
    stop: bool = False,
    wcs_offsets=None,
) -> ExecutionStep:
    return ExecutionStep(
        source_block=block.index,
        emitted_count=emitted_count,
        unit_scale=state.unit_scale,
        x_is_diameter=False,
        absolute=state.absolute,
        stop=stop,
        words=words,
        signals=tuple(signals),
        occurrence=occurrence,
        position=_machine((state.x, state.y, state.z), state, wcs_offsets),
        active_wcs=state.active_wcs,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
    )


def _apply_pre_flow_modal_state(state: MillState, gcodes, all_m, words, *, wcs_offsets) -> None:
    """Apply state-only modal words before an M98/M99 control transfer."""
    for g in gcodes:
        if g == 20:
            state.unit_scale = 25.4
        elif g == 21:
            state.unit_scale = 1.0
        elif g in (17, 18, 19):
            state.plane = g
        elif g == 90:
            state.absolute = True
        elif g == 91:
            state.absolute = False
        elif isinstance(g, int) and 54 <= g <= 59:
            old = _wcs_offset(wcs_offsets, state.active_wcs)
            new = _wcs_offset(wcs_offsets, g)
            state.x += old[0] - new[0]
            state.y += old[1] - new[1]
            state.z += old[2] - new[2]
            state.active_wcs = g
        elif g in (40, 41, 42):
            state.cutter_comp = g
        elif g == 43:
            state.tool_length_comp = True
            if "H" in words:
                h_value = words["H"]
                state.tool_length_h = int(h_value) if float(h_value).is_integer() else None
        elif g == 49:
            state.tool_length_comp = False
            state.tool_length_h = None
        elif g == 98:
            state.return_initial = True
        elif g == 99:
            state.return_initial = False

    if 94 in gcodes:
        state.feed_mode = "per_minute"
    if 95 in gcodes:
        state.feed_mode = "per_revolution"
    if "S" in words:
        state.spindle_rpm = words["S"]
    if 5 in all_m:
        state.spindle_rpm = None
    if "F" in words:
        state.feed = words["F"] * state.unit_scale


def _motion(block, state: MillState, words, *, wcs_offsets, source_kind="motion") -> TraceMotion | None:
    end = _xyz(words, state)
    start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    end_m = _machine(end, state, wcs_offsets)
    state.x, state.y, state.z = end
    has_arc_definition = state.move in (2, 3) and any(key in words for key in ("I", "J", "K", "R"))
    if start_m == end_m and not has_arc_definition:
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end_m[0],
        end_y=end_m[1],
        end_z=end_m[2],
        radius=(words.get("R") * state.unit_scale if "R" in words else None),
        feed=(None if state.move == 0 else state.feed),
        i=(words.get("I") * state.unit_scale if "I" in words else None),
        j=(words.get("J") * state.unit_scale if "J" in words else None),
        k=(words.get("K") * state.unit_scale if "K" in words else None),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind=source_kind,
        plane=state.plane,
        cycle_generated=source_kind == "cycle",
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
    )


def _machine_coordinate_motion(block, state: MillState, words, *, wcs_offsets) -> TraceMotion | None:
    """Execute a non-modal G53 move directly in machine coordinates."""
    start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    end_m = list(start_m)
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        value = words[letter] * state.unit_scale
        end_m[index] = value if state.absolute else start_m[index] + value

    end = (end_m[0], end_m[1], end_m[2])
    ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
    state.x, state.y, state.z = end[0] - ox, end[1] - oy, end[2] - oz
    if start_m == end:
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        feed=(None if state.move == 0 else state.feed),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind="g53",
        plane=state.plane,
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
    )


def _drill(block, state: MillState, words, *, wcs_offsets) -> list[TraceMotion]:
    # Modal XY location + Z/R/Q parameters.  Logical cycle expansion is kept as
    # a small set of machine motions; no render sampling occurs here.
    out: list[TraceMotion] = []
    x, y, _ = _xyz(words, state)
    if "Z" in words:
        state.cycle_z = words["Z"] * state.unit_scale if state.absolute else state.z + words["Z"] * state.unit_scale
    if "R" in words:
        state.cycle_r = words["R"] * state.unit_scale if state.absolute else state.z + words["R"] * state.unit_scale
    if "Q" in words:
        state.cycle_q = abs(words["Q"] * state.unit_scale)
    if "F" in words:
        state.cycle_feed = words["F"] * state.unit_scale
    if state.cycle_z is None:
        return out
    r = state.cycle_r if state.cycle_r is not None else state.z
    start = (state.x, state.y, state.z)

    def add(kind: int, a, b, feed=None):
        am = _machine(a, state, wcs_offsets)
        bm = _machine(b, state, wcs_offsets)
        if am == bm:
            return
        checkpoint("generated_motions")
        out.append(
            TraceMotion(
                kind,
                am[0],
                am[2],
                bm[0],
                bm[2],
                feed=feed,
                start_y=am[1],
                end_y=bm[1],
                plane=state.plane,
                source_block=block.index,
                source_nlabel=block.nlabel,
                source_raw=block.raw,
                source_kind="cycle",
                cycle_generated=True,
                compensation_mode=state.cutter_comp,
                compensation_applied=False,
                tool=state.active_tool,
            )
        )

    add(0, start, (x, y, start[2]))
    add(0, (x, y, start[2]), (x, y, r))
    if state.cycle == 83 and state.cycle_q and state.cycle_q > 1e-12:
        direction = 1.0 if state.cycle_z > r else -1.0
        current = r
        while (state.cycle_z - current) * direction > 1e-9:
            nxt = current + direction * state.cycle_q
            if (state.cycle_z - nxt) * direction < 0:
                nxt = state.cycle_z
            require_progress(current, nxt)
            checkpoint("cycle_iterations")
            add(1, (x, y, r), (x, y, nxt), state.cycle_feed or state.feed)
            if abs(nxt - state.cycle_z) > 1e-9:
                add(0, (x, y, nxt), (x, y, r))
            current = nxt
    else:
        add(1, (x, y, r), (x, y, state.cycle_z), state.cycle_feed or state.feed)
    return_z = start[2] if state.return_initial else r
    return_move = 1 if state.cycle == 85 else 0
    add(return_move, (x, y, state.cycle_z), (x, y, return_z), state.cycle_feed or state.feed)
    state.x, state.y, state.z = x, y, return_z
    return out


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
):

    program = parse_program(source.splitlines())
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(x=home[0] - ox, y=home[1] - oy, z=home[2] - oz)
    motions: list[TraceMotion] = []
    diagnostics: list[Diagnostic] = []
    executed: list[int] = []
    steps: list[ExecutionStep] = []
    signals = []
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
        53,
        54,
        55,
        56,
        57,
        58,
        59,
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
                steps.append(_execution_step(state, block, 0, len(steps), wcs_offsets=wcs_offsets))
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
                steps.append(
                    _execution_step(
                        state,
                        block,
                        0,
                        len(steps),
                        words=evaluated,
                        signals=occurrence_signals,
                        stop=True,
                        wcs_offsets=wcs_offsets,
                    )
                )
                break

            for g in gcodes:
                if g == 43:
                    diagnostics.append(
                        Diagnostic(
                            "UNVERIFIED_TOOL_LENGTH_COMPENSATION",
                            "G43 tool-length compensation is tracked but the H offset is not applied "
                            "to fanuc_mill trace geometry",
                            "warning",
                            "unverified",
                            block.index + 1,
                            block.raw,
                        )
                    )

            if "T" in words:
                tool_value = words["T"]
                if float(tool_value).is_integer() and 1 <= int(tool_value) <= 99:
                    state.active_tool = f"T{int(tool_value)}"
                else:
                    state.active_tool = None
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
            _apply_pre_flow_modal_state(state, gcodes, codes.all_m, words, wcs_offsets=wcs_offsets)
            flow_mcode = flow_control_mcode(codes.all_m, codes.mcode)
            sub = dispatch_subprogram_flow(
                mcode=flow_mcode, words=words, pc=pc, olabel_to_index=index.olabel_to_index, call_stack=call_stack
            )
            call_stack = sub.call_stack
            if sub.handled:
                if sub.stop:
                    steps.append(
                        _execution_step(
                            state,
                            block,
                            0,
                            len(steps),
                            words=evaluated,
                            signals=occurrence_signals,
                            stop=True,
                            wcs_offsets=wcs_offsets,
                        )
                    )
                    break
                steps.append(
                    _execution_step(
                        state,
                        block,
                        0,
                        len(steps),
                        words=evaluated,
                        signals=occurrence_signals,
                        wcs_offsets=wcs_offsets,
                    )
                )
                pc = sub.next_pc
                continue

            motion_start = len(motions)

            action_g = None
            for g in gcodes:
                if g in (0, 1, 2, 3, 28, 53, 80, 81, 82, 83, 84, 85, 86):
                    action_g = g
            if action_g is not None and action_g not in (80, 81, 82, 83, 84, 85, 86):
                # Match CncKernelCli: an explicit motion/reference command ends
                # a modal drilling cycle even without a separate G80 block.
                state.cycle = 80

            for g in gcodes:
                if g in (0, 1, 2, 3):
                    state.move = g
                elif g in (80, 81, 82, 83, 84, 85, 86):
                    if g in (81, 82, 83, 84, 85, 86) and state.cycle == 80:
                        state.cycle_initial_z = state.z
                    state.cycle = g

            if 4 in gcodes:
                pass
            elif 53 in gcodes:
                m = _machine_coordinate_motion(block, state, words, wcs_offsets=wcs_offsets)
                if m:
                    checkpoint("generated_motions")
                    motions.append(m)
            elif 28 in gcodes:
                mid = _xyz(words, state)
                sm = _machine((state.x, state.y, state.z), state, wcs_offsets)
                mm = _machine(mid, state, wcs_offsets)
                if sm != mm:
                    checkpoint("generated_motions")
                    motions.append(
                        TraceMotion(
                            0,
                            sm[0],
                            sm[2],
                            mm[0],
                            mm[2],
                            start_y=sm[1],
                            end_y=mm[1],
                            plane=state.plane,
                            source_block=block.index,
                            source_nlabel=block.nlabel,
                            source_raw=block.raw,
                            source_kind="g28",
                        )
                    )
                axes = {k for k in ("X", "Y", "Z") if k in words}
                target = (
                    home[0] if "X" in axes else mm[0],
                    home[1] if "Y" in axes else mm[1],
                    home[2] if "Z" in axes else mm[2],
                )
                if mm != target:
                    checkpoint("generated_motions")
                    motions.append(
                        TraceMotion(
                            0,
                            mm[0],
                            mm[2],
                            target[0],
                            target[2],
                            start_y=mm[1],
                            end_y=target[1],
                            plane=state.plane,
                            source_block=block.index,
                            source_nlabel=block.nlabel,
                            source_raw=block.raw,
                            source_kind="g28",
                        )
                    )
                ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
                state.x, state.y, state.z = target[0] - ox, target[1] - oy, target[2] - oz
            elif state.cycle in (81, 82, 83, 84, 85, 86) and any(k in words for k in ("X", "Y", "Z", "R")):
                motions.extend(_drill(block, state, words, wcs_offsets=wcs_offsets))
            elif state.cycle == 80 and (
                any(k in words for k in ("X", "Y", "Z")) or any(g in (0, 1, 2, 3) for g in gcodes)
            ):
                m = _motion(block, state, words, wcs_offsets=wcs_offsets)
                if m:
                    checkpoint("generated_motions")
                    motions.append(m)

            if motions and (not executed or executed[-1] != block.index):
                executed.append(block.index)
            steps.append(
                _execution_step(
                    state,
                    block,
                    len(motions) - motion_start,
                    len(steps),
                    words=evaluated,
                    signals=occurrence_signals,
                    wcs_offsets=wcs_offsets,
                )
            )
            pc += 1
    except Exception as exc:
        diagnostics.append(_execution_diagnostic(exc, program))
        return ExecutionResult(False, program, tuple(instructions), (), tuple(diagnostics), tuple(executed))

    signals = tuple(signals)
    return ExecutionResult(
        not any(d.severity == "error" for d in diagnostics),
        program,
        tuple(instructions),
        tuple(motions),
        tuple(diagnostics),
        tuple(executed),
        signals,
        program_end_code(signals),
        tuple(steps),
    )
