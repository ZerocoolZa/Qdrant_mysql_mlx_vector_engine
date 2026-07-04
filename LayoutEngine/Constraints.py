#[@GHOST]{[@file<Constraints.py>][@domain<layout_solver>][@role<constraint_resolution>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<solver>][@return<Tuple3>][@state<solver,results>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/Constraints.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Constraint model + flexbox/CSS-grid solver — pure function of (node tree, available size) -> assigned rects}
#[@CLASS]{ConstraintSolver — resolves weights, min/max, priority, overflow; assigns rects to every node}
#[@METHOD]{Run dispatch: solve, solve_node, measure, read_state, set_config}

import Config
from LayoutNode import (
    LayoutNode, ContainerNode, RowNode, ColumnNode, BlockNode,
    WidgetNode, TextNode, SpacerNode, DividerNode,
)


class Rect:
    """Immutable-ish layout rectangle assigned to a node after solve."""

    def __init__(self, x=0, y=0, w=0, h=0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def to_dict(self):
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    def __repr__(self):
        return "Rect(x=%d, y=%d, w=%d, h=%d)" % (self.x, self.y, self.w, self.h)


class Measure:
    """Intrinsic size result for a node (what it WANTS if unconstrained)."""

    def __init__(self, w=0, h=0, min_w=0, min_h=0, max_w=None, max_h=None):
        self.w = w
        self.h = h
        self.min_w = min_w
        self.min_h = min_h
        self.max_w = max_w if max_w is not None else Config.MAX_SIZE_DEFAULT
        self.max_h = max_h if max_h is not None else Config.MAX_SIZE_DEFAULT

    def to_dict(self):
        return {
            "w": self.w, "h": self.h,
            "min_w": self.min_w, "min_h": self.min_h,
            "max_w": self.max_w, "max_h": self.max_h,
        }


class ConstraintSolver:
    """Mini flexbox + CSS-grid constraint solver.

    Pipeline per node:
      1. measure  — intrinsic desired size (recursively from children)
      2. resolve  — distribute available main-axis size by weight/flex,
                     enforce min/max, handle overflow strategy
      3. position — place children along cross axis per align/justify

    Pure: reads node tree + available size, writes Rect into node.state["rect"]
    and Measure into node.state["measure"]. No rendering, no Qt, no terminal.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "overflow": p.get("overflow", Config.OVERFLOW_STRATEGY),
                "cache": p.get("cache", Config.CACHE_ENABLED),
            },
            "results": {},
            "stats": {"measured": 0, "solved": 0, "cached_hits": 0},
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "solve": self.solve,
            "solve_node": self.solve_node,
            "measure": self.measure,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # Public entry: solve a whole tree against a viewport
    # ------------------------------------------------------------------
    def solve(self, params):
        root = self._p(params, "root")
        width = self._p(params, "width", Config.DEFAULT_TERM_WIDTH)
        height = self._p(params, "height", Config.DEFAULT_TERM_HEIGHT)
        if root is None:
            return (0, None, ("missing_root", "solve requires {'root': LayoutNode}", 0))
        avail = Rect(0, 0, width, height)
        self._solve_node(root, avail)
        self.state["stats"]["solved"] += 1
        return (1, root, None)

    def solve_node(self, params):
        node = self._p(params, "node")
        avail = self._p(params, "avail")
        if node is None or avail is None:
            return (0, None, ("missing_param", "solve_node requires node + avail", 0))
        if isinstance(avail, dict):
            avail = Rect(avail.get("x", 0), avail.get("y", 0),
                         avail.get("w", 0), avail.get("h", 0))
        self._solve_node(node, avail)
        return (1, node, None)

    # ------------------------------------------------------------------
    # Measure: intrinsic desired size (bottom-up)
    # ------------------------------------------------------------------
    def measure(self, params):
        node = self._p(params, "node")
        max_w = self._p(params, "max_w", Config.MAX_SIZE_DEFAULT)
        max_h = self._p(params, "max_h", Config.MAX_SIZE_DEFAULT)
        if node is None:
            return (0, None, ("missing_node", "measure requires {'node': LayoutNode}", 0))
        m = self._measure(node, max_w, max_h)
        node.state["measure"] = m
        self.state["stats"]["measured"] += 1
        return (1, m.to_dict(), None)

    def _measure(self, node, max_w, max_h):
        c = node.state["constraints"]
        kind = node.state["kind"]
        children = node.state["children"]

        # Leaf-ish nodes: derive intrinsic size from content or constraints
        if not children:
            content = node.state["content"]
            if kind == Config.KIND_TEXT and content is not None:
                text = content if isinstance(content, str) else str(content)
                lines = text.split("\n")
                w = 0
                h = 0
                for ln in lines:
                    lw = _visible_width(ln)
                    if lw > w:
                        w = lw
                    h += 1
                w = max(w, c["min_w"])
                h = max(h, c["min_h"])
                return Measure(w, h, c["min_w"], c["min_h"], c["max_w"], c["max_h"])
            if kind == Config.KIND_SPACER:
                return Measure(c["min_w"], c["min_h"], c["min_w"], c["min_h"],
                               c["max_w"], c["max_h"])
            if kind == Config.KIND_DIVIDER:
                return Measure(c["min_w"], 1, c["min_w"], 1, c["max_w"], c["max_h"])
            # Generic leaf widget: use constraints as intrinsic
            iw = c["min_w"] if c["min_w"] > 0 else 0
            ih = c["min_h"] if c["min_h"] > 0 else 1
            return Measure(iw, ih, c["min_w"], c["min_h"], c["max_w"], c["max_h"])

        # Container: aggregate children
        direction = node.state["style"]["direction"]
        is_row = direction in ("row", "row-reverse")
        child_measures = []
        for ch in children:
            cm = self._measure(ch, max_w, max_h)
            ch.state["measure"] = cm
            self.state["stats"]["measured"] += 1
            child_measures.append(cm)

        if is_row:
            total_w = 0
            max_h_inner = 0
            for cm in child_measures:
                total_w += cm.w
                if cm.h > max_h_inner:
                    max_h_inner = cm.h
            gutter = node.state["style"]["gutter"]
            total_w += max(0, len(child_measures) - 1) * gutter
            iw = max(total_w, c["min_w"])
            ih = max(max_h_inner, c["min_h"])
        else:
            total_h = 0
            max_w_inner = 0
            for cm in child_measures:
                total_h += cm.h
                if cm.w > max_w_inner:
                    max_w_inner = cm.w
            gutter = node.state["style"]["gutter"]
            total_h += max(0, len(child_measures) - 1) * gutter
            iw = max(max_w_inner, c["min_w"])
            ih = max(total_h, c["min_h"])

        iw = min(iw, c["max_w"])
        ih = min(ih, c["max_h"])
        return Measure(iw, ih, c["min_w"], c["min_h"], c["max_w"], c["max_h"])

    # ------------------------------------------------------------------
    # Solve: top-down assign rects
    # ------------------------------------------------------------------
    def _solve_node(self, node, avail):
        c = node.state["constraints"]
        kind = node.state["kind"]
        children = node.state["children"]

        # Clamp the node's own rect to available + min/max
        w = avail.w
        h = avail.h
        if w > c["max_w"]:
            w = c["max_w"]
        if w < c["min_w"]:
            w = c["min_w"]
        if h > c["max_h"]:
            h = c["max_h"]
        if h < c["min_h"]:
            h = c["min_h"]
        if w < 0:
            w = 0
        if h < 0:
            h = 0
        rect = Rect(avail.x, avail.y, w, h)
        node.state["rect"] = rect

        if not children:
            return rect

        direction = node.state["style"]["direction"]
        is_row = direction in ("row", "row-reverse")
        gutter = node.state["style"]["gutter"]
        padding = node.state["style"]["padding"]
        justify = node.state["style"]["justify"]
        align = node.state["style"]["align"]
        overflow = node.state["style"]["overflow"]

        # Inner box after padding
        inner_x = rect.x + padding
        inner_y = rect.y + padding
        inner_w = rect.w - 2 * padding
        inner_h = rect.h - 2 * padding
        if inner_w < 0:
            inner_w = 0
        if inner_h < 0:
            inner_h = 0

        if is_row:
            self._solve_row(node, children, inner_x, inner_y, inner_w, inner_h,
                            gutter, justify, align, overflow, direction)
        else:
            self._solve_col(node, children, inner_x, inner_y, inner_w, inner_h,
                            gutter, justify, align, overflow, direction)
        return rect

    # ------------------------------------------------------------------
    # Row solver (main axis = horizontal)
    # ------------------------------------------------------------------
    def _solve_row(self, node, children, x, y, w, h, gutter, justify, align,
                   overflow, direction):
        n = len(children)
        if n == 0:
            return
        total_gutter = (n - 1) * gutter
        avail_main = w - total_gutter
        if avail_main < 0:
            avail_main = 0

        # Phase 1: give every child its min size; collect flex
        sizes = []
        flex_grow = []
        flex_shrink = []
        for ch in children:
            cm = ch.state["measure"]
            if cm is None:
                cm = self._measure(ch, w, h)
                ch.state["measure"] = cm
            mn = cm.min_w
            sizes.append(mn)
            flex_grow.append(ch.state["constraints"]["flex_grow"])
            flex_shrink.append(ch.state["constraints"]["flex_shrink"])

        used = sum(sizes)
        free = avail_main - used

        if free > 0:
            # Grow: distribute by flex_grow (fallback to weight)
            total_grow = 0.0
            for i, ch in enumerate(children):
                fg = flex_grow[i]
                if fg <= 0:
                    fg = ch.state["constraints"]["weight"]
                total_grow += fg
            if total_grow > 0:
                for i, ch in enumerate(children):
                    fg = flex_grow[i]
                    if fg <= 0:
                        fg = ch.state["constraints"]["weight"]
                    sizes[i] += int(free * fg / total_grow)
        elif free < 0 and overflow == "shrink":
            # Shrink: distribute negative by flex_shrink
            total_shrink = sum(flex_shrink)
            if total_shrink > 0:
                deficit = -free
                for i in range(n):
                    sizes[i] -= int(deficit * flex_shrink[i] / total_shrink)

        # Phase 2: enforce max on each, redistribute leftover
        for i, ch in enumerate(children):
            cm = ch.state["measure"]
            if sizes[i] > cm.max_w:
                sizes[i] = cm.max_w
            if sizes[i] < cm.min_w:
                sizes[i] = cm.min_w

        # Phase 3: justify positioning along main axis
        total_used = sum(sizes) + total_gutter
        leading = 0
        between = gutter
        gap = w - total_used
        if gap > 0:
            if justify == "center":
                leading = gap // 2
            elif justify == "end":
                leading = gap
            elif justify == "between":
                if n > 1:
                    between = gutter + gap // (n - 1)
            elif justify == "around":
                if n > 0:
                    leading = gap // (2 * n)
                    between = gutter + gap // n
            elif justify == "evenly":
                if n > 0:
                    leading = gap // (n + 1)
                    between = gutter + gap // (n + 1)

        # Phase 4: place children
        cx = x + leading
        order = range(n)
        if direction == "row-reverse":
            order = list(reversed(order))
        for i in order:
            ch = children[i]
            cm = ch.state["measure"]
            child_w = sizes[i]
            child_h = h
            if child_h > cm.max_h:
                child_h = cm.max_h
            if child_h < cm.min_h:
                child_h = cm.min_h
            # Cross-axis align
            cy = y
            if align == "center":
                cy = y + (h - child_h) // 2
            elif align == "end":
                cy = y + (h - child_h)
            # align == stretch -> child_h stays h (already)
            child_avail = Rect(cx, cy, child_w, child_h)
            self._solve_node(ch, child_avail)
            cx += child_w + between

    # ------------------------------------------------------------------
    # Column solver (main axis = vertical)
    # ------------------------------------------------------------------
    def _solve_col(self, node, children, x, y, w, h, gutter, justify, align,
                   overflow, direction):
        n = len(children)
        if n == 0:
            return
        total_gutter = (n - 1) * gutter
        avail_main = h - total_gutter
        if avail_main < 0:
            avail_main = 0

        sizes = []
        flex_grow = []
        flex_shrink = []
        for ch in children:
            cm = ch.state["measure"]
            if cm is None:
                cm = self._measure(ch, w, h)
                ch.state["measure"] = cm
            mn = cm.min_h
            sizes.append(mn)
            flex_grow.append(ch.state["constraints"]["flex_grow"])
            flex_shrink.append(ch.state["constraints"]["flex_shrink"])

        used = sum(sizes)
        free = avail_main - used

        if free > 0:
            total_grow = 0.0
            for i, ch in enumerate(children):
                fg = flex_grow[i]
                if fg <= 0:
                    fg = ch.state["constraints"]["weight"]
                total_grow += fg
            if total_grow > 0:
                for i, ch in enumerate(children):
                    fg = flex_grow[i]
                    if fg <= 0:
                        fg = ch.state["constraints"]["weight"]
                    sizes[i] += int(free * fg / total_grow)
        elif free < 0 and overflow == "shrink":
            total_shrink = sum(flex_shrink)
            if total_shrink > 0:
                deficit = -free
                for i in range(n):
                    sizes[i] -= int(deficit * flex_shrink[i] / total_shrink)

        for i, ch in enumerate(children):
            cm = ch.state["measure"]
            if sizes[i] > cm.max_h:
                sizes[i] = cm.max_h
            if sizes[i] < cm.min_h:
                sizes[i] = cm.min_h

        total_used = sum(sizes) + total_gutter
        leading = 0
        between = gutter
        gap = h - total_used
        if gap > 0:
            if justify == "center":
                leading = gap // 2
            elif justify == "end":
                leading = gap
            elif justify == "between":
                if n > 1:
                    between = gutter + gap // (n - 1)
            elif justify == "around":
                if n > 0:
                    leading = gap // (2 * n)
                    between = gutter + gap // n
            elif justify == "evenly":
                if n > 0:
                    leading = gap // (n + 1)
                    between = gutter + gap // (n + 1)

        cy = y + leading
        order = range(n)
        if direction == "column-reverse":
            order = list(reversed(order))
        for i in order:
            ch = children[i]
            cm = ch.state["measure"]
            child_h = sizes[i]
            child_w = w
            if child_w > cm.max_w:
                child_w = cm.max_w
            if child_w < cm.min_w:
                child_w = cm.min_w
            cx = x
            if align == "center":
                cx = x + (w - child_w) // 2
            elif align == "end":
                cx = x + (w - child_w)
            child_avail = Rect(cx, cy, child_w, child_h)
            self._solve_node(ch, child_avail)
            cy += child_h + between

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        self.state["config"].update(params)
        return (1, True, None)


# ---------------------------------------------------------------------------
# Text width helpers (CJK-aware) — used by measure
# ---------------------------------------------------------------------------

def _visible_width(text):
    """Visible width of a string ignoring ANSI escapes, CJK-aware."""
    if text is None:
        return 0
    s = text
    width = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\x1b":
            # skip ANSI escape sequence
            i += 1
            while i < n and s[i] not in ("m", "H", "J", "K", "A", "B", "C", "D"):
                i += 1
            i += 1
            continue
        if ch == "\t":
            width += Config.TAB_WIDTH
        elif ch == "\r":
            pass
        else:
            cp = ord(ch)
            width += _char_width(cp)
        i += 1
    return width


def _char_width(cp):
    if cp < 0x20:
        return 0
    for lo, hi in Config.CJK_WIDE_RANGES:
        if lo <= cp <= hi:
            return 2
    return 1
