"""Independent numeric corner references from 737759-23, pp. 237, 238, 244."""

import math
from pathlib import Path

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import checkpoint
from app.gcode.kernel.frontend.ast import _build_program_ast_python
from app.gcode.kernel.frontend.heidenhain import parse_heidenhain_program

FIXTURES = Path(__file__).parents[1] / "fixtures/milling/heidenhain"
TOOLS = {"T4": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}}


def run(source, **options):
    return execute(source, "fanuc_mill", source_dialect="heidenhain", **options)


def point(motion, end=False):
    return (motion.end_x, motion.end_y, motion.end_z) if end else (motion.start_x, motion.start_y, motion.start_z)


def corners(result):
    return [
        m
        for m in result.motions
        if ("RND " in (m.source_raw or "") or "CHF " in (m.source_raw or ""))
        and m.source_kind != "cutter_compensation_transition"
    ]


def continuous(motions):
    for first, second in zip(motions, motions[1:]):
        assert point(first, True) == pytest.approx(point(second), abs=1e-7)


def test_official_six_roundings_and_compensated_tool_center():
    source = (FIXTURES / "6bas154.h").read_text(encoding="utf-8")
    raw = run(source, milling_correction_enabled=False)
    assert raw.ok and raw.complete and raw.program_end == "M30", raw.diagnostics
    # Independent line-line construction: trim = R*tan(turn/2).
    vertices = [(10, 90), (70, 90), (90, 50), (90, 10), (50, 10), (10, 50)]
    path = [(10, 70), *vertices, (10, 70)]
    radii = [10, 5, 5, 10, 5, 5]
    rounded = corners(raw)
    assert len(rounded) == 6
    for i, (motion, vertex, radius) in enumerate(zip(rounded, vertices, radii)):
        v1 = tuple(vertex[j] - path[i][j] for j in range(2))
        v2 = tuple(path[i + 2][j] - vertex[j] for j in range(2))
        u, v = [tuple(x / math.hypot(*w) for x in w) for w in (v1, v2)]
        angle = math.acos(sum(u[j] * v[j] for j in range(2)))
        trim = radius * math.tan(angle / 2)
        start = tuple(vertex[j] - trim * u[j] for j in range(2))
        end = tuple(vertex[j] + trim * v[j] for j in range(2))
        center = (start[0] + u[1] * radius, start[1] - u[0] * radius, -5)
        assert point(motion) == pytest.approx((*start, -5))
        assert point(motion, True) == pytest.approx((*end, -5))
        assert motion.arc.center == pytest.approx(center)
        assert motion.arc.radius == pytest.approx(radius)
        assert motion.arc.sweep == pytest.approx(angle)
        assert motion.arc.clockwise and motion.compensation_mode == 41
        assert motion.feed == 400 and not motion.compensation_applied
    continuous(raw.motions)
    result = run(source, milling_tools=TOOLS)
    assert result.ok and result.complete, result.diagnostics
    continuous(result.motions)
    # APPR/DEP R3 each collapse to a point for the explicitly configured R3 cutter.
    assert len(result.motions) == len(raw.motions) - 2
    for programmed, compensated in zip(rounded, corners(result)):
        assert compensated.compensation_applied
        assert compensated.arc.center == pytest.approx(programmed.arc.center)
        assert compensated.arc.radius == pytest.approx(programmed.arc.radius + 3)
        center = programmed.arc.center
        for is_end in (False, True):
            p = point(programmed, is_end)
            expected = tuple(
                center[j] + (p[j] - center[j]) * (programmed.arc.radius + 3) / programmed.arc.radius for j in range(3)
            )
            assert point(compensated, is_end) == pytest.approx(expected)
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)
    index = 0
    for step in result.execution_steps:
        assert all(m.source_block == step.source_block for m in result.motions[index : index + step.emitted_count])
        index += step.emitted_count


