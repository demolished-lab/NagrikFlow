# CivicPath — Free Resource Registry

Curated from a deep multi-platform research sweep (GitHub, HN/Reddit/V2EX,
vendor docs, live URL probes) on **2026-10-04**. Everything here is either
open-source software, openly licensed data, or a *free tier explicitly
verified on the stated date*. The governing principle:

> **Open source can be free forever. A hosted free tier cannot be assumed to
> be.** Commercial APIs are optional accelerators, never foundations.

Status legend: ✅ verified live / installed here · 📋 researched, not yet
adopted · ⚠️ license or terms caveat · 🔴 avoid as dependency.

---

## 0. What we already run (do not re-add)

| Layer | Tool | License |
|---|---|---|
| Fetch cascade | trafilatura → crawl4ai → obscura → scrapling → jina → wigolo | Apache-2.0 / process-boundary |
| Discovery | wigolo 18-engine keyless search + `catalog.py` seeds | AGPL run as separate process |
| Extraction | LLM lanes (Bynara → free providers → Ollama) + deterministic heuristics | — |
| Change watch | sha256 fingerprints + auto-unverify (`watch.py`) | ours |
| Storage | SQLite → PostgreSQL (`migrate.py`), jobs with leases | — |
| UI | React + React Flow + dagre | MIT |

---

## 1. India government sources (the real raw material)

### Tier P0 — machine-readable national layer

| Source | URL | Access | Notes |
|---|---|---|---|
| **API Setu directory** | https://directory.apisetu.gov.in/ | HTML SSR, 4,216 API collections / 2,966 orgs | master index of govt APIs; not enumerable (signed headers) — crawl category pages |
| **API Setu OpenAPI mirror** | `https://api.apis.guru/v2/specs/apisetu.gov.in/{svc}/{ver}/openapi.json` | keyless JSON | **181 apisetu specs** incl. all 36 `transport{st}`, `edistrictup`, `jharsewa`, `igrmaharashtra`, `epfindia`, `pan`, `csc` — machine-readable contract instead of scraping |
| **Aaple Sarkar (Maharashtra)** | https://aaplesarkar.mahaonline.gov.in/en/CommonForm/ViewAllServices | 2,362-row SSR table: dept, service, time limit, officer, **fee** | Maharashtra backbone; robots 404 (crawlable) |
| **Nivesh Mitra (UP)** | https://niveshmitra.up.gov.in/ | SOP PDFs with exact KG schema: docs, fees, stage-wise procedure + time | **schema donor** for our requirement model |
| **India Code mirror** | https://indiacode.ecourtsindia.com/api + `/data/acts.csv` (1.9 MB) | keyless JSON/Markdown + Akoma Ntoso, **CC BY 4.0** | law layer ("why is this required?") — cleaner than scraping indiacode.gov.in |
| **myScheme** | `https://api.myscheme.gov.in/search/v6/schemes` | needs `x-api-key` (via API Setu partner signup) | ~4,700 schemes — **key to request** (PENDING.md) |

### Tier P1 — catalogues worth crawling

| Source | URL | Notes |
|---|---|---|
| india.gov.in services | https://www.india.gov.in/services | SSR Next.js, stable kebab slugs, `/services/details/{slug}`; sitemap only 55 URLs |
| ServicePlus | https://serviceonline.gov.in/ | "Know Your Eligibility" metadata model — best template for requirement graphs |
| BMC / MyBMC | https://www.mcgm.gov.in/, https://portal.mcgm.gov.in/irj/portal/ | Public Service Charter + **"BMC Services published in Gazette.pdf"** + trade-wise licence list |
| Delhi e-District | https://edistrict.delhi.gov.in/in/en/Public/Services.html | service list + `/Public/ApplicationForm.html` forms |
| TN e-Sevai | https://www.tnesevai.tn.gov.in/Pages/ServiceList.aspx | dept/service/manual/timeline/fee/documents columns |
| PMC Pune | https://www.pmc.gov.in/en/online_services | **nested sitemap.xml works** + citizen charter |
| Passport Document Advisor | portal2.passportindia.gov.in `docAdvisor` | per-passport-type doc + fee matrix |
| Udyam | https://udyamregistration.gov.in/ | paperless; Aadhaar+PAN requirements on-page (already seeded) |
| EPFO | https://epfo.gov.in/ | robots allow-all + sitemap; apisetu spec exists |
| PRS Legislative | https://prsindia.org/billtrack | robots allow + Crawl-delay 10 |
| DoPT circulars | https://dopt.gov.in/rss.xml | working RSS 2.0 (feed lane) |
| OpenCity CKAN | `https://data.opencity.in/api/3/action/package_search` | keyless CKAN, 1,099 municipal datasets, public domain |

