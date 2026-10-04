from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette, QWheelEvent
from PyQt6.QtWidgets import QApplication

from app import i18n
from app.gcode.kernel import execute
from app.gcode.trace_tools import format_tool_list, trace_statistics
from app.main_window import MainWindow
from app.ui.dialogs.statistics import StatisticsDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_statistics_dialog_keeps_long_report_inside_scrollable_text(qt_app):
    dialog = StatisticsDialog()
    report = "Toolpath Statistics\n" + "\n".join(f"Tool T{index}: {index} mm" for index in range(100))

    dialog.show_report(report)
    qt_app.processEvents()

    assert dialog.reportText.isReadOnly()
    assert dialog.reportText.toPlainText().startswith("Tool T0: 0 mm")
    assert "Toolpath Statistics" not in dialog.reportText.toPlainText()
    assert dialog.reportText.verticalScrollBar().maximum() > 0
    assert dialog.height() <= 700
    dialog.close()
    dialog.deleteLater()


def test_main_window_reuses_statistics_dialog_for_current_execution(qt_app):
    window = MainWindow()
    dialog = window.statisticsDlg
    window.execution_result = execute("G21 G90\nG0 X10 Z0\nG1 X20 Z-5 F100\nM30")

    window.statistics()

    assert window.statisticsDlg is dialog
    assert dialog.isVisible()
    assert "Execution: complete" in dialog.reportText.toPlainText().replace(":\n", ": ")
    assert "Motions: 2" in dialog.reportText.toPlainText().replace(":\n", ": ")
    assert dialog.inchesCheck.isEnabled()
    window.close()
    window.deleteLater()


def test_statistics_inches_checkbox_converts_all_lengths_and_speeds(qt_app):
    dialog = StatisticsDialog()
    result = execute("G21 G90\nG0 X25.4\nG1 X50.8 F25.4\nM30", language="fanuc_mill")
    statistics = trace_statistics(result, rapid_feed=2540.0)

    dialog.show_statistics(statistics)
    dialog.inchesCheck.setChecked(True)
    qt_app.processEvents()
    imperial = dialog.reportText.toPlainText().replace(":\n", ": ")

    assert "Length: 2.000 in" in imperial
    assert "Feed length: 1.000 in" in imperial
    assert "Average feed: 1.000 in/min" in imperial
    assert "Assumed rapid speed: 100.000 in/min" in imperial
    assert "Bounds (in)" in imperial
    assert imperial.index("Movements") < imperial.index("Time") < imperial.index("Bounds (in)")
    assert "<table" not in imperial
    assert " mm" not in imperial

    dialog.inchesCheck.setChecked(False)
    metric = dialog.reportText.toPlainText().replace(":\n", ": ")
    assert "Length: 50.800 mm" in metric
    assert "Assumed rapid speed: 2540.000 mm/min" in metric
    dialog.close()
    dialog.deleteLater()


def test_statistics_report_is_localized_only_for_russian(qt_app):
    result = execute("G21 G90\nG0 X10\nG1 X20 F100\nM30", language="fanuc_mill")
    statistics = trace_statistics(result)

    i18n.uninstall_translators(qt_app)
    english = StatisticsDialog()
    english.show_statistics(statistics)
    english_report = english.reportText.toPlainText().replace(":\n", ": ")
    assert "Execution: complete" in english_report
    assert "Rapid length:" in english_report
    english.close()
    english.deleteLater()

    try:
        assert i18n.install_translator(qt_app, "ru") is True
        russian = StatisticsDialog()
        russian.show_statistics(statistics)
        russian_report = russian.reportText.toPlainText().replace(":\n", ": ")
        assert "Выполнение: завершено" in russian_report
        assert "Длина быстрых перемещений:" in russian_report
        assert "Execution:" not in russian_report
        assert "Rapid length:" not in russian_report
        russian.close()
        russian.deleteLater()
    finally:
        i18n.uninstall_translators(qt_app)


