"""Persistent G-code snippets dialog."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QFile, QIODevice, QSignalBlocker
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox

from app.gcode.snippets.snippet_defaults import LANGUAGES, default_snippets
from app.gcode.snippets.snippet_templates import TemplateContext
from app.gcode.snippets.snippets import SnippetLibrary
from app.settings import config_path
from app.ui.generated.dialogs.snippets import Ui_SnippetsDialog
from app.ui.support.snippet_insertion import insert_snippet
from app.ui.support.snippet_preview import picture_image, png_bytes

LOGGER = logging.getLogger(__name__)


def _drilling_pictures():
    pictures = {}
    for language, _label in LANGUAGES:
        for name, _body in default_snippets(language):
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            resource = QFile(f":/resource/snippets/drilling_cycles/{language}--{slug}.svg")
            if resource.open(QIODevice.OpenModeFlag.ReadOnly):
                pictures[(language, name)] = bytes(resource.readAll())
                resource.close()
    return pictures


@dataclass(slots=True)
class _Snippet:
    id: int
    name: str
    text: str


class SnippetsDialog(QDialog):
    """Manage reusable G-code templates and insert rendered snippets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_SnippetsDialog()
        self.ui.setupUi(self)
        self.ui.splitter.setStretchFactor(0, 0)
        self.ui.splitter.setStretchFactor(1, 1)
        self.ui.splitter.setSizes([230, 850])
        self.ui.previewSplitter.setStretchFactor(0, 1)
        self.ui.previewSplitter.setStretchFactor(1, 2)
        self.ui.previewSplitter.setSizes([300, 550])
        config_file = Path(config_path())
        self.database_path = config_file.with_name("snippets.db")
        self.legacy_directory = config_file.with_name("snippets")
        self.library = None
        self._language_id = "fanuc_mill"
        self.snippets: list[_Snippet] = []
        self._loading = False
        self._active_row = -1
        self._dirty = False
        self._picture = None
        self._saved_picture = None
        self._picture_loaded = False
        self._preview_picture = None
        self._picture_menu = QMenu(self)
        self._picture_menu.setObjectName("pictureMenu")
        self._picture_menu.addAction(QCoreApplication.translate("SnippetsDialog", "Load Picture..."), self.load_picture)
        self._paste_picture_action = self._picture_menu.addAction(
            QCoreApplication.translate("SnippetsDialog", "Paste Picture"), self.paste_picture
        )
        self._remove_picture_action = self._picture_menu.addAction(
            QCoreApplication.translate("SnippetsDialog", "Remove Picture"), self.remove_picture
        )
        self._picture_menu.aboutToShow.connect(self._update_picture_menu)
        self.ui.pictureButton.setMenu(self._picture_menu)
        try:
            self.library = SnippetLibrary(str(self.database_path))
            language_labels = {
                "fanuc_turn": QCoreApplication.translate("SnippetsDialog", "Fanuc Lathe"),
                "fanuc_b_turn": QCoreApplication.translate("SnippetsDialog", "Fanuc Lathe (B)"),
                "sinumerik_turn": QCoreApplication.translate("SnippetsDialog", "Sinumerik Lathe"),
            }
            for language_id, label in self.library.list_languages():
                self.ui.languageCombo.addItem(language_labels.get(language_id, label), language_id)
            self._connect()
            self.load_snippets()
        except Exception:
            if self.library is not None:
                self.library.close()
            raise

    def _connect(self):
        self.ui.picturePreview.dropped.connect(self._set_picture)
        self.ui.picturePreview.failed.connect(self._picture_error)
        self.ui.languageCombo.currentIndexChanged.connect(self._language_changed)
        self.ui.snippetList.currentRowChanged.connect(self._selection_changed)
        self.ui.snippetEditor.textChanged.connect(self._editor_changed)
        self.ui.addButton.clicked.connect(self.add_snippet)
        self.ui.saveButton.clicked.connect(self.save_current)
        self.ui.updateDefaultsButton.clicked.connect(self.update_defaults)
        self.ui.renameButton.clicked.connect(self.rename_current)
        self.ui.deleteButton.clicked.connect(self.delete_current)
        self.ui.upButton.clicked.connect(lambda: self.move_current(-1))
        self.ui.downButton.clicked.connect(lambda: self.move_current(1))
        self.ui.insertButton.clicked.connect(self.insert_current)

    def _seed_pictures(self):
        pictures = {}
        for language_id, _label in LANGUAGES:
            for name, asset in (
                ("Rapid Move", "rapid"),
                ("Linear Move", "linear"),
                ("Circular Move", "circle"),
                ("Drill point (formula)", "drill_point"),
            ):
                if name == "Circular Move" and language_id.endswith("turn"):
                    asset = "turning_arc"
                elif name in {"Rapid Move", "Linear Move"} and language_id.endswith("turn"):
                    asset = f"turning_{asset}"
                resource = QFile(f":/resource/snippets/{asset}.svg")
                if resource.open(QIODevice.OpenModeFlag.ReadOnly):
                    pictures[(language_id, name)] = bytes(resource.readAll())
                    resource.close()
        cycles = _drilling_pictures()
        pictures.update(cycles)
        self._bundled_pictures = pictures
        self.library.ensure_illustrations(cycles, key="template_drilling_illustrations_v1")
        self.library.ensure_illustrations(pictures)
        motions = {key: data for key, data in pictures.items() if key[1] in {"Rapid Move", "Linear Move"}}
        self.library.ensure_illustrations(motions, key="template_motion_illustrations_v1")
        type_b = {key: data for key, data in pictures.items() if key[0] == "fanuc_b_turn"}
        self.library.ensure_illustrations(type_b, key="template_illustrations_fanuc_b_turn_v1")

    def load_snippets(self):
        self.library.import_legacy_directory(self.legacy_directory)
        self.library.ensure_defaults()
        self._seed_pictures()
        self.snippets = [
            _Snippet(record.id, record.name, record.body) for record in self.library.list_snippets(self._language_id)
        ]
        self._refresh_list(0 if self.snippets else -1)

    def _language_changed(self, index):
        language_id = self.ui.languageCombo.itemData(index)
        if not language_id or language_id == self._language_id:
            return
        if not self._resolve_dirty():
            with QSignalBlocker(self.ui.languageCombo):
                self.ui.languageCombo.setCurrentIndex(self.ui.languageCombo.findData(self._language_id))
            return
        self._language_id = language_id
        self.load_snippets()

    def showEvent(self, event):
        language_id = self.document_language()
        if language_id is not None:
            index = self.ui.languageCombo.findData(language_id)
            if index >= 0:
                self.ui.languageCombo.setCurrentIndex(index)
        super().showEvent(event)

    def document_language(self):
        owner = self.parent()
        if owner is None:
            return None
        dialect = getattr(owner, "_document_source_dialect", "fanuc")
        file_type = getattr(getattr(owner, "ui", None), "fileTypeCombo", None)
        if file_type is not None and file_type.currentIndex() == 2:
            dialect = "heidenhain"
        if dialect == "heidenhain":
            return "heidenhain"
        if dialect == "fanuc" and getattr(owner, "latheMode", False):
            if str(getattr(owner, "latheGcodeSystem", "A")).upper() == "B":
                return "fanuc_b_turn"
        return f"{dialect}_{'turn' if getattr(owner, 'latheMode', False) else 'mill'}"

    def _show_save_error(self):
        QMessageBox.warning(
            self, self.windowTitle(), QCoreApplication.translate("SnippetsDialog", "Could not save snippet.")
        )

    def _write_order(self) -> bool:
        try:
            self.library.reorder([item.id for item in self.snippets], self._language_id)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_order_save_failed path=%s", self.database_path)
            self._show_save_error()
            return False
        return True

    def _refresh_list(self, row: int):
        self._loading = True
        self.ui.snippetList.clear()
        self.ui.snippetList.addItems(item.name for item in self.snippets)
        self.ui.snippetList.setCurrentRow(row)
        self._loading = False
        self._activate_row(row)

    def _activate_row(self, row: int):
        self._loading = True
        self._active_row = row if 0 <= row < len(self.snippets) else -1
        self._picture_loaded = False
        self._picture = self._saved_picture = None
        with QSignalBlocker(self.ui.snippetEditor):
            text = self.snippets[self._active_row].text if self._active_row >= 0 else ""
            self.ui.snippetEditor.setPlainText(text)
        self._loading = False
        self._load_current_picture()
        self._set_dirty(False)

    def _selection_changed(self, row: int):
        if self._loading or row == self._active_row:
            return
        previous = self._active_row
        if not self._resolve_dirty():
            with QSignalBlocker(self.ui.snippetList):
                self.ui.snippetList.setCurrentRow(previous)
            return
        self._activate_row(row)

    def _editor_changed(self):
        if self._active_row >= 0 and not self._loading:
            self._set_dirty(
                self.ui.snippetEditor.toPlainText() != self.snippets[self._active_row].text
                or self._picture != self._saved_picture
            )

    def _load_current_picture(self):
        if self._active_row < 0:
            return False
        if not self._picture_loaded:
            try:
                self._picture = self.library.image(self.snippets[self._active_row].id)
            except sqlite3.Error:
                LOGGER.exception("snippet_picture_load_failed path=%s", self.database_path)
                self._show_save_error()
                return False
            self._saved_picture = self._picture
            self._picture_loaded = True
        return True

    def _update_picture_menu(self):
        loaded = self._load_current_picture()
        self._paste_picture_action.setEnabled(loaded and not QApplication.clipboard().image().isNull())
        self._remove_picture_action.setEnabled(loaded and self._picture is not None)

    def update_defaults(self):
        if not self._resolve_dirty():
            return
        selected_id = self.snippets[self._active_row].id if self._active_row >= 0 else None
        try:
            pictures = {
                name: data for (language, name), data in self._bundled_pictures.items() if language == self._language_id
            }
            updated, _added = self.library.refresh_defaults(self._language_id, pictures)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_defaults_update_failed path=%s", self.database_path)
            self._show_save_error()
            return
        self.load_snippets()
        row = next((index for index, item in enumerate(self.snippets) if item.id == selected_id), 0)
        self.ui.snippetList.setCurrentRow(row)
        QMessageBox.information(
            self,
            self.windowTitle(),
            QCoreApplication.translate("SnippetsDialog", "Updated {0}").format(updated),
        )

    def _set_picture(self, data):
        if self._load_current_picture():
            self._picture = data
            self._editor_changed()

    def _picture_error(self, error):
        QMessageBox.warning(self, self.windowTitle(), str(error))

    def load_picture(self):
        if self._active_row < 0:
            return
        filename, _filter = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("SnippetsDialog", "Load Picture..."),
            "",
            QCoreApplication.translate("SnippetsDialog", "Pictures (*.png *.jpg *.jpeg *.bmp *.webp *.svg)"),
        )
        if not filename:
            return
        try:
            with Path(filename).open("rb") as stream:
                data = stream.read(10 * 1024 * 1024 + 1)
            picture_image(data)
        except (OSError, ValueError) as exc:
            self._picture_error(exc)
            return
        self._set_picture(data)

    def paste_picture(self):
        if self._active_row < 0:
            return
        try:
            data = png_bytes(QApplication.clipboard().image())
        except ValueError as exc:
            self._picture_error(exc)
            return
        self._set_picture(data)

    def remove_picture(self):
        self._set_picture(None)

    def _set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self._update_actions()
        self._update_picture_status()

    def _update_picture_status(self):
        if self._active_row < 0:
            text = ""
        elif not self._picture_loaded:
            text = QCoreApplication.translate("SnippetsDialog", "Picture unavailable")
        elif self._picture != self._saved_picture:
            text = (
                QCoreApplication.translate("SnippetsDialog", "Picture attached (not saved)")
                if self._picture is not None
                else QCoreApplication.translate("SnippetsDialog", "Picture removed (not saved)")
            )
        else:
            text = (
                QCoreApplication.translate("SnippetsDialog", "Picture attached")
                if self._picture is not None
                else QCoreApplication.translate("SnippetsDialog", "No picture")
            )
        self.ui.pictureStatusLabel.setText(text)
        data = self._picture if self._picture_loaded else None
        if data != self._preview_picture:
            try:
                self.ui.picturePreview.set_picture(data)
            except ValueError:
                self.ui.picturePreview.set_picture(None)
            self._preview_picture = data
        self.ui.picturePreview.setVisible(not self.ui.picturePreview.image.isNull())

    def _update_actions(self):
        selected = 0 <= self._active_row < len(self.snippets)
        row = self._active_row
        defaults = {name.casefold(): body for name, body in default_snippets(self._language_id)}
        stored = {snippet.name.casefold(): snippet.text for snippet in self.snippets}
        defaults_changed = any(stored.get(name) != body for name, body in defaults.items())
        pictures_missing = any(
            (self._language_id, snippet.name) in self._bundled_pictures and not self.library.has_image(snippet.id)
            for snippet in self.snippets
        )
        if selected and self._dirty:
            name = self.snippets[row].name.casefold()
            pictures_missing = pictures_missing or (
                (self._language_id, self.snippets[row].name) in self._bundled_pictures and self._picture is None
            )
            defaults_changed = defaults_changed or (
                name in defaults and self.ui.snippetEditor.toPlainText() != defaults[name]
            )
        self.ui.updateDefaultsButton.setEnabled(defaults_changed or pictures_missing)
        self.ui.saveButton.setEnabled(selected and self._dirty)
        self.ui.pictureButton.setEnabled(selected)
        self.ui.renameButton.setEnabled(selected)
        self.ui.deleteButton.setEnabled(selected)
        self.ui.upButton.setEnabled(selected and row > 0)
        self.ui.downButton.setEnabled(selected and row < len(self.snippets) - 1)
        self.ui.insertButton.setEnabled(selected)
        self.ui.snippetEditor.setEnabled(selected)

    def _resolve_dirty(self) -> bool:
        if not self._dirty or self._active_row < 0:
            return True
        snippet_name = self.snippets[self._active_row].name
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            f'{QCoreApplication.translate("SnippetsDialog", "Save")} "{snippet_name}"?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_row(self._active_row)
        with QSignalBlocker(self.ui.snippetEditor):
            self.ui.snippetEditor.setPlainText(self.snippets[self._active_row].text)
        self._picture = self._saved_picture
        self._set_dirty(False)
        return True

    def _unique_name(self) -> str:
        names = {item.name.casefold() for item in self.snippets}
        index = len(self.snippets) + 1
        while (name := QCoreApplication.translate("SnippetsDialog", "Snippet {0}").format(index)).casefold() in names:
            index += 1
        return name

    def _save_row(self, row: int) -> bool:
        if not 0 <= row < len(self.snippets):
            return False
        snippet = self.snippets[row]
        text = self.ui.snippetEditor.toPlainText() if row == self._active_row else snippet.text
        picture_changed = row == self._active_row and self._picture != self._saved_picture
        if text == snippet.text and not picture_changed:
            return True
        try:
            if picture_changed:
                self.library.update_content(snippet.id, text, self._picture)
            else:
                # Text-only edits must preserve the original image BLOB.
                self.library.update_body(snippet.id, text)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_save_failed id=%s path=%s", snippet.id, self.database_path)
            self._show_save_error()
            return False
        snippet.text = text
        if row == self._active_row:
            self._saved_picture = self._picture
            self._set_dirty(False)
        return True

    def add_snippet(self):
        if not self._resolve_dirty():
            return
        name = self._unique_name()
        try:
            record = self.library.add(name, language_id=self._language_id)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_create_failed path=%s", self.database_path)
            self._show_save_error()
            return
        self.snippets.append(_Snippet(record.id, record.name, record.body))
        self._refresh_list(len(self.snippets) - 1)
        self.ui.snippetEditor.setFocus()

    def save_current(self):
        return self._save_row(self._active_row)

    def rename_current(self):
        row = self._active_row
        if not 0 <= row < len(self.snippets) or not self.save_current():
            return
        snippet = self.snippets[row]
        name, accepted = QInputDialog.getText(
            self,
            QCoreApplication.translate("SnippetsDialog", "Rename snippet"),
            QCoreApplication.translate("SnippetsDialog", "New snippet name:"),
            text=snippet.name,
        )
        name = name.strip()
        if (
            not accepted
            or not name
            or any(item.name.casefold() == name.casefold() for index, item in enumerate(self.snippets) if index != row)
        ):
            return
        try:
            self.library.rename(snippet.id, name)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_rename_failed id=%s path=%s", snippet.id, self.database_path)
            self._show_save_error()
            return
        snippet.name = name
        self._refresh_list(row)

    def delete_current(self):
        row = self._active_row
        if not 0 <= row < len(self.snippets):
            return
        answer = QMessageBox.question(
            self,
            QCoreApplication.translate("SnippetsDialog", "Delete snippet"),
            QCoreApplication.translate("SnippetsDialog", "Delete selected snippet?"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        snippet = self.snippets[row]
        try:
            self.library.delete(snippet.id)
        except sqlite3.Error:
            LOGGER.exception("snippet_delete_failed id=%s path=%s", snippet.id, self.database_path)
            self._show_save_error()
            return
        self._set_dirty(False)
        self.snippets.pop(row)
        self._refresh_list(min(row, len(self.snippets) - 1))

    def move_current(self, direction: int):
        row = self._active_row
        target = row + direction
        if not 0 <= row < len(self.snippets) or not 0 <= target < len(self.snippets) or not self.save_current():
            return
        self.snippets[row], self.snippets[target] = self.snippets[target], self.snippets[row]
        if not self._write_order():
            self.snippets[row], self.snippets[target] = self.snippets[target], self.snippets[row]
            return
        self._refresh_list(target)

    def _snippet_picture(self, snippet_id):
        try:
            return self.library.image(snippet_id)
        except sqlite3.Error:
            LOGGER.exception("snippet_picture_load_failed id=%s path=%s", snippet_id, self.database_path)
            return None

    def insert_current(self):
        row = self._active_row
        if not 0 <= row < len(self.snippets) or not self.save_current():
            return
        owner = self.parent()
        editor = getattr(getattr(owner, "ui", None), "editor", None)
        if editor is None:
            LOGGER.warning("snippet_insert_without_editor path=%s", self.database_path)
            return
        snippet = self.snippets[row]
        context = self.template_context()
        insert_snippet(
            editor,
            snippet.text,
            context,
            picture=self._snippet_picture(snippet.id),
            parent=self,
        )

    def template_context(self):
        owner = self.parent()
        if owner is None:
            return TemplateContext()
        path = getattr(owner, "curFile", "") or ""
        editor = getattr(getattr(owner, "ui", None), "editor", None)
        selection = editor.selectedText() if editor is not None else ""
        return TemplateContext(Path(path) if path else None, selection or "")

    def reject(self):
        if self._resolve_dirty():
            super().reject()

    def closeEvent(self, event):
        if self._resolve_dirty():
            event.accept()
        else:
            event.ignore()
