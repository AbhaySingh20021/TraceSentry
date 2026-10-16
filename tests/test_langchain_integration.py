from uuid import uuid4

from tracesentry.integrations.langchain import TraceSentryCallbackHandler


def test_callback_handler_captures_tool_error_and_parent():
    handler = TraceSentryCallbackHandler(trace_id="trace-test")
    parent = str(uuid4())
    child = str(uuid4())

    handler.on_chain_start({"name": "agent"}, {"question": "secret"}, run_id=parent)
    handler.on_tool_start({"name": "search"}, "private query", run_id=child, parent_run_id=parent)
    handler.on_tool_error(RuntimeError("provider unavailable"), run_id=child)
    handler.on_chain_end({"answer": "secret answer"}, run_id=parent)

    trace = handler.to_trace_document()
    assert trace["trace_id"] == "trace-test"
    assert len(trace["spans"]) == 2
    tool_span = next(span for span in trace["spans"] if span["span_id"] == child)
    assert tool_span["parent_span_id"] == parent
    assert tool_span["status"] == "error"
    assert tool_span["attributes"]["error"] == "provider unavailable"
    assert "query" not in tool_span["attributes"]
    assert trace["metadata"]["content_redacted"] is True


def test_callback_handler_counts_retrieval_results():
    handler = TraceSentryCallbackHandler()
    run_id = str(uuid4())
    handler.on_retriever_start({"name": "vector_search"}, "query", run_id=run_id)
    handler.on_retriever_end([], run_id=run_id)
    trace = handler.to_trace_document(include_content=True)
    span = trace["spans"][0]
    assert span["status"] == "ok"
    assert span["attributes"]["documents_found"] == 0
    assert span["attributes"]["result_count"] == 0


def test_callback_handler_marks_unfinished_span_incomplete():
    handler = TraceSentryCallbackHandler()
    run_id = str(uuid4())
    handler.on_chain_start({"name": "agent"}, {}, run_id=run_id)
    trace = handler.to_trace_document()
    assert trace["spans"][0]["status"] == "unset"
    assert trace["spans"][0]["attributes"]["incomplete"] is True
