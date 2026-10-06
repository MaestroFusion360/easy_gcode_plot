"""Multiaxis EXPANDED post profiles: explicit resolved rotary coordinates only."""

from __future__ import annotations

import re

import pytest

from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.kernel import execute

MULTIAXIS_TARGETS = ("fanuc_mill_multiaxis", "sinumerik_840d_multiaxis")
THREE_AXIS_TARGETS = ("fanuc_mill", "sinumerik_840d")

ROTARY_PROGRAMS = (
    ("G90 G0 X0 Y0 Z0\nA30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_a", "A"),
    ("G90 G0 X0 Y0 Z0\nB30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_b", "B"),
    ("G90 G0 X0 Y0 Z0\nC30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_c", "C"),
    ("G90 G0 X0 Y0 Z0\nA30 C45\nG1 X10 Y20 Z30 F100\nM30", "5ax_table_ac_angled", "A"),
    ("G90 G0 X0 Y0 Z0\nB30 C45\nG1 X10 Y20 Z30 F100\nM30", "5ax_table_bc_angled", "B"),
)


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_multiaxis_profile_declares_all_rotary_axes(target):
    profile = load_post_profile(target)
    assert {"X", "Y", "Z", "A", "B", "C"} <= set(profile["supports"]["axes"])
    words = profile["format"]["words"]
    assert {"A", "B", "C"} <= set(words)
    assert all(words[axis]["required"] is False for axis in "ABC")


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_three_axis_program_exports_through_multiaxis_profile(target):
    result = execute("G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    assert "G1 X10 Z0 F100" in text
    assert not re.search(r"[ABC][-+]?\d", text)


@pytest.mark.parametrize(("source", "kinematics", "axis"), ROTARY_PROGRAMS)
def test_rotary_program_exports_only_through_multiaxis_profiles(source, kinematics, axis):
    result = execute(source, language="fanuc_mill", kinematics=kinematics)
    assert result.ok and result.complete, result.diagnostics

    for target in MULTIAXIS_TARGETS:
        text = convert_resolved_program(result, target, ExportOptions(delimiter=True))
        assert re.search(rf"(?<![A-Z]){axis}[-+]?\d", text), text

    for target in THREE_AXIS_TARGETS:
        with pytest.raises(ExportLimitation):
            convert_resolved_program(result, target, ExportOptions(delimiter=True))


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_multiaxis_profile_still_rejects_tcp(target):
    source = "G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 B30 C45 F100\nG49\nM30"
    result = execute(source, language="fanuc_mill", kinematics="5ax_table_bc_angled")
    assert result.ok and result.complete, result.diagnostics
    with pytest.raises(ExportLimitation, match="TCP"):
        convert_resolved_program(result, target, ExportOptions(delimiter=True))


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_multiaxis_profile_still_rejects_tilted_plane(target):
    source = "G90 G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG53.1\nG0 X10 Y20 Z-5\nG69\nM30"
    result = execute(source, language="fanuc_mill", kinematics="5ax_table_ac_angled")
    assert result.ok and result.complete, result.diagnostics
    with pytest.raises(ExportLimitation, match="tilted"):
        convert_resolved_program(result, target, ExportOptions(delimiter=True))
