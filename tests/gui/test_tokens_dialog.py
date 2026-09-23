"""Tokens analysis and dialog behavior."""

from __future__ import annotations

import csv

import pytest
from gcode_samples import TURNING_PARTIAL_TRACE
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.gcode.kernel import execute
from app.main_window import MainWindow
from app.ui.dialogs.tokens import (
    TABLE_HEADINGS,
    TABLE_WIDTHS,
    TokensDialog,
    rows_from_execution,
    variables_for_playback,
)
from app.ui.plot.playback import build_playback_movements


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_rows_use_kernel_tokens_and_diagnostics():
    source = "G0 X1 Z2\nG999 X3"
    rows = rows_from_execution(source, execute(source))
    assert rows[0].values[2] == "G:0 X:1 Z:2"
    assert rows[0].status == "OK"
    assert rows[1].status == "ERROR"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]


def test_tokens_support_follows_kernel_diagnostics_and_keeps_fractional_g_distinct():
    source = "G54\nG0.6 X1"
    rows = rows_from_execution(source, execute(source))
    assert rows[0].values[15] == "OK"
    assert rows[0].values[12] == "G54"
    assert rows[1].values[7] == ""
    assert rows[1].values[15] == "UNSUPPORTED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]

    milling = rows_from_execution("G85 X1 Z-2 R0 F100", execute("G85 X1 Z-2 R0 F100", language="fanuc_mill"))
    assert milling[0].values[11] == "G85"
    assert milling[0].values[15] == "OK"


def test_tokens_groups_macro_flow_and_multiple_g_codes_follow_kernel_program():
    source = "#1=1\nG21 G18 G90 G190 G97\nIF[#1 EQ 1] GOTO10\nN10 G0 X20 Z0\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[14] == "assign"
    assert rows[1].values[8] == "G18"
    assert rows[1].values[9] == "G21"
    assert rows[1].values[12] == "G90,G190"
    assert rows[1].values[13] == "G97"
    assert rows[2].values[14] == "if_goto"
    assert all(row.values[15] == "OK" for row in rows)


def test_tokens_show_unverified_milling_diagnostics_without_own_support_table():
    source = "G90 G17\nG64\nM123\nG1 X10 Y0 F100\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_mill"))

    assert rows[1].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]
    assert rows[2].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_M_CODE" in rows[2].values[16]
    assert rows[3].values[15] == "OK"


def test_tokens_preserve_fatal_diagnostics_on_their_source_lines():
    source = "G999\nGOTO999"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[0].values[16]
    assert rows[1].status == "ERROR"
    assert "FLOW_TARGET_MISSING" in rows[1].values[16]


def test_tokens_keep_partial_turning_execution_diagnostics_and_later_source_rows():
    rows = rows_from_execution(
        TURNING_PARTIAL_TRACE,
        execute(TURNING_PARTIAL_TRACE, language="fanuc_turn"),
    )

    assert rows[1].values[15] == "UNVERIFIED"
    assert rows[3].values[15] == "UNSUPPORTED"
    assert rows[4].values[15] == "OK"
    assert rows[5].values[15] == "OK"


def test_tokens_dialog_refreshes_live_source_and_does_not_change_it(qt_app):
    current = {"source": "G0 X1 Z2"}
    analyses = []

    def analyze():
        analyses.append(current["source"])
        return execute(current["source"])

    parent = QMainWindow()
    dialog = TokensDialog(parent, lambda: current["source"], analyze)
    dialog.show()
    qt_app.processEvents()
    assert analyses == ["G0 X1 Z2"]
    assert dialog.model.rowCount() == 1
    assert dialog.model.item(0, 17).text() == "Yes"

    current["source"] = "G0 X1\nG999 X2"
    dialog.refresh()
    assert analyses[-1] == current["source"]
    assert dialog.model.rowCount() == 2
    assert dialog.model.item(1, 17).text() == "No"
    assert dialog.model.item(0, 0).background().color().name() == "#e7f6e7"
    assert dialog.model.item(1, 0).background().color().name() == "#ffe6e6"
    assert dialog.model.item(0, 0).foreground().color().name() == "#111111"
    assert current["source"] == "G0 X1\nG999 X2"


def test_tokens_copy_export_and_reset_columns(qt_app, monkeypatch, tmp_path):
    source = "G0 X1\nG1 Z2"
    parent = QMainWindow()
    dialog = TokensDialog(parent, lambda: source, lambda: execute(source))
    dialog.refresh()
    selection = dialog.ui.tokenTable.selectionModel()
    for row in range(2):
        index = dialog.model.index(row, 0)
        selection.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    dialog.copy_selected_rows()
    copied = QApplication.clipboard().text()
    assert copied.count("\n") == 1
    assert all(len(line.split("\t")) == len(TABLE_HEADINGS) for line in copied.splitlines())

    output = tmp_path / "tokens.csv"
    monkeypatch.setattr("app.ui.dialogs.tokens.QFileDialog.getSaveFileName", lambda *args: (str(output), "CSV"))
    dialog.export_csv()
    with output.open(encoding="utf-8", newline="") as stream:
        exported = list(csv.reader(stream, delimiter=";"))
    assert tuple(exported[0]) == TABLE_HEADINGS
    assert exported[1] == [dialog.model.item(0, column).text() for column in range(dialog.model.columnCount())]

    dialog.ui.tokenTable.setColumnWidth(0, 200)
    dialog.ui.tokenTable.horizontalScrollBar().setValue(10)
    dialog.ui.tokenTable.verticalScrollBar().setValue(10)
    dialog.reset_columns()
    assert tuple(dialog.ui.tokenTable.columnWidth(column) for column in range(len(TABLE_WIDTHS))) == TABLE_WIDTHS
    assert dialog.ui.tokenTable.horizontalScrollBar().value() == 0
    assert dialog.ui.tokenTable.verticalScrollBar().value() == 0


