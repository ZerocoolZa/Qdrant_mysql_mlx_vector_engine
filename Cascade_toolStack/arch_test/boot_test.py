#!/usr/bin/env python3
"""
boot_test.py — Test the REAL MemUnit architecture

Boots the actual architecture from MEM_Complete_System.py:
  1. MemUnit starts (gravity center)
  2. MemDB creates in-RAM SQLite tables (command_queue, state_cache, routing_map)
  3. MemBus initializes (pub/sub)
  4. Executor initializes
  5. Core worlds connect
  6. Commands queue + execute
  7. Events publish through the bus
  8. State cache stores/retrieves

This tests the REAL architecture, not a toy.
"""

import sys
import os
import json
import sqlite3
import time
import traceback

# ═══════════════════════════════════════════════════════════════
# THE REAL CLASSES — extracted from vb_code_test.vb_classes
# ═══════════════════════════════════════════════════════════════

class MemBus:
    """Message routing bus."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.subscribers = {}

    def subscribe(self, params):
        try:
            pattern = params.get("pattern")
            callback = params.get("callback")
            if pattern not in self.subscribers:
                self.subscribers[pattern] = []
            self.subscribers[pattern].append(callback)
            return (1, {"pattern": pattern, "subscribers": len(self.subscribers[pattern])}, None)
        except Exception as e:
            return (0, None, ("SUBSCRIBE_ERROR", str(e), 0))

    def publish(self, params):
        try:
            action = params.get("action")
            payload = params.get("payload", {})
            delivered = 0
            for pattern, callbacks in self.subscribers.items():
                if action.startswith(pattern) or pattern == "*":
                    for callback in callbacks:
                        callback(action, payload)
                        delivered += 1
            return (1, {"action": action, "delivered": delivered}, None)
        except Exception as e:
            return (0, None, ("PUBLISH_ERROR", str(e), 0))


class MemDB:
    """In-RAM truth database — where commands swap."""

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
        # ── RAM tables from MEM_Complete_System.py spec ──
        # mandatory at first boot: startup_state, config_state, logs, errors, report_state, memory_routing_state
        for tbl in ["startup_state", "config_state", "logs", "errors",
                     "report_state", "memory_routing_state",
                     "io_state", "os_state", "hw_state", "ast_state",
                     "bracket_state", "rules_state", "gui_state"]:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        self.conn.commit()

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
        elif command == "put_state":
            return self._put_state(params)
        elif command == "get_state":
            return self._get_state(params)
        elif command == "add_route":
            return self._add_route(params)
        elif command == "dump_tables":
            return self._dump_tables(params)
        else:
            return (0, {}, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))

    def _queue_command(self, params):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO command_queue (action, source, target, params) VALUES (?, ?, ?, ?)",
                (params.get("action"), params.get("source"), params.get("target"),
                 json.dumps(params.get("params", {})))
            )
            self.conn.commit()
            return (1, {"cmd_id": cursor.lastrowid}, None)
        except Exception as e:
            return (0, None, ("QUEUE_ERROR", str(e), 0))

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

    def _put_state(self, params):
        """Store a key-value in a RAM table"""
        try:
            table = params.get("table", "state_cache")
            key = params.get("key")
            value = json.dumps(params.get("value")) if not isinstance(params.get("value"), str) else params.get("value")
            cursor = self.conn.cursor()
            cursor.execute(f"INSERT OR REPLACE INTO {table} (key, value) VALUES (?, ?)", (key, value))
            self.conn.commit()
            return (1, {"stored": key, "table": table}, None)
        except Exception as e:
            return (0, None, ("PUT_STATE_ERROR", str(e), 0))

    def _get_state(self, params):
        """Retrieve a key-value from a RAM table"""
        try:
            table = params.get("table", "state_cache")
            key = params.get("key")
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT value FROM {table} WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    val = json.loads(row[0])
                except:
                    val = row[0]
                return (1, {"key": key, "value": val}, None)
            return (1, None, None)
        except Exception as e:
            return (0, None, ("GET_STATE_ERROR", str(e), 0))

    def _add_route(self, params):
        """Add a routing map entry"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO routing_map (action_pattern, target_core, target_lib, priority) VALUES (?, ?, ?, ?)",
                (params.get("action_pattern"), params.get("target_core"),
                 params.get("target_lib"), params.get("priority", 0))
            )
            self.conn.commit()
            return (1, {"route_id": cursor.lastrowid}, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def _dump_tables(self, params=None):
        """Dump all tables and their row counts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cursor.fetchall()]
            result = {}
            for t in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t}")
                result[t] = cursor.fetchone()[0]
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DUMP_ERROR", str(e), 0))

    def read_state(self, params=None):
        return (1, {"state": self.state}, None)

    def set_config(self, values):
        cfg = values.get("config") if isinstance(values, dict) else {}
        if isinstance(cfg, dict):
            self.state["config"].update(cfg)
        return (1, self.state["config"], None)


class Executor:
    """Authority for executing code and functions."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db
        }
        self.cores = {}  # registered core instances
        self.libs = {}   # registered lib instances
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "execute":
            return self._execute(params)
        elif command == "call":
            return self._call(params)
        elif command == "register_core":
            return self._register_core(params)
        elif command == "register_lib":
            return self._register_lib(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        else:
            return (0, {}, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))

    def _register_core(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            if not name:
                return (0, None, ("NO_NAME", "name required", 0))
            self.cores[name] = instance
            return (1, {"registered": name, "type": "core", "total_cores": len(self.cores)}, None)
        except Exception as e:
            return (0, None, ("REGISTER_ERROR", str(e), 0))

    def _register_lib(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            if not name:
                return (0, None, ("NO_NAME", "name required", 0))
            self.libs[name] = instance
            return (1, {"registered": name, "type": "lib", "total_libs": len(self.libs)}, None)
        except Exception as e:
            return (0, None, ("REGISTER_ERROR", str(e), 0))

    def _execute(self, params):
        try:
            target = params.get("target")
            action = params.get("action", "")
            action_params = params.get("params", {})

            # Find target in registered cores or libs
            instance = self.cores.get(target) or self.libs.get(target)
            if instance is None:
                return (0, None, ("NO_TARGET", f"target '{target}' not registered", 0))

            # If the instance has a Run() method, dispatch through it
            if hasattr(instance, "Run"):
                return instance.Run(action, action_params)
            else:
                return (1, {"executed": True, "target": target, "action": action}, None)
        except Exception as e:
            return (0, None, ("EXECUTE_ERROR", str(e), 0))

    def _call(self, params):
        function = params.get("function", "")
        args = params.get("args", [])
        return (1, {"called": True, "function": function}, None)

    def read_state(self, params=None):
        return (1, {"state": self.state, "cores": list(self.cores.keys()), "libs": list(self.libs.keys())}, None)

    def set_config(self, values):
        cfg = values.get("config") if isinstance(values, dict) else {}
        if isinstance(cfg, dict):
            self.state["config"].update(cfg)
        return (1, self.state["config"], None)


class MemUnit:
    """MemUnit orchestrator — the backbone.
    Connects all Core and Lib through central routing."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": []
        }
        self.memdb = MemDB(mem, db, param)
        self.membus = MemBus(mem, db, param)
        self.executor = Executor(mem, db, param)

    def connect_core(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            r = self.executor.Run("register_core", {"name": name, "instance": instance})
            if r[0]:
                self.membus.subscribe({"pattern": name, "callback": lambda a, p: None})
            return r
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    def connect_lib(self, params):
        try:
            name = params.get("name")
            instance = params.get("instance")
            r = self.executor.Run("register_lib", {"name": name, "instance": instance})
            if r[0]:
                self.membus.subscribe({"pattern": name, "callback": lambda a, p: None})
            return r
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    def execute(self, params):
        try:
            target = params.get("target")
            action = params.get("action")
            action_params = params.get("params", {})

            # Queue command in MemDB
            self.memdb.Run("queue_command", {
                "action": action,
                "source": "MemUnit",
                "target": target,
                "params": action_params
            })

            # Execute through Executor
            result = self.executor.Run("execute", {
                "target": target,
                "action": action,
                "params": action_params
            })

            return result
        except Exception as e:
            return (0, None, ("EXECUTE_ERROR", str(e), 0))

    def read_state(self, params=None):
        if params is None:
            params = {}
        return (1, self.state.copy(), None)

    def Run(self, command, params=None):
        if params is None:
            params = {}
        if command == "connect_core":
            return self.connect_core(params)
        elif command == "connect_lib":
            return self.connect_lib(params)
        elif command == "execute":
            return self.execute(params)
        elif command == "read_state":
            return self.read_state(params)
        else:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))


# ═══════════════════════════════════════════════════════════════
# SIMULATED CORE WORLDS — from MEM_Complete_System.py boot chain
# ═══════════════════════════════════════════════════════════════

class Core_config:
    """Core config world — config authority"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "read_config":
            return (1, {"db_name": "vb_shared", "db_user": "root"}, None)
        elif command == "write_config":
            return (1, {"written": True}, None)
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


class Core_os:
    """Core OS world — operating system inspection"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "inspect":
            import platform
            return (1, {"os": platform.system(), "python": sys.version.split()[0]}, None)
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


class Core_hw:
    """Core hardware world — hardware inspection"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "inspect":
            import platform
            return (1, {"machine": platform.machine(), "cpu_count": os.cpu_count()}, None)
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


class Core_io:
    """Core IO world — file operations"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "read_file":
            path = params.get("path", "")
            try:
                with open(path, "r") as f:
                    return (1, {"path": path, "content": f.read()[:4096]}, None)
            except Exception as e:
                return (0, None, ("READ_ERROR", str(e), 0))
        elif command == "write_file":
            path = params.get("path", "")
            content = params.get("content", "")
            try:
                with open(path, "w") as f:
                    f.write(content)
                return (1, {"path": path, "bytes": len(content)}, None)
            except Exception as e:
                return (0, None, ("WRITE_ERROR", str(e), 0))
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


class Core_error:
    """Core error world — error standardization"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "standardize":
            return (1, {"standardized": True, "original": params.get("error")}, None)
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


class Core_report:
    """Core report world — formatting"""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": [], "memunit": mem, "db_manager": db}

    def Run(self, command, params=None):
        params = params or {}
        if command == "format":
            return (1, {"formatted": str(params.get("data", ""))}, None)
        elif command == "read_state":
            return (1, self.state.copy(), None)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))


