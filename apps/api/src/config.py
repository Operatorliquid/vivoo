import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://courtvision:courtvision@localhost:5432/courtvision")
    s3_media_bucket: str = os.getenv("AWS_S3_MEDIA_BUCKET", "")
    cloudfront_domain: str = os.getenv("AWS_CLOUDFRONT_DISTRIBUTION_DOMAIN", "")
    local_agent_key: str = os.getenv("LOCAL_AGENT_KEY", "courtvision-local-agent")
    local_agent_signing_secret: str = os.getenv("LOCAL_AGENT_SIGNING_SECRET", "courtvision-agent-development-secret")
    local_worker_key: str = os.getenv("LOCAL_WORKER_KEY", "courtvision-local-worker")
    owner_session_signing_secret: str = os.getenv("OWNER_SESSION_SIGNING_SECRET", "courtvision-owner-development-secret")
    player_access_signing_secret: str = os.getenv("PLAYER_ACCESS_SIGNING_SECRET", "courtvision-player-access-development-secret")
    data_encryption_key: str = os.getenv("DATA_ENCRYPTION_KEY", "courtvision-data-development-secret")
    local_media_root: str = os.getenv("LOCAL_MEDIA_ROOT", "/tmp/courtvision-media")
    presign_ttl_seconds: int = int(os.getenv("MEDIA_PRESIGN_TTL_SECONDS", "900"))
    public_media_base_url: str = os.getenv("PUBLIC_MEDIA_BASE_URL", "http://127.0.0.1:8000")
    evolution_api_url: str = os.getenv("EVOLUTION_API_URL", "")
    evolution_api_key: str = os.getenv("EVOLUTION_API_KEY", "")
    evolution_instance: str = os.getenv("EVOLUTION_INSTANCE", "courtvision")
    evolution_enabled: bool = os.getenv("EVOLUTION_ENABLED", "false").lower() == "true"
    health_require_worker: bool = os.getenv("HEALTH_REQUIRE_WORKER", "false").lower() == "true"
    health_worker_max_age_seconds: int = int(os.getenv("HEALTH_WORKER_MAX_AGE_SECONDS", "45"))
    health_min_disk_free_bytes: int = int(os.getenv("HEALTH_MIN_DISK_FREE_BYTES", str(512 * 1024 * 1024)))
    cors_allowed_origins: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    )
    trusted_hosts: str = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_allowed_origins.split(",") if value.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [value.strip() for value in self.trusted_hosts.split(",") if value.strip()]

    def validate_production(self) -> None:
        if self.app_env != "production":
            return
        required = {
            "LOCAL_AGENT_SIGNING_SECRET": self.local_agent_signing_secret,
            "LOCAL_WORKER_KEY": self.local_worker_key,
            "OWNER_SESSION_SIGNING_SECRET": self.owner_session_signing_secret,
            "PLAYER_ACCESS_SIGNING_SECRET": self.player_access_signing_secret,
            "DATA_ENCRYPTION_KEY": self.data_encryption_key,
        }
        development_values = {
            "courtvision-agent-development-secret",
            "courtvision-local-worker",
            "courtvision-owner-development-secret",
            "courtvision-player-access-development-secret",
            "courtvision-data-development-secret",
        }
        invalid = [name for name, value in required.items() if len(value) < 32 or value in development_values]
        if invalid:
            raise RuntimeError(f"Production secrets are missing or weak: {', '.join(invalid)}")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise RuntimeError("TRUSTED_HOSTS must explicitly list the production hosts")


settings = Settings()
