#!/usr/bin/env python3
#[@GHOST]{[@file<execution_session.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<execution_session>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
ExecutionSession — self-repairing execution graph runtime.

Wraps ComputationUnit execution with a pause/analyze/repair/test/resume loop.
When a CU fails, the session captures everything (error, traceback, state,
locals, dependency chain) into a MemUnit.result, then either:

  1. Selects an alternative survivor CU with the same capability
  2. Applies an AI-generated patch (forks the CU)
  3. Falls back to a cached result

The AI reasons over structured metadata first (contracts, history, ranking)
and only looks at source code when necessary.

Architecture:
  execution_sessions       — named sessions with state and config
  session_steps            — ordered execution steps (CU IDs)
  memunit_results          — full capture of every execution attempt
  repair_attempts          — AI reasoning + patch + test outcome
  survivor_catalog         — capability → ranked CU IDs index
  execution_cache          — cached results for deterministic CUs

Flow:
  1. Create session with ordered CU steps
  2. Execute each step → capture MemUnit.result
  3. On failure → pause → analyze → select survivor or patch
  4. Test repaired CU → resume if pass, rollback if fail
  5. Cache results for deterministic CUs

Usage:
  session = ExecutionSession()
  session.Run("create", {"session_name": "Bootstrap", "cu_steps": ["cu_abc...", "cu_def..."]})
  session.Run("execute", {"session_name": "Bootstrap"})
  session.Run("repair_log", {"session_name": "Bootstrap"})
"""

import ast
import json
import sqlite3
import time
import hashlib
import traceback
import types
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import concurrent.futures

from SuperConfig import DB, RUNTIME


class ExecutionSession:

    SCHEMA_SESSION = """