def test_shared_footer_refreshes_and_exports_macro_variables(qt_app, monkeypatch, tmp_path):
    source = "#100=25.5\nG1 X1 F100"
    result = execute(source, language="fanuc_mill")
    movements = build_playback_movements(result.motions)[0]
    analyses = []
    parent = QMainWindow()
    dialog = TokensDialog(
        parent,
        lambda: source,
        lambda: analyses.append(True),
        execution_provider=lambda: result,
        playback_provider=lambda: (movements, 1),
        stale_provider=lambda: False,
    )
    dialog.ui.tabWidget.setCurrentWidget(dialog.ui.macroVariablesTab)

    assert not dialog.ui.resetColumnsButton.isEnabled()
    dialog.ui.refreshButton.click()
    assert analyses == []
    assert dialog.variables_model.item(0, 1).text() == "25.5"

    output = tmp_path / "macro-variables.csv"
    monkeypatch.setattr("app.ui.dialogs.tokens.QFileDialog.getSaveFileName", lambda *args: (str(output), "CSV"))
    dialog.ui.exportCsvButton.click()
    with output.open(encoding="utf-8", newline="") as stream:
        exported = list(csv.reader(stream, delimiter=";"))
    assert exported == [["#", "Value"], ["#100", "25.5"]]

    dialog.ui.tabWidget.setCurrentWidget(dialog.ui.tokensTab)
    assert dialog.ui.resetColumnsButton.isEnabled()


@pytest.mark.parametrize("language", ["fanuc_turn", "fanuc_mill"])
def test_macro_variables_follow_logical_playback_and_program_end(language):
    source = "#100=10\nG1 X10 F100\n#100=20\nG1 X20\n#100=0\nM30"
    result = execute(source, language=language)
    movements = build_playback_movements(result.motions)[0]

    assert variables_for_playback(result, movements, 0) == ()
    assert dict(variables_for_playback(result, movements, 1))["100"] == 10
    assert dict(variables_for_playback(result, movements, 2))["100"] == 20
    assert dict(variables_for_playback(result, movements, 2, at_program_end=True))["100"] == 0


def test_macro_variables_are_sorted_numeric_then_named():
    result = execute("#100=1\n#2=2\n#<NAME>=3.2\nG1 X1 F100", language="fanuc_mill")
    movements = build_playback_movements(result.motions)[0]

    assert variables_for_playback(result, movements, 1) == (("2", 2.0), ("100", 1.0), ("NAME", 3.2))


def test_macro_variables_tab_uses_snapshots_without_analyzing_again(qt_app):
    source = "#100=10\nG1 X1 F100"
    result = execute(source, language="fanuc_mill")
    movements = build_playback_movements(result.motions)[0]
    analyses = []
    parent = QMainWindow()
    dialog = TokensDialog(
        parent,
        lambda: source,
        lambda: analyses.append(True),
        execution_provider=lambda: result,
        playback_provider=lambda: (movements, 1),
        stale_provider=lambda: False,
    )
    dialog.ui.tabWidget.setCurrentWidget(dialog.ui.macroVariablesTab)
    dialog.show()
    qt_app.processEvents()

    assert analyses == []
    assert dialog.variables_model.rowCount() == 1
    assert dialog.variables_model.item(0, 0).text() == "#100"
    assert dialog.variables_model.item(0, 1).text() == "10"


def test_macro_variables_tab_reports_missing_and_stale_execution(qt_app):
    state = {"result": None, "stale": False}
    parent = QMainWindow()
    dialog = TokensDialog(
        parent,
        lambda: "",
        lambda: None,
        execution_provider=lambda: state["result"],
        playback_provider=lambda: ((), 0),
        stale_provider=lambda: state["stale"],
    )
    dialog.refresh_macro_variables()
    assert dialog.ui.macroVariablesStatusLabel.text() == "No execution data."

    state["stale"] = True
    dialog.refresh_macro_variables()
    assert dialog.ui.macroVariablesStatusLabel.text() == (
        "Execution is stale. Update the toolpath to inspect Macro Variables."
    )


def test_main_window_macro_variables_follow_slider_and_hide_stale_snapshots(qt_app):
    source = "#100=10\nG1 X10 F100\n#100=20\nG1 X20\n#100=0\nM30"
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.editor.setText(source)
    assert window.updateData()
    result = window.execution_result

    assert window.ui.actionTokens.text() == "Tokens/Macro Variables"
    assert window.tokensDlg.ui.tabWidget.tabText(0) == "Tokens"
    assert window.tokensDlg.ui.tabWidget.tabText(1) == "Macro Variables"
    window.tokensDlg.ui.tabWidget.setCurrentWidget(window.tokensDlg.ui.macroVariablesTab)
    window.tokensDlg.show()
    qt_app.processEvents()

    assert window.tokensDlg.variables_model.item(0, 1).text() == "0"
    window.ui.horizontalSlider.setValue(1)
    assert window.tokensDlg.variables_model.item(0, 1).text() == "10"
    window.ui.horizontalSlider.setValue(2)
    assert window.tokensDlg.variables_model.item(0, 1).text() == "20"
    assert window.execution_result is result

    window.ui.editor.append("#101=1")
    qt_app.processEvents()
    assert window.tokensDlg.variables_model.rowCount() == 0
    assert window.tokensDlg.ui.macroVariablesStatusLabel.text() == (
        "Execution is stale. Update the toolpath to inspect Macro Variables."
    )
    window.deleteLater()
