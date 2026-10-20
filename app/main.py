from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import DATABASE_ERRORS, connect_db, database_backend, database_url
from .agent_launch_rules import evaluate_agent_launch
from .agent_launch_runtime import create_review, get_review_by_token, init_review_tables, _preview_result
from .agent_launch_api import router as agent_launch_router, email_capture_enabled, lead_gate_enabled, privacy_notice_url

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
# Vercel's deployment bundle is read-only. Use /tmp there even if VERCEL
# is not populated in the function runtime or CFA_DATABASE_PATH points into the bundle.
IS_VERCEL = bool(
    os.getenv("VERCEL")
    or os.getenv("VERCEL_ENV")
    or os.getenv("VERCEL_URL")
    or str(ROOT).startswith("/var/task")
)
configured_db_path = os.getenv("CFA_DATABASE_PATH")
if IS_VERCEL:
    DB_PATH = Path("/tmp/cfa.db")
else:
    DB_PATH = Path(configured_db_path or "./data/cfa.db")
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shewiun CFA", version="0.3.0", description="Control & Focus Architecture")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
app.include_router(agent_launch_router)

_RATE_BUCKETS: dict[str, list[float]] = {}
_RATE_LIMIT_PATHS = {
    "/api/auth/login": 5,
    "/api/runtime/runs": 10,
    "/api/council": 10,
    "/api/review/agent-launch/assess": 10,
    "/api/review/agent-launch/unlock": 10,
    "/api/review/agent-launch/authorization-test-request": 5,
    "/api/review/agent-launch/event": 30,
}
_AUTH_PROTECTED_PREFIXES = (
    "/api/projects", "/api/brain", "/api/agents", "/api/council",
    "/api/activity", "/api/security", "/api/runtime", "/api/review/agent-launch/admin",
)


