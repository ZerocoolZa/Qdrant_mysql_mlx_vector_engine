#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/evolution_engine.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 41 Evolution Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="evolution_engine.py" domain="twin_evolution" authority="EvolutionEngine"}
# [@SUMMARY]{summary="Evolution authority that tracks class, method, dependency, error, fix, refactor, variable, and architecture timelines over time using real queries against classes, methods, knowledge, attempts, observations, edges, and snapshots tables."}
# [@CLASS]{class="EvolutionEngine" domain="evolution" authority="single"}
# [@METHOD]{method="class_timeline" type="command"}
# [@METHOD]{method="method_timeline" type="command"}
# [@METHOD]{method="dependency_timeline" type="command"}
# [@METHOD]{method="error_timeline" type="command"}
# [@METHOD]{method="fix_timeline" type="command"}
# [@METHOD]{method="refactor_timeline" type="command"}
# [@METHOD]{method="variable_timeline" type="command"}
# [@METHOD]{method="architecture_timeline" type="command"}
# [@METHOD]{method="growth_rate" type="command"}
# [@METHOD]{method="complexity_trend" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<EvolutionEngine: tracks class/method/dependency/error/fix/refactor/variable/architecture timelines over time. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
EvolutionEngine -- Evolution tracking authority.
Implements Section 41 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: class_timeline, method_timeline, dependency_timeline,
          error_timeline, fix_timeline, refactor_timeline,
          variable_timeline, architecture_timeline,
          growth_rate, complexity_trend.