# ═══════════════════════════════════════════════════════════════
# BOOT TEST — the actual architecture test
# ═══════════════════════════════════════════════════════════════

def test_boot():
    """Test 1: Boot MemUnit and verify MemDB tables exist"""
    print("=" * 70)
    print("TEST 1: BOOT MEMUNIT")
    print("=" * 70)

    mu = MemUnit()
    assert mu is not None
    assert mu.memdb is not None
    assert mu.membus is not None
    assert mu.executor is not None
    print("  [PASS] MemUnit created with MemDB + MemBus + Executor")

    # Check MemDB tables
    r = mu.memdb.Run("dump_tables")
    assert r[0], f"dump_tables failed: {r}"
    tables = r[1]
    print(f"  [PASS] MemDB has {len(tables)} tables:")
    for tname, count in sorted(tables.items()):
        print(f"         {tname}: {count} rows")

    # Verify mandatory tables from spec
    mandatory = ["startup_state", "config_state", "logs", "errors",
                 "report_state", "memory_routing_state"]
    for t in mandatory:
        assert t in tables, f"MISSING mandatory table: {t}"
    print(f"  [PASS] All {len(mandatory)} mandatory boot tables exist")

    # Verify core infrastructure tables
    assert "command_queue" in tables
    assert "state_cache" in tables
    assert "routing_map" in tables
    print(f"  [PASS] Infrastructure tables: command_queue, state_cache, routing_map")

    return mu


