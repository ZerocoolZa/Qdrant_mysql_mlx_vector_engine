#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/reporting_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 15: Reporting -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="reporting_engine.py" domain="twin_reporting" authority="ReportingEngine"}
# [@SUMMARY]{summary="Reporting authority: error timeline, fix timeline, dependency report, duplicate report, complexity report, BCL coverage, graph coverage, method coverage, test coverage, health score."}
# [@CLASS]{class="ReportingEngine" domain="reporting" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="error_timeline" type="command"}
# [@METHOD]{method="fix_timeline" type="command"}
# [@METHOD]{method="dependency_report" type="command"}
# [@METHOD]{method="duplicate_report" type="command"}
# [@METHOD]{method="complexity_report" type="command"}
# [@METHOD]{method="bcl_coverage" type="command"}
# [@METHOD]{method="graph_coverage" type="command"}
# [@METHOD]{method="method_coverage" type="command"}
# [@METHOD]{method="test_coverage" type="command"}
# [@METHOD]{method="health_score" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ReportingEngine:
    """Authority for generating reports across all twin domains."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "export_dir": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "reports"
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
        if command == "error_timeline":
            return self.ErrorTimeline(params)
        elif command == "fix_timeline":
            return self.FixTimeline(params)
        elif command == "dependency_report":
            return self.DependencyReport(params)
        elif command == "duplicate_report":
            return self.DuplicateReport(params)
        elif command == "complexity_report":
            return self.ComplexityReport(params)
        elif command == "bcl_coverage":
            return self.BclCoverage(params)
        elif command == "graph_coverage":
            return self.GraphCoverage(params)
        elif command == "method_coverage":
            return self.MethodCoverage(params)
        elif command == "test_coverage":
            return self.TestCoverage(params)
        elif command == "health_score":
            return self.HealthScore(params)
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

    def ErrorTimeline(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        limit = self._p(params, "limit", 100)
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, error_type, problem, created "
                "FROM knowledge WHERE error_type IS NOT NULL "
                "ORDER BY created DESC LIMIT ?", (limit,)
            )
            entries = []
            for row in cur.fetchall():
                entries.append({
                    "knowledge_id": row[0], "method_id": row[1],
                    "error_type": row[2], "problem": row[3],
                    "created": row[4],
                })
            cur.execute(
                "SELECT error_type, COUNT(*) FROM knowledge "
                "WHERE error_type IS NOT NULL GROUP BY error_type "
                "ORDER BY COUNT(*) DESC"
            )
            by_type = {r[0]: r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": entries, "by_type": by_type,
                    "total": len(entries)}, None)

    def FixTimeline(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        limit = self._p(params, "limit", 100)
        try:
            cur.execute(
                "SELECT attempt_id, method_id, action, knowledge_id, created "
                "FROM attempts WHERE action IN ('fix_applied', 'patch', "
                "'before_after') ORDER BY created DESC LIMIT ?", (limit,)
            )
            entries = []
            for row in cur.fetchall():
                entries.append({
                    "attempt_id": row[0], "method_id": row[1],
                    "action": row[2], "knowledge_id": row[3],
                    "created": row[4],
                })
            cur.execute(
                "SELECT action, COUNT(*) FROM attempts "
                "WHERE action IN ('fix_applied', 'patch', 'before_after') "
                "GROUP BY action"
            )
            by_action = {r[0]: r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"timeline": entries, "by_action": by_action,
                    "total": len(entries)}, None)

    def DependencyReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type "
                "ORDER BY COUNT(*) DESC"
            )
            by_type = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM edges")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT src_type, dst_type, COUNT(*) FROM edges "
                "GROUP BY src_type, dst_type ORDER BY COUNT(*) DESC LIMIT 20"
            )
            top_pairs = [{"src": r[0], "dst": r[1], "count": r[2]}
                         for r in cur.fetchall()]
            cur.execute(
                "SELECT file_path, COUNT(*) as dep_count FROM files "
                "INNER JOIN edges ON files.file_id = edges.src_id "
                "WHERE edges.src_type='file' GROUP BY file_path "
                "ORDER BY dep_count DESC LIMIT 10"
            )
            most_deps = [{"file": r[0], "dependencies": r[1]}
                         for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total_edges": total, "by_type": by_type,
                    "top_pairs": top_pairs, "most_dependent_files": most_deps}, None)

    def DuplicateReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT hash, COUNT(*) as cnt FROM methods "
                "WHERE hash IS NOT NULL GROUP BY hash HAVING cnt > 1 "
                "ORDER BY cnt DESC"
            )
            dup_hashes = cur.fetchall()
            duplicates = []
            for dhash, cnt in dup_hashes:
                cur.execute(
                    "SELECT method_id, method_name, file_id FROM methods "
                    "WHERE hash=?", (dhash,)
                )
                methods = [{"method_id": r[0], "method_name": r[1],
                            "file_id": r[2]} for r in cur.fetchall()]
                duplicates.append({"hash": dhash, "count": cnt,
                                   "methods": methods})
            cur.execute(
                "SELECT class_name, COUNT(*) as cnt FROM classes "
                "GROUP BY class_name HAVING cnt > 1 ORDER BY cnt DESC"
            )
            dup_classes = [{"class_name": r[0], "count": r[1]}
                           for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"duplicate_methods": duplicates,
                    "duplicate_method_groups": len(duplicates),
                    "duplicate_classes": dup_classes,
                    "total_duplicate_classes": len(dup_classes)}, None)

    def ComplexityReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
            avg_cc = cur.fetchone()[0] or 0
            cur.execute("SELECT MAX(cyclomatic_complexity) FROM methods")
            max_cc = cur.fetchone()[0] or 0
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10"
            )
            high = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 20"
            )
            very_high = cur.fetchone()[0]
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity "
                "FROM methods WHERE cyclomatic_complexity >= 10 "
                "ORDER BY cyclomatic_complexity DESC LIMIT 20"
            )
            top_complex = [{"method_id": r[0], "method_name": r[1],
                            "complexity": r[2]} for r in cur.fetchall()]
            cur.execute(
                "SELECT AVG(nesting_depth) FROM methods"
            )
            avg_nesting = cur.fetchone()[0] or 0
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"avg_complexity": round(avg_cc, 2),
                    "max_complexity": max_cc,
                    "high_complexity_count": high,
                    "very_high_complexity_count": very_high,
                    "avg_nesting": round(avg_nesting, 2),
                    "top_complex_methods": top_complex}, None)

    def BclCoverage(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE bcl IS NOT NULL AND bcl != ''")
            with_bcl = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE bcl IS NOT NULL AND bcl != ''")
            methods_with_bcl = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files WHERE bcl_hash IS NOT NULL")
            files_with_bcl = cur.fetchone()[0]
            class_pct = round(with_bcl / total_classes * 100, 1) if total_classes else 0
            method_pct = round(methods_with_bcl / total_methods * 100, 1) if total_methods else 0
            file_pct = round(files_with_bcl / total_files * 100, 1) if total_files else 0
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"class_bcl_coverage": class_pct,
                    "method_bcl_coverage": method_pct,
                    "file_bcl_coverage": file_pct,
                    "classes_with_bcl": with_bcl,
                    "total_classes": total_classes,
                    "methods_with_bcl": methods_with_bcl,
                    "total_methods": total_methods}, None)

    def GraphCoverage(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(DISTINCT src_id) FROM edges WHERE src_type='file'"
            )
            files_in_graph = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(DISTINCT src_id) FROM edges WHERE src_type='class'"
            )
            classes_in_graph = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(DISTINCT src_id) FROM edges WHERE src_type='method'"
            )
            methods_in_graph = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
            cur.execute(
                "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"
            )
            by_type = {r[0]: r[1] for r in cur.fetchall()}
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {
            "file_coverage": round(files_in_graph / total_files * 100, 1) if total_files else 0,
            "class_coverage": round(classes_in_graph / total_classes * 100, 1) if total_classes else 0,
            "method_coverage": round(methods_in_graph / total_methods * 100, 1) if total_methods else 0,
            "total_edges": total_edges,
            "edge_types": by_type,
        }, None)

    def MethodCoverage(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM methods")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
            prints = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
            decorators = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
            underscores = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=1")
            tuple3 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=0")
            non_tuple3 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
            has_run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            tuple3_pct = round(tuple3 / total * 100, 1) if total else 0
            run_pct = round(has_run / total_classes * 100, 1) if total_classes else 0
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"total_methods": total, "prints": prints,
                    "decorators": decorators, "underscores": underscores,
                    "tuple3": tuple3, "non_tuple3": non_tuple3,
                    "tuple3_pct": tuple3_pct,
                    "classes_with_run": has_run,
                    "total_classes": total_classes,
                    "run_pct": run_pct}, None)

    def TestCoverage(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE method_name LIKE 'test_%' "
                "OR method_name LIKE 'Test%'"
            )
            test_methods = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM files WHERE file_path LIKE '%test%' "
                "OR file_path LIKE '%Test%'"
            )
            test_files = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM attempts WHERE action='test_run'"
            )
            test_runs = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM attempts WHERE action='test_run' "
                "AND result=1"
            )
            passed = cur.fetchone()[0]
            method_pct = round(test_methods / total_methods * 100, 1) if total_methods else 0
            file_pct = round(test_files / total_files * 100, 1) if total_files else 0
            pass_rate = round(passed / test_runs * 100, 1) if test_runs else 0
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"test_methods": test_methods,
                    "total_methods": total_methods,
                    "method_coverage": method_pct,
                    "test_files": test_files,
                    "total_files": total_files,
                    "file_coverage": file_pct,
                    "test_runs": test_runs,
                    "passed": passed,
                    "pass_rate": pass_rate}, None)

    def HealthScore(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
            prints = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_decorator=1")
            decorators = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_self_underscore=1")
            underscores = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE returns_tuple3=0")
            non_tuple3 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=0")
            no_run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods WHERE cyclomatic_complexity >= 10")
            complex_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
            resolved = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge")
            total_knowledge = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        violations = prints + decorators + underscores + non_tuple3 + no_run
        violation_score = 100 - (violations / total_methods * 100) if total_methods else 100
        complexity_score = 100 - (complex_methods / total_methods * 100) if total_methods else 100
        knowledge_score = (resolved / total_knowledge * 100) if total_knowledge else 100
        graph_score = min(total_edges / max(total_methods, 1) * 100, 100)
        health = round((violation_score + complexity_score + knowledge_score + graph_score) / 4, 1)
        level = "excellent" if health >= 90 else (
                "good" if health >= 75 else (
                "fair" if health >= 50 else "poor"))
        return (1, {"health_score": health, "level": level,
                    "violation_score": round(violation_score, 1),
                    "complexity_score": round(complexity_score, 1),
                    "knowledge_score": round(knowledge_score, 1),
                    "graph_score": round(graph_score, 1),
                    "total_violations": violations,
                    "resolved_knowledge": resolved,
                    "total_knowledge": total_knowledge}, None)
