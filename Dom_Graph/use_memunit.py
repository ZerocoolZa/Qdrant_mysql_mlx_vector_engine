#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/use_memunit.py"
# date="2026-06-27" author="Devin" session_id="memunit-real-use"
# context="Real-world test: ingest actual Dom_Graph source files into the event-sourced in-RAM context graph, then query it to produce a structured codebase summary. Self-referential -- the system ingests itself."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="use_memunit.py" domain="memunit" authority="demo"}
# [@SUMMARY]{summary="Ingest real .py files into MemUnit event-sourced graph. Parse BCL headers for stamps, ast.parse for methods. Query graph for structured context. See if it helps."}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Demo script testing MemUnit event-sourcing system. Has VBStyle headers but NOT VBStyle compliant: no class no Run() dispatch no Tuple3 returns no self.state dict. Has 33 print() calls. Multiple standalone functions. authority=demo indicates it is not a real engine.>][@todos<1. Wrap in class with Run() dispatch and Tuple3 returns. 2. Remove print() calls. 3. Add self.state dict _p helper read_state set_config.>]}
"""
use_memunit.py -- Real-world test of the MemUnit event-sourcing system.

Ingests actual Dom_Graph/*.py files into the in-RAM event-sourced context
graph, extracting:
  - FILE nodes (one per .py file)
  - CLASS nodes (one per top-level class)
  - METHOD nodes (one per method in each class)
  - AST versions (the actual source code as content)
  - BCL stamps (parsed from [@SUMMARY] headers -- the file's stated intent)
  - Trace chains (one trace per file: parse -> register -> stamp)
  - Dependency edges (class -> file containment)

Then queries the graph to produce a structured context summary and prints it.
This tests whether the in-RAM context graph actually helps organize
understanding of a real codebase.
"""
import ast
import os
import re
import sys
import hashlib
import tempfile
from datetime import datetime

# Add Dom_Graph to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from InRamDb import InRamDb
from EventLogStore import EventLogStore
from AstNodeRegistry import AstNodeRegistry
from AstVersionStore import AstVersionStore
from BclStampStore import BclStampStore
from TraceChainStore import TraceChainStore
from DependencyEdgeStore import DependencyEdgeStore
from ReplayEngine import ReplayEngine


# Files to ingest (the event-sourcing system itself -- self-referential test)
TARGET_FILES = [
    "InRamDb.py",
    "EventLogStore.py",
    "AstNodeRegistry.py",
    "AstVersionStore.py",
    "BclStampStore.py",
    "TraceChainStore.py",
    "DependencyEdgeStore.py",
    "SnapshotStore.py",
    "ReplayEngine.py",
    "RollbackEngine.py",
]


def _p(params, key, default=None):
    if not params:
        return default
    return params.get(key, default)


def extract_bcl_summary(source_text):
    """Extract [@SUMMARY]{summary="..."} from BCL header."""
    m = re.search(r'\[@SUMMARY\]\{[^}]*summary="([^"]+)"', source_text)
    return m.group(1) if m else None


def extract_bcl_class(source_text):
    """Extract [@CLASS]{class="..." domain="..."} from BCL header."""
    m = re.search(r'\[@CLASS\]\{[^}]*class="([^"]+)"[^}]*domain="([^"]+)"', source_text)
    return (m.group(1), m.group(2)) if m else (None, None)


