"""VBStyle domain implementation: observability.

Metrics, traces, structured logs, OpenTelemetry signals, correlation.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import uuid
import random
from collections import defaultdict, deque


class DomObservability:
    """Observability domain: metrics, spans, logs, correlation, sampling, export."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "metrics": defaultdict(list),
            "spans": {},
            "active_spans": {},
            "logs": deque(maxlen=1000),
            "traces": {},
            "exporters": {},
            "correlations": {},
        }
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "record_metric": self.record_metric,
            "start_span": self.start_span,
            "end_span": self.end_span,
            "emit_log": self.emit_log,
            "correlate": self.correlate,
            "sample": self.sample,
            "export": self.export,
            "get_trace": self.get_trace,
            "register_exporter": self.register_exporter,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def record_metric(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("METRIC_NAME_REQUIRED", "name required", 0))
            value = float(params.get("value", 0))
            tags = params.get("tags") or {}
            unit = params.get("unit", "count")
            point = {"value": value, "tags": tags, "unit": unit, "timestamp": time.time()}
            self.state["metrics"][name].append(point)
            result = {
                "domain": "observability",
                "method": "record_metric",
                "data": {"name": name, "value": value, "unit": unit, "count": len(self.state["metrics"][name])},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECORD_METRIC_ERROR", str(e), 0))

    def start_span(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "span")
            trace_id = params.get("trace_id") or str(uuid.uuid4())
            parent_id = params.get("parent_id")
            span_id = str(uuid.uuid4())[:16]
            span = {
                "span_id": span_id,
                "trace_id": trace_id,
                "name": name,
                "parent_id": parent_id,
                "start": time.time(),
                "end": None,
                "attributes": params.get("attributes") or {},
                "status": "active",
            }
            self.state["spans"][span_id] = span
            self.state["active_spans"][span_id] = span
            self.state["traces"].setdefault(trace_id, []).append(span_id)
            result = {
                "domain": "observability",
                "method": "start_span",
                "data": {"span_id": span_id, "trace_id": trace_id, "name": name},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("START_SPAN_ERROR", str(e), 0))

    def end_span(self, params=None):
        params = params or {}
        try:
            span_id = params.get("span_id")
            if not span_id or span_id not in self.state["spans"]:
                return (0, None, ("SPAN_NOT_FOUND", f"Span {span_id} not found", 0))
            span = self.state["spans"][span_id]
            span["end"] = time.time()
            span["duration"] = span["end"] - span["start"]
            span["status"] = params.get("status", "ok")
            self.state["active_spans"].pop(span_id, None)
            result = {
                "domain": "observability",
                "method": "end_span",
                "data": {"span_id": span_id, "duration": span["duration"], "status": span["status"]},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("END_SPAN_ERROR", str(e), 0))

    def emit_log(self, params=None):
        params = params or {}
        try:
            level = params.get("level", "info").upper()
            message = params.get("message", "")
            trace_id = params.get("trace_id")
            span_id = params.get("span_id")
            attributes = params.get("attributes") or {}
            entry = {
                "level": level,
                "message": message,
                "trace_id": trace_id,
                "span_id": span_id,
                "attributes": attributes,
                "timestamp": time.time(),
            }
            self.state["logs"].append(entry)
            result = {
                "domain": "observability",
                "method": "emit_log",
                "data": {"level": level, "message": message, "logged": True},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EMIT_LOG_ERROR", str(e), 0))

    def correlate(self, params=None):
        params = params or {}
        try:
            trace_id = params.get("trace_id")
            if not trace_id:
                return (0, None, ("TRACE_ID_REQUIRED", "trace_id required", 0))
            span_ids = self.state["traces"].get(trace_id, [])
            related_logs = [l for l in self.state["logs"] if l.get("trace_id") == trace_id]
            related_metrics = []
            for name, points in self.state["metrics"].items():
                for p in points:
                    if p.get("tags", {}).get("trace_id") == trace_id:
                        related_metrics.append({"name": name, "value": p["value"]})
            result = {
                "domain": "observability",
                "method": "correlate",
                "data": {
                    "trace_id": trace_id,
                    "spans": len(span_ids),
                    "logs": len(related_logs),
                    "metrics": len(related_metrics),
                },
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CORRELATE_ERROR", str(e), 0))

    def sample(self, params=None):
        params = params or {}
        try:
            rate = float(params.get("rate", 1.0))
            rate = max(0.0, min(1.0, rate))
            sampled = random.random() < rate
            result = {
                "domain": "observability",
                "method": "sample",
                "data": {"sampled": sampled, "rate": rate},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SAMPLE_ERROR", str(e), 0))

    def export(self, params=None):
        params = params or {}
        try:
            exporter_name = params.get("exporter")
            if not exporter_name or exporter_name not in self.state["exporters"]:
                return (0, None, ("EXPORTER_NOT_FOUND", f"Exporter {exporter_name} not found", 0))
            data = {
                "metrics": {k: list(v) for k, v in self.state["metrics"].items()},
                "spans": self.state["spans"],
                "logs": list(self.state["logs"]),
            }
            result = {
                "domain": "observability",
                "method": "export",
                "data": {"exporter": exporter_name, "exported": True, "size": len(str(data))},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXPORT_ERROR", str(e), 0))

    def get_trace(self, params=None):
        params = params or {}
        try:
            trace_id = params.get("trace_id")
            if not trace_id:
                return (0, None, ("TRACE_ID_REQUIRED", "trace_id required", 0))
            span_ids = self.state["traces"].get(trace_id, [])
            spans = [self.state["spans"][sid] for sid in span_ids if sid in self.state["spans"]]
            result = {
                "domain": "observability",
                "method": "get_trace",
                "data": {"trace_id": trace_id, "spans": spans, "count": len(spans)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_TRACE_ERROR", str(e), 0))

    def register_exporter(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("EXPORTER_NAME_REQUIRED", "name required", 0))
            exporter_type = params.get("type", "console")
            config = params.get("config") or {}
            self.state["exporters"][name] = {"type": exporter_type, "config": config, "registered": time.time()}
            result = {
                "domain": "observability",
                "method": "register_exporter",
                "data": {"name": name, "type": exporter_type, "registered": True},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REGISTER_EXPORTER_ERROR", str(e), 0))
