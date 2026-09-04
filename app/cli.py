"""Standalone CLI over the same authoritative CNC kernel used by the GUI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.gcode.exporter import (
    ExportOptions,
    export_cycle_groups,
    export_full_mill_program,
    export_full_program,
    export_result,
)
from app.gcode.kernel import ExecutionResult, execute
from app.gcode.trace_tools import trace_statistics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app", description="Parse, trace and analyze FANUC G-code")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("parse", "trace", "analyze", "export"):
        command = sub.add_parser(name)
        command.add_argument("file", type=Path)
        command.add_argument("--lang", choices=("fanuc_turn", "fanuc_mill"), default="fanuc_turn")
        if name in {"trace", "analyze"}:
            command.add_argument("-o", "--output", type=Path)
        if name == "export":
            command.add_argument("-o", "--output", type=Path, required=True)
            command.add_argument("--mode", choices=("trace", "program", "cycles"), default="trace")
    return parser


def _load(path: Path, language: str) -> tuple[str, ExecutionResult]:
    source = path.read_text(encoding="utf-8-sig")
    return source, execute(source, language=language)


def _result_document(result: ExecutionResult, *, include_motions: bool) -> dict[str, object]:
    doc: dict[str, object] = {
        "ok": result.ok,
        "instructions": [asdict(item) for item in result.instructions],
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "executed_blocks": list(result.executed_blocks),
        "signals": [asdict(item) for item in result.signals],
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
        "status": "verified" if result.ok and not result.diagnostics else "review",
        **summary,
        "statistics": summary,
        "diagnostics": [asdict(item) for item in result.diagnostics],
        "signals": [asdict(item) for item in result.signals],
        "program_end": result.program_end,
    }


def _write(path: Path | None, text: str) -> None:
    if path is None:
        print(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "export" and args.lang == "fanuc_mill" and args.mode == "cycles":
        parser.error("export --mode cycles is only available for fanuc_turn")

    source, result = _load(args.file, args.lang)
    if args.command == "parse":
        _write(None, json.dumps(_result_document(result, include_motions=False), ensure_ascii=False, indent=2))
    elif args.command == "trace":
        _write(args.output, json.dumps(_result_document(result, include_motions=True), ensure_ascii=False, indent=2))
    elif args.command == "analyze":
        _write(args.output, json.dumps(_analysis_document(result), ensure_ascii=False, indent=2))
    elif args.mode == "program":
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
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
