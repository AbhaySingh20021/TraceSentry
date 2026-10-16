"""Small SQLite persistence layer; database path can be set with TRACESENTRY_DB."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from tracesentry.schemas import TraceDocument

DEFAULT_DB = Path(".tracesentry/traces.db")


def database_path() -> Path:
    return Path(os.getenv("TRACESENTRY_DB", str(DEFAULT_DB)))


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)"
        )


def save_trace(trace: TraceDocument) -> dict[str, Any]:
    initialize()
    run_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    payload = trace.model_dump(mode="json")
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO runs (run_id, trace_id, created_at, source, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, trace.trace_id, created_at, trace.source, json.dumps(payload)),
        )
    return {
        "run_id": run_id,
        "trace_id": trace.trace_id,
        "created_at": created_at,
        "span_count": len(trace.spans),
    }


def get_run(run_id: str) -> dict[str, Any] | None:
    initialize()
    with connect() as connection:
        row = connection.execute(
            "SELECT run_id, trace_id, created_at, source, payload_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "trace_id": row["trace_id"],
        "created_at": row["created_at"],
        "source": row["source"],
        "trace": json.loads(row["payload_json"]),
    }


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    initialize()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT run_id, trace_id, created_at, source, payload_json
            FROM runs ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "trace_id": row["trace_id"],
            "created_at": row["created_at"],
            "source": row["source"],
            "span_count": len(json.loads(row["payload_json"])["spans"]),
        }
        for row in rows
    ]
