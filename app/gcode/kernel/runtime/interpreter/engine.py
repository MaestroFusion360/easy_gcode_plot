from __future__ import annotations

# Trace execution dispatches early per block kind and control-flow opcode.
# pylint: disable=too-many-return-statements
from dataclasses import replace

from ...api.types import ExecutionEvent, ExecutionStep
from ...frontend.program import resolve_cycle_profile_indices
from ...geometry.coordinates import extended_wcs_from_gcode, programmed_wcs_id, rebase_work_position
from ...turning.cycles import adapt_cycle_emission
from ..cycles import CycleContext, apply_cycle_outcome
from ..diagnostics import modal_conflict_diagnostics, unsupported_g53_motion_diagnostic
from ..events import TOOL_CHANGE, home_return_event, main_program_location, program_start_event
from ..execution import (
    POSITION_NEUTRAL_GCODES,
    ProgramRuntime,
    apply_unit_mode,
    build_program_execution_index,
)
from ..expansion import expand_cycle_block
from .dispatch import (
    _X_AXIS_WORDS,
    _Z_AXIS_WORDS,
    dispatch_cycle_block,
    dispatch_cycle_emission,
    dispatch_g28_home,
    dispatch_g53_machine_motion,
    dispatch_motion_block,
    has_position_words,
    resolve_modal_move,
)
from .types import TraceExecutionContext, TraceRuntimeState, TurningExecutionSemantics


def build_trace_execution_context(
    *,
    program,
    initial_state: TraceRuntimeState | None = None,
) -> TraceExecutionContext:
    state = initial_state or TraceRuntimeState()
    program_start_block, program_number = main_program_location(program)

    execution_index = build_program_execution_index(program)
    contour_block_indices: set[int] = set()

    return TraceExecutionContext(
        state=state,
        runtime=ProgramRuntime(execution_index, {}, []),
        contour_block_indices=contour_block_indices,
        program_start_block=program_start_block,
        program_number=program_number,
    )


def execute_trace_context_with_steps(
    *,
    program,
    ctx: TraceExecutionContext,
    rough_cycles: list[list[object]],
    finish_cycles: list[list[object]],
    skip_optional_blocks: bool,
    semantics: TurningExecutionSemantics,
) -> tuple[list[object], list[ExecutionStep]]:
    motions: list[object] = []
    steps: list[ExecutionStep] = []
    while 0 <= ctx.pc < len(program.blocks):
        pc_before = ctx.pc
        if skip_optional_blocks and program.blocks[pc_before].optional_skip:
            ctx.pc += 1
            continue
        step_stop, step_motions = execute_trace_step(
            program=program,
            ctx=ctx,
            rough_cycles=rough_cycles,
            finish_cycles=finish_cycles,
            skip_optional_blocks=skip_optional_blocks,
            semantics=semantics,
        )
        motions.extend(step_motions)
        src_block = pc_before
        if 0 <= pc_before < len(program.blocks):
            src_block = int(program.blocks[pc_before].index)
        steps.append(
            ExecutionStep(
                source_block=src_block,
                emitted_count=len(step_motions),
                unit_scale=ctx.state.unit_scale,
                x_is_diameter=ctx.state.x_is_diameter,
                contour_definition=pc_before in (ctx.contour_block_indices or set()),
                stop=step_stop,
                words=ctx.words,
                signals=ctx.signals,
                occurrence=len(steps),
                position=(ctx.state.modal_x, 0.0, ctx.state.modal_z),
                active_wcs=ctx.state.active_wcs,
                feed_mode=ctx.state.feed_mode,
                spindle_rpm=ctx.state.spindle_rpm,
                spindle_mode=ctx.state.spindle_mode,
                surface_speed_m_min=ctx.state.surface_speed_m_min,
                spindle_limit_rpm=ctx.state.spindle_limit_rpm,
                spindle_running=ctx.state.spindle_running,
                modal_move=ctx.state.modal_move,
                variables=ctx.runtime.variable_snapshot(),
                events=ctx.events,
            )
        )
        if step_stop:
            break
    return motions, steps


