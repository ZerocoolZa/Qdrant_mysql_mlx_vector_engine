"""VBStyle domain implementation: ingest.

Data ingestion pipeline: classify, dedupe, enrich, load, transform, store.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import hashlib
import time
import json
from collections import OrderedDict


class DomIngest:
    """Ingest domain: data ingestion, transformation, dedup, scheduling."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "classify": self.classify,
            "dedupe": self.dedupe,
            "enrich": self.enrich,
            "load": self.load,
            "report": self.report,
            "schedule": self.schedule,
            "store": self.store,
            "transform": self.transform,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def classify(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            rules = params.get("rules") or {}
            classified = []
            for r in records:
                label = "default"
                content = json.dumps(r, sort_keys=True, default=str) if isinstance(r, (dict, list)) else str(r)
                for key, pattern in rules.items():
                    if isinstance(pattern, str) and pattern in content:
                        label = key
                        break
                classified.append({"record": r, "label": label})
            counts = {}
            for c in classified:
                counts[c["label"]] = counts.get(c["label"], 0) + 1
            result = {"domain": "ingest", "method": "classify", "data": {"classified": classified, "counts": counts}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def dedupe(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key_fn = params.get("key")
            seen = set()
            unique = []
            duplicates = 0
            for r in records:
                if callable(key_fn):
                    k = key_fn(r)
                elif isinstance(key_fn, str) and isinstance(r, dict):
                    k = r.get(key_fn)
                else:
                    k = json.dumps(r, sort_keys=True, default=str)
                khash = hashlib.sha256(str(k).encode()).hexdigest()
                if khash in seen:
                    duplicates += 1
                    continue
                seen.add(khash)
                unique.append(r)
            result = {"domain": "ingest", "method": "dedupe", "data": {"unique": unique, "duplicates": duplicates, "input": len(records)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEDUPE_ERROR", str(e), 0))

    def enrich(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            fields = params.get("fields") or {}
            enriched = []
            for r in records:
                if isinstance(r, dict):
                    merged = dict(r)
                    merged.update(fields)
                    enriched.append(merged)
                else:
                    enriched.append({"value": r, **fields})
            result = {"domain": "ingest", "method": "enrich", "data": {"enriched": enriched, "added_fields": list(fields.keys())}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENRICH_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            source = params.get("source")
            data = params.get("data")
            if source is not None and data is None:
                if isinstance(source, str):
                    with open(source, "r") as fh:
                        raw = fh.read()
                    try:
                        data = json.loads(raw)
                    except Exception:
                        data = raw
            records = data if isinstance(data, list) else [data] if data is not None else []
            self.state["results"].extend(records)
            result = {"domain": "ingest", "method": "load", "data": {"loaded": len(records), "source": source}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            results = self.state.get("results", [])
            summary = {
                "total": len(results),
                "types": {},
                "first_ts": None,
                "last_ts": None,
            }
            for r in results:
                t = type(r).__name__
                summary["types"][t] = summary["types"].get(t, 0) + 1
            if results:
                summary["first_ts"] = getattr(results[0], "ts", None)
                summary["last_ts"] = getattr(results[-1], "ts", None)
            result = {"domain": "ingest", "method": "report", "data": summary}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def schedule(self, params=None):
        params = params or {}
        try:
            job = params.get("job") or "default"
            interval = float(params.get("interval", 60))
            at = params.get("at")
            schedules = self.state.setdefault("config", {}).setdefault("schedules", {})
            entry = {"job": job, "interval": interval, "at": at, "created": time.time()}
            schedules[job] = entry
            result = {"domain": "ingest", "method": "schedule", "data": {"scheduled": True, "entry": entry}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SCHEDULE_ERROR", str(e), 0))

    def store(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            target = params.get("target") or "memory"
            stored = 0
            if target == "memory":
                self.state["results"].extend(records)
                stored = len(records)
            elif isinstance(target, str):
                with open(target, "w") as fh:
                    json.dump(records, fh, default=str)
                stored = len(records)
            result = {"domain": "ingest", "method": "store", "data": {"target": target, "stored": stored}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STORE_ERROR", str(e), 0))

    def transform(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            mapping = params.get("mapping") or {}
            fn = params.get("fn")
            transformed = []
            for r in records:
                if callable(fn):
                    transformed.append(fn(r))
                elif isinstance(r, dict) and mapping:
                    new = OrderedDict()
                    for new_key, old_key in mapping.items():
                        new[new_key] = r.get(old_key)
                    transformed.append(dict(new))
                else:
                    transformed.append(r)
            result = {"domain": "ingest", "method": "transform", "data": {"transformed": transformed, "count": len(transformed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRANSFORM_ERROR", str(e), 0))
