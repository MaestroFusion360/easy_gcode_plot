"""Resolved geometry and machine states to configurable controller NC."""

from __future__ import annotations

import json
import math
from dataclasses import replace

from .. import post_profiles
from ..comments import extract_comments
from ..drilling_post import emit_drilling_operation
from ..kernel import ExecutionResult, TraceMotion
from ..kernel.geometry.arc_segments import split_arc
from ..kernel.milling.kinematics import MachineKinematics, RotaryAxis, point_orientation, transform_point
from ..kernel.runtime.events import HOME_RETURN, PROGRAM_START, SUBPROGRAM_START, TOOL_CHANGE
from ..post_profiles import _FORMAT_WORD_TOKENS, _render, load_post_profile, select_cycle_profile
from ..trace_tools import arc_geometry, sample_motion
from .common import (
    ExportLimitation,
    ExportOptions,
    _check_cancelled,
    _compact_post_line,
    _execution_slices,
    _expanded_word,
    _require_continuous_motions,
    _word,
    _word_format,
    _word_required,
    motion_line,
    scale_motion,
)

MILLING_TARGETS = post_profiles.MILLING_TARGETS
POST_TARGETS = post_profiles.POST_TARGETS


def _append_expanded_motion(
    lines: list[str],
    motion: TraceMotion,
    options: ExportOptions,
    index: int,
    *,
    override_move: int | None = None,
    profile: dict,
    cancelled=None,
    emit_feed: bool = True,
    include_motion: bool = True,
) -> None:
    if (
        motion.arc is not None
        and motion.arc.sweep > math.tau + 1e-10
        and options.arc_mode != 3
        and not options.multi_turn_arcs
    ):
        split_angle = math.radians(options.radius_split_angle if options.arc_mode == 2 else options.arc_split_angle)
        count = max(1, math.ceil(motion.arc.sweep / split_angle))
        for position, segment in enumerate(split_arc(motion, split_angle)):
            _check_cancelled(cancelled)
            segment = _segment_motion_feed(segment, count)
            _append_expanded_motion(
                lines,
                segment,
                _segment_rotary_options(options, position / count, (position + 1) / count),
                index,
                override_move=override_move,
                profile=profile,
                cancelled=cancelled,
                emit_feed=emit_feed and position == 0,
                include_motion=include_motion,
            )
        return
    motion = scale_motion(motion, options.output_unit_scale)
    formatting = replace(options, delimiter=True)

    if (
        options.arc_mode == 2
        and motion.arc is not None
        and motion.arc.full_circle
        and options.full_circle == "two_half"
    ):
        axes = {17: (0, 1, 2), 18: (0, 2, 1), 19: (1, 2, 0)}
        a, b, other = axes[motion.plane]
        start = [motion.start_x * motion.x_scale, motion.start_y, motion.start_z]
        end = [motion.end_x * motion.x_scale, motion.end_y, motion.end_z]
        center = motion.arc.center
        midpoint = list(start)
        midpoint[a] = 2.0 * center[a] - start[a]
        midpoint[b] = 2.0 * center[b] - start[b]
        midpoint[other] = (start[other] + end[other]) / 2.0
        midpoint_x = midpoint[0] / motion.x_scale
        half_arc = replace(motion.arc, sweep=3.141592653589793, full_circle=False)
        first = replace(
            motion,
            end_x=midpoint_x,
            end_y=midpoint[1],
            end_z=midpoint[2],
            arc=half_arc,
        )
        second = replace(
            motion,
            start_x=midpoint_x,
            start_y=midpoint[1],
            start_z=midpoint[2],
            arc=half_arc,
        )
        first = _segment_motion_feed(first, 2)
        second = _segment_motion_feed(second, 2)
        lines.append(
            _post_motion_line(
                motion_line(
                    first,
                    _segment_rotary_options(formatting, 0.0, 0.5),
                    override_move=override_move,
                    include_feed=emit_feed,
                    include_motion=include_motion,
                ),
                first.move if override_move is None else override_move,
                options,
                profile,
            )
        )
        lines.append(
            _post_motion_line(
                motion_line(
                    second,
                    _segment_rotary_options(formatting, 0.5, 1.0),
                    override_move=override_move,
                    include_feed=False,
                ),
                second.move if override_move is None else override_move,
                options,
                profile,
            )
        )
        return
    if options.arc_mode == 3 and motion.move in (2, 3):
        for line in _linearized_lines(motion, formatting, index, emit_feed=emit_feed, include_motion=include_motion):
            lines.append(_post_motion_line(line, 1, options, profile))
    else:
        lines.append(
            _post_motion_line(
                motion_line(
                    motion,
                    formatting,
                    override_move=override_move,
                    include_feed=emit_feed,
                    include_motion=include_motion,
                ),
                motion.move if override_move is None else override_move,
                options,
                profile,
            )
        )


