#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/CodebaseGrapher.py
#[@SUMMARY] Graphs the CODEBASE MySQL database: tables, row counts, relationships, and data flow. Generates an SVG visualization showing the full schema graph with node sizes proportional to row counts.
#[@CLASS] CodebaseGrapher
#[@METHOD] Run, _QueryCounts, _QuerySchema, _BuildGraph, _RenderSvg, _RenderDot
#[@AUTHORITY] visualization
#[@DOMAIN] dom_gui

import sys
import mysql.connector
import os

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "CODEBASE",
}

OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui"

TABLE_RELATIONSHIPS = [
    ("directories", "python_files", "path_id->id", "contains"),
    ("directories", "c_files", "path_id->id", "contains"),
    ("directories", "swift_files", "path_id->id", "contains"),
    ("directories", "csharp_files", "path_id->id", "contains"),
    ("directories", "markdown_files", "path_id->id", "contains"),
    ("directories", "json_files", "path_id->id", "contains"),
    ("directories", "yaml_files", "path_id->id", "contains"),
    ("directories", "directories", "parent_id->id", "parent_of"),
    ("python_files", "python_class_index", "id->file_id", "defines_class"),
    ("python_files", "file_checkpoint", "content_hash->content_hash", "checkpointed"),
    ("python_files", "ingestion_jobs", "full_path->file_path", "ingested"),
    ("c_files", "file_checkpoint", "content_hash->content_hash", "checkpointed"),
    ("c_files", "ingestion_jobs", "full_path->file_path", "ingested"),
    ("computational_units", "python_class_index", "class_id->file_id", "instantiates"),
    ("file_archive", "file_checkpoint", "full_path->full_path", "archived_from"),
    ("ingestion_jobs", "file_checkpoint", "file_path->full_path", "produces"),
    ("tune_history", "computational_units", "tune_id->unit_id", "tuned"),
]

TABLE_CATEGORIES = {
    "file_storage": ["python_files", "c_files", "swift_files", "csharp_files",
                     "markdown_files", "json_files", "yaml_files"],
    "index": ["python_class_index", "python_baseclass_index",
              "python_decorator_index", "python_import_index",
              "python_method_index", "python_run_index", "python_index_state"],
    "tracking": ["file_checkpoint", "ingestion_jobs", "file_archive",
                 "directories", "ingest_solutions"],
    "semantic": ["computational_units", "tune_history"],
}

CATEGORY_COLORS = {
    "file_storage": "#4A90D9",
    "index": "#F5A623",
    "tracking": "#7ED321",
    "semantic": "#D0021B",
    "other": "#9B9B9B",
}

CATEGORY_LABELS = {
    "file_storage": "File Storage",
    "index": "Index",
    "tracking": "Tracking",
    "semantic": "Semantic",
    "other": "Other",
}

def Run(command, params=None):
    if command == "graph":
        return _BuildGraph(params or {})
    elif command == "read_state":
        return (1, {"status": "ready"}, None)
    elif command == "set_config":
        return (1, True, None)
    return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))

def _QueryCounts():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    for t in tables:
        cur.execute("SELECT COUNT(*) FROM `%s`" % t)
        counts[t] = cur.fetchone()[0]
    cur.close()
    conn.close()
    return counts

def _GetCategory(table):
    for cat, tbls in TABLE_CATEGORIES.items():
        if table in tbls:
            return cat
    return "other"

