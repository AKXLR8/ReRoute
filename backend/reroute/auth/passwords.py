"""Password hashing — PBKDF2-HMAC-SHA256 from the stdlib (no new dependency).

ponytail: 600k iterations is the OWASP floor for PBKDF2-SHA256 (2023+);
bcrypt/argon2 would be nicer but hashlib already does this correctly and
the login path is one admin-sized request per minute, not thousands/sec.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGO = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16
MIN_LEN = 7
MAX_LEN = 128


def check_policy(password: str) -> str | None:
    """Error message when unacceptable, else None."""
    if len(password) < MIN_LEN:
        return f"Password must be at least {MIN_LEN} characters"
    if len(password) > MAX_LEN:
        return f"Password must be at most {MAX_LEN} characters"
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return (
        f"{ALGO}${ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != ALGO:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)


_dummy_hash: str | None = None


def dummy_verify(password: str) -> bool:
    """Burn one PBKDF2 for unknown emails so login timing matches real users."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-equalizer-not-a-real-password")
    verify_password(password, _dummy_hash)
    return False
