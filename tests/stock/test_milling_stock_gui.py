"""Stock settings and axis restrictions remain independent of the GPU renderer."""

# pylint: disable=protected-access

import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.plot.milling_stock_overlay import MillingStockOverlayItem


@pytest.fixture(scope="session")
def stock_qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def milling_window(stock_qt_app, monkeypatch):
    monkeypatch.setattr("app.ui.windows.main_window_milling_stock.QMessageBox.warning", lambda *_: None)
    app = stock_qt_app
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(False)
    window.millingStockManual = True
    window.millingStockXMinus = window.millingStockYMinus = -10
    window.millingStockXPlus = window.millingStockYPlus = 10
    window.millingStockZMinus = -5
    window.millingStockZPlus = 0
    window.millingStockResolution = 1
    yield app, window
    window.ui.editor.setModified(False)
    window.close()
    window.deleteLater()
    app.processEvents()


def test_missing_tool_warning_and_manual_wcs_offsets(milling_window):
    _, window = milling_window
    window.wcsOffsets = {54: (100, 200, 30)}
    window.ui.editor.setText("G21 G17 G90 G54\nT42 M6\nG0 X0 Y0 Z5\nG1 Z-2 F100\nM30")
    assert window.updateData()
    window.millingTools = {}
    window.ui.actionStockPlayback.setChecked(True)
    assert getattr(window, "_stock_animation_active")
    assert getattr(window, "_stock_timeline").bounds == ((90, 110), (190, 210), (25, 30))
    message = window.ui.statusbar.toolTip()
    assert "T42" in message and "inaccurate" in message


def test_milling_dialog_inches_preserve_bounds_on_apply_and_reopen(milling_window):
    app, window = milling_window
    window.millingStockXMinus = -25.4
    window.millingStockXPlus = 50.8
    window.millingStockAllowance = 2.54
    dialog = window.stockDlg
    dialog.show()
    app.processEvents()
    dialog.milling_inches.setChecked(True)
    assert dialog.milling_fields["x_minus"].value() == pytest.approx(-1)
    assert dialog.milling_fields["x_plus"].value() == pytest.approx(2)
    assert dialog.milling_allowance.value() == pytest.approx(0.1)
    assert dialog.milling_fields["x_plus"].suffix() == " in"
    dialog.milling_fields["x_plus"].setValue(3)
    dialog._apply()
    assert window.millingStockXPlus == pytest.approx(76.2)
    assert window.millingStockXMinus == pytest.approx(-25.4)
    assert window.millingStockAllowance == pytest.approx(2.54)
    dialog.show()
    app.processEvents()
    assert dialog.milling_inches.isChecked()
    assert dialog.milling_fields["x_plus"].value() == pytest.approx(3)
    dialog.milling_inches.setChecked(False)
    assert dialog.milling_fields["x_plus"].value() == pytest.approx(76.2)
    assert dialog.milling_fields["x_plus"].suffix() == " mm"
    dialog.reject()


def test_close_with_active_milling_stock(milling_window):
    _, window = milling_window
    window.ui.editor.setText("G21 G17 G90\nG0 Z5\nG1 Z-2 F100\nG1 X3\nM30")
    assert window.updateData()
    window.ui.actionStockPlayback.setChecked(True)
    assert isinstance(window._milling_stock_item, MillingStockOverlayItem)
    window.ui.editor.setModified(False)
    if not window.close():
        # Closing is deferred while cancelled QThreads release their timeline.
        for _ in range(100):
            QTest.qWait(10)
            if not any(worker.isRunning() for worker in window._milling_retired_workers):
                break
        assert window.close()


def test_milling_accuracy_is_applied_and_restored_on_reopen(milling_window):
    app, window = milling_window
    dialog = window.stockDlg
    dialog.show()
    app.processEvents()
    dialog.milling_accuracy.setValue(4)
    dialog._apply()
    assert window.millingStockAccuracy == 4
    for speed in range(1, 6):
        window.playbackSpeed = speed
        assert window._selected_milling_stock_accuracy() == 4
    dialog.show()
    app.processEvents()
    assert dialog.milling_accuracy.value() == 4
    dialog.reject()


