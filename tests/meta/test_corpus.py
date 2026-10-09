from __future__ import annotations

import hashlib
from pathlib import Path

import gcode_samples

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPECTED_FIXTURES = {
    "milling/fanuc/smpl_sim08_5ax_fanuc_mm.nc",
    "milling/sinumerik/smpl_sim08_5ax_sinumerik_mm.mpf",
    "milling/fanuc/test_5ax_ac_fanuc.nc",
    "milling/fanuc/test_5ax_bc_fanuc.nc",
    "milling/sinumerik/test_5ax_ac_sin840d.mpf",
    "milling/sinumerik/test_5ax_bc_sin840d.mpf",
    "milling/sinumerik/5ax_test.mpf",
    "milling/sinumerik/macro_drilling.mpf",
    "milling/sinumerik/impeller.mpf",
    "milling/fanuc/contur_2d.nc",
    "milling/fanuc/correction_fanuc.nc",
    "milling/sinumerik/correction_ijk_sin840d.mpf",
    "milling/sinumerik/correction_sin840d.mpf",
    "milling/fanuc/flange_plate_benchmark.nc",
    "milling/fanuc/g68_2_cube.nc",
    "milling/fanuc/helical_bore.nc",
    "milling/fanuc/inch_spiral.nc",
    "milling/fanuc/incremental_xyz_raster.nc",
    "milling/fanuc/impeller.ptp",
    "milling/fanuc/impeller2.ptp",
    "milling/fanuc/indexed_table_a.nc",
    "milling/fanuc/indexed_table_b.nc",
    "milling/fanuc/indexed_table_c.nc",
    "milling/fanuc/macro_b.nc",
    "milling/fanuc/macro_boss_milling.nc",
    "milling/fanuc/macro_face_milling.nc",
    "milling/fanuc/macro_hole_milling.nc",
    "milling/fanuc/macro_thread_milling.nc",
    "milling/fanuc/Machine_tool_simulation.ptp",
    "milling/fanuc/Machine_tool_simulation_BC.ptp",
    "milling/fanuc/mixed_ijk_r_planes.nc",
    "milling/fanuc/multiplane_edges.nc",
    "milling/fanuc/plate_setup_complete.nc",
    "milling/fanuc/polar_drilling.nc",
    "milling/fanuc/radius_arc_ramp.nc",
    "milling/fanuc/ramped_surface.nc",
    "milling/fanuc/subprogram.nc",
    "milling/sinumerik/sinumerik_traori_ac.mpf",
    "milling/sinumerik/sinumerik_cycle800.mpf",
    "milling/sinumerik/sinumerik_cam_setup.mpf",
    "milling/sinumerik/sinumerik_guide_radius.mpf",
    "milling/sinumerik/sinumerik_cut3dc_unsupported.mpf",
    "milling/sinumerik/contur_2d_sin840d.mpf",
    "milling/fanuc/cycles_fanuc.nc",
    "milling/sinumerik/cycles_sin840d.mpf",
    "milling/sinumerik/ext_cycles.mpf",
    "milling/sinumerik/no_ext_cycles.mpf",
    "milling/sinumerik/text_NX.mpf",
    "milling/fanuc/tapping_fanuc.nc",
    "milling/sinumerik/tapping_sin840d.mpf",
    "milling/fanuc/terraced_ramp.nc",
    "milling/fanuc/toolchange.nc",
    "milling/fanuc/wcs_test.nc",
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
    "turning/simple_programming.nc",
    "turning/lathe_cycles_example.nc",
    "turning/lathe_cycles_example_expanded.nc",
    "turning/lathe_cnc_macro_test.nc",
    "turning/taper_thread.nc",
}


def _fixture_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251")


def _normalized(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_fixture_corpus_is_explicit_unique_and_uses_supported_program_files_only():
    files = sorted(path for path in FIXTURES.rglob("*") if path.is_file())
    actual = {path.relative_to(FIXTURES).as_posix() for path in files}
    assert actual == EXPECTED_FIXTURES
    assert {path.suffix.lower() for path in files} == {".nc", ".ptp", ".mpf"}

    hashes = [hashlib.sha256(_normalized(_fixture_text(path)).encode("utf-8")).hexdigest() for path in files]
    assert len(hashes) == len(set(hashes))


def test_compact_gcode_samples_do_not_duplicate_fixture_programs():
    fixture_programs = {
        _normalized(_fixture_text(path))
        for path in FIXTURES.rglob("*")
        if path.is_file() and path.suffix.lower() in {".nc", ".ptp", ".mpf"}
    }
    compact_programs = {
        _normalized(value)
        for name, value in vars(gcode_samples).items()
        if name.isupper() and isinstance(value, str) and "\n" in value
    }

    assert fixture_programs.isdisjoint(compact_programs)
