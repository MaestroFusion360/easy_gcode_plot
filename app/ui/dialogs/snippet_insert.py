"""Compact modal form for snippet parameters and a read-only illustration."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QCoreApplication, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gcode.snippet_templates import TemplateContext, TemplateError, parameters, render
from app.ui.support.snippet_preview import PictureLabel, error_text, parameter_label

LOGGER = logging.getLogger(__name__)


class SnippetInsertDialog(QDialog):
    """Collect the declared values; never display generated G-code or edit the DB."""

    def __init__(self, source, context=None, picture=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("SnippetsDialog", "Insert"))
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.source = source
        self.context = context or TemplateContext()
        self.rendered = None
        self.fields = {}

        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        layout.addLayout(content)

        requested = parameters(source)
        field_scroll = QScrollArea(self, visible=bool(requested))
        field_scroll.setWidgetResizable(True)
        field_scroll.setFrameShape(QFrame.Shape.NoFrame)
        field_scroll.setMinimumWidth(310)
        field_scroll.setMaximumHeight(330)
        field_widget = QWidget(field_scroll)
        self.form = QFormLayout(field_widget)
        field_scroll.setWidget(field_widget)
        content.addWidget(field_scroll, 1)

        for parameter in requested:
            field = self._parameter_field(parameter)
            self.fields[parameter.name] = field
            self.form.addRow(parameter_label(parameter), field)
        # A small parameter list must not leave a large empty scrolling panel.
        field_scroll.setFixedHeight(min(330, max(46, len(requested) * 39 + 12)))

        self._add_picture(picture, content)

        self.error = QLabel(self)
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setDefault(True)
        self._refresh()
        if self.fields:
            first = next(iter(self.fields.values()))
            first.setFocus()
            if isinstance(first, QLineEdit):
                first.selectAll()
        self.adjustSize()

    def _add_picture(self, picture, content):
        self.picture_label = None
        if not picture:
            return
        label = PictureLabel(self)
        label.setAcceptDrops(False)
        label.setToolTip(QCoreApplication.translate("SnippetsDialog", "Click to enlarge"))
        label.setMinimumWidth(220)
        label.setMinimumHeight(160)
        label.setMaximumHeight(280)
        try:
            label.set_picture(picture)
        except ValueError:
            LOGGER.warning("snippet_insert_picture_invalid", exc_info=True)
            label.deleteLater()
        else:
            self.picture_label = label
            content.addWidget(label, 1)

    def _parameter_field(self, parameter):
        if parameter.choices:
            field = QComboBox(self)
            field.addItems(parameter.choices)
            if parameter.optional and "" not in parameter.choices:
                field.insertItem(0, "")
            field.setCurrentIndex(field.findText(parameter.default))
            field.currentTextChanged.connect(self._refresh)
        else:
            field = QLineEdit(parameter.default, self)
            if parameter.kind in {"number", "int"}:
                pattern = (
                    r"[+-]?[0-9]+"
                    if parameter.kind == "int"
                    else r"[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)(?:[eE][+-]?[0-9]+)?"
                )
                if parameter.optional:
                    pattern = f"(?:{pattern})?"
                field.setValidator(QRegularExpressionValidator(QRegularExpression(pattern), field))
            field.textChanged.connect(self._refresh)
        field.setObjectName(f"parameter_{parameter.name}")
        return field

    def _refresh(self):
        values = {
            name: field.currentText() if isinstance(field, QComboBox) else field.text()
            for name, field in self.fields.items()
        }
        try:
            self.rendered = render(self.source, values, self.context)
        except TemplateError as exc:
            self.rendered = None
            self.error.setText(error_text(exc))
            self.error.show()
            self.ok_button.setEnabled(False)
        else:
            self.error.hide()
            self.ok_button.setEnabled(True)

    def accept(self):
        if self.rendered is not None:
            super().accept()
