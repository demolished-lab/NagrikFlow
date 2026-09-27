"""Path-workflow packet: the citizen-facing artifact of a built map.

Turns real fetch data (graph steps + source meta: final redirect URLs, fetch
tier, official guide links) into:
- ``build_packet``  -> a JSON packet (ordered steps with prerequisites,
  document checklist, fees, apply links, official sources + guides)
- ``render_markdown`` -> the same as Markdown for download / Telegram
  delivery (Hermes hand-off).

Both are pure functions over a TaskMap row — no network.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import worker as workermod


def _sources(raw: str) -> list[dict]:
    """Normalize source_urls (legacy list[str] and list[dict] both accepted)."""
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    out: list[dict] = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, str):
            out.append({"url": item, "ok": True, "guides": []})
        elif isinstance(item, dict):
            out.append({
                "url": item.get("url", ""),
                "ok": bool(item.get("ok", True)),
                "tier": item.get("tier", ""),
                "final_url": item.get("final_url", ""),
                "error": item.get("error", ""),
                "extract": item.get("extract", ""),
                "llm_error": item.get("llm_error", ""),
                "guides": item.get("guides") or [],
                "fetched_at": item.get("fetched_at", ""),
            })
    return out


def source_warnings(sources: list) -> list[str]:
    """User-facing degradation notes for one payload: unreachable sources
    and rules-based (non-AI) extraction — each with the concrete reason,
    so every degraded path is transparent in API responses and the UI."""
    out: list[str] = []
    for s in sources or []:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        host = urlparse(s["url"]).hostname or s["url"]
        if s.get("ok") is False:
            err = str(s.get("error") or "").strip()
            out.append(f"{host} could not be fetched" + (f": {err}" if err else ""))
        elif s.get("extract") == "heuristic":
            reason = str(s.get("llm_error") or "").strip() or "AI model unavailable"
            out.append(
                f"{host}: steps were extracted by rules, not the AI model "
                f"({reason})")
    return out


def build_packet(m) -> dict:
    """Packet JSON for a TaskMap row (pure — no network, no LLM)."""
    try:
        graph = json.loads(m.graph_json or "{}")
    except Exception:
        graph = {}
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []

    prereqs: dict[str, list[str]] = {str(n.get("id")): [] for n in nodes}
    for e in edges:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            a, b = str(e[0]), str(e[1])
            if b in prereqs and a != b and a not in prereqs[b]:
                prereqs[b].append(a)

    steps = []
    for i, n in enumerate(nodes, 1):
        sid = str(n.get("id", ""))
        steps.append({
            "order": i,
            "id": sid,
            "title": n.get("title", ""),
            "type": n.get("type", ""),
            "detail": n.get("detail", ""),
            "fee": n.get("fee", ""),
            "link": (n.get("link") or "").strip(),
            "source": (n.get("url") or "").strip(),
            "prereqs": prereqs.get(sid, []),
        })

    # document checklist: doc tokens named on prerequisite steps (the same
    # requirement-gated text the extractor wrote — nothing fabricated here)
    docs: list[str] = []
    for st in steps:
        if st["type"] != "prereq":
            continue
        for dm in workermod.DOC_RE.finditer(st["detail"] or ""):
            docs.append(dm.group(1).strip())
    checklist = sorted({d for d in docs if d})
    fees = sorted({st["fee"] for st in steps if st["fee"]})
    apply_links = [{"order": st["order"], "title": st["title"],
                    "link": st["link"]}
                   for st in steps if st["link"] and st["type"] in
                   ("action", "payment")]
    sources = _sources(getattr(m, "source_urls", "") or "[]")
    guides: list[dict] = []
    for src in sources:
        for g in src.get("guides", []):
            if g.get("url") and all(g["url"] != x["url"] for x in guides):
                guides.append({"url": g["url"], "title": g.get("title", "")})
    return {
        "slug": m.slug,
        "title": m.title,
        "city": m.city,
        "state": m.state,
        "service_type": m.service_type,
        "verified": bool(getattr(m, "verified_at", None)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "checklist": checklist,
        "fees": fees,
        "apply_links": apply_links,
        "sources": sources,
        "guides": guides,
        "warnings": source_warnings(sources),
        "counts": {
            "steps": len(steps),
            "documents": len(checklist),
            "sources": len([s for s in sources if s.get("ok")]),
            "guides": len(guides),
        },
    }


def render_markdown(p: dict) -> str:
    """Citizen-ready Markdown of a packet (Telegram cap handled by caller)."""
    titles = {st["id"]: st["title"] or st["id"] for st in p["steps"]}
    lines = [f"# {p['title']} — path workflow packet", ""]
    where = " · ".join(x for x in (
        p.get("city") or "", p.get("state") or "",
        p.get("service_type") or "") if x)
    if where:
        lines += [f"Where: {where}", ""]
    if p.get("warnings"):
        lines += ["## Data warnings", ""]
        lines += [f"- {w}" for w in p["warnings"]]
        lines.append("")
    lines += ["## Steps", ""]
    for st in p["steps"]:
        after = ", ".join(titles.get(r, r) for r in st["prereqs"])
        lines.append(f"{st['order']}. **{st['title']}**"
                     + (f" (after: {after})" if after else ""))
        if st["detail"]:
            lines.append(f"   - {st['detail']}")
        if st["fee"]:
            lines.append(f"   - Fee: {st['fee']}")
        if st["link"]:
            lines.append(f"   - Open: {st['link']}")
        elif st["source"]:
            lines.append(f"   - Official source: {st['source']}")
    if p["checklist"]:
        lines += ["", "## Document checklist", ""]
        lines += [f"- {d}" for d in p["checklist"]]
    if p["fees"]:
        lines += ["", "## Fees seen", ""]
        lines += [f"- {f}" for f in p["fees"]]
    lines += ["", "## Official sources", ""]
    for s in p["sources"]:
        if not s.get("url"):
            continue
        bits = ["ok" if s.get("ok") else "unreachable"]
        if s.get("tier"):
            bits.append(f"fetched via {s['tier']}")
        lines.append(f"- <{s['url']}> ({', '.join(bits)})")
        final = s.get("final_url") or ""
        if final and final != s["url"]:
            lines.append(f"  - redirects to: <{final}>")
        for g in s.get("guides", []):
            lines.append(f"  - guide: {g.get('title') or 'document'} "
                         f"<{g.get('url')}>")
    lines += ["",
              f"_Generated {p['generated_at']} from official sources — "
              "always confirm on the portal before paying or submitting._",
              ""]
    return "\n".join(lines)