def execute_trace_step(
    *,
    program,
    ctx: TraceExecutionContext,
    rough_cycles: list[list[object]],
    finish_cycles: list[list[object]],
    skip_optional_blocks: bool,
    semantics: TurningExecutionSemantics,
) -> tuple[bool, list[object]]:
    motions: list[object] = []
    blocks = program.blocks
    state = ctx.state
    runtime = ctx.runtime

    ctx.words = ()
    ctx.signals = ()
    ctx.events = ()
    block = runtime.next_block(blocks, guard_message="Source trace execution guard reached")
    event_list: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        event_list.append(program_start_event(block, ctx.program_number))
        ctx.program_started = True
    ctx.events = tuple(event_list)
    ast_node = None
    if getattr(program, "ast", None) is not None and 0 <= ctx.pc < len(program.ast.nodes):
        ast_node = program.ast.nodes[ctx.pc]

    if skip_optional_blocks and block.optional_skip:
        ctx.pc += 1
        return False, motions

    if ctx.pc in (ctx.contour_block_indices or set()):
        ctx.pc += 1
        return False, motions

    flow_dispatch = runtime.dispatch_macro(block, ctx.pc, blocks)
    if flow_dispatch.handled:
        ctx.pc = flow_dispatch.next_pc
        return False, motions

    evaluated_block = runtime.evaluate_block(block)
    words = evaluated_block.words
    if getattr(words, "errors", None):
        details = ", ".join(f"{tok.letter}{tok.expr}: {msg}" for tok, msg in words.errors)
        raise ValueError(f"Cannot evaluate CNC words at line {block.index + 1}: {block.raw}: {details}")
    ctx.words = evaluated_block.values
    codes = evaluated_block.codes
    all_g = codes.all_g
    all_m = codes.all_m
    gcode = codes.gcode

    conflict_diagnostics = modal_conflict_diagnostics(all_g, "fanuc_turn", block)
    if conflict_diagnostics:
        ctx.diagnostics.extend(conflict_diagnostics)
        ctx.pc += 1
        return False, motions

    effective_motion = resolve_modal_move(ast_node, gcode, state.modal_move)
    if 53 in all_g and effective_motion not in (0, 1):
        ctx.diagnostics.append(unsupported_g53_motion_diagnostic(block, effective_motion))
        ctx.pc += 1
        return False, motions

    g65_flow = runtime.dispatch_g65(
        block=block,
        words=words,
        codes=codes,
        pc=ctx.pc,
        program=program,
    )
    if g65_flow.dispatch.handled:
        event_list.extend(g65_flow.events)
        ctx.signals = ()
        ctx.events = tuple(event_list)
        ctx.pc = g65_flow.dispatch.next_pc
        return False, motions

    ctx.signals = evaluated_block.signals

    if 40 in all_g:
        state.compensation_mode = 40
    elif 41 in all_g:
        state.compensation_mode = 41
    elif 42 in all_g:
        state.compensation_mode = 42
    if "T" in words:
        packed_tool = abs(int(round(words["T"])))
        previous_tool = state.active_tool
        state.active_tool = f"T{packed_tool:04d}"
        event_list.append(
            ExecutionEvent(
                TOOL_CHANGE,
                block.index,
                code=state.active_tool,
                tool=state.active_tool,
                previous_tool=previous_tool,
                call_depth=len(runtime.call_stack),
            )
        )
        ctx.events = tuple(event_list)

    def tagged(items: list[object]) -> list[object]:
        return [
            replace(
                item,
                compensation_mode=state.compensation_mode,
                tool=state.active_tool,
            )
            if hasattr(item, "compensation_mode") and hasattr(item, "tool")
            else item
            for item in items
        ]

    _apply_turning_modal_state(
        state,
        all_g,
        all_m,
        words,
        semantics.try_wcs_from_gcode,
        semantics.wcs_offset,
        semantics.set_wcs_offset,
        semantics.x_value_to_diameter,
    )

    event_list.extend(_turning_reference_events(block, all_g, words, len(runtime.call_stack)))
    ctx.events = tuple(event_list)

    program_flow = runtime.dispatch_program_flow(
        codes=codes,
        words=words,
        pc=ctx.pc,
        program=program,
        block=block,
        program_number=ctx.program_number,
    )
    event_list.extend(program_flow.events)

    ctx.events = tuple(event_list)
    if program_flow.dispatch.handled:
        if program_flow.dispatch.stop:
            return True, motions
        ctx.pc = program_flow.dispatch.next_pc
        return False, motions

    # G10 programs coordinate-system data.  Its X/Z words are values for the
    # offset table and must never fall through to the current modal motion.
    # G10 contains offset data and G4 contains dwell data. Consume either
    # complete block so X/P values cannot fall through to modal motion.
    if 10 in all_g or 4 in all_g:
        ctx.pc += 1
        return False, motions

    if ctx.pc in (ctx.contour_block_indices or set()):
        ctx.pc += 1
        return False, motions

    rough_cycles, finish_cycles = expand_cycle_block(
        program, ctx.pc, words, state, variables=runtime.variables, **ctx.cycle_options
    )
    state.rough_idx = state.finish_idx = 0
    if any(g in (70, 71, 72, 73) for g in all_g) and "P" in words and "Q" in words:
        bounds = resolve_cycle_profile_indices(
            blocks, ctx.pc, int(words["P"]), int(words["Q"]), prefer_preceding=70 in all_g
        )
        if bounds is None:
            raise ValueError(f"Missing cycle P/Q contour at line {block.index + 1}")
        ctx.contour_block_indices.update(range(bounds[0], bounds[1] + 1))

    cyc = dispatch_cycle_block(
        ast_node,
        words,
        gcode,
        all_g=all_g,
        active_g90=state.active_g90_cycle,
        active_g92=state.active_g92_cycle,
        active_g94=state.active_g94_cycle,
        active_g83=state.active_g83_cycle,
        active_g84=state.active_g84_cycle,
        active_g80=state.active_g80,
    )
    state.active_g90_cycle = cyc.active_g90
    state.active_g92_cycle = cyc.active_g92
    state.active_g94_cycle = cyc.active_g94
    state.active_g83_cycle = cyc.active_g83
    state.active_g84_cycle = cyc.active_g84
    state.active_g80 = cyc.active_g80

    if cyc.is_cycle_exec:
        ced = dispatch_cycle_emission(
            is_cycle_exec=cyc.is_cycle_exec,
            use_finish_cycle=cyc.use_finish_cycle,
            rough_cycles=rough_cycles,
            finish_cycles=finish_cycles,
            rough_idx=state.rough_idx,
            finish_idx=state.finish_idx,
            modal_x=state.modal_x,
            modal_z=state.modal_z,
            source_block=block.index,
            blocks=blocks,
            to_machine_fn=semantics.to_machine,
            motion_ctor=semantics.make_motion,
            point_ctor=semantics.make_point,
        )
        cycle_context = CycleContext(
            block=block,
            words=words,
            codes=tuple(all_g),
            machine_state=state,
            runtime_state=ctx,
            modal_cycle_state=cyc,
        )
        cycle_outcome = adapt_cycle_emission(cycle_context, ced, tagged(ced.emitted_motions))
        motions.extend(cycle_outcome.motions)
        apply_cycle_outcome(state, cycle_outcome)
        ctx.pc += 1
        return False, motions

    return _execute_turning_motion(
        ast_node,
        words,
        state,
        gcode,
        all_g,
        ctx,
        semantics.emulate_g28_home,
        semantics.home_x,
        semantics.home_z,
        semantics.to_machine,
        semantics.wcs_offset,
        semantics.x_value_to_diameter,
        semantics.x_delta_to_diameter,
        semantics.make_motion,
        semantics.make_point,
        block,
        motions,
        tagged,
    )


