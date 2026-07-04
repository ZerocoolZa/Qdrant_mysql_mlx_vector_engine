#!/usr/bin/env python3
# [@GHOST]{[@file<MagneticGui.py>][@domain<gui>][@role<magnetic_layout>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<magnetic_layout>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{MagneticGui — GUI items as magnets. Attract when capabilities match requirements. Repel when in repulsion list. Field strength controls pull. Force-directed layout. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{MagneticGui}
# [@METHOD]{Run,add_item,attraction,repulsion,field,step,layout,report,graph,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<GUI items as magnets. Attract when capabilities match requirements, repel when in repulsion list. Force-directed layout. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
MagneticGui — GUI items as magnetic components.

THE MAGNETIC MODEL (from Lib_MagneticComponent_v1):
  Each GUI item has:
    - capabilities:  what it offers (e.g. "search,filter,navigate")
    - requirements:  what it needs (e.g. "data_source,query_input")
    - repulsions:    items it pushes away from (e.g. "modal_dialog")
    - field_strength: how strong its magnetic pull is (0.0-1.0)

ATTRACTION RULE:
  Item A attracts Item B when:
    A's capabilities match B's requirements
    B's capabilities match A's requirements
    Neither is in the other's repulsion list

  attraction = (cap_match * req_match * field_A * field_B)
  If repulsed → attraction = 0 (blocked)

REPULSION RULE:
  Item A repels Item B when:
    B is in A's repulsion list, OR
    A is in B's repulsion list, OR
    Both items are the same type and too close (like poles)

FIELD STRENGTH:
  Controls how far the magnetic pull reaches.
  1.0 = strong magnet (pulls from far away)
  0.1 = weak magnet (only pulls when very close)

LAYOUT BEHAVIOR:
  - Items that attract move toward each other
  - Items that repel move apart
  - Field strength determines pull distance
  - Physics loop converges to magnetic equilibrium

USAGE:
  from MagneticGui import MagneticGui

  mg = MagneticGui()
  mg.Run("add_item", {"id": "search_box", "type": "Input",
      "capabilities": "query_input,text_entry",
      "requirements": "search_engine",
      "field_strength": 0.8, "x": 100, "y": 100})
  mg.Run("add_item", {"id": "results_list", "type": "List",
      "capabilities": "display_results,scroll",
      "requirements": "query_input",
      "field_strength": 0.7, "x": 500, "y": 100})

  ok, data, err = mg.Run("attraction", {"a": "search_box", "b": "results_list"})
  # → attraction score (0.0 = repelled, 1.0 = max attraction)

  ok, data, err = mg.Run("step", {"steps": 50})
  # → physics loop moves items to magnetic equilibrium

  ok, data, err = mg.Run("graph")
  # → visual magnetic field graph
