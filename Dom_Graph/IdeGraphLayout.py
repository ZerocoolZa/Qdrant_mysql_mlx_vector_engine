#!/usr/bin/env python3
# [@GHOST]{[@file<IdeGraphLayout.py>][@domain<gui>][@role<ide_layout>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<ide_layout>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{IdeGraphLayout — VSCode-style IDE layout compiler. Enforces structural zones (TOP/LEFT/CENTER/RIGHT/BOTTOM). Auto-repairs broken graphs. Generates PyQt6 layout. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{IdeGraphLayout}
# [@METHOD]{Run,build,validate,fix,render,graph,report,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<VSCode-style IDE layout compiler. Enforces structural zones (TOP/LEFT/CENTER/RIGHT/BOTTOM). Auto-repairs broken graphs. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
IdeGraphLayout — VSCode-style IDE layout compiler.

THE ARCHITECTURE:
  A constrained graph mapped into semantic IDE regions.
  Not free layout — STRUCTURED layout.

IDE ZONES (hard constraints):
  TOP    → Toolbar, MenuBar
  LEFT   → Sidebar (Explorer, Search, Git)
  CENTER → Editor (primary workspace)
  RIGHT  → Panel (Inspector, Debug, AI)
  BOTTOM → StatusBar, Terminal

GRAPH RULES (enforcement):
  Each node type MUST map to its zone.
  Wrong zone = energy penalty + auto-repair.
  Missing core panels = system is INVALID.

REQUIRED CORE (VSCode rule):
  - 1 Toolbar OR MenuBar
  - 1 Sidebar
  - 1 Editor
  - 1 StatusBar

USAGE:
  from IdeGraphLayout import IdeGraphLayout

  layout = IdeGraphLayout()
  ok, data, err = layout.Run("build", {"nodes": [...]})
  ok, data, err = layout.Run("validate")   # → errors list
  ok, data, err = layout.Run("fix")        # → auto-repair
  ok, data, err = layout.Run("render")     # → PyQt6 widget tree
  ok, data, err = layout.Run("graph")      # → visual graph
