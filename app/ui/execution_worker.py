"""Run a snapshot of CNC input off the GUI thread with modal cancellation."""

from time import monotonic

from PyQt6.QtCore import QCoreApplication, QEventLoop, Qt, QThread
from PyQt6.QtWidgets import QDialog, QWidget

from app.ui.generated.execution_dialog import Ui_ExecutionDialog

EXECUTION_DIALOG_DELAY_MS = 2000


class _ExecutionThread(QThread):
    def __init__(self, function, source, options):
        super().__init__()
        self.function = function
        self.source = source
        self.options = options
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.function(self.source, **self.options)
        except Exception as exc:
            self.error = exc


class _ExecutionDialog(QDialog):
    def __init__(self, parent, cancel):
        super().__init__(parent)
        self.ui = Ui_ExecutionDialog()
        self.ui.setupUi(self)
        self.cancel = cancel
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.label = self.ui.statusLabel
        self.button = self.ui.cancelButton
        self.button.clicked.connect(self.reject)

    def reject(self):
        # Keep the owner blocked until the worker has acknowledged cancellation.
        self.cancel()
        self.label.setText("Cancelling CNC execution…")
        self.button.setEnabled(False)


def run_execution(owner, function, source, options, cancel):
    """Return the worker result; show the existing dialog only for slow runs."""
    worker = _ExecutionThread(function, source, options)
    worker.start()

    if isinstance(owner, QWidget):
        dialog = None
        reveal_at = monotonic() + (EXECUTION_DIALOG_DELAY_MS / 1000.0)

        while worker.isRunning():
            # Keep the GUI responsive without entering a nested QEventLoop.exec().
            # The nested loop is unstable with Qt's offscreen platform on Linux.
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)

            if dialog is None and monotonic() >= reveal_at:
                dialog = _ExecutionDialog(owner, cancel)
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()

            worker.wait(10)

        worker.wait()
        if dialog is not None:
            dialog.accept()
            dialog.deleteLater()
    else:
        # Non-widget consumers (including contract tests) need no event pumping.
        worker.wait()

    if worker.error is not None:
        raise worker.error
    return worker.result
