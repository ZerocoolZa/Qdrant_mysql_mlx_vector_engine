#!/usr/bin/env python3
# [@GHOST]{file_path="Cascade_toolStack/strips_planner.py"
# date="2026-06-29" author="Devin" session_id="strips-planner-rewrite"
# context="STRIPS-style goal planner over bcl_ir database — rewritten to derive preconditions/effects from bcl_edges STATE_READ/STATE_WRITE instead of hardcoded maps"}
# [@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE Tuple3 Run dispatch no-hardcode"}
# [@FILEID]{id="strips_planner.py" domain="planning" authority="StripsPlanner"}
# [@SUMMARY]{summary="Goal-conditioned STRIPS planner: derives action contracts from bcl_edges (STATE_READ=preconditions, STATE_WRITE=effects), does backward goal regression and forward A* search over the real state-space graph"}
# [@CLASS]{class="StripsPlanner" domain="planning" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="load_actions" type="command"}
# [@METHOD]{method="load_contracts" type="command"}
# [@METHOD]{method="backward_plan" type="command"}
# [@METHOD]{method="forward_search" type="command"}
# [@METHOD]{method="match_actions_to_goal" type="command"}
# [@METHOD]{method="expand_preconditions" type="command"}
# [@METHOD]{method="topological_sort" type="command"}
# [@METHOD]{method="query_methods" type="command"}
# [@METHOD]{method="query_edges" type="command"}
# [@METHOD]{method="query_state_keys" type="command"}
# [@METHOD]{method="get_stats" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

"""
StripsPlanner -- Goal-conditioned STRIPS planner over bcl_ir database.

REWRITTEN: Derives action contracts (preconditions + effects) directly from
bcl_edges instead of using hardcoded PRECONDITION_MAP/EFFECT_MAP dicts.

Data model:
    bcl_edges.edge_type = 'STATE_READ'  ->  preconditions (what state a method reads)
    bcl_edges.edge_type = 'STATE_WRITE' ->  effects       (what state a method writes)
    bcl_edges.edge_type = 'CALL'        ->  call dependencies (method-to-method)
    bcl_edges.target                   ->  state key (e.g. self.state[db_conn])

Planning:
    Backward: goal state keys -> find methods that WRITE them -> regress their READs as sub-goals
    Forward:  start state -> apply methods whose READs are satisfied -> add their WRITEs -> reach goal

Usage:
    planner = StripsPlanner(param={"db_host": "localhost", "db_user": "root"})
    planner.Run("load_actions", {})
    rc, data, err = planner.Run("backward_plan", {"goal": "self.state[db_conn]"})
"""

import hashlib
import json
import os
import re
import sqlite3
import heapq
from collections import deque

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = ""
DB_PORT = 3306
DB_NAME = "bcl_ir"

EDGE_STATE_READ = "STATE_READ"
EDGE_STATE_WRITE = "STATE_WRITE"
EDGE_CALL = "CALL"
EDGE_RESOURCE = "RESOURCE"
EDGE_IMPORT = "IMPORT"

CERTAINTY_CERTAIN = "CERTAIN"
CERTAINTY_PROBABLE = "PROBABLE"
CERTAINTY_UNKNOWN = "UNKNOWN"

CERTAINTY_RANK = {
    CERTAINTY_CERTAIN: 3,
    CERTAINTY_PROBABLE: 2,
    CERTAINTY_UNKNOWN: 1,
}

DEFAULT_LIMIT = 5000
DEFAULT_MAX_DEPTH = 12
DEFAULT_MAX_NODES = 5000


