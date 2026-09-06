# pylint: disable=protected-access
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from gcode_samples import MILLING_ARC_PLANES, TURNING_PARTIAL_TRACE

from app import main_window
from app import settings as app_settings
from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace
from app.ui import main_window_execution, main_window_plot
from app.ui.main_window_editor_ops import MainWindowEditorMixin
from app.ui.main_window_execution import MainWindowExecutionMixin
from app.ui.main_window_file_ops import MainWindowFileMixin
from app.ui.window_settings import (
    EDITOR_FONT_FAMILY_KEY,
    EDITOR_FONT_ITALIC_KEY,
    EDITOR_FONT_SIZE_KEY,
    EDITOR_FONT_WEIGHT_KEY,
)


class _Editor:
    def __init__(self, text: str):
        self._text = text

    def text(self):
        return self._text


class _StatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout):
        self.messages.append((message, timeout))


class _ToggleAction:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked


class _Slider:
    def __init__(self, value=1):
        self._value = value

    def value(self):
        return self._value


def _gui_execution_harness(source: str, *, lathe_mode: bool):
    return SimpleNamespace(
        ui=SimpleNamespace(editor=_Editor(source), statusbar=_StatusBar()),
        latheMode=lathe_mode,
        xPosMach=0.0,
        yPosMach=0.0,
        zPosMach=0.0,
    )


def test_gui_executes_editor_source_through_same_kernel_contract():
    window = _gui_execution_harness(MILLING_ARC_PLANES, lathe_mode=False)

    gui_result = main_window.MainWindow._execute_editor_source(
        window,
        show_errors=False,
    )
    direct_result = execute(
        MILLING_ARC_PLANES,
        language="fanuc_mill",
        home_x=0.0,
        home_y=0.0,
        home_z=0.0,
        emulate_g28_home=True,
    )

    assert gui_result.ok == direct_result.ok
    assert gui_result.motions == direct_result.motions
    assert gui_result.diagnostics == direct_result.diagnostics


def test_gui_forwards_xyz_wcs_tools_and_g28_configuration_to_kernel(monkeypatch):
    captured = {}
    expected = SimpleNamespace(ok=True, diagnostics=(), motions=())

    def fake_execute(source, **kwargs):
        captured["source"] = source
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(main_window_execution, "execute", fake_execute)
    tools = {"T0101": {"type": "turning", "noseRadius": 0.4, "tipOrientation": 1}}
    offsets = {54: (10.0, 20.0, -2.0)}
    window = SimpleNamespace(
        ui=SimpleNamespace(editor=_Editor("G54\nG1 X20 Y30 Z-5"), statusbar=_StatusBar()),
        latheMode=False,
        xPosMach=100.0,
        yPosMach=200.0,
        zPosMach=50.0,
        homeConfigured=False,
        defaultUnits="inch",
        wcsOffsets=offsets,
        tools=tools,
    )

    result = main_window.MainWindow._execute_editor_source(window, show_errors=False)

    assert result is expected
    assert captured["language"] == "fanuc_mill"
    assert captured["default_unit_scale"] == 25.4
    assert captured["tools"] == tools
    assert captured["wcs_offsets"] == offsets
    assert captured["home_x"] == 100.0
    assert captured["home_y"] == 200.0
    assert captured["home_z"] == 50.0
    assert captured["emulate_g28_home"] is False


def test_tool_settings_normalization_matches_turning_kernel_keys():
    raw = {
        "101": {"type": "turning", "noseRadius": 0.4, "tipOrientation": 1},
        "T2": {"type": "drill", "description": "  center   drill "},
        "bad": {"type": "turning", "noseRadius": 0.4, "tipOrientation": 1},
        "T0303": {"type": "turning", "noseRadius": 0.0, "tipOrientation": 3},
    }

    assert main_window._normalized_tools(raw) == {
        "T0101": {"type": "turning", "noseRadius": 0.4, "tipOrientation": 1},
        "T0002": {"type": "drill", "description": "center drill"},
    }


def test_editor_font_persistence_uses_existing_font_keys():
    assert (
        EDITOR_FONT_FAMILY_KEY,
        EDITOR_FONT_SIZE_KEY,
        EDITOR_FONT_WEIGHT_KEY,
        EDITOR_FONT_ITALIC_KEY,
    ) == ("FONT_FAMILY", "FONT_SIZE", "FONT_WEIGHT", "FONT_ITALIC")


