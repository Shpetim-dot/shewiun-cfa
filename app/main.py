from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DB_PATH = Path(os.getenv("CFA_DATABASE_PATH", "./data/cfa.db"))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shewiun CFA", version="0.1.0", description="Control & Focus Architecture")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript("""
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
        """)
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


@app.on_event("startup")
def startup() -> None:
    init_db()


def log(action: str, detail: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO activity VALUES (?, ?, ?, ?)", (str(uuid4()), action, detail, now()))


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


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": "Shewiun CFA", "version": "0.1.0",
            "model_configured": bool(os.getenv("CFA_MODEL_API_KEY"))}


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
    live = bool(os.getenv("CFA_MODEL_API_KEY"))
    return [{**a, "provider": os.getenv("CFA_MODEL_NAME", "Configured model") if live else "Local demo",
             "status": "Connected" if live else "Demo mode"} for a in AGENTS]


async def model_reply(role: str, topic: str, context: str) -> str | None:
    key = os.getenv("CFA_MODEL_API_KEY")
    if not key:
        return None
    base = os.getenv("CFA_MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CFA_MODEL_NAME", "gpt-4o-mini")
    system = {
        "Strategist": "You are the Strategist in a multi-agent product council. Identify the opportunity, desired outcome, and priorities. Be concise.",
        "Skeptic": "You are the Skeptic in a multi-agent product council. Challenge assumptions, identify risks, and suggest mitigations. Be constructive.",
        "Builder": "You are the Builder in a multi-agent product council. Turn the discussion into practical steps, dependencies, and an MVP scope.",
        "Synthesizer": "You are the Council Synthesizer. Resolve disagreement, state the strongest shared conclusion, open questions, and next actions."
    }.get(role, f"You are the {role} in a product council. Be concise and specific.")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "system", "content": system},
                  {"role": "user", "content": f"Topic: {topic}\n\nContext from previous speakers:\n{context or '(first speaker)'}"}],
                  "temperature": 0.5})
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


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
    live = bool(os.getenv("CFA_MODEL_API_KEY"))
    try:
        for _ in range(item.rounds):
            for role in roles:
                reply = await model_reply(role, item.topic, context) if live else None
                if reply is None:
                    reply = demo_reply(role, item.topic, context)
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
