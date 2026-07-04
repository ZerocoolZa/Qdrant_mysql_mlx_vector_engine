#[@GHOST]{[@file<Responsive.py>][@domain<layout_responsive>][@role<breakpoint_resolver>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<responsive>][@return<Tuple3>][@state<breakpoint,viewport>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/Responsive.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Bootstrap-like responsive layer: 12-column grid, breakpoints xs/s/m/l/xl, automatic column collapse + row stacking}
#[@CLASS]{ResponsiveResolver — picks col_span per current viewport width, rewrites weights/direction for collapse}
#[@METHOD]{Run dispatch: resolve, resolve_tree, breakpoint_for, read_state, set_config}

import Config
from LayoutNode import LayoutNode


class ResponsiveResolver:
    """Bootstrap-like responsive layer over the Layout Graph.

    Each node carries a responsive spec:
      {"xs": 12, "s": 6, "m": 4, "l": 3, "xl": 2}
    meaning "at breakpoint X, this node spans N of 12 columns".

    Given a viewport width, resolve():
      1. Picks the active breakpoint (largest threshold <= width).
      2. For each node, reads its col_span for that breakpoint.
      3. If col_span >= GRID_COLUMNS (12) at narrow widths, the node is
         "collapsed" — its parent row flips direction to column so children
         stack vertically instead of sitting side-by-side.
      4. Maps col_span -> flex_grow weight (span/12 * base_weight) so the
         constraint solver distributes space proportionally.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "grid_columns": p.get("grid_columns", Config.GRID_COLUMNS),
                "collapse_below": p.get("collapse_below", "m"),
            },
            "viewport": {"width": Config.DEFAULT_TERM_WIDTH, "breakpoint": "m"},
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "resolve": self.resolve,
            "resolve_tree": self.resolve_tree,
            "breakpoint_for": self.breakpoint_for,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # breakpoint_for(width) -> "xs"|"s"|"m"|"l"|"xl"
    # ------------------------------------------------------------------
    def breakpoint_for(self, params):
        width = self._p(params, "width", self.state["viewport"]["width"])
        bp = "xs"
        for name in Config.BREAKPOINT_ORDER:
            if width >= Config.BREAKPOINT_THRESHOLDS[name]:
                bp = name
        return (1, bp, None)

    # ------------------------------------------------------------------
    # resolve: rewrite a single node's weight/direction for active breakpoint
    # ------------------------------------------------------------------
    def resolve(self, params):
        node = self._p(params, "node")
        width = self._p(params, "width", self.state["viewport"]["width"])
        if node is None:
            return (0, None, ("missing_node", "resolve requires {'node': LayoutNode}", 0))
        ok, bp, err = self.breakpoint_for({"width": width})
        if not ok:
            return (0, None, err)
        self.state["viewport"] = {"width": width, "breakpoint": bp}
        self._apply_breakpoint(node, bp, width)
        return (1, bp, None)

    # ------------------------------------------------------------------
    # resolve_tree: walk the whole tree applying breakpoint resolution
    # ------------------------------------------------------------------
    def resolve_tree(self, params):
        root = self._p(params, "root")
        width = self._p(params, "width", self.state["viewport"]["width"])
        if root is None:
            return (0, None, ("missing_root", "resolve_tree requires {'root': LayoutNode}", 0))
        ok, bp, err = self.breakpoint_for({"width": width})
        if not ok:
            return (0, None, err)
        self.state["viewport"] = {"width": width, "breakpoint": bp}
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        for node in data:
            self._apply_breakpoint(node, bp, width)
        return (1, bp, None)

    # ------------------------------------------------------------------
    # Core: apply breakpoint to one node
    # ------------------------------------------------------------------
    def _apply_breakpoint(self, node, bp, width):
        resp = node.state["responsive"]
        # Find the effective col_span: walk down from current bp to xs
        # to find the nearest specified span (Bootstrap cascade behavior).
        span = None
        idx = Config.BREAKPOINT_ORDER.index(bp)
        for i in range(idx, -1, -1):
            name = Config.BREAKPOINT_ORDER[i]
            val = resp.get(name)
            if val is not None:
                span = val
                break
        if span is None:
            span = Config.GRID_COLUMNS

        cols = self.state["config"]["grid_columns"]
        # Map span -> flex_grow weight (proportional to span share)
        base_weight = node.state["constraints"]["weight"]
        node.state["constraints"]["flex_grow"] = (span / cols) * max(base_weight, 1.0)

        # Collapse: if a row's children all want >= full width, flip to column
        kind = node.state["kind"]
        if kind in (Config.KIND_ROW, Config.KIND_CONTAINER):
            children = node.state["children"]
            if children:
                all_full = True
                for ch in children:
                    ch_resp = ch.state["responsive"]
                    ch_span = None
                    for i in range(idx, -1, -1):
                        nm = Config.BREAKPOINT_ORDER[i]
                        v = ch_resp.get(nm)
                        if v is not None:
                            ch_span = v
                            break
                    if ch_span is None:
                        ch_span = Config.GRID_COLUMNS
                    if ch_span < cols:
                        all_full = False
                        break
                if all_full and bp in ("xs", "s"):
                    # Stack vertically at narrow widths
                    node.state["style"]["direction"] = "column"
                    node.state["kind"] = Config.KIND_COLUMN
                else:
                    # Restore original direction if we previously collapsed
                    if node.state.get("_orig_direction"):
                        node.state["style"]["direction"] = node.state["_orig_direction"]
                        node.state["kind"] = node.state.get("_orig_kind", Config.KIND_ROW)

        # Remember original direction so we can un-collapse on wider widths
        if "_orig_direction" not in node.state:
            node.state["_orig_direction"] = node.state["style"]["direction"]
            node.state["_orig_kind"] = node.state["kind"]

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "viewport": dict(self.state["viewport"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("grid_columns", "collapse_below"):
            if k in params:
                self.state["config"][k] = params[k]
        return (1, True, None)
