import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


DEMO_EMAIL = "owner@courtvision.local"
DEMO_PASSWORD = "courtvision-demo"
DEMO_OWNER_ID = "8f0e2f1a-1b21-4ef0-bd2a-2b1d5e540201"
AGENT_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30
OWNER_MEDIA_TICKET_TTL_SECONDS = 60 * 60
_revoked_agent_tokens: set[str] = set()


def _agent_secret() -> bytes:
    return os.getenv("LOCAL_AGENT_SIGNING_SECRET", "courtvision-agent-development-secret").encode()


def _encode(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _sign(payload: str) -> str:
    secret = os.getenv("OWNER_SESSION_SIGNING_SECRET", "courtvision-owner-development-secret").encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


def issue_local_token() -> str:
    payload = _encode({"sub": DEMO_OWNER_ID, "email": DEMO_EMAIL, "exp": int(time.time()) + 3600})
    return f"local.{payload}.{_sign(payload)}"


def verify_local_token(token: str) -> dict[str, str]:
    try:
        prefix, payload, signature = token.split(".", 2)
        if prefix != "local" or not hmac.compare_digest(signature, _sign(payload)):
            raise ValueError
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
        if decoded["exp"] < int(time.time()):
            raise ValueError
        return {"owner_id": decoded["sub"], "email": decoded["email"]}
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("invalid local token") from None


def issue_agent_token(camera_id: str) -> str:
    payload = _encode({
        "camera_id": camera_id,
        "exp": int(time.time()) + AGENT_TOKEN_TTL_SECONDS,
        "jti": secrets.token_urlsafe(18),
    })
    signature = hmac.new(_agent_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"agent.{payload}.{signature}"


def verify_agent_token(token: str) -> dict[str, str]:
    try:
        if token in _revoked_agent_tokens:
            raise ValueError
        prefix, payload, signature = token.split(".", 2)
        expected = hmac.new(_agent_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if prefix != "agent" or not hmac.compare_digest(signature, expected):
            raise ValueError
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
        if decoded["exp"] < int(time.time()) or not decoded["camera_id"]:
            raise ValueError
        return {"camera_id": decoded["camera_id"]}
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("invalid agent token") from None


def revoke_agent_token(token: str) -> None:
    _revoked_agent_tokens.add(token)


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_owner_media_ticket(owner_id: str, highlight_id: str) -> str:
    payload = _encode({
        "owner_id": owner_id,
        "highlight_id": highlight_id,
        "exp": int(time.time()) + OWNER_MEDIA_TICKET_TTL_SECONDS,
    })
    signature = hmac.new(_agent_secret(), f"owner-media:{payload}".encode(), hashlib.sha256).hexdigest()
    return f"media.{payload}.{signature}"


def verify_owner_media_ticket(token: str, highlight_id: str) -> dict[str, str]:
    try:
        prefix, payload, signature = token.split(".", 2)
        expected = hmac.new(_agent_secret(), f"owner-media:{payload}".encode(), hashlib.sha256).hexdigest()
        if prefix != "media" or not hmac.compare_digest(signature, expected):
            raise ValueError
        padding = "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
        if decoded["exp"] < int(time.time()) or decoded["highlight_id"] != highlight_id:
            raise ValueError
        return {"owner_id": str(decoded["owner_id"]), "highlight_id": str(decoded["highlight_id"])}
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("invalid owner media ticket") from None
