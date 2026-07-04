#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Utility script to verify DB build and check graph tables. NOT VBStyle: no VBStyle headers no class no Run() dispatch no Tuple3 returns. Has 6 print() calls. Hardcoded path (/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph). Procedural script with no class structure.>][@todos<1. Add VBStyle headers. 2. Remove print() calls. 3. Remove hardcoded paths. 4. Wrap in class with Run() dispatch and Tuple3 returns.>]}
"""Verify DB build and check graph tables."""
import sys
from pathlib import Path

BASE_DIR = Path("/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph")
sys.path.insert(0, str(BASE_DIR))

from Config import Config

cfg = Config()
result = cfg.Run("build_db")
print(f"DB build: {result[0]}")
if result[0] == 1:
    conn = result[1]["conn"]
    print(f"Tables: {result[1]['tables']}, Primitives: {result[1]['primitives']}")
    
    # Check graph tables
    tables = ["graph_categories", "graph_classes", "graph_edges", "graph_edge_colors", 
              "graph_flows", "graph_flow_colors", "graph_lifecycle_phases", "graph_class_phase", 
              "graph_operation_verbs"]
    print("\nGraph table counts:")
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:25} {count}")
        except Exception as e:
            print(f"  {t:25} ERROR: {e}")
else:
    print(f"Error: {result[2]}")
