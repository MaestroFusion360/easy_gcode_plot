"""Batch validation reports over the authoritative CNC execution kernel."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable

from app.gcode.kernel import Diagnostic, ExecutionResult
from app.gcode.kernel.io import read_nc_text
from app.gcode.program_execution import execute_program

BATCH_REPORT_SCHEMA_VERSION = 2
DEFAULT_BATCH_EXTENSIONS = (".nc", ".cnc", ".ptp", ".tap", ".txt")
STATUS_CLEAN = "CLEAN"
STATUS_WARNINGS = "WARNINGS"
STATUS_ERRORS = "ERRORS"
STATUS_NO_FILES = "NO_FILES"
_TURNING_MODELED_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 8, 9, 30, 98, 99})
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

    allowed = frozenset(_normalize_extensions(extensions))
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    files = [path for path in candidates if path.is_file() and path.suffix.lower() in allowed]
    return tuple(sorted(files, key=lambda path: path.relative_to(directory).as_posix().casefold()))


def _unsupported_codes(diagnostics: Iterable[Diagnostic], diagnostic_code: str) -> tuple[str, ...]:
    codes: set[str] = set()
    for diagnostic in diagnostics:
        if diagnostic.code != diagnostic_code:
            continue
        for match in _UNSUPPORTED_CODE_RE.findall(diagnostic.message):
            codes.add(match.upper())
    return tuple(sorted(codes, key=_code_sort_key))


def _code_sort_key(code: str) -> tuple[str, float, str]:
    try:
        return code[0], float(code[1:]), code
    except (IndexError, ValueError):
        return code[:1], float("inf"), code


def _literal_code(word: Any, letter: str) -> int | None:
    if word.letter != letter:
        return None
    try:
        value = float(word.expr)
    except ValueError:
        return None
    return int(value) if value.is_integer() else None


def _turning_unmodeled_m_diagnostics(result: ExecutionResult) -> tuple[Diagnostic, ...]:
    program = result.program
    if program is None:
        return ()
    diagnostics: list[Diagnostic] = []
    for block in program.blocks:
        if any(_literal_code(word, "G") == 65 for word in block.parsed_words):
            continue
        for word in block.parsed_words:
            code = _literal_code(word, "M")
            if code is None or code in _TURNING_MODELED_M_CODES:
                continue
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_M_CODE",
                    message=f"M{code} is not modeled for fanuc_turn; ignored for trace execution",
                    severity="warning",
                    status="unverified",
                    line=block.index + 1,
                    raw=block.raw,
                )
            )
    return tuple(diagnostics)


def _file_report(
    path: Path,
    root: Path,
    *,
    language: str,
    encoding: str,
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
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        }

    result, _tools, _inferred = execute_program(
        source,
        language=language,
        include_instructions=False,
        autodetect_arc_type=language == "fanuc_mill",
    )
    diagnostics = result.diagnostics
    if language == "fanuc_turn":
        diagnostics += _turning_unmodeled_m_diagnostics(result)
    status = (
        STATUS_ERRORS
        if not result.ok or not result.complete or any(item.severity == "error" for item in diagnostics)
        else STATUS_WARNINGS
        if diagnostics
        else STATUS_CLEAN
    )
    report = {
        "path": path.relative_to(root).as_posix(),
        "status": status,
        "ok": result.ok,
        "complete": result.complete,
        "size_bytes": size_bytes,
        "line_count": len(source.splitlines()),
        "motion_count": len(result.motions),
        "executed_block_count": len(result.executed_blocks),
        "diagnostic_count": len(diagnostics),
        "error_count": sum(item.severity == "error" for item in diagnostics),
        "warning_count": sum(item.severity != "error" for item in diagnostics),
        "unsupported_g_codes": list(_unsupported_codes(diagnostics, "UNSUPPORTED_G_CODE")),
        "unsupported_m_codes": list(_unsupported_codes(diagnostics, "UNSUPPORTED_M_CODE")),
        "diagnostics": [asdict(item) for item in diagnostics],
    }
    report["elapsed_ms"] = round((perf_counter() - started) * 1000.0, 3)
    return report


def _aggregate_unsupported(files: Iterable[dict[str, object]], key: str) -> list[dict[str, object]]:
    occurrences: Counter[str] = Counter()
    affected_files: defaultdict[str, set[str]] = defaultdict(set)
    for file_report in files:
        path = str(file_report["path"])
        for diagnostic in file_report["diagnostics"]:  # type: ignore[union-attr]
            expected_code = "UNSUPPORTED_G_CODE" if key == "unsupported_g_codes" else "UNSUPPORTED_M_CODE"
            if diagnostic["code"] != expected_code:
                continue
            for code in _UNSUPPORTED_CODE_RE.findall(str(diagnostic["message"])):
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
    language: str,
    encoding: str,
    recursive: bool = True,
    extensions: Iterable[str] = DEFAULT_BATCH_EXTENSIONS,
    on_file: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Execute every matching NC file and return a batch analysis report."""
    started = perf_counter()
    directory = Path(root).resolve()
    normalized_extensions = _normalize_extensions(extensions)
    paths = discover_nc_files(directory, recursive=recursive, extensions=normalized_extensions)
    files = []
    for path in paths:
        file_report = _file_report(path, directory, language=language, encoding=encoding)
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
        "language": language,
        "encoding": encoding,
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
        "elapsed_ms",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for file_report in report["files"]:  # type: ignore[union-attr]
            diagnostics = file_report["diagnostics"]
            writer.writerow(
                {
                    **{name: file_report.get(name) for name in fieldnames},
                    "unsupported_g_codes": ";".join(file_report["unsupported_g_codes"]),
                    "unsupported_m_codes": ";".join(file_report["unsupported_m_codes"]),
                    "diagnostic_codes": ";".join(str(item["code"]) for item in diagnostics),
                    "diagnostics": _diagnostic_text(diagnostics),
                }
            )
    return json_path, csv_path
