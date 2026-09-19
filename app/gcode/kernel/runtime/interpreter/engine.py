from __future__ import annotations

# Trace execution dispatches early per block kind and control-flow opcode.
# pylint: disable=too-many-return-statements
from dataclasses import replace

from ...api.resources import checkpoint
from ...api.types import ExecutionEvent
from ...frontend.program import resolve_cycle_profile_indices
from ..events import (
    HOME_RETURN,
    PROGRAM_END,
    PROGRAM_START,
    SUBPROGRAM_END,
    SUBPROGRAM_START,
    TOOL_CHANGE,
    main_program_location,
    subprogram_number,
)
from ..execution import (
    POSITION_NEUTRAL_GCODES,
    build_program_execution_index,
    classify_block_codes,
    dispatch_macro_flow,
    dispatch_subprogram_flow,
    flow_control_mcode,
)
from ..expansion import expand_cycle_block
from ..signals import signals_for_words
from .dispatch import (
    _X_AXIS_WORDS,
    _Z_AXIS_WORDS,
    dispatch_cycle_block,
    dispatch_cycle_emission,
    dispatch_g28_home,
    dispatch_motion_block,
    has_position_words,
    resolve_modal_move,
)
from .types import TraceExecutionContext, TraceRuntimeState, TraceStepSnapshot