### Licensing / terms (store with every record)

- **GODL-India** (data.gov.in): attribution, no endorsement, no DRM —
  `https://data.gov.in/Godl`. Note: `robots.txt` on data.gov.in is
  `Disallow: /` → **use its API/key lane, do not crawl the site**.
- **CC BY 4.0**: indiacode.ecourtsindia.com.
- **GIGW 3.0** (`guidelines.india.gov.in`): govt sites are *pushed* toward
  APIs + MyScheme/data.gov.in integration — policy tailwind for us.
- Per-dept content policies vary (reproduce-with-attribution vs prior
  permission). Our rule stands: **store structured facts + citation + URL +
  timestamp; never redistribute the page** (see `GOVERNMENT_READINESS_AUDIT.md`).
- Crawlability matrix (probed 2026-10-04): most service catalogues have
  robots 404 and no sitemap → hit known list pages directly, 1–2 req/s,
  cache locally. Exceptions: data.gov.in (blocked), mygov.in (Crawl-delay 10).

### Keys worth requesting (all free)

1. **API Setu partner key** — unlocks myScheme v6, `rdapi.mahaonline`
   GetServiceList, data.gov.in-style gateways (already in PENDING.md).
2. **data.gov.in API key** — `api.data.gov.in/resource/{id}?api-key=…`.
3. **DigiLocker requester creds** — sandbox already works.

---

## 2. Discovery — finding the right government URLs

| Resource | License | Use here |
|---|---|---|
| **Common Crawl CDX index** (`index.commoncrawl.org`, `collinfo.json`) | open data | ✅ **adopted this sprint** — discover deep gov URLs (forms/PDFs) without touching the live site; `discover.cdx_*` (`CIVIC_CDX=0` opts out) |
| **cdx_toolkit** (216★) | Apache-2.0 | 📋 programmatic CDX + IA queries at scale |
| **whirlwind-python** (Common Crawl official) | Apache-2.0 | 📋 WARC/WET/WAT tour; byte-range random access |
| Common Crawl `robotstxt` subset | open data | 📋 mine every historically-crawled robots.txt for free |
| Common Crawl URL Index (Parquet + DuckDB/Athena) | open data | 📋 bulk URL discovery at sub-cent query cost; `.gov` is unusually well-archived (~2,500 pages/domain vs ~80 typical) |
| SearXNG self-host | ⚠️ AGPL-3.0 | 📋 internal-only metasearch; add `json` to `search.formats` in settings.yml; never a hard dependency |
| whoogle-search | MIT | 📋 permissive single-engine proxy |
| Marginalia | ⚠️ custom license | 📋 great at small-web/.gov document pages — check terms |
| Wayback CDX (`web.archive.org/cdx/...`) | IA terms | 📋 historical page versions for change timelines |
| Common Crawl *before* live crawling | — | rule: exhaust open archives first, then 1 polite req/s |

---

## 3. Fetching politely

| Resource | License | Note |
|---|---|---|
| curl_cffi | MIT | `impersonate="chrome"` TLS fingerprint rotation; drop-in for httpx |
| httpx + aiolimiter | MIT | leaky-bucket per-host limiter |
| stdlib `urllib.robotparser` | PSF | ✅ already the pattern; robots is a **hard gate** |
| Playwright | Apache-2.0 | ✅ installed (JS portals) |
| camoufox | ⚠️ ~1-yr maintenance gap (2026) | verify before adopting |
| cloakbrowser / bordeaux / reptor | unverified repos | 📋 anti-detect browsers — unproven |
| Community wisdom (V2EX/Reddit) | — | rate limiting is the whole game; *poll + notify a human, never auto-submit*; most proxy services prohibit .gov domains; if the site dies you're first in the logs |

---

## 4. Cleaning & document mining

| Stage | Pick | License | Runner-up |
|---|---|---|---|
| HTML → text | ✅ trafilatura (6.9k★) | Apache-2.0 | jusText (BSD-2), python-readability (Apache-2.0), ReadabiliPy (MIT) |
| Files → Markdown | **markitdown** (188k★) | MIT | docling (68k★, MIT) for layout+tables |
| PDF → Markdown | **marker** (40k★) | Apache-2.0 | docling (MIT); 🔴 PyMuPDF4LLM is AGPL — avoid distributing |
| Tables in PDFs | **pdfplumber** (10.8k★) | MIT | microsoft/table-transformer (MIT) for scanned tables |
| Scanned/Indic OCR | **PaddleOCR** (90k★, Devanagari model) | Apache-2.0 | surya (90+ langs incl. Indic, Apache-2.0), tesseract `hin`/`mar`, EasyOCR |
| PDF at scale | olmocr (19.7k★) | Apache-2.0 | 🔴 MinerU is AGPL |
| Structured metadata | **extruct** (972★) | BSD-3 | 📋 JSON-LD/microdata/RDFa from govt pages; we ship stdlib JSON-LD first (`app/semantics.py`) |
| schema.org extraction | ✅ `app/semantics.py` | ours | wire extruct when microdata-heavy sources matter |

