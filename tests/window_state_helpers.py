"""Initialize the Python state contract for focused mixin boundary tests."""

# pylint: disable=protected-access

from types import SimpleNamespace

from app.main_window import MainWindow


def window_namespace(**values):
    owner = SimpleNamespace()
    MainWindow._initialize_document_state(owner)
    MainWindow._initialize_execution_state(owner)
    MainWindow._initialize_stock_runtime(owner)
    owner.__dict__.update(values)
    return owner
