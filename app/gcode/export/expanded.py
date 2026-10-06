"""Resolved geometry and machine states to configurable controller NC."""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path
from string import Formatter

from ..comments import extract_comments
from ..kernel import ExecutionResult, TraceMotion
from ..kernel.geometry.arc_segments import split_arc
from ..kernel.runtime.events import HOME_RETURN, PROGRAM_START, SUBPROGRAM_START, TOOL_CHANGE
from ..trace_tools import arc_geometry, sample_motion
from .common import (
    WORD_SIGNS,
    ExportLimitation,
    ExportOptions,
    _check_cancelled,
    _execution_slices,
    _expanded_word,
    _require_continuous_motions,
    _word,
    _word_required,
    motion_line,
    scale_motion,
)


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
        for position, segment in enumerate(split_arc(motion, split_angle)):
            _check_cancelled(cancelled)
            _append_expanded_motion(
                lines,
                segment,
                options,
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
        lines.append(
            _post_motion_line(
                motion_line(
                    first,
                    formatting,
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
                motion_line(second, formatting, override_move=override_move, include_feed=False),
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


POST_TARGETS = (
    "fanuc_mill",
    "fanuc_mill_multiaxis",
    "fanuc_lathe_a",
    "fanuc_lathe_b",
    "sinumerik_iso",
    "sinumerik_840d",
    "sinumerik_840d_multiaxis",
)
MILLING_TARGETS = ("fanuc_mill", "sinumerik_iso", "sinumerik_840d")


def load_post_profile(target):
    """Load a bundled controller or a user-supplied JSON post profile."""
    path = Path(__file__).with_name("posts") / f"{target}.json" if target in POST_TARGETS else Path(target)
    try:
        with path.open(encoding="utf-8-sig") as stream:
            profile = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load post profile {target}: {error}") from error
    if not isinstance(profile, dict) or profile.get("machine") not in {"mill", "lathe"}:
        raise ValueError("Post profile must specify mill or lathe")
    required = {
        "options": (
            "incrementalMode",
            "delimiter",
            "leadingZero",
            "decimalPlaces",
            "forceDecimal",
            "plusOutput",
            "units",
        ),
        "format": ("outputArcs", "arcMode", "arcCenter", "absoluteCenterSyntax", "radiusAddress", "multiTurnArcs"),
        "motion": (
            "rapidMove",
            "linearMove",
            "circularMoveCW",
            "circularMoveCCW",
            "planeXY",
            "planeXZ",
            "planeYZ",
            "threadMove",
        ),
        "positioning": ("absolute", "incremental", "incrementalAxes"),
        "home": ("G28", "G53"),
        "tool": ("toolChange",),
        "spindle": ("cw", "ccw", "stop", "cssOn", "cssOff", "maxSpeed"),
        "coolant": ("mist", "flood", "off"),
        "feed": ("perMinute", "perRev", "inverseTime"),
        "units": ("inch", "metric"),
        "dwell": ("command", "address", "scale"),
        "program": ("start", "preamble", "stop", "optionalStop", "end"),
    }
    for section, keys in required.items():
        if not isinstance(profile.get(section), dict) or any(key not in profile[section] for key in keys):
            raise ValueError(f"Missing post profile fields in {section}")
    if not isinstance(profile["options"]["decimalPlaces"], int) or not 0 <= profile["options"]["decimalPlaces"] <= 12:
        raise ValueError("Post decimalPlaces must be an integer from 0 to 12")
    if profile["format"]["arcMode"] not in {"IJK", "R"} or profile["format"]["arcCenter"] not in {
        "absolute",
        "incremental",
    }:
        raise ValueError("Unsupported post arc format")
    if profile["options"]["units"] not in {"mm", "inch"}:
        raise ValueError("Post units must be mm or inch")
    _validate_post_commands(profile)
    return profile


def _validate_post_safety(program) -> None:
    safety = program.get("safety")
    if safety is None:
        return
    if not isinstance(safety, list) or any(not isinstance(line, str) for line in safety):
        raise ValueError("Post program.safety must be a list of command strings")
    for line in safety:
        _render(line, programName="", units="")


def _validate_post_commands(profile):
    if not isinstance(profile.get("extension"), str) or not re.fullmatch(r"[a-zA-Z0-9]+", profile["extension"]):
        raise ValueError("Post extension must be a plain file suffix")
    _validate_post_options(profile["options"])
    if not isinstance(profile["program"]["preamble"], list):
        raise ValueError("Post program.preamble must be a list of command strings")
    _validate_post_safety(profile["program"])
    fields = {
        "motion": {"coord": "", "feed": ""},
        "tool": {"tool": "", "code": ""},
        "spindle": {"speed": "", "value": ""},
        "dwell": {"dwell": ""},
        "program": {"programName": "", "units": ""},
        "feed": {},
        "coolant": {},
        "units": {},
    }
    for section, values in fields.items():
        commands = [
            command
            for key, command in profile[section].items()
            if key not in {"scale", "address", "preamble", "safety"}
        ]
        if section == "program":
            commands.extend(profile[section]["preamble"])
        for command in commands:
            _render(command, **values)
    comment = profile.get("comment")
    if comment is not None:
        if not isinstance(comment, dict) or not isinstance(comment.get("template"), str):
            raise ValueError("Post comment.template must be a string")
        _render(comment["template"], text="")
    _validate_post_geometry(profile)
    _validate_post_extras(profile)


def _validate_post_extras(profile):
    _validate_post_arc_extras(profile["format"])
    _validate_supports(profile.get("supports"))
    _validate_format_words(profile["format"].get("words"), profile.get("supports"))


def _validate_post_arc_extras(arc):
    if "turnsWord" in arc:
        _render(str(arc["turnsWord"]), turns=0)
    for key in ("radiusSplitAngle", "arcSplitAngle"):
        if key in arc and (not isinstance(arc[key], (int, float)) or not math.isfinite(arc[key]) or arc[key] <= 0):
            raise ValueError(f"Post format.{key} must be a positive finite angle")
    if "fullCircle" in arc and arc["fullCircle"] != "two_half":
        raise ValueError("Post format.fullCircle must be two_half")


_FORMAT_WORD_TOKENS = {
    "motion": "motion",
    "X": "x",
    "Y": "y",
    "Z": "z",
    "A": "a",
    "B": "b",
    "C": "c",
    "I": "i",
    "J": "j",
    "K": "k",
    "R": "r",
}
_AXIS_WORD_KEYS = frozenset({"X", "Y", "Z", "A", "B", "C"})


def _validate_format_word_format(spec):
    if "decimals" in spec and (not isinstance(spec["decimals"], int) or not 0 <= spec["decimals"] <= 12):
        raise ValueError("Post format.words decimals must be an integer from 0 to 12")
    if "sign" in spec and spec["sign"] not in WORD_SIGNS:
        raise ValueError("Post format.words sign must be auto, always or never")


def _validate_format_word_entry(key, spec, axes, orders):
    if key not in _FORMAT_WORD_TOKENS:
        raise ValueError(f"Post format.words has unsupported token: {key}")
    if not isinstance(spec, dict) or any(name not in {"order", "required", "decimals", "sign"} for name in spec):
        raise ValueError("Post format.words entries accept order, required, decimals and sign")
    order = spec.get("order")
    if not isinstance(order, int) or isinstance(order, bool):
        raise ValueError("Post format.words order must be an integer")
    if order in orders:
        raise ValueError("Post format.words order values must be unique")
    orders.add(order)
    if not isinstance(spec.get("required"), bool):
        raise ValueError("Post format.words required must be a boolean")
    _validate_format_word_format(spec)
    if key in _AXIS_WORD_KEYS and key not in axes:
        raise ValueError(f"Post format.words axis {key} requires it in supports.axes")


def _validate_format_words(words, supports):
    if words is None:
        return
    if not isinstance(words, dict) or not words:
        raise ValueError("Post format.words must be a non-empty object")
    if "motion" not in words:
        raise ValueError("Post format.words must define motion")
    axes = set((supports or {}).get("axes", ["X", "Y", "Z"]))
    orders: set[int] = set()
    for key, spec in words.items():
        _validate_format_word_entry(key, spec, axes, orders)


def _validate_supports(supports):
    if supports is None:
        return
    if not isinstance(supports, dict):
        raise ValueError("Post supports must be an object")
    axes = supports.get("axes", ["X", "Y", "Z"])
    if not isinstance(axes, list) or not axes or any(axis not in {"X", "Y", "Z", "A", "B", "C"} for axis in axes):
        raise ValueError("Post supports.axes must be a non-empty list of X/Y/Z/A/B/C")
    for key in ("inverseTime", "multiTurnArcs", "absoluteArcCenters"):
        if key in supports and not isinstance(supports[key], bool):
            raise ValueError(f"Post supports.{key} must be boolean")


def _validate_post_options(defaults):
    for key in ("incrementalMode", "delimiter", "leadingZero", "forceDecimal", "plusOutput"):
        if not isinstance(defaults[key], bool):
            raise ValueError(f"Post options.{key} must be boolean")


def _validate_post_geometry(profile):
    arc = profile["format"]
    if arc["absoluteCenterSyntax"] not in {"AC", "words"} or arc["radiusAddress"] not in {"R", "CR="}:
        raise ValueError("Unsupported post center/radius syntax")
    if not all(isinstance(arc[key], bool) for key in ("outputArcs", "multiTurnArcs")):
        raise ValueError("Post arc output flags must be boolean")
    scale = profile["dwell"]["scale"]
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Post dwell scale must be positive and finite")
    if profile["dwell"]["address"] not in {"P", "F", "X"}:
        raise ValueError("Unsupported post dwell address")
    positioning = profile["positioning"]
    _render(positioning["absolute"])
    _render(positioning["incremental"])
    for axes in (positioning["incrementalAxes"], *profile["home"].values()):
        if not isinstance(axes, dict) or any(axis not in "XYZ" for axis in axes):
            raise ValueError("Post axis commands must map X/Y/Z")
        for command in axes.values():
            _render(command)


def _render(template, **values):
    """Data-only templates: no expressions, attribute access or clock values."""
    try:
        for _, field, spec, conversion in Formatter().parse(template):
            if field is not None and (field not in values or spec or conversion):
                raise ValueError(f"Unsupported post placeholder: {field}")
        return template.format(**values).strip()
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"Invalid post template: {template}") from error


def export_result(result, options=None, *, cancelled=None, target=None):
    """Postprocess resolved execution through one controller profile."""
    if target is None:
        if result is None:
            raise ValueError("EXPANDED requires a valid execution result")
        target = "fanuc_lathe_" + result.lathe_gcode_system.lower() if result.language == "fanuc_turn" else "fanuc_mill"
    return convert_resolved_program(result, target, options, cancelled=cancelled)


def convert_resolved_program(result, target="fanuc_mill", options=None, *, cancelled=None):
    """Flatten cycles/variables/transforms into physical XYZ motion and controls.

    Coordinates use one G54 frame with zero offsets; controller offset tables
    and source structure are deliberately absent from this resolved program.
    """
    _check_cancelled(cancelled)
    if result is None:
        raise ValueError("EXPANDED requires a valid execution result")
    profile = load_post_profile(target)
    turning = result.language == "fanuc_turn"
    if (profile["machine"] == "lathe") != turning:
        raise ValueError("Post profile machine does not match the executed geometry")
    _require_valid_trace_export(result, allow_inverse_time=bool(profile["feed"]["inverseTime"]))
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
    for step, block, motions in _execution_slices(result):
        _check_cancelled(cancelled)
        _append_source_comments(lines, block, emitted_comment_blocks, options, profile)
        lines.extend(_tool_change_lines(step, profile))
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
        )
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
    if not {"X", "Z"} <= axes or ("Y" not in axes and _uses_y_axis(result)):
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
        if _word_required(options, axis.lower()) or state is None or state.get(axis) != value:
            emitted[axis] = value
        if state is not None:
            state[axis] = value
    return emitted


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
):
    step_options = options
    if options.rotary_axes and motions:
        step_options = replace(options, rotary_values=_step_rotary_values(step, options, rotary_state))
    dwell = sum(signal.value or 0 for signal in step.signals if signal.kind == "dwell")
    reverse = any(signal.kind == "spindle_reverse" for signal in step.signals)
    feeds = 0
    for motion in motions:
        _check_cancelled(cancelled)
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
            feed=m.feed,
            start_y=previous[1],
            end_y=point.y,
            source_block=m.source_block,
        )
        lines.append(
            motion_line(
                temp,
                options,
                include_feed=emit_feed and position == 0,
                include_motion=include_motion and (position == 0 or repeat_motion),
            )
        )
        previous = (point.x, point.y, point.z)
    return lines


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


def _require_valid_trace_export(result: ExecutionResult, *, allow_inverse_time=False) -> None:
    if result is None or not result.ok or not result.complete:
        raise ValueError("EXPANDED requires a valid and complete execution result")
    if any(event.kind == "TCP_CONTROL_ON" for event in result.events):
        raise ExportLimitation(
            "Selected post supports only XYZ conversion; Expanded NC cannot preserve G43.4 TCP rotary commands",
            code="UNSUPPORTED_TCP_EXPANDED_EXPORT",
        )
    if any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events):
        raise ExportLimitation(
            "Selected post supports only XYZ; Expanded NC cannot preserve G68.2 tilted working-plane commands",
            code="UNSUPPORTED_TWP_EXPANDED_EXPORT",
        )
    _require_continuous_motions(result, allow_reference_rapids=True)
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
    if any(d.code in ignored_native or d.code == "UNMODELED_SINUMERIK_NATIVE" for d in result.diagnostics):
        raise ValueError("NC trace export cannot preserve ignored SINUMERIK diameter/corner/feed commands")
