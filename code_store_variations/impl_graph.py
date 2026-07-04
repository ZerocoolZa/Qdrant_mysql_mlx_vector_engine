class DomGraph:
    """Graph operations: nodes, edges, traversal, paths, cycles, topology."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._graph = {"nodes": {}, "edges": {}}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "add_edge": self.add_edge,
            "bfs": self.bfs,
            "cycles": self.cycles,
            "dfs": self.dfs,
            "get_edge": self.get_edge,
            "get_node": self.get_node,
            "neighbors": self.neighbors,
            "path": self.path,
            "remove_edge": self.remove_edge,
            "remove_node": self.remove_node,
            "shortest_path": self.shortest_path,
            "topology": self.topology,
            "traverse": self.traverse,
            "visualize": self.visualize,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _load_graph(self, params):
        g = params.get("graph")
        if g:
            self._graph["nodes"] = dict(g.get("nodes", {}))
            self._graph["edges"] = {k: list(v) for k, v in g.get("edges", {}).items()}
        return self._graph

    def add_edge(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            src = params.get("source")
            dst = params.get("target")
            weight = params.get("weight", 1)
            if src is None or dst is None:
                return (0, None, ("ADD_EDGE_ERROR", "missing source/target", 0))
            g["nodes"].setdefault(src, {})
            g["nodes"].setdefault(dst, {})
            g["edges"].setdefault(src, []).append({"target": dst, "weight": weight})
            result = {"domain": "graph", "method": "add_edge", "data": {"source": src, "target": dst, "weight": weight}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ADD_EDGE_ERROR", str(e), 0))

    def bfs(self, params=None):
        params = params or {}
        try:
            from collections import deque
            g = self._load_graph(params)
            start = params.get("start")
            if start is None:
                return (0, None, ("BFS_ERROR", "missing start", 0))
            visited = []
            seen = {start}
            q = deque([start])
            while q:
                node = q.popleft()
                visited.append(node)
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    if t not in seen:
                        seen.add(t)
                        q.append(t)
            result = {"domain": "graph", "method": "bfs", "data": {"start": start, "order": visited}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BFS_ERROR", str(e), 0))

    def cycles(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            visited = set()
            stack = set()
            found = []

            def dfs(node, path):
                visited.add(node)
                stack.add(node)
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    if t not in visited:
                        dfs(t, path + [node])
                    elif t in stack:
                        found.append(path + [node, t])
                stack.discard(node)

            for n in g["nodes"]:
                if n not in visited:
                    dfs(n, [])
            result = {"domain": "graph", "method": "cycles", "data": {"cycles": found, "count": len(found)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CYCLES_ERROR", str(e), 0))

    def dfs(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            start = params.get("start")
            if start is None:
                return (0, None, ("DFS_ERROR", "missing start", 0))
            visited = []
            seen = set()

            def _dfs(node):
                seen.add(node)
                visited.append(node)
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    if t not in seen:
                        _dfs(t)

            _dfs(start)
            result = {"domain": "graph", "method": "dfs", "data": {"start": start, "order": visited}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DFS_ERROR", str(e), 0))

    def get_edge(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            src = params.get("source")
            dst = params.get("target")
            if src is None or dst is None:
                return (0, None, ("GET_EDGE_ERROR", "missing source/target", 0))
            found = None
            for edge in g["edges"].get(src, []):
                t = edge["target"] if isinstance(edge, dict) else edge
                if t == dst:
                    found = edge
                    break
            result = {"domain": "graph", "method": "get_edge", "data": {"source": src, "target": dst, "edge": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_EDGE_ERROR", str(e), 0))

    def get_node(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            node = params.get("node")
            if node is None:
                return (0, None, ("GET_NODE_ERROR", "missing node", 0))
            data = g["nodes"].get(node)
            result = {"domain": "graph", "method": "get_node", "data": {"node": node, "exists": data is not None, "data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_NODE_ERROR", str(e), 0))

    def neighbors(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            node = params.get("node")
            if node is None:
                return (0, None, ("NEIGHBORS_ERROR", "missing node", 0))
            nbrs = []
            for edge in g["edges"].get(node, []):
                nbrs.append(edge["target"] if isinstance(edge, dict) else edge)
            result = {"domain": "graph", "method": "neighbors", "data": {"node": node, "neighbors": nbrs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NEIGHBORS_ERROR", str(e), 0))

    def path(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            start = params.get("start")
            end = params.get("end")
            if start is None or end is None:
                return (0, None, ("PATH_ERROR", "missing start/end", 0))
            from collections import deque
            q = deque([[start]])
            seen = {start}
            found = None
            while q:
                p = q.popleft()
                node = p[-1]
                if node == end:
                    found = p
                    break
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    if t not in seen:
                        seen.add(t)
                        q.append(p + [t])
            result = {"domain": "graph", "method": "path", "data": {"start": start, "end": end, "path": found, "exists": found is not None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PATH_ERROR", str(e), 0))

    def remove_edge(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            src = params.get("source")
            dst = params.get("target")
            if src is None or dst is None:
                return (0, None, ("REMOVE_EDGE_ERROR", "missing source/target", 0))
            before = len(g["edges"].get(src, []))
            g["edges"][src] = [
                e for e in g["edges"].get(src, [])
                if (e["target"] if isinstance(e, dict) else e) != dst
            ]
            removed = before - len(g["edges"][src])
            result = {"domain": "graph", "method": "remove_edge", "data": {"source": src, "target": dst, "removed": removed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REMOVE_EDGE_ERROR", str(e), 0))

    def remove_node(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            node = params.get("node")
            if node is None:
                return (0, None, ("REMOVE_NODE_ERROR", "missing node", 0))
            existed = node in g["nodes"]
            g["nodes"].pop(node, None)
            g["edges"].pop(node, None)
            for src in list(g["edges"].keys()):
                g["edges"][src] = [
                    e for e in g["edges"][src]
                    if (e["target"] if isinstance(e, dict) else e) != node
                ]
            result = {"domain": "graph", "method": "remove_node", "data": {"node": node, "removed": existed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REMOVE_NODE_ERROR", str(e), 0))

    def shortest_path(self, params=None):
        params = params or {}
        try:
            import heapq
            g = self._load_graph(params)
            start = params.get("start")
            end = params.get("end")
            if start is None or end is None:
                return (0, None, ("SHORTEST_PATH_ERROR", "missing start/end", 0))
            dist = {start: 0}
            prev = {}
            pq = [(0, start)]
            while pq:
                d, node = heapq.heappop(pq)
                if node == end:
                    break
                if d > dist.get(node, float("inf")):
                    continue
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    w = edge.get("weight", 1) if isinstance(edge, dict) else 1
                    nd = d + w
                    if nd < dist.get(t, float("inf")):
                        dist[t] = nd
                        prev[t] = node
                        heapq.heappush(pq, (nd, t))
            if end not in dist:
                path = None
                cost = None
            else:
                path = [end]
                cur = end
                while cur != start:
                    cur = prev[cur]
                    path.append(cur)
                path.reverse()
                cost = dist[end]
            result = {"domain": "graph", "method": "shortest_path", "data": {"start": start, "end": end, "path": path, "cost": cost}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SHORTEST_PATH_ERROR", str(e), 0))

    def topology(self, params=None):
        params = params or {}
        try:
            from collections import deque
            g = self._load_graph(params)
            indeg = {n: 0 for n in g["nodes"]}
            for src, edges in g["edges"].items():
                for edge in edges:
                    t = edge["target"] if isinstance(edge, dict) else edge
                    indeg[t] = indeg.get(t, 0) + 1
            q = deque([n for n, d in indeg.items() if d == 0])
            order = []
            while q:
                node = q.popleft()
                order.append(node)
                for edge in g["edges"].get(node, []):
                    t = edge["target"] if isinstance(edge, dict) else edge
                    indeg[t] -= 1
                    if indeg[t] == 0:
                        q.append(t)
            result = {"domain": "graph", "method": "topology", "data": {"order": order, "is_dag": len(order) == len(g["nodes"])}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOPOLOGY_ERROR", str(e), 0))

    def traverse(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            mode = params.get("mode", "bfs")
            start = params.get("start")
            if start is None:
                return (0, None, ("TRAVERSE_ERROR", "missing start", 0))
            if mode == "dfs":
                order = []
                seen = set()

                def _dfs(node):
                    seen.add(node)
                    order.append(node)
                    for edge in g["edges"].get(node, []):
                        t = edge["target"] if isinstance(edge, dict) else edge
                        if t not in seen:
                            _dfs(t)

                _dfs(start)
            else:
                from collections import deque
                order = []
                seen = {start}
                q = deque([start])
                while q:
                    node = q.popleft()
                    order.append(node)
                    for edge in g["edges"].get(node, []):
                        t = edge["target"] if isinstance(edge, dict) else edge
                        if t not in seen:
                            seen.add(t)
                            q.append(t)
            result = {"domain": "graph", "method": "traverse", "data": {"mode": mode, "start": start, "order": order}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRAVERSE_ERROR", str(e), 0))

    def visualize(self, params=None):
        params = params or {}
        try:
            g = self._load_graph(params)
            lines = ["digraph G {"]
            for n in g["nodes"]:
                lines.append(f'  "{n}";')
            for src, edges in g["edges"].items():
                for edge in edges:
                    t = edge["target"] if isinstance(edge, dict) else edge
                    w = edge.get("weight", "") if isinstance(edge, dict) else ""
                    if w != "":
                        lines.append(f'  "{src}" -> "{t}" [label="{w}"];')
                    else:
                        lines.append(f'  "{src}" -> "{t}";')
            lines.append("}")
            dot = "\n".join(lines)
            result = {"domain": "graph", "method": "visualize", "data": {"format": "dot", "content": dot}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VISUALIZE_ERROR", str(e), 0))
