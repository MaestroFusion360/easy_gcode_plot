"""One CLI export contract for a file and for directory orchestration."""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter

from app.gcode.batch import _turning_unmodeled_m_diagnostics
from app.gcode.kernel import Diagnostic, ExecutionResult
from app.gcode.kernel.api.engine import _autodetect_arc_type
from app.gcode.kernel.frontend.io import read_nc_text
from app.gcode.program_execution import execute_program
from app.gcode.source_mode import SOURCE_DIALECT_SINUMERIK, source_dialect_for_path

from .dispatch import export_program
from .options import EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE, TURN_FULL_PROGRAM_MODE, ExportOptions
from .resolved import MILLING_TARGETS, convert_resolved_program
from .sinumerik import (
    convert_full_program_to_fanuc,
    convert_full_program_to_sinumerik,
)
from .source_formatting import is_native_full_program
from .turn import export_cycle_groups
from .units import MM_PER_INCH
from .validation import (
    sinumerik_iso_export_diagnostic,
    validate_full_program_dialect_conversion,
)

ARC_MODES = {"ijk-relative": 0, "ijk-absolute": 1, "radius": 2, "linearized": 3}


def _dxf_backend():
    try:
        from .dxf import export_dxf  # pylint: disable=import-outside-toplevel
    except ImportError as error:
        raise ValueError(f"DXF export backend is unavailable: {error}") from error
    return export_dxf


@dataclass(frozen=True)
class ExportRequest:
    language: str
    target_dialect: str | None = None
    lathe_gcode_system: str = "A"
    kinematics: str | None = None
    encoding: str = "utf-8"
    format: str = "nc"
    mode: str = "expanded"
    units: str = "auto"
    arc_type: str = "auto"
    coordinates: str = "absolute"
    force_addresses: bool = False
    sequence_numbers: bool = False
    sequence_start: int = 1
    sequence_increment: int = 1
    sequence_spacing: bool = False
    spaces: bool = True
    leading_zero: bool = False
    comments: bool = True
    safety_line: bool = False


@dataclass(frozen=True)
class ExportResult:
    execution: ExecutionResult
    output_size_bytes: int
    effective_units: str | None
    effective_arc_type: str | None
    elapsed_ms: float


def validate_export_request(request: ExportRequest, *, explicit: frozenset[str] = frozenset()) -> None:
    """Reject option combinations whose meaning exporters cannot guarantee."""
    if request.sequence_start < 0 or request.sequence_increment <= 0:
        raise ValueError("Sequence start must be nonnegative and increment must be positive")
    if not request.sequence_numbers and explicit & {"sequence_start", "sequence_increment", "sequence_spacing"}:
        raise ValueError("Sequence start, increment and spacing require --sequence-numbers")
    _validate_export_mode(request, explicit)


def _validate_export_mode(request: ExportRequest, explicit: frozenset[str]) -> None:
    _validate_target_dialect(request, explicit)
    if request.format == "dxf":
        _validate_dxf_options(explicit)
        return
    if request.mode == "full":
        _validate_full_export_options(request, explicit)
    elif request.mode == "cycles":
        _validate_cycle_export_options(request, explicit)


def _validate_target_dialect(request: ExportRequest, explicit: frozenset[str]) -> None:
    request = _canonical_full_target(request)
    if request.mode == "resolved" or request.target_dialect in MILLING_TARGETS:
        _validate_resolved_target(request)
        return
    if request.target_dialect is None:
        return
    if request.target_dialect != "sinumerik840d":
        raise ValueError("Unsupported target dialect; use sinumerik840d")
    if request.language != "fanuc_mill":
        raise ValueError("SINUMERIK 840D output requires --lang fanuc_mill")
    if request.format != "nc" or request.mode != "full":
        raise ValueError("SINUMERIK 840D dialect conversion requires NC format and --mode full")
    if request.coordinates != "absolute":
        raise ValueError("SINUMERIK 840D output uses absolute coordinates")
    unavailable = explicit & {"arc_type", "coordinates", "force_addresses", "safety_line"}
    if unavailable:
        raise ValueError("SINUMERIK 840D output does not accept: " + ", ".join(sorted(unavailable)))


