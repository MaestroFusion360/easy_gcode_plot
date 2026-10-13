"""Native iTNC blocks are checked directly: this project has no TNC parser."""

import math
import re

import pytest

from app.gcode.batch.export import export_directory
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.export.service import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.post_profiles import load_post_profile
from app.post_profile_library import PostProfileLibrary

TARGET = "heidanhain_itnc530"


@pytest.mark.parametrize("direction,sign", [(2, "-"), (3, "+")])
@pytest.mark.parametrize("end", ["X10 Y0", "X0 Y10 Z-2"])
def test_polar_angle_sign_matches_rotation(direction, sign, end):
    result = execute(f"T1 M6\nG0 X10 Y0 Z0\nG{direction} {end} I-10 J0 F100", "fanuc_mill")
    assert result.ok
    text = convert_resolved_program(result, TARGET)
    blocks = [line for line in text.splitlines() if line.startswith("CP ")]
    assert len(blocks) == 1
    angle = math.degrees(result.motions[-1].arc.sweep)
    assert f"IPA{sign}{angle:g}" in blocks[0]
    assert f"DR{sign}" in blocks[0]


@pytest.mark.parametrize("code,definition,retraction", [(85, "201 REAMING", "+100"), (86, "202 BORING", "+99999")])
def test_boring_never_emits_tapping_and_preserves_retraction(code, definition, retraction):
    result = execute(f"T1 M6\nS1000 M3\nG0 X0 Y0 Z5\nG{code} X10 Z-5 R2 F100\nG80", "fanuc_mill")
    assert result.ok
    text = convert_resolved_program(result, TARGET)
    assert f"CYCL DEF {definition}" in text
    assert "CYCL DEF 206" not in text
    assert "Q201=-7" in text
    assert "Q206=+100" in text
    assert f"Q208={retraction}" in text
    assert "Q211=+0" in text
    assert ("Q214=+0" in text) == (code == 86)
    assert ("Q336=+0" in text) == (code == 86)
    assert text.count("CYCL CALL") == 1


@pytest.mark.parametrize("cycle,spindle,sign", [(74, 4, "-"), (84, 3, "+")])
@pytest.mark.parametrize("scale,pitch", [(1.0, "0.1"), (25.4, "0.003937")])
def test_tapping_pitch_keeps_hand_and_output_units(cycle, spindle, sign, scale, pitch):
    result = execute(f"T1 M6\nS1000 M{spindle}\nG0 X0 Y0 Z5\nG{cycle} X10 Z-5 R2 F100\nG80", "fanuc_mill")
    assert result.ok
    text = convert_resolved_program(
        result, TARGET, ExportOptions(output_unit_scale=scale, decimal_places=6, decimal_places_explicit=True)
    )
    assert "CYCL DEF 207" in text
    assert f"Q239={sign}{pitch}" in text


@pytest.mark.parametrize("plane,endpoint,center", [(18, "X0 Z10", "I-10 K0"), (19, "Y0 Z10", "J-10 K0")])
@pytest.mark.parametrize("arc_mode", [0, 2])
@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_arcs_outside_spindle_plane_are_sampled_with_correct_geometry(
    tmp_path, plane, endpoint, center, arc_mode, scale
):
    start = "X10 Y0 Z0" if plane == 18 else "X0 Y10 Z0"
    result = execute(f"T1 M6\nG0 {start}\nG{plane} G3 {endpoint} {center} F100", "fanuc_mill")
    assert result.ok
    profile = load_post_profile(TARGET)
    profile["options"]["decimalPlaces"] = 6
    path = PostProfileLibrary(tmp_path).save(profile)
    options = ExportOptions(arc_mode=arc_mode, output_unit_scale=scale, linearization_tolerance=0.01 / scale)
    text = convert_resolved_program(result, path, options)
    assert "TOOL CALL 1 Z" in text
    assert not any(line.startswith(("CC ", "C ", "CP ", "CR ")) for line in text.splitlines())
    position = [0.0, 0.0, 0.0]
    points = []
    for line in text.splitlines():
        if not line.startswith("L "):
            continue
        for axis, value in re.findall(r"\b([XYZ])([+-]?[\d.]+)", line):
            position["XYZ".index(axis)] = float(value) * scale
        points.append(tuple(position))
    assert len(points) > 10
    assert points[-1] == pytest.approx((0, 0, 10), abs=0.00002)
    assert all(math.dist(point, (0, 0, 0)) == pytest.approx(10, abs=0.00002) for point in points)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert length == pytest.approx(10 * result.motions[-1].arc.sweep, abs=0.05)


def test_custom_spindle_axis_controls_native_arc_plane(tmp_path):
    profile = load_post_profile(TARGET)
    profile["tool"]["toolChange"] = "TOOL CALL {tool} Y {code}"
    path = PostProfileLibrary(tmp_path).save(profile)
    result = execute("T1 M6\nG0 X10 Z0\nG18 G3 X0 Z10 I-10 K0 F100", "fanuc_mill")
    text = convert_resolved_program(result, path)
    assert "TOOL CALL 1 Y" in text
    assert "CC X+0 Z+0" in text
    assert "C X+0 Z+10 DR+" in text


def test_single_and_batch_export_use_native_writer_and_h_extension(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    path = source / "part.nc"
    path.write_text("T1 M6\nS500 M3\nG0 X10 Y0\nG2 X10 Y0 I-10 J0 F100\nM30")
    request = ExportRequest(language="fanuc_mill", mode="expanded", target_dialect=TARGET)
    output = tmp_path / "single.h"
    result = export_file(path, output, request)
    assert result.execution.ok and result.output_size_bytes > 0
    batch = tmp_path / "batch"
    report = export_directory(source, batch, request)
    assert report["summary"]["exported"] == 1
    assert (batch / "part.h").read_bytes() == output.read_bytes()
    assert "CP IPA-360 DR-" in output.read_text()
