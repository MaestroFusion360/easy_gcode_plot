"""Actionable notification for unresolved rotary axes in the active document."""

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle, QVBoxLayout

_PROFILE_ERRORS = {"ROTARY_KINEMATICS_REQUIRED", "UNCONFIGURED_ROTARY_AXIS"}


def _rotary_addresses(program):
    """Read parsed motion facts, excluding comments and macro-call arguments."""
    blocks = () if program is None else program.blocks
    native = {
        word.address[-1]
        for block in blocks
        if getattr(block.native_syntax, "kind", None) == "motion"
        for word in block.native_syntax.positioning_words
        if word.address in {"A", "B", "C", "IA", "IB", "IC"}
    }
    return sorted(
        native
        | {
            axis
            for block in blocks
            if block.motion_node is not None
            for axis in "ABC"
            if getattr(block.motion_node, axis.lower() + "_expr") is not None
        }
    )


class RotaryKinematicsNotice(QFrame):
    def __init__(self, owner):
        super().__init__(owner.ui.layoutWidget)
        self._owner = owner
        self._result = None
        self._line = None
        self.setObjectName("rotaryKinematicsNotice")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        message_layout = QHBoxLayout()
        icon = QLabel(self)
        icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(24, 24))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        message_layout.addWidget(icon)
        self.message = QLabel(self)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(False)
        self.message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message_layout.addWidget(self.message, 1)
        layout.addLayout(message_layout)
        actions = QHBoxLayout()
        self.profile_button = QPushButton(QCoreApplication.translate("MainWindow", "Choose kinematics..."), self)
        self.profile_button.setMenu(owner._rotary_kinematics_menu)
        actions.addWidget(self.profile_button)
        self.line_button = QPushButton(self)
        self.line_button.clicked.connect(self._go_to_line)
        actions.addWidget(self.line_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.hide()

    def update_result(self, result):
        if result is self._result:
            return
        self._result = result
        diagnostic = next(
            (item for item in (() if result is None else result.diagnostics) if item.code in _PROFILE_ERRORS),
            None,
        )
        if diagnostic is None:
            self._line = None
            self.hide()
            return
        axes = ", ".join(_rotary_addresses(result.program))
        if diagnostic.code == "ROTARY_KINEMATICS_REQUIRED":
            reason = QCoreApplication.translate(
                "MainWindow", "No rotary kinematics selected. Detected axes: {0}."
            ).format(axes)
        else:
            reason = QCoreApplication.translate(
                "MainWindow", "The selected kinematics does not cover the detected axes: {0}."
            ).format(axes)
        self._line = diagnostic.line
        details = ""
        if self._line is not None:
            details = " " + QCoreApplication.translate("MainWindow", "Calculation stopped at line {0}.").format(
                self._line
            )
        self.message.setText(reason + details)
        hint = QCoreApplication.translate("MainWindow", "Zero angles also require a profile.")
        self.message.setToolTip(hint + "\n" + (diagnostic.raw or diagnostic.message))
        self.line_button.setText(QCoreApplication.translate("MainWindow", "Go to line {0}").format(self._line))
        self.line_button.setVisible(self._line is not None)
        self.show()

    def _go_to_line(self):
        if self._line is None:
            return
        editor = self._owner.ui.editor
        editor.setCursorPosition(self._line - 1, 0)
        editor.ensureLineVisible(self._line - 1)
        editor.setFocus()
