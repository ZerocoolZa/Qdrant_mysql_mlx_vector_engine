#!/usr/bin/env python3
# [@GHOST]{[@file<BrainLearning.py>][@domain<graph>][@role<learning_layer>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<learning_layer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainLearning — Advanced learning layer for GuiAiBrain. Good vs bad layout comparison, rule reinforcement, automatic layout recovery (rollback), pattern memory (recurring good layouts become templates). VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainLearning}
# [@METHOD]{Run,compare,reinforce,recover,template,record,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Advanced learning layer for GuiAiBrain: good/bad layout comparison, rule reinforcement, layout recovery rollback, pattern memory templates. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded ring buffer size and template defaults.>][@todos<Move hardcoded buffer size to Config.py>]}
"""
BrainLearning — Advanced learning layer for the GUI AI Brain.

THE 4 CAPABILITIES (steps 21-24 from the roadmap):

  21. GOOD VS BAD COMPARISON ENGINE
      Compares current layout to best-known layout.
      Computes diff score: position delta + energy delta + weight delta.
      Tells you HOW FAR from optimal the current layout is.

  22. RULE REINFORCEMENT
      When a layout succeeds (low energy), the forces that produced it
      get STRENGTHENED. When a layout fails, those forces get WEAKENED.
      This is operant conditioning for the brain.

  23. AUTOMATIC LAYOUT RECOVERY
      If energy spikes (layout gets worse), the brain can ROLLBACK
      to the last known good state. Like undo for layouts.
      Tracks a ring buffer of past states.

  24. PATTERN MEMORY
      When the same good layout keeps appearing, it becomes a TEMPLATE.
      Templates can be loaded instantly without running physics.
      The brain "remembers" good configurations.

USAGE:
  from GuiAiBrain import GuiAiBrain
  from BrainLearning import BrainLearning

  brain = GuiAiBrain()
  brain.Run("perceive", {"spec": spec})
  brain.Run("cycle", {"ticks": 100})

  learner = BrainLearning(param={"brain": brain})
  learner.Run("record")          # save current state
  learner.Run("compare")         # compare to best
  learner.Run("reinforce")       # strengthen good forces
  learner.Run("recover")         # rollback if worse
  learner.Run("template", {"name": "vscode_default"})
  learner.Run("template", {"name": "vscode_default", "load": True})
"""

import json
import os
import math


# ════════════════════════════════════════════
# LEARNING CONSTANTS
# ════════════════════════════════════════════

HISTORY_MAX = 20              # max states in ring buffer
TEMPLATE_DIR = "brain_templates"
RECOVERY_THRESHOLD = 100.0    # energy spike that triggers rollback
REINFORCE_RATE = 0.03         # how much to strengthen/weaken forces
TEMPLATE_THRESHOLD = 50.0     # energy below this = template-worthy
COMPARISON_SCALE = 100.0      # normalization for diff scores


