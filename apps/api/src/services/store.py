import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from auth.local_auth import token_fingerprint
from db.configuration import ConfigurationPersistence, FileConfigurationPersistence
from domain.schemas import CaptureEventRequest, PresignUploadRequest, StartSessionRequest
from fastapi import HTTPException
from services.evolution_service import owner_instance_name

DEMO_FIELD_ID = UUID("3b4b1c7d-4e0d-4a65-8f71-9c0c9c0e0202")
DEMO_CLUB_ID = UUID("8f0e2f1a-1b21-4ef0-bd2a-2b1d5e540201")
DEMO_CAMERA_ID = UUID("c7e4d36b-3b9a-4d14-9d03-4aa4dbbd0203")
FIELD_IDS = {
    "field-01": DEMO_FIELD_ID,
    "demo-field-02": UUID("3b4b1c7d-4e0d-4a65-8f71-9c0c9c0e0204"),
    "field-03": UUID("3b4b1c7d-4e0d-4a65-8f71-9c0c9c0e0205"),
    "field-04": UUID("3b4b1c7d-4e0d-4a65-8f71-9c0c9c0e0206"),
}
VENUE_ID = UUID("5e1fd3a2-2b16-4a9b-9c6f-7e9a1d220207")
CAMERA_IDS = {
    "camera-01": DEMO_CAMERA_ID,
    "camera-02": UUID("c7e4d36b-3b9a-4d14-9d03-4aa4dbbd0204"),
    "camera-03": UUID("c7e4d36b-3b9a-4d14-9d03-4aa4dbbd0205"),
}
MAX_SESSION_DURATION = timedelta(hours=1)
FULL_RECORDING_RETENTION = timedelta(days=2)
PLAYER_ACCESS_TTL = timedelta(hours=max(1, int(os.getenv("PLAYER_ACCESS_TTL_HOURS", "168"))))
AGENT_HEARTBEAT_TIMEOUT = timedelta(seconds=max(60, int(os.getenv("AGENT_HEARTBEAT_TIMEOUT_SECONDS", "95"))))
PROCESSING_LEASE_TIMEOUT = timedelta(seconds=max(30, int(os.getenv("PROCESSING_LEASE_TIMEOUT_SECONDS", "120"))))


@dataclass
class PlayerRecord:
    id: UUID
    display_name: str
    phone_e164: str
    messaging_consent: bool


@dataclass
class SessionRecord:
    id: UUID
    token: str
    field_id: UUID
    camera_id: UUID
    sport_code: str
    started_at: datetime
    player_ids: list[UUID] = field(default_factory=list)
    ended_at: datetime | None = None
    started_by: str = "player"


@dataclass
class ConsentRecord:
    id: UUID
    player_id: UUID
    session_id: UUID
    recording_consent: bool
    messaging_consent: bool
    policy_version: str
    captured_at: datetime


@dataclass
class HighlightRecord:
    id: UUID
    event_id: UUID
    session_id: UUID
    occurred_at: datetime
    window_start_at: datetime
    window_end_at: datetime
    duration_seconds: int
    source_storage_key: str | None = None
    storage_key: str | None = None
    status: str = "processing"
    confidence: float | None = None


@dataclass
class ProcessingJobRecord:
    id: UUID
    job_type: str
    resource_id: UUID
    idempotency_key: str
    status: str = "queued"
    attempts: int = 0
    last_error: str | None = None
    leased_at: datetime | None = None


@dataclass
class RecordingRecord:
    id: UUID
    session_id: UUID
    storage_key: str
    status: str = "processing"


@dataclass
class PlayerAccessRecord:
    grant_id: UUID
    session_id: UUID
    player_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None


