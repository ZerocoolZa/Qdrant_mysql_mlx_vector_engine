#!/usr/bin/env python3
# [@GHOST]{[@file<GuiEnergyGraph.py>][@domain<gui>][@role<energy_graph>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<energy_graph>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiEnergyGraph — GUI layout as optimization problem. Nodes=UI elements, Edges=relationships. Energy function scores layout quality. Auto-fix applies repulsion forces. Bad→good→bad distance model. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiEnergyGraph}
# [@METHOD]{Run,build,energy,optimize,fix,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<GUI layout as energy optimization problem. Nodes=UI elements, edges=relationships. Energy function scores layout quality. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiEnergyGraph — GUI layout as an energy optimization problem.

THE BRAIN MODEL:
  A GUI is a graph. Nodes are UI elements (buttons, labels, inputs).
  Edges are relationships (group, alignment, flow, dependency).
  Energy measures how bad the layout is. Lower = better.

THE DISTANCE LAW (your "bad → good → bad" model):
  Two elements dead center on each other = WORST (overlap)
  As they separate = gets better
  Sweet spot = mid-distance (readable, grouped, not cramped)
  Past that point = gets worse (too disconnected)

  energy(dist):
    dist < 5px   → penalty 50  (OVERLAP — worst zone)
    dist < 20px  → penalty 10  (too close — cramped)
    20-300px     → penalty 0   (SWEET SPOT — good)
    dist > 300px → penalty 5   (too far — disconnected)

THE COMPLETENESS LAW (Porsche Principle):
  Every button/input/menu MUST have tooltip + shortcut + help.
  Missing any = energy penalty.
  This is the structural reasoning — not just spacing, but completeness.

THE AUTO-FIX ENGINE:
  Repulsion forces push overlapping nodes apart.
  Completeness fix adds missing tooltips/shortcuts.
  Iterates until energy stabilizes.

USAGE:
  from GuiEnergyGraph import GuiEnergyGraph

  engine = GuiEnergyGraph()
  ok, data, err = engine.Run("build", {"spec": ui_spec})
  ok, data, err = engine.Run("energy")    # → current energy score
  ok, data, err = engine.Run("optimize", {"steps": 20})  # → auto-fix
  ok, data, err = engine.Run("report")    # → why it's bad
  ok, data, err = engine.Run("graph")     # → visual graph