def _map_motion_word(word, options, profile):
    if options.incremental:
        axes = profile["positioning"]["incrementalAxes"]
        word = axes.get(word[0], word[0]) + word[1:]
    if word.startswith("R"):
        word = profile["format"]["radiusAddress"] + word[1:]
    return word


def _post_motion_line(line, move, options, profile):
    words = line.split()
    if options.arc_mode == 3 and move in (2, 3):
        move = 1
    key = {0: "rapidMove", 1: "linearMove", 2: "circularMoveCW", 3: "circularMoveCCW"}.get(move, "threadMove")
    command = profile["motion"][key]
    if options.leading_zero and command in {"G0", "G1", "G2", "G3"}:
        command = command[0] + "0" + command[1:]
    command_word = next((word for word in words if word.upper().startswith("G")), "")
    mapped = [(word if word is command_word else _map_motion_word(word, options, profile)) for word in words]
    separator = " " if options.delimiter else ""
    if "{" in command:
        rest = [word for word in mapped if word is not command_word]
        coords = separator.join(word for word in rest if not word.startswith("F"))
        feed = separator.join(word for word in rest if word.startswith("F"))
        return _render(command, coord=coords, feed=feed)
    final = [command if word is command_word else word for word in mapped]
    return separator.join(final)


def export_result(result, options=None, *, cancelled=None, target=None, sinumerik_840d_sl=None):
    """Postprocess resolved execution through one controller profile."""
    if target is None:
        if result is None:
            raise ValueError("EXPANDED requires a valid execution result")
        target = "fanuc_lathe_" + result.lathe_gcode_system.lower() if result.language == "fanuc_turn" else "fanuc_mill"
    return convert_resolved_program(result, target, options, cancelled=cancelled, sinumerik_840d_sl=sinumerik_840d_sl)


def convert_resolved_program(result, target="fanuc_mill", options=None, *, cancelled=None, sinumerik_840d_sl=None):
    """Flatten cycles/variables/transforms into physical XYZ motion and controls.

    Coordinates use one G54 frame with zero offsets; controller offset tables
    and source structure are deliberately absent from this resolved program.
    """
    _check_cancelled(cancelled)
    if result is None:
        raise ValueError("EXPANDED requires a valid execution result")
    profile = select_cycle_profile(
        load_post_profile(target), result.sinumerik_840d_sl if sinumerik_840d_sl is None else sinumerik_840d_sl
    )
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
    options = _post_options(options, profile)
    _check_supports(result, profile, options)
    context = {
        "programName": next((event.code for event in result.events if event.kind == PROGRAM_START), "") or "",
        "units": profile["units"]["inch" if options.output_unit_scale == 25.4 else "metric"],
    }
    lines = _program_header_lines(profile, options, context)
    motion_index, feed_mode, spindle_direction, plane = 0, "per_minute", 3, 18 if turning else 17
    spindle_state = None
    emitted_comment_blocks: set[int] = set()
    feed_state: dict[str, object] = {"last": None}
    motion_state: dict[str, object] = {"last": None}
    rotary_state: dict[str, float] = {}
    source_tcp_active = False
    for step, block, motions in _execution_slices(result):
        _check_cancelled(cancelled)
        _append_source_comments(lines, block, emitted_comment_blocks, options, profile)
        lines.extend(_tool_change_lines(step, profile))
        lines.extend(_step_multiaxis_control_lines(step, options, profile, rotary_state, motion_state))
        source_tcp_active = _step_tcp_state(step, source_tcp_active)
        spindle_lines, spindle_state = _spindle_state_lines(step, spindle_state, options, profile)
        lines.extend(spindle_lines)
        lines.extend(
            _home_lines(
                step,
                motions,
                options,
                profile,
                next_motion=result.motions[motion_index] if motion_index < len(result.motions) else None,
            )
        )
        controls = _step_machine_controls(step, options, turning, profile)
        if controls:
            lines.append(" ".join(controls))
        spindle_direction = _step_spindle_direction(lines, step, spindle_direction, profile)
        motion_index, feed_mode, plane = _append_step_motions(
            lines,
            step,
            motions,
            options,
            motion_index,
            feed_mode,
            spindle_direction,
            cancelled,
            plane,
            profile,
            feed_state,
            motion_state,
            rotary_state,
            source_tcp_active,
        )
        source_tcp_active = _append_deferred_tcp_start(lines, step, profile, source_tcp_active)
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


