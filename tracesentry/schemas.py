"""Validated API schemas for trace ingestion and analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    timestamp: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceSpan(BaseModel):
    model_config = ConfigDict(extra="allow")

    span_id: str = Field(min_length=1, max_length=200)
    parent_span_id: str | None = None
    name: str = Field(min_length=1, max_length=500)
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = Field(ge=0)
    status: Literal["ok", "error", "unset"] = "unset"
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[TraceEvent] = Field(default_factory=list)

    @field_validator("start_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class TraceDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    trace_id: str = Field(min_length=1, max_length=200)
    spans: list[TraceSpan] = Field(min_length=1, max_length=10_000)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(default="manual", max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)
    input: Any | None = None
    output: Any | None = None


class TraceIngestResponse(BaseModel):
    run_id: str
    trace_id: str
    span_count: int
    created_at: datetime


class FailureFinding(BaseModel):
    code: str
    severity: Literal["info", "warning", "high"]
    title: str
    explanation: str
    span_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    run_id: str
    trace_id: str
    analyzer_version: str
    finding_count: int
    findings: list[FailureFinding]
    total_duration_ms: float
    error_span_count: int
