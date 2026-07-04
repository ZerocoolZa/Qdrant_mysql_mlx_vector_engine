#!/usr/bin/env python3

#[@GHOST]{[@file<transform_graph_engine.py>][@domain<Cascade_toolStack>][@role<graph_engine>][@auth<user>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<user>][@role<graph_engine>][@return<Tuple3>][@no<decorators|print|hardcoded_paths>]}

"""
Core Transformation Graph Engine.

State graph + primitive algebra + A* planner foundation.
Chunk 1: Core engine. Chunk 2 adds templates, loops, learning.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any, Optional, Tuple
import hashlib
import heapq
import copy


@dataclass
class CodeState:
    """
    Represents a snapshot of a codebase.
    In real system this becomes:
    - AST hashes
    - file graph
    - dependency map
    """
    files: Dict[str, str]

    def hash(self) -> str:
        h = hashlib.sha256()
        for k in sorted(self.files.keys()):
            h.update(k.encode())
            h.update(self.files[k].encode())
        return h.hexdigest()

    def clone(self) -> "CodeState":
        return CodeState(files=copy.deepcopy(self.files))


@dataclass
class Primitive:
    name: str
    apply_fn: Callable[["CodeState", Dict[str, Any]], "CodeState"]

    def apply(self, state: CodeState, params: Dict[str, Any]) -> CodeState:
        return self.apply_fn(state, params)


def grep_pattern(state: CodeState, params: Dict[str, Any]) -> CodeState:
    return state.clone()


def extract_regex(state: CodeState, params: Dict[str, Any]) -> CodeState:
    state = state.clone()
    file = params["file"]
    pattern = params["pattern"]
    if file in state.files:
        state.files[file] = state.files[file].replace(pattern, "")
    return state


def append(state: CodeState, params: Dict[str, Any]) -> CodeState:
    state = state.clone()
    file = params["file"]
    content = params["content"]
    state.files[file] = state.files.get(file, "") + "\n" + content
    return state


def delete_pattern(state: CodeState, params: Dict[str, Any]) -> CodeState:
    state = state.clone()
    file = params["file"]
    pattern = params["pattern"]
    if file in state.files:
        state.files[file] = state.files[file].replace(pattern, "")
    return state


def insert_after(state: CodeState, params: Dict[str, Any]) -> CodeState:
    state = state.clone()
    file = params["file"]
    marker = params["marker"]
    insert = params["insert"]
    if file in state.files and marker in state.files[file]:
        parts = state.files[file].split(marker)
        state.files[file] = marker.join([parts[0] + marker + insert] + parts[1:])
    return state


PRIMITIVES: Dict[str, Primitive] = {
    "grep_pattern": Primitive("grep_pattern", grep_pattern),
    "extract_regex": Primitive("extract_regex", extract_regex),
    "append": Primitive("append", append),
    "delete_pattern": Primitive("delete_pattern", delete_pattern),
    "insert_after": Primitive("insert_after", insert_after),
}


@dataclass
class Action:
    primitive: str
    params: Dict[str, Any]


def apply_action(state: CodeState, action: Action) -> CodeState:
    if action.primitive not in PRIMITIVES:
        return state
    return PRIMITIVES[action.primitive].apply(state, action.params)


@dataclass
class Goal:
    target_contains: Optional[str] = None
    required_file: Optional[str] = None


def evaluate_goal(state: CodeState, goal: Goal) -> float:
    score = 0.0
    if goal.required_file:
        score += 1.0 if goal.required_file in state.files else 0.0
    if goal.target_contains:
        for content in state.files.values():
            if goal.target_contains in content:
                score += 1.0
    return score


@dataclass(order=True)
class PrioritizedItem:
    priority: float
    state: Any = field(compare=False)
    path: Any = field(compare=False)


def heuristic(state: CodeState, goal: Goal) -> float:
    return -evaluate_goal(state, goal)


def plan(
    start: CodeState,
    goal: Goal,
    action_space: List[Action],
    max_steps: int = 10
) -> List[Action]:
    open_set = []
    visited = set()
    start_item = PrioritizedItem(
        priority=0,
        state=start,
        path=[]
    )
    heapq.heappush(open_set, start_item)
    while open_set:
        current = heapq.heappop(open_set)
        state_hash = current.state.hash()
        if state_hash in visited:
            continue
        visited.add(state_hash)
        if evaluate_goal(current.state, goal) > 0:
            return current.path
        if len(current.path) >= max_steps:
            continue
        for action in action_space:
            new_state = apply_action(current.state, action)
            new_path = current.path + [action]
            priority = heuristic(new_state, goal)
            heapq.heappush(
                open_set,
                PrioritizedItem(priority, new_state, new_path)
            )
    return []
