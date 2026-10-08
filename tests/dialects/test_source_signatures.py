"""Controller signatures for unsaved pasted programs, with comment exclusions."""

import pytest

from app.gcode.source_mode import source_dialect_for_path


@pytest.mark.parametrize(
    "code",
    [
        "G0 SUPA Z0",
        "CIP X1 I1=0 J1=1",
        "MCALL CYCLE81(5,0,2,-10)",
        "CYCLE800()",
        "TRANS X1",
        "ATRANS Z1",
        "ROT Z90",
        "AROT Y30",
        "RPL=10",
        "SCALE X2",
        "ASCALE Y2",
        "MIRROR X0",
        "AMIRROR Y0",
        "CYCLE840()",
        "POCKET4()",
        "HOLES1()",
        "SLOT2()",
        "LONGHOLE()",
        "G291",
    ],
)
def test_unnamed_native_signatures(code):
    assert source_dialect_for_path(None, "N10 " + code) == "sinumerik"
    assert source_dialect_for_path(None, "N10" + code) == "sinumerik"
    assert source_dialect_for_path("", "n10 " + code.lower()) == "sinumerik"


@pytest.mark.parametrize(
    "source",
    [
        "; SUPA\nG0 X1",
        "(CIP X1 I1=0)\nG1 X2",
        'MSG("SUPA; CYCLE800")',
        'T="TRANS"',
        "_TRANS=1",
        "G83 X1 Z-2 R1 Q1",
        "G0X1Y2",
        "",
        "SUPAX=1",
    ],
)
def test_comments_strings_and_common_iso_do_not_switch_dialect(source):
    assert source_dialect_for_path(None, source) == "fanuc"


def test_named_container_retains_existing_contract():
    assert source_dialect_for_path("part.nc", "SUPA Z0") == "fanuc"
    assert source_dialect_for_path("part.mpf", "G0 X1") == "sinumerik"
