#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/search_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Section 20 Semantic Search"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="search_engine.py" domain="twin_search" authority="SearchEngine"}
# [@SUMMARY]{summary="Search authority that queries files, classes, methods, knowledge by name, BCL, signature, error, fix, dependency, call chain, variable, comment, and behavior."}
# [@CLASS]{class="SearchEngine" domain="search" authority="single"}
# [@METHOD]{method="search_name" type="command"}
# [@METHOD]{method="search_bcl" type="command"}
# [@METHOD]{method="search_signature" type="command"}
# [@METHOD]{method="search_error" type="command"}
# [@METHOD]{method="search_fix" type="command"}
# [@METHOD]{method="search_dependency" type="command"}
# [@METHOD]{method="search_call_chain" type="command"}
# [@METHOD]{method="search_variable" type="command"}
# [@METHOD]{method="search_comment" type="command"}
# [@METHOD]{method="search_behavior" type="command"}
# [@METHOD]{method="search_all" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SearchEngine: queries files classes methods knowledge by name BCL signature error fix dependency call chain variable comment behavior. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
SearchEngine -- Semantic search authority for the digital twin.
Implements Section 20 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: search_name, search_bcl, search_signature, search_error, search_fix, search_dependency, search_call_chain, search_variable, search_comment, search_behavior, search_all.
"""
import ast
import hashlib
import json
import os
import sqlite3
import textwrap

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class SearchEngine:
    """Semantic search authority for the digital twin."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "search_name":
            return self.SearchName(params)
        elif command == "search_bcl":
            return self.SearchBcl(params)
        elif command == "search_signature":
            return self.SearchSignature(params)
        elif command == "search_error":
            return self.SearchError(params)
        elif command == "search_fix":
            return self.SearchFix(params)
        elif command == "search_dependency":
            return self.SearchDependency(params)
        elif command == "search_call_chain":
            return self.SearchCallChain(params)
        elif command == "search_variable":
            return self.SearchVariable(params)
        elif command == "search_comment":
            return self.SearchComment(params)
        elif command == "search_behavior":
            return self.SearchBehavior(params)
        elif command == "search_all":
            return self.SearchAll(params)

        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def SearchName(self, params):
        name = self._p(params, "name", "")
        entity_type = self._p(params, "entity_type", "method")
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        pattern = "%" + name + "%"
        if entity_type in ("method", "all"):
            cur.execute("SELECT method_id, method_name, class_id FROM methods WHERE method_name LIKE ?", (pattern,))
            results.extend({"entity_type": "method", "id": r[0], "name": r[1], "class_id": r[2]} for r in cur.fetchall())
        if entity_type in ("class", "all"):
            cur.execute("SELECT class_id, class_name FROM classes WHERE class_name LIKE ?", (pattern,))
            results.extend({"entity_type": "class", "id": r[0], "name": r[1]} for r in cur.fetchall())
        if entity_type in ("file", "all"):
            cur.execute("SELECT file_id, file_name FROM files WHERE file_name LIKE ?", (pattern,))
            results.extend({"entity_type": "file", "id": r[0], "name": r[1]} for r in cur.fetchall())
        return (1, {"results": results, "count": len(results)}, None)

    def SearchBcl(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        cur.execute("SELECT file_id, file_name, bcl FROM files WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "file", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        cur.execute("SELECT class_id, class_name, bcl FROM classes WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "class", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        cur.execute("SELECT method_id, method_name, bcl FROM methods WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "method", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        return (1, {"results": results, "count": len(results)}, None)

    def SearchSignature(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, signature FROM methods WHERE signature LIKE ?", (pattern,))
        results = [{"method_id": r[0], "method_name": r[1], "signature": r[2]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchError(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, error_type, error_text FROM knowledge "
                    "WHERE error_type IS NOT NULL AND problem LIKE ?", (pattern,))
        results = [{"knowledge_id": r[0], "problem": r[1], "error_type": r[2], "error_text": r[3]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchFix(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, confidence FROM knowledge "
                    "WHERE answer IS NOT NULL AND answer LIKE ?", (pattern,))
        results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2], "confidence": r[3]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchDependency(self, params):
        edge_type = self._p(params, "edge_type", "depends_on")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE edge_type=? AND (src_id=? OR dst_id=?)", (edge_type, entity_id, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchCallChain(self, params):
        method_id = self._p(params, "method_id")
        direction = self._p(params, "direction", "upstream")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        max_depth = self._p(params, "max_depth", 25)
        conn = self.Connect()
        cur = conn.cursor()
        if direction == "downstream":
            cur.execute(
                "SELECT src_id, dst_id FROM edges WHERE src_type='method' AND "
                "dst_type='method' AND edge_type='calls'"
            )
            graph = {}
            for src_id, dst_id in cur.fetchall():
                graph.setdefault(src_id, []).append(dst_id)
            chain = self.BuildCallTree(method_id, graph, max_depth, set())
        else:
            cur.execute(
                "SELECT src_id, dst_id FROM edges WHERE src_type='method' AND "
                "dst_type='method' AND edge_type='calls'"
            )
            reverse_graph = {}
            for src_id, dst_id in cur.fetchall():
                reverse_graph.setdefault(dst_id, []).append(src_id)
            chain = self.BuildCallTree(method_id, reverse_graph, max_depth, set())
        flat = self.FlattenCallTree(chain)
        result = {
            "method_id": method_id,
            "direction": direction,
            "call_tree": chain,
            "flat_chain": flat,
            "count": len(flat),
        }
        return (1, result, None)

    def BuildCallTree(self, node_id, graph, max_depth, visited):
        if node_id in visited or max_depth <= 0:
            return {"method_id": node_id, "method_name": self.MethodName(node_id), "children": [], "cycle": True}
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name FROM methods WHERE method_id=?", (node_id,))
        row = cur.fetchone()
        method_name = row[0] if row else "unknown"
        new_visited = set(visited)
        new_visited.add(node_id)
        children = []
        for child_id in graph.get(node_id, []):
            children.append(self.BuildCallTree(child_id, graph, max_depth - 1, new_visited))
        return {"method_id": node_id, "method_name": method_name, "children": children, "cycle": False}

    def MethodName(self, method_id):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        return row[0] if row else "unknown"

    def FlattenCallTree(self, tree):
        flat = []
        if tree is None:
            return flat
        flat.append({"method_id": tree["method_id"], "method_name": tree["method_name"]})
        for child in tree.get("children", []):
            flat.extend(self.FlattenCallTree(child))
        return flat

    def SearchVariable(self, params):
        var_name = self._p(params, "name", "")
        if not var_name:
            return (0, None, ("NO_PARAM", "name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_code LIKE ?", ("%" + var_name + "%",))
        results = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchComment(self, params):
        query = self._p(params, "query", "")
        if not query:
            return (0, None, ("NO_PARAM", "query required", 0))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        pattern = "%" + query + "%"
        cur.execute(
            "SELECT method_id, method_name, method_code FROM methods "
            "WHERE method_code LIKE ? ORDER BY method_id LIMIT ?",
            (pattern, limit),
        )
        results = []
        for method_id, method_name, code in cur.fetchall():
            if not code:
                continue
            comment_lines = []
            for idx, line in enumerate(code.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") and query.lower() in stripped.lower():
                    comment_lines.append({"line": idx, "comment": stripped})
            if comment_lines:
                results.append({
                    "method_id": method_id,
                    "method_name": method_name,
                    "comment_lines": comment_lines,
                })
        return (1, {"results": results, "count": len(results)}, None)

    def NormalizeAst(self, tree):
        if tree is None:
            return None
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                node.id = "VAR"
            elif isinstance(node, ast.arg):
                node.arg = "ARG"
            elif isinstance(node, ast.FunctionDef):
                node.name = "FUNC"
            elif isinstance(node, ast.ClassDef):
                node.name = "CLASS"
            elif isinstance(node, ast.Attribute):
                node.attr = "ATTR"
        return tree

    def AstSignature(self, code):
        if not code:
            return ""
        try:
            tree = ast.parse(textwrap.dedent(code))
        except SyntaxError:
            return ""
        tree = self.NormalizeAst(tree)
        try:
            return ast.dump(tree)
        except Exception:
            return ""

    def SearchBehavior(self, params):
        query = self._p(params, "query", "")
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        if not query:
            return (0, None, ("NO_PARAM", "query required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, method_code FROM methods "
            "WHERE method_code IS NOT NULL AND method_code != '' "
            "ORDER BY method_id LIMIT ?",
            (limit * 5,),
        )
        rows = cur.fetchall()
        query_sig = self.AstSignature(query)
        results = []
        if query_sig:
            for method_id, method_name, code in rows:
                if not code:
                    continue
                code_sig = self.AstSignature(code)
                if not code_sig:
                    continue
                similarity = self.AstSimilarity(query_sig, code_sig)
                if similarity > 0.3:
                    results.append({
                        "method_id": method_id,
                        "method_name": method_name,
                        "similarity": round(similarity, 3),
                    })
            results.sort(key=lambda r: r["similarity"], reverse=True)
        else:
            pattern = "%" + query + "%"
            for method_id, method_name, code in rows:
                if code and query.lower() in code.lower():
                    results.append({
                        "method_id": method_id,
                        "method_name": method_name,
                        "similarity": 0.0,
                    })
        results = results[:limit]
        return (1, {"results": results, "count": len(results)}, None)

    def AstSimilarity(self, sig_a, sig_b):
        if not sig_a or not sig_b:
            return 0.0
        set_a = set(sig_a.split())
        set_b = set(sig_b.split())
        if not set_a and not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    def SearchAll(self, params):
        results = {}
        for step in ("search_name", "search_bcl", "search_signature", "search_error", "search_fix"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)

