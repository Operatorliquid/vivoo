from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import settings


class HealthService:
    @staticmethod
    def _database_enabled() -> bool:
        # Local development can run with the in-memory store and no PostgreSQL.
        # Production always receives DATABASE_URL from Compose.
        return bool(settings.database_url and (settings.app_env == "production" or os.getenv("DATABASE_URL")))

    def database(self) -> dict[str, object]:
        if not self._database_enabled():
            return {"status": "disabled"}
        try:
            import psycopg
            with psycopg.connect(settings.database_url, connect_timeout=2) as connection:
                connection.execute("SELECT 1").fetchone()
            return {"status": "ok"}
        except Exception as error:
            return {"status": "error", "detail": type(error).__name__}

    def storage(self) -> dict[str, object]:
        if settings.s3_media_bucket:
            try:
                import boto3
                boto3.client("s3", region_name=settings.aws_region).head_bucket(Bucket=settings.s3_media_bucket)
                return {"status": "ok", "backend": "s3"}
            except Exception as error:
                return {"status": "error", "backend": "s3", "detail": type(error).__name__}
        try:
            root = Path(settings.local_media_root)
            root.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(root)
            writable = os.access(root, os.W_OK)
            healthy = writable and usage.free >= settings.health_min_disk_free_bytes
            return {
                "status": "ok" if healthy else "error",
                "backend": "local",
                "free_bytes": usage.free,
                "writable": writable,
            }
        except OSError as error:
            return {"status": "error", "backend": "local", "detail": type(error).__name__}

    def worker(self) -> dict[str, object]:
        if not self._database_enabled():
            return {"status": "disabled"}
        try:
            import psycopg
            with psycopg.connect(settings.database_url, connect_timeout=2) as connection:
                row = connection.execute(
                    "SELECT observed_at FROM courtvision_service_heartbeats WHERE service_name='media-worker'"
                ).fetchone()
            if row is None:
                return {"status": "error" if settings.health_require_worker else "waiting", "last_seen_at": None}
            observed_at = row[0]
            age = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
            return {"status": "ok" if age <= settings.health_worker_max_age_seconds else "error", "last_seen_at": observed_at.isoformat(), "age_seconds": round(age, 1)}
        except Exception as error:
            return {"status": "error", "detail": type(error).__name__}

    def record_worker(self, metadata: dict[str, object] | None = None) -> None:
        if not self._database_enabled():
            return
        import json

        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute(
                """INSERT INTO courtvision_service_heartbeats(service_name, observed_at, metadata)
                   VALUES ('media-worker', now(), %s::jsonb)
                   ON CONFLICT(service_name) DO UPDATE SET observed_at=now(), metadata=EXCLUDED.metadata""",
                (json.dumps(metadata or {}),),
            )

    def report(self) -> tuple[dict[str, object], bool]:
        checks = {"database": self.database(), "storage": self.storage(), "worker": self.worker()}
        healthy = all(check["status"] in {"ok", "disabled", "waiting"} for check in checks.values())
        return {"status": "ok" if healthy else "degraded", "service": "vivoo-api", "checks": checks}, healthy


health_service = HealthService()
