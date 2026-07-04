import re
import math
import json
import hashlib


class DomSearch:
    """Search domain: text and vector search operations over a catalog."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))
                self.state["catalog"] = list(param.get("catalog", []))
            elif isinstance(param, list):
                self.state["catalog"] = list(param)

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "autocomplete": self.autocomplete,
            "embed": self.embed,
            "facet": self.facet,
            "filter": self.filter,
            "fuzzy": self.fuzzy,
            "highlight": self.highlight,
            "match": self.match,
            "nearest": self.nearest,
            "phrase": self.phrase,
            "regex": self.regex,
            "reindex": self.reindex,
            "similarity": self.similarity,
            "snippet": self.snippet,
            "sort": self.sort,
            "suggest": self.suggest,
            "vector": self.vector,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _catalog(self, params):
        catalog = params.get("catalog")
        if catalog is None:
            catalog = self.state.get("catalog", [])
        return list(catalog)

    def autocomplete(self, params=None):
        params = params or {}
        try:
            prefix = str(params.get("prefix", "")).lower()
            field = params.get("field", "text")
            limit = int(params.get("limit", 10))
            catalog = self._catalog(params)
            matches = []
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else item).lower()
                if val.startswith(prefix):
                    matches.append(item)
            matches = matches[:limit]
            result = {"domain": "search", "method": "autocomplete", "data": {"matches": matches, "count": len(matches)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AUTOCOMPLETE_ERROR", str(e), 0))

    def embed(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            dim = int(params.get("dim", 64))
            if dim <= 0:
                dim = 64
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec = []
            for i in range(dim):
                byte_val = h[i % len(h)]
                vec.append((byte_val / 255.0) * 2 - 1)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            result = {"domain": "search", "method": "embed", "data": {"vector": vec, "dim": dim}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EMBED_ERROR", str(e), 0))

    def facet(self, params=None):
        params = params or {}
        try:
            field = params.get("field", "category")
            catalog = self._catalog(params)
            counts = {}
            for item in catalog:
                if isinstance(item, dict):
                    val = item.get(field)
                else:
                    val = getattr(item, field, None)
                key = str(val) if val is not None else "null"
                counts[key] = counts.get(key, 0) + 1
            facets = [{"value": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
            result = {"domain": "search", "method": "facet", "data": {"field": field, "facets": facets}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FACET_ERROR", str(e), 0))

    def filter(self, params=None):
        params = params or {}
        try:
            field = params.get("field", "text")
            op = params.get("op", "eq")
            value = params.get("value")
            catalog = self._catalog(params)
            out = []
            for item in catalog:
                if isinstance(item, dict):
                    iv = item.get(field)
                else:
                    iv = getattr(item, field, None)
                matched = False
                if op == "eq":
                    matched = iv == value
                elif op == "ne":
                    matched = iv != value
                elif op == "gt":
                    matched = iv is not None and value is not None and iv > value
                elif op == "lt":
                    matched = iv is not None and value is not None and iv < value
                elif op == "gte":
                    matched = iv is not None and value is not None and iv >= value
                elif op == "lte":
                    matched = iv is not None and value is not None and iv <= value
                elif op == "in":
                    matched = iv in (value if isinstance(value, (list, tuple, set)) else [value])
                elif op == "contains":
                    matched = value in iv if iv is not None else False
                if matched:
                    out.append(item)
            result = {"domain": "search", "method": "filter", "data": {"results": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FILTER_ERROR", str(e), 0))

    def fuzzy(self, params=None):
        params = params or {}
        try:
            query = str(params.get("query", ""))
            field = params.get("field", "text")
            threshold = float(params.get("threshold", 0.6))
            catalog = self._catalog(params)
            results = []
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, ""))
                score = self._fuzzy_ratio(query, val)
                if score >= threshold:
                    results.append({"item": item, "score": score})
            results.sort(key=lambda x: -x["score"])
            result = {"domain": "search", "method": "fuzzy", "data": {"results": results, "count": len(results)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FUZZY_ERROR", str(e), 0))

    def _fuzzy_ratio(self, a, b):
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        a_lower = a.lower()
        b_lower = b.lower()
        if a_lower == b_lower:
            return 1.0
        la, lb = len(a_lower), len(b_lower)
        if abs(la - lb) > max(la, lb) // 2:
            return 0.0
        dp = [[0] * (lb + 1) for _ in range(la + 1)]
        for i in range(la + 1):
            dp[i][0] = i
        for j in range(lb + 1):
            dp[0][j] = j
        for i in range(1, la + 1):
            for j in range(1, lb + 1):
                cost = 0 if a_lower[i - 1] == b_lower[j - 1] else 1
                dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
        dist = dp[la][lb]
        return 1.0 - dist / max(la, lb)

    def highlight(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            query = str(params.get("query", ""))
            tag = params.get("tag", "em")
            if not query:
                result = {"domain": "search", "method": "highlight", "data": {"text": text, "highlights": []}}
                return (1, result, None)
            highlights = []
            idx = 0
            q_lower = query.lower()
            t_lower = text.lower()
            out = []
            while True:
                pos = t_lower.find(q_lower, idx)
                if pos == -1:
                    out.append(text[idx:])
                    break
                out.append(text[idx:pos])
                out.append(f"<{tag}>{text[pos:pos + len(query)]}</{tag}>")
                highlights.append({"start": pos, "end": pos + len(query)})
                idx = pos + len(query)
            result = {"domain": "search", "method": "highlight", "data": {"text": "".join(out), "highlights": highlights}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HIGHLIGHT_ERROR", str(e), 0))

    def match(self, params=None):
        params = params or {}
        try:
            query = str(params.get("query", "")).lower()
            field = params.get("field", "text")
            catalog = self._catalog(params)
            out = []
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, "")).lower()
                if query in val:
                    out.append(item)
            result = {"domain": "search", "method": "match", "data": {"results": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MATCH_ERROR", str(e), 0))

    def nearest(self, params=None):
        params = params or {}
        try:
            query_vec = params.get("vector", [])
            field = params.get("field", "vector")
            k = int(params.get("k", 5))
            catalog = self._catalog(params)
            scored = []
            for item in catalog:
                if isinstance(item, dict):
                    iv = item.get(field, [])
                else:
                    iv = getattr(item, field, [])
                if not isinstance(iv, (list, tuple)):
                    continue
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(query_vec, iv)))
                scored.append({"item": item, "distance": dist})
            scored.sort(key=lambda x: x["distance"])
            top = scored[:k]
            result = {"domain": "search", "method": "nearest", "data": {"neighbors": top, "count": len(top)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NEAREST_ERROR", str(e), 0))

    def phrase(self, params=None):
        params = params or {}
        try:
            phrase = str(params.get("phrase", "")).lower()
            field = params.get("field", "text")
            catalog = self._catalog(params)
            out = []
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, "")).lower()
                if phrase and phrase in val:
                    out.append(item)
            result = {"domain": "search", "method": "phrase", "data": {"results": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PHRASE_ERROR", str(e), 0))

    def regex(self, params=None):
        params = params or {}
        try:
            pattern = str(params.get("pattern", ""))
            field = params.get("field", "text")
            flags = 0
            if params.get("ignore_case", True):
                flags |= re.IGNORECASE
            rx = re.compile(pattern, flags)
            catalog = self._catalog(params)
            out = []
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, ""))
                if rx.search(val):
                    out.append(item)
            result = {"domain": "search", "method": "regex", "data": {"results": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REGEX_ERROR", str(e), 0))

    def reindex(self, params=None):
        params = params or {}
        try:
            catalog = self._catalog(params)
            field = params.get("field", "text")
            index = {}
            for i, item in enumerate(catalog):
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, "")).lower()
                for tok in re.split(r"\W+", val):
                    if tok:
                        index.setdefault(tok, []).append(i)
            self.state["catalog"] = list(catalog)
            self.state["results"] = index
            result = {"domain": "search", "method": "reindex", "data": {"tokens": len(index), "docs": len(catalog)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REINDEX_ERROR", str(e), 0))

    def similarity(self, params=None):
        params = params or {}
        try:
            a = params.get("a", [])
            b = params.get("b", [])
            metric = params.get("metric", "cosine")
            if not a or not b:
                result = {"domain": "search", "method": "similarity", "data": {"score": 0.0, "metric": metric}}
                return (1, result, None)
            if metric == "cosine":
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a)) or 1.0
                nb = math.sqrt(sum(y * y for y in b)) or 1.0
                score = dot / (na * nb)
            elif metric == "dot":
                score = sum(x * y for x, y in zip(a, b))
            elif metric == "euclidean":
                score = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
            else:
                score = 0.0
            result = {"domain": "search", "method": "similarity", "data": {"score": score, "metric": metric}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIMILARITY_ERROR", str(e), 0))

    def snippet(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            query = str(params.get("query", ""))
            radius = int(params.get("radius", 30))
            if not query or not text:
                result = {"domain": "search", "method": "snippet", "data": {"snippet": text}}
                return (1, result, None)
            pos = text.lower().find(query.lower())
            if pos == -1:
                snippet = text[:radius * 2]
            else:
                start = max(0, pos - radius)
                end = min(len(text), pos + len(query) + radius)
                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
            result = {"domain": "search", "method": "snippet", "data": {"snippet": snippet}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SNIPPET_ERROR", str(e), 0))

    def sort(self, params=None):
        params = params or {}
        try:
            field = params.get("field", "text")
            order = params.get("order", "asc")
            catalog = self._catalog(params)
            def key_fn(item):
                if isinstance(item, dict):
                    return item.get(field)
                return getattr(item, field, None)
            reverse = (order == "desc")
            out = sorted(catalog, key=key_fn, reverse=reverse)
            result = {"domain": "search", "method": "sort", "data": {"results": out, "count": len(out)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SORT_ERROR", str(e), 0))

    def suggest(self, params=None):
        params = params or {}
        try:
            query = str(params.get("query", "")).lower()
            field = params.get("field", "text")
            limit = int(params.get("limit", 10))
            catalog = self._catalog(params)
            tokens = set()
            for item in catalog:
                val = str(item.get(field, "") if isinstance(item, dict) else getattr(item, field, "")).lower()
                for tok in re.split(r"\W+", val):
                    if tok and tok.startswith(query):
                        tokens.add(tok)
            suggestions = sorted(tokens)[:limit]
            result = {"domain": "search", "method": "suggest", "data": {"suggestions": suggestions, "count": len(suggestions)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SUGGEST_ERROR", str(e), 0))

    def vector(self, params=None):
        params = params or {}
        try:
            query_vec = params.get("vector", [])
            field = params.get("field", "vector")
            k = int(params.get("k", 5))
            catalog = self._catalog(params)
            scored = []
            for item in catalog:
                if isinstance(item, dict):
                    iv = item.get(field, [])
                else:
                    iv = getattr(item, field, [])
                if not isinstance(iv, (list, tuple)):
                    continue
                dot = sum(a * b for a, b in zip(query_vec, iv))
                na = math.sqrt(sum(x * x for x in query_vec)) or 1.0
                nb = math.sqrt(sum(y * y for y in iv)) or 1.0
                score = dot / (na * nb)
                scored.append({"item": item, "score": score})
            scored.sort(key=lambda x: -x["score"])
            top = scored[:k]
            result = {"domain": "search", "method": "vector", "data": {"results": top, "count": len(top)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VECTOR_ERROR", str(e), 0))
