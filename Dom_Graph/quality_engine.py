#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/quality_engine.py"
# date="2026-06-26" author="Devin" session_id="phase4-analysis"
# context="Project Digital Twin Phase 4 Section 48 Quality Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="quality_engine.py" domain="twin_quality" authority="QualityEngine"}
# [@SUMMARY]{summary="Quality authority that computes complexity, readability, maintainability, cohesion, coupling scores and an aggregate project quality report for the Project Digital Twin."}
# [@CLASS]{class="QualityEngine" domain="quality" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="complexity_score" type="command"}
# [@METHOD]{method="readability_score" type="command"}
# [@METHOD]{method="maintainability_score" type="command"}
# [@METHOD]{method="cohesion_score" type="command"}
# [@METHOD]{method="coupling_score" type="command"}
# [@METHOD]{method="quality_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<QualityEngine: computes complexity readability maintainability cohesion coupling scores and aggregate quality report. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
QualityEngine -- authority for quality scoring and reporting.
Implements Section 48 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: complexity_score, readability_score, maintainability_score,
          cohesion_score, coupling_score, quality_report.
The engine computes cyclomatic complexity from the methods table,
readability from line count, comment ratio and average line length,
maintainability from complexity plus dependency count, cohesion from
keyword overlap between class and method names, and coupling from the
class dependency graph. The aggregate report averages all scores.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
IDEAL_LINE_COUNT = 30
MAX_COMPLEXITY = 15
MAX_DEPENDENCIES = 10
COMMENT_RE = re.compile(r"^\s*#")
KEYWORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")


