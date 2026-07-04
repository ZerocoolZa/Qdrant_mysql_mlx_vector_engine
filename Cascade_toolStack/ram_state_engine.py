#!/usr/bin/env python3

#[@GHOST]{[@file<ram_state_engine.py>][@domain<Cascade_toolStack>][@role<state_search>][@auth<cascade>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<state_search>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}

"""
RAM-Based State-Space Exploration Engine.

Bounded combinatorial graph expansion with scoring, pruning, and transition memory.
Explores reachable states from primitives, records successful paths, prunes bad branches.

This is the symbolic learning layer — not neural, not AI model.
It's a search engine over transformation rules with experience memory.

Usage:
  python3 ram_state_engine.py explore --max-depth 3 --max-nodes 5000
  python3 ram_state_engine.py explore --goal "clean_naming"
  python3 ram_state_engine.py stats
  python3 ram_state_engine.py best-paths
  python3 ram_state_engine.py export
"""

import os
import re
import sys
import json
import hashlib
import copy
import sqlite3
import heapq
from collections import deque
from typing import List, Dict, Any, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pipeline_graph.db")
MEMORY_DB_PATH = os.path.join(BASE_DIR, "state_memory.db")


@dataclass
class State:
    value: Dict[str, Any]

    def hash(self) -> str:
        h = hashlib.sha256()
        h.update(str(sorted(self.value.items())).encode())
        return h.hexdigest()[:16]

    def clone(self) -> "State":
        return State(copy.deepcopy(self.value))


@dataclass
class ActionDef:
    name: str
    fn: Callable[[State], State]
    cost: float = 1.0


@dataclass
class TransitionRecord:
    parent_hash: str
    action: str
    child_hash: str
    depth: int
    score: float = 0.0
    pruned: bool = False


@dataclass(order=True)
class FrontierItem:
    priority: float
    state: Any = field(compare=False)
    depth: int = field(compare=False)
    path: Any = field(compare=False)
    hash_val: str = field(compare=False)


