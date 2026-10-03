"""Background jobs: long scrape/recheck runs leave HTTP immediately.

Single-process BackgroundTasks + DB job rows (status polling). Durability:
- per-slug in-process lock (no concurrent build of the same map)
- atomic DB lease/claim: exactly one worker executes a job (multi-instance safe)
- poller thread picks up queued rows and expired leases cross-instance
- startup recovery re-dispatches queued/running rows lost to a restart
- stale running rows are failed on status reads (JOB_STALE_SECONDS)
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text as sqltext
from sqlmodel import Session, select

from .models import Job, TaskMap
from .obs import warn

STALE_SECONDS = int(os.environ.get("JOB_STALE_SECONDS", "3600"))
RECOVER_MAX_AGE_HOURS = int(os.environ.get("JOB_RECOVER_MAX_AGE_HOURS", "24"))
LEASE_SECONDS = int(os.environ.get("JOB_LEASE_SECONDS", "1800"))

# Identity of this process's job claims (lease owner field, diagnostics).
_WORKER_ID = f"{os.getpid()}-{os.urandom(4).hex()}"

# Poller health, surfaced at /readyz — a dead poller means queued builds
# never run, and that must never be invisible.
POLLER_STATUS: dict = {"started": False, "disabled": False,
                       "last_ok_at": "", "last_error": ""}

_active_guard = threading.Lock()
_active_slugs: dict[str, threading.Lock] = {}


def _slug_lock(slug: str) -> threading.Lock:
    with _active_guard:
        lock = _active_slugs.get(slug)
        if lock is None:
            lock = threading.Lock()
            _active_slugs[slug] = lock
        return lock


def _finish(engine, job_id: int, status: str, result: dict):
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if j:
            j.status = status
            j.result = json.dumps(result)
            j.finished_at = datetime.now(timezone.utc)
            s.add(j)
            s.commit()


def _naive_ok(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def claim(engine, job_id: int, lease_seconds: int = LEASE_SECONDS) -> bool:
    """Atomically claim a queued job for this worker.

    One UPDATE with status='queued' in the WHERE clause: on PostgreSQL that is
    a row lock (only one concurrent UPDATE can win), on SQLite the write lock
    serializes it — so exactly one dispatcher transitions queued -> running.
    Everyone else sees rowcount 0 and backs off."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            sqltext("UPDATE job SET status='running', worker_id=:w, "
                    "lease_until=:lease, finished_at=NULL "
                    "WHERE id=:id AND status='queued'"),
            {"w": _WORKER_ID, "lease": now + timedelta(seconds=lease_seconds),
             "id": job_id})
        return bool(res.rowcount)


def fail_if_stale(j: Job) -> bool:
    """Mark a running job failed if it is older than STALE_SECONDS.

    Mutates the session-bound row (caller commits). Returns True if failed."""
    if j.status != "running" or j.finished_at is not None:
        return False
    age = datetime.now(timezone.utc) - _naive_ok(j.created_at)
    if age <= timedelta(seconds=STALE_SECONDS):
        return False
    j.status = "failed"
    j.result = json.dumps({"error": "stale: no completion within "
                                    f"{STALE_SECONDS}s (crashed worker?)"})
    j.finished_at = datetime.now(timezone.utc)
    return True


def recover_orphans(engine) -> list[int]:
    """Re-dispatch queued/running jobs lost to a process restart.

    Rows older than RECOVER_MAX_AGE_HOURS are failed instead of re-run.
    Running rows whose lease is still live belong to another instance and are
    left alone (multi-instance restart: do not steal active work).
    Returns the ids re-dispatched."""
    now = datetime.now(timezone.utc)
    doomed: list[int] = []
    revive: list[tuple[int, str]] = []
    with Session(engine) as s:
        rows = s.exec(select(Job).where(
            Job.status.in_(["queued", "running"]))).all()
        for j in rows:
            age = now - _naive_ok(j.created_at)
            if age > timedelta(hours=RECOVER_MAX_AGE_HOURS):
                doomed.append(j.id)
                j.status = "failed"
                j.result = json.dumps({"error": "lost in restart (expired)"})
                j.finished_at = now
            elif (j.status == "running" and j.lease_until is not None
                  and _naive_ok(j.lease_until) > now):
                continue  # another live worker holds this lease
            else:
                revive.append((j.id, j.kind))
                j.status = "queued"
                j.lease_until = None
            s.add(j)
        s.commit()
    for jid, kind in revive:
        _dispatch_thread(engine, jid, kind)
    return [jid for jid, _ in revive]