class BrainLearning:
    """
    Advanced learning layer for GuiAiBrain.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Comparison, reinforcement, recovery, pattern memory.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "history_max": HISTORY_MAX,
                "recovery_threshold": RECOVERY_THRESHOLD,
                "reinforce_rate": REINFORCE_RATE,
                "template_threshold": TEMPLATE_THRESHOLD,
                "template_dir": TEMPLATE_DIR,
            },
            "brain": p.get("brain", None),
            "history": [],           # ring buffer of past states
            "templates": {},         # name → saved layout
            "last_good": None,       # last state with low energy
            "stats": {
                "comparisons": 0,
                "reinforcements": 0,
                "recoveries": 0,
                "templates_saved": 0,
                "templates_loaded": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "compare": self.cmd_compare,
            "reinforce": self.cmd_reinforce,
            "recover": self.cmd_recover,
            "template": self.cmd_template,
            "record": self.cmd_record,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k != "brain"}, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def snapshotBrain(self):
        """Take a snapshot of the brain's current state."""
        brain = self.state["brain"]
        if not brain:
            return None
        nodes = {}
        for nid, node in brain.state["graph"]["nodes"].items():
            nodes[nid] = {
                "x": node["x"],
                "y": node["y"],
                "vx": node["vx"],
                "vy": node["vy"],
            }
        return {
            "nodes": nodes,
            "weights": dict(brain.state["weights"]),
            "energy": brain.state["energy"]["total"],
            "temperature": brain.state["temperature"],
            "layout_state": brain.state["layout_state"],
            "tick": brain.state["stats"]["ticks"],
        }

    def restoreSnapshot(self, snap):
        """Restore a snapshot into the brain."""
        brain = self.state["brain"]
        if not brain or not snap:
            return False
        for nid, nd in snap.get("nodes", {}).items():
            node = brain.state["graph"]["nodes"].get(nid)
            if node:
                node["x"] = nd["x"]
                node["y"] = nd["y"]
                node["vx"] = nd.get("vx", 0.0)
                node["vy"] = nd.get("vy", 0.0)
        for wk, wv in snap.get("weights", {}).items():
            if wk in brain.state["weights"]:
                brain.state["weights"][wk] = wv
        brain.state["temperature"] = snap.get("temperature", 0.0)
        brain.state["layout_state"] = snap.get("layout_state", "restored")
        return True

    # ════════════════════════════════════════════
    # STEP 21: GOOD VS BAD COMPARISON ENGINE
    # ════════════════════════════════════════════

    def cmd_compare(self, params):
        """Compare current layout to best known layout."""
        brain = self.state["brain"]
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        wm = brain.state["world_model"]
        currentEnergy = brain.state["energy"]["total"]
        bestEnergy = wm["best_energy"]
        energyDelta = currentEnergy - bestEnergy

        # Position delta from best known state
        positionDelta = 0.0
        if wm["last_stable"]:
            for nid, bestPos in wm["last_stable"].items():
                node = brain.state["graph"]["nodes"].get(nid)
                if node:
                    dx = node["x"] - bestPos["x"]
                    dy = node["y"] - bestPos["y"]
                    positionDelta += math.sqrt(dx * dx + dy * dy)

        # Weight delta from best known weights
        weightDelta = 0.0
        if wm["best_weights"]:
            for wk, wv in wm["best_weights"].items():
                currW = brain.state["weights"].get(wk, 0)
                weightDelta += abs(currW - wv)

        # Overall diff score (lower = closer to optimal)
        diffScore = (energyDelta / COMPARISON_SCALE) + (positionDelta / COMPARISON_SCALE) + weightDelta

        self.state["stats"]["comparisons"] += 1

        # Determine verdict
        if diffScore < 0.1:
            verdict = "OPTIMAL"
        elif diffScore < 1.0:
            verdict = "CLOSE"
        elif diffScore < 5.0:
            verdict = "DRIFTING"
        else:
            verdict = "FAR_FROM_OPTIMAL"

        return (1, {
            "current_energy": round(currentEnergy, 2),
            "best_energy": round(bestEnergy, 2),
            "energy_delta": round(energyDelta, 2),
            "position_delta": round(positionDelta, 2),
            "weight_delta": round(weightDelta, 4),
            "diff_score": round(diffScore, 4),
            "verdict": verdict,
        }, None)

    # ════════════════════════════════════════════
    # STEP 22: RULE REINFORCEMENT
    # ════════════════════════════════════════════

    def cmd_reinforce(self, params):
        """Strengthen forces that produce good layouts, weaken bad ones."""
        brain = self.state["brain"]
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        cfg = self.state["config"]
        rate = cfg["reinforce_rate"]
        weights = brain.state["weights"]
        history = self.state["history"]
        if len(history) < 2:
            return (1, {"reinforced": False, "reason": "insufficient history"}, None)

        prevSnap = history[-2]
        currSnap = history[-1]
        prevEnergy = prevSnap["energy"]
        currEnergy = currSnap["energy"]
        delta = currEnergy - prevEnergy

        reinforcements = []
        if delta < 0:
            # Layout IMPROVED — reinforce current weights
            for wk, wv in currSnap["weights"].items():
                if wk in weights:
                    # Strengthen forces that are active
                    if wv > 1.0:
                        weights[wk] = wv * (1.0 + rate)
                        reinforcements.append("%s UP (good layout)" % wk)
                    elif wv < 1.0:
                        weights[wk] = wv * (1.0 - rate * 0.5)
                        reinforcements.append("%s DOWN (good layout)" % wk)
            self.state["stats"]["reinforcements"] += len(reinforcements)
        elif delta > cfg["recovery_threshold"]:
            # Layout WORSENED — weaken current weights
            for wk, wv in currSnap["weights"].items():
                if wk in weights:
                    weights[wk] = wv * (1.0 - rate * 0.5)
                    reinforcements.append("%s DOWN (bad layout)" % wk)
            self.state["stats"]["reinforcements"] += len(reinforcements)

        return (1, {
            "reinforced": len(reinforcements) > 0,
            "energy_delta": round(delta, 2),
            "reinforcements": reinforcements,
            "current_weights": dict(weights),
        }, None)

    # ════════════════════════════════════════════
    # STEP 23: AUTOMATIC LAYOUT RECOVERY
    # ════════════════════════════════════════════

    def cmd_recover(self, params):
        """Rollback to last known good state if energy spiked."""
        brain = self.state["brain"]
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        cfg = self.state["config"]
        currentEnergy = brain.state["energy"]["total"]
        threshold = cfg["recovery_threshold"]

        # Find last good state from history
        lastGood = None
        for snap in reversed(self.state["history"]):
            if snap["energy"] < currentEnergy - threshold:
                lastGood = snap
                break

        if not lastGood:
            # Try world model's best
            wm = brain.state["world_model"]
            if wm["last_stable"] and wm["best_energy"] < currentEnergy - threshold:
                # Reconstruct snapshot from world model
                lastGood = {
                    "nodes": wm["last_stable"],
                    "weights": wm["best_weights"] or dict(brain.state["weights"]),
                    "energy": wm["best_energy"],
                    "temperature": 0.0,
                    "layout_state": "recovered",
                    "tick": brain.state["stats"]["ticks"],
                }

        if not lastGood:
            return (1, {
                "recovered": False,
                "reason": "no better state found",
                "current_energy": round(currentEnergy, 2),
            }, None)

        # Rollback
        restored = self.restoreSnapshot(lastGood)
        if not restored:
            return (0, None, ("ERR_RESTORE", "failed to restore snapshot", 0))

        self.state["stats"]["recoveries"] += 1
        brain.state["layout_state"] = "recovered"
        newEnergy = brain.state["energy"]["total"]

        return (1, {
            "recovered": True,
            "previous_energy": round(currentEnergy, 2),
            "restored_energy": round(lastGood["energy"], 2),
            "energy_saved": round(currentEnergy - lastGood["energy"], 2),
            "tick_restored_to": lastGood["tick"],
        }, None)

    # ════════════════════════════════════════════
    # STEP 24: PATTERN MEMORY (TEMPLATES)
    # ════════════════════════════════════════════

    def cmd_template(self, params):
        """Save or load a layout template."""
        brain = self.state["brain"]
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        name = self.p(params, "name")
        if not name:
            return (0, None, ("ERR_PARAMS", "name required", 0))
        load = self.p(params, "load", False)
        cfg = self.state["config"]
        tmplDir = cfg["template_dir"]

        if load:
            # Load template
            if name in self.state["templates"]:
                tmpl = self.state["templates"][name]
            else:
                # Try loading from file
                path = os.path.join(tmplDir, name + ".json")
                if not os.path.exists(path):
                    return (0, None, ("ERR_NOT_FOUND", "template not found: %s" % name, 0))
                try:
                    with open(path, "r") as f:
                        tmpl = json.load(f)
                except Exception as e:
                    return (0, None, ("ERR_PARSE", str(e)[:200], 0))
            ok = self.restoreSnapshot(tmpl)
            if not ok:
                return (0, None, ("ERR_RESTORE", "failed to restore template", 0))
            self.state["stats"]["templates_loaded"] += 1
            brain.state["layout_state"] = "template_loaded"
            return (1, {
                "loaded": True,
                "name": name,
                "energy": tmpl.get("energy", 0),
                "nodes": len(tmpl.get("nodes", {})),
            }, None)
        else:
            # Save template
            currentEnergy = brain.state["energy"]["total"]
            if currentEnergy > cfg["template_threshold"]:
                return (1, {
                    "saved": False,
                    "reason": "energy too high for template",
                    "current_energy": round(currentEnergy, 2),
                    "threshold": cfg["template_threshold"],
                }, None)
            snap = self.snapshotBrain()
            snap["name"] = name
            snap["saved_at"] = brain.state["stats"]["ticks"]
            self.state["templates"][name] = snap
            # Also save to file
            if not os.path.exists(tmplDir):
                try:
                    os.makedirs(tmplDir)
                except Exception as e:
                    return (0, None, ("ERR_MKDIR", str(e)[:200], 0))
            path = os.path.join(tmplDir, name + ".json")
            try:
                with open(path, "w") as f:
                    json.dump(snap, f, indent=2)
            except Exception as e:
                return (0, None, ("ERR_WRITE", str(e)[:200], 0))
            self.state["stats"]["templates_saved"] += 1
            return (1, {
                "saved": True,
                "name": name,
                "energy": round(currentEnergy, 2),
                "nodes": len(snap["nodes"]),
                "path": path,
            }, None)

    # ════════════════════════════════════════════
    # STEP 20: RECORD STATE (history buffer)
    # ════════════════════════════════════════════

    def cmd_record(self, params):
        """Record current brain state into history ring buffer."""
        brain = self.state["brain"]
        if not brain:
            return (0, None, ("ERR_PARAMS", "brain required", 0))
        snap = self.snapshotBrain()
        if not snap:
            return (0, None, ("ERR_SNAPSHOT", "failed to snapshot", 0))
        self.state["history"].append(snap)
        # Trim to max
        maxHist = self.state["config"]["history_max"]
        if len(self.state["history"]) > maxHist:
            self.state["history"] = self.state["history"][-maxHist:]
        # Track last good
        cfg = self.state["config"]
        if snap["energy"] < cfg["template_threshold"]:
            self.state["last_good"] = snap
        return (1, {
            "recorded": True,
            "history_size": len(self.state["history"]),
            "energy": round(snap["energy"], 2),
            "tick": snap["tick"],
        }, None)
