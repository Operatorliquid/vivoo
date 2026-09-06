from __future__ import annotations

import os
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Apply ordered SQL migrations and return the versions applied in this run."""
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to apply CourtVision migrations")

    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - exercised only in an uninstalled CLI environment
        raise RuntimeError("Install the API dependencies before applying migrations") from error

    migration_files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    applied: list[str] = []
    with psycopg.connect(url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version text PRIMARY KEY,
              applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        existing = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration in migration_files:
            if migration.name in existing:
                continue
            connection.execute(migration.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
            applied.append(migration.name)
    return applied


if __name__ == "__main__":
    for migration in apply_migrations():
        print(f"applied {migration}")
