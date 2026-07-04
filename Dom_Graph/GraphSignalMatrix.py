#!/usr/bin/env python3
# [@GHOST]{[@file<GraphSignalMatrix.py>][@domain<graph>][@role<signal_matrix>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<signal_matrix>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GraphSignalMatrix — GUI as weighted signal matrix. Nodes/edges have weights (positive=good, negative=bad). Weights change as layout evolves. Signals highlight where to look. Overlay compares bad vs good. Matrix output for model review. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GraphSignalMatrix}
# [@METHOD]{Run,snapshot,weight,signal,overlay,diff,matrix,evolve,compare,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<GUI as weighted signal matrix for AI model review. Snapshot/overlay/diff/matrix operations. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GraphSignalMatrix — GUI as a weighted signal matrix for AI model review.

THE VISION:
  A GUI is a graph. Every element has a WEIGHT.
  Weights are numbers — positive = good, negative = bad.
  As the layout evolves, weights CHANGE:
    - Element moves to sweet spot → weight INCREASES (gains weight)
    - Elements overlap → weight DECREASES (loses weight)
    - Missing tooltip → weight goes NEGATIVE (signal: fix this)
    - All tooltips present → weight goes POSITIVE (signal: good here)

THE SIGNAL SYSTEM:
  Signals tell the model WHERE TO LOOK:
    🔴 STRONG_NEGATIVE  → critical problem, fix immediately
    🟠 NEGATIVE         → problem area, should fix
    🟡 NEUTRAL          → borderline, could improve
    🟢 POSITIVE         → good, no action needed
    🔵 STRONG_POSITIVE  → excellent, model reference point

THE OVERLAY (comparative):
  Take a BAD graph snapshot. Take a GOOD graph snapshot.
  Overlay them. The DIFF is the improvement plan.
  - Where weight increased → green signal (improved)
  - Where weight decreased → red signal (regressed)
  - Where weight unchanged → gray signal (no change)
  Models review the overlay and learn what fixes work.

THE MATRIX:
  The entire GUI as a matrix of numbers:
    Row = element ID
    Col = dimension (spacing, completeness, alignment, flow, total)
  Value = weight (-100 to +100)
  Models can read this matrix and reason over it.

USAGE:
  from GraphSignalMatrix import GraphSignalMatrix

  mx = GraphSignalMatrix()
  mx.Run("snapshot", {"id": "before", "nodes": [...], "edges": [...]})
  # ... user moves things, optimizer runs ...
  mx.Run("snapshot", {"id": "after", "nodes": [...], "edges": [...]})
  mx.Run("overlay", {"before": "before", "after": "after"})
  mx.Run("matrix")  # → numeric matrix for model review
  mx.Run("signal")  # → signals telling model where to look
  mx.Run("graph")   # → visual signal graph
