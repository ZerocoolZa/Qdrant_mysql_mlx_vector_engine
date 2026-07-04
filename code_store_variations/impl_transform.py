class DomTransform:
    """Data transformation operations: clean, filter, map, reduce, sort, merge and more."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "clean": self.clean,
            "dedupe": self.dedupe,
            "enrich": self.enrich,
            "filter": self.filter,
            "flatten": self.flatten,
            "format": self.format,
            "group": self.group,
            "map": self.map,
            "merge": self.merge,
            "project": self.project,
            "reduce": self.reduce,
            "rename": self.rename,
            "restructure": self.restructure,
            "sort": self.sort,
            "split": self.split,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def clean(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            strip = params.get("strip", True)
            lower = params.get("lower", False)
            drop_empty = params.get("drop_empty", True)
            cleaned = []
            for it in items:
                val = it
                if isinstance(val, str):
                    if strip:
                        val = val.strip()
                    if lower:
                        val = val.lower()
                    if drop_empty and val == "":
                        continue
                cleaned.append(val)
            result = {"domain": "transform", "method": "clean", "data": cleaned, "count": len(cleaned)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAN_ERROR", str(e), 0))

    def dedupe(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            key = params.get("key")
            seen = set()
            out = []
            for it in items:
                k = it.get(key) if (key and isinstance(it, dict)) else it
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
            result = {"domain": "transform", "method": "dedupe", "data": out, "removed": len(items) - len(out)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEDUPE_ERROR", str(e), 0))

    def enrich(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            extra = params.get("extra", {})
            enriched = []
            for it in items:
                if isinstance(it, dict):
                    new_it = dict(it)
                    new_it.update(extra)
                    enriched.append(new_it)
                else:
                    enriched.append({"value": it, **extra})
            result = {"domain": "transform", "method": "enrich", "data": enriched, "added_fields": list(extra.keys())}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENRICH_ERROR", str(e), 0))

    def filter(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            predicate = params.get("predicate", {})
            field = predicate.get("field")
            op = predicate.get("op", "eq")
            value = predicate.get("value")
            out = []
            for it in items:
                v = it.get(field) if (field and isinstance(it, dict)) else it
                keep = False
                if op == "eq":
                    keep = v == value
                elif op == "ne":
                    keep = v != value
                elif op == "gt":
                    keep = v is not None and value is not None and v > value
                elif op == "lt":
                    keep = v is not None and value is not None and v < value
                elif op == "gte":
                    keep = v is not None and value is not None and v >= value
                elif op == "lte":
                    keep = v is not None and value is not None and v <= value
                elif op == "in":
                    keep = v in (value or [])
                elif op == "contains":
                    keep = value in v if isinstance(v, (str, list, tuple)) else False
                if keep:
                    out.append(it)
            result = {"domain": "transform", "method": "filter", "data": out, "kept": len(out), "dropped": len(items) - len(out)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FILTER_ERROR", str(e), 0))

    def flatten(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            depth = params.get("depth", 1)

            def _flatten(seq, d):
                out = []
                for el in seq:
                    if isinstance(el, (list, tuple)) and d > 0:
                        out.extend(_flatten(el, d - 1))
                    else:
                        out.append(el)
                return out

            flat = _flatten(items, depth)
            result = {"domain": "transform", "method": "flatten", "data": flat, "count": len(flat)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FLATTEN_ERROR", str(e), 0))

    def format(self, params=None):
        params = params or {}
        try:
            template = params.get("template", "{value}")
            items = params.get("items", [])
            formatted = [template.format(value=it, **params.get("fields", {})) if isinstance(it, (str, int, float)) else template.format(**it) for it in items]
            result = {"domain": "transform", "method": "format", "data": formatted, "template": template}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORMAT_ERROR", str(e), 0))

    def group(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            key = params.get("key")
            groups = {}
            for it in items:
                k = it.get(key) if (key and isinstance(it, dict)) else it
                groups.setdefault(k, []).append(it)
            result = {"domain": "transform", "method": "group", "data": groups, "group_count": len(groups)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GROUP_ERROR", str(e), 0))

    def map(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            field = params.get("field")
            op = params.get("op", "identity")
            arg = params.get("arg")
            out = []
            for it in items:
                v = it.get(field) if (field and isinstance(it, dict)) else it
                if op == "upper":
                    v = str(v).upper()
                elif op == "lower":
                    v = str(v).lower()
                elif op == "add":
                    v = v + arg
                elif op == "mul":
                    v = v * arg
                elif op == "neg":
                    v = -v
                elif op == "len":
                    v = len(v)
                elif op == "str":
                    v = str(v)
                elif op == "int":
                    v = int(v)
                elif op == "float":
                    v = float(v)
                if field and isinstance(it, dict):
                    new_it = dict(it)
                    new_it[field] = v
                    out.append(new_it)
                else:
                    out.append(v)
            result = {"domain": "transform", "method": "map", "data": out, "op": op}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MAP_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            lists = params.get("lists", [])
            merged = []
            for lst in lists:
                merged.extend(lst)
            result = {"domain": "transform", "method": "merge", "data": merged, "count": len(merged)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def project(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            fields = params.get("fields", [])
            projected = []
            for it in items:
                if isinstance(it, dict):
                    projected.append({f: it.get(f) for f in fields})
                else:
                    projected.append(it)
            result = {"domain": "transform", "method": "project", "data": projected, "fields": fields}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROJECT_ERROR", str(e), 0))

    def reduce(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            op = params.get("op", "sum")
            start = params.get("start", 0)
            field = params.get("field")
            vals = [it.get(field) if (field and isinstance(it, dict)) else it for it in items]
            acc = start
            if op == "sum":
                acc = sum(vals) if vals else start
            elif op == "product":
                acc = start
                for v in vals:
                    acc = acc * v
            elif op == "count":
                acc = len(vals)
            elif op == "min":
                acc = min(vals) if vals else None
            elif op == "max":
                acc = max(vals) if vals else None
            elif op == "concat":
                acc = "".join(str(v) for v in vals)
            result = {"domain": "transform", "method": "reduce", "data": acc, "op": op}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REDUCE_ERROR", str(e), 0))

    def rename(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            mapping = params.get("mapping", {})
            renamed = []
            for it in items:
                if isinstance(it, dict):
                    new_it = {}
                    for k, v in it.items():
                        new_it[mapping.get(k, k)] = v
                    renamed.append(new_it)
                else:
                    renamed.append(it)
            result = {"domain": "transform", "method": "rename", "data": renamed, "mapping": mapping}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RENAME_ERROR", str(e), 0))

    def restructure(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            mode = params.get("mode", "list_to_dict")
            key_field = params.get("key_field", "id")
            if mode == "list_to_dict":
                out = {}
                for it in items:
                    if isinstance(it, dict):
                        out[it.get(key_field)] = it
                result = {"domain": "transform", "method": "restructure", "data": out, "mode": mode}
            elif mode == "dict_to_list":
                out = list(items.values()) if isinstance(items, dict) else items
                result = {"domain": "transform", "method": "restructure", "data": out, "mode": mode}
            else:
                result = {"domain": "transform", "method": "restructure", "data": items, "mode": mode}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESTRUCTURE_ERROR", str(e), 0))

    def sort(self, params=None):
        params = params or {}
        try:
            items = list(params.get("items", []))
            key = params.get("key")
            reverse = params.get("reverse", False)
            if key and items and isinstance(items[0], dict):
                items.sort(key=lambda x: x.get(key), reverse=reverse)
            else:
                items.sort(reverse=reverse)
            result = {"domain": "transform", "method": "sort", "data": items, "reverse": reverse}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SORT_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            items = params.get("items", [])
            size = params.get("size", 1)
            chunks = [items[i:i + size] for i in range(0, len(items), size)]
            result = {"domain": "transform", "method": "split", "data": chunks, "chunk_count": len(chunks)}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))
