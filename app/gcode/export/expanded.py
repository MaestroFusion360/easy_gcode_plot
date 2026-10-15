"""Resolved geometry and machine states to configurable controller NC."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .. import post_profiles
from ..kernel.runtime.events import HOME_RETURN, PROGRAM_START, SUBPROGRAM_START, TOOL_CHANGE
from ..post_profiles import _render, load_post_profile, select_cycle_profile
from .common import (
    ExportLimitation,
    ExportOptions,
    _check_cancelled,
    _execution_slices,
    _expanded_word,
    _word,
    _word_required,
)
from .full import is_native_full_program
from .motions import _append_expanded_motion, _invalidate_subdivided_feed, _post_motion_geometry
from .multiaxis import (
    _append_deferred_tcp_start,
    _step_multiaxis_control_lines,
    _step_rotary_values,
    _step_tcp_state,
    _step_twp_geometry,
    _twp_motion_options,
    _work_offset_comments,
)
from .operations import _append_resolved_operations
from .post_options import _post_options, _source_comment_lines
from .preflight import _check_supports, _profile_axes, _require_valid_trace_export, _uses_rotary_geometry
from .tool_numbers import MillingLengthOutput, named_tools, target_tool_numbers, tool_mapping_lines

MILLING_TARGETS = post_profiles.MILLING_TARGETS
POST_TARGETS = post_profiles.POST_TARGETS


def default_target_post(result, *, lathe_gcode_system=None):
    """Select the source controller consistently for direct and file export."""
    if result.source_dialect == "heidenhain":
        return "heidenhain_itnc530"
    if result.language == "fanuc_turn":
        return "fanuc_lathe_" + (lathe_gcode_system or result.lathe_gcode_system).lower()
    if is_native_full_program(result):
        return "sinumerik_840d"
    return "sinumerik_iso" if result.source_dialect == "sinumerik" else "fanuc_mill"


def export_result(result, options=None, *, cancelled=None, target=None, sinumerik_840d_sl=None):
    """Postprocess resolved execution through one controller profile."""
    if target is None:
        if result is None:
            raise ValueError("EXPANDED requires a valid execution result")
        target = default_target_post(result)
    return convert_resolved_program(result, target, options, cancelled=cancelled, sinumerik_840d_sl=sinumerik_840d_sl)


@dataclass
class _PostState:
    motion_index: int = 0
    feed_mode: str = "per_minute"
    spindle_direction: int = 3
    plane: int = 17
    spindle: object = None
    comments: set[int] = field(default_factory=set)
    feed: dict = field(default_factory=lambda: {"last": None})
    motion: dict = field(default_factory=lambda: {"last": None})
    rotary: dict[str, float] = field(default_factory=dict)
    tcp_active: bool = False
    active_wcs: int = 54


def convert_resolved_program(result, target="fanuc_mill", options=None, *, cancelled=None, sinumerik_840d_sl=None):
    """Flatten cycles/variables/transforms into physical XYZ motion and controls.

    Ordinary paths use a zero-offset G54 frame. Tilted-plane programs retain
    G54-G59 selection; their required target work offsets are listed in comments.
    """
    _check_cancelled(cancelled)
    if result is None:
        raise ValueError("EXPANDED requires a valid execution result")
    profile = select_cycle_profile(
        load_post_profile(target), result.sinumerik_840d_sl if sinumerik_840d_sl is None else sinumerik_840d_sl
    )
    if profile.get("id") == "heidenhain_itnc530":
        from .heidenhain import export_heidenhain  # pylint: disable=import-outside-toplevel

        return export_heidenhain(result, profile, options, cancelled=cancelled)
    turning = result.language == "fanuc_turn"
    if (profile["machine"] == "lathe") != turning:
        raise ValueError("Post profile machine does not match the executed geometry")
    _require_valid_trace_export(result, profile, allow_inverse_time=bool(profile["feed"]["inverseTime"]))
    profile_axes = _profile_axes(profile)
    rotary_supported = bool({"A", "B", "C"} & set(profile_axes))
    if _uses_rotary_geometry(result) and not rotary_supported:
        raise ExportLimitation(
            "Selected post supports only three-axis XYZ conversion",
            code="UNSUPPORTED_MULTIAXIS_EXPANDED_EXPORT",
        )
    options = _resolved_post_options(result, options, profile)
    tilted = options.preserve_wcs
    context = {
        "programName": next((event.code for event in result.events if event.kind == PROGRAM_START), "") or "",
        "units": profile["units"]["inch" if options.output_unit_scale == 25.4 else "metric"],
    }
    lines, tool_numbers, source_names, length_output = _program_output_setup(result, options, profile, context)
    state = _PostState(plane=18 if turning else 17)
    for step, block, motions in _execution_slices(result):
        _check_cancelled(cancelled)
        _append_source_comments(lines, block, state.comments, options, profile)
        if tilted and step.active_wcs != state.active_wcs:
            lines.append(f"G{step.active_wcs}")
            state.active_wcs = step.active_wcs
        lines.extend(_tool_change_lines(step, profile, tool_numbers=tool_numbers, source_names=source_names))
        lines.extend(length_output.lines(step))
        lines.extend(_step_multiaxis_control_lines(step, options, profile, state.rotary, state.motion, result))
        state.tcp_active = _step_tcp_state(step, state.tcp_active)
        spindle_lines, state.spindle = _spindle_state_lines(step, state.spindle, options, profile)
        lines.extend(spindle_lines)
        lines.extend(
            _home_lines(
                step,
                motions,
                options,
                profile,
                next_motion=result.motions[state.motion_index] if state.motion_index < len(result.motions) else None,
            )
        )
        controls = _step_machine_controls(step, options, turning, profile)
        if controls:
            lines.append(" ".join(controls))
        state.spindle_direction = _step_spindle_direction(lines, step, state.spindle_direction, profile)
        _append_step_motions(lines, step, motions, options, state, profile, cancelled)
        state.tcp_active = _append_deferred_tcp_start(lines, step, profile, state.tcp_active)
    lines.extend(_program_end_lines(profile, options, context))
    numbered = _number_lines(lines, options)
    mode_line = _mode_line(profile, context)
    if mode_line:
        numbered.insert(0, mode_line)
    return "\n".join(numbered) + "\n"


def _program_header_lines(profile, options: ExportOptions, context) -> list[str]:
    lines = [_render(line, **context) for line in profile["program"]["preamble"]]
    lines.append(context["units"])
    position = profile["positioning"]["incremental" if options.incremental else "absolute"]
    if position:
        lines.append(position)
    start = options.start_program if options.start_program else profile["program"]["start"]
    header = _render(start, **context).splitlines()
    if options.safety_line:
        header.extend(_safety_lines(profile, options, context))
    return header + lines


def _resolved_post_options(result, options, profile):
    options = _post_options(options, profile)
    tilted = any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events)
    options = replace(options, preserve_wcs=tilted, work_offsets=dict(result.wcs_offsets))
    _check_supports(result, profile, options)
    if options.incremental and tilted:
        raise ExportLimitation(
            "Tilted-plane output requires absolute coordinates", code="UNSUPPORTED_TWP_EXPANDED_EXPORT"
        )
    return options


def _program_output_setup(result, options, profile, context):
    lines = _program_header_lines(profile, options, context)
    mapping = target_tool_numbers(result, profile, options.tool_numbers)
    lines.extend(tool_mapping_lines(mapping, profile))
    lines.extend(_work_offset_comments(result, profile) if options.preserve_wcs else [])
    return lines, mapping, named_tools(result), MillingLengthOutput(result, profile, mapping)


def _safety_lines(profile, options: ExportOptions, context) -> list[str]:
    """Emit the profile-declared safe restart block after user program start text."""
    safety = profile["program"].get("safety")
    if not safety:
        return []
    return [_render(line, **context) for line in safety]


def _program_end_lines(profile, options: ExportOptions, context) -> list[str]:
    if options.end_program.strip():
        return options.end_program.strip().splitlines()
    return _render(profile["program"]["end"], **context).splitlines()


def _tool_change_lines(step, profile, *, tool_numbers=None, source_names=()) -> list[str]:
    lines = []
    for event in step.events:
        if event.kind != TOOL_CHANGE:
            continue
        code = "" if event.code == event.tool else event.code or ""
        if code == "TOOL CALL":
            code = "M06"
        tool = (tool_numbers or {}).get(event.tool, event.tool or "T0")
        if event.tool in source_names and not tool_numbers:
            tool = f'T="{event.tool}"'
        line = _render(profile["tool"]["toolChange"], tool=tool, code=code)
        if line:
            lines.append(line)
    return lines


def _mode_line(profile, context) -> str:
    mode = str(profile["program"].get("mode", "") or "")
    return _render(mode, **context) if mode else ""


def _append_source_comments(lines, block, emitted, options, profile):
    if block.index in emitted:
        return
    lines.extend(_source_comment_lines(block.raw, options, profile))
    emitted.add(block.index)


def _home_lines(step, motions, options, profile, *, next_motion):
    lines = []
    for event in step.events:
        if event.kind != HOME_RETURN or event.code not in {"G28", "G53"} or motions:
            continue
        if step.programmed_position is not None:
            # The milling kernel resolved this return at the current position.
            # No motion is different from an unknown reference position.
            continue
        if next_motion is not None and (options.incremental or next_motion.move != 0):
            raise ValueError("Unresolved reference return requires an absolute rapid before later geometry")
        if any(value != 0 for letter, value in step.words if letter in "XYZUVW"):
            raise ValueError("Unresolved reference return with an intermediate position")
        for axis in event.axes:
            command = profile["home"][event.code].get(axis)
            if not command:
                raise ValueError(f"Post cannot resolve {event.code} return on {axis}")
            lines.append(_render(command))
        position = profile["positioning"]["incremental" if options.incremental else "absolute"]
        if position:
            lines.append(position)
    return lines


def _step_machine_controls(step, options, turning, profile):
    if any(event.kind == SUBPROGRAM_START and event.code == "G65" for event in step.events):
        return []
    commands = {
        0: profile["program"]["stop"],
        1: profile["program"]["optionalStop"],
        3: profile["spindle"]["cw"],
        4: profile["spindle"]["ccw"],
        5: profile["spindle"]["stop"],
        7: profile["coolant"]["mist"],
        8: profile["coolant"]["flood"],
        9: profile["coolant"]["off"],
    }
    return [
        _expanded_word(letter, value, options) if letter == "S" else _render(commands[value])
        for letter, value in step.words
        if letter == "S" and not turning or letter == "M" and value in commands
    ]


def _step_spindle_direction(lines, step, previous, profile):
    direction = next(
        (int(value) for letter, value in reversed(step.words) if letter == "M" and value in (3, 4)), previous
    )
    native_tap = any(signal.code == "CYCLE84" and signal.kind == "spindle_reverse" for signal in step.signals)
    if native_tap and direction != 3:
        lines.append(profile["spindle"]["cw"])
        direction = 3
    return direction


def _emit_modal_feed(motion, options, feed_state):
    """Return True when this motion must restate F because feed/mode changed."""
    if not options.modal_feed or feed_state is None:
        return True
    if motion.move == 0 or motion.feed is None:
        # Rapids never carry F and an unset feed cannot become modal.
        return True
    current = (motion.feed_mode, motion.feed)
    if feed_state.get("last") == current:
        return False
    feed_state["last"] = current
    return True


def _emit_modal_motion(move, options, motion_state):
    """Return True when this frame must restate its motion code.

    A post profile sets ``format.words.motion.required`` to ``false`` to make the
    motion code modal: it is emitted only when the motion code changes.
    """
    if _word_required(options, "motion", default=True) or motion_state is None:
        return True
    if motion_state.get("last") == move:
        return False
    motion_state["last"] = move
    return True


def _append_step_motions(lines, step, motions, options, state, profile, cancelled):
    motion_index, feed_mode, plane = state.motion_index, state.feed_mode, state.plane
    direction = state.spindle_direction
    feed_state, motion_state, rotary_state = state.feed, state.motion, state.rotary
    source_tcp_active = state.tcp_active
    motions, feed_mode, plane = _append_resolved_operations(
        lines,
        step,
        motions,
        options,
        profile,
        feed_mode,
        plane,
        motion_state,
        feed_state,
        rotary_state,
        source_tcp_active,
        direction,
    )
    motion_index += step.emitted_count - len(motions)
    step_options = options
    if options.rotary_axes and motions:
        start_values = dict(rotary_state or {})
        step_options = replace(
            options,
            rotary_start_values=start_values,
            rotary_values=_step_rotary_values(step, options, rotary_state),
        )
    step_options = _twp_motion_options(step, step_options)
    dwell, reverse = _step_motion_signals(step, motions)
    continuous_rotary = any(event.kind == "ROTARY_MOTION" for event in step.events) and not source_tcp_active
    feeds = 0
    for motion in motions:
        _check_cancelled(cancelled)
        motion = _post_motion_geometry(
            _step_twp_geometry(motion, step, options),
            step_options,
            source_tcp_active=source_tcp_active,
            continuous_rotary=continuous_rotary,
        )
        if motion.plane != plane:
            lines.append(profile["motion"][{17: "planeXY", 18: "planeXZ", 19: "planeYZ"}[motion.plane]])
            plane = motion.plane
        if motion.feed_mode != feed_mode:
            lines.append(
                profile["feed"][
                    {"per_minute": "perMinute", "per_revolution": "perRev", "inverse_time": "inverseTime"}[
                        motion.feed_mode
                    ]
                ]
            )
            feed_mode = motion.feed_mode
        if motion.move == 1 and reverse and feeds == 1:
            lines.append(profile["spindle"]["ccw" if direction == 3 else "cw"])
        threading = motion.move == 1 and motion.threading
        effective_move = 32 if threading else motion.move
        _append_expanded_motion(
            lines,
            motion,
            step_options,
            motion_index,
            override_move=32 if threading else None,
            profile=profile,
            cancelled=cancelled,
            emit_feed=_emit_modal_feed(motion, options, feed_state),
            include_motion=_emit_modal_motion(effective_move, options, motion_state),
        )
        _invalidate_subdivided_feed(motion, feed_state)
        motion_index += 1
        if motion.move == 1:
            feeds += 1
        if feeds == 1 and dwell:
            lines.append(_dwell_line(dwell, options, profile))
            dwell = 0
        if reverse and feeds == 2:
            lines.append(profile["spindle"]["cw" if direction == 3 else "ccw"])
            reverse = False
    if dwell:
        lines.append(_dwell_line(dwell, options, profile))
    state.motion_index, state.feed_mode, state.plane = motion_index, feed_mode, plane


def _dwell_line(seconds, options, profile):
    return _render(
        profile["dwell"]["command"],
        dwell=_expanded_word(profile["dwell"]["address"], seconds * profile["dwell"]["scale"], options),
    )


def _step_motion_signals(step, motions):
    if not motions and step.emitted_count and any(event.drilling is not None for event in step.events):
        return 0, False
    return (
        sum(signal.value or 0 for signal in step.signals if signal.kind == "dwell"),
        any(signal.kind == "spindle_reverse" for signal in step.signals),
    )


def _spindle_state_lines(step, previous, options, profile):
    if profile["machine"] != "lathe":
        return [], previous
    state = (step.spindle_mode, step.spindle_rpm, step.surface_speed_m_min, step.spindle_limit_rpm)
    if state == previous:
        return [], state
    lines = []
    if step.spindle_limit_rpm is not None and (previous is None or previous[3] != step.spindle_limit_rpm):
        lines.append(
            _render(
                profile["spindle"]["maxSpeed"],
                speed=_expanded_word("S", step.spindle_limit_rpm, options),
                value=_word("", step.spindle_limit_rpm, options),
            )
        )
    value = step.surface_speed_m_min if step.spindle_mode == "css" else step.spindle_rpm
    if step.spindle_mode == "css" and options.output_unit_scale == 25.4 and value is not None:
        value /= 0.3048
    if value is not None:
        lines.append(
            _render(
                profile["spindle"]["cssOn" if step.spindle_mode == "css" else "cssOff"],
                speed=_expanded_word("S", value, options),
                value=_word("", value, options),
            )
        )
    return lines, state


def _number_lines(lines: list[str], options: ExportOptions) -> list[str]:
    if not options.sequence_numbers:
        return lines
    out: list[str] = []
    seq = options.sequence_start
    spacer = " " if options.sequence_spacing or options.delimiter else ""
    for line in lines:
        if not line or line == "%" or line.lstrip().startswith(("(", ";")) or line.lstrip().upper().startswith("O"):
            out.append(line)
            continue
        out.append(f"N{seq}{spacer}{line}")
        seq += options.sequence_increment
    return out
