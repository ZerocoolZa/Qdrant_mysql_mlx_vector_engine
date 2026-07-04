import time
import uuid
from collections import deque


class DomIngestCli:
    """CLI ingestion batch tracking: load, schedule, status, resume, cancel, report."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        handler = getattr(self, command, None)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _batches(self):
        if "batches" not in self.state:
            self.state["batches"] = {}
        return self.state["batches"]

    def _new_id(self):
        return uuid.uuid4().hex[:12]

    def batch(self, params=None):
        params = params or {}
        try:
            items = params.get("items") or []
            if not items and params.get("paths"):
                items = params.get("paths")
            if not items:
                return (0, None, ("BATCH_ERROR", "missing items", 0))
            batch_id = params.get("batch_id") or self._new_id()
            batches = self._batches()
            batches[batch_id] = {
                "batch_id": batch_id,
                "items": list(items),
                "status": "pending",
                "created_at": time.time(),
                "processed": [],
                "failed": [],
            }
            result = {"domain": "ingest_cli", "method": "batch", "data": {"batch_id": batch_id, "item_count": len(items), "status": "pending"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BATCH_ERROR", str(e), 0))

    def cancel(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            if not batch_id:
                return (0, None, ("CANCEL_ERROR", "missing batch_id", 0))
            batches = self._batches()
            if batch_id not in batches:
                return (0, None, ("CANCEL_ERROR", "batch not found", 0))
            batches[batch_id]["status"] = "cancelled"
            batches[batch_id]["cancelled_at"] = time.time()
            result = {"domain": "ingest_cli", "method": "cancel", "data": {"batch_id": batch_id, "status": "cancelled"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CANCEL_ERROR", str(e), 0))

    def load(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            if not batch_id:
                return (0, None, ("LOAD_ERROR", "missing batch_id", 0))
            batches = self._batches()
            if batch_id not in batches:
                return (0, None, ("LOAD_ERROR", "batch not found", 0))
            batch = batches[batch_id]
            batch["status"] = "running"
            batch["started_at"] = time.time()
            items = batch["items"]
            limit = params.get("limit", len(items))
            processed = []
            failed = []
            for item in items[:limit]:
                if isinstance(item, str) and item:
                    processed.append(item)
                else:
                    failed.append(item)
            batch["processed"] = processed
            batch["failed"] = failed
            batch["status"] = "completed" if len(processed) + len(failed) >= len(items) else "partial"
            batch["completed_at"] = time.time()
            result = {"domain": "ingest_cli", "method": "load", "data": {"batch_id": batch_id, "processed": len(processed), "failed": len(failed), "status": batch["status"]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            batches = self._batches()
            if batch_id:
                if batch_id not in batches:
                    return (0, None, ("REPORT_ERROR", "batch not found", 0))
                b = batches[batch_id]
                summary = {"batch_id": batch_id, "status": b["status"], "total": len(b["items"]), "processed": len(b["processed"]), "failed": len(b["failed"])}
            else:
                summary = []
                for bid, b in batches.items():
                    summary.append({"batch_id": bid, "status": b["status"], "total": len(b["items"]), "processed": len(b["processed"]), "failed": len(b["failed"])})
            result = {"domain": "ingest_cli", "method": "report", "data": {"summary": summary, "batch_count": len(batches)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def resume(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            if not batch_id:
                return (0, None, ("RESUME_ERROR", "missing batch_id", 0))
            batches = self._batches()
            if batch_id not in batches:
                return (0, None, ("RESUME_ERROR", "batch not found", 0))
            batch = batches[batch_id]
            if batch["status"] not in ("partial", "paused", "failed"):
                return (0, None, ("RESUME_ERROR", "batch not resumable", 0))
            remaining = [i for i in batch["items"] if i not in batch["processed"]]
            batch["status"] = "running"
            for item in remaining:
                if isinstance(item, str) and item:
                    batch["processed"].append(item)
                else:
                    batch["failed"].append(item)
            batch["status"] = "completed"
            batch["resumed_at"] = time.time()
            result = {"domain": "ingest_cli", "method": "resume", "data": {"batch_id": batch_id, "resumed": len(remaining), "status": batch["status"]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESUME_ERROR", str(e), 0))

    def schedule(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            if not batch_id:
                return (0, None, ("SCHEDULE_ERROR", "missing batch_id", 0))
            batches = self._batches()
            if batch_id not in batches:
                batches[batch_id] = {
                    "batch_id": batch_id,
                    "items": params.get("items", []),
                    "status": "scheduled",
                    "created_at": time.time(),
                    "processed": [],
                    "failed": [],
                }
            when = params.get("when") or params.get("at") or time.time()
            batches[batch_id]["status"] = "scheduled"
            batches[batch_id]["scheduled_at"] = when
            result = {"domain": "ingest_cli", "method": "schedule", "data": {"batch_id": batch_id, "scheduled_at": when, "status": "scheduled"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SCHEDULE_ERROR", str(e), 0))

    def status(self, params=None):
        params = params or {}
        try:
            batch_id = params.get("batch_id")
            batches = self._batches()
            if not batch_id:
                statuses = [{"batch_id": bid, "status": b["status"], "progress": round(len(b["processed"]) / max(1, len(b["items"])), 2)} for bid, b in batches.items()]
                result = {"domain": "ingest_cli", "method": "status", "data": {"batches": statuses, "count": len(statuses)}}
                return (1, result, None)
            if batch_id not in batches:
                return (0, None, ("STATUS_ERROR", "batch not found", 0))
            b = batches[batch_id]
            progress = round(len(b["processed"]) / max(1, len(b["items"])), 2)
            result = {"domain": "ingest_cli", "method": "status", "data": {"batch_id": batch_id, "status": b["status"], "progress": progress, "total": len(b["items"]), "processed": len(b["processed"]), "failed": len(b["failed"])}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))
