from __future__ import annotations

from dataclasses import replace

from .cycles import (
    add_g90_longitudinal_pass,
    add_g92_thread_pass,
    add_g94_facing_pass,
    build_finish_contour,
    build_g71_roughing,
    build_g72_facing,
    build_g73_pattern,
    build_g74_cycle,
    build_g75_cycle,
    build_g76_threading,
    build_g83_cycle,
    build_g84_cycle,
    build_offset_profile,
    ensure_cycle_return,
    is_boring_cycle,
)
from .execution import (
    build_program_execution_index,
    classify_block_codes,
    dispatch_macro_flow,
    dispatch_subprogram_flow,
    retain_modal_turning_cycles,
)
from .model import Motion, Point2, RuntimeState
from .profile import build_profile_segments
from .program import (
    eval_words,
    micron_or_mm_to_mm,
    resolve_cycle_profile_indices,
    scaled_word,
    scaled_word_or,
    x_delta_to_diameter,
    x_value_to_diameter,
)
from .tool_compensation import compensate_profile_segments


def compile_program(
    program,
    supplementary_angles: bool = False,
    x_is_diameter: bool = True,
    skip_optional_blocks: bool = False,
    pq_mm_for_g74758384: bool = False,
    tools: dict[str, dict[str, object]] | None = None,
):
    def _cycle_pq_to_mm(value: float, unit_scale: float, expr: str | None = None) -> float:
        raw = abs(value * unit_scale)
        if pq_mm_for_g74758384:
            return raw
        # FANUC commonly programs P/Q as integer least-input increments.  Some
        # CAM posts (including the CncKernelCli donor fixtures) intentionally
        # emit decimal P/Q words such as P3. Q3. to mean direct length units.
        # Use lexical precision rather than a value-magnitude heuristic.
        if expr is not None and ("." in expr or "E" in expr.upper()):
            return raw
        increment_mm = 0.001 if abs(unit_scale - 1.0) <= 1e-12 else (0.0001 * 25.4)
        return abs(value) * increment_mm

    def _word_expr(block, letter: str) -> str | None:
        for token in reversed(block.parsed_words):
            if token.letter.upper() == letter.upper():
                return token.expr
        return None

    blocks = program.blocks
    execution_index = build_program_execution_index(program)
    label_to_index = execution_index.label_to_index
    olabel_to_index = execution_index.olabel_to_index
    while_to_end = execution_index.while_to_end
    end_to_while = execution_index.end_to_while

    state = RuntimeState(x_is_diameter=x_is_diameter)
    rough_cycles: list[list[Motion]] = []
    finish_cycles: list[list[Motion]] = []
    # Stack frame: (return_pc, subprogram_start_pc, remaining_repeats)
    call_stack: list[tuple[int, int, int]] = []
    max_call_depth = 64

    pc = 0
    guard = 0
    while 0 <= pc < len(blocks):
        guard += 1
        if guard > 500000:
            raise RuntimeError("Program execution guard reached")

        block = blocks[pc]
        if skip_optional_blocks and block.optional_skip:
            pc += 1
            continue

        vars_map = state.variables if state.variables is not None else {}
        flow_dispatch = dispatch_macro_flow(
            block=block,
            pc=pc,
            blocks=blocks,
            variables=vars_map,
            label_to_index=label_to_index,
            while_to_end=while_to_end,
            end_to_while=end_to_while,
        )
        if flow_dispatch.handled:
            pc = flow_dispatch.next_pc
            continue

        words = eval_words(block.parsed_words, vars_map)
        if getattr(words, "errors", None):
            details = ", ".join(f"{tok.letter}{tok.expr}: {msg}" for tok, msg in words.errors)
            raise ValueError(f"Cannot evaluate CNC words at line {block.index + 1}: {block.raw}: {details}")
        codes = classify_block_codes(words)
        all_g = codes.all_g
        all_m = codes.all_m
        gcode = codes.gcode
        cycle_line_consumed = False
        if 40 in all_g:
            state.compensation_mode = 40
        elif 41 in all_g:
            state.compensation_mode = 41
        elif 42 in all_g:
            state.compensation_mode = 42
        if "T" in words:
            state.active_tool = f"T{abs(int(round(words['T']))):04d}"

        def profile_compensation_modes(p_index: int, q_index: int) -> dict[int, int]:
            mode = state.compensation_mode
            modes: dict[int, int] = {}
            for profile_index in range(p_index, q_index + 1):
                profile_words = eval_words(blocks[profile_index].parsed_words, state.clone_vars())
                profile_codes = classify_block_codes(profile_words)
                if 40 in profile_codes.all_g:
                    mode = 40
                elif 41 in profile_codes.all_g:
                    mode = 41
                elif 42 in profile_codes.all_g:
                    mode = 42
                modes[profile_index] = mode
            return modes

        def compensated_profile(profile, p_index: int, q_index: int):
            if not tools:
                return profile, False
            modes = profile_compensation_modes(p_index, q_index)
            active = any(mode in (41, 42) for mode in modes.values())
            return (
                compensate_profile_segments(
                    profile,
                    compensation_mode=state.compensation_mode,
                    compensation_modes=modes,
                    tool_code=state.active_tool,
                    tools=tools or {},
                ),
                active,
            )

        def mark_compensated(motions, profile_was_compensated: bool):
            if not tools or not profile_was_compensated:
                return motions
            return [replace(motion, compensation_applied=True) for motion in motions]

        flow_mcode = (
            98 if 98 in all_m else (99 if 99 in all_m else (30 if 30 in all_m else (2 if 2 in all_m else codes.mcode)))
        )
        try:
            sub_flow = dispatch_subprogram_flow(
                mcode=flow_mcode,
                words=words,
                pc=pc,
                olabel_to_index=olabel_to_index,
                call_stack=call_stack,
                max_call_depth=max_call_depth,
            )
        except ValueError as exc:
            raise ValueError(f"{exc} at line {block.index + 1}: {block.raw}") from exc
        call_stack = sub_flow.call_stack
        if sub_flow.handled:
            if sub_flow.stop:
                if flow_mcode in (2, 30):
                    state.active_g83_cycle = False
                    state.active_g84_cycle = False
                    state.active_g80 = True
                break
            pc = sub_flow.next_pc
            continue

        # G4 is a non-modal dwell block. X is seconds and P is milliseconds;
        # neither address is a machine coordinate and modal motion is retained.
        # Mixed G4/G blocks are diagnosed separately and fail closed here.
        if 4 in all_g:
            pc += 1
            continue

        # Apply every modal G word in the block, not only the last one.
        # This is required for normal safety blocks such as G18G21G40G54G80G99.
        if 20 in all_g:
            state.unit_scale = 25.4
        if 21 in all_g:
            state.unit_scale = 1.0
        if 190 in all_g:
            state.x_is_diameter = True
        if 191 in all_g:
            state.x_is_diameter = False

        (
            state.active_g90_cycle,
            state.active_g92_cycle,
            state.active_g94_cycle,
        ) = retain_modal_turning_cycles(
            all_g,
            active_g90=state.active_g90_cycle,
            active_g92=state.active_g92_cycle,
            active_g94=state.active_g94_cycle,
        )
        if "T" in words:
            state.active_g83_cycle = False
            state.active_g84_cycle = False
            state.active_g80 = True
        if 80 in all_g:
            state.active_g83_cycle = False
            state.active_g84_cycle = False
            state.active_g80 = True

        can_continue_g90 = state.active_g90_cycle and gcode is None and ("X" in words or "U" in words)
        is_g90_cycle_line = (gcode == 90 and ("X" in words or "U" in words)) or can_continue_g90
        if is_g90_cycle_line:
            cycle_line_consumed = True
            if gcode == 90:
                state.active_g90_cycle = True
                state.g90_start_x = state.modal_x
                state.g90_start_z = state.modal_z
                state.g90_target_z = (
                    scaled_word(words, "Z", state.unit_scale)
                    if "Z" in words
                    else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
                )
                state.g90_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                state.g90_last_x = state.modal_x
            else:
                if "Z" in words:
                    state.g90_target_z = scaled_word(words, "Z", state.unit_scale)
                elif "W" in words:
                    state.g90_target_z = state.g90_target_z + scaled_word(words, "W", state.unit_scale)
                if "F" in words:
                    state.g90_feed = scaled_word(words, "F", state.unit_scale)

            target_x = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.g90_last_x
                    + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                )
            )
            cyc: list[Motion] = []
            add_g90_longitudinal_pass(
                cyc,
                state.g90_start_x,
                state.g90_start_z,
                target_x,
                state.g90_target_z,
                state.g90_feed,
                first_block_with_z=(gcode == 90 and ("Z" in words or "W" in words)),
            )
            ensure_cycle_return(cyc, Point2(state.g90_start_x, state.g90_start_z))
            rough_cycles.append(cyc)
            state.g90_last_x = target_x
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z

        can_continue_g92 = state.active_g92_cycle and gcode is None and ("X" in words or "U" in words)
        is_g92_cycle_line = (gcode == 92 and ("X" in words or "U" in words)) or can_continue_g92
        if is_g92_cycle_line:
            cycle_line_consumed = True
            if gcode == 92:
                state.active_g92_cycle = True
                state.g92_start_x = state.modal_x
                state.g92_start_z = state.modal_z
                state.g92_target_z = (
                    scaled_word(words, "Z", state.unit_scale)
                    if "Z" in words
                    else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
                )
                state.g92_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                state.g92_last_x = state.modal_x
            else:
                if "Z" in words:
                    state.g92_target_z = scaled_word(words, "Z", state.unit_scale)
                elif "W" in words:
                    state.g92_target_z = state.g92_target_z + scaled_word(words, "W", state.unit_scale)
                if "F" in words:
                    state.g92_feed = scaled_word(words, "F", state.unit_scale)

            target_x = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.g92_last_x
                    + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                )
            )
            cyc: list[Motion] = []
            add_g92_thread_pass(
                cyc,
                state.g92_start_x,
                state.g92_start_z,
                target_x,
                state.g92_target_z,
                state.g92_feed,
            )
            ensure_cycle_return(cyc, Point2(state.g92_start_x, state.g92_start_z))
            rough_cycles.append(cyc)
            state.g92_last_x = target_x
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z

        can_continue_g94 = state.active_g94_cycle and gcode is None and ("Z" in words or "W" in words)
        is_g94_cycle_line = (gcode == 94 and ("X" in words or "U" in words)) or can_continue_g94
        if is_g94_cycle_line:
            cycle_line_consumed = True
            if gcode == 94:
                state.active_g94_cycle = True
                state.g94_start_x = state.modal_x
                state.g94_start_z = state.modal_z
                state.g94_target_x = (
                    x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                    if "X" in words
                    else (
                        state.modal_x
                        + x_delta_to_diameter(
                            scaled_word(words, "U", state.unit_scale),
                            state.x_is_diameter,
                        )
                    )
                )
                state.g94_target_z = (
                    scaled_word(words, "Z", state.unit_scale)
                    if "Z" in words
                    else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
                )
                state.g94_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            else:
                if "Z" in words:
                    state.g94_target_z = scaled_word(words, "Z", state.unit_scale)
                elif "W" in words:
                    state.g94_target_z = state.g94_target_z + scaled_word(words, "W", state.unit_scale)
                if "F" in words:
                    state.g94_feed = scaled_word(words, "F", state.unit_scale)

            cyc: list[Motion] = []
            add_g94_facing_pass(
                cyc,
                state.g94_start_x,
                state.g94_start_z,
                state.g94_target_x,
                state.g94_target_z,
                state.g94_feed,
                first_block_with_z=(gcode == 94 and ("Z" in words or "W" in words)),
            )
            ensure_cycle_return(cyc, Point2(state.g94_start_x, state.g94_start_z))
            rough_cycles.append(cyc)
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z

        can_continue_g83 = state.active_g83_cycle and gcode is None and any(k in words for k in ("X", "U", "Z", "W"))
        is_g83_cycle_line = (gcode == 83 and any(k in words for k in ("X", "U", "Z", "W"))) or can_continue_g83
        if is_g83_cycle_line:
            cycle_line_consumed = True
            if gcode == 83:
                state.active_g83_cycle = True
                state.active_g84_cycle = False
                state.active_g80 = False
                if "R" in words:
                    state.g83_retract_r = abs(scaled_word(words, "R", state.unit_scale))
                if "Q" in words:
                    state.g83_step_q = _cycle_pq_to_mm(words["Q"], state.unit_scale, _word_expr(block, "Q"))
                if "P" in words:
                    state.g83_dwell_p = abs(words["P"])
                state.g83_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            else:
                if "R" in words:
                    state.g83_retract_r = abs(scaled_word(words, "R", state.unit_scale))
                if "Q" in words:
                    state.g83_step_q = _cycle_pq_to_mm(words["Q"], state.unit_scale, _word_expr(block, "Q"))
                if "P" in words:
                    state.g83_dwell_p = abs(words["P"])
                if "F" in words:
                    state.g83_feed = scaled_word(words, "F", state.unit_scale)

            tx = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                    if "U" in words
                    else state.modal_x
                )
            )
            tz = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
            )
            cyc = build_g83_cycle(
                state.modal_x,
                state.modal_z,
                tx,
                tz,
                state.g83_retract_r,
                state.g83_step_q,
                state.g83_dwell_p,
                state.g83_feed,
            )
            rough_cycles.append(cyc)
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z

        can_continue_g84 = state.active_g84_cycle and gcode is None and any(k in words for k in ("X", "U", "Z", "W"))
        is_g84_cycle_line = (gcode == 84 and any(k in words for k in ("X", "U", "Z", "W"))) or can_continue_g84
        if is_g84_cycle_line:
            cycle_line_consumed = True
            if gcode == 84:
                state.active_g84_cycle = True
                state.active_g83_cycle = False
                state.active_g80 = False
                if "R" in words:
                    state.g84_retract_r = abs(scaled_word(words, "R", state.unit_scale))
                if "Q" in words:
                    state.g84_step_q = _cycle_pq_to_mm(words["Q"], state.unit_scale, _word_expr(block, "Q"))
                if "P" in words:
                    state.g84_dwell_p = abs(words["P"])
                state.g84_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            else:
                if "R" in words:
                    state.g84_retract_r = abs(scaled_word(words, "R", state.unit_scale))
                if "Q" in words:
                    state.g84_step_q = _cycle_pq_to_mm(words["Q"], state.unit_scale, _word_expr(block, "Q"))
                if "P" in words:
                    state.g84_dwell_p = abs(words["P"])
                if "F" in words:
                    state.g84_feed = scaled_word(words, "F", state.unit_scale)

            tx = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                    if "U" in words
                    else state.modal_x
                )
            )
            tz = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
            )
            cyc = build_g84_cycle(
                state.modal_x,
                state.modal_z,
                tx,
                tz,
                state.g84_retract_r,
                state.g84_step_q,
                state.g84_dwell_p,
                state.g84_feed,
            )
            rough_cycles.append(cyc)
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z

        if gcode == 71:
            if "P" not in words and "U" in words and "R" in words:
                assert state.g71_first is not None
                state.g71_first.valid = True
                state.g71_first.depth_u_radius = abs(scaled_word(words, "U", state.unit_scale))
                state.g71_first.retract_r_radius = abs(scaled_word(words, "R", state.unit_scale))
                state.g71_first.stock_x = state.modal_x
                state.g71_first.stock_z = state.modal_z
            elif "P" in words and "Q" in words:
                p = int(words["P"])
                q = int(words["Q"])
                profile_bounds = resolve_cycle_profile_indices(blocks, pc, p, q)
                if profile_bounds is not None and state.g71_first is not None and state.g71_first.valid:
                    p_index, q_index = profile_bounds
                    sx = state.g71_first.stock_x
                    sz = state.g71_first.stock_z
                    finish_u = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                    finish_w = words.get("W", 0.0) * state.unit_scale
                    cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                    finish_profile = build_profile_segments(
                        blocks,
                        p_index,
                        q_index,
                        sx,
                        sz,
                        state.clone_vars(),
                        x_is_diameter=state.x_is_diameter,
                        unit_scale=state.unit_scale,
                        supplementary_angles=supplementary_angles,
                    )
                    finish_profile, profile_was_compensated = compensated_profile(finish_profile, p_index, q_index)
                    state.last_finish_stock_x = sx
                    state.last_finish_stock_z = sz
                    boring_mode = is_boring_cycle(finish_profile, finish_u, sx)
                    rough_profile = build_offset_profile(
                        finish_profile,
                        finish_u,
                        finish_w,
                        prefer_positive_x=not boring_mode,
                    )
                    p_block = blocks[p_index]
                    p_letters = {str(tok.letter).upper() for tok in p_block.parsed_words}
                    type_ii = bool(p_letters.intersection({"X", "U"}) and p_letters.intersection({"Z", "W"}))
                    cyc = build_g71_roughing(
                        rough_profile,
                        sx,
                        sz,
                        state.g71_first.depth_u_radius,
                        state.g71_first.retract_r_radius,
                        finish_w,
                        cycle_feed,
                        boring_mode=boring_mode,
                        type_ii=type_ii,
                    )
                    cyc = mark_compensated(cyc, profile_was_compensated)
                    ensure_cycle_return(cyc, Point2(sx, sz), first_axis="x")
                    rough_cycles.append(cyc)
                    if cyc:
                        state.modal_x = cyc[-1].end.x
                        state.modal_z = cyc[-1].end.z

        if gcode == 72:
            if "P" not in words and "W" in words and "R" in words:
                assert state.g72_first is not None
                state.g72_first.valid = True
                state.g72_first.depth_w = abs(scaled_word(words, "W", state.unit_scale))
                state.g72_first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
                state.g72_first.stock_x = state.modal_x
                state.g72_first.stock_z = state.modal_z
            elif "P" in words and "Q" in words:
                p = int(words["P"])
                q = int(words["Q"])
                profile_bounds = resolve_cycle_profile_indices(blocks, pc, p, q)
                if profile_bounds is not None and state.g72_first is not None and state.g72_first.valid:
                    p_index, q_index = profile_bounds
                    sx = state.g72_first.stock_x
                    sz = state.g72_first.stock_z
                    finish_u = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                    finish_w = words.get("W", 0.0) * state.unit_scale
                    cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                    finish_profile = build_profile_segments(
                        blocks,
                        p_index,
                        q_index,
                        sx,
                        sz,
                        state.clone_vars(),
                        x_is_diameter=state.x_is_diameter,
                        unit_scale=state.unit_scale,
                        supplementary_angles=supplementary_angles,
                    )
                    finish_profile, profile_was_compensated = compensated_profile(finish_profile, p_index, q_index)
                    state.last_finish_stock_x = sx
                    state.last_finish_stock_z = sz
                    rough_profile = build_offset_profile(
                        finish_profile,
                        finish_u,
                        finish_w,
                        prefer_positive_x=not is_boring_cycle(finish_profile, finish_u, sx),
                    )
                    p_block = blocks[p_index]
                    p_letters = {str(tok.letter).upper() for tok in p_block.parsed_words}
                    type_ii = bool(p_letters.intersection({"X", "U"}) and p_letters.intersection({"Z", "W"}))
                    cyc = build_g72_facing(
                        rough_profile,
                        sx,
                        sz,
                        state.g72_first.depth_w,
                        state.g72_first.retract_r,
                        finish_u,
                        finish_w,
                        cycle_feed,
                        cycle_return_z=(finish_profile[0].start.z if finish_profile else None),
                        type_ii=type_ii,
                    )
                    cyc = mark_compensated(cyc, profile_was_compensated)
                    ensure_cycle_return(cyc, Point2(sx, sz), first_axis="z")
                    rough_cycles.append(cyc)
                    if cyc:
                        state.modal_x = cyc[-1].end.x
                        state.modal_z = cyc[-1].end.z

        if gcode == 73:
            if "P" not in words and ("U" in words or "W" in words) and "R" in words:
                assert state.g73_first is not None
                state.g73_first.valid = True
                state.g73_first.total_u_x = x_delta_to_diameter(
                    words.get("U", 0.0) * state.unit_scale, state.x_is_diameter
                )
                state.g73_first.total_w_z = words.get("W", 0.0) * state.unit_scale
                state.g73_first.passes = max(1, int(abs(words["R"])))
                state.g73_first.stock_x = state.modal_x
                state.g73_first.stock_z = state.modal_z
            elif "P" in words and "Q" in words:
                p = int(words["P"])
                q = int(words["Q"])
                profile_bounds = resolve_cycle_profile_indices(blocks, pc, p, q)
                if profile_bounds is not None and state.g73_first is not None and state.g73_first.valid:
                    p_index, q_index = profile_bounds
                    sx = state.g73_first.stock_x
                    sz = state.g73_first.stock_z
                    finish_u = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                    finish_w = words.get("W", 0.0) * state.unit_scale
                    cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                    finish_profile = build_profile_segments(
                        blocks,
                        p_index,
                        q_index,
                        sx,
                        sz,
                        state.clone_vars(),
                        x_is_diameter=state.x_is_diameter,
                        unit_scale=state.unit_scale,
                        supplementary_angles=supplementary_angles,
                    )
                    finish_profile, profile_was_compensated = compensated_profile(finish_profile, p_index, q_index)
                    state.last_finish_stock_x = sx
                    state.last_finish_stock_z = sz
                    rough_profile = build_offset_profile(finish_profile, finish_u, finish_w, prefer_positive_x=True)
                    cyc = build_g73_pattern(
                        rough_profile,
                        sx,
                        sz,
                        state.g73_first.total_u_x,
                        state.g73_first.total_w_z,
                        state.g73_first.passes,
                        cycle_feed,
                    )
                    cyc = mark_compensated(cyc, profile_was_compensated)
                    ensure_cycle_return(cyc, Point2(sx, sz), first_axis="x")
                    rough_cycles.append(cyc)
                    if cyc:
                        state.modal_x = cyc[-1].end.x
                        state.modal_z = cyc[-1].end.z

        if gcode == 74:
            if "X" not in words and "Z" not in words and "R" in words:
                assert state.g74_first is not None
                state.g74_first.valid = True
                state.g74_first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
            elif any(k in words for k in ("X", "U", "Z", "W")):
                assert state.g74_first is not None
                retract = state.g74_first.retract_r if state.g74_first.valid else 0.0
                tx = (
                    x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                    if "X" in words
                    else (
                        state.modal_x + x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                        if "U" in words
                        else None
                    )
                )
                tz = (
                    scaled_word(words, "Z", state.unit_scale)
                    if "Z" in words
                    else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else None)
                )
                p_step = _cycle_pq_to_mm(words.get("P", 0.0), state.unit_scale, _word_expr(block, "P"))
                q_step = _cycle_pq_to_mm(words.get("Q", 0.0), state.unit_scale, _word_expr(block, "Q"))
                bottom = micron_or_mm_to_mm(abs(words.get("R", 0.0) * state.unit_scale))
                cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                cyc = build_g74_cycle(
                    state.modal_x,
                    state.modal_z,
                    tx,
                    tz,
                    retract,
                    p_step,
                    q_step,
                    bottom,
                    cycle_feed,
                )
                rough_cycles.append(cyc)
                if cyc:
                    state.modal_x = cyc[-1].end.x
                    state.modal_z = cyc[-1].end.z

        if gcode == 75:
            if "X" not in words and "Z" not in words and "R" in words:
                assert state.g75_first is not None
                state.g75_first.valid = True
                state.g75_first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
            elif "X" in words or "U" in words:
                assert state.g75_first is not None
                retract = state.g75_first.retract_r if state.g75_first.valid else 0.0
                tx = (
                    x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                    if "X" in words
                    else (
                        state.modal_x + x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                    )
                )
                tz = (
                    scaled_word(words, "Z", state.unit_scale)
                    if "Z" in words
                    else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else None)
                )
                p_step = _cycle_pq_to_mm(words.get("P", 0.0), state.unit_scale, _word_expr(block, "P"))
                q_step = _cycle_pq_to_mm(words.get("Q", 0.0), state.unit_scale, _word_expr(block, "Q"))
                bottom = micron_or_mm_to_mm(abs(words.get("R", 0.0) * state.unit_scale))
                cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                cyc = build_g75_cycle(
                    state.modal_x,
                    state.modal_z,
                    tx,
                    tz,
                    retract,
                    p_step,
                    q_step,
                    bottom,
                    cycle_feed,
                )
                rough_cycles.append(cyc)
                if cyc:
                    state.modal_x = cyc[-1].end.x
                    state.modal_z = cyc[-1].end.z

        if gcode == 76:
            # FANUC two-line G76: Q in the first line and P/Q in the second
            # line are integer least-input increments.  For metric turning they
            # are thousandths of a millimetre; R words are ordinary length words.
            g76_inc_scale = 0.001 if abs(state.unit_scale - 1.0) <= 1e-12 else (0.0001 * 25.4)
            if "X" not in words and "Z" not in words:
                assert state.g76_first is not None
                # Real FANUC programs commonly omit the first-block R when no
                # finish allowance is required.  Keep the dataclass default of
                # zero instead of rejecting the complete two-block cycle.
                state.g76_first.valid = all(k in words for k in ("P", "Q"))
                state.g76_first.packed_p = int(words.get("P", 0.0))
                state.g76_first.q_min_microns = abs(words.get("Q", 0.0)) * g76_inc_scale
                state.g76_first.r_finish_microns = abs(words.get("R", 0.0)) * state.unit_scale
            elif "X" in words and "Z" in words and state.g76_first is not None and state.g76_first.valid:
                tx = x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                tz = scaled_word(words, "Z", state.unit_scale)
                thread_height = abs(words.get("P", 0.0)) * g76_inc_scale
                first_cut = abs(words.get("Q", 0.0)) * g76_inc_scale
                taper_r = words.get("R", 0.0) * state.unit_scale
                lead = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
                cyc = build_g76_threading(
                    state.modal_x,
                    state.modal_z,
                    tx,
                    tz,
                    state.g76_first.packed_p,
                    state.g76_first.q_min_microns,
                    state.g76_first.r_finish_microns,
                    thread_height,
                    first_cut,
                    lead,
                    taper_r=taper_r,
                )
                ensure_cycle_return(cyc, Point2(state.modal_x, state.modal_z), first_axis="x")
                rough_cycles.append(cyc)
                if cyc:
                    state.modal_x = cyc[-1].end.x
                    state.modal_z = cyc[-1].end.z

        if gcode == 70 and "P" in words and "Q" in words:
            p = int(words["P"])
            q = int(words["Q"])
            profile_bounds = resolve_cycle_profile_indices(blocks, pc, p, q, prefer_preceding=True)
            if profile_bounds is not None:
                p_index, q_index = profile_bounds
                sx = (
                    state.last_finish_stock_x
                    if state.last_finish_stock_x is not None
                    else (
                        state.g71_first.stock_x
                        if (state.g71_first is not None and state.g71_first.valid)
                        else state.modal_x
                    )
                )
                sz = (
                    state.last_finish_stock_z
                    if state.last_finish_stock_z is not None
                    else (
                        state.g71_first.stock_z
                        if (state.g71_first is not None and state.g71_first.valid)
                        else state.modal_z
                    )
                )
                profile = build_profile_segments(
                    blocks,
                    p_index,
                    q_index,
                    sx,
                    sz,
                    state.clone_vars(),
                    x_is_diameter=state.x_is_diameter,
                    unit_scale=state.unit_scale,
                    supplementary_angles=supplementary_angles,
                )
                profile, profile_was_compensated = compensated_profile(profile, p_index, q_index)
                fcyc = build_finish_contour(profile)
                fcyc = mark_compensated(fcyc, profile_was_compensated)
                ensure_cycle_return(fcyc, Point2(state.modal_x, state.modal_z), first_axis="x")
                finish_cycles.append(fcyc)
                if fcyc:
                    state.modal_x = fcyc[-1].end.x
                    state.modal_z = fcyc[-1].end.z

        cycle_pos_locked = cycle_line_consumed or gcode in (
            70,
            71,
            72,
            73,
            74,
            75,
            76,
            83,
            84,
            90,
            92,
            94,
        )
        if "X" in words and not cycle_pos_locked:
            state.modal_x = x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
        elif "U" in words and gcode not in (70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92):
            state.modal_x += x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
        if "Z" in words and not cycle_pos_locked:
            state.modal_z = scaled_word(words, "Z", state.unit_scale)
        elif "W" in words and gcode not in (70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92):
            state.modal_z += scaled_word(words, "W", state.unit_scale)
        if "F" in words:
            state.modal_feed = scaled_word(words, "F", state.unit_scale)

        pc += 1

    if state.active_g83_cycle or state.active_g84_cycle:
        raise RuntimeError("G83/G84 cycle remains active. Add G80 (or T-word cancel) to terminate cycle mode.")

    return rough_cycles, finish_cycles
