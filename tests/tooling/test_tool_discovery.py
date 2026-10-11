"""Program-driven tool geometry and non-destructive persistence."""

# pylint: disable=protected-access

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import settings
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.program import parse_program
from app.gcode.stock import TurningStockSpec, TurningStockTimeline
from app.tools import discovery
from app.tools.definitions import DEFAULT_MILLING_TOOL, DEFAULT_TURNING_TOOL
from app.tools.discovery import _scan_source_python, discover_tools
from app.tools.library import ToolLibrary
from app.tools.setup import refresh_setup
from app.ui.windows.main_window_execution import MainWindowExecutionMixin


@pytest.mark.parametrize(
    ("turning", "source"),
    [
        (
            False,
            "(T3 D=6 FLAT END MILL)\nG20\nT03 M6\nG81 X0\n; сверло TOOL\nT7 (DRILL D=.25)\nG21\nT9\nG84 Z-5\n",
        ),
        (
            True,
            "(T0101 OD R0.4)\nG21 T0101\nG32 X20 Z-10\nT0202\nG83 Z-20\n(T0303 ID THREAD)\nT0303\nG76 X15 Z-30\n",
        ),
        (
            False,
            "(nearby BALL END MILL D8)\n\nT1 M6\nT#2\nT[2+3]\nX1 (comment after coordinate)\n(T2 SLOT MILL)\nT2\n",
        ),
        (False, "G21\nG1 X1 Y2\n; файл без инструментов\nM30\n"),
        (False, "G21\nG65 P9000 T7 X10. Y20. Z-5. F100. M8\nT3 M6\n"),
    ],
)
def test_native_discovery_scan_matches_python(turning, source):
    native = pytest.importorskip("app.tools._native_discovery")
    assert native.scan_source(source, turning, 1.0) == _scan_source_python(source, turning, 1.0)


def test_g65_arguments_are_not_discovered_as_machine_tools_or_operations():
    tools = discover_tools(
        "G21\nG65 P9000 T7 X10. Y20. Z-5. F100. M8\nT3 M6 (DRILL D6)\nG81 Z-10\n",
        turning=False,
    )

    assert set(tools) == {"T3"}
    assert tools["T3"]["type"] == "drill"


def test_turning_comment_geometry():
    tools = discover_tools("N1T0909(OD ROUGH R0.8)\nN3 T1111 (ID ROUGH R0.8)\nN2 T0808 (GROOVE H4)", turning=True)
    assert tools["T0909"] == {**DEFAULT_TURNING_TOOL, "noseRadius": 0.8, "description": "OD ROUGH R0.8"}
    assert tools["T1111"]["applications"] == ["id"]
    assert tools["T1111"]["tipOrientation"] == 2
    assert tools["T1111"]["noseRadius"] == 0.8
    assert tools["T0808"]["type"] == "groove"
    assert tools["T0808"]["width"] == 4.0


def test_milling_header_and_operation_comments():
    tools = discover_tools(
        "(T3 D=6. CR=0. - ZMIN=-11. - FLAT END MILL)\nG21\nG90\nT03 M06\n"
        "(SPOT_DRILL , TOOL : UGT0321_008)\n\nN482 T07 M6\n"
        "(UGT0201_105 / MILL_SLOT_PARTIAL_RECT)\nT9 M6",
        turning=False,
    )
    assert tools["T3"]["type"] == "mill_flat"
    assert tools["T3"]["diameter"] == 6
    assert tools["T3"]["cornerRadius"] == 0
    assert tools["T7"]["type"] == "drill"
    assert tools["T9"]["type"] == "mill_flat"
    assert tools["T9"]["description"] == "UGT0201_105 / MILL_SLOT_PARTIAL_RECT"


