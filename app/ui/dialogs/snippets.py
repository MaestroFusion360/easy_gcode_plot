"""Persistent G-code snippets dialog."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QSignalBlocker
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

from app.gcode.snippets import SnippetLibrary
from app.settings import config_path
from app.ui.generated.dialogs.snippets import Ui_SnippetsDialog

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Snippet:
    id: int
    name: str
    text: str


class SnippetsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_SnippetsDialog()
        self.ui.setupUi(self)
        config_file = Path(config_path())
        self.database_path = config_file.with_name("snippets.db")
        self.legacy_directory = config_file.with_name("snippets")
        self.library = SnippetLibrary(str(self.database_path))
        self.snippets: list[_Snippet] = []
        self._loading = False
        self._active_row = -1
        self._dirty = False
        self._connect()
        self.load_snippets()

    def _connect(self):
        self.ui.snippetList.currentRowChanged.connect(self._selection_changed)
        self.ui.snippetEditor.textChanged.connect(self._editor_changed)
        self.ui.addButton.clicked.connect(self.add_snippet)
        self.ui.saveButton.clicked.connect(self.save_current)
        self.ui.renameButton.clicked.connect(self.rename_current)
        self.ui.deleteButton.clicked.connect(self.delete_current)
        self.ui.upButton.clicked.connect(lambda: self.move_current(-1))
        self.ui.downButton.clicked.connect(lambda: self.move_current(1))
        self.ui.insertButton.clicked.connect(self.insert_current)
        self.ui.cancelButton.clicked.connect(self.reject)

    def load_snippets(self):
        self.library.import_legacy_directory(self.legacy_directory)
        self.snippets = [_Snippet(record.id, record.name, record.body) for record in self.library.list_snippets()]
        self._refresh_list(0 if self.snippets else -1)

    def _write_order(self) -> bool:
        try:
            self.library.reorder([item.id for item in self.snippets])
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_order_save_failed path=%s", self.database_path)
            QMessageBox.warning(
                self, self.windowTitle(), QCoreApplication.translate("SnippetsDialog", "Could not save snippet.")
            )
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
        self._active_row = row if 0 <= row < len(self.snippets) else -1
        with QSignalBlocker(self.ui.snippetEditor):
            text = self.snippets[self._active_row].text if self._active_row >= 0 else ""
            self.ui.snippetEditor.setPlainText(text)
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
            self._set_dirty(self.ui.snippetEditor.toPlainText() != self.snippets[self._active_row].text)

    def _set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self.ui.saveButton.setEnabled(self._active_row >= 0 and self._dirty)

    def _resolve_dirty(self) -> bool:
        if not self._dirty or self._active_row < 0:
            return True
        snippet_name = self.snippets[self._active_row].name
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            f'{self.ui.saveButton.text()} "{snippet_name}"?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_row(self._active_row)
        with QSignalBlocker(self.ui.snippetEditor):
            self.ui.snippetEditor.setPlainText(self.snippets[self._active_row].text)
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
        try:
            self.library.update_body(snippet.id, text)
        except sqlite3.Error:
            LOGGER.exception("snippet_save_failed id=%s path=%s", snippet.id, self.database_path)
            QMessageBox.warning(
                self, self.windowTitle(), QCoreApplication.translate("SnippetsDialog", "Could not save snippet.")
            )
            return False
        snippet.text = text
        if row == self._active_row:
            self._set_dirty(False)
        return True

    def add_snippet(self):
        if not self._resolve_dirty():
            return
        name = self._unique_name()
        try:
            record = self.library.add(name)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_create_failed path=%s", self.database_path)
            QMessageBox.warning(
                self, self.windowTitle(), QCoreApplication.translate("SnippetsDialog", "Could not save snippet.")
            )
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

    def insert_current(self):
        row = self._active_row
        if not 0 <= row < len(self.snippets) or not self.save_current():
            return
        self.parent().ui.editor.replaceSelectedText(self.snippets[row].text)
        self.accept()

    def reject(self):
        if self._resolve_dirty():
            super().reject()

    def closeEvent(self, event):
        if self._resolve_dirty():
            event.accept()
        else:
            event.ignore()
