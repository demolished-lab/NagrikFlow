"""Civic Path Navigator API: auth -> consent -> vault -> personalized dashboard."""
import json
import os
import re
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
from sqlmodel import Session, SQLModel, create_engine, select

from .models import Consent, LinkCode, Progress, TaskMap, User, VaultItem


def _load_env():
    envf = Path(__file__).resolve().parent.parent / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

from . import auth as authmod  # noqa: E402  (needs .env first)
from . import digilocker as dg  # noqa: E402
from . import eligibility as elig  # noqa: E402
from . import llm as llmmod  # noqa: E402
from . import worker as workermod  # noqa: E402
from . import watch as watchmod  # noqa: E402

ADMIN_EMAILS = {e.strip().lower() for e in
                os.environ.get("ADMIN_EMAILS", "demo@civic.test").split(",") if e.strip()}

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./civic.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="Civic Path Navigator")


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> User:
    if not creds:
        raise HTTPException(401, "login required")
    payload = authmod.verify_token(creds.credentials)
    if not payload:
        raise HTTPException(401, "invalid/expired session")
    with Session(engine) as s:
        user = s.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "unknown user")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "admin only")
    return user


class RegisterIn(BaseModel):
    email: str
    password: str
    name: str = ""
    city: str = ""
    state: str = ""


def _valid_email(e: str) -> bool:
    return bool(EMAIL_RE.match(e or ""))


def _init_db():
    SQLModel.metadata.create_all(engine)
    seed = Path(__file__).resolve().parent.parent / "data" / "udyam_seed.json"
    with Session(engine) as s:
        if not s.exec(select(TaskMap).where(TaskMap.slug == "udyam-register")).first():
            d = json.loads(seed.read_text())
            s.add(TaskMap(slug=d["slug"], title=d["title"], city=d["city"],
                          graph_json=json.dumps({"nodes": d["nodes"], "edges": d["edges"]}),
                          source_urls=json.dumps(d["source_urls"])))
            s.commit()


_init_db()


@app.get("/health")
def health():
    return {"ok": True, "digilocker_env": dg.ENV}


@app.post("/auth/register")
def register(body: RegisterIn):
    if not _valid_email(body.email) or len(body.password) < 4:
        raise HTTPException(400, "valid email + password (4+ chars) required")
    with Session(engine) as s:
        if s.exec(select(User).where(User.email == body.email)).first():
            raise HTTPException(409, "email already registered")
        u = User(email=body.email, name=body.name, city=body.city, state=body.state,
                 password_hash=authmod.hash_password(body.password),
                 is_admin=body.email.lower() in ADMIN_EMAILS)
        s.add(u)
        s.commit()
        s.refresh(u)
        return {"token": authmod.issue_token(u.id, u.email), "user_id": u.id}


@app.post("/auth/login")
def login(body: RegisterIn):
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == body.email)).first()
        if not u or not authmod.check_password(body.password, u.password_hash):
            raise HTTPException(401, "bad credentials")
        return {"token": authmod.issue_token(u.id, u.email), "user_id": u.id}


@app.get("/auth/digilocker/connect")
def dl_connect(user: User = Depends(current_user)):
    """Step 1: returns the MeriPehchaan consent URL. State binds user_id."""
    url, verifier = dg.authorize_url(state=f"{user.id}")
    # NOTE: production must persist verifier server-side keyed by state (Redis/DB).
    return {"authorize_url": url, "pkce_verifier": verifier,
            "note": "save verifier; POST it with code to /auth/digilocker/callback"}


class DLCallback(BaseModel):
    code: str
    verifier: str


@app.post("/auth/digilocker/callback")
def dl_callback(body: DLCallback, user: User = Depends(current_user)):
    """Step 2: exchange code, pull issued docs, store consent receipt + vault facts."""
    tokens = dg.exchange_code(body.code, body.verifier)
    docs = dg.fetch_issued_docs(tokens["access_token"])
    kinds = set()
    with Session(engine) as s:
        s.add(Consent(user_id=user.id, purpose="digilocker.documents.read",
                      scopes=dg.SCOPES))
        for d in docs.get("files", docs if isinstance(docs, list) else []):
            kind = dg.kind_from_doctype(d.get("doctype", d.get("name", "")))
            kinds.add(kind)
            if not s.exec(select(VaultItem).where(
                    VaultItem.user_id == user.id,
                    VaultItem.reference == d.get("uri", ""))).first():
                s.add(VaultItem(user_id=user.id, kind=kind,
                                label=d.get("name", kind),
                                issuer=d.get("issuer", ""),
                                reference=d.get("uri", "")))
        s.commit()
    return {"imported_kinds": sorted(kinds)}


@app.get("/me/dashboard")
def dashboard(user: User = Depends(current_user)):
    """Personalized dashboard: what you have, unlocked paths, next easiest."""
    with Session(engine) as s:
        items = s.exec(select(VaultItem).where(VaultItem.user_id == user.id)).all()
        progs = s.exec(select(Progress).where(Progress.user_id == user.id)).all()
        per_map: dict = {}
        for p in progs:
            per_map[p.map_slug] = per_map.get(p.map_slug, 0) + 1
    board = elig.personalize({i.kind for i in items}, per_map)
    board["user"] = {"name": user.name, "city": user.city, "state": user.state}
    return board


@app.get("/me/brief")
def brief(user: User = Depends(current_user)):
    """LLM-phrased plain-words summary of your dashboard (local first)."""
    board = dashboard(user)
    text, via = llmmod.phrase_dashboard(board)
    return {"brief": text, "via": via}