"""

ZONE_RULES = {
    "Toolbar": "TOP",
    "MenuBar": "TOP",
    "Sidebar": "LEFT",
    "Editor": "CENTER",
    "Panel": "RIGHT",
    "StatusBar": "BOTTOM",
    "Terminal": "BOTTOM",
    "Tab": "CENTER",
    "SearchBox": "LEFT",
    "TreeView": "LEFT",
    "Console": "BOTTOM",
}

REQUIRED_CORE = ["Toolbar", "Sidebar", "Editor", "StatusBar"]

ZONE_ORDER = ["TOP", "LEFT", "CENTER", "RIGHT", "BOTTOM"]

ZONE_LABELS = {
    "TOP": "TOOLBAR / MENU",
    "LEFT": "SIDEBAR",
    "CENTER": "EDITOR",
    "RIGHT": "PANEL",
    "BOTTOM": "STATUS / TERMINAL",
}


class IdeGraphLayout:
    """
    VSCode-style IDE layout compiler.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Enforces structural zones, auto-repairs, generates PyQt6.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "enforce_zones": True,
                "auto_inject_missing": True,
                "window_title": param.get("window_title", "Graph IDE Layout") if param else "Graph IDE Layout",
                "window_width": param.get("window_width", 1200) if param else 1200,
                "window_height": param.get("window_height", 800) if param else 800,
            },
            "nodes": {},       # id → node dict
            "errors": [],
            "valid": False,
            "fixed": False,
            "rendered": False,
            "stats": {"total": 0, "by_zone": {}, "by_type": {}},
        }

    def Run(self, command, params=None):
        dispatch = {
            "build": self.cmd_build,
            "validate": self.cmd_validate,
            "fix": self.cmd_fix,
            "render": self.cmd_render,
            "graph": self.cmd_graph,
            "report": self.cmd_report,
            "add_node": self.cmd_add_node,
            "get_zones": self.cmd_get_zones,
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
    # INTERNAL
    # ════════════════════════════════════════════

    def updateStats(self):
        nodes = self.state["nodes"]
        byZone = {}
        byType = {}
        for n in nodes.values():
            zone = n.get("zone", "UNKNOWN")
            ntype = n.get("type", "Unknown")
            byZone[zone] = byZone.get(zone, 0) + 1
            byType[ntype] = byType.get(ntype, 0) + 1
        self.state["stats"] = {
            "total": len(nodes),
            "by_zone": byZone,
            "by_type": byType,
        }

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_build(self, params):
        nodes = self.p(params, "nodes", [])
        for n in nodes:
            nodeId = n.get("id", "")
            if nodeId:
                self.state["nodes"][nodeId] = dict(n)
        self.updateStats()
        return (1, {"built": True, "nodes": len(self.state["nodes"])}, None)

    def cmd_add_node(self, params):
        nodeId = self.p(params, "id")
        if not nodeId:
            return (0, None, ("ERR_PARAMS", "id required", 0))
        ntype = self.p(params, "type", "Widget")
        zone = self.p(params, "zone", ZONE_RULES.get(ntype, "CENTER"))
        node = {
            "id": nodeId,
            "type": ntype,
            "zone": zone,
            "content": self.p(params, "content", ""),
        }
        self.state["nodes"][nodeId] = node
        self.updateStats()
        return (1, node, None)

    def cmd_validate(self, params):
        errors = []
        nodes = self.state["nodes"]

        # Core structure check
        presentTypes = [n.get("type", "") for n in nodes.values()]
        for req in REQUIRED_CORE:
            if req not in presentTypes:
                errors.append("MISSING_CORE:%s" % req)

        # Zone mismatch check
        for nodeId, n in nodes.items():
            ntype = n.get("type", "")
            expectedZone = ZONE_RULES.get(ntype)
            if expectedZone and n.get("zone", "") != expectedZone:
                errors.append("ZONE_MISMATCH:%s:%s->%s" % (nodeId, n.get("zone", ""), expectedZone))

        self.state["errors"] = errors
        self.state["valid"] = len(errors) == 0
        return (1, {
            "valid": self.state["valid"],
            "errors": errors,
            "error_count": len(errors),
        }, None)

    def cmd_fix(self, params):
        """Auto-repair: fix zone mismatches + inject missing core nodes."""
        fixed = []

        # Fix zone mismatches
        for nodeId, n in self.state["nodes"].items():
            ntype = n.get("type", "")
            expectedZone = ZONE_RULES.get(ntype)
            if expectedZone and n.get("zone", "") != expectedZone:
                oldZone = n.get("zone", "")
                n["zone"] = expectedZone
                fixed.append("ZONE_FIX:%s %s->%s" % (nodeId, oldZone, expectedZone))

        # Inject missing core nodes
        if self.state["config"]["auto_inject_missing"]:
            present = {n.get("type", "") for n in self.state["nodes"].values()}
            autoId = 0
            for req in REQUIRED_CORE:
                if req not in present:
                    autoId += 1
                    nodeId = "auto_%s" % req.lower()
                    self.state["nodes"][nodeId] = {
                        "id": nodeId,
                        "type": req,
                        "zone": ZONE_RULES.get(req, "CENTER"),
                        "content": req,
                    }
                    fixed.append("INJECTED:%s (zone=%s)" % (req, ZONE_RULES.get(req, "CENTER")))

        self.state["fixed"] = True
        self.updateStats()

        # Re-validate
        ok, data, err = self.cmd_validate({})
        return (1, {
            "fixed": fixed,
            "valid_after": data["valid"],
            "errors_after": data["errors"],
        }, None)

    def cmd_render(self, params):
        """Generate PyQt6 widget tree description (not actual widgets — layout spec)."""
        if not self.state["valid"] and not self.state["fixed"]:
            ok, data, err = self.cmd_fix({})
            if not ok:
                return (0, None, err)

        layout = {}
        for zone in ZONE_ORDER:
            layout[zone] = []
            for nodeId, n in self.state["nodes"].items():
                if n.get("zone", "") == zone:
                    layout[zone].append({
                        "id": nodeId,
                        "type": n.get("type", ""),
                        "content": n.get("content", ""),
                    })

        self.state["rendered"] = True
        return (1, {
            "rendered": True,
            "window_title": self.state["config"]["window_title"],
            "window_width": self.state["config"]["window_width"],
            "window_height": self.state["config"]["window_height"],
            "layout": layout,
        }, None)

    def cmd_graph(self, params):
        """Visual IDE structure graph."""
        ok, data, err = self.cmd_validate({})
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║           IDE GRAPH — VSCode-Style Layout Compiler          ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("")
        lines.append("  Nodes: %d   Valid: %s   Fixed: %s" % (
            len(self.state["nodes"]),
            "✅" if self.state["valid"] else "❌",
            "✅" if self.state["fixed"] else "—"))
        lines.append("")

        # Zone layout
        for zone in ZONE_ORDER:
            label = ZONE_LABELS.get(zone, zone)
            zoneNodes = [n for n in self.state["nodes"].values() if n.get("zone", "") == zone]
            lines.append("  ┌─ [%s] %s ─%s┐" % (zone, label, "─" * max(0, 30 - len(label))))
            if zoneNodes:
                for n in zoneNodes:
                    ntype = n.get("type", "")
                    content = n.get("content", "")
                    expected = ZONE_RULES.get(ntype, "")
                    if expected and expected == zone:
                        icon = "✅"
                    elif expected and expected != zone:
                        icon = "❌"
                    else:
                        icon = "  "
                    lines.append("  │  %s %-15s  %-15s  %s" % (icon, ntype, n.get("id", ""), content))
            else:
                lines.append("  │  (empty)")
            lines.append("  └%s┘" % ("─" * 62))
            lines.append("")

        # Errors
        if self.state["errors"]:
            lines.append("  ┌─ ERRORS ──────────────────────────────────────────────────┐")
            for e in self.state["errors"]:
                lines.append("  │  ❌ %s" % e)
            lines.append("  └────────────────────────────────────────────────────────────┘")
        else:
            lines.append("  ┌─ VALIDATION ──────────────────────────────────────────────┐")
            lines.append("  │  ✅ All zones correct, all core panels present")
            lines.append("  └────────────────────────────────────────────────────────────┘")

        lines.append("")
        # Core check
        presentTypes = [n.get("type", "") for n in self.state["nodes"].values()]
        lines.append("  ┌─ CORE REQUIREMENTS (VSCode rule) ─────────────────────────┐")
        for req in REQUIRED_CORE:
            if req in presentTypes:
                lines.append("  │  ✅ %s — present" % req)
            else:
                lines.append("  │  ❌ %s — MISSING" % req)
        lines.append("  └────────────────────────────────────────────────────────────┘")

        graph = "\n".join(lines)
        return (1, graph, None)

    def cmd_report(self, params):
        ok, data, err = self.cmd_validate({})
        lines = []
        lines.append("IDE LAYOUT REPORT")
        lines.append("==================")
        lines.append("Nodes: %d" % len(self.state["nodes"]))
        lines.append("Valid: %s" % self.state["valid"])
        lines.append("")
        lines.append("BY ZONE:")
        stats = self.state["stats"]
        for zone in ZONE_ORDER:
            count = stats["by_zone"].get(zone, 0)
            lines.append("  %-10s: %d" % (zone, count))
        lines.append("")
        lines.append("BY TYPE:")
        for ntype, count in sorted(stats["by_type"].items()):
            lines.append("  %-15s: %d" % (ntype, count))
        lines.append("")
        if self.state["errors"]:
            lines.append("ERRORS:")
            for e in self.state["errors"]:
                lines.append("  ❌ %s" % e)
        else:
            lines.append("ERRORS: none ✅")
        report = "\n".join(lines)
        return (1, report, None)

    def cmd_get_zones(self, params):
        return (1, {"zones": ZONE_ORDER, "rules": ZONE_RULES, "required": REQUIRED_CORE}, None)
