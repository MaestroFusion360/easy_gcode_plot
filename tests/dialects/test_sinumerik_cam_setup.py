"""Real CAM header, named parameters, spindle/tool selection and native TCP."""

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.frontend.sinumerik import parse_sinumerik_program


def native(source, profile="5ax_table_ac_angled", **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile, **options)


def test_real_declarations_assignments_and_case_insensitive_references():
    source = "DEF REAL _x_home, _Z_HOME\n_X_HOME=12 _z_home=-10\nG710 G90\nSUPA G0 X=_x_home Z=_Z_HOME\nM30"
    result = native(source)
    assert result.ok and result.complete, result.diagnostics
    assert len(result.motions) == 1
    assert (result.motions[0].end_x, result.motions[0].end_z) == (12, -10)
    assert result.program.blocks[0].raw == source.splitlines()[0]
    assert result.program.ast.nodes[0].native_syntax.real_declarations == ("_X_HOME", "_Z_HOME")


@pytest.mark.parametrize("profile,axis", [("5ax_table_ac_angled", "A"), ("5ax_table_bc_angled", "B")])
def test_supa_rotary_only_returns_to_absolute_machine_zero_under_g91(profile, axis):
    result = native(f"G0 {axis}30 C20\nG91\nSUPA G0 {axis}0 C0 D0\nM30", profile=profile)
    assert result.ok and result.complete, result.diagnostics
    assert dict(result.rotary_angles)[axis] == dict(result.rotary_angles)["C"] == 0
    assert len([event for event in result.events if event.kind == "ROTARY_INDEX"]) == 2
    assert not result.motions


def test_supa_mixed_linear_and_rotary_machine_targets_ignore_g91_and_offsets():
    result = native(
        "G0 B30 C20\nG91\nSUPA G0 X12 Z5 B0 C=DC(10) D0\nM30",
        profile="5ax_table_bc_angled",
        wcs_offsets={54: (100, 200, 300)},
    )
    assert result.ok and result.complete, result.diagnostics
    assert dict(result.rotary_angles)["B"] == 0
    assert dict(result.rotary_angles)["C"] == 10
    assert result.motions[-1].source_kind == "supa"


@pytest.mark.parametrize(
    "source,profile,code",
    [
        ("SUPA G0 B0 C0 D0", None, "ROTARY_KINEMATICS_REQUIRED"),
        ("SUPA G0 A0 C0 D0", "5ax_table_bc_angled", "UNCONFIGURED_ROTARY_AXIS"),
        ("SUPA G1 B0 C0 D0", "5ax_table_bc_angled", "UNSUPPORTED_SINUMERIK_SUPA"),
        ("SUPA G0 B=IC(10)", "5ax_table_bc_angled", "UNSUPPORTED_SINUMERIK_ROTARY"),
    ],
)
def test_supa_rotary_boundaries_are_validated_even_for_unchanged_zero_axes(source, profile, code):
    result = native(source, profile=profile)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert all(value == 0 for value in dict(result.rotary_angles).values())