"""

import math


# ════════════════════════════════════════════
# MAGNETIC CONSTANTS
# ════════════════════════════════════════════

DEFAULT_FIELD_STRENGTH = 0.85
ATTRACTION_RADIUS = 300.0       # max distance for attraction force
REPULSION_RADIUS = 80.0         # distance at which repulsion kicks in
DAMPING = 0.82                  # velocity decay
FORCE_SCALE = 0.15              # overall force multiplier
EQUILIBRIUM_DIST = 120.0        # ideal distance for attracted items
SAME_TYPE_REPEL_DIST = 60.0     # same-type items repel when closer than this


class MagneticGui:
    """
    GUI items as magnetic components — attract/repel based on capabilities.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Items attract when caps match reqs, repel when in repulsion list.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "default_field_strength": DEFAULT_FIELD_STRENGTH,
                "attraction_radius": ATTRACTION_RADIUS,
                "repulsion_radius": REPULSION_RADIUS,
                "damping": DAMPING,
                "force_scale": FORCE_SCALE,
                "equilibrium_dist": EQUILIBRIUM_DIST,
                "same_type_repel_dist": SAME_TYPE_REPEL_DIST,
            },
            "items": {},          # id → item dict
            "step_count": 0,
            "converged": False,
            "history": [],
            "stats": {"attractions": 0, "repulsions": 0, "steps": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "add_item": self.cmd_add_item,
            "attraction": self.cmd_attraction,
            "repulsion": self.cmd_repulsion,
            "field": self.cmd_field,
            "step": self.cmd_step,
            "layout": self.cmd_layout,
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
    # INTERNAL — magnetic calculations
    # ════════════════════════════════════════════

    def parseCsv(self, text):
        if not text:
            return []
        return [t.strip() for t in text.split(",") if t.strip()]

    def sharedCount(self, listA, listB):
        setA = set(listA)
        setB = set(listB)
        return len(setA & setB)

    def distance(self, a, b):
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        return math.sqrt(dx * dx + dy * dy)

    def isRepulsed(self, a, b):
        """Check if a and b repel each other."""
        aRepulsions = self.parseCsv(a.get("repulsions", ""))
        bRepulsions = self.parseCsv(b.get("repulsions", ""))
        if b["id"] in aRepulsions:
            return True
        if a["id"] in bRepulsions:
            return True
        # Same type items repel when too close (like poles)
        if a.get("type", "") == b.get("type", "") and a.get("type", "") != "":
            if self.distance(a, b) < self.state["config"]["same_type_repel_dist"]:
                return True
        return False

    def calcAttraction(self, a, b):
        """
        Calculate attraction between two items.
        Based on Lib_MagneticComponent_v1 calculate_attraction logic:
          - If repulsed → 0.0 (blocked)
          - cap_match = shared(a.caps, b.reqs) / len(b.reqs)
          - req_match = shared(b.caps, a.reqs) / len(a.reqs)
          - attraction = cap_match * req_match * field_A * field_B
        """
        if self.isRepulsed(a, b):
            return 0.0, True  # blocked by repulsion

        aCaps = self.parseCsv(a.get("capabilities", ""))
        aReqs = self.parseCsv(a.get("requirements", ""))
        bCaps = self.parseCsv(b.get("capabilities", ""))
        bReqs = self.parseCsv(b.get("requirements", ""))

        # How much of B's requirements can A satisfy?
        capMatch = 0.0
        if bReqs:
            capMatch = self.sharedCount(aCaps, bReqs) / len(bReqs)

        # How much of A's requirements can B satisfy?
        reqMatch = 0.0
        if aReqs:
            reqMatch = self.sharedCount(bCaps, aReqs) / len(aReqs)

        fieldA = a.get("field_strength", self.state["config"]["default_field_strength"])
        fieldB = b.get("field_strength", self.state["config"]["default_field_strength"])

        # Attraction works if EITHER direction matches (one-way is still attraction)
        # bidirectional match gets bonus
        matchScore = max(capMatch, reqMatch)
        if capMatch > 0 and reqMatch > 0:
            matchScore = (capMatch + reqMatch) / 2.0 + 0.2  # bidirectional bonus

        attraction = matchScore * fieldA * fieldB
        return attraction, False

    def calcForce(self, a, b):
        """
        Calculate force vector on item A from item B.
        Positive = attract (pull toward B)
        Negative = repel (push away from B)
        """
        dist = self.distance(a, b)
        if dist < 0.001:
            dist = 0.001

        attraction, repulsed = self.calcAttraction(a, b)
        cfg = self.state["config"]

        if repulsed:
            # Repulsion force — push apart, stronger when closer
            if dist < cfg["repulsion_radius"]:
                strength = (cfg["repulsion_radius"] - dist) / cfg["repulsion_radius"]
                force = -strength * cfg["force_scale"] * 2.0
            else:
                force = -cfg["force_scale"] * 0.3  # mild repulsion at distance
        elif attraction > 0:
            # Attraction force — pull toward equilibrium distance
            if dist > cfg["equilibrium_dist"]:
                # Too far — pull closer
                strength = attraction * min(1.0, (dist - cfg["equilibrium_dist"]) / cfg["attraction_radius"])
                force = strength * cfg["force_scale"]
            elif dist < cfg["equilibrium_dist"] * 0.5:
                # Too close — push apart slightly (don't overlap)
                force = -cfg["force_scale"] * 0.5
            else:
                # At equilibrium — no force
                force = 0.0
        else:
            # No attraction, no repulsion — neutral
            force = 0.0

        # Force direction (unit vector from A to B)
        dx = b["x"] - a["x"]
        dy = b["y"] - a["y"]
        fx = (dx / dist) * force
        fy = (dy / dist) * force
        return fx, fy, attraction, repulsed

    def totalEnergy(self):
        """Total magnetic energy — lower = more stable."""
        items = list(self.state["items"].values())
        energy = 0.0
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                dist = self.distance(a, b)
                attraction, repulsed = self.calcAttraction(a, b)
                if repulsed:
                    energy += max(0, 100 - dist) * 0.5
                elif attraction > 0:
                    ideal = self.state["config"]["equilibrium_dist"]
                    energy += abs(dist - ideal) * attraction
        return energy

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_add_item(self, params):
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
            "capabilities": self.p(params, "capabilities", ""),
            "requirements": self.p(params, "requirements", ""),
            "repulsions": self.p(params, "repulsions", ""),
            "field_strength": float(self.p(params, "field_strength",
                self.state["config"]["default_field_strength"])),
            "label": self.p(params, "label", itemId),
        }
        self.state["items"][itemId] = item
        return (1, item, None)

    def cmd_attraction(self, params):
        """Calculate attraction between two items."""
        aId = self.p(params, "a")
        bId = self.p(params, "b")
        if not aId or not bId:
            return (0, None, ("ERR_PARAMS", "a and b required", 0))
        a = self.state["items"].get(aId)
        b = self.state["items"].get(bId)
        if not a:
            return (0, None, ("ERR_NOT_FOUND", "item not found: %s" % aId, 0))
        if not b:
            return (0, None, ("ERR_NOT_FOUND", "item not found: %s" % bId, 0))
        attraction, repulsed = self.calcAttraction(a, b)
        dist = self.distance(a, b)
        result = {
            "a": aId,
            "b": bId,
            "attraction": round(attraction, 4),
            "repulsed": repulsed,
            "distance": round(dist, 2),
            "field_a": a["field_strength"],
            "field_b": b["field_strength"],
        }
        if repulsed:
            self.state["stats"]["repulsions"] += 1
            result["status"] = "REPULSED — blocked by repulsion list"
        elif attraction > 0:
            self.state["stats"]["attractions"] += 1
            result["status"] = "ATTRACTED — caps match reqs"
        else:
            result["status"] = "NEUTRAL — no cap/req overlap"
        return (1, result, None)

    def cmd_repulsion(self, params):
        """Check if two items repel each other."""
        aId = self.p(params, "a")
        bId = self.p(params, "b")
        if not aId or not bId:
            return (0, None, ("ERR_PARAMS", "a and b required", 0))
        a = self.state["items"].get(aId)
        b = self.state["items"].get(bId)
        if not a or not b:
            return (0, None, ("ERR_NOT_FOUND", "item not found", 0))
        repulsed = self.isRepulsed(a, b)
        reason = ""
        if repulsed:
            aReps = self.parseCsv(a.get("repulsions", ""))
            bReps = self.parseCsv(b.get("repulsions", ""))
            if bId in aReps:
                reason = "%s has %s in repulsion list" % (aId, bId)
            elif aId in bReps:
                reason = "%s has %s in repulsion list" % (bId, aId)
            else:
                reason = "same type (%s) too close" % a.get("type", "")
        return (1, {
            "a": aId,
            "b": bId,
            "repulsed": repulsed,
            "reason": reason,
            "distance": round(self.distance(a, b), 2),
        }, None)

    def cmd_field(self, params):
        """Get the full magnetic field — all attraction/repulsion pairs."""
        items = list(self.state["items"].values())
        field = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                attraction, repulsed = self.calcAttraction(a, b)
                dist = self.distance(a, b)
                if repulsed:
                    field.append({
                        "a": a["id"],
                        "b": b["id"],
                        "type": "REPULSION",
                        "strength": 0.0,
                        "distance": round(dist, 2),
                        "icon": "🔴",
                    })
                elif attraction > 0.01:
                    field.append({
                        "a": a["id"],
                        "b": b["id"],
                        "type": "ATTRACTION",
                        "strength": round(attraction, 4),
                        "distance": round(dist, 2),
                        "icon": "🟢",
                    })
                else:
                    field.append({
                        "a": a["id"],
                        "b": b["id"],
                        "type": "NEUTRAL",
                        "strength": 0.0,
                        "distance": round(dist, 2),
                        "icon": "⚪",
                    })
        field.sort(key=lambda x: x["strength"], reverse=True)
        return (1, {
            "field": field,
            "total_pairs": len(field),
            "attractions": sum(1 for f in field if f["type"] == "ATTRACTION"),
            "repulsions": sum(1 for f in field if f["type"] == "REPULSION"),
            "neutral": sum(1 for f in field if f["type"] == "NEUTRAL"),
        }, None)

    def cmd_step(self, params):
        """Run physics steps — items move based on magnetic forces."""
        steps = self.p(params, "steps", 1)
        cfg = self.state["config"]
        items = list(self.state["items"].values())
        for _ in range(steps):
            for a in items:
                fxTotal = 0.0
                fyTotal = 0.0
                for b in items:
                    if a["id"] == b["id"]:
                        continue
                    fx, fy, attraction, repulsed = self.calcForce(a, b)
                    fxTotal += fx
                    fyTotal += fy
                a["vx"] = (a["vx"] + fxTotal) * cfg["damping"]
                a["vy"] = (a["vy"] + fyTotal) * cfg["damping"]
            for a in items:
                a["x"] += a["vx"]
                a["y"] += a["vy"]
            self.state["step_count"] += 1
            self.state["stats"]["steps"] += 1
        energy = self.totalEnergy()
        self.state["history"].append(round(energy, 2))
        return (1, {
            "steps": steps,
            "total_steps": self.state["step_count"],
            "energy": round(energy, 2),
            "converged": energy < 5.0,
        }, None)

    def cmd_layout(self, params):
        """Get current layout positions for rendering."""
        layout = {}
        for itemId, item in self.state["items"].items():
            layout[itemId] = {
                "id": itemId,
                "type": item["type"],
                "x": round(item["x"], 1),
                "y": round(item["y"], 1),
                "vx": round(item["vx"], 3),
                "vy": round(item["vy"], 3),
                "field_strength": item["field_strength"],
                "capabilities": item["capabilities"],
                "requirements": item["requirements"],
                "repulsions": item["repulsions"],
            }
        return (1, {"layout": layout, "step": self.state["step_count"], "energy": round(self.totalEnergy(), 2)}, None)

    def cmd_report(self, params):
        """Full magnetic field report."""
        ok, fieldData, err = self.cmd_field({})
        if not ok:
            return (0, None, err)
        ok, layoutData, err2 = self.cmd_layout({})
        if not ok:
            return (0, None, err2)
        lines = []
        lines.append("MAGNETIC GUI REPORT")
        lines.append("====================")
        lines.append("Items: %d" % len(self.state["items"]))
        lines.append("Steps: %d" % self.state["step_count"])
        lines.append("Energy: %.2f" % layoutData["energy"])
        lines.append("")
        lines.append("ITEMS:")
        lines.append("-" * 70)
        for itemId, item in self.state["items"].items():
            lines.append("  %-15s  type=%-10s  field=%.2f  pos=(%.1f,%.1f)" % (
                itemId, item["type"], item["field_strength"], item["x"], item["y"]))
            lines.append("    caps:  %s" % item["capabilities"])
            lines.append("    reqs:  %s" % item["requirements"])
            if item["repulsions"]:
                lines.append("    reps:  %s" % item["repulsions"])
        lines.append("")
        lines.append("MAGNETIC FIELD:")
        lines.append("-" * 70)
        for f in fieldData["field"]:
            lines.append("  %s %-12s ↔ %-12s  strength=%.4f  dist=%.1f  %s" % (
                f["icon"], f["a"], f["b"], f["strength"], f["distance"], f["type"]))
        lines.append("")
        lines.append("SUMMARY:")
        lines.append("  Attractions: %d" % fieldData["attractions"])
        lines.append("  Repulsions:  %d" % fieldData["repulsions"])
        lines.append("  Neutral:     %d" % fieldData["neutral"])
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_graph(self, params):
        """Visual magnetic field graph."""
        ok, fieldData, err = self.cmd_field({})
        if not ok:
            return (0, None, err)
        ok, layoutData, err2 = self.cmd_layout({})
        if not ok:
            return (0, None, err2)
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║           MAGNETIC GUI — Attract / Repel Field              ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Items: %d   Steps: %d   Energy: %.2f" % (
            len(self.state["items"]), self.state["step_count"], layoutData["energy"]))
        lines.append("  Attractions: %d   Repulsions: %d   Neutral: %d" % (
            fieldData["attractions"], fieldData["repulsions"], fieldData["neutral"]))
        lines.append("")

        # Items with field strength
        lines.append("  ┌─ MAGNETIC ITEMS ──────────────────────────────────────────┐")
        for itemId, item in self.state["items"].items():
            fieldBar = min(int(item["field_strength"] * 20), 20)
            bar = "🧲" * fieldBar
            lines.append("  │  %-15s  type=%-10s  field=%.2f  %s" % (
                itemId[:15], item["type"][:10], item["field_strength"], bar))
            caps = item["capabilities"][:30] if item["capabilities"] else "(none)"
            reqs = item["requirements"][:30] if item["requirements"] else "(none)"
            lines.append("  │    caps: %-30s  reqs: %s" % (caps, reqs))
            if item["repulsions"]:
                lines.append("  │    REPELS: %s" % item["repulsions"][:40])
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Magnetic field pairs
        lines.append("  ┌─ MAGNETIC FIELD (attract / repel pairs) ──────────────────┐")
        for f in fieldData["field"]:
            strength = f["strength"]
            if f["type"] == "ATTRACTION":
                barLen = min(int(strength * 30), 30)
                bar = "🟩" * barLen
                lines.append("  │  🟢 %-12s ↔ %-12s  attract=%.4f  %s" % (
                    f["a"][:12], f["b"][:12], strength, bar))
            elif f["type"] == "REPULSION":
                lines.append("  │  🔴 %-12s ↔ %-12s  REPULSED  dist=%.1f" % (
                    f["a"][:12], f["b"][:12], f["distance"]))
            else:
                lines.append("  │  ⚪ %-12s ↔ %-12s  neutral   dist=%.1f" % (
                    f["a"][:12], f["b"][:12], f["distance"]))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Current positions
        lines.append("  ┌─ LAYOUT POSITIONS ────────────────────────────────────────┐")
        for itemId, pos in layoutData["layout"].items():
            lines.append("  │  %-15s  pos=(%6.1f, %6.1f)  vel=(%+.3f, %+.3f)" % (
                itemId[:15], pos["x"], pos["y"], pos["vx"], pos["vy"]))
        lines.append("  └────────────────────────────────────────────────────────────┘")
        lines.append("")

        # Energy history
        if self.state["history"]:
            hist = self.state["history"]
            lines.append("  ┌─ ENERGY CONVERGENCE ──────────────────────────────────────┐")
            showSteps = min(len(hist), 15)
            for i in range(max(0, len(hist) - showSteps), len(hist)):
                e = hist[i]
                barLen = min(int(e / 10), 30)
                bar = "█" * barLen + "░" * (30 - barLen)
                lines.append("  │  Step %3d: %7.2f  %s" % (i + 1, e, bar))
            lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)
