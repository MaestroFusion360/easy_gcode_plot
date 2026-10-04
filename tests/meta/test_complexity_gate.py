"""The debt baseline permits existing code, never new or growing exceptions."""

import json
import subprocess

import pytest

from scripts import check_complexity


@pytest.mark.parametrize("stdout,stderr", [("", "No module named ruff"), ("broken", "Ruff failure")])
def test_missing_or_broken_ruff_reports_the_tool_failure(monkeypatch, capsys, stdout, stderr):
    monkeypatch.setattr(
        check_complexity.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 1, stdout, stderr)
    )
    assert check_complexity.main() == 2
    assert stderr in capsys.readouterr().err


@pytest.mark.parametrize(
    ("measured", "expected"),
    [({"known:C901": 15}, 0), ({"known:C901": 14}, 0), ({"known:C901": 16}, 1), ({"new:C901": 11}, 1)],
)
def test_complexity_gate_rejects_new_or_increased_debt(tmp_path, monkeypatch, measured, expected):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"known:C901": 15}), encoding="utf-8")
    monkeypatch.setattr(check_complexity, "BASELINE", baseline)
    monkeypatch.setattr(check_complexity, "measurements", lambda: measured)
    assert check_complexity.main() == expected


def test_complexity_names_distinguish_scopes(tmp_path):
    source = tmp_path / "example.py"
    source.write_text(
        "class First:\n    def run(self):\n        def nested(): pass\nclass Second:\n    def run(self): pass\n"
    )
    assert check_complexity.function_names(source) == {
        1: "First",
        2: "First.run",
        3: "First.run.nested",
        4: "Second",
        5: "Second.run",
    }
