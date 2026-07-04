#!/usr/bin/env python3
# [@GHOST]{[@file<graph_cascade_cli.py>][@domain<CascadeToolStack>][@role<graph>][@auth<cascade>][@date<2026-06-28>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<graph>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs>]}
# [@SUMMARY]{Generates SVG call graph for cascade_cli.c CEK v5}
# [@CLASS]{GraphCascadeCli}
# [@METHOD]{Run,GenerateSvg,WriteFile}

import html

class GraphCascadeCli:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {}

    def Run(self, command, params=None):
        if command == "generate":
            return self.GenerateSvg()
        return (0, None, (1, "unknown command", 0))

    def GenerateSvg(self):
        W = 1200
        H = 900

        nodes = [
            # (id, label, x, y, w, h, color, category)
            ("main",       "main()",           540,  40,  120, 40, "#4A90D9", "entry"),
            ("Run",        "Run()",            540, 120,  160, 40, "#4A90D9", "dispatch"),
            ("DbLoad",     "DbLoad()",         100, 220,  120, 36, "#50C878", "db"),
            ("DbSave",     "DbSave()",         250, 220,  120, 36, "#50C878", "db"),
            ("DbAdd",      "DbAdd()",          400, 220,  120, 36, "#50C878", "db"),
            ("DbRemove",   "DbRemove()",       550, 220,  120, 36, "#50C878", "db"),
            ("DbList",     "DbList()",         700, 220,  120, 36, "#50C878", "db"),
            ("DbInit",     "DbInit()",         850, 220,  120, 36, "#50C878", "db"),
            ("Validate",   "ValidateCommand()",200, 340,  160, 36, "#FF6B6B", "validation"),
            ("RunExec",    "RunExec()",        540, 340,  140, 36, "#FF9F43", "engine"),
            ("Retry",      "RunWithRetry()",   540, 420,  150, 36, "#FF9F43", "engine"),
            ("ParseArgs",  "ParseArgs()",      800, 340,  130, 36, "#A29BFE", "cli"),
            ("PrintResult","PrintResult()",    350, 520,  140, 36, "#A29BFE", "cli"),
            ("PrintJson",  "PrintJson()",      520, 520,  130, 36, "#A29BFE", "cli"),
            ("PrintDryRun","PrintDryRun()",    690, 520,  140, 36, "#A29BFE", "cli"),
            ("PrintHelp",  "PrintHelp()",      860, 520,  130, 36, "#A29BFE", "cli"),
            ("DetectErr",  "DetectErrors()",   250, 640,  140, 36, "#FD79A8", "analysis"),
            ("Traceback",  "ExtractTraceback()",430, 640,  160, 36, "#FD79A8", "analysis"),
            ("json_esc",   "json_escape()",    620, 640,  130, 36, "#FD79A8", "analysis"),
            ("elapsed",    "elapsed_sec()",    800, 640,  130, 36, "#636E72", "util"),
            ("sleep_ms",   "sleep_ms()",       950, 640,  110, 36, "#636E72", "util"),
            ("set_nb",     "set_nonblock()",   950, 340,  130, 36, "#636E72", "util"),
            ("resolve_db", "resolve_db_path()",100, 120,  150, 36, "#636E72", "util"),
            ("safe_copy",  "safe_copy()",      100, 640,  120, 36, "#636E72", "util"),
            ("str_lower",  "str_to_lower()",   100, 700,  130, 36, "#636E72", "util"),
            ("ExecLog",    "ExecLog()",        350, 420,  130, 36, "#E17055", "logging"),
        ]

        edges = [
            ("main", "Run"),
            ("Run", "DbLoad"),
            ("Run", "DbInit"),
            ("Run", "resolve_db"),
            ("Run", "Validate"),
            ("Run", "RunExec"),
            ("Run", "Retry"),
            ("Run", "ParseArgs"),
            ("Run", "PrintResult"),
            ("Run", "PrintJson"),
            ("Run", "PrintDryRun"),
            ("Run", "PrintHelp"),
            ("Run", "DbAdd"),
            ("Run", "DbRemove"),
            ("Run", "DbList"),
            ("Run", "DbSave"),
            ("Retry", "RunExec"),
            ("RunExec", "set_nb"),
            ("RunExec", "elapsed"),
            ("Validate", "str_lower"),
            ("Validate", "safe_copy"),
            ("PrintResult", "DetectErr"),
            ("PrintResult", "Traceback"),
            ("PrintJson", "json_esc"),
            ("PrintJson", "DetectErr"),
            ("PrintJson", "str_lower"),
            ("ParseArgs", "safe_copy"),
            ("DbAdd", "DbSave"),
            ("DbAdd", "safe_copy"),
            ("DbRemove", "DbSave"),
            ("DetectErr", "str_lower"),
            ("Run", "ExecLog"),
            ("ExecLog", "safe_copy"),
            ("Retry", "sleep_ms"),
            ("DbLoad", "safe_copy"),
        ]

        categories = {
            "entry":      ("Entry", "#4A90D9"),
            "dispatch":   ("Dispatch", "#4A90D9"),
            "db":         ("Pattern DB", "#50C878"),
            "validation": ("Validation", "#FF6B6B"),
            "engine":     ("Execution Engine", "#FF9F43"),
            "cli":        ("CLI Output", "#A29BFE"),
            "analysis":   ("Error Analysis", "#FD79A8"),
            "util":       ("Utilities", "#636E72"),
            "logging":    ("Exec Logging", "#E17055"),
        }

        svg_parts = []
        svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
        svg_parts.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')

        # Title
        svg_parts.append(f'<text x="{W//2}" y="25" text-anchor="middle" fill="#E0E0E0" font-family="monospace" font-size="16" font-weight="bold">Cascade Execution Kernel (CEK) v5 — Call Graph</text>')
        svg_parts.append(f'<text x="{W//2}" y="42" text-anchor="middle" fill="#888" font-family="monospace" font-size="11">cascade_cli.c — 1164 lines — VBStyle compliant</text>')

        # Legend
        lx = 20
        ly = H - 120
        svg_parts.append(f'<rect x="{lx-10}" y="{ly-10}" width="200" height="110" fill="#16213e" stroke="#333" rx="6"/>')
        svg_parts.append(f'<text x="{lx}" y="{ly+5}" fill="#E0E0E0" font-family="monospace" font-size="10" font-weight="bold">LEGEND</text>')
        ci = 0
        for cat, (label, color) in categories.items():
            svg_parts.append(f'<rect x="{lx}" y="{ly + 15 + ci * 14}" width="12" height="10" fill="{color}" rx="2"/>')
            svg_parts.append(f'<text x="{lx + 18}" y="{ly + 24 + ci * 14}" fill="#CCC" font-family="monospace" font-size="10">{label}</text>')
            ci += 1

        # Edges
        node_map = {n[0]: n for n in nodes}
        for src, dst in edges:
            s = node_map.get(src)
            d = node_map.get(dst)
            if not s or not d:
                continue
            sx = s[2] + s[4] // 2
            sy = s[3] + s[5]
            dx = d[2] + d[4] // 2
            dy = d[3]
            midy = (sy + dy) // 2
            svg_parts.append(f'<path d="M{sx},{sy} C{sx},{midy} {dx},{midy} {dx},{dy}" stroke="#444" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>')

        # Arrow marker
        svg_parts.append('<defs><marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#666"/></marker></defs>')

        # Nodes
        for nid, label, x, y, w, h, color, cat in nodes:
            svg_parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="2" rx="6"/>')
            svg_parts.append(f'<text x="{x + w//2}" y="{y + h//2 + 4}" text-anchor="middle" fill="{color}" font-family="monospace" font-size="11" font-weight="bold">{html.escape(label)}</text>')

        # Stats box
        sx = W - 220
        sy = H - 120
        svg_parts.append(f'<rect x="{sx}" y="{sy}" width="200" height="110" fill="#16213e" stroke="#333" rx="6"/>')
        svg_parts.append(f'<text x="{sx + 10}" y="{sy + 20}" fill="#E0E0E0" font-family="monospace" font-size="10" font-weight="bold">STATS</text>')
        stats = [
            f"Nodes: {len(nodes)}",
            f"Edges: {len(edges)}",
            f"Categories: {len(categories)}",
            f"DB: persistent file-backed",
            f"Engine: fork/exec/select",
            f"Protection: 3-layer",
        ]
        for i, s in enumerate(stats):
            svg_parts.append(f'<text x="{sx + 10}" y="{sy + 38 + i * 14}" fill="#AAA" font-family="monospace" font-size="10">{s}</text>')

        svg_parts.append('</svg>')
        return (1, '\n'.join(svg_parts), None)

    def WriteFile(self, path, content):
        with open(path, 'w') as f:
            f.write(content)
        return (1, len(content), None)


if __name__ == "__main__":
    g = GraphCascadeCli()
    ok, data, err = g.GenerateSvg()
    if ok:
        g.WriteFile("/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/cascade_cli_graph.svg", data)
        print("SVG written to Built_tools/cascade_cli_graph.svg")
    else:
        print(f"Error: {err}")
