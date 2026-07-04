#[@GHOST]{[@file<Lifecycle.py>][@domain<layout_lifecycle>][@role<pipeline_orchestrator>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<lifecycle>][@return<Tuple3>][@state<phase,stats,cache>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/Lifecycle.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Lifecycle pipeline: build -> normalize -> measure -> solve_constraints -> layout -> render, with invalidation}
#[@CLASS]{Lifecycle — orchestrates the full layout pipeline + dirty-flag incremental recompute}
#[@METHOD]{Run dispatch: run, build, normalize, measure, solve, layout, invalidate, read_state, set_config}

import logging

import Config
from LayoutNode import LayoutNode
from Constraints import ConstraintSolver
from Responsive import ResponsiveResolver

log = logging.getLogger("LayoutLifecycle")


class Lifecycle:
    """The layout lifecycle pipeline.

    Phases (in order):
      build     — accept a root LayoutNode (or build from a dict spec)
      normalize — validate tree, assign defaults, fill missing constraints
      measure   — bottom-up intrinsic size (skips clean subtrees)
      solve     — top-down constraint resolution -> rects (skips clean subtrees)
      layout    — finalize rect placement (currently same as solve output)
      render    — hand solved tree to a renderer (terminal or qt)

    Invalidation:
      invalidate(node, flags)  — marks node + ancestors dirty
      run() only re-runs phases on dirty subtrees; clean subtrees reuse cache.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "width": p.get("width", Config.DEFAULT_TERM_WIDTH),
                "height": p.get("height", Config.DEFAULT_TERM_HEIGHT),
                "target": p.get("target", Config.TARGET_TERMINAL),
                "theme": p.get("theme", Config.THEME_DEFAULT),
                "cache": p.get("cache", Config.CACHE_ENABLED),
            },
            "root": None,
            "solver": ConstraintSolver(mem, db, p),
            "responsive": ResponsiveResolver(mem, db, p),
            "renderer": None,
            "phase": "idle",
            "stats": {
                "build": 0, "normalize": 0, "measure": 0,
                "solve": 0, "layout": 0, "render": 0,
                "cache_hits": 0, "dirty_runs": 0,
            },
            "last_result": None,
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "run": self.run,
            "build": self.build,
            "normalize": self.normalize,
            "measure": self.measure,
            "solve": self.solve,
            "layout": self.layout,
            "invalidate": self.invalidate,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # Phase: build
    # ------------------------------------------------------------------
    def build(self, params):
        root = self._p(params, "root")
        spec = self._p(params, "spec")
        if root is not None:
            self.state["root"] = root
        elif spec is not None:
            ok, data, err = _build_from_spec(spec)
            if not ok:
                return (0, None, err)
            self.state["root"] = data
        else:
            return (0, None, ("missing_param", "build requires root or spec", 0))
        # Mark whole tree dirty
        self.state["root"].mark_dirty({"flags": Config.DIRTY_ALL})
        self.state["phase"] = "built"
        self.state["stats"]["build"] += 1
        return (1, self.state["root"], None)

    # ------------------------------------------------------------------
    # Phase: normalize
    # ------------------------------------------------------------------
    def normalize(self, params):
        root = self._p(params, "root", self.state["root"])
        if root is None:
            return (0, None, ("no_root", "no root node; build first", 0))
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        for node in data:
            c = node.state["constraints"]
            if c["min_w"] < 0:
                c["min_w"] = 0
            if c["min_h"] < 0:
                c["min_h"] = 0
            if c["max_w"] < c["min_w"]:
                c["max_w"] = c["min_w"]
            if c["max_h"] < c["min_h"]:
                c["max_h"] = c["min_h"]
            if c["weight"] < 0:
                c["weight"] = Config.WEIGHT_DEFAULT
            if c["flex_grow"] < 0:
                c["flex_grow"] = Config.FLEX_GROW_DEFAULT
            if c["flex_shrink"] < 0:
                c["flex_shrink"] = Config.FLEX_SHRINK_DEFAULT
            # responsive: ensure xs has a default
            if node.state["responsive"]["xs"] is None:
                node.state["responsive"]["xs"] = Config.GRID_COLUMNS
        self.state["phase"] = "normalized"
        self.state["stats"]["normalize"] += 1
        return (1, True, None)

    # ------------------------------------------------------------------
    # Phase: measure (incremental — skip clean subtrees)
    # ------------------------------------------------------------------
    def measure(self, params):
        root = self._p(params, "root", self.state["root"])
        if root is None:
            return (0, None, ("no_root", "no root node; build first", 0))
        w = self._p(params, "width", self.state["config"]["width"])
        h = self._p(params, "height", self.state["config"]["height"])
        self._measure_recursive(root, w, h)
        self.state["phase"] = "measured"
        self.state["stats"]["measure"] += 1
        return (1, True, None)

    def _measure_recursive(self, node, max_w, max_h):
        if not self.state["config"]["cache"]:
            node.state["dirty"] = node.state["dirty"] | Config.DIRTY_MEASURE
        if (node.state["dirty"] & Config.DIRTY_MEASURE) == 0 and node.state["measure"] is not None:
            self.state["stats"]["cache_hits"] += 1
        else:
            ok, data, err = self.state["solver"].Run("measure", {
                "node": node, "max_w": max_w, "max_h": max_h,
            })
            if not ok:
                log.warning("measure failed for %s: %s", node.state["nid"], err)
        for ch in node.state["children"]:
            self._measure_recursive(ch, max_w, max_h)

    # ------------------------------------------------------------------
    # Phase: solve constraints (top-down, incremental)
    # ------------------------------------------------------------------
    def solve(self, params):
        root = self._p(params, "root", self.state["root"])
        if root is None:
            return (0, None, ("no_root", "no root node; build first", 0))
        w = self._p(params, "width", self.state["config"]["width"])
        h = self._p(params, "height", self.state["config"]["height"])
        # Apply responsive resolution first (may rewrite col_span -> weight)
        ok, data, err = self.state["responsive"].Run("resolve_tree", {
            "root": root, "width": w,
        })
        if not ok:
            log.warning("responsive resolve failed: %s", err)
        ok, data, err = self.state["solver"].Run("solve", {
            "root": root, "width": w, "height": h,
        })
        if not ok:
            return (0, None, err)
        # Clear layout dirty on solved nodes
        ok, data, err = root.walk({"order": "pre"})
        if ok:
            for node in data:
                node.clear_dirty({"flags": Config.DIRTY_MEASURE | Config.DIRTY_LAYOUT})
        self.state["phase"] = "solved"
        self.state["stats"]["solve"] += 1
        return (1, root, None)

    # ------------------------------------------------------------------
    # Phase: layout (finalize — currently rect == solve output)
    # ------------------------------------------------------------------
    def layout(self, params):
        root = self._p(params, "root", self.state["root"])
        if root is None:
            return (0, None, ("no_root", "no root node; build first", 0))
        # In a fuller engine this would handle sub-pixel snap, scroll regions,
        # overflow clipping rects, etc. For now rect is already final from solve.
        self.state["phase"] = "laid_out"
        self.state["stats"]["layout"] += 1
        return (1, root, None)

    # ------------------------------------------------------------------
    # Phase: render (delegated to a renderer set via set_config)
    # ------------------------------------------------------------------
    def render(self, params):
        root = self._p(params, "root", self.state["root"])
        if root is None:
            return (0, None, ("no_root", "no root node; build first", 0))
        renderer = self._p(params, "renderer", self.state["renderer"])
        if renderer is None:
            return (0, None, ("no_renderer", "set renderer via set_config", 0))
        ok, data, err = renderer.Run("render", {"root": root})
        if not ok:
            return (0, None, err)
        # Clear render dirty on the whole tree
        ok, data, err = root.walk({"order": "pre"})
        if ok:
            for node in data:
                node.clear_dirty({"flags": Config.DIRTY_RENDER})
        self.state["phase"] = "rendered"
        self.state["stats"]["render"] += 1
        self.state["last_result"] = data
        return (1, data, None)

    # ------------------------------------------------------------------
    # Full pipeline run
    # ------------------------------------------------------------------
    def run(self, params):
        root = self._p(params, "root", self.state["root"])
        spec = self._p(params, "spec")
        width = self._p(params, "width", self.state["config"]["width"])
        height = self._p(params, "height", self.state["config"]["height"])
        renderer = self._p(params, "renderer", self.state["renderer"])

        bp = {}
        if root is not None:
            bp["root"] = root
        elif spec is not None:
            bp["spec"] = spec
        ok, data, err = self.build(bp)
        if not ok:
            return (0, None, err)
        ok, data, err = self.normalize({})
        if not ok:
            return (0, None, err)
        ok, data, err = self.measure({"width": width, "height": height})
        if not ok:
            return (0, None, err)
        ok, data, err = self.solve({"width": width, "height": height})
        if not ok:
            return (0, None, err)
        ok, data, err = self.layout({})
        if not ok:
            return (0, None, err)
        if renderer is not None:
            ok, data, err = self.render({"renderer": renderer})
            if not ok:
                return (0, None, err)
        return (1, self.state["root"], None)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------
    def invalidate(self, params):
        node = self._p(params, "node")
        flags = self._p(params, "flags", Config.DIRTY_ALL)
        if node is None:
            return (0, None, ("missing_node", "invalidate requires {'node': LayoutNode}", 0))
        node.mark_dirty({"flags": flags, "propagate": True})
        self.state["stats"]["dirty_runs"] += 1
        return (1, node.state["dirty"], None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "config": dict(self.state["config"]),
            "phase": self.state["phase"],
            "stats": dict(self.state["stats"]),
            "has_root": self.state["root"] is not None,
            "has_renderer": self.state["renderer"] is not None,
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        for k in ("width", "height", "target", "theme", "cache"):
            if k in params:
                self.state["config"][k] = params[k]
        if "renderer" in params:
            self.state["renderer"] = params["renderer"]
        if "root" in params:
            self.state["root"] = params["root"]
        return (1, True, None)


# ---------------------------------------------------------------------------
# Spec -> tree builder (dict spec becomes a LayoutNode tree)
# ---------------------------------------------------------------------------

def _build_from_spec(spec):
    """Build a LayoutNode tree from a nested dict spec.

    Spec format:
      {"kind": "row", "children": [{"kind": "block", "content": "hi"}, ...],
       "min_w": 10, "weight": 2, "xs": 6, ...}
    """
    if not isinstance(spec, dict):
        return (0, None, ("bad_spec", "spec must be dict", 0))
    node = _make_node(spec)
    children = spec.get("children", [])
    if isinstance(children, list):
        for cs in children:
            ok, data, err = _build_from_spec(cs)
            if not ok:
                return (0, None, err)
            node.Run("add", {"node": data})
    return (1, node, None)


def _make_node(spec):
    kind = spec.get("kind", Config.KIND_CONTAINER)
    p = dict(spec)
    p["kind"] = kind
    cls_map = {
        Config.KIND_CONTAINER: "ContainerNode",
        Config.KIND_ROW: "RowNode",
        Config.KIND_COLUMN: "ColumnNode",
        Config.KIND_BLOCK: "BlockNode",
        Config.KIND_WIDGET: "WidgetNode",
        Config.KIND_TEXT: "TextNode",
        Config.KIND_TABLE: "TableNode",
        Config.KIND_TREE: "TreeNode",
        Config.KIND_PIPELINE: "PipelineNode",
        Config.KIND_SPACER: "SpacerNode",
        Config.KIND_DIVIDER: "DividerNode",
    }
    import LayoutNode as _LN
    cls = getattr(_LN, cls_map.get(kind, "ContainerNode"), _LN.ContainerNode)
    # strip keys that aren't ctor params (children handled by caller)
    p.pop("children", None)
    return cls(param=p)
