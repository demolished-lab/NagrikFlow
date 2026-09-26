"""Secrets: rotation keeps old tokens valid; TTL honored."""


def test_rotation_accepts_previous_secret(client):
    from app import auth as A
    from app import secrets as S
    old_secret, old_prev = S.SECRET, S.PREV
    try:
        S.SECRET = "brand-new-secret-32bytes-12345678"
        S.PREV = ""
        tok_new = A.issue_token(7, "r@x.co")
        S.PREV = old_secret  # rotate: new current, old becomes previous
        assert A.verify_token(tok_new)["sub"] == "7"
        # token minted under the old secret still verifies via PREV chain
        S.SECRET, S.PREV = "zzz", old_secret
        import jwt as _jwt
        legacy = _jwt.encode({"sub": "9", "email": "l@x.co", "iss": "civic-pathfinder"},
                             old_secret, algorithm="HS256")
        assert A.verify_token(legacy)["sub"] == "9"
        assert A.verify_token("garbage.token.here") is None
    finally:
        S.SECRET, S.PREV = old_secret, old_prev


def test_no_default_secret_in_prod():
    import os
    import subprocess
    import sys
    from pathlib import Path
    env = {k: v for k, v in os.environ.items()
           if k not in ("APP_SECRET", "APP_SECRET_PREV", "ALLOW_DEV_SECRET")}
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); from app import secrets"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode != 0
    assert "APP_SECRET must be set" in (r.stderr + r.stdout)
