#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/gap_analysis_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 35: Gap Analysis -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="gap_analysis_engine.py" domain="twin_gap" authority="GapAnalysisEngine"}
# [@SUMMARY]{summary="Gap analysis authority: detect missing methods, detect missing classes, detect missing edges, detect missing knowledge, detect missing tests, detect missing VBStyle, detect missing dependencies, detect missing observations, detect missing snapshots, gap report."}
# [@CLASS]{class="GapAnalysisEngine" domain="gap_analysis" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="detect_missing_methods" type="command"}
# [@METHOD]{method="detect_missing_classes" type="command"}
# [@METHOD]{method="detect_missing_edges" type="command"}
# [@METHOD]{method="detect_missing_knowledge" type="command"}
# [@METHOD]{method="detect_missing_tests" type="command"}
# [@METHOD]{method="detect_missing_vbstyle" type="command"}
# [@METHOD]{method="detect_missing_dependencies" type="command"}
# [@METHOD]{method="detect_missing_observations" type="command"}
# [@METHOD]{method="detect_missing_snapshots" type="command"}
# [@METHOD]{method="gap_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class GapAnalysisEngine:
    """Authority for detecting gaps in project coverage."""

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
        if command == "detect_missing_methods":
            return self.DetectMissingMethods(params)
        elif command == "detect_missing_classes":
            return self.DetectMissingClasses(params)
        elif command == "detect_missing_edges":
            return self.DetectMissingEdges(params)
        elif command == "detect_missing_knowledge":
            return self.DetectMissingKnowledge(params)
        elif command == "detect_missing_tests":
            return self.DetectMissingTests(params)
        elif command == "detect_missing_vbstyle":
            return self.DetectMissingVbstyle(params)
        elif command == "detect_missing_dependencies":
            return self.DetectMissingDependencies(params)
        elif command == "detect_missing_observations":
            return self.DetectMissingObservations(params)
        elif command == "detect_missing_snapshots":
            return self.DetectMissingSnapshots(params)
        elif command == "gap_report":
            return self.GapReport(params)
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

    def DetectMissingMethods(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT class_id, class_name FROM classes WHERE class_id NOT IN "
            "(SELECT DISTINCT class_id FROM methods WHERE class_id IS NOT NULL)"
        )
        missing = [{"class_id": r[0], "class_name": r[1],
                    "gap": "no_methods"} for r in cur.fetchall()]
        return (1, {"missing_methods": missing, "count": len(missing)}, None)

    def DetectMissingClasses(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name FROM files WHERE file_id NOT IN "
            "(SELECT DISTINCT file_id FROM classes WHERE file_id IS NOT NULL) "
            "AND extension='.py'"
        )
        missing = [{"file_id": r[0], "file_name": r[1],
                    "gap": "no_classes"} for r in cur.fetchall()]
        return (1, {"missing_classes": missing, "count": len(missing)}, None)

    def DetectMissingEdges(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT src_id FROM edges WHERE src_type='method') "
            "AND method_id NOT IN "
            "(SELECT dst_id FROM edges WHERE dst_type='method')"
        )
        missing = [{"method_id": r[0], "method_name": r[1],
                    "gap": "no_edges"} for r in cur.fetchall()]
        return (1, {"missing_edges": missing, "count": len(missing)}, None)

    def DetectMissingKnowledge(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT DISTINCT method_id FROM knowledge WHERE method_id IS NOT NULL) "
            "AND (has_print=1 OR has_decorator=1 OR has_self_underscore=1 OR returns_tuple3=0)"
        )
        missing = [{"method_id": r[0], "method_name": r[1],
                    "gap": "no_knowledge"} for r in cur.fetchall()]
        return (1, {"missing_knowledge": missing, "count": len(missing)}, None)

    def DetectMissingTests(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT DISTINCT method_id FROM attempts WHERE method_id IS NOT NULL)"
        )
        missing = [{"method_id": r[0], "method_name": r[1],
                    "gap": "no_tests"} for r in cur.fetchall()]
        return (1, {"missing_tests": missing, "count": len(missing)}, None)

    def DetectMissingVbstyle(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE has_print=1 OR "
            "has_decorator=1 OR has_self_underscore=1 OR returns_tuple3=0"
        )
        missing = [{"method_id": r[0], "method_name": r[1],
                    "gap": "vbstyle_violation"} for r in cur.fetchall()]
        cur.execute(
            "SELECT class_id, class_name FROM classes WHERE has_run_method=0"
        )
        for r in cur.fetchall():
            missing.append({"class_id": r[0], "class_name": r[1],
                            "gap": "missing_run"})
        return (1, {"missing_vbstyle": missing, "count": len(missing)}, None)

    def DetectMissingDependencies(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT file_id, file_name, imports FROM files WHERE imports IS NOT NULL "
            "AND imports != '[]'"
        )
        missing = []
        import json
        for row in cur.fetchall():
            imports = json.loads(row[2]) if row[2] else []
            for imp in imports:
                cur.execute(
                    "SELECT COUNT(*) FROM edges WHERE src_type='file' AND src_id=? "
                    "AND evidence LIKE ?",
                    (row[0], "%" + imp + "%"),
                )
                count = cur.fetchone()[0]
                if count == 0:
                    missing.append({"file_id": row[0], "file_name": row[1],
                                    "import": imp, "gap": "no_edge"})
        return (1, {"missing_dependencies": missing[:100],
                    "count": len(missing)}, None)

    def DetectMissingObservations(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT attempt_id FROM attempts WHERE attempt_id NOT IN "
            "(SELECT CAST(subject AS INTEGER) FROM observations WHERE "
            "subject GLOB '[0-9]*')"
        )
        missing = [{"attempt_id": r[0], "gap": "no_observation"} for r in cur.fetchall()]
        return (1, {"missing_observations": missing[:100],
                    "count": len(missing)}, None)

    def DetectMissingSnapshots(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT method_id, method_name FROM methods WHERE method_id NOT IN "
            "(SELECT DISTINCT method_id FROM snapshots WHERE method_id IS NOT NULL)"
        )
        missing = [{"method_id": r[0], "method_name": r[1],
                    "gap": "no_snapshot"} for r in cur.fetchall()]
        return (1, {"missing_snapshots": missing[:100],
                    "count": len(missing)}, None)

    def GapReport(self, params):
        results = {}
        total_gaps = 0
        for step in ("detect_missing_methods", "detect_missing_classes",
                     "detect_missing_edges", "detect_missing_knowledge",
                     "detect_missing_tests", "detect_missing_vbstyle",
                     "detect_missing_dependencies", "detect_missing_observations",
                     "detect_missing_snapshots"):
            res = self.Run(step, params)
            if res[0] == 1:
                results[step] = res[1]
                total_gaps += res[1].get("count", 0)
            else:
                results[step] = {"error": str(res[2])}
        results["total_gaps"] = total_gaps
        results["generated"] = self.Now()[1]
        return (1, results, None)
