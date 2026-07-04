class MemDb:
    """In-RAM truth database — where commands swap."""

    #[@purpose<in-memory command queue and state cache>]
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        import sqlite3
        self.conn = sqlite3.connect(":memory:")
        self._create_schema()

    def _create_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_queue (
                cmd_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                source TEXT,
                target TEXT,
                params TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routing_map (
                route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_pattern TEXT NOT NULL,
                target_core TEXT,
                target_lib TEXT,
                priority INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch memdb operations>]}
    def Run(self, command, params=None):
        params = params or {}
        if command == "queue_command":
            return self._queue_command(params)
        elif command == "get_next_command":
            return self._get_next_command(params)
        elif command == "update_command_result":
            return self._update_command_result(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        else:
            return (0, {}, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))

    #[@_queue_command]{[@params<<params>][@return<Tuple3>][@purpose<queue command in MemUnit>]}
    def _queue_command(self, params):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO command_queue (action, source, target, params) VALUES (?, ?, ?, ?)",
                (params.get("action"), params.get("source"), params.get("target"), json.dumps(params.get("params", {})))
            )
            self.conn.commit()
            return (1, {"cmd_id": cursor.lastrowid}, None)
        except Exception as e:
            return (0, None, ("QUEUE_ERROR", str(e), 0))

    #[@_get_next_command]{[@params<<params>][@return<Tuple3>][@purpose<get next pending command>]}
    def _get_next_command(self, params=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT cmd_id, action, source, target, params FROM command_queue WHERE status = 'pending' ORDER BY cmd_id LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return (1, {
                    "cmd_id": row[0],
                    "action": row[1],
                    "source": row[2],
                    "target": row[3],
                    "params": json.loads(row[4]) if row[4] else {}
                }, None)
            return (1, None, None)
        except Exception as e:
            return (0, None, ("GET_ERROR", str(e), 0))

    #[@_update_command_result]{[@params<<params>][@return<Tuple3>][@purpose<update command result>]}
    def _update_command_result(self, params):
        try:
            cmd_id = params.get("cmd_id")
            result = params.get("result")
            status = params.get("status", "completed")
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE command_queue SET status = ?, result = ? WHERE cmd_id = ?",
                (status, json.dumps(result) if result else None, cmd_id)
            )
            self.conn.commit()
            return (1, {"updated": cursor.rowcount}, None)
        except Exception as e:
            return (0, None, ("UPDATE_ERROR", str(e), 0))

    #\\[@read_state\\]{[@params<<>][@return<Tuple3>][@purpose<return state snapshot>]}
    def read_state(self):
        return (1, {"state": self.state}, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set config values>]}
    def set_config(self, values):
        cfg = values.get("config") if isinstance(values, dict) else {}
        if isinstance(cfg, dict):
            self.state["config"].update(cfg)
        return (1, self.state["config"], None)
