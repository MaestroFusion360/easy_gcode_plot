"""Export resolved milling operations to native iTNC 530 blocks.

The separate Klartext frontend and three-axis runtime consume native input.
Variables, calls and source cycles from executable input languages are resolved
before this target writer; it does not interpret Klartext source ASTs.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace

from app.gcode.trace.sampling import sample_motion

from ..kernel.geometry.arc_segments import split_arc
from ..kernel.runtime.events import PROGRAM_START, SUBPROGRAM_START, TOOL_CHANGE
from .common import (
    ExportLimitation,
    _check_cancelled,
    _execution_slices,
    _word,
    machine_control_templates,
    scale_motion,
)
from .tool_numbers import target_tool_numbers, tool_mapping_lines


def _unsupported(message):
    raise ExportLimitation(message, code="UNSUPPORTED_HEIDENHAIN_EXPANDED_EXPORT")


def _check_scope(result, profile, options):
    from .preflight import _require_valid_trace_export  # pylint: disable=import-outside-toplevel

    if profile["machine"] != "mill" or result.language == "fanuc_turn":
        _unsupported("Heidenhain block schemes require milling geometry")
    _require_valid_trace_export(result, profile)
    blocked = {"ROTARY_INDEX", "TOOL_AXIS_ORIENT", "TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"}
    if any(event.kind in blocked for event in result.events):
        _unsupported(
            "This Heidenhain post supports three-axis work coordinates; "
            "rotary/TCP operations require additional schemes"
        )
    _check_references(result)
    if options.start_program.strip() or options.end_program.strip():
        _unsupported(
            "Custom program text is incompatible with BEGIN/END PGM; clear Start/End program in Export Options"
        )
    if any(m.feed_mode != "per_minute" or m.threading for m in result.motions):
        _unsupported("This Heidenhain post supports feed per minute and resolved milling moves")
    cycle_kinds = {"drill", "drillDwell", "peckDrill", "tap", "tapLeft", "boreFeed", "boreStop"}
    if any(event.drilling is not None and event.drilling.kind not in cycle_kinds for event in result.events):
        _unsupported("This Heidenhain post supports CYCL DEF 200, 201, 202, 203 and 207 only")
    if any(m.compensation_mode in {41, 42} and not m.compensation_applied for m in result.motions):
        _unsupported("Heidenhain R0 output requires resolved cutter compensation")
    if options.word_order and options.word_order[0] != "motion":
        _unsupported("Heidenhain motion commands must precede coordinate addresses")


def _check_references(result):
    for event in result.events:
        reference = event.reference
        if reference is None:
            continue
        invalid_axes = any(axis not in "XYZ" for axis in reference.home_axes) or any(
            axis not in "XYZ" for segment in reference.segments for axis in segment.axes
        )
        if (
            reference.move != 0
            or reference.coordinate_space != "machine"
            or reference.orientation is not None
            or reference.rotary_target
            or invalid_axes
        ):
            _unsupported("This Heidenhain post supports rapid XYZ machine-coordinate returns through M91 only")


def _coordinates(start, end, options, *, axes=(0, 1, 2), force=False):
    values = {}
    for index in axes:
        axis = "XYZ"[index]
        required = (options.word_required or {}).get(axis.lower(), False)
        if force or required or abs(end[index] - start[index]) > 1e-10:
            value = end[index] - start[index] if options.incremental else end[index]
            word = _word(axis, value, options)
            values[axis.lower()] = ("I" if options.incremental else "") + word
    order = list(options.word_order or ())
    order.extend(key for key in ("x", "y", "z") if key not in order)
    return [values[key] for key in order if key in values]


def _signed_word(letter, value, options):
    word = _word(letter, value, options)
    prefix = len(letter)
    return word if word[prefix : prefix + 1] in "+-" else word[:prefix] + "+" + word[prefix:]


def _target_word(axis, start, end, options):
    """Format an absolute X/Y/Z target or an incremental IX/IY/IZ target."""
    prefix = "I" if options.incremental else ""
    value = end - start if options.incremental else end
    return prefix + _signed_word(axis, value, options)


def linear_block(start, end, options, *, rapid=False, feed=None, first=False, native=None):
    """One native L block, also used by the editor's formatting preview."""
    native = native or {"linear": "L", "compensationOff": "R0", "rapidFeed": "FMAX"}
    words = [native["linear"], *_coordinates(start, end, options, force=first), native["compensationOff"]]
    if rapid:
        words.append(native["rapidFeed"])
    elif feed is not None:
        words.append(_word("F", feed, options))
    return " ".join(words)


