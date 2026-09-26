# Mini-Hermes Agent Reference

## Tool Call Syntax

Agent tool calls follow this format in the LLM response:

```
<tool_call> read_file(path="backend/app/main.py", offset=1, limit=50)
```

or with JSON args:

```
<tool_call> run_cmd(command="python -m pytest backend/tests/ -q", timeout=120)
```

## Available Tools (10 total)

| Tool | Purpose | Key Args |
|------|---------|----------|
| `read_file` | Read file with line numbers | `path`, `offset` (1-indexed), `limit` (default 50) |
| `write_file` | Overwrite file completely | `path`, `content` |
| `patch_file` | Find-and-replace (fuzzy) | `path`, `old_string`, `new_string`, `replace_all` (default false) |
| `search_files` | Find code/text | `pattern`, `path` (default "."), `target` ("content"|"files"), `file_glob`, `limit` (default 30) |
| `run_cmd` | Execute shell command | `command`, `cwd` (default BASE), `timeout` (default 120), `env_extra` |
| `validate_python` | Syntax-check Python file | `path` |
| `list_files` | Directory listing | `path` (default "."), `recursive`, `max_depth` (default 3) |
| `git_status` | Check git state | none |
| `run_tests` | Run pytest suite | `filter_str` (narrow by module/keyword), `verbosity` (1=quiet) |
| `diagnose_db` | Inspect SQLite health | none |

## Mini-Agent Loop Execution

Each turn follows: system prompt -> user msg -> LLM call -> parse tool calls -> execute -> audit -> history update.

**Agent config** (from env or defaults):
- `CIVIC_AGENT_MAX_TURNS` — max turns before budget exhausted (default 20)
- `CIVIC_AGENT_TIMEOUT` — overall timeout in seconds (default 300)

When done (no tool calls in LLM response), the agent returns final text and logs an `agent_run` audit entry.

## Common Workflows

### Fix a Python Bug
1. `read_file` the affected file to see current state
2. `patch_file` the bug with minimal change
3. `validate_python` to confirm syntax
4. `run_tests` to verify fix
5. Report result

### Add a New Feature
1. `search_files` for related code to understand patterns
2. `read_file` existing similar feature
3. `write_file` or `patch_file` new code
4. `run_tests` to confirm no regressions
5. Audit entry auto-generated

### Diagnose DB Issue
1. `diagnose_db` to inspect tables, rows, indexes
2. Plan migration or fix
3. If Postgres: auto-append `m005_postgres` migration when DATABASE_URL starts with `postgresql://`

## Sub-Agent Spawning

Spawn parallel workstreams:

```python
from backend.app.subagent import spawn_subagent, spawn_parallel

# Single sub-agent (background thread)
sub_id = spawn_subagent(engine, parent_job_id, "Fix login lockout bug", budget=10)

# Multiple parallel sub-agents
sub_ids = spawn_parallel(engine, parent_job_id, [
    {"id": "fix-login", "task": "Fix login lockout bug"},
    {"id": "add-test", "task": "Add login lockout test"}
])
```

Each sub-agent gets its own budget and reports results via the Job DB.

## Audit Log Format

Each audit entry is a JSON line in `backend/agent_audit/audit.jsonl`:

```json
{
  "ts": "2026-09-27T00:27:15.332Z",
  "action": "tool_call",
  "target": "patch_file",
  "summary": "old_string[:200]",
  "agent": "mini-hermes",
  "turn": 3,
  "success": true,
  "meta": {
    "parent_job": null,
    "sub_job": null
  }
}
```

Key fields:
- `action`: what was done (tool_call, agent_run, sub_spawn, etc.)
- `target`: tool name or task target
- `summary`: brief description (<=200 chars)
- `agent`: always "mini-hermes"
- `turn`: turn number in this run
- `success`: whether the action succeeded
- `meta`: parent/child job relationships

## REST Endpoints

- `GET /agent/tools` — List available tools with schemas
- `POST /agent/run` — Launch agent task asynchronously
- `GET /agent/result/{job_id}` — Poll result status
- `GET /agent/audit?n=50` — Read last N audit entries

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `CIVIC_AGENT_MAX_TURNS` | `20` | Max turns per agent run |
| `CIVIC_AGENT_TIMEOUT` | `300` | Overall timeout in seconds |
| `OFFLINE_ONLY` | (unset) | If "1", skip Bynara, use only local Ollama |
| `DIGILOCKER_ENV` | `sandbox` | DigiLocker environment |

## Development Notes

- Agent is **Bynara-first**: tries free cloud models (nemotron-3-ultra-free, nemotron-3-super-free, nemotron-3.5-lightning-free) before falling back to local Ollama
- All LLM decisions stay in deterministic rules; LLM only PHRASES/EXTRACTS
- Agent tools are idempotent where possible; patch_file uses fuzzy matching
- Audit log is append-only; entries never overwrite prior entries
- Sub-agents use ThreadPoolExecutor with max_workers=4
- Frontend Agent tab built into App.tsx — see `frontend/src/Agent.tsx`

## Troubleshooting

If agent appears stuck:
1. Check `CIVIC_AGENT_MAX_TURNS` — increase if task is complex
2. Check `CIVIC_AGENT_TIMEOUT` — increase if long-running operations
3. Verify backend is running (check /health endpoint)
4. Check audit log at `/agent/audit` for last action and result
5. If LLM errors, verify BYNARA_API_KEY is set or Ollama is running at localhost:11434