"""Regression cases found by independent semantic replay of the 1.9.4 changes."""

import json

import pytest
from export_signatures import motion_traces_match

from app.cli import main
from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.export.full import normalize_full_program
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.program_execution import execute_program

TARGETS = ("fanuc_mill_multiaxis", "sinumerik_840d_multiaxis")


def _replay(text, target, profile, **kwargs):
    result = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        kinematics=profile,
        **kwargs,
    )
    assert result.ok and result.complete, result.diagnostics
    return result


@pytest.mark.parametrize("target", TARGETS)
def test_repeated_tcp_preserves_physical_position(target):
    source = "G90 G0 B30\nG0 X10 Y20 Z30\nG43.4\nG1 X15 F100\nG43.4\nG1 X20\nG49\nM30"
    original = execute(source, language="fanuc_mill", kinematics="5ax_table_bc_angled")
    first, second = original.motions[-2:]
    assert (second.start_x, second.start_y, second.start_z) == pytest.approx((first.end_x, first.end_y, first.end_z))
    text = convert_resolved_program(original, target, ExportOptions(delimiter=True))
    assert motion_traces_match(original, _replay(text, target, "5ax_table_bc_angled"))


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("incremental", (False, True))
@pytest.mark.parametrize("arc_mode", (2, 3))
def test_split_tcp_arc_interpolates_rotary_angles(target, incremental, arc_mode):
    source = "G90 G0 X10 Y0 Z5\nG43.4\nG3 X10 Y0 I-10 J0 B30 C90 F100\nG49\nM30"
    original = execute(source, language="fanuc_mill", kinematics="5ax_table_bc_angled")
    text = convert_resolved_program(
        original, target, ExportOptions(delimiter=True, incremental=incremental, arc_mode=arc_mode)
    )
    replay = _replay(text, target, "5ax_table_bc_angled")
    assert dict(replay.rotary_angles) == pytest.approx(dict(original.rotary_angles))
    arc_steps = [step for step in replay.execution_steps if any(e.kind == "ROTARY_MOTION" for e in step.events)]
    assert len(arc_steps) >= 2
    for index, step in enumerate(arc_steps, 1):
        angles = dict(step.rotary_angles)
        assert angles["B"] == pytest.approx(30 * index / len(arc_steps), abs=0.0002)
        assert angles["C"] == pytest.approx(90 * index / len(arc_steps), abs=0.0002)
    assert replay.motions[-1].feed == original.motions[-1].feed


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("incremental", (False, True))
def test_indexed_nonzero_wcs_fails_closed(target, incremental):
    source = "G90 G0 X1 Y2 Z5\nB45\nG0 X10 Y3 Z10\nG1 Z8 F100\nM30"
    original = execute(source, language="fanuc_mill", kinematics="4ax_table_b", wcs_offsets={54: (10, 20, 30)})
    assert original.ok and original.complete
    with pytest.raises(ExportLimitation) as error:
        convert_resolved_program(original, target, ExportOptions(incremental=incremental))
    assert error.value.code == "UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT"


def test_tcp_axis_missing_from_custom_post_fails_closed(tmp_path):
    profile = load_post_profile("fanuc_mill_multiaxis")
    profile["supports"]["axes"].remove("B")
    del profile["format"]["words"]["B"]
    path = tmp_path / "without_b.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    result = execute(
        "G90 G0 Z5\nG43.4\nG1 X10 B30 C90 F100\nG49\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_bc_angled",
    )
    with pytest.raises(ExportLimitation) as error:
        convert_resolved_program(result, path)
    assert error.value.code == "UNSUPPORTED_AXIS_EXPANDED_EXPORT"


def test_index_frame_invalidates_modal_motion_cache(tmp_path):
    profile = load_post_profile("fanuc_mill_multiaxis")
    profile["format"]["words"]["motion"]["required"] = False
    path = tmp_path / "modal.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    source = "G90 G0 Z5\nG1 X10 F100\nG0 B45\nG1 X20\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    text = convert_resolved_program(result, path, ExportOptions(delimiter=True))
    assert motion_traces_match(result, _replay(text, "fanuc_mill_multiaxis", "4ax_table_b"))


def test_full_macro_rotary_preserves_index_gaps():
    source = "#1=45\nG90 G0 Z5\nB#1\nG1 X10 Z10 F100\nZ8\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    text = normalize_full_program(result, source, ExportOptions(delimiter=True))
    assert motion_traces_match(result, _replay(text, "fanuc_mill_multiaxis", "4ax_table_b"))


