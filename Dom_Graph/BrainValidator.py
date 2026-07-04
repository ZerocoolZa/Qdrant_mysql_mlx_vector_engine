#!/usr/bin/env python3
# [@GHOST]{[@file<BrainValidator.py>][@domain<graph>][@role<validator>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<validator>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainValidator — Detects broken IDE structures in the GUI AI Brain layout. Validates no panel overlaps, correct docked zones, canvas bounds, constraint target existence, and energy below threshold. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainValidator}
# [@METHOD]{Run,validate,check_overlaps,check_bounds,check_constraints,check_energy,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Detects broken IDE structures: panel overlaps, docked zones, canvas bounds, constraint targets, energy threshold. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded DEFAULT_CANVAS_W/H, ENERGY_THRESHOLD, ZONE_TOLERANCE constants.>][@todos<Move validator constants to Config.py>]}
"""
BrainValidator — Detects broken IDE structures in the GUI AI Brain layout.

WHAT IT CHECKS:
  1. No panels overlap (rectangle intersection test)
  2. All docked panels are in their correct zones (top/left/right/bottom/center)
  3. No panel is out of canvas bounds (x, y, w, h within canvas)
  4. All constraint targets exist (referenced panel IDs are present)
  5. Energy is below a configurable threshold

COMMANDS:
  "validate"          — run all checks, return violations list + valid bool
  "check_overlaps"    — return list of overlapping panel pairs
  "check_bounds"      — return list of out-of-bounds panels
  "check_constraints" — return list of constraint violations
  "check_energy"      — check energy against threshold

USAGE:
  from BrainValidator import BrainValidator

  validator = BrainValidator()
  ok, data, err = validator.Run("validate", {
      "nodes": nodesDict,
      "constraints": constraintsList,
      "canvas_w": 1000,
      "canvas_h": 700,
      "energy": 42.5,
  })
  # data = {"valid": True/False, "violations": [...], "count": N}

  # Or pass a brain directly:
  ok, data, err = validator.Run("validate", {"brain": brainInstance})
"""


# ════════════════════════════════════════════
# VALIDATOR CONSTANTS
# ════════════════════════════════════════════

DEFAULT_CANVAS_W = 1000
DEFAULT_CANVAS_H = 700
ENERGY_THRESHOLD = 500.0
ZONE_TOLERANCE = 50
TOP_ZONE_Y = 10
TOP_ZONE_H = 50
LEFT_ZONE_X = 10
LEFT_ZONE_W = 220
RIGHT_ZONE_MARGIN = 220
RIGHT_ZONE_W = 210
BOTTOM_ZONE_MARGIN = 120
BOTTOM_ZONE_H = 110
CENTER_ZONE_X = 220
CENTER_ZONE_MARGIN = 450
DEFAULT_ENERGY = 0.0


