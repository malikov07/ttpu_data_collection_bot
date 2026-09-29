"""Password hashing (scrypt, standard library) and account name rules."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

# scrypt parameters: ~16 MB of memory and ~50 ms per hash on a small server.
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/l/I
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
MIN_PASSWORD_LENGTH = 8


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, key = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# A valid hash to verify against when the username doesn't exist, so that
# response times don't reveal which usernames are taken.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def generate_password(length: int = 12) -> str:
    """Readable temporary password (no look-alike characters)."""
    while True:
        pw = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in pw) and any(c.isupper() for c in pw) and any(c.islower() for c in pw):
            return pw


def normalize_username(raw: str) -> str | None:
    username = raw.strip().lower()
    return username if USERNAME_RE.match(username) else None


def password_problem(password: str) -> str | None:
    """None if the password is acceptable, else an error code."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return "password_too_short"
    if password.isdigit() or password.isalpha():
        return "password_too_simple"
    return None
