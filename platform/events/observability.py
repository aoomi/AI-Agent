"""Small, dependency-free observability primitives with pluggable exporters."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterable, Mapping, Protocol, TextIO
import json
import math
import os
import re
import tempfile
import time


class ObservabilityError(ValueError):
    pass


_SECRET_WORDS = (
    "secret", "token", "password", "api_key", "authorization", "credential",
    "prompt", "phone", "mobile", "wechat", "payment_account", "paid_account",
)
_SECRET_VALUE = re.compile(
    r"(?i)(?:^|\s)(?:bearer|basic)\s+[a-z0-9._~+/=-]{8,}|"
    r"\b(?:sk|ghp|github_pat)_[a-z0-9_-]{12,}\b|"
    r"(?<!\d)1[3-9]\d{9}(?!\d)"
)
_METRIC_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_METRIC_LABEL_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            any(word in str(key).lower() for word in _SECRET_WORDS)
            or _contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], str):
            if any(word in value[0].lower() for word in _SECRET_WORDS):
                return True
        return any(_contains_secret(item) for item in value)
    if isinstance(value, str):
        return bool(_SECRET_VALUE.search(value))
    return False


def _correlation_fields(fields: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("request_id", "trace_id"):
        value = fields.get(key)
        if value is not None and str(value).strip():
            result[key] = str(value)
    return result


def _validate_metric_value(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ObservabilityError("metric value must be a finite number")


class RecordExporter(Protocol):
    """Extension point for logs, spans, snapshots and alerts."""

    def export(self, kind: str, record: Mapping[str, Any]) -> None: ...


class NullExporter:
    def export(self, kind: str, record: Mapping[str, Any]) -> None:
        return None


class CompositeExporter:
    def __init__(self, exporters: Iterable[RecordExporter]):
        self.exporters = tuple(exporters)

    def export(self, kind: str, record: Mapping[str, Any]) -> None:
        for exporter in self.exporters:
            exporter.export(kind, record)


class JsonLinesExporter:
    """Append-only durable exporter; each write is flushed under a process lock."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()

    def export(self, kind: str, record: Mapping[str, Any]) -> None:
        payload = {"kind": kind, **dict(record)}
        if _contains_secret(payload):
            raise ObservabilityError("export record contains secrets")
        if kind == "metrics_snapshot":
            _validate_metrics_snapshot(record)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as sink:
                sink.write(line + "\n")
                sink.flush()
                os.fsync(sink.fileno())


