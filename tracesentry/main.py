"""FastAPI application for TraceSentry's local MVP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from tracesentry import storage
from tracesentry.analyzer import analyze_trace
from tracesentry.schemas import TraceDocument, TraceIngestResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.initialize()
    yield


app = FastAPI(
    title="TraceSentry API",
    description="Local-first trace ingestion and explainable failure heuristics for LLM systems.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tracesentry-api"}


@app.post("/v1/traces", response_model=TraceIngestResponse, status_code=201, tags=["traces"])
def ingest_trace(trace: TraceDocument) -> dict[str, Any]:
    span_ids = [span.span_id for span in trace.spans]
    if len(span_ids) != len(set(span_ids)):
        raise HTTPException(status_code=422, detail="span_id values must be unique within a trace")
    return storage.save_trace(trace)


@app.get("/v1/runs", tags=["runs"])
def get_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return {"items": storage.list_runs(limit=limit), "limit": limit}


@app.get("/v1/runs/{run_id}", tags=["runs"])
def get_run(run_id: str) -> dict[str, Any]:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/v1/runs/{run_id}/analyze", tags=["analysis"])
def analyze_run(run_id: str) -> dict[str, Any]:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return analyze_trace(run)
