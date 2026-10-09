"""Small public facade for the native FANUC CNC kernel."""

from __future__ import annotations

import math
from dataclasses import replace

from ..compensation.milling import apply_milling_cutter_compensation_with_owners
from ..frontend.model import Motion, Point2, Program
from ..frontend.program import (
    eval_words,
    parse_program,
    resolve_cycle_profile_indices,
    try_wcs_from_gcode,
    x_delta_to_diameter,
    x_value_to_diameter,
)
from ..geometry import resolve_arc
from ..geometry.coordinates import WcsOffset, WcsOffsets  # noqa: F401 - compatibility re-export
from ..geometry.coordinates import milling_extended_wcs_offsets as _mill_extended_wcs_offsets
from ..geometry.coordinates import milling_wcs_offsets as _mill_wcs_offsets
from ..geometry.coordinates import published_extended_wcs_offsets as _result_extended_wcs_offsets
from ..geometry.coordinates import published_wcs_offsets as _result_wcs_offsets
from ..geometry.coordinates import turning_extended_wcs_offsets as _turn_extended_wcs_offsets
from ..geometry.coordinates import turning_wcs_offsets as _turn_wcs_offsets
from ..geometry.direct import build_profile_segments
from ..milling import execute_milling
from ..milling.kinematics import InvalidKinematicsProfile, load_catalog, transform_vector
from ..runtime.diagnostics import SUPPORTED_TURNING_G_CODES as SUPPORTED_G_CODES  # noqa: F401
from ..runtime.diagnostics import (
    diagnostic_from_exception as _diagnostic_from_exception,
)
from ..runtime.events import program_end_code
from ..runtime.execution import resolve_program_tools
from ..runtime.execution import semantic_instructions as _semantic_instructions
from ..runtime.trace import build_source_motion_trace_with_steps as _build_source_motion_trace_with_steps
from ..runtime.trace_metadata import threading_step_flags as _threading_step_flags
from ..turning.dialect import validate_system
from .conversion import trace_motion as _trace_motion
from .resources import ExecutionBudget, ExecutionLimits, SemanticError, active_budget
from .types import (
    Diagnostic,
    ExecutionResult,
    SemanticInstruction,  # noqa: F401 - compatibility re-export
    TraceMotion,  # noqa: F401 - compatibility re-export
)

__all__ = (
    "Diagnostic",
    "ExecutionResult",
    "SUPPORTED_G_CODES",
    "SUPPORTED_LANGUAGES",
    "SemanticInstruction",
    "TraceMotion",
    "WcsOffset",
    "WcsOffsets",
    "execute",
)

SUPPORTED_LANGUAGES = frozenset({"fanuc_turn", "fanuc_mill"})
SUPPORTED_SOURCE_DIALECTS = frozenset({"fanuc", "sinumerik"})


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


def _ijk_radius_mismatch(motion: TraceMotion, source_arc_type: int) -> float | None:
    axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}
    plane_axes = axes.get(motion.plane)
    if motion.move not in (2, 3) or plane_axes is None:
        return None
    start = (motion.start_x * motion.x_scale, motion.start_y, motion.start_z)
    end = (motion.end_x * motion.x_scale, motion.end_y, motion.end_z)
    offsets = (None if motion.i is None else motion.i * motion.x_scale, motion.j, motion.k)
    first_axis, second_axis = plane_axes
    if offsets[first_axis] is None and offsets[second_axis] is None:
        return None
    center_first = offsets[first_axis] or 0.0
    center_second = offsets[second_axis] or 0.0
    if source_arc_type == 1:
        center_first += start[first_axis]
        center_second += start[second_axis]
    elif motion.source_arc_type is None:
        center_offset = motion.absolute_center_offset or motion.orientation_offset
        center_first += center_offset[first_axis] * (motion.x_scale if first_axis == 0 else 1)
        center_second += center_offset[second_axis]
    start_radius = math.hypot(start[first_axis] - center_first, start[second_axis] - center_second)
    if start_radius <= 1e-10:
        return None
    end_radius = math.hypot(end[first_axis] - center_first, end[second_axis] - center_second)
    return abs(start_radius - end_radius)