class LocalStore:
    """Deterministic local provider; production adapters persist the same contracts in RDS."""

    def __init__(
        self,
        owner_id: str = str(DEMO_CLUB_ID),
        email: str = "owner@courtvision.local",
        display_name: str = "José Stratta",
        *,
        seed_demo: bool | None = None,
    ) -> None:
        self._seed_demo = owner_id == str(DEMO_CLUB_ID) if seed_demo is None else seed_demo
        self.players: dict[UUID, PlayerRecord] = {}
        self.player_access: dict[str, PlayerAccessRecord] = {}
        self.sessions: dict[UUID, SessionRecord] = {}
        self.sessions_by_token: dict[str, UUID] = {}
        self.consents: dict[UUID, ConsentRecord] = {}
        self.highlights: dict[UUID, HighlightRecord] = {}
        self.recordings: dict[UUID, RecordingRecord] = {}
        self.recordings_by_key: dict[str, UUID] = {}
        self.processing_jobs: dict[UUID, ProcessingJobRecord] = {}
        self.processing_jobs_by_key: dict[str, UUID] = {}
        self.events_by_key: dict[str, tuple[UUID, UUID]] = {}
        self.idempotency: dict[str, UUID] = {}
        self.activity_events: list[dict[str, object]] = []
        club_id = str(DEMO_CLUB_ID) if self._seed_demo else str(uuid5(NAMESPACE_URL, f"tveo:club:{owner_id}"))
        self.club = {"id": club_id, "name": "", "city": "", "logo_data_url": "", "fields_count": 4 if self._seed_demo else 0}
        self.profile = {
            "id": owner_id,
            "email": email,
            "display_name": display_name,
            "role": "owner",
            "phone": "+54 9 11 5555 0118" if self._seed_demo else "",
            "timezone": "America/Argentina/Buenos_Aires",
        }
        self.fields = [
            {"id": "field-01", "name": "Cancha 01", "field_token": "field-01", "sport_code": "padel", "status": "active", "recording_enabled": True, "detection_mode": "arms_up", "qr_url": "/qr?field=field-01"},
            {"id": "field-02", "name": "Cancha 02", "field_token": "demo-field-02", "sport_code": "padel", "status": "active", "recording_enabled": True, "detection_mode": "arms_up", "qr_url": "/qr?field=demo-field-02"},
            {"id": "field-03", "name": "Cancha 03", "field_token": "field-03", "sport_code": "padel", "status": "active", "recording_enabled": True, "detection_mode": "arms_up", "qr_url": "/qr?field=field-03"},
            {"id": "field-04", "name": "Cancha 04", "field_token": "field-04", "sport_code": "padel", "status": "maintenance", "recording_enabled": True, "detection_mode": "manual", "qr_url": "/qr?field=field-04"},
        ] if self._seed_demo else []
        self.cameras = [
            {"id": "camera-01", "field_id": "field-01", "name": "Cámara fija 01", "serial_number": "CV-PTZ-001", "stream_url": "rtsp://edge.local/court-01", "status": "live", "last_seen": "hace 12s"},
            {"id": "camera-02", "field_id": "field-02", "name": "Cámara fija 02", "serial_number": "CV-PTZ-002", "stream_url": "rtsp://edge.local/court-02", "status": "live", "last_seen": "hace 12s"},
            {"id": "camera-03", "field_id": "field-03", "name": "Cámara fija 03", "serial_number": "CV-PTZ-003", "stream_url": "rtsp://edge.local/court-03", "status": "ready", "last_seen": "lista"},
        ] if self._seed_demo else []
        self.buttons = {
            "field-01": {"device_id": "CV-BTN-01", "label": "Botón de highlights", "status": "ready", "last_seen": "sin conexión"},
        } if self._seed_demo else {}
        self.button_secrets = {"field-01": "button-secret-demo"} if self._seed_demo else {}
        self.notifications = []
        database_url = os.getenv("DATABASE_URL", "").strip()
        local_config_file = os.getenv("COURTVISION_CONFIG_FILE", "").strip()
        if database_url:
            self.persistence = ConfigurationPersistence(database_url)
        elif local_config_file:
            self.persistence = FileConfigurationPersistence(local_config_file)
        else:
            self.persistence = None
        if self.persistence:
            self.persistence.initialize()
            persisted = self.persistence.load(self.profile["id"])
            if persisted is None:
                self._persist_configuration()
            else:
                if persisted["club"] is not None:
                    self.club = persisted["club"]
                self.fields = persisted["fields"]
                recording_policy_migration = any(not bool(item.get("recording_enabled")) for item in self.fields)
                for item in self.fields:
                    item["recording_enabled"] = True
                self.cameras = persisted["cameras"]
                self.buttons = persisted["buttons"]
                self.button_secrets = persisted["button_secrets"]
                if persisted["notifications_initialized"]:
                    self.notifications = [item for item in persisted["notifications"] if not str(item.get("id", "")).startswith("notification-")]
                else:
                    self._persist_configuration()
                if persisted.get("runtime_state"):
                    self._restore_runtime(persisted["runtime_state"])
                if persisted.get("_secret_migration_required") or recording_policy_migration:
                    self._persist_configuration()

    def _persist_configuration(self) -> None:
        if self.persistence:
            self.persistence.save(self.profile["id"], self.club, self.fields, self.cameras, self.buttons, self.button_secrets, self.notifications)

    def _persist_runtime(self) -> None:
        if not self.persistence:
            return
        payload = {
            "players": [
                {"id": str(item.id), "display_name": item.display_name, "phone_e164": item.phone_e164, "messaging_consent": item.messaging_consent}
                for item in self.players.values()
            ],
            "player_access": [
                {
                    "token_hash": token_hash,
                    "grant_id": str(value.grant_id),
                    "session_id": str(value.session_id),
                    "player_id": str(value.player_id),
                    "expires_at": value.expires_at.isoformat(),
                    "revoked_at": value.revoked_at.isoformat() if value.revoked_at else None,
                }
                for token_hash, value in self.player_access.items()
            ],
            "sessions": [
                {
                    "id": str(item.id), "token": item.token, "field_id": str(item.field_id), "camera_id": str(item.camera_id),
                    "sport_code": item.sport_code, "started_at": item.started_at.isoformat(),
                    "player_ids": [str(value) for value in item.player_ids],
                    "ended_at": item.ended_at.isoformat() if item.ended_at else None, "started_by": item.started_by,
                }
                for item in self.sessions.values()
            ],
            "consents": [
                {
                    "id": str(item.id), "player_id": str(item.player_id), "session_id": str(item.session_id),
                    "recording_consent": item.recording_consent, "messaging_consent": item.messaging_consent,
                    "policy_version": item.policy_version, "captured_at": item.captured_at.isoformat(),
                }
                for item in self.consents.values()
            ],
            "highlights": [
                {
                    "id": str(item.id), "event_id": str(item.event_id), "session_id": str(item.session_id),
                    "occurred_at": item.occurred_at.isoformat(), "window_start_at": item.window_start_at.isoformat(),
                    "window_end_at": item.window_end_at.isoformat(), "duration_seconds": item.duration_seconds,
                    "source_storage_key": item.source_storage_key, "storage_key": item.storage_key, "status": item.status,
                    "confidence": item.confidence,
                }
                for item in self.highlights.values()
            ],
            "recordings": [
                {"id": str(item.id), "session_id": str(item.session_id), "storage_key": item.storage_key, "status": item.status}
                for item in self.recordings.values()
            ],
            "processing_jobs": [
                {
                    "id": str(item.id), "job_type": item.job_type, "resource_id": str(item.resource_id),
                    "idempotency_key": item.idempotency_key, "status": item.status,
                    "attempts": item.attempts, "last_error": item.last_error,
                    "leased_at": item.leased_at.isoformat() if item.leased_at else None,
                }
                for item in self.processing_jobs.values()
            ],
            "events_by_key": {key: [str(value[0]), str(value[1])] for key, value in self.events_by_key.items()},
            "idempotency": {key: str(value) for key, value in self.idempotency.items()},
            "activity_events": self.activity_events,
        }
        self.persistence.save_runtime_state(self.profile["id"], payload)

    def _restore_runtime(self, payload: dict[str, object]) -> None:
        self.players = {
            UUID(str(item["id"])): PlayerRecord(UUID(str(item["id"])), str(item["display_name"]), str(item["phone_e164"]), bool(item["messaging_consent"]))
            for item in payload.get("players", [])
        }
        raw_access = payload.get("player_access", [])
        self.player_access = {}
        if isinstance(raw_access, dict):
            # One-time compatibility with early pilot links. Only the hash is kept
            # after the next persistence cycle.
            for token, value in raw_access.items():
                record = PlayerAccessRecord(
                    uuid4(), UUID(str(value[0])), UUID(str(value[1])),
                    datetime.now(timezone.utc) + PLAYER_ACCESS_TTL,
                )
                self.player_access[self._access_hash(str(token))] = record
        else:
            for item in raw_access:
                record = PlayerAccessRecord(
                    UUID(str(item["grant_id"])), UUID(str(item["session_id"])), UUID(str(item["player_id"])),
                    datetime.fromisoformat(str(item["expires_at"])),
                    datetime.fromisoformat(str(item["revoked_at"])) if item.get("revoked_at") else None,
                )
                self.player_access[str(item["token_hash"])] = record
        self.sessions = {}
        self.sessions_by_token = {}
        for item in payload.get("sessions", []):
            session = SessionRecord(
                id=UUID(str(item["id"])), token=str(item["token"]), field_id=UUID(str(item["field_id"])),
                camera_id=UUID(str(item["camera_id"])), sport_code=str(item["sport_code"]),
                started_at=datetime.fromisoformat(str(item["started_at"])),
                player_ids=[UUID(str(value)) for value in item.get("player_ids", [])],
                ended_at=datetime.fromisoformat(str(item["ended_at"])) if item.get("ended_at") else None,
                started_by=str(item.get("started_by", "player")),
            )
            self.sessions[session.id] = session
            self.sessions_by_token[session.token] = session.id
        self.consents = {
            UUID(str(item["id"])): ConsentRecord(
                UUID(str(item["id"])), UUID(str(item["player_id"])), UUID(str(item["session_id"])),
                bool(item["recording_consent"]), bool(item["messaging_consent"]), str(item["policy_version"]),
                datetime.fromisoformat(str(item["captured_at"])),
            )
            for item in payload.get("consents", [])
        }
        self.highlights = {
            UUID(str(item["id"])): HighlightRecord(
                UUID(str(item["id"])), UUID(str(item["event_id"])), UUID(str(item["session_id"])),
                datetime.fromisoformat(str(item["occurred_at"])), datetime.fromisoformat(str(item["window_start_at"])),
                datetime.fromisoformat(str(item["window_end_at"])), int(item["duration_seconds"]),
                item.get("source_storage_key"), item.get("storage_key"), str(item.get("status", "processing")),
                float(item["confidence"]) if item.get("confidence") is not None else None,
            )
            for item in payload.get("highlights", [])
        }
        self.recordings = {
            UUID(str(item["session_id"])): RecordingRecord(UUID(str(item["id"])), UUID(str(item["session_id"])), str(item["storage_key"]), str(item.get("status", "processing")))
            for item in payload.get("recordings", [])
        }
        self.recordings_by_key = {item.storage_key: item.id for item in self.recordings.values()}
        self.processing_jobs = {
            UUID(str(item["id"])): ProcessingJobRecord(
                UUID(str(item["id"])), str(item["job_type"]), UUID(str(item["resource_id"])), str(item["idempotency_key"]),
                str(item.get("status", "queued")), int(item.get("attempts", 0)), item.get("last_error"),
                datetime.fromisoformat(str(item["leased_at"])) if item.get("leased_at") else None,
            )
            for item in payload.get("processing_jobs", [])
        }
        self.processing_jobs_by_key = {item.idempotency_key: item.id for item in self.processing_jobs.values()}
        self.events_by_key = {
            str(key): (UUID(str(value[0])), UUID(str(value[1])))
            for key, value in dict(payload.get("events_by_key", {})).items()
        }
        self.idempotency = {str(key): UUID(str(value)) for key, value in dict(payload.get("idempotency", {})).items()}
        self.activity_events = [dict(item) for item in payload.get("activity_events", [])]

    def _activity(
        self,
        event_id: str,
        kind: str,
        status: str,
        title: str,
        detail: str,
        occurred_at: datetime,
        *,
        field_id: str | None = None,
        session_id: UUID | None = None,
        highlight_id: UUID | None = None,
        href: str | None = None,
    ) -> None:
        event = {
            "id": event_id,
            "kind": kind,
            "status": status,
            "title": title,
            "detail": detail,
            "occurred_at": occurred_at.isoformat(),
            "field_id": field_id,
            "session_id": str(session_id) if session_id else None,
            "highlight_id": str(highlight_id) if highlight_id else None,
            "href": href,
        }
        self.activity_events = [item for item in self.activity_events if item.get("id") != event_id]
        self.activity_events.insert(0, event)
        self.activity_events = self.activity_events[:1000]

    def _session_field(self, session: SessionRecord) -> tuple[str, str]:
        field_id = self._field_slug(session.field_id)
        field = next((item for item in self.fields if item["id"] == field_id), None)
        return field_id, str(field["name"]) if field else "Cancha"

    def field_context(self, field_token: str):
        field = next((item for item in self.fields if item["field_token"] == field_token), None)
        if field is None:
            raise HTTPException(status_code=404, detail="QR de cancha no encontrado")
        field_id = FIELD_IDS.get(field_token, uuid5(NAMESPACE_URL, f"courtvision:field:{field_token}"))
        camera = next((item for item in self.cameras if item["field_id"] == field["id"]), None)
        camera_view = self._camera_view(camera) if camera else None
        camera_status = camera_view["status"] if camera_view and camera_view["status"] in {"live", "ready"} else "offline"
        active = self._active_session(field_id=field_id)
        recording_status = self._recording_status(active, camera)
        return {
            "field_id": field_id,
            "club_id": UUID(str(self.club["id"])),
            "venue_id": VENUE_ID if self._seed_demo else uuid5(NAMESPACE_URL, f"tveo:venue:{self.club['id']}"),
            "camera_id": CAMERA_IDS.get(camera["id"], uuid5(NAMESPACE_URL, f"courtvision:camera:{camera['id']}")) if camera else None,
            "club_name": self.club["name"] or "Tu club",
            "venue_name": f"{self.club['name'] or 'Tu club'} · {self.club['city'] or 'sin ciudad'}",
            "field_name": field["name"],
            "sport_code": field["sport_code"],
            "status": field["status"],
            "camera_status": camera_status,
            "active_session_id": active.id if active else None,
            "recording_status": recording_status,
        }

    def _field_view(self, field: dict[str, object]) -> dict[str, object]:
        camera = next((item for item in self.cameras if item["field_id"] == field["id"]), None)
        camera_view = self._camera_view(camera) if camera else None
        field_uuid = self._field_uuid(str(field["field_token"]))
        active = self._active_session(field_id=field_uuid)
        recording_status = self._recording_status(active, camera)
        return {
            **field,
            "camera_status": camera_view["status"] if camera_view else "offline",
            "last_seen": camera_view["last_seen"] if camera_view else "sin cámara",
            "camera": camera_view,
            "button": dict(self.buttons[field["id"]]) if field["id"] in self.buttons else None,
            "active_session_id": str(active.id) if active else None,
            "recording": {
                "status": recording_status,
                "session_id": str(active.id) if active else None,
                "started_at": active.started_at if active else None,
                "started_by": active.started_by if active else None,
            },
        }

    @staticmethod
    def _recording_status(active: SessionRecord | None, camera: dict[str, object] | None) -> str:
        acknowledged_session_id = str(camera.get("recording_session_id") or "") if camera else ""
        if active:
            return "recording" if acknowledged_session_id == str(active.id) else "starting"
        return "stopping" if acknowledged_session_id else "idle"

    @staticmethod
    def _field_uuid(field_token: str) -> UUID:
        return FIELD_IDS.get(field_token, uuid5(NAMESPACE_URL, f"courtvision:field:{field_token}"))

    def _active_session(self, *, field_id: UUID | None = None, camera_id: UUID | None = None) -> SessionRecord | None:
        self._expire_stale_sessions()
        return next(
            (
                session
                for session in self.sessions.values()
                if session.ended_at is None
                and (field_id is None or session.field_id == field_id)
                and (camera_id is None or session.camera_id == camera_id)
            ),
            None,
        )

    def _expire_stale_sessions(self, now: datetime | None = None) -> None:
        current_time = now or datetime.now(timezone.utc)
        changed = False
        for session in self.sessions.values():
            expires_at = session.started_at + MAX_SESSION_DURATION
            if session.ended_at is None and expires_at <= current_time:
                session.ended_at = expires_at
                field_id, field_name = self._session_field(session)
                self._activity(
                    f"session:{session.id}:ended", "recording", "info", "Grabación finalizada",
                    f"{field_name} · cierre automático después de una hora", expires_at,
                    field_id=field_id, session_id=session.id, href=f"/fields/{field_id}",
                )
                changed = True
        if changed:
            self._persist_runtime()

    @staticmethod
    def _camera_heartbeat_at(camera: dict[str, object]) -> datetime | None:
        value = camera.get("agent_last_seen_at") or camera.get("detector_last_frame_at")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @classmethod
    def _camera_view(cls, camera: dict[str, object]) -> dict[str, object]:
        view = dict(camera)
        view.setdefault("host", "")
        view.setdefault("rtsp_port", 554)
        view.setdefault("username", "")
        view.setdefault("stream_path", "")
        view.setdefault("detector_status", "idle")
        view.setdefault("detector_fps", 0.0)
        view.setdefault("detector_last_frame_at", None)
        heartbeat_at = cls._camera_heartbeat_at(camera)
        heartbeat_age = datetime.now(timezone.utc) - heartbeat_at if heartbeat_at else None
        if view.get("status") == "live" and heartbeat_age is not None and heartbeat_age > AGENT_HEARTBEAT_TIMEOUT:
            view["status"] = "offline"
        if heartbeat_age is not None:
            seconds = max(0, int(heartbeat_age.total_seconds()))
            if seconds < 10:
                view["last_seen"] = "ahora"
            elif seconds < 60:
                view["last_seen"] = f"hace {seconds} s"
            elif seconds < 3600:
                view["last_seen"] = f"hace {seconds // 60} min"
            else:
                view["last_seen"] = f"hace {seconds // 3600} h"
        token_hash = str(view.get("agent_token_hash") or "")
        view["agent_linked"] = bool(
            view.get("agent_accepted_at")
            or (token_hash and token_hash != "revoked" and camera.get("status") == "live")
        )
        view["password_configured"] = bool(view.get("password"))
        view.pop("password", None)
        view.pop("agent_token_hash", None)
        return view

    def owner_clubs(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            return []
        return [{"id": self.club["id"], "name": self.club["name"], "status": "active", "city": self.club["city"], "logo_data_url": self.club.get("logo_data_url", ""), "fields_count": self.club["fields_count"]}]

    def update_owner_club(self, owner_id: str, payload: dict[str, object]) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Club no encontrado")
        for key, value in payload.items():
            if value is not None:
                self.club[key] = value
        self._persist_configuration()
        return dict(self.club)

    def owner_fields(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            return []
        return [self._field_view(item) for item in self.fields]

    def create_owner_field(
        self,
        owner_id: str,
        name: str,
        sport_code: str,
        detection_mode: str,
        camera_name: str | None = None,
        camera_serial_number: str | None = None,
        camera_host: str | None = None,
        camera_rtsp_port: int = 554,
        camera_username: str | None = None,
        camera_password: str | None = None,
        camera_stream_path: str | None = None,
    ) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Club no encontrado")
        resolved_camera_path = camera_stream_path or ("/stream1" if camera_name or camera_host else None)
        camera_values = (camera_name, camera_host, resolved_camera_path)
        if any(camera_values) and not all(camera_values):
            raise HTTPException(status_code=422, detail="Completá nombre, dirección IP y ruta RTSP de la cámara")
        if self._seed_demo:
            next_number = max([int(str(item["id"]).split("-")[-1]) for item in self.fields] or [0]) + 1
            field_id = f"field-{next_number:02d}"
            field_token = field_id
        else:
            suffix = uuid4().hex[:12]
            field_id = f"field-{suffix}"
            field_token = f"{self.profile['id'][:8]}-{suffix}"
        field = {"id": field_id, "name": name, "field_token": field_token, "sport_code": sport_code, "status": "active", "recording_enabled": True, "detection_mode": detection_mode, "qr_url": f"/qr?field={field_token}"}
        self.fields.append(field)
        if camera_name and camera_host and resolved_camera_path:
            self.cameras.append({
                "id": f"camera-{len(self.cameras) + 1:02d}" if self._seed_demo else f"camera-{uuid4().hex[:12]}",
                "field_id": field["id"],
                "name": camera_name,
                "serial_number": camera_serial_number or "",
                "stream_url": f"rtsp://{camera_host}:{camera_rtsp_port}{resolved_camera_path}",
                "host": camera_host,
                "rtsp_port": camera_rtsp_port,
                "username": camera_username or "",
                "password": camera_password or "",
                "stream_path": resolved_camera_path,
                "status": "ready",
                "last_seen": "recién cargada",
            })
        self.club["fields_count"] = len(self.fields)
        self._persist_configuration()
        return self._field_view(field)

    def update_owner_field(self, owner_id: str, field_id: str, payload: dict[str, object]) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        field = next((item for item in self.fields if item["id"] == field_id), None)
        if field is None:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        for key, value in payload.items():
            if key != "recording_enabled" and value is not None:
                field[key] = value
        field["recording_enabled"] = True
        self._persist_configuration()
        return self._field_view(field)

    def delete_owner_field(self, owner_id: str, field_id: str) -> None:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        field = next((item for item in self.fields if item["id"] == field_id), None)
        if field is None:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        self.fields.remove(field)
        self.cameras = [camera for camera in self.cameras if camera["field_id"] != field_id]
        self.buttons.pop(field_id, None)
        self.button_secrets.pop(field_id, None)
        self.club["fields_count"] = len(self.fields)
        self._persist_configuration()

    def update_owner_button(self, owner_id: str, field_id: str, device_id: str, secret: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        if not any(field["id"] == field_id for field in self.fields):
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        if len(device_id.strip()) < 2 or len(secret.strip()) < 8:
            raise HTTPException(status_code=422, detail="El dispositivo y la clave son obligatorios")
        self.buttons[field_id] = {"device_id": device_id.strip(), "label": "Botón de highlights", "status": "ready", "last_seen": "sin conexión"}
        self.button_secrets[field_id] = secret.strip()
        field = next(item for item in self.fields if item["id"] == field_id)
        self._persist_configuration()
        return self._field_view(field)

    def owner_cameras(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            return []
        return [self._camera_view(camera) for camera in self.cameras]

    def set_camera_agent_token(self, owner_id: str, camera_id: str, token: str) -> None:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera["agent_token_hash"] = token_fingerprint(token)
        camera["agent_accepted_at"] = None
        self._persist_configuration()

    def accept_camera_agent_token(self, camera_id: str, token: str) -> bool:
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            return False
        fingerprint = token_fingerprint(token)
        active = str(camera.get("agent_token_hash") or "")
        if active == "revoked":
            return False
        if active:
            accepted = hmac.compare_digest(active, fingerprint)
            if accepted and not camera.get("agent_accepted_at"):
                camera["agent_accepted_at"] = datetime.now(timezone.utc).isoformat()
                self._persist_configuration()
            return accepted
        camera["agent_token_hash"] = fingerprint
        camera["agent_accepted_at"] = datetime.now(timezone.utc).isoformat()
        self._persist_configuration()
        return True

    def revoke_camera_agent_token(self, owner_id: str, camera_id: str) -> None:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera["agent_token_hash"] = "revoked"
        camera["agent_accepted_at"] = None
        camera["agent_last_seen_at"] = None
        camera["status"] = "ready"
        camera["last_seen"] = "desvinculada"
        self._persist_configuration()

    def agent_camera_config(self, camera_id: str) -> dict[str, object]:
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        field = next((item for item in self.fields if item["id"] == camera["field_id"]), None)
        if field is None:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        camera_uuid = CAMERA_IDS.get(camera_id, uuid5(NAMESPACE_URL, f"courtvision:camera:{camera_id}"))
        active = self._active_session(camera_id=camera_uuid)
        return {
            "camera_id": camera["id"],
            "field_id": field["id"],
            "field_name": field["name"],
            "stream_url": camera.get("stream_url", ""),
            "host": camera.get("host", ""),
            "rtsp_port": camera.get("rtsp_port", 554),
            "username": camera.get("username", ""),
            "password": camera.get("password", ""),
            "stream_path": camera.get("stream_path", ""),
            "detection_mode": field.get("detection_mode", "arms_up"),
            "recording_enabled": True,
            "active_session_id": active.id if active else None,
        }

    def assert_agent_session(self, camera_id: str, session_id: UUID) -> None:
        """Reject cross-camera access while preserving the explicit local-dev agent."""
        if not camera_id:
            return
        session = self.sessions.get(session_id)
        expected_camera_id = CAMERA_IDS.get(camera_id, uuid5(NAMESPACE_URL, f"courtvision:camera:{camera_id}"))
        if session is None or session.camera_id != expected_camera_id:
            raise HTTPException(status_code=403, detail="La sesión no pertenece a esta cámara")

    def assert_agent_storage_path(self, camera_id: str, storage_path: str) -> None:
        if not camera_id:
            return
        parts = storage_path.split("/")
        if len(parts) < 4 or parts[0] != "sessions":
            raise HTTPException(status_code=403, detail="El archivo no pertenece a esta cámara")
        try:
            session_id = UUID(parts[1])
        except ValueError:
            raise HTTPException(status_code=403, detail="El archivo no pertenece a esta cámara") from None
        self.assert_agent_session(camera_id, session_id)

    def create_owner_camera(self, owner_id: str, field_id: str, name: str, serial_number: str | None, stream_url: str | None, host: str | None = None, rtsp_port: int = 554, username: str | None = None, password: str | None = None, stream_path: str | None = None) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        if not any(field["id"] == field_id for field in self.fields):
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        if any(camera["field_id"] == field_id for camera in self.cameras):
            raise HTTPException(status_code=409, detail="Esta cancha ya tiene una cámara asignada")
        resolved_stream_path = stream_path or ("/stream1" if host else "")
        camera_id = f"camera-{len(self.cameras) + 1:02d}" if self._seed_demo else f"camera-{uuid4().hex[:12]}"
        camera = {"id": camera_id, "field_id": field_id, "name": name, "serial_number": serial_number or "", "stream_url": stream_url or (f"rtsp://{host}:{rtsp_port}{resolved_stream_path}" if host and resolved_stream_path else ""), "host": host or "", "rtsp_port": rtsp_port, "username": username or "", "password": password or "", "stream_path": resolved_stream_path, "status": "ready", "last_seen": "recién cargada"}
        self.cameras.append(camera)
        self._persist_configuration()
        return self._camera_view(camera)

    def update_owner_camera(self, owner_id: str, camera_id: str, payload: dict[str, object]) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        if any(key in payload for key in ("host", "rtsp_port", "stream_path")):
            next_host = str(payload.get("host", camera.get("host", "")) or "").strip()
            next_path = str(payload.get("stream_path", camera.get("stream_path", "")) or "").strip()
            if next_host and not next_path:
                raise HTTPException(status_code=422, detail="La ruta RTSP es obligatoria cuando se configura la dirección de la cámara")
            if next_path and not next_host:
                raise HTTPException(status_code=422, detail="La dirección IP o hostname es obligatoria cuando se configura la ruta RTSP")
        for key, value in payload.items():
            if value is not None:
                camera[key] = value
        if camera.get("host") and camera.get("stream_path"):
            camera["stream_url"] = f"rtsp://{camera['host']}:{camera.get('rtsp_port', 554)}{camera['stream_path']}"
        self._persist_configuration()
        return self._camera_view(camera)

    def delete_owner_camera(self, owner_id: str, camera_id: str) -> None:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        camera = next((item for item in self.cameras if item["id"] == camera_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        self.cameras.remove(camera)
        self._persist_configuration()

    def record_agent_heartbeat(
        self,
        device_id: str,
        camera_status: str,
        observed_at: datetime,
        active_session_id: UUID | None = None,
        detector_status: str | None = None,
        detector_fps: float | None = None,
        detector_last_frame_at: datetime | None = None,
    ) -> None:
        camera = next((item for item in self.cameras if item["id"] == device_id or item["serial_number"] == device_id), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        previous_status = camera.get("status")
        previous_detector_status = camera.get("detector_status")
        received_at = datetime.now(timezone.utc)
        camera["status"] = {"online": "live", "degraded": "ready", "offline": "offline"}[camera_status]
        camera["last_seen"] = "ahora" if camera_status != "offline" else "sin señal"
        camera["agent_last_seen_at"] = received_at.isoformat()
        camera["agent_accepted_at"] = camera.get("agent_accepted_at") or received_at.isoformat()
        camera["recording_session_id"] = str(active_session_id) if active_session_id else None
        if detector_status is not None:
            camera["detector_status"] = detector_status
        if detector_fps is not None:
            camera["detector_fps"] = round(detector_fps, 2)
        if detector_last_frame_at is not None:
            camera["detector_last_frame_at"] = detector_last_frame_at.isoformat()
        self._persist_configuration()
        if camera["status"] != previous_status:
            field_id = str(camera["field_id"])
            field = next((item for item in self.fields if item["id"] == field_id), None)
            field_name = str(field["name"]) if field else "Cancha"
            online = camera["status"] == "live"
            self._activity(
                f"camera:{camera['id']}:{observed_at.isoformat()}", "camera", "success" if online else "error" if camera["status"] == "offline" else "warning",
                "Cámara conectada" if online else "Cámara sin señal" if camera["status"] == "offline" else "Señal de cámara degradada",
                f"{field_name} · {camera['name']}", observed_at, field_id=field_id, href=f"/fields/{field_id}",
            )
            self._persist_runtime()
        detector_unhealthy = camera.get("detector_status") in {"degraded", "error", "unavailable"}
        detector_recovered = previous_detector_status in {"degraded", "error", "unavailable"} and camera.get("detector_status") == "running"
        if camera.get("detector_status") != previous_detector_status and (detector_unhealthy or detector_recovered):
            field_id = str(camera["field_id"])
            field = next((item for item in self.fields if item["id"] == field_id), None)
            field_name = str(field["name"]) if field else "Cancha"
            self._activity(
                f"detector:{camera['id']}:{observed_at.isoformat()}", "camera", "success" if detector_recovered else "warning",
                "Detector recuperado" if detector_recovered else "Detector necesita atención",
                f"{field_name} · {camera.get('detector_fps', 0):.1f} FPS", observed_at,
                field_id=field_id, href=f"/fields/{field_id}",
            )
            self._persist_runtime()

    def start_owner_recording(self, owner_id: str, field_id: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        field_record = next((item for item in self.fields if item["id"] == field_id), None)
        if field_record is None:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        if field_record["status"] != "active":
            raise HTTPException(status_code=409, detail="La cancha no está disponible para iniciar un partido")
        camera = next((item for item in self.cameras if item["field_id"] == field_id), None)
        if camera is None or self._camera_view(camera).get("status") == "offline":
            raise HTTPException(status_code=409, detail="La cancha necesita una cámara disponible")
        field_uuid = self._field_uuid(str(field_record["field_token"]))
        active = self._active_session(field_id=field_uuid)
        if active is None:
            camera_uuid = CAMERA_IDS.get(str(camera["id"]), uuid5(NAMESPACE_URL, f"courtvision:camera:{camera['id']}"))
            active = SessionRecord(
                id=uuid4(),
                token=token_urlsafe(24),
                field_id=field_uuid,
                camera_id=camera_uuid,
                sport_code=str(field_record["sport_code"]),
                started_at=datetime.now(timezone.utc),
                started_by="owner",
            )
            self.sessions[active.id] = active
            self.sessions_by_token[active.token] = active.id
            self._activity(
                f"session:{active.id}:started", "recording", "success", "Grabación iniciada",
                f"{field_record['name']} · iniciada desde el dashboard", active.started_at,
                field_id=field_id, session_id=active.id, href=f"/fields/{field_id}",
            )
        self._persist_runtime()
        return self._field_view(field_record)

    def stop_owner_recording(self, owner_id: str, field_id: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        field_record = next((item for item in self.fields if item["id"] == field_id), None)
        if field_record is None:
            raise HTTPException(status_code=404, detail="Cancha no encontrada")
        active = self._active_session(field_id=self._field_uuid(str(field_record["field_token"])))
        if active:
            active.ended_at = datetime.now(timezone.utc)
            self._activity(
                f"session:{active.id}:ended", "recording", "info", "Grabación finalizada",
                f"{field_record['name']} · detenida desde el dashboard", active.ended_at,
                field_id=field_id, session_id=active.id, href=f"/fields/{field_id}",
            )
            self._persist_runtime()
        return self._field_view(field_record)

    def owner_profile(self, owner_id: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        return dict(self.profile)

    def update_owner_profile(self, owner_id: str, payload: dict[str, object]) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        for key, value in payload.items():
            if value is not None:
                self.profile[key] = value
        return dict(self.profile)

    def owner_notifications(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            return []
        return [dict(item) for item in self.notifications]

    def owner_activity(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            return []
        self._expire_stale_sessions()
        events = {str(item["id"]): dict(item) for item in self.activity_events}
        for session in self.sessions.values():
            field_id, field_name = self._session_field(session)
            origin = "QR del jugador" if session.started_by == "player" else "dashboard"
            events.setdefault(f"session:{session.id}:started", {
                "id": f"session:{session.id}:started", "kind": "recording", "status": "success",
                "title": "Grabación iniciada", "detail": f"{field_name} · iniciada desde el {origin}",
                "occurred_at": session.started_at.isoformat(), "field_id": field_id, "session_id": str(session.id),
                "highlight_id": None, "href": f"/fields/{field_id}",
            })
            if session.ended_at:
                events.setdefault(f"session:{session.id}:ended", {
                    "id": f"session:{session.id}:ended", "kind": "recording", "status": "info",
                    "title": "Grabación finalizada", "detail": field_name,
                    "occurred_at": session.ended_at.isoformat(), "field_id": field_id, "session_id": str(session.id),
                    "highlight_id": None, "href": f"/fields/{field_id}",
                })
        for highlight in self.highlights.values():
            session = self.sessions.get(highlight.session_id)
            if session is None:
                continue
            field_id, field_name = self._session_field(session)
            events.setdefault(f"highlight:{highlight.id}:registered", {
                "id": f"highlight:{highlight.id}:registered", "kind": "highlight",
                "status": "error" if highlight.status == "failed" else "success" if highlight.status == "available" else "info",
                "title": "Highlight registrado", "detail": f"{field_name} · {highlight.duration_seconds} segundos",
                "occurred_at": highlight.occurred_at.isoformat(), "field_id": field_id, "session_id": str(session.id),
                "highlight_id": str(highlight.id), "href": f"/library?highlight={highlight.id}",
            })
        return sorted(events.values(), key=lambda item: str(item.get("occurred_at", "")), reverse=True)

    def mark_notification_read(self, owner_id: str, notification_id: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        notification = next((item for item in self.notifications if item["id"] == notification_id), None)
        if notification is None:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
        notification["read"] = True
        self._persist_configuration()
        return dict(notification)

    def mark_all_notifications_read(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Notificaciones no encontradas")
        for notification in self.notifications:
            notification["read"] = True
        self._persist_configuration()
        return [dict(notification) for notification in self.notifications]

    def delete_all_notifications(self, owner_id: str) -> None:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Notificaciones no encontradas")
        self.notifications.clear()
        self._persist_configuration()

    def owner_dashboard(self, owner_id: str) -> dict[str, object]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Club no encontrado")
        cameras = [
            {"id": field["id"], "field_name": field["name"], "status": self._field_view(field)["camera_status"], "last_seen": self._field_view(field)["last_seen"]}
            for field in self.fields
        ]
        recent_highlights = []
        for highlight in sorted(self.highlights.values(), key=lambda item: item.occurred_at, reverse=True)[:10]:
            session = self.sessions.get(highlight.session_id)
            field_name = "Cancha asociada" if session else "Cancha"
            recent_highlights.append({"id": f"#CV-{str(highlight.id)[:4].upper()}", "title": "Momento detectado", "field_name": field_name, "status": highlight.status, "occurred_at": highlight.occurred_at.strftime("%H:%M:%S")})
        return {
            "owner": dict(self.profile),
            "club": dict(self.club),
            "cameras": cameras,
            "metrics": {"highlights": str(len(self.highlights)), "players": str(len(self.players)), "delivery_rate": "—", "active_sessions": str(sum(session.ended_at is None for session in self.sessions.values())), "capacity": str(len(self.fields))},
            "recent_highlights": recent_highlights,
        }

    def owner_highlights(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Momentos no encontrados")
        items: list[dict[str, object]] = []
        for highlight in sorted(self.highlights.values(), key=lambda item: item.occurred_at, reverse=True):
            session = self.sessions.get(highlight.session_id)
            if session is None:
                continue
            field_id = self._field_slug(session.field_id)
            field = next((item for item in self.fields if item["id"] == field_id), None)
            players = [
                self.players[player_id].display_name
                for player_id in session.player_ids
                if player_id in self.players
            ]
            items.append({
                "id": str(highlight.id),
                "display_id": f"#CV-{str(highlight.id)[:4].upper()}",
                "title": "Momento destacado",
                "field_id": field_id,
                "field_name": str(field["name"]) if field else "Cancha",
                "session_id": str(session.id),
                "session_code": str(session.id)[:8].upper(),
                "session_started_at": session.started_at.isoformat(),
                "players": players,
                "occurred_at": highlight.occurred_at.isoformat(),
                "duration_seconds": highlight.duration_seconds,
                "status": highlight.status,
                "confidence": highlight.confidence,
                "media_available": highlight.status == "available" and bool(highlight.storage_key),
            })
        return items

    def owner_recordings(self, owner_id: str) -> list[dict[str, object]]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Partidos no encontrados")
        items: list[dict[str, object]] = []
        for recording in self.recordings.values():
            session = self.sessions.get(recording.session_id)
            if session is None or self._full_recording_expired(session):
                continue
            field_id = self._field_slug(session.field_id)
            field = next((item for item in self.fields if item["id"] == field_id), None)
            if field is None:
                continue
            ended_at = session.ended_at
            duration_seconds = max(0, int(((ended_at or datetime.now(timezone.utc)) - session.started_at).total_seconds()))
            players = [
                self.players[player_id].display_name
                for player_id in session.player_ids
                if player_id in self.players
            ]
            items.append({
                "id": str(recording.id),
                "display_id": f"#PT-{str(recording.id)[:4].upper()}",
                "title": "Partido completo",
                "field_id": field_id,
                "field_name": str(field["name"]),
                "session_id": str(session.id),
                "session_code": str(session.id)[:8].upper(),
                "session_started_at": session.started_at.isoformat(),
                "players": players,
                "occurred_at": session.started_at.isoformat(),
                "ended_at": ended_at.isoformat() if ended_at else None,
                "expires_at": (ended_at + FULL_RECORDING_RETENTION).isoformat() if ended_at else None,
                "duration_seconds": duration_seconds,
                "status": recording.status,
                "media_available": recording.status == "available" and bool(recording.storage_key),
            })
        return sorted(items, key=lambda item: str(item["occurred_at"]), reverse=True)

    def _owner_recording(self, owner_id: str, recording_id: UUID) -> tuple[UUID, RecordingRecord, SessionRecord]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        found = next(((session_id, item) for session_id, item in self.recordings.items() if item.id == recording_id), None)
        if found is None:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        session_id, recording = found
        session = self.sessions.get(session_id)
        if session is None or not any(item["id"] == self._field_slug(session.field_id) for item in self.fields):
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        return session_id, recording, session

    def reconcile_owner_recordings(self, owner_id: str, object_exists) -> None:
        """Recover uploads that reached durable storage before their final acknowledgement."""
        changed = False
        for recording in self.recordings.values():
            if recording.status == "processing" and object_exists(recording.storage_key):
                recording.status = "available"
                session = self.sessions.get(recording.session_id)
                if session:
                    field_id, field_name = self._session_field(session)
                    self._activity(
                        f"recording:{recording.id}:available", "recording", "success", "Partido disponible",
                        f"{field_name} · el video completo terminó de subirse", datetime.now(timezone.utc),
                        field_id=field_id, session_id=session.id, href=f"/library?recording={recording.id}",
                    )
                changed = True
        if changed:
            self._persist_runtime()

    def resolve_owner_recording_media(self, owner_id: str, recording_id: UUID) -> str:
        _, recording, session = self._owner_recording(owner_id, recording_id)
        if self._full_recording_expired(session):
            raise HTTPException(status_code=410, detail="Este partido completo venció después de 48 horas")
        if recording.status != "available" or not recording.storage_key:
            raise HTTPException(status_code=404, detail="Partido todavía no disponible")
        return recording.storage_key

    @staticmethod
    def _full_recording_expired(session: SessionRecord, now: datetime | None = None) -> bool:
        return bool(
            session.ended_at
            and session.ended_at + FULL_RECORDING_RETENTION <= (now or datetime.now(timezone.utc))
        )

    def purge_expired_recordings(self, delete_object, now: datetime | None = None) -> int:
        """Delete complete-match media after 48 hours while retaining its highlights."""
        current_time = now or datetime.now(timezone.utc)
        deleted = 0
        for session_id, recording in list(self.recordings.items()):
            session = self.sessions.get(session_id)
            if session is None or recording.status != "available" or not self._full_recording_expired(session, current_time):
                continue
            try:
                if recording.storage_key:
                    delete_object(recording.storage_key)
            except Exception:
                continue
            self.recordings.pop(session_id, None)
            self.recordings_by_key.pop(recording.storage_key, None)
            field_id, field_name = self._session_field(session)
            self._activity(
                f"recording:{recording.id}:expired", "recording", "info", "Partido eliminado automáticamente",
                f"{field_name} · finalizó su disponibilidad de 48 horas", current_time,
                field_id=field_id, session_id=session.id,
            )
            deleted += 1
        if deleted:
            self._persist_runtime()
        return deleted

    def owner_recording_storage_keys(self, owner_id: str, recording_id: UUID) -> list[str]:
        _, recording, _ = self._owner_recording(owner_id, recording_id)
        if recording.status == "processing":
            raise HTTPException(status_code=409, detail="Esperá a que el partido termine de subirse para eliminarlo")
        return [recording.storage_key] if recording.storage_key else []

    def delete_owner_recording(self, owner_id: str, recording_id: UUID) -> None:
        session_id, recording, session = self._owner_recording(owner_id, recording_id)
        self.recordings.pop(session_id, None)
        self.recordings_by_key.pop(recording.storage_key, None)
        field_id, field_name = self._session_field(session)
        self._activity(
            f"recording:{recording_id}:deleted", "recording", "warning", "Partido eliminado",
            f"{field_name} · se liberó el archivo del almacenamiento", datetime.now(timezone.utc),
            field_id=field_id, session_id=session.id,
        )
        self._persist_runtime()

    def resolve_owner_highlight_media(self, owner_id: str, highlight_id: UUID) -> str:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Momento no encontrado")
        highlight = self.highlights.get(highlight_id)
        if highlight is None or highlight.status != "available" or not highlight.storage_key:
            raise HTTPException(status_code=404, detail="Video no disponible")
        session = self.sessions.get(highlight.session_id)
        if session is None or not any(item["id"] == self._field_slug(session.field_id) for item in self.fields):
            raise HTTPException(status_code=404, detail="Momento no encontrado")
        return highlight.storage_key

    def owner_highlight_storage_keys(self, owner_id: str, highlight_id: UUID) -> list[str]:
        if owner_id != self.profile["id"]:
            raise HTTPException(status_code=404, detail="Momento no encontrado")
        highlight = self.highlights.get(highlight_id)
        if highlight is None:
            raise HTTPException(status_code=404, detail="Momento no encontrado")
        session = self.sessions.get(highlight.session_id)
        if session is None or not any(item["id"] == self._field_slug(session.field_id) for item in self.fields):
            raise HTTPException(status_code=404, detail="Momento no encontrado")
        if highlight.status == "processing":
            raise HTTPException(status_code=409, detail="Esperá a que el video termine de procesarse para eliminarlo")
        return list(dict.fromkeys(key for key in (highlight.storage_key, highlight.source_storage_key) if key))

    def delete_owner_highlight(self, owner_id: str, highlight_id: UUID) -> None:
        self.owner_highlight_storage_keys(owner_id, highlight_id)
        highlight = self.highlights.pop(highlight_id)
        session = self.sessions.get(highlight.session_id)
        if session:
            field_id, field_name = self._session_field(session)
            self._activity(
                f"highlight:{highlight_id}:deleted", "highlight", "warning", "Highlight eliminado",
                f"{field_name} · se liberó el archivo del almacenamiento", datetime.now(timezone.utc),
                field_id=field_id, session_id=session.id,
            )
        job_ids = [job_id for job_id, job in self.processing_jobs.items() if job.resource_id == highlight_id]
        for job_id in job_ids:
            job = self.processing_jobs.pop(job_id)
            self.processing_jobs_by_key.pop(job.idempotency_key, None)
        for key, value in list(self.events_by_key.items()):
            if value[0] == highlight.event_id or value[1] == highlight_id:
                self.events_by_key.pop(key, None)
        self._persist_runtime()

    def start_session(self, field_token: str, request: StartSessionRequest, idem_key: str):
        context = self.field_context(field_token)
        if idem_key in self.idempotency:
            session = self.sessions[self.idempotency[idem_key]]
            player_id = session.player_ids[0] if session.player_ids else None
            player = self.players.get(player_id)
            access_token = self._register_player_access(session, player) if player else None
            return session, player, access_token
        if context["status"] != "active":
            raise HTTPException(status_code=409, detail="Esta cancha no está disponible para iniciar un partido")
        if context["camera_id"] is None or context["camera_status"] == "offline":
            raise HTTPException(status_code=409, detail="Esta cancha no tiene una cámara disponible")

        now = datetime.now(timezone.utc)
        player = PlayerRecord(uuid4(), request.display_name, request.phone_e164, request.messaging_consent)
        active = self._active_session(field_id=context["field_id"])
        if active is not None and active.started_by == "owner" and not active.player_ids:
            session = active
        else:
            if active is not None:
                active.ended_at = now
                old_field_id, old_field_name = self._session_field(active)
                self._activity(
                    f"session:{active.id}:ended", "recording", "info", "Grabación finalizada",
                    f"{old_field_name} · comenzó un nuevo partido", now,
                    field_id=old_field_id, session_id=active.id, href=f"/fields/{old_field_id}",
                )
            session = SessionRecord(uuid4(), token_urlsafe(24), context["field_id"], context["camera_id"], context["sport_code"], now, [], None, "player")
        session.player_ids.append(player.id)
        self.players[player.id] = player
        access_token = self._register_player_access(session, player)
        consent = ConsentRecord(uuid4(), player.id, session.id, request.recording_consent, request.messaging_consent, request.policy_version, now)
        self.consents[consent.id] = consent
        self.sessions[session.id] = session
        self.sessions_by_token[session.token] = session.id
        self.idempotency[idem_key] = session.id
        field_id = self._field_slug(session.field_id)
        if session.started_at == now:
            self._activity(
                f"session:{session.id}:started", "recording", "success", "Grabación iniciada",
                f"{context['field_name']} · iniciada desde el QR", now,
                field_id=field_id, session_id=session.id, href=f"/fields/{field_id}",
            )
        self._activity(
            f"player:{player.id}:registered", "player", "info", "Jugador registrado",
            f"{request.display_name} · {context['field_name']}", now,
            field_id=field_id, session_id=session.id, href=f"/fields/{field_id}",
        )
        self._persist_runtime()
        return session, player, access_token

    def join_session(self, session_token: str, request: StartSessionRequest, idem_key: str):
        if session_token not in self.sessions_by_token:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        if idem_key in self.idempotency:
            player_id = self.idempotency[idem_key]
            session_id = self.sessions_by_token[session_token]
            session = self.sessions[session_id]
            player = self.players[player_id]
            return session, player, self._register_player_access(session, player)
        session = self.sessions[self.sessions_by_token[session_token]]
        player = PlayerRecord(uuid4(), request.display_name, request.phone_e164, request.messaging_consent)
        self.players[player.id] = player
        access_token = self._register_player_access(session, player)
        session.player_ids.append(player.id)
        consent = ConsentRecord(uuid4(), player.id, session.id, request.recording_consent, request.messaging_consent, request.policy_version, datetime.now(timezone.utc))
        self.consents[consent.id] = consent
        self.idempotency[idem_key] = player.id
        field_id, field_name = self._session_field(session)
        self._activity(
            f"player:{player.id}:registered", "player", "info", "Jugador registrado",
            f"{request.display_name} · {field_name}", consent.captured_at,
            field_id=field_id, session_id=session.id, href=f"/fields/{field_id}",
        )
        self._persist_runtime()
        return session, player, access_token

    @staticmethod
    def _access_hash(access_token: str) -> str:
        return hashlib.sha256(access_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _access_secret() -> bytes:
        return os.getenv("PLAYER_ACCESS_SIGNING_SECRET", "courtvision-player-access-development-secret").encode("utf-8")

    def _encode_access_token(self, access: PlayerAccessRecord) -> str:
        payload = {
            "grant": str(access.grant_id),
            "session": str(access.session_id),
            "player": str(access.player_id),
            "exp": int(access.expires_at.timestamp()),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
        signature = hmac.new(self._access_secret(), encoded.encode(), hashlib.sha256).hexdigest()
        return f"pa.{encoded}.{signature}"

    def _register_player_access(self, session: SessionRecord, player: PlayerRecord) -> str:
        now = datetime.now(timezone.utc)
        access = next((
            value for value in self.player_access.values()
            if value.session_id == session.id and value.player_id == player.id
            and value.revoked_at is None and value.expires_at > now
        ), None)
        if access is None:
            access = PlayerAccessRecord(uuid4(), session.id, player.id, now + PLAYER_ACCESS_TTL)
        access_token = self._encode_access_token(access)
        self.player_access[self._access_hash(access_token)] = access
        return access_token

    def _resolve_player_access(self, access_token: str) -> PlayerAccessRecord:
        access = self.player_access.get(self._access_hash(access_token))
        if access is None:
            raise HTTPException(status_code=404, detail="Acceso privado no encontrado")
        now = datetime.now(timezone.utc)
        if access.revoked_at is not None or access.expires_at <= now:
            raise HTTPException(status_code=410, detail="Este enlace privado venció o fue revocado")
        return access

    def revoke_session_player_access(self, owner_id: str, session_id: UUID) -> int:
        if owner_id != self.profile["id"] or session_id not in self.sessions:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        revoked_at = datetime.now(timezone.utc)
        count = 0
        for access in {value.grant_id: value for value in self.player_access.values()}.values():
            if access.session_id == session_id and access.revoked_at is None:
                access.revoked_at = revoked_at
                count += 1
        if count:
            self._activity(
                f"session:{session_id}:access-revoked", "player", "warning", "Accesos privados revocados",
                f"{count} enlace(s) dejaron de funcionar", revoked_at, session_id=session_id,
            )
            self._persist_runtime()
        return count

    def player_media_page(self, access_token: str) -> dict[str, object]:
        access = self._resolve_player_access(access_token)
        session_id, player_id = access.session_id, access.player_id
        session = self.sessions.get(session_id)
        player = self.players.get(player_id)
        if session is None or player is None:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        field = next((item for item in self.fields if item["id"] == self._field_slug(session.field_id)), None)
        field_name = str(field["name"]) if field else "Cancha"
        recording = self.recordings.get(session.id)
        recording_expired = self._full_recording_expired(session)
        if recording_expired:
            recording_status = "expired"
        elif recording and recording.status == "available":
            recording_status = "available"
        elif session.ended_at is None:
            recording_status = "in_progress"
        else:
            recording_status = "processing"
        highlights = []
        for highlight in sorted(self.highlights.values(), key=lambda item: item.occurred_at, reverse=True):
            if highlight.session_id != session.id:
                continue
            highlights.append({
                "id": highlight.id,
                "title": "Momento destacado",
                "occurred_at": highlight.occurred_at,
                "duration_seconds": highlight.duration_seconds,
                "status": highlight.status,
                "media_path": f"/public/access/{access_token}/highlights/{highlight.id}" if highlight.status == "available" and highlight.storage_key else None,
            })
        return {
            "session_id": session.id,
            "player_name": player.display_name,
            "club_name": self.club["name"] or "Tu club",
            "field_name": field_name,
            "sport_code": session.sport_code,
            "started_at": session.started_at,
            "recording_status": recording_status,
            "recording_path": f"/public/access/{access_token}/recording" if recording and recording.status == "available" and not recording_expired else None,
            "recording_expires_at": session.ended_at + FULL_RECORDING_RETENTION if session.ended_at else None,
            "highlights": highlights,
        }

    def _field_slug(self, field_id: UUID) -> str:
        for token, known_id in FIELD_IDS.items():
            if known_id == field_id:
                return token if token != "demo-field-02" else "field-02"
        field = next((item for item in self.fields if uuid5(NAMESPACE_URL, f"courtvision:field:{item['field_token']}") == field_id), None)
        return str(field["id"]) if field else ""

    def resolve_player_media(self, access_token: str, highlight_id: UUID | None = None) -> tuple[SessionRecord, str]:
        access = self._resolve_player_access(access_token)
        session_id = access.session_id
        session = self.sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        if highlight_id is None:
            if self._full_recording_expired(session):
                raise HTTPException(status_code=410, detail="Este partido completo venció después de 48 horas")
            recording = self.recordings.get(session.id)
            if recording is None or recording.status != "available":
                raise HTTPException(status_code=404, detail="Partido completo todavía no disponible")
            return session, recording.storage_key
        highlight = self.highlights.get(highlight_id)
        if highlight is None or highlight.session_id != session.id or highlight.status != "available" or not highlight.storage_key:
            raise HTTPException(status_code=404, detail="Highlight todavía no disponible")
        return session, highlight.storage_key

    def register_media_upload(self, request: PresignUploadRequest) -> None:
        if request.media_type != "recording":
            return
        if request.session_id not in self.sessions:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        current = self.recordings.get(request.session_id)
        if current is None:
            recording = RecordingRecord(uuid4(), request.session_id, f"sessions/{request.session_id}/recording/{request.checksum}")
            self.recordings[request.session_id] = recording
            self.recordings_by_key[recording.storage_key] = recording.id
            self._persist_runtime()
        elif current.status == "processing":
            # A restarted finalization can produce a new checksum. Keep the
            # session pointed at the newest reservation so its completion can
            # never become an untracked S3 object.
            storage_key = f"sessions/{request.session_id}/recording/{request.checksum}"
            if current.storage_key != storage_key:
                self.recordings_by_key.pop(current.storage_key, None)
                current.storage_key = storage_key
                self.recordings_by_key[storage_key] = current.id
                self._persist_runtime()

    def mark_media_upload_available(self, storage_key: str) -> None:
        recording_id = self.recordings_by_key.get(storage_key)
        if recording_id is None:
            return
        for recording in self.recordings.values():
            if recording.id == recording_id:
                recording.status = "available"
                session = self.sessions.get(recording.session_id)
                if session:
                    field_id, field_name = self._session_field(session)
                    self._activity(
                        f"recording:{recording.id}:available", "recording", "success", "Partido disponible",
                        f"{field_name} · el video completo terminó de subirse", datetime.now(timezone.utc),
                        field_id=field_id, session_id=session.id, href=f"/fields/{field_id}",
                    )
                self._persist_runtime()
                return

    def create_event(self, session_id: UUID, request: CaptureEventRequest, idem_key: str):
        if session_id not in self.sessions:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        if idem_key in self.events_by_key:
            return self.events_by_key[idem_key]
        event_id, highlight_id = uuid4(), uuid4()
        requested_start = request.occurred_at - timedelta(seconds=30)
        window_start = max(requested_start, request.buffer_start_at) if request.buffer_start_at else requested_start
        window_end = min(request.occurred_at, request.buffer_end_at) if request.buffer_end_at else request.occurred_at
        duration_seconds = max(0, int((window_end - window_start).total_seconds()))
        self.events_by_key[idem_key] = (event_id, highlight_id)
        self.highlights[highlight_id] = HighlightRecord(
            highlight_id,
            event_id,
            session_id,
            request.occurred_at,
            window_start,
            window_end,
            duration_seconds,
            request.source_storage_key,
            confidence=request.confidence,
        )
        job_key = f"assemble_highlight:{highlight_id}"
        job = ProcessingJobRecord(uuid4(), "assemble_highlight", highlight_id, job_key)
        self.processing_jobs[job.id] = job
        self.processing_jobs_by_key[job_key] = job.id
        session = self.sessions[session_id]
        field_id, field_name = self._session_field(session)
        source_label = {
            "gesture": "gesto de brazos",
            "physical_button": "botón físico",
            "manual": "acción manual",
            "automatic_sport_event": "detección automática",
        }.get(request.event_type, "detección")
        self._activity(
            f"highlight:{highlight_id}:registered", "highlight", "info", "Highlight registrado",
            f"{field_name} · {source_label}", request.occurred_at,
            field_id=field_id, session_id=session_id, highlight_id=highlight_id,
            href=f"/library?highlight={highlight_id}",
        )
        self._persist_runtime()
        return event_id, highlight_id

    def lease_next_job(self) -> dict[str, object] | None:
        now = datetime.now(timezone.utc)
        recovered = False
        for item in self.processing_jobs.values():
            if item.status == "leased" and (
                item.leased_at is None or now - item.leased_at >= PROCESSING_LEASE_TIMEOUT
            ):
                item.status = "retryable"
                item.leased_at = None
                item.last_error = "El worker se interrumpió; reintentando automáticamente"
                recovered = True
        if recovered:
            self._persist_runtime()
        job = next((item for item in self.processing_jobs.values() if item.status in {"queued", "retryable"}), None)
        if job is None:
            return None
        highlight = self.highlights.get(job.resource_id)
        if highlight is None:
            job.status = "failed"
            job.last_error = "Highlight no encontrado"
            return None
        session = self.sessions.get(highlight.session_id)
        if session is None:
            job.status = "failed"
            job.last_error = "Sesión del highlight no encontrada"
            return None
        job.status = "leased"
        job.attempts += 1
        job.leased_at = now
        self._persist_runtime()
        return {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "resource_id": str(job.resource_id),
            "attempts": job.attempts,
            "source_storage_key": getattr(highlight, "source_storage_key", None),
            "duration_seconds": highlight.duration_seconds,
            "output_storage_key": f"highlights/{highlight.id}.mp4",
            "evolution_instance": owner_instance_name(str(self.profile["id"])),
            "delivery_recipients": [
                {
                    "phone_e164": self.players[player_id].phone_e164,
                    "display_name": self.players[player_id].display_name,
                    "access_token": self._register_player_access(session, self.players[player_id]),
                }
                for player_id in session.player_ids
                if player_id in self.players and self.players[player_id].messaging_consent
            ],
        }

    def complete_job(self, job_id: UUID, succeeded: bool, output_storage_key: str | None = None, error: str | None = None) -> None:
        job = self.processing_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        highlight = self.highlights.get(job.resource_id)
        if highlight is None:
            raise HTTPException(status_code=404, detail="Highlight no encontrado")
        if succeeded:
            job.status = "succeeded"
            job.last_error = None
            highlight.status = "available"
            if output_storage_key:
                highlight.storage_key = output_storage_key
        else:
            job.status = "retryable" if job.attempts < 3 else "dead_letter"
            job.last_error = error or "Procesamiento fallido"
            if job.status == "dead_letter":
                highlight.status = "failed"
        job.leased_at = None
        session = self.sessions.get(highlight.session_id)
        if session and (succeeded or job.status == "dead_letter"):
            field_id, field_name = self._session_field(session)
            self._activity(
                f"highlight:{highlight.id}:processed", "highlight", "success" if succeeded else "error",
                "Highlight disponible" if succeeded else "Falló el procesamiento del highlight",
                f"{field_name} · {str(highlight.id)[:8].upper()}" if succeeded else f"{field_name} · {job.last_error}",
                datetime.now(timezone.utc), field_id=field_id, session_id=session.id, highlight_id=highlight.id,
                href=f"/library?highlight={highlight.id}",
            )
        self._persist_runtime()

    def record_delivery(self, job_id: UUID, phone_e164: str, display_name: str, succeeded: bool, error: str | None = None) -> None:
        job = self.processing_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        highlight = self.highlights.get(job.resource_id)
        if highlight is None:
            raise HTTPException(status_code=404, detail="Highlight no encontrado")
        session = self.sessions.get(highlight.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        field_id, field_name = self._session_field(session)
        recipient_key = str(uuid5(NAMESPACE_URL, f"courtvision:delivery:{highlight.id}:{phone_e164}"))
        self._activity(
            f"delivery:{recipient_key}", "delivery", "success" if succeeded else "error",
            "Highlight enviado por WhatsApp" if succeeded else "Falló el envío por WhatsApp",
            f"{display_name} · {field_name}" if succeeded else f"{display_name} · {error or 'Evolution no respondió'}",
            datetime.now(timezone.utc), field_id=field_id, session_id=session.id, highlight_id=highlight.id,
            href=f"/library?highlight={highlight.id}",
        )
        self._persist_runtime()


class StoreRegistry:
    """Routes each operation to its tenant while preserving the original store API."""

    OWNER_METHODS = {
        "owner_clubs", "update_owner_club", "owner_fields", "create_owner_field", "update_owner_field",
        "delete_owner_field", "update_owner_button", "owner_cameras", "set_camera_agent_token",
        "revoke_camera_agent_token", "create_owner_camera", "update_owner_camera", "delete_owner_camera",
        "start_owner_recording", "stop_owner_recording", "owner_profile", "update_owner_profile",
        "owner_notifications", "owner_activity", "mark_notification_read", "mark_all_notifications_read",
        "delete_all_notifications", "owner_dashboard", "owner_highlights", "resolve_owner_highlight_media",
        "owner_highlight_storage_keys", "delete_owner_highlight", "owner_recordings", "reconcile_owner_recordings",
        "resolve_owner_recording_media", "owner_recording_storage_keys", "delete_owner_recording",
        "revoke_session_player_access",
    }
    CAMERA_METHODS = {"accept_camera_agent_token", "agent_camera_config", "assert_agent_session", "assert_agent_storage_path"}

    def __init__(self, primary: LocalStore) -> None:
        object.__setattr__(self, "_primary", primary)
        object.__setattr__(self, "_tenants", {str(primary.profile["id"]): primary})
        object.__setattr__(self, "_discovered", False)

    def __getattr__(self, name: str):
        primary = object.__getattribute__(self, "_primary")
        if name in self.OWNER_METHODS:
            return lambda owner_id, *args, **kwargs: getattr(self.for_owner(str(owner_id)), name)(owner_id, *args, **kwargs)
        if name in self.CAMERA_METHODS:
            def camera_call(camera_id, *args, **kwargs):
                if not camera_id:
                    return getattr(primary, name)(camera_id, *args, **kwargs)
                return getattr(self._tenant_for_camera(str(camera_id)), name)(camera_id, *args, **kwargs)
            return camera_call
        if name == "record_agent_heartbeat":
            return lambda device_id, *args, **kwargs: self._tenant_for_camera(str(device_id), include_serial=True).record_agent_heartbeat(device_id, *args, **kwargs)
        if name in {"field_context", "start_session"}:
            return lambda field_token, *args, **kwargs: getattr(self._tenant_for_field(str(field_token)), name)(field_token, *args, **kwargs)
        if name == "join_session":
            return lambda token, *args, **kwargs: self._tenant_for_session_token(str(token)).join_session(token, *args, **kwargs)
        if name in {"player_media_page", "resolve_player_media"}:
            def access_call(access_token, *args, **kwargs):
                for tenant in self._all_tenants():
                    if tenant._access_hash(str(access_token)) in tenant.player_access:
                        return getattr(tenant, name)(access_token, *args, **kwargs)
                raise HTTPException(status_code=404, detail="Acceso privado no encontrado")
            return access_call
        if name in {"create_event"}:
            return lambda session_id, *args, **kwargs: getattr(self._tenant_for_session(session_id), name)(session_id, *args, **kwargs)
        if name == "register_media_upload":
            return lambda request, *args, **kwargs: self._tenant_for_session(request.session_id).register_media_upload(request, *args, **kwargs)
        if name == "mark_media_upload_available":
            def storage_call(storage_key, *args, **kwargs):
                tenant = next((item for item in self._all_tenants() if storage_key in item.recordings_by_key), primary)
                return tenant.mark_media_upload_available(storage_key, *args, **kwargs)
            return storage_call
        if name == "lease_next_job":
            def lease():
                for tenant in self._all_tenants():
                    job = tenant.lease_next_job()
                    if job is not None:
                        return job
                return None
            return lease
        if name in {"complete_job", "record_delivery"}:
            return lambda job_id, *args, **kwargs: getattr(self._tenant_for_job(job_id), name)(job_id, *args, **kwargs)
        return getattr(primary, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_primary"), name, value)

    def purge_expired_recordings(self, delete_object, now: datetime | None = None) -> int:
        return sum(tenant.purge_expired_recordings(delete_object, now) for tenant in self._all_tenants())

    def register_owner(self, owner_id: str, email: str, display_name: str) -> LocalStore:
        tenant = self._tenants.get(owner_id)
        if tenant is None:
            tenant = LocalStore(owner_id, email, display_name, seed_demo=False)
            self._tenants[owner_id] = tenant
        else:
            tenant.profile["email"] = email
            tenant.profile["display_name"] = display_name
        return tenant

    def for_owner(self, owner_id: str) -> LocalStore:
        tenant = self._tenants.get(owner_id)
        if tenant is not None:
            return tenant
        email, display_name = self._identity(owner_id)
        return self.register_owner(owner_id, email, display_name)

    def _identity(self, owner_id: str) -> tuple[str, str]:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            import psycopg
            with psycopg.connect(database_url) as connection:
                row = connection.execute(
                    """SELECT u.email,u.display_name FROM courtvision_users u
                       JOIN courtvision_memberships m ON m.user_id=u.id
                       WHERE m.club_owner_id=%s LIMIT 1""",
                    (owner_id,),
                ).fetchone()
            if row:
                return str(row[0]), str(row[1])
        return "", "Propietario"

    def _all_tenants(self) -> list[LocalStore]:
        if not self._discovered:
            database_url = os.getenv("DATABASE_URL", "").strip()
            if database_url:
                import psycopg
                with psycopg.connect(database_url) as connection:
                    rows = connection.execute(
                        """SELECT DISTINCT m.club_owner_id,u.email,u.display_name
                           FROM courtvision_memberships m JOIN courtvision_users u ON u.id=m.user_id"""
                    ).fetchall()
                for owner_id, email, display_name in rows:
                    self.register_owner(str(owner_id), str(email), str(display_name))
            object.__setattr__(self, "_discovered", True)
        return list(self._tenants.values())

    def _tenant_for_camera(self, camera_id: str, *, include_serial: bool = False) -> LocalStore:
        for tenant in self._all_tenants():
            if any(item["id"] == camera_id or (include_serial and item.get("serial_number") == camera_id) for item in tenant.cameras):
                return tenant
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    def _tenant_for_field(self, field_token: str) -> LocalStore:
        for tenant in self._all_tenants():
            if any(item["field_token"] == field_token for item in tenant.fields):
                return tenant
        raise HTTPException(status_code=404, detail="QR de cancha no encontrado")

    def _tenant_for_session(self, session_id: UUID) -> LocalStore:
        for tenant in self._all_tenants():
            if session_id in tenant.sessions:
                return tenant
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    def _tenant_for_session_token(self, token: str) -> LocalStore:
        for tenant in self._all_tenants():
            if token in tenant.sessions_by_token:
                return tenant
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    def _tenant_for_job(self, job_id: UUID) -> LocalStore:
        for tenant in self._all_tenants():
            if job_id in tenant.processing_jobs:
                return tenant
        raise HTTPException(status_code=404, detail="Job no encontrado")


store = StoreRegistry(LocalStore())
