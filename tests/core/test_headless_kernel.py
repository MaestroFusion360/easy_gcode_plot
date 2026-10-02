"""The public kernel must work when GUI bindings cannot be imported."""

import os
import subprocess
import sys
from pathlib import Path


def test_kernel_import_and_execution_without_qt(tmp_path):
    script = """
import importlib.abc
import sys

class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PyQt6', 'PySide6')) or fullname == 'app.settings':
            raise ImportError('GUI dependency forbidden: ' + fullname)
        return None

sys.meta_path.insert(0, NoQt())
from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import load_catalog, user_catalog_path
assert '4ax_table_b' in load_catalog()
assert user_catalog_path().parent.parent == __import__('pathlib').Path(sys.argv[1])
result = execute('G90 G0 B180\\nG0 Z20\\nG91 G28 Z0\\nM30',
                 language='fanuc_mill', kinematics='4ax_table_b', home_z=500)
assert result.ok and result.complete, result.diagnostics
assert abs(result.motions[-1].end_z + 500) < 1e-8
assert not any(name.startswith(('PyQt6', 'PySide6')) for name in sys.modules)
"""
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
