#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_qa_engine/ingest_qa_engine.py" date="2026-06-29" author="Devin" session_id="resume-last-session" context="Ingest Dom_qa_engine Python files + CODEBASE question generators into qa_question_kb.db using BCL object model"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print no-decorators"}
# [@FILEID]{id="ingest_qa_engine.py" domain="dom_qa_engine" authority="IngestQaEngine"}
# [@SUMMARY]{summary="Build qa_question_kb.db: 7 tables (files, classes, methods, computational_units, question_generators, question_dimensions, question_categories). Ingests local .py files with BCL/BCL-IR/Graph/VBStyle, copies question generators from CODEBASE MySQL, populates dimensions and categories."}
# [@CLASS]{class="IngestQaEngine" domain="dom_qa_engine" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="CmdCreateDb" type="command"}
# [@METHOD]{method="CmdIngestLocal" type="command"}
# [@METHOD]{method="CmdCopyCodebase" type="command"}
# [@METHOD]{method="CmdPopulateDimensions" type="command"}
# [@METHOD]{method="CmdPopulateCategories" type="command"}
# [@METHOD]{method="CmdReport" type="command"}
# [@METHOD]{method="ExtractBclHeaders" type="helper"}
# [@METHOD]{method="ParseBclIr" type="helper"}
# [@METHOD]{method="BuildFileGraph" type="helper"}
# [@METHOD]{method="BuildClassGraph" type="helper"}
# [@METHOD]{method="BuildMethodGraph" type="helper"}
# [@METHOD]{method="CheckVbstyle" type="helper"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import re
import ast
import json
import hashlib
import sqlite3
import sys

BCL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "Dom_Bcl")
UTILITY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "utility")
QA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(QA_DIR, "qa_question_kb.db")

if BCL_DIR not in sys.path:
    sys.path.insert(0, BCL_DIR)
if UTILITY_DIR not in sys.path:
    sys.path.insert(0, UTILITY_DIR)

from bcl_extractor import FeatureExtractor
from bcl_rules import RuleEngine
from bcl_config import IR_RULES

BCL_HEADER_RE = re.compile(r'^#\s*\[@(GHOST|VBSTYLE|SPEC|FILEID|SUMMARY|CLASS|METHOD)\]\{(.*)\}$')
BCL_KV_INLINE_RE = re.compile(r'\[@(\w+)<([^>]*)>\]')
BCL_KV_COMMENT_RE = re.compile(r'(\w+)="([^"]*)"')

