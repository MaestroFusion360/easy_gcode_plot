"""Documented CYCLE800 matrices and shared TWP/TCP behavior."""

import math

import pytest

from app.cli import main
from app.gcode.batch import analyze_directory
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.sinumerik import parse_sinumerik_program
from app.gcode.kernel.milling.kinematics import transform_vector
from app.gcode.kernel.milling.twp import euler_zxz


def native(source, profile="5ax_table_ac_angled"):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics=profile)


def cycle(mode=57, angles=(-15, 0, 0), origin=(0, 0, 50), after=(0, 0, 0), st=200000, direction=1, tc="TISCH"):
    args = (2, f'"{tc}"', st, mode, *origin, *angles, *after, direction, "", 1)
    return f"CYCLE800({','.join(map(str, args))})"


@pytest.mark.parametrize(
    "mode,angles,zxz",
    [
        (57, (-15, 0, 0), (0, -15, 0)),
        (54, (7, 0, 0), (90, 7, -90)),
        (39, (-45, 54.365, 0), (-45, 54.365, 0)),
        (39, (45, 54.365, 0), (45, 54.365, 0)),
        (27, (13, 0, 0), (13, 0, 0)),
        (30, (13, 0, 0), (90, 13, -90)),
        (45, (13, 0, 0), (0, 13, 0)),
    ],
)
def test_documented_examples_build_independent_siemens_matrices(mode, angles, zxz):
    source = cycle(mode, angles)
    result = native(source + "\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert not result.motions
    on = next(e for e in result.events if e.kind == "TILTED_WORK_PLANE_ON")
    for got, expected in zip(on.twp_orientation, euler_zxz(*zxz), strict=True):
        assert got == pytest.approx(expected)
    assert on.twp_origin == (0, 0, 50)
    assert result.source_dialect == "sinumerik"
    assert result.program.blocks[0].raw == source
    assert {e.kind for e in result.events} >= {"TOOL_AXIS_ORIENT", "ROTARY_INDEX"}


def test_parser_preserves_string_blanks_r_references_and_ast():
    source = cycle(angles=("R1", 0, 0))
    program = parse_sinumerik_program(source)
    syntax = program.blocks[0].native_syntax
    assert syntax.kind == "swivel"
    assert len(syntax.cycle_args) == 16
    assert syntax.cycle_args[1] == '"TISCH"'
    assert syntax.cycle_args[7] == "R1"
    assert syntax.cycle_args[14] == ""
    assert program.ast.nodes[0].native_syntax == syntax
    result = native("R1=-15\n" + source)
    assert result.ok, result.diagnostics


@pytest.mark.parametrize("profile", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_cimco_classic_14_argument_normal_plane_matches_extended_call(profile):
    command = 'N22 CYCLE800(0, "", 0, 57, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1)'
    syntax = parse_sinumerik_program(command).blocks[0].native_syntax
    assert syntax.kind == "swivel"
    assert syntax.cycle_args[13:] == ("-1", "", "")
    classic = native(command + "\nG0 X75.575 Y-73.008 Z72.881\nM30", profile)
    extended = native(command[:-1] + ",,0)\nG0 X75.575 Y-73.008 Z72.881\nM30", profile)
    assert classic.ok and classic.complete, classic.diagnostics
    assert not classic.diagnostics
    assert classic.motions == extended.motions
    on = next(event for event in classic.events if event.kind == "TILTED_WORK_PLANE_ON")
    assert on.twp_origin == (0, 0, 0)
    assert on.twp_orientation == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_classic_swivel_new_and_additive_frames_match_documented_offsets():
    # Siemens Tool and Mold Making 08/2007, p. 71: ST0=new, ST1=additive.
    source = 'CYCLE800(0,"",0,57,0,25,0,-15,0,0,0,0,0,-1)\n'
    source += 'CYCLE800(0,"",1,57,8,0,0,0,-8,0,0,0,0,-1)\nG0 X1 Y2 Z3\nM30'
    modern = source.replace(",0,57,", ",200000,57,").replace(",1,57,", ",200001,57,")
    classic, extended = native(source), native(modern)
    assert classic.ok and classic.complete, classic.diagnostics
    assert extended.ok and extended.complete, extended.diagnostics
    assert classic.motions == extended.motions
    frames = [event for event in classic.events if event.kind == "TILTED_WORK_PLANE_ON"]
    assert frames[0].twp_origin == (0, 25, 0)
    assert frames[1].twp_origin == pytest.approx((8, 25, 0))


def test_classic_swivel_still_requires_kinematics_and_an_existing_additive_frame():
    normal = 'CYCLE800(0,"",0,57,0,0,0,0,0,0,0,0,0,-1)'
    assert native(normal, None).diagnostics[-1].code == "TWP_KINEMATICS_REQUIRED"
    additive = native(normal.replace(",0,57,", ",1,57,"))
    assert additive.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_CYCLE800"


def test_post_rotation_offset_and_additive_frame_composition():
    first = cycle(direction=0, after=(0, 10, 0))
    second = cycle(54, (7, 0, 0), (35, -24, 0), st=200001, direction=0)
    result = native(first + "\n" + second)
    assert result.ok, result.diagnostics
    frames = [e for e in result.events if e.kind == "TILTED_WORK_PLANE_ON"]
    c, s = math.cos(math.radians(15)), math.sin(math.radians(15))
    assert frames[0].twp_origin == pytest.approx((0, 10 * c, 50 - 10 * s))
    assert frames[1].twp_origin == pytest.approx((35, -14 * c, 50 + 14 * s))
    normal = transform_vector(frames[1].twp_orientation, (0, 0, 1))
    assert normal == pytest.approx(
        (math.sin(math.radians(7)), s * math.cos(math.radians(7)), c * math.cos(math.radians(7)))
    )


def test_frame_only_status_does_not_index_even_with_nonzero_direction():
    result = native("G0 A10 C20\n" + cycle(st=220000, direction=1) + "\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert dict(result.rotary_angles)["A"] == 10
    assert dict(result.rotary_angles)["C"] == 20
    assert any(event.kind == "TILTED_WORK_PLANE_ON" for event in result.events)
    assert len([event for event in result.events if event.kind == "ROTARY_INDEX"]) == 1


def test_frame_only_additive_status_composes_without_reindexing():
    result = native(cycle(st=220000, direction=0) + "\n" + cycle(st=220001, direction=1) + "\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert len([event for event in result.events if event.kind == "TILTED_WORK_PLANE_ON"]) == 2
    assert not any(event.kind == "ROTARY_INDEX" for event in result.events)


@pytest.mark.parametrize("command", ["G0 A0 C=DC(0)", "G91 G0 A0 C0", "G91 G0 A=IC(0) C=DC(0)"])
def test_fusion_repeated_rotary_targets_preserve_native_normal_frame(command):
    frame = 'CYCLE800(0,"",0,27,0,0,0,0,0,0,0,0,0,1,,0)'
    prefix = "G90\nG0 A0 C=DC(0)\n" + frame + "\nG0 X10 Y20 Z15\n"
    reference = native(prefix + "G0\nG90 G1 X12 F100\nM30", "5ax_table_ac")
    result = native(prefix + command + "\nG90 G1 X12 F100\nM30", "5ax_table_ac")
    assert result.ok and result.complete, result.diagnostics
    assert result.motions == reference.motions
    assert result.rotary_angles == reference.rotary_angles
    assert result.events == reference.events
    assert result.execution_steps[4].twp_orientation == result.execution_steps[3].twp_orientation


@pytest.mark.parametrize("command", ["G90 G0 A10 C20", "G91 G0 A0 C0", "G91 G0 C=DC(20)"])
def test_repeated_rotary_targets_preserve_nonzero_native_frame(command):
    prefix = "G0 A10 C20\n" + cycle(st=220000, direction=0) + "\nG0 X1 Y2 Z3\n"
    reference = native(prefix + "G0\nG90 G1 X4 F100\nM30")
    result = native(prefix + command + "\nG90 G1 X4 F100\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert result.motions == reference.motions
    assert result.rotary_angles == reference.rotary_angles


def test_pure_rapid_rotary_index_preserves_native_frame():
    result = native(cycle(st=220000, direction=0) + "\nG0 A10")
    assert result.ok and result.complete and not result.diagnostics
    assert dict(result.rotary_angles)["A"] == 10
    assert result.execution_steps[-1].twp_orientation is not None
    assert any(event.kind == "ROTARY_INDEX" for event in result.events)


@pytest.mark.parametrize("profile,st", [("5ax_table_ac_angled", 220000), ("5ax_table_bc_angled", 200000)])
def test_dmg_dataset_rejects_other_profiles_and_oem_indexing(profile, st):
    source = f'CYCLE800(0,"DMG",{st},39,0,0,0,-32,52,0,0,0,0,0,0)'
    result = native(source, profile)
    assert not result.ok
    assert result.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_CYCLE800"


@pytest.mark.parametrize("reset", ["CYCLE800()", "CYCLE800", cycle(angles=(0, 0, 0), origin=(0, 0, 0), tc="0")])
def test_reset_preserves_displayed_tip_and_emits_no_motion(reset):
    result = native(cycle() + "\nG0 X1 Y2 Z3\n" + reset + "\nG0\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert len(result.motions) == 1
    assert result.execution_steps[2].position == pytest.approx(result.execution_steps[1].position)
    assert result.execution_steps[2].twp_orientation is None
    assert any(e.kind == "TILTED_WORK_PLANE_OFF" for e in result.events)


@pytest.mark.parametrize("profile", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_native_and_fanuc_tilted_frame_geometry_and_rebase_match(profile):
    fanuc = execute(
        "G21 G90\nG68.2 X0 Y0 Z50 I0 J-15 K0\nG53.1\nG0 X1 Y2 Z3\nG69\nG0 X4 Y5 Z6\nM30",
        language="fanuc_mill",
        kinematics=profile,
    )
    siemens = native("G710 G90\n" + cycle(direction=-1) + "\nG0 X1 Y2 Z3\nCYCLE800()\nG0 X4 Y5 Z6\nM30", profile)
    assert fanuc.ok and siemens.ok, (fanuc.diagnostics, siemens.diagnostics)
    for a, b in zip(fanuc.motions, siemens.motions, strict=True):
        assert (a.start_x, a.start_y, a.start_z, a.end_x, a.end_y, a.end_z) == pytest.approx(
            (b.start_x, b.start_y, b.start_z, b.end_x, b.end_y, b.end_z)
        )
        for x, y in zip(a.tool_orientation, b.tool_orientation, strict=True):
            assert x == pytest.approx(y, abs=1e-6)


@pytest.mark.parametrize(
    "source,profile,code",
    [
        (cycle(), None, "TWP_KINEMATICS_REQUIRED"),
        (cycle(mode=121), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        (cycle(st=200010), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        (cycle(direction=2), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        (cycle(tc="UNKNOWN"), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        (cycle(st=200001), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        ("TRAORI\n" + cycle(), "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_CYCLE800"),
        (cycle() + "\nG291", "5ax_table_ac_angled", "UNSUPPORTED_SINUMERIK_MODE"),
        (cycle() + "\nTRAORI", "5ax_table_ac_angled", "UNSUPPORTED_TCP_COMPOSITION"),
        (cycle(angles=(120, 0, 0)), "5ax_table_ac_angled", "TWP_ORIENTATION_UNREACHABLE"),
    ],
)
def test_unsupported_options_and_state_transitions_fail_closed(source, profile, code):
    result = native(source, profile)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert not result.motions


@pytest.mark.parametrize("mode", ["G90", "G91"])
def test_ic_is_incremental_independent_of_distance_mode(mode):
    result = native(f"G710 G90\nG0 C=20\nTRAORI\n{mode}\nR11=90\nG1 C=IC(R11) F100\nC=IC(90)\nTRAFOOF\nM30")
    assert result.ok, result.diagnostics
    assert dict(result.rotary_angles)["C"] == pytest.approx(200)
    rotary = [e for e in result.events if e.kind == "ROTARY_MOTION"]
    assert [e.new_abc[2] for e in rotary] == [110, 200]


def test_primer_tcp_arc_with_incremental_c_keeps_analytical_circle():
    result = native("G710 G90 G17\nG0 X-55 Y70\nTRAORI\nG3 X-70 Y55 CR=25 C=IC(90) F300\nTRAFOOF\nM30")
    assert result.ok and result.complete, result.diagnostics
    arc = result.motions[-1]
    assert arc.arc.radius == pytest.approx(25)
    assert (arc.end_x, arc.end_y, arc.end_z) == pytest.approx((-70, 55, 0))
    assert arc.start_tool_orientation != arc.tool_orientation


def test_documented_compatibility_reset_and_retract_metadata():
    result = native(cycle() + '\nCYCLE800(0,"0",110000,57,,,,0,0,0,,,,0,,0)')
    assert result.ok, result.diagnostics
    assert not result.motions
    assert [e.code for e in result.events if e.kind == "MACHINE_RETRACT_REQUEST"] == ["CYCLE800_FR2"]
    assert result.execution_steps[-1].twp_orientation is None


@pytest.mark.parametrize("mode", ["expanded", "full", "resolved"])
def test_fixture_executes_and_export_stays_closed(fixture_text, tmp_path, mode):
    source = fixture_text("milling/sinumerik/sinumerik_cycle800.mpf")
    result = native(source)
    assert result.ok and result.complete, result.diagnostics
    path = tmp_path / "native.mpf"
    path.write_text(source, encoding="utf8")
    destination = tmp_path / "converted.nc"
    request = ExportRequest(language="fanuc_mill", kinematics="5ax_table_ac_angled", mode=mode)
    if mode == "full":
        outcome = export_file(path, destination, request)
        assert outcome.execution.ok and destination.exists()
        assert "CYCLE800" in destination.read_text()
        return
    try:
        outcome = export_file(path, destination, request)
    except ValueError:
        pass
    else:
        assert not outcome.execution.ok
    assert not destination.exists()


@pytest.mark.parametrize(
    "command,code",
    [
        ("G0 B=IC(90)", "UNCONFIGURED_ROTARY_AXIS"),
        ("G0 C=IC(R99)", "UNDEFINED_SINUMERIK_PARAMETER"),
        ("G28 C=IC(90)", "UNSUPPORTED_SINUMERIK_ROTARY"),
        ("G0 C=IC(90) C=1", "UNSUPPORTED_SINUMERIK_MODE"),
        ("G0 C=IC(90) C=IC(90)", "UNSUPPORTED_SINUMERIK_MODE"),
        ("G0 C=DC(R11)", "UNDEFINED_SINUMERIK_PARAMETER"),
    ],
)
def test_incremental_rotary_errors_remain_controlled(command, code):
    result = native(command)
    assert not result.ok
    assert result.diagnostics[-1].code == code
    assert dict(result.rotary_angles)["C"] == 0


def test_cycle800_reaches_cli_and_batch_consumers(fixture_text, tmp_path):
    path = tmp_path / "swivel.mpf"
    path.write_text(fixture_text("milling/sinumerik/sinumerik_cycle800.mpf"), encoding="utf8")
    args = [str(path), "--lang", "fanuc_mill", "--kinematics", "5ax_table_ac_angled"]
    assert main(["trace", *args, "-o", str(tmp_path / "trace.json")]) == 0
    assert main(["analyze", *args]) == 0
    report = analyze_directory(
        tmp_path, language="fanuc_mill", encoding="utf-8", extensions=(".mpf",), kinematics="5ax_table_ac_angled"
    )
    assert report["status"] == "CLEAN"
