#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/question_store.py" date="2026-08-18" author="Devin" session_id="question-store" context="SQLite-backed question-answer store — subagents ask, answers saved, code groups and queries"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="question_store.py" domain="utility" authority="QuestionStore"}
#[@SUMMARY]{summary="Persistent Q&A store for problem-space collapse — subagents ask questions, answers saved to SQLite, code queries grouped answers"}
#[@CLASS]{class="QuestionStore" domain="utility" authority="single"}
#[@METHOD]{methods="Run,Ask,Answer,Group,Facts,Unknowns,Collapse,Report,Constraint,Solution,Mistake,Verify,CognitiveLoop,init_db"}

"""
QuestionStore — persistent question-answer store for problem-space collapse.

Implements the CognitiveLoop pattern from Dom_Graph_EngineV2.py:
    Problem → Question → Answer → Constraint → Solution → Verify → Loop

Subagents call Ask() to register a question.
Subagents call Answer() to register an answer (YES/NO/UNKNOWN + evidence).
Main code calls Constraint() to check answers against rules (VBStyle, BCL, governance).
Main code calls Solution() to suggest fixes for each finding.
Main code calls Mistake() to search MySQL learned_rules for past mistakes.
Main code calls Verify() to check if a solution actually worked.
Main code calls CognitiveLoop() to run the full loop automatically.
Main code calls Group() to get all Q&A for a problem.
Main code calls Facts() to get confirmed facts only.
Main code calls Collapse() to check if a problem is collapsed.

Schema:
    problems(id, name, status, created_at, collapsed_at)
    questions(id, problem_id, category, question, parent_id, depth, created_at)
    answers(id, question_id, answer, evidence, source, created_at)
    constraints(id, question_id, rule_type, rule_id, rule_text, created_at)
    solutions(id, question_id, suggested_solution, source, created_at)
    mistakes(id, question_id, pattern, fix_action, confidence, created_at)
    verifications(id, question_id, verified, result, created_at)
"""

import sqlite3
import json
import time
from datetime import datetime

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/utility/question_store.db"

CATEGORIES = [
    "existence", "time", "versions", "location", "dependencies",
    "authorship", "chat_history", "database_state", "errors", "patterns",
    "environment", "naming", "state", "relationships", "assumptions",
    "followup_yes", "followup_no", "meta"
]

ANSWER_YES = "YES"
ANSWER_NO = "NO"
ANSWER_UNKNOWN = "UNKNOWN"
ANSWER_ACTION = "ACTION"

STATUS_OPEN = "open"
STATUS_GOOD_ENOUGH = "good_enough"
STATUS_COLLAPSED = "collapsed"