class QualityEngine:
    """Authority for quality scoring and aggregate reporting."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "ideal_line_count": IDEAL_LINE_COUNT,
                "max_complexity": MAX_COMPLEXITY,
                "max_dependencies": MAX_DEPENDENCIES,
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
        if command == "complexity_score":
            return self.ComplexityScore(params)
        elif command == "readability_score":
            return self.ReadabilityScore(params)
        elif command == "maintainability_score":
            return self.MaintainabilityScore(params)
        elif command == "cohesion_score":
            return self.CohesionScore(params)
        elif command == "coupling_score":
            return self.CouplingScore(params)
        elif command == "quality_report":
            return self.QualityReport(params)
        elif command == "reuse_score":
            return self.ReuseScore(params)
        elif command == "documentation_score":
            return self.DocumentationScore(params)
        elif command == "stability_score":
            return self.StabilityScore(params)
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

    def ClampScore(self, value):
        if value < 0:
            return 0.0
        if value > 100:
            return 100.0
        return round(value, 2)

    def ComplexityScore(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        scope = self._p(params, "scope")
        conn = self.Connect()
        cur = conn.cursor()
        max_complexity = self.state["config"]["max_complexity"]
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity, "
                "line_count FROM methods WHERE method_id=?",
                (method_id,),
            )
            row = cur.fetchone()
            if row is None:
                return (0, None, ("NOT_FOUND", "method not found: " + str(method_id), 0))
            complexity = row[2] or 0
            score = self.ClampScore(100 - (complexity / max_complexity) * 100)
            record = {
                "scope": "method",
                "method_id": row[0],
                "method_name": row[1],
                "cyclomatic_complexity": complexity,
                "score": score,
                "line_count": row[3],
            }
            self.state["results"].append(record)
            return (1, record, None)
        if class_id is not None:
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity "
                "FROM methods WHERE class_id=? ORDER BY method_id",
                (class_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return (0, None, ("NOT_FOUND", "class has no methods: " + str(class_id), 0))
            scores = []
            for mid, mname, cc in rows:
                cc = cc or 0
                sc = self.ClampScore(100 - (cc / max_complexity) * 100)
                scores.append({
                    "method_id": mid,
                    "method_name": mname,
                    "cyclomatic_complexity": cc,
                    "score": sc,
                })
            avg = self.ClampScore(sum(s["score"] for s in scores) / len(scores))
            record = {
                "scope": "class",
                "class_id": class_id,
                "methods": scores,
                "average_score": avg,
            }
            self.state["results"].append(record)
            return (1, record, None)
        if scope == "all" or (method_id is None and class_id is None):
            cur.execute(
                "SELECT method_id, method_name, cyclomatic_complexity, "
                "line_count FROM methods ORDER BY method_id LIMIT ?",
                (self.state["config"]["default_limit"],),
            )
            rows = cur.fetchall()
            scores = []
            for mid, mname, cc, lc in rows:
                cc = cc or 0
                sc = self.ClampScore(100 - (cc / max_complexity) * 100)
                scores.append({
                    "method_id": mid,
                    "method_name": mname,
                    "cyclomatic_complexity": cc,
                    "score": sc,
                    "line_count": lc,
                })
            avg = self.ClampScore(sum(s["score"] for s in scores) / len(scores)) if scores else 100.0
            record = {
                "scope": "all",
                "methods": scores,
                "count": len(scores),
                "average_score": avg,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            self.state["results"].append(record)
            return (1, record, None)
        return (0, None, ("MISSING_PARAM", "method_id, class_id or scope=all required", 0))

    def ReadabilityScore(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name, method_code, line_count FROM methods WHERE method_id=?",
            (method_id,),
        )
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "method not found: " + str(method_id), 0))
        mname, code, line_count = row
        line_count = line_count or 0
        lines = (code or "").splitlines()
        total_lines = len(lines) if lines else 1
        comment_lines = sum(1 for ln in lines if COMMENT_RE.match(ln))
        comment_ratio = comment_lines / total_lines if total_lines else 0
        avg_line_length = (
            sum(len(ln) for ln in lines) / total_lines if total_lines else 0
        )
        ideal = self.state["config"]["ideal_line_count"]
        length_score = max(0.0, 100 - (abs(line_count - ideal) / ideal) * 100)
        comment_score = min(100.0, comment_ratio * 100 * 3)
        line_length_penalty = max(0.0, 100 - max(0, avg_line_length - 80))
        score = self.ClampScore((length_score + comment_score + line_length_penalty) / 3)
        record = {
            "method_id": method_id,
            "method_name": mname,
            "line_count": line_count,
            "comment_lines": comment_lines,
            "comment_ratio": round(comment_ratio, 3),
            "avg_line_length": round(avg_line_length, 2),
            "score": score,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def MaintainabilityScore(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_name, cyclomatic_complexity, dependencies, "
            "line_count FROM methods WHERE method_id=?",
            (method_id,),
        )
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "method not found: " + str(method_id), 0))
        mname, complexity, deps_json, line_count = row
        complexity = complexity or 0
        line_count = line_count or 0
        dep_count = 0
        if deps_json:
            try:
                parsed = json.loads(deps_json)
                if isinstance(parsed, list):
                    dep_count = len(parsed)
                elif isinstance(parsed, dict):
                    dep_count = len(parsed)
            except (ValueError, TypeError):
                dep_count = 0
        max_complexity = self.state["config"]["max_complexity"]
        max_dependencies = self.state["config"]["max_dependencies"]
        complexity_penalty = (complexity / max_complexity) * 100
        dep_penalty = (dep_count / max_dependencies) * 100
        length_penalty = max(0, (line_count - 50) / 50) * 100
        score = self.ClampScore(100 - (complexity_penalty + dep_penalty + length_penalty) / 3)
        record = {
            "method_id": method_id,
            "method_name": mname,
            "cyclomatic_complexity": complexity,
            "dependency_count": dep_count,
            "line_count": line_count,
            "score": score,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def CohesionScore(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_name FROM classes WHERE class_id=?",
            (class_id,),
        )
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "class not found: " + str(class_id), 0))
        class_name = row[0] or ""
        class_keywords = set(KEYWORD_RE.findall(class_name))
        class_keywords_lower = set(k.lower() for k in class_keywords)
        cur.execute(
            "SELECT method_name FROM methods WHERE class_id=? ORDER BY method_id",
            (class_id,),
        )
        method_names = [r[0] or "" for r in cur.fetchall()]
        if not method_names:
            record = {
                "class_id": class_id,
                "class_name": class_name,
                "method_count": 0,
                "overlap_ratio": 0.0,
                "score": 100.0,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            self.state["results"].append(record)
            return (1, record, None)
        overlaps = []
        for mname in method_names:
            method_keywords = set(KEYWORD_RE.findall(mname))
            method_keywords_lower = set(k.lower() for k in method_keywords)
            if not class_keywords_lower or not method_keywords_lower:
                overlaps.append(0.0)
                continue
            shared = class_keywords_lower & method_keywords_lower
            ratio = len(shared) / len(class_keywords_lower | method_keywords_lower)
            overlaps.append(ratio)
        avg_overlap = sum(overlaps) / len(overlaps)
        score = self.ClampScore(avg_overlap * 100)
        record = {
            "class_id": class_id,
            "class_name": class_name,
            "method_count": len(method_names),
            "method_names": method_names,
            "overlaps": [round(o, 3) for o in overlaps],
            "overlap_ratio": round(avg_overlap, 3),
            "score": score,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def CouplingScore(self, params):
        class_id = self._p(params, "class_id")
        if class_id is None:
            return (0, None, ("MISSING_PARAM", "class_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT class_name, dependencies, relationships FROM classes WHERE class_id=?",
            (class_id,),
        )
        row = cur.fetchone()
        if row is None:
            return (0, None, ("NOT_FOUND", "class not found: " + str(class_id), 0))
        class_name, deps_json, rels_json = row
        dep_count = 0
        if deps_json:
            try:
                parsed = json.loads(deps_json)
                if isinstance(parsed, list):
                    dep_count = len(parsed)
                elif isinstance(parsed, dict):
                    dep_count = len(parsed)
            except (ValueError, TypeError):
                dep_count = 0
        rel_count = 0
        if rels_json:
            try:
                parsed = json.loads(rels_json)
                if isinstance(parsed, list):
                    rel_count = len(parsed)
                elif isinstance(parsed, dict):
                    rel_count = len(parsed)
            except (ValueError, TypeError):
                rel_count = 0
        cur.execute(
            "SELECT COUNT(*) FROM edges WHERE src_type='class' AND src_id=? "
            "OR dst_type='class' AND dst_id=?",
            (class_id, class_id),
        )
        edge_count = cur.fetchone()[0]
        total_coupling = dep_count + rel_count + edge_count
        max_dependencies = self.state["config"]["max_dependencies"]
        score = self.ClampScore(100 - (total_coupling / max_dependencies) * 100)
        record = {
            "class_id": class_id,
            "class_name": class_name,
            "dependency_count": dep_count,
            "relationship_count": rel_count,
            "edge_count": edge_count,
            "total_coupling": total_coupling,
            "score": score,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def QualityReport(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id FROM methods ORDER BY method_id LIMIT ?",
            (limit,),
        )
        method_ids = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT class_id FROM classes ORDER BY class_id LIMIT ?",
            (limit,),
        )
        class_ids = [r[0] for r in cur.fetchall()]
        complexity_scores = []
        readability_scores = []
        maintainability_scores = []
        for mid in method_ids:
            cr = self.ComplexityScore({"method_id": mid})
            if cr[0] == 1:
                complexity_scores.append(cr[1]["score"])
            rr = self.ReadabilityScore({"method_id": mid})
            if rr[0] == 1:
                readability_scores.append(rr[1]["score"])
            mr = self.MaintainabilityScore({"method_id": mid})
            if mr[0] == 1:
                maintainability_scores.append(mr[1]["score"])
        cohesion_scores = []
        coupling_scores = []
        for cid in class_ids:
            ch = self.CohesionScore({"class_id": cid})
            if ch[0] == 1:
                cohesion_scores.append(ch[1]["score"])
            cp = self.CouplingScore({"class_id": cid})
            if cp[0] == 1:
                coupling_scores.append(cp[1]["score"])
        avg = lambda scores: round(sum(scores) / len(scores), 2) if scores else 100.0
        report = {
            "method_count": len(method_ids),
            "class_count": len(class_ids),
            "complexity": {
                "average": avg(complexity_scores),
                "min": min(complexity_scores) if complexity_scores else 100.0,
                "max": max(complexity_scores) if complexity_scores else 100.0,
            },
            "readability": {
                "average": avg(readability_scores),
                "min": min(readability_scores) if readability_scores else 100.0,
                "max": max(readability_scores) if readability_scores else 100.0,
            },
            "maintainability": {
                "average": avg(maintainability_scores),
                "min": min(maintainability_scores) if maintainability_scores else 100.0,
                "max": max(maintainability_scores) if maintainability_scores else 100.0,
            },
            "cohesion": {
                "average": avg(cohesion_scores),
                "min": min(cohesion_scores) if cohesion_scores else 100.0,
                "max": max(cohesion_scores) if cohesion_scores else 100.0,
            },
            "coupling": {
                "average": avg(coupling_scores),
                "min": min(coupling_scores) if coupling_scores else 100.0,
                "max": max(coupling_scores) if coupling_scores else 100.0,
            },
            "created": datetime.now(timezone.utc).isoformat(),
        }
        overall_scores = [
            report["complexity"]["average"],
            report["readability"]["average"],
            report["maintainability"]["average"],
            report["cohesion"]["average"],
            report["coupling"]["average"],
        ]
        report["overall_score"] = round(sum(overall_scores) / len(overall_scores), 2)
        self.state["catalog"].append(report)
        return (1, report, None)

    def ReuseScore(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if class_id is not None:
            cur.execute(
                "SELECT class_id, class_name FROM classes WHERE class_id=?",
                (class_id,),
            )
            rows = [cur.fetchone()]
        else:
            cur.execute(
                "SELECT class_id, class_name FROM classes ORDER BY class_id LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        results = []
        for cid, cname in rows:
            if cid is None:
                continue
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE class_id=?",
                (cid,),
            )
            method_count = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(DISTINCT method_name) FROM methods WHERE class_id=?",
                (cid,),
            )
            unique_names = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE src_type='class' AND src_id=?",
                (cid,),
            )
            outgoing = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE dst_type='class' AND dst_id=?",
                (cid,),
            )
            incoming = cur.fetchone()[0]
            reuse_indicator = incoming
            uniqueness_ratio = unique_names / method_count if method_count else 1.0
            external_use_ratio = incoming / (incoming + outgoing + 1) if (incoming + outgoing) > 0 else 0.0
            score = self.ClampScore((uniqueness_ratio * 50) + (external_use_ratio * 50))
            results.append({
                "class_id": cid,
                "class_name": cname,
                "method_count": method_count,
                "unique_method_names": unique_names,
                "incoming_edges": incoming,
                "outgoing_edges": outgoing,
                "reuse_indicator": reuse_indicator,
                "score": score,
            })
        record = {
            "scope": "class" if class_id is not None else "all",
            "results": results,
            "count": len(results),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def DocumentationScore(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id is not None:
            cur.execute(
                "SELECT method_id, method_name, method_code, docstring, start_line "
                "FROM methods WHERE method_id=?",
                (method_id,),
            )
            rows = [cur.fetchone()]
        elif class_id is not None:
            cur.execute(
                "SELECT method_id, method_name, method_code, docstring, start_line "
                "FROM methods WHERE class_id=? ORDER BY method_id LIMIT ?",
                (class_id, limit),
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                "SELECT method_id, method_name, method_code, docstring, start_line "
                "FROM methods WHERE method_code IS NOT NULL "
                "ORDER BY method_id LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        results = []
        for mid, mname, code, docstring, start_line in rows:
            if mid is None:
                continue
            has_docstring = bool(docstring and docstring.strip())
            lines = (code or "").splitlines()
            total_lines = len(lines) if lines else 1
            comment_lines = sum(1 for ln in lines if COMMENT_RE.match(ln))
            comment_ratio = comment_lines / total_lines if total_lines else 0
            doc_score = 40.0 if has_docstring else 0.0
            comment_score = min(40.0, comment_ratio * 100 * 2)
            inline_ratio = comment_lines / total_lines if total_lines else 0
            inline_score = min(20.0, inline_ratio * 100 * 3)
            score = self.ClampScore(doc_score + comment_score + inline_score)
            results.append({
                "method_id": mid,
                "method_name": mname,
                "has_docstring": has_docstring,
                "comment_lines": comment_lines,
                "comment_ratio": round(comment_ratio, 3),
                "score": score,
            })
        record = {
            "results": results,
            "count": len(results),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)

    def StabilityScore(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if class_id is not None:
            cur.execute(
                "SELECT class_id, class_name, dependencies, relationships "
                "FROM classes WHERE class_id=?",
                (class_id,),
            )
            rows = [cur.fetchone()]
        else:
            cur.execute(
                "SELECT class_id, class_name, dependencies, relationships "
                "FROM classes ORDER BY class_id LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        results = []
        for cid, cname, deps_json, rels_json in rows:
            if cid is None:
                continue
            dep_count = 0
            if deps_json:
                try:
                    parsed = json.loads(deps_json)
                    if isinstance(parsed, list):
                        dep_count = len(parsed)
                    elif isinstance(parsed, dict):
                        dep_count = len(parsed)
                except (ValueError, TypeError):
                    dep_count = 0
            rel_count = 0
            if rels_json:
                try:
                    parsed = json.loads(rels_json)
                    if isinstance(parsed, list):
                        rel_count = len(parsed)
                    elif isinstance(parsed, dict):
                        rel_count = len(parsed)
                except (ValueError, TypeError):
                    rel_count = 0
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE dst_type='class' AND dst_id=?",
                (cid,),
            )
            incoming = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM edges WHERE src_type='class' AND src_id=?",
                (cid,),
            )
            outgoing = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM methods WHERE class_id=?",
                (cid,),
            )
            method_count = cur.fetchone()[0]
            max_dep = self.state["config"]["max_dependencies"]
            dep_stability = self.ClampScore(100 - (dep_count / max_dep) * 100)
            ratio = incoming / (incoming + outgoing + 1) if (incoming + outgoing) > 0 else 1.0
            coupling_stability = self.ClampScore(ratio * 100)
            method_stability = self.ClampScore(100 - (method_count / 20) * 100) if method_count > 20 else 100.0
            score = self.ClampScore((dep_stability + coupling_stability + method_stability) / 3)
            results.append({
                "class_id": cid,
                "class_name": cname,
                "dependency_count": dep_count,
                "relationship_count": rel_count,
                "incoming_edges": incoming,
                "outgoing_edges": outgoing,
                "method_count": method_count,
                "dep_stability": dep_stability,
                "coupling_stability": coupling_stability,
                "method_stability": method_stability,
                "score": score,
            })
        record = {
            "results": results,
            "count": len(results),
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.state["results"].append(record)
        return (1, record, None)
