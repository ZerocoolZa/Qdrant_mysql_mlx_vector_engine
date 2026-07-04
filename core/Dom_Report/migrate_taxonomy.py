#!/usr/bin/env python3
# [@GHOST]{[@file<migrate_taxonomy.py>][@domain<Dom_Report>][@role<migration>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<migration>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Populates the universal type, category, and domain tables from all existing MySQL databases. One table for all types, one for all categories, one for all domains — each with a 'kind' column to distinguish what they classify.}
# [@CLASS]{TaxonomyMigrator}
# [@METHOD]{Run,MigrateAll,MigrateTypes,MigrateCategories,MigrateDomains,read_state,set_config}
# [@FILEID]{core/Dom_Report/migrate_taxonomy.py

import os
import sys
import mysql.connector

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TaxonomyMigrator:
    """Populates the universal type, category, and domain tables.

    Three universal tables, each with a 'kind' column:
    - type(kind, name, description)     — ALL types
    - category(kind, name, description)  — ALL categories
    - domain(kind, name, description)    — ALL domains

    The 'kind' column distinguishes what the entry classifies:
    e.g. type(kind='question', name='what'), type(kind='error', name='AttributeError')

    self.state:
        state['stats']: migration counters
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "stats": {"types": 0, "categories": 0, "domains": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "migrate_all": self.MigrateAll,
            "migrate_types": self.MigrateTypes,
            "migrate_categories": self.MigrateCategories,
            "migrate_domains": self.MigrateDomains,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        return (1, dict(self.state), None)

    def _connect(self):
        return mysql.connector.connect(
            host="localhost", user="root", password="",
            unix_socket="/tmp/mysql.sock"
        )

    def _insert_type(self, cur, kind, name, description="", sort_order=0):
        cur.execute(
            "INSERT IGNORE INTO diagnostic_kb.type (kind, name, description, sort_order) VALUES (%s, %s, %s, %s)",
            (kind, name, description, sort_order)
        )
        return cur.rowcount

    def _insert_category(self, cur, kind, name, description="", sort_order=0):
        cur.execute(
            "INSERT IGNORE INTO diagnostic_kb.category (kind, name, description, sort_order) VALUES (%s, %s, %s, %s)",
            (kind, name, description, sort_order)
        )
        return cur.rowcount

    def _insert_domain(self, cur, kind, name, description="", sort_order=0):
        cur.execute(
            "INSERT IGNORE INTO diagnostic_kb.domain (kind, name, description, sort_order) VALUES (%s, %s, %s, %s)",
            (kind, name, description, sort_order)
        )
        return cur.rowcount

    def MigrateAll(self, params):
        self.MigrateTypes(params)
        self.MigrateCategories(params)
        self.MigrateDomains(params)
        return (1, dict(self.state["stats"]), None)

    def MigrateTypes(self, params):
        conn = self._connect()
        cur = conn.cursor()
        count = 0

        # ── Question types (from our existing question_type table) ──
        cur.execute("SELECT type_name, description, sort_order FROM diagnostic_kb.question_type")
        for name, desc, order in cur.fetchall():
            count += self._insert_type(cur, "question", name, desc or "", order)

        # ── Question types from chatgpt_export ──
        cur.execute("SELECT DISTINCT question_type FROM chatgpt_export.Questions WHERE question_type IS NOT NULL AND question_type != ''")
        for (qt,) in cur.fetchall():
            count += self._insert_type(cur, "question_source", qt, "Source type from chatgpt_export")

        # ── Error types ──
        cur.execute("SELECT DISTINCT error_type FROM vb_shared.error_knowledge WHERE error_type IS NOT NULL AND error_type != ''")
        for (et,) in cur.fetchall():
            count += self._insert_type(cur, "error", et, "Error type from vb_shared.error_knowledge")

        # ── Anti-collapse question types ──
        cur.execute("SELECT DISTINCT question_type FROM vb_shared.anti_collapse_questions WHERE question_type IS NOT NULL AND question_type != ''")
        for (qt,) in cur.fetchall():
            count += self._insert_type(cur, "investigation", qt, "Investigation question type")

        # ── File types ──
        for db_name, tbl in [("qa_system", "files"), ("token_registry", "files")]:
            cur.execute("SELECT DISTINCT file_type FROM `%s`.`%s` WHERE file_type IS NOT NULL AND file_type != ''" % (db_name, tbl))
            for (ft,) in cur.fetchall():
                count += self._insert_type(cur, "file", ft, "File type from %s.%s" % (db_name, tbl))

        # ── Execution event types ──
        cur.execute("SELECT DISTINCT event_type FROM agent_os.event_log WHERE event_type IS NOT NULL AND event_type != ''")
        for (et,) in cur.fetchall():
            count += self._insert_type(cur, "event", et, "Event type from agent_os.event_log")

        # ── Edge types (graph) ──
        for db_name, tbl in [("vb_shared", "graph_edges"), ("token_registry", "token_graph_edges")]:
            cur.execute("SELECT DISTINCT edge_type FROM `%s`.`%s` WHERE edge_type IS NOT NULL AND edge_type != ''" % (db_name, tbl))
            for (et,) in cur.fetchall():
                count += self._insert_type(cur, "edge", et, "Edge type from %s.%s" % (db_name, tbl))

        # ── Node types (graph) ──
        cur.execute("SELECT DISTINCT node_type FROM vb_shared.graph_nodes WHERE node_type IS NOT NULL AND node_type != ''")
        for (nt,) in cur.fetchall():
            count += self._insert_type(cur, "node", nt, "Node type from vb_shared.graph_nodes")

        # ── Operation types ──
        cur.execute("SELECT DISTINCT operation_type FROM token_registry.file_operations WHERE operation_type IS NOT NULL AND operation_type != ''")
        for (ot,) in cur.fetchall():
            count += self._insert_type(cur, "operation", ot, "Operation type from token_registry.file_operations")

        # ── Computational unit types ──
        cur.execute("SELECT DISTINCT unit_type FROM token_registry.computational_units WHERE unit_type IS NOT NULL AND unit_type != ''")
        for (ut,) in cur.fetchall():
            count += self._insert_type(cur, "unit", ut, "Unit type from token_registry.computational_units")

        # ── GUI token types ──
        cur.execute("SELECT DISTINCT gui_type FROM vb_shared.gui_tokens WHERE gui_type IS NOT NULL AND gui_type != ''")
        for (gt,) in cur.fetchall():
            count += self._insert_type(cur, "gui", gt, "GUI type from vb_shared.gui_tokens")

        # ── Fix types (from our own schema) ──
        for ft in ["auto", "manual", "recommended"]:
            count += self._insert_type(cur, "fix", ft, "Fix type")

        # ── Cause types ──
        for ct in ["root", "contributing", "runtime", "behavioral"]:
            count += self._insert_type(cur, "cause", ct, "Cause type")

        # ── Prevention types ──
        for pt in ["guard", "validation", "detection", "process"]:
            count += self._insert_type(cur, "prevention", pt, "Prevention type")

        # ── Incident result types ──
        for rt in ["ok", "fail", "partial"]:
            count += self._insert_type(cur, "result", rt, "Incident result type")

        # ── Answer status types ──
        for ast in ["known", "unknown", "pending", "n/a"]:
            count += self._insert_type(cur, "answer_status", ast, "Answer status type")

        conn.commit()
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.type")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.state["stats"]["types"] = total
        return (1, {"inserted": count, "total": total}, None)

    def MigrateCategories(self, params):
        conn = self._connect()
        cur = conn.cursor()
        count = 0

        # ── Question categories from vb_shared.know_questions ──
        cur.execute("SELECT category, COUNT(*) as cnt FROM vb_shared.know_questions WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY cnt DESC")
        order = 0
        for cat, cnt in cur.fetchall():
            order += 1
            count += self._insert_category(cur, "question", cat, "Question category (%d occurrences)" % cnt, order)

        # ── Question families from questions.question ──
        cur.execute("SELECT family, COUNT(*) as cnt FROM questions.question GROUP BY family ORDER BY cnt DESC")
        for fam, cnt in cur.fetchall():
            count += self._insert_category(cur, "question_family", fam, "Question family (%d occurrences)" % cnt)

        # ── File categories from vb_shared.categories ──
        cur.execute("SELECT name, description FROM vb_shared.categories")
        for name, desc in cur.fetchall():
            count += self._insert_category(cur, "file", name, desc or "")

        # ── Learned rule categories from vb_shared.learned_rules ──
        cur.execute("SELECT category, COUNT(*) as cnt FROM vb_shared.learned_rules WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY cnt DESC")
        for cat, cnt in cur.fetchall():
            count += self._insert_category(cur, "rule", cat, "Rule category (%d occurrences)" % cnt)

        # ── Lesson dimensions from vb_shared.know_lessons ──
        cur.execute("SELECT dimension, COUNT(*) as cnt FROM vb_shared.know_lessons WHERE dimension IS NOT NULL AND dimension != '' GROUP BY dimension ORDER BY cnt DESC")
        for dim, cnt in cur.fetchall():
            count += self._insert_category(cur, "lesson", dim, "Lesson dimension (%d occurrences)" % cnt)

        # ── Lesson issue types ──
        cur.execute("SELECT issue_type, COUNT(*) as cnt FROM vb_shared.know_lessons WHERE issue_type IS NOT NULL AND issue_type != '' GROUP BY issue_type ORDER BY cnt DESC")
        for it, cnt in cur.fetchall():
            count += self._insert_category(cur, "lesson_issue", it, "Lesson issue type (%d occurrences)" % cnt)

        # ── Common text categories ──
        cur.execute("SELECT DISTINCT category FROM vb_shared.common_text WHERE category IS NOT NULL AND category != ''")
        for (cat,) in cur.fetchall():
            count += self._insert_category(cur, "text", cat, "Common text category")

        # ── Help text categories ──
        cur.execute("SELECT DISTINCT category FROM vb_shared.help_text WHERE category IS NOT NULL AND category != ''")
        for (cat,) in cur.fetchall():
            count += self._insert_category(cur, "help", cat, "Help text category")

        # ── Instruction categories ──
        cur.execute("SELECT DISTINCT category FROM vb_shared.instructions WHERE category IS NOT NULL AND category != ''")
        for (cat,) in cur.fetchall():
            count += self._insert_category(cur, "instruction", cat, "Instruction category")

        # ── Treasure categories ──
        cur.execute("SELECT DISTINCT category FROM treasure_trove.treasures WHERE category IS NOT NULL AND category != ''")
        for (cat,) in cur.fetchall():
            count += self._insert_category(cur, "treasure", cat, "Treasure category")

        # ── Diagnostic categories (from our Config) ──
        for cat in ["identity", "outcome", "cause", "history", "repair", "prevention"]:
            count += self._insert_category(cur, "diagnostic", cat, "Diagnostic category")

        conn.commit()
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.category")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.state["stats"]["categories"] = total
        return (1, {"inserted": count, "total": total}, None)

    def MigrateDomains(self, params):
        conn = self._connect()
        cur = conn.cursor()
        count = 0

        # ── Software domains from vb_shared.domains ──
        cur.execute("SELECT name, description FROM vb_shared.domains")
        order = 0
        for name, desc in cur.fetchall():
            order += 1
            count += self._insert_domain(cur, "software", name, desc or "", order)

        # ── Question domains from vb_shared.know_questions categories that look like domains ──
        domain_like = ["database", "ai", "python", "filesystem", "network", "security", "web", "ui", "testing", "performance", "architecture"]
        for d in domain_like:
            count += self._insert_domain(cur, "question", d, "Domain inferred from question categories")

        # ── Error knowledge domains ──
        cur.execute("SELECT DISTINCT domain FROM vb_shared.error_knowledge WHERE domain IS NOT NULL AND domain != ''")
        for (d,) in cur.fetchall():
            count += self._insert_domain(cur, "error", d, "Error domain from vb_shared.error_knowledge")

        # ── Graph config domains ──
        cur.execute("SELECT DISTINCT domain FROM vb_shared.graph_config WHERE domain IS NOT NULL AND domain != ''")
        for (d,) in cur.fetchall():
            count += self._insert_domain(cur, "graph", d, "Graph domain from vb_shared.graph_config")

        # ── Computation unit domains ──
        cur.execute("SELECT DISTINCT domain FROM graph_computation_units.computation_units WHERE domain IS NOT NULL AND domain != ''")
        for (d,) in cur.fetchall():
            count += self._insert_domain(cur, "computation", d, "Computation domain")

        # ── VB class domains ──
        cur.execute("SELECT DISTINCT domain FROM vb_code_test.vb_classes WHERE domain IS NOT NULL AND domain != ''")
        for (d,) in cur.fetchall():
            count += self._insert_domain(cur, "vbclass", d, "VB class domain")

        # ── C class domains ──
        cur.execute("SELECT DISTINCT domain FROM vb_shared.c_classes WHERE domain IS NOT NULL AND domain != ''")
        for (d,) in cur.fetchall():
            count += self._insert_domain(cur, "cclass", d, "C class domain")

        conn.commit()
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.domain")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.state["stats"]["domains"] = total
        return (1, {"inserted": count, "total": total}, None)


def main():
    migrator = TaxonomyMigrator()
    sys.stdout.write("Universal Taxonomy Migration\n")
    sys.stdout.write("=" * 60 + "\n\n")

    sys.stdout.write("Step 1: Migrating types...\n")
    ok, type_stats, _ = migrator.Run("migrate_types", {})
    sys.stdout.write("  Inserted: %d, Total types: %d\n\n" % (type_stats["inserted"], type_stats["total"]))

    sys.stdout.write("Step 2: Migrating categories...\n")
    ok, cat_stats, _ = migrator.Run("migrate_categories", {})
    sys.stdout.write("  Inserted: %d, Total categories: %d\n\n" % (cat_stats["inserted"], cat_stats["total"]))

    sys.stdout.write("Step 3: Migrating domains...\n")
    ok, dom_stats, _ = migrator.Run("migrate_domains", {})
    sys.stdout.write("  Inserted: %d, Total domains: %d\n\n" % (dom_stats["inserted"], dom_stats["total"]))

    conn = mysql.connector.connect(host="localhost", user="root", password="", unix_socket="/tmp/mysql.sock")
    cur = conn.cursor()

    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("TYPE DISTRIBUTION (by kind)\n")
    sys.stdout.write("=" * 60 + "\n")
    cur.execute("SELECT kind, COUNT(*) as cnt FROM diagnostic_kb.type GROUP BY kind ORDER BY cnt DESC")
    for kind, cnt in cur.fetchall():
        sys.stdout.write("  %-25s %d\n" % (kind, cnt))

    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("CATEGORY DISTRIBUTION (by kind)\n")
    sys.stdout.write("=" * 60 + "\n")
    cur.execute("SELECT kind, COUNT(*) as cnt FROM diagnostic_kb.category GROUP BY kind ORDER BY cnt DESC")
    for kind, cnt in cur.fetchall():
        sys.stdout.write("  %-25s %d\n" % (kind, cnt))

    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("DOMAIN DISTRIBUTION (by kind)\n")
    sys.stdout.write("=" * 60 + "\n")
    cur.execute("SELECT kind, COUNT(*) as cnt FROM diagnostic_kb.domain GROUP BY kind ORDER BY cnt DESC")
    for kind, cnt in cur.fetchall():
        sys.stdout.write("  %-25s %d\n" % (kind, cnt))

    cur.execute("SELECT COUNT(*) FROM diagnostic_kb.type")
    types_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM diagnostic_kb.category")
    cats_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM diagnostic_kb.domain")
    doms_total = cur.fetchone()[0]
    cur.close()
    conn.close()

    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("TAXONOMY MIGRATION COMPLETE\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Total types:      %d (across all kinds)\n" % types_total)
    sys.stdout.write("Total categories: %d (across all kinds)\n" % cats_total)
    sys.stdout.write("Total domains:    %d (across all kinds)\n" % doms_total)
    sys.stdout.write("Total taxonomy:   %d entries\n" % (types_total + cats_total + doms_total))


if __name__ == "__main__":
    main()
