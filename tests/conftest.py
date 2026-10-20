from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))

from app import paths  # noqa: E402  # pylint: disable=wrong-import-position
from app import settings as app_settings  # noqa: E402  # pylint: disable=wrong-import-position

_CURRENT_TEST_FOLDER = pytest.StashKey[str]()


def pytest_runtest_protocol(item, nextitem):
    """Show folder boundaries without restarting pytest or its session fixtures."""
    folder = item.path.parent.relative_to(ROOT).as_posix()
    if item.config.stash.get(_CURRENT_TEST_FOLDER, None) != folder:
        reporter = item.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line("")
            reporter.write_sep("=", folder)
        item.config.stash[_CURRENT_TEST_FOLDER] = folder


@pytest.fixture(autouse=True)
def isolate_application_settings(tmp_path, monkeypatch):
    """Keep GUI tests away from the user's real settings and log files."""
    config_file = tmp_path / "config.ini"
    log_file = tmp_path / "main.log"
    config_file.touch()
    monkeypatch.setattr(paths, "config_dir", lambda: str(tmp_path))
    monkeypatch.setattr(app_settings, "config_path", lambda: str(config_file))
    monkeypatch.setattr(app_settings, "log_path", lambda: str(log_file))

    settings = QSettings(str(config_file), QSettings.Format.IniFormat)
    settings.clear()
    settings.sync()
    del settings
    yield
    # A test may destroy QApplication, which also deletes existing Qt objects.
    settings = QSettings(str(config_file), QSettings.Format.IniFormat)
    settings.clear()
    settings.sync()


@pytest.fixture
def fixture_text():
    def _read(relative_path: str) -> str:
        return (FIXTURES / relative_path).read_text(encoding="utf-8-sig")

    return _read
