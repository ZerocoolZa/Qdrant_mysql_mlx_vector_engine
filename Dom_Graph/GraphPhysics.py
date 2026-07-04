#!/usr/bin/env python3
# [@GHOST]{[@file<GraphPhysics.py>][@domain<graph>][@role<physics_annealing>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<physics_annealing>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{GraphPhysics — Shake-the-bowl simulated annealing for GUI layout. Force fields + collisions + temperature noise + annealing schedule. Elements bump around, find where they belong, lock in. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{GraphPhysics}
# [@METHOD]{Run,add,anchor,force,shake,step,anneal,settle,energy,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Simulated annealing physics engine for GUI layout. Force fields, collisions, temperature noise. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
GraphPhysics — Shake-the-bowl simulated annealing for GUI layout.

THE PHYSICAL INTUITION:
  Put buttons, labels, panels in a bowl.
  Assign magnetic forces — attract (+), repel (-).
  Add anchors — top, left, right, bottom, center.
  Shake the bowl hard.
  Elements bump around, collide, push, pull.
  Gradually stop shaking.
  Everything settles into where it belongs.

THE 4 LAYERS:

  1. FORCE FIELD LAYER
     - toolbar attracts top edge
     - sidebar attracts left edge
     - buttons repel each other (don't overlap)
     - labels attract their inputs
     - panels attract center

  2. PHYSICS LAYER
     - velocity, damping, collision response
     - elements bounce off walls and each other
     - momentum carries elements past bad spots

  3. TEMPERATURE LAYER (the shake)
     - position += random_noise * temperature
     - high temperature = chaos (explore)
     - low temperature = settle (lock in)

  4. ANNEALING SCHEDULE
     - temperature starts high (1.0)
     - decreases over time (cooling rate)
     - at temperature 0, system is frozen
     - elements locked in final position

THE EQUATION:
  Total Energy =
      attraction_terms      (magnetic pulls)
    + repulsion_terms        (magnetic pushes)
    + boundary_constraints   (wall penalties)
    + collision_penalties    (overlap penalties)
    + temperature_noise      (random shake)

  Goal: minimize energy over time via annealing.

WHY SHAKING WORKS:
  - Shaking escapes bad local layouts (local minima)
  - Elements re-explore the space
  - Collisions force separation
  - Constraints reassert structure
  - As shaking reduces, system locks into stable config

USAGE:
  from GraphPhysics import GraphPhysics

  gp = GraphPhysics()
  gp.Run("add", {"id": "toolbar", "type": "Toolbar", "x": 100, "y": 50, "w": 600, "h": 30})
  gp.Run("add", {"id": "sidebar", "type": "Sidebar", "x": 50, "y": 100, "w": 200, "h": 400})
  gp.Run("add", {"id": "editor", "type": "Editor", "x": 300, "y": 100, "w": 400, "h": 400})

  # Assign forces
  gp.Run("anchor", {"id": "toolbar", "edge": "top", "strength": 0.9})
  gp.Run("anchor", {"id": "sidebar", "edge": "left", "strength": 0.8})
  gp.Run("force", {"a": "toolbar", "b": "sidebar", "type": "repel", "strength": 0.5})

  # Shake the bowl!
  gp.Run("shake", {"temperature": 1.0})
  gp.Run("anneal", {"steps": 200, "cooling": 0.95})

  # System settled — check energy
  gp.Run("energy")
  gp.Run("graph")
"""

import math
import random


# ════════════════════════════════════════════
# PHYSICS CONSTANTS
# ════════════════════════════════════════════

DAMPING = 0.80                    # velocity decay per step
FORCE_SCALE = 0.03                # overall force multiplier
COLLISION_BOUNCE = 0.3            # energy retained on collision
DEFAULT_TEMP = 0.8                # starting temperature (max shake)
DEFAULT_COOLING = 0.99            # cooling rate per step
MIN_TEMP = 0.001                  # temperature at which system is frozen
WALL_BOUNCE = 0.2                 # velocity retained on wall hit
BOUNDARY_MARGIN = 10              # margin from canvas edge
ANCHOR_PULL = 0.04                # anchor force strength (gentle)
REPEL_STRENGTH = 0.2              # default repulsion between same-type
ATTRACT_STRENGTH = 0.08           # default attraction between paired items
COLLISION_REPEL = 8.0             # force multiplier when overlapping


class GraphPhysics:
    """
    Shake-the-bowl simulated annealing for GUI layout.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Force fields + collisions + temperature + annealing.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "damping": DAMPING,
                "force_scale": FORCE_SCALE,
                "collision_bounce": COLLISION_BOUNCE,
                "wall_bounce": WALL_BOUNCE,
                "boundary_margin": BOUNDARY_MARGIN,
                "anchor_pull": ANCHOR_PULL,
                "repel_strength": REPEL_STRENGTH,
                "attract_strength": ATTRACT_STRENGTH,
                "collision_repel": COLLISION_REPEL,
                "canvas_w": 1000,
                "canvas_h": 700,
            },
            "items": {},            # id → item dict
            "forces": [],           # explicit force pairs
            "anchors": {},          # id → {edge, strength}
            "temperature": 0.0,     # current shake amount
            "cooling_rate": DEFAULT_COOLING,
            "step_count": 0,
            "frozen": False,
            "energy_history": [],
            "collision_count": 0,
            "stats": {"steps": 0, "collisions": 0, "shakes": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "add": self.cmd_add,
            "anchor": self.cmd_anchor,
            "force": self.cmd_force,
            "shake": self.cmd_shake,
            "step": self.cmd_step,
            "anneal": self.cmd_anneal,
            "settle": self.cmd_settle,
            "energy": self.cmd_energy,
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

    # ════════════════════════════════════════════
    # INTERNAL — physics calculations
    # ════════════════════════════════════════════

    def itemBounds(self, item):
        """Get bounding box of an item."""
        x = item["x"]
        y = item["y"]
        w = item["w"]
        h = item["h"]
        return (x, y, x + w, y + h)

    def itemsOverlap(self, a, b):
        """Check if two items overlap."""
        ax1, ay1, ax2, ay2 = self.itemBounds(a)
        bx1, by1, bx2, by2 = self.itemBounds(b)
        return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

    def overlapArea(self, a, b):
        """Calculate overlap area between two items."""
        ax1, ay1, ax2, ay2 = self.itemBounds(a)
        bx1, by1, bx2, by2 = self.itemBounds(b)
        ox = max(0, min(ax2, bx2) - max(ax1, bx1))
        oy = max(0, min(ay2, by2) - max(ay1, by1))
        return ox * oy

    def centerDistance(self, a, b):
        """Distance between centers of two items."""
        acx = a["x"] + a["w"] / 2.0
        acy = a["y"] + a["h"] / 2.0
        bcx = b["x"] + b["w"] / 2.0
        bcy = b["y"] + b["h"] / 2.0
        dx = acx - bcx
        dy = acy - bcy
        return math.sqrt(dx * dx + dy * dy)

    def anchorPosition(self, item, edge, cfg):
        """Get the target position for an anchored edge."""
        w = cfg["canvas_w"]
        h = cfg["canvas_h"]
        m = cfg["boundary_margin"]
        if edge == "top":
            return (item["x"], m)
        elif edge == "bottom":
            return (item["x"], h - m - item["h"])
        elif edge == "left":
            return (m, item["y"])
        elif edge == "right":
            return (w - m - item["w"], item["y"])
        elif edge == "center":
            return ((w - item["w"]) / 2.0, (h - item["h"]) / 2.0)
        return (item["x"], item["y"])

    def applyAnchorForce(self, item, itemId, cfg):
        """Apply force from anchor toward target edge position."""
        anchor = self.state["anchors"].get(itemId)
        if not anchor:
            return 0.0, 0.0
        tx, ty = self.anchorPosition(item, anchor["edge"], cfg)
        dx = tx - item["x"]
        dy = ty - item["y"]
        strength = anchor["strength"] * cfg["anchor_pull"]
        return dx * strength, dy * strength

    def applyForces(self, item, itemId, cfg):
        """Apply explicit force pairs (attract/repel)."""
        fxTotal = 0.0
        fyTotal = 0.0
        for f in self.state["forces"]:
            if f["a"] != itemId and f["b"] != itemId:
                continue
            otherId = f["b"] if f["a"] == itemId else f["a"]
            other = self.state["items"].get(otherId)
            if not other:
                continue
            dist = self.centerDistance(item, other)
            if dist < 0.001:
                dist = 0.001
            dx = (other["x"] + other["w"] / 2.0) - (item["x"] + item["w"] / 2.0)
            dy = (other["y"] + other["h"] / 2.0) - (item["y"] + item["h"] / 2.0)
            strength = f["strength"] * cfg["force_scale"]
            if f["type"] == "repel":
                strength = -strength
            fxTotal += (dx / dist) * strength
            fyTotal += (dy / dist) * strength
        return fxTotal, fyTotal

    def applyCollisions(self, item, itemId, cfg):
        """Apply repulsion force from overlapping items."""
        fxTotal = 0.0
        fyTotal = 0.0
        for otherId, other in self.state["items"].items():
            if otherId == itemId:
                continue
            if not self.itemsOverlap(item, other):
                continue
            overlap = self.overlapArea(item, other)
            if overlap <= 0:
                continue
            dist = self.centerDistance(item, other)
            if dist < 0.001:
                dist = 0.001
            dx = (item["x"] + item["w"] / 2.0) - (other["x"] + other["w"] / 2.0)
            dy = (item["y"] + item["h"] / 2.0) - (other["y"] + other["h"] / 2.0)
            force = (overlap / 100.0) * cfg["collision_repel"] * cfg["force_scale"]
            fxTotal += (dx / dist) * force
            fyTotal += (dy / dist) * force
            self.state["collision_count"] += 1
        return fxTotal, fyTotal

    def applySameTypeRepel(self, item, itemId, cfg):
        """Same-type items repel each other (don't stack)."""
        fxTotal = 0.0
        fyTotal = 0.0
        for otherId, other in self.state["items"].items():
            if otherId == itemId:
                continue
            if other.get("type", "") != item.get("type", ""):
                continue
            if not item.get("type", ""):
                continue
            dist = self.centerDistance(item, other)
            if dist < 0.001:
                dist = 0.001
            if dist < 150:
                dx = (item["x"] + item["w"] / 2.0) - (other["x"] + other["w"] / 2.0)
                dy = (item["y"] + item["h"] / 2.0) - (other["y"] + other["h"] / 2.0)
                strength = cfg["repel_strength"] * (1.0 - dist / 150.0) * cfg["force_scale"]
                fxTotal += (dx / dist) * strength
                fyTotal += (dy / dist) * strength
        return fxTotal, fyTotal

    def applyWalls(self, item, cfg):
        """Bounce items off canvas walls."""
        w = cfg["canvas_w"]
        h = cfg["canvas_h"]
        m = cfg["boundary_margin"]
        bounce = cfg["wall_bounce"]
        if item["x"] < m:
            item["x"] = m
            item["vx"] = abs(item["vx"]) * bounce
        if item["x"] + item["w"] > w - m:
            item["x"] = w - m - item["w"]
            item["vx"] = -abs(item["vx"]) * bounce
        if item["y"] < m:
            item["y"] = m
            item["vy"] = abs(item["vy"]) * bounce
        if item["y"] + item["h"] > h - m:
            item["y"] = h - m - item["h"]
            item["vy"] = -abs(item["vy"]) * bounce

    def applyTemperature(self, item, cfg):
        """Add random noise based on temperature (the shake)."""
        temp = self.state["temperature"]
        if temp < MIN_TEMP:
            return
        item["vx"] += random.uniform(-temp, temp) * cfg["force_scale"]
        item["vy"] += random.uniform(-temp, temp) * cfg["force_scale"]

    def calcEnergy(self, cfg):
        """Calculate total system energy — lower = more stable."""
        energy = 0.0
        items = list(self.state["items"].values())
        # Collision energy (overlaps)
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self.itemsOverlap(items[i], items[j]):
                    energy += self.overlapArea(items[i], items[j]) * 0.1
        # Anchor energy (distance from target)
        for itemId, item in self.state["items"].items():
            anchor = self.state["anchors"].get(itemId)
            if anchor:
                tx, ty = self.anchorPosition(item, anchor["edge"], cfg)
                energy += math.sqrt((tx - item["x"]) ** 2 + (ty - item["y"]) ** 2) * anchor["strength"]
        # Force pair energy
        for f in self.state["forces"]:
            a = self.state["items"].get(f["a"])
            b = self.state["items"].get(f["b"])
            if a and b:
                dist = self.centerDistance(a, b)
                if f["type"] == "attract":
                    energy += dist * f["strength"] * 0.01
                else:
                    energy += max(0, 200 - dist) * f["strength"] * 0.01
        # Temperature energy
        energy += self.state["temperature"] * 50
        return energy

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_add(self, params):
        itemId = self.p(params, "id")
        if not itemId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        item = {
            "id": itemId,
            "type": self.p(params, "type", "Widget"),
            "x": float(self.p(params, "x", 0)),
            "y": float(self.p(params, "y", 0)),
            "vx": 0.0,
            "vy": 0.0,
            "w": int(self.p(params, "w", 100)),
            "h": int(self.p(params, "h", 30)),
            "label": self.p(params, "label", itemId),
        }
        self.state["items"][itemId] = item
        return (1, item, None)

    def cmd_anchor(self, params):
        """Anchor an item to an edge (top/bottom/left/right/center)."""
        itemId = self.p(params, "id")
        edge = self.p(params, "edge")
        if not itemId or not edge:
            return (0, None, ("ERR_PARAMS", "id and edge required", 0))
        if edge not in ("top", "bottom", "left", "right", "center"):
            return (0, None, ("ERR_PARAMS", "edge must be top/bottom/left/right/center", 0))
        if itemId not in self.state["items"]:
            return (0, None, ("ERR_NOT_FOUND", "item not found", 0))
        strength = float(self.p(params, "strength", 0.8))
        self.state["anchors"][itemId] = {"edge": edge, "strength": strength}
        return (1, {"id": itemId, "edge": edge, "strength": strength}, None)

    def cmd_force(self, params):
        """Define a force between two items (attract or repel)."""
        aId = self.p(params, "a")
        bId = self.p(params, "b")
        ftype = self.p(params, "type", "repel")
        if not aId or not bId:
            return (0, None, ("ERR_PARAMS", "a and b required", 0))
        if ftype not in ("attract", "repel"):
            return (0, None, ("ERR_PARAMS", "type must be attract or repel", 0))
        strength = float(self.p(params, "strength", 0.5))
        force = {"a": aId, "b": bId, "type": ftype, "strength": strength}
        self.state["forces"].append(force)
        return (1, force, None)

    def cmd_shake(self, params):
        """Set the temperature (shake amount). High = chaos, low = settle."""
        temp = float(self.p(params, "temperature", DEFAULT_TEMP))
        self.state["temperature"] = temp
        self.state["frozen"] = temp < MIN_TEMP
        self.state["stats"]["shakes"] += 1
        return (1, {
            "temperature": self.state["temperature"],
            "frozen": self.state["frozen"],
            "status": "FROZEN" if self.state["frozen"] else ("HOT" if temp > 0.7 else ("WARM" if temp > 0.3 else "COOL")),
        }, None)

    def cmd_step(self, params):
        """One physics step — apply all forces, collisions, temperature."""
        cfg = self.state["config"]
        damping = cfg["damping"]
        for itemId, item in self.state["items"].items():
            # Apply all forces
            afx, afy = self.applyAnchorForce(item, itemId, cfg)
            ffx, ffy = self.applyForces(item, itemId, cfg)
            cfx, cfy = self.applyCollisions(item, itemId, cfg)
            rfx, rfy = self.applySameTypeRepel(item, itemId, cfg)
            fx = afx + ffx + cfx + rfx
            fy = afy + ffy + cfy + rfy
            # Update velocity with damping
            item["vx"] = (item["vx"] + fx) * damping
            item["vy"] = (item["vy"] + fy) * damping
            # Apply temperature noise (the shake)
            self.applyTemperature(item, cfg)
            # Update position
            item["x"] += item["vx"]
            item["y"] += item["vy"]
            # Bounce off walls
            self.applyWalls(item, cfg)
        self.state["step_count"] += 1
        self.state["stats"]["steps"] += 1
        energy = self.calcEnergy(cfg)
        self.state["energy_history"].append(round(energy, 2))
        return (1, {
            "step": self.state["step_count"],
            "energy": round(energy, 2),
            "temperature": round(self.state["temperature"], 4),
            "collisions": self.state["collision_count"],
            "frozen": self.state["frozen"],
        }, None)

    def cmd_anneal(self, params):
        """Run annealing loop — shake hard, then gradually cool down."""
        steps = int(self.p(params, "steps", 100))
        cooling = float(self.p(params, "cooling", DEFAULT_COOLING))
        self.state["cooling_rate"] = cooling
        cfg = self.state["config"]
        results = []
        for i in range(steps):
            # Cool down
            self.state["temperature"] *= cooling
            if self.state["temperature"] < MIN_TEMP:
                self.state["temperature"] = 0.0
                self.state["frozen"] = True
            # Step physics
            ok, data, err = self.cmd_step({})
            if not ok:
                return (0, None, err)
            results.append({
                "step": data["step"],
                "energy": data["energy"],
                "temp": round(self.state["temperature"], 4),
            })
            if self.state["frozen"] and data["collisions"] == 0:
                break
        finalEnergy = self.calcEnergy(cfg)
        return (1, {
            "steps_run": len(results),
            "final_energy": round(finalEnergy, 2),
            "final_temp": round(self.state["temperature"], 4),
            "frozen": self.state["frozen"],
            "collisions": self.state["collision_count"],
            "history": results[-10:],
        }, None)

    def cmd_settle(self, params):
        """Run steps with zero temperature until energy stabilizes."""
        steps = int(self.p(params, "steps", 50))
        self.state["temperature"] = 0.0
        self.state["frozen"] = True
        cfg = self.state["config"]
        prevEnergy = 999999.0
        for i in range(steps):
            ok, data, err = self.cmd_step({})
            if not ok:
                return (0, None, err)
            currEnergy = data["energy"]
            if abs(prevEnergy - currEnergy) < 0.5:
                break
            prevEnergy = currEnergy
        return (1, {
            "settled": True,
            "steps": i + 1,
            "final_energy": round(currEnergy, 2),
            "collisions": self.state["collision_count"],
        }, None)

    def cmd_energy(self, params):
        """Get current system energy."""
        cfg = self.state["config"]
        energy = self.calcEnergy(cfg)
        collisions = 0
        items = list(self.state["items"].values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self.itemsOverlap(items[i], items[j]):
                    collisions += 1
        return (1, {
            "energy": round(energy, 2),
            "temperature": round(self.state["temperature"], 4),
            "collisions": collisions,
            "frozen": self.state["frozen"],
            "step": self.state["step_count"],
        }, None)

    def cmd_report(self, params):
        """Full physics report."""
        ok, energyData, err = self.cmd_energy({})
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("GRAPH PHYSICS REPORT")
        lines.append("====================")
        lines.append("Step: %d" % self.state["step_count"])
        lines.append("Energy: %.2f" % energyData["energy"])
        lines.append("Temperature: %.4f" % energyData["temperature"])
        lines.append("Frozen: %s" % energyData["frozen"])
        lines.append("Collisions: %d" % energyData["collisions"])
        lines.append("")
        lines.append("ITEMS:")
        lines.append("-" * 70)
        for itemId, item in self.state["items"].items():
            anchor = self.state["anchors"].get(itemId)
            anchorStr = "anchor=%s(%.2f)" % (anchor["edge"], anchor["strength"]) if anchor else "no anchor"
            lines.append("  %-15s  type=%-10s  pos=(%.1f,%.1f)  vel=(%+.2f,%+.2f)  %s" % (
                itemId, item["type"], item["x"], item["y"], item["vx"], item["vy"], anchorStr))
        lines.append("")
        lines.append("FORCES:")
        lines.append("-" * 70)
        for f in self.state["forces"]:
            icon = "🟢" if f["type"] == "attract" else "🔴"
            lines.append("  %s %-12s ↔ %-12s  %s  strength=%.2f" % (
                icon, f["a"], f["b"], f["type"], f["strength"]))
        if not self.state["forces"]:
            lines.append("  (none)")
        lines.append("")
        lines.append("OVERLAPS:")
        lines.append("-" * 70)
        items = list(self.state["items"].values())
        foundOverlap = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self.itemsOverlap(items[i], items[j]):
                    foundOverlap = True
                    area = self.overlapArea(items[i], items[j])
                    lines.append("  🔴 %-12s overlaps %-12s  area=%d" % (
                        items[i]["id"], items[j]["id"], area))
        if not foundOverlap:
            lines.append("  ✅ No overlaps — clean layout")
        if self.state["energy_history"]:
            lines.append("")
            lines.append("ENERGY HISTORY:")
            lines.append("-" * 70)
            hist = self.state["energy_history"]
            showSteps = min(len(hist), 20)
            for i in range(max(0, len(hist) - showSteps), len(hist)):
                e = hist[i]
                barLen = min(int(e / 10), 30)
                bar = "█" * barLen + "░" * (30 - barLen)
                lines.append("  Step %3d: %7.2f  %s" % (i + 1, e, bar))
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual physics graph — the bowl, shaken."""
        ok, energyData, err = self.cmd_energy({})
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║         GRAPH PHYSICS — Shake the Bowl Annealer             ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        temp = self.state["temperature"]
        energy = energyData["energy"]
        lines.append("  Step: %d   Energy: %.2f   Collisions: %d" % (
            self.state["step_count"], energy, energyData["collisions"]))
        lines.append("")

        # Temperature bar (the shake)
        barLen = 30
        tempFilled = min(int(temp * barLen), barLen)
        tempBar = "🔥" * tempFilled + "❄️" * (barLen - tempFilled)
        lines.append("  Temperature: [%.4f]  %s" % (temp, tempBar[:30]))
        if temp > 0.7:
            lines.append("  Status:  🔥 HOT — shaking hard, exploring")
        elif temp > 0.3:
            lines.append("  Status:  🌡️  WARM — settling down")
        elif temp > MIN_TEMP:
            lines.append("  Status:  🧊 COOL — almost frozen")
        else:
            lines.append("  Status:  ❄️  FROZEN — locked in place")
        lines.append("")

        # Energy bar
        energyFilled = min(int(energy / 10), barLen)
        energyBar = "█" * energyFilled + "░" * (barLen - energyFilled)
        lines.append("  Energy:  [%s]  %.2f" % (energyBar, energy))
        if energy < 10:
            lines.append("  Layout:  ✅ STABLE — minimal energy")
        elif energy < 50:
            lines.append("  Layout:  🟢 GOOD — mostly settled")
        elif energy < 200:
            lines.append("  Layout:  🟡 SETTLING — still moving")
        else:
            lines.append("  Layout:  🔴 CHAOTIC — high energy")
        lines.append("")

        # Items in the bowl
        lines.append("  ┌─ ITEMS IN THE BOWL ───────────────────────────────────────┐")
        for itemId, item in self.state["items"].items():
            anchor = self.state["anchors"].get(itemId)
            anchorIcon = "⚓" if anchor else "  "
            anchorStr = ""
            if anchor:
                anchorStr = " ⚓%s(%.1f)" % (anchor["edge"][:1].upper(), anchor["strength"])
            speed = math.sqrt(item["vx"] ** 2 + item["vy"] ** 2)
            if speed > 5:
                motion = "💨 FAST"
            elif speed > 1:
                motion = "🔄 moving"
            elif speed > 0.1:
                motion = "🐢 slow"
            else:
                motion = "🧊 still"
            lines.append("  │  %s %-12s  pos=(%5.0f,%5.0f)  %s%s" % (
                anchorIcon, itemId[:12], item["x"], item["y"], motion, anchorStr))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Forces
        if self.state["forces"]:
            lines.append("  ┌─ MAGNETIC FORCES ─────────────────────────────────────────┐")
            for f in self.state["forces"]:
                icon = "🧲➕" if f["type"] == "attract" else "🧲➖"
                lines.append("  │  %s  %-12s ↔ %-12s  %s  strength=%.2f" % (
                    icon, f["a"][:12], f["b"][:12], f["type"], f["strength"]))
            lines.append("  └────────────────────────────────────────────────────────────┘")
            lines.append("")

        # Collisions
        items = list(self.state["items"].values())
        overlapPairs = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self.itemsOverlap(items[i], items[j]):
                    overlapPairs.append((items[i]["id"], items[j]["id"]))
        lines.append("  ┌─ COLLISIONS ──────────────────────────────────────────────┐")
        if overlapPairs:
            for a, b in overlapPairs:
                lines.append("  │  💥 %-12s crashes into %-12s" % (a[:12], b[:12]))
        else:
            lines.append("  │  ✅ No collisions — clean layout")
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Energy convergence
        if self.state["energy_history"]:
            hist = self.state["energy_history"]
            lines.append("  ┌─ ANNEALING CONVERGENCE ───────────────────────────────────┐")
            showSteps = min(len(hist), 20)
            for i in range(max(0, len(hist) - showSteps), len(hist)):
                e = hist[i]
                barLen = min(int(e / 10), 30)
                bar = "█" * barLen + "░" * (30 - barLen)
                lines.append("  │  Step %3d: %7.2f  %s" % (i + 1, e, bar))
            lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)
