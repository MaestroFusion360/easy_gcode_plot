"""Options table for shortcuts on named main-menu commands."""

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QDialog, QHeaderView, QMessageBox, QTableWidgetItem

from app.ui.dialogs.hotkey_assignment import HotkeyAssignmentDialog
from app.ui.support.hotkeys import menu_commands


class HotkeyEditor:
    def __init__(self, dialog):
        self.dialog = dialog
        self.table = dialog.ui.hotkeysTable
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.commands = []
        self.values = {}
        self.defaults = {}
        dialog.ui.editHotkeyButton.clicked.connect(self.edit_selected)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected())
        self.table.itemSelectionChanged.connect(self._update_button)
        self._update_button()

    def load(self, window):
        self.commands = list(menu_commands(window))
        self.values = dict(window.hotkeys)
        self.defaults = dict(window.defaultHotkeys)
        self.table.setRowCount(len(self.commands))
        for row, (key, action, category) in enumerate(self.commands):
            name = action.text().replace("&", "")
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(self.values.get(key, "")))
            self.table.setItem(row, 2, QTableWidgetItem(category))
        self.table.clearSelection()
        self._update_button()

    def reset_defaults(self):
        self.values = dict(self.defaults)
        for row, (key, _action, _category) in enumerate(self.commands):
            self.table.item(row, 1).setText(self.values[key])

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.commands):
            return
        key, action, _category = self.commands[row]
        used = {
            shortcut: other.text().replace("&", "")
            for other_key, other, _category in self.commands
            if other_key != key and (shortcut := self.values.get(other_key))
        }
        editor = HotkeyAssignmentDialog(action.text().replace("&", ""), self.values[key], used, self.dialog)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.assign(key, editor.shortcut())

    def assign(self, key, shortcut):
        """Change one row after validating that no other command uses its key."""
        for other_key, action, _category in self.commands:
            if shortcut and other_key != key and self.values.get(other_key) == shortcut:
                message = QCoreApplication.translate(
                    "HotkeyAssignmentDlg", "{shortcut} is already assigned to {command}."
                ).format(shortcut=shortcut, command=action.text().replace("&", ""))
                QMessageBox.warning(self.dialog, self.dialog.windowTitle(), message)
                return False
        self.values[key] = shortcut
        row = next(index for index, command in enumerate(self.commands) if command[0] == key)
        self.table.item(row, 1).setText(shortcut)
        return True

    def _update_button(self):
        self.dialog.ui.editHotkeyButton.setEnabled(bool(self.table.selectedItems()))