FIXTURES = (
    ("fanuc/contur_2d.nc", None),
    ("fanuc/mixed_ijk_r_planes.nc", None),
    ("fanuc/cycles_fanuc.nc", None),
    ("fanuc/flange_plate_benchmark.nc", None),
    ("fanuc/indexed_table_a.nc", "4ax_table_a"),
    ("fanuc/indexed_table_b.nc", "4ax_table_b"),
    ("fanuc/indexed_table_c.nc", "4ax_table_c"),
    ("fanuc/impeller.ptp", "5ax_table_bc_angled"),
    ("fanuc/impeller2.ptp", "5ax_table_ac_angled"),
    ("sinumerik/contur_2d_sin840d.mpf", None),
    ("sinumerik/cycles_sin840d.mpf", None),
    ("sinumerik/tapping_sin840d.mpf", None),
    ("sinumerik/sinumerik_traori_ac.mpf", "5ax_table_ac_angled"),
)


@pytest.mark.parametrize("fixture,kinematics", FIXTURES)
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("incremental", (False, True))
def test_real_fixture_semantic_replay(fixture_text, fixture, kinematics, target, incremental):
    original, _tools, _inferred = execute_program(
        fixture_text(f"milling/{fixture}"),
        language="fanuc_mill",
        source_dialect="sinumerik" if fixture.startswith("sinumerik/") else "fanuc",
        kinematics=kinematics,
        home_z=500,
        autodetect_arc_type=True,
    )
    assert original.ok and original.complete, original.diagnostics
    if fixture == "fanuc/indexed_table_b.nc":
        assert any(d.code == "UNVERIFIED_CUTTER_COMPENSATION" for d in original.diagnostics)
        with pytest.raises(ExportLimitation) as error:
            convert_resolved_program(original, target, ExportOptions(incremental=incremental))
        assert error.value.code == "UNSUPPORTED_UNVERIFIED_GEOMETRY_EXPANDED_EXPORT"
        return
    text = convert_resolved_program(original, target, ExportOptions(delimiter=True, incremental=incremental))
    replay = _replay(text, target, kinematics, home_z=500, autodetect_arc_type=True)
    assert motion_traces_match(original, replay, allow_split_cycle_rapids=True)
    assert dict(replay.rotary_angles) == pytest.approx(dict(original.rotary_angles), abs=1e-5)
    assert {motion.tool for motion in replay.motions} == {motion.tool for motion in original.motions}


@pytest.mark.parametrize("cancel", ("G49", "G43 H1"))
def test_tcp_cancel_preserves_physical_position(cancel):
    result = execute(
        f"G90 G0 B30\nG0 X10 Y20 Z30\nG43.4\nG1 X15 F100\n{cancel}\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_bc_angled",
    )
    assert result.ok and result.complete
    motion = result.motions[-1]
    assert result.execution_steps[-2].position == pytest.approx((motion.end_x, motion.end_y, motion.end_z))
    assert [e.kind for e in result.events if e.kind.startswith("TCP_CONTROL")] == ["TCP_CONTROL_ON", "TCP_CONTROL_OFF"]


@pytest.mark.parametrize(
    "fixture,profile,dialect",
    (
        ("fanuc/g68_2_cube.nc", "5ax_table_ac_angled", "fanuc"),
        ("sinumerik/sinumerik_cycle800.mpf", "5ax_table_ac_angled", "sinumerik"),
        ("sinumerik/5ax_test.mpf", "5ax_table_ac_angled", "sinumerik"),
        ("sinumerik/impeller.mpf", "5ax_table_bc_angled", "sinumerik"),
    ),
)
def test_tilted_plane_real_fixtures_full_and_expanded(fixture_text, fixture, profile, dialect):
    source = fixture_text(f"milling/{fixture}")
    original, tools, _inferred = execute_program(
        source,
        language="fanuc_mill",
        source_dialect=dialect,
        kinematics=profile,
        home_z=500,
        autodetect_arc_type=True,
    )
    assert original.ok and original.complete, original.diagnostics
    full = normalize_full_program(original, source, ExportOptions(delimiter=True, sequence_numbers=True))
    target = "sinumerik_840d_multiaxis" if dialect == "sinumerik" else "fanuc_mill_multiaxis"
    replay = _replay(full, target, profile, home_z=500, autodetect_arc_type=True, milling_tools=tools)
    assert motion_traces_match(original, replay)
    for post in TARGETS:
        if fixture in {"sinumerik/5ax_test.mpf", "sinumerik/impeller.mpf"}:
            with pytest.raises(ExportLimitation) as error:
                convert_resolved_program(original, post)
            expected = (
                "UNSUPPORTED_UNVERIFIED_GEOMETRY_EXPANDED_EXPORT"
                if fixture.endswith("5ax_test.mpf")
                else "UNSUPPORTED_TWP_EXPANDED_EXPORT"
            )
            assert error.value.code == expected
            continue
        expanded = convert_resolved_program(original, post, ExportOptions(delimiter=True))
        replay = _replay(expanded, post, profile, home_z=500, autodetect_arc_type=True, milling_tools=tools)
        assert motion_traces_match(original, replay)


