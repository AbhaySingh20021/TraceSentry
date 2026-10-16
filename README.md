# TraceSentry

TraceSentry is an open-source debugging and evaluation workbench for LLM applications and tool-using agents. It ingests execution traces, highlights likely failure points, and makes it easier to reproduce failures and compare runs.

> Status: early-stage starter. The repository provides a local API, trace schema, deterministic failure heuristics, a dashboard, and an optional LangChain callback adapter. OTLP ingestion, model-based diagnosis, replay, and production integrations are future work.

## Why TraceSentry?

LLM systems can fail for reasons that are difficult to distinguish from the final answer alone: poor retrieval, tool errors, unsupported claims, latency, or prompt changes. TraceSentry gives each run a structured timeline and a reproducible analysis report.

## Features

- Ingest JSON traces through FastAPI and persist runs locally in SQLite.
- Inspect runs through a static dashboard and API.
- Detect common signals such as tool errors, empty retrieval, and high latency.
- Capture LangChain chain, LLM, tool, and retriever callbacks with the optional integration.
- Redact prompt/query/input/output content by default in exported traces.
- Run tests and lint checks in CI.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
uvicorn tracesentry.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API explorer.

## Dashboard

With the API running, open a second terminal at the repository root:

```bash
python -m http.server 8080
```

Visit `http://127.0.0.1:8080/dashboard/`. Load the synthetic failed-RAG example, select the run, then click **Analyze run**.

## Capture a real LangChain/LangGraph execution

Install the optional integration:

```bash
pip install -e ".[langchain]"
```

Example for a LangChain runnable or LangGraph compiled graph:

```python
import requests
from tracesentry.integrations.langchain import TraceSentryCallbackHandler

handler = TraceSentryCallbackHandler(
    metadata={"environment": "local", "feature": "support-agent"}
)

# Use your existing runnable or compiled LangGraph graph:
result = graph.invoke(
    {"messages": [{"role": "user", "content": "Where is my order?"}]},
    config={"callbacks": [handler]},
)

# Content is redacted by default in the exported trace.
trace = handler.to_trace_document()
response = requests.post("http://127.0.0.1:8000/v1/traces", json=trace, timeout=10)
response.raise_for_status()
print(response.json())
```

The example assumes `graph` is your existing LangChain runnable or compiled LangGraph graph and `requests` is installed in your application. Use a fresh handler per request. Callback coverage depends on the components and execution path used.

### Content and privacy

The adapter records timing, names, status, error messages, retrieval counts, and limited metadata. Prompt, message, query, input, and output content is redacted in `to_trace_document()` by default. Call `to_trace_document(include_content=True)` only if your data-handling policy permits it. Error messages and tool metadata may still contain sensitive information; review them before sharing traces.

## API

- `GET /health` — service health.
- `POST /v1/traces` — ingest a trace document.
- `GET /v1/runs` — list recent runs.
- `GET /v1/runs/{run_id}` — inspect a run.
- `POST /v1/runs/{run_id}/analyze` — generate a deterministic failure report.

See [architecture notes](docs/architecture.md) and [dashboard setup](dashboard/README.md).

## Current limitations

The callback adapter is a first integration slice, not a complete OpenTelemetry implementation. It does not yet capture token/cost metrics consistently across providers, stream events, or provide replay. Trace payloads should be reviewed for sensitive information before ingestion into shared environments.
