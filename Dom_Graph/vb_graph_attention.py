#!/usr/bin/env python3
#[@GHOST]{[@date<2026-07-02>][@author<devin>][@session<bcl_transformer>][@file<Dom_Graph/vb_graph_attention.py>][@domain<bcl_transformer>][@authority<graph_attention>]}
#[@VBSTYLE]{[@fileid<vb_graph_attention>][@summary<8 domain graphs guide transformer attention via edge-type to attention-bias mapping. Bias added to scores before softmax like T5 relative position bias>][@class<GraphAttention>][@method<Run,load_graphs,build_bias,explain,info,read_state,set_config,p>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore|enums>][@model<one_class_one_domain_one_authority_complete>]}
#[@CLASS]{GraphAttention}
#[@METHOD]{Run,load_graphs,build_bias,explain,info,read_state,set_config,p}
"""
GraphAttention — 8 domain graphs guide transformer attention.

WHAT IT DOES:
  - Loads the 8 domain graphs (Plan, Spec, Flow, Lifecycle, Dep, Error, Orch, Gap)
    from Config.py (or MySQL if wired via db param).
  - Maps graph edge types to attention bias weights:
      FEEDS    (A->B): A attends to B          (forward, weight 1.0)
      USES     (A->B): A attends to B          (dependency, weight 1.0)
      TRIGGERS (A->B): A attends to B, B NOT A (causal, weight 1.0 one-way)
      PAIRS    (A-B):  both attend to each other (bidirectional, weight 1.0)
      WRAPS    (A->B): A attends to B + B children (hierarchical, weight 1.0)
      ENABLES  (A->B): A attends to B weakly  (weight 0.5)
      MEASURES (A->B): A attends to B low     (weight 0.3)
  - Builds an attention bias matrix (seq_len, seq_len) of float weights.
  - This bias is ADDED to attention scores before softmax (like T5 relative
    position bias). Higher bias = stronger attention. Zero bias = no edge.

USAGE:
  from vb_graph_attention import GraphAttention

  ga = GraphAttention()
  ok, data, err = ga.Run("load_graphs")
  ok, data, err = ga.Run("build_bias", {"sequence": ["Browser", "Request", "HTTP", "Response", "Parser"]})
  # data = {"bias": [[...], ...], "seq_len": 5, "edges_used": 3}

  ok, data, err = ga.Run("explain", {"sequence": ["Browser", "Request", "HTTP", "Response", "Parser"]})
  # data = {"explanation": "Browser ->USE-> Request (1.0)..."}

  ok, data, err = ga.Run("info")
  # data = config snapshot

CONFIG:
  config["graphs"] = ["Plan", "Spec", "Flow", "Lifecycle", "Dep", "Error", "Orch", "Gap"]
  config["edge_weights"] = {"FEEDS": 1.0, "USES": 1.0, "TRIGGERS": 1.0,
                            "PAIRS": 1.0, "WRAPS": 1.0, "ENABLES": 0.5, "MEASURES": 0.3}
  config["default_bias"] = 0.0
  config["source"] = "config"  # or "mysql"
"""

import sys
import os

# ─── Edge type to attention weight mapping ───────────────────────────────────
# These are the DEFAULT weights. Config can override via set_config.
# The bias matrix cell [i][j] = how much token i attends to token j.
# A higher weight means stronger attention (added to score before softmax).

EDGE_WEIGHTS = {
    "FEEDS": 1.0,       # forward attention: A can attend to B
    "USES": 1.0,        # dependency attention: A attends to B
    "TRIGGERS": 1.0,    # causal attention: A attends to B, B cannot attend back
    "PAIRS": 1.0,       # bidirectional: both attend to each other
    "WRAPS": 1.0,       # hierarchical: A attends to B and B children
    "ENABLES": 0.5,     # weak attention: scaled by 0.5
    "MEASURES": 0.3,    # low weight attention: scaled by 0.3
}

