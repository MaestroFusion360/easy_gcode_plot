"""Resolve trace geometry, compensation and execution-step ownership."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..compensation.milling import apply_milling_cutter_compensation_with_owners
from ..geometry import resolve_arc
from ..milling.heidenhain_corners import prepare_corner_compensation
from ..milling.kinematics import profile_from_snapshot, transform_vector
from ..runtime.diagnostics import diagnostic_from_exception as _diagnostic_from_exception
from .arc_validation import _validate_turning_arc_source
from .resources import SemanticError
from .types import Diagnostic, TraceMotion


def _compensation_frame(motion: TraceMotion, *, local: bool) -> TraceMotion:
    """Move resolved geometry between fixed WCS display and the local cutter plane."""
    matrix = motion.orientation
    if matrix is None:
        return motion
    offset = motion.orientation_offset
    rotation = tuple(tuple(matrix[column][row] for column in range(3)) for row in range(3)) if local else matrix

    def point(value):
        source = tuple(value[i] - offset[i] for i in range(3)) if local else value
        transformed = transform_vector(rotation, source)
        return transformed if local else tuple(transformed[i] + offset[i] for i in range(3))

    def vector(value):
        return transform_vector(rotation, value)

    start = point((motion.start_x, motion.start_y, motion.start_z))
    end = point((motion.end_x, motion.end_y, motion.end_z))
    delta = vector((motion.i or 0.0, motion.j or 0.0, motion.k or 0.0))
    center_offset = motion.absolute_center_offset or offset
    center_offset = point(center_offset)
    has_ijk = any(value is not None for value in (motion.i, motion.j, motion.k))
    arc = motion.arc
    if arc is not None:
        normal = arc.normal
        if normal is None and not local:
            normal = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}[arc.plane]
        arc = replace(
            arc,
            center=point(arc.center),
            normal=vector(normal) if normal is not None else None,
        )
    return replace(
        motion,
        start_x=start[0],
        start_y=start[1],
        start_z=start[2],
        end_x=end[0],
        end_y=end[1],
        end_z=end[2],
        i=delta[0] if has_ijk else None,
        j=delta[1] if has_ijk else None,
        k=delta[2] if has_ijk else None,
        absolute_center_offset=center_offset,
        arc=arc,
    )


def _motion_with_step_metadata(motion, step, language, threading):
    threading = threading or motion.threading
    feed_mode = motion.feed_mode if motion.threading else step.feed_mode
    x_scale = 0.5 if language == "fanuc_turn" else 1.0
    compensation_status = (
        "APPLIED"
        if motion.compensation_applied
        else ("UNVERIFIED" if motion.compensation_mode in (41, 42) else "NOT_APPLIED")
    )
    current_metadata = (
        motion.x_scale,
        motion.feed_mode,
        motion.spindle_rpm,
        motion.spindle_mode,
        motion.surface_speed_m_min,
        motion.spindle_limit_rpm,
        motion.spindle_running,
        motion.compensation_status,
        motion.threading,
    )
    expected_metadata = (
        x_scale,
        feed_mode,
        step.spindle_rpm,
        step.spindle_mode,
        step.surface_speed_m_min,
        step.spindle_limit_rpm,
        step.spindle_running,
        compensation_status,
        threading,
    )
    if current_metadata == expected_metadata:
        return motion
    return replace(
        motion,
        x_scale=x_scale,
        feed_mode=feed_mode,
        spindle_rpm=step.spindle_rpm,
        spindle_mode=step.spindle_mode,
        surface_speed_m_min=step.surface_speed_m_min,
        spindle_limit_rpm=step.spindle_limit_rpm,
        spindle_running=step.spindle_running,
        compensation_status=compensation_status,
        threading=threading,
    )


def _steps_with_emitted_counts(steps, emitted_counts):
    return tuple(
        step if step.emitted_count == emitted_counts[index] else replace(step, emitted_count=emitted_counts[index])
        for index, step in enumerate(steps)
    )


def _compensation_diagnostics(result, motions, *, code, message, predicate):
    """Attach cutter-compensation diagnostics to every affected source block."""
    blocks = result.program.blocks if result.program is not None else ()
    diagnostics = []
    seen_blocks = set()
    for motion in motions:
        if not predicate(motion):
            continue
        block_index = motion.source_block
        if block_index is None or block_index in seen_blocks:
            continue
        seen_blocks.add(block_index)
        block = blocks[block_index] if 0 <= block_index < len(blocks) else None
        diagnostics.append(
            Diagnostic(
                code,
                message,
                "warning",
                "unverified",
                block_index + 1,
                None if block is None else block.raw,
            )
        )
    return tuple(diagnostics)


def _resolve_milling_compensation(result, motions, motion_step_owners, milling_tools, kinematics):
    """Apply verified local-plane offsets or retain the unverified C-table trace."""
    profile = profile_from_snapshot(result.kinematics_definition)
    table_c = profile is not None and profile.continuous_c_table
    diagnostics = ()
    if table_c:
        diagnostics = _compensation_diagnostics(
            result,
            motions,
            code="UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION",
            message=(
                "G41/G42 cutter compensation is not supported for a vertical C table; "
                "the plotted path is the programmed, uncompensated tool-tip path"
            ),
            predicate=lambda motion: motion.compensation_mode in (41, 42),
        )
    else:
        local_motions = [_compensation_frame(motion, local=True) for motion in motions]
        corner_diagnostics = ()
        if result.source_dialect == "heidenhain" and any(
            motion.source_kind in {"heidenhain_rnd", "heidenhain_chf"} for motion in local_motions
        ):
            local_motions, motion_step_owners, corner_diagnostics, failing_owner = prepare_corner_compensation(
                result.program, local_motions, motion_step_owners, milling_tools
            )
            if corner_diagnostics:
                result = replace(
                    result,
                    ok=False,
                    complete=False,
                    execution_steps=_partial_steps_after_geometry_failure(
                        result.execution_steps, motion_step_owners, failing_owner
                    ),
                )
        motions, motion_step_owners = apply_milling_cutter_compensation_with_owners(
            local_motions,
            milling_tools or {},
            motion_step_owners,
        )
        motions = [_compensation_frame(motion, local=False) for motion in motions]
        diagnostics = corner_diagnostics + _compensation_diagnostics(
            result,
            motions,
            code="UNVERIFIED_CUTTER_COMPENSATION",
            message=("G41/G42 requires a configured milling cutter and supported resolved line/arc/helix geometry"),
            predicate=lambda motion: motion.compensation_mode in (41, 42) and not motion.compensation_applied,
        )

    emitted_counts = [0] * len(result.execution_steps)
    for owner in motion_step_owners:
        emitted_counts[owner] += 1
    result = replace(result, execution_steps=_steps_with_emitted_counts(result.execution_steps, emitted_counts))
    return result, motions, diagnostics


def _emitted_counts_for_owners(steps, owners):
    counts = [0] * len(steps)
    for owner in owners:
        counts[owner] += 1
    return counts


def _partial_steps_after_geometry_failure(steps, owners, failing_index):
    emitted_counts = _emitted_counts_for_owners(steps, owners)
    partial = []
    for index, step in enumerate(steps):
        if index > failing_index:
            break
        partial.append(replace(step, emitted_count=emitted_counts[index], stop=(step.stop or index == failing_index)))
    return tuple(partial)


def _resolve_geometry_motion(motion, program, language, arc_type, tolerance):
    """Resolve one motion and attach source location to geometry diagnostics."""
    try:
        arc_type = 1 if language == "fanuc_turn" and motion.cycle_generated else (motion.source_arc_type or arc_type)
        if language == "fanuc_turn":
            _validate_turning_arc_source(motion, arc_type, tolerance)
        elif (
            arc_type == 2
            and motion.source_arc_type is None
            and any(v is not None for v in (motion.i, motion.j, motion.k))
        ):
            offset = motion.absolute_center_offset or motion.orientation_offset
            motion = replace(
                motion, i=(motion.i or 0) + offset[0], j=(motion.j or 0) + offset[1], k=(motion.k or 0) + offset[2]
            )
        return resolve_arc(motion, source_arc_type=arc_type, tolerance=tolerance), None
    except SemanticError as exc:
        diagnostic = _diagnostic_from_exception(exc, program)
        if diagnostic.line is None and motion.source_block is not None:
            block = program.blocks[motion.source_block] if program is not None else None
            diagnostic = replace(diagnostic, line=motion.source_block + 1, raw=None if block is None else block.raw)
        return None, diagnostic


@dataclass
class ResolvedTrace:
    """Keep every published motion paired with its execution-step owner."""

    motions: list[TraceMotion] = field(default_factory=list)
    owners: list[int] = field(default_factory=list)

    def append(self, motion, owner):
        self.motions.append(motion)
        self.owners.append(owner)

    def emitted_counts(self, steps):
        return _emitted_counts_for_owners(steps, self.owners)
