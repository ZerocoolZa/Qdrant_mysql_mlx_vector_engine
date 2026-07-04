#!/usr/bin/env python3
# [@GHOST]{[@file<demo_bcl_report.py>][@domain<Dom_Bcl>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<bcl-report>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<BclReportPacket>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Demo: generate a [@REPORT] BCL packet from the database, then resolve it back into the story. Proves the three-layer pipeline: DB stores truth, BCL transports references, report engine resolves the story.}
# [@FILEID]{core/Dom_Bcl/demo_bcl_report.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from BclReportPacket import BclReportPacket


def main():
    packet_builder = BclReportPacket()

    # ── Step 1: Find the latest report ──
    import mysql.connector
    conn = mysql.connector.connect(
        host="localhost", user="root", password="",
        database="diagnostic_kb", unix_socket="/tmp/mysql.sock"
    )
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, title FROM report ORDER BY id DESC LIMIT 1")
    report = cur.fetchone()
    cur.close()
    conn.close()

    if not report:
        sys.stdout.write("No reports found. Run demo_report_graph.py first.\n")
        return

    report_id = report["id"]

    # ════════════════════════════════════════════════════════════════
    # LAYER 2: BCL PACKET — transport references
    # ════════════════════════════════════════════════════════════════
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("LAYER 2: BCL PACKET (transport)\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("Generating [@REPORT] packet from report #%d...\n\n" % report_id)

    ok, packet, err = packet_builder.Run("generate", {"report_id": report_id})
    if not ok:
        sys.stdout.write("ERROR: %s\n" % str(err))
        return

    sys.stdout.write(packet)
    sys.stdout.write("\n\n")
    sys.stdout.write("The packet contains ONLY references (IDs).\n")
    sys.stdout.write("No error names, no severity names, no story text.\n")
    sys.stdout.write("Just numbers that point to the database.\n\n")

    # Show packet stats
    packet_bytes = len(packet.encode())
    packet_lines = packet.count("\n") + 1
    sys.stdout.write("Packet size: %d bytes, %d lines\n\n" % (packet_bytes, packet_lines))

    # ════════════════════════════════════════════════════════════════
    # LAYER 3: REPORT ENGINE — resolve references into story
    # ════════════════════════════════════════════════════════════════
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("LAYER 3: REPORT ENGINE (resolve)\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("Resolving BCL packet against diagnostic_kb...\n\n")

    ok, story, err = packet_builder.Run("resolve", {"packet": packet})
    if not ok:
        sys.stdout.write("ERROR: %s\n" % str(err))
        return

    # ── Print the resolved story ──
    sys.stdout.write("Title: %s\n\n" % story["title"])

    # Incident
    inc = story["incident"]
    if inc:
        sys.stdout.write("INCIDENT #%d\n" % inc["id"])
        sys.stdout.write("  Operation: %s\n" % inc["operation"])
        sys.stdout.write("  Result:    %s (status: %s, severity: %s level %d)\n" % (
            inc["result"], inc["status_name"], inc["severity_name"], inc["sev_level"]))
        sys.stdout.write("  Reason:    %s\n\n" % (inc["reason"] or ""))

    # Entities
    for entity_name, rows in story["entities"].items():
        if not rows:
            continue
        sys.stdout.write("%s (%d resolved)\n" % (entity_name.upper(), len(rows)))

        for row in rows:
            if entity_name == "error":
                sentence = "A %s %s %s error named '%s'. Status: %s. Severity: %s (level %d)." % (
                    row.get("domain") or "?", row.get("category") or "?",
                    row.get("type") or "?", row.get("name") or "?",
                    row.get("status") or "?", row.get("severity") or "?",
                    row.get("sev_level") or 0)
                sys.stdout.write("  #%d  %s\n" % (row["id"], sentence))
                if row.get("cause"):
                    sys.stdout.write("       Cause: %s\n" % row["cause"])
                if row.get("solution"):
                    sys.stdout.write("       Solution: %s\n" % row["solution"])
            elif entity_name == "problem":
                sys.stdout.write("  #%d  %s — %s (occurrences: %d)\n" % (
                    row["id"], row["problem"], row.get("description") or "", row["occurrence_count"]))
            elif entity_name == "cause":
                sys.stdout.write("  #%d  [%s] %s\n" % (row["id"], row["cause_type"], row["cause_text"]))
            elif entity_name == "fix":
                sys.stdout.write("  #%d  [%s] %s → %s\n" % (row["id"], row["fix_type"], row["fix_action"], row["result"]))
            elif entity_name == "prevention":
                sys.stdout.write("  #%d  [%s] %s\n" % (row["id"], row["prevention_type"], row["rule_text"]))
            elif entity_name == "fact":
                sys.stdout.write("  #%d  [%s] %s: %s\n" % (row["id"], row["kind"], row["name"], row["value"]))
            elif entity_name == "answer":
                marker = "OK" if row["status"] == "known" else ".."
                sys.stdout.write("  #%d  %s [%s] %s: %s\n" % (row["id"], marker, row["category"], row["question"], row.get("answer") or ""))
            elif entity_name == "evidence":
                sys.stdout.write("  #%d  [%s] %s" % (row["id"], row["evidence_type"], row["content"]))
                if row.get("source_file"):
                    sys.stdout.write(" (%s:%d)" % (row["source_file"], row["source_line"]))
                sys.stdout.write("\n")
            elif entity_name == "rule":
                sys.stdout.write("  #%d  [conf=%.2f] %s → %s\n" % (
                    row["id"], float(row["confidence"]), row["pattern"][:50], row["fix_action"][:50]))
        sys.stdout.write("\n")

    # ── Summary ──
    total_entities = sum(len(rows) for rows in story["entities"].values())
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("THE THREE-LAYER PIPELINE\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("  Layer 1: Database     → stored canonical truth (32 tables)\n")
    sys.stdout.write("  Layer 2: BCL packet   → transported %d references (%d bytes)\n" % (total_entities, packet_bytes))
    sys.stdout.write("  Layer 3: Report engine → resolved %d entities into story\n" % total_entities)
    sys.stdout.write("\n")
    sys.stdout.write("The packet carried only IDs.\n")
    sys.stdout.write("The database provided the facts.\n")
    sys.stdout.write("The report engine assembled the story.\n")
    sys.stdout.write("Three layers. Three responsibilities. Zero duplication.\n")


if __name__ == "__main__":
    main()
