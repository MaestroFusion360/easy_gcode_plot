"""Qt-free SQLite storage for reusable G-code snippets."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.gcode.snippet_defaults import LANGUAGES, default_snippets

SCHEMA_VERSION = 3
LOGGER = logging.getLogger(__name__)
LEGACY_IMPORT_META_KEY = "legacy_text_snippets_imported_v1"

_SNIPPETS_SCHEMA = """
CREATE TABLE snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language_id TEXT NOT NULL REFERENCES snippet_languages(id),
    name TEXT NOT NULL COLLATE NOCASE,
    body TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(language_id, name),
    UNIQUE(language_id, sort_order)
)
"""


@dataclass(frozen=True, slots=True)
class SnippetRecord:
    id: int
    name: str
    body: str
    sort_order: int
    created_at: str
    updated_at: str
    language_id: str


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
        self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            self._ensure_schema_version()
        except Exception:
            self._conn.close()
            raise

    def _ensure_schema_version(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = self._conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            stored = int(row["value"]) if row else 0
            if stored not in (0, 1, 2, SCHEMA_VERSION):
                raise RuntimeError(f"Unsupported snippet-library schema version: {stored}")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS snippet_languages "
                "(id TEXT PRIMARY KEY, name TEXT NOT NULL, sort_order INTEGER NOT NULL UNIQUE)"
            )
            self._conn.executemany(
                "INSERT OR IGNORE INTO snippet_languages(id, name, sort_order) VALUES (?, ?, ?)",
                [(key, name, index) for index, (key, name) in enumerate(LANGUAGES)],
            )
            if stored == 1:
                self._conn.execute("ALTER TABLE snippets RENAME TO snippets_v1")
                self._conn.execute(_SNIPPETS_SCHEMA)
                self._conn.execute(
                    "INSERT INTO snippets(id, language_id, name, body, sort_order, created_at, updated_at) "
                    "SELECT id, 'fanuc_mill', name, body, sort_order, created_at, updated_at FROM snippets_v1"
                )
                self._conn.execute("DROP TABLE snippets_v1")
            elif stored == 0:
                self._conn.execute(_SNIPPETS_SCHEMA)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS snippet_images ("
                "snippet_id INTEGER PRIMARY KEY REFERENCES snippets(id) ON DELETE CASCADE, "
                "data BLOB NOT NULL)"
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )

    def list_languages(self) -> list[tuple[str, str]]:
        with self._lock:
            return [
                tuple(row) for row in self._conn.execute("SELECT id, name FROM snippet_languages ORDER BY sort_order")
            ]

    def ensure_defaults(self) -> None:
        """Seed once, without replacing user text or restoring deleted examples."""
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            key = "language_defaults_v2"
            if self._conn.execute("SELECT 1 FROM meta WHERE key = ?", (key,)).fetchone():
                return
            now = _now()
            for language_id, _label in LANGUAGES:
                order = self._next_order(language_id)
                for name, body in default_snippets(language_id):
                    cursor = self._conn.execute(
                        "INSERT OR IGNORE INTO snippets(language_id, name, body, sort_order, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (language_id, name, body, order, now, now),
                    )
                    order += cursor.rowcount
            self._conn.execute("INSERT INTO meta(key, value) VALUES (?, '1')", (key,))

    def refresh_defaults(self, language_id: str, pictures: dict[str, bytes] | None = None) -> tuple[int, int]:
        """Restore the selected controller's standard text without deleting custom records or images."""
        if language_id not in dict(LANGUAGES):
            raise ValueError(f"Unknown snippet language: {language_id}")
        updated = added = 0
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            records = {record.name.casefold(): record for record in self.list_snippets(language_id)}
            for name, body in default_snippets(language_id):
                record = records.get(name.casefold())
                if record is None:
                    self._conn.execute(
                        "INSERT INTO snippets(language_id, name, body, sort_order, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (language_id, name, body, self._next_order(language_id), _now(), _now()),
                    )
                    added += 1
                elif record.body != body:
                    self._conn.execute(
                        "UPDATE snippets SET body = ?, updated_at = ? WHERE id = ?", (body, _now(), record.id)
                    )
                    updated += 1
            for name, data in (pictures or {}).items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO snippet_images(snippet_id, data) "
                    "SELECT id, ? FROM snippets WHERE language_id = ? AND name = ?",
                    (data, language_id, name),
                )
        return updated, added

    def _next_order(self, language_id: str) -> int:
        return int(
            self._conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM snippets WHERE language_id = ?", (language_id,)
            ).fetchone()[0]
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def list_snippets(self, language_id: str = "fanuc_mill") -> list[SnippetRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snippets WHERE language_id = ? ORDER BY sort_order, id", (language_id,)
            ).fetchall()
            return [self._record(row) for row in rows]

    def add(self, name: str, body: str = "", language_id: str = "fanuc_mill") -> SnippetRecord:
        name = _name(name)
        now = _now()
        with self._lock, self._conn:
            next_order = self._next_order(language_id)
            cursor = self._conn.execute(
                "INSERT INTO snippets(language_id, name, body, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (language_id, name, str(body), next_order, now, now),
            )
            row = self._conn.execute(
                "SELECT * FROM snippets WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._record(row)

    def update_body(self, snippet_id: int, body: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE snippets SET body = ?, updated_at = ? WHERE id = ?",
                (str(body), _now(), int(snippet_id)),
            )

    def image(self, snippet_id: int) -> bytes | None:
        """Load an illustration only when its snippet is selected."""
        with self._lock:
            row = self._conn.execute("SELECT data FROM snippet_images WHERE snippet_id = ?", (snippet_id,)).fetchone()
            return bytes(row[0]) if row else None

    def has_image(self, snippet_id: int) -> bool:
        """Check attachment presence without loading the image BLOB."""
        with self._lock:
            return (
                self._conn.execute("SELECT 1 FROM snippet_images WHERE snippet_id = ?", (snippet_id,)).fetchone()
                is not None
            )

    def update_content(self, snippet_id: int, body: str, image: bytes | None) -> None:
        """Save text and illustration atomically, preserving the snippet identity."""
        if image is not None and len(image) > 10 * 1024 * 1024:
            raise ValueError("Snippet illustration exceeds 10 MB")
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE snippets SET body = ?, updated_at = ? WHERE id = ?", (str(body), _now(), snippet_id)
            )
            self._write_image(snippet_id, image)

    def _write_image(self, snippet_id: int, image: bytes | None) -> None:
        if image is None:
            self._conn.execute("DELETE FROM snippet_images WHERE snippet_id = ?", (snippet_id,))
        else:
            self._conn.execute(
                "INSERT INTO snippet_images(snippet_id, data) VALUES (?, ?) "
                "ON CONFLICT(snippet_id) DO UPDATE SET data = excluded.data",
                (snippet_id, image),
            )

    def ensure_illustrations(
        self, pictures: dict[tuple[str, str], bytes], *, key: str = "template_illustrations_v1"
    ) -> None:
        """Attach bundled diagrams once, without altering existing user illustrations."""
        if not pictures:
            return
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            if self._conn.execute("SELECT 1 FROM meta WHERE key = ?", (key,)).fetchone():
                return
            for language_id, _label in LANGUAGES:
                for name, body in default_snippets(language_id):
                    if (language_id, name) not in pictures:
                        continue
                    self._conn.execute(
                        "INSERT OR IGNORE INTO snippet_images(snippet_id, data) "
                        "SELECT id, ? FROM snippets WHERE language_id = ? AND name = ? AND body = ?",
                        (pictures[(language_id, name)], language_id, name, body),
                    )
            self._conn.execute("INSERT INTO meta(key, value) VALUES (?, '1')", (key,))

    def rename(self, snippet_id: int, name: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE snippets SET name = ?, updated_at = ? WHERE id = ?",
                (_name(name), _now(), int(snippet_id)),
            )

    def delete(self, snippet_id: int) -> None:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT language_id FROM snippets WHERE id = ?", (int(snippet_id),)).fetchone()
            self._conn.execute("DELETE FROM snippets WHERE id = ?", (int(snippet_id),))
            if row:
                self._normalize_order(row[0])

    def reorder(self, snippet_ids: list[int], language_id: str = "fanuc_mill") -> None:
        normalized = [int(snippet_id) for snippet_id in snippet_ids]
        with self._lock, self._conn:
            stored = {
                int(row[0])
                for row in self._conn.execute("SELECT id FROM snippets WHERE language_id = ?", (language_id,))
            }
            if len(normalized) != len(set(normalized)) or set(normalized) != stored:
                raise ValueError("Snippet reorder must contain every stored snippet exactly once")
            # Avoid transient collisions with the unique sort-order index.
            self._conn.execute("UPDATE snippets SET sort_order = -id - 1 WHERE language_id = ?", (language_id,))
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
            next_order = self._next_order("fanuc_mill")
            imported = 0
            now = _now()
            for path in paths:
                try:
                    body = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    LOGGER.warning("Cannot import legacy snippet %s: %s", path, exc)
                    continue
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO snippets(name, body, sort_order, created_at, updated_at, language_id) "
                    "VALUES (?, ?, ?, ?, ?, 'fanuc_mill')",
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
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = []
        order = payload if isinstance(payload, list) else []
        positions = {str(name).casefold(): index for index, name in enumerate(order)}
        paths.sort(key=lambda item: (positions.get(item.name.casefold(), len(positions)), item.name.casefold()))
        return paths

    def _normalize_order(self, language_id: str) -> None:
        ids = [
            int(row[0])
            for row in self._conn.execute(
                "SELECT id FROM snippets WHERE language_id = ? ORDER BY sort_order, id", (language_id,)
            )
        ]
        self._conn.execute("UPDATE snippets SET sort_order = -id - 1 WHERE language_id = ?", (language_id,))
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
            language_id=str(row["language_id"]),
        )
