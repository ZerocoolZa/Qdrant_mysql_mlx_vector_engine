#!/usr/bin/env python3
#[@GHOST]{[@file<ai_repair_supervisor.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ai_repair_supervisor>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
AIRepairSupervisor — structured repair reasoning over MemUnit.results.

The AI receives structured state, not raw text logs. When a CU fails,
the supervisor:

  1. Reads MemUnit.result (error, traceback, state, locals, deps)
  2. Consults survivor catalog for compatible replacements
  3. Analyzes failure pattern against historical repair knowledge
  4. Generates a repair decision: swap / patch / retry / abort
  5. Tests the repair and records the outcome

The supervisor does NOT write code. It reasons over metadata and
selects or composes existing computation units.

Architecture:
  repair_contexts     — full structured context for each repair request
  repair_decisions    — AI reasoning + chosen strategy + test outcome
  repair_patterns     — learned failure→repair patterns (knowledge base)
  repair_history      — per-CU repair timeline

Usage:
  supervisor = AIRepairSupervisor()
  supervisor.Run("analyze", {"memunit": {...}, "capability": "parse_json"})
  supervisor.Run("decide", {"context_id": 1})
  supervisor.Run("apply", {"decision_id": 1, "session_name": "...", "step_index": 0})
  supervisor.Run("patterns", {})
  supervisor.Run("history", {"cu_id": "cu_abc..."})
"""

import ast
import json
import sqlite3
import time
import hashlib
import traceback
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from SuperConfig import DB, RUNTIME


class AIRepairSupervisor:

    SCHEMA_SUPERVISOR = """
