"""Native MPF subset, physical SUPA coordinates and real-program trace parity.

The fixtures are the user's paired CAM programs. FANUC rounds some geometry
to 0.001 mm and uses rapid for the final Z retract; those differences are explicit.
The C# SiemensModalResolver/LanguageSupportRegressionTests supply the reference
for WCS, tool, plane, compensation, message and radius-address semantics.
"""

from math import dist
from pathlib import Path

import pytest

from app.gcode.export.mill import export_full_mill_program
from app.gcode.export.options import ExportOptions
from app.gcode.export.trace import export_result
from app.gcode.export.validation import _motion_trace_signature
from app.gcode.kernel import execute
from app.gcode.program_execution import execute_program

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling"


def _native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def _end(motion):
    return motion.end_x, motion.end_y, motion.end_z


def test_paired_contour_programs_have_same_compensated_trace_with_cam_rounding():
    native, tools, _ = execute_program(
        (FIXTURES / "contur_2d_sin840d.mpf").read_text(), language="fanuc_mill", source_dialect="sinumerik"
    )
    fanuc, _, _ = execute_program((FIXTURES / "contur_2d.nc").read_text(), language="fanuc_mill")
    assert native.ok and native.complete and not native.diagnostics
    assert fanuc.ok and fanuc.complete and not fanuc.diagnostics
    assert tools["T3"]["diameter"] == 6
    assert len(native.motions) == 74
    assert len(fanuc.motions) == len(native.motions)
    assert fanuc.motions[-1].move == 0
    assert _end(fanuc.motions[-1]) == (-39, -28.4, 0)
    for index, (mpf, nc) in enumerate(zip(native.motions, fanuc.motions, strict=True)):
        if index == 72:
            # Actual fixtures differ in this one retract: G1 Z15 vs G0 Z15.
            assert (mpf.move, nc.move) == (1, 0)
            assert _end(mpf) == _end(nc) == (-39, -28.4, 15)
        else:
            assert (mpf.move, mpf.feed) == (nc.move, nc.feed)
        assert (mpf.plane, mpf.compensation_mode, mpf.compensation_applied, mpf.tool) == (
            nc.plane,
            nc.compensation_mode,
            nc.compensation_applied,
            nc.tool,
        )
        assert dist(_end(mpf), _end(nc)) <= 0.00051
        assert dist((mpf.start_x, mpf.start_y, mpf.start_z), (nc.start_x, nc.start_y, nc.start_z)) <= 0.00051
        assert bool(mpf.arc) == bool(nc.arc)
        if mpf.arc:
            assert mpf.arc.clockwise == nc.arc.clockwise
            assert dist(mpf.arc.center, nc.arc.center) <= 0.00051
            assert abs(mpf.arc.radius - nc.arc.radius) <= 0.00051
            assert abs(mpf.arc.sweep - nc.arc.sweep) <= 0.002
    assert any(m.compensation_applied and m.compensation_mode == 41 for m in native.motions)
    assert any(m.compensation_applied and m.compensation_mode == 42 for m in native.motions)


def test_native_trace_export_roundtrips_to_fanuc_geometry():
    native, _, _ = execute_program(
        (FIXTURES / "contur_2d_sin840d.mpf").read_text(), language="fanuc_mill", source_dialect="sinumerik"
    )
    nc = export_result(native, ExportOptions(include_execution_events=False, safety_line=True, delimiter=True))
    replay = execute(nc, language="fanuc_mill")
    assert replay.ok and replay.complete and not replay.diagnostics
    assert len(replay.motions) == len(native.motions)
    for source, target in zip(native.motions, replay.motions, strict=True):
        assert source.move == target.move
        assert dist(_end(source), _end(target)) < 0.000002
        if source.arc:
            assert target.arc is not None
            assert dist(source.arc.center, target.arc.center) < 0.000002
    assert "SUPA" not in nc and "CR=" not in nc and "WORKPIECE" not in nc


