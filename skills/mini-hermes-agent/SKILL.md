# Mini-Hermes Built-In Agent

A compact autonomous agent subsystem embedded within Civic Path Navigator. The agent can perceive issues, diagnose root causes using the LLM (Bynara/Ollama), safely fix code, audit every change with before/after diffs, spawn sub-agents for parallel workstreams, self-heal via detect-diagnose-fix-verify loops, and help users explain code, suggest improvements, and automate updates.

**Run modes:**
- Agent loop: perceive -> think -> act -> audit -> verify (auto mode)
- CLI chat: `hermes chat --task "..."`
- REST: POST /agent/run {task, mode, budget}
- Frontend dashboard widget

**Key capabilities:**
1. **Perceive** — detect errors, bugs, missing features from logs and user reports
2. **Diagnose** — gather context via read_file, search_code, check_tests
3. **Plan** — decide minimal set of changes
4. **Act** — make surgical changes one at a time, validate each with validate_python
5. **Verify** — run_tests, check for regressions
6. **Report** — summarize what changed, what's verified, what's left

**Architecture:**
- `backend/app/agent.py` — Main agent loop (AgentLoop class), CLI entry point, background job runner
- `backend/app/agent_tools.py` — Tool registry (10 tools: read_file, write_file, patch_file, search_files, run_cmd, validate_python, list_files, git_status, run_tests, diagnose_db) with TOOL_SCHEMA for REST
- `backend/app/audit.py` — Append-only JSONL audit log with before/after diff, agent attribution, timestamps
- `backend/app/subagent.py` — Parallel sub-agent spawning via BackgroundTasks (parent job ID + budget + callback)

**Configuration:**
- `CIVIC_AGENT_MAX_TURNS` (default 20) — max turns before budget exhaustion
- `CIVIC_AGENT_TIMEOUT` (default 300) — overall timeout in seconds
- Agent operates at `/agent/run`, /agent/result/{job_id}, /agent/tools, /agent/audit endpoints

**Usage examples:**
```
# CLI one-shot:
hermes chat -q "Fix the login bug where wrong password locks account for 15 min"

# REST API:
POST /agent/run { "task": "add parallel-branch rendering to roadmap", "mode": "auto", "budget": 15 }

# Frontend dashboard widget (built into Agent tab)
```

**Pitfalls & Rules:**
- ALWAYS read before writing. Never edit files without seeing their current state (see audit_append).
- ALWAYS validate Python after editing (validate_python).
- ALWAYS run tests after any code change (run_tests).
- If a test fails, diagnose first, then fix, then re-run. Never ship broken code.
- Prefer minimal, surgical changes over rewrites.
- If you cannot fix something safely, report the issue with context and stop.
- For user-facing messages, be helpful and plain-spoken. No jargon.

**CLI entry:**
```
hermes chat --task "Describe what you want to accomplish"
```