#!/usr/bin/env python3

#[@GHOST]{[@file<vb_rule_lunchbox.py>][@domain<Piplines>][@role<rule_lunchbox>][@auth<cascade>][@date<2026-07-05>][@ver<1.0.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<rule_lunchbox>][@return<tuple3>][@orch<BCLTransformer>][@no<decorators|print|hardcoded|tabs>]}
#[@FILEID]{[@id<vb_rule_lunchbox.py>][@domain<Piplines>][@authority<RuleLunchbox>]}
#[@SUMMARY]{RuleLunchbox — converts MySQL learned_rules (pattern -> fix_action) into packed binary training sequences for the BCL Transformer. Supports prepare_all, prepare_filtered, prepare_correction, stats, info.}
#[@CLASS]{[@name<RuleLunchbox>][@base<object>][@ctor<mem|db|param>]}
#[@METHOD]{[@name<Run>][@sig<command, params=None>][@return<tuple3>]}

"""
RuleLunchbox — Learned Rules to Training Sequences
==================================================

Queries vb_shared.learned_rules from MySQL and converts each rule
(pattern -> fix_action) into a tokenized training pair:

    Input sequence  = tokenize(pattern)       # the error / bad code
    Target sequence = tokenize(fix_action)    # the correct code

This trains the BCL Transformer to learn: "when you see X, output Y".

Binary Format (RULB):
    Header:
        magic       : 4 bytes  = b"RULB"
        version     : int32    = 1
        seq_count   : int32
        created_at  : float64  (unix timestamp)
    Per sequence:
        rule_id     : int32
        confidence  : float64
        severity    : int32
        lang_len    : int32 + lang bytes (utf-8)
        cat_len     : int32 + cat bytes (utf-8)
        in_count    : int32
        in_tokens   : repeated (tok_len int32 + tok bytes utf-8)
        tgt_count   : int32
        tgt_tokens  : repeated (tok_len int32 + tok bytes utf-8)

Commands:
    prepare_all        — convert all rules to training sequences
    prepare_filtered   — convert rules matching language/category/min_confidence
    prepare_correction — generate tiny correction lunchbox for a specific error pattern
    stats              — rule counts by language, category, confidence distribution
    info               — config and state

Usage:
    from core.Piplines.vb_rule_lunchbox import RuleLunchbox
    rl = RuleLunchbox()
    code, data, err = rl.Run("prepare_all", {"output_path": "rules.lunchbox"})
    code, data, err = rl.Run("stats", {})
"""

import os
import re
import struct
import time

from core.utility import Config

try:
    import mysql.connector as _mysql
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False


# ─── CONSTANTS ─────────────────────────────────────────────────────────────

MAGIC = b"RULB"
VERSION = 1
DEFAULT_MIN_CONFIDENCE = 0.7
DEFAULT_OCCURRENCE_THRESHOLD = 100
DEFAULT_CORRECTION_PAIRS = 5000
DEFAULT_OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "rule_lunchbox.bin"
)

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


# ─── CLASS ─────────────────────────────────────────────────────────────────