def _BuildGraph(params):
    counts = _QueryCounts()
    svg = _RenderSvg(counts)
    svg_path = os.path.join(OUTPUT_DIR, "codebase_graph.svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    dot = _RenderDot(counts)
    dot_path = os.path.join(OUTPUT_DIR, "codebase_graph.dot")
    with open(dot_path, "w") as f:
        f.write(dot)

    total_rows = sum(counts.values())
    summary_lines = []
    summary_lines.append("CODEBASE Database Graph")
    summary_lines.append("=" * 60)
    summary_lines.append("")
    summary_lines.append("Tables: %d" % len(counts))
    summary_lines.append("Total rows: %s" % format(total_rows, ","))
    summary_lines.append("")
    summary_lines.append("By category:")
    for cat in ["file_storage", "index", "tracking", "semantic", "other"]:
        cat_tables = [(t, c) for t, c in counts.items() if _GetCategory(t) == cat]
        cat_total = sum(c for _, c in cat_tables)
        summary_lines.append("  %-14s %3d tables, %15s rows" % (
            CATEGORY_LABELS[cat], len(cat_tables), format(cat_total, ",")))
    summary_lines.append("")
    summary_lines.append("Top 10 tables by row count:")
    sorted_tables = sorted(counts.items(), key=lambda x: -x[1])
    for t, c in sorted_tables[:10]:
        summary_lines.append("  %-30s %15s rows [%s]" % (
            t, format(c, ","), _GetCategory(t)))
    summary_lines.append("")
    summary_lines.append("Relationships: %d" % len(TABLE_RELATIONSHIPS))
    summary_lines.append("")
    summary_lines.append("Output:")
    summary_lines.append("  SVG: %s" % svg_path)
    summary_lines.append("  DOT: %s" % dot_path)

    summary = "\n".join(summary_lines)
    print(summary)
    return (1, {"svg": svg_path, "dot": dot_path, "summary": summary,
                 "counts": counts, "total_rows": total_rows}, None)

def _RenderSvg(counts):
    max_count = max(counts.values()) if counts else 1
    width = 1400
    height = 900

    positions = {
        "python_files": (200, 150),
        "c_files": (200, 280),
        "swift_files": (200, 380),
        "csharp_files": (200, 460),
        "markdown_files": (200, 530),
        "json_files": (200, 600),
        "yaml_files": (200, 670),
        "directories": (500, 150),
        "file_checkpoint": (800, 150),
        "ingestion_jobs": (800, 300),
        "file_archive": (800, 430),
        "ingest_solutions": (800, 520),
        "python_class_index": (1100, 150),
        "python_baseclass_index": (1100, 250),
        "python_decorator_index": (1100, 320),
        "python_import_index": (1100, 390),
        "python_method_index": (1100, 460),
        "python_run_index": (1100, 530),
        "python_index_state": (1100, 600),
        "computational_units": (500, 600),
        "tune_history": (500, 700),
    }

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (
        width, height, width, height))
    lines.append('<rect width="100%%" height="100%%" fill="#1a1a2e"/>')

    lines.append('<text x="700" y="40" text-anchor="middle" fill="#ffffff" font-family="Menlo" font-size="24" font-weight="bold">CODEBASE Database Graph</text>')
    lines.append('<text x="700" y="65" text-anchor="middle" fill="#888888" font-family="Menlo" font-size="14">%d tables, %s total rows</text>' % (
        len(counts), format(sum(counts.values()), ",")))

    for cat, color in CATEGORY_COLORS.items():
        cx = 50 + list(CATEGORY_COLORS.keys()).index(cat) * 250
        lines.append('<rect x="%d" y="830" width="14" height="14" fill="%s" rx="2"/>' % (cx, color))
        lines.append('<text x="%d" y="842" fill="#cccccc" font-family="Menlo" font-size="12">%s</text>' % (cx + 20, CATEGORY_LABELS[cat]))

    for src, dst, _, rel in TABLE_RELATIONSHIPS:
        if src in positions and dst in positions:
            sx, sy = positions[src]
            dx, dy = positions[dst]
            mx, my = (sx + dx) / 2, (sy + dy) / 2
            lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#444466" stroke-width="1" stroke-dasharray="3,2"/>' % (
                sx, sy, dx, dy))
            lines.append('<text x="%d" y="%d" fill="#555577" font-family="Menlo" font-size="9" text-anchor="middle">%s</text>' % (
                mx, my - 3, rel))

    for table, count in counts.items():
        if table not in positions:
            continue
        x, y = positions[table]
        cat = _GetCategory(table)
        color = CATEGORY_COLORS[cat]
        radius = max(12, min(45, 12 + (count / max_count) * 33))

        lines.append('<circle cx="%d" cy="%d" r="%d" fill="%s" fill-opacity="0.3" stroke="%s" stroke-width="2"/>' % (
            x, y, radius, color, color))

        lines.append('<text x="%d" y="%d" text-anchor="middle" fill="#ffffff" font-family="Menlo" font-size="10" font-weight="bold">%s</text>' % (
            x, y - 2, table.replace("_", " ")[:18]))
        lines.append('<text x="%d" y="%d" text-anchor="middle" fill="#aaaaaa" font-family="Menlo" font-size="9">%s</text>' % (
            x, y + 10, format(count, ",")))

    lines.append('</svg>')
    return "\n".join(lines)

def _RenderDot(counts):
    lines = []
    lines.append("digraph CODEBASE {")
    lines.append("  rankdir=LR;")
    lines.append('  bgcolor="#1a1a2e";')
    lines.append('  node [fontname="Menlo", fontsize=10, style="filled"];')
    lines.append('  edge [fontname="Menlo", fontsize=8, color="#666688"];')
    lines.append("")

    for table, count in counts.items():
        cat = _GetCategory(table)
        color = CATEGORY_COLORS[cat]
        label = "%s\\n%s rows" % (table, format(count, ","))
        lines.append('  "%s" [label="%s", fillcolor="%s", fontcolor="#ffffff"];' % (
            table, label, color))

    lines.append("")
    for src, dst, keys, rel in TABLE_RELATIONSHIPS:
        lines.append('  "%s" -> "%s" [label="%s"];' % (src, dst, rel))

    lines.append("")
    lines.append("  subgraph cluster_file {")
    lines.append('    label="File Storage"; bgcolor="#2a2a4e";')
    for t in TABLE_CATEGORIES["file_storage"]:
        if t in counts:
            lines.append('    "%s";' % t)
    lines.append("  }")

    lines.append("  subgraph cluster_index {")
    lines.append('    label="Index"; bgcolor="#2e2a1e";')
    for t in TABLE_CATEGORIES["index"]:
        if t in counts:
            lines.append('    "%s";' % t)
    lines.append("  }")

    lines.append("  subgraph cluster_track {")
    lines.append('    label="Tracking"; bgcolor="#1e2e1e";')
    for t in TABLE_CATEGORIES["tracking"]:
        if t in counts:
            lines.append('    "%s";' % t)
    lines.append("  }")

    lines.append("}")
    return "\n".join(lines)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "graph"
    result = Run(cmd, {})
    if result[0] != 1:
        print("Error:", result[2])
        sys.exit(1)