def build_trace_execution_context(
    *,
    program,
    eval_words_fn,
    initial_state: TraceRuntimeState | None = None,
) -> TraceExecutionContext:
    state = initial_state or TraceRuntimeState()
    program_start_block, program_number = main_program_location(program)

    execution_index = build_program_execution_index(program)
    label_to_index = execution_index.label_to_index
    olabel_to_index = execution_index.olabel_to_index

    contour_block_indices: set[int] = set()

    while_to_end = execution_index.while_to_end
    end_to_while = execution_index.end_to_while

    return TraceExecutionContext(
        state=state,
        pc=0,
        guard=0,
        call_stack=[],
        max_call_depth=64,
        label_to_index=label_to_index,
        olabel_to_index=olabel_to_index,
        contour_block_indices=contour_block_indices,
        while_to_end=while_to_end,
        end_to_while=end_to_while,
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
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
) -> tuple[list[object], list[TraceStepSnapshot]]:
    motions: list[object] = []
    steps: list[TraceStepSnapshot] = []
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
            emulate_g28_home=emulate_g28_home,
            x_is_diameter=x_is_diameter,
            home_x=home_x,
            home_z=home_z,
            eval_words_fn=eval_words_fn,
            try_wcs_from_gcode_fn=try_wcs_from_gcode_fn,
            to_machine_fn=to_machine_fn,
            wcs_off_fn=wcs_off_fn,
            x_value_to_diameter_fn=x_value_to_diameter_fn,
            x_delta_to_diameter_fn=x_delta_to_diameter_fn,
            motion_ctor=motion_ctor,
            point_ctor=point_ctor,
        )
        motions.extend(step_motions)
        src_block = pc_before
        src_nlabel = None
        if 0 <= pc_before < len(program.blocks):
            src_block = int(program.blocks[pc_before].index)
            src_nlabel = program.blocks[pc_before].nlabel
        steps.append(
            TraceStepSnapshot(
                pc_before=pc_before,
                pc_after=ctx.pc,
                source_block=src_block,
                source_nlabel=src_nlabel,
                stop=step_stop,
                emitted_count=len(step_motions),
                modal_x=ctx.state.modal_x,
                modal_z=ctx.state.modal_z,
                modal_move=ctx.state.modal_move,
                unit_scale=ctx.state.unit_scale,
                active_wcs=ctx.state.active_wcs,
                x_is_diameter=ctx.state.x_is_diameter,
                contour_definition=pc_before in (ctx.contour_block_indices or set()),
                variables=tuple(sorted((ctx.state.vars_map or {}).items())),
                words=ctx.words,
                signals=ctx.signals,
                events=ctx.events,
                feed_mode=ctx.state.feed_mode,
                spindle_rpm=ctx.state.spindle_rpm,
                spindle_mode=ctx.state.spindle_mode,
                surface_speed_m_min=ctx.state.surface_speed_m_min,
                spindle_limit_rpm=ctx.state.spindle_limit_rpm,
                spindle_running=ctx.state.spindle_running,
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
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
) -> tuple[bool, list[object]]:
    motions: list[object] = []
    blocks = program.blocks
    state = ctx.state

    checkpoint("executed_blocks")
    ctx.words = ()
    ctx.signals = ()
    ctx.events = ()
    ctx.guard += 1
    if ctx.guard > 500000:
        raise RuntimeError("Source trace execution guard reached")

    block = blocks[ctx.pc]
    event_list: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        event_list.append(
            ExecutionEvent(
                PROGRAM_START,
                block.index,
                code=(f"O{ctx.program_number}" if ctx.program_number is not None else None),
                program_number=ctx.program_number,
            )
        )
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

    vars_map = state.vars_map if state.vars_map is not None else {}
    flow_dispatch = dispatch_macro_flow(
        block=block,
        pc=ctx.pc,
        blocks=blocks,
        variables=vars_map,
        label_to_index=ctx.label_to_index or {},
        while_to_end=ctx.while_to_end or {},
        end_to_while=ctx.end_to_while or {},
    )
    if flow_dispatch.handled:
        ctx.pc = flow_dispatch.next_pc
        return False, motions

    words = eval_words_fn(block.parsed_words, vars_map)
    if getattr(words, "errors", None):
        details = ", ".join(f"{tok.letter}{tok.expr}: {msg}" for tok, msg in words.errors)
        raise ValueError(f"Cannot evaluate CNC words at line {block.index + 1}: {block.raw}: {details}")
    ctx.words = tuple((k, v) for k in words for v in words.all(k))
    ctx.signals = signals_for_words(block.index, words)
    codes = classify_block_codes(words)
    all_g = codes.all_g
    all_m = codes.all_m
    gcode = codes.gcode
    mcode = codes.mcode

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
                call_depth=len(ctx.call_stack or ()),
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

    _apply_turning_modal_state(state, all_g, all_m, words, try_wcs_from_gcode_fn, wcs_off_fn)

    for reference_code in (28, 30):
        if reference_code in all_g:
            axes = tuple(
                axis
                for axis, addresses in (("X", _X_AXIS_WORDS), ("Z", _Z_AXIS_WORDS))
                if any(address in words for address in addresses)
            )
            event_list.append(
                ExecutionEvent(
                    HOME_RETURN,
                    block.index,
                    code=f"G{reference_code}",
                    axes=axes,
                    call_depth=len(ctx.call_stack or ()),
                )
            )
    ctx.events = tuple(event_list)

    flow_mcode = flow_control_mcode(all_m, mcode)
    call_stack_before = list(ctx.call_stack or [])
    sub_flow = dispatch_subprogram_flow(
        mcode=flow_mcode,
        words=words,
        pc=ctx.pc,
        olabel_to_index=ctx.olabel_to_index or {},
        call_stack=ctx.call_stack or [],
        max_call_depth=ctx.max_call_depth,
    )
    ctx.call_stack = sub_flow.call_stack
    _record_turning_flow_events(flow_mcode, sub_flow, words, program, block, ctx, call_stack_before, event_list)

    ctx.events = tuple(event_list)
    if sub_flow.handled:
        if sub_flow.stop:
            return True, motions
        ctx.pc = sub_flow.next_pc
        return False, motions

    # G4 is non-modal dwell: X is seconds and P is milliseconds, not motion.
    # Consume the complete block before modal-motion dispatch so G0/G1 state
    # cannot reinterpret the dwell value as an X coordinate.
    if 4 in all_g:
        ctx.pc += 1
        return False, motions

    if ctx.pc in (ctx.contour_block_indices or set()):
        ctx.pc += 1
        return False, motions

    cs = ctx.cycle_state
    cs.modal_x, cs.modal_z = state.modal_x, state.modal_z
    cs.modal_feed, cs.unit_scale = state.modal_feed, state.unit_scale
    cs.x_is_diameter = state.x_is_diameter
    cs.variables = state.vars_map
    cs.compensation_mode, cs.active_tool = state.compensation_mode, state.active_tool
    rough_cycles, finish_cycles = expand_cycle_block(program, ctx.pc, words, cs, **ctx.cycle_options)
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
        active_g90=state.active_g90,
        active_g92=state.active_g92,
        active_g94=state.active_g94,
        active_g83=state.active_g83,
        active_g84=state.active_g84,
        active_g80=state.active_g80,
    )
    state.active_g90 = cyc.active_g90
    state.active_g92 = cyc.active_g92
    state.active_g94 = cyc.active_g94
    state.active_g83 = cyc.active_g83
    state.active_g84 = cyc.active_g84
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
            to_machine_fn=to_machine_fn,
            motion_ctor=motion_ctor,
            point_ctor=point_ctor,
        )
        motions.extend(tagged(ced.emitted_motions))
        state.modal_x = ced.new_modal_x
        state.modal_z = ced.new_modal_z
        state.rough_idx = ced.new_rough_idx
        state.finish_idx = ced.new_finish_idx
        ctx.pc += 1
        return False, motions

    return _execute_turning_motion(
        ast_node,
        words,
        state,
        gcode,
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
    )


