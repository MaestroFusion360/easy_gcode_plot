"""Qt-free SQLite storage for reusable G-code snippets."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
LEGACY_IMPORT_META_KEY = "legacy_text_snippets_imported_v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    body TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_snippets_sort_order ON snippets(sort_order);
"""


@dataclass(frozen=True, slots=True)
class SnippetRecord:
    id: int
    name: str
    body: str
    sort_order: int
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _name(value: str) -> str:
    name = str(value).strip()
    if not name:
        raise ValueError("Snippet name must not be empty")
    return name


class SnippetLibrary:
    """Thread-safe ordered snippet catalogue backed by SQLite."""

    def __init__(self, path: str):
        self.path = str(Path(path))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._ensure_schema_version()

    def _ensure_schema_version(self) -> None:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
                return
            stored = int(row["value"])
            if stored != SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported snippet-library schema version: {stored}")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def list_snippets(self) -> list[SnippetRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, body, sort_order, created_at, updated_at FROM snippets ORDER BY sort_order, id"
            ).fetchall()
            return [self._record(row) for row in rows]

    def add(self, name: str, body: str = "") -> SnippetRecord:
        name = _name(name)
        now = _now()
        with self._lock, self._conn:
            next_order = int(self._conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM snippets").fetchone()[0])
            cursor = self._conn.execute(
                "INSERT INTO snippets(name, body, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (name, str(body), next_order, now, now),
            )
            row = self._conn.execute(
                "SELECT id, name, body, sort_order, created_at, updated_at FROM snippets WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._record(row)

    def update_body(self, snippet_id: int, body: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE snippets SET body = ?, updated_at = ? WHERE id = ?",
                (str(body), _now(), int(snippet_id)),
            )

    def rename(self, snippet_id: int, name: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE snippets SET name = ?, updated_at = ? WHERE id = ?",
                (_name(name), _now(), int(snippet_id)),
            )

    def delete(self, snippet_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM snippets WHERE id = ?", (int(snippet_id),))
            self._normalize_order()

    def reorder(self, snippet_ids: list[int]) -> None:
        normalized = [int(snippet_id) for snippet_id in snippet_ids]
        with self._lock, self._conn:
            stored = {int(row[0]) for row in self._conn.execute("SELECT id FROM snippets")}
            if len(normalized) != len(set(normalized)) or set(normalized) != stored:
                raise ValueError("Snippet reorder must contain every stored snippet exactly once")
            # Avoid transient collisions with the unique sort-order index.
            self._conn.execute("UPDATE snippets SET sort_order = -id - 1")
            self._conn.executemany(
                "UPDATE snippets SET sort_order = ?, updated_at = ? WHERE id = ?",
                [(index, _now(), snippet_id) for index, snippet_id in enumerate(normalized)],
            )

    def import_legacy_directory(self, directory: Path) -> int:
        """Import the former ``*.txt`` store once, leaving it as a backup."""
        with self._lock, self._conn:
            done = self._conn.execute("SELECT value FROM meta WHERE key = ?", (LEGACY_IMPORT_META_KEY,)).fetchone()
            if done is not None:
                return 0
            paths = self._ordered_legacy_paths(directory)
            next_order = int(self._conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM snippets").fetchone()[0])
            imported = 0
            now = _now()
            for path in paths:
                try:
                    body = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO snippets(name, body, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (path.stem, body, next_order, now, now),
                )
                if cursor.rowcount:
                    imported += 1
                    next_order += 1
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, '1')",
                (LEGACY_IMPORT_META_KEY,),
            )
            return imported

    @staticmethod
    def _ordered_legacy_paths(directory: Path) -> list[Path]:
        paths = sorted(directory.glob("*.txt"), key=lambda item: item.name.casefold()) if directory.is_dir() else []
        try:
            payload = json.loads((directory / ".order.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = []
        order = payload if isinstance(payload, list) else []
        positions = {str(name).casefold(): index for index, name in enumerate(order)}
        paths.sort(key=lambda item: (positions.get(item.name.casefold(), len(positions)), item.name.casefold()))
        return paths

    def _normalize_order(self) -> None:
        ids = [int(row[0]) for row in self._conn.execute("SELECT id FROM snippets ORDER BY sort_order, id")]
        self._conn.execute("UPDATE snippets SET sort_order = -id - 1")
        self._conn.executemany(
            "UPDATE snippets SET sort_order = ? WHERE id = ?",
            list(enumerate(ids)),
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> SnippetRecord:
        return SnippetRecord(
            id=int(row["id"]),
            name=str(row["name"]),
            body=str(row["body"]),
            sort_order=int(row["sort_order"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
