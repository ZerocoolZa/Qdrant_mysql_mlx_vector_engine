class DomStorage:
    """Storage domain: object/blob/record management across buckets and volumes."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            for k, v in param.items():
                self.state["config"][k] = v

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "blob": self.blob,
            "bucket": self.bucket,
            "delete": self.delete,
            "document": self.document,
            "exists": self.exists,
            "object": self.object,
            "put": self.put,
            "record": self.record,
            "replicate": self.replicate,
            "size": self.size,
            "table": self.table,
            "volume": self.volume,
        }
        h = handlers.get(command)
        if h:
            return h(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def blob(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            data = params.get("data")
            if not key:
                return (0, None, ("BLOB_ERROR", "key required", 0))
            size = len(data) if data is not None else 0
            entry = {"key": key, "size": size, "type": "blob"}
            self.state["results"].append(entry)
            result = {"domain": "storage", "method": "blob", "entry": entry, "stored": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BLOB_ERROR", str(e), 0))

    def bucket(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            action = params.get("action", "create")
            if not name:
                return (0, None, ("BUCKET_ERROR", "name required", 0))
            if action == "create":
                self.state["catalog"].append({"type": "bucket", "name": name})
            elif action == "delete":
                self.state["catalog"] = [c for c in self.state["catalog"] if not (c.get("type") == "bucket" and c.get("name") == name)]
            result = {"domain": "storage", "method": "bucket", "name": name, "action": action}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUCKET_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if not key:
                return (0, None, ("DELETE_ERROR", "key required", 0))
            self.state["results"] = [r for r in self.state["results"] if r.get("key") != key]
            result = {"domain": "storage", "method": "delete", "key": key, "deleted": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def document(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            content = params.get("content", "")
            doctype = params.get("type", "json")
            if not key:
                return (0, None, ("DOCUMENT_ERROR", "key required", 0))
            doc = {"key": key, "content": content, "type": doctype}
            self.state["results"].append(doc)
            result = {"domain": "storage", "method": "document", "document": doc, "stored": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DOCUMENT_ERROR", str(e), 0))

    def exists(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if not key:
                return (0, None, ("EXISTS_ERROR", "key required", 0))
            found = any(r.get("key") == key for r in self.state["results"])
            result = {"domain": "storage", "method": "exists", "key": key, "exists": found}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXISTS_ERROR", str(e), 0))

    def object(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if not key:
                return (0, None, ("OBJECT_ERROR", "key required", 0))
            found = next((r for r in self.state["results"] if r.get("key") == key), None)
            result = {"domain": "storage", "method": "object", "key": key, "object": found}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OBJECT_ERROR", str(e), 0))

    def put(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            value = params.get("value")
            if not key:
                return (0, None, ("PUT_ERROR", "key required", 0))
            entry = {"key": key, "value": value}
            self.state["results"].append(entry)
            result = {"domain": "storage", "method": "put", "entry": entry, "stored": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PUT_ERROR", str(e), 0))

    def record(self, params=None):
        params = params or {}
        try:
            table = params.get("table")
            fields = params.get("fields", {})
            if not table or not fields:
                return (0, None, ("RECORD_ERROR", "table and fields required", 0))
            rec = {"table": table, "fields": fields}
            self.state["results"].append(rec)
            result = {"domain": "storage", "method": "record", "record": rec, "stored": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECORD_ERROR", str(e), 0))

    def replicate(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            target = params.get("target")
            if not key or not target:
                return (0, None, ("REPLICATE_ERROR", "key and target required", 0))
            result = {"domain": "storage", "method": "replicate", "key": key, "target": target, "replicated": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPLICATE_ERROR", str(e), 0))

    def size(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if not key:
                return (0, None, ("SIZE_ERROR", "key required", 0))
            obj = next((r for r in self.state["results"] if r.get("key") == key), None)
            total = obj.get("size", 0) if obj else 0
            result = {"domain": "storage", "method": "size", "key": key, "size": total}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIZE_ERROR", str(e), 0))

    def table(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            action = params.get("action", "create")
            if not name:
                return (0, None, ("TABLE_ERROR", "name required", 0))
            if action == "create":
                self.state["catalog"].append({"type": "table", "name": name})
            elif action == "delete":
                self.state["catalog"] = [c for c in self.state["catalog"] if not (c.get("type") == "table" and c.get("name") == name)]
            result = {"domain": "storage", "method": "table", "name": name, "action": action}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TABLE_ERROR", str(e), 0))

    def volume(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            size = params.get("size", 0)
            if not name:
                return (0, None, ("VOLUME_ERROR", "name required", 0))
            vol = {"name": name, "size": size}
            self.state["catalog"].append(vol)
            result = {"domain": "storage", "method": "volume", "volume": vol, "created": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VOLUME_ERROR", str(e), 0))