class RuleLunchbox:
    """RuleLunchbox — converts learned_rules into packed binary training sequences.

    Each rule (pattern, fix_action) becomes a training pair:
        input  = tokenize(pattern)
        target = tokenize(fix_action)
    """

    MYSQL_CONFIG = Config.ERROR_TRACKER_MYSQL

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "mysql_ok": False,
            "last_command": None,
            "last_count": 0,
            "last_output": "",
            "total_rules": 0,
            "config": {
                "min_confidence": self.param.get("min_confidence", DEFAULT_MIN_CONFIDENCE),
                "occurrence_threshold": self.param.get(
                    "occurrence_threshold", DEFAULT_OCCURRENCE_THRESHOLD
                ),
                "correction_pairs": self.param.get(
                    "correction_pairs", DEFAULT_CORRECTION_PAIRS
                ),
                "output_path": self.param.get("output_path", DEFAULT_OUTPUT_PATH),
            },
        }
        self.check_mysql()

    # ── DISPATCH ────────────────────────────────────────────────────────────

    def Run(self, command, params=None):
        p = params or {}
        if command == "prepare_all":
            return self.prepare_all(p)
        elif command == "prepare_filtered":
            return self.prepare_filtered(p)
        elif command == "prepare_correction":
            return self.prepare_correction(p)
        elif command == "stats":
            return self.stats(p)
        elif command == "info":
            return self.info(p)
        return (0, None, ("unknown_command", command, 0))

    # ── HELPERS ─────────────────────────────────────────────────────────────

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, params):
        cfg = self.state["config"]
        for k in ("min_confidence", "occurrence_threshold", "correction_pairs", "output_path"):
            if k in params:
                cfg[k] = params[k]
        return (1, dict(cfg), None)

    # ── MYSQL ───────────────────────────────────────────────────────────────

    def check_mysql(self):
        try:
            if not _MYSQL_AVAILABLE:
                self.state["mysql_ok"] = False
                return
            conn = self.mysql_connect()
            if conn:
                conn.close()
                self.state["mysql_ok"] = True
        except Exception:
            self.state["mysql_ok"] = False

    def mysql_connect(self):
        cfg = dict(self.MYSQL_CONFIG)
        unix_socket = cfg.pop("unix_socket", None)
        if unix_socket and os.path.exists(unix_socket):
            return _mysql.connect(unix_socket=unix_socket, **cfg)
        return _mysql.connect(**cfg)

    def query_rules(self, where_clause, params, limit=None):
        """Query learned_rules with an optional WHERE clause. Returns list of dicts."""
        if not self.state["mysql_ok"]:
            return []
        sql = (
            "SELECT id, pattern, trigger_condition, fix_action, language, "
            "category, severity, success_count, failure_count, confidence, "
            "source FROM learned_rules"
        )
        if where_clause:
            sql += " WHERE " + where_clause
        sql += " ORDER BY confidence DESC, id ASC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        conn = None
        rows = []
        try:
            conn = self.mysql_connect()
            cur = conn.cursor()
            cur.execute(sql, params)
            for r in cur.fetchall():
                rows.append({
                    "id": r[0],
                    "pattern": r[1] or "",
                    "trigger_condition": r[2] or "",
                    "fix_action": r[3] or "",
                    "language": r[4] or "unknown",
                    "category": r[5] or "general",
                    "severity": r[6] if r[6] is not None else 2,
                    "success_count": r[7] or 0,
                    "failure_count": r[8] or 0,
                    "confidence": float(r[9]) if r[9] is not None else 0.5,
                    "source": r[10] or "",
                    "occurrence_count": (r[7] or 0) + (r[8] or 0),
                })
            cur.close()
        except Exception:
            rows = []
        finally:
            if conn:
                conn.close()
        return rows

    # ── TOKENIZER ───────────────────────────────────────────────────────────

    def tokenize(self, text):
        """Tokenize text into a list of string tokens.

        Splits on word boundaries and individual punctuation characters.
        """
        if not text:
            return []
        return TOKEN_RE.findall(text)

    # ── PACKING ─────────────────────────────────────────────────────────────

    def pack_sequences(self, rules, output_path):
        """Pack a list of rule dicts into a binary RULB file. Returns byte count."""
        buf = bytearray()
        # Header
        buf += MAGIC
        buf += struct.pack("<i", VERSION)
        buf += struct.pack("<i", len(rules))
        buf += struct.pack("<d", time.time())
        # Sequences
        for r in rules:
            in_tokens = self.tokenize(r["pattern"])
            tgt_tokens = self.tokenize(r["fix_action"])
            lang = (r["language"] or "unknown").encode("utf-8")
            cat = (r["category"] or "general").encode("utf-8")
            buf += struct.pack("<i", r["id"])
            buf += struct.pack("<d", r["confidence"])
            buf += struct.pack("<i", r["severity"])
            buf += struct.pack("<i", len(lang))
            buf += lang
            buf += struct.pack("<i", len(cat))
            buf += cat
            buf += struct.pack("<i", len(in_tokens))
            for tok in in_tokens:
                tb = tok.encode("utf-8")
                buf += struct.pack("<i", len(tb))
                buf += tb
            buf += struct.pack("<i", len(tgt_tokens))
            for tok in tgt_tokens:
                tb = tok.encode("utf-8")
                buf += struct.pack("<i", len(tb))
                buf += tb
        with open(output_path, "wb") as fh:
            fh.write(buf)
        self.state["last_count"] = len(rules)
        self.state["last_output"] = output_path
        return len(buf)

    # ── COMMANDS ────────────────────────────────────────────────────────────

    def prepare_all(self, params):
        """Convert all learned_rules to training sequences."""
        if not self.state["mysql_ok"]:
            return (0, None, ("MYSQL_UNAVAILABLE", "MySQL connection failed", 0))
        output_path = self._p(params, "output_path", self.state["config"]["output_path"])
        rules = self.query_rules("", ())
        if not rules:
            return (0, None, ("NO_RULES", "No rules found in learned_rules", 0))
        byte_count = self.pack_sequences(rules, output_path)
        self.state["total_rules"] = len(rules)
        self.state["last_command"] = "prepare_all"
        result = {
            "rules_converted": len(rules),
            "bytes_written": byte_count,
            "output_path": output_path,
        }
        return (1, result, None)

    def prepare_filtered(self, params):
        """Convert rules matching language, category, min_confidence filters."""
        if not self.state["mysql_ok"]:
            return (0, None, ("MYSQL_UNAVAILABLE", "MySQL connection failed", 0))
        min_conf = float(self._p(params, "min_confidence", self.state["config"]["min_confidence"]))
        language = self._p(params, "language", None)
        category = self._p(params, "category", None)
        min_occurrence = int(self._p(params, "min_occurrence", 0))
        output_path = self._p(params, "output_path", self.state["config"]["output_path"])

        clauses = ["confidence >= %s"]
        vals = [min_conf]
        if language:
            clauses.append("language = %s")
            vals.append(language)
        if category:
            clauses.append("category = %s")
            vals.append(category)
        if min_occurrence > 0:
            clauses.append("(success_count + failure_count) >= %s")
            vals.append(min_occurrence)
        where_clause = " AND ".join(clauses)
        rules = self.query_rules(where_clause, tuple(vals))
        if not rules:
            return (0, None, ("NO_MATCHES", "No rules matched the filters", 0))
        byte_count = self.pack_sequences(rules, output_path)
        self.state["last_command"] = "prepare_filtered"
        result = {
            "rules_converted": len(rules),
            "bytes_written": byte_count,
            "output_path": output_path,
            "filters": {
                "min_confidence": min_conf,
                "language": language,
                "category": category,
                "min_occurrence": min_occurrence,
            },
        }
        return (1, result, None)

    def prepare_correction(self, params):
        """Generate a tiny correction lunchbox for a specific error pattern.

        Creates up to 'correction_pairs' (default 5000) training pairs by
        repeating the matched rule(s) for the given error pattern. This is
        used when an error pattern reaches the occurrence threshold.
        """
        if not self.state["mysql_ok"]:
            return (0, None, ("MYSQL_UNAVAILABLE", "MySQL connection failed", 0))
        error_pattern = self._p(params, "error_pattern", "")
        if not error_pattern:
            return (0, None, ("NO_PATTERN", "error_pattern is required", 0))
        max_pairs = int(self._p(params, "max_pairs", self.state["config"]["correction_pairs"]))
        output_path = self._p(params, "output_path", self.state["config"]["output_path"])

        # Find rules whose pattern contains the error_pattern keyword
        rules = self.query_rules(
            "pattern LIKE %s",
            ("%" + error_pattern + "%",),
        )
        if not rules:
            return (0, None, ("NO_MATCH", "No rule matched error_pattern: " + error_pattern, 0))

        # Build correction pairs by repeating matched rules up to max_pairs
        correction_rules = []
        idx = 0
        while len(correction_rules) < max_pairs:
            base = rules[idx % len(rules)]
            copy = dict(base)
            copy["id"] = 1000000 + (idx % 1000000)
            correction_rules.append(copy)
            idx += 1
        byte_count = self.pack_sequences(correction_rules, output_path)
        self.state["last_command"] = "prepare_correction"
        result = {
            "rules_matched": len(rules),
            "pairs_generated": len(correction_rules),
            "bytes_written": byte_count,
            "output_path": output_path,
            "error_pattern": error_pattern,
        }
        return (1, result, None)

    def stats(self, params):
        """Return rule counts by language, category, and confidence distribution."""
        if not self.state["mysql_ok"]:
            return (0, None, ("MYSQL_UNAVAILABLE", "MySQL connection failed", 0))
        conn = None
        try:
            conn = self.mysql_connect()
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM learned_rules")
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT IFNULL(language, 'NULL'), COUNT(*) "
                "FROM learned_rules GROUP BY language ORDER BY COUNT(*) DESC"
            )
            by_language = [{"language": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute(
                "SELECT IFNULL(category, 'NULL'), COUNT(*) "
                "FROM learned_rules GROUP BY category ORDER BY COUNT(*) DESC"
            )
            by_category = [{"category": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute(
                "SELECT CASE WHEN confidence >= 0.9 THEN '0.9+' "
                "WHEN confidence >= 0.8 THEN '0.8-0.9' "
                "WHEN confidence >= 0.7 THEN '0.7-0.8' "
                "WHEN confidence >= 0.5 THEN '0.5-0.7' "
                "ELSE '<0.5' END AS bucket, COUNT(*) "
                "FROM learned_rules GROUP BY bucket ORDER BY bucket"
            )
            by_confidence = [{"bucket": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute(
                "SELECT MIN(confidence), MAX(confidence), AVG(confidence) "
                "FROM learned_rules"
            )
            row = cur.fetchone()
            confidence_stats = {
                "min": float(row[0]) if row[0] is not None else 0.0,
                "max": float(row[1]) if row[1] is not None else 0.0,
                "avg": float(row[2]) if row[2] is not None else 0.0,
            }

            cur.execute(
                "SELECT severity, COUNT(*) FROM learned_rules "
                "GROUP BY severity ORDER BY severity"
            )
            by_severity = [{"severity": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.close()
            self.state["total_rules"] = total
            self.state["last_command"] = "stats"
            result = {
                "total": total,
                "by_language": by_language,
                "by_category": by_category,
                "by_confidence": by_confidence,
                "by_severity": by_severity,
                "confidence_stats": confidence_stats,
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATS_ERROR", str(e), 0))
        finally:
            if conn:
                conn.close()

    def info(self, params):
        """Return config and current state."""
        self.state["last_command"] = "info"
        result = {
            "config": dict(self.state["config"]),
            "mysql_ok": self.state["mysql_ok"],
            "total_rules": self.state["total_rules"],
            "last_command": self.state["last_command"],
            "last_count": self.state["last_count"],
            "last_output": self.state["last_output"],
            "mysql_config": {
                "host": self.MYSQL_CONFIG.get("host"),
                "user": self.MYSQL_CONFIG.get("user"),
                "database": self.MYSQL_CONFIG.get("database"),
            },
        }
        return (1, result, None)
