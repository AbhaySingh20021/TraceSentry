"""Deterministic, explainable heuristics for common LLM trace failure signals.

These rules are intentionally conservative. They surface evidence to investigate;
they do not claim to infer causality or judge semantic correctness.
"""

from __future__ import annotations

from typing import Any

ANALYZER_VERSION = "heuristics-0.1.0"


def _attribute_text(span: dict[str, Any]) -> str:
    return " ".join(
        [
            span.get("name", ""),
            str(span.get("attributes", {})),
            str(span.get("events", [])),
        ]
    ).lower()


def analyze_trace(run: dict[str, Any]) -> dict[str, Any]:
    trace = run["trace"]
    spans = trace["spans"]
    findings: list[dict[str, Any]] = []

    for span in spans:
        span_id = span["span_id"]
        status = str(span.get("status", "unset")).lower()
        attributes = span.get("attributes") or {}
        text = _attribute_text(span)

        if status == "error":
            findings.append(
                {
                    "code": "SPAN_ERROR",
                    "severity": "high",
                    "title": f"Span failed: {span.get('name', span_id)}",
                    "explanation": "This span is explicitly marked as an error. Inspect its recorded exception or error attributes.",
                    "span_ids": [span_id],
                    "evidence": {"status": status, "attributes": attributes},
                }
            )

        if any(term in text for term in ("retriev", "vector_search", "similarity_search")):
            count = attributes.get("result_count", attributes.get("retrieval.result_count"))
            if count == 0 or attributes.get("documents_found") == 0:
                findings.append(
                    {
                        "code": "EMPTY_RETRIEVAL",
                        "severity": "high",
                        "title": "Retrieval returned no documents",
                        "explanation": "The span attributes report zero retrieved documents. A downstream answer may lack supporting context.",
                        "span_ids": [span_id],
                        "evidence": {
                            "result_count": count,
                            "documents_found": attributes.get("documents_found"),
                        },
                    }
                )

        if any(term in text for term in ("tool", "function_call")) and status == "ok":
            error_value = attributes.get("error") or attributes.get("tool.error")
            if error_value:
                findings.append(
                    {
                        "code": "TOOL_ERROR_ATTRIBUTE",
                        "severity": "warning",
                        "title": "Tool span contains an error attribute",
                        "explanation": "The span status is not marked as an error, but its attributes contain an error value. Check status mapping and tool handling.",
                        "span_ids": [span_id],
                        "evidence": {"error": error_value},
                    }
                )

        if span.get("duration_ms", 0) >= 10_000:
            findings.append(
                {
                    "code": "SLOW_SPAN",
                    "severity": "warning",
                    "title": f"Slow span: {span.get('name', span_id)}",
                    "explanation": "This span took at least 10 seconds. Compare provider latency, retries, queueing, and tool execution.",
                    "span_ids": [span_id],
                    "evidence": {"duration_ms": span["duration_ms"], "threshold_ms": 10_000},
                }
            )

    if not findings:
        findings.append(
            {
                "code": "NO_RULE_MATCH",
                "severity": "info",
                "title": "No known failure signal detected",
                "explanation": "The current heuristic rules did not match this trace. This is not proof that the answer is correct or grounded.",
                "span_ids": [],
                "evidence": {"analyzer_version": ANALYZER_VERSION},
            }
        )

    total_duration = sum(float(span.get("duration_ms", 0)) for span in spans)
    return {
        "run_id": run["run_id"],
        "trace_id": run["trace_id"],
        "analyzer_version": ANALYZER_VERSION,
        "finding_count": len(findings),
        "findings": findings,
        "total_duration_ms": round(total_duration, 3),
        "error_span_count": sum(1 for span in spans if span.get("status") == "error"),
    }
