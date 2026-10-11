"""Stock settings and axis restrictions remain independent of the GPU renderer."""

# pylint: disable=protected-access

import pytest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.plot.milling_stock_overlay import MillingStockOverlayItem


@pytest.fixture(scope="session")
def stock_qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def milling_window(stock_qt_app):
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
