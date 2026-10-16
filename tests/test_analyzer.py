from tracesentry.analyzer import analyze_trace


def make_run(spans):
    return {
        "run_id": "run-test",
        "trace_id": "trace-test",
        "trace": {"spans": spans},
    }


def test_empty_retrieval_and_slow_span_are_reported():
    report = analyze_trace(
        make_run(
            [
                {
                    "span_id": "retrieve-1",
                    "name": "retriever.search",
                    "duration_ms": 10_500,
                    "status": "ok",
                    "attributes": {"result_count": 0},
                }
            ]
        )
    )
    codes = {finding["code"] for finding in report["findings"]}
    assert "EMPTY_RETRIEVAL" in codes
    assert "SLOW_SPAN" in codes
    assert report["total_duration_ms"] == 10_500


def test_error_span_is_evidence_linked():
    report = analyze_trace(
        make_run(
            [
                {
                    "span_id": "tool-1",
                    "name": "browser.search",
                    "duration_ms": 40,
                    "status": "error",
                    "attributes": {"exception.type": "TimeoutError"},
                }
            ]
        )
    )
    finding = next(item for item in report["findings"] if item["code"] == "SPAN_ERROR")
    assert finding["span_ids"] == ["tool-1"]
    assert finding["evidence"]["status"] == "error"
    assert report["error_span_count"] == 1


def test_no_rule_match_does_not_claim_correctness():
    report = analyze_trace(
        make_run(
            [
                {
                    "span_id": "custom-1",
                    "name": "custom.operation",
                    "duration_ms": 20,
                    "status": "ok",
                    "attributes": {},
                }
            ]
        )
    )
    assert report["findings"][0]["code"] == "NO_RULE_MATCH"
    assert "not proof" in report["findings"][0]["explanation"]
