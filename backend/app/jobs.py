"""Background jobs: long scrape/recheck runs leave HTTP immediately.

Single-process BackgroundTasks + DB job rows (status polling). When we grow
to multi-worker, swap add_task for a Celery/Redis .delay() — same interface.
"""
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from .models import Job, TaskMap


def _finish(engine, job_id: int, status: str, result: dict):
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if j:
            j.status = status
            j.result = json.dumps(result)
            j.finished_at = datetime.now(timezone.utc)
            s.add(j)
            s.commit()


def run_build(engine, job_id: int):
    from . import worker as workermod
    from . import watch as watchmod
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if not j:
            return
        j.status = "running"
        s.add(j)
        s.commit()
        p = json.loads(j.payload)
    try:
        result = workermod.build_map(p["task"], p["urls"], city=p.get("city", ""), state=p.get("state", ""))
        with Session(engine) as s:
            m = s.exec(select(TaskMap).where(
                TaskMap.slug == p["slug"])).first()
            payload = json.dumps({"nodes": result["nodes"], "edges": result["edges"]})
            if m:
                m.title, m.graph_json = p["task"], payload
                m.source_urls = json.dumps(result["sources"])
                m.edge_sources = json.dumps(result.get("edge_sources", {}))
                m.city = p.get("city", "") or m.city
                m.state = p.get("state", "") or m.state
                m.verified_at = None
                s.add(m)
            else:
                s.add(TaskMap(slug=p["slug"], title=p["task"], city=p.get("city", ""),
                              state=p.get("state", ""), graph_json=payload,
                              source_urls=json.dumps(result["sources"])))
            s.commit()
        base = watchmod.recheck(engine, p["slug"])
        _finish(engine, job_id, "done",
                {"slug": p["slug"], "steps": len(result["nodes"]),
                 "sources": result["sources"], "baseline": base})
    except Exception as e:
        _finish(engine, job_id, "failed", {"error": str(e)[:300]})


def run_recheck(engine, job_id: int):
    from . import watch as watchmod
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if not j:
            return
        j.status = "running"
        s.add(j)
        s.commit()
        slug = json.loads(j.payload).get("slug") or None
    try:
        out = watchmod.recheck(engine, slug)
        _finish(engine, job_id, "done", {"maps": out})
    except Exception as e:
        _finish(engine, job_id, "failed", {"error": str(e)[:300]})
