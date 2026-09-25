"""Directory orchestration over the single-file export service."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from app.gcode.batch import DEFAULT_BATCH_EXTENSIONS, _normalize_extensions, discover_nc_files
from app.gcode.export.service import ExportRequest, export_file, request_document

REPORT_BASENAME = "batch_export_report"
REPORT_SCHEMA_VERSION = 1


def _destination(path: Path, root: Path, output_root: Path, format_name: str, source_extensions: Iterable[str]) -> Path:
    destination = output_root / path.relative_to(root)
    suffix = ".dxf" if format_name == "dxf" else ".nc"
    if path.suffix.lower() in source_extensions:
        return destination.with_suffix(suffix)
    return destination.with_name(destination.name + suffix)


def _file_report(
    path: Path, root: Path, destination: Path, output_root: Path, request: ExportRequest
) -> dict[str, object]:
    started = perf_counter()
    relative = path.relative_to(root).as_posix()
    report: dict[str, object] = {
        "input_path": str(path),
        "input_relative_path": relative,
        "output_path": None,
        "output_relative_path": None,
        "status": "ERRORS",
        "ok": False,
        "complete": False,
        "size_bytes": None,
        "output_size_bytes": None,
        "motion_count": 0,
        "executed_block_count": 0,
        "diagnostic_count": 0,
        "diagnostics": [],
        "elapsed_ms": 0.0,
        "effective_units": None,
        "effective_arc_type": None,
    }
    try:
        report["size_bytes"] = path.stat().st_size
        exported = export_file(path, destination, request)
    except (OSError, UnicodeError, ValueError) as exc:
        report["diagnostics"] = [{"code": "EXPORT_ERROR", "message": str(exc), "severity": "error"}]
    else:
        execution = exported.execution
        diagnostics = execution.diagnostics
        report.update(
            ok=execution.ok,
            complete=execution.complete,
            motion_count=len(execution.motions),
            executed_block_count=len(execution.executed_blocks),
            diagnostics=[asdict(item) for item in diagnostics],
            effective_units=exported.effective_units,
            effective_arc_type=exported.effective_arc_type,
        )
        if execution.ok and execution.complete:
            report["status"] = "WARNINGS" if diagnostics else "EXPORTED"
            report["output_path"] = str(destination)
            report["output_relative_path"] = destination.relative_to(output_root).as_posix()
            report["output_size_bytes"] = exported.output_size_bytes
    report["diagnostic_count"] = len(report["diagnostics"])
    report["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
    return report


def export_directory(
    root: str | Path,
    output_root: str | Path,
    request: ExportRequest,
    *,
    recursive: bool = True,
    extensions: Iterable[str] = DEFAULT_BATCH_EXTENSIONS,
    on_file: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Export each discovered file to a mirrored tree and return a manifest."""
    started = perf_counter()
    directory = Path(root).resolve()
    destination_root = Path(output_root).resolve()
    if destination_root == directory or directory in destination_root.parents:
        raise ValueError("Output directory must be outside the input directory")
    normalized_extensions = _normalize_extensions(extensions)
    paths = discover_nc_files(directory, recursive=recursive, extensions=normalized_extensions)
    destinations = [
        _destination(path, directory, destination_root, request.format, normalized_extensions) for path in paths
    ]
    duplicates = [
        name for name, count in Counter(path.as_posix().casefold() for path in destinations).items() if count > 1
    ]
    if duplicates:
        raise ValueError(f"Multiple inputs map to the same output: {duplicates[0]}")
    files = []
    for path, destination in zip(paths, destinations, strict=True):
        item = _file_report(path, directory, destination, destination_root, request)
        files.append(item)
        if on_file is not None:
            on_file(item)
    counts = Counter(item["status"] for item in files)
    status = (
        "NO_FILES" if not files else "ERRORS" if counts["ERRORS"] else "WARNINGS" if counts["WARNINGS"] else "CLEAN"
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "root": str(directory),
        "output_root": str(destination_root),
        "language": request.language,
        "encoding": request.encoding,
        "recursive": recursive,
        "extensions": list(normalized_extensions),
        "format": request.format,
        "mode": request.mode,
        "units": request.units,
        "arc_type": request.arc_type,
        "export_options": request_document(request),
        "summary": {
            "files_total": len(files),
            "exported": counts["EXPORTED"] + counts["WARNINGS"],
            "warnings": counts["WARNINGS"],
            "errors": counts["ERRORS"],
            "diagnostics_total": sum(int(item["diagnostic_count"]) for item in files),
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        },
        "files": files,
    }


def write_export_reports(report: dict[str, object], output_root: str | Path) -> tuple[Path, Path]:
    """Write JSON and Excel-friendly CSV manifests beside exported programs."""
    directory = Path(output_root)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{REPORT_BASENAME}.json"
    csv_path = directory / f"{REPORT_BASENAME}.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    fieldnames = (
        "input_relative_path",
        "output_relative_path",
        "status",
        "ok",
        "complete",
        "size_bytes",
        "output_size_bytes",
        "motion_count",
        "executed_block_count",
        "diagnostic_count",
        "diagnostics",
        "elapsed_ms",
        "effective_units",
        "effective_arc_type",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for item in report["files"]:
            row = {name: item.get(name) for name in fieldnames}
            row["diagnostics"] = "; ".join(f"{entry['code']}: {entry['message']}" for entry in item["diagnostics"])
            writer.writerow(row)
    return json_path, csv_path
