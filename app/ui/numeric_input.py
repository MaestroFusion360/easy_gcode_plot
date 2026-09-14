"""Application-wide input handling for locale-aware decimal spin boxes."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QDoubleSpinBox


class DecimalSeparatorFilter(QObject):
    """Let QDoubleSpinBox accept both decimal separator keys in every locale."""

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.KeyPress or event.text() not in (".", ","):
            return False

        parent = watched.parentWidget() if hasattr(watched, "parentWidget") else None
        spin = watched if isinstance(watched, QDoubleSpinBox) else parent
        if not isinstance(spin, QDoubleSpinBox):
            return False

        decimal_point = spin.locale().decimalPoint()
        if event.text() == decimal_point:
            return False

        spin.lineEdit().insert(decimal_point)
        return True


def install_decimal_separator_filter(application) -> DecimalSeparatorFilter:
    """Install and return the global decimal-key compatibility filter."""
    event_filter = DecimalSeparatorFilter(application)
    application.installEventFilter(event_filter)
    return event_filter