def test_real_variables_default_to_zero_and_can_copy_numeric_r_and_named_values():
    result = native("DEF REAL _a, _b\nR11=25\nG0 X=_a\n_a=R11 _b=_a\nG1 X=_b F100\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert result.motions[-1].end_x == 25


@pytest.mark.parametrize(
    "source,code",
    [
        ("G0 X=_unknown", "UNDEFINED_SINUMERIK_VARIABLE"),
        ("_unknown=1", "UNDEFINED_SINUMERIK_VARIABLE"),
        ("DEF REAL _a,_a", "DUPLICATE_SINUMERIK_VARIABLE"),
        ("DEF REAL _a\nDEF REAL _A", "DUPLICATE_SINUMERIK_VARIABLE"),
        ("DEF REAL _a\n_a=R99", "UNDEFINED_SINUMERIK_PARAMETER"),
        ("DEF REAL _a\n_a=1+2", "UNSUPPORTED_SINUMERIK_MODE"),
        ("DEF REAL _a[2]", "UNSUPPORTED_SINUMERIK_MODE"),
        ("DEF INT _a", "UNSUPPORTED_SINUMERIK_MODE"),
        ('T="A" T="B" M6', "UNSUPPORTED_SINUMERIK_MODE"),
        ('T="A" T2 M6', "UNSUPPORTED_SINUMERIK_MODE"),
        ("SETMS(2)", "UNSUPPORTED_SINUMERIK_MODE"),
        ("FLIN", "UNSUPPORTED_SINUMERIK_MODE"),
    ],
)
def test_unsupported_cam_constructs_remain_explicit_errors(source, code):
    result = native(source)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert not result.motions


def test_cycle832_is_explicitly_ignored_without_geometry_or_events():
    result = native("G0 X10\nCYCLE832(_unused,1,1)\nG1 X20 F100\nCYCLE832()\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert len(result.motions) == 2
    assert all(e.source_block not in (1, 3) for e in result.events)
    assert all(s.emitted_count == 0 for s in result.execution_steps if s.source_block in (1, 3))
    failed = native("CYCLE832(1+2,1,1)")
    assert not failed.ok


def test_named_tool_selection_is_delayed_until_m6_and_t0_unloads():
    result = native('T="UGT0202_001"\nM6\nG0 X1\nT="NextTool"\nG1 X2 F100\nM6\nG1 X3\nT0\nM6\nG0 X4\nM30')
    assert result.ok and not result.diagnostics, result.diagnostics
    assert [m.tool for m in result.motions] == ["UGT0202_001", "UGT0202_001", "NextTool", None]
    assert [e.tool for e in result.events if e.kind == "tool_change"] == ["UGT0202_001", "NextTool", None]


@pytest.mark.parametrize("distance", ["G90", "G91"])
def test_dc_uses_shortest_absolute_target_independently_of_distance_mode(distance):
    result = native(f"G90 G0 C350\nTRAORI\n{distance}\nR11=10\nG1 C=DC(R11) F100\nC=DC(350)\nTRAFOOF\nM30")
    assert result.ok, result.diagnostics
    events = [e for e in result.events if e.kind == "ROTARY_MOTION"]
    assert [e.new_abc[2] for e in events] == [370, 350]
    assert parse_sinumerik_program("C=DC(R11)").blocks[0].native_syntax.direct_rotary == ("C",)


@pytest.mark.parametrize(
    "source,code",
    [
        ("G0 C=DC(-1)", "INVALID_SINUMERIK_DC"),
        ("G0 C=DC(361)", "INVALID_SINUMERIK_DC"),
        ("G0 C=DC(180)", "UNSUPPORTED_SINUMERIK_DC_TIE"),
        ("G0 B=DC(10)", "UNCONFIGURED_ROTARY_AXIS"),
        ("G0 C=DC(10) C=IC(20)", "UNSUPPORTED_SINUMERIK_MODE"),
    ],
)
def test_dc_invalid_or_ambiguous_targets_fail_before_rotary_mutation(source, code):
    result = native(source)
    assert not result.ok
    assert result.diagnostics[-1].code == code
    assert dict(result.rotary_angles)["C"] == 0


@pytest.mark.parametrize("edge", [0, 1, 2, 12])
def test_d_edge_selection_does_not_cancel_tcp(edge):
    result = native(f"TRAORI\nG0 X10 Y0 Z5 A10 C=DC(278) D{edge}\nG1 X0 Y10 Z0 A20 C=DC(277) F100\nTRAFOOF\nM30")
    assert result.ok, result.diagnostics
    assert not any(e.kind == "TCP_CONTROL_OFF" and e.source_block == 1 for e in result.events)
    assert dict(result.rotary_angles)["C"] == -83
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == (0, 10, 0)


def test_supplied_bc_impeller_finishes_without_skipping_cam_header(fixture_text):
    result = native(fixture_text("milling/sinumerik/impeller.mpf"), profile="5ax_table_bc_angled", home_z=300)
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert len(result.motions) == 5469
    assert {d.code for d in result.diagnostics} == {"UNMODELED_SINUMERIK_NATIVE"}
    assert {motion.tool for motion in result.motions if motion.tool} == {"T60"}
    assert any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events)
    assert any(event.kind == "TCP_CONTROL_ON" for event in result.events)
    assert dict(result.rotary_angles)["B"] == dict(result.rotary_angles)["C"] == 0


@pytest.mark.parametrize("command", ["TRANS", "TRANS X10", "AROT Z90", "FGROUP(X,Y,Z)"])
def test_unmodeled_frame_commands_warn_without_blocking_execution(command):
    result = native(f"G0 X1\n{command}\nG1 X2 F100\nM30")
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert [motion.end_x for motion in result.motions] == [1, 2]
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "UNMODELED_SINUMERIK_NATIVE"
    assert diagnostic.severity == "warning"
    assert diagnostic.line == 2


def test_compact_cam_fixture_finishes_static_tcp_drilling_and_home_sections(fixture_text):
    result = native(fixture_text("milling/sinumerik/sinumerik_cam_setup.mpf"))
    assert result.ok and result.complete and not result.diagnostics, result.diagnostics
    assert any(m.arc is not None for m in result.motions)
    assert any(m.source_kind == "cycle" for m in result.motions)
    assert any(m.source_kind == "supa" and m.end_z == -10 for m in result.motions)
    assert result.execution_steps[-1].source_block == len(result.program.blocks) - 1


def test_supplied_full_cam_program_reaches_m30_without_suppressing_compensation_warning(fixture_text):
    result = native(fixture_text("milling/sinumerik/5ax_test.mpf"))
    assert result.ok and result.complete, result.diagnostics
    # Machine-home edits may add or remove zero-length SUPA returns.
    assert sum(motion.source_kind != "supa" for motion in result.motions) == 4950
    first_arc = next(m.arc for m in result.motions if m.arc is not None)
    assert first_arc.radius == pytest.approx(11.500224084773304)
    assert len(result.execution_steps) == len(result.program.blocks) == 5232
    assert [d.code for d in result.diagnostics] == ["UNVERIFIED_CUTTER_COMPENSATION"]


@pytest.mark.parametrize("distance", ["G90 X0 Y10", "G91 X-10 Y10"])
@pytest.mark.parametrize("legacy", [1, 2, 3])
def test_native_ijk_defaults_relative_independently_of_gui_and_distance_mode(distance, legacy):
    result = native(f"G0 X10 Y0\nG3 {distance} I-10 J0 F100\nM30", source_arc_type=legacy)
    assert result.ok and result.complete, result.diagnostics
    arc = result.motions[-1].arc
    assert arc.center == (0, 0, 0)
    assert arc.radius == 10


def test_native_absolute_center_can_mix_with_incremental_addresses():
    result = native("G0 X10 Y5\nG3 X0 Y15 I=AC(0) J0 F100\nM30")
    assert result.ok, result.diagnostics
    assert result.motions[-1].arc.center == (0, 5, 0)
    assert result.motions[-1].arc.radius == 10
