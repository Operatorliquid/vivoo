"""Read-only, cross-tenant operational view for vivoo platform administrators."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from auth.account_service import MemoryAccountRepository, account_service
from services.store import AGENT_HEARTBEAT_TIMEOUT, MAX_SESSION_DURATION, store


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _camera_online(camera: dict[str, Any], now: datetime) -> bool:
    heartbeat = _as_datetime(camera.get("agent_last_seen_at"))
    return bool(heartbeat and now - heartbeat <= AGENT_HEARTBEAT_TIMEOUT)


def _active_sessions(runtime: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for session in runtime.get("sessions", []):
        started = _as_datetime(session.get("started_at"))
        if session.get("ended_at") or started is None or now - started > MAX_SESSION_DURATION:
            continue
        active.append(session)
    return active


def _customer_view(
    account: dict[str, Any],
    club: dict[str, Any] | None,
    fields: list[dict[str, Any]],
    cameras: list[dict[str, Any]],
    runtime: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    active_sessions = _active_sessions(runtime, now)
    active_by_field = {str(item.get("field_id")) for item in active_sessions}
    online = sum(1 for item in cameras if _camera_online(item, now))
    offline = len(cameras) - online
    highlights = runtime.get("highlights", [])
    failed_highlights = sum(1 for item in highlights if item.get("status") == "failed")
    pending_highlights = sum(1 for item in highlights if item.get("status") in {"requested", "processing"})

    if not club or not fields:
        status = "setup"
    elif offline > 0 or failed_highlights > 0:
        status = "attention"
    else:
        status = "operational"

    camera_by_field = {str(item.get("field_id")): item for item in cameras}
    court_views = []
    for field in fields:
        field_id = str(field.get("id", ""))
        camera = camera_by_field.get(field_id)
        camera_online = bool(camera and _camera_online(camera, now))
        court_views.append({
            "id": field_id,
            "name": str(field.get("name") or "Cancha sin nombre"),
            "sport_code": str(field.get("sport_code") or "padel"),
            "status": str(field.get("status") or "inactive"),
            "recording": field_id in active_by_field,
            "camera": None if camera is None else {
                "id": str(camera.get("id", "")),
                "name": str(camera.get("name") or "Cámara"),
                "status": "online" if camera_online else "offline",
                "detector_status": str(camera.get("detector_status") or "idle"),
                "last_seen_at": camera.get("agent_last_seen_at"),
            },
        })

    seen_values = [_as_datetime(item.get("agent_last_seen_at")) for item in cameras]
    last_seen = max((item for item in seen_values if item is not None), default=None)
    return {
        "id": str(account["id"]),
        "display_name": str(account["display_name"]),
        "email": str(account["email"]),
        "active": bool(account["active"]),
        "created_at": account.get("created_at"),
        "club": None if club is None else {
            "id": str(club.get("id", "")),
            "name": str(club.get("name") or "Club sin nombre"),
            "city": str(club.get("city") or ""),
            "logo_data_url": str(club.get("logo_data_url") or ""),
        },
        "status": status,
        "last_seen_at": last_seen,
        "metrics": {
            "courts": len(fields),
            "cameras": len(cameras),
            "cameras_online": online,
            "cameras_offline": offline,
            "active_recordings": len(active_sessions),
            "highlights": len(highlights),
            "highlights_pending": pending_highlights,
            "highlights_failed": failed_highlights,
        },
        "courts": court_views,
    }


class AdminStore:
    def overview(self) -> dict[str, Any]:
        database_url = os.getenv("DATABASE_URL", "").strip()
        customers = self._postgres_customers(database_url) if database_url else self._memory_customers()
        attention = sum(1 for item in customers if item["status"] == "attention")
        return {
            "generated_at": _now(),
            "summary": {
                "customers": len(customers),
                "clubs": sum(1 for item in customers if item["club"] is not None),
                "courts": sum(item["metrics"]["courts"] for item in customers),
                "cameras": sum(item["metrics"]["cameras"] for item in customers),
                "cameras_online": sum(item["metrics"]["cameras_online"] for item in customers),
                "active_recordings": sum(item["metrics"]["active_recordings"] for item in customers),
                "attention": attention,
            },
            "customers": customers,
        }

    def customer(self, customer_id: str) -> dict[str, Any] | None:
        return next((item for item in self.overview()["customers"] if item["id"] == customer_id), None)

    def _memory_customers(self) -> list[dict[str, Any]]:
        repository = account_service.repository
        if not isinstance(repository, MemoryAccountRepository):
            return []
        now = _now()
        runtime = {
            "sessions": [
                {"field_id": str(item.field_id), "started_at": item.started_at, "ended_at": item.ended_at}
                for item in store.sessions.values()
            ],
            "highlights": [{"status": item.status} for item in store.highlights.values()],
        }
        result = []
        for account in repository.accounts.values():
            if account.is_platform_admin:
                continue
            owner_id = repository.memberships.get(account.id, (account.id, "owner"))[0]
            tenant = store.for_owner(owner_id)
            result.append(_customer_view(
                {"id": account.id, "email": account.email, "display_name": account.display_name, "active": account.active, "created_at": None},
                tenant.club,
                tenant.fields,
                tenant.cameras,
                runtime if owner_id == store.profile["id"] else {},
                now,
            ))
        return result

    def _postgres_customers(self, database_url: str) -> list[dict[str, Any]]:
        import psycopg

        with psycopg.connect(database_url) as connection:
            account_rows = connection.execute(
                """SELECT u.id,u.email,u.display_name,u.active,u.created_at,m.club_owner_id
                   FROM courtvision_users u
                   JOIN courtvision_memberships m ON m.user_id=u.id
                   WHERE u.is_platform_admin=false
                   ORDER BY u.created_at DESC"""
            ).fetchall()
            club_rows = connection.execute(
                "SELECT owner_id,id,name,city,logo_data_url FROM courtvision_clubs"
            ).fetchall()
            field_rows = connection.execute(
                """SELECT owner_id,id,name,sport_code,status,recording_enabled,detection_mode
                   FROM courtvision_fields ORDER BY name"""
            ).fetchall()
            camera_rows = connection.execute(
                """SELECT owner_id,id,field_id,name,status,detector_status,agent_last_seen_at
                   FROM courtvision_cameras ORDER BY name"""
            ).fetchall()
            runtime_rows = connection.execute(
                "SELECT owner_id,payload FROM courtvision_runtime_state"
            ).fetchall()

        clubs = {
            row[0]: {"id": row[1], "name": row[2], "city": row[3], "logo_data_url": row[4]}
            for row in club_rows
        }
        fields: dict[str, list[dict[str, Any]]] = {}
        for row in field_rows:
            fields.setdefault(row[0], []).append({
                "id": row[1], "name": row[2], "sport_code": row[3], "status": row[4],
                "recording_enabled": row[5], "detection_mode": row[6],
            })
        cameras: dict[str, list[dict[str, Any]]] = {}
        for row in camera_rows:
            cameras.setdefault(row[0], []).append({
                "id": row[1], "field_id": row[2], "name": row[3], "status": row[4],
                "detector_status": row[5], "agent_last_seen_at": row[6],
            })
        runtimes = {
            row[0]: row[1] if isinstance(row[1], dict) else json.loads(row[1])
            for row in runtime_rows
        }
        now = _now()
        return [
            _customer_view(
                {"id": row[0], "email": row[1], "display_name": row[2], "active": row[3], "created_at": row[4]},
                clubs.get(row[5]), fields.get(row[5], []), cameras.get(row[5], []), runtimes.get(row[5], {}), now,
            )
            for row in account_rows
        ]


admin_store = AdminStore()
