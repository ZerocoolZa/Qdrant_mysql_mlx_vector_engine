#!/usr/bin/env python3
#[@GHOST]{[@file<survivor_ranking.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<survivor_ranking>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
SurvivorRanking — evolutionary selection layer for Computation Units.

Sits between the ComputationUnit store and the ExecutionPlanner.

The planner never decides which implementation wins. It asks:
    "Give me the highest-ranked compatible implementation of capability X."

This layer:
  1. Tracks all versions of a capability (method name + interface hash)
  2. Ranks them by: success rate, performance, verification, usage count
  3. Prunes weak versions (evolutionary selection — only survivors persist)
  4. Maintains the survivor graph (which version replaced which)
  5. Provides compatibility matching (interface hash + dependency compatibility)

Architecture:
  survivor_versions     — all versions of each capability
  survivor_rankings     — computed rank scores (updated on every execution)
  survivor_graph        — which version replaced which (evolutionary tree)
  survivor_pruning_log  — record of pruned versions and why

Usage:
  ranking = SurvivorRanking()
  ranking.Run("register", {"cu_id": "cu_abc...", "capability": "read_state"})
  ranking.Run("best", {"capability": "read_state"})
  ranking.Run("promote", {"cu_id": "cu_abc...", "reason": "faster + verified"})
  ranking.Run("prune", {"capability": "read_state", "keep_top_n": 3})
  ranking.Run("evolution", {"capability": "read_state"})
"""

import json
import sqlite3
import time
import hashlib
from typing import Dict, List, Optional, Tuple

from SuperConfig import DB, RUNTIME


class SurvivorRanking:

    SCHEMA_SURVIVOR = """
CREATE TABLE IF NOT EXISTS survivor_versions (
    version_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cu_id           TEXT NOT NULL,
    capability      TEXT NOT NULL,
    interface_hash  TEXT NOT NULL,
    version_number  INTEGER NOT NULL,
    status          TEXT DEFAULT 'candidate',
    created_at      REAL DEFAULT 0,
    last_used       REAL DEFAULT 0,
    UNIQUE(cu_id, capability)
);
CREATE INDEX IF NOT EXISTS idx_sv_cap ON survivor_versions(capability);
CREATE INDEX IF NOT EXISTS idx_sv_status ON survivor_versions(status);
CREATE INDEX IF NOT EXISTS idx_sv_interface ON survivor_versions(interface_hash);

CREATE TABLE IF NOT EXISTS survivor_rankings (
    cu_id           TEXT PRIMARY KEY,
    capability      TEXT NOT NULL,
    rank_score      REAL DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    total_runs      INTEGER DEFAULT 0,
    avg_latency_ms  REAL DEFAULT 0,
    p99_latency_ms  REAL DEFAULT 0,
    verified        INTEGER DEFAULT 0,
    usage_count     INTEGER DEFAULT 0,
    compatibility_score REAL DEFAULT 0,
    last_ranked     REAL DEFAULT 0,
    FOREIGN KEY (cu_id) REFERENCES survivor_versions(cu_id)
);
CREATE INDEX IF NOT EXISTS idx_sr_cap ON survivor_rankings(capability);
CREATE INDEX IF NOT EXISTS idx_sr_rank ON survivor_rankings(rank_score DESC);