def poll_once(engine) -> list[int]:
    """Cross-instance pickup: dispatch queued rows and revive expired leases.

    Every worker process runs this on an interval; claim() guarantees exactly
    one of them actually starts a given job. Rows past RECOVER_MAX_AGE_HOURS
    are failed here too (a build that never ran and never aged out of the
    queue shouldn't sit forever). Returns the ids dispatched."""
    now = datetime.now(timezone.utc)
    dispatch: list[tuple[int, str]] = []
    with Session(engine) as s:
        rows = s.exec(select(Job).where(
            Job.status.in_(["queued", "running"]))).all()
        for j in rows:
            if now - _naive_ok(j.created_at) > timedelta(
                    hours=RECOVER_MAX_AGE_HOURS):
                j.status = "failed"
                j.result = json.dumps({"error": "expired (never picked up)"})
                j.finished_at = now
                s.add(j)
                continue
            if j.status == "running":
                if j.lease_until is not None and _naive_ok(j.lease_until) > now:
                    continue  # live lease: a worker is actively on it
                j.status = "queued"  # dead worker: lease expired / legacy row
                j.lease_until = None
                s.add(j)
            dispatch.append((j.id, j.kind))
        s.commit()
    for jid, kind in dispatch:
        _dispatch_thread(engine, jid, kind)
    return [jid for jid, _ in dispatch]


