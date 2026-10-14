"""Helpers for the rotary profile sidebar in GUI scenarios."""

from PyQt6.QtCore import Qt


def profile_row(widget, profile_id):
    return next((i for i in range(widget.count()) if widget.item(i).data(Qt.ItemDataRole.UserRole) == profile_id), -1)


def profile_id(widget):
    item = widget.currentItem()
    return item.data(Qt.ItemDataRole.UserRole) if item is not None else None
