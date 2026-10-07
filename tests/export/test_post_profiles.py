"""Controller profiles emit the same resolved geometry and machine signals."""

import json
from pathlib import Path

import pytest

from app.gcode.export import expanded
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import MILLING_TARGETS, convert_resolved_program, load_post_profile
from app.gcode.export_file import ExportRequest, export_file, validate_export_request
from app.gcode.kernel import execute
from app.gcode.post_profiles import load_post_profile as dedicated_load_post_profile
from app.gcode.trace_tools import motion_length


@pytest.mark.parametrize("target", MILLING_TARGETS)
@pytest.mark.parametrize(
    "cycle",
    [
        "CYCLE81(5,0,2,-9)",
        "CYCLE82(5,0,2,-9,,0.2)",
        "CYCLE83(5,-1,5,-7,,-2,,0.1,0,0,1,1,,0.5,0,0,0,0,0,1001110)",
        "CYCLE84(5,0,2,-9,,0,3,,1.25,0,500,500)",
    ],
)
def test_native_drilling_is_postprocessed_from_resolved_operation(cycle, target):
    source = f"T1 M6\nS500 M3\nG17 G0 X2 Y3 Z5 F100\nMCALL {cycle}\nX2 Y3\nMCALL\nM30\n"
    result = execute(source, language="fanuc_mill", source_dialect="sinumerik")
    assert result.ok and result.complete, result.diagnostics
    output = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    if target == "sinumerik_840d":
        assert "MCALL CYCLE" in output
    else:
        assert "CYCLE" not in output and "MCALL" not in output
    replay = execute(output, language="fanuc_mill", source_dialect="fanuc" if target == "fanuc_mill" else "sinumerik")
    assert replay.ok and replay.complete, replay.diagnostics
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=1e-5)
    assert [m.feed for m in replay.motions if m.move == 1] == pytest.approx(
        [m.feed for m in result.motions if m.move == 1]
    )


@pytest.mark.parametrize("target,system", [("fanuc_lathe_a", "A"), ("fanuc_lathe_b", "B")])
def test_lathe_profiles_preserve_threading_and_feed_per_revolution(target, system):
    source = "T0101\nG18 G21 G99\nG97 S500 M3\nG0 X20 Z2\nG32 Z-10 F1.5\nZ-20\nG0 X22\nM30"
    result = execute(source, language="fanuc_turn")
    assert result.ok and result.complete
    output = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    replay = execute(output, language="fanuc_turn", lathe_gcode_system=system)
    assert replay.ok and replay.complete, replay.diagnostics
    assert [m.threading for m in replay.motions] == [m.threading for m in result.motions]
    assert [m.feed_mode for m in replay.motions] == [m.feed_mode for m in result.motions]
    assert [(m.end_x, m.end_z) for m in replay.motions] == [(m.end_x, m.end_z) for m in result.motions]