def test_displaced_index_failure_preserves_existing_output(tmp_path):
    source = tmp_path / "indexed.nc"
    source.write_text("G10 L2 P1 X10 Y20 Z30\nG90 G0 X1 Y2 Z5\nB45\nG0 X10 Y3 Z10\nM30", encoding="utf-8")
    output = tmp_path / "output.nc"
    output.write_text("existing output", encoding="utf-8")
    exported = export_file(
        source,
        output,
        ExportRequest(
            language="fanuc_mill",
            kinematics="4ax_table_b",
            target_dialect="fanuc_mill_multiaxis",
        ),
    )
    assert not exported.execution.ok
    assert exported.execution.diagnostics[-1].code == "UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT"
    assert output.read_text(encoding="utf-8") == "existing output"


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("incremental", (False, True))
def test_supa_nonzero_home_wcs_and_following_motion(target, incremental):
    source = "G710 G90\nG0 X10 Y20 Z30\nG91\nG0 SUPA Z0 D0\nG90 G1 X15 Y25 Z50 F100\nM30"
    original = execute(
        source, language="fanuc_mill", source_dialect="sinumerik", home_z=500, wcs_offsets={54: (40, -25, 80)}
    )
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, target, ExportOptions(delimiter=True, incremental=incremental))
    replay = _replay(text, target, None, home_z=500)
    assert motion_traces_match(original, replay)


@pytest.mark.parametrize("profile", ("4ax_head_b", "5ax_table_c_head_b_negative"))
@pytest.mark.parametrize("target", TARGETS)
def test_head_reference_uses_table_frame_only(profile, target):
    source = "G90 G0 B30\nG0 X10 Y20 Z30\nG53 G0 Z0\nG1 X15 Z35 F100\nM30"
    original = execute(source, language="fanuc_mill", kinematics=profile, home_z=500)
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, target, ExportOptions(delimiter=True))
    assert motion_traces_match(original, _replay(text, target, profile, home_z=500))


@pytest.mark.parametrize("target", TARGETS)
def test_table_c_rotation_at_origin_keeps_feed_and_orientation(target):
    original = execute("G90 G1 C90 F300\nX10\nM30", language="fanuc_mill", kinematics="4ax_table_c")
    assert original.ok and original.complete
    text = convert_resolved_program(original, target, ExportOptions(delimiter=True))
    rotary_line = next(line for line in text.splitlines() if "C90" in line)
    assert "F300" in rotary_line
    replay = _replay(text, target, "4ax_table_c")
    assert motion_traces_match(original, replay)


@pytest.mark.parametrize("arc_mode", (2, 3))
def test_inverse_time_tcp_split_preserves_duration(tmp_path, arc_mode):
    profile = load_post_profile("sinumerik_840d_multiaxis")
    profile["supports"]["inverseTime"] = True
    profile["feed"]["inverseTime"] = "G93"
    path = tmp_path / "g93.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    original = execute(
        "G710 G90 G0 X10 Z5\nTRAORI\nG93 G3 X10 Y0 I-10 J0 B30 C90 F2\nG1 X20\nTRAFOOF\nM30",
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics="5ax_table_bc_angled",
    )
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, path, ExportOptions(delimiter=True, arc_mode=arc_mode))
    replay = _replay(text, "sinumerik_840d_multiaxis", "5ax_table_bc_angled")
    original_minutes = sum(1 / m.feed for m in original.motions if m.feed_mode == "inverse_time")
    replay_minutes = sum(1 / m.feed for m in replay.motions if m.feed_mode == "inverse_time")
    assert replay_minutes == pytest.approx(original_minutes)


def test_cli_displaced_index_is_unsupported_without_output(tmp_path, capsys):
    source = tmp_path / "index.nc"
    source.write_text("G10 L2 P1 X10 Y20 Z30\nG90 G0 Z5\nB45\nG0 X10 Z10\nM30", encoding="utf-8")
    output = tmp_path / "out.nc"
    status = main(
        [
            "export",
            str(source),
            "--lang",
            "fanuc_mill",
            "--kinematics",
            "4ax_table_b",
            "--post-profile",
            "fanuc_mill_multiaxis",
            "-o",
            str(output),
        ]
    )
    assert status == 2
    assert not output.exists()
    assert "UNSUPPORTED_INDEXED_WCS_EXPANDED_EXPORT" in capsys.readouterr().out


@pytest.mark.parametrize(
    "profile,offset",
    (
        ("4ax_head_b", (10, 20, 30)),
        ("4ax_table_b", (0, 20, 0)),
    ),
)
def test_index_with_invariant_wcs_is_reconstructable(profile, offset):
    source = "G90 G0 X10 Y20 Z30\nB45\nG1 X15 F100\nM30"
    original = execute(source, language="fanuc_mill", kinematics=profile, wcs_offsets={54: offset})
    text = convert_resolved_program(original, "fanuc_mill_multiaxis", ExportOptions(delimiter=True))
    assert motion_traces_match(original, _replay(text, "fanuc_mill_multiaxis", profile))