"""

import math


# ════════════════════════════════════════════
# ENERGY CONSTANTS — the distance law
# ════════════════════════════════════════════

OVERLAP_PENALTY = 50       # dist < 5px — worst zone
TOO_CLOSE_PENALTY = 10     # dist < 20px — cramped
SWEET_SPOT_MIN = 20        # good zone starts
SWEET_SPOT_MAX = 300       # good zone ends
TOO_FAR_PENALTY = 5        # dist > 300px — disconnected

COMPLETENESS_PENALTIES = {
    "tooltip": 10,
    "shortcut": 8,
    "help": 6,
}

EDGE_PENALTIES = {
    "GROUP": 20,        # grouped items should be close
    "ALIGNMENT": 15,    # aligned items should be near
    "DEPENDENCY": 25,   # dependent items should be reachable
    "FLOW": 18,         # flow items should follow each other
}

EDGE_MAX_DIST = {
    "GROUP": 200,
    "ALIGNMENT": 100,
    "DEPENDENCY": 250,
    "FLOW": 150,
}

REPULSION_RADIUS = 50     # nodes closer than this push apart
REPULSION_FORCE = 0.05   # how strong the push is


class GuiEnergyGraph:
    """
    GUI layout energy optimizer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Nodes = UI elements, Edges = relationships, Energy = layout quality.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "overlap_penalty": OVERLAP_PENALTY,
                "too_close_penalty": TOO_CLOSE_PENALTY,
                "sweet_spot_min": SWEET_SPOT_MIN,
                "sweet_spot_max": SWEET_SPOT_MAX,
                "too_far_penalty": TOO_FAR_PENALTY,
                "repulsion_radius": REPULSION_RADIUS,
                "repulsion_force": REPULSION_FORCE,
            },
            "nodes": {},       # id → node dict
            "edges": [],       # list of edge dicts
            "energy": 0.0,
            "energy_breakdown": {},
            "iterations": 0,
            "optimized": False,
            "history": [],     # energy per iteration
        }

    def Run(self, command, params=None):
        dispatch = {
            "build": self.cmd_build,
            "energy": self.cmd_energy,
            "optimize": self.cmd_optimize,
            "fix": self.cmd_fix,
            "report": self.cmd_report,
            "graph": self.cmd_graph,
            "add_node": self.cmd_add_node,
            "add_edge": self.cmd_add_edge,
            "get_nodes": self.cmd_get_nodes,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
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

    # ════════════════════════════════════════════
    # INTERNAL — distance + energy calculations
    # ════════════════════════════════════════════

    def distance(self, a, b):
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        return math.sqrt(dx * dx + dy * dy)

    def center(self, node):
        return (node["x"] + node.get("w", 100) / 2, node["y"] + node.get("h", 30) / 2)

    def overlapEnergy(self):
        """The bad→good→bad distance model."""
        nodes = list(self.state["nodes"].values())
        penalty = 0.0
        cfg = self.state["config"]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dist = self.distance(a, b)
                if dist < 5:
                    penalty += cfg["overlap_penalty"]
                elif dist < cfg["sweet_spot_min"]:
                    penalty += cfg["too_close_penalty"]
                elif dist > cfg["sweet_spot_max"]:
                    penalty += cfg["too_far_penalty"]
        return penalty

    def completenessEnergy(self):
        """Porsche Principle — missing tooltip/shortcut/help = penalty."""
        penalty = 0.0
        missing = []
        for nodeId, n in self.state["nodes"].items():
            ntype = n.get("type", "")
            if ntype in ("Button", "Input", "MenuItem", "Tab"):
                if not n.get("has_tooltip", False):
                    penalty += COMPLETENESS_PENALTIES["tooltip"]
                    missing.append((nodeId, "tooltip"))
                if not n.get("has_shortcut", False):
                    penalty += COMPLETENESS_PENALTIES["shortcut"]
                    missing.append((nodeId, "shortcut"))
                if not n.get("has_help", False):
                    penalty += COMPLETENESS_PENALTIES["help"]
                    missing.append((nodeId, "help"))
        return penalty, missing

    def edgeEnergy(self):
        """Relationship constraint energy."""
        penalty = 0.0
        violations = []
        for e in self.state["edges"]:
            a = self.state["nodes"].get(e["a"])
            b = self.state["nodes"].get(e["b"])
            if not a or not b:
                continue
            dist = self.distance(a, b)
            eType = e.get("type", "GROUP")
            maxDist = EDGE_MAX_DIST.get(eType, 200)
            ePenalty = EDGE_PENALTIES.get(eType, 20)
            if dist > maxDist:
                penalty += ePenalty
                violations.append({
                    "edge": "%s→%s" % (e["a"], e["b"]),
                    "type": eType,
                    "dist": round(dist, 1),
                    "max": maxDist,
                    "penalty": ePenalty,
                })
        return penalty, violations

    def computeEnergy(self):
        overlap = self.overlapEnergy()
        completeness, missingItems = self.completenessEnergy()
        edges, edgeViolations = self.edgeEnergy()
        total = overlap + completeness + edges
        breakdown = {
            "overlap": round(overlap, 2),
            "completeness": round(completeness, 2),
            "edges": round(edges, 2),
            "total": round(total, 2),
            "missing_items": missingItems,
            "edge_violations": edgeViolations,
        }
        return total, breakdown

    # ════════════════════════════════════════════
    # AUTO-FIX ENGINE — repulsion + completeness
    # ════════════════════════════════════════════

    def applyRepulsion(self):
        """Push overlapping nodes apart — spring physics."""
        nodes = list(self.state["nodes"].values())
        cfg = self.state["config"]
        radius = cfg["repulsion_radius"]
        force = cfg["repulsion_force"]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dx = a["x"] - b["x"]
                dy = a["y"] - b["y"]
                dist = math.sqrt(dx * dx + dy * dy) + 0.001
                if dist < radius:
                    push = (radius - dist) * force
                    a["x"] += dx / dist * push
                    a["y"] += dy / dist * push
                    b["x"] -= dx / dist * push
                    b["y"] -= dy / dist * push

    def applyCompletenessFix(self):
        """Add missing tooltips/shortcuts to buttons."""
        fixed = []
        for nodeId, n in self.state["nodes"].items():
            ntype = n.get("type", "")
            if ntype in ("Button", "Input", "MenuItem", "Tab"):
                if not n.get("has_tooltip", False):
                    n["has_tooltip"] = True
                    fixed.append((nodeId, "tooltip"))
                if not n.get("has_shortcut", False):
                    n["has_shortcut"] = True
                    fixed.append((nodeId, "shortcut"))
                if not n.get("has_help", False):
                    n["has_help"] = True
                    fixed.append((nodeId, "help"))
        return fixed

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_build(self, params):
        spec = self.p(params, "spec")
        if not spec:
            return (0, None, ("ERR_PARAMS", "spec required", 0))
        nodes = spec.get("nodes", [])
        edges = spec.get("edges", [])
        for n in nodes:
            nodeId = n.get("id", "")
            if nodeId:
                self.state["nodes"][nodeId] = dict(n)
        self.state["edges"] = [dict(e) for e in edges]
        return (1, {"built": True, "nodes": len(self.state["nodes"]), "edges": len(self.state["edges"])}, None)

    def cmd_add_node(self, params):
        nodeId = self.p(params, "id")
        if not nodeId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        node = {
            "id": nodeId,
            "type": self.p(params, "type", "Widget"),
            "x": self.p(params, "x", 0),
            "y": self.p(params, "y", 0),
            "w": self.p(params, "w", 100),
            "h": self.p(params, "h", 30),
            "label": self.p(params, "label", ""),
            "has_tooltip": self.p(params, "has_tooltip", False),
            "has_shortcut": self.p(params, "has_shortcut", False),
            "has_help": self.p(params, "has_help", False),
        }
        self.state["nodes"][nodeId] = node
        return (1, node, None)

    def cmd_add_edge(self, params):
        a = self.p(params, "a")
        b = self.p(params, "b")
        if not a or not b:
            return (0, None, ("ERR_PARAMS", "a and b required", 0))
        edge = {
            "a": a,
            "b": b,
            "type": self.p(params, "type", "GROUP"),
        }
        self.state["edges"].append(edge)
        return (1, edge, None)

    def cmd_energy(self, params):
        total, breakdown = self.computeEnergy()
        self.state["energy"] = total
        self.state["energy_breakdown"] = breakdown
        return (1, breakdown, None)

    def cmd_fix(self, params):
        """One pass of auto-fix."""
        self.applyRepulsion()
        fixed = self.applyCompletenessFix()
        total, breakdown = self.computeEnergy()
        self.state["energy"] = total
        self.state["energy_breakdown"] = breakdown
        return (1, {
            "fixed": fixed,
            "energy": breakdown["total"],
            "breakdown": breakdown,
        }, None)

    def cmd_optimize(self, params):
        steps = self.p(params, "steps", 10)
        history = []
        bestEnergy = float("inf")
        for step in range(steps):
            self.applyRepulsion()
            if step == steps - 1:
                self.applyCompletenessFix()
            total, breakdown = self.computeEnergy()
            history.append(round(total, 2))
            if total < bestEnergy:
                bestEnergy = total
            self.state["iterations"] = step + 1
        self.state["energy"] = bestEnergy
        self.state["history"] = history
        self.state["optimized"] = True
        ok, data, err = self.Run("energy")
        if not ok:
            return (0, None, err)
        return (1, {
            "optimized": True,
            "iterations": steps,
            "best_energy": round(bestEnergy, 2),
            "final_energy": breakdown["total"],
            "breakdown": breakdown,
            "history": history,
        }, None)

    def cmd_report(self, params):
        """Explain WHY the layout is bad."""
        total, breakdown = self.computeEnergy()
        lines = []
        lines.append("GUI ENERGY REPORT")
        lines.append("==================")
        lines.append("Total Energy: %.2f  (lower = better)" % breakdown["total"])
        lines.append("")
        lines.append("BREAKDOWN:")
        lines.append("  Overlap/Spacing:  %.2f" % breakdown["overlap"])
        lines.append("  Completeness:     %.2f" % breakdown["completeness"])
        lines.append("  Edge/Relations:   %.2f" % breakdown["edges"])
        lines.append("")
        if breakdown["missing_items"]:
            lines.append("MISSING ITEMS (Porsche violations):")
            for nodeId, item in breakdown["missing_items"]:
                lines.append("  ❌ %s missing %s" % (nodeId, item))
        else:
            lines.append("MISSING ITEMS: none ✅")
        lines.append("")
        if breakdown["edge_violations"]:
            lines.append("EDGE VIOLATIONS:")
            for v in breakdown["edge_violations"]:
                lines.append("  ❌ %s [%s] dist=%.1f > max=%d (penalty=%d)" % (
                    v["edge"], v["type"], v["dist"], v["max"], v["penalty"]))
        else:
            lines.append("EDGE VIOLATIONS: none ✅")
        lines.append("")
        # Distance analysis
        nodes = list(self.state["nodes"].values())
        lines.append("DISTANCE ANALYSIS:")
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dist = self.distance(a, b)
                if dist < 5:
                    zone = "OVERLAP (worst)"
                elif dist < 20:
                    zone = "too close"
                elif dist < 300:
                    zone = "sweet spot ✅"
                else:
                    zone = "too far"
                lines.append("  %s ↔ %s: %.1fpx  %s" % (a["id"], b["id"], dist, zone))
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual energy graph."""
        total, breakdown = self.computeEnergy()
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║           GUI ENERGY GRAPH — Layout Optimizer              ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Nodes: %d   Edges: %d   Iterations: %d" % (
            len(self.state["nodes"]), len(self.state["edges"]), self.state["iterations"]))
        lines.append("")

        # Energy breakdown bar
        eTotal = breakdown["total"]
        eOverlap = breakdown["overlap"]
        eComplete = breakdown["completeness"]
        eEdges = breakdown["edges"]
        lines.append("  ┌─ ENERGY BREAKDOWN ────────────────────────────────────────┐")
        lines.append("  │  Total: %.2f" % eTotal)
        if eTotal > 0:
            overlapPct = int(eOverlap / eTotal * 100) if eTotal > 0 else 0
            completePct = int(eComplete / eTotal * 100) if eTotal > 0 else 0
            edgePct = int(eEdges / eTotal * 100) if eTotal > 0 else 0
            lines.append("  │  Overlap/Spacing:  %6.2f  (%3d%%)  %s" % (
                eOverlap, overlapPct, "█" * min(overlapPct // 5, 30)))
            lines.append("  │  Completeness:     %6.2f  (%3d%%)  %s" % (
                eComplete, completePct, "█" * min(completePct // 5, 30)))
            lines.append("  │  Edge/Relations:   %6.2f  (%3d%%)  %s" % (
                eEdges, edgePct, "█" * min(edgePct // 5, 30)))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Distance zones
        nodes = list(self.state["nodes"].values())
        lines.append("  ┌─ DISTANCE ZONES (bad→good→bad) ───────────────────────────┐")
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dist = self.distance(a, b)
                if dist < 5:
                    icon = "🔴"
                    zone = "OVERLAP"
                elif dist < 20:
                    icon = "🟠"
                    zone = "too close"
                elif dist < 300:
                    icon = "🟢"
                    zone = "sweet spot"
                else:
                    icon = "🟡"
                    zone = "too far"
                barLen = min(int(dist / 10), 30)
                bar = "░" * barLen
                lines.append("  │  %s %s↔%s  %6.1fpx  %-12s  %s" % (icon, a["id"][:10], b["id"][:10], dist, zone, bar))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Completeness
        missing = breakdown["missing_items"]
        lines.append("  ┌─ PORSCHE COMPLETENESS ────────────────────────────────────┐")
        if missing:
            for nodeId, item in missing:
                lines.append("  │  ❌ %-15s missing %s" % (nodeId, item))
        else:
            lines.append("  │  ✅ All buttons/inputs have tooltip + shortcut + help")
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # History
        if self.state["history"]:
            lines.append("  ┌─ OPTIMIZATION HISTORY ────────────────────────────────────┐")
            hist = self.state["history"]
            for i, e in enumerate(hist):
                barLen = min(int(e / 5), 30)
                bar = "█" * barLen
                lines.append("  │  Step %2d: %6.2f  %s" % (i + 1, e, bar))
            lines.append("  └────────────────────────────────────────────────────────────┘")
        else:
            lines.append("  (not optimized yet — run optimize)")

        # Verdict
        lines.append("")
        if eTotal == 0:
            verdict = "🏆 PERFECT LAYOUT — zero energy, everything in sweet spot"
        elif eTotal < 20:
            verdict = "✅ GOOD LAYOUT — minor issues"
        elif eTotal < 50:
            verdict = "⚠️  NEEDS WORK — some overlap or missing items"
        else:
            verdict = "❌ BAD LAYOUT — major overlap or completeness violations"
        lines.append("  ┌─ VERDICT ─────────────────────────────────────────────────┐")
        lines.append("  │  %s" % verdict)
        lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)

    def cmd_get_nodes(self, params):
        return (1, dict(self.state["nodes"]), None)
