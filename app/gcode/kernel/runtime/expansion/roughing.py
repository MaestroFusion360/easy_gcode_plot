"""Turning roughing-cycle expansion (G71/G72/G73)."""

from __future__ import annotations

from dataclasses import dataclass

from ...frontend.model import Point2, ProfileSegment
from ...frontend.program import resolve_cycle_profile_indices, scaled_word, scaled_word_or, x_delta_to_diameter
from ...geometry import build_profile_segments
from ...turning.cycles import (
    build_g71_roughing,
    build_g72_facing,
    build_g73_pattern,
    build_offset_profile,
    ensure_cycle_return,
    is_boring_cycle,
)


@dataclass(frozen=True)
class _RoughingProfileData:
    sx: float
    sz: float
    finish_u: float
    finish_w: float
    feed: float
    profile: list[ProfileSegment]
    compensated: bool
    type_ii: bool


def _prepare_roughing_profile(
    blocks,
    compensated_profile,
    pc,
    first,
    state,
    supplementary_angles,
    words,
    variables,
) -> _RoughingProfileData | None:
    if "P" not in words or "Q" not in words or first is None or not first.valid:
        return None
    bounds = resolve_cycle_profile_indices(blocks, pc, int(words["P"]), int(words["Q"]))
    if bounds is None:
        return None

    p_index, q_index = bounds
    sx = first.stock_x
    sz = first.stock_z
    finish_u = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
    finish_w = words.get("W", 0.0) * state.unit_scale
    feed = scaled_word_or(words, "F", state.feed, state.unit_scale)
    profile = build_profile_segments(
        blocks,
        p_index,
        q_index,
        sx,
        sz,
        dict(variables or {}),
        x_is_diameter=state.x_is_diameter,
        unit_scale=state.unit_scale,
        supplementary_angles=supplementary_angles,
    )
    profile, was_compensated = compensated_profile(profile, p_index, q_index)
    state.last_finish_stock_x = sx
    state.last_finish_stock_z = sz
    p_letters = {str(token.letter).upper() for token in blocks[p_index].parsed_words}
    type_ii = bool(p_letters.intersection({"X", "U"}) and p_letters.intersection({"Z", "W"}))
    return _RoughingProfileData(sx, sz, finish_u, finish_w, feed, profile, was_compensated, type_ii)


def _store_cycle_result(cycle, rough_cycles, state) -> None:
    rough_cycles.append(cycle)
    if cycle:
        state.modal_x = cycle[-1].end.x
        state.modal_z = cycle[-1].end.z


def _expand_g71(
    blocks,
    compensated_profile,
    gcode,
    mark_compensated,
    pc,
    rough_cycles,
    state,
    supplementary_angles,
    words,
    variables,
):
    if gcode != 71:
        return
    first = state.g71_first
    assert first is not None
    if "P" not in words and "U" in words and "R" in words:
        first.valid = True
        first.depth_u_radius = abs(scaled_word(words, "U", state.unit_scale))
        first.retract_r_radius = abs(scaled_word(words, "R", state.unit_scale))
        first.stock_x = state.modal_x
        first.stock_z = state.modal_z
        return

    data = _prepare_roughing_profile(
        blocks, compensated_profile, pc, first, state, supplementary_angles, words, variables
    )
    if data is None:
        return
    boring_mode = is_boring_cycle(data.profile, data.finish_u, data.sx)
    rough_profile = build_offset_profile(
        data.profile,
        data.finish_u,
        data.finish_w,
        prefer_positive_x=not boring_mode,
    )
    cycle = build_g71_roughing(
        rough_profile,
        data.sx,
        data.sz,
        first.depth_u_radius,
        first.retract_r_radius,
        data.finish_w,
        data.feed,
        boring_mode=boring_mode,
        type_ii=data.type_ii,
    )
    cycle = mark_compensated(cycle, data.compensated)
    ensure_cycle_return(cycle, Point2(data.sx, data.sz), first_axis="x")
    _store_cycle_result(cycle, rough_cycles, state)


def _expand_g72(
    blocks,
    compensated_profile,
    gcode,
    mark_compensated,
    pc,
    rough_cycles,
    state,
    supplementary_angles,
    words,
    variables,
):
    if gcode != 72:
        return
    first = state.g72_first
    assert first is not None
    if "P" not in words and "W" in words and "R" in words:
        first.valid = True
        first.depth_w = abs(scaled_word(words, "W", state.unit_scale))
        first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
        first.stock_x = state.modal_x
        first.stock_z = state.modal_z
        return

    data = _prepare_roughing_profile(
        blocks, compensated_profile, pc, first, state, supplementary_angles, words, variables
    )
    if data is None:
        return
    rough_profile = build_offset_profile(
        data.profile,
        data.finish_u,
        data.finish_w,
        prefer_positive_x=not is_boring_cycle(data.profile, data.finish_u, data.sx),
    )
    cycle = build_g72_facing(
        rough_profile,
        data.sx,
        data.sz,
        first.depth_w,
        first.retract_r,
        data.finish_u,
        data.finish_w,
        data.feed,
        cycle_return_z=(data.profile[0].start.z if data.profile else None),
        type_ii=data.type_ii,
    )
    cycle = mark_compensated(cycle, data.compensated)
    ensure_cycle_return(cycle, Point2(data.sx, data.sz), first_axis="z")
    _store_cycle_result(cycle, rough_cycles, state)


def _expand_g73(
    blocks,
    compensated_profile,
    gcode,
    mark_compensated,
    pc,
    rough_cycles,
    state,
    supplementary_angles,
    words,
    variables,
):
    if gcode != 73:
        return
    first = state.g73_first
    assert first is not None
    if "P" not in words and ("U" in words or "W" in words) and "R" in words:
        first.valid = True
        first.total_u_x = x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
        first.total_w_z = words.get("W", 0.0) * state.unit_scale
        first.passes = max(1, int(abs(words["R"])))
        first.stock_x = state.modal_x
        first.stock_z = state.modal_z
        return

    data = _prepare_roughing_profile(
        blocks, compensated_profile, pc, first, state, supplementary_angles, words, variables
    )
    if data is None:
        return
    rough_profile = build_offset_profile(data.profile, data.finish_u, data.finish_w, prefer_positive_x=True)
    cycle = build_g73_pattern(
        rough_profile,
        data.sx,
        data.sz,
        first.total_u_x,
        first.total_w_z,
        first.passes,
        data.feed,
    )
    cycle = mark_compensated(cycle, data.compensated)
    ensure_cycle_return(cycle, Point2(data.sx, data.sz), first_axis="x")
    _store_cycle_result(cycle, rough_cycles, state)