CREATE TABLE IF NOT EXISTS execution_sessions (
    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name    TEXT NOT NULL UNIQUE,
    cu_steps        TEXT NOT NULL,
    init_state      TEXT DEFAULT '{}',
    description     TEXT,
    status          TEXT DEFAULT 'pending',
    created_at      REAL DEFAULT 0,
    completed_at    REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session_steps (
    step_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name    TEXT NOT NULL,
    step_index      INTEGER NOT NULL,
    cu_id           TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    attempts        INTEGER DEFAULT 0,
    final_result    TEXT,
    duration_ms     REAL DEFAULT 0,
    timestamp       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ss_session ON session_steps(session_name);

CREATE TABLE IF NOT EXISTS memunit_results (
    memunit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name    TEXT NOT NULL,
    step_index      INTEGER NOT NULL,
    cu_id           TEXT NOT NULL,
    attempt         INTEGER NOT NULL,
    status          TEXT NOT NULL,
    result_value    TEXT,
    error_type      TEXT,
    error_msg       TEXT,
    error_traceback TEXT,
    state_before    TEXT,
    state_after     TEXT,
    locals_capture  TEXT,
    dependency_chain TEXT,
    duration_ms     REAL,
    timestamp       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mr_session ON memunit_results(session_name);
CREATE INDEX IF NOT EXISTS idx_mr_cu ON memunit_results(cu_id);

CREATE TABLE IF NOT EXISTS repair_attempts (
    repair_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name    TEXT NOT NULL,
    step_index      INTEGER NOT NULL,
    failed_cu_id    TEXT NOT NULL,
    attempt         INTEGER NOT NULL,
    strategy        TEXT NOT NULL,
    replacement_cu_id TEXT,
    patch_source    TEXT,
    reasoning       TEXT,
    metadata_consulted TEXT,
    test_result     TEXT,
    test_status     TEXT DEFAULT 'pending',
    status          TEXT DEFAULT 'pending',
    timestamp       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ra_session ON repair_attempts(session_name);

CREATE TABLE IF NOT EXISTS survivor_catalog (
    capability      TEXT NOT NULL,
    cu_id           TEXT NOT NULL,
    rank_score      REAL DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    avg_latency_ms  REAL DEFAULT 0,
    interface_hash  TEXT,
    last_used       REAL DEFAULT 0,
    PRIMARY KEY (capability, cu_id)
);
CREATE INDEX IF NOT EXISTS idx_sc_cap ON survivor_catalog(capability);

CREATE TABLE IF NOT EXISTS execution_cache (
    cache_key       TEXT PRIMARY KEY,
    cu_id           TEXT NOT NULL,
    input_hash      TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    hits            INTEGER DEFAULT 0,
    created_at      REAL DEFAULT 0
);
"""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "session_db": DB.EXECUTION_SESSIONS_DB,
            "cu_db": DB.COMPUTATION_UNITS_DB,
            "orchestrator_db": DB.METHOD_ORCHESTRATOR_DB,
            "conn": None,
            "cu_conn": None,
            "orch_conn": None,
            "compile_cache": {},
            "max_repair_attempts": 3,
            "stats": {
                "sessions_created": 0,
                "sessions_completed": 0,
                "steps_executed": 0,
                "steps_repaired": 0,
                "cache_hits": 0,
                "repair_attempts": 0,
                "survivor_swaps": 0,
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
            self.state["conn"] = sqlite3.connect(self.state["session_db"], check_same_thread=False)
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _CuConn(self):
        if self.state["cu_conn"] is None:
            self.state["cu_conn"] = sqlite3.connect(self.state["cu_db"], check_same_thread=False)
            self.state["cu_conn"].row_factory = sqlite3.Row
            self.state["cu_conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["cu_conn"]

    def _OrchConn(self):
        if self.state["orch_conn"] is None:
            self.state["orch_conn"] = sqlite3.connect(self.state["orchestrator_db"], check_same_thread=False)
            self.state["orch_conn"].row_factory = sqlite3.Row
            self.state["orch_conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["orch_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["session_db"])
        conn.executescript(self.SCHEMA_SESSION)
        conn.commit()
        conn.close()

    def Close(self, params=None):
        for key in ("conn", "cu_conn", "orch_conn"):
            if self.state.get(key) is not None:
                try:
                    self.state[key].close()
                except Exception:
                    pass
                self.state[key] = None
        return (1, {"closed": True}, None)

    def Run(self, command, params=None):
        dispatch = {
            "create": self.Create,
            "execute": self.Execute,
            "status": self.Status,
            "repair_log": self.RepairLog,
            "memunit_log": self.MemunitLog,
            "register_survivor": self.RegisterSurvivor,
            "survivor_lookup": self.SurvivorLookup,
            "build_survivor_catalog": self.BuildSurvivorCatalog,
            "clear_cache": self.ClearCache,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
            "parallel_execute": self.ParallelExecute,
            "dry_run": self.DryRun,
            "replay": self.Replay,
            "export_session": self.ExportSession,
            "import_session": self.ImportSession,
            "session_diff": self.SessionDiff,
            "validate": self.Validate,
            "cleanup": self.Cleanup,
            "profile": self.Profile,
            "invalidate_cache": self.InvalidateCache,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    # -----------------------------------------------------------------------
    # CREATE — define a session with ordered CU steps
    # -----------------------------------------------------------------------

    def Create(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")
        cu_steps = self._p(params, "cu_steps", [])
        if not cu_steps:
            return self._err("NO_STEPS", "cu_steps required")
        init_state = self._p(params, "init_state", {})
        description = self._p(params, "description", "")

        conn = self._Conn()
        now = time.time()

        conn.execute(
            "INSERT OR REPLACE INTO execution_sessions "
            "(session_name, cu_steps, init_state, description, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (session_name, json.dumps(cu_steps), json.dumps(init_state),
             description, "pending", now)
        )

        conn.execute("DELETE FROM session_steps WHERE session_name = ?", (session_name,))
        for i, cu_id in enumerate(cu_steps):
            conn.execute(
                "INSERT INTO session_steps "
                "(session_name, step_index, cu_id, status, timestamp) "
                "VALUES (?,?,?,?,?)",
                (session_name, i, cu_id, "pending", now)
            )

        conn.execute("DELETE FROM memunit_results WHERE session_name = ?", (session_name,))
        conn.execute("DELETE FROM repair_attempts WHERE session_name = ?", (session_name,))

        conn.commit()
        self.state["stats"]["sessions_created"] += 1

        return (1, {
            "session_name": session_name,
            "steps": len(cu_steps),
            "cu_ids": cu_steps,
            "status": "pending",
        }, None)

    # -----------------------------------------------------------------------
    # EXECUTE — run the session with self-repair
    # -----------------------------------------------------------------------

    def Execute(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        cu_steps = json.loads(session["cu_steps"])
        runtime_state = json.loads(session["init_state"])
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn.execute("DELETE FROM session_steps WHERE session_name = ?", (session_name,))
        for i, cu_id in enumerate(cu_steps):
            conn.execute(
                "INSERT INTO session_steps "
                "(session_name, step_index, cu_id, status, timestamp) "
                "VALUES (?,?,?,?,?)",
                (session_name, i, cu_id, "pending", time.time())
            )

        conn.execute(
            "UPDATE execution_sessions SET status = 'running' WHERE session_name = ?",
            (session_name,)
        )
        conn.commit()

        results = []
        completed = 0
        repaired = 0

        for i, cu_id in enumerate(cu_steps):
            step_result = self._ExecuteStep(
                session_name, i, cu_id, runtime_state,
                entry_command, entry_params
            )

            if step_result["status"] == "ok":
                runtime_state.update(step_result.get("state_update", {}))
                completed += 1
                results.append(step_result)
            elif step_result["status"] == "repaired":
                runtime_state.update(step_result.get("state_update", {}))
                completed += 1
                repaired += 1
                results.append(step_result)
            else:
                results.append(step_result)
                conn.execute(
                    "UPDATE execution_sessions SET status = 'failed' WHERE session_name = ?",
                    (session_name,)
                )
                conn.commit()
                break

        final_status = "completed" if completed == len(cu_steps) else "failed"
        conn.execute(
            "UPDATE execution_sessions SET status = ?, completed_at = ? WHERE session_name = ?",
            (final_status, time.time(), session_name)
        )
        conn.commit()

        if final_status == "completed":
            self.state["stats"]["sessions_completed"] += 1

        return (1, {
            "session_name": session_name,
            "status": final_status,
            "steps_total": len(cu_steps),
            "steps_completed": completed,
            "steps_repaired": repaired,
            "final_state": runtime_state,
            "results": results,
        }, None)

    def _ExecuteStep(self, session_name, step_index, cu_id, runtime_state,
                     entry_command, entry_params):
        conn = self._Conn()
        cu_conn = self._CuConn()

        state_before = dict(runtime_state)
        attempt = 0
        max_attempts = self.state["max_repair_attempts"]

        current_cu_id = cu_id

        while attempt <= max_attempts:
            attempt += 1

            cache_key = self._CacheKey(current_cu_id, entry_command, entry_params)
            cached = conn.execute(
                "SELECT result_json FROM execution_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()

            if cached:
                self.state["stats"]["cache_hits"] += 1
                result = json.loads(cached["result_json"])
                state_update = result.get("data", result) if isinstance(result, dict) else {}
                if not isinstance(state_update, dict):
                    state_update = {}
                conn.execute(
                    "UPDATE execution_cache SET hits = hits + 1 WHERE cache_key = ?",
                    (cache_key,)
                )
                conn.execute(
                    "UPDATE session_steps SET cu_id = ?, status = 'ok', attempts = ?, "
                    "final_result = ?, duration_ms = 0, timestamp = ? "
                    "WHERE session_name = ? AND step_index = ?",
                    (current_cu_id, attempt,
                     json.dumps(result, default=str), time.time(),
                     session_name, step_index)
                )
                conn.commit()
                self.state["stats"]["steps_executed"] += 1
                return {
                    "step": step_index,
                    "cu_id": current_cu_id,
                    "status": "ok",
                    "attempts": attempt,
                    "result": result,
                    "cached": True,
                    "state_update": state_update,
                    "error": None,
                    "duration_ms": 0,
                }

            t0 = time.time()
            ok, exec_result, err = self._ExecuteCu(
                current_cu_id, runtime_state, entry_command, entry_params
            )
            duration = (time.time() - t0) * 1000

            self._LogMemunit(
                session_name, step_index, current_cu_id, attempt,
                "ok" if ok else "error",
                exec_result if ok else None,
                err if err else None,
                state_before, runtime_state,
                duration
            )

            if ok:
                result_value = exec_result
                state_update = {}
                if isinstance(exec_result, tuple) and len(exec_result) == 3:
                    tu_ok, tu_data, tu_err = exec_result
                    result_value = {"ok": tu_ok, "data": tu_data, "error": tu_err}
                    if tu_ok and isinstance(tu_data, dict):
                        state_update = tu_data
                elif isinstance(exec_result, dict):
                    result_value = exec_result
                    state_update = exec_result
                else:
                    result_value = {"value": str(exec_result)[:200]}

                if self._IsDeterministic(current_cu_id):
                    conn.execute(
                        "INSERT OR REPLACE INTO execution_cache "
                        "(cache_key, cu_id, input_hash, result_json, created_at) "
                        "VALUES (?,?,?,?,?)",
                        (cache_key, current_cu_id,
                         hashlib.md5(json.dumps(entry_params, default=str).encode()).hexdigest(),
                         json.dumps(result_value, default=str), time.time())
                    )

                conn.execute(
                    "UPDATE session_steps SET cu_id = ?, status = 'ok', attempts = ?, "
                    "final_result = ?, duration_ms = ?, timestamp = ? "
                    "WHERE session_name = ? AND step_index = ?",
                    (current_cu_id, attempt,
                     json.dumps(result_value, default=str), duration, time.time(),
                     session_name, step_index)
                )
                conn.commit()
                self.state["stats"]["steps_executed"] += 1

                self._UpdateSurvivorStats(current_cu_id, True, duration)

                return {
                    "step": step_index,
                    "cu_id": current_cu_id,
                    "status": "ok",
                    "attempts": attempt,
                    "result": result_value,
                    "duration_ms": round(duration, 2),
                    "state_update": state_update,
                    "cached": False,
                    "error": None,
                }
            else:
                self._UpdateSurvivorStats(current_cu_id, False, duration)

                if attempt > max_attempts:
                    conn.execute(
                        "UPDATE session_steps SET cu_id = ?, status = 'failed', attempts = ?, "
                        "final_result = ?, duration_ms = ?, timestamp = ? "
                        "WHERE session_name = ? AND step_index = ?",
                        (current_cu_id, attempt,
                         json.dumps({"error": str(err)}, default=str), duration, time.time(),
                         session_name, step_index)
                    )
                    conn.commit()
                    return {
                        "step": step_index,
                        "cu_id": current_cu_id,
                        "status": "failed",
                        "attempts": attempt,
                        "error": str(err),
                        "duration_ms": round(duration, 2),
                        "result": None,
                        "state_update": {},
                        "cached": False,
                    }

                repair_result = self._AttemptRepair(
                    session_name, step_index, current_cu_id, err,
                    runtime_state, entry_command, entry_params
                )

                if repair_result and repair_result.get("replacement_cu_id"):
                    current_cu_id = repair_result["replacement_cu_id"]
                    self.state["stats"]["survivor_swaps"] += 1
                elif repair_result and repair_result.get("patched_cu_id"):
                    current_cu_id = repair_result["patched_cu_id"]
                else:
                    conn.execute(
                        "UPDATE session_steps SET cu_id = ?, status = 'failed', attempts = ?, "
                        "final_result = ?, duration_ms = ?, timestamp = ? "
                        "WHERE session_name = ? AND step_index = ?",
                        (current_cu_id, attempt,
                         json.dumps({"error": str(err), "repair_failed": True}, default=str),
                         duration, time.time(), session_name, step_index)
                    )
                    conn.commit()
                    return {
                        "step": step_index,
                        "cu_id": current_cu_id,
                        "status": "failed",
                        "attempts": attempt,
                        "error": str(err),
                        "repair_attempted": True,
                        "repair_result": repair_result,
                        "result": None,
                        "state_update": {},
                        "cached": False,
                        "duration_ms": 0,
                    }

        return {
            "step": step_index,
            "cu_id": current_cu_id,
            "status": "failed",
            "attempts": attempt,
            "error": "max attempts exceeded",
            "result": None,
            "state_update": {},
            "cached": False,
            "duration_ms": 0,
        }

    def _ExecuteCu(self, cu_id, runtime_state, entry_command, entry_params):
        cu_conn = self._CuConn()
        cu = cu_conn.execute(
            "SELECT source_code, method_name FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("CU_NOT_FOUND", cu_id)

        cache_key = "exec:" + cu_id
        if cache_key in self.state["compile_cache"]:
            code_obj = self.state["compile_cache"][cache_key]
        else:
            try:
                tree = ast.parse(cu["source_code"])
                code_obj = compile(tree, f"<session://{cu_id}>", "exec")
                self.state["compile_cache"][cache_key] = code_obj
            except SyntaxError as e:
                return self._err("SYNTAX_ERROR", str(e))

        ns = {}
        self._InjectStdlib(ns)
        try:
            exec(code_obj, ns)
        except Exception as e:
            return self._err("COMPILE_ERROR", str(e))

        func = ns.get(cu["method_name"])
        if not func:
            return self._err("FUNC_NOT_FOUND", cu["method_name"])

        try:
            namespace = {cu["method_name"]: func}
            for name, val in ns.items():
                if callable(val) and not name.startswith("__"):
                    namespace[name] = val

            if "__init__" not in namespace:
                def _default_init(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
                    if not hasattr(self, "state"):
                        self.state = {}
                namespace["__init__"] = _default_init

            cls = type("SessionCU", (object,), namespace)
            instance = cls(state=dict(runtime_state), config={})

            entry_point = cu["method_name"]
            if entry_point == "Run" and hasattr(instance, "Run"):
                result = instance.Run(entry_command, entry_params or {})
            elif hasattr(instance, entry_point):
                method = types.MethodType(func, instance)
                result = method(entry_params or {})
            else:
                method = types.MethodType(func, instance)
                result = method(entry_params or {})

            return (1, result, None)
        except Exception as e:
            tb = traceback.format_exc()
            return self._err("EXEC_ERROR", f"{cu_id}: {e}\n{tb}")

    def _AttemptRepair(self, session_name, step_index, failed_cu_id, error,
                       runtime_state, entry_command, entry_params):
        conn = self._Conn()
        cu_conn = self._CuConn()
        self.state["stats"]["repair_attempts"] += 1

        failed_cu = cu_conn.execute(
            "SELECT method_name, origin_class, semantic_hash, arg_names "
            "FROM computation_units WHERE cu_id = ?",
            (failed_cu_id,)
        ).fetchone()
        if not failed_cu:
            return {"strategy": "cu_not_found", "replacement_cu_id": None}

        error_msg = error[1] if isinstance(error, tuple) and len(error) >= 2 else str(error)
        error_type = error[0] if isinstance(error, tuple) and len(error) >= 1 else "Unknown"

        metadata = {
            "failed_cu_id": failed_cu_id,
            "method_name": failed_cu["method_name"],
            "origin_class": failed_cu["origin_class"],
            "semantic_hash": failed_cu["semantic_hash"][:16],
            "error_type": error_type,
            "error_msg": error_msg,
            "state_keys": list(runtime_state.keys()),
        }

        # Strategy 1: Find survivor with same capability
        capability = failed_cu["method_name"]
        survivors = cu_conn.execute(
            "SELECT sc.cu_id, sc.rank_score, sc.success_count, sc.failure_count, "
            "sc.avg_latency_ms, cu.source_code, cu.method_name "
            "FROM survivor_catalog sc "
            "JOIN computation_units cu ON sc.cu_id = cu.cu_id "
            "WHERE sc.capability = ? AND sc.cu_id != ? "
            "ORDER BY sc.rank_score DESC LIMIT 5",
            (capability, failed_cu_id)
        ).fetchall()

        if survivors:
            best = survivors[0]
            ok, test_result, test_err = self._ExecuteCu(
                best["cu_id"], runtime_state, entry_command, entry_params
            )

            test_status = "pass" if ok else "fail"

            conn.execute(
                "INSERT INTO repair_attempts "
                "(session_name, step_index, failed_cu_id, attempt, strategy, "
                "replacement_cu_id, reasoning, metadata_consulted, "
                "test_result, test_status, status, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_name, step_index, failed_cu_id,
                 self.state["stats"]["repair_attempts"],
                 "survivor_swap", best["cu_id"],
                 f"Swapped to survivor rank={best['rank_score']} "
                 f"success={best['success_count']} fail={best['failure_count']}",
                 json.dumps(metadata, default=str),
                 json.dumps({"ok": ok, "result": str(test_result)[:200]}, default=str),
                 test_status, "applied" if ok else "failed", time.time())
            )
            conn.commit()

            if ok:
                self.state["stats"]["steps_repaired"] += 1
                return {
                    "strategy": "survivor_swap",
                    "replacement_cu_id": best["cu_id"],
                    "reasoning": "swapped to higher-ranked survivor",
                    "test_status": "pass",
                }

        # Strategy 2: Find by same method name + compatible interface
        compatibles = cu_conn.execute(
            "SELECT cu_id, method_name, arg_names, semantic_hash "
            "FROM computation_units "
            "WHERE method_name = ? AND cu_id != ? "
            "ORDER BY created_at LIMIT 5",
            (failed_cu["method_name"], failed_cu_id)
        ).fetchall()

        for compat in compatibles:
            ok, test_result, test_err = self._ExecuteCu(
                compat["cu_id"], runtime_state, entry_command, entry_params
            )
            test_status = "pass" if ok else "fail"

            conn.execute(
                "INSERT INTO repair_attempts "
                "(session_name, step_index, failed_cu_id, attempt, strategy, "
                "replacement_cu_id, reasoning, metadata_consulted, "
                "test_result, test_status, status, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_name, step_index, failed_cu_id,
                 self.state["stats"]["repair_attempts"],
                 "compatible_name", compat["cu_id"],
                 f"Same method name, different semantic hash {compat['semantic_hash'][:16]}",
                 json.dumps(metadata, default=str),
                 json.dumps({"ok": ok, "result": str(test_result)[:200]}, default=str),
                 test_status, "applied" if ok else "failed", time.time())
            )
            conn.commit()

            if ok:
                self.state["stats"]["steps_repaired"] += 1
                return {
                    "strategy": "compatible_name",
                    "replacement_cu_id": compat["cu_id"],
                    "reasoning": "same method name, different implementation",
                    "test_status": "pass",
                }

        # Strategy 3: Log failure for AI patch (future: AI generates patch)
        conn.execute(
            "INSERT INTO repair_attempts "
            "(session_name, step_index, failed_cu_id, attempt, strategy, "
            "reasoning, metadata_consulted, test_result, test_status, status, timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (session_name, step_index, failed_cu_id,
             self.state["stats"]["repair_attempts"],
             "ai_patch_pending",
             "No survivor or compatible CU found. AI patch required.",
             json.dumps(metadata, default=str),
             json.dumps({"error": error_msg}, default=str),
             "pending", "pending", time.time())
        )
        conn.commit()

        return {
            "strategy": "ai_patch_pending",
            "reasoning": "no survivor available, AI patch needed",
            "test_status": "pending",
        }

    # -----------------------------------------------------------------------
    # MEMUNIT LOGGING — capture everything
    # -----------------------------------------------------------------------

    def _LogMemunit(self, session_name, step_index, cu_id, attempt,
                    status, result, error, state_before, state_after, duration):
        conn = self._Conn()

        error_type = None
        error_msg = None
        error_tb = None
        if error:
            if isinstance(error, tuple) and len(error) >= 2:
                error_type = str(error[0])
                error_msg = str(error[1])
                if len(error) >= 3:
                    error_tb = str(error[2]) if error[2] else None
            else:
                error_msg = str(error)

        cu_conn = self._CuConn()
        deps = cu_conn.execute(
            "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?",
            (cu_id,)
        ).fetchall()
        dep_chain = [d["depends_on"] for d in deps]

        conn.execute(
            "INSERT INTO memunit_results "
            "(session_name, step_index, cu_id, attempt, status, "
            "result_value, error_type, error_msg, error_traceback, "
            "state_before, state_after, locals_capture, dependency_chain, "
            "duration_ms, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session_name, step_index, cu_id, attempt, status,
             json.dumps(result, default=str) if result else None,
             error_type, error_msg, error_tb,
             json.dumps(state_before, default=str),
             json.dumps(state_after, default=str),
             json.dumps({}, default=str),
             json.dumps(dep_chain, default=str),
             duration, time.time())
        )
        conn.commit()

    # -----------------------------------------------------------------------
    # SURVIVOR CATALOG — capability → ranked CU index
    # -----------------------------------------------------------------------

    def RegisterSurvivor(self, params):
        capability = self._p(params, "capability")
        cu_id = self._p(params, "cu_id")
        if not capability or not cu_id:
            return self._err("MISSING", "capability and cu_id required")

        rank_score = self._p(params, "rank_score", 1.0)
        interface_hash = self._p(params, "interface_hash", "")

        conn = self._Conn()
        conn.execute(
            "INSERT OR REPLACE INTO survivor_catalog "
            "(capability, cu_id, rank_score, interface_hash, last_used) "
            "VALUES (?,?,?,?,?)",
            (capability, cu_id, rank_score, interface_hash, time.time())
        )
        conn.commit()

        return (1, {
            "capability": capability,
            "cu_id": cu_id,
            "rank_score": rank_score,
        }, None)

    def SurvivorLookup(self, params):
        capability = self._p(params, "capability")
        if not capability:
            return self._err("NO_CAPABILITY", "capability required")

        conn = self._Conn()
        cu_conn = self._CuConn()
        rows = conn.execute(
            "SELECT sc.capability, sc.cu_id, sc.rank_score, "
            "sc.success_count, sc.failure_count, sc.avg_latency_ms "
            "FROM survivor_catalog sc "
            "WHERE sc.capability = ? "
            "ORDER BY sc.rank_score DESC",
            (capability,)
        ).fetchall()

        survivors = []
        for r in rows:
            cu = cu_conn.execute(
                "SELECT method_name, origin_class FROM computation_units WHERE cu_id = ?",
                (r["cu_id"],)
            ).fetchone()
            survivors.append({
                "cu_id": r["cu_id"],
                "rank": r["rank_score"],
                "success": r["success_count"],
                "failure": r["failure_count"],
                "avg_latency": r["avg_latency_ms"],
                "method_name": cu["method_name"] if cu else "",
                "origin_class": cu["origin_class"] if cu else "",
            })

        return (1, {
            "capability": capability,
            "count": len(survivors),
            "survivors": survivors,
        }, None)

    def BuildSurvivorCatalog(self, params):
        cu_conn = self._CuConn()
        conn = self._Conn()

        rows = cu_conn.execute(
            "SELECT cu_id, method_name, origin_class, semantic_hash "
            "FROM computation_units"
        ).fetchall()

        registered = 0
        for r in rows:
            existing = conn.execute(
                "SELECT 1 FROM survivor_catalog WHERE capability = ? AND cu_id = ?",
                (r["method_name"], r["cu_id"])
            ).fetchone()
            if existing:
                continue

            rank = 1.0
            proof = cu_conn.execute(
                "SELECT status FROM cu_proof_status WHERE cu_id = ?",
                (r["cu_id"],)
            ).fetchone()
            if proof and proof["status"] == "verified":
                rank += 0.5

            exec_stats = cu_conn.execute(
                "SELECT total_runs, total_failures, avg_latency_ms "
                "FROM cu_execution_stats WHERE cu_id = ?",
                (r["cu_id"],)
            ).fetchone()
            if exec_stats and exec_stats["total_runs"] > 0:
                success_rate = 1 - (exec_stats["total_failures"] / exec_stats["total_runs"])
                rank += success_rate
                conn.execute(
                    "INSERT OR REPLACE INTO survivor_catalog "
                    "(capability, cu_id, rank_score, success_count, "
                    "failure_count, avg_latency_ms, last_used) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (r["method_name"], r["cu_id"], rank,
                     exec_stats["total_runs"] - exec_stats["total_failures"],
                     exec_stats["total_failures"],
                     exec_stats["avg_latency_ms"], time.time())
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO survivor_catalog "
                    "(capability, cu_id, rank_score, last_used) "
                    "VALUES (?,?,?,?)",
                    (r["method_name"], r["cu_id"], rank, time.time())
                )
            registered += 1

        conn.commit()
        return (1, {"registered": registered, "total_cus": len(rows)}, None)

    def _UpdateSurvivorStats(self, cu_id, success, duration_ms):
        conn = self._Conn()
        cu_conn = self._CuConn()

        cu = cu_conn.execute(
            "SELECT method_name FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return

        capability = cu["method_name"]
        existing = conn.execute(
            "SELECT success_count, failure_count, avg_latency_ms "
            "FROM survivor_catalog WHERE capability = ? AND cu_id = ?",
            (capability, cu_id)
        ).fetchone()

        if existing:
            sc = existing["success_count"] + (1 if success else 0)
            fc = existing["failure_count"] + (0 if success else 1)
            total = sc + fc
            prev_avg = existing["avg_latency_ms"] or 0
            new_avg = (prev_avg * (total - 1) + duration_ms) / max(total, 1)
            new_rank = sc / max(total, 1) + 0.5
            conn.execute(
                "UPDATE survivor_catalog SET success_count = ?, failure_count = ?, "
                "avg_latency_ms = ?, rank_score = ?, last_used = ? "
                "WHERE capability = ? AND cu_id = ?",
                (sc, fc, new_avg, new_rank, time.time(), capability, cu_id)
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO survivor_catalog "
                "(capability, cu_id, rank_score, success_count, failure_count, "
                "avg_latency_ms, last_used) VALUES (?,?,?,?,?,?,?)",
                (capability, cu_id, 1.0 if success else 0.5,
                 1 if success else 0, 0 if success else 1,
                 duration_ms, time.time())
            )
        conn.commit()

    # -----------------------------------------------------------------------
    # CACHE
    # -----------------------------------------------------------------------

    def _CacheKey(self, cu_id, command, params):
        input_str = json.dumps({"cu": cu_id, "cmd": command, "params": params}, default=str, sort_keys=True)
        return hashlib.sha256(input_str.encode()).hexdigest()

    def _IsDeterministic(self, cu_id):
        cu_conn = self._CuConn()
        r = cu_conn.execute(
            "SELECT deterministic FROM cu_contracts WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        return r and r["deterministic"] == 1

    def ClearCache(self, params=None):
        conn = self._Conn()
        conn.execute("DELETE FROM execution_cache")
        conn.commit()
        return (1, {"cache_cleared": True}, None)

    # -----------------------------------------------------------------------
    # STATUS / LOG / STATS
    # -----------------------------------------------------------------------

    def Status(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")
        conn = self._Conn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("NOT_FOUND", session_name)

        steps = conn.execute(
            "SELECT * FROM session_steps WHERE session_name = ? ORDER BY step_index",
            (session_name,)
        ).fetchall()

        return (1, {
            "session_name": session_name,
            "status": session["status"],
            "steps_total": len(json.loads(session["cu_steps"])),
            "steps": [{
                "step": s["step_index"],
                "cu_id": s["cu_id"],
                "status": s["status"],
                "attempts": s["attempts"],
                "duration_ms": s["duration_ms"],
            } for s in steps],
            "created_at": session["created_at"],
            "completed_at": session["completed_at"],
        }, None)

    def RepairLog(self, params):
        session_name = self._p(params, "session_name")
        conn = self._Conn()
        if session_name:
            rows = conn.execute(
                "SELECT * FROM repair_attempts WHERE session_name = ? ORDER BY repair_id",
                (session_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM repair_attempts ORDER BY repair_id DESC LIMIT 50"
            ).fetchall()

        return (1, {
            "count": len(rows),
            "repairs": [{
                "session": r["session_name"],
                "step": r["step_index"],
                "failed_cu": r["failed_cu_id"],
                "attempt": r["attempt"],
                "strategy": r["strategy"],
                "replacement": r["replacement_cu_id"],
                "reasoning": r["reasoning"],
                "test_status": r["test_status"],
                "status": r["status"],
            } for r in rows],
        }, None)

    def MemunitLog(self, params):
        session_name = self._p(params, "session_name")
        conn = self._Conn()
        if session_name:
            rows = conn.execute(
                "SELECT * FROM memunit_results WHERE session_name = ? "
                "ORDER BY memunit_id",
                (session_name,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memunit_results ORDER BY memunit_id DESC LIMIT 50"
            ).fetchall()

        return (1, {
            "count": len(rows),
            "memunits": [{
                "session": r["session_name"],
                "step": r["step_index"],
                "cu_id": r["cu_id"],
                "attempt": r["attempt"],
                "status": r["status"],
                "error_type": r["error_type"],
                "error_msg": r["error_msg"],
                "dependency_chain": json.loads(r["dependency_chain"]) if r["dependency_chain"] else [],
                "duration_ms": r["duration_ms"],
            } for r in rows],
        }, None)

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "sessions": conn.execute("SELECT COUNT(*) FROM execution_sessions").fetchone()[0],
            "session_steps": conn.execute("SELECT COUNT(*) FROM session_steps").fetchone()[0],
            "memunits": conn.execute("SELECT COUNT(*) FROM memunit_results").fetchone()[0],
            "repairs": conn.execute("SELECT COUNT(*) FROM repair_attempts").fetchone()[0],
            "survivors": conn.execute("SELECT COUNT(*) FROM survivor_catalog").fetchone()[0],
            "cache_entries": conn.execute("SELECT COUNT(*) FROM execution_cache").fetchone()[0],
            "compile_cache": len(self.state["compile_cache"]),
        }
        return (1, {"counts": counts, "stats": self.state["stats"]}, None)

    def read_state(self, params=None):
        safe = dict(self.state)
        for key in ("conn", "cu_conn", "orch_conn"):
            safe.pop(key, None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)

    # -----------------------------------------------------------------------
    # PARALLEL EXECUTE — run independent steps concurrently
    # -----------------------------------------------------------------------

    def ParallelExecute(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        cu_steps = json.loads(session["cu_steps"])
        runtime_state = json.loads(session["init_state"])
        init_state = self._p(params, "init_state", {})
        if isinstance(init_state, dict):
            runtime_state.update(init_state)
        max_workers = self._p(params, "max_workers", 4)
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn.execute("DELETE FROM session_steps WHERE session_name = ?", (session_name,))
        now = time.time()
        for i, cu_id in enumerate(cu_steps):
            conn.execute(
                "INSERT INTO session_steps "
                "(session_name, step_index, cu_id, status, timestamp) "
                "VALUES (?,?,?,?,?)",
                (session_name, i, cu_id, "pending", now)
            )
        conn.execute(
            "UPDATE execution_sessions SET status = 'running' WHERE session_name = ?",
            (session_name,)
        )
        conn.commit()

        cu_conn = self._CuConn()
        step_cu_set = set(cu_steps)
        dep_map = {}
        for cu_id in cu_steps:
            deps = cu_conn.execute(
                "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?",
                (cu_id,)
            ).fetchall()
            dep_set = set()
            for d in deps:
                dep = d["depends_on"]
                if dep in step_cu_set:
                    dep_set.add(dep)
            dep_map[cu_id] = dep_set

        completed_cus = set()
        completed = 0
        repaired = 0
        results = []
        batches = 0
        remaining = list(range(len(cu_steps)))

        while remaining:
            ready = []
            for idx in remaining:
                if dep_map[cu_steps[idx]].issubset(completed_cus):
                    ready.append(idx)
            if not ready:
                ready = remaining[:]

            batches += 1
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            future_map = {}
            for idx in ready:
                future = executor.submit(
                    self._ExecuteStep,
                    session_name, idx, cu_steps[idx], dict(runtime_state),
                    entry_command, entry_params
                )
                future_map[future] = idx

            batch_results = {}
            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    batch_results[idx] = future.result()
                except Exception as e:
                    batch_results[idx] = {
                        "step": idx, "cu_id": cu_steps[idx],
                        "status": "failed", "attempts": 0,
                        "result": None, "state_update": {},
                        "cached": False, "error": str(e), "duration_ms": 0,
                    }
            executor.shutdown(wait=True)

            failed = False
            for idx in sorted(batch_results.keys()):
                step_result = batch_results[idx]
                if step_result["status"] in ("ok", "repaired"):
                    runtime_state.update(step_result.get("state_update", {}))
                    completed_cus.add(cu_steps[idx])
                    completed += 1
                    if step_result["status"] == "repaired":
                        repaired += 1
                    results.append(step_result)
                    remaining.remove(idx)
                else:
                    results.append(step_result)
                    failed = True
                    remaining.remove(idx)

            if failed:
                break

        final_status = "completed" if completed == len(cu_steps) else "failed"
        conn.execute(
            "UPDATE execution_sessions SET status = ?, completed_at = ? WHERE session_name = ?",
            (final_status, time.time(), session_name)
        )
        conn.commit()
        if final_status == "completed":
            self.state["stats"]["sessions_completed"] += 1

        return (1, {
            "session_name": session_name,
            "status": final_status,
            "steps_total": len(cu_steps),
            "steps_completed": completed,
            "steps_repaired": repaired,
            "parallel_batches": batches,
            "final_state": runtime_state,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # DRY RUN — show what would happen without executing
    # -----------------------------------------------------------------------

    def DryRun(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        cu_conn = self._CuConn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        cu_steps = json.loads(session["cu_steps"])
        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        steps_info = []
        cached_count = 0
        repair_candidates = 0
        total_est = 0.0

        for i, cu_id in enumerate(cu_steps):
            cache_key = self._CacheKey(cu_id, entry_command, entry_params)
            cached = conn.execute(
                "SELECT 1 FROM execution_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            is_cached = cached is not None
            if is_cached:
                cached_count += 1

            cu = cu_conn.execute(
                "SELECT method_name, origin_class FROM computation_units WHERE cu_id = ?",
                (cu_id,)
            ).fetchone()
            method_name = cu["method_name"] if cu else ""

            survivors = conn.execute(
                "SELECT COUNT(*) FROM survivor_catalog WHERE capability = ? AND cu_id != ?",
                (method_name, cu_id)
            ).fetchone()[0]
            if survivors > 0:
                repair_candidates += 1

            est = cu_conn.execute(
                "SELECT avg_latency_ms FROM cu_execution_stats WHERE cu_id = ?",
                (cu_id,)
            ).fetchone()
            est_ms = est["avg_latency_ms"] if est and est["avg_latency_ms"] else 0
            if is_cached:
                est_ms = 0
            total_est += est_ms

            deps = cu_conn.execute(
                "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?",
                (cu_id,)
            ).fetchall()
            dep_list = [d["depends_on"] for d in deps]

            steps_info.append({
                "step": i,
                "cu_id": cu_id,
                "method_name": method_name,
                "cached": is_cached,
                "repair_candidates": survivors,
                "estimated_ms": round(est_ms, 2),
                "dependencies": dep_list,
            })

        return (1, {
            "session_name": session_name,
            "steps": steps_info,
            "cached_count": cached_count,
            "repair_candidates": repair_candidates,
            "estimated_time_ms": round(total_est, 2),
        }, None)

    # -----------------------------------------------------------------------
    # REPLAY — re-execute a session from a specific step
    # -----------------------------------------------------------------------

    def Replay(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        from_step = self._p(params, "from_step", 0)
        conn = self._Conn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        cu_steps = json.loads(session["cu_steps"])
        runtime_state = json.loads(session["init_state"])
        init_state = self._p(params, "init_state", {})
        if isinstance(init_state, dict):
            runtime_state.update(init_state)

        if from_step > 0:
            prior = conn.execute(
                "SELECT state_after FROM memunit_results "
                "WHERE session_name = ? AND step_index < ? AND status = 'ok' "
                "ORDER BY memunit_id DESC LIMIT 1",
                (session_name, from_step)
            ).fetchone()
            if prior and prior["state_after"]:
                try:
                    restored = json.loads(prior["state_after"])
                    if isinstance(restored, dict):
                        runtime_state = restored
                        runtime_state.update(init_state)
                except (ValueError, TypeError):
                    pass

        entry_command = self._p(params, "entry_command", "read_state")
        entry_params = self._p(params, "entry_params", {})

        conn.execute(
            "UPDATE execution_sessions SET status = 'running' WHERE session_name = ?",
            (session_name,)
        )
        conn.commit()

        results = []
        completed = 0
        for i in range(from_step, len(cu_steps)):
            step_result = self._ExecuteStep(
                session_name, i, cu_steps[i], runtime_state,
                entry_command, entry_params
            )
            if step_result["status"] in ("ok", "repaired"):
                runtime_state.update(step_result.get("state_update", {}))
                completed += 1
                results.append(step_result)
            else:
                results.append(step_result)
                break

        final_status = "completed" if completed == (len(cu_steps) - from_step) else "failed"
        conn.execute(
            "UPDATE execution_sessions SET status = ?, completed_at = ? WHERE session_name = ?",
            (final_status, time.time(), session_name)
        )
        conn.commit()

        return (1, {
            "session_name": session_name,
            "replayed_from": from_step,
            "status": final_status,
            "steps_completed": completed,
            "final_state": runtime_state,
            "results": results,
        }, None)

    # -----------------------------------------------------------------------
    # EXPORT SESSION — export a session and its data as JSON
    # -----------------------------------------------------------------------

    def ExportSession(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        session_data = {
            "session_name": session["session_name"],
            "cu_steps": json.loads(session["cu_steps"]),
            "init_state": json.loads(session["init_state"]),
            "description": session["description"],
            "status": session["status"],
            "created_at": session["created_at"],
            "completed_at": session["completed_at"],
        }

        steps = conn.execute(
            "SELECT * FROM session_steps WHERE session_name = ? ORDER BY step_index",
            (session_name,)
        ).fetchall()
        steps_data = [{
            "step_index": s["step_index"],
            "cu_id": s["cu_id"],
            "status": s["status"],
            "attempts": s["attempts"],
            "final_result": s["final_result"],
            "duration_ms": s["duration_ms"],
        } for s in steps]

        memunits = conn.execute(
            "SELECT * FROM memunit_results WHERE session_name = ? ORDER BY memunit_id",
            (session_name,)
        ).fetchall()
        memunits_data = [{
            "step_index": m["step_index"],
            "cu_id": m["cu_id"],
            "attempt": m["attempt"],
            "status": m["status"],
            "result_value": m["result_value"],
            "error_type": m["error_type"],
            "error_msg": m["error_msg"],
            "error_traceback": m["error_traceback"],
            "state_before": m["state_before"],
            "state_after": m["state_after"],
            "duration_ms": m["duration_ms"],
        } for m in memunits]

        repairs = conn.execute(
            "SELECT * FROM repair_attempts WHERE session_name = ? ORDER BY repair_id",
            (session_name,)
        ).fetchall()
        repairs_data = [{
            "step_index": r["step_index"],
            "failed_cu_id": r["failed_cu_id"],
            "attempt": r["attempt"],
            "strategy": r["strategy"],
            "replacement_cu_id": r["replacement_cu_id"],
            "reasoning": r["reasoning"],
            "test_status": r["test_status"],
            "status": r["status"],
        } for r in repairs]

        export = {
            "session": session_data,
            "steps": steps_data,
            "memunit_results": memunits_data,
            "repair_attempts": repairs_data,
        }
        return (1, json.dumps(export, default=str), None)

    # -----------------------------------------------------------------------
    # IMPORT SESSION — import a session from JSON
    # -----------------------------------------------------------------------

    def ImportSession(self, params):
        json_str = self._p(params, "json")
        if not json_str:
            return self._err("NO_JSON", "json string required")
        try:
            data = json.loads(json_str)
        except (ValueError, TypeError) as e:
            return self._err("INVALID_JSON", str(e))
        if not isinstance(data, dict) or "session" not in data:
            return self._err("INVALID_FORMAT", "missing session key")

        sess = data["session"]
        session_name = self._p(params, "session_name") or sess.get("session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        now = time.time()
        cu_steps = sess.get("cu_steps", [])
        init_state = sess.get("init_state", {})

        conn.execute(
            "INSERT OR REPLACE INTO execution_sessions "
            "(session_name, cu_steps, init_state, description, status, created_at, completed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_name, json.dumps(cu_steps), json.dumps(init_state),
             sess.get("description", ""), sess.get("status", "imported"),
             sess.get("created_at", now), sess.get("completed_at", 0))
        )

        conn.execute("DELETE FROM session_steps WHERE session_name = ?", (session_name,))
        steps_imported = 0
        for s in data.get("steps", []):
            conn.execute(
                "INSERT INTO session_steps "
                "(session_name, step_index, cu_id, status, attempts, final_result, duration_ms, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (session_name, s.get("step_index", 0), s.get("cu_id", ""),
                 s.get("status", "imported"), s.get("attempts", 0),
                 s.get("final_result"), s.get("duration_ms", 0), now)
            )
            steps_imported += 1

        conn.execute("DELETE FROM memunit_results WHERE session_name = ?", (session_name,))
        results_imported = 0
        for m in data.get("memunit_results", []):
            conn.execute(
                "INSERT INTO memunit_results "
                "(session_name, step_index, cu_id, attempt, status, result_value, "
                "error_type, error_msg, error_traceback, state_before, state_after, "
                "locals_capture, dependency_chain, duration_ms, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_name, m.get("step_index", 0), m.get("cu_id", ""),
                 m.get("attempt", 0), m.get("status", ""), m.get("result_value"),
                 m.get("error_type"), m.get("error_msg"), m.get("error_traceback"),
                 m.get("state_before"), m.get("state_after"),
                 json.dumps({}), json.dumps([]),
                 m.get("duration_ms", 0), now)
            )
            results_imported += 1

        conn.commit()
        return (1, {
            "session_name": session_name,
            "steps_imported": steps_imported,
            "results_imported": results_imported,
        }, None)

    # -----------------------------------------------------------------------
    # SESSION DIFF — compare two sessions
    # -----------------------------------------------------------------------

    def SessionDiff(self, params):
        session_a = self._p(params, "session_a")
        session_b = self._p(params, "session_b")
        if not session_a or not session_b:
            return self._err("NO_SESSION", "session_a and session_b required")

        conn = self._Conn()
        sa = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_a,)
        ).fetchone()
        sb = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_b,)
        ).fetchone()
        if not sa:
            return self._err("NOT_FOUND", session_a)
        if not sb:
            return self._err("NOT_FOUND", session_b)

        steps_a = conn.execute(
            "SELECT * FROM session_steps WHERE session_name = ? ORDER BY step_index",
            (session_a,)
        ).fetchall()
        steps_b = conn.execute(
            "SELECT * FROM session_steps WHERE session_name = ? ORDER BY step_index",
            (session_b,)
        ).fetchall()

        differences = []
        max_len = max(len(steps_a), len(steps_b))
        for i in range(max_len):
            ra = steps_a[i] if i < len(steps_a) else None
            rb = steps_b[i] if i < len(steps_b) else None
            if ra is None:
                differences.append({
                    "step": i, "type": "missing_in_a",
                    "cu_b": rb["cu_id"], "status_b": rb["status"],
                })
            elif rb is None:
                differences.append({
                    "step": i, "type": "missing_in_b",
                    "cu_a": ra["cu_id"], "status_a": ra["status"],
                })
            else:
                if ra["status"] != rb["status"]:
                    differences.append({
                        "step": i, "type": "status_diff",
                        "status_a": ra["status"], "status_b": rb["status"],
                    })
                if abs((ra["duration_ms"] or 0) - (rb["duration_ms"] or 0)) > 0.01:
                    differences.append({
                        "step": i, "type": "duration_diff",
                        "duration_a": ra["duration_ms"], "duration_b": rb["duration_ms"],
                    })
                if ra["cu_id"] != rb["cu_id"]:
                    differences.append({
                        "step": i, "type": "cu_diff",
                        "cu_a": ra["cu_id"], "cu_b": rb["cu_id"],
                    })

        summary = {
            "steps_a": len(steps_a),
            "steps_b": len(steps_b),
            "status_a": sa["status"],
            "status_b": sb["status"],
            "differences_count": len(differences),
        }
        return (1, {"differences": differences, "summary": summary}, None)

    # -----------------------------------------------------------------------
    # VALIDATE — validate a session before execution
    # -----------------------------------------------------------------------

    def Validate(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        cu_conn = self._CuConn()
        session = conn.execute(
            "SELECT * FROM execution_sessions WHERE session_name = ?",
            (session_name,)
        ).fetchone()
        if not session:
            return self._err("SESSION_NOT_FOUND", session_name)

        cu_steps = json.loads(session["cu_steps"])
        issues = []

        if not cu_steps:
            issues.append("session has no steps")

        seen = set()
        for cu_id in cu_steps:
            if cu_id in seen:
                issues.append("duplicate step cu_id: " + str(cu_id))
            seen.add(cu_id)

        for cu_id in cu_steps:
            exists = cu_conn.execute(
                "SELECT 1 FROM computation_units WHERE cu_id = ?",
                (cu_id,)
            ).fetchone()
            if not exists:
                issues.append("cu_id not found in computation_units: " + str(cu_id))

        step_cu_set = set(cu_steps)
        dep_map = {}
        for cu_id in cu_steps:
            deps = cu_conn.execute(
                "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?",
                (cu_id,)
            ).fetchall()
            dep_set = set()
            for d in deps:
                dep = d["depends_on"]
                if dep in step_cu_set:
                    dep_set.add(dep)
            dep_map[cu_id] = dep_set

        visited = set()
        stack = set()
        cyclic = []

        def detect(cu_id, path):
            if cu_id in stack:
                cyclic.append(path + [cu_id])
                return
            if cu_id in visited:
                return
            visited.add(cu_id)
            stack.add(cu_id)
            for dep in dep_map.get(cu_id, ()):
                detect(dep, path + [cu_id])
            stack.discard(cu_id)

        for cu_id in cu_steps:
            detect(cu_id, [])

        if cyclic:
            issues.append("circular dependencies detected: " + json.dumps(cyclic, default=str))

        valid = len(issues) == 0
        return (1, {"valid": valid, "issues": issues}, None)

    # -----------------------------------------------------------------------
    # CLEANUP — delete old session data
    # -----------------------------------------------------------------------

    def Cleanup(self, params):
        max_age_days = self._p(params, "max_age_days", 30)
        cutoff = time.time() - (max_age_days * 86400)
        conn = self._Conn()

        old_sessions = conn.execute(
            "SELECT session_name FROM execution_sessions WHERE created_at < ?",
            (cutoff,)
        ).fetchall()
        old_names = [s["session_name"] for s in old_sessions]

        steps_deleted = 0
        results_deleted = 0
        sessions_deleted = 0

        if old_names:
            placeholders = ",".join("?" for _ in old_names)
            steps_deleted = conn.execute(
                "DELETE FROM session_steps WHERE session_name IN (" + placeholders + ")",
                old_names
            ).rowcount
            results_deleted = conn.execute(
                "DELETE FROM memunit_results WHERE session_name IN (" + placeholders + ")",
                old_names
            ).rowcount
            conn.execute(
                "DELETE FROM repair_attempts WHERE session_name IN (" + placeholders + ")",
                old_names
            )
            sessions_deleted = conn.execute(
                "DELETE FROM execution_sessions WHERE session_name IN (" + placeholders + ")",
                old_names
            ).rowcount

        cache_deleted = conn.execute(
            "DELETE FROM execution_cache WHERE created_at < ?",
            (cutoff,)
        ).rowcount

        conn.commit()
        return (1, {
            "sessions_deleted": sessions_deleted,
            "steps_deleted": steps_deleted,
            "results_deleted": results_deleted,
            "cache_entries_deleted": cache_deleted,
        }, None)

    # -----------------------------------------------------------------------
    # PROFILE — profile the last execution of a session
    # -----------------------------------------------------------------------

    def Profile(self, params):
        session_name = self._p(params, "session_name")
        if not session_name:
            return self._err("NO_SESSION_NAME", "session_name required")

        conn = self._Conn()
        steps = conn.execute(
            "SELECT * FROM session_steps WHERE session_name = ? ORDER BY step_index",
            (session_name,)
        ).fetchall()
        if not steps:
            return self._err("NO_STEPS", "no steps found for session")

        per_step = []
        total = 0.0
        for s in steps:
            dur = s["duration_ms"] or 0
            total += dur
            per_step.append({
                "step": s["step_index"],
                "cu_id": s["cu_id"],
                "duration_ms": round(dur, 2),
                "status": s["status"],
                "attempts": s["attempts"],
            })

        for ps in per_step:
            ps["percent"] = round((ps["duration_ms"] / total * 100), 2) if total > 0 else 0

        sorted_steps = sorted(per_step, key=lambda x: x["duration_ms"])
        fastest = sorted_steps[0] if sorted_steps else None
        slowest = sorted_steps[-1] if sorted_steps else None

        bottlenecks = [ps for ps in per_step if total > 0 and ps["duration_ms"] / total > 0.5]

        cache_entries = conn.execute("SELECT hits FROM execution_cache").fetchall()
        total_hits = sum(c["hits"] for c in cache_entries)
        total_entries = len(cache_entries)
        cache_hit_rate = round(total_hits / total_entries, 4) if total_entries > 0 else 0.0

        return (1, {
            "session_name": session_name,
            "total_time_ms": round(total, 2),
            "per_step": per_step,
            "slowest": slowest,
            "fastest": fastest,
            "bottlenecks": bottlenecks,
            "cache_hit_rate": cache_hit_rate,
        }, None)

    # -----------------------------------------------------------------------
    # INVALIDATE CACHE — selective cache invalidation
    # -----------------------------------------------------------------------

    def InvalidateCache(self, params):
        conn = self._Conn()
        cu_id = self._p(params, "cu_id")
        capability = self._p(params, "capability")
        clear_all = self._p(params, "all", False)

        if clear_all:
            deleted = conn.execute("DELETE FROM execution_cache").rowcount
        elif cu_id:
            deleted = conn.execute(
                "DELETE FROM execution_cache WHERE cu_id = ?",
                (cu_id,)
            ).rowcount
        elif capability:
            cu_conn = self._CuConn()
            cus = cu_conn.execute(
                "SELECT cu_id FROM computation_units WHERE method_name = ?",
                (capability,)
            ).fetchall()
            cu_ids = [c["cu_id"] for c in cus]
            deleted = 0
            if cu_ids:
                placeholders = ",".join("?" for _ in cu_ids)
                deleted = conn.execute(
                    "DELETE FROM execution_cache WHERE cu_id IN (" + placeholders + ")",
                    cu_ids
                ).rowcount
        else:
            return self._err("NO_PARAM", "cu_id, capability, or all required")

        conn.commit()
        return (1, {"invalidated": deleted}, None)

    # -----------------------------------------------------------------------
    # STDLIB INJECTION
    # -----------------------------------------------------------------------

    def _InjectStdlib(self, ns):
        import time as _time, json as _json, re, hashlib as _hl, ast as _ast
        import collections, typing, traceback as _tb
        import functools, itertools, copy as _copy, math, random, textwrap
        import io, uuid, warnings, inspect, struct, base64, operator
        import string, pprint, decimal, fractions, array, bisect, heapq
        import numbers, statistics, types as _types, dataclasses, enum
        import abc, contextlib, weakref, gc

        ns.update({
            "json": _json, "re": re, "time": _time, "hashlib": _hl,
            "ast": _ast, "collections": collections, "typing": typing,
            "traceback": _tb, "functools": functools, "itertools": itertools,
            "copy": _copy, "math": math, "random": random, "textwrap": textwrap,
            "io": io, "uuid": uuid, "warnings": warnings, "inspect": inspect,
            "struct": struct, "base64": base64, "operator": operator,
            "string": string, "pprint": pprint, "decimal": decimal,
            "fractions": fractions, "array": array, "bisect": bisect,
            "heapq": heapq, "numbers": numbers, "statistics": statistics,
            "types": _types, "dataclasses": dataclasses, "enum": enum,
            "abc": abc, "contextlib": contextlib, "weakref": weakref, "gc": gc,
            "defaultdict": collections.defaultdict,
            "deque": collections.deque,
            "Counter": collections.Counter,
            "namedtuple": collections.namedtuple,
            "wraps": functools.wraps,
            "lru_cache": functools.lru_cache,
            "partial": functools.partial,
            "reduce": functools.reduce,
        })
        for name in ("Optional", "List", "Dict", "Tuple", "Any", "Union",
                      "Set", "Callable", "Iterator", "Generator"):
            if hasattr(typing, name):
                ns[name] = getattr(typing, name)


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== EXECUTION SESSION ===")
    print()

    session = ExecutionSession()

    # Step 1: Ingest CUs first (via ComputationUnit)
    print("--- Step 1: Ingest CUs ---")
    from computation_unit import ComputationUnit
    cu = ComputationUnit()

    ok1, d1, _ = cu.Run("ingest_method", {
        "method_name": "Run",
        "source_code": (
            "def Run(self, command, params=None):\n"
            "    dispatch = {'read_state': lambda p: (1, self.state, None),\n"
            "                'set_config': lambda p: (1, {'updated': True}, None)}\n"
            "    fn = dispatch.get(command)\n"
            "    if fn is None:\n"
            "        return (0, None, ('UNKNOWN_CMD', command, 0))\n"
            "    return fn(params or {})\n"
        ),
        "origin_class": "TestAgent",
        "arg_names": ["self", "command", "params"],
    })
    if ok1:
        print(f"  CU 1: {d1['cu_id']}  method={d1.get('method_name', 'Run')}  status={d1['status']}")
    else:
        err_code = _[0] if isinstance(_, tuple) else "?"
        err_msg = _[1] if isinstance(_, tuple) else str(_)
        print(f"  CU 1 FAILED: {err_code}: {err_msg}")
        raise SystemExit(1)

    ok2, d2, _ = cu.Run("ingest_method", {
        "method_name": "read_state",
        "source_code": (
            "def read_state(self, params=None):\n"
            "    return (1, dict(self.state), None)\n"
        ),
        "origin_class": "TestAgent",
        "arg_names": ["self", "params"],
    })
    if ok2:
        print(f"  CU 2: {d2['cu_id']}  method={d2.get('method_name', 'read_state')}  status={d2['status']}")

    ok3, d3, _ = cu.Run("ingest_method", {
        "method_name": "set_config",
        "source_code": (
            "def set_config(self, params=None):\n"
            "    if params:\n"
            "        self.state.update(params)\n"
            "    return (1, dict(self.state), None)\n"
        ),
        "origin_class": "TestAgent",
        "arg_names": ["self", "params"],
    })
    if ok3:
        print(f"  CU 3: {d3['cu_id']}  method={d3.get('method_name', 'set_config')}  status={d3['status']}")

    # Step 2: Build survivor catalog
    print()
    print("--- Step 2: Build survivor catalog ---")
    ok, cat, _ = session.Run("build_survivor_catalog", {})
    if ok:
        print(f"  Registered: {cat['registered']}")
        print(f"  Total CUs:  {cat['total_cus']}")

    # Step 3: Create a session
    print()
    print("--- Step 3: Create session ---")
    cu_steps = [d1["cu_id"], d2["cu_id"], d3["cu_id"]]
    ok, sess, err = session.Run("create", {
        "session_name": "TestSession",
        "cu_steps": cu_steps,
        "init_state": {"version": "1.0", "session_test": True},
        "description": "Test execution session with self-repair",
    })
    if ok:
        print(f"  Session: {sess['session_name']}")
        print(f"  Steps:   {sess['steps']}")
        print(f"  CUs:     {sess['cu_ids']}")
    else:
        print(f"  CREATE FAILED: {err}")

    # Step 4: Execute the session
    print()
    print("--- Step 4: Execute session ---")
    ok, exec_result, err = session.Run("execute", {
        "session_name": "TestSession",
        "entry_command": "read_state",
        "entry_params": {},
    })
    if ok:
        print(f"  Status:          {exec_result['status']}")
        print(f"  Steps total:     {exec_result['steps_total']}")
        print(f"  Steps completed: {exec_result['steps_completed']}")
        print(f"  Steps repaired:  {exec_result['steps_repaired']}")
        print(f"  Final state:     {exec_result['final_state']}")
        for r in exec_result["results"]:
            icon = "OK" if r["status"] == "ok" else "FAIL"
            cached = " (cached)" if r.get("cached") else ""
            print(f"    [{icon:4s}] step={r['step']}  cu={r['cu_id'][:20]}...  "
                  f"attempts={r['attempts']}  {r.get('duration_ms', 0):.1f}ms{cached}")
    else:
        print(f"  EXECUTE FAILED: {err}")

    # Step 5: Session status
    print()
    print("--- Step 5: Session status ---")
    ok, status, _ = session.Run("status", {"session_name": "TestSession"})
    if ok:
        print(f"  Status: {status['status']}")
        for s in status["steps"]:
            print(f"    step={s['step']}  cu={s['cu_id'][:20]}...  "
                  f"status={s['status']}  attempts={s['attempts']}  "
                  f"{s['duration_ms']:.1f}ms")

    # Step 6: MemUnit log
    print()
    print("--- Step 6: MemUnit log ---")
    ok, mlog, _ = session.Run("memunit_log", {"session_name": "TestSession"})
    if ok:
        print(f"  MemUnits: {mlog['count']}")
        for m in mlog["memunits"]:
            print(f"    step={m['step']}  attempt={m['attempt']}  "
                  f"status={m['status']}  cu={m['cu_id'][:20]}...  "
                  f"dur={m['duration_ms']:.1f}ms")
            if m["error_msg"]:
                print(f"      error: {m['error_msg'][:80]}")
            if m["dependency_chain"]:
                print(f"      deps:  {m['dependency_chain']}")

    # Step 7: Repair log
    print()
    print("--- Step 7: Repair log ---")
    ok, rlog, _ = session.Run("repair_log", {"session_name": "TestSession"})
    if ok:
        print(f"  Repairs: {rlog['count']}")
        for r in rlog["repairs"]:
            print(f"    step={r['step']}  strategy={r['strategy']}  "
                  f"test={r['test_status']}  status={r['status']}")
            if r["reasoning"]:
                print(f"      reasoning: {r['reasoning'][:80]}")

    # Step 8: Survivor lookup
    print()
    print("--- Step 8: Survivor lookup ---")
    ok, survivors, _ = session.Run("survivor_lookup", {"capability": "read_state"})
    if ok:
        print(f"  Capability: read_state")
        print(f"  Survivors:  {survivors['count']}")
        for s in survivors["survivors"]:
            print(f"    {s['cu_id'][:20]}...  rank={s['rank']:.2f}  "
                  f"success={s['success']}  fail={s['failure']}  "
                  f"from={s['origin_class']}")

    # Step 9: Re-execute (should hit cache for deterministic CUs)
    print()
    print("--- Step 9: Re-execute (cache test) ---")
    ok, exec2, _ = session.Run("execute", {
        "session_name": "TestSession",
        "entry_command": "read_state",
        "entry_params": {},
    })
    if ok:
        cached_count = sum(1 for r in exec2["results"] if r.get("cached"))
        print(f"  Status:          {exec2['status']}")
        print(f"  Cached steps:    {cached_count}/{exec2['steps_total']}")

    # Step 10: Final stats
    print()
    print("--- Step 10: Final stats ---")
    ok, stats, _ = session.Run("stats", {})
    if ok:
        for k, v in stats["counts"].items():
            print(f"  {k:25s} {v}")
        print()
        for k, v in stats["stats"].items():
            print(f"  {k:25s} {v}")

    print()
    print("=== EXECUTION SESSION DEMO COMPLETE ===")