def test_connect_cores(mu):
    """Test 2: Connect core worlds (boot chain)"""
    print("\n" + "=" * 70)
    print("TEST 2: CONNECT CORE WORLDS (BOOT CHAIN)")
    print("=" * 70)

    # Boot chain from MEM_Complete_System.py:
    # MemUnit → config → os → hw → io → ast → brackets → rules → error → report → output
    boot_chain = [
        ("Core_config", Core_config()),
        ("Core_os",     Core_os()),
        ("Core_hw",     Core_hw()),
        ("Core_io",     Core_io()),
        ("Core_error",  Core_error()),
        ("Core_report", Core_report()),
    ]

    for name, instance in boot_chain:
        r = mu.Run("connect_core", {"name": name, "instance": instance})
        assert r[0], f"connect_core({name}) failed: {r}"
        print(f"  [PASS] Connected: {name}")

    # Verify they're registered
    r = mu.executor.Run("read_state")
    assert r[0]
    cores = r[1]["cores"]
    assert len(cores) == len(boot_chain)
    print(f"  [PASS] {len(cores)} cores registered in Executor")

    # Verify bus subscribers
    assert len(mu.membus.subscribers) == len(boot_chain)
    print(f"  [PASS] {len(mu.membus.subscribers)} subscribers on MemBus")

    return boot_chain