def _apply_turning_modal_state(
    state,
    all_g,
    all_m,
    words,
    try_wcs_from_gcode_fn,
    wcs_off_fn,
    set_wcs_off_fn,
    x_value_to_diameter_fn,
):
    apply_unit_mode(state, all_g)
    if 190 in all_g:
        state.x_is_diameter = True
    if 191 in all_g:
        state.x_is_diameter = False

    _apply_turning_coordinate_state(
        state,
        all_g,
        words,
        try_wcs_from_gcode_fn,
        wcs_off_fn,
        set_wcs_off_fn,
        x_value_to_diameter_fn,
    )

    # Modal words on an M98 block are active for the called subprogram.  Apply
    # state-only words before transferring control; the source block is not
    # revisited after M99 returns.
    if 98 in all_g:
        state.feed_mode = "per_minute"
    if 99 in all_g:
        state.feed_mode = "per_revolution"
    if 50 in all_g and "S" in words:
        state.spindle_limit_rpm = words["S"]
    if 96 in all_g:
        state.spindle_mode = "css"
        if "S" in words:
            state.surface_speed_m_min = words["S"] * (0.3048 if state.unit_scale > 1.0 else 1.0)
        state.spindle_rpm = None
    elif 97 in all_g:
        state.spindle_mode = "rpm"
        if "S" in words:
            state.spindle_rpm = words["S"]
    elif "S" in words and 50 not in all_g:
        if state.spindle_mode == "css":
            state.surface_speed_m_min = words["S"] * (0.3048 if state.unit_scale > 1.0 else 1.0)
        else:
            state.spindle_rpm = words["S"]
    if 3 in all_m or 4 in all_m:
        state.spindle_running = True
    if 5 in all_m:
        state.spindle_running = False
    if "F" in words:
        state.feed = words["F"] * state.unit_scale


