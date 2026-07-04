#!/usr/bin/env python3
# [@GHOST]{[@file<QuestionChecker.py>][@domain<Dom_Db>][@role<question_audit>][@auth<devin>][@date<2026-07-04>][@ver<1.0.0>][@session<question-cleanup>]}
# [@VBSTYLE]{[@auth<devin>][@role<question_audit>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Audits 141K questions in laws.question — finds duplicates, garbage, orphans, missing classifications, stale DELETE verdicts.}
# [@CLASS]{QuestionChecker}
# [@METHOD]{Run,CheckAll,CheckDuplicates,CheckGarbage,CheckMissing,CheckOrphans,CheckStaleDeletes,CheckNearDuplicates,GenerateReport,ApplyCleanup,read_state,set_config}
# [@FILEID]{core/Dom_Db/QuestionChecker.py}

import os
import sys
import hashlib
import re
import mysql.connector
from typing import Tuple, List, Dict, Any, Optional

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


GARBAGE_PATTERNS = {
    "base64": re.compile(r'^[A-Za-z0-9+/=]{50,}$'),
    "hex_string": re.compile(r'^[0-9a-fA-F]{40,}$'),
    "uuid_only": re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I),
    "url_only": re.compile(r'^https?://\S+$'),
    "file_path_only": re.compile(r'^/[\w/.-]+\.\w+$'),
    "numeric_only": re.compile(r'^[\d.,\s]+$'),
    "single_word_repeat": re.compile(r'^(\w+)\s+\1\s+\1', re.I),
}

NON_PRINTABLE = re.compile(r'[^\x20-\x7E\n\r\t]')

QUESTION_WORDS = ["what", "how", "why", "is", "does", "have", "can", "are", "who", "when", "where", "which", "will", "should", "could", "would", "do", "did", "was", "were", "has", "had", "may", "might", "must", "shall"]


