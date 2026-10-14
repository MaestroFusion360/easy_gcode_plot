"""Stage toolbar button choices until the customization dialog is accepted."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QTreeWidgetItem

from app.ui.generated.dialogs.toolbar_settings import Ui_ToolbarSettingsDlg


class ToolbarSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.ui = Ui_ToolbarSettingsDlg()
        self.ui.setupUi(self)
        self._configure_search_clear()
        self.setWindowIcon(parent.windowIcon())
        self.items = {}
        self._populate()
        self.ui.upButton.clicked.connect(lambda: self.move_command(-1))
        self.ui.downButton.clicked.connect(lambda: self.move_command(1))
        self.ui.commandTree.currentItemChanged.connect(self.update_move_buttons)
        self.update_move_buttons()
        self.ui.searchEdit.textChanged.connect(self._filter)
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)

    def _configure_search_clear(self):
        """Use the application's close glyph with the current theme's text color."""
        pixmap = QPixmap(":/resource/icons/close.png")
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), self.palette().color(QPalette.ColorRole.Text))
        painter.end()
        self.clearSearchAction = QAction(QIcon(pixmap), self.tr("Clear search"), self)
        self.clearSearchAction.setObjectName("actionClearToolbarSearch")
        self.clearSearchAction.setVisible(False)
        self.ui.searchEdit.addAction(self.clearSearchAction, QLineEdit.ActionPosition.TrailingPosition)
        self.clearSearchAction.triggered.connect(self.ui.searchEdit.clear)
        self.ui.searchEdit.textChanged.connect(lambda text: self.clearSearchAction.setVisible(bool(text)))

    def _populate(self):
        groups = {
            toolbar: QTreeWidgetItem(self.ui.commandTree, [toolbar.windowTitle()]) for toolbar in self.settings.toolbars
        }
        for key in (key for keys in self.settings.order.values() for key in keys):
            action, toolbar, category = self.settings.commands[key]
            item = QTreeWidgetItem(groups[toolbar], [action.text().replace("&", "")])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            item.setIcon(0, action.icon())
            item.setToolTip(0, category + ": " + action.toolTip())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if self.settings.selected[key] else Qt.CheckState.Unchecked)
            self.items[key] = item
        self.ui.commandTree.expandAll()
        self._filter("")

    def _filter(self, query):
        query = query.casefold().strip()
        for item in self.items.values():
            item.setHidden(query not in item.text(0).casefold())
        for index in range(self.ui.commandTree.topLevelItemCount()):
            group = self.ui.commandTree.topLevelItem(index)
            group.setHidden(all(group.child(row).isHidden() for row in range(group.childCount())))
        self.update_move_buttons()

    def update_move_buttons(self, *_args):
        item = self.ui.commandTree.currentItem()
        parent = item.parent() if item is not None else None
        movable = parent is not None and not self.ui.searchEdit.text().strip()
        row = parent.indexOfChild(item) if movable else -1
        self.ui.upButton.setEnabled(movable and row > 0)
        self.ui.downButton.setEnabled(movable and row < parent.childCount() - 1)

    def move_command(self, offset):
        """Move a selected command within its toolbar without applying changes yet."""
        button = self.ui.upButton if offset < 0 else self.ui.downButton
        if not button.isEnabled():
            return
        item = self.ui.commandTree.currentItem()
        parent = item.parent()
        row = parent.indexOfChild(item)
        parent.takeChild(row)
        parent.insertChild(row + offset, item)
        self.ui.commandTree.setCurrentItem(item)
        self.update_move_buttons()

    def command_order(self):
        result = {}
        for index, toolbar in enumerate(self.settings.toolbars):
            group = self.ui.commandTree.topLevelItem(index)
            result[toolbar.objectName()] = [
                group.child(row).data(0, Qt.ItemDataRole.UserRole) for row in range(group.childCount())
            ]
        return result

    def restore_defaults(self):
        for keys in self.settings.default_order.values():
            for row, key in enumerate(keys):
                item = self.items[key]
                parent = item.parent()
                parent.takeChild(parent.indexOfChild(item))
                parent.insertChild(row, item)
        for key, item in self.items.items():
            item.setCheckState(0, Qt.CheckState.Checked if self.settings.defaults[key] else Qt.CheckState.Unchecked)
        self.update_move_buttons()

    def accept(self):
        self.settings.apply(
            {key: item.checkState(0) == Qt.CheckState.Checked for key, item in self.items.items()},
            order=self.command_order(),
            persist=True,
        )
        super().accept()
