"""Civic Path Navigator API: auth -> consent -> vault -> personalized dashboard."""
import json
import os
import re
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Header, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from .https_middleware import HTTPSRedirectMiddleware

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy import delete as _sa_delete, text as _sa_text


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
from . import agent as agentmod  # noqa: E402
from . import hermes_core as hermesmod  # noqa: E402
from . import hermes_subagents as submod  # noqa: E402
from . import telegram_validate as tgramval  # noqa: E402
from . import llm_health as llmhealth  # noqa: E402
from fastapi import BackgroundTasks as _BT  # noqa: E402
from .models import (Consent, Grievance, Job, LinkCode, Notification, OAuthState,
                     OtpCode, Progress, RoadmapMilestone, TaskMap, User, VaultItem)

ADMIN_DEFAULT = "demo@civic.test" if os.environ.get("ALLOW_DEV_SECRET") == "1" else ""
ADMIN_EMAILS = {e.strip().lower() for e in
                os.environ.get("ADMIN_EMAILS", ADMIN_DEFAULT).split(",") if e.strip()}

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./civic.db")
ENGINE_KWARGS = {"connect_args": {"check_same_thread": False}} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, **ENGINE_KWARGS)
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="Civic Path Navigator")
FRONTEND_ORIGINS = [o.strip() for o in os.environ.get(
    "FRONTEND_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(secmod.rate_limit_middleware)
app.middleware("http")(obsmod.obs_middleware)
edgemod.install(app)

# Add HTTPS redirect middleware if configured for production
if os.environ.get("FORCE_HTTPS", "").lower() == "true":
    from .https_middleware import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)


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


def _validate_fetch_url(url: str) -> str:
    """Allow public HTTPS government sources only; block SSRF targets."""
    try:
        parsed = urlparse(url)
        local_dev = os.environ.get("CIVIC_DEV") == "1" and parsed.hostname in {"localhost", "127.0.0.1"}
        if (parsed.scheme != "https" and not local_dev) or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
        if local_dev:
            return url
        host = parsed.hostname.rstrip(".").lower()
        if not (host.endswith(".gov.in") or host.endswith(".nic.in") or host in {"gov.in", "nic.in"}):
            raise ValueError
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if any(ipaddress.ip_address(addr).is_private or ipaddress.ip_address(addr).is_loopback
               or ipaddress.ip_address(addr).is_link_local or ipaddress.ip_address(addr).is_reserved
               for addr in addresses):
            raise ValueError
    except (ValueError, socket.gaierror, OSError):
        raise HTTPException(400, "urls must be public HTTPS .gov.in or .nic.in sources")
    return url


def _init_db():
    from . import migrate as migratemod
    migratemod.migrate(engine)
    from . import nltk_guard as nltkguard
    nltkguard.install()  # pathsec guard for nltk model-artifact APIs (PYSEC-2026-3740)
    if os.environ.get("RECOVER_JOBS", "1") != "0":
        try:
            from . import jobs as jobsmod
            jobsmod.recover_orphans(engine)  # restart recovery for queued/running jobs
        except Exception:
            pass


_init_db()


@app.get("/health")
def health():
    return {"ok": True, "digilocker_env": dg.ENV}


@app.get("/healthz")
def healthz():
    """Liveness probe: process is up and serving (never rate limited)."""
    return {"ok": True, "status": "live"}


@app.get("/readyz")
def readyz():
    """Readiness probe: database reachable + schema present + Redis (if
    configured) answering. 503 when any required component fails."""
    checks: dict[str, str] = {}
    ok = True
    try:
        with engine.connect() as conn:
            conn.execute(_sa_text("SELECT 1"))
            conn.execute(_sa_text("SELECT count(*) FROM schemaversion"))
        checks["database"] = "ok"
        checks["migrations"] = "ok"
    except Exception as e:
        checks["database"] = f"fail: {type(e).__name__}"
        ok = False
    if os.environ.get("REDIS_URL", "").strip():
        from . import security_redis as srmod
        client = srmod.get_client()
        if client is None:
            srmod.reset()  # give Redis a reconnect chance on each probe
            client = srmod.get_client()
        checks["redis"] = "ok" if client is not None else "fail"
        ok = ok and client is not None
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": ok, "checks": checks}, 200 if ok else 503)


@app.get("/metrics")
def metrics(request: Request):
    """Prometheus text format. Optional METRICS_TOKEN guards scraping
    (Authorization: Bearer <token> or X-Metrics-Token)."""
    token = os.environ.get("METRICS_TOKEN", "").strip()
    if token:
        got = request.headers.get("x-metrics-token", "")
        auth = request.headers.get("authorization", "")
        if got != token and auth != f"Bearer {token}":
            raise HTTPException(401, "metrics token required")
    return Response(obsmod.prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/health/llm")
async def health_llm():
    """Check LLM backend availability (Bynara + Ollama)."""
    return await llmhealth.health_check()


@app.post("/auth/register")
def register(body: RegisterIn):
    if not _valid_email(body.email) or len(body.password) < 8:
        raise HTTPException(400, "valid email + password (8+ chars) required")
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
            # single active code: retire previous unused OTPs so they cannot
            # accumulate (and be brute-forced) inside the 10-minute window
            for old in s.exec(select(OtpCode).where(
                    OtpCode.user_id == u.id, OtpCode.used_at.is_(None))).all():
                old.used_at = datetime.now(timezone.utc)
                s.add(old)
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
        now = datetime.now(timezone.utc)
        if u.locked_until:
            locked = u.locked_until.replace(tzinfo=timezone.utc) \
                if u.locked_until.tzinfo is None else u.locked_until
            if locked > now:
                raise HTTPException(423, "account locked: too many failed attempts, try later")
            u.locked_until = None
        cutoff = now - timedelta(minutes=10)
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
            # per-account attempt limit (IP rate limiting alone is bypassable)
            u.failed_attempts += 1
            if u.failed_attempts >= secmod.MAX_FAILS:
                u.failed_attempts = 0
                u.locked_until = now + timedelta(seconds=secmod.LOCK_SECONDS)
            s.add(u)
            s.commit()
            raise HTTPException(401, "bad code")
        good.used_at = now
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


def _complete_dl_callback(code: str, state: str, user_id: int) -> dict:
    """Exchange a server-stored PKCE state exactly once and import documents."""
    with Session(engine) as s:
        row = s.exec(select(OAuthState).where(
            OAuthState.state == state, OAuthState.user_id == user_id)).first()
        if not row:
            raise HTTPException(400, "unknown, expired, or already-used oauth state")
        verifier = row.verifier
    tokens = dg.exchange_code(code, verifier)
    docs = dg.fetch_issued_docs(tokens["access_token"])
    kinds = set()
    with Session(engine) as s:
        current = s.get(OAuthState, row.id)
        if not current:
            raise HTTPException(400, "oauth state already used")
        s.delete(current)
        s.add(Consent(user_id=user_id, purpose="digilocker.documents.read",
                      scopes=dg.SCOPES))
        for d in docs.get("files", docs if isinstance(docs, list) else []):
            kind = dg.kind_from_doctype(d.get("doctype", d.get("name", "")))
            kinds.add(kind)
            if not s.exec(select(VaultItem).where(
                    VaultItem.user_id == user_id,
                    VaultItem.reference == d.get("uri", ""))).first():
                s.add(VaultItem(user_id=user_id, kind=kind,
                                label=d.get("name", kind),
                                issuer=d.get("issuer", ""),
                                reference=d.get("uri", "")))
        s.commit()
    return {"imported_kinds": sorted(kinds)}


@app.get("/auth/digilocker/callback")
def dl_callback_get(code: str, state: str):
    """Browser redirect callback; the unpredictable state binds it to its user."""
    with Session(engine) as s:
        row = s.exec(select(OAuthState).where(OAuthState.state == state)).first()
        if not row:
            raise HTTPException(400, "unknown, expired, or already-used oauth state")
        user_id = row.user_id
    return _complete_dl_callback(code, state, user_id)


@app.post("/auth/digilocker/callback")
def dl_callback(body: DLCallback, user: User = Depends(current_user)):
    """API callback for clients that receive the provider redirect themselves."""
    if not body.state:
        raise HTTPException(400, "state required")
    return _complete_dl_callback(body.code, body.state, user.id)


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


@app.get("/me/profile")
def profile(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name,
            "city": user.city, "state": user.state,
            "role": "admin" if user.is_admin else "citizen"}


@app.get("/me/pathways")
def my_pathways(user: User = Depends(current_user)):
    """List only pathways requested by this user, joined to their saved maps."""
    with Session(engine) as s:
        jobs = s.exec(select(Job).where(
            Job.created_by == user.id, Job.kind == "build"
        ).order_by(Job.created_at.desc()).limit(50)).all()
        pathways = []
        for job in jobs:
            try:
                request_data = json.loads(job.payload or "{}")
                result_data = json.loads(job.result or "{}")
            except (TypeError, json.JSONDecodeError):
                request_data, result_data = {}, {}
            slug = result_data.get("slug") or request_data.get("slug")
            if not slug:
                continue
            task_map = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
            graph = json.loads(task_map.graph_json) if task_map else {"nodes": [], "edges": []}
            nodes = graph.get("nodes", [])
            completed = s.exec(select(Progress).where(
                Progress.user_id == user.id, Progress.map_slug == slug
            )).all() if task_map else []
            if job.status == "failed":
                status = "failed"
            elif not task_map:
                status = job.status
            else:
                status = "verified" if task_map.verified_at else "review_required"
            try:
                sources = json.loads(task_map.source_urls or "[]") if task_map else []
            except json.JSONDecodeError:
                sources = []
            pathways.append({
                "job_id": job.id,
                "slug": slug,
                "title": task_map.title if task_map else request_data.get("task", "Civic pathway"),
                "city": (task_map.city or request_data.get("city", "")) if task_map else request_data.get("city", ""),
                "state": (task_map.state or request_data.get("state", "")) if task_map else request_data.get("state", ""),
                "status": status,
                "verified": bool(task_map and task_map.verified_at),
                "verified_at": task_map.verified_at.isoformat() if task_map and task_map.verified_at else None,
                "steps": len(nodes),
                "completed": len(completed),
                "completed_steps": [item.step_id for item in completed],
                "steps_preview": [{key: node.get(key, "") for key in ("id", "title", "detail", "url", "type")}
                                  for node in nodes[:4]],
                "sources": sources,
                "created_at": job.created_at.isoformat(),
                "error": result_data.get("error", "") if job.status == "failed" else "",
            })
        return pathways


@app.get("/me/brief")
def brief(user: User = Depends(current_user)):
    """LLM-phrased plain-words summary of your dashboard (local first)."""
    board = dashboard(user)
    text, via = llmmod.phrase_dashboard(board)
    return {"brief": text, "via": via}


@app.get("/maps/{slug}")
def get_map(
    slug: str,
    node_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    user: User = Depends(current_user),
):
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        # Unverified maps are visible only to their builder and admins
        # (404, not 403, so slugs of unverified maps don't leak existence).
        if not m.verified_at and not user.is_admin and m.created_by != user.id:
            raise HTTPException(404, "unknown map")
        graph = json.loads(m.graph_json)
        completed = {p.step_id for p in s.exec(select(Progress).where(
            Progress.user_id == user.id, Progress.map_slug == slug)).all()}

    def node_status(node: dict) -> str:
        if node.get("id") in completed:
            return "verified"
        if node.get("type") == "action":
            return "action"
        if node.get("type") == "unlocked":
            return "unlocked"
        return "ready"

    all_nodes = graph.get("nodes", [])
    normalized_q = q.strip().lower() if q else ""
    filtered_nodes = [node for node in all_nodes if
                      (not node_type or node.get("type") == node_type) and
                      (not status or node_status(node) == status) and
                      (not normalized_q or normalized_q in " ".join([
                          str(node.get("title", "")), str(node.get("detail", "")),
                          str(node.get("fee", ""))]).lower())]
    visible_ids = {node.get("id") for node in filtered_nodes}
    filtered_edges = [edge for edge in graph.get("edges", [])
                      if len(edge) >= 2 and edge[0] in visible_ids and edge[1] in visible_ids]
    filter_options = {
        "types": sorted({str(node.get("type")) for node in all_nodes if node.get("type")}),
        "statuses": sorted({node_status(node) for node in all_nodes}),
        "total": len(all_nodes),
    }
    return {"slug": m.slug, "title": m.title, "city": m.city, "state": m.state,
            "service_type": m.service_type,
            "graph": {"nodes": filtered_nodes, "edges": filtered_edges},
            "filters": filter_options, "sources": json.loads(m.source_urls),
            "verified": bool(m.verified_at),
            "edge_sources": json.loads(m.edge_sources) if m.edge_sources else {}}


class DoneIn(BaseModel):
    map_slug: str
    step_id: str


@app.post("/me/progress")
def mark_done(body: DoneIn, user: User = Depends(current_user)):
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == body.map_slug)).first()
        if not m or not m.verified_at:
            raise HTTPException(404, "unknown or unverified map")
        node_ids = {n.get("id") for n in json.loads(m.graph_json).get("nodes", [])}
        if body.step_id not in node_ids:
            raise HTTPException(400, "unknown step for map")
        if not s.exec(select(Progress).where(
                Progress.user_id == user.id, Progress.map_slug == body.map_slug,
                Progress.step_id == body.step_id)).first():
            s.add(Progress(user_id=user.id, map_slug=body.map_slug,
                           step_id=body.step_id))
            s.commit()
    return {"ok": True}


