"""Coverage for the four PSWB 02 gap closures:
1. Cross-source dependency inference (merge + prereq/LLM edges, JSON-safe provenance)
2. dagre layout is frontend-only (build-checked in CI; backend asserts edge validity)
3. Per-step admin editing (GET/PUT/POST/DELETE /admin/maps/{slug}/steps)
4. Explicit type-of-service input (build-task -> job payload -> TaskMap -> API)
"""
import json

from sqlmodel import select


def _acyclic(edges, ids):
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for a, b in edges:
        adj[a].append(b)
        indeg[b] += 1
    stack = [i for i in ids if indeg[i] == 0]
    seen = 0
    while stack:
        node = stack.pop()
        seen += 1
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                stack.append(nxt)
    return seen == len(ids)


SOURCE_STEPS = {
    "https://dept.gov.in/business": [
        {"id": "pan", "type": "prereq", "title": "Get PAN card",
         "detail": "PAN card needed for registration", "fee": ""},
        {"id": "docs", "type": "prereq", "title": "Gather documents",
         "detail": "PAN, Aadhaar, address proof", "fee": ""},
        {"id": "apply", "type": "action", "title": "Apply on official portal",
         "detail": "Fill the online form", "fee": ""},
    ],
    "https://dept2.gov.in/gst": [
        {"id": "gst", "type": "action", "title": "Register for GST",
         "detail": "Requires PAN card and Aadhaar", "fee": ""},
        {"id": "payfee", "type": "payment", "title": "Pay GST fee",
         "detail": "Pay the registration fee online", "fee": "500"},
    ],
}


def _mock_pipeline(monkeypatch, infer=None):
    from app import worker as W

    def fake_llm_extract(text, url, task):
        return [dict(s, url=url) for s in SOURCE_STEPS.get(url, [])]

    monkeypatch.setattr(W, "cascade_fetch", lambda url: (f"page content for {url}", "trafilatura"))
    monkeypatch.setattr(W, "llm_extract", fake_llm_extract)
    if infer is not None:
        monkeypatch.setattr(W, "llm_infer_edges", lambda task, nodes: infer)
    else:
        monkeypatch.setattr(W, "llm_infer_edges", lambda task, nodes: [])


def test_build_map_cross_source_inference(monkeypatch):
    """Prereq from source A links to dependent step in source B; provenance JSON-safe."""
    _mock_pipeline(monkeypatch)
    from app import worker as W

    result = W.build_map("register a small business", list(SOURCE_STEPS))
    nodes, edges = result["nodes"], result["edges"]
    ids = {n["id"] for n in nodes}

    assert ids == {"pan", "docs", "apply", "gst", "payfee"}
    # all edges reference real nodes, no self loops, acyclic
    assert all(a in ids and b in ids and a != b for a, b in edges)
    assert _acyclic(edges, ids)
    # cross-source edge: PAN prereq (source A) -> GST registration (source B)
    assert ["pan", "gst"] in edges
    # sequential chain within a source preserved
    assert ["gst", "payfee"] in edges
    # edge_sources must be json-serializable with string keys (was a tuple-key crash)
    dumped = json.dumps(result["edge_sources"])
    assert "pan|gst" in dumped
    assert "inferred" in dumped


def test_build_map_merges_duplicate_steps(monkeypatch):
    """Same step appearing in two sources collapses into one node."""
    _mock_pipeline(monkeypatch)
    from app import worker as W

    dup = {
        "https://a.gov.in": [{"id": "x", "type": "action",
                              "title": "Apply on official portal", "detail": "from A"}],
        "https://b.gov.in": [{"id": "y", "type": "action",
                              "title": "Apply on official portal", "detail": "from B"}],
    }

    def fake_extract(text, url, task):
        return [dict(s, url=url) for s in dup[url]]

    monkeypatch.setattr(W, "llm_extract", fake_extract)
    result = W.build_map("task", list(dup))
    assert len(result["nodes"]) == 1
    node = result["nodes"][0]
    assert node["detail"] == "from A"  # first source wins, no data wiped


def test_llm_edges_are_validated(monkeypatch):
    """Junk LLM edges (unknown ids, self loops, cycles) are dropped."""
    _mock_pipeline(monkeypatch, infer=[
        ["ghost", "pan"],      # unknown id
        ["pan", "pan"],        # self loop
        ["gst", "pan"],        # cycle: pan -> gst already exists
        ["docs", "gst"],       # valid extra edge
    ])
    from app import worker as W

    result = W.build_map("register a small business", list(SOURCE_STEPS))
    edges = result["edges"]
    ids = {n["id"] for n in result["nodes"]}
    assert all(a in ids and b in ids for a, b in edges)
    assert all(a != b for a, b in edges)
    assert ["gst", "pan"] not in edges
    assert ["docs", "gst"] in edges
    assert _acyclic(edges, ids)


