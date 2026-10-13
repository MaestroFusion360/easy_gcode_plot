"""Resolved rotary, TCP and tilted-plane output controls."""

from __future__ import annotations

import math
from dataclasses import replace

from ..post_profiles import _render
from .common import ExportLimitation, _word, _word_required

_ABC_INDEX = {"A": 0, "B": 1, "C": 2}


def _step_rotary_values(step, options, state):
    """Return the explicit resolved rotary coordinates to emit for one step."""
    available = dict(step.rotary_angles)
    emitted: dict[str, float] = {}
    for axis in options.rotary_axes:
        if axis not in available:
            continue
        value = available[axis]
        previous = 0.0 if state is None else state.get(axis, 0.0)
        if _word_required(options, axis.lower()) or state is None or previous != value:
            emitted[axis] = value - previous if options.incremental else value
        if state is not None:
            state[axis] = value
    return emitted


def _rotary_event_line(event, options, profile, *, move=0):
    """Serialize one verified rotary state change without inventing XYZ motion."""
    if event.old_abc is None or event.new_abc is None:
        raise ValueError("Rotary event is missing resolved ABC coordinates")
    unsupported = [axis for axis in event.axes if axis not in options.rotary_axes]
    if unsupported:
        raise ExportLimitation(
            "Selected post cannot represent rotary address " + ", ".join(unsupported),
            code="UNSUPPORTED_AXIS_EXPANDED_EXPORT",
        )
    command = profile["motion"]["rapidMove" if move == 0 else "linearMove"]
    if options.leading_zero and command in {"G0", "G1"}:
        command = command[0] + "0" + command[1:]
    tokens = {"motion": command}
    for axis in event.axes:
        index = _ABC_INDEX[axis]
        value = event.new_abc[index]
        if options.incremental:
            value -= event.old_abc[index]
        tokens[axis.lower()] = _word(axis, value, options)
    order = options.word_order or ("motion", "a", "b", "c")
    words = [tokens[key] for key in order if tokens.get(key)]
    for key in ("motion", "a", "b", "c"):
        if key not in order and tokens.get(key):
            words.append(tokens[key])
    return (" " if options.delimiter else "").join(words)


def _tcp_start_after_motion(step, event):
    return event.kind == "TCP_CONTROL_ON" and event.code == "G43.4" and step.emitted_count > 0


def _append_deferred_tcp_start(lines, step, profile, active):
    if any(_tcp_start_after_motion(step, event) for event in step.events):
        event = next(event for event in step.events if _tcp_start_after_motion(step, event))
        lines.extend(_tcp_control_lines(event, profile))
        return True
    return active


def _resolved_twp_step(step, result):
    """G68.2 defines the frame; the following G53.1 supplies its solved index."""
    if not any(event.kind == "TILTED_WORK_PLANE_ON" for event in step.events):
        return step
    for candidate in result.execution_steps[step.occurrence : step.occurrence + 2]:
        if any(event.kind == "TOOL_AXIS_ORIENT" for event in candidate.events):
            return replace(step, rotary_angles=candidate.rotary_angles)
    return step


def _step_multiaxis_control_lines(step, options, profile, rotary_state, motion_state, result):
    """Reconstruct target rotary/TCP control frames from controller-neutral events."""
    lines: list[str] = []
    step = _resolved_twp_step(step, result)
    supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
    for event in step.events:
        if event.kind in {"TILTED_WORK_PLANE_ON", "TILTED_WORK_PLANE_OFF"}:
            lines.extend(_twp_control_lines(event, step, options, profile))
            motion_state.clear()
        elif event.kind == "ROTARY_INDEX" and event.code == "CYCLE800":
            continue
        elif (
            event.kind == "ROTARY_INDEX" or event.kind == "ROTARY_MOTION" and step.emitted_count == 0
        ) and not _reference_owns_rotary(step, event):
            move = step.modal_move if event.kind == "ROTARY_MOTION" else 0
            lines.append(_rotary_event_line(event, options, profile, move=move))
            motion_state["last"] = move
            if rotary_state is not None and event.new_abc is not None:
                for axis in event.axes:
                    rotary_state[axis] = event.new_abc[_ABC_INDEX[axis]]
        elif event.kind in {"TCP_CONTROL_ON", "TCP_CONTROL_OFF"} and not _tcp_start_after_motion(step, event):
            if not supports_tcp:
                raise ExportLimitation(
                    "Selected post cannot reconstruct TCP control",
                    code="UNSUPPORTED_TCP_EXPANDED_EXPORT",
                )
            lines.extend(_tcp_control_lines(event, profile))
    return lines


def _step_tcp_state(step, active):
    """Return source TCP state after applying this step's semantic edges."""
    for event in step.events:
        if event.kind == "TCP_CONTROL_ON" and not _tcp_start_after_motion(step, event):
            active = True
        elif event.kind == "TCP_CONTROL_OFF":
            active = False
    return active