def test_statistics_selector_and_export_preserve_all_tools(qt_app, monkeypatch, tmp_path):
    dialog = StatisticsDialog()
    result = execute("G21 G90\nT1 M6\nG1 X10 F100\nT2 M6\nG1 X30 F200\nM30", language="fanuc_mill")
    dialog.show_statistics(trace_statistics(result))
    dialog.toolSelect.setCurrentIndex(dialog.toolSelect.findData("T2"))
    text = dialog.reportText.toPlainText().replace(":\n", ": ")
    assert "Tool T2" in text and "Tool T1" not in text
    assert "Length: 20.000 mm" in text
    output = tmp_path / "statistics.html"
    monkeypatch.setattr("app.ui.dialogs.statistics.QFileDialog.getSaveFileName", lambda *_a: (str(output), "HTML"))
    notices = []
    monkeypatch.setattr("app.ui.dialogs.statistics.QMessageBox.information", lambda *args: notices.append(args))
    assert dialog.export_html()
    assert len(notices) == 1 and str(output) in notices[0][2]
    exported = output.read_text(encoding="utf-8")
    assert "Tool T1" in exported and "Tool T2" in exported
    assert '<option value="section-2" selected>' in exported
    dialog.close()
    dialog.deleteLater()


def _font_sizes(browser):
    sizes = []
    block = browser.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.text().strip():
                sizes.append(fragment.charFormat().fontPointSize())
            iterator += 1
        block = block.next()
    return sizes


def test_dark_statistics_exports_light_report_and_reports_write_failure(qt_app, monkeypatch, tmp_path):
    dialog = StatisticsDialog()
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#eeeeee"))
    dialog.setPalette(palette)
    result = execute("G0 X10\nM30")
    dialog.show_statistics(trace_statistics(result), execution=result)
    assert dialog.reportText.document().rootFrame().frameFormat().background().color().name() == "#252526"
    output = tmp_path / "statistics.html"
    notices, errors = [], []
    monkeypatch.setattr("app.ui.dialogs.statistics.QFileDialog.getSaveFileName", lambda *_a: (str(output), "HTML"))
    monkeypatch.setattr("app.ui.dialogs.statistics.QMessageBox.information", lambda *a: notices.append(a))
    monkeypatch.setattr("app.ui.dialogs.statistics.QMessageBox.warning", lambda *a: errors.append(a))
    assert dialog.export_html()
    report = output.read_text(encoding="utf-8")
    assert "background: #ffffff" in report
    assert "#252526" not in report and "#eeeeee" not in report
    assert "<svg" in report
    assert "<svg" not in dialog.reportText.document().toHtml()
    assert len(notices) == 1 and not errors

    def fail_write(*_a, **_kw):
        raise OSError("disk write failed")

    monkeypatch.setattr("app.ui.dialogs.statistics.write_statistics_html", fail_write)
    assert not dialog.export_html()
    assert len(notices) == 1 and len(errors) == 1
    assert "disk write failed" in errors[0][2]
    dialog.close()
    dialog.deleteLater()


def test_statistics_wheel_scrolls_and_control_wheel_scales_every_fragment(qt_app):
    dialog = StatisticsDialog()
    dialog.show_statistics(trace_statistics(execute("G0 X10\nG1 X20 F100\nM30")))
    dialog.resize(500, 350)
    qt_app.processEvents()
    scroll_bar = dialog.reportText.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    wheel = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qt_app.sendEvent(dialog.reportText.viewport(), wheel)
    assert scroll_bar.value() > 0
    before = _font_sizes(dialog.reportText)
    zoom = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qt_app.sendEvent(dialog.reportText.viewport(), zoom)
    after = _font_sizes(dialog.reportText)
    assert len(before) == len(after)
    assert all(new > old for old, new in zip(before, after))
    dialog.inchesCheck.setChecked(True)
    assert _font_sizes(dialog.reportText) == after
    dialog.close()
    dialog.deleteLater()


@pytest.mark.parametrize("background,foreground", [("#ffffff", "#202020"), ("#252526", "#eeeeee")])
def test_statistics_background_follows_palette(qt_app, background, foreground):
    dialog = StatisticsDialog()
    dialog.show_statistics(trace_statistics(execute("G0 X10\nM30")))
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor(background))
    palette.setColor(QPalette.ColorRole.Text, QColor(foreground))
    dialog.setPalette(palette)
    qt_app.processEvents()
    assert dialog.reportText.document().rootFrame().frameFormat().background().color().name() == background
    assert foreground in dialog.reportText.toHtml()
    dialog.close()
    dialog.deleteLater()