@app.get("/me/progress/{map_slug}")
def get_progress(map_slug: str, user: User = Depends(current_user)):
    with Session(engine) as s:
        return {"steps": [p.step_id for p in s.exec(select(Progress).where(
            Progress.user_id == user.id, Progress.map_slug == map_slug)).all()]}


def _ensure_milestones(user: User, map_slug: str) -> list[dict]:
    """Create stable, per-user deadlines for map nodes the first time they are viewed."""
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        task_map = s.exec(select(TaskMap).where(TaskMap.slug == map_slug)).first()
        if not task_map or not task_map.verified_at:
            raise HTTPException(404, "unknown or unverified map")
        nodes = json.loads(task_map.graph_json).get("nodes", [])
        completed = {p.step_id for p in s.exec(select(Progress).where(
            Progress.user_id == user.id, Progress.map_slug == map_slug)).all()}
        rows = s.exec(select(RoadmapMilestone).where(
            RoadmapMilestone.user_id == user.id,
            RoadmapMilestone.map_slug == map_slug)).all()
        by_step = {row.step_id: row for row in rows}
        for index, node in enumerate(nodes):
            step_id = str(node.get("id", ""))
            if not step_id or step_id in by_step:
                continue
            row = RoadmapMilestone(user_id=user.id, map_slug=map_slug,
                                   step_id=step_id,
                                   due_at=now + timedelta(days=(index + 1) * 7))
            s.add(row)
            by_step[step_id] = row
        s.commit()
        for row in by_step.values():
            if row.step_id in completed and row.status != "completed":
                row.status = "completed"
                s.add(row)
        s.commit()
        return [{
            "id": row.id, "map_slug": row.map_slug, "step_id": row.step_id,
            "title": next((n.get("title", row.step_id) for n in nodes
                            if n.get("id") == row.step_id), row.step_id),
            "due_at": row.due_at.isoformat(),
            "status": "completed" if row.step_id in completed else row.status,
            "days_left": (row.due_at - now).days,
        } for row in sorted(by_step.values(), key=lambda item: item.due_at)]


