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
    assert rows[0].values[TABLE_HEADINGS.index("Words")] == "G:0 X:1 Z:2"
    assert rows[0].status == "OK"
    assert rows[1].status == "ERROR"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[TABLE_HEADINGS.index("Action")]


def test_tokens_support_follows_kernel_diagnostics_and_keeps_fractional_g_distinct():
    source = "G54\nG0.6 X1"
    rows = rows_from_execution(source, execute(source))
    assert rows[0].values[TABLE_HEADINGS.index("Support")] == "OK"
    assert rows[0].values[TABLE_HEADINGS.index("Mode G")] == "G54"
    assert rows[1].values[TABLE_HEADINGS.index("Motion G")] == ""
    assert rows[1].values[TABLE_HEADINGS.index("Support")] == "UNSUPPORTED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[TABLE_HEADINGS.index("Action")]

    milling = rows_from_execution("G85 X1 Z-2 R0 F100", execute("G85 X1 Z-2 R0 F100", language="fanuc_mill"))
    assert milling[0].values[TABLE_HEADINGS.index("Cycle G")] == "G85"
    assert milling[0].values[TABLE_HEADINGS.index("Support")] == "OK"


def test_tokens_groups_macro_flow_and_multiple_g_codes_follow_kernel_program():
    source = "#1=1\nG21 G18 G90 G97\nIF[#1 EQ 1] GOTO10\nN10 G0 X20 Z0\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[TABLE_HEADINGS.index("Flow")] == "assign"
    assert rows[1].values[TABLE_HEADINGS.index("Plane G")] == "G18"
    assert rows[1].values[TABLE_HEADINGS.index("Units G")] == "G21"
    assert rows[1].values[TABLE_HEADINGS.index("Mode G")] == "G90"
    assert rows[1].values[TABLE_HEADINGS.index("Spindle G")] == "G97"
    assert rows[2].values[TABLE_HEADINGS.index("Flow")] == "if_goto"
    assert all(row.values[TABLE_HEADINGS.index("Support")] == "OK" for row in rows)


def test_tokens_show_unverified_milling_diagnostics_without_own_support_table():
    source = "G90 G17\nG64\nM123\nG1 X10 Y0 F100\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_mill"))

    assert rows[1].values[TABLE_HEADINGS.index("Support")] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[TABLE_HEADINGS.index("Action")]
    assert rows[2].values[TABLE_HEADINGS.index("Support")] == "UNVERIFIED"
    assert "UNSUPPORTED_M_CODE" in rows[2].values[TABLE_HEADINGS.index("Action")]
    assert rows[3].values[TABLE_HEADINGS.index("Support")] == "OK"


def test_tokens_attach_unverified_cutter_compensation_to_each_affected_block():
    source = "G90 G17\nG0 X0 Y0\nG41 G1 X10 Y0 F100\nG1 X10 Y10\nG40 G1 X20\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_mill"))

    assert rows[0].values[TABLE_HEADINGS.index("Support")] == "OK"
    assert rows[1].values[TABLE_HEADINGS.index("Support")] == "OK"
    for row in rows[2:4]:
        assert row.values[TABLE_HEADINGS.index("Support")] == "UNVERIFIED"
        assert "UNVERIFIED_CUTTER_COMPENSATION" in row.values[TABLE_HEADINGS.index("Action")]
    assert rows[4].values[TABLE_HEADINGS.index("Support")] == "OK"


def test_tokens_preserve_fatal_diagnostics_on_their_source_lines():
    source = "G999\nGOTO999"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[TABLE_HEADINGS.index("Support")] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[0].values[TABLE_HEADINGS.index("Action")]
    assert rows[1].status == "ERROR"
    assert "FLOW_TARGET_MISSING" in rows[1].values[TABLE_HEADINGS.index("Action")]


