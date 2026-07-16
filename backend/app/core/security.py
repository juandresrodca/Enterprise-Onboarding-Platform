"""Security primitives: password hashing, JWT sessions, CSRF tokens.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib, no native deps).
Sessions are short-lived JWTs delivered in an httpOnly cookie; CSRF uses the
double-submit-cookie pattern (non-httpOnly cookie mirrored in a header).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

PBKDF2_ITERATIONS = 210_000
_ALGO = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_session_token(
    *,
    secret: str,
    username: str,
    display_name: str,
    role: str,
    timeout_minutes: int,
    auth_source: str = "local",
) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
    payload: dict[str, Any] = {
        "sub": username,
        "name": display_name,
        "role": role,
        "src": auth_source,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, secret, algorithm=_ALGO), expires


def decode_session_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, secret, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