def test_supa_zero_means_machine_zero_even_with_nonzero_home_and_wcs():
    result = _native(
        "G710 G90 G54\nG0 X1 Y2 Z3\nG91\nG0 SUPA Z0 D0\nG90\nG1 Z4 F100\nM30",
        home_z=500,
        wcs_offsets={54: (10, 20, 100)},
    )
    assert result.ok and result.complete and not result.diagnostics
    supa = result.motions[-2]
    assert _end(supa) == (11, 22, 0)
    assert supa.source_kind == "supa"
    assert _end(result.motions[-1]) == (11, 22, 104)
    assert not any(event.kind == "HOME_RETURN" and event.source_block == 3 for event in result.events)
    nc = export_result(result, ExportOptions(safety_line=True, delimiter=True))
    replay = execute(nc, language="fanuc_mill", home_z=500, wcs_offsets={54: (10, 20, 100)})
    assert replay.ok and replay.complete and not replay.diagnostics
    assert [_end(m) for m in replay.motions] == [_end(m) for m in result.motions]


def test_native_metadata_cannot_generate_phantom_geometry():
    result = _native(
        'G0 X1\nMSG("IF THEN GOTO 100 X99")\nWORKPIECE(,"",,"BOX",112,0,-51,,50,25,-50,-25)\nG64\nG1 X2 F100\nM30'
    )
    assert result.ok and result.complete and not result.diagnostics
    assert [_end(m) for m in result.motions] == [(1, 0, 0), (2, 0, 0)]
    assert result.program.blocks[1].native_syntax.kind == "message"
    assert result.program.blocks[2].native_syntax.kind == "workpiece"


def test_cr_radius_and_major_arc_share_existing_arc_geometry():
    minor = _native("G17 G0 X0 Y0\nG2 X10 Y0 CR=10 F100\nM30")
    major = _native("G17 G0 X0 Y0\nG2 X10 Y0 CR=-10 F100\nM30")
    assert minor.ok and major.ok
    assert minor.motions[-1].arc.radius == major.motions[-1].arc.radius == 10
    assert minor.motions[-1].arc.sweep < 3.142 < major.motions[-1].arc.sweep
    assert ("CR", "10") in minor.instructions[1].words


def test_native_d_selects_and_cancels_modeled_edge_without_motion():
    result = _native("T3\nM6\nD1\nG0 X1\nD0\nM30")
    assert result.ok and not result.diagnostics
    assert len(result.motions) == 1
    assert ("G", 43.0) in result.execution_steps[2].words
    assert ("H", 1.0) in result.execution_steps[2].words
    assert ("G", 49.0) in result.execution_steps[4].words
    assert result.motions[0].tool == "T3"


@pytest.mark.parametrize("operation", ["G1 SUPA Z0", "G1 X10 CR=4", "G2 X10 CR=8 I1", "D2", 'MSG("ok") G0 X99'])
def test_unmodeled_native_forms_fail_closed(operation):
    result = _native(operation + "\nG0 X99")
    assert not result.ok and not result.complete
    assert result.diagnostics[0].status == "unsupported"
    assert not result.motions


def test_native_constructs_do_not_leak_into_iso_mode():
    result = _native("G710\nG291\nG2 X10 CR=10\nG0 X99")
    assert not result.ok and not result.complete
    assert result.diagnostics[0].line == 3
    assert not result.motions


def test_native_compensation_cannot_leak_through_mode_switch():
    result = _native("G41\nG291\nG0 X99")
    assert not result.ok and not result.complete
    assert result.diagnostics[0].line == 2
    assert not result.motions


def test_native_full_program_export_preserves_native_syntax():
    source = (FIXTURES / "contur_2d_sin840d.mpf").read_text()
    result, _, _ = execute_program(source, language="fanuc_mill", source_dialect="sinumerik")
    converted = export_full_mill_program(result, source.splitlines())
    assert "WORKPIECE(" in converted and "G710" in converted
    assert "G43" not in converted
    target, _, _ = execute_program(converted, language="fanuc_mill", source_dialect="sinumerik")
    assert target.ok and target.complete
    assert _motion_trace_signature(target) == _motion_trace_signature(result)
