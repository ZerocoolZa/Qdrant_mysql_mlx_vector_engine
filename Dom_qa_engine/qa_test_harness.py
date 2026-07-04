#!/usr/bin/env python3
"""
QA Test Harness — Curated Chat + 3-Mode Result Storage

Creates a SQLite test database with two tables:
  1. curated_chat  — curated Q&A pairs with evidence text (ground truth)
  2. qa_results    — results from running GhostQA against each question

Three modes tested:
  TRUE    — answer found AND matches expected answer
  FALSE   — answer found but does NOT match expected answer
  UNKNOWN — answer not found (confidence below threshold or "Not Found")

Usage:
  python3 qa_test_harness.py --setup    # create DB + insert curated data
  python3 qa_test_harness.py --run      # run GhostQA against all curated questions
  python3 qa_test_harness.py --report   # show results summary
  python3 qa_test_harness.py --all      # setup + run + report
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "qa_test.db")

# ─── Curated Q&A pairs ───────────────────────────────────────────────────
# Each entry has:
#   id          — unique identifier
#   category    — what domain this tests
#   question    — the question to ask
#   evidence    — the source text the answer should come from
#   expected    — the expected answer string (what BERT QA should extract)
#   expected_mode — TRUE (answer should be found and correct)
#                   FALSE (answer will be found but wrong — mismatched context)
#                   UNKNOWN (answer should NOT be found — question unrelated to evidence)

CURATED_DATA = [
    # ─── TRUE cases: answer exists in evidence and should be extracted ───
    {
        "id": "T01",
        "category": "vbstyle_core",
        "question": "What is MemUnit?",
        "evidence": "MemUnit is the core execution authority in VBStyle. It is the only place where execution runs. It acts as a dispatcher, not a selector. The orchestrator loads a precomputed path and MemUnit executes it deterministically.",
        "expected": "the core execution authority",
        "expected_mode": "TRUE",
    },
    {
        "id": "T02",
        "category": "vbstyle_core",
        "question": "What does the Reporter class handle?",
        "evidence": "The Reporter class handles central output in VBStyle. No print statements are allowed. All output goes through Reporter which returns strings, not prints to console.",
        "expected": "central output",
        "expected_mode": "TRUE",
    },
    {
        "id": "T03",
        "category": "vbstyle_rules",
        "question": "What is Rule 7 in VBStyle?",
        "evidence": "Rule 7: NO print statements. Use the Report class or logging instead. This rule has severity level 3 and is enforced by the RuleEnforcer. Violations are recorded in method_violations table.",
        "expected": "no print statements",
        "expected_mode": "TRUE",
    },
    {
        "id": "T04",
        "category": "vbstyle_rules",
        "question": "What is Rule 8 in VBStyle?",
        "evidence": "Rule 8: NO hardcoded paths. Nothing is allowed to be hardcoded. Database names, users, paths must all come from config or memunit. This rule has severity level 3.",
        "expected": "no hardcoded paths",
        "expected_mode": "TRUE",
    },
    {
        "id": "T05",
        "category": "vbstyle_architecture",
        "question": "What is the boot spine order?",
        "evidence": "The boot spine is fixed and deterministic: Config then MemDB then AST then Brackets then ClassDB then Orchestration then MemUnit then Report then Output. This order cannot break.",
        "expected": "config then memdb then ast then brackets then classdb then orchestration then memunit then report then output",
        "expected_mode": "TRUE",
    },
    {
        "id": "T06",
        "category": "vbstyle_architecture",
        "question": "What is BCL?",
        "evidence": "BCL stands for Bracket Configuration Language. It uses bracket syntax like [@name]{...} for both passive configuration state and active execution commands. Config is read passively, commands are executed by MemUnit.",
        "expected": "bracket configuration language",
        "expected_mode": "TRUE",
    },
    {
        "id": "T07",
        "category": "vbstyle_patterns",
        "question": "What return format do all VBStyle methods use?",
        "evidence": "All VBStyle methods must return Tuple3 format: (ok, data, error). On success return (1, data, None). On error return (0, None, error_tuple). The error tuple format is (code, description, 0).",
        "expected": "tuple3",
        "expected_mode": "TRUE",
    },
    {
        "id": "T08",
        "category": "vbstyle_patterns",
        "question": "What is the constructor signature in VBStyle?",
        "evidence": "The VBStyle constructor signature is: def __init__(self, mem=None, db=None, param=None). Every class receives mem as the shared memory bus. The state dictionary holds config, catalog, results, errors, and meta.",
        "expected": "def __init__(self, mem=none, db=none, param=none)",
        "expected_mode": "TRUE",
    },
    {
        "id": "T09",
        "category": "general",
        "question": "What is the capital of France?",
        "evidence": "Paris is the capital of France. France is a country in Western Europe bordering Belgium, Germany, Switzerland, Italy, and Spain.",
        "expected": "paris",
        "expected_mode": "TRUE",
    },
    {
        "id": "T10",
        "category": "general",
        "question": "What port does MemDB use?",
        "evidence": "MemDB uses port 7011 for its in-memory SQLite runtime state substrate. It operates in RAM with SQLite tables as channels for the memory bus.",
        "expected": "7011",
        "expected_mode": "TRUE",
    },

    # ─── FALSE cases: answer will be extracted but from wrong context ───
    # The question is asked against evidence that does NOT contain the answer,
    # but the BERT QA model may still extract something with low confidence.
    # We expect the system to either return UNKNOWN (ideal) or FALSE (wrong answer).
    {
        "id": "F01",
        "category": "mismatched_context",
        "question": "What is the capital of Japan?",
        "evidence": "The VBStyle lifecycle has five stages: parm, validate, execute, return_, and cleanup. Each stage has specific responsibilities in the execution chain.",
        "expected": None,
        "expected_mode": "FALSE",
    },
    {
        "id": "F02",
        "category": "mismatched_context",
        "question": "What database does MemUnit use?",
        "evidence": "Wayne's Container Laws state that every class must own exactly one domain. One class, one domain, one authority. No class may cross domain boundaries. This is the Domain Collapse Law.",
        "expected": None,
        "expected_mode": "FALSE",
    },
    {
        "id": "F03",
        "category": "mismatched_context",
        "question": "How many chapters are in the VBStyle book?",
        "evidence": "The Zero-Drift Philosophy states that code should be written so the problem never occurs. Prevention over correction. Do not write code where you go back and fix it.",
        "expected": None,
        "expected_mode": "FALSE",
    },

    # ─── UNKNOWN cases: question has no relevant evidence at all ───
    # The retrieval step should find nothing above threshold,
    # or the QA model should return very low confidence.
    {
        "id": "U01",
        "category": "no_evidence",
        "question": "What is the airspeed of an unladen swallow?",
        "evidence": "MemUnit is the execution authority. It dispatches commands and manages the execution chain. The orchestrator builds the dependency graph and loads the precomputed execution path.",
        "expected": None,
        "expected_mode": "UNKNOWN",
    },
    {
        "id": "U02",
        "category": "no_evidence",
        "question": "How do I configure nginx for load balancing?",
        "evidence": "The state dictionary in VBStyle holds config, catalog, results, errors, and meta. No self._ variables are allowed. All state flows through self.state dict. Constants are UPPERCASE at class level.",
        "expected": None,
        "expected_mode": "UNKNOWN",
    },
    {
        "id": "U03",
        "category": "no_evidence",
        "question": "What is the weather in Tokyo today?",
        "evidence": "Bracket annotations use the syntax [@name]{...} for both configuration and commands. The same syntax serves two consumers: dom_config reads passive state, MemUnit executes active commands.",
        "expected": None,
        "expected_mode": "UNKNOWN",
    },
]


def setup_database():
    """Create the test database and insert curated data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table 1: curated_chat — ground truth Q&A pairs
    c.execute("""
        CREATE TABLE curated_chat (
            id            TEXT PRIMARY KEY,
            category      TEXT NOT NULL,
            question      TEXT NOT NULL,
            evidence      TEXT NOT NULL,
            expected      TEXT,
            expected_mode TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # Table 2: qa_results — results from running GhostQA
    c.execute("""
        CREATE TABLE qa_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            curated_id      TEXT NOT NULL,
            question        TEXT NOT NULL,
            extracted       TEXT,
            confidence      REAL,
            expected        TEXT,
            expected_mode   TEXT NOT NULL,
            actual_mode     TEXT NOT NULL,
            mode_correct    INTEGER NOT NULL,
            answer_correct  INTEGER NOT NULL,
            source          TEXT,
            evidence_used   TEXT,
            run_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (curated_id) REFERENCES curated_chat(id)
        )
    """)

    # Insert curated data
    for item in CURATED_DATA:
        c.execute("""
            INSERT INTO curated_chat (id, category, question, evidence, expected, expected_mode)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item["category"],
            item["question"],
            item["evidence"],
            item["expected"],
            item["expected_mode"],
        ))

    conn.commit()

    counts = c.execute("SELECT expected_mode, COUNT(*) FROM curated_chat GROUP BY expected_mode").fetchall()
    print(f"Database created: {DB_PATH}")
    print(f"Total curated entries: {len(CURATED_DATA)}")
    for mode, count in counts:
        print(f"  {mode}: {count}")

    conn.close()


