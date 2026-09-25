"""One CLI export contract for a file and for directory orchestration."""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter

from app.gcode.batch import _turning_unmodeled_m_diagnostics
from app.gcode.kernel import ExecutionResult
from app.gcode.kernel.api.engine import _autodetect_milling_arc_type
from app.gcode.kernel.io import read_nc_text
from app.gcode.program_execution import execute_program

from .dispatch import export_program
from .dxf import export_dxf
from .options import EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE, TURN_FULL_PROGRAM_MODE, ExportOptions
from .turn import export_cycle_groups
from .units import MM_PER_INCH

ARC_MODES = {"ijk-relative": 0, "ijk-absolute": 1, "radius": 2, "linearized": 3}


@dataclass(frozen=True)
class ExportRequest:
    language: str
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
    if request.format == "dxf":
        _validate_dxf_options(explicit)
        return
    if request.mode == "full":
        if request.units != "auto":
            raise ValueError("Full Program export only supports --units auto")
        unavailable = explicit & {"arc_type", "coordinates", "force_addresses", "safety_line"}
        if unavailable:
            raise ValueError("Full Program export does not accept: " + ", ".join(sorted(unavailable)))
    if request.mode == "cycles":
        if request.language != "fanuc_turn":
            raise ValueError("Cycle export is only available for fanuc_turn")
        if request.units != "auto":
            raise ValueError("Cycle export only supports --units auto")
        unavailable = explicit & {"arc_type", "coordinates", "force_addresses", "safety_line"}
        if unavailable:
            raise ValueError("Cycle export does not accept: " + ", ".join(sorted(unavailable)))
    if request.language == "fanuc_turn" and "arc_type" in explicit:
        raise ValueError("Explicit --arc-type is only available for fanuc_mill expanded NC export")


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
    if request.language != "fanuc_mill" or request.format != "nc" or request.mode != "expanded":
        return None
    if request.arc_type != "auto":
        return request.arc_type
    detected = _autodetect_milling_arc_type(result.motions, tolerance=0.001, fallback=1)
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


def export_file(source_path: Path, output_path: Path, request: ExportRequest) -> ExportResult:
    """Execute once and export through the existing NC or DXF exporter."""
    started = perf_counter()
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("Output must differ from the source file")
    source = read_nc_text(source_path, encoding=request.encoding)
    result, _tools, _inferred = execute_program(
        source,
        language=request.language,
        autodetect_arc_type=request.language == "fanuc_mill",
    )
    if request.language == "fanuc_turn":
        result = replace(result, diagnostics=result.diagnostics + _turning_unmodeled_m_diagnostics(result))
    if not result.ok or not result.complete:
        return ExportResult(result, 0, None, None, round((perf_counter() - started) * 1000, 3))
    _check_unit_conversion(result, request)
    arc_type = _arc_type(result, request)
    if request.format == "dxf":
        size = _atomic_export(
            output_path,
            lambda temp: export_dxf(
                result, temp, output_units=request.units if request.units != "auto" else "mm", deterministic=True
            ),
        )
    else:
        mode = (
            EXPANDED_EXECUTION_MODE
            if request.mode == "expanded"
            else TURN_FULL_PROGRAM_MODE
            if request.language == "fanuc_turn"
            else MILL_FULL_PROGRAM_MODE
        )
        options = _options(request, arc_type)
        text = (
            export_cycle_groups(result, options)
            if request.mode == "cycles"
            else export_program(
                result,
                source,
                mode=mode,
                lathe_mode=request.language == "fanuc_turn",
                options=options,
                export_arc_mode=options.arc_mode,
            )
        )
        size = _atomic_export(output_path, lambda temp: temp.write_bytes(text.encode("utf-8")))
    return ExportResult(
        result, size, "inch" if request.units == "inch" else "mm", arc_type, round((perf_counter() - started) * 1000, 3)
    )


def request_document(request: ExportRequest) -> dict[str, object]:
    return asdict(request)