def radius_block(start, end, radius, clockwise, options, *, axes=(0, 1), feed=None, native=None):
    """One planar CR block with an R radius, endpoint and direction."""
    native = native or {"radiusCircle": "R", "clockwise": "DR-", "counterclockwise": "DR+"}
    radius_value = _word("", abs(radius), options).lstrip("+")
    radius_address = native["radiusCircle"]
    words = ["CR", *_coordinates(start, end, options, axes=axes, force=True), f"{radius_address}{radius_value}"]
    words.append(native["clockwise"] if clockwise else native["counterclockwise"])
    if feed is not None:
        words.append(_word("F", feed, options))
    return " ".join(words)


def _arc_axes(motion):
    return {17: ((0, 1), 2), 18: ((0, 2), 1), 19: ((1, 2), 0)}[motion.plane]


def _center_arc_lines(motion, start, end, options, native, *, feed=None):
    plane_axes, out_axis = _arc_axes(motion)
    center = motion.arc.center
    center_words = [_signed_word("XYZ"[axis], center[axis], options) for axis in plane_axes]
    lines = [" ".join([native["circleCenter"], *center_words])]
    direction = native["clockwise"] if motion.move == 2 else native["counterclockwise"]
    helical = abs(end[out_axis] - start[out_axis]) > 1e-10
    if helical or motion.arc.full_circle:
        sweep = max(1e-9, math.degrees(motion.arc.sweep))
        if motion.move == 2:
            sweep = -sweep
        words = [native["polarCircle"], _signed_word("IPA", sweep, replace(options, decimal_places=3))]
        if helical:
            words.append(_target_word("XYZ"[out_axis], start[out_axis], end[out_axis], options))
    else:
        words = [
            native["circle"],
            *(_target_word("XYZ"[axis], start[axis], end[axis], options) for axis in plane_axes),
        ]
    words.append(direction)
    if feed is not None:
        words.append(_word("F", feed, options))
    lines.append(" ".join(words))
    return lines


def _motion_lines(motion, options, index, native, *, first=False, cancelled=None, spindle_axis="Z"):
    motion = scale_motion(motion, options.output_unit_scale)
    start = (motion.start_x, motion.start_y, motion.start_z)
    end = (motion.end_x, motion.end_y, motion.end_z)
    if motion.move in {0, 1}:
        return [linear_block(start, end, options, rapid=motion.move == 0, feed=motion.feed, first=first, native=native)]
    if motion.move not in {2, 3} or motion.arc is None:
        _unsupported("Heidenhain circular output requires resolved arc geometry")
    standard_normal = {17: (0, 0, 1), 18: (0, 1, 0), 19: (1, 0, 0)}[motion.plane]
    standard_plane = not motion.arc.normal or all(
        abs(a - b) <= 1e-8 for a, b in zip(motion.arc.normal, standard_normal)
    )
    spindle_plane = {"Z": 17, "Y": 18, "X": 19}[spindle_axis]
    if options.arc_mode == 3 or not standard_plane or motion.plane != spindle_plane:
        lines = []
        for point in sample_motion(motion, index, chord_error=options.linearization_tolerance, cancelled=cancelled):
            _check_cancelled(cancelled)
            target = (point.x, point.y, point.z)
            lines.append(
                linear_block(start, target, options, feed=motion.feed, first=first and not lines, native=native)
            )
            start = target
        return lines
    split_angle = options.radius_split_angle if options.arc_mode == 2 else options.arc_split_angle
    limit = math.radians(min(split_angle, 180.0 if options.arc_mode == 2 else 5400.0))
    if (
        options.arc_mode == 2
        and motion.arc.full_circle
        or (motion.arc.sweep > limit + 1e-10 and not motion.arc.full_circle)
    ):
        lines = []
        for segment in split_arc(motion, limit):
            _check_cancelled(cancelled)
            # Already scaled: recursive segments must retain the same units.
            lines.extend(
                _motion_lines(
                    segment,
                    replace(options, output_unit_scale=1.0),
                    index,
                    native,
                    first=first and not lines,
                    cancelled=cancelled,
                    spindle_axis=spindle_axis,
                )
            )
        return lines
    plane_axes, out_axis = _arc_axes(motion)
    if options.arc_mode == 2 and not motion.arc.full_circle and abs(end[out_axis] - start[out_axis]) <= 1e-10:
        radius = math.dist(
            tuple(start[axis] for axis in plane_axes),
            tuple(motion.arc.center[axis] for axis in plane_axes),
        )
        return [
            radius_block(
                start,
                end,
                radius,
                motion.move == 2,
                options,
                axes=plane_axes,
                feed=motion.feed,
                native=native,
            )
        ]
    return _center_arc_lines(motion, start, end, options, native, feed=motion.feed)


