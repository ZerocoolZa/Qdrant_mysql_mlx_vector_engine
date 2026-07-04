#!/usr/bin/env python3
#[@GHOST]{[@file<ast_rank_engine.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ast_rank_engine>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import ast
import os
import re
import time
import json
import math
import hashlib
import sqlite3
import subprocess
from collections import deque


class AstRankEngine:
    """Multi-language AST structural scoring and ranking engine.

    Domain: AST structural analysis, complexity scoring, BCL tag detection,
    shape signature generation, and SQLite storage of code metrics.
    Authority: owns AST parsing, metric extraction, ranking, and persistence.
    """

    DEFAULT_SCAN_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
    DEFAULT_DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/db/go_mcp_store.db"
    SKIP_DIRS = (
        ".git", "__pycache__", ".devin", ".windsurf", ".codeium",
        "node_modules", ".tasks", "snapshots", "logs",
    )
    PYTHON_EXTENSIONS = (".py",)
    C_EXTENSIONS = (".c", ".h")
    ALL_EXTENSIONS = (".py", ".c", ".h")
    MAX_FILES = 10000

    NODE_WEIGHT = 0.2
    DEPTH_WEIGHT = 1.5
    FUNCTION_WEIGHT = 2.0
    CLASS_WEIGHT = 2.5
    IMPORT_WEIGHT = 1.0
    BCL_WEIGHT = 0.5
    CYCLO_WEIGHT = 1.0

    READABILITY_MAX_LINE = 100
    READABILITY_IDEAL_BLANK_RATIO = 0.20
    READABILITY_ID_MIN = 2
    READABILITY_ID_MAX = 40
    READABILITY_DEPTH_PENALTY = 5.0
    COUPLING_FAN_IN_MULT = 0.1
    MUTATION_CYCLO_MULT = 0.05
    MUTATION_SIZE_DIVISOR = 10000
    UNIFIED_W_COMPLEXITY = 0.3
    UNIFIED_W_READABILITY = 0.2
    UNIFIED_W_COUPLING = 0.15
    UNIFIED_W_MUTATION = 0.2
    UNIFIED_W_VOLATILITY = 0.15
    GIT_TIMEOUT = 15

    DEFAULT_MAX_CYCLOMATIC = 10
    DEFAULT_MAX_COGNITIVE = 15
    DEFAULT_MAX_FUNCTION_LINES = 80
    DEFAULT_MAX_NESTING_DEPTH = 6
    DEFAULT_MAX_ARGUMENTS = 6
    DEFAULT_MIN_MAINTAINABILITY = 50
    DEFAULT_MIN_READABILITY = 40
    DEFAULT_MAX_HALSTEAD_VOLUME = 10000

    GRADE_CYCLO_A = 10
    GRADE_CYCLO_B = 20
    GRADE_CYCLO_C = 50
    GRADE_COGNITIVE_A = 10
    GRADE_COGNITIVE_B = 15
    GRADE_COGNITIVE_C = 20
    GRADE_COGNITIVE_D = 30
    GRADE_MI_A = 80
    GRADE_MI_B = 70
    GRADE_MI_C = 60
    GRADE_MI_D = 50
    GRADE_HALSTEAD_A = 1000
    GRADE_HALSTEAD_B = 5000
    GRADE_HALSTEAD_C = 10000
    GRADE_HALSTEAD_D = 20000
    GRADE_READ_A = 80
    GRADE_READ_B = 60
    GRADE_READ_C = 40
    GRADE_READ_D = 20

    HALSTEAD_KEYWORD_OPS = (
        "If", "For", "While", "Return", "Assign", "AugAssign", "Assert",
        "Import", "ImportFrom", "FunctionDef", "AsyncFunctionDef", "ClassDef",
        "With", "AsyncWith", "Try", "ExceptHandler", "Raise", "Global",
        "Nonlocal", "Delete", "Pass", "Break", "Continue", "Await", "Yield",
        "YieldFrom",
    )
    COGNITIVE_BREAK_NODES = (
        "If", "For", "While", "ExceptHandler", "With", "AsyncFor", "AsyncWith",
    )
    COGNITIVE_NEST_NODES = (
        "If", "For", "While", "Try", "With", "AsyncFor", "AsyncWith",
    )

    BCL_TAG_RE = re.compile(r'\[@(\w+)\]')
    BCL_TAG_ANGLE_RE = re.compile(r'\[@(\w+)<([^>]*)>\]')
    HEADER_BCL_RE = re.compile(r'^#\s*\[@(\w+)\]')
    GHOST_HEADER_RE = re.compile(r'^#\[@GHOST\]')
    VBSTYLE_HEADER_RE = re.compile(r'^#\[@VBSTYLE\]')
    WCL_WIDGET_RE = re.compile(r'#\s*\[@WIDGET\]')

    C_FUNC_DEF_RE = re.compile(
        r'^\s*(?:static\s+|inline\s+|extern\s+)*'
        r'(?:[\w\*]+\s+)+([\w]+)\s*\([^;]*\)\s*\{',
        re.MULTILINE,
    )
    C_TYPEDEF_RE = re.compile(r'^\s*typedef\s+', re.MULTILINE)
    C_STRUCT_RE = re.compile(r'^\s*struct\s+', re.MULTILINE)
    C_INCLUDE_RE = re.compile(r'^\s*#\s*include', re.MULTILINE)
    C_DEFINE_RE = re.compile(r'^\s*#\s*define', re.MULTILINE)
    C_IF_RE = re.compile(r'\bif\s*\(')
    C_FOR_RE = re.compile(r'\bfor\s*\(')
    C_WHILE_RE = re.compile(r'\bwhile\s*\(')
    C_SWITCH_RE = re.compile(r'\bswitch\s*\(')

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "scan_path": self.DEFAULT_SCAN_PATH,
                "db_path": self.DEFAULT_DB_PATH,
                "skip_dirs": list(self.SKIP_DIRS),
                "extensions": list(self.ALL_EXTENSIONS),
                "max_files": self.MAX_FILES,
            },
            "metrics": [],
            "bcl_tags": {},
            "dependency_graph": {},
            "git_volatility": {},
            "call_graph": {},
            "unified_scores": {},
            "memunit": mem,
            "db_manager": db,
            "thresholds": {
                "max_cyclomatic": self.DEFAULT_MAX_CYCLOMATIC,
                "max_cognitive": self.DEFAULT_MAX_COGNITIVE,
                "max_function_lines": self.DEFAULT_MAX_FUNCTION_LINES,
                "max_nesting_depth": self.DEFAULT_MAX_NESTING_DEPTH,
                "max_arguments": self.DEFAULT_MAX_ARGUMENTS,
                "min_maintainability": self.DEFAULT_MIN_MAINTAINABILITY,
                "min_readability": self.DEFAULT_MIN_READABILITY,
                "max_halstead_volume": self.DEFAULT_MAX_HALSTEAD_VOLUME,
                "weights": {
                    "complexity": self.UNIFIED_W_COMPLEXITY,
                    "readability": self.UNIFIED_W_READABILITY,
                    "coupling": self.UNIFIED_W_COUPLING,
                    "mutation": self.UNIFIED_W_MUTATION,
                    "volatility": self.UNIFIED_W_VOLATILITY,
                },
            },
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "metrics_count": len(self.state["metrics"]),
            "bcl_tags_count": len(self.state["bcl_tags"]),
        }

    def set_config(self, config):
        if config is None:
            return (0, None, ("CFG_NULL", "config is None", 0))
        for key, value in config.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Run(self, command, params=None):
        dispatch = {
            "scan": self.Scan,
            "analyze": self.Analyze,
            "rank": self.Rank,
            "report": self.Report,
            "detect_bcl": self.DetectBcl,
            "shape_signature": self.ShapeSignature,
            "store_sqlite": self.StoreSqlite,
            "query_sqlite": self.QuerySqlite,
            "cyclomatic": self.Cyclomatic,
            "readability": self.Readability,
            "coupling": self.Coupling,
            "mutation_risk": self.MutationRisk,
            "git_volatility": self.GitVolatility,
            "call_graph": self.CallGraph,
            "unified_score": self.UnifiedScore,
            "store_memunit": self.StoreMemunit,
            "cognitive": self.Cognitive,
            "halstead": self.Halstead,
            "maintainability": self.Maintainability,
            "grade": self.Grade,
            "diff": self.Diff,
            "config": self.Config,
            "violations": self.Violations,
            "read_state": lambda p: (1, self.read_state(), None),
            "set_config": lambda p: self.set_config(p),
            "close": lambda p: self.Close(),
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))
        return handler(params)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def Scan(self, params=None):
        path = self._p(params, "path", self.state["config"].get("scan_path", self.DEFAULT_SCAN_PATH))
        extensions = self._p(params, "extensions", self.state["config"].get("extensions", list(self.ALL_EXTENSIONS)))
        skip_dirs = set(self.state["config"].get("skip_dirs", list(self.SKIP_DIRS)))
        max_files = self._p(params, "max_files", self.state["config"].get("max_files", self.MAX_FILES))
        ext_tuple = tuple(extensions)

        if not os.path.isdir(path):
            return (0, None, ("ROOT_MISSING", "scan path does not exist: " + str(path), 0))

        metrics_list = []
        file_count = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if file_count >= max_files:
                    break
                if not fname.endswith(ext_tuple):
                    continue
                fpath = os.path.join(root, fname)
                ok, data, err = self.Analyze({"file": fpath})
                if ok == 1:
                    metrics_list.append(data)
                    file_count += 1

        self.state["metrics"] = metrics_list
        return (1, metrics_list, None)

    def Analyze(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        ext = os.path.splitext(fpath)[1].lower()
        t0 = time.time()
        metrics = None
        if ext in self.PYTHON_EXTENSIONS:
            ok, data, err = self.AnalyzePython(fpath)
            if ok == 0:
                return (0, None, err)
            metrics = data
        elif ext in self.C_EXTENSIONS:
            ok, data, err = self.AnalyzeC(fpath)
            if ok == 0:
                return (0, None, err)
            metrics = data
        else:
            return (0, None, ("UNSUPPORTED_EXT", "unsupported extension: " + str(ext), 0))

        parse_time = time.time() - t0
        metrics["parse_time"] = parse_time

        ok, bcl_data, bcl_err = self.DetectBcl({"file": fpath})
        if ok == 1:
            bcl_info = bcl_data.get(fpath, {})
            metrics["bcl_tag_count"] = bcl_info.get("tag_count", 0)
            metrics["bcl_tags_found"] = bcl_info.get("tags_found", [])
        else:
            metrics["bcl_tag_count"] = 0
            metrics["bcl_tags_found"] = []

        ok, sig_data, sig_err = self.ShapeSignature({"file": fpath})
        if ok == 1:
            metrics["shape_signature"] = sig_data.get("signature", "")
            metrics["shape"] = sig_data.get("shape", "")
        else:
            metrics["shape_signature"] = ""
            metrics["shape"] = ""

        metrics["complexity_score"] = self.ComputeComplexity(metrics)
        return (1, metrics, None)

    def AnalyzePython(self, fpath):
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))

        try:
            tree = ast.parse(source, filename=fpath)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAIL", "syntax error: " + str(exc), 0))
        except Exception as exc:
            return (0, None, ("PARSE_FAIL", "parse error: " + str(exc), 0))

        node_count = 0
        max_depth = 0
        function_count = 0
        class_count = 0
        import_count = 0
        decision_points = 0

        queue = deque()
        queue.append((tree, 1))
        while queue:
            node, depth = queue.popleft()
            node_count += 1
            if depth > max_depth:
                max_depth = depth
            ntype = type(node).__name__
            if ntype in ("FunctionDef", "AsyncFunctionDef"):
                function_count += 1
            elif ntype == "ClassDef":
                class_count += 1
            elif ntype in ("Import", "ImportFrom"):
                import_count += 1
            elif ntype == "If":
                decision_points += 1
            elif ntype == "For":
                decision_points += 1
            elif ntype == "While":
                decision_points += 1
            elif ntype == "ExceptHandler":
                decision_points += 1
            elif ntype == "With":
                decision_points += 1
            elif ntype == "BoolOp":
                decision_points += len(node.values) - 1
            elif ntype == "Assert":
                decision_points += 1
            elif ntype in ("ListComp", "SetComp", "DictComp", "GeneratorExp"):
                for gen in node.generators:
                    decision_points += len(gen.ifs)
            for child in ast.iter_child_nodes(node):
                queue.append((child, depth + 1))

        cyclomatic = decision_points + 1
        metrics = {
            "file": fpath,
            "language": "python",
            "node_count": node_count,
            "max_depth": max_depth,
            "function_count": function_count,
            "class_count": class_count,
            "import_count": import_count,
            "decision_points": decision_points,
            "cyclomatic_complexity": cyclomatic,
        }
        return (1, metrics, None)

    def AnalyzeC(self, fpath):
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))

        function_count = len(self.C_FUNC_DEF_RE.findall(source))
        typedef_count = len(self.C_TYPEDEF_RE.findall(source))
        struct_count = len(self.C_STRUCT_RE.findall(source))
        import_count = len(self.C_INCLUDE_RE.findall(source))
        define_count = len(self.C_DEFINE_RE.findall(source))
        if_count = len(self.C_IF_RE.findall(source))
        for_count = len(self.C_FOR_RE.findall(source))
        while_count = len(self.C_WHILE_RE.findall(source))
        switch_count = len(self.C_SWITCH_RE.findall(source))

        max_depth = 0
        depth = 0
        for ch in source:
            if ch == "{":
                depth += 1
                if depth > max_depth:
                    max_depth = depth
            elif ch == "}":
                if depth > 0:
                    depth -= 1

        node_count = (
            function_count + typedef_count + struct_count + import_count +
            define_count + if_count + for_count + while_count + switch_count
        )
        decision_points = if_count + for_count + while_count + switch_count
        cyclomatic = decision_points + 1
        class_count = typedef_count + struct_count

        metrics = {
            "file": fpath,
            "language": "c",
            "node_count": node_count,
            "max_depth": max_depth,
            "function_count": function_count,
            "class_count": class_count,
            "import_count": import_count,
            "decision_points": decision_points,
            "cyclomatic_complexity": cyclomatic,
        }
        return (1, metrics, None)

    def ComputeComplexity(self, metrics):
        complexity = (
            metrics.get("node_count", 0) * self.NODE_WEIGHT +
            metrics.get("max_depth", 0) * self.DEPTH_WEIGHT +
            metrics.get("function_count", 0) * self.FUNCTION_WEIGHT +
            metrics.get("class_count", 0) * self.CLASS_WEIGHT +
            metrics.get("import_count", 0) * self.IMPORT_WEIGHT +
            metrics.get("bcl_tag_count", 0) * self.BCL_WEIGHT +
            metrics.get("cyclomatic_complexity", 0) * self.CYCLO_WEIGHT
        )
        return complexity

    def Rank(self, params=None):
        sort_by = self._p(params, "sort_by", "complexity_score")
        metrics = list(self.state["metrics"])
        if not metrics:
            return (1, [], None)
        valid = all(sort_by in m for m in metrics)
        if not valid:
            return (0, None, ("BAD_SORT_KEY", "sort_by field missing in some metrics: " + str(sort_by), 0))
        sorted_list = sorted(metrics, key=lambda m: m.get(sort_by, 0), reverse=True)
        self.state["metrics"] = sorted_list
        return (1, sorted_list, None)

    def Report(self, params=None):
        top_n = self._p(params, "top_n", 20)
        metrics = list(self.state["metrics"])
        if not metrics:
            return (1, "No metrics in state. Run 'scan' first.", None)
        sorted_metrics = sorted(
            metrics,
            key=lambda m: m.get("complexity_score", 0),
            reverse=True,
        )
        top = sorted_metrics[:top_n]
        lines = []
        lines.append("=" * 100)
        lines.append("AST RANK ENGINE REPORT — top " + str(top_n) + " files by complexity")
        lines.append("=" * 100)
        header = (
            "{:>4}  {:<60} {:>6} {:>5} {:>4} {:>4} {:>4} {:>4} {:>10} {:>8}".format(
                "Rank", "File", "Nodes", "Depth", "Func", "Cls", "Imp", "BCL", "Complex", "Time(s)"
            )
        )
        lines.append(header)
        lines.append("-" * 100)
        for idx, m in enumerate(top, start=1):
            fpath = m.get("file", "")
            if len(fpath) > 60:
                fpath = "..." + fpath[-57:]
            row = (
                "{:>4}  {:<60} {:>6} {:>5} {:>4} {:>4} {:>4} {:>4} {:>10.2f} {:>8.4f}".format(
                    idx,
                    fpath,
                    m.get("node_count", 0),
                    m.get("max_depth", 0),
                    m.get("function_count", 0),
                    m.get("class_count", 0),
                    m.get("import_count", 0),
                    m.get("bcl_tag_count", 0),
                    m.get("complexity_score", 0.0),
                    m.get("parse_time", 0.0),
                )
            )
            lines.append(row)
        lines.append("-" * 100)
        lines.append("Total files scanned: " + str(len(metrics)))
        lines.append("=" * 100)
        return (1, "\n".join(lines), None)

    def DetectBcl(self, params=None):
        fpath = self._p(params, "file")
        if fpath:
            if not os.path.isfile(fpath):
                return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
            files_to_scan = [fpath]
        else:
            files_to_scan = [m.get("file") for m in self.state["metrics"] if m.get("file")]

        bcl_tags = {}
        for fp in files_to_scan:
            if not fp or not os.path.isfile(fp):
                continue
            try:
                with open(fp, "r", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue
            tags_found = []
            for match in self.BCL_TAG_RE.finditer(content):
                tag = match.group(1)
                if tag not in tags_found:
                    tags_found.append(tag)
            for match in self.BCL_TAG_ANGLE_RE.finditer(content):
                tag = match.group(1)
                if tag not in tags_found:
                    tags_found.append(tag)
            for match in self.HEADER_BCL_RE.finditer(content):
                tag = match.group(1)
                if tag not in tags_found:
                    tags_found.append(tag)
            bcl_tags[fp] = {
                "tag_count": len(tags_found),
                "tags_found": tags_found,
            }

        if fpath:
            self.state["bcl_tags"][fpath] = bcl_tags.get(fpath, {"tag_count": 0, "tags_found": []})
        else:
            self.state["bcl_tags"] = bcl_tags
        return (1, bcl_tags, None)

    def ShapeSignature(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        ext = os.path.splitext(fpath)[1].lower()
        shape_parts = []
        if ext in self.PYTHON_EXTENSIONS:
            try:
                with open(fpath, "r", errors="replace") as f:
                    source = f.read()
            except Exception as exc:
                return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))
            try:
                tree = ast.parse(source, filename=fpath)
            except SyntaxError as exc:
                return (0, None, ("PARSE_FAIL", "syntax error: " + str(exc), 0))
            except Exception as exc:
                return (0, None, ("PARSE_FAIL", "parse error: " + str(exc), 0))
            shape_parts = self.PythonShape(tree)
        elif ext in self.C_EXTENSIONS:
            try:
                with open(fpath, "r", errors="replace") as f:
                    source = f.read()
            except Exception as exc:
                return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))
            shape_parts = self.CShape(source)
        else:
            return (0, None, ("UNSUPPORTED_EXT", "unsupported extension: " + str(ext), 0))

        shape_string = ".".join(shape_parts)
        sig_hash = hashlib.md5(shape_string.encode("utf-8")).hexdigest()
        return (1, {"file": fpath, "signature": sig_hash, "shape": shape_string}, None)

    def PythonShape(self, tree):
        shape = []
        queue = deque()
        queue.append(tree)
        while queue:
            node = queue.popleft()
            shape.append(type(node).__name__)
            for child in ast.iter_child_nodes(node):
                queue.append(child)
        return shape

    def CShape(self, source):
        shape = ["TranslationUnit"]
        for match in self.C_INCLUDE_RE.finditer(source):
            shape.append("Include")
        for match in self.C_DEFINE_RE.finditer(source):
            shape.append("Define")
        for match in self.C_TYPEDEF_RE.finditer(source):
            shape.append("TypeDef")
        for match in self.C_STRUCT_RE.finditer(source):
            shape.append("Struct")
        for match in self.C_FUNC_DEF_RE.finditer(source):
            shape.append("FunctionDef")
        for match in self.C_IF_RE.finditer(source):
            shape.append("If")
        for match in self.C_FOR_RE.finditer(source):
            shape.append("For")
        for match in self.C_WHILE_RE.finditer(source):
            shape.append("While")
        for match in self.C_SWITCH_RE.finditer(source):
            shape.append("Switch")
        return shape

    def StoreSqlite(self, params=None):
        db_path = self._p(params, "db_path", self.state["config"].get("db_path", self.DEFAULT_DB_PATH))
        metrics = self.state["metrics"]
        if not metrics:
            return (0, None, ("NO_METRICS", "no metrics in state to store", 0))

        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.isdir(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as exc:
                return (0, None, ("MKDIR_FAIL", "cannot create db dir: " + str(exc), 0))

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS ast_metrics ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_path TEXT, "
                "node_count INTEGER, "
                "max_depth INTEGER, "
                "function_count INTEGER, "
                "class_count INTEGER, "
                "import_count INTEGER, "
                "bcl_tag_count INTEGER, "
                "complexity_score REAL, "
                "parse_time REAL, "
                "shape_signature TEXT, "
                "scanned_at TEXT)"
            )
            conn.commit()
        except Exception as exc:
            if conn is not None:
                conn.close()
            return (0, None, ("DB_INIT_FAIL", "db init failed: " + str(exc), 0))

        stored = 0
        try:
            cursor = conn.cursor()
            for m in metrics:
                scanned_at = time.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO ast_metrics ("
                    "file_path, node_count, max_depth, function_count, "
                    "class_count, import_count, bcl_tag_count, "
                    "complexity_score, parse_time, shape_signature, scanned_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        m.get("file", ""),
                        m.get("node_count", 0),
                        m.get("max_depth", 0),
                        m.get("function_count", 0),
                        m.get("class_count", 0),
                        m.get("import_count", 0),
                        m.get("bcl_tag_count", 0),
                        m.get("complexity_score", 0.0),
                        m.get("parse_time", 0.0),
                        m.get("shape_signature", ""),
                        scanned_at,
                    ),
                )
                stored += 1
            conn.commit()
        except Exception as exc:
            if conn is not None:
                conn.close()
            return (0, None, ("DB_INSERT_FAIL", "db insert failed: " + str(exc), 0))
        finally:
            if conn is not None:
                conn.close()

        return (1, {"stored": stored, "db_path": db_path}, None)

    def QuerySqlite(self, params=None):
        db_path = self._p(params, "db_path", self.state["config"].get("db_path", self.DEFAULT_DB_PATH))
        min_complexity = self._p(params, "min_complexity", None)
        max_complexity = self._p(params, "max_complexity", None)
        file_pattern = self._p(params, "file_pattern", None)
        min_nodes = self._p(params, "min_nodes", None)

        if not os.path.isfile(db_path):
            return (0, None, ("DB_MISSING", "db file not found: " + str(db_path), 0))

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            query = "SELECT id, file_path, node_count, max_depth, function_count, class_count, import_count, bcl_tag_count, complexity_score, parse_time, shape_signature, scanned_at FROM ast_metrics WHERE 1=1"
            args = []
            if min_complexity is not None:
                query += " AND complexity_score >= ?"
                args.append(min_complexity)
            if max_complexity is not None:
                query += " AND complexity_score <= ?"
                args.append(max_complexity)
            if file_pattern is not None:
                query += " AND file_path LIKE ?"
                args.append(file_pattern)
            if min_nodes is not None:
                query += " AND node_count >= ?"
                args.append(min_nodes)
            query += " ORDER BY complexity_score DESC"
            cursor.execute(query, args)
            rows = cursor.fetchall()
        except Exception as exc:
            if conn is not None:
                conn.close()
            return (0, None, ("DB_QUERY_FAIL", "db query failed: " + str(exc), 0))
        finally:
            if conn is not None:
                conn.close()

        return (1, {"rows": rows, "count": len(rows)}, None)

    def Cyclomatic(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        ext = os.path.splitext(fpath)[1].lower()
        if ext in self.PYTHON_EXTENSIONS:
            ok, data, err = self.AnalyzePython(fpath)
            if ok == 0:
                return (0, None, err)
            cc = data.get("cyclomatic_complexity", 1)
            dp = data.get("decision_points", 0)
            return (1, {"file": fpath, "cyclomatic_complexity": cc, "decision_points": dp}, None)
        elif ext in self.C_EXTENSIONS:
            ok, data, err = self.AnalyzeC(fpath)
            if ok == 0:
                return (0, None, err)
            cc = data.get("cyclomatic_complexity", 1)
            dp = data.get("decision_points", 0)
            return (1, {"file": fpath, "cyclomatic_complexity": cc, "decision_points": dp}, None)
        else:
            return (0, None, ("UNSUPPORTED_EXT", "unsupported extension: " + str(ext), 0))

    def Readability(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))

        lines = source.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return (1, {"file": fpath, "readability_score": 0, "factors": {}}, None)

        line_lengths = [len(ln) for ln in lines]
        avg_line_length = sum(line_lengths) / total_lines
        over_threshold = sum(1 for ln in lines if len(ln) > self.READABILITY_MAX_LINE)
        line_length_score = max(0.0, 100.0 - (over_threshold / total_lines) * 100.0)
        if avg_line_length > self.READABILITY_MAX_LINE:
            line_length_score = max(0.0, line_length_score - (avg_line_length - self.READABILITY_MAX_LINE))

        comment_lines = 0
        blank_lines = 0
        code_lines = 0
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1
        if code_lines > 0:
            comment_density = comment_lines / code_lines
        else:
            comment_density = 0.0
        comment_score = min(100.0, comment_density * 200.0)

        blank_ratio = blank_lines / total_lines
        blank_delta = abs(blank_ratio - self.READABILITY_IDEAL_BLANK_RATIO)
        blank_score = max(0.0, 100.0 - (blank_delta * 300.0))

        docstring_total = 0
        docstring_with = 0
        identifier_lengths = []
        max_depth = 0
        try:
            tree = ast.parse(source, filename=fpath)
            for node in ast.walk(tree):
                ntype = type(node).__name__
                if ntype in ("FunctionDef", "AsyncFunctionDef", "ClassDef"):
                    docstring_total += 1
                    if (node.body and isinstance(node.body[0], ast.Expr) and
                            isinstance(node.body[0].value, ast.Constant) and
                            isinstance(node.body[0].value.value, str)):
                        docstring_with += 1
                if ntype in ("FunctionDef", "AsyncFunctionDef", "ClassDef"):
                    name = node.name
                    identifier_lengths.append(len(name))
                if ntype == "Name":
                    identifier_lengths.append(len(node.id))
            depth_queue = deque()
            depth_queue.append((tree, 1))
            while depth_queue:
                node, depth = depth_queue.popleft()
                if depth > max_depth:
                    max_depth = depth
                for child in ast.iter_child_nodes(node):
                    depth_queue.append((child, depth + 1))
        except Exception:
            pass

        if docstring_total > 0:
            docstring_coverage = docstring_with / docstring_total
        else:
            docstring_coverage = 0.0
        docstring_score = docstring_coverage * 100.0

        if identifier_lengths:
            bad_id_count = sum(
                1 for ilen in identifier_lengths
                if ilen < self.READABILITY_ID_MIN or ilen > self.READABILITY_ID_MAX
            )
            identifier_score = max(0.0, 100.0 - (bad_id_count / len(identifier_lengths)) * 100.0)
        else:
            identifier_score = 50.0

        nesting_score = max(0.0, 100.0 - (max_depth * self.READABILITY_DEPTH_PENALTY))

        factors = {
            "avg_line_length": avg_line_length,
            "line_length_score": line_length_score,
            "comment_density": comment_density,
            "comment_score": comment_score,
            "docstring_coverage": docstring_coverage,
            "docstring_score": docstring_score,
            "blank_ratio": blank_ratio,
            "blank_score": blank_score,
            "identifier_score": identifier_score,
            "max_depth": max_depth,
            "nesting_score": nesting_score,
        }
        score_values = [
            line_length_score, comment_score, docstring_score,
            blank_score, identifier_score, nesting_score,
        ]
        readability_score = sum(score_values) / len(score_values)
        if readability_score < 0.0:
            readability_score = 0.0
        if readability_score > 100.0:
            readability_score = 100.0
        return (1, {"file": fpath, "readability_score": readability_score, "factors": factors}, None)

    def Coupling(self, params=None):
        path = self._p(params, "path", self.state["config"].get("scan_path", self.DEFAULT_SCAN_PATH))
        if not os.path.isdir(path):
            return (0, None, ("ROOT_MISSING", "scan path does not exist: " + str(path), 0))

        skip_dirs = set(self.state["config"].get("skip_dirs", list(self.SKIP_DIRS)))
        py_files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if fname.endswith(self.PYTHON_EXTENSIONS):
                    py_files.append(os.path.join(root, fname))

        module_to_file = {}
        for fpath in py_files:
            base = os.path.splitext(os.path.basename(fpath))[0]
            if base not in module_to_file:
                module_to_file[base] = fpath

        raw_imports = {}
        for fpath in py_files:
            imports = set()
            try:
                with open(fpath, "r", errors="replace") as f:
                    source = f.read()
                tree = ast.parse(source, filename=fpath)
            except Exception:
                raw_imports[fpath] = []
                continue
            for node in ast.walk(tree):
                ntype = type(node).__name__
                if ntype == "Import":
                    for alias in node.names:
                        imports.add(alias.name)
                elif ntype == "ImportFrom":
                    if node.module:
                        imports.add(node.module)
                    if node.level and node.level > 0:
                        for alias in node.names:
                            imports.add(alias.name)
            raw_imports[fpath] = list(imports)

        graph = {}
        for fpath in py_files:
            graph[fpath] = {"imports": [], "imported_by": [], "fan_in": 0, "fan_out": 0, "coupling_score": 0}

        for fpath, imp_list in raw_imports.items():
            resolved = []
            for imp_name in imp_list:
                top = imp_name.split(".")[0]
                target = module_to_file.get(top)
                if target and target != fpath and target not in resolved:
                    resolved.append(target)
            graph[fpath]["imports"] = resolved
            graph[fpath]["fan_out"] = len(resolved)

        for fpath, entry in graph.items():
            for dep in entry["imports"]:
                if dep in graph:
                    graph[dep]["imported_by"].append(fpath)
                    graph[dep]["fan_in"] += 1

        total_edges = 0
        for fpath, entry in graph.items():
            entry["coupling_score"] = entry["fan_in"] + entry["fan_out"]
            total_edges += entry["fan_out"]

        self.state["dependency_graph"] = graph
        return (1, {"graph": graph, "total_files": len(graph), "total_edges": total_edges}, None)

    def MutationRisk(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))

        metrics = None
        for m in self.state["metrics"]:
            if m.get("file") == fpath:
                metrics = m
                break
        if metrics is None:
            ok, data, err = self.Analyze({"file": fpath})
            if ok == 0:
                return (0, None, err)
            metrics = data

        complexity = metrics.get("complexity_score", 0.0)
        cyclomatic = metrics.get("cyclomatic_complexity", 1)
        node_count = metrics.get("node_count", 0)

        dep_graph = self.state.get("dependency_graph", {})
        fan_in = 0
        if fpath in dep_graph:
            fan_in = dep_graph[fpath].get("fan_in", 0)

        coupling_mult = 1.0 + (fan_in * self.COUPLING_FAN_IN_MULT)
        cyclomatic_mult = 1.0 + (cyclomatic * self.MUTATION_CYCLO_MULT)
        size_mult = 1.0 + (node_count / self.MUTATION_SIZE_DIVISOR)
        mutation_risk = complexity * coupling_mult * cyclomatic_mult * size_mult

        factors = {
            "complexity_score": complexity,
            "fan_in": fan_in,
            "coupling_multiplier": coupling_mult,
            "cyclomatic_complexity": cyclomatic,
            "cyclomatic_multiplier": cyclomatic_mult,
            "node_count": node_count,
            "size_multiplier": size_mult,
        }
        return (1, {"file": fpath, "mutation_risk": mutation_risk, "factors": factors}, None)

    def GitVolatility(self, params=None):
        path = self._p(params, "path", self.state["config"].get("scan_path", self.DEFAULT_SCAN_PATH))
        if not os.path.isdir(path):
            return (0, None, ("ROOT_MISSING", "scan path does not exist: " + str(path), 0))

        metrics = self.state.get("metrics", [])
        if not metrics:
            return (0, None, ("NO_METRICS", "no metrics in state, run scan first", 0))

        try:
            probe = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=path, capture_output=True, text=True, timeout=self.GIT_TIMEOUT,
            )
        except FileNotFoundError:
            return (0, None, ("GIT_NOT_FOUND", "git executable not installed", 0))
        except subprocess.TimeoutExpired:
            return (0, None, ("GIT_TIMEOUT", "git command timed out", 0))
        except Exception as exc:
            return (0, None, ("GIT_ERROR", "git probe failed: " + str(exc), 0))

        if probe.returncode != 0:
            return (0, None, ("NOT_GIT_REPO", "path is not a git repository: " + str(path), 0))

        vol_dict = {}
        total_commits = 0
        for m in metrics:
            fpath = m.get("file")
            if not fpath or not os.path.isfile(fpath):
                continue
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "--format=%H|%ci", "--", fpath],
                    cwd=path, capture_output=True, text=True, timeout=self.GIT_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                vol_dict[fpath] = {"commit_count": 0, "last_commit": "", "volatility_score": 0.0}
                continue
            except Exception:
                vol_dict[fpath] = {"commit_count": 0, "last_commit": "", "volatility_score": 0.0}
                continue
            if result.returncode != 0:
                vol_dict[fpath] = {"commit_count": 0, "last_commit": "", "volatility_score": 0.0}
                continue
            out = result.stdout.strip()
            if not out:
                vol_dict[fpath] = {"commit_count": 0, "last_commit": "", "volatility_score": 0.0}
                continue
            commit_lines = [ln for ln in out.splitlines() if ln.strip()]
            commit_count = len(commit_lines)
            last_commit = ""
            if commit_lines:
                parts = commit_lines[0].split("|", 1)
                last_commit = parts[0].strip()
            vol_score = commit_count * 1.0
            vol_dict[fpath] = {
                "commit_count": commit_count,
                "last_commit": last_commit,
                "volatility_score": vol_score,
            }
            total_commits += commit_count

        self.state["git_volatility"] = vol_dict
        return (1, {"volatility": vol_dict, "total_commits": total_commits}, None)

    def CallGraph(self, params=None):
        fpath = self._p(params, "file")
        if fpath:
            if not os.path.isfile(fpath):
                return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
            files_to_scan = [fpath]
        else:
            metrics = self.state.get("metrics", [])
            files_to_scan = [m.get("file") for m in metrics if m.get("file")]
            if not files_to_scan:
                return (0, None, ("NO_METRICS", "no metrics in state, run scan first", 0))

        graph = {}
        total_functions = 0
        total_calls = 0

        for fp in files_to_scan:
            if not fp or not os.path.isfile(fp):
                continue
            try:
                with open(fp, "r", errors="replace") as f:
                    source = f.read()
                tree = ast.parse(source, filename=fp)
            except Exception:
                continue

            functions = []
            class_stack = []

            class CallVisitor(ast.NodeVisitor):
                def __init__(_self):
                    _self.current_func = None
                    _self.current_class = None
                    _self.func_calls = {}

                def visit_ClassDef(_self, node):
                    _self.current_class = node.name
                    _self.generic_visit(node)
                    _self.current_class = None

                def visit_FunctionDef(_self, node):
                    _self.current_func = node.name
                    _self.func_calls[node.name] = []
                    _self.generic_visit(node)
                    _self.current_func = None

                def visit_AsyncFunctionDef(_self, node):
                    _self.current_func = node.name
                    _self.func_calls[node.name] = []
                    _self.generic_visit(node)
                    _self.current_func = None

                def visit_Call(_self, node):
                    call_name = None
                    if isinstance(node.func, ast.Name):
                        call_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        call_name = node.func.attr
                    if call_name and _self.current_func:
                        _self.func_calls[_self.current_func].append(call_name)
                    _self.generic_visit(node)

            visitor = CallVisitor()
            visitor.visit(tree)
            file_graph = {}
            for func_name, calls in visitor.func_calls.items():
                file_graph[func_name] = list(calls)
                total_functions += 1
                total_calls += len(calls)
            graph[fp] = file_graph

        self.state["call_graph"] = graph
        return (1, {"graph": graph, "total_functions": total_functions, "total_calls": total_calls}, None)

    def UnifiedScore(self, params=None):
        fpath = self._p(params, "file")
        if fpath:
            if not os.path.isfile(fpath):
                return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
            metrics_list = []
            for m in self.state.get("metrics", []):
                if m.get("file") == fpath:
                    metrics_list.append(m)
                    break
            if not metrics_list:
                ok, data, err = self.Analyze({"file": fpath})
                if ok == 0:
                    return (0, None, err)
                metrics_list.append(data)
        else:
            metrics_list = self.state.get("metrics", [])
            if not metrics_list:
                return (0, None, ("NO_METRICS", "no metrics in state, run scan first", 0))

        dep_graph = self.state.get("dependency_graph", {})
        vol_data = self.state.get("git_volatility", {})

        scores = {}
        for m in metrics_list:
            fp = m.get("file", "")
            complexity = m.get("complexity_score", 0.0)
            cyclomatic = m.get("cyclomatic_complexity", 0)
            bcl_tag_count = m.get("bcl_tag_count", 0)

            readability_score = 50.0
            ok_r, rd_r, err_r = self.Readability({"file": fp})
            if ok_r == 1:
                readability_score = rd_r.get("readability_score", 50.0)

            coupling_score = 0.0
            if fp in dep_graph:
                coupling_score = dep_graph[fp].get("coupling_score", 0)

            mutation_risk = 0.0
            ok_m, md_m, err_m = self.MutationRisk({"file": fp})
            if ok_m == 1:
                mutation_risk = md_m.get("mutation_risk", 0.0)

            volatility_score = 0.0
            if fp in vol_data:
                volatility_score = vol_data[fp].get("volatility_score", 0.0)

            unified = (
                complexity * self.UNIFIED_W_COMPLEXITY +
                (100.0 - readability_score) * self.UNIFIED_W_READABILITY +
                coupling_score * self.UNIFIED_W_COUPLING +
                mutation_risk * self.UNIFIED_W_MUTATION +
                volatility_score * self.UNIFIED_W_VOLATILITY
            )

            scores[fp] = {
                "complexity_score": complexity,
                "readability_score": readability_score,
                "coupling_score": coupling_score,
                "mutation_risk": mutation_risk,
                "volatility_score": volatility_score,
                "bcl_tag_count": bcl_tag_count,
                "cyclomatic_complexity": cyclomatic,
                "unified_score": unified,
            }

        self.state["unified_scores"] = scores
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["unified_score"], reverse=True)
        top_5 = []
        for fp, info in ranked[:5]:
            top_5.append({"file": fp, "unified_score": info["unified_score"]})
        return (1, {"scores": scores, "top_5": top_5}, None)

    def StoreMemunit(self, params=None):
        db_path = self._p(params, "db_path", self.state["config"].get("db_path", self.DEFAULT_DB_PATH))
        metrics = self.state.get("metrics", [])
        if not metrics:
            return (0, None, ("NO_METRICS", "no metrics in state to store", 0))

        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.isdir(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as exc:
                return (0, None, ("MKDIR_FAIL", "cannot create db dir: " + str(exc), 0))

        dep_graph = self.state.get("dependency_graph", {})
        vol_data = self.state.get("git_volatility", {})
        unified_scores = self.state.get("unified_scores", {})

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS ast_intelligence ("
                "id INTEGER PRIMARY KEY, "
                "file_path TEXT UNIQUE, "
                "complexity_score REAL, "
                "readability_score REAL, "
                "coupling_score REAL, "
                "mutation_risk REAL, "
                "volatility_score REAL, "
                "bcl_tag_count INTEGER, "
                "cyclomatic_complexity INTEGER, "
                "unified_score REAL, "
                "shape_signature TEXT, "
                "scanned_at TEXT)"
            )
            conn.commit()
        except Exception as exc:
            if conn is not None:
                conn.close()
            return (0, None, ("DB_INIT_FAIL", "db init failed: " + str(exc), 0))

        stored = 0
        try:
            cursor = conn.cursor()
            for m in metrics:
                fp = m.get("file", "")
                complexity = m.get("complexity_score", 0.0)
                cyclomatic = m.get("cyclomatic_complexity", 0)
                bcl_tag_count = m.get("bcl_tag_count", 0)
                shape_sig = m.get("shape_signature", "")
                scanned_at = time.strftime("%Y-%m-%d %H:%M:%S")

                readability_score = 0.0
                ok_r, rd_r, err_r = self.Readability({"file": fp})
                if ok_r == 1:
                    readability_score = rd_r.get("readability_score", 0.0)

                coupling_score = 0.0
                if fp in dep_graph:
                    coupling_score = dep_graph[fp].get("coupling_score", 0)

                mutation_risk = 0.0
                ok_m, md_m, err_m = self.MutationRisk({"file": fp})
                if ok_m == 1:
                    mutation_risk = md_m.get("mutation_risk", 0.0)

                volatility_score = 0.0
                if fp in vol_data:
                    volatility_score = vol_data[fp].get("volatility_score", 0.0)

                unified_score = 0.0
                if fp in unified_scores:
                    unified_score = unified_scores[fp].get("unified_score", 0.0)

                cursor.execute(
                    "INSERT OR REPLACE INTO ast_intelligence ("
                    "file_path, complexity_score, readability_score, coupling_score, "
                    "mutation_risk, volatility_score, bcl_tag_count, "
                    "cyclomatic_complexity, unified_score, shape_signature, scanned_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        fp, complexity, readability_score, coupling_score,
                        mutation_risk, volatility_score, bcl_tag_count,
                        cyclomatic, unified_score, shape_sig, scanned_at,
                    ),
                )
                stored += 1
            conn.commit()
        except Exception as exc:
            if conn is not None:
                conn.close()
            return (0, None, ("DB_INSERT_FAIL", "db insert failed: " + str(exc), 0))
        finally:
            if conn is not None:
                conn.close()

        return (1, {"stored": stored, "db_path": db_path}, None)

    def Cognitive(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
        ext = os.path.splitext(fpath)[1].lower()
        if ext not in self.PYTHON_EXTENSIONS:
            return (0, None, ("UNSUPPORTED_EXT", "cognitive requires python file: " + str(ext), 0))
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))
        try:
            tree = ast.parse(source, filename=fpath)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAIL", "syntax error: " + str(exc), 0))
        except Exception as exc:
            return (0, None, ("PARSE_FAIL", "parse error: " + str(exc), 0))

        breakdown = {
            "control_flow": 0,
            "boolean_ops": 0,
            "recursion": 0,
            "ternary": 0,
            "comprehension_if": 0,
        }
        score = [0]
        func_stack = []

        def walk(node, nesting):
            ntype = type(node).__name__
            is_break = ntype in self.COGNITIVE_BREAK_NODES
            is_nest = ntype in self.COGNITIVE_NEST_NODES
            if is_break:
                score[0] += 1 + nesting
                breakdown["control_flow"] += 1 + nesting
            if ntype == "BoolOp":
                added = len(node.values) - 1
                score[0] += added
                breakdown["boolean_ops"] += added
            if ntype == "IfExp":
                score[0] += 1 + nesting
                breakdown["ternary"] += 1 + nesting
            if ntype in ("ListComp", "SetComp", "DictComp", "GeneratorExp"):
                for gen in node.generators:
                    for ifc in gen.ifs:
                        score[0] += 1 + nesting
                        breakdown["comprehension_if"] += 1 + nesting
            if ntype == "Call":
                call_name = None
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                if call_name and func_stack and call_name == func_stack[-1]:
                    score[0] += 1 + nesting
                    breakdown["recursion"] += 1 + nesting
            new_nesting = nesting
            if is_nest:
                new_nesting = nesting + 1
            pushed = False
            if ntype in ("FunctionDef", "AsyncFunctionDef"):
                func_stack.append(node.name)
                pushed = True
            for child in ast.iter_child_nodes(node):
                walk(child, new_nesting)
            if pushed:
                func_stack.pop()

        walk(tree, 0)
        return (1, {
            "file": fpath,
            "cognitive_complexity": score[0],
            "breakdown": breakdown,
        }, None)

    def Halstead(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
        ext = os.path.splitext(fpath)[1].lower()
        if ext not in self.PYTHON_EXTENSIONS:
            return (0, None, ("UNSUPPORTED_EXT", "halstead requires python file: " + str(ext), 0))
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception as exc:
            return (0, None, ("READ_FAIL", "failed to read file: " + str(exc), 0))
        try:
            tree = ast.parse(source, filename=fpath)
        except SyntaxError as exc:
            return (0, None, ("PARSE_FAIL", "syntax error: " + str(exc), 0))
        except Exception as exc:
            return (0, None, ("PARSE_FAIL", "parse error: " + str(exc), 0))

        operators = []
        operands = []
        for node in ast.walk(tree):
            ntype = type(node).__name__
            if isinstance(node, ast.BinOp):
                operators.append(type(node.op).__name__)
            elif isinstance(node, ast.UnaryOp):
                operators.append(type(node.op).__name__)
            elif isinstance(node, ast.BoolOp):
                operators.append(type(node.op).__name__)
            elif isinstance(node, ast.Compare):
                for op in node.ops:
                    operators.append(type(op).__name__)
            elif isinstance(node, ast.AugAssign):
                operators.append(type(node.op).__name__)
            elif ntype in self.HALSTEAD_KEYWORD_OPS:
                operators.append(ntype)
            if isinstance(node, ast.Name):
                operands.append(node.id)
            elif isinstance(node, ast.Constant):
                operands.append(repr(node.value))
            elif isinstance(node, ast.Attribute):
                operands.append(node.attr)

        n1 = len(set(operators))
        n2 = len(set(operands))
        N1 = len(operators)
        N2 = len(operands)
        N = N1 + N2
        n = n1 + n2
        if n > 0:
            volume = N * math.log2(n)
        else:
            volume = 0.0
        if n2 > 0:
            difficulty = (n1 / 2.0) * (N2 / float(n2))
        else:
            difficulty = 0.0
        effort = difficulty * volume
        time_seconds = effort / 18.0
        estimated_bugs = volume / 3000.0
        return (1, {
            "file": fpath,
            "volume": volume,
            "difficulty": difficulty,
            "effort": effort,
            "time_seconds": time_seconds,
            "estimated_bugs": estimated_bugs,
            "operators": N1,
            "operands": N2,
            "unique_operators": n1,
            "unique_operands": n2,
        }, None)

    def CountLoc(self, fpath):
        try:
            with open(fpath, "r", errors="replace") as f:
                source = f.read()
        except Exception:
            return 0
        count = 0
        for ln in source.splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            count += 1
        return count

    def Maintainability(self, params=None):
        fpath = self._p(params, "file")
        if not fpath:
            return (0, None, ("NO_FILE", "file param required", 0))
        if not os.path.isfile(fpath):
            return (0, None, ("FILE_MISSING", "file not found: " + str(fpath), 0))
        ext = os.path.splitext(fpath)[1].lower()
        if ext not in self.PYTHON_EXTENSIONS:
            return (0, None, ("UNSUPPORTED_EXT", "maintainability requires python file: " + str(ext), 0))
        ok_h, h_data, h_err = self.Halstead({"file": fpath})
        if ok_h == 0:
            return (0, None, h_err)
        volume = h_data.get("volume", 0.0)
        ok_c, c_data, c_err = self.Cyclomatic({"file": fpath})
        if ok_c == 0:
            return (0, None, c_err)
        cc = c_data.get("cyclomatic_complexity", 1)
        loc = self.CountLoc(fpath)
        ln_vol = math.log(max(1, volume))
        ln_loc = math.log(max(1, loc))
        mi_raw = 171.0 - 5.2 * ln_vol - 0.23 * cc - 16.2 * ln_loc
        mi = mi_raw * 100.0 / 171.0
        if mi < 0.0:
            mi = 0.0
        grade = self.GradeMaintainabilityValue(mi)
        return (1, {
            "file": fpath,
            "maintainability_index": mi,
            "volume": volume,
            "cyclomatic": cc,
            "loc": loc,
            "grade": grade,
        }, None)

    def GradeCyclomatic(self, score):
        if score <= self.GRADE_CYCLO_A:
            return "A"
        if score <= self.GRADE_CYCLO_B:
            return "B"
        if score <= self.GRADE_CYCLO_C:
            return "C"
        return "D"

    def GradeCognitiveValue(self, score):
        if score <= self.GRADE_COGNITIVE_A:
            return "A"
        if score <= self.GRADE_COGNITIVE_B:
            return "B"
        if score <= self.GRADE_COGNITIVE_C:
            return "C"
        if score <= self.GRADE_COGNITIVE_D:
            return "D"
        return "F"

    def GradeMaintainabilityValue(self, mi):
        if mi >= self.GRADE_MI_A:
            return "A"
        if mi >= self.GRADE_MI_B:
            return "B"
        if mi >= self.GRADE_MI_C:
            return "C"
        if mi >= self.GRADE_MI_D:
            return "D"
        return "F"

    def GradeHalsteadValue(self, volume):
        if volume < self.GRADE_HALSTEAD_A:
            return "A"
        if volume <= self.GRADE_HALSTEAD_B:
            return "B"
        if volume <= self.GRADE_HALSTEAD_C:
            return "C"
        if volume <= self.GRADE_HALSTEAD_D:
            return "D"
        return "F"

    def GradeReadabilityValue(self, score):
        if score >= self.GRADE_READ_A:
            return "A"
        if score >= self.GRADE_READ_B:
            return "B"
        if score >= self.GRADE_READ_C:
            return "C"
        if score >= self.GRADE_READ_D:
            return "D"
        return "F"

    def GradeMetric(self, metric, score):
        if metric == "cyclomatic":
            return self.GradeCyclomatic(score)
        if metric == "cognitive":
            return self.GradeCognitiveValue(score)
        if metric == "maintainability":
            return self.GradeMaintainabilityValue(score)
        if metric in ("halstead_volume", "halstead"):
            return self.GradeHalsteadValue(score)
        if metric == "readability":
            return self.GradeReadabilityValue(score)
        return "N/A"

    def OverallGrade(self, grades):
        order = ["A", "B", "C", "D", "F"]
        nums = []
        for g in grades.values():
            if g in order:
                nums.append(order.index(g))
        if not nums:
            return "N/A"
        avg = sum(nums) / len(nums)
        idx = int(round(avg))
        if idx >= len(order):
            idx = len(order) - 1
        return order[idx]

    def Grade(self, params=None):
        fpath = self._p(params, "file", None)
        score = self._p(params, "score", None)
        metric = self._p(params, "metric", None)
        if fpath:
            grades = {}
            ok, data, err = self.Cyclomatic({"file": fpath})
            if ok == 1:
                grades["cyclomatic"] = self.GradeCyclomatic(data.get("cyclomatic_complexity", 1))
            ok, data, err = self.Cognitive({"file": fpath})
            if ok == 1:
                grades["cognitive"] = self.GradeCognitiveValue(data.get("cognitive_complexity", 0))
            ok, data, err = self.Halstead({"file": fpath})
            if ok == 1:
                grades["halstead_volume"] = self.GradeHalsteadValue(data.get("volume", 0.0))
            ok, data, err = self.Maintainability({"file": fpath})
            if ok == 1:
                grades["maintainability"] = data.get("grade", "N/A")
            ok, data, err = self.Readability({"file": fpath})
            if ok == 1:
                grades["readability"] = self.GradeReadabilityValue(data.get("readability_score", 0.0))
            overall = self.OverallGrade(grades)
            return (1, {"grades": grades, "summary": "Overall: " + overall}, None)
        if score is None or metric is None:
            return (0, None, ("NO_INPUT", "provide file or score+metric", 0))
        grade = self.GradeMetric(metric, score)
        return (1, {"grades": {metric: grade}, "summary": metric + ": " + grade}, None)

    def Diff(self, params=None):
        path = self._p(params, "path", self.state["config"].get("scan_path", self.DEFAULT_SCAN_PATH))
        base = self._p(params, "base", "main")
        head = self._p(params, "head", "HEAD")
        if not os.path.isdir(path):
            return (0, None, ("ROOT_MISSING", "scan path does not exist: " + str(path), 0))
        try:
            probe = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=path, capture_output=True, text=True, timeout=self.GIT_TIMEOUT,
            )
        except FileNotFoundError:
            return (0, None, ("GIT_NOT_FOUND", "git executable not installed", 0))
        except subprocess.TimeoutExpired:
            return (0, None, ("GIT_TIMEOUT", "git command timed out", 0))
        except Exception as exc:
            return (0, None, ("GIT_ERROR", "git probe failed: " + str(exc), 0))
        if probe.returncode != 0:
            return (0, None, ("NOT_GIT_REPO", "path is not a git repository: " + str(path), 0))
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base + ".." + head],
                cwd=path, capture_output=True, text=True, timeout=self.GIT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("GIT_TIMEOUT", "git diff timed out", 0))
        except Exception as exc:
            return (0, None, ("GIT_ERROR", "git diff failed: " + str(exc), 0))
        changed_files = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        metrics = []
        analyzed_files = []
        for rel in changed_files:
            full = os.path.join(path, rel)
            if not os.path.isfile(full):
                continue
            if not full.endswith(self.ALL_EXTENSIONS):
                continue
            ok, data, err = self.Analyze({"file": full})
            if ok == 1:
                metrics.append(data)
                analyzed_files.append(rel)
        return (1, {
            "changed_files": analyzed_files,
            "metrics": metrics,
            "count": len(metrics),
        }, None)

    def Config(self, params=None):
        config = self._p(params, "config", None)
        if config is None:
            return (1, {"thresholds": dict(self.state["thresholds"])}, None)
        if not isinstance(config, dict):
            return (0, None, ("BAD_CONFIG", "config must be a dict", 0))
        for key, value in config.items():
            self.state["thresholds"][key] = value
        return (1, {"thresholds": dict(self.state["thresholds"])}, None)

    def Violations(self, params=None):
        path = self._p(params, "path", None)
        metrics = self.state.get("metrics", [])
        if path:
            ok, data, err = self.Scan({"path": path})
            if ok == 0:
                return (0, None, err)
            metrics = data
        if not metrics:
            return (0, None, ("NO_METRICS", "no metrics to check against thresholds", 0))
        thresholds = self.state["thresholds"]
        violations = []
        for m in metrics:
            fp = m.get("file", "")
            cc = m.get("cyclomatic_complexity", 0)
            max_cc = thresholds.get("max_cyclomatic", self.DEFAULT_MAX_CYCLOMATIC)
            if cc > max_cc:
                severity = "critical" if cc > max_cc * 2 else "warning"
                violations.append({
                    "file": fp, "metric": "cyclomatic_complexity",
                    "value": cc, "threshold": max_cc, "severity": severity,
                })
            nd = m.get("max_depth", 0)
            max_nd = thresholds.get("max_nesting_depth", self.DEFAULT_MAX_NESTING_DEPTH)
            if nd > max_nd:
                severity = "critical" if nd > max_nd * 2 else "warning"
                violations.append({
                    "file": fp, "metric": "nesting_depth",
                    "value": nd, "threshold": max_nd, "severity": severity,
                })
            ok_c, cog_data, cog_err = self.Cognitive({"file": fp})
            if ok_c == 1:
                cog = cog_data.get("cognitive_complexity", 0)
                max_cog = thresholds.get("max_cognitive", self.DEFAULT_MAX_COGNITIVE)
                if cog > max_cog:
                    severity = "critical" if cog > max_cog * 2 else "warning"
                    violations.append({
                        "file": fp, "metric": "cognitive_complexity",
                        "value": cog, "threshold": max_cog, "severity": severity,
                    })
            ok_h, h_data, h_err = self.Halstead({"file": fp})
            if ok_h == 1:
                vol = h_data.get("volume", 0.0)
                max_vol = thresholds.get("max_halstead_volume", self.DEFAULT_MAX_HALSTEAD_VOLUME)
                if vol > max_vol:
                    severity = "critical" if vol > max_vol * 2 else "warning"
                    violations.append({
                        "file": fp, "metric": "halstead_volume",
                        "value": vol, "threshold": max_vol, "severity": severity,
                    })
            ok_m, mi_data, mi_err = self.Maintainability({"file": fp})
            if ok_m == 1:
                mi = mi_data.get("maintainability_index", 100.0)
                min_mi = thresholds.get("min_maintainability", self.DEFAULT_MIN_MAINTAINABILITY)
                if mi < min_mi:
                    severity = "critical" if mi < min_mi / 2.0 else "warning"
                    violations.append({
                        "file": fp, "metric": "maintainability_index",
                        "value": mi, "threshold": min_mi, "severity": severity,
                    })
            ok_r, r_data, r_err = self.Readability({"file": fp})
            if ok_r == 1:
                rs = r_data.get("readability_score", 100.0)
                min_rs = thresholds.get("min_readability", self.DEFAULT_MIN_READABILITY)
                if rs < min_rs:
                    severity = "critical" if rs < min_rs / 2.0 else "warning"
                    violations.append({
                        "file": fp, "metric": "readability_score",
                        "value": rs, "threshold": min_rs, "severity": severity,
                    })
        critical_count = sum(1 for v in violations if v["severity"] == "critical")
        warning_count = sum(1 for v in violations if v["severity"] == "warning")
        return (1, {
            "violations": violations,
            "count": len(violations),
            "critical_count": critical_count,
            "warning_count": warning_count,
        }, None)