# Edge directions: which direction(s) the bias applies
# "forward" = bias[row=A][col=B]
# "reverse" = bias[row=B][col=A]
# "both"    = bias in both directions
EDGE_DIRECTIONS = {
    "FEEDS": "forward",
    "USES": "forward",
    "TRIGGERS": "forward",   # causal: only A->B, NOT B->A
    "PAIRS": "both",          # bidirectional
    "WRAPS": "forward",       # A attends to B + B children (handled specially)
    "ENABLES": "forward",
    "MEASURES": "forward",
}

# The 8 graph viewer names
GRAPH_NAMES = ["Plan", "Spec", "Flow", "Lifecycle", "Dep", "Error", "Orch", "Gap"]


class GraphAttention:
    """
    8 domain graphs guide transformer attention.
    Edge types map to attention bias weights added to scores before softmax.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "graphs": list(GRAPH_NAMES),
                "edge_weights": dict(EDGE_WEIGHTS),
                "default_bias": 0.0,
                "source": "config",   # "config" or "mysql"
                "d_model": 384,
                "n_heads": 6,
            },
            "db": db,
            "mem": mem,
            "loaded": False,
            "classes": [],       # list of (name, kind, methods, desc)
            "edges": [],         # list of (src, dst, edge_type)
            "flows": {},         # class_name -> list of (kind, text)
            "categories": {},    # category -> list of class names
            "class_children": {},  # class_name -> list of child class names (for WRAPS)
            "class_index": {},     # class_name -> index in classes list
            "last_bias": None,     # last computed bias matrix
            "last_sequence": [],   # last sequence used
            "last_explanation": [],  # last explanation lines
        }
        if param and "source" in param:
            self.state["config"]["source"] = param["source"]
        if param and "graphs" in param:
            self.state["config"]["graphs"] = param["graphs"]
        if param and "edge_weights" in param:
            for k, v in param["edge_weights"].items():
                self.state["config"]["edge_weights"][k] = v

    def Run(self, command, params=None):
        dispatch = {
            "load_graphs": self.cmd_load_graphs,
            "build_bias": self.cmd_build_bias,
            "explain": self.cmd_explain,
            "info": self.cmd_info,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ══════════════════════════════════════════════════════════════════════════
    # INTERNAL: load graph data from Config.py or MySQL
    # ══════════════════════════════════════════════════════════════════════════

    def loadFromConfig(self):
        """Load GRAPH_CLASSES, GRAPH_EDGES, GRAPH_FLOWS from Config.py."""
        try:
            # Config.py is in the same directory (Dom_Graph/)
            graphDir = os.path.dirname(os.path.abspath(__file__))
            if graphDir not in sys.path:
                sys.path.insert(0, graphDir)
            from Config import Config as DomConfig
        except Exception as e:
            return (0, None, ("ERR_IMPORT", "Cannot import Config: %s" % str(e), 0))

        classes = list(DomConfig.GRAPH_CLASSES)
        edges = list(DomConfig.GRAPH_EDGES)
        flows = {}
        if hasattr(DomConfig, "GRAPH_FLOWS"):
            flows = dict(DomConfig.GRAPH_FLOWS)
        categories = {}
        if hasattr(DomConfig, "GRAPH_CATEGORIES"):
            categories = dict(DomConfig.GRAPH_CATEGORIES)

        self.state["classes"] = classes
        self.state["edges"] = edges
        self.state["flows"] = flows
        self.state["categories"] = categories
        self.state["loaded"] = True

        # Build class index and children map for WRAPS edges
        self.buildClassIndex()
        self.buildChildrenMap()

        return (1, {
            "classes": len(classes),
            "edges": len(edges),
            "flows": len(flows),
            "categories": len(categories),
            "source": "config",
        }, None)

    def loadFromMysql(self):
        """Load graph data from MySQL if db connection is provided."""
        db = self.state.get("db")
        if db is None:
            return (0, None, ("ERR_NO_DB", "No db connection provided for mysql source", 0))
        try:
            cursor = db.cursor()
            # Load classes
            cursor.execute("SELECT class_name, kind, methods, description FROM dom_graph_classes")
            classes = []
            for row in cursor.fetchall():
                classes.append((row[0], row[1], row[2], row[3]))
            # Load edges
            cursor.execute("SELECT src, dst, edge_type FROM dom_graph_edges")
            edges = []
            for row in cursor.fetchall():
                edges.append((row[0], row[1], row[2]))
            # Load flows
            cursor.execute("SELECT class_name, kind, text FROM dom_graph_flows")
            flows = {}
            for row in cursor.fetchall():
                cname = row[0]
                if cname not in flows:
                    flows[cname] = []
                flows[cname].append((row[1], row[2]))
            cursor.close()

            self.state["classes"] = classes
            self.state["edges"] = edges
            self.state["flows"] = flows
            self.state["loaded"] = True
            self.buildClassIndex()
            self.buildChildrenMap()

            return (1, {
                "classes": len(classes),
                "edges": len(edges),
                "flows": len(flows),
                "source": "mysql",
            }, None)
        except Exception as e:
            return (0, None, ("ERR_MYSQL", "MySQL load failed: %s" % str(e), 0))

    def buildClassIndex(self):
        """Build class_name -> index mapping."""
        idx = {}
        for i, entry in enumerate(self.state["classes"]):
            name = entry[0]
            idx[name] = i
        self.state["class_index"] = idx

    def buildChildrenMap(self):
        """
        Build class_name -> list of children for WRAPS edges.
        WRAPS (A->B) means A wraps B. B children = classes that B itself wraps
        or classes in the same category as B (for hierarchical attention).
        We use category membership: children of B = all classes in B category
        excluding B itself. This gives WRAPS its hierarchical scope.
        """
        children = {}
        categories = self.state.get("categories", {})

        # Build reverse: class -> category
        classToCat = {}
        for cat, members in categories.items():
            for m in members:
                classToCat[m] = cat

        # For each class, children = same-category members (minus self)
        for entry in self.state["classes"]:
            name = entry[0]
            cat = classToCat.get(name)
            if cat and cat in categories:
                children[name] = [m for m in categories[cat] if m != name]
            else:
                children[name] = []

        # Also add explicit WRAPS targets as children
        for src, dst, etype in self.state["edges"]:
            if etype == "WRAPS":
                if src not in children:
                    children[src] = []
                if dst not in children[src]:
                    children[src].append(dst)

        self.state["class_children"] = children

    # ══════════════════════════════════════════════════════════════════════════
    # INTERNAL: build attention bias matrix
    # ══════════════════════════════════════════════════════════════════════════

    def buildBiasMatrix(self, sequence):
        """
        Build (seq_len x seq_len) attention bias matrix.
        bias[i][j] = weight that token i can attend to token j.
        Added to attention scores before softmax (like T5 relative position bias).
        """
        seqLen = len(sequence)
        weights = self.state["config"]["edge_weights"]
        defaultBias = self.state["config"]["default_bias"]

        # Initialize bias matrix with default (0.0 = no edge influence)
        bias = []
        for i in range(seqLen):
            row = []
            for j in range(seqLen):
                row.append(defaultBias)
            bias.append(row)

        # Build edge lookup: (src, dst) -> edge_type
        # Also build reverse for quick lookup
        edgeLookup = {}
        for src, dst, etype in self.state["edges"]:
            edgeLookup[(src, dst)] = etype

        # Build set of all class names that exist in graph
        allClassNames = set(self.state["class_index"].keys())
        children = self.state.get("class_children", {})

        explanations = []

        for i in range(seqLen):
            tokenA = sequence[i]
            for j in range(seqLen):
                if i == j:
                    # Self-attention: token attends to itself (weight 1.0 baseline)
                    bias[i][j] = 1.0
                    continue

                tokenB = sequence[j]
                weight = defaultBias

                # Check direct edge A->B
                edgeType = edgeLookup.get((tokenA, tokenB))
                if edgeType:
                    direction = EDGE_DIRECTIONS.get(edgeType, "forward")
                    ew = weights.get(edgeType, 1.0)

                    if edgeType == "TRIGGERS":
                        # Causal: A attends to B, but B does NOT attend back to A
                        # So bias[i][j] = weight, but bias[j][i] stays 0
                        weight = ew
                        explanations.append("%s ->TRIGGERS-> %s (w=%.1f, causal one-way)" % (tokenA, tokenB, ew))
                    elif edgeType == "PAIRS":
                        # Bidirectional: both directions get weight
                        weight = ew
                        explanations.append("%s <-PAIRS-> %s (w=%.1f, bidirectional)" % (tokenA, tokenB, ew))
                    elif edgeType == "WRAPS":
                        # Hierarchical: A attends to B and B children
                        weight = ew
                        explanations.append("%s ->WRAPS-> %s (w=%.1f, hierarchical)" % (tokenA, tokenB, ew))
                    else:
                        weight = ew
                        explanations.append("%s ->%s-> %s (w=%.1f)" % (tokenA, edgeType, tokenB, ew))

                # Check WRAPS children: if A wraps B, and j is a child of B
                if weight == defaultBias:
                    for wrappedName, wrappedChildren in children.items():
                        if wrappedName == tokenA:
                            # tokenA wraps something. Check if tokenB is a child
                            if tokenB in wrappedChildren:
                                # Check if there is a WRAPS edge A->wrappedName
                                wrapEdge = edgeLookup.get((tokenA, wrappedName))
                                if wrapEdge == "WRAPS":
                                    weight = weights.get("WRAPS", 1.0)
                                    explanations.append("%s ->WRAPS(child)-> %s (w=%.1f, via %s)" % (tokenA, tokenB, weight, wrappedName))
                                    break

                # Check reverse edge B->A for PAIRS (already handled above via both)
                # For PAIRS we set both directions, so when we process (i,j) where
                # edge is (B,A) with PAIRS, we also get it here
                if weight == defaultBias:
                    revEdge = edgeLookup.get((tokenB, tokenA))
                    if revEdge == "PAIRS":
                        weight = weights.get("PAIRS", 1.0)
                        explanations.append("%s <-PAIRS- %s (w=%.1f, bidirectional)" % (tokenA, tokenB, weight))

                # Check TRIGGERS reverse: B->A TRIGGERS means A CANNOT attend to B
                # (causal: only trigger source attends to target, not reverse)
                revEdge2 = edgeLookup.get((tokenB, tokenA))
                if revEdge2 == "TRIGGERS":
                    # B triggers A. So A is the target. A should NOT attend back to B
                    # for the TRIGGERS relationship. But A may attend to B via other edges.
                    # We do NOT zero out here because other edges may apply.
                    # The TRIGGERS forward direction already set bias[B][A].
                    pass

                bias[i][j] = weight

        self.state["last_bias"] = bias
        self.state["last_sequence"] = list(sequence)
        self.state["last_explanation"] = explanations
        return bias, explanations

    # ══════════════════════════════════════════════════════════════════════════
    # COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    def cmd_load_graphs(self, params):
        """Load graph data from Config.py or MySQL."""
        source = self.p(params, "source", self.state["config"]["source"])
        self.state["config"]["source"] = source

        if source == "mysql":
            ok, data, err = self.loadFromMysql()
            if not ok:
                return (0, None, err)
            return (1, data, None)
        else:
            ok, data, err = self.loadFromConfig()
            if not ok:
                return (0, None, err)
            return (1, data, None)

    def cmd_build_bias(self, params):
        """Build attention bias matrix for a sequence of class names."""
        if not self.state["loaded"]:
            ok, data, err = self.cmd_load_graphs({})
            if not ok:
                return (0, None, err)

        sequence = self.p(params, "sequence")
        if not sequence or not isinstance(sequence, list):
            return (0, None, ("ERR_PARAMS", "sequence (list of class names) required", 0))

        if len(sequence) == 0:
            return (0, None, ("ERR_PARAMS", "sequence must not be empty", 0))

        # Validate class names exist in graph
        classIndex = self.state["class_index"]
        unknown = []
        for name in sequence:
            if name not in classIndex:
                unknown.append(name)
        if unknown:
            return (0, None, ("ERR_UNKNOWN_CLASS", "Classes not in graph: %s" % ", ".join(unknown), 0))

        bias, explanations = self.buildBiasMatrix(sequence)
        seqLen = len(sequence)

        # Count edges used
        edgesUsed = len(explanations)

        return (1, {
            "bias": bias,
            "seq_len": seqLen,
            "sequence": list(sequence),
            "edges_used": edgesUsed,
            "edge_weights": dict(self.state["config"]["edge_weights"]),
        }, None)

    def cmd_explain(self, params):
        """Human-readable explanation of attention weights for a sequence."""
        if not self.state["loaded"]:
            ok, data, err = self.cmd_load_graphs({})
            if not ok:
                return (0, None, err)

        sequence = self.p(params, "sequence")
        if not sequence or not isinstance(sequence, list):
            return (0, None, ("ERR_PARAMS", "sequence (list of class names) required", 0))

        if len(sequence) == 0:
            return (0, None, ("ERR_PARAMS", "sequence must not be empty", 0))

        # Build bias if not already built for this sequence
        if self.state["last_sequence"] != list(sequence):
            bias, explanations = self.buildBiasMatrix(sequence)
        else:
            explanations = self.state.get("last_explanation", [])
            bias = self.state.get("last_bias")

        # Build human-readable text
        lines = []
        lines.append("GraphAttention Explanation")
        lines.append("=" * 50)
        lines.append("Sequence: %s" % " -> ".join(sequence))
        lines.append("Seq length: %d" % len(sequence))
        lines.append("")
        lines.append("Edge type weight mapping:")
        for etype, w in self.state["config"]["edge_weights"].items():
            direction = EDGE_DIRECTIONS.get(etype, "forward")
            lines.append("  %-10s weight=%.1f  direction=%s" % (etype, w, direction))
        lines.append("")
        lines.append("Edges found in sequence:")
        if explanations:
            for line in explanations:
                lines.append("  %s" % line)
        else:
            lines.append("  (no graph edges between sequence tokens)")
        lines.append("")
        lines.append("Bias matrix (rows=attend_from, cols=attend_to):")
        if bias:
            # Header
            header = "       " + "  ".join(["%8s" % n[:8] for n in sequence])
            lines.append(header)
            for i, row in enumerate(bias):
                rowStr = "%8s " % sequence[i][:8]
                vals = "  ".join(["%8.1f" % v for v in row])
                lines.append(rowStr + vals)
        lines.append("")
        lines.append("Legend: 1.0=full attention  0.5=weak(ENABLES)  0.3=low(MEASURES)  0.0=no edge")

        text = "\n".join(lines)
        return (1, {
            "explanation": text,
            "lines": lines,
            "edges_found": len(explanations),
            "sequence": list(sequence),
        }, None)

    def cmd_info(self, params):
        """Return config and status info."""
        info = {
            "config": dict(self.state["config"]),
            "loaded": self.state["loaded"],
            "class_count": len(self.state["classes"]),
            "edge_count": len(self.state["edges"]),
            "flow_count": len(self.state["flows"]),
            "graphs": list(self.state["config"]["graphs"]),
            "edge_weights": dict(self.state["config"]["edge_weights"]),
            "edge_directions": dict(EDGE_DIRECTIONS),
            "source": self.state["config"]["source"],
        }
        return (1, info, None)


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT (for testing)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ga = GraphAttention()

    # Load graphs
    ok, data, err = ga.Run("load_graphs")
    if not ok:
        sys.stderr.write("load_graphs failed: %s\n" % str(err))
        sys.exit(1)
    sys.stderr.write("Loaded: %s\n" % str(data))

    # Info
    ok, data, err = ga.Run("info")
    if not ok:
        sys.stderr.write("info failed: %s\n" % str(err))
        sys.exit(1)
    sys.stderr.write("Info: %s\n" % str(data))

    # Build bias for 5 Web domain class names
    testSeq = ["Browser", "Request", "HTTP", "Response", "Parser"]
    ok, data, err = ga.Run("build_bias", {"sequence": testSeq})
    if not ok:
        sys.stderr.write("build_bias failed: %s\n" % str(err))
        sys.exit(1)
    sys.stderr.write("Bias built: seq_len=%d edges_used=%d\n" % (data["seq_len"], data["edges_used"]))

    # Explain
    ok, data, err = ga.Run("explain", {"sequence": testSeq})
    if not ok:
        sys.stderr.write("explain failed: %s\n" % str(err))
        sys.exit(1)
    sys.stdout.write(data["explanation"] + "\n")