def auth_required() -> bool:
    configured = os.getenv("CFA_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
    return IS_VERCEL or configured


def auth_configured() -> bool:
    password = os.getenv("CFA_ACCESS_PASSWORD", "")
    secret = os.getenv("CFA_SESSION_SECRET", "")
    return len(password) >= 16 and len(secret) >= 32


def _session_token(expiry: int) -> str:
    secret = os.getenv("CFA_SESSION_SECRET", "").encode()
    payload = str(expiry).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def _valid_session(token: str | None) -> bool:
    if not token or not auth_configured():
        return False
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(os.getenv("CFA_SESSION_SECRET", "").encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        return int(payload.decode()) > int(time.time())
    except (ValueError, TypeError, UnicodeDecodeError):
        return False


def _is_protected_api(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _AUTH_PROTECTED_PREFIXES)


def _same_origin(request: Request) -> bool:
    origin_value = request.headers.get("origin")
    if not origin_value:
        return False
    try:
        origin = urlsplit(origin_value)
    except ValueError:
        return False
    host = request.headers.get("host", "").lower()
    if not host or origin.netloc.lower() != host or origin.username or origin.password:
        return False
    if IS_VERCEL:
        return origin.scheme == "https"
    return origin.scheme == request.url.scheme


@app.middleware("http")
async def security_and_access_middleware(request: Request, call_next):
    path = request.url.path
    now_mono = time.monotonic()
    rate_limit = _RATE_LIMIT_PATHS.get(path)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if rate_limit is None and path.startswith("/api/"):
            rate_limit = 60
        if rate_limit is not None:
            client_ip = request.client.host if request.client else "unknown"
            bucket_key = path + ":" + client_ip
            if database_backend() == "postgresql":
                try:
                    allowed = _consume_distributed_rate_limit(bucket_key, rate_limit)
                except DATABASE_ERRORS:
                    return _apply_security_headers(JSONResponse(status_code=503, content={
                        "detail": "Shared rate-limit storage is unavailable; request rejected."
                    }))
                if not allowed:
                    return _apply_security_headers(JSONResponse(status_code=429, content={
                        "detail": "Rate limit reached. Wait one minute and retry."
                    }, headers={"Retry-After": "60"}))
            else:
                hits = [stamp for stamp in _RATE_BUCKETS.get(bucket_key, []) if now_mono - stamp < 60]
                if len(hits) >= rate_limit:
                    response = JSONResponse(status_code=429, content={"detail": "Rate limit reached. Wait one minute and retry."},
                                             headers={"Retry-After": "60"})
                    return _apply_security_headers(response)
                hits.append(now_mono)
                _RATE_BUCKETS[bucket_key] = hits
                if len(_RATE_BUCKETS) > 2000:
                    for key in list(_RATE_BUCKETS)[:500]:
                        if not _RATE_BUCKETS[key] or now_mono - _RATE_BUCKETS[key][-1] >= 60:
                            _RATE_BUCKETS.pop(key, None)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_000_000:
                return _apply_security_headers(JSONResponse(status_code=413, content={"detail": "Request body too large."}))
        except ValueError:
            return _apply_security_headers(JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."}))

    if auth_required() and (_is_protected_api(path) or path == "/api/auth/logout"):
        if not auth_configured():
            return _apply_security_headers(JSONResponse(status_code=503, content={
                "detail": "Workspace access is locked until CFA_ACCESS_PASSWORD (minimum 16 characters) and CFA_SESSION_SECRET (minimum 32 characters) are configured in the server environment."
            }))
        if not _valid_session(request.cookies.get("cfa_session")):
            return _apply_security_headers(JSONResponse(status_code=401, content={"detail": "Sign in to access the workspace."}))
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _same_origin(request):
            return _apply_security_headers(JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected."}))

    response = await call_next(request)
    return _apply_security_headers(response)


def _apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    if IS_VERCEL:
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
    return response


def model_provider_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or (os.getenv("CFA_MODEL_API_KEY") and os.getenv("CFA_MODEL_NAME")))


def configured_model_name() -> str | None:
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return os.getenv("CFA_MODEL_NAME") if os.getenv("CFA_MODEL_API_KEY") and os.getenv("CFA_MODEL_NAME") else None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    # Explicit SQLite paths are retained for tests and local development.
    return connect_db(None if database_url() else DB_PATH)


def _consume_distributed_rate_limit(bucket_key: str, limit: int) -> bool:
    current = time.time()
    with connect() as db:
        row = db.execute(
            """INSERT INTO api_rate_limits (bucket_key, window_started_at, count)
               VALUES (?, ?, 1)
               ON CONFLICT(bucket_key) DO UPDATE SET
                 count = CASE
                   WHEN excluded.window_started_at - api_rate_limits.window_started_at >= 60 THEN 1
                   ELSE api_rate_limits.count + 1
                 END,
                 window_started_at = CASE
                   WHEN excluded.window_started_at - api_rate_limits.window_started_at >= 60
                   THEN excluded.window_started_at ELSE api_rate_limits.window_started_at
                 END
               RETURNING count""",
            (bucket_key, current),
        ).fetchone()
    return bool(row and row[0] <= limit)


def init_db() -> None:
    with connect() as db:
        schema = """
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brain (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'Fact', source TEXT NOT NULL DEFAULT 'User input',
          confidence INTEGER NOT NULL DEFAULT 80, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS council (
          id TEXT PRIMARY KEY, topic TEXT NOT NULL, result TEXT NOT NULL,
          transcript TEXT NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
          id TEXT PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL,
          actor TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approval_requests (
          id TEXT PRIMARY KEY, action_type TEXT NOT NULL, description TEXT NOT NULL, requested_by TEXT NOT NULL,
          risk_level TEXT NOT NULL, status TEXT NOT NULL, decision_by TEXT, decision_note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS runtime_runs (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, input_json TEXT NOT NULL,
          state_json TEXT NOT NULL, result_json TEXT, error TEXT, attempt INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL DEFAULT 3, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          started_at TEXT, finished_at TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_runtime_runs_status_created ON runtime_runs(status, created_at);
        CREATE TABLE IF NOT EXISTS api_rate_limits (
          bucket_key TEXT PRIMARY KEY, window_started_at DOUBLE PRECISION NOT NULL, count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runtime_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES runtime_runs(id)
        );
        """
        if database_backend() == "postgresql":
            schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
        db.executescript(schema)
        if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            db.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", (
                "proj-cfa", "Shewiun CFA MVP", "Build the control center for collaborative AI agents.", "Active", now()
            ))
        if db.execute("SELECT COUNT(*) FROM brain").fetchone()[0] == 0:
            samples = [
                ("CFA principle", "CFA coordinates external models and agents; it is not itself a new foundation model.", "Rule", "Product brief", 95),
                ("Shared knowledge", "Knowledge entries should keep their source and confidence visible.", "Decision", "Product brief", 90),
                ("Human oversight", "High-impact actions should require explicit human approval.", "Rule", "Security baseline", 95),
            ]
            for title, content, kind, source, confidence in samples:
                db.execute("INSERT INTO brain VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (str(uuid4()), title, content, kind, source, confidence, now()))
        if db.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 0:
            db.execute("INSERT INTO activity VALUES (?, ?, ?, ?)",
                       (str(uuid4()), "Workspace initialized", "CFA local workspace is ready.", now()))


_runtime_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    global _runtime_worker_task
    init_db()
    init_review_tables(None if database_url() else DB_PATH)
    # Single-process SQLite MVP: recover interrupted runs after restart.
    with connect() as db:
        db.execute("UPDATE runtime_runs SET status='queued', updated_at=?, error=NULL WHERE status='running'", (now(),))
    _runtime_worker_task = asyncio.create_task(runtime_worker())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _runtime_worker_task
    if _runtime_worker_task:
        _runtime_worker_task.cancel()
        try:
            await _runtime_worker_task
        except asyncio.CancelledError:
            pass
        _runtime_worker_task = None


def append_audit(event_type: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a hash-linked audit event. This detects edits to the chain; it is not a signed external ledger."""
    created_at = now()
    event_id = str(uuid4())
    canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with connect() as db:
        row = db.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = row["event_hash"] if row else "GENESIS"
        material = json.dumps({
            "id": event_id, "event_type": event_type, "actor": actor, "payload": json.loads(canonical_payload),
            "previous_hash": previous_hash, "created_at": created_at
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        import hashlib
        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        db.execute(
            "INSERT INTO audit_events (id,event_type,actor,payload,previous_hash,event_hash,created_at) VALUES (?,?,?,?,?,?,?)",
            (event_id, event_type, actor, canonical_payload, previous_hash, event_hash, created_at)
        )
    return {"id": event_id, "event_type": event_type, "actor": actor, "payload": payload,
            "previous_hash": previous_hash, "event_hash": event_hash, "created_at": created_at}


def log(action: str, detail: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO activity VALUES (?, ?, ?, ?)", (str(uuid4()), action, detail, now()))
    append_audit("workspace.activity", "system", {"action": action, "detail": detail})


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class BrainIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    content: str = Field(min_length=1, max_length=5000)
    kind: str = Field(default="Fact", max_length=40)
    source: str = Field(default="User input", max_length=200)
    confidence: int = Field(default=80, ge=0, le=100)


class CouncilIn(BaseModel):
    topic: str = Field(min_length=3, max_length=4000)
    roles: list[str] = Field(default_factory=lambda: ["Strategist", "Skeptic", "Builder"])
    rounds: int = Field(default=1, ge=1, le=2)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=512)


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict[str, Any]:
    required = auth_required()
    configured = auth_configured()
    return {
        "required": required,
        "configured": configured,
        "authenticated": (not required) or _valid_session(request.cookies.get("cfa_session")),
        "setup_message": (
            "Configure CFA_ACCESS_PASSWORD (16+ characters) and CFA_SESSION_SECRET (32+ characters) in Vercel Environment Variables."
            if required and not configured else None
        ),
    }


@app.post("/api/auth/login")
def auth_login(item: LoginIn, request: Request):
    if not auth_required():
        return {"ok": True, "auth_required": False}
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Workspace authentication is not configured.")
    if not hmac.compare_digest(item.password, os.getenv("CFA_ACCESS_PASSWORD", "")):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    expiry = int(time.time()) + 8 * 60 * 60
    response = JSONResponse({"ok": True, "expires_in": 8 * 60 * 60})
    response.set_cookie(
        "cfa_session", _session_token(expiry), max_age=8 * 60 * 60, httponly=True,
        secure=(request.url.scheme == "https" or IS_VERCEL), samesite="strict", path="/",
    )
    return response


@app.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("cfa_session", path="/", httponly=True, secure=IS_VERCEL, samesite="strict")
    return response


def database_connection_ok() -> bool:
    try:
        with connect() as db:
            db.execute("SELECT 1").fetchone()
        return True
    except DATABASE_ERRORS:
        return False


@app.get("/api/health")
def health() -> dict[str, Any]:
    db_ok = database_connection_ok()
    return {
        "status": "ok",
        "app": "Shewiun CFA",
        "version": "0.3.0",
        "auth_required": auth_required(),
        "auth_configured": auth_configured(),
        "authentication": "configured" if auth_configured() else ("required_but_missing" if auth_required() else "development_open"),
        "model_configured": model_provider_configured(),
        "model_provider": "Google Gemini API" if os.getenv("GEMINI_API_KEY") else ("OpenAI-compatible" if os.getenv("CFA_MODEL_API_KEY") and os.getenv("CFA_MODEL_NAME") else None),
        "model_name": configured_model_name(),
        "free_agent_available": True,
        "free_agent_name": "Gemini Flash (API key required; free-tier availability depends on Google account and current limits)",
        "database": database_backend(),
        "database_connection_ok": db_ok,
        "storage_persistent": database_backend() == "postgresql" or not IS_VERCEL,
        "database_backend": database_backend(),
        "distributed_rate_limits": database_backend() == "postgresql",
        "durable_queue": False,
        "email_unlock_configured": email_capture_enabled(),
        "retention_configured": len(os.getenv("CRON_SECRET", "")) >= 32,
        "production_ready": False,
        "readiness_blockers": [
            *(["workspace authentication secrets are not configured"] if auth_required() and not auth_configured() else []),
            *(["persistent PostgreSQL storage is not configured"] if database_backend() != "postgresql" else []),
            *(["configured PostgreSQL connection is unavailable"] if database_backend() == "postgresql" and not db_ok else []),
            *(["rate limiting is process-local, not distributed"] if database_backend() != "postgresql" else []),
            "background orchestration queue is process-local",
            *(["model provider key is not configured"] if not model_provider_configured() else []),
            *(["public HTTPS privacy notice is not configured for email capture"] if IS_VERCEL and not privacy_notice_url() else []),
            *(["CRON_SECRET is not configured for retention automation"] if IS_VERCEL and len(os.getenv("CRON_SECRET", "")) < 32 else []),
        ],
        "queue": "in_process",
        "storage": "postgresql" if database_backend() == "postgresql" else ("ephemeral_sqlite" if IS_VERCEL else "sqlite"),
        "storage_warning": (
            "Vercel /tmp storage is ephemeral; data may be lost between instances or deployments."
            if IS_VERCEL and database_backend() != "postgresql" else None
        ),
    }


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]


@app.post("/api/projects")
def create_project(item: ProjectIn) -> dict[str, Any]:
    record = {"id": str(uuid4()), "name": item.name.strip(), "description": item.description.strip(),
              "status": "Active", "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO projects VALUES (:id, :name, :description, :status, :created_at)", record)
    log("Project created", record["name"])
    return record


@app.get("/api/brain")
def list_brain() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM brain ORDER BY created_at DESC")]


@app.post("/api/brain")
def create_brain(item: BrainIn) -> dict[str, Any]:
    record = {"id": str(uuid4()), **item.model_dump(), "title": item.title.strip(),
              "content": item.content.strip(), "source": item.source.strip(), "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO brain VALUES (:id, :title, :content, :kind, :source, :confidence, :created_at)", record)
    log("Brain entry added", record["title"])
    return record


AGENTS = [
    {"id": "strategist", "name": "Strategist", "role": "Direction & priorities", "provider": "CFA demo", "status": "Ready", "color": "violet"},
    {"id": "skeptic", "name": "Skeptic", "role": "Risks & counterarguments", "provider": "CFA demo", "status": "Ready", "color": "amber"},
    {"id": "builder", "name": "Builder", "role": "Implementation & next steps", "provider": "CFA demo", "status": "Ready", "color": "mint"},
    {"id": "synthesizer", "name": "Synthesizer", "role": "Decision & summary", "provider": "CFA demo", "status": "Ready", "color": "blue"},
]


@app.get("/api/agents")
def list_agents() -> list[dict[str, str]]:
    live = model_provider_configured()
    return [{**a, "provider": configured_model_name() if live else "Not configured",
             "status": "Connected" if live else "Demo mode"} for a in AGENTS]


async def model_reply(role: str, topic: str, context: str) -> str | None:
    system = {
        "Strategist": "You are the Strategist in a multi-agent product council. Identify the opportunity, desired outcome, and priorities. Be concise.",
        "Skeptic": "You are the Skeptic in a multi-agent product council. Challenge assumptions, identify risks, and suggest mitigations. Be constructive.",
        "Builder": "You are the Builder in a multi-agent product council. Turn the discussion into practical steps, dependencies, and an MVP scope.",
        "Synthesizer": "You are the Council Synthesizer. Resolve disagreement, state the strongest shared conclusion, open questions, and next actions."
    }.get(role, f"You are the {role} in a product council. Be concise and specific.")
    prompt = f"Topic: {topic}\\n\\nContext from previous speakers:\\n{context or '(first speaker)'}"
    async with httpx.AsyncClient(timeout=45) as client:
        if os.getenv("GEMINI_API_KEY"):
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY")},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1200}},
            )
            response.raise_for_status()
            parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            answer = "\\n".join(p.get("text", "") for p in parts if p.get("text"))
            if not answer.strip():
                raise RuntimeError("Gemini returned no text content.")
            return answer.strip()
        key = os.getenv("CFA_MODEL_API_KEY")
        model = os.getenv("CFA_MODEL_NAME")
        if not key or not model:
            return None
        base = os.getenv("CFA_MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        response = await client.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "system", "content": system},
                  {"role": "user", "content": prompt}], "temperature": 0.4, "max_tokens": 1200})
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        if not answer or not answer.strip():
            raise RuntimeError("Configured model returned no text content.")
        return answer.strip()


def demo_reply(role: str, topic: str, context: str) -> str:
    snippets = {
        "Strategist": f"Frame “{topic}” around one measurable outcome. Start with the smallest workflow that demonstrates user value, then expand only after validating adoption.",
        "Skeptic": "Main risks: unclear success criteria, hidden integration costs, and too much automation before trust is earned. Define a baseline, show sources, and keep consequential actions behind human approval.",
        "Builder": "Proposed sequence: (1) define the target user and acceptance criteria, (2) build one end-to-end path, (3) record decisions and evidence, (4) test with real tasks, (5) prioritize from observed friction.",
        "Synthesizer": "Recommendation: run a narrow, measurable pilot. Align on the success metric, document assumptions in CFA Brain, assign one owner per action, and review evidence before increasing scope."
    }
    return snippets.get(role, f"Assess “{topic}” from the perspective of {role}. State the key recommendation, assumptions, and next action.")


@app.post("/api/council")
async def start_council(item: CouncilIn) -> dict[str, Any]:
    roles = [r for r in item.roles if r in {"Strategist", "Skeptic", "Builder"}]
    if not roles:
        roles = ["Strategist", "Skeptic", "Builder"]
    if "Synthesizer" not in roles:
        roles.append("Synthesizer")
    transcript: list[dict[str, str]] = []
    context = ""
    live = model_provider_configured()
    if not live:
        raise HTTPException(status_code=503, detail="No model configured. Add GEMINI_API_KEY for the Gemini Flash integration, or set CFA_MODEL_API_KEY and CFA_MODEL_NAME.")
    try:
        for _ in range(item.rounds):
            for role in roles:
                reply = await model_reply(role, item.topic, context)
                if not reply:
                    raise ValueError(f"The configured model returned no content for role {role}.")
                transcript.append({"role": role, "content": reply})
                context += f"\n{role}: {reply}"
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Configured model request failed: {exc}") from exc
    result = next((m["content"] for m in reversed(transcript) if m["role"] == "Synthesizer"), transcript[-1]["content"])
    record = {"id": str(uuid4()), "topic": item.topic, "result": result,
              "transcript": json.dumps(transcript, ensure_ascii=False), "mode": "live" if live else "demo",
              "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO council VALUES (:id, :topic, :result, :transcript, :mode, :created_at)", record)
    log("Council completed", item.topic[:180])
    return {**record, "transcript": transcript}


@app.get("/api/council")
def list_councils() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM council ORDER BY created_at DESC LIMIT 10").fetchall()
    return [{**dict(r), "transcript": json.loads(r["transcript"])} for r in rows]


@app.get("/api/activity")
def list_activity() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM activity ORDER BY created_at DESC LIMIT 20")]


# --- CFA Security: policy decisions, human approvals and verifiable audit chain ---

RISK_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
POLICY_DEFAULTS = {
    "project.create": "allow",
    "brain.write": "allow",
    "council.run": "allow",
    "external.write": "approval_required",
    "external.delete": "approval_required",
    "secrets.read": "deny",
    "shell.execute": "deny",
}


class ApprovalIn(BaseModel):
    action_type: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=2000)
    requested_by: str = Field(default="workspace-owner", min_length=1, max_length=100)
    risk_level: str = Field(default="high")


class ApprovalDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    decided_by: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=1000)


def verify_audit_chain() -> dict[str, Any]:
    import hashlib
    expected_previous = "GENESIS"
    checked = 0
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_events ORDER BY seq ASC").fetchall()
    for row in rows:
        payload = json.loads(row["payload"])
        material = json.dumps({
            "id": row["id"], "event_type": row["event_type"], "actor": row["actor"], "payload": payload,
            "previous_hash": row["previous_hash"], "created_at": row["created_at"]
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        calculated = hashlib.sha256(material.encode("utf-8")).hexdigest()
        if row["previous_hash"] != expected_previous or row["event_hash"] != calculated:
            return {"valid": False, "checked": checked, "failed_event_id": row["id"]}
        expected_previous = row["event_hash"]
        checked += 1
    return {"valid": True, "checked": checked, "head": expected_previous}


@app.get("/api/security/policies")
def security_policies() -> dict[str, Any]:
    return {
        "default_effect": "deny for unknown action types",
        "policies": [{"action_type": k, "decision": v} for k, v in POLICY_DEFAULTS.items()],
        "note": "Policy reference layer for the MVP; no external tools are executed."
    }


@app.get("/api/security/audit")
def security_audit(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    return {"integrity": verify_audit_chain(), "events": [
        {**dict(r), "payload": json.loads(r["payload"])} for r in rows
    ]}


@app.post("/api/security/approvals")
def request_approval(item: ApprovalIn) -> dict[str, Any]:
    risk = item.risk_level.lower()
    if risk not in RISK_LEVELS:
        raise HTTPException(status_code=422, detail="risk_level must be low, medium, high, or critical")
    policy = POLICY_DEFAULTS.get(item.action_type, "deny")
    if policy == "deny":
        status = "rejected"
    elif policy == "approval_required" or RISK_LEVELS[risk] >= 3:
        status = "pending"
    else:
        status = "approved"
    record = {
        "id": str(uuid4()), "action_type": item.action_type, "description": item.description.strip(),
        "requested_by": item.requested_by, "risk_level": risk, "status": status,
        "decision_by": "policy-engine" if status != "pending" else None,
        "decision_note": "Policy decision: " + policy, "created_at": now(),
        "decided_at": now() if status != "pending" else None
    }
    with connect() as db:
        db.execute(
            "INSERT INTO approval_requests (id,action_type,description,requested_by,risk_level,status,decision_by,decision_note,created_at,decided_at) VALUES (:id,:action_type,:description,:requested_by,:risk_level,:status,:decision_by,:decision_note,:created_at,:decided_at)",
            record
        )
    append_audit("approval.requested", item.requested_by, {
        "approval_id": record["id"], "action_type": item.action_type, "risk_level": risk, "status": status
    })
    log("Approval " + status, item.action_type + ": " + item.description[:150])
    return record


@app.get("/api/security/approvals")
def list_approvals(status: str | None = None) -> list[dict[str, Any]]:
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM approval_requests WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM approval_requests ORDER BY created_at DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/security/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, item: ApprovalDecisionIn) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Approval request has already been decided")
        decided_at = now()
        db.execute(
            "UPDATE approval_requests SET status=?, decision_by=?, decision_note=?, decided_at=? WHERE id=? AND status='pending'",
            (item.decision, item.decided_by, item.note, decided_at, approval_id)
        )
        record = dict(db.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone())
    append_audit("approval." + item.decision, item.decided_by, {
        "approval_id": approval_id, "action_type": record["action_type"], "note": item.note
    })
    log("Approval " + item.decision, record["action_type"] + " decided by " + item.decided_by)
    return record


@app.get("/api/security/audit/verify")
def audit_verify() -> dict[str, Any]:
    return verify_audit_chain()

# --- CFA Agent Runtime: durable queue, per-speaker checkpoints, bounded retries ---

RUNTIME_ROLES = ("Strategist", "Skeptic", "Builder", "Synthesizer")
_RUNTIME_POLL_SECONDS = 0.75

def _runtime_event(run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    with connect() as db:
        db.execute("INSERT INTO runtime_events (run_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
                   (run_id, event_type, json.dumps(payload, ensure_ascii=False), now()))

def _runtime_run(row: sqlite3.Row, include_state: bool = True) -> dict[str, Any]:
    item = dict(row)
    item["input"] = json.loads(item.pop("input_json"))
    state = json.loads(item.pop("state_json"))
    if include_state:
        item["state"] = state
    result_json = item.pop("result_json")
    item["result"] = json.loads(result_json) if result_json else None
    item["cancel_requested"] = bool(item["cancel_requested"])
    return item

async def _execute_runtime_run(run_id: str) -> None:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
    if not row or row["status"] != "running":
        return
    item = _runtime_run(row)
    request, state = item["input"], item["state"]
    roles, transcript = state["roles"], state["transcript"]
    live = model_provider_configured()
    try:
        while state["next_index"] < len(roles):
            with connect() as db:
                current = db.execute("SELECT status,cancel_requested FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
            if not current or current["cancel_requested"] or current["status"] == "cancelled":
                with connect() as db:
                    db.execute("UPDATE runtime_runs SET status='cancelled',updated_at=?,finished_at=? WHERE id=?", (now(), now(), run_id))
                _runtime_event(run_id, "run.cancelled", {"completed_steps": len(transcript)})
                return
            role = roles[state["next_index"]]
            context = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
            if not live:
                raise RuntimeError("No model configured. Add GEMINI_API_KEY for Gemini Flash or configure CFA_MODEL_API_KEY and CFA_MODEL_NAME.")
            reply = await model_reply(role, request["topic"], context)
            if not reply:
                raise RuntimeError(f"The configured model returned no content for role {role}.")
            transcript.append({"role": role, "content": reply, "step": state["next_index"]})
            state["next_index"] += 1
            state["transcript"] = transcript
            # Persist after every completed speaker; restart resumes from next_index.
            with connect() as db:
                db.execute("UPDATE runtime_runs SET state_json=?,updated_at=? WHERE id=? AND status='running'",
                           (json.dumps(state, ensure_ascii=False), now(), run_id))
            _runtime_event(run_id, "step.completed", {"index": state["next_index"] - 1, "role": role})
        result = next((m["content"] for m in reversed(transcript) if m["role"] == "Synthesizer"),
                      transcript[-1]["content"] if transcript else "")
        result_record = {"topic": request["topic"], "result": result, "transcript": transcript,
                         "mode": "live" if live else "demo"}
        with connect() as db:
            db.execute("UPDATE runtime_runs SET status='completed',result_json=?,updated_at=?,finished_at=?,error=NULL WHERE id=? AND status='running'",
                       (json.dumps(result_record, ensure_ascii=False), now(), now(), run_id))
            db.execute("INSERT INTO council VALUES (?, ?, ?, ?, ?, ?)",
                       (run_id, request["topic"], result, json.dumps(transcript, ensure_ascii=False), result_record["mode"], now()))
        _runtime_event(run_id, "run.completed", {"mode": result_record["mode"], "steps": len(transcript)})
        log("Council runtime completed", request["topic"][:180])
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        with connect() as db:
            row = db.execute("SELECT attempt,max_attempts FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
            if row and row["attempt"] < row["max_attempts"]:
                db.execute("UPDATE runtime_runs SET status='queued',error=?,updated_at=? WHERE id=?",
                           (str(exc)[:1000], now(), run_id))
                event_type = "run.retry_scheduled"
            else:
                db.execute("UPDATE runtime_runs SET status='failed',error=?,updated_at=?,finished_at=? WHERE id=?",
                           (str(exc)[:1000], now(), now(), run_id))
                event_type = "run.failed"
        _runtime_event(run_id, event_type, {"error": str(exc)[:500]})
        if event_type == "run.failed":
            log("Council runtime failed", f"{run_id}: {str(exc)[:120]}")

async def runtime_worker() -> None:
    # SQLite runtime intentionally supports one app worker process at a time.
    while True:
        run_id = None
        with connect() as db:
            row = db.execute("SELECT id FROM runtime_runs WHERE status='queued' ORDER BY created_at ASC LIMIT 1").fetchone()
            if row:
                run_id = row["id"]
                changed = db.execute("UPDATE runtime_runs SET status='running',attempt=attempt+1,started_at=COALESCE(started_at,?),updated_at=? WHERE id=? AND status='queued'",
                                     (now(), now(), run_id)).rowcount
                if not changed:
                    run_id = None
        if run_id:
            _runtime_event(run_id, "run.started", {})
            await _execute_runtime_run(run_id)
        else:
            await asyncio.sleep(_RUNTIME_POLL_SECONDS)

class RuntimeCouncilIn(BaseModel):
    topic: str = Field(min_length=3, max_length=4000)
    roles: list[str] = Field(default_factory=lambda: ["Strategist", "Skeptic", "Builder"])
    rounds: int = Field(default=1, ge=1, le=2)
    max_attempts: int = Field(default=3, ge=1, le=5)

@app.post("/api/runtime/runs", status_code=202)
def create_runtime_run(item: RuntimeCouncilIn) -> dict[str, Any]:
    if not model_provider_configured():
        raise HTTPException(status_code=503, detail="No model configured. Add GEMINI_API_KEY for Gemini Flash or configure CFA_MODEL_API_KEY and CFA_MODEL_NAME.")
    roles = [role for role in item.roles if role in {"Strategist", "Skeptic", "Builder"}]
    if not roles:
        roles = ["Strategist", "Skeptic", "Builder"]
    if "Synthesizer" not in roles:
        roles.append("Synthesizer")
    expanded_roles = roles * item.rounds
    run_id, timestamp = str(uuid4()), now()
    request = {"topic": item.topic.strip(), "roles": roles, "rounds": item.rounds}
    state = {"roles": expanded_roles, "next_index": 0, "transcript": []}
    with connect() as db:
        db.execute("INSERT INTO runtime_runs (id,kind,status,input_json,state_json,attempt,max_attempts,created_at,updated_at) VALUES (?,?,?,?,?,0,?,?,?)",
                   (run_id, "council", "queued", json.dumps(request, ensure_ascii=False), json.dumps(state, ensure_ascii=False), item.max_attempts, timestamp, timestamp))
    _runtime_event(run_id, "run.queued", {"kind": "council", "steps": len(expanded_roles)})
    append_audit("runtime.run.queued", "workspace-owner", {"run_id": run_id, "kind": "council"})
    return {"id": run_id, "kind": "council", "status": "queued", "created_at": timestamp, "poll_url": f"/api/runtime/runs/{run_id}"}

@app.get("/api/runtime/runs")
def list_runtime_runs(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM runtime_runs WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM runtime_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_runtime_run(row) for row in rows]

@app.get("/api/runtime/runs/{run_id}")
def get_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        events = db.execute("SELECT event_type,payload_json,created_at FROM runtime_events WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
    result = _runtime_run(row)
    result["events"] = [{**dict(e), "payload": json.loads(e["payload_json"])} for e in events]
    return result

@app.post("/api/runtime/runs/{run_id}/retry", status_code=202)
def retry_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        if row["status"] not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Only failed or cancelled runs can be retried")
        state = json.loads(row["state_json"])
        db.execute("UPDATE runtime_runs SET status='queued',error=NULL,finished_at=NULL,cancel_requested=0,updated_at=? WHERE id=?", (now(), run_id))
    _runtime_event(run_id, "run.requeued", {"resume_from_step": state["next_index"]})
    return {"id": run_id, "status": "queued", "resume_from_step": state["next_index"]}

@app.post("/api/runtime/runs/{run_id}/cancel")
def cancel_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT status FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        if row["status"] in {"completed", "failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Run is already terminal")
        db.execute("UPDATE runtime_runs SET cancel_requested=1,updated_at=? WHERE id=?", (now(), run_id))
    _runtime_event(run_id, "run.cancel_requested", {})
    return {"id": run_id, "status": "cancellation_requested"}



# --- Public Agent Launch Review: deterministic Phase 1 assessment ---

class AgentLaunchAssessmentIn(BaseModel):
    answers: dict[str, Any] = Field()


@app.get("/review/agent-launch")
def agent_launch_review_page() -> FileResponse:
    return FileResponse(STATIC / "agent-launch.html")


@app.get("/review/agent-launch/result/{share_token}")
def agent_launch_review_result_page(share_token: str) -> FileResponse:
    # The random token is the capability for this private, read-only share URL.
    # Result API returns 404 for unknown/revoked tokens; no public index exists.
    return FileResponse(STATIC / "agent-launch.html", headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/api/review/agent-launch/result/{share_token}")
def get_agent_launch_result(share_token: str) -> dict[str, Any]:
    result = get_review_by_token(None if database_url() else DB_PATH, share_token, require_lead=lead_gate_enabled())
    if result is None:
        raise HTTPException(status_code=404, detail="Review not found or link revoked.")
    if result.get("lead_required"):
        result["privacy_notice_url"] = privacy_notice_url()
    return result


@app.post("/api/review/agent-launch/assess")
async def assess_agent_launch(item: AgentLaunchAssessmentIn) -> dict[str, Any]:
    encoded = json.dumps(item.answers, ensure_ascii=False)
    if len(encoded) > 20000:
        raise HTTPException(status_code=413, detail="Answers exceed the 20 KB limit.")
    try:
        result = await create_review(None if database_url() else DB_PATH, item.answers, allow_share=(database_backend() == "postgresql" or not IS_VERCEL))
    except DATABASE_ERRORS:
        raise HTTPException(status_code=503, detail="Review storage is unavailable. Please try again later.")
    if not result["model_configured"]:
        result["assessment_type"] = "deterministic_self_assessment"
    result["preliminary_status"] = result["deterministic"]["preliminary_status"]
    result["findings"] = result["deterministic"]["findings"]
    result["finding_count"] = result["deterministic"]["finding_count"]
    result["note"] = ("Model-backed perspectives and synthesis completed." if result["model_configured"]
                      else "No model was called. This is a deterministic self-assessment preview only.")
    if lead_gate_enabled():
        preview = _preview_result(result)
        preview["privacy_notice_url"] = privacy_notice_url()
        return preview
    return result
