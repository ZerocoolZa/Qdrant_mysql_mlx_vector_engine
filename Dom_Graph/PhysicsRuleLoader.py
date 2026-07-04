#!/usr/bin/env python3
# [@GHOST]{[@file<PhysicsRuleLoader.py>][@domain<graph>][@role<rule_loader>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<rule_loader>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{PhysicsRuleLoader — Load magnetic force rules from JSON config. Define items, anchors, forces in a file. Feed into GraphPhysics. Shake to resolve. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{PhysicsRuleLoader}
# [@METHOD]{Run,load,save,compile,validate,template,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<JSON rule system for UI Physics Composer. Loads items, anchors, forces from JSON config, compiles into GraphPhysics commands. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
PhysicsRuleLoader — JSON rule system for the UI Physics Composer.

WHAT IT DOES:
  Reads a JSON config file that defines:
    - items:       UI elements with positions and sizes
    - anchors:     which edge each item should stick to
    - forces:      attract/repel pairs between items
    - rules:       type-based auto-forces (all Toolbars repel each other, etc.)
    - anneal:      shake temperature and cooling schedule

  Then compiles those rules into GraphPhysics commands and runs them.

THE JSON FORMAT:
  {
    "canvas": {"width": 1000, "height": 700},
    "items": [
      {"id": "toolbar", "type": "Toolbar", "x": 400, "y": 300, "w": 600, "h": 30}
    ],
    "anchors": [
      {"id": "toolbar", "edge": "top", "strength": 0.9}
    ],
    "forces": [
      {"a": "toolbar", "b": "sidebar", "type": "repel", "strength": 0.6}
    ],
    "rules": [
      {"type": "Toolbar", "anchor": "top", "strength": 0.9},
      {"same_type": "Button", "force": "repel", "strength": 0.5},
      {"pair": ["Input", "Label"], "force": "attract", "strength": 0.3}
    ],
    "anneal": {"temperature": 0.8, "steps": 300, "cooling": 0.98}
  }

THE RULE SYSTEM:
  Type-based rules auto-generate forces:
    - "all Toolbars anchor to top"
    - "all Buttons repel each other"
    - "Inputs attract Labels"
    - "Panels repel Modals"

  This means you define RULES, not individual forces.
  The compiler expands rules into concrete force pairs.

USAGE:
  from PhysicsRuleLoader import PhysicsRuleLoader
  from GraphPhysics import GraphPhysics

  loader = PhysicsRuleLoader()
  ok, data, err = loader.Run("load", {"path": "layout_rules.json"})
  ok, data, err = loader.Run("compile", {"engine": physics_engine})
  # Now the engine has all items, anchors, forces loaded
  # Shake it!
  physics_engine.Run("shake", {"temperature": 0.8})
  physics_engine.Run("anneal", {"steps": 300, "cooling": 0.98})