@pytest.mark.parametrize("mode,offset", [("R0", 0), ("RL", -3), ("RR", 3)])
def test_official_multiple_chamfers(mode, offset):
    source = (FIXTURES / "manual_chf.h").read_text(encoding="utf-8").replace(" RL ", f" {mode} ")
    result = run(source, milling_tools={"T1": TOOLS["T4"]})
    assert result.ok, result.diagnostics
    first, second = corners(result)
    # Chamfer 10 cuts (95,95) at (85,95)/(95,85), not a 10 mm diagonal.
    if mode == "RL":
        shift = 3 / math.sqrt(2)
        expected = [
            (85 + shift, 95 + shift),
            (95 + shift, 85 + shift),
            (95 + shift, 25 - shift),
            (75 + shift, 5 - shift),
        ]
    else:
        shift = -offset * (math.sqrt(2) - 1)
        expected = [
            (85 + shift, 95 - offset),
            (95 - offset, 85 + shift),
            (95 - offset, 25 - shift),
            (75 + shift, 5 + offset),
        ]
    for motion, start, end in ((first, expected[0], expected[1]), (second, expected[2], expected[3])):
        assert point(motion) == pytest.approx((*start, -5))
        assert point(motion, True) == pytest.approx((*end, -5))
    assert first.arc is None and second.arc is None
    continuous(result.motions)


@pytest.mark.parametrize("mode,radius", [("R0", 5), ("RL", 2), ("RR", 8)])
def test_rounding_modes_and_block_local_feeds(mode, radius):
    source = (
        f"TOOL CALL 4 Z\nL X0 Y-10 R0 F100\nL X0 Y0 {mode}\nL X20 Y0\n"
        "RND R5 F50\nL X20 Y20 F200\nCHF 3 F75\nL X0 Y20\nL X-10 Y20 R0"
    )
    result = run(source, milling_tools=TOOLS)
    assert result.ok, result.diagnostics
    rounded, chamfered = corners(result)
    assert rounded.arc.radius == pytest.approx(radius)
    assert rounded.arc.center == pytest.approx((15, 5, 0))
    assert rounded.feed == 50 and chamfered.feed == 75
    after = [m for m in result.motions if m.source_raw == "L X0 Y20"]
    assert all(m.feed == 200 for m in after)
    continuous(result.motions)


@pytest.mark.parametrize("mode", ["R0", "RL", "RR"])
@pytest.mark.parametrize(
    "prefix,following,start,end,center",
    [
        (
            "L X0 Y0 F100\nL X20 Y0",
            "CC X10 Y0\nC X10 Y10 DR+",
            (10 + math.sqrt(60), 0),
            (10 + math.sqrt(60) * 1.25, 2.5),
            (10 + math.sqrt(60), 2),
        ),
        (
            "L X0 Y-10 F100\nCC X0 Y0\nC X10 Y0 DR+",
            "L X20 Y0",
            (math.sqrt(140) / 1.2, -2 / 1.2),
            (math.sqrt(140), 0),
            (math.sqrt(140), -2),
        ),
        (
            "L X0 Y-10 F100\nCC X0 Y0\nC X10 Y0 DR+",
            "CC X10 Y10\nC X20 Y10 DR+",
            ((5 + math.sqrt(47)) / 1.2, (5 - math.sqrt(47)) / 1.2),
            (10 + (math.sqrt(47) - 5) / 1.2, 10 + (-5 - math.sqrt(47)) / 1.2),
            (5 + math.sqrt(47), 5 - math.sqrt(47)),
        ),
    ],
)
def test_rounding_line_arc_arc_line_and_arc_arc(prefix, following, start, end, center, mode):
    prefix = "TOOL CALL 4 Z\n" + prefix.replace(" F100", f" F100 {mode}")
    result = run(prefix + "\nRND R2\n" + following, milling_tools={"T4": {"type": "mill_flat", "diameter": 1}})
    assert result.ok, result.diagnostics
    (rounded,) = corners(result)
    side = {"R0": 0, "RL": 0.5, "RR": -0.5}[mode]
    radius = 2 + side if rounded.arc.clockwise else 2 - side
    for actual, programmed in ((point(rounded), start), (point(rounded, True), end)):
        expected = tuple(center[i] + (programmed[i] - center[i]) * radius / 2 for i in range(2))
        assert actual == pytest.approx((*expected, 0))
    assert rounded.arc.center == pytest.approx((*center, 0))
    assert rounded.arc.radius == pytest.approx(radius)
    continuous(result.motions)


