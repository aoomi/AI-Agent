"""Production lifecycle wiring for the dependency-free observability exporters."""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from uuid import uuid4

from ai_agent_events import CompositeExporter, JsonLinesExporter, MetricsRegistry, PrometheusSnapshotExporter, StructuredLogger


class RuntimeObservability:
    """Persist bounded-cardinality API telemetry without affecting request results."""

    def __init__(self, root: str | Path, *, clock=time.monotonic):
        root = Path(root)
        exporter = CompositeExporter((
            JsonLinesExporter(root / "records.jsonl"),
            PrometheusSnapshotExporter(root / "metrics.prom"),
        ))
        self.metrics = MetricsRegistry(exporter)
        self.logger = StructuredLogger(io.StringIO(), exporter)
        self.clock = clock
        self._lock = threading.RLock()
        self._active = 0

    @staticmethod
    def correlation_id(value: str | None, prefix: str) -> str:
        value = str(value or "").strip()
        if value and len(value) <= 128 and all(character.isalnum() or character in "-_.:" for character in value):
            return value
        return f"{prefix}-{uuid4().hex}"

    def begin_request(self, request_id: str | None, trace_id: str | None) -> tuple[float, str, str]:
        request_id = self.correlation_id(request_id, "req")
        trace_id = self.correlation_id(trace_id, "trace")
        with self._lock:
            self._active += 1
            self.metrics.gauge("short_drama_http_active_requests", self._active)
        return self.clock(), request_id, trace_id

    def finish_request(self, started: float, request_id: str, trace_id: str, method: str, status: int) -> None:
        duration_ms = max(0.0, (self.clock() - started) * 1000.0)
        status_class = f"{max(0, int(status)) // 100}xx"
        labels = (("method", str(method).upper()), ("status_class", status_class))
        with self._lock:
            self._active = max(0, self._active - 1)
            self.metrics.gauge("short_drama_http_active_requests", self._active)
            self.metrics.increment("short_drama_http_requests_total", labels=labels)
            self.metrics.increment("short_drama_http_duration_ms_total", duration_ms, labels=labels)
            self.logger.emit("info", "http.request.completed", {
                "request_id": request_id,
                "trace_id": trace_id,
                "method": str(method).upper(),
                "status": int(status),
                "duration_ms": round(duration_ms, 3),
            })
            self.metrics.export_snapshot()

    def service_event(self, event: str) -> None:
        with self._lock:
            self.logger.emit("info", event, {})
            self.metrics.export_snapshot()