@pytest.mark.parametrize(
    ("comment", "kind"),
    [
        ("BALL END MILL", "mill_ball"),
        ("FACE MILL", "face_mill"),
        ("CHAMFER MILL", "chamfer_mill"),
        ("SLOT MILL", "slot_mill"),
        ("TAP", "tap"),
        ("FLAT END MILL D=8 CR=1", "mill_bull"),
    ],
)
def test_milling_types(comment, kind):
    spec = discover_tools(f"T7 M6 ({comment})", turning=False)["T7"]
    assert spec["type"] == kind


@pytest.mark.parametrize(
    "comment,kind",
    [
        ("flat-endmill", "mill_flat"),
        ("SQUARE END MILL", "mill_flat"),
        ("ENDMILL", "mill_flat"),
        ("mill_flat", "mill_flat"),
        ("BALLNOSE", "mill_ball"),
        ("BALL_NOSE_END_MILL", "mill_ball"),
        ("SPHERICAL ENDMILL", "mill_ball"),
        ("END_MILL_SPHER", "mill_ball"),
        ("mill_ball", "mill_ball"),
        ("BULLNOSE", "mill_bull"),
        ("CORNER-RADIUS END MILL", "mill_bull"),
        ("RADIUS END MILL", "mill_bull"),
        ("TOROIDAL CUTTER", "mill_bull"),
        ("TAPERED BALLNOSE", "taper_ball_mill"),
        ("TAPER_BALL_MILL", "taper_ball_mill"),
        ("TAPERED BALL END MILL", "taper_ball_mill"),
        ("FACEMILL", "face_mill"),
        ("FACE_MILL", "face_mill"),
        ("SHELL MILL", "face_mill"),
        ("SLOT-MILL", "slot_mill"),
        ("T-SLOT CUTTER", "slot_mill"),
        ("WOODRUFF KEYSEAT CUTTER", "slot_mill"),
        ("DISC MILL", "slot_mill"),
        ("CHAMFER_MILL", "chamfer_mill"),
        ("COUNTERSINK", "chamfer_mill"),
        ("V-BIT", "chamfer_mill"),
        ("SPOT_DRILL", "drill"),
        ("CENTRE DRILL", "drill"),
        ("RIGHT HAND TAP", "tap"),
        ("LEFT-HAND TAP", "tap"),
        ("ТОРЦЕВАЯ ФРЕЗА", "face_mill"),
        ("МЕТЧИК", "tap"),
        ("СВЕРЛО", "drill"),
    ],
)
def test_milling_tool_name_variants(comment, kind):
    assert discover_tools(f"T7 M6 ({comment} D=8)", turning=False)["T7"]["type"] == kind


@pytest.mark.parametrize("python_scanner", [False, True])
@pytest.mark.parametrize("shared_program", [False, True])
def test_toolchange_first_tool_is_face_mill_not_preselected_tap(
    fixture_text, monkeypatch, python_scanner, shared_program
):
    source = fixture_text("milling/fanuc/toolchange.nc")
    if python_scanner:
        monkeypatch.setattr(discovery, "_native_scan_source", None)
    tools = discover_tools(source, turning=False, program=parse_program(source) if shared_program else None)
    assert {key: (spec["type"], spec["diameter"]) for key, spec in tools.items()} == {
        "T1": ("face_mill", 50),
        "T2": ("mill_flat", 8),
        "T3": ("drill", 5),
        "T8": ("tap", 6),
    }
    assert tools["T3"]["tipAngle"] == 118


@pytest.mark.parametrize("change", ["M6", "M06", "M6.0", "M06.000"])
def test_preselected_tool_does_not_inherit_current_tool_cycle(change):
    tools = discover_tools(
        f"T8 {change} (RIGHT HAND TAP D6)\nT1\nG84 Z-5\nG80\nT1 {change} (FACE MILL D50)\nG1 X10", turning=False
    )
    assert tools["T8"]["type"] == "tap"
    assert tools["T1"]["type"] == "face_mill"


