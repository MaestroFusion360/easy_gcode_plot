"""Snippet browsing must not disturb the current editor or controller context."""

# pylint: disable=protected-access

import sqlite3

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QDockWidget, QToolBar, QToolButton

from app.main_window import MainWindow
from app.settings import get_settings
from app.ui.dialogs.snippet_insert import SnippetInsertDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    get_settings().setValue("GENERAL/AUTO_UPDATE", False)
    owner = MainWindow()
    yield owner
    owner.autoUpdateTimer.stop()
    owner.timer.stop()
    owner.hide()
    owner.deleteLater()
    qt_app.processEvents()


def test_panel_is_a_dock_with_only_insert_and_edit_buttons(window):
    panel = window.snippetsDock
    assert isinstance(panel, QDockWidget)
    assert window.dockWidgetArea(panel) == Qt.DockWidgetArea.LeftDockWidgetArea
    assert window.findChild(QToolBar, "quickSnippetsToolBar") is None
    assert panel.toggleViewAction() in window.ui.menu_View.actions()
    assert set(panel.widget().findChildren(QToolButton, options=Qt.FindChildOption.FindDirectChildrenOnly)) == {
        panel.ui.insertButton,
        panel.ui.editButton,
    }
    for button in (panel.ui.insertButton, panel.ui.editButton):
        assert not button.icon().isNull()
        assert not button.autoRaise()
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert panel.ui.editButton.text() == "Edit Snippets"
    assert panel.ui.editButton.toolTip() == "Edit Snippets"


