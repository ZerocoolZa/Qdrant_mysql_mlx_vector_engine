# [@GHOST]
# Ghost header — GraphOrchestrator
# Purpose: Root coordinator. Single entry point for all subsystems.
# Layer: Sits above CascadeEngine, GraphEngine, DecisionEngine, TmpWorkspace.
# Triangle: Cascade validates -> GraphEngine executes -> DEGS evolves
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import sqlite3
from Config_graph_engine import cfg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CascadeEngine import CascadeEngine


class GraphOrchestrator:
    """Root coordinator. Routes commands to correct subsystem."""

    def __init__(self):
        self.state = {
            "db_path": cfg.DB_PATH,
            "cascade": CascadeEngine(),
            "cascade_run_id": None,
            "cascade_status": None,
        }

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "cascade": self.Cascade,
            "pipeline": self.Pipeline,
            "degs": self.Degs,
            "sandbox": self.Sandbox,
            "engine": self.Engine,
            "gui": self.Gui,
            "status": self.AllStatus,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Cascade(self, params):
        """Forward to CascadeEngine."""
        sub_cmd = params.get("sub_command", "start")
        cascade_params = params.get("params", {})
        if sub_cmd == "start":
            ok, data, err = self.state["cascade"].Run("start", cascade_params)
            if ok:
                self.state["cascade_run_id"] = data["run_id"]
            return (ok, data, err)
        return self.state["cascade"].Run(sub_cmd, cascade_params)

    def Pipeline(self, params):
        """Run full 8-graph cascade validation."""
        domain = params.get("domain", cfg.DOMAIN)
        idea = params.get("idea", "Pipeline run for domain: {domain}".format(domain=domain))
        ok, data, err = self.state["cascade"].Run("start", {"idea": idea})
        if not ok:
            return (0, data, err)
        run_id = data["run_id"]
        self.state["cascade_run_id"] = run_id
        ok, data, err = self.state["cascade"].Run("validate", {"run_id": run_id})
        if not ok:
            return (0, data, err)
        ok, data, err = self.state["cascade"].Run("commit", {"run_id": run_id})
        if not ok:
            return (0, data, err)
        self.state["cascade_status"] = "passed"
        return (1, {"run_id": run_id, "status": "passed", "domain": domain}, None)

    def Degs(self, params):
        """Forward to DecisionEngine (lazy import to avoid circular deps)."""
        from DecisionEngine import DecisionEngine
        engine = DecisionEngine()
        sub_cmd = params.get("sub_command", "start")
        degs_params = params.get("params", {})
        return engine.Run(sub_cmd, degs_params)

    def Sandbox(self, params):
        """Forward to TmpWorkspace (lazy import)."""
        from TmpWorkspace import TmpWorkspace
        ws = TmpWorkspace()
        sub_cmd = params.get("sub_command", "create")
        ws_params = params.get("params", {})
        return ws.Run(sub_cmd, ws_params)

    def Engine(self, params):
        """Forward to GraphEngine (lazy import). GATED by cascade status."""
        sub_cmd = params.get("sub_command", "status")
        engine_params = params.get("params", {})
        if sub_cmd == "code":
            run_id = engine_params.get("cascade_run_id", self.state.get("cascade_run_id"))
            if not run_id:
                return (0, None, cfg.GetError("cascade_not_passed"))
            ok, data, err = self.state["cascade"].Run("commit", {"run_id": run_id})
            if not ok:
                return (0, None, cfg.GetError("cascade_not_passed"))
        from GraphEngine import GraphEngine
        engine = GraphEngine()
        return engine.Run(sub_cmd, engine_params)

    def Gui(self, params):
        """Launch DecisionGUI (lazy import)."""
        try:
            from DecisionGUI import DecisionGUI
            gui = DecisionGUI()
            gui.Run("show", params)
            return (1, {"gui": "launched"}, None)
        except ImportError:
            return (0, None, cfg.GetError("tkinter_unavailable"))
        except Exception as exc:
            return (0, None, "gui_error: {msg}".format(msg=str(exc)))

    def AllStatus(self, params):
        """Return status of all subsystems."""
        db = sqlite3.connect(self.state["db_path"])
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM classes WHERE domain='graph_engine'")
        class_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bcl_instructions")
        bcl_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cascade_rules")
        rule_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM decision_nodes")
        node_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM run_metrics")
        metric_count = cur.fetchone()[0]
        db.close()
        cascade_status = "none"
        if self.state.get("cascade_run_id"):
            ok, data, err = self.state["cascade"].Run(
                "status", {"run_id": self.state["cascade_run_id"]}
            )
            if ok:
                cascade_status = data["status"]
        return (
            1,
            {
                "db_path": self.state["db_path"],
                "classes": class_count,
                "bcl_instructions": bcl_count,
                "cascade_rules": rule_count,
                "decision_nodes": node_count,
                "run_metrics": metric_count,
                "cascade_run_id": self.state.get("cascade_run_id"),
                "cascade_status": cascade_status,
            },
            None,
        )