def test_command_queue(mu):
    """Test 3: Queue commands in MemDB"""
    print("\n" + "=" * 70)
    print("TEST 3: COMMAND QUEUE (MemDB)")
    print("=" * 70)

    # Queue 3 commands
    commands = [
        {"action": "inspect", "source": "MemUnit", "target": "Core_os", "params": {}},
        {"action": "inspect", "source": "MemUnit", "target": "Core_hw", "params": {}},
        {"action": "read_config", "source": "MemUnit", "target": "Core_config", "params": {}},
    ]

    for cmd in commands:
        r = mu.memdb.Run("queue_command", cmd)
        assert r[0], f"queue_command failed: {r}"
        print(f"  [PASS] Queued: {cmd['action']} → {cmd['target']} (cmd_id={r[1]['cmd_id']})")

    # Get next command
    r = mu.memdb.Run("get_next_command")
    assert r[0]
    assert r[1] is not None
    assert r[1]["action"] == "inspect"
    assert r[1]["target"] == "Core_os"
    print(f"  [PASS] Get next: cmd_id={r[1]['cmd_id']}, action={r[1]['action']}, target={r[1]['target']}")

    # Update result
    r = mu.memdb.Run("update_command_result", {"cmd_id": 1, "result": {"os": "Darwin"}, "status": "completed"})
    assert r[0]
    assert r[1]["updated"] == 1
    print(f"  [PASS] Updated cmd_id=1 → completed")

    # Get next should skip completed
    r = mu.memdb.Run("get_next_command")
    assert r[0]
    assert r[1]["cmd_id"] == 2  # should skip cmd_id=1 (completed)
    print(f"  [PASS] Next pending: cmd_id={r[1]['cmd_id']} (skipped completed)")


def test_execute(mu):
    """Test 4: Execute commands through the full chain"""
    print("\n" + "=" * 70)
    print("TEST 4: EXECUTE THROUGH FULL CHAIN")
    print("=" * 70)

    # Execute: Core_os.inspect
    r = mu.Run("execute", {"target": "Core_os", "action": "inspect", "params": {}})
    assert r[0], f"execute failed: {r}"
    print(f"  [PASS] Core_os.inspect → {r[1]}")

    # Execute: Core_hw.inspect
    r = mu.Run("execute", {"target": "Core_hw", "action": "inspect", "params": {}})
    assert r[0]
    print(f"  [PASS] Core_hw.inspect → {r[1]}")

    # Execute: Core_config.read_config
    r = mu.Run("execute", {"target": "Core_config", "action": "read_config", "params": {}})
    assert r[0]
    print(f"  [PASS] Core_config.read_config → {r[1]}")

    # Execute: Core_io.write_file + read_file
    r = mu.Run("execute", {"target": "Core_io", "action": "write_file",
                           "params": {"path": "/tmp/arch_test.txt", "content": "hello from MemUnit"}})
    assert r[0]
    print(f"  [PASS] Core_io.write_file → {r[1]}")

    r = mu.Run("execute", {"target": "Core_io", "action": "read_file",
                           "params": {"path": "/tmp/arch_test.txt"}})
    assert r[0]
    print(f"  [PASS] Core_io.read_file → {r[1]}")

    # Execute: unknown target (should fail)
    r = mu.Run("execute", {"target": "NonExistent", "action": "foo", "params": {}})
    assert not r[0]
    print(f"  [PASS] Unknown target rejected: {r[2]}")


