from __future__ import annotations

import pytest
from PyQt6.QtCore import QFile
from PyQt6.QtWidgets import QApplication

from app import main_window


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def _window(qt_app):
    del qt_app
    window = main_window.MainWindow()
    window.autoUpdateEnabled = False
    return window


def _stock_outline_is_visible(window):
    return any(item in window.ui.graphicsView.items for item in getattr(window, "_stock_outline_items", ()))


def test_stl_and_lathe_toolbar_actions_are_in_the_required_order(qt_app):
    window = _window(qt_app)
    file_actions = window.ui.fileToolBar.actions()
    edit_actions = window.ui.editToolBar.actions()
    cnc_actions = window.ui.cncToolBar.actions()
    view_actions = window.ui.viewToolBar.actions()
    playback_actions = window.ui.playbackToolBar.actions()
    menu_actions = window.ui.menu_File.actions()

    export_index = file_actions.index(window.ui.actionExportData)
    assert file_actions[export_index + 1] is window.ui.actionImportSTL
    assert edit_actions[0] is window.ui.actionUndo
    assert menu_actions.index(window.ui.actionImportSTL) + 1 == menu_actions.index(window.ui.actionClearSTL)
    assert cnc_actions.index(window.ui.actionLatheMode) + 1 == cnc_actions.index(window.ui.actionRefresh)
    assert window.ui.actionFitToView in view_actions
    assert view_actions.index(window.ui.action3D) + 1 == view_actions.index(window.ui.actionTop)
    assert playback_actions[-1] is window.ui.actionStep_Forward
    assert window.optionsDlg.ui.showStockCheck.text() == "Show Stock"
    plot_form = window.optionsDlg.ui.plotForm
    assert plot_form.getWidgetPosition(window.optionsDlg.ui.gridCheck)[0] == 3
    assert plot_form.getWidgetPosition(window.optionsDlg.ui.showStockCheck)[0] == 5
    assert QFile(":/resource/icons/stl.png").exists()
    assert not window.ui.actionImportSTL.icon().isNull()
    window.deleteLater()


def test_toolbars_default_to_one_row_and_layout_can_be_reset(qt_app):
    window = _window(qt_app)
    toolbars = (
        window.ui.fileToolBar,
        window.ui.editToolBar,
        window.ui.cncToolBar,
        window.ui.viewToolBar,
        window.ui.playbackToolBar,
    )
    assert all(not window.toolBarBreak(toolbar) for toolbar in toolbars)

    window.insertToolBarBreak(window.ui.viewToolBar)
    assert window.toolBarBreak(window.ui.viewToolBar)
    window.resetToolbarsToDefault()

    assert all(window.toolBarArea(toolbar) == window.toolBarArea(window.ui.fileToolBar) for toolbar in toolbars)
    assert all(not window.toolBarBreak(toolbar) for toolbar in toolbars)
    assert all(not toolbar.isHidden() for toolbar in toolbars)
    window.deleteLater()


def test_toolbar_layout_state_round_trip(qt_app):
    window = _window(qt_app)
    window.insertToolBarBreak(window.ui.viewToolBar)
    state = window.saveState(1)
    window.resetToolbarsToDefault()
    assert not window.toolBarBreak(window.ui.viewToolBar)
    assert window.restoreState(state, 1)
    assert window.toolBarBreak(window.ui.viewToolBar)
    window.deleteLater()