class QuestionChecker:
    """Audits the laws.question table for quality issues.

    Checks:
        1. Exact duplicates (same normalized text, different fingerprints)
        2. Near-duplicates (Levenshtein distance <= 2 within same type)
        3. Garbage questions (base64, hex, URLs, paths, numeric-only, non-printable)
        4. Missing classifications (NULL type, category, domain)
        5. Orphaned questions (no QuestionReview entry)
        6. Stale DELETE verdicts (QuestionReview says DELETE but row still active)
        7. Too short (< 10 chars) or too long (> 2000 chars)
        8. Non-English / non-question text (no question mark, no question word)

    self.state:
        state['db_config']: MySQL connection config
        state['report']: last audit report dict
        state['dry_run']: if True, do not apply cleanup
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_config": {
                "host": "localhost",
                "user": "root",
                "password": "",
                "database": "laws",
                "unix_socket": "/tmp/mysql.sock",
            },
            "report": {},
            "dry_run": True,
        }

    def Run(self, command, params=None):
        dispatch = {
            "check_all": self.CheckAll,
            "check_duplicates": self.CheckDuplicates,
            "check_garbage": self.CheckGarbage,
            "check_missing": self.CheckMissing,
            "check_orphans": self.CheckOrphans,
            "check_stale_deletes": self.CheckStaleDeletes,
            "check_near_duplicates": self.CheckNearDuplicates,
            "generate_report": self.GenerateReport,
            "apply_cleanup": self.ApplyCleanup,
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
        return mysql.connector.connect(**self.state["db_config"])

    def _fingerprint(self, text):
        normalized = " ".join(text.strip().lower().split())[:500]
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _levenshtein(self, s1, s2):
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    def _classify_garbage(self, text):
        if not text:
            return "empty"
        stripped = text.strip()
        if len(stripped) < 5:
            return "too_short"
        if len(stripped) > 2000:
            return "too_long"
        for name, pattern in GARBAGE_PATTERNS.items():
            if pattern.match(stripped):
                return name
        if NON_PRINTABLE.search(stripped):
            return "non_printable"
        lower = stripped.lower()
        has_question_word = any(lower.startswith(w + " ") or lower.startswith(w + "?") for w in QUESTION_WORDS)
        has_question_mark = "?" in stripped
        if not has_question_word and not has_question_mark and len(stripped) < 30:
            return "not_a_question"
        return None

    def CheckAll(self, params):
        report = {
            "total_questions": 0,
            "duplicates": {},
            "garbage": {},
            "missing": {},
            "orphans": {},
            "stale_deletes": {},
            "near_duplicates": {},
        }
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM question")
        report["total_questions"] = cur.fetchone()[0]

        ok, dup_data, err = self.CheckDuplicates({})
        if err:
            report["duplicates"] = {"error": err}
        else:
            report["duplicates"] = dup_data

        ok, garbage_data, err = self.CheckGarbage({})
        if err:
            report["garbage"] = {"error": err}
        else:
            report["garbage"] = garbage_data

        ok, missing_data, err = self.CheckMissing({})
        if err:
            report["missing"] = {"error": err}
        else:
            report["missing"] = missing_data

        ok, orphan_data, err = self.CheckOrphans({})
        if err:
            report["orphans"] = {"error": err}
        else:
            report["orphans"] = orphan_data

        ok, stale_data, err = self.CheckStaleDeletes({})
        if err:
            report["stale_deletes"] = {"error": err}
        else:
            report["stale_deletes"] = stale_data

        cur.close()
        conn.close()

        self.state["report"] = report
        return (1, report, None)

    def CheckDuplicates(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT fingerprint, COUNT(*) as cnt, GROUP_CONCAT(id ORDER BY id SEPARATOR ',') as ids
            FROM question
            GROUP BY fingerprint
            HAVING cnt > 1
            ORDER BY cnt DESC
            LIMIT 100
        """)
        exact_dupes = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM (SELECT fingerprint FROM question GROUP BY fingerprint HAVING COUNT(*) > 1) t")
        total_duped_fps = cur.fetchone()[0]
        cur.execute("SELECT SUM(cnt - 1) FROM (SELECT fingerprint, COUNT(*) as cnt FROM question GROUP BY fingerprint HAVING cnt > 1) t")
        redundant_rows = cur.fetchone()[0] or 0
        cur.execute("""
            SELECT questionText, COUNT(*) as cnt
            FROM question
            GROUP BY questionText
            HAVING cnt > 1
            ORDER BY cnt DESC
            LIMIT 50
        """)
        same_text = cur.fetchall()
        cur.close()
        conn.close()
        result = {
            "duplicate_fingerprints": total_duped_fps,
            "redundant_rows": redundant_rows,
            "top_duplicates": [(r[0], r[1], r[2][:200] if r[2] else "") for r in exact_dupes[:20]],
            "same_text_groups": len(same_text),
            "same_text_samples": [(r[0][:80], r[1]) for r in same_text[:10]],
        }
        return (1, result, None)

    def CheckGarbage(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id, questionText FROM question")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        categories = {}
        garbage_ids = []
        for qid, text in rows:
            cat = self._classify_garbage(text)
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
                garbage_ids.append((qid, cat, (text or "")[:80]))
        result = {
            "total_garbage": len(garbage_ids),
            "by_category": categories,
            "samples": garbage_ids[:30],
        }
        return (1, result, None)

    def CheckMissing(self, params):
        conn = self._connect()
        cur = conn.cursor()
        checks = {
            "null_type": "SELECT COUNT(*) FROM question WHERE question_type_id IS NULL",
            "null_category": "SELECT COUNT(*) FROM question WHERE categoryId IS NULL",
            "null_domain": "SELECT COUNT(*) FROM question WHERE domainId IS NULL",
            "null_confidence": "SELECT COUNT(*) FROM question WHERE confidenceId IS NULL",
            "not_answered": "SELECT COUNT(*) FROM question WHERE isAnswered = 0",
            "inactive": "SELECT COUNT(*) FROM question WHERE isActive = 0",
        }
        results = {}
        for name, query in checks.items():
            cur.execute(query)
            results[name] = cur.fetchone()[0]
        cur.execute("""
            SELECT question_type_id, COUNT(*) as cnt
            FROM question
            WHERE question_type_id IS NOT NULL
            GROUP BY question_type_id
            ORDER BY cnt DESC
        """)
        type_dist = cur.fetchall()
        cur.close()
        conn.close()
        results["type_distribution"] = type_dist
        return (1, results, None)

    def CheckOrphans(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM question q
            LEFT JOIN QuestionReview qr ON q.id = qr.questionId
            WHERE qr.questionId IS NULL
        """)
        orphan_count = cur.fetchone()[0]
        cur.execute("""
            SELECT q.id, LEFT(q.questionText, 80)
            FROM question q
            LEFT JOIN QuestionReview qr ON q.id = qr.questionId
            WHERE qr.questionId IS NULL
            LIMIT 20
        """)
        samples = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM QuestionReview qr LEFT JOIN question q ON qr.questionId = q.id WHERE q.id IS NULL")
        ghost_reviews = cur.fetchone()[0]
        cur.close()
        conn.close()
        result = {
            "questions_without_review": orphan_count,
            "reviews_without_question": ghost_reviews,
            "samples": samples,
        }
        return (1, result, None)

    def CheckStaleDeletes(self, params):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM question q
            JOIN QuestionReview qr ON q.id = qr.questionId
            WHERE qr.verdict = 'DELETE' AND q.isActive = 1
        """)
        stale_count = cur.fetchone()[0]
        cur.execute("""
            SELECT q.id, LEFT(q.questionText, 80), qr.category, qr.reason
            FROM question q
            JOIN QuestionReview qr ON q.id = qr.questionId
            WHERE qr.verdict = 'DELETE' AND q.isActive = 1
            LIMIT 30
        """)
        samples = cur.fetchall()
        cur.execute("""
            SELECT qr.category, COUNT(*) as cnt
            FROM question q
            JOIN QuestionReview qr ON q.id = qr.questionId
            WHERE qr.verdict = 'DELETE' AND q.isActive = 1
            GROUP BY qr.category
            ORDER BY cnt DESC
        """)
        by_category = cur.fetchall()
        cur.close()
        conn.close()
        result = {
            "stale_delete_count": stale_count,
            "by_category": by_category,
            "samples": samples,
        }
        return (1, result, None)

    def CheckNearDuplicates(self, params):
        sample_limit = self._p(params, "sample_limit", 5000)
        max_distance = self._p(params, "max_distance", 2)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, questionText, question_type_id
            FROM question
            WHERE question_type_id IS NOT NULL
            ORDER BY question_type_id, id
            LIMIT %s
        """, (sample_limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        by_type = {}
        for qid, text, qtype in rows:
            by_type.setdefault(qtype, []).append((qid, text or ""))
        near_dups = []
        for qtype, questions in by_type.items():
            for i in range(len(questions)):
                id_a, text_a = questions[i]
                norm_a = " ".join(text_a.lower().split())[:200]
                for j in range(i + 1, min(i + 50, len(questions))):
                    id_b, text_b = questions[j]
                    norm_b = " ".join(text_b.lower().split())[:200]
                    if norm_a == norm_b:
                        continue
                    dist = self._levenshtein(norm_a, norm_b)
                    if dist <= max_distance:
                        near_dups.append((id_a, id_b, dist, text_a[:60], text_b[:60]))
                        if len(near_dups) >= 100:
                            break
                if len(near_dups) >= 100:
                    break
            if len(near_dups) >= 100:
                break
        result = {
            "sampled": len(rows),
            "near_duplicate_pairs": len(near_dups),
            "max_distance": max_distance,
            "samples": near_dups[:20],
        }
        return (1, result, None)

    def GenerateReport(self, params):
        report = self.state.get("report", {})
        if not report:
            ok, data, err = self.CheckAll({})
            if err:
                return (0, None, err)
            report = data
        lines = []
        lines.append("=" * 70)
        lines.append("QUESTION TABLE AUDIT REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Total questions: %d" % report.get("total_questions", 0))
        lines.append("")
        dupes = report.get("duplicates", {})
        if dupes and "error" not in dupes:
            lines.append("-" * 40)
            lines.append("DUPLICATES")
            lines.append("-" * 40)
            lines.append("  Duplicate fingerprints: %d" % dupes.get("duplicate_fingerprints", 0))
            lines.append("  Redundant rows: %d" % dupes.get("redundant_rows", 0))
            lines.append("  Same-text groups: %d" % dupes.get("same_text_groups", 0))
            if dupes.get("same_text_samples"):
                lines.append("  Sample same-text:")
                for text, cnt in dupes["same_text_samples"][:5]:
                    lines.append("    (%dx) %s" % (cnt, text))
            lines.append("")
        garbage = report.get("garbage", {})
        if garbage and "error" not in garbage:
            lines.append("-" * 40)
            lines.append("GARBAGE / NON-QUESTIONS")
            lines.append("-" * 40)
            lines.append("  Total garbage: %d" % garbage.get("total_garbage", 0))
            lines.append("  By category:")
            for cat, cnt in sorted(garbage.get("by_category", {}).items(), key=lambda x: x[1], reverse=True):
                lines.append("    %-20s %d" % (cat, cnt))
            if garbage.get("samples"):
                lines.append("  Samples:")
                for qid, cat, text in garbage["samples"][:10]:
                    lines.append("    id=%-7d [%s] %s" % (qid, cat, text))
            lines.append("")
        missing = report.get("missing", {})
        if missing and "error" not in missing:
            lines.append("-" * 40)
            lines.append("MISSING CLASSIFICATIONS")
            lines.append("-" * 40)
            lines.append("  NULL type:       %d" % missing.get("null_type", 0))
            lines.append("  NULL category:   %d" % missing.get("null_category", 0))
            lines.append("  NULL domain:     %d" % missing.get("null_domain", 0))
            lines.append("  NULL confidence: %d" % missing.get("null_confidence", 0))
            lines.append("  Not answered:    %d" % missing.get("not_answered", 0))
            lines.append("  Inactive:        %d" % missing.get("inactive", 0))
            lines.append("  Type distribution:")
            for type_id, cnt in missing.get("type_distribution", []):
                lines.append("    type_id=%s  count=%d" % (type_id, cnt))
            lines.append("")
        orphans = report.get("orphans", {})
        if orphans and "error" not in orphans:
            lines.append("-" * 40)
            lines.append("ORPHANS")
            lines.append("-" * 40)
            lines.append("  Questions without review: %d" % orphans.get("questions_without_review", 0))
            lines.append("  Reviews without question: %d" % orphans.get("reviews_without_question", 0))
            if orphans.get("samples"):
                lines.append("  Sample orphans:")
                for qid, text in orphans["samples"][:5]:
                    lines.append("    id=%-7d %s" % (qid, text))
            lines.append("")
        stale = report.get("stale_deletes", {})
        if stale and "error" not in stale:
            lines.append("-" * 40)
            lines.append("STALE DELETE VERDICTS")
            lines.append("-" * 40)
            lines.append("  Active questions marked DELETE: %d" % stale.get("stale_delete_count", 0))
            lines.append("  By category:")
            for cat, cnt in stale.get("by_category", []):
                lines.append("    %-20s %d" % (cat, cnt))
            if stale.get("samples"):
                lines.append("  Samples:")
                for qid, text, cat, reason in stale["samples"][:10]:
                    lines.append("    id=%-7d [%s] %s | %s" % (qid, cat, text, reason))
            lines.append("")
        lines.append("=" * 70)
        lines.append("END REPORT")
        lines.append("=" * 70)
        text = "\n".join(lines)
        return (1, text, None)

    def ApplyCleanup(self, params):
        if self.state.get("dry_run", True):
            return (0, None, ("DRY_RUN", "Set dry_run=False in state to apply cleanup", 0))
        actions = self._p(params, "actions", ["deactivate_stale_deletes", "delete_garbage", "delete_orphan_reviews"])
        conn = self._connect()
        cur = conn.cursor()
        results = {}
        if "deactivate_stale_deletes" in actions:
            cur.execute("""
                UPDATE question q
                JOIN QuestionReview qr ON q.id = qr.questionId
                SET q.isActive = 0
                WHERE qr.verdict = 'DELETE' AND q.isActive = 1
            """)
            results["deactivated_stale_deletes"] = cur.rowcount
            conn.commit()
        if "delete_garbage" in actions:
            ok, garbage_data, err = self.CheckGarbage({})
            if not err and garbage_data:
                garbage_ids = [s[0] for s in garbage_data.get("samples", [])]
                if garbage_ids:
                    placeholders = ",".join(["%s"] * len(garbage_ids))
                    cur.execute("UPDATE question SET isActive=0 WHERE id IN (%s)" % placeholders, garbage_ids)
                    results["deactivated_garbage"] = cur.rowcount
                    conn.commit()
        if "delete_orphan_reviews" in actions:
            cur.execute("""
                DELETE qr FROM QuestionReview qr
                LEFT JOIN question q ON qr.questionId = q.id
                WHERE q.id IS NULL
            """)
            results["deleted_orphan_reviews"] = cur.rowcount
            conn.commit()
        cur.close()
        conn.close()
        return (1, results, None)


def Main():
    checker = QuestionChecker()
    sys.stdout.write("Question Table Auditor\n")
    sys.stdout.write("=" * 60 + "\n\n")
    sys.stdout.write("Running full audit on laws.question...\n\n")
    ok, report, err = checker.Run("check_all", {})
    if err:
        sys.stdout.write("ERROR: %s\n" % str(err))
        return 1
    ok, text, err = checker.Run("generate_report", {})
    if err:
        sys.stdout.write("ERROR generating report: %s\n" % str(err))
        return 1
    sys.stdout.write(text + "\n")
    sys.stdout.write("\nChecking near-duplicates (sample of 5000)...\n")
    ok, near_data, err = checker.Run("check_near_duplicates", {"sample_limit": 5000, "max_distance": 2})
    if not err:
        sys.stdout.write("  Sampled: %d\n" % near_data["sampled"])
        sys.stdout.write("  Near-duplicate pairs (distance <= 2): %d\n" % near_data["near_duplicate_pairs"])
        if near_data["samples"]:
            sys.stdout.write("  Sample pairs:\n")
            for id_a, id_b, dist, text_a, text_b in near_data["samples"][:10]:
                sys.stdout.write("    id=%d vs id=%d (dist=%d)\n" % (id_a, id_b, dist))
                sys.stdout.write("      A: %s\n" % text_a)
                sys.stdout.write("      B: %s\n" % text_b)
    return 0


if __name__ == "__main__":
    sys.exit(Main())