def test_milling_tool_settings_normalization_matches_cnceditor_geometry_rules():
    raw = {
        "1": {"type": "mill_flat", "diameter": 10, "cornerRadius": 2, "length": 50},
        "T2": {"type": "mill_bull", "diameter": 12, "cornerRadius": 1.5, "length": 60},
        "T0003": {"type": "mill_ball", "diameter": 8, "cornerRadius": 99, "length": 45},
        "4": {"type": "drill", "diameter": 6, "cornerRadius": 1, "length": 70, "description": "  center   drill "},
        "T100": {"type": "mill_flat", "diameter": 10, "length": 20},
        "bad": {"type": "mill_flat", "diameter": 10, "length": 20},
        "T5": {"type": "unknown", "diameter": 10, "length": 20},
    }

    assert main_window._normalized_milling_tools(raw) == {
        "T1": {
            "type": "mill_flat",
            "diameter": 10.0,
            "cornerRadius": 0.0,
            "length": 50.0,
        },
        "T2": {
            "type": "mill_bull",
            "diameter": 12.0,
            "cornerRadius": 1.5,
            "length": 60.0,
        },
        "T3": {
            "type": "mill_ball",
            "diameter": 8.0,
            "cornerRadius": 4.0,
            "length": 45.0,
        },
        "T4": {
            "type": "drill",
            "diameter": 6.0,
            "cornerRadius": 0.0,
            "length": 70.0,
            "description": "center drill",
        },
    }


def test_gui_keeps_partial_turning_trace_renderable_when_kernel_reports_unsupported_cycle():
    execution_window = _gui_execution_harness(
        TURNING_PARTIAL_TRACE,
        lathe_mode=True,
    )
    result = main_window.MainWindow._execute_editor_source(
        execution_window,
        show_errors=False,
    )

    captured = []
    cleared = []

    window = SimpleNamespace(
        _execute_editor_source=lambda *, show_errors: result,
        clearPlot=lambda: cleared.append(True),
        _finishDataUpdate=lambda result=None, points=None: captured.append(result),
    )

    assert main_window.MainWindow.updateData(window) is True
    assert cleared == []
    assert captured == [result]
    assert result.ok is False
    assert [(motion.end_x, motion.end_z) for motion in result.motions] == pytest.approx(
        [(20, 5), (18, 2), (30, 10), (25, 0)]
    )


def test_grid_toggle_changes_state_and_refreshes_current_plot_position():
    action_grid = _ToggleAction(False)
    slider = _Slider(5)

    redraws = []
    recreated_trace_items = []
    refreshed = []

    window = SimpleNamespace(
        ui=SimpleNamespace(
            actionGrid=action_grid,
            horizontalSlider=slider,
        ),
        plotGrid=True,
        execution_result=SimpleNamespace(motions=[object()]),
        loadPlot=lambda: redraws.append(True),
        _create_trace_items=lambda: recreated_trace_items.append(True),
        valueHandler=lambda value: refreshed.append(value),
    )

    main_window.MainWindow.gridChecked(window)
    assert window.plotGrid is False

    action_grid.setChecked(True)
    main_window.MainWindow.gridChecked(window)
    assert window.plotGrid is True

    assert redraws == [True, True]
    assert recreated_trace_items == [True, True]
    assert refreshed == [5, 5]


