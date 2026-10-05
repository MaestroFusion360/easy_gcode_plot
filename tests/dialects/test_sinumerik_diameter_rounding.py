"""Diameter words remain warning-only; CR arcs follow native source semantics."""

import pytest

from app.gcode.export.resolved import convert_resolved_program
from app.gcode.kernel import execute


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


@pytest.mark.parametrize("mode", ["DIAMON", "DIAMOF", "DIAM90"])
def test_diameter_words_warn_without_scaling_or_stopping(mode):
    result = native(f"G0 X10\n{mode} G1 X20 F100\nX30\nM30")
    assert result.ok and result.complete
    assert [m.end_x for m in result.motions] == [10, 20, 30]
    assert result.diagnostics[0].code == "IGNORED_SINUMERIK_DIAMETER_MODE"
    assert result.diagnostics[0].severity == "warning"


def test_rndm_keeps_sharp_corners_and_warns_on_setting_and_cancel():
    result = native("G0 X0 Y0\nG1 X10 RNDM=-.375 F100\nY10\nX=IC(.375) RNDM=0\nM30")
    assert result.ok and result.complete
    assert [d.code for d in result.diagnostics] == ["UNMODELED_SINUMERIK_RNDM"] * 2
    assert all(m.arc is None for m in result.motions)
    assert result.motions[-1].end_x == 10.375


def test_optional_diameter_and_rounding_words_do_not_warn_when_skipped():
    result = native("/DIAMON\n/G1 X10 RNDM=3\nG0 X20\nM30", skip_optional_blocks=True)
    assert result.ok and not result.diagnostics


@pytest.mark.parametrize("scale", [1.0, 25.4])
@pytest.mark.parametrize("skip", [False, True])
def test_supplied_guide_radius_arcs_complete_with_bounded_warnings(fixture_text, scale, skip):
    result = native(
        fixture_text("milling/sinumerik/sinumerik_guide_radius.mpf"),
        default_unit_scale=scale,
        skip_optional_blocks=skip,
    )
    assert result.ok and result.complete, result.diagnostics
    arcs = [m.arc for m in result.motions if m.arc is not None]
    assert [a.radius for a in arcs] == pytest.approx([2 * scale, 3 * scale, 2 * scale, 3 * scale, 2 * scale])
    assert {d.code for d in result.diagnostics} <= {"UNVERIFIED_CUTTER_COMPENSATION", "UNMODELED_SINUMERIK_RNDM"}
    assert len([m for m in result.motions if m.source_kind == "cycle" and m.move == 1]) == 3


def test_cr_error_reproduces_when_native_program_is_selected_as_fanuc():
    source = "G1 X1 Y2 F30\nG2 X1.5476 Y3.375 CR=2\nM30"
    assert native(source).ok
    assert not execute(source, language="fanuc_mill").ok


def test_ic_linear_addresses_cannot_be_misinterpreted_in_machine_frame():
    result = native("SUPA G0 X=IC(10)")
    assert not result.ok and result.diagnostics[-1].code == "UNSUPPORTED_SINUMERIK_IC_RETURN"


@pytest.mark.parametrize("word", ["CHF", "CHR", "RND", "RNDM", "FRC", "FRCM"])
def test_corner_and_feed_words_are_lexical_metadata_only(word):
    source = f"G0 X0\nG1 X10 {word}=R99 F100\nY10\nM30"
    result = native(source)
    assert result.ok and result.complete
    assert [m.end_x for m in result.motions] == [10, 10]
    assert all(m.feed == 100 and m.arc is None for m in result.motions)
    assert [d.code for d in result.diagnostics] == [f"UNMODELED_SINUMERIK_{word}"]
    assert result.program.blocks[1].parsed_words[-2].letter == word
    with pytest.raises(ValueError, match="ignored SINUMERIK"):
        convert_resolved_program(result)
