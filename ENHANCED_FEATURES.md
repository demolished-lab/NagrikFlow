# CivicPath — Enhanced Features

Feature roadmap distilled from the deep research sweep (see `FREE_RESOURCES.md`).
Items are checked when implemented **and covered by the test suite**.

## Shipped — 2026-10-04 (research → build sprint)

### 1. Evidence snapshots (`app/evidence.py`, `models.SourceSnapshot`)
Every built map now stores **immutable evidence per source**: fetched text,
raw HTML (when the tier-1 fetch captured it), sha256 of both, fetch tier,
final redirect URL, and retrieval timestamp. Capped (50 KB text / 400 KB
HTML per row) and pruned to the newest few per (slug, url).
- Why: the AI is not the database — evidence is. This is what makes
  verification, diffs and audits possible later.
- Written by `jobs.run_build` from `build_map` results; survives rechecks.

### 2. Change diffs on the night watch (`app/watch.py`, `models.ChangeEvent`)
When a recheck detects a source change it no longer only revokes the
verification stamp: it stores a **readable unified diff** of what actually
moved (`ChangeEvent`), so the admin review queue and citizens can see
*"Form F fee text changed"*, not just *"something changed"*.
- `GET /task/{slug}/changes` → newest-first change events with diffs
  (same visibility rule as `GET /task/{slug}`).
- First recheck after upgrade establishes a text baseline (no event).

### 3. schema.org / JSON-LD extraction (`app/semantics.py`)
Gov portals increasingly emit JSON-LD (`GovernmentService`, `Offer`,
`FAQPage`, `HowTo`). A dependency-free extractor pulls **structured facts**
(service name, description, fee/price, documents mentioned, provider,
application URL) straight from raw HTML — no LLM, no hallucination risk.
- Attached to each source entry as `facts` and used to seed a node when the
  LLM and heuristics both return nothing.

### 4. Common Crawl CDX discovery lane (`app/discover.py`)
When live search finds nothing, CivicPath now asks the **Common Crawl CDX
index** for archived URLs on the catalog's government domains — discovering
deep form/PDF pages *without hitting the live government site at all*.
- Polite by construction: 1 HTTPS GET to a public index, keyword-filtered,
  https+.gov only, `CIVIC_CDX=0` opts out (tests run with it off).
- Discovery order: live search → CDX archive → curated catalog
  (`discovery: "search" | "cdx" | "catalog"`).

### 5. India source seeds (`app/catalog.py`)
Catalog expanded with the research's P0/P1 Indian sources:
- **Aaple Sarkar** (Maharashtra, 2,362-service table) for state services
- **BMC/MyBMC** for Mumbai municipal workflows (shop & establishment,
  trade/hawker/advertisement licences, property, certificates)
- **Delhi e-District** for Delhi certificates/services
- New keyword families: shop/establishment, trade licence, municipal,
  birth/death/marriage certificate, property, building, hawker.

### 6. Free-tier LLM lanes (`app/llm.py`)
Between Bynara and Ollama there are now **env-gated free providers**:
Groq (best free lane: no card, no expiry), Google AI Studio/Gemini
(`flash-lite`), and OpenRouter `:free`. Set `GROQ_API_KEY` / `GEMINI_API_KEY`
/ `OPENROUTER_API_KEY` (+ optional `*_MODEL`) and they join the role chain
automatically; no key → behaviour unchanged. Still $0, still no hard
dependency — each lane is optional and failure only walks to the next.

---

## Roadmap — next (research-backed, not yet built)

### P1 — proof & mining
- [ ] **API Setu partner key** request (unlocks myScheme v6 + MahaOpenAPI)
      — only blocker is human signup (PENDING.md).
- [ ] **Aaple Sarkar table miner** — parse the 2,362-row service table into
      `services/requirements` rows (dept, time limit, officer, fee) using the
      Nivesh Mitra SOP schema as the canonical shape.
- [ ] **extruct microdata/RDFa** alongside JSON-LD for portals that skip
      JSON-LD (BSD-3, tiny).
- [ ] **promptfoo eval** in CI: golden gov-page fixtures → extraction
      assertions (fee/document/link) so prompts can't silently regress.
- [ ] **bge-m3 embeddings** (MIT, multilingual) + pgvector hybrid BM25 for
      service matching — replaces token-jaccard service lookup.

### P2 — trust & history
- [ ] **warcio WARC evidence** for byte-exact archives of fetched pages.
- [ ] **Near-dup detection (simhash)** so cosmetic restyles don't revoke
      trust; only material text changes do.
- [ ] **Historical timeline** via Wayback/Common Crawl CDX: "this
      requirement was different on <date>" on the roadmap UI.
- [ ] **Change events → review queue UI** with approve/reject + diff viewer
      (Label Studio-style, self-hosted, Apache-2.0).
- [ ] **pySHACL shapes** validating the extracted graph (every requirement
      must cite a source; every edge must be acyclic + typed).

### P3 — scale & distribution
- [ ] **Dagster asset freshness** (or keep cron) when source count > 100.
- [ ] **Cloudflare Pages** deploy for the frontend + Workers API lane.
- [ ] **Static machine-readable registry** (`/api/v1/*.json`, VAANI
      pattern) so others embed the civic graph — the moat becomes public
      infrastructure.
- [ ] **WhatsApp/Telegram channel** growth (Cloudflare Worker webhook free
      tier; Meta Cloud API 1,000 free conversations/mo — never unofficial
      automation).
- [ ] **GraphRAG / LightRAG** (both MIT) over the evidence DB for
      cross-jurisdiction questions, running on local Ollama.
- [ ] **Temporal/hatchet** migration if the in-process job queue outgrows
      single-box operation.

### Standing rules (from the research)
1. Deterministic rules decide; the LLM only extracts and explains.
2. No proof link = no display; every fact keeps url + timestamp + hash.
3. Commercial APIs (Brave/Gemini/Brave-style SERP) are adapters, never
   foundations — see FREE_RESOURCES §5 for the current free-tier truth.
4. Never vendor AGPL/GPL code (firecrawl, PyMuPDF, pywb, searxng…);
   process-boundary only, as with wigolo/obscura.
5. Crawl politely: robots gate → rate limit → cache; exhaust open archives
   (Common Crawl) before touching live government servers.
