#[@GHOST]{[@file<LayoutEngine.py>][@domain<layout_engine_facade>][@role<public_api>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<facade>][@return<Tuple3>][@state<engine,lifecycle,renderers>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/LayoutEngine.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Public facade: Engine.build(tree) -> Engine.render(target). One entry point for the unified Layout Graph kernel.}
#[@CLASS]{LayoutEngine — owns Lifecycle, TerminalRenderer, QtRenderer; one public API for both render targets}
#[@METHOD]{Run dispatch: build, render, render_terminal, render_qt, invalidate, viewport, read_state, set_config}

import logging

import Config
from LayoutNode import (
    LayoutNode, ContainerNode, RowNode, ColumnNode, BlockNode,
    WidgetNode, TextNode, TableNode, TreeNode, PipelineNode,
    SpacerNode, DividerNode,
)
from Constraints import ConstraintSolver
from Lifecycle import Lifecycle
from Responsive import ResponsiveResolver
from TextLayout import TextLayout
from AnsiTheme import AnsiTheme
from TerminalRenderer import TerminalRenderer
from QtRenderer import QtRenderer
from DomDiff import DomDiff
from DependencyOrder import DependencyOrder
from DomHistory import DomHistory

log = logging.getLogger("LayoutEngine")


class LayoutEngine:
    """Public facade for the unified Layout Graph kernel.

    Usage:
        eng = LayoutEngine(param={"target": "terminal", "width": 120})
        eng.Run("build", {"spec": {...}})          # or {"root": node}
        eng.Run("render", {"target": "terminal"})  # -> ANSI string
        eng.Run("render", {"target": "qt"})        # -> QWidget

    Both render targets consume the SAME solved LayoutNode tree.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        width = p.get("width", Config.DEFAULT_TERM_WIDTH)
        height = p.get("height", Config.DEFAULT_TERM_HEIGHT)
        target = p.get("target", Config.TARGET_TERMINAL)
        theme = p.get("theme", Config.THEME_DEFAULT)
        self.state = {
            "config": {
                "width": width, "height": height,
                "target": target, "theme": theme,
                "scale_x": p.get("scale_x", 8),
                "scale_y": p.get("scale_y", 16),
            },
            "lifecycle": Lifecycle(mem, db, {
                "width": width, "height": height,
                "target": target, "theme": theme,
            }),
            "terminal_renderer": TerminalRenderer(mem, db, {
                "width": width, "height": height, "theme": theme,
            }),
            "qt_renderer": QtRenderer(mem, db, {
                "scale_x": p.get("scale_x", 8),
                "scale_y": p.get("scale_y", 16),
            }),
            "dom_diff": DomDiff(mem, db, p),
            "dependency_order": DependencyOrder(mem, db, p),
            "dom_history": DomHistory(mem, db, p),
            "last_render": None,
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "build": self.build,
            "render": self.render,
            "render_terminal": self.render_terminal,
            "render_qt": self.render_qt,
            "invalidate": self.invalidate,
            "viewport": self.viewport,
            "diff": self.diff,
            "history": self.history,
            "serialize": self.serialize,
            "restore": self.restore,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # build: accept root or spec, run normalize+measure+solve+layout
    # ------------------------------------------------------------------
    def build(self, params):
        root = self._p(params, "root")
        spec = self._p(params, "spec")
        width = self._p(params, "width", self.state["config"]["width"])
        height = self._p(params, "height", self.state["config"]["height"])
        bp = {"width": width, "height": height}
        if root is not None:
            bp["root"] = root
        elif spec is not None:
            bp["spec"] = spec
        else:
            return (0, None, ("missing_param", "build requires root or spec", 0))
        ok, data, err = self.state["lifecycle"].Run("run", bp)
        if not ok:
            return (0, None, err)
        return (1, self.state["lifecycle"].state["root"], None)

    # ------------------------------------------------------------------
    # render: dispatch on target
    # ------------------------------------------------------------------
    def render(self, params):
        target = self._p(params, "target", self.state["config"]["target"])
        if target == Config.TARGET_TERMINAL:
            return self.render_terminal(params)
        if target == Config.TARGET_QT:
            return self.render_qt(params)
        return (0, None, ("unknown_target", "target must be 'terminal' or 'qt'", 0))

    def render_terminal(self, params):
        root = self._p(params, "root", self.state["lifecycle"].state["root"])
        if root is None:
            return (0, None, ("no_root", "build first", 0))
        ok, data, err = self.state["terminal_renderer"].Run("render", {"root": root})
        if not ok:
            return (0, None, err)
        self._clear_render_dirty(root)
        self.state["last_render"] = data
        return (1, data, None)

    def render_qt(self, params):
        root = self._p(params, "root", self.state["lifecycle"].state["root"])
        parent = self._p(params, "parent", None)
        if root is None:
            return (0, None, ("no_root", "build first", 0))
        ok, data, err = self.state["qt_renderer"].Run("render", {
            "root": root, "parent": parent,
        })
        if not ok:
            return (0, None, err)
        self._clear_render_dirty(root)
        self.state["last_render"] = data
        return (1, data, None)

    def _clear_render_dirty(self, root):
        ok, data, err = root.walk({"order": "pre"})
        if ok:
            for node in data:
                node.clear_dirty({"flags": Config.DIRTY_RENDER})

    # ------------------------------------------------------------------
    # invalidate: mark a node dirty + ancestors, re-run solve
    # ------------------------------------------------------------------
    def invalidate(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("missing_node", "invalidate requires {'node': LayoutNode}", 0))
        ok, data, err = self.state["lifecycle"].Run("invalidate", {
            "node": node, "flags": Config.DIRTY_ALL,
        })
        if not ok:
            return (0, None, err)
        # Re-run measure+solve on dirty tree
        width = self.state["config"]["width"]
        height = self.state["config"]["height"]
        self.state["lifecycle"].Run("measure", {"width": width, "height": height})
        self.state["lifecycle"].Run("solve", {"width": width, "height": height})
        self.state["lifecycle"].Run("layout", {})
        return (1, True, None)

    # ------------------------------------------------------------------
    # viewport: change width/height and re-solve
    # ------------------------------------------------------------------
    def viewport(self, params):
        width = self._p(params, "width")
        height = self._p(params, "height")
        if width is not None:
            self.state["config"]["width"] = width
        if height is not None:
            self.state["config"]["height"] = height
        root = self.state["lifecycle"].state["root"]
        if root is None:
            return (1, True, None)
        root.mark_dirty({"flags": Config.DIRTY_ALL})
        self.state["lifecycle"].Run("measure", {
            "width": self.state["config"]["width"],
            "height": self.state["config"]["height"],
        })
        self.state["lifecycle"].Run("solve", {
            "width": self.state["config"]["width"],
            "height": self.state["config"]["height"],
        })
        self.state["lifecycle"].Run("layout", {})
        return (1, True, None)

    # ------------------------------------------------------------------
    # diff: snapshot + diff the tree (for incremental reflow)
    # ------------------------------------------------------------------
    def diff(self, params):
        root = self._p(params, "root", self.state["lifecycle"].state["root"])
        if root is None:
            return (0, None, ("no_root", "build first", 0))
        action = self._p(params, "action", "snapshot")
        dd = self.state["dom_diff"]
        if action == "snapshot":
            ok, data, err = dd.Run("snapshot", {"root": root})
            if not ok:
                return (0, None, err)
            return (1, {"nodes_snapshotted": data}, None)
        if action == "diff":
            ok, data, err = dd.Run("diff", {})
            if not ok:
                return (0, None, err)
            return (1, data, None)
        if action == "changed":
            ok, data, err = dd.Run("changed_nodes", {})
            if not ok:
                return (0, None, err)
            return (1, data, None)
        if action == "commit":
            ok, data, err = dd.Run("commit", {})
            if not ok:
                return (0, None, err)
            return (1, True, None)
        return (0, None, ("unknown_action", "diff action: snapshot|diff|changed|commit", 0))

    # ------------------------------------------------------------------
    # history: record/undo/redo/replay layout mutations
    # ------------------------------------------------------------------
    def history(self, params):
        action = self._p(params, "action")
        dh = self.state["dom_history"]
        if action == "record":
            return dh.Run("record", params)
        if action == "undo":
            return dh.Run("undo", params)
        if action == "redo":
            return dh.Run("redo", params)
        if action == "replay":
            root = self._p(params, "root", self.state["lifecycle"].state["root"])
            if root is None:
                return (0, None, ("no_root", "build first", 0))
            return dh.Run("replay", {"root": root})
        if action == "state":
            return dh.Run("read_state", {})
        return (0, None, ("unknown_action", "history action: record|undo|redo|replay|state", 0))

    # ------------------------------------------------------------------
    # serialize: export tree as DB-ready event list
    # ------------------------------------------------------------------
    def serialize(self, params):
        return self.state["dom_history"].Run("serialize", params)

    # ------------------------------------------------------------------
    # restore: rebuild history from DB event list
    # ------------------------------------------------------------------
    def restore(self, params):
        return self.state["dom_history"].Run("restore", params)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        lc = self.state["lifecycle"]
        return (1, {
            "config": dict(self.state["config"]),
            "phase": lc.state["phase"],
            "has_root": lc.state["root"] is not None,
            "stats": dict(lc.state["stats"]),
            "has_last_render": self.state["last_render"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("width", "height", "target", "theme", "scale_x", "scale_y"):
            if k in params:
                self.state["config"][k] = params[k]
        if "width" in params or "height" in params:
            self.state["lifecycle"].Run("set_config", {
                "width": self.state["config"]["width"],
                "height": self.state["config"]["height"],
            })
            self.state["terminal_renderer"].Run("set_config", {
                "width": self.state["config"]["width"],
                "height": self.state["config"]["height"],
            })
        if "theme" in params:
            self.state["terminal_renderer"].Run("set_config", {
                "theme": self.state["config"]["theme"],
            })
        if "scale_x" in params or "scale_y" in params:
            self.state["qt_renderer"].Run("set_config", {
                "scale_x": self.state["config"]["scale_x"],
                "scale_y": self.state["config"]["scale_y"],
            })
        return (1, True, None)
