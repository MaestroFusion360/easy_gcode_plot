"""Test-runner arguments and exit codes must agree across supported shells."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _invoke(shell, arguments, tmp_path, active=False, exit_code=0):
    stub = tmp_path / "stub.py"
    stub.write_text(
        "import json, os, sys\n"
        "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}))\n"
        "sys.exit(int(os.environ['RUNNER_EXIT']))\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.cmd").write_text(f'@"{sys.executable}" "{stub}" %*\n', encoding="utf-8")
    uv = tmp_path / "uv"
    uv.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "{stub.as_posix()}" "$@"\n', encoding="utf-8")
    uv.chmod(0o755)
    env = dict(os.environ, RUNNER_EXIT=str(exit_code), VIRTUAL_ENV="test environment" if active else "")
    env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
    if shell == "powershell":
        executable = shutil.which("powershell") or shutil.which("pwsh")
        if executable is None:
            pytest.skip("PowerShell is unavailable")
        invocation = [executable, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts/ps1/test.ps1")]
    else:
        executable = shutil.which("bash")
        if executable is None and os.name == "nt":
            candidate = Path("C:/Program Files/Git/bin/bash.exe")
            executable = str(candidate) if candidate.exists() else None
        if executable is None:
            pytest.skip("Bash is unavailable")
        invocation = [executable, (ROOT / "scripts/sh/test.sh").as_posix()]
    return subprocess.run(
        [*invocation, *arguments], cwd=tmp_path, env=env, text=True, capture_output=True, timeout=20, check=False
    )


@pytest.mark.parametrize("shell", ["powershell", "bash"])
@pytest.mark.parametrize("configured", [False, True])
def test_test_runners_preserve_arguments_working_directory_and_exit_code(shell, configured, tmp_path):
    flags = ["-NoSync", "-Verbose"] if shell == "powershell" else ["--no-sync", "--verbose"]
    arguments = [*flags, "tests/a test.py", "-k", "alpha or beta"] if configured else []
    result = _invoke(shell, arguments, tmp_path, active=configured, exit_code=23)
    assert result.returncode == 23, result.stderr
    report = json.loads(result.stdout)
    expected = (
        ["run", "--no-sync", "--active", "pytest", "-q", "tests/a test.py", "-k", "alpha or beta", "-v"]
        if configured
        else ["run", "pytest", "-q", "tests"]
    )
    assert report["args"] == expected
    assert Path(report["cwd"]).resolve() == ROOT
