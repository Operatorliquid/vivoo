import pytest

from config import Settings


def test_production_rejects_development_secrets() -> None:
    configuration = Settings(app_env="production")
    with pytest.raises(RuntimeError, match="Production secrets are missing or weak"):
        configuration.validate_production()


def test_production_accepts_independent_strong_secrets() -> None:
    configuration = Settings(
        app_env="production",
        local_agent_signing_secret="agent-" + "a" * 48,
        local_worker_key="worker-" + "b" * 48,
        owner_session_signing_secret="owner-" + "c" * 48,
        player_access_signing_secret="player-" + "d" * 48,
        data_encryption_key="data-" + "e" * 48,
    )
    configuration.validate_production()
