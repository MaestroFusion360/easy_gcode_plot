import pytest
from PyQt6.QtWidgets import QApplication

from app import main_window


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def _lathe_window(qt_app):
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    return window


def _outline_items(window):
    return [
        item
        for item in getattr(window, "_stock_outline_items", ())
        if item in window.ui.graphicsView.items and bool(getattr(item, "visible", False))
    ]


def test_stock_outline_uses_auto_suggestion_and_clear_removes_it(qt_app):
    window = _lathe_window(qt_app)
    window.ui.editor.setText("G21 G18 G90\nG0 X200 Z50\nG0 X40 Z0\nG1 X40 Z-25 F100\nM30")

    assert window.updateData()
    suggestion = window._stock_auto_suggestion  # pylint: disable=protected-access
    assert suggestion is not None
    assert suggestion.outer_diameter == pytest.approx(40.0)
    assert suggestion.length == pytest.approx(25.0)
    assert _outline_items(window)

    window.clearPlot()

    assert window._stock_auto_suggestion is None  # pylint: disable=protected-access
    assert not _outline_items(window)
    window.deleteLater()


def test_stock_dialog_prefills_auto_suggestion_without_saving(qt_app):
    window = _lathe_window(qt_app)
    window.turnStockDiameter = 99.0
    window.turnStockInnerDiameter = 5.0
    window.turnStockLength = 88.0
    window.turnStockResolution = 0.25
    window.turnStockFrontAllowance = 2.0
    window.stockConfigured = False
    window.ui.editor.setText("G21 G18 G90\nG0 X200 Z50\nG0 X40 Z0\nG1 X40 Z-25 F100\nM30")
    assert window.updateData()

    window.stockDlg.show()
    qt_app.processEvents()

    assert window.stockDlg.outer.value() == pytest.approx(40.0)
    assert window.stockDlg.inner.value() == pytest.approx(0.0)
    assert window.stockDlg.length.value() == pytest.approx(27.0)
    assert window.stockDlg.front_allowance.value() == pytest.approx(2.0)
    assert window.stockDlg.resolution() == pytest.approx(0.25)
    assert window.turnStockDiameter == pytest.approx(99.0)
    assert window.stockConfigured is False
    window.stockDlg.close()
    window.deleteLater()


def test_stock_outline_hidden_in_milling_and_manual_stock_expands_scene_bounds(qt_app):
    window = _lathe_window(qt_app)
    window.ui.editor.setText("G21 G18 G90\nG1 X20 Z-10 F100\nM30")
    assert window.updateData()
    assert _outline_items(window)

    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 100.0,
            "inner_diameter": 0.0,
            "length": 60.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )
    bounds = window._scene_bounds()  # pylint: disable=protected-access
    assert bounds[0] == pytest.approx((-50.0, 50.0))
    assert bounds[2] == pytest.approx((-58.0, 2.0))

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()

    assert not _outline_items(window)

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()

    assert _outline_items(window)
    restored = window._stock_auto_suggestion  # pylint: disable=protected-access
    assert restored is not None
    assert restored.outer_diameter == pytest.approx(20.0)
    assert restored.length == pytest.approx(10.0)
    window.deleteLater()


def test_lathe_fit_bounds_include_stock_when_outline_is_hidden(qt_app):
    window = _lathe_window(qt_app)
    window.ui.editor.setText("G21 G18 G90\nG0 X20 Z0\nG1 X10 Z-10 F100\nM30")
    assert window.updateData()
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 100.0,
            "inner_diameter": 0.0,
            "length": 60.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )
    window.showStockChecked(False)

    assert window.stockOutlineBounds() is None
    assert window._scene_bounds()[0] == pytest.approx((-50.0, 50.0))  # pylint: disable=protected-access
    assert window._scene_bounds()[2] == pytest.approx((-58.0, 2.0))  # pylint: disable=protected-access

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert window.stockFitBounds() is None
    window.deleteLater()


