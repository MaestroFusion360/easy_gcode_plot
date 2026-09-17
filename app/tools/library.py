"""Qt-free SQLite storage for turning and milling tool definitions."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
KIND_TURNING = "turning"
KIND_MILLING = "milling"
VALID_KINDS = frozenset({KIND_TURNING, KIND_MILLING})
STARTER_TOOLS_META_KEY = "starter_tools_seeded_v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tools (
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (kind, key)
);

CREATE INDEX IF NOT EXISTS idx_tools_kind ON tools(kind);
"""


@dataclass(frozen=True)
class ToolRecord:
    """One persisted tool definition."""

    kind: str
    key: str
    spec: dict
    created_at: str = ""
    updated_at: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_kind(kind: str) -> str:
    normalized = str(kind).strip().lower()
    if normalized not in VALID_KINDS:
        raise ValueError(f"Unknown tool kind: {kind!r}")
    return normalized


def _validate_key(key: str) -> str:
    normalized = str(key).strip().upper()
    if not normalized:
        raise ValueError("Tool key must not be empty")
    return normalized


def _validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("Tool spec must be a mapping")
    return dict(spec)


class ToolLibrary:
    """Thread-safe SQLite catalogue independent from Qt and QSettings."""

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
                raise RuntimeError(f"Unsupported tool-library schema version: {stored}")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(key), str(value)),
            )

    def list_tools(self, *, kind: str | None = None) -> list[ToolRecord]:
        with self._lock:
            if kind is None:
                rows = self._conn.execute(
                    "SELECT kind, key, spec_json, created_at, updated_at FROM tools ORDER BY kind, key"
                ).fetchall()
            else:
                normalized_kind = _validate_kind(kind)
                rows = self._conn.execute(
                    "SELECT kind, key, spec_json, created_at, updated_at FROM tools WHERE kind = ? ORDER BY key",
                    (normalized_kind,),
                ).fetchall()
            return [self._row_to_record(row) for row in rows]

    def tools_by_kind(self, kind: str) -> dict[str, dict]:
        return {record.key: dict(record.spec) for record in self.list_tools(kind=kind)}

    def get_tool(self, kind: str, key: str) -> ToolRecord | None:
        normalized_kind = _validate_kind(kind)
        normalized_key = _validate_key(key)
        with self._lock:
            row = self._conn.execute(
                "SELECT kind, key, spec_json, created_at, updated_at FROM tools WHERE kind = ? AND key = ?",
                (normalized_kind, normalized_key),
            ).fetchone()
            return self._row_to_record(row) if row is not None else None

    def save_tool(self, kind: str, key: str, spec: dict) -> None:
        normalized_kind = _validate_kind(kind)
        normalized_key = _validate_key(key)
        payload = json.dumps(_validate_spec(spec), ensure_ascii=False, sort_keys=True)
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(kind, key) DO UPDATE SET spec_json = excluded.spec_json, updated_at = excluded.updated_at",
                (normalized_kind, normalized_key, payload, now, now),
            )

    def delete_tool(self, kind: str, key: str) -> None:
        normalized_kind = _validate_kind(kind)
        normalized_key = _validate_key(key)
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM tools WHERE kind = ? AND key = ?",
                (normalized_kind, normalized_key),
            )

    def add_missing_tools(self, kind: str, tools: dict[str, dict]) -> dict[str, dict]:
        """Insert candidates atomically without updating any existing record."""
        kind = _validate_kind(kind)
        now = _now()
        rows = [
            (kind, _validate_key(key), json.dumps(_validate_spec(spec), ensure_ascii=False), now, now)
            for key, spec in tools.items()
        ]
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(kind, key) DO NOTHING",
                rows,
            )
            return {key: self.get_tool(kind, key).spec for _, key, *_ in rows}

    def apply_edits(self, kind, original, edited):
        """Commit explicit edits only, preserving records absent from the editor."""
        kind = _validate_kind(kind)
        with self._lock, self._conn:
            self._apply_edits(kind, original, edited)

    def apply_edits_by_kind(self, changes):
        """Commit multiple kind-specific edits in one SQLite transaction."""
        prepared = [(_validate_kind(kind), original, edited) for kind, (original, edited) in changes.items()]
        with self._lock, self._conn:
            for kind, original, edited in prepared:
                self._apply_edits(kind, original, edited)

    def _apply_edits(self, kind, original, edited):
        for key in original.keys() - edited.keys():
            self._conn.execute("DELETE FROM tools WHERE kind = ? AND key = ?", (kind, _validate_key(key)))
        for key, spec in edited.items():
            if key not in original:
                self._insert_entry(kind, key, spec)
            elif spec != original[key]:
                payload = json.dumps(_validate_spec(spec), ensure_ascii=False)
                self._conn.execute(
                    "UPDATE tools SET spec_json = ?, updated_at = ? WHERE kind = ? AND key = ?",
                    (payload, _now(), kind, _validate_key(key)),
                )

    def _insert_entry(self, kind, key, spec):
        now = _now()
        self._conn.execute(
            "INSERT INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (kind, _validate_key(key), json.dumps(_validate_spec(spec), ensure_ascii=False), now, now),
        )

    def duplicate_tool(self, kind: str, key: str, new_key: str) -> None:
        normalized_kind = _validate_kind(kind)
        normalized_key = _validate_key(key)
        normalized_new_key = _validate_key(new_key)
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT spec_json FROM tools WHERE kind = ? AND key = ?",
                (normalized_kind, normalized_key),
            ).fetchone()
            if row is None:
                raise KeyError((normalized_kind, normalized_key))
            now = _now()
            self._conn.execute(
                "INSERT INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (normalized_kind, normalized_new_key, str(row["spec_json"]), now, now),
            )

    def sync_kind(self, kind: str, tools: dict[str, dict]) -> None:
        """Atomically replace one complete kind-specific tool set."""
        normalized_kind = _validate_kind(kind)
        prepared: list[tuple[str, str]] = []
        for key, spec in tools.items():
            normalized_key = _validate_key(key)
            payload = json.dumps(_validate_spec(spec), ensure_ascii=False, sort_keys=True)
            prepared.append((normalized_key, payload))

        now = _now()
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM tools WHERE kind = ?", (normalized_kind,))
            self._conn.executemany(
                "INSERT INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                [(normalized_kind, key, payload, now, now) for key, payload in prepared],
            )

    def seed_defaults_once(self, turning: dict[str, dict], milling: dict[str, dict]) -> bool:
        """Add starter tools once without overwriting existing user-created keys."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?",
                (STARTER_TOOLS_META_KEY,),
            ).fetchone()
            if row is not None and str(row["value"]) == "1":
                return False
            now = _now()
            self._insert_missing(KIND_TURNING, turning, now)
            self._insert_missing(KIND_MILLING, milling, now)
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, '1') ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (STARTER_TOOLS_META_KEY,),
            )
            return True

    def _insert_missing(self, kind: str, tools: dict[str, dict], now: str) -> None:
        for key, spec in tools.items():
            normalized_key = _validate_key(key)
            payload = json.dumps(_validate_spec(spec), ensure_ascii=False, sort_keys=True)
            self._conn.execute(
                "INSERT OR IGNORE INTO tools(kind, key, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (kind, normalized_key, payload, now, now),
            )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ToolRecord:
        spec = json.loads(row["spec_json"])
        if not isinstance(spec, dict):
            raise ValueError(f"Invalid tool-library payload for {row['kind']}:{row['key']}")
        return ToolRecord(
            kind=str(row["kind"]),
            key=str(row["key"]),
            spec=spec,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
