#[@GHOST]{file_path="core/Dom_Benchmark/BclirGraph.py" date="2026-07-04" author="Devin" session_id="benchmark-bclir-graph" context="BCLIR + Graph engine for benchmark test cases. Converts test cases → BCL packets → BCLIR typed nodes → execution graph. Includes type checking, validation, graph building, traversal, and visualization."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="BclirGraph.py" domain="dom_benchmark" authority="BclirGraph"}
#[@SUMMARY]{summary="BCLIR + Graph engine. Test cases → BCL packets → BCLIR typed nodes → execution graph. Type checking, validation, graph building, traversal, DOT visualization. The missing layer between BCL parse and execution."}
#[@CLASS]{class="BclirGraph" domain="dom_benchmark" authority="engine"}
#[@METHOD]{method="case_to_bcl" type="converter"}
#[@METHOD]{method="bcl_to_bclir" type="compiler"}
#[@METHOD]{method="bclir_to_graph" type="builder"}
#[@METHOD]{method="case_to_graph" type="pipeline"}
#[@METHOD]{method="validate_bclir" type="validator"}
#[@METHOD]{method="traverse" type="walker"}
#[@METHOD]{method="to_dot" type="visualizer"}
#[@METHOD]{method="Run" type="dispatch"}

"""BclirGraph — BCLIR + Graph engine for benchmark test cases.

Full pipeline:
    TestCase → BCL packet → BCLIR (typed nodes) → Graph (nodes+edges)

BCLIR is the typed intermediate representation between BCL parse and execution.
Graph is the execution graph built from BCLIR nodes.

BCLIRNode types:
    OP_CASE       — a test case operation
    OP_TRIGGER    — trigger the error (execute broken code)
    OP_CAPTURE    — capture exception + traceback
    OP_FIX        — generate fix candidates
    OP_APPLY      — apply a fix candidate
    OP_VALIDATE   — validate the fixed code
    OP_SCORE      — score the fix candidate
    OP_PROMOTE    — promote/demote confidence

Graph edges:
    NEXT          — sequential flow (case → trigger → capture → fix → ...)
    DEPENDS       — data dependency (validate depends on apply)
    BRANCHES      — conditional branch (fix → apply candidate 1, 2, 3...)
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import Config
    from ErrorModel import ErrorModel, FixCandidate, ValidationResult
except ImportError:
    from . import Config
    from .ErrorModel import ErrorModel, FixCandidate, ValidationResult

# ── BCLIR Types ──
BCLIR_STRING = "STRING"
BCLIR_INT = "INT"
BCLIR_FLOAT = "FLOAT"
BCLIR_BOOL = "BOOL"
BCLIR_CODE = "CODE"
BCLIR_LIST = "LIST"
BCLIR_DICT = "DICT"

# ── BCLIR Operations ──
OP_CASE = "CASE"
OP_TRIGGER = "TRIGGER"
OP_CAPTURE = "CAPTURE"
OP_FIX = "FIX"
OP_APPLY = "APPLY"
OP_VALIDATE = "VALIDATE"
OP_SCORE = "SCORE"
OP_PROMOTE = "PROMOTE"

# ── Graph Edge Relations ──
EDGE_NEXT = "NEXT"
EDGE_DEPENDS = "DEPENDS"
EDGE_BRANCHES = "BRANCHES"

# ── Type Schema (which params each OP expects) ──
OP_SCHEMA = {
    OP_CASE: {
        "CASE_ID": BCLIR_STRING,
        "FAMILY": BCLIR_STRING,
        "EXPECTED": BCLIR_STRING,
        "SEVERITY": BCLIR_INT,
        "BROKEN_CODE": BCLIR_CODE,
        "FIXED_CODE": BCLIR_CODE,
    },
    OP_TRIGGER: {
        "BROKEN_CODE": BCLIR_CODE,
        "TIMEOUT": BCLIR_INT,
    },
    OP_CAPTURE: {
        "EXCEPTION": BCLIR_STRING,
        "TRACEBACK": BCLIR_STRING,
        "TIMING_MS": BCLIR_FLOAT,
    },
    OP_FIX: {
        "BROKEN_CODE": BCLIR_CODE,
        "EXCEPTION": BCLIR_STRING,
        "STRATEGY": BCLIR_STRING,
    },
    OP_APPLY: {
        "CANDIDATE": BCLIR_CODE,
        "ORIGINAL": BCLIR_CODE,
    },
    OP_VALIDATE: {
        "CANDIDATE": BCLIR_CODE,
        "PY_COMPILE": BCLIR_BOOL,
        "AST_PARSE": BCLIR_BOOL,
        "RE_RUN": BCLIR_BOOL,
    },
    OP_SCORE: {
        "STRATEGY": BCLIR_STRING,
        "SCORE": BCLIR_INT,
        "PASSED": BCLIR_BOOL,
    },
    OP_PROMOTE: {
        "CONFIDENCE": BCLIR_FLOAT,
        "ACTION": BCLIR_STRING,
    },
}


@dataclass
class BCLIRVal:
    """A typed BCLIR value."""
    type: str = BCLIR_STRING
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "value": self.value}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BCLIRVal":
        return cls(type=d.get("type", BCLIR_STRING), value=d.get("value"))

    def __repr__(self) -> str:
        return "BCLIRVal({}:{})".format(self.type, repr(self.value)[:60])


@dataclass
class BCLIRNode:
    """A single BCLIR node — one operation in the pipeline."""
    op: str = ""
    params: Dict[str, BCLIRVal] = field(default_factory=dict)
    children: List["BCLIRNode"] = field(default_factory=list)
    node_id: str = ""
    validated: bool = False
    validation_errors: List[str] = field(default_factory=list)
    cost_estimate: float = 0.0
    cached: bool = False
    result: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op,
            "node_id": self.node_id,
            "params": {k: v.to_dict() for k, v in self.params.items()},
            "children": [c.to_dict() for c in self.children],
            "validated": self.validated,
            "validation_errors": self.validation_errors,
            "cost_estimate": self.cost_estimate,
            "cached": self.cached,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BCLIRNode":
        node = cls(
            op=d.get("op", ""),
            node_id=d.get("node_id", ""),
            validated=d.get("validated", False),
            validation_errors=d.get("validation_errors", []),
            cost_estimate=d.get("cost_estimate", 0.0),
            cached=d.get("cached", False),
        )
        node.params = {k: BCLIRVal.from_dict(v) for k, v in d.get("params", {}).items()}
        node.children = [BCLIRNode.from_dict(c) for c in d.get("children", [])]
        return node


@dataclass
class GraphNode:
    """A node in the execution graph."""
    id: str = ""
    label: str = ""
    node_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    edges_out: List["GraphEdge"] = field(default_factory=list)
    edges_in: List["GraphEdge"] = field(default_factory=list)
    visited: bool = False
    depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "data": self.data,
            "depth": self.depth,
            "edges_out": [e.to_dict() for e in self.edges_out],
            "edges_in_count": len(self.edges_in),
        }


@dataclass
class GraphEdge:
    """An edge in the execution graph."""
    from_id: str = ""
    to_id: str = ""
    relation: str = EDGE_NEXT
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_id,
            "to": self.to_id,
            "relation": self.relation,
            "label": self.label,
        }


class ExecutionGraph:
    """Execution graph built from BCLIR nodes."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.root_id: str = ""
        self.node_order: List[str] = []

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node
        self.node_order.append(node.id)
        if not self.root_id:
            self.root_id = node.id

    def add_edge(self, from_id: str, to_id: str, relation: str = EDGE_NEXT, label: str = "") -> None:
        edge = GraphEdge(from_id=from_id, to_id=to_id, relation=relation, label=label)
        self.edges.append(edge)
        if from_id in self.nodes:
            self.nodes[from_id].edges_out.append(edge)
        if to_id in self.nodes:
            self.nodes[to_id].edges_in.append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def traverse(self, start_id: str = "") -> List[Dict[str, Any]]:
        """BFS traversal from start node."""
        if not start_id:
            start_id = self.root_id
        if start_id not in self.nodes:
            return []
        for n in self.nodes.values():
            n.visited = False
        result = []
        queue = [(start_id, 0)]
        while queue:
            node_id, depth = queue.pop(0)
            node = self.nodes.get(node_id)
            if not node or node.visited:
                continue
            node.visited = True
            node.depth = depth
            result.append({
                "id": node.id,
                "label": node.label,
                "type": node.node_type,
                "depth": depth,
                "edges_out": [(e.to_id, e.relation, e.label) for e in node.edges_out],
            })
            for edge in node.edges_out:
                if not self.nodes.get(edge.to_id, None) or not self.nodes[edge.to_id].visited:
                    queue.append((edge.to_id, depth + 1))
        return result

    def to_dot(self) -> str:
        """Generate Graphviz DOT format for visualization."""
        lines = ["digraph ExecutionGraph {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [fontname=Monospace, fontsize=10, style=filled];")
        color_map = {
            OP_CASE: "lightblue",
            OP_TRIGGER: "lightyellow",
            OP_CAPTURE: "yellow",
            OP_FIX: "lightgreen",
            OP_APPLY: "green",
            OP_VALIDATE: "orange",
            OP_SCORE: "gold",
            OP_PROMOTE: "pink",
        }
        for node_id in self.node_order:
            node = self.nodes.get(node_id)
            if not node:
                continue
            color = color_map.get(node.node_type, "white")
            label = node.label.replace('"', '\\"')
            lines.append('  "{}" [label="{}\\n({})", fillcolor={}];'.format(
                node_id, label, node.node_type, color))
        for edge in self.edges:
            label = edge.label.replace('"', '\\"') if edge.label else ""
            lines.append('  "{}" -> "{}" [label="{}"];'.format(
                edge.from_id, edge.to_id, label))
        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [self.nodes[nid].to_dict() for nid in self.node_order],
            "edges": [e.to_dict() for e in self.edges],
        }


