#!/usr/bin/env python3
"""
run_codegraph_on_c.py — Run CodeGraphAuthority on the C version (Cascade_toolStack)
Then compare Python MemUnit vs C MemUnit side by side.
"""

import sys
import os
import json

sys.path.insert(0, "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains")
from dom_codegraph import CodeGraphAuthority

def run_on_dir(cga, label, target_dir):
    """Run codegraph analysis on a directory, return results dict"""
    print(f"\n{'='*70}")
    print(f"CODEGRAPH: {label}")
    print(f"Target: {target_dir}")
    print(f"{'='*70}")

    results = {}

    # SCAN
    print("\n--- SCAN ---")
    r = cga.Run("scan", {"root_path": target_dir, "run_eyes": True, "run_layers": True})
    print(f"ok={r[0]}")
    if r[0]:
        data = r[1]
        results["scan"] = data
        ov = data.get("overview", {})
        print(f"  Files:          {ov.get('total_files', '?')}")
        print(f"  Classes:        {ov.get('total_classes', '?')}")
        print(f"  Functions:      {ov.get('total_functions', '?')}")
        print(f"  Complexity:     {ov.get('total_complexity', '?')}")
        print(f"  Avg power:      {ov.get('average_power_level', '?')}")
        print(f"  Size:           {ov.get('total_size', '?')} bytes")
        print(f"  Languages:      {data.get('languages', {})}")
        print(f"  Edges:          {data.get('edges', '?')}")
        print(f"  Scan time:      {data.get('runtime', {}).get('scan_seconds', '?')}s")
    else:
        print(f"  Error: {r[2]}")
        results["scan_error"] = r[2]

    # GRAPH
    print("\n--- GRAPH ---")
    r = cga.Run("graph", {"root_path": target_dir})
    print(f"ok={r[0]}")
    if r[0]:
        data = r[1]
        results["graph"] = data
        if isinstance(data, dict):
            edges = data.get("edges", [])
            nodes = data.get("nodes", [])
            print(f"  Nodes: {len(nodes)}")
            print(f"  Edges: {len(edges)}")
            if edges:
                print(f"  Edge list:")
                for e in edges[:15]:
                    if isinstance(e, (tuple, list)):
                        # (source, target, type)
                        src = os.path.basename(str(e[0])) if len(e) > 0 else "?"
                        tgt = os.path.basename(str(e[1])) if len(e) > 1 else "?"
                        etype = e[2] if len(e) > 2 else "?"
                        print(f"    {src} --{etype}--> {tgt}")
    else:
        print(f"  Error: {r[2]}")

    # STATS
    print("\n--- STATS ---")
    r = cga.Run("stats", {})
    print(f"ok={r[0]}")
    if r[0]:
        data = r[1]
        results["stats"] = data
        ov = data.get("overview", {})
        graph = data.get("graph", {})
        layers = data.get("layers", {})
        print(f"  Files:          {ov.get('total_files', '?')}")
        print(f"  Classes:        {ov.get('total_classes', '?')}")
        print(f"  Functions:      {ov.get('total_functions', '?')}")
        print(f"  Complexity:     {ov.get('total_complexity', '?')}")
        print(f"  Graph nodes:    {graph.get('nodes', '?')}")
        print(f"  Graph edges:    {graph.get('edges', '?')}")
        print(f"  Graph density:  {graph.get('density', '?')}")
        print(f"  12-layer system:")
        for layer, count in sorted(layers.items()):
            marker = " ★" if count > 0 else ""
            print(f"    {layer}: {count}{marker}")
    else:
        print(f"  Error: {r[2]}")

    # CODE TO BRACKET (first file)
    print("\n--- CODE TO BRACKET (main file) ---")
    main_files = {
        "Python MemUnit": f"{target_dir}/boot_test.py",
        "C MemUnit":      f"{target_dir}/memunit.c",
    }
    target_file = main_files.get(label, f"{target_dir}/memunit.c")

    if os.path.exists(target_file):
        r = cga.Run("code_to_bracket_file", {"file_path": target_file})
        print(f"ok={r[0]}")
        if r[0]:
            data = r[1]
            bracket = data if isinstance(data, str) else data.get("bracket", str(data))
            results["bracket"] = bracket
            print(f"  Bracket length: {len(bracket)} chars")
            print(f"  First 1500 chars:")
            print(f"  {bracket[:1500]}")
        else:
            print(f"  Error: {r[2]}")
    else:
        print(f"  File not found: {target_file}")

    # QUERY
    print("\n--- QUERY: MemUnit ---")
    r = cga.Run("query", {"pattern": "MemUnit"})
    print(f"ok={r[0]}")
    if r[0]:
        data = r[1]
        results["query"] = data
        rows = data.get("rows", []) if isinstance(data, dict) else []
        print(f"  Found {len(rows)} matching class(es) in MySQL knowledge base")
        for row in rows[:5]:
            if isinstance(row, dict):
                print(f"    {row.get('class_name', '?')} [{row.get('layer', '?')}]")
    else:
        print(f"  Error: {r[2]}")

    return results


