from __future__ import annotations

import hashlib
from pathlib import Path

import gcode_samples

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_FIXTURES = {
    "milling/contur_2d.nc",
    "milling/macro_b.nc",
    "milling/macro_boss_milling.nc",
    "milling/macro_face_milling.nc",
    "milling/macro_hole_milling.nc",
    "milling/subprogram.nc",
    "milling/wcs_test.nc",
    "turning/basic_turning_cycles.NC",
    "turning/compensation_control_off.nc",
    "turning/compensation_control_on.nc",
    "turning/drill.nc",
    "turning/thread.nc",
}


def _normalized(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_fixture_corpus_is_explicit_unique_and_uses_supported_nc_files_only():
    files = sorted(path for path in FIXTURES.rglob("*") if path.is_file())
    actual = {path.relative_to(FIXTURES).as_posix() for path in files}
    assert actual == EXPECTED_FIXTURES
    assert {path.suffix.lower() for path in files} == {".nc"}

    hashes = [
        hashlib.sha256(_normalized(path.read_text(encoding="utf-8-sig")).encode("utf-8")).hexdigest() for path in files
    ]
    assert len(hashes) == len(set(hashes))


def test_compact_gcode_samples_do_not_duplicate_fixture_programs():
    fixture_programs = {_normalized(path.read_text(encoding="utf-8-sig")) for path in FIXTURES.rglob("*.nc")}
    compact_programs = {
        _normalized(value)
        for name, value in vars(gcode_samples).items()
        if name.isupper() and isinstance(value, str) and "\n" in value
    }

    assert fixture_programs.isdisjoint(compact_programs)
