# [@GHOST]
# Ghost header — DecisionGUI
# Purpose: Tkinter GUI for DEGS decision engine. Step button, log panel, graph view.
# Layer: Above DecisionEngine. Calls engine commands.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
from Config_graph_engine import cfg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from DecisionEngine import DecisionEngine
from GraphViewer import GraphViewer


class DecisionGUI:
    """Tkinter GUI for DEGS. Headless fallback if Tkinter unavailable."""

    def __init__(self):
        self.state = {
            "engine": DecisionEngine(),
            "viewer": GraphViewer(),
            "tk_available": False,
            "root": None,
            "log_text": None,
            "status_label": None,
            "run_id": None,
        }
        self.InitTk()

    def InitTk(self):
        """Try to import Tkinter."""
        try:
            import tkinter as tk
            self.state["tk_available"] = True
            self.state["tk_module"] = tk
        except ImportError:
            self.state["tk_available"] = False
            self.state["tk_module"] = None

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "show": self.Show,
            "start": self.StartRun,
            "step": self.StepRun,
            "auto": self.AutoRun,
            "end": self.EndRun,
            "log": self.ShowLog,
            "headless": self.Headless,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Show(self, params):
        """Create the main GUI window."""
        if not self.state["tk_available"]:
            return self.Headless(params)
        tk = self.state["tk_module"]
        try:
            self.state["root"] = tk.Tk()
            self.state["root"].title("DEGS Decision Engine")
            self.state["root"].geometry("1200x800")
            self.state["root"].configure(bg=cfg.GUI_BG)
            self.BuildControls()
            self.BuildLogPanel()
            self.BuildGraphArea()
            return (1, {"gui": "shown"}, None)
        except Exception as exc:
            return (0, None, "gui_error: {msg}".format(msg=str(exc)))

    def BuildControls(self):
        """Build the control panel with buttons."""
        tk = self.state["tk_module"]
        root = self.state["root"]
        panel = tk.Frame(root, bg=cfg.GUI_BG)
        panel.pack(side="top", fill="x", padx=5, pady=5)
        tk.Button(panel, text="Start", command=self.StartRun, bg=cfg.GUI_ACCENT, fg=cfg.GUI_FG).pack(side="left", padx=2)
        tk.Button(panel, text="Step", command=self.StepRun, bg=cfg.GUI_ACCENT, fg=cfg.GUI_FG).pack(side="left", padx=2)
        tk.Button(panel, text="Auto", command=self.AutoRun, bg=cfg.GUI_ACCENT, fg=cfg.GUI_FG).pack(side="left", padx=2)
        tk.Button(panel, text="End", command=self.EndRun, bg=cfg.GUI_ACCENT, fg=cfg.GUI_FG).pack(side="left", padx=2)
        self.state["status_label"] = tk.Label(panel, text="Idle", bg=cfg.GUI_BG, fg=cfg.GUI_FG)
        self.state["status_label"].pack(side="right", padx=5)

    def BuildLogPanel(self):
        """Build the log text area."""
        tk = self.state["tk_module"]
        root = self.state["root"]
        log_frame = tk.Frame(root, bg=cfg.GUI_BG)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=5, pady=5)
        self.state["log_text"] = tk.Text(log_frame, bg="#181825", fg=cfg.GUI_FG, font=("Courier", 10))
        self.state["log_text"].pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(log_frame, command=self.state["log_text"].yview)
        scrollbar.pack(side="right", fill="y")
        self.state["log_text"].config(yscrollcommand=scrollbar.set)

    def BuildGraphArea(self):
        """Build the graph visualization area."""
        tk = self.state["tk_module"]
        root = self.state["root"]
        graph_frame = tk.Frame(root, bg=cfg.GUI_BG, height=300)
        graph_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        canvas = tk.Canvas(graph_frame, bg="#181825", height=300)
        canvas.pack(fill="both", expand=True)
        self.state["canvas"] = canvas

    def StartRun(self, params=None):
        """Start a DEGS run."""
        ok, data, err = self.state["engine"].Run("start", {"start_node": 1})
        if ok:
            self.state["run_id"] = data["run_id"]
            self.AppendLog("Run started: {rid}".format(rid=data["run_id"]))
            self.UpdateStatus("Running")
        else:
            self.AppendLog("Start error: {err}".format(err=err))
        return (ok, data, err)

    def StepRun(self, params=None):
        """Execute one step."""
        if not self.state["run_id"]:
            return (0, None, "no_active_run")
        ok, data, err = self.state["engine"].Run("step", {"run_id": self.state["run_id"]})
        if ok:
            self.AppendLog("Step: node={node}, next={next}".format(node=data.get("node"), next=data.get("next_node")))
            if data.get("terminal"):
                self.UpdateStatus("Completed (terminal)")
        else:
            self.AppendLog("Step error: {err}".format(err=err))
        return (ok, data, err)

    def AutoRun(self, params=None):
        """Run to completion."""
        if not self.state["run_id"]:
            return (0, None, "no_active_run")
        ok, data, err = self.state["engine"].Run("auto", {"run_id": self.state["run_id"]})
        if ok:
            self.AppendLog("Auto completed: {steps} steps".format(steps=data.get("steps")))
            self.UpdateStatus("Completed")
        else:
            self.AppendLog("Auto: {steps} steps, err={err}".format(steps=data.get("steps", 0), err=err))
        return (ok, data, err)

    def EndRun(self, params=None):
        """End the current run."""
        if not self.state["run_id"]:
            return (0, None, "no_active_run")
        ok, data, err = self.state["engine"].Run("end", {"run_id": self.state["run_id"]})
        if ok:
            self.AppendLog("Run ended: state={state}, success={success}".format(state=data.get("state"), success=data.get("success")))
            self.UpdateStatus("Ended")
            self.state["run_id"] = None
        else:
            self.AppendLog("End error: {err}".format(err=err))
        return (ok, data, err)

    def ShowLog(self, params):
        """Show execution log for a run."""
        run_id = params.get("run_id", self.state.get("run_id"))
        if not run_id:
            return (0, None, "missing_param: run_id")
        ok, data, err = self.state["engine"].Run("history", {"run_id": run_id})
        if ok:
            for entry in data.get("trace", []):
                self.AppendLog("[{ts}] node={nid} status={st}".format(ts=entry.get("timestamp"), nid=entry.get("node_id"), st=entry.get("status")))
        return (ok, data, err)

    def AppendLog(self, message):
        """Append a message to the log panel."""
        if self.state.get("log_text"):
            self.state["log_text"].insert("end", message + "\n")
            self.state["log_text"].see("end")
        else:
            self.state.setdefault("log_buffer", [])
            self.state["log_buffer"].append(message)

    def UpdateStatus(self, status):
        """Update the status label."""
        if self.state.get("status_label"):
            self.state["status_label"].config(text=status)
        self.state["status"] = status

    def Headless(self, params):
        """Headless mode — no GUI, return data only."""
        return (1, {"mode": "headless", "message": "Tkinter not available, running headless"}, None)
