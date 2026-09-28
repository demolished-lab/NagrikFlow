"""Attach the existing simulator Udyam map to the synthetic Rani demo account.

This must only target backend/t_sim.db created by backend/sim/run_sim.py; it
never touches the configured production/application database.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "backend" / "t_sim.db"
EMAIL = "rani@example.in"
SLUG = "udyam-register"

if not DB.is_file():
    raise SystemExit(f"Missing simulator database: {DB}\nRun backend/sim/run_sim.py first.")

con = sqlite3.connect(DB)
try:
    user = con.execute("SELECT id FROM user WHERE email=?", (EMAIL,)).fetchone()
    task_map = con.execute(
        "SELECT slug, verified_at FROM taskmap WHERE slug=?", (SLUG,)
    ).fetchone()
    if not user or not task_map:
        raise SystemExit("Expected simulator user/map is missing; rerun backend/sim/run_sim.py.")
    if not task_map[1]:
        raise SystemExit("The simulator pathway is not verified; rerun backend/sim/run_sim.py.")

    user_id = user[0]
    con.execute(
        "UPDATE taskmap SET created_by=?, city=?, state=?, service_type=? WHERE slug=?",
        (user_id, "Hyderabad", "Telangana", "Business & Trade", SLUG),
    )
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps({
        "task": "Register a small business",
        "city": "Hyderabad",
        "state": "Telangana",
        "service_type": "Business & Trade",
        "slug": SLUG,
    })
    result = json.dumps({"slug": SLUG, "verified": True})

    existing = None
    for job_id, raw_payload, raw_result in con.execute(
        "SELECT id, payload, result FROM job WHERE kind='build' AND created_by=?",
        (user_id,),
    ):
        try:
            if json.loads(raw_result or "{}").get("slug") == SLUG or json.loads(raw_payload or "{}").get("slug") == SLUG:
                existing = job_id
                break
        except (TypeError, json.JSONDecodeError):
            continue

    if existing:
        con.execute(
            "UPDATE job SET status='done', payload=?, result=?, created_at=?, finished_at=?, worker_id=? WHERE id=?",
            (payload, result, now, now, "demo-fixture", existing),
        )
    else:
        con.execute(
            "INSERT INTO job(kind,status,payload,result,created_by,created_at,finished_at,worker_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("build", "done", payload, result, user_id, now, now, "demo-fixture"),
        )
    con.commit()
    print(f"Prepared verified simulator pathway '{SLUG}' for the synthetic demo account.")
finally:
    con.close()