"""

import json
import os


# ════════════════════════════════════════════
# DEFAULT RULES — VSCode-style layout
# ════════════════════════════════════════════

DEFAULT_CANVAS_W = 1000
DEFAULT_CANVAS_H = 700
DEFAULT_TEMP = 0.8
DEFAULT_STEPS = 300
DEFAULT_COOLING = 0.98


class PhysicsRuleLoader:
    """
    JSON rule system for UI Physics Composer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Loads rules from JSON, compiles into GraphPhysics commands.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "default_canvas_w": DEFAULT_CANVAS_W,
                "default_canvas_h": DEFAULT_CANVAS_H,
                "default_temp": DEFAULT_TEMP,
                "default_steps": DEFAULT_STEPS,
                "default_cooling": DEFAULT_COOLING,
            },
            "ruleset": None,         # loaded JSON rules
            "compiled": None,        # compiled commands list
            "validation": [],        # validation errors
            "stats": {"items": 0, "anchors": 0, "forces": 0, "rules": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "load": self.cmd_load,
            "save": self.cmd_save,
            "compile": self.cmd_compile,
            "validate": self.cmd_validate,
            "template": self.cmd_template,
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
    # INTERNAL — rule expansion
    # ════════════════════════════════════════════

    def expandRules(self, ruleset):
        """Expand type-based rules into concrete force pairs and anchors."""
        items = ruleset.get("items", [])
        rules = ruleset.get("rules", [])
        expandedAnchors = list(ruleset.get("anchors", []))
        expandedForces = list(ruleset.get("forces", []))

        for rule in rules:
            # Type-based anchor: all items of type X anchor to edge Y
            if "type" in rule and "anchor" in rule:
                anchorEdge = rule["anchor"]
                anchorStrength = rule.get("strength", 0.8)
                for item in items:
                    if item.get("type", "") == rule["type"]:
                        expandedAnchors.append({
                            "id": item["id"],
                            "edge": anchorEdge,
                            "strength": anchorStrength,
                        })

            # Same-type repel: all items of type X repel each other
            if "same_type" in rule and "force" in rule:
                itemType = rule["same_type"]
                forceType = rule["force"]
                strength = rule.get("strength", 0.5)
                matched = [i for i in items if i.get("type", "") == itemType]
                for i in range(len(matched)):
                    for j in range(i + 1, len(matched)):
                        expandedForces.append({
                            "a": matched[i]["id"],
                            "b": matched[j]["id"],
                            "type": forceType,
                            "strength": strength,
                        })

            # Pair attraction: items of type A attract items of type B
            if "pair" in rule and "force" in rule:
                pair = rule["pair"]
                forceType = rule["force"]
                strength = rule.get("strength", 0.3)
                if len(pair) == 2:
                    typeA = pair[0]
                    typeB = pair[1]
                    itemsA = [i for i in items if i.get("type", "") == typeA]
                    itemsB = [i for i in items if i.get("type", "") == typeB]
                    for a in itemsA:
                        for b in itemsB:
                            if a["id"] != b["id"]:
                                expandedForces.append({
                                    "a": a["id"],
                                    "b": b["id"],
                                    "type": forceType,
                                    "strength": strength,
                                })

        # Deduplicate anchors (keep highest strength per id)
        anchorMap = {}
        for a in expandedAnchors:
            aid = a["id"]
            if aid not in anchorMap or a["strength"] > anchorMap[aid]["strength"]:
                anchorMap[aid] = a
        expandedAnchors = list(anchorMap.values())

        # Deduplicate forces (same a+b pair, keep highest strength)
        forceMap = {}
        for f in expandedForces:
            key = tuple(sorted([f["a"], f["b"]])) + (f["type"],)
            if key not in forceMap or f["strength"] > forceMap[key]["strength"]:
                forceMap[key] = f
        expandedForces = list(forceMap.values())

        ruleset["anchors"] = expandedAnchors
        ruleset["forces"] = expandedForces
        return ruleset

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_load(self, params):
        """Load rules from a JSON file."""
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not os.path.exists(path):
            return (0, None, ("ERR_NOT_FOUND", "file not found: %s" % path, 0))
        try:
            with open(path, "r") as f:
                ruleset = json.load(f)
        except Exception as e:
            return (0, None, ("ERR_PARSE", str(e)[:200], 0))
        # Expand rules
        ruleset = self.expandRules(ruleset)
        self.state["ruleset"] = ruleset
        self.state["stats"] = {
            "items": len(ruleset.get("items", [])),
            "anchors": len(ruleset.get("anchors", [])),
            "forces": len(ruleset.get("forces", [])),
            "rules": len(ruleset.get("rules", [])),
        }
        return (1, {
            "loaded": True,
            "path": path,
            "stats": self.state["stats"],
        }, None)

    def cmd_save(self, params):
        """Save current ruleset to a JSON file."""
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not self.state["ruleset"]:
            return (0, None, ("ERR_NO_RULES", "no ruleset loaded", 0))
        try:
            with open(path, "w") as f:
                json.dump(self.state["ruleset"], f, indent=2)
        except Exception as e:
            return (0, None, ("ERR_WRITE", str(e)[:200], 0))
        return (1, {"saved": True, "path": path}, None)

    def cmd_compile(self, params):
        """Compile loaded ruleset into GraphPhysics engine commands and execute them."""
        engine = self.p(params, "engine")
        if not engine:
            return (0, None, ("ERR_PARAMS", "engine required", 0))
        if not self.state["ruleset"]:
            return (0, None, ("ERR_NO_RULES", "load rules first", 0))
        ruleset = self.state["ruleset"]
        commands = []

        # Set canvas size
        canvas = ruleset.get("canvas", {})
        if canvas:
            engine.Run("set_config", {
                "canvas_w": canvas.get("width", DEFAULT_CANVAS_W),
                "canvas_h": canvas.get("height", DEFAULT_CANVAS_H),
            })
            commands.append({"cmd": "set_config", "canvas": canvas})

        # Add items
        for item in ruleset.get("items", []):
            ok, data, err = engine.Run("add", item)
            if not ok:
                return (0, None, err)
            commands.append({"cmd": "add", "item": item})

        # Add anchors
        for anchor in ruleset.get("anchors", []):
            ok, data, err = engine.Run("anchor", anchor)
            if ok:
                commands.append({"cmd": "anchor", "anchor": anchor})

        # Add forces
        for force in ruleset.get("forces", []):
            ok, data, err = engine.Run("force", force)
            if ok:
                commands.append({"cmd": "force", "force": force})

        # Set anneal params
        anneal = ruleset.get("anneal", {})
        if anneal:
            temp = anneal.get("temperature", DEFAULT_TEMP)
            engine.Run("shake", {"temperature": temp})
            commands.append({"cmd": "shake", "temperature": temp})

        self.state["compiled"] = commands
        return (1, {
            "compiled": True,
            "commands": len(commands),
            "items": len(ruleset.get("items", [])),
            "anchors": len(ruleset.get("anchors", [])),
            "forces": len(ruleset.get("forces", [])),
        }, None)

    def cmd_validate(self, params):
        """Validate the loaded ruleset for errors."""
        if not self.state["ruleset"]:
            return (0, None, ("ERR_NO_RULES", "load rules first", 0))
        ruleset = self.state["ruleset"]
        errors = []
        warnings = []
        itemIds = set()
        for item in ruleset.get("items", []):
            iid = item.get("id", "")
            if not iid:
                errors.append("item missing id")
            elif iid in itemIds:
                errors.append("duplicate item id: %s" % iid)
            else:
                itemIds.add(iid)
            if "x" not in item or "y" not in item:
                warnings.append("item %s missing position" % iid)
        for anchor in ruleset.get("anchors", []):
            if anchor.get("id", "") not in itemIds:
                errors.append("anchor references unknown item: %s" % anchor.get("id", ""))
            if anchor.get("edge", "") not in ("top", "bottom", "left", "right", "center"):
                errors.append("anchor %s has invalid edge: %s" % (anchor.get("id", ""), anchor.get("edge", "")))
        for force in ruleset.get("forces", []):
            if force.get("a", "") not in itemIds:
                errors.append("force references unknown item a: %s" % force.get("a", ""))
            if force.get("b", "") not in itemIds:
                errors.append("force references unknown item b: %s" % force.get("b", ""))
            if force.get("type", "") not in ("attract", "repel"):
                errors.append("force has invalid type: %s" % force.get("type", ""))
        self.state["validation"] = errors + warnings
        return (1, {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }, None)

    def cmd_template(self, params):
        """Generate a template JSON ruleset for VSCode-style layout."""
        template = {
            "canvas": {"width": DEFAULT_CANVAS_W, "height": DEFAULT_CANVAS_H},
            "items": [
                {"id": "menubar", "type": "MenuBar", "x": 100, "y": 300, "w": 800, "h": 25},
                {"id": "toolbar", "type": "Toolbar", "x": 400, "y": 350, "w": 600, "h": 30},
                {"id": "sidebar", "type": "Sidebar", "x": 700, "y": 100, "w": 200, "h": 400},
                {"id": "editor", "type": "Editor", "x": 50, "y": 500, "w": 400, "h": 300},
                {"id": "panel", "type": "Panel", "x": 600, "y": 600, "w": 300, "h": 200},
                {"id": "statusbar", "type": "StatusBar", "x": 300, "y": 50, "w": 400, "h": 20},
                {"id": "terminal", "type": "Terminal", "x": 200, "y": 600, "w": 500, "h": 80},
            ],
            "anchors": [
                {"id": "menubar", "edge": "top", "strength": 0.95},
                {"id": "toolbar", "edge": "top", "strength": 0.85},
                {"id": "sidebar", "edge": "left", "strength": 0.8},
                {"id": "statusbar", "edge": "bottom", "strength": 0.9},
                {"id": "terminal", "edge": "bottom", "strength": 0.7},
                {"id": "editor", "edge": "center", "strength": 0.5},
            ],
            "forces": [
                {"a": "toolbar", "b": "sidebar", "type": "repel", "strength": 0.6},
                {"a": "editor", "b": "panel", "type": "attract", "strength": 0.4},
                {"a": "terminal", "b": "editor", "type": "repel", "strength": 0.5},
            ],
            "rules": [
                {"type": "MenuBar", "anchor": "top", "strength": 0.95},
                {"type": "StatusBar", "anchor": "bottom", "strength": 0.9},
                {"same_type": "Button", "force": "repel", "strength": 0.5},
                {"pair": ["Input", "Label"], "force": "attract", "strength": 0.3},
                {"pair": ["Editor", "Panel"], "force": "attract", "strength": 0.4},
            ],
            "anneal": {
                "temperature": DEFAULT_TEMP,
                "steps": DEFAULT_STEPS,
                "cooling": DEFAULT_COOLING,
            },
        }
        path = self.p(params, "path")
        if path:
            try:
                with open(path, "w") as f:
                    json.dump(template, f, indent=2)
                return (1, {"saved": True, "path": path, "items": len(template["items"])}, None)
            except Exception as e:
                return (0, None, ("ERR_WRITE", str(e)[:200], 0))
        return (1, template, None)
