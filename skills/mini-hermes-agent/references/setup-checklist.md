# Mini-Hermes Agent Setup Checklist

## Prerequisites

### Backend
- Python 3.11+ venv at `.venv-civic`
- All deps installed: `pip install -r backend/requirements.txt pytest httpx`
- SQLite DB at `backend/civic.db` (created at first startup)
- Backend running: `.venv-civic/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- TELEGRAM_BOT_TOKEN in `backend/.env` (optional but needed for Telegram features)

### Frontend
- Node 20+ with npm
- `npm install` in frontend/ directory
- Vite dev server: `npm run dev` in frontend/ (port 5173)

### Agent-Specific
- Bynara API key (optional but recommended for free models)
  - Set `BYNARA_API_KEY` env var
  - Or run without — agent falls back to local Ollama
- Ollama local model (fallback):
  - Install: `ollama pull openbmb/minicpm5:latest`
  - Run: `ollama serve`
  - Model at `http://localhost:11434`

### Environment Variables
Set these in `backend/.env`:
```
APP_SECRET=change-me-generate-32-random-bytes
DATABASE_URL=sqlite:///./civic.db
DIGILOCKER_ENV=sandbox
TELEGRAM_BOT_TOKEN=  # optional
BYNARA_API_KEY=  # optional
APP_SECRET_PREV=
SESSION_TTL_SECONDS=7200
ALLOW_DEV_SECRET=
FRONTEND_ORIGINS=http://localhost:5173
DIGILOCKER_CLIENT_ID=
DIGILOCKER_CLIENT_SECRET=
DIGILOCKER_REDIRECT_URI=http://localhost:8000/auth/digilocker/callback
NOTIFY_PROVIDER=console
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=openbmb/minicpm5:latest
NOTIFY_PROVIDER=console
```

## Quick Start

### 1. Start Backend
```bash
cd /c/Users/Raja/civic-pathfinder
C:/Users/Raja/.venv-civic/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Start Frontend
```bash
cd /c/Users/Raja/civic-pathfinder/frontend
npm run dev
```

### 3. Test Agent (CLI)
```bash
cd /c/Users/Raja/civic-pathfinder
C:/Users/Raja/.venv-civic/Scripts/python -m app.agent --task "Check health endpoint" --mode auto --budget 5
```

### 4. Test Agent (REST)
```bash
# Launch agent task
curl -X POST http://localhost:8000/agent/run \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"task": "Check health endpoint", "mode": "auto", "budget": 5}'

# Poll result
curl http://localhost:8000/agent/result/{job_id}
```

### 5. Test Agent (Frontend)
- Open http://localhost:5173
- Click "Agent" tab
- Enter task description
- Click "Run Agent"

## Common Issues & Fixes

### "Agent won't start — budget exceeded"
- Increase `CIVIC_AGENT_MAX_TURNS` env var
- Complex tasks may need 20-30 turns

### "LLM unreachable"
- Check `BYNARA_API_KEY` is set OR Ollama is running
- Set `OFFLINE_ONLY=1` to skip Bynara and use only local Ollama
- Verify Ollama model exists: `ollama list`

### "Syntax error after edit"
- Always `validate_python` after `patch_file`
- Read the file with `read_file` before editing
- Use exact `old_string` matches (include surrounding context)

### "Tests fail after change"
- Run `run_tests` to see which tests fail
- Diagnose root cause before fixing
- Never ship broken code

### "Audit log not writing"
- Check write permissions on `backend/agent_audit/` directory
- Ensure directory exists (created automatically on first append)
- Verify `CIVIC_AGENT_LOG` env var isn't disabling logging

## Reference Commands Cheat Sheet

```bash
# Check agent health
curl http://localhost:8000/health

# List available agent tools
curl http://localhost:8000/agent/tools

# Launch agent task
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "your task here", "mode": "auto", "budget": 15}'

# Poll result
curl http://localhost:8000/agent/result/123

# Read audit log
curl http://localhost:8000/agent/audit?n=20

# Run pytest suite
cd /c/Users/Raja/civic-pathfinder
C:/Users/Raja/.venv-civic/Scripts/python -m pytest backend/tests/ -q

# Syntax-check a Python file
C:/Users/Raja/.venv-civic/Scripts/python -c "
from hermes_tools import read_file, validate_python
r = validate_python('backend/app/main.py')
print(r)
"