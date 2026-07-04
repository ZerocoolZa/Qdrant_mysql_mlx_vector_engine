#!/usr/bin/env python3
#[@GHOST]{[@file<method_orchestrator.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<method_orchestrator>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}
"""
MethodOrchestrator — method-centric runtime composition.

The DB is the source of truth for behavior. Classes are projections
over shared method nodes. The orchestrator composes classes from
method IDs, resolves call closures, and materializes runtime instances.

Architecture:
  methods table       — 7,553 unique behavior nodes (source_code, ast_hash)
  class_methods table — projection: which methods belong to which class
  orchestrator        — compose, resolve, materialize, execute

Usage:
  orch = MethodOrchestrator()
  orch.BuildFromMethodsDb()          # one-time: dedupe + project
  orch.Compose("DynamicAgent", method_ids=[1,4,9,12])
  agent = orch.Materialize("DynamicAgent")
  result = agent.Run("read_state", {})
"""

import ast
import hashlib
import json
import sqlite3
import time
import types
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from SuperConfig import DB, RUNTIME


class MethodOrchestrator:

    SCHEMA_METHOD_CENTRIC = """
CREATE TABLE IF NOT EXISTS methods (
    method_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    source_code TEXT NOT NULL,
    ast_hash    TEXT NOT NULL,
    arg_names   TEXT,
    returns     TEXT,
    cyclomatic  INTEGER DEFAULT 0,
    max_nesting INTEGER DEFAULT 0,
    body_lines  INTEGER DEFAULT 0,
    call_count  INTEGER DEFAULT 0,
    call_names  TEXT,
    recursive   INTEGER DEFAULT 0,
    has_docstring INTEGER DEFAULT 0,
    is_empty    INTEGER DEFAULT 0,
    origin_class TEXT,
    origin_qualname TEXT,
    version     INTEGER DEFAULT 1,
    created_at  REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_m_name ON methods(name);
CREATE INDEX IF NOT EXISTS idx_m_hash ON methods(ast_hash);
CREATE INDEX IF NOT EXISTS idx_m_origin ON methods(origin_class);

CREATE TABLE IF NOT EXISTS class_methods (
    class_name  TEXT NOT NULL,
    method_id   INTEGER NOT NULL,
    slot_name   TEXT NOT NULL,
    FOREIGN KEY (method_id) REFERENCES methods(method_id)
);
CREATE INDEX IF NOT EXISTS idx_cm_class ON class_methods(class_name);
CREATE INDEX IF NOT EXISTS idx_cm_method ON class_methods(method_id);

CREATE TABLE IF NOT EXISTS class_contracts (
    class_name  TEXT PRIMARY KEY,
    required_state TEXT,
    description TEXT,
    created_at  REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS method_calls (
    caller_id   INTEGER NOT NULL,
    called_name TEXT NOT NULL,
    FOREIGN KEY (caller_id) REFERENCES methods(method_id)
);
CREATE INDEX IF NOT EXISTS idx_mc_caller ON method_calls(caller_id);
CREATE INDEX IF NOT EXISTS idx_mc_name ON method_calls(called_name);
"""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "source_db": DB.METHODS_DB,
            "orchestrator_db": DB.METHOD_ORCHESTRATOR_DB,
            "conn": None,
            "runtime_classes": {},
            "runtime_instances": {},
            "compile_cache": {},
            "stats": {
                "composed": 0,
                "materialized": 0,
                "executed": 0,
                "cache_hits": 0,
                "db_queries": 0,
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
            self.state["conn"] = sqlite3.connect(
                self.state["orchestrator_db"]
            )
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA foreign_keys = ON")
        return self.state["conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["orchestrator_db"])
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(self.SCHEMA_METHOD_CENTRIC)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "build": self.BuildFromMethodsDb,
            "compose": self.Compose,
            "compose_by_seed": self.ComposeBySeed,
            "compose_from_class": self.ComposeFromClass,
            "materialize": self.Materialize,
            "list_classes": self.ListClasses,
            "list_methods": self.ListMethods,
            "call_closure": self.CallClosure,
            "class_info": self.ClassInfo,
            "method_info": self.MethodInfo,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
            "close": self.Close,
            "export_class": self.ExportClass,
            "import_class": self.ImportClass,
            "class_health": self.ClassHealth,
            "method_signature": self.MethodSignature,
            "call_tree": self.CallTree,
            "global_health": self.GlobalHealth,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    # -----------------------------------------------------------------------
    # BUILD — dedupe methods from source DB into method-centric schema
    # -----------------------------------------------------------------------

    def BuildFromMethodsDb(self, params=None):
        src = sqlite3.connect(self.state["source_db"])
        src.row_factory = sqlite3.Row
        conn = self._Conn()

        conn.execute("DELETE FROM methods")
        conn.execute("DELETE FROM class_methods")
        conn.execute("DELETE FROM class_contracts")
        conn.execute("DELETE FROM method_calls")

        rows = src.execute(
            "SELECT name, class_name, qualname, source_code, ast_hash, "
            "arg_names, returns, cyclomatic, max_nesting, body_lines, "
            "call_count, call_names, recursive, has_docstring, is_empty "
            "FROM ci_methods WHERE source_code IS NOT NULL AND source_code != ''"
        ).fetchall()

        hash_to_id = {}
        class_method_pairs = []
        method_calls_rows = []
        total = 0
        unique = 0
        duplicates = 0

        for r in rows:
            total += 1
            h = r["ast_hash"]
            if not h:
                h = hashlib.md5(r["source_code"].encode()).hexdigest()

            if h in hash_to_id:
                mid = hash_to_id[h]
                duplicates += 1
            else:
                cur = conn.execute(
                    "INSERT INTO methods "
                    "(name, source_code, ast_hash, arg_names, returns, "
                    "cyclomatic, max_nesting, body_lines, call_count, "
                    "call_names, recursive, has_docstring, is_empty, "
                    "origin_class, origin_qualname, version, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["name"], r["source_code"], h,
                     r["arg_names"], r["returns"],
                     r["cyclomatic"], r["max_nesting"], r["body_lines"],
                     r["call_count"], r["call_names"],
                     r["recursive"], r["has_docstring"], r["is_empty"],
                     r["class_name"], r["qualname"], 1, time.time())
                )
                mid = cur.lastrowid
                hash_to_id[h] = mid
                unique += 1

                calls = [c.strip() for c in (r["call_names"] or "").split(",") if c.strip()]
                for cname in calls:
                    method_calls_rows.append((mid, cname))

            class_method_pairs.append((r["class_name"], mid, r["name"]))

        conn.executemany(
            "INSERT INTO class_methods (class_name, method_id, slot_name) VALUES (?,?,?)",
            class_method_pairs
        )
        conn.executemany(
            "INSERT INTO method_calls (caller_id, called_name) VALUES (?,?)",
            method_calls_rows
        )

        class_names = set(p[0] for p in class_method_pairs)
        for cn in class_names:
            conn.execute(
                "INSERT OR REPLACE INTO class_contracts "
                "(class_name, required_state, description, created_at) "
                "VALUES (?,?,?,?)",
                (cn, '{"state": "dict"}', "auto-imported from methods.sqlite", time.time())
            )

        conn.commit()
        src.close()

        self.state["stats"]["db_queries"] += 1
        return (1, {
            "total_methods": total,
            "unique_methods": unique,
            "duplicates_eliminated": duplicates,
            "classes": len(class_names),
            "call_edges": len(method_calls_rows),
        }, None)

    # -----------------------------------------------------------------------
    # CALL CLOSURE — find all methods reachable from a seed set
    # -----------------------------------------------------------------------

    def CallClosure(self, params):
        seed_names = self._p(params, "seeds", [])
        if not seed_names:
            return self._err("NO_SEEDS", "seeds list required")

        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1

        all_method_names = set(
            r[0] for r in conn.execute("SELECT name FROM methods").fetchall()
        )

        name_to_ids = defaultdict(list)
        for r in conn.execute("SELECT method_id, name FROM methods").fetchall():
            name_to_ids[r["name"]].append(r["method_id"])

        closure_ids = set()
        closure_names = set(seed_names)
        frontier = set(seed_names)

        while frontier:
            current = frontier.pop()
            if current not in all_method_names:
                continue
            ids = name_to_ids.get(current, [])
            for mid in ids:
                if mid in closure_ids:
                    continue
                closure_ids.add(mid)
                called = conn.execute(
                    "SELECT called_name FROM method_calls WHERE caller_id = ?",
                    (mid,)
                ).fetchall()
                for c in called:
                    cn = c["called_name"]
                    if cn in all_method_names and cn not in closure_names:
                        closure_names.add(cn)
                        frontier.add(cn)

        return (1, {
            "seed_count": len(seed_names),
            "closure_size": len(closure_ids),
            "closure_names": sorted(closure_names),
            "method_ids": sorted(closure_ids),
        }, None)

    # -----------------------------------------------------------------------
    # COMPOSE — define a class as a set of method IDs
    # -----------------------------------------------------------------------

    def Compose(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")

        method_ids = self._p(params, "method_ids", [])
        required_state = self._p(params, "required_state", {"state": "dict"})
        description = self._p(params, "description", "")
        resolve_closure = self._p(params, "resolve_closure", False)

        if not method_ids and not resolve_closure:
            return self._err("NO_METHODS", "method_ids or resolve_closure required")

        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1

        final_ids = list(method_ids)

        if resolve_closure:
            seed_names = []
            for mid in method_ids:
                r = conn.execute(
                    "SELECT name FROM methods WHERE method_id = ?", (mid,)
                ).fetchone()
                if r:
                    seed_names.append(r["name"])

            ok, closure, err = self.CallClosure({"seeds": seed_names})
            if ok:
                final_ids = list(set(final_ids + closure["method_ids"]))

        existing = conn.execute(
            "DELETE FROM class_methods WHERE class_name = ?", (class_name,)
        )

        pairs = []
        for mid in final_ids:
            r = conn.execute(
                "SELECT name FROM methods WHERE method_id = ?", (mid,)
            ).fetchone()
            if r:
                pairs.append((class_name, mid, r["name"]))

        conn.executemany(
            "INSERT INTO class_methods (class_name, method_id, slot_name) VALUES (?,?,?)",
            pairs
        )

        import json as _json
        conn.execute(
            "INSERT OR REPLACE INTO class_contracts "
            "(class_name, required_state, description, created_at) "
            "VALUES (?,?,?,?)",
            (class_name, _json.dumps(required_state), description, time.time())
        )

        conn.commit()
        self.state["stats"]["composed"] += 1
        self.state["runtime_classes"].pop(class_name, None)

        return (1, {
            "class_name": class_name,
            "method_count": len(pairs),
            "methods": [p[2] for p in pairs],
            "resolved_closure": resolve_closure,
        }, None)

    # -----------------------------------------------------------------------
    # COMPOSE BY SEED — compose from method names (auto-resolves closure)
    # -----------------------------------------------------------------------

    def ComposeBySeed(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")

        seeds = self._p(params, "seeds", [])
        if not seeds:
            return self._err("NO_SEEDS", "seeds list required")

        ok, closure, err = self.CallClosure({"seeds": seeds})
        if not ok:
            return (0, None, err)

        return self.Compose({
            "class_name": class_name,
            "method_ids": closure["method_ids"],
            "required_state": self._p(params, "required_state", {"state": "dict"}),
            "description": self._p(params, "description", "composed from seeds: " + ",".join(seeds)),
            "resolve_closure": False,
        })

    # -----------------------------------------------------------------------
    # COMPOSE FROM CLASS — import all methods from an existing class
    # -----------------------------------------------------------------------

    def ComposeFromClass(self, params):
        source_class = self._p(params, "source_class")
        if not source_class:
            return self._err("NO_SOURCE_CLASS", "source_class required")
        target_class = self._p(params, "target_class", source_class)
        description = self._p(params, "description", "imported from " + source_class)

        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1

        rows = conn.execute(
            "SELECT method_id, slot_name FROM class_methods WHERE class_name = ?",
            (source_class,)
        ).fetchall()
        if not rows:
            return self._err("CLASS_NOT_FOUND", source_class)

        method_ids = [r["method_id"] for r in rows]

        return self.Compose({
            "class_name": target_class,
            "method_ids": method_ids,
            "description": description,
        })

    # -----------------------------------------------------------------------
    # MATERIALIZE — create a runtime class instance from composed methods
    # -----------------------------------------------------------------------

    def Materialize(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")

        init_args = self._p(params, "init_args", {})

        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1

        rows = conn.execute(
            "SELECT cm.slot_name, m.method_id, m.source_code, m.arg_names "
            "FROM class_methods cm "
            "JOIN methods m ON cm.method_id = m.method_id "
            "WHERE cm.class_name = ?",
            (class_name,)
        ).fetchall()

        if not rows:
            return self._err("CLASS_NOT_COMPOSED", class_name)

        contract = conn.execute(
            "SELECT required_state FROM class_contracts WHERE class_name = ?",
            (class_name,)
        ).fetchone()

        import json as _json
        required_state = {}
        if contract and contract["required_state"]:
            try:
                required_state = _json.loads(contract["required_state"])
            except Exception:
                required_state = {}

        namespace = {
            "__module__": "orchestrated." + class_name,
            "__qualname__": class_name,
        }

        shared_ns = {}
        self._InjectStdlib(shared_ns)

        compiled_sources = []
        slot_names = []
        for r in rows:
            source = r["source_code"]
            cache_key = str(r["method_id"]) + ":" + r["slot_name"]

            if cache_key not in self.state["compile_cache"]:
                try:
                    tree = ast.parse(source)
                    code_obj = compile(tree, f"<db://{class_name}.{r['slot_name']}>", "exec")
                    self.state["compile_cache"][cache_key] = code_obj
                except SyntaxError as e:
                    continue
                except Exception as e:
                    continue

            compiled_sources.append((cache_key, r["slot_name"]))

        for cache_key, slot_name in compiled_sources:
            code_obj = self.state["compile_cache"][cache_key]
            try:
                exec(code_obj, shared_ns)
            except Exception:
                continue

        for _, slot_name in compiled_sources:
            func = shared_ns.get(slot_name)
            if func is not None:
                namespace[slot_name] = func

        if "__init__" not in namespace:
            def _default_init(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
                if not hasattr(self, "state"):
                    self.state = {}
            namespace["__init__"] = _default_init

        cls = type(class_name, (object,), namespace)

        try:
            instance = cls(**init_args)
        except Exception as e:
            return self._err("INSTANTIATE_ERROR", str(e))

        if not hasattr(instance, "state"):
            instance.state = {}

        self.state["runtime_instances"][class_name] = instance
        self.state["stats"]["materialized"] += 1

        return (1, {
            "class_name": class_name,
            "instance": instance,
            "method_count": len(rows),
            "methods": [r["slot_name"] for r in rows],
        }, None)

    # -----------------------------------------------------------------------
    # LIST / INFO
    # -----------------------------------------------------------------------

    def ListClasses(self, params=None):
        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1
        rows = conn.execute(
            "SELECT cm.class_name, COUNT(*) as method_count, "
            "cc.description "
            "FROM class_methods cm "
            "LEFT JOIN class_contracts cc ON cm.class_name = cc.class_name "
            "GROUP BY cm.class_name ORDER BY method_count DESC"
        ).fetchall()
        classes = []
        for r in rows:
            classes.append({
                "class_name": r["class_name"],
                "method_count": r["method_count"],
                "description": r["description"] or "",
            })
        return (1, {"classes": classes, "count": len(classes)}, None)

    def ListMethods(self, params=None):
        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1
        limit = self._p(params, "limit", 100)
        offset = self._p(params, "offset", 0)
        rows = conn.execute(
            "SELECT method_id, name, origin_class, cyclomatic, "
            "body_lines, call_count, ast_hash "
            "FROM methods ORDER BY method_id LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        methods = []
        for r in rows:
            methods.append({
                "method_id": r["method_id"],
                "name": r["name"],
                "origin_class": r["origin_class"],
                "cyclomatic": r["cyclomatic"],
                "body_lines": r["body_lines"],
                "call_count": r["call_count"],
                "ast_hash": r["ast_hash"][:16] + "...",
            })
        return (1, {"methods": methods, "count": len(methods)}, None)

    def ClassInfo(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")
        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1
        rows = conn.execute(
            "SELECT cm.slot_name, m.method_id, m.name as method_name, "
            "m.cyclomatic, m.body_lines, m.call_count, m.arg_names, "
            "m.origin_class, m.ast_hash "
            "FROM class_methods cm "
            "JOIN methods m ON cm.method_id = m.method_id "
            "WHERE cm.class_name = ? ORDER BY cm.slot_name",
            (class_name,)
        ).fetchall()
        if not rows:
            return self._err("CLASS_NOT_FOUND", class_name)
        methods = []
        for r in rows:
            methods.append({
                "slot": r["slot_name"],
                "method_id": r["method_id"],
                "name": r["method_name"],
                "origin": r["origin_class"],
                "cyclomatic": r["cyclomatic"],
                "body_lines": r["body_lines"],
                "calls": r["call_count"],
                "args": r["arg_names"],
                "hash": r["ast_hash"][:16] + "...",
            })
        return (1, {"class_name": class_name, "methods": methods, "count": len(methods)}, None)

    def MethodInfo(self, params):
        method_id = self._p(params, "method_id")
        if method_id is None:
            return self._err("NO_METHOD_ID", "method_id required")
        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1
        r = conn.execute(
            "SELECT * FROM methods WHERE method_id = ?", (method_id,)
        ).fetchone()
        if not r:
            return self._err("NOT_FOUND", str(method_id))
        calls = conn.execute(
            "SELECT called_name FROM method_calls WHERE caller_id = ?",
            (method_id,)
        ).fetchall()
        callers = conn.execute(
            "SELECT mc.caller_id, m.name as caller_name "
            "FROM method_calls mc JOIN methods m ON mc.caller_id = m.method_id "
            "WHERE mc.called_name = ?",
            (r["name"],)
        ).fetchall()
        return (1, {
            "method_id": r["method_id"],
            "name": r["name"],
            "origin_class": r["origin_class"],
            "cyclomatic": r["cyclomatic"],
            "body_lines": r["body_lines"],
            "call_count": r["call_count"],
            "calls": [c["called_name"] for c in calls],
            "called_by": [{"id": c["caller_id"], "name": c["caller_name"]} for c in callers],
            "arg_names": r["arg_names"],
            "ast_hash": r["ast_hash"],
            "source_preview": (r["source_code"] or "")[:200],
        }, None)

    # -----------------------------------------------------------------------
    # STATS
    # -----------------------------------------------------------------------

    def Stats(self, params=None):
        conn = self._Conn()
        self.state["stats"]["db_queries"] += 1
        counts = {
            "methods": conn.execute("SELECT COUNT(*) FROM methods").fetchone()[0],
            "class_methods": conn.execute("SELECT COUNT(*) FROM class_methods").fetchone()[0],
            "classes": conn.execute("SELECT COUNT(*) FROM class_contracts").fetchone()[0],
            "call_edges": conn.execute("SELECT COUNT(*) FROM method_calls").fetchone()[0],
            "compile_cache": len(self.state["compile_cache"]),
            "runtime_instances": len(self.state["runtime_instances"]),
        }
        return (1, {"counts": counts, "stats": self.state["stats"]}, None)

    # -----------------------------------------------------------------------
    # STATE / CONFIG
    # -----------------------------------------------------------------------

    def read_state(self, params=None):
        safe = dict(self.state)
        safe.pop("conn", None)
        safe.pop("runtime_instances", None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)

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
        return (1, {"closed": True}, None)

    # -----------------------------------------------------------------------
    # EXPORT CLASS — export a class with all methods as JSON
    # -----------------------------------------------------------------------

    def ExportClass(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")
        conn = self._Conn()
        contract = conn.execute(
            "SELECT * FROM class_contracts WHERE class_name = ?", (class_name,)
        ).fetchone()
        rows = conn.execute(
            "SELECT cm.slot_name, m.method_id, m.name, m.source_code, "
            "m.arg_names, m.returns, m.cyclomatic, m.max_nesting, m.body_lines, "
            "m.call_count, m.call_names, m.recursive, m.has_docstring, m.is_empty, "
            "m.origin_class, m.origin_qualname, m.ast_hash "
            "FROM class_methods cm JOIN methods m ON cm.method_id = m.method_id "
            "WHERE cm.class_name = ? ORDER BY cm.slot_name",
            (class_name,)
        ).fetchall()
        if not rows:
            return self._err("CLASS_NOT_FOUND", class_name)
        methods = []
        for r in rows:
            methods.append({
                "slot_name": r["slot_name"],
                "method_id": r["method_id"],
                "name": r["name"],
                "source_code": r["source_code"],
                "arg_names": r["arg_names"],
                "returns": r["returns"],
                "cyclomatic": r["cyclomatic"],
                "body_lines": r["body_lines"],
                "call_count": r["call_count"],
                "call_names": r["call_names"],
                "origin_class": r["origin_class"],
                "ast_hash": r["ast_hash"],
            })
        payload = {
            "class_name": class_name,
            "description": contract["description"] if contract else "",
            "required_state": contract["required_state"] if contract else "",
            "method_count": len(methods),
            "methods": methods,
        }
        return (1, json.dumps(payload, default=str), None)

    # -----------------------------------------------------------------------
    # IMPORT CLASS — import a class and all its methods from JSON
    # -----------------------------------------------------------------------

    def ImportClass(self, params):
        raw = self._p(params, "json")
        if not raw:
            return self._err("NO_JSON", "json string required")
        try:
            payload = json.loads(raw)
        except Exception as e:
            return self._err("BAD_JSON", str(e))
        class_name = payload.get("class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required in json")
        conn = self._Conn()
        conn.execute("DELETE FROM class_methods WHERE class_name = ?", (class_name,))
        imported = 0
        for m in payload.get("methods", []):
            source_code = m.get("source_code")
            name = m.get("name") or m.get("slot_name")
            if not source_code or not name:
                continue
            ast_hash = m.get("ast_hash") or hashlib.sha256(
                source_code.encode()
            ).hexdigest()
            existing = conn.execute(
                "SELECT method_id FROM methods WHERE ast_hash = ?", (ast_hash,)
            ).fetchone()
            if existing:
                mid = existing["method_id"]
            else:
                cur = conn.execute(
                    "INSERT INTO methods "
                    "(name, source_code, ast_hash, arg_names, returns, cyclomatic, "
                    "max_nesting, body_lines, call_count, call_names, recursive, "
                    "has_docstring, is_empty, origin_class, origin_qualname, "
                    "version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (name, source_code, ast_hash, m.get("arg_names"),
                     m.get("returns"), m.get("cyclomatic", 0), m.get("max_nesting", 0),
                     m.get("body_lines", 0), m.get("call_count", 0),
                     m.get("call_names"), m.get("recursive", 0),
                     m.get("has_docstring", 0), m.get("is_empty", 0),
                     m.get("origin_class", class_name), m.get("origin_qualname", ""),
                     1, time.time())
                )
                mid = cur.lastrowid
            conn.execute(
                "INSERT INTO class_methods (class_name, method_id, slot_name) VALUES (?,?,?)",
                (class_name, mid, m.get("slot_name", name))
            )
            imported += 1
        conn.execute(
            "INSERT OR REPLACE INTO class_contracts "
            "(class_name, required_state, description, created_at) VALUES (?,?,?,?)",
            (class_name, payload.get("required_state", '{"state": "dict"}'),
             payload.get("description", ""), time.time())
        )
        conn.commit()
        return (1, {"class_name": class_name, "methods_imported": imported}, None)

    # -----------------------------------------------------------------------
    # CLASS HEALTH — health check for a single class
    # -----------------------------------------------------------------------

    def ClassHealth(self, params):
        class_name = self._p(params, "class_name")
        if not class_name:
            return self._err("NO_CLASS_NAME", "class_name required")
        conn = self._Conn()
        rows = conn.execute(
            "SELECT m.method_id, m.name, m.cyclomatic, m.body_lines, m.call_count "
            "FROM class_methods cm JOIN methods m ON cm.method_id = m.method_id "
            "WHERE cm.class_name = ?",
            (class_name,)
        ).fetchall()
        if not rows:
            return self._err("CLASS_NOT_FOUND", class_name)
        method_names = set(r["name"] for r in rows)
        name_to_id = {r["name"]: r["method_id"] for r in rows}
        total_complexity = sum(r["cyclomatic"] for r in rows)
        total_body = sum(r["body_lines"] for r in rows)
        avg_complexity = round(total_complexity / max(len(rows), 1), 2)
        avg_body = round(total_body / max(len(rows), 1), 2)
        missing = []
        isolated = []
        for r in rows:
            calls = conn.execute(
                "SELECT called_name FROM method_calls WHERE caller_id = ?",
                (r["method_id"],)
            ).fetchall()
            call_list = [c["called_name"] for c in calls]
            if not call_list:
                isolated.append(r["name"])
            for cn in call_list:
                if cn not in method_names:
                    missing.append({"method": r["name"], "missing_call": cn})
        circular = []

        def has_cycle(start_id, start_name):
            visited = set()
            stack = [start_id]
            while stack:
                cur_id = stack.pop()
                if cur_id in visited:
                    continue
                visited.add(cur_id)
                cur_calls = conn.execute(
                    "SELECT called_name FROM method_calls WHERE caller_id = ?",
                    (cur_id,)
                ).fetchall()
                for c in cur_calls:
                    if c["called_name"] == start_name:
                        return True
                    if c["called_name"] in name_to_id:
                        stack.append(name_to_id[c["called_name"]])
            return False

        for r in rows:
            if has_cycle(r["method_id"], r["name"]):
                circular.append(r["name"])
        issues = []
        if missing:
            issues.append({"type": "missing_methods", "count": len(missing)})
        if circular:
            issues.append({"type": "circular_dependencies", "count": len(circular)})
        if isolated:
            issues.append({"type": "isolated_methods", "count": len(isolated)})
        healthy = len(issues) == 0
        return (1, {
            "healthy": healthy,
            "stats": {
                "method_count": len(rows),
                "avg_complexity": avg_complexity,
                "avg_body_lines": avg_body,
            },
            "issues": issues,
            "missing_methods": missing,
            "circular_dependencies": circular,
            "isolated_methods": isolated,
        }, None)

    # -----------------------------------------------------------------------
    # METHOD SIGNATURE — get the signature of a method
    # -----------------------------------------------------------------------

    def MethodSignature(self, params):
        method_name = self._p(params, "method_name")
        if not method_name:
            return self._err("NO_METHOD_NAME", "method_name required")
        conn = self._Conn()
        r = conn.execute(
            "SELECT method_id, name, source_code, arg_names, returns, cyclomatic, "
            "body_lines, origin_class, recursive, has_docstring "
            "FROM methods WHERE name = ? ORDER BY method_id LIMIT 1",
            (method_name,)
        ).fetchone()
        if not r:
            return self._err("NOT_FOUND", method_name)
        has_yield = False
        has_async = False
        arg_count = 0
        try:
            tree = ast.parse(r["source_code"])
            for node in ast.walk(tree):
                if isinstance(node, ast.Yield):
                    has_yield = True
                if isinstance(node, (ast.Await, ast.AsyncFunctionDef)):
                    has_async = True
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arg_count = len(node.args.args)
                    break
        except Exception:
            pass
        arg_names = []
        if r["arg_names"]:
            try:
                arg_names = json.loads(r["arg_names"])
            except Exception:
                arg_names = [a.strip() for a in r["arg_names"].split(",") if a.strip()]
        return_count = 0
        if r["returns"]:
            try:
                returns_data = json.loads(r["returns"])
                return_count = len(returns_data) if isinstance(returns_data, list) else 1
            except Exception:
                return_count = 1
        return (1, {
            "method_name": r["name"],
            "args": arg_names,
            "arg_count": len(arg_names) if arg_names else arg_count,
            "return_count": return_count,
            "has_yield": has_yield,
            "has_async": has_async,
            "origin_class": r["origin_class"],
            "cyclomatic": r["cyclomatic"],
        }, None)

    # -----------------------------------------------------------------------
    # CALL TREE — build a call tree from a method
    # -----------------------------------------------------------------------

    def CallTree(self, params):
        method_name = self._p(params, "method_name")
        if not method_name:
            return self._err("NO_METHOD_NAME", "method_name required")
        max_depth = self._p(params, "max_depth", 5)
        conn = self._Conn()
        all_names = set(
            r[0] for r in conn.execute("SELECT name FROM methods").fetchall()
        )
        name_to_id = {}
        for r in conn.execute("SELECT method_id, name FROM methods").fetchall():
            if r["name"] not in name_to_id:
                name_to_id[r["name"]] = r["method_id"]
        counts = {"resolved": 0, "unresolved": 0}

        def build(name, depth):
            children = []
            mid = name_to_id.get(name)
            if mid is None:
                return children
            calls = conn.execute(
                "SELECT called_name FROM method_calls WHERE caller_id = ?",
                (mid,)
            ).fetchall()
            for c in calls:
                cn = c["called_name"]
                is_resolved = cn in all_names
                if is_resolved:
                    counts["resolved"] += 1
                else:
                    counts["unresolved"] += 1
                node = {
                    "name": cn,
                    "resolved": is_resolved,
                    "depth": depth + 1,
                }
                if depth + 1 < max_depth and is_resolved:
                    node["children"] = build(cn, depth + 1)
                children.append(node)
            return children

        tree = {
            "name": method_name,
            "resolved": method_name in all_names,
            "depth": 0,
            "children": build(method_name, 0),
        }
        return (1, {
            "root": method_name,
            "tree": tree,
            "resolved": counts["resolved"],
            "unresolved": counts["unresolved"],
        }, None)

    # -----------------------------------------------------------------------
    # GLOBAL HEALTH — health check for the entire orchestrator
    # -----------------------------------------------------------------------

    def GlobalHealth(self, params=None):
        conn = self._Conn()
        total_methods = conn.execute("SELECT COUNT(*) FROM methods").fetchone()[0]
        total_classes = conn.execute("SELECT COUNT(*) FROM class_contracts").fetchone()[0]
        total_calls = conn.execute("SELECT COUNT(*) FROM method_calls").fetchone()[0]
        single_method_classes = conn.execute(
            "SELECT class_name FROM class_methods "
            "GROUP BY class_name HAVING COUNT(*) = 1"
        ).fetchall()
        all_method_names = set(
            r[0] for r in conn.execute("SELECT name FROM methods").fetchall()
        )
        called_names = set(
            r[0] for r in conn.execute(
                "SELECT DISTINCT called_name FROM method_calls"
            ).fetchall()
        )
        unresolved_calls = called_names - all_method_names
        dead_methods = conn.execute(
            "SELECT COUNT(*) FROM methods WHERE call_count = 0"
        ).fetchone()[0]
        class_complexity = conn.execute(
            "SELECT cm.class_name, AVG(m.cyclomatic) as avg_cx "
            "FROM class_methods cm JOIN methods m ON cm.method_id = m.method_id "
            "GROUP BY cm.class_name ORDER BY avg_cx DESC"
        ).fetchall()
        most_complex = [{
            "class_name": r["class_name"],
            "avg_complexity": round(r["avg_cx"] or 0, 2),
        } for r in class_complexity[:10]]
        issues = []
        if len(single_method_classes) > 0:
            issues.append({"type": "single_method_classes", "count": len(single_method_classes)})
        if dead_methods > 0:
            issues.append({"type": "dead_methods", "count": dead_methods})
        if len(unresolved_calls) > 0:
            issues.append({"type": "unresolved_calls", "count": len(unresolved_calls)})
        healthy = (total_methods > 0 and len(issues) == 0)
        return (1, {
            "healthy": healthy,
            "stats": {
                "total_classes": total_classes,
                "total_methods": total_methods,
                "total_calls": total_calls,
                "single_method_classes": len(single_method_classes),
                "dead_methods": dead_methods,
                "unresolved_calls": len(unresolved_calls),
            },
            "issues": issues,
            "most_complex_classes": most_complex,
        }, None)

    # -----------------------------------------------------------------------
    # INTERNAL — stdlib injection for compiled methods
    # -----------------------------------------------------------------------

    def _InjectStdlib(self, ns):
        import os, sys, time, json, re, sqlite3, hashlib
        import ast as _ast, collections, threading, typing, traceback
        import functools, itertools, copy, math, random, textwrap
        import io, uuid, logging, warnings, subprocess, pathlib
        import inspect, struct, base64, operator, string, pprint
        import argparse, configparser, csv, glob, fnmatch, pickle
        import socket, select, signal, mmap, ctypes, errno, stat
        import shutil, tempfile, weakref, gc, contextlib, decimal
        import fractions, array, queue, dataclasses, enum, abc
        import bisect, heapq, numbers, statistics, types as _types

        std = {
            "os": os, "sys": sys, "time": time, "json": json, "re": re,
            "sqlite3": sqlite3, "hashlib": hashlib, "ast": _ast,
            "collections": collections, "threading": threading,
            "typing": typing, "traceback": traceback, "functools": functools,
            "itertools": itertools, "copy": copy, "math": math,
            "random": random, "textwrap": textwrap, "io": io,
            "uuid": uuid, "logging": logging, "warnings": warnings,
            "subprocess": subprocess, "pathlib": pathlib,
            "inspect": inspect, "struct": struct, "base64": base64,
            "operator": operator, "string": string, "pprint": pprint,
            "argparse": argparse, "configparser": configparser,
            "csv": csv, "glob": glob, "fnmatch": fnmatch, "pickle": pickle,
            "socket": socket, "select": select, "signal": signal,
            "mmap": mmap, "ctypes": ctypes, "errno": errno, "stat": stat,
            "shutil": shutil, "tempfile": tempfile, "weakref": weakref,
            "gc": gc, "contextlib": contextlib, "decimal": decimal,
            "fractions": fractions, "array": array, "queue": queue,
            "dataclasses": dataclasses, "enum": enum, "abc": abc,
            "bisect": bisect, "heapq": heapq, "numbers": numbers,
            "statistics": statistics, "types": _types,
        }
        for name in ("Optional", "List", "Dict", "Tuple", "Any", "Union",
                      "Set", "Callable", "Iterator", "Generator", "Sequence",
                      "Mapping", "TypeVar", "Generic", "NoReturn", "ClassVar"):
            if hasattr(typing, name):
                std[name] = getattr(typing, name)
        for name in ("defaultdict", "OrderedDict", "Counter", "deque",
                      "namedtuple", "ChainMap"):
            if hasattr(collections, name):
                std[name] = getattr(collections, name)
        for name in ("wraps", "lru_cache", "partial", "reduce", "singledispatch"):
            if hasattr(functools, name):
                std[name] = getattr(functools, name)
        for name in ("chain", "product", "combinations", "permutations",
                      "cycle", "islice", "groupby", "accumulate", "count",
                      "repeat", "starmap", "tee", "zip_longest"):
            if hasattr(itertools, name):
                std[name] = getattr(itertools, name)
        for name in ("dataclass", "field", "asdict", "astuple", "replace"):
            if hasattr(dataclasses, name):
                std[name] = getattr(dataclasses, name)
        for name in ("contextmanager", "suppress", "closing", "ExitStack"):
            if hasattr(contextlib, name):
                std[name] = getattr(contextlib, name)
        for name in ("Path", "PurePath", "PurePosixPath", "PosixPath"):
            if hasattr(pathlib, name):
                std[name] = getattr(pathlib, name)
        for name in ("BytesIO", "StringIO", "TextIO", "BufferedReader", "TextIOWrapper"):
            if hasattr(io, name):
                std[name] = getattr(io, name)
        for name in ("Lock", "RLock", "Event", "Condition", "Semaphore", "Thread"):
            if hasattr(threading, name):
                std[name] = getattr(threading, name)
        for name in ("Queue", "LifoQueue", "PriorityQueue", "SimpleQueue"):
            if hasattr(queue, name):
                std[name] = getattr(queue, name)
        for name in ("Enum", "IntEnum", "auto", "Flag", "IntFlag"):
            if hasattr(enum, name):
                std[name] = getattr(enum, name)
        for name in ("ABC", "abstractmethod", "abstractproperty"):
            if hasattr(abc, name):
                std[name] = getattr(abc, name)
        ns.update(std)


# ---------------------------------------------------------------------------
# TEST / DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== METHOD ORCHESTRATOR ===")
    print()

    orch = MethodOrchestrator()

    # Step 1: Build method-centric DB from methods.sqlite
    print("--- Step 1: Build from methods.sqlite ---")
    ok, data, err = orch.Run("build", {})
    if ok:
        print(f"  Total methods:   {data['total_methods']}")
        print(f"  Unique methods:  {data['unique_methods']}")
        print(f"  Duplicates:      {data['duplicates_eliminated']}")
        print(f"  Classes:         {data['classes']}")
        print(f"  Call edges:      {data['call_edges']}")
    else:
        print(f"  BUILD FAILED: {err}")
        raise SystemExit(1)

    # Step 2: Call closure from targeted seeds
    print()
    print("--- Step 2: Call closure from ['read_state', 'set_config'] ---")
    ok, closure, err = orch.Run("call_closure", {"seeds": ["read_state", "set_config"]})
    if ok:
        print(f"  Seeds:      read_state, set_config")
        print(f"  Closure:    {closure['closure_size']} methods")
        print(f"  Names:      {', '.join(closure['closure_names'][:15])}...")
    else:
        print(f"  CLOSURE FAILED: {err}")

    # Step 3: Compose a class from an existing class's methods
    print()
    print("--- Step 3: Compose 'DynamicConfig' from Config class ---")
    ok, comp, err = orch.Run("compose_from_class", {
        "source_class": "Config",
        "target_class": "DynamicConfig",
        "description": "Composed from Config class methods",
    })
    if ok:
        print(f"  Class:      {comp['class_name']}")
        print(f"  Methods:    {comp['method_count']}")
        print(f"  Names:      {', '.join(comp['methods'][:15])}...")
    else:
        print(f"  COMPOSE FAILED: {err}")

    # Step 4: Compose a class from explicit method IDs
    print()
    print("--- Step 4: Compose 'MiniAgent' from explicit IDs ---")
    ok, methods, _ = orch.Run("list_methods", {"limit": 5})
    if ok:
        ids = [m["method_id"] for m in methods["methods"]]
        ok2, comp2, err2 = orch.Run("compose", {
            "class_name": "MiniAgent",
            "method_ids": ids,
            "description": "Composed from first 5 methods",
        })
        if ok2:
            print(f"  Class:      {comp2['class_name']}")
            print(f"  Methods:    {comp2['method_count']}")
            print(f"  Names:      {', '.join(comp2['methods'])}")
        else:
            print(f"  COMPOSE FAILED: {err2}")

    # Step 5: Materialize and call
    print()
    print("--- Step 5: Materialize 'DynamicConfig' and call read_state ---")
    ok, mat, err = orch.Run("materialize", {
        "class_name": "DynamicConfig",
        "init_args": {"state": {"version": "1.0", "composed": True}, "config": {}},
    })
    if ok:
        instance = mat["instance"]
        print(f"  Instance:   {instance}")
        print(f"  Methods:    {mat['method_count']}")
        print(f"  has Run:    {hasattr(instance, 'Run')}")
        print(f"  has read_state: {hasattr(instance, 'read_state')}")

        if hasattr(instance, "read_state"):
            try:
                r = instance.read_state(None)
                print(f"  read_state() = {r}")
            except Exception as e:
                print(f"  read_state() raised: {type(e).__name__}: {e}")

        if hasattr(instance, "Run"):
            try:
                r = instance.Run("read_state", {})
                print(f"  Run('read_state', {{}}) = {r}")
            except Exception as e:
                print(f"  Run raised: {type(e).__name__}: {e}")
    else:
        print(f"  MATERIALIZE FAILED: {err}")

    # Step 6: Class info
    print()
    print("--- Step 6: DynamicConfig class info ---")
    ok, info, _ = orch.Run("class_info", {"class_name": "DynamicConfig"})
    if ok:
        print(f"  Class: {info['class_name']}")
        print(f"  Methods ({info['count']}):")
        for m in info["methods"][:10]:
            print(f"    {m['slot']:25s}  id={m['method_id']:5d}  cx={m['cyclomatic']:3d}  from={m['origin']}")
        if info["count"] > 10:
            print(f"    ... and {info['count'] - 10} more")

    # Step 7: Method info
    print()
    print("--- Step 7: Method info for method_id=1 ---")
    ok, mi, _ = orch.Run("method_info", {"method_id": 5})
    if ok:
        print(f"  Method:    {mi['name']}")
        print(f"  Origin:    {mi['origin_class']}")
        print(f"  Calls:     {mi['calls'][:10]}")
        print(f"  Called by: {len(mi['called_by'])} methods")
        print(f"  Source:    {mi['source_preview'][:100]}...")

    # Step 8: Stats
    print()
    print("--- Step 8: Final stats ---")
    ok, stats, _ = orch.Run("stats", {})
    if ok:
        for k, v in stats["counts"].items():
            print(f"  {k:25s} {v}")
        print(f"  {'composed':25s} {stats['stats']['composed']}")
        print(f"  {'materialized':25s} {stats['stats']['materialized']}")

    # Step 9: Show a composed class is just a projection
    print()
    print("--- Step 9: Compose 'RebelConfig' sharing methods with DynamicConfig ---")
    ok, dyn_info, _ = orch.Run("class_info", {"class_name": "DynamicConfig"})
    if ok:
        shared_ids = [m["method_id"] for m in dyn_info["methods"][:5]]
        ok2, rebel, _ = orch.Run("compose", {
            "class_name": "RebelConfig",
            "method_ids": shared_ids,
            "description": "Shares 5 methods with DynamicConfig",
        })
        if ok2:
            print(f"  RebelConfig:   {rebel['method_count']} methods")
            print(f"  Shared with DynamicConfig: {len(shared_ids)} methods")
            print(f"  Method names:  {', '.join(rebel['methods'])}")

            ok3, rmat, _ = orch.Run("materialize", {
                "class_name": "RebelConfig",
                "init_args": {"state": {"name": "rebel"}},
            })
            if ok3:
                rinst = rmat["instance"]
                if hasattr(rinst, "read_state"):
                    try:
                        r = rinst.read_state(None)
                        print(f"  RebelConfig.read_state() = {r}")
                    except Exception as e:
                        print(f"  RebelConfig.read_state() raised: {e}")

    print()
    print("=== ORCHESTRATOR DEMO COMPLETE ===")
