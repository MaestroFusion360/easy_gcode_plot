from __future__ import annotations

import hashlib
from pathlib import Path

import gcode_samples

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPECTED_FIXTURES = {
    "milling/contur_2d.nc",
    "milling/flange_plate_benchmark.nc",
    "milling/g68_2_cube.nc",
    "milling/helical_bore.nc",
    "milling/inch_spiral.nc",
    "milling/incremental_xyz_raster.nc",
    "milling/impeller.ptp",
    "milling/impeller2.ptp",
    "milling/indexed_table_a.nc",
    "milling/indexed_table_b.nc",
    "milling/indexed_table_c.nc",
    "milling/macro_b.nc",
    "milling/macro_boss_milling.nc",
    "milling/macro_face_milling.nc",
    "milling/macro_hole_milling.nc",
    "milling/macro_thread_milling.nc",
    "milling/Machine_tool_simulation.ptp",
    "milling/Machine_tool_simulation_BC.ptp",
    "milling/mixed_ijk_r_planes.nc",
    "milling/multiplane_edges.nc",
    "milling/plate_setup_complete.nc",
    "milling/polar_drilling.nc",
    "milling/radius_arc_ramp.nc",
    "milling/ramped_surface.nc",
    "milling/subprogram.nc",
    "milling/contur_2d_sin840d.mpf",
    "milling/cycles_fanuc.nc",
    "milling/cycles_sin840d.mpf",
    "milling/tapping_fanuc.nc",
    "milling/tapping_sin840d.mpf",
    "milling/terraced_ramp.nc",
    "milling/toolchange.nc",
    "milling/wcs_test.nc",
    "turning/basic_turning_cycles.NC",
    "turning/compensation_control_off.nc",
    "turning/compensation_control_on.nc",
    "turning/cycle71_ID.nc",
    "turning/drill.nc",
    "turning/thread.nc",
    "turning/face_groove.nc",
    "turning/od_rough_finish.nc",
    "turning/oem_header.nc",
    "turning/radius_profile.nc",
    "turning/taper_thread.nc",
}


def _normalized(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_fixture_corpus_is_explicit_unique_and_uses_supported_program_files_only():
    files = sorted(path for path in FIXTURES.rglob("*") if path.is_file())
    actual = {path.relative_to(FIXTURES).as_posix() for path in files}
    assert actual == EXPECTED_FIXTURES
    assert {path.suffix.lower() for path in files} == {".nc", ".ptp", ".mpf"}

    hashes = [
        hashlib.sha256(_normalized(path.read_text(encoding="utf-8-sig")).encode("utf-8")).hexdigest() for path in files
    ]
    assert len(hashes) == len(set(hashes))


def test_compact_gcode_samples_do_not_duplicate_fixture_programs():
    fixture_programs = {
        _normalized(path.read_text(encoding="utf-8-sig"))
        for path in FIXTURES.rglob("*")
        if path.is_file() and path.suffix.lower() in {".nc", ".ptp", ".mpf"}
    }
    compact_programs = {
        _normalized(value)
        for name, value in vars(gcode_samples).items()
        if name.isupper() and isinstance(value, str) and "\n" in value
    }

    assert fixture_programs.isdisjoint(compact_programs)
