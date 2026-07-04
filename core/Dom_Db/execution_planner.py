#!/usr/bin/env python3
#[@GHOST]{[@file<execution_planner.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<execution_planner>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
ExecutionPlanner — deterministic execution planner for compressed method-units.

Takes BCLIR compressed method-units (deduplicated method clusters from the
orchestrator DB), resolves dependencies, detects conflicts, and composes
runnable execution graphs with caching and rollback safety.

Architecture:
  execution_units     — clusters of methods forming a single computation
  unit_deps           — unit A depends on unit B (DAG edges)
  execution_plans     — named plans composed of units
  plan_steps          — ordered steps in a plan (topological sort)
  execution_log       — log of executions for rollback
  state_snapshots     — state before/after for rollback safety

Flow:
  1. Define units from method sets
  2. Resolve dependencies (call graph → unit graph)
  3. Detect conflicts (signature mismatch, state conflict, missing dep)
  4. Topological sort → execution order
  5. Execute with state snapshot → rollback on failure
  6. Cache compiled graphs and results

Usage:
  planner = ExecutionPlanner()
  planner.Run("build_from_orchestrator", {})
  planner.Run("define_unit", {"unit_name": "ReadState", "method_ids": [1,4,9]})
  planner.Run("create_plan", {"plan_name": "Bootstrap", "unit_names": ["ReadState", "SetConfig"]})
  planner.Run("execute_plan", {"plan_name": "Bootstrap", "init_state": {}})