def _cycle_number(operation):
    if operation.kind in {"drill", "drillDwell"}:
        return 200
    if operation.kind == "peckDrill":
        return 203
    if operation.kind == "boreFeed":
        return 201
    if operation.kind == "boreStop":
        return 202
    if operation.kind in {"tap", "tapLeft"}:
        return 207
    _unsupported("This drilling operation has no iTNC 530 CYCL DEF mapping")


def _reference_lines(event, options, profile):
    reference = event.reference
    native = profile["native"]
    targets = [(segment.end, segment.axes) for segment in reference.segments]
    if not targets:
        targets = [(reference.target, reference.home_axes)]
    lines = []
    for endpoint, axis_names in targets:
        axes = tuple("XYZ".index(axis) for axis in axis_names)
        words = [_signed_word("XYZ"[axis], endpoint[axis] / options.output_unit_scale, options) for axis in axes]
        if not words:
            continue
        lines.append(
            " ".join(
                [
                    native["linear"],
                    *words,
                    native["compensationOff"],
                    native["rapidFeed"],
                    native["machineCoordinates"],
                ]
            )
        )
    return lines


def _q_line(number, value, options):
    return f"Q{number}=" + _signed_word("", value, options)


def _cycle_lines(operation, options, profile):
    if operation.feed_mode != "per_minute" or operation.feed <= 0:
        _unsupported("Heidenhain cycles require a positive feed per minute")
    scale = options.output_unit_scale
    cycle = _cycle_number(operation)
    reference = operation.reference[2] / scale
    depth = operation.position[2] / scale - reference
    clearance = max(0.0, operation.safety[2] / scale - reference)
    second_clearance = max(operation.safety[2], operation.returned[2]) / scale - reference
    cycle_key = {
        200: "drillDwell" if operation.dwell_bottom > 0 else "drill",
        203: "peckDrill",
        201: "boreFeed",
        202: "boreStop",
        207: "tap",
    }[cycle]
    lines = [profile["cycles"][cycle_key] + " ~"]
    values = [(200, clearance), (201, depth)]
    if cycle in {200, 201, 202, 203}:
        values.append((206, operation.feed / scale))
    if cycle in {200, 203}:
        peck = operation.peck_first / scale if operation.peck_first > 0 else abs(depth)
        values.extend(((202, peck), (210, 0.0)))
    values.extend(((203, reference), (204, max(0.0, second_clearance))))
    if cycle == 200:
        values.append((211, operation.dwell_bottom))
    elif cycle in {201, 202}:
        # G85 feeds out with the spindle running; G86 stops and rapids out.
        values.extend(((211, operation.dwell_bottom), (208, operation.feed / scale if cycle == 201 else 99999)))
        if cycle == 202:
            values.extend(((214, 0), (336, 0)))
    elif cycle == 203:
        values.extend(
            (
                (212, operation.peck_reduction / scale),
                (213, 0.0),
                (205, operation.peck_minimum / scale),
                (211, operation.dwell_bottom),
                (208, 0.0),
                (256, operation.retract_distance / scale),
            )
        )
    elif cycle == 207:
        if operation.spindle_speed <= 0:
            _unsupported("CYCL DEF 207 requires a known spindle speed")
        pitch = operation.feed / operation.spindle_speed / scale
        values.append((239, -pitch if operation.kind == "tapLeft" else pitch))
    lines.extend(
        _q_line(number, value, options) + (" ~" if index < len(values) - 1 else "")
        for index, (number, value) in enumerate(values)
    )
    position = " ".join(
        _signed_word(axis, value, options)
        for axis, value in zip(
            "XYZ",
            (operation.position[0] / scale, operation.position[1] / scale, reference),
            strict=True,
        )
    )
    native = profile["native"]
    return [f"{native['linear']} {position} {native['rapidFeed']}", *lines, native["cycleCall"]]


def _tool_number(tool, mapping):
    value = str(mapping.get(tool, tool or ""))
    match = re.fullmatch(r"T?(\d+)", value)
    if not match:
        _unsupported("Heidenhain TOOL CALL requires a numeric tool mapping")
    return str(int(match[1]))


