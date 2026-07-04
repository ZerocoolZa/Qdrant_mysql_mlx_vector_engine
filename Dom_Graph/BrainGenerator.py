#!/usr/bin/env python3
# [@GHOST]{[@file<BrainGenerator.py>][@domain<graph>][@role<generator>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<generator>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainGenerator — Auto-generates a full VSCode-style IDE layout from an empty or minimal JSON spec. Takes a list of desired panel types and produces a complete UI spec with positions, constraints, and edges. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainGenerator}
# [@METHOD]{Run,generate,from_template,spec,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Auto-generates VSCode-style IDE layout from panel list. Produces positions, constraints, edges. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded zone placement coordinates and template definitions.>][@todos<Move hardcoded placement coordinates to Config.py>]}
"""
BrainGenerator — Auto-generates a full VSCode-style IDE layout.

WHAT IT DOES:
  Takes a list of desired panel types (e.g. Toolbar, Sidebar, Editor)
  and produces a complete UI spec with:
    - Node positions (x, y, w, h) placed in VSCode zones
    - Docking constraints (edge + strength per panel)
    - Force edges (repulsion between all pairs, attraction between related)

ZONE PLACEMENT RULES:
  toolbar   → top     (y=10, x=10, w=canvas_w-20, h=30)
  sidebar   → left    (x=10, y=50, w=200, h=canvas_h-180)
  editor    → center  (x=220, y=50, w=canvas_w-450, h=canvas_h-180)
  terminal  → bottom  (x=220, y=canvas_h-120, w=canvas_w-450, h=100)
  inspector → right   (x=canvas_w-220, y=50, w=210, h=canvas_h-180)
  statusbar → bottom  (x=10, y=canvas_h-15, w=canvas_w-20, h=10)

COMMANDS:
  "generate"      — params {panels, canvas_w, canvas_h} → full spec
  "from_template" — params {template_name} → spec from named template
  "spec"          — params {} → return last generated spec

TEMPLATES:
  "vscode_default" — toolbar, sidebar, editor, terminal, inspector, statusbar
  "minimal"        — toolbar, editor, statusbar
  "debugger"       — toolbar, editor, terminal, inspector, statusbar

USAGE:
  from BrainGenerator import BrainGenerator

  gen = BrainGenerator()
  ok, data, err = gen.Run("generate", {
      "panels": [
          {"id": "toolbar", "type": "Toolbar"},
          {"id": "editor", "type": "Editor"},
      ],
      "canvas_w": 1000,
      "canvas_h": 700,
  })
  # data = {"nodes": {...}, "constraints": [...], "edges": [...], "canvas": {...}}

  ok, data, err = gen.Run("from_template", {"template_name": "vscode_default"})
  ok, data, err = gen.Run("spec", {})
"""


# ════════════════════════════════════════════
# GENERATOR CONSTANTS
# ════════════════════════════════════════════

DEFAULT_CANVAS_W = 1000
DEFAULT_CANVAS_H = 700
DEFAULT_MARGIN = 10
TOP_Y = 10
TOP_H = 30
TOP_X = 10
LEFT_X = 10
LEFT_Y = 50
LEFT_W = 200
CENTER_X = 220
CENTER_Y = 50
CENTER_W_OFFSET = 450
CENTER_H_OFFSET = 180
RIGHT_X_OFFSET = 220
RIGHT_W = 210
RIGHT_Y = 50
BOTTOM_Y_OFFSET = 120
BOTTOM_H = 100
BOTTOM_X = 220
STATUSBAR_Y_OFFSET = 15
STATUSBAR_H = 10
STATUSBAR_X = 10
FALLBACK_X = 50
FALLBACK_Y = 50
FALLBACK_W = 200
FALLBACK_H = 200
STRENGTH_DOCK_TOP = 0.95
STRENGTH_DOCK_LEFT = 0.85
STRENGTH_DOCK_RIGHT = 0.85
STRENGTH_DOCK_BOTTOM = 0.80
STRENGTH_DOCK_CENTER = 0.50
STRENGTH_REPEL = 0.60
STRENGTH_ATTRACT = 0.40
INITIAL_VX = 0.0
INITIAL_VY = 0.0

