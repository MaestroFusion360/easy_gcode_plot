"""Three milling targets serialize evaluated geometry, not source constructs."""

import math

import pytest

from app.gcode.batch_export import export_directory
from app.gcode.export.options import ExportOptions
from app.gcode.export.resolved import MILLING_TARGETS, convert_resolved_program
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length

SOURCES = (
    ("fanuc", "#1=10\nT1 M6\nS500 M3\nG17 G0 X#1\nG3 X0 Y10 I-10 J0 F100\nG99 G84 X2 Y3 Z-9 R2 F625\nG80\nM9 M5 M30"),
    ("sinumerik", "G291\nT1 M6\nS500 M3\nG17 G0 X10\nG3 X0 Y10 I-10 J0 F100\nM9 M5 M30"),
    (
        "sinumerik",
        "R1=500\nT1 M6\nS=R1 M3\nG17 G0 X10\nG3 X0 Y10 Z-6 I=AC(0) J=AC(0) TURN=2 F100\n"
        "MCALL CYCLE84(5,0,2,-9,,0,3,,1.25,0,500,500)\nX2 Y3\nMCALL\nM9 M5 M30",
    ),
)


@pytest.mark.parametrize("target", MILLING_TARGETS)
@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_resolved_conversion_preserves_planes_units_dwell_and_feed(target, scale):
    source = "G1 X10 F100\nG4 F2\nG18 G3 X0 Z10 I=AC(0) K=AC(0) TURN=2\nG19 G3 Y10 Z0 J=AC(0) K=AC(0)\nM30"
    result = execute(source, language="fanuc_mill", source_dialect="sinumerik")
    assert result.ok
    output = convert_resolved_program(result, target, ExportOptions(output_unit_scale=scale))
    replay = execute(output, language="fanuc_mill", source_dialect="fanuc" if target == "fanuc_mill" else "sinumerik")
    assert replay.ok and replay.complete
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=0.001)
    assert {m.plane for m in replay.motions if m.arc} == {18, 19}
    assert all(m.feed == pytest.approx(100, abs=0.001) for m in replay.motions)
    assert (
        sum(signal.value for step in replay.execution_steps for signal in step.signals if signal.kind == "dwell") == 2
    )


@pytest.mark.parametrize("dialect,source", SOURCES)
@pytest.mark.parametrize("target", MILLING_TARGETS)
def test_resolved_conversion_matrix_preserves_geometry_and_machine_controls(dialect, source, target):
    result = execute(source, language="fanuc_mill", source_dialect=dialect)
    assert result.ok and result.complete
    output = convert_resolved_program(result, target)
    replay = execute(output, language="fanuc_mill", source_dialect="fanuc" if target == "fanuc_mill" else "sinumerik")
    assert replay.ok and replay.complete and not replay.diagnostics
    assert "MCALL" not in output and "#1" not in output and "R1=" not in output
    assert output.startswith("G291\n") == (target == "sinumerik_iso")
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=1e-5)
    assert (replay.motions[-1].end_x, replay.motions[-1].end_y, replay.motions[-1].end_z) == pytest.approx(
        (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z)
    )
    assert replay.motions[-1].tool == result.motions[-1].tool
    if target == "sinumerik_native" and "TURN=" in source:
        assert "TURN=2" in output
        assert max(m.arc.sweep for m in replay.motions if m.arc) > math.tau


@pytest.mark.parametrize("target", MILLING_TARGETS)
def test_resolved_targets_use_single_file_and_batch_service(tmp_path, target):
    source = tmp_path / "input"
    source.mkdir()
    path = source / "part.mpf"
    path.write_text(SOURCES[2][1])
    request = ExportRequest(language="fanuc_mill", mode="resolved", target_dialect=target)
    output = tmp_path / ("output.nc" if target == "fanuc_mill" else "output.mpf")
    result = export_file(path, output, request)
    assert result.execution.ok and result.output_size_bytes > 0
    replay = execute(
        output.read_text(), language="fanuc_mill", source_dialect="fanuc" if target == "fanuc_mill" else "sinumerik"
    )
    assert replay.ok and replay.complete
    exported = tmp_path / "batch"
    report = export_directory(source, exported, request)
    assert report["summary"]["exported"] == 1
    assert (exported / ("part.nc" if target == "fanuc_mill" else "part.mpf")).is_file()
