"""Validate execution requests and dispatch machine-specific execution."""

from __future__ import annotations

from dataclasses import replace

from ..conversion import trace_motion as _trace_motion
from ..frontend.model import Motion, Point2, Program
from ..frontend.program import parse_program, try_wcs_from_gcode, x_delta_to_diameter, x_value_to_diameter
from ..frontend.turning_dialect import validate_system
from ..geometry.coordinates import (
    WcsOffsets,
)
from ..geometry.coordinates import (
    milling_extended_wcs_offsets as _mill_extended_wcs_offsets,
)
from ..geometry.coordinates import (
    milling_wcs_offsets as _mill_wcs_offsets,
)
from ..geometry.coordinates import (
    published_extended_wcs_offsets as _result_extended_wcs_offsets,
)
from ..geometry.coordinates import (
    published_wcs_offsets as _result_wcs_offsets,
)
from ..geometry.coordinates import (
    turning_extended_wcs_offsets as _turn_extended_wcs_offsets,
)
from ..geometry.coordinates import (
    turning_wcs_offsets as _turn_wcs_offsets,
)
from ..machine.diagnostics import diagnostic_from_exception as _diagnostic_from_exception
from ..machine.events import program_end_code
from ..machine.execution import resolve_program_tools
from ..machine.execution import semantic_instructions as _semantic_instructions
from ..milling import execute_milling
from ..milling.heidenhain import execute_heidenhain
from ..milling.kinematics import InvalidKinematicsProfile, load_catalog
from ..runtime.trace import build_source_motion_trace_with_steps as _build_source_motion_trace_with_steps
from ..turning.sinumerik import execute_sinumerik_turning
from ..types import Diagnostic, ExecutionResult

SUPPORTED_SOURCE_DIALECTS = frozenset({"fanuc", "sinumerik", "heidenhain"})


SUPPORTED_LANGUAGES = frozenset({"fanuc_turn", "fanuc_mill"})


def _invalid_execution_request(language: str, source_dialect: str) -> ExecutionResult | None:
    if source_dialect not in SUPPORTED_SOURCE_DIALECTS:
        diagnostic = Diagnostic(
            code="UNSUPPORTED_SOURCE_DIALECT",
            message=f"Unsupported source dialect: {source_dialect}",
        )
    elif source_dialect == "heidenhain" and language != "fanuc_mill":
        diagnostic = Diagnostic(
            "UNSUPPORTED_HEIDENHAIN_TURNING", "Klartext execution supports milling only", status="unsupported"
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
    parsed_program=None,
    geometry_tolerance=0.01,
    turning_correction_enabled=True,
) -> ExecutionResult:
    """Parse, compile, and trace a FANUC turning program.

    Unsupported position-changing commands fail closed at that block while
    preserving every trustworthy motion produced before it.
    """
    invalid_request = _invalid_execution_request(language, source_dialect)
    if invalid_request is not None:
        return invalid_request

    if language == "fanuc_mill" and isinstance(kinematics, str):
        try:
            kinematics = load_catalog()[kinematics]
        except (InvalidKinematicsProfile, KeyError):
            return ExecutionResult(
                False,
                None,
                (),
                (),
                (
                    Diagnostic(
                        "INVALID_KINEMATICS_PROFILE",
                        "The selected kinematics profile is missing or invalid.",
                        "error",
                        "malformed",
                    ),
                ),
                (),
                complete=False,
                language=language,
                source_dialect=source_dialect,
            )

    if source_dialect == "heidenhain":
        mill_offsets = _mill_wcs_offsets(wcs_offsets)
        mill_offsets.update(_mill_extended_wcs_offsets(extended_wcs_offsets))
        return replace(
            execute_heidenhain(
                source,
                parsed_program=parsed_program,
                default_unit_scale=default_unit_scale,
                home=(home_x, home_y, home_z),
                emulate_home=emulate_g28_home,
                wcs_offsets=mill_offsets,
                skip_optional_blocks=skip_optional_blocks,
                tool_resolver=tool_resolver,
                include_instructions=include_instructions,
                arc_tolerance=geometry_tolerance,
                kinematics=kinematics,
            ),
            wcs_offsets=_result_wcs_offsets(mill_offsets),
            extended_wcs_offsets=_result_extended_wcs_offsets(mill_offsets),
        )

    if language == "fanuc_mill":
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
                parsed_program=parsed_program,
            ),
            wcs_offsets=_result_wcs_offsets(mill_offsets),
            extended_wcs_offsets=_result_extended_wcs_offsets(mill_offsets),
        )

    return _execute_turning(
        source,
        source_dialect=source_dialect,
        lathe_gcode_system=lathe_gcode_system,
        x_is_diameter=x_is_diameter,
        pq_mm_for_g74758384=pq_mm_for_g74758384,
        supplementary_angles=supplementary_angles,
        default_unit_scale=default_unit_scale,
        skip_optional_blocks=skip_optional_blocks,
        home_x=home_x,
        home_z=home_z,
        wcs_offsets=wcs_offsets,
        extended_wcs_offsets=extended_wcs_offsets,
        emulate_g28_home=emulate_g28_home,
        tools=tools,
        tool_resolver=tool_resolver,
        parsed_program=parsed_program,
        include_instructions=include_instructions,
        geometry_tolerance=geometry_tolerance,
        sinumerik_840d_sl=sinumerik_840d_sl,
        turning_correction_enabled=turning_correction_enabled,
    )


def _execute_turning(
    source,
    *,
    source_dialect,
    lathe_gcode_system,
    x_is_diameter,
    pq_mm_for_g74758384,
    supplementary_angles,
    default_unit_scale,
    skip_optional_blocks,
    home_x,
    home_z,
    wcs_offsets,
    extended_wcs_offsets,
    emulate_g28_home,
    tools,
    tool_resolver,
    parsed_program,
    include_instructions,
    geometry_tolerance,
    sinumerik_840d_sl,
    turning_correction_enabled,
):
    lathe_gcode_system = validate_system(lathe_gcode_system)
    program: Program | None = None
    unsupported: tuple[Diagnostic, ...] = ()
    execution_diagnostics: list[Diagnostic] = []
    turn_offsets = _turn_wcs_offsets(wcs_offsets)
    turn_offsets.update(_turn_extended_wcs_offsets(extended_wcs_offsets))
    if source_dialect == "sinumerik":
        return replace(
            execute_sinumerik_turning(
                source,
                parsed_program=parsed_program,
                tools=tools,
                tool_resolver=tool_resolver,
                home=(home_x, home_z),
                wcs_offsets=turn_offsets,
                default_unit_scale=default_unit_scale,
                x_is_diameter=x_is_diameter,
                iso_system=lathe_gcode_system,
                skip_optional_blocks=skip_optional_blocks,
                emulate_home=emulate_g28_home,
                include_instructions=include_instructions,
                tolerance=geometry_tolerance,
                solution_line=sinumerik_840d_sl,
                correction_enabled=turning_correction_enabled,
            ),
            wcs_offsets=_result_wcs_offsets(turn_offsets),
            extended_wcs_offsets=_result_extended_wcs_offsets(turn_offsets),
        )
    try:
        program = parsed_program if parsed_program is not None else parse_program(source)
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
            tools=tools if turning_correction_enabled else {},
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
