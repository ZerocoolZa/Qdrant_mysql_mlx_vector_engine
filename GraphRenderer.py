#!/usr/bin/env python3
"""
#[@GHOST]{("file_path=/Users/wws/Qdrant_mysql_mlx_vector_engine/GraphRenderer.py";"identity=GraphRenderer";"purpose=Extract all graphs from dom_graph_work.db and render them as ASCII + GraphML + PNG/SVG images";"date=2026-06-27";"version=2.0";"author=Devin";"chat_link=sqlite://dom_graph_work.db/edges")}
#[@VBSTYLE]{("auth=Devin";"role=tool";"return=Tuple3";"orch=none";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete")}
#[@FILEID]{("session_id=mire-region";"context=Code Graph Pipeline Stage 2 — Graph rendering";"purpose=Turn DB edges into visual graphs (ASCII + GraphML + PNG/SVG)")}
#[@SUMMARY]{("Reads the edges table from dom_graph_work.db, builds a separate networkx graph per edge_type, renders each as an ASCII diagram, exports GraphML/JSON, and produces PNG/SVG images via graphviz. Uses sfdp layout for large graphs, dot for small ones.")}
"""
import sqlite3
import os
import sys
import json
import argparse
import subprocess
import tempfile
from collections import defaultdict, Counter
import networkx as nx
from networkx.drawing.nx_agraph import to_agraph


DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/dom_graph_work.db"
OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/rendered_graphs"

EDGE_COLORS = {
    "calls": "#2563eb",
    "reads": "#16a34a",
    "writes": "#dc2626",
    "gui_call": "#9333ea",
    "api_call": "#ea580c",
    "thread_call": "#0891b2",
    "imports": "#65a30d",
    "database_access": "#be185d",
    "gui_import": "#7c3aed",
    "thread_import": "#0e7490",
}

NODE_COLORS = {
    "file": "#dbeafe",
    "class": "#fef3c7",
    "method": "#dcfce7",
    "variable": "#fee2e2",
    "gui": "#f3e8ff",
    "api": "#ffedd5",
    "thread": "#cffafe",
    "database": "#fce7f3",
}