def _apply_turning_modal_state(state, all_g, all_m, words, try_wcs_from_gcode_fn, wcs_off_fn):
    for candidate in all_g:
        wcs_code = try_wcs_from_gcode_fn(candidate)
        if wcs_code is not None:
            old_x, old_z = wcs_off_fn(state.active_wcs)
            new_x, new_z = wcs_off_fn(wcs_code)
            state.modal_x += old_x - new_x
            state.modal_z += old_z - new_z
            state.active_wcs = wcs_code

    # Modal words on an M98 block are active for the called subprogram.  Apply
    # state-only words before transferring control; the source block is not
    # revisited after M99 returns.
    if 20 in all_g:
        state.unit_scale = 25.4
    if 21 in all_g:
        state.unit_scale = 1.0
    if 190 in all_g:
        state.x_is_diameter = True
    if 191 in all_g:
        state.x_is_diameter = False
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
        state.modal_feed = words["F"] * state.unit_scale


def _record_turning_flow_events(flow_mcode, sub_flow, words, program, block, ctx, call_stack_before, event_list):
    if flow_mcode == 98 and sub_flow.handled and not sub_flow.stop:
        target_block = sub_flow.next_pc
        event_list.append(
            ExecutionEvent(
                SUBPROGRAM_START,
                block.index,
                code=(f"O{int(words['P'])}" if "P" in words else None),
                program_number=subprogram_number(program, target_block),
                call_depth=len(sub_flow.call_stack),
                target_block=target_block,
            )
        )
    elif flow_mcode == 99 and sub_flow.handled:
        if call_stack_before:
            current_target = call_stack_before[-1][1]
            current_program = subprogram_number(program, current_target)
            event_list.append(
                ExecutionEvent(
                    SUBPROGRAM_END,
                    block.index,
                    code="M99",
                    program_number=current_program,
                    call_depth=len(call_stack_before),
                    target_block=current_target,
                )
            )
            if sub_flow.next_pc == current_target and len(sub_flow.call_stack) == len(call_stack_before):
                event_list.append(
                    ExecutionEvent(
                        SUBPROGRAM_START,
                        block.index,
                        code=(f"O{current_program}" if current_program is not None else None),
                        program_number=current_program,
                        call_depth=len(sub_flow.call_stack),
                        target_block=current_target,
                    )
                )
        else:
            event_list.append(
                ExecutionEvent(
                    PROGRAM_END,
                    block.index,
                    code="M99",
                    program_number=ctx.program_number,
                )
            )
    elif flow_mcode in (2, 30) and sub_flow.handled:
        event_list.append(
            ExecutionEvent(
                PROGRAM_END,
                block.index,
                code=f"M{int(flow_mcode):02d}",
                program_number=ctx.program_number,
            )
        )


def _execute_turning_motion(
    ast_node,
    words,
    state,
    gcode,
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

    if non_motion_g and has_pos and gcode not in (28, 30) and gcode not in POSITION_NEUTRAL_GCODES:
        # An unmodeled position-bearing command may have changed physical
        # position. Taint only the addressed axes and resume after absolute
        # X/Z re-establishes them; never invent a connecting segment.
        state.unknown_x_after_g28 = ("X" in words) or ("U" in words)
        state.unknown_z_after_g28 = ("Z" in words) or ("W" in words)
        state.position_unknown_reason = "unsupported"
        ctx.pc += 1
        return False, motions

    g28d = dispatch_g28_home(
        emulate_g28_home=emulate_g28_home,
        gcode=gcode,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
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
    if g28d.handled:
        motions.extend(tagged(g28d.emitted_motions))
        state.modal_x = g28d.new_modal_x
        state.modal_z = g28d.new_modal_z
        ctx.pc += 1
        return False, motions

    md = dispatch_motion_block(
        has_pos=has_pos,
        non_motion_g=non_motion_g,
        modal_move=state.modal_move,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
        modal_feed=state.modal_feed,
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
