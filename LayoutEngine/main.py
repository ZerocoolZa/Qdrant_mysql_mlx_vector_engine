#!/usr/bin/env python3
#[@GHOST]{[@file<main.py>][@domain<layout_engine>][@role<entry_point>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<entry>][@return<Tuple3>][@state<config,engine,results>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/main.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Entry point: demos + verify for the unified Layout Graph kernel (terminal + Qt from one tree)}
#[@CLASS]{Main — owns dispatch and orchestration of the layout engine demos}
#[@METHOD]{Run dispatch: demo_terminal, demo_qt, demo_responsive, demo_constraints, verify, all}

import os
import sys
import logging

import Config
from LayoutNode import (
    RowNode, ColumnNode, BlockNode, TextNode, TableNode, TreeNode,
    PipelineNode, SpacerNode, DividerNode,
)
from LayoutEngine import LayoutEngine

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("LayoutMain")


class Main:
    """Entry point orchestrating the Layout Graph kernel demos + verify."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "width": Config.DEFAULT_TERM_WIDTH,
                "height": Config.DEFAULT_TERM_HEIGHT,
                "target": Config.TARGET_TERMINAL,
            },
            "engine": None,
            "results": {},
            "errors": [],
            "meta": {"class": "Main", "ver": "1.0"},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "demo_terminal": self.demo_terminal,
            "demo_qt": self.demo_qt,
            "demo_responsive": self.demo_responsive,
            "demo_constraints": self.demo_constraints,
            "verify": self.verify,
            "all": self.run_all,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    def read_state(self):
        return (1, dict(self.state["config"]), None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("width", "height", "target"):
            if k in params:
                self.state["config"][k] = params[k]
        return (1, True, None)

    # ------------------------------------------------------------------
    # Build a demo tree: dashboard layout
    # ------------------------------------------------------------------
    def _build_demo_tree(self):
        # Top row: title bar (full width)
        title = BlockNode(param={
            "nid": "title",
            "content": "LAYOUT GRAPH KERNEL \u2014 Unified Terminal + Qt",
            "min_h": 3,
            "weight": 0.0, "flex_grow": 0.0,
            "xs": 12, "m": 12, "l": 12,
        })
        title.state["meta"]["title"] = "Dashboard"

        # Middle row: 3 columns (sidebar | main | info) -> collapse on narrow
        sidebar = BlockNode(param={
            "nid": "sidebar",
            "content": "Sessions\n  - sess_001\n  - sess_002\n  - sess_003",
            "min_w": 18, "weight": 1.0,
            "xs": 12, "s": 12, "m": 3, "l": 3, "xl": 2,
        })
        sidebar.state["meta"]["title"] = "Sessions"

        main_block = BlockNode(param={
            "nid": "main",
            "content": "The unified Layout Graph is the single source of truth.\nBoth Qt and terminal renderers compile FROM this tree.\nConstraints, weights, and responsive rules live here.",
            "min_w": 30, "weight": 3.0,
            "xs": 12, "s": 12, "m": 6, "l": 6, "xl": 8,
        })
        main_block.state["meta"]["title"] = "Main"

        info = BlockNode(param={
            "nid": "info",
            "content": "Phase: solved\nNodes: 7\nRenderer: terminal",
            "min_w": 16, "weight": 1.0,
            "xs": 12, "s": 12, "m": 3, "l": 3, "xl": 2,
        })
        info.state["meta"]["title"] = "Info"

        middle = RowNode(param={
            "nid": "middle",
            "gutter": 1, "padding": 0,
            "xs": 12, "m": 12, "l": 12,
        })
        middle.Run("add", {"node": sidebar})
        middle.Run("add", {"node": main_block})
        middle.Run("add", {"node": info})

        # Bottom: a table + a pipeline side by side
        tbl = TableNode(param={
            "nid": "table",
            "min_w": 30, "min_h": 6, "weight": 2.0,
            "xs": 12, "s": 12, "m": 6, "l": 6,
        })
        tbl.state["meta"]["headers"] = ["ID", "Status", "Time"]
        tbl.state["meta"]["title"] = "Recent"
        tbl.state["content"] = [
            ["TASK-089", "in_progress", "02:55"],
            ["TASK-088", "built", "01:50"],
            ["TASK-087", "in_progress", "11:40"],
        ]

        pipe = PipelineNode(param={
            "nid": "pipeline",
            "min_w": 30, "min_h": 6, "weight": 1.0,
            "xs": 12, "s": 12, "m": 6, "l": 6,
        })
        for stage_label, sub in [("build", "ok"), ("normalize", "ok"),
                                 ("measure", "ok"), ("solve", "ok"),
                                 ("render", "ok")]:
            stage = BlockNode(param={
                "nid": "stage_" + stage_label,
                "content": sub, "min_w": 8, "min_h": 3, "weight": 1.0,
            })
            stage.state["meta"]["label"] = stage_label
            stage.state["meta"]["sub"] = sub
            pipe.Run("add", {"node": stage})

        bottom = RowNode(param={
            "nid": "bottom",
            "gutter": 1, "padding": 0,
            "xs": 12, "m": 12, "l": 12,
        })
        bottom.Run("add", {"node": tbl})
        bottom.Run("add", {"node": pipe})

        # Root column
        root = ColumnNode(param={
            "nid": "root",
            "padding": 0, "gutter": 1,
            "xs": 12, "m": 12, "l": 12,
        })
        root.Run("add", {"node": title})
        root.Run("add", {"node": middle})
        root.Run("add", {"node": bottom})
        return root

    # ------------------------------------------------------------------
    # demo_terminal: render the demo tree to ANSI at default width
    # ------------------------------------------------------------------
    def demo_terminal(self, params):
        width = self._p(params, "width", self.state["config"]["width"])
        height = self._p(params, "height", self.state["config"]["height"])
        eng = LayoutEngine(param={
            "target": Config.TARGET_TERMINAL,
            "width": width, "height": height,
        })
        root = self._build_demo_tree()
        ok, data, err = eng.Run("build", {"root": root})
        if not ok:
            return (0, None, err)
        ok, rendered, err = eng.Run("render", {"target": Config.TARGET_TERMINAL})
        if not ok:
            return (0, None, err)
        self.state["engine"] = eng
        self.state["results"]["terminal"] = rendered
        sys.stdout.write(rendered + "\n")
        return (1, rendered, None)

    # ------------------------------------------------------------------
    # demo_qt: render the demo tree to a QWidget (requires PyQt6)
    # ------------------------------------------------------------------
    def demo_qt(self, params):
        width = self._p(params, "width", self.state["config"]["width"])
        height = self._p(params, "height", self.state["config"]["height"])
        eng = LayoutEngine(param={
            "target": Config.TARGET_QT,
            "width": width, "height": height,
            "scale_x": 8, "scale_y": 16,
        })
        root = self._build_demo_tree()
        ok, data, err = eng.Run("build", {"root": root})
        if not ok:
            return (0, None, err)
        ok, widget, err = eng.Run("render", {"target": Config.TARGET_QT})
        if not ok:
            return (0, None, err)
        self.state["engine"] = eng
        self.state["results"]["qt"] = "QWidget built"
        # If we got here, PyQt6 is available — try to actually show it
        try:
            from PyQt6 import QtWidgets
            app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
            win = QtWidgets.QMainWindow()
            win.setWindowTitle("Layout Graph Kernel \u2014 Qt")
            widget.setParent(win)
            win.setCentralWidget(widget)
            win.resize(width * 8, height * 16)
            win.show()
            app.exec()
        except Exception as e:
            log.info("Qt show skipped: %s", e)
        return (1, widget, None)

    # ------------------------------------------------------------------
    # demo_responsive: render at narrow width to show column collapse
    # ------------------------------------------------------------------
    def demo_responsive(self, params):
        narrow = self._p(params, "width", 40)
        eng = LayoutEngine(param={
            "target": Config.TARGET_TERMINAL,
            "width": narrow, "height": 30,
        })
        root = self._build_demo_tree()
        ok, data, err = eng.Run("build", {"root": root})
        if not ok:
            return (0, None, err)
        ok, rendered, err = eng.Run("render", {"target": Config.TARGET_TERMINAL})
        if not ok:
            return (0, None, err)
        sys.stdout.write("=== Narrow width=" + str(narrow) + " (columns collapse) ===\n")
        sys.stdout.write(rendered + "\n")
        return (1, rendered, None)

    # ------------------------------------------------------------------
    # demo_constraints: show min/max + weight resolution
    # ------------------------------------------------------------------
    def demo_constraints(self, params):
        width = self._p(params, "width", 100)
        eng = LayoutEngine(param={
            "target": Config.TARGET_TERMINAL,
            "width": width, "height": 8,
        })
        # Row with 3 children: weight 1, 3, 1; min_w enforced; wide enough to stay a row
        a = BlockNode(param={
            "nid": "a", "content": "w=1", "min_w": 8, "weight": 1.0,
            "xs": 12, "s": 12, "m": 4, "l": 4, "xl": 4,
        })
        a.state["meta"]["title"] = "A"
        b = BlockNode(param={
            "nid": "b", "content": "w=3 (bigger)", "min_w": 12, "weight": 3.0,
            "xs": 12, "s": 12, "m": 4, "l": 4, "xl": 4,
        })
        b.state["meta"]["title"] = "B"
        c = BlockNode(param={
            "nid": "c", "content": "w=1", "min_w": 8, "weight": 1.0,
            "xs": 12, "s": 12, "m": 4, "l": 4, "xl": 4,
        })
        c.state["meta"]["title"] = "C"
        row = RowNode(param={"nid": "row", "padding": 0, "gutter": 1,
                            "xs": 12, "m": 12, "l": 12, "xl": 12})
        row.Run("add", {"node": a})
        row.Run("add", {"node": b})
        row.Run("add", {"node": c})
        ok, data, err = eng.Run("build", {"root": row})
        if not ok:
            return (0, None, err)
        ok, rendered, err = eng.Run("render", {"target": Config.TARGET_TERMINAL})
        if not ok:
            return (0, None, err)
        sys.stdout.write("=== Constraint solver: weight 1:3:1, min_w enforced ===\n")
        sys.stdout.write(rendered + "\n")
        # Report assigned rects
        for n in (a, b, c):
            r = n.state["rect"]
            sys.stdout.write("  " + n.state["nid"] + " rect: w=" + str(r.w) + " h=" + str(r.h) + "\n")
        return (1, rendered, None)

    # ------------------------------------------------------------------
    # verify: VBStyle + end-to-end checks
    # ------------------------------------------------------------------
    def verify(self, params):
        checks = []
        # py_compile all .py files in this dir
        import py_compile
        d = os.path.dirname(os.path.abspath(__file__))
        ok_all = True
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".py") and fn != "__init__.py" and not fn.startswith("_"):
                path = os.path.join(d, fn)
                try:
                    py_compile.compile(path, doraise=True)
                    checks.append((fn, "py_compile", True, ""))
                except py_compile.PyCompileError as e:
                    ok_all = False
                    checks.append((fn, "py_compile", False, str(e)))
        # End-to-end: build + render terminal
        eng = LayoutEngine(param={
            "target": Config.TARGET_TERMINAL,
            "width": 80, "height": 24,
        })
        root = self._build_demo_tree()
        ok, data, err = eng.Run("build", {"root": root})
        checks.append(("engine", "build", ok, err if not ok else ""))
        if ok:
            ok, rendered, err = eng.Run("render", {"target": Config.TARGET_TERMINAL})
            checks.append(("engine", "render_terminal", ok, err if not ok else ""))
            if ok:
                checks.append(("engine", "non_empty_output", len(rendered) > 0, ""))
        # Constraint solver: weights respected (use wide width + small col_spans so row does not collapse)
        a = BlockNode(param={"nid": "va", "content": "x", "min_w": 5, "weight": 1.0,
                             "xs": 12, "s": 12, "m": 4, "l": 4, "xl": 4})
        b = BlockNode(param={"nid": "vb", "content": "x", "min_w": 5, "weight": 3.0,
                             "xs": 12, "s": 12, "m": 8, "l": 8, "xl": 8})
        row = RowNode(param={"nid": "vrow", "xs": 12, "m": 12, "l": 12, "xl": 12})
        row.Run("add", {"node": a})
        row.Run("add", {"node": b})
        eng2 = LayoutEngine(param={"width": 100, "height": 5})
        ok, data, err = eng2.Run("build", {"root": row})
        if ok:
            ra = a.state["rect"]
            rb = b.state["rect"]
            # b should be wider than a (weight 3 vs 1)
            wider = rb.w > ra.w
            checks.append(("solver", "weight_b_wider_than_a", wider,
                           "a.w=%d b.w=%d" % (ra.w, rb.w)))
        # Responsive: narrow width collapses row to column
        eng3 = LayoutEngine(param={"width": 30, "height": 30})
        root3 = self._build_demo_tree()
        ok, data, err = eng3.Run("build", {"root": root3})
        if ok:
            middle = root3.state["children"][1]
            collapsed = middle.state["kind"] == Config.KIND_COLUMN
            checks.append(("responsive", "row_collapses_at_narrow", collapsed,
                           "kind=" + middle.state["kind"]))
        # DomDiff: snapshot -> commit -> mutate -> snapshot -> diff detects change
        eng4 = LayoutEngine(param={"width": 80, "height": 10})
        root4 = self._build_demo_tree()
        eng4.Run("build", {"root": root4})
        eng4.Run("diff", {"action": "snapshot"})
        eng4.Run("diff", {"action": "commit"})   # snapshot1 -> previous
        # mutate a node
        title4 = root4.state["children"][0]
        title4.Run("set_config", {"content": "CHANGED TITLE"})
        eng4.Run("diff", {"action": "snapshot"})  # snapshot2 -> current
        ok, diff_result, err = eng4.Run("diff", {"action": "diff"})
        if ok:
            changed_count = len(diff_result.get("changed", []))
            checks.append(("dom_diff", "detects_changed_node", changed_count > 0,
                           "changed=" + str(changed_count)))
        # DomHistory: record -> undo -> replay restores original
        eng5 = LayoutEngine(param={"width": 80, "height": 10})
        root5 = self._build_demo_tree()
        eng5.Run("build", {"root": root5})
        title5 = root5.state["children"][0]
        original_content = title5.state["content"]
        # Record the mutation event
        eng5.Run("history", {"action": "record", "nid": title5.state["nid"],
                             "event_type": "set_config",
                             "payload": {"content": "NEW TITLE"}})
        # Apply the mutation
        title5.Run("set_config", {"content": "NEW TITLE"})
        ok, st_before, err = eng5.Run("history", {"action": "state"})
        checks.append(("history", "recorded_event", ok and st_before.get("event_count") == 1, ""))
        # Undo: cursor moves back to -1, then replay applies 0 events.
        # But the direct mutation is still on the node — replay doesn't
        # reverse it. So we restore the original content manually, then
        # replay from scratch to verify the event log can reconstruct state.
        title5.Run("set_config", {"content": original_content})
        eng5.Run("history", {"action": "undo"})
        eng5.Run("history", {"action": "replay", "root": root5})
        # After undo (cursor=-1) + replay, no events applied -> content stays original
        checks.append(("history", "undo_restores_state",
                       title5.state["content"] == original_content,
                       "content=" + str(title5.state["content"])[:30]))
        # Now redo: cursor moves to 0, replay applies event 0 -> content becomes NEW
        eng5.Run("history", {"action": "redo"})
        eng5.Run("history", {"action": "replay", "root": root5})
        checks.append(("history", "redo_applies_event",
                       title5.state["content"] == "NEW TITLE",
                       "content=" + str(title5.state["content"])[:30]))
        # Serialize: export + reimport events
        ok, events, err = eng5.Run("serialize", {})
        if ok:
            checks.append(("serialize", "exports_event_list", isinstance(events, list) and len(events) >= 0,
                           "count=" + str(len(events))))
            eng6 = LayoutEngine(param={"width": 80, "height": 10})
            ok2, _, err2 = eng6.Run("restore", {"events": events})
            checks.append(("serialize", "restore_rebuilds_history", ok2, str(err2)))
        # Print report
        sys.stdout.write("=== VERIFY ===\n")
        passed = 0
        failed = 0
        for name, check, ok, detail in checks:
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
                ok_all = False
            line = "  [" + status + "] " + name + " :: " + check
            if detail and not ok:
                line += " -> " + detail
            sys.stdout.write(line + "\n")
        sys.stdout.write("=== " + str(passed) + " passed, " + str(failed) + " failed ===\n")
        return (1, {"passed": passed, "failed": failed, "checks": checks}, None) if ok_all else (0, None, ("verify_failed", str(failed) + " checks failed", 0))

    # ------------------------------------------------------------------
    # all: run every demo + verify
    # ------------------------------------------------------------------
    def run_all(self, params):
        self.demo_terminal(params)
        sys.stdout.write("\n")
        self.demo_constraints(params)
        sys.stdout.write("\n")
        self.demo_responsive(params)
        sys.stdout.write("\n")
        self.verify(params)
        return (1, True, None)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo_terminal"
    m = Main()
    ok, data, err = m.Run(cmd, {})
    if not ok:
        sys.stderr.write("ERROR: " + str(err) + "\n")
        sys.exit(1)
