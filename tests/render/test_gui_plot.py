# pylint: disable=protected-access
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QMatrix4x4
from PyQt6.QtWidgets import QApplication
from window_state_helpers import window_namespace

from app import main_window
from app.gcode.kernel import execute
from app.gcode.trace import render_trace
from app.ui.plot.stock_overlay import STOCK_COLOR, TOOL_COLOR, TurningStockOverlayItem
from app.ui.support.widgets import Editor
from app.ui.windows import main_window_plot


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_picked_source_line_is_visible_without_editor_focus(qt_app):
    editor = Editor()
    editor.resize(400, 120)
    editor.setText("\n".join(f"G1 X{index}" for index in range(200)))
    editor.setCaretLineVisible(True)
    editor.show()
    qt_app.processEvents()
    owner = SimpleNamespace(
        execution_result=SimpleNamespace(motions=[SimpleNamespace(source_block=150)]),
        ui=SimpleNamespace(editor=editor),
    )
    try:
        main_window.MainWindow._sync_editor_to_motion(owner, 0)
        assert editor.getCursorPosition() == (150, 0)
        assert editor.SendScintilla(editor.SCI_GETCARETLINEVISIBLEALWAYS)
        visible_lines = editor.SendScintilla(editor.SCI_LINESONSCREEN)
        assert editor.firstVisibleLine() <= 150 < editor.firstVisibleLine() + visible_lines
        editor.setFirstVisibleLine(0)
        main_window.MainWindow._sync_editor_to_motion(owner, 0)
        assert editor.firstVisibleLine() > 0
        assert not owner._syncing_cursor
    finally:
        editor.close()
        editor.deleteLater()


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


def test_turning_insert_is_unlit_gold_without_changing_stock_material(qt_app):
    overlay = TurningStockOverlayItem()
    tool_color = QColor(TOOL_COLOR)

    assert tool_color.red() > 220
    assert tool_color.green() > 170
    assert tool_color.blue() < 100
    assert overlay._tool_mesh.opts["color"] == tool_color
    assert overlay._tool_mesh.opts["shader"] is None
    assert overlay._stock_mesh.opts["color"] == QColor(STOCK_COLOR)
    assert overlay._stock_mesh.opts["shader"] == "shaded"


def test_grid_toggle_changes_state_and_refreshes_current_plot_position():
    action_grid = _ToggleAction(False)
    slider = _Slider(5)

    redraws = []
    recreated_trace_items = []
    refreshed = []

    window = window_namespace(
        ui=SimpleNamespace(
            actionGrid=action_grid,
            horizontalSlider=slider,
        ),
        plotGrid=True,
        execution_result=SimpleNamespace(motions=[object()]),
        loadPlot=lambda: redraws.append(True),
        _create_trace_items=lambda: recreated_trace_items.append(True),
        valueHandler=lambda value, **kwargs: refreshed.append((value, kwargs)),
    )

    main_window.MainWindow.gridChecked(window)
    assert window.plotGrid is False

    action_grid.setChecked(True)
    main_window.MainWindow.gridChecked(window)
    assert window.plotGrid is True

    assert redraws == [True, True]
    assert recreated_trace_items == [True, True]
    assert refreshed == [(5, {"sync_editor": False}), (5, {"sync_editor": False})]


def test_trace_cursor_is_fixed_pixel_size_and_toolpath_uses_one_vbo_item(monkeypatch):
    created_toolpaths = []
    created_scatters = []

    class _ToolpathItem:
        def __init__(self):
            created_toolpaths.append(self)

        def set_segments(self, segments, logical_count):
            self.segments = tuple(segments)
            self.logical_count = logical_count

        def set_style(self, **kwargs):
            self.style = kwargs

        def update_dashes_for_view(self):
            pass

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

    monkeypatch.setattr(main_window_plot, "ToolpathVboItem", _ToolpathItem)
    monkeypatch.setattr(main_window_plot, "GLScatterPlotItem", _ScatterItem)
    result = execute("G0 X10\nG1 X20 F100\nM30", language="fanuc_mill")
    window = window_namespace(
        execution_result=result,
        render_points=render_trace(result),
        plotRapidColor="#110000",
        plotLineColor="#001100",
        plotArcColor="#000011",
        plotCurrentColor="#111111",
        plotLineWidth=2.5,
        ui=SimpleNamespace(graphicsView=_View()),
    )

    main_window.MainWindow._create_trace_items(window)

    assert len(created_toolpaths) == 1
    assert created_toolpaths[0].logical_count == 2
    assert [segment.move for segment in created_toolpaths[0].segments] == [0, 1]
    assert created_toolpaths[0].style == {
        "rapid_color": "#110000",
        "linear_color": "#001100",
        "arc_color": "#000011",
        "width": 2.5,
        "show_rapid": True,
        "dashed_rapid": True,
        "color_by_tool": False,
    }
    assert created_scatters[0].kwargs["size"] == main_window.CURSOR_SIZE_PX
    assert created_scatters[0].kwargs["pxMode"] is True
    assert created_scatters[0].kwargs["color"].name() == "#111111"


