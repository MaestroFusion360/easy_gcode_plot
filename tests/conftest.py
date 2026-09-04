from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"

sys.path.insert(0, str(ROOT))


@pytest.fixture
def fixture_text():
    def _read(relative_path: str) -> str:
        return (FIXTURES / relative_path).read_text(encoding="utf-8-sig")

    return _read
