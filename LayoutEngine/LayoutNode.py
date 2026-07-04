#[@GHOST]{[@file<LayoutNode.py>][@domain<layout_graph_dom>][@role<layout_truth>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<layout_dom>][@return<Tuple3>][@state<tree,nodes,root>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/LayoutNode.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Unified Layout Graph DOM — single source of truth for both Qt and terminal renderers}
#[@CLASS]{LayoutNode — base node; ContainerNode/RowNode/ColumnNode/BlockNode/WidgetNode/TextNode/TableNode/TreeNode/PipelineNode/SpacerNode/DividerNode}
#[@METHOD]{Run dispatch: add, remove, child, children, mark_dirty, clear_dirty, walk, measure_cache, layout_cache, read_state, set_config}

import Config


class LayoutNode:
    """Base node in the Layout Graph.

    Every node carries:
      - identity (nid, kind)
      - constraints (min_w, max_w, min_h, max_h, weight, flex_grow, flex_shrink, priority)
      - responsive spec (col_span per breakpoint)
      - style (align, justify, direction, wrap, padding, gutter, overflow)
      - dirty flag + cached measure + cached layout rect
      - parent / children tree

    This is the single source of truth. Neither Qt nor terminal owns layout;
    both compile FROM a solved LayoutNode tree.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "nid": p.get("nid"),
            "kind": p.get("kind", Config.KIND_CONTAINER),
            "parent": None,
            "children": [],
            "constraints": {
                "min_w": p.get("min_w", Config.MIN_SIZE_DEFAULT),
                "max_w": p.get("max_w", Config.MAX_SIZE_DEFAULT),
                "min_h": p.get("min_h", Config.MIN_SIZE_DEFAULT),
                "max_h": p.get("max_h", Config.MAX_SIZE_DEFAULT),
                "weight": p.get("weight", Config.WEIGHT_DEFAULT),
                "flex_grow": p.get("flex_grow", Config.FLEX_GROW_DEFAULT),
                "flex_shrink": p.get("flex_shrink", Config.FLEX_SHRINK_DEFAULT),
                "priority": p.get("priority", Config.PRIORITY_NORMAL),
            },
            "responsive": {
                "xs": p.get("xs", Config.GRID_COLUMNS),
                "s": p.get("s", None),
                "m": p.get("m", None),
                "l": p.get("l", None),
                "xl": p.get("xl", None),
            },
            "style": {
                "align": p.get("align", Config.ALIGN_DEFAULT),
                "justify": p.get("justify", Config.JUSTIFY_DEFAULT),
                "direction": p.get("direction", Config.DIRECTION_DEFAULT),
                "wrap": p.get("wrap", Config.WRAP_DEFAULT),
                "padding": p.get("padding", Config.PADDING_DEFAULT),
                "gutter": p.get("gutter", Config.GUTTER_DEFAULT),
                "overflow": p.get("overflow", Config.OVERFLOW_STRATEGY),
                "theme_key": p.get("theme_key", None),
            },
            "content": p.get("content", None),
            "meta": p.get("meta", {}),
            "dirty": Config.DIRTY_ALL,
            "measure": None,
            "rect": None,
            "render_cache": None,
            "memunit": mem,
            "dbunit": db,
        }
        if self.state["nid"] is None:
            self.state["nid"] = _next_nid()

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "add": self.add,
            "remove": self.remove,
            "child": self.child,
            "children": self.children,
            "mark_dirty": self.mark_dirty,
            "clear_dirty": self.clear_dirty,
            "walk": self.walk,
            "measure_cache": self.measure_cache,
            "layout_cache": self.layout_cache,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # Tree mutation
    # ------------------------------------------------------------------
    def add(self, params):
        node = self._p(params, "node")
        if node is None:
            return (0, None, ("missing_node", "add requires {'node': LayoutNode}", 0))
        node.state["parent"] = self
        self.state["children"].append(node)
        self.mark_dirty({"flags": Config.DIRTY_ALL})
        return (1, node, None)

    def remove(self, params):
        node = self._p(params, "node")
        nid = self._p(params, "nid")
        removed = None
        new_children = []
        for c in self.state["children"]:
            if (node is not None and c is node) or (nid is not None and c.state["nid"] == nid):
                removed = c
                c.state["parent"] = None
                continue
            new_children.append(c)
        self.state["children"] = new_children
        if removed is not None:
            self.mark_dirty({"flags": Config.DIRTY_ALL})
            return (1, removed, None)
        return (0, None, ("not_found", "child not found", 0))

    def child(self, params):
        idx = self._p(params, "index")
        nid = self._p(params, "nid")
        if idx is not None:
            ch = self.state["children"]
            if 0 <= idx < len(ch):
                return (1, ch[idx], None)
            return (0, None, ("out_of_range", "index out of range", 0))
        if nid is not None:
            for c in self.state["children"]:
                if c.state["nid"] == nid:
                    return (1, c, None)
            return (0, None, ("not_found", "nid not found", 0))
        return (0, None, ("missing_param", "child requires index or nid", 0))

    def children(self, params):
        return (1, list(self.state["children"]), None)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------
    def mark_dirty(self, params):
        flags = self._p(params, "flags", Config.DIRTY_ALL)
        propagate = self._p(params, "propagate", True)
        self.state["dirty"] = self.state["dirty"] | flags
        if propagate:
            node = self.state["parent"]
            while node is not None:
                node.state["dirty"] = node.state["dirty"] | flags
                node = node.state["parent"]
        return (1, self.state["dirty"], None)

    def clear_dirty(self, params):
        flags = self._p(params, "flags", Config.DIRTY_ALL)
        self.state["dirty"] = self.state["dirty"] & ~flags
        return (1, self.state["dirty"], None)

    # ------------------------------------------------------------------
    # Walk
    # ------------------------------------------------------------------
    def walk(self, params):
        order = self._p(params, "order", "pre")
        result = []
        if order == "pre":
            result.append(self)
            for c in self.state["children"]:
                ok, data, err = c.walk({"order": "pre"})
                if ok:
                    result.extend(data)
        elif order == "post":
            for c in self.state["children"]:
                ok, data, err = c.walk({"order": "post"})
                if ok:
                    result.extend(data)
            result.append(self)
        elif order == "level":
            queue = [self]
            while queue:
                n = queue.pop(0)
                result.append(n)
                queue.extend(n.state["children"])
        return (1, result, None)

    # ------------------------------------------------------------------
    # Cache access
    # ------------------------------------------------------------------
    def measure_cache(self, params):
        return (1, self.state["measure"], None)

    def layout_cache(self, params):
        return (1, self.state["rect"], None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        s = self.state
        return (1, {
            "nid": s["nid"],
            "kind": s["kind"],
            "constraints": dict(s["constraints"]),
            "responsive": dict(s["responsive"]),
            "style": dict(s["style"]),
            "child_count": len(s["children"]),
            "dirty": s["dirty"],
            "has_measure": s["measure"] is not None,
            "has_rect": s["rect"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for group in ("constraints", "responsive", "style", "meta"):
            if group in params and isinstance(params[group], dict):
                self.state[group].update(params[group])
        if "content" in params:
            self.state["content"] = params["content"]
        self.mark_dirty({"flags": Config.DIRTY_ALL})
        return (1, True, None)


# ---------------------------------------------------------------------------
# Node ID generator (module-level counter)
# ---------------------------------------------------------------------------
_NID_COUNTER = [0]


def _next_nid():
    _NID_COUNTER[0] += 1
    return "n" + str(_NID_COUNTER[0]).zfill(4)


def reset_nid():
    _NID_COUNTER[0] = 0
    return (1, 0, None)


# ---------------------------------------------------------------------------
# Concrete node classes — thin specializations of LayoutNode
# ---------------------------------------------------------------------------

class ContainerNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_CONTAINER
        LayoutNode.__init__(self, mem, db, p)


class RowNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_ROW
        p.setdefault("direction", "row")
        LayoutNode.__init__(self, mem, db, p)


class ColumnNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_COLUMN
        p.setdefault("direction", "column")
        LayoutNode.__init__(self, mem, db, p)


class BlockNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_BLOCK
        LayoutNode.__init__(self, mem, db, p)


class WidgetNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_WIDGET
        LayoutNode.__init__(self, mem, db, p)


class TextNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_TEXT
        LayoutNode.__init__(self, mem, db, p)


class TableNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_TABLE
        LayoutNode.__init__(self, mem, db, p)


class TreeNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_TREE
        LayoutNode.__init__(self, mem, db, p)


class PipelineNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_PIPELINE
        LayoutNode.__init__(self, mem, db, p)


class SpacerNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_SPACER
        LayoutNode.__init__(self, mem, db, p)


class DividerNode(LayoutNode):
    def __init__(self, mem=None, db=None, param=None):
        p = dict(param or {})
        p["kind"] = Config.KIND_DIVIDER
        LayoutNode.__init__(self, mem, db, p)
