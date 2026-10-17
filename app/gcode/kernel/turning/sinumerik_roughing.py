"""Native CYCLE95 contour ranges and balanced paraxial stock-removal passes."""

import math
import re
from dataclasses import replace

from ..frontend.model import Point2, ProfileSegment
from ..geometry.profile_arcs import normalize_sweep, try_get_arc_geometry
from ..resources import SemanticError, checkpoint
from ..types import Diagnostic
from .cycles.profile import build_offset_profile
from .sinumerik_motion import evaluate, position_block
from .sinumerik_state import unsupported
from .sinumerik_values import arguments, integer, nonnegative, positive


def _label_index(program, name):
    name = name.upper()
    matches = [
        block.index
        for block in program.blocks
        if getattr(block.native_syntax, "label", None) == name
        or re.fullmatch(r"N?\d+", name)
        and block.nlabel == int(name.lstrip("N"))
    ]
    if len(matches) != 1:
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", f"Contour label {name} must exist exactly once")
    return matches[0]


def contour_profile(state, reference):
    match = re.fullmatch(r'"([A-Z_0-9]+):([A-Z_0-9]+)"', reference, re.I)
    if match is None:
        unsupported("CYCLE95 requires a local quoted START:END contour range", "UNSUPPORTED_SINUMERIK_CYCLE")
    first, last = (_label_index(state.program, name) for name in match.groups())
    if first >= last:
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", "Contour end must follow its start label")
    first += getattr(state.program.blocks[first].native_syntax, "label", None) is not None
    last += getattr(state.program.blocks[last].native_syntax, "label", None) is None
    local = replace(state, motions=[], threading=[], events=[], signals=[], diagnostics=[], steps=[], cutter_comp=40)
    profile, first_motion = [], True
    for block in state.program.blocks[first:last]:
        checkpoint()
        syntax = block.native_syntax
        if syntax is None or syntax.kind not in {"words", "turning_label"}:
            unsupported("CYCLE95 contour permits straight/circular XZ geometry only", "UNSUPPORTED_SINUMERIK_CYCLE")
        if syntax.kind == "turning_label":
            continue
        words, _ = evaluate(block, local)
        _validate_contour_words(words, syntax, first_motion)
        before = len(local.motions)
        position_block(local, words, syntax, block)
        if len(local.motions) == before:
            if first_motion and {"X", "Z"} <= words.keys():
                first_motion = False
            continue
        motion = local.motions[-1]
        if first_motion:
            first_motion = False
        else:
            profile.append(_profile_segment(motion, local.offset))
    if len(profile) < 2:
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", "CYCLE95 requires at least three contour motion blocks")
    return profile


def _validate_contour_words(words, syntax, first):
    if (
        set(words) - {"N", "G", "X", "Z", "I", "K", "CR", "_G", "_M"}
        or set(words["_G"]) - {0, 1, 2, 3, 90, 91}
        or syntax.supa
        or syntax.ignored_diameter_modes
    ):
        unsupported(
            "CYCLE95 contour cannot change technology, units, diameter mode or compensation",
            "UNSUPPORTED_SINUMERIK_CYCLE",
        )
    positioned = "X" in words or "Z" in words
    if first and positioned and (not {"X", "Z"} <= words.keys() or not set(words["_G"]) & {0, 1, 2, 3}):
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", "First contour motion requires explicit G0/G1/G2/G3 and X/Z")


def _profile_segment(motion, offset):
    start = Point2(motion.start.x - 2 * offset.x, motion.start.z - offset.z)
    end = Point2(motion.end.x - 2 * offset.x, motion.end.z - offset.z)
    has_center = motion.i is not None or motion.k is not None
    center = Point2(start.x + (motion.i or 0), start.z + (motion.k or 0))
    return ProfileSegment(
        motion.source_block,
        motion.move or 1,
        start,
        end,
        motion.radius is not None,
        motion.radius or 0,
        has_center,
        center,
    )