@pytest.mark.parametrize("form,parameters", [("LT", "LEN5"), ("LN", "LEN5"), ("CT", "R5 CCA90"), ("LCT", "R5")])
@pytest.mark.parametrize("modifier", ["", "RND R2", "CHF 2"])
@pytest.mark.parametrize("compensated", [False, True])
def test_approach_departure_geometry_preserved(form, parameters, modifier, compensated):
    def program(corner):
        return (
            f"TOOL CALL 4 Z\nL X-20 Y-20 R0 F100\nAPPR {form} X0 Y0 {parameters} RL F300\n"
            f"L X0 Y20\n{corner}\nL X20 Y20\nDEP {form} X40 Y40 {parameters}\nL Z50 R0 FMAX"
        )

    tools = {"T4": {"type": "mill_flat", "diameter": 1}}
    reference = run(program(""), milling_correction_enabled=compensated, milling_tools=tools)
    result = run(program(modifier), milling_correction_enabled=compensated, milling_tools=tools)
    assert result.ok and reference.ok, result.diagnostics
    for command in ("APPR", "DEP"):
        expected = [m for m in reference.motions if command in m.source_raw]
        actual = [m for m in result.motions if command in m.source_raw]
        assert actual == expected
    continuous(result.motions)


@pytest.mark.parametrize(
    "source,line",
    [
        ("RND R2\nL X20 Y20", 1),
        ("L X20 Y0 F100\nRND R2", 2),
        ("L X20 Y0 F100\nRND R2\nM30", 2),
        ("L X20 Y0 F100\nRND R30\nL X20 Y20", 2),
        ("L X20 Y0 F100\nCHF 30\nL X20 Y20", 2),
        ("L X20 Y0 F100\nCHF -1\nL X20 Y20", 2),
        ("L X20 Y0 F100\nRND R0\nL X20 Y20", 2),
        ("L X20 Y0 F100\nRND R2\nL X40 Y0", 2),
        ("L X20 Y0 F100\nCHF 2\nL X0 Y0", 2),
        ("L X20 Y0 F100\nRND R2\nL X20 Y0", 2),
        ("L X20 Y0 F100\nL X20 Y0\nRND R2\nL X20 Y20", 3),
        ("L X20 Y0 F100\nCHF 2\nRND R2\nL X20 Y20", 2),
        ("L X20 Y0 F100\nCHF 2\nCC X10 Y0\nC X10 Y10 DR+", 2),
        ("L X20 Y0 F100\nRND R2\nL X20 Y20 RL", 2),
        ("L X20 Y0 F100\nRND R2\nL X20 Y20 FMAX", 2),
        ("L X20 Y0 F100\nRND R2\nL X20 Y20 Z5", 2),
        ("L X20 F100\nRND R2\nL X20 Y20", 2),
        ("L X20 Y0 F100\nRND R12\nL X20 Y20\nRND R12\nL X0 Y20", 4),
    ],
)
def test_invalid_geometry_is_reported_at_modifier_without_fake_motions(source, line):
    result = run(source, milling_correction_enabled=False)
    assert not result.ok and not result.complete
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "INVALID_HEIDENHAIN_CORNER"
    assert diagnostic.line == line
    assert diagnostic.raw == source.splitlines()[line - 1]
    assert not any(m.source_block == line - 1 for m in result.motions)


def test_official_positional_chf_expression_and_source_columns():
    program = parse_heidenhain_program("  / 12 CHF +Q1 F250")
    block = program.blocks[0]
    length = block.native_syntax.word("L")
    assert length.expression.source == "+Q1"
    assert block.raw[length.column : length.column + len(length.source)] == "+Q1"
    result = run("Q1=3\nL X20 Y0 F100\nCHF Q1 F50\nL X20 Y20")
    assert result.ok, result.diagnostics
    (chamfer,) = corners(result)
    assert point(chamfer) == pytest.approx((17, 0, 0))
    assert point(chamfer, True) == pytest.approx((20, 3, 0))
    assert chamfer.feed == 50 and result.motions[-1].feed == 100


def test_official_skew_chamfer_side_lengths_and_temporary_feed():
    # 737759-23 p. 237, the four-block example, replayed without compensation.
    source = "L X0 Y30 R0 F300 M3\nL X40 IY5\nCHF 12 F250\nL IX5 Y0"
    result = run(source)
    assert result.ok, result.diagnostics
    (chamfer,) = corners(result)
    assert point(chamfer) == pytest.approx((40 - 96 / math.sqrt(65), 35 - 12 / math.sqrt(65), 0))
    assert point(chamfer, True) == pytest.approx((40 + 12 / math.sqrt(50), 35 - 84 / math.sqrt(50), 0))
    assert math.dist(point(chamfer), (40, 35, 0)) == pytest.approx(12)
    assert math.dist(point(chamfer, True), (40, 35, 0)) == pytest.approx(12)
    assert chamfer.feed == 250 and result.motions[-1].feed == 300
    continuous(result.motions)


