"""Programmed-contour RND/CHF geometry, before the shared cutter compensation.

Normative source: iTNC 530 60642x-04, 737759-23, pp. 237–238.
Offset loci locate tangent-circle centers; they do not compensate the cutter.
"""

import math
from dataclasses import dataclass, replace

from ..api.resources import SemanticError, checkpoint
from ..api.types import Diagnostic
from ..compensation.milling.joins import (
    _arc_arc_intersections,
    _get_progress,
    _line_arc_intersections,
    _line_line_intersection,
)
from ..compensation.milling.offset import _offset_arc, _offset_line, _tool_radius
from ..compensation.milling.projection import _project_motion, _projected_to_motion
from ..frontend.model import Block
from .heidenhain_values import scalar

_TOL = 1e-7


@dataclass(frozen=True)
class Corner:
    command: str
    size: float
    feed: float | None
    block: Block
    motion_index: int
    step_index: int
    frame: object

    def error(self, message):
        raise SemanticError(
            "INVALID_HEIDENHAIN_CORNER",
            f"{self.command}: {message}",
            "invalid_geometry",
            line=self.block.index + 1,
            raw=self.block.raw,
        )


def _tangent(motion, point):
    if motion.is_line:
        vector = (motion.end[0] - motion.start[0], motion.end[1] - motion.start[1])
    else:
        x, y = point[0] - motion.center[0], point[1] - motion.center[1]
        vector = (y, -x) if motion.source.move == 2 else (-y, x)
    length = math.hypot(*vector)
    return tuple(value / length for value in vector)


def _geometry(projected):
    """Reuse XYZ/arc conversion without marking programmed geometry compensated."""
    source = projected.source
    return replace(
        _projected_to_motion(projected, comp_mode=source.compensation_mode, source_kind=source.source_kind),
        compensation_applied=source.compensation_applied,
        compensation_status=source.compensation_status,
        additional_turns=0,
    )


def _neighbors(corner, incoming, outgoing):
    first, second = _project_motion(incoming), _project_motion(outgoing)
    if first is None or second is None:
        corner.error("two nonzero feed contour elements are required")
    if incoming.plane != outgoing.plane or first.is_helix or second.is_helix:
        corner.error("adjacent elements must lie in the same working plane; spatial/helical corners are unsupported")
    if incoming.tool != outgoing.tool or incoming.compensation_mode != outgoing.compensation_mode:
        corner.error("tool and radius compensation must remain the same on both sides")
    if math.dist(first.end, second.start) > _TOL or abs(first.end_w - second.start_w) > _TOL:
        corner.error("adjacent contour elements are not continuous")
    if any(m.additional_turns or (m.arc is not None and m.arc.full_circle) for m in (incoming, outgoing)):
        corner.error("full circles and multi-turn neighbors have no unambiguous local corner")
    before, after = _tangent(first, first.end), _tangent(second, second.start)
    cross = before[0] * after[1] - before[1] * after[0]
    if abs(cross) <= _TOL:
        corner.error("collinear, tangent or reversing elements do not define a unique corner")
    return first, second, before, after, 1 if cross > 0 else -1


def _chamfer(corner, first, second, before, after):
    if not first.is_line or not second.is_line:
        corner.error("CHF requires two straight lines (manual p. 237)")
    vertex = first.end
    start = tuple(vertex[i] - corner.size * before[i] for i in range(2))
    end = tuple(vertex[i] + corner.size * after[i] for i in range(2))
    return start, end, None


def _intersections(first, second):
    if first.is_line and second.is_line:
        return _line_line_intersection(first, second)
    if first.is_line:
        return _line_arc_intersections(first, second)
    if second.is_line:
        return _line_arc_intersections(second, first)
    return _arc_arc_intersections(first, second)


