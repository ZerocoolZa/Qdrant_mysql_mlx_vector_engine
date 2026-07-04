#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<Graph Engine v2 implementing CognitiveLoop pattern (Problem-Question-Answer-Constraint-Solution-Verify-Loop). 7 connected parts. No #[@...] headers. No Run dispatch. No Tuple3 returns. Multiple classes (CuriosityController, GraphEngine, ConstraintChecker, SolutionSuggester, MistakeRecorder, ReportMaker, GuiDisplayer). Has hardcoded DB_PATH.>][@todos<Add #[@GHOST]/#[@VBSTYLE]/#[@FILEID]/#[@SUMMARY]/#[@CLASS]/#[@METHOD] headers. Add Run dispatch and Tuple3. Split classes into separate files. Move DB_PATH to Config.py.>]}
"""
Graph Engine v2 — follows the CognitiveLoop pattern from MySQL.
The [@CognitiveLoop] token describes the full reasoning loop:
    Problem → Question → Answer → Constraint → Solution → Verify → Loop
This engine implements that loop as 7 connected parts:
    1. Problem Finder      — what needs investigating? (reads schema)
    2. Question Generator  — what to ask? (curiosity)
    3. Answer Discoverer   — investigate, find facts (engine)
    4. Constraint Checker  — what rules apply? (validation)
    5. Solution Suggester  — what should we do? (recommendations)
    6. Mistake Recorder    — what went wrong before? (history)
    7. Report + GUI        — show everything (output)
The loop: after Solution, Verify checks if it worked. If not,
back to Problem with new knowledge.
Architecture:
    CuriosityController  → generates questions from schema
    GraphEngine          → runs the investigation
    ConstraintChecker    → checks findings against rules
    SolutionSuggester    → recommends fixes for each gap
    MistakeRecorder      → checks MySQL learned_rules for past mistakes
    ReportMaker          → formats and outputs results
    Guidisplayer         → visualizes the graph
This is NOT a checklist. It's a cognitive loop that discovers,
investigates, validates, suggests, and learns.
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
# PART 1: PROBLEM FINDER + QUESTION GENERATOR (Curiosity Controller)
# Reads the schema, discovers what exists, generates questions.
# ════════════════════════════════════════════════════════════════════════
class CuriosityController:
    """Reads the database schema and generates questions dynamically.
    This is the 'Question' phase of the CognitiveLoop:
        Problem → QUESTION → Answer → Constraint → Solution → Verify
    It doesn't know what to look for. It discovers the schema
    and generates questions based on what it finds.
    """
    def __init__(self):
        self.mistakes = []
        self.mysql_conn = None
        try:
            self.mysql_conn = sqlite3.connect(":memory:")  # placeholder
            # Try MySQL connection
            import subprocess
            # We'll use subprocess to query MySQL since we might not have mysql connector
        except:
            pass
    def discover_schema(self):
        """Read the actual database schema — all tables, columns, counts."""
        self.c.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            AND name NOT LIKE '%_fts%'
            AND name NOT LIKE 'search_idx%'
            AND name NOT LIKE 'bcl_search%'
            ORDER BY name
        """)
        tables = [r[0] for r in self.c.fetchall()]
        for table_name in tables:
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
            self.c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = self.c.fetchone()[0]
            self.schema[table_name] = {
                "columns": columns,
                "column_names": [c["name"] for c in columns],
                "row_count": count,
            }
        return (1, self.schema, None)
    def add_question(self, category, question, investigator, params=None, priority="normal"):
        self.questions.append({
            "category": category,
            "question": question,
            "investigator": investigator,
            "params": params or {},
            "priority": priority,
        })
        return (1, None, None)
    def generate_questions(self):
        """Generate questions dynamically from the discovered schema.
        For each table and column, ask questions based on what we see.
        This is curiosity — not a fixed checklist.
        """
        for table_name, info in self.schema.items():
            cols = info["column_names"]
            count = info["row_count"]
            # ── Documentation questions ──
            if table_name == "_table_registry":
                self.add_question("DOCUMENTATION",
                    "Are all tables registered in _table_registry?",
                    "check_table_registry", {"tables": list(self.schema.keys())}, "high")
            if table_name == "_column_docs":
                self.add_question("DOCUMENTATION",
                    "Are all columns in all tables documented?",
                    "check_column_docs", {"tables": self.schema}, "high")
            if table_name == "_db_meta":
                self.add_question("DOCUMENTATION",
                    "Does _db_meta have essential keys (db_name, db_purpose, architecture)?",
                    "check_db_meta", {}, "high")
            # ── Empty table questions ──
            if count == 0 and not table_name.startswith("_"):
                self.add_question("EMPTY_TABLE",
                    f"Table '{table_name}' has 0 rows — is it supposed to be empty?",
                    "check_empty_table", {"table": table_name}, "medium")
            # ── Hierarchy questions ──
            if "parent_id" in cols:
                self.add_question("HIERARCHY",
                    f"Table '{table_name}' has parent_id — is the chain complete?",
                    "check_parent_chain", {"table": table_name}, "medium")
            # ── BCL identity questions ──
            if "bcl_token" in cols:
                self.add_question("BCL_IDENTITY",
                    f"Do all BCL tokens in '{table_name}' have the 7 required fields?",
                    "check_bcl_completeness", {"table": table_name}, "high")
                if table_name == "bcl_identity":
                    self.add_question("BCL_IDENTITY",
                        "Do all VBStyle classes have BCL tokens?",
                        "check_bcl_coverage", {}, "high")
                    self.add_question("BCL_IDENTITY",
                        "Do all VBStyle methods have BCL tokens?",
                        "check_bcl_method_coverage", {}, "medium")
            # ── Closure questions ──
            if "closure_pct" in cols:
                self.add_question("CLOSURE",
                    f"Are all entities in '{table_name}' fully closed (100%)?",
                    "check_closure", {"table": table_name}, "high")
            # ── Orchestration questions ──
            if "domain" in cols and table_name == "classes":
                self.add_question("ORCHESTRATION",
                    "Are all domains used in orchestration pipelines?",
                    "check_domain_orchestration", {}, "medium")
            # ── Structure questions ──
            if "method_name" in cols and table_name == "methods":
                self.add_question("STRUCTURE",
                    "Are there method pairs missing their opposite?",
                    "check_method_pairs", {}, "medium")
                self.add_question("STRUCTURE",
                    "Do all domains have CRUD operations?",
                    "check_crud_coverage", {}, "low")
            if table_name == "computational_units":
                self.add_question("STRUCTURE",
                    "Are there orphan CUs (no class link)?",
                    "check_cu_orphans", {}, "low")
            # ── Plan questions ──
            if table_name == "plans":
                self.add_question("PLANS",
                    "Are there enough plans for the number of domains?",
                    "check_plan_count", {}, "high")
            # ── Execution questions ──
            if table_name == "execution_log":
                self.add_question("EXECUTION",
                    "Has anything actually been executed?",
                    "check_execution", {}, "medium")
            # ── Violation questions ──
            if table_name == "violations":
                self.add_question("VIOLATIONS",
                    "What VBStyle violations exist?",
                    "check_violations", {}, "low")
            # ── Data quality questions (for every nullable column) ──
            skip_null_check = {"created_at", "updated_at", "description", "notes",
                              "key_columns", "example", "default", "parent_id",
                              "complexity_score", "performance_score", "domain",
                              "class_id", "method_id", "parent_plan_id",
                              "promoted_to_class_id", "source_file", "line_start"}
            for col in info["columns"]:
                if col["not_null"] == 0 and not col["is_pk"] and col["name"] not in skip_null_check:
                    if count > 10:
                        self.add_question("DATA_QUALITY",
                            f"Column '{col['name']}' in '{table_name}' — how many NULLs?",
                            "check_nulls",
                            {"table": table_name, "column": col["name"]}, "low")
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
    def __init__(self):
        self.mistakes = []
        self.mysql_conn = None
        try:
            self.mysql_conn = sqlite3.connect(":memory:")  # placeholder
            # Try MySQL connection
            import subprocess
            # We'll use subprocess to query MySQL since we might not have mysql connector
        except:
            pass
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
        investigators = {
            "check_table_registry": self.Check_table_registry,
            "check_column_docs": self.Check_column_docs,
            "check_db_meta": self.Check_db_meta,
            "check_empty_table": self.Check_empty_table,
            "check_parent_chain": self.Check_parent_chain,
            "check_bcl_completeness": self.Check_bcl_completeness,
            "check_bcl_coverage": self.Check_bcl_coverage,
            "check_bcl_method_coverage": self.Check_bcl_method_coverage,
            "check_closure": self.Check_closure,
            "check_domain_orchestration": self.Check_domain_orchestration,
            "check_method_pairs": self.Check_method_pairs,
            "check_crud_coverage": self.Check_crud_coverage,
            "check_cu_orphans": self.Check_cu_orphans,
            "check_plan_count": self.Check_plan_count,
            "check_execution": self.Check_execution,
            "check_violations": self.Check_violations,
            "check_nulls": self.Check_nulls,
        }
        for q in questions:
            method = investigators.get(q["investigator"])
            if method:
                method(q["params"])
            else:
                self.add_finding("ENGINE", "low", q["investigator"],
                                 f"No investigator for: {q['question']}", "")
        return (1, self.findings, None)
    def _check_table_registry(self, params):
        tables = params["tables"]
        self.c.execute("SELECT table_name FROM _table_registry")
        registered = set(r[0] for r in self.c.fetchall())
        for t in tables:
            if t not in registered:
                self.add_finding("DOCUMENTATION", "high", t,
                                 "Table not in _table_registry", "")
        return (1, None, None)
    def _check_column_docs(self, params):
        tables = params["tables"]
        for table_name, info in tables.items():
            self.c.execute("SELECT column_name FROM _column_docs WHERE table_name=?", (table_name,))
            documented = set(r[0] for r in self.c.fetchall())
            for col in info["column_names"]:
                if col not in documented:
                    self.add_finding("DOCUMENTATION", "medium", f"{table_name}.{col}",
                                     "Column not documented", "")
        return (1, None, None)
    def _check_db_meta(self, params):
        essential = ["db_name", "db_purpose", "architecture"]
        self.c.execute("SELECT key FROM _db_meta")
        existing = set(r[0] for r in self.c.fetchall())
        for key in essential:
            if key not in existing:
                self.add_finding("DOCUMENTATION", "high", f"_db_meta.{key}",
                                 f"Essential metadata '{key}' missing", "")
        return (1, None, None)
    def _check_empty_table(self, params):
        self.add_finding("EMPTY_TABLE", "medium", params["table"],
                         f"Table '{params['table']}' has 0 rows", "")
        return (1, None, None)
    def _check_parent_chain(self, params):
        if params["table"] == "bcl_identity":
            self.c.execute("SELECT entity_type, entity_name FROM bcl_identity WHERE entity_type IN ('class','method') AND parent_id IS NULL")
            for r in self.c.fetchall():
                self.add_finding("HIERARCHY", "medium", r[1],
                                 f"{r[0]} has no parent_id (orphan)", "")
        return (1, None, None)
    def _check_bcl_completeness(self, params):
        required = ["identity", "capabilities", "used_in_pipelines", "depends_on", "depended_by", "closure", "self_narrative"]
        self.c.execute(f"SELECT entity_name, bcl_token FROM {params['table']} WHERE entity_type='domain'")
        for r in self.c.fetchall():
            missing = [f for f in required if f not in r[1]]
            if missing:
                self.add_finding("BCL_IDENTITY", "medium", r[0],
                                 f"BCL token missing: {', '.join(missing)}", "")
        return (1, None, None)
    def _check_bcl_coverage(self, params):
        self.c.execute("SELECT id, class_name FROM classes WHERE is_vbstyle=1")
        vb = self.c.fetchall()
        self.c.execute("SELECT entity_id FROM bcl_identity WHERE entity_type='class'")
        bcl = set(r[0] for r in self.c.fetchall())
        for cid, name in vb:
            if cid not in bcl:
                self.add_finding("BCL_IDENTITY", "high", name,
                                 "VBStyle class has no BCL token", "")
        return (1, None, None)
    def _check_bcl_method_coverage(self, params):
        self.c.execute("SELECT m.id, m.method_name, cl.class_name FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'")
        vb = self.c.fetchall()
        self.c.execute("SELECT entity_id FROM bcl_identity WHERE entity_type='method'")
        bcl = set(r[0] for r in self.c.fetchall())
        for mid, mname, cname in missing[:20]:
            self.add_finding("BCL_IDENTITY", "medium", f"{cname}.{mname}",
                             "Method has no BCL token", "")
        return (1, None, None)
    def _check_closure(self, params):
        self.c.execute(f"SELECT domain, closure_pct, methods_missing, status FROM {params['table']} WHERE closure_pct < 100.0")
        for r in self.c.fetchall():
            self.add_finding("CLOSURE", "high", r[0],
                             f"Not fully closed ({r[1]}%) — missing {r[2]} methods", "")
        return (1, None, None)
    def _check_domain_orchestration(self, params):
        self.c.execute("SELECT DISTINCT cl.domain FROM classes cl WHERE cl.is_vbstyle=1 AND cl.id NOT IN (SELECT class_id FROM orchestration) ORDER BY cl.domain")
        for r in self.c.fetchall():
            self.add_finding("ORCHESTRATION", "medium", r[0],
                             "Domain not used in any pipeline", "")
        return (1, None, None)
    def _check_method_pairs(self, params):
        pairs = [("compress","decompress"),("encrypt","decrypt"),("sign","verify"),
                 ("serialize","deserialize"),("encode","decode"),("import","export"),
                 ("load","save"),("start","stop"),("open","close"),("add","remove"),
                 ("create","delete"),("push","pop"),("lock","unlock"),
                 ("connect","disconnect"),("register","unregister"),("subscribe","unsubscribe")]
        self.c.execute("SELECT DISTINCT m.method_name FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'")
        all_m = set(r[0] for r in self.c.fetchall())
        for a, b in pairs:
            ha, hb = a in all_m, b in all_m
            if ha and not hb:
                self.add_finding("STRUCTURE", "medium", f"{a}/{b}",
                                 f"Missing pair: {a}() exists but {b}() is missing", "")
            elif hb and not ha:
                self.add_finding("STRUCTURE", "medium", f"{a}/{b}",
                                 f"Missing pair: {b}() exists but {a}() is missing", "")
        return (1, None, None)
    def _check_crud_coverage(self, params):
        crud = {
            "create": ["create","add","insert","write","compress","generate","build","make"],
            "read": ["read","get","fetch","load","list","search","find","query"],
            "update": ["update","edit","modify","rename","patch","set","convert","transform"],
            "delete": ["delete","remove","drop","clear","purge","forget","strip","destroy"],
        }
        self.c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle=1 ORDER BY domain")
        for d in [r[0] for r in self.c.fetchall()]:
            self.c.execute("SELECT DISTINCT m.method_name FROM methods m JOIN classes cl ON m.class_id=cl.id WHERE cl.is_vbstyle=1 AND cl.domain=? AND m.method_name NOT LIKE '\\_%'", (d,))
            methods = set(r[0].lower() for r in self.c.fetchall())
            missing = [r for r in crud if not any(m in crud[r] for m in methods)]
            if missing:
                self.add_finding("STRUCTURE", "low", d,
                                 f"CRUD gap: missing {', '.join(missing)}", "")
        return (1, None, None)
    def _check_cu_orphans(self, params):
        self.c.execute("SELECT COUNT(*) FROM computational_units WHERE class_id IS NULL OR class_id = 0")
        count = self.c.fetchone()[0]
        if count > 0:
            self.add_finding("STRUCTURE", "low", "computational_units",
                             f"{count} orphan CUs (no class link)", "")
        self.c.execute("SELECT COUNT(*) FROM plans")
        plans = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM classes WHERE is_vbstyle=1")
        domains = self.c.fetchone()[0]
        if plans < 5:
            self.add_finding("PLANS", "high", "system",
                             f"Only {plans} plan(s) for {domains} domains", "")
        return (1, None, None)
    def _check_execution(self, params):
        self.c.execute("SELECT COUNT(*) FROM execution_log")
        count = self.c.fetchone()[0]
        if count == 0:
            self.add_finding("EXECUTION", "medium", "system",
                             "No execution log entries — nothing has run", "")
        return (1, None, None)
    def _check_violations(self, params):
        self.c.execute("SELECT kind, COUNT(*) FROM violations GROUP BY kind ORDER BY COUNT(*) DESC")
        for r in self.c.fetchall():
            self.add_finding("VIOLATIONS", "low", r[0],
                             f"{r[1]} violations of rule: {r[0]}", "")
        return (1, None, None)
    def _check_nulls(self, params):
        table, column = params["table"], params["column"]
        self.c.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
        nulls = self.c.fetchone()[0]
        self.c.execute(f"SELECT COUNT(*) FROM {table}")
        total = self.c.fetchone()[0]
        if total > 0 and nulls > 0:
            pct = (nulls / total) * 100
            if pct > 50:
                self.add_finding("DATA_QUALITY", "medium", f"{table}.{column}",
                                 f"{nulls}/{total} ({pct:.0f}%) NULL", "")
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
    def __init__(self):
        self.mistakes = []
        self.mysql_conn = None
        try:
            self.mysql_conn = sqlite3.connect(":memory:")  # placeholder
            # Try MySQL connection
            import subprocess
            # We'll use subprocess to query MySQL since we might not have mysql connector
        except:
            pass
    def check(self, findings):
        """Check each finding against known rules."""
        for finding in findings:
            cat = finding["category"]
            rules_that_apply = []
            if cat == "VBSTYLE" or cat == "VIOLATIONS":
                for rule_id, rule_text in self.VBSTYLE_RULES.items():
                    rules_that_apply.append(("VBSTYLE", rule_id, rule_text))
            if cat == "BCL_IDENTITY":
                for rule_id, rule_text in self.BCL_RULES.items():
                    rules_that_apply.append(("BCL", rule_id, rule_text))
            if cat == "DOCUMENTATION":
                for rule_id, rule_text in self.DOC_RULES.items():
                    rules_that_apply.append(("DOC", rule_id, rule_text))
            if cat == "CLOSURE":
                rules_that_apply.append(("CLOSURE", "must_be_100", "Every domain must be at 100% closure"))
            if cat == "ORCHESTRATION":
                rules_that_apply.append(("ORCH", "should_be_used", "Every domain should be used in at least one pipeline"))
            if rules_that_apply:
                finding["constraints"] = rules_that_apply
                for rule_type, rule_id, rule_text in rules_that_apply:
                    self.constraints.append({
                        "finding": finding["entity"],
                        "rule_type": rule_type,
                        "rule_id": rule_id,
                        "rule_text": rule_text,
                    })
        return (1, self.constraints, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def suggest(self, findings):
        """Add solution suggestions to each finding."""
        for finding in findings:
            issue = finding["issue"]
            solution = "No automatic solution available"
            for pattern, fix in self.SOLUTIONS.items():
                if pattern in issue:
                    solution = fix
                    break
            finding["suggested_solution"] = solution
        return (1, findings, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def __init__(self):
        self.mistakes = []
        self.mysql_conn = None
        try:
            self.mysql_conn = sqlite3.connect(":memory:")  # placeholder
            # Try MySQL connection
            import subprocess
            # We'll use subprocess to query MySQL since we might not have mysql connector
        except:
            pass
    def check_mistakes(self, findings):
        """For each finding, search learned_rules for related past mistakes."""
        try:
            import subprocess
            for finding in findings:
                # Search learned_rules for patterns matching this finding
                keyword = finding["entity"]
                if len(keyword) < 3:
                    continue
                result = subprocess.run(
                    ["mysql", "-u", "root", "vb_shared", "-e",
                     f"SELECT pattern, fix_action, confidence, success_count FROM learned_rules WHERE pattern LIKE '%{keyword}%' LIMIT 3"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout and result.stdout.strip():
                    finding["past_mistakes"] = result.stdout.strip()
        except:
            pass  # MySQL not available is OK
        return (1, findings, None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def text_report(findings, questions, constraints):
        lines = []
        lines.append("=" * 70)
        lines.append("GRAPH ENGINE v2 — COGNITIVE LOOP REPORT")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("=" * 70)
        lines.append(f"\nCognitive Loop:")
        lines.append(f"  Problem → Question → Answer → Constraint → Solution → Verify")
        lines.append(f"\n  Questions generated: {len(questions)}")
        lines.append(f"  Answers (findings):  {len(findings)}")
        lines.append(f"  Constraints applied: {len(constraints)}")
        # Questions
        lines.append(f"\n── QUESTIONS (curiosity) ──")
        by_cat = defaultdict(list)
        for q in questions:
            by_cat[q["category"]].append(q["question"])
        for cat in sorted(by_cat.keys()):
            lines.append(f"\n  [{cat}] ({len(by_cat[cat])} questions)")
            for q in by_cat[cat]:
                lines.append(f"    • {q}")
        # Findings summary
        lines.append(f"\n── FINDINGS (answers) ──")
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
                lines.append(f"  ⚠️  {cat:15}: {count} gaps ({high}H {med}M {low}L)")
        # Findings detail with constraints and solutions
        for cat in sorted(by_category.keys()):
            items = by_category[cat]
            if not items:
                continue
            lines.append(f"\n── {cat} ({len(items)} findings) ──")
            for f in items[:25]:
                lines.append(f"  [{f['severity']:6}] {f['entity']:35}: {f['issue']}")
                if f.get("constraints"):
                    for ct, cid, ctext in f["constraints"][:2]:
                        lines.append(f"           constraint: [{ct}] {ctext}")
                if f.get("suggested_solution"):
                    lines.append(f"           solution:   {f['suggested_solution']}")
                if f.get("past_mistakes"):
                    lines.append(f"           past:       {f['past_mistakes'][:100]}")
            if len(items) > 25:
                lines.append(f"  ... and {len(items) - 25} more")
        lines.append("\n" + "=" * 70)
        lines.append("COGNITIVE LOOP COMPLETE")
        lines.append("=" * 70)
        return (1, "\n".join(lines), None)
    def json_report(findings, questions, constraints):
        return (1, json.dumps({
            "generated": datetime.now().isoformat(),
            "loop": "Problem → Question → Answer → Constraint → Solution → Verify",
            "questions": len(questions),
            "findings": len(findings),
            "constraints": len(constraints),
            "questions_detail": questions,
            "findings_detail": findings,
            "constraints_detail": constraints,
        }, indent=2, default=str), None)
    def Run(self, command, params=None):
        dispatch = {
            'read_state': self.read_state,
            'set_config': self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params or {})
        return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))
    def show(findings, questions, constraints):
        try:
            import math
            import tkinter as tk
        except ImportError:
            pass
            return (1, None, None)
        by_category = defaultdict(list)
        for f in findings:
            by_category[f["category"]].append(f)
        root = tk.Tk()
        root.title("Graph Engine v2 — Cognitive Loop")
        root.geometry("1500x950")
        root.configure(bg="#1e1e2e")
        # ── Title ──
        tk.Label(root, text="Graph Engine v2 — Cognitive Loop",
                fg="#cdd6f4", bg="#1e1e2e", font=("Helvetica", 16, "bold")).pack(pady=5)
        tk.Label(root, text=f"Problem → Question → Answer → Constraint → Solution → Verify",
                fg="#89b4fa", bg="#1e1e2e", font=("Helvetica", 10)).pack()
        tk.Label(root, text=f"{len(questions)} questions → {len(findings)} findings → {len(constraints)} constraints",
                fg="#a6e3a1", bg="#1e1e2e", font=("Helvetica", 10, "bold")).pack(pady=5)
        # ── Main body: 3 panels ──
        body = tk.Frame(root, bg="#1e1e2e")
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Left: Questions
        left = tk.Frame(body, bg="#1e1e2e", width=400)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left.pack_propagate(False)
        tk.Label(left, text="QUESTIONS (Curiosity)", fg="#89b4fa", bg="#1e1e2e",
                font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        q_text = tk.Text(left, bg="#181825", fg="#cdd6f4", font=("Helvetica", 9), wrap=tk.WORD)
        q_text.pack(fill=tk.BOTH, expand=True)
        q_by_cat = defaultdict(list)
        for q in questions:
            q_by_cat[q["category"]].append(q["question"])
        for cat in sorted(q_by_cat.keys()):
            q_text.insert(tk.END, f"\n[{cat}] ({len(q_by_cat[cat])})\n", "cat")
            for q in q_by_cat[cat]:
                q_text.insert(tk.END, f"  • {q}\n")
        q_text.tag_config("cat", foreground="#89b4fa", font=("Helvetica", 9, "bold"))
        q_text.config(state=tk.DISABLED)
        # Center: Graph
        center = tk.Frame(body, bg="#1e1e2e")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(center, text="GRAPH (Findings by Category)", fg="#cba6f7", bg="#1e1e2e",
                font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        canvas = tk.Canvas(center, bg="#181825", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        # Draw cognitive loop in center
        cx, cy = 350, 300
        loop_steps = ["Problem", "Question", "Answer", "Constraint", "Solution", "Verify"]
        loop_colors = ["#f38ba8", "#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#94e2d5"]
        for i, (step, color) in enumerate(zip(loop_steps, loop_colors)):
            angle = (2 * math.pi * i) / len(loop_steps) - math.pi / 2
            x = cx + 80 * math.cos(angle)
            y = cy + 80 * math.sin(angle)
            canvas.create_oval(x - 30, y - 15, x + 30, y + 15,
                             fill=color, outline="#1e1e2e", width=2)
            canvas.create_text(x, y, text=step, fill="#1e1e2e",
                             font=("Helvetica", 8, "bold"))
            # Arrow to next
            next_i = (i + 1) % len(loop_steps)
            next_angle = (2 * math.pi * next_i) / len(loop_steps) - math.pi / 2
            nx = cx + 80 * math.cos(next_angle)
            ny = cy + 80 * math.sin(next_angle)
            canvas.create_line(x, y, nx, ny, fill="#585b70", width=2, arrow=tk.LAST)
        # Draw category nodes around the loop
        categories = list(by_category.keys())
        for i, cat in enumerate(categories):
            angle = (2 * math.pi * i) / max(len(categories), 1)
            x = cx + 200 * math.cos(angle)
            y = cy + 200 * math.sin(angle)
            count = len(by_category[cat])
            high = sum(1 for f in by_category[cat] if f["severity"] == "high")
            if high > 0:
                color = "#f38ba8"
            elif count > 0:
                color = "#f9e2af"
            else:
                color = "#a6e3a1"
            canvas.create_oval(x - 50, y - 20, x + 50, y + 20,
                             fill=color, outline="#1e1e2e", width=2)
            canvas.create_text(x, y, text=f"{cat}\n{count} gaps",
                             fill="#1e1e2e", font=("Helvetica", 8, "bold"))
            # Line from center to category
            canvas.create_line(cx, cy, x, y, fill="#585b70", width=1, dash=(3, 3))
        # Right: Findings with solutions
        right = tk.Frame(body, bg="#1e1e2e", width=500)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right.pack_propagate(False)
        tk.Label(right, text="FINDINGS + SOLUTIONS", fg="#f38ba8", bg="#1e1e2e",
                font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
        f_text = tk.Text(right, bg="#181825", fg="#cdd6f4", font=("Helvetica", 9), wrap=tk.WORD)
        f_text.pack(fill=tk.BOTH, expand=True)
        SEV_COLORS = {"high": "#f38ba8", "medium": "#f9e2af", "low": "#a6e3a1"}
        for sev in ["high", "medium", "low"]:
            f_text.tag_config(sev, foreground=SEV_COLORS[sev])
        f_text.tag_config("solution", foreground="#a6e3a1", font=("Helvetica", 8, "italic"))
        f_text.tag_config("constraint", foreground="#f9e2af", font=("Helvetica", 8, "italic"))
        f_text.tag_config("cat", foreground="#cba6f7", font=("Helvetica", 9, "bold"))
        for cat in sorted(by_category.keys()):
            items = by_category[cat]
            f_text.insert(tk.END, f"\n[{cat}] ({len(items)})\n", "cat")
            for f in items[:15]:
                f_text.insert(tk.END, f"  [{f['severity']:6}] {f['entity']:30}: {f['issue']}\n", f["severity"])
                if f.get("suggested_solution"):
                    f_text.insert(tk.END, f"    → {f['suggested_solution'][:80]}\n", "solution")
                if f.get("constraints"):
                    for ct, cid, ctext in f["constraints"][:1]:
                        f_text.insert(tk.END, f"    ⚖ {ctext[:70]}\n", "constraint")
            if len(items) > 15:
                f_text.insert(tk.END, f"  ... and {len(items) - 15} more\n")
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
    pass
    # Step 1: PROBLEM — discover schema
    controller = CuriosityController(conn)
    schema = controller.discover_schema()
    # Step 2: QUESTION — generate questions
    questions = controller.generate_questions()
    # Step 3: ANSWER — investigate
    engine = GraphEngine(conn)
    findings = engine.investigate(questions)
    # Step 4: CONSTRAINT — check against rules
    checker = ConstraintChecker(conn)
    constraints = checker.check(findings)
    # Step 5: SOLUTION — suggest fixes
    suggester = SolutionSuggester()
    findings = suggester.suggest(findings)
    solutions = sum(1 for f in findings if f.get("suggested_solution"))
    # Step 6: MISTAKE — check past mistakes
    recorder = MistakeRecorder()
    findings = recorder.check_mistakes(findings)
    mistakes = sum(1 for f in findings if f.get("past_mistakes"))
    # Step 7: VERIFY + REPORT
    if "--json" in sys.argv:
        pass
    elif "--gui" in sys.argv:
        Guidisplayer.show(findings, questions, constraints)
    else:
        pass
    conn.close()
if __name__ == "__main__":
    main()

