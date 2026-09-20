# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Compiled bulk loop for ordinary modal milling blocks."""

import math

from ..api.resources import checkpoint
from ..api.types import ExecutionStep, TraceMotion


def execute_simple_blocks(program, runtime, state, motions, executed, steps, wcs_offsets):
    """Consume a contiguous run of literal N/X/Y/Z/I/J/K/R blocks."""
    cdef Py_ssize_t processed = 0
    cdef object block
    cdef object token
    cdef object letter
    cdef object value
    cdef object motion
    cdef dict all_values
    cdef dict latest
    cdef list values
    cdef bint has_position
    cdef double start_x
    cdef double start_y
    cdef double start_z
    cdef double end_x
    cdef double end_y
    cdef double end_z
    cdef double scale
    cdef object offsets
    cdef object position
    cdef object radius
    cdef object i_value
    cdef object j_value
    cdef object k_value

    while 0 <= runtime.pc < len(program.blocks):
        block = program.blocks[runtime.pc]
        if (
            block.flow_node is not None
            or block.optional_skip
            or state.cycle != 80
            or state.unknown_axes
            or state.transform.translation != (0.0, 0.0, 0.0)
            or state.transform.rotation_active
            or state.transform.scaling_active
        ):
            break

        all_values = {}
        latest = {}
        values = []
        has_position = False
        for token in block.parsed_words:
            letter = token.letter
            if letter not in ("N", "X", "Y", "Z", "I", "J", "K", "R"):
                return processed
            try:
                value = float(token.expr)
            except (TypeError, ValueError):
                return processed
            if not math.isfinite(value):
                return processed
            all_values.setdefault(letter, []).append(value)
            latest[letter] = value
            if letter == "X" or letter == "Y" or letter == "Z":
                has_position = True
        for letter, letter_values in all_values.items():
            for value in letter_values:
                values.append((letter, value))

        runtime.next_block(program.blocks)
        motion = None
        if has_position:
            scale = state.unit_scale
            start_x = state.x
            start_y = state.y
            start_z = state.z
            if state.absolute:
                end_x = latest["X"] * scale if "X" in latest else start_x
                end_y = latest["Y"] * scale if "Y" in latest else start_y
                end_z = latest["Z"] * scale if "Z" in latest else start_z
            else:
                end_x = start_x + latest.get("X", 0.0) * scale
                end_y = start_y + latest.get("Y", 0.0) * scale
                end_z = start_z + latest.get("Z", 0.0) * scale
            state.x = end_x
            state.y = end_y
            state.z = end_z
            offsets = (wcs_offsets or {}).get(state.active_wcs, (0.0, 0.0, 0.0))
            position = (end_x + offsets[0], end_y + offsets[1], end_z + offsets[2])
            radius = latest.get("R")
            if radius is not None:
                radius *= scale
            i_value = latest.get("I")
            j_value = latest.get("J")
            k_value = latest.get("K")
            if i_value is not None:
                i_value *= scale
            if j_value is not None:
                j_value *= scale
            if k_value is not None:
                k_value *= scale
            if (
                (start_x, start_y, start_z) != (end_x, end_y, end_z)
                or (state.move in (2, 3) and (i_value is not None or j_value is not None or k_value is not None or radius is not None))
            ):
                motion = TraceMotion(
                    state.move,
                    start_x + offsets[0],
                    start_z + offsets[2],
                    end_x + offsets[0],
                    end_z + offsets[2],
                    radius,
                    None if state.move == 0 else state.feed,
                    i_value,
                    k_value,
                    block.index,
                    block.nlabel,
                    block.raw,
                    "motion",
                    state.cutter_comp,
                    state.active_tool,
                    False,
                    state.plane,
                    False,
                    start_y + offsets[1],
                    end_y + offsets[1],
                    j_value,
                    feed_mode=state.feed_mode,
                    spindle_rpm=state.spindle_rpm,
                    compensation_status="UNVERIFIED" if state.cutter_comp in (41, 42) else "NOT_APPLIED",
                )
                checkpoint("generated_motions")
                motions.append(motion)
                if not executed or executed[len(executed) - 1] != block.index:
                    executed.append(block.index)
        else:
            offsets = (wcs_offsets or {}).get(state.active_wcs, (0.0, 0.0, 0.0))
            position = (state.x + offsets[0], state.y + offsets[1], state.z + offsets[2])
        steps.append(
            ExecutionStep(
                block.index,
                1 if motion is not None else 0,
                state.unit_scale,
                False,
                False,
                False,
                state.absolute,
                tuple(values),
                (),
                len(steps),
                position,
                state.active_wcs,
                state.feed_mode,
                state.spindle_rpm,
            )
        )
        runtime.advance()
        processed += 1
    return processed
