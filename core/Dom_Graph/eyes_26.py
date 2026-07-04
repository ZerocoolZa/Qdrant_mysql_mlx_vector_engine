# [@GHOST]{[@file<eyes_26.py>][@domain<Dom_Graph>][@role<analysis>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<graph_engine>][@return<dict>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{26 Eyes — multi-dimensional bracket packet inspection engine, 26 perspectives on code graph}
# [@WCL]{[@self_contained<true>][@eyes<26>][@engine<GhostBracket>][@dispatcher<Eyes26>]}

import re
import numpy as np
from collections import defaultdict
import copy

class GhostBracket:
    def __init__(self, bracket_packet=None, ghost_metadata=None):
        self.root = self.parse_bracket_packet(bracket_packet) if bracket_packet else None
        self.nodes = []
        self.token_sequence = []
        self.adj_matrix = None
        self.adj_list = {}
        self.feature_vectors = []
        self.event_log = []
        self.embeddings = {}
        self.hypergraph_layers = {}
        self.sibling_map = {}
        self.depth_map = {}
        self.semantic_roles = {}
        self.constraints = {}
        self.temporal_log = []
        self.ghost_metadata = ghost_metadata or {}

        # Max++ perspectives
        self.cross_layer_dependencies = defaultdict(list)
        self.aggregate_metrics = {}
        self.change_impact = defaultdict(list)

        # New ultimate perspectives
        self.full_paths = {}
        self.leaf_nodes = []
        self.subtree_snapshots = {}
        self.parent_map = {}
        self.change_risk = {}
        self.flattened_metadata = {}

        if self.root:
            self.collect_nodes(self.root)

    class BracketNode:
        def __init__(self, label, metadata=None):
            self.label = label
            self.children = []
            self.parent = None
            self.metadata = metadata or {}
            self.locked = False

        def add_child(self, child):
            child.parent = self
            self.children.append(child)

        def Run(self, command, params=None):
            return (0, None, ("unknown_command", command, 0))

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)

    # ---------------- Parsing ----------------
    def parse_bracket_packet(self, s):
        tokens = re.findall(r'\[|\]|[^\[\]]+', s)
        stack = []
        root = None
        current_node = None
        for tok in tokens:
            if tok == '[':
                continue
            elif tok == ']':
                if stack:
                    stack.pop()
                    current_node = stack[-1] if stack else None
            else:
                node = self.BracketNode(tok)
                if current_node:
                    current_node.add_child(node)
                else:
                    root = node
                stack.append(node)
                current_node = node
        return root

    # ---------------- Node collection ----------------
    def collect_nodes(self, node, path=None):
        path = path or []
        self.nodes.append(node)
        self.token_sequence.append(node.label)

        # Depth map
        depth = self.get_depth(node)
        self.depth_map.setdefault(depth, []).append(node)

        # Sibling map
        if node.parent:
            self.sibling_map.setdefault(node.parent.label, []).append(node)

        # Parent map
        if node.parent:
            self.parent_map[node.label] = node.parent

        # Full path
        full_path = path + [node.label]
        self.full_paths[node.label] = full_path

        # Leaf nodes
        if not node.children:
            self.leaf_nodes.append(node)

        # Flattened metadata
        self.flattened_metadata[node.label] = copy.deepcopy(node.metadata)

        for c in node.children:
            self.collect_nodes(c, full_path)

        # Subtree snapshot
        self.subtree_snapshots[node.label] = self.snapshot_subtree(node)

    def snapshot_subtree(self, node):
        return copy.deepcopy(node)

    # ---------------- Traversals ----------------
    def traverse_top_down(self, node=None):
        node = node or self.root
        yield node
        for c in node.children:
            yield from self.traverse_top_down(c)

    def traverse_bottom_up(self, node=None):
        node = node or self.root
        for c in node.children:
            yield from self.traverse_bottom_up(c)
        yield node

    # ---------------- Graph / adjacency ----------------
    def build_adj_matrix(self):
        n = len(self.nodes)
        self.adj_matrix = np.zeros((n, n), dtype=int)
        node_index = {node: i for i, node in enumerate(self.nodes)}
        for i, node in enumerate(self.nodes):
            for c in node.children:
                j = node_index[c]
                self.adj_matrix[i][j] = 1
        return self.adj_matrix

    def build_adj_list(self):
        self.adj_list = {node.label: [c.label for c in node.children] for node in self.nodes}
        return self.adj_list

    # ---------------- Feature Vectors ----------------
    def build_feature_vectors(self):
        self.feature_vectors = []
        for node in self.nodes:
            fv = {
                'label_len': len(node.label),
                'num_children': len(node.children),
                'depth': self.get_depth(node),
                'metadata_keys': len(node.metadata),
                'locked': node.locked
            }
            self.feature_vectors.append(fv)
        return self.feature_vectors

    # ---------------- Depth / sibling helpers ----------------
    def get_depth(self, node):
        depth = 0
        while node.parent:
            node = node.parent
            depth += 1
        return depth

    def get_siblings(self, node):
        return node.parent.children if node.parent else []

    # ---------------- Pointers / cross-references ----------------
    def find_node_by_label(self, label):
        return [n for n in self.nodes if n.label == label]

    # ---------------- Event / Temporal log ----------------
    def log_event(self, action, node):
        self.event_log.append({'action': action, 'node': node.label})
        self.temporal_log.append({'action': action, 'node': node.label})
        self.update_change_impact(node, action)
        self.update_change_risk(node)

    # ---------------- Hypergraph layers ----------------
    def assign_layer(self, layer_name, node):
        self.hypergraph_layers.setdefault(layer_name, []).append(node)

    # ---------------- Embeddings ----------------
    def set_embedding(self, node, vector):
        self.embeddings[node.label] = vector

    # ---------------- Semantic / role classification ----------------
    def classify_semantic_role(self, node, role):
        self.semantic_roles[node.label] = role

    # ---------------- Constraints ----------------
    def add_constraint(self, node, constraint):
        self.constraints.setdefault(node.label, []).append(constraint)

    # ---------------- Tensor / 3D array ----------------
    def to_tensor(self):
        max_depth = max(self.get_depth(n) for n in self.nodes) + 1
        max_children = max(len(n.children) for n in self.nodes) + 1
        tensor = np.zeros((max_depth, max_children, 3))
        for n in self.nodes:
            d = self.get_depth(n)
            for i, c in enumerate(n.children):
                tensor[d, i, 0] = len(c.label)
                tensor[d, i, 1] = len(c.metadata)
                tensor[d, i, 2] = len(c.children)
        return tensor

    # ---------------- Ghost Lock / Unlock ----------------
    def lock_node(self, node):
        node.locked = True
        self.log_event('lock', node)

    def unlock_node(self, node):
        node.locked = False
        self.log_event('unlock', node)

    # ---------------- Scaffold ----------------
    def scaffold_node(self, parent_node, label, metadata=None):
        node = self.BracketNode(label, metadata)
        parent_node.add_child(node)
        self.nodes.append(node)
        self.token_sequence.append(node.label)
        self.collect_nodes(node)
        self.log_event('scaffold', node)
        return node

    # ---------------- Validation ----------------
    def validate_bracket_law(self):
        violations = [node.label for node in self.nodes if '[' in node.label or ']' in node.label]
        return violations

    # ---------------- Bidirectional Conversion ----------------
    def code_to_brackets(self, code_structure, parent_node=None):
        if parent_node is None:
            parent_node = self.root or self.BracketNode("Root")
            if self.root is None:
                self.root = parent_node
                self.nodes.append(parent_node)
        for k, v in code_structure.items():
            node = self.BracketNode(k)
            parent_node.add_child(node)
            self.nodes.append(node)
            self.token_sequence.append(node.label)
            self.collect_nodes(node)
            if isinstance(v, dict):
                self.code_to_brackets(v, node)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        self.code_to_brackets(item, node)
                    else:
                        n = self.BracketNode(str(item))
                        node.add_child(n)
                        self.nodes.append(n)
                        self.token_sequence.append(n.label)
                        self.collect_nodes(n)
            else:
                n = self.BracketNode(str(v))
                node.add_child(n)
                self.nodes.append(n)
                self.token_sequence.append(n.label)
                self.collect_nodes(n)

    def brackets_to_code(self, node=None):
        node = node or self.root
        if not node.children:
            return node.label
        code_dict = {}
        for c in node.children:
            code_dict[c.label] = self.brackets_to_code(c) if c.children else c.label
        return code_dict

    # ---------------- Normal code / human-readable ----------------
    def to_normal_code(self, node=None, indent=0):
        node = node or self.root
        spacer = "    " * indent
        lines = [f"{spacer}{node.label}"]
        for c in node.children:
            lines.append(self.to_normal_code(c, indent + 1))
        return "\n".join(lines)

    # ---------------- Max+++ new perspectives ----------------
    def update_cross_layer_dependency(self, node, depends_on_labels):
        self.cross_layer_dependencies[node.label].extend(depends_on_labels)

    def compute_aggregate_metrics(self):
        metrics = {}
        total_descendants = lambda n: sum(total_descendants(c) + 1 for c in n.children)
        for node in self.nodes:
            metrics[node.label] = {
                'descendants': total_descendants(node),
                'leaves': sum(1 for c in node.children if not c.children),
                'depth': self.get_depth(node),
                'locked': node.locked
            }
        self.aggregate_metrics = metrics
        return metrics

    def update_change_impact(self, node, action):
        affected = [n.label for n in self.nodes if node in n.children or node == n]
        self.change_impact[node.label].append({'action': action, 'affected': affected})


    def update_change_risk(self, node):
        impacted_count = len(self.change_impact.get(node.label, []))
        self.change_risk[node.label] = impacted_count

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