def test_milling_comment_shape_parameters_and_dimensions():
    tools = discover_tools(
        "T1 M6 (TAPERED BALLNOSE DIA:6,35MM TAPER=8DEG FL=20 BL=30)\n"
        "T2 M6 (CORNER RADIUS END MILL Ø8 CORNER_RADIUS=1.5)\n"
        "T3 M6 (COUNTERSINK D=12 TIP_DIAMETER=2 CHAMFER_ANGLE=60DEG)\n"
        "T4 M6 (FACE MILL DIAM=50 SHANK_DIA=20)\n"
        "T5 M6 (TWIST DRILL ⌀5 POINT_ANGLE=135DEG)\n",
        turning=False,
    )
    assert tools["T1"]["diameter"] == 6.35
    assert tools["T1"]["taperAngle"] == 8
    assert tools["T1"]["fluteLength"] == 20 and tools["T1"]["bodyLength"] == 30
    assert tools["T2"]["cornerRadius"] == 1.5
    assert tools["T3"]["tipDiameter"] == 2 and tools["T3"]["chamferAngle"] == 60
    assert tools["T4"]["diameter"] == 50 and tools["T4"]["shankDiameter"] == 20
    assert tools["T5"]["diameter"] == 5 and tools["T5"]["tipAngle"] == 135


@pytest.mark.parametrize("turning", [True, False])
def test_defaults_and_non_executable_t_words(turning):
    tools = discover_tools("(T8 DRILL)\n; T9 TAP\nT0\nT10000\nT3.2\nT#1\nT[2+4]\nT07", turning=turning)
    key = "T0007" if turning else "T7"
    assert tools == ({key: DEFAULT_TURNING_TOOL} if turning else {})


def test_units_and_invalid_dimensions():
    tools = discover_tools("G20\nT7 M6 (FLAT END MILL D=.25 CR=.01)\nG21\nT8 M6 (DRILL D=-4)", turning=False)
    assert tools["T7"]["diameter"] == pytest.approx(6.35)
    assert tools["T7"]["cornerRadius"] == pytest.approx(0.254)
    assert tools["T8"]["diameter"] == 10


@pytest.mark.parametrize("dialect", ["fanuc", "sinumerik"])
@pytest.mark.parametrize("change", ["M6", "M06", "M06.000"])
def test_current_program_contains_only_installed_milling_tools(dialect, change):
    source = (
        "(T1 FACE MILL D50)\n(T2 FLAT END MILL D8)\n(T3 DRILL D5)\n"
        f"T1 {change}\nT2\nG1 X10 F100\nT7 (TAP D6)\nT3\n{change}\nT8\nM30\n"
    )
    tools = discover_tools(source, turning=False, source_dialect=dialect)
    assert set(tools) == {"T1", "T3"}
    assert tools["T1"]["type"] == "face_mill"
    assert tools["T3"]["type"] == "drill"


def test_named_sinumerik_preselection_is_not_current_program_tool():
    tools = discover_tools(
        'T="FACE" ; FACE MILL D50\nM6\nT="UNUSED" ; TAP D6\nT="BALL" ; BALLNOSE D8\nG0 Z50\nM06\nT="NEXT"\nM30\n',
        turning=False,
        source_dialect="sinumerik",
    )
    assert set(tools) == {"FACE", "BALL"}
    assert tools["FACE"]["type"] == "face_mill"
    assert tools["BALL"]["type"] == "mill_ball"


def test_pending_milling_tool_without_m6_never_creates_a_candidate():
    assert discover_tools("T1 (FACE MILL D50)\nG1 X10 F100\nT2 (TAP D6)\nM30", turning=False) == {}


def test_turning_t_words_remain_immediate_without_m6():
    tools = discover_tools("T0101 (OD R0.8)\nG1 X20\nT0202 (ID R0.4)\nM30", turning=True)
    assert set(tools) == {"T0101", "T0202"}


