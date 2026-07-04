#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_connector.py
# Domain:   efl_brain
# Authority: Connector brother — reads efl_brain.db and builds the agent graph
#            from database rows instead of AST walking the file system.
# DB:       efl_brain.db (read-only — reads classes, methods, graph_edges)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — No hardcoded paths (all from Config_efl_brain.py)
#   @cstyle   — Coding style compliant
# ============================================================================

"""
Connector Brother — builds the agent graph from the database.

The agent graph used to build by walking the folder and parsing every .py
file with AST. That's slow and couples the graph to the file system.

The connector brother reads from efl_brain.db instead:
  - classes table  → AgentNode (type=CLASS or MEMUNIT)
  - methods table  → AgentNode (type=FUNCTION)
  - graph_edges    → Edge (type from edge_type column)

No AST walking. No file system scanning. Just SQL.

The resulting graph is written to agent_prediction_links via BrainDb
so other brothers can read it.

Usage:
  python3 Efi_connector.py           — build graph from DB and print summary
  python3 Efi_connector.py run build — same, via Run() dispatch
"""

import os
import sys
import sqlite3
from collections import defaultdict

from Config_efl_brain import DB_PATH
from Efi_brain_db import BrainDb

# Table name constants — no hardcoding (R7 compliance)
CLASSES_TABLE = "classes"
METHODS_TABLE = "methods"
GRAPH_EDGES_TABLE = "graph_edges"


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  Connector
# Domain: efl_brain
# Authority: Reads efl_brain.db and constructs an agent graph from DB rows
# Dependencies: sqlite3, Config_efl_brain, Efi_brain_db
# ============================================================================