def _reference_owns_rotary(step, rotary_event):
    return any(event.reference is not None and set(rotary_event.axes) <= set(event.axes) for event in step.events)


def _tcp_control_lines(event, profile):
    multiaxis = profile["multiaxis"]
    if event.kind == "TCP_CONTROL_OFF":
        command = _render(multiaxis["tcpOff"])
        if command == "G49" and event.code == "G43":
            # The ordinary G43 emitted for this block cancels TCP itself;
            # a following G49 would cancel its newly selected length offset.
            return []
        return [command, "D0"] if command == "TRAFOOF" and event.code == "G49" else [command]
    command = _render(multiaxis["tcpOn"])
    if event.length_offset is None:
        return [command]
    offset = event.length_offset
    cross_controller = (command == "G43.4") != (event.code == "G43.4")
    if cross_controller:
        # Supported tool-table convention: FANUC H equals the tool number;
        # SINUMERIK uses the first cutting edge D1 of that same tool.
        tool_word = (event.tool or "").removeprefix("T")
        tool = int(tool_word) if tool_word.isdecimal() else None
        valid = tool is not None and (offset == 1 if command == "G43.4" else offset == tool)
        if not valid:
            raise ExportLimitation(
                "TCP offset conversion requires a numbered tool with FANUC H=tool / SINUMERIK D1",
                code="UNSUPPORTED_TCP_OFFSET_EXPANDED_EXPORT",
            )
        offset = tool if command == "G43.4" else 1
    if command == "G43.4":
        return [f"{command} H{offset}"]
    return [f"D{offset}", command]


def _twp_euler(matrix, *, zxz):
    if zxz:
        middle = math.acos(max(-1.0, min(1.0, matrix[2][2])))
        if abs(math.sin(middle)) < 1e-10:
            first, last = math.atan2(matrix[1][0], matrix[0][0]), 0.0
        else:
            first = math.atan2(matrix[0][2], -matrix[1][2])
            last = math.atan2(matrix[2][0], matrix[2][1])
    else:
        middle = math.asin(max(-1.0, min(1.0, -matrix[2][0])))
        if abs(math.cos(middle)) < 1e-10:
            first, last = math.atan2(-matrix[0][1], matrix[1][1]), 0.0
        else:
            first = math.atan2(matrix[1][0], matrix[0][0])
            last = math.atan2(matrix[2][1], matrix[2][2])
    return tuple(math.degrees(v) for v in (first, middle, last))


def _twp_control_lines(event, step, options, profile):
    fanuc = profile["id"] == "fanuc_mill_multiaxis"
    if event.kind == "TILTED_WORK_PLANE_OFF":
        return ["G69" if fanuc else "CYCLE800()"]
    angles = _twp_euler(event.twp_orientation, zxz=fanuc)
    origin = event.twp_origin
    if fanuc:
        words = [_word(axis, value, options) for axis, value in zip("IJK", angles, strict=True)]
        xyz = " ".join(
            _word(axis, value / options.output_unit_scale, options) for axis, value in zip("XYZ", origin, strict=True)
        )
        rotary = dict(step.rotary_angles)
        axes = [axis for axis in options.rotary_axes if axis in rotary]
        index = "G0 " + " ".join(_word(axis, rotary.get(axis, 0.0), options) for axis in axes)
        return ["G69", index, f"G68.2 {xyz} " + " ".join(words), "G53.1"]
    values = [format(v, ".9f").rstrip("0").rstrip(".") or "0" for v in angles]
    rotary = dict(step.rotary_angles)
    first_axis = "A" if "A" in rotary and rotary["A"] else "B"
    principal = (rotary.get(first_axis, 0) + 180) % 360 - 180
    direction = -1 if principal < 0 else 1
    xyz = ",".join(_word("", value / options.output_unit_scale, options) for value in origin)
    return [f'CYCLE800(0,"",0,27,{xyz},{",".join(values)},0,0,0,{direction},,0)']


def _work_offset_comments(result, profile):
    used = {step.active_wcs for step in result.execution_steps}
    return [
        _render(
            profile["comment"]["template"],
            text=f"G{code} work offset mm: X{offset[0]:.6f} Y{offset[1]:.6f} Z{offset[2]:.6f}",
        )
        for code, offset in result.wcs_offsets
        if code in used and any(value != 0 for value in offset)
    ]


def _twp_motion_options(step, options):
    # A live tilted frame receives local XYZ; explicit ABC is prohibited.
    if step.twp_orientation is not None:
        return replace(options, rotary_values={}, rotary_start_values={})
    return options


def _step_twp_geometry(motion, step, options):
    if step.twp_orientation is None:
        return motion
    offset = (options.work_offsets or {}).get(step.active_wcs, (0.0, 0.0, 0.0))
    origin = step.twp_origin or (0.0, 0.0, 0.0)
    return replace(
        motion,
        orientation=step.twp_orientation,
        orientation_offset=tuple(offset[i] + origin[i] for i in range(3)),
    )
