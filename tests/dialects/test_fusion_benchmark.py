"""Full, unmodified Fusion programs and controller cycle path regressions.

Sources: tmp/last/1001.nc and 1001.mpf supplied with the 1.9.8 bug report.
The local CPS posts define signatures; Siemens PGZ 11/2006 sections 2.1.6,
2.1.8-12 and FANUC B-63014EN/02 sections 13.1/13.2 define the movements.
"""

import math
from pathlib import Path

import pytest

from app.gcode.kernel import execute

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling"


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


@pytest.mark.parametrize("filename,dialect", [("1001.nc", "fanuc"), ("1001.mpf", "sinumerik")])
@pytest.mark.parametrize("home_z", [0, 500])
def test_entire_fusion_benchmark_reaches_m30(filename, dialect, home_z):
    source = (FIXTURES / dialect / f"fusion_benchmark_{filename}").read_text(encoding="utf-8-sig")
    result = execute(source, language="fanuc_mill", source_dialect=dialect, kinematics="5ax_table_ac", home_z=home_z)
    assert result.ok and result.complete, result.diagnostics
    assert not any(d.severity == "error" or d.status == "unsupported" for d in result.diagnostics)
    assert {d.code for d in result.diagnostics} <= {"NORMALIZED_SINUMERIK_DC", "UNVERIFIED_CUTTER_COMPENSATION"}
    assert result.events[-1].kind == "program_end"
    assert result.program.blocks[result.execution_steps[-1].source_block].raw.strip() == "M30"
    operations = [e for e in result.events if e.drilling]
    required = {"G74", "G76", "G87"} if dialect == "fanuc" else {"CYCLE84", "CYCLE85", "CYCLE86", "CYCLE87", "CYCLE89"}
    assert required <= {e.code for e in operations}
    assert any(e.kind == "TCP_CONTROL_ON" for e in result.events)
    assert any(m.source_block > 1800 and m.move == 1 and m.tool_orientation is not None for m in result.motions)
    assert all(
        math.isfinite(v) for m in result.motions for v in (m.start_x, m.start_y, m.start_z, m.end_x, m.end_y, m.end_z)
    )


@pytest.mark.parametrize("code", [74, 84])
@pytest.mark.parametrize("full_retract", [False, True])
def test_fanuc_tapping_q_is_synchronized_and_resets_on_g80(code, full_retract):
    source = f"G90 G0 Z10\nS500 M3\nM29 S500\nG98 G{code} X2 Z-5 R1 Q2 F500\nX3\nG80\nG{code} X4 Z-5 R1 F500\nG80\nM30"
    result = execute(
        source, "fanuc_mill", milling_tapping_retract_distance=0.5, milling_tapping_full_retract=full_retract
    )
    assert result.ok and result.complete, result.diagnostics
    for x in (2, 3):
        cuts = [m for m in result.motions if m.move == 1 and m.end_x == x]
        assert [m.end_z for m in cuts if m.end_z < m.start_z] == [-1, -3, -5]
        assert [m.end_z for m in cuts if m.end_z > m.start_z] == ([1, 1, 1] if full_retract else [-0.5, -2.5, 1])
        assert all(m.feed == 500 for m in cuts)
    assert len([m for m in result.motions if m.move == 1 and m.end_x == 4]) == 2


@pytest.mark.parametrize("code", [76, 87])
@pytest.mark.parametrize("direction", [(-1, 0, 0), (0, 1, 0)])
def test_fanuc_fine_and_back_boring_use_real_q_shift_and_return(code, direction):
    depth, rplane = (-10, 2) if code == 76 else (-8, -10)
    result = execute(
        f"G90 G0 X5 Y6 Z20\nF100\nG99 G{code} X5 Y6 Z{depth} R{rplane} Q0.2 P250\nG80\nG1 X7\nM30",
        "fanuc_mill",
        milling_boring_shift_direction=direction,
    )
    assert result.ok and result.complete, result.diagnostics
    motions = [m for m in result.motions if m.cycle_generated]
    cuts = [m for m in motions if m.move == 1]
    assert len(cuts) == 1
    assert (cuts[0].start_z, cuts[0].end_z) == (rplane, depth)
    assert cuts[0].feed == 100
    assert any((m.end_x, m.end_y) == pytest.approx((5 + direction[0] * 0.2, 6 + direction[1] * 0.2)) for m in motions)
    assert (motions[-1].end_x, motions[-1].end_y, motions[-1].end_z) == (5, 6, 20 if code == 87 else 2)
    assert result.motions[-1].start_x == 5
    assert sum(s.kind == "spindle_orient" for s in result.signals) == (2 if code == 87 else 1)


