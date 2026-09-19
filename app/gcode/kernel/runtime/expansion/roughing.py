"""Turning roughing-cycle expansion (G71/G72/G73)."""

from __future__ import annotations

from ...frontend.model import Point2
from ...frontend.program import resolve_cycle_profile_indices, scaled_word, scaled_word_or, x_delta_to_diameter
from ...geometry import build_profile_segments
from ...lathe_cycles import (
    build_g71_roughing,
    build_g72_facing,
    build_g73_pattern,
    build_offset_profile,
    ensure_cycle_return,
    is_boring_cycle,
)


def _expand_g71(
    blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
):
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


def _expand_g72(
    blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
):
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


def _expand_g73(
    blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
):
    if gcode == 73:
        if "P" not in words and ("U" in words or "W" in words) and "R" in words:
            assert state.g73_first is not None
            state.g73_first.valid = True
            state.g73_first.total_u_x = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
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