# ============================================================
# ERRORS -- Section 41 spec vs. implementation
# Rating: 10/10 (was 3/10 SHELL)
# Spec has 8 sub-sections (41.1-41.8). All 8 implemented.
# ============================================================
# 41.1 ClassTimeline        -- SELECT * FROM classes WHERE class_name=? ORDER BY version
#                              plus snapshots for class content history.
# 41.2 MethodTimeline       -- SELECT * FROM methods WHERE method_name=? ORDER BY version
#                              plus snapshots for method content history.
# 41.3 VariableTimeline     -- observations WHERE observation_type LIKE '%variable%'
#                              ordered by created, plus method_code assignment scan.
# 41.4 DependencyTimeline   -- edges ORDER BY created, grouped by edge_type.
# 41.5 ArchitectureTimeline -- classes ORDER BY class_name, version showing
#                              method_count/fields/properties/relationships drift.
# 41.6 ErrorTimeline        -- knowledge WHERE error_type IS NOT NULL ORDER BY created.
# 41.7 FixTimeline          -- knowledge WHERE answer IS NOT NULL ORDER BY created.
# 41.8 RefactorTimeline     -- attempts ORDER BY created.
# ============================================================
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class EvolutionEngine:
    """Evolution tracking authority."""

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
        if command == "class_timeline":
            return self.ClassTimeline(params)
        elif command == "method_timeline":
            return self.MethodTimeline(params)
        elif command == "dependency_timeline":
            return self.DependencyTimeline(params)
        elif command == "error_timeline":
            return self.ErrorTimeline(params)
        elif command == "fix_timeline":
            return self.FixTimeline(params)
        elif command == "refactor_timeline":
            return self.RefactorTimeline(params)
        elif command == "variable_timeline":
            return self.VariableTimeline(params)
        elif command == "architecture_timeline":
            return self.ArchitectureTimeline(params)
        elif command == "growth_rate":
            return self.GrowthRate(params)
        elif command == "complexity_trend":
            return self.ComplexityTrend(params)

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

    def ClassTimeline(self, params):
        # 41.1 Class Timeline: SELECT * FROM classes WHERE class_name=? ORDER BY version
        class_name = self._p(params, "class_name")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if class_id:
            cur.execute(
                "SELECT class_id, class_name, version, hash, method_count, "
                "parent, start_line, end_line, cyclomatic_complexity "
                "FROM classes WHERE class_id=? ORDER BY version",
                (class_id,),
            )
        elif class_name:
            cur.execute(
                "SELECT class_id, class_name, version, hash, method_count, "
                "parent, start_line, end_line, cyclomatic_complexity "
                "FROM classes WHERE class_name=? ORDER BY version",
                (class_name,),
            )
        else:
            cur.execute(
                "SELECT class_id, class_name, version, hash, method_count, "
                "parent, start_line, end_line, cyclomatic_complexity "
                "FROM classes ORDER BY class_name, version"
            )
        rows = cur.fetchall()
        timeline = []
        prev_hash = None
        for r in rows:
            changed = prev_hash is not None and r[3] != prev_hash
            timeline.append({
                "class_id": r[0], "class_name": r[1], "version": r[2],
                "hash": r[3], "method_count": r[4], "parent": r[5],
                "start_line": r[6], "end_line": r[7],
                "cyclomatic_complexity": r[8], "changed": changed,
            })
            prev_hash = r[3]
        # Append snapshot history for the class if available.
        if class_id or class_name:
            if class_id:
                cur.execute(
                    "SELECT snapshot_id, snapshot_type, content, hash, created, notes "
                    "FROM snapshots WHERE class_id=? ORDER BY created",
                    (class_id,),
                )
            else:
                cur.execute(
                    "SELECT s.snapshot_id, s.snapshot_type, s.content, s.hash, s.created, s.notes "
                    "FROM snapshots s JOIN classes c ON s.class_id=c.class_id "
                    "WHERE c.class_name=? ORDER BY s.created",
                    (class_name,),
                )
            snaps = [{"snapshot_id": s[0], "snapshot_type": s[1], "content": s[2],
                      "hash": s[3], "created": s[4], "notes": s[5]} for s in cur.fetchall()]
        else:
            snaps = []
        return (1, {"timeline": timeline, "count": len(timeline),
                    "snapshots": snaps, "snapshot_count": len(snaps)}, None)

    def MethodTimeline(self, params):
        # 41.2 Method Timeline: SELECT * FROM methods WHERE method_name=? ORDER BY version
        method_name = self._p(params, "method_name")
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute(
                "SELECT method_id, method_name, version, hash, class_id, "
                "cyclomatic_complexity, line_count, returns_tuple3, has_print "
                "FROM methods WHERE method_id=? ORDER BY version",
                (method_id,),
            )
        elif method_name:
            cur.execute(
                "SELECT method_id, method_name, version, hash, class_id, "
                "cyclomatic_complexity, line_count, returns_tuple3, has_print "
                "FROM methods WHERE method_name=? ORDER BY version",
                (method_name,),
            )
        else:
            return (0, None, ("NO_PARAM", "method_name or method_id required", 0))
        rows = cur.fetchall()
        timeline = []
        prev_hash = None
        for r in rows:
            changed = prev_hash is not None and r[3] != prev_hash
            timeline.append({
                "method_id": r[0], "method_name": r[1], "version": r[2],
                "hash": r[3], "class_id": r[4], "cyclomatic_complexity": r[5],
                "line_count": r[6], "returns_tuple3": r[7], "has_print": r[8],
                "changed": changed,
            })
            prev_hash = r[3]
        # Append snapshot history for the method if available.
        cur.execute(
            "SELECT snapshot_id, snapshot_type, content, hash, created, notes "
            "FROM snapshots WHERE method_id=? ORDER BY created",
            (method_id,) if method_id else (rows[0][0] if rows else 0,),
        )
        snaps = [{"snapshot_id": s[0], "snapshot_type": s[1], "content": s[2],
                  "hash": s[3], "created": s[4], "notes": s[5]} for s in cur.fetchall()]
        return (1, {"timeline": timeline, "count": len(timeline),
                    "snapshots": snaps, "snapshot_count": len(snaps)}, None)

    def DependencyTimeline(self, params):
        # 41.4 Dependency Timeline: track edge changes over time
        edge_type = self._p(params, "edge_type")
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        if edge_type:
            cur.execute(
                "SELECT edge_id, edge_type, src_type, src_id, dst_type, dst_id, "
                "evidence, confidence, created "
                "FROM edges WHERE edge_type=? ORDER BY created LIMIT ?",
                (edge_type, limit),
            )
        else:
            cur.execute(
                "SELECT edge_id, edge_type, src_type, src_id, dst_type, dst_id, "
                "evidence, confidence, created "
                "FROM edges ORDER BY created LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        timeline = [{
            "edge_id": r[0], "edge_type": r[1], "src_type": r[2], "src_id": r[3],
            "dst_type": r[4], "dst_id": r[5], "evidence": r[6],
            "confidence": r[7], "created": r[8],
        } for r in rows]
        # Group counts by edge_type for a summary of dependency drift.
        cur.execute(
            "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type ORDER BY edge_type"
        )
        by_type = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"timeline": timeline, "count": len(timeline),
                    "by_edge_type": by_type}, None)

    def ErrorTimeline(self, params):
        # 41.6 Error Timeline: SELECT * FROM knowledge WHERE error_type IS NOT NULL ORDER BY created
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, error_type, error_text, stack_trace, "
            "fix_result, confidence, created, file_id, class_id, method_id "
            "FROM knowledge WHERE error_type IS NOT NULL "
            "ORDER BY created LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        timeline = [{
            "knowledge_id": r[0], "problem": r[1], "error_type": r[2],
            "error_text": r[3], "stack_trace": r[4], "fix_result": r[5],
            "confidence": r[6], "created": r[7], "file_id": r[8],
            "class_id": r[9], "method_id": r[10],
        } for r in rows]
        return (1, {"timeline": timeline, "count": len(timeline)}, None)

    def FixTimeline(self, params):
        # 41.7 Fix Timeline: SELECT * FROM knowledge WHERE answer IS NOT NULL ORDER BY created
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT knowledge_id, problem, answer, fix_applied, fix_result, "
            "is_best, confidence, resolution_time_ms, created, method_id "
            "FROM knowledge WHERE answer IS NOT NULL "
            "ORDER BY created LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        timeline = [{
            "knowledge_id": r[0], "problem": r[1], "answer": r[2],
            "fix_applied": r[3], "fix_result": r[4], "is_best": r[5],
            "confidence": r[6], "resolution_time_ms": r[7], "created": r[8],
            "method_id": r[9],
        } for r in rows]
        return (1, {"timeline": timeline, "count": len(timeline)}, None)

    def RefactorTimeline(self, params):
        # 41.8 Refactor Timeline: SELECT * FROM attempts ORDER BY created
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute(
                "SELECT attempt_id, method_id, action, before_code, after_code, "
                "compile_result, test_result, error_text, rollback, "
                "knowledge_id, created "
                "FROM attempts WHERE method_id=? ORDER BY created LIMIT ?",
                (method_id, limit),
            )
        else:
            cur.execute(
                "SELECT attempt_id, method_id, action, before_code, after_code, "
                "compile_result, test_result, error_text, rollback, "
                "knowledge_id, created "
                "FROM attempts ORDER BY created LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        timeline = [{
            "attempt_id": r[0], "method_id": r[1], "action": r[2],
            "before_code": r[3], "after_code": r[4], "compile_result": r[5],
            "test_result": r[6], "error_text": r[7], "rollback": r[8],
            "knowledge_id": r[9], "created": r[10],
        } for r in rows]
        # Summary of refactor actions performed.
        cur.execute(
            "SELECT action, COUNT(*) FROM attempts GROUP BY action ORDER BY action"
        )
        by_action = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"timeline": timeline, "count": len(timeline),
                    "by_action": by_action}, None)

    def VariableTimeline(self, params):
        # 41.3 Variable Timeline: track variable name changes
        # Variables are stored in observations (observation_type='variable_assignment')
        # plus assignments parsed from method_code across versions.
        variable_name = self._p(params, "variable_name")
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        if variable_name:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, method_id, class_id, file_id, created "
                "FROM observations WHERE observation_type LIKE '%variable%' "
                "AND subject LIKE ? ORDER BY created LIMIT ?",
                ("%" + variable_name + "%", limit),
            )
        else:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, method_id, class_id, file_id, created "
                "FROM observations WHERE observation_type LIKE '%variable%' "
                "ORDER BY created LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        timeline = [{
            "observation_id": r[0], "observation_type": r[1], "subject": r[2],
            "evidence": r[3], "confidence": r[4], "method_id": r[5],
            "class_id": r[6], "file_id": r[7], "created": r[8],
        } for r in rows]
        # Also scan method_code for assignment statements to track variable
        # introduction across method versions.
        cur.execute(
            "SELECT method_id, method_name, version, method_code "
            "FROM methods WHERE method_code LIKE ? ORDER BY method_name, version",
            ("%" + (variable_name or "") + " = %",),
        )
        assignments = []
        for r in cur.fetchall():
            code = r[3] or ""
            for line in code.split("\n"):
                stripped = line.strip()
                if " = " in stripped and not stripped.startswith("#"):
                    name = stripped.split(" = ")[0].strip()
                    if variable_name and name != variable_name:
                        continue
                    assignments.append({
                        "method_id": r[0], "method_name": r[1], "version": r[2],
                        "variable": name,
                    })
        return (1, {"timeline": timeline, "count": len(timeline),
                    "assignments": assignments, "assignment_count": len(assignments)}, None)

    def ArchitectureTimeline(self, params):
        # 41.5 Architecture Timeline: track class structure changes
        # Show method_count, fields, properties, relationships drift per class/version.
        class_name = self._p(params, "class_name")
        conn = self.Connect()
        cur = conn.cursor()
        if class_name:
            cur.execute(
                "SELECT class_id, class_name, version, method_count, fields, "
                "properties, relationships, parent, interfaces, "
                "cyclomatic_complexity, hash "
                "FROM classes WHERE class_name=? ORDER BY version",
                (class_name,),
            )
        else:
            cur.execute(
                "SELECT class_id, class_name, version, method_count, fields, "
                "properties, relationships, parent, interfaces, "
                "cyclomatic_complexity, hash "
                "FROM classes ORDER BY class_name, version"
            )
        rows = cur.fetchall()
        timeline = []
        prev = {}
        for r in rows:
            key = r[1]
            changed = (
                key in prev and (
                    prev[key].get("method_count") != r[3] or
                    prev[key].get("fields") != r[4] or
                    prev[key].get("properties") != r[5] or
                    prev[key].get("relationships") != r[6] or
                    prev[key].get("parent") != r[7] or
                    prev[key].get("hash") != r[10]
                )
            )
            timeline.append({
                "class_id": r[0], "class_name": r[1], "version": r[2],
                "method_count": r[3], "fields": r[4], "properties": r[5],
                "relationships": r[6], "parent": r[7], "interfaces": r[8],
                "cyclomatic_complexity": r[9], "hash": r[10],
                "structure_changed": changed,
            })
            prev[key] = {"method_count": r[3], "fields": r[4], "properties": r[5],
                         "relationships": r[6], "parent": r[7], "hash": r[10]}
        # Overall architecture summary: class count, total methods, inheritance depth.
        cur.execute("SELECT COUNT(*) FROM classes")
        class_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        method_count = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM classes WHERE parent IS NOT NULL AND parent != ''"
        )
        inherited = cur.fetchone()[0]
        return (1, {"timeline": timeline, "count": len(timeline),
                    "summary": {"class_count": class_count,
                                "method_count": method_count,
                                "inherited_classes": inherited}}, None)

    def GrowthRate(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge")
        knowledge = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts")
        attempts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations")
        observations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM snapshots")
        snapshots = cur.fetchone()[0]
        return (1, {"files": files, "classes": classes, "methods": methods,
                    "edges": edges, "knowledge": knowledge, "attempts": attempts,
                    "observations": observations, "snapshots": snapshots}, None)

    def ComplexityTrend(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT AVG(cyclomatic_complexity), MAX(cyclomatic_complexity), "
            "MIN(cyclomatic_complexity) FROM methods"
        )
        row = cur.fetchone()
        # Per-class average complexity trend.
        cur.execute(
            "SELECT c.class_name, AVG(m.cyclomatic_complexity) "
            "FROM methods m JOIN classes c ON m.class_id=c.class_id "
            "GROUP BY c.class_id ORDER BY c.class_name"
        )
        per_class = {r[0]: r[1] for r in cur.fetchall()}
        # Methods above threshold (complexity hotspots over time).
        cur.execute(
            "SELECT method_name, cyclomatic_complexity, version "
            "FROM methods WHERE cyclomatic_complexity > 10 "
            "ORDER BY cyclomatic_complexity DESC LIMIT 20"
        )
        hotspots = [{"method_name": r[0], "complexity": r[1], "version": r[2]}
                    for r in cur.fetchall()]
        return (1, {"avg": row[0], "max": row[1], "min": row[2],
                    "per_class": per_class, "hotspots": hotspots}, None)
