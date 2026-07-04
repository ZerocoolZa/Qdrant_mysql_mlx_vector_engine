#!/usr/bin/env python3
"""
Execution Contracts — Node Guarantee Layer
==========================================
Makes every node type machine-verifiable and prevents invalid
graph transitions BEFORE runtime.

This answers: "How do I define the execution_contract schema so
every node type (plan/spec/flow/error) becomes machine-verifiable
and prevents invalid graph transitions before runtime?"

THE PROBLEM
-----------
Right now, decision_nodes have a node_type (question/action/check/fallback)
but no contract. The engine can't verify:
  - Is the input valid for this node?
  - Will the output match what the next node expects?
  - What failures are possible?
  - Is the edge to the next node a legal transition?

THE SOLUTION
------------
execution_contracts defines a TYPE SYSTEM for the graph:

  node_type → input_schema → output_schema → failure_modes → retry_policy

Every edge A→B is validated:
  1. Does A's output_schema produce a state that B's input_schema accepts?
  2. Is the edge condition a valid output state of A?
  3. Does B have a contract that covers the input A produces?

If any check fails, the transition is BLOCKED before runtime.
This prevents graph corruption.

CONTRACT STRUCTURE
------------------
Each contract is JSON with:
  input_schema:   {required_fields, types, constraints}
  output_states:  {state_name: {fields, types}}  — all possible outputs
  failure_modes:  {mode_name: {cause, recovery_edge_condition}}
  retry_policy:   {max_retries, backoff, on_exhausted}
  bcl_alignment:  which BCL token governs this contract

TRANSITION VALIDATION
---------------------
For edge A→B with condition C:
  1. C must be in A's output_states (can A actually produce state C?)
  2. B's input_schema must accept A's output for state C
  3. If C is a failure state, B must be a check or fallback node
  4. If C is a success state, B must be an action, check, or terminal node

This is compile-time checking for the execution graph.
"""

import sqlite3
import os
import json
import sys
from datetime import datetime

V20_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"


# ════════════════════════════════════════════════════════════════════════
# CONTRACT DEFINITIONS — one per node type
# ════════════════════════════════════════════════════════════════════════

