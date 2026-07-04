# [@GHOST]{[@file<stats_report.py>][@domain<utility>][@role<universal_reporter>][@auth<cascade>][@date<2026-07-02>][@ver<2.0.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<universal_reporter>][@return<tuple3>][@orch<VbsMain>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Universal SQLite report engine — any DB, any query, any format. Replaces domain-specific reporters.}
# [@WCL]{[@self_contained<true>][@input<sqlite_db>][@output<markdown|json|csv|text>][@commands<run_query|format_table|summary|schema|top_n|group_by|duplicates|full_report|export>]}
# [@CLASS]{StatsReport}
# [@METHOD]{Run,run_query,format_table,summary,schema,top_n,group_by,duplicates,full_report,export,read_state,set_config}

"""
StatsReport — Universal SQLite Report Engine
=============================================
Works with ANY SQLite database. Not tied to file indexes, code structure,
provenance, or any specific schema.

Give it a DB path and a SQL query, get formatted output.
Auto-discovers tables, columns, row counts.
Formats: markdown, JSON, CSV, text.

Usage:
    from core.utility.stats_report import StatsReport

    rpt = StatsReport()

    # Run any query on any DB
    ok, rows, err = rpt.Run("run_query", {"db_path": "/path/to/db.sqlite", "sql": "SELECT * FROM files LIMIT 10"})

    # Format rows as markdown table
    ok, markdown, err = rpt.Run("format_table", {"rows": rows, "format": "markdown"})

    # Auto-summary of entire DB
    ok, report, err = rpt.Run("summary", {"db_path": "/path/to/db.sqlite"})

    # Top N by column
    ok, data, err = rpt.Run("top_n", {"db_path": "/path/to/db.sqlite", "table": "files", "column": "size_bytes", "n": 20, "order": "desc"})

    # Group by with aggregation
    ok, data, err = rpt.Run("group_by", {"db_path": "/path/to/db.sqlite", "table": "files", "group_col": "category", "agg_col": "size_bytes", "agg_func": "sum"})

    # Find duplicates
    ok, data, err = rpt.Run("duplicates", {"db_path": "/path/to/db.sqlite", "table": "files", "column": "md5"})

    # Full report — all tables, all stats
    ok, report, err = rpt.Run("full_report", {"db_path": "/path/to/db.sqlite"})

    # Export query results to file
    ok, data, err = rpt.Run("export", {"db_path": "/path/to/db.sqlite", "sql": "SELECT * FROM files", "format": "csv", "dest_path": "/tmp/export.csv"})
"""

import os
import csv
import json
import sqlite3
import datetime


