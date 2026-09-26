"""DigiLocker / API Setu Requester connector (OAuth2 + PKCE, consent-first).

Sandbox endpoints (free, no approval): https://sandbox.api-setu.in/
Production: https://partners.apisetu.gov.in (org registration required).

Flow: authorize_url() -> user consents on MeriPehchaan -> callback with
code -> exchange_code() -> fetch_issued_docs() / fetch_file().
Tokens live only in memory; per-user refresh bound to (user_id, endpoint)
— never replay across users (pattern: omniharness _bound_auth).
"""
import hashlib
import os
import secrets
from urllib.parse import urlencode

import httpx

ENV = os.environ.get("DIGILOCKER_ENV", "sandbox")
BASE = os.environ.get("DIGILOCKER_API_BASE",
                       "https://sandbox.api-setu.in" if ENV == "sandbox" else "https://api.apisetu.gov.in")
SSO = os.environ.get("DIGILOCKER_SSO_BASE",
                      "https://digilocker.meripehchaan.gov.in" if ENV != "sandbox"
                      else f"{BASE}/sso")

CLIENT_ID = os.environ.get("DIGILOCKER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DIGILOCKER_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get(
    "DIGILOCKER_REDIRECT_URI", "http://localhost:8000/auth/digilocker/callback"
)

# purpose-bound scopes: only what personalization needs
SCOPES = "userdetails,files.issueddocs"


def new_verifier() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).digest()
    import base64
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return raw, challenge


def authorize_url(state: str) -> tuple[str, str]:
    """Return (url, code_verifier). Persist verifier keyed by state server-side."""
    verifier, challenge = new_verifier()
    q = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    })
    return f"{SSO}/public/oauth2/1/authorize?{q}", verifier


def exchange_code(code: str, verifier: str) -> dict:
    r = httpx.post(
        f"{SSO}/public/oauth2/1/token",
        data={"grant_type": "authorization_code", "code": code,
              "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID,
              "client_secret": CLIENT_SECRET, "code_verifier": verifier},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def fetch_issued_docs(access_token: str) -> dict:
    r = httpx.get(f"{BASE}/digilocker/issueddocs",
                  headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def kind_from_doctype(doctype: str) -> str:
    d = doctype.lower()
    if "udyam" in d or "udyog" in d:
        return "udyam"
    if "pan" in d:
        return "pan"
    if "aadhaar" in d or "aadhar" in d or "adhar" in d:
        return "aadhaar"
    if "driving" in d or "licence" in d or "license" in d or "drvlc" in d:
        return "dl"
    if "gst" in d:
        return "gstin"
    return "other"
