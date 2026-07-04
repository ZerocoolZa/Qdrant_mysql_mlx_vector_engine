# [@GHOST]{[@file<eyes_26_v1.py>][@domain<Dom_Graph>][@role<analysis>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<vision_engine>][@return<dict>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{3D Vision engine — original full bracket packet analyzer with 80 methods, CLI, tensor, embeddings}
# [@WCL]{[@self_contained<true>][@base<Vision3D>][@classes<6>]}

from __future__ import annotations

import ast
import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np

TORCH_AVAILABLE = False
TORCH_MPS_AVAILABLE = False
try:
    import torch

    TORCH_AVAILABLE = True
    TORCH_MPS_AVAILABLE = bool(torch.backends.mps.is_built() and torch.backends.mps.is_available())
except Exception:
    torch = None  # type: ignore[assignment]


def _sanitize_bracket_label(s: str) -> str:
    """
    Bracket_law doesn't define escaping. Keep labels readable and safe:
    - Strip
    - Remove '[' and ']'
    - Collapse whitespace
    """
    if s is None:
        return ""
    out = str(s).replace("[", "").replace("]", "").strip()
    out = re.sub(r"\s+", " ", out)
    return out


def python_code_to_bracket_packet(source: str, *, module_name: str = "<module>") -> str:
    """
    Convert Python code into a VBSTYLE bracket packet (AST-derived).
    This enables "3D vision" analysis for normal code via the same pipeline.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise BracketParseError(f"Python syntax error: {e}") from e

    def pack(label: str, children: Optional[List[str]] = None) -> str:
        lbl = _sanitize_bracket_label(label)
        if not lbl:
            lbl = "_"
        return "[" + lbl + ("".join(children or [])) + "]"

    def stmt_label(n: ast.AST) -> str:
        # Best-effort stable string; ast.unparse is available in modern Python.
        try:
            return ast.unparse(n)
        except Exception:
            return n.__class__.__name__

    imports: List[str] = []
    classes: List[str] = []
    functions: List[str] = []
    assignments: List[str] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(pack("Import", [pack(stmt_label(node))]))
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                bases.append(pack(_sanitize_bracket_label(stmt_label(b))))
            decos = []
            for d in node.decorator_list:
                decos.append(pack(_sanitize_bracket_label(stmt_label(d))))

            methods: List[str] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(pack("Method", _function_children(item)))

            doc = ast.get_docstring(node) or ""
            class_children = [
                pack("Name", [pack(node.name)]),
                pack("Bases", bases) if bases else pack("Bases"),
                pack("Decorators", decos) if decos else pack("Decorators"),
                pack("Docstring", [pack(_sanitize_bracket_label(doc))]) if doc else pack("Docstring"),
                pack("Methods", methods) if methods else pack("Methods"),
                pack("BodyStats", [pack(f"stmts={len(node.body)}")]),
            ]
            classes.append(pack("Class", class_children))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(pack("Function", _function_children(node)))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            assignments.append(pack("Assign", [pack(_sanitize_bracket_label(stmt_label(node)))]))
        else:
            # Keep other top-level statements summarized (prevents explosion).
            assignments.append(pack("Stmt", [pack(_sanitize_bracket_label(stmt_label(node)))]))

    root_children = [
        pack("Module", [pack("Name", [pack(module_name)])]),
        pack("Imports", imports) if imports else pack("Imports"),
        pack("Classes", classes) if classes else pack("Classes"),
        pack("Functions", functions) if functions else pack("Functions"),
        pack("TopLevel", assignments) if assignments else pack("TopLevel"),
    ]
    return pack("Python", root_children)


def _function_children(fn: ast.AST) -> List[str]:
    """
    Shared builder for (Async)FunctionDef nodes.
    """
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))

    def pack(label: str, children: Optional[List[str]] = None) -> str:
        lbl = _sanitize_bracket_label(label)
        if not lbl:
            lbl = "_"
        return "[" + lbl + ("".join(children or [])) + "]"

    def expr_str(n: ast.AST) -> str:
        try:
            return ast.unparse(n)
        except Exception:
            return n.__class__.__name__

    args = []
    for a in fn.args.posonlyargs:
        args.append(pack("Arg", [pack(a.arg)]))
    for a in fn.args.args:
        args.append(pack("Arg", [pack(a.arg)]))
    if fn.args.vararg is not None:
        args.append(pack("VarArg", [pack(fn.args.vararg.arg)]))
    for a in fn.args.kwonlyargs:
        args.append(pack("KwArg", [pack(a.arg)]))
    if fn.args.kwarg is not None:
        args.append(pack("KwVarArg", [pack(fn.args.kwarg.arg)]))

    decos = []
    for d in fn.decorator_list:
        decos.append(pack(_sanitize_bracket_label(expr_str(d))))

    doc = ast.get_docstring(fn) or ""
    returns = ""
    if getattr(fn, "returns", None) is not None:
        returns = expr_str(fn.returns)

    return [
        pack("Name", [pack(fn.name)]),
        pack("Decorators", decos) if decos else pack("Decorators"),
        pack("Args", args) if args else pack("Args"),
        pack("Returns", [pack(_sanitize_bracket_label(returns))]) if returns else pack("Returns"),
        pack("Docstring", [pack(_sanitize_bracket_label(doc))]) if doc else pack("Docstring"),
        pack("BodyStats", [pack(f"stmts={len(fn.body)}")]),
    ]


class BracketParseError(ValueError):
    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


class BracketValidationError(ValueError):
    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))

class Vision3D:
    """
    Parse + analyze a VBSTYLE bracket packet (or a file containing one).

    Backwards-compatibility:
    - Keeps class name and the original public method names.
    - `to_tensor()` still returns (depth, max_children, 3) by default.
    """

    def __init__(
        self,
        bracket_packet: str,
        *,
        strict: bool = True,
        extract_packet: bool = True,
        ghost_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.raw_input = bracket_packet
        self.strict = strict
        self.ghost_metadata: Dict[str, Any] = ghost_metadata or {}

        extracted = (
            self.extract_bracket_packet(bracket_packet, allow_fallback=not strict) if extract_packet else bracket_packet
        )
        self.bracket_packet = extracted

        self.governance_headers: List[str] = self.extract_governance_headers(bracket_packet)

        self.root = self.parse_bracket_packet(extracted, strict=strict)
        self.nodes = []
        self.token_sequence = []
        self.adj_matrix = None
        self.adj_list: Dict[int, List[int]] = {}
        self.feature_vectors = []
        self.event_log = []
        self.temporal_log = []  # same events as event_log, but named for "timeline" usage
        self.embeddings = {}
        self.hypergraph_layers = {}
        self.sibling_map: Dict[int, List[int]] = {}  # parent_id -> child_ids
        self.depth_map: Dict[int, List[int]] = {}  # depth -> node_ids
        self.semantic_roles: Dict[int, str] = {}  # node_id -> role string
        self.constraints: Dict[int, List[str]] = {}  # node_id -> list of constraints
        self.subtree_size_cache: Dict[int, int] = {}

        # Ultimate max+++ perspectives (ID-based; avoids label collision bugs)
        self.cross_layer_dependencies: Dict[int, List[int]] = {}  # node_id -> depends_on node_ids
        self.change_impact: Dict[int, List[Dict[str, Any]]] = {}  # node_id -> impact events
        self.change_risk: Dict[int, float] = {}  # node_id -> risk score (heuristic 0..1)
        self.aggregate_metrics: Dict[int, Dict[str, Any]] = {}  # node_id -> metrics snapshot

        self.parent_map: Dict[int, Optional[int]] = {}  # node_id -> parent_id
        self.full_paths: Dict[int, List[str]] = {}  # node_id -> lineage labels from root
        self.leaf_nodes: List[int] = []  # node_ids of leaves
        self.flattened_metadata: Dict[int, Dict[str, Any]] = {}  # node_id -> metadata copy
        self.subtree_snapshots: Dict[int, Dict[str, Any]] = {}  # node_id -> subtree dict snapshot
        self.last_layout_backend = "numpy"
        if self.root is not None:
            self.collect_nodes(self.root)

    def layout_backend_info() -> Dict[str, Any]:
        return {
            "torch_available": TORCH_AVAILABLE,
            "mps_available": TORCH_MPS_AVAILABLE,
            "preferred_backend": "mps" if TORCH_MPS_AVAILABLE else "numpy",
        }

    def active_layout_backend(self) -> str:
        return self.last_layout_backend

    @dataclasses.dataclass(eq=False)
    class Node:
        label: str
        metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
        children: List["Vision3D.Node"] = dataclasses.field(default_factory=list)
        parent: Optional["Vision3D.Node"] = None
        locked: bool = False

        # Assigned during `collect_nodes()`
        _id: Optional[int] = None

        def add_child(self, child: "Vision3D.Node") -> None:
            child.parent = self
            self.children.append(child)

        def path_labels(self) -> List[str]:
            out: List[str] = []
            cur: Optional["Vision3D.Node"] = self
            while cur is not None:
                out.append(cur.label)
                cur = cur.parent
            return list(reversed(out))

        def Run(self, command, params=None):
            return (0, None, ("unknown_command", command, 0))

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)

    # --- Parsing ---
    def _iter_tokens(packet: str) -> Iterator[str]:
        """
        Tokenizer for bracket packets.
        Yields "[", "]", or TEXT chunks between brackets.
        """
        buf: List[str] = []
        for ch in packet:
            if ch in "[]":
                if buf:
                    yield "".join(buf)
                    buf.clear()
                yield ch
            else:
                buf.append(ch)
        if buf:
            yield "".join(buf)

    def extract_governance_headers(text: str) -> List[str]:
        """
        Extract lines that look like governance headers (e.g. '#[Ghost{...}]' or '#[Something[...]]').
        Returns raw lines (trimmed). Never required for parsing the bracket packet.
        """
        headers: List[str] = []
        for line in text.splitlines()[:30]:  # keep it bounded
            ln = line.strip()
            if ln.startswith("#[") and ln.endswith("]") and len(ln) >= 4:
                headers.append(ln)
        return headers

    def extract_bracket_packet(cls, text: str, *, allow_fallback: bool = False) -> str:
        """
        Extract the first *complete* bracket packet from a larger text blob.
        - Prefers packets that begin at the start of a line (after whitespace), which is how your docs are written.
        - Skips governance/header packets of the form '#[ ... ]' when possible.
        - If multiple packets exist, prefers the longest non-header packet (usually the real body packet).
        - If a line-start packet exists but is unbalanced, raises (unless allow_fallback=True).
        """
        # Fast path: already looks like a packet
        s = text.strip()
        if s.startswith("[") and s.endswith("]"):
            # Still validate balancing.
            cls._validate_balanced(s)
            return s

        # 1) Prefer packets that start at the beginning of a line (after whitespace).
        line_start_positions: List[int] = []
        for m in re.finditer(r"(?m)^[ \t]*\[", text):
            # m.start() points at whitespace; find the bracket.
            pos = text.find("[", m.start(), m.end() + 1)
            if pos >= 0:
                # Skip '#[' headers
                if pos > 0 and text[pos - 1] == "#":
                    continue
                # Skip MSF-style packet envelopes like '[[PKT|...]]' and other double-bracket openers at line start.
                if (pos + 1) < len(text) and text[pos + 1] == "[":
                    if text.startswith("[[PKT|", pos) or text.startswith("[[ENDPKT", pos):
                        continue
                    # Generally, line-start packets in this system are single '[', not '[['.
                    continue
                line_start_positions.append(pos)

        def try_extract_at(start: int) -> Optional[str]:
            depth = 0
            in_packet = False
            for i in range(start, len(text)):
                ch = text[i]
                if ch == "[":
                    depth += 1
                    in_packet = True
                elif ch == "]" and in_packet:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1].strip()
                        cls._validate_balanced(candidate)
                        return candidate
                    if depth < 0:
                        return None
            return None

        if line_start_positions:
            extracted: List[str] = []
            unbalanced = 0
            for start in line_start_positions:
                try:
                    cand = try_extract_at(start)
                except BracketValidationError:
                    cand = None
                if cand is None:
                    unbalanced += 1
                else:
                    extracted.append(cand)
            if extracted:
                extracted.sort(key=len, reverse=True)
                return extracted[0]
            if not allow_fallback:
                # Diagnose the first line-start candidate for a helpful error message.
                start0 = line_start_positions[0]
                depth = 0
                under_at: Optional[int] = None
                for i, ch in enumerate(text[start0:], start=start0):
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                        if depth < 0:
                            under_at = i
                            break
                raise BracketValidationError(
                    "Found bracket packet(s) at start-of-line, but none were balanced/complete. "
                    + (
                        f"Bracket underflow near char {under_at}."
                        if under_at is not None
                        else f"This usually means the main packet is missing {depth} closing bracket(s)."
                    )
                )

        # 2) Fallback: scan any '[' occurrences and pick the best balanced candidate.
        bracket_starts = [m.start() for m in re.finditer(r"\[", text)]
        if not bracket_starts:
            raise BracketParseError("No '[' found; cannot extract bracket packet.")

        candidates: List[Tuple[bool, int, str]] = []
        # tuple: (is_header_like, length, candidate)
        for start in bracket_starts:
            # Heuristic: if immediately preceded by '#', treat as header-like.
            prev = text[start - 1] if start > 0 else ""
            # Also de-prioritize starts preceded by '[' (nested packets / '[[' envelopes).
            is_header_like = prev in "#["

            depth = 0
            in_packet = False
            for i in range(start, len(text)):
                ch = text[i]
                if ch == "[":
                    depth += 1
                    in_packet = True
                elif ch == "]" and in_packet:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1].strip()
                        try:
                            cls._validate_balanced(candidate)
                        except BracketValidationError:
                            break
                        candidates.append((is_header_like, len(candidate), candidate))
                        break
                    if depth < 0:
                        break

        if not candidates:
            raise BracketParseError("No complete bracket packet found.")

        non_header = [c for c in candidates if not c[0]]
        pick_from = non_header if non_header else candidates
        # Prefer the longest candidate (body packets are typically much larger than headers).
        pick_from.sort(key=lambda t: t[1], reverse=True)
        return pick_from[0][2]

    def _validate_balanced(packet: str) -> None:
        depth = 0
        for idx, ch in enumerate(packet):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth < 0:
                    raise BracketValidationError(f"Bracket underflow at char {idx}.")
        if depth != 0:
            raise BracketValidationError(f"Unbalanced brackets; depth={depth} at end.")

    def parse_bracket_packet(self, s: str, *, strict: bool = True) -> Optional["Vision3D.Node"]:
        """
        Parse a single bracket packet into a tree.
        Enforces the One Packet Rule by default.
        """
        if not isinstance(s, str):
            raise TypeError("bracket packet must be a string")
        packet = s.strip()
        if not packet:
            return None

        self.validate_balanced(packet)

        stack: List[Vision3D.Node] = []
        root: Optional[Vision3D.Node] = None
        current_node: Optional[Vision3D.Node] = None

        for tok in self.iter_tokens(packet):
            if tok == "[":
                continue
            if tok == "]":
                if not stack:
                    raise BracketParseError("Unexpected ']' with empty stack.")
                stack.pop()
                current_node = stack[-1] if stack else None
                continue

            # TEXT token
            label_raw = tok
            label = label_raw.strip()
            if not label:
                # Ignore pure whitespace between brackets (common in pretty-printed packets).
                continue

            node = self.Node(label=label)
            if current_node is not None:
                current_node.add_child(node)
            else:
                if root is not None and strict:
                    raise BracketValidationError("Multiple top-level roots detected (fragmented packet).")
                root = node

            stack.append(node)
            current_node = node

        if strict and stack:
            # Balanced check should prevent this, but keep the invariant explicit.
            raise BracketParseError("Parse ended with non-empty stack (unexpected).")

        if strict and root is None:
            raise BracketParseError("No root node parsed.")
        return root

    # --- Collect nodes + tokens ---
    def collect_nodes(self, node: "Vision3D.Node") -> None:
        """
        Iterative pre-order traversal (avoids recursion depth issues).
        Also assigns stable integer IDs to nodes.
        """
        self.nodes = []
        self.token_sequence = []
        self.depth_map = {}
        self.sibling_map = {}
        self.parent_map = {}
        self.full_paths = {}
        self.leaf_nodes = []
        self.flattened_metadata = {}
        self.subtree_snapshots = {}
        self.subtree_size_cache = {}
        self.adj_list = {}

        stack: List[Vision3D.Node] = [node]
        while stack:
            cur = stack.pop()
            cur._id = len(self.nodes)
            self.nodes.append(cur)
            self.token_sequence.append(cur.label)

            depth = self.get_depth(cur)
            self.depth_map.setdefault(depth, []).append(cur._id)
            if cur.parent is not None and cur.parent._id is not None:
                self.sibling_map.setdefault(cur.parent._id, []).append(cur._id)

            # Reverse hierarchy / lineage / leaf view / flattened metadata.
            self.parent_map[cur._id] = (cur.parent._id if cur.parent is not None else None)
            self.full_paths[cur._id] = cur.path_labels()
            if not cur.children:
                self.leaf_nodes.append(cur._id)
            self.flattened_metadata[cur._id] = dict(cur.metadata) if cur.metadata else {}

            # pre-order: push reversed children so natural order is preserved
            if cur.children:
                stack.extend(reversed(cur.children))

        # Build adjacency list for quick "horizontal view" usage.
        self.build_adj_list()

        # Refresh metrics snapshot after a re-index.
        self.compute_aggregate_metrics()

    # --- Traversals ---
    def traverse_top_down(self, node: Optional["Vision3D.Node"] = None) -> Iterator["Vision3D.Node"]:
        node = node or self.root
        if node is None:
            return
        yield node
        for c in node.children:
            yield from self.traverse_top_down(c)

    def traverse_bottom_up(self, node: Optional["Vision3D.Node"] = None) -> Iterator["Vision3D.Node"]:
        node = node or self.root
        if node is None:
            return
        for c in node.children:
            yield from self.traverse_bottom_up(c)
        yield node

    # --- Graph / adjacency matrix ---
    def build_adj_matrix(self, *, directed: bool = True) -> np.ndarray:
        n = len(self.nodes)
        self.adj_matrix = np.zeros((n, n), dtype=int)
        node_index = {node: i for i, node in enumerate(self.nodes)}  # object-identity map
        for i, node in enumerate(self.nodes):
            for c in node.children:
                j = node_index[c]
                self.adj_matrix[i][j] = 1
                if not directed:
                    self.adj_matrix[j][i] = 1
        return self.adj_matrix

    def build_adj_list(self) -> Dict[int, List[int]]:
        """
        Adjacency list using node IDs: {parent_id: [child_id, ...], ...}
        """
        out: Dict[int, List[int]] = {}
        for n in self.nodes:
            if n._id is None:
                continue
            out[n._id] = [c._id for c in n.children if c._id is not None]
        self.adj_list = out
        return out

    def edge_list(self) -> List[Tuple[int, int]]:
        """
        Returns (parent_id, child_id) edges using assigned node IDs.
        """
        edges: List[Tuple[int, int]] = []
        for n in self.nodes:
            if n._id is None:
                continue
            for c in n.children:
                if c._id is None:
                    continue
                edges.append((n._id, c._id))
        return edges

    # --- Feature vectors ---
    def build_feature_vectors(self) -> List[Dict[str, Any]]:
        self.feature_vectors = []
        for node in self.nodes:
            nid = -1 if node._id is None else node._id
            parent_id = -1
            if node.parent is not None and node.parent._id is not None:
                parent_id = int(node.parent._id)
            sib_index = -1
            sib_count = 0
            if parent_id >= 0:
                sibs = self.sibling_map.get(parent_id, [])
                sib_count = len(sibs)
                try:
                    sib_index = sibs.index(nid)
                except ValueError:
                    sib_index = -1
            fv = {
                'label_len': len(node.label),
                'num_children': len(node.children),
                'depth': self.get_depth(node),
                'metadata_keys': len(node.metadata),
                'is_leaf': 1 if not node.children else 0,
                'locked': 1 if node.locked else 0,
                'sibling_index': sib_index,
                'sibling_count': sib_count,
                'subtree_size': self.subtree_size(node),
                'constraints': len(self.constraints.get(nid, [])) if nid >= 0 else 0,
            }
            self.feature_vectors.append(fv)
        return self.feature_vectors

    def build_feature_matrix(self, *, fields: Sequence[str] = ("label_len", "num_children", "depth", "metadata_keys", "is_leaf")) -> np.ndarray:
        """
        Numeric feature matrix aligned to `self.nodes`.
        """
        if not self.feature_vectors:
            self.build_feature_vectors()
        mat = np.zeros((len(self.nodes), len(fields)), dtype=float)
        for i, fv in enumerate(self.feature_vectors):
            for j, k in enumerate(fields):
                mat[i, j] = float(fv.get(k, 0.0))
        return mat

    # --- Depth helper ---
    def get_depth(self, node: "Vision3D.Node") -> int:
        depth = 0
        while node.parent:
            node = node.parent
            depth += 1
        return depth

    # --- Pointers / cross-references ---
    def find_node_by_label(self, label: str) -> List["Vision3D.Node"]:
        return [n for n in self.nodes if n.label == label]

    def get_siblings(self, node: "Vision3D.Node") -> List["Vision3D.Node"]:
        if node.parent is None:
            return []
        return list(node.parent.children)

    # --- Event log ---
    def log_event(self, action: str, node: "Vision3D.Node", *, details: Optional[Dict[str, Any]] = None) -> None:
        evt = {
            "ts": _dt.datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "node": node.label,
            "node_id": node._id,
        }
        if details:
            evt["details"] = details
        self.event_log.append(evt)
        self.temporal_log.append(evt)
        if node._id is not None:
            self.update_change_impact_and_risk(int(node._id), action, evt)

    # --- Ghost lock / unlock ---
    def lock_node(self, node: "Vision3D.Node") -> None:
        node.locked = True
        self.log_event("lock", node)

    def unlock_node(self, node: "Vision3D.Node") -> None:
        node.locked = False
        self.log_event("unlock", node)

    # --- Hypergraph layers ---
    def assign_layer(self, layer_name: str, node: "Vision3D.Node") -> None:
        if layer_name not in self.hypergraph_layers:
            self.hypergraph_layers[layer_name] = []
        self.hypergraph_layers[layer_name].append(node)

    # --- Placeholder embeddings ---
    def set_embedding(self, node: "Vision3D.Node", vector: Sequence[float], *, key: str = "id") -> None:
        """
        Store an embedding.
        key="id" (default): uses stable node id if assigned.
        key="label": uses node.label (will collide if labels repeat).
        """
        if key == "id":
            if node._id is None:
                raise ValueError("node has no id; call collect_nodes() first")
            k = f"id:{node._id}"
        elif key == "label":
            k = f"label:{node.label}"
        else:
            raise ValueError("key must be 'id' or 'label'")
        self.embeddings[k] = list(vector)

    def get_embedding_hash(self, node: "Vision3D.Node", *, dim: int = 32, salt: str = "Vision3D") -> np.ndarray:
        """
        Deterministic embedding without external models:
        - Hash the node path into `dim` floats in [-1, 1].
        """
        path = "/".join(node.path_labels())
        h = hashlib.blake2b((salt + ":" + path).encode("utf-8"), digest_size=32).digest()
        # Expand to dim floats using repeated hashing (cheap, deterministic).
        out = np.zeros((dim,), dtype=float)
        cur = h
        i = 0
        while i < dim:
            for b in cur:
                if i >= dim:
                    break
                out[i] = (b / 127.5) - 1.0
                i += 1
            cur = hashlib.blake2b(cur, digest_size=32).digest()
        return out

    # --- Semantic roles / constraints ---
    def classify_semantic_role(self, node: "Vision3D.Node", role: str) -> None:
        if node._id is None:
            raise ValueError("node has no id; call collect_nodes() first")
        self.semantic_roles[int(node._id)] = role
        self.log_event("semantic_role", node, details={"role": role})

    def add_constraint(self, node: "Vision3D.Node", constraint: str) -> None:
        if node._id is None:
            raise ValueError("node has no id; call collect_nodes() first")
        nid = int(node._id)
        self.constraints.setdefault(nid, []).append(constraint)
        self.log_event("constraint_add", node, details={"constraint": constraint})

    # --- Scaffold ---
    def scaffold_child(self, parent: "Vision3D.Node", label: str, metadata: Optional[Dict[str, Any]] = None) -> "Vision3D.Node":
        """
        Safe scaffold helper: adds a new child node, then re-indexes/maps.
        """
        n = self.Node(label=label, metadata=metadata or {})
        parent.add_child(n)
        # Re-collect to assign IDs/mappings deterministically.
        if self.root is not None:
            self.collect_nodes(self.root)
        self.log_event("scaffold", n, details={"parent": parent.label})
        return n

    # --- Subtree size ---
    def subtree_size(self, node: "Vision3D.Node") -> int:
        """
        Number of nodes in the subtree rooted at node (including itself).
        Cached by node id.
        """
        if node._id is None:
            # Not indexed yet; compute recursively without caching.
            return 1 + sum(self.subtree_size(c) for c in node.children)
        nid = int(node._id)
        if nid in self.subtree_size_cache:
            return self.subtree_size_cache[nid]
        total = 1
        for c in node.children:
            total += self.subtree_size(c)
        self.subtree_size_cache[nid] = total
        return total

    # --- Cross-layer dependencies (max+++) ---
    def update_cross_layer_dependency(
        self,
        node: "Vision3D.Node",
        depends_on: Sequence["Vision3D.Node"] | Sequence[int],
    ) -> None:
        """
        Declare that `node` depends on other nodes across layers.
        Stored by node ID (safe when labels repeat).
        """
        if node._id is None:
            raise ValueError("node has no id; call collect_nodes() first")
        nid = int(node._id)
        dep_ids: List[int] = []
        for d in depends_on:
            if isinstance(d, int):
                dep_ids.append(d)
            else:
                if d._id is None:
                    raise ValueError("dependency node has no id; call collect_nodes() first")
                dep_ids.append(int(d._id))
        self.cross_layer_dependencies.setdefault(nid, [])
        for did in dep_ids:
            if did not in self.cross_layer_dependencies[nid]:
                self.cross_layer_dependencies[nid].append(did)
        self.log_event("xdep_update", node, details={"depends_on": dep_ids})

    def dependents_of(self, node_id: int) -> List[int]:
        """
        Reverse dependency lookup: list node_ids that depend on node_id.
        """
        out: List[int] = []
        for src, deps in self.cross_layer_dependencies.items():
            if node_id in deps:
                out.append(src)
        return out

    # --- Aggregate metrics / statistics (max+++) ---
    def compute_aggregate_metrics(self) -> Dict[int, Dict[str, Any]]:
        """
        Compute and store per-node metrics:
        - descendants, leaves_in_subtree, depth, lock
        - degree (in/out), constraints, roles
        - cross-layer dependencies + dependents
        """
        if not self.nodes:
            self.aggregate_metrics = {}
            return {}

        edges = self.edge_list()
        n_nodes = len(self.nodes)
        in_deg = [0] * n_nodes
        out_deg = [0] * n_nodes
        for a, b in edges:
            if 0 <= a < n_nodes and 0 <= b < n_nodes:
                out_deg[a] += 1
                in_deg[b] += 1

        leaf_set = set(self.leaf_nodes)
        leaves_in_subtree: Dict[int, int] = {}

        def rec(n: "Vision3D.Node") -> int:
            if n._id is None:
                return 0
            nid = int(n._id)
            if nid in leaves_in_subtree:
                return leaves_in_subtree[nid]
            if nid in leaf_set:
                leaves_in_subtree[nid] = 1
                return 1
            total = 0
            for c in n.children:
                total += rec(c)
            leaves_in_subtree[nid] = total
            return total

        if self.root is not None:
            rec(self.root)

        metrics: Dict[int, Dict[str, Any]] = {}
        for n in self.nodes:
            if n._id is None:
                continue
            nid = int(n._id)
            metrics[nid] = {
                "label": n.label,
                "depth": self.get_depth(n),
                "locked": bool(n.locked),
                "descendants": max(self.subtree_size(n) - 1, 0),
                "leaves_in_subtree": int(leaves_in_subtree.get(nid, 1 if not n.children else 0)),
                "in_degree": int(in_deg[nid]),
                "out_degree": int(out_deg[nid]),
                "degree": int(in_deg[nid] + out_deg[nid]),
                "constraint_count": int(len(self.constraints.get(nid, []))),
                "has_role": 1 if nid in self.semantic_roles else 0,
                "depends_on": list(self.cross_layer_dependencies.get(nid, [])),
                "dependents": self.dependents_of(nid) if self.cross_layer_dependencies else [],
            }
        self.aggregate_metrics = metrics
        return metrics

    # --- Subtree snapshots (max+++) ---
    def snapshot_subtree(self, node: "Vision3D.Node") -> Dict[str, Any]:
        """
        JSON-safe subtree snapshot (no parent pointers, no cycles).
        """
        def rec(n: "Vision3D.Node") -> Dict[str, Any]:
            return {
                "id": n._id,
                "label": n.label,
                "locked": bool(n.locked),
                "metadata": dict(n.metadata) if n.metadata else {},
                "children": [rec(c) for c in n.children],
            }

        snap = rec(node)
        if node._id is not None:
            self.subtree_snapshots[int(node._id)] = snap
        return snap

    def snapshot_all_subtrees(self, *, max_nodes: int = 5000) -> None:
        """
        Cache snapshots for all nodes (can be heavy on large trees).
        """
        if len(self.nodes) > max_nodes:
            raise ValueError(f"Refusing to snapshot {len(self.nodes)} nodes (limit {max_nodes}).")
        for n in self.nodes:
            self.snapshot_subtree(n)

    # --- Change impact propagation + risk scoring (max+++) ---
    def _descendants_ids(self, node_id: int) -> List[int]:
        out: List[int] = []
        q: List[int] = [node_id]
        while q:
            cur = q.pop()
            for c in self.adj_list.get(cur, []):
                out.append(c)
                q.append(c)
        return out

    def _ancestors_ids(self, node_id: int) -> List[int]:
        out: List[int] = []
        cur = node_id
        seen = set()
        while True:
            p = self.parent_map.get(cur)
            if p is None:
                break
            if p in seen:
                break
            out.append(p)
            seen.add(p)
            cur = p
        return out

    def _update_change_impact_and_risk(self, node_id: int, action: str, evt: Dict[str, Any]) -> None:
        descendants = self.descendants_ids(node_id)
        ancestors = self.ancestors_ids(node_id)
        deps = list(self.cross_layer_dependencies.get(node_id, []))
        dependents = self.dependents_of(node_id) if self.cross_layer_dependencies else []

        affected_set = set([node_id] + descendants + ancestors + deps + dependents)
        affected = sorted(affected_set)

        impact_evt = {"ts": evt.get("ts"), "action": action, "affected": affected}
        self.change_impact.setdefault(node_id, []).append(impact_evt)

        locked_weight = 0
        constraint_weight = 0
        for aid in affected:
            if 0 <= aid < len(self.nodes) and self.nodes[aid].locked:
                locked_weight += 3
            constraint_weight += len(self.constraints.get(aid, []))
        dep_weight = len(deps) + len(dependents)
        base = len(affected) + locked_weight + 2 * constraint_weight + 2 * dep_weight
        self.change_risk[node_id] = float(base) / float(base + 50.0)

    # --- Human-readable normal code view (max+++) ---
    def to_normal_code(self, node: Optional["Vision3D.Node"] = None, *, indent: int = 0) -> List[str]:
        """
        Indentation-based view of the hierarchy (no brackets).
        """
        node = node or self.root
        if node is None:
            return []
        spacer = "    " * indent
        lines = [f"{spacer}{node.label}"]
        for c in node.children:
            lines.extend(self.to_normal_code(c, indent=indent + 1))
        return lines

    # --- Tensor / 3D array export ---
    def to_tensor(self, *, channels: Sequence[str] = ("label_len", "metadata_keys", "num_children")) -> np.ndarray:
        """
        Depth x sibling-index x channel tensor.

        Backwards compatible default:
        - channel 0: child label_len
        - channel 1: child metadata_keys
        - channel 2: child num_children
        """
        if not self.nodes:
            return np.zeros((0, 0, len(channels)), dtype=float)

        max_depth = max(self.get_depth(n) for n in self.nodes) + 1
        max_children = max(len(n.children) for n in self.nodes) + 1
        tensor = np.zeros((max_depth, max_children, len(channels)), dtype=float)

        def _label_hash_u16(s: str) -> int:
            h = hashlib.blake2b(s.encode("utf-8"), digest_size=2).digest()
            return int.from_bytes(h, "little")

        def _role_id(nid: int) -> float:
            role = self.semantic_roles.get(nid, "")
            if not role:
                return 0.0
            return float(_label_hash_u16(role))

        def channel_value(node: "Vision3D.Node", name: str, *, parent: Optional["Vision3D.Node"] = None, sibling_index: int = 0) -> float:
            if name == "label_len":
                return float(len(node.label))
            if name == "metadata_keys":
                return float(len(node.metadata))
            if name == "num_children":
                return float(len(node.children))
            if name == "depth":
                return float(self.get_depth(node))
            if name == "is_leaf":
                return 1.0 if not node.children else 0.0
            if name == "locked":
                return 1.0 if node.locked else 0.0
            if name == "sibling_index":
                return float(sibling_index)
            if name == "sibling_count":
                return float(len(parent.children) if parent is not None else 0)
            if name == "parent_depth":
                return float(self.get_depth(parent)) if parent is not None else 0.0
            if name == "parent_num_children":
                return float(len(parent.children)) if parent is not None else 0.0
            if name == "subtree_size":
                return float(self.subtree_size(node))
            if name == "path_len":
                return float(len(node.path_labels()))
            if name == "label_hash_u16":
                return float(_label_hash_u16(node.label))
            if name == "constraint_count":
                if node._id is None:
                    return 0.0
                return float(len(self.constraints.get(int(node._id), [])))
            if name == "role_id":
                if node._id is None:
                    return 0.0
                return _role_id(int(node._id))
            # Unknown channel -> 0
            return 0.0

        for parent in self.nodes:
            d = self.get_depth(parent)
            for i, child in enumerate(parent.children):
                for k, ch in enumerate(channels):
                    tensor[d, i, k] = channel_value(child, ch, parent=parent, sibling_index=i)
        return tensor

    EYES16_CHANNELS: Tuple[str, ...] = (
        "label_len",
        "metadata_keys",
        "num_children",
        "depth",
        "is_leaf",
        "locked",
        "sibling_index",
        "sibling_count",
        "parent_depth",
        "parent_num_children",
        "subtree_size",
        "path_len",
        "label_hash_u16",
        "constraint_count",
        "role_id",
        "metadata_present",
    )

    EYES26_CHANNELS: Tuple[str, ...] = (
        # Base 16
        "label_len",
        "metadata_keys",
        "num_children",
        "depth",
        "is_leaf",
        "locked",
        "sibling_index",
        "sibling_count",
        "parent_depth",
        "parent_num_children",
        "subtree_size",
        "path_len",
        "label_hash_u16",
        "constraint_count",
        "role_id",
        "metadata_present",
        # Extra 10 (graph + text + normalization)
        "in_degree",
        "out_degree",
        "degree",
        "is_root",
        "depth_norm",
        "sibling_index_norm",
        "subtree_frac",
        "label_occurrences",
        "metadata_json_len",
        "leaf_descendants",
    )

    def to_tensor16(self) -> np.ndarray:
        """
        16-channel tensor ("16 eyes") using EYES16_CHANNELS.

        Note: "metadata_present" is derived from metadata_keys > 0.
        """
        channels = list(self.EYES16_CHANNELS)
        # Implement metadata_present via post-pass (keeps channel_value simple).
        if "metadata_present" in channels:
            # Replace with metadata_keys for computation then map to 0/1.
            idx = channels.index("metadata_present")
            channels[idx] = "metadata_keys"
            t = self.to_tensor(channels=channels)
            t[:, :, idx] = (t[:, :, idx] > 0).astype(float)
            return t
        return self.to_tensor(channels=channels)

    def to_tensor26(self) -> np.ndarray:
        """
        26-channel tensor ("26 eyes") using EYES26_CHANNELS.

        Notes:
        - "metadata_present" is derived from metadata_keys > 0.
        - Degree metrics are computed from the parsed tree edges (directed).
        """
        if not self.nodes:
            return np.zeros((0, 0, 26), dtype=float)

        # Precompute graph/label/leaf metrics once for stable channel_value behavior.
        edges = self.edge_list()
        n_nodes = len(self.nodes)
        in_deg = [0] * n_nodes
        out_deg = [0] * n_nodes
        for a, b in edges:
            if 0 <= a < n_nodes and 0 <= b < n_nodes:
                out_deg[a] += 1
                in_deg[b] += 1

        label_counts: Dict[str, int] = {}
        for n in self.nodes:
            label_counts[n.label] = label_counts.get(n.label, 0) + 1

        # Leaf descendants in subtree (excluding self unless self is a leaf and we count 0 for internal nodes).
        leaf_desc: Dict[int, int] = {}

        def count_leaf_desc(node: "Vision3D.Node") -> int:
            if node._id is None:
                return 0
            nid = int(node._id)
            if nid in leaf_desc:
                return leaf_desc[nid]
            if not node.children:
                leaf_desc[nid] = 0
                return 0
            total = 0
            for c in node.children:
                if not c.children:
                    total += 1
                total += count_leaf_desc(c)
            leaf_desc[nid] = total
            return total

        if self.root is not None:
            count_leaf_desc(self.root)

        # Compute tensor via the generic path, then patch "metadata_present".
        channels = list(self.EYES26_CHANNELS)
        mp_idx = None
        if "metadata_present" in channels:
            mp_idx = channels.index("metadata_present")
            channels[mp_idx] = "metadata_keys"

        # Extend the per-channel computation by temporarily teaching to_tensor() about extra channel names.
        # We do this by calling to_tensor() with channels, then overwriting the extra 10 channels in-place.
        t = self.to_tensor(channels=channels)

        # Map metadata_present to 0/1.
        if mp_idx is not None:
            t[:, :, mp_idx] = (t[:, :, mp_idx] > 0).astype(float)

        # Overwrite the extra 10 channels that the base to_tensor() doesn't know about (it yields 0.0).
        name_to_idx = {name: i for i, name in enumerate(self.EYES26_CHANNELS)}
        max_depth = t.shape[0]

        total_nodes = float(max(n_nodes, 1))
        max_depth_val = float(max(self.get_depth(n) for n in self.nodes)) if self.nodes else 0.0

        for parent in self.nodes:
            d = self.get_depth(parent)
            if d >= max_depth:
                continue
            parent_id = -1 if parent._id is None else int(parent._id)
            sib_count = float(len(parent.children)) if parent.children else 0.0
            for i, child in enumerate(parent.children):
                cid = -1 if child._id is None else int(child._id)
                if cid < 0:
                    continue

                def put(ch: str, val: float) -> None:
                    idx = name_to_idx.get(ch)
                    if idx is None:
                        return
                    t[d, i, idx] = val

                put("in_degree", float(in_deg[cid]))
                put("out_degree", float(out_deg[cid]))
                put("degree", float(in_deg[cid] + out_deg[cid]))
                # Note: tensor cells are emitted for "child-of-parent" relationships, so the actual root node
                # never appears as a "child" entry. We interpret is_root as "is directly under the root".
                put("is_root", 1.0 if (parent is not None and parent.parent is None) else 0.0)
                put("depth_norm", (float(self.get_depth(child)) / max_depth_val) if max_depth_val > 0 else 0.0)
                put("sibling_index_norm", (float(i) / (sib_count - 1.0)) if sib_count > 1.0 else 0.0)
                put("subtree_frac", float(self.subtree_size(child)) / total_nodes)
                put("label_occurrences", float(label_counts.get(child.label, 1)))
                put("metadata_json_len", float(len(json.dumps(child.metadata, sort_keys=True))) if child.metadata else 0.0)
                put("leaf_descendants", float(leaf_desc.get(cid, 0)))

        return t

    def eyes26(
        self,
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
    ) -> Dict[str, Any]:
        """
        Exactly 26 "perspectives/eyes" in one payload.
        - light=True: returns shapes/summaries rather than full dense arrays.
        """
        stats = self.stats()
        edges = self.edge_list()
        if not self.feature_vectors:
            self.build_feature_vectors()

        feats = None
        if not light and self.feature_vectors:
            feats = self.build_feature_matrix(fields=tuple(self.feature_vectors[0].keys()))

        adj = None
        if not light:
            adj = self.build_adj_matrix(directed=True)

        tensor26 = None
        if not light:
            tensor26 = self.to_tensor26()

        layout = None
        if include_layout3d:
            layout = self.layout_3d(iterations=layout3d_iters).tolist() if not light else {"shape": [len(self.nodes), 3]}

        violations = self.validate_bracket_law()

        # 26 keys, stable order (Python preserves insertion order).
        out: Dict[str, Any] = {}
        out["01_packet"] = self.bracket_packet
        out["02_governance_headers"] = list(self.governance_headers)
        out["03_ghost_metadata"] = dict(self.ghost_metadata)
        out["04_stats"] = stats
        out["05_violations"] = violations
        out["06_nodes"] = [
            {
                "id": n._id,
                "label": n.label,
                "parent_id": (n.parent._id if n.parent else None),
                "path": self.full_paths.get(int(n._id), []) if n._id is not None else [],
                "is_leaf": (0 if n.children else 1),
                "locked": bool(n.locked),
                "subtree_size": self.subtree_size(n),
            }
            for n in self.nodes
        ]
        out["07_edges"] = edges
        out["08_adj_matrix"] = (adj.tolist() if adj is not None else {"shape": list(self.build_adj_matrix().shape)})
        out["09_adj_list"] = {str(k): v for k, v in self.adj_list.items()}
        out["10_depth_map"] = {str(k): v for k, v in self.depth_map.items()}
        out["11_sibling_map"] = {str(k): v for k, v in self.sibling_map.items()}
        out["12_feature_vectors"] = list(self.feature_vectors)
        out["13_feature_matrix"] = (feats.tolist() if feats is not None else {"shape": [len(self.nodes), len(self.feature_vectors[0]) if self.feature_vectors else 0]})
        out["14_tensor26"] = (tensor26.tolist() if tensor26 is not None else {"shape": list(self.to_tensor26().shape)})
        out["15_tensor16_shape"] = list(self.to_tensor16().shape)
        out["16_channels16"] = list(self.EYES16_CHANNELS)
        out["17_channels26"] = list(self.EYES26_CHANNELS)
        out["18_temporal_log"] = list(self.temporal_log)
        out["19_event_log"] = list(self.event_log)
        out["20_semantic_roles"] = {str(k): v for k, v in self.semantic_roles.items()}
        out["21_constraints"] = {str(k): v for k, v in self.constraints.items()}
        out["22_embeddings_keys"] = list(self.embeddings.keys())
        out["23_hypergraph_layers"] = {k: [n._id for n in v if n._id is not None] for k, v in self.hypergraph_layers.items()}
        out["24_layout3d"] = layout
        out["25_extract_mode"] = {"strict": bool(self.strict)}
        out["26_version"] = {"eyes": 26, "schema": 1}
        return out

    def export_eyes26_json(
        self,
        out_path: str | os.PathLike[str],
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
    ) -> None:
        p = Path(out_path)
        data = self.eyes26(light=light, include_layout3d=include_layout3d, layout3d_iters=layout3d_iters)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def eyes_maxppp(
        self,
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
        include_subtree_snapshots: bool = False,
    ) -> Dict[str, Any]:
        """
        Ultimate max+++ bundle: everything in one payload (26+ perspectives).
        This is intentionally bigger than eyes26.
        """
        if not self.feature_vectors:
            self.build_feature_vectors()
        self.compute_aggregate_metrics()

        if include_subtree_snapshots and not self.subtree_snapshots:
            # Safe snapshot caching; caller can control size via light mode.
            self.snapshot_all_subtrees(max_nodes=5000)

        payload: Dict[str, Any] = {}
        payload["packet"] = self.bracket_packet
        payload["governance_headers"] = list(self.governance_headers)
        payload["ghost_metadata"] = dict(self.ghost_metadata)
        payload["stats"] = self.stats()
        payload["violations"] = self.validate_bracket_law()
        payload["nodes"] = [
            {
                "id": n._id,
                "label": n.label,
                "parent_id": (n.parent._id if n.parent else None),
                "path": self.full_paths.get(int(n._id), []) if n._id is not None else [],
                "is_leaf": (0 if n.children else 1),
                "locked": bool(n.locked),
                "metadata": (dict(n.metadata) if not light else None),
            }
            for n in self.nodes
        ]
        payload["edges"] = self.edge_list()
        payload["adj_list"] = {str(k): v for k, v in self.adj_list.items()}
        payload["adj_matrix"] = (self.build_adj_matrix().tolist() if not light else {"shape": list(self.build_adj_matrix().shape)})
        payload["depth_map"] = {str(k): v for k, v in self.depth_map.items()}
        payload["sibling_map"] = {str(k): v for k, v in self.sibling_map.items()}
        payload["parent_map"] = {str(k): v for k, v in self.parent_map.items()}
        payload["full_paths"] = {str(k): v for k, v in self.full_paths.items()}
        payload["leaf_nodes"] = list(self.leaf_nodes)
        payload["flattened_metadata"] = ({str(k): v for k, v in self.flattened_metadata.items()} if not light else {"count": len(self.flattened_metadata)})
        payload["subtree_snapshots"] = (self.subtree_snapshots if (include_subtree_snapshots and not light) else {"enabled": bool(include_subtree_snapshots), "count": len(self.subtree_snapshots)})
        payload["feature_vectors"] = list(self.feature_vectors)
        payload["tensor16_shape"] = list(self.to_tensor16().shape)
        payload["tensor26_shape"] = list(self.to_tensor26().shape)
        payload["channels16"] = list(self.EYES16_CHANNELS)
        payload["channels26"] = list(self.EYES26_CHANNELS)
        payload["temporal_log"] = list(self.temporal_log)
        payload["event_log"] = list(self.event_log)
        payload["semantic_roles"] = {str(k): v for k, v in self.semantic_roles.items()}
        payload["constraints"] = {str(k): v for k, v in self.constraints.items()}
        payload["cross_layer_dependencies"] = {str(k): v for k, v in self.cross_layer_dependencies.items()}
        payload["aggregate_metrics"] = {str(k): v for k, v in self.aggregate_metrics.items()}
        payload["change_impact"] = {str(k): v for k, v in self.change_impact.items()}
        payload["change_risk"] = {str(k): v for k, v in self.change_risk.items()}

        if include_layout3d:
            payload["layout3d"] = self.layout_3d(iterations=layout3d_iters).tolist() if not light else {"shape": [len(self.nodes), 3]}
        else:
            payload["layout3d"] = None

        payload["normal_code"] = (self.to_normal_code() if not light else {"lines": len(self.to_normal_code())})
        payload["version"] = {"bundle": "maxppp", "schema": 1}
        return payload

    def export_eyes_maxppp_json(
        self,
        out_path: str | os.PathLike[str],
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
        include_subtree_snapshots: bool = False,
    ) -> None:
        p = Path(out_path)
        data = self.eyes_maxppp(
            light=light,
            include_layout3d=include_layout3d,
            layout3d_iters=layout3d_iters,
            include_subtree_snapshots=include_subtree_snapshots,
        )
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


    # --- 3D layout (optional) ---
    def _layout_3d_numpy(self, *, iterations: int = 200, seed: int = 0, k: Optional[float] = None) -> np.ndarray:
        """
        Simple force-directed 3D layout (spring + repulsion).
        Returns coords array shape (N, 3), aligned to self.nodes by id.
        """
        n = len(self.nodes)
        if n == 0:
            return np.zeros((0, 3), dtype=float)

        rng = np.random.default_rng(seed)
        pos = rng.normal(scale=0.5, size=(n, 3)).astype(float)

        edges = self.edge_list()
        if k is None:
            k = math.sqrt(1.0 / max(n, 1))

        # Precompute adjacency for attractive forces
        adj = [[] for _ in range(n)]
        for a, b in edges:
            adj[a].append(b)
            adj[b].append(a)

        # Cooling schedule
        t0 = 0.1
        for it in range(iterations):
            t = t0 * (1.0 - (it / max(iterations, 1)))
            disp = np.zeros_like(pos)

            # Repulsion (O(N^2) but ok for utility sizes)
            for i in range(n):
                delta = pos[i] - pos
                dist = np.linalg.norm(delta, axis=1) + 1e-9
                force = (k * k) / dist
                disp[i] += (delta.T * force).T.sum(axis=0)

            # Attraction along edges
            for i in range(n):
                for j in adj[i]:
                    delta = pos[i] - pos[j]
                    dist = np.linalg.norm(delta) + 1e-9
                    force = (dist * dist) / k
                    disp[i] -= (delta / dist) * force

            # Apply displacement with temperature cap
            lengths = np.linalg.norm(disp, axis=1) + 1e-9
            pos += (disp.T * (np.minimum(lengths, t) / lengths)).T

        return pos

    def _layout_3d_torch_mps(self, *, iterations: int = 200, seed: int = 0, k: Optional[float] = None) -> np.ndarray:
        n = len(self.nodes)
        if n == 0:
            return np.zeros((0, 3), dtype=float)

        device = torch.device("mps")
        init_gen = torch.Generator(device="cpu")
        init_gen.manual_seed(seed)
        pos = torch.randn((n, 3), generator=init_gen, dtype=torch.float32) * 0.5
        pos = pos.to(device)

        edges = self.edge_list()
        if k is None:
            k = math.sqrt(1.0 / max(n, 1))

        eps = 1e-9
        t0 = 0.1
        eye_mask = torch.eye(n, device=device, dtype=torch.bool)

        if edges:
            src = torch.tensor([a for a, _ in edges], device=device, dtype=torch.long)
            dst = torch.tensor([b for _, b in edges], device=device, dtype=torch.long)
        else:
            src = dst = None

        for it in range(iterations):
            t = t0 * (1.0 - (it / max(iterations, 1)))
            delta = pos.unsqueeze(1) - pos.unsqueeze(0)
            dist = torch.linalg.norm(delta, dim=2).clamp_min(eps)
            repulse = ((k * k) / dist).masked_fill(eye_mask, 0.0)
            disp = (delta * repulse.unsqueeze(2)).sum(dim=1)

            if src is not None and dst is not None and len(edges) > 0:
                edge_delta = pos[src] - pos[dst]
                edge_dist = torch.linalg.norm(edge_delta, dim=1).clamp_min(eps)
                edge_force = (edge_delta / edge_dist.unsqueeze(1)) * ((edge_dist * edge_dist) / k).unsqueeze(1)
                disp.index_add_(0, src, -edge_force)
                disp.index_add_(0, dst, edge_force)

            lengths = torch.linalg.norm(disp, dim=1).clamp_min(eps)
            scale = torch.minimum(lengths, torch.full_like(lengths, t)) / lengths
            pos = pos + disp * scale.unsqueeze(1)

        return pos.detach().to("cpu").numpy().astype(float, copy=False)

    def layout_3d(
        self,
        *,
        iterations: int = 200,
        seed: int = 0,
        k: Optional[float] = None,
        backend: str = "auto",
    ) -> np.ndarray:
        requested = backend.lower()
        use_mps = requested == "mps" or (requested == "auto" and TORCH_MPS_AVAILABLE)

        if use_mps:
            try:
                coords = self.layout_3d_torch_mps(iterations=iterations, seed=seed, k=k)
                self.last_layout_backend = "mps"
                return coords
            except Exception:
                # Fall back cleanly when torch/MPS is present but unstable or out of memory.
                pass

        coords = self.layout_3d_numpy(iterations=iterations, seed=seed, k=k)
        self.last_layout_backend = "numpy"
        return coords

    # --- Exports ---
    def to_dict(self) -> Dict[str, Any]:
        def node_to_dict(n: "Vision3D.Node") -> Dict[str, Any]:
            return {
                "id": n._id,
                "label": n.label,
                "metadata": n.metadata,
                "children": [node_to_dict(c) for c in n.children],
            }

        return {
            "governance_headers": self.governance_headers,
            "packet": self.bracket_packet,
            "root": node_to_dict(self.root) if self.root else None,
        }

    def export_json(self, out_path: str | os.PathLike[str]) -> None:
        p = Path(out_path)
        data = self.to_dict()
        p.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    def export_csv_nodes_edges(self, out_dir: str | os.PathLike[str]) -> Tuple[Path, Path]:
        """
        Writes nodes.csv + edges.csv into out_dir.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        nodes_p = out / "nodes.csv"
        edges_p = out / "edges.csv"

        nodes_lines = ["id,label,depth,num_children,metadata_keys\n"]
        for n in self.nodes:
            nid = -1 if n._id is None else n._id
            nodes_lines.append(f"{nid},{json.dumps(n.label)},{self.get_depth(n)},{len(n.children)},{len(n.metadata)}\n")
        nodes_p.write_text("".join(nodes_lines), encoding="utf-8")

        edges_lines = ["parent_id,child_id\n"]
        for a, b in self.edge_list():
            edges_lines.append(f"{a},{b}\n")
        edges_p.write_text("".join(edges_lines), encoding="utf-8")
        return nodes_p, edges_p

    def export_npz(self, out_path: str | os.PathLike[str]) -> None:
        """
        Stores adjacency matrix, feature matrix, and tensor into a .npz.
        """
        adj = self.build_adj_matrix(directed=True)
        feats = self.build_feature_matrix()
        ten = self.to_tensor()
        np.savez_compressed(str(out_path), adjacency=adj, features=feats, tensor=ten)

    def export_npz16(self, out_path: str | os.PathLike[str]) -> None:
        """
        Stores adjacency matrix, feature matrix, and 16-channel tensor into a .npz.
        """
        adj = self.build_adj_matrix(directed=True)
        # Use the richer default feature vector keys if present.
        if not self.feature_vectors:
            self.build_feature_vectors()
        fields = tuple(self.feature_vectors[0].keys()) if self.feature_vectors else ("label_len", "num_children", "depth")
        feats = self.build_feature_matrix(fields=fields)
        ten16 = self.to_tensor16()
        np.savez_compressed(str(out_path), adjacency=adj, features=feats, tensor16=ten16)

    def export_npz26(self, out_path: str | os.PathLike[str]) -> None:
        """
        Stores adjacency matrix, feature matrix, and 26-channel tensor into a .npz.
        """
        adj = self.build_adj_matrix(directed=True)
        if not self.feature_vectors:
            self.build_feature_vectors()
        fields = tuple(self.feature_vectors[0].keys()) if self.feature_vectors else ("label_len", "num_children", "depth")
        feats = self.build_feature_matrix(fields=fields)
        ten26 = self.to_tensor26()
        np.savez_compressed(str(out_path), adjacency=adj, features=feats, tensor26=ten26)

    def export_sqlite(self, db_path: str | os.PathLike[str], *, overwrite_tables: bool = False) -> None:
        """
        Export packet, nodes, and edges into SQLite.
        Safe by default: will not drop tables unless overwrite_tables=True.
        Tables:
        - packets(packet_id INTEGER PK, created_at TEXT, packet TEXT)
        - nodes(packet_id INTEGER, node_id INTEGER, label TEXT, depth INTEGER, metadata_json TEXT)
        - edges(packet_id INTEGER, parent_id INTEGER, child_id INTEGER)
        """
        dbp = Path(db_path)
        con = sqlite3.connect(str(dbp))
        try:
            cur = con.cursor()
            if overwrite_tables:
                cur.executescript(
                    """
                    DROP TABLE IF EXISTS packets;
                    DROP TABLE IF EXISTS nodes;
                    DROP TABLE IF EXISTS edges;
                    """
                )
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS packets(
                    packet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    packet TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes(
                    packet_id INTEGER NOT NULL,
                    node_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY(packet_id, node_id)
                );
                CREATE TABLE IF NOT EXISTS edges(
                    packet_id INTEGER NOT NULL,
                    parent_id INTEGER NOT NULL,
                    child_id INTEGER NOT NULL
                );
                """
            )

            created_at = _dt.datetime.now().isoformat(timespec="seconds")
            cur.execute("INSERT INTO packets(created_at, packet) VALUES(?, ?)", (created_at, self.bracket_packet))
            packet_id = int(cur.lastrowid)

            for n in self.nodes:
                nid = int(n._id) if n._id is not None else -1
                cur.execute(
                    "INSERT INTO nodes(packet_id, node_id, label, depth, metadata_json) VALUES(?, ?, ?, ?, ?)",
                    (packet_id, nid, n.label, self.get_depth(n), json.dumps(n.metadata, sort_keys=True)),
                )
            for a, b in self.edge_list():
                cur.execute("INSERT INTO edges(packet_id, parent_id, child_id) VALUES(?, ?, ?)", (packet_id, a, b))

            con.commit()
        finally:
            con.close()

    # --- Utilities ---
    def validate_bracket_law(self) -> List[Dict[str, Any]]:
        """
        Bracket_law-oriented validation against the parsed structure.
        Returns a list of violations; empty list means "clean".
        """
        violations: List[Dict[str, Any]] = []
        if self.root is None:
            violations.append({"rule": "Root", "error": "No root node parsed"})
            return violations

        for n in self.nodes:
            if n.label is None or not str(n.label).strip():
                violations.append({"rule": "Names", "node_id": n._id, "error": "Empty label"})
            if "[" in n.label or "]" in n.label:
                violations.append({"rule": "Names", "node_id": n._id, "label": n.label, "error": "Label contains bracket char"})
        return violations

    def eyes16(
        self,
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
    ) -> Dict[str, Any]:
        """
        Exactly 16 "perspectives/eyes" in one payload.
        - light=True: returns shapes/summaries rather than full dense arrays.
        """
        stats = self.stats()
        edges = self.edge_list()
        adj = self.adj_matrix if self.adj_matrix is not None else None
        if adj is None and not light:
            adj = self.build_adj_matrix(directed=True)
        if not self.feature_vectors:
            self.build_feature_vectors()
        feats = None
        if not light:
            feats = self.build_feature_matrix(fields=tuple(self.feature_vectors[0].keys()))

        tensor16 = None
        if not light:
            tensor16 = self.to_tensor16()

        layout = None
        if include_layout3d:
            layout = self.layout_3d(iterations=layout3d_iters).tolist() if not light else {"shape": [len(self.nodes), 3]}

        nodes_summary = []
        for n in self.nodes:
            nodes_summary.append(
                {
                    "id": n._id,
                    "label": n.label,
                    "parent_id": (n.parent._id if n.parent is not None else None),
                    "depth": self.get_depth(n),
                    "locked": bool(n.locked),
                }
            )

        # 16 keys, stable order by construction (Python preserves insertion order).
        out: Dict[str, Any] = {}
        out["1_packet"] = self.bracket_packet
        out["2_governance_headers"] = list(self.governance_headers)
        out["3_stats"] = stats
        out["4_nodes"] = nodes_summary
        out["5_edges"] = edges
        out["6_adj_matrix"] = (adj.tolist() if (adj is not None and not light) else {"shape": list(self.build_adj_matrix().shape)})
        out["7_adj_list"] = {str(k): v for k, v in self.adj_list.items()}
        out["8_depth_map"] = {str(k): v for k, v in self.depth_map.items()}
        out["9_sibling_map"] = {str(k): v for k, v in self.sibling_map.items()}
        out["10_feature_vectors"] = list(self.feature_vectors)
        out["11_feature_matrix"] = (feats.tolist() if feats is not None else {"shape": [len(self.nodes), len(self.feature_vectors[0]) if self.feature_vectors else 0]})
        out["12_tensor16"] = (tensor16.tolist() if tensor16 is not None else {"shape": list(self.to_tensor16().shape)})
        out["13_temporal_log"] = list(self.temporal_log)
        out["14_semantic_roles"] = {str(k): v for k, v in self.semantic_roles.items()}
        out["15_constraints"] = {str(k): v for k, v in self.constraints.items()}
        out["16_layout3d"] = layout
        return out

    def export_eyes16_json(
        self,
        out_path: str | os.PathLike[str],
        *,
        light: bool = True,
        include_layout3d: bool = False,
        layout3d_iters: int = 200,
    ) -> None:
        p = Path(out_path)
        data = self.eyes16(light=light, include_layout3d=include_layout3d, layout3d_iters=layout3d_iters)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def stats(self) -> Dict[str, Any]:
        if not self.nodes:
            return {"nodes": 0, "edges": 0, "max_depth": 0}
        label_counts: Dict[str, int] = {}
        for n in self.nodes:
            label_counts[n.label] = label_counts.get(n.label, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edge_list()),
            "max_depth": max(self.get_depth(n) for n in self.nodes),
            "max_children": max(len(n.children) for n in self.nodes),
            "governance_headers": len(self.governance_headers),
            "leaf_nodes": len(self.leaf_nodes) if hasattr(self, "leaf_nodes") else sum(1 for n in self.nodes if not n.children),
            "unique_labels": len(label_counts),
            "repeated_labels": sum(1 for _, c in label_counts.items() if c > 1),
        }

    def print_tree(self, *, max_width: int = 120) -> str:
        """
        ASCII tree for quick inspection.
        """
        if self.root is None:
            return "<empty>\n"

        lines: List[str] = []

        def rec(n: "Vision3D.Node", prefix: str, is_last: bool) -> None:
            nid = "" if n._id is None else f"{n._id}:"
            label = n.label
            line = f"{prefix}{'└─' if is_last else '├─'}{nid}{label}"
            lines.append(line[:max_width])
            new_prefix = prefix + ("  " if is_last else "│ ")
            for i, c in enumerate(n.children):
                rec(c, new_prefix, i == len(n.children) - 1)

        # Root printed without branch prefix.
        rid = "" if self.root._id is None else f"{self.root._id}:"
        lines.append(f"{rid}{self.root.label}"[:max_width])
        for i, c in enumerate(self.root.children):
            rec(c, "", i == len(self.root.children) - 1)
        return "\n".join(lines) + "\n"


class VisionUltimate(Vision3D):
    """
    Compatibility alias for the "ultimate max+++" GhostBracket class.
    This inherits the full 26-eye tensor/payload plus max+++ perspectives:
    paths/lineage, leaf view, subtree snapshots, parent map, cross-layer deps,
    aggregate metrics, and change impact/risk propagation.
    """
    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


class VisionMaxPlus(Vision3D):
    """Compatibility alias for earlier naming."""
    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


def _cli() -> int:
    ap = argparse.ArgumentParser(description="VBSTYLE bracket packet -> 3D graph/tensor utility")
    ap.add_argument("--in", dest="in_path", help="Input file path (markdown/text) containing a packet. Use '-' for stdin.")
    ap.add_argument("--packet", dest="packet", help="Bracket packet string (if provided, overrides --in).")
    ap.add_argument("--code-in", dest="code_in", help="Input CODE file path (currently supports --lang python). Use '-' for stdin.")
    ap.add_argument("--code", dest="code", help="Inline code string (currently supports --lang python).")
    ap.add_argument("--lang", dest="lang", default="python", help="Language for --code/--code-in (default: python).")
    ap.add_argument("--module-name", dest="module_name", help="Module name label when converting code to brackets.")
    ap.add_argument("--show-bracket", action="store_true", help="When using --code/--code-in, print the generated bracket packet.")
    ap.add_argument("--export-bracket", dest="export_bracket", help="When using --code/--code-in, write the generated bracket packet to this path.")
    ap.add_argument("--no-extract", action="store_true", help="Do not extract; treat input as pure bracket packet.")
    ap.add_argument("--non-strict", action="store_true", help="Allow multiple roots / be permissive.")
    ap.add_argument("--stats", action="store_true", help="Print stats as JSON to stdout.")
    ap.add_argument("--print-tree", action="store_true", help="Print ASCII tree to stdout.")
    ap.add_argument("--export-json", dest="export_json", help="Write parsed tree JSON to this path.")
    ap.add_argument("--export-csv", dest="export_csv", help="Write nodes.csv + edges.csv into this directory.")
    ap.add_argument("--export-npz", dest="export_npz", help="Write adjacency/features/tensor into .npz.")
    ap.add_argument("--export-npz16", dest="export_npz16", help="Write adjacency/features/tensor16 into .npz.")
    ap.add_argument("--export-npz26", dest="export_npz26", help="Write adjacency/features/tensor26 into .npz.")
    ap.add_argument("--export-sqlite", dest="export_sqlite", help="Write nodes/edges into SQLite DB.")
    ap.add_argument("--overwrite-sqlite-tables", action="store_true", help="Drop export tables before writing (danger).")
    ap.add_argument("--layout3d-json", dest="layout3d_json", help="Write node coords (N x 3) to JSON.")
    ap.add_argument("--layout3d-iters", type=int, default=200, help="Iterations for layout3d (default: 200).")
    ap.add_argument("--eyes16-json", dest="eyes16_json", help="Write the 16-eye payload to JSON.")
    ap.add_argument("--eyes16-full", action="store_true", help="When writing eyes16, include full dense arrays (bigger file).")
    ap.add_argument("--eyes16-layout3d", action="store_true", help="When writing eyes16, include layout3d (or its shape).")
    ap.add_argument("--eyes26-json", dest="eyes26_json", help="Write the 26-eye payload to JSON.")
    ap.add_argument("--eyes26-full", action="store_true", help="When writing eyes26, include full dense arrays (bigger file).")
    ap.add_argument("--eyes26-layout3d", action="store_true", help="When writing eyes26, include layout3d (or its shape).")
    ap.add_argument("--eyes-max-json", dest="eyes_max_json", help="Write the ultimate max+++ bundle payload to JSON.")
    ap.add_argument("--eyes-max-full", action="store_true", help="When writing eyes-max, include heavier fields (metadata).")
    ap.add_argument("--eyes-max-layout3d", action="store_true", help="When writing eyes-max, include layout3d (or its shape).")
    ap.add_argument("--eyes-max-subtrees", action="store_true", help="When writing eyes-max, include subtree snapshots (can be large).")
    ap.add_argument("--normal-code", action="store_true", help="Print indentation-based normal-code view to stdout.")
    args = ap.parse_args()

    input_kind = "packet"
    extract = not args.no_extract
    strict = not args.non_strict

    raw: Optional[str] = None
    if args.packet is not None:
        raw = args.packet
        input_kind = "packet"
    elif args.code is not None or args.code_in is not None:
        input_kind = "code"
        lang = (args.lang or "python").lower().strip()
        if lang != "python":
            ap.error("Only --lang python is supported right now.")
            return 2
        if args.code is not None:
            code_text = args.code
        elif args.code_in == "-":
            code_text = sys.stdin.read()
        else:
            code_text = Path(args.code_in).read_text(encoding="utf-8", errors="replace")

        # Convenience: allow passing multiline code via --code with literal "\n".
        # We only unescape if there are no real newlines yet, to avoid surprising transforms.
        if "\\n" in code_text and "\n" not in code_text:
            try:
                code_text = code_text.encode("utf-8").decode("unicode_escape")
            except Exception:
                pass

        mod_name = args.module_name
        if not mod_name and args.code_in and args.code_in not in ("-", None):
            mod_name = Path(args.code_in).name
        mod_name = mod_name or "<module>"
        packet = python_code_to_bracket_packet(code_text, module_name=mod_name)
        raw = packet
        extract = False  # already a pure packet
        strict = True
        if args.show_bracket:
            pass
        if args.export_bracket:
            Path(args.export_bracket).write_text(packet + "\n", encoding="utf-8")
    elif args.in_path == "-":
        raw = sys.stdin.read()
        input_kind = "doc"
    elif args.in_path:
        raw = Path(args.in_path).read_text(encoding="utf-8", errors="replace")
        input_kind = "doc"
    else:
        ap.error("Provide --packet, --in, or --code/--code-in")
        return 2

    v = Vision3D(raw, strict=strict, extract_packet=extract, ghost_metadata={"input_kind": input_kind})

    if args.stats:
        pass
    if args.print_tree:
        pass
    if args.export_json:
        v.export_json(args.export_json)
    if args.export_csv:
        v.export_csv_nodes_edges(args.export_csv)
    if args.export_npz:
        v.export_npz(args.export_npz)
    if args.export_npz16:
        v.export_npz16(args.export_npz16)
    if args.export_npz26:
        v.export_npz26(args.export_npz26)
    if args.export_sqlite:
        v.export_sqlite(args.export_sqlite, overwrite_tables=args.overwrite_sqlite_tables)
    if args.layout3d_json:
        coords = v.layout_3d(iterations=args.layout3d_iters)
        Path(args.layout3d_json).write_text(json.dumps(coords.tolist(), indent=2) + "\n", encoding="utf-8")
    if args.eyes16_json:
        v.export_eyes16_json(
            args.eyes16_json,
            light=not args.eyes16_full,
            include_layout3d=args.eyes16_layout3d,
            layout3d_iters=args.layout3d_iters,
        )
    if args.eyes26_json:
        v.export_eyes26_json(
            args.eyes26_json,
            light=not args.eyes26_full,
            include_layout3d=args.eyes26_layout3d,
            layout3d_iters=args.layout3d_iters,
        )
    if args.eyes_max_json:
        v.export_eyes_maxppp_json(
            args.eyes_max_json,
            light=not args.eyes_max_full,
            include_layout3d=args.eyes_max_layout3d,
            layout3d_iters=args.layout3d_iters,
            include_subtree_snapshots=args.eyes_max_subtrees,
        )
    if args.normal_code:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