def test_build_map_echoes_service_type(monkeypatch):
    _mock_pipeline(monkeypatch)
    from app import worker as W

    result = W.build_map("t", [], service_type="Business & Trade")
    assert result["service_type"] == "Business & Trade"


# ---------------- Per-step application links (deep links) ----------------

def test_heuristic_extracts_deep_links():
    from app import worker as W

    text = ("Udyam registration for MSME. Fee: Rs. 0. Required documents: PAN, "
            "Aadhaar, photograph. Apply online at "
            "https://udyam.gov.in/registration/apply-form. Download the form "
            "from https://udyam.gov.in/forms/template.pdf")
    steps = W.heuristic_extract(text, "https://udyam.gov.in/page")
    apply_step = next(s for s in steps if s["id"] == "apply")
    assert apply_step["link"] == "https://udyam.gov.in/registration/apply-form"
    # every step still carries the source page as proof link
    assert all(s["url"] == "https://udyam.gov.in/page" for s in steps)


def test_llm_links_are_hallucination_proof(monkeypatch):
    """Foreign-host LLM links are dropped; same-host / gov links kept."""
    from app import worker as W
    from app import llm as llmmod

    raw = json.dumps([
        {"id": "a", "type": "action", "title": "Apply", "detail": "x",
         "fee": "", "link": "https://evil.example/phish"},
        {"id": "b", "type": "payment", "title": "Pay fee", "detail": "x",
         "fee": "100", "link": "https://dept.gov.in/pay"},
        {"id": "c", "type": "prereq", "title": "Get form", "detail": "x",
         "fee": "", "link": "not-a-url"},
    ])
    monkeypatch.setattr(llmmod, "_chat_raw", lambda prompt: (raw, "model"))
    steps = W.llm_extract("page text " * 20, "https://dept.gov.in/page", "task")
    links = {s["id"]: s["link"] for s in steps}
    assert links["a"] == ""            # phishing host dropped
    assert links["b"] == "https://dept.gov.in/pay"
    assert links["c"] == ""            # malformed dropped
    # source proof link never overwritten
    assert all(s["url"] == "https://dept.gov.in/page" for s in steps)


def test_build_map_nodes_carry_link(monkeypatch):
    _mock_pipeline(monkeypatch)
    from app import worker as W

    monkeypatch.setattr(W, "llm_extract", lambda text, url, task: [
        {"id": "apply", "type": "action", "title": "Apply online", "detail": "",
         "fee": "", "url": url, "link": "https://dept.gov.in/forms/apply-1"},
    ])
    result = W.build_map("task", ["https://dept.gov.in/page"])
    assert result["nodes"][0]["link"] == "https://dept.gov.in/forms/apply-1"


# ---------------- Gap 3: per-step admin editing ----------------

def _seed_edit_map(slug="edit-map", edge_sources=None):
    from sqlmodel import Session
    from app import main as M
    from app.models import TaskMap

    graph = {
        "nodes": [
            {"id": "a", "type": "action", "title": "Old title", "detail": "d",
             "url": "", "fee": ""},
            {"id": "b", "type": "prereq", "title": "Second step", "detail": "",
             "url": "", "fee": ""},
        ],
        "edges": [["a", "b"]],
    }
    with Session(M.engine) as s:
        old = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
        if old:  # tests share one DB — reseed idempotently
            s.delete(old)
            s.commit()
        s.add(TaskMap(slug=slug, title="Edit map",
                      graph_json=json.dumps(graph),
                      edge_sources=json.dumps(edge_sources or {"a|b": "https://x.gov.in"}),
                      source_urls="[]"))
        s.commit()


def test_admin_step_edit_update(client, admin, monkeypatch):
    from app import main as M
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)
    _seed_edit_map()

    r = client.get("/admin/maps/edit-map/steps", headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()["nodes"]) == 2

    r = client.put("/admin/maps/edit-map/steps/a", headers=admin["headers"],
                   json={"title": "Updated title", "detail": "new detail",
                         "fee": "₹100", "url": "https://updated.gov.in/page",
                         "link": "https://updated.gov.in/forms/form-9.pdf",
                         "type": "payment"})
    assert r.status_code == 200, r.text
    node = r.json()["node"]
    assert node["title"] == "Updated title"
    assert node["type"] == "payment"
    assert node["fee"] == "₹100"
    assert node["link"] == "https://updated.gov.in/forms/form-9.pdf"

    # persisted
    r = client.get("/admin/maps/edit-map/steps", headers=admin["headers"])
    titles = {n["id"]: n["title"] for n in r.json()["nodes"]}
    assert titles["a"] == "Updated title"


