#!/usr/bin/env python3
# [@GHOST]{[@file<EnergyFieldGraph.py>][@domain<graph>][@role<energy_field>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<energy_field>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{EnergyFieldGraph — Dual-state energy field optimizer. BAD state + GOOD state + current live state. Signal = good - current. Force-directed movement toward optimal. Heatmap color per node. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{EnergyFieldGraph}
# [@METHOD]{Run,build,step,signal,heatmap,converged,reset,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Dual-state energy field optimizer with signal gradient. VBStyle compliant: Run dispatch, Tuple3, self.state, no decorators/print/self._/hardcoded visible.>][@todos<none>]}
"""
EnergyFieldGraph — Dual-state energy field optimizer with signal gradient.

THE FORMAL MODEL:
  G = (N, E, W)
  N = nodes (UI elements)
  E = edges (relationships)
  W = weights (quality score per node)

  Two graphs:
    G_bad  = broken layout (initial state)
    G_good = ideal layout (reference design)

  Signal graph:
    S = G_good - G_current

  Each node has a displacement vector toward good state.
  Force-directed physics moves nodes toward optimal.
  Heatmap colors show distance to target.

THE CONTROL SYSTEM:
  1. Graph           — nodes with positions
  2. Energy function  — distance to good state
  3. Differential     — signal = good - current
  4. Feedback signal  — force vector per node
  5. Optimization     — physics loop converges to good

USAGE:
  from EnergyFieldGraph import EnergyFieldGraph

  engine = EnergyFieldGraph()
  engine.Run("build", {"nodes": [
      {"id": "Toolbar", "bad_x": 50, "bad_y": 50, "good_x": 300, "good_y": 50},
      {"id": "Sidebar", "bad_x": 50, "bad_y": 200, "good_x": 50, "good_y": 200},
  ]})

  # Step the physics loop
  for i in range(100):
      ok, data, err = engine.Run("step")
      if data["converged"]:
          break

  # Get heatmap colors for rendering
  ok, data, err = engine.Run("heatmap")

  # Get signal vectors
  ok, data, err = engine.Run("signal")
"""

import math


# ════════════════════════════════════════════
# PHYSICS CONSTANTS — force-directed movement
# ════════════════════════════════════════════

DAMPING = 0.85          # velocity decay per step
STRENGTH = 0.08         # force strength toward good state
CONVERGE_THRESHOLD = 1.0  # distance at which node is "arrived"
HEATMAP_MAX_DIST = 300.0  # distance for red→green color range
NODE_RADIUS = 20         # visual radius