def test_lathe_mode_disables_y_wcs_and_converts_x_at_the_ui_boundary(qt_app):
    window = _window(qt_app)
    window.wcsOffsets[54] = (20.0, 7.0, -3.0)
    window.xPosMach = 30.0
    window.yPosMach = 8.0
    window.ui.actionLatheMode.setChecked(True)

    assert window.wcsDlg.ui.g54X.value() == 40.0
    assert window.wcsDlg.ui.homeX.value() == 60.0
    assert not window.wcsDlg.ui.g54Y.isEnabled()
    assert not window.wcsDlg.ui.homeY.isEnabled()

    window.wcsDlg.ui.g54X.setValue(80.0)
    window.wcsDlg.ui.homeX.setValue(100.0)
    window.wcsDlg.applyValues()
    assert window.wcsOffsets[54] == (40.0, 7.0, -3.0)
    assert window.xPosMach == 50.0

    window.ui.actionLatheMode.setChecked(False)
    assert window.wcsDlg.ui.g54X.value() == 40.0
    assert window.wcsDlg.ui.g54Y.isEnabled()
    assert window.wcsDlg.ui.homeY.isEnabled()
    window.deleteLater()


def test_lathe_coordinates_show_diameter_but_milling_values_are_unchanged(qt_app):
    window = _window(qt_app)
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18 G90\nG0 X40 Z0\nG2 X20 Z-10 I-10 K0\nM30")
    assert window.updateData()
    window.ui.horizontalSlider.setValue(window.ui.horizontalSlider.maximum())
    assert window.ui.lineEditX.text() == "20.0"
    assert window.ui.lineEdit_I.text() == "-20.0"
    assert window.render_points[-1].x == pytest.approx(10.0)

    window.ui.actionLatheMode.setChecked(False)
    window.ui.editor.setText("G21 G17 G90\nG0 X20 Y0\nG2 X10 Y10 I-10 J0\nM30")
    assert window.updateData()
    window.ui.horizontalSlider.setValue(window.ui.horizontalSlider.maximum())
    assert window.ui.lineEditX.text() == "10.0"
    assert window.ui.lineEdit_I.text() == "-10.0"
    window.deleteLater()


def test_lathe_indicators_follow_g20_units_and_resolve_r_arc_ik(qt_app):
    window = _window(qt_app)
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G20 G18 G90\nG0 X2.83 Z0.1\nG1 X2.73 Z0 F0.005\nG2 X2.63 Z-0.05 R0.05\nM30")

    assert window.updateData()
    arc_index = next(index for index, motion in enumerate(window.execution_result.motions) if motion.arc is not None)
    window.ui.horizontalSlider.setValue(arc_index + 1)

    assert window.ui.lineEditX.text() == "2.63"
    assert window.ui.lineEditZ.text() == "-0.05"
    assert window.ui.lineEditFeed.text() == "0.005"
    assert window.ui.lineEdit_I.text() != ""
    assert window.ui.lineEdit_K.text() != ""
    window.deleteLater()


def test_lathe_indicator_units_change_with_g20_and_g21(qt_app):
    window = _window(qt_app)
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G20 G90\nG1 X1 Z-1 F0.01\nG21\nG1 X20 Z-20 F2\nM30")

    assert window.updateData()
    window.ui.horizontalSlider.setValue(1)
    assert window.ui.lineEditX.text() == "1.0"
    assert window.ui.lineEditZ.text() == "-1.0"
    assert window.ui.lineEditFeed.text() == "0.01"

    window.ui.horizontalSlider.setValue(2)
    assert window.ui.lineEditX.text() == "20.0"
    assert window.ui.lineEditZ.text() == "-20.0"
    assert window.ui.lineEditFeed.text() == "2.0"
    window.deleteLater()


def test_show_stock_toggles_the_outline_without_changing_lathe_mode(qt_app):
    window = _window(qt_app)
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18 G90\nG0 X40 Z0\nG1 X40 Z-20 F100\nM30")
    assert window.updateData()
    assert _stock_outline_is_visible(window)

    window.optionsDlg.show()
    qt_app.processEvents()
    window.optionsDlg.ui.showStockCheck.setChecked(False)
    assert window.latheMode is True
    assert not _stock_outline_is_visible(window)

    window.optionsDlg.ui.showStockCheck.setChecked(True)
    assert _stock_outline_is_visible(window)
    window.optionsDlg.reject()
    window.deleteLater()
