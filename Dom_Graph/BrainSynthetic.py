#!/usr/bin/env python3
# [@GHOST]{[@file<BrainSynthetic.py>][@domain<graph>][@role<synthetic_generator>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<synthetic_generator>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainSynthetic — Synthetic UI graph generator for RL layout brain training. Generates random UI specs (some good, some bad) with items, constraints, edges in the format GuiAiBrain.Run("perceive", {"spec": ...}) expects. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainSynthetic}
# [@METHOD]{Run,generate,random_spec,good_spec,bad_spec,batch,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Synthetic UI graph generator for RL training. Generates good/bad/random UI specs. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded CANVAS_WIDTH=1000, CANVAS_HEIGHT=700, MIN/MAX_PANELS, PANEL_TYPES constants.>][@todos<Move canvas and panel constants to Config.py>]}
"""
BrainSynthetic — Synthetic UI graph generator for RL training.

WHAT IT DOES:
  Generates synthetic UI specs for the RL layout brain to learn from.
  Each spec is a dict with "items", "constraints", "edges" — the same
  format that GuiAiBrain.Run("perceive", {"spec": ...}) expects.

  - good_spec: panels already in correct VSCode zones (low energy target)
  - bad_spec:  panels deliberately overlapping and misplaced (high energy)
  - random_spec: random panel types with random positions
  - batch:     mix of good/bad/random for training

SPEC FORMAT:
  {
    "items":       [ {id, type, role, x, y, w, h, label}, ... ],
    "constraints": [ {id, type, edge, strength}, ... ],
    "edges":       [ {a, b, type, strength}, ... ],
    "canvas":      {w, h},
    "label":       "good" | "bad" | "random",
  }

USAGE:
  from BrainSynthetic import BrainSynthetic

  gen = BrainSynthetic()
  ok, data, err = gen.Run("good_spec", {})
  ok, data, err = gen.Run("batch", {"size": 32})
  ok, data, err = gen.Run("generate", {"count": 10})
"""

import random


# ════════════════════════════════════════════
# SYNTHETIC GENERATOR CONSTANTS
# ════════════════════════════════════════════

CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700
MIN_PANELS = 3
MAX_PANELS = 8
PANEL_TYPES = ("Toolbar", "Sidebar", "Editor", "Terminal", "Inspector", "StatusBar", "Panel", "MenuBar")
PANEL_ROLES = ("top", "left", "right", "bottom", "center")
DOCK_EDGES = ("top", "left", "right", "bottom", "center")
BATCH_SIZE = 32
RANDOM_SEED = 42

# Good-spec VSCode zone placements (x, y, w, h)
GOOD_TOOLBAR = (10, 10, 980, 30)
GOOD_SIDEBAR = (10, 50, 200, 580)
GOOD_EDITOR = (220, 50, 560, 480)
GOOD_TERMINAL = (220, 540, 560, 90)
GOOD_INSPECTOR = (790, 50, 200, 580)
GOOD_STATUSBAR = (10, 685, 980, 5)

# Panel type → role
TYPE_TO_ROLE = {
    "Toolbar": "top",
    "Sidebar": "left",
    "Editor": "center",
    "Terminal": "bottom",
    "Inspector": "right",
    "StatusBar": "bottom",
    "MenuBar": "top",
    "Panel": "center",
}

# Panel type → dock edge
TYPE_TO_EDGE = {
    "Toolbar": "top",
    "Sidebar": "left",
    "Editor": "center",
    "Terminal": "bottom",
    "Inspector": "right",
    "StatusBar": "bottom",
    "MenuBar": "top",
    "Panel": "center",
}

# Panel type → good placement tuple
GOOD_PLACEMENT = {
    "Toolbar": GOOD_TOOLBAR,
    "Sidebar": GOOD_SIDEBAR,
    "Editor": GOOD_EDITOR,
    "Terminal": GOOD_TERMINAL,
    "Inspector": GOOD_INSPECTOR,
    "StatusBar": GOOD_STATUSBAR,
}

# Dock constraint strengths
STRENGTH_DOCK_TOP = 0.95
STRENGTH_DOCK_LEFT = 0.85
STRENGTH_DOCK_RIGHT = 0.85
STRENGTH_DOCK_BOTTOM = 0.80
STRENGTH_DOCK_CENTER = 0.50
STRENGTH_REPEL = 0.60
STRENGTH_ATTRACT = 0.40

# Bad-spec overlap offsets
BAD_X_JITTER = 400
BAD_Y_JITTER = 300
BAD_W_MIN = 150
BAD_W_MAX = 500
BAD_H_MIN = 100
BAD_H_MAX = 400

# Random-spec size ranges
RAND_W_MIN = 120
RAND_W_MAX = 400
RAND_H_MIN = 80
RAND_H_MAX = 300


