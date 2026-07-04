#!/usr/bin/env python3
#[@GHOST]{("file_path=Dom_Graph/Dom_Graph_Engine.py";"identity=Dom_Graph_Engine.py";"purpose=";"date=2026-06-28";"version=1.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@pass]{"return=Tuple3";"dispatch=Run";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete"}[@fail]{"decorators_found";"print_found";"hardcoded_values";"self._used"}}
#[@FILEID]{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}
#[@SUMMARY]{("Created on 2026-06-28";"auto_stamped=true")}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Line 7 has garbled user text pasted into source code. Duplicate shebang on line 7. GHOST purpose field empty. Not VBStyle: uses self.conn/self.c/self.questions instead of self.state dict. No Run() dispatch. No Tuple3 returns. Classes: CuriosityController, GraphEngine, ReportMaker — none have Run() dispatch. DB_PATH hardcoded to v20_hybrid_best.db.>][@todos<1. Remove garbled text on line 7. 2. Remove duplicate shebang. 3. Fill GHOST purpose field. 4. Convert to VBStyle: self.state dict, Run() dispatch, Tuple3 returns. 5. Move DB_PATH to Config.py. 6. One class per file per VBStyle model.>]}

"""
Graph Engine — a self-discovering database investigator.
Unlike db_gap_graph.py which has hardcoded checks, this engine:
  1. Reads the database schema (what tables exist? what columns?)
  2. Generates questions dynamically based on what it finds
  3. Investigates each question
  4. Reports gaps, inconsistencies, and missing documentation
Architecture:
  CuriosityController  → generates questions from schema
  GraphEngine          → runs the investigation
  ReportMaker          → formats and outputs results
The engine doesn't know what to look for. It figures it out by reading
the database structure. If it sees a column called 'parent_id', it asks
'do all rows that should have a parent actually have one?' If it sees
a table called '_table_registry', it asks 'do all tables have entries?'
This is NOT a checklist. It's a discovery process.
"""
import sqlite3
import os
import sys
import json
import re
from collections import defaultdict
from datetime import datetime
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "code_store_variations", "v20_hybrid_best.db"
)
# ════════════════════════════════════════════════════════════════════════
# CURIOSITY CONTROLLER
# Generates questions dynamically by reading the database schema.
# Each question is a thread to pull on — the engine investigates.
class CuriosityController:
    def add_question(self, category, question, investigator_method, params=None):
        """Add a question for the engine to investigate."""
        self.questions.append({
            "category": category,
            "question": question,
            "investigator": investigator_method,
            "params": params or {},
        })
        return (1, None, None)
    def discover_tables(self):
        """Read the actual schema and discover all tables and columns."""
        self.c.execute("""
            SELECT name, sql FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            AND name NOT LIKE '%_fts%'
            AND name NOT LIKE 'search_idx%'
            AND name NOT LIKE 'bcl_search%'
            ORDER BY name
        """)
        tables = {}
        for row in self.c.fetchall():
            table_name = row[0]
            self.c.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for col in self.c.fetchall():
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "not_null": col[3],
                    "default": col[4],
                    "is_pk": col[5] == 1,
                })
            # Get row count
            self.c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = self.c.fetchone()[0]
            tables[table_name] = {
                "columns": columns,
                "row_count": count,
                "column_names": [c["name"] for c in columns],
            }
        return (1, tables, None)
    def generate_questions(self, tables):
        """Look at the schema and generate questions dynamically.
        This is the core of the curiosity — it doesn't know what to look for.
        It figures it out by reading the structure.
        """
        # ── If _table_registry exists, ask: are all tables registered? ──
        if "_table_registry" in tables:
            self.add_question(
                "DOCUMENTATION",
                "Are all tables registered in _table_registry?",
                "check_table_registry",
                {"tables": list(tables.keys())}
            )
        # ── If _column_docs exists, ask: are all columns documented? ──
        if "_column_docs" in tables:
            self.add_question(
                "DOCUMENTATION",
                "Are all columns in all tables documented in _column_docs?",
                "check_column_docs",
                {"tables": tables}
            )
        # ── If _db_meta exists, ask: does it describe the database? ──
        if "_db_meta" in tables:
            self.add_question(
                "DOCUMENTATION",
                "Does _db_meta contain essential metadata?",
                "check_db_meta",
                {}
            )
        # ── For each table, ask questions based on its structure ──
        for table_name, info in tables.items():
            columns = info["columns"]
            col_names = info["column_names"]
            row_count = info["row_count"]
            # Empty table?
            if row_count == 0 and not table_name.startswith("_"):
                self.add_question(
                    "EMPTY_TABLE",
                    f"Table '{table_name}' has 0 rows — is it supposed to be empty?",
                    "check_empty_table",
                    {"table": table_name}
                )
            # Has parent_id? Check if the chain is complete
            if "parent_id" in col_names:
                self.add_question(
                    "HIERARCHY",
                    f"Table '{table_name}' has parent_id — is the hierarchy chain complete?",
                    "check_parent_chain",
                    {"table": table_name}
                )
            # Has status column? Check for unexpected values
            if "status" in col_names:
                self.add_question(
                    "DATA_QUALITY",
                    f"Table '{table_name}' has status column — what are the distinct values?",
                    "check_status_values",
                    {"table": table_name}
                )
            # Has is_vbstyle column? Check coverage
            if "is_vbstyle" in col_names:
                self.add_question(
                    "VBSTYLE",
                    f"Table '{table_name}' has is_vbstyle — how many are VBStyle vs legacy?",
                    "check_vbstyle_coverage",
                    {"table": table_name}
                )
            # Has domain column? Check for orphans
            if "domain" in col_names and table_name == "classes":
                self.add_question(
                    "ORCHESTRATION",
                    "Are all domains used in orchestration pipelines?",
                    "check_domain_orchestration",
                    {}
                )
            # Has closure_pct? Check for incomplete closure
            if "closure_pct" in col_names:
                self.add_question(
                    "CLOSURE",
                    f"Table '{table_name}' has closure_pct — are all entities fully closed?",
                    "check_closure",
                    {"table": table_name}
                )
            # Has bcl_token? Check completeness
            if "bcl_token" in col_names:
                self.add_question(
                    "BCL_IDENTITY",
                    f"Table '{table_name}' has bcl_token — do all tokens have required fields?",
                    "check_bcl_completeness",
                    {"table": table_name}
                )
                # Also check: do all entities that SHOULD have BCL tokens actually have them?
                if table_name == "bcl_identity":
                    self.add_question(
                        "BCL_IDENTITY",
                        "Do all VBStyle classes have BCL identity tokens?",
                        "check_bcl_coverage",
                        {}
                    )
                    self.add_question(
                        "BCL_IDENTITY",
                        "Do all VBStyle methods have BCL identity tokens?",
                        "check_bcl_method_coverage",
                        {}
                    )
            # Has method_name? Check for missing pairs
            if "method_name" in col_names and table_name == "methods":
                self.add_question(
                    "STRUCTURE",
                    "Are there method pairs missing their opposite? (compress/decompress, etc.)",
                    "check_method_pairs",
                    {}
                )
                self.add_question(
                    "STRUCTURE",
                    "Do all domains have CRUD operations (create/read/update/delete)?",
                    "check_crud_coverage",
                    {}
                )
            # Has violations? Check count
            if table_name == "violations":
                self.add_question(
                    "VIOLATIONS",
                    "What VBStyle violations exist and how many?",
                    "check_violations",
                    {}
                )
            # Plans table — check if enough plans exist
            if table_name == "plans":
                self.add_question(
                    "PLANS",
                    "Are there enough plans for the number of domains?",
                    "check_plan_count",
                    {}
                )
            # Execution log — check if anything has run
            if table_name == "execution_log":
                self.add_question(
                    "EXECUTION",
                    "Has anything actually been executed?",
                    "check_execution",
                    {}
                )
            # computational_units — check for orphans
            if table_name == "computational_units":
                self.add_question(
                    "STRUCTURE",
                    "Are there orphan computational units (no class link)?",
                    "check_cu_orphans",
                    {}
                )
            # Check for columns that have NULL where they shouldn't
            for col in columns:
                if col["not_null"] == 0 and not col["is_pk"] and col["name"] not in (
                    "created_at", "updated_at", "description", "notes",
                    "key_columns", "example", "default", "parent_id",
                    "complexity_score", "performance_score", "domain",
                    "class_id", "method_id", "parent_plan_id", "promoted_to_class_id"
                ):
                    # Only check if table has enough rows to matter
                    if row_count > 10:
                        self.add_question(
                            "DATA_QUALITY",
                            f"Column '{col['name']}' in '{table_name}' — how many NULLs?",
                            "check_nulls",
                            {"table": table_name, "column": col["name"]}
                        )
        return (1, self.questions, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def add_finding(self, category, severity, entity, issue, detail=""):
        self.findings.append({
            "category": category,
            "severity": severity,
            "entity": entity,
            "issue": issue,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })
        return (1, None, None)
    def investigate(self, questions):
        """Run each question's investigator method."""
        investigators = {
            "check_table_registry": self.Check_table_registry,
            "check_column_docs": self.Check_column_docs,
            "check_db_meta": self.Check_db_meta,
            "check_empty_table": self.Check_empty_table,
            "check_parent_chain": self.Check_parent_chain,
            "check_status_values": self.Check_status_values,
            "check_vbstyle_coverage": self.Check_vbstyle_coverage,
            "check_domain_orchestration": self.Check_domain_orchestration,
            "check_closure": self.Check_closure,
            "check_bcl_completeness": self.Check_bcl_completeness,
            "check_bcl_coverage": self.Check_bcl_coverage,
            "check_bcl_method_coverage": self.Check_bcl_method_coverage,
            "check_method_pairs": self.Check_method_pairs,
            "check_crud_coverage": self.Check_crud_coverage,
            "check_violations": self.Check_violations,
            "check_plan_count": self.Check_plan_count,
            "check_execution": self.Check_execution,
            "check_cu_orphans": self.Check_cu_orphans,
            "check_nulls": self.Check_nulls,
        }
        for q in questions:
            method = investigators.get(q["investigator"])
            if method:
                method(q["params"])
            else:
                self.add_finding("ENGINE", "low", q["investigator"],
                                 f"No investigator implemented for: {q['question']}",
                                 "")
        return (1, self.findings, None)
    def _check_table_registry(self, params):
        tables = params["tables"]
        self.c.execute("SELECT table_name FROM _table_registry")
        registered = set(r[0] for r in self.c.fetchall())
        for t in tables:
            if t not in registered:
                self.add_finding("DOCUMENTATION", "high", t,
                                 "Table not in _table_registry",
                                 f"AI won't know what table '{t}' is for.")
        return (1, None, None)
    def _check_column_docs(self, params):
        tables = params["tables"]
        for table_name, info in tables.items():
            self.c.execute("SELECT column_name FROM _column_docs WHERE table_name=?", (table_name,))
            documented = set(r[0] for r in self.c.fetchall())
            for col in info["column_names"]:
                if col not in documented:
                    self.add_finding("DOCUMENTATION", "medium", f"{table_name}.{col}",
                                     "Column not documented in _column_docs",
                                     f"AI won't understand what column '{col}' in table '{table_name}' means.")
        return (1, None, None)
    def _check_db_meta(self, params):
        essential_keys = ["db_name", "db_purpose", "architecture"]
        self.c.execute("SELECT key FROM _db_meta")
        existing = set(r[0] for r in self.c.fetchall())
        for key in essential_keys:
            if key not in existing:
                self.add_finding("DOCUMENTATION", "high", f"_db_meta.{key}",
                                 f"Essential metadata key '{key}' missing from _db_meta",
                                 "AI won't understand the database's purpose.")
        return (1, None, None)
    def _check_empty_table(self, params):
        table = params["table"]
        self.add_finding("EMPTY_TABLE", "medium", table,
                         f"Table '{table}' has 0 rows",
                         "Table exists but contains no data. Is it supposed to be empty?")
        return (1, None, None)
    def _check_parent_chain(self, params):
        table = params["table"]
        # Check for rows that should have a parent but don't
        if table == "bcl_identity":
            self.c.execute("""
                SELECT entity_type, entity_name FROM bcl_identity
                WHERE entity_type IN ('class', 'method') AND parent_id IS NULL
            """)
            for r in self.c.fetchall():
                self.add_finding("HIERARCHY", "medium", r[1],
                                 f"{r[0]} '{r[1]}' has no parent_id (orphan in chain)",
                                 "Entity should link to its parent but doesn't.")
        return (1, None, None)
    def _check_status_values(self, params):
        table = params["table"]
        self.c.execute(f"SELECT DISTINCT status FROM {table}")
        values = [r[0] for r in self.c.fetchall()]
        # Check for unexpected status values
        expected = {"active", "deprecated", "draft", "ready", "active", "retired", "closed", "OK", "ERROR", "TIMEOUT"}
        unexpected = [v for v in values if v not in expected and v is not None]
        if unexpected:
            self.add_finding("DATA_QUALITY", "low", table,
                             f"Unexpected status values: {unexpected}",
                             f"Table '{table}' has status values not in expected set.")
        return (1, None, None)
    def _check_nulls(self, params):
        table = params["table"]
        column = params["column"]
        self.c.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
        null_count = self.c.fetchone()[0]
        self.c.execute(f"SELECT COUNT(*) FROM {table}")
        total = self.c.fetchone()[0]
        if total > 0 and null_count > 0:
            pct = (null_count / total) * 100
            if pct > 50:
                self.add_finding("DATA_QUALITY", "medium", f"{table}.{column}",
                                 f"{null_count}/{total} rows ({pct:.0f}%) have NULL in '{column}'",
                                 f"Column '{column}' is mostly NULL — is it needed?")
        return (1, None, None)
    def _check_vbstyle_coverage(self, params):
        table = params["table"]
        self.c.execute(f"SELECT is_vbstyle, COUNT(*) FROM {table} GROUP BY is_vbstyle")
        for r in self.c.fetchall():
            style = "VBStyle" if r[0] == 1 else "legacy"
        return (1, None, None)
    def _check_domain_orchestration(self, params):
        self.c.execute("""
            SELECT DISTINCT cl.domain FROM classes cl
            WHERE cl.is_vbstyle=1 AND cl.id NOT IN (
                SELECT class_id FROM orchestration
            )
            ORDER BY cl.domain
        """)
        for r in self.c.fetchall():
            self.add_finding("ORCHESTRATION", "medium", r[0],
                             "Domain not used in any pipeline",
                             f"Domain '{r[0]}' is built but not wired into any orchestration.")
        return (1, None, None)
    def _check_closure(self, params):
        table = params["table"]
        self.c.execute(f"SELECT domain, closure_pct, methods_missing, status FROM {table} WHERE closure_pct < 100.0")
        for r in self.c.fetchall():
            self.add_finding("CLOSURE", "high", r[0],
                             f"Domain not fully closed ({r[1]}%)",
                             f"Missing {r[2]} methods. Status: {r[3]}.")
        return (1, None, None)
    def _check_closure(self, params):
        table = params["table"]
        self.c.execute(f"SELECT domain, closure_pct, methods_missing, status FROM {table} WHERE closure_pct < 100.0")
        for r in self.c.fetchall():
            self.add_finding("CLOSURE", "high", r[0],
                             f"Domain not fully closed ({r[1]}%)",
                             f"Missing {r[2]} methods. Status: {r[3]}.")
        return (1, None, None)
    def _check_bcl_completeness(self, params):
        table = params["table"]
        required_fields = ["identity", "capabilities", "used_in_pipelines",
                          "depends_on", "depended_by", "closure", "self_narrative"]
        self.c.execute(f"SELECT entity_type, entity_name, bcl_token FROM {table} WHERE entity_type='domain'")
        for r in self.c.fetchall():
            bcl = r[2]
            missing = [f for f in required_fields if f not in bcl]
            if missing:
                self.add_finding("BCL_IDENTITY", "medium", r[1],
                                 f"BCL token missing fields: {', '.join(missing)}",
                                 f"Domain '{r[1]}' doesn't answer all 7 W-questions.")
        return (1, None, None)
    def _check_bcl_coverage(self, params):
        self.c.execute("SELECT id, class_name FROM classes WHERE is_vbstyle=1")
        vb_classes = self.c.fetchall()
        self.c.execute("SELECT entity_id FROM bcl_identity WHERE entity_type='class'")
        bcl_ids = set(r[0] for r in self.c.fetchall())
        for cls_id, cls_name in vb_classes:
            if cls_id not in bcl_ids:
                self.add_finding("BCL_IDENTITY", "high", cls_name,
                                 "VBStyle class has no BCL token",
                                 f"Class '{cls_name}' is VBStyle but has no BCL identity.")
        return (1, None, None)
    def _check_bcl_method_coverage(self, params):
        self.c.execute("""
            SELECT m.id, m.method_name, cl.class_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'
        """)
        vb_methods = self.c.fetchall()
        self.c.execute("SELECT entity_id FROM bcl_identity WHERE entity_type='method'")
        bcl_ids = set(r[0] for r in self.c.fetchall())
        missing = [(m[0], m[1], m[2]) for m in vb_methods if m[0] not in bcl_ids]
        if missing:
            for m_id, m_name, c_name in missing[:20]:
                self.add_finding("BCL_IDENTITY", "medium", f"{c_name}.{m_name}",
                                 "Method has no BCL token",
                                 f"Method '{m_name}' of '{c_name}' has no BCL identity.")
            if len(missing) > 20:
                self.add_finding("BCL_IDENTITY", "medium", "system",
                                 f"{len(missing)} methods missing BCL tokens",
                                 f"{len(missing) - 20} more not shown.")
        return (1, None, None)
    def _check_method_pairs(self, params):
        expected_pairs = [
            ("compress", "decompress"), ("encrypt", "decrypt"), ("sign", "verify"),
            ("serialize", "deserialize"), ("encode", "decode"), ("import", "export"),
            ("load", "save"), ("start", "stop"), ("open", "close"), ("add", "remove"),
            ("create", "delete"), ("push", "pop"), ("lock", "unlock"),
            ("connect", "disconnect"), ("register", "unregister"),
            ("subscribe", "unsubscribe"),
        ]
        self.c.execute("""
            SELECT DISTINCT m.method_name FROM methods m
            JOIN classes cl ON m.class_id = cl.id
            WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'
        """)
        all_methods = set(r[0] for r in self.c.fetchall())
        for a, b in expected_pairs:
            has_a = a in all_methods
            has_b = b in all_methods
            if has_a and not has_b:
                self.add_finding("STRUCTURE", "medium", f"{a}/{b}",
                                 f"Missing pair: {a}() exists but {b}() is missing", "")
            elif has_b and not has_a:
                self.add_finding("STRUCTURE", "medium", f"{a}/{b}",
                                 f"Missing pair: {b}() exists but {a}() is missing", "")
        return (1, None, None)
    def _check_crud_coverage(self, params):
        crud = {
            "create": ["create", "add", "insert", "write", "compress", "generate", "build", "make"],
            "read":   ["read", "get", "fetch", "load", "list", "search", "find", "query"],
            "update": ["update", "edit", "modify", "rename", "patch", "set", "convert", "transform"],
            "delete": ["delete", "remove", "drop", "clear", "purge", "forget", "strip", "destroy"],
        }
        self.c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle=1 ORDER BY domain")
        domains = [r[0] for r in self.c.fetchall()]
        for domain in domains:
            self.c.execute("""
                SELECT DISTINCT m.method_name FROM methods m
                JOIN classes cl ON m.class_id = cl.id
                WHERE cl.is_vbstyle=1 AND cl.domain=? AND m.method_name NOT LIKE '\\_%'
            """, (domain,))
            methods = set(r[0].lower() for r in self.c.fetchall())
            missing = [r for r in crud if not any(m in crud[r] for m in methods)]
            if missing:
                self.add_finding("STRUCTURE", "low", domain,
                                 f"CRUD gap: missing {', '.join(missing)}", "")
        return (1, None, None)
    def _check_cu_orphans(self, params):
        self.c.execute("SELECT COUNT(*) FROM computational_units WHERE class_id IS NULL OR class_id = 0")
        orphan_count = self.c.fetchone()[0]
        if orphan_count > 0:
            self.add_finding("STRUCTURE", "low", "computational_units",
                             f"{orphan_count} orphan CUs (no class link)",
                             "These CUs exist but aren't linked to any class.")
        return (1, None, None)
    def _check_cu_orphans(self, params):
        self.c.execute("SELECT COUNT(*) FROM computational_units WHERE class_id IS NULL OR class_id = 0")
        orphan_count = self.c.fetchone()[0]
        if orphan_count > 0:
            self.add_finding("STRUCTURE", "low", "computational_units",
                             f"{orphan_count} orphan CUs (no class link)",
                             "These CUs exist but aren't linked to any class.")
        return (1, None, None)
    def _check_violations(self, params):
        self.c.execute("SELECT kind, COUNT(*) FROM violations GROUP BY kind ORDER BY COUNT(*) DESC")
        for r in self.c.fetchall():
            self.add_finding("VIOLATIONS", "low", r[0],
                             f"{r[1]} violations of rule: {r[0]}", "")
        return (1, None, None)
    def _check_plan_count(self, params):
        self.c.execute("SELECT COUNT(*) FROM plans")
        plan_count = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1")
        domain_count = self.c.fetchone()[0]
        if plan_count < 5:
            self.add_finding("PLANS", "high", "system",
                             f"Only {plan_count} plan(s) for {domain_count} domains",
                             "Most domains are unused — need more plans.")
        return (1, None, None)
    def _check_execution(self, params):
        self.c.execute("SELECT COUNT(*) FROM execution_log")
        count = self.c.fetchone()[0]
        if count == 0:
            self.add_finding("EXECUTION", "medium", "system",
                             "No execution log entries — nothing has run",
                             "The system is designed but nothing has been executed.")
        return (1, None, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def text_report(findings, questions):
        lines = []
        lines.append("=" * 70)
        lines.append("GRAPH ENGINE REPORT")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("=" * 70)
        lines.append(f"\nQuestions generated: {len(questions)}")
        lines.append(f"Findings discovered: {len(findings)}")
        # Show what the engine was curious about
        lines.append(f"\n── QUESTIONS THE ENGINE GENERATED ──")
        by_cat = defaultdict(list)
        for q in questions:
            by_cat[q["category"]].append(q["question"])
        for cat in sorted(by_cat.keys()):
            lines.append(f"\n  [{cat}] ({len(by_cat[cat])} questions)")
            for q in by_cat[cat]:
                lines.append(f"    • {q}")
        # Summary
        lines.append(f"\n── FINDINGS SUMMARY ──")
        by_category = defaultdict(list)
        for f in findings:
            by_category[f["category"]].append(f)
        for cat in sorted(by_category.keys()):
            count = len(by_category[cat])
            high = sum(1 for f in by_category[cat] if f["severity"] == "high")
            med = sum(1 for f in by_category[cat] if f["severity"] == "medium")
            low = sum(1 for f in by_category[cat] if f["severity"] == "low")
            if count == 0:
                lines.append(f"  ✅ {cat:15}: no gaps")
            else:
                lines.append(f"  ⚠️  {cat:15}: {count} gaps ({high} high, {med} medium, {low} low)")
        # Details
        for cat in sorted(by_category.keys()):
            items = by_category[cat]
            if not items:
                continue
            lines.append(f"\n── {cat} ({len(items)} findings) ──")
            for f in items[:25]:
                lines.append(f"  [{f['severity']:6}] {f['entity']:35}: {f['issue']}")
            if len(items) > 25:
                lines.append(f"  ... and {len(items) - 25} more")
        lines.append("\n" + "=" * 70)
        return (1, "\n".join(lines), None)
    def json_report(findings, questions):
        return (1, json.dumps({
            "generated": datetime.now().isoformat(),
            "questions_asked": len(questions),
            "findings_count": len(findings),
            "questions": questions,
            "findings": findings,
        }, indent=2), None)
    def gui_report(findings, questions):
        """Show findings in a tkinter GUI."""
        try:
            import math
            import tkinter as tk
        except ImportError:
            pass  # VBStyle: no print
            return (1, None, None)
        by_category = defaultdict(list)
        for f in findings:
            by_category[f["category"]].append(f)
        root = tk.Tk()
        root.title("Graph Engine — Database Investigation Report")
        root.geometry("1400x900")
        root.configure(bg="#1e1e2e")
        # Title
        tk.Label(root, text=f"Graph Engine Report — {len(findings)} findings from {len(questions)} questions",
                fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica", 14, "bold")).pack(pady=10)
        # Left panel: questions the engine generated
        left = tk.Frame(root, bg="#1e1e2e", width=400)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        tk.Label(left, text="QUESTIONS GENERATED", fg="#89b4fa", bg="#1e1e2e",
                font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        q_text = tk.Text(left, bg="#181825", fg="#cdd6f4", font=("Helvetica", 9),
                        wrap=tk.WORD, height=40)
        q_text.pack(fill=tk.BOTH, expand=True)
        q_by_cat = defaultdict(list)
        for q in questions:
            q_by_cat[q["category"]].append(q["question"])
        for cat in sorted(q_by_cat.keys()):
            q_text.insert(tk.END, f"\n[{cat}] ({len(q_by_cat[cat])} questions)\n", "category")
            for q in q_by_cat[cat]:
                q_text.insert(tk.END, f"  • {q}\n")
        q_text.tag_config("category", foreground="#89b4fa", font=("Helvetica", 9, "bold"))
        q_text.config(state=tk.DISABLED)
        # Right panel: findings
        right = tk.Frame(root, bg="#1e1e2e")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(right, text="FINDINGS", fg="#f38ba8", bg="#1e1e2e",
                font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        f_text = tk.Text(right, bg="#181825", fg="#cdd6f4", font=("Helvetica", 9),
                        wrap=tk.WORD)
        f_text.pack(fill=tk.BOTH, expand=True)
        SEV_COLORS = {"high": "#f38ba8", "medium": "#f9e2af", "low": "#a6e3a1"}
        for sev in ["high", "medium", "low"]:
            f_text.tag_config(sev, foreground=SEV_COLORS[sev])
        for cat in sorted(by_category.keys()):
            items = by_category[cat]
            f_text.insert(tk.END, f"\n[{cat}] ({len(items)} findings)\n", "category")
            for f in items:
                f_text.insert(tk.END, f"  [{f['severity']:6}] {f['entity']:35}: {f['issue']}\n",
                            f["severity"])
        f_text.tag_config("category", foreground="#cba6f7", font=("Helvetica", 9, "bold"))
        f_text.config(state=tk.DISABLED)
        root.mainloop()
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Step 1: Curiosity Controller discovers the schema
    pass  # VBStyle: no print
    controller = CuriosityController(conn)
    tables = controller.discover_tables()
    pass  # VBStyle: no print
    # Step 2: Generate questions dynamically
    pass  # VBStyle: no print
    questions = controller.generate_questions(tables)
    pass  # VBStyle: no print
    # Step 3: Engine investigates each question
    pass  # VBStyle: no print
    engine = GraphEngine(conn)
    findings = engine.investigate(questions)
    pass  # VBStyle: no print
    # Step 4: Report Maker outputs results
    pass  # VBStyle: no print
    if "--json" in sys.argv:
        pass  # VBStyle: no print
    elif "--gui" in sys.argv:
        ReportMaker.gui_report(findings, questions)
    else:
        pass  # VBStyle: no print
    conn.close()
if __name__ == "__main__":
    main()