def _canonical_full_target(request):
    if request.mode == "full" and request.target_dialect in ("fanuc_mill", "sinumerik_iso"):
        if request.language != "fanuc_mill" or request.format != "nc":
            raise ValueError("Full Program milling targets require --lang fanuc_mill and NC format")
        return replace(request, target_dialect="sinumerik840d" if request.target_dialect == "sinumerik_iso" else None)
    return request


def _validate_resolved_target(request):
    if request.mode == "full" and request.target_dialect == "sinumerik_native":
        if request.language != "fanuc_mill" or request.format != "nc" or request.coordinates != "absolute":
            raise ValueError("Native Full Program formatting requires milling NC and source coordinates")
        return
    if request.language != "fanuc_mill" or request.format != "nc" or request.mode not in ("expanded", "resolved"):
        raise ValueError("Resolved milling targets require NC and --mode resolved (or expanded)")
    if request.target_dialect not in (None, *MILLING_TARGETS) or request.coordinates != "absolute":
        raise ValueError("Resolved conversion requires a supported milling target and absolute coordinates")


def _validate_full_export_options(request: ExportRequest, explicit: frozenset[str]) -> None:
    if request.units != "auto":
        raise ValueError("Full Program export only supports --units auto")
    _reject_explicit_export_options(explicit, "Full Program")


def _validate_cycle_export_options(request: ExportRequest, explicit: frozenset[str]) -> None:
    if request.language != "fanuc_turn":
        raise ValueError("Cycle export is only available for fanuc_turn")
    if request.units != "auto":
        raise ValueError("Cycle export only supports --units auto")
    _reject_explicit_export_options(explicit, "Cycle export")


def _reject_explicit_export_options(explicit: frozenset[str], mode_name: str) -> None:
    unavailable = explicit & {"arc_type", "coordinates", "force_addresses", "safety_line"}
    if unavailable:
        raise ValueError(f"{mode_name} export does not accept: " + ", ".join(sorted(unavailable)))


def _validate_dxf_options(explicit: frozenset[str]) -> None:
    nc_only = explicit & {
        "mode",
        "arc_type",
        "coordinates",
        "force_addresses",
        "sequence_numbers",
        "sequence_start",
        "sequence_increment",
        "sequence_spacing",
        "spaces",
        "leading_zero",
        "comments",
        "safety_line",
    }
    if nc_only:
        raise ValueError("DXF export does not accept NC-only options: " + ", ".join(sorted(nc_only)))


def _options(request: ExportRequest, arc_type: str | None) -> ExportOptions:
    unit_scale = MM_PER_INCH if request.units == "inch" else 1.0
    return ExportOptions(
        arc_mode=ARC_MODES.get(arc_type or "ijk-relative", 0),
        incremental=request.coordinates == "incremental",
        force_addresses=request.force_addresses,
        sequence_numbers=request.sequence_numbers,
        sequence_start=request.sequence_start,
        sequence_increment=request.sequence_increment,
        sequence_spacing=request.sequence_spacing,
        delimiter=request.spaces,
        leading_zero=request.leading_zero,
        safety_line=request.safety_line,
        include_comments=request.comments,
        output_unit_scale=unit_scale,
        output_unit_code={"auto": "G21", "mm": "G21", "inch": "G20"}[request.units],
        linearization_tolerance=0.0005 / unit_scale,
        synthesize_program_number=False,
    )


def _arc_type(result: ExecutionResult, request: ExportRequest) -> str | None:
    if request.mode == "resolved" or request.target_dialect in MILLING_TARGETS and request.mode == "expanded":
        if request.arc_type == "linearized":
            return "linearized"
        if request.target_dialect == "sinumerik_native":
            return "ijk-absolute"
        return "radius" if request.arc_type == "radius" else "ijk-relative"
    if request.format != "nc" or request.mode != "expanded":
        return None
    if request.arc_type != "auto":
        return request.arc_type
    detected = _autodetect_arc_type(result.motions, tolerance=0.001, fallback=1)
    return "ijk-absolute" if detected == 2 else "ijk-relative"


def _check_unit_conversion(result: ExecutionResult, request: ExportRequest) -> None:
    if request.units == "auto" or request.format != "nc":
        return
    # The expanded exporter preserves these non-motion source operands. Their
    # physical dimensions are not uniformly represented by TraceMotion.
    for step in result.execution_steps:
        gcodes = {int(value) for letter, value in step.words if letter == "G" and value.is_integer()}
        unsupported = gcodes & {4, 10, 28, 30, 50, 51, 52, 53, 68, 69, 92, 96}
        if unsupported:
            codes = ", ".join(f"G{code}" for code in sorted(unsupported))
            raise ValueError(f"Unit conversion cannot safely preserve source operands for {codes}")


