"""Persistent owner accounts, memberships, sessions, and password recovery."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from uuid import uuid4


DEVELOPMENT_EMAIL = "owner@courtvision.local"
DEVELOPMENT_PASSWORD = "courtvision-demo"
DEVELOPMENT_OWNER_ID = "8f0e2f1a-1b21-4ef0-bd2a-2b1d5e540201"
SESSION_TTL = timedelta(hours=max(1, int(os.getenv("OWNER_SESSION_TTL_HOURS", "720"))))
RESET_TTL = timedelta(minutes=max(5, int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "30"))))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Return a versioned, salted scrypt password hash."""
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    password_hash: str
    display_name: str
    active: bool
    is_platform_admin: bool = False


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    owner_id: str
    email: str
    display_name: str
    role: str

    def as_dependency(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "owner_id": self.owner_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
        }


class MemoryAccountRepository:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.email_index: dict[str, str] = {}
        self.memberships: dict[str, tuple[str, str]] = {}
        self.sessions: dict[str, tuple[AuthContext, datetime, datetime | None]] = {}
        self.resets: dict[str, tuple[str, datetime, datetime | None]] = {}

    def initialize(self) -> None:
        return

    def account_count(self) -> int:
        return len(self.accounts)

    def create_account(self, account: Account, owner_id: str, role: str) -> None:
        email = account.email.casefold()
        if email in self.email_index:
            raise ValueError("Ya existe una cuenta con ese email")
        self.accounts[account.id] = account
        self.email_index[email] = account.id
        self.memberships[account.id] = (owner_id, role)

    def create_platform_admin(self, account: Account) -> None:
        email = account.email.casefold()
        existing_id = self.email_index.get(email)
        if existing_id:
            existing = self.accounts[existing_id]
            self.accounts[existing_id] = Account(
                existing.id, existing.email, existing.password_hash, existing.display_name, existing.active, True
            )
            return
        self.accounts[account.id] = account
        self.email_index[email] = account.id

    def account_by_email(self, email: str) -> Account | None:
        account_id = self.email_index.get(email.casefold())
        return self.accounts.get(account_id) if account_id else None

    def context_for_user(self, user_id: str) -> AuthContext | None:
        account = self.accounts.get(user_id)
        if account is not None and account.active and account.is_platform_admin:
            return AuthContext(account.id, "platform", account.email, account.display_name, "platform_admin")
        membership = self.memberships.get(user_id)
        if account is None or membership is None or not account.active:
            return None
        return AuthContext(account.id, membership[0], account.email, account.display_name, membership[1])

    def save_session(self, token_hash: str, context: AuthContext, expires_at: datetime) -> None:
        self.sessions[token_hash] = (context, expires_at, None)

    def session(self, token_hash: str) -> AuthContext | None:
        row = self.sessions.get(token_hash)
        if row is None or row[2] is not None or row[1] <= _now():
            return None
        return row[0]

    def revoke_session(self, token_hash: str) -> None:
        row = self.sessions.get(token_hash)
        if row:
            self.sessions[token_hash] = (row[0], row[1], _now())

    def save_reset(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        self.resets[token_hash] = (user_id, expires_at, None)

    def consume_reset(self, token_hash: str) -> str | None:
        row = self.resets.get(token_hash)
        if row is None or row[2] is not None or row[1] <= _now():
            return None
        self.resets[token_hash] = (row[0], row[1], _now())
        return row[0]

    def update_password(self, user_id: str, password_hash: str) -> None:
        account = self.accounts[user_id]
        self.accounts[user_id] = Account(
            account.id, account.email, password_hash, account.display_name, account.active, account.is_platform_admin
        )
        for token_hash, row in list(self.sessions.items()):
            if row[0].user_id == user_id and row[2] is None:
                self.sessions[token_hash] = (row[0], row[1], _now())



class PostgresAccountRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        import psycopg
        return psycopg.connect(self.database_url)

    def initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS courtvision_users (
                id text PRIMARY KEY, email text NOT NULL UNIQUE, password_hash text NOT NULL,
                display_name text NOT NULL, active boolean NOT NULL DEFAULT true,
                is_platform_admin boolean NOT NULL DEFAULT false,
                created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
            )""",
            "ALTER TABLE courtvision_users ADD COLUMN IF NOT EXISTS is_platform_admin boolean NOT NULL DEFAULT false",
            "CREATE UNIQUE INDEX IF NOT EXISTS courtvision_users_email_lower_idx ON courtvision_users (lower(email))",
            """CREATE TABLE IF NOT EXISTS courtvision_memberships (
                user_id text NOT NULL REFERENCES courtvision_users(id) ON DELETE CASCADE,
                club_owner_id text NOT NULL, role text NOT NULL CHECK (role = 'owner'),
                created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, club_owner_id)
            )""",
            """CREATE TABLE IF NOT EXISTS courtvision_owner_sessions (
                token_hash text PRIMARY KEY, user_id text NOT NULL REFERENCES courtvision_users(id) ON DELETE CASCADE,
                club_owner_id text NOT NULL, role text NOT NULL, expires_at timestamptz NOT NULL,
                revoked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
                last_seen_at timestamptz NOT NULL DEFAULT now()
            )""",
            "CREATE INDEX IF NOT EXISTS courtvision_owner_sessions_user_idx ON courtvision_owner_sessions (user_id, expires_at)",
            """CREATE TABLE IF NOT EXISTS courtvision_password_resets (
                token_hash text PRIMARY KEY, user_id text NOT NULL REFERENCES courtvision_users(id) ON DELETE CASCADE,
                expires_at timestamptz NOT NULL, used_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
            )""",
        )
        with self._connect() as connection:
            for statement in statements:
                connection.execute(statement)

    def account_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT count(*) FROM courtvision_users").fetchone()[0])

    def create_account(self, account: Account, owner_id: str, role: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO courtvision_users (id,email,password_hash,display_name,active,is_platform_admin) VALUES (%s,%s,%s,%s,%s,%s)",
                    (account.id, account.email.casefold(), account.password_hash, account.display_name, account.active, account.is_platform_admin),
                )
                connection.execute(
                    "INSERT INTO courtvision_memberships (user_id,club_owner_id,role) VALUES (%s,%s,%s)",
                    (account.id, owner_id, role),
                )
        except Exception as error:
            if "unique" in str(error).lower():
                raise ValueError("Ya existe una cuenta con ese email") from None
            raise

    def create_platform_admin(self, account: Account) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO courtvision_users
                   (id,email,password_hash,display_name,active,is_platform_admin)
                   VALUES (%s,%s,%s,%s,%s,true)
                   ON CONFLICT (email) DO UPDATE SET is_platform_admin=true""",
                (account.id, account.email.casefold(), account.password_hash, account.display_name, account.active),
            )

    def account_by_email(self, email: str) -> Account | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id,email,password_hash,display_name,active,is_platform_admin FROM courtvision_users WHERE lower(email)=lower(%s)",
                (email.strip(),),
            ).fetchone()
        return Account(*row) if row else None

    def context_for_user(self, user_id: str) -> AuthContext | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT u.id,
                          CASE WHEN u.is_platform_admin THEN 'platform' ELSE m.club_owner_id END,
                          u.email,u.display_name,
                          CASE WHEN u.is_platform_admin THEN 'platform_admin' ELSE m.role END
                   FROM courtvision_users u
                   LEFT JOIN courtvision_memberships m ON m.user_id=u.id
                   WHERE u.id=%s AND u.active=true
                     AND (u.is_platform_admin OR m.user_id IS NOT NULL)
                   ORDER BY m.created_at NULLS FIRST LIMIT 1""",
                (user_id,),
            ).fetchone()
        return AuthContext(*row) if row else None

    def save_session(self, token_hash: str, context: AuthContext, expires_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO courtvision_owner_sessions
                   (token_hash,user_id,club_owner_id,role,expires_at) VALUES (%s,%s,%s,%s,%s)""",
                (token_hash, context.user_id, context.owner_id, context.role, expires_at),
            )

    def session(self, token_hash: str) -> AuthContext | None:
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE courtvision_owner_sessions s SET last_seen_at=now()
                   FROM courtvision_users u
                   WHERE s.token_hash=%s AND s.user_id=u.id AND s.revoked_at IS NULL
                     AND s.expires_at>now() AND u.active=true
                   RETURNING u.id,s.club_owner_id,u.email,u.display_name,s.role""",
                (token_hash,),
            ).fetchone()
        return AuthContext(*row) if row else None

    def revoke_session(self, token_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE courtvision_owner_sessions SET revoked_at=COALESCE(revoked_at,now()) WHERE token_hash=%s",
                (token_hash,),
            )

    def save_reset(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM courtvision_password_resets WHERE user_id=%s AND used_at IS NULL", (user_id,))
            connection.execute(
                "INSERT INTO courtvision_password_resets (token_hash,user_id,expires_at) VALUES (%s,%s,%s)",
                (token_hash, user_id, expires_at),
            )

    def consume_reset(self, token_hash: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE courtvision_password_resets SET used_at=now()
                   WHERE token_hash=%s AND used_at IS NULL AND expires_at>now() RETURNING user_id""",
                (token_hash,),
            ).fetchone()
        return str(row[0]) if row else None

    def update_password(self, user_id: str, password_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE courtvision_users SET password_hash=%s,updated_at=now() WHERE id=%s",
                (password_hash, user_id),
            )
            connection.execute(
                "UPDATE courtvision_owner_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
                (user_id,),
            )



