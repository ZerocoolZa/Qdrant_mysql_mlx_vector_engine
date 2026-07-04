import re


class DomAi:
    """AI domain: text classification, generation, memory, reasoning, and scoring using stdlib."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memory": {}, "patterns": {}}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command == "classify":
            return self.classify(params)
        if command == "complete":
            return self.complete(params)
        if command == "embed":
            return self.embed(params)
        if command == "forget":
            return self.forget(params)
        if command == "generate":
            return self.generate(params)
        if command == "learn":
            return self.learn(params)
        if command == "plan":
            return self.plan(params)
        if command == "prompt":
            return self.prompt(params)
        if command == "reason":
            return self.reason(params)
        if command == "reflect":
            return self.reflect(params)
        if command == "remember":
            return self.remember(params)
        if command == "score":
            return self.score(params)
        if command == "summarize":
            return self.summarize(params)
        if command == "translate":
            return self.translate(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def classify(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", "")).lower()
            categories = params.get("categories") or {}
            if not isinstance(categories, dict) or not categories:
                categories = {
                    "question": ["what", "why", "how", "when", "where", "?"],
                    "command": ["do", "run", "create", "delete", "update", "build"],
                    "statement": ["is", "are", "was", "were", "the", "a"],
                }
            scores = {}
            tokens = re.findall(r"[a-z0-9]+", text)
            for cat, keywords in categories.items():
                scores[cat] = sum(1 for kw in keywords if kw in tokens or kw in text)
            best = max(scores, key=lambda k: scores[k]) if scores else "unknown"
            result = {"domain": "ai", "method": "classify", "text": params.get("text", ""), "category": best, "scores": scores}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def complete(self, params=None):
        params = params or {}
        try:
            seed = str(params.get("seed", ""))
            corpus = params.get("corpus") or []
            if not corpus:
                corpus = self.state.get("catalog", [])
            suffixes = [str(c) for c in corpus if str(c).startswith(seed)]
            completion = suffixes[0][len(seed):] if suffixes else ""
            result = {"domain": "ai", "method": "complete", "seed": seed, "completion": completion, "candidates": len(suffixes)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPLETE_ERROR", str(e), 0))

    def embed(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            vocab = sorted(set(tokens))
            vector = [tokens.count(w) for w in vocab]
            result = {"domain": "ai", "method": "embed", "text": text, "vocab": vocab, "vector": vector, "dim": len(vocab)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EMBED_ERROR", str(e), 0))

    def forget(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            removed = False
            if key is not None and key in self.state["memory"]:
                del self.state["memory"][key]
                removed = True
            result = {"domain": "ai", "method": "forget", "key": key, "removed": removed, "remaining": len(self.state["memory"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORGET_ERROR", str(e), 0))

    def generate(self, params=None):
        params = params or {}
        try:
            template = str(params.get("template", ""))
            values = params.get("values") or {}
            output = template
            for k, v in values.items():
                output = output.replace("{" + str(k) + "}", str(v))
            result = {"domain": "ai", "method": "generate", "template": template, "output": output}
            self.state["results"].append(result)
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GENERATE_ERROR", str(e), 0))

    def learn(self, params=None):
        params = params or {}
        try:
            pattern = str(params.get("pattern", ""))
            response = params.get("response", "")
            self.state["patterns"][pattern] = response
            result = {"domain": "ai", "method": "learn", "pattern": pattern, "response": response, "total_patterns": len(self.state["patterns"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LEARN_ERROR", str(e), 0))

    def plan(self, params=None):
        params = params or {}
        try:
            goal = str(params.get("goal", ""))
            steps = params.get("steps") or []
            if not steps:
                steps = [f"analyze: {goal}", f"design: {goal}", f"implement: {goal}", f"verify: {goal}"]
            result = {"domain": "ai", "method": "plan", "goal": goal, "steps": steps, "step_count": len(steps)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PLAN_ERROR", str(e), 0))

    def prompt(self, params=None):
        params = params or {}
        try:
            role = str(params.get("role", "assistant"))
            task = str(params.get("task", ""))
            context = params.get("context", "")
            template = params.get("template", "You are {role}. Task: {task}. Context: {context}")
            text = template.replace("{role}", role).replace("{task}", task).replace("{context}", str(context))
            result = {"domain": "ai", "method": "prompt", "role": role, "task": task, "prompt": text}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROMPT_ERROR", str(e), 0))

    def reason(self, params=None):
        params = params or {}
        try:
            facts = params.get("facts") or []
            rules = params.get("rules") or []
            derived = []
            for rule in rules:
                if isinstance(rule, dict) and "if" in rule and "then" in rule:
                    condition = rule["if"]
                    if isinstance(condition, dict):
                        if all(condition.get(k, False) == v for k, v in condition.items()):
                            derived.append(rule["then"])
                    elif condition in facts:
                        derived.append(rule["then"])
            result = {"domain": "ai", "method": "reason", "facts": facts, "derived": derived, "rule_count": len(rules)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REASON_ERROR", str(e), 0))

    def reflect(self, params=None):
        params = params or {}
        try:
            memory_count = len(self.state["memory"])
            pattern_count = len(self.state["patterns"])
            result_count = len(self.state["results"])
            summary = f"memory={memory_count} patterns={pattern_count} results={result_count}"
            result = {"domain": "ai", "method": "reflect", "summary": summary, "memory_count": memory_count, "pattern_count": pattern_count, "result_count": result_count}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REFLECT_ERROR", str(e), 0))

    def remember(self, params=None):
        params = params or {}
        try:
            key = params.get("key", str(len(self.state["memory"])))
            value = params.get("value")
            self.state["memory"][key] = value
            result = {"domain": "ai", "method": "remember", "key": key, "stored": True, "total": len(self.state["memory"])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REMEMBER_ERROR", str(e), 0))

    def score(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            criteria = params.get("criteria") or {"length": 1.0, "keywords": 1.0}
            length_score = min(len(text) / 100.0, 1.0) * criteria.get("length", 1.0)
            keywords = params.get("keywords") or []
            kw_score = (sum(1 for k in keywords if k in text) / max(len(keywords), 1)) * criteria.get("keywords", 1.0)
            total = (length_score + kw_score) / 2.0
            result = {"domain": "ai", "method": "score", "text": text, "length_score": length_score, "keyword_score": kw_score, "total": total}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SCORE_ERROR", str(e), 0))

    def summarize(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            max_sentences = int(params.get("max_sentences", 3))
            scored = sorted(sentences, key=lambda s: len(s), reverse=True)
            summary = ". ".join(scored[:max_sentences])
            result = {"domain": "ai", "method": "summarize", "original_length": len(text), "summary": summary, "sentence_count": len(scored[:max_sentences])}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SUMMARIZE_ERROR", str(e), 0))

    def translate(self, params=None):
        params = params or {}
        try:
            text = str(params.get("text", ""))
            dictionary = params.get("dictionary") or {}
            words = text.split()
            translated = [dictionary.get(w, w) for w in words]
            result = {"domain": "ai", "method": "translate", "text": text, "translated": " ".join(translated), "dict_size": len(dictionary)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRANSLATE_ERROR", str(e), 0))