TABLE_DDL = [
    """CREATE TABLE IF NOT EXISTS files (
        file_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        original_filename TEXT NOT NULL,
        bcl              TEXT,
        bcl_ir           TEXT,
        graph            TEXT,
        vbstyle          INTEGER,
        vbstyle_violations TEXT,
        line_count       INTEGER,
        content_hash     TEXT,
        ingested_at      TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS classes (
        class_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id          INTEGER NOT NULL,
        class_name       TEXT NOT NULL,
        bcl              TEXT,
        bcl_ir           TEXT,
        graph            TEXT,
        vbstyle          INTEGER,
        vbstyle_violations TEXT,
        base_class       TEXT,
        start_line       INTEGER,
        end_line         INTEGER,
        FOREIGN KEY (file_id) REFERENCES files(file_id)
    )""",
    """CREATE TABLE IF NOT EXISTS methods (
        method_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id         INTEGER NOT NULL,
        file_id          INTEGER NOT NULL,
        method_name      TEXT NOT NULL,
        bcl              TEXT,
        bcl_ir           TEXT,
        graph            TEXT,
        vbstyle          INTEGER,
        vbstyle_violations TEXT,
        start_line       INTEGER,
        end_line         INTEGER,
        returns_tuple3   INTEGER,
        has_run_dispatch INTEGER,
        FOREIGN KEY (class_id) REFERENCES classes(class_id),
        FOREIGN KEY (file_id) REFERENCES files(file_id)
    )""",
    """CREATE TABLE IF NOT EXISTS computational_units (
        unit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_name        TEXT NOT NULL,
        class_id         INTEGER,
        method_id        INTEGER,
        file_id          INTEGER NOT NULL,
        bcl              TEXT,
        bcl_ir           TEXT,
        graph            TEXT,
        vbstyle          INTEGER,
        vbstyle_violations TEXT,
        composite_key    TEXT UNIQUE,
        status           TEXT DEFAULT 'active',
        description      TEXT,
        FOREIGN KEY (class_id) REFERENCES classes(class_id),
        FOREIGN KEY (method_id) REFERENCES methods(method_id),
        FOREIGN KEY (file_id) REFERENCES files(file_id)
    )""",
    """CREATE TABLE IF NOT EXISTS question_generators (
        gen_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name       TEXT NOT NULL,
        source_file_id   INTEGER,
        source_filename  TEXT,
        source_full_path TEXT,
        source_line_count INTEGER,
        tier             TEXT,
        bcl              TEXT,
        bcl_ir           TEXT,
        vbstyle          INTEGER,
        vbstyle_violations TEXT,
        source_code      TEXT,
        ingested         INTEGER DEFAULT 0,
        created_at       TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS question_dimensions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        dimension        TEXT NOT NULL,
        sector           TEXT NOT NULL,
        description      TEXT,
        aspect_template  TEXT,
        question_template TEXT,
        UNIQUE(dimension, sector, aspect_template)
    )""",
    """CREATE TABLE IF NOT EXISTS question_categories (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        category         TEXT UNIQUE NOT NULL,
        description      TEXT
    )""",
]

QUESTION_GENERATORS = [
    {"class_name": "QuestionEngine", "file_id": 45914, "filename": "dom_knowledge.py", "tier": "engine"},
    {"class_name": "InterrogationAuthority", "file_id": 40817, "filename": "migrate_sqlite_to_mysql.py", "tier": "engine"},
    {"class_name": "QuestionEngine", "file_id": 306719, "filename": "Core_QAEngine.py", "tier": "engine"},
    {"class_name": "SmartQuestionTackleApp", "file_id": 320162, "filename": "smart_question_tackle_app.py", "tier": "engine"},
    {"class_name": "EnhancedQuestionDB", "file_id": 79993, "filename": "enhanced_question_db.py", "tier": "engine"},
    {"class_name": "ChatInterrogationEngine", "file_id": 111583, "filename": "chat_interrogation_engine.py", "tier": "engine"},
    {"class_name": "DynamicQuestionGenerator", "file_id": 111583, "filename": "chat_interrogation_engine.py", "tier": "engine"},
    {"class_name": "CodeQuestionProofEngine", "file_id": 61275, "filename": "Unit_CodeQuestionProofEngine.py", "tier": "engine"},
    {"class_name": "QuestioningEngine", "file_id": 311293, "filename": "maxed_thinking_reasoning_engine.py", "tier": "engine"},
    {"class_name": "QuestionLogic", "file_id": 21429, "filename": "maximum_freedom_cognitive_model.py", "tier": "engine"},
    {"class_name": "ModelQuestionUnit", "file_id": 52917, "filename": "Reg_gui.py", "tier": "node"},
    {"class_name": "UncertaintyQueue", "file_id": 67053, "filename": "fv.py", "tier": "engine"},
    {"class_name": "DatabaseQuestionEngine", "file_id": 79945, "filename": "question_gui_db.py", "tier": "engine"},
    {"class_name": "BookQuestionGenerator", "file_id": 324741, "filename": "book_question_generator.py", "tier": "engine"},
    {"class_name": "InvestigationQuestion", "file_id": 313628, "filename": "LIB_INVESTIGATOR.py", "tier": "node"},
    {"class_name": "QuestionToLawClosure_V3", "file_id": 70516, "filename": "Unit_QuestionToLawClosure_V3.py", "tier": "engine"},
    {"class_name": "QuestionWeigherV2", "file_id": 60594, "filename": "Unit_QuestionWeigherV2.py", "tier": "engine"},
    {"class_name": "QuestionCascadeEngine", "file_id": 227893, "filename": "Not_in_Service_MEMBUS_V3.py", "tier": "engine"},
    {"class_name": "QuestionNode", "file_id": 358066, "filename": "Lib_PredictiveWorldModel_chat169_dup2.py", "tier": "node"},
    {"class_name": "QuestionThinkingAI", "file_id": 223006, "filename": "question_thinking_ai_framework.py", "tier": "engine"},
    {"class_name": "RankedQuestion", "file_id": 74272, "filename": "Question_Engine.py", "tier": "engine"},
    {"class_name": "QuestionWeigher", "file_id": 60602, "filename": "Unit_QuestionWeigher.py", "tier": "engine"},
    {"class_name": "L8_QuestionGate", "file_id": 70024, "filename": "Unit_L8_QuestionGate.py", "tier": "engine"},
    {"class_name": "CuriosityEngine", "file_id": 65436, "filename": "Core_CuriosityEngine.py", "tier": "engine"},
    {"class_name": "OpenAIQuestionGenerator", "file_id": 46640, "filename": "openai_question_generator.py", "tier": "engine"},
    {"class_name": "LLMQuestionGenerator", "file_id": 175627, "filename": "llm_generators.py", "tier": "engine"},
    {"class_name": "Cls_QuestionEngine", "file_id": 220469, "filename": "Cls_QuestionEngine.py", "tier": "engine"},
    {"class_name": "Cls_Question", "file_id": 229451, "filename": "Cls_Question.py", "tier": "node"},
    {"class_name": "ComBookQuestionGenerator", "file_id": 45475, "filename": "lib_com_book_question_generator.py", "tier": "engine"},
    {"class_name": "ComVB2010QuestionGenerator", "file_id": 45258, "filename": "lib_com_v_b2010_question_generator.py", "tier": "engine"},
]

