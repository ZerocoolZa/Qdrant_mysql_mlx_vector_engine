#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/optimization_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 38: Optimization Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="optimization_engine.py" domain="twin_optimization" authority="OptimizationEngine"}
# [@SUMMARY]{summary="Optimization authority: optimize imports, optimize complexity, optimize dependencies, optimize structure, optimize VBStyle, optimize knowledge, optimize graph, optimize queries, optimize storage, optimization report."}
# [@CLASS]{class="OptimizationEngine" domain="optimization" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="optimize_imports" type="command"}
# [@METHOD]{method="optimize_complexity" type="command"}
# [@METHOD]{method="optimize_dependencies" type="command"}
# [@METHOD]{method="optimize_structure" type="command"}
# [@METHOD]{method="optimize_vbstyle" type="command"}
# [@METHOD]{method="optimize_knowledge" type="command"}
# [@METHOD]{method="optimize_graph" type="command"}
# [@METHOD]{method="optimize_queries" type="command"}
# [@METHOD]{method="optimize_storage" type="command"}
# [@METHOD]{method="optimization_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class OptimizationEngine:
    """Authority for suggesting and applying optimizations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
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
        if command == "optimize_imports":
            return self.OptimizeImports(params)
        elif command == "optimize_complexity":
            return self.OptimizeComplexity(params)
        elif command == "optimize_dependencies":
            return self.OptimizeDependencies(params)
        elif command == "optimize_structure":
            return self.OptimizeStructure(params)
        elif command == "optimize_vbstyle":
            return self.OptimizeVbstyle(params)
        elif command == "optimize_knowledge":
            return self.OptimizeKnowledge(params)
        elif command == "optimize_graph":
            return self.OptimizeGraph(params)
        elif command == "optimize_queries":
            return self.OptimizeQueries(params)
        elif command == "optimize_storage":
            return self.OptimizeStorage(params)
        elif command == "optimization_report":
            return self.OptimizationReport(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def OptimizeImports(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, imports FROM files WHERE imports IS NOT NULL AND imports != '[]'")
        suggestions = []
        for row in cur.fetchall():
            imports = json.loads(row[2]) if row[2] else []
            unique = list(set(imports))
            if len(unique) < len(imports):
                suggestions.append({"file_id": row[0], "file_name": row[1],
                                    "issue": "duplicate_imports",
                                    "before": len(imports),
                                    "after": len(unique)})
        return (1, {"suggestions": suggestions[:100],
                    "count": len(suggestions)}, None)

    def OptimizeComplexity(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, cyclomatic_complexity, line_count "
            "FROM methods WHERE cyclomatic_complexity >= 10 "
            "ORDER BY cyclomatic_complexity DESC LIMIT 50"
        )
        suggestions = [{"method_id": r[0], "method_name": r[1],
                        "complexity": r[2], "lines": r[3],
                        "suggestion": "split_method"}
                       for r in cur.fetchall()]
        return (1, {"suggestions": suggestions, "count": len(suggestions)}, None)

    def OptimizeDependencies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT dst_type, dst_id, COUNT(*) AS incoming FROM edges "
            "GROUP BY dst_type, dst_id HAVING incoming > 15"
        )
        suggestions = [{"type": r[0], "id": r[1], "incoming": r[2],
                        "suggestion": "reduce_coupling"}
                       for r in cur.fetchall()]
        return (1, {"suggestions": suggestions[:100],
                    "count": len(suggestions)}, None)

    def OptimizeStructure(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE method_count > 30")
        suggestions = [{"class_id": r[0], "class_name": r[1],
                        "method_count": r[2],
                        "suggestion": "split_class"}
                       for r in cur.fetchall()]
        return (1, {"suggestions": suggestions[:100],
                    "count": len(suggestions)}, None)

    def OptimizeVbstyle(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name, has_print, has_decorator, "
            "has_self_underscore, returns_tuple3 FROM methods WHERE "
            "has_print=1 OR has_decorator=1 OR has_self_underscore=1 OR returns_tuple3=0"
        )
        suggestions = []
        for row in cur.fetchall():
            fixes = []
            if row[2]:
                fixes.append("remove_print")
            if row[3]:
                fixes.append("remove_decorator")
            if row[4]:
                fixes.append("rename_self_underscore")
            if not row[5]:
                fixes.append("return_tuple3")
            suggestions.append({"method_id": row[0], "method_name": row[1],
                                "fixes": fixes})
        return (1, {"suggestions": suggestions[:100],
                    "count": len(suggestions)}, None)

    def OptimizeKnowledge(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT AVG(confidence) FROM knowledge")
        avg = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE confidence < 30")
        low = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NULL OR answer = ''")
        no_fix = cur.fetchone()[0]
        suggestions = []
        if avg < 50:
            suggestions.append({"issue": "low_avg_confidence", "value": round(avg, 1),
                                "suggestion": "verify_and_boost_confidence"})
        if low > 0:
            suggestions.append({"issue": "low_confidence_entries", "count": low,
                                "suggestion": "review_low_confidence"})
        if no_fix > 0:
            suggestions.append({"issue": "missing_fixes", "count": no_fix,
                                "suggestion": "add_fixes"})
        return (1, {"avg_confidence": round(avg, 1), "low_confidence": low,
                    "missing_fixes": no_fix,
                    "suggestions": suggestions}, None)

    def OptimizeGraph(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT edge_type) FROM edges")
        types = cur.fetchone()[0]
        cur.execute("SELECT AVG(confidence) FROM edges")
        avg_conf = cur.fetchone()[0] or 0
        suggestions = []
        if avg_conf < 70:
            suggestions.append({"issue": "low_edge_confidence",
                                "value": round(avg_conf, 1),
                                "suggestion": "verify_edges"})
        return (1, {"total_edges": total, "edge_types": types,
                    "avg_confidence": round(avg_conf, 1),
                    "suggestions": suggestions}, None)

    def OptimizeQueries(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        suggestions = []
        for table in tables:
            if not any(table in idx for idx in indexes):
                suggestions.append({"table": table,
                                    "suggestion": "add_index"})
        return (1, {"existing_indexes": len(indexes),
                    "tables": len(tables),
                    "suggestions": suggestions[:50]}, None)

    def OptimizeStorage(self, params):
        db_path = self.state["config"]["db_path"]
        if not os.path.isfile(db_path):
            return (0, None, ("DB_NOT_FOUND", db_path, 0))
        size = os.path.getsize(db_path)
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        suggestions = []
        if size > 100 * 1024 * 1024:
            suggestions.append({"issue": "large_db", "size_mb": round(size / 1024 / 1024, 1),
                                "suggestion": "vacuum_or_archive"})
        return (1, {"db_size": size, "db_size_mb": round(size / 1024 / 1024, 1),
                    "integrity": integrity,
                    "suggestions": suggestions}, None)

    def OptimizationReport(self, params):
        results = {}
        total_suggestions = 0
        for step in ("optimize_imports", "optimize_complexity",
                     "optimize_dependencies", "optimize_structure",
                     "optimize_vbstyle", "optimize_knowledge",
                     "optimize_graph", "optimize_queries", "optimize_storage"):
            res = self.Run(step, params)
            if res[0] == 1:
                results[step] = res[1]
                count = res[1].get("count", len(res[1].get("suggestions", [])))
                total_suggestions += count
            else:
                results[step] = {"error": str(res[2])}
        results["total_suggestions"] = total_suggestions
        results["generated"] = self.Now()[1]
        return (1, results, None)
