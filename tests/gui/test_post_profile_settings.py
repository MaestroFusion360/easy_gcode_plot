"""Exercise the embedded desktop editor and its save/discard lifecycle."""

# pylint: disable=protected-access
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app.post_profile_library import PostProfileLibrary
from app.ui.dialogs.options import OptionsDialog
from app.ui.generated.dialogs.snippets import Ui_SnippetsDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(qt_app, tmp_path):
    dialog = OptionsDialog()
    controller = dialog.postProfileSettings
    controller.library = PostProfileLibrary(tmp_path)
    controller.reload()
    yield controller
    dialog.deleteLater()
    qt_app.processEvents()


def select(settings, value):
    widget = settings.ui.postProfileList
    for row in range(widget.count()):
        if widget.item(row).data(Qt.ItemDataRole.UserRole)[1] == value:
            widget.setCurrentRow(row)
            return
    pytest.fail(f"Profile missing: {value}")


def test_settings_embeds_editor_and_protects_builtins(settings):
    assert settings.owner.width() >= 1000
    assert settings.owner.height() >= 700
    for value in ("fanuc_mill", "fanuc_lathe_a", "heidanhain_itnc530"):
        select(settings, value)
        assert not isinstance(settings.editor, QDialog)
        assert not settings.editor.isWindow()
        assert settings.editor.parent() is settings.ui.postProfileEditorHost
        assert settings.editor.ui.nameEdit.isReadOnly()
        assert settings.ui.newPostProfileButton.isEnabled()
        for name in ("save", "rename", "remove"):
            assert not getattr(settings.ui, f"{name}PostProfileButton").isEnabled()
        with pytest.raises(ValueError, match="read-only"):
            settings.editor.save()


def test_management_buttons_match_snippets(settings):
    dialog = QDialog()
    ui = Ui_SnippetsDialog()
    ui.setupUi(dialog)
    for name, snippet in (("new", "add"), ("save", "save"), ("rename", "rename"), ("remove", "delete")):
        button = getattr(settings.ui, f"{name}PostProfileButton")
        reference = getattr(ui, f"{snippet}Button")
        assert button.text() == reference.text() == ""
        assert button.iconSize() == reference.iconSize()
        assert button.accessibleName() == reference.accessibleName()
        assert button.icon().pixmap(24, 24).toImage() == reference.icon().pixmap(24, 24).toImage()
        assert not button.icon().isNull()
    dialog.deleteLater()


def test_add_creates_embedded_draft_and_save_preserves_controller(settings):
    select(settings, "heidanhain_itnc530")
    settings.ui.newPostProfileButton.click()
    assert not settings.library.list_profiles()
    assert not settings.editor.ui.nameEdit.isReadOnly()
    settings.editor.ui.nameEdit.setText("Workshop")
    settings.ui.savePostProfileButton.click()
    path = settings.editor.path
    assert settings._selected() == ("user", path)
    assert settings.library.load(path)["name"] == "Workshop"
    assert settings.library.load(path)["id"] == "heidanhain_itnc530"
    assert not settings.editor.is_dirty()


def test_cancel_settings_discards_new_draft(settings):
    settings._new()
    settings.editor.ui.nameEdit.setText("Unsaved")
    settings.owner.reject()
    assert not settings.library.list_profiles()
    assert settings.editor.read_only


def test_cancel_settings_preserves_existing_file(settings):
    path = settings.library.duplicate("fanuc_mill", "Shop")
    before = Path(path).read_bytes()
    settings.reload(path)
    settings.editor.ui.linearMoveEdit.setText("G1 {unknown}")
    settings.owner.reject()
    assert Path(path).read_bytes() == before


@pytest.mark.parametrize("answer", ["Save", "Discard", "Cancel"])
def test_switching_profiles_resolves_pending_edits(settings, monkeypatch, answer):
    path = settings.library.duplicate("fanuc_mill", "Shop")
    settings.reload(path)
    settings.editor.ui.nameEdit.setText("Changed")
    monkeypatch.setattr(QMessageBox, "question", lambda *a: getattr(QMessageBox.StandardButton, answer))
    select(settings, "fanuc_lathe_a")
    assert settings.library.load(path)["name"] == ("Changed" if answer == "Save" else "Shop")
    assert settings._selected()[1] == (path if answer == "Cancel" else "fanuc_lathe_a")
    assert settings.editor.read_only == (answer != "Cancel")


def test_invalid_save_blocks_navigation_and_keeps_edits(settings, monkeypatch):
    settings._new()
    row = settings.ui.postProfileList.currentRow()
    settings.editor.ui.linearMoveEdit.setText("G1 {unknown}")
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save)
    select(settings, "fanuc_lathe_a")
    assert settings.ui.postProfileList.currentRow() == row
    assert settings.editor.ui.linearMoveEdit.text() == "G1 {unknown}"
    assert settings.ui.postProfileErrorLabel.text()
    assert not settings.library.list_profiles()


def test_save_failure_retains_draft(settings, monkeypatch):
    settings._new()

    def fail(*_args):
        raise OSError("Disk unavailable")

    monkeypatch.setattr(settings.library, "save", fail)
    assert not settings.apply()
    assert settings.editor.path is None
    assert settings.ui.postProfileErrorLabel.text() == "Disk unavailable"


def test_rename_and_remove_user_profile(settings, monkeypatch):
    path = settings.library.duplicate("fanuc_mill", "Shop")
    settings.reload(path)
    monkeypatch.setattr("app.ui.dialogs.post_profile_settings.QInputDialog.getText", lambda *a, **k: ("Renamed", True))
    settings.ui.renamePostProfileButton.click()
    assert settings.apply()
    assert settings.editor.path == path
    assert settings.library.load(path)["name"] == "Renamed"
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    settings.ui.removePostProfileButton.click()
    assert not Path(path).exists()
    assert settings.editor.read_only


def test_return_to_discarded_draft_is_editable(settings, monkeypatch):
    settings._new()
    row = settings.ui.postProfileList.currentRow()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    select(settings, "fanuc_lathe_a")
    settings.ui.postProfileList.setCurrentRow(row)
    assert settings.editor.profile["id"] == "fanuc_mill"
    assert settings.editor.path is None
    assert settings.apply()


def test_saved_field_can_be_changed_back_to_original(settings):
    path = settings.library.duplicate("fanuc_mill", "Shop")
    settings.reload(path)
    original = settings.editor.ui.linearMoveEdit.text()
    settings.editor.ui.linearMoveEdit.setText("G01")
    assert settings.apply()
    settings.editor.ui.linearMoveEdit.setText(original)
    assert settings.editor.is_dirty()
    assert settings.apply()
    assert settings.library.load(path)["motion"]["linearMove"] == original


@pytest.mark.parametrize("valid", [True, False])
def test_settings_ok_validates_and_saves_profile(settings, monkeypatch, valid):
    settings._new()
    if not valid:
        settings.editor.ui.linearMoveEdit.setText("G1 {unknown}")
    monkeypatch.setattr(settings.owner, "_valid_colors", lambda *_: True)
    monkeypatch.setattr(settings.owner, "_apply_hotkeys", lambda *_: True)
    assert settings.owner._validate_pending_options(None) == valid
    assert bool(settings.library.list_profiles()) == valid
