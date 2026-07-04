#!/usr/bin/env python3
# [@GHOST]{[@file<BrainDockSystem.py>][@domain<graph>][@role<dock_system>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<dock_system>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainDockSystem — VSCode-style dock zone system for the GUI AI Brain. Defines top, left, right, bottom, center zones and snaps panels to them. Overrides physics when panels are close to a dock zone. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainDockSystem}
# [@METHOD]{Run,add_zone,add_panel,snap,validate,layout,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<VSCode-style dock zone system for GUI AI Brain. Defines zones and snaps panels. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded zone constants (ZONE_TOP_HEIGHT etc) in file.>][@todos<Move hardcoded zone constants to Config.py>]}
"""
BrainDockSystem — VSCode-style dock zone system for the GUI AI Brain.

WHAT IT DOES:
  - Defines VSCode-style zones (top, left, right, bottom, center)
  - Snaps panels to zones when they are close enough
  - Overrides physics when panels are within SNAP_DISTANCE of a dock zone
  - Validates that panels are inside their preferred zone bounds
  - Returns the full zone layout dict

THE DOCK ZONES:
  top:    full width strip at the top (height ZONE_TOP_HEIGHT)
  left:   vertical strip on the left (width ZONE_LEFT_WIDTH)
  right:  vertical strip on the right (width ZONE_RIGHT_WIDTH)
  bottom: full width strip at the bottom (height ZONE_BOTTOM_HEIGHT)
  center: the remaining area in the middle

SNAP LOGIC:
  Given a panel id and position, if the panel is within SNAP_DISTANCE
  of its preferred zone, return the snapped position. Otherwise return
  the original position. This is the hard structural constraint that
  overrides physics.

VALIDATE LOGIC:
  Check each registered panel — is it inside its preferred zone bounds?
  Return a list of violations for any panel that is out of bounds.

USAGE:
  from BrainDockSystem import BrainDockSystem

  dock = BrainDockSystem()
  dock.Run("add_zone", {"edge": "left", "x": 0, "y": 0, "w": 200, "h": 700, "strength": 1.0})
  dock.Run("add_panel", {"id": "explorer", "type": "tree", "preferred_zone": "left"})
  ok, data, err = dock.Run("snap", {"id": "explorer", "x": 12, "y": 50})
  ok, data, err = dock.Run("validate", {})
  ok, data, err = dock.Run("layout", {})
"""

import math


# ════════════════════════════════════════════
# DOCK ZONE CONSTANTS
# ════════════════════════════════════════════

ZONE_TOP_HEIGHT = 35
ZONE_LEFT_WIDTH = 200
ZONE_RIGHT_WIDTH = 220
ZONE_BOTTOM_HEIGHT = 120
ZONE_MARGIN = 5
SNAP_DISTANCE = 30
CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700

# Default zone edges
EDGE_TOP = "top"
EDGE_LEFT = "left"
EDGE_RIGHT = "right"
EDGE_BOTTOM = "bottom"
EDGE_CENTER = "center"


