"""Serialize resolved hole operations through data-only post templates."""

import math
from dataclasses import replace

from .export.common import _compact_post_line, _expanded_word, _word
from .post_profiles import _render


def emit_drilling_operation(lines, step, motions, options, profile, *, direction=3, cycle_state=None):
    operations = [event.drilling for event in step.events if event.drilling is not None]
    if not operations or not profile.get("cycles"):
        return False
    if len(operations) != 1 or operations[0].emitted_count != len(motions):
        raise ValueError("Drilling operation and execution geometry disagree")
    operation = _post_operation(operations[0], options)
    if operation is None:
        return False
    if operation.kind == "tap" and config_direction_unsupported(profile["cycles"], direction):
        return False
    config = profile["cycles"]
    if not _can_emit(operation, motions, options, config):
        return False
    values = _cycle_values(operation, options, profile)
    block = [
        profile["positioning"]["absolute"],
        profile["motion"]["planeXY"],
        profile["feed"]["perRev" if operation.feed_mode == "per_revolution" else "perMinute"],
    ]
    if config["syntax"] == "native":
        _native_lines(block, operation, values, options, profile)
    else:
        _iso_lines(block, operation, values, options, profile)
    block.append(profile["positioning"]["incremental" if options.incremental else "absolute"])
    _append_cycle_block(lines, block, operation, config, cycle_state)
    return True


def _append_cycle_block(lines, block, operation, config, state):
    if state is None or config["syntax"] != "native":
        lines.extend(block)
        return
    previous = state.pop("drilling_group", None)
    # Additional return motions must run after cancellation, outside MCALL.
    if len(block) != 9:
        lines.extend(block)
        return
    signature = tuple(block[:3] + block[4:6] + block[7:])
    if previous is not None and previous[:2] == (len(lines), signature) and previous[3] == operation.start[2]:
        del lines[previous[2] :]
        lines.extend(block[6:])
    else:
        lines.extend(block)
    state["drilling_group"] = (len(lines), signature, len(lines) - 2, operation.returned[2])


def config_direction_unsupported(config, direction):
    return config["syntax"] == "native" and direction != 3


def _post_operation(operation, options):
    orientation = operation.orientation
    if orientation is None or not options.rotary_axes:
        return operation
    if any(abs(orientation[i][2] - (1 if i == 2 else 0)) > 1e-9 for i in range(3)):
        return None
    points = {}
    for name in ("start", "position", "safety", "reference", "returned"):
        point = getattr(operation, name)
        points[name] = tuple(sum(orientation[j][i] * point[j] for j in range(3)) for i in range(3))
    return replace(operation, **points, orientation=None)


def _can_emit(operation, motions, options, config):
    if (
        operation.kind not in config
        or operation.feed_mode == "inverse_time"
        or operation.feed <= 0
        or _missing_peck_template(operation, config)
    ):
        return False
    if any(motion.plane != 17 for motion in motions):
        return False
    if any(
        abs(point[i] - operation.position[i]) > 1e-9
        for point in (operation.safety, operation.reference, operation.returned)
        for i in (0, 1)
    ):
        return False
    if operation.position[2] >= operation.reference[2] or operation.safety[2] < operation.reference[2]:
        return False
    if config["syntax"] == "native":
        return _native_compatible(operation, options)
    return _iso_compatible(operation)


def _missing_peck_template(operation, config):
    return (
        operation.kind == "peckDrill"
        and not operation.full_retract
        and config["syntax"] == "iso"
        and "highSpeedPeck" not in config
    )


def _native_compatible(operation, options):
    if operation.kind == "tap":
        return (
            options.output_unit_scale == 1
            and operation.feed_mode == "per_minute"
            and operation.spindle_speed > 0
            and operation.feed_return_height == operation.safety[2]
        )
    return True