def print_comparison(py_results, c_results):
    """Print side-by-side comparison"""
    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE COMPARISON: Python MemUnit vs C MemUnit")
    print("=" * 80)

    py_scan = py_results.get("scan", {}).get("overview", {})
    c_scan  = c_results.get("scan", {}).get("overview", {})

    py_stats = py_results.get("stats", {})
    c_stats  = c_results.get("stats", {})

    py_graph = py_stats.get("graph", {})
    c_graph  = c_stats.get("graph", {})

    py_layers = py_stats.get("layers", {})
    c_layers  = c_stats.get("layers", {})

    rows = [
        ("Metric", "Python MemUnit", "C MemUnit"),
        ("-" * 30, "-" * 25, "-" * 25),
        ("Files",        py_scan.get("total_files", "?"),  c_scan.get("total_files", "?")),
        ("Classes",      py_scan.get("total_classes", "?"),c_scan.get("total_classes", "?")),
        ("Functions",    py_scan.get("total_functions", "?"),c_scan.get("total_functions", "?")),
        ("Complexity",   py_scan.get("total_complexity", "?"),c_scan.get("total_complexity", "?")),
        ("Avg power",    py_scan.get("average_power_level", "?"),c_scan.get("average_power_level", "?")),
        ("Size (bytes)", py_scan.get("total_size", "?"),   c_scan.get("total_size", "?")),
        ("Graph nodes",  py_graph.get("nodes", "?"),       c_graph.get("nodes", "?")),
        ("Graph edges",  py_graph.get("edges", "?"),       c_graph.get("edges", "?")),
        ("Graph density",py_graph.get("density", "?"),     c_graph.get("density", "?")),
    ]

    for row in rows:
        print(f"  {str(row[0]):<30} {str(row[1]):<25} {str(row[2]):<25}")

    # Layer comparison
    print(f"\n  12-LAYER SYSTEM COMPARISON:")
    print(f"  {'Layer':<30} {'Python':<10} {'C':<10}")
    print(f"  {'-'*30} {'-'*10} {'-'*10}")
    all_layers = sorted(set(list(py_layers.keys()) + list(c_layers.keys())))
    for layer in all_layers:
        pv = py_layers.get(layer, 0)
        cv = c_layers.get(layer, 0)
        marker_py = " ★" if pv > 0 else ""
        marker_c  = " ★" if cv > 0 else ""
        print(f"  {layer:<30} {str(pv)+marker_py:<10} {str(cv)+marker_c:<10}")

    # Bracket comparison
    py_bracket = py_results.get("bracket", "")
    c_bracket  = c_results.get("bracket", "")

    print(f"\n  BCL BRACKET OUTPUT COMPARISON:")
    print(f"  Python: {len(py_bracket)} chars")
    print(f"  C:      {len(c_bracket)} chars")

    if py_bracket and c_bracket:
        print(f"\n  Python bracket (first 300 chars):")
        print(f"    {py_bracket[:300]}")
        print(f"\n  C bracket (first 300 chars):")
        print(f"    {c_bracket[:300]}")

    # Verdict
    print(f"\n  {'='*70}")
    print(f"  VERDICT")
    print(f"  {'='*70}")

    py_classes = py_scan.get("total_classes", 0)
    c_classes  = c_scan.get("total_classes", 0)
    py_edges   = py_graph.get("edges", 0)
    c_edges    = c_graph.get("edges", 0)
    py_complex = py_scan.get("total_complexity", 0)
    c_complex  = c_scan.get("total_complexity", 0)

    print(f"  Python MemUnit: {py_classes} classes, {py_edges} edges, complexity {py_complex}")
    print(f"  C MemUnit:      {c_classes} classes, {c_edges} edges, complexity {c_complex}")

    if isinstance(py_classes, int) and isinstance(c_classes, int) and py_classes > 0:
        ratio = c_classes / py_classes if py_classes else 0
        print(f"  C has {ratio:.1%} of Python's class count")

    if isinstance(py_complex, int) and isinstance(c_complex, int) and py_complex > 0:
        cratio = c_complex / py_complex if py_complex else 0
        print(f"  C has {cratio:.1%} of Python's complexity")


def main():
    cga = CodeGraphAuthority()

    # Python version
    py_dir = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/arch_test"
    py_results = run_on_dir(cga, "Python MemUnit", py_dir)

    # Reset authority for C scan
    cga2 = CodeGraphAuthority()

    # C version
    c_dir = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack"
    c_results = run_on_dir(cga2, "C MemUnit", c_dir)

    # Comparison
    print_comparison(py_results, c_results)

    print("\n" + "=" * 80)
    print("CODEGRAPH COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
