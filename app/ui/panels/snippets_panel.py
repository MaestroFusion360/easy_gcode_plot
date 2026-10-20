"""Docked snippet browser using the shared library and editor insertion flow."""

from __future__ import annotations

import logging
import re
import sqlite3

from PyQt6.QtCore import QCoreApplication, QEvent, QSignalBlocker, QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDockWidget, QListWidgetItem, QMessageBox, QSizePolicy, QWidget

from app.gcode.snippets.snippet_defaults import LANGUAGES
from app.ui.generated.panels.snippets_panel import Ui_SnippetsPanelForm
from app.ui.support.snippet_insertion import insert_snippet

LOGGER = logging.getLogger(__name__)
_PROGRAM_NAMES = {"Program Start", "Toolchange", "Program End", "Comment", "Toolchange (Drill)", "Document header"}
_GROUPS = ("all", "program", "motion", "cycles", "formulas")
_CYCLE = re.compile(r"\b(?:G7[1346]|G8[12345679]|CYCLE\d+|CYCL DEF\s+\d+|HOLES[12]|POCKET[34])\b", re.I)
_TURNING_CYCLE = re.compile(r"\bG7[025789]\b", re.I)
_TYPE_A_CYCLE = re.compile(r"\bG9[024]\b", re.I)


def _group(record):
    if record.name in _PROGRAM_NAMES:
        return "program"
    if "{{=" in record.body:
        return "formulas"
    if _CYCLE.search(record.body) or (record.language_id == "fanuc_turn" and _TYPE_A_CYCLE.search(record.body)):
        return "cycles"
    if record.language_id in {"fanuc_turn", "fanuc_b_turn"} and _TURNING_CYCLE.search(record.body):
        return "cycles"
    return "motion"


class SnippetsPanel(QDockWidget):
    def __init__(self, window):
        super().__init__(QCoreApplication.translate("SnippetsPanelForm", "Snippets"), window)
        self.window = window
        self.setObjectName("snippetsDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        content = QWidget(self)
        self.ui = Ui_SnippetsPanelForm()
        self.ui.setupUi(content)
        self.setWidget(content)
        self._cached_records = []
        self._language = None
        self._style_button(self.ui.insertButton, "paste.png")
        self._style_button(self.ui.editButton, "edit.png")
        for index, group in enumerate(_GROUPS):
            self.ui.groupCombo.setItemData(index, group)
        self.ui.groupCombo.currentIndexChanged.connect(self._filter)
        self.ui.searchEdit.textChanged.connect(self._filter)
        self.ui.snippetList.currentRowChanged.connect(self._selection_changed)
        self.ui.snippetList.itemActivated.connect(self.insert_current)
        self.ui.insertButton.clicked.connect(self.insert_current)
        if window.snippetsDlg is not None:
            self.ui.editButton.clicked.connect(window.snippetsDlg.show)
            window.snippetsDlg.installEventFilter(self)
        else:
            self.ui.editButton.setEnabled(False)
        self.refresh()

    @staticmethod
    def _style_button(button, icon):
        button.setIcon(QIcon(f":/resource/icons/{icon}"))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(18, 18))
        button.setAutoRaise(False)
        button.setMinimumHeight(28)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        button.setToolTip(button.text())
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def eventFilter(self, watched, event):
        if watched is self.window.snippetsDlg and event.type() == QEvent.Type.Hide:
            self.refresh()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def _records(self):
        if self.window.snippetsDlg is None:
            return []
        language = self.window.snippetsDlg.document_language() or "fanuc_mill"
        try:
            return self.window.snippetsDlg.library.list_snippets(language)
        except (sqlite3.Error, ValueError):
            LOGGER.exception("snippet_panel_load_failed language=%s", language)
            QMessageBox.warning(
                self.window,
                self.windowTitle(),
                QCoreApplication.translate("MainWindow", "Could not load snippets."),
            )
            return []

    def refresh(self, *_args):
        if self.window.snippetsDlg is None:
            self._cached_records = []
            self.ui.snippetList.clear()
            self.ui.insertButton.setEnabled(False)
            return
        language = self.window.snippetsDlg.document_language() or "fanuc_mill"
        self._cached_records = self._records()
        label = dict(LANGUAGES).get(language, language)
        self.ui.controllerLabel.setText(QCoreApplication.translate("SnippetsDialog", label))
        if language != self._language:
            with QSignalBlocker(self.ui.searchEdit), QSignalBlocker(self.ui.groupCombo):
                self.ui.searchEdit.clear()
                self.ui.groupCombo.setCurrentIndex(0)
            self._language = language
        self._filter()

    def _filter(self, *_args):
        selected = self.ui.snippetList.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        scrollbar = self.ui.snippetList.verticalScrollBar()
        scroll = scrollbar.value()
        query = self.ui.searchEdit.text().strip().casefold()
        group = self.ui.groupCombo.currentData()
        with QSignalBlocker(self.ui.snippetList):
            self.ui.snippetList.clear()
            for record in self._cached_records:
                if query not in record.name.casefold() or group not in ("all", _group(record)):
                    continue
                item = QListWidgetItem(record.name, self.ui.snippetList)
                item.setData(Qt.ItemDataRole.UserRole, record.id)
                item.setToolTip(record.name)
                if record.id == selected_id:
                    self.ui.snippetList.setCurrentItem(item)
            if self.ui.snippetList.currentRow() < 0 and self.ui.snippetList.count():
                self.ui.snippetList.setCurrentRow(0)
        scrollbar.setValue(scroll)
        self._selection_changed()

    def _selection_changed(self, *_args):
        self.ui.insertButton.setEnabled(self.ui.snippetList.currentItem() is not None)

    def insert_current(self, *_args):
        item = self.ui.snippetList.currentItem()
        if item is not None:
            self.insert_id(item.data(Qt.ItemDataRole.UserRole))

    def insert_id(self, snippet_id):
        record = next((item for item in self._records() if item.id == snippet_id), None)
        if record is not None:
            self._insert(record)

    def _insert(self, record):
        if self.window.snippetsDlg is None:
            return
        library = self.window.snippetsDlg.library
        try:
            picture = library.image(record.id)
        except sqlite3.Error:
            LOGGER.exception("snippet_panel_picture_load_failed id=%s", record.id)
            picture = None
        insert_snippet(
            self.window.ui.editor,
            record.body,
            self.window.snippetsDlg.template_context(),
            picture=picture,
            parent=self.window,
        )
