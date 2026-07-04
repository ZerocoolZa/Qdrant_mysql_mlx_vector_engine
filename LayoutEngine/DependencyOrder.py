#[@GHOST]{[@file<DependencyOrder.py>][@domain<layout_dependency>][@role<topological_walk>][@return<Tuple3>][@auth<devin>][@date<2026-06-29>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<dependency>][@return<Tuple3>][@state<edges,order>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/LayoutEngine/DependencyOrder.py>][@date<2026-06-29>][@session<layout_engine>]}
#[@SUMMARY]{Dependency-ordered traversal — topological-ish ordering for nodes whose size depends on other nodes. Adapted from DependencyGraph.resolve_order in _extracted_existing.py}
#[@CLASS]{DependencyOrder — builds a dependency graph over LayoutNodes, resolves traversal order so deps are measured first}
#[@METHOD]{Run dispatch: add_dep, resolve_order, walk_ordered, read_state, set_config}

import Config
from LayoutNode import LayoutNode


class DependencyOrder:
    """Dependency-ordered traversal for the Layout Graph.

    Adapted from DependencyGraph.resolve_order() in the extracted code
    (_extracted_existing.py line 5489): build an edge map node_id -> set(depends_on),
    then order nodes so dependencies are visited first.

    Use case: when node B's size depends on node A's size (e.g. a table column
    width derived from a sibling's content, or a sidebar that must match the
    main content's height), the measure pass must visit A before B. A plain
    pre-order walk doesn't guarantee that; this does.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "edges": {},      # nid -> set(depends_on nid)
            "order": [],      # resolved nid order
            "memunit": mem,
            "dbunit": db,
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "add_dep": self.add_dep,
            "resolve_order": self.resolve_order,
            "walk_ordered": self.walk_ordered,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    # ------------------------------------------------------------------
    # add_dep: declare "node depends on dep" (dep must be measured first)
    # ------------------------------------------------------------------
    def add_dep(self, params):
        nid = self._p(params, "nid")
        dep = self._p(params, "dep")
        if nid is None or dep is None:
            return (0, None, ("missing_param", "add_dep requires nid + dep", 0))
        if nid not in self.state["edges"]:
            self.state["edges"][nid] = set()
        self.state["edges"][nid].add(dep)
        return (1, True, None)

    # ------------------------------------------------------------------
    # resolve_order: given a root, return nids in dependency-first order
    # Falls back to pre-order for nodes with no declared deps.
    # ------------------------------------------------------------------
    def resolve_order(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("missing_root", "resolve_order requires {'root': LayoutNode}", 0))
        # Collect all nids in pre-order
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        all_nids = [n.state["nid"] for n in data]
        nid_set = set(all_nids)
        # Build adjacency: only keep deps that exist in the tree
        edges = {}
        for nid in all_nids:
            deps = self.state["edges"].get(nid, set())
            edges[nid] = {d for d in deps if d in nid_set}
        # Kahn's algorithm for topological sort
        in_degree = {nid: 0 for nid in all_nids}
        for nid, deps in edges.items():
            for d in deps:
                # d must come before nid, so nid has in-edges from d
                in_degree[nid] = in_degree.get(nid, 0)
        # Recompute in_degree properly: count how many deps each node has
        in_degree = {nid: len(edges.get(nid, set())) for nid in all_nids}
        # Queue of nodes with no unresolved deps, in pre-order for determinism
        queue = [nid for nid in all_nids if in_degree[nid] == 0]
        order = []
        visited = set()
        # Reverse edges: dep -> [nodes that depend on dep]
        dependents = {nid: [] for nid in all_nids}
        for nid, deps in edges.items():
            for d in deps:
                dependents[d].append(nid)
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            order.append(nid)
            for dependent in dependents.get(nid, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        # Append any remaining (cycle-breaking fallback — preserves pre-order)
        for nid in all_nids:
            if nid not in visited:
                order.append(nid)
        self.state["order"] = order
        return (1, order, None)

    # ------------------------------------------------------------------
    # walk_ordered: return LayoutNodes in resolved dependency order
    # ------------------------------------------------------------------
    def walk_ordered(self, params):
        root = self._p(params, "root")
        if root is None:
            return (0, None, ("missing_root", "walk_ordered requires {'root': LayoutNode}", 0))
        ok, order, err = self.resolve_order({"root": root})
        if not ok:
            return (0, None, err)
        # Build nid -> node map
        ok, data, err = root.walk({"order": "pre"})
        if not ok:
            return (0, None, err)
        nid_map = {n.state["nid"]: n for n in data}
        ordered_nodes = [nid_map[nid] for nid in order if nid in nid_map]
        return (1, ordered_nodes, None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def read_state(self):
        return (1, {
            "edge_count": sum(len(v) for v in self.state["edges"].values()),
            "order_length": len(self.state["order"]),
        }, None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_param", "set_config requires dict", 0))
        return (1, True, None)