@app.get("/me/milestones/{map_slug}")
def get_milestones(map_slug: str, user: User = Depends(current_user)):
    return {"milestones": _ensure_milestones(user, map_slug)}


@app.get("/me/notifications")
def get_notifications(user: User = Depends(current_user)):
    milestones = _ensure_milestones(user, "udyam-register")
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        for milestone in milestones:
            if milestone["status"] == "completed" or milestone["days_left"] > 7:
                continue
            reference = f"deadline:{milestone['map_slug']}:{milestone['step_id']}:{milestone['due_at']}"
            exists = s.exec(select(Notification).where(
                Notification.user_id == user.id, Notification.reference == reference)).first()
            if exists:
                continue
            overdue = milestone["days_left"] < 0
            title = f"Overdue milestone: {milestone['title']}" if overdue else f"Upcoming milestone: {milestone['title']}"
            body = (f"{milestone['title']} was due {abs(milestone['days_left'])} days ago."
                    if overdue else f"{milestone['title']} is due in {milestone['days_left']} days.")
            s.add(Notification(user_id=user.id, kind="deadline", reference=reference,
                               title=title, body=body))
        s.commit()
        rows = s.exec(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc())).all()
        return {"notifications": [{"id": row.id, "kind": row.kind, "title": row.title,
                                    "body": row.body, "read": bool(row.read_at),
                                    "created_at": row.created_at.isoformat()}
                                   for row in rows[:30]],
                "unread": sum(1 for row in rows if row.read_at is None)}


