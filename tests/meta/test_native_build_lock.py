"""Windows builds should identify locked extensions before compiling them."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ps1/assert-native-unlocked.ps1"
pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None, reason="Windows native build workflow"
)


def _check(project):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-ProjectRoot", str(project)],
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize("module", ["frontend/_native_parser", "milling/_native_executor", "discovery"])
def test_native_build_reports_locked_extension_and_succeeds_after_release(tmp_path, module):
    relative = "app/tools/_native_discovery.pyd" if module == "discovery" else f"app/gcode/kernel/{module}.pyd"
    extension = tmp_path / relative
    extension.parent.mkdir(parents=True)
    extension.write_bytes(b"native build lock fixture")
    with extension.open("rb"):
        result = _check(tmp_path)
        assert result.returncode != 0
        assert b"Native extension cannot be replaced" in result.stderr
        assert b"Close the running application or Python session" in result.stderr
    assert _check(tmp_path).returncode == 0


def test_native_build_accepts_initial_checkout_without_extensions(tmp_path):
    assert _check(tmp_path).returncode == 0
