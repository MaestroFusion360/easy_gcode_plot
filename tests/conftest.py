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

from app import settings as app_settings  # noqa: E402  # pylint: disable=wrong-import-position


@pytest.fixture(autouse=True)
def isolate_application_settings(tmp_path, monkeypatch):
    """Keep GUI tests away from the user's real settings and log files."""
    config_file = tmp_path / "config.ini"
    log_file = tmp_path / "main.log"
    config_file.touch()
    monkeypatch.setattr(app_settings, "config_path", lambda: str(config_file))
    monkeypatch.setattr(app_settings, "log_path", lambda: str(log_file))

    settings = QSettings(str(config_file), QSettings.Format.IniFormat)
    settings.clear()
    settings.sync()
    yield
    settings.clear()
    settings.sync()


@pytest.fixture
def fixture_text():
    def _read(relative_path: str) -> str:
        return (FIXTURES / relative_path).read_text(encoding="utf-8-sig")

    return _read
