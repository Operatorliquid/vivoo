from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading

from inference.events import NormalizedCaptureEvent


class EventOutbox:
    """Durable local queue for events that must survive a network outage."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS events (source_id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS media_uploads (
                    upload_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    local_source_path TEXT NOT NULL,
                    storage_key TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def enqueue(self, event: NormalizedCaptureEvent, session_id: str, local_source_path: Path | None = None) -> None:
        payload = asdict(event)
        for key, value in tuple(payload.items()):
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            elif value is None:
                payload.pop(key)
        if local_source_path is not None:
            payload["local_source_path"] = str(local_source_path)
        payload["session_id"] = session_id
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO events(source_id, payload, created_at) VALUES (?, ?, ?)",
                (event.source_id, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )

    def set_source_storage_key(self, source_id: str, storage_key: str) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT payload FROM events WHERE source_id = ?", (source_id,)).fetchone()
            if row is None:
                return
            payload = json.loads(row[0])
            payload["source_storage_key"] = storage_key
            connection.execute("UPDATE events SET payload = ? WHERE source_id = ?", (json.dumps(payload), source_id))

    def pending(self) -> list[dict[str, object]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT source_id, payload FROM events WHERE status = 'pending' ORDER BY created_at").fetchall()
        return [{"source_id": row[0], "payload": json.loads(row[1])} for row in rows]

    def mark_sent(self, source_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE events SET status = 'sent' WHERE source_id = ?", (source_id,))

    def pending_count(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM events WHERE status = 'pending'").fetchone()[0])

    def enqueue_media(self, upload_id: str, session_id: str, media_type: str, content_type: str, local_source_path: Path) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO media_uploads(
                    upload_id, session_id, media_type, content_type, local_source_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (upload_id, session_id, media_type, content_type, str(local_source_path), datetime.now(timezone.utc).isoformat()),
            )

    def pending_media(self) -> list[dict[str, object]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT upload_id, session_id, media_type, content_type, local_source_path,
                       storage_key, attempts, last_error
                FROM media_uploads WHERE status = 'pending' ORDER BY created_at
                """
            ).fetchall()
        return [
            {
                "upload_id": row[0], "session_id": row[1], "media_type": row[2],
                "content_type": row[3], "local_source_path": row[4],
                "storage_key": row[5], "attempts": row[6], "last_error": row[7],
            }
            for row in rows
        ]

    def set_media_storage_key(self, upload_id: str, storage_key: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE media_uploads SET storage_key = ? WHERE upload_id = ?",
                (storage_key, upload_id),
            )

    def mark_media_attempt(self, upload_id: str, error: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE media_uploads SET attempts = attempts + 1, last_error = ? WHERE upload_id = ?",
                (error[:500], upload_id),
            )

    def mark_media_sent(self, upload_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE media_uploads SET status = 'sent', last_error = NULL WHERE upload_id = ?",
                (upload_id,),
            )

    def pending_media_count(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM media_uploads WHERE status = 'pending'").fetchone()[0])
