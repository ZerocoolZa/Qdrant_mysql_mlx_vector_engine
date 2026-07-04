#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_Graph/BndEngine.py" date="2026-07-04" author="Devin" session_id="bnd-radiation" context="BND radiation engine — seed -> BNQ burst -> BND burst -> repeat -> closure. Directed semantic state machine. No interrogative layer required."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch no_decorators no_print no_hardcoded no_self_underscore"}
# [@FILEID]{id="BndEngine.py" domain="dom_graph" authority="BndEngine"}
# [@SUMMARY]{summary="BND radiation engine. Give it a seed word. It radiates ALL questions (BNQ) and ALL directions (BND) outward like radiation in expanding layers until closure. bnq -> bnd -> bnq -> bnq -> done. Cluster initializes state space. BND defines all valid forward transitions. R filters invalid moves. Closure when no edges above threshold."}
# [@CLASS]{class="BndEngine" domain="dom_graph" authority="engine"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="cmd_seed" type="init"}
# [@METHOD]{method="cmd_radiate" type="loop"}
# [@METHOD]{method="cmd_frontier" type="export"}
# [@METHOD]{method="cmd_closure" type="check"}
# [@METHOD]{method="cmd_graph" type="visualize"}
# [@METHOD]{method="cmd_state" type="read"}
# [@METHOD]{method="cluster_seed" type="expand"}
# [@METHOD]{method="generate_bnq" type="expand"}
# [@METHOD]{method="generate_bnd" type="expand"}
# [@METHOD]{method="score_edge" type="score"}
# [@METHOD]{method="restrict" type="filter"}
# [@METHOD]{method="check_closure" type="check"}
# [@METHOD]{method="build_graph_text" type="visualize"}

"""BndEngine — BND radiation engine.

Pipeline:
    1. SEED      — give a word
    2. CLUSTER   — expand seed into concept space (meanings, subdomains, functions, components, edge cases, related)
    3. RADIATE   — burst BNQ (questions) then BND (directions) outward in layers
    4. RESTRICT  — R filters invalid moves (structural, domain, progress, saturation)
    5. SCORE     — score each edge: information_gain + dependency_unlock + structural_progress + execution_closeness
    6. SELECT    — argmax over valid scored edges
    7. MOVE      — transition to next state
    8. CLOSURE   — when no edges above threshold, graph is saturated

The radiation pattern:
    Layer 0: seed
    Layer 1: BNQ burst (all questions around seed) -> BND burst (all directions)
    Layer 2: BNQ burst from each BND -> BND burst
    Layer 3: BNQ burst from each BND -> BND burst
    ...
    Layer N: no BNQ or BND above threshold -> CLOSURE

bnq -> bnd -> bnq -> bnq -> done

BNQ is optional. BND is the primitive. The question was the old UI layer.
The direction is the engine. Intelligence = path selection, not questioning.

Commands (via Run dispatch):
    seed       — give a seed word, cluster it, start radiation
    radiate    — run full radiation loop until closure
    frontier   — export all BNQ + BND across all nodes
    closure    — check if graph is saturated
    graph      — return graph as text (nodes, edges, layers)
    state      — return engine state
    set_config — set config (threshold, max_depth, weights)
"""

import os
import json
import math
import random
import mysql.connector
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── MySQL knowledge base (replaces LLM) ──
_DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
}
_DB_CONN_VB_CODE = None
_DB_CONN_VB_SHARED = None

def _db_get_conn(db_name):
    """Get or create persistent connection."""
    global _DB_CONN_VB_CODE, _DB_CONN_VB_SHARED
    try:
        if db_name == "vb_code_test":
            if _DB_CONN_VB_CODE is None or not _DB_CONN_VB_CODE.is_connected():
                _DB_CONN_VB_CODE = mysql.connector.connect(database="vb_code_test", **_DB_CONFIG)
            return _DB_CONN_VB_CODE
        elif db_name == "vb_shared":
            if _DB_CONN_VB_SHARED is None or not _DB_CONN_VB_SHARED.is_connected():
                _DB_CONN_VB_SHARED = mysql.connector.connect(database="vb_shared", **_DB_CONFIG)
            return _DB_CONN_VB_SHARED
    except Exception:
        return None
    return None

def _db_query(sql, db_name):
    """Query MySQL using persistent connection. Returns list of dicts. Never raises."""
    conn = _db_get_conn(db_name)
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        return rows
    except Exception:
        try:
            conn.reconnect()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            return []

def _db_find_classes(keyword, limit=5):
    sql = "SELECT class_name FROM vb_classes WHERE class_name LIKE '%{}%' LIMIT {};".format(keyword.replace("'", ""), limit)
    rows = _db_query(sql, "vb_code_test")
    return [r["class_name"] for r in rows if r.get("class_name")]