def test_sinumerik_reaming_separate_return_feed_survives_tilted_frame():
    source = (
        'G90 G0 Z10\nS500 M3\nCYCLE800(0,"",0,27,0,0,0,0,0,180,0,0,0,0,,0)\n'
        "MCALL CYCLE85(5,0,2,-8,,.2,100,250,0,0,0)\nX2 Y3\nMCALL\nM30"
    )
    result = native(source, kinematics="5ax_table_ac")
    assert result.ok and result.complete, result.diagnostics
    cuts = [m for m in result.motions if m.move == 1]
    assert [m.feed for m in cuts] == [100, 250]
    # In this frame the working stroke travels upwards in display Z.
    assert cuts[0].end_z > cuts[0].start_z


def test_sinumerik_tapping_balances_final_pecks_and_keeps_modal_feed():
    source = (
        "G0 Z10\nF17\nS500 M3\n"
        "MCALL CYCLE84(5,0,2,-10,,0,3,,1,0,500,500,0,1,,1,3,.5,,,,0,0,1001002)\nX2\nMCALL\nG1 X3\nM30"
    )
    result = native(source)
    assert result.ok and result.complete, result.diagnostics
    cuts = [m for m in result.motions if m.move == 1 and m.cycle_generated]
    assert [m.end_z for m in cuts if m.end_z < m.start_z] == [-3, -6, -8, -10]
    assert [m.end_z for m in cuts if m.end_z > m.start_z] == [-2.5, -5.5, -7.5, 2]
    assert all(m.feed == 500 for m in cuts)
    assert result.motions[-1].feed == 17


def test_sinumerik_fine_boring_keeps_all_three_shift_components():
    result = native("G0 Z20\nF100\nMCALL CYCLE86(10,0,2,-8,,.5,3,-.2,.3,1,45)\nX5 Y6\nMCALL\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert any((m.end_x, m.end_y, m.end_z) == pytest.approx((4.8, 6.3, -7)) for m in result.motions)
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == (5, 6, 10)
    assert any(s.kind == "spindle_orient" and s.value == 45 for s in result.signals)


@pytest.mark.parametrize("angle,expected", [(-90, -90), (450, 90), (-315, 45)])
def test_signed_and_unwrapped_dc_targets_are_normalized_with_source_warning(angle, expected):
    result = native(f"G0 C=DC({angle})\nM30", kinematics="5ax_table_ac")
    assert result.ok and result.complete, result.diagnostics
    assert dict(result.rotary_angles)["C"] == expected
    assert result.diagnostics[0].code == "NORMALIZED_SINUMERIK_DC"
    assert result.diagnostics[0].line == 1


def test_g92_1_presets_without_moving_or_resetting_physical_rotary_angle():
    result = execute("G90 G0 C720\nG0 X5 Y6 Z10\nG92.1 C0\nG1 X7 F100\nM30", "fanuc_mill", kinematics="5ax_table_ac")
    assert result.ok and result.complete, result.diagnostics
    preset = result.execution_steps[2]
    assert preset.emitted_count == 0
    assert dict(preset.rotary_angles)["C"] == 720
    assert any(e.kind == "COORDINATE_SYSTEM_PRESET" for e in preset.events)


def test_unknown_position_recovery_updates_previously_recovered_axes():
    result = execute(
        "G90 G0 X0 Y0 Z10\nG75 X25 Y-8 Z-16\nG0 X25\nG0 Z15\nG0 X30 Y-8\nG3 X31 I.5 F100\nM30", "fanuc_mill"
    )
    assert [d.code for d in result.diagnostics] == ["UNSUPPORTED_G_CODE"]
    assert result.complete
    arc = next(m for m in result.motions if m.move == 3)
    assert (arc.start_x, arc.start_y, arc.start_z) == (30, -8, 15)


def test_bad_arc_diagnostic_does_not_stop_execution_of_later_blocks():
    result = execute("G90 G0 X1\nG3 X0 Y2 I-1 J0 F100\nG1 X5\nM30", "fanuc_mill")
    assert not result.ok and result.complete
    assert [d.code for d in result.diagnostics] == ["INVALID_GEOMETRY"]
    assert result.motions[-1].end_x == 5
    assert result.events[-1].kind == "program_end"


def test_native_circle_plane_is_local_and_does_not_change_modal_helix_plane():
    result = native("G17 G90 G0 X0 Y0 Z0\nG2 X1 Z1 I1 K0 F100\nG0 X1 Y0 Z1\nG3 X0 Y1 Z2 I-1 J0 TURN=1\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert [m.plane for m in result.motions if m.move in (2, 3)] == [18, 17]