def _tool_change_lines(step, profile) -> list[str]:
    lines = []
    for event in step.events:
        if event.kind != TOOL_CHANGE:
            continue
        code = "" if event.code == event.tool else event.code or ""
        line = _render(profile["tool"]["toolChange"], tool=event.tool or "", code=code)
        if line:
            lines.append(line)
    return lines


def _mode_line(profile, context) -> str:
    mode = str(profile["program"].get("mode", "") or "")
    return _render(mode, **context) if mode else ""


def _uses_y_axis(result: ExecutionResult) -> bool:
    return any(
        abs(motion.start_y) > 1e-12 or abs(motion.end_y) > 1e-12 or motion.plane in (17, 19)
        for motion in result.motions
    )


def _check_supports(result: ExecutionResult, profile: dict, options: ExportOptions) -> None:
    """Declared post capabilities fail closed before any output is written."""
    supports = profile.get("supports")
    if not supports:
        return
    _check_supports_axes(result, supports)
    _check_supports_arcs(result, supports, options)
    _check_supports_feed(result, supports)


def _check_supports_axes(result: ExecutionResult, supports: dict) -> None:
    axes = set(supports.get("axes", ("X", "Y", "Z")))
    rotary_axes = {axis for event in result.events for axis in event.axes if event.kind.startswith("ROTARY_")}
    if not {"X", "Z"} <= axes or ("Y" not in axes and _uses_y_axis(result)) or not rotary_axes <= axes:
        raise ExportLimitation(
            "Selected post supports only axes " + ", ".join(sorted(axes)),
            code="UNSUPPORTED_AXIS_EXPANDED_EXPORT",
        )


def _check_supports_arcs(result: ExecutionResult, supports: dict, options: ExportOptions) -> None:
    multi_turn = any(motion.arc is not None and motion.arc.sweep > math.tau + 1e-10 for motion in result.motions)
    if not supports.get("multiTurnArcs", True) and options.multi_turn_arcs and multi_turn:
        raise ExportLimitation(
            "Selected post cannot emit multi-turn arcs",
            code="UNSUPPORTED_MULTITURN_ARC_EXPANDED_EXPORT",
        )
    if not supports.get("absoluteArcCenters", True) and options.arc_mode == 1:
        raise ExportLimitation(
            "Selected post does not support absolute arc centers",
            code="UNSUPPORTED_ABSOLUTE_ARC_EXPANDED_EXPORT",
        )


def _check_supports_feed(result: ExecutionResult, supports: dict) -> None:
    inverse_time = any(motion.feed_mode == "inverse_time" for motion in result.motions)
    if not supports.get("inverseTime", True) and inverse_time:
        raise ExportLimitation(
            "Selected post cannot represent inverse-time feed (G93)",
            code="UNSUPPORTED_INVERSE_TIME_EXPANDED_EXPORT",
        )


def _append_source_comments(lines, block, emitted, options, profile):
    if block.index in emitted:
        return
    lines.extend(_source_comment_lines(block.raw, options, profile))
    emitted.add(block.index)


