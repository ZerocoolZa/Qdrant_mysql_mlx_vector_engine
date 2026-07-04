#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_Graph/DomGraphEngine.py"
# date="2026-06-28" author="Devin" session_id="domgraph-phase1"
# context="Unified Decision Graph Engine Phase 1 — codefix domain"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="DomGraphEngine.py" domain="unified_graph" authority="DomGraphEngine"}
# [@SUMMARY]{summary="Unified decision graph engine merging DecisionEngine, ConfidenceEngine, DomSessionGraph, and GUIDecisionEngine into one VBStyle authority with domain-partitioned 5-table schema."}
# [@CLASS]{class="DomGraphEngine" domain="unified_graph" authority="single"}
# [@METHOD]{method="decide" type="command"}
# [@METHOD]{method="get_candidates" type="command"}
# [@METHOD]{method="filter" type="command"}
# [@METHOD]{method="when_rules" type="command"}
# [@METHOD]{method="resolve_conflicts" type="command"}
# [@METHOD]{method="score" type="command"}
# [@METHOD]{method="trace" type="command"}
# [@METHOD]{method="persist" type="command"}
# [@METHOD]{method="rank_fixes" type="command"}
# [@METHOD]{method="analyze_risk" type="command"}
# [@METHOD]{method="simulate" type="command"}
# [@METHOD]{method="validate" type="command"}
# [@METHOD]{method="analyze_cost" type="command"}
# [@METHOD]{method="analyze_benefit" type="command"}
# [@METHOD]{method="parse_confidence" type="command"}
# [@METHOD]{method="match_confidence" type="command"}
# [@METHOD]{method="graph_confidence" type="command"}
# [@METHOD]{method="repair_confidence" type="command"}
# [@METHOD]{method="runtime_confidence" type="command"}
# [@METHOD]{method="overall_confidence" type="command"}
# [@METHOD]{method="add_node" type="command"}
# [@METHOD]{method="get_node" type="command"}
# [@METHOD]{method="query_nodes" type="command"}
# [@METHOD]{method="delete_node" type="command"}
# [@METHOD]{method="update_node" type="command"}
# [@METHOD]{method="add_edge" type="command"}
# [@METHOD]{method="get_edges" type="command"}
# [@METHOD]{method="delete_edge" type="command"}
# [@METHOD]{method="get_neighbors" type="command"}
# [@METHOD]{method="get_paths" type="command"}
# [@METHOD]{method="export" type="command"}
# [@METHOD]{method="add_rule" type="command"}
# [@METHOD]{method="get_rules" type="command"}
# [@METHOD]{method="get_decision" type="command"}
# [@METHOD]{method="query_decisions" type="command"}
# [@METHOD]{method="add_snapshot" type="command"}
# [@METHOD]{method="get_snapshot" type="command"}
# [@METHOD]{method="init_schema" type="command"}
# [@METHOD]{method="migrate_codefix" type="command"}
# [@METHOD]{method="migrate_session" type="command"}
# [@METHOD]{method="stats" type="command"}
# [@METHOD]{method="open_session" type="command"}
# [@METHOD]{method="add_path" type="command"}
# [@METHOD]{method="update_path" type="command"}
# [@METHOD]{method="add_resume" type="command"}
# [@METHOD]{method="get_resume" type="command"}
# [@METHOD]{method="render" type="command"}
# [@METHOD]{method="dashboard" type="command"}
# [@METHOD]{method="close_session" type="command"}
# [@METHOD]{method="list_sessions" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="_get_conn" type="helper"}
# [@METHOD]{method="_infer_domain" type="helper"}
# [@METHOD]{method="_now" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Unified decision graph engine merging DecisionEngine, ConfidenceEngine, DomSessionGraph, GUIDecisionEngine. 1859 lines with 50+ methods. VBStyle Run dispatch, Tuple3, self.state. Has _p, _get_conn, _infer_domain, _now helpers using self._ pattern (underscore prefix). Massive file with multiple domain concerns.>][@todos<Move helper methods away from self._ prefix. Consider splitting domains into separate files. Reduce file size.>]}
"""
DomGraphEngine -- Unified decision graph engine.
Phase 1: codefix domain (DecisionEngine + ConfidenceEngine ported).
Commands: decide, get_candidates, filter, when_rules, resolve_conflicts,
          score, trace, persist, rank_fixes, analyze_risk, simulate,
          validate, analyze_cost, analyze_benefit,
          parse_confidence, match_confidence, graph_confidence,
          repair_confidence, runtime_confidence, overall_confidence,
          add_node, get_node, query_nodes, add_edge, get_edges,
          add_rule, get_rules, get_decision, query_decisions,
          add_snapshot, get_snapshot, init_schema, migrate_codefix, stats.
Phase 2: session domain (DomSessionGraph ported from MySQL to SQLite).
Commands: migrate_session, open_session, add_path, update_path, add_resume,
          get_resume, render, dashboard, close_session, list_sessions.
"""
import ast
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone, date

