# TraceSentry Dashboard

A dependency-free static dashboard for inspecting trace runs through the TraceSentry API.

## Start locally

Terminal 1 — from the repository root:

```bash
pip install -e ".[dev]"
uvicorn tracesentry.main:app --reload
```

Terminal 2 — also from the repository root:

```bash
python -m http.server 8080
```

Open <http://127.0.0.1:8080/dashboard/>.

1. Click **Load demo trace** to submit the synthetic empty-retrieval trace.
2. Select a run from the left-hand list.
3. Click **Analyze run** to see the heuristic findings and evidence.
4. Inspect the normalized trace payload at the bottom.

The API allows local development origins on ports 8080 and 5500. If you change the dashboard origin, update the explicit CORS allowlist in `tracesentry/main.py`. Do not use this development configuration as a substitute for production authentication, access control, and deployment hardening.

The API URL defaults to `http://127.0.0.1:8000`. For a custom local URL, set `window.TRACESENTRY_API_URL` before loading `app.js`.

## Scope

The dashboard is intentionally a first UI slice: recent runs, a time-ordered span view, rule-based findings, and raw JSON. It does not yet offer live OTLP ingestion, model-based diagnosis, trace replay, or a production security model.
