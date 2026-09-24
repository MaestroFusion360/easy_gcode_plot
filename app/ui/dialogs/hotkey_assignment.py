"""Choose a single key and modifiers for one menu command."""

from PyQt6.QtCore import QCoreApplication, QKeyCombination, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QComboBox, QDialog, QMessageBox

from app.ui.generated.dialogs.hotkey_assignment import Ui_HotkeyAssignmentDlg
from app.ui.support.hotkeys import portable_shortcut

_NAMED_KEYS = (
    ("Space", Qt.Key.Key_Space),
    ("Tab", Qt.Key.Key_Tab),
    ("Backspace", Qt.Key.Key_Backspace),
    ("Enter", Qt.Key.Key_Return),
    ("Escape", Qt.Key.Key_Escape),
    ("Insert", Qt.Key.Key_Insert),
    ("Delete", Qt.Key.Key_Delete),
    ("Home", Qt.Key.Key_Home),
    ("End", Qt.Key.Key_End),
    ("Page Up", Qt.Key.Key_PageUp),
    ("Page Down", Qt.Key.Key_PageDown),
    ("Up", Qt.Key.Key_Up),
    ("Down", Qt.Key.Key_Down),
    ("Left", Qt.Key.Key_Left),
    ("Right", Qt.Key.Key_Right),
    ("-", Qt.Key.Key_Minus),
    ("=", Qt.Key.Key_Equal),
    ("+", Qt.Key.Key_Plus),
    (",", Qt.Key.Key_Comma),
    (".", Qt.Key.Key_Period),
    ("/", Qt.Key.Key_Slash),
    ("\\", Qt.Key.Key_Backslash),
    (";", Qt.Key.Key_Semicolon),
    ("'", Qt.Key.Key_Apostrophe),
    ("[", Qt.Key.Key_BracketLeft),
    ("]", Qt.Key.Key_BracketRight),
    ("`", Qt.Key.Key_QuoteLeft),
)


class HotkeyAssignmentDialog(QDialog):
    def __init__(self, command, current, used, parent=None):
        super().__init__(parent)
        self.ui = Ui_HotkeyAssignmentDlg()
        self.ui.setupUi(self)
        self.ui.commandEdit.setText(command)
        self._used = used
        self._populate_keys()
        self._load_sequence(current)

    def _populate_keys(self):
        combo = self.ui.keyCombo
        combo.addItem(QCoreApplication.translate("HotkeyAssignmentDlg", "None"), 0)
        for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            combo.addItem(character, int(getattr(Qt.Key, f"Key_{character}")))
        for number in range(1, 25):
            combo.addItem(f"F{number}", int(getattr(Qt.Key, f"Key_F{number}")))
        for label, key in _NAMED_KEYS:
            combo.addItem(label, int(key))
        listed = {combo.itemData(index) for index in range(combo.count())}
        modifier_keys = {
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        }
        for key in Qt.Key:
            if int(key) in listed or key in modifier_keys:
                continue
            if QKeySequence(QKeyCombination(Qt.KeyboardModifier.NoModifier, key)).isEmpty():
                continue
            combo.addItem(key.name.removeprefix("Key_").replace("_", " "), int(key))
        combo.setEditable(True)
        combo.setInsertPolicy(combo.InsertPolicy.NoInsert)
        combo.setMinimumContentsLength(10)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def _load_sequence(self, text):
        sequence = QKeySequence(text, QKeySequence.SequenceFormat.PortableText)
        if sequence.isEmpty():
            return
        combination = sequence[0]
        modifiers = combination.keyboardModifiers()
        for checkbox, modifier in (
            (self.ui.ctrlCheck, Qt.KeyboardModifier.ControlModifier),
            (self.ui.altCheck, Qt.KeyboardModifier.AltModifier),
            (self.ui.shiftCheck, Qt.KeyboardModifier.ShiftModifier),
            (self.ui.metaCheck, Qt.KeyboardModifier.MetaModifier),
        ):
            checkbox.setChecked(bool(modifiers & modifier))
        self.ui.keyCombo.setCurrentIndex(self.ui.keyCombo.findData(combination.key()))

    def shortcut(self):
        key = self.ui.keyCombo.currentData()
        if not key:
            return ""
        modifiers = Qt.KeyboardModifier.NoModifier
        for checkbox, modifier in (
            (self.ui.ctrlCheck, Qt.KeyboardModifier.ControlModifier),
            (self.ui.altCheck, Qt.KeyboardModifier.AltModifier),
            (self.ui.shiftCheck, Qt.KeyboardModifier.ShiftModifier),
            (self.ui.metaCheck, Qt.KeyboardModifier.MetaModifier),
        ):
            if checkbox.isChecked():
                modifiers |= modifier
        return portable_shortcut(QKeySequence(QKeyCombination(modifiers, Qt.Key(key))))

    def accept(self):
        combo = self.ui.keyCombo
        if combo.currentIndex() < 0 or combo.currentText() != combo.itemText(combo.currentIndex()):
            QMessageBox.warning(
                self,
                self.windowTitle(),
                QCoreApplication.translate("HotkeyAssignmentDlg", "Choose a key from the list."),
            )
            return
        shortcut = self.shortcut()
        if shortcut in self._used:
            message = QCoreApplication.translate(
                "HotkeyAssignmentDlg", "{shortcut} is already assigned to {command}."
            ).format(shortcut=shortcut, command=self._used[shortcut])
            QMessageBox.warning(self, self.windowTitle(), message)
            return
        super().accept()
