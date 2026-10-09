"""One CLI export contract for a file and for directory orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter

from app.gcode.file_io import atomic_export as _atomic_export
from app.gcode.file_io import protect_source
from app.gcode.kernel import Diagnostic, ExecutionResult
from app.gcode.kernel.frontend.io import read_nc_text
from app.gcode.program_execution import execute_program
from app.gcode.source_mode import source_dialect_for_path

from .comments import DEFAULT_COMMENT_STYLE, normalize_comment_style
from .export.common import (
    MM_PER_INCH,
    ExportLimitation,
    ExportOptions,
)
from .export.expanded import convert_resolved_program
from .export.full import is_native_full_program, normalize_full_program
from .post_profiles import load_post_profile

ARC_MODES = {"ijk-relative": 0, "ijk-absolute": 1, "radius": 2, "linearized": 3}


def _dxf_backend():
    try:
        from .export.dxf import export_dxf  # pylint: disable=import-outside-toplevel
    except ImportError as error:
        raise ValueError(f"DXF export backend is unavailable: {error}") from error
    return export_dxf


@dataclass(frozen=True)
class ExportRequest:
    language: str
    target_dialect: str | None = None
    lathe_gcode_system: str = "A"
    sinumerik_840d_sl: bool = True
    kinematics: str | None = None
    encoding: str = "utf-8"
    format: str = "nc"
    mode: str = "expanded"
    units: str = "auto"
    arc_type: str = "auto"
    coordinates: str = "absolute"
    sequence_numbers: bool = False
    sequence_start: int = 1
    sequence_increment: int = 1
    sequence_spacing: bool = False
    spaces: bool = True
    leading_zero: bool = False
    comments: bool = True
    comment_style: str = DEFAULT_COMMENT_STYLE
    safety_line: bool = False
    start_program: str = ""
    end_program: str = ""
    modal_feed: bool = True
    decimal_places: int = 6
    decimal_places_explicit: bool = False
    force_decimal: bool = False
    force_decimal_explicit: bool = False
    plus_output: bool = False
    plus_output_explicit: bool = False
    tool_numbers: dict[str, int] | None = None


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
    if request.mode not in ("full", "expanded"):
        raise ValueError("NC export mode must be full or expanded")
    _validate_export_mode(request, explicit)


def _validate_export_mode(request: ExportRequest, explicit: frozenset[str]) -> None:
    _validate_target_dialect(request, explicit)
    if request.format == "dxf":
        _validate_dxf_options(explicit)
        return
    if request.mode == "full":
        _validate_full_export_options(request, explicit)


def _validate_target_dialect(request, explicit):
    if request.target_dialect is None:
        return
    if request.mode != "expanded" or request.format != "nc":
        raise ValueError("Target post profiles require NC format and --mode expanded")
    profile = load_post_profile(request.target_dialect)
    lathe = profile["machine"] == "lathe"
    if lathe != (request.language == "fanuc_turn"):
        raise ValueError("Target post profile must match the source machine")


def _validate_full_export_options(request: ExportRequest, explicit: frozenset[str]) -> None:
    if request.units != "auto":
        raise ValueError("Full Program export only supports --units auto")
    _reject_explicit_export_options(explicit, "Full Program")


def _reject_explicit_export_options(explicit: frozenset[str], mode_name: str) -> None:
    unavailable = explicit & {"arc_type", "coordinates", "modal_feed"}
    if unavailable:
        raise ValueError(f"{mode_name} export does not accept: " + ", ".join(sorted(unavailable)))


def _validate_dxf_options(explicit: frozenset[str]) -> None:
    nc_only = explicit & {
        "mode",
        "arc_type",
        "coordinates",
        "sequence_numbers",
        "sequence_start",
        "sequence_increment",
        "sequence_spacing",
        "spaces",
        "leading_zero",
        "comments",
        "safety_line",
        "modal_feed",
    }
    if nc_only:
        raise ValueError("DXF export does not accept NC-only options: " + ", ".join(sorted(nc_only)))


def _options(request: ExportRequest, arc_type: str | None, *, units_explicit: bool = False) -> ExportOptions:
    unit_scale = MM_PER_INCH if request.units == "inch" else 1.0
    return ExportOptions(
        arc_mode=ARC_MODES.get(arc_type or "ijk-relative", 0),
        incremental=request.coordinates == "incremental",
        sequence_numbers=request.sequence_numbers,
        sequence_start=request.sequence_start,
        sequence_increment=request.sequence_increment,
        sequence_spacing=request.sequence_spacing,
        delimiter=request.spaces,
        leading_zero=request.leading_zero,
        start_program=request.start_program,
        end_program=request.end_program,
        safety_line=request.safety_line,
        comment_style=normalize_comment_style(request.comment_style),
        include_comments=request.comments,
        output_unit_scale=unit_scale,
        output_unit_scale_explicit=units_explicit,
        modal_feed=request.modal_feed,
        decimal_places=request.decimal_places,
        decimal_places_explicit=request.decimal_places_explicit,
        force_decimal=request.force_decimal,
        force_decimal_explicit=request.force_decimal_explicit,
        plus_output=request.plus_output,
        plus_output_explicit=request.plus_output_explicit,
        tool_numbers=request.tool_numbers,
        linearization_tolerance=0.0005 / unit_scale,
    )


def _arc_type(result, request):
    if request.format != "nc" or request.mode != "expanded":
        return None
    if request.arc_type != "auto":
        return request.arc_type
    arc = load_post_profile(_target_post(result, request))["format"]
    return (
        "linearized"
        if not arc["outputArcs"]
        else "radius"
        if arc["arcMode"] == "R"
        else "ijk-absolute"
        if arc["arcCenter"] == "absolute"
        else "ijk-relative"
    )


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


def _failed_export(
    result: ExecutionResult, code: str, message: str, started: float, *, source_block: int | None = None
) -> ExportResult:
    block = (
        result.program.blocks[source_block]
        if result.program is not None and source_block is not None and 0 <= source_block < len(result.program.blocks)
        else None
    )
    diagnostic = Diagnostic(
        code,
        message,
        "error",
        "unsupported",
        line=block.index + 1 if block is not None else None,
        raw=block.raw.rstrip("\r\n") if block is not None else None,
    )
    failed = replace(
        result,
        ok=False,
        complete=False,
        diagnostics=result.diagnostics + (diagnostic,),
    )
    return ExportResult(failed, 0, None, None, round((perf_counter() - started) * 1000, 3))


def _preflight_export_failure(result, request, started):
    if not result.ok or not result.complete:
        return ExportResult(result, 0, None, None, round((perf_counter() - started) * 1000, 3))
    if request.format == "nc" and request.mode == "expanded":
        profile = load_post_profile(_target_post(result, request))
        supports_tcp = bool((profile.get("supports") or {}).get("tcp"))
        unsupported = {
            "TILTED_WORK_PLANE_ON": (
                "UNSUPPORTED_TWP_EXPANDED_EXPORT",
                "Expanded multiaxis export does not yet reconstruct G68.2/CYCLE800 tilted working-plane semantics",
            ),
        }
        if supports_tcp and result.kinematics_profile in {
            "5ax_table_ac",
            "5ax_table_bc",
            "5ax_table_ac_angled",
            "5ax_table_bc_angled",
        }:
            unsupported.pop("TILTED_WORK_PLANE_ON")
        if not supports_tcp:
            unsupported["TCP_CONTROL_ON"] = (
                "UNSUPPORTED_TCP_EXPANDED_EXPORT",
                "Selected post cannot preserve G43.4 TCP rotary commands / TRAORI or reconstruct resolved TCP motion",
            )
        for event in result.events:
            if event.kind in unsupported:
                code, message = unsupported[event.kind]
                return _failed_export(result, code, message, started, source_block=event.source_block)
    if _dxf_has_unrepresentable_indexed_arcs(result, request):
        return _failed_export(
            result, "UNSUPPORTED_INDEXED_MULTIAXIS_EXPORT", "DXF cannot represent tilted indexed arcs safely", started
        )
    return None


def _nc_output(source, result, request, options, *, cancelled=None):
    if request.mode == "full":
        return normalize_full_program(result, source, options, cancelled=cancelled)
    return convert_resolved_program(
        result, _target_post(result, request), options, cancelled=cancelled, sinumerik_840d_sl=request.sinumerik_840d_sl
    )


def _target_post(result, request):
    return request.target_dialect or (
        "fanuc_lathe_" + request.lathe_gcode_system.lower()
        if request.language == "fanuc_turn"
        else "sinumerik_840d"
        if is_native_full_program(result)
        else "sinumerik_iso"
        if result.source_dialect == "sinumerik"
        else "fanuc_mill"
    )


def export_file(source_path: Path, output_path: Path, request: ExportRequest) -> ExportResult:
    """Execute once and export through the shared NC/DXF writer."""
    validate_export_request(request)
    started = perf_counter()
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    protect_source(output_path, source_path)
    source = read_nc_text(source_path, encoding=request.encoding)
    source_dialect = source_dialect_for_path(source_path, source)
    result, _tools, _inferred = execute_program(
        source,
        language=request.language,
        lathe_gcode_system=request.lathe_gcode_system,
        sinumerik_840d_sl=request.sinumerik_840d_sl,
        autodetect_arc_type=True,
        kinematics=request.kinematics,
        source_dialect=source_dialect,
    )
    return write_export(result, source, output_path, request, started=started)


def write_export(
    result: ExecutionResult,
    source: str,
    output_path: str | Path,
    request: ExportRequest,
    *,
    render_points=None,
    cancelled=None,
    started: float | None = None,
) -> ExportResult:
    """Serialize one resolved execution through the single export contract.

    This is the shared implementation used by the GUI, the single-file CLI and
    batch export. The caller supplies an already-executed ``result`` and the
    matching ``source`` text; no second interpreter runs here.
    """
    validate_export_request(request)
    started = perf_counter() if started is None else started
    output_path = Path(output_path).resolve()
    failure = _preflight_export_failure(result, request, started)
    if failure is not None:
        return failure
    arc_type = _arc_type(result, request)
    units_explicit = request.units != "auto"
    if request.mode == "expanded" and request.format == "nc" and request.units == "auto":
        request = replace(request, units=load_post_profile(_target_post(result, request))["options"]["units"])
    if request.format == "dxf":
        export_dxf = _dxf_backend()
        size = _atomic_export(
            output_path,
            lambda temp: export_dxf(
                result,
                temp,
                turning=result.language == "fanuc_turn",
                render_points=render_points,
                output_units=request.units if request.units != "auto" else "mm",
                deterministic=True,
                cancelled=cancelled,
            ),
            cancelled=cancelled,
        )
    else:
        options = _options(request, arc_type, units_explicit=units_explicit)
        try:
            text = _nc_output(source, result, request, options, cancelled=cancelled)
        except ExportLimitation as exc:
            return _failed_export(result, getattr(exc, "code", "UNSUPPORTED_EXPANDED_EXPORT"), str(exc), started)
        size = _atomic_export(output_path, lambda temp: temp.write_bytes(text.encode("utf-8")), cancelled=cancelled)
    effective_units = "inch" if request.units == "inch" else "mm"
    if request.format == "nc" and request.mode == "full" and result.execution_steps:
        effective_units = "inch" if result.execution_steps[-1].unit_scale == MM_PER_INCH else "mm"
    return ExportResult(result, size, effective_units, arc_type, round((perf_counter() - started) * 1000, 3))


def request_document(request: ExportRequest) -> dict[str, object]:
    return asdict(request)