def _db_find_methods(keyword, limit=5):
    sql = "SELECT method_name FROM vb_methods WHERE method_name LIKE '%{}%' LIMIT {};".format(keyword.replace("'", ""), limit)
    rows = _db_query(sql, "vb_code_test")
    return [r["method_name"] for r in rows if r.get("method_name")]

def _db_find_rules(keyword, limit=3):
    sql = "SELECT pattern, fix_action, confidence FROM learned_rules WHERE pattern LIKE '%{}%' ORDER BY confidence DESC LIMIT {};".format(keyword.replace("'", ""), limit)
    rows = _db_query(sql, "vb_shared")
    return [(r.get("pattern", ""), r.get("fix_action", ""), r.get("confidence", 0)) for r in rows]

def _db_find_problems(keyword, limit=3):
    sql = "SELECT problem, description FROM know_problems WHERE problem LIKE '%{}%' LIMIT {};".format(keyword.replace("'", ""), limit)
    rows = _db_query(sql, "vb_shared")
    return [(r.get("problem", ""), r.get("description", "")) for r in rows]

# ── Constants ──
DEFAULT_THRESHOLD = 0.10
DEFAULT_MAX_DEPTH = 10
DEFAULT_MAX_BNQ_PER_LAYER = 20
DEFAULT_MAX_BND_PER_LAYER = 15
DEFAULT_CLUSTER_SIZE = 15

SCORE_WEIGHTS = {
    "information_gain": 0.25,
    "dependency_unlock": 0.25,
    "structural_progress": 0.25,
    "execution_closeness": 0.25,
}

NODE_STATES = ("unvisited", "frontier", "active", "visited", "closed")

DIRECTION_TYPES = (
    "expansion",
    "decomposition",
    "constraint_tightening",
    "implementation_shift",
    "validation_shift",
)

RESTRICTION_TYPES = ("structural", "domain", "progress", "saturation")

# ── Cluster expansion templates ──
CLUSTER_ANGLES = (
    "meaning",
    "subdomain",
    "function",
    "component",
    "edge_case",
    "related_system",
    "input",
    "output",
    "dependency",
    "constraint",
    "failure_mode",
    "validation",
    "storage",
    "interface",
    "lifecycle",
)

# ── BNQ generation templates ──
BNQ_TEMPLATES = (
    "What is {node}?",
    "What does {node} do?",
    "What are the parts of {node}?",
    "How does {node} work?",
    "Why does {node} exist?",
    "When is {node} used?",
    "Where does {node} store data?",
    "What feeds into {node}?",
    "What reads from {node}?",
    "What restricts {node}?",
    "What can go wrong with {node}?",
    "How is {node} validated?",
    "What is {node} dependent on?",
    "What depends on {node}?",
    "What happens after {node}?",
    "What happens before {node}?",
    "Can {node} fail?",
    "Can {node} be replaced?",
    "What is the boundary of {node}?",
    "What is inside {node} vs outside?",
)

# ── BND generation templates ──
BND_TEMPLATES = {
    "expansion": (
        "Expand {node} into sub-concepts",
        "Go deeper into {node}",
        "Radiate from {node} to related areas",
    ),
    "decomposition": (
        "Split {node} into parts",
        "Decompose {node} into components",
        "Break {node} into modules",
    ),
    "constraint_tightening": (
        "Add rules to {node}",
        "Define limits for {node}",
        "Tighten constraints on {node}",
    ),
    "implementation_shift": (
        "Move {node} from design to code",
        "Implement {node}",
        "Build {node}",
    ),
    "validation_shift": (
        "Test {node}",
        "Validate {node}",
        "Verify {node}",
    ),
}


@dataclass
class BnqNode:
    """A question node in the radiation graph."""
    node_id: int = 0
    text: str = ""
    layer: int = 0
    parent_id: int = 0
    state: str = "frontier"
    score: float = 0.0
    answer: str = ""
    answered: bool = False


@dataclass
class BndEdge:
    """A directional edge in the radiation graph."""
    edge_id: int = 0
    from_node: str = ""
    to_node: str = ""
    direction_type: str = ""
    layer: int = 0
    score: float = 0.0
    restricted: bool = False
    restriction_reason: str = ""
    traversed: bool = False