def _autodetect_arc_type(
    motions: tuple[TraceMotion, ...], *, tolerance: float, fallback: int, turning: bool = False
) -> int:
    tolerance = max(0.0, float(tolerance))
    for motion in motions:
        if motion.orientation is not None:
            motion = _compensation_frame(motion, local=True)
        if turning:
            # Detection runs before per-step geometry metadata is attached.
            # Native turning X/I values are diameters; compare physical radii.
            motion = replace(motion, x_scale=0.5)
        relative_error = _ijk_radius_mismatch(motion, 1)
        absolute_error = _ijk_radius_mismatch(motion, 2)
        if relative_error is None and absolute_error is None:
            continue
        relative_valid = relative_error is not None and relative_error <= tolerance
        absolute_valid = absolute_error is not None and absolute_error <= tolerance
        if relative_valid != absolute_valid:
            return 1 if relative_valid else 2
    return fallback


def _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type):
    if result.source_dialect == "sinumerik":
        return source_arc_type
    if language not in ("fanuc_mill", "fanuc_turn") or not autodetect_arc_type:
        return source_arc_type
    return _autodetect_arc_type(
        result.motions,
        tolerance=arc_tolerance,
        fallback=source_arc_type,
        turning=language == "fanuc_turn",
    )


def _validate_turning_arc_source(motion, source_arc_type: int, tolerance: float) -> None:
    """Reject an I/K arc that cannot represent the selected turning center mode."""
    if motion.move not in (2, 3) or motion.radius is not None and source_arc_type == 3:
        return
    if source_arc_type == 3:
        raise SemanticError("TURNING_ARC_REQUIRES_R", "Radius arc mode requires an R word", "invalid_geometry")
    mismatch = _ijk_radius_mismatch(motion, source_arc_type)
    if mismatch is not None and mismatch > max(0.0, float(tolerance)):
        raise SemanticError(
            "INVALID_TURNING_ARC_CENTER",
            f"I/K center does not fit the arc endpoints in the selected mode (radius mismatch {mismatch:.4g} mm)",
            "invalid_geometry",
        )


def _profile_arc_diagnostic(segment, blocks, variables, step, source_arc_type, tolerance):
    if segment.move not in (2, 3):
        return None
    if source_arc_type == 3:
        if segment.has_radius:
            return None
        code = "TURNING_ARC_REQUIRES_R"
        message = "Radius arc mode requires an R word in the P/Q profile"
    elif not segment.has_center:
        return None
    else:
        if source_arc_type == 1:
            center_x, center_z = segment.center.x * 0.5, segment.center.z
        else:
            arc_words = eval_words(blocks[segment.block].parsed_words, variables)
            center_x = arc_words.get("I", 0.0) * step.unit_scale
            center_z = arc_words.get("K", 0.0) * step.unit_scale
        start_radius = math.hypot(segment.start.x * 0.5 - center_x, segment.start.z - center_z)
        end_radius = math.hypot(segment.end.x * 0.5 - center_x, segment.end.z - center_z)
        mismatch = abs(start_radius - end_radius)
        if mismatch <= max(0.0, float(tolerance)):
            return None
        code = "INVALID_TURNING_ARC_CENTER"
        message = f"P/Q arc center does not fit the endpoints in the selected mode (radius mismatch {mismatch:.4g} mm)"
    return Diagnostic(code, message, "error", "invalid_geometry", segment.block + 1, blocks[segment.block].raw)


def _invalid_turning_profile_cycles(result, source_arc_type: int, tolerance: float, gcode_system: str = "A"):
    """Preflight P/Q arc words before publishing any motions from their cycles."""
    if result.program is None or source_arc_type not in (1, 2, 3):
        return {}
    blocks = result.program.blocks
    invalid = {}
    for step_index, step in enumerate(result.execution_steps):
        words = dict(step.words)
        gcode = words.get("G")
        if gcode not in (70, 71, 72, 73) or "P" not in words or "Q" not in words or not step.emitted_count:
            continue
        bounds = resolve_cycle_profile_indices(
            blocks, step.source_block, int(words["P"]), int(words["Q"]), prefer_preceding=gcode == 70
        )
        if bounds is None or step.position is None:
            continue
        variables = dict(step.variables)
        profile = build_profile_segments(
            blocks,
            *bounds,
            step.position[0],
            step.position[2],
            variables,
            x_is_diameter=step.x_is_diameter,
            unit_scale=step.unit_scale,
            gcode_system=gcode_system,
            distance_absolute=step.absolute,
        )
        for segment in profile:
            diagnostic = _profile_arc_diagnostic(segment, blocks, variables, step, source_arc_type, tolerance)
            if diagnostic is not None:
                invalid[step_index] = diagnostic
                break
    return invalid