def _profile_axes(profile: dict) -> tuple[str, ...]:
    """Return the axes a post profile declares it supports (default XYZ)."""
    supports = profile.get("supports") or {}
    return tuple(supports.get("axes", ["X", "Y", "Z"]))


def _uses_rotary_geometry(result: ExecutionResult) -> bool:
    """Reject actual rotary/TWP/TCP use, not merely a selected kinematics profile."""
    rotary_events = {"ROTARY_INDEX", "ROTARY_MOTION", "TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"}
    if any(event.kind in rotary_events for event in result.events):
        return True
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for motion in result.motions:
        if motion.orientation is None:
            continue
        if any(
            abs(motion.orientation[row][column] - identity[row][column]) > 1e-9
            for row in range(3)
            for column in range(3)
        ):
            return True
    return False


def _post_options(options, profile):
    defaults = profile["options"]
    arc = profile["format"]
    profile_unit_scale = 25.4 if defaults["units"] == "inch" else 1.0
    if options is None:
        default_arc_mode = (
            3 if not arc["outputArcs"] else 2 if arc["arcMode"] == "R" else int(arc["arcCenter"] == "absolute")
        )
        options = ExportOptions(
            delimiter=defaults["delimiter"],
            leading_zero=defaults["leadingZero"],
            incremental=defaults["incrementalMode"],
            output_unit_scale=profile_unit_scale,
            arc_mode=default_arc_mode,
        )
    elif not options.output_unit_scale_explicit and options.output_unit_scale == 1.0:
        options = replace(options, output_unit_scale=profile_unit_scale)
    if options.arc_mode not in range(4):
        raise ValueError("Arc output must be IJK relative, IJK absolute, radius or linearized")
    word_formats, word_order, word_required = _resolve_format_words(arc.get("words"), defaults["decimalPlaces"])
    return replace(
        options,
        decimal_places=options.decimal_places if options.decimal_places_explicit else defaults["decimalPlaces"],
        force_decimal=options.force_decimal if options.force_decimal_explicit else defaults["forceDecimal"],
        plus_output=options.plus_output if options.plus_output_explicit else defaults["plusOutput"],
        absolute_arc_syntax=arc["absoluteCenterSyntax"] == "AC",
        multi_turn_arcs=arc["multiTurnArcs"],
        arc_mode=3 if not arc["outputArcs"] else options.arc_mode,
        word_formats=word_formats,
        word_order=word_order,
        word_required=word_required,
        rotary_axes=tuple(axis for axis in _profile_axes(profile) if axis in {"A", "B", "C"}),
        turns_word=str(arc.get("turnsWord", options.turns_word)),
        radius_split_angle=float(arc.get("radiusSplitAngle", options.radius_split_angle)),
        arc_split_angle=float(arc.get("arcSplitAngle", options.arc_split_angle)),
        full_circle=str(arc.get("fullCircle", options.full_circle)),
    )


def _resolve_format_words(words, default_decimals: int):
    """Return ``(formats, order, required)`` from a ``format.words`` section.

    ``order`` is a tuple of internal motion-token names sorted by the profile's
    ``order`` field. ``turns`` keeps its legacy position immediately after
    ``motion`` so multi-turn arc serialization is unchanged.
    """
    if not words:
        return None, None, None
    ordered = sorted(words.items(), key=lambda item: item[1]["order"])
    order_tokens: list[str] = []
    required: dict[str, bool] = {}
    formats: dict[str, tuple[int, str]] = {}
    for key, spec in ordered:
        token = _FORMAT_WORD_TOKENS[key]
        order_tokens.append(token)
        required[token] = bool(spec["required"])
        if key != "motion" and ("decimals" in spec or "sign" in spec):
            formats[key] = (int(spec.get("decimals", default_decimals)), str(spec.get("sign", "auto")))
    if "motion" in order_tokens:
        order_tokens.insert(order_tokens.index("motion") + 1, "turns")
    return formats or None, tuple(order_tokens), required


def _source_comment_lines(raw: str, options: ExportOptions, profile: dict) -> list[str]:
    if not options.include_comments:
        return []
    return [
        _render(profile.get("comment", {}).get("template", "({text})"), text=comment)
        for comment in extract_comments(raw)
        if comment.strip()
    ]


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


