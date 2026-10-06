"""Post profile extensions: format.words order/required, arcs, supports and mode."""

from __future__ import annotations

import json

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.kernel import execute


def _write(tmp_path, profile, name="post.json"):
    path = tmp_path / name
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def test_format_words_order_and_number_format_apply(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["X"] = {"order": 25, "required": False, "decimals": 2, "sign": "always"}
    profile["format"]["words"]["Z"] = {"order": 15, "required": False, "decimals": 3, "sign": "never"}
    path = _write(tmp_path, profile)

    result = execute("G21 G17 G90\nG0 X1 Y0 Z5\nG1 X1.2345 Y0 Z-2 F123.456\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, path, ExportOptions(delimiter=True))

    assert "G1 Z-2 X+1.23 F123.456" in text


def test_bundled_profiles_keep_default_word_order():
    result = execute("G21 G17 G90\nG0 X1 Y0 Z5\nG1 X2 Y0 Z0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))

    assert "G1 X2 Z0 F100" in text


def test_format_words_required_forces_zero_axis_address(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["Y"]["required"] = True
    path = _write(tmp_path, profile)

    result = execute("G21 G17 G90\nG0 X1 Y0 Z5\nG1 X2 Y0 Z0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, path, ExportOptions(delimiter=True))

    assert "G1 X2 Y0 Z0 F100" in text


def test_format_words_motion_can_be_modal(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["motion"]["required"] = False
    path = _write(tmp_path, profile)

    result = execute("G21 G17 G90\nG0 X1 Y0 Z5\nG1 X2 Y0 Z0 F100\nG1 X3 Y0 Z0\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, path, ExportOptions(delimiter=True))

    assert text.count("G1 ") == 1
    assert "X3 Z0" in text


@pytest.mark.parametrize(("target", "mode"), [("sinumerik_iso", "G291"), ("sinumerik_840d", "G290")])
def test_sinumerik_mode_is_first_program_line(target, mode):
    result = execute("G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(
        result,
        target,
        ExportOptions(delimiter=True, sequence_numbers=True, start_program="O9999"),
    )
    lines = text.splitlines()

    assert lines[0] == mode
    assert all(not line.lstrip().startswith(mode) for line in lines[1:])
    assert "O9999" in text
    assert lines.index("O9999") > 0


def test_format_words_must_define_motion(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"].pop("motion")
    with pytest.raises(ValueError, match="motion"):
        load_post_profile(_write(tmp_path, profile))


def test_format_words_rejects_unknown_tokens(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["bogus"] = {"order": 5, "required": False}
    with pytest.raises(ValueError, match="unsupported token"):
        load_post_profile(_write(tmp_path, profile))


def test_format_words_axis_requires_supports_axes(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["A"] = {"order": 5, "required": False}
    with pytest.raises(ValueError, match="supports.axes"):
        load_post_profile(_write(tmp_path, profile))


def test_format_words_sign_and_decimals_are_validated(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["X"] = {"order": 20, "required": False, "sign": "sometimes"}
    with pytest.raises(ValueError, match="sign"):
        load_post_profile(_write(tmp_path, profile))


def test_format_words_order_values_must_be_unique(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile["format"]["words"]["Z"]["order"] = profile["format"]["words"]["X"]["order"]
    with pytest.raises(ValueError, match="unique"):
        load_post_profile(_write(tmp_path, profile))


def test_arc_turns_word_is_parameterized(tmp_path):
    profile = load_post_profile("sinumerik_840d")
    profile["format"]["turnsWord"] = "TURNS={turns}"
    path = _write(tmp_path, profile)

    result = execute(
        "G21 G17 G90\nG0 X10 Y0\nG3 X0 Y10 Z-6 I=AC(0) J=AC(0) TURN=2 F100\nM30",
        language="fanuc_mill",
        source_dialect="sinumerik",
    )
    text = convert_resolved_program(result, path, ExportOptions(delimiter=True))

    assert "TURNS=2" in text