CREATE TABLE IF NOT EXISTS survivor_graph (
    edge_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    capability      TEXT NOT NULL,
    replaced_cu     TEXT NOT NULL,
    by_cu           TEXT NOT NULL,
    reason          TEXT,
    timestamp       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sg_cap ON survivor_graph(capability);

CREATE TABLE IF NOT EXISTS survivor_pruning_log (
    prune_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    capability      TEXT NOT NULL,
    pruned_cu_id    TEXT NOT NULL,
    rank_score      REAL,
    reason          TEXT,
    timestamp       REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS survivor_interface_cache (
    interface_hash  TEXT PRIMARY KEY,
    capability      TEXT NOT NULL,
    arg_names       TEXT,
    arg_count       INTEGER,
    return_count    INTEGER,
    has_yield       INTEGER,
    has_async       INTEGER,
    dep_count       INTEGER
);
"""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "survivor_db": DB.SURVIVOR_RANKING_DB,
            "cu_db": DB.COMPUTATION_UNITS_DB,
            "conn": None,
            "cu_conn": None,
            "prune_threshold": 0.3,
            "default_keep_top_n": 5,
            "stats": {
                "registered": 0,
                "promoted": 0,
                "pruned": 0,
                "queries": 0,
                "best_served": 0,
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

    def _CheckCuId(self, cu_id):
        if not isinstance(cu_id, str) or not cu_id:
            return self._err("INVALID_CU_ID", "cu_id must be a non-empty string")
        return None

    def _CheckCapability(self, capability):
        if not isinstance(capability, str) or not capability:
            return self._err("INVALID_CAPABILITY", "capability must be a non-empty string")
        return None

    def _Conn(self):
        if self.state["conn"] is None:
            self.state["conn"] = sqlite3.connect(self.state["survivor_db"])
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _CuConn(self):
        if self.state["cu_conn"] is None:
            self.state["cu_conn"] = sqlite3.connect(self.state["cu_db"])
            self.state["cu_conn"].row_factory = sqlite3.Row
            self.state["cu_conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["cu_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["survivor_db"])
        conn.executescript(self.SCHEMA_SURVIVOR)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "register": self.Register,
            "register_all": self.RegisterAll,
            "best": self.Best,
            "top_n": self.TopN,
            "promote": self.Promote,
            "record_run": self.RecordRun,
            "prune": self.Prune,
            "evolution": self.Evolution,
            "compatibility": self.Compatibility,
            "rankings": self.Rankings,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
            "batch_record": self.BatchRecord,
            "head_to_head": self.HeadToHead,
            "decay": self.Decay,
            "reset_capability": self.ResetCapability,
            "import_rankings": self.ImportRankings,
            "export_rankings": self.ExportRankings,
            "health": self.Health,
            "lineage": self.Lineage,
            "stats_detail": self.StatsDetail,
            "merge_capabilities": self.MergeCapabilities,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

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
        if self.state.get("cu_conn") is not None:
            try:
                self.state["cu_conn"].close()
            except Exception:
                pass
            self.state["cu_conn"] = None
        return (1, {"closed": True}, None)

    # -----------------------------------------------------------------------
    # INTERFACE HASH — compatibility key
    # -----------------------------------------------------------------------

    def _InterfaceHash(self, cu_id):
        cu_conn = self._CuConn()
        cu = cu_conn.execute(
            "SELECT method_name, arg_names, arg_count, return_count, "
            "has_yield, has_async FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return None, None

        deps = cu_conn.execute(
            "SELECT COUNT(*) FROM cu_dependencies WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()[0]

        interface_data = {
            "method_name": cu["method_name"],
            "arg_count": cu["arg_count"],
            "return_count": cu["return_count"],
            "has_yield": cu["has_yield"],
            "has_async": cu["has_async"],
            "dep_count": deps,
        }
        h = hashlib.sha256(
            json.dumps(interface_data, sort_keys=True).encode()
        ).hexdigest()
        return h, interface_data

    # -----------------------------------------------------------------------
    # REGISTER — add a CU as a candidate version
    # -----------------------------------------------------------------------

    def Register(self, params):
        cu_id = self._p(params, "cu_id")
        err = self._CheckCuId(cu_id)
        if err is not None:
            return err

        cu_conn = self._CuConn()
        cu = cu_conn.execute(
            "SELECT method_name FROM computation_units WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not cu:
            return self._err("CU_NOT_FOUND", cu_id)

        capability = self._p(params, "capability", cu["method_name"])
        err = self._CheckCapability(capability)
        if err is not None:
            return err
        interface_hash, interface_data = self._InterfaceHash(cu_id)
        if not interface_hash:
            return self._err("NO_INTERFACE", "could not compute interface hash")

        conn = self._Conn()
        existing = conn.execute(
            "SELECT version_number FROM survivor_versions "
            "WHERE capability = ? ORDER BY version_number DESC LIMIT 1",
            (capability,)
        ).fetchone()
        version_number = (existing["version_number"] + 1) if existing else 1

        try:
            conn.execute(
                "INSERT INTO survivor_versions "
                "(cu_id, capability, interface_hash, version_number, "
                "status, created_at, last_used) VALUES (?,?,?,?,?,?,?)",
                (cu_id, capability, interface_hash, version_number,
                 "candidate", time.time(), time.time())
            )
        except sqlite3.IntegrityError:
            existing_version = conn.execute(
                "SELECT sv.version_number, sv.interface_hash, sv.status, "
                "sr.rank_score, sr.verified "
                "FROM survivor_versions sv "
                "LEFT JOIN survivor_rankings sr ON sv.cu_id = sr.cu_id "
                "WHERE sv.cu_id = ? AND sv.capability = ?",
                (cu_id, capability)
            ).fetchone()
            return (1, {
                "cu_id": cu_id,
                "capability": capability,
                "version_number": existing_version["version_number"] if existing_version else version_number,
                "interface_hash": existing_version["interface_hash"][:16] if existing_version and existing_version["interface_hash"] else interface_hash[:16],
                "rank_score": existing_version["rank_score"] if existing_version and existing_version["rank_score"] is not None else 0,
                "verified": bool(existing_version["verified"]) if existing_version and existing_version["verified"] is not None else False,
                "status": "already_registered",
            }, None)

        proof = cu_conn.execute(
            "SELECT status FROM cu_proof_status WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        verified = 1 if proof and proof["status"] == "verified" else 0

        exec_stats = cu_conn.execute(
            "SELECT total_runs, total_failures, avg_latency_ms "
            "FROM cu_execution_stats WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()

        success = 0
        failure = 0
        avg_lat = 0
        total_runs = 0
        if exec_stats:
            total_runs = exec_stats["total_runs"]
            failure = exec_stats["total_failures"]
            success = total_runs - failure
            avg_lat = exec_stats["avg_latency_ms"] or 0

        rank = self._ComputeRank(success, failure, avg_lat, verified, 0)
        compat = self._CompatibilityScore(cu_id, interface_hash)

        conn.execute(
            "INSERT OR REPLACE INTO survivor_rankings "
            "(cu_id, capability, rank_score, success_count, failure_count, "
            "total_runs, avg_latency_ms, verified, usage_count, "
            "compatibility_score, last_ranked) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (cu_id, capability, rank, success, failure, total_runs,
             avg_lat, verified, 0, compat, time.time())
        )

        if interface_data:
            conn.execute(
                "INSERT OR REPLACE INTO survivor_interface_cache "
                "(interface_hash, capability, arg_names, arg_count, "
                "return_count, has_yield, has_async, dep_count) VALUES (?,?,?,?,?,?,?,?)",
                (interface_hash, capability,
                 json.dumps(interface_data.get("arg_names", [])),
                 interface_data["arg_count"], interface_data["return_count"],
                 interface_data["has_yield"], interface_data["has_async"],
                 interface_data["dep_count"])
            )

        conn.commit()
        self.state["stats"]["registered"] += 1

        return (1, {
            "cu_id": cu_id,
            "capability": capability,
            "version_number": version_number,
            "interface_hash": interface_hash[:16],
            "rank_score": rank,
            "verified": bool(verified),
            "status": "candidate",
        }, None)

    def RegisterAll(self, params):
        cu_conn = self._CuConn()
        rows = cu_conn.execute(
            "SELECT cu_id, method_name FROM computation_units"
        ).fetchall()

        registered = 0
        skipped = 0
        for r in rows:
            ok, _, _ = self.Register({"cu_id": r["cu_id"], "capability": r["method_name"]})
            if ok:
                registered += 1
            else:
                skipped += 1

        return (1, {"registered": registered, "skipped": skipped, "total": len(rows)}, None)

    # -----------------------------------------------------------------------
    # RANK COMPUTATION
    # -----------------------------------------------------------------------

    def _ComputeRank(self, success, failure, avg_latency, verified, usage):
        total = success + failure
        if total == 0:
            success_rate = 0.5
        else:
            success_rate = success / total

        if avg_latency is None:
            avg_latency = 0
        perf_score = 1.0
        if avg_latency > 0:
            perf_score = max(0.1, 1.0 / (1.0 + avg_latency / 1000.0))

        verified_bonus = 0.5 if verified else 0.0
        usage_bonus = min(0.3, usage / 10000.0)

        rank = (success_rate * 4.0) + (perf_score * 2.0) + verified_bonus + usage_bonus
        return round(rank, 4)

    def _CompatibilityScore(self, cu_id, interface_hash):
        conn = self._Conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM survivor_versions "
            "WHERE interface_hash = ? AND cu_id != ?",
            (interface_hash, cu_id)
        ).fetchone()[0]
        return round(min(1.0, count / 10.0), 4)

    # -----------------------------------------------------------------------
    # BEST — give me the highest-ranked survivor for a capability
    # -----------------------------------------------------------------------

    def Best(self, params):
        capability = self._p(params, "capability")
        err = self._CheckCapability(capability)
        if err is not None:
            return err

        interface_hash = self._p(params, "interface_hash")
        conn = self._Conn()
        self.state["stats"]["queries"] += 1

        if interface_hash:
            row = conn.execute(
                "SELECT sr.cu_id, sr.capability, sr.rank_score, "
                "sr.success_count, sr.failure_count, sr.avg_latency_ms, "
                "sr.verified, sr.usage_count, sr.compatibility_score, "
                "sv.version_number, sv.status "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sr.capability = ? AND sv.interface_hash = ? "
                "AND sv.status IN ('survivor', 'candidate', 'promoted') "
                "ORDER BY sr.rank_score DESC LIMIT 1",
                (capability, interface_hash)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT sr.cu_id, sr.capability, sr.rank_score, "
                "sr.success_count, sr.failure_count, sr.avg_latency_ms, "
                "sr.verified, sr.usage_count, sr.compatibility_score, "
                "sv.version_number, sv.status "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sr.capability = ? "
                "AND sv.status IN ('survivor', 'candidate', 'promoted') "
                "ORDER BY sr.rank_score DESC LIMIT 1",
                (capability,)
            ).fetchone()

        if not row:
            return (1, {"capability": capability, "found": False}, None)

        conn.execute(
            "UPDATE survivor_versions SET last_used = ? WHERE cu_id = ?",
            (time.time(), row["cu_id"])
        )
        conn.execute(
            "UPDATE survivor_rankings SET usage_count = usage_count + 1 WHERE cu_id = ?",
            (row["cu_id"],)
        )
        conn.commit()
        self.state["stats"]["best_served"] += 1

        return (1, {
            "capability": capability,
            "found": True,
            "cu_id": row["cu_id"],
            "rank_score": row["rank_score"],
            "version_number": row["version_number"],
            "status": row["status"],
            "success": row["success_count"],
            "failure": row["failure_count"],
            "avg_latency_ms": row["avg_latency_ms"],
            "verified": bool(row["verified"]),
            "usage_count": row["usage_count"],
            "compatibility": row["compatibility_score"],
        }, None)

    def TopN(self, params):
        capability = self._p(params, "capability")
        err = self._CheckCapability(capability)
        if err is not None:
            return err
        n = self._p(params, "n", 5)
        if not isinstance(n, int) or n < 0:
            return self._err("INVALID_N", "n must be a non-negative integer")

        conn = self._Conn()
        rows = conn.execute(
            "SELECT sr.cu_id, sr.rank_score, sr.success_count, sr.failure_count, "
            "sr.avg_latency_ms, sr.verified, sr.usage_count, sv.version_number, sv.status "
            "FROM survivor_rankings sr "
            "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
            "WHERE sr.capability = ? AND sv.status != 'pruned' "
            "ORDER BY sr.rank_score DESC LIMIT ?",
            (capability, n)
        ).fetchall()

        return (1, {
            "capability": capability,
            "count": len(rows),
            "survivors": [{
                "cu_id": r["cu_id"],
                "rank": r["rank_score"],
                "version": r["version_number"],
                "status": r["status"],
                "success": r["success_count"],
                "failure": r["failure_count"],
                "avg_latency": r["avg_latency_ms"],
                "verified": bool(r["verified"]),
                "usage": r["usage_count"],
            } for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # PROMOTE — mark a version as the current best survivor
    # -----------------------------------------------------------------------

    def Promote(self, params):
        cu_id = self._p(params, "cu_id")
        err = self._CheckCuId(cu_id)
        if err is not None:
            return err
        reason = self._p(params, "reason", "manual promotion")

        conn = self._Conn()
        ver = conn.execute(
            "SELECT capability, version_number FROM survivor_versions WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not ver:
            return self._err("NOT_REGISTERED", cu_id)

        conn.execute(
            "UPDATE survivor_versions SET status = 'promoted' WHERE cu_id = ?",
            (cu_id,)
        )

        current_best = conn.execute(
            "SELECT sr.cu_id FROM survivor_rankings sr "
            "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
            "WHERE sr.capability = ? AND sv.status = 'promoted' AND sr.cu_id != ? "
            "ORDER BY sr.rank_score DESC LIMIT 1",
            (ver["capability"], cu_id)
        ).fetchone()

        if current_best:
            conn.execute(
                "UPDATE survivor_versions SET status = 'survivor' WHERE cu_id = ?",
                (current_best["cu_id"],)
            )
            conn.execute(
                "INSERT INTO survivor_graph (capability, replaced_cu, by_cu, reason, timestamp) "
                "VALUES (?,?,?,?,?)",
                (ver["capability"], current_best["cu_id"], cu_id, reason, time.time())
            )

        conn.commit()
        self.state["stats"]["promoted"] += 1

        return (1, {
            "cu_id": cu_id,
            "capability": ver["capability"],
            "version": ver["version_number"],
            "status": "promoted",
            "replaced": current_best["cu_id"] if current_best else None,
            "reason": reason,
        }, None)

    # -----------------------------------------------------------------------
    # RECORD RUN — update execution stats for a CU
    # -----------------------------------------------------------------------

    def RecordRun(self, params):
        cu_id = self._p(params, "cu_id")
        err = self._CheckCuId(cu_id)
        if err is not None:
            return err
        success = self._p(params, "success", True)
        duration_ms = self._p(params, "duration_ms", 0)

        conn = self._Conn()
        existing = conn.execute(
            "SELECT success_count, failure_count, total_runs, avg_latency_ms, "
            "verified, usage_count, capability "
            "FROM survivor_rankings WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()

        if not existing:
            return self._err("NOT_REGISTERED", cu_id)

        sc = existing["success_count"] + (1 if success else 0)
        fc = existing["failure_count"] + (0 if success else 1)
        tr = existing["total_runs"] + 1
        prev_avg = existing["avg_latency_ms"] or 0
        new_avg = (prev_avg * (tr - 1) + duration_ms) / tr

        rank = self._ComputeRank(sc, fc, new_avg, existing["verified"], existing["usage_count"])

        conn.execute(
            "UPDATE survivor_rankings SET success_count = ?, failure_count = ?, "
            "total_runs = ?, avg_latency_ms = ?, rank_score = ?, last_ranked = ? "
            "WHERE cu_id = ?",
            (sc, fc, tr, new_avg, rank, time.time(), cu_id)
        )
        conn.commit()

        return (1, {
            "cu_id": cu_id,
            "rank_score": rank,
            "success": sc,
            "failure": fc,
            "total_runs": tr,
            "avg_latency": round(new_avg, 2),
        }, None)

    # -----------------------------------------------------------------------
    # PRUNE — evolutionary selection: remove weak versions
    # -----------------------------------------------------------------------

    def Prune(self, params):
        capability = self._p(params, "capability")
        err = self._CheckCapability(capability)
        if err is not None:
            return err
        keep_top_n = self._p(params, "keep_top_n", self.state["default_keep_top_n"])
        threshold = self._p(params, "threshold", self.state["prune_threshold"])

        conn = self._Conn()
        rows = conn.execute(
            "SELECT sr.cu_id, sr.rank_score, sr.success_count, sr.failure_count, "
            "sv.version_number, sv.status "
            "FROM survivor_rankings sr "
            "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
            "WHERE sr.capability = ? AND sv.status != 'pruned' "
            "ORDER BY sr.rank_score DESC",
            (capability,)
        ).fetchall()

        if len(rows) <= keep_top_n:
            return (1, {
                "capability": capability,
                "total_versions": len(rows),
                "kept": len(rows),
                "pruned": 0,
                "threshold": threshold,
                "message": "below keep_top_n threshold",
            }, None)

        to_prune = rows[keep_top_n:]
        pruned = 0
        for r in to_prune:
            if r["rank_score"] < threshold:
                conn.execute(
                    "UPDATE survivor_versions SET status = 'pruned' WHERE cu_id = ?",
                    (r["cu_id"],)
                )
                conn.execute(
                    "INSERT INTO survivor_pruning_log "
                    "(capability, pruned_cu_id, rank_score, reason, timestamp) "
                    "VALUES (?,?,?,?,?)",
                    (capability, r["cu_id"], r["rank_score"],
                     f"rank {r['rank_score']} below threshold {threshold}", time.time())
                )
                pruned += 1

        conn.commit()
        self.state["stats"]["pruned"] += pruned

        return (1, {
            "capability": capability,
            "total_versions": len(rows),
            "kept": len(rows) - pruned,
            "pruned": pruned,
            "threshold": threshold,
        }, None)

    # -----------------------------------------------------------------------
    # EVOLUTION — show the version tree for a capability
    # -----------------------------------------------------------------------

    def Evolution(self, params):
        capability = self._p(params, "capability")
        if not capability:
            return self._err("NO_CAPABILITY", "capability required")

        conn = self._Conn()

        versions = conn.execute(
            "SELECT sv.cu_id, sv.version_number, sv.status, sv.created_at, "
            "sr.rank_score, sr.success_count, sr.failure_count, "
            "sr.avg_latency_ms, sr.verified, sr.usage_count "
            "FROM survivor_versions sv "
            "LEFT JOIN survivor_rankings sr ON sv.cu_id = sr.cu_id "
            "WHERE sv.capability = ? ORDER BY sv.version_number",
            (capability,)
        ).fetchall()

        replacements = conn.execute(
            "SELECT replaced_cu, by_cu, reason, timestamp "
            "FROM survivor_graph WHERE capability = ? ORDER BY timestamp",
            (capability,)
        ).fetchall()

        pruned = conn.execute(
            "SELECT pruned_cu_id, rank_score, reason, timestamp "
            "FROM survivor_pruning_log WHERE capability = ? ORDER BY timestamp",
            (capability,)
        ).fetchall()

        return (1, {
            "capability": capability,
            "total_versions": len(versions),
            "active": sum(1 for v in versions if v["status"] != "pruned"),
            "pruned": len(pruned),
            "versions": [{
                "cu_id": v["cu_id"],
                "version": v["version_number"],
                "status": v["status"],
                "rank": v["rank_score"] if v["rank_score"] else 0,
                "success": v["success_count"] if v["success_count"] else 0,
                "failure": v["failure_count"] if v["failure_count"] else 0,
                "avg_latency": v["avg_latency_ms"] if v["avg_latency_ms"] else 0,
                "verified": bool(v["verified"]) if v["verified"] else False,
                "usage": v["usage_count"] if v["usage_count"] else 0,
            } for v in versions],
            "replacements": [{
                "replaced": r["replaced_cu"],
                "by": r["by_cu"],
                "reason": r["reason"],
            } for r in replacements],
            "pruned_log": [{
                "cu_id": p["pruned_cu_id"],
                "rank": p["rank_score"],
                "reason": p["reason"],
            } for p in pruned],
        }, None)

    # -----------------------------------------------------------------------
    # COMPATIBILITY — find CUs with compatible interfaces
    # -----------------------------------------------------------------------

    def Compatibility(self, params):
        cu_id = self._p(params, "cu_id")
        if not cu_id:
            return self._err("NO_CU_ID", "cu_id required")

        interface_hash, _ = self._InterfaceHash(cu_id)
        if not interface_hash:
            return self._err("NO_INTERFACE", "could not compute interface hash")

        conn = self._Conn()
        rows = conn.execute(
            "SELECT sv.cu_id, sv.capability, sv.version_number, sv.status, "
            "sr.rank_score, sr.success_count, sr.failure_count "
            "FROM survivor_versions sv "
            "LEFT JOIN survivor_rankings sr ON sv.cu_id = sr.cu_id "
            "WHERE sv.interface_hash = ? AND sv.cu_id != ? AND sv.status != 'pruned' "
            "ORDER BY sr.rank_score DESC",
            (interface_hash, cu_id)
        ).fetchall()

        return (1, {
            "cu_id": cu_id,
            "interface_hash": interface_hash[:16],
            "compatible_count": len(rows),
            "compatible": [{
                "cu_id": r["cu_id"],
                "capability": r["capability"],
                "version": r["version_number"],
                "status": r["status"],
                "rank": r["rank_score"] if r["rank_score"] else 0,
                "success": r["success_count"] if r["success_count"] else 0,
                "failure": r["failure_count"] if r["failure_count"] else 0,
            } for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # RANKINGS — overview of all rankings
    # -----------------------------------------------------------------------

    def Rankings(self, params):
        capability = self._p(params, "capability")
        conn = self._Conn()

        if capability:
            rows = conn.execute(
                "SELECT sr.cu_id, sr.capability, sr.rank_score, sr.success_count, "
                "sr.failure_count, sr.avg_latency_ms, sr.verified, sr.usage_count, "
                "sv.version_number, sv.status "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sr.capability = ? AND sv.status != 'pruned' "
                "ORDER BY sr.rank_score DESC",
                (capability,)
            ).fetchall()
        else:
            limit = self._p(params, "limit", 50)
            rows = conn.execute(
                "SELECT sr.cu_id, sr.capability, sr.rank_score, sr.success_count, "
                "sr.failure_count, sr.avg_latency_ms, sr.verified, sr.usage_count, "
                "sv.version_number, sv.status "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sv.status != 'pruned' "
                "ORDER BY sr.rank_score DESC LIMIT ?",
                (limit,)
            ).fetchall()

        return (1, {
            "count": len(rows),
            "rankings": [{
                "cu_id": r["cu_id"],
                "capability": r["capability"],
                "rank": r["rank_score"],
                "version": r["version_number"],
                "status": r["status"],
                "success": r["success_count"],
                "failure": r["failure_count"],
                "avg_latency": r["avg_latency_ms"],
                "verified": bool(r["verified"]),
                "usage": r["usage_count"],
            } for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # STATS / STATE / CONFIG
    # -----------------------------------------------------------------------

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "versions": conn.execute("SELECT COUNT(*) FROM survivor_versions").fetchone()[0],
            "rankings": conn.execute("SELECT COUNT(*) FROM survivor_rankings").fetchone()[0],
            "promoted": conn.execute("SELECT COUNT(*) FROM survivor_versions WHERE status = 'promoted'").fetchone()[0],
            "survivors": conn.execute("SELECT COUNT(*) FROM survivor_versions WHERE status = 'survivor'").fetchone()[0],
            "candidates": conn.execute("SELECT COUNT(*) FROM survivor_versions WHERE status = 'candidate'").fetchone()[0],
            "pruned": conn.execute("SELECT COUNT(*) FROM survivor_versions WHERE status = 'pruned'").fetchone()[0],
            "replacements": conn.execute("SELECT COUNT(*) FROM survivor_graph").fetchone()[0],
            "capabilities": conn.execute("SELECT COUNT(DISTINCT capability) FROM survivor_versions").fetchone()[0],
        }
        return (1, {"counts": counts, "stats": self.state["stats"]}, None)

    def read_state(self, params=None):
        safe = dict(self.state)
        safe.pop("conn", None)
        safe.pop("cu_conn", None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)

    # -----------------------------------------------------------------------
    # BATCH RECORD — record multiple execution runs in one call
    # -----------------------------------------------------------------------

    def BatchRecord(self, params):
        runs = self._p(params, "runs")
        if not isinstance(runs, list) or not runs:
            return self._err("NO_RUNS", "runs must be a non-empty list")

        recorded = 0
        updated_ranks = []
        for entry in runs:
            if not isinstance(entry, dict):
                continue
            ok, data, err = self.RecordRun(entry)
            if ok:
                recorded += 1
                updated_ranks.append({
                    "cu_id": data["cu_id"],
                    "rank_score": data["rank_score"],
                })
            else:
                updated_ranks.append({
                    "cu_id": self._p(entry, "cu_id"),
                    "error": err[1] if err else "unknown",
                })

        return (1, {"recorded": recorded, "updated_ranks": updated_ranks}, None)

    # -----------------------------------------------------------------------
    # HEAD TO HEAD — compare two survivors directly
    # -----------------------------------------------------------------------

    def _SurvivorSummary(self, cu_id):
        conn = self._Conn()
        row = conn.execute(
            "SELECT sr.cu_id, sr.capability, sr.rank_score, "
            "sr.success_count, sr.failure_count, sr.avg_latency_ms, "
            "sr.verified, sr.usage_count, "
            "sv.version_number, sv.status "
            "FROM survivor_rankings sr "
            "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
            "WHERE sr.cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "cu_id": row["cu_id"],
            "capability": row["capability"],
            "rank_score": row["rank_score"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "avg_latency_ms": row["avg_latency_ms"],
            "verified": bool(row["verified"]),
            "usage_count": row["usage_count"],
            "version_number": row["version_number"],
            "status": row["status"],
        }

    def HeadToHead(self, params):
        cu_id_a = self._p(params, "cu_id_a")
        err = self._CheckCuId(cu_id_a)
        if err is not None:
            return err
        cu_id_b = self._p(params, "cu_id_b")
        err = self._CheckCuId(cu_id_b)
        if err is not None:
            return err

        a = self._SurvivorSummary(cu_id_a)
        b = self._SurvivorSummary(cu_id_b)
        if not a:
            return self._err("NOT_REGISTERED", cu_id_a)
        if not b:
            return self._err("NOT_REGISTERED", cu_id_b)

        rank_a = a["rank_score"] if a["rank_score"] is not None else 0
        rank_b = b["rank_score"] if b["rank_score"] is not None else 0
        if rank_a >= rank_b:
            winner = "a"
            margin = round(rank_a - rank_b, 4)
        else:
            winner = "b"
            margin = round(rank_b - rank_a, 4)

        return (1, {
            "a": a,
            "b": b,
            "winner": winner,
            "margin": margin,
        }, None)

    # -----------------------------------------------------------------------
    # DECAY — apply time decay to rank scores
    # -----------------------------------------------------------------------

    def Decay(self, params):
        decay_factor = self._p(params, "decay_factor", 0.95)
        if not isinstance(decay_factor, (int, float)):
            return self._err("INVALID_DECAY_FACTOR", "decay_factor must be numeric")
        if decay_factor <= 0 or decay_factor > 1:
            return self._err("INVALID_DECAY_FACTOR", "decay_factor must be in (0, 1]")
        min_usage = self._p(params, "min_usage", 10)
        if not isinstance(min_usage, int) or min_usage < 0:
            return self._err("INVALID_MIN_USAGE", "min_usage must be a non-negative integer")

        conn = self._Conn()
        rows = conn.execute(
            "SELECT cu_id, rank_score, usage_count FROM survivor_rankings "
            "WHERE usage_count > ?",
            (min_usage,)
        ).fetchall()

        decayed = 0
        for r in rows:
            new_score = round((r["rank_score"] or 0) * decay_factor, 4)
            conn.execute(
                "UPDATE survivor_rankings SET rank_score = ?, last_ranked = ? "
                "WHERE cu_id = ?",
                (new_score, time.time(), r["cu_id"])
            )
            decayed += 1

        conn.commit()
        return (1, {"decayed": decayed, "factor": decay_factor}, None)

    # -----------------------------------------------------------------------
    # RESET CAPABILITY — delete all rankings and versions for a capability
    # -----------------------------------------------------------------------

    def ResetCapability(self, params):
        capability = self._p(params, "capability")
        err = self._CheckCapability(capability)
        if err is not None:
            return err

        conn = self._Conn()
        conn.execute(
            "DELETE FROM survivor_versions WHERE capability = ?",
            (capability,)
        )
        conn.execute(
            "DELETE FROM survivor_rankings WHERE capability = ?",
            (capability,)
        )
        conn.execute(
            "DELETE FROM survivor_graph WHERE capability = ?",
            (capability,)
        )
        conn.execute(
            "DELETE FROM survivor_pruning_log WHERE capability = ?",
            (capability,)
        )
        conn.commit()

        return (1, {"reset": True, "capability": capability}, None)

    # -----------------------------------------------------------------------
    # EXPORT RANKINGS — export all survivor data as JSON
    # -----------------------------------------------------------------------

    def ExportRankings(self, params):
        capability = self._p(params, "capability")
        conn = self._Conn()

        if capability:
            err = self._CheckCapability(capability)
            if err is not None:
                return err
            versions = conn.execute(
                "SELECT cu_id, capability, interface_hash, version_number, "
                "status, created_at, last_used FROM survivor_versions "
                "WHERE capability = ?",
                (capability,)
            ).fetchall()
            rankings = conn.execute(
                "SELECT cu_id, capability, rank_score, success_count, "
                "failure_count, total_runs, avg_latency_ms, p99_latency_ms, "
                "verified, usage_count, compatibility_score, last_ranked "
                "FROM survivor_rankings WHERE capability = ?",
                (capability,)
            ).fetchall()
            graph = conn.execute(
                "SELECT capability, replaced_cu, by_cu, reason, timestamp "
                "FROM survivor_graph WHERE capability = ?",
                (capability,)
            ).fetchall()
            pruning = conn.execute(
                "SELECT capability, pruned_cu_id, rank_score, reason, timestamp "
                "FROM survivor_pruning_log WHERE capability = ?",
                (capability,)
            ).fetchall()
        else:
            versions = conn.execute(
                "SELECT cu_id, capability, interface_hash, version_number, "
                "status, created_at, last_used FROM survivor_versions"
            ).fetchall()
            rankings = conn.execute(
                "SELECT cu_id, capability, rank_score, success_count, "
                "failure_count, total_runs, avg_latency_ms, p99_latency_ms, "
                "verified, usage_count, compatibility_score, last_ranked "
                "FROM survivor_rankings"
            ).fetchall()
            graph = conn.execute(
                "SELECT capability, replaced_cu, by_cu, reason, timestamp "
                "FROM survivor_graph"
            ).fetchall()
            pruning = conn.execute(
                "SELECT capability, pruned_cu_id, rank_score, reason, timestamp "
                "FROM survivor_pruning_log"
            ).fetchall()

        payload = {
            "versions": [dict(v) for v in versions],
            "rankings": [dict(r) for r in rankings],
            "graph_edges": [dict(g) for g in graph],
            "pruning_log": [dict(p) for p in pruning],
        }
        return (1, json.dumps(payload, default=str), None)

    # -----------------------------------------------------------------------
    # IMPORT RANKINGS — import survivor rankings from a JSON string
    # -----------------------------------------------------------------------

    def ImportRankings(self, params):
        json_str = self._p(params, "json")
        if not isinstance(json_str, str) or not json_str:
            return self._err("NO_JSON", "json string required")

        try:
            payload = json.loads(json_str)
        except (ValueError, TypeError) as e:
            return self._err("BAD_JSON", str(e))

        if not isinstance(payload, dict):
            return self._err("BAD_JSON", "payload must be a JSON object")

        conn = self._Conn()
        versions_n = 0
        rankings_n = 0
        graph_n = 0

        for v in payload.get("versions", []):
            if not isinstance(v, dict):
                continue
            conn.execute(
                "INSERT OR REPLACE INTO survivor_versions "
                "(cu_id, capability, interface_hash, version_number, "
                "status, created_at, last_used) VALUES (?,?,?,?,?,?,?)",
                (
                    v.get("cu_id"),
                    v.get("capability"),
                    v.get("interface_hash"),
                    v.get("version_number", 1),
                    v.get("status", "candidate"),
                    v.get("created_at", 0),
                    v.get("last_used", 0),
                )
            )
            versions_n += 1

        for r in payload.get("rankings", []):
            if not isinstance(r, dict):
                continue
            conn.execute(
                "INSERT OR REPLACE INTO survivor_rankings "
                "(cu_id, capability, rank_score, success_count, failure_count, "
                "total_runs, avg_latency_ms, p99_latency_ms, verified, "
                "usage_count, compatibility_score, last_ranked) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r.get("cu_id"),
                    r.get("capability"),
                    r.get("rank_score", 0),
                    r.get("success_count", 0),
                    r.get("failure_count", 0),
                    r.get("total_runs", 0),
                    r.get("avg_latency_ms", 0),
                    r.get("p99_latency_ms", 0),
                    r.get("verified", 0),
                    r.get("usage_count", 0),
                    r.get("compatibility_score", 0),
                    r.get("last_ranked", 0),
                )
            )
            rankings_n += 1

        for g in payload.get("graph_edges", []):
            if not isinstance(g, dict):
                continue
            conn.execute(
                "INSERT INTO survivor_graph "
                "(capability, replaced_cu, by_cu, reason, timestamp) "
                "VALUES (?,?,?,?,?)",
                (
                    g.get("capability"),
                    g.get("replaced_cu"),
                    g.get("by_cu"),
                    g.get("reason"),
                    g.get("timestamp", 0),
                )
            )
            graph_n += 1

        conn.commit()
        return (1, {
            "imported": {
                "versions": versions_n,
                "rankings": rankings_n,
                "graph_edges": graph_n,
            }
        }, None)

    # -----------------------------------------------------------------------
    # HEALTH — health check of the survivor ranking system
    # -----------------------------------------------------------------------

    def Health(self, params=None):
        conn = self._Conn()
        total_versions = conn.execute(
            "SELECT COUNT(*) FROM survivor_versions"
        ).fetchone()[0]
        total_rankings = conn.execute(
            "SELECT COUNT(*) FROM survivor_rankings"
        ).fetchone()[0]
        total_graph = conn.execute(
            "SELECT COUNT(*) FROM survivor_graph"
        ).fetchone()[0]
        total_pruned = conn.execute(
            "SELECT COUNT(*) FROM survivor_versions WHERE status = 'pruned'"
        ).fetchone()[0]

        orphaned_rankings = conn.execute(
            "SELECT COUNT(*) FROM survivor_rankings sr "
            "WHERE NOT EXISTS (SELECT 1 FROM survivor_versions sv "
            "WHERE sv.cu_id = sr.cu_id)"
        ).fetchone()[0]
        orphaned_versions = conn.execute(
            "SELECT COUNT(*) FROM survivor_versions sv "
            "WHERE NOT EXISTS (SELECT 1 FROM survivor_rankings sr "
            "WHERE sr.cu_id = sv.cu_id)"
        ).fetchone()[0]

        low_diversity = conn.execute(
            "SELECT capability, COUNT(*) AS cnt FROM survivor_versions "
            "GROUP BY capability HAVING cnt = 1"
        ).fetchall()
        low_diversity_caps = [r["capability"] for r in low_diversity]

        avg_row = conn.execute(
            "SELECT AVG(rank_score) FROM survivor_rankings"
        ).fetchone()
        avg_rank = avg_row[0] if avg_row and avg_row[0] is not None else 0

        top_caps = conn.execute(
            "SELECT capability, COUNT(*) AS cnt FROM survivor_versions "
            "GROUP BY capability ORDER BY cnt DESC LIMIT 5"
        ).fetchall()

        issues = []
        if orphaned_rankings > 0:
            issues.append("orphaned_rankings: ranking exists without version")
        if orphaned_versions > 0:
            issues.append("orphaned_versions: version exists without ranking")
        if low_diversity_caps:
            issues.append("low_diversity: capabilities with only one version")
        healthy = len(issues) == 0

        stats = {
            "total_versions": total_versions,
            "total_rankings": total_rankings,
            "total_graph_edges": total_graph,
            "total_pruned": total_pruned,
            "orphaned_rankings": orphaned_rankings,
            "orphaned_versions": orphaned_versions,
            "low_diversity_capabilities": len(low_diversity_caps),
            "avg_rank_score": round(avg_rank, 4),
            "top_5_capabilities": [
                {"capability": r["capability"], "version_count": r["cnt"]}
                for r in top_caps
            ],
        }
        return (1, {"healthy": healthy, "stats": stats, "issues": issues}, None)

    # -----------------------------------------------------------------------
    # LINEAGE — show the full version lineage of a CU
    # -----------------------------------------------------------------------

    def Lineage(self, params):
        cu_id = self._p(params, "cu_id")
        err = self._CheckCuId(cu_id)
        if err is not None:
            return err

        conn = self._Conn()
        ver = conn.execute(
            "SELECT cu_id, capability, version_number, status, created_at "
            "FROM survivor_versions WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()
        if not ver:
            return self._err("NOT_REGISTERED", cu_id)

        replaced = conn.execute(
            "SELECT replaced_cu, reason, timestamp "
            "FROM survivor_graph WHERE by_cu = ? ORDER BY timestamp",
            (cu_id,)
        ).fetchall()
        replaced_by = conn.execute(
            "SELECT by_cu, reason, timestamp "
            "FROM survivor_graph WHERE replaced_cu = ? ORDER BY timestamp",
            (cu_id,)
        ).fetchall()
        rank_row = conn.execute(
            "SELECT rank_score, success_count, failure_count, total_runs, "
            "avg_latency_ms, verified, usage_count "
            "FROM survivor_rankings WHERE cu_id = ?",
            (cu_id,)
        ).fetchone()

        rank = None
        if rank_row:
            rank = {
                "rank_score": rank_row["rank_score"],
                "success_count": rank_row["success_count"],
                "failure_count": rank_row["failure_count"],
                "total_runs": rank_row["total_runs"],
                "avg_latency_ms": rank_row["avg_latency_ms"],
                "verified": bool(rank_row["verified"]),
                "usage_count": rank_row["usage_count"],
            }

        return (1, {
            "cu_id": cu_id,
            "capability": ver["capability"],
            "version": ver["version_number"],
            "status": ver["status"],
            "created_at": ver["created_at"],
            "replaced": [{
                "cu_id": r["replaced_cu"],
                "reason": r["reason"],
                "timestamp": r["timestamp"],
            } for r in replaced],
            "replaced_by": [{
                "cu_id": r["by_cu"],
                "reason": r["reason"],
                "timestamp": r["timestamp"],
            } for r in replaced_by],
            "rank": rank,
        }, None)

    # -----------------------------------------------------------------------
    # STATS DETAIL — detailed statistics beyond stats()
    # -----------------------------------------------------------------------

    def StatsDetail(self, params=None):
        conn = self._Conn()

        caps = conn.execute(
            "SELECT capability, COUNT(*) AS cnt FROM survivor_versions "
            "GROUP BY capability"
        ).fetchall()
        per_capability = []
        for c in caps:
            cap = c["capability"]
            avg_rank = conn.execute(
                "SELECT AVG(rank_score) FROM survivor_rankings "
                "WHERE capability = ?",
                (cap,)
            ).fetchone()[0]
            top = conn.execute(
                "SELECT sr.cu_id, sr.rank_score "
                "FROM survivor_rankings sr "
                "JOIN survivor_versions sv ON sr.cu_id = sv.cu_id "
                "WHERE sr.capability = ? AND sv.status != 'pruned' "
                "ORDER BY sr.rank_score DESC LIMIT 1",
                (cap,)
            ).fetchone()
            pruned_n = conn.execute(
                "SELECT COUNT(*) FROM survivor_versions "
                "WHERE capability = ? AND status = 'pruned'",
                (cap,)
            ).fetchone()[0]
            per_capability.append({
                "capability": cap,
                "version_count": c["cnt"],
                "avg_rank": round(avg_rank, 4) if avg_rank is not None else 0,
                "top_survivor": top["cu_id"] if top else None,
                "top_rank": top["rank_score"] if top else None,
                "pruned_count": pruned_n,
            })

        total_cus = conn.execute(
            "SELECT COUNT(*) FROM survivor_rankings"
        ).fetchone()[0]
        total_runs = conn.execute(
            "SELECT COALESCE(SUM(total_runs), 0) FROM survivor_rankings"
        ).fetchone()[0]
        avg_success_row = conn.execute(
            "SELECT AVG(CASE WHEN total_runs > 0 "
            "THEN success_count * 1.0 / total_runs ELSE 0 END) "
            "FROM survivor_rankings"
        ).fetchone()
        avg_success = avg_success_row[0] if avg_success_row and avg_success_row[0] is not None else 0
        avg_lat_row = conn.execute(
            "SELECT AVG(avg_latency_ms) FROM survivor_rankings "
            "WHERE avg_latency_ms > 0"
        ).fetchone()
        avg_latency = avg_lat_row[0] if avg_lat_row and avg_lat_row[0] is not None else 0

        global_stats = {
            "total_cus": total_cus,
            "total_runs": total_runs,
            "avg_success_rate": round(avg_success, 4),
            "avg_latency": round(avg_latency, 4),
        }

        buckets = {"0_2": 0, "2_4": 0, "4_6": 0, "6_8": 0, "8_10": 0}
        score_rows = conn.execute(
            "SELECT rank_score FROM survivor_rankings"
        ).fetchall()
        for sr in score_rows:
            score = sr["rank_score"] if sr["rank_score"] is not None else 0
            if score < 2:
                buckets["0_2"] += 1
            elif score < 4:
                buckets["2_4"] += 1
            elif score < 6:
                buckets["4_6"] += 1
            elif score < 8:
                buckets["6_8"] += 1
            else:
                buckets["8_10"] += 1

        return (1, {
            "per_capability": per_capability,
            "global": global_stats,
            "distribution": buckets,
        }, None)

    # -----------------------------------------------------------------------
    # MERGE CAPABILITIES — merge all versions/rankings from one cap to another
    # -----------------------------------------------------------------------

    def MergeCapabilities(self, params):
        from_cap = self._p(params, "from_cap")
        err = self._CheckCapability(from_cap)
        if err is not None:
            return err
        to_cap = self._p(params, "to_cap")
        err = self._CheckCapability(to_cap)
        if err is not None:
            return err
        if from_cap == to_cap:
            return self._err("SAME_CAPABILITY", "from_cap and to_cap must differ")

        conn = self._Conn()
        existing = conn.execute(
            "SELECT MAX(version_number) AS max_v FROM survivor_versions "
            "WHERE capability = ?",
            (to_cap,)
        ).fetchone()
        offset = existing["max_v"] if existing and existing["max_v"] else 0

        rows = conn.execute(
            "SELECT cu_id, version_number FROM survivor_versions "
            "WHERE capability = ? ORDER BY version_number",
            (from_cap,)
        ).fetchall()
        versions_moved = 0
        for idx, r in enumerate(rows):
            new_vn = offset + idx + 1
            conn.execute(
                "UPDATE survivor_versions SET capability = ?, version_number = ? "
                "WHERE cu_id = ?",
                (to_cap, new_vn, r["cu_id"])
            )
            versions_moved += 1

        rankings_cur = conn.execute(
            "SELECT COUNT(*) FROM survivor_rankings WHERE capability = ?",
            (from_cap,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE survivor_rankings SET capability = ? WHERE capability = ?",
            (to_cap, from_cap)
        )
        rankings_moved = rankings_cur

        conn.execute(
            "UPDATE survivor_graph SET capability = ? WHERE capability = ?",
            (to_cap, from_cap)
        )
        conn.execute(
            "UPDATE survivor_pruning_log SET capability = ? WHERE capability = ?",
            (to_cap, from_cap)
        )

        conn.commit()
        return (1, {
            "merged": True,
            "versions_moved": versions_moved,
            "rankings_moved": rankings_moved,
        }, None)


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== SURVIVOR RANKING ===")
    print()

    from computation_unit import ComputationUnit

    # First, ingest some CUs with the same capability but different versions
    cu = ComputationUnit()

    print("--- Step 1: Ingest 3 versions of 'parse_json' ---")

    # v1: basic, slow, fails on edge cases
    ok1, d1, _ = cu.Run("ingest_method", {
        "method_name": "parse_json",
        "source_code": (
            "def parse_json(self, params):\n"
            "    import json\n"
            "    text = params.get('text', '')\n"
            "    return (1, json.loads(text), None)\n"
        ),
        "origin_class": "ParserV1",
        "arg_names": ["self", "params"],
    })
    if ok1:
        print(f"  v1: {d1['cu_id'][:20]}...  status={d1['status']}")

    # v2: better error handling
    ok2, d2, _ = cu.Run("ingest_method", {
        "method_name": "parse_json",
        "source_code": (
            "def parse_json(self, params):\n"
            "    import json\n"
            "    text = params.get('text', '')\n"
            "    try:\n"
            "        return (1, json.loads(text), None)\n"
            "    except json.JSONDecodeError as e:\n"
            "        return (0, None, ('PARSE_ERROR', str(e), 0))\n"
        ),
        "origin_class": "ParserV2",
        "arg_names": ["self", "params"],
    })
    if ok2:
        print(f"  v2: {d2['cu_id'][:20]}...  status={d2['status']}")

    # v3: fastest, with validation
    ok3, d3, _ = cu.Run("ingest_method", {
        "method_name": "parse_json",
        "source_code": (
            "def parse_json(self, params):\n"
            "    import json\n"
            "    text = params.get('text', '{}')\n"
            "    if not text:\n"
            "        return (0, None, ('EMPTY', 'no text', 0))\n"
            "    try:\n"
            "        data = json.loads(text)\n"
            "        return (1, data, None)\n"
            "    except Exception as e:\n"
            "        return (0, None, ('PARSE_ERROR', str(e), 0))\n"
        ),
        "origin_class": "ParserV3",
        "arg_names": ["self", "params"],
    })
    if ok3:
        print(f"  v3: {d3['cu_id'][:20]}...  status={d3['status']}")

    # Step 2: Register all as survivor candidates
    print()
    print("--- Step 2: Register as survivor candidates ---")
    ranking = SurvivorRanking()

    for d in [d1, d2, d3]:
        ok, reg, _ = ranking.Run("register", {"cu_id": d["cu_id"], "capability": "parse_json"})
        if ok:
            print(f"  {reg['cu_id'][:20]}...  v{reg['version_number']}  rank={reg['rank_score']}  verified={reg['verified']}")

    # Step 3: Record execution results (v1 fails, v2 ok, v3 ok + fast)
    print()
    print("--- Step 3: Record execution results ---")
    ranking.Run("record_run", {"cu_id": d1["cu_id"], "success": False, "duration_ms": 50})
    ranking.Run("record_run", {"cu_id": d1["cu_id"], "success": False, "duration_ms": 45})
    ranking.Run("record_run", {"cu_id": d1["cu_id"], "success": True, "duration_ms": 40})

    ranking.Run("record_run", {"cu_id": d2["cu_id"], "success": True, "duration_ms": 20})
    ranking.Run("record_run", {"cu_id": d2["cu_id"], "success": True, "duration_ms": 18})
    ranking.Run("record_run", {"cu_id": d2["cu_id"], "success": True, "duration_ms": 22})

    ranking.Run("record_run", {"cu_id": d3["cu_id"], "success": True, "duration_ms": 5})
    ranking.Run("record_run", {"cu_id": d3["cu_id"], "success": True, "duration_ms": 4})
    ranking.Run("record_run", {"cu_id": d3["cu_id"], "success": True, "duration_ms": 6})
    ranking.Run("record_run", {"cu_id": d3["cu_id"], "success": True, "duration_ms": 3})

    print("  v1: 1 success, 2 failures")
    print("  v2: 3 successes, 0 failures, ~20ms avg")
    print("  v3: 4 successes, 0 failures, ~4.5ms avg")

    # Step 4: Get the best survivor
    print()
    print("--- Step 4: Best survivor for 'parse_json' ---")
    ok, best, _ = ranking.Run("best", {"capability": "parse_json"})
    if ok and best.get("found"):
        print(f"  CU:        {best['cu_id'][:20]}...")
        print(f"  Rank:      {best['rank_score']}")
        print(f"  Version:   {best['version_number']}")
        print(f"  Status:    {best['status']}")
        print(f"  Success:   {best['success']}")
        print(f"  Failure:   {best['failure']}")
        print(f"  Latency:   {best['avg_latency_ms']:.1f}ms")
        print(f"  Verified:  {best['verified']}")
    else:
        print(f"  NOT FOUND")

    # Step 5: Top N
    print()
    print("--- Step 5: Top 3 survivors ---")
    ok, top, _ = ranking.Run("top_n", {"capability": "parse_json", "n": 3})
    if ok:
        for i, s in enumerate(top["survivors"]):
            print(f"  #{i+1}  {s['cu_id'][:20]}...  v{s['version']}  "
                  f"rank={s['rank']}  success={s['success']}  fail={s['failure']}  "
                  f"{s['avg_latency']:.1f}ms  status={s['status']}")

    # Step 6: Promote v3 as the current best
    print()
    print("--- Step 6: Promote v3 ---")
    ok, promo, _ = ranking.Run("promote", {
        "cu_id": d3["cu_id"],
        "reason": "fastest + zero failures + validated",
    })
    if ok:
        print(f"  Promoted:   {promo['cu_id'][:20]}...")
        print(f"  Replaced:   {promo.get('replaced', 'none')}")
        print(f"  Reason:     {promo['reason']}")

    # Step 7: Prune weak versions
    print()
    print("--- Step 7: Prune weak versions ---")
    ok, prune, _ = ranking.Run("prune", {
        "capability": "parse_json",
        "keep_top_n": 2,
        "threshold": 4.0,
    })
    if ok:
        print(f"  Total:      {prune['total_versions']}")
        print(f"  Kept:       {prune['kept']}")
        print(f"  Pruned:     {prune['pruned']}")

    # Step 8: Evolution tree
    print()
    print("--- Step 8: Evolution tree ---")
    ok, evo, _ = ranking.Run("evolution", {"capability": "parse_json"})
    if ok:
        print(f"  Total versions:  {evo['total_versions']}")
        print(f"  Active:          {evo['active']}")
        print(f"  Pruned:          {evo['pruned']}")
        print()
        for v in evo["versions"]:
            icon = "KEEP" if v["status"] != "pruned" else "DROP"
            print(f"  [{icon:4s}] v{v['version']}  {v['cu_id'][:20]}...  "
                  f"rank={v['rank']}  s={v['success']} f={v['failure']}  "
                  f"status={v['status']}")
        print()
        if evo["replacements"]:
            print("  Replacements:")
            for r in evo["replacements"]:
                print(f"    {r['replaced'][:20]}... → {r['by'][:20]}...  ({r['reason']})")

    # Step 9: Compatibility check
    print()
    print("--- Step 9: Compatibility check ---")
    ok, compat, _ = ranking.Run("compatibility", {"cu_id": d2["cu_id"]})
    if ok:
        print(f"  CU:              {compat['cu_id'][:20]}...")
        print(f"  Interface hash:  {compat['interface_hash']}")
        print(f"  Compatible:      {compat['compatible_count']}")
        for c in compat["compatible"]:
            print(f"    {c['cu_id'][:20]}...  v{c['version']}  rank={c['rank']}  status={c['status']}")

    # Step 10: Full rankings
    print()
    print("--- Step 10: All rankings ---")
    ok, ranks, _ = ranking.Run("rankings", {"capability": "parse_json"})
    if ok:
        for r in ranks["rankings"]:
            print(f"  {r['cu_id'][:20]}...  cap={r['capability']:15s}  "
                  f"rank={r['rank']:.4f}  v{r['version']}  "
                  f"s={r['success']} f={r['failure']}  status={r['status']}")

    # Step 11: Stats
    print()
    print("--- Step 11: Stats ---")
    ok, stats, _ = ranking.Run("stats", {})
    if ok:
        for k, v in stats["counts"].items():
            print(f"  {k:20s} {v}")
        print()
        for k, v in stats["stats"].items():
            print(f"  {k:20s} {v}")

    print()
    print("=== SURVIVOR RANKING DEMO COMPLETE ===")
