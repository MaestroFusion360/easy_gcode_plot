"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

from dataclasses import replace

from app.native import native_symbol

from ..frontend.ast import SinumerikFlowAstNode
from ..frontend.program import parse_program
from ..frontend.sinumerik import parse_sinumerik_program
from ..machine.cycles import CycleContext, apply_cycle_outcome
from ..machine.events import main_program_location, program_start_event
from ..machine.execution import ProgramRuntime, resolve_program_tools, semantic_instructions
from ..resources import SemanticError
from ..types import Diagnostic, ExecutionEvent, MachineSignal, TraceMotion
from .block import _BlockAction, _BlockOutcome, _MillingExecutionContext, _PreparedMillingBlock
from .controller import controller_capability_gate
from .cycles.sinumerik import execute_native_cycle
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic
from .kinematics import MachineKinematics, effective_orientation, kinematics_snapshot, rotary_limit_violations
from .motion import _emit_milling_motions
from .policy import (
    MILLING_RECOGNIZED_G_CODES,
    MILLING_RECOGNIZED_M_CODES,
    _diagnose_unknown_milling_codes,
    _rotary_index_error,
    _validate_boring_tapping_configuration,
    _validate_g73_retract_distance,
    _validate_g83_clearance,
    _validate_milling_block,
)
from .result import MillingOutput
from .sinumerik_flow import build_native_loop_maps, build_native_repeat_maps, native_flow_destination
from .sinumerik_native import (
    apply_native_declaration,
    apply_native_tcp_edge,
    evaluate_native_block,
    native_dc_diagnostics,
    native_edge_diagnostics,
    native_ignored_mode_warnings,
    native_operation_code,
)
from .state import MillState, _activate_tcp, _apply_pre_flow_modal_state, _cancel_tcp, _execution_step, _wcs_offset

_execute_simple_blocks = native_symbol("executor", "execute_simple_blocks")


def _milling_spindle_signals(block, words, mcodes) -> tuple[MachineSignal, ...]:
    signals = []
    for code, kind in ((19, "spindle_orient"), (29, "rigid_tapping_prepare")):
        if code in mcodes:
            signals.append(MachineSignal(kind, block.index, f"M{code}", words.get("S")))
    return tuple(signals)


def _finalize_milling_block(
    ctx,
    block,
    outcome,
    motions,
    diagnostics,
    executed,
    steps,
    signals,
    events,
) -> bool:
    """Commit one block exactly once and apply its control-flow action."""
    diagnostics.extend(outcome.diagnostics)
    motions.extend(outcome.motions)
    signals.extend(outcome.signals)
    events.extend(outcome.events)
    if outcome.motions and (not executed or executed[-1] != block.index):
        executed.append(block.index)
    steps.append(
        _execution_step(
            ctx.state,
            block,
            len(outcome.motions),
            len(steps),
            words=outcome.words,
            signals=outcome.signals,
            events=outcome.events,
            stop=outcome.action is _BlockAction.STOP,
            wcs_offsets=ctx.wcs_offsets,
            variables=ctx.runtime.variable_snapshot(),
        )
    )
    if outcome.action is _BlockAction.STOP:
        return True
    if outcome.action is _BlockAction.JUMP:
        if outcome.next_pc is None:
            raise RuntimeError("Jump outcome requires a destination")
        ctx.runtime.jump(outcome.next_pc)
    else:
        ctx.runtime.advance()
    return False


