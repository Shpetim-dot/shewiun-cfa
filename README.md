# Shewiun CFA

**CFA — Control & Focus Architecture** is a provider-agnostic workspace for coordinating AI agents, shared knowledge and team-style agent discussions.

> MVP status: working starter application. The Council currently supports a deterministic demo mode; connect an OpenAI-compatible endpoint to enable live model responses.

## Features
- Workspace dashboard with projects, tasks and recent activity
- CFA Brain: source-aware knowledge entries with type, confidence and source
- CFA Council: start a multi-role discussion and receive a synthesis
- CFA Control: inspect agents and their operating status
- CFA Security: visible safety defaults, activity log and approval-oriented design
- SQLite persistence; responsive dark navy / cream UI
- Optional OpenAI-compatible chat-completions integration

## Run locally
Requires Python 3.11+.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Optional live model
Set these in your environment or `.env`:
- `CFA_MODEL_BASE_URL` — OpenAI-compatible API base, default `https://api.openai.com/v1`
- `CFA_MODEL_API_KEY` — API key
- `CFA_MODEL_NAME` — model identifier, default `gpt-4o-mini`

Without a key, Council runs in clearly labeled demo mode. Never commit real keys.

## API
- `GET /api/health`
- `GET/POST /api/projects`
- `GET/POST /api/brain`
- `GET /api/agents`
- `GET/POST /api/council`
- `GET /api/activity`

## Security notes
This is an MVP, not a hardened multi-user production system. It does not execute arbitrary tools or shell commands. Before production use, add authentication, per-user authorization, encrypted secret storage, rate limiting, backups, structured provider-specific controls and deployment secrets. Model calls can send the entered meeting prompt to the configured provider.
