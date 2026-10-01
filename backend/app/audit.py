"""Change audit log: every agent action is recorded with before/after + reason."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DIR = Path(os.environ.get("CIVIC_AGENT_AUDIT_DIR",
                                 Path(__file__).resolve().parent.parent.parent / "agent_audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _log_path() -> Path:
    return AUDIT_DIR / "audit.jsonl"


def append(action: str, target: str, summary: str,
           diff_before: str = "", diff_after: str = "",
           agent: str = "mini-hermes", **meta):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,       # file_write | file_patch | cmd_run | db_migrate | sub_spawn | alert
        "target": target,
        "summary": summary,
        "diff_before": diff_before,
        "diff_after": diff_after,
        "agent": agent,
        "meta": meta,
    }
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_last(n: int = 50) -> list[dict]:
    p = _log_path()
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines[-n:]]


def read_since(iso_ts: str) -> list[dict]:
    """Return entries after an ISO timestamp."""
    return [e for e in read_last(500) if e.get("ts", "") > iso_ts]
