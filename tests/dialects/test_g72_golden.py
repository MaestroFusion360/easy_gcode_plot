"""G72 reference trajectory must depend on NC compensation commands, not tool presence."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.gcode.export import ExportOptions, export_full_program, export_result
from app.gcode.kernel import execute


def _coordinates(motions):
    return [(m.move, m.start_x, m.start_z, m.end_x, m.end_z) for m in motions]


def _first_facing_cycle(result):
    offset = 0
    for step in result.execution_steps:
        if result.program.blocks[step.source_block].raw.startswith("G72P11Q12"):
            return result.motions[offset : offset + step.emitted_count]
        offset += step.emitted_count
    raise AssertionError("The fixture's first G72 cycle did not execute")


@pytest.mark.parametrize("radius", [None, 0.4, 0.7, 0.8, 1.2])
def test_o0339_g72_matches_complete_golden_with_or_without_tool_geometry(fixture_text, radius):
    tools = (
        None
        if radius is None
        else {"T0909": {"type": "diamond_80", "applications": ["od"], "noseRadius": radius, "tipOrientation": 3}}
    )
    result = execute(fixture_text("turning/basic_turning_cycles.NC"), language="fanuc_turn", tools=tools)
    assert result.ok and result.complete, result.diagnostics
    motions = _first_facing_cycle(result)
    golden = Path(__file__).resolve().parents[1] / "golden" / "turning" / "basic_turning_cycles_g72.csv"
    reader = csv.reader(golden.read_text(encoding="ascii").splitlines())
    assert next(reader) == ["move", "start_x", "start_z", "end_x", "end_z"]
    expected = [tuple(map(float, row)) for row in reader]
    assert len(motions) == len(expected) == 457
    for index, (actual, reference) in enumerate(zip(_coordinates(motions), expected, strict=True)):
        assert actual == pytest.approx(reference, abs=1e-8), f"G72 motion {index}"
    assert not any(m.compensation_applied for m in motions)
    assert (motions[-4].start_z, motions[-4].end_z) == pytest.approx((-222.7, -222.7))


@pytest.mark.parametrize("cycle", [71, 72, 73])
@pytest.mark.parametrize("mode", [None, 40, 41, 42, "cancel"])
def test_roughing_tool_geometry_requires_explicit_active_compensation(cycle, mode):
    first = {71: "U2 R0.2", 72: "W2 R0.2", 73: "U4 W2 R3"}[cycle]
    entry = "Z0" if cycle == 72 else "X40"
    end = "X20" if cycle == 72 else "Z-10"
    control = "" if mode is None else "G41\nG40\n" if mode == "cancel" else f"G{mode}\n"
    source = (
        f"G21 G18\nT0101\nG0 X50 Z5\n{control}G{cycle} {first}\n"
        f"G{cycle} P10 Q20 U0 W0.2 F0.25\nN10 G0 {entry}\nN20 G1 {end}\nM30"
    )
    nominal = execute(source, language="fanuc_turn")
    result = execute(
        source,
        language="fanuc_turn",
        tools={"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.7, "tipOrientation": 3}},
    )
    assert nominal.ok and result.ok, result.diagnostics
    if mode in (41, 42):
        assert any(m.compensation_applied for m in result.motions if m.cycle_generated)
        assert _coordinates(result.motions) != _coordinates(nominal.motions)
    else:
        assert _coordinates(result.motions) == _coordinates(nominal.motions)
        assert not any(m.compensation_applied for m in result.motions)


@pytest.mark.parametrize("expanded", [False, True])
def test_o0339_facing_export_replays_the_nominal_trace_with_configured_nose(fixture_text, expanded):
    source = fixture_text("turning/basic_turning_cycles.NC").split("G0Z2.", 1)[0] + "\nM30\n"
    source = "\n".join(line for line in source.splitlines() if not line.startswith("G1901"))
    result = execute(
        source,
        language="fanuc_turn",
        tools={"T0909": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.7, "tipOrientation": 3}},
    )
    assert result.ok and result.complete, result.diagnostics
    options = ExportOptions(delimiter=True, leading_zero=True, decimal_places=6)
    output = export_result(result, options) if expanded else export_full_program(result, source.splitlines(), options)
    replay = execute(output, language="fanuc_turn")
    assert replay.ok and replay.complete, replay.diagnostics
    assert len(replay.motions) == len(result.motions)
    for actual, expected in zip(_coordinates(replay.motions), _coordinates(result.motions), strict=True):
        assert actual == pytest.approx(expected, abs=1e-6)
    assert any(m.move == 1 and m.end_x == 214 and m.end_z == pytest.approx(-222.7) for m in replay.motions)
