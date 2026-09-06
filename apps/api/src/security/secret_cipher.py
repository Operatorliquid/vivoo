"""Versioned authenticated encryption for secrets persisted by the API."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


PREFIX = "encv1:"


class SecretCipher:
    """Encrypts database values without requiring the raw key to be a Fernet key."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("DATA_ENCRYPTION_KEY is required")
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(derived_key)

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        if self.is_encrypted(value):
            return value
        token = self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{PREFIX}{token}"

    def decrypt(self, value: str) -> str:
        if not value or not self.is_encrypted(value):
            return value
        try:
            return self._fernet.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as error:
            raise RuntimeError("No se pudo descifrar una credencial persistida") from error

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return value.startswith(PREFIX)
