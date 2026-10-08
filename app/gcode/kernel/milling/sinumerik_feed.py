"""Separate Siemens geometry units, modal feed units and inverse block time."""

from .sinumerik_iso import _diag


def native_feed_diagnostic(block, evaluated, state):
    codes = evaluated.codes.all_g
    units = [g for g in codes if g in (70, 71, 700, 710)]
    if len(units) > 1:
        return _diag(block, "CONFLICTING_SINUMERIK_UNITS", "Select one native unit mode per block")
    inverse = next(
        (g == 93 for g in reversed(codes) if g in (93, 94, 95, 96, 97, 961, 971)), state.feed_mode == "inverse_time"
    )
    if not inverse:
        return None
    if state.native_cycle is not None or block.native_syntax.kind == "cycle" or any(g in range(81, 90) for g in codes):
        return _diag(block, "UNSUPPORTED_G93_CYCLE", "Inverse-time drilling cycles are not modeled")
    return _inverse_motion_diagnostic(block, evaluated, state)


def _inverse_motion_diagnostic(block, evaluated, state):
    codes = evaluated.codes.all_g
    move = next((g for g in reversed(codes) if g in (0, 1, 2, 3)), state.move)
    if move == 0 or not any(axis in evaluated.words for axis in "XYZABCIJKR"):
        return None
    feed = evaluated.words.get("F", state.native_programmed_feed if state.feed_mode == "inverse_time" else None)
    if feed is None or feed <= 0:
        return _diag(block, "INVALID_G93_FEED", "G93 cutting motion requires a positive inverse-time F")
    compensation = next((g for g in reversed(codes) if g in (40, 41, 42)), state.cutter_comp)
    if compensation != 40:
        return _diag(block, "UNSUPPORTED_G93_COMPENSATION", "Cancel cutter compensation before inverse-time motion")
    return None


def apply_native_feed_state(block, state, words):
    codes = [float(token.expr) for token in block.parsed_words if token.letter == "G"]
    scale = next((25.4 if g in (20, 700) else 1.0 for g in reversed(codes) if g in (20, 21, 700, 710)), None)
    if scale is not None:
        state.native_feed_scale = scale
    if any(g in (93, 94, 95, 96, 97, 961, 971) for g in codes) and "F" not in words:
        # Reissuing the same mode preserves F; switching requires a new F.
        previous = getattr(state, "native_previous_feed_mode", "per_minute")
        if previous != state.feed_mode:
            state.native_programmed_feed = None
            state.feed = 0.0
    if "F" in words:
        state.native_programmed_feed = words["F"]
    if state.native_programmed_feed is not None:
        state.feed = state.native_programmed_feed * (
            1.0 if state.feed_mode == "inverse_time" else state.native_feed_scale
        )
    state.native_previous_feed_mode = state.feed_mode