class PrometheusSnapshotExporter:
    """Atomically publish the latest registry snapshot for textfile scraping."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()

    @staticmethod
    def _labels(labels: Iterable[tuple[str, str]]) -> str:
        values = []
        for key, value in labels:
            escaped = str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
            values.append(f'{key}="{escaped}"')
        return "{" + ",".join(values) + "}" if values else ""

    def export(self, kind: str, record: Mapping[str, Any]) -> None:
        if kind != "metrics_snapshot":
            return
        if _contains_secret(record):
            raise ObservabilityError("export record contains secrets")
        _validate_metrics_snapshot(record)
        lines = []
        for metric_type in ("counters", "gauges"):
            for item in record.get(metric_type, []):
                labels = _normalise_labels(item.get("labels", ()))
                value = item.get("value")
                lines.append(f'{item["name"]}{self._labels(labels)} {value}')
        content = "\n".join(lines) + ("\n" if lines else "")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as sink:
                    sink.write(content)
                    sink.flush()
                    os.fsync(sink.fileno())
                os.replace(temporary, self.path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise


class StructuredLogger:
    def __init__(self, sink: TextIO, exporter: RecordExporter | None = None):
        self.sink = sink
        self.exporter = exporter or NullExporter()
        self._lock = RLock()

    def emit(self, level: str, event: str, fields: Mapping[str, Any]):
        if _contains_secret(fields):
            raise ObservabilityError("log fields contain secrets")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            **dict(fields),
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.sink.write(line + "\n")
            self.exporter.export("log", record)
        return record


def _normalise_labels(labels: Iterable[tuple[str, Any]]) -> tuple[tuple[str, str], ...]:
    if isinstance(labels, (str, bytes, Mapping)):
        raise ObservabilityError("metric labels must be key-value pairs")
    try:
        pairs = tuple(labels)
        if any(not isinstance(item, (list, tuple)) or len(item) != 2 for item in pairs):
            raise ObservabilityError("metric labels must be key-value pairs")
        normalised = tuple(sorted((str(item[0]), str(item[1])) for item in pairs))
    except TypeError as error:
        raise ObservabilityError("metric labels must be key-value pairs") from error
    if len({key for key, _ in normalised}) != len(normalised):
        raise ObservabilityError("metric labels contain duplicate keys")
    if any(not _METRIC_LABEL_NAME.fullmatch(key) for key, _ in normalised):
        raise ObservabilityError("metric labels contain invalid keys")
    if _contains_secret(normalised):
        raise ObservabilityError("metric labels contain secrets")
    return normalised


def _validate_metrics_snapshot(record: Mapping[str, Any]) -> None:
    for metric_type in ("counters", "gauges"):
        items = record.get(metric_type, [])
        if not isinstance(items, (list, tuple)):
            raise ObservabilityError("metrics snapshot contains an invalid metric collection")
        for item in items:
            if not isinstance(item, Mapping) or not _METRIC_NAME.fullmatch(str(item.get("name") or "")):
                raise ObservabilityError("metrics snapshot contains an invalid metric")
            _normalise_labels(item.get("labels", ()))
            _validate_metric_value(item.get("value"))


class MetricsRegistry:
    def __init__(self, exporter: RecordExporter | None = None):
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.exporter = exporter or NullExporter()
        self._lock = RLock()

    def _key(self, name: str, labels: Iterable[tuple[str, Any]]):
        if not _METRIC_NAME.fullmatch(name):
            raise ObservabilityError(f"invalid metric name: {name}")
        return name, _normalise_labels(labels)

    def increment(self, name: str, value: float = 1, labels=()):
        _validate_metric_value(value)
        if value < 0:
            raise ObservabilityError("counter increment must not be negative")
        key = self._key(name, labels)
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + value

    def gauge(self, name: str, value: float = 0, labels=()):
        _validate_metric_value(value)
        key = self._key(name, labels)
        with self._lock:
            self.gauges[key] = value

    def snapshot(self):
        """Return the legacy in-memory shape without leaking mutable registry state."""
        with self._lock:
            return {"counters": dict(self.counters), "gauges": dict(self.gauges)}

    def structured_snapshot(self, *, request_id: str | None = None, trace_id: str | None = None):
        with self._lock:
            result: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "counters": [
                    {"name": name, "labels": list(labels), "value": value}
                    for (name, labels), value in sorted(self.counters.items())
                ],
                "gauges": [
                    {"name": name, "labels": list(labels), "value": value}
                    for (name, labels), value in sorted(self.gauges.items())
                ],
            }
        result.update(_correlation_fields({"request_id": request_id, "trace_id": trace_id}))
        if _contains_secret(result):
            raise ObservabilityError("metrics snapshot contains secrets")
        return result

    def export_snapshot(self, *, request_id: str | None = None, trace_id: str | None = None):
        snapshot = self.structured_snapshot(request_id=request_id, trace_id=trace_id)
        self.exporter.export("metrics_snapshot", snapshot)
        return snapshot


@dataclass(frozen=True, slots=True)
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    duration_ms: int
    status: str
    request_id: str | None = None
    attributes: Mapping[str, Any] | None = None


class TraceRecorder:
    def __init__(self, clock=time.monotonic, exporter: RecordExporter | None = None):
        self.clock = clock
        self.exporter = exporter or NullExporter()
        self.spans: list[TraceSpan] = []
        self._lock = RLock()

    @contextmanager
    def span(self, trace_id: str, span_id: str, name: str, *, request_id: str | None = None, attributes=None):
        if not trace_id or not span_id:
            raise ObservabilityError("trace_id and span_id are required")
        attributes = dict(attributes or {})
        if _contains_secret(attributes):
            raise ObservabilityError("span attributes contain secrets")
        start = self.clock()
        status = "ok"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            span = TraceSpan(trace_id, span_id, name, int((self.clock() - start) * 1000), status, request_id, attributes)
            with self._lock:
                self.spans.append(span)
                self.exporter.export("span", asdict(span))


@dataclass(frozen=True, slots=True)
class AlertRule:
    name: str
    metric: str
    threshold: float
    comparison: str = "gte"
    labels: tuple[tuple[str, str], ...] = ()


class AlertEvaluator:
    """Deterministic rule evaluator; delivery remains a replaceable exporter."""

    def __init__(self, rules: Iterable[AlertRule], exporter: RecordExporter | None = None):
        self.rules = tuple(rules)
        self.exporter = exporter or NullExporter()

    def evaluate(self, snapshot: Mapping[str, Any], *, request_id: str | None = None, trace_id: str | None = None):
        values = {
            (item["name"], tuple(tuple(label) for label in item.get("labels", []))): item["value"]
            for group in ("counters", "gauges")
            for item in snapshot.get(group, [])
        }
        alerts = []
        comparisons: dict[str, Callable[[float, float], bool]] = {
            "gte": lambda value, threshold: value >= threshold,
            "gt": lambda value, threshold: value > threshold,
            "lte": lambda value, threshold: value <= threshold,
            "lt": lambda value, threshold: value < threshold,
        }
        for rule in self.rules:
            if rule.comparison not in comparisons:
                raise ObservabilityError(f"unsupported alert comparison: {rule.comparison}")
            labels = _normalise_labels(rule.labels)
            value = values.get((rule.metric, labels))
            if value is None or not comparisons[rule.comparison](value, rule.threshold):
                continue
            alert = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "alert": rule.name,
                "metric": rule.metric,
                "labels": list(labels),
                "value": value,
                "threshold": rule.threshold,
                "comparison": rule.comparison,
                **_correlation_fields({"request_id": request_id, "trace_id": trace_id}),
            }
            self.exporter.export("alert", alert)
            alerts.append(alert)
        return alerts