# Class: Connector — reads efl_brain.db and constructs an agent graph from DB rows
class Connector:
    """Connector brother — reads the database and builds the graph.

    self.state holds all working data:
      state["nodes"]    — dict of node_id → node dict
      state["edges"]    — list of edge dicts
      state["stats"]    — build statistics
    """

    def __init__(self):
        """Initialize the connector brother with empty state."""
        self.state = {}
        self.state["nodes"] = {}
        self.state["edges"] = []
        self.state["stats"] = {}
        self.state["db_path"] = DB_PATH

    # ----------------------------------------------------------------
    # Build — read DB and construct graph
    # ----------------------------------------------------------------

    def BuildFromDb(self):
        """Read efl_brain.db and build the graph from classes, methods, edges.

        Returns:
            Tuple3 (ok, data, error)
        """
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # 1. Read classes → CLASS or MEMUNIT nodes
            c.execute(f"""
                SELECT id, class_name, domain, source, class_code, description, method_count
                FROM {CLASSES_TABLE}
            """)
            class_rows = c.fetchall()
            class_nodes = 0
            memunit_nodes = 0

            for row in class_rows:
                class_name = row["class_name"]
                node_id = f"db::class::{class_name}"

                # Detect MEMUNIT: has Run() method and self.state dict
                c2 = conn.cursor()
                c2.execute(f"""
                    SELECT method_name FROM {METHODS_TABLE}
                    WHERE class_id = ? AND method_name = 'Run'
                """, (row["id"],))
                has_run = c2.fetchone() is not None

                # Check for self.state in class code
                class_code = row["class_code"] or ""
                has_state = "self.state" in class_code

                node_type = "MEMUNIT" if (has_run and has_state) else "CLASS"

                self.state["nodes"][node_id] = {
                    "id": node_id,
                    "type": node_type,
                    "name": class_name,
                    "domain": row["domain"],
                    "source": row["source"],
                    "description": row["description"],
                    "method_count": row["method_count"],
                    "path": "",
                }

                if node_type == "MEMUNIT":
                    memunit_nodes += 1
                else:
                    class_nodes += 1

            # 2. Read methods → FUNCTION nodes
            c.execute(f"""
                SELECT id, class_id, class_name, method_name, params,
                       method_code, is_run, is_init, returns_tuple3, line_start
                FROM {METHODS_TABLE}
            """)
            method_rows = c.fetchall()
            function_nodes = 0

            for row in method_rows:
                method_name = row["method_name"]
                class_name = row["class_name"]
                node_id = f"db::method::{class_name}.{method_name}"

                self.state["nodes"][node_id] = {
                    "id": node_id,
                    "type": "FUNCTION",
                    "name": method_name,
                    "class_name": class_name,
                    "params": row["params"],
                    "is_run": row["is_run"],
                    "is_init": row["is_init"],
                    "returns_tuple3": row["returns_tuple3"],
                    "line_start": row["line_start"],
                    "path": "",
                }
                function_nodes += 1

                # Create DEFINES edge: class → method
                class_node_id = f"db::class::{class_name}"
                if class_node_id in self.state["nodes"]:
                    self.state["edges"].append({
                        "src": class_node_id,
                        "dst": node_id,
                        "type": "DEFINES",
                    })

            # 3. Read graph_edges → Edge connections
            c.execute(f"""
                SELECT source_class, source_method, target_class, target_method, edge_type
                FROM {GRAPH_EDGES_TABLE}
            """)
            edge_rows = c.fetchall()
            graph_edges = 0

            for row in edge_rows:
                src_class = row["source_class"] or ""
                src_method = row["source_method"] or ""
                dst_class = row["target_class"] or ""
                dst_method = row["target_method"] or ""
                edge_type = row["edge_type"] or "CALLS"

                # Map to node IDs
                if src_method:
                    src_id = f"db::method::{src_class}.{src_method}"
                else:
                    src_id = f"db::class::{src_class}"

                if dst_method:
                    dst_id = f"db::method::{dst_class}.{dst_method}"
                else:
                    dst_id = f"db::class::{dst_class}"

                # Only add if both nodes exist
                if src_id in self.state["nodes"] and dst_id in self.state["nodes"]:
                    self.state["edges"].append({
                        "src": src_id,
                        "dst": dst_id,
                        "type": edge_type.upper().replace("INTERNAL_CALL", "CALLS")
                                              .replace("CROSS_CALL", "CALLS")
                                              .replace("DISPATCH", "CALLS"),
                    })
                    graph_edges += 1

            conn.close()

            # 4. Compute stats
            self.state["stats"] = {
                "class_nodes": class_nodes,
                "memunit_nodes": memunit_nodes,
                "function_nodes": function_nodes,
                "total_nodes": len(self.state["nodes"]),
                "graph_edges": graph_edges,
                "defines_edges": sum(1 for e in self.state["edges"] if e["type"] == "DEFINES"),
                "total_edges": len(self.state["edges"]),
            }

            return (True, self.state["stats"], "")

        except Exception as e:
            return (False, None, str(e))

    # ----------------------------------------------------------------
    # Write — push graph to BrainDb (dinner table)
    # ----------------------------------------------------------------

    def WriteToDb(self):
        """Write the connector-built graph to efl_brain.db via BrainDb.

        Returns:
            Tuple3 (ok, data, error)
        """
        try:
            db = BrainDb()
            db.Connect()

            # Write prediction links from edges (initial confidence = 0.5)
            links = []
            for edge in self.state["edges"]:
                links.append({
                    "source_node": edge["src"],
                    "target_node": edge["dst"],
                    "expected_reward": 0.5,
                    "expected_pain": 0.0,
                    "confidence": 0.5,
                    "update_count": 0,
                })
            written = db.WritePredictionLinks(links, writer="connector")
            db.Disconnect()

            return (True, {"prediction_links_written": written}, "")

        except Exception as e:
            return (False, None, str(e))

    # ----------------------------------------------------------------
    # Summary — return graph summary
    # ----------------------------------------------------------------

    def Summary(self):
        """Return a summary of the connector-built graph.

        Returns:
            dict with node counts, edge counts, type breakdown
        """
        type_counts = defaultdict(int)
        for node in self.state["nodes"].values():
            type_counts[node["type"]] += 1

        edge_type_counts = defaultdict(int)
        for edge in self.state["edges"]:
            edge_type_counts[edge["type"]] += 1

        return {
            "total_nodes": len(self.state["nodes"]),
            "total_edges": len(self.state["edges"]),
            "node_types": dict(type_counts),
            "edge_types": dict(edge_type_counts),
            "stats": self.state["stats"],
        }

    # ----------------------------------------------------------------
    # Run — dispatch entry point
    # ----------------------------------------------------------------

    def Run(self, command, params=None):
        """Dispatch entry point.

        Args:
            command: str — "build", "write", "summary", "full"
            params: dict — optional parameters

        Returns:
            Tuple3 (ok, data, error)
        """
        if params is None:
            params = {}

        if command == "build":
            return self.BuildFromDb()

        elif command == "write":
            return self.WriteToDb()

        elif command == "summary":
            return (True, self.Summary(), "")

        elif command == "full":
            # Build + write + summary
            ok1, data1, err1 = self.BuildFromDb()
            if not ok1:
                return (False, None, f"Build failed: {err1}")
            ok2, data2, err2 = self.WriteToDb()
            if not ok2:
                return (False, None, f"Write failed: {err2}")
            summary = self.Summary()
            summary["write_result"] = data2
            return (True, summary, "")

        else:
            return (False, None, f"Unknown command: {command}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    connector = Connector()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    ok, data, err = connector.Run(cmd)
    if ok:
        sys.stdout.write("=" * 60 + "\n")
        sys.stdout.write("  CONNECTOR BROTHER — Graph from Database\n")
        sys.stdout.write("=" * 60 + "\n")
        if "node_types" in data:
            sys.stdout.write(f"\n  Nodes: {data['total_nodes']}\n")
            for ntype, count in sorted(data["node_types"].items()):
                sys.stdout.write(f"    {ntype:12s}  {count}\n")
            sys.stdout.write(f"\n  Edges: {data['total_edges']}\n")
            for etype, count in sorted(data["edge_types"].items()):
                sys.stdout.write(f"    {etype:12s}  {count}\n")
            if "write_result" in data:
                sys.stdout.write(f"\n  Written to DB: {data['write_result']['prediction_links_written']} prediction links\n")
        else:
            sys.stdout.write(f"\n  Result: {data}\n")
        sys.stdout.write("=" * 60 + "\n")
    else:
        sys.stdout.write(f"ERROR: {err}\n")
        sys.exit(1)
