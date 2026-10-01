"""Auth: password hashing (stdlib PBKDF2) + JWT sessions (PyJWT).

Borrowed shape from universal_api/auth (Tenant + JWTManager) but rebuilt
for multi-user login: per-user sub, short expiry, issuer check.
"""
import hashlib
import hmac
import secrets
import time

import jwt

from . import secrets as secretmod

ISSUER = "civic-pathfinder"
ALGO = "HS256"


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
    kid, secret = secretmod.secrets()[0]
    return jwt.encode(
        {"sub": str(user_id), "email": email, "iss": ISSUER,
         "iat": now, "exp": now + secretmod.TTL},
        secret, algorithm=ALGO, headers={"kid": kid},
    )


def verify_token(token: str) -> dict | None:
    """Try each known secret newest-first (rotation-safe)."""
    for _, secret in secretmod.secrets():
        try:
            return jwt.decode(token, secret, algorithms=[ALGO], issuer=ISSUER)
        except jwt.PyJWTError:
            continue
    return None
