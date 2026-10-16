const API_BASE = window.TRACESENTRY_API_URL || "http://127.0.0.1:8000";
const state = { runs: [], selectedRunId: null, selectedRun: null, report: null };

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[char]));
const shortId = (value) => String(value || "").length > 18 ? String(value).slice(0, 8) + "…" + String(value).slice(-5) : String(value || "");
const formatDate = (value) => {
  if (!value) return "Unknown time";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const formatDuration = (ms) => {
  if (ms === undefined || ms === null || Number.isNaN(Number(ms))) return "—";
  const value = Number(ms);
  return value >= 1000 ? (value / 1000).toFixed(value >= 10000 ? 1 : 2) + " s" : Math.round(value) + " ms";
};
const setAlert = (message) => {
  $("alert").textContent = message || "";
  $("alert").classList.toggle("hidden", !message);
};
async function api(path, options = {}) {
  const response = await fetch(API_BASE + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || "Request failed (" + response.status + ")");
  return body;
}
function updateConnection(online) {
  $("connection-label").textContent = online ? "API connected" : "API unavailable";
  $("connection-dot").parentElement.classList.toggle("offline", !online);
}
function renderRuns() {
  $("run-count").textContent = state.runs.length;
  $("stat-runs").textContent = state.runs.length;
  if (!state.runs.length) {
    $("run-list").innerHTML = '<div class="empty-state">No runs yet.<br>Load the demo trace to see TraceSentry in action.</div>';
    return;
  }
  $("run-list").innerHTML = state.runs.map((run) => {
    const selected = run.run_id === state.selectedRunId;
    const trace = run.trace_id || run.run_id;
    return '<button type="button" class="run-item ' + (selected ? "selected" : "") + '" data-run-id="' + escapeHtml(run.run_id) + '">' +
      '<div class="run-top"><span class="run-name">' + escapeHtml(trace) + '</span><span class="run-time">' + escapeHtml(formatDate(run.created_at)) + '</span></div>' +
      '<div class="run-meta"><span class="tiny-dot"></span><span>' + escapeHtml(run.span_count ?? "—") + ' spans</span><span>·</span><span class="run-id">' + escapeHtml(shortId(run.run_id)) + '</span></div>' +
      '</button>';
  }).join("");
  $("run-list").querySelectorAll("[data-run-id]").forEach((button) => button.addEventListener("click", () => selectRun(button.dataset.runId)));
}
function renderTimeline(trace) {
  const spans = trace?.spans || [];
  $("span-count-label").textContent = spans.length + (spans.length === 1 ? " span" : " spans");
  $("stat-spans").textContent = spans.length;
  $("stat-duration").textContent = formatDuration(spans.reduce((sum, span) => sum + Number(span.duration_ms || 0), 0));
  if (!spans.length) {
    $("timeline").innerHTML = '<div class="empty-state">No spans were included in this trace.</div>';
    return;
  }
  const ids = new Set(spans.map((span) => span.span_id));
  const depthOf = (span) => {
    let depth = 0, parent = span.parent_span_id, seen = new Set([span.span_id]);
    while (parent && ids.has(parent) && !seen.has(parent) && depth < 8) {
      seen.add(parent); depth++;
      parent = spans.find((item) => item.span_id === parent)?.parent_span_id;
    }
    return depth;
  };
  const ordered = [...spans].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  $("timeline").innerHTML = ordered.map((span) => {
    const error = span.status === "error";
    const statusClass = error ? "pill-error" : span.status === "ok" ? "pill-ok" : "pill-unset";
    const statusLabel = String(span.status || "unset").toUpperCase();
    const depth = depthOf(span);
    const attrs = span.attributes || {};
    return '<div class="span-row ' + (error ? "error" : "") + '">' +
      '<div class="span-rail"><span class="rail-dot"></span><span class="rail-line"></span></div>' +
      '<div class="span-card" style="margin-left:' + (depth * 13) + 'px">' +
      '<div class="span-card-top"><span class="span-name">' + escapeHtml(span.name) + '</span><span class="duration">' + escapeHtml(formatDuration(span.duration_ms)) + '</span></div>' +
      '<div class="span-id">' + escapeHtml(span.span_id) + (span.parent_span_id ? ' · parent ' + escapeHtml(shortId(span.parent_span_id)) : '') + '</div>' +
      '<div class="span-foot"><span class="pill ' + statusClass + '">' + escapeHtml(statusLabel) + '</span>' +
      (attrs.model ? '<span class="pill pill-unset">' + escapeHtml(attrs.model) + '</span>' : '') +
      (attrs.result_count === 0 || attrs.documents_found === 0 ? '<span class="pill pill-warn">0 documents</span>' : '') +
      '</div></div></div>';
  }).join("");
}
function renderFindings(report) {
  if (!report) {
    $("stat-findings").textContent = "—";
    $("stat-findings-foot").textContent = "Run analysis to inspect signals";
    $("analyzer-label").textContent = "Evidence-linked heuristics";
    $("findings").innerHTML = '<div class="empty-state">Analyze a run to surface potential failure signals.</div>';
    return;
  }
  $("stat-findings").textContent = report.finding_count;
  $("stat-findings-foot").textContent = report.error_span_count + " error spans";
  $("analyzer-label").textContent = report.analyzer_version || "Analysis complete";
  $("findings").innerHTML = (report.findings || []).map((finding) => {
    const severity = finding.severity || "info";
    const evidence = JSON.stringify(finding.evidence || {}, null, 2);
    return '<article class="finding-card"><div class="finding-top"><span class="severity severity-' + escapeHtml(severity) + '">' + escapeHtml(severity.toUpperCase()) + '</span><span class="finding-title">' + escapeHtml(finding.title) + '</span></div>' +
      '<div class="finding-description">' + escapeHtml(finding.explanation) + '</div>' +
      '<div class="finding-evidence">' + escapeHtml(finding.code) + ' · spans: ' + escapeHtml((finding.span_ids || []).join(", ") || "none") + '<br>' + escapeHtml(evidence) + '</div></article>';
  }).join("");
}
function renderSelected() {
  const run = state.selectedRun;
  if (!run) {
    $("detail-title").textContent = "Select a trace";
    $("detail-subtitle").textContent = "Choose a run from the list or load the demo trace.";
    $("analyze-button").disabled = true;
    $("raw-json").textContent = "Select a run to inspect its payload.";
    $("stat-spans").textContent = "—";
    $("stat-duration").textContent = "—";
    renderTimeline(null); renderFindings(null);
    return;
  }
  const trace = run.trace || {};
  $("detail-title").textContent = trace.trace_id || run.trace_id || "Trace run";
  $("detail-subtitle").textContent = "Run " + run.run_id + " · source: " + (run.source || trace.source || "manual");
  $("analyze-button").disabled = false;
  $("raw-json").textContent = JSON.stringify(trace, null, 2);
  renderTimeline(trace);
  renderFindings(state.report);
}
async function loadRuns(preferredId) {
  const data = await api("/v1/runs?limit=100");
  state.runs = data.items || [];
  updateConnection(true);
  renderRuns();
  $("stat-runs").textContent = state.runs.length;
  const target = preferredId || state.selectedRunId;
  if (target && state.runs.some((run) => run.run_id === target)) await selectRun(target);
  else if (state.runs.length) await selectRun(state.runs[0].run_id);
  else { state.selectedRun = null; state.selectedRunId = null; state.report = null; renderSelected(); }
}
async function selectRun(runId) {
  try {
    const run = await api("/v1/runs/" + encodeURIComponent(runId));
    state.selectedRunId = runId;
    state.selectedRun = run;
    state.report = null;
    renderRuns(); renderSelected(); setAlert("");
  } catch (error) { setAlert(error.message); }
}
async function loadDemo() {
  $("demo-button").disabled = true;
  try {
    const response = await fetch("/examples/failed_rag_trace.json");
    if (!response.ok) throw new Error("Could not load example trace. Start the static server from the repository root.");
    const trace = await response.json();
    const created = await api("/v1/traces", { method: "POST", body: JSON.stringify(trace) });
    await loadRuns(created.run_id);
    setAlert("");
  } catch (error) { setAlert(error.message + " Check that the API is running and dashboard origin is allowed."); }
  finally { $("demo-button").disabled = false; }
}
async function analyzeSelected() {
  if (!state.selectedRunId) return;
  $("analyze-button").disabled = true;
  $("analyze-button").textContent = "Analyzing…";
  try {
    state.report = await api("/v1/runs/" + encodeURIComponent(state.selectedRunId) + "/analyze", { method: "POST" });
    renderSelected(); setAlert("");
  } catch (error) { setAlert(error.message); }
  finally { $("analyze-button").disabled = false; $("analyze-button").textContent = "Analyze run"; }
}
$("refresh-button").addEventListener("click", () => loadRuns().catch((error) => { updateConnection(false); setAlert(error.message); }));
$("demo-button").addEventListener("click", loadDemo);
$("analyze-button").addEventListener("click", analyzeSelected);

loadRuns().catch((error) => {
  updateConnection(false);
  setAlert("Could not connect to " + API_BASE + ". Start the API with uvicorn tracesentry.main:app --reload. " + error.message);
  $("run-list").innerHTML = '<div class="empty-state">API unavailable.<br>Start the FastAPI server, then refresh.</div>';
  $("stat-runs").textContent = "—";
});