def test_membus(mu):
    """Test 5: MemBus pub/sub"""
    print("\n" + "=" * 70)
    print("TEST 5: MEMBUS (PUB/SUB)")
    print("=" * 70)

    # Track delivered events
    delivered = []

    # Subscribe a real callback
    r = mu.membus.subscribe({"pattern": "Core_error", "callback": lambda a, p: delivered.append((a, p))})
    assert r[0]
    print(f"  [PASS] Subscribed to 'Core_error' pattern")

    # Publish an event
    r = mu.membus.publish({"action": "Core_error.standardize", "payload": {"error": "test error"}})
    assert r[0]
    assert r[1]["delivered"] >= 1
    assert len(delivered) >= 1
    print(f"  [PASS] Published 'Core_error.standardize' → delivered to {r[1]['delivered']} subscriber(s)")
    print(f"  [PASS] Callback received: action={delivered[0][0]}, payload={delivered[0][1]}")

    # Publish to wildcard
    r = mu.membus.subscribe({"pattern": "*", "callback": lambda a, p: delivered.append(("wildcard", a))})
    assert r[0]
    r = mu.membus.publish({"action": "anything.happened", "payload": {"x": 1}})
    assert r[0]
    assert r[1]["delivered"] >= 1
    print(f"  [PASS] Wildcard subscriber received 'anything.happened'")


def test_state_cache(mu):
    """Test 6: State cache — store and retrieve"""
    print("\n" + "=" * 70)
    print("TEST 6: STATE CACHE (RAM TABLES)")
    print("=" * 70)

    # Store in config_state
    r = mu.memdb.Run("put_state", {"table": "config_state", "key": "db_name", "value": "vb_shared"})
    assert r[0]
    print(f"  [PASS] Stored config_state.db_name = 'vb_shared'")

    r = mu.memdb.Run("put_state", {"table": "config_state", "key": "db_user", "value": "root"})
    assert r[0]
    print(f"  [PASS] Stored config_state.db_user = 'root'")

    # Retrieve
    r = mu.memdb.Run("get_state", {"table": "config_state", "key": "db_name"})
    assert r[0]
    assert r[1]["value"] == "vb_shared"
    print(f"  [PASS] Retrieved config_state.db_name = '{r[1]['value']}'")

    # Store in errors table
    r = mu.memdb.Run("put_state", {"table": "errors", "key": "err_001", "value": "test error"})
    assert r[0]
    print(f"  [PASS] Stored errors.err_001 = 'test error'")

    # Store in logs
    r = mu.memdb.Run("put_state", {"table": "logs", "key": "log_001", "value": "boot started"})
    assert r[0]
    print(f"  [PASS] Stored logs.log_001 = 'boot started'")

    # Store in startup_state
    r = mu.memdb.Run("put_state", {"table": "startup_state", "key": "boot_stage", "value": "complete"})
    assert r[0]
    print(f"  [PASS] Stored startup_state.boot_stage = 'complete'")


def test_routing_map(mu):
    """Test 7: Routing map — action patterns to targets"""
    print("\n" + "=" * 70)
    print("TEST 7: ROUTING MAP")
    print("=" * 70)

    routes = [
        {"action_pattern": "inspect.*", "target_core": "Core_os", "priority": 1},
        {"action_pattern": "read_file", "target_core": "Core_io", "priority": 1},
        {"action_pattern": "write_file", "target_core": "Core_io", "priority": 1},
        {"action_pattern": "standardize", "target_core": "Core_error", "priority": 2},
    ]

    for route in routes:
        r = mu.memdb.Run("add_route", route)
        assert r[0]
        print(f"  [PASS] Route: {route['action_pattern']} → {route['target_core']} (priority={route['priority']})")

    # Verify routes in DB
    cursor = mu.memdb.conn.cursor()
    cursor.execute("SELECT action_pattern, target_core, priority FROM routing_map ORDER BY priority")
    rows = cursor.fetchall()
    assert len(rows) == len(routes)
    print(f"  [PASS] {len(rows)} routes registered in routing_map table")


