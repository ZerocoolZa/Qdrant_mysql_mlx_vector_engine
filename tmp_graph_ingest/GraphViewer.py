# [@GHOST]
# Ghost header — GraphViewer
# Purpose: Shared Tkinter rendering for all 8 graph views. Headless fallback.
# Layer: Below GraphEngine. Above individual View classes.
# [@VBSTYLE]
# VBStyle: Run() dispatch, Tuple3 returns, self.state dict, PascalCase, UPPERCASE
# Rules: @ghost(33), @vbsty(34), @cstyle(35), @clshdr(36), @mthdr(37), @pascal(38), @upper(39), @print(22), @decorators(20), @hardcode(24), @underscore(19), @run(43), @t3(50), @state(41), @ctor(40), @memunit(32), @dismap(31)

import os
import sys
import json
from Config_graph_engine import cfg


class GraphViewer:
    """Shared rendering for all graph views. Tkinter with headless fallback."""

    def __init__(self):
        self.state = {
            "tk_available": False,
            "root": None,
            "canvas": None,
            "title": cfg.GUI_WINDOW["title"],
            "width": cfg.GUI_WINDOW["width"],
            "height": cfg.GUI_WINDOW["height"],
            "colors": cfg.COLORS,
        }
        self.InitTk()

    def InitTk(self):
        """Try to import Tkinter. Set headless mode if unavailable."""
        try:
            import tkinter as tk
            from tkinter import ttk
            self.state["tk_available"] = True
            self.state["tk_module"] = tk
            self.state["ttk_module"] = ttk
        except ImportError:
            self.state["tk_available"] = False
            self.state["tk_module"] = None
            self.state["ttk_module"] = None

    def Run(self, command, params):
        """Dispatch entry point. Returns Tuple3(ok, data, error)."""
        if params is None:
            params = {}
        dispatch = {
            "show": self.Show,
            "render": self.Render,
            "render_nodes": self.RenderNodes,
            "render_edges": self.RenderEdges,
            "close": self.Close,
            "headless": self.Headless,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, "unknown_command: {command}".format(command=command))
        return handler(params)

    def Show(self, params):
        """Create the main window."""
        if not self.state["tk_available"]:
            return self.Headless(params)
        tk = self.state["tk_module"]
        try:
            self.state["root"] = tk.Tk()
            self.state["root"].title(self.state["title"])
            self.state["root"].geometry("{w}x{h}".format(w=self.state["width"], h=self.state["height"]))
            self.state["root"].configure(bg=self.state["colors"]["background"])
            return (1, {"window": "created", "title": self.state["title"]}, None)
        except Exception as exc:
            return (0, None, "tk_init_error: {msg}".format(msg=str(exc)))

    def Render(self, params):
        """Render a complete graph view with nodes and edges."""
        view_name = params.get("view", "unknown")
        nodes = params.get("nodes", [])
        edges = params.get("edges", [])
        if not self.state["tk_available"]:
            return self.Headless({"view": view_name, "nodes": nodes, "edges": edges})
        tk = self.state["tk_module"]
        if not self.state["root"]:
            ok, data, err = self.Show({})
            if not ok:
                return (0, data, err)
        try:
            canvas = tk.Canvas(self.state["root"], bg=self.state["colors"]["background"], width=self.state["width"]-50, height=self.state["height"]-50)
            canvas.pack(padx=10, pady=10)
            self.state["canvas"] = canvas
            self.RenderNodes({"nodes": nodes, "canvas": canvas})
            self.RenderEdges({"edges": edges, "canvas": canvas})
            return (1, {"view": view_name, "nodes": len(nodes), "edges": len(edges), "rendered": True}, None)
        except Exception as exc:
            return (0, None, "render_error: {msg}".format(msg=str(exc)))

    def RenderNodes(self, params):
        """Render nodes on canvas."""
        nodes = params.get("nodes", [])
        canvas = params.get("canvas") or self.state.get("canvas")
        if not self.state["tk_available"] or not canvas:
            return (1, {"nodes": len(nodes), "mode": "headless"}, None)
        colors = self.state["colors"]
        x = 50
        y = 50
        for node in nodes:
            node_type = node.get("type", "default")
            color_key = "node_{ntype}".format(ntype=node_type)
            fill = colors.get(color_key, colors["node_default"])
            canvas.create_oval(x, y, x+60, y+40, fill=fill, outline=colors["text"])
            canvas.create_text(x+30, y+20, text=str(node.get("id", "?"))[:15], fill=colors["text"], font=("Arial", 8))
            x += 80
            if x > self.state["width"] - 100:
                x = 50
                y += 60
        return (1, {"nodes_rendered": len(nodes)}, None)

    def RenderEdges(self, params):
        """Render edges on canvas."""
        edges = params.get("edges", [])
        canvas = params.get("canvas") or self.state.get("canvas")
        if not self.state["tk_available"] or not canvas:
            return (1, {"edges": len(edges), "mode": "headless"}, None)
        for edge in edges:
            src = edge.get("from", "?")
            dst = edge.get("to", "?")
            canvas.create_text(10, 10, text="{src} -> {dst}".format(src=src, dst=dst), fill=self.state["colors"]["edge_default"], anchor="nw")
        return (1, {"edges_rendered": len(edges)}, None)

    def Close(self, params):
        """Close the Tkinter window."""
        if self.state["root"]:
            try:
                self.state["root"].destroy()
            except Exception:
                pass
            self.state["root"] = None
            self.state["canvas"] = None
        return (1, {"closed": True}, None)

    def Headless(self, params):
        """Headless mode — return data without GUI."""
        view = params.get("view", "headless")
        nodes = params.get("nodes", [])
        edges = params.get("edges", [])
        return (
            1,
            {
                "view": view,
                "mode": "headless",
                "nodes": len(nodes),
                "edges": len(edges),
                "node_list": nodes[:10],
                "edge_list": edges[:10],
            },
            None,
        )