@pytest.mark.parametrize(
    "program",
    [
        "G21 G17 G90\nG0 A10\nG1 X2 F100\nM30",
        "G21 G17 G90\nG43.4\nG1 X2 A10 F100\nM30",
    ],
)
def test_rotary_milling_simulation_remains_unavailable(milling_window, program):
    _, window = milling_window
    window.rotaryKinematics = "5ax_table_ac_angled"
    window.ui.editor.setText(program)
    window.updateData()
    window.ui.actionStockPlayback.setChecked(True)
    assert not getattr(window, "_stock_animation_active")
    assert not window.ui.actionStockPlayback.isChecked()
    assert not window.ui.actionSaveStockStl.isEnabled()


def test_stock_resource_limit_notifies_without_reducing_accuracy(milling_window, monkeypatch, caplog):
    _, window = milling_window
    messages = []
    monkeypatch.setattr(
        "app.ui.windows.main_window_milling_stock.QMessageBox.warning", lambda *args: messages.append(args[-1])
    )
    window.millingStockXMinus = window.millingStockYMinus = -300
    window.millingStockXPlus = window.millingStockYPlus = 300
    window.millingStockAccuracy = 4
    window.ui.editor.setText("G21 G17 G90\nT1 M6\nG0 Z5\nG1 Z-2 F100\nM30")
    assert window.updateData()
    window.ui.actionStockPlayback.setChecked(True)
    assert not window._stock_animation_active
    assert window._stock_timeline is None
    assert not window.ui.actionStockPlayback.isChecked()
    assert not window.ui.actionSaveStockStl.isEnabled()
    assert window.millingStockAccuracy == 4
    assert len(messages) == 1 and "4096.0 MiB" in messages[0]
    assert "milling_stock_unavailable" in caplog.text


def test_gpu_failure_stops_playback_after_paint_and_ignores_stale_signal(milling_window, monkeypatch, caplog):
    app, window = milling_window
    messages = []
    monkeypatch.setattr(
        "app.ui.windows.main_window_milling_stock.QMessageBox.warning", lambda *args: messages.append(args[-1])
    )
    window.ui.editor.setText("G21 G17 G90\nT1 M6\nG0 Z5\nG1 Z-2 F100\nM30")
    assert window.updateData()
    window.ui.actionStockPlayback.setChecked(True)
    item, timeline = window._milling_stock_item, window._stock_timeline
    window._milling_stock_render_failed(object(), RuntimeError("stale"))
    assert window._stock_animation_active and not messages
    item.renderFailed.emit(timeline, RuntimeError("GPU allocation failed"))
    assert window._stock_animation_active
    app.processEvents()
    assert not window._stock_animation_active
    assert not window.ui.actionPlay.isChecked()
    assert not window.ui.actionSaveStockStl.isEnabled()
    assert item._frame is None
    assert len(messages) == 1 and "GPU allocation failed" in messages[0]
    assert "milling_stock_render_failed" in caplog.text


def test_live_stock_zoom_at_speed_four(milling_window, fixture_text):
    app, window = milling_window
    if app.platformName() in {"offscreen", "minimal"}:
        pytest.skip("Live zoom regression needs a native OpenGL window")
    window.resize(1280, 800)
    window.show()
    QTest.qWait(100)
    context = window.ui.graphicsView.context()
    if context is None or (context.format().majorVersion(), context.format().minorVersion()) < (4, 3):
        pytest.skip("GPU stock requires OpenGL 4.3")
    window.millingStockXMinus, window.millingStockXPlus = -100, 100
    window.millingStockYMinus, window.millingStockYPlus = -70, 80
    window.millingStockZMinus, window.millingStockZPlus = 0, 22
    window.millingStockAccuracy = 4
    window.setPlaybackSpeed(4)
    window.ui.editor.setText(fixture_text("milling/fanuc/toolchange.nc"))
    assert window.updateData()
    window.ui.actionStockPlayback.setChecked(True)
    window.ui.actionPlay.setChecked(True)
    maximum_seen = 0
    for step in range(180):
        QTest.qWait(200)
        maximum_seen = max(maximum_seen, window.ui.horizontalSlider.value())
        if not window.ui.actionPlay.isChecked():
            window.ui.actionPlay.setChecked(True)
        if step % 48 < 24:
            window.zoomIn()
        else:
            window.zoomOut()
        assert window._stock_animation_active
        assert window._milling_stock_item._failure is None
        assert window.millingStockAccuracy == 4
        if step >= 143 and maximum_seen == window.ui.horizontalSlider.maximum():
            break
    window._pause_playback()
    window._leave_stock_animation()
    QTest.qWait(100)
    assert maximum_seen == window.ui.horizontalSlider.maximum()
    assert window.playbackSpeed == 4