@app.post("/me/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(current_user)):
    with Session(engine) as s:
        row = s.exec(select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id)).first()
        if not row:
            raise HTTPException(404, "notification not found")
        row.read_at = datetime.now(timezone.utc)
        s.add(row)
        s.commit()
    return {"ok": True}


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _make_text_pdf(lines: list[str]) -> bytes:
    """Create a small dependency-free PDF report using a standard Type1 font."""
    content = ["BT", "/F1 11 Tf", "50 770 Td"]
    for index, line in enumerate(lines[:48]):
        if index:
            content.append("0 -15 Td")
        content.append(f"({_pdf_escape(line[:110])}) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


@app.get("/me/progress-report.pdf")
def progress_report_pdf(user: User = Depends(current_user)):
    milestones = _ensure_milestones(user, "udyam-register")
    completed = sum(item["status"] == "completed" for item in milestones)
    lines = [
        "Civic Path Navigator — Personalized Progress Report",
        f"Citizen: {user.name or user.email}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Roadmap: Register a small business (Udyam + GST + Shops)",
        f"Progress: {completed} of {len(milestones)} milestones completed",
        "",
    ]
    for item in milestones:
        marker = "COMPLETED" if item["status"] == "completed" else f"DUE {item['due_at'][:10]}"
        lines.append(f"[{marker}] {item['title']}")
    return Response(content=_make_text_pdf(lines), media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=civic-progress-report.pdf"})


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
def telegram_webhook(body: dict, x_telegram_token: str = Header(default=None)):
    """Bot API webhook. Binds chat_id via link code; enforces expiry + single use."""
    # Validate Telegram webhook secret if configured
    try:
        tgramval.check(x_telegram_token)
    except ValueError as e:
        raise HTTPException(401, str(e))
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


VERIFY_MAX_AGE_DAYS = int(os.environ.get("VERIFY_MAX_AGE_DAYS", "45"))


def _graph_error(graph_json: str) -> str | None:
    """Structural validation for admin verification: parseable, has steps,
    no dangling edge endpoints, acyclic."""
    try:
        g = json.loads(graph_json or "{}")
    except Exception:
        return "graph is not valid JSON"
    nodes = g.get("nodes") or []
    edges = g.get("edges") or []
    if not nodes:
        return "graph has no steps"
    ids = {str(n.get("id")) for n in nodes if n.get("id") is not None}
    if not ids:
        return "graph steps have no ids"
    for e in edges:
        if len(e) < 2 or str(e[0]) not in ids or str(e[1]) not in ids:
            return f"edge references an unknown step: {e!r}"
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for e in edges:
        a, b = str(e[0]), str(e[1])
        adj[a].append(b)
        indeg[b] += 1
    stack = [i for i, d in indeg.items() if d == 0]
    seen = 0
    while stack:
        n = stack.pop()
        seen += 1
        for nxt in adj[n]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                stack.append(nxt)
    if seen != len(ids):
        return "graph contains a cycle"
    return None


def _provenance_error(m) -> str | None:
    """Fresh-provenance requirement: sources + content hash + recent check."""
    from datetime import datetime, timedelta, timezone
    try:
        urls = json.loads(m.source_urls or "[]")
    except Exception:
        urls = []
    if not urls:
        return "map has no source_urls"
    if not m.content_hash:
        return "map has no content_hash (run a recheck first)"
    if not m.checked_at:
        return "map was never checked (run a recheck first)"
    checked = m.checked_at.replace(tzinfo=timezone.utc) \
        if m.checked_at.tzinfo is None else m.checked_at
    age = datetime.now(timezone.utc) - checked
    if age > timedelta(days=VERIFY_MAX_AGE_DAYS):
        return (f"provenance is {age.days}d old (limit {VERIFY_MAX_AGE_DAYS}d) "
                "- run a recheck first")
    return None


@app.post("/admin/maps/{slug}/verify")
def admin_verify(slug: str, body: VerifyIn, admin: User = Depends(require_admin)):
    from datetime import datetime, timezone
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        if body.verified:
            err = _graph_error(m.graph_json) or _provenance_error(m)
            if err:
                raise HTTPException(400, f"cannot verify: {err}")
        m.verified_at = datetime.now(timezone.utc) if body.verified else None
        s.add(m)
        s.commit()
        return {"slug": slug, "verified": m.verified_at}


# ---- Per-step admin editing (review, validate, UPDATE extracted info) ----

STEP_TYPES = {"prereq", "action", "payment", "visit", "unlocked", "document"}


class StepIn(BaseModel):
    title: str
    detail: str = ""
    fee: str = ""
    url: str = ""    # official source page (proof link)
    link: str = ""   # per-step application/form deep link
    type: str = "action"
    depends_on: list[str] = []  # used when adding a step


def _slug_step(title: str, existing: set) -> str:
    base = re.sub(r"\W+", "-", title.strip().lower()).strip("-")[:40] or "step"
    sid, n = base, 2
    while sid in existing:
        sid, n = f"{base}-{n}", n + 1
    return sid


@app.get("/admin/maps/{slug}/steps")
def admin_map_steps(slug: str, admin: User = Depends(require_admin)):
    """Full node/edge graph for the step editor."""
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        g = json.loads(m.graph_json)
        return {"slug": slug, "title": m.title,
                "nodes": g.get("nodes", []), "edges": g.get("edges", [])}


@app.put("/admin/maps/{slug}/steps/{step_id}")
def admin_update_step(slug: str, step_id: str, body: StepIn,
                      admin: User = Depends(require_admin)):
    """Edit an extracted step in place (title/detail/fee/url/type)."""
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title required")
    url = body.url.strip()
    if url:
        url = _validate_fetch_url(url)  # SSRF + .gov/.nic policy applies to edits too
    link = body.link.strip()
    if link:
        link = _validate_fetch_url(link)
    node_type = body.type if body.type in STEP_TYPES else "action"
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        g = json.loads(m.graph_json)
        node = next((n for n in g.get("nodes", []) if n.get("id") == step_id), None)
        if not node:
            raise HTTPException(404, "unknown step")
        before = dict(node)
        node.update({"title": title, "detail": body.detail.strip(),
                     "fee": body.fee.strip(), "url": url, "link": link,
                     "type": node_type})
        m.graph_json = json.dumps(g)
        m.verified_at = None  # content changed -> approval must be re-stamped
        s.add(m)
        s.commit()
    from . import audit as auditmod
    auditmod.append("admin_step_edit", f"{slug}/{step_id}",
                    f"Edited step '{title}'", diff_before=json.dumps(before),
                    diff_after=json.dumps(node), agent="admin")
    return {"slug": slug, "node": node}


@app.post("/admin/maps/{slug}/steps")
def admin_add_step(slug: str, body: StepIn, admin: User = Depends(require_admin)):
    """Append a new step, optionally wired as a dependency of existing steps."""
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title required")
    url = body.url.strip()
    if url:
        url = _validate_fetch_url(url)
    link = body.link.strip()
    if link:
        link = _validate_fetch_url(link)
    node_type = body.type if body.type in STEP_TYPES else "action"
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        g = json.loads(m.graph_json)
        nodes, edges = g.get("nodes", []), g.get("edges", [])
        existing = {n.get("id") for n in nodes}
        missing = [d for d in body.depends_on if d not in existing]
        if missing:
            raise HTTPException(400, f"unknown depends_on: {', '.join(missing)}")
        new_id = _slug_step(title, existing)
        nodes.append({"id": new_id, "type": node_type, "title": title,
                      "detail": body.detail.strip(), "url": url, "link": link,
                      "fee": body.fee.strip()})
        # new node has no outgoing edges yet -> dep->new can never close a cycle
        for dep in body.depends_on:
            if [dep, new_id] not in edges:
                edges.append([dep, new_id])
        g["nodes"], g["edges"] = nodes, edges
        m.graph_json = json.dumps(g)
        m.verified_at = None  # content changed -> approval must be re-stamped
        s.add(m)
        s.commit()
    from . import audit as auditmod
    auditmod.append("admin_step_add", f"{slug}/{new_id}",
                    f"Added step '{title}'", diff_after=json.dumps(nodes[-1]),
                    agent="admin")
    return {"slug": slug, "node": nodes[-1], "edges": edges}


@app.delete("/admin/maps/{slug}/steps/{step_id}")
def admin_delete_step(slug: str, step_id: str, admin: User = Depends(require_admin)):
    """Remove a step and every edge that referenced it."""
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        g = json.loads(m.graph_json)
        before_nodes = list(g.get("nodes", []))
        kept = [n for n in g.get("nodes", []) if n.get("id") != step_id]
        if len(kept) == len(before_nodes):
            raise HTTPException(404, "unknown step")
        edges = [e for e in g.get("edges", [])
                 if len(e) >= 2 and step_id not in (e[0], e[1])]
        esrc = json.loads(m.edge_sources) if m.edge_sources else {}

        def _mentions(key: str) -> bool:
            if "|" in key:  # new format "a|b"
                a, _, b = key.partition("|")
                return step_id in (a, b)
            parts = re.findall(r"['\"]([^'\"]+)['\"]", key)  # legacy tuple repr
            return step_id in parts if parts else key == step_id

        esrc = {k: v for k, v in esrc.items() if not _mentions(k)}
        g["nodes"], g["edges"] = kept, edges
        m.graph_json = json.dumps(g)
        m.edge_sources = json.dumps(esrc)
        m.verified_at = None  # content changed -> approval must be re-stamped
        # a deleted step must not linger in user progress or milestone records
        s.exec(_sa_delete(Progress).where(Progress.map_slug == slug,
                                          Progress.step_id == step_id))
        s.exec(_sa_delete(RoadmapMilestone).where(RoadmapMilestone.map_slug == slug,
                                                  RoadmapMilestone.step_id == step_id))
        s.add(m)
        s.commit()
    from . import audit as auditmod
    auditmod.append("admin_step_delete", f"{slug}/{step_id}",
                    f"Deleted step '{step_id}'", diff_before=json.dumps(before_nodes),
                    agent="admin")
    return {"slug": slug, "removed": step_id, "steps": len(kept),
            "edges": len(edges)}


class BuildIn(BaseModel):
    task: str
    slug: str
    urls: list[str]


@app.post("/admin/build-map")
def admin_build(body: BuildIn, admin: User = Depends(require_admin)):
    """Run scrape cascade + extraction now (slow: minutes). Saves UNVERIFIED map."""
    if not body.urls or len(body.urls) > 5:
        raise HTTPException(400, "1-5 urls required")
    body.urls = [_validate_fetch_url(u) for u in body.urls]
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
    body.urls = [_validate_fetch_url(u) for u in body.urls]
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
        if jobsmod.fail_if_stale(j):
            s.add(j)
            s.commit()
        return {"job_id": j.id, "kind": j.kind, "status": j.status,
                "result": json.loads(j.result), "finished": j.finished_at}


@app.get("/admin/metrics")
def admin_metrics(admin: User = Depends(require_admin)):
    """Request counts, error counts, avg latency per route (in-memory)."""
    return obsmod.snapshot()


@app.get("/admin/integrations")
async def admin_integrations(probe: bool = False,
                             admin: User = Depends(require_admin)):
    """Config status of every external integration; secrets are never echoed.
    probe=true adds live pings (Telegram getMe, Redis ping)."""
    from . import security_redis as srmod
    from . import nltk_guard as ngmod
    redis_url = os.environ.get("REDIS_URL", "").strip()
    redis_ok = None
    if redis_url:
        client = srmod.get_client()
        if client is None:
            srmod.reset()
            client = srmod.get_client()
        redis_ok = client is not None
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    telegram = {"bot_token": bool(tg_token),
                "webhook_secret": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()),
                "live": None}
    if probe and tg_token:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as hc:
                r = await hc.get(f"https://api.telegram.org/bot{tg_token}/getMe")
                telegram["live"] = bool(r.json().get("ok"))
        except Exception:
            telegram["live"] = False
    dl_id = os.environ.get("DIGILOCKER_CLIENT_ID", "").strip()
    dl_secret = os.environ.get("DIGILOCKER_CLIENT_SECRET", "").strip()
    return {
        "database": {"engine": str(engine.url).split(":")[0]},
        "rate_limiter": {"backend": "redis" if redis_url else "memory"},
        "redis": {"configured": bool(redis_url), "ok": redis_ok},
        "telegram": telegram,
        "digilocker": {"env": dg.ENV, "client_id": bool(dl_id),
                       "client_secret": bool(dl_secret),
                       "ready": bool(dl_id and dl_secret)},
        "llm": await llmhealth.health_check(),
        "backup": {"dir": str(backupmod.BACKUP_DIR),
                   "s3": backupmod.s3_configured()},
        "email": {"provider": os.environ.get("NOTIFY_PROVIDER", ""),
                  "smtp": bool(os.environ.get("SMTP_HOST", "").strip())},
        "nltk_guard": {"installed": ngmod.is_installed()},
    }


@app.post("/admin/backup")
def admin_backup(admin: User = Depends(require_admin)):
    """Online snapshot now (E: by default). Pair with Task Scheduler daily."""
    return backupmod.run(engine)


@app.get("/admin/backups")
def admin_backups(admin: User = Depends(require_admin)):
    return backupmod.listing()


class BuildTaskIn(BaseModel):
    task: str
    city: str = ""
    state: str = ""
    service_type: str = ""


class DiscoverIn(BaseModel):
    task: str
    max_results: int = 8


@app.post("/build-task")
async def build_task(body: "BuildTaskIn", bg: _BT, user: User = Depends(current_user)):
    """Citizen submits civic task -> discovers sources -> builds map async."""
    if not body.task.strip():
        raise HTTPException(400, "task required")
    
    # Generate slug from task + city
    slug_base = re.sub(r'\W+', '-', body.task.lower().strip()).strip('-')
    city_suffix = re.sub(r'\W+', '-', body.city.lower().strip()).strip('-') if body.city else ''
    slug = f"{slug_base}{'-' + city_suffix if city_suffix else ''}"
    
    # Ensure unique slug
    with Session(engine) as s:
        existing = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if existing:
            slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Discover government sources: enriched query first (service category +
    # state sharpen recall), then the bare task, then the curated catalog so
    # the build flow never dies just because live search (npx/network) is
    # unavailable.
    from . import catalog as catalogmod

    def _discover_urls(q: str) -> list[str]:
        try:
            found = discovermod.discover(q, max_results=8)
        except Exception:
            return []
        return [r["url"] for r in found[:5] if r.get("url")]

    bare = body.task.strip()
    enriched = " ".join(part for part in
                        (bare, body.service_type.strip(), body.state.strip())
                        if part)
    urls = _discover_urls(enriched) if enriched != bare else _discover_urls(bare)
    if not urls and enriched != bare:
        urls = _discover_urls(bare)
    discovery = "search"
    if not urls:
        urls = catalogmod.fallback_sources(body.task, body.service_type, body.state)
        discovery = "catalog"
    if not urls:
        raise HTTPException(400, "No government sources found for this task")

    # Validate URLs — skip entries the policy gate rejects (it raises
    # HTTPException, not ValueError; catching only ValueError aborted whole runs)
    valid_urls = []
    for url in urls:
        try:
            valid_urls.append(_validate_fetch_url(url))
        except HTTPException:
            continue
        except ValueError:
            continue

    if not valid_urls:
        raise HTTPException(400, "No valid government URLs found")
    
    # Create background job
    job_payload = json.dumps({
        "task": body.task,
        "slug": slug,
        "urls": valid_urls,
        "city": body.city,
        "state": body.state,
        "service_type": body.service_type,
        "user_id": user.id
    })
    
    with Session(engine) as s:
        j = Job(kind="build", created_by=user.id, payload=job_payload)
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    
    bg.add_task(jobsmod.run_build, engine, jid)
    return {
        "job_id": jid,
        "slug": slug,
        "status": "queued",
        "task": body.task,
        "urls_found": len(valid_urls),
        "discovery": discovery
    }


@app.get("/jobs/{job_id}")
def job_status_public(job_id: int, user: User = Depends(current_user)):
    """Public job status endpoint (for polling build tasks)."""
    from .models import Job as JobModel
    with Session(engine) as s:
        j = s.get(JobModel, job_id)
        if not j:
            raise HTTPException(404, "unknown job")
        # Check ownership or admin
        if j.created_by != user.id and not user.is_admin:
            raise HTTPException(403, "not your job")
        if jobsmod.fail_if_stale(j):
            s.add(j)
            s.commit()
        result = json.loads(j.result) if j.result else {}
        return {
            "job_id": j.id,
            "kind": j.kind,
            "status": j.status,
            "result": result,
            "finished": bool(j.finished_at)
        }


@app.get("/task/{slug}")
def get_task_map(slug: str, user: User = Depends(current_user)):
    """Verified maps: any authenticated user. Unverified: builder + admin only."""
    with Session(engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if not m:
            raise HTTPException(404, "unknown map")
        if not m.verified_at and not user.is_admin and m.created_by != user.id:
            raise HTTPException(404, "unknown map")
        return {
            "slug": m.slug,
            "title": m.title,
            "city": m.city,
            "state": m.state,
            "service_type": m.service_type,
            "graph": json.loads(m.graph_json),
            "sources": json.loads(m.source_urls),
            "verified": bool(m.verified_at),
            "verified_at": m.verified_at
        }




# ---------------- Mini-Hermes Agent -----------------------------------------

class AgentRunIn(BaseModel):
    task: str
    mode: str = "auto"
    budget: int = 20


@app.post("/agent/run")
def agent_run(body: AgentRunIn, bg: _BT, admin: User = Depends(require_admin)):
    """Launch mini-Hermes agent task asynchronously. Poll GET /agent/result/{job_id}."""
    with Session(engine) as s:
        j = Job(kind="agent", created_by=admin.id,
                payload=json.dumps({"task": body.task, "mode": body.mode, "budget": body.budget}))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    bg.add_task(agentmod.run_agent_job, engine, jid)
    return {"job_id": jid, "status": "queued"}


@app.get("/agent/result/{job_id}")
def agent_result(job_id: int, admin: User = Depends(require_admin)):
    from .models import Job as JobModel
    with Session(engine) as s:
        j = s.get(JobModel, job_id)
        if not j:
            raise HTTPException(404, "unknown job")
        return {"job_id": j.id, "status": j.status,
                "result": json.loads(j.result), "finished": bool(j.finished_at)}


@app.get("/agent/tools")
def agent_tools(admin: User = Depends(require_admin)):
    """List available agent tools and their schemas."""
    return {"tools": agentmod.TOOL_SCHEMA}


@app.get("/agent/audit")
def agent_audit(n: int = 50, admin: User = Depends(require_admin)):
    """Read recent agent audit log entries."""
    return {"entries": agentmod.audit_read(n)}


# ---------------- Hermes Core Agent ----------------------------------------

class HermesRunIn(BaseModel):
    task: str
    mode: str = "auto"
    budget: int = 30


@app.post("/hermes/run")
def hermes_run(body: HermesRunIn, bg: _BT, admin: User = Depends(require_admin)):
    """Launch Hermes autonomous agent task asynchronously."""
    with Session(engine) as s:
        j = Job(kind="hermes", created_by=admin.id,
                payload=json.dumps({"task": body.task, "mode": body.mode, "budget": body.budget}))
        s.add(j)
        s.commit()
        s.refresh(j)
        jid = j.id
    bg.add_task(hermesmod.run_hermes_job, engine, jid)
    return {"job_id": jid, "status": "queued"}


@app.get("/hermes/result/{job_id}")
def hermes_result(job_id: int, admin: User = Depends(require_admin)):
    from .models import Job as JobModel
    with Session(engine) as s:
        j = s.get(JobModel, job_id)
        if not j:
            raise HTTPException(404, "unknown job")
        return {"job_id": j.id, "status": j.status,
                "result": json.loads(j.result), "finished": bool(j.finished_at)}


@app.get("/hermes/tools")
def hermes_tools(admin: User = Depends(require_admin)):
    """List available Hermes tools and their schemas."""
    return {"tools": list(hermesmod.TOOLS.values())}


# ---------------- Sub-Agent Spawning --------------------------------------

class SubAgentIn(BaseModel):
    parent_job_id: int
    tasks: list[dict]


@app.post("/hermes/spawn")
def hermes_spawn(body: SubAgentIn, admin: User = Depends(require_admin)):
    """Spawn parallel sub-agents for specialized work."""
    try:
        sub_ids = submod.spawn_parallel(engine, body.parent_job_id, body.tasks)
        return {"sub_agent_ids": sub_ids, "count": len(sub_ids)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/hermes/sub/{sub_id}")
def hermes_sub_result(sub_id: int, admin: User = Depends(require_admin)):
    from .models import Job as JobModel
    with Session(engine) as s:
        j = s.get(JobModel, sub_id)
        if not j:
            raise HTTPException(404, "unknown sub-agent")
        return {"sub_id": j.id, "status": j.status,
                "result": json.loads(j.result), "finished": bool(j.finished_at)}


# ---------------- DPDP Act compliance --------------------------------------
# Consent withdrawal, data export/erasure, grievance mechanism.

class GrievanceIn(BaseModel):
    subject: str
    message: str


@app.post("/me/data-export")
def data_export(user: User = Depends(current_user)):
    """DPDP data-portability: download all your data as a JSON receipt."""
    with Session(engine) as s:
        items = s.exec(select(VaultItem).where(VaultItem.user_id == user.id)).all()
        consents = s.exec(select(Consent).where(Consent.user_id == user.id)).all()
        progs = s.exec(select(Progress).where(Progress.user_id == user.id)).all()
        receipt = {
            "format": "civic-pathfinder-data-receipt/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user": {"id": user.id, "email": user.email,
                     "name": user.name, "city": user.city, "state": user.state,
                     "created_at": user.created_at.isoformat() if user.created_at else None},
            "vault": [{"kind": i.kind, "label": i.label, "issuer": i.issuer,
                       "reference": i.reference,
                       "verified_at": i.verified_at.isoformat() if i.verified_at else None,
                       "expires_at": i.expires_at.isoformat() if i.expires_at else None,
                       "meta": i.meta} for i in items],
            "consents": [{"purpose": c.purpose, "scopes": c.scopes,
                          "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                          "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None}
                         for c in consents],
            "progress": [{"map": p.map_slug, "step": p.step_id,
                          "done_at": p.done_at.isoformat() if p.done_at else None}
                         for p in progs],
        }
        return receipt


@app.post("/me/consent/withdraw")
def consent_withdraw(user: User = Depends(current_user)):
    """Withdraw DigiLocker consent → immediately erases vault items.
    Returns count of erased records."""
    from datetime import datetime, timezone as _tz
    with Session(engine) as s:
        # Mark consents withdrawn
        consents = s.exec(select(Consent).where(
            Consent.user_id == user.id,
            Consent.withdrawn_at.is_(None))).all()
        for c in consents:
            c.withdrawn_at = datetime.now(_tz.utc)
            s.add(c)
        # Erase vault (storage limitation — DPDP §8)
        items = s.exec(select(VaultItem).where(VaultItem.user_id == user.id)).all()
        for it in items:
            s.delete(it)
        # Erase OAuth states + link codes
        for row in s.exec(select(OAuthState).where(OAuthState.user_id == user.id)).all():
            s.delete(row)
        for row in s.exec(select(LinkCode).where(LinkCode.user_id == user.id)).all():
            s.delete(row)
        s.commit()
        return {"consents_withdrawn": len(consents), "vault_items_erased": len(items)}


@app.delete("/me/account")
def account_delete(user: User = Depends(current_user)):
    """Right to erasure: permanently delete account and all associated data."""
    with Session(engine) as s:
        uid = user.id
        # Delete in FK-safe order — every user-linked table (DPDP erasure)
        for row in s.exec(select(VaultItem).where(VaultItem.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Consent).where(Consent.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Progress).where(Progress.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(RoadmapMilestone).where(
                RoadmapMilestone.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Notification).where(
                Notification.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Grievance).where(Grievance.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(OtpCode).where(OtpCode.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(LinkCode).where(LinkCode.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(OAuthState).where(OAuthState.user_id == uid)).all():
            s.delete(row)
        for row in s.exec(select(Job).where(Job.created_by == uid)).all():
            s.delete(row)
        u = s.get(User, uid)
        if u:
            s.delete(u)
        s.commit()
    return {"deleted": True}


@app.post("/me/grievance")
def grievance_submit(body: GrievanceIn, user: User = Depends(current_user)):
    """DPDP §24 — submit grievance; must respond within prescribed period."""
    if not body.subject.strip() or not body.message.strip():
        raise HTTPException(400, "subject + message required")
    with Session(engine) as s:
        g = Grievance(user_id=user.id, subject=body.subject.strip(),
                      message=body.message.strip())
        s.add(g)
        s.commit()
        s.refresh(g)
        try:
            from . import notify as notifmod
            notifmod.send(
                os.environ.get("GRIEVANCE_EMAIL", "grievance@civicpath.in"),
                f"New grievance #{g.id} from {user.email}",
                f"Subject: {g.subject}\n\n{g.message[:4000]}")
        except Exception:
            pass
        return {"id": g.id, "status": g.status,
                "expected_response_days": 7}


@app.get("/me/grievance")
def grievance_list(user: User = Depends(current_user)):
    with Session(engine) as s:
        gs = s.exec(select(Grievance).where(Grievance.user_id == user.id)).all()
        return [{"id": g.id, "subject": g.subject, "status": g.status,
                 "created_at": g.created_at.isoformat() if g.created_at else None,
                 "resolution": g.resolution, } for g in gs]


@app.get("/admin/grievances")
def admin_grievances(status: str = "", admin: User = Depends(require_admin)):
    """Admin: list all grievances (filter by status)."""
    with Session(engine) as s:
        q = select(Grievance)
        if status:
            q = q.where(Grievance.status == status)
        gs = s.exec(q.order_by(Grievance.created_at.desc())).all()
        return [{"id": g.id, "user_id": g.user_id, "subject": g.subject,
                 "message": g.message, "status": g.status,
                 "created_at": g.created_at.isoformat() if g.created_at else None} for g in gs]


class GrievanceResolveIn(BaseModel):
    status: str
    resolution: str = ""


@app.post("/admin/grievances/{gid}/resolve")
def admin_grievance_resolve(gid: int, body: GrievanceResolveIn,
                            admin: User = Depends(require_admin)):
    if body.status not in ("open", "in_review", "resolved", "rejected"):
        raise HTTPException(400, "invalid status")
    with Session(engine) as s:
        g = s.get(Grievance, gid)
        if not g:
            raise HTTPException(404, "unknown grievance")
        g.status = body.status
        g.resolution = body.resolution
        if body.status in ("resolved", "rejected"):
            from datetime import datetime as _dt, timezone as _tz
            g.resolved_at = _dt.now(_tz.utc)
        s.add(g)
        s.commit()
        return {"id": g.id, "status": g.status}


# Public legal endpoints — no login required (DPDP transparency)

@app.get("/legal/privacy")
def legal_privacy():
    """Serve the privacy policy."""
    p = Path(__file__).resolve().parent.parent / "privacy_policy.md"
    if not p.exists():
        raise HTTPException(404, "privacy policy not found")
    return {"policy": p.read_text(encoding="utf-8")}


@app.get("/legal/terms")
def legal_terms():
    """Serve the terms of service."""
    p = Path(__file__).resolve().parent.parent / "terms_of_service.md"
    if not p.exists():
        raise HTTPException(404, "terms not found")
    return {"terms": p.read_text(encoding="utf-8")}