def test_2d_picking_selects_nearest_motion_and_source_line(monkeypatch):
    matrix = QMatrix4x4()
    matrix.ortho(0, 20, 20, 0, -1, 1)
    monkeypatch.setattr("app.ui.windows.main_window_plot.view_projection", lambda _view: (matrix, (0, 0, 20, 20)))
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
    result = SimpleNamespace(
        motions=[
            SimpleNamespace(source_block=4, start_x=0, start_y=0, start_z=0, tool=None, move=1),
            SimpleNamespace(source_block=5, start_x=10, start_y=0, start_z=0, tool=None, move=1),
        ]
    )
    window = window_namespace(
        latheMode=False,
        _view_mode="top",
        render_points=points,
        execution_result=result,
        ui=SimpleNamespace(
            graphicsView=None,
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


def test_picking_without_an_execution_result_is_ignored_in_3d_view():
    window = window_namespace(latheMode=False, _view_mode="3d", render_points=[object()])
    position = SimpleNamespace(x=lambda: 0.0, y=lambda: 0.0)
    assert main_window.MainWindow._pick_trace_at(window, position) is False


def test_playback_stop_has_true_zero_motion_state(qt_app):
    window = main_window.MainWindow()
    window.latheMode = False
    window.ui.actionLatheMode.setChecked(False)
    window.ui.editor.setText("G0 X10\nG1 X20 F100\nM30")
    assert window.updateData()
    window.stop()

    assert window.ui.horizontalSlider.minimum() == 0
    assert window.ui.horizontalSlider.value() == 0
    assert window._toolpath_item.visible_segment_count == 0
    window.deleteLater()


def test_turning_stock_removal_uses_stock_toggle_play_stop_and_rebuilds_after_update(qt_app):
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(True)
    window.tools = {
        "T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3},
    }
    window.ui.editor.setText("G18 G90 T0101 M3\nG0 X50 Z0\nG1 X40 Z-20 F100\nM30")
    assert window.updateData()
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 50.0,
            "inner_diameter": 0.0,
            "length": 40.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )

    window.ui.actionStockPlayback.setChecked(True)
    assert not window.ui.actionPlay.isChecked()
    window.ui.actionPlay.setChecked(True)
    assert window._stock_animation_active  # pylint: disable=protected-access
    assert window._stock_item in window.ui.graphicsView.items  # pylint: disable=protected-access
    assert window._toolpath_item not in window.ui.graphicsView.items  # pylint: disable=protected-access
    assert window._stock_tail_item in window.ui.graphicsView.items  # pylint: disable=protected-access

    window.ui.horizontalSlider.setValue(2)
    assert window._stock_timeline.motion_count == 2  # pylint: disable=protected-access
    assert len(window._stock_tail_item.pos) > 0  # pylint: disable=protected-access

    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 52.0,
            "inner_diameter": 0.0,
            "length": 40.0,
            "front_allowance": 3.0,
            "resolution": 1.0,
        }
    )
    assert not window._stock_animation_active  # pylint: disable=protected-access
    assert not window.ui.actionPlay.isChecked()
    assert not window.timer.isActive()
    assert window._toolpath_item in window.ui.graphicsView.items  # pylint: disable=protected-access
    window.settings.sync()
    assert window.settings.value("STOCK/ENABLED", type=bool) is True
    assert window.settings.value("STOCK/DIAMETER", type=float) == 52.0
    assert window.settings.value("STOCK/LENGTH", type=float) == 40.0
    assert window.settings.value("STOCK/FRONT_ALLOWANCE", type=float) == 3.0

    assert window.updateData()
    assert not window._stock_animation_active  # pylint: disable=protected-access
    assert window._toolpath_item in window.ui.graphicsView.items  # pylint: disable=protected-access

    window.ui.actionStockPlayback.setChecked(True)
    assert not window.ui.actionPlay.isChecked()
    window.ui.actionPlay.setChecked(True)
    assert window._stock_animation_active  # pylint: disable=protected-access
    window.stop()
    assert not window._stock_animation_active  # pylint: disable=protected-access
    assert window.ui.horizontalSlider.value() == window.ui.horizontalSlider.maximum()
    assert window._toolpath_item in window.ui.graphicsView.items  # pylint: disable=protected-access
    assert window._toolpath_item.visible_logical_count == window.ui.horizontalSlider.maximum()

    window.ui.actionLatheMode.setChecked(False)
    window.ui.actionPlay.setChecked(True)
    assert not window._stock_animation_active  # pylint: disable=protected-access
    assert window.ui.actionPlay.isChecked()
    window.stop()
    window.deleteLater()


def test_3d_pick_synchronizes_selected_execution_occurrence(monkeypatch):
    matrix, viewport = QMatrix4x4(), (0, 0, 100, 100)
    monkeypatch.setattr("app.ui.windows.main_window_plot.view_projection", lambda _view: (matrix, viewport))
    motions = [
        SimpleNamespace(start_x=-0.8, start_y=0, start_z=z, move=1, tool=None, source_block=12) for z in (0.5, -0.5)
    ]
    points = [
        SimpleNamespace(x=x, y=0, z=z, motion_index=index) for index, z in enumerate((0.5, -0.5)) for x in (-0.8, 0.8)
    ]
    selected = []
    window = window_namespace(
        latheMode=False,
        _view_mode="3d",
        render_points=points,
        execution_result=SimpleNamespace(motions=motions),
        _sync_editor_to_motion=lambda index: selected.append(("source", index)),
        _motion_to_playback=(4, 9),
        ui=SimpleNamespace(
            graphicsView=None,
            horizontalSlider=SimpleNamespace(setValue=selected.append),
            statusbar=SimpleNamespace(showMessage=lambda *_args: None),
        ),
    )
    assert main_window.MainWindow._pick_trace_at(window, QPointF(50, 50))
    assert selected == [10, ("source", 1)]