@pytest.mark.parametrize(
    "source,status,color",
    [
        ("G0 X10\nM30", "complete", "#21664f"),
        ("G0 X10\nG999\nM30", "WARNINGS", "#a85400"),
        ("G0 X10\nG2 X100 Z100 R1\nM30", "PARTIAL / INVALID", "#b42318"),
    ],
)
def test_execution_status_has_distinct_colors(qt_app, source, status, color):
    dialog = StatisticsDialog()
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    dialog.setPalette(palette)
    dialog.show_statistics(trace_statistics(execute(source)))
    block = dialog.reportText.document().begin()
    while block.isValid() and not block.text().startswith("Execution:"):
        block = block.next()
    block = block.next()
    assert block.isValid() and status in block.text()
    assert block.begin().fragment().charFormat().foreground().color().name() == color
    assert dialog.reportText.document().rootFrame().frameFormat().margin() == 20
    assert block.blockFormat().leftMargin() == 0
    dialog.close()
    dialog.deleteLater()


@pytest.mark.parametrize(
    "background,foreground,border",
    [
        ("#ffffff", "#000000", "#cccccc"),
        ("#252526", "#eeeeee", "#4d4d4e"),
    ],
)
def test_separator_color_does_not_use_black_system_mid_color(qt_app, background, foreground, border):
    dialog = StatisticsDialog()
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Base, QColor(background))
    palette.setColor(QPalette.ColorRole.Text, QColor(foreground))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#000000"))
    dialog.setPalette(palette)
    dialog.show_statistics(trace_statistics(execute("G0 X10\nM30")))
    table = dialog.reportText.document().rootFrame().childFrames()[0]
    cell_format = table.cellAt(3, 0).format().toTableCellFormat()
    assert cell_format.bottomBorderBrush().color().name() == border
    dialog.close()
    dialog.deleteLater()


def test_statistics_context_menu_uses_application_copy_and_select_all_icons(qt_app):
    dialog = StatisticsDialog()
    menu = dialog.create_report_context_menu()
    actions = {action.text().split("\t", 1)[0].replace("&", ""): action for action in menu.actions()}

    for label, resource in (
        ("Copy", ":/resource/icons/copy.png"),
        ("Select All", ":/resource/icons/select-all.png"),
    ):
        actual = actions[label].icon().pixmap(16, 16).toImage()
        expected = QIcon(resource).pixmap(16, 16).toImage()
        assert not actual.isNull()
        assert actual == expected

    menu.deleteLater()
    dialog.deleteLater()
    qt_app.processEvents()


def test_tool_list_formats_file_metadata_geometry_and_per_tool_zmin(tmp_path):
    source = """\
O1001
G21 G90 G17
T1 M6
G0 Z5
G1 Z-1 F100
T2 M6
G1 Z-11
M30
"""
    result = execute(source, language="fanuc_mill")
    statistics = trace_statistics(result)
    nc_file = tmp_path / "Документы" / "1001.nc"
    nc_file.parent.mkdir()
    nc_file.write_text(source, encoding="utf-8")
    tools = {
        "T1": {"type": "face_mill", "diameter": 50.0, "cornerRadius": 0.0},
        "T2": {"type": "mill_flat", "diameter": 12.0, "cornerRadius": 0.0},
    }

    report = format_tool_list(result, statistics, tools, file_path=str(nc_file))

    assert report.startswith("Tool List: 1001")
    assert "File              : 1001.nc" in report
    assert f"Full name         : {nc_file.resolve()}" in report
    assert "T1              D=50 CR=0 - ZMIN=-1 - FACE MILL" in report
    assert "T2              D=12 CR=0 - ZMIN=-11 - FLAT END MILL" in report


def test_main_window_exports_tool_list_as_utf8_bom(qt_app, monkeypatch, tmp_path):
    output = tmp_path / "tools.txt"
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(False)
    window.autoUpdateEnabled = False
    window.millingTools = {"T1": {"type": "drill", "diameter": 4.2, "tipAngle": 118.0}}
    window.ui.editor.setText("O7\nG21 G90\nT1 M6\nG0 Z5\nG1 Z-10 F100\nM30")
    assert window.updateData()
    monkeypatch.setattr(
        "app.ui.windows.main_window_file_ops.QFileDialog.getSaveFileName",
        lambda *args: (str(output), "Text"),
    )

    assert window.exportToolList()
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")
    exported = output.read_text(encoding="utf-8-sig")
    assert "Tool List: 7" in exported
    assert "T1              D=4.2 TAPER=118DEG - ZMIN=-10 - DRILL" in exported
    window.deleteLater()
