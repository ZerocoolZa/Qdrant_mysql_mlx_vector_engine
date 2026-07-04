#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/confidence_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 30: Confidence Scoring -- 7 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="confidence_engine.py" domain="twin_confidence" authority="ConfidenceEngine"}
# [@SUMMARY]{summary="Confidence authority: parse confidence, match confidence, graph confidence, repair confidence, runtime confidence, test confidence, overall confidence."}
# [@CLASS]{class="ConfidenceEngine" domain="confidence" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="parse_confidence" type="command"}
# [@METHOD]{method="match_confidence" type="command"}
# [@METHOD]{method="graph_confidence" type="command"}
# [@METHOD]{method="repair_confidence" type="command"}
# [@METHOD]{method="runtime_confidence" type="command"}
# [@METHOD]{method="test_confidence" type="command"}
# [@METHOD]{method="overall_confidence" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ConfidenceEngine:
    """Authority for computing confidence scores across pipeline stages."""

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
        if command == "parse_confidence":
            return self.ParseConfidence(params)
        elif command == "match_confidence":
            return self.MatchConfidence(params)
        elif command == "graph_confidence":
            return self.GraphConfidence(params)
        elif command == "repair_confidence":
            return self.RepairConfidence(params)
        elif command == "runtime_confidence":
            return self.RuntimeConfidence(params)
        elif command == "test_confidence":
            return self.TestConfidence(params)
        elif command == "overall_confidence":
            return self.OverallConfidence(params)
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

    def ParseConfidence(self, params):
        file_id = self._p(params, "file_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if file_id:
                cur.execute("SELECT file_path, hash, line_count, language FROM files WHERE file_id=?", (file_id,))
                row = cur.fetchone()
                if row is None:
                    return (0, None, ("FILE_NOT_FOUND", str(file_id), 0))
                score = 100.0
                if not row[3]:
                    score -= 20
                if row[2] and row[2] > 1000:
                    score -= 10
                cur.execute("SELECT COUNT(*) FROM classes WHERE file_id=?", (file_id,))
                class_count = cur.fetchone()[0]
                if class_count == 0:
                    score -= 15
            else:
                cur.execute("SELECT COUNT(*) FROM files")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM files WHERE language IS NOT NULL AND language != ''")
                detected = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM classes")
                classes = cur.fetchone()[0]
                score = (detected / max(total, 1)) * 100
                if classes == 0:
                    score -= 20
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"parse_confidence": round(score, 1)}, None)

    def MatchConfidence(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT hash, signature FROM methods WHERE method_id=?", (method_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            method_hash, signature = row
            cur.execute("SELECT COUNT(*) FROM methods WHERE hash=? AND method_id!=?", (method_hash, method_id))
            duplicates = cur.fetchone()[0]
            if duplicates > 0:
                score = 30.0
            else:
                score = 90.0
            if signature and "Tuple3" in signature:
                score += 5
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"match_confidence": round(min(score, 100), 1),
                    "duplicates": duplicates}, None)

    def GraphConfidence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM classes WHERE has_run_method=1"
            )
            has_run = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE class_id IS NOT NULL"
            )
            linked_methods = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM classes WHERE file_id IS NOT NULL"
            )
            linked_classes = cur.fetchone()[0]
            edge_score = min(total_edges / max(total_methods, 1) * 100, 100)
            run_score = (has_run / max(total_classes, 1)) * 100
            link_score = (linked_methods / max(total_methods, 1)) * 100
            class_link_score = (linked_classes / max(total_classes, 1)) * 100
            score = (edge_score + run_score + link_score + class_link_score) / 4
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"graph_confidence": round(score, 1),
                    "edge_score": round(edge_score, 1),
                    "run_score": round(run_score, 1),
                    "link_score": round(link_score, 1)}, None)

    def RepairConfidence(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        if knowledge_id is None:
            return (0, None, ("MISSING_PARAM", "knowledge_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT confidence, answer, evidence FROM knowledge WHERE knowledge_id=?", (knowledge_id,))
            row = cur.fetchone()
            if row is None:
                return (0, None, ("KNOWLEDGE_NOT_FOUND", str(knowledge_id), 0))
            stored_conf, answer, evidence = row
            score = stored_conf or 0
            if answer and len(answer) > 50:
                score += 10
            if evidence and len(evidence) > 20:
                score += 5
            cur.execute(
                "SELECT COUNT(*) FROM attempts WHERE knowledge_id=? AND action='fix_applied'",
                (knowledge_id,),
            )
            applied = cur.fetchone()[0]
            if applied > 0:
                score += 10
            score = min(score, 100)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"repair_confidence": round(score, 1),
                    "stored_confidence": stored_conf,
                    "times_applied": applied}, None)

    def RuntimeConfidence(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT returns_tuple3, has_print, has_decorator, has_self_underscore "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
            tuple3, prints, decorators, underscores = row
            score = 100.0
            if not tuple3:
                score -= 30
            if prints:
                score -= 15
            if decorators:
                score -= 15
            if underscores:
                score -= 10
            score = max(0, score)
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"runtime_confidence": round(score, 1),
                    "returns_tuple3": bool(tuple3)}, None)

    def TestConfidence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM attempts WHERE action='fix_applied'")
            applied = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM attempts WHERE action='fix_failed'")
            failed = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM attempts")
            total = cur.fetchone()[0]
            if total == 0:
                score = 0
            else:
                score = (applied / total) * 100
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"test_confidence": round(score, 1),
                    "tests_passed": applied, "tests_failed": failed,
                    "total_tests": total}, None)

    def OverallConfidence(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM methods")
            total_methods = cur.fetchone()[0]
            cur.execute("SELECT AVG(returns_tuple3) FROM methods")
            tuple3_rate = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1")
            violators = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes WHERE has_run_method=1")
            has_run = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM classes")
            total_classes = cur.fetchone()[0]
            cur.execute("SELECT AVG(confidence) FROM knowledge")
            avg_knowledge = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM edges")
            total_edges = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        compliance = tuple3_rate * 100
        violation_free = 100 - (violators / max(total_methods, 1) * 100)
        run_coverage = (has_run / max(total_classes, 1)) * 100
        knowledge_score = avg_knowledge
        graph_density = min(total_edges / max(total_methods, 1) * 50, 100)
        overall = (compliance + violation_free + run_coverage + knowledge_score + graph_density) / 5
        overall = max(0, min(100, overall))
        return (1, {"overall_confidence": round(overall, 1),
                    "compliance": round(compliance, 1),
                    "violation_free": round(violation_free, 1),
                    "run_coverage": round(run_coverage, 1),
                    "knowledge_score": round(knowledge_score, 1),
                    "graph_density": round(graph_density, 1)}, None)
