#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/MysqlSchemaGrapher.py
#[@SUMMARY] Graphs the FULL MySQL schema across all 3 databases (CODEBASE, vb_code_test, vb_shared). Shows every table, row count, column count, and cross-database relationships. Outputs SVG + DOT + PNG.
#[@CLASS] MysqlSchemaGrapher
#[@METHOD] Run, _QueryAllTables, _QueryColumns, _DetectRelationships, _RenderSvg, _RenderDot
#[@AUTHORITY] visualization
#[@DOMAIN] dom_gui

import sys
import mysql.connector
import os
import subprocess

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
}

DATABASES = ["CODEBASE", "vb_code_test", "vb_shared"]

OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui"

DB_COLORS = {
    "CODEBASE": "#4A90D9",
    "vb_code_test": "#F5A623",
    "vb_shared": "#7ED321",
}

DB_LABELS = {
    "CODEBASE": "CODEBASE\n(File Store + Index)",
    "vb_code_test": "vb_code_test\n(BCL + MU Engine)",
    "vb_shared": "vb_shared\n(Knowledge + Rules)",
}

# Known cross-database and intra-database relationships
RELATIONSHIPS = [
    # CODEBASE internal
    ("CODEBASE", "directories", "CODEBASE", "python_files", "path_id->id", "contains"),
    ("CODEBASE", "directories", "CODEBASE", "c_files", "path_id->id", "contains"),
    ("CODEBASE", "directories", "CODEBASE", "directories", "parent_id->id", "parent_of"),
    ("CODEBASE", "python_files", "CODEBASE", "python_class_index", "id->file_id", "defines_class"),
    ("CODEBASE", "python_files", "CODEBASE", "file_checkpoint", "content_hash", "checkpointed"),
    ("CODEBASE", "python_files", "CODEBASE", "ingestion_jobs", "full_path", "ingested"),
    ("CODEBASE", "computational_units", "CODEBASE", "python_class_index", "class_id->file_id", "instantiates"),

    # vb_code_test internal
    ("vb_code_test", "vb_classes", "vb_code_test", "vb_methods", "id->class_id", "has_method"),
    ("vb_code_test", "bcl_classes", "vb_code_test", "bcl_methods", "id->class_id", "has_method"),
    ("vb_code_test", "bcl_units", "vb_code_test", "bcl_unit_methods", "unit_id->unit_id", "contains"),
    ("vb_code_test", "bcl_units", "vb_code_test", "bcl_unit_deps", "unit_id->source_unit_id", "depends"),
    ("vb_code_test", "bcl_methods", "vb_code_test", "bcl_edges", "id->bcl_method_id", "calls"),
    ("vb_code_test", "bcl_methods", "vb_code_test", "bcl_stamps", "id->bcl_method_id", "stamped"),
    ("vb_code_test", "bcl_stamps", "vb_code_test", "mu_nodes", "mu_node_id->id", "triggers"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_edges", "id->source_id", "connects"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_events", "id->target_node", "events"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_semantic_tags", "id->node_id", "tagged"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_node_state", "id->node_id", "state"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_packets", "task_id->task_id", "packets"),
    ("vb_code_test", "mu_nodes", "vb_code_test", "mu_execution_state", "task_id->task_id", "exec_state"),

    # vb_shared internal
    ("vb_shared", "know_nodes", "vb_shared", "know_edges", "id->source_id", "connects"),
    ("vb_shared", "know_questions", "vb_shared", "know_answers", "id->question_id", "answered"),
    ("vb_shared", "know_problems", "vb_shared", "know_solutions", "id->problem_id", "solved"),
    ("vb_shared", "know_problems", "vb_shared", "know_causes", "id->problem_id", "caused"),
    ("vb_shared", "know_problems", "vb_shared", "know_fixes", "id->problem_id", "fixed"),
    ("vb_shared", "code_classes", "vb_shared", "code_index", "id->related_entity", "indexed"),
    ("vb_shared", "learned_rules", "vb_shared", "code_index", "id->source_row_id", "indexed"),
    ("vb_shared", "code_classes", "vb_shared", "code_co_occurrence", "class_name->entity_a", "co_occurs"),
    ("vb_shared", "code_classes", "vb_shared", "class_graph", "class_name->source_class", "arch_graph"),
    ("vb_shared", "code_classes", "vb_shared", "class_understandings", "id->code_classes_id", "understood"),
    ("vb_shared", "know_nodes", "vb_shared", "know_memory_units", "id->node_id", "memorized"),
    ("vb_shared", "memory_objects", "vb_shared", "neural_brain_state", "query_key->edge_key", "brain_state"),
    ("vb_shared", "anti_collapse_hypotheses", "vb_shared", "anti_collapse_questions", "investigation_id", "tested"),

    # Cross-database
    ("CODEBASE", "computational_units", "vb_code_test", "bcl_units", "unit_name->unit_id", "maps_to"),
    ("CODEBASE", "python_class_index", "vb_shared", "code_classes", "class_name->class_name", "mirrors"),
    ("vb_code_test", "vb_classes", "vb_shared", "code_classes", "class_name->class_name", "mirrors"),
    ("vb_code_test", "bcl_methods", "vb_shared", "method_inventory", "method_name->method_name", "inventoried"),
    ("vb_code_test", "mu_nodes", "vb_shared", "neural_brain_state", "id->edge_key", "brain_wired"),
    ("vb_shared", "know_lessons", "vb_code_test", "bcl_stamps", "file->goal", "learned_from"),
]

def Run(command, params=None):
    if command == "graph":
        return _BuildGraph(params or {})
    elif command == "read_state":
        return (1, {"status": "ready"}, None)
    elif command == "set_config":
        return (1, True, None)
    return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))