def _control_lines(step, mapping, active_tool, options, profile, *, drilling=False):
    lines = []
    if any(event.kind == SUBPROGRAM_START and event.code == "G65" for event in step.events):
        return lines, active_tool
    speed = next((value for letter, value in step.words if letter == "S"), None)
    for event in step.events:
        if event.kind == TOOL_CHANGE:
            active_tool = _tool_number(event.tool, mapping)
            code = _word("S", speed, options) if speed is not None else ""
            lines.append(profile["tool"]["toolChange"].format(tool=active_tool, code=code).strip())
    if speed is not None and not any(event.kind == TOOL_CHANGE for event in step.events):
        if active_tool is None:
            _unsupported("Spindle speed output requires an active TOOL CALL")
        lines.append(profile["tool"]["toolChange"].format(tool=active_tool, code=_word("S", speed, options)).strip())
    controls = machine_control_templates(profile)
    lines.extend(controls[int(value)] for letter, value in step.words if letter == "M" and value in controls)
    for signal in step.signals:
        if signal.kind == "dwell" and not drilling:
            lines.extend(
                [
                    profile["native"]["dwellDefinition"],
                    profile["dwell"]["command"].format(dwell=_word("", signal.value, options)),
                ]
            )
    return lines, active_tool


def _spindle_axis(profile):
    tool_call = profile["tool"]["toolChange"].format(tool=0, code="")
    match = re.search(r"\bTOOL\s+CALL\s+0\s+([XYZ])\b", tool_call)
    if match is None:
        _unsupported("Heidenhain TOOL CALL must specify a spindle axis X, Y or Z")
    return match[1]


def _operation_lines(operations, references, motions, options, profile, spindle_axis):
    if references:
        if len(references) != 1 or len(references[0].reference.segments) not in {0, len(motions)}:
            _unsupported("Reference return and resolved geometry disagree")
        return _reference_lines(references[0], options, profile)
    if operations:
        if len(operations) != 1 or operations[0].emitted_count != len(motions):
            _unsupported("Drilling operation and resolved geometry disagree")
        if spindle_axis != "Z" or operations[0].orientation is not None:
            _unsupported("Heidenhain drilling cycles require the Z spindle axis")
        return _cycle_lines(operations[0], options, profile)
    return None


def export_heidenhain(result, profile, options=None, *, cancelled=None):
    """Emit native blocks from trace geometry and semantic execution steps."""
    from .post_options import _post_options, _source_comment_lines  # pylint: disable=import-outside-toplevel

    options = _post_options(options, profile)
    options = replace(options, delimiter=True, multi_turn_arcs=False)
    _check_scope(result, profile, options)
    native = profile["native"]
    spindle_axis = _spindle_axis(profile)
    units = "INCH" if options.output_unit_scale == 25.4 else "MM"
    source_name = next((event.code for event in result.events if event.kind == PROGRAM_START and event.code), "PART")
    name = re.sub(r"[^A-Za-z0-9_]", "_", str(source_name)).strip("_") or "PART"
    lines = profile["program"]["start"].format(programName=name, units=units).splitlines()
    mapping = target_tool_numbers(result, profile, options.tool_numbers)
    active_tool = None
    motion_index = 0
    comment_profile = dict(profile, comment={"template": "; {text}"})
    lines.extend(tool_mapping_lines(mapping, comment_profile))
    seen_comments = set()
    for step, block, motions in _execution_slices(result):
        _check_cancelled(cancelled)
        if options.include_comments and block.index not in seen_comments:
            lines.extend(_source_comment_lines(block.raw, options, comment_profile))
            seen_comments.add(block.index)
        operations = [event.drilling for event in step.events if event.drilling is not None]
        references = [event for event in step.events if event.reference is not None]
        controls, active_tool = _control_lines(step, mapping, active_tool, options, profile, drilling=bool(operations))
        lines.extend(controls)
        operation_lines = _operation_lines(operations, references, motions, options, profile, spindle_axis)
        if operation_lines is not None:
            lines.extend(operation_lines)
            motion_index += len(motions)
            continue
        for motion in motions:
            _check_cancelled(cancelled)
            if active_tool is None and motion.tool:
                active_tool = _tool_number(motion.tool, mapping)
                lines.append(profile["tool"]["toolChange"].format(tool=active_tool, code="").strip())
            lines.extend(
                _motion_lines(
                    motion,
                    options,
                    motion_index,
                    native,
                    first=motion_index == 0,
                    cancelled=cancelled,
                    spindle_axis=spindle_axis,
                )
            )
            motion_index += 1
    lines.extend(profile["program"]["end"].format(programName=name, units=units).splitlines())
    if options.sequence_numbers:
        lines = [
            f"{options.sequence_start + index * options.sequence_increment} {line}" for index, line in enumerate(lines)
        ]
    return "\n".join(lines) + "\n"
