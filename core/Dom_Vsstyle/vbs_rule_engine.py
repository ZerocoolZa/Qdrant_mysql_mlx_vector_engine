#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_engine.py>][@domain<Vbs_Code_Verifiation>][@role<rules_authority>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<rules_authority>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
RuleEngine: authority over VBStyle rules.

The ONE place all VBStyle rules live is vb_shared.rule_tokens. This engine
extracts rules from the .md source files, loads the canonical tokens, and
analyses the two for coverage, duplication, ambiguity, and conflict. It can
search, propose, create, edit, and fix tokens.

Safety by construction:
  - every write surface defaults to dry_run (returns SQL, executes nothing)
  - writes require explicit commit=True
  - creation is dedup-gated: refuses if the concept already exists
    (enforces [@MetaOneConcept]); honours @nobulk (one token at a time)
"""

import re

from . import Config_Vbs_Code_Verifiation as Config

try:
    import mysql.connector as _mysql
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False


class RuleEngine:
    """VBStyle rules authority — extract, analyse, search, create, edit, fix."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
            "conn": None,
            "cur": None,
            "tokens": [],
            "extracted": [],
        }

    # ── connection ───────────────────────────────────────────

    #[@open]{[@params<<params>][@return<Tuple3>][@purpose<open MySQL connection to canonical store>]}
    def open(self, params=None):
        try:
            if not _MYSQL_AVAILABLE:
                return (0, None, ("MYSQL_NOT_AVAILABLE", "mysql.connector not installed", 0))
            self.state["conn"] = _mysql.connect(**Config.MYSQL_CONFIG)
            self.state["cur"] = self.state["conn"].cursor()
            return (1, {"connected": True}, None)
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    #[@close]{[@params<<params>][@return<Tuple3>][@purpose<close MySQL connection>]}
    def close(self, params=None):
        try:
            if self.state["conn"]:
                self.state["conn"].close()
                self.state["conn"] = None
                self.state["cur"] = None
            return (1, {"closed": True}, None)
        except Exception as e:
            return (0, None, ("CLOSE_ERROR", str(e), 0))

    # ── concept signature helpers ────────────────────────────

    #[@signature]{[@params<<params>][@return<Tuple3>][@purpose<reduce text to a concept word set for matching>]}
    def signature(self, params):
        try:
            text = params.get("text", "")
            words = re.findall(r"[a-z0-9_]+", text.lower())
            sig = {w for w in words if w not in Config.RULE_STOPWORDS and len(w) > 2}
            return (1, {"signature": sig}, None)
        except Exception as e:
            return (0, None, ("SIGNATURE_ERROR", str(e), 0))

    #[@score_match]{[@params<<params>][@return<Tuple3>][@purpose<score concept overlap between a rule and a token>]}
    def score_match(self, params):
        try:
            rule_sig = params.get("rule_sig", set())
            token_sig = params.get("token_sig", set())
            if not rule_sig or not token_sig:
                return (1, {"score": 0.0}, None)
            overlap = rule_sig & token_sig
            denom = max(1, min(len(rule_sig), len(token_sig)))
            score = len(overlap) / denom
            distinctive = {w for w in overlap if len(w) >= Config.RULE_DISTINCTIVE_LEN}
            if distinctive:
                score += 0.25 * len(distinctive)
            return (1, {"score": min(score, 1.0), "overlap": sorted(overlap)}, None)
        except Exception as e:
            return (0, None, ("SCORE_ERROR", str(e), 0))

    # ── extraction ───────────────────────────────────────────

    #[@extract]{[@params<<params>][@return<Tuple3>][@purpose<parse one .md rule file into rule statements>]}
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
                        rules.append({
                            "source": source,
                            "rid": "@" + tag.group(1),
                            "text": tag.group(2),
                            "kind": "obey_tag",
                        })
                        continue
                    sec = Config.SECTION_RULE_RE.match(line)
                    if sec:
                        if current_id:
                            rules.append({
                                "source": source,
                                "rid": current_id,
                                "text": " ".join(current_text).strip(),
                                "kind": "section",
                            })
                        current_id = sec.group(1)
                        current_text = [sec.group(2)]
                    elif current_id and line.strip() and not line.startswith("#") and not line.startswith("```"):
                        current_text.append(line.strip())
            if current_id:
                rules.append({
                    "source": source,
                    "rid": current_id,
                    "text": " ".join(current_text).strip(),
                    "kind": "section",
                })

            return (1, {"rules": rules, "count": len(rules)}, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ERROR", str(e), 0))

    #[@extract_all]{[@params<<params>][@return<Tuple3>][@purpose<extract rules from all configured .md sources>]}
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

    # ── canonical load ───────────────────────────────────────

    #[@load_tokens]{[@params<<params>][@return<Tuple3>][@purpose<read canonical rule_tokens into state>]}
    def load_tokens(self, params=None):
        try:
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute(
                "SELECT name, bracket_body, category FROM {}".format(Config.RULE_TOKENS_TABLE)
            )
            tokens = []
            for name, body, cat in cur.fetchall():
                sig_r = self.signature({"text": "{} {}".format(name or "", body or "")})
                sig = sig_r[1]["signature"] if sig_r[0] else set()
                tokens.append({
                    "name": name,
                    "body": body or "",
                    "category": cat or "",
                    "signature": sig,
                })
            self.state["tokens"] = tokens
            return (1, {"tokens": tokens, "count": len(tokens)}, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    #[@best_match]{[@params<<params>][@return<Tuple3>][@purpose<find the closest canonical token for a rule text>]}
    def best_match(self, params):
        try:
            text = params.get("text", "")
            tokens = params.get("tokens") or self.state["tokens"]
            sig_r = self.signature({"text": text})
            rule_sig = sig_r[1]["signature"] if sig_r[0] else set()
            best = None
            best_score = 0.0
            for tok in tokens:
                sc = self.score_match({"rule_sig": rule_sig, "token_sig": tok["signature"]})
                score = sc[1]["score"] if sc[0] else 0.0
                if score > best_score:
                    best_score = score
                    best = tok
            return (1, {"match": best, "score": best_score}, None)
        except Exception as e:
            return (0, None, ("MATCH_ERROR", str(e), 0))

    # ── analysis ─────────────────────────────────────────────

    #[@analyze]{[@params<<params>][@return<Tuple3>][@purpose<gap report covered weak missing for extracted rules>]}
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
                entry = {
                    "source": rule["source"],
                    "rid": rule["rid"],
                    "text": rule["text"][:100],
                    "closest": match["name"] if match else None,
                    "score": round(score, 2),
                }
                if score >= Config.RULE_MATCH_COVERED:
                    covered.append(entry)
                elif score >= Config.RULE_MATCH_WEAK:
                    weak.append(entry)
                else:
                    missing.append(entry)

            return (1, {
                "total": len(rules),
                "covered": covered,
                "weak": weak,
                "missing": missing,
                "counts": {
                    "covered": len(covered),
                    "weak": len(weak),
                    "missing": len(missing),
                },
            }, None)
        except Exception as e:
            return (0, None, ("ANALYZE_ERROR", str(e), 0))

    #[@detect_duplicates]{[@params<<params>][@return<Tuple3>][@purpose<find tokens with identical bodies enforcing MetaNoDupBody>]}
    def detect_duplicates(self, params=None):
        try:
            if not self.state["tokens"]:
                self.load_tokens({})
            by_body = {}
            for tok in self.state["tokens"]:
                key = tok["body"].strip()
                by_body.setdefault(key, []).append(tok["name"])
            dups = [
                {"body": body, "tokens": names}
                for body, names in by_body.items() if len(names) > 1
            ]
            return (1, {"duplicates": dups, "count": len(dups)}, None)
        except Exception as e:
            return (0, None, ("DUP_ERROR", str(e), 0))

    #[@detect_conflicts]{[@params<<params>][@return<Tuple3>][@purpose<flag known contradictory concepts sharing a keyword>]}
    def detect_conflicts(self, params=None):
        try:
            conflicts = []
            for token_a, tag_b, keyword, note in Config.RULE_CONFLICT_PAIRS:
                conflicts.append({
                    "token": token_a,
                    "rule": tag_b,
                    "shared_keyword": keyword,
                    "note": note,
                })
            return (1, {"conflicts": conflicts, "count": len(conflicts)}, None)
        except Exception as e:
            return (0, None, ("CONFLICT_ERROR", str(e), 0))

    #[@search]{[@params<<params>][@return<Tuple3>][@purpose<search canonical tokens by concept keyword>]}
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
                sc = self.score_match({"rule_sig": qsig, "token_sig": tok["signature"]})
                score = sc[1]["score"] if sc[0] else 0.0
                if score > 0:
                    scored.append((score, tok))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [
                {"name": t["name"], "body": t["body"], "category": t["category"], "score": round(s, 2)}
                for s, t in scored[:limit]
            ]
            return (1, {"results": results, "count": len(results)}, None)
        except Exception as e:
            return (0, None, ("SEARCH_ERROR", str(e), 0))

    # ── proposal / write (safe by construction) ──────────────

    #[@propose]{[@params<<params>][@return<Tuple3>][@purpose<build a dedup-checked canonical token from a rule statement>]}
    def propose(self, params):
        try:
            name = params.get("name", "")
            detail = params.get("detail", "")
            category = params.get("category", "Other")
            if not name or not detail:
                return (0, None, ("MISSING_PARAMS", "name and detail required", 0))
            if not name.startswith("[@"):
                name = "[@{}]".format(name)
            if category not in Config.RULE_CATEGORIES:
                return (0, None, ("BAD_CATEGORY", category, 0))

            if not self.state["tokens"]:
                self.load_tokens({})

            # dedup gate — enforce [@MetaOneConcept].
            # Exact name collision is always a duplicate.
            for tok in self.state["tokens"]:
                if tok["name"] == name:
                    return (0, None, ("DUPLICATE_NAME", name, 0))
            # Concept collision requires BOTH a high score AND enough
            # distinctive (long) shared words, so generic prose overlap
            # ("without"/"explicit") cannot cause a false block.
            m = self.best_match({"text": detail})
            close = m[1]["match"] if m[0] else None
            close_score = m[1]["score"] if m[0] else 0.0
            distinctive = []
            if close:
                det_sig = self.signature({"text": detail})[1]["signature"]
                shared = det_sig & close["signature"]
                distinctive = [w for w in shared if len(w) >= Config.RULE_DISTINCTIVE_LEN]
            blocked = (
                close_score >= Config.RULE_DEDUP_BLOCK
                and len(distinctive) >= Config.RULE_DEDUP_MIN_DISTINCTIVE
            )

            body = '("{}";{})'.format(detail.replace('"', "'"), Config.RULE_TOKEN_WEIGHT)
            sql = (
                "INSERT INTO {} (name, bracket_body, category) VALUES (%s, %s, %s);".format(
                    Config.RULE_TOKENS_TABLE)
            )
            return (1, {
                "name": name,
                "body": body,
                "category": category,
                "sql": sql,
                "sql_params": [name, body, category],
                "dedup_closest": close["name"] if close else None,
                "dedup_score": round(close_score, 2),
                "blocked_as_duplicate": blocked,
            }, None)
        except Exception as e:
            return (0, None, ("PROPOSE_ERROR", str(e), 0))

    #[@create]{[@params<<params>][@return<Tuple3>][@purpose<create one canonical token dedup-gated dry_run default>]}
    def create(self, params):
        try:
            commit = params.get("commit", False)
            prop = self.propose(params)
            if not prop[0]:
                return prop
            plan = prop[1]
            if plan["blocked_as_duplicate"]:
                return (0, None, (
                    "BLOCKED_DUPLICATE",
                    "concept overlaps {} ({:.2f}); refuse per [@MetaOneConcept]".format(
                        plan["dedup_closest"], plan["dedup_score"]), 0))
            if not commit:
                return (1, {"dry_run": True, "would_execute": plan["sql"],
                            "params": plan["sql_params"], "plan": plan}, None)

            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute(plan["sql"], tuple(plan["sql_params"]))
            self.state["conn"].commit()
            self.load_tokens({})
            return (1, {"created": plan["name"], "committed": True}, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    #[@edit]{[@params<<params>][@return<Tuple3>][@purpose<edit an existing token body or category dry_run default>]}
    def edit(self, params):
        try:
            name = params.get("name", "")
            commit = params.get("commit", False)
            new_body = params.get("body")
            new_category = params.get("category")
            if not name:
                return (0, None, ("MISSING_NAME", "name required", 0))

            set_parts = []
            values = []
            if new_body is not None:
                set_parts.append("bracket_body = %s")
                values.append(new_body)
            if new_category is not None:
                if new_category not in Config.RULE_CATEGORIES:
                    return (0, None, ("BAD_CATEGORY", new_category, 0))
                set_parts.append("category = %s")
                values.append(new_category)
            if not set_parts:
                return (0, None, ("NO_CHANGES", "nothing to edit", 0))

            sql = "UPDATE {} SET {} WHERE name = %s;".format(
                Config.RULE_TOKENS_TABLE, ", ".join(set_parts))
            values.append(name)

            if not commit:
                return (1, {"dry_run": True, "would_execute": sql, "params": values}, None)

            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute(sql, tuple(values))
            self.state["conn"].commit()
            self.load_tokens({})
            return (1, {"edited": name, "committed": True}, None)
        except Exception as e:
            return (0, None, ("EDIT_ERROR", str(e), 0))

    #[@fix]{[@params<<params>][@return<Tuple3>][@purpose<plan resolution of a duplicate set keep one supersede others>]}
    def fix(self, params):
        try:
            keep = params.get("keep", "")
            drop = params.get("drop", [])
            commit = params.get("commit", False)
            if not keep or not drop:
                return (0, None, ("MISSING_PARAMS", "keep and drop required", 0))

            statements = []
            for name in drop:
                statements.append((
                    "UPDATE {} SET category = 'Other', bracket_body = CONCAT('SUPERSEDED by ', %s, ' :: ', bracket_body) WHERE name = %s;".format(
                        Config.RULE_TOKENS_TABLE),
                    [keep, name],
                ))

            if not commit:
                return (1, {"dry_run": True, "keep": keep, "drop": drop,
                            "would_execute": [s for s, _ in statements]}, None)

            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            for sql, vals in statements:
                cur.execute(sql, tuple(vals))
            self.state["conn"].commit()
            self.load_tokens({})
            return (1, {"kept": keep, "superseded": drop, "committed": True}, None)
        except Exception as e:
            return (0, None, ("FIX_ERROR", str(e), 0))

    # ── boilerplate ──────────────────────────────────────────

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read RuleEngine state>]}
    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k not in ("conn", "cur")}, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set RuleEngine config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch RuleEngine commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "open": self.open,
            "close": self.close,
            "signature": self.signature,
            "score_match": self.score_match,
            "extract": self.extract,
            "extract_all": self.extract_all,
            "load_tokens": self.load_tokens,
            "best_match": self.best_match,
            "analyze": self.analyze,
            "detect_duplicates": self.detect_duplicates,
            "detect_conflicts": self.detect_conflicts,
            "search": self.search,
            "propose": self.propose,
            "create": self.create,
            "edit": self.edit,
            "fix": self.fix,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))
