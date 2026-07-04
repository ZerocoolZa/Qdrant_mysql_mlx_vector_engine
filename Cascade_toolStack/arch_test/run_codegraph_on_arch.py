#!/usr/bin/env python3
"""
run_codegraph_on_arch.py — Run the REAL CodeGraphAuthority from dom_codegraph.py
on the MemUnit architecture test files.

This uses the actual codegraph engine from the workspace — not a toy.
"""

import sys
import os
import json

# Add the dom_codegraph.py path
sys.path.insert(0, "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains")

from dom_codegraph import CodeGraphAuthority

def main():
    print("=" * 70)
    print("CODEGRAPH AUTHORITY — ANALYZING MEMUNIT ARCHITECTURE")
    print("=" * 70)

    # Create the authority
    cga = CodeGraphAuthority()

    # Target: the arch_test directory with boot_test.py
    target_dir = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/arch_test"

    print(f"\nTarget: {target_dir}")
    print(f"Files: boot_test.py, arch_graph.py, MemUnit_real.py, MemDb_real.py,")
    print(f"       MemBus_real.py, Executor_real.py")

    # ── SCAN ──
    print("\n--- SCAN ---")
    r = cga.Run("scan", {"root_path": target_dir, "run_eyes": True, "run_layers": True})
    print(f"Scan result: ok={r[0]}")
    if r[0]:
        data = r[1]
        print(f"  Raw data type: {type(data).__name__}")
        print(f"  Raw data: {json.dumps(data, indent=2, default=str)[:3000]}")
    else:
        print(f"  Error: {r[2]}")

    # ── ANALYZE (single file) ──
    print("\n--- ANALYZE boot_test.py ---")
    r = cga.Run("analyze", {"file_path": f"{target_dir}/boot_test.py"})
    print(f"Analyze result: ok={r[0]}")
    if r[0]:
        data = r[1]
        print(f"  {json.dumps(data, indent=2, default=str)[:3000]}")
    else:
        print(f"  Error: {r[2]}")

    # ── GRAPH ──
    print("\n--- GRAPH ---")
    r = cga.Run("graph", {"root_path": target_dir})
    print(f"Graph result: ok={r[0]}")
    if r[0]:
        data = r[1]
        print(f"  Raw data type: {type(data).__name__}")
        if isinstance(data, dict):
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            print(f"  Nodes: {len(nodes)}")
            print(f"  Edges: {len(edges)}")
            if nodes:
                print(f"\n  Nodes:")
                for n in nodes[:30]:
                    if isinstance(n, dict):
                        print(f"    [{n.get('type', '?')}] {n.get('name', '?')} "
                              f"(file={n.get('file', '?')})")
                    else:
                        print(f"    {n}")
            if edges:
                print(f"\n  Edges:")
                for e in edges[:30]:
                    if isinstance(e, dict):
                        print(f"    {e.get('source', '?')} --{e.get('type', '?')}--> {e.get('target', '?')}")
                    elif isinstance(e, (tuple, list)):
                        print(f"    {e}")
                    else:
                        print(f"    {e}")
        else:
            print(f"  Data: {str(data)[:3000]}")
    else:
        print(f"  Error: {r[2]}")

    # ── STATS ──
    print("\n--- STATS ---")
    r = cga.Run("stats", {})
    print(f"Stats result: ok={r[0]}")
    if r[0]:
        data = r[1]
        print(f"  {json.dumps(data, indent=2, default=str)[:2000]}")
    else:
        print(f"  Error: {r[2]}")

    # ── QUERY: find MemUnit classes ──
    print("\n--- QUERY: MemUnit ---")
    r = cga.Run("query", {"pattern": "MemUnit"})
    print(f"Query result: ok={r[0]}")
    if r[0]:
        data = r[1]
        print(f"  Raw: {json.dumps(data, indent=2, default=str)[:2000]}")
    else:
        print(f"  Error: {r[2]}")

    # ── CODE TO BRACKET ──
    print("\n--- CODE TO BRACKET (boot_test.py) ---")
    r = cga.Run("code_to_bracket_file", {"file_path": f"{target_dir}/boot_test.py"})
    print(f"Bracket result: ok={r[0]}")
    if r[0]:
        data = r[1]
        bracket_text = data if isinstance(data, str) else data.get("bracket", str(data))
        print(f"  Bracket output ({len(bracket_text)} chars):")
        print(f"  {bracket_text[:3000]}")
    else:
        print(f"  Error: {r[2]}")

    print("\n" + "=" * 70)
    print("CODEGRAPH ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