# Panel type → zone name
TYPE_TO_ZONE = {
    "Toolbar": "toolbar",
    "Sidebar": "sidebar",
    "Editor": "editor",
    "Terminal": "terminal",
    "Inspector": "inspector",
    "StatusBar": "statusbar",
    "MenuBar": "toolbar",
    "Panel": "terminal",
}

# Zone name → dock edge
ZONE_TO_EDGE = {
    "toolbar": "top",
    "sidebar": "left",
    "editor": "center",
    "terminal": "bottom",
    "inspector": "right",
    "statusbar": "bottom",
}

# Named templates — each is a list of panel specs
TEMPLATES = {
    "vscode_default": [
        {"id": "toolbar", "type": "Toolbar"},
        {"id": "sidebar", "type": "Sidebar"},
        {"id": "editor", "type": "Editor"},
        {"id": "terminal", "type": "Terminal"},
        {"id": "inspector", "type": "Inspector"},
        {"id": "statusbar", "type": "StatusBar"},
    ],
    "minimal": [
        {"id": "toolbar", "type": "Toolbar"},
        {"id": "editor", "type": "Editor"},
        {"id": "statusbar", "type": "StatusBar"},
    ],
    "debugger": [
        {"id": "toolbar", "type": "Toolbar"},
        {"id": "editor", "type": "Editor"},
        {"id": "terminal", "type": "Terminal"},
        {"id": "inspector", "type": "Inspector"},
        {"id": "statusbar", "type": "StatusBar"},
    ],
}

# Panel ID pairs that attract each other
ATTRACT_PAIRS = [
    ("editor", "terminal"),
    ("sidebar", "editor"),
]


