"""Database compatibility helpers for SQLite development and PostgreSQL deployments."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import class_row


def database_url() -> str | None:
    return os.getenv("CFA_DATABASE_URL") or os.getenv("DATABASE_URL")


def database_backend() -> str:
    return "postgresql" if database_url() else "sqlite"


class CompatRow(dict):
    """Mapping row that also supports SQLite-style integer indexing."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresConnection:
    """Small adapter for the existing SQLite-shaped query layer."""

    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def execute(self, query: str, params: Any = None):
        if params is None:
            return self._connection.execute(query)
        if isinstance(params, dict):
            query = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", query)
        else:
            query = re.sub(r"\?", "%s", query)
        return self._connection.execute(query, params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self._connection.execute(statement)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            return self._connection.__exit__(exc_type, exc, traceback)
        finally:
            self._connection.close()

    def close(self) -> None:
        self._connection.close()


def connect_db(path: Path | str | None = None):
    """Connect to PostgreSQL when configured; explicit paths always select SQLite."""
    url = database_url() if path is None else None
    if url:
        connection = psycopg.connect(
            url,
            connect_timeout=10,
            application_name="shewiun-cfa",
            row_factory=class_row(CompatRow),
        )
        return PostgresConnection(connection)

    if path is None:
        path = os.getenv("CFA_DATABASE_PATH", "./data/cfa.db")
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