---

## 5. Generation — inference & extraction

### Free LLM API tiers (verified Sep–Oct 2026)

| Provider | Free status | Card? | Catch |
|---|---|---|---|
| **Groq** | best free lane: ~30 RPM / 1,000 RPD per model | No | Llama removed from free tier (Aug 2026) |
| **Google AI Studio / Gemini** | permanent free tier, limits unpublished | No | training data outside EU/UK; prefer `flash-lite` (main often 503) |
| **OpenRouter `:free`** | permanent free models, 20 RPM / 50 RPD (1,000 after $10 lifetime credit) | No | some free models logged/trained |
| **Cloudflare Workers AI** | 10,000 neurons/day forever | No | includes **IndicTrans2** (Indic translation) |
| **GitHub Models / Copilot Free** | ~15 RPM; 2,000 completions/mo | No | "prototyping, not production" |
| **Mistral Experiment** | ~1B tokens/mo | No | ⚠️ requires data-training opt-in |
| **Hugging Face Inference** | ~$0.10/mo credit | No | hard stop at 0 |
| **Cerebras** | 🔴 trial-only now ($5/30 days) | Yes | do not build on it |
| Trial-credit farms (SambaNova, Fireworks, Together…) | one-time balance | varies | walls quickly |

✅ **Adopted this sprint**: Groq + Gemini + OpenRouter as env-gated lanes in
`app/llm.py` (key present → tried between Bynara and Ollama). Canonical
tracker to keep current: `cheahjs/free-llm-api-resources` on GitHub.
Gateway pattern reference: `freelm` (Python, pools 6 free providers,
quota-aware routing).

### Local (the actual "free forever" backbone)

| Tool | License | Note |
|---|---|---|
| Ollama | MIT | ✅ installed; `OLLAMA_MODEL` pinned (minicpm5 — qwen3.5 OOMs on 16 GB) |
| llama.cpp server | MIT | JSON-schema/function calling; faster than Ollama for batch |
| vLLM / SGLang | Apache-2.0 | GPU production; SGLang has constrained decoding built in |
| Qwen3 (most sizes) | **Apache-2.0** ✅ | cleanest license; phi-4 (MIT) also good small extractor |
| ⚠️ Llama 4 / Gemma 3 / Ministral | custom terms | verify before shipping |
| **instructor** | MIT | validated structured outputs + retries over any OpenAI-compatible endpoint |
| **outlines** / **xgrammar** | Apache-2.0 | JSON-schema constrained decoding |
| **guidance** | MIT | grammar-controlled generation |
| **Google langextract** (38.9k★) | Apache-2.0 | 📋 schema'd extraction with **source-span grounding** — perfect for citation-first claims |
| Community lesson (r/ollama) | — | put semantics in Pydantic field names, restate schema in prompt, validate+retry; production bar ≈ Mistral-24B for no-confabulation |

---

## 6. Storage, graph & retrieval

| Pick | License | Note |
|---|---|---|
| PostgreSQL + **pgvector** | Postgres + MIT | ✅ CI runs full suite on PG16; HNSW, `SET LOCAL hnsw.ef_search`, `unnest()` batch inserts; stays right to ~20M chunks |
| rank_bm25 / PG text search | Apache-2.0 | hybrid lexical leg alongside vectors |
| **bge-m3** embedding model | MIT ✅ | multilingual + long-context + hybrid dense/sparse — Hindi/English mix |
| sentence-transformers | Apache-2.0 | standard encode path |
| networkx | BSD-3 | dependency DAG math (topological order, cycle checks — we already hand-roll this) |
| graphology | MIT | JS-side graph object |
| **kuzu** (embedded property graph) | MIT | 📋 Cypher without running a server — better fit than Neo4j on a laptop; 🔴 Neo4j itself is GPL-3 |
| RDFLib + **pySHACL** | BSD-3 / Apache-2.0 | 📋 SHACL constraints to *validate* extracted graphs ("eligibility requires doc X") |
| microsoft graphrag / LightRAG | MIT | 📋 LLM-driven entity-relation extraction; LightRAG (40k★) cheap enough for Ollama |
| **graphiti** (31k★) | Apache-2.0 | 📋 **temporal** knowledge graph — tracks when a fact stopped being true ("rule changed on date X") |
| Meilisearch | ⚠️ AGPL | internal corpus only or buy |
| Benchmark reality (r/vectordatabase, prod writeups) | — | pgvector HNSW ≈ Qdrant speed at 1M/1536d; $45 vs $280/mo; dedicated DB only >~20M chunks |

