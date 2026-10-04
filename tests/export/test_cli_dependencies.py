"""Optional DXF dependencies must not leak into analysis commands."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("command", ["parse", "trace", "analyze", "batch", "export_nc", "export_dxf"])
def test_cli_without_ezdxf(tmp_path, command):
    source = tmp_path / "program.nc"
    source.write_text("G1 X1 Z2 F100\nM30\n", encoding="utf-8")
    arguments = [command, str(source)]
    if command == "batch":
        arguments = ["batch", str(tmp_path), "-o", str(tmp_path / "report")]
    if command.startswith("export_"):
        format_name = command.removeprefix("export_")
        arguments = ["export", str(source), "--format", format_name, "-o", str(tmp_path / f"out.{format_name}")]
    script = """import importlib.abc, sys
class NoDxf(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'ezdxf' or fullname.startswith('ezdxf.'):
            raise ModuleNotFoundError('ezdxf deliberately unavailable')
sys.meta_path.insert(0, NoDxf())
from app.cli import main
assert 'ezdxf' not in sys.modules
raise SystemExit(main(sys.argv[1:]))
"""
    checked = subprocess.run(
        [sys.executable, "-c", script, *arguments], capture_output=True, text=True, timeout=20, check=False
    )
    assert checked.returncode == (2 if command == "export_dxf" else 0), checked.stderr
    assert "Traceback" not in checked.stderr
    if command == "export_dxf":
        assert "DXF export backend is unavailable" in checked.stderr
