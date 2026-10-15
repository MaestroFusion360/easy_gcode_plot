"""Open local files dropped on widgets without inserting their URLs as text."""

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt


def local_drop_paths(mime):
    """Keep existing local files in the order supplied by the drag source."""
    if not mime.hasUrls():
        return ()
    return tuple(
        dict.fromkeys(
            url.toLocalFile() for url in mime.urls() if url.isLocalFile() and Path(url.toLocalFile()).is_file()
        )
    )


class FileDropTarget(QObject):
    """Intercept file drops while preserving normal editor text drag behavior."""

    def __init__(self, widgets, open_files, *, parent, max_files=None):
        super().__init__(parent)
        self._open_files = open_files
        self._max_files = max_files
        for widget in widgets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return super().eventFilter(watched, event)
        mime = event.mimeData()
        if not mime.hasUrls():
            return super().eventFilter(watched, event)
        paths = local_drop_paths(mime)
        if not paths or (self._max_files is not None and len(paths) > self._max_files):
            event.ignore()
            return True
        if event.type() == QEvent.Type.Drop and not self._open_files(paths):
            event.ignore()
            return True
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        return True