LOCAL_GENERATORS = [
    {"class_name": "QuestionAgent", "path": os.path.join(UTILITY_DIR, "question_agent.py"), "tier": "utility"},
    {"class_name": "QuestionStore", "path": os.path.join(UTILITY_DIR, "question_store.py"), "tier": "utility"},
    {"class_name": "QuestionDimensions", "path": os.path.join(UTILITY_DIR, "question_dimensions.py"), "tier": "utility"},
    {"class_name": "CuriosityController", "path": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Dom_Graph", "Dom_Graph_EngineV2.py"), "tier": "utility"},
]

CATEGORY_DESCRIPTIONS = {
    "existence": "Does it exist? In what form?",
    "time": "When did it happen? Timeline?",
    "versions": "Which version? Changes over time?",
    "location": "Where is it? Path? Container?",
    "dependencies": "What depends on it? What does it depend on?",
    "authorship": "Who created it? Who modified it?",
    "chat_history": "What was discussed in chat sessions?",
    "database_state": "What is in the database? Schema? Rows?",
    "errors": "What errors occurred? Root cause?",
    "patterns": "What patterns are present? Repeated structures?",
    "environment": "What is the runtime environment? OS? Config?",
    "naming": "What is it called? Naming conventions?",
    "state": "What is the current state? Active? Inactive?",
    "relationships": "How do entities relate? Edges? Hierarchy?",
    "assumptions": "What assumptions are being made?",
    "followup_yes": "If yes, what follows?",
    "followup_no": "If no, what follows?",
    "meta": "Questions about questions themselves.",
}


class IngestQaEngine:
    """Ingest Dom_qa_engine files + CODEBASE question generators into qa_question_kb.db."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": DB_PATH, "qa_dir": QA_DIR, "bcl_dir": BCL_DIR},
            "conn": None,
            "extractor": FeatureExtractor(mem=mem),
            "rule_engine": RuleEngine(param={"rules": IR_RULES}),
            "files_ingested": 0,
            "classes_ingested": 0,
            "methods_ingested": 0,
            "cus_ingested": 0,
            "generators_copied": 0,
            "dimensions_populated": 0,
            "categories_populated": 0,
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "create_db": self.CmdCreateDb,
            "ingest_local": self.CmdIngestLocal,
            "copy_codebase": self.CmdCopyCodebase,
            "populate_dimensions": self.CmdPopulateDimensions,
            "populate_categories": self.CmdPopulateCategories,
            "report": self.CmdReport,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "all": self.CmdAll,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)

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

    def ConnectDb(self):
        if self.state["conn"] is not None:
            return (1, True, None)
        db_path = self.state["config"]["db_path"]
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self.state["conn"] = conn
        return (1, True, None)

    def CmdAll(self, params):
        steps = ["create_db", "ingest_local", "copy_codebase", "populate_dimensions", "populate_categories", "report"]
        results = {}
        for step in steps:
            handler = {
                "create_db": self.CmdCreateDb,
                "ingest_local": self.CmdIngestLocal,
                "copy_codebase": self.CmdCopyCodebase,
                "populate_dimensions": self.CmdPopulateDimensions,
                "populate_categories": self.CmdPopulateCategories,
                "report": self.CmdReport,
            }[step]
            r = handler(params)
            results[step] = {"ok": r[0], "data": r[1], "error": r[2]}
            if r[0] == 0 and step != "copy_codebase":
                return (0, results, ("STEP_FAILED", "Step " + step + " failed", 0))
        return (1, results, None)

    def CmdCreateDb(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        for ddl in TABLE_DDL:
            conn.execute(ddl)
        conn.commit()
        return (1, {"tables_created": len(TABLE_DDL)}, None)

    def CmdIngestLocal(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        conn.execute("DELETE FROM computational_units")
        conn.execute("DELETE FROM methods")
        conn.execute("DELETE FROM classes")
        conn.execute("DELETE FROM files")
        qa_dir = self.state["config"]["qa_dir"]
        py_files = sorted([f for f in os.listdir(qa_dir) if f.endswith(".py") and f != "ingest_qa_engine.py"])
        files_count = 0
        classes_count = 0
        methods_count = 0
        cus_count = 0
        for fname in py_files:
            fpath = os.path.join(qa_dir, fname)
            r = self.IngestOneFile(conn, fname, fpath)
            if r[0] == 1:
                files_count += 1
                classes_count += r[1].get("classes", 0)
                methods_count += r[1].get("methods", 0)
                cus_count += r[1].get("cus", 0)
            else:
                self.state["errors"].append({"file": fname, "error": r[2]})
        conn.commit()
        self.state["files_ingested"] = files_count
        self.state["classes_ingested"] = classes_count
        self.state["methods_ingested"] = methods_count
        self.state["cus_ingested"] = cus_count
        return (1, {"files": files_count, "classes": classes_count, "methods": methods_count, "cus": cus_count}, None)

    def IngestOneFile(self, conn, fname, fpath):
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError as exc:
            return (0, None, ("FILE_READ_ERROR", str(exc), 0))
        source_lines = source.splitlines()
        content_hash = hashlib.md5(source.encode("utf-8")).hexdigest()
        bcl_raw = self.ExtractBclHeaders(source_lines)
        bcl_ir = self.ParseBclIr(bcl_raw) if bcl_raw else None
        try:
            tree = ast.parse(source, filename=fpath)
        except SyntaxError as exc:
            tree = None
            self.state["errors"].append({"file": fname, "error": "SyntaxError: " + str(exc)})
        file_graph = self.BuildFileGraph(tree, fname) if tree else json.dumps({"nodes": [], "edges": []})
        vbstyle_result = self.CheckVbstyle(tree, source_lines) if tree else (None, None)
        vbstyle_flag = vbstyle_result[0]
        vbstyle_violations = vbstyle_result[1]
        cursor = conn.execute(
            "INSERT INTO files (original_filename, bcl, bcl_ir, graph, vbstyle, vbstyle_violations, line_count, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fname, bcl_raw, json.dumps(bcl_ir) if bcl_ir else None, file_graph, vbstyle_flag, json.dumps(vbstyle_violations) if vbstyle_violations else None, len(source_lines), content_hash),
        )
        file_id = cursor.lastrowid
        classes_count = 0
        methods_count = 0
        cus_count = 0
        if tree is None:
            return (1, {"file_id": file_id, "classes": 0, "methods": 0, "cus": 0}, None)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            cr = self.IngestOneClass(conn, node, file_id, source_lines, fname)
            if cr[0] == 1:
                classes_count += 1
                methods_count += cr[1].get("methods", 0)
                cus_count += cr[1].get("cus", 0)
        return (1, {"file_id": file_id, "classes": classes_count, "methods": methods_count, "cus": cus_count}, None)

    def IngestOneClass(self, conn, node, file_id, source_lines, fname):
        class_name = node.name
        bases_clean = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases_clean.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases_clean.append(b.attr)
            else:
                bases_clean.append("complex")
        base_class = ",".join(bases_clean) if bases_clean else None
        class_graph = self.BuildClassGraph(node)
        cf_result = self.state["extractor"].Run("extract_class_features", {"node": node, "source_lines": source_lines})
        vbstyle_flag = None
        vbstyle_violations = None
        if cf_result[0] == 1:
            cf = cf_result[1]
            vr = self.state["rule_engine"].Run("evaluate_class", {"features": cf})
            if vr[0] == 1:
                vbstyle_violations = vr[1]["violations"]
                vbstyle_flag = 1 if len(vbstyle_violations) == 0 else 0
        class_bcl = self.ExtractClassBcl(source_lines, node.lineno)
        class_bcl_ir = self.ParseBclIr(class_bcl) if class_bcl else None
        cursor = conn.execute(
            "INSERT INTO classes (file_id, class_name, bcl, bcl_ir, graph, vbstyle, vbstyle_violations, base_class, start_line, end_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, class_name, class_bcl, json.dumps(class_bcl_ir) if class_bcl_ir else None, class_graph, vbstyle_flag, json.dumps(vbstyle_violations) if vbstyle_violations else None, base_class, node.lineno, getattr(node, "end_lineno", node.lineno)),
        )
        class_id = cursor.lastrowid
        methods_count = 0
        cus_count = 0
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            mr = self.IngestOneMethod(conn, child, class_id, file_id, source_lines, class_name, fname)
            if mr[0] == 1:
                methods_count += 1
                method_id = mr[1]["method_id"]
                unit_name = class_name + "." + child.name
                composite_key = str(file_id) + ":" + class_name + ":" + child.name
                conn.execute(
                    "INSERT OR IGNORE INTO computational_units (unit_name, class_id, method_id, file_id, bcl, bcl_ir, graph, vbstyle, vbstyle_violations, composite_key, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (unit_name, class_id, method_id, file_id, class_bcl, json.dumps(class_bcl_ir) if class_bcl_ir else None, class_graph, vbstyle_flag, json.dumps(vbstyle_violations) if vbstyle_violations else None, composite_key, "CU for " + unit_name),
                )
                cus_count += 1
        return (1, {"class_id": class_id, "methods": methods_count, "cus": cus_count}, None)

    def IngestOneMethod(self, conn, node, class_id, file_id, source_lines, class_name, fname):
        method_name = node.name
        method_graph = self.BuildMethodGraph(node)
        mf_result = self.state["extractor"].Run("extract_method_features", {"node": node, "class_name": class_name})
        vbstyle_flag = None
        vbstyle_violations = None
        returns_tuple3 = 0
        has_run_dispatch = 1 if method_name == "Run" else 0
        if mf_result[0] == 1:
            mf = mf_result[1]
            returns_tuple3 = 1 if mf.get("returns_tuple3") else 0
            vr = self.state["rule_engine"].Run("evaluate_method", {"features": mf})
            if vr[0] == 1:
                vbstyle_violations = vr[1]["violations"]
                vbstyle_flag = 1 if len(vbstyle_violations) == 0 else 0
        method_bcl = self.ExtractMethodBcl(source_lines, node.lineno)
        method_bcl_ir = self.ParseBclIr(method_bcl) if method_bcl else None
        cursor = conn.execute(
            "INSERT INTO methods (class_id, file_id, method_name, bcl, bcl_ir, graph, vbstyle, vbstyle_violations, start_line, end_line, returns_tuple3, has_run_dispatch) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (class_id, file_id, method_name, method_bcl, json.dumps(method_bcl_ir) if method_bcl_ir else None, method_graph, vbstyle_flag, json.dumps(vbstyle_violations) if vbstyle_violations else None, node.lineno, getattr(node, "end_lineno", node.lineno), returns_tuple3, has_run_dispatch),
        )
        return (1, {"method_id": cursor.lastrowid}, None)

    def CmdCopyCodebase(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        conn.execute("DELETE FROM question_generators")
        copied = 0
        try:
            import mysql.connector as mysql_conn
        except ImportError:
            self.state["errors"].append({"step": "copy_codebase", "error": "mysql.connector not installed"})
            return (1, {"generators": 0, "note": "mysql.connector not installed, skipped"}, None)
        try:
            mconn = mysql_conn.connect(host="localhost", user="root", password="", database="CODEBASE", autocommit=True)
        except Exception as exc:
            self.state["errors"].append({"step": "copy_codebase", "error": str(exc)})
            return (1, {"generators": 0, "note": "CODEBASE MySQL connection failed: " + str(exc)}, None)
        mcur = mconn.cursor()
        for gen in QUESTION_GENERATORS:
            try:
                mcur.execute("SELECT content FROM python_files WHERE id = %s", (gen["file_id"],))
                row = mcur.fetchone()
                if row is None:
                    self.state["errors"].append({"generator": gen["class_name"], "error": "file_id " + str(gen["file_id"]) + " not found"})
                    continue
                source_code = row[0]
                if isinstance(source_code, bytes):
                    source_code = source_code.decode("utf-8", errors="replace")
                source_lines = source_code.splitlines()
                bcl_raw = self.ExtractBclHeaders(source_lines)
                bcl_ir = self.ParseBclIr(bcl_raw) if bcl_raw else None
                vbstyle_flag = None
                vbstyle_violations = None
                if bcl_raw:
                    try:
                        tree = ast.parse(source_code)
                        ff_result = self.state["extractor"].Run("extract_file_features", {"tree": tree, "source_lines": source_lines})
                        if ff_result[0] == 1:
                            vr = self.state["rule_engine"].Run("evaluate_file", {"features": ff_result[1]})
                            if vr[0] == 1:
                                vbstyle_violations = vr[1]["violations"]
                                vbstyle_flag = 1 if len(vbstyle_violations) == 0 else 0
                    except SyntaxError:
                        vbstyle_flag = 0
                conn.execute(
                    "INSERT INTO question_generators (class_name, source_file_id, source_filename, source_line_count, tier, bcl, bcl_ir, vbstyle, vbstyle_violations, source_code, ingested) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (gen["class_name"], gen["file_id"], gen["filename"], len(source_lines), gen["tier"], bcl_raw, json.dumps(bcl_ir) if bcl_ir else None, vbstyle_flag, json.dumps(vbstyle_violations) if vbstyle_violations else None, source_code),
                )
                copied += 1
            except Exception as exc:
                self.state["errors"].append({"generator": gen["class_name"], "error": str(exc)})
        mcur.close()
        mconn.close()
        for gen in LOCAL_GENERATORS:
            fpath = gen["path"]
            if not os.path.exists(fpath):
                self.state["errors"].append({"generator": gen["class_name"], "error": "file not found: " + fpath})
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    source_code = fh.read()
            except OSError as exc:
                self.state["errors"].append({"generator": gen["class_name"], "error": str(exc)})
                continue
            source_lines = source_code.splitlines()
            bcl_raw = self.ExtractBclHeaders(source_lines)
            bcl_ir = self.ParseBclIr(bcl_raw) if bcl_raw else None
            conn.execute(
                "INSERT INTO question_generators (class_name, source_filename, source_full_path, source_line_count, tier, bcl, bcl_ir, source_code, ingested) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (gen["class_name"], os.path.basename(fpath), fpath, len(source_lines), gen["tier"], bcl_raw, json.dumps(bcl_ir) if bcl_ir else None, source_code),
            )
            copied += 1
        conn.commit()
        self.state["generators_copied"] = copied
        return (1, {"generators": copied}, None)

    def CmdPopulateDimensions(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        conn.execute("DELETE FROM question_dimensions")
        try:
            from question_dimensions import DIMENSIONS
        except ImportError as exc:
            return (0, None, ("IMPORT_ERROR", str(exc), 0))
        count = 0
        for dim_name, dim_data in DIMENSIONS.items():
            dim_desc = dim_data.get("description", "")
            sectors = dim_data.get("sectors", {})
            for sector_name, sector_desc in sectors.items():
                aspect = dim_desc
                question = sector_desc
                conn.execute(
                    "INSERT OR IGNORE INTO question_dimensions (dimension, sector, description, aspect_template, question_template) VALUES (?, ?, ?, ?, ?)",
                    (dim_name, sector_name, sector_desc, aspect, question),
                )
                count += 1
        conn.commit()
        self.state["dimensions_populated"] = count
        return (1, {"dimensions": count}, None)

    def CmdPopulateCategories(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        conn.execute("DELETE FROM question_categories")
        try:
            from question_store import CATEGORIES
        except ImportError as exc:
            return (0, None, ("IMPORT_ERROR", str(exc), 0))
        count = 0
        for cat in CATEGORIES:
            desc = CATEGORY_DESCRIPTIONS.get(cat, "")
            conn.execute(
                "INSERT OR IGNORE INTO question_categories (category, description) VALUES (?, ?)",
                (cat, desc),
            )
            count += 1
        conn.commit()
        self.state["categories_populated"] = count
        return (1, {"categories": count}, None)

    def CmdReport(self, params):
        cr = self.ConnectDb()
        if cr[0] == 0:
            return cr
        conn = self.state["conn"]
        tables = ["files", "classes", "methods", "computational_units", "question_generators", "question_dimensions", "question_categories"]
        counts = {}
        for t in tables:
            cur = conn.execute("SELECT COUNT(*) FROM " + t)
            counts[t] = cur.fetchone()[0]
        error_count = len(self.state["errors"])
        report = {"counts": counts, "errors": error_count, "state": {k: v for k, v in self.state.items() if k not in ("conn", "extractor", "rule_engine")}}
        return (1, report, None)

    def ExtractBclHeaders(self, source_lines):
        lines = []
        for line in source_lines[:30]:
            if BCL_HEADER_RE.match(line):
                lines.append(line)
            elif line.strip() == "" and lines:
                break
            elif not line.startswith("#") and lines:
                break
        return "\n".join(lines) if lines else None

    def ParseBclIr(self, bcl_raw):
        if not bcl_raw:
            return None
        ir = {}
        for line in bcl_raw.split("\n"):
            m = BCL_HEADER_RE.match(line)
            if m is None:
                continue
            tag = m.group(1)
            content = m.group(2)
            kvs = {}
            for kv in BCL_KV_INLINE_RE.finditer(content):
                kvs[kv.group(1)] = kv.group(2)
            if not kvs:
                for kv in BCL_KV_COMMENT_RE.finditer(content):
                    kvs[kv.group(1)] = kv.group(2)
            if kvs:
                ir[tag.lower()] = kvs
            else:
                ir[tag.lower()] = content
        return ir if ir else None

    def ExtractClassBcl(self, source_lines, class_lineno):
        for i in range(max(0, class_lineno - 1), min(len(source_lines), class_lineno + 15)):
            line = source_lines[i]
            if BCL_HEADER_RE.match(line) and "[@CLASS]" in line:
                return line
        return None

    def ExtractMethodBcl(self, source_lines, method_lineno):
        for i in range(max(0, method_lineno - 1), min(len(source_lines), method_lineno + 10)):
            line = source_lines[i]
            if BCL_HEADER_RE.match(line) and "[@METHOD]" in line:
                return line
        return None

    def BuildFileGraph(self, tree, fname):
        nodes = [{"type": "file", "name": fname}]
        edges = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                nodes.append({"type": "class", "name": node.name, "line": node.lineno})
                edges.append({"from": fname, "to": node.name, "rel": "contains"})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes.append({"type": "function", "name": node.name, "line": node.lineno})
                edges.append({"from": fname, "to": node.name, "rel": "contains"})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    nodes.append({"type": "import", "name": alias.name, "line": node.lineno})
                    edges.append({"from": fname, "to": alias.name, "rel": "imports"})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    nodes.append({"type": "import", "name": mod + "." + alias.name, "line": node.lineno})
                    edges.append({"from": fname, "to": mod + "." + alias.name, "rel": "imports"})
        return json.dumps({"nodes": nodes, "edges": edges})

    def BuildClassGraph(self, node):
        nodes = [{"type": "class", "name": node.name, "line": node.lineno}]
        edges = []
        for b in node.bases:
            bname = b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else "complex")
            nodes.append({"type": "baseclass", "name": bname})
            edges.append({"from": node.name, "to": bname, "rel": "inherits"})
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes.append({"type": "method", "name": child.name, "line": child.lineno})
                edges.append({"from": node.name, "to": child.name, "rel": "contains"})
        return json.dumps({"nodes": nodes, "edges": edges})

    def BuildMethodGraph(self, node):
        nodes = [{"type": "method", "name": node.name, "line": node.lineno}]
        edges = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    nodes.append({"type": "call", "name": child.func.id, "line": getattr(child, "lineno", 0)})
                    edges.append({"from": node.name, "to": child.func.id, "rel": "calls"})
                elif isinstance(child.func, ast.Attribute):
                    nodes.append({"type": "call", "name": child.func.attr, "line": getattr(child, "lineno", 0)})
                    edges.append({"from": node.name, "to": child.func.attr, "rel": "calls"})
        return json.dumps({"nodes": nodes, "edges": edges})

    def CheckVbstyle(self, tree, source_lines):
        ff_result = self.state["extractor"].Run("extract_file_features", {"tree": tree, "source_lines": source_lines})
        if ff_result[0] == 0:
            return (None, None)
        vr = self.state["rule_engine"].Run("evaluate_file", {"features": ff_result[1]})
        if vr[0] == 0:
            return (None, None)
        violations = vr[1]["violations"]
        flag = 1 if len(violations) == 0 else 0
        return (flag, violations)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest QA engine files into qa_question_kb.db")
    parser.add_argument("command", nargs="?", default="all", help="Command: create_db|ingest_local|copy_codebase|populate_dimensions|populate_categories|report|all")
    args = parser.parse_args()
    engine = IngestQaEngine()
    result = engine.Run(args.command, {})
    if result[0] == 1:
        data = result[1]
        if isinstance(data, dict):
            sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        else:
            sys.stdout.write(str(data) + "\n")
        sys.exit(0)
    else:
        err = result[2]
        sys.stderr.write("ERROR: " + (err[1] if err else "unknown") + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
