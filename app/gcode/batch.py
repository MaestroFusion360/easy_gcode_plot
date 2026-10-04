"""Batch validation reports over the authoritative CNC execution kernel."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from app.gcode.kernel import Diagnostic, ExecutionResult
from app.gcode.kernel.frontend.io import read_nc_text
from app.gcode.kinematics_report import kinematics_report_fields
from app.gcode.program_execution import execute_program
from app.gcode.source_mode import language_for_path, source_dialect_for_path
from app.gcode.statistics_report import export_execution_statistics

BATCH_REPORT_SCHEMA_VERSION = 2
DEFAULT_BATCH_EXTENSIONS = (".nc", ".cnc", ".ptp", ".mpf", ".spf", ".tap", ".txt")
_NC_HEADER_RE = re.compile(rb"(?m)^\s*O\d{1,5}(?:\b|\s*\()", re.IGNORECASE)
_NC_BLOCK_RE = re.compile(rb"(?m)^\s*(?:N\d+\s*)?[GMT]\d+(?:\.\d+)?\b", re.IGNORECASE)
STATUS_CLEAN = "CLEAN"
STATUS_WARNINGS = "WARNINGS"
STATUS_ERRORS = "ERRORS"
STATUS_NO_FILES = "NO_FILES"
_UNSUPPORTED_CODE_RE = re.compile(r"\b([GM]\d+(?:\.\d+)?)\b", re.IGNORECASE)


def _normalize_extensions(extensions: Iterable[str]) -> tuple[str, ...]:
    normalized = []
    for extension in extensions:
        value = extension.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("At least one NC file extension is required")
    return tuple(normalized)


def discover_nc_files(
    root: str | Path,
    *,
    recursive: bool = True,
    extensions: Iterable[str] = DEFAULT_BATCH_EXTENSIONS,
) -> tuple[Path, ...]:
    """Return a deterministic list of NC files below *root*."""
    directory = Path(root)
    if not directory.exists():
        raise FileNotFoundError(f"Batch input directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Batch input path is not a directory: {directory}")

    normalized = _normalize_extensions(extensions)
    allowed = frozenset(normalized)
    detect_nonstandard_names = allowed == frozenset(DEFAULT_BATCH_EXTENSIONS)
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    files = [
        path
        for path in candidates
        if path.is_file()
        and (path.suffix.lower() in allowed or (detect_nonstandard_names and _looks_like_nc_program(path)))
    ]
    return tuple(
        sorted(
            files,
            key=lambda path: (
                path.relative_to(directory).as_posix().casefold(),
                path.relative_to(directory).as_posix(),
            ),
        )
    )


def _looks_like_nc_program(path: Path) -> bool:
    """Recognize FANUC programs whose names use part numbers instead of NC extensions."""
    try:
        with path.open("rb") as stream:
            prefix = stream.read(8192)
    except OSError:
        return False
    if b"\0" in prefix or not prefix:
        return False
    return bool(_NC_HEADER_RE.search(prefix) or len(_NC_BLOCK_RE.findall(prefix)) >= 2)


def _unsupported_codes(diagnostics: Iterable[Diagnostic], diagnostic_code: str) -> tuple[str, ...]:
    codes: set[str] = set()
    for diagnostic in diagnostics:
        codes.update(_diagnostic_cnc_codes(asdict(diagnostic), diagnostic_code))
    return tuple(sorted(codes, key=_code_sort_key))


def _diagnostic_cnc_codes(diagnostic, expected_code):
    """Use structured SINUMERIK codes; retain legacy FANUC aggregation."""
    if diagnostic["code"] == expected_code:
        return tuple(code.upper() for code in _UNSUPPORTED_CODE_RE.findall(diagnostic["message"]))
    if not diagnostic["code"].startswith("UNSUPPORTED_SINUMERIK_"):
        return ()
    letter = "G" if expected_code == "UNSUPPORTED_G_CODE" else "M"
    return tuple(code for code in diagnostic.get("cnc_codes", ()) if code.startswith(letter))


def _code_sort_key(code: str) -> tuple[str, float, str]:
    try:
        return code[0], float(code[1:]), code
    except (IndexError, ValueError):
        return code[:1], float("inf"), code


def execute_analysis_program(
    source: str,
    *,
    language: str,
    include_instructions: bool = True,
    kinematics: str | None = None,
    lathe_gcode_system: str = "A",
    source_dialect: str = "fanuc",
) -> ExecutionResult:
    """Use the same execution options and diagnostics for single and batch analysis."""
    result, _tools, _inferred = execute_program(
        source,
        language=language,
        include_instructions=include_instructions,
        autodetect_arc_type=language == "fanuc_mill",
        kinematics=kinematics,
        lathe_gcode_system=lathe_gcode_system,
        source_dialect=source_dialect,
    )
    return result


def analysis_status(result: ExecutionResult) -> str:
    if not result.ok or not result.complete or any(item.severity == "error" for item in result.diagnostics):
        return STATUS_ERRORS
    return STATUS_WARNINGS if result.diagnostics else STATUS_CLEAN


def analyze_file(path, *, language=None, encoding="utf-8", source=None, **options):
    """Shared single-file analysis entry point used by CLI and directory batches."""
    if source is None:
        source = read_nc_text(path, encoding=encoding)
    result = execute_analysis_program(
        source,
        language=language_for_path(path, language),
        source_dialect=source_dialect_for_path(path, source),
        **options,
    )
    return source, result


def _export_file_statistics(result, path, root, html_dir, inches):
    """Keep directory structure and source suffixes; report export failures per file."""
    if html_dir is None:
        return result, None
    relative = path.relative_to(root)
    destination = Path(html_dir) / relative.with_name(relative.name + ".html")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        export_execution_statistics(result, destination, source_path=path, inches=inches)
    except (OSError, ValueError) as exc:
        diagnostic = Diagnostic(code="HTML_REPORT_WRITE_ERROR", message=str(exc), severity="error", status="malformed")
        return replace(result, ok=False, diagnostics=result.diagnostics + (diagnostic,)), None
    return result, str(destination.resolve())


def analysis_diagnostic_summary(result: ExecutionResult) -> dict[str, object]:
    diagnostics = result.diagnostics
    return {
        "source_dialect": result.source_dialect,
        "diagnostic_count": len(diagnostics),
        "error_count": sum(item.severity == "error" for item in diagnostics),
        "warning_count": sum(item.severity != "error" for item in diagnostics),
        "unsupported_g_codes": list(_unsupported_codes(diagnostics, "UNSUPPORTED_G_CODE")),
        "unsupported_m_codes": list(_unsupported_codes(diagnostics, "UNSUPPORTED_M_CODE")),
    }


def _file_report(
    path: Path,
    root: Path,
    *,
    language: str | None,
    encoding: str,
    kinematics: str | None = None,
    lathe_gcode_system: str = "A",
    html_dir: Path | None = None,
    inches: bool = False,
) -> dict[str, object]:
    started = perf_counter()
    try:
        source = read_nc_text(path, encoding=encoding)
        size_bytes = path.stat().st_size
    except (OSError, UnicodeError) as exc:
        diagnostic = Diagnostic(
            code="FILE_PROCESSING_ERROR",
            message=str(exc),
            severity="error",
            status="malformed",
        )
        return {
            "path": path.relative_to(root).as_posix(),
            "source_dialect": source_dialect_for_path(path),
            "status": STATUS_ERRORS,
            "ok": False,
            "complete": False,
            "size_bytes": None,
            "line_count": None,
            "motion_count": 0,
            "executed_block_count": 0,
            "diagnostic_count": 1,
            "error_count": 1,
            "warning_count": 0,
            "unsupported_g_codes": [],
            "unsupported_m_codes": [],
            "diagnostics": [asdict(diagnostic)],
            "kinematics_profile": kinematics,
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        }

    _source, result = analyze_file(
        path,
        source=source,
        language=language,
        include_instructions=False,
        kinematics=kinematics,
        lathe_gcode_system=lathe_gcode_system,
    )
    result, html_path = _export_file_statistics(result, path, root, html_dir, inches)
    diagnostics = result.diagnostics
    status = analysis_status(result)
    report = {
        "path": path.relative_to(root).as_posix(),
        "status": status,
        "ok": result.ok,
        "complete": result.complete,
        "size_bytes": size_bytes,
        "line_count": len(source.splitlines()),
        "motion_count": len(result.motions),
        "executed_block_count": len(result.executed_blocks),
        **analysis_diagnostic_summary(result),
        "diagnostics": [asdict(item) for item in diagnostics],
        "kinematics_profile": result.kinematics_profile,
        **kinematics_report_fields(result),
        "rotary_axes": list(result.rotary_axes),
    }
    report["elapsed_ms"] = round((perf_counter() - started) * 1000.0, 3)
    report["language"] = result.language
    if html_dir is not None:
        report["html_report"] = html_path
    return report


def _aggregate_unsupported(files: Iterable[dict[str, object]], key: str) -> list[dict[str, object]]:
    occurrences: Counter[str] = Counter()
    affected_files: defaultdict[str, set[str]] = defaultdict(set)
    for file_report in files:
        path = str(file_report["path"])
        for diagnostic in file_report["diagnostics"]:  # type: ignore[union-attr]
            expected_code = "UNSUPPORTED_G_CODE" if key == "unsupported_g_codes" else "UNSUPPORTED_M_CODE"
            for code in _diagnostic_cnc_codes(diagnostic, expected_code):
                normalized = code.upper()
                occurrences[normalized] += 1
                affected_files[normalized].add(path)
    return [
        {
            "code": code,
            "occurrences": occurrences[code],
            "files": len(affected_files[code]),
        }
        for code in sorted(occurrences, key=_code_sort_key)
    ]


def analyze_directory(
    root: str | Path,
    *,
    language: str | None = None,
    encoding: str = "utf-8",
    recursive: bool = True,
    extensions: Iterable[str] = DEFAULT_BATCH_EXTENSIONS,
    on_file: Callable[[dict[str, object]], None] | None = None,
    kinematics: str | None = None,
    kinematics_by_file: dict[str, str] | None = None,
    lathe_gcode_system: str = "A",
    html_dir: str | Path | None = None,
    inches: bool = False,
) -> dict[str, object]:
    """Execute every matching NC file and return a batch analysis report."""
    started = perf_counter()
    directory = Path(root).resolve()
    normalized_extensions = _normalize_extensions(extensions)
    paths = discover_nc_files(directory, recursive=recursive, extensions=normalized_extensions)
    profiles = kinematics_by_file or {}
    actual = {path.relative_to(directory).as_posix() for path in paths}
    unknown = set(profiles) - actual
    if unknown:
        raise ValueError(f"Kinematics map references an undiscovered file: {sorted(unknown)[0]}")
    files = []
    for path in paths:
        selected = profiles.get(path.relative_to(directory).as_posix(), kinematics)
        file_report = _file_report(
            path,
            directory,
            language=language,
            encoding=encoding,
            kinematics=selected,
            lathe_gcode_system=lathe_gcode_system,
            html_dir=Path(html_dir) if html_dir is not None else None,
            inches=inches,
        )
        files.append(file_report)
        if on_file is not None:
            on_file(file_report)

    status_counts = Counter(str(item["status"]) for item in files)
    diagnostic_codes: Counter[str] = Counter()
    for file_report in files:
        diagnostic_codes.update(str(item["code"]) for item in file_report["diagnostics"])  # type: ignore[union-attr]

    if not files:
        overall_status = STATUS_NO_FILES
    elif status_counts[STATUS_ERRORS]:
        overall_status = STATUS_ERRORS
    elif status_counts[STATUS_WARNINGS]:
        overall_status = STATUS_WARNINGS
    else:
        overall_status = STATUS_CLEAN

    elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
    return {
        "schema_version": BATCH_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "root": str(directory),
        "language": language or "auto",
        "encoding": encoding,
        "kinematics_profile": kinematics,
        "kinematics_by_file": profiles,
        "recursive": recursive,
        "extensions": list(normalized_extensions),
        "scan_warnings": ["No matching NC files found"] if not files else [],
        "summary": {
            "files_total": len(files),
            STATUS_CLEAN: status_counts[STATUS_CLEAN],
            STATUS_WARNINGS: status_counts[STATUS_WARNINGS],
            STATUS_ERRORS: status_counts[STATUS_ERRORS],
            "diagnostics_total": sum(int(item["diagnostic_count"]) for item in files),
            "errors_total": sum(int(item["error_count"]) for item in files),
            "warnings_total": sum(int(item["warning_count"]) for item in files),
            "elapsed_ms": elapsed_ms,
            "diagnostic_codes": dict(sorted(diagnostic_codes.items())),
            "unsupported_g_codes": _aggregate_unsupported(files, "unsupported_g_codes"),
            "unsupported_m_codes": _aggregate_unsupported(files, "unsupported_m_codes"),
        },
        "files": files,
    }


def _diagnostic_text(diagnostics: list[dict[str, object]]) -> str:
    parts = []
    for diagnostic in diagnostics:
        line = diagnostic.get("line")
        location = f" line {line}" if line is not None else ""
        parts.append(
            f"[{str(diagnostic.get('severity', '')).upper()}] "
            f"{diagnostic.get('code', '')}{location}: {diagnostic.get('message', '')}"
        )
    return " | ".join(parts)


def write_batch_reports(
    report: dict[str, object],
    output_dir: str | Path,
    *,
    basename: str = "batch_report",
) -> tuple[Path, Path]:
    """Write detailed JSON and spreadsheet-friendly CSV batch reports."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{basename}.json"
    csv_path = directory / f"{basename}.csv"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fieldnames = (
        "path",
        "status",
        "ok",
        "complete",
        "size_bytes",
        "line_count",
        "motion_count",
        "executed_block_count",
        "diagnostic_count",
        "error_count",
        "warning_count",
        "unsupported_g_codes",
        "unsupported_m_codes",
        "diagnostic_codes",
        "diagnostics",
        "kinematics_profile",
        "kinematics_fingerprint",
        "kinematics_definition",
        "elapsed_ms",
        "source_dialect",
        "language",
        "html_report",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for file_report in report["files"]:  # type: ignore[union-attr]
            diagnostics = file_report["diagnostics"]
            writer.writerow(
                {
                    **{name: file_report.get(name) for name in fieldnames},
                    "kinematics_definition": json.dumps(file_report.get("kinematics_definition"), sort_keys=True),
                    "unsupported_g_codes": ";".join(file_report["unsupported_g_codes"]),
                    "unsupported_m_codes": ";".join(file_report["unsupported_m_codes"]),
                    "diagnostic_codes": ";".join(str(item["code"]) for item in diagnostics),
                    "diagnostics": _diagnostic_text(diagnostics),
                }
            )
    return json_path, csv_path
