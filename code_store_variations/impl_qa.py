import math
import hashlib

class DomQa:
    """Question answering: ask, answer, route, score, embed, classify, tune and history."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {"threshold": 0.5, "top_k": 5}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._kb = []
        self._history = []
        self._routes = {}
        self._feedback = []
        self._weights = {"overlap": 1.0, "length": 0.1, "order": 0.2}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "answer": self.answer,
            "ask": self.ask,
            "classify": self.classify,
            "confidence": self.confidence,
            "embed": self.embed,
            "explain": self.explain,
            "fallback": self.fallback,
            "feedback": self.feedback,
            "history": self.history,
            "route": self.route,
            "score": self.score,
            "tune": self.tune,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _tokenize(self, text):
        return [t for t in text.lower().split() if t]

    def _embed_vec(self, text):
        tokens = self._tokenize(text)
        vec = {}
        for t in tokens:
            vec[t] = vec.get(t, 0) + 1
        return vec

    def _cosine(self, a, b):
        if not a or not b:
            return 0.0
        keys = set(a) & set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def embed(self, params=None):
        params = params or {}
        try:
            text = params.get("text", "")
            vec = self._embed_vec(text)
            result = {"domain": "qa", "method": "embed", "data": vec, "dim": len(vec)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EMBED_ERROR", str(e), 0))

    def ask(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            qvec = self._embed_vec(question)
            scored = []
            for item in self._kb:
                sim = self._cosine(qvec, item.get("vec", {}))
                scored.append((sim, item))
            scored.sort(key=lambda x: x[0], reverse=True)
            top_k = self.state["config"].get("top_k", 5)
            best = scored[:top_k]
            self._history.append({"question": question, "ts": len(self._history), "candidates": len(scored)})
            result = {"domain": "qa", "method": "ask", "data": [{"score": s, "answer": it.get("answer"), "q": it.get("q")} for s, it in best], "candidates": len(scored)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ASK_ERROR", str(e), 0))

    def answer(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            qvec = self._embed_vec(question)
            best_score = 0.0
            best_item = None
            for item in self._kb:
                sim = self._cosine(qvec, item.get("vec", {}))
                if sim > best_score:
                    best_score = sim
                    best_item = item
            threshold = self.state["config"].get("threshold", 0.5)
            if best_item and best_score >= threshold:
                data = {"answer": best_item.get("answer"), "score": best_score, "matched_q": best_item.get("q")}
            else:
                data = None
            result = {"domain": "qa", "method": "answer", "data": data, "best_score": best_score}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ANSWER_ERROR", str(e), 0))

    def classify(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            labels = params.get("labels", [])
            tokens = set(self._tokenize(question))
            best_label = None
            best_score = -1
            for label in labels:
                lt = set(self._tokenize(label if isinstance(label, str) else label.get("name", "")))
                if not lt:
                    continue
                score = len(tokens & lt) / max(len(tokens | lt), 1)
                if score > best_score:
                    best_score = score
                    best_label = label if isinstance(label, str) else label.get("name")
            result = {"domain": "qa", "method": "classify", "data": {"label": best_label, "score": best_score}, "labels": labels}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def confidence(self, params=None):
        params = params or {}
        try:
            score = params.get("score", 0.0)
            threshold = self.state["config"].get("threshold", 0.5)
            conf = max(0.0, min(1.0, score))
            level = "high" if conf >= 0.75 else ("medium" if conf >= threshold else "low")
            result = {"domain": "qa", "method": "confidence", "data": {"confidence": conf, "level": level, "above_threshold": conf >= threshold}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONFIDENCE_ERROR", str(e), 0))

    def explain(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            answer = params.get("answer", "")
            qtokens = self._tokenize(question)
            atokens = self._tokenize(answer)
            overlap = set(qtokens) & set(atokens)
            result = {"domain": "qa", "method": "explain", "data": {"overlap": sorted(overlap), "q_terms": qtokens, "a_terms": atokens, "match_ratio": len(overlap) / max(len(set(qtokens)), 1)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXPLAIN_ERROR", str(e), 0))

    def fallback(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            message = params.get("message", "I cannot answer this question.")
            result = {"domain": "qa", "method": "fallback", "data": {"question": question, "fallback": message, "handled": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FALLBACK_ERROR", str(e), 0))

    def feedback(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            rating = params.get("rating", 0)
            comment = params.get("comment", "")
            entry = {"question": question, "rating": rating, "comment": comment}
            self._feedback.append(entry)
            result = {"domain": "qa", "method": "feedback", "data": entry, "total_feedback": len(self._feedback)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FEEDBACK_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            limit = params.get("limit", 10)
            entries = self._history[-limit:]
            result = {"domain": "qa", "method": "history", "data": entries, "count": len(entries), "total": len(self._history)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def route(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            rules = params.get("rules", {})
            tokens = self._tokenize(question)
            chosen = None
            for dest, keywords in rules.items():
                if any(k in tokens for k in keywords):
                    chosen = dest
                    break
            self._routes.setdefault(chosen or "default", 0)
            self._routes[chosen or "default"] += 1
            result = {"domain": "qa", "method": "route", "data": {"destination": chosen, "routes": dict(self._routes)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def score(self, params=None):
        params = params or {}
        try:
            question = params.get("question", "")
            candidate = params.get("candidate", "")
            qvec = self._embed_vec(question)
            cvec = self._embed_vec(candidate)
            sim = self._cosine(qvec, cvec)
            result = {"domain": "qa", "method": "score", "data": {"score": sim, "question": question, "candidate": candidate}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SCORE_ERROR", str(e), 0))

    def tune(self, params=None):
        params = params or {}
        try:
            weights = params.get("weights")
            threshold = params.get("threshold")
            top_k = params.get("top_k")
            if weights:
                self._weights.update(weights)
            if threshold is not None:
                self.state["config"]["threshold"] = threshold
            if top_k is not None:
                self.state["config"]["top_k"] = top_k
            result = {"domain": "qa", "method": "tune", "data": {"weights": dict(self._weights), "config": dict(self.state["config"])}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TUNE_ERROR", str(e), 0))