class BndEngine:
    """BND radiation engine — seed -> BNQ burst -> BND burst -> repeat -> closure.

    The engine radiates questions and directions outward from a seed word
    in expanding layers until no more valid edges exist above threshold.

    bnq -> bnd -> bnq -> bnq -> done
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.state = {
            "class": "BndEngine",
            "initialized": True,
            "seed": "",
            "cluster": [],
            "nodes": [],
            "edges": [],
            "bnq_nodes": [],
            "bnd_edges": [],
            "layer": 0,
            "closed": False,
            "total_bnq": 0,
            "total_bnd": 0,
            "total_layers": 0,
            "total_restricted": 0,
            "total_traversed": 0,
            "threshold": DEFAULT_THRESHOLD,
            "max_depth": DEFAULT_MAX_DEPTH,
            "max_bnq_per_layer": DEFAULT_MAX_BNQ_PER_LAYER,
            "max_bnd_per_layer": DEFAULT_MAX_BND_PER_LAYER,
            "cluster_size": DEFAULT_CLUSTER_SIZE,
            "score_weights": dict(SCORE_WEIGHTS),
            "restriction_types": list(RESTRICTION_TYPES),
            "visited_hashes": [],
            "frontier_nodes": [],
            "closure_reason": "",
            "last_seed": "",
            "last_result": None,
            "use_llm": False,
            "max_nodes": 200,
            "max_edges": 500,
        }
        self._node_counter = 0
        self._edge_counter = 0

    def _p(self, label, value):
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "seed": self.cmd_seed,
            "radiate": self.cmd_radiate,
            "frontier": self.cmd_frontier,
            "closure": self.cmd_closure,
            "graph": self.cmd_graph,
            "state": self.cmd_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("BND_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    # ── Commands ──

    def cmd_set_config(self, params):
        for key, value in params.items():
            if key in self.state:
                self.state[key] = value
        return (1, {"updated": len(params)}, None)

    def cmd_state(self, params):
        return (1, dict(self.state), None)

    def cmd_seed(self, params):
        """Give a BNQ (question) or seed word. Cluster it. Initialize the graph.

        BNQ is the entry point — the user's question.
        From BNQ, the system asks 'all best next directions' and radiates BND -> BND -> closure.
        """
        seed = params.get("seed") or params.get("word") or params.get("question") or params.get("bnq")
        if not seed:
            return (0, None, ("BND_NO_SEED", "no seed/question provided", 0))

        # Reset
        self.state["seed"] = seed
        self.state["cluster"] = []
        self.state["nodes"] = []
        self.state["edges"] = []
        self.state["bnq_nodes"] = []
        self.state["bnd_edges"] = []
        self.state["layer"] = 0
        self.state["closed"] = False
        self.state["total_bnq"] = 0
        self.state["total_bnd"] = 0
        self.state["total_layers"] = 0
        self.state["total_restricted"] = 0
        self.state["total_traversed"] = 0
        self.state["visited_hashes"] = []
        self.state["frontier_nodes"] = []
        self.state["closure_reason"] = ""
        self._node_counter = 0
        self._edge_counter = 0

        # Level 1: Cluster around the question/seed
        cluster = self.cluster_seed(seed)
        self.state["cluster"] = cluster

        # Add the BNQ (question) as the root node
        self._add_node(seed, layer=0, node_type="bnq")

        # Add cluster items as layer 0 nodes
        for item in cluster:
            self._add_node(item, layer=0, node_type="cluster")

        self.state["last_seed"] = seed
        self._p("seed", seed)

        return (1, {
            "seed": seed,
            "cluster_size": len(cluster),
            "cluster": cluster,
            "nodes": len(self.state["nodes"]),
            "message": "BNQ seeded. Run 'radiate' to ask all best next directions.",
        }, None)

    def cmd_radiate(self, params):
        """Run the full BND-recursive radiation loop until closure.

        BND -> BND -> BND -> closure.
        Feed-forward only. Each step consumed into state. No backward traversal.
        BNQ is optional probe — used only to expand frontier, not as driver.
        """
        if not self.state["seed"]:
            return (0, None, ("BND_NO_SEED", "run 'seed' first", 0))

        max_depth = params.get("max_depth", self.state["max_depth"])
        threshold = params.get("threshold", self.state["threshold"])
        use_bnq_probe = params.get("use_bnq_probe", False)

        layers = []

        while not self.state["closed"] and self.state["layer"] < max_depth:
            # Hard caps — prevent explosion
            if len(self.state["nodes"]) >= self.state["max_nodes"]:
                self.state["closed"] = True
                self.state["closure_reason"] = "max_nodes_reached ({})".format(self.state["max_nodes"])
                break
            if len(self.state["edges"]) >= self.state["max_edges"]:
                self.state["closed"] = True
                self.state["closure_reason"] = "max_edges_reached ({})".format(self.state["max_edges"])
                break

            layer_num = self.state["layer"]
            layer_result = self._radiate_bnd_recursive(layer_num, threshold, use_bnq_probe)
            layers.append(layer_result)

            if layer_result["bnd_count"] == 0:
                self.state["closed"] = True
                self.state["closure_reason"] = "no_bnd at layer {}".format(layer_num)
                break

            if layer_result["valid_bnd_count"] == 0:
                self.state["closed"] = True
                self.state["closure_reason"] = "no_valid_bnd at layer {}".format(layer_num)
                break

            self.state["layer"] += 1
            self.state["total_layers"] += 1

        if self.state["layer"] >= max_depth and not self.state["closed"]:
            self.state["closed"] = True
            self.state["closure_reason"] = "max_depth_reached"

        # Mark all remaining frontier nodes as closed
        for node in self.state["nodes"]:
            if node["state"] == "frontier":
                node["state"] = "closed"

        result = {
            "seed": self.state["seed"],
            "closed": self.state["closed"],
            "closure_reason": self.state["closure_reason"],
            "total_layers": self.state["total_layers"],
            "total_bnq": self.state["total_bnq"],
            "total_bnd": self.state["total_bnd"],
            "total_restricted": self.state["total_restricted"],
            "total_traversed": self.state["total_traversed"],
            "total_nodes": len(self.state["nodes"]),
            "total_edges": len(self.state["edges"]),
            "layers": layers,
        }
        self.state["last_result"] = result
        self._p("result", result)

        return (1, result, None)

    def cmd_frontier(self, params):
        """Export all BNQ + BND across all nodes, grouped by node."""
        if not self.state["nodes"]:
            return (0, None, ("BND_NO_GRAPH", "no graph exists", 0))

        frontier = {}
        for node in self.state["nodes"]:
            node_name = node["name"]
            node_bnq = [b for b in self.state["bnq_nodes"] if b["parent_name"] == node_name]
            node_bnd = [e for e in self.state["bnd_edges"] if e["from_node"] == node_name]
            if node_bnq or node_bnd:
                frontier[node_name] = {
                    "bnq": [{"text": b["text"], "layer": b["layer"], "answered": b["answered"]} for b in node_bnq],
                    "bnd": [{"to": e["to_node"], "type": e["direction_type"], "score": e["score"], "traversed": e["traversed"], "layer": e["layer"]} for e in node_bnd],
                }

        return (1, {
            "seed": self.state["seed"],
            "total_nodes_with_frontier": len(frontier),
            "frontier": frontier,
        }, None)

    def cmd_closure(self, params):
        """Check if graph is saturated."""
        return (1, {
            "closed": self.state["closed"],
            "closure_reason": self.state["closure_reason"],
            "total_bnq": self.state["total_bnq"],
            "total_bnd": self.state["total_bnd"],
            "total_layers": self.state["total_layers"],
            "threshold": self.state["threshold"],
        }, None)

    def cmd_graph(self, params):
        """Return graph as text — nodes, edges, layers, visual."""
        if not self.state["nodes"]:
            return (0, None, ("BND_NO_GRAPH", "no graph exists", 0))

        fmt = params.get("format", "text")
        if fmt == "json":
            return (1, {
                "nodes": self.state["nodes"],
                "edges": self.state["edges"],
                "bnq_nodes": self.state["bnq_nodes"],
                "bnd_edges": self.state["bnd_edges"],
            }, None)

        text = self.build_graph_text()
        return (1, {"graph_text": text, "node_count": len(self.state["nodes"]), "edge_count": len(self.state["edges"])}, None)

    # ── Core: Cluster ──

    def cluster_seed(self, seed):
        """Level 1: Expand seed (question or word) into concept space. Templates only.

        If seed is a question, extract key concepts from the question text.
        If seed is a word, expand into compound concepts.
        """
        cluster = []
        seed_lower = seed.lower()

        # If seed is a question, extract key words as cluster items
        if "?" in seed or len(seed.split()) > 3:
            # Extract meaningful words from the question
            stop_words = {"what", "how", "why", "when", "where", "who", "is", "are", "the", "a", "an", "of", "to", "in", "on", "for", "do", "does", "can", "could", "should", "would", "will", "about", "with", "that", "this", "it", "its", "and", "or", "but", "if", "then"}
            words = [w.strip("?,.!\"'").lower() for w in seed.split()]
            key_words = [w for w in words if w and w not in stop_words and len(w) > 2]
            for w in key_words:
                if w not in cluster:
                    cluster.append(w)
                # Add compound forms
                for suffix in ("_engine", "_graph", "_node", "_storage", "_validation", "_scoring", "_restriction", "_closure", "_input", "_output"):
                    compound = "{}{}".format(w, suffix)
                    if compound not in cluster and len(cluster) < self.state["cluster_size"]:
                        cluster.append(compound)
        else:
            # Single word seed — use angle-based expansion
            for angle in CLUSTER_ANGLES:
                item = self._cluster_item(seed, angle)
                if item and item not in cluster:
                    cluster.append(item)
            compounds = [
                "{}_engine".format(seed_lower), "{}_graph".format(seed_lower),
                "{}_node".format(seed_lower), "{}_edge".format(seed_lower),
                "{}_storage".format(seed_lower), "{}_validation".format(seed_lower),
                "{}_scoring".format(seed_lower), "{}_restriction".format(seed_lower),
                "{}_closure".format(seed_lower), "{}_input".format(seed_lower),
                "{}_output".format(seed_lower), "{}_lifecycle".format(seed_lower),
                "{}_failure".format(seed_lower), "{}_boundary".format(seed_lower),
                "{}_state".format(seed_lower),
            ]
            for c in compounds:
                if c not in cluster and len(cluster) < self.state["cluster_size"]:
                    cluster.append(c)

        return cluster[:self.state["cluster_size"]]

    def _cluster_item(self, seed, angle):
        """Generate a cluster item for a given angle."""
        templates = {
            "meaning": "what_{}_means".format(seed.lower()),
            "subdomain": "{}_subdomain".format(seed.lower()),
            "function": "{}_function".format(seed.lower()),
            "component": "{}_component".format(seed.lower()),
            "edge_case": "{}_edge_case".format(seed.lower()),
            "related_system": "{}_related".format(seed.lower()),
            "input": "{}_input".format(seed.lower()),
            "output": "{}_output".format(seed.lower()),
            "dependency": "{}_depends_on".format(seed.lower()),
            "constraint": "{}_constraint".format(seed.lower()),
            "failure_mode": "{}_failure_mode".format(seed.lower()),
            "validation": "{}_validation".format(seed.lower()),
            "storage": "{}_storage".format(seed.lower()),
            "interface": "{}_interface".format(seed.lower()),
            "lifecycle": "{}_lifecycle".format(seed.lower()),
        }
        return templates.get(angle, "{}_{}".format(seed.lower(), angle))

    # ── Core: BND-recursive radiation ──

    def _radiate_bnd_recursive(self, layer_num, threshold, use_bnq_probe):
        """Run one BND-recursive radiation layer.

        BND generates BND directly from each frontier node.
        Feed-forward: node is consumed (visited) after generating BNDs.
        BNQ is optional probe — if use_bnq_probe, questions expand frontier first.
        Each traversed BND's target becomes a new node that generates more BNDs next layer.
        """
        # Get frontier nodes at current layer (feed-forward: only unvisited/frontier nodes)
        frontier = [n for n in self.state["nodes"] if n["state"] in ("frontier", "unvisited") and n["layer"] == layer_num]

        if not frontier and layer_num == 0:
            frontier = [n for n in self.state["nodes"] if n["layer"] == 0]

        # ── Optional BNQ probe (expansion function, not driver) ──
        bnq_generated = []
        if use_bnq_probe:
            for node in frontier:
                bnqs = self.generate_bnq(node["name"], layer_num)
                for q_text in bnqs:
                    bnq = {
                        "id": self._next_node_id(),
                        "text": q_text,
                        "layer": layer_num,
                        "parent_name": node["name"],
                        "state": "probe",
                        "score": 0.0,
                        "answer": "",
                        "answered": False,
                    }
                    self.state["bnq_nodes"].append(bnq)
                    bnq_generated.append(bnq)
                    self.state["total_bnq"] += 1
                    q_hash = hash(q_text.lower())
                    if q_hash in self.state["visited_hashes"]:
                        bnq["state"] = "closed"
                        bnq["answer"] = "duplicate"
                        bnq["answered"] = True
                    else:
                        self.state["visited_hashes"].append(q_hash)

        # ── BND generation (recursive operator) ──
        # Batch: ONE LLM call for all frontier nodes in this layer.
        bnd_generated = []
        node_names = [n["name"] for n in frontier]
        batch_directions = self.generate_bnd_batch(node_names, layer_num)

        for i, node in enumerate(frontier):
            bnds = batch_directions[i] if i < len(batch_directions) else []
            for bnd_data in bnds:
                edge = {
                    "id": self._next_edge_id(),
                    "from_node": node["name"],
                    "to_node": bnd_data["to_node"],
                    "direction_type": bnd_data["direction_type"],
                    "layer": layer_num,
                    "score": 0.0,
                    "restricted": False,
                    "restriction_reason": "",
                    "traversed": False,
                    "source_bnq": "",
                    "source": bnd_data.get("source", "template"),
                    "real_name": bnd_data.get("real_name", bnd_data["to_node"]),
                }

                edge["score"] = self.score_edge(edge, layer_num)
                restricted, reason = self.restrict(edge)
                edge["restricted"] = restricted
                edge["restriction_reason"] = reason
                if restricted:
                    self.state["total_restricted"] += 1

                self.state["bnd_edges"].append(edge)
                self.state["edges"].append(edge)
                bnd_generated.append(edge)
                self.state["total_bnd"] += 1

            # Feed-forward: mark node as consumed (visited). Cannot generate again.
            node["state"] = "visited"

        # ── Select valid BNDs (score >= threshold, not restricted) ──
        valid_bnd = [e for e in bnd_generated if not e["restricted"] and e["score"] >= threshold]
        if len(valid_bnd) > self.state["max_bnd_per_layer"]:
            valid_bnd = sorted(valid_bnd, key=lambda e: e["score"], reverse=True)[:self.state["max_bnd_per_layer"]]

        # ── Traverse: each valid BND's target becomes new node (BND generates BND) ──
        for edge in valid_bnd:
            edge["traversed"] = True
            self.state["total_traversed"] += 1

            to_hash = hash(edge["to_node"].lower())
            if to_hash not in self.state["visited_hashes"]:
                self._add_node(edge["to_node"], layer=layer_num + 1, node_type=edge["direction_type"])
                self.state["visited_hashes"].append(to_hash)

        return {
            "layer": layer_num,
            "frontier_count": len(frontier),
            "bnq_count": len(bnq_generated),
            "bnd_count": len(bnd_generated),
            "valid_bnd_count": len(valid_bnd),
            "traversed_count": sum(1 for e in valid_bnd if e["traversed"]),
            "restricted_count": sum(1 for e in bnd_generated if e["restricted"]),
            "top_score": max((e["score"] for e in valid_bnd), default=0.0),
        }

    # ── Core: BNQ generation (optional probe) ──

    def generate_bnd_from_node(self, node_name, layer):
        """Generate BNDs directly from a single node (fallback, non-batched)."""
        return self.generate_bnd_batch([node_name], layer)[0]

    def generate_bnd_batch(self, node_names, layer):
        """Generate BNDs for multiple nodes. Uses MySQL knowledge base for real concepts.

        Queries vb_classes, vb_methods, learned_rules, know_problems.
        Real class names and method names become real BND targets.
        Falls back to templates if DB unavailable.
        """
        if not node_names:
            return []

        all_directions = []
        for name in node_names:
            directions = []
            node_lower = name.lower()
            # Extract key word from node name (strip prefixes like build_, implement_, etc)
            key_word = node_lower
            for prefix in ("build_", "implement_", "validate_", "constrain_", "split_", "decompose_", "break_", "expand_", "radiate_", "go_", "implement_implement_", "implement_"):
                if key_word.startswith(prefix):
                    key_word = key_word[len(prefix):]
                    break

            # Also try extracting meaningful words from messy node names
            # e.g. "implement_solution_feature_add_dominion" -> "dominion"
            words = node_lower.split("_")
            meaningful = [w for w in words if len(w) > 3 and w not in ("implement", "solution", "feature", "method", "build", "validate", "constrain", "split", "decompose", "break", "expand", "radiate", "yourself", "directly", "command", "equivalent", "option", "skip", "output")]
            if meaningful and len(meaningful[0]) > 3:
                key_word = meaningful[0]

            # Query DB for real classes matching this concept
            classes = _db_find_classes(key_word, limit=5)
            for cls in classes:
                to_node = cls.lower().replace(" ", "_")
                if hash(to_node.lower()) not in self.state["visited_hashes"]:
                    directions.append({"to_node": to_node, "direction_type": "decomposition", "source": "db_class", "real_name": cls})

            # Query DB for real methods matching this concept
            methods = _db_find_methods(key_word, limit=5)
            for method in methods:
                to_node = method.lower().replace(" ", "_")
                if hash(to_node.lower()) not in self.state["visited_hashes"]:
                    directions.append({"to_node": to_node, "direction_type": "expansion", "source": "db_method", "real_name": method})

            # Query DB for real rules matching this concept
            rules = _db_find_rules(key_word, limit=3)
            for pattern, fix_action, confidence in rules:
                if fix_action and "requirement" in fix_action.lower():
                    dtype = "implementation_shift"
                elif "prohibition" in fix_action.lower():
                    dtype = "constraint_tightening"
                elif "bug" in fix_action.lower() or "fix" in fix_action.lower():
                    dtype = "validation_shift"
                else:
                    dtype = "expansion"
                # Clean short name from pattern — first 5 meaningful words
                words = pattern.split()[:5]
                to_node = "_".join(w.lower().strip(".,:;()") for w in words if len(w) > 2)
                if hash(to_node.lower()) not in self.state["visited_hashes"]:
                    directions.append({"to_node": to_node, "direction_type": dtype, "source": "db_rule", "real_name": pattern[:60]})

            # Query DB for real problems matching this concept
            problems = _db_find_problems(key_word, limit=3)
            for problem, description in problems:
                words = problem.split()[:4]
                to_node = "_".join(w.lower().strip(".,:;()") for w in words if len(w) > 2)
                if hash(to_node.lower()) not in self.state["visited_hashes"]:
                    directions.append({"to_node": to_node, "direction_type": "validation_shift", "source": "db_problem", "real_name": problem})

            # If DB gave us directions, use them. Otherwise fall back to templates.
            if not directions:
                if layer == 0:
                    for dtype in ("expansion", "decomposition"):
                        for template in BND_TEMPLATES.get(dtype, ()):
                            action = template.replace("{node}", name).split()[0].lower()
                            to_node = "{}_{}".format(action, node_lower)
                            if hash(to_node.lower()) not in self.state["visited_hashes"]:
                                directions.append({"to_node": to_node, "direction_type": dtype})
                elif layer == 1:
                    directions.append({"to_node": "implement_{}".format(node_lower), "direction_type": "implementation_shift"})
                    directions.append({"to_node": "constrain_{}".format(node_lower), "direction_type": "constraint_tightening"})
                else:
                    directions.append({"to_node": "validate_{}".format(node_lower), "direction_type": "validation_shift"})
                    directions.append({"to_node": "implement_{}".format(node_lower), "direction_type": "implementation_shift"})

            all_directions.append(directions)
        return all_directions

    def generate_bnq(self, node_name, layer):
        """Generate questions (BNQ) around a node. Templates only — no LLM."""
        questions = []
        for template in BNQ_TEMPLATES:
            q = template.replace("{node}", node_name)
            questions.append(q)
        if layer == 0:
            questions.append("What is the boundary of {}?".format(node_name))
            questions.append("What is inside {} vs outside?".format(node_name))
        elif layer > 2:
            questions.append("Is {} already resolved?".format(node_name))
            questions.append("Can {} be closed?".format(node_name))
        return questions

    # ── Core: BND generation ──

    def generate_bnd(self, bnq_text, from_node, layer):
        """Generate directions (BND) from a question. Templates only — no LLM."""
        directions = []
        bnq_lower = bnq_text.lower()
        if "what is" in bnq_lower or "what does" in bnq_lower:
            applicable = ("expansion", "decomposition")
        elif "how" in bnq_lower:
            applicable = ("expansion", "implementation_shift")
        elif "why" in bnq_lower:
            applicable = ("expansion",)
        elif "when" in bnq_lower or "where" in bnq_lower:
            applicable = ("expansion", "constraint_tightening")
        elif "what feeds" in bnq_lower or "what reads" in bnq_lower or "dependency" in bnq_lower or "depends" in bnq_lower:
            applicable = ("decomposition", "constraint_tightening")
        elif "restrict" in bnq_lower or "constraint" in bnq_lower or "limit" in bnq_lower:
            applicable = ("constraint_tightening",)
        elif "wrong" in bnq_lower or "fail" in bnq_lower:
            applicable = ("validation_shift", "constraint_tightening")
        elif "valid" in bnq_lower or "test" in bnq_lower or "verify" in bnq_lower:
            applicable = ("validation_shift",)
        elif "part" in bnq_lower or "component" in bnq_lower or "split" in bnq_lower:
            applicable = ("decomposition",)
        elif "implement" in bnq_lower or "build" in bnq_lower or "code" in bnq_lower:
            applicable = ("implementation_shift",)
        elif "before" in bnq_lower or "after" in bnq_lower:
            applicable = ("expansion", "implementation_shift")
        elif "boundary" in bnq_lower or "inside" in bnq_lower or "outside" in bnq_lower:
            applicable = ("constraint_tightening", "decomposition")
        elif "resolved" in bnq_lower or "closed" in bnq_lower:
            applicable = ("validation_shift",)
        elif "replace" in bnq_lower:
            applicable = ("decomposition", "implementation_shift")
        else:
            applicable = ("expansion",)

        for dtype in applicable:
            templates = BND_TEMPLATES.get(dtype, ())
            for template in templates:
                action = template.replace("{node}", from_node).split()[0].lower()
                to_node = "{}_{}".format(action, from_node.lower())
                directions.append({"to_node": to_node, "direction_type": dtype})
        return directions

    # ── Core: Scoring ──

    def score_edge(self, edge, layer):
        """Score an edge: information_gain + dependency_unlock + structural_progress + execution_closeness."""
        weights = self.state["score_weights"]

        # information_gain: deeper layers have less new info
        info_gain = max(0.0, 1.0 - (layer * 0.15))

        # dependency_unlock: implementation shifts unlock more
        dep_unlock = 0.5
        if edge["direction_type"] == "implementation_shift":
            dep_unlock = 0.9
        elif edge["direction_type"] == "decomposition":
            dep_unlock = 0.7
        elif edge["direction_type"] == "constraint_tightening":
            dep_unlock = 0.6
        elif edge["direction_type"] == "validation_shift":
            dep_unlock = 0.4
        elif edge["direction_type"] == "expansion":
            dep_unlock = 0.5

        # structural_progress: increases with layer depth (we're building structure)
        struct_progress = min(1.0, 0.3 + (layer * 0.1))

        # execution_closeness: implementation and validation are closer to executable
        exec_closeness = 0.5
        if edge["direction_type"] == "implementation_shift":
            exec_closeness = 0.95
        elif edge["direction_type"] == "validation_shift":
            exec_closeness = 0.85
        elif edge["direction_type"] == "constraint_tightening":
            exec_closeness = 0.7
        elif edge["direction_type"] == "decomposition":
            exec_closeness = 0.6
        elif edge["direction_type"] == "expansion":
            exec_closeness = 0.4

        score = (
            weights["information_gain"] * info_gain
            + weights["dependency_unlock"] * dep_unlock
            + weights["structural_progress"] * struct_progress
            + weights["execution_closeness"] * exec_closeness
        )

        # Add small random factor for variety
        score += random.uniform(-0.02, 0.02)

        return round(max(0.0, min(1.0, score)), 4)

    # ── Core: Restriction ──

    def restrict(self, edge):
        """R = restriction layer. Returns (restricted, reason)."""
        # Structural: must reduce ambiguity, must move toward implementability
        if edge["score"] < 0.15:
            return (True, "structural: score too low")

        # Domain: stay within cluster (check if to_node is related to seed)
        seed_lower = self.state["seed"].lower()
        if seed_lower and seed_lower not in edge["to_node"].lower() and edge["layer"] > 3:
            # Allow some drift at higher layers but not too much
            if edge["layer"] > 5:
                return (True, "domain: too far from seed")

        # Progress: BNQ allowed only if unresolved, BND allowed only if path viable
        if edge["direction_type"] == "expansion" and edge["layer"] > 4:
            return (True, "progress: expansion blocked at deep layer — switch to implementation or validation")

        # Saturation: prevent infinite branching
        node_bnd_count = sum(1 for e in self.state["bnd_edges"] if e["from_node"] == edge["from_node"])
        if node_bnd_count > 10:
            return (True, "saturation: too many edges from this node")

        return (False, "")

    # ── Core: Graph building ──

    def _add_node(self, name, layer, node_type="concept"):
        node = {
            "id": self._next_node_id(),
            "name": name,
            "layer": layer,
            "type": node_type,
            "state": "frontier",
        }
        self.state["nodes"].append(node)
        return node

    def _next_node_id(self):
        self._node_counter += 1
        return self._node_counter

    def _next_edge_id(self):
        self._edge_counter += 1
        return self._edge_counter

    # ── Visualization ──

    def build_graph_text(self):
        """Build a text visualization of the graph."""
        lines = []
        lines.append("=" * 70)
        lines.append("BND RADIATION GRAPH")
        lines.append("Seed: {}".format(self.state["seed"]))
        lines.append("Closed: {} | Reason: {}".format(self.state["closed"], self.state["closure_reason"]))
        lines.append("Layers: {} | BNQ: {} | BND: {} | Restricted: {} | Traversed: {}".format(
            self.state["total_layers"], self.state["total_bnq"], self.state["total_bnd"],
            self.state["total_restricted"], self.state["total_traversed"]))
        lines.append("Nodes: {} | Edges: {}".format(len(self.state["nodes"]), len(self.state["edges"])))
        lines.append("=" * 70)

        # Cluster
        lines.append("")
        lines.append("LEVEL 1 — CLUSTER")
        lines.append("-" * 40)
        for i, item in enumerate(self.state["cluster"]):
            lines.append("  [{}] {}".format(i, item))

        # Layers
        max_layer = max((n["layer"] for n in self.state["nodes"]), default=0)
        for layer in range(max_layer + 1):
            lines.append("")
            lines.append("LAYER {} — RADIATION".format(layer))
            lines.append("-" * 40)

            layer_nodes = [n for n in self.state["nodes"] if n["layer"] == layer]
            layer_bnq = [b for b in self.state["bnq_nodes"] if b["layer"] == layer]
            layer_bnd = [e for e in self.state["bnd_edges"] if e["layer"] == layer]

            lines.append("  Nodes ({}):".format(len(layer_nodes)))
            for n in layer_nodes:
                lines.append("    [{}] {} ({}) state={}".format(n["id"], n["name"], n["type"], n["state"]))

            lines.append("  BNQ ({}):".format(len(layer_bnq)))
            for b in layer_bnq:
                status = "ANSWERED: {}".format(b["answer"]) if b["answered"] else "OPEN"
                lines.append("    Q{}: {} [score={:.2f}] {}".format(b["id"], b["text"], b["score"], status))

            lines.append("  BND ({}):".format(len(layer_bnd)))
            for e in layer_bnd:
                r_marker = " [RESTRICTED: {}]".format(e["restriction_reason"]) if e["restricted"] else ""
                t_marker = " [TRAVERSED]" if e["traversed"] else ""
                lines.append("    E{}: {} -> {} ({}) score={:.4f}{}{}".format(
                    e["id"], e["from_node"], e["to_node"], e["direction_type"],
                    e["score"], r_marker, t_marker))

        # Closure
        lines.append("")
        lines.append("=" * 70)
        lines.append("CLOSURE: {} | {}".format(self.state["closed"], self.state["closure_reason"]))
        lines.append("Pattern: bnq -> bnd -> bnq -> bnq -> done")
        lines.append("=" * 70)

        return "\n".join(lines)