class StripsPlanner:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "memunit": mem,
            "db_manager": db,
            "methods": [],
            "edges": [],
            "units": [],
            "unit_deps": [],
            "contracts": {},
            "write_index": {},
            "read_index": {},
            "call_index": {},
            "method_lookup": {},
            "db_conn": None,
            "db_host": DB_HOST,
            "db_user": DB_USER,
            "db_pass": DB_PASS,
            "db_port": DB_PORT,
            "db_name": DB_NAME,
            "loaded": False,
            "contracts_loaded": False,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
                if key in ("db_host", "db_user", "db_pass", "db_port", "db_name"):
                    self.state[key] = value

    def Run(self, command, params=None):
        if command == "load_actions":
            return self.load_actions(params)
        if command == "load_contracts":
            return self.load_contracts(params)
        if command == "backward_plan":
            return self.backward_plan(params)
        if command == "forward_search":
            return self.forward_search(params)
        if command == "match_actions_to_goal":
            return self.match_actions_to_goal(params)
        if command == "expand_preconditions":
            return self.expand_preconditions(params)
        if command == "query_methods":
            return self.query_methods(params)
        if command == "query_edges":
            return self.query_edges(params)
        if command == "query_state_keys":
            return self.query_state_keys(params)
        if command == "stats":
            return self.get_stats(params)
        if command == "read_state":
            return self.read_state(params)
        if command == "set_config":
            return self.set_config(params)
        return (0, None, (1, "unknown command", 0))

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
            if key in ("db_host", "db_user", "db_pass", "db_port", "db_name"):
                self.state[key] = value
        return (1, dict(self.state["config"]), None)

    def _connect(self):
        if self.state.get("db_conn"):
            try:
                conn = self.state["db_conn"]
                conn.ping(reconnect=True)
                return conn
            except Exception:
                pass
        if not MYSQL_AVAILABLE:
            return None
        try:
            conn = mysql.connector.connect(
                host=self.state["db_host"],
                user=self.state["db_user"],
                password=self.state["db_pass"],
                port=self.state["db_port"],
                database=self.state["db_name"],
            )
            self.state["db_conn"] = conn
            return conn
        except Exception:
            return None

    def load_actions(self, params):
        limit = self._p(params, "limit", DEFAULT_LIMIT)
        conn = self._connect()
        if conn is None:
            return (0, None, ("DB_CONNECT_FAILED", "Cannot connect to bcl_ir database", 0))

        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT id, codebase_id, bcl_class_id, method_id, method_id_hash,
                   method_name, class_name, file_path, method_type,
                   is_async, is_deterministic_subset, line_start, line_end,
                   ast_hash, inputs, outputs,
                   certain_count, probable_count, unknown_count,
                   has_branching, has_loops, has_recursion,
                   throws_exceptions, handles_exceptions,
                   mutates_global_state, mutates_external
            FROM bcl_methods
            WHERE method_type IS NOT NULL
            ORDER BY id
            LIMIT %s
        """, (limit,))
        methods = []
        for row in cur.fetchall():
            inputs_parsed = []
            outputs_parsed = []
            try:
                if row.get("inputs"):
                    inputs_parsed = json.loads(row["inputs"])
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                if row.get("outputs"):
                    outputs_parsed = json.loads(row["outputs"])
            except (json.JSONDecodeError, TypeError):
                pass
            methods.append({
                "id": row["id"],
                "method_id": row.get("method_id", ""),
                "method_name": row["method_name"],
                "class_name": row.get("class_name") or "",
                "file_path": row.get("file_path") or "",
                "method_type": row.get("method_type") or "",
                "inputs": inputs_parsed,
                "outputs": outputs_parsed,
                "has_branching": bool(row.get("has_branching", 0)),
                "has_loops": bool(row.get("has_loops", 0)),
                "has_recursion": bool(row.get("has_recursion", 0)),
                "ast_hash": row.get("ast_hash", ""),
                "certain_count": row.get("certain_count", 0),
                "probable_count": row.get("probable_count", 0),
                "unknown_count": row.get("unknown_count", 0),
                "mutates_external": bool(row.get("mutates_external", 0)),
            })

        cur.execute("""
            SELECT e.id, e.codebase_id, e.bcl_method_id, e.source_method_id,
                   e.target, e.edge_type, e.certainty, e.resolution, e.resource_type, e.line_number
            FROM bcl_edges e
            JOIN bcl_methods m ON e.source_method_id = m.method_id
            WHERE e.edge_type IN ('STATE_READ', 'STATE_WRITE')
            AND m.method_type IS NOT NULL
            ORDER BY m.id
            LIMIT %s
        """, (limit * 50,))
        edges = []
        for row in cur.fetchall():
            edges.append({
                "id": row["id"],
                "bcl_method_id": row.get("bcl_method_id"),
                "source": row.get("source_method_id") or "",
                "target": row.get("target") or "",
                "edge_type": row.get("edge_type") or "",
                "certainty": row.get("certainty") or "",
                "resolution": row.get("resolution") or "",
                "resource_type": row.get("resource_type") or "",
                "line_number": row.get("line_number"),
            })

        cur.execute("""
            SELECT unit_id, method_count, class_names, is_closed,
                   internal_calls, external_call_count, resources, state_keys
            FROM bcl_units
            LIMIT %s
        """, (limit,))
        units = []
        for row in cur.fetchall():
            units.append({
                "unit_id": row["unit_id"],
                "method_count": row["method_count"],
                "class_names": row["class_names"].split(",") if row.get("class_names") else [],
                "is_closed": bool(row["is_closed"]),
                "internal_calls": row["internal_calls"],
                "external_calls": row["external_call_count"],
                "resources": row.get("resources") or "",
                "state_keys": row.get("state_keys") or "",
            })

        cur.execute("SELECT source_unit_id, target_unit_id FROM bcl_unit_deps LIMIT %s", (limit * 5,))
        unit_deps = []
        for row in cur.fetchall():
            unit_deps.append({
                "source": row["source_unit_id"],
                "target": row["target_unit_id"],
            })

        cur.close()

        self.state["methods"] = methods
        self.state["edges"] = edges
        self.state["units"] = units
        self.state["unit_deps"] = unit_deps
        self.state["loaded"] = True

        method_lookup = {}
        for m in methods:
            mid = m["method_id"]
            if mid:
                method_lookup[mid] = m
        self.state["method_lookup"] = method_lookup

        rc, data, err = self.load_contracts(params)
        if rc == 0:
            return (0, None, err)

        return (1, {
            "methods_loaded": len(methods),
            "edges_loaded": len(edges),
            "units_loaded": len(units),
            "unit_deps_loaded": len(unit_deps),
            "contracts_built": len(self.state.get("contracts", {})),
            "write_index_size": len(self.state.get("write_index", {})),
            "read_index_size": len(self.state.get("read_index", {})),
        }, None)

    def load_contracts(self, params):
        if not self.state.get("loaded"):
            rc, data, err = self.load_actions(params)
            if rc == 0:
                return (0, None, err)

        contracts = {}
        write_index = {}
        read_index = {}
        call_index = {}

        for m in self.state["methods"]:
            mid = m["method_id"]
            if not mid:
                continue
            contracts[mid] = {
                "method_id": mid,
                "method_name": m["method_name"],
                "class_name": m["class_name"],
                "method_type": m["method_type"],
                "preconditions": [],
                "effects": [],
                "calls": [],
                "resources": [],
                "certainty_preconds": {},
                "certainty_effects": {},
            }

        for e in self.state["edges"]:
            src = e["source"]
            if not src:
                continue
            etype = e["edge_type"]
            target = e["target"]
            certainty = e["certainty"]

            if src not in contracts:
                continue

            if etype == EDGE_STATE_READ:
                if target not in contracts[src]["preconditions"]:
                    contracts[src]["preconditions"].append(target)
                contracts[src]["certainty_preconds"][target] = certainty
                if target not in read_index:
                    read_index[target] = []
                if src not in read_index[target]:
                    read_index[target].append(src)

            elif etype == EDGE_STATE_WRITE:
                if target not in contracts[src]["effects"]:
                    contracts[src]["effects"].append(target)
                contracts[src]["certainty_effects"][target] = certainty
                if target not in write_index:
                    write_index[target] = []
                if src not in write_index[target]:
                    write_index[target].append(src)

            elif etype == EDGE_CALL:
                contracts[src]["calls"].append(target)
                if src not in call_index:
                    call_index[src] = []
                call_index[src].append(target)

            elif etype == EDGE_RESOURCE:
                contracts[src]["resources"].append(target)

        self.state["contracts"] = contracts
        self.state["write_index"] = write_index
        self.state["read_index"] = read_index
        self.state["call_index"] = call_index
        self.state["contracts_loaded"] = True

        return (1, {
            "contracts_built": len(contracts),
            "write_index_size": len(write_index),
            "read_index_size": len(read_index),
            "call_index_size": len(call_index),
            "total_preconditions": sum(len(c["preconditions"]) for c in contracts.values()),
            "total_effects": sum(len(c["effects"]) for c in contracts.values()),
        }, None)

    def _parse_goal_keys(self, goal):
        goal = goal.strip()
        if not goal:
            return []

        if goal.startswith("{") or goal.startswith("["):
            try:
                parsed = json.loads(goal)
                if isinstance(parsed, list):
                    return [str(k) for k in parsed]
                if isinstance(parsed, dict):
                    return list(parsed.keys())
            except (json.JSONDecodeError, TypeError):
                pass

        if "self.state[" in goal or "self." in goal:
            keys = re.findall(r'self\.\w+(?:\[[^\]]+\])?', goal)
            if keys:
                return list(set(keys))

        return [goal]

    def _match_state_keys(self, pattern):
        pattern_lower = pattern.lower()
        matches = []
        for key in self.state.get("write_index", {}):
            if pattern_lower in key.lower():
                matches.append(key)
        return matches

    def match_actions_to_goal(self, params):
        goal = self._p(params, "goal", "")
        if not goal:
            return (0, None, ("MISSING_PARAM", "goal required", 0))

        if not self.state.get("contracts_loaded"):
            rc, data, err = self.load_contracts(params)
            if rc == 0:
                return (0, None, err)

        goal_keys = self._parse_goal_keys(goal)
        if not goal_keys:
            return (0, None, ("GOAL_PARSE_FAILED", "Cannot parse goal into state keys", 0))

        expanded_keys = []
        for gk in goal_keys:
            if gk in self.state.get("write_index", {}):
                expanded_keys.append(gk)
            else:
                matched = self._match_state_keys(gk)
                if matched:
                    expanded_keys.extend(matched)
                else:
                    expanded_keys.append(gk)

        expanded_keys = list(set(expanded_keys))

        matched_actions = []
        for key in expanded_keys:
            writers = self.state.get("write_index", {}).get(key, [])
            for writer_id in writers:
                contract = self.state["contracts"].get(writer_id)
                if not contract:
                    continue
                matched_actions.append({
                    "method_id": writer_id,
                    "method_name": contract["method_name"],
                    "class_name": contract["class_name"],
                    "method_type": contract["method_type"],
                    "writes_key": key,
                    "preconditions": list(contract["preconditions"]),
                    "effects": list(contract["effects"]),
                    "calls": len(contract["calls"]),
                    "from_db": True,
                })

        seen = set()
        unique_actions = []
        for a in matched_actions:
            sig = (a["method_id"], a["writes_key"])
            if sig not in seen:
                seen.add(sig)
                unique_actions.append(a)

        unique_actions.sort(key=lambda x: (
            -CERTAINTY_RANK.get(
                self.state["contracts"].get(x["method_id"], {}).get("certainty_effects", {}).get(x["writes_key"], ""),
                0
            ),
            len(x["preconditions"]),
            x["method_name"],
        ))

        return (1, {
            "goal": goal,
            "goal_keys": goal_keys,
            "expanded_keys": expanded_keys,
            "matched_actions": unique_actions,
            "total_matches": len(unique_actions),
            "write_index_searched": len(self.state.get("write_index", {})),
        }, None)

    def expand_preconditions(self, params):
        action = self._p(params, "action", "")
        if not action:
            return (0, None, ("MISSING_PARAM", "action required", 0))

        if not self.state.get("contracts_loaded"):
            rc, data, err = self.load_contracts(params)
            if rc == 0:
                return (0, None, err)

        contract = self.state["contracts"].get(action)
        if not contract:
            lookup = None
            for mid, c in self.state["contracts"].items():
                if c["method_name"].lower() == action.lower() or mid.endswith("::" + action):
                    lookup = mid
                    break
            if not lookup:
                return (0, None, ("ACTION_NOT_FOUND", "No contract for action: " + action, 0))
            contract = self.state["contracts"][lookup]
            action = lookup

        tree = self._build_dep_tree(action, set())
        ordered = self._topo_sort(tree)

        return (1, {
            "action": action,
            "method_name": contract["method_name"],
            "class_name": contract["class_name"],
            "dependency_tree": tree,
            "execution_order": ordered,
            "pipeline_str": " -> ".join(ordered) if ordered else contract["method_name"],
            "steps": len(ordered),
        }, None)

    def _build_dep_tree(self, method_id, seen):
        if method_id in seen:
            return {"action": method_id, "preconditions": [], "cycle": True}
        seen.add(method_id)

        contract = self.state["contracts"].get(method_id)
        if not contract:
            return {"action": method_id, "preconditions": [], "effects": [], "not_found": True}

        node = {
            "action": method_id,
            "method_name": contract["method_name"],
            "class_name": contract["class_name"],
            "preconditions": [],
            "effects": list(contract["effects"]),
        }

        for prereq_key in contract["preconditions"]:
            writers = self.state.get("write_index", {}).get(prereq_key, [])
            if not writers:
                node["preconditions"].append({
                    "state_key": prereq_key,
                    "satisfied_by": None,
                    "message": "No method writes this key — must be in start state",
                })
                continue
            for writer_id in writers:
                child = self._build_dep_tree(writer_id, seen.copy())
                child["state_key"] = prereq_key
                node["preconditions"].append(child)

        return node

    def _topo_sort(self, tree):
        order = []
        visited = set()

        def visit(node):
            for prereq in node.get("preconditions", []):
                if isinstance(prereq, dict) and "action" in prereq:
                    visit(prereq)
            action = node.get("action", "")
            if action and action not in visited:
                visited.add(action)
                contract = self.state["contracts"].get(action)
                if contract:
                    order.append(contract["method_name"])
                else:
                    order.append(action)

        visit(tree)
        return order

    def backward_plan(self, params):
        goal = self._p(params, "goal", "")
        start_state = self._p(params, "start_state", [])
        max_depth = self._p(params, "max_depth", DEFAULT_MAX_DEPTH)
        if not goal:
            return (0, None, ("MISSING_PARAM", "goal required", 0))

        if not self.state.get("contracts_loaded"):
            rc, data, err = self.load_contracts(params)
            if rc == 0:
                return (0, None, err)

        goal_keys = self._parse_goal_keys(goal)
        if not goal_keys:
            return (0, None, ("GOAL_PARSE_FAILED", "Cannot parse goal", 0))

        expanded_keys = []
        for gk in goal_keys:
            if gk in self.state.get("write_index", {}):
                expanded_keys.append(gk)
            else:
                matched = self._match_state_keys(gk)
                if matched:
                    expanded_keys.extend(matched)
                else:
                    expanded_keys.append(gk)
        expanded_keys = list(set(expanded_keys))

        start_set = set(start_state)

        plan_actions = []
        plan_set = set()
        frontier = list(expanded_keys)
        unresolved = []
        visited_keys = set()
        depth_map = {}

        while frontier:
            current_key = frontier.pop(0)
            if current_key in start_set:
                continue
            if current_key in visited_keys:
                continue
            visited_keys.add(current_key)

            writers = self.state.get("write_index", {}).get(current_key, [])
            if not writers:
                unresolved.append(current_key)
                continue

            best_writer = None
            best_score = -1
            for writer_id in writers:
                contract = self.state["contracts"].get(writer_id)
                if not contract:
                    continue
                certainty = contract["certainty_effects"].get(current_key, "")
                rank = CERTAINTY_RANK.get(certainty, 0)
                unmet = sum(1 for p in contract["preconditions"] if p not in start_set and p not in visited_keys)
                score = rank * 100 - unmet
                if score > best_score:
                    best_score = score
                    best_writer = writer_id

            if not best_writer:
                unresolved.append(current_key)
                continue

            if best_writer not in plan_set:
                plan_set.add(best_writer)
                plan_actions.append(best_writer)
                contract = self.state["contracts"][best_writer]
                for prereq in contract["preconditions"]:
                    if prereq not in start_set and prereq not in visited_keys:
                        frontier.append(prereq)

        ordered = []
        visited_methods = set()
        for method_id in plan_actions:
            tree = self._build_dep_tree(method_id, set())
            sub_order = self._topo_sort(tree)
            for name in sub_order:
                if name not in visited_methods:
                    visited_methods.add(name)
                    ordered.append(name)

        plan_details = []
        for method_id in plan_actions:
            contract = self.state["contracts"].get(method_id)
            if contract:
                plan_details.append({
                    "method_id": method_id,
                    "method_name": contract["method_name"],
                    "class_name": contract["class_name"],
                    "method_type": contract["method_type"],
                    "preconditions": list(contract["preconditions"]),
                    "effects": list(contract["effects"]),
                    "writes": [k for k in expanded_keys if method_id in self.state.get("write_index", {}).get(k, [])],
                })

        return (1, {
            "goal": goal,
            "goal_keys": goal_keys,
            "expanded_keys": expanded_keys,
            "start_state": list(start_set),
            "plan_methods": ordered,
            "plan_details": plan_details,
            "pipeline_str": " -> ".join(ordered) if ordered else "already_satisfied",
            "pipeline_steps": len(ordered),
            "unresolved_keys": unresolved,
            "methods_searched": len(self.state.get("contracts", {})),
            "write_index_size": len(self.state.get("write_index", {})),
        }, None)

    def forward_search(self, params):
        goal = self._p(params, "goal", "")
        start_state = self._p(params, "start_state", [])
        max_depth = self._p(params, "max_depth", DEFAULT_MAX_DEPTH)
        max_nodes = self._p(params, "max_nodes", DEFAULT_MAX_NODES)
        if not goal:
            return (0, None, ("MISSING_PARAM", "goal required", 0))

        if not self.state.get("contracts_loaded"):
            rc, data, err = self.load_contracts(params)
            if rc == 0:
                return (0, None, err)

        goal_keys = self._parse_goal_keys(goal)
        if not goal_keys:
            return (0, None, ("GOAL_PARSE_FAILED", "Cannot parse goal", 0))

        expanded_keys = []
        for gk in goal_keys:
            if gk in self.state.get("write_index", {}):
                expanded_keys.append(gk)
            else:
                matched = self._match_state_keys(gk)
                if matched:
                    expanded_keys.extend(matched)
                else:
                    expanded_keys.append(gk)
        goal_set = set(expanded_keys)

        start_set = set(start_state)
        if goal_set <= start_set:
            return (1, {
                "goal": goal,
                "pipeline": [],
                "pipeline_str": "already_satisfied",
                "pipeline_steps": 0,
                "score": 1.0,
                "states_explored": 0,
            }, None)

        applicable = []
        for method_id, contract in self.state["contracts"].items():
            if not contract["effects"]:
                continue
            if not contract["preconditions"]:
                applicable.append(method_id)
            elif set(contract["preconditions"]) <= start_set:
                applicable.append(method_id)

        if not applicable:
            return (1, {
                "goal": goal,
                "pipeline": [],
                "pipeline_str": "no_path_found",
                "pipeline_steps": 0,
                "best_score": 0.0,
                "states_explored": 0,
                "message": "No applicable actions from start state",
            }, None)

        def state_score(state_set):
            if not goal_set:
                return 0.0
            satisfied = len(goal_set & state_set)
            return satisfied / len(goal_set)

        def state_key(state_set):
            return "|".join(sorted(state_set))

        visited = {}
        counter = 0
        start_score = state_score(start_set)
        start_entry = (-start_score, counter, frozenset(start_set), [])
        heap = [start_entry]
        visited[state_key(start_set)] = start_score
        best_path = None
        best_score = start_score

        while heap and len(visited) < max_nodes:
            neg_score, _, current_state, path = heapq.heappop(heap)
            current_score = -neg_score

            if current_score >= 1.0:
                return (1, {
                    "goal": goal,
                    "pipeline": path,
                    "pipeline_str": " -> ".join(path) if path else "already_satisfied",
                    "pipeline_steps": len(path),
                    "score": 1.0,
                    "states_explored": len(visited),
                }, None)

            if current_score > best_score:
                best_score = current_score
                best_path = list(path)

            if len(path) >= max_depth:
                continue

            for method_id, contract in self.state["contracts"].items():
                if not contract["effects"]:
                    continue
                preconds = set(contract["preconditions"])
                if not preconds <= current_state:
                    continue
                effects = set(contract["effects"])
                new_state = current_state | effects
                new_key = state_key(new_state)
                new_score = state_score(new_state)
                if new_key in visited:
                    if new_score <= visited[new_key]:
                        continue
                visited[new_key] = new_score
                counter += 1
                name = contract["method_name"]
                new_path = path + [name]
                heapq.heappush(heap, (-new_score, counter, new_state, new_path))

        return (1, {
            "goal": goal,
            "pipeline": best_path or [],
            "pipeline_str": " -> ".join(best_path) if best_path else "no_path_found",
            "pipeline_steps": len(best_path) if best_path else 0,
            "best_score": round(best_score, 4),
            "states_explored": len(visited),
            "goal_keys": list(goal_set),
            "start_state": list(start_set),
        }, None)

    def query_methods(self, params):
        keyword = self._p(params, "keyword", "")
        limit = self._p(params, "limit", 20)
        if not keyword:
            return (0, None, ("MISSING_PARAM", "keyword required", 0))

        if not self.state.get("loaded"):
            rc, data, err = self.load_actions(params)
            if rc == 0:
                return (0, None, err)

        results = []
        kw_lower = keyword.lower()
        for m in self.state.get("methods", []):
            if kw_lower in m["method_name"].lower() or kw_lower in (m["class_name"] or "").lower():
                contract = self.state.get("contracts", {}).get(m["method_id"], {})
                results.append({
                    "id": m["id"],
                    "method_id": m["method_id"],
                    "method_name": m["method_name"],
                    "class_name": m["class_name"],
                    "method_type": m["method_type"],
                    "inputs": m["inputs"],
                    "outputs": m["outputs"],
                    "preconditions": contract.get("preconditions", []) if contract else [],
                    "effects": contract.get("effects", []) if contract else [],
                })
                if len(results) >= limit:
                    break

        return (1, {
            "keyword": keyword,
            "matches": results,
            "count": len(results),
        }, None)

    def query_edges(self, params):
        method_name = self._p(params, "method_name", "")
        edge_type = self._p(params, "edge_type", "")
        limit = self._p(params, "limit", 50)
        if not method_name and not edge_type:
            return (0, None, ("MISSING_PARAM", "method_name or edge_type required", 0))

        if not self.state.get("loaded"):
            rc, data, err = self.load_actions(params)
            if rc == 0:
                return (0, None, err)

        results = []
        for e in self.state.get("edges", []):
            if method_name and method_name not in e["source"] and method_name not in e["target"]:
                continue
            if edge_type and e["edge_type"] != edge_type:
                continue
            results.append(e)
            if len(results) >= limit:
                break

        return (1, {
            "method_name": method_name,
            "edge_type": edge_type,
            "edges": results,
            "count": len(results),
        }, None)

    def query_state_keys(self, params):
        pattern = self._p(params, "pattern", "")
        edge_type = self._p(params, "edge_type", "")
        limit = self._p(params, "limit", 50)

        if not self.state.get("contracts_loaded"):
            rc, data, err = self.load_contracts(params)
            if rc == 0:
                return (0, None, err)

        if edge_type == EDGE_STATE_WRITE or not edge_type:
            source = self.state.get("write_index", {})
        elif edge_type == EDGE_STATE_READ:
            source = self.state.get("read_index", {})
        else:
            source = {}

        results = []
        pat_lower = pattern.lower() if pattern else ""
        for key, method_ids in source.items():
            if pat_lower and pat_lower not in key.lower():
                continue
            methods = []
            for mid in method_ids:
                contract = self.state["contracts"].get(mid)
                if contract:
                    methods.append({
                        "method_id": mid,
                        "method_name": contract["method_name"],
                        "class_name": contract["class_name"],
                    })
            results.append({"state_key": key, "method_count": len(method_ids), "methods": methods})
            if len(results) >= limit:
                break

        results.sort(key=lambda x: -x["method_count"])

        return (1, {
            "pattern": pattern,
            "edge_type": edge_type or "STATE_WRITE",
            "state_keys": results,
            "count": len(results),
            "total_keys_in_index": len(source),
        }, None)

    def get_stats(self, params):
        conn = self._connect()
        if conn is None:
            return (0, None, ("DB_CONNECT_FAILED", "Cannot connect", 0))

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bcl_methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_units")
        units = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_unit_deps")
        deps = cur.fetchone()[0]
        cur.execute("SELECT method_type, COUNT(*) FROM bcl_methods WHERE method_type IS NOT NULL GROUP BY method_type ORDER BY COUNT(*) DESC LIMIT 10")
        by_type = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT edge_type, certainty, COUNT(*) FROM bcl_edges GROUP BY edge_type, certainty ORDER BY COUNT(*) DESC")
        by_edge = [{"edge_type": r[0], "certainty": r[1], "count": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(DISTINCT target) FROM bcl_edges WHERE edge_type='STATE_WRITE'")
        unique_writes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT target) FROM bcl_edges WHERE edge_type='STATE_READ'")
        unique_reads = cur.fetchone()[0]
        cur.close()

        return (1, {
            "database": self.state["db_name"],
            "classes": classes,
            "methods": methods,
            "edges": edges,
            "units": units,
            "unit_deps": deps,
            "methods_by_type": by_type,
            "edges_by_type_certainty": by_edge,
            "unique_state_write_keys": unique_writes,
            "unique_state_read_keys": unique_reads,
            "contracts_loaded": len(self.state.get("contracts", {})),
            "write_index_size": len(self.state.get("write_index", {})),
            "read_index_size": len(self.state.get("read_index", {})),
            "loaded": self.state.get("loaded", False),
        }, None)


if __name__ == "__main__":
    import sys

    planner = StripsPlanner()

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: strips_planner.py <command> [args]\n")
        sys.stderr.write("Commands:\n")
        sys.stderr.write("  stats                                    -- DB overview + edge type breakdown\n")
        sys.stderr.write("  load-actions [--limit 5000]              -- Load methods + edges + contracts from bcl_ir\n")
        sys.stderr.write("  backward-plan --goal 'self.state[db]'    -- Backward goal regression (STRIPS)\n")
        sys.stderr.write("          [--start-state 'self.state[config]']\n")
        sys.stderr.write("          [--max-depth 12]\n")
        sys.stderr.write("  forward-search --goal 'self.state[db]'   -- Forward A* over state-space\n")
        sys.stderr.write("          [--start-state 'self.state[config]']\n")
        sys.stderr.write("          [--max-depth 12] [--max-nodes 5000]\n")
        sys.stderr.write("  match --goal 'self.state[db_conn]'       -- Match goal keys to methods that write them\n")
        sys.stderr.write("  expand --action Connect                  -- Expand precondition tree for a method\n")
        sys.stderr.write("  query-methods --keyword Connect          -- Search methods by keyword\n")
        sys.stderr.write("  query-edges --method-name Run            -- Search edges by method\n")
        sys.stderr.write("  query-state-keys [--pattern db]          -- List state keys in write/read index\n")
        sys.stderr.write("          [--edge-type STATE_WRITE]\n")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]
    goal = ""
    action = ""
    keyword = ""
    method_name = ""
    edge_type = ""
    pattern = ""
    start_state_raw = ""
    limit = DEFAULT_LIMIT
    max_depth = DEFAULT_MAX_DEPTH
    max_nodes = DEFAULT_MAX_NODES

    i = 0
    while i < len(args):
        if args[i] == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            i += 2
        elif args[i] == "--action" and i + 1 < len(args):
            action = args[i + 1]
            i += 2
        elif args[i] == "--keyword" and i + 1 < len(args):
            keyword = args[i + 1]
            i += 2
        elif args[i] == "--method-name" and i + 1 < len(args):
            method_name = args[i + 1]
            i += 2
        elif args[i] == "--edge-type" and i + 1 < len(args):
            edge_type = args[i + 1]
            i += 2
        elif args[i] == "--pattern" and i + 1 < len(args):
            pattern = args[i + 1]
            i += 2
        elif args[i] == "--start-state" and i + 1 < len(args):
            start_state_raw = args[i + 1]
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--max-depth" and i + 1 < len(args):
            max_depth = int(args[i + 1])
            i += 2
        elif args[i] == "--max-nodes" and i + 1 < len(args):
            max_nodes = int(args[i + 1])
            i += 2
        else:
            i += 1

    start_state = []
    if start_state_raw:
        if start_state_raw.startswith("["):
            try:
                start_state = json.loads(start_state_raw)
            except (json.JSONDecodeError, TypeError):
                start_state = [start_state_raw]
        else:
            start_state = [s.strip() for s in start_state_raw.split(",") if s.strip()]

    rc = 0
    data = None
    err = None

    if cmd == "stats":
        rc, data, err = planner.get_stats({})
    elif cmd == "load-actions":
        rc, data, err = planner.load_actions({"limit": limit})
    elif cmd == "load-contracts":
        rc, data, err = planner.load_contracts({"limit": limit})
    elif cmd == "backward-plan":
        rc, data, err = planner.backward_plan({
            "goal": goal,
            "start_state": start_state,
            "max_depth": max_depth,
            "limit": limit,
        })
    elif cmd == "forward-search":
        rc, data, err = planner.forward_search({
            "goal": goal,
            "start_state": start_state,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "limit": limit,
        })
    elif cmd == "match":
        rc, data, err = planner.match_actions_to_goal({"goal": goal, "limit": limit})
    elif cmd == "expand":
        rc, data, err = planner.expand_preconditions({"action": action, "limit": limit})
    elif cmd == "query-methods":
        rc, data, err = planner.query_methods({"keyword": keyword, "limit": limit})
    elif cmd == "query-edges":
        rc, data, err = planner.query_edges({"method_name": method_name, "edge_type": edge_type, "limit": limit})
    elif cmd == "query-state-keys":
        rc, data, err = planner.query_state_keys({"pattern": pattern, "edge_type": edge_type, "limit": limit})
    else:
        sys.stderr.write("Unknown command: " + cmd + "\n")
        sys.exit(1)

    if rc == 1:
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
    else:
        sys.stderr.write("Error: " + str(err) + "\n")
        sys.exit(1)
