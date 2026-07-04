#!/usr/bin/env python3
# [@GHOST]{[@file<migrate_questions.py>][@domain<Dom_Report>][@role<migration>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<migration>][@return<tuple3>][@orch<DiagnosticDB>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Phase 1 migration — finds every question across all MySQL databases, migrates them into diagnostic_kb.question with provenance, deduplicates by fingerprint.}
# [@CLASS]{QuestionMigrator}
# [@METHOD]{Run,MigrateAll,MigrateFromSource,Deduplicate,AnalyzeTypes,CreateTypes,ClassifyQuestions,read_state,set_config}
# [@FILEID]{core/Dom_Report/migrate_questions.py

import os
import sys
import hashlib
import mysql.connector

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class QuestionMigrator:
    """Migrates questions from all MySQL databases into diagnostic_kb.question.

    Phase 1 of the knowledge base migration:
    1. Find every question across all databases
    2. Fingerprint each (MD5 of normalized text)
    3. Insert with provenance (source_db, source_table, source_id)
    4. Deduplicate (same fingerprint = same question, increment occurrence_count)
    5. Analyze → discover natural types
    6. Classify each question

    self.state:
        state['stats']: migration counters
        state['sources']: list of source configs
        state['types_discovered']: discovered question types
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "stats": {"total_found": 0, "inserted": 0, "duplicates": 0, "skipped": 0},
            "sources": [],
            "types_discovered": [],
        }

    def Run(self, command, params=None):
        dispatch = {
            "migrate_all": self.MigrateAll,
            "analyze_types": self.AnalyzeTypes,
            "create_types": self.CreateTypes,
            "classify_questions": self.ClassifyQuestions,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

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

    def _fingerprint(self, text):
        normalized = " ".join(text.strip().lower().split())[:500]
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _is_real_question(self, text):
        if not text or len(text.strip()) < 5:
            return False
        stripped = text.strip()
        if not stripped[0].isalpha() and stripped[0] not in ("'", '"', "W", "w", "H", "h", "I", "i", "D", "d", "C", "c", "A", "a"):
            return False
        if len(stripped) > 2000:
            return False
        return True

    def MigrateAll(self, params):
        sources = [
            {"db": "chatgpt_export", "table": "Questions", "column": "question_text", "id_col": "id", "extra": {"category": "chatgpt"}},
            {"db": "questions", "table": "question", "column": "question_text", "id_col": "id", "extra": {"category": "structured"}},
            {"db": "vb_shared", "table": "anti_collapse_questions", "column": "question", "id_col": "id", "extra": {"category": "investigation"}},
            {"db": "vb_shared", "table": "anti_collapse_templates", "column": "question_template", "id_col": "id", "extra": {"category": "template"}},
            {"db": "vb_shared", "table": "graph_config", "column": "question_text", "id_col": "id", "extra": {"category": "graph"}},
            {"db": "vb_shared", "table": "know_questions", "column": "question", "id_col": "id", "extra": {"category": "knowledge"}},
        ]
        self.state["sources"] = sources
        for source in sources:
            self._migrate_from_source(source)
        return (1, dict(self.state["stats"]), None)

    def _migrate_from_source(self, source):
        conn = self._connect()
        cur = conn.cursor(dictionary=True)
        db_name = source["db"]
        tbl = source["table"]
        col = source["column"]
        id_col = source["id_col"]
        extra = source.get("extra", {})
        category = extra.get("category", "")
        cur.execute("SELECT `%s` as qtext, `%s` as qid FROM `%s`.`%s` WHERE `%s` IS NOT NULL AND `%s` != ''" % (
            col, id_col, db_name, tbl, col, col
        ))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        dest_conn = self._connect()
        dest_cur = dest_conn.cursor()
        for row in rows:
            text = row["qtext"]
            qid = row["qid"]
            if not self._is_real_question(text):
                self.state["stats"]["skipped"] += 1
                continue
            self.state["stats"]["total_found"] += 1
            fp = self._fingerprint(text)
            dest_cur.execute(
                "SELECT id, occurrence_count FROM diagnostic_kb.question WHERE fingerprint=%s",
                (fp,)
            )
            existing = dest_cur.fetchone()
            if existing:
                dest_cur.execute(
                    "UPDATE diagnostic_kb.question SET occurrence_count=occurrence_count+1 WHERE id=%s",
                    (existing[0],)
                )
                self.state["stats"]["duplicates"] += 1
            else:
                dest_cur.execute(
                    "INSERT INTO diagnostic_kb.question (question_text, fingerprint, category, source_db, source_table, source_id, source_column) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (text[:2000], fp, category, db_name, tbl, qid, col)
                )
                self.state["stats"]["inserted"] += 1
        dest_conn.commit()
        dest_cur.close()
        dest_conn.close()

    def AnalyzeTypes(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT category, COUNT(*) as cnt FROM diagnostic_kb.question GROUP BY category ORDER BY cnt DESC")
        by_category = cur.fetchall()
        cur.execute("SELECT SUBSTRING(question_text, 1, 1) as first_char, COUNT(*) as cnt FROM diagnostic_kb.question GROUP BY first_char ORDER BY cnt DESC LIMIT 10")
        by_first_char = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'What%'")
        what_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'How%'")
        how_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Why%'")
        why_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Is%'")
        is_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Does%'")
        does_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Have%'")
        have_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Can%'")
        can_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE question_text LIKE 'Are%'")
        are_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        analysis = {
            "by_source_category": by_category,
            "by_first_word": {
                "What": what_count, "How": how_count, "Why": why_count,
                "Is": is_count, "Does": does_count, "Have": have_count,
                "Can": can_count, "Are": are_count,
            },
        }
        self.state["types_discovered"] = analysis
        return (1, analysis, None)

    def CreateTypes(self, params):
        conn = self._connect()
        cur = conn.cursor()
        types = [
            ("what", "What-type questions — asking for definition or identification", 1),
            ("how", "How-type questions — asking for method or process", 2),
            ("why", "Why-type questions — asking for cause or reason", 3),
            ("is", "Is-type questions — asking for verification or confirmation", 4),
            ("does", "Does-type questions — asking for behavior or capability", 5),
            ("have", "Have-type questions — asking for existence or history", 6),
            ("can", "Can-type questions — asking for possibility or capability", 7),
            ("are", "Are-type questions — asking for state or property", 8),
            ("other", "Questions that don't fit a standard pattern", 99),
        ]
        for type_name, desc, order in types:
            cur.execute(
                "INSERT INTO diagnostic_kb.question_type (type_name, description, sort_order) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE description=VALUES(description), sort_order=VALUES(sort_order)",
                (type_name, desc, order)
            )
        conn.commit()
        cur.close()
        conn.close()
        return (1, len(types), None)

    def ClassifyQuestions(self, params):
        conn = self._connect()
        cur = conn.cursor()
        word_to_type = [
            ("What", 1), ("How", 2), ("Why", 3), ("Is", 4), ("Does", 5),
            ("Have", 6), ("Can", 7), ("Are", 8),
        ]
        classified = 0
        for word, type_id in word_to_type:
            cur.execute(
                "UPDATE diagnostic_kb.question SET type_id=%s WHERE type_id IS NULL AND question_text LIKE %s",
                (type_id, word + "%")
            )
            classified += cur.rowcount
        conn.commit()
        cur.execute(
            "UPDATE diagnostic_kb.question SET type_id=9 WHERE type_id IS NULL"
        )
        remaining = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return (1, {"classified_by_word": classified, "classified_as_other": remaining, "total": classified + remaining}, None)


def main():
    migrator = QuestionMigrator()
    sys.stdout.write("Phase 1: Question Migration\n")
    sys.stdout.write("=" * 60 + "\n\n")
    sys.stdout.write("Step 1: Migrating questions from all databases...\n")
    ok, stats, err = migrator.Run("migrate_all", {})
    sys.stdout.write("  Total found:    %d\n" % stats["total_found"])
    sys.stdout.write("  Inserted:       %d\n" % stats["inserted"])
    sys.stdout.write("  Duplicates:     %d\n" % stats["duplicates"])
    sys.stdout.write("  Skipped:        %d\n\n" % stats["skipped"])
    sys.stdout.write("Step 2: Analyzing question types...\n")
    ok, analysis, _ = migrator.Run("analyze_types", {})
    sys.stdout.write("  By source category:\n")
    for cat, cnt in analysis["by_source_category"]:
        sys.stdout.write("    %-20s %d\n" % (cat, cnt))
    sys.stdout.write("  By first word:\n")
    for word, cnt in sorted(analysis["by_first_word"].items(), key=lambda x: x[1], reverse=True):
        sys.stdout.write("    %-10s %d\n" % (word, cnt))
    sys.stdout.write("\nStep 3: Creating question types...\n")
    ok, type_count, _ = migrator.Run("create_types", {})
    sys.stdout.write("  Created %d types\n\n" % type_count)
    sys.stdout.write("Step 4: Classifying questions...\n")
    ok, class_stats, _ = migrator.Run("classify_questions", {})
    sys.stdout.write("  Classified by word: %d\n" % class_stats["classified_by_word"])
    sys.stdout.write("  Classified as other: %d\n" % class_stats["classified_as_other"])
    sys.stdout.write("  Total classified: %d\n\n" % class_stats["total"])
    conn = mysql.connector.connect(host="localhost", user="root", password="", unix_socket="/tmp/mysql.sock")
    cur = conn.cursor()
    cur.execute("SELECT qt.type_name, COUNT(q.id) as cnt FROM diagnostic_kb.question q LEFT JOIN diagnostic_kb.question_type qt ON q.type_id=qt.id GROUP BY qt.type_name ORDER BY cnt DESC")
    sys.stdout.write("Step 5: Final type distribution:\n")
    for type_name, cnt in cur.fetchall():
        sys.stdout.write("  %-15s %d\n" % (type_name or "NULL", cnt))
    cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM diagnostic_kb.question WHERE occurrence_count > 1")
    dupes = cur.fetchone()[0]
    cur.close()
    conn.close()
    sys.stdout.write("\n%s\n" % "=" * 60)
    sys.stdout.write("MIGRATION COMPLETE\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Total questions in diagnostic_kb: %d\n" % total)
    sys.stdout.write("Questions appearing in multiple sources: %d\n" % dupes)
    sys.stdout.write("Deduplication rate: %.1f%%\n" % (100.0 * dupes / total if total else 0))


if __name__ == "__main__":
    main()
