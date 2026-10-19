"""Run installed static analyzers without importing or executing application code.

Usage: uv run --no-sync python scripts/analyze_project.py
GUI:   uv run --no-sync python scripts/analyze_project.py --scope ui
Reports go to tmp/gcode-analysis or tmp/ui-analysis. Exit 1 means findings need review, not that
behavior is wrong. Existing findings are not suppressed or accepted as a baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable(name):
    path = Path(sys.executable).with_name(name + (".exe" if os.name == "nt" else ""))
    if not path.is_file():
        raise RuntimeError(f"Missing {name}. Install the locked dev group with uv sync --group dev.")
    return str(path)


def analyze(output, scope="gcode"):
    output.mkdir(parents=True, exist_ok=True)
    config = ROOT / ".jscpd.json"
    targets = ["app/gcode"]
    if scope == "ui":
        targets = ["app/ui", "app/main_window.py"]
        settings = json.loads(config.read_text(encoding="utf-8"))
        settings["path"] = [str(ROOT / target) for target in targets]
        settings["ignore"] += ["**/generated/**", "**/resources/**"]
        config = output / "jscpd-config.json"
        config.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    for report in ("summary.json", "pylint.json", "exact/jscpd-report.json", "normalized/jscpd-report.json"):
        (output / report).unlink(missing_ok=True)
    clone_command = [
        executable("jscpd"),
        "--config",
        str(config),
        "--no-colors",
        "--no-tips",
        "--fail-on-empty",
        "--exit-code",
        "1",
    ]
    commands = {
        "imports": [executable("lint-imports"), "--no-logo", "--no-cache", "--verbose"],
        "pylint": [
            sys.executable,
            "-m",
            "pylint",
            *targets,
            *(["--disable=all"] if scope == "gcode" else []),
            "--enable=cyclic-import,duplicate-code",
            "--score=n",
            "--reports=n",
            "--persistent=n",
            "--output-format=json",
            f"--output={output / 'pylint.json'}",
        ],
        "exact": [*clone_command, "--output", str(output / "exact")],
        "normalized": [
            *clone_command,
            "--ignore-identifiers",
            "--ignore-literals",
            "--similarity=0.9",
            "--min-nodes",
            "40",
            "--output",
            str(output / "normalized"),
        ],
    }
    summary = {}
    for name, command in commands.items():
        print(f"Running {name}...", flush=True)
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"},
        )
        (output / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        summary[name] = {"command": command, "exit_code": result.returncode}
        if name in {"exact", "normalized"}:
            report_path = output / name / "jscpd-report.json"
            if not report_path.is_file():
                raise RuntimeError(f"{name} analyzer did not create {report_path}; see {output / (name + '.log')}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            summary[name]["statistics"] = report["statistics"]["total"]
            summary[name]["clone_kinds"] = dict(Counter(clone["kind"] for clone in report["duplicates"]))
        elif name == "pylint":
            messages = json.loads((output / "pylint.json").read_text(encoding="utf-8"))
            summary[name]["messages"] = dict(Counter(message["symbol"] for message in messages))
        print(f"{name}: exit {result.returncode}; report {output / (name + '.log')}", flush=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return int(any(item["exit_code"] for item in summary.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("gcode", "ui"), default="gcode")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = args.output or ROOT / "tmp" / f"{args.scope}-analysis"
        return analyze(output.resolve(), args.scope)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
