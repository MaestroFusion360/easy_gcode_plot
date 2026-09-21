"""Program-driven tool geometry and non-destructive persistence."""

# pylint: disable=protected-access

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import settings
from app.gcode.kernel import execute
from app.gcode.stock import TurningStockSpec, TurningStockTimeline
from app.tools.definitions import DEFAULT_MILLING_TOOL, DEFAULT_TURNING_TOOL
from app.tools.discovery import _scan_source_python, discover_tools
from app.tools.library import ToolLibrary
from app.tools.setup import refresh_setup
from app.ui.windows import main_window_execution
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


@pytest.mark.parametrize("turning", [True, False])
def test_defaults_and_non_executable_t_words(turning):
    tools = discover_tools("(T8 DRILL)\n; T9 TAP\nT0\nT10000\nT3.2\nT#1\nT[2+4]\nT07", turning=turning)
    key = "T0007" if turning else "T7"
    assert tools == {key: DEFAULT_TURNING_TOOL if turning else DEFAULT_MILLING_TOOL}


def test_units_and_invalid_dimensions():
    tools = discover_tools("G20\nT7 (FLAT END MILL D=.25 CR=.01)\nG21\nT8 (DRILL D=-4)", turning=False)
    assert tools["T7"]["diameter"] == pytest.approx(6.35)
    assert tools["T7"]["cornerRadius"] == pytest.approx(0.254)
    assert tools["T8"]["diameter"] == 10


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


def test_explicit_tool_comment_overrides_cycle_fallback():
    tools = discover_tools("T7 M6 (FLAT END MILL D6)\nG81 Z-5", turning=False)

    assert tools["T7"]["type"] == "mill_flat"
    assert tools["T7"]["diameter"] == 6.0


def test_real_program_fixtures(fixture_text):
    turning = discover_tools(fixture_text("turning/basic_turning_cycles.NC"), turning=True)
    assert turning["T0909"]["noseRadius"] == 0.8
    assert turning["T1111"]["applications"] == ["id"]
    assert turning["T0808"]["type"] == "groove"
    milling = discover_tools(fixture_text("milling/plate_setup_complete.nc"), turning=False)
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
        observed.append(options["tools"]["T0909"]["noseRadius"])
        return execute(text, **options)

    monkeypatch.setattr(main_window_execution, "execute", checked_execute)
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
