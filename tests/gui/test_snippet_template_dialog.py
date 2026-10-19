"""Snippet manager, parameter entry and one-step editor insertion."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMenu, QPlainTextEdit, QPushButton, QScrollArea

from app.gcode.snippet_defaults import LANGUAGES, default_snippets
from app.gcode.snippet_templates import TemplateContext, render
from app.gcode.snippets import SnippetLibrary
from app.ui.dialogs import snippet_insert as insert_module
from app.ui.dialogs import snippets as module
from app.ui.dialogs.snippet_insert import SnippetInsertDialog
from app.ui.dialogs.snippets import SnippetsDialog
from app.ui.panels.snippets_panel import SnippetsPanel
from app.ui.support.snippet_preview import png_bytes


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qt_app, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "config_path", lambda: str(tmp_path / "config.ini"))
    instance = SnippetsDialog()
    yield instance
    instance.library.close()
    instance.deleteLater()
    qt_app.processEvents()


def select(dialog, name):
    index = next(i for i, item in enumerate(dialog.snippets) if item.name == name)
    dialog.ui.snippetList.setCurrentRow(index)
    return dialog.snippets[index]


def owner_window(editor=None):
    owner = QMainWindow()
    owner.ui = SimpleNamespace(editor=editor or QsciScintilla())
    return owner


def test_dialog_opens_with_controller_list_and_template_editor(dialog):
    dialog.show()
    QApplication.processEvents()
    assert dialog.ui.languageCombo.count() == 5
    assert dialog.ui.snippetList.count() == len(dialog.snippets)
    names = {dialog.ui.snippetList.item(index).text() for index in range(dialog.ui.snippetList.count())}
    assert {"Program Start", "Toolchange", "Drill point (formula)"} <= names
    assert dialog.ui.snippetList.currentRow() == 0
    assert "{{" in dialog.ui.snippetEditor.toPlainText()
    assert dialog.ui.insertButton.isEnabled()
    assert not hasattr(dialog.ui, "snippetTabs")
    assert not hasattr(dialog.ui, "previewLayout")
    assert dialog.ui.pictureButton.isVisible()


def test_plain_template_inserts_rendered_text_without_extra_dialog(dialog):
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    expected = "; 1910\nG0 X0\n"
    dialog.ui.snippetEditor.setPlainText("; {{=1000*12/(PI*2):0}}\n{{cursor}}G0 X0\n")
    dialog.show()
    QApplication.processEvents()
    owner.ui.editor.setText("OLD")
    owner.ui.editor.setSelection(0, 0, 0, 3)

    dialog.insert_current()

    assert owner.ui.editor.text() == expected
    assert dialog.isVisible()
    assert owner.ui.editor.getCursorPosition() == (1, 0)
    owner.ui.editor.undo()
    assert owner.ui.editor.text() == "OLD"
    owner.deleteLater()


def test_unchanged_saved_snippet_inserts_without_writing_to_library(dialog, monkeypatch):
    record = dialog.library.add("Read-only insertion", "G1 X42\n")
    dialog.load_snippets()
    select(dialog, record.name)
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    owner.ui.editor.setText("OLD")
    owner.ui.editor.setSelection(0, 0, 0, 3)
    writes, warnings = [], []

    def readonly(*_args):
        writes.append(True)
        raise sqlite3.OperationalError("read-only database")

    monkeypatch.setattr(dialog.library, "update_body", readonly)
    monkeypatch.setattr(dialog.library, "update_content", readonly)
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    dialog.insert_current()
    assert not writes and not warnings
    assert owner.ui.editor.text() == "G1 X42\n"
    owner.ui.editor.undo()
    assert owner.ui.editor.text() == "OLD"
    owner.deleteLater()


def test_parametrized_snippet_opens_insert_dialog_and_cancel_keeps_editor(dialog, monkeypatch):
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    dialog.ui.snippetEditor.setPlainText("X{{?X=10}}\n")
    owner.ui.editor.setText("OLD\n")

    class CancelledDialog:
        def __init__(self, *_args, **_kwargs):
            self.rendered = None

        def exec(self):
            return QDialog.DialogCode.Rejected

        def deleteLater(self):
            pass

    monkeypatch.setattr(insert_module, "SnippetInsertDialog", CancelledDialog)

    dialog.insert_current()

    assert owner.ui.editor.text() == "OLD\n"
    owner.deleteLater()


def test_parametrized_snippet_inserts_values_from_insert_dialog(dialog, monkeypatch):
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    source = "(Привет {{?Name=NC}})\n{{cursor}}S{{=1000*12/(PI*2):0}}\n"
    dialog.ui.snippetEditor.setPlainText(source)

    class AcceptedDialog:
        def __init__(self, text, context=None, picture=None, parent=None):
            self.rendered = render(text, {"Name": "Мир"}, context)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    monkeypatch.setattr(insert_module, "SnippetInsertDialog", AcceptedDialog)

    dialog.insert_current()

    assert owner.ui.editor.text() == "(Привет Мир)\nS1910\n"
    assert owner.ui.editor.getCursorPosition() == (1, 0)
    owner.ui.editor.undo()
    assert owner.ui.editor.text() == ""
    owner.deleteLater()


def test_insert_dialog_exposes_fields_and_validates_before_accepting(qt_app):
    source = "; D={{?D=10}} mm; Angle={{?Angle=118}} deg\n; H={{=(D/2)/TAN(Angle/2):4}} mm\n"
    insert = SnippetInsertDialog(source, TemplateContext())
    try:
        assert set(insert.fields) == {"D", "Angle"}
        assert insert.rendered is not None
        insert.fields["Angle"].setText("0")
        assert insert.rendered is None
        assert not insert.ok_button.isEnabled()
        insert.fields["Angle"].setText("118")
        assert insert.ok_button.isEnabled()
        assert "H=3.0043 mm" in insert.rendered.text
    finally:
        insert.deleteLater()


def test_insert_dialog_shows_stored_picture_read_only(qt_app):
    image = QImage(20, 10, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    data = png_bytes(image)
    insert = SnippetInsertDialog("G0 X0\n", TemplateContext(), data)
    try:
        assert insert.picture_label is not None
        assert not insert.picture_label.image.isNull()
        assert not insert.picture_label.acceptDrops()
        assert not insert.findChildren(QPlainTextEdit)
        assert all(area.isHidden() for area in insert.findChildren(QScrollArea))
    finally:
        insert.deleteLater()


def test_insert_dialog_hides_missing_picture_area(qt_app):
    insert = SnippetInsertDialog("G0 X0\n", TemplateContext())
    try:
        assert insert.picture_label is None
    finally:
        insert.deleteLater()


def test_insert_dialog_does_not_replace_invalid_default_with_first_choice(qt_app):
    form = SnippetInsertDialog("G{{?ReturnMode=97|int|choices=98,99}}")
    try:
        assert form.fields["ReturnMode"].currentIndex() == -1
        assert form.rendered is None
        assert not form.ok_button.isEnabled()
        form.accept()
        assert form.result() == QDialog.DialogCode.Rejected
        form.fields["ReturnMode"].setCurrentText("99")
        assert form.rendered.text == "G99"
        assert form.ok_button.isEnabled()
    finally:
        form.deleteLater()


def test_insert_dialog_preserves_empty_optional_choice_and_its_prefix(qt_app):
    form = SnippetInsertDialog("{{?Direction=|int|optional|choices=3,4|prefix=M}}")
    try:
        assert form.fields["Direction"].currentText() == ""
        assert form.rendered.text == ""
        assert form.ok_button.isEnabled()
        form.fields["Direction"].setCurrentText("4")
        assert form.rendered.text == "M4"
        form.fields["Direction"].setCurrentText("")
        assert form.rendered.text == ""
    finally:
        form.deleteLater()


def test_insert_picture_can_be_enlarged_without_editing(qt_app, picture_file, monkeypatch):
    image = QImage(str(picture_file))
    insert = SnippetInsertDialog("X{{?X=10}}", picture=picture_file.read_bytes())
    inspected = []

    def inspect(viewer):
        label = viewer.findChild(QScrollArea).widget()
        before = label.pixmap().width()
        plus = next(button for button in viewer.findChildren(QPushButton) if button.text() == "+")
        plus.click()
        inspected.append(label.pixmap().width() > before)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    try:
        QTest.mouseClick(insert.picture_label, Qt.MouseButton.LeftButton)
        assert inspected == [True]
        assert insert.picture_label.image == image
        assert not insert.findChildren(QPlainTextEdit)
    finally:
        insert.deleteLater()


def test_saving_text_preserves_the_existing_illustration(dialog, tmp_path):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    assert original

    dialog.ui.snippetEditor.setPlainText("G0 X1\n")
    dialog.save_current()

    assert dialog.library.image(selected.id) == original
    with SnippetLibrary(str(tmp_path / "snippets.db")) as reopened:
        assert reopened.image(selected.id) == original


@pytest.fixture
def picture_file(tmp_path):
    image = QImage(24, 12, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.green)
    path = tmp_path / "picture.png"
    assert image.save(str(path))
    return path


def test_picture_button_and_menu_follow_selection(dialog):
    button = dialog.ui.pictureButton
    assert button.isEnabled() and button.icon().isNull()
    assert isinstance(button, QPushButton) and button.text() == "Picture"
    assert button.menu() is dialog.findChild(QMenu, "pictureMenu")
    assert [action.text() for action in dialog.findChild(QMenu, "pictureMenu").actions()] == [
        "Load Picture...",
        "Paste Picture",
        "Remove Picture",
    ]
    dialog.ui.snippetList.setCurrentRow(-1)
    assert not button.isEnabled()


def test_picture_button_opens_its_dropdown_menu(dialog):
    menu = dialog.findChild(QMenu, "pictureMenu")
    opened = []
    menu.aboutToShow.connect(lambda: opened.append(True))
    QTimer.singleShot(0, menu.close)
    dialog.ui.pictureButton.showMenu()
    assert opened == [True]
    assert dialog.ui.pictureButton.menu() is menu


def test_update_defaults_button_resolves_dirty_changes_and_refreshes(dialog, monkeypatch):
    calls = []
    refresh_defaults = dialog.library.refresh_defaults

    def refresh(language, pictures=None):
        calls.append(language)
        assert pictures and "Circular Move" in pictures
        return refresh_defaults(language, pictures)

    monkeypatch.setattr(dialog.library, "refresh_defaults", refresh)
    monkeypatch.setattr(module.QMessageBox, "information", lambda *_args: None)
    dialog.ui.snippetEditor.setPlainText("EDITED")
    monkeypatch.setattr(module.QMessageBox, "question", lambda *_args: module.QMessageBox.StandardButton.Cancel)
    dialog.ui.updateDefaultsButton.click()
    assert not calls
    assert dialog.ui.snippetEditor.toPlainText() == "EDITED"
    monkeypatch.setattr(module.QMessageBox, "question", lambda *_args: module.QMessageBox.StandardButton.Save)
    dialog.ui.updateDefaultsButton.click()
    assert calls == ["fanuc_mill"]
    assert dialog.ui.snippetEditor.toPlainText() == dict(default_snippets("fanuc_mill"))["Program Start"]
    assert not dialog.ui.updateDefaultsButton.isEnabled()


@pytest.mark.parametrize("custom", [False, True])
def test_load_picture_saves_text_and_blob_and_survives_reopening(dialog, picture_file, monkeypatch, custom):
    if custom:
        dialog.add_snippet()
    selected = dialog.snippets[dialog.ui.snippetList.currentRow()]
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(picture_file), ""))
    dialog.findChild(QMenu, "pictureMenu").actions()[0].trigger()
    dialog.ui.snippetEditor.setPlainText("G1 X42\n")
    assert dialog.ui.saveButton.isEnabled()
    assert dialog.save_current()
    dialog.load_snippets()
    with SnippetLibrary(str(dialog.database_path)) as reopened:
        assert reopened.image(selected.id) == picture_file.read_bytes()
        assert next(item for item in reopened.list_snippets() if item.id == selected.id).body == "G1 X42\n"


def test_paste_picture_and_remove_only_selected_picture(dialog, picture_file):
    other = select(dialog, "Circular Move")
    original = dialog.library.image(other.id)
    selected = select(dialog, "Program Start")
    clipboard = QApplication.clipboard()
    clipboard.setImage(QImage(str(picture_file)))
    try:
        dialog.findChild(QMenu, "pictureMenu").aboutToShow.emit()
        paste = dialog.findChild(QMenu, "pictureMenu").actions()[1]
        assert paste.isEnabled()
        paste.trigger()
        assert dialog.library.image(selected.id) is None
        assert dialog.save_current()
        assert dialog.library.image(selected.id) == png_bytes(clipboard.image())
        dialog.findChild(QMenu, "pictureMenu").aboutToShow.emit()
        remove = dialog.findChild(QMenu, "pictureMenu").actions()[2]
        assert remove.isEnabled()
        remove.trigger()
        assert dialog.library.image(selected.id) is not None
        assert dialog.save_current()
        assert dialog.library.image(selected.id) is None
        assert dialog.library.image(other.id) == original
    finally:
        clipboard.clear()


def test_missing_standard_picture_survives_reopening_and_is_restored_only_by_update_defaults(dialog, monkeypatch):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    assert original
    dialog.remove_picture()
    assert dialog.save_current()
    reopened = SnippetsDialog()
    try:
        assert reopened.library.image(selected.id) is None
        assert reopened.ui.updateDefaultsButton.isEnabled()
        monkeypatch.setattr(module.QMessageBox, "information", lambda *_args: None)
        reopened.ui.updateDefaultsButton.click()
        assert reopened.library.image(selected.id) == original
        assert not reopened.ui.updateDefaultsButton.isEnabled()
    finally:
        reopened.library.close()
        reopened.deleteLater()


@pytest.mark.parametrize("answer", ["Save", "Discard", "Cancel"])
@pytest.mark.parametrize("change", ["replace", "remove"])
def test_picture_only_changes_obey_selection_save_discard_cancel(dialog, picture_file, monkeypatch, answer, change):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    row = dialog.ui.snippetList.currentRow()
    if change == "remove":
        dialog.remove_picture()
        expected = None
    else:
        monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(picture_file), ""))
        dialog.load_picture()
        expected = picture_file.read_bytes()
    assert dialog.ui.saveButton.isEnabled()
    # A text edit followed by undo must not clear the image's dirty state.
    dialog.ui.snippetEditor.setPlainText(selected.text + "\n")
    dialog.ui.snippetEditor.setPlainText(selected.text)
    assert dialog.ui.saveButton.isEnabled()
    monkeypatch.setattr(
        module.QMessageBox, "question", lambda *_args: getattr(module.QMessageBox.StandardButton, answer)
    )
    dialog.ui.snippetList.setCurrentRow(0)
    assert dialog.library.image(selected.id) == (expected if answer == "Save" else original)
    assert dialog.ui.snippetList.currentRow() == (row if answer == "Cancel" else 0)
    if answer == "Cancel":
        assert dialog.ui.saveButton.isEnabled()


def test_invalid_picture_keeps_saved_blob(dialog, tmp_path, monkeypatch):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    path = tmp_path / "invalid.png"
    path.write_bytes(b"not a picture")
    warnings = []
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    dialog.load_picture()
    assert warnings
    assert not dialog.ui.saveButton.isEnabled()
    assert dialog.library.image(selected.id) == original


@pytest.mark.parametrize("extension", ["jpg", "bmp", "webp", "svg"])
def test_load_supported_picture_formats(dialog, tmp_path, monkeypatch, extension):
    path = tmp_path / f"picture.{extension}"
    if extension == "svg":
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10"/></svg>'
        )
    else:
        image = QImage(20, 10, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.blue)
        assert image.save(str(path))
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    selected = dialog.snippets[dialog.ui.snippetList.currentRow()]
    dialog.load_picture()
    assert dialog.save_current()
    assert dialog.library.image(selected.id) == path.read_bytes()


@pytest.mark.parametrize("oversized", ["bytes", "dimensions"])
def test_picture_limits_preserve_original_blob(dialog, tmp_path, monkeypatch, oversized):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    path = tmp_path / "oversized.svg"
    if oversized == "bytes":
        path.write_bytes(b" " * (10 * 1024 * 1024 + 1))
    else:
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="4097" height="10"/>')
    warnings = []
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    dialog.load_picture()
    assert warnings
    assert not dialog.ui.saveButton.isEnabled()
    assert dialog.library.image(selected.id) == original


@pytest.mark.parametrize("destination", ["close", "language"])
@pytest.mark.parametrize("answer", ["Save", "Discard", "Cancel"])
def test_picture_changes_obey_close_and_language_prompts(dialog, monkeypatch, destination, answer):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    dialog.remove_picture()
    prompts = []

    def respond(*_args):
        prompts.append(True)
        return getattr(module.QMessageBox.StandardButton, answer)

    monkeypatch.setattr(module.QMessageBox, "question", respond)
    if destination == "close":
        dialog.reject()
    else:
        dialog.ui.languageCombo.setCurrentIndex(dialog.ui.languageCombo.findData("heidenhain"))
        assert dialog.ui.languageCombo.currentData() == ("fanuc_mill" if answer == "Cancel" else "heidenhain")
    assert len(prompts) == 1
    assert dialog.library.image(selected.id) == (None if answer == "Save" else original)
    assert dialog.ui.saveButton.isEnabled() == (answer == "Cancel")


def test_manager_passes_saved_picture_to_parameter_insert(dialog, picture_file, monkeypatch):
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(picture_file), ""))
    dialog.load_picture()
    dialog.ui.snippetEditor.setPlainText("G0 X{{?X=42}}\n")
    pictures = []

    def accept(insert):
        assert not insert.findChildren(QPlainTextEdit)
        pictures.append(insert.picture_label.image)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SnippetInsertDialog, "exec", accept)
    dialog.insert_current()
    assert len(pictures) == 1 and pictures[0] == QImage(str(picture_file))
    assert owner.ui.editor.text() == "G0 X42\n"
    owner.deleteLater()


def test_failed_image_save_preserves_blob_and_unsaved_changes(dialog, monkeypatch):
    selected = select(dialog, "Circular Move")
    original = dialog.library.image(selected.id)
    dialog.remove_picture()
    dialog.ui.snippetEditor.setPlainText("G0 X42")
    warnings = []

    def fail(*_args):
        raise sqlite3.OperationalError("read-only database")

    monkeypatch.setattr(dialog.library, "update_content", fail)
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    assert not dialog.save_current()
    assert warnings
    assert dialog.ui.saveButton.isEnabled()
    assert dialog.library.image(selected.id) == original


def test_quick_snippet_uses_saved_picture_after_manager_edit(dialog, picture_file, monkeypatch):
    selected = select(dialog, "Circular Move")
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *_args: (str(picture_file), ""))
    dialog.load_picture()
    dialog.ui.snippetEditor.setPlainText("G0 X42\n")
    assert dialog.save_current()
    owner = owner_window()
    owner.snippetsDlg = dialog
    toolbar = SnippetsPanel(owner)
    try:
        toolbar.insert_id(selected.id)
        assert owner.ui.editor.text() == "G0 X42\n"
    finally:
        owner.deleteLater()


def test_file_literal_without_document_reports_error_and_keeps_editor(dialog, monkeypatch):
    owner = owner_window()
    dialog.setParent(owner, dialog.windowFlags())
    select(dialog, "Document header")
    owner.ui.editor.setText("OLD\n")
    warnings = []
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: warnings.append(args[2]))

    dialog.insert_current()

    assert owner.ui.editor.text() == "OLD\n"
    assert warnings and "Save the document" in warnings[0]
    owner.deleteLater()


def test_v2_schema_upgrades_images_without_losing_text_order_or_identifiers(tmp_path):
    path = tmp_path / "snippets.db"
    with SnippetLibrary(str(path)) as library:
        saved = library.add("Custom", "G1 X42")
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE snippet_images")
        connection.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    with SnippetLibrary(str(path)) as library:
        assert library.list_snippets() == [saved]
        library.update_content(saved.id, saved.body, b"picture")
        assert library.image(saved.id) == b"picture"
        library.delete(saved.id)
        assert library.image(saved.id) is None


def test_reopening_keeps_user_text_until_explicit_defaults_update(tmp_path):
    path = str(tmp_path / "snippets.db")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        start = next(record for record in library.list_snippets() if record.name == "Program Start")
        library.update_body(start.id, "MY PROGRAM START")
        custom = library.add("My custom template", "MY OWN PROGRAM")
    with SnippetLibrary(path) as library:
        library.ensure_defaults()
        records = {record.id: record for record in library.list_snippets()}
        assert records[start.id].body == "MY PROGRAM START"
        library.refresh_defaults("fanuc_mill")
        records = {record.id: record for record in library.list_snippets()}
        assert records[start.id].body == dict(default_snippets("fanuc_mill"))["Program Start"]
        assert records[custom.id] == custom


@pytest.mark.parametrize("language", ["fanuc_mill", "sinumerik_mill", "heidenhain", "fanuc_turn", "sinumerik_turn"])
def test_manager_create_rename_reorder_delete_persists_only_selected_library(dialog, monkeypatch, language):
    dialog.ui.languageCombo.setCurrentIndex(dialog.ui.languageCombo.findData(language))
    other = "heidenhain" if language != "heidenhain" else "fanuc_mill"
    untouched = dialog.library.list_snippets(other)
    dialog.ui.addButton.click()
    created = dialog.snippets[dialog.ui.snippetList.currentRow()]
    dialog.ui.snippetEditor.setPlainText("CUSTOM TEXT")
    dialog.ui.saveButton.click()
    monkeypatch.setattr(module.QInputDialog, "getText", lambda *_args, **_kwargs: ("Renamed custom", True))
    dialog.ui.renameButton.click()
    dialog.ui.upButton.click()
    row = dialog.ui.snippetList.currentRow()
    records = dialog.library.list_snippets(language)
    assert records[row].id == created.id
    assert records[row].name == "Renamed custom" and records[row].body == "CUSTOM TEXT"
    dialog.load_snippets()
    select(dialog, "Renamed custom")
    monkeypatch.setattr(module.QMessageBox, "question", lambda *_args: module.QMessageBox.StandardButton.Yes)
    dialog.ui.deleteButton.click()
    assert all(item.id != created.id for item in dialog.library.list_snippets(language))
    assert dialog.library.list_snippets(other) == untouched
    assert not dialog.ui.saveButton.isEnabled()


@pytest.mark.parametrize("operation", ["add", "rename", "reorder", "delete"])
def test_failed_manager_mutation_preserves_database_and_display(dialog, monkeypatch, operation):
    select(dialog, "Linear Move")
    before = dialog.library.list_snippets()
    names = [item.name for item in dialog.snippets]
    selected = dialog.ui.snippetList.currentRow()
    warnings = []

    def fail(*_args, **_kwargs):
        raise sqlite3.OperationalError("read-only database")

    monkeypatch.setattr(dialog.library, operation, fail)
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    monkeypatch.setattr(module.QMessageBox, "question", lambda *_args: module.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(module.QInputDialog, "getText", lambda *_args, **_kwargs: ("Renamed", True))
    buttons = {
        "add": dialog.ui.addButton,
        "rename": dialog.ui.renameButton,
        "reorder": dialog.ui.upButton,
        "delete": dialog.ui.deleteButton,
    }
    buttons[operation].click()
    assert [(item.id, item.name, item.body, item.sort_order) for item in dialog.library.list_snippets()] == [
        (item.id, item.name, item.body, item.sort_order) for item in before
    ]
    assert [item.name for item in dialog.snippets] == names
    assert dialog.ui.snippetList.currentRow() == selected
    assert warnings


def test_failed_text_save_keeps_draft_and_blocks_language_switch(dialog, monkeypatch):
    saved = dialog.snippets[dialog.ui.snippetList.currentRow()]
    dialog.ui.snippetEditor.setPlainText("UNSAVED DRAFT")
    warnings = []

    def fail(*_args):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(dialog.library, "update_body", fail)
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *_args: warnings.append(True))
    monkeypatch.setattr(module.QMessageBox, "question", lambda *_args: module.QMessageBox.StandardButton.Save)
    dialog.ui.languageCombo.setCurrentIndex(dialog.ui.languageCombo.findData("heidenhain"))
    assert warnings
    assert dialog.ui.languageCombo.currentData() == "fanuc_mill"
    assert dialog.ui.snippetEditor.toPlainText() == "UNSAVED DRAFT"
    assert dialog.ui.saveButton.isEnabled()
    assert dialog.library.list_snippets()[0].body == saved.text


@pytest.mark.parametrize(
    "language,name,source",
    [(language, name, source) for language, _label in LANGUAGES for name, source in default_snippets(language)],
    ids=lambda value: value.splitlines()[0] if isinstance(value, str) else str(value),
)
def test_every_bundled_template_keeps_defaults_in_the_insert_form(qt_app, language, name, source):
    context = TemplateContext(file=Path(__file__))
    form = SnippetInsertDialog(source, context)
    try:
        assert form.ok_button.isEnabled(), (language, name, form.error.text())
        assert form.rendered == render(source, context=context), (language, name)
        form.accept()
        assert form.result() == QDialog.DialogCode.Accepted
    finally:
        form.deleteLater()


def test_itnc_insert_form_keeps_explicit_coordinate_signs_after_editing(qt_app):
    source = dict(default_snippets("heidenhain"))["Rapid Move"]
    form = SnippetInsertDialog(source)
    try:
        form.fields["X"].setText("12.5")
        form.fields["Y"].setText("-4")
        form.fields["Z"].setText("0")
        assert form.rendered.text == "L X+12.5 Y-4 Z+0 R0 FMAX\n"
        assert form.ok_button.isEnabled()
    finally:
        form.deleteLater()