class QuestionStore:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": DB_PATH},
            "results": None,
            "error": None
        }
        self.conn = None
        self.init_db()

    def init_db(self):
        path = self.state["config"]["db_path"]
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TEXT,
            collapsed_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            category TEXT,
            question TEXT NOT NULL,
            parent_id INTEGER,
            depth INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (problem_id) REFERENCES problems(id),
            FOREIGN KEY (parent_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            evidence TEXT,
            source TEXT,
            created_at TEXT,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            rule_type TEXT,
            rule_id TEXT,
            rule_text TEXT,
            created_at TEXT,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            suggested_solution TEXT,
            source TEXT,
            created_at TEXT,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            pattern TEXT,
            fix_action TEXT,
            confidence REAL,
            created_at TEXT,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            verified INTEGER DEFAULT 0,
            result TEXT,
            created_at TEXT,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_q_problem ON questions(problem_id)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_q_category ON questions(category)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_a_question ON answers(question_id)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_c_question ON constraints(question_id)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_s_question ON solutions(question_id)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_m_question ON mistakes(question_id)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_v_question ON verifications(question_id)""")
        self.conn.commit()

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _now(self):
        return datetime.now().isoformat()

    def Run(self, command, params=None):
        if command == "register_problem":
            return self._register_problem(params)
        elif command == "ask":
            return self._ask(params)
        elif command == "answer":
            return self._answer(params)
        elif command == "group":
            return self._group(params)
        elif command == "facts":
            return self._facts(params)
        elif command == "unknowns":
            return self._unknowns(params)
        elif command == "collapse_check":
            return self._collapse_check(params)
        elif command == "report":
            return self._report(params)
        elif command == "list_problems":
            return self._list_problems(params)
        elif command == "stats":
            return self._stats(params)
        elif command == "reset":
            return self._reset(params)
        elif command == "constraint":
            return self._constraint(params)
        elif command == "solution":
            return self._solution(params)
        elif command == "mistake":
            return self._mistake(params)
        elif command == "verify":
            return self._verify(params)
        elif command == "cognitive_loop":
            return self._cognitive_loop(params)
        elif command == "full_report":
            return self._full_report(params)
        else:
            return (0, None, (1, f"unknown_command:{command}", 0))

    def _register_problem(self, params):
        name = self._p(params, "name")
        if not name:
            return (0, None, (2, "missing name", 0))
        c = self.conn.cursor()
        c.execute("SELECT id FROM problems WHERE name=?", (name,))
        row = c.fetchone()
        if row:
            return (1, {"problem_id": row["id"], "exists": True}, None)
        c.execute("INSERT INTO problems (name, status, created_at) VALUES (?,?,?)",
                  (name, STATUS_OPEN, self._now()))
        self.conn.commit()
        pid = c.lastrowid
        return (1, {"problem_id": pid, "exists": False}, None)

    def _ask(self, params):
        problem_id = self._p(params, "problem_id")
        question = self._p(params, "question")
        category = self._p(params, "category", "unknown")
        parent_id = self._p(params, "parent_id")
        depth = self._p(params, "depth", 0)
        if not problem_id or not question:
            return (0, None, (2, "missing problem_id or question", 0))
        c = self.conn.cursor()
        c.execute("""INSERT INTO questions (problem_id, category, question, parent_id, depth, created_at)
                     VALUES (?,?,?,?,?,?)""",
                  (problem_id, category, question, parent_id, depth, self._now()))
        self.conn.commit()
        qid = c.lastrowid
        return (1, {"question_id": qid}, None)

    def _answer(self, params):
        question_id = self._p(params, "question_id")
        answer = self._p(params, "answer")
        evidence = self._p(params, "evidence", "")
        source = self._p(params, "source", "")
        if not question_id or not answer:
            return (0, None, (2, "missing question_id or answer", 0))
        if answer not in (ANSWER_YES, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_ACTION):
            return (0, None, (3, f"invalid_answer:{answer}", 0))
        c = self.conn.cursor()
        c.execute("""INSERT INTO answers (question_id, answer, evidence, source, created_at)
                     VALUES (?,?,?,?,?)""",
                  (question_id, answer, evidence, source, self._now()))
        self.conn.commit()
        aid = c.lastrowid
        return (1, {"answer_id": aid}, None)

    def _group(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        c.execute("""SELECT q.id, q.category, q.question, q.depth, q.parent_id,
                            a.answer, a.evidence, a.source, a.created_at
                     FROM questions q
                     LEFT JOIN answers a ON q.id = a.question_id
                     WHERE q.problem_id = ?
                     ORDER BY q.depth, q.category, q.id""",
                  (problem_id,))
        rows = c.fetchall()
        grouped = {}
        for r in rows:
            cat = r["category"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append({
                "question_id": r["id"],
                "question": r["question"],
                "depth": r["depth"],
                "parent_id": r["parent_id"],
                "answer": r["answer"],
                "evidence": r["evidence"],
                "source": r["source"]
            })
        return (1, {"problem_id": problem_id, "grouped": grouped, "total": len(rows)}, None)

    def _facts(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        c.execute("""SELECT q.id, q.category, q.question, q.depth,
                            a.answer, a.evidence, a.source
                     FROM questions q
                     JOIN answers a ON q.id = a.question_id
                     WHERE q.problem_id = ? AND a.answer IN ('YES','NO')
                     ORDER BY q.depth, q.category""",
                  (problem_id,))
        rows = c.fetchall()
        facts = []
        for r in rows:
            facts.append({
                "question_id": r["id"],
                "category": r["category"],
                "question": r["question"],
                "depth": r["depth"],
                "answer": r["answer"],
                "evidence": r["evidence"],
                "source": r["source"]
            })
        return (1, {"problem_id": problem_id, "facts": facts, "count": len(facts)}, None)

    def _unknowns(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        c.execute("""SELECT q.id, q.category, q.question, q.depth
                     FROM questions q
                     LEFT JOIN answers a ON q.id = a.question_id
                     WHERE q.problem_id = ? AND (a.answer IS NULL OR a.answer = 'UNKNOWN')
                     ORDER BY q.depth, q.category""",
                  (problem_id,))
        rows = c.fetchall()
        unknowns = []
        for r in rows:
            unknowns.append({
                "question_id": r["id"],
                "category": r["category"],
                "question": r["question"],
                "depth": r["depth"]
            })
        return (1, {"problem_id": problem_id, "unknowns": unknowns, "count": len(unknowns)}, None)

    def _collapse_check(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, facts_data, err = self._facts(params)
        ok2, unknowns_data, err2 = self._unknowns(params)
        ok3, group_data, err3 = self._group(params)

        fact_count = facts_data["count"] if facts_data else 0
        unknown_count = unknowns_data["count"] if unknowns_data else 0
        total = group_data["total"] if group_data else 0

        if total == 0:
            status = "empty"
        elif unknown_count == 0:
            status = STATUS_COLLAPSED
            c = self.conn.cursor()
            c.execute("UPDATE problems SET status=?, collapsed_at=? WHERE id=?",
                      (STATUS_COLLAPSED, self._now(), problem_id))
            self.conn.commit()
        elif fact_count >= 10 and unknown_count <= 2:
            status = STATUS_GOOD_ENOUGH
            c = self.conn.cursor()
            c.execute("UPDATE problems SET status=? WHERE id=?",
                      (STATUS_GOOD_ENOUGH, problem_id))
            self.conn.commit()
        else:
            status = STATUS_OPEN

        return (1, {
            "problem_id": problem_id,
            "status": status,
            "total_questions": total,
            "facts": fact_count,
            "unknowns": unknown_count,
            "collapsed": status == STATUS_COLLAPSED
        }, None)

    def _report(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, group_data, err = self._group(params)
        ok2, collapse_data, err2 = self._collapse_check(params)

        lines = []
        lines.append(f"# Problem Space Report (id={problem_id})")
        lines.append(f"Status: {collapse_data['status']}")
        lines.append(f"Total questions: {collapse_data['total_questions']}")
        lines.append(f"Facts confirmed: {collapse_data['facts']}")
        lines.append(f"Unknowns remaining: {collapse_data['unknowns']}")
        lines.append("")
        for cat, items in group_data["grouped"].items():
            lines.append(f"## {cat} ({len(items)} questions)")
            for item in items:
                ans = item["answer"] or "UNANSWERED"
                ev = item["evidence"] or ""
                marker = {"YES": "[Y]", "NO": "[N]", "UNKNOWN": "[?]",
                          "ACTION": "[A]", None: "[ ]"}.get(ans, "[?]")
                lines.append(f"  {marker} (d{item['depth']}) {item['question']}")
                if ev:
                    lines.append(f"       evidence: {ev[:120]}")
            lines.append("")
        report = "\n".join(lines)
        return (1, {"report": report, "collapse": collapse_data}, None)

    def _list_problems(self, params):
        c = self.conn.cursor()
        c.execute("SELECT id, name, status, created_at, collapsed_at FROM problems ORDER BY id")
        rows = c.fetchall()
        problems = []
        for r in rows:
            problems.append({
                "id": r["id"], "name": r["name"], "status": r["status"],
                "created_at": r["created_at"], "collapsed_at": r["collapsed_at"]
            })
        return (1, {"problems": problems, "count": len(problems)}, None)

    def _stats(self, params):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) as n FROM problems")
        problems = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM questions")
        questions = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM answers")
        answers = c.fetchone()["n"]
        c.execute("SELECT answer, COUNT(*) as n FROM answers GROUP BY answer")
        by_answer = {r["answer"]: r["n"] for r in c.fetchall()}
        c.execute("SELECT category, COUNT(*) as n FROM questions GROUP BY category ORDER BY n DESC")
        by_category = {r["category"]: r["n"] for r in c.fetchall()}
        c.execute("SELECT status, COUNT(*) as n FROM problems GROUP BY status")
        by_status = {r["status"]: r["n"] for r in c.fetchall()}
        return (1, {
            "problems": problems, "questions": questions, "answers": answers,
            "by_answer": by_answer, "by_category": by_category, "by_status": by_status
        }, None)

    def _reset(self, params):
        c = self.conn.cursor()
        c.execute("DELETE FROM answers")
        c.execute("DELETE FROM questions")
        c.execute("DELETE FROM problems")
        c.execute("DELETE FROM constraints")
        c.execute("DELETE FROM solutions")
        c.execute("DELETE FROM mistakes")
        c.execute("DELETE FROM verifications")
        self.conn.commit()
        return (1, {"reset": True}, None)

    # ════════════════════════════════════════════════════════════════
    # COGNITIVE LOOP — Constraint → Solution → Mistake → Verify
    # Pattern from Dom_Graph_EngineV2.py
    # Problem → Question → Answer → CONSTRAINT → SOLUTION → VERIFY → Loop
    # ════════════════════════════════════════════════════════════════

    def _constraint(self, params):
        """Check answers against rules (VBStyle, BCL, governance, learned_rules).
        For each answered question, find applicable rules and store them."""
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        # Get all answered questions for this problem
        c.execute("""SELECT q.id, q.category, q.question, a.answer, a.evidence
                     FROM questions q
                     JOIN answers a ON q.id = a.question_id
                     WHERE q.problem_id = ? AND a.answer IN ('YES','NO')""",
                  (problem_id,))
        rows = c.fetchall()
        constraints_added = 0
        for r in rows:
            qid = r["id"]
            cat = r["category"] or ""
            qtext = r["question"]
            ans = r["answer"]
            # Map category to rule types (from EngineV2 pattern)
            rules = []
            if "vbsty" in cat.lower() or "compliance" in cat.lower():
                rules.append(("VBSTYLE", "one_class_per_file", "One class per file, no monoliths"))
                rules.append(("VBSTYLE", "no_print", "No print statements, use Report"))
                rules.append(("VBSTYLE", "no_hardcode", "No hardcoded values"))
                rules.append(("VBSTYLE", "pascal_case", "PascalCase class names, no underscores"))
                rules.append(("VBSTYLE", "tuple3", "All methods return Tuple3"))
                rules.append(("VBSTYLE", "run_dispatch", "Run() dispatch required"))
                rules.append(("VBSTYLE", "state_dict", "self.state dict, no self._"))
            if "bcl" in cat.lower() or "identity" in cat.lower():
                rules.append(("BCL", "ghost_header", "All files must have #[@GHOST] header"))
                rules.append(("BCL", "vbstyle_header", "All files must have #[@VBSTYLE] header"))
                rules.append(("BCL", "fileid_header", "All files must have #[@FILEID] header"))
            if "doc" in cat.lower() or "documented" in cat.lower():
                rules.append(("DOC", "summary_header", "All files must have #[@SUMMARY] header"))
                rules.append(("DOC", "class_header", "All classes must have #[@CLASS] header"))
                rules.append(("DOC", "method_header", "All methods must have #[@METHOD] header"))
            if "closure" in cat.lower():
                rules.append(("CLOSURE", "must_be_100", "Every domain must be at 100% closure"))
            if "orchestrat" in cat.lower():
                rules.append(("ORCH", "should_be_used", "Every domain should be used in at least one pipeline"))
            if "risk" in cat.lower():
                rules.append(("RISK", "assess_failure", "Every change must assess failure mode"))
                rules.append(("RISK", "recoverability", "Every change must have recovery plan"))
            if "causal" in cat.lower():
                rules.append(("CAUSAL", "root_cause", "Every problem must trace to root cause"))
            if "evidence" in cat.lower():
                rules.append(("EVIDENCE", "verifiable", "Every claim must be independently verifiable"))
            if "intent" in cat.lower():
                rules.append(("INTENT", "purpose_defined", "Every action must have stated purpose"))
            # Store constraints
            for rule_type, rule_id, rule_text in rules:
                c.execute("""INSERT INTO constraints (question_id, rule_type, rule_id, rule_text, created_at)
                             VALUES (?,?,?,?,?)""",
                          (qid, rule_type, rule_id, rule_text, self._now()))
                constraints_added += 1
        self.conn.commit()
        return (1, {
            "problem_id": problem_id,
            "questions_checked": len(rows),
            "constraints_added": constraints_added
        }, None)

    def _solution(self, params):
        """Suggest solutions for each answered question based on pattern matching.
        Pattern from EngineV2 SolutionSuggester."""
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        # Solution patterns (from EngineV2 + extended)
        SOLUTIONS = {
            "monolith": "Split into one-class-per-file modules with Config.py for shared constants",
            "print": "Replace print() with Report class or logging via Run() dispatch",
            "hardcoded": "Move hardcoded values to Config.py as UPPERCASE constants",
            "self._": "Replace self._ with self.state dict entries",
            "underscore": "Rename to PascalCase (no underscores in class names)",
            "no Run": "Add Run(self, command, params=None) dispatch method",
            "no Tuple3": "Change return to (1, data, None) or (0, None, (code, desc, 0))",
            "no header": "Add #[@GHOST], #[@VBSTYLE], #[@FILEID], #[@SUMMARY] headers",
            "no GHOST": "Add #[@GHOST] header with file_path, date, author, session_id, context",
            "no VBSTYLE": "Add #[@VBSTYLE] header with standard, version, rules",
            "no FILEID": "Add #[@FILEID] header with id, domain, authority",
            "decorator": "Remove @property/@staticmethod/@classmethod, use explicit methods",
            "enum": "Replace enum with UPPERCASE constants at class level",
            "tab": "Replace tabs with spaces",
            "trailing": "Remove trailing whitespace",
            "sqlite": "Consider using DomSystem.Run('query', sql) for DB access",
            "mysql": "Use cascade_cli.py for MySQL queries to auto-check learned_rules",
            "no test": "Write a test that verifies the behavior before refactoring",
            "no doc": "Add #[@SUMMARY] and #[@METHOD] headers to document purpose",
            "broken": "Fix the bug before refactoring — preserve behavior first",
            "stale": "Check if the file is still used before refactoring",
            "circular": "Move shared dependency to Config.py or a new shared module",
            "performance": "Move DB queries off the UI thread to prevent freeze",
            "risk": "Add try/except with ErrorHandler.Run('consume', ...) around risky operations",
            "unknown": "Run automated checks to convert UNKNOWN to YES or NO",
        }
        # Get all answered questions
        c.execute("""SELECT q.id, q.question, a.answer, a.evidence
                     FROM questions q
                     JOIN answers a ON q.id = a.question_id
                     WHERE q.problem_id = ?""",
                  (problem_id,))
        rows = c.fetchall()
        solutions_added = 0
        for r in rows:
            qid = r["id"]
            qtext = r["question"].lower()
            ans = r["answer"]
            evidence = (r["evidence"] or "").lower()
            # Find matching solution
            solution = "No automatic solution — requires manual investigation"
            for pattern, fix in SOLUTIONS.items():
                if pattern in qtext or pattern in evidence:
                    solution = fix
                    break
            # If answer is NO, the question found a gap — suggest a fix
            if ans == "NO":
                for pattern, fix in SOLUTIONS.items():
                    if pattern in qtext or pattern in evidence:
                        solution = fix
                        break
            # If answer is UNKNOWN, suggest verification
            if ans == "UNKNOWN":
                solution = "Run automated check to verify — convert UNKNOWN to YES or NO"
            c.execute("""INSERT INTO solutions (question_id, suggested_solution, source, created_at)
                         VALUES (?,?,?,?)""",
                      (qid, solution, "pattern_match", self._now()))
            solutions_added += 1
        self.conn.commit()
        return (1, {
            "problem_id": problem_id,
            "questions_processed": len(rows),
            "solutions_added": solutions_added
        }, None)

    def _mistake(self, params):
        """Search MySQL learned_rules for past mistakes related to each question.
        Pattern from EngineV2 MistakeRecorder."""
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        # Get all questions for this problem
        c.execute("""SELECT q.id, q.category, q.question
                     FROM questions q
                     WHERE q.problem_id = ?""",
                  (problem_id,))
        rows = c.fetchall()
        mistakes_added = 0
        import subprocess
        for r in rows:
            qid = r["id"]
            qtext = r["question"]
            # Extract keyword from question (skip common words)
            words = qtext.replace("?", "").replace(".", "").split()
            skip = {"does", "is", "the", "a", "an", "what", "where", "when", "how",
                    "who", "why", "was", "were", "are", "will", "can", "could",
                    "should", "would", "do", "did", "has", "have", "had",
                    "in", "on", "at", "to", "for", "of", "with", "by",
                    "and", "or", "not", "no", "yes", "it", "this", "that",
                    "from", "as", "be", "been", "being", "if", "then"}
            keywords = [w for w in words if len(w) > 3 and w.lower() not in skip]
            # Try top 2 keywords
            for kw in keywords[:2]:
                try:
                    result = subprocess.run(
                        ["mysql", "-u", "root", "vb_shared", "-e",
                         f"SELECT pattern, fix_action, confidence FROM learned_rules WHERE pattern LIKE '%{kw}%' LIMIT 3"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout and result.stdout.strip():
                        lines = result.stdout.strip().split("\n")
                        for line in lines[1:]:  # skip header
                            parts = line.split("\t")
                            if len(parts) >= 3:
                                pattern = parts[0]
                                fix = parts[1] if len(parts) > 1 else ""
                                conf = 0.0
                                try:
                                    conf = float(parts[2]) if len(parts) > 2 else 0.0
                                except ValueError:
                                    pass
                                c.execute("""INSERT INTO mistakes (question_id, pattern, fix_action, confidence, created_at)
                                             VALUES (?,?,?,?,?)""",
                                          (qid, pattern, fix, conf, self._now()))
                                mistakes_added += 1
                except Exception:
                    pass
        self.conn.commit()
        return (1, {
            "problem_id": problem_id,
            "questions_checked": len(rows),
            "mistakes_found": mistakes_added
        }, None)

    def _verify(self, params):
        """Mark a question as verified or not.
        After a solution is applied, verify checks if it worked."""
        question_id = self._p(params, "question_id")
        verified = self._p(params, "verified", 0)
        result = self._p(params, "result", "")
        if not question_id:
            return (0, None, (2, "missing question_id", 0))
        c = self.conn.cursor()
        c.execute("""INSERT INTO verifications (question_id, verified, result, created_at)
                     VALUES (?,?,?,?)""",
                  (question_id, 1 if verified else 0, result, self._now()))
        self.conn.commit()
        return (1, {"question_id": question_id, "verified": bool(verified)}, None)

    def _cognitive_loop(self, params):
        """Run the full CognitiveLoop: Constraint → Solution → Mistake.
        Pattern from Dom_Graph_EngineV2.py main().
        Problem → Question → Answer → Constraint → Solution → Mistake → Verify
        """
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        # Step 1: CONSTRAINT — check answers against rules
        ok1, constraint_data, err1 = self._constraint({"problem_id": problem_id})
        # Step 2: SOLUTION — suggest fixes
        ok2, solution_data, err2 = self._solution({"problem_id": problem_id})
        # Step 3: MISTAKE — search learned_rules
        ok3, mistake_data, err3 = self._mistake({"problem_id": problem_id})
        # Step 4: COLLAPSE — check status
        ok4, collapse_data, err4 = self._collapse_check({"problem_id": problem_id})
        return (1, {
            "problem_id": problem_id,
            "loop": "Problem → Question → Answer → Constraint → Solution → Mistake → Verify",
            "constraint": constraint_data if ok1 else None,
            "solution": solution_data if ok2 else None,
            "mistake": mistake_data if ok3 else None,
            "collapse": collapse_data if ok4 else None,
            "errors": [e for e in [err1, err2, err3, err4] if e]
        }, None)

    def _full_report(self, params):
        """Full CognitiveLoop report with constraints, solutions, mistakes, verifications."""
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        c = self.conn.cursor()
        # Get all Q&A with constraints, solutions, mistakes, verifications
        c.execute("""SELECT q.id, q.category, q.question, q.depth,
                            a.answer, a.evidence,
                            cs.rule_type, cs.rule_text,
                            sl.suggested_solution,
                            mk.pattern, mk.fix_action, mk.confidence,
                            vf.verified, vf.result
                     FROM questions q
                     LEFT JOIN answers a ON q.id = a.question_id
                     LEFT JOIN constraints cs ON q.id = cs.question_id
                     LEFT JOIN solutions sl ON q.id = sl.question_id
                     LEFT JOIN mistakes mk ON q.id = mk.question_id
                     LEFT JOIN verifications vf ON q.id = vf.question_id
                     WHERE q.problem_id = ?
                     ORDER BY q.depth, q.category, q.id""",
                  (problem_id,))
        rows = c.fetchall()
        # Collapse check
        ok, collapse, err = self._collapse_check({"problem_id": problem_id})
        # Count by type
        constraints_count = sum(1 for r in rows if r["rule_type"])
        solutions_count = sum(1 for r in rows if r["suggested_solution"])
        mistakes_count = sum(1 for r in rows if r["pattern"])
        verified_count = sum(1 for r in rows if r["verified"])
        lines = []
        lines.append("=" * 70)
        lines.append("COGNITIVE LOOP REPORT (QuestionStore + EngineV2 pattern)")
        lines.append(f"Problem ID: {problem_id}")
        lines.append(f"Loop: Problem → Question → Answer → Constraint → Solution → Mistake → Verify")
        lines.append("=" * 70)
        lines.append(f"  Questions:     {collapse['total_questions']}")
        lines.append(f"  Facts (Y/N):   {collapse['facts']}")
        lines.append(f"  Unknowns:      {collapse['unknowns']}")
        lines.append(f"  Constraints:   {constraints_count}")
        lines.append(f"  Solutions:     {solutions_count}")
        lines.append(f"  Mistakes:      {mistakes_count}")
        lines.append(f"  Verified:      {verified_count}")
        lines.append(f"  Status:        {collapse['status']}")
        lines.append("")
        # Group by category
        grouped = {}
        for r in rows:
            cat = r["category"] or "uncategorized"
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(r)
        for cat in sorted(grouped.keys()):
            items = grouped[cat]
            lines.append(f"── {cat} ({len(items)} questions) ──")
            for r in items:
                ans = r["answer"] or "UNANSWERED"
                marker = {"YES": "[Y]", "NO": "[N]", "UNKNOWN": "[?]",
                          "ACTION": "[A]", None: "[ ]"}.get(ans, "[?]")
                lines.append(f"  {marker} (d{r['depth']}) {r['question']}")
                if r["evidence"]:
                    lines.append(f"       evidence: {r['evidence'][:100]}")
                if r["rule_type"]:
                    lines.append(f"       constraint: [{r['rule_type']}] {r['rule_text']}")
                if r["suggested_solution"]:
                    lines.append(f"       solution: {r['suggested_solution'][:100]}")
                if r["pattern"]:
                    lines.append(f"       mistake: {r['pattern'][:60]} → {r['fix_action'][:60]} (conf={r['confidence']})")
                if r["verified"] is not None:
                    vmark = "VERIFIED" if r["verified"] else "FAILED"
                    lines.append(f"       verify: {vmark} — {r['result']}")
            lines.append("")
        lines.append("=" * 70)
        if collapse["status"] == "collapsed":
            lines.append("PROBLEM SPACE COLLAPSED — zero unknowns")
        elif collapse["status"] == "good_enough":
            lines.append(f"GOOD ENOUGH — {collapse['facts']} facts, {collapse['unknowns']} unknowns")
        else:
            lines.append(f"OPEN — {collapse['unknowns']} unknowns remaining, keep asking")
        lines.append("=" * 70)
        report = "\n".join(lines)
        return (1, {
            "report": report,
            "collapse": collapse,
            "counts": {
                "questions": collapse["total_questions"],
                "facts": collapse["facts"],
                "unknowns": collapse["unknowns"],
                "constraints": constraints_count,
                "solutions": solutions_count,
                "mistakes": mistakes_count,
                "verified": verified_count
            }
        }, None)

    def close(self):
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    import sys
    qs = QuestionStore()
    if len(sys.argv) < 2:
        print("Usage: question_store.py <command> [json_params]")
        print("Commands: register_problem, ask, answer, group, facts, unknowns,")
        print("          collapse_check, report, list_problems, stats, reset")
        sys.exit(1)
    cmd = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ok, data, error = qs.Run(cmd, params)
    if ok:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
    qs.close()