def _gate_milling_block(ctx, block, occurrence_events, evaluated_block=None):
    normalized, diagnostic, switch = controller_capability_gate(ctx.runtime, block, evaluated_block, state=ctx.state)
    if ctx.source_dialect == "sinumerik":
        ctx.state.source_arc_type = 1
    if diagnostic is not None:
        return normalized, _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(diagnostic,),
            words=normalized.values if normalized is not None else (),
        )
    if switch is not None:
        occurrence_events.append(
            ExecutionEvent(
                "SINUMERIK_ISO_MODE" if switch == 291 else "SINUMERIK_SIEMENS_MODE",
                block.index,
                code=f"G{switch}",
            )
        )
        return normalized, _BlockOutcome(events=tuple(occurrence_events), words=normalized.values)
    if normalized is not None and ctx.runtime.controller_mode == "sinumerik_native":
        rotary_start_angles = dict(ctx.state.rotary_angles)
        code = native_operation_code(block)
        if code is not None:
            occurrence_events.append(ExecutionEvent("SINUMERIK_NATIVE_OPERATION", block.index, code=code))
        if apply_native_declaration(block, normalized, ctx.state, occurrence_events):
            return normalized, _BlockOutcome(
                events=tuple(occurrence_events),
                words=normalized.values,
                diagnostics=tuple(
                    native_ignored_mode_warnings(block)
                    + _rotary_limit_diagnostics(ctx.state, block, rotary_start_angles)
                ),
            )
    return normalized, None


def _finish_milling_block(ctx, block, prepared: _PreparedMillingBlock, occurrence_events):
    emitted: list[TraceMotion] = []
    cycle = execute_native_cycle(
        CycleContext(block, prepared.words, prepared.gcodes, ctx.state, coordinate_context=ctx.wcs_offsets)
    )
    if cycle.handled:
        apply_cycle_outcome(ctx.state, cycle)
        emitted.extend(cycle.motions)
        occurrence_events.extend(cycle.events)
        cycle_signals = cycle.signals
    else:
        cycle_signals = _emit_milling_motions(
            block,
            ctx.state,
            prepared.words,
            prepared.gcodes,
            emitted,
            ctx.home,
            ctx.wcs_offsets,
            rotary_start_angles=prepared.rotary_start_angles,
            events=occurrence_events,
            call_depth=len(ctx.runtime.call_stack),
        )
    if 43.4 in prepared.gcodes:
        _activate_tcp(ctx.state)
    if ctx.state.kinematics is not None:
        tool_orientation = effective_orientation(ctx.state.kinematics, ctx.state.rotary_angles)
        emitted = [replace(motion, tool_orientation=tool_orientation) for motion in emitted]
    elif ctx.state.twp.active and ctx.state.twp.tool_axis_control:
        emitted = [replace(motion, tool_orientation=ctx.state.twp.orientation) for motion in emitted]
    return _BlockOutcome(
        motions=tuple(emitted),
        events=tuple(occurrence_events),
        signals=prepared.signals + cycle_signals,
        diagnostics=prepared.diagnostics,
        words=prepared.evaluated,
    )


def _rotary_limit_diagnostics(state, block, start_angles):
    return [
        Diagnostic(
            code="ROTARY_AXIS_LIMIT_EXCEEDED",
            message=(
                f"{address} angle {value:g} exceeds [{minimum:g}, {maximum:g}] degrees "
                f'for profile "{state.kinematics.name}"'
            ),
            severity="warning",
            status="unverified",
            line=block.index + 1,
            raw=block.raw,
        )
        for address, value, minimum, maximum in rotary_limit_violations(state.kinematics, state.rotary_angles)
        if value != start_angles.get(address, 0.0)
    ]


