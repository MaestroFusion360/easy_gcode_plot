"""Bearing plate: independent dimensions from the source and Siemens PGZ 01/2008."""

import math

import pytest
from export_signatures import motion_traces_match

from app.gcode.execution.program import execute_program
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import builtin_profile_ids, load_catalog, point_orientation, transform_vector
from app.gcode.trace import render_trace, trace_statistics


@pytest.mark.parametrize("correction", [False, True])
@pytest.mark.parametrize("kinematics", (None, *sorted(builtin_profile_ids())))
def test_complete_primer_retains_pocket_and_repeats_holes_with_either_correction_setting(
    fixture_text, correction, kinematics
):
    source = fixture_text("milling/sinumerik/cycles/primer.mpf")
    result, tools, _ = execute_program(
        source,
        language="fanuc_mill",
        source_dialect="sinumerik",
        correction_enabled=correction,
        kinematics=kinematics,
    )
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert not result.diagnostics
    assert [tools[f"T{i}"]["diameter"] for i in range(1, 5)] == [50, 10, 6, 5]
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    assert all(m.source_raw == source.splitlines()[m.source_block] for m in result.motions)

    # PRAD=15 is a radius, so a D10 cutter finishes with its center at R10.
    pocket = [m for m in result.motions if m.source_raw.startswith("POCKET4")]
    assert len(pocket) == 11
    arcs = [m for m in pocket if m.arc is not None]
    assert [m.arc.radius for m in arcs] == [2, 2, 5, 10]
    assert all(not m.arc.clockwise for m in arcs)  # CDIR=0, M3 => downcut G3.
    helix = arcs[0]
    assert (helix.start_z, helix.end_z, helix.feed) == (1, -5, 1300)
    assert helix.arc.center == (0, 0, 1)
    assert helix.arc.sweep == pytest.approx(12 * math.tau)
    assert (helix.start_z - helix.end_z) / (helix.arc.sweep / math.tau) == pytest.approx(0.5)
    assert arcs[1].arc.sweep == pytest.approx(math.tau)  # Clean the helical ramp at final depth.
    assert all(m.end_z == -5 and m.feed == 800 for m in arcs[2:])
    assert pocket[-1].end_z == 2

    # Explicit INDA=45 and NUM=6 cover 225 degrees, not a uniform full circle.
    expected_xy = [(25 * math.cos(math.radians(a)), 25 * math.sin(math.radians(a))) for a in range(0, 226, 45)]
    for tool, depth in (("T3", -2.6), ("T4", -13.5)):
        cuts = [m for m in result.motions if m.tool == tool and m.cycle_generated and m.move == 1]
        assert len(cuts) == 6
        for cut, xy in zip(cuts, expected_xy, strict=True):
            assert (cut.end_x, cut.end_y) == pytest.approx(xy)
            assert (cut.start_z, cut.end_z) == (1, depth)
    repeated = [step for step in result.execution_steps if source.splitlines()[step.source_block].startswith("HOLES2")]
    assert len(repeated) == 2 and repeated[1].occurrence > repeated[0].occurrence

    contour = [m for m in result.motions if m.compensation_mode == 41]
    assert all(m.compensation_applied == correction for m in contour)
    rounded = next(m for m in contour if m.arc is not None and m.source_block == 8)
    assert rounded.arc.center == pytest.approx((-30, 20, -10))
    assert rounded.arc.radius == pytest.approx(35 if correction else 10)
    assert rounded.arc.clockwise and rounded.arc.sweep == pytest.approx(math.pi / 2)
    if not correction:
        chamfer = next(m for m in contour if m.source_kind == "sinumerik_chr")
        assert (chamfer.start_x, chamfer.start_y, chamfer.end_x, chamfer.end_y) == (30, 30, 40, 20)


@pytest.mark.parametrize("command", ["CHR", "RND"])
@pytest.mark.parametrize("angle", [0, 360])
@pytest.mark.parametrize("kinematics", ["5ax_table_ac", "4ax_table_c"])
def test_corner_with_selected_profile_and_identity_rotary_frame(command, angle, kinematics):
    source = f"G0 C{angle}\nG1 X40 Y0 F100\nG1 X40 Y30 {command}=10\nG1 X0 Y30\nM30"
    result = execute(source, "fanuc_mill", source_dialect="sinumerik", kinematics=kinematics)
    assert result.ok and result.complete, result.diagnostics
    corner = next(m for m in result.motions if m.source_kind == "sinumerik_" + command.lower())
    assert (corner.start_x, corner.start_y, corner.end_x, corner.end_y) == pytest.approx((40, 20, 30, 30))
    assert corner.move == (1 if command == "CHR" else 3)
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)