def extract_methods(source_text):
    """Use ast.parse to find all method definitions in top-level classes."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return []
    methods = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end_line = getattr(item, "end_lineno", item.lineno)
                    methods.append({
                        "class": node.name,
                        "method": item.name,
                        "line_range": f"{item.lineno}-{end_line}",
                    })
    return methods


def ingest_file(db, log, reg, vs, bs, tc, de, file_name, source_text, trace_counter):
    """Ingest one .py file into the event-sourced graph. Returns node ids."""
    trace_id = f"tr_{trace_counter[0]}"
    trace_counter[0] += 1

    # 1. Create FILE node
    r = reg.Run("create_node", {
        "node_type": "FILE",
        "symbolic_name": file_name,
        "file_path": f"Dom_Graph/{file_name}",
        "trace_id": trace_id,
        "cause": "ingest source file",
    })
    if r[0] != 1:
        print(f"  FAIL create FILE node for {file_name}: {r[2]}")
        return None
    file_node_id = r[1]["node_id"]

    # 2. Add version (the source content)
    r = vs.Run("add_version", {
        "node_id": file_node_id,
        "content": source_text,
        "content_format": "SOURCE",
        "trace_id": trace_id,
    })
    if r[0] != 1:
        print(f"  FAIL add version for FILE {file_name}: {r[2]}")
        return None
    file_version_id = r[1]["version_id"]

    # 3. Extract BCL summary -> attach stamp to FILE node
    summary = extract_bcl_summary(source_text)
    if summary:
        r = bs.Run("attach_stamp", {
            "node_id": file_node_id,
            "ast_version_id": file_version_id,
            "trace_id": trace_id,
            "scope_binding": "FULL",
            "intent_vector": {"primary_goal": summary},
            "dependency_set": {"writes": ["mu_ast_nodes", "mu_ast_versions"]},
            "event_refs": [],
            "cause": "BCL header summary",
        })
        if r[0] != 1:
            print(f"  WARN attach FILE stamp for {file_name}: {r[2]}")

    # 4. Parse classes + methods
    class_name, domain = extract_bcl_class(source_text)
    methods = extract_methods(source_text)

    # Group methods by class
    classes = {}
    for m in methods:
        classes.setdefault(m["class"], []).append(m)

    # If BCL header names a class, prefer that; otherwise use all found
    class_node_ids = {}
    method_node_ids = {}

    for cls_name, cls_methods in classes.items():
        # 5. Create CLASS node
        r = reg.Run("create_node", {
            "node_type": "CLASS",
            "symbolic_name": cls_name,
            "parent_node_id": file_node_id,
            "file_path": f"Dom_Graph/{file_name}",
            "trace_id": trace_id,
            "cause": f"class {cls_name} in {file_name}",
        })
        if r[0] != 1:
            print(f"  FAIL create CLASS {cls_name}: {r[2]}")
            continue
        class_node_id = r[1]["node_id"]
        class_node_ids[cls_name] = class_node_id

        # 6. Add version for class (extract class source snippet)
        r = vs.Run("add_version", {
            "node_id": class_node_id,
            "content": f"# class {cls_name} from {file_name}\n# {len(cls_methods)} methods",
            "content_format": "SOURCE",
            "trace_id": trace_id,
        })
        if r[0] != 1:
            continue
        class_version_id = r[1]["version_id"]

        # 7. Attach class-level stamp (BCL summary as class intent)
        if summary:
            r = bs.Run("attach_stamp", {
                "node_id": class_node_id,
                "ast_version_id": class_version_id,
                "trace_id": trace_id,
                "scope_binding": "FULL",
                "intent_vector": {
                    "primary_goal": summary,
                    "domain": domain or "unknown",
                },
                "dependency_set": {"writes": []},
                "event_refs": [],
                "cause": "class-level reasoning from BCL header",
            })
            class_stamp_event_id = r[1]["event_id"] if r[0] == 1 else None
        else:
            class_stamp_event_id = None

        # 8. Create METHOD nodes
        for m in cls_methods:
            r = reg.Run("create_node", {
                "node_type": "METHOD",
                "symbolic_name": f"{cls_name}.{m['method']}",
                "parent_node_id": class_node_id,
                "file_path": f"Dom_Graph/{file_name}",
                "line_range": m["line_range"],
                "trace_id": trace_id,
                "cause": f"method {cls_name}.{m['method']}",
            })
            if r[0] != 1:
                continue
            method_node_id = r[1]["node_id"]
            method_node_ids[f"{cls_name}.{m['method']}"] = method_node_id

            # Add version for method
            r = vs.Run("add_version", {
                "node_id": method_node_id,
                "content": f"def {m['method']}(self, ...):  # lines {m['line_range']}",
                "content_format": "SOURCE",
                "trace_id": trace_id,
            })
            if r[0] != 1:
                continue
            method_version_id = r[1]["version_id"]

            # Attach method-level stamp (event_refs -> class stamp)
            r = bs.Run("attach_stamp", {
                "node_id": method_node_id,
                "ast_version_id": method_version_id,
                "trace_id": trace_id,
                "scope_binding": "FULL",
                "intent_vector": {
                    "primary_goal": f"Method {m['method']} of {cls_name}",
                    "line_range": m["line_range"],
                },
                "dependency_set": {"writes": []},
                "event_refs": [class_stamp_event_id] if class_stamp_event_id else [],
                "cause": "method-level reasoning",
            })

        # 9. Dependency edge: class -> file (CONTAINS)
        r = de.Run("add_edge", {
            "from_node_id": class_node_id,
            "to_node_id": file_node_id,
            "from_version_id": class_version_id,
            "edge_type": "CONTAINS",
        })

    # 10. Trace chain: parse -> register_nodes -> add_versions -> attach_stamps
    for step_no, decision in enumerate(
        ["PARSE_SOURCE", "REGISTER_NODES", "ADD_VERSIONS", "ATTACH_STAMPS",
         "BUILD_EDGES"], start=1):
        tc.Run("append_step", {
            "trace_id": trace_id,
            "decision": decision,
            "input_nodes": [file_node_id],
            "transformation": decision.lower(),
            "output_nodes": [file_node_id],
        })

    return {
        "file_node_id": file_node_id,
        "class_node_ids": class_node_ids,
        "method_node_ids": method_node_ids,
    }


def query_context_summary(db, log, replay):
    """Query the event-sourced graph and produce a structured summary."""
    print("\n" + "=" * 70)
    print("STRUCTURED CONTEXT SUMMARY (from in-RAM event-sourced graph)")
    print("=" * 70)

    # Counts
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_ast_nodes", "params": []})
    node_count = r[1]["rows"][0]["c"]
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_ast_versions", "params": []})
    version_count = r[1]["rows"][0]["c"]
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_bcl_stamps WHERE state_status='ACTIVE'", "params": []})
    stamp_count = r[1]["rows"][0]["c"]
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_trace_steps", "params": []})
    trace_count = r[1]["rows"][0]["c"]
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_dependency_edges", "params": []})
    edge_count = r[1]["rows"][0]["c"]
    r = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_events", "params": []})
    event_count = r[1]["rows"][0]["c"]

    print(f"\nGraph size: {node_count} nodes | {version_count} versions | "
          f"{stamp_count} stamps | {trace_count} trace steps | "
          f"{edge_count} edges | {event_count} events")

    # Node breakdown by type
    print("\n--- Nodes by type ---")
    r = db.Run("query", {
        "sql": "SELECT node_type, COUNT(*) as c FROM mu_ast_nodes GROUP BY node_type",
        "params": [],
    })
    for row in r[1]["rows"]:
        print(f"  {row['node_type']}: {row['c']}")

    # Files with their class+method counts and BCL summaries
    print("\n--- Files with reasoning (BCL stamps) ---")
    r = db.Run("query", {
        "sql": """SELECT n.node_id, n.symbolic_name, n.file_path,
                  s.intent_vector
                  FROM mu_ast_nodes n
                  LEFT JOIN mu_bcl_stamps s
                    ON s.node_id=n.node_id AND s.state_status='ACTIVE'
                       AND s.superseded_by IS NULL
                  WHERE n.node_type='FILE' AND n.destroyed_event_id IS NULL
                  ORDER BY n.node_id""",
        "params": [],
    })
    import json
    for row in r[1]["rows"]:
        intent = row["intent_vector"]
        if intent:
            try:
                iv = json.loads(intent) if isinstance(intent, str) else intent
                goal = iv.get("primary_goal", "?")
            except Exception:
                goal = "?"
        else:
            goal = "(no stamp)"
        print(f"  FILE #{row['node_id']} {row['symbolic_name']}")
        print(f"    intent: {goal}")

    # Classes with method counts
    print("\n--- Classes with method counts ---")
    r = db.Run("query", {
        "sql": """SELECT c.node_id, c.symbolic_name, c.file_path,
                  COUNT(m.node_id) as method_count
                  FROM mu_ast_nodes c
                  LEFT JOIN mu_ast_nodes m ON m.parent_node_id=c.node_id
                  WHERE c.node_type='CLASS' AND c.destroyed_event_id IS NULL
                  GROUP BY c.node_id ORDER BY c.node_id""",
        "params": [],
    })
    for row in r[1]["rows"]:
        print(f"  CLASS #{row['node_id']} {row['symbolic_name']} "
              f"({row['method_count']} methods) [{row['file_path']}]")

    # Methods with line ranges and stamp binding
    print("\n--- Methods with line ranges ---")
    r = db.Run("query", {
        "sql": """SELECT n.node_id, n.symbolic_name, n.line_range, n.file_path
                  FROM mu_ast_nodes n
                  WHERE n.node_type='METHOD' AND n.destroyed_event_id IS NULL
                  ORDER BY n.file_path, n.node_id""",
        "params": [],
    })
    for row in r[1]["rows"]:
        print(f"  METHOD #{row['node_id']} {row['symbolic_name']} "
              f"lines {row['line_range']} [{row['file_path']}]")

    # Verify continuity (strict)
    print("\n--- Continuity check (strict) ---")
    r = replay.Run("verify_continuity", {"strict": True})
    if r[0] == 1:
        print(f"  PASS: no orphan nodes, no broken traces, no stale edges")
    else:
        print(f"  FAIL: {r[2]}")

    # Deterministic replay check
    print("\n--- Deterministic replay check ---")
    # Get latest event id from EventLogStore (the durable truth), not mu_events
    # (which is only populated by some stores as a mirror).
    r = log.Run("read_state", {})
    latest_event = r[1]["next_id"] - 1
    if latest_event < 1:
        print("  SKIP: no events in log")
    else:
        r = replay.Run("rebuild_at", {"event_id": latest_event})
        if r[0] == 1:
            r2 = db.Run("query", {"sql": "SELECT COUNT(*) as c FROM mu_ast_nodes", "params": []})
            replayed_nodes = r2[1]["rows"][0]["c"]
            match = "PASS" if replayed_nodes == node_count else "FAIL"
            print(f"  Replayed {r[1]['events_applied']} events -> "
                  f"{replayed_nodes} nodes (matches original {node_count}): {match}")
            # Show continuity after replay
            r3 = replay.Run("verify_continuity", {"strict": True})
            if r3[0] == 1:
                print(f"  Post-replay strict continuity: PASS")
            else:
                print(f"  Post-replay strict continuity: FAIL - {r3[2]}")
        else:
            print(f"  FAIL: {r[2]}")


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    # Setup: fresh :memory: DB + temp event log
    tmpdir = tempfile.mkdtemp(prefix="memunit_use_")
    log_path = os.path.join(tmpdir, "memunit_events.log")

    db = InRamDb()
    r = db.Run("open", {})
    if r[0] != 1:
        print(f"FATAL: cannot open InRamDb: {r[2]}")
        return 1
    db.Run("init_schema", {})

    log = EventLogStore(param={"log_path": log_path})
    reg = AstNodeRegistry(mem=log, db=db)
    vs = AstVersionStore(mem=log, db=db)
    bs = BclStampStore(mem=log, db=db)
    tc = TraceChainStore(mem=log, db=db)
    de = DependencyEdgeStore(mem=log, db=db)
    replay = ReplayEngine(mem=log, db=db)

    trace_counter = [1]
    total_files = 0
    total_classes = 0
    total_methods = 0

    print("=" * 70)
    print("INGESTING REAL SOURCE FILES INTO EVENT-SOURCED CONTEXT GRAPH")
    print("=" * 70)

    for fname in TARGET_FILES:
        fpath = os.path.join(base, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP {fname} (not found)")
            continue
        with open(fpath, "r") as f:
            source = f.read()
        result = ingest_file(db, log, reg, vs, bs, tc, de, fname, source, trace_counter)
        if result:
            total_files += 1
            total_classes += len(result["class_node_ids"])
            total_methods += len(result["method_node_ids"])
            print(f"  INGESTED {fname}: "
                  f"{len(result['class_node_ids'])} classes, "
                  f"{len(result['method_node_ids'])} methods")

    print(f"\nIngestion complete: {total_files} files, "
          f"{total_classes} classes, {total_methods} methods")

    # Now query the graph for a structured summary
    query_context_summary(db, log, replay)

    # Cleanup
    db.Run("close", {})
    return 0


if __name__ == "__main__":
    sys.exit(main())
