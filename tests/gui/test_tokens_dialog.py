"""Tokens analysis and dialog behavior."""

from __future__ import annotations

import csv

import pytest
from gcode_samples import TURNING_PARTIAL_TRACE
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.gcode.kernel import execute
from app.ui.dialogs.tokens import TABLE_HEADINGS, TABLE_WIDTHS, TokensDialog, rows_from_execution


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