def _turning_reference_events(block, all_g, words, call_depth):
    events = []
    for reference_code in (28, 30):
        if reference_code in all_g:
            axes = tuple(
                axis
                for axis, addresses in (("X", _X_AXIS_WORDS), ("Z", _Z_AXIS_WORDS))
                if any(address in words for address in addresses)
            )
            events.append(home_return_event(block, f"G{reference_code}", axes, call_depth))
    return events


def _apply_turning_coordinate_state(
    state,
    all_g,
    words,
    try_wcs_from_gcode_fn,
    wcs_off_fn,
    set_wcs_off_fn,
    x_value_to_diameter_fn,
):
    """Apply G10 and WCS selection while preserving machine position."""
    for candidate in all_g:
        if candidate == 10:
            target = programmed_wcs_id(words)
            machine_x, machine_z = (
                state.modal_x + wcs_off_fn(state.active_wcs)[0],
                state.modal_z + wcs_off_fn(state.active_wcs)[1],
            )
            offset_x, offset_z = wcs_off_fn(target)
            if "X" in words:
                offset_x = x_value_to_diameter_fn(words["X"] * state.unit_scale, state.x_is_diameter)
            if "Z" in words:
                offset_z = words["Z"] * state.unit_scale
            set_wcs_off_fn(target, (offset_x, offset_z))
            if target == state.active_wcs:
                state.modal_x = machine_x - offset_x
                state.modal_z = machine_z - offset_z
            continue
        wcs_code = try_wcs_from_gcode_fn(candidate)
        if wcs_code is None:
            wcs_code = extended_wcs_from_gcode(candidate, words)
        if wcs_code is not None:
            state.modal_x, state.modal_z = rebase_work_position(
                (state.modal_x, state.modal_z),
                wcs_off_fn(state.active_wcs),
                wcs_off_fn(wcs_code),
            )
            state.active_wcs = wcs_code


