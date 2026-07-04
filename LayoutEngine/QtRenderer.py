#[@GHOST]{[@file<QtRenderer.py>][@domain<qt_render>][@role<qt_geometry_compile>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<renderer_qt>][@return<Tuple3>][@state<widgets,geometry>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/QtRenderer.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Qt renderer: compiles solved Layout Graph -> PyQt6 setGeometry calls. Lazy import so terminal path works headless.}
#[@CLASS]{QtRenderer — walks solved tree, builds QWidget per node, applies rect via setGeometry}
#[@METHOD]{Run dispatch: render, build_widget, geometry_for, read_state, set_config}

import logging

import Config
from LayoutNode import LayoutNode

log = logging.getLogger("LayoutQt")

# Lazy PyQt6 import — only needed when actually rendering to Qt
_QT = None


def _load_qt():
    global _QT
    if _QT is not None:
        return _QT
    try:
        from PyQt6 import QtWidgets, QtCore, QtGui
        _QT = (QtWidgets, QtCore, QtGui)
        return _QT
    except ImportError as e:
        log.warning("PyQt6 unavailable: %s", e)
        return None


class QtRenderer:
    """Compiles a solved Layout Graph into PyQt6 widgets + setGeometry calls.

    Both QtRenderer and TerminalRenderer consume the SAME solved tree —
    neither owns layout truth. This replaces "manual geometry mode" by
    driving Qt from the constraint solver's output rects.

    PyQt6 is imported lazily so the terminal path works headless without Qt.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "scale_x": p.get("scale_x", 1),   # cell -> px multiplier
                "scale_y": p.get("scale_y", 1),
                "parent_widget": p.get("parent_widget", None),
            },
            "widgets": {},   # nid -> QWidget
            "root_widget": None,
            "stats": {"nodes": 0, "built": 0},
            "qt_available": _load_qt() is not None,
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "render": self.render,
            "build_widget": self.build_widget,
            "geometry_for": self.geometry_for,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # render(root) -> root QWidget (with all children positioned)
    # ------------------------------------------------------------------
    def render(self, params):
        root = self._p(params, "root")
        parent = self._p(params, "parent", self.state["config"]["parent_widget"])
        if root is None:
            return (0, None, ("missing_root", "render requires {'root': LayoutNode}", 0))
        if not self.state["qt_available"]:
            return (0, None, ("no_qt", "PyQt6 not available; install PyQt6 to use QtRenderer", 0))
        rect = root.state["rect"]
        if rect is None:
            return (0, None, ("not_solved", "tree has no rects; run solver first", 0))
        ok, widget, err = self._build(root, parent)
        if not ok:
            return (0, None, err)
        self.state["root_widget"] = widget
        return (1, widget, None)

    # ------------------------------------------------------------------
    # build_widget(node) -> single QWidget for that node
    # ------------------------------------------------------------------
    def build_widget(self, params):
        node = self._p(params, "node")
        parent = self._p(params, "parent", None)
        if node is None:
            return (0, None, ("missing_node", "build_widget requires {'node': LayoutNode}", 0))
        if not self.state["qt_available"]:
            return (0, None, ("no_qt", "PyQt6 not available", 0))
        return self._build(node, parent)

    # ------------------------------------------------------------------
    # geometry_for(node) -> (x, y, w, h) in pixels
    # ------------------------------------------------------------------
    def geometry_for(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("missing_node", "geometry_for requires {'node': LayoutNode}", 0))
        rect = node.state["rect"]
        if rect is None:
            return (0, None, ("not_solved", "node has no rect", 0))
        sx = self.state["config"]["scale_x"]
        sy = self.state["config"]["scale_y"]
        return (1, (rect.x * sx, rect.y * sy, rect.w * sx, rect.h * sy), None)

    # ------------------------------------------------------------------
    # Core: recursively build widgets + apply geometry
    # ------------------------------------------------------------------
    def _build(self, node, parent):
        qt = _load_qt()
        if qt is None:
            return (0, None, ("no_qt", "PyQt6 not available", 0))
        QtWidgets, QtCore, QtGui = qt
        self.state["stats"]["nodes"] += 1
        kind = node.state["kind"]
        rect = node.state["rect"]
        sx = self.state["config"]["scale_x"]
        sy = self.state["config"]["scale_y"]
        px = rect.x * sx
        py = rect.y * sy
        pw = rect.w * sx
        ph = rect.h * sy

        # Pick widget class by kind
        if kind in (Config.KIND_ROW, Config.KIND_COLUMN, Config.KIND_CONTAINER):
            widget = QtWidgets.QWidget(parent)
        elif kind == Config.KIND_BLOCK:
            widget = QtWidgets.QGroupBox(node.state["meta"].get("title", ""), parent)
        elif kind == Config.KIND_TEXT:
            widget = QtWidgets.QLabel(str(node.state["content"] or ""), parent)
        elif kind == Config.KIND_TABLE:
            tw = QtWidgets.QTableWidget(parent)
            meta = node.state["meta"]
            headers = meta.get("headers", [])
            rows = node.state["content"] or []
            tw.setColumnCount(len(headers))
            tw.setRowCount(len(rows) if isinstance(rows, list) else 0)
            tw.setHorizontalHeaderLabels([str(h) for h in headers])
            if isinstance(rows, list):
                for r, row in enumerate(rows):
                    if not isinstance(row, (list, tuple)):
                        row = [row]
                    for c, val in enumerate(row):
                        if c < len(headers):
                            item = QtWidgets.QTableWidgetItem(str(val))
                            tw.setItem(r, c, item)
            widget = tw
        elif kind == Config.KIND_TREE:
            tw = QtWidgets.QTreeWidget(parent)
            tw.setHeaderLabel(str(node.state["meta"].get("root_label", "")))
            for ch in node.state["children"]:
                label = ch.state["meta"].get("label", str(ch.state["content"] or ""))
                item = QtWidgets.QTreeWidgetItem([str(label)])
                for gc in ch.state["children"]:
                    glabel = gc.state["meta"].get("label", str(gc.state["content"] or ""))
                    child_item = QtWidgets.QTreeWidgetItem([str(glabel)])
                    item.addChild(child_item)
                tw.addTopLevelItem(item)
            widget = tw
        elif kind == Config.KIND_PIPELINE:
            widget = QtWidgets.QWidget(parent)
        elif kind == Config.KIND_SPACER:
            widget = QtWidgets.QWidget(parent)
        elif kind == Config.KIND_DIVIDER:
            line = QtWidgets.QFrame(parent)
            line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            widget = line
        else:
            widget = QtWidgets.QWidget(parent)

        widget.setGeometry(QtCore.QRect(px, py, pw, ph))
        self.state["widgets"][node.state["nid"]] = widget
        self.state["stats"]["built"] += 1

        # Recurse children — they become children of this widget
        for ch in node.state["children"]:
            ok, cw, err = self._build(ch, widget)
            if not ok:
                log.warning("child build failed for %s: %s", ch.state["nid"], err)
        return (1, widget, None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
            "qt_available": self.state["qt_available"],
            "widget_count": len(self.state["widgets"]),
            "has_root_widget": self.state["root_widget"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("scale_x", "scale_y", "parent_widget"):
            if k in params:
                self.state["config"][k] = params[k]
        return (1, True, None)