class BclirGraph:
    """BCLIR + Graph engine for benchmark test cases.

    Full pipeline:
        TestCase → BCL packet → BCLIR (typed nodes) → Graph (nodes+edges)

    Commands (via Run dispatch):
        case_to_bcl     — convert ErrorModel → BCL packet string
        bcl_to_bclir    — compile BCL packet → BCLIRNode tree
        bclir_to_graph  — build ExecutionGraph from BCLIRNode tree
        case_to_graph   — full pipeline: TestCase → BCL → BCLIR → Graph
        validate_bclir  — type-check a BCLIRNode tree
        traverse        — BFS traverse the execution graph
        to_dot          — generate Graphviz DOT visualization
        batch_to_graph  — convert multiple test cases → one merged graph
        read_state      — return state
        set_config      — set config
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.state = {
            "class": "BclirGraph",
            "initialized": True,
            "total_bcl_generated": 0,
            "total_bclir_compiled": 0,
            "total_graphs_built": 0,
            "total_nodes": 0,
            "total_edges": 0,
            "total_validation_errors": 0,
            "last_case_id": "",
            "last_graph_node_count": 0,
            "last_graph_edge_count": 0,
        }

    def _p(self, label, value):
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "case_to_bcl": self.cmd_case_to_bcl,
            "bcl_to_bclir": self.cmd_bcl_to_bclir,
            "bclir_to_graph": self.cmd_bclir_to_graph,
            "case_to_graph": self.cmd_case_to_graph,
            "validate_bclir": self.cmd_validate_bclir,
            "traverse": self.cmd_traverse,
            "to_dot": self.cmd_to_dot,
            "batch_to_graph": self.cmd_batch_to_graph,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("BCLIR_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        for key, value in params.items():
            self.state[key] = value
        return (1, {"updated": len(params)}, None)

    def cmd_case_to_bcl(self, params):
        case = params.get("case")
        if not case:
            return (0, None, ("BCLIR_NO_CASE", "no case provided", 0))
        if isinstance(case, dict):
            case = ErrorModel.from_dict(case)
        bcl = self.case_to_bcl(case)
        self.state["total_bcl_generated"] += 1
        self.state["last_case_id"] = case.case_id
        return (1, {"bcl": bcl, "case_id": case.case_id}, None)

    def cmd_bcl_to_bclir(self, params):
        bcl = params.get("bcl")
        if not bcl:
            return (0, None, ("BCLIR_NO_BCL", "no bcl packet provided", 0))
        node = self.bcl_to_bclir(bcl)
        if not node:
            return (0, None, ("BCLIR_COMPILE_FAILED", "could not compile BCL", 0))
        errors = self.validate_bclir(node)
        self.state["total_bclir_compiled"] += 1
        self.state["total_validation_errors"] += len(errors)
        return (1, {"bclir": node.to_dict(), "validation_errors": errors}, None)

    def cmd_bclir_to_graph(self, params):
        bclir = params.get("bclir")
        if not bclir:
            return (0, None, ("BCLIR_NO_NODE", "no bclir node provided", 0))
        if isinstance(bclir, dict):
            node = BCLIRNode.from_dict(bclir)
        else:
            node = bclir
        graph = self.bclir_to_graph(node)
        self.state["total_graphs_built"] += 1
        self.state["total_nodes"] += len(graph.nodes)
        self.state["total_edges"] += len(graph.edges)
        self.state["last_graph_node_count"] = len(graph.nodes)
        self.state["last_graph_edge_count"] = len(graph.edges)
        return (1, {"graph": graph.to_dict(), "dot": graph.to_dot()}, None)

    def cmd_case_to_graph(self, params):
        case = params.get("case")
        if not case:
            return (0, None, ("BCLIR_NO_CASE", "no case provided", 0))
        if isinstance(case, dict):
            case = ErrorModel.from_dict(case)
        bcl = self.case_to_bcl(case)
        bclir_node = self.bcl_to_bclir(bcl)
        if not bclir_node:
            return (0, None, ("BCLIR_COMPILE_FAILED", "could not compile BCL", 0))
        errors = self.validate_bclir(bclir_node)
        graph = self.bclir_to_graph(bclir_node)
        self.state["total_bcl_generated"] += 1
        self.state["total_bclir_compiled"] += 1
        self.state["total_graphs_built"] += 1
        self.state["total_nodes"] += len(graph.nodes)
        self.state["total_edges"] += len(graph.edges)
        self.state["last_case_id"] = case.case_id
        self.state["last_graph_node_count"] = len(graph.nodes)
        self.state["last_graph_edge_count"] = len(graph.edges)
        self.state["total_validation_errors"] += len(errors)
        return (1, {
            "case_id": case.case_id,
            "bcl": bcl,
            "bclir": bclir_node.to_dict(),
            "validation_errors": errors,
            "graph": graph.to_dict(),
            "dot": graph.to_dot(),
            "traversal": graph.traverse(),
        }, None)

    def cmd_validate_bclir(self, params):
        bclir = params.get("bclir")
        if not bclir:
            return (0, None, ("BCLIR_NO_NODE", "no bclir node provided", 0))
        if isinstance(bclir, dict):
            node = BCLIRNode.from_dict(bclir)
        else:
            node = bclir
        errors = self.validate_bclir(node)
        return (1, {"errors": errors, "valid": len(errors) == 0}, None)

    def cmd_traverse(self, params):
        graph_data = params.get("graph")
        if not graph_data:
            return (0, None, ("BCLIR_NO_GRAPH", "no graph provided", 0))
        graph = ExecutionGraph()
        for nd in graph_data.get("nodes", []):
            gn = GraphNode(id=nd["id"], label=nd["label"], node_type=nd["node_type"], data=nd.get("data", {}))
            graph.add_node(gn)
        for ed in graph_data.get("edges", []):
            graph.add_edge(ed["from"], ed["to"], ed["relation"], ed.get("label", ""))
        traversal = graph.traverse()
        return (1, {"traversal": traversal}, None)

    def cmd_to_dot(self, params):
        graph_data = params.get("graph")
        if not graph_data:
            return (0, None, ("BCLIR_NO_GRAPH", "no graph provided", 0))
        graph = ExecutionGraph()
        for nd in graph_data.get("nodes", []):
            gn = GraphNode(id=nd["id"], label=nd["label"], node_type=nd["node_type"], data=nd.get("data", {}))
            graph.add_node(gn)
        for ed in graph_data.get("edges", []):
            graph.add_edge(ed["from"], ed["to"], ed["relation"], ed.get("label", ""))
        return (1, {"dot": graph.to_dot()}, None)

    def cmd_batch_to_graph(self, params):
        cases = params.get("cases", [])
        if not cases:
            return (0, None, ("BCLIR_NO_CASES", "no cases provided", 0))
        merged_graph = ExecutionGraph()
        for case_data in cases:
            if isinstance(case_data, dict):
                case = ErrorModel.from_dict(case_data)
            else:
                case = case_data
            bcl = self.case_to_bcl(case)
            bclir_node = self.bcl_to_bclir(bcl)
            if not bclir_node:
                continue
            self.validate_bclir(bclir_node)
            graph = self.bclir_to_graph(bclir_node)
            for nid in graph.node_order:
                node = graph.nodes[nid]
                merged_graph.add_node(node)
            for edge in graph.edges:
                merged_graph.add_edge(edge.from_id, edge.to_id, edge.relation, edge.label)
        self.state["total_bcl_generated"] += len(cases)
        self.state["total_bclir_compiled"] += len(cases)
        self.state["total_graphs_built"] += 1
        self.state["total_nodes"] += len(merged_graph.nodes)
        self.state["total_edges"] += len(merged_graph.edges)
        self.state["last_graph_node_count"] = len(merged_graph.nodes)
        self.state["last_graph_edge_count"] = len(merged_graph.edges)
        return (1, {
            "case_count": len(cases),
            "graph": merged_graph.to_dict(),
            "dot": merged_graph.to_dot(),
            "traversal": merged_graph.traverse(),
            "node_count": len(merged_graph.nodes),
            "edge_count": len(merged_graph.edges),
        }, None)

    # ── Core Pipeline Methods ──

    def case_to_bcl(self, case: ErrorModel) -> str:
        """Convert an ErrorModel test case → BCL packet.

        Produces a BCL packet with the full pipeline as nested tags:
        [@CASE]{[@CASE_ID]{...}[@TRIGGER]{...}[@CAPTURE]{...}[@FIX]{...}...}
        """
        safe_broken = case.broken_code.replace("{", "(").replace("}", ")")
        safe_fixed = (case.fixed_code or "").replace("{", "(").replace("}", ")")
        safe_desc = case.description.replace("{", "(").replace("}", ")")

        parts = []
        parts.append("[@CASE]{")
        parts.append("[@CASE_ID]{" + case.case_id + "}")
        parts.append("[@FAMILY]{" + case.family + "}")
        parts.append("[@EXPECTED]{" + case.expected_exception + "}")
        parts.append("[@SEVERITY]{" + str(case.severity) + "}")
        parts.append("[@CONFIDENCE]{" + str(round(case.confidence, 4)) + "}")
        if safe_desc:
            parts.append("[@DESCRIPTION]{" + safe_desc + "}")
        if case.tags:
            parts.append("[@TAGS]{" + ",".join(case.tags) + "}")
        # Pipeline stages as nested BCL
        parts.append("[@TRIGGER]{[@BROKEN_CODE]{" + safe_broken + "}[@TIMEOUT]{10}}")
        parts.append("[@CAPTURE]{[@EXCEPTION]{" + case.expected_exception + "}[@TRACEBACK]{}[@TIMING_MS]{0.0}}")
        parts.append("[@FIX]{[@BROKEN_CODE]{" + safe_broken + "}[@EXCEPTION]{" + case.expected_exception + "}[@STRATEGY]{auto}}")
        if safe_fixed:
            parts.append("[@APPLY]{[@CANDIDATE]{" + safe_fixed + "}[@ORIGINAL]{" + safe_broken + "}}")
        parts.append("[@VALIDATE]{[@CANDIDATE]{" + safe_fixed + "}[@PY_COMPILE]{true}[@AST_PARSE]{true}[@RE_RUN]{true}}")
        parts.append("[@SCORE]{[@STRATEGY]{auto}[@SCORE]{0}[@PASSED]{false}}")
        parts.append("[@PROMOTE]{[@CONFIDENCE]{" + str(round(case.confidence, 4)) + "}[@ACTION]{keep}}")
        parts.append("}")
        return "".join(parts)

    def bcl_to_bclir(self, bcl: str) -> Optional[BCLIRNode]:
        """Compile a BCL packet → BCLIRNode tree (typed).

        Parses the BCL packet, infers types for each param, and builds
        a tree of BCLIRNode objects with typed BCLIRVal params.
        """
        # Extract the root CASE tag
        case_match = re.search(r"\[@CASE\]\{(.+)\}", bcl, re.DOTALL)
        if not case_match:
            return None
        inner = case_match.group(1)

        root = BCLIRNode(op=OP_CASE, node_id="case_root")
        root.cost_estimate = 0.01

        # Extract top-level tags from inner content
        tags = self._extract_all_tags(inner)
        for tag_name, tag_value in tags:
            if tag_name in ("CASE_ID", "FAMILY", "EXPECTED", "SEVERITY", "CONFIDENCE", "DESCRIPTION", "TAGS"):
                val = self._infer_type(tag_name, tag_value, OP_CASE)
                root.params[tag_name] = val
            elif tag_name in ("TRIGGER", "CAPTURE", "FIX", "APPLY", "VALIDATE", "SCORE", "PROMOTE"):
                child = self._compile_stage(tag_name, tag_value)
                if child:
                    root.children.append(child)

        return root

    def _compile_stage(self, op_name: str, content: str) -> Optional[BCLIRNode]:
        """Compile one pipeline stage from BCL content → BCLIRNode."""
        op = op_name
        node = BCLIRNode(op=op, node_id=op_name.lower() + "_0")
        tags = self._extract_all_tags(content)
        schema = OP_SCHEMA.get(op, {})
        for tag_name, tag_value in tags:
            val = self._infer_type(tag_name, tag_value, op)
            node.params[tag_name] = val
        # Cost estimates per op
        cost_map = {
            OP_TRIGGER: 0.5,
            OP_CAPTURE: 0.01,
            OP_FIX: 1.0,
            OP_APPLY: 0.1,
            OP_VALIDATE: 0.3,
            OP_SCORE: 0.01,
            OP_PROMOTE: 0.001,
        }
        node.cost_estimate = cost_map.get(op, 0.1)
        return node

    def _infer_type(self, param_name: str, raw_value: str, op: str) -> BCLIRVal:
        """Infer the type of a BCL value based on the param schema."""
        expected_type = OP_SCHEMA.get(op, {}).get(param_name, BCLIR_STRING)
        if expected_type == BCLIR_INT:
            try:
                return BCLIRVal(type=BCLIR_INT, value=int(raw_value))
            except ValueError:
                return BCLIRVal(type=BCLIR_STRING, value=raw_value)
        elif expected_type == BCLIR_FLOAT:
            try:
                return BCLIRVal(type=BCLIR_FLOAT, value=float(raw_value))
            except ValueError:
                return BCLIRVal(type=BCLIR_STRING, value=raw_value)
        elif expected_type == BCLIR_BOOL:
            return BCLIRVal(type=BCLIR_BOOL, value=raw_value.lower() in ("true", "1", "yes"))
        elif expected_type == BCLIR_CODE:
            restored = raw_value.replace("(", "{").replace(")", "}")
            return BCLIRVal(type=BCLIR_CODE, value=restored)
        else:
            return BCLIRVal(type=BCLIR_STRING, value=raw_value)

    def _extract_all_tags(self, text: str) -> List[Tuple[str, str]]:
        """Extract all [@TAG]{value} pairs from text (non-nested)."""
        results = []
        i = 0
        while i < len(text):
            if text[i:i+2] == "[@":
                tag_end = text.find("]", i)
                if tag_end == -1:
                    break
                tag = text[i+2:tag_end]
                brace_start = tag_end + 1
                if brace_start < len(text) and text[brace_start] == "{":
                    depth = 1
                    j = brace_start + 1
                    while j < len(text) and depth > 0:
                        if text[j] == "{":
                            depth += 1
                        elif text[j] == "}":
                            depth -= 1
                        j += 1
                    value = text[brace_start+1:j-1]
                    results.append((tag, value))
                    i = j
                else:
                    i = tag_end + 1
            else:
                i += 1
        return results

    def validate_bclir(self, node: BCLIRNode) -> List[str]:
        """Type-check a BCLIRNode tree. Returns list of error strings."""
        errors = []
        schema = OP_SCHEMA.get(node.op, {})
        for param_name, expected_type in schema.items():
            if param_name not in node.params:
                errors.append("{}: missing required param '{}'".format(node.op, param_name))
            else:
                actual_type = node.params[param_name].type
                if actual_type != expected_type:
                    errors.append("{}: param '{}' expected {} but got {}".format(
                        node.op, param_name, expected_type, actual_type))
        node.validation_errors = errors
        node.validated = True
        node.validated = len(errors) == 0
        for child in node.children:
            errors.extend(self.validate_bclir(child))
        return errors

    def bclir_to_graph(self, root: BCLIRNode) -> ExecutionGraph:
        """Build an ExecutionGraph from a BCLIRNode tree.

        Each BCLIRNode becomes a GraphNode.
        Sequential ops (CASE → TRIGGER → CAPTURE → FIX → ...) get NEXT edges.
        Branch ops (FIX → APPLY candidate 1, 2, 3) get BRANCHES edges.
        Data dependencies (VALIDATE depends on APPLY) get DEPENDS edges.
        """
        graph = ExecutionGraph()

        # Create root node
        root_gn = GraphNode(
            id=root.node_id or "root",
            label=root.params.get("CASE_ID", BCLIRVal(value="root")).value,
            node_type=root.op,
            data={k: v.value for k, v in root.params.items()},
        )
        graph.add_node(root_gn)

        # Add children as sequential pipeline
        prev_id = root_gn.id
        for i, child in enumerate(root.children):
            child_id = "{}_{}".format(child.node_id or child.op.lower(), i)
            child_gn = GraphNode(
                id=child_id,
                label=child.op,
                node_type=child.op,
                data={k: v.value for k, v in child.params.items()},
            )
            graph.add_node(child_gn)

            # Determine edge relation
            if child.op == OP_APPLY:
                relation = EDGE_BRANCHES
                label = "candidate"
            elif child.op == OP_VALIDATE:
                relation = EDGE_DEPENDS
                label = "needs apply"
            else:
                relation = EDGE_NEXT
                label = ""

            graph.add_edge(prev_id, child_id, relation, label)
            prev_id = child_id

        return graph
