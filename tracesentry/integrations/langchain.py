"""Optional LangChain callback adapter for capturing real agent executions.

Install the optional integration with:
    pip install -e ".[langchain]"

Pass a TraceSentryCallbackHandler instance in a LangChain/LangGraph config's
callbacks list. Export the captured trace with handler.to_trace_document().
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:  # Keep core TraceSentry usable without the optional dependency.
    BaseCallbackHandler = object  # type: ignore[assignment,misc]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_value(value: Any, limit: int = 2_000) -> Any:
    """Convert callback values into JSON-safe, bounded data."""
    try:
        encoded = json.dumps(value, default=str, ensure_ascii=False)
        if len(encoded) > limit:
            return encoded[:limit] + "…[truncated]"
        return json.loads(encoded)
    except (TypeError, ValueError, RecursionError):
        return str(value)[:limit]


class TraceSentryCallbackHandler(BaseCallbackHandler):
    """Capture LangChain callback events into a TraceSentry-compatible trace.

    A handler instance captures one logical run. Create a fresh instance for each
    request so traces do not accidentally combine unrelated user executions.
    """

    def __init__(
        self,
        *,
        trace_id: str | None = None,
        source: str = "langchain",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.trace_id = trace_id or str(uuid4())
        self.source = source
        self.metadata = dict(metadata or {})
        self._spans: list[dict[str, Any]] = []
        self._active: dict[str, dict[str, Any]] = {}
        self._started: dict[str, float] = {}
        self._parents: dict[str, str | None] = {}
        self._seen: set[str] = set()

    def _start(
        self,
        run_id: Any,
        parent_run_id: Any,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        span_id = str(run_id or uuid4())
        if span_id in self._seen:
            return
        self._seen.add(span_id)
        parent_id = str(parent_run_id) if parent_run_id is not None else None
        span = {
            "span_id": span_id,
            "parent_span_id": parent_id,
            "name": name[:500],
            "start_time": _utc_now(),
            "duration_ms": 0.0,
            "status": "unset",
            "attributes": _safe_value(attributes or {}),
            "events": [],
        }
        self._active[span_id] = span
        self._started[span_id] = time.perf_counter()
        self._parents[span_id] = parent_id
        self._spans.append(span)

    def _event(self, run_id: Any, name: str, attributes: dict[str, Any] | None = None) -> None:
        span = self._active.get(str(run_id))
        if span is not None:
            span["events"].append(
                {"name": name, "timestamp": _utc_now(), "attributes": _safe_value(attributes or {})}
            )

    def _finish(
        self,
        run_id: Any,
        *,
        error: Any = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        span_id = str(run_id)
        span = self._active.get(span_id)
        if span is None:
            return
        span["duration_ms"] = round(
            max(0.0, time.perf_counter() - self._started.get(span_id, time.perf_counter())) * 1000,
            3,
        )
        span["status"] = "error" if error is not None else "ok"
        if attributes:
            span["attributes"].update(_safe_value(attributes))
        if error is not None:
            message = str(error)[:2_000]
            span["attributes"]["error"] = message
            span["events"].append(
                {
                    "name": "exception",
                    "timestamp": _utc_now(),
                    "attributes": {"message": message, "exception_type": type(error).__name__},
                }
            )
        self._active.pop(span_id, None)
        self._started.pop(span_id, None)

    def _capture(
        self,
        kind: str,
        serialized: dict[str, Any] | None,
        run_id: Any,
        parent_run_id: Any = None,
        **attributes: Any,
    ) -> None:
        name = (serialized or {}).get("name") or (serialized or {}).get("id", [kind])[-1]
        self._start(run_id, parent_run_id, f"{kind}.{name}", attributes)

    def on_chain_start(
        self, serialized: dict[str, Any], inputs: dict[str, Any], *, run_id: Any,
        parent_run_id: Any = None, **kwargs: Any,
    ) -> None:
        self._capture("chain", serialized, run_id, parent_run_id, inputs=_safe_value(inputs))

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, attributes={"outputs": _safe_value(outputs)})

    def on_chain_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], *, run_id: Any,
        parent_run_id: Any = None, **kwargs: Any,
    ) -> None:
        self._capture(
            "llm", serialized, run_id, parent_run_id,
            prompt_count=len(prompts),
            prompts=[str(prompt)[:2_000] for prompt in prompts[:10]],
        )

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: Any,
        parent_run_id: Any = None, **kwargs: Any,
    ) -> None:
        self._capture(
            "llm", serialized, run_id, parent_run_id,
            message_count=sum(len(group) for group in messages),
            messages=_safe_value(messages, limit=4_000),
        )

    def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
        llm_output = getattr(response, "llm_output", None)
        self._finish(run_id, attributes={"llm_output": _safe_value(llm_output or {})})

    def on_llm_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, *, run_id: Any,
        parent_run_id: Any = None, **kwargs: Any,
    ) -> None:
        self._capture(
            "tool", serialized, run_id, parent_run_id, input=str(input_str)[:2_000]
        )

    def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, attributes={"output": _safe_value(output)})

    def on_tool_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    def on_retriever_start(
        self, serialized: dict[str, Any], query: str, *, run_id: Any,
        parent_run_id: Any = None, **kwargs: Any,
    ) -> None:
        self._capture(
            "retriever", serialized, run_id, parent_run_id, query=str(query)[:2_000]
        )

    def on_retriever_end(self, documents: list[Any], *, run_id: Any, **kwargs: Any) -> None:
        self._finish(
            run_id,
            attributes={
                "documents_found": len(documents),
                "result_count": len(documents),
                "document_previews": [
                    {
                        "page_content": str(getattr(doc, "page_content", ""))[:500],
                        "metadata": _safe_value(getattr(doc, "metadata", {}), limit=500),
                    }
                    for doc in documents[:5]
                ],
            },
        )

    def on_retriever_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        self._finish(run_id, error=error)

    def to_trace_document(
        self,
        *,
        input: Any = None,
        output: Any = None,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """Return a TraceSentry ingestion payload; close unfinished spans as errors.

        Content capture is opt-in because prompts, documents, and outputs may
        contain sensitive data. Set include_content=True only when appropriate.
        """
        now = time.perf_counter()
        for span_id, span in list(self._active.items()):
            span["duration_ms"] = round(
                max(0.0, now - self._started.get(span_id, now)) * 1000, 3
            )
            span["status"] = "unset"
            span["attributes"]["incomplete"] = True

        spans = []
        for original in self._spans:
            span = dict(original)
            span["attributes"] = dict(span["attributes"])
            if not include_content:
                for key in ("inputs", "outputs", "prompts", "messages", "query", "input", "output"):
                    span["attributes"].pop(key, None)
                span["attributes"]["content_redacted"] = True
            spans.append(span)

        if not spans:
            spans = [
                {
                    "span_id": str(uuid4()),
                    "parent_span_id": None,
                    "name": "trace.empty",
                    "start_time": _utc_now(),
                    "duration_ms": 0,
                    "status": "unset",
                    "attributes": {"message": "No callback events were captured"},
                    "events": [],
                }
            ]

        document: dict[str, Any] = {
            "trace_id": self.trace_id,
            "source": self.source,
            "metadata": self.metadata,
            "spans": spans,
        }
        if include_content:
            if input is not None:
                document["input"] = _safe_value(input)
            if output is not None:
                document["output"] = _safe_value(output)
        else:
            document["metadata"]["content_redacted"] = True
        return document