class BrainSynthetic:
    """
    Synthetic UI graph generator for RL layout brain training.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Produces specs with items, constraints, edges.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "canvas_w": p.get("canvas_w", CANVAS_WIDTH),
                "canvas_h": p.get("canvas_h", CANVAS_HEIGHT),
                "seed": p.get("seed", RANDOM_SEED),
                "batch_size": p.get("batch_size", BATCH_SIZE),
            },
            "rng": random.Random(p.get("seed", RANDOM_SEED)),
            "last_spec": None,
            "stats": {
                "specs_generated": 0,
                "good_generated": 0,
                "bad_generated": 0,
                "random_generated": 0,
                "batches_generated": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "generate": self.cmd_generate,
            "random_spec": self.cmd_random_spec,
            "good_spec": self.cmd_good_spec,
            "bad_spec": self.cmd_bad_spec,
            "batch": self.cmd_batch,
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
        if "seed" in params:
            self.state["rng"] = random.Random(params["seed"])
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # INTERNAL HELPERS
    # ════════════════════════════════════════════

    def strengthForEdge(self, edge):
        """Return dock constraint strength for a given edge."""
        if edge == "top":
            return STRENGTH_DOCK_TOP
        if edge == "left":
            return STRENGTH_DOCK_LEFT
        if edge == "right":
            return STRENGTH_DOCK_RIGHT
        if edge == "bottom":
            return STRENGTH_DOCK_BOTTOM
        return STRENGTH_DOCK_CENTER

    def makeItem(self, itemId, panelType, x, y, w, h, role):
        """Build a single item dict for a spec."""
        return {
            "id": itemId,
            "type": panelType,
            "role": role,
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "label": itemId,
        }

    def makeConstraint(self, itemId, edge):
        """Build a single dock constraint dict."""
        return {
            "id": itemId,
            "type": "dock",
            "edge": edge,
            "strength": self.strengthForEdge(edge),
        }

    def makeEdges(self, itemIds):
        """Build repulsion edges between all pairs of items."""
        edges = []
        for i in range(len(itemIds)):
            for j in range(i + 1, len(itemIds)):
                edges.append({
                    "a": itemIds[i],
                    "b": itemIds[j],
                    "type": "repel",
                    "strength": STRENGTH_REPEL,
                })
        return edges

    def pickPanelTypes(self, count):
        """Pick count distinct panel types from PANEL_TYPES."""
        pool = list(PANEL_TYPES)
        self.state["rng"].shuffle(pool)
        return pool[:count]

    def panelIdFor(self, panelType, index):
        """Build a stable panel id from type and index."""
        return "%s_%d" % (panelType.lower(), index)

    # ════════════════════════════════════════════
    # SPEC GENERATORS
    # ════════════════════════════════════════════

    def buildGoodSpec(self):
        """Generate a spec with panels in correct VSCode zones (low energy)."""
        canvasW = self.state["config"]["canvas_w"]
        canvasH = self.state["config"]["canvas_h"]
        scaleX = canvasW / float(CANVAS_WIDTH)
        scaleY = canvasH / float(CANVAS_HEIGHT)

        items = []
        constraints = []
        index = 0
        for panelType, placement in GOOD_PLACEMENT.items():
            itemId = self.panelIdFor(panelType, index)
            x = int(placement[0] * scaleX)
            y = int(placement[1] * scaleY)
            w = int(placement[2] * scaleX)
            h = int(placement[3] * scaleY)
            role = TYPE_TO_ROLE.get(panelType, "center")
            items.append(self.makeItem(itemId, panelType, x, y, w, h, role))
            edge = TYPE_TO_EDGE.get(panelType, "center")
            constraints.append(self.makeConstraint(itemId, edge))
            index += 1

        itemIds = [it["id"] for it in items]
        edges = self.makeEdges(itemIds)
        spec = {
            "items": items,
            "constraints": constraints,
            "edges": edges,
            "canvas": {"w": canvasW, "h": canvasH},
            "label": "good",
        }
        return spec

    def buildBadSpec(self):
        """Generate a spec with panels deliberately overlapping and misplaced."""
        canvasW = self.state["config"]["canvas_w"]
        canvasH = self.state["config"]["canvas_h"]
        rng = self.state["rng"]

        count = rng.randint(MIN_PANELS, MAX_PANELS)
        panelTypes = self.pickPanelTypes(count)

        items = []
        constraints = []
        for index, panelType in enumerate(panelTypes):
            itemId = self.panelIdFor(panelType, index)
            # Deliberately cluster near center to force overlaps
            x = rng.randint(0, BAD_X_JITTER)
            y = rng.randint(0, BAD_Y_JITTER)
            w = rng.randint(BAD_W_MIN, BAD_W_MAX)
            h = rng.randint(BAD_H_MIN, BAD_H_MAX)
            role = rng.choice(PANEL_ROLES)
            items.append(self.makeItem(itemId, panelType, x, y, w, h, role))
            edge = rng.choice(DOCK_EDGES)
            constraints.append(self.makeConstraint(itemId, edge))

        itemIds = [it["id"] for it in items]
        edges = self.makeEdges(itemIds)
        spec = {
            "items": items,
            "constraints": constraints,
            "edges": edges,
            "canvas": {"w": canvasW, "h": canvasH},
            "label": "bad",
        }
        return spec

    def buildRandomSpec(self):
        """Generate a spec with random panel types and random positions."""
        canvasW = self.state["config"]["canvas_w"]
        canvasH = self.state["config"]["canvas_h"]
        rng = self.state["rng"]

        count = rng.randint(MIN_PANELS, MAX_PANELS)
        panelTypes = self.pickPanelTypes(count)

        items = []
        constraints = []
        for index, panelType in enumerate(panelTypes):
            itemId = self.panelIdFor(panelType, index)
            w = rng.randint(RAND_W_MIN, RAND_W_MAX)
            h = rng.randint(RAND_H_MIN, RAND_H_MAX)
            maxX = max(0, canvasW - w)
            maxY = max(0, canvasH - h)
            x = rng.randint(0, maxX) if maxX > 0 else 0
            y = rng.randint(0, maxY) if maxY > 0 else 0
            role = TYPE_TO_ROLE.get(panelType, "center")
            items.append(self.makeItem(itemId, panelType, x, y, w, h, role))
            edge = TYPE_TO_EDGE.get(panelType, "center")
            constraints.append(self.makeConstraint(itemId, edge))

        itemIds = [it["id"] for it in items]
        edges = self.makeEdges(itemIds)
        spec = {
            "items": items,
            "constraints": constraints,
            "edges": edges,
            "canvas": {"w": canvasW, "h": canvasH},
            "label": "random",
        }
        return spec

    def verifySpec(self, spec):
        """Verify that a generated spec has valid structure."""
        items = spec.get("items", [])
        if not items:
            return (0, None, ("ERR_EMPTY_SPEC", "spec has no items", 0))
        for item in items:
            if "x" not in item or "y" not in item:
                return (0, None, ("ERR_INVALID_ITEM", "item missing position: %s" % item.get("id", ""), 0))
            if "w" not in item or "h" not in item:
                return (0, None, ("ERR_INVALID_ITEM", "item missing dimensions: %s" % item.get("id", ""), 0))
        if "constraints" not in spec:
            return (0, None, ("ERR_NO_CONSTRAINTS", "spec missing constraints", 0))
        if "edges" not in spec:
            return (0, None, ("ERR_NO_EDGES", "spec missing edges", 0))
        return (1, {"valid": True, "item_count": len(items)}, None)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_generate(self, params):
        """Generate count random specs and return a list."""
        count = self.p(params, "count", 1)
        if not count or count < 1:
            return (0, None, ("ERR_PARAMS", "count must be >= 1", 0))

        specs = []
        for _ in range(count):
            spec = self.buildRandomSpec()
            ok, verifyData, err = self.verifySpec(spec)
            if not ok:
                return (0, None, err)
            specs.append(spec)
            self.state["stats"]["specs_generated"] += 1
            self.state["stats"]["random_generated"] += 1

        self.state["last_spec"] = specs[-1]
        return (1, specs, None)

    def cmd_random_spec(self, params):
        """Generate one random spec with random positions."""
        spec = self.buildRandomSpec()
        ok, verifyData, err = self.verifySpec(spec)
        if not ok:
            return (0, None, err)

        self.state["last_spec"] = spec
        self.state["stats"]["specs_generated"] += 1
        self.state["stats"]["random_generated"] += 1
        return (1, spec, None)

    def cmd_good_spec(self, params):
        """Generate one spec with panels in correct VSCode zones (low energy)."""
        spec = self.buildGoodSpec()
        ok, verifyData, err = self.verifySpec(spec)
        if not ok:
            return (0, None, err)

        self.state["last_spec"] = spec
        self.state["stats"]["specs_generated"] += 1
        self.state["stats"]["good_generated"] += 1
        return (1, spec, None)

    def cmd_bad_spec(self, params):
        """Generate one spec with panels deliberately overlapping (high energy)."""
        spec = self.buildBadSpec()
        ok, verifyData, err = self.verifySpec(spec)
        if not ok:
            return (0, None, err)

        self.state["last_spec"] = spec
        self.state["stats"]["specs_generated"] += 1
        self.state["stats"]["bad_generated"] += 1
        return (1, spec, None)

    def cmd_batch(self, params):
        """Generate a batch of specs for training — mix of good/bad/random."""
        size = self.p(params, "size", self.state["config"]["batch_size"])
        if not size or size < 1:
            return (0, None, ("ERR_PARAMS", "size must be >= 1", 0))

        specs = []
        for i in range(size):
            mod = i % 3
            if mod == 0:
                spec = self.buildGoodSpec()
                self.state["stats"]["good_generated"] += 1
            elif mod == 1:
                spec = self.buildBadSpec()
                self.state["stats"]["bad_generated"] += 1
            else:
                spec = self.buildRandomSpec()
                self.state["stats"]["random_generated"] += 1

            ok, verifyData, err = self.verifySpec(spec)
            if not ok:
                return (0, None, err)

            specs.append(spec)
            self.state["stats"]["specs_generated"] += 1

        self.state["last_spec"] = specs[-1]
        self.state["stats"]["batches_generated"] += 1
        return (1, specs, None)
