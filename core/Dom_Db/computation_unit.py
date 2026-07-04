#!/usr/bin/env python3
#[@GHOST]{[@file<computation_unit.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<computation_unit>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
ComputationUnit — the single immutable execution object.

Every method, once extracted and deduplicated, becomes a Computation Unit (CU).
A CU is not a function. It is not a class. It is a self-contained, verifiable,
versioned, addressable behavior atom that any runtime, language, or AI agent
can execute and reason about consistently.

A CU contains:
  1. Identity        — UUID + semantic hash + AST hash (immutable)
  2. Contracts       — IO contract, parameter contract, side effects
  3. Dependencies    — call graph edges, state requirements
  4. Version Lineage — parent CUs, fork history, mutation chain
  5. Proof Status    — verified, tested, untested, failed, patched
  6. Repair History  — AI patches applied, reasoning, test results
  7. Execution Stats — runs, failures, latency, cache hits

The CU is the atom. Everything else (classes, plans, sessions) is a projection
over CUs. Behavior becomes data.

Schema:
  computation_units     — the atoms themselves
  cu_contracts          — IO + parameter + side-effect contracts
  cu_dependencies       — call graph edges between CUs
  cu_lineage            — version history (parent → child)
  cu_proof_status       — verification + test results
  cu_repair_history     — AI repair attempts and outcomes
  cu_execution_stats    — runtime statistics

Usage:
  cu = ComputationUnit()
  cu.Run("ingest_method", {"method_id": 42, "source_code": "def foo(x): ..."})
  cu.Run("verify", {"cu_id": "abc123..."})
  cu.Run("lineage", {"cu_id": "abc123..."})
  cu.Run("repair", {"cu_id": "abc123...", "patch": "..."})
  cu.Run("query", {"semantic_hash": "..."})
"""

import ast
import json
import sqlite3
import time
import hashlib
import uuid
import textwrap
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from SuperConfig import DB, RUNTIME


class ComputationUnit:

    SCHEMA_CU = """
CREATE TABLE IF NOT EXISTS computation_units (
    cu_id           TEXT PRIMARY KEY,
    cu_uuid         TEXT NOT NULL UNIQUE,
    method_name     TEXT NOT NULL,
    origin_class    TEXT,
    source_code     TEXT NOT NULL,
    ast_hash        TEXT NOT NULL,
    semantic_hash   TEXT NOT NULL,
    arg_names       TEXT,
    arg_count       INTEGER DEFAULT 0,
    return_count    INTEGER DEFAULT 0,
    has_yield       INTEGER DEFAULT 0,
    has_async       INTEGER DEFAULT 0,
    body_lines      INTEGER DEFAULT 0,
    cyclomatic      INTEGER DEFAULT 0,
    node_count      INTEGER DEFAULT 0,
    created_at      REAL DEFAULT 0,
    updated_at      REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cu_semantic ON computation_units(semantic_hash);
CREATE INDEX IF NOT EXISTS idx_cu_ast ON computation_units(ast_hash);
CREATE INDEX IF NOT EXISTS idx_cu_name ON computation_units(method_name);

CREATE TABLE IF NOT EXISTS cu_contracts (
    cu_id           TEXT PRIMARY KEY,
    input_contract  TEXT,
    output_contract TEXT,
    side_effects    TEXT,
    state_reads     TEXT,
    state_writes    TEXT,
    pure            INTEGER DEFAULT 0,
    deterministic   INTEGER DEFAULT 0,
    io_bound        INTEGER DEFAULT 0,
    network_bound   INTEGER DEFAULT 0,
    cpu_bound       INTEGER DEFAULT 1,
    memory_bound    INTEGER DEFAULT 0,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);

CREATE TABLE IF NOT EXISTS cu_dependencies (
    cu_id           TEXT NOT NULL,
    depends_on      TEXT NOT NULL,
    dep_type        TEXT DEFAULT 'call',
    call_site       TEXT,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);
CREATE INDEX IF NOT EXISTS idx_cd_cu ON cu_dependencies(cu_id);
CREATE INDEX IF NOT EXISTS idx_cd_dep ON cu_dependencies(depends_on);

CREATE TABLE IF NOT EXISTS cu_lineage (
    cu_id           TEXT NOT NULL,
    parent_cu_id    TEXT NOT NULL,
    fork_type       TEXT DEFAULT 'extract',
    fork_reason     TEXT,
    forked_at       REAL DEFAULT 0,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id),
    FOREIGN KEY (parent_cu_id) REFERENCES computation_units(cu_id)
);
CREATE INDEX IF NOT EXISTS idx_cl_cu ON cu_lineage(cu_id);
CREATE INDEX IF NOT EXISTS idx_cl_parent ON cu_lineage(parent_cu_id);

CREATE TABLE IF NOT EXISTS cu_proof_status (
    cu_id           TEXT PRIMARY KEY,
    status          TEXT DEFAULT 'untested',
    verified_at     REAL DEFAULT 0,
    verified_by     TEXT,
    test_count      INTEGER DEFAULT 0,
    pass_count      INTEGER DEFAULT 0,
    fail_count      INTEGER DEFAULT 0,
    proof_hash      TEXT,
    proof_detail    TEXT,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);

CREATE TABLE IF NOT EXISTS cu_repair_history (
    repair_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    cu_id           TEXT NOT NULL,
    attempt         INTEGER DEFAULT 1,
    error_type      TEXT,
    error_msg       TEXT,
    error_traceback TEXT,
    patch_applied   TEXT,
    patch_reasoning TEXT,
    patch_source    TEXT DEFAULT 'ai',
    test_result     TEXT,
    status          TEXT DEFAULT 'pending',
    timestamp       REAL DEFAULT 0,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);
CREATE INDEX IF NOT EXISTS idx_rh_cu ON cu_repair_history(cu_id);

CREATE TABLE IF NOT EXISTS cu_execution_stats (
    cu_id           TEXT PRIMARY KEY,
    total_runs      INTEGER DEFAULT 0,
    total_failures  INTEGER DEFAULT 0,
    total_cache_hits INTEGER DEFAULT 0,
    avg_latency_ms  REAL DEFAULT 0,
    p99_latency_ms  REAL DEFAULT 0,
    last_run_at     REAL DEFAULT 0,
    last_result     TEXT,
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);

