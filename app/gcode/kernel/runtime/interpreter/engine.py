from __future__ import annotations

# Trace execution dispatches early per block kind and control-flow opcode.
# pylint: disable=too-many-return-statements
from dataclasses import replace

from ...api.types import ExecutionEvent, ExecutionStep
from ...frontend.program import resolve_cycle_profile_indices
from ...geometry.coordinates import rebase_work_position
from ..events import TOOL_CHANGE, home_return_event, main_program_location, program_start_event
from ..execution import POSITION_NEUTRAL_GCODES, ProgramRuntime, apply_unit_mode, build_program_execution_index
from ..expansion import expand_cycle_block
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
from .types import TraceExecutionContext, TraceRuntimeState


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
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    try_wcs_from_gcode_fn,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
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
            emulate_g28_home=emulate_g28_home,
            x_is_diameter=x_is_diameter,
            home_x=home_x,
            home_z=home_z,
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
                variables=tuple(sorted(ctx.runtime.variables.items())),
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
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
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

    _apply_turning_modal_state(state, all_g, all_m, words, try_wcs_from_gcode_fn, wcs_off_fn)

    for reference_code in (28, 30):
        if reference_code in all_g:
            axes = tuple(
                axis
                for axis, addresses in (("X", _X_AXIS_WORDS), ("Z", _Z_AXIS_WORDS))
                if any(address in words for address in addresses)
            )
            event_list.append(home_return_event(block, f"G{reference_code}", axes, len(runtime.call_stack)))
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

    # G4 is non-modal dwell: X is seconds and P is milliseconds, not motion.
    # Consume the complete block before modal-motion dispatch so G0/G1 state
    # cannot reinterpret the dwell value as an X coordinate.
    if 4 in all_g:
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
            state.modal_x, state.modal_z = rebase_work_position(
                (state.modal_x, state.modal_z),
                wcs_off_fn(state.active_wcs),
                wcs_off_fn(wcs_code),
            )
            state.active_wcs = wcs_code

    # Modal words on an M98 block are active for the called subprogram.  Apply
    # state-only words before transferring control; the source block is not
    # revisited after M99 returns.
    apply_unit_mode(state, all_g)
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
        state.feed = words["F"] * state.unit_scale


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