CONTRACTS = {

    # ─── ACTION NODE CONTRACT ───
    # Action nodes execute a payload (BCL instruction or code).
    # They produce exactly two output states: "success" or "fail".
    "action": {
        "input_schema": {
            "required_fields": ["run_id", "node_id", "params"],
            "types": {"run_id": "string", "node_id": "int", "params": "dict"},
            "constraints": ["params must be JSON-serializable", "run_id must exist in run_state"]
        },
        "output_states": {
            "success": {
                "fields": {"status": "executed", "result": "any", "error": "null"},
                "meaning": "Payload executed without error"
            },
            "fail": {
                "fields": {"status": "failed", "result": "null", "error": "Tuple3_error"},
                "meaning": "Payload raised an error or returned (0, None, error)"
            }
        },
        "failure_modes": {
            "syntax_error": {
                "cause": "Payload code has syntax error",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "runtime_error": {
                "cause": "Payload raised exception at runtime",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "timeout": {
                "cause": "Payload exceeded time limit",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "missing_dependency": {
                "cause": "Payload requires a module/class not in DB",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "invalid_input": {
                "cause": "Input params don't match input_schema",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            }
        },
        "retry_policy": {
            "max_retries": 1,
            "backoff": "none",
            "on_exhausted": "traverse fail edge"
        },
        "bcl_alignment": "AddDomCode",
        "valid_incoming_edges": ["success", "pass", "answered", "retry"],  # actions reached via success, pass, or retry from fallback
        "valid_outgoing_edges": ["success", "fail"],
        "valid_next_node_types_on_success": ["action", "check", "question"],
        "valid_next_node_types_on_fail": ["fallback", "check"]
    },

    # ─── CHECK NODE CONTRACT ───
    # Check nodes evaluate a condition and produce "pass" or "fail".
    # They are gatekeepers — they decide which branch to take.
    "check": {
        "input_schema": {
            "required_fields": ["run_id", "node_id", "result_to_check"],
            "types": {"run_id": "string", "node_id": "int", "result_to_check": "any"},
            "constraints": ["result_to_check comes from prior action node output"]
        },
        "output_states": {
            "pass": {
                "fields": {"status": "pass", "condition": "string", "evaluated": "bool"},
                "meaning": "Condition evaluated to true"
            },
            "fail": {
                "fields": {"status": "fail", "condition": "string", "evaluated": "bool"},
                "meaning": "Condition evaluated to false"
            }
        },
        "failure_modes": {
            "condition_unparseable": {
                "cause": "Check condition is not valid Python/SQL",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "missing_input": {
                "cause": "result_to_check is None or missing",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            },
            "type_mismatch": {
                "cause": "result_to_check type doesn't match condition expectation",
                "recovery_edge_condition": "fail",
                "recovery_node_type": "fallback"
            }
        },
        "retry_policy": {
            "max_retries": 0,
            "backoff": "none",
            "on_exhausted": "traverse fail edge"
        },
        "bcl_alignment": "HowToVerify",
        "valid_incoming_edges": ["success", "pass", "fail"],
        "valid_outgoing_edges": ["pass", "fail", "success"],  # success aliased to pass
        "valid_next_node_types_on_success": ["action", "check", "question"],
        "valid_next_node_types_on_fail": ["fallback", "check", "action"]
    },

    # ─── QUESTION NODE CONTRACT ───
    # Question nodes pause execution and await input.
    # They produce "answered" or "timeout".
    "question": {
        "input_schema": {
            "required_fields": ["run_id", "node_id"],
            "types": {"run_id": "string", "node_id": "int"},
            "constraints": ["run must be in 'running' or 'paused' state"]
        },
        "output_states": {
            "answered": {
                "fields": {"status": "answered", "response": "string", "choice": "string"},
                "meaning": "User/AI provided an answer to the question"
            },
            "timeout": {
                "fields": {"status": "timeout", "response": "null", "choice": "null"},
                "meaning": "No answer received within time limit"
            }
        },
        "failure_modes": {
            "no_options": {
                "cause": "Question has no valid answer options",
                "recovery_edge_condition": "timeout",
                "recovery_node_type": "fallback"
            },
            "invalid_choice": {
                "cause": "Answer doesn't match any valid option",
                "recovery_edge_condition": "timeout",
                "recovery_node_type": "fallback"
            }
        },
        "retry_policy": {
            "max_retries": 3,
            "backoff": "linear",
            "on_exhausted": "traverse timeout edge"
        },
        "bcl_alignment": "WhenToAddCode",
        "valid_incoming_edges": ["success", "pass"],
        "valid_outgoing_edges": ["answered", "timeout", "success"],
        "valid_next_node_types_on_success": ["action", "check"],
        "valid_next_node_types_on_fail": ["fallback"]
    },

    # ─── FALLBACK NODE CONTRACT ───
    # Fallback nodes are recovery paths. They log the error and
    # either recover (producing "recovered") or give up ("unrecoverable").
    "fallback": {
        "input_schema": {
            "required_fields": ["run_id", "node_id", "failed_node_id", "error"],
            "types": {"run_id": "string", "node_id": "int", "failed_node_id": "int", "error": "Tuple3"},
            "constraints": ["error must be a Tuple3 (code, message, severity)", "failed_node_id must exist"]
        },
        "output_states": {
            "recovered": {
                "fields": {"status": "recovered", "recovery_action": "string", "resume_from": "int"},
                "meaning": "Error was handled, execution can resume from resume_from node"
            },
            "retry": {
                "fields": {"status": "retry", "retry_node": "int", "attempt": "int"},
                "meaning": "Recovery action is to retry the failed node"
            },
            "unrecoverable": {
                "fields": {"status": "unrecoverable", "recovery_action": "null", "reason": "string"},
                "meaning": "Error cannot be recovered, run must terminate"
            }
        },
        "failure_modes": {
            "no_recovery_path": {
                "cause": "No recovery action defined for this error type",
                "recovery_edge_condition": "unrecoverable",
                "recovery_node_type": None  # terminal
            },
            "recovery_failed": {
                "cause": "Recovery action itself raised an error",
                "recovery_edge_condition": "unrecoverable",
                "recovery_node_type": None
            },
            "loop_detected": {
                "cause": "Fallback points back to a node already visited in this run",
                "recovery_edge_condition": "unrecoverable",
                "recovery_node_type": None
            }
        },
        "retry_policy": {
            "max_retries": 0,
            "backoff": "none",
            "on_exhausted": "traverse unrecoverable edge"
        },
        "bcl_alignment": "ErrorDecisionTree",
        "valid_incoming_edges": ["fail", "timeout", "unrecoverable"],
        "valid_outgoing_edges": ["recovered", "retry", "unrecoverable", "success"],
        "valid_next_node_types_on_success": ["action", "check"],  # resume after recovery
        "valid_next_node_types_on_fail": [],  # terminal — no further nodes
        "valid_next_node_types_on_retry": ["action"]  # retry goes back to an action node
    },
}


# ════════════════════════════════════════════════════════════════════════
# TRANSITION VALIDATOR
# Checks every edge in the graph against contracts.
# Invalid transitions are blocked BEFORE runtime.
# ════════════════════════════════════════════════════════════════════════

class TransitionValidator:
    """Validates graph transitions against execution contracts.

    For every edge A→B with condition C:
      1. Is C a valid output state of A's contract?
      2. Does B's contract accept the input A produces?
      3. Is the node type transition legal?
      4. Does B have a contract at all?

    Returns: list of valid edges and list of violations.
    """

    def __init__(self, conn):
        self.conn = conn
        self.c = conn.cursor()
        self.contracts = {}
        self.violations = []
        self.valid_edges = []

    def load_contracts(self):
        """Load contracts from execution_contracts table."""
        self.c.execute("SELECT node_type, contract_json FROM execution_contracts")
        for row in self.c.fetchall():
            self.contracts[row[0]] = json.loads(row[1])
        return len(self.contracts)

    def validate_edge(self, from_node, to_node, condition):
        """Validate a single edge. Returns (is_valid, reason)."""
        from_type = from_node["node_type"]
        to_type = to_node["node_type"]

        # 1. Does from_node have a contract?
        from_contract = self.contracts.get(from_type)
        if not from_contract:
            return False, f"No contract for node type '{from_type}' (node {from_node['node_id']})"

        # 2. Does to_node have a contract?
        to_contract = self.contracts.get(to_type)
        if not to_contract:
            return False, f"No contract for node type '{to_type}' (node {to_node['node_id']})"

        # 3. Is the condition a valid output state of from_node?
        output_states = from_contract.get("output_states", {})
        valid_outgoing = from_contract.get("valid_outgoing_edges", [])

        # Normalize condition (success=pass for check nodes, etc.)
        condition_normalized = condition
        if condition == "success" and "pass" in output_states and "success" not in output_states:
            condition_normalized = "pass"
        if condition == "pass" and "success" in output_states and "pass" not in output_states:
            condition_normalized = "success"

        if condition_normalized not in output_states and condition not in valid_outgoing:
            return False, (f"Edge condition '{condition}' is not a valid output state of "
                          f"{from_type} node {from_node['node_id']}. "
                          f"Valid states: {list(output_states.keys()) + valid_outgoing}")

        # 4. Is the node type transition legal?
        # Check if to_type is valid for this condition
        if condition in ("success", "pass", "answered", "recovered"):
            valid_next = from_contract.get("valid_next_node_types_on_success", [])
        elif condition in ("fail", "timeout", "unrecoverable"):
            valid_next = from_contract.get("valid_next_node_types_on_fail", [])
        elif condition == "retry":
            valid_next = from_contract.get("valid_next_node_types_on_retry", [])
        else:
            valid_next = list(set(
                from_contract.get("valid_next_node_types_on_success", []) +
                from_contract.get("valid_next_node_types_on_fail", [])
            ))

        if valid_next and to_type not in valid_next:
            return False, (f"Invalid transition: {from_type}→{to_type} on condition '{condition}'. "
                          f"{from_type} can only go to {valid_next} on '{condition}', "
                          f"but target is {to_type}")

        # 5. Does to_node accept the incoming edge condition?
        valid_incoming = to_contract.get("valid_incoming_edges", [])
        if valid_incoming and condition not in valid_incoming:
            # Check aliases
            aliases = {"success": ["pass", "answered", "recovered", "retry"],
                       "pass": ["success"],
                       "fail": ["timeout", "unrecoverable"],
                       "retry": ["success"]}
            found_alias = any(condition in aliases.get(c, []) for c in valid_incoming)
            if not found_alias:
                return False, (f"Node {to_node['node_id']} ({to_type}) doesn't accept "
                              f"incoming edge condition '{condition}'. "
                              f"Accepts: {valid_incoming}")

        return True, "valid"

    def validate_all(self):
        """Validate every edge in the graph. Returns (valid_count, violations)."""
        self.violations = []
        self.valid_edges = []

        # Get all nodes
        self.c.execute("SELECT node_id, name, node_type FROM decision_nodes")
        nodes = {r[0]: {"node_id": r[0], "name": r[1], "node_type": r[2]} for r in self.c.fetchall()}

        # Get all edges
        self.c.execute("SELECT edge_id, from_node, to_node, condition, weight FROM decision_edges")
        edges = self.c.fetchall()

        for edge_id, from_id, to_id, condition, weight in edges:
            from_node = nodes.get(from_id)
            to_node = nodes.get(to_id)

            if not from_node:
                self.violations.append({
                    "edge_id": edge_id,
                    "type": "missing_from_node",
                    "message": f"Edge {edge_id}: from_node {from_id} doesn't exist"
                })
                continue

            if not to_node:
                self.violations.append({
                    "edge_id": edge_id,
                    "type": "missing_to_node",
                    "message": f"Edge {edge_id}: to_node {to_id} doesn't exist"
                })
                continue

            is_valid, reason = self.validate_edge(from_node, to_node, condition)

            if is_valid:
                self.valid_edges.append({
                    "edge_id": edge_id,
                    "from": from_id,
                    "to": to_id,
                    "condition": condition,
                    "from_type": from_node["node_type"],
                    "to_type": to_node["node_type"]
                })
            else:
                self.violations.append({
                    "edge_id": edge_id,
                    "from": from_id,
                    "to": to_id,
                    "condition": condition,
                    "type": "invalid_transition",
                    "message": reason
                })

        # Also check for nodes with no outgoing edges (dead ends)
        for nid, node in nodes.items():
            if node["node_type"] != "fallback":  # fallback can be terminal
                has_outgoing = any(e[1] == nid for e in edges)
                if not has_outgoing and node["node_type"] not in ("fallback",):
                    # Check if it's a terminal node (name suggests it)
                    if node["name"] and any(x in node["name"].lower() for x in ["end", "success", "terminal", "complete"]):
                        continue  # terminal nodes are OK
                    self.violations.append({
                        "node_id": nid,
                        "type": "dead_end",
                        "message": f"Node {nid} ({node['name']}, {node['node_type']}) has no outgoing edges"
                    })

        # Check for nodes with no incoming edges (orphans, except root)
        for nid, node in nodes.items():
            has_incoming = any(e[2] == nid for e in edges)
            if not has_incoming and nid != 1 and node["node_type"] != "question":
                # Root node (id=1) is expected to have no incoming
                self.violations.append({
                    "node_id": nid,
                    "type": "orphan",
                    "message": f"Node {nid} ({node['name']}) has no incoming edges — unreachable"
                })

        return len(self.valid_edges), self.violations


# ════════════════════════════════════════════════════════════════════════
# SCHEMA CREATION + SEEDING
# ════════════════════════════════════════════════════════════════════════

def create_schema(conn):
    """Create execution_contracts, graph_schema_registry, view_descriptors tables."""
    c = conn.cursor()

    # ─── execution_contracts ───
    c.execute("DROP TABLE IF EXISTS execution_contracts")
    c.execute("""
        CREATE TABLE execution_contracts (
            contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_type TEXT NOT NULL UNIQUE,
            contract_json TEXT NOT NULL,
            input_schema TEXT,
            output_schema TEXT,
            failure_modes TEXT,
            retry_policy TEXT,
            bcl_alignment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── graph_schema_registry ───
    c.execute("DROP TABLE IF EXISTS graph_schema_registry")
    c.execute("""
        CREATE TABLE graph_schema_registry (
            schema_id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            schema_type TEXT NOT NULL,
            definition TEXT NOT NULL,
            version TEXT DEFAULT '1.0',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── view_descriptors ───
    c.execute("DROP TABLE IF EXISTS view_descriptors")
    c.execute("""
        CREATE TABLE view_descriptors (
            view_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT NOT NULL,
            query_template TEXT NOT NULL,
            layout_type TEXT NOT NULL,
            interaction_model TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    print("  Created: execution_contracts, graph_schema_registry, view_descriptors")


def seed_contracts(conn):
    """Seed execution_contracts with the 4 node type contracts."""
    c = conn.cursor()

    for node_type, contract in CONTRACTS.items():
        contract_json = json.dumps(contract, indent=2)
        input_schema = json.dumps(contract["input_schema"])
        output_schema = json.dumps(contract["output_states"])
        failure_modes = json.dumps(contract["failure_modes"])
        retry_policy = json.dumps(contract["retry_policy"])
        bcl_alignment = contract.get("bcl_alignment", "")

        c.execute("""
            INSERT INTO execution_contracts
                (node_type, contract_json, input_schema, output_schema,
                 failure_modes, retry_policy, bcl_alignment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (node_type, contract_json, input_schema, output_schema,
              failure_modes, retry_policy, bcl_alignment))

    conn.commit()
    print(f"  Seeded {len(CONTRACTS)} execution contracts: {', '.join(CONTRACTS.keys())}")


def seed_schema_registry(conn):
    """Seed graph_schema_registry with schema definitions."""
    c = conn.cursor()

    schemas = [
        ("graph_engine", "node",
         json.dumps({"types": ["question", "action", "check", "fallback"],
                     "fields": ["node_id", "name", "node_type", "payload", "domain"],
                     "constraints": ["every node must have a contract",
                                     "every node must have at least one outgoing edge (except terminal)"]}),
         "1.0"),

        ("graph_engine", "edge",
         json.dumps({"fields": ["edge_id", "from_node", "to_node", "condition", "weight"],
                     "conditions": ["success", "fail", "pass", "timeout", "recovered", "unrecoverable", "answered"],
                     "constraints": ["condition must match from_node output_states",
                                     "to_node must accept incoming condition",
                                     "weight >= 0.0 and weight <= 1.0"]}),
         "1.0"),

        ("graph_engine", "view",
         json.dumps({"views": ["plan", "spec", "flow", "lifecycle", "dependency",
                               "error", "orchestration", "gap"],
                     "rule": "views are SQL projections over decision_nodes + decision_edges, not separate systems"}),
         "1.0"),

        ("graph_engine", "bcl_mapping",
         json.dumps({"rule": "bcl_instructions.token_name → decision_nodes.payload",
                     "binding": "each action node's payload references a BCL token",
                     "execution": "engine reads BCL from bcl_instructions, follows it as graph"}),
         "1.0"),
    ]

    for domain, schema_type, definition, version in schemas:
        c.execute("""
            INSERT INTO graph_schema_registry (domain, schema_type, definition, version)
            VALUES (?, ?, ?, ?)
        """, (domain, schema_type, definition, version))

    conn.commit()
    print(f"  Seeded {len(schemas)} schema registry entries")


def seed_view_descriptors(conn):
    """Seed view_descriptors with SQL-based view definitions."""
    c = conn.cursor()

    views = [
        ("plan", "graph_engine",
         "SELECT n.node_id, n.name, n.node_type, e.to_node, e.condition FROM decision_nodes n LEFT JOIN decision_edges e ON n.node_id = e.from_node WHERE n.node_type = 'action' ORDER BY n.node_id",
         "tree", "click_to_expand"),

        ("spec", "graph_engine",
         "SELECT n.node_id, n.name, n.node_type, n.payload FROM decision_nodes n WHERE n.node_type IN ('action','check') ORDER BY n.node_id",
         "circular", "click_to_inspect"),

        ("flow", "graph_engine",
         "SELECT e.from_node, e.to_node, e.condition, n1.name as from_name, n2.name as to_name FROM decision_edges e JOIN decision_nodes n1 ON e.from_node = n1.node_id JOIN decision_nodes n2 ON e.to_node = n2.node_id ORDER BY e.from_node, e.weight DESC",
         "linear", "step_through"),

        ("lifecycle", "graph_engine",
         "SELECT n.node_id, n.name, n.node_type, n.created_at FROM decision_nodes n ORDER BY n.node_type, n.node_id",
         "swimlane", "filter_by_type"),

        ("dependency", "graph_engine",
         "SELECT e.from_node, e.to_node, e.condition, e.weight FROM decision_edges e WHERE e.condition = 'success' ORDER BY e.from_node",
         "graph", "trace_chain"),

        ("error", "graph_engine",
         "SELECT n.node_id, n.name, n.payload FROM decision_nodes n WHERE n.node_type = 'fallback' ORDER BY n.node_id",
         "graph", "highlight_recovery"),

        ("orchestration", "graph_engine",
         "SELECT n.node_id, n.name, n.node_type, COUNT(e.edge_id) as edge_count FROM decision_nodes n LEFT JOIN decision_edges e ON n.node_id = e.from_node GROUP BY n.node_id ORDER BY edge_count DESC",
         "tree", "collapse_branches"),

        ("gap", "graph_engine",
         "SELECT n.node_id, n.name, n.node_type FROM decision_nodes n WHERE n.node_id NOT IN (SELECT from_node FROM decision_edges) AND n.node_type != 'fallback'",
         "graph", "show_missing"),
    ]

    for name, domain, query, layout, interaction in views:
        c.execute("""
            INSERT INTO view_descriptors (name, domain, query_template, layout_type, interaction_model)
            VALUES (?, ?, ?, ?, ?)
        """, (name, domain, query, layout, interaction))

    conn.commit()
    print(f"  Seeded {len(views)} view descriptors")


def document_tables(conn):
    """Document the new tables in _table_registry and _column_docs."""
    c = conn.cursor()

    # _table_registry entries
    new_tables = [
        ("execution_contracts", "execution", "Defines input/output/failure/retry contracts per node type. Prevents invalid graph transitions before runtime.", "node_type, contract_json", "Type system for the execution graph"),
        ("graph_schema_registry", "execution", "Locks schema definitions for nodes, edges, views, and BCL mappings. Prevents schema drift.", "domain, schema_type, definition", "Schema stability layer"),
        ("view_descriptors", "execution", "DB-defined view specs. Views are SQL projections, not GUI logic.", "name, query_template, layout_type", "View = query definition, not code"),
    ]

    for table_name, layer, purpose, key_cols, notes in new_tables:
        c.execute("SELECT COUNT(*) FROM _table_registry WHERE table_name=?", (table_name,))
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO _table_registry (table_name, layer, purpose, key_columns, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (table_name, layer, purpose, key_cols, notes))

    # _column_docs entries
    column_docs = [
        ("execution_contracts", "contract_id", "Primary key — unique contract ID"),
        ("execution_contracts", "node_type", "Which node type this contract covers: action, check, question, fallback"),
        ("execution_contracts", "contract_json", "Full contract as JSON — input_schema, output_states, failure_modes, retry_policy, bcl_alignment"),
        ("execution_contracts", "input_schema", "What input the node requires (fields, types, constraints)"),
        ("execution_contracts", "output_schema", "All possible output states and their fields"),
        ("execution_contracts", "failure_modes", "Named failure modes with causes and recovery edges"),
        ("execution_contracts", "retry_policy", "How many retries, backoff strategy, what to do when exhausted"),
        ("execution_contracts", "bcl_alignment", "Which BCL instruction token governs this contract"),

        ("graph_schema_registry", "schema_id", "Primary key"),
        ("graph_schema_registry", "domain", "Which domain this schema applies to"),
        ("graph_schema_registry", "schema_type", "node, edge, view, or bcl_mapping"),
        ("graph_schema_registry", "definition", "JSON schema definition"),
        ("graph_schema_registry", "version", "Schema version for evolution tracking"),

        ("view_descriptors", "view_id", "Primary key"),
        ("view_descriptors", "name", "View name: plan, spec, flow, lifecycle, dependency, error, orchestration, gap"),
        ("view_descriptors", "domain", "Which domain this view projects"),
        ("view_descriptors", "query_template", "SQL query that produces the view data — views are SQL projections"),
        ("view_descriptors", "layout_type", "tree, graph, swimlane, circular, linear"),
        ("view_descriptors", "interaction_model", "How the user interacts: click_to_expand, step_through, trace_chain, etc."),
    ]

    for table_name, column_name, meaning in column_docs:
        c.execute("SELECT COUNT(*) FROM _column_docs WHERE table_name=? AND column_name=?", (table_name, column_name))
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO _column_docs (table_name, column_name, meaning)
                VALUES (?, ?, ?)
            """, (table_name, column_name, meaning))

    conn.commit()
    print(f"  Documented {len(new_tables)} tables and {len(column_docs)} columns")


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("EXECUTION CONTRACTS — Node Guarantee Layer")
    print("Prevents invalid graph transitions before runtime")
    print("=" * 70)

    conn = sqlite3.connect(V20_DB)
    conn.row_factory = sqlite3.Row

    # Phase A: Schema Lock
    print("\n[Phase A] Schema Lock — creating 3 structural tables...")
    create_schema(conn)

    print("\n[Phase A] Seeding contracts...")
    seed_contracts(conn)
    seed_schema_registry(conn)
    seed_view_descriptors(conn)

    print("\n[Phase A] Documenting tables...")
    document_tables(conn)

    # Validate existing graph against contracts
    print("\n[Validation] Checking existing 44 nodes + 43 edges against contracts...")
    validator = TransitionValidator(conn)
    contract_count = validator.load_contracts()
    print(f"  Loaded {contract_count} contracts")

    valid_count, violations = validator.validate_all()
    print(f"  Valid edges: {valid_count}")
    print(f"  Violations: {len(violations)}")

    if violations:
        print("\n  ── VIOLATIONS ──")
        for v in violations[:20]:
            if "edge_id" in v:
                print(f"    [{v['type']}] edge {v['edge_id']}: {v['message'][:100]}")
            else:
                print(f"    [{v['type']}] node {v['node_id']}: {v['message'][:100]}")
        if len(violations) > 20:
            print(f"    ... and {len(violations) - 20} more")
    else:
        print("  ✅ All edges pass contract validation")

    # Show contract summary
    print("\n[Summary] Execution contracts:")
    c = conn.cursor()
    c.execute("SELECT node_type, bcl_alignment, LENGTH(contract_json) as size FROM execution_contracts")
    for r in c.fetchall():
        print(f"  {r[0]:12} BCL={r[1]:20} {r[2]:>5} chars")

    # Show what the validator checks
    print("\n[Transition Rules] What the validator checks per edge A→B:")
    print("  1. Does A have a contract? (type system coverage)")
    print("  2. Does B have a contract? (type system coverage)")
    print("  3. Is the edge condition a valid output state of A?")
    print("  4. Is the node type transition A→B legal for this condition?")
    print("  5. Does B accept this incoming edge condition?")
    print("  6. Are there dead-end nodes (no outgoing edges)?")
    print("  7. Are there orphan nodes (no incoming edges)?")

    # Show view descriptors
    print("\n[Views] SQL-based view descriptors (views = projections, not code):")
    c.execute("SELECT name, layout_type, interaction_model FROM view_descriptors")
    for r in c.fetchall():
        print(f"  {r[0]:15} layout={r[1]:10} interaction={r[2]}")

    # Show schema registry
    print("\n[Schema Registry] Locked schema definitions:")
    c.execute("SELECT schema_type, version FROM graph_schema_registry")
    for r in c.fetchall():
        print(f"  {r[0]:15} v{r[1]}")

    print("\n" + "=" * 70)
    print("PHASE A COMPLETE — SCHEMA LOCKED")
    print("=" * 70)
    print("""
  3 new tables created:
    ✅ execution_contracts    — type system for nodes (4 contracts)
    ✅ graph_schema_registry  — schema stability (4 definitions)
    ✅ view_descriptors       — views as SQL projections (8 views)

  Existing graph validated:
    {} valid edges
    {} violations to fix

  What this enables:
    - DecisionEngine can now check contracts BEFORE traversing an edge
    - Invalid transitions are blocked at compile time, not runtime
    - Views are SQL queries, not Python code
    - Schema drift is prevented by the registry

  Next: Phase B/C — Build DecisionEngine that uses these contracts
  to safely walk the graph.
""".format(valid_count, len(violations)))

    conn.close()


if __name__ == "__main__":
    main()
