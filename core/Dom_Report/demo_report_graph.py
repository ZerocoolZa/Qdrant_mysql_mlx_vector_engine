#!/usr/bin/env python3
# [@GHOST]{[@file<demo_report_graph.py>][@domain<Dom_Report>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<DiagnosticDB>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Demo: store a report as references (join tables), then walk the graph to reconstruct the story. A report is a container of relationships — 1:N to every entity. The story is assembled by following the links.}
# [@FILEID]{core/Dom_Report/demo_report_graph.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mysql.connector


def connect():
    return mysql.connector.connect(
        host="localhost", user="root", password="",
        database="diagnostic_kb", unix_socket="/tmp/mysql.sock"
    )


def main():
    conn = connect()
    cur = conn.cursor(dictionary=True)

    # ── Step 1: Find the failed incident ──
    cur.execute("SELECT * FROM incident WHERE result='fail' ORDER BY id LIMIT 1")
    incident = cur.fetchone()
    if not incident:
        sys.stdout.write("No failed incidents found. Run demo_full_loop.py first.\n")
        return

    # ── Step 2: Gather entities for this incident ──
    cur.execute("SELECT * FROM error WHERE name IN ('FileNotFoundError','OSError','PermissionError') ORDER BY id")
    errors = cur.fetchall()

    cur.execute("SELECT * FROM problem WHERE problem LIKE '%FileNotFound%' ORDER BY id")
    problems = cur.fetchall()

    cur.execute("SELECT * FROM fact WHERE incident_id=%s ORDER BY id", (incident["id"],))
    facts = cur.fetchall()

    cur.execute("SELECT * FROM answer WHERE incident_id=%s ORDER BY category, id", (incident["id"],))
    answers = cur.fetchall()

    cur.execute("SELECT * FROM cause WHERE incident_id=%s ORDER BY id", (incident["id"],))
    causes = cur.fetchall()

    cur.execute("SELECT * FROM fix WHERE incident_id=%s ORDER BY id", (incident["id"],))
    fixes = cur.fetchall()

    cur.execute("SELECT * FROM prevention WHERE incident_id=%s ORDER BY id", (incident["id"],))
    preventions = cur.fetchall()

    cur.execute("SELECT * FROM evidence WHERE incident_id=%s ORDER BY id", (incident["id"],))
    evidence_rows = cur.fetchall()

    rules = []
    if problems:
        cur.execute("SELECT * FROM rule WHERE problem_id=%s OR pattern LIKE %s ORDER BY confidence DESC LIMIT 3", (problems[0]["id"], "%read_file%"))
        rules = cur.fetchall()

    # ── Step 3: Create the report — root node with incident_id ──
    cur.execute(
        "INSERT INTO report (title, incident_id) VALUES (%s, %s)",
        ("ReadFile failure report", incident["id"])
    )
    report_id = cur.lastrowid

    # ── Step 4: Link ALL entities via join tables (1:N) ──
    for i, e in enumerate(errors):
        cur.execute("INSERT IGNORE INTO report_error (report_id, error_id, sort_order) VALUES (%s, %s, %s)", (report_id, e["id"], i))
    for p in problems:
        cur.execute("INSERT IGNORE INTO report_problem (report_id, problem_id) VALUES (%s, %s)", (report_id, p["id"]))
    for c in causes:
        cur.execute("INSERT IGNORE INTO report_cause (report_id, cause_id) VALUES (%s, %s)", (report_id, c["id"]))
    for i, f in enumerate(fixes):
        cur.execute("INSERT IGNORE INTO report_fix (report_id, fix_id, sort_order) VALUES (%s, %s, %s)", (report_id, f["id"], i))
    for p in preventions:
        cur.execute("INSERT IGNORE INTO report_prevention (report_id, prevention_id) VALUES (%s, %s)", (report_id, p["id"]))
    for i, f in enumerate(facts):
        cur.execute("INSERT IGNORE INTO report_fact (report_id, fact_id, sort_order) VALUES (%s, %s, %s)", (report_id, f["id"], i))
    for a in answers:
        cur.execute("INSERT IGNORE INTO report_answer (report_id, answer_id) VALUES (%s, %s)", (report_id, a["id"]))
    for e in evidence_rows:
        cur.execute("INSERT IGNORE INTO report_evidence (report_id, evidence_id) VALUES (%s, %s)", (report_id, e["id"]))
    for r in rules:
        cur.execute("INSERT IGNORE INTO report_rule (report_id, rule_id) VALUES (%s, %s)", (report_id, r["id"]))

    conn.commit()

    # ── Step 5: Show what was stored (references only, no text) ──
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("REPORT #%d — STORED AS REFERENCES (join tables)\n" % report_id)
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("title:        %s\n" % "ReadFile failure report")
    sys.stdout.write("incident_id:  %d  (root entity)\n" % incident["id"])
    sys.stdout.write("errors:       %d linked  → %s\n" % (len(errors), ", ".join(str(e["id"]) for e in errors)))
    sys.stdout.write("problems:     %d linked  → %s\n" % (len(problems), ", ".join(str(p["id"]) for p in problems)))
    sys.stdout.write("causes:       %d linked  → %s\n" % (len(causes), ", ".join(str(c["id"]) for c in causes)))
    sys.stdout.write("fixes:        %d linked  → %s\n" % (len(fixes), ", ".join(str(f["id"]) for f in fixes)))
    sys.stdout.write("preventions:  %d linked  → %s\n" % (len(preventions), ", ".join(str(p["id"]) for p in preventions)))
    sys.stdout.write("facts:        %d linked  → %s\n" % (len(facts), ", ".join(str(f["id"]) for f in facts)))
    sys.stdout.write("answers:      %d linked  → %s\n" % (len(answers), ", ".join(str(a["id"]) for a in answers)))
    sys.stdout.write("evidence:     %d linked  → %s\n" % (len(evidence_rows), ", ".join(str(e["id"]) for e in evidence_rows)))
    sys.stdout.write("rules:        %d linked  → %s\n" % (len(rules), ", ".join(str(r["id"]) for r in rules)))
    sys.stdout.write("\n")
    total_refs = 1 + len(errors) + len(problems) + len(causes) + len(fixes) + len(preventions) + len(facts) + len(answers) + len(evidence_rows) + len(rules)
    sys.stdout.write("The report stores %d FK references. 0 bytes of story text.\n" % total_refs)
    sys.stdout.write("Now the report engine walks the graph...\n\n")

    # ── Step 6: WALK THE GRAPH — reconstruct the story ──
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("REPORT #%d — STORY RECONSTRUCTED FROM GRAPH\n" % report_id)
    sys.stdout.write("=" * 70 + "\n\n")

    # ── Incident (root) ──
    cur.execute("""
        SELECT i.*, s.name as status_name, sev.name as severity_name, sev.level as sev_level
        FROM incident i
        LEFT JOIN status s ON i.status_id=s.id
        LEFT JOIN severity sev ON i.severity_id=sev.id
        WHERE i.id=%s
    """, (incident["id"],))
    inc = cur.fetchone()
    sys.stdout.write("INCIDENT #%d\n" % inc["id"])
    sys.stdout.write("  Operation: %s\n" % inc["operation"])
    sys.stdout.write("  Source:    %s\n" % inc["source"])
    sys.stdout.write("  Result:    %s (status: %s, severity: %s level %d)\n" % (inc["result"], inc["status_name"], inc["severity_name"], inc["sev_level"]))
    sys.stdout.write("  Reason:    %s\n\n" % (inc["reason"] or ""))

    # ── Errors (1:N via report_error) ──
    cur.execute("""
        SELECT e.*, d.name as domain, c.name as category, t.name as type,
               s.name as status, sev.name as severity, sev.level as sev_level, p.name as priority
        FROM error e
        JOIN report_error re ON e.id=re.error_id
        LEFT JOIN domain d ON e.domain_id=d.id
        LEFT JOIN category c ON e.category_id=c.id
        LEFT JOIN type t ON e.type_id=t.id
        LEFT JOIN status s ON e.status_id=s.id
        LEFT JOIN severity sev ON e.severity_id=sev.id
        LEFT JOIN priority p ON e.priority_id=p.id
        WHERE re.report_id=%s ORDER BY re.sort_order
    """, (report_id,))
    linked_errors = cur.fetchall()
    sys.stdout.write("ERRORS (%d linked via report_error)\n" % len(linked_errors))
    for err in linked_errors:
        sys.stdout.write("  #%d  %s\n" % (err["id"], err["name"]))
        sys.stdout.write("       Sentence: A %s %s %s error named '%s'. Status: %s. Severity: %s (level %d). Priority: %s.\n" % (
            err["domain"] or "?", err["category"] or "?", err["type"] or "?",
            err["name"], err["status"] or "?", err["severity"] or "?", err["sev_level"] or 0, err["priority"] or "?"))
        if err["cause"]:
            sys.stdout.write("       Cause:    %s\n" % err["cause"])
        if err["solution"]:
            sys.stdout.write("       Solution: %s\n" % err["solution"])
        sys.stdout.write("       Freq: %d  Confidence: %s\n" % (err["frequency"], err["confidence"]))
    sys.stdout.write("\n")

    # ── Problems (1:N via report_problem) ──
    cur.execute("""
        SELECT p.* FROM problem p
        JOIN report_problem rp ON p.id=rp.problem_id
        WHERE rp.report_id=%s ORDER BY p.id
    """, (report_id,))
    linked_problems = cur.fetchall()
    sys.stdout.write("PROBLEMS (%d linked via report_problem)\n" % len(linked_problems))
    for prob in linked_problems:
        sys.stdout.write("  #%d  %s — %s (occurrences: %d)\n" % (prob["id"], prob["problem"], prob["description"] or "", prob["occurrence_count"]))
    sys.stdout.write("\n")

    # ── Causes (1:N via report_cause) ──
    cur.execute("""
        SELECT c.* FROM cause c
        JOIN report_cause rc ON c.id=rc.cause_id
        WHERE rc.report_id=%s ORDER BY c.id
    """, (report_id,))
    linked_causes = cur.fetchall()
    sys.stdout.write("CAUSES (%d linked via report_cause)\n" % len(linked_causes))
    for cau in linked_causes:
        sys.stdout.write("  #%d  [%s] %s (severity: %d)\n" % (cau["id"], cau["cause_type"], cau["cause_text"], cau["severity"]))
    sys.stdout.write("\n")

    # ── Fixes (1:N via report_fix) ──
    cur.execute("""
        SELECT f.* FROM fix f
        JOIN report_fix rf ON f.id=rf.fix_id
        WHERE rf.report_id=%s ORDER BY rf.sort_order
    """, (report_id,))
    linked_fixes = cur.fetchall()
    sys.stdout.write("FIXES (%d linked via report_fix)\n" % len(linked_fixes))
    for fx in linked_fixes:
        sys.stdout.write("  #%d  [%s] %s → result: %s (confidence: %s)\n" % (fx["id"], fx["fix_type"], fx["fix_action"], fx["result"], fx["confidence"]))
    sys.stdout.write("\n")

    # ── Preventions (1:N via report_prevention) ──
    cur.execute("""
        SELECT pr.* FROM prevention pr
        JOIN report_prevention rp ON pr.id=rp.prevention_id
        WHERE rp.report_id=%s ORDER BY pr.id
    """, (report_id,))
    linked_preventions = cur.fetchall()
    sys.stdout.write("PREVENTIONS (%d linked via report_prevention)\n" % len(linked_preventions))
    for pr in linked_preventions:
        sys.stdout.write("  #%d  [%s] %s\n" % (pr["id"], pr["prevention_type"], pr["rule_text"]))
    sys.stdout.write("\n")

    # ── Facts (1:N via report_fact) ──
    cur.execute("""
        SELECT f.* FROM fact f
        JOIN report_fact rf ON f.id=rf.fact_id
        WHERE rf.report_id=%s ORDER BY rf.sort_order
    """, (report_id,))
    linked_facts = cur.fetchall()
    sys.stdout.write("FACTS (%d linked via report_fact)\n" % len(linked_facts))
    for f in linked_facts:
        sys.stdout.write("  [%s] %s: %s" % (f["kind"], f["name"], f["value"]))
        if f["detail"]:
            sys.stdout.write(" — %s" % f["detail"])
        sys.stdout.write("\n")
    sys.stdout.write("\n")

    # ── Answers (1:N via report_answer) ──
    cur.execute("""
        SELECT a.* FROM answer a
        JOIN report_answer ra ON a.id=ra.answer_id
        WHERE ra.report_id=%s ORDER BY a.category, a.id
    """, (report_id,))
    linked_answers = cur.fetchall()
    known_count = sum(1 for a in linked_answers if a["status"] == "known")
    pending_count = sum(1 for a in linked_answers if a["status"] == "pending")
    sys.stdout.write("ANSWERS (%d linked via report_answer — %d known, %d pending)\n" % (len(linked_answers), known_count, pending_count))
    for a in linked_answers:
        marker = "OK" if a["status"] == "known" else ".." if a["status"] == "pending" else "??"
        sys.stdout.write("  %s [%s] %s: %s\n" % (marker, a["category"], a["question"], a["answer"] or ""))
    sys.stdout.write("\n")

    # ── Evidence (1:N via report_evidence) ──
    cur.execute("""
        SELECT ev.* FROM evidence ev
        JOIN report_evidence re ON ev.id=re.evidence_id
        WHERE re.report_id=%s ORDER BY ev.id
    """, (report_id,))
    linked_evidence = cur.fetchall()
    sys.stdout.write("EVIDENCE (%d linked via report_evidence)\n" % len(linked_evidence))
    for ev in linked_evidence:
        sys.stdout.write("  [%s] %s" % (ev["evidence_type"], ev["content"]))
        if ev["source_file"]:
            sys.stdout.write(" (%s:%d)" % (ev["source_file"], ev["source_line"]))
        sys.stdout.write("\n")
    sys.stdout.write("\n")

    # ── Rules (1:N via report_rule) ──
    cur.execute("""
        SELECT r.* FROM rule r
        JOIN report_rule rr ON r.id=rr.rule_id
        WHERE rr.report_id=%s ORDER BY r.confidence DESC
    """, (report_id,))
    linked_rules = cur.fetchall()
    sys.stdout.write("RULES (%d linked via report_rule)\n" % len(linked_rules))
    for r in linked_rules:
        sys.stdout.write("  [conf=%.2f] %s → %s\n" % (float(r["confidence"]), r["pattern"][:60], r["fix_action"][:60]))
    sys.stdout.write("\n")

    # ── Summary ──
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("THE STORY (assembled from %d pieces, 0 stored as text)\n" % total_refs)
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("Report #%d is a container of relationships.\n" % report_id)
    sys.stdout.write("Every entity is linked via a join table (1:N).\n")
    sys.stdout.write("The report engine walked the graph and reconstructed the story.\n")
    sys.stdout.write("No sentence was stored. Every word came from an entity or authority.\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
