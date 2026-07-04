#!/usr/bin/env python3
# [@GHOST]{[@file<demo_full_loop.py>][@domain<Dom_Report>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<DiagnosticDB>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Full feedback loop demo — Execution → Report → Investigation → MySQL DiagnosticDB. Stores the entire incident (facts, diagnosis, causes, fixes, prevention) and retrieves it.}
# [@FILEID]{core/Dom_Report/demo_full_loop.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Report.ReportUnit import ReportUnit
from core.Dom_Report.Investigator import Investigator
from core.Dom_Report.DiagnosticDB import DiagnosticDB
from core.Dom_Report import Config


def main():
    # ── Layer 1: Execution → Report ──
    ru = ReportUnit()
    ru.Run("open", {"operation": "ReadFile", "source": "FileIO.read_file"})
    ru.Run("emit", {"kind": "input", "name": "path", "value": "/nonexistent/missing.py"})
    ru.Run("emit", {"kind": "issue", "name": "file_not_found", "value": "File not found", "severity": "error", "detail": "the file does not exist on disk"})
    ru.Run("emit", {"kind": "recommendation", "name": "suggestion", "value": "verify the file path exists before calling read_file"})
    ru.Run("result", {"ok": False, "reason": "File not found"})
    ru.Run("finalize", {})

    ok, report_text, _ = ru.Run("render", {"verbosity": "verbose", "use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 1 — REPORT\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(report_text + "\n\n")

    # ── Layer 2: Investigation ──
    inv = Investigator()
    inv.Run("investigate", {"report": ru.state["report"]})
    ok, diag_text, _ = inv.Run("render_diagnosis", {"use_color": False})
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 2 — INVESTIGATION\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(diag_text + "\n")

    # ── Layer 3: Store to MySQL DiagnosticDB ──
    db = DiagnosticDB()
    if not db.state["connected"]:
        sys.stdout.write("ERROR: Cannot connect to MySQL diagnostic_kb database.\n")
        sys.stdout.write("Start MySQL: /opt/homebrew/bin/mysqld_safe --datadir=/opt/homebrew/var/mysql &\n")
        return

    rstate = inv.state["report_state"]
    ok, incident_id, err = db.Run("store_incident", {
        "operation": rstate["operation"],
        "source": rstate["source"],
        "result": rstate["result"],
        "reason": rstate["reason"],
        "fact_count": inv.state["facts_count"],
    })

    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("LAYER 3 — STORE TO MySQL diagnostic_kb\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Incident ID: %d\n" % incident_id)

    # Store all facts
    ok, facts, _ = ru.state["report"].Run("get_facts", {})
    facts_stored = 0
    for f in facts:
        db.Run("store_fact", {
            "incident_id": incident_id,
            "slot": Config.KIND_TO_SLOT.get(f.state["kind"], Config.SLOT_OCCURRENCES),
            "kind": f.state["kind"],
            "name": f.state["name"],
            "value": str(f.state["value"]),
            "severity": f.state["severity"],
            "unit": f.state["unit"],
            "detail": f.state["detail"],
            "source": f.state["source"],
        })
        facts_stored += 1
    sys.stdout.write("Facts stored: %d\n" % facts_stored)

    # Store the diagnosis (all 19 answers)
    ok, answers_stored, _ = db.Run("store_diagnosis", {
        "incident_id": incident_id,
        "diagnosis": inv.state["diagnosis"],
    })
    sys.stdout.write("Answers stored: %d\n" % answers_stored)

    # Store the cause
    db.Run("store_cause", {
        "incident_id": incident_id,
        "cause_type": "root",
        "cause_text": rstate["reason"],
        "severity": 3,
        "evidence": "issue fact: file_not_found",
    })
    sys.stdout.write("Cause stored: 1\n")

    # Store the fix (from the recommendation fact)
    recs = [f for f in facts if f.state["kind"] == Config.KIND_RECOMMENDATION]
    if recs:
        db.Run("store_fix", {
            "incident_id": incident_id,
            "fix_type": "recommended",
            "fix_action": recs[0].state["value"],
            "confidence": 0.7,
        })
        sys.stdout.write("Fix stored: 1\n")

    # Store prevention rule
    db.Run("store_prevention", {
        "incident_id": incident_id,
        "prevention_type": "guard",
        "rule_text": "Validate file path with os.path.exists() before calling read_file",
    })
    sys.stdout.write("Prevention stored: 1\n")

    # Create or update the problem type
    ok, problem_id, _ = db.Run("create_problem", {
        "problem": "FileNotFoundError on read_file",
        "description": "Attempted to read a file that does not exist on disk",
        "category": "filesystem",
    })
    sys.stdout.write("Problem ID: %d\n" % problem_id)

    # Link incident to problem
    db.Run("link_incident_problem", {"incident_id": incident_id, "problem_id": problem_id})
    sys.stdout.write("Incident linked to problem: yes\n")

    # Add a solution to the problem
    db.Run("add_solution", {
        "problem_id": problem_id,
        "solution": "Check os.path.exists() before read_file",
        "weight": 0.85,
        "auto_apply": 1,
    })
    sys.stdout.write("Solution added: 1\n")

    # Add a learned rule
    db.Run("add_learned_rule", {
        "pattern": "read_file called without path validation",
        "fix_action": "Add os.path.exists() guard before read_file",
        "category": "error_handling",
        "confidence": 0.9,
        "problem_id": problem_id,
    })
    sys.stdout.write("Learned rule added: 1\n")

    # ── Layer 4: Retrieve from DB ──
    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("LAYER 4 — RETRIEVE FROM MySQL diagnostic_kb\n")
    sys.stdout.write("=" * 60 + "\n")

    ok, incident, _ = db.Run("get_incident", {"incident_id": incident_id})
    sys.stdout.write("Incident: %s | result=%s | facts=%d\n" % (
        incident["operation"], incident["result"], len(incident["facts"])
    ))

    ok, answers, _ = db.Run("get_diagnosis", {"incident_id": incident_id})
    known = sum(1 for a in answers if a["status"] == "known")
    pending = sum(1 for a in answers if a["status"] == "pending")
    sys.stdout.write("Diagnosis: %d answers (%d known, %d pending)\n" % (len(answers), known, pending))

    ok, problems, _ = db.Run("search_problems", {"search": "FileNotFoundError"})
    sys.stdout.write("Problems found: %d\n" % len(problems))
    for p in problems[:3]:
        sys.stdout.write("  — [%d] %s (occurrences: %d)\n" % (p["id"], p["problem"], p["occurrence_count"]))

    ok, rules, _ = db.Run("search_learned_rules", {"search": "read_file"})
    sys.stdout.write("Learned rules found: %d\n" % len(rules))
    for r in rules[:3]:
        sys.stdout.write("  — [conf=%.2f] %s → %s\n" % (r["confidence"], r["pattern"][:50], r["fix_action"][:50]))

    ok, solutions, _ = db.Run("search_solutions", {"search": "exists"})
    sys.stdout.write("Solutions found: %d\n" % len(solutions))
    for s in solutions[:3]:
        sys.stdout.write("  — [weight=%.2f] %s\n" % (s["weight"], s["solution"][:60]))

    # ── Summary ──
    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("FULL FEEDBACK LOOP COMPLETE\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Execution → Report → Investigation → MySQL Storage → Retrieval\n")
    sys.stdout.write("\nDB stats: %s\n" % str(db.state["stats"]))


if __name__ == "__main__":
    main()
