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
from . import security as secmod  # noqa: E402
from . import notify as notifmod  # noqa: E402
from . import jobs as jobsmod  # noqa: E402
from . import discover as discovermod  # noqa: E402
from . import obs as obsmod  # noqa: E402
from . import backup as backupmod  # noqa: E402
from . import edge as edgemod  # noqa: E402
from fastapi import BackgroundTasks as _BT  # noqa: E402
from .models import Consent, Job, LinkCode, OAuthState, OtpCode, Progress, TaskMap, User, VaultItem

ADMIN_EMAILS = {e.strip().lower() for e in
                os.environ.get("ADMIN_EMAILS", "demo@civic.test").split(",") if e.strip()}

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./civic.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="Civic Path Navigator")
app.middleware("http")(secmod.rate_limit_middleware)
app.middleware("http")(obsmod.obs_middleware)
edgemod.install(app)


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
    from . import migrate as migratemod
    migratemod.migrate(engine)


_init_db()


@app.get("/health")
def health():
    return {"ok": True, "digilocker_env": dg.ENV}


@app.post("/auth/register")
def register(body: RegisterIn):
    if not _valid_email(body.email) or len(body.password) < 4:
        raise HTTPException(400, "valid email + password (4+ chars) required")
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
    from datetime import datetime, timezone
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == body.email)).first()
        if u and u.locked_until and u.locked_until.replace(tzinfo=timezone.utc) \
                > datetime.now(timezone.utc):
            raise HTTPException(423, "account locked: too many failed attempts, try later")
        if not u or not authmod.check_password(body.password, u.password_hash):
            if u:
                u.failed_attempts += 1
                if u.failed_attempts >= secmod.MAX_FAILS:
                    from datetime import timedelta as _td
                    u.locked_until = datetime.now(timezone.utc) + _td(seconds=secmod.LOCK_SECONDS)
                    u.failed_attempts = 0
                s.add(u)
                s.commit()
            raise HTTPException(401, "bad credentials")
        u.failed_attempts = 0
        u.locked_until = None
        s.add(u)
        s.commit()
        return {"token": authmod.issue_token(u.id, u.email), "user_id": u.id}


class OtpReq(BaseModel):
    email: str


@app.post("/auth/otp/request")
def otp_request(body: OtpReq):
    """Passwordless login step 1. Always returns ok (no account enumeration)."""
    import hashlib as _hl
    import secrets as _secrets
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == body.email)).first()
        if u:
            code = f"{_secrets.randbelow(900000) + 100000}"
            s.add(OtpCode(user_id=u.id,
                          code_hash=_hl.sha256(code.encode()).hexdigest()))
            s.commit()
            subj, text = notifmod.otp_message(code)
            try:
                notifmod.send(u.email, subj, text)
            except Exception:
                pass
    return {"ok": True}


class OtpVerify(BaseModel):
    email: str
    code: str


@app.post("/auth/otp/verify")
def otp_verify(body: OtpVerify):
    from datetime import datetime, timedelta, timezone
    import hashlib as _hl
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == body.email)).first()
        if not u:
            raise HTTPException(401, "bad code")
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        cands = s.exec(select(OtpCode).where(
            OtpCode.user_id == u.id, OtpCode.used_at.is_(None))).all()
        good = None
        for c0 in cands:
            created = c0.created_at.replace(tzinfo=timezone.utc) \
                if c0.created_at.tzinfo is None else c0.created_at
            if created >= cutoff and c0.code_hash == _hl.sha256(body.code.encode()).hexdigest():
                good = c0
                break
        if not good:
            raise HTTPException(401, "bad code")
        good.used_at = datetime.now(timezone.utc)
        u.failed_attempts = 0
        u.locked_until = None
        s.add(good)
        s.add(u)
        s.commit()
        return {"token": authmod.issue_token(u.id, u.email), "user_id": u.id}