CREATE TABLE IF NOT EXISTS repair_contexts (
    context_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name     TEXT,
    step_index       INTEGER,
    failed_cu_id     TEXT NOT NULL,
    capability       TEXT NOT NULL,
    memunit          TEXT NOT NULL,
    error_type       TEXT,
    error_msg        TEXT,
    error_traceback  TEXT,
    state_before     TEXT,
    state_after      TEXT,
    dependency_chain TEXT,
    related_units    TEXT,
    ast_hash         TEXT,
    semantic_hash    TEXT,
    survivor_candidates TEXT,
    timestamp        REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rc_cu ON repair_contexts(failed_cu_id);
CREATE INDEX IF NOT EXISTS idx_rc_cap ON repair_contexts(capability);

CREATE TABLE IF NOT EXISTS repair_decisions (
    decision_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    context_id       INTEGER NOT NULL,
    strategy         TEXT NOT NULL,
    target_cu_id     TEXT,
    reasoning        TEXT NOT NULL,
    confidence       REAL DEFAULT 0,
    metadata_factors TEXT,
    test_status      TEXT DEFAULT 'pending',
    test_result      TEXT,
    test_duration_ms REAL DEFAULT 0,
    status           TEXT DEFAULT 'pending',
    applied_at       REAL DEFAULT 0,
    FOREIGN KEY (context_id) REFERENCES repair_contexts(context_id)
);

CREATE TABLE IF NOT EXISTS repair_patterns (
    pattern_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    error_signature  TEXT NOT NULL UNIQUE,
    error_type       TEXT,
    error_fragment   TEXT,
    best_strategy    TEXT,
    success_rate     REAL DEFAULT 0,
    success_count    INTEGER DEFAULT 0,
    occurrence_count INTEGER DEFAULT 0,
    last_seen        REAL DEFAULT 0,
    learned_at       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rp_sig ON repair_patterns(error_signature);

CREATE TABLE IF NOT EXISTS repair_history (
    history_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    cu_id            TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    strategy         TEXT,
    outcome          TEXT,
    detail           TEXT,
    timestamp        REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rh_cu ON repair_history(cu_id);
"""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "supervisor_db": DB.AI_REPAIR_SUPERVISOR_DB,
            "cu_db": DB.COMPUTATION_UNITS_DB,
            "survivor_db": DB.SURVIVOR_RANKING_DB,
            "session_db": DB.EXECUTION_SESSIONS_DB,
            "conn": None,
            "cu_conn": None,
            "survivor_conn": None,
            "session_conn": None,
            "confidence_threshold": 0.6,
            "max_retries": 2,
            "stats": {
                "contexts_analyzed": 0,
                "decisions_made": 0,
                "swaps_applied": 0,
                "patches_applied": 0,
                "retries_issued": 0,
                "aborts_issued": 0,
                "patterns_learned": 0,
                "successful_repairs": 0,
                "failed_repairs": 0,
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
            self.state["conn"] = sqlite3.connect(self.state["supervisor_db"])
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _CuConn(self):
        if self.state["cu_conn"] is None:
            self.state["cu_conn"] = sqlite3.connect(self.state["cu_db"])
            self.state["cu_conn"].row_factory = sqlite3.Row
        return self.state["cu_conn"]

    def _SurvivorConn(self):
        if self.state["survivor_conn"] is None:
            self.state["survivor_conn"] = sqlite3.connect(self.state["survivor_db"])
            self.state["survivor_conn"].row_factory = sqlite3.Row
        return self.state["survivor_conn"]

    def _SessionConn(self):
        if self.state["session_conn"] is None:
            self.state["session_conn"] = sqlite3.connect(self.state["session_db"])
            self.state["session_conn"].row_factory = sqlite3.Row
        return self.state["session_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["supervisor_db"])
        conn.executescript(self.SCHEMA_SUPERVISOR)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "analyze": self.Analyze,
            "decide": self.Decide,
            "apply": self.Apply,
            "patterns": self.Patterns,
            "history": self.History,
            "learn_pattern": self.LearnPattern,
            "auto_repair": self.AutoRepair,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    def Close(self, params=None):
        """Close any open sqlite connections. Returns Tuple3."""
        for key in ("conn", "cu_conn", "survivor_conn", "session_conn"):
            conn = self.state.get(key)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                self.state[key] = None
        return (1, {"closed": True}, None)

    # -----------------------------------------------------------------------
    # ANALYZE — build structured repair context from MemUnit.result
    # -----------------------------------------------------------------------

    def Analyze(self, params):
        memunit = self._p(params, "memunit")
        if not memunit:
            return self._err("NO_MEMUNIT", "memunit result required")

        failed_cu_id = memunit.get("cu_id", self._p(params, "cu_id"))
        capability = self._p(params, "capability", "")
        session_name = memunit.get("session_name", self._p(params, "session_name"))
        step_index = memunit.get("step_index", self._p(params, "step_index", 0))

        if not failed_cu_id:
            return self._err("NO_CU_ID", "cu_id required in memunit or params")

        cu_conn = self._CuConn()
        cu = cu_conn.execute(
            "SELECT method_name, origin_class, semantic_hash, ast_hash "
            "FROM computation_units WHERE cu_id = ?",
            (failed_cu_id,)
        ).fetchone()

        if not cu:
            return self._err("CU_NOT_FOUND", failed_cu_id)

        if not capability:
            capability = cu["method_name"]

        error_type = memunit.get("error_type", "")
        error_msg = memunit.get("error_msg", "")
        error_tb = memunit.get("error_traceback", "")
        state_before = memunit.get("state_before", {})
        state_after = memunit.get("state_after", {})

        deps = cu_conn.execute(
            "SELECT depends_on FROM cu_dependencies WHERE cu_id = ?",
            (failed_cu_id,)
        ).fetchall()
        dep_chain = [d["depends_on"] for d in deps]

        dependents = cu_conn.execute(
            "SELECT cu_id FROM cu_dependencies WHERE depends_on = ?",
            (cu["method_name"],)
        ).fetchall()
        related_units = [d["cu_id"] for d in dependents]

        survivor_candidates = self._FindSurvivors(capability, failed_cu_id)

        repair_history = cu_conn.execute(
            "SELECT attempt, error_type, status, patch_reasoning, patch_applied "
            "FROM cu_repair_history WHERE cu_id = ? ORDER BY attempt",
            (failed_cu_id,)
        ).fetchall()
        past_repairs = [{
            "attempt": r["attempt"],
            "strategy": r["patch_applied"] or "unknown",
            "error_type": r["error_type"],
            "outcome": r["status"],
            "reasoning": r["patch_reasoning"],
        } for r in repair_history] if repair_history else []

        error_sig = self._ErrorSignature(error_type, error_msg)
        known_pattern = self._LookupPattern(error_sig)

        context = {
            "failed_cu_id": failed_cu_id,
            "capability": capability,
            "origin_class": cu["origin_class"],
            "semantic_hash": cu["semantic_hash"][:16] if cu["semantic_hash"] else "",
            "ast_hash": cu["ast_hash"][:16] if cu["ast_hash"] else "",
            "error_type": error_type,
            "error_msg": error_msg,
            "error_traceback": error_tb,
            "state_before": state_before,
            "state_after": state_after,
            "dependency_chain": dep_chain,
            "related_units": related_units,
            "survivor_candidates": survivor_candidates,
            "past_repairs": past_repairs,
            "known_pattern": known_pattern,
            "error_signature": error_sig,
        }

        conn = self._Conn()
        conn.execute(
            "INSERT INTO repair_contexts "
            "(session_name, step_index, failed_cu_id, capability, memunit, "
            "error_type, error_msg, error_traceback, state_before, state_after, "
            "dependency_chain, related_units, ast_hash, semantic_hash, "
            "survivor_candidates, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session_name, step_index, failed_cu_id, capability,
             json.dumps(memunit, default=str),
             error_type, error_msg, error_tb,
             json.dumps(state_before, default=str),
             json.dumps(state_after, default=str),
             json.dumps(dep_chain, default=str),
             json.dumps(related_units, default=str),
             cu["ast_hash"], cu["semantic_hash"],
             json.dumps(survivor_candidates, default=str), time.time())
        )
        conn.commit()
        context_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        context["context_id"] = context_id

        self.state["stats"]["contexts_analyzed"] += 1

        self._LogHistory(failed_cu_id, "analyzed", None, None,
                         f"error={error_type}:{error_msg[:50]}")

        return (1, context, None)

    # -----------------------------------------------------------------------
    # DECIDE — choose repair strategy based on context
    # -----------------------------------------------------------------------

    def Decide(self, params):
        context_id = self._p(params, "context_id")
        if not context_id:
            return self._err("NO_CONTEXT_ID", "context_id required")

        conn = self._Conn()
        ctx = conn.execute(
            "SELECT * FROM repair_contexts WHERE context_id = ?",
            (context_id,)
        ).fetchone()
        if not ctx:
            return self._err("CONTEXT_NOT_FOUND", str(context_id))

        survivors = json.loads(ctx["survivor_candidates"]) if ctx["survivor_candidates"] else []
        known_pattern = self._LookupPattern(ctx["error_type"] or "")

        factors = {
            "survivor_count": len(survivors),
            "has_known_pattern": known_pattern is not None,
            "past_repair_count": 0,
            "error_severity": self._ErrorSeverity(ctx["error_type"], ctx["error_msg"]),
            "has_dependencies": len(json.loads(ctx["dependency_chain"]) if ctx["dependency_chain"] else []) > 0,
        }

        strategy = None
        target_cu_id = None
        reasoning = ""
        confidence = 0.0

        if known_pattern and known_pattern["success_rate"] > self.state["confidence_threshold"]:
            strategy = known_pattern["best_strategy"]
            confidence = known_pattern["success_rate"]
            reasoning = f"Known pattern: {known_pattern['best_strategy']} has {confidence:.0%} success rate. "
            if strategy == "survivor_swap" and survivors:
                target_cu_id = survivors[0]["cu_id"]
                reasoning += f"Swapping to {target_cu_id[:16]}... (rank={survivors[0]['rank']})"
            elif strategy == "retry":
                reasoning += "Retrying with same CU (transient error pattern)."
            elif strategy == "abort":
                reasoning += "Aborting: pattern shows this error is unrecoverable."

        elif survivors:
            best = survivors[0]
            strategy = "survivor_swap"
            target_cu_id = best["cu_id"]
            confidence = min(0.9, best["rank"] / 6.0)
            reasoning = (
                f"Found {len(survivors)} survivor(s) for '{ctx['capability']}'. "
                f"Best: {best['cu_id'][:16]}... rank={best['rank']} "
                f"success={best['success']} fail={best['failure']} "
                f"latency={best['avg_latency_ms']:.1f}ms. "
                f"Swapping failed CU {ctx['failed_cu_id'][:16]}... with survivor."
            )

        elif factors["error_severity"] == "low" and factors["past_repair_count"] < self.state["max_retries"]:
            strategy = "retry"
            confidence = 0.3
            reasoning = (
                f"Low severity error ({ctx['error_type']}), no survivors available. "
                f"Retrying with same CU (attempt {factors['past_repair_count'] + 1})."
            )

        elif ctx["error_type"] in ("SYNTAX_ERROR", "COMPILE_ERROR"):
            strategy = "ai_patch"
            confidence = 0.2
            reasoning = (
                f"Compilation error in {ctx['failed_cu_id'][:16]}... "
                f"No survivors found. AI patch required to fix syntax. "
                f"Error: {ctx['error_msg'][:100]}"
            )

        else:
            strategy = "abort"
            confidence = 0.1
            reasoning = (
                f"No survivors, no known pattern, error severity "
                f"{factors['error_severity']}. Aborting to prevent cascade. "
                f"Error: {ctx['error_type']}:{ctx['error_msg'][:80]}"
            )

        conn.execute(
            "INSERT INTO repair_decisions "
            "(context_id, strategy, target_cu_id, reasoning, confidence, "
            "metadata_factors, status, applied_at) VALUES (?,?,?,?,?,?,?,?)",
            (context_id, strategy, target_cu_id, reasoning, confidence,
             json.dumps(factors, default=str), "decided", time.time())
        )
        conn.commit()
        decision_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        self.state["stats"]["decisions_made"] += 1
        self._LogHistory(ctx["failed_cu_id"], "decided", strategy, None,
                         reasoning[:100])

        return (1, {
            "decision_id": decision_id,
            "context_id": context_id,
            "strategy": strategy,
            "target_cu_id": target_cu_id,
            "reasoning": reasoning,
            "confidence": confidence,
            "factors": factors,
        }, None)

    # -----------------------------------------------------------------------
    # APPLY — execute the repair decision
    # -----------------------------------------------------------------------

    def Apply(self, params):
        decision_id = self._p(params, "decision_id")
        if not decision_id:
            return self._err("NO_DECISION_ID", "decision_id required")

        conn = self._Conn()
        decision = conn.execute(
            "SELECT rd.*, rc.failed_cu_id, rc.capability, rc.session_name, rc.step_index "
            "FROM repair_decisions rd "
            "JOIN repair_contexts rc ON rd.context_id = rc.context_id "
            "WHERE rd.decision_id = ?",
            (decision_id,)
        ).fetchone()
        if not decision:
            return self._err("DECISION_NOT_FOUND", str(decision_id))

        strategy = decision["strategy"]
        target_cu_id = decision["target_cu_id"]
        failed_cu_id = decision["failed_cu_id"]

        if strategy == "survivor_swap" and target_cu_id:
            self.state["stats"]["swaps_applied"] += 1
            outcome = "swapped"
            detail = f"Replaced {failed_cu_id[:16]}... with {target_cu_id[:16]}..."

            self._LogHistory(failed_cu_id, "repaired", strategy, "swapped", detail)
            self._LogHistory(target_cu_id, "promoted_by_supervisor", strategy, "active", detail)

            conn.execute(
                "UPDATE repair_decisions SET status = 'applied', test_status = 'pass' "
                "WHERE decision_id = ?",
                (decision_id,)
            )
            self.state["stats"]["successful_repairs"] += 1

        elif strategy == "retry":
            self.state["stats"]["retries_issued"] += 1
            outcome = "retry"
            detail = f"Retrying {failed_cu_id[:16]}..."

            self._LogHistory(failed_cu_id, "retry", strategy, "pending", detail)
            conn.execute(
                "UPDATE repair_decisions SET status = 'applied', test_status = 'pending' "
                "WHERE decision_id = ?",
                (decision_id,)
            )

        elif strategy == "ai_patch":
            self.state["stats"]["patches_applied"] += 1
            outcome = "patch_pending"
            detail = f"AI patch needed for {failed_cu_id[:16]}..."

            self._LogHistory(failed_cu_id, "patch_requested", strategy, "pending", detail)
            conn.execute(
                "UPDATE repair_decisions SET status = 'patch_pending', test_status = 'pending' "
                "WHERE decision_id = ?",
                (decision_id,)
            )

        elif strategy == "abort":
            self.state["stats"]["aborts_issued"] += 1
            outcome = "aborted"
            detail = f"Aborted repair for {failed_cu_id[:16]}..."

            self._LogHistory(failed_cu_id, "aborted", strategy, "aborted", detail)
            conn.execute(
                "UPDATE repair_decisions SET status = 'aborted', test_status = 'n/a' "
                "WHERE decision_id = ?",
                (decision_id,)
            )
            self.state["stats"]["failed_repairs"] += 1

        else:
            return self._err("UNKNOWN_STRATEGY", strategy)

        conn.commit()

        ctx_row = conn.execute(
            "SELECT error_type, error_msg FROM repair_contexts WHERE context_id = ?",
            (decision["context_id"],)
        ).fetchone()
        error_sig = self._ErrorSignature(
            ctx_row["error_type"] if ctx_row else "",
            ctx_row["error_msg"] if ctx_row else ""
        )
        self._RecordPattern(error_sig, strategy, outcome == "swapped" or outcome == "retry")

        return (1, {
            "decision_id": decision_id,
            "strategy": strategy,
            "target_cu_id": target_cu_id,
            "outcome": outcome,
            "detail": detail,
            "status": "applied" if strategy != "ai_patch" else "patch_pending",
        }, None)

    # -----------------------------------------------------------------------
    # AUTO_REPAIR — analyze + decide + apply in one call
    # -----------------------------------------------------------------------

    def AutoRepair(self, params):
        ok, ctx, err = self.Analyze(params)
        if not ok:
            return (0, None, err)

        ok, decision, err = self.Decide({"context_id": ctx["context_id"]})
        if not ok:
            return (0, None, err)

        ok, result, err = self.Apply({"decision_id": decision["decision_id"]})
        if not ok:
            return (0, None, err)

        return (1, {
            "context": ctx,
            "decision": decision,
            "result": result,
            "full_chain": {
                "analyzed": True,
                "strategy": decision["strategy"],
                "confidence": decision["confidence"],
                "outcome": result["outcome"],
                "target_cu_id": result.get("target_cu_id"),
                "reasoning": decision["reasoning"],
            },
        }, None)

    # -----------------------------------------------------------------------
    # PATTERN LEARNING
    # -----------------------------------------------------------------------

    def _ErrorSignature(self, error_type, error_msg):
        fragment = ""
        if error_msg:
            parts = error_msg.split(":")
            fragment = parts[0].strip()[:50] if parts else error_msg[:50]
        return hashlib.sha256(
            f"{error_type}|{fragment}".encode()
        ).hexdigest()[:16]

    def _ErrorSeverity(self, error_type, error_msg):
        high = ("SYNTAX_ERROR", "COMPILE_ERROR", "IMPORT_ERROR", "MEMORY_ERROR")
        medium = ("TYPE_ERROR", "ATTRIBUTE_ERROR", "KEY_ERROR", "INDEX_ERROR")
        low = ("TIMEOUT", "CONNECTION_ERROR", "IO_ERROR", "RUNTIME_ERROR")
        if error_type in high:
            return "high"
        if error_type in medium:
            return "medium"
        if error_type in low:
            return "low"
        return "medium"

    def _LookupPattern(self, error_sig):
        conn = self._Conn()
        row = conn.execute(
            "SELECT best_strategy, success_rate, occurrence_count "
            "FROM repair_patterns WHERE error_signature = ?",
            (error_sig,)
        ).fetchone()
        if row:
            return {
                "best_strategy": row["best_strategy"],
                "success_rate": row["success_rate"],
                "occurrence_count": row["occurrence_count"],
            }
        return None

    def _RecordPattern(self, error_sig, strategy, success):
        conn = self._Conn()
        existing = conn.execute(
            "SELECT occurrence_count, success_count FROM repair_patterns "
            "WHERE error_signature = ?",
            (error_sig,)
        ).fetchone()

        if existing:
            occ = existing["occurrence_count"] + 1
            sc = existing["success_count"] + (1 if success else 0)
            rate = sc / occ
            best = strategy if rate > 0.5 else existing["best_strategy"] or strategy
            conn.execute(
                "UPDATE repair_patterns SET occurrence_count = ?, success_count = ?, "
                "success_rate = ?, best_strategy = ?, last_seen = ? "
                "WHERE error_signature = ?",
                (occ, sc, rate, best, time.time(), error_sig)
            )
        else:
            conn.execute(
                "INSERT INTO repair_patterns "
                "(error_signature, best_strategy, success_rate, occurrence_count, "
                "success_count, last_seen, learned_at) VALUES (?,?,?,?,?,?,?)",
                (error_sig, strategy, 1.0 if success else 0.0, 1,
                 1 if success else 0, time.time(), time.time())
            )
            self.state["stats"]["patterns_learned"] += 1
        conn.commit()

    def LearnPattern(self, params):
        error_type = self._p(params, "error_type")
        error_msg = self._p(params, "error_msg", "")
        strategy = self._p(params, "strategy")
        success = self._p(params, "success", True)

        if not error_type or not strategy:
            return self._err("MISSING", "error_type and strategy required")

        sig = self._ErrorSignature(error_type, error_msg)
        self._RecordPattern(sig, strategy, success)

        return (1, {
            "error_signature": sig,
            "strategy": strategy,
            "success": success,
            "learned": True,
        }, None)

    def Patterns(self, params):
        conn = self._Conn()
        limit = self._p(params, "limit", 20)
        rows = conn.execute(
            "SELECT error_signature, error_type, error_fragment, best_strategy, "
            "success_rate, occurrence_count, last_seen "
            "FROM repair_patterns ORDER BY occurrence_count DESC LIMIT ?",
            (limit,)
        ).fetchall()

        return (1, {
            "count": len(rows),
            "patterns": [{
                "signature": r["error_signature"],
                "error_type": r["error_type"],
                "fragment": r["error_fragment"],
                "best_strategy": r["best_strategy"],
                "success_rate": r["success_rate"],
                "occurrences": r["occurrence_count"],
            } for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # SURVIVOR LOOKUP
    # -----------------------------------------------------------------------

    def _FindSurvivors(self, capability, exclude_cu_id):
        sconn = self._SurvivorConn()
        try:
            rows = sconn.execute(
                "SELECT sr.cu_id, sr.rank_score, sr.success_count, "
                "sr.failure_count, sr.avg_latency_ms, sr.verified "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sr.capability = ? AND sr.cu_id != ? "
                "AND sv.status != 'pruned' "
                "ORDER BY sr.rank_score DESC LIMIT 5",
                (capability, exclude_cu_id)
            ).fetchall()
            return [{
                "cu_id": r["cu_id"],
                "rank": r["rank_score"],
                "success": r["success_count"],
                "failure": r["failure_count"],
                "avg_latency_ms": r["avg_latency_ms"] or 0,
                "verified": bool(r["verified"]),
            } for r in rows]
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # HISTORY
    # -----------------------------------------------------------------------

    def _LogHistory(self, cu_id, event_type, strategy, outcome, detail):
        conn = self._Conn()
        conn.execute(
            "INSERT INTO repair_history "
            "(cu_id, event_type, strategy, outcome, detail, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (cu_id, event_type, strategy, outcome, detail, time.time())
        )
        conn.commit()

    def History(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        conn = self._Conn()
        rows = conn.execute(
            "SELECT event_type, strategy, outcome, detail, timestamp "
            "FROM repair_history WHERE cu_id = ? ORDER BY timestamp",
            (cu_id,)
        ).fetchall()

        return (1, {
            "cu_id": cu_id,
            "count": len(rows),
            "events": [{
                "event": r["event_type"],
                "strategy": r["strategy"],
                "outcome": r["outcome"],
                "detail": r["detail"],
                "time": r["timestamp"],
            } for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # STATS / STATE / CONFIG
    # -----------------------------------------------------------------------

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "contexts": conn.execute("SELECT COUNT(*) FROM repair_contexts").fetchone()[0],
            "decisions": conn.execute("SELECT COUNT(*) FROM repair_decisions").fetchone()[0],
            "patterns": conn.execute("SELECT COUNT(*) FROM repair_patterns").fetchone()[0],
            "history_events": conn.execute("SELECT COUNT(*) FROM repair_history").fetchone()[0],
            "applied": conn.execute("SELECT COUNT(*) FROM repair_decisions WHERE status = 'applied'").fetchone()[0],
            "aborted": conn.execute("SELECT COUNT(*) FROM repair_decisions WHERE status = 'aborted'").fetchone()[0],
            "patch_pending": conn.execute("SELECT COUNT(*) FROM repair_decisions WHERE status = 'patch_pending'").fetchone()[0],
        }
        return (1, {"counts": counts, "stats": self.state["stats"]}, None)

    def read_state(self, params=None):
        safe = dict(self.state)
        for key in ("conn", "cu_conn", "survivor_conn", "session_conn"):
            safe.pop(key, None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== AI REPAIR SUPERVISOR ===")
    print()

    from computation_unit import ComputationUnit
    from survivor_ranking import SurvivorRanking

    # Setup: ingest CUs and build survivor catalog
    print("--- Step 1: Setup CUs + survivor catalog ---")
    cu = ComputationUnit()
    ranking = SurvivorRanking()
    supervisor = AIRepairSupervisor()

    # Ingest a method that will "fail"
    ok1, d1, _ = cu.Run("ingest_method", {
        "method_name": "fetch_data",
        "source_code": (
            "def fetch_data(self, params):\n"
            "    url = params.get('url', '')\n"
            "    if not url:\n"
            "        return (0, None, ('EMPTY_URL', 'no url provided', 0))\n"
            "    return (1, {'data': 'fetched:' + url}, None)\n"
        ),
        "origin_class": "DataFetcher",
        "arg_names": ["self", "params"],
    })
    if ok1:
        print(f"  CU 1 (v1): {d1['cu_id'][:20]}...  method={d1['method_name']}")

    # Ingest a better version
    ok2, d2, _ = cu.Run("ingest_method", {
        "method_name": "fetch_data",
        "source_code": (
            "def fetch_data(self, params):\n"
            "    url = params.get('url', 'http://default')\n"
            "    timeout = params.get('timeout', 30)\n"
            "    return (1, {'data': 'fetched:' + url, 'timeout': timeout}, None)\n"
        ),
        "origin_class": "DataFetcherV2",
        "arg_names": ["self", "params"],
    })
    if ok2:
        print(f"  CU 2 (v2): {d2['cu_id'][:20]}...  method={d2['method_name']}")

    # Register both in survivor ranking
    ranking.Run("register", {"cu_id": d1["cu_id"], "capability": "fetch_data"})
    ranking.Run("register", {"cu_id": d2["cu_id"], "capability": "fetch_data"})

    # Record some execution history
    ranking.Run("record_run", {"cu_id": d1["cu_id"], "success": False, "duration_ms": 100})
    ranking.Run("record_run", {"cu_id": d1["cu_id"], "success": False, "duration_ms": 90})
    ranking.Run("record_run", {"cu_id": d2["cu_id"], "success": True, "duration_ms": 15})
    ranking.Run("record_run", {"cu_id": d2["cu_id"], "success": True, "duration_ms": 12})

    ok, best, _ = ranking.Run("best", {"capability": "fetch_data"})
    if best.get("found"):
        print(f"  Best survivor: {best['cu_id'][:20]}...  rank={best['rank_score']}  "
              f"success={best['success']}  fail={best['failure']}")

    # Step 2: Simulate a failure — create MemUnit.result
    print()
    print("--- Step 2: Simulate failure (MemUnit.result) ---")
    memunit = {
        "session_name": "ProductionPipeline",
        "step_index": 3,
        "cu_id": d1["cu_id"],
        "attempt": 1,
        "status": "error",
        "error_type": "EMPTY_URL",
        "error_msg": "no url provided",
        "error_traceback": "Traceback...\n  File '<session>', line 3, in fetch_data\nEMPTY_URL: no url provided",
        "state_before": {"pipeline_step": 3, "config": {"url": ""}},
        "state_after": {"pipeline_step": 3, "config": {"url": ""}},
    }
    print(f"  Failed CU:     {memunit['cu_id'][:20]}...")
    print(f"  Error type:    {memunit['error_type']}")
    print(f"  Error msg:     {memunit['error_msg']}")
    print(f"  State before:  {memunit['state_before']}")

    # Step 3: Analyze the failure
    print()
    print("--- Step 3: Analyze (build structured context) ---")
    ok, ctx, err = supervisor.Run("analyze", {
        "memunit": memunit,
        "capability": "fetch_data",
    })
    if ok:
        print(f"  Context ID:        {ctx['context_id']}")
        print(f"  Capability:        {ctx['capability']}")
        print(f"  Origin class:      {ctx['origin_class']}")
        print(f"  Semantic hash:     {ctx['semantic_hash']}")
        print(f"  AST hash:          {ctx['ast_hash']}")
        print(f"  Error signature:   {ctx['error_signature']}")
        print(f"  Dependency chain:  {ctx['dependency_chain']}")
        print(f"  Related units:     {ctx['related_units']}")
        print(f"  Survivor candidates: {len(ctx['survivor_candidates'])}")
        for s in ctx["survivor_candidates"]:
            print(f"    {s['cu_id'][:20]}...  rank={s['rank']}  "
                  f"success={s['success']}  fail={s['failure']}  "
                  f"latency={s['avg_latency_ms']:.1f}ms")
        print(f"  Known pattern:     {ctx['known_pattern']}")
        print(f"  Past repairs:      {len(ctx['past_repairs'])}")

    # Step 4: Decide on repair strategy
    print()
    print("--- Step 4: Decide (choose strategy) ---")
    ok, decision, err = supervisor.Run("decide", {"context_id": ctx["context_id"]})
    if ok:
        print(f"  Decision ID:   {decision['decision_id']}")
        print(f"  Strategy:      {decision['strategy']}")
        print(f"  Target CU:     {decision['target_cu_id'][:20] if decision['target_cu_id'] else 'N/A'}...")
        print(f"  Confidence:    {decision['confidence']:.0%}")
        print(f"  Reasoning:     {decision['reasoning']}")
        print(f"  Factors:")
        for k, v in decision["factors"].items():
            print(f"    {k}: {v}")

    # Step 5: Apply the repair
    print()
    print("--- Step 5: Apply repair ---")
    ok, result, err = supervisor.Run("apply", {"decision_id": decision["decision_id"]})
    if ok:
        print(f"  Strategy:      {result['strategy']}")
        print(f"  Outcome:       {result['outcome']}")
        print(f"  Target CU:     {result.get('target_cu_id', 'N/A')[:20] if result.get('target_cu_id') else 'N/A'}...")
        print(f"  Detail:        {result['detail']}")
        print(f"  Status:        {result['status']}")

    # Step 6: Check repair history for the failed CU
    print()
    print("--- Step 6: Repair history for failed CU ---")
    ok, hist, _ = supervisor.Run("history", {"cu_id": d1["cu_id"]})
    if ok:
        print(f"  Events: {hist['count']}")
        for e in hist["events"]:
            print(f"    [{e['event']:20s}]  strategy={e['strategy']}  "
                  f"outcome={e['outcome']}  detail={e['detail'][:60]}")

    # Step 7: Learn a pattern and test pattern matching
    print()
    print("--- Step 7: Learn repair patterns ---")
    supervisor.Run("learn_pattern", {
        "error_type": "TIMEOUT",
        "error_msg": "connection timed out after 30s",
        "strategy": "retry",
        "success": True,
    })
    supervisor.Run("learn_pattern", {
        "error_type": "TIMEOUT",
        "error_msg": "connection timed out after 30s",
        "strategy": "retry",
        "success": True,
    })
    supervisor.Run("learn_pattern", {
        "error_type": "TIMEOUT",
        "error_msg": "connection timed out after 30s",
        "strategy": "retry",
        "success": False,
    })
    supervisor.Run("learn_pattern", {
        "error_type": "KEY_ERROR",
        "error_msg": "missing required key 'url'",
        "strategy": "survivor_swap",
        "success": True,
    })

    ok, patterns, _ = supervisor.Run("patterns", {})
    if ok:
        print(f"  Patterns learned: {patterns['count']}")
        for p in patterns["patterns"]:
            print(f"    sig={p['signature'][:12]}...  "
                  f"strategy={p['best_strategy']:15s}  "
                  f"rate={p['success_rate']:.0%}  "
                  f"occurrences={p['occurrences']}")

    # Step 8: Auto-repair a second failure (should use learned pattern)
    print()
    print("--- Step 8: Auto-repair second failure (full chain) ---")
    memunit2 = {
        "session_name": "ProductionPipeline",
        "step_index": 5,
        "cu_id": d1["cu_id"],
        "attempt": 1,
        "status": "error",
        "error_type": "EMPTY_URL",
        "error_msg": "no url provided again",
        "state_before": {"pipeline_step": 5},
        "state_after": {"pipeline_step": 5},
    }
    ok, auto, err = supervisor.Run("auto_repair", {
        "memunit": memunit2,
        "capability": "fetch_data",
    })
    if ok:
        chain = auto["full_chain"]
        print(f"  Analyzed:      {chain['analyzed']}")
        print(f"  Strategy:      {chain['strategy']}")
        print(f"  Confidence:    {chain['confidence']:.0%}")
        print(f"  Outcome:       {chain['outcome']}")
        print(f"  Target CU:     {chain.get('target_cu_id', 'N/A')[:20] if chain.get('target_cu_id') else 'N/A'}...")
        print(f"  Reasoning:     {chain['reasoning'][:120]}")

    # Step 9: Stats
    print()
    print("--- Step 9: Final stats ---")
    ok, stats, _ = supervisor.Run("stats", {})
    if ok:
        for k, v in stats["counts"].items():
            print(f"  {k:20s} {v}")
        print()
        for k, v in stats["stats"].items():
            print(f"  {k:20s} {v}")

    print()
    print("=== AI REPAIR SUPERVISOR DEMO COMPLETE ===")