def test_tokens_keep_partial_turning_execution_diagnostics_and_later_source_rows():
    rows = rows_from_execution(
        TURNING_PARTIAL_TRACE,
        execute(TURNING_PARTIAL_TRACE, language="fanuc_turn"),
    )

    assert rows[1].values[TABLE_HEADINGS.index("Support")] == "UNVERIFIED"
    assert rows[3].values[TABLE_HEADINGS.index("Support")] == "UNSUPPORTED"
    assert rows[4].values[TABLE_HEADINGS.index("Support")] == "OK"
    assert rows[5].values[TABLE_HEADINGS.index("Support")] == "OK"


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
    assert dialog.model.item(0, TABLE_HEADINGS.index("Valid")).text() == "Yes"

    current["source"] = "G0 X1\nG999 X2"
    dialog.refresh()
    assert analyses[-1] == current["source"]
    assert dialog.model.rowCount() == 2
    assert dialog.model.item(1, TABLE_HEADINGS.index("Valid")).text() == "No"
    assert dialog.model.item(0, 0).background().color().name() == "#e7f6e7"
    assert dialog.model.item(1, 0).background().color().name() == "#ffe6e6"
    assert dialog.model.item(0, 0).foreground().color().name() == "#111111"
    assert current["source"] == "G0 X1\nG999 X2"


def test_filters_reuse_crlf_execution_without_calculating(qt_app):
    source = "T1 M6\r\nG0 X1\r\nG999\r\nGOTO999\r\n"
    result = execute(source, language="fanuc_mill")
    analyses = []
    parent = QMainWindow()
    dialog = TokensDialog(
        parent,
        lambda: source,
        lambda: analyses.append(True),
        execution_provider=lambda: result,
        stale_provider=lambda: False,
    )
    dialog.refresh()
    assert dialog.model.rowCount() == 4
    dialog.ui.searchEdit.setText("T1 M6")
    assert not dialog.ui.tokenTable.isRowHidden(0)
    assert dialog.ui.tokenTable.isRowHidden(1)
    assert dialog.ui.tokenTable.isRowHidden(2)
    assert dialog.ui.tokenTable.isRowHidden(3)
    dialog.ui.searchEdit.clear()
    dialog.ui.filterCombo.setCurrentIndex(1)
    assert not dialog.ui.tokenTable.isRowHidden(2)
    assert dialog.ui.tokenTable.isRowHidden(3)
    dialog.ui.filterCombo.setCurrentIndex(2)
    assert dialog.ui.tokenTable.isRowHidden(0)
    assert dialog.ui.tokenTable.isRowHidden(2)
    assert not dialog.ui.tokenTable.isRowHidden(3)
    dialog.refresh()
    assert analyses == []


@pytest.mark.parametrize(
    "dialect,source,expected",
    [
        ("sinumerik", "R2=2\nR10=10\nG1 X1 F100", {"R2": 2, "R10": 10}),
        ("heidenhain", "Q2=2\nQL3=3\nQR4=4\nL X1 F100", {"Q2": 2, "QL3": 3, "QR4": 4}),
    ],
)
def test_native_variables_use_controller_identifiers(dialect, source, expected):
    result = execute(source, language="fanuc_mill", source_dialect=dialect)
    assert result.ok and result.complete, result.diagnostics
    movements = build_playback_movements(result.motions)[0]
    values = dict(variables_for_playback(result, movements, 1))
    assert values.items() >= expected.items()


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
    assert exported == [["Variable", "Value"], ["#100", "25.5"]]

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
        "Execution is stale. Update the toolpath to inspect Variables."
    )


def test_main_window_macro_variables_follow_slider_and_hide_stale_snapshots(qt_app):
    source = "#100=10\nG1 X10 F100\n#100=20\nG1 X20\n#100=0\nM30"
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.editor.setText(source)
    assert window.updateData()
    result = window.execution_result

    assert window.ui.actionTokens.text() == "Tokens/Variables"
    assert window.tokensDlg.ui.tabWidget.tabText(0) == "Tokens"
    assert window.tokensDlg.ui.tabWidget.tabText(1) == "Variables"
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
        "Execution is stale. Update the toolpath to inspect Variables."
    )
    window.deleteLater()