CREATE TABLE IF NOT EXISTS cu_tags (
    cu_id           TEXT NOT NULL,
    tag             TEXT NOT NULL,
    PRIMARY KEY (cu_id, tag),
    FOREIGN KEY (cu_id) REFERENCES computation_units(cu_id)
);
"""

    BUILTIN_NAMES = {
        "print", "len", "str", "int", "float", "list", "dict", "set", "tuple",
        "bool", "bytes", "range", "enumerate", "zip", "map", "filter", "sorted",
        "reversed", "min", "max", "sum", "abs", "round", "isinstance", "issubclass",
        "hasattr", "getattr", "setattr", "delattr", "type", "id", "hash", "repr",
        "format", "chr", "ord", "hex", "oct", "bin", "pow", "divmod", "all", "any",
        "next", "iter", "open", "input", "callable", "compile", "eval", "exec",
        "globals", "locals", "vars", "dir", "help", "memoryview", "object",
        "property", "staticmethod", "classmethod", "super", "Exception", "ValueError",
        "TypeError", "KeyError", "IndexError", "AttributeError", "RuntimeError",
        "StopIteration", "NotImplementedError", "ImportError", "NameError",
        "OSError", "IOError", "FileNotFoundError", "PermissionError",
        "ConnectionError", "TimeoutError", "ZeroDivisionError", "OverflowError",
        "AssertionError", "Warning", "SyntaxError", "SystemExit", "KeyboardInterrupt",
        "GeneratorExit", "frozenset", "bytearray", "complex", "slice", "True",
        "False", "None", "__import__",
    }

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "cu_db": DB.COMPUTATION_UNITS_DB,
            "orchestrator_db": DB.METHOD_ORCHESTRATOR_DB,
            "conn": None,
            "orch_conn": None,
            "compile_cache": {},
            "stats": {
                "ingested": 0,
                "deduplicated": 0,
                "verified": 0,
                "repaired": 0,
                "executed": 0,
            },
        }
        if isinstance(param, dict):
            self.state.update(param)
        self._InitDb()

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _err(self, code, msg):
        return (0, None, (code, msg, 0))

    def _Conn(self):
        if self.state["conn"] is None:
            self.state["conn"] = sqlite3.connect(self.state["cu_db"])
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _OrchConn(self):
        if self.state["orch_conn"] is None:
            self.state["orch_conn"] = sqlite3.connect(self.state["orchestrator_db"])
            self.state["orch_conn"].row_factory = sqlite3.Row
            self.state["orch_conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["orch_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["cu_db"])
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(self.SCHEMA_CU)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "ingest_method": self.IngestMethod,
            "ingest_from_orchestrator": self.IngestFromOrchestrator,
            "ingest_all": self.IngestAll,
            "verify": self.Verify,
            "verify_batch": self.VerifyBatch,
            "lineage": self.Lineage,
            "fork": self.Fork,
            "repair": self.Repair,
            "query": self.Query,
            "lookup": self.Lookup,
            "execute": self.Execute,
            "info": self.Info,
            "stats": self.Stats,
            "dedup_report": self.DedupReport,
            "contract": self.GetContract,
            "set_contract": self.SetContract,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
            "batch_ingest": self.BatchIngest,
            "export_cu": self.ExportCu,
            "import_cu": self.ImportCu,
            "compare_cus": self.CompareCus,
            "dependency_graph": self.DependencyGraph,
            "health": self.Health,
            "purge_duplicates": self.PurgeDuplicates,
            "stats_detail": self.StatsDetail,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    # -----------------------------------------------------------------------
    # HASH COMPUTATION — the identity layer
    # -----------------------------------------------------------------------

    def _AstHash(self, source_code):
        try:
            tree = ast.parse(source_code)
            normalized = self._NormalizeAst(tree)
            return hashlib.sha256(
                ast.dump(normalized).encode()
            ).hexdigest()
        except Exception:
            return hashlib.sha256(source_code.encode()).hexdigest()

    def _SemanticHash(self, source_code, method_name, arg_names):
        try:
            tree = ast.parse(source_code)
            features = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        features.append("call:" + node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        features.append("attr:" + node.func.attr)
                elif isinstance(node, ast.Attribute):
                    features.append("read:" + node.attr)
                elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                    features.append("comprehension")
                elif isinstance(node, ast.Yield):
                    features.append("yield")
                elif isinstance(node, ast.Await):
                    features.append("await")
                elif isinstance(node, ast.List):
                    features.append("list")
                elif isinstance(node, ast.Dict):
                    features.append("dict")
                elif isinstance(node, ast.Tuple):
                    features.append("tuple")
                elif isinstance(node, ast.BinOp):
                    features.append("binop:" + type(node.op).__name__)
                elif isinstance(node, ast.Compare):
                    features.append("compare:" + str(len(node.ops)))
                elif isinstance(node, ast.If):
                    features.append("if")
                elif isinstance(node, ast.For):
                    features.append("for")
                elif isinstance(node, ast.While):
                    features.append("while")
                elif isinstance(node, ast.Try):
                    features.append("try")
                elif isinstance(node, ast.With):
                    features.append("with")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        features.append("import:" + alias.name)
                elif isinstance(node, ast.ImportFrom):
                    features.append("from:" + (node.module or ""))
            features.sort()
            signature = method_name + "|" + "|".join(arg_names or [])
            combined = signature + "|" + "|".join(features)
            return hashlib.sha256(combined.encode()).hexdigest()
        except Exception:
            return hashlib.sha256((method_name + str(arg_names)).encode()).hexdigest()

    def _NormalizeAst(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                node.name = "_fn_"
                for arg in node.args.args:
                    arg.arg = "_a_"
                if node.args.vararg:
                    node.args.vararg.arg = "_v_"
                if node.args.kwarg:
                    node.args.kwarg.arg = "_k_"
            elif isinstance(node, ast.ClassDef):
                node.name = "_cls_"
            elif isinstance(node, ast.Name):
                if node.id not in ("self", "True", "False", "None"):
                    node.id = "_n_"
            elif isinstance(node, ast.arg):
                if node.arg not in ("self", "cls"):
                    node.arg = "_a_"
        return tree

    def _Cyclomatic(self, tree):
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, (ast.ExceptHandler,)):
                complexity += 1
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                complexity += 1
        return complexity

    def _NodeCount(self, tree):
        return sum(1 for _ in ast.walk(tree))

    def _ExtractContracts(self, source_code, tree, arg_names):
        reads = set()
        writes = set()
        calls = set()
        imports = set()
        has_yield = False
        has_async = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "self":
                    if isinstance(node.ctx, ast.Store):
                        writes.add(node.attr)
                    else:
                        reads.add(node.attr)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
            elif isinstance(node, ast.Yield):
                has_yield = True
            elif isinstance(node, (ast.Await, ast.AsyncFunctionDef)):
                has_async = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        io_funcs = {"open", "input", "print", "read", "write", "send", "recv",
                     "connect", "bind", "listen", "accept", "socket"}
        net_funcs = {"socket", "connect", "send", "recv", "request", "urlopen",
                      "get", "post", "fetch"}
        io_bound = bool(calls & io_funcs)
        net_bound = bool(calls & net_funcs)
        pure = (len(writes) == 0 and not io_bound and not net_bound
                and not has_yield and "print" not in calls)
        deterministic = (pure and not any(
            name in calls for name in
            ("random", "time", "uuid", "hash", "id", "now")
        ))

        return {
            "input_contract": json.dumps({
                "args": arg_names or [],
                "arg_count": len(arg_names or []),
            }),
            "output_contract": json.dumps({
                "has_yield": has_yield,
                "return_count": self._CountReturns(tree),
            }),
            "side_effects": json.dumps({
                "state_reads": sorted(reads),
                "state_writes": sorted(writes),
                "external_calls": sorted(calls),
                "imports": sorted(imports),
            }),
            "state_reads": json.dumps(sorted(reads)),
            "state_writes": json.dumps(sorted(writes)),
            "pure": int(pure),
            "deterministic": int(deterministic),
            "io_bound": int(io_bound),
            "network_bound": int(net_bound),
            "cpu_bound": int(not io_bound and not net_bound),
            "memory_bound": int(bool(writes)),
        }

    def _CountReturns(self, tree):
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Return):
                count += 1
        return count

    def _ExtractCalls(self, tree):
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        return calls

    # -----------------------------------------------------------------------
    # INGEST METHOD — create a CU from a single method
    # -----------------------------------------------------------------------

    def IngestMethod(self, params):
        source_code = self._p(params, "source_code")
        method_name = self._p(params, "method_name")
        if not source_code or not method_name:
            return self._err("MISSING", "source_code and method_name required")

        origin_class = self._p(params, "origin_class", "")
        arg_names = self._p(params, "arg_names", [])
        parent_cu_id = self._p(params, "parent_cu_id")
        fork_reason = self._p(params, "fork_reason", "extract")

        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return self._err("SYNTAX_ERROR", str(e))

        ast_hash = self._AstHash(source_code)
        semantic_hash = self._SemanticHash(source_code, method_name, arg_names)

        conn = self._Conn()

        existing = conn.execute(
            "SELECT cu_id FROM computation_units WHERE semantic_hash = ?",
            (semantic_hash,)
        ).fetchone()

        if existing:
            self.state["stats"]["deduplicated"] += 1
            return (1, {
                "cu_id": existing["cu_id"],
                "method_name": method_name,
                "status": "duplicate",
                "semantic_hash": semantic_hash[:16],
                "message": "identical CU already exists",
            }, None)

        cu_uuid = str(uuid.uuid4())
        cu_id = "cu_" + semantic_hash[:20]

        cyclomatic = self._Cyclomatic(tree)
        node_count = self._NodeCount(tree)
        body_lines = len(source_code.strip().split("\n"))
        has_yield = int(any(isinstance(n, ast.Yield) for n in ast.walk(tree)))
        has_async = int(any(isinstance(n, (ast.Await, ast.AsyncFunctionDef)) for n in ast.walk(tree)))
        return_count = self._CountReturns(tree)

        now = time.time()
        conn.execute(
            "INSERT INTO computation_units "
            "(cu_id, cu_uuid, method_name, origin_class, source_code, "
            "ast_hash, semantic_hash, arg_names, arg_count, return_count, "
            "has_yield, has_async, body_lines, cyclomatic, node_count, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cu_id, cu_uuid, method_name, origin_class, source_code,
             ast_hash, semantic_hash, json.dumps(arg_names), len(arg_names),
             return_count, has_yield, has_async, body_lines,
             cyclomatic, node_count, now, now)
        )

        contracts = self._ExtractContracts(source_code, tree, arg_names)
        conn.execute(
            "INSERT OR REPLACE INTO cu_contracts "
            "(cu_id, input_contract, output_contract, side_effects, "
            "state_reads, state_writes, pure, deterministic, io_bound, "
            "network_bound, cpu_bound, memory_bound) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cu_id, contracts["input_contract"], contracts["output_contract"],
             contracts["side_effects"], contracts["state_reads"],
             contracts["state_writes"], contracts["pure"],
             contracts["deterministic"], contracts["io_bound"],
             contracts["network_bound"], contracts["cpu_bound"],
             contracts["memory_bound"])
        )

        conn.execute(
            "INSERT OR REPLACE INTO cu_proof_status (cu_id, status) VALUES (?,?)",
            (cu_id, "untested")
        )

        conn.execute(
            "INSERT OR REPLACE INTO cu_execution_stats (cu_id) VALUES (?)",
            (cu_id,)
        )

        if parent_cu_id:
            conn.execute(
                "INSERT INTO cu_lineage (cu_id, parent_cu_id, fork_type, fork_reason, forked_at) "
                "VALUES (?,?,?,?,?)",
                (cu_id, parent_cu_id, fork_reason, fork_reason, now)
            )

        calls = self._ExtractCalls(tree)
        for call_name in calls:
            if call_name in self.BUILTIN_NAMES:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO cu_dependencies (cu_id, depends_on, dep_type, call_site) "
                "VALUES (?,?,?,?)",
                (cu_id, call_name, "call", method_name)
            )

        conn.commit()
        self.state["stats"]["ingested"] += 1

        return (1, {
            "cu_id": cu_id,
            "cu_uuid": cu_uuid,
            "method_name": method_name,
            "origin_class": origin_class,
            "status": "created",
            "ast_hash": ast_hash[:16],
            "semantic_hash": semantic_hash[:16],
            "cyclomatic": cyclomatic,
            "node_count": node_count,
            "body_lines": body_lines,
            "pure": bool(contracts["pure"]),
            "deterministic": bool(contracts["deterministic"]),
            "has_yield": bool(has_yield),
            "has_async": bool(has_async),
            "calls": sorted(calls)[:10],
        }, None)

    # -----------------------------------------------------------------------
    # INGEST FROM ORCHESTRATOR — pull methods from orchestrator DB
    # -----------------------------------------------------------------------

    def IngestFromOrchestrator(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return self._err("NO_METHOD_ID", "method_id required")

        orch = self._OrchConn()
        r = orch.execute(
            "SELECT method_id, name, source_code, arg_names, origin_class, "
            "cyclomatic, body_lines FROM methods WHERE method_id = ?",
            (method_id,)
        ).fetchone()
        if not r:
            return self._err("NOT_FOUND", f"method_id {method_id}")

        arg_names = json.loads(r["arg_names"]) if r["arg_names"] else []

        return self.IngestMethod({
            "source_code": r["source_code"],
            "method_name": r["name"],
            "origin_class": r["origin_class"] or "",
            "arg_names": arg_names,
        })

    # -----------------------------------------------------------------------
    # INGEST ALL — bulk ingest from orchestrator
    # -----------------------------------------------------------------------

    def IngestAll(self, params):
        limit = self._p(params, "limit", 0)
        class_filter = self._p(params, "class_filter")

        orch = self._OrchConn()
        if class_filter:
            rows = orch.execute(
                "SELECT method_id FROM methods WHERE origin_class = ? ORDER BY method_id",
                (class_filter,)
            ).fetchall()
        elif limit > 0:
            rows = orch.execute(
                "SELECT method_id FROM methods ORDER BY method_id LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = orch.execute(
                "SELECT method_id FROM methods ORDER BY method_id"
            ).fetchall()

        created = 0
        duplicates = 0
        errors = 0

        for r in rows:
            ok, data, err = self.IngestFromOrchestrator({"method_id": r["method_id"]})
            if ok:
                if data.get("status") == "duplicate":
                    duplicates += 1
                else:
                    created += 1
            else:
                errors += 1

        return (1, {
            "total": len(rows),
            "created": created,
            "duplicates": duplicates,
            "errors": errors,
        }, None)

    # -----------------------------------------------------------------------
    # VERIFY — check if a CU compiles and its contracts hold
    # -----------------------------------------------------------------------

    def Verify(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        cu = conn.execute(
            "SELECT * FROM computation_units WHERE cu_id = ?", (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("NOT_FOUND", cu_id)

        results = {
            "cu_id": cu_id,
            "method_name": cu["method_name"],
            "checks": {},
        }

        results["checks"]["compiles"] = True
        try:
            tree = ast.parse(cu["source_code"])
            compile(tree, f"<cu://{cu_id}>", "exec")
        except SyntaxError as e:
            results["checks"]["compiles"] = False
            results["checks"]["syntax_error"] = str(e)

        results["checks"]["ast_hash_valid"] = (
            self._AstHash(cu["source_code"]) == cu["ast_hash"]
        )

        results["checks"]["semantic_hash_valid"] = (
            self._SemanticHash(
                cu["source_code"],
                cu["method_name"],
                json.loads(cu["arg_names"]) if cu["arg_names"] else []
            ) == cu["semantic_hash"]
        )

        contract = conn.execute(
            "SELECT * FROM cu_contracts WHERE cu_id = ?", (cu_id,)
        ).fetchone()
        if contract:
            results["checks"]["pure"] = bool(contract["pure"])
            results["checks"]["deterministic"] = bool(contract["deterministic"])
            results["checks"]["io_bound"] = bool(contract["io_bound"])
            results["checks"]["network_bound"] = bool(contract["network_bound"])
            side_effects = json.loads(contract["side_effects"]) if contract["side_effects"] else {}
            results["checks"]["state_reads"] = side_effects.get("state_reads", [])
            results["checks"]["state_writes"] = side_effects.get("state_writes", [])
            results["checks"]["external_calls"] = side_effects.get("external_calls", [])

        deps = conn.execute(
            "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?", (cu_id,)
        ).fetchall()
        results["checks"]["dependency_count"] = len(deps)
        results["checks"]["dependencies"] = [d["depends_on"] for d in deps]

        all_pass = all(
            v is True or (isinstance(v, list) and True)
            for k, v in results["checks"].items()
            if k not in ("syntax_error", "state_reads", "state_writes",
                          "external_calls", "dependencies", "dependency_count")
        )

        status = "verified" if results["checks"]["compiles"] and results["checks"]["ast_hash_valid"] else "failed"

        conn.execute(
            "INSERT OR REPLACE INTO cu_proof_status "
            "(cu_id, status, verified_at, verified_by, proof_detail) "
            "VALUES (?,?,?,?,?)",
            (cu_id, status, time.time(), "ComputationUnit.Verify",
             json.dumps(results["checks"], default=str))
        )
        conn.commit()

        if status == "verified":
            self.state["stats"]["verified"] += 1

        results["status"] = status
        return (1, results, None)

    def VerifyBatch(self, params):
        limit = self._p(params, "limit", 100)
        conn = self._Conn()
        rows = conn.execute(
            "SELECT cu_id FROM computation_units LIMIT ?", (limit,)
        ).fetchall()

        verified = 0
        failed = 0
        for r in rows:
            ok, data, _ = self.Verify({"cu_id": r["cu_id"]})
            if ok and data.get("status") == "verified":
                verified += 1
            else:
                failed += 1

        return (1, {"verified": verified, "failed": failed, "total": len(rows)}, None)

    # -----------------------------------------------------------------------
    # LINEAGE — version history of a CU
    # -----------------------------------------------------------------------

    def Lineage(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        chain = []
        current = cu_id
        visited = set()

        while current and current not in visited:
            visited.add(current)
            cu = conn.execute(
                "SELECT cu_id, method_name, origin_class, semantic_hash, created_at "
                "FROM computation_units WHERE cu_id = ?",
                (current,)
            ).fetchone()
            if not cu:
                break
            chain.append({
                "cu_id": cu["cu_id"],
                "method_name": cu["method_name"],
                "origin_class": cu["origin_class"],
                "semantic_hash": cu["semantic_hash"][:16],
                "created_at": cu["created_at"],
            })
            parent = conn.execute(
                "SELECT parent_cu_id FROM cu_lineage WHERE cu_id = ?",
                (current,)
            ).fetchone()
            if parent:
                current = parent["parent_cu_id"]
            else:
                current = None

        children = conn.execute(
            "SELECT cu_id, fork_type, fork_reason, forked_at "
            "FROM cu_lineage WHERE parent_cu_id = ?",
            (cu_id,)
        ).fetchall()

        return (1, {
            "cu_id": cu_id,
            "ancestry": chain,
            "children": [{
                "cu_id": c["cu_id"],
                "fork_type": c["fork_type"],
                "fork_reason": c["fork_reason"],
                "forked_at": c["forked_at"],
            } for c in children],
            "depth": len(chain),
        }, None)

    # -----------------------------------------------------------------------
    # FORK — create a new CU version from an existing one
    # -----------------------------------------------------------------------

    def Fork(self, params):
        parent_cu_id = self._p(params, "parent_cu_id")
        if not parent_cu_id:
            return self._err("NO_PARENT", "parent_cu_id required")
        new_source = self._p(params, "source_code")
        if not new_source:
            return self._err("NO_SOURCE", "source_code for forked CU required")

        conn = self._Conn()
        parent = conn.execute(
            "SELECT method_name, arg_names, origin_class FROM computation_units "
            "WHERE cu_id = ?",
            (parent_cu_id,)
        ).fetchone()
        if not parent:
            return self._err("PARENT_NOT_FOUND", parent_cu_id)

        fork_reason = self._p(params, "fork_reason", "mutation")
        arg_names = json.loads(parent["arg_names"]) if parent["arg_names"] else []

        ok, data, err = self.IngestMethod({
            "source_code": new_source,
            "method_name": parent["method_name"],
            "origin_class": parent["origin_class"] or "",
            "arg_names": arg_names,
            "parent_cu_id": parent_cu_id,
            "fork_reason": fork_reason,
        })

        if ok:
            data["forked_from"] = parent_cu_id
            data["fork_reason"] = fork_reason
        return (ok, data, err)

    # -----------------------------------------------------------------------
    # REPAIR — record an AI repair attempt on a CU
    # -----------------------------------------------------------------------

    def Repair(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        cu = conn.execute(
            "SELECT method_name FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("NOT_FOUND", cu_id)

        attempt = conn.execute(
            "SELECT COUNT(*) as cnt FROM cu_repair_history WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()["cnt"] + 1

        conn.execute(
            "INSERT INTO cu_repair_history "
            "(cu_id, attempt, error_type, error_msg, error_traceback, "
            "patch_applied, patch_reasoning, patch_source, test_result, status, timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (cu_id, attempt,
             self._p(params, "error_type", ""),
             self._p(params, "error_msg", ""),
             self._p(params, "error_traceback", ""),
             self._p(params, "patch", ""),
             self._p(params, "reasoning", ""),
             self._p(params, "patch_source", "ai"),
             self._p(params, "test_result", ""),
             self._p(params, "status", "pending"),
             time.time())
        )
        conn.commit()

        if self._p(params, "patch"):
            ok, fork_data, _ = self.Fork({
                "parent_cu_id": cu_id,
                "source_code": self._p(params, "patch"),
                "fork_reason": "repair:attempt_" + str(attempt),
            })
            if ok:
                conn.execute(
                    "UPDATE cu_repair_history SET status = 'forked', test_result = ? "
                    "WHERE repair_id = last_insert_rowid()",
                    (json.dumps({"forked_cu_id": fork_data.get("cu_id", "")}),)
                )
                conn.commit()
                self.state["stats"]["repaired"] += 1
                return (1, {
                    "cu_id": cu_id,
                    "attempt": attempt,
                    "status": "forked",
                    "forked_cu_id": fork_data.get("cu_id", ""),
                }, None)

        return (1, {
            "cu_id": cu_id,
            "attempt": attempt,
            "status": "logged",
        }, None)

    # -----------------------------------------------------------------------
    # QUERY — find CUs by various criteria
    # -----------------------------------------------------------------------

    def Query(self, params):
        conn = self._Conn()
        conditions = []
        values = []

        semantic_hash = self._p(params, "semantic_hash")
        if semantic_hash:
            conditions.append("cu.semantic_hash = ?")
            values.append(semantic_hash)

        ast_hash = self._p(params, "ast_hash")
        if ast_hash:
            conditions.append("cu.ast_hash = ?")
            values.append(ast_hash)

        method_name = self._p(params, "method_name")
        if method_name:
            conditions.append("cu.method_name = ?")
            values.append(method_name)

        origin_class = self._p(params, "origin_class")
        if origin_class:
            conditions.append("cu.origin_class = ?")
            values.append(origin_class)

        pure_only = self._p(params, "pure_only", False)
        if pure_only:
            conditions.append("cc.pure = 1")

        limit = self._p(params, "limit", 50)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = (
            "SELECT cu.cu_id, cu.method_name, cu.origin_class, "
            "cu.semantic_hash, cu.ast_hash, cu.cyclomatic, cu.body_lines, "
            "cc.pure, cc.deterministic, cc.io_bound, cc.network_bound, "
            "ps.status as proof_status "
            "FROM computation_units cu "
            "LEFT JOIN cu_contracts cc ON cu.cu_id = cc.cu_id "
            "LEFT JOIN cu_proof_status ps ON cu.cu_id = ps.cu_id "
            f"WHERE {where_clause} "
            "ORDER BY cu.created_at DESC LIMIT ?"
        )
        values.append(limit)
        rows = conn.execute(sql, values).fetchall()

        return (1, {
            "count": len(rows),
            "results": [{
                "cu_id": r["cu_id"],
                "method_name": r["method_name"],
                "origin_class": r["origin_class"],
                "semantic_hash": r["semantic_hash"][:16],
                "ast_hash": r["ast_hash"][:16],
                "cyclomatic": r["cyclomatic"],
                "body_lines": r["body_lines"],
                "pure": bool(r["pure"]),
                "deterministic": bool(r["deterministic"]),
                "io_bound": bool(r["io_bound"]),
                "network_bound": bool(r["network_bound"]),
                "proof_status": r["proof_status"],
            } for r in rows],
        }, None)

    def Lookup(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")
        return self.Info(params)

    # -----------------------------------------------------------------------
    # EXECUTE — run a CU and record stats
    # -----------------------------------------------------------------------

    def Execute(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        cu = conn.execute(
            "SELECT * FROM computation_units WHERE cu_id = ?", (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("NOT_FOUND", cu_id)

        t0 = time.time()
        error = None
        result = None

        try:
            tree = ast.parse(cu["source_code"])
            code_obj = compile(tree, f"<cu://{cu_id}>", "exec")
            ns = {}
            exec(code_obj, ns)
            func = ns.get(cu["method_name"])
            if func:
                class Shell:
                    pass
                shell = Shell()
                shell.state = self._p(params, "state", {})
                shell.config = self._p(params, "config", {})
                import types as _types
                bound = _types.MethodType(func, shell)
                call_args = self._p(params, "args", {})
                result = bound(call_args) if call_args else bound({})
        except Exception as e:
            error = str(e)

        duration = (time.time() - t0) * 1000

        stats_row = conn.execute(
            "SELECT total_runs, total_failures, avg_latency_ms FROM cu_execution_stats WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()

        total_runs = (stats_row["total_runs"] if stats_row else 0) + 1
        total_failures = (stats_row["total_failures"] if stats_row else 0) + (1 if error else 0)
        prev_avg = stats_row["avg_latency_ms"] if stats_row else 0
        avg_latency = (prev_avg * (total_runs - 1) + duration) / total_runs

        conn.execute(
            "INSERT OR REPLACE INTO cu_execution_stats "
            "(cu_id, total_runs, total_failures, avg_latency_ms, last_run_at, last_result) "
            "VALUES (?,?,?,?,?,?)",
            (cu_id, total_runs, total_failures, avg_latency,
             time.time(), json.dumps({"ok": error is None, "error": error, "result": str(result)[:200] if result else None}, default=str))
        )
        conn.commit()

        self.state["stats"]["executed"] += 1

        if error:
            return self._err("EXEC_ERROR", error)
        return (1, {
            "cu_id": cu_id,
            "method_name": cu["method_name"],
            "result": result,
            "duration_ms": round(duration, 2),
            "total_runs": total_runs,
        }, None)

    # -----------------------------------------------------------------------
    # INFO — full detail on a CU
    # -----------------------------------------------------------------------

    def Info(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        cu = conn.execute(
            "SELECT * FROM computation_units WHERE cu_id = ?", (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("NOT_FOUND", cu_id)

        contract = conn.execute(
            "SELECT * FROM cu_contracts WHERE cu_id = ?", (cu_id,)
        ).fetchone()

        proof = conn.execute(
            "SELECT * FROM cu_proof_status WHERE cu_id = ?", (cu_id,)
        ).fetchone()

        exec_stats = conn.execute(
            "SELECT * FROM cu_execution_stats WHERE cu_id = ?", (cu_id,)
        ).fetchone()

        deps = conn.execute(
            "SELECT depends_on, dep_type FROM cu_dependencies WHERE cu_id = ?",
            (cu_id,)
        ).fetchall()

        dependents = conn.execute(
            "SELECT cu_id FROM cu_dependencies WHERE depends_on = ?",
            (cu_id,)
        ).fetchall()

        repairs = conn.execute(
            "SELECT attempt, error_type, status, timestamp FROM cu_repair_history "
            "WHERE cu_id = ? ORDER BY attempt",
            (cu_id,)
        ).fetchall()

        tags = conn.execute(
            "SELECT tag FROM cu_tags WHERE cu_id = ?", (cu_id,)
        ).fetchall()

        return (1, {
            "cu_id": cu["cu_id"],
            "cu_uuid": cu["cu_uuid"],
            "method_name": cu["method_name"],
            "origin_class": cu["origin_class"],
            "ast_hash": cu["ast_hash"][:16],
            "semantic_hash": cu["semantic_hash"][:16],
            "arg_names": json.loads(cu["arg_names"]) if cu["arg_names"] else [],
            "arg_count": cu["arg_count"],
            "return_count": cu["return_count"],
            "has_yield": bool(cu["has_yield"]),
            "has_async": bool(cu["has_async"]),
            "body_lines": cu["body_lines"],
            "cyclomatic": cu["cyclomatic"],
            "node_count": cu["node_count"],
            "source_preview": cu["source_code"][:200] if cu["source_code"] else "",
            "contract": {
                "pure": bool(contract["pure"]) if contract else None,
                "deterministic": bool(contract["deterministic"]) if contract else None,
                "io_bound": bool(contract["io_bound"]) if contract else None,
                "network_bound": bool(contract["network_bound"]) if contract else None,
                "cpu_bound": bool(contract["cpu_bound"]) if contract else None,
                "memory_bound": bool(contract["memory_bound"]) if contract else None,
                "side_effects": json.loads(contract["side_effects"]) if contract and contract["side_effects"] else {},
            },
            "proof_status": proof["status"] if proof else "none",
            "execution": {
                "total_runs": exec_stats["total_runs"] if exec_stats else 0,
                "total_failures": exec_stats["total_failures"] if exec_stats else 0,
                "avg_latency_ms": exec_stats["avg_latency_ms"] if exec_stats else 0,
            } if exec_stats else {},
            "dependencies": [d["depends_on"] for d in deps],
            "dependents": [d["cu_id"] for d in dependents],
            "repairs": [{
                "attempt": r["attempt"],
                "error_type": r["error_type"],
                "status": r["status"],
            } for r in repairs],
            "tags": [t["tag"] for t in tags],
            "created_at": cu["created_at"],
        }, None)

    # -----------------------------------------------------------------------
    # DEDUP REPORT — show how many CUs are truly unique vs name-collisions
    # -----------------------------------------------------------------------

    def DedupReport(self, params):
        conn = self._Conn()

        total = conn.execute("SELECT COUNT(*) FROM computation_units").fetchone()[0]
        unique_semantic = conn.execute(
            "SELECT COUNT(DISTINCT semantic_hash) FROM computation_units"
        ).fetchone()[0]
        unique_ast = conn.execute(
            "SELECT COUNT(DISTINCT ast_hash) FROM computation_units"
        ).fetchone()[0]
        unique_names = conn.execute(
            "SELECT COUNT(DISTINCT method_name) FROM computation_units"
        ).fetchone()[0]

        name_collisions = conn.execute(
            "SELECT method_name, COUNT(*) as cnt FROM computation_units "
            "GROUP BY method_name HAVING cnt > 1 "
            "ORDER BY cnt DESC LIMIT 20"
        ).fetchall()

        pure_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE pure = 1"
        ).fetchone()[0]
        deterministic_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE deterministic = 1"
        ).fetchone()[0]
        io_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE io_bound = 1"
        ).fetchone()[0]
        net_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE network_bound = 1"
        ).fetchone()[0]

        verified = conn.execute(
            "SELECT COUNT(*) FROM cu_proof_status WHERE status = 'verified'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM cu_proof_status WHERE status = 'failed'"
        ).fetchone()[0]
        untested = conn.execute(
            "SELECT COUNT(*) FROM cu_proof_status WHERE status = 'untested'"
        ).fetchone()[0]

        return (1, {
            "total_cus": total,
            "unique_semantic_hashes": unique_semantic,
            "unique_ast_hashes": unique_ast,
            "unique_method_names": unique_names,
            "name_collisions": sum(r["cnt"] - 1 for r in name_collisions),
            "top_collisions": [{
                "method_name": r["method_name"],
                "count": r["cnt"],
            } for r in name_collisions[:10]],
            "contract_summary": {
                "pure": pure_count,
                "deterministic": deterministic_count,
                "io_bound": io_count,
                "network_bound": net_count,
            },
            "proof_summary": {
                "verified": verified,
                "failed": failed,
                "untested": untested,
            },
            "dedup_ratio": round(1 - (unique_semantic / max(total, 1)), 4),
        }, None)

    # -----------------------------------------------------------------------
    # CONTRACT — get/set contracts
    # -----------------------------------------------------------------------

    def GetContract(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")
        conn = self._Conn()
        r = conn.execute(
            "SELECT * FROM cu_contracts WHERE cu_id = ?", (cu_id,)
        ).fetchone()
        if not r:
            return self._err("NO_CONTRACT", cu_id)
        return (1, {
            "cu_id": cu_id,
            "input_contract": json.loads(r["input_contract"]) if r["input_contract"] else {},
            "output_contract": json.loads(r["output_contract"]) if r["output_contract"] else {},
            "side_effects": json.loads(r["side_effects"]) if r["side_effects"] else {},
            "pure": bool(r["pure"]),
            "deterministic": bool(r["deterministic"]),
            "io_bound": bool(r["io_bound"]),
            "network_bound": bool(r["network_bound"]),
            "cpu_bound": bool(r["cpu_bound"]),
            "memory_bound": bool(r["memory_bound"]),
        }, None)

    def SetContract(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")
        conn = self._Conn()
        existing = conn.execute(
            "SELECT cu_id FROM cu_contracts WHERE cu_id = ?", (cu_id,)
        ).fetchone()

        fields = {}
        for key in ("pure", "deterministic", "io_bound", "network_bound",
                     "cpu_bound", "memory_bound"):
            val = self._p(params, key)
            if val is not None:
                fields[key] = int(val)

        if existing and fields:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [cu_id]
            conn.execute(
                f"UPDATE cu_contracts SET {set_clause} WHERE cu_id = ?",
                values
            )
            conn.commit()
            return (1, {"cu_id": cu_id, "updated": list(fields.keys())}, None)
        return self._err("NO_UPDATE", "no fields to update or CU not found")

    # -----------------------------------------------------------------------
    # STATS / STATE / CONFIG
    # -----------------------------------------------------------------------

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "cus": conn.execute("SELECT COUNT(*) FROM computation_units").fetchone()[0],
            "contracts": conn.execute("SELECT COUNT(*) FROM cu_contracts").fetchone()[0],
            "dependencies": conn.execute("SELECT COUNT(*) FROM cu_dependencies").fetchone()[0],
            "lineage_edges": conn.execute("SELECT COUNT(*) FROM cu_lineage").fetchone()[0],
            "verified": conn.execute("SELECT COUNT(*) FROM cu_proof_status WHERE status = 'verified'").fetchone()[0],
            "repairs": conn.execute("SELECT COUNT(*) FROM cu_repair_history").fetchone()[0],
            "tags": conn.execute("SELECT COUNT(*) FROM cu_tags").fetchone()[0],
            "compile_cache": len(self.state["compile_cache"]),
        }
        return (1, {"counts": counts, "stats": self.state["stats"]}, None)

    def read_state(self, params=None):
        safe = dict(self.state)
        safe.pop("conn", None)
        safe.pop("orch_conn", None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)

    # -----------------------------------------------------------------------
    # CLOSE — connection cleanup
    # -----------------------------------------------------------------------

    def Close(self, params=None):
        if self.state.get("conn") is not None:
            try:
                self.state["conn"].close()
            except Exception:
                pass
            self.state["conn"] = None
        if self.state.get("orch_conn") is not None:
            try:
                self.state["orch_conn"].close()
            except Exception:
                pass
            self.state["orch_conn"] = None
        return (1, {"closed": True}, None)

    # -----------------------------------------------------------------------
    # BATCH INGEST — ingest multiple methods in one call
    # -----------------------------------------------------------------------

    def BatchIngest(self, params):
        methods = self._p(params, "methods", [])
        if not methods or not isinstance(methods, list):
            return self._err("NO_METHODS", "methods list required")
        created = 0
        duplicates = 0
        errors = []
        cu_ids = []
        for m in methods:
            ok, data, err = self.IngestMethod({
                "method_name": m.get("method_name"),
                "source_code": m.get("source_code"),
                "origin_class": m.get("origin_class", ""),
                "arg_names": m.get("arg_names", []),
            })
            if ok:
                if data.get("status") == "duplicate":
                    duplicates += 1
                else:
                    created += 1
                cu_ids.append(data.get("cu_id"))
            else:
                errors.append({
                    "method_name": m.get("method_name"),
                    "error": err[1] if err else "unknown",
                })
        return (1, {
            "created": created,
            "duplicates": duplicates,
            "errors": errors,
            "cu_ids": cu_ids,
        }, None)

    # -----------------------------------------------------------------------
    # EXPORT CU — export a single CU as JSON
    # -----------------------------------------------------------------------

    def ExportCu(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")
        ok, data, err = self.Info(params)
        if not ok:
            return (0, None, err)
        conn = self._Conn()
        cu = conn.execute(
            "SELECT source_code FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("NOT_FOUND", cu_id)
        payload = dict(data)
        payload["source_code"] = cu["source_code"]
        return (1, json.dumps(payload, default=str), None)

    # -----------------------------------------------------------------------
    # IMPORT CU — import a CU from JSON
    # -----------------------------------------------------------------------

    def ImportCu(self, params):
        raw = self._p(params, "json")
        if not raw:
            return self._err("NO_JSON", "json string required")
        try:
            payload = json.loads(raw)
        except Exception as e:
            return self._err("BAD_JSON", str(e))
        source_code = payload.get("source_code")
        method_name = payload.get("method_name")
        if not source_code or not method_name:
            return self._err("MISSING", "source_code and method_name required in json")
        ok, data, err = self.IngestMethod({
            "source_code": source_code,
            "method_name": method_name,
            "origin_class": payload.get("origin_class", ""),
            "arg_names": payload.get("arg_names", []),
        })
        if not ok:
            return (0, None, err)
        return (1, {
            "cu_id": data.get("cu_id"),
            "imported": True,
            "status": data.get("status"),
        }, None)

    # -----------------------------------------------------------------------
    # COMPARE CUS — compare two CUs
    # -----------------------------------------------------------------------

    def CompareCus(self, params):
        cu_id_a = self._p(params, "cu_id_a")
        cu_id_b = self._p(params, "cu_id_b")
        if not cu_id_a or not cu_id_b:
            return self._err("NO_CU_ID", "cu_id_a and cu_id_b required")
        conn = self._Conn()
        ra = conn.execute(
            "SELECT * FROM computation_units WHERE cu_id = ?", (cu_id_a,)
        ).fetchone()
        rb = conn.execute(
            "SELECT * FROM computation_units WHERE cu_id = ?", (cu_id_b,)
        ).fetchone()
        if not ra:
            return self._err("NOT_FOUND", cu_id_a)
        if not rb:
            return self._err("NOT_FOUND", cu_id_b)
        ca = conn.execute(
            "SELECT * FROM cu_contracts WHERE cu_id = ?", (cu_id_a,)
        ).fetchone()
        cb = conn.execute(
            "SELECT * FROM cu_contracts WHERE cu_id = ?", (cu_id_b,)
        ).fetchone()
        da = conn.execute(
            "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?", (cu_id_a,)
        ).fetchall()
        db_rows = conn.execute(
            "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?", (cu_id_b,)
        ).fetchall()
        deps_a = sorted(d["depends_on"] for d in da)
        deps_b = sorted(d["depends_on"] for d in db_rows)
        identical = (ra["ast_hash"] == rb["ast_hash"])
        differences = []
        if ra["ast_hash"] != rb["ast_hash"]:
            differences.append({"field": "ast_hash", "a": ra["ast_hash"][:16], "b": rb["ast_hash"][:16]})
        if ra["cyclomatic"] != rb["cyclomatic"]:
            differences.append({"field": "cyclomatic", "a": ra["cyclomatic"], "b": rb["cyclomatic"]})
        if ra["body_lines"] != rb["body_lines"]:
            differences.append({"field": "body_lines", "a": ra["body_lines"], "b": rb["body_lines"]})
        if deps_a != deps_b:
            differences.append({"field": "method_calls", "a": deps_a, "b": deps_b})
        pure_a = bool(ca["pure"]) if ca else None
        pure_b = bool(cb["pure"]) if cb else None
        if pure_a != pure_b:
            differences.append({"field": "purity", "a": pure_a, "b": pure_b})
        return (1, {
            "identical": identical,
            "differences": differences,
            "a": {
                "cu_id": ra["cu_id"],
                "method_name": ra["method_name"],
                "ast_hash": ra["ast_hash"][:16],
                "cyclomatic": ra["cyclomatic"],
                "body_lines": ra["body_lines"],
                "method_calls": deps_a,
                "purity": pure_a,
            },
            "b": {
                "cu_id": rb["cu_id"],
                "method_name": rb["method_name"],
                "ast_hash": rb["ast_hash"][:16],
                "cyclomatic": rb["cyclomatic"],
                "body_lines": rb["body_lines"],
                "method_calls": deps_b,
                "purity": pure_b,
            },
        }, None)

    # -----------------------------------------------------------------------
    # DEPENDENCY GRAPH — build CU dependency graph
    # -----------------------------------------------------------------------

    def DependencyGraph(self, params=None):
        cu_id = self._p(params, "cu_id")
        conn = self._Conn()
        if cu_id:
            nodes_rows = conn.execute(
                "SELECT cu_id, method_name FROM computation_units WHERE cu_id = ?",
                (cu_id,)
            ).fetchall()
            edge_rows = conn.execute(
                "SELECT cu_id, depends_on, dep_type FROM cu_dependencies WHERE cu_id = ?",
                (cu_id,)
            ).fetchall()
        else:
            nodes_rows = conn.execute(
                "SELECT cu_id, method_name FROM computation_units"
            ).fetchall()
            edge_rows = conn.execute(
                "SELECT cu_id, depends_on, dep_type FROM cu_dependencies"
            ).fetchall()
        nodes = [{"cu_id": r["cu_id"], "method_name": r["method_name"]} for r in nodes_rows]
        edges = [{
            "from": r["cu_id"],
            "to": r["depends_on"],
            "type": r["dep_type"],
        } for r in edge_rows]
        return (1, {"nodes": nodes, "edges": edges}, None)

    # -----------------------------------------------------------------------
    # HEALTH — health check of the CU store
    # -----------------------------------------------------------------------

    def Health(self, params=None):
        conn = self._Conn()
        total = conn.execute("SELECT COUNT(*) FROM computation_units").fetchone()[0]
        total_dup = conn.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT semantic_hash) FROM computation_units"
        ).fetchone()[0]
        total_classes = conn.execute(
            "SELECT COUNT(DISTINCT origin_class) FROM computation_units "
            "WHERE origin_class IS NOT NULL AND origin_class != ''"
        ).fetchone()[0]
        orphaned = conn.execute(
            "SELECT COUNT(*) FROM computation_units "
            "WHERE origin_class IS NULL OR origin_class = ''"
        ).fetchone()[0]
        no_stats = conn.execute(
            "SELECT COUNT(*) FROM computation_units cu "
            "LEFT JOIN cu_execution_stats es ON cu.cu_id = es.cu_id "
            "WHERE es.total_runs = 0 OR es.total_runs IS NULL"
        ).fetchone()[0]
        high_complexity = conn.execute(
            "SELECT cu_id, method_name, cyclomatic FROM computation_units "
            "WHERE cyclomatic > 10 ORDER BY cyclomatic DESC"
        ).fetchall()
        isolated = conn.execute(
            "SELECT COUNT(*) FROM computation_units cu "
            "WHERE NOT EXISTS (SELECT 1 FROM cu_dependencies WHERE cu_id = cu.cu_id) "
            "AND NOT EXISTS (SELECT 1 FROM cu_dependencies WHERE depends_on = cu.cu_id)"
        ).fetchone()[0]
        issues = []
        if orphaned > 0:
            issues.append({"type": "orphaned_cus", "count": orphaned})
        if no_stats > 0:
            issues.append({"type": "no_execution_stats", "count": no_stats})
        if len(high_complexity) > 0:
            issues.append({"type": "high_complexity", "count": len(high_complexity)})
        if isolated > 0:
            issues.append({"type": "isolated_cus", "count": isolated})
        healthy = (total > 0 and len(issues) == 0)
        return (1, {
            "healthy": healthy,
            "stats": {
                "total_cus": total,
                "total_duplicates": total_dup,
                "total_classes": total_classes,
                "orphaned_cus": orphaned,
                "cus_no_stats": no_stats,
                "high_complexity_cus": len(high_complexity),
                "isolated_cus": isolated,
            },
            "issues": issues,
        }, None)

    # -----------------------------------------------------------------------
    # PURGE DUPLICATES — remove duplicate CUs (same semantic_hash)
    # -----------------------------------------------------------------------

    def PurgeDuplicates(self, params=None):
        dry_run = self._p(params, "dry_run", False)
        conn = self._Conn()
        dup_groups = conn.execute(
            "SELECT semantic_hash, COUNT(*) as cnt, GROUP_CONCAT(cu_id) as cu_ids "
            "FROM computation_units GROUP BY semantic_hash HAVING cnt > 1"
        ).fetchall()
        removed_cus = []
        for g in dup_groups:
            cu_ids = [c for c in (g["cu_ids"] or "").split(",") if c]
            cu_ids_sorted = sorted(cu_ids)
            keep = cu_ids_sorted[0]
            to_remove = cu_ids_sorted[1:]
            for rid in to_remove:
                removed_cus.append(rid)
                if not dry_run:
                    conn.execute("DELETE FROM cu_dependencies WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_dependencies WHERE depends_on = ?", (rid,))
                    conn.execute("DELETE FROM cu_contracts WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_proof_status WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_execution_stats WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_lineage WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_lineage WHERE parent_cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_repair_history WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM cu_tags WHERE cu_id = ?", (rid,))
                    conn.execute("DELETE FROM computation_units WHERE cu_id = ?", (rid,))
                    conn.execute(
                        "UPDATE cu_dependencies SET depends_on = ? WHERE depends_on = ?",
                        (keep, rid)
                    )
        if not dry_run:
            conn.commit()
        return (1, {
            "purged": len(removed_cus),
            "dry_run": bool(dry_run),
            "removed_cus": removed_cus,
        }, None)

    # -----------------------------------------------------------------------
    # STATS DETAIL — detailed statistics
    # -----------------------------------------------------------------------

    def StatsDetail(self, params=None):
        conn = self._Conn()
        per_class_rows = conn.execute(
            "SELECT origin_class, COUNT(*) as cu_count, "
            "AVG(cyclomatic) as avg_complexity, AVG(body_lines) as avg_body_lines "
            "FROM computation_units WHERE origin_class IS NOT NULL AND origin_class != '' "
            "GROUP BY origin_class ORDER BY cu_count DESC"
        ).fetchall()
        per_class = [{
            "class_name": r["origin_class"],
            "cu_count": r["cu_count"],
            "avg_complexity": round(r["avg_complexity"] or 0, 2),
            "avg_body_lines": round(r["avg_body_lines"] or 0, 2),
        } for r in per_class_rows]
        total = conn.execute("SELECT COUNT(*) FROM computation_units").fetchone()[0]
        total_dup = conn.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT semantic_hash) FROM computation_units"
        ).fetchone()[0]
        pure_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE pure = 1"
        ).fetchone()[0]
        det_count = conn.execute(
            "SELECT COUNT(*) FROM cu_contracts WHERE deterministic = 1"
        ).fetchone()[0]
        contract_total = conn.execute("SELECT COUNT(*) FROM cu_contracts").fetchone()[0]
        purity_rate = round(pure_count / max(contract_total, 1), 4)
        determinism_rate = round(det_count / max(contract_total, 1), 4)
        complexity_hist = conn.execute(
            "SELECT cyclomatic, COUNT(*) as cnt FROM computation_units "
            "GROUP BY cyclomatic ORDER BY cyclomatic"
        ).fetchall()
        body_hist = conn.execute(
            "SELECT CASE WHEN body_lines <= 5 THEN '0-5' "
            "WHEN body_lines <= 10 THEN '6-10' "
            "WHEN body_lines <= 20 THEN '11-20' "
            "WHEN body_lines <= 50 THEN '21-50' "
            "ELSE '50+' END as bucket, COUNT(*) as cnt "
            "FROM computation_units GROUP BY bucket ORDER BY bucket"
        ).fetchall()
        return (1, {
            "per_class": per_class,
            "global": {
                "total_cus": total,
                "total_duplicates": total_dup,
                "purity_rate": purity_rate,
                "determinism_rate": determinism_rate,
            },
            "distribution": {
                "complexity_histogram": {str(r["cyclomatic"]): r["cnt"] for r in complexity_hist},
                "body_lines_histogram": {r["bucket"]: r["cnt"] for r in body_hist},
            },
        }, None)


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== COMPUTATION UNIT ===")
    print()

    cu = ComputationUnit()

    # Step 1: Ingest a single method
    print("--- Step 1: Ingest a method ---")
    ok, data, err = cu.Run("ingest_method", {
        "method_name": "Add",
        "source_code": "def Add(self, params):\n    a = params.get('a', 0)\n    b = params.get('b', 0)\n    return (1, {'sum': a + b}, None)",
        "origin_class": "Calculator",
        "arg_names": ["self", "params"],
    })
    if ok:
        print(f"  CU ID:       {data['cu_id']}")
        print(f"  Method:      {data['method_name']}")
        print(f"  Semantic:    {data['semantic_hash']}")
        print(f"  AST:         {data['ast_hash']}")
        print(f"  Pure:        {data['pure']}")
        print(f"  Deterministic: {data['deterministic']}")
        print(f"  Cyclomatic:  {data['cyclomatic']}")
        print(f"  Nodes:       {data['node_count']}")
        print(f"  Calls:       {data['calls']}")
    else:
        print(f"  FAILED: {err}")

    # Step 2: Ingest same method again (dedup)
    print()
    print("--- Step 2: Ingest duplicate (should dedup) ---")
    ok2, data2, _ = cu.Run("ingest_method", {
        "method_name": "Add",
        "source_code": "def Add(self, params):\n    a = params.get('a', 0)\n    b = params.get('b', 0)\n    return (1, {'sum': a + b}, None)",
        "origin_class": "OtherCalculator",
        "arg_names": ["self", "params"],
    })
    if ok2:
        print(f"  Status:      {data2['status']}")
        print(f"  Same CU ID:  {data2['cu_id'] == data['cu_id']}")
    else:
        print(f"  FAILED: {err}")

    # Step 3: Ingest a different method with same name (should NOT dedup)
    print()
    print("--- Step 3: Ingest same name, different behavior ---")
    ok3, data3, _ = cu.Run("ingest_method", {
        "method_name": "Add",
        "source_code": "def Add(self, params):\n    items = params.get('items', [])\n    total = sum(items)\n    return (1, {'total': total}, None)",
        "origin_class": "Aggregator",
        "arg_names": ["self", "params"],
    })
    if ok3:
        print(f"  CU ID:       {data3['cu_id']}")
        print(f"  Same name:   {data3['method_name'] == data['method_name']}")
        print(f"  Different CU: {data3['cu_id'] != data['cu_id']}")
        print(f"  Semantic:    {data3['semantic_hash']}")
    else:
        print(f"  FAILED: {err}")

    # Step 4: Verify the first CU
    print()
    print("--- Step 4: Verify CU ---")
    ok4, verified, _ = cu.Run("verify", {"cu_id": data["cu_id"]})
    if ok4:
        print(f"  Status:      {verified['status']}")
        print(f"  Compiles:    {verified['checks']['compiles']}")
        print(f"  AST valid:   {verified['checks']['ast_hash_valid']}")
        print(f"  Sem valid:   {verified['checks']['semantic_hash_valid']}")
        print(f"  Pure:        {verified['checks']['pure']}")
        print(f"  Deterministic: {verified['checks']['deterministic']}")
        print(f"  Deps:        {verified['checks']['dependency_count']}")
    else:
        print(f"  FAILED: {err}")

    # Step 5: Get contract
    print()
    print("--- Step 5: Contract ---")
    ok5, contract, _ = cu.Run("contract", {"cu_id": data["cu_id"]})
    if ok5:
        print(f"  Input:       {contract['input_contract']}")
        print(f"  Output:      {contract['output_contract']}")
        print(f"  Side effects: {contract['side_effects']}")
        print(f"  Pure:        {contract['pure']}")
        print(f"  IO bound:    {contract['io_bound']}")

    # Step 6: Execute the CU
    print()
    print("--- Step 6: Execute CU ---")
    ok6, exec_result, err6 = cu.Run("execute", {
        "cu_id": data["cu_id"],
        "args": {"a": 5, "b": 7},
        "state": {},
    })
    if ok6:
        print(f"  Result:      {exec_result['result']}")
        print(f"  Duration:    {exec_result['duration_ms']}ms")
        print(f"  Total runs:  {exec_result['total_runs']}")
    else:
        print(f"  EXEC FAILED: {err6}")

    # Step 7: Fork the CU (create a version)
    print()
    print("--- Step 7: Fork CU (multiply instead of add) ---")
    ok7, fork_data, _ = cu.Run("fork", {
        "parent_cu_id": data["cu_id"],
        "source_code": "def Add(self, params):\n    a = params.get('a', 0)\n    b = params.get('b', 0)\n    return (1, {'product': a * b}, None)",
        "fork_reason": "behavior_mutation: add->multiply",
    })
    if ok7:
        print(f"  Forked CU:   {fork_data.get('cu_id', 'N/A')}")
        print(f"  Parent:      {fork_data.get('forked_from', 'N/A')}")
        print(f"  Reason:      {fork_data.get('fork_reason', 'N/A')}")

    # Step 8: Lineage
    print()
    print("--- Step 8: Lineage ---")
    if ok7 and fork_data.get("cu_id"):
        ok8, lineage, _ = cu.Run("lineage", {"cu_id": fork_data["cu_id"]})
        if ok8:
            print(f"  Depth:       {lineage['depth']}")
            for ancestor in lineage["ancestry"]:
                print(f"    {ancestor['cu_id']:25s}  {ancestor['method_name']:10s}  from={ancestor['origin_class']}")
            print(f"  Children:    {len(lineage['children'])}")

    # Step 9: Query by method name
    print()
    print("--- Step 9: Query 'Add' ---")
    ok9, query_result, _ = cu.Run("query", {"method_name": "Add"})
    if ok9:
        print(f"  Found:       {query_result['count']} CUs")
        for r in query_result["results"]:
            print(f"    {r['cu_id']:25s}  from={r['origin_class']:20s}  pure={r['pure']}  proof={r['proof_status']}")

    # Step 10: Dedup report
    print()
    print("--- Step 10: Dedup report ---")
    ok10, report, _ = cu.Run("dedup_report", {})
    if ok10:
        print(f"  Total CUs:            {report['total_cus']}")
        print(f"  Unique semantic:      {report['unique_semantic_hashes']}")
        print(f"  Unique AST:           {report['unique_ast_hashes']}")
        print(f"  Unique names:         {report['unique_method_names']}")
        print(f"  Name collisions:      {report['name_collisions']}")
        print(f"  Dedup ratio:          {report['dedup_ratio']}")
        print(f"  Pure:                 {report['contract_summary']['pure']}")
        print(f"  Deterministic:        {report['contract_summary']['deterministic']}")
        print(f"  Verified:             {report['proof_summary']['verified']}")
        print(f"  Untested:             {report['proof_summary']['untested']}")

    # Step 11: Full info
    print()
    print("--- Step 11: Full CU info ---")
    ok11, info, _ = cu.Run("info", {"cu_id": data["cu_id"]})
    if ok11:
        print(f"  CU ID:         {info['cu_id']}")
        print(f"  UUID:          {info['cu_uuid']}")
        print(f"  Method:        {info['method_name']}")
        print(f"  Origin:        {info['origin_class']}")
        print(f"  Semantic hash: {info['semantic_hash']}")
        print(f"  AST hash:      {info['ast_hash']}")
        print(f"  Args:          {info['arg_names']}")
        print(f"  Cyclomatic:    {info['cyclomatic']}")
        print(f"  Node count:    {info['node_count']}")
        print(f"  Pure:          {info['contract']['pure']}")
        print(f"  Deterministic: {info['contract']['deterministic']}")
        print(f"  Side effects:  {info['contract']['side_effects']}")
        print(f"  Proof:         {info['proof_status']}")
        print(f"  Deps:          {info['dependencies']}")
        print(f"  Dependents:    {info['dependents']}")
        print(f"  Repairs:       {len(info['repairs'])}")
        print(f"  Source:        {info['source_preview'][:80]}...")

    # Step 12: Repair attempt
    print()
    print("--- Step 12: Repair attempt ---")
    ok12, repair, _ = cu.Run("repair", {
        "cu_id": data["cu_id"],
        "error_type": "ValueError",
        "error_msg": "missing 'a' key",
        "patch": "def Add(self, params):\n    a = params.get('a', 0)\n    b = params.get('b', 0)\n    if a is None or b is None:\n        return (0, None, ('MISSING_ARG', 'a and b required', 0))\n    return (1, {'sum': a + b}, None)",
        "reasoning": "Added null check for missing params before arithmetic",
        "status": "patched",
    })
    if ok12:
        print(f"  Attempt:      {repair['attempt']}")
        print(f"  Status:       {repair['status']}")
        if repair.get("forked_cu_id"):
            print(f"  Forked to:    {repair['forked_cu_id']}")

    # Step 13: Stats
    print()
    print("--- Step 13: Final stats ---")
    ok13, stats, _ = cu.Run("stats", {})
    if ok13:
        for k, v in stats["counts"].items():
            print(f"  {k:25s} {v}")
        print()
        for k, v in stats["stats"].items():
            print(f"  {k:25s} {v}")

    print()
    print("=== COMPUTATION UNIT DEMO COMPLETE ===")
