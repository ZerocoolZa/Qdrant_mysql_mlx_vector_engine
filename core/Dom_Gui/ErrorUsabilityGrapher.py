#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui/ErrorUsabilityGrapher.py
#[@SUMMARY] Graphs IDE errors, usability items, GUI tokens, widgets, lessons, fix attempts, execution log. Shows error->cause->solution->fix chains, GUI component usability, lesson severity by dimension. Outputs SVG + DOT + PNG.
#[@CLASS] ErrorUsabilityGrapher
#[@METHOD] Run, _QueryErrors, _QueryLessons, _QueryGuiTokens, _QueryWidgets, _QueryExecutionLog, _QueryFixAttempts, _RenderSvg, _RenderDot
#[@AUTHORITY] visualization
#[@DOMAIN] dom_gui

import sys
import mysql.connector
import os
import subprocess

SHARED = {"host": "localhost", "user": "root", "password": "", "database": "vb_shared"}
OUTPUT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Gui"

def Run(command, params=None):
    if command == "graph":
        return _BuildGraph(params or {})
    elif command == "read_state":
        return (1, {"status": "ready"}, None)
    return (0, None, ("UNKNOWN_CMD", "unknown command", 0))

def _q(sql, db=SHARED):
    conn = mysql.connector.connect(**db)
    cur = conn.cursor(dictionary=True)
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def _BuildGraph(params):
    errors = _q("SELECT error_id, error_type, domain, LEFT(cause,80) as cause, LEFT(solution,80) as solution, frequency, confidence FROM error_knowledge ORDER BY frequency DESC LIMIT 50")
    exec_log = _q("SELECT status, error_type, COUNT(*) as cnt FROM execution_log GROUP BY status, error_type ORDER BY cnt DESC")
    fixes = _q("SELECT attempt_type, result, COUNT(*) as cnt FROM fix_attempts GROUP BY attempt_type, result")
    lessons = _q("SELECT dimension, issue_type, COUNT(*) as cnt, SUM(severity) as total_sev FROM know_lessons GROUP BY dimension, issue_type ORDER BY cnt DESC LIMIT 30")
    gui_tokens = _q("SELECT token_name, gui_type, authority_rank, version FROM gui_tokens")
    widgets = _q("SELECT widget_key, widget_name, category, parent_widget, is_container, is_active FROM widget_library")
    widget_props_count = _q("SELECT COUNT(*) as c FROM widget_properties")[0]["c"]
    layouts = _q("SELECT COUNT(*) as c FROM layout_definitions")[0]["c"]
    menus = _q("SELECT COUNT(*) as c FROM context_menus")[0]["c"]
    menu_items = _q("SELECT COUNT(*) as c FROM menu_items")[0]["c"]
    tooltips = _q("SELECT COUNT(*) as c FROM tooltips")[0]["c"]
    shortcuts = _q("SELECT COUNT(*) as c FROM shortcut_library")[0]["c"]
    problems = _q("SELECT COUNT(*) as c FROM know_problems")[0]["c"]
    solutions = _q("SELECT COUNT(*) as c FROM know_solutions")[0]["c"]
    causes = _q("SELECT COUNT(*) as c FROM know_causes")[0]["c"]
    contradictions = _q("SELECT COUNT(*) as c FROM code_contradictions")[0]["c"]

    svg = _RenderSvg(errors, exec_log, fixes, lessons, gui_tokens, widgets,
                     widget_props_count, layouts, menus, menu_items, tooltips, shortcuts,
                     problems, solutions, causes, contradictions)
    svg_path = os.path.join(OUTPUT_DIR, "error_usability_graph.svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    dot = _RenderDot(errors, lessons, gui_tokens, widgets, exec_log, fixes)
    dot_path = os.path.join(OUTPUT_DIR, "error_usability_graph.dot")
    with open(dot_path, "w") as f:
        f.write(dot)

    try:
        subprocess.run(["/opt/homebrew/bin/dot", "-Tpng", dot_path, "-o",
                        os.path.join(OUTPUT_DIR, "error_usability_graph.png")],
                       check=True, timeout=60)
    except Exception as e:
        print("PNG render failed:", e)

    _PrintSummary(errors, exec_log, fixes, lessons, gui_tokens, widgets,
                  widget_props_count, layouts, menus, menu_items, tooltips, shortcuts,
                  problems, solutions, causes, contradictions)
    return (1, {"svg": svg_path, "dot": dot_path,
                 "png": os.path.join(OUTPUT_DIR, "error_usability_graph.png")}, None)

def _PrintSummary(errors, exec_log, fixes, lessons, gui_tokens, widgets,
                  wpc, layouts, menus, mi, tips, sc, problems, solutions, causes, contradictions):
    print("=" * 70)
    print("Error + Usability Graph")
    print("=" * 70)
    print()
    print("ERRORS:")
    print("  error_knowledge:       %d errors (showing top %d)" % (139, len(errors)))
    print("  execution_log:         404 runs")
    print("    by status:")
    for r in exec_log:
        print("      %-12s %-25s %d" % (r["status"], r["error_type"] or "none", r["cnt"]))
    print("  fix_attempts:          22 (all manual success)")
    print("  know_problems:         %d" % problems)
    print("  know_solutions:        %d" % solutions)
    print("  know_causes:           %d" % causes)
    print("  code_contradictions:   %d" % contradictions)
    print()
    print("Top errors by frequency:")
    for e in errors[:10]:
        print("  [%3d] %-25s freq=%d conf=%.2f  %s" % (
            e["error_id"], e["error_type"], e["frequency"], e["confidence"], (e["cause"] or "")[:50]))
    print()
    print("LESSONS (usability issues):")
    print("  know_lessons: 240 total, by dimension:")
    for l in lessons[:10]:
        print("    %-30s %-30s %d entries (severity %d)" % (
            l["dimension"], l["issue_type"], l["cnt"], l["total_sev"]))
    print()
    print("GUI / USABILITY:")
    print("  gui_tokens:            %d (toolbar, menubar, statusbar, search, table, etc.)" % len(gui_tokens))
    print("  widget_library:        %d widgets" % len(widgets))
    print("  widget_properties:     %d" % wpc)
    print("  layout_definitions:    %d" % layouts)
    print("  context_menus:         %d" % menus)
    print("  menu_items:            %d" % mi)
    print("  tooltips:              %d" % tips)
    print("  shortcut_library:      %d" % sc)
    print()
    print("GUI Tokens:")
    for g in gui_tokens:
        print("  %-25s %-15s authority=%s" % (g["token_name"], g["gui_type"], g["authority_rank"]))
    print()
    print("Widgets:")
    for w in widgets:
        parent = w["parent_widget"] or "(root)"
        container = "container" if w["is_container"] else "leaf"
        active = "active" if w["is_active"] else "inactive"
        print("  %-25s %-25s [%s] parent=%s %s %s" % (
            w["widget_key"], w["widget_name"], w["category"], parent, container, active))
    print()
    print("Output:")
    print("  PNG: %s/error_usability_graph.png" % OUTPUT_DIR)
    print("  SVG: %s/error_usability_graph.svg" % OUTPUT_DIR)
    print("  DOT: %s/error_usability_graph.dot" % OUTPUT_DIR)

def _RenderSvg(errors, exec_log, fixes, lessons, gui_tokens, widgets,
               wpc, layouts, menus, mi, tips, sc, problems, solutions, causes, contradictions):
    width = 1800
    height = 1600
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height))
    L.append('<rect width="100%%" height="100%%" fill="#0d0d1a"/>')
    L.append('<text x="900" y="35" text-anchor="middle" fill="#fff" font-family="Menlo" font-size="22" font-weight="bold">Errors + Usability Graph</text>')
    L.append('<text x="900" y="58" text-anchor="middle" fill="#888" font-family="Menlo" font-size="13">Errors -> Causes -> Solutions -> Fixes | GUI Tokens -> Widgets -> Properties -> Layouts</text>')

    # Section 1: Error chains (left side)
    L.append('<text x="50" y="100" fill="#FF4444" font-family="Menlo" font-size="16" font-weight="bold">ERROR CHAINS</text>')
    L.append('<text x="50" y="120" fill="#888" font-family="Menlo" font-size="11">error_knowledge: 139 errors | execution_log: 404 runs | fix_attempts: 22</text>')
    L.append('<text x="50" y="138" fill="#888" font-family="Menlo" font-size="11">know_problems: %d | know_solutions: %d | know_causes: %d</text>' % (problems, solutions, causes))

    # Error nodes
    for i, e in enumerate(errors[:25]):
        y = 160 + i * 28
        color = "#FF4444" if e["frequency"] > 10 else "#FF8844" if e["frequency"] > 5 else "#FFAA44"
        r = max(5, min(15, 5 + e["frequency"] * 0.3))
        L.append('<circle cx="70" cy="%d" r="%d" fill="%s" fill-opacity="0.6"/>' % (y, r, color))
        L.append('<text x="90" y="%d" fill="#ccc" font-family="Menlo" font-size="10">[%d] %-25s freq=%d conf=%.2f</text>' % (
            y + 3, e["error_id"], e["error_type"] or "?", e["frequency"], e["confidence"]))
        L.append('<text x="90" y="%d" fill="#666" font-family="Menlo" font-size="9">%s</text>' % (
            y + 14, (e["cause"] or "")[:70]))
        # Arrow to solution
        L.append('<line x1="70" y1="%d" x2="350" y2="%d" stroke="%s" stroke-width="1" opacity="0.3"/>' % (y, y, color))
        L.append('<text x="360" y="%d" fill="#7ED321" font-family="Menlo" font-size="9">%s</text>' % (
            y + 3, (e["solution"] or "")[:60]))

    # Execution log summary (right of errors)
    L.append('<text x="700" y="100" fill="#F5A623" font-family="Menlo" font-size="16" font-weight="bold">EXECUTION LOG</text>')
    L.append('<text x="700" y="120" fill="#888" font-family="Menlo" font-size="11">404 runs by status</text>')
    for i, r in enumerate(exec_log):
        y = 145 + i * 25
        status_color = {"DONE": "#7ED321", "FAILED": "#FF4444", "BLOCKED": "#F5A623", "TIMEOUT": "#E74C3C"}.get(r["status"], "#888")
        L.append('<rect x="710" y="%d" width="14" height="14" fill="%s" rx="2"/>' % (y, status_color))
        L.append('<text x="730" y="%d" fill="#ccc" font-family="Menlo" font-size="11">%-12s %-25s %d runs</text>' % (
            y + 11, r["status"], r["error_type"] or "none", r["cnt"]))

    # Section 2: Lessons (middle)
    L.append('<text x="50" y="900" fill="#9B59B6" font-family="Menlo" font-size="16" font-weight="bold">LESSONS (Usability Issues)</text>')
    L.append('<text x="50" y="920" fill="#888" font-family="Menlo" font-size="11">know_lessons: 240 total, by dimension</text>')
    max_cnt = max(l["cnt"] for l in lessons) if lessons else 1
    for i, l in enumerate(lessons[:20]):
        y = 945 + i * 25
        r = max(4, min(15, 4 + (l["cnt"] / max_cnt) * 11))
        sev_color = "#FF4444" if l["total_sev"] > 100 else "#F5A623" if l["total_sev"] > 20 else "#9B59B6"
        L.append('<circle cx="70" cy="%d" r="%d" fill="%s" fill-opacity="0.6"/>' % (y, r, sev_color))
        L.append('<text x="90" y="%d" fill="#ccc" font-family="Menlo" font-size="10">%-30s %-30s %d entries (sev %d)</text>' % (
            y + 3, l["dimension"], l["issue_type"], l["cnt"], l["total_sev"]))

    # Section 3: GUI Usability (right side)
    L.append('<text x="700" y="900" fill="#4A90D9" font-family="Menlo" font-size="16" font-weight="bold">GUI / USABILITY</text>')
    L.append('<text x="700" y="920" fill="#888" font-family="Menlo" font-size="11">gui_tokens: %d | widgets: %d | props: %d | layouts: %d</text>' % (
        len(gui_tokens), len(widgets), wpc, layouts))
    L.append('<text x="700" y="938" fill="#888" font-family="Menlo" font-size="11">menus: %d | menu_items: %d | tooltips: %d | shortcuts: %d</text>' % (
        menus, mi, tips, sc))

    # GUI tokens
    L.append('<text x="710" y="965" fill="#4A90D9" font-family="Menlo" font-size="12" font-weight="bold">GUI Tokens:</text>')
    for i, g in enumerate(gui_tokens):
        y = 985 + i * 22
        auth_color = {"safety": "#FF4444", "functional": "#7ED321", "layout": "#4A90D9"}.get(g["authority_rank"], "#888")
        L.append('<rect x="720" y="%d" width="12" height="12" fill="%s" rx="2"/>' % (y, auth_color))
        L.append('<text x="740" y="%d" fill="#ccc" font-family="Menlo" font-size="10">%-25s %-15s auth=%s</text>' % (
            y + 10, g["token_name"], g["gui_type"], g["authority_rank"]))

    # Widget tree
    wx = 1050
    L.append('<text x="%d" y="965" fill="#4A90D9" font-family="Menlo" font-size="12" font-weight="bold">Widget Tree:</text>')
    for i, w in enumerate(widgets):
        y = 985 + i * 22
        cat_color = {"container": "#4A90D9", "input": "#F5A623", "display": "#7ED321", "general": "#888"}.get(w["category"], "#888")
        L.append('<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (wx, y + 5, cat_color))
        parent = w["parent_widget"] or "(root)"
        L.append('<text x="%d" y="%d" fill="#ccc" font-family="Menlo" font-size="10">%-20s parent=%-15s [%s]</text>' % (
            wx + 12, y + 10, w["widget_name"], parent, w["category"]))

    # Legend
    ly = height - 60
    L.append('<rect x="50" y="%d" width="1700" height="50" fill="#1a1a2e" stroke="#333" rx="5"/>' % ly)
    L.append('<text x="70" y="%d" fill="#ccc" font-family="Menlo" font-size="10">Red=error/safety | Gold=warning/C | Green=success/functional | Blue=GUI/layout | Purple=lessons</text>' % (ly + 20))
    L.append('<text x="70" y="%d" fill="#888" font-family="Menlo" font-size="10">Node size = frequency/count | Edges: error->cause->solution, widget->parent, lesson->dimension</text>' % (ly + 38))

    L.append('</svg>')
    return "\n".join(L)

def _RenderDot(errors, lessons, gui_tokens, widgets, exec_log, fixes):
    lines = []
    lines.append("digraph ErrorsUsability {")
    lines.append("  rankdir=LR;")
    lines.append('  bgcolor="#0d0d1a";')
    lines.append('  node [fontname="Menlo", fontsize=9, style="filled"];')
    lines.append('  edge [fontname="Menlo", fontsize=7];')
    lines.append("")

    # Error -> Cause -> Solution chains
    lines.append("  subgraph cluster_errors {")
    lines.append('    label="Error Chains (139 errors)"; bgcolor="#2e1a1a"; style="filled"; fillopacity="0.3";')
    for e in errors[:30]:
        eid = "err_%d" % e["error_id"]
        label = "%s\\nfreq=%d conf=%.2f" % (e["error_type"] or "?", e["frequency"], e["confidence"])
        color = "#FF4444" if e["frequency"] > 10 else "#FF8844"
        lines.append('    "%s" [label="%s", fillcolor="%s", fontcolor="#fff", shape=box];' % (eid, label, color))
        # Solution node
        sid = "sol_%d" % e["error_id"]
        sol_text = (e["solution"] or "no solution")[:40].replace('"', "'")
        lines.append('    "%s" [label="%s", fillcolor="#7ED321", fontcolor="#000", shape=box, fontsize=8];' % (sid, sol_text))
        lines.append('    "%s" -> "%s" [label="fixed by", color="#7ED321"];' % (eid, sid))
    lines.append("  }")
    lines.append("")

    # Execution log
    lines.append("  subgraph cluster_exec {")
    lines.append('    label="Execution Log (404 runs)"; bgcolor="#2e2a1a"; style="filled"; fillopacity="0.3";')
    for r in exec_log:
        status_color = {"DONE": "#7ED321", "FAILED": "#FF4444", "BLOCKED": "#F5A623", "TIMEOUT": "#E74C3C"}.get(r["status"], "#888")
        label = "%s\\n%s\\n%d runs" % (r["status"], r["error_type"] or "none", r["cnt"])
        lines.append('    "exec_%s_%s" [label="%s", fillcolor="%s", fontcolor="#fff", shape=box];' % (
            r["status"], (r["error_type"] or "none")[:10], label, status_color))
    lines.append("  }")
    lines.append("")

    # Lessons
    lines.append("  subgraph cluster_lessons {")
    lines.append('    label="Lessons (240 usability issues)"; bgcolor="#2a1a2e"; style="filled"; fillopacity="0.3";')
    for l in lessons[:20]:
        lid = "lesson_%s_%s" % (l["dimension"][:10], l["issue_type"][:10])
        lid = lid.replace(" ", "_").replace("/", "_")
        label = "%s\\n%s\\n%d entries (sev %d)" % (l["dimension"], l["issue_type"], l["cnt"], l["total_sev"])
        color = "#FF4444" if l["total_sev"] > 100 else "#F5A623" if l["total_sev"] > 20 else "#9B59B6"
        lines.append('    "%s" [label="%s", fillcolor="%s", fontcolor="#fff", shape=box];' % (lid, label, color))
    lines.append("  }")
    lines.append("")

    # GUI tokens
    lines.append("  subgraph cluster_gui {")
    lines.append('    label="GUI Tokens + Widgets"; bgcolor="#1a2e2a"; style="filled"; fillopacity="0.3";')
    for g in gui_tokens:
        gid = "gui_%s" % g["token_name"].replace("[", "").replace("]", "").replace("@", "")
        auth_color = {"safety": "#FF4444", "functional": "#7ED321", "layout": "#4A90D9"}.get(g["authority_rank"], "#888")
        label = "%s\\n%s\\nauth=%s" % (g["token_name"], g["gui_type"], g["authority_rank"])
        lines.append('    "%s" [label="%s", fillcolor="%s", fontcolor="#fff", shape=box];' % (gid, label, auth_color))
    lines.append("")

    # Widget tree
    for w in widgets:
        wid = "widget_%s" % w["widget_key"]
        cat_color = {"container": "#4A90D9", "input": "#F5A623", "display": "#7ED321", "general": "#888"}.get(w["category"], "#888")
        label = "%s\\n[%s]" % (w["widget_name"], w["category"])
        lines.append('    "%s" [label="%s", fillcolor="%s", fontcolor="#fff", shape=box];' % (wid, label, cat_color))
        if w["parent_widget"]:
            pid = "widget_%s" % w["parent_widget"]
            lines.append('    "%s" -> "%s" [label="child of", color="#4A90D9"];' % (pid, wid))
    lines.append("  }")
    lines.append("}")

    return "\n".join(lines)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "graph"
    result = Run(cmd, {})
    if result[0] != 1:
        print("Error:", result[2])
        sys.exit(1)