def test_admin_step_edit_validation(client, admin, monkeypatch):
    from app import main as M
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)
    _seed_edit_map()

    bad = client.put("/admin/maps/edit-map/steps/a", headers=admin["headers"],
                     json={"title": "   "})
    assert bad.status_code == 400
    missing_map = client.put("/admin/maps/nope/steps/a", headers=admin["headers"],
                             json={"title": "x"})
    assert missing_map.status_code == 404
    missing_step = client.put("/admin/maps/edit-map/steps/ghost", headers=admin["headers"],
                              json={"title": "x"})
    assert missing_step.status_code == 404


def test_admin_step_add_and_delete(client, admin, monkeypatch):
    from sqlmodel import Session
    from app import main as M
    from app.models import TaskMap
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)
    _seed_edit_map()

    # add wired as dependency of step a
    r = client.post("/admin/maps/edit-map/steps", headers=admin["headers"],
                    json={"title": "Collect signed declaration", "type": "prereq",
                          "depends_on": ["a"]})
    assert r.status_code == 200, r.text
    new_id = r.json()["node"]["id"]
    assert new_id == "collect-signed-declaration"
    assert ["a", new_id] in r.json()["edges"]

    # unknown dependency rejected
    bad = client.post("/admin/maps/edit-map/steps", headers=admin["headers"],
                      json={"title": "x", "depends_on": ["ghost"]})
    assert bad.status_code == 400

    # delete step a -> node and its edges/provenance gone
    r = client.delete("/admin/maps/edit-map/steps/a", headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["steps"] == 2  # b + new

    r = client.get("/admin/maps/edit-map/steps", headers=admin["headers"])
    data = r.json()
    ids = {n["id"] for n in data["nodes"]}
    assert "a" not in ids
    assert all("a" not in (e[0], e[1]) for e in data["edges"])
    with Session(M.engine) as s:
        m = s.exec(select(TaskMap).where(TaskMap.slug == "edit-map")).first()
        assert m is not None
        assert "a|b" not in json.loads(m.edge_sources or "{}")

    # deleting unknown step -> 404
    assert client.delete("/admin/maps/edit-map/steps/ghost",
                         headers=admin["headers"]).status_code == 404


def test_admin_step_edit_requires_admin(client, user):
    _seed_edit_map()
    r = client.put("/admin/maps/edit-map/steps/a", headers=user["headers"],
                   json={"title": "hijack"})
    assert r.status_code == 403


# ---------------- Gap 4: type-of-service end-to-end ----------------

def test_build_task_carries_service_type(client, user, monkeypatch):
    from app import main as M
    import app.jobs as J

    seen_query = {}

    def fake_discover(query, max_results=8):
        seen_query["q"] = query
        return [{"url": "https://udyam.gov.in/x"}]

    monkeypatch.setattr(M.discovermod, "discover", fake_discover)
    monkeypatch.setattr(M, "_validate_fetch_url", lambda u: u)

    captured = {}

    def fake_run_build(engine, job_id):
        from sqlmodel import Session
        from app.models import Job, TaskMap
        with Session(engine) as s:
            job = s.get(Job, job_id)
            payload = json.loads(job.payload)
            captured.update(payload)
            s.add(TaskMap(slug=payload["slug"], title=payload["task"],
                          city=payload.get("city", ""), state=payload.get("state", ""),
                          service_type=payload.get("service_type", ""),
                          graph_json='{"nodes": [], "edges": []}',
                          source_urls="[]", edge_sources="{}"))
            job.status = "done"
            job.result = json.dumps({"slug": payload["slug"]})
            s.add(job)
            s.commit()

    monkeypatch.setattr(J, "run_build", fake_run_build)

    r = client.post("/build-task", headers=user["headers"], json={
        "task": "Register a small business", "city": "Hyderabad",
        "state": "Telangana", "service_type": "Business & Trade"})
    assert r.status_code == 200, r.text
    slug = r.json()["slug"]

    # payload carried the service type + location through the job
    assert captured["service_type"] == "Business & Trade"
    assert captured["city"] == "Hyderabad"
    # discovery query enriched with service category + state
    assert "Business & Trade" in seen_query["q"]
    assert "Telangana" in seen_query["q"]

    # stored and exposed on the map API
    r = client.get(f"/maps/{slug}", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["service_type"] == "Business & Trade"
    r = client.get(f"/task/{slug}", headers=user["headers"])
    assert r.json()["service_type"] == "Business & Trade"
