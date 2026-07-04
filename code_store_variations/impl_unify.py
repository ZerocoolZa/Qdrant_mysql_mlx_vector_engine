class DomUnify:
    """Entity unification: match, dedupe, merge, link, group, resolve, aggregate, standardize, report."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "entities": {},
            "links": [],
            "groups": [],
        }
        self.mem = mem
        self.db = db
        self._next_id = 1

    def _new_id(self):
        cid = self._next_id
        self._next_id += 1
        return cid

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "aggregate": self.aggregate,
            "dedupe": self.dedupe,
            "group": self.group,
            "link": self.link,
            "match": self.match,
            "merge": self.merge,
            "report": self.report,
            "resolve": self.resolve,
            "standardize": self.standardize,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _normalize(self, value):
        if value is None:
            return ""
        return str(value).strip().lower()

    def match(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key = params.get("key", "name")
            threshold = float(params.get("threshold", 0.8))
            pairs = []
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    a = self._normalize(records[i].get(key))
                    b = self._normalize(records[j].get(key))
                    if not a or not b:
                        continue
                    if a == b:
                        score = 1.0
                    else:
                        longer = max(len(a), len(b))
                        shorter = min(len(a), len(b))
                        if longer == 0:
                            score = 1.0
                        else:
                            matches = sum(1 for k in range(shorter) if k < len(a) and k < len(b) and a[k] == b[k])
                            score = matches / longer
                    if score >= threshold:
                        pairs.append({"a": records[i], "b": records[j], "score": round(score, 3)})
            result = {"domain": "unify", "method": "match", "data": {"pairs": pairs, "count": len(pairs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MATCH_ERROR", str(e), 0))

    def dedupe(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key = params.get("key", "id")
            seen = {}
            unique = []
            duplicates = []
            for rec in records:
                k = rec.get(key)
                if k in seen:
                    duplicates.append(rec)
                else:
                    seen[k] = True
                    unique.append(rec)
            result = {"domain": "unify", "method": "dedupe", "data": {"unique": unique, "duplicates": duplicates, "removed": len(duplicates)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEDUPE_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            strategy = params.get("strategy", "first")
            if not records:
                return (0, None, ("EMPTY_RECORDS", "records required", 0))
            merged = {}
            for rec in records:
                for k, v in rec.items():
                    if k not in merged or v is None:
                        if k not in merged or merged[k] is None:
                            merged[k] = v
                    elif strategy == "last" and v is not None:
                        merged[k] = v
            result = {"domain": "unify", "method": "merge", "data": {"merged": merged, "source_count": len(records)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def link(self, params=None):
        params = params or {}
        try:
            source = params.get("source")
            target = params.get("target")
            relation = params.get("relation", "same_as")
            if source is None or target is None:
                return (0, None, ("MISSING_LINK", "source and target required", 0))
            link = {"id": self._new_id(), "source": source, "target": target, "relation": relation}
            self.state["links"].append(link)
            result = {"domain": "unify", "method": "link", "data": link}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LINK_ERROR", str(e), 0))

    def group(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key = params.get("key", "category")
            groups = {}
            for rec in records:
                k = rec.get(key, "uncategorized")
                groups.setdefault(k, []).append(rec)
            self.state["groups"] = [{"key": k, "members": v} for k, v in groups.items()]
            result = {"domain": "unify", "method": "group", "data": {"groups": groups, "count": len(groups)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GROUP_ERROR", str(e), 0))

    def resolve(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key = params.get("key", "name")
            threshold = float(params.get("threshold", 0.9))
            clusters = []
            for rec in records:
                placed = False
                norm = self._normalize(rec.get(key))
                for cluster in clusters:
                    if self._normalize(cluster["canonical"].get(key)) == norm:
                        cluster["members"].append(rec)
                        placed = True
                        break
                if not placed:
                    clusters.append({"canonical": rec, "members": [rec]})
            resolved = [{"canonical": c["canonical"], "count": len(c["members"])} for c in clusters]
            result = {"domain": "unify", "method": "resolve", "data": {"clusters": resolved, "count": len(clusters)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESOLVE_ERROR", str(e), 0))

    def aggregate(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            group_key = params.get("group_key", "category")
            agg_key = params.get("agg_key", "value")
            operation = params.get("operation", "sum")
            groups = {}
            for rec in records:
                gk = rec.get(group_key, "default")
                val = rec.get(agg_key, 0)
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    val = 0
                groups.setdefault(gk, []).append(val)
            aggregated = {}
            for gk, vals in groups.items():
                if operation == "sum":
                    aggregated[gk] = sum(vals)
                elif operation == "avg":
                    aggregated[gk] = sum(vals) / len(vals) if vals else 0
                elif operation == "count":
                    aggregated[gk] = len(vals)
                elif operation == "max":
                    aggregated[gk] = max(vals) if vals else 0
                elif operation == "min":
                    aggregated[gk] = min(vals) if vals else 0
                else:
                    aggregated[gk] = sum(vals)
            result = {"domain": "unify", "method": "aggregate", "data": {"aggregated": aggregated, "operation": operation}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AGGREGATE_ERROR", str(e), 0))

    def standardize(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            field_map = params.get("field_map") or {}
            standardized = []
            for rec in records:
                new_rec = {}
                for k, v in rec.items():
                    new_key = field_map.get(k, k)
                    if isinstance(v, str):
                        new_rec[new_key] = v.strip().lower()
                    else:
                        new_rec[new_key] = v
                standardized.append(new_rec)
            result = {"domain": "unify", "method": "standardize", "data": {"standardized": standardized, "count": len(standardized)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STANDARDIZE_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            data = {
                "entities": len(self.state["entities"]),
                "links": len(self.state["links"]),
                "groups": len(self.state["groups"]),
                "link_relations": [l["relation"] for l in self.state["links"]],
            }
            result = {"domain": "unify", "method": "report", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