def test_default_dock_layout_places_snippets_before_editor_and_stl_after_plot(window):
    assert window.dockWidgetArea(window.snippetsDock) == Qt.DockWidgetArea.LeftDockWidgetArea
    assert window.dockWidgetArea(window.stlObjectsDock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert not window.snippetsDock.isFloating()
    assert not window.stlObjectsDock.isFloating()
    splitter = window.ui.splitter
    assert splitter.orientation() == Qt.Orientation.Horizontal
    assert splitter.indexOf(window.ui.editor) == 0
    assert splitter.widget(1).isAncestorOf(window.ui.graphicsView)


def test_group_and_search_filter_without_touching_the_editor(window):
    editor = window.ui.editor
    editor.setText("G0 X1\nG1 X2\nM30\n")
    editor.setSelection(0, 1, 1, 3)
    expected = editor.text(), editor.getSelection(), editor.getCursorPosition(), editor.isModified()
    ui = window.snippetsDock.ui
    ui.groupCombo.setCurrentIndex(ui.groupCombo.findData("cycles"))
    ui.searchEdit.setText("g73")
    assert ui.snippetList.count() == 1
    assert ui.snippetList.item(0).text() == "High-Speed Peck Drilling (G73)"
    assert ui.insertButton.isEnabled()
    ui.searchEdit.setText("no such snippet")
    assert ui.snippetList.count() == 0
    assert not ui.insertButton.isEnabled()
    assert (editor.text(), editor.getSelection(), editor.getCursorPosition(), editor.isModified()) == expected


def test_insert_uses_saved_text_replaces_selection_and_is_one_undo(window):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("My snippet", "G1 X42\n")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    editor = window.ui.editor
    editor.setText("BEFORE\nOLD\nAFTER\n")
    editor.setSelection(1, 0, 2, 0)
    panel.ui.insertButton.click()
    assert editor.text() == "BEFORE\nG1 X42\nAFTER\n"
    editor.undo()
    assert editor.text() == "BEFORE\nOLD\nAFTER\n"


def test_panel_tracks_controller_and_document_switches(window):
    panel = window.snippetsDock
    assert panel._language == "fanuc_mill"
    panel.ui.searchEdit.setText("G73")
    window.ui.fileTypeCombo.setCurrentIndex(2)
    assert panel._language == "heidenhain"
    assert panel.ui.searchEdit.text() == ""
    assert any("CYCL DEF 251" in panel.ui.snippetList.item(i).text() for i in range(panel.ui.snippetList.count()))
    window.newFile()
    assert panel._language == "fanuc_mill"
    assert window._activate_document(0)
    assert panel._language == "heidenhain"


def test_refresh_after_closing_manager_keeps_query_and_selection(window):
    panel = window.snippetsDock
    panel.ui.searchEdit.setText("Drilling")
    selected = panel.ui.snippetList.currentItem().data(Qt.ItemDataRole.UserRole)
    window.snippetsDlg.show()
    window.snippetsDlg.library.add("Drilling custom", "G1 Z-5 F100\n")
    window.snippetsDlg.reject()
    assert panel.ui.searchEdit.text() == "Drilling"
    assert panel.ui.snippetList.currentItem().data(Qt.ItemDataRole.UserRole) == selected
    assert any(panel.ui.snippetList.item(i).text() == "Drilling custom" for i in range(panel.ui.snippetList.count()))


def test_options_restore_defaults_includes_only_registered_hotkeys(window):
    window.optionsDlg.load_values()
    window.optionsDlg.restore_defaults()
    assert set(window.optionsDlg.hotkeyEditor.values) == set(window.defaultHotkeys)


def test_keyboard_activation_inserts_once_and_supports_undo(window):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("Keyboard insert", "G1 X42\n")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    editor = window.ui.editor
    editor.setText("OLD\n")
    editor.setSelection(0, 0, 1, 0)
    QTest.keyClick(panel.ui.snippetList, Qt.Key.Key_Return)
    assert editor.text() == "G1 X42\n"
    editor.undo()
    assert editor.text() == "OLD\n"


def test_deleted_cached_snippet_cannot_insert_stale_text(window):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("Deleted insert", "STALE")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    window.snippetsDlg.library.delete(record.id)
    window.ui.editor.setText("UNCHANGED")
    panel.ui.insertButton.click()
    assert window.ui.editor.text() == "UNCHANGED"
    panel.refresh()
    assert panel.ui.snippetList.count() == 0
    assert not panel.ui.insertButton.isEnabled()


def test_refresh_preserves_list_selection_scroll_and_editor_state(window):
    panel = window.snippetsDock
    for index in range(60):
        window.snippetsDlg.library.add(f"Scroll {index:02}", f"G1 X{index}\n")
    panel.refresh()
    panel.ui.searchEdit.setText("Scroll")
    panel.resize(280, 300)
    panel.show()
    QApplication.processEvents()
    listing = panel.ui.snippetList
    listing.setCurrentRow(35)
    listing.scrollToItem(listing.currentItem())
    QApplication.processEvents()
    selected = listing.currentItem().data(Qt.ItemDataRole.UserRole)
    scroll = listing.verticalScrollBar().value()
    editor = window.ui.editor
    editor.setText("G0 X1\nG1 X2\n")
    editor.setSelection(1, 4, 0, 1)
    expected = editor.text(), editor.getSelection(), editor.getCursorPosition(), editor.isModified()
    panel.refresh()
    assert listing.currentItem().data(Qt.ItemDataRole.UserRole) == selected
    assert listing.verticalScrollBar().value() == scroll
    assert (editor.text(), editor.getSelection(), editor.getCursorPosition(), editor.isModified()) == expected


@pytest.mark.parametrize(
    "dialect,lathe,language",
    [
        ("fanuc", False, "fanuc_mill"),
        ("fanuc", True, "fanuc_turn"),
        ("sinumerik", False, "sinumerik_mill"),
        ("sinumerik", True, "sinumerik_turn"),
        ("heidenhain", False, "heidenhain"),
    ],
)
def test_panel_uses_only_active_controller_library(window, dialect, lathe, language):
    window._document_source_dialect = dialect
    window.latheMode = lathe
    panel = window.snippetsDock
    panel.refresh()
    expected = window.snippetsDlg.library.list_snippets(language)
    assert panel._language == language
    assert [
        panel.ui.snippetList.item(i).data(Qt.ItemDataRole.UserRole) for i in range(panel.ui.snippetList.count())
    ] == [record.id for record in expected]


def test_panel_load_failure_is_reported_without_inserting(window, monkeypatch):
    warnings = []
    panel = window.snippetsDock
    editor = window.ui.editor
    editor.setText("UNCHANGED")

    def fail(_language):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(window.snippetsDlg.library, "list_snippets", fail)
    monkeypatch.setattr("app.ui.panels.snippets_panel.QMessageBox.warning", lambda *args: warnings.append(args))
    panel.refresh()
    assert len(warnings) == 1
    assert not panel.ui.insertButton.isEnabled()
    panel.insert_current()
    assert editor.text() == "UNCHANGED"


def test_view_action_reopens_panel_without_resetting_filters(window):
    panel = window.snippetsDock
    panel.ui.groupCombo.setCurrentIndex(panel.ui.groupCombo.findData("cycles"))
    panel.ui.searchEdit.setText("G73")
    panel.close()
    action = panel.toggleViewAction()
    assert not action.isChecked()
    action.trigger()
    assert not panel.isHidden()
    assert panel.ui.groupCombo.currentData() == "cycles"
    assert panel.ui.searchEdit.text() == "G73"
    assert panel.ui.snippetList.count() == 1


@pytest.mark.parametrize("accepted", [False, True])
def test_panel_parameter_form_cancel_or_insert_preserves_editor_contract(window, monkeypatch, accepted):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("Parameterized panel insert", "X{{?X=3|number}} {{selection}}{{cursor}}END")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    editor = window.ui.editor
    editor.setText("BEFORE\nOLD\nAFTER\n")
    editor.setSelection(1, 3, 1, 0)
    before = (
        editor.getSelection(),
        editor.getCursorPosition(),
        editor.firstVisibleLine(),
        editor.horizontalScrollBar().value(),
        editor.isModified(),
    )
    forms = []

    def finish(form):
        forms.append(form)
        assert form.context.selection == "OLD"
        form.fields["X"].setText("42")
        return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected

    monkeypatch.setattr(SnippetInsertDialog, "exec", finish)
    panel.ui.insertButton.click()
    assert len(forms) == 1
    if accepted:
        assert editor.text() == "BEFORE\nX42 OLDEND\nAFTER\n"
        assert editor.getCursorPosition() == (1, 7)
        editor.undo()
        assert editor.text() == "BEFORE\nOLD\nAFTER\n"
    else:
        assert editor.text() == "BEFORE\nOLD\nAFTER\n"
        assert (
            editor.getSelection(),
            editor.getCursorPosition(),
            editor.firstVisibleLine(),
            editor.horizontalScrollBar().value(),
            editor.isModified(),
        ) == before


@pytest.mark.parametrize(
    "group,name",
    [("program", "Program Start"), ("motion", "Rapid Move"), ("cycles", "Drilling"), ("formulas", "MM to INCHES")],
)
@pytest.mark.parametrize("dialect", ["fanuc", "sinumerik", "heidenhain"])
def test_panel_groups_include_controller_program_motion_cycles_and_formulas(window, dialect, group, name):
    window._document_source_dialect = dialect
    panel = window.snippetsDock
    panel.refresh()
    panel.ui.groupCombo.setCurrentIndex(panel.ui.groupCombo.findData(group))
    names = {panel.ui.snippetList.item(i).text() for i in range(panel.ui.snippetList.count())}
    assert name in names


def test_edit_button_opens_manager_for_active_controller(window):
    window._document_source_dialect = "sinumerik"
    panel = window.snippetsDock
    panel.refresh()
    panel.ui.editButton.click()
    assert window.snippetsDlg.isVisible()
    assert window.snippetsDlg.ui.languageCombo.currentData() == "sinumerik_mill"
    window.snippetsDlg.reject()


def test_picture_read_failure_does_not_prevent_plain_snippet_insertion(window, monkeypatch):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("Unavailable picture", "G1 X42\n")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    window.ui.editor.setText("")

    def fail(_snippet_id):
        raise sqlite3.OperationalError("picture unavailable")

    monkeypatch.setattr(window.snippetsDlg.library, "image", fail)
    panel.ui.insertButton.click()
    assert window.ui.editor.text() == "G1 X42\n"
    window.ui.editor.undo()
    assert window.ui.editor.text() == ""


def test_invalid_template_from_panel_reports_error_and_keeps_selection(window, monkeypatch):
    panel = window.snippetsDock
    record = window.snippetsDlg.library.add("Broken template", "{{=1/0}}")
    panel.refresh()
    panel.ui.searchEdit.setText(record.name)
    editor = window.ui.editor
    editor.setText("UNCHANGED")
    editor.setSelection(0, 7, 0, 1)
    expected = editor.getSelection(), editor.getCursorPosition(), editor.isModified()
    warnings = []
    monkeypatch.setattr("app.ui.support.snippet_insertion.QMessageBox.warning", lambda *args: warnings.append(args))
    panel.ui.insertButton.click()
    assert warnings
    assert editor.text() == "UNCHANGED"
    assert (editor.getSelection(), editor.getCursorPosition(), editor.isModified()) == expected