def _contact(motion, center):
    if motion.is_line:
        tangent = _tangent(motion, motion.start)
        distance = sum((center[i] - motion.start[i]) * tangent[i] for i in range(2))
        return tuple(motion.start[i] + distance * tangent[i] for i in range(2))
    distance = math.dist(center, motion.center)
    return tuple(motion.center[i] + (center[i] - motion.center[i]) * motion.radius / distance for i in range(2))


def _within(motion, point):
    progress = _get_progress(motion, point, _TOL)
    return progress is not None and _TOL < progress[0] < progress[1] - _TOL


def _rounding(corner, first, second, sign):
    distance = sign * corner.size
    loci = [_offset_line(m, distance) if m.is_line else _offset_arc(m, distance, _TOL) for m in (first, second)]
    if any(locus is None for locus in loci):
        corner.error("radius does not admit a regular local tangent-circle locus")
    candidates = []
    for center in _intersections(*loci):
        checkpoint()
        start, end = _contact(first, center), _contact(second, center)
        if not _within(first, start) or not _within(second, end):
            continue
        # Accept only the local arc (less than a half turn), tangent in the
        # direction of travel. Never choose a distant solution by proximity.
        v1, v2 = (start[0] - center[0], start[1] - center[1]), (end[0] - center[0], end[1] - center[1])
        sweep = (sign * math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])) % math.tau
        if not _TOL < sweep < math.pi - _TOL:
            continue
        tangents = [(-sign * v[1] / corner.size, sign * v[0] / corner.size) for v in (v1, v2)]
        if any(math.dist(t, _tangent(m, p)) > _TOL for t, m, p in zip(tangents, (first, second), (start, end))):
            continue
        if not any(math.dist(center, candidate[2]) <= _TOL for candidate in candidates):
            candidates.append((start, end, center))
    if len(candidates) != 1:
        corner.error("radius does not fit adjacent elements or the local tangent solution is ambiguous")
    return candidates[0]


def build_corner(corner, incoming, outgoing):
    first, second, before, after, sign = _neighbors(corner, incoming, outgoing)
    start, end, center = (
        _chamfer(corner, first, second, before, after)
        if corner.command == "CHF"
        else _rounding(corner, first, second, sign)
    )
    if not _within(first, start) or not _within(second, end):
        corner.error("size consumes or exceeds an adjacent element")
    source = replace(
        incoming,
        move=1 if center is None else (3 if sign > 0 else 2),
        source_block=corner.block.index,
        source_nlabel=corner.block.nlabel,
        source_raw=corner.block.raw,
        source_kind="heidenhain_" + corner.command.lower(),
        feed=corner.feed,
        spindle_rpm=outgoing.spindle_rpm,
        spindle_running=outgoing.spindle_running,
    )
    inserted = replace(
        first, source=source, start=start, end=end, center=center, radius=corner.size if center else None
    )
    return _geometry(replace(first, end=start)), _geometry(inserted), _geometry(replace(second, start=end))


def queue_corner(state, syntax, values, block):
    size = values["R" if syntax.command == "RND" else "L"] * state.scale
    feed = values["F"] * state.scale if "F" in values else state.feed
    corner = Corner(syntax.command, size, feed, block, len(state.motions) - 1, len(state.steps), state.frame)
    if not math.isfinite(size) or size <= 0:
        corner.error("size must be finite and positive")
    if feed is not None and (not math.isfinite(feed) or feed < 0):
        corner.error("feed must be finite and nonnegative")
    if not state.motions:
        corner.error("missing preceding contour element")
    previous = state.motions[-1]
    native = state.program.blocks[previous.source_block].native_syntax
    if native.kind != "motion" or previous.cycle_generated or previous.source_block != state.last_contour_block:
        corner.error("preceding element must be a native contour movement")
    if previous.move == 0:
        corner.error("a rapid movement cannot bound a corner")
    if _unsafe_motion(state, native):
        corner.error("preceding element cannot use machine coordinates, a retraction or a cycle call")
    _check_coordinates(corner, native, previous)
    if feed == 0:
        state.diagnostics.append(
            Diagnostic(
                "HEIDENHAIN_ZERO_FEED",
                "F0: geometric path retained; feed duration is undefined",
                "warning",
                "unverified",
                block.index + 1,
                block.raw,
            )
        )
    state.pending_corner = corner


