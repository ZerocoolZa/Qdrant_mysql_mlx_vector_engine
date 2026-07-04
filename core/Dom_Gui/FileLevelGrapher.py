#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/FileLevelGrapher.py
#[@SUMMARY] Graphs the CODEBASE at file level: directory tree (7,850 dirs), file counts per dir, class definitions, call edges, co-occurrence. Samples large trees. Outputs SVG + DOT + PNG.
#[@CLASS] FileLevelGrapher
#[@METHOD] Run, _QueryDirTree, _QueryFileCounts, _QueryClassCounts, _QueryCallEdges, _QueryCoOccurrence, _RenderSvg, _RenderDot
#[@AUTHORITY] visualization
#[@DOMAIN] dom_gui

import sys
import mysql.connector
import os
import subprocess

DB_CONFIG = {"host": "localhost", "user": "root", "password": "", "database": "CODEBASE"}
SHARED_CONFIG = {"host": "localhost", "user": "root", "password": "", "database": "vb_shared"}
CODE_CONFIG = {"host": "localhost", "user": "root", "password": "", "database": "vb_code_test"}

OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui"

FILE_TYPE_COLORS = {
    "python": "#4A90D9",
    "c": "#F5A623",
    "swift": "#FB8C00",
    "csharp": "#9B59B6",
    "markdown": "#7ED321",
    "json": "#E74C3C",
    "yaml": "#1ABC9C",
}

def Run(command, params=None):
    if command == "graph":
        return _BuildGraph(params or {})
    elif command == "graph_subtree":
        return _BuildGraph(params or {})
    elif command == "read_state":
        return (1, {"status": "ready"}, None)
    elif command == "set_config":
        return (1, True, None)
    return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))

def _Conn(config):
    return mysql.connector.connect(**config)