def test_rapid_and_cutting_segments_are_split_by_motion_type():
    result = execute("G0 X10 Y0 Z0\nG1 X20 Y0 Z0 F100\nM30", language="fanuc_mill")
    assert result.ok
    points = render_trace(result)
    window = SimpleNamespace(execution_result=result, render_points=points)

    rapid, cutting, arcs = main_window.MainWindow._trace_segment_vertices(window, len(points))

    assert rapid == [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    assert cutting == [(10.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
    assert arcs == []


def test_trace_cursor_is_fixed_pixel_size_and_rapid_has_own_item(monkeypatch):
    created_lines = []
    created_scatters = []

    class _LineItem:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created_lines.append(self)

    class _ScatterItem:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created_scatters.append(self)

        def setGLOptions(self, value):
            self.gl_options = value

    class _View:
        def __init__(self):
            self.items = []

        def addItem(self, item):
            self.items.append(item)

    monkeypatch.setattr(main_window_plot, "GLLinePlotItem", _LineItem)
    monkeypatch.setattr(main_window_plot, "GLScatterPlotItem", _ScatterItem)
    window = SimpleNamespace(
        plotRapidColor="#110000",
        plotLineColor="#001100",
        plotArcColor="#000011",
        plotCurrentColor="#111111",
        plotLineWidth=2.5,
        ui=SimpleNamespace(graphicsView=_View()),
    )

    main_window.MainWindow._create_trace_items(window)

    assert len(created_lines) == 3
    assert [item.kwargs["color"].name() for item in created_lines] == ["#110000", "#001100", "#000011"]
    assert all(item.kwargs["width"] == 2.5 for item in created_lines)
    assert created_lines[0].kwargs["mode"] == "lines"
    assert created_scatters[0].kwargs["size"] == main_window.CURSOR_SIZE_PX
    assert created_scatters[0].kwargs["pxMode"] is True
    assert created_scatters[0].kwargs["color"].name() == "#111111"


def test_2d_picking_selects_nearest_motion_and_source_line():
    selected = []
    synced = []
    messages = []

    class _Position:
        def x(self):
            return 5.0

        def y(self):
            return 1.0

    class _Slider:
        def setValue(self, value):
            selected.append(value)

    points = [
        SimpleNamespace(x=0.0, y=0.0, z=0.0, motion_index=0),
        SimpleNamespace(x=10.0, y=0.0, z=0.0, motion_index=0),
        SimpleNamespace(x=20.0, y=0.0, z=0.0, motion_index=1),
    ]
    result = SimpleNamespace(motions=[SimpleNamespace(source_block=4), SimpleNamespace(source_block=5)])
    window = SimpleNamespace(
        latheMode=False,
        _view_mode="top",
        render_points=points,
        execution_result=result,
        ui=SimpleNamespace(
            horizontalSlider=_Slider(),
            statusbar=SimpleNamespace(showMessage=lambda message, timeout: messages.append((message, timeout))),
        ),
        _project_world_to_screen=lambda x, y, z: (x, y),
        _sync_editor_to_motion=lambda index: synced.append(index),
    )

    assert main_window.MainWindow._pick_trace_at(window, _Position()) is True
    assert selected == [1]
    assert synced == [0]
    assert "line 5" in messages[0][0]


def test_picking_is_disabled_in_3d_view():
    window = SimpleNamespace(latheMode=False, _view_mode="3d", render_points=[object()])
    position = SimpleNamespace(x=lambda: 0.0, y=lambda: 0.0)
    assert main_window.MainWindow._pick_trace_at(window, position) is False


def test_recent_files_are_unique_case_insensitively_and_limited():
    recent = main_window._normalized_recent_files(
        ["C:/A.nc", "c:/a.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc", "C:/F.nc"]
    )
    assert recent == ["C:/A.nc", "C:/B.nc", "C:/C.nc", "C:/D.nc", "C:/E.nc"]


class _DropUrl:
    def __init__(self, path, *, local=True):
        self._path = path
        self._local = local

    def isLocalFile(self):
        return self._local

    def toLocalFile(self):
        return self._path


class _DropEvent:
    def __init__(self, urls):
        self._mime = SimpleNamespace(hasUrls=lambda: bool(urls), urls=lambda: urls)
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def test_drop_event_opens_first_local_file_only():
    opened = []

    class Window(MainWindowFileMixin):
        def maybeSave(self):
            return True

        def loadFile(self, fileName):
            opened.append(fileName)

    event = _DropEvent(
        [
            _DropUrl("https://example.invalid/program.nc", local=False),
            _DropUrl("C:/first.nc"),
            _DropUrl("C:/second.nc"),
        ]
    )

    Window().dropEvent(event)

    assert opened == ["C:/first.nc"]
    assert event.accepted is True
    assert event.ignored is False


def test_auto_update_schedule_invalidates_previous_trace_before_debounce():
    calls = []

    class Timer:
        def stop(self):
            calls.append("stop")

        def start(self):
            calls.append("start")

    class Window(MainWindowExecutionMixin):
        def __init__(self):
            self.autoUpdateTimer = Timer()
            self.execution_result = object()
            self.render_points = [object()]

        def clearPlot(self):
            calls.append("clear")
            self.execution_result = None
            self.render_points = []

    Window().scheduleAutoUpdate()

    assert calls == ["stop", "clear", "start"]


def test_remove_spaces_preserves_multiple_parenthesized_comments():
    class Window(MainWindowEditorMixin):
        def __init__(self):
            self.transformed = None

        def _process_selected_lines(self, handler):
            self.transformed = handler(["G1 X1 (first comment) Y2 (second comment) F100\n"])

    window = Window()
    window.removeSpaces()

    assert window.transformed == ["G1X1(first comment)Y2(second comment)F100\n"]


def test_application_logging_toggle_creates_and_closes_project_handler(monkeypatch, tmp_path):
    monkeypatch.setattr(app_settings, "_config_dir", lambda: str(tmp_path))
    app_settings.configure_logging(False)
    app_settings.configure_logging(True)
    logging.getLogger("easy_gcode_plot.test").warning("logging-regression")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "logging-regression" in (tmp_path / "main.log").read_text(encoding="utf-8")
    app_settings.configure_logging(False)
    assert not any(getattr(handler, "_easy_gcode_plot_handler", False) for handler in logging.getLogger().handlers)
