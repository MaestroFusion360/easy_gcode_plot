"""Contracts for the modular ``app.gcode.export`` package and its aliases."""

from __future__ import annotations

# Alias identity is exercised with local imports inside the tests.
# pylint: disable=import-outside-toplevel
import importlib

import pytest

import app.gcode.export as export_pkg

LEGACY_REEXPORTS = [
    ("app.gcode.exporter", "ExportOptions"),
    ("app.gcode.exporter", "export_result"),
    ("app.gcode.exporter", "motion_line"),
    ("app.gcode.exporter", "export_full_program"),
    ("app.gcode.exporter", "export_full_mill_program"),
    ("app.gcode.exporter", "export_program"),
    ("app.gcode.exporter", "export_pgm"),
    ("app.gcode.exporter", "DXF_MODE"),
    ("app.gcode.exporter", "_window_export_options"),
    ("app.gcode.dxf_exporter", "RAPID_LAYER"),
    ("app.gcode.dxf_exporter", "CUT_LAYER"),
    ("app.gcode.dxf_exporter", "build_dxf_document"),
    ("app.gcode.dxf_exporter", "export_dxf"),
]


@pytest.mark.parametrize(("legacy_name", "attribute"), LEGACY_REEXPORTS)
def test_legacy_exporter_paths_resolve_to_canonical_objects(legacy_name, attribute):
    legacy = importlib.import_module(legacy_name)
    assert getattr(legacy, attribute) is getattr(export_pkg, attribute)


def test_legacy_package_attribute_access_matches_submodule_import():
    from app.gcode import dxf_exporter, exporter

    assert exporter.ExportOptions is export_pkg.ExportOptions
    assert dxf_exporter.export_dxf is export_pkg.export_dxf


def test_export_package_contains_only_three_paths_and_shared_helpers():
    from pathlib import Path

    from app.gcode.export import common, expanded, full

    folder = Path(export_pkg.__file__).parent
    assert {path.name for path in folder.glob("*.py")} == {
        "__init__.py",
        "common.py",
        "full.py",
        "expanded.py",
        "tool_numbers.py",
        "dxf.py",
    }
    assert {path.stem for path in (folder / "posts").glob("*.json")} == {
        "fanuc_mill",
        "fanuc_mill_multiaxis",
        "fanuc_lathe_a",
        "fanuc_lathe_b",
        "sinumerik_iso",
        "sinumerik_840d",
        "sinumerik_840d_multiaxis",
    }
    assert callable(common.motion_line)
    assert callable(full.normalize_full_program)
    assert callable(expanded.convert_resolved_program)


def test_dxf_import_is_lazy_for_gcode_only_callers():
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import app.gcode.export as export_pkg\n"
        "assert 'app.gcode.export.dxf' not in sys.modules\n"
        "assert callable(export_pkg.export_result)\n"
        "assert 'app.gcode.export.dxf' not in sys.modules\n"
        "assert callable(export_pkg.export_dxf)\n"
        "assert 'app.gcode.export.dxf' in sys.modules\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
