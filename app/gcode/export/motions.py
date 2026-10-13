"""Serialize resolved motion geometry through post profile syntax."""

from __future__ import annotations

import math
from dataclasses import replace

from app.gcode.trace.geometry import arc_geometry
from app.gcode.trace.sampling import sample_motion

from ..kernel import TraceMotion
from ..kernel.geometry.arc_segments import split_arc
from ..post_profiles import _render
from .common import (
    ExportLimitation,
    ExportOptions,
    _check_cancelled,
    _word_format,
    _word_required,
    motion_line,
    scale_motion,
)
from .preflight import _inverse_orientation_point


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
    if (options.arc_mode == 3 or _spatial_arc_output(motion)) and motion.move in (2, 3):
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


def _spatial_arc_output(motion):
    standard = {17: (0, 0, 1), 18: (0, 1, 0), 19: (1, 0, 0)}
    return motion.source_kind == "cip" or (
        motion.arc is not None
        and motion.arc.normal is not None
        and any(abs(a - b) > 1e-9 for a, b in zip(motion.arc.normal, standard[motion.plane], strict=True))
    )


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
    if not options.rotary_axes or source_tcp_active and not options.preserve_wcs:
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
    orientation = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)) if source_tcp_active else motion.orientation
    if orientation is None:
        return motion
    offset = motion.orientation_offset if options.preserve_wcs else (0.0, 0.0, 0.0)

    def point(value):
        return _inverse_orientation_point(orientation, tuple(value[i] - offset[i] for i in range(3)))

    start = point((motion.start_x, motion.start_y, motion.start_z))
    end = point((motion.end_x, motion.end_y, motion.end_z))
    arc = motion.arc
    if arc is not None:
        normal = None if arc.normal is None else _inverse_orientation_point(orientation, arc.normal)
        arc = replace(
            arc,
            center=point(arc.center),
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
