#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/dna_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 58 Project DNA"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="dna_engine.py" domain="twin_dna" authority="DnaEngine"}
# [@SUMMARY]{summary="Project DNA authority that extracts coding style, architecture, naming, error, fix, dependency, and runtime DNA to compute project identity."}
# [@CLASS]{class="DnaEngine" domain="dna" authority="single"}
# [@METHOD]{method="extract_dna" type="command"}
# [@METHOD]{method="compare_dna" type="command"}
# [@METHOD]{method="project_identity" type="command"}
# [@METHOD]{method="style_dna" type="command"}
# [@METHOD]{method="architecture_dna" type="command"}
# [@METHOD]{method="error_dna" type="command"}
# [@METHOD]{method="fix_dna" type="command"}
# [@METHOD]{method="naming_dna" type="command"}
# [@METHOD]{method="dependency_dna" type="command"}
# [@METHOD]{method="runtime_dna" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<DnaEngine: extracts coding style, architecture, naming, error, fix, dependency, runtime DNA to compute project identity. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
DnaEngine -- Project DNA extraction authority.
Implements Section 58 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: extract_dna, compare_dna, project_identity, style_dna, architecture_dna, error_dna, fix_dna.
"""
import json
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class DnaEngine:
    """Project DNA extraction authority."""

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
        if command == "extract_dna":
            return self.ExtractDna(params)
        elif command == "compare_dna":
            return self.CompareDna(params)
        elif command == "project_identity":
            return self.ProjectIdentity(params)
        elif command == "style_dna":
            return self.StyleDna(params)
        elif command == "architecture_dna":
            return self.ArchitectureDna(params)
        elif command == "error_dna":
            return self.ErrorDna(params)
        elif command == "fix_dna":
            return self.FixDna(params)
        elif command == "naming_dna":
            return self.NamingDna(params)
        elif command == "dependency_dna":
            return self.DependencyDna(params)
        elif command == "runtime_dna":
            return self.RuntimeDna(params)

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

    def ExtractDna(self, params):
        style = self.StyleDna(params)
        arch = self.ArchitectureDna(params)
        err = self.ErrorDna(params)
        fix = self.FixDna(params)
        naming = self.NamingDna(params)
        dep = self.DependencyDna(params)
        runtime = self.RuntimeDna(params)
        identity = self.ProjectIdentity(params)
        dna = {
            "style": style[1] if style[0] == 1 else {},
            "architecture": arch[1] if arch[0] == 1 else {},
            "error": err[1] if err[0] == 1 else {},
            "fix": fix[1] if fix[0] == 1 else {},
            "naming": naming[1] if naming[0] == 1 else {},
            "dependency": dep[1] if dep[0] == 1 else {},
            "runtime": runtime[1] if runtime[0] == 1 else {},
            "identity": identity[1] if identity[0] == 1 else {},
        }
        return (1, {"dna": dna}, None)

    def CompareDna(self, params):
        dna1 = self._p(params, "dna1", {})
        dna2 = self._p(params, "dna2", {})
        if not isinstance(dna1, dict) or not isinstance(dna2, dict):
            return (0, None, ("INVALID_DNA", "dna1 and dna2 must be dicts", 0))
        diffs = []
        total_keys = 0
        matching_keys = 0
        all_keys = set(list(dna1.keys()) + list(dna2.keys()))
        for key in all_keys:
            total_keys = total_keys + 1
            v1 = dna1.get(key)
            v2 = dna2.get(key)
            if v1 == v2:
                matching_keys = matching_keys + 1
            else:
                diffs.append({"key": key, "dna1": v1, "dna2": v2})
        similarity = round((matching_keys / total_keys * 100) if total_keys else 0, 2)
        return (1, {"differences": diffs, "similarity": similarity,
                    "matched": matching_keys, "total": total_keys}, None)

    def ProjectIdentity(self, params):
        import hashlib
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        class_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        method_count = cur.fetchone()[0]
        cur.execute("SELECT file_name FROM files ORDER BY file_name LIMIT 1")
        row = cur.fetchone()
        project_name = row[0] if row else "unknown"
        combined = json.dumps({
            "project": project_name,
            "files": file_count,
            "classes": class_count,
            "methods": method_count,
        })
        identity = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return (1, {"identity_hash": identity, "project": project_name,
                    "files": file_count, "classes": class_count,
                    "methods": method_count}, None)

    def StyleDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        pascal = 0
        upper = 0
        snake = 0
        camel = 0
        total_classes = 0
        cur.execute("SELECT class_name FROM classes")
        for row in cur.fetchall():
            name = row[0] or ""
            if not name:
                continue
            total_classes = total_classes + 1
            if name and name[0].isupper() and "_" not in name:
                pascal = pascal + 1
            elif "_" in name and name.isupper():
                upper = upper + 1
            elif "_" in name:
                snake = snake + 1
            else:
                camel = camel + 1
        pascal_ratio = round(pascal / total_classes, 4) if total_classes else 0
        upper_ratio = round(upper / total_classes, 4) if total_classes else 0
        snake_ratio = round(snake / total_classes, 4) if total_classes else 0
        cur.execute("SELECT AVG(line_count) FROM methods")
        avg_lines = cur.fetchone()[0] or 0
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg_complexity = cur.fetchone()[0] or 0
        cur.execute("SELECT AVG(returns_tuple3) FROM methods")
        tuple3_ratio = cur.fetchone()[0] or 0
        return (1, {
            "pascal_classes": pascal,
            "upper_classes": upper,
            "snake_classes": snake,
            "camel_classes": camel,
            "total_classes": total_classes,
            "pascal_ratio": pascal_ratio,
            "upper_ratio": upper_ratio,
            "snake_ratio": snake_ratio,
            "avg_method_lines": round(avg_lines, 2),
            "avg_complexity": round(avg_complexity, 2),
            "tuple3_ratio": round(tuple3_ratio, 4),
        }, None)

    def ArchitectureDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT parent FROM classes WHERE parent IS NOT NULL AND parent != ''")
        parents = set(r[0] for r in cur.fetchall())
        hierarchy_depth = len(parents)
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='depends_on'")
        coupling = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        total_edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT file_name) FROM files")
        layer_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        total_classes = cur.fetchone()[0]
        density = round(coupling / total_classes, 4) if total_classes else 0
        return (1, {
            "hierarchy_depth": hierarchy_depth,
            "coupling_edges": coupling,
            "total_edges": total_edges,
            "layer_count": layer_count,
            "dependency_density": density,
        }, None)

    def ErrorDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT error_type, COUNT(*) FROM knowledge "
                    "WHERE error_type IS NOT NULL AND error_type != '' "
                    "GROUP BY error_type ORDER BY COUNT(*) DESC")
        rows = cur.fetchall()
        distribution = {r[0]: r[1] for r in rows}
        total = sum(distribution.values()) if distribution else 0
        most_common = rows[0][0] if rows else None
        return (1, {
            "error_distribution": distribution,
            "total_errors": total,
            "most_common_error": most_common,
        }, None)

    def FixDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT fix_applied, COUNT(*), AVG(confidence), "
                    "SUM(CASE WHEN fix_result='success' THEN 1 ELSE 0 END) "
                    "FROM knowledge WHERE fix_applied IS NOT NULL "
                    "AND fix_applied != '' GROUP BY fix_applied "
                    "ORDER BY COUNT(*) DESC")
        rows = cur.fetchall()
        distribution = {}
        for r in rows:
            fix = r[0]
            count = r[1] or 0
            avg_conf = r[2] or 0
            success = r[3] or 0
            rate = round(success / count, 4) if count else 0
            distribution[fix] = {
                "count": count,
                "avg_confidence": round(avg_conf, 4),
                "success_count": success,
                "success_rate": rate,
            }
        most_common = rows[0][0] if rows else None
        return (1, {
            "fix_distribution": distribution,
            "most_common_fix": most_common,
        }, None)

    def NamingDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        prefixes = {}
        suffixes = {}
        cur.execute("SELECT method_name FROM methods WHERE method_name IS NOT NULL")
        for row in cur.fetchall():
            name = row[0] or ""
            if not name or len(name) < 3:
                continue
            prefix = name[:3]
            suffix = name[-3:]
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
            suffixes[suffix] = suffixes.get(suffix, 0) + 1
        top_prefixes = sorted(prefixes.items(), key=lambda x: x[1], reverse=True)[:10]
        top_suffixes = sorted(suffixes.items(), key=lambda x: x[1], reverse=True)[:10]
        return (1, {
            "top_prefixes": [{"prefix": p, "count": c} for p, c in top_prefixes],
            "top_suffixes": [{"suffix": s, "count": c} for s, c in top_suffixes],
        }, None)

    def DependencyDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='imports'")
        import_edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='depends_on'")
        depends_edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM files")
        total_files = cur.fetchone()[0]
        density = round(import_edges / total_files, 4) if total_files else 0
        cur.execute("SELECT dst_id, COUNT(*) FROM edges WHERE edge_type='imports' "
                    "GROUP BY dst_id ORDER BY COUNT(*) DESC LIMIT 10")
        top_deps = [{"module": r[0], "count": r[1]} for r in cur.fetchall()]
        return (1, {
            "import_edges": import_edges,
            "depends_edges": depends_edges,
            "total_files": total_files,
            "import_density": density,
            "most_depended_modules": top_deps,
        }, None)

    def RuntimeDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity) FROM methods")
        avg_complexity = cur.fetchone()[0] or 0
        cur.execute("SELECT method_name, calls FROM methods "
                    "WHERE calls IS NOT NULL AND calls != '' "
                    "ORDER BY length(calls) DESC LIMIT 10")
        call_freq = [{"method": r[0], "call_list_size": len(r[1] or "")} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1")
        print_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total_methods = cur.fetchone()[0]
        print_ratio = round(print_count / total_methods, 4) if total_methods else 0
        return (1, {
            "avg_complexity": round(avg_complexity, 2),
            "call_frequency_top": call_freq,
            "print_statement_count": print_count,
            "print_ratio": print_ratio,
        }, None)

