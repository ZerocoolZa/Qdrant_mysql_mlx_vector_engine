#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_reader.py>][@domain<Vbs_Code_Verifiation>][@role<rule_reader>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<rule_reader>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
RuleReader: read-only authority over VBStyle rules.
Extracts rules from .md sources, loads canonical tokens from MySQL,
analyzes coverage gaps, detects duplicates and conflicts, searches.
Never writes to the database.
"""

import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import Config_Vbs_Code_Verifiation as Config

try:
    import mysql.connector as _mysql
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False


class RuleReader:
    """Read-only authority: extract, load, analyze, search, detect."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "conn": None,
            "cur": None,
            "tokens": [],
            "extracted": [],
            "analysis": None,
        }

    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "open": self.open,
            "close": self.close,
            "extract": self.extract,
            "extract_all": self.extract_all,
            "load_tokens": self.load_tokens,
            "analyze": self.analyze,
            "search": self.search,
            "detect_duplicates": self.detect_duplicates,
            "detect_conflicts": self.detect_conflicts,
            "best_match": self.best_match,
            "signature": self.signature,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))

    def open(self, params=None):
        try:
            if not _MYSQL_AVAILABLE:
                return (0, None, ("MYSQL_NOT_AVAILABLE", "mysql.connector not installed", 0))
            self.state["conn"] = _mysql.connect(**Config.MYSQL_CONFIG)
            self.state["cur"] = self.state["conn"].cursor()
            return (1, {"connected": True}, None)
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    def close(self, params=None):
        try:
            if self.state["conn"]:
                self.state["conn"].close()
                self.state["conn"] = None
                self.state["cur"] = None
            return (1, {"closed": True}, None)
        except Exception as e:
            return (0, None, ("CLOSE_ERROR", str(e), 0))

    def signature(self, params):
        try:
            text = params.get("text", "")
            words = re.findall(r"[a-z0-9_]+", text.lower())
            sig = {w for w in words if w not in Config.RULE_STOPWORDS and len(w) > 2}
            return (1, {"signature": sig}, None)
        except Exception as e:
            return (0, None, ("SIGNATURE_ERROR", str(e), 0))

    def score_match(self, rule_sig, token_sig):
        if not rule_sig or not token_sig:
            return 0.0, []
        overlap = rule_sig & token_sig
        denom = max(1, min(len(rule_sig), len(token_sig)))
        score = len(overlap) / denom
        distinctive = {w for w in overlap if len(w) >= Config.RULE_DISTINCTIVE_LEN}
        if distinctive:
            score += 0.25 * len(distinctive)
        return min(score, 1.0), sorted(overlap)

    def extract(self, params):
        try:
            source = params.get("source", "")
            path = params.get("path", "")
            if not path:
                path = Config.RULE_SOURCE_FILES.get(source, "")
            if not path:
                return (0, None, ("NO_PATH", source, 0))
            rules = []
            current_id = None
            current_text = []
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    tag = Config.OBEY_TAG_RE.match(line)
                    if tag:
                        rules.append({"source": source, "rid": "@" + tag.group(1),
                                      "text": tag.group(2), "kind": "obey_tag"})
                        continue
                    sec = Config.SECTION_RULE_RE.match(line)
                    if sec:
                        if current_id:
                            rules.append({"source": source, "rid": current_id,
                                          "text": " ".join(current_text).strip(), "kind": "section"})
                        current_id = sec.group(1)
                        current_text = [sec.group(2)]
                    elif current_id and line.strip() and not line.startswith("#") and not line.startswith("```"):
                        current_text.append(line.strip())
            if current_id:
                rules.append({"source": source, "rid": current_id,
                              "text": " ".join(current_text).strip(), "kind": "section"})
            return (1, {"rules": rules, "count": len(rules)}, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ERROR", str(e), 0))

    def extract_all(self, params=None):
        try:
            all_rules = []
            per_source = {}
            for source in Config.RULE_SOURCE_FILES:
                r = self.extract({"source": source})
                if r[0]:
                    all_rules.extend(r[1]["rules"])
                    per_source[source] = r[1]["count"]
            self.state["extracted"] = all_rules
            return (1, {"rules": all_rules, "total": len(all_rules), "per_source": per_source}, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ALL_ERROR", str(e), 0))

    def load_tokens(self, params=None):
        try:
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute("SELECT name, bracket_body, category FROM {}".format(Config.RULE_TOKENS_TABLE))
            tokens = []
            for name, body, cat in cur.fetchall():
                sig_r = self.signature({"text": "{} {}".format(name or "", body or "")})
                sig = sig_r[1]["signature"] if sig_r[0] else set()
                tokens.append({"name": name, "body": body or "", "category": cat or "", "signature": sig})
            self.state["tokens"] = tokens
            return (1, {"tokens": tokens, "count": len(tokens)}, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def best_match(self, params):
        try:
            text = params.get("text", "")
            tokens = params.get("tokens") or self.state["tokens"]
            sig_r = self.signature({"text": text})
            rule_sig = sig_r[1]["signature"] if sig_r[0] else set()
            best = None
            best_score = 0.0
            for tok in tokens:
                score, _ = self.score_match(rule_sig, tok["signature"])
                if score > best_score:
                    best_score = score
                    best = tok
            return (1, {"match": best, "score": best_score}, None)
        except Exception as e:
            return (0, None, ("MATCH_ERROR", str(e), 0))

    def analyze(self, params=None):
        try:
            rules = self.state["extracted"]
            if not rules:
                r = self.extract_all({})
                if r[0]:
                    rules = r[1]["rules"]
            if not self.state["tokens"]:
                self.load_tokens({})
            covered, weak, missing = [], [], []
            for rule in rules:
                m = self.best_match({"text": rule["text"]})
                match = m[1]["match"] if m[0] else None
                score = m[1]["score"] if m[0] else 0.0
                entry = {"source": rule["source"], "rid": rule["rid"], "text": rule["text"][:100],
                         "closest": match["name"] if match else None, "score": round(score, 2)}
                if score >= Config.RULE_MATCH_COVERED:
                    covered.append(entry)
                elif score >= Config.RULE_MATCH_WEAK:
                    weak.append(entry)
                else:
                    missing.append(entry)
            result = {"total": len(rules), "covered": covered, "weak": weak, "missing": missing,
                      "counts": {"covered": len(covered), "weak": len(weak), "missing": len(missing)}}
            self.state["analysis"] = result
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ANALYZE_ERROR", str(e), 0))

    def detect_duplicates(self, params=None):
        try:
            if not self.state["tokens"]:
                self.load_tokens({})
            by_body = {}
            for tok in self.state["tokens"]:
                key = tok["body"].strip()
                by_body.setdefault(key, []).append(tok["name"])
            dups = [{"body": body, "tokens": names} for body, names in by_body.items() if len(names) > 1]
            return (1, {"duplicates": dups, "count": len(dups)}, None)
        except Exception as e:
            return (0, None, ("DUP_ERROR", str(e), 0))

    def detect_conflicts(self, params=None):
        try:
            conflicts = []
            for token_a, tag_b, keyword, note in Config.RULE_CONFLICT_PAIRS:
                conflicts.append({"token": token_a, "rule": tag_b, "shared_keyword": keyword, "note": note})
            return (1, {"conflicts": conflicts, "count": len(conflicts)}, None)
        except Exception as e:
            return (0, None, ("CONFLICT_ERROR", str(e), 0))

    def search(self, params):
        try:
            query = params.get("query", "")
            limit = params.get("limit", 20)
            if not self.state["tokens"]:
                self.load_tokens({})
            sig_r = self.signature({"text": query})
            qsig = sig_r[1]["signature"] if sig_r[0] else set()
            scored = []
            for tok in self.state["tokens"]:
                score, _ = self.score_match(qsig, tok["signature"])
                if score > 0:
                    scored.append((score, tok))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [{"name": t["name"], "body": t["body"], "category": t["category"], "score": round(s, 2)}
                       for s, t in scored[:limit]]
            return (1, {"results": results, "count": len(results)}, None)
        except Exception as e:
            return (0, None, ("SEARCH_ERROR", str(e), 0))

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k not in ("conn", "cur")}, None)

    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))
