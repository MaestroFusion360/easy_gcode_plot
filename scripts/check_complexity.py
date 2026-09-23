"""Reject new complexity debt and growth of existing per-function exceptions.

Run from either lint entrypoint. The baseline is reviewed source, not regenerated
by CI; lower or remove entries as functions are simplified. New functions use
Ruff's defaults: complexity 10, branches 12, statements 50.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "complexity_baseline.json"


def function_names(path):
    """Map definition lines to stable qualified names, including nested scopes."""
    names = {}

    def visit(node, scope=()):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = (*scope, child.name)
                names[child.lineno] = ".".join(qualified)
                visit(child, qualified)
            else:
                visit(child, scope)

    visit(ast.parse(path.read_text(encoding="utf-8")))
    return names


def measurements():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "app",
            "main.py",
            "--select",
            "C901,PLR0912,PLR0915",
            "--ignore-noqa",
            "--output-format",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    names = {}
    measured = {}
    for item in json.loads(result.stdout):
        path = Path(item["filename"])
        if path not in names:
            names[path] = function_names(path)
        function = names[path][item["location"]["row"]]
        key = f"{path.relative_to(ROOT).as_posix()}:{function}:{item['code']}"
        measured[key] = int(re.search(r"\((\d+) >", item["message"])[1])
    return measured


def main():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures = []
    for key, value in measurements().items():
        allowed = baseline.get(key)
        if allowed is None or value > allowed:
            failures.append(f"{key}: {value}; allowed {allowed if allowed is not None else 'Ruff default'}")
    if failures:
        print("Complexity increased:\n" + "\n".join(failures))
        return 1
    print("Complexity gate passed (no new or increased per-function debt).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
