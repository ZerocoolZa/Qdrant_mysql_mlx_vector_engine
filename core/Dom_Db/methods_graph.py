#!/usr/bin/env python3
"""
Methods Graph Engine — multiple graphs from one methods table.

Each method is a node. Each graph type creates different edges.

Graph types:
  1. Call Graph       — method A calls method B
  2. Similarity Graph — methods with same name in different classes
  3. API Graph        — methods sharing the same library calls
  4. Complexity Graph — methods with similar complexity profile
  5. Class Graph      — methods grouped by owning class
  6. Pattern Graph    — methods with same call signature shape
  7. Compose Graph    — method A's output could feed method B's input

The engine explores "what could exist" by finding compatible building blocks.
"""

import sqlite3
import json
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class MethodsGraph:

    def __init__(self, db_path: str = "/tmp/methods.sqlite"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.methods: List[dict] = []
        self.by_name: Dict[str, List[dict]] = defaultdict(list)
        self.by_class: Dict[str, List[dict]] = defaultdict(list)
        self.by_qualname: Dict[str, dict] = {}
        self._load()

    def _load(self):
        rows = self.conn.execute("SELECT * FROM ci_methods").fetchall()
        self.methods = [dict(r) for r in rows]
        for m in self.methods:
            self.by_name[m["name"]].append(m)
            self.by_class[m["class_name"]].append(m)
            self.by_qualname[m["qualname"]] = m

    def close(self):
        self.conn.close()

    # -----------------------------------------------------------------------
    # GRAPH 1: CALL GRAPH — who calls whom
    # -----------------------------------------------------------------------

    def call_graph(self) -> List[dict]:
        """Edge: method A calls method B (by name match)."""
        edges = []
        all_names = set(self.by_name.keys())
        for m in self.methods:
            calls = [c.strip() for c in (m["call_names"] or "").split(",") if c.strip()]
            for called_name in calls:
                if called_name in all_names:
                    for target in self.by_name[called_name]:
                        if target["qualname"] != m["qualname"]:
                            edges.append({
                                "source": m["qualname"],
                                "target": target["qualname"],
                                "source_class": m["class_name"],
                                "target_class": target["class_name"],
                                "type": "calls",
                            })
        return edges

    # -----------------------------------------------------------------------
    # GRAPH 2: SIMILARITY GRAPH — same method name, different class
    # -----------------------------------------------------------------------

    def similarity_graph(self, min_classes: int = 2) -> List[dict]:
        """Edge: methods with same name in different classes (pattern/interface)."""
        edges = []
        for name, methods in self.by_name.items():
            if len(methods) < min_classes:
                continue
            classes = list(set(m["class_name"] for m in methods))
            for i in range(len(classes)):
                for j in range(i + 1, len(classes)):
                    a = next(m for m in methods if m["class_name"] == classes[i])
                    b = next(m for m in methods if m["class_name"] == classes[j])
                    edges.append({
                        "source": a["qualname"],
                        "target": b["qualname"],
                        "source_class": classes[i],
                        "target_class": classes[j],
                        "shared_name": name,
                        "type": "similar_name",
                    })
        return edges

    # -----------------------------------------------------------------------
    # GRAPH 3: API GRAPH — methods sharing library calls
    # -----------------------------------------------------------------------

    def api_graph(self) -> List[dict]:
        """Edge: methods that call the same external APIs."""
        api_calls: Dict[str, List[dict]] = defaultdict(list)
        known_apis = {
            "sqlite3", "connect", "execute", "commit", "cursor", "fetchall", "fetchone",
            "requests", "get", "post", "put", "delete",
            "open", "read", "write", "close",
            "print", "input",
            "QFont", "QPushButton", "QLabel", "QLineEdit", "QTextEdit", "QSplitter",
            "QVBoxLayout", "QHBoxLayout", "QGridLayout", "QWidget", "QMainWindow",
            "QTimer", "QThread", "QSignal",
            "json", "loads", "dumps", "load", "dump",
            "os", "path", "walk", "listdir", "mkdir", "remove", "exists",
            "subprocess", "Popen", "run",
            "ast", "parse", "walk", "dump",
            "hashlib", "md5", "sha256",
            "time", "sleep", "time",
            "threading", "Thread", "Lock",
            "re", "search", "match", "findall", "sub", "compile",
            "defaultdict", "deque", "Counter",
            "enumerate", "range", "zip", "map", "filter", "sorted", "reversed",
            "min", "max", "sum", "abs", "len", "str", "int", "float", "list", "dict", "set", "tuple", "bool",
            "isinstance", "issubclass", "hasattr", "getattr", "setattr", "type",
            "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
            "exec", "eval",
        }
        for m in self.methods:
            calls = set(c.strip() for c in (m["call_names"] or "").split(",") if c.strip())
            apis = calls & known_apis
            for api in apis:
                api_calls[api].append(m)

        edges = []
        for api, methods in api_calls.items():
            if len(methods) < 2:
                continue
            for i in range(len(methods)):
                for j in range(i + 1, min(len(methods), i + 20)):
                    if methods[i]["qualname"] != methods[j]["qualname"]:
                        edges.append({
                            "source": methods[i]["qualname"],
                            "target": methods[j]["qualname"],
                            "shared_api": api,
                            "type": "shared_api",
                        })
        return edges

    # -----------------------------------------------------------------------
    # GRAPH 4: COMPLEXITY GRAPH — methods with similar complexity profile
    # -----------------------------------------------------------------------

    def complexity_graph(self) -> List[dict]:
        """Edge: methods with similar complexity (within 2) and similar body size (within 20%)."""
        edges = []
        methods = sorted(self.methods, key=lambda m: m["cyclomatic"])
        for i, a in enumerate(methods):
            for j in range(i + 1, min(len(methods), i + 50)):
                b = methods[j]
                if abs(a["cyclomatic"] - b["cyclomatic"]) > 2:
                    break
                if a["qualname"] == b["qualname"]:
                    continue
                size_diff = abs(a["body_lines"] - b["body_lines"])
                if size_diff <= max(a["body_lines"], b["body_lines"]) * 0.2:
                    edges.append({
                        "source": a["qualname"],
                        "target": b["qualname"],
                        "cx_a": a["cyclomatic"],
                        "cx_b": b["cyclomatic"],
                        "type": "similar_complexity",
                    })
        return edges

    # -----------------------------------------------------------------------
    # GRAPH 5: COMPOSE GRAPH — method A's return could feed method B's args
    # -----------------------------------------------------------------------

    def compose_graph(self) -> List[dict]:
        """
        Edge: method A returns something, method B takes args that might match.
        Heuristic: A has returns_annotation, B has arg_names that overlap.
        Also: A's call_names produce things B's arg_names consume.
        """
        edges = []
        producers = [m for m in self.methods if m["returns"] and m["returns"] != "None"]
        consumers = self.methods

        for a in producers:
            ret = a["returns"].lower()
            for b in consumers:
                if a["qualname"] == b["qualname"]:
                    continue
                args = (b["arg_names"] or "").lower()
                if not args:
                    continue
                # Check if return type appears in arg names
                if ret in args or any(w in args for w in ret.split(".")):
                    edges.append({
                        "source": a["qualname"],
                        "target": b["qualname"],
                        "returns": a["returns"],
                        "args": b["arg_names"],
                        "type": "compose_candidate",
                    })
                    if len(edges) > 5000:
                        return edges
        return edges

    # -----------------------------------------------------------------------
    # GRAPH 6: CLASS GRAPH — classes connected by method calls
    # -----------------------------------------------------------------------

    def class_graph(self) -> List[dict]:
        """Edge: class A's method calls class B's method."""
        edges = []
        all_names = set(self.by_name.keys())
        class_edges: Dict[Tuple[str, str], int] = defaultdict(int)

        for m in self.methods:
            calls = [c.strip() for c in (m["call_names"] or "").split(",") if c.strip()]
            for called_name in calls:
                if called_name in all_names:
                    for target in self.by_name[called_name]:
                        if target["class_name"] != m["class_name"]:
                            key = (m["class_name"], target["class_name"])
                            class_edges[key] += 1

        for (src_cls, dst_cls), weight in class_edges.items():
            edges.append({
                "source": src_cls,
                "target": dst_cls,
                "weight": weight,
                "type": "class_calls",
            })
        return edges

    # -----------------------------------------------------------------------
    # EXPLORATION: "what could exist" — find composable chains
    # -----------------------------------------------------------------------

    def find_chains(self, start_name: str, depth: int = 3, limit: int = 20) -> List[List[str]]:
        """Find call chains starting from a method name."""
        chains = []
        all_names = set(self.by_name.keys())

        def dfs(qualname: str, chain: List[str], visited: Set[str]):
            if len(chain) >= depth or len(chains) >= limit:
                return
            m = self.by_qualname.get(qualname)
            if not m:
                return
            calls = [c.strip() for c in (m["call_names"] or "").split(",") if c.strip()]
            for called_name in calls:
                if called_name in all_names:
                    for target in self.by_name[called_name]:
                        tq = target["qualname"]
                        if tq not in visited:
                            new_chain = chain + [tq]
                            chains.append(new_chain)
                            dfs(tq, new_chain, visited | {tq})

        for m in self.by_name.get(start_name, []):
            dfs(m["qualname"], [m["qualname"]], {m["qualname"]})

        return chains[:limit]

    def find_compatible(self, method_name: str) -> List[dict]:
        """
        Find methods that could compose with this one.
        - Methods whose args match this method's return type
        - Methods whose calls overlap with this method's calls
        - Methods in classes that this method's class calls
        """
        target = self.by_qualname.get(method_name)
        if not target:
            # try by name
            methods = self.by_name.get(method_name, [])
            if methods:
                target = methods[0]
        if not target:
            return []

        results = []
        ret = (target["returns"] or "").lower()
        target_calls = set(c.strip() for c in (target["call_names"] or "").split(",") if c.strip())

        for m in self.methods:
            if m["qualname"] == target["qualname"]:
                continue
            score = 0
            reasons = []

            # Return type matches arg
            if ret and ret != "none":
                args = (m["arg_names"] or "").lower()
                if ret in args:
                    score += 3
                    reasons.append("return_feeds_arg")

            # Shared calls
            m_calls = set(c.strip() for c in (m["call_names"] or "").split(",") if c.strip())
            shared = target_calls & m_calls
            if shared:
                score += len(shared)
                reasons.append(f"shared_calls:{len(shared)}")

            # Same name pattern
            if m["name"] == target["name"] and m["class_name"] != target["class_name"]:
                score += 2
                reasons.append("same_name_diff_class")

            # Complementary complexity
            if abs(m["cyclomatic"] - target["cyclomatic"]) <= 2 and m["qualname"] != target["qualname"]:
                score += 1
                reasons.append("similar_complexity")

            if score > 0:
                results.append({
                    "qualname": m["qualname"],
                    "class": m["class_name"],
                    "score": score,
                    "reasons": reasons,
                    "cx": m["cyclomatic"],
                    "args": m["arg_names"],
                    "returns": m["returns"],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:30]

    def stats(self) -> dict:
        return {
            "total_methods": len(self.methods),
            "total_classes": len(self.by_class),
            "total_names": len(self.by_name),
            "methods_with_calls": sum(1 for m in self.methods if m["call_count"] > 0),
            "recursive": sum(1 for m in self.methods if m["recursive"]),
            "documented": sum(1 for m in self.methods if m["has_docstring"]),
            "god_methods": sum(1 for m in self.methods if m["cyclomatic"] > 10),
        }


if __name__ == "__main__":
    g = MethodsGraph()

    print("=== METHODS GRAPH ENGINE ===")
    stats = g.stats()
    for k, v in stats.items():
        print(f"  {k:25s} {v}")

    print("\n=== GRAPH 1: CALL GRAPH ===")
    cg = g.call_graph()
    print(f"  Edges: {len(cg)}")
    print(f"  Sample: {cg[:3]}")

    print("\n=== GRAPH 2: SIMILARITY GRAPH (same name, diff class) ===")
    sg = g.similarity_graph(min_classes=2)
    print(f"  Edges: {len(sg)}")
    print(f"  Sample: {sg[:3]}")

    print("\n=== GRAPH 3: API GRAPH (shared library calls) ===")
    ag = g.api_graph()
    print(f"  Edges: {len(ag)}")
    print(f"  Sample: {ag[:3]}")

    print("\n=== GRAPH 4: COMPLEXITY GRAPH ===")
    cxg = g.complexity_graph()
    print(f"  Edges: {len(cxg)}")
    print(f"  Sample: {cxg[:3]}")

    print("\n=== GRAPH 5: COMPOSE GRAPH (return feeds args) ===")
    compg = g.compose_graph()
    print(f"  Edges: {len(compg)}")
    print(f"  Sample: {compg[:3]}")

    print("\n=== GRAPH 6: CLASS GRAPH ===")
    clsg = g.class_graph()
    print(f"  Edges: {len(clsg)}")
    print(f"  Top connections:")
    for e in sorted(clsg, key=lambda x: x["weight"], reverse=True)[:10]:
        print(f"    {e['source']:25s} -> {e['target']:25s} ({e['weight']} calls)")

    print("\n=== EXPLORE: call chains from 'Run' ===")
    chains = g.find_chains("Run", depth=4, limit=10)
    for chain in chains[:5]:
        print(f"  {' -> '.join(chain)}")

    print("\n=== EXPLORE: compatible methods for 'Run' ===")
    compat = g.find_compatible("Run")
    for c in compat[:10]:
        print(f"  score={c['score']:2d} {c['qualname']:40s} reasons={c['reasons']}")

    print("\n=== EXPLORE: compatible methods for 'Scan' ===")
    compat = g.find_compatible("Scan")
    for c in compat[:10]:
        print(f"  score={c['score']:2d} {c['qualname']:40s} reasons={c['reasons']}")

    g.close()