def _contour_points(segment, tolerance):
    if segment.move not in {2, 3}:
        return (segment.start, segment.end)
    geometry = try_get_arc_geometry(segment)
    if geometry is None:
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", "Contour arc has no center or radius")
    cx, cz = geometry.center.x / 2, geometry.center.z
    radius = math.hypot(segment.start.x / 2 - cx, segment.start.z - cz)
    start = math.atan2(segment.start.z - cz, segment.start.x / 2 - cx)
    end = math.atan2(segment.end.z - cz, segment.end.x / 2 - cx)
    sweep = normalize_sweep(segment.move, start, end)
    angle = 4 * math.asin(math.sqrt(min(1, max(tolerance, 1e-6) / (2 * radius))))
    count = max(1, math.ceil(abs(sweep) / angle))
    points = [segment.start]
    for index in range(1, count):
        checkpoint("cycle_iterations")
        phase = start + sweep * index / count
        points.append(Point2(2 * (cx + radius * math.cos(phase)), cz + radius * math.sin(phase)))
    return (*points, segment.end)


def _polyline(profile, facing, tolerance):
    points = []
    for segment in profile:
        for point in _contour_points(segment, tolerance):
            value = Point2(point.z, point.x / 2) if facing else Point2(point.x / 2, point.z)
            if not points or value != points[-1]:
                points.append(value)
    direction = math.copysign(1, points[-1].z - points[0].z)
    if points[-1].z == points[0].z or any((b.z - a.z) * direction < -1e-8 for a, b in zip(points, points[1:])):
        unsupported("CYCLE95 overhanging contours are not supported", "UNSUPPORTED_SINUMERIK_CYCLE")
    return points, direction


def _boundary(points, travel, internal):
    depths = []
    for a, b in zip(points, points[1:]):
        if abs(b.z - a.z) > 1e-12 and min(a.z, b.z) <= travel <= max(a.z, b.z):
            depths.append(a.x + (b.x - a.x) * (travel - a.z) / (b.z - a.z))
    if not depths:
        raise SemanticError("INVALID_SINUMERIK_CONTOUR", "Contour has no boundary at this machining section")
    return min(depths) if internal else max(depths)


def _cut_intervals(points, depth, internal, direction):
    breaks = {point.z for point in points}
    for a, b in zip(points, points[1:]):
        if abs(b.x - a.x) > 1e-12 and min(a.x, b.x) <= depth <= max(a.x, b.x):
            breaks.add(a.z + (b.z - a.z) * (depth - a.x) / (b.x - a.x))
    ordered = sorted(breaks, reverse=direction < 0)
    intervals = []
    for start, end in zip(ordered, ordered[1:]):
        boundary = _boundary(points, (start + end) / 2, internal)
        allowed = depth <= boundary + 1e-9 if internal else depth >= boundary - 1e-9
        if allowed and abs(end - start) > 1e-9:
            if intervals and abs(intervals[-1][1] - start) < 1e-8:
                intervals[-1] = (intervals[-1][0], end)
            else:
                intervals.append((start, end))
    return intervals


def _follow_corner(state, block, points, previous_depth, internal, direction, point, emit):
    side = 1 if internal else -1
    for vertex in points:
        if (vertex.z - point.z) * direction < -1e-8:
            continue
        if side * (vertex.x - previous_depth) <= 0:
            if abs(vertex.x - point.x) > 1e-12:
                fraction = (previous_depth - point.x) / (vertex.x - point.x)
                if 0 <= fraction <= 1:
                    emit(Point2(previous_depth, point.z + (vertex.z - point.z) * fraction))
            return
        emit(vertex)
        point = vertex