def test_external_profile_controls_preamble_dwell_and_program_end(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["id"] = "custom"
    profile["program"].update(preamble=["G17 G90 G94 G54", "M7"], end="M9\nM2")
    profile["dwell"]["scale"] = 1000
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    result = execute("G1 X10 F100\nG4 P250\nM30", language="fanuc_mill")
    output = convert_resolved_program(result, path, ExportOptions(delimiter=True))
    assert "M7" in output and "G4 P250" in output and output.endswith("M9\nM2\n")
    assert output == convert_resolved_program(result, path, ExportOptions(delimiter=True))


def test_full_has_no_target_conversion():
    with pytest.raises(ValueError, match="expanded"):
        validate_export_request(ExportRequest(language="fanuc_mill", mode="full", target_dialect="sinumerik_iso"))


def test_post_profile_loader_has_dedicated_module():
    assert load_post_profile is dedicated_load_post_profile


def test_post_profiles_are_packaged():
    assert len(list(Path(expanded.__file__).with_name("posts").glob("*.json"))) == 7


def test_external_motion_templates_and_numeric_policy_replay(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["motion"]["linearMove"] = "G01 {coord} {feed}"
    profile["options"].update(decimalPlaces=4, forceDecimal=True, plusOutput=True)
    profile["program"]["start"] = "({programName} {units})"
    path = tmp_path / "formatted.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    result = execute("O42\nG0 X1.25 Y2 Z3\nG1 X4.125 F100\nM30", language="fanuc_mill")
    output = convert_resolved_program(result, path)
    assert "(O42 G21)" in output and "G01 X+4.125 Y+2. Z+3. F+100." in output
    replay = execute(output, language="fanuc_mill")
    assert replay.ok and replay.complete
    assert [(m.end_x, m.end_y, m.end_z) for m in replay.motions] == [
        (m.end_x, m.end_y, m.end_z) for m in result.motions
    ]


@pytest.mark.parametrize("template", ["G1 {unknown}", "G1 {coord.__class__}", "G1 {coord[0]}", "G1 {coord!r}"])
def test_invalid_post_templates_fail_even_when_unused(tmp_path, template):
    profile = load_post_profile("fanuc_mill")
    profile["motion"]["circularMoveCW"] = template
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ValueError, match="placeholder"):
        load_post_profile(path)


@pytest.mark.parametrize("target,system", [("fanuc_lathe_a", "A"), ("fanuc_lathe_b", "B")])
@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_lathe_css_clamp_and_feed_units_replay(target, system, scale):
    result = execute(
        "G21 G18 G99\nG50 S2500\nG96 S180 M3\nG0 X40 Z2\nG1 Z-10 F0.2\nG97 S500\nM30", language="fanuc_turn"
    )
    output = convert_resolved_program(result, target, ExportOptions(delimiter=True, output_unit_scale=scale))
    replay = execute(output, language="fanuc_turn", lathe_gcode_system=system)
    assert replay.ok and replay.complete, replay.diagnostics
    for actual, expected in zip(replay.motions, result.motions, strict=True):
        assert actual.spindle_limit_rpm == expected.spindle_limit_rpm
        assert actual.surface_speed_m_min == pytest.approx(expected.surface_speed_m_min, abs=1e-5)
        assert actual.feed == pytest.approx(expected.feed, abs=1e-5)


def test_post_can_disable_arcs_without_changing_geometry(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["outputArcs"] = False
    path = tmp_path / "linear.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    result = execute("G0 X10\nG3 X0 Y10 I-10 J0 F100\nM30", language="fanuc_mill")
    output = convert_resolved_program(result, path)
    replay = execute(output, language="fanuc_mill")
    assert replay.ok and replay.complete and not any(m.arc for m in replay.motions)
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=0.002)


def test_prebuilt_options_still_use_post_default_units(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["options"]["units"] = "inch"
    post = tmp_path / "inch.json"
    post.write_text(json.dumps(profile), encoding="utf-8")
    result = execute("G21 G0 X25.4\nG1 X50.8 F254\nM30", language="fanuc_mill")

    output = convert_resolved_program(result, post, ExportOptions(delimiter=True))

    assert "G20" in output
    assert "X1" in output and "X2" in output and "F10" in output


def test_explicit_file_units_override_post_default_units(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["options"]["units"] = "inch"
    post = tmp_path / "inch.json"
    post.write_text(json.dumps(profile), encoding="utf-8")
    source = tmp_path / "source.nc"
    source.write_text("G21 G0 X25.4\nG1 X50.8 F254\nM30", encoding="utf-8")
    output = tmp_path / "output.nc"

    export_file(
        source,
        output,
        ExportRequest(language="fanuc_mill", target_dialect=str(post), units="mm"),
    )

    text = output.read_text(encoding="utf-8")
    assert "G21" in text
    assert "X25.4" in text and "X50.8" in text and "F254" in text


def test_file_export_uses_profile_default_units_and_arc_mode(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["options"]["units"] = "inch"
    profile["format"]["arcMode"] = "R"
    post = tmp_path / "inch.json"
    post.write_text(json.dumps(profile), encoding="utf-8")
    source = tmp_path / "source.nc"
    source.write_text("G21 G0 X25.4\nG3 X0 Y25.4 I-25.4 J0 F254\nM30", encoding="utf-8")
    output = tmp_path / "output.nc"
    outcome = export_file(source, output, ExportRequest(language="fanuc_mill", target_dialect=str(post)))
    text = output.read_text(encoding="utf-8")
    assert outcome.effective_units == "inch" and outcome.effective_arc_type == "radius"
    assert "G20" in text and "R1" in text and "F10" in text
    replay = execute(text, language="fanuc_mill")
    assert replay.ok and replay.complete
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, outcome.execution.motions)))