class StatsReport:
    """Universal SQLite report engine.

    self.state holds runtime config and last report cache:
        state['config']: default format, max rows, db_path
        state['last_report']: last generated report string
        state['last_rows']: last query result rows
        state['stats']: operation counters
    """

    FORMATS = ("markdown", "json", "csv", "text")
    AGG_FUNCS = ("count", "sum", "avg", "min", "max")

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "default_format": "markdown",
                "max_rows": 1000,
                "default_db": "",
            },
            "last_report": "",
            "last_rows": [],
            "stats": {
                "queries": 0,
                "reports": 0,
                "exports": 0,
                "errors": 0,
            },
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
        if db:
            self.state["config"]["default_db"] = db

    def Run(self, command, params=None):
        dispatch = {
            "run_query": self.run_query,
            "format_table": self.format_table,
            "summary": self.summary,
            "schema": self.schema,
            "top_n": self.top_n,
            "group_by": self.group_by,
            "duplicates": self.duplicates,
            "full_report": self.full_report,
            "export": self.export,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    # ================================================================
    # CORE QUERY ENGINE
    # ================================================================

    def run_query(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        sql = self._p(params, "sql")
        args = self._p(params, "args", [])
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        if not sql:
            return (0, None, ("ERR_SQL", "sql parameter required", 0))
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql, args or [])
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            conn.close()
            row_dicts = [dict(r) for r in rows]
            self.state["last_rows"] = row_dicts
            self.state["stats"]["queries"] += 1
            return (1, {"columns": columns, "rows": row_dicts, "count": len(row_dicts)}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_QUERY", str(e), 0))

    def format_table(self, params):
        rows = self._p(params, "rows", self.state["last_rows"])
        fmt = self._p(params, "format", self.state["config"]["default_format"])
        columns = self._p(params, "columns")
        if not rows:
            return (0, None, ("ERR_EMPTY", "no rows to format", 0))
        if fmt not in self.FORMATS:
            return (0, None, ("ERR_FORMAT", f"unsupported: {fmt}. valid: {self.FORMATS}", 0))
        if not columns:
            columns = list(rows[0].keys()) if rows else []
        if fmt == "markdown":
            text = self._format_markdown(columns, rows)
        elif fmt == "csv":
            text = self._format_csv(columns, rows)
        elif fmt == "json":
            text = self._format_json(columns, rows)
        else:
            text = self._format_text(columns, rows)
        self.state["last_report"] = text
        self.state["stats"]["reports"] += 1
        return (1, text, None)

    # ================================================================
    # AUTO-DISCOVERY
    # ================================================================

    def summary(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]
            table_info = []
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                count = cur.fetchone()[0]
                cur.execute(f"PRAGMA table_info([{t}])")
                cols = [r[1] for r in cur.fetchall()]
                table_info.append({"table": t, "rows": count, "columns": cols})
            conn.close()
            self.state["stats"]["reports"] += 1
            return (1, {"db_path": db_path, "tables": table_info, "table_count": len(tables)}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_DB", str(e), 0))

    def schema(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        table = self._p(params, "table")
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        if not table:
            return (0, None, ("ERR_TABLE", "table parameter required", 0))
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info([{table}])")
            cols = []
            for r in cur.fetchall():
                cols.append({"name": r[1], "type": r[2], "notnull": r[3], "default": r[4], "pk": r[5]})
            cur.execute(f"PRAGMA index_list([{table}])")
            indexes = [dict(zip(["seq", "name", "unique", "origin", "partial"], r)) for r in cur.fetchall()]
            conn.close()
            return (1, {"table": table, "columns": cols, "indexes": indexes}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_DB", str(e), 0))

    # ================================================================
    # ANALYSIS
    # ================================================================

    def top_n(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        table = self._p(params, "table")
        column = self._p(params, "column")
        n = self._p(params, "n", 10)
        order = self._p(params, "order", "desc")
        extra_cols = self._p(params, "extra_cols", "*")
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        if not table or not column:
            return (0, None, ("ERR_PARAMS", "table and column required", 0))
        if order not in ("asc", "desc"):
            order = "desc"
        sql = f"SELECT {extra_cols} FROM [{table}] ORDER BY [{column}] {order.upper()} LIMIT ?"
        ok, data, err = self.run_query({"db_path": db_path, "sql": sql, "args": [n]})
        if not ok:
            return (ok, None, err)
        self.state["stats"]["reports"] += 1
        return (1, data, None)

    def group_by(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        table = self._p(params, "table")
        group_col = self._p(params, "group_col")
        agg_col = self._p(params, "agg_col", "*")
        agg_func = self._p(params, "agg_func", "count")
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        if not table or not group_col:
            return (0, None, ("ERR_PARAMS", "table and group_col required", 0))
        if agg_func not in self.AGG_FUNCS:
            return (0, None, ("ERR_AGG", f"unsupported: {agg_func}. valid: {self.AGG_FUNCS}", 0))
        sql = f"SELECT [{group_col}], {agg_func.upper()}([{agg_col}]) as agg_value FROM [{table}] GROUP BY [{group_col}] ORDER BY agg_value DESC"
        ok, data, err = self.run_query({"db_path": db_path, "sql": sql})
        if not ok:
            return (ok, None, err)
        self.state["stats"]["reports"] += 1
        return (1, data, None)

    def duplicates(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        table = self._p(params, "table")
        column = self._p(params, "column")
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        if not table or not column:
            return (0, None, ("ERR_PARAMS", "table and column required", 0))
        sql = f"SELECT [{column}], COUNT(*) as dup_count FROM [{table}] GROUP BY [{column}] HAVING dup_count > 1 ORDER BY dup_count DESC"
        ok, data, err = self.run_query({"db_path": db_path, "sql": sql})
        if not ok:
            return (ok, None, err)
        total_dupes = sum(r["dup_count"] for r in data["rows"])
        self.state["stats"]["reports"] += 1
        return (1, {"columns": data["columns"], "rows": data["rows"], "duplicate_groups": len(data["rows"]), "total_duplicate_rows": total_dupes}, None)

    def full_report(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        fmt = self._p(params, "format", "markdown")
        if not db_path or not os.path.isfile(db_path):
            return (0, None, ("ERR_DB", f"DB not found: {db_path}", 0))
        ok, summary_data, err = self.summary({"db_path": db_path})
        if not ok:
            return (ok, None, err)
        sections = []
        sections.append(f"# Database Report: {os.path.basename(db_path)}")
        sections.append(f"Generated: {datetime.datetime.now().isoformat()}")
        sections.append(f"Path: {db_path}")
        sections.append(f"File size: {self._human_size(os.path.getsize(db_path))}")
        sections.append("")
        sections.append(f"Tables: {summary_data['table_count']}")
        sections.append("")
        sections.append("## Table Overview")
        sections.append("")
        tbl_rows = [{"table": t["table"], "rows": t["rows"], "columns": len(t["columns"])} for t in summary_data["tables"]]
        ok, tbl_md, err = self.format_table({"rows": tbl_rows, "format": fmt, "columns": ["table", "rows", "columns"]})
        if ok:
            sections.append(tbl_md)
        sections.append("")
        for t in summary_data["tables"]:
            if t["rows"] == 0:
                continue
            sections.append(f"## {t['table']} ({t['rows']} rows)")
            sections.append("")
            cols = t["columns"]
            sections.append(f"Columns: {', '.join(cols)}")
            sections.append("")
            for col in cols:
                ok, dupe_data, dupe_err = self.duplicates({"db_path": db_path, "table": t["table"], "column": col})
                if ok and dupe_data["duplicate_groups"] > 0:
                    sections.append(f"### Duplicates in `{col}`")
                    sections.append(f"Groups: {dupe_data['duplicate_groups']}, Total duplicate rows: {dupe_data['total_duplicate_rows']}")
                    ok, dupe_md, _ = self.format_table({"rows": dupe_data["rows"][:20], "format": fmt})
                    if ok:
                        sections.append(dupe_md)
                    sections.append("")
            top_col = cols[0] if cols else None
            for col in cols:
                lower = col.lower()
                if "size" in lower or "bytes" in lower or "count" in lower:
                    top_col = col
                    break
            if top_col:
                ok, top_data, _ = self.top_n({"db_path": db_path, "table": t["table"], "column": top_col, "n": 10})
                if ok and top_data["count"] > 0:
                    sections.append(f"### Top 10 by `{top_col}`")
                    ok, top_md, _ = self.format_table({"rows": top_data["rows"], "format": fmt})
                    if ok:
                        sections.append(top_md)
                    sections.append("")
        report = "\n".join(sections)
        self.state["last_report"] = report
        self.state["stats"]["reports"] += 1
        return (1, report, None)

    # ================================================================
    # EXPORT
    # ================================================================

    def export(self, params):
        db_path = self._p(params, "db_path", self.state["config"]["default_db"])
        sql = self._p(params, "sql")
        fmt = self._p(params, "format", self.state["config"]["default_format"])
        dest_path = self._p(params, "dest_path")
        if not db_path or not sql:
            return (0, None, ("ERR_PARAMS", "db_path and sql required", 0))
        if not dest_path:
            return (0, None, ("ERR_PARAMS", "dest_path required", 0))
        ok, data, err = self.run_query({"db_path": db_path, "sql": sql})
        if not ok:
            return (ok, None, err)
        ok, text, err = self.format_table({"rows": data["rows"], "format": fmt, "columns": data["columns"]})
        if not ok:
            return (ok, None, err)
        try:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(text)
            self.state["stats"]["exports"] += 1
            return (1, {"dest_path": dest_path, "rows": data["count"], "format": fmt, "size": len(text)}, None)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))

    # ================================================================
    # FORMATTERS
    # ================================================================

    def _format_markdown(self, columns, rows):
        lines = []
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("|" + "|".join(["---"] * len(columns)) + "|")
        for row in rows:
            vals = []
            for col in columns:
                val = row.get(col, "")
                val_str = str(val) if val is not None else ""
                if len(val_str) > 60:
                    val_str = val_str[:57] + "..."
                vals.append(val_str)
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    def _format_csv(self, columns, rows):
        import io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buf.getvalue().strip()

    def _format_json(self, columns, rows):
        return json.dumps(rows, indent=2, default=str, ensure_ascii=False)

    def _format_text(self, columns, rows):
        col_widths = {}
        for col in columns:
            col_widths[col] = len(col)
        for row in rows:
            for col in columns:
                val_len = len(str(row.get(col, ""))) if row.get(col) is not None else 0
                if val_len > col_widths[col]:
                    col_widths[col] = min(val_len, 60)
        lines = []
        header = "  ".join(col.ljust(col_widths[col]) for col in columns)
        lines.append(header)
        lines.append("  ".join("-" * col_widths[col] for col in columns))
        for row in rows:
            vals = []
            for col in columns:
                val = row.get(col, "")
                val_str = str(val) if val is not None else ""
                if len(val_str) > 60:
                    val_str = val_str[:57] + "..."
                vals.append(val_str.ljust(col_widths[col]))
            lines.append("  ".join(vals))
        return "\n".join(lines)

    # ================================================================
    # HELPERS
    # ================================================================

    def _human_size(self, n):
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"
