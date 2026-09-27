"""Life-sim: a full citizen day through REAL endpoints, mock outside world.

Rani (Hyderabad) registers -> DigiLocker consent (mock server) -> vault
fills -> dashboard personalizes -> LLM brief -> Telegram link -> ticks a
step -> admin builds a map from the fixture gov page. Asserts each hop.
"""
import os
import sys
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./t_sim.db"
os.environ["ALLOW_DEV_SECRET"] = "1"
os.environ["CIVIC_DEV"] = "1"
os.environ["LINK_PROBE"] = "0"  # offline sim: no reachability probes
os.environ["SSRF_PROBE"] = "0"  # offline sim: fixture gov page served on localhost
os.environ["DIGILOCKER_API_BASE"] = "http://localhost:8001"
os.environ["DIGILOCKER_SSO_BASE"] = "http://localhost:8001/sso"
for f in ("t_sim.db",):
    try:
        os.remove(f)
    except OSError:
        pass

import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sim.mock_server import mock_app  # noqa: E402

threading.Thread(target=uvicorn.run,
                 kwargs={"app": mock_app, "port": 8001, "log_level": "error"},
                 daemon=True).start()

import functools  # noqa: E402
import http.server  # noqa: E402

handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                            directory=str(SIM_DIR))
threading.Thread(target=http.server.HTTPServer(
    ("localhost", 8003), handler).serve_forever, daemon=True).start()
time.sleep(3)

import app.main as M  # noqa: E402

c = TestClient(M.app)

print("1. register Rani")
rani = c.post("/auth/register", json={
    "email": "rani@example.in", "password": "secret1234",
    "name": "Rani Devi", "city": "Hyderabad", "state": "Telangana"}).json()
H = {"Authorization": f"Bearer {rani['token']}"}
assert "token" in rani, rani
print("   user_id:", rani["user_id"])

print("2. DigiLocker consent callback (mock code)")
connect = c.get("/auth/digilocker/connect", headers=H).json()
imp = c.post("/auth/digilocker/callback", headers=H,
             json={"code": "mock-code", "state": connect["state"]}).json()
print("   imported:", imp["imported_kinds"])
assert {"aadhaar", "pan", "udyam"} <= set(imp["imported_kinds"]), imp

print("3. personalized dashboard")
dash = c.get("/me/dashboard", headers=H).json()
print("   have:", dash["have"])
print("   next:", [(n["get"], n["effort"]) for n in dash["next_easiest"]])
assert "Udyam (MSME)" in dash["have"]

print("4. plain-words brief")
br = c.get("/me/brief", headers=H).json()
print("   via:", br["via"], "|", br["brief"][:150])
assert br["brief"].strip()

print("5. Telegram link")
code = c.post("/me/telegram/link-code", headers=H).json()["code"]
hook = c.post("/hooks/telegram", json={
    "message": {"chat": {"id": 9178452301}, "text": f"/start {code}"}}).json()
print("   hook:", hook)
assert hook.get("linked") is True

print("6. tick a roadmap step")
c.post("/me/progress", headers=H,
       json={"map_slug": "udyam-register", "step_id": "udyam"}).json()
dash2 = c.get("/me/dashboard", headers=H).json()
print("   in_progress:", dash2["in_progress_maps"])
assert dash2["in_progress_maps"].get("udyam-register") == 1

print("7. admin builds map from fixture gov page")
admin = c.post("/auth/register", json={
    "email": "demo@civic.test", "password": "demo1234", "name": "Admin"}).json()
HA = {"Authorization": f"Bearer {admin['token']}"}
built = c.post("/admin/build-map", headers=HA, json={
    "task": "Udyam registration (sim)", "slug": "udyam-sim",
    "urls": ["http://localhost:8003/gov_fixture.html"]},
    timeout=300).json()
print("   steps:", built["steps"], "| verified:", built["verified"])
assert built["steps"] >= 2 and built["verified"] is None

print("8. admin stamps it")
stamped = c.post("/admin/maps/udyam-sim/verify", headers=HA,
                 json={"verified": True}).json()
print("   verified:", stamped["verified"])
assert stamped["verified"]

print("\nLIFE-SIM ALL GREEN [OK]")
