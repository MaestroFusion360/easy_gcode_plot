"""Native iTNC goldens; unique module name also permits full-suite collection."""

import csv
import math

import pytest
from test_fanuc import GOLDEN, HEADER, ROOT, assert_same_geometry, coordinates

from app.gcode.kernel import execute

FIXTURES = ROOT / "tests/fixtures/milling/heidenhain"
REFERENCE = GOLDEN / "heidenhain"
COUNTS = {"bore_itnc530": 18, "itnc530_base_pgm": 12, "6bas154": 20, "manual_chf": 18}
OPTIONS = {
    "cycles_itnc530": {"home_z": 100, "emulate_g28_home": True},
    # A nominal reference preserves all CP turns; compensated CP is tested below.
    "bore_itnc530": {
        "milling_tools": {"T1": {"type": "mill_flat", "diameter": 6}},
        "milling_correction_enabled": False,
    },
    # No cutter diameter is specified by this source; retain the nominal contour.
    "itnc530_base_pgm": {"milling_correction_enabled": False},
    "6bas154": {"milling_tools": {"T4": {"type": "mill_flat", "diameter": 6}}},
    "manual_chf": {"milling_tools": {"T1": {"type": "mill_flat", "diameter": 6}}},
}
ENDS = {"bore_itnc530": "M30", "itnc530_base_pgm": None, "6bas154": "M30", "manual_chf": "M2"}
DIAGNOSTICS = {
    "bore_itnc530": (("HEIDENHAIN_SMOOTHING_NOT_SIMULATED", "warning", "unverified", 19),),
    "itnc530_base_pgm": (),
    "6bas154": (),
    "manual_chf": (),
    "cycles_itnc530": (
        ("HEIDENHAIN_M140_HOME_EMULATION", "warning", "unverified", 8),
        ("HEIDENHAIN_SMOOTHING_NOT_SIMULATED", "warning", "unverified", 21),
    ),
}


def run_fixture(name, **overrides):
    options = {"home_x": 0, "home_y": 0, "home_z": 0, **OPTIONS[name], **overrides}
    return execute(
        (FIXTURES / f"{name}.h").read_text(encoding="utf-8-sig"),
        language="fanuc_mill",
        source_dialect="heidenhain",
        source_arc_type=1,
        autodetect_arc_type=False,
        arc_tolerance=0.01,
        **options,
    )


def assert_execution(result, name, end):
    assert result.ok and result.complete and result.program_end == end, result.diagnostics
    assert tuple((d.code, d.severity, d.status, d.line) for d in result.diagnostics) == DIAGNOSTICS[name]


@pytest.mark.parametrize("name", COUNTS)
def test_itnc_fixture_matches_complete_golden(name):
    result = run_fixture(name)
    assert_execution(result, name, ENDS[name])
    reader = csv.reader((REFERENCE / f"{name}.csv").read_text(encoding="ascii").splitlines())
    assert tuple(next(reader)) == HEADER
    expected = [tuple(float(value) if value else None for value in row) for row in reader]
    assert all(len(row) == len(HEADER) for row in expected)
    assert_same_geometry(coordinates(result.motions), expected, name, motion_count=COUNTS[name])


def test_bore_compensation_preserves_programmed_cp_turns():
    result = run_fixture("bore_itnc530", milling_correction_enabled=True)
    assert_execution(result, "bore_itnc530", "M30")
    arcs = [m.arc for m in result.motions if m.arc is not None]
    assert len(arcs) == 6
    assert [a.radius for a in arcs] == pytest.approx([4, 4, 4, 7, 7, 7], abs=1e-8)
    assert [a.sweep for a in arcs] == pytest.approx(
        [math.radians(degrees) for degrees in (5400, 2699.969, 360, 2834.989, 2834.989, 360)], abs=1e-8
    )


def test_cycles_last_200_keeps_its_programmed_one_mm_pecks():
    result = run_fixture("cycles_itnc530")
    assert_execution(result, "cycles_itnc530", "M30")
    # Both calls use the last CYCL DEF 200 with Q202=1, no decrement.
    expected_depths = [-1 - depth for depth in range(1, 17)] + [-17.262]
    for label, x in ((52, -25), (53, 25)):
        feeds = [m for m in result.motions if m.move == 1 and (m.source_raw or "").startswith(f"{label} ")]
        assert feeds and all((m.end_x, m.end_y) == (x, 10) for m in feeds)
        assert [m.end_z for m in feeds] == pytest.approx(expected_depths, abs=1e-8)
