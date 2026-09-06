"""PostgreSQL persistence for mutable club configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import settings
from security.secret_cipher import SecretCipher


class FileConfigurationPersistence:
    """Small durable local adapter used only when developing without PostgreSQL."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.cipher = SecretCipher(settings.data_encryption_key)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, owner_id: str) -> dict[str, Any] | None:
        del owner_id
        if not self.path.exists():
            return None
        try:
            payload = self._read_raw()
            migration_required = False
            for camera in payload.get("cameras", []):
                password = str(camera.get("password", ""))
                migration_required = migration_required or bool(password and not self.cipher.is_encrypted(password))
                camera["password"] = self.cipher.decrypt(password)
            for field_id, secret in payload.get("button_secrets", {}).items():
                value = str(secret)
                migration_required = migration_required or bool(value and not self.cipher.is_encrypted(value))
                payload["button_secrets"][field_id] = self.cipher.decrypt(value)
            payload["_secret_migration_required"] = migration_required
            return payload
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"No se pudo leer la configuración local: {self.path}") from error

    def save(
        self,
        owner_id: str,
        club: dict[str, Any],
        fields: list[dict[str, Any]],
        cameras: list[dict[str, Any]],
        buttons: dict[str, dict[str, Any]],
        button_secrets: dict[str, str],
        notifications: list[dict[str, Any]],
    ) -> None:
        previous = self.load(owner_id) or {}
        payload = {
            "club": club,
            "fields": fields,
            "cameras": [
                {**camera, "password": self.cipher.encrypt(str(camera.get("password", "")))}
                for camera in cameras
            ],
            "buttons": buttons,
            "button_secrets": {
                field_id: self.cipher.encrypt(secret)
                for field_id, secret in button_secrets.items()
            },
            "notifications_initialized": True,
            "notifications": notifications,
            "runtime_state": previous.get("runtime_state"),
        }
        self._write(payload)

    def save_runtime_state(self, owner_id: str, runtime_state: dict[str, Any]) -> None:
        del owner_id
        previous = self._read_raw() if self.path.exists() else {
            "club": None,
            "fields": [],
            "cameras": [],
            "buttons": {},
            "button_secrets": {},
            "notifications_initialized": True,
            "notifications": [],
        }
        previous["runtime_state"] = runtime_state
        self._write(previous)

    def _read_raw(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        except OSError as error:
            raise RuntimeError(f"No se pudo guardar la configuración local: {self.path}") from error


class ConfigurationPersistence:
    """Persists the owner configuration while the domain store remains in-memory."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.cipher = SecretCipher(settings.data_encryption_key)

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - only relevant outside the API image
            raise RuntimeError("psycopg is required when DATABASE_URL is configured") from error
        return psycopg.connect(self.database_url)

    def initialize(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS courtvision_clubs (
                owner_id text PRIMARY KEY,
                id text NOT NULL,
                name text NOT NULL DEFAULT '',
                city text NOT NULL DEFAULT '',
                logo_data_url text NOT NULL DEFAULT '',
                fields_count integer NOT NULL DEFAULT 0,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            """
            ALTER TABLE courtvision_clubs
            ADD COLUMN IF NOT EXISTS logo_data_url text NOT NULL DEFAULT ''
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_runtime_state (
                owner_id text PRIMARY KEY,
                payload jsonb NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_fields (
                owner_id text NOT NULL,
                id text NOT NULL,
                name text NOT NULL,
                field_token text NOT NULL,
                sport_code text NOT NULL,
                status text NOT NULL,
                recording_enabled boolean NOT NULL DEFAULT true,
                detection_mode text NOT NULL,
                qr_url text NOT NULL,
                PRIMARY KEY (owner_id, id)
            )
            """,
            """
            ALTER TABLE courtvision_fields
            ALTER COLUMN recording_enabled SET DEFAULT true
            """,
            """
            UPDATE courtvision_fields
            SET recording_enabled = true
            WHERE recording_enabled = false
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_cameras (
                owner_id text NOT NULL,
                id text NOT NULL,
                field_id text NOT NULL,
                name text NOT NULL,
                serial_number text NOT NULL DEFAULT '',
                stream_url text NOT NULL DEFAULT '',
                host text NOT NULL DEFAULT '',
                rtsp_port integer NOT NULL DEFAULT 554,
                username text NOT NULL DEFAULT '',
                password text NOT NULL DEFAULT '',
                stream_path text NOT NULL DEFAULT '',
                status text NOT NULL,
                last_seen text NOT NULL,
                detector_status text NOT NULL DEFAULT 'idle',
                detector_fps double precision NOT NULL DEFAULT 0,
                detector_last_frame_at text,
                agent_token_hash text NOT NULL DEFAULT '',
                agent_last_seen_at text,
                agent_accepted_at text,
                PRIMARY KEY (owner_id, id),
                UNIQUE (owner_id, field_id)
            )
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS detector_status text NOT NULL DEFAULT 'idle'
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS detector_fps double precision NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS detector_last_frame_at text
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS agent_token_hash text NOT NULL DEFAULT ''
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS agent_last_seen_at text
            """,
            """
            ALTER TABLE courtvision_cameras
            ADD COLUMN IF NOT EXISTS agent_accepted_at text
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_buttons (
                owner_id text NOT NULL,
                field_id text NOT NULL,
                device_id text NOT NULL,
                label text NOT NULL,
                status text NOT NULL,
                last_seen text NOT NULL,
                secret text NOT NULL,
                PRIMARY KEY (owner_id, field_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_notification_state (
                owner_id text PRIMARY KEY,
                initialized boolean NOT NULL DEFAULT false
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_notifications (
                owner_id text NOT NULL,
                id text NOT NULL,
                kind text NOT NULL,
                title text NOT NULL,
                detail text NOT NULL,
                time text NOT NULL,
                read boolean NOT NULL DEFAULT false,
                severity text NOT NULL,
                PRIMARY KEY (owner_id, id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS courtvision_service_heartbeats (
                service_name text PRIMARY KEY,
                observed_at timestamptz NOT NULL,
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb
            )
            """,
        )
        with self._connect() as connection:
            for statement in statements:
                connection.execute(statement)

    def load(self, owner_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            club = connection.execute(
                "SELECT id, name, city, logo_data_url, fields_count FROM courtvision_clubs WHERE owner_id = %s",
                (owner_id,),
            ).fetchone()
            fields = connection.execute(
                """
                SELECT id, name, field_token, sport_code, status, recording_enabled, detection_mode, qr_url
                FROM courtvision_fields WHERE owner_id = %s ORDER BY id
                """,
                (owner_id,),
            ).fetchall()
            cameras = connection.execute(
                """
                SELECT id, field_id, name, serial_number, stream_url, host, rtsp_port, username,
                       password, stream_path, status, last_seen, detector_status, detector_fps,
                       detector_last_frame_at, agent_token_hash, agent_last_seen_at, agent_accepted_at
                FROM courtvision_cameras WHERE owner_id = %s ORDER BY id
                """,
                (owner_id,),
            ).fetchall()
            buttons = connection.execute(
                """
                SELECT field_id, device_id, label, status, last_seen, secret
                FROM courtvision_buttons WHERE owner_id = %s
                """,
                (owner_id,),
            ).fetchall()
            notification_state = connection.execute(
                "SELECT initialized FROM courtvision_notification_state WHERE owner_id = %s",
                (owner_id,),
            ).fetchone()
            notifications = connection.execute(
                """
                SELECT id, kind, title, detail, time, read, severity
                FROM courtvision_notifications WHERE owner_id = %s ORDER BY id
                """,
                (owner_id,),
            ).fetchall()
            runtime_state = connection.execute(
                "SELECT payload FROM courtvision_runtime_state WHERE owner_id = %s",
                (owner_id,),
            ).fetchone()

        if club is None and not fields and not cameras and not buttons:
            return None

        migration_required = any(row[8] and not self.cipher.is_encrypted(row[8]) for row in cameras)
        migration_required = migration_required or any(row[5] and not self.cipher.is_encrypted(row[5]) for row in buttons)
        return {
            "club": {"id": club[0], "name": club[1], "city": club[2], "logo_data_url": club[3], "fields_count": club[4]} if club else None,
            "fields": [
                {
                    "id": row[0],
                    "name": row[1],
                    "field_token": row[2],
                    "sport_code": row[3],
                    "status": row[4],
                    "recording_enabled": row[5],
                    "detection_mode": row[6],
                    "qr_url": row[7],
                }
                for row in fields
            ],
            "cameras": [
                {
                    "id": row[0],
                    "field_id": row[1],
                    "name": row[2],
                    "serial_number": row[3],
                    "stream_url": row[4],
                    "host": row[5],
                    "rtsp_port": row[6],
                    "username": row[7],
                    "password": self.cipher.decrypt(row[8]),
                    "stream_path": row[9],
                    "status": row[10],
                    "last_seen": row[11],
                    "detector_status": row[12],
                    "detector_fps": row[13],
                    "detector_last_frame_at": row[14],
                    "agent_token_hash": row[15],
                    "agent_last_seen_at": row[16],
                    "agent_accepted_at": row[17],
                }
                for row in cameras
            ],
            "buttons": {
                row[0]: {"device_id": row[1], "label": row[2], "status": row[3], "last_seen": row[4]}
                for row in buttons
            },
            "button_secrets": {row[0]: self.cipher.decrypt(row[5]) for row in buttons},
            "notifications_initialized": bool(notification_state[0]) if notification_state else False,
            "notifications": [
                {"id": row[0], "kind": row[1], "title": row[2], "detail": row[3], "time": row[4], "read": row[5], "severity": row[6]}
                for row in notifications
            ],
            "runtime_state": runtime_state[0] if runtime_state else None,
            "_secret_migration_required": migration_required,
        }

    def save_runtime_state(self, owner_id: str, runtime_state: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO courtvision_runtime_state (owner_id, payload, updated_at)
                VALUES (%s, %s::jsonb, now())
                ON CONFLICT (owner_id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (owner_id, json.dumps(runtime_state)),
            )

    def save(
        self,
        owner_id: str,
        club: dict[str, Any],
        fields: list[dict[str, Any]],
        cameras: list[dict[str, Any]],
        buttons: dict[str, dict[str, Any]],
        button_secrets: dict[str, str],
        notifications: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO courtvision_clubs (owner_id, id, name, city, logo_data_url, fields_count, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (owner_id) DO UPDATE SET
                    id = EXCLUDED.id, name = EXCLUDED.name, city = EXCLUDED.city,
                    logo_data_url = EXCLUDED.logo_data_url,
                    fields_count = EXCLUDED.fields_count, updated_at = now()
                """,
                (owner_id, club["id"], club.get("name", ""), club.get("city", ""), club.get("logo_data_url", ""), len(fields)),
            )
            connection.execute("DELETE FROM courtvision_fields WHERE owner_id = %s", (owner_id,))
            connection.execute("DELETE FROM courtvision_cameras WHERE owner_id = %s", (owner_id,))
            connection.execute("DELETE FROM courtvision_buttons WHERE owner_id = %s", (owner_id,))
            connection.execute("DELETE FROM courtvision_notifications WHERE owner_id = %s", (owner_id,))

            for item in fields:
                connection.execute(
                    """
                    INSERT INTO courtvision_fields
                    (owner_id, id, name, field_token, sport_code, status, recording_enabled, detection_mode, qr_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (owner_id, item["id"], item["name"], item["field_token"], item["sport_code"], item["status"], item["recording_enabled"], item["detection_mode"], item["qr_url"]),
                )

            for item in cameras:
                connection.execute(
                    """
                    INSERT INTO courtvision_cameras
                    (owner_id, id, field_id, name, serial_number, stream_url, host, rtsp_port,
                     username, password, stream_path, status, last_seen, detector_status, detector_fps,
                     detector_last_frame_at, agent_token_hash, agent_last_seen_at, agent_accepted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (owner_id, item["id"], item["field_id"], item["name"], item.get("serial_number", ""), item.get("stream_url", ""), item.get("host", ""), item.get("rtsp_port", 554), item.get("username", ""), self.cipher.encrypt(str(item.get("password", ""))), item.get("stream_path", ""), item["status"], item["last_seen"], item.get("detector_status", "idle"), item.get("detector_fps", 0.0), item.get("detector_last_frame_at"), item.get("agent_token_hash", ""), item.get("agent_last_seen_at"), item.get("agent_accepted_at")),
                )

            for field_id, item in buttons.items():
                connection.execute(
                    """
                    INSERT INTO courtvision_buttons
                    (owner_id, field_id, device_id, label, status, last_seen, secret)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (owner_id, field_id, item["device_id"], item["label"], item["status"], item["last_seen"], self.cipher.encrypt(button_secrets.get(field_id, ""))),
                )

            connection.execute(
                """
                INSERT INTO courtvision_notification_state (owner_id, initialized)
                VALUES (%s, true)
                ON CONFLICT (owner_id) DO UPDATE SET initialized = true
                """,
                (owner_id,),
            )
            for item in notifications:
                connection.execute(
                    """
                    INSERT INTO courtvision_notifications
                    (owner_id, id, kind, title, detail, time, read, severity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (owner_id, item["id"], item["kind"], item["title"], item["detail"], item["time"], item["read"], item["severity"]),
                )