def run_tests():
    """Run GhostQA ExtractAnswer against each curated question using its evidence as context."""
    from qa_prototype import GhostQA

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    rows = c.execute("""
        SELECT id, category, question, evidence, expected, expected_mode
        FROM curated_chat
        ORDER BY id
    """).fetchall()

    print(f"\nRunning {len(rows)} tests...")
    print(f"{'ID':5s} {'Mode':8s} {'Question':45s} {'Extracted':30s} {'Conf':>8s} {'Actual':8s} {'Correct':8s}")
    print("-" * 120)

    qa = GhostQA()
    ok, _, err = qa.Run("load_models")
    if not ok:
        print(f"ERROR loading models: {err}")
        conn.close()
        return

    total = 0
    mode_correct_count = 0
    answer_correct_count = 0

    for row in rows:
        curated_id, category, question, evidence, expected, expected_mode = row
        total += 1

        # Run BERT QA extraction directly with the curated evidence as context
        ok, result, err = qa.Run("extract", {
            "question": question,
            "context": evidence,
        })

        if not ok:
            print(f"{curated_id:5s} {expected_mode:8s} {question[:45]:45s} ERROR: {err}")
            # Store as UNKNOWN
            actual_mode = "UNKNOWN"
            mode_correct = 1 if expected_mode == "UNKNOWN" else 0
            answer_correct = 0
            extracted = None
            confidence = -999.0
        else:
            extracted = result["answer"]
            confidence = result["confidence"]

            # Determine actual mode based on confidence
            qa_threshold = qa.state["config"]["qa_confidence_threshold"]
            if confidence < qa_threshold:
                actual_mode = "UNKNOWN"
            elif expected is not None and expected.lower() in extracted.lower():
                actual_mode = "TRUE"
            else:
                actual_mode = "FALSE"

            # Check if mode classification is correct
            mode_correct = 1 if actual_mode == expected_mode else 0

            # Check if answer content is correct (only for TRUE cases)
            if expected is not None:
                answer_correct = 1 if expected.lower() in extracted.lower() else 0
            else:
                answer_correct = 1 if actual_mode in ("UNKNOWN", "FALSE") else 0

        mode_correct_count += mode_correct
        answer_correct_count += answer_correct

        # Store result in qa_results table
        c.execute("""
            INSERT INTO qa_results
                (curated_id, question, extracted, confidence, expected, expected_mode,
                 actual_mode, mode_correct, answer_correct, source, evidence_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            curated_id,
            question,
            extracted,
            confidence,
            expected,
            expected_mode,
            actual_mode,
            mode_correct,
            answer_correct,
            "bert_squad_coreml",
            evidence[:300],
        ))

        status = "OK" if mode_correct else "XX"
        print(f"{curated_id:5s} {expected_mode:8s} {question[:45]:45s} {(extracted or 'None')[:30]:30s} {confidence:8.2f} {actual_mode:8s} {status}")

    conn.commit()
    conn.close()

    print("-" * 120)
    print(f"\nSUMMARY:")
    print(f"  Total tests:        {total}")
    print(f"  Mode correct:       {mode_correct_count}/{total} ({mode_correct_count/total*100:.0f}%)")
    print(f"  Answer correct:     {answer_correct_count}/{total} ({answer_correct_count/total*100:.0f}%)")


def report():
    """Show detailed results from the qa_results table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("\n" + "=" * 100)
    print("QA TEST RESULTS REPORT")
    print("=" * 100)

    # Summary by expected mode
    print("\n--- BY EXPECTED MODE ---")
    rows = c.execute("""
        SELECT expected_mode,
               COUNT(*) as total,
               SUM(mode_correct) as mode_ok,
               SUM(answer_correct) as ans_ok,
               AVG(confidence) as avg_conf,
               MIN(confidence) as min_conf,
               MAX(confidence) as max_conf
        FROM qa_results
        GROUP BY expected_mode
        ORDER BY expected_mode
    """).fetchall()

    print(f"{'Mode':8s} {'Total':>6s} {'ModeOK':>7s} {'AnsOK':>6s} {'AvgConf':>9s} {'MinConf':>9s} {'MaxConf':>9s}")
    print("-" * 60)
    for mode, total, mode_ok, ans_ok, avg_conf, min_conf, max_conf in rows:
        print(f"{mode:8s} {total:6d} {mode_ok:7d} {ans_ok:6d} {avg_conf:9.2f} {min_conf:9.2f} {max_conf:9.2f}")

    # Confusion matrix: expected vs actual
    print("\n--- CONFUSION MATRIX (expected vs actual) ---")
    rows = c.execute("""
        SELECT expected_mode, actual_mode, COUNT(*) as count
        FROM qa_results
        GROUP BY expected_mode, actual_mode
        ORDER BY expected_mode, actual_mode
    """).fetchall()

    print(f"{'Expected':10s} {'Actual':10s} {'Count':>6s}")
    print("-" * 30)
    for exp, act, count in rows:
        print(f"{exp:10s} {act:10s} {count:6d}")

    # False positives: expected UNKNOWN/FALSE but got TRUE
    print("\n--- FALSE POSITIVES (expected UNKNOWN/FALSE, got TRUE) ---")
    rows = c.execute("""
        SELECT curated_id, question, extracted, confidence, expected_mode, actual_mode
        FROM qa_results
        WHERE expected_mode IN ('UNKNOWN', 'FALSE') AND actual_mode = 'TRUE'
    """).fetchall()
    if rows:
        for cid, q, ext, conf, exp, act in rows:
            print(f"  {cid}: {q[:50]} -> '{ext[:30]}' (conf={conf:.2f}) expected={exp} got={act}")
    else:
        print("  None")

    # False negatives: expected TRUE but got UNKNOWN/FALSE
    print("\n--- FALSE NEGATIVES (expected TRUE, got UNKNOWN/FALSE) ---")
    rows = c.execute("""
        SELECT curated_id, question, extracted, confidence, expected_mode, actual_mode
        FROM qa_results
        WHERE expected_mode = 'TRUE' AND actual_mode != 'TRUE'
    """).fetchall()
    if rows:
        for cid, q, ext, conf, exp, act in rows:
            print(f"  {cid}: {q[:50]} -> '{(ext or 'None')[:30]}' (conf={conf:.2f}) expected={exp} got={act}")
    else:
        print("  None")

    # All results detail
    print("\n--- ALL RESULTS ---")
    rows = c.execute("""
        SELECT curated_id, question, extracted, confidence, expected, expected_mode, actual_mode, mode_correct
        FROM qa_results
        ORDER BY curated_id
    """).fetchall()

    print(f"{'ID':5s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Conf':>8s} {'Question':40s} {'Extracted':30s} {'Expected':30s}")
    print("-" * 140)
    for cid, q, ext, conf, exp, exp_mode, act_mode, ok in rows:
        print(f"{cid:5s} {exp_mode:5s} {act_mode:5s} {'Y' if ok else 'N':3s} {conf:8.2f} {q[:40]:40s} {(ext or 'None')[:30]:30s} {(exp or 'None')[:30]:30s}")

    conn.close()


def main():
    args = sys.argv[1:]
    if not args or "--all" in args:
        setup_database()
        run_tests()
        report()
    elif "--setup" in args:
        setup_database()
    elif "--run" in args:
        run_tests()
    elif "--report" in args:
        report()
    else:
        print("Usage: python3 qa_test_harness.py [--setup|--run|--report|--all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
