import math

class DomWwsIndex:
    """Inverted index operations: build, create, update, delete, merge, optimize, rebuild, stats and import."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._index = {}
        self._docs = {}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "build": self.build,
            "create": self.create,
            "delete": self.delete,
            "import": self._import,
            "merge": self.merge,
            "optimize": self.optimize,
            "rebuild": self.rebuild,
            "stats": self.stats,
            "update": self.update,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _tokenize(self, text):
        return [t for t in text.lower().split() if t]

    def _add_doc_to_index(self, doc_id, tokens):
        for pos, tok in enumerate(tokens):
            self._index.setdefault(tok, {}).setdefault(doc_id, []).append(pos)

    def _remove_doc_from_index(self, doc_id):
        for tok in list(self._index.keys()):
            if doc_id in self._index[tok]:
                del self._index[tok][doc_id]
                if not self._index[tok]:
                    del self._index[tok]

    def build(self, params=None):
        params = params or {}
        try:
            documents = params.get("documents", {})
            self._index = {}
            self._docs = {}
            for doc_id, text in documents.items():
                tokens = self._tokenize(text) if isinstance(text, str) else text
                self._docs[doc_id] = tokens
                self._add_doc_to_index(doc_id, tokens)
            result = {"domain": "wws_index", "method": "build", "data": {"docs": len(self._docs), "terms": len(self._index)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def create(self, params=None):
        params = params or {}
        try:
            doc_id = params.get("doc_id")
            text = params.get("text", "")
            if doc_id is None:
                return (0, None, ("CREATE_ERROR", "doc_id required", 0))
            tokens = self._tokenize(text)
            self._docs[doc_id] = tokens
            self._add_doc_to_index(doc_id, tokens)
            result = {"domain": "wws_index", "method": "create", "data": {"doc_id": doc_id, "tokens": len(tokens)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def update(self, params=None):
        params = params or {}
        try:
            doc_id = params.get("doc_id")
            text = params.get("text", "")
            if doc_id is None:
                return (0, None, ("UPDATE_ERROR", "doc_id required", 0))
            if doc_id in self._docs:
                self._remove_doc_from_index(doc_id)
            tokens = self._tokenize(text)
            self._docs[doc_id] = tokens
            self._add_doc_to_index(doc_id, tokens)
            result = {"domain": "wws_index", "method": "update", "data": {"doc_id": doc_id, "tokens": len(tokens), "updated": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            doc_id = params.get("doc_id")
            if doc_id is None:
                return (0, None, ("DELETE_ERROR", "doc_id required", 0))
            existed = doc_id in self._docs
            if existed:
                self._remove_doc_from_index(doc_id)
                del self._docs[doc_id]
            result = {"domain": "wws_index", "method": "delete", "data": {"doc_id": doc_id, "deleted": existed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            other = params.get("index", {})
            other_docs = params.get("docs", {})
            added = 0
            for term, postings in other.items():
                for doc_id, positions in postings.items():
                    self._index.setdefault(term, {}).setdefault(doc_id, []).extend(positions)
                    added += 1
            for doc_id, text in other_docs.items():
                tokens = self._tokenize(text) if isinstance(text, str) else text
                if doc_id not in self._docs:
                    self._docs[doc_id] = tokens
            result = {"domain": "wws_index", "method": "merge", "data": {"merged_postings": added, "docs": len(self._docs), "terms": len(self._index)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def optimize(self, params=None):
        params = params or {}
        try:
            for term in self._index:
                for doc_id in self._index[term]:
                    self._index[term][doc_id] = sorted(set(self._index[term][doc_id]))
            before_terms = len(self._index)
            self._index = {t: p for t, p in self._index.items() if p}
            result = {"domain": "wws_index", "method": "optimize", "data": {"terms": len(self._index), "removed_empty": before_terms - len(self._index), "docs": len(self._docs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPTIMIZE_ERROR", str(e), 0))

    def rebuild(self, params=None):
        params = params or {}
        try:
            docs = dict(self._docs)
            self._index = {}
            for doc_id, tokens in docs.items():
                self._add_doc_to_index(doc_id, tokens)
            result = {"domain": "wws_index", "method": "rebuild", "data": {"docs": len(self._docs), "terms": len(self._index), "rebuilt": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REBUILD_ERROR", str(e), 0))

    def stats(self, params=None):
        params = params or {}
        try:
            postings_total = sum(len(p) for p in self._index.values())
            avg_postings = postings_total / len(self._index) if self._index else 0
            doc_lens = [len(t) for t in self._docs.values()]
            avg_doc_len = sum(doc_lens) / len(doc_lens) if doc_lens else 0
            result = {"domain": "wws_index", "method": "stats", "data": {"docs": len(self._docs), "terms": len(self._index), "postings": postings_total, "avg_postings_per_term": avg_postings, "avg_doc_len": avg_doc_len}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))

    def _import(self, params=None):
        params = params or {}
        try:
            data = params.get("data", {})
            index = data.get("index", {})
            docs = data.get("docs", {})
            self._index = dict(index)
            self._docs = {}
            for doc_id, text in docs.items():
                self._docs[doc_id] = self._tokenize(text) if isinstance(text, str) else text
            result = {"domain": "wws_index", "method": "import", "data": {"docs": len(self._docs), "terms": len(self._index)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))
