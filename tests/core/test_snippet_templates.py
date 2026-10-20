"""Independent template values, degree-based math and literal insertion boundaries."""

import re
from datetime import datetime

import pytest

from app.gcode.kernel import execute
from app.gcode.snippets.snippet_defaults import default_snippets
from app.gcode.snippets.snippet_templates import TemplateContext, TemplateError, formula, parameters, render


def test_context_literals_share_one_instant_and_only_read_existing_document_paths(tmp_path):
    file = tmp_path / "part.h"
    file.touch()
    context = TemplateContext(file, "L X10\nL Y20", datetime(2026, 10, 19, 8, 9, 10))
    source = "{{date}} {{time}} {{datetime}} {{date:DD.MM.YYYY}} {{time:HH:mm}}\n"
    source += "{{file.name}}|{{file.stem}}|{{file.path}}|{{file.dir}}\n{{selection}}"
    result = render(source, context=context)
    assert result.text == (
        "2026-10-19 08:09:10 2026-10-19 08:09:10 19.10.2026 08:09\n"
        f"part.h|part|{file.resolve()}|{tmp_path.resolve()}\nL X10\nL Y20"
    )
    file.unlink()
    with pytest.raises(TemplateError, match="File no longer exists"):
        render("{{file.path}}", context=context)
    with pytest.raises(TemplateError, match="Save the document first"):
        render("{{file.name}}")


def test_named_fields_are_prompted_once_and_allow_forward_references_and_decimal_comma():
    source = "X{{D}} (D={{?D=10|D, mm}}) Y{{D}} S{{=1000*Vc/(PI*D):0}} (Vc={{?Vc=120}})"
    assert [(p.name, p.default, p.label) for p in parameters(source)] == [("D", "10", "D, mm"), ("Vc", "120", "Vc")]
    assert render(source, {"D": "12,5", "Vc": "100"}).text == "X12.5 (D=12.5) Y12.5 S2546 (Vc=100)"
    assert render("T{{?Tool=0101}}").text == "T0101"


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("SIN(30)", 0.5),
        ("COS(60)", 0.5),
        ("TAN(45)", 1),
        ("ASIN(0.5)", 30),
        ("ACOS(0.5)", 60),
        ("ATAN(1)", 45),
        ("ATAN2(1,-1)", 135),
        ("TO_MM(1)", 25.4),
        ("TO_INCH(25.4)", 1),
        ("TO_DEG(PI)", 180),
        ("TO_RAD(180)", 3.141592653589793),
        ("ABS(-4)+SQRT(9)", 7),
        ("ROUND(1.234,2)", 1.23),
        ("MIN(5,3,8)+MAX(2,4)", 7),
        ("2^3 + 5%2", 9),
        ("(10/2)/TAN(118/2)", 3.004303095137801),
    ],
)
def test_formula_functions_are_independent_of_cnc_variable_syntax(expression, expected):
    assert formula(expression, {}) == pytest.approx(expected)


@pytest.mark.parametrize(
    "source",
    [
        "{{=1/0}}",
        "{{=SQRT(-1)}}",
        "{{=TAN(90)}}",
        "{{=2^101}}",
        "{{=__import__('os').getcwd()}}",
        "{{=(1).__class__}}",
        "{{=[1,2][0]}}",
        "{{=sum(x for x in [1,2])}}",
        "{{=UNKNOWN(1)}}",
        "{{=True}}",
        "{{?D=abc}} {{=D+1}}",
        "{{?D}}",
        "{{unknown}}",
        "{{date}",
        "{{cursor}}{{cursor}}",
        "{{?D=1}}{{?D=2}}",
        "{{?date=1}}",
        "{{=1:99}}",
    ],
)
def test_errors_never_return_partially_expanded_source(source):
    with pytest.raises(TemplateError):
        render("G0 X100\n" + source)


def test_cursor_uses_character_offsets_and_inserted_values_are_never_reinterpreted():
    source = "{{?Text=hello}} {{cursor}}X{{?X=2}}"
    result = render(source, {"Text": "Привет {{=1/0}}", "X": "3"})
    assert result.text == "Привет {{=1/0}} X3"
    assert result.cursor == len("Привет {{=1/0}} ")


def test_ordinary_cnc_variables_and_plain_snippets_are_unchanged():
    source = "#1=2\nR1=3\nQ1=4\nL X+10\n"
    assert render(source).text == source
    assert render(source).cursor is None


@pytest.mark.parametrize("depth", ["2", "3"])
def test_drilling_depth_must_be_below_forward_referenced_retract_plane(depth):
    source = "Z{{?Z=-20|number|lt=R}} R{{?R=2|number}}"
    assert render(source).text == "Z-20 R2"
    with pytest.raises(TemplateError, match="Value out of range"):
        render(source, {"Z": depth})


def test_retract_clearance_bound_uses_supplied_reference_plane_and_safety_distance():
    source = "{{?RTP=5|number|min=RFP+SDIS}},{{?RFP=0|number}},{{?SDIS=2|number|min=0}}"
    assert render(source, {"RTP": "12", "RFP": "10"}).text == "12,10,2"
    with pytest.raises(TemplateError, match="Value out of range"):
        render(source, {"RTP": "11", "RFP": "10"})


