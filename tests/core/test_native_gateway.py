"""Cached native availability, missing DLL policy and parser instrumentation."""

# pylint: disable=protected-access

import importlib.util
import subprocess
import sys
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest

from app import native
from app.cli import main
from app.gcode.kernel.frontend import program as program_module
from app.gcode.kernel.frontend.program import _parse_program_python, parse_program, parser_statistics


def test_gateway_reports_availability_and_reason():
    for name, status in native.native_status().items():
        assert status["available"] == (native.extension(name).module is not None)
        assert status["available"] == getattr(native, "HAS_NATIVE_" + name.upper())
        assert status["available"] or status["reason"]


def test_import_failures_are_cached_with_reason(monkeypatch):
    calls = []

    def missing(name):
        calls.append(name)
        raise ImportError("DLL load failed")

    monkeypatch.setattr(native, "_extensions", {})
    monkeypatch.setattr(native.importlib, "import_module", missing)
    assert native.extension("parser").module is None
    assert "DLL load failed" in native.extension("parser").reason
    assert len(calls) == 1


def test_source_fallback_and_frozen_release_policy(monkeypatch):
    monkeypatch.setattr(
        native, "_extensions", {name: native.NativeExtension(None, "missing test extension") for name in native.MODULES}
    )
    monkeypatch.setattr(native.sys, "frozen", False, raising=False)
    source = "#1=2\nG1 X#1 F100\nM30\n"
    assert parse_program(source) == _parse_program_python(StringIO(source))
    stats = parser_statistics()
    assert (stats.total_blocks, stats.native_blocks, stats.fallback_blocks) == (3, 0, 3)
    native.require_packaged_native()
    monkeypatch.setattr(native.sys, "frozen", True)
    with pytest.raises(native.NativeRuntimeError, match="missing native extensions"):
        native.require_packaged_native()
    assert main(["--help"]) == 2


def test_native_parser_fallback_counter_matches_reference():
    if not native.HAS_NATIVE_PARSER:
        pytest.skip("Native parser is not present in this source environment")
    source = "G1 X1 F100\n#1=2\nG1 X#1\nM30\n"
    assert parse_program(source) == _parse_program_python(StringIO(source))
    stats = parser_statistics()
    assert stats.total_blocks == 4
    assert stats.native_blocks == 2
    assert stats.fallback_blocks == 2


def test_ordinary_gcode_has_no_native_fallback():
    if not native.HAS_NATIVE_PARSER:
        pytest.skip("Native parser is not present in this source environment")
    parse_program("G1 X1 Y2 F100\n" * 1000)
    stats = parser_statistics()
    assert (stats.total_blocks, stats.native_blocks, stats.fallback_blocks) == (1000, 1000, 0)


@pytest.mark.parametrize(
    "source",
    [
        "G1 X1\rG1 X2\rM30",
        "G1 X1\u2028G1 X2\u2028M30",
        "G18446744073709551616 X1\nM30",
        "N18446744073709551616 G1 X1\nM30",
    ],
)
def test_native_frontend_preserves_python_reference_for_unusual_source(source):
    assert parse_program(source) == _parse_program_python(source.splitlines(keepends=True))
    stats = parser_statistics()
    assert stats.native_blocks == 0
    assert stats.total_blocks == stats.fallback_blocks


@pytest.mark.parametrize(
    "source",
    ["", "G1 X1\nM30", "G1 X1\r\nM30", "G1 X1\r", "G1 X1\rM30"]
    + [f"G1 X1{separator}M30" for separator in "\v\f\x1c\x1d\x1e\x85\u2028\u2029"]
    + [f"N{digit * count} G1 X1" for digit in ("1", "\u0661", "\U0001d7d9") for count in (18, 19, 20)]
    + ["N" + "1" * 10 + "." + "1" * 10, "G1 X\u00b2", "(\u65e5\u672c\u8a9e) G1 X1"],
)
def test_compiled_source_guard_matches_reference(source):
    guard = native.native_symbol("parser", "requires_reference_source")
    if guard is None:
        pytest.skip("Compiled source guard is not installed")
    assert guard(source) == (program_module._REFERENCE_SOURCE.search(source) is not None)


def test_source_guard_works_with_older_native_extension(monkeypatch):
    monkeypatch.setitem(native._extensions, "parser", native.NativeExtension(ModuleType("older_parser"), None))
    assert program_module._requires_reference_source("N" + "1" * 19)
    assert not program_module._requires_reference_source("G1 X1\r\nM30")


@pytest.mark.parametrize("script", ["scripts/ps1/build.ps1", "scripts/sh/build.sh"])
def test_frozen_build_collects_dynamic_gateway_extensions(script):
    root = Path(__file__).resolve().parents[2]
    source = (root / script).read_text(encoding="utf-8")
    for module in native.MODULES.values():
        assert module in source
    assert source.count("--hidden-import") >= len(native.MODULES)


def test_fresh_kernel_import_keeps_installed_native_executor_available():
    if importlib.util.find_spec("app.gcode.kernel.milling._native_executor") is None:
        pytest.skip("Native executor is not installed in this source checkout")
    code = (
        "from app.gcode.kernel import execute; "
        "from app.native import native_status; "
        "from app.gcode.kernel.milling import executor; "
        "assert native_status()['executor']['available'], native_status(); "
        "assert executor._execute_simple_blocks is not None; "
        "assert execute('G1 X1 F100', language='fanuc_mill').ok"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
