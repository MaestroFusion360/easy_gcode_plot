"""Complete FANUC milling trajectories, using the O0339 CSV comparison pattern."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.gcode.kernel import execute

GOLDEN = Path(__file__).resolve().parent
ROOT = GOLDEN.parents[2]
FIXTURES = ROOT / "tests/fixtures/milling/fanuc"
HEADER = (
    "move",
    "start_x",
    "start_y",
    "start_z",
    "end_x",
    "end_y",
    "end_z",
    "arc_plane",
    "center_x",
    "center_y",
    "center_z",
    "radius",
    "sweep",
    "clockwise",
    "full_circle",
)
COUNTS = {
    "wcs_test": 74,
    "macro_b": 14,
    "correction_fanuc": 27,
    "subprogram": 172,
    "terraced_ramp": 13,
    "ramped_surface": 12,
    "macro_boss_milling": 208,
    "macro_hole_milling": 57,
    "multiplane_edges": 9,
    "incremental_xyz_raster": 10,
    "inch_spiral": 6,
    "mixed_ijk_r_planes": 7,
    "helical_bore": 7,
    "radius_arc_ramp": 7,
    "macro_face_milling": 27,
    "tapping_fanuc": 22,
    "polar_drilling": 20,
}
# Public API inputs, independent of GUI settings or comment-based tool discovery.
OPTIONS = {
    "wcs_test": {"wcs_offsets": {54: (0, 0, 0), 55: (200, 0, 10), 56: (0, 200, 20), 57: (200, 200, 30)}},
    "correction_fanuc": {"milling_tools": {"T2": {"type": "mill_flat", "diameter": 8}}},
    "macro_boss_milling": {"milling_tools": {"T2": {"type": "mill_flat", "diameter": 50}}},
    "macro_hole_milling": {"milling_tools": {"T2": {"type": "mill_flat", "diameter": 50}}},
}


def run_fixture(name):
    return execute(
        (FIXTURES / f"{name}.nc").read_text(encoding="utf-8-sig"),
        language="fanuc_mill",
        source_dialect="fanuc",
        source_arc_type=1,
        autodetect_arc_type=False,
        arc_tolerance=0.01,
        home_x=0,
        home_y=0,
        home_z=0,
        **OPTIONS.get(name, {}),
    )


def coordinates(motions):
    rows = []
    for m in motions:
        arc = m.arc
        geometry = (
            (arc.plane, *arc.center, arc.radius, arc.sweep, int(arc.clockwise), int(arc.full_circle))
            if arc
            else (None,) * 8
        )
        rows.append((m.move, m.start_x, m.start_y, m.start_z, m.end_x, m.end_y, m.end_z, *geometry))
    return rows


def assert_same_geometry(actual, expected, name, *, motion_count=None):
    count = COUNTS[name] if motion_count is None else motion_count
    assert len(actual) == len(expected) == count, name
    for index, (motion, reference) in enumerate(zip(actual, expected, strict=True)):
        context = f"{name} motion {index}"
        assert tuple(v is None for v in motion) == tuple(v is None for v in reference), context
        for column in (0, 7, 13, 14):
            assert motion[column] == reference[column], context
        assert tuple(v for v in motion if v is not None) == pytest.approx(
            tuple(v for v in reference if v is not None), abs=1e-8
        ), context


@pytest.mark.parametrize("name", COUNTS)
def test_fanuc_fixture_matches_complete_golden(name):
    result = run_fixture(name)
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert not result.diagnostics, result.diagnostics
    reader = csv.reader((GOLDEN / f"{name}.csv").read_text(encoding="ascii").splitlines())
    assert tuple(next(reader)) == HEADER
    expected = [tuple(float(value) if value else None for value in row) for row in reader]
    assert all(len(row) == len(HEADER) for row in expected)
    assert_same_geometry(coordinates(result.motions), expected, name)