class BrainValidator:
    """
    Detects broken IDE structures in the GUI AI Brain layout.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Validates overlaps, zones, bounds, constraints, energy.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "energy_threshold": p.get("energy_threshold", ENERGY_THRESHOLD),
                "zone_tolerance": p.get("zone_tolerance", ZONE_TOLERANCE),
                "canvas_w": p.get("canvas_w", DEFAULT_CANVAS_W),
                "canvas_h": p.get("canvas_h", DEFAULT_CANVAS_H),
            },
            "last_violations": [],
            "last_valid": True,
            "stats": {
                "validations": 0,
                "overlaps_found": 0,
                "bounds_violations": 0,
                "constraint_violations": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "validate": self.cmd_validate,
            "check_overlaps": self.cmd_check_overlaps,
            "check_bounds": self.cmd_check_bounds,
            "check_constraints": self.cmd_check_constraints,
            "check_energy": self.cmd_check_energy,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command: %s" % command, 0))
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
    # INTERNAL HELPERS
    # ════════════════════════════════════════════

    def normalizeNodes(self, nodes):
        """Convert nodes dict or list to a list of node dicts."""
        if isinstance(nodes, dict):
            return list(nodes.values())
        return list(nodes)

    def rectsOverlap(self, a, b):
        """Check if two rectangles overlap."""
        ax2 = a["x"] + a["w"]
        ay2 = a["y"] + a["h"]
        bx2 = b["x"] + b["w"]
        by2 = b["y"] + b["h"]
        if ax2 <= b["x"] or bx2 <= a["x"]:
            return False
        if ay2 <= b["y"] or by2 <= a["y"]:
            return False
        return True

    def getZoneForEdge(self, edge, canvasW, canvasH):
        """Return the expected zone rect for a given dock edge."""
        if edge == "top":
            return {"x": 0, "y": 0, "w": canvasW, "h": TOP_ZONE_H + 20}
        if edge == "left":
            return {"x": 0, "y": 0, "w": LEFT_ZONE_W + 20, "h": canvasH}
        if edge == "right":
            return {
                "x": canvasW - RIGHT_ZONE_MARGIN - 10,
                "y": 0,
                "w": RIGHT_ZONE_W + 30,
                "h": canvasH,
            }
        if edge == "bottom":
            return {
                "x": 0,
                "y": canvasH - BOTTOM_ZONE_MARGIN - 10,
                "w": canvasW,
                "h": BOTTOM_ZONE_H + 30,
            }
        if edge == "center":
            return {
                "x": CENTER_ZONE_X - 10,
                "y": 40,
                "w": canvasW - CENTER_ZONE_MARGIN + 20,
                "h": canvasH - 180,
            }
        return None

    def rectInZone(self, node, zone, tolerance):
        """Check if a node rect is within a zone (with tolerance)."""
        if not zone:
            return True
        if node["x"] < zone["x"] - tolerance:
            return False
        if node["y"] < zone["y"] - tolerance:
            return False
        if node["x"] + node["w"] > zone["x"] + zone["w"] + tolerance:
            return False
        if node["y"] + node["h"] > zone["y"] + zone["h"] + tolerance:
            return False
        return True

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_validate(self, params):
        """Run all checks and return violations list + valid bool."""
        brain = self.p(params, "brain")
        if brain:
            nodes = brain.state["graph"]["nodes"]
            constraints = brain.state["graph"]["constraints"]
            canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
            canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])
            energy = brain.state["energy"]["total"]
        else:
            nodes = self.p(params, "nodes", {})
            constraints = self.p(params, "constraints", [])
            canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
            canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])
            energy = self.p(params, "energy", DEFAULT_ENERGY)

        if not nodes:
            return (0, None, ("ERR_PARAMS", "nodes required for validation", 0))

        violations = []

        # Check overlaps
        ok, overlapData, err = self.cmd_check_overlaps({"nodes": nodes})
        if not ok:
            return (0, None, err)
        for pair in overlapData["overlaps"]:
            violations.append({"type": "overlap", "a": pair[0], "b": pair[1]})

        # Check bounds
        ok, boundsData, err = self.cmd_check_bounds({
            "nodes": nodes,
            "canvas_w": canvasW,
            "canvas_h": canvasH,
        })
        if not ok:
            return (0, None, err)
        for panelId in boundsData["out_of_bounds"]:
            violations.append({"type": "out_of_bounds", "id": panelId})

        # Check constraints
        ok, constData, err = self.cmd_check_constraints({
            "nodes": nodes,
            "constraints": constraints,
            "canvas_w": canvasW,
            "canvas_h": canvasH,
        })
        if not ok:
            return (0, None, err)
        for v in constData["violations"]:
            violations.append(v)

        # Check energy
        ok, energyData, err = self.cmd_check_energy({"energy": energy})
        if not ok:
            return (0, None, err)
        if not energyData["within_threshold"]:
            violations.append({
                "type": "energy_exceeded",
                "value": energyData["energy"],
                "threshold": energyData["threshold"],
            })

        valid = len(violations) == 0
        self.state["last_violations"] = violations
        self.state["last_valid"] = valid
        self.state["stats"]["validations"] += 1

        return (1, {
            "valid": valid,
            "violations": violations,
            "count": len(violations),
        }, None)

    def cmd_check_overlaps(self, params):
        """Return list of overlapping panel pairs."""
        nodes = self.p(params, "nodes")
        if not nodes:
            return (0, None, ("ERR_PARAMS", "nodes required", 0))

        nodeList = self.normalizeNodes(nodes)
        overlaps = []

        for i in range(len(nodeList)):
            for j in range(i + 1, len(nodeList)):
                a = nodeList[i]
                b = nodeList[j]
                if self.rectsOverlap(a, b):
                    pair = [a.get("id", "node_%d" % i), b.get("id", "node_%d" % j)]
                    overlaps.append(pair)

        if overlaps:
            self.state["stats"]["overlaps_found"] += len(overlaps)

        return (1, {
            "overlaps": overlaps,
            "count": len(overlaps),
        }, None)

    def cmd_check_bounds(self, params):
        """Return list of out-of-bounds panels."""
        nodes = self.p(params, "nodes")
        if not nodes:
            return (0, None, ("ERR_PARAMS", "nodes required", 0))
        canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
        canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])

        nodeList = self.normalizeNodes(nodes)
        outOfBounds = []

        for i, node in enumerate(nodeList):
            panelId = node.get("id", "node_%d" % i)
            x = node.get("x", 0)
            y = node.get("y", 0)
            w = node.get("w", 0)
            h = node.get("h", 0)
            if x < 0 or y < 0:
                outOfBounds.append(panelId)
            elif x + w > canvasW or y + h > canvasH:
                outOfBounds.append(panelId)

        if outOfBounds:
            self.state["stats"]["bounds_violations"] += len(outOfBounds)

        return (1, {
            "out_of_bounds": outOfBounds,
            "count": len(outOfBounds),
            "canvas_w": canvasW,
            "canvas_h": canvasH,
        }, None)

    def cmd_check_constraints(self, params):
        """Return list of constraint violations."""
        nodes = self.p(params, "nodes")
        if not nodes:
            return (0, None, ("ERR_PARAMS", "nodes required", 0))
        constraints = self.p(params, "constraints", [])
        canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
        canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])
        tolerance = self.state["config"]["zone_tolerance"]

        # Build node lookup
        nodeMap = {}
        nodeList = self.normalizeNodes(nodes)
        for i, node in enumerate(nodeList):
            nid = node.get("id", "node_%d" % i)
            nodeMap[nid] = node

        violations = []

        for con in constraints:
            conId = con.get("id", "")
            edge = con.get("edge", "")
            target = con.get("target", None)

            # Check constraint target exists
            if conId not in nodeMap:
                violations.append({
                    "type": "missing_constraint_target",
                    "id": conId,
                    "detail": "constraint references non-existent panel",
                })
                continue

            # Check optional target field
            if target and target not in nodeMap:
                violations.append({
                    "type": "missing_target",
                    "id": conId,
                    "target": target,
                    "detail": "constraint target does not exist",
                })
                continue

            # Check docked panel is in correct zone
            node = nodeMap[conId]
            zone = self.getZoneForEdge(edge, canvasW, canvasH)
            if zone:
                if not self.rectInZone(node, zone, tolerance):
                    violations.append({
                        "type": "wrong_zone",
                        "id": conId,
                        "edge": edge,
                        "detail": "panel not in correct dock zone",
                    })

        if violations:
            self.state["stats"]["constraint_violations"] += len(violations)

        return (1, {
            "violations": violations,
            "count": len(violations),
        }, None)

    def cmd_check_energy(self, params):
        """Check if energy is below threshold."""
        energy = self.p(params, "energy", DEFAULT_ENERGY)
        threshold = self.state["config"]["energy_threshold"]
        withinThreshold = energy <= threshold

        return (1, {
            "energy": energy,
            "threshold": threshold,
            "within_threshold": withinThreshold,
        }, None)