def _check_coordinates(corner, syntax, motion):
    if corner.command != "RND" or motion.compensation_mode in (41, 42):
        return
    axes = {17: "XY", 18: "XZ", 19: "YZ"}[motion.plane]
    addresses = {word.address for word in syntax.positioning_words}
    missing = any(axis not in addresses and "I" + axis not in addresses for axis in axes)
    if syntax.command not in {"LP", "CP"} and missing:
        corner.error("RND without radius compensation requires both working-plane coordinates (manual p. 238)")


def guard_corner(state, syntax):
    corner = state.pending_corner
    if corner is None:
        return
    if syntax.kind not in {"empty", "comment", "center", "motion", "parameter"} or syntax.cycle_code is not None:
        corner.error("missing following contour element before " + syntax.command)
    if syntax.kind == "motion" and (_unsafe_motion(state, syntax) or syntax.word("FMAX")):
        corner.error("following element cannot contain rapid motion, machine-coordinate motion or a cycle call")


def _unsafe_motion(state, syntax):
    return state.cycle_modal or any(
        function.parameters or scalar(function.code, state.parameters) in {89, 91, 99, 140}
        for function in syntax.machine_functions
    )


def resolve_corner(state, outgoing):
    corner = state.pending_corner
    if corner is None:
        return outgoing
    if state.frame != corner.frame:
        corner.error("coordinate frame changed between adjacent elements")
    _check_coordinates(corner, state.program.blocks[state.pc].native_syntax, outgoing)
    incoming, inserted, outgoing = build_corner(corner, state.motions[corner.motion_index], outgoing)
    checkpoint("generated_motions")
    state.motions[corner.motion_index] = incoming
    state.trace_motions[corner.motion_index] = state.machine_motion(incoming)
    state.publish_motion(inserted, owner=corner.step_index)
    state.pending_corner = None
    return outgoing


def prepare_corner_compensation(program, motions, owners, tools):
    """Adapt native zero-radius limits without changing the shared offset solver.

    A rounding/entry arc exactly equal to the inward cutter offset collapses
    to its center. Removing that zero-length arc lets the existing line entry
    and join logic reach the same point. DEP's remaining line cancels RL/RR.
    This adapter runs only for native programs containing RND/CHF.
    """
    output, output_owners = [], []
    collapsed_departure = None
    for motion, owner in zip(motions, owners):
        checkpoint()
        syntax = program.blocks[motion.source_block].native_syntax
        radius = _tool_radius((tools or {}).get(motion.tool or ""))
        arc = motion.arc
        inward = (motion.move == 3 and motion.compensation_mode == 41) or (
            motion.move == 2 and motion.compensation_mode == 42
        )
        native_arc = syntax.command == "RND" or syntax.command.startswith(("APPR ", "DEP "))
        if native_arc and arc is not None and radius is not None and inward:
            if arc.radius < radius - _TOL:
                diagnostic = Diagnostic(
                    "HEIDENHAIN_CORNER_TOOL_TOO_LARGE",
                    f"{syntax.command}: inward arc radius {arc.radius:g} is smaller than cutter radius {radius:g}",
                    "error",
                    "invalid_geometry",
                    motion.source_block + 1,
                    motion.source_raw,
                )
                return output, output_owners, (diagnostic,), owner
            if abs(arc.radius - radius) <= _TOL:
                if syntax.command.startswith("DEP "):
                    collapsed_departure = owner
                continue
        if owner == collapsed_departure:
            motion = replace(motion, compensation_mode=40)
        output.append(motion)
        output_owners.append(owner)
    return output, output_owners, (), None
