import json
from pathlib import Path

from plugins.builtin.short_drama.backend.runtime_observability import RuntimeObservability


def test_runtime_observability_persists_correlated_records_and_bounded_metrics(tmp_path: Path):
    ticks = iter((10.0, 10.025))
    runtime = RuntimeObservability(tmp_path, clock=lambda: next(ticks))
    started, request_id, trace_id = runtime.begin_request("request-1", "trace-1")
    runtime.finish_request(started, request_id, trace_id, "get", 200)

    rows = [json.loads(line) for line in (tmp_path / "records.jsonl").read_text().splitlines()]
    completed = next(row for row in rows if row.get("event") == "http.request.completed")
    assert completed["request_id"] == "request-1"
    assert completed["trace_id"] == "trace-1"
    assert completed["duration_ms"] == 25.0
    metrics = (tmp_path / "metrics.prom").read_text()
    assert 'short_drama_http_requests_total{method="GET",status_class="2xx"} 1' in metrics
    assert "request-1" not in metrics and "trace-1" not in metrics
    assert "short_drama_http_active_requests 0" in metrics


def test_runtime_observability_generates_correlation_and_lifecycle_records(tmp_path: Path):
    ticks = iter((1.0, 1.0))
    runtime = RuntimeObservability(tmp_path, clock=lambda: next(ticks))
    started, request_id, trace_id = runtime.begin_request(None, None)
    assert request_id.startswith("req-") and trace_id.startswith("trace-")
    runtime.finish_request(started, request_id, trace_id, "post", 503)
    runtime.service_event("service.stopped")
    records = (tmp_path / "records.jsonl").read_text()
    assert '"event":"service.stopped"' in records
    assert 'status_class="5xx"' in (tmp_path / "metrics.prom").read_text()
    assert runtime.correlation_id("safe-id:1", "req") == "safe-id:1"
    assert runtime.correlation_id("token\nforged", "req").startswith("req-")
    assert runtime.correlation_id("x" * 129, "trace").startswith("trace-")
