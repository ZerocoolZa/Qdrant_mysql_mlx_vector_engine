#!/usr/bin/env python3
# [@GHOST]{[@file<GuiAiBrain.py>][@domain<graph>][@role<ai_brain>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<ai_brain>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GuiAiBrain — Self-organizing GUI layout brain. 8 layers: perceive, world model, force field, energy, learning, annealing, compiler, persistence. Adapts force weights based on energy feedback. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GuiAiBrain}
# [@METHOD]{Run,perceive,cycle,energy,adapt,anneal,compile,persist,restore,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Self-organizing GUI layout brain with 8 layers: perceive, world model, force field, energy, learning, annealing, compiler, persistence. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GuiAiBrain — The AI brain that learns GUI layout.

THE 8 LAYERS (from the spec):

  1. PERCEPTION LAYER (UI → GRAPH)
     Input: UI spec JSON
     Output: Graph with nodes, edges, constraints

  2. WORLD MODEL (GRAPH STATE MEMORY)
     Stores: last stable layouts, energy history, rule weights, relationships

  3. FORCE FIELD ENGINE (PHYSICS CORE)
     Attraction: center gravity, dock anchors
     Repulsion: overlap prevention, minimum spacing
     Constraint: fixed panels, boundary limits

  4. ENERGY FUNCTION (BRAIN METRIC)
     E = overlap_cost + misalignment_cost + constraint_violation + unused_space - order_reward

  5. LEARNING LAYER (ADAPTIVE WEIGHTS)
     Each force has a weight that adapts:
       if energy increases → increase penalty weights
       if energy decreases → stabilize weights
     This is the "AI" — not ML, but rule adaptation.

  6. ANNEALING SYSTEM (SHAKE ENGINE)
     temperature *= 0.98 per tick
     High T = chaos, Low T = stable lock

  7. LAYOUT COMPILER (FINAL OUTPUT)
     Graph → PyQt layout (QSplitter zones, QFrame panels)

  8. PERSISTENCE SYSTEM
     Save/load: nodes, forces, temperature, energy, layout_state

THE BRAIN CYCLE (runs every tick):
  1. perceive UI → graph
  2. apply forces (with learned weights)
  3. compute energy
  4. adapt weights based on energy history
  5. anneal (reduce temperature)
  6. integrate motion
  7. render (caller does this)

WHAT MAKES THIS "AI":
  The brain MODIFIES ITS OWN FORCE WEIGHTS based on feedback.
  If layout is unstable → it increases stabilization forces.
  If layout is stable → it reduces excess forces.
  Over time, the brain CONVERGES on optimal weight values.
  That is learning — not memorization, not ML, but adaptive feedback.

USAGE:
  from GuiAiBrain import GuiAiBrain

  brain = GuiAiBrain()
  brain.Run("perceive", {"spec": ui_spec_json})
  brain.Run("cycle", {"ticks": 300})
  brain.Run("report")
  brain.Run("persist", {"path": "brain_state.json"})
