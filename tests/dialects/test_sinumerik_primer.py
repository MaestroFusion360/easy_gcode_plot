"""Bearing plate: independent dimensions from the source and Siemens PGZ 01/2008."""

import math

import pytest
from export_signatures import motion_traces_match

from app.gcode.execution.program import execute_program
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute


@pytest.mark.parametrize("correction", [False, True])
def test_complete_primer_retains_pocket_and_repeats_holes_with_either_correction_setting(fixture_text, correction):
    source = fixture_text("milling/sinumerik/cycles/primer.mpf")
    result, tools, _ = execute_program(
        source,
        language="fanuc_mill",
        source_dialect="sinumerik",
        correction_enabled=correction,
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