class GraphRenderer:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": db or DB_PATH,
            "output_dir": param or OUTPUT_DIR,
            "conn": None,
            "graphs": {},
            "stats": {}
        }
        self._p = lambda key, default=None: self.state.get(key, default)

    def _connect(self):
        path = self._p("db_path")
        conn = sqlite3.connect(path)
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
            return row["class_name"] if row else f"class#{entity_id}"
        elif entity_type == "method":
            row = conn.execute(
                "SELECT m.method_name, c.class_name FROM methods m "
                "JOIN classes c ON m.class_id=c.class_id WHERE m.method_id=?",
                (entity_id,)).fetchone()
            if row:
                return f"{row['class_name']}.{row['method_name']}" if row["class_name"] else row["method_name"]
            return f"method#{entity_id}"
        elif entity_type == "variable":
            return f"var#{entity_id}"
        elif entity_type == "gui":
            return f"gui#{entity_id}"
        elif entity_type == "api":
            return f"api#{entity_id}"
        elif entity_type == "thread":
            return f"thread#{entity_id}"
        elif entity_type == "database":
            return f"db#{entity_id}"
        return f"{entity_type}#{entity_id}"

    def _node_id(self, entity_type, entity_id):
        return f"{entity_type}:{entity_id}"

    def load_edges(self):
        conn = self._connect()
        rows = conn.execute("SELECT * FROM edges").fetchall()
        edges_by_type = defaultdict(list)
        for row in rows:
            edges_by_type[row["edge_type"]].append(row)
        self.state["edges_by_type"] = dict(edges_by_type)
        self.state["all_edges"] = rows
        return (1, dict(edges_by_type), None)

    def build_graphs(self):
        edges_by_type = self._p("edges_by_type")
        graphs = {}
        for edge_type, edge_rows in edges_by_type.items():
            g = nx.DiGraph()
            for row in edge_rows:
                src = self._node_id(row["src_type"], row["src_id"])
                dst = self._node_id(row["dst_type"], row["dst_id"])
                src_label = self._label_for(row["src_type"], row["src_id"])
                dst_label = self._label_for(row["dst_type"], row["dst_id"])
                g.add_node(src, label=src_label, type=row["src_type"])
                g.add_node(dst, label=dst_label, type=row["dst_type"])
                g.add_edge(src, dst, edge_type=edge_type, evidence=row["evidence"], confidence=row["confidence"])
            graphs[edge_type] = g
        self.state["graphs"] = graphs
        stats = {et: {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()} for et, g in graphs.items()}
        self.state["stats"] = stats
        return (1, stats, None)

    def build_merged_graph(self):
        all_edges = self._p("all_edges")
        g = nx.DiGraph()
        for row in all_edges:
            src = self._node_id(row["src_type"], row["src_id"])
            dst = self._node_id(row["dst_type"], row["dst_id"])
            src_label = self._label_for(row["src_type"], row["src_id"])
            dst_label = self._label_for(row["dst_type"], row["dst_id"])
            g.add_node(src, label=src_label, type=row["src_type"])
            g.add_node(dst, label=dst_label, type=row["dst_type"])
            g.add_edge(src, dst, edge_type=row["edge_type"], evidence=row["evidence"])
        self.state["merged_graph"] = g
        return (1, {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()}, None)

    def render_ascii(self, graph, title, max_nodes=50):
        lines = []
        lines.append(f"  ┌{'─' * 78}┐")
        title_str = f" {title} "
        pad = (78 - len(title_str)) // 2
        lines.append(f"  │{' ' * pad}{title_str}{' ' * (78 - pad - len(title_str))}│")
        lines.append(f"  └{'─' * 78}┘")
        lines.append(f"  nodes: {graph.number_of_nodes()}  edges: {graph.number_of_edges()}")
        lines.append("")

        in_deg = dict(graph.in_degree())
        out_deg = dict(graph.out_degree())
        nodes_sorted = sorted(graph.nodes(), key=lambda n: -(in_deg.get(n, 0) + out_deg.get(n, 0)))

        if graph.number_of_nodes() > max_nodes:
            lines.append(f"  (showing top {max_nodes} of {graph.number_of_nodes()} nodes by degree)")
            nodes_sorted = nodes_sorted[:max_nodes]

        for node in nodes_sorted:
            label = graph.nodes[node].get("label", node)
            ntype = graph.nodes[node].get("type", "?")
            indeg = in_deg.get(node, 0)
            outdeg = out_deg.get(node, 0)
            lines.append(f"  [{ntype:6s}] {label:40s} ←in:{indeg:4d}  out→:{outdeg:4d}")

        lines.append("")
        lines.append("  Top edges:")
        edges_sorted = sorted(graph.edges(data=True), key=lambda e: -e[2].get("confidence", 0))
        for src, dst, data in edges_sorted[:30]:
            src_label = graph.nodes[src].get("label", src)
            dst_label = graph.nodes[dst].get("label", dst)
            ev = data.get("evidence", "")[:30]
            lines.append(f"    {src_label:25s} ──{data.get('edge_type',''):10s}→ {dst_label:25s}  {ev}")
        lines.append("")
        return "\n".join(lines)

    def render_hub_analysis(self, graph, title):
        lines = [f"  === {title} — Hub Analysis ===", ""]
        in_deg = dict(graph.in_degree())
        out_deg = dict(graph.out_degree())
        total_deg = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in graph.nodes()}

        lines.append("  Top 20 hubs (by total degree):")
        for node, deg in sorted(total_deg.items(), key=lambda x: -x[1])[:20]:
            label = graph.nodes[node].get("label", node)
            ntype = graph.nodes[node].get("type", "?")
            lines.append(f"    [{ntype:6s}] {label:40s} degree={deg:4d} (in={in_deg.get(node,0):3d} out={out_deg.get(node,0):3d})")

        lines.append("")
        lines.append("  Top 10 fan-out nodes (most outgoing edges):")
        for node, deg in sorted(out_deg.items(), key=lambda x: -x[1])[:10]:
            label = graph.nodes[node].get("label", node)
            lines.append(f"    {label:40s} out→={deg:4d}")

        lines.append("")
        lines.append("  Top 10 fan-in nodes (most incoming edges):")
        for node, deg in sorted(in_deg.items(), key=lambda x: -x[1])[:10]:
            label = graph.nodes[node].get("label", node)
            lines.append(f"    {label:40s} ←in={deg:4d}")

        if graph.number_of_nodes() > 0:
            lines.append("")
            lines.append(f"  Density: {nx.density(graph):.4f}")
            sccs = list(nx.strongly_connected_components(graph))
            if sccs:
                biggest = max(sccs, key=len)
                lines.append(f"  Strongly connected components: {len(sccs)}")
                if len(biggest) > 1:
                    lines.append(f"  Biggest SCC: {len(biggest)} nodes")
                    for n in list(biggest)[:10]:
                        lines.append(f"    - {graph.nodes[n].get('label', n)}")

        lines.append("")
        return "\n".join(lines)

    def export_graphml(self, graph, filename):
        out_dir = self._p("output_dir")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, filename)
        nx.write_graphml(graph, path)
        return (1, path, None)

    def export_json(self, graph, filename):
        out_dir = self._p("output_dir")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, filename)
        nodes = []
        for node, data in graph.nodes(data=True):
            nodes.append({"id": node, "label": data.get("label", node), "type": data.get("type", "?")})
        edges = []
        for src, dst, data in graph.edges(data=True):
            edges.append({"source": src, "target": dst, "edge_type": data.get("edge_type", ""),
                          "evidence": data.get("evidence", ""), "confidence": data.get("confidence", 0)})
        payload = {"nodes": nodes, "edges": edges}
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        return (1, path, None)

    def render_image(self, graph, edge_type, fmt="png", max_nodes=200, max_edges=500):
        out_dir = self._p("output_dir")
        images_dir = os.path.join(out_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        g = graph
        if g.number_of_nodes() > max_nodes:
            in_deg = dict(g.in_degree())
            out_deg = dict(g.out_degree())
            nodes_sorted = sorted(g.nodes(), key=lambda n: -(in_deg.get(n, 0) + out_deg.get(n, 0)))[:max_nodes]
            g = g.subgraph(nodes_sorted).copy()
        if g.number_of_edges() > max_edges:
            edges = list(g.edges(data=True))[:max_edges]
            g = nx.DiGraph()
            for src, dst, data in edges:
                g.add_node(src, **graph.nodes[src])
                g.add_node(dst, **graph.nodes[dst])
                g.add_edge(src, dst, **data)

        edge_color = EDGE_COLORS.get(edge_type, "#666666")

        for node, data in g.nodes(data=True):
            ntype = data.get("type", "method")
            data["color"] = NODE_COLORS.get(ntype, "#f3f4f6")
            data["style"] = "filled"
            data["shape"] = "box"
            data["fontsize"] = "10"
            data["label"] = data.get("label", node)
            data["fontname"] = "Helvetica"

        for src, dst, data in g.edges(data=True):
            data["color"] = edge_color
            data["arrowsize"] = "0.7"
            data["penwidth"] = "1.0"

        try:
            agraph = to_agraph(g)
        except Exception as e:
            return (0, None, ("AGRAPH_FAIL", str(e), 0))

        agraph.graph_attr.update(
            bgcolor="white",
            overlap="false",
            splines="true",
            pad="0.5",
            label=f"{edge_type} graph ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)",
            labelloc="t",
            fontsize="14",
            fontname="Helvetica-Bold",
        )
        agraph.node_attr.update(fontname="Helvetica", fontsize="10")
        agraph.edge_attr.update(fontname="Helvetica", fontsize="8")

        if graph.number_of_nodes() > 100:
            agraph.graph_attr.update(layout="sfdp", overlap="prism", sep="+10")
            engine = "sfdp"
        elif graph.number_of_nodes() > 30:
            agraph.graph_attr.update(layout="neato", overlap="false")
            engine = "neato"
        else:
            agraph.graph_attr.update(rankdir="LR", layout="dot")
            engine = "dot"

        base = os.path.join(images_dir, edge_type)
        dot_path = base + ".dot"
        agraph.write(dot_path)

        try:
            if fmt == "svg":
                out_path = base + ".svg"
                subprocess.run([engine, "-Tsvg", dot_path, "-o", out_path],
                               check=True, capture_output=True, timeout=120)
            else:
                out_path = base + ".png"
                subprocess.run([engine, "-Tpng", "-Gdpi=150", dot_path, "-o", out_path],
                               check=True, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            return (0, None, ("TIMEOUT", f"graphviz timed out on {edge_type}", 0))
        except subprocess.CalledProcessError as e:
            return (0, None, ("DOT_FAIL", e.stderr.decode("utf-8", errors="replace")[:200], 0))

        return (1, out_path, None)

    def render_all_images(self, params):
        graphs = self._p("graphs")
        fmt = params.get("format", "png") if isinstance(params, dict) else "png"
        results = []
        for edge_type, graph in sorted(graphs.items(), key=lambda x: -x[1].number_of_edges()):
            ok, path, err = self.render_image(graph, edge_type, fmt=fmt)
            results.append({"edge_type": edge_type, "ok": ok, "path": path, "error": err})
        merged = self._p("merged_graph")
        if merged:
            ok, path, err = self.render_image(merged, "merged_all", fmt=fmt, max_nodes=300, max_edges=800)
            results.append({"edge_type": "merged_all", "ok": ok, "path": path, "error": err})
        return (1, results, None)

    def Run(self, command, params=None):
        params = params or {}
        if command == "load":
            return self.load_edges()
        elif command == "build":
            return self.build_graphs()
        elif command == "build_merged":
            return self.build_merged_graph()
        elif command == "render_all":
            return self._render_all(params)
        elif command == "export_all":
            return self._export_all(params)
        elif command == "render_images":
            return self.render_all_images(params)
        elif command == "status":
            return self._status()
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _render_all(self, params):
        out_dir = self._p("output_dir")
        os.makedirs(out_dir, exist_ok=True)
        graphs = self._p("graphs")
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("  GRAPH RENDERING REPORT — dom_graph_work.db")
        report_lines.append("=" * 80)
        report_lines.append("")

        stats = self._p("stats")
        report_lines.append("  Graphs found in edges table:")
        for et, st in sorted(stats.items(), key=lambda x: -x[1]["edges"]):
            report_lines.append(f"    {et:20s}  nodes={st['nodes']:5d}  edges={st['edges']:5d}")
        report_lines.append("")

        for edge_type, graph in sorted(graphs.items(), key=lambda x: -x[1].number_of_edges()):
            title = f"GRAPH: {edge_type.upper()}"
            report_lines.append(self.render_ascii(graph, title))
            report_lines.append(self.render_hub_analysis(graph, title))

        merged = self._p("merged_graph")
        if merged:
            report_lines.append(self.render_ascii(merged, "MERGED GRAPH (all edge types)"))
            report_lines.append(self.render_hub_analysis(merged, "MERGED GRAPH"))

        report_text = "\n".join(report_lines)
        report_path = os.path.join(out_dir, "GRAPH_REPORT.txt")
        with open(report_path, "w") as f:
            f.write(report_text)
        self.state["report_path"] = report_path
        return (1, {"report_path": report_path, "graphs": len(graphs)}, None)

    def _export_all(self, params):
        out_dir = self._p("output_dir")
        os.makedirs(out_dir, exist_ok=True)
        graphs = self._p("graphs")
        exported = []
        for edge_type, graph in graphs.items():
            ok1, p1, _ = self.export_graphml(graph, f"{edge_type}.graphml")
            ok2, p2, _ = self.export_json(graph, f"{edge_type}.json")
            exported.append({"edge_type": edge_type, "graphml": p1, "json": p2})
        merged = self._p("merged_graph")
        if merged:
            self.export_graphml(merged, "merged_all.graphml")
            self.export_json(merged, "merged_all.json")
            exported.append({"edge_type": "merged", "graphml": os.path.join(out_dir, "merged_all.graphml"),
                             "json": os.path.join(out_dir, "merged_all.json")})
        return (1, exported, None)

    def _status(self):
        stats = self._p("stats")
        return (1, stats, None)


def main():
    parser = argparse.ArgumentParser(description="Render graphs from dom_graph_work.db")
    parser.add_argument("--db", default=DB_PATH, help="SQLite DB path")
    parser.add_argument("--out", default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--command", default="all",
                        choices=["all", "status", "render", "export", "images"],
                        help="What to do")
    parser.add_argument("--format", default="png", choices=["png", "svg"],
                        help="Image format (for --command images)")
    args = parser.parse_args()

    renderer = GraphRenderer(db=args.db, param=args.out)
    renderer.Run("load")
    renderer.Run("build")
    renderer.Run("build_merged")

    if args.command in ("all", "render"):
        ok, data, err = renderer.Run("render_all")
        if err:
            sys.stderr.write(f"RENDER FAIL: {err}\n")
            sys.exit(1)
        print(f"Report written: {data['report_path']}")
        print(f"Graphs rendered: {data['graphs']}")

    if args.command in ("all", "export"):
        ok, data, err = renderer.Run("export_all")
        if err:
            sys.stderr.write(f"EXPORT FAIL: {err}\n")
            sys.exit(1)
        print(f"\nExported {len(data)} graphs:")
        for item in data:
            print(f"  {item['edge_type']:20s} → {item['graphml']}")
            print(f"  {'':20s}   {item['json']}")

    if args.command in ("all", "images"):
        ok, data, err = renderer.Run("render_images", {"format": args.format})
        if err:
            sys.stderr.write(f"IMAGE FAIL: {err}\n")
            sys.exit(1)
        print(f"\nRendered {len(data)} images ({args.format}):")
        for item in data:
            status = "OK" if item["ok"] else "FAIL"
            path = item["path"] or item["error"]
            print(f"  [{status}] {item['edge_type']:20s} → {path}")

    if args.command == "status":
        ok, stats, err = renderer.Run("status")
        if err:
            sys.stderr.write(f"STATUS FAIL: {err}\n")
            sys.exit(1)
        print("Graphs in DB:")
        for et, st in sorted(stats.items(), key=lambda x: -x[1]["edges"]):
            print(f"  {et:20s}  nodes={st['nodes']:5d}  edges={st['edges']:5d}")


if __name__ == "__main__":
    main()