class EnergyFieldGraph:
    """
    Dual-state energy field optimizer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    BAD state → GOOD state via force-directed physics.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "damping": DAMPING,
                "strength": STRENGTH,
                "converge_threshold": CONVERGE_THRESHOLD,
                "heatmap_max_dist": HEATMAP_MAX_DIST,
                "node_radius": NODE_RADIUS,
            },
            "nodes": {},           # id → node dict with positions + velocity
            "edges": [],           # relationship edges
            "step_count": 0,
            "converged": False,
            "history": [],         # total energy per step
            "stats": {"steps": 0, "converged_at": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "build": self.cmd_build,
            "step": self.cmd_step,
            "signal": self.cmd_signal,
            "heatmap": self.cmd_heatmap,
            "converged": self.cmd_converged,
            "reset": self.cmd_reset,
            "report": self.cmd_report,
            "graph": self.cmd_graph,
            "add_node": self.cmd_add_node,
            "add_edge": self.cmd_add_edge,
            "set_good": self.cmd_set_good,
            "set_bad": self.cmd_set_bad,
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
    # INTERNAL — physics calculations
    # ════════════════════════════════════════════

    def nodeDistance(self, node):
        """Distance from current position to good position."""
        dx = node["good_x"] - node["x"]
        dy = node["good_y"] - node["y"]
        return math.sqrt(dx * dx + dy * dy)

    def nodeSignal(self, node):
        """Signal vector = good - current (direction to move)."""
        return (node["good_x"] - node["x"], node["good_y"] - node["y"])

    def totalEnergy(self):
        """Total energy = sum of all node distances to good state."""
        total = 0.0
        for node in self.state["nodes"].values():
            total += self.nodeDistance(node)
        return total

    def allConverged(self):
        """Check if all nodes have arrived at good state."""
        threshold = self.state["config"]["converge_threshold"]
        for node in self.state["nodes"].values():
            if self.nodeDistance(node) > threshold:
                return False
        return True

    def heatColor(self, dist):
        """Convert distance to RGB color. 0=green, max=red."""
        maxDist = self.state["config"]["heatmap_max_dist"]
        score = max(0.0, min(1.0, 1.0 - dist / maxDist))
        r = int(255 * (1.0 - score))
        g = int(255 * score)
        b = 120
        return {"r": r, "g": g, "b": b, "score": round(score, 3)}

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_build(self, params):
        nodes = self.p(params, "nodes", [])
        edges = self.p(params, "edges", [])
        for n in nodes:
            nodeId = n.get("id", "")
            if nodeId:
                node = {
                    "id": nodeId,
                    "type": n.get("type", "Widget"),
                    "x": float(n.get("bad_x", n.get("x", 0))),
                    "y": float(n.get("bad_y", n.get("y", 0))),
                    "vx": 0.0,
                    "vy": 0.0,
                    "good_x": float(n.get("good_x", n.get("x", 0))),
                    "good_y": float(n.get("good_y", n.get("y", 0))),
                    "bad_x": float(n.get("bad_x", n.get("x", 0))),
                    "bad_y": float(n.get("bad_y", n.get("y", 0))),
                }
                self.state["nodes"][nodeId] = node
        self.state["edges"] = [dict(e) for e in edges]
        self.state["step_count"] = 0
        self.state["converged"] = False
        self.state["history"] = []
        return (1, {"built": True, "nodes": len(self.state["nodes"]), "edges": len(self.state["edges"])}, None)

    def cmd_add_node(self, params):
        nodeId = self.p(params, "id")
        if not nodeId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        bx = float(self.p(params, "bad_x", self.p(params, "x", 0)))
        by = float(self.p(params, "bad_y", self.p(params, "y", 0)))
        gx = float(self.p(params, "good_x", bx))
        gy = float(self.p(params, "good_y", by))
        node = {
            "id": nodeId,
            "type": self.p(params, "type", "Widget"),
            "x": bx,
            "y": by,
            "vx": 0.0,
            "vy": 0.0,
            "good_x": gx,
            "good_y": gy,
            "bad_x": bx,
            "bad_y": by,
        }
        self.state["nodes"][nodeId] = node
        return (1, node, None)

    def cmd_add_edge(self, params):
        a = self.p(params, "a")
        b = self.p(params, "b")
        if not a or not b:
            return (0, None, ("ERR_PARAMS", "a and b required", 0))
        edge = {"a": a, "b": b, "type": self.p(params, "type", "GROUP")}
        self.state["edges"].append(edge)
        return (1, edge, None)

    def cmd_set_good(self, params):
        """Update the good (target) position for a node."""
        nodeId = self.p(params, "id")
        if not nodeId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        node = self.state["nodes"].get(nodeId)
        if not node:
            return (0, None, ("ERR_NOT_FOUND", "node not found", 0))
        node["good_x"] = float(self.p(params, "good_x", node["good_x"]))
        node["good_y"] = float(self.p(params, "good_y", node["good_y"]))
        return (1, {"id": nodeId, "good_x": node["good_x"], "good_y": node["good_y"]}, None)

    def cmd_set_bad(self, params):
        """Reset a node to its bad (initial) position."""
        nodeId = self.p(params, "id")
        if not nodeId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        node = self.state["nodes"].get(nodeId)
        if not node:
            return (0, None, ("ERR_NOT_FOUND", "node not found", 0))
        node["x"] = node["bad_x"]
        node["y"] = node["bad_y"]
        node["vx"] = 0.0
        node["vy"] = 0.0
        return (1, {"id": nodeId, "reset": True}, None)

    def cmd_step(self, params):
        """One physics step — move all nodes toward good state."""
        cfg = self.state["config"]
        damping = cfg["damping"]
        strength = cfg["strength"]
        for node in self.state["nodes"].values():
            sx, sy = self.nodeSignal(node)
            node["vx"] += sx * strength
            node["vy"] += sy * strength
            node["vx"] *= damping
            node["vy"] *= damping
            node["x"] += node["vx"]
            node["y"] += node["vy"]
        self.state["step_count"] += 1
        self.state["stats"]["steps"] += 1
        energy = self.totalEnergy()
        self.state["history"].append(round(energy, 2))
        converged = self.allConverged()
        if converged and not self.state["converged"]:
            self.state["converged"] = True
            self.state["stats"]["converged_at"] = self.state["step_count"]
        return (1, {
            "step": self.state["step_count"],
            "energy": round(energy, 2),
            "converged": converged,
        }, None)

    def cmd_signal(self, params):
        """Get signal vectors for all nodes — the gradient field."""
        signals = {}
        for nodeId, node in self.state["nodes"].items():
            sx, sy = self.nodeSignal(node)
            dist = self.nodeDistance(node)
            signals[nodeId] = {
                "signal_x": round(sx, 2),
                "signal_y": round(sy, 2),
                "distance": round(dist, 2),
                "direction": "ARRIVED" if dist < self.state["config"]["converge_threshold"] else "MOVING",
            }
        return (1, {
            "signals": signals,
            "total_energy": round(self.totalEnergy(), 2),
            "step": self.state["step_count"],
        }, None)

    def cmd_heatmap(self, params):
        """Get heatmap colors for all nodes — for visual rendering."""
        heatmap = {}
        for nodeId, node in self.state["nodes"].items():
            dist = self.nodeDistance(node)
            color = self.heatColor(dist)
            heatmap[nodeId] = {
                "x": round(node["x"], 1),
                "y": round(node["y"], 1),
                "good_x": node["good_x"],
                "good_y": node["good_y"],
                "distance": round(dist, 2),
                "color": color,
                "label": nodeId,
            }
        return (1, {
            "heatmap": heatmap,
            "step": self.state["step_count"],
            "converged": self.state["converged"],
        }, None)

    def cmd_converged(self, params):
        return (1, {"converged": self.state["converged"], "step": self.state["step_count"]}, None)

    def cmd_reset(self, params):
        """Reset all nodes to bad positions."""
        for node in self.state["nodes"].values():
            node["x"] = node["bad_x"]
            node["y"] = node["bad_y"]
            node["vx"] = 0.0
            node["vy"] = 0.0
        self.state["step_count"] = 0
        self.state["converged"] = False
        self.state["history"] = []
        return (1, {"reset": True, "nodes": len(self.state["nodes"])}, None)

    def cmd_report(self, params):
        """Full energy field report."""
        ok, sigData, err = self.cmd_signal({})
        if not ok:
            return (0, None, err)
        ok, heatData, err2 = self.cmd_heatmap({})
        if not ok:
            return (0, None, err2)
        lines = []
        lines.append("ENERGY FIELD REPORT")
        lines.append("====================")
        lines.append("Step: %d" % self.state["step_count"])
        lines.append("Total Energy: %.2f" % sigData["total_energy"])
        lines.append("Converged: %s" % self.state["converged"])
        lines.append("")
        lines.append("NODE SIGNALS:")
        lines.append("-" * 60)
        for nodeId, sig in sigData["signals"].items():
            lines.append("  %-15s  signal=(%+.2f, %+.2f)  dist=%6.2f  %s" % (
                nodeId, sig["signal_x"], sig["signal_y"], sig["distance"], sig["direction"]))
        lines.append("")
        lines.append("HEATMAP:")
        lines.append("-" * 60)
        for nodeId, heat in heatData["heatmap"].items():
            c = heat["color"]
            lines.append("  %-15s  pos=(%.1f, %.1f)  target=(%.1f, %.1f)  dist=%.2f  rgb=(%d,%d,%d)  score=%.3f" % (
                nodeId, heat["x"], heat["y"], heat["good_x"], heat["good_y"],
                heat["distance"], c["r"], c["g"], c["b"], c["score"]))
        if self.state["history"]:
            lines.append("")
            lines.append("ENERGY HISTORY:")
            lines.append("-" * 60)
            for i, e in enumerate(self.state["history"]):
                barLen = min(int(e / 10), 30)
                bar = "█" * barLen
                lines.append("  Step %3d: %7.2f  %s" % (i + 1, e, bar))
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual energy field graph."""
        ok, sigData, err = self.cmd_signal({})
        if not ok:
            return (0, None, err)
        ok, heatData, err2 = self.cmd_heatmap({})
        if not ok:
            return (0, None, err2)
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║         ENERGY FIELD GRAPH — Dual-State Optimizer           ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Step: %d   Energy: %.2f   Converged: %s" % (
            self.state["step_count"], sigData["total_energy"],
            "✅ YES" if self.state["converged"] else "❌ NO"))
        lines.append("")

        # Energy bar
        energy = sigData["total_energy"]
        barLen = 30
        filled = min(int(energy / 10), barLen)
        bar = "█" * filled + "░" * (barLen - filled)
        lines.append("  Energy:  [%s]  %.2f" % (bar, energy))
        if self.state["converged"]:
            lines.append("  Status:  ✅ CONVERGED — all nodes at optimal position")
        elif energy < 50:
            lines.append("  Status:  🟢 NEAR OPTIMAL — almost converged")
        elif energy < 200:
            lines.append("  Status:  🟡 MOVING — nodes progressing toward target")
        elif energy < 500:
            lines.append("  Status:  🟠 FAR — significant displacement remaining")
        else:
            lines.append("  Status:  🔴 STARTING — large displacement from target")
        lines.append("")

        # Per-node heatmap
        lines.append("  ┌─ HEATMAP (red=far, green=arrived) ────────────────────────┐")
        for nodeId, heat in heatData["heatmap"].items():
            c = heat["color"]
            dist = heat["distance"]
            score = c["score"]
            if score > 0.8:
                icon = "🟢"
            elif score > 0.5:
                icon = "🟡"
            elif score > 0.2:
                icon = "🟠"
            else:
                icon = "🔴"
            barLen = min(int(score * 20), 20)
            bar = "🟩" * barLen + "⬜" * (20 - barLen)
            lines.append("  │  %s %-12s  dist=%6.2f  %s  rgb(%d,%d,%d)" % (
                icon, nodeId[:12], dist, bar, c["r"], c["g"], c["b"]))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Signal vectors
        lines.append("  ┌─ SIGNAL GRADIENT (direction to move) ─────────────────────┐")
        for nodeId, sig in sigData["signals"].items():
            sx = sig["signal_x"]
            sy = sig["signal_y"]
            mag = math.sqrt(sx * sx + sy * sy)
            if mag < 1:
                arrow = "● ARRIVED"
            else:
                angle = math.degrees(math.atan2(sy, sx))
                if -22.5 <= angle < 22.5:
                    arrow = "→ EAST"
                elif 22.5 <= angle < 67.5:
                    arrow = "↘ SE"
                elif 67.5 <= angle < 112.5:
                    arrow = "↓ SOUTH"
                elif 112.5 <= angle < 157.5:
                    arrow = "↙ SW"
                elif angle >= 157.5 or angle < -157.5:
                    arrow = "← WEST"
                elif -157.5 <= angle < -112.5:
                    arrow = "↖ NW"
                elif -112.5 <= angle < -67.5:
                    arrow = "↑ NORTH"
                else:
                    arrow = "↗ NE"
            lines.append("  │  %-12s  signal=(%+7.2f, %+7.2f)  mag=%6.2f  %s" % (
                nodeId[:12], sx, sy, mag, arrow))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Energy history
        if self.state["history"]:
            hist = self.state["history"]
            lines.append("  ┌─ ENERGY CONVERGENCE ──────────────────────────────────────┐")
            showSteps = min(len(hist), 20)
            stepStart = max(0, len(hist) - showSteps)
            for i in range(stepStart, len(hist)):
                e = hist[i]
                barLen = min(int(e / 10), 30)
                bar = "█" * barLen + "░" * (30 - barLen)
                lines.append("  │  Step %3d: %7.2f  %s" % (i + 1, e, bar))
            lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)