DEFAULT_DB_NAME = "dom_graph_unified.db"
DEFAULT_LIMIT = 50
DEFAULT_DOMAIN = "codefix"

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS nodes (
        node_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        domain           TEXT NOT NULL,
        node_type        TEXT NOT NULL,
        name             TEXT NOT NULL,
        qualified_name   TEXT,
        description      TEXT,
        content          TEXT,
        properties       TEXT,
        domain_tags      TEXT,
        complexity_level TEXT,
        confidence       REAL DEFAULT 0,
        status           TEXT DEFAULT 'active',
        score            REAL DEFAULT 0,
        parent_node_id   INTEGER,
        source_file      TEXT,
        line_start       INTEGER,
        line_end         INTEGER,
        hash             TEXT,
        version          INTEGER DEFAULT 1,
        created          TEXT,
        updated          TEXT,
        FOREIGN KEY (parent_node_id) REFERENCES nodes(node_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_nodes_domain     ON nodes(domain)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_type       ON nodes(node_type)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_name       ON nodes(name)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_parent     ON nodes(parent_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_status     ON nodes(status)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_confidence ON nodes(confidence DESC)",
    """CREATE TABLE IF NOT EXISTS edges (
        edge_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        domain           TEXT NOT NULL,
        src_node_id      INTEGER NOT NULL,
        src_type         TEXT NOT NULL,
        dst_node_id      INTEGER NOT NULL,
        dst_type         TEXT NOT NULL,
        edge_type        TEXT NOT NULL,
        evidence         TEXT,
        confidence       REAL DEFAULT 100.0,
        weight           REAL DEFAULT 1.0,
        created          TEXT,
        FOREIGN KEY (src_node_id) REFERENCES nodes(node_id),
        FOREIGN KEY (dst_node_id) REFERENCES nodes(node_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_edges_domain ON edges(domain)",
    "CREATE INDEX IF NOT EXISTS idx_edges_src    ON edges(src_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_edges_dst    ON edges(dst_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_edges_type   ON edges(edge_type)",
    """CREATE TABLE IF NOT EXISTS rules (
        rule_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        domain           TEXT NOT NULL,
        rule_type        TEXT NOT NULL,
        target_node_id   INTEGER,
        condition_expr   TEXT,
        resolution_expr  TEXT,
        score_expr       TEXT,
        base_score       REAL DEFAULT 0,
        max_score        REAL DEFAULT 100,
        priority         INTEGER DEFAULT 1,
        description      TEXT,
        category         TEXT,
        correction       TEXT,
        anti_pattern     TEXT,
        implementation   TEXT,
        is_active        INTEGER DEFAULT 1,
        created          TEXT,
        FOREIGN KEY (target_node_id) REFERENCES nodes(node_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rules_domain ON rules(domain)",
    "CREATE INDEX IF NOT EXISTS idx_rules_type   ON rules(rule_type)",
    "CREATE INDEX IF NOT EXISTS idx_rules_target ON rules(target_node_id)",
    """CREATE TABLE IF NOT EXISTS decisions (
        decision_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        domain           TEXT NOT NULL,
        decision_type    TEXT NOT NULL,
        input_context    TEXT,
        chosen_node_id   INTEGER,
        chosen_name      TEXT,
        decision_score   REAL DEFAULT 0,
        reason           TEXT,
        reason_trace     TEXT,
        evaluated        TEXT,
        state            TEXT,
        resume_action    TEXT,
        is_active        INTEGER DEFAULT 1,
        created          TEXT,
        FOREIGN KEY (chosen_node_id) REFERENCES nodes(node_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_decisions_domain ON decisions(domain)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_type   ON decisions(decision_type)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_chosen ON decisions(chosen_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_active ON decisions(is_active)",
    """CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        domain           TEXT NOT NULL,
        snapshot_type    TEXT NOT NULL,
        target_node_id   INTEGER,
        project_name     TEXT,
        progress         INTEGER DEFAULT 0,
        state            TEXT,
        resume_action    TEXT,
        content          TEXT NOT NULL,
        hash             TEXT NOT NULL,
        notes            TEXT,
        is_active        INTEGER DEFAULT 1,
        created          TEXT NOT NULL,
        FOREIGN KEY (target_node_id) REFERENCES nodes(node_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_domain ON snapshots(domain)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_type   ON snapshots(snapshot_type)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_active ON snapshots(is_active)",
]


class DomGraphEngine:
    """Unified decision graph engine."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    DEFAULT_DB_NAME,
                ),
                "default_limit": DEFAULT_LIMIT,
                "default_domain": DEFAULT_DOMAIN,
            },
            "candidates": [],
            "filtered": [],
            "triggered": [],
            "resolved": [],
            "scored": [],
            "decision": None,
            "reason_trace": [],
            "stats": {
                "decisions_made": 0,
                "candidates_evaluated": 0,
            },
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            "decide": self.Decide,
            "get_candidates": self.GetCandidates,
            "filter": self.Filter,
            "when_rules": self.WhenRules,
            "resolve_conflicts": self.ResolveConflicts,
            "score": self.Score,
            "trace": self.Trace,
            "persist": self.Persist,
            "rank_fixes": self.RankFixes,
            "analyze_risk": self.AnalyzeRisk,
            "simulate": self.Simulate,
            "validate": self.Validate,
            "analyze_cost": self.AnalyzeCost,
            "analyze_benefit": self.AnalyzeBenefit,
            "parse_confidence": self.ParseConfidence,
            "match_confidence": self.MatchConfidence,
            "graph_confidence": self.GraphConfidence,
            "repair_confidence": self.RepairConfidence,
            "runtime_confidence": self.RuntimeConfidence,
            "overall_confidence": self.OverallConfidence,
            "add_node": self.AddNode,
            "get_node": self.GetNode,
            "query_nodes": self.QueryNodes,
            "delete_node": self.DeleteNode,
            "update_node": self.UpdateNode,
            "add_edge": self.AddEdge,
            "get_edges": self.GetEdges,
            "delete_edge": self.DeleteEdge,
            "get_neighbors": self.GetNeighbors,
            "get_paths": self.GetPaths,
            "export": self.Export,
            "add_rule": self.AddRule,
            "get_rules": self.GetRules,
            "get_decision": self.GetDecision,
            "query_decisions": self.QueryDecisions,
            "add_snapshot": self.AddSnapshot,
            "get_snapshot": self.GetSnapshot,
            "init_schema": self.InitSchema,
            "migrate_codefix": self.MigrateCodefix,
            "migrate_session": self.MigrateSession,
            "gc": self.Gc,
            "stats": self.Stats,
            "open_session": self.OpenSession,
            "add_path": self.AddPath,
            "update_path": self.UpdatePath,
            "add_resume": self.AddResume,
            "get_resume": self.GetResume,
            "render": self.Render,
            "dashboard": self.Dashboard,
            "close_session": self.CloseSession,
            "list_sessions": self.ListSessions,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _get_conn(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
            self.state["db_conn"].row_factory = sqlite3.Row
        return self.state["db_conn"]

    def _infer_domain(self, command):
        session_cmds = {"open_session", "add_path", "update_path", "add_resume",
                        "get_resume", "render", "dashboard", "close_session",
                        "list_sessions"}
        gui_cmds = {"decide_component", "validate_context"}
        codefix_cmds = {"rank_fixes", "analyze_risk", "simulate", "validate",
                        "analyze_cost", "analyze_benefit"}
        if command in session_cmds:
            return "session"
        if command in gui_cmds:
            return "gui"
        if command in codefix_cmds:
            return "codefix"
        return self.state["config"].get("default_domain", DEFAULT_DOMAIN)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def InitSchema(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()
        return (1, {"schema_initialized": True, "tables": ["nodes", "edges", "rules", "decisions", "snapshots"]}, None)

    def AddNode(self, params):
        domain = self._p(params, "domain", DEFAULT_DOMAIN)
        node_type = self._p(params, "node_type")
        name = self._p(params, "name")
        if not node_type or not name:
            return (0, None, ("NO_PARAM", "node_type and name required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        props = self._p(params, "properties", {})
        if isinstance(props, dict):
            props = json.dumps(props)
        cur.execute(
            "INSERT INTO nodes (domain, node_type, name, qualified_name, description, "
            "content, properties, domain_tags, complexity_level, confidence, status, "
            "parent_node_id, source_file, line_start, line_end, hash, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (domain, node_type, name, self._p(params, "qualified_name"),
             self._p(params, "description"), self._p(params, "content"), props,
             self._p(params, "domain_tags"), self._p(params, "complexity_level"),
             self._p(params, "confidence", 0), self._p(params, "status", "active"),
             self._p(params, "parent_node_id"), self._p(params, "source_file"),
             self._p(params, "line_start"), self._p(params, "line_end"),
             self._p(params, "hash"), self._now(), self._now())
        )
        conn.commit()
        node_id = cur.lastrowid
        return (1, {"node_id": node_id, "domain": domain, "node_type": node_type, "name": name}, None)

    def GetNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("NO_PARAM", "node_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM nodes WHERE node_id=?", (node_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "node not found", 0))
        node = dict(row)
        if node.get("properties"):
            try:
                node["properties"] = json.loads(node["properties"])
            except (json.JSONDecodeError, TypeError):
                pass
        return (1, node, None)

    def QueryNodes(self, params):
        domain = self._p(params, "domain")
        node_type = self._p(params, "node_type")
        query = self._p(params, "query", self._p(params, "name", ""))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM nodes WHERE 1=1"
        args = []
        if domain:
            sql += " AND domain=?"
            args.append(domain)
        if node_type:
            sql += " AND node_type=?"
            args.append(node_type)
        if query:
            sql += " AND name LIKE ?"
            args.append("%" + query + "%")
        sql += " ORDER BY confidence DESC LIMIT ?"
        args.append(limit)
        cur.execute(sql, args)
        results = []
        for row in cur.fetchall():
            node = dict(row)
            if node.get("properties"):
                try:
                    node["properties"] = json.loads(node["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(node)
        return (1, {"nodes": results, "count": len(results)}, None)

    def AddEdge(self, params):
        domain = self._p(params, "domain", DEFAULT_DOMAIN)
        src_node_id = self._p(params, "src_node_id")
        dst_node_id = self._p(params, "dst_node_id")
        edge_type = self._p(params, "edge_type")
        if not all([src_node_id, dst_node_id, edge_type]):
            return (0, None, ("NO_PARAM", "src_node_id, dst_node_id, edge_type required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO edges (domain, src_node_id, src_type, dst_node_id, dst_type, "
            "edge_type, evidence, confidence, weight, created) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (domain, src_node_id, self._p(params, "src_type", "method"),
             dst_node_id, self._p(params, "dst_type", "method"), edge_type,
             self._p(params, "evidence"), self._p(params, "confidence", 100.0),
             self._p(params, "weight", 1.0), self._now())
        )
        conn.commit()
        edge_id = cur.lastrowid
        return (1, {"edge_id": edge_id}, None)

    def GetEdges(self, params):
        node_id = self._p(params, "node_id")
        domain = self._p(params, "domain")
        if not node_id:
            return (0, None, ("NO_PARAM", "node_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM edges WHERE (src_node_id=? OR dst_node_id=?)"
        args = [node_id, node_id]
        if domain:
            sql += " AND domain=?"
            args.append(domain)
        cur.execute(sql, args)
        results = [dict(row) for row in cur.fetchall()]
        return (1, {"edges": results, "count": len(results)}, None)

    def DeleteNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("NO_PARAM", "node_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT node_id FROM nodes WHERE node_id=?", (node_id,))
        if not cur.fetchone():
            return (0, None, ("NOT_FOUND", "node not found", 0))
        cur.execute("DELETE FROM edges WHERE src_node_id=? OR dst_node_id=?",
                    (node_id, node_id))
        deleted_edges = cur.rowcount
        cur.execute("DELETE FROM nodes WHERE node_id=?", (node_id,))
        conn.commit()
        return (1, {"node_id": node_id, "deleted": True,
                    "edges_removed": deleted_edges}, None)

    def DeleteEdge(self, params):
        edge_id = self._p(params, "edge_id")
        if not edge_id:
            return (0, None, ("NO_PARAM", "edge_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT edge_id FROM edges WHERE edge_id=?", (edge_id,))
        if not cur.fetchone():
            return (0, None, ("NOT_FOUND", "edge not found", 0))
        cur.execute("DELETE FROM edges WHERE edge_id=?", (edge_id,))
        conn.commit()
        return (1, {"edge_id": edge_id, "deleted": True}, None)

    def UpdateNode(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("NO_PARAM", "node_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT node_id FROM nodes WHERE node_id=?", (node_id,))
        if not cur.fetchone():
            return (0, None, ("NOT_FOUND", "node not found", 0))
        sets = ["updated=?"]
        vals = [self._now()]
        name = self._p(params, "name")
        if name:
            sets.append("name=?")
            vals.append(name)
        description = self._p(params, "description")
        if description:
            sets.append("description=?")
            vals.append(description)
        properties = self._p(params, "properties")
        if properties:
            if isinstance(properties, dict):
                properties = json.dumps(properties)
            sets.append("properties=?")
            vals.append(properties)
        vals.append(node_id)
        cur.execute("UPDATE nodes SET " + ", ".join(sets) + " WHERE node_id=?", vals)
        conn.commit()
        return (1, {"node_id": node_id, "updated": True}, None)

    def GetNeighbors(self, params):
        node_id = self._p(params, "node_id")
        if not node_id:
            return (0, None, ("NO_PARAM", "node_id required", 0))
        edge_type = self._p(params, "edge_type")
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        domain = self._p(params, "domain")
        conn = self._get_conn()
        cur = conn.cursor()
        sql = (
            "SELECT n.*, e.edge_type, e.edge_id, e.confidence AS edge_confidence, "
            "CASE WHEN e.src_node_id=? THEN 'outgoing' ELSE 'incoming' END AS direction "
            "FROM edges e JOIN nodes n ON "
            "n.node_id = CASE WHEN e.src_node_id=? THEN e.dst_node_id ELSE e.src_node_id END "
            "WHERE (e.src_node_id=? OR e.dst_node_id=?)"
        )
        args = [node_id, node_id, node_id, node_id]
        if edge_type:
            sql += " AND e.edge_type=?"
            args.append(edge_type)
        if domain:
            sql += " AND e.domain=?"
            args.append(domain)
        sql += " LIMIT ?"
        args.append(limit)
        cur.execute(sql, args)
        neighbors = []
        for row in cur.fetchall():
            n = dict(row)
            if n.get("properties"):
                try:
                    n["properties"] = json.loads(n["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            neighbors.append(n)
        return (1, {"neighbors": neighbors, "count": len(neighbors)}, None)

    def GetPaths(self, params):
        src_node_id = self._p(params, "src_node_id")
        dst_node_id = self._p(params, "dst_node_id")
        if not src_node_id or not dst_node_id:
            return (0, None, ("NO_PARAM", "src_node_id and dst_node_id required", 0))
        max_depth = self._p(params, "max_depth", 5)
        domain = self._p(params, "domain")
        conn = self._get_conn()
        cur = conn.cursor()
        paths = []

        def dfs(current, target, depth, path):
            if depth > max_depth:
                return
            if current == target:
                paths.append(list(path))
                return
            sql = "SELECT dst_node_id FROM edges WHERE src_node_id=?"
            args = [current]
            if domain:
                sql += " AND domain=?"
                args.append(domain)
            cur.execute(sql, args)
            for r in cur.fetchall():
                nxt = r[0]
                if nxt not in path:
                    path.append(nxt)
                    dfs(nxt, target, depth + 1, path)
                    path.pop()

        dfs(src_node_id, dst_node_id, 0, [src_node_id])
        return (1, {"paths": paths, "count": len(paths),
                    "src_node_id": src_node_id, "dst_node_id": dst_node_id}, None)

    def Export(self, params):
        fmt = self._p(params, "format", "json")
        limit = self._p(params, "limit", 0)
        domain = self._p(params, "domain")
        conn = self._get_conn()
        cur = conn.cursor()
        node_sql = "SELECT * FROM nodes"
        node_args = []
        if domain:
            node_sql += " WHERE domain=?"
            node_args.append(domain)
        if limit and limit > 0:
            node_sql += " LIMIT ?"
            node_args.append(limit)
        cur.execute(node_sql, node_args)
        nodes = [dict(r) for r in cur.fetchall()]
        edge_sql = "SELECT * FROM edges"
        edge_args = []
        if domain:
            edge_sql += " WHERE domain=?"
            edge_args.append(domain)
        if limit and limit > 0:
            edge_sql += " LIMIT ?"
            edge_args.append(limit)
        cur.execute(edge_sql, edge_args)
        edges = [dict(r) for r in cur.fetchall()]
        if fmt.lower() == "csv":
            lines = []
            node_cols = ["node_id", "domain", "node_type", "name",
                         "description", "confidence", "status"]
            lines.append(",".join(node_cols))
            for n in nodes:
                lines.append(",".join([str(n.get(c, "")) for c in node_cols]))
            lines.append("")
            edge_cols = ["edge_id", "domain", "src_node_id", "dst_node_id",
                         "edge_type", "confidence"]
            lines.append(",".join(edge_cols))
            for e in edges:
                lines.append(",".join([str(e.get(c, "")) for c in edge_cols]))
            return (1, {"format": "csv", "data": "\n".join(lines),
                        "node_count": len(nodes), "edge_count": len(edges)}, None)
        return (1, {"format": "json", "nodes": nodes, "edges": edges,
                    "node_count": len(nodes), "edge_count": len(edges)}, None)

    def AddRule(self, params):
        domain = self._p(params, "domain", DEFAULT_DOMAIN)
        rule_type = self._p(params, "rule_type")
        if not rule_type:
            return (0, None, ("NO_PARAM", "rule_type required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rules (domain, rule_type, target_node_id, condition_expr, "
            "resolution_expr, score_expr, base_score, max_score, priority, description, "
            "category, correction, anti_pattern, implementation, is_active, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (domain, rule_type, self._p(params, "target_node_id"),
             self._p(params, "condition_expr"), self._p(params, "resolution_expr"),
             self._p(params, "score_expr"), self._p(params, "base_score", 0),
             self._p(params, "max_score", 100), self._p(params, "priority", 1),
             self._p(params, "description"), self._p(params, "category"),
             self._p(params, "correction"), self._p(params, "anti_pattern"),
             self._p(params, "implementation"), 1, self._now())
        )
        conn.commit()
        rule_id = cur.lastrowid
        return (1, {"rule_id": rule_id}, None)

    def GetRules(self, params):
        domain = self._p(params, "domain")
        target_node_id = self._p(params, "target_node_id")
        rule_type = self._p(params, "rule_type")
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM rules WHERE is_active=1"
        args = []
        if domain:
            sql += " AND domain=?"
            args.append(domain)
        if target_node_id:
            sql += " AND target_node_id=?"
            args.append(target_node_id)
        if rule_type:
            sql += " AND rule_type=?"
            args.append(rule_type)
        cur.execute(sql, args)
        results = [dict(row) for row in cur.fetchall()]
        return (1, {"rules": results, "count": len(results)}, None)

    def GetDecision(self, params):
        decision_id = self._p(params, "decision_id")
        if not decision_id:
            return (0, None, ("NO_PARAM", "decision_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "decision not found", 0))
        decision = dict(row)
        for field in ["input_context", "reason_trace", "evaluated"]:
            if decision.get(field):
                try:
                    decision[field] = json.loads(decision[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return (1, decision, None)

    def QueryDecisions(self, params):
        domain = self._p(params, "domain")
        decision_type = self._p(params, "decision_type")
        limit = self._p(params, "limit", 20)
        conn = self._get_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM decisions WHERE is_active=1"
        args = []
        if domain:
            sql += " AND domain=?"
            args.append(domain)
        if decision_type:
            sql += " AND decision_type=?"
            args.append(decision_type)
        sql += " ORDER BY created DESC LIMIT ?"
        args.append(limit)
        cur.execute(sql, args)
        results = [dict(row) for row in cur.fetchall()]
        return (1, {"decisions": results, "count": len(results)}, None)

    def AddSnapshot(self, params):
        domain = self._p(params, "domain", DEFAULT_DOMAIN)
        snapshot_type = self._p(params, "snapshot_type")
        content = self._p(params, "content", "")
        if not snapshot_type:
            return (0, None, ("NO_PARAM", "snapshot_type required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        cur.execute(
            "INSERT INTO snapshots (domain, snapshot_type, target_node_id, project_name, "
            "progress, state, resume_action, content, hash, notes, is_active, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (domain, snapshot_type, self._p(params, "target_node_id"),
             self._p(params, "project_name"), self._p(params, "progress", 0),
             self._p(params, "state"), self._p(params, "resume_action"),
             content, hash_val, self._p(params, "notes"), 1, self._now())
        )
        conn.commit()
        snapshot_id = cur.lastrowid
        return (1, {"snapshot_id": snapshot_id, "hash": hash_val}, None)

    def GetSnapshot(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        if not snapshot_id:
            return (0, None, ("NO_PARAM", "snapshot_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "snapshot not found", 0))
        return (1, dict(row), None)

    def GetCandidates(self, params):
        domain = self._p(params, "domain", self._infer_domain("get_candidates"))
        query = self._p(params, "query", self._p(params, "problem", ""))
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self._get_conn()
        cur = conn.cursor()
        if domain == "codefix":
            cur.execute(
                "SELECT node_id, name, description, confidence, properties, domain_tags "
                "FROM nodes WHERE domain='codefix' AND node_type='knowledge' "
                "AND description IS NOT NULL AND name LIKE ? "
                "ORDER BY confidence DESC LIMIT ?",
                ("%" + query + "%", limit)
            )
        elif domain == "gui":
            cur.execute(
                "SELECT node_id, name, description, confidence, properties "
                "FROM nodes WHERE domain='gui' AND node_type='component' "
                "ORDER BY confidence DESC LIMIT ?",
                (limit,)
            )
        else:
            cur.execute(
                "SELECT node_id, name, description, confidence, properties "
                "FROM nodes WHERE domain=? AND name LIKE ? "
                "ORDER BY confidence DESC LIMIT ?",
                (domain, "%" + query + "%", limit)
            )
        candidates = []
        for row in cur.fetchall():
            c = dict(row)
            if c.get("properties"):
                try:
                    c["properties"] = json.loads(c["properties"])
                except (json.JSONDecodeError, TypeError):
                    pass
            candidates.append(c)
        self.state["candidates"] = candidates
        self.state["stats"]["candidates_evaluated"] += len(candidates)
        return (1, {"candidates": candidates, "count": len(candidates), "domain": domain}, None)

    def Filter(self, params):
        candidates = self._p(params, "candidates", self.state.get("candidates", []))
        domain = self._p(params, "domain", self._infer_domain("filter"))
        if not candidates:
            ok, data, err = self.GetCandidates(params)
            if ok != 1:
                return (0, None, err)
            candidates = data["candidates"]
        filtered = []
        for c in candidates:
            props = c.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except (json.JSONDecodeError, TypeError):
                    props = {}
            if domain == "codefix":
                fix_result = props.get("fix_result", "")
                if fix_result == "failed" and c.get("confidence", 0) < 50:
                    continue
            filtered.append(c)
        self.state["filtered"] = filtered
        return (1, {"filtered": filtered, "count": len(filtered)}, None)

    def WhenRules(self, params):
        candidates = self._p(params, "candidates", self.state.get("filtered", []))
        domain = self._p(params, "domain", self._infer_domain("when_rules"))
        if not candidates:
            ok, data, err = self.Filter(params)
            if ok != 1:
                return (0, None, err)
            candidates = data["filtered"]
        conn = self._get_conn()
        cur = conn.cursor()
        triggered = []
        for c in candidates:
            node_id = c.get("node_id")
            cur.execute(
                "SELECT * FROM rules WHERE domain=? AND rule_type='when' AND is_active=1 "
                "AND (target_node_id IS NULL OR target_node_id=?)",
                (domain, node_id)
            )
            rules = cur.fetchall()
            passed = True
            for rule in rules:
                condition = rule["condition_expr"]
                if condition and "fix_result == 'success'" in condition:
                    props = c.get("properties", {})
                    if isinstance(props, str):
                        try:
                            props = json.loads(props)
                        except (json.JSONDecodeError, TypeError):
                            props = {}
                    if props.get("fix_result") != "success":
                        passed = False
                        break
            if passed:
                triggered.append(c)
        self.state["triggered"] = triggered
        return (1, {"triggered": triggered, "count": len(triggered)}, None)

    def ResolveConflicts(self, params):
        candidates = self._p(params, "candidates", self.state.get("triggered", []))
        domain = self._p(params, "domain", self._infer_domain("resolve_conflicts"))
        if not candidates:
            ok, data, err = self.WhenRules(params)
            if ok != 1:
                return (0, None, err)
            candidates = data["triggered"]
        if len(candidates) <= 1:
            self.state["resolved"] = candidates
            return (1, {"resolved": candidates, "count": len(candidates)}, None)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM rules WHERE domain=? AND rule_type='conflict_resolution' AND is_active=1",
            (domain,)
        )
        rules = cur.fetchall()
        if rules:
            resolved = sorted(candidates, key=lambda c: c.get("confidence", 0), reverse=True)
        else:
            if domain == "codefix":
                def sort_key(c):
                    props = c.get("properties", {})
                    if isinstance(props, str):
                        try:
                            props = json.loads(props)
                        except (json.JSONDecodeError, TypeError):
                            props = {}
                    return (props.get("fix_result") == "success", c.get("confidence", 0))
                resolved = sorted(candidates, key=sort_key, reverse=True)
            else:
                resolved = sorted(candidates, key=lambda c: c.get("confidence", 0), reverse=True)
        self.state["resolved"] = resolved
        return (1, {"resolved": resolved, "count": len(resolved)}, None)

    def Score(self, params):
        candidates = self._p(params, "candidates", self.state.get("resolved", []))
        domain = self._p(params, "domain", self._infer_domain("score"))
        method_id = self._p(params, "method_id")
        problem = self._p(params, "problem", self._p(params, "query", ""))
        if not candidates:
            ok, data, err = self.ResolveConflicts(params)
            if ok != 1:
                return (0, None, err)
            candidates = data["resolved"]
        scored = []
        for c in candidates:
            entry = dict(c)
            risk = 0.0
            if method_id and domain == "codefix":
                risk_res = self.AnalyzeRisk({"method_id": method_id})
                if risk_res[0] == 1:
                    risk = risk_res[1]["risk_score"]
                    entry["risk_analysis"] = risk_res[1]
            entry["risk_score"] = risk
            sim_res = self.Simulate({"fix_id": c.get("node_id"), "domain": domain})
            entry["simulation"] = sim_res[1] if sim_res[0] == 1 else {"simulated": False}
            val_res = self.Validate({"fix_id": c.get("node_id"), "domain": domain})
            entry["validation"] = val_res[1] if val_res[0] == 1 else {"validated": False}
            cost = 0.0
            if method_id and domain == "codefix":
                cost_res = self.AnalyzeCost({"method_id": method_id})
                if cost_res[0] == 1:
                    cost = cost_res[1]["cost_score"]
                    entry["cost_analysis"] = cost_res[1]
            entry["cost_score"] = cost
            benefit = 0.0
            if problem and domain == "codefix":
                ben_res = self.AnalyzeBenefit({"problem": problem})
                if ben_res[0] == 1:
                    benefit = ben_res[1]["benefit_score"]
                    entry["benefit_analysis"] = ben_res[1]
            entry["benefit_score"] = benefit
            confidence = c.get("confidence", 0)
            sim_ok = 1 if entry["simulation"].get("simulated") else 0
            val_ok = 1 if entry["validation"].get("validated") else 0
            denom = 1 + risk + (cost / 10.0)
            if denom == 0:
                denom = 1
            props = c.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except (json.JSONDecodeError, TypeError):
                    props = {}
            success_rate = props.get("success_rate", 0.0)
            entry["decision_score"] = (confidence * (1 + success_rate) *
                                        (1 + sim_ok) * (1 + val_ok) + benefit) / denom
            scored.append(entry)
        scored.sort(key=lambda e: e["decision_score"], reverse=True)
        self.state["scored"] = scored
        return (1, {"scored": scored, "count": len(scored)}, None)

    def Decide(self, params):
        domain = self._p(params, "domain", self._infer_domain("decide"))
        steps = []
        ok, data, err = self.GetCandidates(params)
        if ok != 1:
            return (0, None, err)
        steps.append({"step": "get_candidates", "count": data["count"]})
        ok, data, err = self.Filter(params)
        if ok != 1:
            return (0, None, err)
        steps.append({"step": "filter", "count": data["count"]})
        ok, data, err = self.WhenRules(params)
        if ok != 1:
            return (0, None, err)
        steps.append({"step": "when_rules", "count": data["count"]})
        ok, data, err = self.ResolveConflicts(params)
        if ok != 1:
            return (0, None, err)
        steps.append({"step": "resolve_conflicts", "count": data["count"]})
        ok, data, err = self.Score(params)
        if ok != 1:
            return (0, None, err)
        steps.append({"step": "score", "count": data["count"]})
        scored = data["scored"]
        if not scored:
            self.state["decision"] = None
            self.state["reason_trace"] = steps
            return (1, {"chosen": None, "reason": "no candidates found", "reason_trace": steps}, None)
        best = scored[0]
        decision = {
            "chosen": best,
            "decision_score": best["decision_score"],
            "reason": "best confidence/risk ratio after simulation, validation, cost and benefit",
            "evaluated": scored,
            "domain": domain,
        }
        self.state["decision"] = decision
        self.state["reason_trace"] = steps
        self.state["stats"]["decisions_made"] += 1
        do_persist = self._p(params, "persist", False)
        if do_persist:
            self.Persist(params)
        return (1, decision, None)

    def Trace(self, params):
        return (1, {"reason_trace": self.state.get("reason_trace", []), "decision": self.state.get("decision")}, None)

    def Persist(self, params):
        decision = self._p(params, "decision", self.state.get("decision"))
        if not decision:
            return (0, None, ("NO_DECISION", "no decision to persist", 0))
        domain = decision.get("domain", DEFAULT_DOMAIN)
        chosen = decision.get("chosen", {})
        conn = self._get_conn()
        cur = conn.cursor()
        chosen_node_id = chosen.get("node_id")
        chosen_name = chosen.get("name", "")
        decision_type = "fix_choice" if domain == "codefix" else "component_choice" if domain == "gui" else "resume_point"
        cur.execute(
            "INSERT INTO decisions (domain, decision_type, input_context, chosen_node_id, "
            "chosen_name, decision_score, reason, reason_trace, evaluated, is_active, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (domain, decision_type,
             json.dumps(self._p(params, "context", {})),
             chosen_node_id, chosen_name, decision.get("decision_score", 0),
             decision.get("reason", ""),
             json.dumps(self.state.get("reason_trace", [])),
             json.dumps(decision.get("evaluated", [])),
             1, self._now())
        )
        conn.commit()
        decision_id = cur.lastrowid
        return (1, {"decision_id": decision_id, "persisted": True}, None)

    def RankFixes(self, params):
        ok, data, err = self.GetCandidates(params)
        if ok != 1:
            return (0, None, err)
        candidates = data["candidates"]
        conn = self._get_conn()
        cur = conn.cursor()
        for c in candidates:
            cur.execute(
                "SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' "
                "AND description=? AND properties LIKE '%\"fix_result\":\"success\"%'",
                (c.get("description", ""),)
            )
            c["success_count"] = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' "
                "AND description=?", (c.get("description", ""),)
            )
            total = cur.fetchone()[0]
            c["total_count"] = total
            c["success_rate"] = (c["success_count"] / total) if total > 0 else 0.0
        props_key = lambda c: c.get("properties", {})
        ranked = sorted(candidates, key=lambda c: (
            isinstance(c.get("properties"), dict) and c["properties"].get("fix_result") == "success",
            c.get("success_rate", 0.0), c.get("confidence", 0)), reverse=True)
        return (1, {"ranked_fixes": ranked, "count": len(ranked)}, None)

    def AnalyzeRisk(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT complexity_level, properties FROM nodes WHERE domain='codefix' "
            "AND node_type='method' AND node_id=?", (method_id,)
        )
        row = cur.fetchone()
        complexity = 0
        if row:
            complexity = int(row["complexity_level"] or 0)
        cur.execute(
            "SELECT COUNT(DISTINCT src_node_id) FROM edges WHERE domain='codefix' "
            "AND dst_node_id=? AND edge_type='calls'", (method_id,)
        )
        incoming_edges = cur.fetchone()[0]
        total_complexity = complexity
        affected = [method_id]
        visited = set()
        queue = [method_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            cur.execute(
                "SELECT DISTINCT src_node_id FROM edges WHERE domain='codefix' "
                "AND dst_node_id=? AND edge_type='calls'", (current,)
            )
            for r in cur.fetchall():
                caller = r[0]
                if caller not in visited:
                    affected.append(caller)
                    queue.append(caller)
                    cur.execute(
                        "SELECT complexity_level FROM nodes WHERE domain='codefix' "
                        "AND node_type='method' AND node_id=?", (caller,)
                    )
                    crow = cur.fetchone()
                    if crow and crow[0]:
                        total_complexity += int(crow[0])
        depth = self._compute_depth(method_id, cur)
        risk = (incoming_edges * complexity * (1 + depth)) / 10.0
        return (1, {"method_id": method_id, "incoming_edges": incoming_edges,
                    "complexity": complexity, "total_complexity": total_complexity,
                    "dependency_depth": depth, "affected_methods": len(affected),
                    "risk_score": risk}, None)

    def _compute_depth(self, method_id, cur):
        visited = set()
        max_depth = [0]
        def dfs(mid, depth):
            if mid in visited:
                return
            visited.add(mid)
            if depth > max_depth[0]:
                max_depth[0] = depth
            cur.execute(
                "SELECT DISTINCT dst_node_id FROM edges WHERE domain='codefix' "
                "AND src_node_id=? AND edge_type='calls'", (mid,)
            )
            for r in cur.fetchall():
                dfs(r[0], depth + 1)
        dfs(method_id, 0)
        return max_depth[0]

    def Simulate(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT description, content, properties FROM nodes WHERE domain='codefix' "
            "AND node_type='knowledge' AND node_id=?", (fix_id,)
        )
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Fix not found", 0))
        answer = row["description"] or ""
        props = row["properties"] or "{}"
        try:
            props = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            props = {}
        method_id = props.get("method_id")
        sandbox = sqlite3.connect(":memory:")
        try:
            scur = sandbox.cursor()
            ssrc = conn.cursor()
            ssrc.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
            for r in ssrc.fetchall():
                scur.execute(r[0])
            ssrc.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
            for r in ssrc.fetchall():
                try:
                    scur.execute(r[0])
                except sqlite3.Error:
                    pass
            for table in ("nodes", "edges", "rules", "decisions", "snapshots"):
                try:
                    ssrc.execute("SELECT * FROM " + table)
                    cols = [d[0] for d in ssrc.description]
                    placeholders = ",".join(["?"] * len(cols))
                    col_list = ",".join(cols)
                    for data_row in ssrc.fetchall():
                        scur.execute("INSERT INTO " + table + " (" + col_list + ") VALUES (" + placeholders + ")", data_row)
                except sqlite3.Error:
                    pass
            simulated = True
            compile_ok = True
            if method_id:
                scur.execute(
                    "SELECT content FROM nodes WHERE domain='codefix' AND node_type='method' "
                    "AND node_id=?", (method_id,)
                )
                mrow = scur.fetchone()
                if mrow and mrow[0]:
                    try:
                        compile(mrow[0], "<simulated>", "exec")
                    except SyntaxError:
                        compile_ok = False
                        simulated = False
            sandbox.commit()
            return (1, {"simulated": simulated, "fix_id": fix_id, "answer": answer,
                        "compile_ok": compile_ok, "sandbox": "memory"}, None)
        except sqlite3.Error as e:
            return (0, None, ("SIMULATE_FAILED", str(e), 0))
        finally:
            sandbox.close()

    def Validate(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        sim_res = self.Simulate({"fix_id": fix_id})
        if sim_res[0] != 1:
            return sim_res
        sim_data = sim_res[1]
        compile_ok = sim_data.get("compile_ok", False)
        validated = compile_ok and sim_data.get("simulated", False)
        return (1, {"fix_id": fix_id, "compile_ok": compile_ok,
                    "validated": validated, "sandbox_result": sim_data}, None)

    def AnalyzeCost(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT complexity_level, properties FROM nodes WHERE domain='codefix' "
            "AND node_type='method' AND node_id=?", (method_id,)
        )
        row = cur.fetchone()
        complexity = 0
        line_count = 0
        if row:
            complexity = int(row["complexity_level"] or 0)
            try:
                props = json.loads(row["properties"] or "{}")
                line_count = props.get("line_count", 0)
            except (json.JSONDecodeError, TypeError):
                pass
        cur.execute(
            "SELECT COUNT(DISTINCT src_node_id) FROM edges WHERE domain='codefix' "
            "AND dst_node_id=? AND edge_type='calls'", (method_id,)
        )
        affected = cur.fetchone()[0]
        cost = line_count + (complexity * 2) + (affected * 5)
        return (1, {"method_id": method_id, "lines_changed": line_count,
                    "methods_affected": affected, "complexity": complexity,
                    "cost_score": cost}, None)

    def AnalyzeBenefit(self, params):
        problem = self._p(params, "problem", "")
        if not problem:
            return (0, None, ("NO_PARAM", "problem required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' "
            "AND name LIKE ? AND properties LIKE '%\"fix_result\":\"success\"%'",
            ("%" + problem + "%",)
        )
        fixes_resolved = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='method' "
            "AND properties LIKE '%\"has_print\":1%'"
        )
        violations = cur.fetchone()[0]
        benefit = (fixes_resolved * 10) + (violations * 2)
        return (1, {"problem": problem, "fixes_resolved": fixes_resolved,
                    "violations_addressed": violations, "benefit_score": benefit}, None)

    def ParseConfidence(self, params):
        file_path = self._p(params, "file_path")
        file_id = self._p(params, "file_id")
        conn = self._get_conn()
        cur = conn.cursor()
        if file_id:
            cur.execute(
                "SELECT qualified_name FROM nodes WHERE domain='codefix' AND node_type='file' AND node_id=?",
                (file_id,)
            )
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            file_path = row[0]
        parse_score = 0
        if file_path and os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                ast.parse(content, filename=file_path)
                parse_score = 100
            except SyntaxError:
                parse_score = 0
        cur.execute("SELECT AVG(confidence) FROM nodes WHERE domain='codefix' AND confidence IS NOT NULL")
        knowledge_conf = cur.fetchone()[0] or 0
        cur.execute(
            "SELECT AVG(confidence) FROM nodes WHERE domain='codefix' AND node_type='observation' AND confidence IS NOT NULL"
        )
        obs_conf = cur.fetchone()[0] or 0
        if file_path:
            overall = parse_score * 0.6 + knowledge_conf * 0.2 + obs_conf * 0.2
        else:
            overall = knowledge_conf * 0.5 + obs_conf * 0.5
        return (1, {"parse_confidence": overall, "ast_parse_score": parse_score,
                    "knowledge_confidence": knowledge_conf,
                    "observation_confidence": obs_conf}, None)

    def MatchConfidence(self, params):
        pattern = self._p(params, "pattern", "")
        target = self._p(params, "target", "")
        error_type = self._p(params, "error_type")
        conn = self._get_conn()
        cur = conn.cursor()
        text_score = 0
        if pattern and target:
            matching = sum(1 for a, b in zip(pattern, target) if a == b)
            text_score = (matching / max(len(pattern), len(target))) * 100
        similar_confidences = []
        if error_type:
            cur.execute(
                "SELECT confidence, name FROM nodes WHERE domain='codefix' AND node_type='knowledge' "
                "AND properties LIKE ? ORDER BY confidence DESC LIMIT 10",
                ('%"error_type":"' + error_type + '"%',)
            )
            for row in cur.fetchall():
                similar_confidences.append({"confidence": row[0], "problem": row[1]})
        avg_conf = sum(c["confidence"] for c in similar_confidences) / len(similar_confidences) if similar_confidences else 0
        if pattern and similar_confidences:
            match_score = text_score * 0.5 + avg_conf * 0.5
        elif pattern:
            match_score = text_score
        else:
            match_score = avg_conf
        return (1, {"match_confidence": match_score, "text_similarity": text_score,
                    "similar_error_avg_confidence": avg_conf,
                    "similar_errors_count": len(similar_confidences)}, None)

    def GraphConfidence(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT src_node_id) + COUNT(DISTINCT dst_node_id) FROM edges WHERE domain='codefix'")
        graph_entities = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix'")
        total = cur.fetchone()[0] or 0
        coverage_pct = (graph_entities / total * 100) if total > 0 else 0
        cur.execute("SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM edges WHERE domain='codefix'")
        row = cur.fetchone()
        avg_edge_conf = row[0] or 0
        min_edge_conf = row[1] or 0
        max_edge_conf = row[2] or 0
        cur.execute("SELECT edge_type, AVG(confidence), COUNT(*) FROM edges WHERE domain='codefix' GROUP BY edge_type")
        distribution = {}
        for et_row in cur.fetchall():
            distribution[et_row[0]] = {"avg_confidence": et_row[1], "count": et_row[2]}
        graph_conf = coverage_pct * 0.6 + avg_edge_conf * 0.4
        return (1, {"graph_confidence": round(graph_conf, 2),
                    "coverage_pct": round(coverage_pct, 2),
                    "avg_edge_confidence": round(avg_edge_conf, 2),
                    "min_edge_confidence": min_edge_conf,
                    "max_edge_confidence": max_edge_conf,
                    "distribution": distribution}, None)

    def RepairConfidence(self, params):
        error_type = self._p(params, "error_type")
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' AND description IS NOT NULL")
        total_fixes = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' AND properties LIKE '%\"fix_result\":\"success\"%'")
        successful = cur.fetchone()[0] or 0
        overall_success_rate = (successful / total_fixes * 100) if total_fixes > 0 else 0
        type_success_rate = overall_success_rate
        if error_type:
            cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' AND properties LIKE ? AND description IS NOT NULL", ('%"error_type":"' + error_type + '"%',))
            type_total = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='knowledge' AND properties LIKE '%\"fix_result\":\"success\"%' AND properties LIKE ?", ('%"error_type":"' + error_type + '"%',))
            type_success = cur.fetchone()[0] or 0
            type_success_rate = (type_success / type_total * 100) if type_total > 0 else 0
        attempts_success_rate = 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='attempt'")
        attempts_total = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='attempt' AND properties LIKE '%\"compile_result\":1%' AND properties LIKE '%\"test_result\":1%'")
        attempts_success = cur.fetchone()[0] or 0
        attempts_success_rate = (attempts_success / attempts_total * 100) if attempts_total > 0 else 0
        if error_type:
            repair_conf = type_success_rate * 0.5 + overall_success_rate * 0.25 + attempts_success_rate * 0.25
        else:
            repair_conf = overall_success_rate * 0.6 + attempts_success_rate * 0.4
        return (1, {"repair_confidence": round(repair_conf, 2),
                    "overall_success_rate": round(overall_success_rate, 2),
                    "type_success_rate": round(type_success_rate, 2),
                    "attempts_success_rate": round(attempts_success_rate, 2),
                    "total_fixes": total_fixes,
                    "successful_fixes": successful}, None)

    def RuntimeConfidence(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='observation' AND properties LIKE '%\"observation_type\":\"confirmed\"%'")
        confirmed = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='observation'")
        total_obs = cur.fetchone()[0] or 0
        obs_confidence = (confirmed / total_obs * 100) if total_obs > 0 else 0
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='method'")
        total_methods = cur.fetchone()[0] or 1
        cur.execute("SELECT COUNT(*) FROM nodes WHERE domain='codefix' AND node_type='method' AND properties LIKE '%\"has_run_method\":1%' AND properties LIKE '%\"returns_tuple3\":1%'")
        runtime_ready = cur.fetchone()[0] or 0
        runtime_coverage = (runtime_ready / total_methods * 100) if total_methods > 0 else 0
        runtime_conf = obs_confidence * 0.4 + runtime_coverage * 0.6
        return (1, {"runtime_confidence": round(runtime_conf, 2),
                    "observation_confidence": round(obs_confidence, 2),
                    "runtime_coverage": round(runtime_coverage, 2),
                    "confirmed_observations": confirmed,
                    "total_observations": total_obs,
                    "runtime_ready_methods": runtime_ready}, None)

    def OverallConfidence(self, params):
        p = self.ParseConfidence(params)
        m = self.MatchConfidence(params)
        g = self.GraphConfidence(params)
        r = self.RepairConfidence(params)
        rt = self.RuntimeConfidence(params)
        pv = p[1].get("parse_confidence", 0) if p[0] == 1 else 0
        mv = m[1].get("match_confidence", 0) if m[0] == 1 else 0
        gv = g[1].get("graph_confidence", 0) if g[0] == 1 else 0
        rv = r[1].get("repair_confidence", 0) if r[0] == 1 else 0
        rtv = rt[1].get("runtime_confidence", 0) if rt[0] == 1 else 0
        overall = pv * 0.15 + mv * 0.10 + gv * 0.20 + rv * 0.20 + rtv * 0.35
        return (1, {"overall_confidence": round(overall, 2),
                    "parse": round(pv, 2), "match": round(mv, 2),
                    "graph": round(gv, 2), "repair": round(rv, 2),
                    "runtime": round(rtv, 2)}, None)

    def MigrateCodefix(self, params):
        source_db = self._p(params, "source_db",
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), "dom_graph_work.db"))
        if not os.path.isfile(source_db):
            return (0, None, ("SOURCE_NOT_FOUND", f"source db not found: {source_db}", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()
        src = sqlite3.connect(source_db)
        src.row_factory = sqlite3.Row
        scur = src.cursor()
        migrated = {"files": 0, "classes": 0, "methods": 0, "knowledge": 0,
                    "edges": 0, "attempts": 0, "observations": 0, "snapshots": 0}
        id_map = {}
        scur.execute("SELECT file_id, file_name, path, extension, hash, imports, exports, class_count, method_count, language FROM files")
        for row in scur.fetchall():
            props = json.dumps({"extension": row["extension"], "hash": row["hash"],
                                "imports": row["imports"], "exports": row["exports"],
                                "class_count": row["class_count"], "method_count": row["method_count"],
                                "language": row["language"]})
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, qualified_name, properties, hash, created, updated) "
                "VALUES ('codefix', 'file', ?, ?, ?, ?, ?, ?)",
                (row["file_name"], row["path"], props, row["hash"], self._now(), self._now())
            )
            id_map[("file", row["file_id"])] = cur.lastrowid
            migrated["files"] += 1
        scur.execute("SELECT class_id, class_name, file_id, parent, interfaces, method_count, cyclomatic_complexity FROM classes")
        for row in scur.fetchall():
            parent_id = id_map.get(("file", row["file_id"]))
            props = json.dumps({"parent": row["parent"], "interfaces": row["interfaces"],
                                "method_count": row["method_count"]})
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, parent_node_id, complexity_level, properties, created, updated) "
                "VALUES ('codefix', 'class', ?, ?, ?, ?, ?, ?)",
                (row["class_name"], parent_id, row["cyclomatic_complexity"], props, self._now(), self._now())
            )
            id_map[("class", row["class_id"])] = cur.lastrowid
            migrated["classes"] += 1
        scur.execute("SELECT method_id, method_name, class_id, file_id, method_code, cyclomatic_complexity, line_count, has_print, has_decorator, has_self_underscore, returns_tuple3, is_vbstyle, start_line, end_line FROM methods")
        for row in scur.fetchall():
            parent_id = id_map.get(("class", row["class_id"]))
            props = json.dumps({"file_id": row["file_id"], "line_count": row["line_count"],
                                "has_print": row["has_print"], "has_decorator": row["has_decorator"],
                                "has_self_underscore": row["has_self_underscore"],
                                "returns_tuple3": row["returns_tuple3"],
                                "is_vbstyle": row["is_vbstyle"],
                                "has_run_method": 1 if "def Run" in (row["method_code"] or "") else 0})
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, parent_node_id, content, complexity_level, properties, line_start, line_end, created, updated) "
                "VALUES ('codefix', 'method', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["method_name"], parent_id, row["method_code"],
                 row["cyclomatic_complexity"], props, row["start_line"], row["end_line"],
                 self._now(), self._now())
            )
            id_map[("method", row["method_id"])] = cur.lastrowid
            migrated["methods"] += 1
        scur.execute("SELECT knowledge_id, problem, question, answer, confidence, fix_result, error_type, error_text, stack_trace, fix_applied, method_id, class_id, file_id, tags, created FROM knowledge")
        for row in scur.fetchall():
            props = json.dumps({"question": row["question"], "fix_result": row["fix_result"],
                                "error_type": row["error_type"], "error_text": row["error_text"],
                                "stack_trace": row["stack_trace"], "fix_applied": row["fix_applied"],
                                "method_id": row["method_id"], "class_id": row["class_id"],
                                "file_id": row["file_id"]})
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, description, confidence, properties, domain_tags, created, updated) "
                "VALUES ('codefix', 'knowledge', ?, ?, ?, ?, ?, ?, ?)",
                (row["problem"], row["answer"], row["confidence"], props, row["tags"],
                 row["created"] or self._now(), self._now())
            )
            id_map[("knowledge", row["knowledge_id"])] = cur.lastrowid
            migrated["knowledge"] += 1
        scur.execute("SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type, evidence, confidence FROM edges")
        for row in scur.fetchall():
            src_new = id_map.get((row["src_type"], row["src_id"]), row["src_id"])
            dst_new = id_map.get((row["dst_type"], row["dst_id"]), row["dst_id"])
            cur.execute(
                "INSERT INTO edges (domain, src_node_id, src_type, dst_node_id, dst_type, edge_type, evidence, confidence, created) "
                "VALUES ('codefix', ?, ?, ?, ?, ?, ?, ?, ?)",
                (src_new, row["src_type"], dst_new, row["dst_type"], row["edge_type"],
                 row["evidence"], row["confidence"], self._now())
            )
            migrated["edges"] += 1
        try:
            scur.execute("SELECT attempt_id, method_id, action, before_code, after_code, compile_result, test_result, knowledge_id FROM attempts")
            for row in scur.fetchall():
                parent_id = id_map.get(("method", row["method_id"]))
                props = json.dumps({"compile_result": row["compile_result"], "test_result": row["test_result"],
                                    "knowledge_id": row["knowledge_id"], "before_code": row["before_code"]})
                cur.execute(
                    "INSERT INTO nodes (domain, node_type, name, parent_node_id, content, properties, created, updated) "
                    "VALUES ('codefix', 'attempt', ?, ?, ?, ?, ?, ?)",
                    (row["action"], parent_id, row["after_code"], props, self._now(), self._now())
                )
                migrated["attempts"] += 1
        except sqlite3.Error:
            pass
        try:
            scur.execute("SELECT observation_id, observation_type, subject, evidence, confidence FROM observations")
            for row in scur.fetchall():
                props = json.dumps({"observation_type": row["observation_type"]})
                cur.execute(
                    "INSERT INTO nodes (domain, node_type, name, description, confidence, properties, created, updated) "
                    "VALUES ('codefix', 'observation', ?, ?, ?, ?, ?, ?)",
                    (row["subject"], row["evidence"], row["confidence"], props, self._now(), self._now())
                )
                migrated["observations"] += 1
        except sqlite3.Error:
            pass
        try:
            scur.execute("SELECT snapshot_id, snapshot_type, file_id, class_id, method_id, content, hash, notes, created FROM snapshots")
            for row in scur.fetchall():
                target_id = id_map.get(("file", row["file_id"])) or id_map.get(("method", row["method_id"]))
                cur.execute(
                    "INSERT INTO snapshots (domain, snapshot_type, target_node_id, content, hash, notes, is_active, created) "
                    "VALUES ('codefix', ?, ?, ?, ?, ?, 1, ?)",
                    (row["snapshot_type"], target_id, row["content"], row["hash"],
                     row["notes"], row["created"] or self._now())
                )
                migrated["snapshots"] += 1
        except sqlite3.Error:
            pass
        conn.commit()
        src.close()
        return (1, {"migrated": migrated, "source_db": source_db,
                    "target_db": self.state["config"]["db_path"]}, None)

    def MigrateSession(self, params):
        host = self._p(params, "mysql_host", "localhost")
        user = self._p(params, "mysql_user", "root")
        password = self._p(params, "mysql_pass", "")
        database = self._p(params, "mysql_db", "vb_shared")
        # Try mysql.connector first, fall back to pymysql
        mconn = None
        mcur = None
        try:
            import mysql.connector
            mconn = mysql.connector.connect(host=host, user=user, password=password, database=database)
            mcur = mconn.cursor(dictionary=True)
        except ImportError:
            try:
                import pymysql
                mconn = pymysql.connect(host=host, user=user, password=password, database=database)
                mcur = mconn.cursor(pymysql.cursors.DictCursor)
            except ImportError:
                return (0, None, ("NO_MYSQL_DRIVER",
                                  "Neither mysql.connector nor pymysql is installed. "
                                  "Install one: pip install mysql-connector-python OR pip install pymysql", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()
        migrated = {"session_graphs": 0, "session_paths": 0,
                    "session_resume_points": 0, "edges": 0}
        id_map = {}
        mcur.execute(
            "SELECT id, session_id, session_date, main_thread, main_progress, "
            "main_status, resume_action, created_at, updated_at FROM session_graphs"
        )
        for row in mcur.fetchall():
            status_val = (row["main_status"] or "IN_PROGRESS").lower()
            props = json.dumps({
                "session_date": str(row["session_date"]) if row["session_date"] else None,
                "resume_action": row["resume_action"],
            })
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, description, confidence, "
                "status, properties, created, updated) "
                "VALUES ('session', 'session', ?, ?, ?, ?, ?, ?, ?)",
                (row["session_id"], row["main_thread"], row["main_progress"] or 0,
                 status_val, props,
                 str(row["created_at"]) if row["created_at"] else self._now(),
                 str(row["updated_at"]) if row["updated_at"] else self._now())
            )
            id_map[("session", row["session_id"])] = cur.lastrowid
            migrated["session_graphs"] += 1
        mcur.execute(
            "SELECT id, session_id, path_type, path_name, path_status, progress, "
            "trigger_reason, time_cost_min, was_worth_it, parent_path, sort_order, "
            "notes, created_at FROM session_paths"
        )
        for row in mcur.fetchall():
            parent_node_id = id_map.get(("session", row["session_id"]))
            props = json.dumps({
                "trigger_reason": row["trigger_reason"],
                "time_cost_min": row["time_cost_min"],
                "was_worth_it": row["was_worth_it"],
                "sort_order": row["sort_order"],
            })
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, parent_node_id, domain_tags, "
                "status, confidence, properties, content, created, updated) "
                "VALUES ('session', 'path', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["path_name"], parent_node_id, row["path_type"],
                 (row["path_status"] or "IN_PROGRESS").lower(),
                 row["progress"] or 0, props, row["notes"],
                 str(row["created_at"]) if row["created_at"] else self._now(),
                 self._now())
            )
            id_map[("path", row["id"])] = cur.lastrowid
            migrated["session_paths"] += 1
        mcur.execute(
            "SELECT session_id, path_name, parent_path FROM session_paths "
            "WHERE parent_path IS NOT NULL AND parent_path <> ''"
        )
        for row in mcur.fetchall():
            session_node_id = id_map.get(("session", row["session_id"]))
            if not session_node_id:
                continue
            cur.execute(
                "SELECT node_id FROM nodes WHERE domain='session' AND node_type='path' "
                "AND name=? AND parent_node_id=?",
                (row["path_name"], session_node_id)
            )
            child_row = cur.fetchone()
            cur.execute(
                "SELECT node_id FROM nodes WHERE domain='session' AND node_type='path' "
                "AND name=? AND parent_node_id=?",
                (row["parent_path"], session_node_id)
            )
            parent_row = cur.fetchone()
            if child_row and parent_row:
                cur.execute(
                    "INSERT INTO edges (domain, src_node_id, src_type, dst_node_id, "
                    "dst_type, edge_type, created) "
                    "VALUES ('session', ?, 'path', ?, 'path', 'parent_of', ?)",
                    (child_row[0], parent_row[0], self._now())
                )
                migrated["edges"] += 1
        mcur.execute(
            "SELECT id, session_id, project_name, progress, state, resume_action, "
            "is_active, created_at, updated_at FROM session_resume_points"
        )
        for row in mcur.fetchall():
            content = row["resume_action"] or ""
            hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            notes = json.dumps({"session_id": row["session_id"]})
            cur.execute(
                "INSERT INTO snapshots (domain, snapshot_type, project_name, progress, "
                "state, resume_action, content, hash, notes, is_active, created) "
                "VALUES ('session', 'resume_point', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["project_name"], row["progress"] or 0, row["state"],
                 row["resume_action"], content, hash_val, notes,
                 row["is_active"] if row["is_active"] is not None else 1,
                 str(row["updated_at"]) if row["updated_at"] else self._now())
            )
            migrated["session_resume_points"] += 1
        conn.commit()
        mcur.close()
        mconn.close()
        return (1, {"migrated": migrated, "source_db": "mysql:" + database,
                    "target_db": self.state["config"]["db_path"]}, None)


    def Gc(self, params):
        """Garbage collector: drop all tables and recreate clean schema.
        Like DomSystem._cmd_gc — marks stale data for cleanup, then rebuilds.
        Use this instead of rm to reset the unified DB."""
        conn = self._get_conn()
        cur = conn.cursor()
        dropped = []
        for table in ("decisions", "snapshots", "edges", "rules", "nodes"):
            try:
                cur.execute("DROP TABLE IF EXISTS " + table)
                dropped.append(table)
            except sqlite3.Error:
                pass
        conn.commit()
        for sql in SCHEMA_SQL:
            cur.execute(sql)
        conn.commit()
        self.state["candidates"] = []
        self.state["filtered"] = []
        self.state["triggered"] = []
        self.state["resolved"] = []
        self.state["scored"] = []
        self.state["decision"] = None
        self.state["reason_trace"] = []
        self.state["stats"] = {"decisions_made": 0, "candidates_evaluated": 0}
        return (1, {"dropped": dropped, "schema_recreated": True, "message": "GC complete — clean schema ready for migration"}, None)

    def Stats(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        counts = {}
        for domain in ("codefix", "gui", "session"):
            cur.execute("SELECT COUNT(*) FROM nodes WHERE domain=?", (domain,))
            counts[f"nodes_{domain}"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edges WHERE domain=?", (domain,))
            counts[f"edges_{domain}"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM decisions WHERE domain=?", (domain,))
            counts[f"decisions_{domain}"] = cur.fetchone()[0]
        return (1, {"counts": counts, "stats": self.state["stats"],
                    "db_path": self.state["config"]["db_path"]}, None)

    def OpenSession(self, params):
        session_id = self._p(params, "session_id")
        main_thread = self._p(params, "main_thread")
        if not session_id or not main_thread:
            return (0, None, ("MISSING_PARAM", "session_id and main_thread required", 0))
        session_date = self._p(params, "session_date", date.today().isoformat())
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT node_id FROM nodes WHERE domain='session' AND node_type='session' AND name=?",
            (session_id,)
        )
        row = cur.fetchone()
        props = json.dumps({"session_date": session_date, "resume_action": None})
        if row:
            cur.execute(
                "UPDATE nodes SET description=?, status='in_progress', properties=?, updated=? "
                "WHERE node_id=?",
                (main_thread, props, self._now(), row[0])
            )
            session_node_id = row[0]
        else:
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, description, confidence, "
                "status, properties, created, updated) "
                "VALUES ('session', 'session', ?, ?, 0, 'in_progress', ?, ?, ?)",
                (session_id, main_thread, props, self._now(), self._now())
            )
            session_node_id = cur.lastrowid
        cur.execute(
            "SELECT node_id FROM nodes WHERE domain='session' AND node_type='path' "
            "AND parent_node_id=? AND name=?",
            (session_node_id, main_thread)
        )
        prow = cur.fetchone()
        path_props = json.dumps({"sort_order": 0, "trigger_reason": None,
                                 "time_cost_min": 0, "was_worth_it": "UNKNOWN"})
        if prow:
            cur.execute(
                "UPDATE nodes SET status='in_progress', properties=?, updated=? WHERE node_id=?",
                (path_props, self._now(), prow[0])
            )
        else:
            cur.execute(
                "INSERT INTO nodes (domain, node_type, name, parent_node_id, domain_tags, "
                "status, confidence, properties, created, updated) "
                "VALUES ('session', 'path', ?, ?, 'MAIN', 'in_progress', 0, ?, ?, ?)",
                (main_thread, session_node_id, path_props, self._now(), self._now())
            )
        conn.commit()
        self.state["current_session"] = session_id
        return (1, {"session_id": session_id, "main_thread": main_thread,
                    "status": "in_progress"}, None)

    def AddPath(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        path_type = self._p(params, "path_type")
        path_name = self._p(params, "path_name")
        if not session_id or not path_type or not path_name:
            return (0, None, ("MISSING_PARAM", "session_id, path_type, path_name required", 0))
        path_status = self._p(params, "path_status", "IN_PROGRESS")
        progress = self._p(params, "progress", 0)
        trigger = self._p(params, "trigger")
        time_cost = self._p(params, "time_cost_min", 0)
        worth_it = self._p(params, "was_worth_it", "UNKNOWN")
        parent = self._p(params, "parent_path")
        sort_order = self._p(params, "sort_order", 99)
        notes = self._p(params, "notes")
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT node_id FROM nodes WHERE domain='session' AND node_type='session' AND name=?",
            (session_id,)
        )
        srow = cur.fetchone()
        if not srow:
            return (0, None, ("NOT_FOUND", "session not found: " + str(session_id), 0))
        session_node_id = srow[0]
        props = json.dumps({"trigger_reason": trigger, "time_cost_min": time_cost,
                            "was_worth_it": worth_it, "sort_order": sort_order})
        cur.execute(
            "INSERT INTO nodes (domain, node_type, name, parent_node_id, domain_tags, "
            "status, confidence, properties, content, created, updated) "
            "VALUES ('session', 'path', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path_name, session_node_id, path_type, path_status.lower(), progress,
             props, notes, self._now(), self._now())
        )
        path_node_id = cur.lastrowid
        if parent:
            cur.execute(
                "SELECT node_id FROM nodes WHERE domain='session' AND node_type='path' "
                "AND parent_node_id=? AND name=?",
                (session_node_id, parent)
            )
            prow = cur.fetchone()
            if prow:
                cur.execute(
                    "INSERT INTO edges (domain, src_node_id, src_type, dst_node_id, "
                    "dst_type, edge_type, created) "
                    "VALUES ('session', ?, 'path', ?, 'path', 'parent_of', ?)",
                    (path_node_id, prow[0], self._now())
                )
        conn.commit()
        return (1, {"path_id": path_node_id, "path_name": path_name,
                    "path_type": path_type, "path_status": path_status}, None)

    def UpdatePath(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        path_name = self._p(params, "path_name")
        if not session_id or not path_name:
            return (0, None, ("MISSING_PARAM", "session_id and path_name required", 0))
        path_status = self._p(params, "path_status")
        progress = self._p(params, "progress")
        worth_it = self._p(params, "was_worth_it")
        notes = self._p(params, "notes")
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT node_id, properties FROM nodes WHERE domain='session' AND node_type='path' "
            "AND parent_node_id=(SELECT node_id FROM nodes WHERE domain='session' "
            "AND node_type='session' AND name=?) AND name=?",
            (session_id, path_name)
        )
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Path not found: " + str(path_name), 0))
        node_id = row[0]
        props = {}
        if row[1]:
            try:
                props = json.loads(row[1])
            except (json.JSONDecodeError, TypeError):
                props = {}
        sets = ["updated=?"]
        vals = [self._now()]
        if path_status:
            sets.append("status=?")
            vals.append(path_status.lower())
        if progress is not None:
            sets.append("confidence=?")
            vals.append(progress)
        if worth_it:
            props["was_worth_it"] = worth_it
        if notes:
            sets.append("content=?")
            vals.append(notes)
        sets.append("properties=?")
        vals.append(json.dumps(props))
        vals.append(node_id)
        cur.execute(
            "UPDATE nodes SET " + ", ".join(sets) + " WHERE node_id=?", vals
        )
        conn.commit()
        return (1, {"path_name": path_name, "updated": True}, None)

    def AddResume(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        project_name = self._p(params, "project_name")
        resume_action = self._p(params, "resume_action")
        if not session_id or not project_name or not resume_action:
            return (0, None, ("MISSING_PARAM", "session_id, project_name, resume_action required", 0))
        progress = self._p(params, "progress", 0)
        state_val = self._p(params, "state", "STALLED")
        conn = self._get_conn()
        cur = conn.cursor()
        hash_val = hashlib.sha256(resume_action.encode("utf-8")).hexdigest()[:16]
        notes = json.dumps({"session_id": session_id})
        cur.execute(
            "SELECT snapshot_id FROM snapshots WHERE domain='session' "
            "AND snapshot_type='resume_point' AND project_name=? AND is_active=1",
            (project_name,)
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE snapshots SET progress=?, state=?, resume_action=?, content=?, "
                "hash=?, notes=?, created=? WHERE snapshot_id=?",
                (progress, state_val, resume_action, resume_action, hash_val,
                 notes, self._now(), row[0])
            )
        else:
            cur.execute(
                "INSERT INTO snapshots (domain, snapshot_type, project_name, progress, "
                "state, resume_action, content, hash, notes, is_active, created) "
                "VALUES ('session', 'resume_point', ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (project_name, progress, state_val, resume_action, resume_action,
                 hash_val, notes, self._now())
            )
        conn.commit()
        return (1, {"project_name": project_name, "progress": progress,
                    "state": state_val, "resume_action": resume_action}, None)

    def GetResume(self, params):
        project_name = self._p(params, "project_name")
        if not project_name:
            return (0, None, ("MISSING_PARAM", "project_name required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM snapshots WHERE domain='session' "
            "AND snapshot_type='resume_point' AND project_name=? AND is_active=1 "
            "ORDER BY created DESC LIMIT 1",
            (project_name,)
        )
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "No resume point for: " + str(project_name), 0))
        result = dict(row)
        if result.get("notes"):
            try:
                result["session_id"] = json.loads(result["notes"]).get("session_id")
            except (json.JSONDecodeError, TypeError):
                pass
        return (1, result, None)

    def Render(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        if not session_id:
            return (0, None, ("MISSING_PARAM", "session_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM nodes WHERE domain='session' AND node_type='session' AND name=?",
            (session_id,)
        )
        graph = cur.fetchone()
        if not graph:
            return (0, None, ("NOT_FOUND", "Session not found: " + str(session_id), 0))
        graph = dict(graph)
        cur.execute(
            "SELECT * FROM nodes WHERE domain='session' AND node_type='path' "
            "AND parent_node_id=? ORDER BY node_id",
            (graph["node_id"],)
        )
        paths = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT * FROM snapshots WHERE domain='session' "
            "AND snapshot_type='resume_point' AND is_active=1 AND notes LIKE ? "
            "ORDER BY project_name",
            ('%"session_id":"' + session_id + '"%',)
        )
        resumes = [dict(r) for r in cur.fetchall()]
        lines = []
        lines.append("SESSION: " + str(session_id) + " — " + str(graph.get("description") or ""))
        lines.append("")
        for path in paths:
            props = {}
            if path.get("properties"):
                try:
                    props = json.loads(path["properties"])
                except (json.JSONDecodeError, TypeError):
                    props = {}
            ptype = path.get("domain_tags") or ""
            pname = path.get("name") or ""
            pstatus = path.get("status") or ""
            progress = int(path.get("confidence") or 0)
            bar_len = 40
            filled = int(progress / 100 * bar_len)
            bar = "#" * filled + "." * (bar_len - filled)
            pct = str(progress) + "%"
            lines.append("  [" + str(ptype) + "] " + str(pname))
            lines.append("    [" + bar + "] " + pct + " " + str(pstatus))
            if props.get("trigger_reason"):
                lines.append("    trigger: " + str(props["trigger_reason"]))
            worth = props.get("was_worth_it", "UNKNOWN")
            if worth and worth != "UNKNOWN":
                lines.append("    worth it: " + str(worth))
            if path.get("content"):
                lines.append("    notes: " + str(path["content"]))
            lines.append("")
        if resumes:
            lines.append("RESUME POINTS:")
            for r in resumes:
                lines.append("  " + str(r.get("project_name") or "") + " (" +
                             str(r.get("progress") or 0) + "%, " + str(r.get("state") or "") + ")")
                lines.append("    -> " + str(r.get("resume_action") or ""))
                lines.append("")
        return (1, "\n".join(lines), None)

    def Dashboard(self, params):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT project_name, progress, state, resume_action FROM snapshots "
            "WHERE domain='session' AND snapshot_type='resume_point' AND is_active=1 "
            "ORDER BY project_name"
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return (1, "No active projects tracked.", None)
        lines = []
        lines.append("PROJECT DASHBOARD")
        lines.append("=" * 60)
        for row in rows:
            progress = int(row.get("progress") or 0)
            bar_len = 40
            filled = int(progress / 100 * bar_len)
            bar = "#" * filled + "." * (bar_len - filled)
            lines.append("  " + str(row.get("project_name") or ""))
            lines.append("    [" + bar + "] " + str(progress) + "% " + str(row.get("state") or ""))
            lines.append("    resume: " + str(row.get("resume_action") or ""))
            lines.append("")
        return (1, "\n".join(lines), None)

    def CloseSession(self, params):
        session_id = self._p(params, "session_id", self.state.get("current_session"))
        if not session_id:
            return (0, None, ("MISSING_PARAM", "session_id required", 0))
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE nodes SET status='closed', updated=? "
            "WHERE domain='session' AND node_type='session' AND name=?",
            (self._now(), session_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            return (0, None, ("NOT_FOUND", "Session not found: " + str(session_id), 0))
        self.state["current_session"] = None
        return (1, {"session_id": session_id, "status": "closed"}, None)

    def ListSessions(self, params):
        limit = self._p(params, "limit", 20)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT node_id, name, description, status, confidence, properties, created "
            "FROM nodes WHERE domain='session' AND node_type='session' "
            "ORDER BY created DESC LIMIT ?",
            (limit,)
        )
        rows = []
        for r in cur.fetchall():
            entry = dict(r)
            props = {}
            if entry.get("properties"):
                try:
                    props = json.loads(entry["properties"])
                except (json.JSONDecodeError, TypeError):
                    props = {}
            rows.append({
                "session_id": entry.get("name"),
                "session_date": props.get("session_date"),
                "main_thread": entry.get("description"),
                "main_status": entry.get("status"),
                "main_progress": entry.get("confidence"),
            })
        return (1, rows, None)