# Compatibility for the export service's existing internal import.
_autodetect_milling_arc_type = _autodetect_arc_type


def _motion_with_step_metadata(motion, step, language, threading):
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
        step.feed_mode,
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
        feed_mode=step.feed_mode,
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


def _invalid_execution_request(language: str, source_dialect: str) -> ExecutionResult | None:
    if source_dialect not in SUPPORTED_SOURCE_DIALECTS:
        diagnostic = Diagnostic(
            code="UNSUPPORTED_SOURCE_DIALECT",
            message=f"Unsupported source dialect: {source_dialect}",
        )
    elif source_dialect == "sinumerik" and language != "fanuc_mill":
        diagnostic = Diagnostic(
            code="UNSUPPORTED_SINUMERIK_ISO_T",
            message=("SINUMERIK ISO Dialect T is not modeled yet; G291 currently supports milling ISO Dialect M only"),
            severity="error",
            status="unsupported",
        )
    elif language not in SUPPORTED_LANGUAGES:
        diagnostic = Diagnostic(
            code="UNSUPPORTED_LANGUAGE",
            message=f"Unsupported G-code language: {language}",
        )
    else:
        return None
    return ExecutionResult(
        ok=False,
        program=None,
        instructions=(),
        motions=(),
        diagnostics=(diagnostic,),
        executed_blocks=(),
        complete=False,
        language=language,
    )


