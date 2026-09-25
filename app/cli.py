"""Standalone CLI over the same authoritative CNC kernel used by the GUI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.gcode.batch import DEFAULT_BATCH_EXTENSIONS, analyze_directory, write_batch_reports
from app.gcode.exporter import (
    ExportOptions,
    export_cycle_groups,
    export_full_mill_program,
    export_full_program,
    export_result,
)
from app.gcode.kernel import ExecutionResult
from app.gcode.kernel.io import SUPPORTED_NC_ENCODINGS, read_nc_text
from app.gcode.program_execution import execute_program
from app.gcode.trace_tools import format_trace_statistics, trace_statistics


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action):
        if action.default is None:
            return action.help
        return super()._get_help_string(action)


def _parser() -> tuple[argparse.ArgumentParser, tuple[argparse.ArgumentParser, ...]]:
    program = Path(sys.argv[0]).name if getattr(sys, "frozen", False) else "python -m app"
    parser = argparse.ArgumentParser(prog=program, description="Parse, trace and analyze FANUC G-code")
    sub = parser.add_subparsers(dest="command", required=True)
    command_help = {
        "parse": "Parse one NC program and print a terminal summary",
        "trace": "Execute one NC program and optionally write its motion trace as JSON",
        "analyze": "Print execution statistics and optionally write JSON",
        "export": "Export an executed NC program, trace or cycle groups",
    }
    for name, description in command_help.items():
        command = sub.add_parser(
            name,
            help=description,
            description=description,
            formatter_class=_HelpFormatter,
        )
        command.add_argument("file", type=Path, help="NC program to process")
        command.add_argument(
            "--lang", choices=("fanuc_turn", "fanuc_mill"), default="fanuc_turn", help="Controller dialect"
        )
        command.add_argument("--encoding", choices=SUPPORTED_NC_ENCODINGS, default="utf-8", help="Input file encoding")
        if name in {"trace", "analyze"}:
            command.add_argument("-o", "--output", type=Path, help="Write detailed JSON to this file")
        if name == "export":
            command.add_argument("-o", "--output", type=Path, required=True, help="Export destination")
            command.add_argument(
                "--mode", choices=("trace", "program", "cycles"), default="trace", help="Export format"
            )

    batch = sub.add_parser(
        "batch",
        help="Analyze a directory of NC programs and write JSON/CSV reports",
        formatter_class=_HelpFormatter,
    )
    batch.add_argument("directory", type=Path, help="Directory containing NC programs")
    batch.add_argument("--lang", choices=("fanuc_turn", "fanuc_mill"), default="fanuc_turn", help="Controller dialect")
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
    return parser, tuple(sub.choices.values())


def _load(path: Path, language: str, encoding: str) -> tuple[str, ExecutionResult]:
    source = read_nc_text(path, encoding=encoding)
    result, _tools, _inferred = execute_program(source, language=language)
    return source, result


def _result_document(result: ExecutionResult, *, include_motions: bool) -> dict[str, object]:
    doc: dict[str, object] = {
        "ok": result.ok,
        "complete": result.complete,
        "instructions": [asdict(item) for item in result.instructions],
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "executed_blocks": list(result.executed_blocks),
        "signals": [asdict(item) for item in result.signals],
        "events": [asdict(item) for item in result.events],
        "program_end": result.program_end,
    }
    if include_motions:
        doc["motions"] = [asdict(item) for item in result.motions]
    return doc


def _analysis_document(result: ExecutionResult) -> dict[str, object]:
    stats = trace_statistics(result)
    summary = {k: v for k, v in stats.items() if k not in {"lengths", "times"}}
    return {
        "ok": result.ok,
        "complete": result.complete,
        "status": "verified" if result.ok and not result.diagnostics else "review",
        **summary,
        "statistics": summary,
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "signals": [asdict(item) for item in result.signals],
        "events": [asdict(item) for item in result.events],
        "program_end": result.program_end,
    }


def _write(path: Path | None, text: str) -> None:
    if path is None:
        print(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def _print_batch_file(file_report: dict[str, object]) -> None:
    print(f"[{file_report['status']}] {file_report['path']}", flush=True)
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


def _print_program_result(command: str, path: Path, result: ExecutionResult, output: Path | None = None) -> None:
    status = "ERRORS" if not result.ok or not result.complete else "WARNINGS" if result.diagnostics else "CLEAN"
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
    print(f"Analyzing NC programs in {Path(args.directory).resolve()} ({args.lang})", flush=True)
    try:
        report = analyze_directory(
            args.directory,
            language=args.lang,
            encoding=args.encoding,
            recursive=not args.top_level_only,
            extensions=extensions,
            on_file=_print_batch_file,
        )
        json_path, csv_path = write_batch_reports(report, args.output_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as exc:
        parser.error(str(exc))
    _print_batch_summary(report, json_path, csv_path)
    return 2 if report["status"] in {"ERRORS", "NO_FILES"} else 0


def _run_export(args: argparse.Namespace, source: str, result: ExecutionResult) -> int:
    if not result.ok or not result.complete:
        _print_program_result("export", args.file, result)
        return 2
    if args.mode == "program":
        program_exporter = export_full_program if args.lang == "fanuc_turn" else export_full_mill_program
        text = program_exporter(
            result,
            source.splitlines(),
            ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
        )
        _write(args.output, text.rstrip("\n"))
    elif args.mode == "cycles":
        text = export_cycle_groups(
            result,
            ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
        )
        _write(args.output, text.rstrip("\n"))
    else:
        _write(args.output, export_result(result, ExportOptions(delimiter=True, leading_zero=True)).rstrip("\n"))
    _print_program_result("export", args.file, result, args.output)
    return 0


def _run_single(args: argparse.Namespace) -> int:
    source, result = _load(args.file, args.lang, args.encoding)
    if args.command == "parse":
        _print_program_result("parse", args.file, result)
    elif args.command == "trace":
        if args.output is not None:
            _write(
                args.output, json.dumps(_result_document(result, include_motions=True), ensure_ascii=False, indent=2)
            )
        _print_program_result("trace", args.file, result, args.output)
    elif args.command == "analyze":
        if args.output is not None:
            _write(args.output, json.dumps(_analysis_document(result), ensure_ascii=False, indent=2))
        _print_program_result("analyze", args.file, result, args.output)
    else:
        return _run_export(args, source, result)
    return 0 if result.ok and result.complete else 2


def main(argv: list[str] | None = None) -> int:
    parser, commands = _parser()
    arguments = sys.argv[1:] if argv is None else argv
    if arguments in (["--help"], ["-h"]):
        parser.print_help()
        for command in commands:
            print()
            command.print_help()
        return 0
    args = parser.parse_args(arguments)
    if args.command == "export" and args.lang == "fanuc_mill" and args.mode == "cycles":
        parser.error("export --mode cycles is only available for fanuc_turn")
    if args.command == "batch":
        return _run_batch(args, parser)
    return _run_single(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
