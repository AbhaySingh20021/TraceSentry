# TraceSentry

TraceSentry is an open-source debugging and evaluation workbench for LLM applications and tool-using agents. It ingests execution traces, highlights likely failure points, and makes it easier to reproduce failures and compare runs.

> Status: early-stage starter. The repository currently provides a local API, trace schema, deterministic failure heuristics, sample traces, and tests. Model-based diagnosis and production integrations are planned extensions—not claimed as implemented.

## Why TraceSentry?

LLM systems can fail for reasons that are difficult to distinguish from the final answer alone: poor retrieval, tool errors, unsupported claims, latency, or prompt changes. TraceSentry gives each run a structured timeline and a reproducible analysis report.

## MVP features

- Ingest JSON traces through a FastAPI endpoint.
- Normalize spans and validate trace payloads.
- Identify common signals such as tool errors, empty retrieval, high latency, and missing evidence.
- Persist runs locally in SQLite for a zero-service setup.
- Inspect runs through a small API and replay deterministic analysis.
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

Open `http://127.0.0.1:8000/docs` for the API explorer and `http://127.0.0.1:8000/health` for a health check.\n\n## Dashboard\n\nWith the API running, open a second terminal at the repository root and run:\n\n```bash\npython -m http.server 8080\n```\n\nVisit `http://127.0.0.1:8080/dashboard/`. Click **Load demo trace** to ingest the synthetic RAG failure, select it, then click **Analyze run**. The dashboard uses the local API at `http://127.0.0.1:8000`; this is a development setup, not a production deployment.

## API sketch

- `GET /health` — service health.
- `POST /v1/traces` — ingest a trace document.
- `GET /v1/runs` — list recent runs.
- `GET /v1/runs/{run_id}` — inspect a run and its spans.
- `POST /v1/runs/{run_id}/analyze` — generate a deterministic failure report.

See [`docs/architecture.md`](docs/architecture.md) and [`examples/`](examples/) for details.

## Example trace

A trace is a JSON object with a `trace_id`, optional metadata, and a list of spans. Each span has a unique `span_id`, a name, a start time, a duration, a status, and optional attributes/events. The sample in `examples/failed_rag_trace.json` demonstrates a retrieval span returning zero documents before an agent produces an answer.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Roadmap

- [x] Trace schema and API foundation
- [x] Local persistence and deterministic failure heuristics
- [x] Example failure traces and tests
- [ ] OpenTelemetry OTLP ingestion adapter
- [ ] LangGraph callback integration
- [ ] Replay runner for stored input and tool fixtures
- [ ] Before/after evaluation comparisons
- [ ] Optional model-assisted diagnosis with evidence-linked explanations
- [ ] Web dashboard

## Design principles

1. **Evidence before explanation:** every finding should reference a span or event.
2. **Reproducibility:** store input traces and version analysis rules.
3. **Provider-neutral core:** don't require a particular LLM provider to ingest or inspect traces.
4. **Safe by default:** avoid logging secrets; treat trace attributes as potentially sensitive.

## Security and privacy

Traces may contain prompts, customer data, credentials, or retrieved documents. Do not ingest production data without appropriate authorization and redaction. This MVP is intended for local development; it is not yet hardened for multi-tenant or internet-facing deployment. Never commit `.env` files or API keys.

## License

MIT. See [`LICENSE`](LICENSE).
