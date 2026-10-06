"""Turning finishing-contour expansion (G70)."""

from __future__ import annotations

from ...frontend.model import Point2
from ...frontend.program import eval_words, resolve_cycle_profile_indices
from ...geometry import build_profile_segments
from ...turning.cycles import build_finish_contour, ensure_cycle_return


def _expand_g70(
    blocks,
    compensated_profile,
    finish_cycles,
    gcode,
    mark_compensated,
    pc,
    state,
    supplementary_angles,
    words,
    variables,
    gcode_system="A",
    distance_absolute=True,
):
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
                dict(variables or {}),
                x_is_diameter=state.x_is_diameter,
                unit_scale=state.unit_scale,
                supplementary_angles=supplementary_angles,
                gcode_system=gcode_system,
                distance_absolute=distance_absolute,
            )
            profile, profile_was_compensated = compensated_profile(profile, p_index, q_index)
            fcyc = build_finish_contour(
                profile,
                entry_start=Point2(state.modal_x, state.modal_z),
                feeds_by_block=_profile_feeds(blocks, p_index, q_index, variables, state),
            )
            fcyc = mark_compensated(fcyc, profile_was_compensated)
            ensure_cycle_return(fcyc, Point2(state.modal_x, state.modal_z), first_axis="x")
            finish_cycles.append(fcyc)
            if fcyc:
                state.modal_x = fcyc[-1].end.x
                state.modal_z = fcyc[-1].end.z


def _profile_feeds(blocks, start, end, variables, state):
    feed = state.feed if state.feed > 0 else None
    feeds = {}
    for block in blocks[start : end + 1]:
        values = eval_words(block.parsed_words, dict(variables or {}))
        if "F" in values:
            feed = values["F"] * state.unit_scale
        feeds[block.index] = feed
    return feeds
