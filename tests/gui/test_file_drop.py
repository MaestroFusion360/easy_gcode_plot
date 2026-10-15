"""File-drop filters against real Qt MIME data and drag/drop events."""

import pytest
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QWidget

from app.ui.support.file_drop import FileDropTarget, local_drop_paths


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_local_paths_preserve_order_and_exclude_urls_directories_and_missing_files(tmp_path):
    first, second = tmp_path / "first.h", tmp_path / "second.nc"
    first.touch()
    second.touch()
    mime = QMimeData()
    mime.setUrls(
        [
            QUrl("https://example.invalid/program.h"),
            *(QUrl.fromLocalFile(str(path)) for path in (first, tmp_path, second, first, tmp_path / "missing.h")),
        ]
    )
    assert local_drop_paths(mime) == (first.as_posix(), second.as_posix())


@pytest.mark.parametrize(
    "count,max_files,opened,accepted", [(2, None, True, True), (2, 1, True, False), (1, 1, False, False)]
)
def test_drop_acceptance_matches_file_limit_and_open_result(qt_app, tmp_path, count, max_files, opened, accepted):
    widget = QWidget()
    calls = []
    target = FileDropTarget((widget,), lambda paths: calls.append(paths) or opened, parent=widget, max_files=max_files)
    mime = QMimeData()
    files = [tmp_path / f"part{index}.h" for index in range(count)]
    for path in files:
        path.touch()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in files])
    arguments = (Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    drag = QDragEnterEvent(QPoint(1, 1), *arguments)
    assert target.eventFilter(widget, drag)
    assert drag.isAccepted() == (max_files is None or count <= max_files)
    assert calls == []
    drop = QDropEvent(QPointF(1, 1), *arguments)
    assert target.eventFilter(widget, drop)
    assert drop.isAccepted() == accepted
    assert calls == ([] if max_files is not None and count > max_files else [tuple(path.as_posix() for path in files)])
    widget.deleteLater()
    qt_app.processEvents()
