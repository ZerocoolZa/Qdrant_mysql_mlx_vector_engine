class DomKnowledge:
    """Knowledge graph store: concepts, facts, relations, rules, inference and provenance."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "concepts": {},
            "facts": {},
            "relations": [],
            "rules": [],
            "sources": {},
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
            "add_concept": self.add_concept,
            "add_fact": self.add_fact,
            "add_relation": self.add_relation,
            "confidence": self.confidence,
            "disprove": self.disprove,
            "explain": self.explain,
            "import": self.import_data,
            "infer": self.infer,
            "merge": self.merge,
            "prove": self.prove,
            "query_concept": self.query_concept,
            "query_fact": self.query_fact,
            "query_relation": self.query_relation,
            "query_rule": self.query_rule,
            "source": self.source,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def add_concept(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("MISSING_NAME", "concept name required", 0))
            cid = self._new_id()
            concept = {
                "id": cid,
                "name": name,
                "attributes": params.get("attributes", {}),
                "tags": params.get("tags", []),
            }
            self.state["concepts"][name] = concept
            self.state["catalog"].append({"type": "concept", "id": cid, "name": name})
            result = {"domain": "knowledge", "method": "add_concept", "data": concept}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_CONCEPT_ERROR", str(e), 0))

    def add_fact(self, params=None):
        params = params or {}
        try:
            subject = params.get("subject")
            predicate = params.get("predicate")
            obj = params.get("object")
            if subject is None or predicate is None or obj is None:
                return (0, None, ("MISSING_FACT", "subject, predicate, object required", 0))
            fid = self._new_id()
            fact = {
                "id": fid,
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "confidence": float(params.get("confidence", 1.0)),
                "source": params.get("source"),
            }
            self.state["facts"][fid] = fact
            self.state["catalog"].append({"type": "fact", "id": fid})
            result = {"domain": "knowledge", "method": "add_fact", "data": fact}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_FACT_ERROR", str(e), 0))

    def add_relation(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            rel = params.get("relation")
            dst = params.get("target")
            if src is None or rel is None or dst is None:
                return (0, None, ("MISSING_RELATION", "source, relation, target required", 0))
            rid = self._new_id()
            relation = {
                "id": rid,
                "source": src,
                "relation": rel,
                "target": dst,
                "weight": float(params.get("weight", 1.0)),
            }
            self.state["relations"].append(relation)
            result = {"domain": "knowledge", "method": "add_relation", "data": relation}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_RELATION_ERROR", str(e), 0))

    def confidence(self, params=None):
        params = params or {}
        try:
            fid = params.get("fact_id")
            fact = self.state["facts"].get(fid)
            if fact is None:
                return (0, None, ("FACT_NOT_FOUND", f"no fact {fid}", 0))
            conf = fact.get("confidence", 0.0)
            result = {"domain": "knowledge", "method": "confidence", "data": {"fact_id": fid, "confidence": conf}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONFIDENCE_ERROR", str(e), 0))

    def disprove(self, params=None):
        params = params or {}
        try:
            fid = params.get("fact_id")
            fact = self.state["facts"].get(fid)
            if fact is None:
                return (0, None, ("FACT_NOT_FOUND", f"no fact {fid}", 0))
            fact["confidence"] = 0.0
            fact["disproven"] = True
            result = {"domain": "knowledge", "method": "disprove", "data": fact}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISPROVE_ERROR", str(e), 0))

    def explain(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            concept = self.state["concepts"].get(name)
            if concept is None:
                return (0, None, ("CONCEPT_NOT_FOUND", f"no concept {name}", 0))
            related = [r for r in self.state["relations"] if r["source"] == name or r["target"] == name]
            facts = [f for f in self.state["facts"].values() if f["subject"] == name or f["object"] == name]
            explanation = {"concept": concept, "related_relations": related, "related_facts": facts}
            result = {"domain": "knowledge", "method": "explain", "data": explanation}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXPLAIN_ERROR", str(e), 0))

    def import_data(self, params=None):
        params = params or {}
        try:
            payload = params.get("data") or {}
            concepts = payload.get("concepts", [])
            facts = payload.get("facts", [])
            added = 0
            for c in concepts:
                ok, data, err = self.add_concept(c)
                if ok:
                    added += 1
            for f in facts:
                ok, data, err = self.add_fact(f)
                if ok:
                    added += 1
            result = {"domain": "knowledge", "method": "import", "data": {"imported": added}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def infer(self, params=None):
        params = params or {}
        try:
            inferred = []
            facts_by_subject = {}
            for f in self.state["facts"].values():
                facts_by_subject.setdefault(f["subject"], []).append(f)
            for rule in self.state["rules"]:
                cond = rule.get("if")
                cons = rule.get("then")
                if not cond or not cons:
                    continue
                matched = True
                for key, val in cond.items():
                    found = any(
                        f.get("predicate") == key and f.get("object") == val
                        for f in self.state["facts"].values()
                    )
                    if not found:
                        matched = False
                        break
                if matched:
                    inferred.append({"rule": rule.get("name"), "then": cons})
            result = {"domain": "knowledge", "method": "infer", "data": {"inferred": inferred}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INFER_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            names = params.get("concepts") or []
            if len(names) < 2:
                return (0, None, ("MERGE_NEEDS_TWO", "at least two concepts required", 0))
            primary = names[0]
            primary_concept = self.state["concepts"].get(primary)
            if primary_concept is None:
                return (0, None, ("CONCEPT_NOT_FOUND", f"no concept {primary}", 0))
            merged = []
            for name in names[1:]:
                other = self.state["concepts"].pop(name, None)
                if other:
                    primary_concept["attributes"].update(other.get("attributes", {}))
                    primary_concept["tags"] = list(set(primary_concept["tags"] + other.get("tags", [])))
                    merged.append(name)
            result = {"domain": "knowledge", "method": "merge", "data": {"primary": primary, "merged": merged}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def prove(self, params=None):
        params = params or {}
        try:
            fid = params.get("fact_id")
            evidence = params.get("evidence", [])
            fact = self.state["facts"].get(fid)
            if fact is None:
                return (0, None, ("FACT_NOT_FOUND", f"no fact {fid}", 0))
            fact["confidence"] = 1.0
            fact["disproven"] = False
            fact["evidence"] = evidence
            result = {"domain": "knowledge", "method": "prove", "data": fact}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PROVE_ERROR", str(e), 0))

    def query_concept(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if name:
                concept = self.state["concepts"].get(name)
                data = concept if concept else {}
            else:
                data = list(self.state["concepts"].values())
            result = {"domain": "knowledge", "method": "query_concept", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUERY_CONCEPT_ERROR", str(e), 0))

    def query_fact(self, params=None):
        params = params or {}
        try:
            subject = params.get("subject")
            predicate = params.get("predicate")
            facts = list(self.state["facts"].values())
            if subject is not None:
                facts = [f for f in facts if f["subject"] == subject]
            if predicate is not None:
                facts = [f for f in facts if f["predicate"] == predicate]
            result = {"domain": "knowledge", "method": "query_fact", "data": facts}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUERY_FACT_ERROR", str(e), 0))

    def query_relation(self, params=None):
        params = params or {}
        try:
            src = params.get("source")
            rel = params.get("relation")
            relations = list(self.state["relations"])
            if src is not None:
                relations = [r for r in relations if r["source"] == src]
            if rel is not None:
                relations = [r for r in relations if r["relation"] == rel]
            result = {"domain": "knowledge", "method": "query_relation", "data": relations}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUERY_RELATION_ERROR", str(e), 0))

    def query_rule(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if name:
                rules = [r for r in self.state["rules"] if r.get("name") == name]
            else:
                rules = list(self.state["rules"])
            result = {"domain": "knowledge", "method": "query_rule", "data": rules}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUERY_RULE_ERROR", str(e), 0))

    def source(self, params=None):
        params = params or {}
        try:
            sid = params.get("source_id")
            if sid is None:
                data = list(self.state["sources"].values())
            else:
                data = self.state["sources"].get(sid, {})
            result = {"domain": "knowledge", "method": "source", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SOURCE_ERROR", str(e), 0))
