"""Sub-agent system: spawn specialized parallel workers.

Each sub-agent gets its own budget and runs independently.
Results are collected and reported together.
"""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlmodel import Session, select

from .models import Job as JobModel
from .audit import append as audit_append
from .hermes_core import run_hermes


_SUB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sub-agent")


def spawn_subagent(
    engine,
    parent_job_id: int,
    task: str,
    specialization: str = "general",
    budget: int = 15,
    callback: Optional[Callable[[dict], None]] = None,
) -> int:
    """Spawn a sub-agent task. Returns sub-job ID for polling."""
    from .models import Job
    
    with Session(engine) as s:
        parent = s.get(JobModel, parent_job_id)
        if not parent:
            raise ValueError(f"parent job {parent_job_id} not found")
        
        sub_job = Job(
            kind="sub_agent",
            created_by=parent.created_by,
            payload=json.dumps({
                "task": task,
                "specialization": specialization,
                "budget": budget,
                "parent_job_id": parent_job_id
            }),
        )
        s.add(sub_job)
        s.commit()
        s.refresh(sub_job)
        sub_id = sub_job.id
    
    # Run in background thread
    def _run():
        try:
            result = run_hermes(task, mode="auto", budget=budget)
            result["sub_agent_id"] = sub_id
            result["specialization"] = specialization
            
            with Session(engine) as s:
                j = s.get(JobModel, sub_id)
                if j:
                    j.status = "done"
                    j.result = json.dumps(result)
                    j.finished_at = datetime.now(timezone.utc)
                    s.add(j)
                    s.commit()
            
            audit_append(
                action="sub_spawn",
                target=f"sub-{sub_id}",
                summary=task[:100],
                agent="hermes",
                parent_job=parent_job_id,
                sub_job=sub_id,
                specialization=specialization,
                status=result.get("status"),
            )
            if callback:
                callback(result)
        except Exception as e:
            with Session(engine) as s:
                j = s.get(JobModel, sub_id)
                if j:
                    j.status = "failed"
                    j.result = json.dumps({"error": str(e)})
                    j.finished_at = datetime.now(timezone.utc)
                    s.add(j)
                    s.commit()
            audit_append(
                action="sub_spawn",
                target=f"sub-{sub_id}",
                summary=f"FAILED: {e}",
                agent="hermes",
                parent_job=parent_job_id,
                sub_job=sub_id,
                status="failed",
            )
    
    _SUB_EXECUTOR.submit(_run)
    return sub_id


def spawn_parallel(
    engine,
    parent_job_id: int,
    tasks: list[dict],
    budget_per: int = 15,
) -> list[int]:
    """Spawn multiple sub-agents in parallel. Each task: {'id': str, 'task': str, 'specialization': str}."""
    sub_ids = []
    for t in tasks:
        sid = spawn_subagent(
            engine,
            parent_job_id,
            task=t["task"],
            specialization=t.get("specialization", "general"),
            budget=budget_per,
        )
        sub_ids.append(sid)
    return sub_ids


def collect_results(engine, sub_ids: list[int]) -> list[dict]:
    """Poll and collect results from sub-agents."""
    results = []
    with Session(engine) as s:
        for sid in sub_ids:
            j = s.get(JobModel, sid)
            if j and j.finished_at:
                try:
                    results.append(json.loads(j.result))
                except Exception:
                    results.append({"sub_id": sid, "status": j.status, "error": "parse failed"})
    return results