def _prepare_milling_block_state(ctx, block, evaluated_block, occurrence_events):
    words = evaluated_block.words
    early_outcome = _validate_milling_block(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome, None

    gcodes = evaluated_block.codes.all_g
    evaluated = evaluated_block.values
    signals = evaluated_block.signals + _milling_spindle_signals(block, words, evaluated_block.codes.all_m)
    diagnostics: list[Diagnostic] = (
        native_ignored_mode_warnings(block)
        + native_edge_diagnostics(block, words)
        + native_dc_diagnostics(block, ctx.state)
        if ctx.runtime.controller_mode == "sinumerik_native"
        else []
    )
    early_outcome = _diagnose_unknown_milling_codes(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None

    rotary_start_angles = dict(ctx.state.rotary_angles)
    early_outcome = _apply_rotary_index(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is None:
        early_outcome = _apply_milling_block_state(ctx, block, evaluated_block, occurrence_events, diagnostics)
    limit_diagnostics = _rotary_limit_diagnostics(ctx.state, block, rotary_start_angles)
    if early_outcome is not None:
        return replace(early_outcome, diagnostics=early_outcome.diagnostics + tuple(limit_diagnostics)), None

    diagnostics.extend(limit_diagnostics)
    early_outcome = _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None
    return None, _PreparedMillingBlock(words, evaluated, gcodes, rotary_start_angles, signals, tuple(diagnostics))


def _apply_native_feed(block, state, words):
    if block.native_syntax is not None:
        from .sinumerik_feed import apply_native_feed_state  # pylint: disable=import-outside-toplevel

        apply_native_feed_state(block, state, words)


def _append_milling_state_events(
    ctx,
    block,
    codes,
    occurrence_events,
    *,
    was_twp_active,
    was_tcp_active,
    old_rotary_angles,
):
    if 68.2 in codes.all_g:
        occurrence_events.append(
            ExecutionEvent(
                "TILTED_WORK_PLANE_ON",
                block.index,
                twp_origin=ctx.state.twp.origin,
                twp_angles=ctx.state.twp.angles,
                twp_orientation=ctx.state.twp.orientation,
            )
        )

    if 53.1 in codes.all_g:
        occurrence_events.append(
            ExecutionEvent(
                "TOOL_AXIS_ORIENT",
                block.index,
                twp_origin=ctx.state.twp.origin,
                twp_angles=ctx.state.twp.angles,
                twp_orientation=ctx.state.twp.orientation,
                old_abc=old_rotary_angles,
                new_abc=tuple(ctx.state.rotary_angles[axis] for axis in ("A", "B", "C")),
                kinematics_profile=ctx.state.kinematics.id,
            )
        )

    if 69 in codes.all_g and was_twp_active:
        occurrence_events.append(ExecutionEvent("TILTED_WORK_PLANE_OFF", block.index))

    if 43.4 in codes.all_g:
        if not was_tcp_active:
            occurrence_events.append(
                ExecutionEvent(
                    "TCP_CONTROL_ON",
                    block.index,
                    code="G43.4",
                    tool=ctx.state.active_tool,
                    length_offset=ctx.state.tool_length_h,
                    kinematics_profile=(ctx.state.kinematics.id if ctx.state.kinematics else None),
                )
            )
    elif was_tcp_active and not ctx.state.tcp_control:
        occurrence_events.append(
            ExecutionEvent("TCP_CONTROL_OFF", block.index, code="G49" if 49 in codes.all_g else "G43")
        )


def _resolve_unknown_milling_axes(state, words):
    if not state.absolute:
        return

    # Explicit absolute positions also update axes recovered in earlier blocks.
    for letter in ("X", "Y", "Z"):
        if letter not in words:
            continue

        setattr(state, letter.lower(), words[letter] * state.unit_scale)
        state.unknown_axes.discard(letter)


def _apply_milling_block_state(
    ctx,
    block,
    evaluated_block,
    occurrence_events,
    block_diagnostics,
):
    """Apply tool/modal state and return early while position remains unknown."""
    words = evaluated_block.words
    codes = evaluated_block.codes

    _apply_milling_tool_change(
        block,
        ctx.state,
        words,
        codes,
        block_diagnostics,
        occurrence_events,
        ctx.runtime.call_stack,
    )

    was_twp_active = ctx.state.twp.active
    was_tcp_active = ctx.state.tcp_control
    old_rotary_angles = tuple(ctx.state.rotary_angles[axis] for axis in ("A", "B", "C"))

    _apply_pre_flow_modal_state(
        ctx.state,
        codes.all_g,
        codes.all_m,
        words,
        wcs_offsets=ctx.wcs_offsets,
        block_index=block.index,
    )
    _apply_native_feed(block, ctx.state, words)
    if any(g in (0, 1, 2, 3) for g in codes.all_g):
        ctx.state.cip_mode = False
    if block.native_syntax is not None and block.native_syntax.cip:
        ctx.state.cip_mode = True
    apply_native_tcp_edge(block, words, ctx.state)

    _append_milling_state_events(
        ctx,
        block,
        codes,
        occurrence_events,
        was_twp_active=was_twp_active,
        was_tcp_active=was_tcp_active,
        old_rotary_angles=old_rotary_angles,
    )

    if not ctx.state.unknown_axes:
        return None

    _resolve_unknown_milling_axes(ctx.state, words)

    return _BlockOutcome(
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, block_diagnostics):
    codes = evaluated_block.codes
    if ctx.runtime.controller_mode != "fanuc":
        # M98 is not a modeled SINUMERIK subprogram call. Warn and ignore it,
        # preserving program-end semantics even when M98 shares an end block.
        codes = replace(codes, all_m=tuple(code for code in codes.all_m if code != 98), mcode=None)
        if not any(code in (2, 30, 99) for code in codes.all_m):
            return None
    program_flow = ctx.runtime.dispatch_program_flow(
        codes=codes,
        words=evaluated_block.words,
        pc=ctx.runtime.pc,
        program=ctx.program,
        block=block,
        program_number=ctx.program_number,
    )
    occurrence_events.extend(program_flow.events)
    if not program_flow.dispatch.handled:
        return None
    action = _BlockAction.STOP if program_flow.dispatch.stop else _BlockAction.JUMP
    return _BlockOutcome(
        action=action,
        next_pc=program_flow.dispatch.next_pc,
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _cancel_tcp_before_index(state, block, gcodes, events):
    """Rebase the tip at the old rotary position before a cancellation index."""
    if state.tcp_control and any(g in (43, 49) for g in gcodes):
        _cancel_tcp(state)
        events.append(ExecutionEvent("TCP_CONTROL_OFF", block.index))


def _apply_rotary_index(ctx, block, evaluated_block, occurrence_events) -> _BlockOutcome | None:
    words = evaluated_block.words
    codes = evaluated_block.codes
    gcodes = codes.all_g
    rotary = tuple(axis for axis in ("A", "B", "C") if axis in words)
    if not rotary or 65 in gcodes:
        return None
    state = ctx.state
    supa = block.native_syntax is not None and block.native_syntax.supa
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    if supa:
        absolute = True
    targets = {
        axis: 0.0
        if 28 in gcodes
        else float(words[axis])
        if absolute
        else state.rotary_angles[axis] + float(words[axis])
        for axis in rotary
    }
    changed = tuple(axis for axis in rotary if targets[axis] != state.rotary_angles[axis])
    if supa and (state.kinematics is None or any(axis not in state.kinematics.addresses for axis in rotary)):
        changed = rotary
    if not changed and state.kinematics is not None and set(rotary) <= state.kinematics.addresses:
        return None
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    continuous_c = (
        state.kinematics is not None
        and state.kinematics.continuous_c_table
        and changed == ("C",)
        and 28 not in gcodes
        and 53 not in gcodes
        and move in (0, 1)
    )
    tcp_motion = (
        state.tcp_control
        and not any(g in (43, 49) for g in gcodes)
        and state.kinematics is not None
        and state.kinematics.tcp_table_supported
        and 28 not in gcodes
        and 53 not in gcodes
        and move in (0, 1, 2, 3)
    )
    machine_rapid = 28 in gcodes or 53 in gcodes and move == 0
    code, message = _rotary_index_error(state, words, gcodes, rotary, move, continuous_c, tcp_motion, machine_rapid)
    if code is not None:
        return _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(Diagnostic(code, message, "error", "unsupported", block.index + 1, block.raw),),
            words=evaluated_block.values,
        )
    _cancel_tcp_before_index(state, block, gcodes, occurrence_events)
    old = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
    # Indexed tables retain programmed XYZ, as in 1.7.0, including
    # five-axis profiles with TCP off. Rebasing to the previous display
    # point puts the next approach on the opposite side of the workpiece.
    # Active TCP keeps its existing fixed-tip semantics in _machine.
    for axis in changed:
        state.rotary_angles[axis] = targets[axis]
    new = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
    occurrence_events.append(
        ExecutionEvent(
            "ROTARY_MOTION" if (continuous_c or tcp_motion) else "ROTARY_INDEX",
            block.index,
            axes=changed,
            old_abc=old,
            new_abc=new,
            kinematics_profile=state.kinematics.id,
        )
    )
    return None


def _dispatch_milling_macro(ctx, block, occurrence_events):
    if ctx.runtime.controller_mode == "sinumerik_native":
        node = ctx.program.ast.nodes[ctx.runtime.pc]
        if isinstance(node, SinumerikFlowAstNode):
            return _BlockOutcome(
                action=_BlockAction.JUMP,
                next_pc=native_flow_destination(
                    node, ctx.runtime.pc, ctx.program, ctx.state, ctx.state.native_loop_pairs
                ),
                events=tuple(occurrence_events),
            )
        return None
    flow = ctx.runtime.dispatch_macro(block, ctx.runtime.pc, ctx.program.blocks)
    if flow.handled:
        return _BlockOutcome(
            action=_BlockAction.JUMP,
            next_pc=flow.next_pc,
            events=tuple(occurrence_events),
        )

    return None


def _execute_milling_block(ctx: _MillingExecutionContext, block) -> _BlockOutcome:
    """Run the named milling phases without committing PC or ExecutionStep."""
    occurrence_events: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        occurrence_events.append(program_start_event(block, ctx.program_number))
        ctx.program_started = True

    _, early_outcome = _gate_milling_block(ctx, block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    early_outcome = _dispatch_milling_macro(ctx, block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    # Phase 2: evaluate the block once and establish its modal codes.
    evaluated_block = (
        evaluate_native_block(block, ctx.state)
        if ctx.runtime.controller_mode == "sinumerik_native" and block.native_syntax is not None
        else ctx.runtime.evaluate_block(block)
    )
    words = evaluated_block.words
    if words.errors:
        token, error = words.errors[0]
        raise ValueError(f"{error} at line {block.index + 1}: {block.raw} ({token.letter}{token.expr})") from error

    evaluated_block, early_outcome = _gate_milling_block(ctx, block, occurrence_events, evaluated_block)
    if early_outcome is not None:
        return early_outcome

    # Phases 3Р Р†Р вЂљРІР‚Сљ5 validate and apply state before program-flow transfer.
    ctx.state.native_spindle_semantics = ctx.runtime.controller_mode == "sinumerik_native"
    early_outcome, prepared = _prepare_milling_block_state(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome
    assert prepared is not None

    # Phase 6: execute geometric semantics and return everything for one commit.
    return _finish_milling_block(ctx, block, prepared, occurrence_events)


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
    g73_retract_distance: float = 1.0,
    g83_clearance: float = 1.0,
    boring_shift_direction: tuple[float, float, float] = (-1.0, 0.0, 0.0),
    tapping_retract_distance: float = 1.0,
    tapping_full_retract: bool = False,
    include_instructions: bool = True,
    kinematics: MachineKinematics | None = None,
    source_dialect: str = "fanuc",
    sinumerik_840d_sl: bool = True,
    tool_resolver=None,
    parsed_program=None,
):

    definition, fingerprint = kinematics_snapshot(kinematics)
    program = parsed_program
    if program is None:
        program = parse_sinumerik_program(source) if source_dialect == "sinumerik" else parse_program(source)
    tools = resolve_program_tools(program, None, tool_resolver)
    program_start_block, program_number = main_program_location(program)
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        native_feed_scale=default_unit_scale,
        tools=tools or {},
        kinematics=kinematics,
        x=home[0] - ox,
        y=home[1] - oy,
        z=home[2] - oz,
        unit_scale=float(default_unit_scale),
        source_arc_type=1 if source_dialect == "sinumerik" else None,
        g73_retract_distance=float(g73_retract_distance),
        g83_clearance=float(g83_clearance),
        boring_shift_direction=tuple(boring_shift_direction),
        tapping_retract_distance=float(tapping_retract_distance),
        tapping_full_retract=bool(tapping_full_retract),
        sinumerik_840d_sl=sinumerik_840d_sl,
    )
    output = MillingOutput()
    motions, diagnostics, executed = output.motions, output.diagnostics, output.executed
    steps, signals, events = output.steps, output.signals, output.events
    runtime = ProgramRuntime.create(program)
    runtime.controller_mode = "sinumerik_native" if source_dialect == "sinumerik" else "fanuc"
    instructions = semantic_instructions(program) if include_instructions else ()
    ctx = _MillingExecutionContext(
        program=program,
        state=state,
        runtime=runtime,
        home=home,
        wcs_offsets=wcs_offsets,
        program_start_block=program_start_block,
        program_number=program_number,
        source_dialect=source_dialect,
    )
    contains_rotary = source_dialect == "fanuc" and any(
        any(token.letter in ("A", "B", "C") for token in block.parsed_words) for block in program.blocks
    )
    stopped_due_error = False

    try:
        _validate_g73_retract_distance(state.g73_retract_distance)
        _validate_boring_tapping_configuration(state)
        if source_dialect == "sinumerik":
            state.native_loop_pairs = build_native_loop_maps(program)
            state.native_repeat_ranges = build_native_repeat_maps(program)
        _validate_g83_clearance(state.g83_clearance)
        while 0 <= runtime.pc < len(program.blocks):
            simple_blocks_available = (
                not contains_rotary
                and state.spindle_mode != "css"
                and not state.twp.active
                and not state.tcp_control
                and kinematics is None
                and _execute_simple_blocks is not None
                and (ctx.program_started or runtime.pc != ctx.program_start_block)
            )
            if simple_blocks_available and _execute_simple_blocks(
                program, runtime, state, motions, executed, steps, wcs_offsets
            ):
                continue
            block = runtime.next_block(program.blocks)
            if block.optional_skip and skip_optional_blocks:
                runtime.advance()
                continue
            try:
                outcome = _execute_milling_block(ctx, block)
            except SemanticError as error:
                raise SemanticError(
                    error.code,
                    f"{error} at line {block.index + 1}",
                    error.status,
                    line=error.line or block.index + 1,
                    raw=error.raw or block.raw,
                ) from error
            if _finalize_milling_block(
                ctx,
                block,
                outcome,
                motions,
                diagnostics,
                executed,
                steps,
                signals,
                events,
            ):
                stopped_due_error = any(d.severity == "error" for d in outcome.diagnostics)
                break
    except Exception as exc:
        if isinstance(exc, SemanticError) and " at line " not in str(exc) and "line " not in str(exc):
            line = program.blocks[min(runtime.pc, len(program.blocks) - 1)].index + 1 if program.blocks else 1
            exc = SemanticError(exc.code, f"{exc} at line {line}", exc.status, line=line)
        diagnostics.append(_execution_diagnostic(exc, program))
        return output.result(ctx, instructions, definition, fingerprint, failed=True)

    return output.result(ctx, instructions, definition, fingerprint, stopped_due_error=stopped_due_error)


__all__ = ["MILLING_RECOGNIZED_G_CODES", "MILLING_RECOGNIZED_M_CODES"]
