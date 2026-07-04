#!/usr/bin/env python3
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/GraphToWizard.py";"identity=GraphToWizard";"purpose=Convert dom_graph_work.db graphs into Wizard SVG Engine scene JSON, then render via the C engine";"date=2026-06-27";"version=1.0";"author=Devin";"chat_link=sqlite://dom_graph_work.db/edges→wizard_engine")}
#[@VBSTYLE]{("auth=Devin";"role=tool";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=mire-region";"context=Code Graph Pipeline — SVG rendering via Wizard Engine";"purpose=Turn DB graph edges into animated SVG using the native C Wizard SVG Engine")}
#[@SUMMARY]{("Reads the edges table from dom_graph_work.db, picks top nodes by degree, lays them out radially or by tier, generates a Wizard Engine scene JSON with mcp_node objects + rect links, then calls the C engine to produce animated SVG output.")}
"""
import sqlite3
import os
import sys
import json
import math
import subprocess
import argparse
from collections import defaultdict


DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/dom_graph_work.db"
ENGINE_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/svg_engine/c/wizard_engine"
OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/rendered_graphs/wizard_svg"

MAX_OBJECTS = 250


class GraphToWizard:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": db or DB_PATH,
            "engine_bin": ENGINE_BIN,
            "output_dir": param or OUTPUT_DIR,
            "conn": None,
        }
        self._p = lambda key, default=None: self.state.get(key, default)

    def _connect(self):
        conn = sqlite3.connect(self._p("db_path"))
        conn.row_factory = sqlite3.Row
        self.state["conn"] = conn
        return conn

    def _label_for(self, entity_type, entity_id):
        conn = self._p("conn")
        if entity_type == "file":
            row = conn.execute("SELECT file_name FROM files WHERE file_id=?", (entity_id,)).fetchone()
            return row["file_name"] if row else f"file#{entity_id}"
        elif entity_type == "class":
            row = conn.execute("SELECT class_name FROM classes WHERE class_id=?", (entity_id,)).fetchone()
            return row["class_name"] if row else f"cls#{entity_id}"
        elif entity_type == "method":
            row = conn.execute(
                "SELECT m.method_name, c.class_name FROM methods m "
                "JOIN classes c ON m.class_id=c.class_id WHERE m.method_id=?",
                (entity_id,)).fetchone()
            if row:
                base = f"{row['class_name']}.{row['method_name']}" if row["class_name"] else row["method_name"]
                return base[:20]
            return f"m#{entity_id}"
        elif entity_type == "variable":
            return "var"
        elif entity_type == "gui":
            return "gui"
        elif entity_type == "api":
            return "api"
        elif entity_type == "thread":
            return "thread"
        elif entity_type == "database":
            return "db"
        return f"{entity_type}#{entity_id}"

    def _node_id(self, entity_type, entity_id):
        return f"{entity_type}:{entity_id}"

    def _status_for_type(self, entity_type):
        return {"file": 1, "class": 1, "method": 1, "variable": 2,
                "gui": 2, "api": 2, "thread": 3, "database": 3}.get(entity_type, 0)

    def load_graph(self, edge_type=None, max_nodes=80):
        conn = self._connect()
        if edge_type:
            rows = conn.execute("SELECT * FROM edges WHERE edge_type=?", (edge_type,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM edges").fetchall()

        adj = defaultdict(set)
        in_deg = defaultdict(int)
        out_deg = defaultdict(int)
        node_types = {}
        edges_list = []

        for row in rows:
            src = self._node_id(row["src_type"], row["src_id"])
            dst = self._node_id(row["dst_type"], row["dst_id"])
            adj[src].add(dst)
            in_deg[dst] += 1
            out_deg[src] += 1
            node_types[src] = row["src_type"]
            node_types[dst] = row["dst_type"]
            edges_list.append((src, dst, row["edge_type"]))

        all_nodes = set(node_types.keys())
        total_deg = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in all_nodes}
        nodes_sorted = sorted(all_nodes, key=lambda n: -total_deg[n])[:max_nodes]
        node_set = set(nodes_sorted)

        filtered_edges = [(s, d, t) for s, d, t in edges_list if s in node_set and d in node_set]

        self.state["nodes"] = nodes_sorted
        self.state["node_types"] = node_types
        self.state["edges"] = filtered_edges
        self.state["in_deg"] = in_deg
        self.state["out_deg"] = out_deg
        self.state["total_deg"] = total_deg
        self.state["edge_type"] = edge_type or "merged"
        return (1, {"nodes": len(nodes_sorted), "edges": len(filtered_edges)}, None)

    def layout_radial(self, width=1200, height=900):
        nodes = self._p("nodes")
        total_deg = self._p("total_deg")
        cx, cy = width / 2, height / 2
        positions = {}
        if not nodes:
            return positions
        hub = nodes[0]
        positions[hub] = (cx, cy)
        max_deg = total_deg.get(hub, 1)
        for i, node in enumerate(nodes[1:], 1):
            angle = (i / max(len(nodes) - 1, 1)) * 2 * math.pi
            deg = total_deg.get(node, 1)
            radius = 150 + (max_deg - deg) / max(max_deg, 1) * 250
            radius = max(120, min(radius, 400))
            positions[node] = (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
        return positions

    def layout_tiered(self, width=1200, height=900):
        nodes = self._p("nodes")
        in_deg = self._p("in_deg")
        out_deg = self._p("out_deg")
        edges = self._p("edges")
        node_types = self._p("node_types")

        adj = defaultdict(set)
        for src, dst, _ in edges:
            adj[src].add(dst)

        tier_map = {}
        visited = set()
        queue = []
        for n in nodes:
            if in_deg.get(n, 0) == 0:
                tier_map[n] = 0
                queue.append(n)
                visited.add(n)

        while queue:
            current = queue.pop(0)
            for neighbor in adj.get(current, set()):
                if neighbor in tier_map:
                    continue
                if all(pred in visited for pred in [s for s, d, _ in edges if d == neighbor]):
                    tier_map[neighbor] = tier_map[current] + 1
                    visited.add(neighbor)
                    queue.append(neighbor)

        for n in nodes:
            if n not in tier_map:
                tier_map[n] = 0

        max_tier = max(tier_map.values()) if tier_map else 1
        tier_counts = defaultdict(list)
        for n, t in tier_map.items():
            tier_counts[t].append(n)

        positions = {}
        for tier, tier_nodes in tier_counts.items():
            y = 100 + (tier / max(max_tier, 1)) * (height - 200)
            spacing = width / max(len(tier_nodes), 1)
            for i, node in enumerate(tier_nodes):
                x = spacing / 2 + i * spacing
                positions[node] = (x, y)
        return positions

    def build_scene_json(self, positions, title="Code Graph"):
        nodes = self._p("nodes")
        node_types = self._p("node_types")
        edges = self._p("edges")
        total_deg = self._p("total_deg")
        edge_type_name = self._p("edge_type")

        width = 1200
        height = 900
        max_deg = max(total_deg.values()) if total_deg else 1

        objects = []

        for node in nodes:
            ntype = node_types.get(node, "method")
            label = self._label_for(*node.split(":"))
            x, y = positions.get(node, (width / 2, height / 2))
            deg = total_deg.get(node, 0)
            scale = 0.5 + (deg / max_deg) * 1.5
            status = self._status_for_type(ntype)
            node_id = node.replace(":", "_").replace("/", "_")[:60]

            obj = {
                "id": node_id,
                "type": "mcp_node",
                "position": [round(x, 1), round(y, 1)],
                "rotation": 0,
                "scale": round(scale, 3),
                "opacity": 1.0,
                "color": "#00ff88",
                "stroke_color": "#00ff88",
                "stroke_width": 2,
                "node_label": label,
                "node_status": status,
                "text": "",
            }
            if deg > max_deg * 0.5:
                obj["motion"] = {
                    "type": "glow",
                    "speed": 0.3,
                    "amplitude": 0,
                    "radius": 0,
                    "phase": 0,
                    "center": [round(x, 1), round(y, 1)],
                    "seed": 42,
                }
            else:
                obj["motion"] = {
                    "type": "pulse",
                    "speed": 0.4,
                    "amplitude": 3.0,
                    "radius": 0,
                    "phase": hash(node) % 100 / 100.0,
                    "center": [round(x, 1), round(y, 1)],
                    "seed": 42,
                }
            objects.append(obj)

        link_count = 0
        max_links = MAX_OBJECTS - len(nodes)
        for src, dst, etype in edges:
            if link_count >= max_links:
                break
            src_pos = positions.get(src)
            dst_pos = positions.get(dst)
            if not src_pos or not dst_pos:
                continue
            sx, sy = src_pos
            dx, dy = dst_pos
            mid_x = (sx + dx) / 2
            mid_y = (sy + dy) / 2
            length = math.sqrt((dx - sx) ** 2 + (dy - sy) ** 2)
            angle = math.degrees(math.atan2(dy - sy, dx - sx))

            link_id = f"link_{link_count}"
            obj = {
                "id": link_id,
                "type": "rect",
                "position": [round(mid_x, 1), round(mid_y, 1)],
                "rotation": round(angle, 2),
                "scale": 1.0,
                "opacity": 0.25,
                "color": "#1e5eff",
                "stroke_color": "#1e5eff",
                "stroke_width": 0,
                "width": round(length, 1),
                "height": 1.5,
                "text": "",
            }
            objects.append(obj)
            link_count += 1

        bg_dust = {
            "id": "bg_particles",
            "type": "emitter",
            "position": [width / 2, height / 2],
            "rotation": 0,
            "scale": 1.0,
            "opacity": 1.0,
            "color": "#7b2ff7",
            "stroke_color": "#ffffff",
            "stroke_width": 1,
            "emitter": {
                "type": "dust",
                "rate": 8,
                "speed": 15,
                "speed_var": 10,
                "size": 1.5,
                "size_var": 0.5,
                "life": 4.0,
                "life_var": 1.0,
                "gravity": -5,
                "drag": 0.98,
                "area": [400, 300],
                "max": 80,
            },
            "text": "",
        }
        objects.append(bg_dust)

        scene = {
            "name": title,
            "width": width,
            "height": height,
            "background": [0.02, 0.02, 0.06],
            "duration": 8.0,
            "fps": 60,
            "objects": objects,
        }
        return scene

    def render_svg(self, scene_json, output_path):
        out_dir = os.path.dirname(output_path)
        os.makedirs(out_dir, exist_ok=True)
        scene_path = output_path.replace(".svg", ".json")
        with open(scene_path, "w") as f:
            json.dump(scene_json, f, indent=2)

        engine = self._p("engine_bin")
        try:
            result = subprocess.run(
                [engine, scene_path, output_path],
                capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TIMEOUT", "C engine timed out", 0))
        except Exception as e:
            return (0, None, ("ENGINE_FAIL", str(e), 0))

        if result.returncode != 0:
            return (0, None, ("ENGINE_ERR", result.stderr[:200], 0))

        return (1, {"svg": output_path, "scene": scene_path, "stdout": result.stdout.strip()}, None)

    def Run(self, command, params=None):
        params = params or {}
        if command == "load":
            edge_type = params.get("edge_type")
            max_nodes = params.get("max_nodes", 80)
            return self.load_graph(edge_type, max_nodes)
        elif command == "render":
            return self._render(params)
        elif command == "render_all":
            return self._render_all(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _render(self, params):
        layout = params.get("layout", "radial")
        title = params.get("title", "Code Graph")
        out_name = params.get("output", "graph.svg")
        out_dir = self._p("output_dir")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, out_name)

        if layout == "tiered":
            positions = self.layout_tiered()
        else:
            positions = self.layout_radial()

        scene = self.build_scene_json(positions, title=title)
        ok, data, err = self.render_svg(scene, out_path)
        if err:
            return (0, None, err)
        return (1, data, None)

    def _render_all(self, params):
        conn = self._p("conn")
        if conn is None:
            conn = self._connect()
        edge_types = conn.execute("SELECT DISTINCT edge_type FROM edges ORDER BY edge_type").fetchall()
        results = []
        for row in edge_types:
            et = row["edge_type"]
            ok1, _, _ = self.Run("load", {"edge_type": et, "max_nodes": params.get("max_nodes", 60)})
            if not ok1:
                continue
            ok2, data, err = self.Run("render", {
                "layout": params.get("layout", "radial"),
                "title": f"Graph: {et}",
                "output": f"{et}.svg",
            })
            results.append({"edge_type": et, "ok": ok2, "data": data, "error": err})

        ok1, _, _ = self.Run("load", {"edge_type": None, "max_nodes": params.get("max_nodes", 100)})
        ok2, data, err = self.Run("render", {
            "layout": "tiered",
            "title": "Merged Code Graph (all edges)",
            "output": "merged_all.svg",
        })
        results.append({"edge_type": "merged_all", "ok": ok2, "data": data, "error": err})
        return (1, results, None)


def main():
    parser = argparse.ArgumentParser(description="Render DB graphs as animated SVG via Wizard Engine")
    parser.add_argument("--db", default=DB_PATH, help="SQLite DB path")
    parser.add_argument("--engine", default=ENGINE_BIN, help="Wizard C engine binary")
    parser.add_argument("--out", default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--edge-type", default=None, help="Specific edge type (default: all)")
    parser.add_argument("--layout", default="radial", choices=["radial", "tiered"],
                        help="Node layout algorithm")
    parser.add_argument("--max-nodes", type=int, default=80, help="Max nodes per graph")
    parser.add_argument("--all", action="store_true", help="Render all edge types + merged")
    args = parser.parse_args()

    converter = GraphToWizard(db=args.db, param=args.out)
    converter.state["engine_bin"] = args.engine

    if args.all:
        ok, data, err = converter.Run("render_all", {
            "layout": args.layout,
            "max_nodes": args.max_nodes,
        })
        if err:
            sys.stderr.write(f"FAIL: {err}\n")
            sys.exit(1)
        print(f"Rendered {len(data)} graphs:")
        for item in data:
            status = "OK" if item["ok"] else "FAIL"
            info = item["data"]["svg"] if item["ok"] and item["data"] else item["error"]
            print(f"  [{status}] {item['edge_type']:20s} → {info}")
    else:
        converter.Run("load", {"edge_type": args.edge_type, "max_nodes": args.max_nodes})
        title = f"Graph: {args.edge_type}" if args.edge_type else "Merged Code Graph"
        out_name = f"{args.edge_type or 'merged'}.svg"
        ok, data, err = converter.Run("render", {
            "layout": args.layout,
            "title": title,
            "output": out_name,
        })
        if err:
            sys.stderr.write(f"FAIL: {err}\n")
            sys.exit(1)
        print(f"SVG: {data['svg']}")
        print(f"Scene JSON: {data['scene']}")
        print(f"Engine: {data['stdout']}")


if __name__ == "__main__":
    main()