# ------------------------------------------------------------------------
# Eyes: Multi-perspective inspection classes for GhostBracket

class EyeBase:
    eye_id = 0
    eye_name = "base"

    def inspect(self, engine: GhostBracket):
        raise NotImplementedError

    def packet(self, engine: GhostBracket):
        return {
            "eye_id": self.eye_id,
            "eye_name": self.eye_name,
            "result": self.inspect(engine),
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye01Tree(EyeBase):
    eye_id = 1
    eye_name = "tree"

    def inspect(self, engine: GhostBracket):
        return {
            "root": engine.root.label if engine.root else None,
            "node_count": len(engine.nodes),
            "child_map": {n.label: [c.label for c in n.children] for n in engine.nodes},
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye02Token(EyeBase):
    eye_id = 2
    eye_name = "token"

    def inspect(self, engine: GhostBracket):
        return {
            "count": len(engine.token_sequence),
            "sequence": list(engine.token_sequence),
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye03Depth(EyeBase):
    eye_id = 3
    eye_name = "depth"

    def inspect(self, engine: GhostBracket):
        return {
            "levels": {depth: [n.label for n in nodes] for depth, nodes in engine.depth_map.items()},
            "max_depth": max(engine.depth_map.keys()) if engine.depth_map else 0,
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye04Sibling(EyeBase):
    eye_id = 4
    eye_name = "sibling"

    def inspect(self, engine: GhostBracket):
        return {
            parent: [n.label for n in siblings]
            for parent, siblings in engine.sibling_map.items()
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye05Parent(EyeBase):
    eye_id = 5
    eye_name = "parent"

    def inspect(self, engine: GhostBracket):
        return {label: parent.label for label, parent in engine.parent_map.items()}

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye06Path(EyeBase):
    eye_id = 6
    eye_name = "path"

    def inspect(self, engine: GhostBracket):
        return dict(engine.full_paths)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye07Leaf(EyeBase):
    eye_id = 7
    eye_name = "leaf"

    def inspect(self, engine: GhostBracket):
        return {
            "count": len(engine.leaf_nodes),
            "labels": [n.label for n in engine.leaf_nodes],
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye08Subtree(EyeBase):
    eye_id = 8
    eye_name = "subtree"

    def inspect(self, engine: GhostBracket):
        return {
            label: snapshot.label
            for label, snapshot in engine.subtree_snapshots.items()
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye09Adjacency(EyeBase):
    eye_id = 9
    eye_name = "adjacency"

    def inspect(self, engine: GhostBracket):
        matrix = engine.build_adj_matrix() if engine.nodes else np.zeros((0, 0), dtype=int)
        adj_list = engine.build_adj_list() if engine.nodes else {}
        return {
            "matrix_shape": list(matrix.shape),
            "adj_list": adj_list,
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye10Feature(EyeBase):
    eye_id = 10
    eye_name = "feature"

    def inspect(self, engine: GhostBracket):
        return engine.build_feature_vectors()

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye11Semantic(EyeBase):
    eye_id = 11
    eye_name = "semantic"

    def inspect(self, engine: GhostBracket):
        return dict(engine.semantic_roles)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye12Constraint(EyeBase):
    eye_id = 12
    eye_name = "constraint"

    def inspect(self, engine: GhostBracket):
        return dict(engine.constraints)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye13Embedding(EyeBase):
    eye_id = 13
    eye_name = "embedding"

    def inspect(self, engine: GhostBracket):
        return dict(engine.embeddings)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye14Hypergraph(EyeBase):
    eye_id = 14
    eye_name = "hypergraph"

    def inspect(self, engine: GhostBracket):
        return {
            layer: [n.label for n in nodes]
            for layer, nodes in engine.hypergraph_layers.items()
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye15CrossLayer(EyeBase):
    eye_id = 15
    eye_name = "cross_layer"

    def inspect(self, engine: GhostBracket):
        return dict(engine.cross_layer_dependencies)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye16Event(EyeBase):
    eye_id = 16
    eye_name = "event"

    def inspect(self, engine: GhostBracket):
        return list(engine.event_log)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye17Temporal(EyeBase):
    eye_id = 17
    eye_name = "temporal"

    def inspect(self, engine: GhostBracket):
        return list(engine.temporal_log)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye18Lock(EyeBase):
    eye_id = 18
    eye_name = "lock"

    def inspect(self, engine: GhostBracket):
        return {n.label: n.locked for n in engine.nodes}

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye19Scaffold(EyeBase):
    eye_id = 19
    eye_name = "scaffold"

    def inspect(self, engine: GhostBracket):
        return {
            "scaffoldable": [n.label for n in engine.nodes],
            "root_exists": engine.root is not None,
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye20Validation(EyeBase):
    eye_id = 20
    eye_name = "validation"

    def inspect(self, engine: GhostBracket):
        return {
            "violations": engine.validate_bracket_law(),
            "ok": len(engine.validate_bracket_law()) == 0,
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye21CodeToBracket(EyeBase):
    eye_id = 21
    eye_name = "code_to_bracket"

    def inspect(self, engine: GhostBracket):
        return {
            "available": hasattr(engine, "code_to_brackets"),
            "root": engine.root.label if engine.root else None,
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye22BracketToCode(EyeBase):
    eye_id = 22
    eye_name = "bracket_to_code"

    def inspect(self, engine: GhostBracket):
        if not engine.root:
            return {}
        return engine.brackets_to_code()

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye23Tensor(EyeBase):
    eye_id = 23
    eye_name = "tensor"

    def inspect(self, engine: GhostBracket):
        if not engine.nodes:
            return {
                "shape": [0, 0, 0],
                "sum": 0.0,
            }
        tensor = engine.to_tensor()
        return {
            "shape": list(tensor.shape),
            "sum": float(np.sum(tensor)),
        }

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye24Metrics(EyeBase):
    eye_id = 24
    eye_name = "metrics"

    def inspect(self, engine: GhostBracket):
        return engine.compute_aggregate_metrics()

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye25Impact(EyeBase):
    eye_id = 25
    eye_name = "impact"

    def inspect(self, engine: GhostBracket):
        return dict(engine.change_impact)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eye26Risk(EyeBase):
    eye_id = 26
    eye_name = "risk"

    def inspect(self, engine: GhostBracket):
        return dict(engine.change_risk)

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Eyes26:
    def __init__(self):
        self.eyes = [
            Eye01Tree(),
            Eye02Token(),
            Eye03Depth(),
            Eye04Sibling(),
            Eye05Parent(),
            Eye06Path(),
            Eye07Leaf(),
            Eye08Subtree(),
            Eye09Adjacency(),
            Eye10Feature(),
            Eye11Semantic(),
            Eye12Constraint(),
            Eye13Embedding(),
            Eye14Hypergraph(),
            Eye15CrossLayer(),
            Eye16Event(),
            Eye17Temporal(),
            Eye18Lock(),
            Eye19Scaffold(),
            Eye20Validation(),
            Eye21CodeToBracket(),
            Eye22BracketToCode(),
            Eye23Tensor(),
            Eye24Metrics(),
            Eye25Impact(),
            Eye26Risk(),
        ]

    def inspect_all(self, engine: GhostBracket):
        return {eye.eye_name: eye.packet(engine) for eye in self.eyes}

    def inspect_one(self, engine: GhostBracket, eye_id: int):
        for eye in self.eyes:
            if eye.eye_id == eye_id:
                return eye.packet(engine)
        raise ValueError(f"Unknown eye_id: {eye_id}")

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)