def roughing_cycle(state, syntax, block):
    reference = syntax.cycle_args[0] if syntax.cycle_args else ""
    mid, falz, falx, fal, ff1, ff2, ff3, variant, dwell, chip, retract, gmode, dmode = arguments(
        state, replace(syntax, cycle_args=syntax.cycle_args[1:]), 8, 13
    )
    variant = integer(variant, 1, 12, "VARI")
    positive(mid, ff1, ff2, ff3)
    nonnegative(falz, falx, fal, dwell, chip, retract)
    if fal or dwell or chip or gmode or dmode:
        unsupported(
            "CYCLE95 contour-normal allowance, chip breaking and extended G/diameter modes are not implemented",
            "UNSUPPORTED_SINUMERIK_CYCLE",
        )
    profile = contour_profile(state, reference)
    _nose_compensation_notice(state, block)
    base = (variant - 1) % 4 + 1
    internal, facing = base in {3, 4}, base in {2, 4}
    scale = state.unit_scale
    side = -1 if internal else 1
    offset = build_offset_profile(profile, side * 2 * state.x_value(falx), falz * scale, not internal)
    origin = state.position
    if variant <= 4 or variant >= 9:
        _rough_passes(
            state,
            block,
            offset,
            facing,
            internal,
            mid * scale,
            (retract or 1) * scale,
            ff1 * state.feed_scale,
            ff2 * state.feed_scale,
        )
    if variant >= 5:
        _finish_profile(state, block, profile, ff3 * state.feed_scale)
    state.emit(Point2(state.position.x, origin.z), block, cycle=True)
    state.emit(origin, block, cycle=True)


def _nose_compensation_notice(state, block):
    if state.edge and state.tools.get(state.tool, {}).get("noseRadius", 0):
        state.diagnostics.append(
            Diagnostic(
                "UNVERIFIED_SINUMERIK_CYCLE95_NOSE_COMPENSATION",
                "CYCLE95 uses the nominal contour; automatic controller nose compensation is not modeled",
                "warning",
                "unverified",
                block.index + 1,
                block.raw,
            )
        )


def _rough_passes(state, block, profile, facing, internal, maximum, retract, feed, relief_feed):
    points, direction = _polyline(profile, facing, state.tolerance)
    original_depth = state.position.z if facing else state.position.x
    stock = min(original_depth, min(p.x for p in points)) if internal else max(original_depth, max(p.x for p in points))
    limit = max(p.x for p in points) if internal else min(p.x for p in points)
    distance = abs(stock - limit)
    positive(distance)
    count = max(1, math.ceil(distance / maximum))
    side = 1 if internal else -1
    safe_travel = points[0].z - direction * retract

    def emit(point, move=1, value=feed):
        target = Point2(point.z, point.x) if facing else point
        state.emit(target, block, move=move, feed=value if move else None, cycle=True)

    for index in range(1, count + 1):
        checkpoint("cycle_iterations")
        depth = stock + side * distance * index / count
        previous = stock + side * distance * (index - 1) / count
        for start, end in _cut_intervals(points, depth, internal, direction):
            emit(Point2(stock - side * retract, safe_travel), 0)
            emit(Point2(depth, safe_travel), 0)
            emit(Point2(depth, start))
            emit(Point2(depth, end))
            _follow_corner(
                state,
                block,
                points,
                previous,
                internal,
                direction,
                Point2(depth, end),
                lambda p: emit(p, value=relief_feed),
            )
            current = Point2(state.position.z, state.position.x) if facing else state.position
            emit(Point2(current.x - side * retract, current.z - direction * retract))
            emit(Point2(stock - side * retract, current.z - direction * retract), 0)


def _finish_profile(state, block, profile, feed):
    first = profile[0].start
    state.emit(Point2(first.x / 2, state.position.z), block, cycle=True)
    state.emit(Point2(first.x / 2, first.z), block, cycle=True)
    for segment in profile:
        state.emit(
            Point2(segment.end.x / 2, segment.end.z),
            block,
            move=segment.move,
            feed=feed,
            radius=segment.radius if segment.has_radius else None,
            i=(segment.center.x - segment.start.x) / 2 if segment.has_center else None,
            k=segment.center.z - segment.start.z if segment.has_center else None,
            cycle=True,
        )
