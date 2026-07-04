#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/sql_analyzer.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 39 SQL Analyzer"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="sql_analyzer.py" domain="twin_sqlanalyzer" authority="SqlAnalyzer"}
# [@SUMMARY]{summary="SQL analyzer authority that logs queries, explains plans, finds slow queries, suggests indexes, and tracks transaction history."}
# [@CLASS]{class="SqlAnalyzer" domain="sqlanalyzer" authority="single"}
# [@METHOD]{method="log_query" type="command"}
# [@METHOD]{method="explain_plan" type="command"}
# [@METHOD]{method="find_slow" type="command"}
# [@METHOD]{method="suggest_indexes" type="command"}
# [@METHOD]{method="transaction_history" type="command"}
# [@METHOD]{method="table_usage" type="command"}
# [@METHOD]{method="lock_analysis" type="command"}
# [@METHOD]{method="deadlock_analysis" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<SqlAnalyzer: logs queries explains plans finds slow queries suggests indexes tracks transaction history. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
SqlAnalyzer -- SQL analysis authority.
Implements Section 39 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: log_query, explain_plan, find_slow, suggest_indexes,
          transaction_history, table_usage, lock_analysis, deadlock_analysis.
"""
import os
import re
import json
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
SLOW_THRESHOLD_MS = 100


class SqlAnalyzer:
    """SQL analysis authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "log_query":
            return self.LogQuery(params)
        elif command == "explain_plan":
            return self.ExplainPlan(params)
        elif command == "find_slow":
            return self.FindSlow(params)
        elif command == "suggest_indexes":
            return self.SuggestIndexes(params)
        elif command == "transaction_history":
            return self.TransactionHistory(params)
        elif command == "table_usage":
            return self.TableUsage(params)
        elif command == "lock_analysis":
            return self.LockAnalysis(params)
        elif command == "deadlock_analysis":
            return self.DeadlockAnalysis(params)

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
        return self.state["db_conn"]

    def LogQuery(self, params):
        # 39.1 Query History: log every execute() call into observations
        query = self._p(params, "query", "")
        duration = self._p(params, "duration_ms", 0)
        params_used = self._p(params, "params")
        if not query:
            return (0, None, ("NO_PARAM", "query required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        evidence = json.dumps({"duration_ms": duration, "params": params_used,
                               "slow": duration > SLOW_THRESHOLD_MS})
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("sql_query", query[:500], evidence, 50, now))
        conn.commit()
        return (1, {"logged": True, "slow": duration > SLOW_THRESHOLD_MS}, None)

    def ExplainPlan(self, params):
        # 39.2 Query Plan: EXPLAIN QUERY PLAN <sql>
        sql = self._p(params, "sql", "")
        if not sql:
            return (0, None, ("NO_PARAM", "sql required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("EXPLAIN QUERY PLAN " + sql)
            rows = cur.fetchall()
            plan = []
            for r in rows:
                plan.append({"id": r[0], "parent": r[1], "notused": r[2], "detail": r[3]})
            # detect table scans (no index usage)
            uses_scan = any("SCAN" in str(p["detail"]).upper() for p in plan)
            uses_index = any("SEARCH" in str(p["detail"]).upper() or "INDEX" in str(p["detail"]).upper() for p in plan)
            return (1, {"plan": plan, "uses_scan": uses_scan,
                        "uses_index": uses_index, "raw": rows}, None)
        except Exception as exc:
            return (0, None, ("QUERY_ERROR", str(exc), 0))

    def FindSlow(self, params):
        # 39.3 Slow Queries: queries taking > 100ms + methods with SQL lacking indexes
        conn = self.Connect()
        cur = conn.cursor()
        # slow queries from observations log
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='sql_query' ORDER BY created DESC")
        slow = []
        for r in cur.fetchall():
            try:
                payload = json.loads(r[2]) if r[2] else {}
            except Exception:
                payload = {}
            duration = payload.get("duration_ms", 0)
            if duration and duration > SLOW_THRESHOLD_MS:
                slow.append({"observation_id": r[0], "query": r[1],
                             "duration_ms": duration, "created": r[3]})
        # find methods with SQL in method_code that lack indexes
        cur.execute("SELECT method_id, method_name, method_code FROM methods "
                    "WHERE method_code LIKE '%execute%' OR method_code LIKE '%SELECT%' "
                    "OR method_code LIKE '%INSERT%' OR method_code LIKE '%UPDATE%'")
        sql_methods = []
        for r in cur.fetchall():
            code = r[2] or ""
            has_where = "WHERE" in code.upper()
            has_index_hint = "INDEXED BY" in code.upper()
            sql_methods.append({
                "method_id": r[0], "method_name": r[1],
                "has_where": has_where, "has_index_hint": has_index_hint,
                "potential_slow": has_where and not has_index_hint,
            })
        return (1, {"slow_queries": slow, "slow_count": len(slow),
                    "sql_methods": sql_methods, "method_count": len(sql_methods)}, None)

    def SuggestIndexes(self, params):
        # 39.4 Missing Indexes: analyze table schema and suggest indexes for common query patterns
        conn = self.Connect()
        cur = conn.cursor()
        # get existing indexes
        cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
        existing = {}
        for r in cur.fetchall():
            existing.setdefault(r[1], set()).add(r[0])
        # get table schemas
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        suggestions = []
        for tbl_name, tbl_sql in tables:
            if tbl_name.startswith("sqlite_") or tbl_name.startswith("knowledge_fts"):
                continue
            # parse columns from CREATE TABLE
            cols = self.ExtractColumns(tbl_sql)
            # get primary key columns
            cur.execute("PRAGMA table_info(" + tbl_name + ")")
            pk_cols = set()
            indexed_cols = set()
            for col_info in cur.fetchall():
                if col_info[5]:  # pk flag
                    pk_cols.add(col_info[1])
            # get existing indexed columns
            cur.execute("PRAGMA index_list(" + tbl_name + ")")
            for idx in cur.fetchall():
                cur.execute("PRAGMA index_info(" + idx[1] + ")")
                for ic in cur.fetchall():
                    indexed_cols.add(ic[2])
            # suggest indexes on non-PK, non-indexed columns frequently used in WHERE
            cur.execute("SELECT subject, evidence FROM observations WHERE observation_type='sql_query'")
            where_cols = {}
            for qrow in cur.fetchall():
                query_text = qrow[0]
                if tbl_name in query_text:
                    wcols = self.ExtractWhereColumns(query_text)
                    for wc in wcols:
                        if wc in cols and wc not in pk_cols and wc not in indexed_cols:
                            where_cols[wc] = where_cols.get(wc, 0) + 1
            for col, freq in where_cols.items():
                if freq > 0:
                    suggestions.append({
                        "table": tbl_name, "column": col, "frequency": freq,
                        "suggestion": "CREATE INDEX idx_" + tbl_name + "_" + col +
                                      " ON " + tbl_name + "(" + col + ")",
                    })
        suggestions.sort(key=lambda x: x["frequency"], reverse=True)
        return (1, {"suggestions": suggestions[:30], "existing_indexes": existing,
                    "table_count": len(tables)}, None)

    def ExtractColumns(self, create_sql):
        # helper: extract column names from CREATE TABLE statement
        if not create_sql:
            return []
        match = re.search(r"\((.*)\)", create_sql, re.DOTALL)
        if not match:
            return []
        body = match.group(1)
        cols = []
        for line in body.split(","):
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT")):
                continue
            parts = line.split()
            if parts:
                cols.append(parts[0].strip('"`[]'))
        return cols

    def ExtractWhereColumns(self, query):
        # helper: extract column names from WHERE clause
        upper = query.upper()
        idx = upper.find("WHERE")
        if idx < 0:
            return []
        where_part = query[idx + 5:]
        # stop at ORDER BY / GROUP BY / LIMIT
        for stopper in ("ORDER BY", "GROUP BY", "LIMIT", "HAVING"):
            sidx = where_part.upper().find(stopper)
            if sidx >= 0:
                where_part = where_part[:sidx]
        cols = re.findall(r"(\w+)\s*(=|LIKE|IN|>|<|>=|<=|!=|IS)", where_part)
        return [c[0] for c in cols if not c[0].isdigit()]

    def TransactionHistory(self, params):
        # 39.6 Transaction History: SELECT from observations WHERE subject LIKE '%transaction%'
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='transaction' OR subject LIKE '%transaction%' "
                    "ORDER BY created DESC")
        results = []
        for r in cur.fetchall():
            try:
                results.append({"observation_id": r[0], "subject": r[1],
                                "data": json.loads(r[2]), "created": r[3]})
            except Exception:
                results.append({"observation_id": r[0], "subject": r[1],
                                "evidence": r[2], "created": r[3]})
        return (1, {"history": results, "count": len(results)}, None)

    def TableUsage(self, params):
        # 39.5 Table Usage: find database access edges + count queries per table
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE edge_type='database_access'")
        edge_rows = cur.fetchall()
        # count which tables appear in logged queries
        cur.execute("SELECT subject FROM observations WHERE observation_type='sql_query'")
        table_counts = {}
        for r in cur.fetchall():
            query = (r[0] or "").upper()
            cur2 = conn.cursor()
            cur2.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for trow in cur2.fetchall():
                tname = trow[0].upper()
                if tname in query and not tname.startswith("SQLITE_"):
                    table_counts[trow[0]] = table_counts.get(trow[0], 0) + 1
        usage = [{"table": k, "query_count": v} for k, v in table_counts.items()]
        usage.sort(key=lambda x: x["query_count"], reverse=True)
        return (1, {"table_usage": usage, "database_access_edges": len(edge_rows)}, None)

    def LockAnalysis(self, params):
        # 39.7 Lock Analysis: check for potential deadlocks by analyzing transaction patterns
        conn = self.Connect()
        cur = conn.cursor()
        # look for 'database is locked' errors in knowledge
        cur.execute("SELECT knowledge_id, problem, error_text, created FROM knowledge "
                    "WHERE error_text LIKE '%locked%' OR problem LIKE '%locked%' "
                    "ORDER BY created DESC")
        lock_errors = []
        for r in cur.fetchall():
            lock_errors.append({"knowledge_id": r[0], "problem": r[1],
                                "error_text": r[2], "created": r[3]})
        # analyze transaction patterns: long-running transactions risk locks
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='transaction' ORDER BY created DESC")
        transactions = []
        for r in cur.fetchall():
            try:
                payload = json.loads(r[2]) if r[2] else {}
            except Exception:
                payload = {}
            transactions.append({"observation_id": r[0], "subject": r[1],
                                 "data": payload, "created": r[3]})
        risk_score = min(100, len(lock_errors) * 20 + len(transactions) * 2)
        return (1, {"lock_errors": lock_errors, "lock_error_count": len(lock_errors),
                    "transactions": transactions, "risk_score": risk_score}, None)

    def DeadlockAnalysis(self, params):
        # 39.8 Deadlock Analysis: detect deadlock patterns in transaction history
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='transaction' ORDER BY created")
        txns = []
        for r in cur.fetchall():
            try:
                payload = json.loads(r[2]) if r[2] else {}
            except Exception:
                payload = {}
            txns.append({"observation_id": r[0], "subject": r[1],
                         "data": payload, "created": r[3]})
        # detect potential deadlock: transactions locking same tables in different order
        table_lock_order = []
        for t in txns:
            tables = t["data"].get("tables", []) if isinstance(t["data"], dict) else []
            if len(tables) > 1:
                table_lock_order.append({"txn": t["observation_id"], "order": tables})
        deadlocks = []
        for i in range(len(table_lock_order)):
            for j in range(i + 1, len(table_lock_order)):
                a = table_lock_order[i]["order"]
                b = table_lock_order[j]["order"]
                common = set(a) & set(b)
                if common and a != b:
                    deadlocks.append({
                        "txn_a": table_lock_order[i]["txn"],
                        "txn_b": table_lock_order[j]["txn"],
                        "order_a": a, "order_b": b,
                        "common_tables": list(common),
                    })
        return (1, {"potential_deadlocks": deadlocks,
                    "deadlock_count": len(deadlocks),
                    "transactions_analyzed": len(txns)}, None)