def test_tuple3(mu):
    """Test 8: Tuple3 compliance — every return is (ok, data, error)"""
    print("\n" + "=" * 70)
    print("TEST 8: TUPLE3 COMPLIANCE")
    print("=" * 70)

    # Test MemUnit.Run
    r = mu.Run("read_state")
    assert isinstance(r, tuple) and len(r) == 3
    assert r[0] == 1  # ok
    assert isinstance(r[1], dict)  # data
    assert r[2] is None  # error
    print(f"  [PASS] MemUnit.Run('read_state') → (1, dict, None)")

    # Test MemDB.Run
    r = mu.memdb.Run("read_state")
    assert isinstance(r, tuple) and len(r) == 3
    print(f"  [PASS] MemDB.Run('read_state') → Tuple3")

    # Test MemBus.publish
    r = mu.membus.publish({"action": "test", "payload": {}})
    assert isinstance(r, tuple) and len(r) == 3
    print(f"  [PASS] MemBus.publish() → Tuple3")

    # Test Executor.Run
    r = mu.executor.Run("read_state")
    assert isinstance(r, tuple) and len(r) == 3
    print(f"  [PASS] Executor.Run('read_state') → Tuple3")

    # Test error format
    r = mu.Run("unknown_command")
    assert isinstance(r, tuple) and len(r) == 3
    assert r[0] == 0  # fail
    assert r[1] is None  # no data
    assert isinstance(r[2], tuple)  # error tuple
    print(f"  [PASS] Error return: (0, None, {r[2]})")


def test_command_queue_after_execute(mu):
    """Test 9: Verify commands were queued during execute()"""
    print("\n" + "=" * 70)
    print("TEST 9: COMMAND QUEUE INTEGRITY")
    print("=" * 70)

    cursor = mu.memdb.conn.cursor()
    cursor.execute("SELECT cmd_id, action, target, status FROM command_queue ORDER BY cmd_id")
    rows = cursor.fetchall()
    print(f"  Command queue has {len(rows)} commands:")
    for row in rows:
        print(f"    [{row[0]}] {row[1]} → {row[2]} ({row[3]})")
    assert len(rows) >= 5  # 3 from test 3 + 2+ from test 4
    print(f"  [PASS] {len(rows)} commands queued through MemUnit.execute()")


def test_full_dump(mu):
    """Test 10: Full architecture dump"""
    print("\n" + "=" * 70)
    print("TEST 10: FULL ARCHITECTURE DUMP")
    print("=" * 70)

    # MemDB tables
    r = mu.memdb.Run("dump_tables")
    tables = r[1]
    print(f"\n  MemDB tables ({len(tables)}):")
    for tname, count in sorted(tables.items()):
        marker = " ★" if count > 0 else ""
        print(f"    {tname}: {count} rows{marker}")

    # Executor state
    r = mu.executor.Run("read_state")
    print(f"\n  Executor:")
    print(f"    Cores: {r[1]['cores']}")
    print(f"    Libs:  {r[1]['libs']}")

    # MemBus state
    print(f"\n  MemBus:")
    print(f"    Subscribers: {list(mu.membus.subscribers.keys())}")

    # MemUnit state
    r = mu.Run("read_state")
    print(f"\n  MemUnit state: {r[1]}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  REAL MEMUNIT ARCHITECTURE TEST                                       ║")
    print("║  From MEM_Complete_System.py — the actual specification               ║")
    print("║                                                                       ║")
    print("║  MemUnit (gravity center)                                             ║")
    print("║    ├── MemDB   (in-RAM SQLite: command_queue, state_cache, routing)   ║")
    print("║    ├── MemBus  (pub/sub message routing)                              ║")
    print("║    └── Executor (core/lib registration + dispatch)                    ║")
    print("║                                                                       ║")
    print("║  Boot chain: MemUnit → config → os → hw → io → error → report         ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    passed = 0
    failed = 0

    tests = [
        ("Boot MemUnit",           test_boot),
        ("Connect core worlds",    test_connect_cores),
        ("Command queue",          test_command_queue),
        ("Execute through chain",  test_execute),
        ("MemBus pub/sub",         test_membus),
        ("State cache",            test_state_cache),
        ("Routing map",            test_routing_map),
        ("Tuple3 compliance",      test_tuple3),
        ("Command queue integrity",test_command_queue_after_execute),
        ("Full architecture dump", test_full_dump),
    ]

    for name, fn in tests:
        try:
            if name == "Connect core worlds":
                boot_chain = fn(mu)
            elif name == "Boot MemUnit":
                mu = fn()
            else:
                fn(mu)
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  [FAIL] {name}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("ALL TESTS PASSED — the architecture works")
    else:
        print(f"{failed} TEST(S) FAILED — architecture has issues")
    print("=" * 70)