def _atomic_export(path: Path, write) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        write(temporary)
        size = temporary.stat().st_size
        temporary.replace(path)
        return size
    finally:
        temporary.unlink(missing_ok=True)


def _source_preserving_nc_formatting_requested(request: ExportRequest) -> bool:
    return request.sequence_numbers or not request.comments or not request.spaces or request.leading_zero


def _has_unrepresentable_indexed_arcs(result: ExecutionResult) -> bool:
    standard_normals = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}
    return any(
        motion.arc is not None
        and motion.arc.normal is not None
        and any(
            abs(actual - expected) > 1e-9 for actual, expected in zip(motion.arc.normal, standard_normals[motion.plane])
        )
        for motion in result.motions
    )


def _dxf_has_unrepresentable_indexed_arcs(result: ExecutionResult, request: ExportRequest) -> bool:
    return request.format == "dxf" and bool(result.kinematics_profile) and _has_unrepresentable_indexed_arcs(result)


def _failed_export(result: ExecutionResult, code: str, message: str, started: float) -> ExportResult:
    failed = replace(
        result,
        ok=False,
        complete=False,
        diagnostics=result.diagnostics + (Diagnostic(code, message, "error", "unsupported"),),
    )
    return ExportResult(failed, 0, None, None, round((perf_counter() - started) * 1000, 3))


def _preflight_export_failure(result: ExecutionResult, request: ExportRequest, started: float):
    if request.target_dialect in ("sinumerik840d", "sinumerik_iso") and request.mode == "full":
        diagnostic = sinumerik_iso_export_diagnostic(result)
        if diagnostic is not None:
            return _failed_export(result, diagnostic.code, diagnostic.message, started)
    if not result.ok or not result.complete:
        return ExportResult(result, 0, None, None, round((perf_counter() - started) * 1000, 3))

    diagnostic = None
    target_compensation_diagnostics = {
        "UNVERIFIED_CUTTER_COMPENSATION",
        "UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION",
    }
    checks = (
        (
            request.target_dialect in ("sinumerik840d", "sinumerik_iso")
            and request.mode == "full"
            and any(item.code in target_compensation_diagnostics for item in result.diagnostics),
            "UNVERIFIED_TARGET_CUTTER_COMPENSATION",
            "SINUMERIK conversion requires cutter compensation to be resolved by the kernel",
        ),
        (
            request.format == "nc"
            and request.mode != "full"
            and any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events),
            "UNSUPPORTED_TWP_EXPANDED_EXPORT",
            "Generated NC cannot preserve G68.2 tilted working-plane commands",
        ),
        (
            request.format == "nc"
            and request.mode == "expanded"
            and any(event.kind == "TCP_CONTROL_ON" for event in result.events),
            "UNSUPPORTED_TCP_EXPANDED_EXPORT",
            "Expanded NC cannot preserve G43.4 TCP rotary commands",
        ),
        (
            request.format == "nc"
            and request.mode == "expanded"
            and result.kinematics_profile
            and any(event.kind == "ROTARY_INDEX" for event in result.events),
            "UNSUPPORTED_INDEXED_MULTIAXIS_EXPORT",
            "Expanded NC cannot preserve indexed rotary commands",
        ),
        (
            request.format == "nc"
            and request.mode == "full"
            and any(event.kind == "TCP_CONTROL_ON" for event in result.events)
            and not is_native_full_program(result)
            and _source_preserving_nc_formatting_requested(request),
            "UNSUPPORTED_TCP_FULL_EXPORT_OPTIONS",
            "G43.4 TCP NC is preserved verbatim; formatting options cannot be applied safely",
        ),
        (
            request.format == "nc"
            and request.mode == "full"
            and result.kinematics_profile
            and any(event.kind == "ROTARY_INDEX" for event in result.events)
            and not is_native_full_program(result)
            and _source_preserving_nc_formatting_requested(request),
            "UNSUPPORTED_INDEXED_MULTIAXIS_EXPORT_OPTIONS",
            "Indexed NC is preserved verbatim; formatting options cannot be applied safely",
        ),
        (
            _dxf_has_unrepresentable_indexed_arcs(result, request),
            "UNSUPPORTED_INDEXED_MULTIAXIS_EXPORT",
            "DXF cannot represent tilted indexed arcs safely",
        ),
    )
    for applies, code, message in checks:
        if applies and diagnostic is None:
            diagnostic = Diagnostic(code, message, "error", "unsupported")
    return _failed_export(result, diagnostic.code, diagnostic.message, started) if diagnostic else None