def test_milling_cycle_context_selects_default_drill_and_tap_geometry():
    tools = discover_tools(
        "T1 M6\nG1 X1\nT2 M6\nG81 X0 Y0 Z-5\nT3 M6\nG84 X0 Y0 Z-5",
        turning=False,
    )

    assert tools["T1"] == DEFAULT_MILLING_TOOL
    assert tools["T2"]["type"] == "drill"
    assert tools["T2"]["diameter"] == 10.0
    assert tools["T3"]["type"] == "tap"
    assert tools["T3"]["diameter"] == 10.0


@pytest.mark.parametrize("cycle", ["G32", "G33", "G76", "G92"])
def test_turning_thread_cycles_select_default_od_thread(cycle):
    tools = discover_tools(f"T0101\n{cycle} X20 Z-10 F1", turning=True)

    assert tools["T0101"]["type"] == "thread"
    assert tools["T0101"]["applications"] == ["od"]


def test_turning_cycle_context_preserves_default_and_selects_drill_and_tap():
    tools = discover_tools("T0101\nG1 X20\nT0202\nG83 Z-20\nT0303\nG84 Z-20", turning=True)

    assert tools["T0101"] == DEFAULT_TURNING_TOOL
    assert tools["T0202"]["type"] == "drill"
    assert tools["T0202"]["diameter"] == 10.0
    assert tools["T0303"]["type"] == "tap"
    assert tools["T0303"]["diameter"] == 10.0


def test_cycle_operation_selects_type_while_comment_supplies_dimensions():
    tools = discover_tools("T7 M6 (FLAT END MILL D6)\nG81 Z-5", turning=False)

    assert tools["T7"]["type"] == "drill"
    assert tools["T7"]["diameter"] == 6.0


def test_operation_hints_respect_preselection_and_subprogram_header():
    source = (
        "O1\nT1 M6 (DRILL D6)\nT2\nG81 Z-5\nG80\nT2 M6 (FLAT END MILL D10)\nG1 X10\nM30\nO8000 T1\nG81 Z-5\nG80\nM99"
    )
    tools = discover_tools(source, turning=False, program=parse_program(source))
    assert tools["T1"]["type"] == "drill"
    assert tools["T2"]["type"] == "mill_flat"


def test_real_program_fixtures(fixture_text):
    turning = discover_tools(fixture_text("turning/basic_turning_cycles.NC"), turning=True)
    assert turning["T0909"]["noseRadius"] == 0.8
    assert turning["T1111"]["applications"] == ["id"]
    assert turning["T0808"]["type"] == "groove"
    milling = discover_tools(fixture_text("milling/fanuc/plate_setup_complete.nc"), turning=False)
    assert milling["T3"]["type"] == "drill"
    assert "SPOT_DRILL" in milling["T3"]["description"]


def test_discovery_never_overwrites_existing_database_or_session_tools(tmp_path, monkeypatch):
    with ToolLibrary(str(tmp_path / "tools.db")) as library:
        existing = {**DEFAULT_TURNING_TOOL, "noseRadius": 1.2, "description": "User tool"}
        future = {"type": "future_type", "custom": 123}
        library.save_tool("turning", "T0909", existing)
        library.save_tool("turning", "T0808", future)
        before = library.get_tool("turning", "T0909")
        monkeypatch.setattr(settings, "get_tool_library", lambda: library)
        current = {}
        source = "T0909 (OD R0.8)\nT1111 (ID R0.8)\nT0808 (GROOVE H4)"
        previous = refresh_setup(source, current, {}, turning=True)
        assert current["T0909"]["noseRadius"] == 0.8
        assert library.get_tool("turning", "T0909") == before
        assert library.get_tool("turning", "T0808").spec == future
        current["T1111"]["noseRadius"] = 2.0
        snapshot = deepcopy(current)
        refresh_setup(source, current, previous, turning=True)
        assert current == snapshot
        assert library.get_tool("turning", "T1111") is None