def _QueryAllTables(db):
    conn = mysql.connector.connect(**{**DB_CONFIG, "database": db})
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    col_counts = {}
    for t in tables:
        cur.execute("SELECT COUNT(*) FROM `%s`" % t)
        counts[t] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s'" % (db, t))
        col_counts[t] = cur.fetchone()[0]
    cur.close()
    conn.close()
    return counts, col_counts

def _BuildGraph(params):
    all_data = {}
    for db in DATABASES:
        counts, cols = _QueryAllTables(db)
        all_data[db] = {"counts": counts, "cols": cols}

    svg = _RenderSvg(all_data)
    svg_path = os.path.join(OUTPUT_DIR, "mysql_schema_graph.svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    dot = _RenderDot(all_data)
    dot_path = os.path.join(OUTPUT_DIR, "mysql_schema_graph.dot")
    with open(dot_path, "w") as f:
        f.write(dot)

    try:
        subprocess.run(["/opt/homebrew/bin/dot", "-Tpng", dot_path, "-o",
                        os.path.join(OUTPUT_DIR, "mysql_schema_graph.png")],
                       check=True, timeout=60)
    except Exception as e:
        print("PNG render failed:", e)

    summary = _BuildSummary(all_data)
    print(summary)
    return (1, {"svg": svg_path, "dot": dot_path,
                 "png": os.path.join(OUTPUT_DIR, "mysql_schema_graph.png"),
                 "summary": summary}, None)

def _BuildSummary(all_data):
    lines = []
    lines.append("FULL MySQL Schema Graph")
    lines.append("=" * 70)
    total_tables = 0
    total_rows = 0
    for db in DATABASES:
        d = all_data[db]
        n_tables = len(d["counts"])
        n_rows = sum(d["counts"].values())
        total_tables += n_tables
        total_rows += n_rows
        lines.append("")
        lines.append("%s:" % db)
        lines.append("  Tables: %d, Rows: %s" % (n_tables, format(n_rows, ",")))
        sorted_t = sorted(d["counts"].items(), key=lambda x: -x[1])
        lines.append("  Top 5:")
        for t, c in sorted_t[:5]:
            lines.append("    %-35s %15s rows (%d cols)" % (t, format(c, ","), d["cols"][t]))
    lines.append("")
    lines.append("TOTAL: %d tables, %s rows" % (total_tables, format(total_rows, ",")))
    lines.append("Relationships: %d (cross-db + intra-db)" % len(RELATIONSHIPS))
    lines.append("")
    lines.append("C BCL Graph Units (12):")
    for u in ["bcl_graph_core", "bcl_graph_builder", "bcl_graph_cache",
              "bcl_graph_compiler", "bcl_graph_config", "bcl_graph_expand",
              "bcl_graph_learning", "bcl_graph_optimizer", "bcl_graph_policy",
              "bcl_graph_store", "bcl_graph_trace", "bcl_graph_view"]:
        lines.append("  %s.c" % u)
    lines.append("")
    lines.append("Output:")
    lines.append("  PNG: %s/mysql_schema_graph.png" % OUTPUT_DIR)
    lines.append("  SVG: %s/mysql_schema_graph.svg" % OUTPUT_DIR)
    lines.append("  DOT: %s/mysql_schema_graph.dot" % OUTPUT_DIR)
    return "\n".join(lines)

def _RenderSvg(all_data):
    width = 1800
    height = 1200
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height))
    lines.append('<rect width="100%%" height="100%%" fill="#0d0d1a"/>')

    lines.append('<text x="900" y="35" text-anchor="middle" fill="#ffffff" font-family="Menlo" font-size="22" font-weight="bold">Full MySQL Schema Graph</text>')
    lines.append('<text x="900" y="58" text-anchor="middle" fill="#888" font-family="Menlo" font-size="13">3 databases, all tables, cross-db relationships</text>')

    # DB cluster positions
    db_positions = {
        "CODEBASE": (300, 100),
        "vb_code_test": (900, 100),
        "vb_shared": (300, 650),
    }

    # Draw DB cluster boxes
    for db, (bx, by) in db_positions.items():
        d = all_data[db]
        n = len(d["counts"])
        color = DB_COLORS[db]
        h = max(200, n * 22 + 40)
        lines.append('<rect x="%d" y="%d" width="550" height="%d" fill="%s" fill-opacity="0.05" stroke="%s" stroke-width="2" rx="8"/>' % (
            bx, by, h, color, color))
        lines.append('<text x="%d" y="%d" fill="%s" font-family="Menlo" font-size="14" font-weight="bold">%s</text>' % (
            bx + 15, by + 25, color, DB_LABELS[db]))
        lines.append('<text x="%d" y="%d" fill="#888" font-family="Menlo" font-size="11">%d tables, %s rows</text>' % (
            bx + 15, by + 42, n, format(sum(d["counts"].values()), ",")))

    # Position tables within clusters
    table_positions = {}
    for db, (bx, by) in db_positions.items():
        d = all_data[db]
        sorted_tables = sorted(d["counts"].items(), key=lambda x: -x[1])
        for i, (t, c) in enumerate(sorted_tables):
            tx = bx + 20 + (i % 2) * 270
            ty = by + 60 + (i // 2) * 22
            table_positions[(db, t)] = (tx, ty)

    # Draw relationships
    for src_db, src_tbl, dst_db, dst_tbl, keys, rel in RELATIONSHIPS:
        sk = (src_db, src_tbl)
        dk = (dst_db, dst_tbl)
        if sk in table_positions and dk in table_positions:
            sx, sy = table_positions[sk]
            dx, dy = table_positions[dk]
            color = "#FF4444" if src_db != dst_db else "#444466"
            dash = "5,3" if src_db != dst_db else "3,2"
            lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="%s" opacity="0.4"/>' % (
                sx + 5, sy + 5, dx + 5, dy + 5, color, dash))

    # Draw table nodes
    for db, (bx, by) in db_positions.items():
        d = all_data[db]
        color = DB_COLORS[db]
        max_count = max(d["counts"].values()) if d["counts"] else 1
        for t, c in d["counts"].items():
            tx, ty = table_positions[(db, t)]
            r = max(3, min(10, 3 + (c / max_count) * 7))
            lines.append('<circle cx="%d" cy="%d" r="%d" fill="%s" fill-opacity="0.6"/>' % (tx, ty, r, color))
            label = t if len(t) <= 28 else t[:26] + ".."
            lines.append('<text x="%d" y="%d" fill="#ccc" font-family="Menlo" font-size="9">%s</text>' % (tx + 12, ty + 3, label))
            if c > 0:
                lines.append('<text x="%d" y="%d" fill="#666" font-family="Menlo" font-size="8">%s</text>' % (tx + 12, ty + 13, format(c, ",")))

    # Legend
    ly = height - 80
    lines.append('<rect x="50" y="%d" width="1700" height="70" fill="#1a1a2e" stroke="#333" rx="5"/>' % ly)
    for i, (db, color) in enumerate(DB_COLORS.items()):
        lx = 70 + i * 200
        lines.append('<rect x="%d" y="%d" width="14" height="14" fill="%s" rx="2"/>' % (lx, ly + 15, color))
        lines.append('<text x="%d" y="%d" fill="#ccc" font-family="Menlo" font-size="11">%s</text>' % (lx + 20, ly + 26, db))
    lines.append('<line x1="700" y1="%d" x2="730" y2="%d" stroke="#444466" stroke-width="1" stroke-dasharray="3,2"/>' % (ly + 22, ly + 22))
    lines.append('<text x="740" y="%d" fill="#ccc" font-family="Menlo" font-size="11">intra-db relationship</text>' % (ly + 26))
    lines.append('<line x1="950" y1="%d" x2="980" y2="%d" stroke="#FF4444" stroke-width="1" stroke-dasharray="5,3"/>' % (ly + 22, ly + 22))
    lines.append('<text x="990" y="%d" fill="#ccc" font-family="Menlo" font-size="11">cross-db relationship</text>' % (ly + 26))
    lines.append('<text x="1200" y="%d" fill="#ccc" font-family="Menlo" font-size="11">12 C BCL graph units: bcl_graph_core/builder/cache/compiler/config/expand/learning/optimizer/policy/store/trace/view</text>' % (ly + 26))

    lines.append('</svg>')
    return "\n".join(lines)

