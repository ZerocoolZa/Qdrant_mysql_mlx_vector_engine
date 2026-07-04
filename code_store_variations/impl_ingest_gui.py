import time
import uuid as _uuid


class DomIngestGui:
    """GUI ingestion workflow: browse, select, preview, import, progress, history, report, cancel, settings."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._items = []
        self._selected = []
        self._history = []
        self._progress = {}
        self._settings = {"batch_size": 100, "auto_preview": True, "format": "json"}
        self._current_job = None

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "browse": self.browse,
            "cancel": self.cancel,
            "history": self.history,
            "import": self.import_,
            "preview": self.preview,
            "progress": self.progress,
            "report": self.report,
            "select": self.select,
            "settings": self.settings,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def browse(self, params=None):
        params = params or {}
        try:
            path = params.get("path", ".")
            import os
            entries = []
            if path and os.path.isdir(path):
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    entries.append({"name": name, "path": full, "is_dir": os.path.isdir(full), "size": os.path.getsize(full) if os.path.isfile(full) else 0})
            self._items = entries
            result = {"domain": "ingest_gui", "method": "browse", "data": {"path": path, "entries": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BROWSE_ERROR", str(e), 0))

    def select(self, params=None):
        params = params or {}
        try:
            indices = params.get("indices", [])
            names = params.get("names", [])
            selected = []
            for i, item in enumerate(self._items):
                if i in indices or item["name"] in names:
                    selected.append(item)
            self._selected = selected
            result = {"domain": "ingest_gui", "method": "select", "data": {"selected": selected, "count": len(selected)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SELECT_ERROR", str(e), 0))

    def preview(self, params=None):
        params = params or {}
        try:
            items = self._selected if self._selected else self._items
            previews = []
            for item in items[: params.get("limit", 10)]:
                preview_item = {"name": item["name"], "path": item["path"]}
                if "size" in item:
                    preview_item["size"] = item["size"]
                previews.append(preview_item)
            result = {"domain": "ingest_gui", "method": "preview", "data": {"previews": previews, "count": len(previews)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PREVIEW_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            items = self._selected if self._selected else self._items
            job_id = str(_uuid.uuid4())
            self._current_job = job_id
            self._progress[job_id] = {"total": len(items), "done": 0, "status": "running", "started": time.time()}
            imported = []
            for item in items:
                imported.append({"name": item["name"], "path": item.get("path", item["name"]), "imported": True})
                self._progress[job_id]["done"] += 1
            self._progress[job_id]["status"] = "completed"
            self._history.append({"job_id": job_id, "items": imported, "ts": time.time()})
            result = {"domain": "ingest_gui", "method": "import", "data": {"job_id": job_id, "imported": len(imported), "items": imported}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def progress(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", self._current_job)
            prog = self._progress.get(job_id, {})
            if prog:
                pct = (prog["done"] / prog["total"] * 100) if prog["total"] else 0
                prog = dict(prog)
                prog["percent"] = round(pct, 2)
            result = {"domain": "ingest_gui", "method": "progress", "data": {"job_id": job_id, "progress": prog}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROGRESS_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            result = {"domain": "ingest_gui", "method": "history", "data": {"history": self._history, "count": len(self._history)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            total_jobs = len(self._history)
            total_items = sum(len(h["items"]) for h in self._history)
            result = {"domain": "ingest_gui", "method": "report", "data": {"total_jobs": total_jobs, "total_items": total_items, "available": len(self._items), "selected": len(self._selected)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def cancel(self, params=None):
        params = params or {}
        try:
            job_id = params.get("job_id", self._current_job)
            cancelled = False
            if job_id and job_id in self._progress and self._progress[job_id]["status"] == "running":
                self._progress[job_id]["status"] = "cancelled"
                cancelled = True
            result = {"domain": "ingest_gui", "method": "cancel", "data": {"job_id": job_id, "cancelled": cancelled}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CANCEL_ERROR", str(e), 0))

    def settings(self, params=None):
        params = params or {}
        try:
            if "set" in params and isinstance(params["set"], dict):
                self._settings.update(params["set"])
            result = {"domain": "ingest_gui", "method": "settings", "data": {"settings": dict(self._settings)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SETTINGS_ERROR", str(e), 0))
