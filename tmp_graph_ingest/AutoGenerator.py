# [@GHOST]
# Ghost header — AutoGenerator
# Purpose: Self-writing graph evolution. Reads failures, creates fallback nodes.
# Layer: Called by DecisionEngine when nodes fail. Evolves the decision graph.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import json
import sqlite3
from Config_graph_engine import cfg


class AutoGenerator:
    """Self-writing graph. Reads failures from execution_log, creates fallback nodes."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "domain": cfg.DOMAIN,
            "promote_threshold": cfg.PROMOTE_THRESHOLD,
            "prune_threshold": cfg.PRUNE_THRESHOLD,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "auto_generate": self.AutoGenerate,
            "dedup": self.Dedup,
            "merge_runs": self.MergeRuns,
            "promote_path": self.PromotePath,
            "prune_dead": self.PruneDead,
            "metrics": self.Metrics,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def AutoGenerate(self, params):
        """Read failures from execution_log, create fallback nodes for them."""
        run_id = params.get("run_id")
        domain = params.get("domain", self.state["domain"])
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        if run_id:
            failures = cur.execute(
                "SELECT node_id, output FROM execution_log WHERE run_id=? AND status='failed'",
                (run_id,),
            ).fetchall()
        else:
            failures = cur.execute(
                "SELECT node_id, output FROM execution_log WHERE status='failed' ORDER BY log_id DESC LIMIT 20",
                (),
            ).fetchall()
        created = 0
        skipped = 0
        for node_id, output in failures:
            existing = cur.execute(
                "SELECT node_id FROM decision_nodes WHERE name=? AND node_type='fallback'",
                ("fallback_for_{nid}".format(nid=node_id),),
            ).fetchone()
            if existing:
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO decision_nodes (domain, name, node_type, payload) VALUES (?, ?, ?, ?)",
                (domain, "fallback_for_{nid}".format(nid=node_id), "fallback", json.dumps({"source_node": node_id, "error": output})),
            )
            fallback_id = cur.lastrowid
            cur.execute(
                "INSERT INTO decision_edges (from_node, to_node, condition, weight) VALUES (?, ?, ?, ?)",
                (node_id, fallback_id, "error", 0.5),
            )
            created += 1
        db.commit()
        db.close()
        return (1, {"created": created, "dedup_skipped": skipped, "total_failures": len(failures)}, None)

    def Dedup(self, params):
        """Remove duplicate fallback nodes."""
        domain = params.get("domain", self.state["domain"])
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        duplicates = cur.execute(
            "SELECT name, COUNT(*) as cnt FROM decision_nodes WHERE domain=? AND node_type='fallback' GROUP BY name HAVING cnt > 1",
            (domain,),
        ).fetchall()
        removed = 0
        for name, count in duplicates:
            ids = cur.execute(
                "SELECT node_id FROM decision_nodes WHERE domain=? AND name=? AND node_type='fallback' ORDER BY node_id",
                (domain, name),
            ).fetchall()
            keep_id = ids[0][0]
            for extra_id in ids[1:]:
                cur.execute("DELETE FROM decision_edges WHERE from_node=? OR to_node=?", (extra_id[0], extra_id[0]))
                cur.execute("DELETE FROM decision_nodes WHERE node_id=?", (extra_id[0],))
                removed += 1
        db.commit()
        db.close()
        return (1, {"duplicates_found": len(duplicates), "removed": removed}, None)

    def MergeRuns(self, params):
        """Find patterns across failed runs."""
        run_ids = params.get("run_ids", [])
        if not run_ids:
            return (0, None, "missing_param: run_ids")
        placeholders = ",".join("?" * len(run_ids))
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        patterns = cur.execute(
            "SELECT node_id, COUNT(*) as freq FROM execution_log WHERE run_id IN ({ph}) AND status='failed' GROUP BY node_id ORDER BY freq DESC".format(ph=placeholders),
            run_ids,
        ).fetchall()
        db.close()
        pattern_list = [{"node_id": p[0], "frequency": p[1]} for p in patterns]
        return (1, {"run_ids": run_ids, "patterns": pattern_list, "count": len(pattern_list)}, None)

    def PromotePath(self, params):
        """Promote weight after N successes."""
        node_id = params.get("node_id")
        threshold = params.get("threshold", self.state["promote_threshold"])
        if not node_id:
            return (0, None, "missing_param: node_id")
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        success_count = cur.execute(
            "SELECT COUNT(*) FROM execution_log WHERE node_id=? AND status='executed'",
            (node_id,),
        ).fetchone()[0]
        promoted = 0
        if success_count >= threshold:
            cur.execute(
                "UPDATE decision_edges SET weight = weight + 0.5 WHERE from_node=?",
                (node_id,),
            )
            promoted = 1
        db.commit()
        db.close()
        return (1, {"node_id": node_id, "successes": success_count, "promoted": promoted, "threshold": threshold}, None)

    def PruneDead(self, params):
        """Remove edges below threshold."""
        threshold = params.get("threshold", self.state["prune_threshold"])
        domain = params.get("domain", self.state["domain"])
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        cur.execute(
            "DELETE FROM decision_edges WHERE weight < ?",
            (threshold,),
        )
        pruned = cur.rowcount
        db.commit()
        db.close()
        return (1, {"pruned_edges": pruned, "threshold": threshold}, None)

    def Metrics(self, params):
        """Return run success/failure counts."""
        domain = params.get("domain", self.state["domain"])
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        total = cur.execute(
            "SELECT COUNT(*) FROM run_metrics WHERE domain=?", (domain,)
        ).fetchone()[0]
        successes = cur.execute(
            "SELECT COUNT(*) FROM run_metrics WHERE domain=? AND success=1", (domain,)
        ).fetchone()[0]
        failures = total - successes
        avg_duration = cur.execute(
            "SELECT AVG(duration_seconds) FROM run_metrics WHERE domain=?", (domain,)
        ).fetchone()[0]
        db.close()
        return (
            1,
            {
                "domain": domain,
                "total_runs": total,
                "successes": successes,
                "failures": failures,
                "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
                "avg_duration": round(avg_duration, 2) if avg_duration else 0,
            },
            None,
        )