@app.get("/auth/digilocker/connect")
def dl_connect(user: User = Depends(current_user)):
    """Step 1: persist PKCE verifier server-side, return consent URL + state."""
    import secrets as _secrets
    state = f"{user.id}.{_secrets.token_hex(8)}"
    url, verifier = dg.authorize_url(state=state)
    with Session(engine) as s:
        s.add(OAuthState(user_id=user.id, state=state, verifier=verifier))
        s.commit()
    return {"authorize_url": url, "state": state}


class DLCallback(BaseModel):
    code: str
    state: str = ""
    verifier: str = ""  # legacy clients holding their own verifier


@app.post("/auth/digilocker/callback")
def dl_callback(body: DLCallback, user: User = Depends(current_user)):
    """Step 2: resolve user-bound verifier, single-use, then exchange + import."""
    verifier = body.verifier
    with Session(engine) as s:
        if body.state:
            row = s.exec(select(OAuthState).where(
                OAuthState.state == body.state,
                OAuthState.user_id == user.id)).first()
            if not row:
                raise HTTPException(400, "unknown or foreign oauth state")
            verifier = row.verifier
            s.delete(row)
            s.commit()
        if not verifier:
            raise HTTPException(400, "verifier required")
    tokens = dg.exchange_code(body.code, verifier)
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
    board = elig.personalize({i.kind for i in items}, per_map, [
        {"kind": i.kind, "label": i.label,
         "expires_at": i.expires_at.isoformat() if i.expires_at else "",
         "meta": i.meta} for i in items])
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


@app.post("/admin/jobs/build")
def job_build(body: BuildIn, bg: _BT, admin: User = Depends(require_admin)):
    """Enqueue build-map; poll GET /admin/jobs/{id}. Returns immediately."""
    if not body.urls or len(body.urls) > 5:
        raise HTTPException(400, "1-5 urls required")
    with Session(engine) as s:
        j = Job(kind="build", created_by=admin.id,
                payload=json.dumps({"task": body.task, "slug": body.slug,
                                    "urls": body.urls}))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    bg.add_task(jobsmod.run_build, engine, jid)
    return {"job_id": jid, "status": "queued"}


@app.post("/admin/jobs/recheck")
def job_recheck(body: RecheckIn, bg: _BT, admin: User = Depends(require_admin)):
    with Session(engine) as s:
        j = Job(kind="recheck", created_by=admin.id,
                payload=json.dumps({"slug": body.slug}))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    bg.add_task(jobsmod.run_recheck, engine, jid)
    return {"job_id": jid, "status": "queued"}


@app.get("/admin/jobs/{job_id}")
def job_status(job_id: int, admin: User = Depends(require_admin)):
    from .models import Job as JobModel
    with Session(engine) as s:
        j = s.get(JobModel, job_id)
        if not j:
            raise HTTPException(404, "unknown job")
        return {"job_id": j.id, "kind": j.kind, "status": j.status,
                "result": json.loads(j.result), "finished": j.finished_at}


@app.get("/admin/metrics")
def admin_metrics(admin: User = Depends(require_admin)):
    """Request counts, error counts, avg latency per route (in-memory)."""
    return obsmod.snapshot()


@app.post("/admin/backup")
def admin_backup(admin: User = Depends(require_admin)):
    """Online snapshot now (E: by default). Pair with Task Scheduler daily."""
    return backupmod.run(engine)


@app.get("/admin/backups")
def admin_backups(admin: User = Depends(require_admin)):
    return backupmod.listing()


class DiscoverIn(BaseModel):
    task: str
    max_results: int = 8


@app.post("/admin/discover")
def admin_discover(body: DiscoverIn, admin: User = Depends(require_admin)):
    """Keyless gov-URL discovery (wigolo) — feeds /admin/jobs/build."""
    if not body.task.strip():
        raise HTTPException(400, "task required")
    return {"task": body.task,
            "urls": discovermod.discover(body.task, min(body.max_results, 10))}
