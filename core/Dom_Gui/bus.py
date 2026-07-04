# [@GHOST]{[@file<bus.py>][@domain<Dom_Gui>][@role<bus>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<gui_bus>][@return<tuple3>][@orch<router>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{In-RAM SQLite GUI bus — events, signals, slots. Ephemeral, recreated each session.}

import sqlite3
import json
from datetime import datetime
from . import config


class GuiBus:
    """In-RAM SQLite event bus for GUI signal/slot routing.

    This is the ephemeral layer — events fire, handlers respond, log is kept in RAM.
    Pairs with GuiDB (on-disk persistent) and ThemeLoader (MySQL themes).

    Three stores:
    - events: log of every signal fired (source, signal, handler, payload, status)
    - slots: registered signal→handler connections (like router.py but queryable)
    - queue: pending events waiting to be dispatched
    """

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.executescript(config.RAM_DB_SCHEMA)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                source_widget TEXT,
                signal_name TEXT,
                handler_name TEXT,
                payload TEXT
            )
        """)
        self.conn.commit()
        self._handlers = {}

    def Run(self, command, params=None):
        if command == "register_slot":
            return self.register_slot(
                params.get("widget"), params.get("signal"),
                params.get("handler")
            )
        elif command == "fire_event":
            return self.fire_event(
                params.get("widget"), params.get("signal"),
                params.get("handler"), params.get("payload")
            )
        elif command == "query_events":
            return self.query_events(params or {})
        elif command == "query_slots":
            return self.query_slots(params.get("widget"))
        elif command == "query_pending":
            return self.query_pending()
        elif command == "dispatch_pending":
            return self.dispatch_pending()
        elif command == "register_handler":
            return self.register_handler(
                params.get("name"), params.get("callback")
            )
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def register_slot(self, widget_name, signal_name, handler_name):
        self.cursor.execute(
            "INSERT OR IGNORE INTO slots (widget_name, signal_name, handler_name) VALUES (?, ?, ?)",
            (widget_name, signal_name, handler_name)
        )
        self.conn.commit()
        return (1, {"widget": widget_name, "signal": signal_name, "handler": handler_name}, None)

    def register_handler(self, name, callback):
        self._handlers[name] = callback
        return (1, {"handler": name}, None)

    def fire_event(self, widget_name, signal_name, handler_name, payload=None):
        payload_str = json.dumps(payload) if payload and not isinstance(payload, str) else payload
        self.cursor.execute(
            "INSERT INTO events (source_widget, signal_name, handler_name, payload) VALUES (?, ?, ?, ?)",
            (widget_name, signal_name, handler_name, payload_str)
        )
        self.cursor.execute(
            "INSERT INTO queue (source_widget, signal_name, handler_name, payload) VALUES (?, ?, ?, ?)",
            (widget_name, signal_name, handler_name, payload_str)
        )
        self.conn.commit()
        return (1, {"queued": True}, None)

    def query_events(self, filters=None):
        filters = filters or {}
        sql = "SELECT * FROM events WHERE 1=1"
        args = []
        if "source_widget" in filters:
            sql += " AND source_widget = ?"
            args.append(filters["source_widget"])
        if "status" in filters:
            sql += " AND status = ?"
            args.append(filters["status"])
        sql += " ORDER BY id DESC LIMIT 100"
        self.cursor.execute(sql, args)
        return (1, [dict(r) for r in self.cursor.fetchall()], None)

    def query_slots(self, widget_name=None):
        if widget_name:
            self.cursor.execute(
                "SELECT * FROM slots WHERE widget_name = ?", (widget_name,)
            )
        else:
            self.cursor.execute("SELECT * FROM slots")
        return (1, [dict(r) for r in self.cursor.fetchall()], None)

    def query_pending(self):
        self.cursor.execute("SELECT * FROM queue ORDER BY id")
        return (1, [dict(r) for r in self.cursor.fetchall()], None)

    def dispatch_pending(self):
        self.cursor.execute("SELECT * FROM queue ORDER BY id")
        pending = self.cursor.fetchall()
        dispatched = 0
        failed = 0
        for row in pending:
            handler_name = row["handler_name"]
            handler = self._handlers.get(handler_name)
            if handler:
                try:
                    payload = row["payload"]
                    handler(payload if payload else None)
                    self.cursor.execute(
                        "UPDATE events SET status = 'dispatched' WHERE id IN "
                        "(SELECT id FROM events WHERE source_widget = ? AND signal_name = ? "
                        "AND handler_name = ? ORDER BY id DESC LIMIT 1)",
                        (row["source_widget"], row["signal_name"], row["handler_name"])
                    )
                    dispatched += 1
                except Exception as e:
                    self.cursor.execute(
                        "UPDATE events SET status = 'failed' WHERE id IN "
                        "(SELECT id FROM events WHERE source_widget = ? AND signal_name = ? "
                        "AND handler_name = ? ORDER BY id DESC LIMIT 1)",
                        (row["source_widget"], row["signal_name"], row["handler_name"])
                    )
                    failed += 1
            else:
                failed += 1
            self.cursor.execute("DELETE FROM queue WHERE id = ?", (row["id"],))
        self.conn.commit()
        return (1, {"dispatched": dispatched, "failed": failed}, None)

    def read_state(self):
        self.cursor.execute("SELECT COUNT(*) FROM events")
        event_count = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM slots")
        slot_count = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT COUNT(*) FROM queue")
        queue_count = self.cursor.fetchone()[0]
        return (1, {
            "events": event_count,
            "slots": slot_count,
            "pending": queue_count,
            "handlers": len(self._handlers),
            "ram": True,
        }, None)

    def close(self):
        self.conn.close()
