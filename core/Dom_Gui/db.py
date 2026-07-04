# [@GHOST]{[@file<db.py>][@domain<Dom_Gui>][@role<db>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<gui_db>][@return<tuple3>][@orch<builder>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{GUI DB manager — on-disk SQLite (gui_engine.db) + MySQL (gui_pipeline.themes)}

import os
import sqlite3
import json

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from . import config


class GuiDB:
    """On-disk SQLite DB storing the GUI code graph.

    Wraps the existing gui_engine.db created by GuiIngester.
    Tables: gui_files, gui_classes, gui_widgets, gui_styles,
            gui_signals, gui_layouts, gui_edges, gui_methods, gui_findings

    This is the persistent storage — themes, fonts, layouts, settings.
    The RAM bus (bus.py) is the ephemeral event/signal router.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or config.GUI_ENGINE_DB
        self.conn = None
        self.cursor = None
        self._mysql_ok = False
        self._connect()
        self._check_mysql()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def _mysql_connect(self):
        cfg = dict(config.MYSQL_CONFIG)
        unix_socket = cfg.pop("unix_socket", None)
        if unix_socket and os.path.exists(unix_socket):
            return mysql.connector.connect(unix_socket=unix_socket, **cfg)
        return mysql.connector.connect(**cfg)

    def _check_mysql(self):
        if not HAS_MYSQL:
            return
        try:
            conn = self._mysql_connect()
            cur = conn.cursor()
            for stmt in config.SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM gui_pipeline.themes")
            if cur.fetchone()[0] == 0:
                for theme_name, palette in config.THEMES.items():
                    for key, value in palette.items():
                        cat = "font" if key == "font" else "color"
                        cur.execute(
                            "INSERT INTO gui_pipeline.themes (theme_name, `key`, value, category) VALUES (%s, %s, %s, %s)",
                            (theme_name, key, value, cat)
                        )
            conn.commit()
            cur.close()
            conn.close()
            self._mysql_ok = True
        except Exception:
            self._mysql_ok = False

    def Run(self, command, params=None):
        if command == "query_widgets":
            return self.query_widgets(params or {})
        elif command == "query_widget":
            return self.query_widget((params or {}).get("name"))
        elif command == "query_signals":
            return self.query_signals((params or {}).get("class_name"))
        elif command == "query_styles":
            return self.query_styles((params or {}).get("widget_var"))
        elif command == "query_edges":
            return self.query_edges((params or {}).get("edge_type"))
        elif command == "query_widget_graph":
            return self.query_widget_graph((params or {}).get("class_name"))
        elif command == "load_theme":
            return self.load_theme((params or {}).get("name"))
        elif command == "list_themes":
            return self.list_themes()
        elif command == "stats":
            return self.get_stats()
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def load_theme(self, name):
        if self._mysql_ok and HAS_MYSQL:
            try:
                conn = self._mysql_connect()
                cur = conn.cursor()
                cur.execute(
                    "SELECT `key`, value FROM gui_pipeline.themes WHERE theme_name=%s",
                    (name,)
                )
                rows = cur.fetchall()
                cur.close()
                conn.close()
                if rows:
                    return (1, {k: v for k, v in rows}, None)
            except Exception:
                pass
        palette = dict(config.THEMES.get(name, config.THEMES[config.DEFAULT_THEME]))
        return (1, palette, None)

    def list_themes(self):
        if self._mysql_ok and HAS_MYSQL:
            try:
                conn = self._mysql_connect()
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT theme_name FROM gui_pipeline.themes")
                names = [row[0] for row in cur.fetchall()]
                cur.close()
                conn.close()
                if names:
                    return (1, names, None)
            except Exception:
                pass
        return (1, list(config.THEMES.keys()), None)

    def query_widgets(self, filters=None):
        filters = filters or {}
        sql = "SELECT * FROM gui_widgets WHERE 1=1"
        args = []
        if "class_name" in filters:
            sql += " AND class_name = ?"
            args.append(filters["class_name"])
        if "widget_type" in filters:
            sql += " AND widget_type = ?"
            args.append(filters["widget_type"])
        if "parent_var" in filters:
            sql += " AND parent_var = ?"
            args.append(filters["parent_var"])
        sql += " ORDER BY line_num"
        self.cursor.execute(sql, args)
        rows = self.cursor.fetchall()
        return (1, [dict(r) for r in rows], None)

    def query_widget(self, name):
        self.cursor.execute(
            "SELECT * FROM gui_widgets WHERE widget_var = ?", (name,)
        )
        rows = self.cursor.fetchall()
        if not rows:
            return (0, None, ("not_found", name, 0))
        return (1, [dict(r) for r in rows], None)

    def query_signals(self, class_name=None):
        if class_name:
            self.cursor.execute(
                "SELECT * FROM gui_signals WHERE class_name = ? ORDER BY line_num",
                (class_name,)
            )
        else:
            self.cursor.execute("SELECT * FROM gui_signals ORDER BY line_num")
        rows = self.cursor.fetchall()
        return (1, [dict(r) for r in rows], None)

    def query_styles(self, widget_var=None):
        if widget_var:
            self.cursor.execute(
                "SELECT * FROM gui_styles WHERE widget_var = ? ORDER BY line_num",
                (widget_var,)
            )
        else:
            self.cursor.execute("SELECT * FROM gui_styles ORDER BY line_num")
        rows = self.cursor.fetchall()
        return (1, [dict(r) for r in rows], None)

    def query_edges(self, edge_type=None):
        if edge_type:
            self.cursor.execute(
                "SELECT * FROM gui_edges WHERE edge_type = ?",
                (edge_type,)
            )
        else:
            self.cursor.execute("SELECT * FROM gui_edges")
        rows = self.cursor.fetchall()
        return (1, [dict(r) for r in rows], None)

    def query_widget_graph(self, class_name=None):
        if class_name:
            self.cursor.execute(
                "SELECT * FROM gui_widgets WHERE class_name = ? ORDER BY line_num",
                (class_name,)
            )
        else:
            self.cursor.execute("SELECT * FROM gui_widgets ORDER BY line_num")
        widgets = [dict(r) for r in self.cursor.fetchall()]
        self.cursor.execute("SELECT * FROM gui_edges ORDER BY line_num")
        edges = [dict(r) for r in self.cursor.fetchall()]
        return (1, {"widgets": widgets, "edges": edges}, None)

    def get_stats(self):
        stats = {}
        for table in ("gui_files", "gui_classes", "gui_widgets",
                       "gui_styles", "gui_signals", "gui_layouts",
                       "gui_edges", "gui_methods", "gui_findings"):
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = self.cursor.fetchone()[0]
            except Exception:
                stats[table] = 0
        return (1, stats, None)

    def read_state(self):
        return (1, {
            "db_path": self.db_path,
            "connected": self.conn is not None,
            "mysql_ok": self._mysql_ok,
        }, None)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
