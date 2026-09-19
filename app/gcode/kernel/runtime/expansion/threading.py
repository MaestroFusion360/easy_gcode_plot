"""Turning threading-cycle expansion (G76)."""

from __future__ import annotations

from ...frontend.model import Point2
from ...frontend.program import scaled_word, scaled_word_or, x_value_to_diameter
from ...lathe_cycles import build_g76_threading, ensure_cycle_return


def _expand_g76(gcode, rough_cycles, state, words):
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
