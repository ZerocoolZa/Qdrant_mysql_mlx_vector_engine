#!/usr/bin/env python3

#[@GHOST]{[@file<unit_discovery.py>][@domain<Dom_Db>][@role<discovery>][@auth<cascade>][@date<2026-07-01>][@ver<2.0.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<discovery>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded_paths>]}

"""
UnitDiscovery — automatic computation unit discovery from the call graph.

Instead of manually defining units by class boundaries, this module
discovers the smallest self-contained executable behaviors from the
method call graph using:

  1. Call graph extraction (method → method edges)
  2. Strongly Connected Components (Tarjan's algorithm)
  3. Call closure (transitive call reachability)
  4. State dependency analysis (shared state reads/writes)
  5. Side-effect compatibility (pure vs impure clustering)
  6. Minimal executable cluster merging

The result: computation units that emerge from behavior, not class names.

Architecture:
  discovered_units       — auto-discovered units with member methods
  discovery_edges        — call graph edges used for discovery
  scc_results            — Tarjan SCC results
  cluster_analysis       — per-cluster state/side-effect analysis
  discovery_stats        — aggregate discovery statistics

Usage:
  discovery = UnitDiscovery()
  discovery.Run("discover", {"method_db": "/tmp/method_orchestrator.sqlite"})
  discovery.Run("units", {})
  discovery.Run("unit_detail", {"unit_name": "Cluster_0"})
  discovery.Run("sccs", {})
  discovery.Run("graph", {})
"""

import ast
import json
import sqlite3
import time
import hashlib
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set

from SuperConfig import DB, RUNTIME


SCHEMA_DISCOVERY = """
CREATE TABLE IF NOT EXISTS discovered_units (
    unit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name       TEXT NOT NULL UNIQUE,
    unit_hash       TEXT NOT NULL,
    member_methods  TEXT NOT NULL,
    member_count    INTEGER NOT NULL,
    scc_id          INTEGER,
    is_scc          INTEGER DEFAULT 0,
    has_pure        INTEGER DEFAULT 0,
    has_impure      INTEGER DEFAULT 0,
    shared_state    TEXT,
    side_effects    TEXT,
    entry_methods   TEXT,
    exit_methods    TEXT,
    callable_from   TEXT,
    discovered_at   REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_du_hash ON discovered_units(unit_hash);

CREATE TABLE IF NOT EXISTS discovery_edges (
    edge_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    caller          TEXT NOT NULL,
    callee          TEXT NOT NULL,
    edge_type       TEXT DEFAULT 'call',
    weight          REAL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_de_caller ON discovery_edges(caller);
CREATE INDEX IF NOT EXISTS idx_de_callee ON discovery_edges(callee);

CREATE TABLE IF NOT EXISTS scc_results (
    scc_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_methods  TEXT NOT NULL,
    member_count    INTEGER NOT NULL,
    is_trivial      INTEGER DEFAULT 1,
    has_cycle       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cluster_analysis (
    cluster_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name       TEXT NOT NULL,
    state_reads     TEXT,
    state_writes    TEXT,
    shared_state    TEXT,
    external_calls  TEXT,
    pure_members    TEXT,
    impure_members  TEXT,
    cohesion_score  REAL DEFAULT 0,
    coupling_score  REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS discovery_stats (
    stat_key        TEXT PRIMARY KEY,
    stat_value      TEXT
);
"""