@app.get("/maps/{slug}")
def get_map(slug: str, user: User = Depends(current_user)):
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        return {"slug": m.slug, "title": m.title, "city": m.city,
                "graph": json.loads(m.graph_json),
                "sources": json.loads(m.source_urls), "verified": m.verified_at}


class DoneIn(BaseModel):
    map_slug: str
    step_id: str


@app.post("/me/progress")
def mark_done(body: DoneIn, user: User = Depends(current_user)):
    with Session(engine) as s:
        if not s.exec(select(Progress).where(
                Progress.user_id == user.id, Progress.map_slug == body.map_slug,
                Progress.step_id == body.step_id)).first():
            s.add(Progress(user_id=user.id, map_slug=body.map_slug,
                           step_id=body.step_id))
            s.commit()
    return {"ok": True}


# ---------------- Per-user channel linking ----------------
# App-level secrets (ONE bot, ONE DigiLocker requester) identify OUR app.
# Per-user tokens (each citizen's DigiLocker access_token, each citizen's
# Telegram chat_id) are bound to user_id and never cross users.


@app.post("/me/telegram/link-code")
def telegram_link_code(user: User = Depends(current_user)):
    """Generate a one-time code. User sends '/start CODE' to our bot; the
    webhook binds that chat id to ONLY this user."""
    import secrets as _secrets
    code = _secrets.token_hex(4).upper()
    with Session(engine) as s:
        s.add(LinkCode(user_id=user.id, code=code))
        s.commit()
    return {"code": code, "expires_min": 15,
            "instruction": "Send '/start {}' to our Telegram bot.".format(code)}


@app.post("/hooks/telegram")
def telegram_webhook(body: dict):
    """Bot API webhook. Binds chat_id via link code; enforces expiry + single use."""
    from datetime import datetime, timedelta, timezone
    try:
        msg = body.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text", "") or "").strip()
    except Exception:
        raise HTTPException(400, "bad update")
    if not chat_id or not text.startswith("/start"):
        return {"ok": True}
    parts = text.split()
    if len(parts) < 2:
        return {"ok": True, "reply": "Send /start YOURCODE from your dashboard."}
    with Session(engine) as s:
        link = s.exec(select(LinkCode).where(LinkCode.code == parts[1].upper())).first()
        if not link or link.used_at:
            return {"ok": True, "reply": "Invalid or used code. Generate a fresh one."}
        age = datetime.now(timezone.utc) - link.created_at.replace(tzinfo=timezone.utc) \
            if link.created_at.tzinfo is None else datetime.now(timezone.utc) - link.created_at
        if age > timedelta(minutes=15):
            return {"ok": True, "reply": "Code expired. Generate a fresh one."}
        # chat belongs to exactly one user: refuse if bound elsewhere
        other = s.exec(select(User).where(User.telegram_chat == chat_id)).first()
        me = s.get(User, link.user_id)
        if other and other.id != me.id:
            return {"ok": True, "reply": "This chat is already linked to another account."}
        me.telegram_chat = chat_id
        link.used_at = datetime.now(timezone.utc)
        s.add(me)
        s.add(link)
        s.commit()
        try:
            from . import alerts as alertsmod
            alertsmod.send(chat_id, "✅ Alerts linked. You'll get due-date and change pings here.")
        except Exception:
            pass
    return {"ok": True, "linked": True}


# ---------------- Admin desk ----------------

@app.get("/admin/maps")
def admin_maps(admin: User = Depends(require_admin)):
    with Session(engine) as s:
        maps = s.exec(select(TaskMap)).all()
        return [{"slug": m.slug, "title": m.title, "city": m.city,
                 "verified": m.verified_at,
                 "steps": len(json.loads(m.graph_json).get("nodes", [])),
                 "hash": m.content_hash, "checked": m.checked_at,
                 "sources": json.loads(m.source_urls)} for m in maps]


class VerifyIn(BaseModel):
    verified: bool = True


@app.post("/admin/maps/{slug}/verify")
def admin_verify(slug: str, body: VerifyIn, admin: User = Depends(require_admin)):
    from datetime import datetime, timezone
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        m.verified_at = datetime.now(timezone.utc) if body.verified else None
        s.add(m)
        s.commit()
        return {"slug": slug, "verified": m.verified_at}


class BuildIn(BaseModel):
    task: str
    slug: str
    urls: list[str]


@app.post("/admin/build-map")
def admin_build(body: BuildIn, admin: User = Depends(require_admin)):
    """Run scrape cascade + extraction now (slow: minutes). Saves UNVERIFIED map."""
    if not body.urls or len(body.urls) > 5:
        raise HTTPException(400, "1-5 urls required")
    result = workermod.build_map(body.task, body.urls)
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == body.slug)).first()
        payload = json.dumps({"nodes": result["nodes"], "edges": result["edges"]})
        if m:
            m.title, m.graph_json = body.task, payload
            m.source_urls = json.dumps(result["sources"])
            m.verified_at = None
            s.add(m)
        else:
            s.add(TaskMap(slug=body.slug, title=body.task, graph_json=payload,
                          source_urls=json.dumps(result["sources"])))
        s.commit()
    return {"slug": body.slug, "steps": len(result["nodes"]),
            "sources": result["sources"], "verified": None,
            "baseline": watchmod.recheck(engine, body.slug)}


class RecheckIn(BaseModel):
    slug: str = ""


@app.post("/admin/recheck")
def admin_recheck(body: RecheckIn, admin: User = Depends(require_admin)):
    """Night-watchman run: None (all maps) or one slug. Slow: fetches sources."""
    return watchmod.recheck(engine, body.slug or None)