def _execute_turning_motion(
    ast_node,
    words,
    state,
    gcode,
    all_g,
    ctx,
    emulate_g28_home,
    home_x,
    home_z,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
    block,
    motions,
    tagged,
):
    has_pos = has_position_words(ast_node, words)
    state.modal_move = resolve_modal_move(ast_node, gcode, state.modal_move)
    non_motion_g = gcode is not None and gcode not in (0, 1, 2, 3, 32, 33) and gcode not in POSITION_NEUTRAL_GCODES

    if gcode == 30 or (gcode == 28 and not emulate_g28_home):
        # The machine-reference coordinates are unknown without a machine
        # configuration. Mark the affected axes unknown and break the plotted
        # trace instead of joining two operations with a fictitious rapid.
        state.unknown_x_after_g28 = ("X" in words) or ("U" in words)
        state.unknown_z_after_g28 = ("Z" in words) or ("W" in words)
        state.position_unknown_reason = "g30" if gcode == 30 else "g28"
        ctx.pc += 1
        return False, motions

    if _taint_unsupported_position(state, words, gcode, has_pos, non_motion_g):
        ctx.pc += 1
        return False, motions

    reference = _dispatch_turning_reference_motion(
        all_g=all_g,
        emulate_g28_home=emulate_g28_home,
        gcode=gcode,
        modal_move=state.modal_move,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
        modal_feed=state.feed,
        unit_scale=state.unit_scale,
        x_is_diameter=state.x_is_diameter,
        home_x=home_x,
        home_z=home_z,
        to_machine_fn=to_machine_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        active_wcs=state.active_wcs,
        wcs_off_fn=wcs_off_fn,
    )
    if reference[0]:
        motions.extend(tagged(reference[3]))
        state.modal_x = reference[1]
        state.modal_z = reference[2]
        ctx.pc += 1
        return False, motions

    md = dispatch_motion_block(
        has_pos=has_pos,
        non_motion_g=non_motion_g,
        modal_move=state.modal_move,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
        modal_feed=state.feed,
        unit_scale=state.unit_scale,
        x_is_diameter=state.x_is_diameter,
        supplementary_angles=bool(ctx.cycle_options.get("supplementary_angles", False)),
        to_machine_fn=to_machine_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
    )
    if md.handled:
        if md.emitted_motion is not None:
            if state.unknown_x_after_g28 or state.unknown_z_after_g28:
                if "X" in words:
                    state.unknown_x_after_g28 = False
                if "Z" in words:
                    state.unknown_z_after_g28 = False
                if not (state.unknown_x_after_g28 or state.unknown_z_after_g28):
                    emitted = md.emitted_motion
                    motions.extend(
                        tagged(
                            [
                                motion_ctor(
                                    emitted.move,
                                    emitted.end,
                                    emitted.end,
                                    radius=emitted.radius,
                                    feed=emitted.feed,
                                    i=emitted.i,
                                    k=emitted.k,
                                    source_block=emitted.source_block,
                                    source_nlabel=emitted.source_nlabel,
                                    source_raw=emitted.source_raw,
                                    source_kind=(
                                        "reference_resume"
                                        if state.position_unknown_reason in {"g28", "g30"}
                                        else "position_resume"
                                    ),
                                )
                            ]
                        )
                    )
                    state.position_unknown_reason = None
            else:
                motions.extend(tagged([md.emitted_motion]))
        state.modal_x = md.new_modal_x
        state.modal_z = md.new_modal_z
    ctx.pc += 1
    return False, motions


def _taint_unsupported_position(state, words, gcode, has_pos, non_motion_g) -> bool:
    """Fail closed for an unmodeled position-bearing turning command."""
    if not non_motion_g or not has_pos or gcode in (28, 30):
        return False
    state.unknown_x_after_g28 = ("X" in words) or ("U" in words)
    state.unknown_z_after_g28 = ("Z" in words) or ("W" in words)
    state.position_unknown_reason = "unsupported"
    return True


def _dispatch_turning_reference_motion(
    *,
    all_g,
    emulate_g28_home,
    gcode,
    modal_move,
    words,
    modal_x,
    modal_z,
    modal_feed,
    unit_scale,
    x_is_diameter,
    home_x,
    home_z,
    to_machine_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
    source_block,
    source_nlabel,
    source_raw,
    active_wcs,
    wcs_off_fn,
):
    """Dispatch non-modal G53 or configured G28 through one trace contract."""
    g53 = dispatch_g53_machine_motion(
        enabled=53 in all_g,
        modal_move=modal_move,
        words=words,
        modal_x=modal_x,
        modal_z=modal_z,
        modal_feed=modal_feed,
        unit_scale=unit_scale,
        x_is_diameter=x_is_diameter,
        to_machine_fn=to_machine_fn,
        wcs_off_fn=wcs_off_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=source_block,
        source_nlabel=source_nlabel,
        source_raw=source_raw,
        active_wcs=active_wcs,
    )
    if g53.handled:
        emitted = [] if g53.emitted_motion is None else [g53.emitted_motion]
        return True, g53.new_modal_x, g53.new_modal_z, emitted

    g28 = dispatch_g28_home(
        emulate_g28_home=emulate_g28_home,
        gcode=gcode,
        words=words,
        modal_x=modal_x,
        modal_z=modal_z,
        unit_scale=unit_scale,
        x_is_diameter=x_is_diameter,
        home_x=home_x,
        home_z=home_z,
        to_machine_fn=to_machine_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=source_block,
        source_nlabel=source_nlabel,
        source_raw=source_raw,
        active_wcs=active_wcs,
        wcs_off_fn=wcs_off_fn,
    )
    return g28.handled, g28.new_modal_x, g28.new_modal_z, g28.emitted_motions