class RamStateEngine:
    """Bounded state-space exploration with scoring and pruning."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "max_depth": self.param.get("max_depth", 4),
            "max_nodes": self.param.get("max_nodes", 5000),
            "prune_threshold": self.param.get("prune_threshold", 0.3),
            "memory_db": self.param.get("memory_db", MEMORY_DB_PATH),
            "pipeline_db": self.param.get("pipeline_db", DB_PATH),
            "actions": [],
            "goal_fn": None,
            "score_fn": None,
            "visited": {},
            "transitions": [],
            "best_paths": [],
            "stats": {
                "expanded": 0,
                "pruned": 0,
                "goals_reached": 0,
                "duplicates": 0,
            },
        }
        self._init_actions()
        self._init_memory_db()

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def _init_memory_db(self):
        conn = sqlite3.connect(self.state["memory_db"])
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_hash TEXT NOT NULL,
                action TEXT NOT NULL,
                child_hash TEXT NOT NULL,
                depth INTEGER NOT NULL,
                score REAL DEFAULT 0,
                pruned INTEGER DEFAULT 0,
                goal_reached INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS best_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                path TEXT NOT NULL,
                score REAL NOT NULL,
                depth INTEGER NOT NULL,
                hit_count INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS state_scores (
                hash TEXT PRIMARY KEY,
                score REAL NOT NULL,
                depth INTEGER NOT NULL,
                visited_count INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

    def _init_actions(self):
        self.state["actions"] = [
            ActionDef("rename_pascal", self._act_rename_pascal, 1.0),
            ActionDef("rename_snake", self._act_rename_snake, 1.0),
            ActionDef("add_prefix", self._act_add_prefix, 0.5),
            ActionDef("remove_prefix", self._act_remove_prefix, 0.5),
            ActionDef("normalize_ext", self._act_normalize_ext, 0.3),
            ActionDef("group_by_ext", self._act_group_by_ext, 2.0),
            ActionDef("flatten", self._act_flatten, 1.5),
            ActionDef("dedup_names", self._act_dedup, 2.0),
            ActionDef("extract_functions", self._act_extract_functions, 1.0),
            ActionDef("move_to_shared", self._act_move_to_shared, 2.0),
            ActionDef("delete_duplicate", self._act_delete_duplicate, 1.5),
            ActionDef("cleanup_empty", self._act_cleanup_empty, 0.5),
        ]

    def _act_rename_pascal(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        new_files = []
        for f in files:
            name, ext = os.path.splitext(f)
            parts = re.split(r"[_\-\s\.]+", name)
            pascal = "".join(p[:1].upper() + p[1:].lower() for p in parts if p)
            new_files.append(pascal + ext)
        state.value["files"] = new_files
        state.value["naming_style"] = "pascal"
        return state

    def _act_rename_snake(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        new_files = []
        for f in files:
            name, ext = os.path.splitext(f)
            parts = re.split(r"[_\-\s\.]+", name)
            snake = "_".join(p.lower() for p in parts if p)
            new_files.append(snake + ext)
        state.value["files"] = new_files
        state.value["naming_style"] = "snake"
        return state

    def _act_add_prefix(self, state):
        state = state.clone()
        prefix = state.value.get("target_prefix", "Plf_")
        files = state.value.get("files", [])
        state.value["files"] = [
            f if f.startswith(prefix) else prefix + f for f in files
        ]
        state.value["has_prefix"] = True
        return state

    def _act_remove_prefix(self, state):
        state = state.clone()
        prefix = state.value.get("target_prefix", "Plf_")
        files = state.value.get("files", [])
        state.value["files"] = [
            f[len(prefix):] if f.startswith(prefix) else f for f in files
        ]
        state.value["has_prefix"] = False
        return state

    def _act_normalize_ext(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        ext_map = {".markdown": ".md", ".text": ".txt", ".py3": ".py"}
        new_files = []
        for f in files:
            for old, new in ext_map.items():
                if f.endswith(old):
                    f = f[: -len(old)] + new
                    break
            new_files.append(f)
        state.value["files"] = new_files
        state.value["ext_normalized"] = True
        return state

    def _act_group_by_ext(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        groups = {}
        for f in files:
            ext = os.path.splitext(f)[1]
            groups.setdefault(ext, []).append(f)
        state.value["grouped"] = True
        state.value["groups"] = groups
        return state

    def _act_flatten(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        state.value["files"] = [os.path.basename(f) for f in files]
        state.value["flattened"] = True
        return state

    def _act_dedup(self, state):
        state = state.clone()
        files = state.value.get("files", [])
        seen = set()
        deduped = []
        for f in files:
            if f not in seen:
                seen.add(f)
                deduped.append(f)
        state.value["files"] = deduped
        state.value["deduped"] = True
        state.value["dup_count"] = len(files) - len(deduped)
        return state

    def _score_naming_consistency(self, state):
        files = state.value.get("files", [])
        if not files:
            return 0.0
        styles = set()
        for f in files:
            name, _ = os.path.splitext(f)
            if "_" in name:
                styles.add("snake")
            elif re.search(r"[a-z][A-Z]", name):
                styles.add("camel")
            elif name[:1].isupper():
                styles.add("pascal")
            else:
                styles.add("unknown")
        return 1.0 / len(styles) if styles else 0.0

    def _score_prefix_consistency(self, state):
        files = state.value.get("files", [])
        if not files:
            return 0.0
        prefix = state.value.get("target_prefix", "Plf_")
        prefixed = sum(1 for f in files if f.startswith(prefix))
        return prefixed / len(files)

    def _score_dedup(self, state):
        files = state.value.get("files", [])
        if not files:
            return 0.0
        unique = len(set(files))
        return unique / len(files)

    def _score_clean_naming(self, state):
        consistency = self._score_naming_consistency(state)
        prefix = self._score_prefix_consistency(state)
        dedup = self._score_dedup(state)
        return (consistency * 0.4) + (prefix * 0.3) + (dedup * 0.3)

    def _score_modular(self, state):
        files = state.value.get("files", [])
        if not files:
            return 0.0
        groups = state.value.get("groups", {})
        if groups:
            balance = 1.0 - (max(len(v) for v in groups.values()) / len(files))
            return balance
        return 0.0

    def _extract_func_blocks(self, content):
        pattern = r'(def\s+\w+\s*\([^)]*\)\s*(?:->\s*\w+)?\s*:\n(?:\s+.+\n?)+)'
        return re.findall(pattern, content)

    def _act_extract_functions(self, state):
        state = state.clone()
        code_files = state.value.get("code_files", {})
        if not code_files:
            code_files = {"module_a.py": "def foo():\n    return 1\n\ndef bar():\n    return 2\n", "module_b.py": "def foo():\n    return 1\n\ndef baz():\n    return 3\n"}
        func_map = {}
        for fname, content in code_files.items():
            funcs = self._extract_func_blocks(content)
            for fn_text in funcs:
                h = hashlib.sha256(fn_text.encode()).hexdigest()[:16]
                func_map.setdefault(h, {"text": fn_text, "locations": []})
                func_map[h]["locations"].append(fname)
        state.value["func_map"] = func_map
        state.value["functions_extracted"] = True
        dup_count = sum(1 for v in func_map.values() if len(v["locations"]) > 1)
        state.value["dup_func_count"] = dup_count
        return state

    def _act_move_to_shared(self, state):
        state = state.clone()
        func_map = state.value.get("func_map", {})
        if not func_map:
            return state
        shared_content = []
        moved = 0
        for h, info in func_map.items():
            if len(info["locations"]) > 1:
                shared_content.append(info["text"])
                moved += 1
        code_files = state.value.get("code_files", {})
        code_files["shared_utils.py"] = "\n\n".join(shared_content) + "\n"
        state.value["code_files"] = code_files
        state.value["shared_created"] = True
        state.value["funcs_moved"] = moved
        return state

    def _act_delete_duplicate(self, state):
        state = state.clone()
        func_map = state.value.get("func_map", {})
        code_files = state.value.get("code_files", {})
        if not func_map or not code_files:
            return state
        deleted = 0
        for h, info in func_map.items():
            if len(info["locations"]) <= 1:
                continue
            for fname in info["locations"]:
                if fname not in code_files:
                    continue
                if info["text"] in code_files[fname]:
                    code_files[fname] = code_files[fname].replace(info["text"], "")
                    deleted += 1
        state.value["code_files"] = code_files
        state.value["dups_removed"] = deleted
        state.value["dup_func_count"] = 0
        return state

    def _act_cleanup_empty(self, state):
        state = state.clone()
        code_files = state.value.get("code_files", {})
        for k in code_files:
            code_files[k] = re.sub(r'\n{3,}', '\n\n', code_files[k])
        state.value["code_files"] = code_files
        state.value["cleaned"] = True
        return state

    def _score_code_dedup(self, state):
        code_files = state.value.get("code_files", {})
        if not code_files:
            return 0.0
        seen = set()
        total = 0
        for content in code_files.values():
            funcs = self._extract_func_blocks(content)
            for fn in funcs:
                h = hashlib.sha256(fn.encode()).hexdigest()[:16]
                seen.add(h)
                total += 1
        if total == 0:
            return 1.0
        return len(seen) / total

    def _score_shared_extracted(self, state):
        if not state.value.get("shared_created"):
            return 0.0
        moved = state.value.get("funcs_moved", 0)
        dup_count = state.value.get("dup_func_count", 0)
        if dup_count == 0:
            return 1.0
        return min(moved / max(dup_count, 1), 1.0)

    def Run(self, command, params=None):
        if command == "explore":
            return self.explore(params)
        if command == "backward":
            return self.backward_search(params)
        if command == "plan":
            return self.goal_directed_plan(params)
        if command == "deps":
            return self.dependency_expansion(params)
        if command == "stats":
            return self.get_stats(params)
        if command == "best-paths":
            return self.get_best_paths(params)
        if command == "export":
            return self.export_graph(params)
        if command == "score":
            return self.score_state(params)
        if command == "diff":
            return self.constraint_diff(params)
        return (0, None, (1, "unknown command", 0))

    DEP_GRAPH = {
        "mixed_naming_styles": {
            "actions": ["rename_pascal", "rename_snake"],
            "requires": [],
            "description": "Unify naming convention across all files",
        },
        "missing_prefix": {
            "actions": ["add_prefix"],
            "requires": [],
            "description": "Add consistent prefix to all files",
        },
        "duplicate_files": {
            "actions": ["dedup_names"],
            "requires": [],
            "description": "Remove duplicate file entries",
        },
        "duplicate_functions": {
            "actions": ["delete_duplicate", "move_to_shared"],
            "requires": ["extract_functions"],
            "description": "Extract and deduplicate function definitions",
        },
        "no_shared_module": {
            "actions": ["move_to_shared"],
            "requires": ["extract_functions"],
            "description": "Create shared module for common functions",
        },
        "not_grouped": {
            "actions": ["group_by_ext"],
            "requires": [],
            "description": "Group files by extension",
        },
        "no_files": {
            "actions": [],
            "requires": [],
            "description": "No files to process",
        },
    }

    ACTION_PREREQS = {
        "rename_pascal": [],
        "rename_snake": [],
        "add_prefix": [],
        "remove_prefix": [],
        "normalize_ext": [],
        "group_by_ext": [],
        "flatten": [],
        "dedup_names": [],
        "extract_functions": [],
        "move_to_shared": ["extract_functions"],
        "delete_duplicate": ["extract_functions"],
        "cleanup_empty": [],
    }

    def _expand_dependency_tree(self, violation_type, depth=0, seen=None):
        if seen is None:
            seen = set()
        if violation_type in seen:
            return {"type": violation_type, "actions": [], "requires": [], "cycle": True, "depth": depth}
        seen.add(violation_type)

        spec = self.DEP_GRAPH.get(violation_type, {"actions": [], "requires": [], "description": "unknown"})
        node = {
            "type": violation_type,
            "description": spec["description"],
            "actions": spec["actions"],
            "requires": [],
            "depth": depth,
        }

        for req_action in spec["requires"]:
            prereqs = self.ACTION_PREREQS.get(req_action, [])
            req_node = {
                "action": req_action,
                "prerequisite": {
                    "action": req_action,
                    "prerequisites": list(prereqs),
                    "depth": depth + 1,
                },
            }
            for prereq in prereqs:
                sub_prereqs = self.ACTION_PREREQS.get(prereq, [])
                req_node["prerequisite"]["sub_prerequisites"] = list(sub_prereqs)
            node["requires"].append(req_node)

        for action in spec["actions"]:
            prereqs = self.ACTION_PREREQS.get(action, [])
            if prereqs:
                req_node = {
                    "action": action,
                    "prerequisite": {
                        "action": action,
                        "prerequisites": list(prereqs),
                        "depth": depth + 1,
                    },
                }
                for prereq in prereqs:
                    sub_prereqs = self.ACTION_PREREQS.get(prereq, [])
                    req_node["prerequisite"]["sub_prerequisites"] = list(sub_prereqs)
                if not any(r.get("action") == action for r in node["requires"]):
                    node["requires"].append(req_node)

        return node

    def _topological_sort_actions(self, dep_tree):
        order = []
        visited = set()

        def visit(node):
            if not isinstance(node, dict):
                return
            for req in node.get("requires", []):
                prereq = req.get("prerequisite", {})
                if isinstance(prereq, dict):
                    for sub in prereq.get("prerequisites", []):
                        if sub not in visited:
                            visited.add(sub)
                            order.append(sub)
                action = req.get("action")
                if action and action not in visited:
                    visited.add(action)
                    order.append(action)
            for action in node.get("actions", []):
                if action not in visited:
                    visited.add(action)
                    order.append(action)

        visit(dep_tree)
        return order

    def dependency_expansion(self, params):
        files = self._p(params, "files", [])
        current_files = self._p(params, "current_files", [])
        goal_name = self._p(params, "goal", "clean_naming")

        if not files and not current_files:
            current_files = [
                "old_const_file.py", "MyCamelScript.py", "UPPER_NAME.py",
                "already_ok.py", "old_const_file.py", "data.markdown",
            ]
        elif current_files and not files:
            files = current_files
        elif files and not current_files:
            current_files = files

        state = State({
            "files": list(current_files),
            "target_prefix": "Plf_",
            "naming_style": "mixed",
            "has_prefix": False,
        })
        if goal_name == "deduplicated_code":
            state.value["code_files"] = {
                "module_a.py": "def foo():\n    return 1\n\ndef bar():\n    return 2\n",
                "module_b.py": "def foo():\n    return 1\n\ndef baz():\n    return 3\n",
            }

        violations = self._compute_constraints(state, goal_name)
        initial_score = self._constraint_score(state, goal_name)

        dep_trees = []
        all_actions_ordered = []
        action_visited = set()

        for v_type, severity in violations:
            tree = self._expand_dependency_tree(v_type)
            dep_trees.append(tree)
            ordered = self._topological_sort_actions(tree)
            for action in ordered:
                if action not in action_visited:
                    action_visited.add(action)
                    all_actions_ordered.append(action)

        cleanup_actions = []
        if "delete_duplicate" in all_actions_ordered or "move_to_shared" in all_actions_ordered:
            if "cleanup_empty" not in action_visited:
                cleanup_actions.append("cleanup_empty")
                action_visited.add("cleanup_empty")

        full_pipeline = all_actions_ordered + cleanup_actions

        return (1, {
            "goal": goal_name,
            "current_score": round(initial_score, 4),
            "violations_found": len(violations),
            "violation_details": [{"type": v[0], "severity": round(v[1], 4)} for v in violations],
            "dependency_trees": dep_trees,
            "required_actions": all_actions_ordered,
            "cleanup_actions": cleanup_actions,
            "executable_pipeline": full_pipeline,
            "pipeline_steps": len(full_pipeline),
            "pipeline_str": " -> ".join(full_pipeline) if full_pipeline else "already_satisfied",
        }, None)

    def _compute_constraints(self, state, goal_name):
        violations = []
        files = state.value.get("files", [])
        if not files:
            return [("no_files", 1.0)]

        if goal_name in ("clean_naming", "consistent_prefix"):
            styles = set()
            for f in files:
                name, _ = os.path.splitext(f)
                if "_" in name:
                    styles.add("snake")
                elif re.search(r"[a-z][A-Z]", name):
                    styles.add("camel")
                elif name[:1].isupper():
                    styles.add("pascal")
                else:
                    styles.add("unknown")
            if len(styles) > 1:
                violations.append(("mixed_naming_styles", len(styles) / 4.0))
            prefix = state.value.get("target_prefix", "Plf_")
            unprefixed = sum(1 for f in files if not f.startswith(prefix))
            if unprefixed > 0:
                violations.append(("missing_prefix", unprefixed / len(files)))

        if goal_name in ("clean_naming", "no_duplicates"):
            dup_count = len(files) - len(set(files))
            if dup_count > 0:
                violations.append(("duplicate_files", dup_count / len(files)))

        if goal_name == "deduplicated_code":
            code_files = state.value.get("code_files", {})
            if code_files:
                seen = set()
                total = 0
                for content in code_files.values():
                    funcs = self._extract_func_blocks(content)
                    for fn in funcs:
                        h = hashlib.sha256(fn.encode()).hexdigest()[:16]
                        seen.add(h)
                        total += 1
                if total > len(seen):
                    violations.append(("duplicate_functions", (total - len(seen)) / total))
            if not state.value.get("shared_created"):
                violations.append(("no_shared_module", 0.5))

        if goal_name == "modular":
            if not state.value.get("grouped"):
                violations.append(("not_grouped", 0.5))

        return violations

    def _constraint_score(self, state, goal_name):
        violations = self._compute_constraints(state, goal_name)
        if not violations:
            return 1.0
        total_penalty = sum(v[1] for v in violations)
        return max(0.0, 1.0 - total_penalty)

    def _constraint_heuristic(self, state, goal_name):
        return self._constraint_score(state, goal_name)

    def constraint_diff(self, params):
        files = self._p(params, "files", [])
        goal_name = self._p(params, "goal", "clean_naming")
        if not files:
            files = [
                "old_const_file.py", "MyCamelScript.py", "UPPER_NAME.py",
                "already_ok.py", "old_const_file.py", "data.markdown",
            ]
        state = State({
            "files": list(files),
            "target_prefix": "Plf_",
            "naming_style": "mixed",
            "has_prefix": False,
        })
        violations = self._compute_constraints(state, goal_name)
        score = self._constraint_score(state, goal_name)
        return (1, {
            "goal": goal_name,
            "current_score": round(score, 4),
            "violations": [{"type": v[0], "severity": round(v[1], 4)} for v in violations],
            "violation_count": len(violations),
            "satisfied": len(violations) == 0,
        }, None)

    def goal_directed_plan(self, params):
        max_depth = self._p(params, "max_depth", self.state["max_depth"])
        max_nodes = self._p(params, "max_nodes", self.state["max_nodes"])
        goal_name = self._p(params, "goal", "clean_naming")
        files = self._p(params, "files", [])
        current_files = self._p(params, "current_files", [])

        if not current_files and not files:
            current_files = [
                "old_const_file.py", "MyCamelScript.py", "UPPER_NAME.py",
                "already_ok.py", "old_const_file.py", "data.markdown",
            ]
        elif files and not current_files:
            current_files = files

        root = State({
            "files": list(current_files),
            "target_prefix": "Plf_",
            "naming_style": "mixed",
            "has_prefix": False,
        })
        if goal_name == "deduplicated_code":
            root.value["code_files"] = {
                "module_a.py": "def foo():\n    return 1\n\ndef bar():\n    return 2\n",
                "module_b.py": "def foo():\n    return 1\n\ndef baz():\n    return 3\n",
            }
            self.state["prune_threshold"] = 0.05

        self.state["visited"] = {}
        self.state["transitions"] = []
        self.state["best_paths"] = []
        self.state["stats"] = {
            "expanded": 0, "pruned": 0, "goals_reached": 0, "duplicates": 0,
        }

        initial_violations = self._compute_constraints(root, goal_name)
        initial_score = self._constraint_score(root, goal_name)

        open_set = []
        root_hash = root.hash()
        heapq.heappush(open_set, FrontierItem(
            priority=-initial_score,
            state=root,
            depth=0,
            path=[],
            hash_val=root_hash,
        ))
        self.state["visited"][root_hash] = initial_score

        while open_set and len(self.state["visited"]) < max_nodes:
            current = heapq.heappop(open_set)
            self.state["stats"]["expanded"] += 1

            current_violations = self._compute_constraints(current.state, goal_name)
            if not current_violations:
                self.state["best_paths"].append({
                    "path": " -> ".join(current.path) if current.path else "already_satisfied",
                    "score": 1.0,
                    "depth": current.depth,
                    "goal": goal_name,
                    "direction": "constraint_driven",
                    "violations_at_goal": 0,
                })
                self.state["stats"]["goals_reached"] += 1
                continue

            if current.depth >= max_depth:
                continue

            for action in self.state["actions"]:
                new_state = action.fn(current.state)
                new_hash = new_state.hash()

                if new_hash in self.state["visited"]:
                    self.state["stats"]["duplicates"] += 1
                    continue

                new_score = self._constraint_heuristic(new_state, goal_name)

                old_score = self._constraint_heuristic(current.state, goal_name)
                if new_score < old_score:
                    self.state["stats"]["pruned"] += 1
                    self.state["transitions"].append(TransitionRecord(
                        parent_hash=current.hash_val,
                        action=action.name,
                        child_hash=new_hash,
                        depth=current.depth + 1,
                        score=new_score,
                        pruned=True,
                    ))
                    continue

                self.state["visited"][new_hash] = new_score
                self.state["transitions"].append(TransitionRecord(
                    parent_hash=current.hash_val,
                    action=action.name,
                    child_hash=new_hash,
                    depth=current.depth + 1,
                    score=new_score,
                ))

                new_path = current.path + [action.name]
                heapq.heappush(open_set, FrontierItem(
                    priority=-new_score,
                    state=new_state,
                    depth=current.depth + 1,
                    path=new_path,
                    hash_val=new_hash,
                ))

        self._save_memory(goal_name)

        return (1, {
            "goal": goal_name,
            "direction": "constraint_driven",
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "initial_violations": [{"type": v[0], "severity": round(v[1], 4)} for v in initial_violations],
            "initial_score": round(initial_score, 4),
            "stats": dict(self.state["stats"]),
            "best_paths": self.state["best_paths"][:10],
            "total_transitions": len(self.state["transitions"]),
        }, None)

    def _get_goal_fn(self, goal_name):
        goals = {
            "clean_naming": lambda s: self._score_clean_naming(s) >= 0.95,
            "consistent_prefix": lambda s: self._score_prefix_consistency(s) >= 0.95,
            "no_duplicates": lambda s: self._score_dedup(s) >= 1.0,
            "modular": lambda s: self._score_modular(s) >= 0.7,
            "deduplicated_code": lambda s: self._score_code_dedup(s) >= 1.0 and s.value.get("shared_created", False),
        }
        return goals.get(goal_name)

    def _get_score_fn(self, goal_name):
        scores = {
            "clean_naming": self._score_clean_naming,
            "consistent_prefix": self._score_prefix_consistency,
            "no_duplicates": self._score_dedup,
            "modular": self._score_modular,
            "deduplicated_code": lambda s: (self._score_code_dedup(s) * 0.6) + (self._score_shared_extracted(s) * 0.4),
        }
        return scores.get(goal_name, self._score_clean_naming)

    def explore(self, params):
        max_depth = self._p(params, "max_depth", self.state["max_depth"])
        max_nodes = self._p(params, "max_nodes", self.state["max_nodes"])
        goal_name = self._p(params, "goal", "clean_naming")
        files = self._p(params, "files", [])
        use_bfs = self._p(params, "bfs", False)

        goal_fn = self._get_goal_fn(goal_name)
        score_fn = self._get_score_fn(goal_name)

        if not files:
            files = [
                "old_const_file.py", "MyCamelScript.py", "UPPER_NAME.py",
                "already_ok.py", "old_const_file.py", "data.markdown",
            ]

        root = State({
            "files": list(files),
            "target_prefix": "Plf_",
            "naming_style": "mixed",
            "has_prefix": False,
        })

        if goal_name == "deduplicated_code":
            root.value["code_files"] = {
                "module_a.py": "def foo():\n    return 1\n\ndef bar():\n    return 2\n",
                "module_b.py": "def foo():\n    return 1\n\ndef baz():\n    return 3\n",
            }
            self.state["prune_threshold"] = 0.05

        self.state["visited"] = {}
        self.state["transitions"] = []
        self.state["best_paths"] = []
        self.state["stats"] = {
            "expanded": 0, "pruned": 0, "goals_reached": 0, "duplicates": 0,
        }

        if use_bfs:
            self._bfs_explore(root, max_depth, max_nodes, goal_fn, score_fn, goal_name)
        else:
            self._astar_explore(root, max_depth, max_nodes, goal_fn, score_fn, goal_name)

        self._save_memory(goal_name)

        return (1, {
            "goal": goal_name,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "stats": dict(self.state["stats"]),
            "best_paths": self.state["best_paths"][:10],
            "total_transitions": len(self.state["transitions"]),
        }, None)

    def _build_goal_state(self, goal_name, files):
        goal_state = State({
            "files": list(files) if files else [
                "Plf_OldConstFile.py", "Plf_MyCamelScript.py",
                "Plf_UpperName.py", "Plf_AlreadyOk.py", "Plf_Data.md",
            ],
            "target_prefix": "Plf_",
            "naming_style": "pascal",
            "has_prefix": True,
        })
        if goal_name == "deduplicated_code":
            goal_state.value["code_files"] = {
                "module_a.py": "def bar():\n    return 2\n",
                "module_b.py": "def baz():\n    return 3\n",
                "shared_utils.py": "def foo():\n    return 1\n",
            }
            goal_state.value["shared_created"] = True
            goal_state.value["dup_func_count"] = 0
            goal_state.value["functions_extracted"] = True
        elif goal_name == "clean_naming":
            goal_state.value["naming_style"] = "pascal"
            goal_state.value["has_prefix"] = True
        elif goal_name == "no_duplicates":
            goal_state.value["deduped"] = True
        elif goal_name == "consistent_prefix":
            goal_state.value["has_prefix"] = True
        elif goal_name == "modular":
            goal_state.value["grouped"] = True
        return goal_state

    def _get_inverse_actions(self, action_name):
        inverse_map = {
            "rename_pascal": ["rename_snake", "rename_pascal"],
            "rename_snake": ["rename_pascal", "rename_snake"],
            "add_prefix": ["remove_prefix"],
            "remove_prefix": ["add_prefix"],
            "normalize_ext": ["normalize_ext"],
            "group_by_ext": ["flatten"],
            "flatten": ["group_by_ext"],
            "dedup_names": ["dedup_names"],
            "extract_functions": ["extract_functions"],
            "move_to_shared": ["delete_duplicate"],
            "delete_duplicate": ["move_to_shared"],
            "cleanup_empty": ["cleanup_empty"],
        }
        return inverse_map.get(action_name, [])

    def backward_search(self, params):
        max_depth = self._p(params, "max_depth", self.state["max_depth"])
        max_nodes = self._p(params, "max_nodes", self.state["max_nodes"])
        goal_name = self._p(params, "goal", "clean_naming")
        files = self._p(params, "files", [])
        current_files = self._p(params, "current_files", [])
        use_bfs = self._p(params, "bfs", False)

        if not current_files:
            current_files = [
                "old_const_file.py", "MyCamelScript.py", "UPPER_NAME.py",
                "already_ok.py", "old_const_file.py", "data.markdown",
            ]

        current_set = set(current_files)

        if goal_name == "deduplicated_code":
            goal_state = self._build_goal_state(goal_name, files)
        else:
            temp_state = State({
                "files": list(current_files),
                "target_prefix": "Plf_",
                "naming_style": "mixed",
                "has_prefix": False,
            })
            if goal_name in ("clean_naming", "consistent_prefix"):
                temp_state = self._act_rename_pascal(temp_state)
                temp_state = self._act_dedup(temp_state)
                temp_state = self._act_add_prefix(temp_state)
            elif goal_name == "no_duplicates":
                temp_state = self._act_dedup(temp_state)
            elif goal_name == "modular":
                temp_state = self._act_group_by_ext(temp_state)
            goal_state = temp_state

        goal_files = set(goal_state.value.get("files", []))

        self.state["visited"] = {}
        self.state["transitions"] = []
        self.state["best_paths"] = []
        self.state["stats"] = {
            "expanded": 0, "pruned": 0, "goals_reached": 0, "duplicates": 0,
        }

        forward_visited = {}
        backward_visited = {}

        root = State({
            "files": list(current_files),
            "target_prefix": "Plf_",
            "naming_style": "mixed",
            "has_prefix": False,
        })

        root_hash = root.hash()
        goal_hash = goal_state.hash()
        forward_visited[root_hash] = (root, [], 0)
        backward_visited[goal_hash] = (goal_state, [], 0)

        forward_queue = deque([(root, [], 0, root_hash)])
        backward_queue = deque([(goal_state, [], 0, goal_hash)])

        half_depth = max_depth // 2 + 1

        while (forward_queue or backward_queue) and \
              (len(forward_visited) + len(backward_visited)) < max_nodes:

            if forward_queue:
                current, path, depth, current_hash = forward_queue.popleft()
                self.state["stats"]["expanded"] += 1

                if depth >= half_depth:
                    pass
                else:
                    for action in self.state["actions"]:
                        new_state = action.fn(current)
                        new_hash = new_state.hash()
                        if new_hash in forward_visited:
                            self.state["stats"]["duplicates"] += 1
                            continue
                        new_path = path + [action.name]
                        forward_visited[new_hash] = (new_state, new_path, depth + 1)
                        self.state["transitions"].append(TransitionRecord(
                            parent_hash=current_hash,
                            action=action.name,
                            child_hash=new_hash,
                            depth=depth + 1,
                            score=1.0 - (depth * 0.1),
                        ))
                        if new_hash in backward_visited:
                            back_state, back_path, back_depth = backward_visited[new_hash]
                            full_path = new_path + list(reversed(back_path))
                            self.state["best_paths"].append({
                                "path": " -> ".join(full_path) if full_path else "already_at_goal",
                                "score": 1.0,
                                "depth": depth + 1 + back_depth,
                                "goal": goal_name,
                                "direction": "bidirectional",
                                "meeting_point": new_hash,
                            })
                            self.state["stats"]["goals_reached"] += 1
                        forward_queue.append((new_state, new_path, depth + 1, new_hash))

            if backward_queue:
                current, path, depth, current_hash = backward_queue.popleft()
                self.state["stats"]["expanded"] += 1

                if depth >= half_depth:
                    pass
                else:
                    for action in self.state["actions"]:
                        new_state = action.fn(current)
                        new_hash = new_state.hash()
                        if new_hash in backward_visited:
                            self.state["stats"]["duplicates"] += 1
                            continue
                        new_path = path + [action.name]
                        backward_visited[new_hash] = (new_state, new_path, depth + 1)
                        self.state["transitions"].append(TransitionRecord(
                            parent_hash=current_hash,
                            action=action.name,
                            child_hash=new_hash,
                            depth=depth + 1,
                            score=1.0 - (depth * 0.1),
                        ))
                        if new_hash in forward_visited:
                            fwd_state, fwd_path, fwd_depth = forward_visited[new_hash]
                            full_path = fwd_path + list(reversed(new_path))
                            self.state["best_paths"].append({
                                "path": " -> ".join(full_path) if full_path else "already_at_goal",
                                "score": 1.0,
                                "depth": fwd_depth + depth + 1,
                                "goal": goal_name,
                                "direction": "bidirectional",
                                "meeting_point": new_hash,
                            })
                            self.state["stats"]["goals_reached"] += 1
                        backward_queue.append((new_state, new_path, depth + 1, new_hash))

        self._save_memory(goal_name)

        return (1, {
            "goal": goal_name,
            "direction": "bidirectional",
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "current_files": current_files,
            "target_files": list(goal_files),
            "stats": dict(self.state["stats"]),
            "best_paths": self.state["best_paths"][:10],
            "forward_states": len(forward_visited),
            "backward_states": len(backward_visited),
            "total_transitions": len(self.state["transitions"]),
        }, None)

    def _bfs_explore(self, root, max_depth, max_nodes, goal_fn, score_fn, goal_name):
        queue = deque()
        root_hash = root.hash()
        queue.append((root, 0, [], root_hash))
        self.state["visited"][root_hash] = 0.0

        while queue and len(self.state["visited"]) < max_nodes:
            current, depth, path, current_hash = queue.popleft()
            self.state["stats"]["expanded"] += 1

            if goal_fn and goal_fn(current):
                score = score_fn(current) if score_fn else 1.0
                self.state["best_paths"].append({
                    "path": " -> ".join(path) if path else "root",
                    "score": score,
                    "depth": depth,
                    "goal": goal_name,
                })
                self.state["stats"]["goals_reached"] += 1
                continue

            if depth >= max_depth:
                continue

            for action in self.state["actions"]:
                new_state = action.fn(current)
                new_hash = new_state.hash()

                if new_hash in self.state["visited"]:
                    self.state["stats"]["duplicates"] += 1
                    continue

                score = score_fn(new_state) if score_fn else 0.5

                if score < self.state["prune_threshold"]:
                    self.state["stats"]["pruned"] += 1
                    self.state["transitions"].append(TransitionRecord(
                        parent_hash=current_hash,
                        action=action.name,
                        child_hash=new_hash,
                        depth=depth + 1,
                        score=score,
                        pruned=True,
                    ))
                    continue

                self.state["visited"][new_hash] = score
                self.state["transitions"].append(TransitionRecord(
                    parent_hash=current_hash,
                    action=action.name,
                    child_hash=new_hash,
                    depth=depth + 1,
                    score=score,
                ))

                new_path = path + [action.name]
                queue.append((new_state, depth + 1, new_path, new_hash))

    def _astar_explore(self, root, max_depth, max_nodes, goal_fn, score_fn, goal_name):
        open_set = []
        root_hash = root.hash()
        root_score = score_fn(root) if score_fn else 0.0
        heapq.heappush(open_set, FrontierItem(
            priority=-root_score,
            state=root,
            depth=0,
            path=[],
            hash_val=root_hash,
        ))
        self.state["visited"][root_hash] = root_score

        while open_set and len(self.state["visited"]) < max_nodes:
            current = heapq.heappop(open_set)
            self.state["stats"]["expanded"] += 1

            if goal_fn and goal_fn(current.state):
                self.state["best_paths"].append({
                    "path": " -> ".join(current.path) if current.path else "root",
                    "score": -current.priority,
                    "depth": current.depth,
                    "goal": goal_name,
                })
                self.state["stats"]["goals_reached"] += 1
                continue

            if current.depth >= max_depth:
                continue

            for action in self.state["actions"]:
                new_state = action.fn(current.state)
                new_hash = new_state.hash()

                if new_hash in self.state["visited"]:
                    self.state["stats"]["duplicates"] += 1
                    continue

                score = score_fn(new_state) if score_fn else 0.5

                if score < self.state["prune_threshold"]:
                    self.state["stats"]["pruned"] += 1
                    self.state["transitions"].append(TransitionRecord(
                        parent_hash=current.hash_val,
                        action=action.name,
                        child_hash=new_hash,
                        depth=current.depth + 1,
                        score=score,
                        pruned=True,
                    ))
                    continue

                self.state["visited"][new_hash] = score
                self.state["transitions"].append(TransitionRecord(
                    parent_hash=current.hash_val,
                    action=action.name,
                    child_hash=new_hash,
                    depth=current.depth + 1,
                    score=score,
                ))

                new_path = current.path + [action.name]
                heapq.heappush(open_set, FrontierItem(
                    priority=-score,
                    state=new_state,
                    depth=current.depth + 1,
                    path=new_path,
                    hash_val=new_hash,
                ))

    def _save_memory(self, goal_name):
        conn = sqlite3.connect(self.state["memory_db"])
        cur = conn.cursor()
        for t in self.state["transitions"]:
            cur.execute("""
                INSERT INTO state_transitions
                (parent_hash, action, child_hash, depth, score, pruned, goal_reached)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                t.parent_hash, t.action, t.child_hash,
                t.depth, t.score, 1 if t.pruned else 0, 0,
            ))
        for bp in self.state["best_paths"]:
            cur.execute("""
                INSERT INTO best_paths (goal_name, path, score, depth)
                VALUES (?, ?, ?, ?)
            """, (bp["goal"], bp["path"], bp["score"], bp["depth"]))
        for h, score in self.state["visited"].items():
            cur.execute("""
                INSERT OR REPLACE INTO state_scores (hash, score, depth, visited_count)
                VALUES (?, ?, 0, 1)
            """, (h, score))
        conn.commit()
        conn.close()

    def get_stats(self, params):
        conn = sqlite3.connect(self.state["memory_db"])
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM state_transitions")
        transitions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as cnt FROM state_transitions WHERE pruned=1")
        pruned = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as cnt FROM best_paths")
        best = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as cnt FROM state_scores")
        scored = cur.fetchone()[0]
        cur.execute("SELECT goal_name, COUNT(*) as cnt, AVG(score) as avg_score FROM best_paths GROUP BY goal_name")
        by_goal = [{"goal": r[0], "count": r[1], "avg_score": round(r[2], 4)} for r in cur.fetchall()]
        cur.execute("SELECT action, COUNT(*) as cnt, AVG(score) as avg FROM state_transitions WHERE pruned=0 GROUP BY action ORDER BY cnt DESC")
        by_action = [{"action": r[0], "count": r[1], "avg_score": round(r[2], 4)} for r in cur.fetchall()]
        conn.close()
        return (1, {
            "total_transitions": transitions,
            "pruned": pruned,
            "best_paths": best,
            "scored_states": scored,
            "by_goal": by_goal,
            "by_action": by_action,
        }, None)

    def get_best_paths(self, params):
        goal = self._p(params, "goal")
        limit = self._p(params, "limit", 10)
        conn = sqlite3.connect(self.state["memory_db"])
        cur = conn.cursor()
        if goal:
            cur.execute(
                "SELECT goal_name, path, score, depth, hit_count FROM best_paths WHERE goal_name=? ORDER BY score DESC LIMIT ?",
                (goal, limit)
            )
        else:
            cur.execute(
                "SELECT goal_name, path, score, depth, hit_count FROM best_paths ORDER BY score DESC LIMIT ?",
                (limit,)
            )
        rows = [{"goal": r[0], "path": r[1], "score": r[2], "depth": r[3], "hits": r[4]} for r in cur.fetchall()]
        conn.close()
        return (1, rows, None)

    def export_graph(self, params):
        conn = sqlite3.connect(self.state["memory_db"])
        cur = conn.cursor()
        cur.execute("SELECT parent_hash, action, child_hash, depth, score, pruned FROM state_transitions LIMIT 1000")
        edges = [{"parent": r[0], "action": r[1], "child": r[2], "depth": r[3], "score": r[4], "pruned": bool(r[5])} for r in cur.fetchall()]
        cur.execute("SELECT hash, score, visited_count FROM state_scores")
        nodes = [{"hash": r[0], "score": r[1], "visits": r[2]} for r in cur.fetchall()]
        conn.close()
        return (1, {"nodes": len(nodes), "edges": len(edges), "node_sample": nodes[:20], "edge_sample": edges[:20]}, None)

    def score_state(self, params):
        files = self._p(params, "files", [])
        if not files:
            return (0, None, (1, "no files", 0))
        state = State({"files": files, "target_prefix": "Plf_"})
        return (1, {
            "clean_naming": round(self._score_clean_naming(state), 4),
            "prefix_consistency": round(self._score_prefix_consistency(state), 4),
            "dedup": round(self._score_dedup(state), 4),
            "modular": round(self._score_modular(state), 4),
        }, None)