@pytest.mark.parametrize(
    "values,expected",
    [({"DP": "-20", "DPR": ""}, "-20,,0"), ({"DP": "", "DPR": "20"}, ",20,0")],
)
def test_absolute_or_relative_depth_keeps_empty_cycle_argument(values, expected):
    source = "{{?DP=-20|number|optional|oneof=DPR|lt=RFP}},{{?DPR=|number|optional|oneof=DP|gt=0}},{{?RFP=0|number}}"
    assert render(source, values).text == expected
    with pytest.raises(TemplateError, match="Missing value"):
        render(source, {"DP": "", "DPR": ""})


@pytest.mark.parametrize("value", ["1.5", "-1", "100"])
def test_tool_number_rejects_fractional_and_out_of_range_values(value):
    source = "T{{?Tool=1|int|min=0|max=99|width=2}}"
    assert render(source).text == "T01"
    with pytest.raises(TemplateError):
        render(source, {"Tool": value})


def test_cycle_return_mode_only_accepts_supported_integer_choices():
    source = "G{{?ReturnMode=98|int|choices=98,99}}"
    assert render(source).text == "G98"
    assert render(source, {"ReturnMode": "99"}).text == "G99"
    with pytest.raises(TemplateError, match="Invalid choice"):
        render(source, {"ReturnMode": "97"})


def test_optional_spindle_speed_omits_prefix_until_value_is_supplied():
    source = "{{?RPM=|int|optional|min=1|prefix=S}} M3"
    assert render(source).text == " M3"
    assert render(source, {"RPM": "500"}).text == "S500 M3"
    with pytest.raises(TemplateError, match="Value out of range"):
        render(source, {"RPM": "0"})


@pytest.mark.parametrize(
    "name,values,expected",
    [
        ("Rapid Move", {"X": "20", "Y": "-10", "Z": "0"}, "L X+20 Y-10 Z+0 R0 FMAX\n"),
        ("Linear Move", {"X": "-20", "Y": "10.5", "Z": "2"}, "L X-20 Y+10.5 Z+2 R0 F300\n"),
        ("Circular Move", {"X": "10", "Y": "-5", "Z": "0", "R": "-10"}, "CR X+10 Y-5 Z+0 R-10 DR+ F300\n"),
    ],
)
def test_itnc_motion_templates_explicitly_sign_positive_negative_and_zero_coordinates(name, values, expected):
    source = dict(default_snippets("heidenhain"))[name]
    assert render(source, values).text == expected


@pytest.mark.parametrize(
    "name,source", [(name, source) for name, source in default_snippets("heidenhain") if "CYCL DEF" in source]
)
def test_itnc_cycle_templates_explicitly_sign_every_numeric_q_parameter(name, source):
    text = render(source).text
    assignments = re.findall(r"\bQ\d+=([^\s;]+)", text)
    assert assignments, name
    assert all(value.startswith(("+", "-")) for value in assignments), (name, assignments)


@pytest.mark.parametrize("family", ["fanuc_mill", "sinumerik_mill"])
@pytest.mark.parametrize("plane", [17, 18, 19])
def test_milling_circular_template_selects_plane_and_preserves_xyz(family, plane):
    source = dict(default_snippets(family))["Circular Move"]
    values = {"Plane": str(plane), "X": "10", "Y": "10", "Z": "10", "R": "10"}
    text = render(source, values).text
    assert text.startswith(f"G{plane} G3 X10 Y10 Z10 ")
    result = execute(
        "G21 G90 G0 X0 Y0 Z0\n" + text + "M30\n",
        language="fanuc_mill",
        source_dialect="sinumerik" if family == "sinumerik_mill" else "fanuc",
    )
    assert result.ok and result.complete, result.diagnostics
    arc = result.motions[-1]
    assert arc.plane == plane
    assert (arc.end_x, arc.end_y, arc.end_z) == pytest.approx((10, 10, 10))


@pytest.mark.parametrize("family", ["fanuc_mill", "sinumerik_mill"])
def test_milling_circular_template_defaults_to_xy_and_rejects_other_planes(family):
    source = dict(default_snippets(family))["Circular Move"]
    assert render(source).text.startswith("G17 G3 ")
    with pytest.raises(TemplateError, match="Invalid choice"):
        render(source, {"Plane": "20"})


@pytest.mark.parametrize("family", ["fanuc_mill", "sinumerik_mill", "heidenhain"])
def test_milling_program_end_retracts_to_machine_home_without_safe_z_input(family):
    snippets = dict(default_snippets(family))
    source = snippets["Program End"]
    assert render(source).text.startswith(render(snippets["Retract Home Z"]).text)
    assert "SafeZ" not in {field.name for field in parameters(source)}


@pytest.mark.parametrize("family,address", [("fanuc_mill", "X"), ("sinumerik_mill", "F")])
def test_milling_dwell_template_uses_controller_seconds_address(family, address):
    source = dict(default_snippets(family))["Dwell (G4)"]
    assert render(source).text == f"G4 {address}1\n"
    assert render(source, {"Seconds": "0.25"}).text == f"G4 {address}0.25\n"
    assert render(source, {"Seconds": "0"}).text == f"G4 {address}0\n"
    with pytest.raises(TemplateError, match="Value out of range"):
        render(source, {"Seconds": "-0.1"})
