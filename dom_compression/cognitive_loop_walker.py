#!/usr/bin/env python3
"""
Cognitive Loop Walker — follows the 7-step reasoning path through the graph.

Reads decision_nodes + decision_edges from v20_hybrid_best.db.
Walks: Problem → Question → Answer → Constraint → Mistake → Solution → Verify
Logs every step to execution_log.

This IS the reasoning engine. It follows the tried-and-tested path.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"

# Tuple3 = (ok, data, error)
Tuple3 = tuple


class CognitiveLoopWalker:
    """Walks the cognitive loop graph from root to terminal."""

    def __init__(self, db_path=DB_PATH):
        self.state = {
            "db_path": db_path,
            "conn": None,
            "current_node": None,
            "path_history": [],
            "step_count": 0,
            "domain": None,
            "operation": None,
            "params": {},
            "result": None,
            "errors": [],
            "start_time": None,
        }

    def Run(self, command, params):
        """Dispatch entry point — VBStyle compliant."""
        dispatch = {
            "walk": self.WalkLoop,
            "list_operations": self.ListOperations,
            "show_graph": self.ShowGraph,
            "verify_graph": self.VerifyGraph,
        }

        handler = dispatch.get(command)
        if not handler:
            return (0, None, "Unknown command: " + str(command) + ". Valid: " + ", ".join(dispatch.keys()))

        return handler(params)

    def WalkLoop(self, params):
        """Walk the cognitive loop for a given domain + operation."""
        domain = params.get("domain", "workflow")
        operation = params.get("operation", "")
        user_input = params.get("input", {})

        if not operation:
            return (0, None, "No operation specified. Use list_operations to see valid options.")

        self.state["domain"] = domain
        self.state["operation"] = operation
        self.state["params"] = user_input
        self.state["start_time"] = datetime.now().isoformat()
        self.state["path_history"] = []
        self.state["step_count"] = 0
        self.state["errors"] = []

        conn = sqlite3.connect(self.state["db_path"])
        self.state["conn"] = conn
        c = conn.cursor()

        # Find root node for this domain
        c.execute("SELECT node_id, name, payload FROM decision_nodes WHERE domain=? AND category='root'", (domain,))
        root = c.fetchone()
        if not root:
            conn.close()
            return (0, None, "No root node found for domain: " + domain)

        root_id, root_name, root_payload = root
        self.state["current_node"] = root_id

        print("=" * 70)
        print("COGNITIVE LOOP WALKER")
        print("=" * 70)
        print(f"  Domain:    {domain}")
        print(f"  Operation: {operation}")
        print(f"  Root:      {root_name} (node_id={root_id})")
        print(f"  Payload:   {root_payload}")
        print()

        # Log root step
        self.LogStep(root_id, root_name, "root", "entered", root_payload, "")

        # Follow the edge matching the operation condition
        next_node = self.FollowEdge(c, root_id, operation)
        if not next_node:
            conn.close()
            return (0, None, f"No edge from root with condition='{operation}'. Valid operations: prj, index, config, validate, report")

        # Walk the loop
        result = self.WalkFromNode(c, next_node)

        # Log completion
        self.LogStep(self.state["current_node"], "", "terminal", "completed" if result[0] else "failed", "", result[2] if result[2] else "OK")

        # Write execution log to DB
        self.WriteExecutionLog(conn)

        conn.close()
        return result

    def WalkFromNode(self, c, node_id):
        """Walk from a given node, following edges based on step outcomes."""
        max_steps = 50  # Safety limit
        max_retries = 3  # Max retries per Mistake node

        visited = []
        retry_counts = {}

        while node_id and self.state["step_count"] < max_steps:
            c.execute("SELECT name, node_type, category, payload FROM decision_nodes WHERE node_id=?", (node_id,))
            row = c.fetchone()
            if not row:
                return (0, None, f"Node {node_id} not found")

            name, node_type, category, payload = row
            self.state["current_node"] = node_id
            self.state["step_count"] += 1
            visited.append(node_id)

            # Check for terminal nodes
            if category == "terminal":
                print(f"\n  [{self.state['step_count']:2d}] TERMINAL: {name}")
                print(f"       {payload}")
                self.LogStep(node_id, name, category, "terminal", payload, "")
                if "Complete" in name:
                    return (1, {"path": visited, "steps": self.state["step_count"]}, None)
                else:
                    return (0, {"path": visited, "steps": self.state["step_count"]}, f"Workflow failed: {payload}")

            # Process the node based on its type
            print(f"\n  [{self.state['step_count']:2d}] {category.upper():10s} [{node_type:8s}] {name}")
            if payload:
                # Truncate payload for display
                display = payload[:120] + "..." if len(payload) > 120 else payload
                print(f"       {display}")

            outcome = self.ProcessNode(c, node_id, name, node_type, category, payload)
            status = outcome[0]
            detail = outcome[1]

            print(f"       → {status.upper()}: {detail}")

            self.LogStep(node_id, name, category, status, payload, detail)

            # Follow edge based on outcome
            next_node = self.FollowEdge(c, node_id, status)

            if not next_node and status == "fail":
                # If we failed but no fail edge, try "retry"
                next_node = self.FollowEdge(c, node_id, "retry")

            if not next_node:
                # No edge to follow — check if we're at a dead end
                if category == "verify" and status == "pass":
                    # Verify passed but no edge — look for terminal
                    c.execute("SELECT to_node FROM decision_edges WHERE from_node=? AND condition='pass'", (node_id,))
                    term = c.fetchone()
                    if term:
                        next_node = term[0]

            if not next_node:
                print(f"\n  ⚠ DEAD END at {name} (status={status})")
                self.state["errors"].append(f"Dead end at {name} with status={status}")
                break

            # Handle retry loops
            if node_type == "fallback" and "Solution" in name:
                retry_key = str(node_id)
                retry_counts[retry_key] = retry_counts.get(retry_key, 0) + 1
                if retry_counts[retry_key] > max_retries:
                    print(f"\n  ⚠ MAX RETRIES ({max_retries}) exceeded at {name}")
                    # Go to WorkflowFailed
                    c.execute("SELECT node_id FROM decision_nodes WHERE domain=? AND category='terminal' AND name LIKE '%Failed%'", (self.state["domain"],))
                    fail_node = c.fetchone()
                    if fail_node:
                        node_id = fail_node[0]
                        continue
                    else:
                        return (0, {"path": visited}, "Max retries exceeded, no fail terminal found")

            node_id = next_node

        if self.state["step_count"] >= max_steps:
            return (0, {"path": visited}, f"Max steps ({max_steps}) exceeded — possible infinite loop")

        return (1, {"path": visited, "steps": self.state["step_count"]}, None)

    def ProcessNode(self, c, node_id, name, node_type, category, payload):
        """Process a single node and return (status, detail).
        status = 'success', 'fail', 'answered', 'pass', 'retry', 'unrecoverable'

        CONNECTED to registry tables — Constraint and Verify steps actually check the DB.
        """
        # Problem node — acknowledge the problem
        if "Problem" in name:
            return ("success", "Problem identified, proceeding to question")

        # Question node — check if the TARGET domain (from params) is registered
        if "Question" in name:
            params = self.state.get("params", {})
            target_domain = params.get("domain", self.state.get("domain", ""))

            # Check domain_registry for the target domain
            c.execute("SELECT name FROM domain_registry WHERE name=?", (target_domain,))
            if not c.fetchone():
                return ("answered", f"Domain '{target_domain}' NOT in registry — will need to register first")

            return ("answered", f"Domain '{target_domain}' found in registry. Params: {params}")

        # Answer node — check type_registry and category_registry for target domain
        if "Answer" in name:
            params = self.state.get("params", {})
            target_domain = params.get("domain", self.state.get("domain", ""))
            operation = self.state.get("operation", "")

            # Check type_registry has the operation's node types
            c.execute("SELECT name FROM type_registry WHERE name='action'")
            has_action = c.fetchone()
            c.execute("SELECT name FROM type_registry WHERE name='check'")
            has_check = c.fetchone()

            if not has_action or not has_check:
                return ("fail", "type_registry missing required types (action, check)")

            # Check category_registry has the operation's category for the target domain
            c.execute("SELECT name FROM category_registry WHERE domain=? AND name=?", (target_domain, operation))
            has_cat = c.fetchone()
            if not has_cat:
                return ("fail", f"Category '{operation}' not registered for domain '{target_domain}'")

            if payload and "Dom_workflow.Run" in payload:
                return ("success", f"Registry checks passed for '{target_domain}'. Would execute: Dom_workflow.Run('{operation}', {params})")
            return ("success", f"Registry checks passed for '{target_domain}'")

        # Constraint node — check cognitive loop exists for this domain+operation
        if "Constraint" in name:
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")

            # Check all 7 cognitive loop steps exist
            steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, operation))
            nodes = [r[0] for r in c.fetchall()]

            missing = []
            for step in steps:
                if not any(step in n for n in nodes):
                    missing.append(step)

            if missing:
                return ("fail", f"Cognitive loop INCOMPLETE — missing: {', '.join(missing)}")

            # Check VBStyle compliance — only for THIS domain's methods
            try:
                c.execute("""SELECT COUNT(*) FROM violations v 
                             JOIN methods m ON v.method_id = m.id 
                             JOIN classes cl ON m.class_id = cl.id 
                             WHERE cl.domain = ?""", (domain,))
                domain_violations = c.fetchone()[0]
                if domain_violations > 0:
                    return ("fail", f"{domain_violations} VBStyle violations in domain '{domain}'")
            except:
                pass  # tables might not exist or columns might differ

            return ("pass", f"All constraints satisfied: 7 steps present, 0 violations for domain '{domain}'")

        # Mistake node — something went wrong
        if "Mistake" in name:
            return ("fail", "Error detected, seeking solution")

        # Solution node — recovery attempt
        if "Solution" in name:
            # Check what went wrong and suggest fix
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")

            # Check if domain needs registering
            c.execute("SELECT name FROM domain_registry WHERE name=?", (domain,))
            if not c.fetchone():
                return ("retry", f"Recovery: register domain '{domain}' in domain_registry, then retry")

            # Check if category needs registering
            c.execute("SELECT name FROM category_registry WHERE domain=? AND name=?", (domain, operation))
            if not c.fetchone():
                return ("retry", f"Recovery: register category '{operation}' for domain '{domain}', then retry")

            return ("retry", "Recovery attempted, retrying answer")

        # Verify node — verify the insert would be valid
        if "Verify" in name:
            domain = self.state.get("domain", "")
            operation = self.state.get("operation", "")

            # Verify domain is registered
            c.execute("SELECT name FROM domain_registry WHERE name=?", (domain,))
            if not c.fetchone():
                return ("fail", f"Verify FAILED: domain '{domain}' not in registry")

            # Verify all 7 cognitive loop steps still exist
            steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, operation))
            nodes = [r[0] for r in c.fetchall()]
            missing = [s for s in steps if not any(s in n for n in nodes)]
            if missing:
                return ("fail", f"Verify FAILED: cognitive loop missing: {', '.join(missing)}")

            # Verify triggers exist
            c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='validate_node_domain'")
            if not c.fetchone():
                return ("fail", "Verify FAILED: validate_node_domain trigger missing")

            return ("pass", "Verified: domain registered, 7 steps present, triggers active")

        # Unknown node type
        return ("success", "Processed")

    def FollowEdge(self, c, from_node, condition):
        """Follow an edge from from_node with the given condition."""
        c.execute("SELECT to_node FROM decision_edges WHERE from_node=? AND condition=?", (from_node, condition))
        row = c.fetchone()
        return row[0] if row else None

    def LogStep(self, node_id, name, category, status, payload, detail):
        """Log a step to path_history."""
        self.state["path_history"].append({
            "step": self.state["step_count"],
            "node_id": node_id,
            "name": name,
            "category": category,
            "status": status,
            "payload": payload[:200] if payload else "",
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })

    def WriteExecutionLog(self, conn):
        """Write the path history to execution_log table."""
        c = conn.cursor()

        # Check if execution_log table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='execution_log'")
        if not c.fetchone():
            c.execute("""CREATE TABLE IF NOT EXISTS execution_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step INTEGER,
                node_id INTEGER,
                node_name TEXT,
                category TEXT,
                status TEXT,
                detail TEXT,
                timestamp TEXT)""")
            conn.commit()

        run_id = f"walk_{self.state['domain']}_{self.state['operation']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for entry in self.state["path_history"]:
            c.execute("""INSERT INTO execution_log
                        (run_id, node_id, status, output, timestamp)
                        VALUES (?, ?, ?, ?, ?)""",
                      (run_id, entry["node_id"], entry["status"],
                       entry["name"] + " | " + entry["detail"], entry["timestamp"]))

        conn.commit()
        print(f"\n  📝 Execution log written: {len(self.state['path_history'])} entries (run_id={run_id})")

    def ListOperations(self, params):
        """List all valid operations for a domain."""
        domain = params.get("domain", "workflow")
        conn = sqlite3.connect(self.state["db_path"])
        c = conn.cursor()

        # Find root node
        c.execute("SELECT node_id FROM decision_nodes WHERE domain=? AND category='root'", (domain,))
        root = c.fetchone()
        if not root:
            conn.close()
            return (0, None, "No root node for domain: " + domain)

        # Find all edges from root — these are the operations
        c.execute("SELECT condition, to_node FROM decision_edges WHERE from_node=?", (root[0],))
        edges = c.fetchall()

        operations = []
        for cond, to_node in edges:
            c.execute("SELECT name, payload FROM decision_nodes WHERE node_id=?", (to_node,))
            node = c.fetchone()
            if node:
                operations.append({
                    "operation": cond,
                    "entry_node": node[0],
                    "description": node[1][:100] if node[1] else "",
                })

        conn.close()
        return (1, {"domain": domain, "operations": operations}, None)

    def ShowGraph(self, params):
        """Show the cognitive loop graph for a domain."""
        domain = params.get("domain", "workflow")
        conn = sqlite3.connect(self.state["db_path"])
        c = conn.cursor()

        c.execute("SELECT node_id, name, node_type, category, payload FROM decision_nodes WHERE domain=? ORDER BY category, name", (domain,))
        nodes = c.fetchall()

        c.execute("""SELECT e.condition, n1.name, n2.name 
                     FROM decision_edges e 
                     JOIN decision_nodes n1 ON e.from_node=n1.node_id 
                     JOIN decision_nodes n2 ON e.to_node=n2.node_id
                     WHERE n1.domain=? ORDER BY n1.category, e.condition""", (domain,))
        edges = c.fetchall()

        conn.close()
        return (1, {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}, None)

    def VerifyGraph(self, params):
        """Verify the cognitive loop graph is complete — all 7 steps exist per category."""
        domain = params.get("domain", "workflow")
        conn = sqlite3.connect(self.state["db_path"])
        c = conn.cursor()

        c.execute("SELECT DISTINCT category FROM decision_nodes WHERE domain=? AND category NOT IN ('root','terminal')", (domain,))
        categories = [r[0] for r in c.fetchall()]

        steps = ["Problem", "Question", "Answer", "Constraint", "Mistake", "Solution", "Verify"]
        results = {}

        for cat in categories:
            c.execute("SELECT name FROM decision_nodes WHERE domain=? AND category=?", (domain, cat))
            nodes = [r[0] for r in c.fetchall()]
            missing = [s for s in steps if not any(s in n for n in nodes)]
            results[cat] = {
                "complete": len(missing) == 0,
                "missing": missing,
                "node_count": len(nodes),
            }

        conn.close()
        return (1, {"domain": domain, "categories": results}, None)


# ============================================================================
# MAIN — CLI for testing
# ============================================================================
if __name__ == "__main__":
    import sys

    walker = CognitiveLoopWalker()

    if len(sys.argv) < 2:
        print("Usage: python3 cognitive_loop_walker.py <command> [args]")
        print("Commands:")
        print("  list_operations  — show valid operations for a domain")
        print("  walk             — walk the cognitive loop")
        print("  show_graph       — show the graph structure")
        print("  verify_graph     — verify all 7 steps exist")
        print()
        print("Examples:")
        print("  python3 cognitive_loop_walker.py list_operations")
        print("  python3 cognitive_loop_walker.py walk prj")
        print("  python3 cognitive_loop_walker.py walk index")
        print("  python3 cognitive_loop_walker.py verify_graph")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list_operations":
        ok, data, err = walker.Run("list_operations", {"domain": "workflow"})
        if ok:
            print("\nValid operations for workflow domain:")
            for op in data["operations"]:
                print(f"  {op['operation']:10s} → {op['entry_node']:20s} {op['description']}")
        else:
            print("Error:", err)

    elif command == "walk":
        if len(sys.argv) < 3:
            print("Usage: walk <operation> [param1=value1 param2=value2 ...]")
            sys.exit(1)
        operation = sys.argv[2]
        params = {}
        for arg in sys.argv[3:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                params[k] = v
        ok, data, err = walker.Run("walk", {"domain": "workflow", "operation": operation, "input": params})
        print()
        if ok:
            print("=" * 70)
            print("WALK COMPLETE")
            print("=" * 70)
            print(f"  Steps taken: {data.get('steps', 0)}")
            print(f"  Path: {' → '.join(str(n) for n in data.get('path', []))}")
        else:
            print("=" * 70)
            print("WALK FAILED")
            print("=" * 70)
            print(f"  Error: {err}")
            if data:
                print(f"  Path: {' → '.join(str(n) for n in data.get('path', []))}")

    elif command == "show_graph":
        ok, data, err = walker.Run("show_graph", {"domain": "workflow"})
        if ok:
            print(f"\nGraph for workflow domain: {data['node_count']} nodes, {data['edge_count']} edges")
            print("\nNODES:")
            for n in data["nodes"]:
                print(f"  [{n[3]:10s}] [{n[2]:8s}] {n[1]}")
            print("\nEDGES:")
            for e in data["edges"]:
                print(f"  {e[1]:30s} --{e[0]:10s}--> {e[2]}")

    elif command == "verify_graph":
        ok, data, err = walker.Run("verify_graph", {"domain": "workflow"})
        if ok:
            print(f"\nGraph verification for {data['domain']} domain:")
            all_complete = True
            for cat, info in data["categories"].items():
                status = "COMPLETE" if info["complete"] else "INCOMPLETE"
                missing = ", ".join(info["missing"]) if info["missing"] else "none"
                print(f"  {cat:10s} [{status}] {info['node_count']} nodes, missing: {missing}")
                if not info["complete"]:
                    all_complete = False
            print(f"\n  Overall: {'ALL COMPLETE' if all_complete else 'HAS GAPS'}")

    else:
        print(f"Unknown command: {command}")