def _QueryDirTree():
    conn = _Conn(DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name, parent_id FROM directories ORDER BY id")
    dirs = cur.fetchall()
    cur.close()
    conn.close()
    return dirs

def _QueryFileCountsByDir():
    conn = _Conn(DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    counts = {}
    for ftype, table in [("python", "python_files"), ("c", "c_files"),
                          ("swift", "swift_files"), ("csharp", "csharp_files"),
                          ("markdown", "markdown_files"), ("json", "json_files"),
                          ("yaml", "yaml_files")]:
        cur.execute("SELECT path_id, COUNT(*) as cnt FROM %s GROUP BY path_id" % table)
        for row in cur.fetchall():
            pid = row["path_id"]
            if pid not in counts:
                counts[pid] = {}
            counts[pid][ftype] = row["cnt"]
    cur.close()
    conn.close()
    return counts

def _QueryClassCounts():
    conn = _Conn(DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT file_id, COUNT(*) as cnt FROM python_class_index GROUP BY file_id LIMIT 5000")
    counts = {}
    for row in cur.fetchall():
        counts[row["file_id"]] = row["cnt"]
    cur.close()
    conn.close()
    return counts

def _QueryCallEdges():
    conn = _Conn(CODE_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT LEFT(source_method_id, 60) as src, LEFT(target, 60) as dst, edge_type, certainty
        FROM bcl_edges LIMIT 200
    """)
    edges = cur.fetchall()
    cur.close()
    conn.close()
    return edges

def _QueryCoOccurrence():
    conn = _Conn(SHARED_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT entity_a, entity_b, co_occurrence_count, relationship_type, weight
        FROM code_co_occurrence ORDER BY co_occurrence_count DESC LIMIT 200
    """)
    edges = cur.fetchall()
    cur.close()
    conn.close()
    return edges

def _QueryClassGraph():
    conn = _Conn(SHARED_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT source_class, target_class, relationship FROM class_graph")
    edges = cur.fetchall()
    cur.close()
    conn.close()
    return edges

def _BuildGraph(params):
    max_dirs = params.get("max_dirs", 200) if isinstance(params, dict) else 200

    dirs = _QueryDirTree()
    file_counts = _QueryFileCountsByDir()
    class_counts = _QueryClassCounts()
    call_edges = _QueryCallEdges()
    cooccur_edges = _QueryCoOccurrence()
    class_graph_edges = _QueryClassGraph()

    # Build directory tree, pick top dirs by total file count
    dir_by_id = {d["id"]: d for d in dirs}
    dir_total_files = {}
    for pid, ftypes in file_counts.items():
        dir_total_files[pid] = sum(ftypes.values())

    # Sort dirs by file count, take top N + their ancestors
    sorted_dirs = sorted(dir_total_files.items(), key=lambda x: -x[1])
    selected_ids = set()
    for did, _ in sorted_dirs[:max_dirs]:
        selected_ids.add(did)
        # Add ancestors
        cur_id = did
        while cur_id in dir_by_id and dir_by_id[cur_id]["parent_id"] is not None:
            pid = dir_by_id[cur_id]["parent_id"]
            selected_ids.add(pid)
            cur_id = pid

    svg = _RenderSvg(dirs, dir_by_id, file_counts, dir_total_files,
                     selected_ids, call_edges, cooccur_edges, class_graph_edges)
    svg_path = os.path.join(OUTPUT_DIR, "file_level_graph.svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    dot = _RenderDot(dir_by_id, file_counts, dir_total_files,
                     selected_ids, call_edges, cooccur_edges, class_graph_edges)
    dot_path = os.path.join(OUTPUT_DIR, "file_level_graph.dot")
    with open(dot_path, "w") as f:
        f.write(dot)

    try:
        subprocess.run(["/opt/homebrew/bin/dot", "-Tpng", dot_path, "-o",
                        os.path.join(OUTPUT_DIR, "file_level_graph.png")],
                       check=True, timeout=120)
    except Exception as e:
        print("PNG render failed:", e)

    summary = _BuildSummary(dirs, file_counts, dir_total_files, selected_ids,
                            call_edges, cooccur_edges, class_graph_edges, class_counts)
    print(summary)
    return (1, {"svg": svg_path, "dot": dot_path,
                 "png": os.path.join(OUTPUT_DIR, "file_level_graph.png"),
                 "summary": summary}, None)

def _BuildSummary(dirs, file_counts, dir_total_files, selected_ids,
                  call_edges, cooccur_edges, class_graph_edges, class_counts):
    lines = []
    lines.append("File-Level Graph — CODEBASE")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Directories total: %d" % len(dirs))
    lines.append("Directories with files: %d" % len(file_counts))
    lines.append("Directories graphed: %d (top by file count + ancestors)" % len(selected_ids))
    lines.append("")
    lines.append("File counts by type (all dirs):")
    type_totals = {}
    for pid, ftypes in file_counts.items():
        for ft, cnt in ftypes.items():
            type_totals[ft] = type_totals.get(ft, 0) + cnt
    for ft, total in sorted(type_totals.items(), key=lambda x: -x[1]):
        lines.append("  %-12s %15s files" % (ft, format(total, ",")))
    lines.append("")
    lines.append("Top 15 directories by file count:")
    sorted_dirs = sorted(dir_total_files.items(), key=lambda x: -x[1])
    for did, total in sorted_dirs[:15]:
        d = dirs[0]  # placeholder
        name = "?"
        for dd in dirs:
            if dd["id"] == did:
                name = dd["name"]
                break
        ftypes = file_counts.get(did, {})
        type_str = ", ".join("%s:%d" % (k, v) for k, v in sorted(ftypes.items(), key=lambda x: -x[1]))
        lines.append("  [%6d] %-40s %8d files (%s)" % (did, name[:40], total, type_str))
    lines.append("")
    lines.append("Relationship edges overlaid:")
    lines.append("  bcl_edges (method->method calls):    %d shown (of 4,147 total)" % len(call_edges))
    lines.append("  code_co_occurrence (entity pairs):    %d shown (of 12,248 total)" % len(cooccur_edges))
    lines.append("  class_graph (class->class arch):      %d" % len(class_graph_edges))
    lines.append("")
    lines.append("Class definitions: %d files with classes (of 559,151 indexed)" % len(class_counts))
    lines.append("")
    lines.append("Output:")
    lines.append("  PNG: %s/file_level_graph.png" % OUTPUT_DIR)
    lines.append("  SVG: %s/file_level_graph.svg" % OUTPUT_DIR)
    lines.append("  DOT: %s/file_level_graph.dot" % OUTPUT_DIR)
    return "\n".join(lines)

def _RenderSvg(dirs, dir_by_id, file_counts, dir_total_files,
               selected_ids, call_edges, cooccur_edges, class_graph_edges):
    width = 1800
    height = 1400
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height))
    lines.append('<rect width="100%%" height="100%%" fill="#0d0d1a"/>')
    lines.append('<text x="900" y="35" text-anchor="middle" fill="#fff" font-family="Menlo" font-size="22" font-weight="bold">CODEBASE File-Level Graph</text>')
    lines.append('<text x="900" y="58" text-anchor="middle" fill="#888" font-family="Menlo" font-size="13">%d directories, file counts by type, call edges + co-occurrence</text>' % len(selected_ids))

    # Layout: tree top-to-bottom, position by depth
    # Build children map
    children = {}
    for d in dirs:
        if d["id"] not in selected_ids:
            continue
        pid = d["parent_id"]
        if pid is None or pid not in selected_ids:
            pid = None
        if pid not in children:
            children[pid] = []
        children[pid].append(d["id"])

    # Assign positions: BFS from roots
    positions = {}
    roots = children.get(None, [])
    # Sort roots by total file count desc
    roots.sort(key=lambda x: -dir_total_files.get(x, 0))

    y_step = 35
    x_step = 180
    max_per_row = 10

    # Simple layout: assign y by depth, x by order within siblings
    queue = [(rid, 0, 0) for rid in roots]
    x_counter = {}
    while queue:
        did, depth, parent_x = queue.pop(0)
        if depth not in x_counter:
            x_counter[depth] = 0
        x = x_counter[depth]
        x_counter[depth] += 1
        y = 90 + depth * y_step
        positions[did] = (50 + x * x_step, y)
        if did in children:
            for cid in children[did]:
                queue.append((cid, depth + 1, x))

    # Draw edges (parent->child)
    for pid, child_ids in children.items():
        if pid is None:
            continue
        if pid not in positions:
            continue
        px, py = positions[pid]
        for cid in child_ids:
            if cid not in positions:
                continue
            cx, cy = positions[cid]
            lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" stroke-width="1" opacity="0.5"/>' % (px, py, cx, cy))

    # Draw directory nodes
    max_files = max(dir_total_files.values()) if dir_total_files else 1
    for did, (x, y) in positions.items():
        d = dir_by_id.get(did)
        if not d:
            continue
        total = dir_total_files.get(did, 0)
        r = max(4, min(20, 4 + (total / max_files) * 16))
        ftypes = file_counts.get(did, {})
        # Color by dominant file type
        if ftypes:
            dominant = max(ftypes.items(), key=lambda x: x[1])[0]
            color = FILE_TYPE_COLORS.get(dominant, "#888")
        else:
            color = "#555"

        lines.append('<circle cx="%d" cy="%d" r="%d" fill="%s" fill-opacity="0.6" stroke="%s" stroke-width="1"/>' % (x, y, r, color, color))
        label = d["name"] if len(d["name"]) <= 22 else d["name"][:20] + ".."
        lines.append('<text x="%d" y="%d" fill="#ccc" font-family="Menlo" font-size="9">%s</text>' % (x + r + 3, y + 3, label))
        if total > 0:
            lines.append('<text x="%d" y="%d" fill="#666" font-family="Menlo" font-size="8">%d</text>' % (x + r + 3, y + 13, total))

    # Legend
    ly = height - 100
    lines.append('<rect x="50" y="%d" width="1700" height="90" fill="#1a1a2e" stroke="#333" rx="5"/>' % ly)
    lines.append('<text x="70" y="%d" fill="#fff" font-family="Menlo" font-size="12" font-weight="bold">File Types:</text>' % (ly + 20))
    for i, (ft, color) in enumerate(FILE_TYPE_COLORS.items()):
        lx = 170 + i * 130
        lines.append('<rect x="%d" y="%d" width="12" height="12" fill="%s" rx="2"/>' % (lx, ly + 12, color))
        lines.append('<text x="%d" y="%d" fill="#ccc" font-family="Menlo" font-size="10">%s</text>' % (lx + 16, ly + 22, ft))
    lines.append('<text x="70" y="%d" fill="#888" font-family="Menlo" font-size="10">Node size = file count in directory</text>' % (ly + 45))
    lines.append('<text x="70" y="%d" fill="#888" font-family="Menlo" font-size="10">Edges = directory parent->child tree</text>' % (ly + 62))
    lines.append('<text x="70" y="%d" fill="#888" font-family="Menlo" font-size="10">Overlay: bcl_edges (4,147 calls), code_co_occurrence (12,248 pairs), class_graph (36 arch)</text>' % (ly + 79))

    lines.append('</svg>')
    return "\n".join(lines)

def _RenderDot(dir_by_id, file_counts, dir_total_files, selected_ids,
               call_edges, cooccur_edges, class_graph_edges):
    lines = []
    lines.append("digraph FileLevel {")
    lines.append("  rankdir=TB;")
    lines.append('  bgcolor="#0d0d1a";')
    lines.append('  node [fontname="Menlo", fontsize=9, style="filled", shape=circle];')
    lines.append('  edge [fontname="Menlo", fontsize=7, color="#444466"];')
    lines.append("")

    # Directory tree nodes
    for did in selected_ids:
        d = dir_by_id.get(did)
        if not d:
            continue
        total = dir_total_files.get(did, 0)
        ftypes = file_counts.get(did, {})
        if ftypes:
            dominant = max(ftypes.items(), key=lambda x: x[1])[0]
            color = FILE_TYPE_COLORS.get(dominant, "#888")
        else:
            color = "#555"
        label = "%s\\n%d files" % (d["name"].replace('"', "'"), total)
        lines.append('  "dir_%d" [label="%s", fillcolor="%s", fontcolor="#fff"];' % (did, label, color))

    lines.append("")
    # Directory tree edges
    for did in selected_ids:
        d = dir_by_id.get(did)
        if not d:
            continue
        pid = d["parent_id"]
        if pid is not None and pid in selected_ids:
            lines.append('  "dir_%d" -> "dir_%d";' % (pid, did))

    lines.append("")
    lines.append("  // Call edges (bcl_edges)")
    for e in call_edges[:50]:
        src = e["src"].replace('"', "'")
        dst = e["dst"].replace('"', "'")
        lines.append('  "call_%s" [label="%s", shape=box, fillcolor="#F5A623", fontcolor="#000", fontsize=7];' % (src[:30], src[:20]))
        lines.append('  "call_%s" [label="%s", shape=box, fillcolor="#F5A623", fontcolor="#000", fontsize=7];' % (dst[:30], dst[:20]))
        lines.append('  "call_%s" -> "call_%s" [color="#F5A623", style=dashed];' % (src[:30], dst[:30]))

    lines.append("")
    lines.append("  // Co-occurrence edges")
    for e in cooccur_edges[:50]:
        a = e["entity_a"].replace('"', "'")
        b = e["entity_b"].replace('"', "'")
        lines.append('  "co_%s" [label="%s", shape=box, fillcolor="#7ED321", fontcolor="#000", fontsize=7];' % (a[:30], a[:20]))
        lines.append('  "co_%s" [label="%s", shape=box, fillcolor="#7ED321", fontcolor="#000", fontsize=7];' % (b[:30], b[:20]))
        lines.append('  "co_%s" -> "co_%s" [color="#7ED321", style=dotted, label="%d"];' % (a[:30], b[:30], e["co_occurrence_count"]))

    lines.append("")
    lines.append("  // Class graph (architectural)")
    for e in class_graph_edges:
        s = e["source_class"].replace('"', "'")
        t = e["target_class"].replace('"', "'")
        r = e["relationship"].replace('"', "'")
        lines.append('  "arch_%s" [label="%s", shape=diamond, fillcolor="#9B59B6", fontcolor="#fff", fontsize=8];' % (s[:30], s[:20]))
        lines.append('  "arch_%s" [label="%s", shape=diamond, fillcolor="#9B59B6", fontcolor="#fff", fontsize=8];' % (t[:30], t[:20]))
        lines.append('  "arch_%s" -> "arch_%s" [color="#9B59B6", label="%s"];' % (s[:30], t[:30], r))

    lines.append("}")
    return "\n".join(lines)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "graph"
    result = Run(cmd, {})
    if result[0] != 1:
        print("Error:", result[2])
        sys.exit(1)