if __name__ == "__main__":
    engine = RamStateEngine()

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: ram_state_engine.py <command> [args]\n")
        sys.stderr.write("Commands:\n")
        sys.stderr.write("  explore [--goal clean_naming] [--max-depth 4] [--max-nodes 5000] [--bfs]\n")
        sys.stderr.write("  backward [--goal clean_naming] [--current-files f1.py,f2.py] [--max-depth 5]\n")
        sys.stderr.write("  plan [--goal clean_naming] [--current-files f1.py,f2.py] [--max-depth 5]\n")
        sys.stderr.write("  deps [--goal clean_naming] [--files f1.py,f2.py]\n")
        sys.stderr.write("  diff [--goal clean_naming] [--files f1.py,f2.py]\n")
        sys.stderr.write("  stats\n")
        sys.stderr.write("  best-paths [--goal clean_naming] [--limit 10]\n")
        sys.stderr.write("  export\n")
        sys.stderr.write("  score --files file1.py,file2.py\n")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]
    goal = "clean_naming"
    max_depth = 4
    max_nodes = 5000
    use_bfs = False
    files_arg = None
    current_files_arg = None

    i = 0
    while i < len(args):
        if args[i] == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            i += 2
        elif args[i] == "--max-depth" and i + 1 < len(args):
            max_depth = int(args[i + 1])
            i += 2
        elif args[i] == "--max-nodes" and i + 1 < len(args):
            max_nodes = int(args[i + 1])
            i += 2
        elif args[i] == "--bfs":
            use_bfs = True
            i += 1
        elif args[i] == "--files" and i + 1 < len(args):
            files_arg = args[i + 1].split(",")
            i += 2
        elif args[i] == "--current-files" and i + 1 < len(args):
            current_files_arg = args[i + 1].split(",")
            i += 2
        else:
            i += 1

    if cmd == "explore":
        rc, data, err = engine.explore({
            "goal": goal,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "bfs": use_bfs,
            "files": files_arg,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "backward":
        rc, data, err = engine.backward_search({
            "goal": goal,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "files": files_arg,
            "current_files": current_files_arg,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "plan":
        rc, data, err = engine.goal_directed_plan({
            "goal": goal,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "files": files_arg,
            "current_files": current_files_arg,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "diff":
        rc, data, err = engine.constraint_diff({
            "goal": goal,
            "files": files_arg or current_files_arg,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "deps":
        rc, data, err = engine.dependency_expansion({
            "goal": goal,
            "files": files_arg,
            "current_files": current_files_arg,
        })
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "stats":
        rc, data, err = engine.get_stats({})
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "best-paths":
        rc, data, err = engine.get_best_paths({"goal": goal if goal != "clean_naming" else None})
        if rc == 1:
            for p in data:
                sys.stdout.write(f"  [{p['depth']}] {p['path']}  score={p['score']}  goal={p['goal']}\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "export":
        rc, data, err = engine.export_graph({})
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    elif cmd == "score":
        if not files_arg:
            sys.stderr.write("Usage: score --files file1.py,file2.py\n")
            sys.exit(1)
        rc, data, err = engine.score_state({"files": files_arg})
        if rc == 1:
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stderr.write(f"Error: {err}\n")
            sys.exit(1)

    else:
        sys.stderr.write(f"Unknown command: {cmd}\n")
        sys.exit(1)
