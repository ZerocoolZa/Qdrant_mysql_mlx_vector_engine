#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/knowledge_graph_engine.py"
# date="2026-06-27" author="Cascade" session_id="twin-rewrite"
# context="Section 28: Knowledge Graph -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="knowledge_graph_engine.py" domain="twin_kgraph" authority="KnowledgeGraphEngine"}
# [@SUMMARY]{summary="Knowledge graph authority: files, classes, methods, variables, databases, apis, gui, threads, errors, fixes."}
# [@CLASS]{class="KnowledgeGraphEngine" domain="kgraph" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="files" type="command"}
# [@METHOD]{method="classes" type="command"}
# [@METHOD]{method="methods" type="command"}
# [@METHOD]{method="variables" type="command"}
# [@METHOD]{method="databases" type="command"}
# [@METHOD]{method="apis" type="command"}
# [@METHOD]{method="gui" type="command"}
# [@METHOD]{method="threads" type="command"}
# [@METHOD]{method="errors" type="command"}
# [@METHOD]{method="fixes" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class KnowledgeGraphEngine:
    """Authority for querying knowledge graph by entity type."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "result_limit": 100,
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
        if command == "files":
            return self.Files(params)
        elif command == "classes":
            return self.Classes(params)
        elif command == "methods":
            return self.Methods(params)
        elif command == "variables":
            return self.Variables(params)
        elif command == "databases":
            return self.Databases(params)
        elif command == "apis":
            return self.Apis(params)
        elif command == "gui":
            return self.Gui(params)
        elif command == "threads":
            return self.Threads(params)
        elif command == "errors":
            return self.Errors(params)
        elif command == "fixes":
            return self.Fixes(params)
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

    def Files(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT file_id, file_path, hash, line_count, language, status "
                "FROM files ORDER BY file_id LIMIT ?", (limit,)
            )
            files = [{"file_id": r[0], "file_path": r[1], "hash": r[2],
                      "line_count": r[3], "language": r[4], "status": r[5]}
                     for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM files")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"files": files, "count": len(files), "total": total}, None)

    def Classes(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        file_id = self._p(params, "file_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if file_id:
                cur.execute(
                    "SELECT class_id, class_name, file_id, method_count, parent, has_run_method "
                    "FROM classes WHERE file_id=? ORDER BY class_id LIMIT ?",
                    (file_id, limit),
                )
            else:
                cur.execute(
                    "SELECT class_id, class_name, file_id, method_count, parent, has_run_method "
                    "FROM classes ORDER BY class_id LIMIT ?",
                    (limit,),
                )
            classes = [{"class_id": r[0], "class_name": r[1], "file_id": r[2],
                        "method_count": r[3], "parent": r[4], "has_run": r[5]}
                       for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM classes")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"classes": classes, "count": len(classes), "total": total}, None)

    def Methods(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        class_id = self._p(params, "class_id")
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            if class_id:
                cur.execute(
                    "SELECT method_id, method_name, class_id, signature, cyclomatic_complexity "
                    "FROM methods WHERE class_id=? ORDER BY method_id LIMIT ?",
                    (class_id, limit),
                )
            else:
                cur.execute(
                    "SELECT method_id, method_name, class_id, signature, cyclomatic_complexity "
                    "FROM methods ORDER BY method_id LIMIT ?",
                    (limit,),
                )
            methods = [{"method_id": r[0], "method_name": r[1], "class_id": r[2],
                        "signature": r[3], "complexity": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM methods")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"methods": methods, "count": len(methods), "total": total}, None)

    def Variables(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT DISTINCT edge_type, src_id, src_type, dst_id, dst_type "
                "FROM edges WHERE edge_type IN ('uses_variable', 'reads', 'writes', 'assigns') "
                "LIMIT ?",
                (limit,),
            )
            variables = [{"edge_type": r[0], "src_id": r[1], "src_type": r[2],
                          "dst_id": r[3], "dst_type": r[4]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"variables": variables, "count": len(variables)}, None)

    def Databases(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE '%sqlite3%' OR method_code LIKE '%CREATE TABLE%' "
                "OR method_code LIKE '%SELECT %FROM%' OR method_code LIKE '%INSERT INTO%' "
                "LIMIT ?",
                (limit,),
            )
            databases = [{"method_id": r[0], "method_name": r[1],
                          "has_db_code": True} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"databases": databases, "count": len(databases)}, None)

    def Apis(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE '%request%' OR method_code LIKE '%api%' "
                "OR method_code LIKE '%endpoint%' OR method_code LIKE '%http%' "
                "LIMIT ?",
                (limit,),
            )
            apis = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"apis": apis, "count": len(apis)}, None)

    def Gui(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT class_id, class_name FROM classes "
                "WHERE class_name LIKE '%Window%' OR class_name LIKE '%Widget%' "
                "OR class_name LIKE '%Dialog%' OR class_name LIKE '%Frame%' "
                "OR class_name LIKE '%Panel%' OR class_name LIKE '%Viewer%' "
                "LIMIT ?",
                (limit,),
            )
            gui = [{"class_id": r[0], "class_name": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"gui": gui, "count": len(gui)}, None)

    def Threads(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT method_id, method_name, method_code FROM methods "
                "WHERE method_code LIKE '%threading%' OR method_code LIKE '%Thread%' "
                "OR method_code LIKE '%async%' OR method_code LIKE '%await%' "
                "OR method_code LIKE '%concurrent%' LIMIT ?",
                (limit,),
            )
            threads = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"threads": threads, "count": len(threads)}, None)

    def Errors(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, error_type, problem, confidence, created "
                "FROM knowledge ORDER BY knowledge_id DESC LIMIT ?",
                (limit,),
            )
            errors = [{"knowledge_id": r[0], "method_id": r[1], "error_type": r[2],
                       "problem": r[3], "confidence": r[4], "created": r[5]}
                      for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM knowledge")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"errors": errors, "count": len(errors), "total": total}, None)

    def Fixes(self, params):
        limit = self._p(params, "limit", self.state["config"]["result_limit"])
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT knowledge_id, method_id, answer, evidence, confidence, created "
                "FROM knowledge WHERE answer IS NOT NULL AND answer != '' "
                "ORDER BY confidence DESC, knowledge_id DESC LIMIT ?",
                (limit,),
            )
            fixes = [{"knowledge_id": r[0], "method_id": r[1], "answer": r[2],
                      "evidence": r[3], "confidence": r[4], "created": r[5]}
                     for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL AND answer != ''")
            total = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("QUERY_FAILED", str(exc), 0))
        return (1, {"fixes": fixes, "count": len(fixes), "total": total}, None)