"""

import math


# ════════════════════════════════════════════
# SIGNAL THRESHOLDS — the weight → signal mapping
# ════════════════════════════════════════════

SIGNAL_STRONG_NEGATIVE = -50    # 🔴 critical
SIGNAL_NEGATIVE = -20           # 🟠 problem
SIGNAL_NEUTRAL = -5             # 🟡 borderline
SIGNAL_POSITIVE = 10            # 🟢 good
SIGNAL_STRONG_POSITIVE = 40     # 🔵 excellent

SIGNAL_LABELS = {
    "STRONG_NEGATIVE": "🔴",
    "NEGATIVE": "🟠",
    "NEUTRAL": "🟡",
    "POSITIVE": "🟢",
    "STRONG_POSITIVE": "🔵",
}

# Weight calculation constants
WEIGHT_OVERLAP = -50            # elements overlapping
WEIGHT_TOO_CLOSE = -15          # cramped
WEIGHT_SWEET_SPOT = +30         # perfect distance
WEIGHT_TOO_FAR = -10            # disconnected
WEIGHT_MISSING_TOOLTIP = -20
WEIGHT_MISSING_SHORTCUT = -15
WEIGHT_MISSING_HELP = -10
WEIGHT_HAS_TOOLTIP = +15
WEIGHT_HAS_SHORTCUT = +12
WEIGHT_HAS_HELP = +8
WEIGHT_EDGE_GOOD = +20          # edge constraint satisfied
WEIGHT_EDGE_BAD = -25           # edge constraint violated


class GraphSignalMatrix:
    """
    GUI as weighted signal matrix for AI model review.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Weights change. Signals guide. Overlay compares. Matrix informs.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "strong_neg": SIGNAL_STRONG_NEGATIVE,
                "negative": SIGNAL_NEGATIVE,
                "neutral": SIGNAL_NEUTRAL,
                "positive": SIGNAL_POSITIVE,
                "strong_pos": SIGNAL_STRONG_POSITIVE,
            },
            "snapshots": {},       # id → snapshot dict
            "current": None,       # current snapshot id
            "overlay": None,       # last overlay result
            "matrix": {},          # last matrix output
            "signals": {},         # last signals output
            "evolution": [],       # weight history per element
            "stats": {"snapshots": 0, "overlays": 0, "evolutions": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "snapshot": self.cmd_snapshot,
            "weight": self.cmd_weight,
            "signal": self.cmd_signal,
            "overlay": self.cmd_overlay,
            "diff": self.cmd_diff,
            "matrix": self.cmd_matrix,
            "evolve": self.cmd_evolve,
            "compare": self.cmd_compare,
            "report": self.cmd_report,
            "graph": self.cmd_graph,
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
    # INTERNAL — weight calculation
    # ════════════════════════════════════════════

    def distance(self, a, b):
        dx = a.get("x", 0) - b.get("x", 0)
        dy = a.get("y", 0) - b.get("y", 0)
        return math.sqrt(dx * dx + dy * dy)

    def weightToSignal(self, weight):
        cfg = self.state["config"]
        if weight <= cfg["strong_neg"]:
            return "STRONG_NEGATIVE"
        elif weight <= cfg["negative"]:
            return "NEGATIVE"
        elif weight <= cfg["neutral"]:
            return "NEUTRAL"
        elif weight >= cfg["strong_pos"]:
            return "STRONG_POSITIVE"
        elif weight >= cfg["positive"]:
            return "POSITIVE"
        else:
            return "NEUTRAL"

    def signalIcon(self, signalType):
        return SIGNAL_LABELS.get(signalType, "⚪")

    def calcNodeWeight(self, nodeId, nodes, edges):
        """Calculate weight for a single node across all dimensions."""
        node = nodes.get(nodeId)
        if not node:
            return {"total": 0, "spacing": 0, "completeness": 0, "alignment": 0, "flow": 0}

        spacing = 0
        completeness = 0
        alignment = 0
        flow = 0

        # SPACING — distance to all other nodes
        for otherId, other in nodes.items():
            if otherId == nodeId:
                continue
            dist = self.distance(node, other)
            if dist < 5:
                spacing += WEIGHT_OVERLAP
            elif dist < 20:
                spacing += WEIGHT_TOO_CLOSE
            elif dist < 300:
                spacing += WEIGHT_SWEET_SPOT
            else:
                spacing += WEIGHT_TOO_FAR

        # COMPLETENESS — Porsche principle
        ntype = node.get("type", "")
        if ntype in ("Button", "Input", "MenuItem", "Tab"):
            if node.get("has_tooltip", False):
                completeness += WEIGHT_HAS_TOOLTIP
            else:
                completeness += WEIGHT_MISSING_TOOLTIP
            if node.get("has_shortcut", False):
                completeness += WEIGHT_HAS_SHORTCUT
            else:
                completeness += WEIGHT_MISSING_SHORTCUT
            if node.get("has_help", False):
                completeness += WEIGHT_HAS_HELP
            else:
                completeness += WEIGHT_MISSING_HELP

        # ALIGNMENT + FLOW — edge constraints
        for e in edges:
            if e.get("a") == nodeId or e.get("b") == nodeId:
                otherId = e.get("b") if e.get("a") == nodeId else e.get("a")
                other = nodes.get(otherId)
                if other:
                    dist = self.distance(node, other)
                    eType = e.get("type", "GROUP")
                    maxDist = {"GROUP": 200, "ALIGNMENT": 100, "DEPENDENCY": 250, "FLOW": 150}.get(eType, 200)
                    if eType == "ALIGNMENT":
                        alignment += WEIGHT_EDGE_GOOD if dist <= maxDist else WEIGHT_EDGE_BAD
                    elif eType == "FLOW":
                        flow += WEIGHT_EDGE_GOOD if dist <= maxDist else WEIGHT_EDGE_BAD
                    else:
                        alignment += WEIGHT_EDGE_GOOD if dist <= maxDist else WEIGHT_EDGE_BAD

        total = spacing + completeness + alignment + flow
        return {
            "total": round(total, 2),
            "spacing": round(spacing, 2),
            "completeness": round(completeness, 2),
            "alignment": round(alignment, 2),
            "flow": round(flow, 2),
        }

    def calcSnapshot(self, nodes, edges):
        """Calculate weights for all nodes in a snapshot."""
        weights = {}
        for nodeId in nodes:
            weights[nodeId] = self.calcNodeWeight(nodeId, nodes, edges)
        # Overall graph weight
        totalWeight = sum(w["total"] for w in weights.values())
        avgWeight = totalWeight / len(weights) if weights else 0
        return {
            "weights": weights,
            "graph_total": round(totalWeight, 2),
            "graph_avg": round(avgWeight, 2),
            "node_count": len(weights),
            "edge_count": len(edges),
        }

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_snapshot(self, params):
        snapId = self.p(params, "id")
        if not snapId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        nodes = self.p(params, "nodes", {})
        edges = self.p(params, "edges", [])
        calc = self.calcSnapshot(nodes, edges)
        snapshot = {
            "id": snapId,
            "nodes": nodes,
            "edges": edges,
            "weights": calc["weights"],
            "graph_total": calc["graph_total"],
            "graph_avg": calc["graph_avg"],
            "node_count": calc["node_count"],
            "edge_count": calc["edge_count"],
        }
        self.state["snapshots"][snapId] = snapshot
        self.state["current"] = snapId
        self.state["stats"]["snapshots"] += 1
        # Track evolution
        self.state["evolution"].append({
            "snapshot": snapId,
            "graph_total": calc["graph_total"],
            "graph_avg": calc["graph_avg"],
        })
        return (1, snapshot, None)

    def cmd_weight(self, params):
        """Get weight for a specific node in current snapshot."""
        snapId = self.p(params, "snapshot", self.state["current"])
        nodeId = self.p(params, "node")
        if not snapId or not nodeId:
            return (0, None, ("ERR_PARAMS", "snapshot and node required", 0))
        snap = self.state["snapshots"].get(snapId)
        if not snap:
            return (0, None, ("ERR_NOT_FOUND", "snapshot not found: %s" % snapId, 0))
        weight = snap["weights"].get(nodeId)
        if not weight:
            return (0, None, ("ERR_NOT_FOUND", "node not found: %s" % nodeId, 0))
        signal = self.weightToSignal(weight["total"])
        return (1, {"weight": weight, "signal": signal, "icon": self.signalIcon(signal)}, None)

    def cmd_signal(self, params):
        """Generate signals for all nodes — tells model where to look."""
        snapId = self.p(params, "snapshot", self.state["current"])
        if not snapId:
            return (0, None, ("ERR_PARAMS", "no current snapshot", 0))
        snap = self.state["snapshots"].get(snapId)
        if not snap:
            return (0, None, ("ERR_NOT_FOUND", "snapshot not found: %s" % snapId, 0))
        signals = {}
        for nodeId, weight in snap["weights"].items():
            signalType = self.weightToSignal(weight["total"])
            signals[nodeId] = {
                "weight": weight["total"],
                "signal": signalType,
                "icon": self.signalIcon(signalType),
                "dimensions": weight,
                "action": self.signalAction(signalType),
            }
        # Sort by weight (worst first — model looks here first)
        sortedSignals = sorted(signals.items(), key=lambda x: x[1]["weight"])
        self.state["signals"] = signals
        return (1, {
            "snapshot": snapId,
            "signals": signals,
            "sorted": [{"node": k, **v} for k, v in sortedSignals],
            "graph_total": snap["graph_total"],
            "graph_avg": snap["graph_avg"],
        }, None)

    def signalAction(self, signalType):
        actions = {
            "STRONG_NEGATIVE": "FIX NOW — critical problem",
            "NEGATIVE": "should fix — problem area",
            "NEUTRAL": "could improve — borderline",
            "POSITIVE": "no action — good",
            "STRONG_POSITIVE": "reference — excellent",
        }
        return actions.get(signalType, "review")

    def cmd_overlay(self, params):
        """Overlay two snapshots — the diff IS the improvement plan."""
        beforeId = self.p(params, "before")
        afterId = self.p(params, "after")
        if not beforeId or not afterId:
            return (0, None, ("ERR_PARAMS", "before and after required", 0))
        before = self.state["snapshots"].get(beforeId)
        after = self.state["snapshots"].get(afterId)
        if not before:
            return (0, None, ("ERR_NOT_FOUND", "before snapshot not found", 0))
        if not after:
            return (0, None, ("ERR_NOT_FOUND", "after snapshot not found", 0))
        overlay = {}
        allNodes = set(before["weights"].keys()) | set(after["weights"].keys())
        for nodeId in allNodes:
            beforeW = before["weights"].get(nodeId, {"total": 0})
            afterW = after["weights"].get(nodeId, {"total": 0})
            delta = afterW["total"] - beforeW["total"]
            if delta > 5:
                change = "IMPROVED"
                icon = "🟢"
            elif delta < -5:
                change = "REGRESSED"
                icon = "🔴"
            else:
                change = "UNCHANGED"
                icon = "⚪"
            overlay[nodeId] = {
                "before": beforeW["total"],
                "after": afterW["total"],
                "delta": round(delta, 2),
                "change": change,
                "icon": icon,
            }
        graphDelta = after["graph_total"] - before["graph_total"]
        self.state["overlay"] = {
            "before": beforeId,
            "after": afterId,
            "overlay": overlay,
            "graph_delta": round(graphDelta, 2),
            "before_total": before["graph_total"],
            "after_total": after["graph_total"],
        }
        self.state["stats"]["overlays"] += 1
        return (1, self.state["overlay"], None)

    def cmd_diff(self, params):
        """Alias for overlay with simpler output."""
        ok, data, err = self.cmd_overlay(params)
        if not ok:
            return (0, None, err)
        diffs = []
        for nodeId, info in data["overlay"].items():
            diffs.append({
                "node": nodeId,
                "before": info["before"],
                "after": info["after"],
                "delta": info["delta"],
                "change": info["change"],
            })
        diffs.sort(key=lambda x: x["delta"])
        return (1, {
            "graph_delta": data["graph_delta"],
            "improved": sum(1 for d in diffs if d["change"] == "IMPROVED"),
            "regressed": sum(1 for d in diffs if d["change"] == "REGRESSED"),
            "unchanged": sum(1 for d in diffs if d["change"] == "UNCHANGED"),
            "diffs": diffs,
        }, None)

    def cmd_matrix(self, params):
        """Output the GUI as a numeric matrix for model review."""
        snapId = self.p(params, "snapshot", self.state["current"])
        if not snapId:
            return (0, None, ("ERR_PARAMS", "no current snapshot", 0))
        snap = self.state["snapshots"].get(snapId)
        if not snap:
            return (0, None, ("ERR_NOT_FOUND", "snapshot not found", 0))
        matrix = {}
        for nodeId, weight in snap["weights"].items():
            matrix[nodeId] = [
                weight["spacing"],
                weight["completeness"],
                weight["alignment"],
                weight["flow"],
                weight["total"],
            ]
        # Also output as flat array for model input
        flat = []
        for nodeId in sorted(matrix.keys()):
            flat.extend(matrix[nodeId])
        self.state["matrix"] = {
            "snapshot": snapId,
            "headers": ["spacing", "completeness", "alignment", "flow", "total"],
            "matrix": matrix,
            "flat": flat,
            "graph_total": snap["graph_total"],
            "graph_avg": snap["graph_avg"],
        }
        return (1, self.state["matrix"], None)

    def cmd_evolve(self, params):
        """Track weight evolution — how the graph gains/loses weight over time."""
        snapId = self.p(params, "id")
        nodes = self.p(params, "nodes", {})
        edges = self.p(params, "edges", [])
        if not snapId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        ok, data, err = self.cmd_snapshot({"id": snapId, "nodes": nodes, "edges": edges})
        if not ok:
            return (0, None, err)
        self.state["stats"]["evolutions"] += 1
        # Calculate weight changes from previous evolution step
        evo = self.state["evolution"]
        changes = []
        if len(evo) >= 2:
            prev = evo[-2]
            curr = evo[-1]
            delta = curr["graph_total"] - prev["graph_total"]
            changes.append({
                "from": prev["snapshot"],
                "to": curr["snapshot"],
                "delta": round(delta, 2),
                "direction": "GAINING" if delta > 0 else ("LOSING" if delta < 0 else "STABLE"),
            })
        return (1, {
            "evolved": True,
            "snapshot": snapId,
            "graph_total": data["graph_total"],
            "graph_avg": data["graph_avg"],
            "evolution_length": len(evo),
            "recent_changes": changes,
        }, None)

    def cmd_compare(self, params):
        """Compare two snapshots — full weight comparison."""
        beforeId = self.p(params, "before")
        afterId = self.p(params, "after")
        if not beforeId or not afterId:
            return (0, None, ("ERR_PARAMS", "before and after required", 0))
        before = self.state["snapshots"].get(beforeId)
        after = self.state["snapshots"].get(afterId)
        if not before or not after:
            return (0, None, ("ERR_NOT_FOUND", "snapshot not found", 0))
        comparison = {
            "before": {
                "graph_total": before["graph_total"],
                "graph_avg": before["graph_avg"],
                "nodes": before["node_count"],
            },
            "after": {
                "graph_total": after["graph_total"],
                "graph_avg": after["graph_avg"],
                "nodes": after["node_count"],
            },
            "delta_total": round(after["graph_total"] - before["graph_total"], 2),
            "delta_avg": round(after["graph_avg"] - before["graph_avg"], 2),
            "verdict": "",
        }
        delta = comparison["delta_total"]
        if delta > 50:
            comparison["verdict"] = "MASSIVE IMPROVEMENT — graph gained significant weight"
        elif delta > 10:
            comparison["verdict"] = "IMPROVED — graph gained weight"
        elif delta > -10:
            comparison["verdict"] = "STABLE — no significant change"
        elif delta > -50:
            comparison["verdict"] = "DEGRADED — graph lost weight"
        else:
            comparison["verdict"] = "CRITICAL DEGRADATION — graph lost significant weight"
        return (1, comparison, None)

    def cmd_report(self, params):
        """Full signal report for model review."""
        snapId = self.p(params, "snapshot", self.state["current"])
        ok, sigData, err = self.cmd_signal({"snapshot": snapId})
        if not ok:
            return (0, None, err)
        ok, matData, err2 = self.cmd_matrix({"snapshot": snapId})
        if not ok:
            return (0, None, err2)
        lines = []
        lines.append("GRAPH SIGNAL MATRIX REPORT")
        lines.append("===========================")
        lines.append("Snapshot: %s" % snapId)
        lines.append("Graph Total Weight: %.2f" % sigData["graph_total"])
        lines.append("Graph Average Weight: %.2f" % sigData["graph_avg"])
        lines.append("")
        lines.append("SIGNALS (sorted worst first — model looks here):")
        lines.append("-" * 60)
        for item in sigData["sorted"]:
            lines.append("  %s %-15s  weight=%7.2f  %s" % (
                item["icon"], item["node"], item["weight"], item["action"]))
        lines.append("")
        lines.append("MATRIX (for model input):")
        lines.append("-" * 60)
        lines.append("  %-15s  %8s  %8s  %8s  %8s  %8s" % (
            "node", "spacing", "compl", "align", "flow", "TOTAL"))
        for nodeId, row in sorted(matData["matrix"].items()):
            lines.append("  %-15s  %8.2f  %8.2f  %8.2f  %8.2f  %8.2f" % (
                nodeId, row[0], row[1], row[2], row[3], row[4]))
        lines.append("")
        lines.append("FLAT MATRIX (model input vector):")
        lines.append("  %s" % str(matData["flat"]))
        if self.state["overlay"]:
            ov = self.state["overlay"]
            lines.append("")
            lines.append("OVERLAY (%s → %s):" % (ov["before"], ov["after"]))
            lines.append("-" * 60)
            lines.append("  Graph delta: %+.2f" % ov["graph_delta"])
            for nodeId, info in sorted(ov["overlay"].items(), key=lambda x: x[1]["delta"]):
                lines.append("  %s %-15s  %+.2f → %+.2f  (delta %+.2f)" % (
                    info["icon"], nodeId, info["before"], info["after"], info["delta"]))
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual signal graph — the matrix as a picture."""
        snapId = self.p(params, "snapshot", self.state["current"])
        ok, sigData, err = self.cmd_signal({"snapshot": snapId})
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║         GRAPH SIGNAL MATRIX — Weighted GUI Brain            ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Snapshot: %s" % snapId)
        lines.append("  Graph Weight: %+.2f  (avg: %+.2f)" % (
            sigData["graph_total"], sigData["graph_avg"]))
        lines.append("")

        # Weight bar
        total = sigData["graph_total"]
        barLen = 30
        if total >= 0:
            filled = min(int(total / 10), barLen)
            bar = "█" * filled + "░" * (barLen - filled)
        else:
            filled = min(int(abs(total) / 10), barLen)
            bar = "░" * (barLen - filled) + "█" * filled
        lines.append("  Weight:  [%s]  %+.2f" % (bar, total))
        if total > 100:
            lines.append("  Status:  🔵 EXCELLENT — graph is healthy")
        elif total > 20:
            lines.append("  Status:  🟢 GOOD — graph is mostly healthy")
        elif total > -20:
            lines.append("  Status:  🟡 BORDERLINE — needs attention")
        elif total > -100:
            lines.append("  Status:  🟠 BAD — needs fixing")
        else:
            lines.append("  Status:  🔴 CRITICAL — major problems")
        lines.append("")

        # Signals per node (sorted worst first)
        lines.append("  ┌─ SIGNALS (worst first — model looks here) ────────────────┐")
        for item in sigData["sorted"]:
            weight = item["weight"]
            signalLen = min(int(abs(weight) / 5), 20)
            if weight >= 0:
                signalBar = "🟩" * signalLen
            else:
                signalBar = "🟥" * signalLen
            lines.append("  │  %s %-15s  %+7.2f  %s  %s" % (
                item["icon"], item["node"][:15], weight, signalBar, item["action"][:25]))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Evolution
        evo = self.state["evolution"]
        if len(evo) > 1:
            lines.append("  ┌─ EVOLUTION (weight over time) ─────────────────────────────┐")
            for i, step in enumerate(evo):
                total = step["graph_total"]
                if i > 0:
                    prev = evo[i - 1]["graph_total"]
                    delta = total - prev
                    direction = "📈 GAINING" if delta > 0 else ("📉 LOSING" if delta < 0 else "➡️  STABLE")
                    lines.append("  │  %s  %s  total=%+.2f  (delta %+.2f)" % (
                        step["snapshot"][:15], direction, total, delta))
                else:
                    lines.append("  │  %s  START  total=%+.2f" % (step["snapshot"][:15], total))
            lines.append("  └────────────────────────────────────────────────────────────┘")
            lines.append("")

        # Overlay
        if self.state["overlay"]:
            ov = self.state["overlay"]
            lines.append("  ┌─ OVERLAY (%s → %s) ──────────────────────────────┐" % (
                ov["before"][:10], ov["after"][:10]))
            lines.append("  │  Graph delta: %+.2f  (%+.2f → %+.2f)" % (
                ov["graph_delta"], ov["before_total"], ov["after_total"]))
            for nodeId, info in sorted(ov["overlay"].items(), key=lambda x: x[1]["delta"], reverse=True):
                lines.append("  │  %s %-15s  %+.2f → %+.2f  delta=%+.2f" % (
                    info["icon"], nodeId[:15], info["before"], info["after"], info["delta"]))
            lines.append("  └────────────────────────────────────────────────────────────┘")
            lines.append("")

        # Matrix preview
        ok, matData, err2 = self.cmd_matrix({"snapshot": snapId})
        if ok:
            lines.append("  ┌─ MATRIX (model input) ────────────────────────────────────┐")
            lines.append("  │  %-12s  %7s  %7s  %7s  %7s  %7s" % (
                "node", "space", "compl", "align", "flow", "TOTAL"))
            for nodeId, row in sorted(matData["matrix"].items()):
                lines.append("  │  %-12s  %+7.2f  %+7.2f  %+7.2f  %+7.2f  %+7.2f" % (
                    nodeId[:12], row[0], row[1], row[2], row[3], row[4]))
            lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)
