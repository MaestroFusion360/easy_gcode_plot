"""Cached native availability, missing DLL policy and parser instrumentation."""

from io import StringIO
from pathlib import Path

import pytest

from app import native
from app.cli import main
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


@pytest.mark.parametrize("script", ["scripts/ps1/build.ps1", "scripts/sh/build.sh"])
def test_frozen_build_collects_dynamic_gateway_extensions(script):
    root = Path(__file__).resolve().parents[2]
    source = (root / script).read_text(encoding="utf-8")
    for module in native.MODULES.values():
        assert module in source
    assert source.count("--hidden-import") >= len(native.MODULES)