def _iso_compatible(operation):
    if operation.kind == "peckDrill":
        return (
            operation.peck_reduction == 0
            and operation.first_feed_factor == 1
            and operation.reference[2] == operation.safety[2]
            and (not operation.full_retract or operation.reentry_clearance == 1)
            and (operation.full_retract or operation.retract_distance == 1)
            and (not operation.full_retract or operation.peck_return_height == operation.safety[2])
        )
    if operation.kind in ("tap", "boreFeed"):
        return operation.feed_return_height == operation.safety[2]
    return True


def _cycle_values(operation, options, profile):
    scale = options.output_unit_scale
    parameters = {
        "x": operation.position[0] / scale,
        "y": operation.position[1] / scale,
        "clearance": operation.returned[2] / scale,
        "referenceHeight": operation.reference[2] / scale,
        "secondClearance": (operation.safety[2] - operation.reference[2]) / scale,
        "depth": operation.position[2] / scale,
        "retractHeight": operation.safety[2] / scale,
        "peckFirst": operation.peck_first / scale,
        "peckReduction": operation.peck_reduction / scale,
        "peckMinimum": operation.peck_minimum / scale,
        "firstDepth": (operation.reference[2] - operation.peck_first) / scale,
        "dwellBottom": operation.dwell_bottom,
        "dwellTop": 0.0,
        "reentryClearance": operation.reentry_clearance / scale,
        "retractDistance": operation.retract_distance / scale,
        "firstFeedFactor": operation.first_feed_factor,
        "fullRetract": int(operation.full_retract),
        "spindleSpeedTap": operation.spindle_speed,
        "spindleSpeedReturn": operation.spindle_speed,
        "feed": operation.feed / scale,
        "threadPitch": (operation.feed / operation.spindle_speed if operation.spindle_speed else 0) / scale,
        "dwellWord": operation.dwell_bottom * profile["dwell"]["scale"],
    }
    if not all(math.isfinite(value) for value in parameters.values()):
        raise ValueError("Drilling operation parameters must be finite")
    return {name: _word("", value, options) for name, value in parameters.items()}


def _line(lines, template, values, options):
    line = _render(template, **values)
    lines.append(_compact_post_line(line, options))


def _native_lines(lines, operation, values, options, profile):
    config = profile["cycles"]
    # MCALL drilling needs an explicit hole-position block, even at the same XY.
    xy = " ".join(
        _expanded_word(axis, operation.position[i] / options.output_unit_scale, options) for i, axis in enumerate("XY")
    )
    _line(lines, profile["motion"]["rapidMove"] + " " + xy, {}, options)
    _line(lines, "F{feed}", values, options)
    if operation.kind == "peckDrill":
        values = dict(values, clearance=_word("", operation.peck_return_height / options.output_unit_scale, options))
    key = "drill" if operation.kind == "peckDrill" and operation.peck_first <= 0 else operation.kind
    _line(lines, config[key], values, options)
    _line(lines, xy, {}, options)
    _line(lines, config["cancel"], {}, options)
    if operation.kind == "peckDrill" and operation.returned[2] != operation.peck_return_height:
        _line(
            lines, profile["motion"]["rapidMove"] + " Z{clearance}", _cycle_values(operation, options, profile), options
        )


def _iso_lines(lines, operation, values, options, profile):
    config = profile["cycles"]
    cycle_return = operation.returned[2]
    return_initial = cycle_return != operation.safety[2] and cycle_return == max(
        operation.start[2], operation.safety[2]
    )
    _line(lines, config["returnInitial" if return_initial else "returnSafety"], {}, options)
    if operation.kind == "tap" and operation.rigid_tapping and config.get("rigidTap"):
        _line(lines, config["rigidTap"], values, options)
    key = "highSpeedPeck" if operation.kind == "peckDrill" and not operation.full_retract else operation.kind
    if operation.kind == "peckDrill" and operation.peck_first <= 0:
        key = "drill"
    _line(lines, config[key], values, options)
    _line(lines, config["cancel"], {}, options)
    emitted_return = max(operation.start[2], operation.safety[2]) if return_initial else operation.safety[2]
    if operation.returned[2] != emitted_return:
        _line(lines, profile["motion"]["rapidMove"] + " Z{clearance}", values, options)