@pytest.mark.parametrize("command", ["CHR", "RND"])
@pytest.mark.parametrize("kinematics", sorted(builtin_profile_ids()))
def test_corner_supports_any_fixed_profile_orientation(command, kinematics):
    profile = load_catalog()[kinematics]
    angles = {axis: 23 + 14 * index for index, axis in enumerate(sorted(profile.addresses))}
    index = "G0 " + " ".join(f"{axis}{value}" for axis, value in angles.items())
    source = f"{index}\nG1 X40 Y0 Z0 F100\nG1 X40 Y30 {command}=10\nG1 X0 Y30\nM30"
    offset = (13, -17, 29)
    result = execute(source, "fanuc_mill", source_dialect="sinumerik", kinematics=kinematics, wcs_offsets={54: offset})
    assert result.ok and result.complete, result.diagnostics
    corner = next(m for m in result.motions if m.source_kind == "sinumerik_" + command.lower())
    matrix = point_orientation(profile, angles)

    def point(local):
        rotated = transform_vector(matrix, local)
        return tuple(rotated[i] + offset[i] for i in range(3))

    assert (corner.start_x, corner.start_y, corner.start_z) == pytest.approx(point((40, 20, 0)))
    assert (corner.end_x, corner.end_y, corner.end_z) == pytest.approx(point((30, 30, 0)))
    if command == "RND":
        assert corner.arc.center == pytest.approx(point((30, 20, 0)))
        assert corner.arc.radius == pytest.approx(10)
        assert corner.arc.normal == pytest.approx(transform_vector(matrix, (0, 0, 1)))
        assert corner.arc.sweep == pytest.approx(math.pi / 2)
    assert render_trace(result)


@pytest.mark.parametrize("kinematics", ["5ax_table_ac", "5ax_table_bc"])
@pytest.mark.parametrize("angle", [30, -45, 90])
@pytest.mark.parametrize("correction", [False, True])
def test_complete_primer_rotates_without_changing_local_contour_or_cycles(fixture_text, kinematics, angle, correction):
    source = fixture_text("milling/sinumerik/cycles/primer.mpf")
    baseline, _, _ = execute_program(
        source, language="fanuc_mill", source_dialect="sinumerik", correction_enabled=correction
    )
    profile = load_catalog()[kinematics]
    tilt = profile.table_rotary_axes[0].address
    result, _, _ = execute_program(
        f"G0 {tilt}{angle} C37\n" + source,
        language="fanuc_mill",
        source_dialect="sinumerik",
        correction_enabled=correction,
        kinematics=kinematics,
    )
    assert result.ok and result.complete and not result.diagnostics, result.diagnostics
    matrix = point_orientation(profile, {tilt: angle, "C": 37})
    assert len(result.motions) == len(baseline.motions)
    for got, original in zip(result.motions, baseline.motions, strict=True):
        assert (got.end_x, got.end_y, got.end_z) == pytest.approx(
            transform_vector(matrix, (original.end_x, original.end_y, original.end_z))
        )
        assert got.source_kind == original.source_kind and got.compensation_applied == original.compensation_applied
    assert trace_statistics(result)["total_length"] == pytest.approx(trace_statistics(baseline)["total_length"])


def test_corner_rejects_adjacent_elements_in_different_working_planes():
    source = "G0 A30\nG1 X40 Y0 F100\nG1 X40 Y30 CHR=10\nG0 A60\nG1 X0 Y30\nM30"
    result = execute(source, "fanuc_mill", source_dialect="sinumerik", kinematics="5ax_table_ac")
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == "INVALID_SINUMERIK_CORNER"
    assert "share a working plane" in result.diagnostics[-1].message


@pytest.mark.parametrize("target", ["fanuc_mill", "sinumerik_840d"])
@pytest.mark.parametrize("correction", [False, True])
def test_primer_expanded_export_preserves_both_hole_patterns_and_arcs(fixture_text, target, correction):
    result, _, _ = execute_program(
        fixture_text("milling/sinumerik/cycles/primer.mpf"),
        language="fanuc_mill",
        source_dialect="sinumerik",
        correction_enabled=correction,
    )
    text = convert_resolved_program(result, target=target, options=ExportOptions(decimal_places=6))
    replay = execute(text, language="fanuc_mill", source_dialect="sinumerik" if target == "sinumerik_840d" else "fanuc")
    assert replay.ok and replay.complete and not replay.diagnostics
    if target == "sinumerik_840d":
        assert motion_traces_match(result, replay, tolerance=0.000002)
    else:
        # FANUC splits multi-turn/full-circle arcs into supported individual arcs.
        for tool in ("T1", "T2", "T3", "T4"):
            before = [m for m in result.motions if m.tool == tool]
            after = [m for m in replay.motions if m.tool == tool]
            assert sum(m.arc.radius * m.arc.sweep for m in after if m.arc) == pytest.approx(
                sum(m.arc.radius * m.arc.sweep for m in before if m.arc),
                abs=0.00001,
            )
        for tool, depth in (("T3", -2.6), ("T4", -13.5)):
            cuts = [m for m in replay.motions if m.tool == tool and m.move == 1]
            assert len(cuts) == 6 and all(m.start_z == 1 and m.end_z == depth for m in cuts)
