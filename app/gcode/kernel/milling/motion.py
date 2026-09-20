"""Milling motion construction from evaluated words and state."""

from __future__ import annotations

from ..api.resources import checkpoint
from ..api.types import TraceMotion
from ..runtime.home import reference_return
from .drilling import _drill
from .state import MillState, _coordinate_transform, _machine, _wcs_offset, _xyz


def _motion(block, state: MillState, words, *, wcs_offsets, source_kind="motion") -> TraceMotion | None:
    end = _xyz(words, state)
    start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    end_m = _machine(end, state, wcs_offsets)
    arc_vector = (0.0, 0.0, 0.0)
    plane_scales = (1.0, 1.0)
    if state.move in (2, 3):
        transform = _coordinate_transform(state)
        arc_vector = transform.apply_vector(tuple(words.get(axis, 0.0) * state.unit_scale for axis in ("I", "J", "K")))
        plane_scales = transform.plane_scale_factors(state.plane)
        if abs(plane_scales[0] - plane_scales[1]) > 1e-12:
            raise ValueError("G51 axis-specific scaling of arcs requires spiral interpolation, which is not modeled")
    state.x, state.y, state.z = end
    has_arc_definition = state.move in (2, 3) and any(key in words for key in ("I", "J", "K", "R"))
    if start_m == end_m and not has_arc_definition:
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end_m[0],
        end_y=end_m[1],
        end_z=end_m[2],
        radius=(words.get("R") * state.unit_scale * abs(plane_scales[0]) if "R" in words else None),
        feed=(None if state.move == 0 else state.feed),
        i=(arc_vector[0] if "I" in words else None),
        j=(arc_vector[1] if "J" in words else None),
        k=(arc_vector[2] if "K" in words else None),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind=source_kind,
        plane=state.plane,
        cycle_generated=source_kind == "cycle",
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
        compensation_status="UNVERIFIED" if state.cutter_comp in (41, 42) else "NOT_APPLIED",
    )


def _machine_coordinate_motion(block, state: MillState, words, *, wcs_offsets) -> TraceMotion | None:
    """Execute a non-modal G53 move directly in machine coordinates."""
    start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    end_m = list(start_m)
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        value = words[letter] * state.unit_scale
        end_m[index] = value if state.absolute else start_m[index] + value

    end = (end_m[0], end_m[1], end_m[2])
    ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
    work = (end[0] - ox, end[1] - oy, end[2] - oz)
    state.x, state.y, state.z = _coordinate_transform(state).inverse(work)
    if start_m == end:
        return None
    return TraceMotion(
        move=state.move,
        start_x=start_m[0],
        start_y=start_m[1],
        start_z=start_m[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        feed=(None if state.move == 0 else state.feed),
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        source_kind="g53",
        plane=state.plane,
        compensation_mode=state.cutter_comp,
        compensation_applied=False,
        tool=state.active_tool,
    )


def _g53_home_axes(
    state: MillState,
    words,
    home: tuple[float, float, float],
    *,
    wcs_offsets,
) -> tuple[str, ...]:
    """Return addressed G53 axes that deterministically target configured home."""
    start_m = _machine((state.x, state.y, state.z), state, wcs_offsets)
    axes: list[str] = []
    for index, letter in enumerate(("X", "Y", "Z")):
        if letter not in words:
            continue
        if state.absolute:
            target = words[letter] * state.unit_scale
        else:
            target = start_m[index] + words[letter] * state.unit_scale
        if abs(target - home[index]) > 1e-9:
            return ()
        axes.append(letter)
    return tuple(axes)


def _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets):
    if not gcodes and state.cycle == 80:
        if "X" in words or "Y" in words or "Z" in words:
            m = _motion(block, state, words, wcs_offsets=wcs_offsets)
            if m:
                checkpoint("generated_motions")
                motions.append(m)
        return True
    return False


def _emit_milling_motions(block, state, words, gcodes, motions, home, wcs_offsets):
    if _emit_simple_modal_motion(block, state, words, gcodes, motions, wcs_offsets):
        return

    action_g = None
    for g in gcodes:
        if g in (0, 1, 2, 3, 28, 53, 73, 80, 81, 82, 83, 84, 85, 86):
            action_g = g
    if action_g is not None and action_g not in (73, 80, 81, 82, 83, 84, 85, 86):
        # Match CncKernelCli: an explicit motion/reference command ends
        # a modal drilling cycle even without a separate G80 block.
        state.cycle = 80

    for g in gcodes:
        if g in (0, 1, 2, 3):
            state.move = g
        elif g in (73, 80, 81, 82, 83, 84, 85, 86):
            if g in (73, 81, 82, 83, 84, 85, 86) and state.cycle == 80:
                state.cycle_initial_z = state.z
            state.cycle = g

    if 4 in gcodes or any(g in gcodes for g in (50, 51, 52, 68, 69)):
        pass
    elif 53 in gcodes:
        m = _machine_coordinate_motion(block, state, words, wcs_offsets=wcs_offsets)
        if m:
            checkpoint("generated_motions")
            motions.append(m)
    elif 28 in gcodes:
        mid = _xyz(words, state)
        start_machine = _machine((state.x, state.y, state.z), state, wcs_offsets)
        intermediate_machine = _machine(mid, state, wcs_offsets)
        path = reference_return(
            start_machine,
            intermediate_machine,
            home,
            tuple(axis in words for axis in ("X", "Y", "Z")),
        )
        for segment_start, segment_end in path.segments:
            checkpoint("generated_motions")
            motions.append(
                TraceMotion(
                    0,
                    segment_start[0],
                    segment_start[2],
                    segment_end[0],
                    segment_end[2],
                    start_y=segment_start[1],
                    end_y=segment_end[1],
                    plane=state.plane,
                    source_block=block.index,
                    source_nlabel=block.nlabel,
                    source_raw=block.raw,
                    source_kind="g28",
                    tool=state.active_tool,
                )
            )
        ox, oy, oz = _wcs_offset(wcs_offsets, state.active_wcs)
        work = (path.target[0] - ox, path.target[1] - oy, path.target[2] - oz)
        state.x, state.y, state.z = _coordinate_transform(state).inverse(work)
    elif state.cycle in (73, 81, 82, 83, 84, 85, 86) and any(k in words for k in ("X", "Y", "Z", "R")):
        motions.extend(_drill(block, state, words, wcs_offsets=wcs_offsets))
    elif state.cycle == 80 and (any(k in words for k in ("X", "Y", "Z")) or any(g in (0, 1, 2, 3) for g in gcodes)):
        m = _motion(block, state, words, wcs_offsets=wcs_offsets)
        if m:
            checkpoint("generated_motions")
            motions.append(m)