def start_poller(engine, interval: float = 2.0) -> None:
    """Daemon thread that runs poll_once on an interval (JOB_POLLER=0 opts out;
    tests disable it via conftest)."""

    def _loop():
        while True:
            time.sleep(interval)
            try:
                poll_once(engine)
                POLLER_STATUS["last_ok_at"] = datetime.now(
                    timezone.utc).isoformat()
                POLLER_STATUS["last_error"] = ""
            except Exception as e:
                POLLER_STATUS["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                warn("jobs", "job poller iteration failed", error=e)

    POLLER_STATUS["started"] = True
    threading.Thread(target=_loop, name="job-poller", daemon=True).start()


def _dispatch_thread(engine, job_id: int, kind: str) -> None:
    from . import agent as agentmod
    from . import hermes as hermesmod
    targets = {
        "build": run_build,
        "discover_build": run_discover_build,
        "recheck": run_recheck,
        "agent": agentmod.run_agent_job,
        "hermes": hermesmod.run_hermes_job,
    }
    target = targets.get(kind)
    if target is None:
        _finish(engine, job_id, "failed",
                {"error": f"unknown job kind {kind!r} after restart"})
        return
    threading.Thread(target=target, args=(engine, job_id),
                     name=f"recover-{kind}-{job_id}", daemon=True).start()


def run_discover_build(engine, job_id: int):
    """Discover official sources, then hand the enriched row to run_build.

    The external search process can be slow; keeping it in this worker stage
    means the API returns a job id immediately and remains responsive.
    """
    if not claim(engine, job_id):
        return
    try:
        with Session(engine) as s:
            job = s.get(Job, job_id)
            if not job:
                return
            payload = json.loads(job.payload)

        from fastapi import HTTPException

        from . import catalog as catalogmod
        from . import discover as discovermod
        from . import main as mainmod

        bare = payload["task"].strip()
        enriched = " ".join(part for part in
                            (bare, payload.get("service_type", "").strip(),
                             payload.get("state", "").strip()) if part)

        def discover_urls(query: str) -> list[str]:
            try:
                found = discovermod.discover(query, max_results=8)
            except Exception as e:
                mainmod.obsmod.warn("discover",
                                    "live URL discovery failed, catalog fallback",
                                    q=query, error=e)
                return []
            return [r["url"] for r in found[:5] if r.get("url")]

        urls = discover_urls(enriched)
        if not urls and enriched != bare:
            urls = discover_urls(bare)
        discovery = "search"
        if not urls:
            seeds = catalogmod.fallback_sources(
                payload["task"], payload.get("service_type", ""),
                payload.get("state", ""))
            # Common Crawl archive lane: deep pages on the catalog's gov
            # domains, found without touching the live site (CIVIC_CDX=0 off)
            archived: list[str] = []
            if seeds:
                try:
                    archived = discovermod.cdx_task_urls(enriched, seeds)
                except Exception as e:
                    mainmod.obsmod.warn("cdx", "archive discovery failed",
                                        q=enriched, error=e)
            if archived:
                urls, discovery = archived, "cdx"
            else:
                urls, discovery = seeds, "catalog"

        def valid(candidates: list[str]) -> list[str]:
            out = []
            for url in candidates:
                try:
                    out.append(mainmod._validate_fetch_url(url))
                except (HTTPException, ValueError):
                    continue
            return out

        valid_urls = valid(urls)
        if not valid_urls and discovery != "catalog":
            valid_urls = valid(catalogmod.fallback_sources(
                payload["task"], payload.get("service_type", ""),
                payload.get("state", "")))
            if valid_urls:
                discovery = "catalog"
        if not valid_urls:
            _finish(engine, job_id, "failed",
                    {"error": "No valid government URLs found"})
            return

        payload["urls"] = valid_urls
        payload["discovery"] = discovery
        with Session(engine) as s:
            job = s.get(Job, job_id)
            if not job:
                return
            job.payload = json.dumps(payload)
            job.status = "queued"
            job.worker_id = ""
            job.lease_until = None
            s.add(job)
            s.commit()
        run_build(engine, job_id)
    except Exception as e:
        _finish(engine, job_id, "failed", {"error": str(e)[:300]})


def run_build(engine, job_id: int):
    from . import watch as watchmod
    from . import worker as workermod
    if not claim(engine, job_id):
        return  # another dispatcher (poller / recovery / bg task) owns this job
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if not j:
            return
        p = json.loads(j.payload)
        creator = j.created_by
    slug = p.get("slug", "")
    lock = _slug_lock(slug)
    if not lock.acquire(blocking=False):
        _finish(engine, job_id, "failed",
                {"error": "another build is already running for this slug"})
        return
    try:
        with Session(engine) as s:
            j = s.get(Job, job_id)
            if not j:
                return
            j.status = "running"
            s.add(j)
            s.commit()
        try:
            result = workermod.build_map(p["task"], p["urls"], city=p.get("city", ""),
                                         state=p.get("state", ""),
                                         service_type=p.get("service_type", ""))
            with Session(engine) as s:
                m = s.exec(select(TaskMap).where(
                    TaskMap.slug == p["slug"])).first()
                payload = json.dumps({"nodes": result["nodes"],
                                      "edges": result["edges"]})

                def _apply(row):
                    row.title, row.graph_json = p["task"], payload
                    row.source_urls = json.dumps(result["sources"])
                    row.edge_sources = json.dumps(result.get("edge_sources", {}))
                    row.city = p.get("city", "") or row.city
                    row.state = p.get("state", "") or row.state
                    row.service_type = p.get("service_type", "") or row.service_type
                    row.verified_at = None
                    if row.created_by == 0 and creator:
                        row.created_by = creator
                    s.add(row)

                if m:
                    _apply(m)
                else:
                    s.add(TaskMap(slug=p["slug"], title=p["task"],
                                  city=p.get("city", ""),
                                  state=p.get("state", ""),
                                  service_type=p.get("service_type", ""),
                                  graph_json=payload,
                                  source_urls=json.dumps(result["sources"]),
                                  edge_sources=json.dumps(
                                      result.get("edge_sources", {})),
                                  created_by=creator))
                    try:
                        s.commit()
                    except Exception:
                        # unique-slug race with another instance (uq_taskmap_slug):
                        # fall back to updating the row that won the insert
                        s.rollback()
                        m = s.exec(select(TaskMap).where(
                            TaskMap.slug == p["slug"])).first()
                        if m is None:
                            raise
                        _apply(m)
                s.commit()
            # evidence: immutable per-source snapshots (text + raw HTML +
            # hashes) so later rechecks can produce real diffs, not just
            # "something changed". Never fails a build.
            try:
                from . import evidence as evidencemod
                evidencemod.save_snapshots(engine, p["slug"],
                                           result.get("snapshots") or [])
            except Exception as e:
                warn("evidence", "snapshot persist failed",
                     slug=p["slug"], error=e)
            base = watchmod.recheck(engine, p["slug"])
            _finish(engine, job_id, "done",
                    {"slug": p["slug"], "steps": len(result["nodes"]),
                     "sources": result["sources"], "baseline": base})
        except Exception as e:
            _finish(engine, job_id, "failed", {"error": str(e)[:300]})
    finally:
        lock.release()


def run_recheck(engine, job_id: int):
    from . import watch as watchmod
    if not claim(engine, job_id):
        return  # another dispatcher owns this job
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if not j:
            return
        payload = json.loads(j.payload)
    slug = payload.get("slug") or None
    lock = _slug_lock(slug) if slug else None
    if lock is not None and not lock.acquire(blocking=False):
        _finish(engine, job_id, "failed",
                {"error": "a build/recheck for this slug is already running"})
        return
    try:
        with Session(engine) as s:
            j = s.get(Job, job_id)
            if not j:
                return
            j.status = "running"
            s.add(j)
            s.commit()
        try:
            out = watchmod.recheck(engine, slug)
            _finish(engine, job_id, "done", {"maps": out})
        except Exception as e:
            _finish(engine, job_id, "failed", {"error": str(e)[:300]})
    finally:
        if lock is not None:
            lock.release()