class UnitDiscovery:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "discovery_db": DB.UNIT_DISCOVERY_DB,
            "method_db": DB.METHOD_ORCHESTRATOR_DB,
            "cu_db": DB.COMPUTATION_UNITS_DB,
            "conn": None,
            "method_conn": None,
            "cu_conn": None,
            "graph": {},
            "reverse_graph": {},
            "method_info": {},
            "stats": {
                "methods_scanned": 0,
                "edges_built": 0,
                "sccs_found": 0,
                "units_discovered": 0,
                "trivial_sccs": 0,
                "nontrivial_sccs": 0,
                "pure_units": 0,
                "impure_units": 0,
                "max_cluster_size": 0,
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
            self.state["conn"] = sqlite3.connect(self.state["discovery_db"])
            self.state["conn"].row_factory = sqlite3.Row
        return self.state["conn"]

    def _MethodConn(self):
        path = self.state["method_db"]
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    def _CuConn(self):
        if self.state["cu_conn"] is None:
            self.state["cu_conn"] = sqlite3.connect(self.state["cu_db"])
            self.state["cu_conn"].row_factory = sqlite3.Row
        return self.state["cu_conn"]

    def _InitDb(self):
        conn = sqlite3.connect(self.state["discovery_db"])
        conn.executescript(SCHEMA_DISCOVERY)
        conn.commit()
        conn.close()

    def Run(self, command, params=None):
        dispatch = {
            "discover": self.Discover,
            "units": self.Units,
            "unit_detail": self.UnitDetail,
            "sccs": self.SCCs,
            "graph": self.Graph,
            "stats": self.Stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        fn = dispatch.get(command)
        if fn is None:
            return self._err("UNKNOWN_COMMAND", str(command))
        return fn(params or {})

    # -----------------------------------------------------------------------
    # DISCOVER — full pipeline: extract → SCC → cluster → analyze → store
    # -----------------------------------------------------------------------

    def Discover(self, params):
        method_db = self._p(params, "method_db", self.state["method_db"])
        if method_db:
            self.state["method_db"] = method_db

        t0 = time.time()

        self._LoadMethods()
        self._BuildCallGraph()
        sccs = self._TarjanSCC()
        clusters = self._FormClusters(sccs)
        self._AnalyzeClusters(clusters)
        self._StoreUnits(clusters, sccs)

        elapsed = (time.time() - t0) * 1000

        conn = self._Conn()
        conn.execute(
            "INSERT OR REPLACE INTO discovery_stats (stat_key, stat_value) VALUES ('last_discovery_ms', ?)",
            (str(round(elapsed, 2)),)
        )
        conn.execute(
            "INSERT OR REPLACE INTO discovery_stats (stat_key, stat_value) VALUES ('total_methods', ?)",
            (str(self.state["stats"]["methods_scanned"]),)
        )
        conn.execute(
            "INSERT OR REPLACE INTO discovery_stats (stat_key, stat_value) VALUES ('total_edges', ?)",
            (str(self.state["stats"]["edges_built"]),)
        )
        conn.execute(
            "INSERT OR REPLACE INTO discovery_stats (stat_key, stat_value) VALUES ('total_sccs', ?)",
            (str(self.state["stats"]["sccs_found"]),)
        )
        conn.execute(
            "INSERT OR REPLACE INTO discovery_stats (stat_key, stat_value) VALUES ('total_units', ?)",
            (str(self.state["stats"]["units_discovered"]),)
        )
        conn.commit()

        return (1, {
            "methods_scanned": self.state["stats"]["methods_scanned"],
            "edges_built": self.state["stats"]["edges_built"],
            "sccs_found": self.state["stats"]["sccs_found"],
            "trivial_sccs": self.state["stats"]["trivial_sccs"],
            "nontrivial_sccs": self.state["stats"]["nontrivial_sccs"],
            "units_discovered": self.state["stats"]["units_discovered"],
            "pure_units": self.state["stats"]["pure_units"],
            "impure_units": self.state["stats"]["impure_units"],
            "max_cluster_size": self.state["stats"]["max_cluster_size"],
            "discovery_ms": round(elapsed, 2),
        }, None)

    # -----------------------------------------------------------------------
    # LOAD METHODS — extract all methods from orchestrator DB
    # -----------------------------------------------------------------------

    def _LoadMethods(self):
        conn = self._MethodConn()

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        methods = {}
        if "methods" in table_names:
            cols = [c["name"] for c in conn.execute("PRAGMA table_info(methods)").fetchall()]
            name_col = "name" if "name" in cols else "method_name"
            cls_col = "origin_class" if "origin_class" in cols else ("class_name" if "class_name" in cols else None)
            pure_col = "is_pure" if "is_pure" in cols else None
            se_col = "has_side_effects" if "has_side_effects" in cols else None

            select_cols = ["method_id", name_col, "source_code", "arg_names"]
            if cls_col:
                select_cols.append(cls_col)
            if pure_col:
                select_cols.append(pure_col)
            if se_col:
                select_cols.append(se_col)

            query = f"SELECT {', '.join(select_cols)} FROM methods"
            rows = conn.execute(query).fetchall()
            for r in rows:
                mname = r[name_col]
                cname = r[cls_col] if cls_col else ""
                key = f"{cname}.{mname}" if cname else mname
                methods[key] = {
                    "method_id": r["method_id"],
                    "method_name": mname,
                    "class_name": cname or "",
                    "source_code": r["source_code"] or "",
                    "arg_names": json.loads(r["arg_names"]) if r["arg_names"] else [],
                    "is_pure": bool(r[pure_col]) if pure_col and r[pure_col] is not None else None,
                    "has_side_effects": bool(r[se_col]) if se_col and r[se_col] is not None else None,
                }

        if not methods and "unique_methods" in table_names:
            cols = [c["name"] for c in conn.execute("PRAGMA table_info(unique_methods)").fetchall()]
            name_col = "name" if "name" in cols else "method_name"
            cls_col = "origin_class" if "origin_class" in cols else ("class_name" if "class_name" in cols else None)
            select_cols = ["method_id", name_col, "source_code", "arg_names"]
            if cls_col:
                select_cols.append(cls_col)
            query = f"SELECT {', '.join(select_cols)} FROM unique_methods"
            rows = conn.execute(query).fetchall()
            for r in rows:
                mname = r[name_col]
                cname = r[cls_col] if cls_col else ""
                key = f"{cname}.{mname}" if cname else mname
                methods[key] = {
                    "method_id": r["method_id"],
                    "method_name": mname,
                    "class_name": cname or "",
                    "source_code": r["source_code"] or "",
                    "arg_names": json.loads(r["arg_names"]) if r["arg_names"] else [],
                    "is_pure": None,
                    "has_side_effects": None,
                }

        if not methods:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%method%'"
            ).fetchall()
            fallback = [r["name"] for r in rows]
            if fallback:
                for tname in fallback:
                    try:
                        cols = conn.execute(f"PRAGMA table_info({tname})").fetchall()
                        col_names = [c["name"] for c in cols]
                        if "method_name" in col_names and "source_code" in col_names:
                            cls_col = "class_name" if "class_name" in col_names else None
                            q = f"SELECT method_name, {cls_col}, source_code FROM {tname}" if cls_col else f"SELECT method_name, source_code FROM {tname}"
                            for r in conn.execute(q).fetchall():
                                cls = r[cls_col] if cls_col else ""
                                key = f"{cls}.{r['method_name']}" if cls else r["method_name"]
                                methods[key] = {
                                    "method_id": len(methods),
                                    "method_name": r["method_name"],
                                    "class_name": cls,
                                    "source_code": r["source_code"] or "",
                                    "arg_names": [],
                                    "is_pure": None,
                                    "has_side_effects": None,
                                }
                            break
                    except Exception:
                        continue

        conn.close()

        for key, info in methods.items():
            if info["is_pure"] is None:
                info["is_pure"], info["has_side_effects"] = self._AnalyzePurity(info["source_code"])

        self.state["method_info"] = methods
        self.state["stats"]["methods_scanned"] = len(methods)

    def _AnalyzePurity(self, source_code):
        if not source_code:
            return True, False
        try:
            tree = ast.parse(source_code)
        except Exception:
            return True, False

        impure_calls = {"print", "open", "exec", "eval", "input", "compile",
                        "setattr", "delattr", "globals", "locals"}
        impure_attrs = {"write", "writelines", "flush", "close", "insert",
                        "append", "extend", "pop", "remove", "clear",
                        "update", "popitem", "setdefault", "sort", "reverse"}

        has_side_effects = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in impure_calls:
                    has_side_effects = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr in impure_attrs:
                    has_side_effects = True
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "self":
                            has_side_effects = True

        is_pure = not has_side_effects
        return is_pure, has_side_effects

    # -----------------------------------------------------------------------
    # BUILD CALL GRAPH — extract method→method edges from AST
    # -----------------------------------------------------------------------

    def _BuildCallGraph(self):
        graph = defaultdict(set)
        reverse_graph = defaultdict(set)
        edges = []

        method_names = set()
        bare_names = set()
        for key in self.state["method_info"]:
            method_names.add(key)
            bare_names.add(self.state["method_info"][key]["method_name"])

        conn = self._Conn()
        conn.execute("DELETE FROM discovery_edges")

        for key, info in self.state["method_info"].items():
            source = info["source_code"]
            if not source:
                continue
            try:
                tree = ast.parse(source)
            except Exception:
                continue

            calls = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        callee = node.func.id
                        if callee in bare_names and callee != info["method_name"]:
                            calls.add(callee)
                    elif isinstance(node.func, ast.Attribute):
                        callee = node.func.attr
                        if callee in bare_names and callee != info["method_name"]:
                            calls.add(callee)

            for callee in calls:
                callee_keys = [k for k in method_names
                               if self.state["method_info"][k]["method_name"] == callee]
                for ck in callee_keys:
                    graph[key].add(ck)
                    reverse_graph[ck].add(key)
                    edges.append((key, ck))
                    conn.execute(
                        "INSERT INTO discovery_edges (caller, callee, edge_type, weight) VALUES (?,?,?,?)",
                        (key, ck, "call", 1.0)
                    )

        conn.commit()
        self.state["graph"] = dict(graph)
        self.state["reverse_graph"] = dict(reverse_graph)
        self.state["stats"]["edges_built"] = len(edges)

    # -----------------------------------------------------------------------
    # TARJAN SCC — find strongly connected components
    # -----------------------------------------------------------------------

    def _TarjanSCC(self):
        index_counter = [0]
        stack = []
        lowlink = {}
        index = {}
        on_stack = {}
        result = []

        all_nodes = set(self.state["method_info"].keys())
        for n in all_nodes:
            if n not in index:
                self._StrongConnect(n, index_counter, stack, lowlink,
                                    index, on_stack, result)

        conn = self._Conn()
        conn.execute("DELETE FROM scc_results")

        sccs = []
        for i, scc in enumerate(result):
            is_trivial = len(scc) == 1
            has_cycle = len(scc) > 1
            conn.execute(
                "INSERT INTO scc_results (scc_id, member_methods, member_count, is_trivial, has_cycle) "
                "VALUES (?,?,?,?,?)",
                (i + 1, json.dumps(scc), len(scc),
                 1 if is_trivial else 0, 1 if has_cycle else 0)
            )
            sccs.append({"scc_id": i + 1, "members": scc, "is_trivial": is_trivial})

        conn.commit()
        self.state["stats"]["sccs_found"] = len(sccs)
        self.state["stats"]["trivial_sccs"] = sum(1 for s in sccs if s["is_trivial"])
        self.state["stats"]["nontrivial_sccs"] = sum(1 for s in sccs if not s["is_trivial"])

        return sccs

    def _StrongConnect(self, node, index_counter, stack, lowlink,
                       index, on_stack, result):
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        neighbors = self.state["graph"].get(node, set())
        for neighbor in neighbors:
            if neighbor not in index:
                self._StrongConnect(neighbor, index_counter, stack, lowlink,
                                    index, on_stack, result)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif on_stack.get(neighbor, False):
                lowlink[node] = min(lowlink[node], index[neighbor])

        if lowlink[node] == index[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == node:
                    break
            result.append(scc)

    # -----------------------------------------------------------------------
    # FORM CLUSTERS — merge SCCs by call closure + state dependency
    # -----------------------------------------------------------------------

    def _FormClusters(self, sccs):
        scc_of = {}
        for scc in sccs:
            for member in scc["members"]:
                scc_of[member] = scc["scc_id"]

        scc_graph = defaultdict(set)
        for caller, callees in self.state["graph"].items():
            caller_scc = scc_of.get(caller)
            if caller_scc is None:
                continue
            for callee in callees:
                callee_scc = scc_of.get(callee)
                if callee_scc is not None and callee_scc != caller_scc:
                    scc_graph[caller_scc].add(callee_scc)

        merged = self._MergeByStateDependency(sccs, scc_of)

        clusters = []
        for cluster_methods in merged:
            entry_methods = self._FindEntryMethods(cluster_methods)
            exit_methods = self._FindExitMethods(cluster_methods)
            callable_from = self._FindExternalCallers(cluster_methods)

            member_list = sorted(cluster_methods)
            unit_hash = hashlib.sha256(
                "|".join(member_list).encode()
            ).hexdigest()[:16]

            clusters.append({
                "unit_name": f"Cluster_{len(clusters)}",
                "unit_hash": unit_hash,
                "members": member_list,
                "member_count": len(member_list),
                "entry_methods": entry_methods,
                "exit_methods": exit_methods,
                "callable_from": callable_from,
                "scc_ids": list(set(scc_of.get(m, -1) for m in cluster_methods)),
            })

        self.state["stats"]["units_discovered"] = len(clusters)
        self.state["stats"]["max_cluster_size"] = max((c["member_count"] for c in clusters), default=0)

        return clusters

    def _MergeByStateDependency(self, sccs, scc_of):
        state_groups = defaultdict(set)

        for key, info in self.state["method_info"].items():
            state_vars = self._ExtractStateVars(info["source_code"])
            for var in state_vars:
                state_groups[var].add(key)

        parent = {}
        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for scc in sccs:
            for m in scc["members"]:
                parent[m] = m

        changed = True
        while changed:
            changed = False
            for caller, callees in self.state["graph"].items():
                for callee in callees:
                    if find(caller) != find(callee):
                        union(caller, callee)
                        changed = True

        changed = True
        while changed:
            changed = False
            for caller, callees in self.state["graph"].items():
                for callee in callees:
                    if find(caller) == find(callee):
                        continue
                    caller_state = self._ExtractStateVars(
                        self.state["method_info"].get(caller, {}).get("source_code", ""))
                    callee_state = self._ExtractStateVars(
                        self.state["method_info"].get(callee, {}).get("source_code", ""))
                    if caller_state & callee_state:
                        union(caller, callee)
                        changed = True

            for caller, callees in self.state["graph"].items():
                for callee in callees:
                    if find(caller) == find(callee):
                        continue
                    caller_root = find(caller)
                    callee_root = find(callee)
                    caller_cluster = [m for m in parent if find(m) == caller_root]
                    callee_cluster = [m for m in parent if find(m) == callee_root]
                    caller_state = set()
                    for m in caller_cluster:
                        caller_state |= self._ExtractStateVars(
                            self.state["method_info"].get(m, {}).get("source_code", ""))
                    callee_state = set()
                    for m in callee_cluster:
                        callee_state |= self._ExtractStateVars(
                            self.state["method_info"].get(m, {}).get("source_code", ""))
                    if caller_state & callee_state:
                        union(caller, callee)
                        changed = True

        for caller, callees in self.state["graph"].items():
            for callee in callees:
                if find(caller) != find(callee):
                    callee_info = self.state["method_info"].get(callee)
                    if callee_info and callee_info["is_pure"]:
                        caller_info = self.state["method_info"].get(caller)
                        if caller_info and not caller_info["is_pure"]:
                            union(caller, callee)

        clusters_map = defaultdict(set)
        for m in parent:
            clusters_map[find(m)].add(m)

        merged = list(clusters_map.values())

        all_keys = set(self.state["method_info"].keys())
        for key in all_keys:
            if key not in parent:
                merged.append({key})

        return merged

    def _ExtractStateVars(self, source_code):
        vars_found = set()
        if not source_code:
            return vars_found
        try:
            tree = ast.parse(source_code)
        except Exception:
            return vars_found

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "self":
                    vars_found.add(node.attr)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "self":
                            vars_found.add(target.attr)

        return vars_found

    def _IsCallable(self, cluster, method):
        for m in cluster:
            if method in self.state["graph"].get(m, set()):
                return True
            if m in self.state["graph"].get(method, set()):
                return True
        return False

    def _FindEntryMethods(self, members):
        entries = []
        for m in members:
            callers = self.state["reverse_graph"].get(m, set())
            external = callers - members
            if not external or len(external) > 0:
                if not callers or len(callers - members) > 0:
                    entries.append(m)
        if not entries:
            entries = list(members)[:1]
        return entries

    def _FindExitMethods(self, members):
        exits = []
        for m in members:
            callees = self.state["graph"].get(m, set())
            external = callees - members
            if external:
                exits.append(m)
        return exits

    def _FindExternalCallers(self, members):
        callers = set()
        for m in members:
            for c in self.state["reverse_graph"].get(m, set()):
                if c not in members:
                    callers.add(c)
        return sorted(callers)

    # -----------------------------------------------------------------------
    # ANALYZE CLUSTERS — state, side effects, cohesion, coupling
    # -----------------------------------------------------------------------

    def _AnalyzeClusters(self, clusters):
        conn = self._Conn()
        conn.execute("DELETE FROM cluster_analysis")

        for cluster in clusters:
            members = cluster["members"]
            all_reads = set()
            all_writes = set()
            pure_members = []
            impure_members = []
            external_calls = set()

            for m in members:
                info = self.state["method_info"].get(m, {})
                source = info.get("source_code", "")
                reads, writes = self._StateReadsWrites(source)
                all_reads |= reads
                all_writes |= writes

                if info.get("is_pure"):
                    pure_members.append(m)
                else:
                    impure_members.append(m)

                ext = self.state["graph"].get(m, set()) - set(members)
                external_calls |= ext

            shared = all_reads & all_writes
            cohesion = len(shared) / max(len(all_reads | all_writes), 1)
            coupling = len(external_calls) / max(len(members), 1)

            conn.execute(
                "INSERT INTO cluster_analysis "
                "(unit_name, state_reads, state_writes, shared_state, "
                "external_calls, pure_members, impure_members, "
                "cohesion_score, coupling_score) VALUES (?,?,?,?,?,?,?,?,?)",
                (cluster["unit_name"],
                 json.dumps(sorted(all_reads)),
                 json.dumps(sorted(all_writes)),
                 json.dumps(sorted(shared)),
                 json.dumps(sorted(external_calls)),
                 json.dumps(pure_members),
                 json.dumps(impure_members),
                 round(cohesion, 4), round(coupling, 4))
            )

            cluster["shared_state"] = sorted(shared)
            cluster["pure_members"] = pure_members
            cluster["impure_members"] = impure_members
            cluster["external_calls"] = sorted(external_calls)
            cluster["cohesion"] = round(cohesion, 4)
            cluster["coupling"] = round(coupling, 4)

            if impure_members:
                self.state["stats"]["impure_units"] += 1
            else:
                self.state["stats"]["pure_units"] += 1

        conn.commit()

    def _StateReadsWrites(self, source_code):
        reads = set()
        writes = set()
        if not source_code:
            return reads, writes
        try:
            tree = ast.parse(source_code)
        except Exception:
            return reads, writes

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "self":
                            writes.add(target.attr)
            if isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name):
                    if node.target.value.id == "self":
                        writes.add(node.target.attr)
                        reads.add(node.target.attr)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "self":
                    if not isinstance(node.ctx, ast.Store):
                        reads.add(node.attr)

        return reads, writes

    # -----------------------------------------------------------------------
    # STORE UNITS
    # -----------------------------------------------------------------------

    def _StoreUnits(self, clusters, sccs):
        conn = self._Conn()
        conn.execute("DELETE FROM discovered_units")

        for cluster in clusters:
            scc_ids = cluster.get("scc_ids", [])
            is_scc = 1 if len(scc_ids) == 1 and not any(
                s["is_trivial"] for s in sccs if s["scc_id"] == scc_ids[0]
            ) else 0

            has_pure = 1 if cluster.get("pure_members") else 0
            has_impure = 1 if cluster.get("impure_members") else 0

            conn.execute(
                "INSERT INTO discovered_units "
                "(unit_name, unit_hash, member_methods, member_count, "
                "scc_id, is_scc, has_pure, has_impure, shared_state, "
                "side_effects, entry_methods, exit_methods, callable_from, "
                "discovered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cluster["unit_name"], cluster["unit_hash"],
                 json.dumps(cluster["members"]), cluster["member_count"],
                 scc_ids[0] if scc_ids else None, is_scc,
                 has_pure, has_impure,
                 json.dumps(cluster.get("shared_state", [])),
                 json.dumps(cluster.get("external_calls", [])),
                 json.dumps(cluster.get("entry_methods", [])),
                 json.dumps(cluster.get("exit_methods", [])),
                 json.dumps(cluster.get("callable_from", [])),
                 time.time())
            )

        conn.commit()

    # -----------------------------------------------------------------------
    # QUERY METHODS
    # -----------------------------------------------------------------------

    def Units(self, params):
        conn = self._Conn()
        limit = self._p(params, "limit", 50)
        rows = conn.execute(
            "SELECT * FROM discovered_units ORDER BY member_count DESC LIMIT ?",
            (limit,)
        ).fetchall()

        return (1, {
            "count": len(rows),
            "units": [{
                "unit_name": r["unit_name"],
                "unit_hash": r["unit_hash"],
                "member_count": r["member_count"],
                "members": json.loads(r["member_methods"]),
                "has_pure": bool(r["has_pure"]),
                "has_impure": bool(r["has_impure"]),
                "entry_methods": json.loads(r["entry_methods"]),
                "exit_methods": json.loads(r["exit_methods"]),
                "callable_from": json.loads(r["callable_from"]),
            } for r in rows],
        }, None)

    def UnitDetail(self, params):
        unit_name = self._p(params, "unit_name")
        if not unit_name:
            return self._err("NO_UNIT_NAME", "unit_name required")

        conn = self._Conn()
        unit = conn.execute(
            "SELECT * FROM discovered_units WHERE unit_name = ?",
            (unit_name,)
        ).fetchone()
        if not unit:
            return self._err("NOT_FOUND", unit_name)

        analysis = conn.execute(
            "SELECT * FROM cluster_analysis WHERE unit_name = ?",
            (unit_name,)
        ).fetchone()

        members = json.loads(unit["member_methods"])
        member_details = []
        for m in members:
            info = self.state["method_info"].get(m, {})
            member_details.append({
                "method": m,
                "class": info.get("class_name", ""),
                "is_pure": info.get("is_pure"),
                "has_side_effects": info.get("has_side_effects"),
            })

        return (1, {
            "unit_name": unit["unit_name"],
            "unit_hash": unit["unit_hash"],
            "member_count": unit["member_count"],
            "members": member_details,
            "entry_methods": json.loads(unit["entry_methods"]),
            "exit_methods": json.loads(unit["exit_methods"]),
            "callable_from": json.loads(unit["callable_from"]),
            "shared_state": json.loads(unit["shared_state"]),
            "side_effects": json.loads(unit["side_effects"]),
            "cohesion": analysis["cohesion_score"] if analysis else 0,
            "coupling": analysis["coupling_score"] if analysis else 0,
            "pure_members": json.loads(analysis["pure_members"]) if analysis else [],
            "impure_members": json.loads(analysis["impure_members"]) if analysis else [],
        }, None)

    def SCCs(self, params):
        conn = self._Conn()
        rows = conn.execute(
            "SELECT * FROM scc_results ORDER BY member_count DESC"
        ).fetchall()

        return (1, {
            "count": len(rows),
            "sccs": [{
                "scc_id": r["scc_id"],
                "member_count": r["member_count"],
                "members": json.loads(r["member_methods"]),
                "is_trivial": bool(r["is_trivial"]),
                "has_cycle": bool(r["has_cycle"]),
            } for r in rows],
        }, None)

    def Graph(self, params):
        conn = self._Conn()
        rows = conn.execute(
            "SELECT caller, callee, edge_type FROM discovery_edges"
        ).fetchall()

        return (1, {
            "nodes": len(self.state["method_info"]),
            "edges": len(rows),
            "edge_list": [{
                "caller": r["caller"],
                "callee": r["callee"],
                "type": r["edge_type"],
            } for r in rows],
        }, None)

    def Stats(self, params=None):
        conn = self._Conn()
        counts = {
            "units": conn.execute("SELECT COUNT(*) FROM discovered_units").fetchone()[0],
            "edges": conn.execute("SELECT COUNT(*) FROM discovery_edges").fetchone()[0],
            "sccs": conn.execute("SELECT COUNT(*) FROM scc_results").fetchone()[0],
            "clusters_analyzed": conn.execute("SELECT COUNT(*) FROM cluster_analysis").fetchone()[0],
        }
        stat_rows = conn.execute(
            "SELECT stat_key, stat_value FROM discovery_stats"
        ).fetchall()
        stored = {r["stat_key"]: r["stat_value"] for r in stat_rows}

        return (1, {
            "counts": counts,
            "stats": self.state["stats"],
            "stored": stored,
        }, None)

    def read_state(self, params=None):
        safe = dict(self.state)
        for key in ("conn", "method_conn", "cu_conn"):
            safe.pop(key, None)
        safe.pop("graph", None)
        safe.pop("reverse_graph", None)
        safe.pop("method_info", None)
        return (1, safe, None)

    def set_config(self, params=None):
        if not params:
            return self._err("NO_PARAMS", "missing config")
        cfg = params.get("config", params)
        if isinstance(cfg, dict):
            self.state.update(cfg)
        return (1, dict(self.state), None)


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== UNIT DISCOVERY ===")
    print()

    import hashlib as _hl
    from method_orchestrator import MethodOrchestrator

    # Step 1: Insert methods directly into orchestrator DB
    print("--- Step 1: Ingest methods into orchestrator ---")

    test_methods = [
        ("LoadConfig", "ConfigManager", "def LoadConfig(self, params):\n    path = params.get('path', '')\n    self.config = {'path': path}\n    self.ValidateConfig({'path': path})\n    return (1, self.config, None)"),
        ("ValidateConfig", "ConfigManager", "def ValidateConfig(self, params):\n    path = params.get('path', '')\n    if not path:\n        return (0, None, ('NO_PATH', 'missing path', 0))\n    self.config_valid = True\n    return (1, True, None)"),
        ("ReadConfig", "ConfigManager", "def ReadConfig(self, params):\n    return (1, getattr(self, 'config', {}), None)"),
        ("WriteConfig", "ConfigManager", "def WriteConfig(self, params):\n    self.config = params.get('config', {})\n    self.ValidateConfig(params)\n    return (1, True, None)"),
        ("ProcessData", "DataProcessor", "def ProcessData(self, params):\n    data = params.get('data', [])\n    self.results = [x * 2 for x in data]\n    self.ValidateConfig(params)\n    return (1, self.results, None)"),
        ("AggregateData", "DataProcessor", "def AggregateData(self, params):\n    results = getattr(self, 'results', [])\n    total = sum(results)\n    return (1, {'total': total}, None)"),
        ("ExportData", "DataProcessor", "def ExportData(self, params):\n    results = getattr(self, 'results', [])\n    return (1, {'exported': len(results)}, None)"),
        ("ParseJson", "Utils", "def ParseJson(self, params):\n    import json\n    text = params.get('text', '{}')\n    return (1, json.loads(text), None)"),
        ("FormatOutput", "Utils", "def FormatOutput(self, params):\n    data = params.get('data', {})\n    return (1, str(data), None)"),
        ("HashKey", "Utils", "def HashKey(self, params):\n    import hashlib\n    key = params.get('key', '')\n    return (1, hashlib.md5(key.encode()).hexdigest(), None)"),
    ]

    # Initialize orchestrator DB schema
    orch = MethodOrchestrator()

    conn = sqlite3.connect(DB.METHOD_ORCHESTRATOR_DB)
    conn.execute("DELETE FROM methods")
    conn.execute("DELETE FROM class_methods")
    conn.execute("DELETE FROM method_calls")
    conn.execute("DELETE FROM class_contracts")

    for method_name, class_name, source in test_methods:
        ast_hash = _hl.md5(source.encode()).hexdigest()
        call_names = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        call_names.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        call_names.append(node.func.attr)
        except Exception:
            pass

        cur = conn.execute(
            "INSERT INTO methods "
            "(name, source_code, ast_hash, arg_names, returns, "
            "cyclomatic, max_nesting, body_lines, call_count, "
            "call_names, recursive, has_docstring, is_empty, "
            "origin_class, origin_qualname, version, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (method_name, source, ast_hash,
             json.dumps(["self", "params"]), "tuple3",
             1, 1, len(source.splitlines()), len(call_names),
             ",".join(call_names), 0, 0, 0,
             class_name, f"{class_name}.{method_name}", 1, time.time())
        )
        mid = cur.lastrowid
        conn.execute(
            "INSERT INTO class_methods (class_name, method_id, slot_name) VALUES (?,?,?)",
            (class_name, mid, method_name)
        )
        for cname in call_names:
            conn.execute(
                "INSERT INTO method_calls (caller_id, called_name) VALUES (?,?)",
                (mid, cname)
            )
        conn.execute(
            "INSERT OR REPLACE INTO class_contracts "
            "(class_name, required_state, description, created_at) "
            "VALUES (?,?,?,?)",
            (class_name, '{"state": "dict"}', "demo", time.time())
        )
        print(f"  {method_name:20s}  id={mid}  class={class_name}  calls={call_names}")

    conn.commit()
    conn.close()

    # Step 2: Run discovery
    print()
    print("--- Step 2: Run discovery ---")
    discovery = UnitDiscovery()
    ok, result, err = discovery.Run("discover", {})
    if ok:
        print(f"  Methods scanned:    {result['methods_scanned']}")
        print(f"  Edges built:        {result['edges_built']}")
        print(f"  SCCs found:         {result['sccs_found']}")
        print(f"  Trivial SCCs:       {result['trivial_sccs']}")
        print(f"  Non-trivial SCCs:   {result['nontrivial_sccs']}")
        print(f"  Units discovered:   {result['units_discovered']}")
        print(f"  Pure units:         {result['pure_units']}")
        print(f"  Impure units:       {result['impure_units']}")
        print(f"  Max cluster size:   {result['max_cluster_size']}")
        print(f"  Discovery time:     {result['discovery_ms']:.1f}ms")
    else:
        print(f"  FAILED: {err}")
        raise SystemExit(1)

    # Step 3: Show discovered units
    print()
    print("--- Step 3: Discovered units ---")
    ok, units, _ = discovery.Run("units", {})
    if ok:
        for u in units["units"]:
            pure = "pure" if u["has_pure"] and not u["has_impure"] else "impure" if u["has_impure"] else "pure"
            print(f"  {u['unit_name']:15s}  hash={u['unit_hash'][:12]}...  "
                  f"members={u['member_count']}  {pure}")
            for m in u["members"]:
                print(f"    {m}")
            if u["entry_methods"]:
                print(f"    entries: {u['entry_methods']}")
            if u["exit_methods"]:
                print(f"    exits:   {u['exit_methods']}")
            if u["callable_from"]:
                print(f"    called by: {u['callable_from']}")

    # Step 4: SCC analysis
    print()
    print("--- Step 4: SCC analysis ---")
    ok, sccs, _ = discovery.Run("sccs", {})
    if ok:
        print(f"  Total SCCs: {sccs['count']}")
        for s in sccs["sccs"]:
            kind = "trivial" if s["is_trivial"] else "CYCLE"
            print(f"  SCC {s['scc_id']:3d}  members={s['member_count']}  {kind}")
            if not s["is_trivial"]:
                for m in s["members"]:
                    print(f"    {m}")

    # Step 5: Unit detail
    print()
    print("--- Step 5: Unit detail (largest cluster) ---")
    if units["units"]:
        largest = max(units["units"], key=lambda u: u["member_count"])
        ok, detail, _ = discovery.Run("unit_detail", {"unit_name": largest["unit_name"]})
        if ok:
            print(f"  Unit:          {detail['unit_name']}")
            print(f"  Hash:          {detail['unit_hash']}")
            print(f"  Members:       {detail['member_count']}")
            for m in detail["members"]:
                pure = "pure" if m["is_pure"] else "impure"
                print(f"    {m['method']:40s}  class={m['class']:20s}  {pure}")
            print(f"  Entry methods: {detail['entry_methods']}")
            print(f"  Exit methods:  {detail['exit_methods']}")
            print(f"  Shared state:  {detail['shared_state']}")
            print(f"  Side effects:  {detail['side_effects']}")
            print(f"  Cohesion:      {detail['cohesion']}")
            print(f"  Coupling:      {detail['coupling']}")
            print(f"  Pure members:  {detail['pure_members']}")
            print(f"  Impure members:{detail['impure_members']}")

    # Step 6: Call graph
    print()
    print("--- Step 6: Call graph ---")
    ok, graph, _ = discovery.Run("graph", {})
    if ok:
        print(f"  Nodes: {graph['nodes']}")
        print(f"  Edges: {graph['edges']}")
        for e in graph["edge_list"]:
            print(f"    {e['caller']:40s} → {e['callee']}")

    # Step 7: Stats
    print()
    print("--- Step 7: Stats ---")
    ok, stats, _ = discovery.Run("stats", {})
    if ok:
        for k, v in stats["counts"].items():
            print(f"  {k:25s} {v}")
        print()
        for k, v in stats["stats"].items():
            print(f"  {k:25s} {v}")
        print()
        for k, v in stats["stored"].items():
            print(f"  {k:25s} {v}")

    print()
    print("=== UNIT DISCOVERY DEMO COMPLETE ===")
