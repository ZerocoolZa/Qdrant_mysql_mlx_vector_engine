class DomIndex:
    """Index domain: build, merge, split and maintain searchable indices."""

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
            "build": self.build,
            "create": self.create,
            "delete": self.delete,
            "import": self.import_,
            "merge": self.merge,
            "optimize": self.optimize,
            "rebuild": self.rebuild,
            "split": self.split,
            "stats": self.stats,
            "update": self.update,
        }
        h = handlers.get(command)
        if h:
            return h(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def build(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            documents = params.get("documents", [])
            if not name:
                return (0, None, ("BUILD_ERROR", "name required", 0))
            index = {"name": name, "documents": len(documents), "built": True}
            self.state["catalog"].append(index)
            result = {"domain": "index", "method": "build", "index": index}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def create(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            fields = params.get("fields", [])
            if not name:
                return (0, None, ("CREATE_ERROR", "name required", 0))
            index = {"name": name, "fields": fields, "documents": 0}
            self.state["catalog"].append(index)
            result = {"domain": "index", "method": "create", "index": index, "created": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("DELETE_ERROR", "name required", 0))
            self.state["catalog"] = [c for c in self.state["catalog"] if c.get("name") != name]
            result = {"domain": "index", "method": "delete", "name": name, "deleted": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            documents = params.get("documents", [])
            if not name:
                return (0, None, ("IMPORT_ERROR", "name required", 0))
            idx = next((c for c in self.state["catalog"] if c.get("name") == name), None)
            if idx is None:
                idx = {"name": name, "documents": 0}
                self.state["catalog"].append(idx)
            idx["documents"] = idx.get("documents", 0) + len(documents)
            result = {"domain": "index", "method": "import", "name": name, "imported": len(documents), "total": idx["documents"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            sources = params.get("sources", [])
            target = params.get("target")
            if not sources or not target:
                return (0, None, ("MERGE_ERROR", "sources and target required", 0))
            total = 0
            for s in sources:
                idx = next((c for c in self.state["catalog"] if c.get("name") == s), None)
                if idx:
                    total += idx.get("documents", 0)
            merged = {"name": target, "documents": total, "merged_from": sources}
            self.state["catalog"].append(merged)
            result = {"domain": "index", "method": "merge", "merged": merged}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def optimize(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("OPTIMIZE_ERROR", "name required", 0))
            result = {"domain": "index", "method": "optimize", "name": name, "optimized": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPTIMIZE_ERROR", str(e), 0))

    def rebuild(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("REBUILD_ERROR", "name required", 0))
            idx = next((c for c in self.state["catalog"] if c.get("name") == name), None)
            if idx:
                idx["rebuilt"] = True
            result = {"domain": "index", "method": "rebuild", "name": name, "rebuilt": True}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REBUILD_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            parts = params.get("parts", 2)
            if not name:
                return (0, None, ("SPLIT_ERROR", "name required", 0))
            idx = next((c for c in self.state["catalog"] if c.get("name") == name), None)
            total = idx.get("documents", 0) if idx else 0
            per = total // int(parts) if parts else 0
            shards = [{"name": f"{name}_{i}", "documents": per} for i in range(int(parts))]
            result = {"domain": "index", "method": "split", "name": name, "shards": shards}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))

    def stats(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if name:
                idx = next((c for c in self.state["catalog"] if c.get("name") == name), None)
                stats = {"name": name, "documents": idx.get("documents", 0) if idx else 0}
            else:
                stats = {"indices": len(self.state["catalog"]), "total_documents": sum(c.get("documents", 0) for c in self.state["catalog"])}
            result = {"domain": "index", "method": "stats", "stats": stats}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def update(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            documents = params.get("documents", [])
            if not name:
                return (0, None, ("UPDATE_ERROR", "name required", 0))
            idx = next((c for c in self.state["catalog"] if c.get("name") == name), None)
            if idx is None:
                idx = {"name": name, "documents": 0}
                self.state["catalog"].append(idx)
            idx["documents"] = idx.get("documents", 0) + len(documents)
            result = {"domain": "index", "method": "update", "name": name, "added": len(documents), "total": idx["documents"]}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))