def test_stock_outline_restored_after_stock_playback_stop(qt_app):
    window = _lathe_window(qt_app)
    window.tools = {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}}
    window.ui.editor.setText("G21 G18 G90 T0101 M3\nG0 X50 Z0\nG1 X40 Z-20 F100\nM30")
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
    assert _outline_items(window)

    window.ui.actionPlay.setChecked(True)
    qt_app.processEvents()
    assert window._stock_animation_active  # pylint: disable=protected-access
    assert not _outline_items(window)

    window.stop()
    qt_app.processEvents()

    assert not window._stock_animation_active  # pylint: disable=protected-access
    assert _outline_items(window)
    assert window.ui.horizontalSlider.value() == window.ui.horizontalSlider.maximum()
    window.deleteLater()


def test_stock_playback_uses_current_program_auto_bounds(qt_app):
    window = _lathe_window(qt_app)
    window.tools = {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}}
    window.ui.editor.setText("G21 G18 G90 T0101 M3\nG0 X40 Z0\nG1 X40 Z-20 F100\nM30")
    assert window.updateData()
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 40.0,
            "inner_diameter": 0.0,
            "length": 22.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )

    window.ui.editor.setText("G21 G18 G90 T0101 M3\nG0 X60 Z0\nG1 X60 Z-40 F100\nM30")
    assert window.updateData()
    expected = window.stockOutlineBounds()

    window.ui.actionPlay.setChecked(True)
    qt_app.processEvents()

    timeline = window._stock_timeline  # pylint: disable=protected-access
    assert timeline.spec.outer_diameter == pytest.approx(60.0)
    assert timeline.spec.length == pytest.approx(42.0)
    for actual_axis, expected_axis in zip(timeline.bounds, expected):
        assert actual_axis == pytest.approx(expected_axis)
    window.stop()
    window.deleteLater()


def test_auto_stock_suggestion_replaces_stale_program_bounds(qt_app):
    window = _lathe_window(qt_app)
    window.ui.editor.setText("G21 G18 G90\nG0 X200 Z50\nG0 X40 Z0\nG1 X40 Z-25 F100\nM30")
    assert window.updateData()

    first = window._stock_auto_suggestion  # pylint: disable=protected-access
    assert first is not None
    assert first.outer_diameter == pytest.approx(40.0)
    assert first.length == pytest.approx(25.0)

    window.ui.editor.setText("G21 G18 G90\nG0 X250 Z80\nG0 X60 Z0\nG1 X60 Z-40 F100\nM30")
    assert window.updateData()

    second = window._stock_auto_suggestion  # pylint: disable=protected-access
    assert second is not None
    assert second.outer_diameter == pytest.approx(60.0)
    assert second.length == pytest.approx(40.0)
    assert second != first
    bounds = window.stockOutlineBounds()
    assert bounds is not None
    assert bounds[0] == pytest.approx((-30.0, 30.0))
    assert bounds[2] == pytest.approx((-40.0, 2.0))
    window.deleteLater()


def test_refresh_replaces_configured_outline_with_current_program_bounds(qt_app):
    window = _lathe_window(qt_app)
    window.ui.editor.setText("G21 G18 G90\nG0 X20 Z0\nG1 X20 Z-10 F100\nM30")
    assert window.updateData()
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 100.0,
            "inner_diameter": 0.0,
            "length": 60.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )
    assert window.stockOutlineBounds()[0] == pytest.approx((-50.0, 50.0))

    assert window.updateData()

    assert window.stockConfigured is True
    assert window.turnStockDiameter == pytest.approx(100.0)
    assert window.stockOutlineBounds()[0] == pytest.approx((-10.0, 10.0))
    window.deleteLater()


def test_program_change_refreshes_outline_without_stock_dialog_confirmation(qt_app):
    window = _lathe_window(qt_app)
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 100.0,
            "inner_diameter": 0.0,
            "length": 60.0,
            "front_allowance": 2.0,
            "resolution": 1.0,
        }
    )
    window.ui.editor.setText("G21 G18 G90\nG0 X40 Z0\nG1 X40 Z-25 F100\nM30")
    assert window.updateData()
    assert window.stockOutlineBounds()[0] == pytest.approx((-20.0, 20.0))

    window.ui.editor.setText("G21 G18 G90\nG0 X60 Z0\nG1 X60 Z-40 F100\nM30")
    assert window.updateData()

    assert window.stockOutlineBounds()[0] == pytest.approx((-30.0, 30.0))
    assert window.stockOutlineBounds()[2] == pytest.approx((-40.0, 2.0))
    window.deleteLater()