def test_new_program_tool_reaches_kernel_before_execution_and_removes_stock(monkeypatch):
    source = "G18 G21\nT0909 (OD ROUGH R0.8)\nG0 X52 Z0\nG1 X40 F100\nG1 Z-10\nM30"
    observed = []

    def checked_execute(text, **options):
        resolver = options["tool_resolver"]

        def checked_resolver(program):
            tools = resolver(program)
            observed.append(tools["T0909"]["noseRadius"])
            return tools

        options["tool_resolver"] = checked_resolver
        return execute(text, **options)

    monkeypatch.setattr("app.gcode.program_execution.execute", checked_execute)
    window = SimpleNamespace(
        ui=SimpleNamespace(editor=SimpleNamespace(text=lambda: source)),
        latheMode=True,
        tools={},
        xPosMach=0.0,
        yPosMach=0.0,
        zPosMach=0.0,
    )
    result, _points, _render_limited = MainWindowExecutionMixin._calculate_editor_source(window, show_errors=False)
    assert result.ok
    assert observed == [0.8]
    assert settings.get_tool_library().get_tool("turning", "T0909") is None
    timeline = TurningStockTimeline(result.motions, TurningStockSpec(length=20), window.tools)
    initial = timeline.outer.copy()
    timeline.set_motion_count(len(result.motions))
    assert any(new < old for new, old in zip(timeline.outer, initial, strict=True))


@pytest.mark.parametrize(("cycle", "kind"), [(81, "drill"), (82, "drill"), (83, "drill"), (84, "tap")])
def test_sinumerik_cycle_ast_selects_operation_tool(cycle, kind):
    tools = discover_tools(
        f"T2 M6\nMCALL CYCLE{cycle}(5,0,1,-10)\nX0 Y0\nMCALL\n",
        turning=False,
        source_dialect="sinumerik",
    )
    assert tools["T2"]["type"] == kind


def test_sinumerik_cycle_mentions_in_comments_and_messages_are_not_operations():
    tools = discover_tools(
        'T2 M6\n; MCALL CYCLE84(5,0,1,-10)\nMSG("CYCLE83(5,0,1,-10)")\nG1 X10 F100\n',
        turning=False,
        source_dialect="sinumerik",
    )
    assert tools["T2"]["type"] == DEFAULT_MILLING_TOOL["type"]


def test_named_sinumerik_tools_preserve_identity_comments_units_and_cycle_type():
    source = (
        '; T="COMMENT_ONLY"\nMSG("T=IGNORED")\nG700\n'
        'T="Mixed_case" M6 ; FLAT MILL D.25\n'
        'G710\nT="UGT0301_495" M6\nMCALL CYCLE81(5,0,1,-10)\n'
        "T0 M6\nMCALL CYCLE84(5,0,1,-10)\nMCALL\n"
        'T="T04" M6 ; BULL MILL D10 CR2\nT4 M6\n'
    )
    tools = discover_tools(source, turning=False, source_dialect="sinumerik")
    assert set(tools) == {"Mixed_case", "UGT0301_495", "T04", "T4"}
    assert tools["Mixed_case"]["diameter"] == 6.35
    assert tools["UGT0301_495"]["type"] == "drill"
    assert tools["T04"]["type"] == "mill_bull"
    assert tools["T04"]["cornerRadius"] == 2


def test_native_modal_cycle_tracks_tool_changes_and_cancellation():
    tools = discover_tools(
        "T1 M6\nMCALL CYCLE83(5,0,1,-10)\nX0 Y0\nT2 M6\nX10 Y0\nMCALL\nT3 M6\nG1 X20 F100\n",
        turning=False,
        source_dialect="sinumerik",
    )
    assert tools["T1"]["type"] == tools["T2"]["type"] == "drill"
    assert tools["T3"]["type"] == "mill_flat"


def test_python_fallback_discovery_handles_empty_parenthesized_cycle_call():
    source = "N10 T4 M6\nN20 CYCLE800()\nN30 G1 X0 Y0 F100\n"
    headers, occurrences, operations = _scan_source_python(source, False, 1.0)
    assert headers == {}
    assert operations == {}
    assert [key for key, *_ in occurrences] == ["T4"]