"""

import math
import json
import os
import random


# ════════════════════════════════════════════
# BRAIN CONSTANTS
# ════════════════════════════════════════════

DAMPING = 0.82
TEMP_DECAY = 0.98
MIN_TEMP = 0.001
MAX_VELOCITY = 20.0
LEARNING_RATE = 0.05
WEIGHT_MIN = 0.01
WEIGHT_MAX = 5.0
ENERGY_HISTORY_LEN = 50
STABLE_THRESHOLD = 5.0
INSTABILITY_THRESHOLD = 50.0

# Initial force weights (the brain learns to adjust these)
INIT_W_ATTRACT_CENTER = 1.0
INIT_W_REPULSION = 2.0
INIT_W_DOCK_LEFT = 1.5
INIT_W_DOCK_RIGHT = 1.5
INIT_W_DOCK_TOP = 1.5
INIT_W_DOCK_BOTTOM = 1.5
INIT_W_STABILITY = 0.90
INIT_W_SPACING = 0.8
INIT_W_ALIGNMENT = 1.0

# VSCode zone targets
ZONE_LEFT_X = 10
ZONE_RIGHT_MARGIN = 220
ZONE_TOP_Y = 10
ZONE_BOTTOM_MARGIN = 120
ZONE_CENTER_X = 300
ZONE_CENTER_Y = 250


class GuiAiBrain:
    """
    Self-organizing GUI layout brain.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    8 layers: perceive, world model, forces, energy, learning, annealing, compile, persist.
    The brain adapts force weights based on energy feedback — that is the AI.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "damping": DAMPING,
                "temp_decay": TEMP_DECAY,
                "min_temp": MIN_TEMP,
                "max_velocity": MAX_VELOCITY,
                "learning_rate": LEARNING_RATE,
                "weight_min": WEIGHT_MIN,
                "weight_max": WEIGHT_MAX,
                "canvas_w": 1000,
                "canvas_h": 700,
            },
            # Layer 1: Perception — the graph
            "graph": {
                "nodes": {},
                "edges": [],
                "constraints": [],
            },
            # Layer 2: World Model — memory
            "world_model": {
                "energy_history": [],
                "weight_history": [],
                "last_stable": None,
                "best_energy": 999999.0,
                "best_weights": None,
                "tick_count": 0,
            },
            # Layer 3: Force Field — learned weights (THE BRAIN)
            "weights": {
                "attract_center": INIT_W_ATTRACT_CENTER,
                "repulsion": INIT_W_REPULSION,
                "dock_left": INIT_W_DOCK_LEFT,
                "dock_right": INIT_W_DOCK_RIGHT,
                "dock_top": INIT_W_DOCK_TOP,
                "dock_bottom": INIT_W_DOCK_BOTTOM,
                "stability": INIT_W_STABILITY,
                "spacing": INIT_W_SPACING,
                "alignment": INIT_W_ALIGNMENT,
            },
            # Layer 4: Energy — current score
            "energy": {
                "total": 0.0,
                "overlap_cost": 0.0,
                "misalignment_cost": 0.0,
                "constraint_violation": 0.0,
                "unused_space": 0.0,
                "order_reward": 0.0,
            },
            # Layer 6: Annealing
            "temperature": 0.0,
            "frozen": False,
            # Layer 8: Persistence
            "layout_state": "init",
            # Stats
            "stats": {
                "ticks": 0,
                "adaptations": 0,
                "cycles": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "perceive": self.cmd_perceive,
            "cycle": self.cmd_cycle,
            "energy": self.cmd_energy,
            "adapt": self.cmd_adapt,
            "anneal": self.cmd_anneal,
            "compile": self.cmd_compile,
            "persist": self.cmd_persist,
            "restore": self.cmd_restore,
            "report": self.cmd_report,
            "graph": self.cmd_graph,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command", 0))
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

    def clampWeight(self, w):
        cfg = self.state["config"]
        return max(cfg["weight_min"], min(cfg["weight_max"], w))

    # ════════════════════════════════════════════
    # LAYER 1: PERCEPTION — UI spec → graph
    # ════════════════════════════════════════════

    def cmd_perceive(self, params):
        """Convert UI spec into graph nodes, edges, constraints."""
        spec = self.p(params, "spec")
        if not spec:
            return (0, None, ("ERR_PARAMS", "spec required", 0))
        nodes = {}
        edges = []
        constraints = []
        for item in spec.get("items", []):
            nodeId = item.get("id", "")
            if not nodeId:
                continue
            nodes[nodeId] = {
                "id": nodeId,
                "type": item.get("type", "panel"),
                "role": item.get("role", "center"),
                "x": float(item.get("x", 100)),
                "y": float(item.get("y", 100)),
                "vx": 0.0,
                "vy": 0.0,
                "w": int(item.get("w", 200)),
                "h": int(item.get("h", 120)),
                "anchors": item.get("anchors", []),
                "mass": float(item.get("mass", 1.0)),
                "label": item.get("label", nodeId),
            }
        for edge in spec.get("edges", []):
            edges.append({
                "a": edge.get("a", ""),
                "b": edge.get("b", ""),
                "type": edge.get("type", "adjacent"),
                "strength": float(edge.get("strength", 0.5)),
            })
        for con in spec.get("constraints", []):
            constraints.append({
                "id": con.get("id", ""),
                "type": con.get("type", "dock"),
                "edge": con.get("edge", "left"),
                "strength": float(con.get("strength", 0.8)),
            })
        self.state["graph"]["nodes"] = nodes
        self.state["graph"]["edges"] = edges
        self.state["graph"]["constraints"] = constraints
        self.state["layout_state"] = "perceived"
        return (1, {
            "nodes": len(nodes),
            "edges": len(edges),
            "constraints": len(constraints),
        }, None)

    # ════════════════════════════════════════════
    # LAYER 3: FORCE FIELD — apply forces with learned weights
    # ════════════════════════════════════════════

    def applyForces(self, cfg):
        """Apply all forces to all nodes using current learned weights."""
        weights = self.state["weights"]
        nodes = self.state["graph"]["nodes"]
        cw = cfg["canvas_w"]
        ch = cfg["canvas_h"]
        cx = cw / 2.0
        cy = ch / 2.0

        for nodeId, node in nodes.items():
            fx = 0.0
            fy = 0.0

            # A. Attraction — center gravity
            dx = cx - (node["x"] + node["w"] / 2.0)
            dy = cy - (node["y"] + node["h"] / 2.0)
            fx += dx * 0.001 * weights["attract_center"]
            fy += dy * 0.001 * weights["attract_center"]

            # A. Attraction — dock anchors (from constraints)
            for con in self.state["graph"]["constraints"]:
                if con["id"] != nodeId:
                    continue
                edge = con["edge"]
                strength = con["strength"]
                if edge == "left":
                    fx += (ZONE_LEFT_X - node["x"]) * 0.01 * weights["dock_left"] * strength
                elif edge == "right":
                    targetX = cw - ZONE_RIGHT_MARGIN
                    fx += (targetX - node["x"]) * 0.01 * weights["dock_right"] * strength
                elif edge == "top":
                    fy += (ZONE_TOP_Y - node["y"]) * 0.01 * weights["dock_top"] * strength
                elif edge == "bottom":
                    targetY = ch - ZONE_BOTTOM_MARGIN
                    fy += (targetY - node["y"]) * 0.01 * weights["dock_bottom"] * strength

            # B. Repulsion — pairwise overlap prevention
            for otherId, other in nodes.items():
                if otherId == nodeId:
                    continue
                odx = (node["x"] + node["w"] / 2.0) - (other["x"] + other["w"] / 2.0)
                ody = (node["y"] + node["h"] / 2.0) - (other["y"] + other["h"] / 2.0)
                dist = math.sqrt(odx * odx + ody * ody) + 0.01
                minDist = (node["w"] + other["w"]) / 2.0
                if dist < minDist:
                    force = weights["repulsion"] * ((minDist - dist) / minDist) * 0.5
                    fx += (odx / dist) * force * 10
                    fy += (ody / dist) * force * 10
                # Spacing force — keep minimum distance
                elif dist < minDist * 1.5:
                    force = weights["spacing"] * 0.01
                    fx += (odx / dist) * force * 5
                    fy += (ody / dist) * force * 5

            # C. Constraint — boundary limits
            margin = 10
            if node["x"] < margin:
                fx += (margin - node["x"]) * 0.05 * weights["stability"]
            if node["x"] + node["w"] > cw - margin:
                fx -= (node["x"] + node["w"] - (cw - margin)) * 0.05 * weights["stability"]
            if node["y"] < margin:
                fy += (margin - node["y"]) * 0.05 * weights["stability"]
            if node["y"] + node["h"] > ch - margin:
                fy -= (node["y"] + node["h"] - (ch - margin)) * 0.05 * weights["stability"]

            # Temperature noise (annealing)
            temp = self.state["temperature"]
            if temp > MIN_TEMP:
                fx += random.uniform(-temp, temp) * 0.5
                fy += random.uniform(-temp, temp) * 0.5

            # Integrate motion
            node["vx"] = (node["vx"] + fx) * weights["stability"]
            node["vy"] = (node["vy"] + fy) * weights["stability"]

            # Clamp velocity
            maxV = cfg["max_velocity"]
            node["vx"] = max(-maxV, min(maxV, node["vx"]))
            node["vy"] = max(-maxV, min(maxV, node["vy"]))

            # Update position
            node["x"] += node["vx"]
            node["y"] += node["vy"]

    # ════════════════════════════════════════════
    # LAYER 4: ENERGY FUNCTION — the brain metric
    # ════════════════════════════════════════════

    def computeEnergy(self, cfg):
        """Compute total energy — lower = better layout."""
        nodes = self.state["graph"]["nodes"]
        cw = cfg["canvas_w"]
        ch = cfg["canvas_h"]
        overlapCost = 0.0
        misalignmentCost = 0.0
        constraintViolation = 0.0
        unusedSpace = 0.0
        orderReward = 0.0

        nodeList = list(nodes.values())

        # Overlap cost — pairwise overlap area
        for i in range(len(nodeList)):
            for j in range(i + 1, len(nodeList)):
                a = nodeList[i]
                b = nodeList[j]
                ox = max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
                oy = max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
                overlapCost += ox * oy * 0.1

        # Misalignment cost — distance from dock targets
        for con in self.state["graph"]["constraints"]:
            node = nodes.get(con["id"])
            if not node:
                continue
            edge = con["edge"]
            if edge == "left":
                misalignmentCost += abs(node["x"] - ZONE_LEFT_X) * con["strength"]
            elif edge == "right":
                targetX = cw - ZONE_RIGHT_MARGIN
                misalignmentCost += abs(node["x"] - targetX) * con["strength"]
            elif edge == "top":
                misalignmentCost += abs(node["y"] - ZONE_TOP_Y) * con["strength"]
            elif edge == "bottom":
                targetY = ch - ZONE_BOTTOM_MARGIN
                misalignmentCost += abs(node["y"] - targetY) * con["strength"]

        # Constraint violation — out of bounds
        for node in nodeList:
            if node["x"] < 0:
                constraintViolation += abs(node["x"]) * 2
            if node["x"] + node["w"] > cw:
                constraintViolation += (node["x"] + node["w"] - cw) * 2
            if node["y"] < 0:
                constraintViolation += abs(node["y"]) * 2
            if node["y"] + node["h"] > ch:
                constraintViolation += (node["y"] + node["h"] - ch) * 2

        # Unused space — gaps between nodes
        totalArea = sum(n["w"] * n["h"] for n in nodeList)
        canvasArea = cw * ch
        unusedSpace = max(0, canvasArea - totalArea) * 0.001

        # Order reward — nodes at their dock positions get negative cost
        for con in self.state["graph"]["constraints"]:
            node = nodes.get(con["id"])
            if not node:
                continue
            edge = con["edge"]
            if edge == "left" and abs(node["x"] - ZONE_LEFT_X) < 20:
                orderReward -= 10
            elif edge == "right" and abs(node["x"] - (cw - ZONE_RIGHT_MARGIN)) < 20:
                orderReward -= 10
            elif edge == "top" and abs(node["y"] - ZONE_TOP_Y) < 20:
                orderReward -= 10
            elif edge == "bottom" and abs(node["y"] - (ch - ZONE_BOTTOM_MARGIN)) < 20:
                orderReward -= 10

        total = overlapCost + misalignmentCost + constraintViolation + unusedSpace + orderReward
        self.state["energy"] = {
            "total": round(total, 2),
            "overlap_cost": round(overlapCost, 2),
            "misalignment_cost": round(misalignmentCost, 2),
            "constraint_violation": round(constraintViolation, 2),
            "unused_space": round(unusedSpace, 2),
            "order_reward": round(orderReward, 2),
        }
        return total

    # ════════════════════════════════════════════
    # LAYER 5: LEARNING — adaptive weight update
    # ════════════════════════════════════════════

    def cmd_adapt(self, params):
        """Adapt force weights based on energy history — THE AI LEARNING."""
        cfg = self.state["config"]
        lr = cfg["learning_rate"]
        weights = self.state["weights"]
        history = self.state["world_model"]["energy_history"]
        energy = self.state["energy"]

        if len(history) < 2:
            return (1, {"adapted": False, "reason": "insufficient history"}, None)

        prevEnergy = history[-2]
        currEnergy = history[-1]
        delta = currEnergy - prevEnergy

        adaptations = []
        wm = self.state["world_model"]

        if delta > INSTABILITY_THRESHOLD:
            # Energy INCREASING — layout getting worse
            # Increase stabilization forces
            weights["repulsion"] = self.clampWeight(weights["repulsion"] * (1.0 + lr))
            weights["stability"] = self.clampWeight(weights["stability"] * (1.0 - lr * 0.5))
            weights["spacing"] = self.clampWeight(weights["spacing"] * (1.0 + lr * 0.5))
            adaptations.append("repulsion UP (overlap detected)")
            adaptations.append("stability DOWN (allow movement)")
            adaptations.append("spacing UP (more separation)")
            wm["adaptations"] = wm.get("adaptations", 0) + 3
            self.state["stats"]["adaptations"] += 3

        elif delta > STABLE_THRESHOLD:
            # Mild instability — fine-tune
            weights["alignment"] = self.clampWeight(weights["alignment"] * (1.0 + lr * 0.3))
            weights["dock_top"] = self.clampWeight(weights["dock_top"] * (1.0 + lr * 0.2))
            weights["dock_left"] = self.clampWeight(weights["dock_left"] * (1.0 + lr * 0.2))
            adaptations.append("alignment UP (fine-tuning)")
            adaptations.append("dock forces UP (snapping)")
            wm["adaptations"] = wm.get("adaptations", 0) + 3
            self.state["stats"]["adaptations"] += 3

        elif delta < -STABLE_THRESHOLD:
            # Energy DECREASING — layout improving
            # Stabilize current weights, reduce excess
            weights["stability"] = self.clampWeight(weights["stability"] * (1.0 + lr * 0.1))
            weights["repulsion"] = self.clampWeight(weights["repulsion"] * (1.0 - lr * 0.1))
            adaptations.append("stability UP (locking in)")
            adaptations.append("repulsion DOWN (settled)")
            wm["adaptations"] = wm.get("adaptations", 0) + 2
            self.state["stats"]["adaptations"] += 2

            # Track best state
            if currEnergy < wm["best_energy"]:
                wm["best_energy"] = currEnergy
                wm["best_weights"] = dict(weights)
                wm["last_stable"] = {
                    nodeId: {"x": n["x"], "y": n["y"]}
                    for nodeId, n in self.state["graph"]["nodes"].items()
                }
                self.state["layout_state"] = "stable"

        # Record weight history
        wm["weight_history"].append(dict(weights))
        if len(wm["weight_history"]) > ENERGY_HISTORY_LEN:
            wm["weight_history"] = wm["weight_history"][-ENERGY_HISTORY_LEN:]

        return (1, {
            "adapted": len(adaptations) > 0,
            "energy_delta": round(delta, 2),
            "adaptations": adaptations,
            "current_weights": dict(weights),
        }, None)

    # ════════════════════════════════════════════
    # LAYER 6: ANNEALING — shake and cool
    # ════════════════════════════════════════════

    def cmd_anneal(self, params):
        """Set or decay temperature."""
        temp = self.p(params, "temperature")
        if temp is not None:
            self.state["temperature"] = float(temp)
            self.state["frozen"] = self.state["temperature"] < self.state["config"]["min_temp"]
            return (1, {
                "temperature": self.state["temperature"],
                "frozen": self.state["frozen"],
            }, None)
        # Decay
        decay = self.state["config"]["temp_decay"]
        self.state["temperature"] *= decay
        if self.state["temperature"] < self.state["config"]["min_temp"]:
            self.state["temperature"] = 0.0
            self.state["frozen"] = True
        return (1, {
            "temperature": round(self.state["temperature"], 4),
            "frozen": self.state["frozen"],
        }, None)

    # ════════════════════════════════════════════
    # LAYER 4: ENERGY — command
    # ════════════════════════════════════════════

    def cmd_energy(self, params):
        """Get current energy breakdown."""
        cfg = self.state["config"]
        total = self.computeEnergy(cfg)
        return (1, dict(self.state["energy"]), None)

    # ════════════════════════════════════════════
    # MAIN CYCLE — the brain loop
    # ════════════════════════════════════════════

    def cmd_cycle(self, params):
        """Run the full brain cycle for N ticks."""
        ticks = int(self.p(params, "ticks", 100))
        cfg = self.state["config"]
        wm = self.state["world_model"]
        results = []

        for i in range(ticks):
            # 1. Apply forces (with learned weights)
            self.applyForces(cfg)

            # 2. Compute energy
            energy = self.computeEnergy(cfg)
            wm["energy_history"].append(round(energy, 2))
            if len(wm["energy_history"]) > ENERGY_HISTORY_LEN:
                wm["energy_history"] = wm["energy_history"][-ENERGY_HISTORY_LEN:]

            # 3. Adapt weights (THE LEARNING)
            ok, adaptData, err = self.cmd_adapt({})
            adapted = False
            if ok and adaptData:
                adapted = adaptData.get("adapted", False)

            # 4. Anneal (reduce temperature)
            okA, dataA, errA = self.cmd_anneal({})
            if not okA:
                break

            # 5. Record tick
            wm["tick_count"] += 1
            self.state["stats"]["ticks"] += 1

            if i % 10 == 0 or i == ticks - 1:
                results.append({
                    "tick": wm["tick_count"],
                    "energy": round(energy, 2),
                    "temp": round(self.state["temperature"], 4),
                    "adapted": adapted,
                    "frozen": self.state["frozen"],
                })

            # Stop if frozen and stable
            if self.state["frozen"] and energy < STABLE_THRESHOLD:
                self.state["layout_state"] = "converged"
                break

        self.state["stats"]["cycles"] += 1
        finalEnergy = self.computeEnergy(cfg)
        return (1, {
            "ticks_run": len(results),
            "final_energy": round(finalEnergy, 2),
            "final_temp": round(self.state["temperature"], 4),
            "frozen": self.state["frozen"],
            "layout_state": self.state["layout_state"],
            "best_energy": round(wm["best_energy"], 2),
            "total_adaptations": self.state["stats"]["adaptations"],
            "history": results,
        }, None)

    # ════════════════════════════════════════════
    # LAYER 7: LAYOUT COMPILER — graph → layout dict
    # ════════════════════════════════════════════

    def cmd_compile(self, params):
        """Compile graph into final layout dict for PyQt rendering."""
        nodes = self.state["graph"]["nodes"]
        layout = {}
        for nodeId, node in nodes.items():
            # Determine zone based on position
            cfg = self.state["config"]
            cw = cfg["canvas_w"]
            ch = cfg["canvas_h"]
            zone = "center"
            if node["x"] < cw * 0.25:
                zone = "left"
            elif node["x"] + node["w"] > cw * 0.75:
                zone = "right"
            if node["y"] < ch * 0.15:
                zone = "top"
            elif node["y"] + node["h"] > ch * 0.85:
                zone = "bottom"
            layout[nodeId] = {
                "id": nodeId,
                "type": node["type"],
                "role": node["role"],
                "x": round(node["x"], 1),
                "y": round(node["y"], 1),
                "w": node["w"],
                "h": node["h"],
                "zone": zone,
                "vx": round(node["vx"], 3),
                "vy": round(node["vy"], 3),
            }
        return (1, {
            "layout": layout,
            "energy": self.state["energy"]["total"],
            "layout_state": self.state["layout_state"],
            "weights": dict(self.state["weights"]),
        }, None)

    # ════════════════════════════════════════════
    # LAYER 8: PERSISTENCE — save/load
    # ════════════════════════════════════════════

    def cmd_persist(self, params):
        """Save brain state to JSON."""
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        state = {
            "nodes": {
                nid: {"x": n["x"], "y": n["y"], "w": n["w"], "h": n["h"],
                      "type": n["type"], "role": n["role"], "label": n["label"]}
                for nid, n in self.state["graph"]["nodes"].items()
            },
            "edges": self.state["graph"]["edges"],
            "constraints": self.state["graph"]["constraints"],
            "weights": dict(self.state["weights"]),
            "temperature": self.state["temperature"],
            "energy": self.state["energy"]["total"],
            "layout_state": self.state["layout_state"],
            "best_energy": self.state["world_model"]["best_energy"],
            "best_weights": self.state["world_model"]["best_weights"],
            "tick_count": self.state["world_model"]["tick_count"],
        }
        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            return (0, None, ("ERR_WRITE", str(e)[:200], 0))
        return (1, {"saved": True, "path": path, "state": state["layout_state"]}, None)

    def cmd_restore(self, params):
        """Load brain state from JSON."""
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not os.path.exists(path):
            return (0, None, ("ERR_NOT_FOUND", "file not found", 0))
        try:
            with open(path, "r") as f:
                state = json.load(f)
        except Exception as e:
            return (0, None, ("ERR_PARSE", str(e)[:200], 0))
        # Restore nodes
        for nid, n in state.get("nodes", {}).items():
            if nid in self.state["graph"]["nodes"]:
                node = self.state["graph"]["nodes"][nid]
                node["x"] = float(n.get("x", node["x"]))
                node["y"] = float(n.get("y", node["y"]))
                node["vx"] = 0.0
                node["vy"] = 0.0
        # Restore weights
        if "weights" in state:
            for k, v in state["weights"].items():
                if k in self.state["weights"]:
                    self.state["weights"][k] = float(v)
        # Restore temperature
        self.state["temperature"] = float(state.get("temperature", 0.0))
        self.state["layout_state"] = state.get("layout_state", "restored")
        if "best_energy" in state:
            self.state["world_model"]["best_energy"] = float(state["best_energy"])
        if "best_weights" in state:
            self.state["world_model"]["best_weights"] = state["best_weights"]
        return (1, {"restored": True, "path": path, "state": self.state["layout_state"]}, None)

    # ════════════════════════════════════════════
    # REPORT + GRAPH
    # ════════════════════════════════════════════

    def cmd_report(self, params):
        """Full brain report."""
        e = self.state["energy"]
        w = self.state["weights"]
        wm = self.state["world_model"]
        lines = []
        lines.append("GUI AI BRAIN REPORT")
        lines.append("====================")
        lines.append("Layout State: %s" % self.state["layout_state"])
        lines.append("Ticks: %d  Cycles: %d  Adaptations: %d" % (
            self.state["stats"]["ticks"], self.state["stats"]["cycles"],
            self.state["stats"]["adaptations"]))
        lines.append("Temperature: %.4f  Frozen: %s" % (
            self.state["temperature"], self.state["frozen"]))
        lines.append("")
        lines.append("ENERGY BREAKDOWN:")
        lines.append("-" * 50)
        lines.append("  Total:              %8.2f" % e["total"])
        lines.append("  Overlap cost:       %8.2f" % e["overlap_cost"])
        lines.append("  Misalignment cost:  %8.2f" % e["misalignment_cost"])
        lines.append("  Constraint viol:    %8.2f" % e["constraint_violation"])
        lines.append("  Unused space:       %8.2f" % e["unused_space"])
        lines.append("  Order reward:       %8.2f" % e["order_reward"])
        lines.append("")
        lines.append("LEARNED WEIGHTS (the brain):")
        lines.append("-" * 50)
        for wk, wv in sorted(w.items()):
            barLen = min(int(wv * 10), 30)
            bar = "█" * barLen + "░" * (30 - barLen)
            lines.append("  %-20s  %.4f  %s" % (wk, wv, bar))
        lines.append("")
        lines.append("WORLD MODEL:")
        lines.append("-" * 50)
        lines.append("  Best energy:    %.2f" % wm["best_energy"])
        lines.append("  Tick count:     %d" % wm["tick_count"])
        if wm["energy_history"]:
            lines.append("  Energy history (last 10):")
            hist = wm["energy_history"][-10:]
            for i, h in enumerate(hist):
                barLen = min(int(abs(h) / 10), 30)
                bar = "█" * barLen
                lines.append("    %3d: %8.2f  %s" % (i, h, bar))
        lines.append("")
        lines.append("NODES:")
        lines.append("-" * 50)
        for nodeId, node in self.state["graph"]["nodes"].items():
            speed = math.sqrt(node["vx"] ** 2 + node["vy"] ** 2)
            lines.append("  %-15s  pos=(%5.0f,%5.0f)  vel=%5.2f  type=%s" % (
                nodeId, node["x"], node["y"], speed, node["type"]))
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual brain graph."""
        e = self.state["energy"]
        w = self.state["weights"]
        wm = self.state["world_model"]
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║            GUI AI BRAIN — Self-Organizing Layout            ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  State: %s  |  Ticks: %d  |  Adaptations: %d" % (
            self.state["layout_state"], self.state["stats"]["ticks"],
            self.state["stats"]["adaptations"]))
        lines.append("  Temp: %.4f  |  Frozen: %s  |  Best: %.2f" % (
            self.state["temperature"], self.state["frozen"], wm["best_energy"]))
        lines.append("")

        # Energy bar
        energy = e["total"]
        barLen = 30
        if energy >= 0:
            filled = min(int(energy / 10), barLen)
            bar = "█" * filled + "░" * (barLen - filled)
        else:
            filled = min(int(abs(energy) / 10), barLen)
            bar = "🟩" * filled
        lines.append("  Energy:  [%s]  %.2f" % (bar[:30], energy))
        if energy < 0:
            lines.append("  Status:  🔵 EXCELLENT — negative energy (order reward dominates)")
        elif energy < STABLE_THRESHOLD:
            lines.append("  Status:  🟢 STABLE — layout converged")
        elif energy < INSTABILITY_THRESHOLD:
            lines.append("  Status:  🟡 SETTLING — still adapting")
        else:
            lines.append("  Status:  🔴 UNSTABLE — brain is learning")
        lines.append("")

        # Energy breakdown
        lines.append("  ┌─ ENERGY BREAKDOWN ────────────────────────────────────────┐")
        lines.append("  │  Overlap:       %8.2f" % e["overlap_cost"])
        lines.append("  │  Misalignment:  %8.2f" % e["misalignment_cost"])
        lines.append("  │  Constraint:    %8.2f" % e["constraint_violation"])
        lines.append("  │  Unused space:  %8.2f" % e["unused_space"])
        lines.append("  │  Order reward:  %8.2f" % e["order_reward"])
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Learned weights — THE BRAIN
        lines.append("  ┌─ LEARNED WEIGHTS (the AI brain) ──────────────────────────┐")
        for wk in sorted(w.keys()):
            wv = w[wk]
            barLen = min(int(wv * 10), 20)
            bar = "🧠" * barLen
            lines.append("  │  %-20s  %.4f  %s" % (wk, wv, bar))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Nodes
        lines.append("  ┌─ NODES (the GUI) ─────────────────────────────────────────┐")
        for nodeId, node in self.state["graph"]["nodes"].items():
            speed = math.sqrt(node["vx"] ** 2 + node["vy"] ** 2)
            if speed > 5:
                motion = "FAST"
            elif speed > 1:
                motion = "moving"
            elif speed > 0.1:
                motion = "slow"
            else:
                motion = "still"
            lines.append("  │  %-15s  pos=(%5.0f,%5.0f)  %s  type=%-10s" % (
                nodeId[:15], node["x"], node["y"], motion, node["type"][:10]))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Energy history (learning curve)
        hist = wm["energy_history"]
        if hist:
            lines.append("  ┌─ LEARNING CURVE (energy over time) ───────────────────────┐")
            showSteps = min(len(hist), 20)
            for i in range(max(0, len(hist) - showSteps), len(hist)):
                h = hist[i]
                if h >= 0:
                    barLen = min(int(h / 10), 30)
                    bar = "█" * barLen + "░" * (30 - barLen)
                else:
                    barLen = min(int(abs(h) / 5), 30)
                    bar = "🟩" * barLen
                lines.append("  │  T%3d: %8.2f  %s" % (i, h, bar[:30]))
            lines.append("  └────────────────────────────────────────────────────────────┘")
            lines.append("")

        # Weight adaptation history
        wHist = wm["weight_history"]
        if wHist:
            lines.append("  ┌─ WEIGHT EVOLUTION (brain learning) ───────────────────────┐")
            lines.append("  │  %-12s  %8s  %8s  %8s  %8s" % (
                "tick", "repulse", "dock_L", "stab", "align"))
            showSteps = min(len(wHist), 10)
            for i in range(max(0, len(wHist) - showSteps), len(wHist)):
                wh = wHist[i]
                lines.append("  │  T%3d         %.3f    %.3f    %.3f    %.3f" % (
                    i, wh.get("repulsion", 0), wh.get("dock_left", 0),
                    wh.get("stability", 0), wh.get("alignment", 0)))
            lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)
