"""Serialize resolved reference moves and drilling operations."""

from __future__ import annotations

import math

from app.gcode.export.drilling import emit_drilling_operation

from .common import ExportLimitation, _compact_post_line, _expanded_word
from .motions import _append_expanded_motion, _post_motion_geometry


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


def _home_line(event, axes, options, profile, source_words):
    reference = event.reference
    if reference.move != 0 or set(axes) != set(reference.home_axes):
        return None
    if event.code != "G28" and any(value != 0 for axis, value in source_words if axis in axes):
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


def _append_reference_event(lines, event, options, profile, source_words):
    reference = event.reference
    _validate_reference_frame(reference)
    axes = event.axes
    if not axes:
        return
    key = "rapid" if reference.move == 0 else "linear"
    template = (profile.get("reference") or {}).get(key)
    lines.append(profile["positioning"]["absolute"])
    home = _home_line(event, axes, options, profile, source_words)
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
    if not options.preserve_wcs and emit_drilling_operation(
        lines, step, motions, options, profile, direction=direction, cycle_state=motion_state
    ):
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
    _append_reference_event(lines, events[0], options, profile, step.words)
    if rotary_state is not None:
        rotary_state.update(reference.rotary_target)
    if motion_state is not None:
        motion_state["last"] = reference.move
    if reference.feed is not None and feed_state is not None:
        feed_state["last"] = (feed_mode, reference.feed)
    return (), feed_mode, plane
