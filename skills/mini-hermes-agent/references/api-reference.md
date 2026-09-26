# Mini-Hermes Agent API Reference

## Base URL
All endpoints: `http://localhost:8000/api/v1/agent/` (prefix added by FastAPI)

## Endpoints

### GET /agent/tools
**Description:** List all available agent tools with their JSON schemas.

**Response:**
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read a file with line numbers. Use for inspecting code before patching.",
      "params": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Path to file, relative to BASE"},
          "offset": {"type": "integer", "description": "Line number to start from (1-indexed)"},
          "limit": {"type": "integer", "description": "Max lines to read (default: 50, max: 2000)"}
        },
        "required": ["path"]
      }
    },
    {
      "name": "write_file",
      "description": "Overwrite a file completely. Safe for new files; use patch_file for edits.",
      "params": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "content": {"type": "string"}
        },
        "required": ["path", "content"]
      }
    },
    {
      "name": "patch_file",
      "description": "Find-and-replace in a file (fuzzy match). Returns diff.",
      "params": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "old_string": {"type": "string"},
          "new_string": {"type": "string"},
          "replace_all": {"type": "boolean", "default": false}
        },
        "required": ["path", "old_string", "new_string"]
      }
    },
    {
      "name": "search_files",
      "description": "Search file contents or find files by glob pattern.",
      "params": {
        "type": "object",
        "properties": {
          "pattern": {"type": "string"},
          "path": {"type": "string", "default": "."},
          "target": {"type": "string", "enum": ["content", "files"], "default": "content"},
          "file_glob": {"type": "string"},
          "limit": {"type": "integer", "default": 30}
        },
        "required": ["pattern"]
      }
    },
    {
      "name": "run_cmd",
      "description": "Execute a shell command and return stdout/stderr/exit_code.",
      "params": {
        "type": "object",
        "properties": {
          "command": {"type": "string"},
          "cwd": {"type": "string", "description": "Working directory (default: BASE)"},
          "timeout": {"type": "integer", "description": "Max seconds (default: 120)"},
          "env_extra": {"type": "object"}
        },
        "required": ["command"]
      }
    },
    {
      "name": "validate_python",
      "description": "Syntax-check a Python file. Returns errors or ok.",
      "params": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        },
        "required": ["path"]
      }
    },
    {
      "name": "list_files",
      "description": "List files/dirs under path, respecting max_depth.",
      "params": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "default": "."},
          "recursive": {"type": "boolean", "default": false},
          "max_depth": {"type": "integer", "description": "Max depth (default: 3)"}
        },
        "required": []
      }
    },
    {
      "name": "git_status",
      "description": "Show git status, recent commits, and uncommitted changes.",
      "params": {
        "type": "object",
        "properties": {},
        "required": []
      }
    },
    {
      "name": "run_tests",
      "description": "Run pytest suite. filter_str narrows to a module or keyword.",
      "params": {
        "type": "object",
        "properties": {
          "filter_str": {"type": "string"},
          "verbosity": {"type": "integer", "default": 1}
        },
        "required": []
      }
    },
    {
      "name": "diagnose_db",
      "description": "Inspect SQLite schema, row counts, and health.",
      "params": {
        "type": "object",
        "properties": {},
        "required": []
      }
    }
  ]
}
```

### POST /agent/run
**Description:** Launch a mini-Hermes agent task asynchronously. Returns a job_id for polling.

**Request:**
```json
{
  "task": "Describe what you want to accomplish",
  "mode": "auto",  // "auto" | "help" | "chat"
  "budget": 20     // max turns (default from env CIVIC_AGENT_MAX_TURNS)
}
```

**Response:**
```json
{
  "job_id": 123,
  "status": "queued"
}
```

### GET /agent/result/{job_id}
**Description:** Poll the result of an agent job.

**Response (pending):**
```json
{
  "job_id": 123,
  "status": "queued"
}
```

**Response (done):**
```json
{
  "job_id": 123,
  "status": "done",
  "result": {
    "status": "done",
    "turns": 5,
    "elapsed_secs": 3.2,
    "task": "your task here",
    "final": "The agent completed the task successfully.",
    "via": "bynara/openbmb/minicpm5:latest"
  },
  "finished": true
}
```

**Response (failed):**
```json
{
  "job_id": 123,
  "status": "failed",
  "result": {
    "status": "failed",
    "turns": 3,
    "elapsed_secs": 2.1,
    "task": "your task here",
    "error": "Error message describing what went wrong"
  }
}
```

**Response (timeout):**
```json
{
  "job_id": 123,
  "status": "timeout",
  "result": {
    "status": "timeout",
    "turns": 20,
    "elapsed_secs": 30.0,
    "task": "your task here"
  }
}
```

### GET /agent/audit?n=50
**Description:** Read the last N entries from the agent audit log.

**Response:**
```json
{
  "entries": [
    {
      "ts": "2026-09-27T00:27:15.332Z",
      "action": "tool_call",
      "target": "patch_file",
      "summary": "Replaced rate limit configuration",
      "agent": "mini-hermes",
      "turn": 3,
      "success": true
    },
    {
      "ts": "2026-09-27T00:27:16.127Z",
      "action": "run_tests",
      "target": "backend/tests/",
      "summary": "29 tests passed",
      "agent": "mini-hermes",
      "turn": 4,
      "success": true
    }
  ]
}
```

## Error Responses

All endpoints may return these error formats:

**404 Not Found:**
```json
{"detail": "unknown job"}
```

**400 Bad Request:**
```json
{"detail": "task required"}
```

**500 Internal:**
```json
{"detail": "error message from agent execution"}
```

## Authentication

Most endpoints require admin authentication. Set `ALLOW_DEV_SECRET=1` in `backend/.env` for development, or use proper JWT tokens in production.

**Header example:**
```http
Authorization: Bearer <admin-jwt-token>
```

Or with dev secret:
```http
APP_SECRET=change-me-generate-32-random-bytes
```

## Versioning

API version: v1 (subject to change as agent features evolve).

## Changelog

- **v1.0.0** — Initial release with 10 tools, agent loop, audit trail, sub-agent spawning, REST + CLI interfaces.