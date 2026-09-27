"""Background jobs: long scrape/recheck runs leave HTTP immediately.

Single-process BackgroundTasks + DB job rows (status polling). Durability:
- per-slug in-process lock (no concurrent build of the same map)
- startup recovery re-dispatches queued/running rows lost to a restart
- stale running rows are failed on status reads (JOB_STALE_SECONDS)
When we grow to multi-worker, swap add_task for a Celery/Redis .delay().
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .models import Job, TaskMap

STALE_SECONDS = int(os.environ.get("JOB_STALE_SECONDS", "3600"))
RECOVER_MAX_AGE_HOURS = int(os.environ.get("JOB_RECOVER_MAX_AGE_HOURS", "24"))

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
            else:
                revive.append((j.id, j.kind))
                j.status = "queued"
            s.add(j)
        s.commit()
    for jid, kind in revive:
        _dispatch_thread(engine, jid, kind)
    return [jid for jid, _ in revive]


def _dispatch_thread(engine, job_id: int, kind: str) -> None:
    from . import agent as agentmod
    from . import hermes as hermesmod
    targets = {
        "build": run_build,
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


def run_build(engine, job_id: int):
    from . import worker as workermod
    from . import watch as watchmod
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
                if m:
                    m.title, m.graph_json = p["task"], payload
                    m.source_urls = json.dumps(result["sources"])
                    m.edge_sources = json.dumps(result.get("edge_sources", {}))
                    m.city = p.get("city", "") or m.city
                    m.state = p.get("state", "") or m.state
                    m.service_type = p.get("service_type", "") or m.service_type
                    m.verified_at = None
                    if m.created_by == 0 and creator:
                        m.created_by = creator
                    s.add(m)
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
                s.commit()
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