"""

import ast
import json
import sqlite3
import time
import copy
import hashlib
import types
import threading
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from SuperConfig import DB, RUNTIME

SCHEMA_EXECUTION_PLANNER = """
CREATE TABLE IF NOT EXISTS execution_units (
    unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name    TEXT NOT NULL UNIQUE,
    method_ids   TEXT NOT NULL,
    method_names TEXT NOT NULL,
    description  TEXT,
    ast_fingerprint TEXT,
    created_at   REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS unit_deps (
    unit_id      INTEGER NOT NULL,
    depends_on   INTEGER NOT NULL,
    dep_type     TEXT DEFAULT 'call',
    FOREIGN KEY (unit_id) REFERENCES execution_units(unit_id),
    FOREIGN KEY (depends_on) REFERENCES execution_units(unit_id)
);
CREATE INDEX IF NOT EXISTS idx_ud_unit ON unit_deps(unit_id);
CREATE INDEX IF NOT EXISTS idx_ud_dep ON unit_deps(depends_on);

CREATE TABLE IF NOT EXISTS execution_plans (
    plan_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL UNIQUE,
    unit_names   TEXT NOT NULL,
    step_order   TEXT NOT NULL,
    description  TEXT,
    created_at   REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS execution_log (
    log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL,
    step_index   INTEGER NOT NULL,
    unit_name    TEXT NOT NULL,
    status       TEXT NOT NULL,
    duration_ms  REAL,
    result_json  TEXT,
    error_msg    TEXT,
    timestamp    REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_el_plan ON execution_log(plan_name);

CREATE TABLE IF NOT EXISTS state_snapshots (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name    TEXT NOT NULL,
    step_index   INTEGER NOT NULL,
    state_json   TEXT NOT NULL,
    timestamp    REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ss_plan ON state_snapshots(plan_name);

CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_a       TEXT NOT NULL,
    unit_b       TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    detail       TEXT,
    severity     TEXT DEFAULT 'error',
    resolved     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_eu_name ON execution_units(unit_name);
CREATE INDEX IF NOT EXISTS idx_eu_fp ON execution_units(ast_fingerprint);
CREATE INDEX IF NOT EXISTS idx_conf_a ON conflicts(unit_a);
CREATE INDEX IF NOT EXISTS idx_conf_b ON conflicts(unit_b);
CREATE INDEX IF NOT EXISTS idx_el_status ON execution_log(status);
CREATE INDEX IF NOT EXISTS idx_el_time ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_ss_time ON state_snapshots(timestamp);
"""


class ExecutionPlanner:

    MAX_WORKERS = 4
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 0.5

    BUILTIN_NAMES = {
        "print", "len", "str", "int", "float", "list", "dict", "set", "tuple",
        "bool", "bytes", "range", "enumerate", "zip", "map", "filter", "sorted",
        "reversed", "min", "max", "sum", "abs", "round", "isinstance", "issubclass",
        "hasattr", "getattr", "setattr", "delattr", "type", "id", "hash", "repr",
        "format", "chr", "ord", "hex", "oct", "bin", "pow", "divmod", "all", "any",
        "next", "iter", "open", "input", "breakpoint", "callable", "compile",
        "globals", "locals", "vars", "dir", "help", "memoryview",
        "object", "property", "staticmethod", "classmethod", "super",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
        "ImportError", "ModuleNotFoundError", "NameError", "OSError", "IOError",
        "FileNotFoundError", "PermissionError", "ConnectionError", "TimeoutError",
        "ZeroDivisionError", "OverflowError", "AssertionError", "Warning",
        "DeprecationWarning", "UserWarning", "FutureWarning", "PendingDeprecationWarning",
        "SyntaxError", "IndentationError", "TabError", "SystemExit", "KeyboardInterrupt",
        "GeneratorExit", "StopAsyncIteration", "ArithmeticError", "BufferError",
        "LookupError", "MemoryError", "RecursionError", "ReferenceError",
        "SystemError", "UnboundLocalError", "UnicodeError", "UnicodeDecodeError",
        "UnicodeEncodeError", "UnicodeTranslateError", "frozenset", "bytearray",
        "complex", "slice", "Ellipsis", "NotImplemented", "True", "False", "None",
        "__import__", "license", "credits", "copyright",
    }

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "orchestrator_db": DB.METHOD_ORCHESTRATOR_DB,
            "planner_db": DB.EXECUTION_PLANNER_DB,
            "conn": None,
            "orch_conn": None,
            "compile_cache": {},
            "result_cache": {},
            "cache_lock": threading.Lock(),
            "max_cache_size": 1000,
            "stats": {
                "units_defined": 0,
                "plans_created": 0,
                "plans_executed": 0,
                "rollbacks": 0,
                "cache_hits": 0,
                "conflicts_detected": 0,
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
            self.state["conn"] = sqlite3.connect(self.state["planner_db"])
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _OrchConn(self):
        if self.state["orch_conn"] is None:
            self.state["orch_conn"] = sqlite3.connect(self.state["orchestrator_db"])
            self.state["orch_conn"].row_factory = sqlite3.Row
        return self.state["orch_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["planner_db"])
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_EXECUTION_PLANNER)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "define_unit": self.DefineUnit,
            "auto_units": self.AutoUnits,
            "resolve_deps": self.ResolveDeps,
            "detect_conflicts": self.DetectConflicts,
            "create_plan": self.CreatePlan,
            "execute_plan": self.ExecutePlan,
            "list_units": self.ListUnits,
            "list_plans": self.ListPlans,
            "unit_info": self.UnitInfo,
            "plan_info": self.PlanInfo,
            "execution_log": self.ExecutionLog,
            "rollback": self.Rollback,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
            "parallel_execute": self.ParallelExecute,
            "retry_execute": self.RetryExecute,
            "timeout_execute": self.TimeoutExecute,
            "conditional_plan": self.ConditionalPlan,
            "export_plan": self.ExportPlan,
            "import_plan": self.ImportPlan,
            "visualize": self.Visualize,
            "validate_plan": self.ValidatePlan,
            "replay": self.Replay,
            "profile": self.Profile,
            "state_diff": self.StateDiff,
            "cost_estimate": self.CostEstimate,
            "export_dot": self.ExportDot,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    # -----------------------------------------------------------------------
    # DEFINE UNIT — cluster methods into an execution unit
    # -----------------------------------------------------------------------

    def DefineUnit(self, params):
        unit_name = self._p(params, "unit_name")
        if not unit_name:
            return self._err("NO_UNIT_NAME", "unit_name required")
        method_ids = self._p(params, "method_ids", [])
        description = self._p(params, "description", "")

        if not isinstance(method_ids, list):
            return self._err("INVALID_METHOD_IDS", "method_ids must be a list")
        validated_ids = []
        for mid in method_ids:
            if isinstance(mid, int) and mid > 0:
                validated_ids.append(mid)
            elif isinstance(mid, str) and mid.isdigit():
                validated_ids.append(int(mid))
        if not validated_ids:
            return self._err("NO_VALID_METHODS", "no valid method IDs after validation")
        method_ids = validated_ids

        if not method_ids:
            return self._err("NO_METHODS", "method_ids required")

        conn = self._Conn()
        orch = self._OrchConn()

        names = []
        sources = []
        for mid in method_ids:
            r = orch.execute(
                "SELECT name, source_code FROM methods WHERE method_id = ?",
                (mid,)
            ).fetchone()
            if r:
                names.append(r["name"])
                sources.append(r["source_code"] or "")

        fingerprint = hashlib.md5(
            "|".join(sorted(names)).encode()
        ).hexdigest()

        conn.execute(
            "INSERT OR REPLACE INTO execution_units "
            "(unit_name, method_ids, method_names, description, "
            "ast_fingerprint, created_at) VALUES (?,?,?,?,?,?)",
            (unit_name, json.dumps(method_ids), json.dumps(names),
             description, fingerprint, time.time())
        )
        conn.commit()

        self.state["stats"]["units_defined"] += 1
        return (1, {
            "unit_name": unit_name,
            "method_count": len(method_ids),
            "method_names": names,
            "fingerprint": fingerprint[:16],
        }, None)

    # -----------------------------------------------------------------------
    # AUTO UNITS — automatically create units from orchestrator classes
    # -----------------------------------------------------------------------

    def AutoUnits(self, params):
        class_filter = self._p(params, "class_filter")
        max_units = self._p(params, "max_units", 50)

        orch = self._OrchConn()
        conn = self._Conn()

        if class_filter:
            rows = orch.execute(
                "SELECT DISTINCT class_name FROM class_methods WHERE class_name = ?",
                (class_filter,)
            ).fetchall()
        else:
            rows = orch.execute(
                "SELECT DISTINCT class_name, COUNT(*) as cnt "
                "FROM class_methods GROUP BY class_name "
                "ORDER BY cnt DESC LIMIT ?",
                (max_units,)
            ).fetchall()

        created = []
        for r in rows:
            cn = r["class_name"]
            mids = orch.execute(
                "SELECT method_id FROM class_methods WHERE class_name = ?",
                (cn,)
            ).fetchall()
            method_ids = [m["method_id"] for m in mids]
            unit_name = "unit_" + cn

            ok, data, err = self.DefineUnit({
                "unit_name": unit_name,
                "method_ids": method_ids,
                "description": "auto-created from class " + cn,
            })
            if ok:
                created.append(data)

        return (1, {"units_created": len(created), "units": created}, None)

    # -----------------------------------------------------------------------
    # RESOLVE DEPS — build unit dependency graph from method call graph
    # -----------------------------------------------------------------------

    def ResolveDeps(self, params):
        conn = self._Conn()
        orch = self._OrchConn()

        units = conn.execute(
            "SELECT unit_id, unit_name, method_ids FROM execution_units"
        ).fetchall()

        unit_method_names = {}
        unit_method_ids = {}
        for u in units:
            mids = json.loads(u["method_ids"])
            unit_method_ids[u["unit_name"]] = mids
            mid_to_name = {}
            for mid in mids:
                r = orch.execute(
                    "SELECT name FROM methods WHERE method_id = ?", (mid,)
                ).fetchone()
                if r:
                    mid_to_name[mid] = r["name"]
            unit_method_names[u["unit_name"]] = mid_to_name

        all_method_names = set()
        for names in unit_method_names.values():
            all_method_names.update(names.values())

        conn.execute("DELETE FROM unit_deps")

        edges_added = 0
        for u in units:
            uname = u["unit_name"]
            mids = unit_method_ids.get(uname, [])
            for mid in mids:
                calls = orch.execute(
                    "SELECT called_name FROM method_calls WHERE caller_id = ?",
                    (mid,)
                ).fetchall()
                for c in calls:
                    cname = c["called_name"]
                    if cname not in all_method_names:
                        continue
                    for other_u in units:
                        if other_u["unit_name"] == uname:
                            continue
                        other_names = set(unit_method_names.get(other_u["unit_name"], {}).values())
                        if cname in other_names:
                            exists = conn.execute(
                                "SELECT 1 FROM unit_deps WHERE unit_id = ? AND depends_on = ?",
                                (u["unit_id"], other_u["unit_id"])
                            ).fetchone()
                            if not exists:
                                conn.execute(
                                    "INSERT INTO unit_deps (unit_id, depends_on, dep_type) VALUES (?,?,?)",
                                    (u["unit_id"], other_u["unit_id"], "call")
                                )
                                edges_added += 1

        conn.commit()
        return (1, {"dependency_edges": edges_added, "units": len(units)}, None)

    # -----------------------------------------------------------------------
    # DETECT CONFLICTS — find signature mismatches, state conflicts, cycles
    # -----------------------------------------------------------------------

    def DetectConflicts(self, params):
        conn = self._Conn()
        orch = self._OrchConn()

        conn.execute("DELETE FROM conflicts")
        conflicts = []

        units = conn.execute(
            "SELECT unit_id, unit_name, method_ids FROM execution_units"
        ).fetchall()

        unit_map = {u["unit_name"]: u for u in units}

        # Conflict 1: Same method name, different signatures across units
        name_to_units = defaultdict(list)
        for u in units:
            mids = json.loads(u["method_ids"])
            for mid in mids:
                r = orch.execute(
                    "SELECT name, arg_names FROM methods WHERE method_id = ?",
                    (mid,)
                ).fetchone()
                if r:
                    name_to_units[r["name"]].append({
                        "unit": u["unit_name"],
                        "args": r["arg_names"] or "",
                    })

        for name, entries in name_to_units.items():
            if len(entries) < 2:
                continue
            arg_sets = set(e["args"] for e in entries)
            if len(arg_sets) > 1:
                units_involved = list(set(e["unit"] for e in entries))
                for i in range(len(units_involved)):
                    for j in range(i + 1, len(units_involved)):
                        conn.execute(
                            "INSERT INTO conflicts (unit_a, unit_b, conflict_type, detail, severity) "
                            "VALUES (?,?,?,?,?)",
                            (units_involved[i], units_involved[j],
                             "signature_mismatch",
                             f"method '{name}' has different args: {arg_sets}",
                             "warning")
                        )
                        conflicts.append({
                            "type": "signature_mismatch",
                            "units": [units_involved[i], units_involved[j]],
                            "method": name,
                            "severity": "warning",
                        })

        # Conflict 2: Circular dependencies (cycles in unit graph)
        adj = defaultdict(list)
        for u in units:
            deps = conn.execute(
                "SELECT depends_on FROM unit_deps WHERE unit_id = ?",
                (u["unit_id"],)
            ).fetchall()
            for d in deps:
                dep_unit = conn.execute(
                    "SELECT unit_name FROM execution_units WHERE unit_id = ?",
                    (d["depends_on"],)
                ).fetchone()
                if dep_unit:
                    adj[u["unit_name"]].append(dep_unit["unit_name"])

        cycles = self._FindCycles(adj)
        for cycle in cycles:
            for i in range(len(cycle)):
                a = cycle[i]
                b = cycle[(i + 1) % len(cycle)]
                conn.execute(
                    "INSERT INTO conflicts (unit_a, unit_b, conflict_type, detail, severity) "
                    "VALUES (?,?,?,?,?)",
                    (a, b, "circular_dependency",
                     f"cycle: {' -> '.join(cycle)} -> {cycle[0]}",
                     "error")
                )
                conflicts.append({
                    "type": "circular_dependency",
                    "units": cycle,
                    "severity": "error",
                })

        # Conflict 3: Missing dependencies (method calls something not in any unit)
        for u in units:
            mids = json.loads(u["method_ids"])
            for mid in mids:
                calls = orch.execute(
                    "SELECT called_name FROM method_calls WHERE caller_id = ?",
                    (mid,)
                ).fetchall()
                for c in calls:
                    cname = c["called_name"]
                    if cname not in name_to_units and cname not in self.BUILTIN_NAMES:
                        conn.execute(
                            "INSERT INTO conflicts (unit_a, unit_b, conflict_type, detail, severity) "
                            "VALUES (?,?,?,?,?)",
                            (u["unit_name"], "<missing>", "missing_dependency",
                             f"calls '{cname}' but no unit provides it",
                             "warning")
                        )
                        conflicts.append({
                            "type": "missing_dependency",
                            "unit": u["unit_name"],
                            "missing": cname,
                            "severity": "warning",
                        })

        conn.commit()
        self.state["stats"]["conflicts_detected"] = len(conflicts)
        return (1, {
            "conflicts": conflicts,
            "count": len(conflicts),
            "errors": sum(1 for c in conflicts if c["severity"] == "error"),
            "warnings": sum(1 for c in conflicts if c["severity"] == "warning"),
        }, None)

    def _FindCycles(self, adj):
        cycles = []
        # Check for self-loops
        for node in adj:
            if node in adj.get(node, []):
                cycles.append([node, node])
        visited = set()
        stack = []
        on_stack = set()

        def dfs(node):
            if node in on_stack:
                idx = stack.index(node)
                cycles.append(stack[idx:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            on_stack.add(node)
            stack.append(node)
            for neighbor in adj.get(node, []):
                dfs(neighbor)
            stack.pop()
            on_stack.discard(node)

        for node in adj:
            dfs(node)

        return cycles

    # -----------------------------------------------------------------------
    # CREATE PLAN — topological sort of units into an execution plan
    # -----------------------------------------------------------------------

    def CreatePlan(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        unit_names = self._p(params, "unit_names", [])
        if not unit_names:
            return self._err("NO_UNITS", "unit_names required")

        conn = self._Conn()

        unit_ids = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if not r:
                return self._err("UNIT_NOT_FOUND", un)
            unit_ids[un] = r["unit_id"]

        adj = defaultdict(list)
        in_degree = {un: 0 for un in unit_names}
        unit_set = set(unit_names)

        for un in unit_names:
            deps = conn.execute(
                "SELECT eu.unit_name FROM unit_deps ud "
                "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                "WHERE ud.unit_id = ?",
                (unit_ids[un],)
            ).fetchall()
            for d in deps:
                dep_name = d["unit_name"]
                if dep_name in unit_set:
                    adj[dep_name].append(un)
                    in_degree[un] += 1

        queue = deque([un for un in unit_names if in_degree[un] == 0])
        order = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(unit_names):
            unresolved = [un for un in unit_names if un not in order]
            return self._err("CYCLE_DETECTED",
                             f"unresolved units (circular dep): {unresolved}")

        conn.execute(
            "INSERT OR REPLACE INTO execution_plans "
            "(plan_name, unit_names, step_order, description, created_at) "
            "VALUES (?,?,?,?,?)",
            (plan_name, json.dumps(unit_names), json.dumps(order),
             self._p(params, "description", ""), time.time())
        )
        conn.commit()

        self.state["stats"]["plans_created"] += 1
        return (1, {
            "plan_name": plan_name,
            "units": len(unit_names),
            "execution_order": order,
        }, None)

    # -----------------------------------------------------------------------
    # EXECUTE PLAN — run units in topological order with rollback safety
    # -----------------------------------------------------------------------

    def ExecutePlan(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        init_state = self._p(params, "init_state", {})
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        orch = self._OrchConn()

        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])
        unit_names = json.loads(plan["unit_names"])

        runtime_state = dict(init_state)
        results = []
        log_entries = []
        snapshot_id = None

        snapshot = conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, -1, json.dumps(runtime_state, default=str), time.time())
        )
        snapshot_id = snapshot.lastrowid

        executed_steps = 0
        rolled_back = False

        for i, unit_name in enumerate(step_order):
            t0 = time.time()

            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, i, json.dumps(runtime_state, default=str), time.time())
            )

            try:
                ok, unit_result, err = self._ExecuteUnit(
                    unit_name, runtime_state, entry_command, entry_params
                )
                duration = (time.time() - t0) * 1000

                if ok:
                    if isinstance(unit_result, dict):
                        runtime_state.update(unit_result.get("state_update", {}))
                    log_entries.append({
                        "step": i, "unit": unit_name, "status": "ok",
                        "duration_ms": duration, "result": unit_result,
                    })
                    results.append({
                        "step": i, "unit": unit_name, "status": "ok",
                        "duration_ms": round(duration, 2),
                    })
                    executed_steps += 1
                else:
                    log_entries.append({
                        "step": i, "unit": unit_name, "status": "error",
                        "duration_ms": duration, "error": str(err),
                    })
                    results.append({
                        "step": i, "unit": unit_name, "status": "error",
                        "error": str(err), "duration_ms": round(duration, 2),
                    })

                    rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                    if rollback_state is not None:
                        runtime_state = rollback_state
                        rolled_back = True
                    break

            except Exception as e:
                duration = (time.time() - t0) * 1000
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "exception",
                    "duration_ms": duration, "error": str(e),
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "exception",
                    "error": str(e), "duration_ms": round(duration, 2),
                })
                rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1
        if rolled_back:
            self.state["stats"]["rollbacks"] += 1

        return (1, {
            "plan_name": plan_name,
            "steps_total": len(step_order),
            "steps_executed": executed_steps,
            "rolled_back": rolled_back,
            "final_state": runtime_state,
            "results": results,
        }, None)

    def _ExecuteUnit(self, unit_name, runtime_state, entry_command="read_state", entry_params=None):
        conn = self._Conn()
        orch = self._OrchConn()

        unit = conn.execute(
            "SELECT method_ids FROM execution_units WHERE unit_name = ?",
            (unit_name,)
        ).fetchone()
        if not unit:
            return self._err("UNIT_NOT_FOUND", unit_name)

        method_ids = json.loads(unit["method_ids"])

        shared_ns = {}
        self._InjectStdlib(shared_ns)

        compiled = []
        slot_names = []
        for mid in method_ids:
            cache_key = "unit:" + str(mid)
            with self.state["cache_lock"]:
                code_obj = self.state["compile_cache"].get(cache_key)
            if code_obj is None:
                r = orch.execute(
                    "SELECT source_code, name FROM methods WHERE method_id = ?",
                    (mid,)
                ).fetchone()
                if not r or not r["source_code"]:
                    continue
                try:
                    tree = ast.parse(r["source_code"])
                    code_obj = compile(tree, f"<unit://{unit_name}.{r['name']}>", "exec")
                except Exception:
                    continue
                with self.state["cache_lock"]:
                    if len(self.state["compile_cache"]) >= self.state["max_cache_size"]:
                        self.state["compile_cache"].clear()
                    self.state["compile_cache"][cache_key] = code_obj
            compiled.append((cache_key, mid))
            r2 = orch.execute(
                "SELECT name FROM methods WHERE method_id = ?", (mid,)
            ).fetchone()
            if r2:
                slot_names.append(r2["name"])

        for cache_key, mid in compiled:
            with self.state["cache_lock"]:
                code_obj = self.state["compile_cache"].get(cache_key)
            if code_obj is None:
                continue
            try:
                exec(code_obj, shared_ns)
            except Exception:
                continue

        entry_point = None
        for candidate in ("Run", "run", "Execute", "execute"):
            if candidate in shared_ns:
                entry_point = candidate
                break
        if entry_point is None:
            for sn in slot_names:
                if sn in shared_ns:
                    entry_point = sn
                    break

        if entry_point and entry_point in shared_ns:
            func = shared_ns[entry_point]
            try:
                namespace = {}
                for sn in slot_names:
                    if sn in shared_ns:
                        namespace[sn] = shared_ns[sn]

                if "__init__" not in namespace:
                    def _default_init(self, **kwargs):
                        for k, v in kwargs.items():
                            setattr(self, k, v)
                        if not hasattr(self, "state"):
                            self.state = {}
                    namespace["__init__"] = _default_init

                cls = type(unit_name, (object,), namespace)
                instance = cls(state=dict(runtime_state), config={})

                if entry_point == "Run":
                    result = instance.Run(entry_command, entry_params or {})
                else:
                    method = types.MethodType(func, instance)
                    result = method({})

                state_update = {}
                if isinstance(result, tuple) and len(result) == 3:
                    ok, data, err = result
                    if ok and isinstance(data, dict):
                        state_update = data
                    return (1, {
                        "unit": unit_name,
                        "entry_point": entry_point,
                        "result": result,
                        "state_update": state_update,
                    }, None)
                elif isinstance(result, dict):
                    state_update = result
                    return (1, {
                        "unit": unit_name,
                        "entry_point": entry_point,
                        "result": result,
                        "state_update": state_update,
                    }, None)
                else:
                    return (1, {
                        "unit": unit_name,
                        "entry_point": entry_point,
                        "result": str(result)[:200],
                        "state_update": {},
                    }, None)
            except Exception as e:
                return self._err("UNIT_EXEC_ERROR", f"{unit_name}: {e}")

        return (1, {
            "unit": unit_name,
            "entry_point": entry_point,
            "result": "no_entry_point",
            "state_update": {},
        }, None)

    def _RollbackTo(self, conn, plan_name, step_index):
        if step_index < 0:
            r = conn.execute(
                "SELECT state_json FROM state_snapshots "
                "WHERE plan_name = ? AND step_index = -1 "
                "ORDER BY snapshot_id DESC LIMIT 1",
                (plan_name,)
            ).fetchone()
        else:
            r = conn.execute(
                "SELECT state_json FROM state_snapshots "
                "WHERE plan_name = ? AND step_index = ? "
                "ORDER BY snapshot_id DESC LIMIT 1",
                (plan_name, step_index)
            ).fetchone()
        if r:
            try:
                return json.loads(r["state_json"])
            except Exception:
                return None
        return None

    # -----------------------------------------------------------------------
    # ROLLBACK — manually rollback to a specific step
    # -----------------------------------------------------------------------

    def Rollback(self, params):
        plan_name = self._p(params, "plan_name")
        step_index = self._p(params, "step_index", -1)
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        conn = self._Conn()
        state = self._RollbackTo(conn, plan_name, step_index)
        if state is None:
            return self._err("SNAPSHOT_NOT_FOUND", f"{plan_name} step {step_index}")
        return (1, {
            "plan_name": plan_name,
            "rolled_back_to": step_index,
            "state": state,
        }, None)

    # -----------------------------------------------------------------------
    # LIST / INFO
    # -----------------------------------------------------------------------

    def ListUnits(self, params=None):
        conn = self._Conn()
        rows = conn.execute(
            "SELECT u.unit_id, u.unit_name, u.method_names, u.description, "
            "COUNT(ud.depends_on) as dep_count "
            "FROM execution_units u "
            "LEFT JOIN unit_deps ud ON u.unit_id = ud.unit_id "
            "GROUP BY u.unit_id ORDER BY u.unit_id"
        ).fetchall()
        units = []
        for r in rows:
            units.append({
                "unit_name": r["unit_name"],
                "methods": json.loads(r["method_names"]),
                "deps": r["dep_count"],
                "description": r["description"] or "",
            })
        return (1, {"units": units, "count": len(units)}, None)

    def ListPlans(self, params=None):
        conn = self._Conn()
        rows = conn.execute(
            "SELECT * FROM execution_plans ORDER BY plan_id"
        ).fetchall()
        plans = []
        for r in rows:
            plans.append({
                "plan_name": r["plan_name"],
                "units": json.loads(r["unit_names"]),
                "order": json.loads(r["step_order"]),
            })
        return (1, {"plans": plans, "count": len(plans)}, None)

    def UnitInfo(self, params):
        unit_name = self._p(params, "unit_name")
        if not unit_name:
            return self._err("NO_UNIT_NAME", "unit_name required")
        conn = self._Conn()
        orch = self._OrchConn()
        u = conn.execute(
            "SELECT * FROM execution_units WHERE unit_name = ?",
            (unit_name,)
        ).fetchone()
        if not u:
            return self._err("NOT_FOUND", unit_name)

        deps = conn.execute(
            "SELECT eu.unit_name, ud.dep_type FROM unit_deps ud "
            "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
            "WHERE ud.unit_id = ?",
            (u["unit_id"],)
        ).fetchall()

        dependents = conn.execute(
            "SELECT eu.unit_name FROM unit_deps ud "
            "JOIN execution_units eu ON ud.unit_id = eu.unit_id "
            "WHERE ud.depends_on = ?",
            (u["unit_id"],)
        ).fetchall()

        method_ids = json.loads(u["method_ids"])
        methods = []
        for mid in method_ids:
            r = orch.execute(
                "SELECT name, arg_names, cyclomatic, body_lines, origin_class "
                "FROM methods WHERE method_id = ?",
                (mid,)
            ).fetchone()
            if r:
                methods.append({
                    "name": r["name"],
                    "args": r["arg_names"],
                    "cx": r["cyclomatic"],
                    "lines": r["body_lines"],
                    "origin": r["origin_class"],
                })

        return (1, {
            "unit_name": unit_name,
            "methods": methods,
            "dependencies": [d["unit_name"] for d in deps],
            "dependents": [d["unit_name"] for d in dependents],
            "fingerprint": u["ast_fingerprint"][:16] if u["ast_fingerprint"] else "",
        }, None)

    def PlanInfo(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        conn = self._Conn()
        p = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not p:
            return self._err("NOT_FOUND", plan_name)

        logs = conn.execute(
            "SELECT * FROM execution_log WHERE plan_name = ? ORDER BY step_index",
            (plan_name,)
        ).fetchall()
        log_entries = []
        for l in logs:
            log_entries.append({
                "step": l["step_index"],
                "unit": l["unit_name"],
                "status": l["status"],
                "duration_ms": l["duration_ms"],
                "error": l["error_msg"],
            })

        return (1, {
            "plan_name": plan_name,
            "units": json.loads(p["unit_names"]),
            "execution_order": json.loads(p["step_order"]),
            "execution_log": log_entries,
        }, None)

    def ExecutionLog(self, params):
        plan_name = self._p(params, "plan_name")
        conn = self._Conn()
        if plan_name:
            rows = conn.execute(
                "SELECT * FROM execution_log WHERE plan_name = ? ORDER BY log_id",
                (plan_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM execution_log ORDER BY log_id DESC LIMIT 50"
            ).fetchall()
        entries = []
        for r in rows:
            entries.append({
                "plan": r["plan_name"],
                "step": r["step_index"],
                "unit": r["unit_name"],
                "status": r["status"],
                "duration_ms": r["duration_ms"],
                "error": r["error_msg"],
            })
        return (1, {"log": entries, "count": len(entries)}, None)

    # -----------------------------------------------------------------------
    # STATS / STATE / CONFIG
    # -----------------------------------------------------------------------

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "units": conn.execute("SELECT COUNT(*) FROM execution_units").fetchone()[0],
            "deps": conn.execute("SELECT COUNT(*) FROM unit_deps").fetchone()[0],
            "plans": conn.execute("SELECT COUNT(*) FROM execution_plans").fetchone()[0],
            "log_entries": conn.execute("SELECT COUNT(*) FROM execution_log").fetchone()[0],
            "snapshots": conn.execute("SELECT COUNT(*) FROM state_snapshots").fetchone()[0],
            "conflicts": conn.execute("SELECT COUNT(*) FROM conflicts WHERE resolved = 0").fetchone()[0],
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

    def Close(self, params=None):
        """Close all database connections."""
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
    # PARALLEL EXECUTE — run independent units in parallel batches
    # -----------------------------------------------------------------------

    def ParallelExecute(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        init_state = self._p(params, "init_state", {})
        max_workers = self._p(params, "max_workers", self.MAX_WORKERS)
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])
        unit_names = json.loads(plan["unit_names"])
        unit_set = set(unit_names)

        unit_ids = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if r:
                unit_ids[un] = r["unit_id"]

        adj = defaultdict(list)
        in_degree = {un: 0 for un in unit_names}
        for un in unit_names:
            deps = conn.execute(
                "SELECT eu.unit_name FROM unit_deps ud "
                "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                "WHERE ud.unit_id = ?",
                (unit_ids.get(un),)
            ).fetchall() if un in unit_ids else []
            for d in deps:
                dep_name = d["unit_name"]
                if dep_name in unit_set:
                    adj[dep_name].append(un)
                    in_degree[un] += 1

        runtime_state = dict(init_state)
        results = []
        log_entries = []
        executed_steps = 0
        rolled_back = False
        parallel_batches = 0
        state_lock = threading.Lock()

        snapshot = conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, -1, json.dumps(runtime_state, default=str), time.time())
        )

        step_counter = 0
        remaining = set(unit_names)
        completed = set()

        while remaining:
            batch = [un for un in remaining if in_degree[un] == 0]
            if not batch:
                rolled_back = True
                break

            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, step_counter, json.dumps(runtime_state, default=str), time.time())
            )

            batch_results = {}
            batch_errors = {}
            threads = []
            sem = threading.Semaphore(max_workers)

            def run_one(un, rs):
                sem.acquire()
                try:
                    t0 = time.time()
                    ok, unit_result, err = self._ExecuteUnit(
                        un, dict(rs), entry_command, entry_params
                    )
                    duration = (time.time() - t0) * 1000
                    with state_lock:
                        batch_results[un] = (ok, unit_result, err, duration)
                finally:
                    sem.release()

            for un in batch:
                t = threading.Thread(target=run_one, args=(un, runtime_state))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            batch_failed = False
            for un in batch:
                ok, unit_result, err, duration = batch_results[un]
                step_idx = step_counter
                if ok:
                    if isinstance(unit_result, dict):
                        with state_lock:
                            runtime_state.update(unit_result.get("state_update", {}))
                    log_entries.append({
                        "step": step_idx, "unit": un, "status": "ok",
                        "duration_ms": duration, "result": unit_result,
                    })
                    results.append({
                        "step": step_idx, "unit": un, "status": "ok",
                        "duration_ms": round(duration, 2),
                    })
                    executed_steps += 1
                    completed.add(un)
                else:
                    log_entries.append({
                        "step": step_idx, "unit": un, "status": "error",
                        "duration_ms": duration, "error": str(err),
                    })
                    results.append({
                        "step": step_idx, "unit": un, "status": "error",
                        "error": str(err), "duration_ms": round(duration, 2),
                    })
                    batch_failed = True

            for un in batch:
                remaining.discard(un)
                for neighbor in adj.get(un, []):
                    in_degree[neighbor] -= 1

            step_counter += 1
            parallel_batches += 1

            if batch_failed:
                rollback_state = self._RollbackTo(conn, plan_name, step_counter - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1
        if rolled_back:
            self.state["stats"]["rollbacks"] += 1

        return (1, {
            "plan_name": plan_name,
            "steps_total": len(step_order),
            "steps_executed": executed_steps,
            "parallel_batches": parallel_batches,
            "rolled_back": rolled_back,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # RETRY EXECUTE — retry failed units up to max_retries
    # -----------------------------------------------------------------------

    def RetryExecute(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        init_state = self._p(params, "init_state", {})
        max_retries = self._p(params, "max_retries", self.DEFAULT_RETRIES)
        retry_delay = self._p(params, "retry_delay", self.DEFAULT_RETRY_DELAY)
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])
        runtime_state = dict(init_state)
        results = []
        log_entries = []
        attempts = []
        executed_steps = 0
        rolled_back = False
        final_status = "ok"

        conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, -1, json.dumps(runtime_state, default=str), time.time())
        )

        for i, unit_name in enumerate(step_order):
            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, i, json.dumps(runtime_state, default=str), time.time())
            )

            unit_attempts = []
            unit_ok = False
            unit_result = None
            unit_err = None
            duration = 0.0

            for attempt in range(max_retries + 1):
                t0 = time.time()
                ok, result, err = self._ExecuteUnit(
                    unit_name, runtime_state, entry_command, entry_params
                )
                duration = (time.time() - t0) * 1000
                unit_attempts.append({
                    "attempt": attempt + 1,
                    "status": "ok" if ok else "failed",
                    "duration_ms": round(duration, 2),
                    "error": str(err) if err else None,
                })
                if ok:
                    unit_ok = True
                    unit_result = result
                    break
                unit_err = err
                if attempt < max_retries:
                    time.sleep(retry_delay)

            attempts.append({"unit": unit_name, "attempts": unit_attempts})

            if unit_ok:
                if isinstance(unit_result, dict):
                    runtime_state.update(unit_result.get("state_update", {}))
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": duration, "result": unit_result,
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": round(duration, 2),
                    "attempts": len(unit_attempts),
                })
                executed_steps += 1
            else:
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "duration_ms": duration, "error": str(unit_err),
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "error": str(unit_err), "duration_ms": round(duration, 2),
                    "attempts": len(unit_attempts),
                })
                rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                final_status = "failed"
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1
        if rolled_back:
            self.state["stats"]["rollbacks"] += 1

        return (1, {
            "plan_name": plan_name,
            "attempts": attempts,
            "final_status": final_status,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # TIMEOUT EXECUTE — per-unit timeout
    # -----------------------------------------------------------------------

    def TimeoutExecute(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        init_state = self._p(params, "init_state", {})
        unit_timeout = self._p(params, "unit_timeout", self.DEFAULT_TIMEOUT)
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])
        runtime_state = dict(init_state)
        results = []
        log_entries = []
        timeouts = []
        executed_steps = 0
        rolled_back = False

        conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, -1, json.dumps(runtime_state, default=str), time.time())
        )

        for i, unit_name in enumerate(step_order):
            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, i, json.dumps(runtime_state, default=str), time.time())
            )

            container = {"ok": None, "result": None, "err": None, "duration": 0.0}

            def worker():
                t0 = time.time()
                ok, result, err = self._ExecuteUnit(
                    unit_name, runtime_state, entry_command, entry_params
                )
                container["ok"] = ok
                container["result"] = result
                container["err"] = err
                container["duration"] = (time.time() - t0) * 1000

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join(timeout=unit_timeout)

            if t.is_alive():
                timeouts.append({
                    "step": i, "unit": unit_name,
                    "timeout": unit_timeout, "status": "timeout",
                })
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "timeout",
                    "duration_ms": unit_timeout * 1000, "error": "unit timed out",
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "timeout",
                    "error": "unit timed out",
                    "duration_ms": round(unit_timeout * 1000, 2),
                })
                rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                break

            ok = container["ok"]
            duration = container["duration"]

            if ok:
                unit_result = container["result"]
                if isinstance(unit_result, dict):
                    runtime_state.update(unit_result.get("state_update", {}))
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": duration, "result": unit_result,
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": round(duration, 2),
                })
                executed_steps += 1
            else:
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "duration_ms": duration, "error": str(container["err"]),
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "error": str(container["err"]),
                    "duration_ms": round(duration, 2),
                })
                rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1
        if rolled_back:
            self.state["stats"]["rollbacks"] += 1

        return (1, {
            "plan_name": plan_name,
            "timeouts": timeouts,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # CONDITIONAL PLAN — skip units whose condition is false
    # -----------------------------------------------------------------------

    def ConditionalPlan(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        conditions = self._p(params, "conditions", {})
        init_state = self._p(params, "init_state", {})
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])
        runtime_state = dict(init_state)
        results = []
        log_entries = []
        executed = 0
        skipped = 0

        conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, -1, json.dumps(runtime_state, default=str), time.time())
        )

        safe_globals = {"__builtins__": {}}

        for i, unit_name in enumerate(step_order):
            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, i, json.dumps(runtime_state, default=str), time.time())
            )

            cond = conditions.get(unit_name)
            should_run = True
            if cond is not None:
                try:
                    should_run = bool(eval(cond, safe_globals, runtime_state))
                except Exception:
                    should_run = False

            if not should_run:
                results.append({
                    "step": i, "unit": unit_name, "status": "skipped",
                    "condition": cond,
                })
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "skipped",
                    "duration_ms": 0.0, "result": None,
                })
                skipped += 1
                continue

            t0 = time.time()
            ok, unit_result, err = self._ExecuteUnit(
                unit_name, runtime_state, entry_command, entry_params
            )
            duration = (time.time() - t0) * 1000

            if ok:
                if isinstance(unit_result, dict):
                    runtime_state.update(unit_result.get("state_update", {}))
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": duration, "result": unit_result,
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": round(duration, 2),
                })
                executed += 1
            else:
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "duration_ms": duration, "error": str(err),
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "error": str(err), "duration_ms": round(duration, 2),
                })
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1

        return (1, {
            "plan_name": plan_name,
            "executed": executed,
            "skipped": skipped,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # EXPORT PLAN — export plan as JSON string
    # -----------------------------------------------------------------------

    def ExportPlan(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        unit_names = json.loads(plan["unit_names"])
        step_order = json.loads(plan["step_order"])

        units_data = []
        deps_data = []
        for un in unit_names:
            u = conn.execute(
                "SELECT * FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if u:
                units_data.append({
                    "unit_name": u["unit_name"],
                    "method_ids": json.loads(u["method_ids"]),
                    "method_names": json.loads(u["method_names"]),
                    "description": u["description"] or "",
                    "ast_fingerprint": u["ast_fingerprint"] or "",
                })
                deps = conn.execute(
                    "SELECT eu.unit_name, ud.dep_type FROM unit_deps ud "
                    "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                    "WHERE ud.unit_id = ?",
                    (u["unit_id"],)
                ).fetchall()
                for d in deps:
                    deps_data.append({
                        "unit": un,
                        "depends_on": d["unit_name"],
                        "dep_type": d["dep_type"],
                    })

        export = {
            "plan_name": plan_name,
            "unit_names": unit_names,
            "step_order": step_order,
            "description": plan["description"] or "",
            "units": units_data,
            "dependencies": deps_data,
        }

        return (1, json.dumps(export, indent=2, default=str), None)

    # -----------------------------------------------------------------------
    # IMPORT PLAN — import plan from JSON string
    # -----------------------------------------------------------------------

    def ImportPlan(self, params):
        json_str = self._p(params, "json")
        if not json_str:
            return self._err("NO_JSON", "json required")
        override_name = self._p(params, "plan_name")

        try:
            data = json.loads(json_str)
        except Exception as e:
            return self._err("INVALID_JSON", str(e))

        conn = self._Conn()
        orch = self._OrchConn()

        plan_name = override_name or data.get("plan_name", "imported_plan")
        units_imported = 0
        deps_imported = 0

        for u in data.get("units", []):
            unit_name = u["unit_name"]
            method_ids = u.get("method_ids", [])
            method_names = u.get("method_names", [])
            description = u.get("description", "")
            fingerprint = u.get("ast_fingerprint", "")

            existing = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (unit_name,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE execution_units SET method_ids=?, method_names=?, "
                    "description=?, ast_fingerprint=? WHERE unit_name=?",
                    (json.dumps(method_ids), json.dumps(method_names),
                     description, fingerprint, unit_name)
                )
            else:
                conn.execute(
                    "INSERT INTO execution_units "
                    "(unit_name, method_ids, method_names, description, "
                    "ast_fingerprint, created_at) VALUES (?,?,?,?,?,?)",
                    (unit_name, json.dumps(method_ids), json.dumps(method_names),
                     description, fingerprint, time.time())
                )
            units_imported += 1

        conn.commit()

        for d in data.get("dependencies", []):
            u_row = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (d["unit"],)
            ).fetchone()
            dep_row = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (d["depends_on"],)
            ).fetchone()
            if u_row and dep_row:
                exists = conn.execute(
                    "SELECT 1 FROM unit_deps WHERE unit_id=? AND depends_on=?",
                    (u_row["unit_id"], dep_row["unit_id"])
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO unit_deps (unit_id, depends_on, dep_type) VALUES (?,?,?)",
                        (u_row["unit_id"], dep_row["unit_id"],
                         d.get("dep_type", "call"))
                    )
                    deps_imported += 1

        unit_names = data.get("unit_names", [])
        step_order = data.get("step_order", unit_names)

        conn.execute(
            "INSERT OR REPLACE INTO execution_plans "
            "(plan_name, unit_names, step_order, description, created_at) "
            "VALUES (?,?,?,?,?)",
            (plan_name, json.dumps(unit_names), json.dumps(step_order),
             data.get("description", ""), time.time())
        )

        conn.commit()
        return (1, {
            "plan_name": plan_name,
            "units_imported": units_imported,
            "deps_imported": deps_imported,
        }, None)

    # -----------------------------------------------------------------------
    # VISUALIZE — text-based DAG visualization
    # -----------------------------------------------------------------------

    def Visualize(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        unit_names = json.loads(plan["unit_names"])
        step_order = json.loads(plan["step_order"])

        unit_ids = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if r:
                unit_ids[un] = r["unit_id"]

        deps_map = {}
        for un in unit_names:
            deps = []
            if un in unit_ids:
                rows = conn.execute(
                    "SELECT eu.unit_name FROM unit_deps ud "
                    "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                    "WHERE ud.unit_id = ?",
                    (unit_ids[un],)
                ).fetchall()
                deps = [r["unit_name"] for r in rows if r["unit_name"] in set(unit_names)]
            deps_map[un] = deps

        lines = []
        lines.append(f"Plan: {plan_name}")
        for idx, un in enumerate(step_order):
            deps = deps_map.get(un, [])
            if deps:
                dep_str = ", ".join(deps)
                lines.append(f"  [{idx}] {un} (depends: {dep_str})")
            else:
                lines.append(f"  [{idx}] {un} (no deps)")
            if idx < len(step_order) - 1:
                lines.append("   |")
        viz = "\n".join(lines)
        return (1, viz, None)

    # -----------------------------------------------------------------------
    # VALIDATE PLAN — pre-execution validation
    # -----------------------------------------------------------------------

    def ValidatePlan(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")

        conn = self._Conn()
        orch = self._OrchConn()

        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        unit_names = json.loads(plan["unit_names"])
        step_order = json.loads(plan["step_order"])
        issues = []
        warnings = []

        unit_ids = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id, method_ids FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if not r:
                issues.append(f"unit '{un}' does not exist")
            else:
                unit_ids[un] = r

        adj = defaultdict(list)
        for un in unit_names:
            if un not in unit_ids:
                continue
            deps = conn.execute(
                "SELECT eu.unit_name FROM unit_deps ud "
                "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                "WHERE ud.unit_id = ?",
                (unit_ids[un]["unit_id"],)
            ).fetchall()
            for d in deps:
                dep_name = d["unit_name"]
                if dep_name not in unit_names:
                    issues.append(
                        f"unit '{un}' depends on '{dep_name}' which is not in the plan"
                    )
                else:
                    adj[dep_name].append(un)

        cycles = self._FindCycles(adj)
        for cycle in cycles:
            issues.append(f"circular dependency: {' -> '.join(cycle)} -> {cycle[0]}")

        conflicts = conn.execute(
            "SELECT * FROM conflicts WHERE resolved = 0 "
            "AND (unit_a IN ({}) OR unit_b IN ({}))".format(
                ",".join("?" * len(unit_names)),
                ",".join("?" * len(unit_names))
            ),
            unit_names + unit_names
        ).fetchall()
        for c in conflicts:
            if c["severity"] == "error":
                issues.append(
                    f"unresolved conflict: {c['conflict_type']} between "
                    f"{c['unit_a']} and {c['unit_b']}"
                )
            else:
                warnings.append(
                    f"conflict warning: {c['conflict_type']} between "
                    f"{c['unit_a']} and {c['unit_b']}"
                )

        for un in unit_names:
            if un not in unit_ids:
                continue
            method_ids = json.loads(unit_ids[un]["method_ids"])
            for mid in method_ids:
                r = orch.execute(
                    "SELECT source_code FROM methods WHERE method_id = ?",
                    (mid,)
                ).fetchone()
                if not r:
                    issues.append(f"unit '{un}': method_id {mid} not found in orchestrator")
                elif not r["source_code"]:
                    warnings.append(f"unit '{un}': method_id {mid} has no source code")

        valid = len(issues) == 0
        return (1, {
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
        }, None)

    # -----------------------------------------------------------------------
    # REPLAY — replay execution from a specific step
    # -----------------------------------------------------------------------

    def Replay(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        from_step = self._p(params, "from_step", 0)
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn = self._Conn()
        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        step_order = json.loads(plan["step_order"])

        restore_state = self._RollbackTo(conn, plan_name, from_step - 1)
        if restore_state is None:
            restore_state = {}
        runtime_state = dict(restore_state)
        results = []
        log_entries = []
        executed_steps = 0
        rolled_back = False

        conn.execute(
            "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
            "VALUES (?,?,?,?)",
            (plan_name, from_step - 1, json.dumps(runtime_state, default=str), time.time())
        )

        for i in range(from_step, len(step_order)):
            unit_name = step_order[i]
            conn.execute(
                "INSERT INTO state_snapshots (plan_name, step_index, state_json, timestamp) "
                "VALUES (?,?,?,?)",
                (plan_name, i, json.dumps(runtime_state, default=str), time.time())
            )

            t0 = time.time()
            ok, unit_result, err = self._ExecuteUnit(
                unit_name, runtime_state, entry_command, entry_params
            )
            duration = (time.time() - t0) * 1000

            if ok:
                if isinstance(unit_result, dict):
                    runtime_state.update(unit_result.get("state_update", {}))
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": duration, "result": unit_result,
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "ok",
                    "duration_ms": round(duration, 2),
                })
                executed_steps += 1
            else:
                log_entries.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "duration_ms": duration, "error": str(err),
                })
                results.append({
                    "step": i, "unit": unit_name, "status": "error",
                    "error": str(err), "duration_ms": round(duration, 2),
                })
                rollback_state = self._RollbackTo(conn, plan_name, i - 1)
                if rollback_state is not None:
                    runtime_state = rollback_state
                    rolled_back = True
                break

        for entry in log_entries:
            conn.execute(
                "INSERT INTO execution_log "
                "(plan_name, step_index, unit_name, status, duration_ms, "
                "result_json, error_msg, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (plan_name, entry["step"], entry["unit"], entry["status"],
                 entry["duration_ms"],
                 json.dumps(entry.get("result"), default=str) if entry.get("result") else None,
                 entry.get("error"), time.time())
            )

        conn.commit()
        self.state["stats"]["plans_executed"] += 1
        if rolled_back:
            self.state["stats"]["rollbacks"] += 1

        return (1, {
            "plan_name": plan_name,
            "replayed_from": from_step,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # PROFILE — execution profiling from log
    # -----------------------------------------------------------------------

    def Profile(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")

        conn = self._Conn()
        rows = conn.execute(
            "SELECT * FROM execution_log WHERE plan_name = ? "
            "ORDER BY log_id DESC LIMIT 1000",
            (plan_name,)
        ).fetchall()

        if not rows:
            return (1, {
                "total_time_ms": 0,
                "per_unit": [],
                "slowest": None,
                "fastest": None,
                "bottlenecks": [],
            }, None)

        per_unit = {}
        for r in rows:
            un = r["unit_name"]
            dur = r["duration_ms"] or 0.0
            if un not in per_unit:
                per_unit[un] = {"unit": un, "total_ms": 0.0, "calls": 0}
            per_unit[un]["total_ms"] += dur
            per_unit[un]["calls"] += 1

        total_time = sum(v["total_ms"] for v in per_unit.values())
        unit_list = []
        for v in per_unit.values():
            avg = v["total_ms"] / v["calls"] if v["calls"] else 0
            pct = (v["total_ms"] / total_time * 100) if total_time else 0
            unit_list.append({
                "unit": v["unit"],
                "total_ms": round(v["total_ms"], 2),
                "calls": v["calls"],
                "avg_ms": round(avg, 2),
                "pct": round(pct, 2),
            })
        unit_list.sort(key=lambda x: x["total_ms"], reverse=True)

        slowest = unit_list[0] if unit_list else None
        fastest = unit_list[-1] if unit_list else None
        bottlenecks = [u for u in unit_list if total_time and (u["total_ms"] / total_time) > 0.5]

        return (1, {
            "total_time_ms": round(total_time, 2),
            "per_unit": unit_list,
            "slowest": slowest,
            "fastest": fastest,
            "bottlenecks": bottlenecks,
        }, None)

    # -----------------------------------------------------------------------
    # STATE DIFF — diff state between two steps
    # -----------------------------------------------------------------------

    def StateDiff(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")
        step_a = self._p(params, "step_a", 0)
        step_b = self._p(params, "step_b", 1)

        conn = self._Conn()

        ra = conn.execute(
            "SELECT state_json FROM state_snapshots "
            "WHERE plan_name = ? AND step_index = ? "
            "ORDER BY snapshot_id DESC LIMIT 1",
            (plan_name, step_a)
        ).fetchone()
        rb = conn.execute(
            "SELECT state_json FROM state_snapshots "
            "WHERE plan_name = ? AND step_index = ? "
            "ORDER BY snapshot_id DESC LIMIT 1",
            (plan_name, step_b)
        ).fetchone()

        if not ra:
            return self._err("SNAPSHOT_NOT_FOUND", f"{plan_name} step {step_a}")
        if not rb:
            return self._err("SNAPSHOT_NOT_FOUND", f"{plan_name} step {step_b}")

        try:
            state_a = json.loads(ra["state_json"])
        except Exception:
            state_a = {}
        try:
            state_b = json.loads(rb["state_json"])
        except Exception:
            state_b = {}

        keys_a = set(state_a.keys())
        keys_b = set(state_b.keys())

        added = {k: state_b[k] for k in (keys_b - keys_a)}
        removed = list(keys_a - keys_b)
        changed = {}
        for k in (keys_a & keys_b):
            if state_a[k] != state_b[k]:
                changed[k] = {"from": state_a[k], "to": state_b[k]}

        return (1, {
            "added": added,
            "removed": removed,
            "changed": changed,
        }, None)

    # -----------------------------------------------------------------------
    # COST ESTIMATE — estimate execution cost
    # -----------------------------------------------------------------------

    def CostEstimate(self, params):
        plan_name = self._p(params, "plan_name")
        if not plan_name:
            return self._err("NO_PLAN_NAME", "plan_name required")

        conn = self._Conn()
        orch = self._OrchConn()

        plan = conn.execute(
            "SELECT * FROM execution_plans WHERE plan_name = ?",
            (plan_name,)
        ).fetchone()
        if not plan:
            return self._err("PLAN_NOT_FOUND", plan_name)

        unit_names = json.loads(plan["unit_names"])
        step_order = json.loads(plan["step_order"])

        hist_times = {}
        for un in unit_names:
            rows = conn.execute(
                "SELECT duration_ms FROM execution_log "
                "WHERE plan_name = ? AND unit_name = ? AND status = 'ok'",
                (plan_name, un)
            ).fetchall()
            if rows:
                hist_times[un] = sum(r["duration_ms"] for r in rows) / len(rows)

        unit_complexity = {}
        for un in unit_names:
            u = conn.execute(
                "SELECT method_ids FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if not u:
                unit_complexity[un] = 1
                continue
            method_ids = json.loads(u["method_ids"])
            total_cx = 0
            for mid in method_ids:
                r = orch.execute(
                    "SELECT cyclomatic, body_lines FROM methods WHERE method_id = ?",
                    (mid,)
                ).fetchone()
                if r:
                    total_cx += (r["cyclomatic"] or 1) + (r["body_lines"] or 1) // 10
            unit_complexity[un] = max(total_cx, 1)

        estimated_times = {}
        for un in step_order:
            if un in hist_times:
                estimated_times[un] = hist_times[un]
            else:
                estimated_times[un] = unit_complexity.get(un, 1) * 5.0

        total_time = sum(estimated_times.values())
        total_methods = sum(unit_complexity.values())
        estimated_memory = max(total_methods * 0.5, 1.0)

        unit_ids = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if r:
                unit_ids[un] = r["unit_id"]

        in_degree = {un: 0 for un in unit_names}
        for un in unit_names:
            if un not in unit_ids:
                continue
            deps = conn.execute(
                "SELECT eu.unit_name FROM unit_deps ud "
                "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                "WHERE ud.unit_id = ?",
                (unit_ids[un],)
            ).fetchall()
            for d in deps:
                if d["unit_name"] in in_degree:
                    in_degree[un] += 1

        max_parallel = sum(1 for v in in_degree.values() if v == 0)
        parallel_speedup = round(total_time / max(estimated_times.values()), 2) if estimated_times else 1.0

        bottleneck_unit = None
        if estimated_times:
            bottleneck_unit = max(estimated_times, key=estimated_times.get)

        return (1, {
            "estimated_time_ms": round(total_time, 2),
            "estimated_memory_mb": round(estimated_memory, 2),
            "parallel_speedup": parallel_speedup,
            "bottleneck_unit": bottleneck_unit,
        }, None)

    # -----------------------------------------------------------------------
    # EXPORT DOT — Graphviz DOT format
    # -----------------------------------------------------------------------

    def ExportDot(self, params):
        plan_name = self._p(params, "plan_name")
        conn = self._Conn()

        if plan_name:
            plan = conn.execute(
                "SELECT * FROM execution_plans WHERE plan_name = ?",
                (plan_name,)
            ).fetchone()
            if not plan:
                return self._err("PLAN_NOT_FOUND", plan_name)
            unit_names = json.loads(plan["unit_names"])
        else:
            rows = conn.execute(
                "SELECT unit_name FROM execution_units"
            ).fetchall()
            unit_names = [r["unit_name"] for r in rows]

        if not unit_names:
            return (1, "digraph execution_plan {\n  rankdir=TB;\n}\n", None)

        unit_ids = {}
        unit_method_counts = {}
        for un in unit_names:
            r = conn.execute(
                "SELECT unit_id, method_ids FROM execution_units WHERE unit_name = ?",
                (un,)
            ).fetchone()
            if r:
                unit_ids[un] = r["unit_id"]
                unit_method_counts[un] = len(json.loads(r["method_ids"]))
            else:
                unit_method_counts[un] = 0

        lines = []
        lines.append("digraph execution_plan {")
        lines.append("  rankdir=TB;")

        for un in unit_names:
            mc = unit_method_counts.get(un, 0)
            lines.append(
                f'  {un} [shape=box, label="{un}\\n({mc} methods)"];'
            )

        for un in unit_names:
            if un not in unit_ids:
                continue
            deps = conn.execute(
                "SELECT eu.unit_name FROM unit_deps ud "
                "JOIN execution_units eu ON ud.depends_on = eu.unit_id "
                "WHERE ud.unit_id = ?",
                (unit_ids[un],)
            ).fetchall()
            for d in deps:
                dep_name = d["unit_name"]
                if dep_name in unit_names:
                    lines.append(f"  {dep_name} -> {un};")

        lines.append("}")
        return (1, "\n".join(lines), None)

    # -----------------------------------------------------------------------
    # INTERNAL — stdlib injection
    # -----------------------------------------------------------------------

    def _InjectStdlib(self, ns):
        import time, json, re, sqlite3, hashlib
        import ast as _ast, collections, typing, traceback
        import functools, itertools, copy, math, random, textwrap
        import io, uuid, warnings
        import inspect, struct, base64, operator, string, pprint
        import errno, stat
        import weakref, gc, contextlib, decimal
        import fractions, array, dataclasses, enum, abc
        import bisect, heapq, numbers, statistics, types as _types

        std = {
            "time": time, "json": json, "re": re,
            "sqlite3": sqlite3, "hashlib": hashlib, "ast": _ast,
            "collections": collections,
            "typing": typing, "traceback": traceback, "functools": functools,
            "itertools": itertools, "copy": copy, "math": math,
            "random": random, "textwrap": textwrap, "io": io,
            "uuid": uuid, "warnings": warnings,
            "inspect": inspect, "struct": struct, "base64": base64,
            "operator": operator, "string": string, "pprint": pprint,
            "errno": errno, "stat": stat, "weakref": weakref,
            "gc": gc, "contextlib": contextlib, "decimal": decimal,
            "fractions": fractions, "array": array,
            "dataclasses": dataclasses, "enum": enum, "abc": abc,
            "bisect": bisect, "heapq": heapq, "numbers": numbers,
            "statistics": statistics, "types": _types,
        }
        for name in ("Optional", "List", "Dict", "Tuple", "Any", "Union",
                      "Set", "Callable", "Iterator", "Generator", "Sequence",
                      "Mapping", "TypeVar", "Generic", "NoReturn", "ClassVar"):
            if hasattr(typing, name):
                std[name] = getattr(typing, name)
        for name in ("defaultdict", "OrderedDict", "Counter", "deque",
                      "namedtuple", "ChainMap"):
            if hasattr(collections, name):
                std[name] = getattr(collections, name)
        for name in ("wraps", "lru_cache", "partial", "reduce", "singledispatch"):
            if hasattr(functools, name):
                std[name] = getattr(functools, name)
        for name in ("chain", "product", "combinations", "permutations",
                      "cycle", "islice", "groupby", "accumulate", "count",
                      "repeat", "starmap", "tee", "zip_longest"):
            if hasattr(itertools, name):
                std[name] = getattr(itertools, name)
        for name in ("dataclass", "field", "asdict", "astuple", "replace"):
            if hasattr(dataclasses, name):
                std[name] = getattr(dataclasses, name)
        for name in ("contextmanager", "suppress", "closing", "ExitStack"):
            if hasattr(contextlib, name):
                std[name] = getattr(contextlib, name)
        for name in ("BytesIO", "StringIO", "TextIO", "BufferedReader", "TextIOWrapper"):
            if hasattr(io, name):
                std[name] = getattr(io, name)
        for name in ("Enum", "IntEnum", "auto", "Flag", "IntFlag"):
            if hasattr(enum, name):
                std[name] = getattr(enum, name)
        for name in ("ABC", "abstractmethod", "abstractproperty"):
            if hasattr(abc, name):
                std[name] = getattr(abc, name)
        ns.update(std)


# ---------------------------------------------------------------------------
# TEST / DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    planner = ExecutionPlanner()
    planner.Run("stats", {})
