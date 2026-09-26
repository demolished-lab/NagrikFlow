"""Secrets discipline: no defaults, rotation, short sessions.

- APP_SECRET required in production (refuse to boot with dev fallback
  unless ALLOW_DEV_SECRET=1, which tests set).
- APP_SECRET_PREV accepts tokens signed by the previous secret during
  rotation (verify tries current, then previous).
- SESSION_TTL_SECONDS env (default 2h, was 12h).
- JWT carries kid so verifiers know which secret signed.
"""
import os

ALLOW_DEV = os.environ.get("ALLOW_DEV_SECRET", "") == "1"
SECRET = os.environ.get("APP_SECRET", "")
PREV = os.environ.get("APP_SECRET_PREV", "")
TTL = int(os.environ.get("SESSION_TTL_SECONDS", "7200"))

if not SECRET:
    if ALLOW_DEV:
        SECRET = "dev-only-insecure"
    else:
        raise RuntimeError("APP_SECRET must be set (ALLOW_DEV_SECRET=1 for local dev only)")


def secrets():
    """Return [(kid, secret)] newest-first for verify chaining."""
    out = [("cur", SECRET)]
    if PREV and PREV != SECRET:
        out.append(("prev", PREV))
    return out