_ABC_INDEX = {"A": 0, "B": 1, "C": 2}


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
        lines.append(_render(profile["multiaxis"]["tcpOn"]))
        return True
    return active


def _step_multiaxis_control_lines(step, options, profile, rotary_state, motion_state):
    """Reconstruct target rotary/TCP control frames from controller-neutral events."""
    lines: list[str] = []
    multiaxis = profile.get("multiaxis") or {}
    supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
    for event in step.events:
        if (
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
            key = "tcpOn" if event.kind == "TCP_CONTROL_ON" else "tcpOff"
            lines.append(_render(multiaxis[key]))
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


def _inverse_orientation_point(matrix, point):
    """Map one physical point back into the indexed table frame."""
    return tuple(sum(matrix[j][i] * point[j] for j in range(3)) for i in range(3))


def _post_motion_geometry(
    motion: TraceMotion,
    options: ExportOptions,
    *,
    source_tcp_active: bool,
    continuous_rotary: bool = False,
) -> TraceMotion:
    """Return coordinates suitable for the selected multiaxis post.

    Indexed-table traces store physical XYZ plus the table orientation.  A target
    post that also emits the resolved ABC state must receive XYZ in that indexed
    frame, otherwise the target executor would rotate physical XYZ a second time.
    TCP motions deliberately have ``orientation is None`` and remain physical XYZ.
    """
    if not options.rotary_axes or source_tcp_active:
        return motion
    if continuous_rotary:
        if motion.arc is not None or motion.start_tool_orientation is None or motion.tool_orientation is None:
            raise ExportLimitation(
                "Selected post cannot reconstruct this continuous rotary interpolation",
                code="UNSUPPORTED_CONTINUOUS_ROTARY_EXPANDED_EXPORT",
            )
        start = _inverse_orientation_point(
            motion.start_tool_orientation,
            (motion.start_x, motion.start_y, motion.start_z),
        )
        end = _inverse_orientation_point(
            motion.tool_orientation,
            (motion.end_x, motion.end_y, motion.end_z),
        )
        return replace(
            motion,
            start_x=start[0],
            start_y=start[1],
            start_z=start[2],
            end_x=end[0],
            end_y=end[1],
            end_z=end[2],
            orientation=None,
            orientation_offset=(0.0, 0.0, 0.0),
        )
    orientation = motion.orientation
    if orientation is None:
        return motion
    start = _inverse_orientation_point(orientation, (motion.start_x, motion.start_y, motion.start_z))
    end = _inverse_orientation_point(orientation, (motion.end_x, motion.end_y, motion.end_z))
    arc = motion.arc
    if arc is not None:
        normal = None if arc.normal is None else _inverse_orientation_point(orientation, arc.normal)
        arc = replace(
            arc,
            center=_inverse_orientation_point(orientation, arc.center),
            normal=normal,
        )
    vector = _inverse_orientation_point(
        orientation,
        (motion.i or 0.0, motion.j or 0.0, motion.k or 0.0),
    )
    return replace(
        motion,
        start_x=start[0],
        start_y=start[1],
        start_z=start[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        i=vector[0] if motion.i is not None else None,
        j=vector[1] if motion.j is not None else None,
        k=vector[2] if motion.k is not None else None,
        arc=arc,
        orientation=None,
        orientation_offset=(0.0, 0.0, 0.0),
    )


def _append_step_motions(
    lines,
    step,
    motions,
    options,
    motion_index,
    feed_mode,
    direction,
    cancelled,
    plane,
    profile,
    feed_state=None,
    motion_state=None,
    rotary_state=None,
    source_tcp_active=False,
):
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
    dwell, reverse = _step_motion_signals(step, motions)
    continuous_rotary = any(event.kind == "ROTARY_MOTION" for event in step.events) and not source_tcp_active
    feeds = 0
    for motion in motions:
        _check_cancelled(cancelled)
        motion = _post_motion_geometry(
            motion,
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
    return motion_index, feed_mode, plane


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


def _linearized_lines(
    m: TraceMotion, options: ExportOptions, motion_index: int, *, emit_feed: bool = True, include_motion: bool = True
) -> list[str]:
    if arc_geometry(m) is None:
        raise ValueError("Linearized arc export requires resolved arc geometry")
    points = sample_motion(m, motion_index, chord_error=float(options.linearization_tolerance))
    lines: list[str] = []
    previous = (m.start_x, m.start_y, m.start_z)
    repeat_motion = _word_required(options, "motion", default=True)
    for position, point in enumerate(points):
        temp = TraceMotion(
            1,
            previous[0],
            previous[2],
            point.x,
            point.z,
            feed=m.feed * len(points) if m.feed_mode == "inverse_time" and m.feed is not None else m.feed,
            feed_mode=m.feed_mode,
            start_y=previous[1],
            end_y=point.y,
            source_block=m.source_block,
        )
        lines.append(
            motion_line(
                temp,
                _segment_rotary_options(options, position / len(points), (position + 1) / len(points)),
                include_feed=emit_feed and position == 0,
                include_motion=include_motion and (position == 0 or repeat_motion),
            )
        )
        previous = (point.x, point.y, point.z)
    return lines


def _segment_motion_feed(motion, count):
    """Splitting a G93 block must preserve its total duration, 1/F."""
    if motion.feed_mode == "inverse_time" and motion.feed is not None:
        return replace(motion, feed=motion.feed * count)
    return motion


def _invalidate_subdivided_feed(motion, feed_state):
    if motion.feed_mode == "inverse_time" and motion.arc is not None and feed_state is not None:
        # Arc subdivision may have emitted a different F than the source block.
        feed_state.clear()


def _segment_rotary_options(options, start_fraction, end_fraction):
    """Distribute resolved joint angles over the same subdivision as XYZ."""
    if not options.rotary_values:
        return options
    starts = options.rotary_start_values or {}
    values = {}
    segment_starts = {}
    for axis, value in options.rotary_values.items():
        start = starts.get(axis, 0.0)
        delta = value if options.incremental else value - start
        decimals, _sign = _word_format(axis, options)
        values[axis] = (
            round(start + delta * end_fraction, decimals) - round(start + delta * start_fraction, decimals)
            if options.incremental
            else start + delta * end_fraction
        )
        segment_starts[axis] = start + delta * start_fraction
    return replace(options, rotary_values=values, rotary_start_values=segment_starts)


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


def _has_unreconstructable_non_tcp_rotary_motion(result: ExecutionResult) -> bool:
    tcp_active = False
    for step in result.execution_steps:
        for event in step.events:
            if event.kind == "TCP_CONTROL_ON":
                tcp_active = True
            elif event.kind == "TCP_CONTROL_OFF":
                tcp_active = False
            elif event.kind == "ROTARY_MOTION" and not tcp_active and event.kinematics_profile != "4ax_table_c":
                return True
    return False


def _require_reconstructable_index_origin(result):
    """Zero-offset output cannot preserve an index about a displaced WCS origin."""
    offsets = {m.orientation_offset for m in result.motions if any(abs(v) > 1e-9 for v in m.orientation_offset)}
    if not offsets:
        return
    definition = json.loads(result.kinematics_definition) if result.kinematics_definition else None
    table = (
        None
        if definition is None
        else MachineKinematics(
            "resolved",
            "resolved",
            tuple(RotaryAxis(joint["address"], tuple(joint["axis"])) for joint in definition["table_rotary_axes"]),
            (),
        )
    )
    indexed = any(
        event.kind == "ROTARY_INDEX" and any(_index_moves_offset(event, table, offset) for offset in offsets)
        for event in result.events
    )
    if indexed:
        raise ExportLimitation(
            "Indexed rotary export with a displaced WCS requires target frame-offset reconstruction",
            code="UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT",
        )


def _index_moves_offset(event, table, offset):
    if table is None or event.old_abc is None or event.new_abc is None:
        return True
    old = point_orientation(table, dict(zip("ABC", event.old_abc, strict=True)))
    new = point_orientation(table, dict(zip("ABC", event.new_abc, strict=True)))
    moved = transform_point(new, _inverse_orientation_point(old, offset))
    return any(abs(a - b) > 1e-9 for a, b in zip(moved, offset, strict=True))


def _require_valid_trace_export(result: ExecutionResult, profile: dict, *, allow_inverse_time=False) -> None:
    if result is None or not result.ok or not result.complete:
        raise ValueError("EXPANDED requires a valid and complete execution result")
    supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
    if any(event.kind == "TCP_CONTROL_ON" for event in result.events) and not supports_tcp:
        raise ExportLimitation(
            "Selected post cannot preserve G43.4 TCP rotary commands / TRAORI or reconstruct resolved TCP motion",
            code="UNSUPPORTED_TCP_EXPANDED_EXPORT",
        )
    if any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events):
        raise ExportLimitation(
            "Expanded multiaxis export does not yet reconstruct G68.2/CYCLE800 tilted working-plane semantics",
            code="UNSUPPORTED_TWP_EXPANDED_EXPORT",
        )
    if _has_unreconstructable_non_tcp_rotary_motion(result):
        raise ExportLimitation(
            "Expanded multiaxis export cannot reconstruct this non-TCP continuous rotary interpolation",
            code="UNSUPPORTED_CONTINUOUS_ROTARY_EXPANDED_EXPORT",
        )
    _require_reconstructable_index_origin(result)
    _require_continuous_motions(result, allow_reference_rapids=True, allow_rotary_index_gaps=True)
    if not allow_inverse_time and any(m.feed_mode == "inverse_time" for m in result.motions):
        raise ExportLimitation(
            "Selected post cannot represent inverse-time feed (G93)",
            code="UNSUPPORTED_INVERSE_TIME_EXPANDED_EXPORT",
        )
    ignored_native = {
        "IGNORED_SINUMERIK_DIAMETER_MODE",
        "UNMODELED_SINUMERIK_CHF",
        "UNMODELED_SINUMERIK_CHR",
        "UNMODELED_SINUMERIK_RND",
        "UNMODELED_SINUMERIK_RNDM",
        "UNMODELED_SINUMERIK_FRC",
        "UNMODELED_SINUMERIK_FRCM",
        "UNVERIFIED_CUTTER_COMPENSATION",
        "UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION",
    }
    blockers = [
        d.code for d in result.diagnostics if d.code in ignored_native or d.code == "UNMODELED_SINUMERIK_NATIVE"
    ]
    if blockers:
        message = (
            "NC trace export cannot preserve ignored SINUMERIK diameter/corner/feed commands"
            if any("SINUMERIK" in code for code in blockers)
            else "NC trace export cannot preserve unverified cutter compensation"
        )
        raise ExportLimitation(
            message + ": " + ", ".join(sorted(set(blockers))),
            code="UNSUPPORTED_UNVERIFIED_GEOMETRY_EXPANDED_EXPORT",
        )


def _validate_reference_frame(reference):
    if reference.coordinate_space != "machine" or not all(math.isfinite(value) for value in reference.target):
        raise ValueError("Reference event requires finite machine coordinates")


def _reference_line(template, target, axes, reference, options):
    rotary = dict(reference.rotary_target)
    words = [
        _expanded_word(
            axis, target["XYZ".index(axis)] / options.output_unit_scale if axis in "XYZ" else rotary[axis], options
        )
        for axis in axes
    ]
    feed = ""
    if reference.move != 0 and reference.feed is not None:
        feed = _expanded_word("F", reference.feed / options.output_unit_scale, options)
    line = template.format(axes=(" " if options.delimiter else "").join(words), feed=feed).strip()
    return _compact_post_line(line, options)


def _home_line(event, axes, options, profile):
    reference = event.reference
    if reference.move != 0 or set(axes) != set(reference.home_axes):
        return None
    key = "G28" if event.code == "G28" else "G53"
    commands = profile["home"][key]
    if "all" in commands:
        words = (" " if options.delimiter else "").join(_expanded_word(axis, 0, options) for axis in axes)
        line = commands["all"].format(axes=words)
    elif len(axes) == 1 and commands.get(axes[0]):
        line = profile["motion"]["rapidMove"] + " " + commands[axes[0]]
    else:
        raise ExportLimitation(
            "Post cannot preserve simultaneous home axes", code="UNSUPPORTED_REFERENCE_EXPANDED_EXPORT"
        )
    return _compact_post_line(line, options)


def _append_reference_event(lines, event, options, profile):
    reference = event.reference
    _validate_reference_frame(reference)
    axes = event.axes
    if not axes:
        return
    key = "rapid" if reference.move == 0 else "linear"
    template = (profile.get("reference") or {}).get(key)
    lines.append(profile["positioning"]["absolute"])
    home = _home_line(event, axes, options, profile)
    if home is not None:
        lines.append(home)
    elif template:
        _require_encodable_machine_zero(reference, axes)
        lines.append(_reference_line(template, reference.target, axes, reference, options))
    else:
        raise ExportLimitation(
            "Post cannot emit resolved machine reference motion", code="UNSUPPORTED_REFERENCE_EXPANDED_EXPORT"
        )
    lines.append(profile["positioning"]["incremental" if options.incremental else "absolute"])


def _require_encodable_machine_zero(reference, axes):
    if any(reference.target[i] == 0 and reference.home[i] != 0 for i, axis in enumerate("XYZ") if axis in axes):
        raise ExportLimitation(
            "Machine zero differs from configured home; this post's zero reference address denotes home",
            code="UNSUPPORTED_REFERENCE_ZERO_EXPANDED_EXPORT",
        )


def _append_reference_intermediate(lines, event, motions, options, profile, rotary_state, source_tcp_active):
    reference = event.reference
    for segment, motion in zip(reference.segments, motions, strict=True):
        if segment.phase != "intermediate":
            continue
        if any(value != (rotary_state or {}).get(axis, 0) for axis, value in reference.rotary_target):
            raise ExportLimitation(
                "G28 intermediate motion with simultaneous rotary homing is not reconstructable",
                code="UNSUPPORTED_REFERENCE_ROTARY_EXPANDED_EXPORT",
            )
        motion = _post_motion_geometry(motion, options, source_tcp_active=source_tcp_active)
        _append_expanded_motion(lines, motion, options, 0, profile=profile)


def _append_resolved_operations(
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
):
    if emit_drilling_operation(lines, step, motions, options, profile, direction=direction, cycle_state=motion_state):
        if motion_state is not None:
            motion_state.pop("last", None)
        if feed_state is not None:
            feed_state.clear()
        operation = next(event.drilling for event in step.events if event.drilling is not None)
        return (), operation.feed_mode, 17
    return _append_resolved_reference(
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
    )


def _append_resolved_reference(
    lines, step, motions, options, profile, feed_mode, plane, motion_state, feed_state, rotary_state, source_tcp_active
):
    events = [event for event in step.events if event.reference is not None]
    if not events:
        return motions, feed_mode, plane
    if len(events) != 1 or len(events[0].reference.segments) != len(motions):
        raise ValueError("Reference event and emitted geometry disagree")
    reference = events[0].reference
    if motions and motions[0].plane != plane:
        plane = motions[0].plane
        lines.append(profile["motion"][{17: "planeXY", 18: "planeXZ", 19: "planeYZ"}[plane]])
    if motions and step.feed_mode != feed_mode:
        key = {"per_minute": "perMinute", "per_revolution": "perRev", "inverse_time": "inverseTime"}[step.feed_mode]
        lines.append(profile["feed"][key])
        feed_mode = step.feed_mode
    if reference.move != 0 and step.feed_mode == "inverse_time":
        raise ExportLimitation(
            "Inverse-time machine references are not modeled", code="UNSUPPORTED_REFERENCE_EXPANDED_EXPORT"
        )
    _append_reference_intermediate(lines, events[0], motions, options, profile, rotary_state, source_tcp_active)
    _append_reference_event(lines, events[0], options, profile)
    if rotary_state is not None:
        rotary_state.update(reference.rotary_target)
    if motion_state is not None:
        motion_state["last"] = reference.move
    if reference.feed is not None and feed_state is not None:
        feed_state["last"] = (feed_mode, reference.feed)
    return (), feed_mode, plane
