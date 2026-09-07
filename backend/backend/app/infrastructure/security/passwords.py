"""Password hashing helpers using PBKDF2-HMAC-SHA256."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

ALGORITHM = "sha256"
ITERATIONS = 310_000
SALT_BYTES = 16
KEY_BYTES = 32


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(ALGORITHM, password.encode(), salt, ITERATIONS, dklen=KEY_BYTES)
    return f"pbkdf2_{ALGORITHM}${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != f"pbkdf2_{ALGORITHM}":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac(ALGORITHM, password.encode(), salt, int(iterations), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> str:
    """Require a practical baseline for account passwords."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain a lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain a special character")
    return password