class AccountService:
    def __init__(self) -> None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        self.repository: MemoryAccountRepository | PostgresAccountRepository
        self.repository = PostgresAccountRepository(database_url) if database_url else MemoryAccountRepository()
        self.repository.initialize()
        self._bootstrap_if_empty()
        self._bootstrap_platform_admin()

    def _bootstrap_if_empty(self) -> None:
        if self.repository.account_count() > 0:
            return
        production = os.getenv("APP_ENV", "local") == "production"
        email = os.getenv("BOOTSTRAP_OWNER_EMAIL", DEVELOPMENT_EMAIL).strip().casefold()
        encoded = os.getenv("BOOTSTRAP_OWNER_PASSWORD_HASH", "").strip()
        if not encoded and production:
            raise RuntimeError("BOOTSTRAP_OWNER_PASSWORD_HASH is required for the first production account")
        if not encoded:
            encoded = hash_password(DEVELOPMENT_PASSWORD)
        owner_id = os.getenv("BOOTSTRAP_OWNER_ID", DEVELOPMENT_OWNER_ID).strip()
        self.repository.create_account(
            Account(
                id=owner_id,
                email=email,
                password_hash=encoded,
                display_name=os.getenv("BOOTSTRAP_OWNER_DISPLAY_NAME", "José Stratta").strip(),
                active=True,
            ),
            owner_id=owner_id,
            role="owner",
        )

    def _bootstrap_platform_admin(self) -> None:
        production = os.getenv("APP_ENV", "local") == "production"
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@tveo.local" if not production else "").strip().casefold()
        encoded = os.getenv("BOOTSTRAP_ADMIN_PASSWORD_HASH", "").strip()
        if not email:
            return
        if not encoded:
            if production:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD_HASH is required when BOOTSTRAP_ADMIN_EMAIL is configured")
            encoded = hash_password("tveo-admin-demo")
        self.repository.create_platform_admin(
            Account(
                id=os.getenv("BOOTSTRAP_ADMIN_ID", "tveo-platform-admin").strip(),
                email=email,
                password_hash=encoded,
                display_name=os.getenv("BOOTSTRAP_ADMIN_DISPLAY_NAME", "vivoo Admin").strip(),
                active=True,
                is_platform_admin=True,
            )
        )

    def authenticate(self, email: str, password: str) -> AuthContext | None:
        account = self.repository.account_by_email(email.strip())
        if account is None or not account.active or not verify_password(password, account.password_hash):
            return None
        return self.repository.context_for_user(account.id)

    def authenticate_owner(self, email: str, password: str) -> AuthContext | None:
        context = self.authenticate(email, password)
        return context if context is not None and context.role == "owner" else None

    def authenticate_admin(self, email: str, password: str) -> AuthContext | None:
        context = self.authenticate(email, password)
        return context if context is not None and context.role == "platform_admin" else None

    def create_owner_account(self, email: str, password: str, display_name: str) -> AuthContext:
        normalized_email = email.strip().casefold()
        if self.repository.account_by_email(normalized_email) is not None:
            raise ValueError("Ya existe un usuario con ese email")
        owner_id = str(uuid4())
        account = Account(
            id=owner_id,
            email=normalized_email,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            active=True,
        )
        self.repository.create_account(account, owner_id=owner_id, role="owner")
        context = self.repository.context_for_user(owner_id)
        if context is None:
            raise RuntimeError("No se pudo crear el acceso del usuario")
        return context

    def issue_session(self, context: AuthContext) -> str:
        token = f"cv_session_{secrets.token_urlsafe(36)}"
        self.repository.save_session(_fingerprint(token), context, _now() + SESSION_TTL)
        return token

    def verify_session(self, token: str) -> AuthContext | None:
        if not token.startswith("cv_session_"):
            return None
        return self.repository.session(_fingerprint(token))

    def revoke_session(self, token: str) -> None:
        self.repository.revoke_session(_fingerprint(token))

    def rotate_session(self, token: str) -> tuple[str, AuthContext] | None:
        context = self.verify_session(token)
        if context is None:
            return None
        replacement = self.issue_session(context)
        self.revoke_session(token)
        return replacement, context

    def request_password_reset(self, email: str) -> str | None:
        account = self.repository.account_by_email(email.strip())
        if account is None or not account.active:
            return None
        token = f"cv_reset_{secrets.token_urlsafe(32)}"
        self.repository.save_reset(_fingerprint(token), account.id, _now() + RESET_TTL)
        return token

    def reset_password(self, token: str, password: str) -> bool:
        if not token.startswith("cv_reset_"):
            return False
        user_id = self.repository.consume_reset(_fingerprint(token))
        if user_id is None:
            return False
        self.repository.update_password(user_id, hash_password(password))
        return True



account_service = AccountService()
