"""Turning starter fragments cover the selected controller's source vocabulary."""

from pathlib import Path

import pytest

from app.gcode.kernel import execute
from app.gcode.snippets.snippet_defaults import default_snippets
from app.gcode.snippets.snippet_templates import TemplateContext, parameters, render


def test_type_b_program_start_restores_absolute_coordinates_after_incremental_mode():
    templates = dict(default_snippets("fanuc_b_turn"))
    start = render(templates["Program Start"]).text
    move = render(templates["Rapid Move"]).text
    result = execute(
        "G21 G90 G0 X40 Z5\nG91\n" + start + move + "M30\n",
        language="fanuc_turn",
        lathe_gcode_system="B",
    )
    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((40, 5))


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_b_turn"])
def test_fanuc_turning_catalog_contains_profile_groove_and_simple_cycles(language):
    templates = dict(default_snippets(language))
    expected_codes = (
        (70, 71, 72, 73, 74, 75, 76, 77, 78, 79)
        if language == "fanuc_b_turn"
        else (70, 71, 72, 73, 74, 75, 76, 90, 92, 94)
    )
    context = TemplateContext(file=Path(__file__))
    rendered = "\n".join(render(body, context=context).text for body in templates.values())
    for code in expected_codes:
        assert any(line.startswith(f"G{code} ") for line in rendered.splitlines()), code


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_b_turn", "sinumerik_turn"])
def test_turning_catalog_exposes_dwell_threading_and_plane(language):
    templates = dict(default_snippets(language))
    assert "Dwell (G4)" in templates
    assert f"Threading (G{32 if language == 'fanuc_turn' else 33})" in templates
    plane = next(parameter for parameter in parameters(templates["Circular Move"]) if parameter.name == "Plane")
    assert plane.default == "18"
    assert plane.choices == ("17", "18", "19")
    assert render(templates["Circular Move"], {"Plane": "19"}).text.startswith("G19 ")


@pytest.mark.parametrize(
    "language,home_command",
    [
        ("fanuc_turn", "G28 W0"),
        ("fanuc_b_turn", "G28 G91 Z0"),
        ("sinumerik_turn", "SUPA G0 Z0 D0"),
    ],
)
def test_turning_program_end_reuses_z_only_home_return(language, home_command):
    templates = dict(default_snippets(language))
    assert home_command in render(templates["Retract Home Z"]).text
    assert home_command in render(templates["Program End"]).text
    assert "SafeZ" not in {parameter.name for parameter in parameters(templates["Program End"])}
