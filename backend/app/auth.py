"""Auth: password hashing (stdlib PBKDF2) + JWT sessions (PyJWT).

Borrowed shape from universal_api/auth (Tenant + JWTManager) but rebuilt
for multi-user login: per-user sub, short expiry, issuer check.
"""
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import jwt

SECRET = os.environ.get("APP_SECRET", "dev-only-change-me")
ISSUER = "civic-pathfinder"
ALGO = "HS256"
SESSION_TTL = 12 * 3600


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2$200000${salt}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, hexd = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), hexd)
    except Exception:
        return False


def issue_token(user_id: int, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "email": email, "iss": ISSUER,
         "iat": now, "exp": now + SESSION_TTL},
        SECRET, algorithm=ALGO,
    )


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO], issuer=ISSUER)
        return payload
    except jwt.PyJWTError:
        return None
