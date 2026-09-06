from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL


@dataclass(frozen=True)
class DeliveryItem:
    id: str
    job_id: str
    phone_e164: str
    display_name: str
    media_url: str
    caption: str
    instance: str
    state: str
    send_attempts: int
    created_at: float
    last_error: str | None


class DeliveryOutbox:
    """Durable WhatsApp queue; survives worker, container and network restarts."""

    MAX_SEND_ATTEMPTS = 96
    MAX_AGE_SECONDS = 48 * 60 * 60

    def __init__(self, path: Path, clock=time.time) -> None:
        self.path = path
        self.clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_outbox (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    phone_e164 TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    media_url TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    instance TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    send_attempts INTEGER NOT NULL DEFAULT 0,
                    callback_attempts INTEGER NOT NULL DEFAULT 0,
                    available_at REAL NOT NULL,
                    locked_until REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_error TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def enqueue(
        self, job_id: str, resource_id: str, phone_e164: str, display_name: str,
        media_url: str, caption: str, instance: str,
    ) -> str:
        item_id = str(uuid5(NAMESPACE_URL, f"vivoo:delivery:{resource_id}:{phone_e164}"))
        now = self.clock()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO delivery_outbox
                   (id, job_id, phone_e164, display_name, media_url, caption, instance, available_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, job_id, phone_e164, display_name, media_url, caption, instance, now, now),
            )
        return item_id

    def claim_next(self) -> DeliveryItem | None:
        now = self.clock()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM delivery_outbox
                   WHERE available_at <= ? AND locked_until <= ?
                   ORDER BY available_at, created_at LIMIT 1""",
                (now, now),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE delivery_outbox SET locked_until = ? WHERE id = ?",
                (now + 120, row["id"]),
            )
        return DeliveryItem(
            id=row["id"], job_id=row["job_id"], phone_e164=row["phone_e164"],
            display_name=row["display_name"], media_url=row["media_url"], caption=row["caption"],
            instance=row["instance"], state=row["state"], send_attempts=row["send_attempts"],
            created_at=row["created_at"], last_error=row["last_error"],
        )

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(15 * (2 ** min(max(0, attempt - 1), 8)), 30 * 60)

    def mark_sent(self, item_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE delivery_outbox SET state='sent', locked_until=0, available_at=?, last_error=NULL WHERE id=?",
                (self.clock(), item_id),
            )

    def mark_send_failure(self, item: DeliveryItem, error: str) -> bool:
        now = self.clock()
        attempts = item.send_attempts + 1
        terminal = attempts >= self.MAX_SEND_ATTEMPTS or now - item.created_at >= self.MAX_AGE_SECONDS
        state = "failed" if terminal else "pending"
        available_at = now if terminal else now + self._backoff(attempts)
        with self._connect() as connection:
            connection.execute(
                """UPDATE delivery_outbox
                   SET state=?, send_attempts=?, last_error=?, available_at=?, locked_until=0 WHERE id=?""",
                (state, attempts, error[:500], available_at, item.id),
            )
        return terminal

    def mark_callback_failure(self, item_id: str, error: str) -> None:
        now = self.clock()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT callback_attempts FROM delivery_outbox WHERE id=?", (item_id,),
            ).fetchone()
            attempts = int(row[0]) + 1 if row else 1
            connection.execute(
                """UPDATE delivery_outbox
                   SET callback_attempts=?, last_error=?, available_at=?, locked_until=0 WHERE id=?""",
                (attempts, error[:500], now + self._backoff(attempts), item_id),
            )

    def complete(self, item_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM delivery_outbox WHERE id=?", (item_id,))

    def pending_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT count(*) FROM delivery_outbox").fetchone()[0])