---

## 7. Change detection & provenance (the killer feature)

| Resource | License | Status |
|---|---|---|
| sha256 fingerprints + auto-unverify | ours | ✅ `watch.py` |
| **unified diffs on change** | stdlib | ✅ **this sprint** — `ChangeEvent` rows with a readable diff of what moved |
| **Evidence snapshots** (text + raw HTML + hashes + timestamps) | ours | ✅ **this sprint** — `SourceSnapshot`, `GET /task/{slug}/changes` |
| warcio | Apache-2.0 | 📋 store raw pages as immutable WARC evidence |
| pywb (CDX + replay) | 🔴 GPL-3 | internal viewer only; shows citizens "the page as it was on date X" |
| diff-match-patch | Apache-2.0 | 📋 char-level diffs for reviewer UI |
| changedetection.io (34.7k★) | Apache-2.0 | 📋 self-host page monitor with filters + visual diff + JSON API |
| huginn | MIT | 📋 agent event pipelines ("if changed → job → notify") |
| simhash / ssdeep | varies | 📋 near-duplicate detection (cosmetic restyles shouldn't revoke trust) |
| **prov** (W3C PROV) / dataprov | MIT / small | 📋 formal provenance chains with SHA-256 checksums |

---

## 8. Validation, verification & human-in-the-loop

| Pick | License | Status |
|---|---|---|
| pydantic schema gates | MIT | ✅ used across API |
| Deterministic dependency engine | ours | ✅ LLM never invents edges unchallenged — validate/dedupe/acyclicity in `_add_edges` |
| **promptfoo** (25.7k★) | MIT | 📋 extraction-prompt assertions in CI (`npx promptfoo eval`) |
| Label Studio CE | Apache-2.0 | 📋 review queue for fee/eligibility claims |
| doccano | MIT | 📋 lighter annotation UI |
| ragas | Apache-2.0 | 📋 RAG faithfulness metrics |
| Opik (Comet) | Apache-2.0 | 📋 self-hosted tracing |
| Langfuse | MIT core + proprietary `ee/` | 📋 self-host traces (ClickHouse-owned now) |
| 🔴 deepchecks | AGPL + `ee/` | avoid |

---

## 9. Orchestration & hosting (₹0 lanes)

| Pick | License | Status |
|---|---|---|
| In-process job queue + DB leases | ours | ✅ `jobs.py` (claim/lease/recovery) |
| hatchet (8k★) / trigger.dev (16k★) | MIT / Apache-2.0 | 📋 durable workflows when we outgrow the in-process queue; Temporal (MIT) if ops-heavy |
| dagster | Apache-2.0 | 📋 **asset-based** freshness ("which govt sources are stale") |
| Prefect | Apache-2.0 | low-ceremony flows |
| 🔴 n8n | Sustainable Use License | internal automations only, never the core engine |
| **Cloudflare Pages** (frontend) | free: 500 builds/mo, 20k files | ✅ target (or GitHub Pages) |
| **Cloudflare Workers/D1/R2/Vectorize** | free: 100k req/day, D1 5M rows read/d, R2 10 GB no egress | 📋 zero-cost API+DB+objects+search lane |
| Vercel Hobby | 100 deploys/day | frontend alternative |
| 🔴 Fly.io | no free tier (≥$2.19/30d) | plan ~$3–5/mo if ever needed |
| Cloudflare Tunnel (`cloudflared`) | free | expose the home box without a server |
| GitHub Actions | free unlimited (public repos) | ✅ CI already |
| WhatsApp Cloud API | 1,000 conversations/mo free | 📋 distribution once validated; Baileys-style automation = ToS risk |
| Cloudflare Project Galileo | free civic security | 📋 apply — positioned as civic infrastructure |
| Precedent | — | Kaya Guides (India) runs ~500k WA msgs/mo on Cloudflare; AP "Mana Mitra" = 161 services on WhatsApp |

---

## 10. Ready-made datasets (skip scraping where it exists)

| Dataset | What | Where |
|---|---|---|
| `smartduketech/indian-government-schemes-2025` | 4,693 schemes **with parsed eligibility fields** (gender, caste, income ₹, state…) | HuggingFace |
| `shrijayan/gov_myscheme` | sitemap-scraped myScheme + 723 PDFs w/ text | HuggingFace |
| `satyajitdas/bharatschemes-v1` | 2,029 scheme Q&A pairs (Apache-2.0) | HuggingFace |
| `endomorphosis/ipfs_india_laws` | 849 instruments / 35,400 articles of India Code (en+hi) + collector script | HuggingFace |
| `RUDXLABS/india-central-state-acts` | 34,729 act PDFs | HuggingFace |
| `ankitjh4/bharat-government-documents` | deduped crawl→screen→publish corpus template | HuggingFace |
| `fireboy21/tenders_aoc` | ~16.6M structured tender records 2011–2026 | HuggingFace |
| `joyboseroy/rti-bench` | 1,516 CIC RTI cases (CC BY 4.0) | GitHub |
| datameet org | India boundary GeoJSON, **municipal ward boundaries**, election data | GitHub (MIT / CC-BY) |
| SIH problem statements | 229+ daily-mirrored with changelog | `vedantchalke36/sih-2026-problem-statements` (CC BY 4.0) |
| OpenCity CKAN | 1,099 municipal datasets, keyless API | data.opencity.in |
| tender.sarthaksidhant.com | raw SQLite mirrors w/ SHA-256 | community |

---

## 11. Prior art & competitors (steal the lessons, not the code)

| Project | Lesson for CivicPath |
|---|---|
| ClearTax | monetizes *execution* (filing), not information; their "AI Neha" had to move deep-nav links out of RAG into a 30-enum tool — **near-identical URLs defeat similarity search** (our graph + exact links win here) |
| IndiaFilings / VakilSearch / BankBazaar | ₹399–1,500 per-registration fees = the market we hand off to |
| **Yojana-Khojna** | 4,669 schemes in SQLite, `parsed_eligibility` = 70+ structured columns → branching decision tree; proves structure-the-text-once is the moat |
| **Yojana-Saathi** | 5-agent pipeline, rule engine ≠ keyword search, 119 tests |
| **VAANI (Rajasthan)** | "34 verified schemes only by design" + **versioned static `api/v1/` registry** others can embed |
| CivicSahayak | offline PWA, no backend |
| DataDollars/opportunity-ai-engine | closest analog: myScheme+data.gov.in crawlers, **SHA-256 raw dedupe**, Pydantic-normalized objects |
| Yojana-Setu | gov crawler → staging → **admin moderation** → public API (mirrors our review queue) |
| Civic Compass (HN) | address → which office serves you |
| RTI Online MCP server | read-only MCP for RTI (community) |

Positioning (unchanged, now with evidence): **the open, evidence-backed
dependency graph of public services** — not another gov chatbot.

---

## 12. Communities & trackers to keep watching

- `cheahjs/free-llm-api-resources` — bot-updated free-API directory (the
  source of truth behind §5).
- HN Algolia threads: "Crawling More Politely Than Big Tech", Common Crawl
  pipeline posts, "My failures: Civic technology ideas that didn't work"
  (Joshua Tauberer), FireStriker ("Making Civic Tech Free").
- r/webscraping, r/developersIndia, r/StartUpIndia, r/Indianlaw — gov
  scraping norms (public records = safest class; DPDP = personal data;
  ToS-silent monetization is where risk concentrates).
- V2EX scraping threads — rate-limit-first wisdom, RSSHub-for-gov-notices
  pattern (turn notice boards into RSS = clean structured history).
- datameet Google Group, CivicDataLab, iSPIRT, PRS Legislative Research,
  hackathons.mygov.in (community scrapers fill its API gap).
- agent-reach / wigolo / obscura / page-agent — the local tooling lane this
  repo already builds on.

---

## 13. License danger list (never vendor into this MIT repo)

🔴 AGPL: firecrawl, searxng, PyMuPDF/PyMuPDF4LLM, MinerU, ckan, meilisearch,
mwmbl, deepchecks · 🔴 GPL-3: pywb, neo4j, windmill (AGPL+CE) ·
⚠️ custom: Marginalia, urlwatch (unset), GOT-OCR2.0 (unset), REBEL (unset),
camelot (stale/unclear) · ⚠️ model terms: Llama 4, Gemma 3, Mistral
(data-training opt-in) · ⚖️ process-boundary rule already in PRODUCTION.md
applies to wigolo & friends: **subprocess/REST only, never linked**.
