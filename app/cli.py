"""Standalone CLI over the same authoritative CNC kernel used by the GUI."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from importlib import import_module
from pathlib import Path

from app.gcode.batch.analysis import (
    DEFAULT_BATCH_EXTENSIONS,
    analysis_diagnostic_summary,
    analysis_status,
    analyze_directory,
    analyze_file,
    validate_batch_output_directory,
    write_batch_reports,
)
from app.gcode.batch.export import export_directory, write_export_reports
from app.gcode.comments import COMMENT_STYLES, DEFAULT_COMMENT_STYLE
from app.gcode.execution.program import execute_program
from app.gcode.execution.source import language_for_path, source_dialect_for_path
from app.gcode.export.common import is_export_limitation
from app.gcode.export.service import ExportRequest, export_file, validate_export_request
from app.gcode.file_io import atomic_write_text, same_file, validate_output_paths
from app.gcode.kernel import ExecutionResult
from app.gcode.kernel.frontend.io import SUPPORTED_NC_ENCODINGS, read_nc_text
from app.gcode.reports.html import export_execution_statistics
from app.gcode.reports.kinematics import kinematics_report_fields
from app.gcode.trace import format_trace_statistics, trace_statistics
from app.integration.minicad_bundle import read_bundle
from app.native import NativeRuntimeError, require_packaged_native

MACHINE_TYPE_HELP = (
    "Machine type (auto: H milling; MPF/SPF turning with native turning signatures, otherwise milling; "
    "other extensions turning)"
)


def _add_kinematics_option(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--kinematics", metavar="PROFILE_ID", help="Milling rotary-kinematics profile (FANUC, SINUMERIK or HEIDENHAIN)"
    )


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action):
        if action.default is None:
            return action.help
        return super()._get_help_string(action)


def _add_export_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--format", choices=("nc", "dxf"), default="nc", help="Output format")
    command.add_argument(
        "--target-dialect",
        "--post-profile",
        metavar="NAME_OR_JSON",
        help=(
            "Expanded NC post profile: fanuc_mill, fanuc_mill_multiaxis, fanuc_lathe_a/b, "
            "sinumerik_iso, sinumerik_840d, sinumerik_840d_multiaxis, "
            "heidenhain_itnc530, or JSON path"
        ),
    )
    command.add_argument("--mode", choices=("expanded", "full"), default="expanded", help="NC export mode")
    command.add_argument("--units", choices=("auto", "mm", "inch"), default="auto", help="Output units")
    command.add_argument(
        "--arc-type",
        choices=("auto", "ijk-relative", "ijk-absolute", "radius", "linearized"),
        default="auto",
        help="Expanded arc representation",
    )
    command.add_argument("--coordinates", choices=("absolute", "incremental"), default="absolute")
    for name in (
        "sequence-numbers",
        "sequence-spacing",
        "spaces",
        "leading-zero",
        "comments",
        "safety-line",
        "modal-feed",
    ):
        command.add_argument(f"--{name}", action=argparse.BooleanOptionalAction, default=None)
    command.add_argument("--sequence-start", type=int, default=1)
    command.add_argument("--sequence-increment", type=int, default=1)
    command.add_argument("--start-program", default="")
    command.add_argument("--end-program", default="")
    command.add_argument("--comment-style", choices=COMMENT_STYLES, default=DEFAULT_COMMENT_STYLE)
    command.add_argument("--decimal-places", type=int, default=None)
    command.add_argument("--force-decimal", action=argparse.BooleanOptionalAction, default=None)
    command.add_argument("--plus-output", action=argparse.BooleanOptionalAction, default=None)


_EXPORT_FLAGS = {
    "--mode": "mode",
    "--arc-type": "arc_type",
    "--coordinates": "coordinates",
    "--sequence-start": "sequence_start",
    "--sequence-increment": "sequence_increment",
    "--start-program": "start_program",
    "--end-program": "end_program",
    "--comment-style": "comment_style",
    "--decimal-places": "decimal_places",
}
for _name in (
    "sequence-numbers",
    "sequence-spacing",
    "spaces",
    "leading-zero",
    "comments",
    "safety-line",
    "modal-feed",
    "force-decimal",
    "plus-output",
):
    _EXPORT_FLAGS[f"--{_name}"] = _name.replace("-", "_")
    _EXPORT_FLAGS[f"--no-{_name}"] = _name.replace("-", "_")


def _export_request(args: argparse.Namespace, arguments: list[str]) -> tuple[ExportRequest, frozenset[str]]:
    explicit = frozenset(
        _EXPORT_FLAGS[token.split("=", 1)[0]] for token in arguments if token.split("=", 1)[0] in _EXPORT_FLAGS
    )
    return ExportRequest(
        language=args.lang,
        target_dialect=getattr(args, "target_dialect", None),
        lathe_gcode_system=args.lathe_gcode_system,
        sinumerik_840d_sl=args.sinumerik_cycles == "sl",
        kinematics=args.kinematics,
        encoding=args.encoding,
        format=args.format,
        mode=args.mode,
        units=args.units,
        arc_type=args.arc_type,
        coordinates=args.coordinates,
        sequence_numbers=bool(args.sequence_numbers),
        sequence_start=args.sequence_start,
        sequence_increment=args.sequence_increment,
        sequence_spacing=bool(args.sequence_spacing),
        spaces=True if args.spaces is None else args.spaces,
        leading_zero=bool(args.leading_zero),
        comments=True if args.comments is None else args.comments,
        safety_line=bool(args.safety_line),
        modal_feed=True if args.modal_feed is None else args.modal_feed,
        start_program=args.start_program,
        end_program=args.end_program,
        comment_style=args.comment_style,
        decimal_places=6 if args.decimal_places is None else args.decimal_places,
        decimal_places_explicit=args.decimal_places is not None,
        force_decimal=bool(args.force_decimal),
        force_decimal_explicit=args.force_decimal is not None,
        plus_output=bool(args.plus_output),
        plus_output_explicit=args.plus_output is not None,
    ), explicit


def _parser() -> tuple[argparse.ArgumentParser, tuple[argparse.ArgumentParser, ...]]:
    program = Path(sys.argv[0]).name if getattr(sys, "frozen", False) else "python -m app"
    parser = argparse.ArgumentParser(
        prog=program, description="Parse, analyze and export FANUC, SINUMERIK and HEIDENHAIN iTNC programs"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    command_help = {
        "parse": "Parse one NC program and print a terminal summary",
        "trace": "Execute one NC program and optionally write its motion trace as JSON",
        "analyze": "Print execution statistics and optionally write JSON",
        "export": "Export one executed NC program or DXF toolpath",
    }
    for name, description in command_help.items():
        command = sub.add_parser(
            name,
            help=description,
            description=description,
            formatter_class=_HelpFormatter,
        )
        command.add_argument("file", type=Path, help="NC program to process")
        if name in {"trace", "analyze", "export"}:
            _add_kinematics_option(command)
        command.add_argument(
            "--lang",
            choices=("fanuc_turn", "fanuc_mill"),
            default=None,
            help=MACHINE_TYPE_HELP,
        )
        command.add_argument("--lathe-gcode-system", choices=("A", "B"), default="A")
        command.add_argument(
            "--sinumerik-cycles",
            choices=("classic", "sl"),
            default="sl",
            help="Native cycles: classic 01/2008 or 840D Extended cycles (03/2009)",
        )
        command.add_argument("--encoding", choices=SUPPORTED_NC_ENCODINGS, default="utf-8", help="Input file encoding")
        if name in {"trace", "analyze"}:
            command.add_argument("-o", "--output", type=Path, help="Write detailed JSON to this file")
        if name == "analyze":
            command.add_argument("--html", type=Path, help="Save aggregate statistics as HTML with a tool selector")
            command.add_argument("--inches", action="store_true", help="Display HTML statistics in inches")
        if name == "export":
            command.add_argument("-o", "--output", type=Path, required=True, help="Export destination")
            command.add_argument(
                "--compare-with",
                type=Path,
                metavar="FILE",
                help="Compare generated NC with a UTF-8 reference; print unified diff and exit 1 on mismatch",
            )
            _add_export_options(command)

    simulate = sub.add_parser(
        "simulate",
        help="Open an NC program in the GUI and start stock-removal simulation",
        formatter_class=_HelpFormatter,
    )
    simulate.add_argument("file", type=Path, help="NC program to simulate")
    simulate.add_argument("--bundle", type=Path, help="MiniCAD simulation.json manifest")
    simulate.add_argument(
        "--lang",
        choices=("fanuc_turn", "fanuc_mill"),
        default=None,
        help=MACHINE_TYPE_HELP,
    )

    batch = sub.add_parser(
        "batch",
        help="Analyze a directory of NC programs and write JSON/CSV reports",
        formatter_class=_HelpFormatter,
    )
    batch.add_argument("directory", type=Path, help="Directory containing NC programs")
    _add_kinematics_option(batch)
    batch.add_argument(
        "--lang",
        choices=("fanuc_turn", "fanuc_mill"),
        default=None,
        help=MACHINE_TYPE_HELP,
    )
    batch.add_argument("--html", type=Path, metavar="DIRECTORY", help="Save one HTML statistics/SVG report per NC file")
    batch.add_argument("--inches", action="store_true", help="Display HTML statistics in inches")
    batch.add_argument("--lathe-gcode-system", choices=("A", "B"), default="A")
    batch.add_argument(
        "--sinumerik-cycles",
        choices=("classic", "sl"),
        default="sl",
        help="Native cycles: classic 01/2008 or 840D Extended cycles (03/2009)",
    )
    batch.add_argument("--encoding", choices=SUPPORTED_NC_ENCODINGS, default="utf-8", help="Input file encoding")
    batch.add_argument("-o", "--output-dir", type=Path, default=Path("batch-report"), help="Report directory")
    batch.add_argument(
        "--extensions",
        default=",".join(DEFAULT_BATCH_EXTENSIONS),
        help="Comma-separated NC file extensions",
    )
    batch.add_argument(
        "--top-level-only",
        action="store_true",
        help="Do not scan subdirectories",
    )
    batch.add_argument(
        "--kinematics-map",
        type=Path,
        metavar="JSON",
        help="JSON object mapping input-relative NC paths to rotary profile IDs",
    )
    batch_export = sub.add_parser(
        "batch-export",
        help="Export a directory of NC programs to a mirrored tree",
        formatter_class=_HelpFormatter,
    )
    batch_export.add_argument("directory", type=Path, help="Directory containing NC programs")
    _add_kinematics_option(batch_export)
    batch_export.add_argument(
        "--lang",
        choices=("fanuc_turn", "fanuc_mill"),
        default=None,
        help=MACHINE_TYPE_HELP,
    )
    batch_export.add_argument("--lathe-gcode-system", choices=("A", "B"), default="A")
    batch_export.add_argument(
        "--sinumerik-cycles",
        choices=("classic", "sl"),
        default="sl",
        help="Native cycles: classic 01/2008 or 840D Extended cycles (03/2009)",
    )
    batch_export.add_argument("--encoding", choices=SUPPORTED_NC_ENCODINGS, default="utf-8")
    batch_export.add_argument("-o", "--output-dir", type=Path, required=True, help="Separate output directory")
    batch_export.add_argument("--extensions", default=",".join(DEFAULT_BATCH_EXTENSIONS))
    batch_export.add_argument("--top-level-only", action="store_true")
    batch_export.add_argument(
        "--kinematics-map",
        type=Path,
        metavar="JSON",
        help="JSON object mapping input-relative NC paths to rotary profile IDs",
    )
    _add_export_options(batch_export)
    return parser, tuple(sub.choices.values())


def _load(
    path: Path,
    language: str,
    encoding: str,
    *,
    for_analysis: bool = False,
    kinematics: str | None = None,
    lathe_gcode_system: str = "A",
    sinumerik_840d_sl: bool = True,
) -> tuple[str, ExecutionResult]:
    if for_analysis:
        return analyze_file(
            path,
            encoding=encoding,
            language=language,
            kinematics=kinematics,
            lathe_gcode_system=lathe_gcode_system,
            sinumerik_840d_sl=sinumerik_840d_sl,
        )
    source = read_nc_text(path, encoding=encoding)
    result, _tools, _inferred = execute_program(
        source,
        language=language,
        kinematics=kinematics,
        lathe_gcode_system=lathe_gcode_system,
        sinumerik_840d_sl=sinumerik_840d_sl,
        source_dialect=source_dialect_for_path(path, source),
    )
    return source, result


def _result_document(result: ExecutionResult, *, include_motions: bool) -> dict[str, object]:
    doc: dict[str, object] = {
        "source_dialect": result.source_dialect,
        "ok": result.ok,
        "complete": result.complete,
        "instructions": [asdict(item) for item in result.instructions],
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "executed_blocks": list(result.executed_blocks),
        "signals": [asdict(item) for item in result.signals],
        "events": [asdict(item) for item in result.events],
        "program_end": result.program_end,
        "kinematics_profile": result.kinematics_profile,
        **kinematics_report_fields(result),
        "rotary_angles": dict(result.rotary_angles),
    }
    if include_motions:
        doc["motions"] = [asdict(item) for item in result.motions]
    return doc


def _analysis_document(result: ExecutionResult) -> dict[str, object]:
    stats = trace_statistics(result)
    summary = {k: v for k, v in stats.items() if k not in {"lengths", "times"}}
    return {
        "source_dialect": result.source_dialect,
        "ok": result.ok,
        "complete": result.complete,
        "status": analysis_status(result),
        **summary,
        "executed_block_count": len(result.executed_blocks),
        **analysis_diagnostic_summary(result),
        "statistics": summary,
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "signals": [asdict(item) for item in result.signals],
        "events": [asdict(item) for item in result.events],
        "program_end": result.program_end,
        "kinematics_profile": result.kinematics_profile,
        **kinematics_report_fields(result),
        "rotary_angles": dict(result.rotary_angles),
    }


def _write(path: Path | None, text: str) -> None:
    if path is None:
        print(text)
        return
    atomic_write_text(path, text + ("" if text.endswith("\n") else "\n"))


def _print_batch_file(file_report: dict[str, object]) -> None:
    print(f"[{file_report['status']}] {file_report['path']}", flush=True)
    if file_report.get("html_report"):
        print(f"  HTML statistics: {file_report['html_report']}", flush=True)
    for diagnostic in file_report["diagnostics"]:
        location = f"line {diagnostic['line']}: " if diagnostic.get("line") is not None else ""
        print(f"  {location}{diagnostic['code']}: {diagnostic['message']}", flush=True)


def _print_batch_summary(report: dict[str, object], json_path: Path, csv_path: Path) -> None:
    summary = report["summary"]
    print(f"\nResult: {report['status']}")
    print(
        f"Processed: {summary['files_total']}  Clean: {summary['CLEAN']}  "
        f"Warnings: {summary['WARNINGS']}  Errors: {summary['ERRORS']}"
    )
    print(f"Diagnostics: {summary['diagnostics_total']}  Time: {summary['elapsed_ms']} ms")
    if report["status"] == "NO_FILES":
        print("\nNo matching NC files found.")
    print(f"\nJSON report: {json_path}")
    print(f"CSV report:  {csv_path}")


def _result_status(result: ExecutionResult) -> str:
    if result.ok and result.complete:
        return "WARNINGS" if result.diagnostics else "CLEAN"
    errors = [diagnostic for diagnostic in result.diagnostics if diagnostic.severity == "error"]
    if errors and all(is_export_limitation(diagnostic) for diagnostic in errors):
        return "UNSUPPORTED"
    return "ERRORS"


def _print_program_result(command: str, path: Path, result: ExecutionResult, output: Path | None = None) -> None:
    status = _result_status(result)
    print(f"{command.capitalize()}: {path}")
    print(f"Result: {status}")
    print(
        f"Instructions: {len(result.instructions)}  Motions: {len(result.motions)}  "
        f"Diagnostics: {len(result.diagnostics)}"
    )
    if command == "analyze":
        print()
        print(format_trace_statistics(trace_statistics(result)))
    for diagnostic in result.diagnostics:
        location = f"line {diagnostic.line}: " if diagnostic.line is not None else ""
        print(f"  {location}{diagnostic.code}: {diagnostic.message}")
    if output is not None and output.exists():
        print(f"Output: {output}")


def _run_batch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    extensions = tuple(item.strip() for item in args.extensions.split(",") if item.strip())
    print(f"Analyzing NC programs in {Path(args.directory).resolve()} ({args.lang or 'auto'})", flush=True)
    try:
        validate_batch_output_directory(
            args.directory,
            args.output_dir,
            extensions=extensions,
            generated_extensions=(".json", ".csv"),
            recursive=not args.top_level_only,
            label="Report output",
        )
        if args.html is not None:
            validate_batch_output_directory(
                args.directory,
                args.html,
                extensions=extensions,
                generated_extensions=(".html",),
                recursive=not args.top_level_only,
                label="HTML output",
            )
        profile_map = _read_kinematics_map(args.kinematics_map)
        report = analyze_directory(
            args.directory,
            language=args.lang,
            encoding=args.encoding,
            recursive=not args.top_level_only,
            extensions=extensions,
            on_file=_print_batch_file,
            kinematics=args.kinematics,
            kinematics_by_file=profile_map,
            lathe_gcode_system=args.lathe_gcode_system,
            sinumerik_840d_sl=args.sinumerik_cycles == "sl",
            html_dir=args.html,
            inches=args.inches,
        )
        json_path, csv_path = write_batch_reports(report, args.output_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    _print_batch_summary(report, json_path, csv_path)
    return 2 if report["status"] in {"ERRORS", "NO_FILES"} else 0


def _compare_nc_output(output: Path, reference: Path, expected: str) -> int:
    actual = output.read_text(encoding="utf-8")
    if actual == expected:
        print(f"Comparison: MATCH ({reference})")
        return 0
    print(f"Comparison: DIFFERENT ({reference})")
    for line in difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=reference.as_posix(),
        tofile=output.as_posix(),
    ):
        sys.stdout.write(line)
        if not line.endswith("\n"):
            sys.stdout.write("\n\\ No newline at end of file\n")
    return 1


def _run_export(args: argparse.Namespace, request: ExportRequest) -> int:
    try:
        expected = None
        if args.compare_with is not None:
            if request.format != "nc":
                raise ValueError("--compare-with requires --format nc")
            if same_file(args.output, args.compare_with):
                raise ValueError("Export output must differ from the comparison reference file")
            expected = args.compare_with.read_text(encoding="utf-8")
        exported = export_file(args.file, args.output, request)
        _print_program_result("export", args.file, exported.execution, args.output)
        if not exported.execution.ok or not exported.execution.complete:
            return 2
        if expected is not None:
            return _compare_nc_output(args.output, args.compare_with, expected)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Export error: {exc}", file=sys.stderr)
        return 2
    return 0


def _read_kinematics_map(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    mapping = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or any(
        not isinstance(name, str) or not name or not isinstance(profile, str) or not profile
        for name, profile in mapping.items()
    ):
        raise ValueError("Kinematics map must be a JSON object of relative paths to profile IDs")
    return mapping


def _run_batch_export(args: argparse.Namespace, request: ExportRequest, parser: argparse.ArgumentParser) -> int:
    extensions = tuple(item.strip() for item in args.extensions.split(",") if item.strip())
    print(f"Exporting NC programs in {Path(args.directory).resolve()} ({args.lang or 'auto'})", flush=True)

    def print_file(item: dict[str, object]) -> None:
        print(f"[{item['status']}] {item['input_relative_path']}", flush=True)
        for diagnostic in item["diagnostics"]:
            location = f"line {diagnostic['line']}: " if diagnostic.get("line") is not None else ""
            print(f"  {location}{diagnostic['code']}: {diagnostic['message']}", flush=True)

    try:
        profile_map = _read_kinematics_map(args.kinematics_map)
        report = export_directory(
            args.directory,
            args.output_dir,
            request,
            recursive=not args.top_level_only,
            extensions=extensions,
            on_file=print_file,
            kinematics_by_file=profile_map,
        )
        json_path, csv_path = write_export_reports(report, args.output_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    summary = report["summary"]
    print(f"\nResult: {report['status']}")
    print(
        f"Processed: {summary['files_total']}  Exported: {summary['exported']}  "
        f"Unsupported: {summary['unsupported']}  Warnings: {summary['warnings']}  Errors: {summary['errors']}"
    )
    print(f"JSON report: {json_path}\nCSV report:  {csv_path}")
    return 2 if report["status"] in {"ERRORS", "UNSUPPORTED", "NO_FILES"} else 0


def _run_single(args: argparse.Namespace) -> int:
    validate_output_paths(args.file, getattr(args, "output", None), getattr(args, "html", None))
    _source, result = _load(
        args.file,
        args.lang,
        args.encoding,
        for_analysis=args.command == "analyze",
        kinematics=getattr(args, "kinematics", None),
        lathe_gcode_system=args.lathe_gcode_system,
        sinumerik_840d_sl=args.sinumerik_cycles == "sl",
    )
    if args.command == "parse":
        _print_program_result("parse", args.file, result)
    elif args.command == "trace":
        if args.output is not None:
            _write(
                args.output, json.dumps(_result_document(result, include_motions=True), ensure_ascii=False, indent=2)
            )
        _print_program_result("trace", args.file, result, args.output)
    elif args.command == "analyze":
        if args.html is not None:
            try:
                export_execution_statistics(result, args.html, source_path=args.file, inches=args.inches)
            except (OSError, ValueError) as exc:
                print(f"HTML export error: {exc}", file=sys.stderr)
                return 2
            print(f"HTML statistics: {args.html}")
        if args.output is not None:
            _write(args.output, json.dumps(_analysis_document(result), ensure_ascii=False, indent=2))
        _print_program_result("analyze", args.file, result, args.output)
    return 0 if result.ok and result.complete else 2


def _native_runtime_ready() -> bool:
    try:
        require_packaged_native()
    except NativeRuntimeError as error:
        print(f"Native runtime error: {error}", file=sys.stderr)
        return False
    return True


def _run_simulate(args: argparse.Namespace) -> int:
    """Use the existing GUI stock simulator, including in packaged CLI builds."""
    path = args.file.expanduser().resolve()
    if not path.is_file() or path.suffix.casefold() == ".stl":
        print(f"Simulate error: NC program not found: {path}", file=sys.stderr)
        return 2
    bundle = None
    if args.bundle is not None:
        try:
            bundle = read_bundle(args.bundle)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Simulate error: {exc}", file=sys.stderr)
            return 2
        if bundle.nc != path:
            print("Simulate error: NC path does not match bundle", file=sys.stderr)
            return 2
    if getattr(sys, "frozen", False):
        return _run_frozen_simulate(path, args.lang, args.bundle)
    return _run_source_simulate(path, args.lang, bundle)


def _run_frozen_simulate(path: Path, language: str, bundle_path=None) -> int:
    """Launch the companion GUI without waiting for its event loop to exit."""
    gui_name = "easy_gcode_plot.exe" if os.name == "nt" else "easy_gcode_plot"
    gui_path = Path(sys.executable).with_name(gui_name)
    if not gui_path.is_file():
        print(f"Simulate error: GUI executable not found: {gui_path}", file=sys.stderr)
        return 2
    try:
        # A Popen context manager would wait for the GUI at scope exit.
        command = [str(gui_path), "--simulate", str(path), "--lang", language]
        if bundle_path is not None:
            command.extend(("--bundle", str(Path(bundle_path).resolve())))
        subprocess.Popen(command)  # pylint: disable=consider-using-with
    except OSError as exc:
        print(f"Simulate error: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_source_simulate(path: Path, language: str, bundle=None) -> int:
    """Import the Qt application only for the simulate command."""
    return import_module("app.application").run(startup_file=path, simulate=True, language=language, bundle=bundle)


def _run_single_safely(args) -> int:
    try:
        return _run_single(args)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"{args.command.capitalize()} error: {exc}", file=sys.stderr)
        return 2


def _validate_cli_profiles(args, parser) -> None:
    if args.command in {"batch", "batch-export"} and args.lang is None:
        return
    if getattr(args, "kinematics", None) and args.lang != "fanuc_mill":
        parser.error("--kinematics requires --lang fanuc_mill")
    if getattr(args, "kinematics_map", None) and args.lang != "fanuc_mill":
        parser.error("--kinematics-map requires --lang fanuc_mill")


def main(argv: list[str] | None = None) -> int:
    if not _native_runtime_ready():
        return 2
    parser, commands = _parser()
    arguments = sys.argv[1:] if argv is None else argv
    if arguments in (["--help"], ["-h"]):
        parser.print_help()
        for command in commands:
            print()
            command.print_help()
        return 0
    args = parser.parse_args(arguments)
    if args.lang is None and args.command not in {"batch", "batch-export"}:
        args.lang = language_for_path(args.file)
    _validate_cli_profiles(args, parser)
    if args.command in {"export", "batch-export"}:
        request, explicit = _export_request(args, arguments)
        try:
            validate_export_request(request, explicit=explicit)
        except ValueError as exc:
            parser.error(str(exc))
        if args.command == "export":
            return _run_export(args, request)
        return _run_batch_export(args, request, parser)
    if args.command == "batch":
        return _run_batch(args, parser)
    handler = _run_simulate if args.command == "simulate" else _run_single_safely
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