def _RenderDot(all_data):
    lines = []
    lines.append("digraph MySQLSchema {")
    lines.append("  rankdir=LR;")
    lines.append('  bgcolor="#0d0d1a";')
    lines.append('  node [fontname="Menlo", fontsize=9, style="filled", shape=box];')
    lines.append('  edge [fontname="Menlo", fontsize=7, color="#666688"];')
    lines.append("")

    for db in DATABASES:
        d = all_data[db]
        color = DB_COLORS[db]
        lines.append('  subgraph cluster_%s {' % db)
        lines.append('    label="%s"; bgcolor="%s"; style="filled"; fillopacity="0.05";' % (DB_LABELS[db], color))
        for t, c in d["counts"].items():
            label = "%s\\n%s rows\\n%d cols" % (t, format(c, ","), d["cols"][t])
            lines.append('    "%s.%s" [label="%s", fillcolor="%s", fontcolor="#ffffff"];' % (db, t, label, color))
        lines.append("  }")
        lines.append("")

    for src_db, src_tbl, dst_db, dst_tbl, keys, rel in RELATIONSHIPS:
        color = "#FF4444" if src_db != dst_db else "#666688"
        style = "dashed" if src_db != dst_db else "solid"
        lines.append('  "%s.%s" -> "%s.%s" [label="%s", color="%s", style="%s"];' % (
            src_db, src_tbl, dst_db, dst_tbl, rel, color, style))

    lines.append("}")
    return "\n".join(lines)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "graph"
    result = Run(cmd, {})
    if result[0] != 1:
        print("Error:", result[2])
        sys.exit(1)