def _execute_impl(
    source: str,
    language: str = "fanuc_turn",
    *,
    x_is_diameter: bool = True,
    lathe_gcode_system: str = "A",
    sinumerik_840d_sl: bool = True,
    skip_optional_blocks: bool = False,
    supplementary_angles: bool = False,
    pq_mm_for_g74758384: bool = False,
    default_unit_scale: float = 1.0,
    tools: dict[str, dict[str, object]] | None = None,
    home_x: float = 0.0,
    home_y: float = 0.0,
    home_z: float = 0.0,
    wcs_offsets: WcsOffsets | None = None,
    extended_wcs_offsets: WcsOffsets | None = None,
    milling_g73_retract_distance: float = 1.0,
    milling_g83_clearance: float = 1.0,
    milling_boring_shift_direction: tuple[float, float, float] = (-1.0, 0.0, 0.0),
    milling_tapping_retract_distance: float = 1.0,
    milling_tapping_full_retract: bool = False,
    emulate_g28_home: bool = False,
    include_instructions: bool = True,
    kinematics=None,
    source_dialect: str = "fanuc",
    tool_resolver=None,
) -> ExecutionResult:
    """Parse, compile, and trace a FANUC turning program.

    Unsupported position-changing commands fail closed at that block while
    preserving every trustworthy motion produced before it.
    """
    invalid_request = _invalid_execution_request(language, source_dialect)
    if invalid_request is not None:
        return invalid_request

    if language == "fanuc_mill":
        if isinstance(kinematics, str):
            try:
                kinematics = load_catalog()[kinematics]
            except (InvalidKinematicsProfile, KeyError) as exc:
                return ExecutionResult(
                    False,
                    None,
                    (),
                    (),
                    (
                        Diagnostic(
                            "INVALID_KINEMATICS_PROFILE",
                            f"Invalid kinematics profile: {kinematics}: {exc}",
                            "error",
                            "malformed",
                        ),
                    ),
                    (),
                    complete=False,
                    language=language,
                )
        mill_offsets = _mill_wcs_offsets(wcs_offsets)
        mill_offsets.update(_mill_extended_wcs_offsets(extended_wcs_offsets))
        return replace(
            execute_milling(
                source,
                skip_optional_blocks=skip_optional_blocks,
                default_unit_scale=default_unit_scale,
                home=(home_x, home_y, home_z),
                wcs_offsets=mill_offsets,
                g73_retract_distance=milling_g73_retract_distance,
                g83_clearance=milling_g83_clearance,
                boring_shift_direction=milling_boring_shift_direction,
                tapping_retract_distance=milling_tapping_retract_distance,
                tapping_full_retract=milling_tapping_full_retract,
                include_instructions=include_instructions,
                kinematics=kinematics,
                source_dialect=source_dialect,
                sinumerik_840d_sl=sinumerik_840d_sl,
                tool_resolver=tool_resolver,
            ),
            wcs_offsets=_result_wcs_offsets(mill_offsets),
            extended_wcs_offsets=_result_extended_wcs_offsets(mill_offsets),
        )

    lathe_gcode_system = validate_system(lathe_gcode_system)
    program: Program | None = None
    unsupported: tuple[Diagnostic, ...] = ()
    execution_diagnostics: list[Diagnostic] = []
    turn_offsets = _turn_wcs_offsets(wcs_offsets)
    turn_offsets.update(_turn_extended_wcs_offsets(extended_wcs_offsets))
    try:
        program = parse_program(source)
        tools = resolve_program_tools(program, tools, tool_resolver)
        rough, finish = [], []
        native_motions, trace_steps = _build_source_motion_trace_with_steps(
            program,
            rough,
            finish,
            x_is_diameter=x_is_diameter,
            gcode_system=lathe_gcode_system,
            pq_mm_for_g74758384=pq_mm_for_g74758384,
            supplementary_angles=supplementary_angles,
            default_unit_scale=default_unit_scale,
            skip_optional_blocks=skip_optional_blocks,
            home_x=home_x,
            home_z=home_z,
            wcs_offsets=turn_offsets,
            emulate_g28_home=emulate_g28_home,
            try_wcs_from_gcode_fn=try_wcs_from_gcode,
            x_value_to_diameter_fn=x_value_to_diameter,
            x_delta_to_diameter_fn=x_delta_to_diameter,
            motion_ctor=Motion,
            point_ctor=Point2,
            tools=tools,
            diagnostics=execution_diagnostics,
        )
        unsupported += tuple(execution_diagnostics)
    except Exception as exc:
        return ExecutionResult(
            ok=False,
            program=program,
            instructions=_semantic_instructions(program) if include_instructions else (),
            motions=(),
            diagnostics=tuple(execution_diagnostics) + (_diagnostic_from_exception(exc, program),),
            executed_blocks=(),
            complete=False,
        )

    signals = tuple(signal for step in trace_steps for signal in step.signals)
    events = tuple(event for step in trace_steps for event in step.events)
    return ExecutionResult(
        ok=not any(item.severity == "error" for item in unsupported),
        program=program,
        instructions=_semantic_instructions(program) if include_instructions else (),
        motions=tuple(_trace_motion(motion) for motion in native_motions),
        diagnostics=unsupported,
        executed_blocks=tuple(
            dict.fromkeys(motion.source_block for motion in native_motions if motion.source_block is not None)
        ),
        signals=signals,
        program_end=program_end_code(events),
        execution_steps=tuple(trace_steps),
        events=events,
        wcs_offsets=_result_wcs_offsets(turn_offsets),
        extended_wcs_offsets=_result_extended_wcs_offsets(turn_offsets),
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
    selected = getattr(kinematics, "id", kinematics)
    table_c = selected == "4ax_table_c"
    diagnostics = ()
    if table_c:
        diagnostics = _compensation_diagnostics(
            result,
            motions,
            code="UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION",
            message=(
                "G41/G42 cutter compensation is not supported for 4ax_table_c; "
                "the plotted path is the programmed, uncompensated tool-tip path"
            ),
            predicate=lambda motion: motion.compensation_mode in (41, 42),
        )
    else:
        local_motions = [_compensation_frame(motion, local=True) for motion in motions]
        motions, motion_step_owners = apply_milling_cutter_compensation_with_owners(
            local_motions,
            milling_tools or {},
            motion_step_owners,
        )
        motions = [_compensation_frame(motion, local=False) for motion in motions]
        diagnostics = _compensation_diagnostics(
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


def _capture_tool_resolver(resolver, resolved_tools):
    if resolver is None:
        return None

    def resolve(program):
        tools = resolver(program)
        resolved_tools["milling_tools"] = tools
        return tools

    return resolve


def _execution_arc_tolerance(value, language):
    if value is not None:
        return value
    return 0.01 if language == "fanuc_mill" else 0.001


def execute(
    source,
    language="fanuc_turn",
    *,
    limits=None,
    cancelled=None,
    source_arc_type=1,
    autodetect_arc_type=False,
    arc_tolerance=None,
    **options,
):
    """Execute once; resolve geometry and publish a self-contained immutable result.

    An optional tool_resolver receives the parsed Program once, before motion
    execution, and returns the tool geometry used by execution/compensation.
    Parsing and tool preparation share execution cancellation checkpoints.
    """
    arc_tolerance = _execution_arc_tolerance(arc_tolerance, language)
    token = active_budget.set(ExecutionBudget(limits or ExecutionLimits(), cancelled))
    resolved_tools = {"milling_tools": options.pop("milling_tools", None)}
    milling_correction_enabled = bool(options.pop("milling_correction_enabled", True))
    options["tool_resolver"] = _capture_tool_resolver(options.pop("tool_resolver", None), resolved_tools)
    try:
        result = _execute_impl(source, language, **options)
        result = replace(
            result,
            source_dialect=options.get("source_dialect", "fanuc"),
            lathe_gcode_system=validate_system(options.get("lathe_gcode_system", "A")),
            sinumerik_840d_sl=options.get("sinumerik_840d_sl", True),
        )
        effective_arc_type = _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type)
        motions, motion_step_owners, geometry_diagnostics, cursor = [], [], [], 0
        invalid_cycles = (
            _invalid_turning_profile_cycles(
                result, effective_arc_type, arc_tolerance, options.get("lathe_gcode_system", "A")
            )
            if language == "fanuc_turn"
            else {}
        )
        geometry_diagnostics.extend(invalid_cycles.values())
        step_index = 0
        try:
            threading_steps = (
                _threading_step_flags(result.execution_steps)
                if language == "fanuc_turn"
                else (False,) * len(result.execution_steps)
            )
            for step_index, step in enumerate(result.execution_steps):
                if step_index in invalid_cycles:
                    cursor += step.emitted_count
                    continue
                for motion in result.motions[cursor : cursor + step.emitted_count]:
                    threading = threading_steps[step_index] and motion.move == 1
                    motion = _motion_with_step_metadata(motion, step, language, threading)
                    resolved, diagnostic = _resolve_geometry_motion(
                        motion, result.program, language, effective_arc_type, arc_tolerance
                    )
                    if diagnostic is not None:
                        geometry_diagnostics.append(diagnostic)
                        continue
                    motions.append(resolved)
                    motion_step_owners.append(step_index)
                cursor += step.emitted_count
        except Exception as exc:
            diagnostic = _diagnostic_from_exception(exc, result.program)
            partial_steps = _partial_steps_after_geometry_failure(
                result.execution_steps, motion_step_owners, step_index
            )
            partial_events = tuple(event for step in partial_steps for event in step.events)
            partial_signals = tuple(signal for step in partial_steps for signal in step.signals)
            return replace(
                result,
                ok=False,
                motions=tuple(motions),
                diagnostics=result.diagnostics + (diagnostic,),
                executed_blocks=tuple(step.source_block for step in partial_steps),
                execution_steps=tuple(partial_steps),
                signals=partial_signals,
                program_end=program_end_code(partial_events),
                events=partial_events,
                complete=False,
                language=language,
            )
        if not result.execution_steps:
            motions = list(result.motions)
        if result.execution_steps:
            emitted_counts = _emitted_counts_for_owners(result.execution_steps, motion_step_owners)
            result = replace(
                result,
                execution_steps=_steps_with_emitted_counts(result.execution_steps, emitted_counts),
            )
        diagnostics = result.diagnostics + tuple(geometry_diagnostics)
        if language == "fanuc_mill" and milling_correction_enabled:
            result, motions, compensation_diagnostics = _resolve_milling_compensation(
                result, motions, motion_step_owners, resolved_tools["milling_tools"], options.get("kinematics")
            )
            diagnostics += compensation_diagnostics
        return replace(
            result,
            motions=tuple(motions),
            diagnostics=diagnostics,
            ok=result.ok and not any(item.severity == "error" for item in geometry_diagnostics),
            complete=result.complete,
            language=language,
            executed_blocks=tuple(step.source_block for step in result.execution_steps),
        )
    except Exception as exc:
        diagnostic = _diagnostic_from_exception(exc, None)
        return ExecutionResult(
            False,
            None,
            (),
            (),
            (diagnostic,),
            (),
            complete=False,
            language=language,
            source_dialect=options.get("source_dialect", "fanuc"),
        )
    finally:
        active_budget.reset(token)