class BrainDockSystem:
    """
    VSCode-style dock zone system for the GUI AI Brain.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Defines zones, snaps panels, validates bounds, returns layout.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "canvas_w": CANVAS_WIDTH,
                "canvas_h": CANVAS_HEIGHT,
                "snap_distance": SNAP_DISTANCE,
                "margin": ZONE_MARGIN,
            },
            "zones": {},
            "panels": {},
            "violations": [],
            "stats": {
                "snaps": 0,
                "validations": 0,
                "zones_added": 0,
                "panels_added": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "add_zone": self.cmd_add_zone,
            "add_panel": self.cmd_add_panel,
            "snap": self.cmd_snap,
            "validate": self.cmd_validate,
            "layout": self.cmd_layout,
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
    # HELPERS
    # ════════════════════════════════════════════

    def defaultZones(self):
        """Build the default VSCode-style zone layout from constants."""
        cw = self.state["config"]["canvas_w"]
        ch = self.state["config"]["canvas_h"]
        margin = self.state["config"]["margin"]
        topH = ZONE_TOP_HEIGHT
        leftW = ZONE_LEFT_WIDTH
        rightW = ZONE_RIGHT_WIDTH
        bottomH = ZONE_BOTTOM_HEIGHT
        zones = {
            EDGE_TOP: {
                "edge": EDGE_TOP,
                "x": 0,
                "y": 0,
                "w": cw,
                "h": topH,
                "strength": 1.0,
            },
            EDGE_LEFT: {
                "edge": EDGE_LEFT,
                "x": 0,
                "y": topH + margin,
                "w": leftW,
                "h": ch - topH - bottomH - margin * 2,
                "strength": 1.0,
            },
            EDGE_RIGHT: {
                "edge": EDGE_RIGHT,
                "x": cw - rightW,
                "y": topH + margin,
                "w": rightW,
                "h": ch - topH - bottomH - margin * 2,
                "strength": 1.0,
            },
            EDGE_BOTTOM: {
                "edge": EDGE_BOTTOM,
                "x": 0,
                "y": ch - bottomH,
                "w": cw,
                "h": bottomH,
                "strength": 1.0,
            },
            EDGE_CENTER: {
                "edge": EDGE_CENTER,
                "x": leftW + margin,
                "y": topH + margin,
                "w": cw - leftW - rightW - margin * 2,
                "h": ch - topH - bottomH - margin * 2,
                "strength": 0.5,
            },
        }
        return zones

    def pointInZone(self, x, y, zone):
        """Check if a point (x, y) is inside a zone bounds."""
        if not zone:
            return False
        zx = zone["x"]
        zy = zone["y"]
        zw = zone["w"]
        zh = zone["h"]
        if x < zx or x > zx + zw:
            return False
        if y < zy or y > zy + zh:
            return False
        return True

    def distanceToZone(self, x, y, zone):
        """Compute the minimum distance from a point to a zone rectangle."""
        if not zone:
            return 999999.0
        zx = zone["x"]
        zy = zone["y"]
        zw = zone["w"]
        zh = zone["h"]
        dx = 0.0
        dy = 0.0
        if x < zx:
            dx = zx - x
        elif x > zx + zw:
            dx = x - (zx + zw)
        if y < zy:
            dy = zy - y
        elif y > zy + zh:
            dy = y - (zy + zh)
        return math.sqrt(dx * dx + dy * dy)

    def snapPointToZone(self, x, y, zone):
        """Snap a point to the nearest edge of a zone."""
        if not zone:
            return x, y
        zx = zone["x"]
        zy = zone["y"]
        zw = zone["w"]
        zh = zone["h"]
        snappedX = x
        snappedY = y
        if x < zx:
            snappedX = zx
        elif x > zx + zw:
            snappedX = zx + zw
        if y < zy:
            snappedY = zy
        elif y > zy + zh:
            snappedY = zy + zh
        return snappedX, snappedY

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_add_zone(self, params):
        """Define a dock zone with edge, position, size, and strength."""
        edge = self.p(params, "edge")
        if not edge:
            return (0, None, ("ERR_PARAMS", "edge required", 0))
        x = float(self.p(params, "x", 0))
        y = float(self.p(params, "y", 0))
        w = float(self.p(params, "w", 0))
        h = float(self.p(params, "h", 0))
        strength = float(self.p(params, "strength", 1.0))
        if w <= 0 or h <= 0:
            return (0, None, ("ERR_PARAMS", "w and h must be positive", 0))
        zone = {
            "edge": edge,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "strength": strength,
        }
        self.state["zones"][edge] = zone
        self.state["stats"]["zones_added"] += 1
        return (1, dict(zone), None)

    def cmd_add_panel(self, params):
        """Register a panel with an id, type, and preferred zone."""
        panelId = self.p(params, "id")
        if not panelId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        panelType = self.p(params, "type", "panel")
        preferredZone = self.p(params, "preferred_zone", EDGE_CENTER)
        panel = {
            "id": panelId,
            "type": panelType,
            "preferred_zone": preferredZone,
            "x": 0.0,
            "y": 0.0,
            "snapped": False,
        }
        self.state["panels"][panelId] = panel
        self.state["stats"]["panels_added"] += 1
        return (1, dict(panel), None)

    def cmd_snap(self, params):
        """Check if a panel position should snap to its preferred zone."""
        panelId = self.p(params, "id")
        if not panelId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        panel = self.state["panels"].get(panelId)
        if not panel:
            return (0, None, ("ERR_PANEL", "panel not found", 0))
        x = float(self.p(params, "x", 0))
        y = float(self.p(params, "y", 0))
        preferredZone = panel["preferred_zone"]
        zones = self.state["zones"]
        if not zones:
            zones = self.defaultZones()
        zone = zones.get(preferredZone)
        if not zone:
            panel["x"] = x
            panel["y"] = y
            panel["snapped"] = False
            return (1, {
                "id": panelId,
                "x": x,
                "y": y,
                "snapped": False,
                "reason": "no zone for preferred",
            }, None)
        snapDist = self.state["config"]["snap_distance"]
        dist = self.distanceToZone(x, y, zone)
        if dist <= snapDist:
            snappedX, snappedY = self.snapPointToZone(x, y, zone)
            panel["x"] = snappedX
            panel["y"] = snappedY
            panel["snapped"] = True
            self.state["stats"]["snaps"] += 1
            return (1, {
                "id": panelId,
                "x": snappedX,
                "y": snappedY,
                "snapped": True,
                "distance": round(dist, 2),
            }, None)
        panel["x"] = x
        panel["y"] = y
        panel["snapped"] = False
        return (1, {
            "id": panelId,
            "x": x,
            "y": y,
            "snapped": False,
            "distance": round(dist, 2),
        }, None)

    def cmd_validate(self, params):
        """Check all panels are in valid zones, return violations."""
        zones = self.state["zones"]
        if not zones:
            zones = self.defaultZones()
        panels = self.state["panels"]
        violations = []
        for panelId, panel in panels.items():
            preferredZone = panel["preferred_zone"]
            zone = zones.get(preferredZone)
            if not zone:
                violations.append({
                    "id": panelId,
                    "reason": "no zone for preferred",
                    "preferred_zone": preferredZone,
                })
                continue
            ok = self.pointInZone(panel["x"], panel["y"], zone)
            if not ok:
                violations.append({
                    "id": panelId,
                    "reason": "out of bounds",
                    "preferred_zone": preferredZone,
                    "x": panel["x"],
                    "y": panel["y"],
                    "zone_x": zone["x"],
                    "zone_y": zone["y"],
                    "zone_w": zone["w"],
                    "zone_h": zone["h"],
                })
        self.state["violations"] = violations
        self.state["stats"]["validations"] += 1
        return (1, {
            "violations": violations,
            "count": len(violations),
            "valid": len(violations) == 0,
        }, None)

    def cmd_layout(self, params):
        """Return the full zone layout dict."""
        zones = self.state["zones"]
        if not zones:
            zones = self.defaultZones()
            self.state["zones"] = zones
        layout = {
            "zones": {edge: dict(z) for edge, z in zones.items()},
            "panels": {pid: dict(p) for pid, p in self.state["panels"].items()},
            "canvas_w": self.state["config"]["canvas_w"],
            "canvas_h": self.state["config"]["canvas_h"],
            "snap_distance": self.state["config"]["snap_distance"],
        }
        return (1, layout, None)