def _nc_output(source: str, result: ExecutionResult, request: ExportRequest, options: ExportOptions) -> str:
    if request.target_dialect == "sinumerik_native" and not is_native_full_program(result):
        raise ValueError("Native Full Program formatting requires a SINUMERIK native source")
    mode = (
        EXPANDED_EXECUTION_MODE
        if request.mode == "expanded"
        else TURN_FULL_PROGRAM_MODE
        if request.language == "fanuc_turn"
        else MILL_FULL_PROGRAM_MODE
    )
    preserve_source = (
        request.mode == "full"
        and not is_native_full_program(result)
        and (
            any(e.kind in {"TILTED_WORK_PLANE_ON", "TCP_CONTROL_ON"} for e in result.events)
            or result.kinematics_profile
            and any(e.kind == "ROTARY_INDEX" for e in result.events)
        )
    )
    if preserve_source:
        return source
    if request.mode == "cycles":
        return export_cycle_groups(result, options)
    return export_program(
        result,
        source,
        mode=mode,
        lathe_mode=request.language == "fanuc_turn",
        options=options,
        export_arc_mode=options.arc_mode,
    )


def _full_fanuc_conversion_requested(request, result):
    return (
        request.mode == "full"
        and result.source_dialect == SOURCE_DIALECT_SINUMERIK
        and request.target_dialect != "sinumerik_native"
    )


def export_file(source_path: Path, output_path: Path, request: ExportRequest) -> ExportResult:
    """Execute once and export through the existing NC or DXF exporter."""
    validate_export_request(request)
    started = perf_counter()
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("Output must differ from the source file")
    source = read_nc_text(source_path, encoding=request.encoding)
    source_dialect = source_dialect_for_path(source_path, source)
    result, _tools, _inferred = execute_program(
        source,
        language=request.language,
        lathe_gcode_system=request.lathe_gcode_system,
        autodetect_arc_type=True,
        kinematics=request.kinematics,
        source_dialect=source_dialect,
    )
    if request.language == "fanuc_turn":
        result = replace(result, diagnostics=result.diagnostics + _turning_unmodeled_m_diagnostics(result))
    failure = _preflight_export_failure(result, request, started)
    if failure is not None:
        return failure
    if request.target_dialect not in ("sinumerik840d", *MILLING_TARGETS) and request.mode != "resolved":
        _check_unit_conversion(result, request)
    arc_type = _arc_type(result, request)
    if request.format == "dxf":
        export_dxf = _dxf_backend()
        size = _atomic_export(
            output_path,
            lambda temp: export_dxf(
                result, temp, output_units=request.units if request.units != "auto" else "mm", deterministic=True
            ),
        )
    else:
        options = _options(request, arc_type)
        if request.mode == "resolved" or request.target_dialect in MILLING_TARGETS and request.mode == "expanded":
            text = convert_resolved_program(result, request.target_dialect or "fanuc_mill", options)
        elif request.target_dialect in ("sinumerik840d", "sinumerik_iso"):
            text = convert_full_program_to_sinumerik(
                source,
                source_result=result,
                execution_options={"kinematics": request.kinematics},
            )
        else:
            if _full_fanuc_conversion_requested(request, result):
                text = convert_full_program_to_fanuc(
                    source,
                    source_result=result,
                    execution_options={"kinematics": request.kinematics},
                    export_options=options,
                )
                validate_full_program_dialect_conversion(
                    result,
                    text,
                    request.language,
                    source_dialect="fanuc",
                    execution_options={"kinematics": request.kinematics},
                )
            else:
                text = _nc_output(source, result, request, options)
        size = _atomic_export(output_path, lambda temp: temp.write_bytes(text.encode("utf-8")))
    return ExportResult(
        result, size, "inch" if request.units == "inch" else "mm", arc_type, round((perf_counter() - started) * 1000, 3)
    )


def request_document(request: ExportRequest) -> dict[str, object]:
    return asdict(request)