@pytest.mark.parametrize(
    "axis,coordinates,center",
    [
        ("Z", ("X20 Y0", "X20 Y20"), (15, 5, 0)),
        ("Y", ("X20 Z0", "X20 Z20"), (15, 0, 5)),
        ("X", ("Y20 Z0", "Y20 Z20"), (0, 15, 5)),
    ],
)
@pytest.mark.parametrize("units,scale", [("MM", 1), ("INCH", 25.4)])
@pytest.mark.parametrize("mode", ["R0", "RL", "RR"])
def test_rounding_planes_units_and_nonmodal_zero_feed(axis, coordinates, center, units, scale, mode):
    source = (
        f"BEGIN PGM A {units}\nTOOL CALL 4 {axis}\nL {coordinates[0]} {mode} F100\n"
        f"RND R5 F0\nL {coordinates[1]}\nEND PGM A {units}"
    )
    result = run(source, milling_tools={"T4": {"type": "mill_flat", "diameter": 2 * scale}})
    assert result.ok, result.diagnostics
    (rounded,) = corners(result)
    assert rounded.arc.center == pytest.approx(tuple(c * scale for c in center))
    offset = {"R0": 0, "RL": 1, "RR": -1}[mode]
    radius = 5 + offset if axis == "Y" else 5 - offset
    assert rounded.arc.radius == pytest.approx(radius * scale)
    assert rounded.arc.sweep == pytest.approx(math.pi / 2)
    assert rounded.feed == 0 and result.motions[-1].feed == 100 * scale
    assert [(d.code, d.line) for d in result.diagnostics] == [("HEIDENHAIN_ZERO_FEED", 4)]
    continuous(result.motions)


@pytest.mark.parametrize("diameter,valid,number", [(3, True, 1), (4, True, 0), (5, False, 0)])
def test_inward_rounding_tool_radius_limit(diameter, valid, number):
    source = "TOOL CALL 4 Z\nL X0 Y-10 R0 F100\nL X0 Y0 RL\nL X20 Y0\nRND R2\nL X20 Y20\nL X30 Y20 R0"
    result = run(source, milling_tools={"T4": {"type": "mill_flat", "diameter": diameter}})
    assert result.ok is valid
    assert len(corners(result)) == number
    if valid:
        continuous(result.motions)
        if number:
            assert corners(result)[0].arc.radius == pytest.approx(2 - diameter / 2)
        else:
            assert any(point(m, True) == pytest.approx((18, 2, 0)) for m in result.motions)
    else:
        diagnostic = result.diagnostics[-1]
        assert diagnostic.code == "HEIDENHAIN_CORNER_TOOL_TOO_LARGE" and diagnostic.line == 5
        assert result.execution_steps[-1].stop


def test_repeated_native_corners_preserve_each_execution_owner():
    source = "L X0 Y0 F100\nLBL 1\nL IX20 IY0\nRND R2\nL IX0 IY20\nCHF 2\nL IX-20 IY0\nLBL 0\nCALL LBL 1\nM30"
    result = run(source)
    assert result.ok and result.complete, result.diagnostics
    continuous(result.motions)
    assert len(corners(result)) == 4
    assert point(result.motions[-1], True) == pytest.approx((0, 40, 0))
    index = 0
    for step in result.execution_steps:
        owned = result.motions[index : index + step.emitted_count]
        assert all(m.source_block == step.source_block for m in owned)
        if step.source_block in (3, 5):
            assert len(owned) == 1
        index += step.emitted_count
    assert index == len(result.motions)


def test_corner_ast_matches_python_and_compiled_builders():
    program = parse_heidenhain_program("Q1=2\nL X20 Y0 F100\nCHF Q1 F50\nL X20 Y20\nRND R3\nL X0 Y20")
    expected = _build_program_ast_python(program.blocks)
    assert program.ast == expected
    native = pytest.importorskip("app.gcode.kernel.frontend._native_parser")
    assert native.build_program_ast_native(program.blocks, checkpoint) == expected