class BrainGenerator:
    """
    Auto-generates a full VSCode-style IDE layout from panel specs.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Produces nodes with positions, constraints, and force edges.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "canvas_w": p.get("canvas_w", DEFAULT_CANVAS_W),
                "canvas_h": p.get("canvas_h", DEFAULT_CANVAS_H),
            },
            "last_spec": None,
            "stats": {
                "specs_generated": 0,
                "templates_used": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "generate": self.cmd_generate,
            "from_template": self.cmd_from_template,
            "spec": self.cmd_spec,
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

    def computePlacement(self, zone, canvasW, canvasH):
        """Compute x, y, w, h for a panel based on its zone."""
        if zone == "toolbar":
            return {"x": TOP_X, "y": TOP_Y, "w": canvasW - 20, "h": TOP_H}
        if zone == "sidebar":
            return {"x": LEFT_X, "y": LEFT_Y, "w": LEFT_W, "h": canvasH - CENTER_H_OFFSET}
        if zone == "editor":
            return {
                "x": CENTER_X,
                "y": CENTER_Y,
                "w": canvasW - CENTER_W_OFFSET,
                "h": canvasH - CENTER_H_OFFSET,
            }
        if zone == "terminal":
            return {
                "x": BOTTOM_X,
                "y": canvasH - BOTTOM_Y_OFFSET,
                "w": canvasW - CENTER_W_OFFSET,
                "h": BOTTOM_H,
            }
        if zone == "inspector":
            return {
                "x": canvasW - RIGHT_X_OFFSET,
                "y": RIGHT_Y,
                "w": RIGHT_W,
                "h": canvasH - CENTER_H_OFFSET,
            }
        if zone == "statusbar":
            return {
                "x": STATUSBAR_X,
                "y": canvasH - STATUSBAR_Y_OFFSET,
                "w": canvasW - 20,
                "h": STATUSBAR_H,
            }
        return {"x": FALLBACK_X, "y": FALLBACK_Y, "w": FALLBACK_W, "h": FALLBACK_H}

    def strengthForEdge(self, edge):
        """Return the dock constraint strength for a given edge."""
        if edge == "top":
            return STRENGTH_DOCK_TOP
        if edge == "left":
            return STRENGTH_DOCK_LEFT
        if edge == "right":
            return STRENGTH_DOCK_RIGHT
        if edge == "bottom":
            return STRENGTH_DOCK_BOTTOM
        return STRENGTH_DOCK_CENTER

    def generateNodes(self, panels, canvasW, canvasH):
        """Generate node dicts from panel specs with zone-based positions."""
        nodes = {}
        for panel in panels:
            panelId = panel.get("id", "")
            panelType = panel.get("type", "")
            if not panelId:
                return None, ("ERR_PANEL_ID", "panel missing id field", 0)
            zone = TYPE_TO_ZONE.get(panelType, "center")
            placement = self.computePlacement(zone, canvasW, canvasH)
            nodes[panelId] = {
                "id": panelId,
                "type": panelType,
                "zone": zone,
                "x": placement["x"],
                "y": placement["y"],
                "w": placement["w"],
                "h": placement["h"],
                "vx": INITIAL_VX,
                "vy": INITIAL_VY,
                "label": panelId,
            }
        return nodes, None

    def generateConstraints(self, nodes):
        """Generate docking constraints from node zone assignments."""
        constraints = []
        for nid, node in nodes.items():
            zone = node.get("zone", "center")
            edge = ZONE_TO_EDGE.get(zone, "center")
            strength = self.strengthForEdge(edge)
            constraints.append({
                "id": nid,
                "edge": edge,
                "strength": strength,
            })
        return constraints

    def generateEdges(self, panelIds):
        """Generate force edges: repulsion between all pairs, attraction between related."""
        edges = []
        idSet = set(panelIds)

        # Repulsion between all pairs
        for i in range(len(panelIds)):
            for j in range(i + 1, len(panelIds)):
                edges.append({
                    "a": panelIds[i],
                    "b": panelIds[j],
                    "type": "repel",
                    "strength": STRENGTH_REPEL,
                })

        # Attraction between related pairs
        for a, b in ATTRACT_PAIRS:
            if a in idSet and b in idSet:
                edges.append({
                    "a": a,
                    "b": b,
                    "type": "attract",
                    "strength": STRENGTH_ATTRACT,
                })

        return edges

    def verifySpec(self, spec):
        """Verify that a generated spec has valid structure."""
        nodes = spec.get("nodes", {})
        if not nodes:
            return (0, None, ("ERR_EMPTY_SPEC", "spec has no nodes", 0))
        for nid, node in nodes.items():
            if "x" not in node or "y" not in node:
                return (0, None, ("ERR_INVALID_NODE", "node missing position: %s" % nid, 0))
            if "w" not in node or "h" not in node:
                return (0, None, ("ERR_INVALID_NODE", "node missing dimensions: %s" % nid, 0))
        return (1, {"valid": True, "node_count": len(nodes)}, None)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_generate(self, params):
        """Generate a full UI spec from a list of desired panel types."""
        panels = self.p(params, "panels")
        if not panels:
            return (0, None, ("ERR_PARAMS", "panels list required", 0))
        canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
        canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])

        # Generate nodes with zone-based positions
        nodes, err = self.generateNodes(panels, canvasW, canvasH)
        if err:
            return (0, None, err)

        # Generate constraints from zone assignments
        constraints = self.generateConstraints(nodes)

        # Generate force edges
        panelIds = list(nodes.keys())
        edges = self.generateEdges(panelIds)

        # Assemble full spec
        spec = {
            "nodes": nodes,
            "constraints": constraints,
            "edges": edges,
            "canvas": {"w": canvasW, "h": canvasH},
            "panel_count": len(nodes),
            "constraint_count": len(constraints),
            "edge_count": len(edges),
        }

        # Verify generated spec
        ok, verifyData, err = self.verifySpec(spec)
        if not ok:
            return (0, None, err)

        self.state["last_spec"] = spec
        self.state["stats"]["specs_generated"] += 1

        return (1, spec, None)

    def cmd_from_template(self, params):
        """Generate a spec from a named template."""
        templateName = self.p(params, "template_name")
        if not templateName:
            return (0, None, ("ERR_PARAMS", "template_name required", 0))
        template = TEMPLATES.get(templateName)
        if not template:
            return (0, None, ("ERR_NOT_FOUND", "template not found: %s" % templateName, 0))

        canvasW = self.p(params, "canvas_w", self.state["config"]["canvas_w"])
        canvasH = self.p(params, "canvas_h", self.state["config"]["canvas_h"])

        # Generate from template panels
        ok, genData, err = self.cmd_generate({
            "panels": template,
            "canvas_w": canvasW,
            "canvas_h": canvasH,
        })
        if not ok:
            return (0, None, err)

        self.state["stats"]["templates_used"] += 1
        return (1, genData, None)

    def cmd_spec(self, params):
        """Return the last generated spec."""
        spec = self.state["last_spec"]
        if not spec:
            return (0, None, ("ERR_NO_SPEC", "no spec generated yet", 0))
        return (1, spec, None)
