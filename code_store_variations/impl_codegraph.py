import re
from collections import defaultdict, deque


class DomCodegraph:
    """Code dependency graph builder and analyzer."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        method_name = command + "_" if command == "import" else command
        handler = getattr(self, method_name, None)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _adj_from_graph(self, params):
        g = params.get("graph") or {}
        if not g and params.get("nodes"):
            g = {n: [] for n in params["nodes"]}
        return g

    def build(self, params=None):
        params = params or {}
        try:
            code = params.get("code") or ""
            nodes = params.get("nodes") or []
            edges = params.get("edges") or []
            if code:
                found = re.findall(r"^(?:from|import)\s+([\w\.]+)", code, re.M)
                nodes = list(set(nodes + found))
                for f in found:
                    edges.append((f, "__root__"))
            adj = defaultdict(list)
            for n in nodes:
                adj.setdefault(n, [])
            for e in edges:
                if isinstance(e, (list, tuple)) and len(e) >= 2:
                    adj[e[0]].append(e[1])
                    adj.setdefault(e[1], [])
            graph = {k: list(v) for k, v in adj.items()}
            self.state["graph"] = graph
            result = {"domain": "codegraph", "method": "build", "data": {"graph": graph, "node_count": len(graph), "edge_count": sum(len(v) for v in graph.values())}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BUILD_ERROR", str(e), 0))

    def components(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            seen = set()
            comps = []
            for node in g:
                if node in seen:
                    continue
                stack = [node]
                comp = []
                while stack:
                    cur = stack.pop()
                    if cur in seen:
                        continue
                    seen.add(cur)
                    comp.append(cur)
                    for nb in g.get(cur, []):
                        if nb not in seen:
                            stack.append(nb)
                comps.append(sorted(comp))
            result = {"domain": "codegraph", "method": "components", "data": {"components": comps, "count": len(comps)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPONENTS_ERROR", str(e), 0))

    def connected(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            src = params.get("src") or params.get("source")
            dst = params.get("dst") or params.get("dest")
            if not src or not dst:
                return (0, None, ("CONNECTED_ERROR", "missing src/dst", 0))
            visited = set()
            stack = [src]
            while stack:
                cur = stack.pop()
                if cur == dst:
                    result = {"domain": "codegraph", "method": "connected", "data": {"src": src, "dst": dst, "connected": True}}
                    return (1, result, None)
                if cur in visited:
                    continue
                visited.add(cur)
                stack.extend(g.get(cur, []))
            result = {"domain": "codegraph", "method": "connected", "data": {"src": src, "dst": dst, "connected": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONNECTED_ERROR", str(e), 0))

    def cycles(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            visited = set()
            stack = []
            cycles = []

            def dfs(node):
                if node in stack:
                    idx = stack.index(node)
                    cycles.append(stack[idx:] + [node])
                    return
                if node in visited:
                    return
                visited.add(node)
                stack.append(node)
                for nb in g.get(node, []):
                    dfs(nb)
                stack.pop()

            for n in g:
                if n not in visited:
                    dfs(n)
            result = {"domain": "codegraph", "method": "cycles", "data": {"cycles": cycles, "count": len(cycles)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CYCLES_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            code = params.get("code") or ""
            imports = re.findall(r"^(?:from\s+([\w\.]+)\s+import\s+(.+)|import\s+([\w\.]+))$", code, re.M)
            parsed = []
            for frm, names, imp in imports:
                if imp:
                    parsed.append({"module": imp, "names": []})
                else:
                    parsed.append({"module": frm, "names": [n.strip() for n in names.split(",")]})
            result = {"domain": "codegraph", "method": "import", "data": {"imports": parsed, "count": len(parsed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            graphs = params.get("graphs") or []
            merged = defaultdict(list)
            for g in graphs:
                for k, v in g.items():
                    merged[k].extend(v)
            graph = {k: list(set(v)) for k, v in merged.items()}
            result = {"domain": "codegraph", "method": "merge", "data": {"graph": graph, "node_count": len(graph)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def neighbors(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            node = params.get("node")
            if not node:
                return (0, None, ("NEIGHBORS_ERROR", "missing node", 0))
            nbs = list(g.get(node, []))
            result = {"domain": "codegraph", "method": "neighbors", "data": {"node": node, "neighbors": nbs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NEIGHBORS_ERROR", str(e), 0))

    def path(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            src = params.get("src") or params.get("source")
            dst = params.get("dst") or params.get("dest")
            if not src or not dst:
                return (0, None, ("PATH_ERROR", "missing src/dst", 0))
            queue = deque([[src]])
            seen = {src}
            while queue:
                p = queue.popleft()
                cur = p[-1]
                if cur == dst:
                    result = {"domain": "codegraph", "method": "path", "data": {"src": src, "dst": dst, "path": p, "found": True}}
                    return (1, result, None)
                for nb in g.get(cur, []):
                    if nb not in seen:
                        seen.add(nb)
                        queue.append(p + [nb])
            result = {"domain": "codegraph", "method": "path", "data": {"src": src, "dst": dst, "path": [], "found": False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PATH_ERROR", str(e), 0))

    def shortest_path(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            src = params.get("src") or params.get("source")
            dst = params.get("dst") or params.get("dest")
            if not src or not dst:
                return (0, None, ("SHORTEST_PATH_ERROR", "missing src/dst", 0))
            queue = deque([(src, [src])])
            seen = {src}
            while queue:
                cur, p = queue.popleft()
                if cur == dst:
                    result = {"domain": "codegraph", "method": "shortest_path", "data": {"src": src, "dst": dst, "path": p, "length": len(p) - 1}}
                    return (1, result, None)
                for nb in g.get(cur, []):
                    if nb not in seen:
                        seen.add(nb)
                        queue.append((nb, p + [nb]))
            result = {"domain": "codegraph", "method": "shortest_path", "data": {"src": src, "dst": dst, "path": [], "length": -1}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SHORTEST_PATH_ERROR", str(e), 0))

    def topology(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            indeg = {n: 0 for n in g}
            for k, v in g.items():
                for nb in v:
                    indeg[nb] = indeg.get(nb, 0) + 1
                    if nb not in indeg:
                        indeg[nb] = 1
            queue = deque([n for n in indeg if indeg[n] == 0])
            order = []
            while queue:
                cur = queue.popleft()
                order.append(cur)
                for nb in g.get(cur, []):
                    indeg[nb] -= 1
                    if indeg[nb] == 0:
                        queue.append(nb)
            result = {"domain": "codegraph", "method": "topology", "data": {"order": order, "valid": len(order) == len(indeg)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOPOLOGY_ERROR", str(e), 0))

    def traverse(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            start = params.get("start") or (next(iter(g)) if g else None)
            mode = params.get("mode", "bfs")
            if not start:
                result = {"domain": "codegraph", "method": "traverse", "data": {"order": [], "mode": mode}}
                return (1, result, None)
            visited = set()
            order = []
            if mode == "dfs":
                stack = [start]
                while stack:
                    cur = stack.pop()
                    if cur in visited:
                        continue
                    visited.add(cur)
                    order.append(cur)
                    for nb in reversed(g.get(cur, [])):
                        if nb not in visited:
                            stack.append(nb)
            else:
                queue = deque([start])
                while queue:
                    cur = queue.popleft()
                    if cur in visited:
                        continue
                    visited.add(cur)
                    order.append(cur)
                    for nb in g.get(cur, []):
                        if nb not in visited:
                            queue.append(nb)
            result = {"domain": "codegraph", "method": "traverse", "data": {"order": order, "mode": mode, "count": len(order)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRAVERSE_ERROR", str(e), 0))

    def visualize(self, params=None):
        params = params or {}
        try:
            g = self._adj_from_graph(params)
            if not g and self.state.get("graph"):
                g = self.state["graph"]
            lines = []
            for k in sorted(g):
                nbs = g.get(k, [])
                if nbs:
                    lines.append(f"{k} -> " + ", ".join(sorted(nbs)))
                else:
                    lines.append(f"{k}")
            text = "\n".join(lines)
            result = {"domain": "codegraph", "method": "visualize", "data": {"text": text, "lines": len(lines)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VISUALIZE_ERROR", str(e), 0))
