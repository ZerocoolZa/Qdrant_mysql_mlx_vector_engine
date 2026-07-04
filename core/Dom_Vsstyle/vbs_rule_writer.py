#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_writer.py>][@domain<Vbs_Code_Verifiation>][@role<rule_writer>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<rule_writer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
RuleWriter: write authority over VBStyle rule_tokens.
Creates, edits, fixes, and syncs tokens. Uses RuleReader for analysis.
Safety: dry_run default, commit=True to execute. Dedup-gated.
"""

import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import Config_Vbs_Code_Verifiation as Config
from .vbs_rule_reader import RuleReader


class RuleWriter:
    """Write authority: create, edit, fix, sync. Dedup-gated, dry-run default."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "reader": None,
            "conn": None,
            "cur": None,
            "tokens": [],
            "last_plan": None,
            "sync_log": [],
        }

    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "open": self.open,
            "close": self.close,
            "create": self.create,
            "edit": self.edit,
            "fix": self.fix,
            "sync": self.sync,
            "propose": self.propose,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))

    def open(self, params=None):
        try:
            reader = RuleReader()
            r = reader.Run("open", {})
            if not r[0]:
                return r
            reader.Run("extract_all", {})
            reader.Run("load_tokens", {})
            self.state["reader"] = reader
            self.state["conn"] = reader.state["conn"]
            self.state["cur"] = reader.state["cur"]
            self.state["tokens"] = reader.state["tokens"]
            return (1, {"connected": True, "tokens": len(self.state["tokens"])}, None)
        except Exception as e:
            return (0, None, ("OPEN_ERROR", str(e), 0))

    def close(self, params=None):
        try:
            if self.state["reader"]:
                self.state["reader"].Run("close", {})
                self.state["reader"] = None
                self.state["conn"] = None
                self.state["cur"] = None
            return (1, {"closed": True}, None)
        except Exception as e:
            return (0, None, ("CLOSE_ERROR", str(e), 0))

    def refresh_tokens(self):
        if self.state["reader"]:
            self.state["reader"].Run("load_tokens", {})
            self.state["tokens"] = self.state["reader"].state["tokens"]

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
            for tok in self.state["tokens"]:
                if tok["name"] == name:
                    return (0, None, ("DUPLICATE_NAME", name, 0))
            reader = self.state["reader"]
            m = reader.Run("best_match", {"text": detail})
            close = m[1]["match"] if m[0] else None
            close_score = m[1]["score"] if m[0] else 0.0
            distinctive = []
            if close:
                det_sig = reader.Run("signature", {"text": detail})[1]["signature"]
                shared = det_sig & close["signature"]
                distinctive = [w for w in shared if len(w) >= Config.RULE_DISTINCTIVE_LEN]
            blocked = (close_score >= Config.RULE_DEDUP_BLOCK and len(distinctive) >= Config.RULE_DEDUP_MIN_DISTINCTIVE)
            body = '("{}";{})'.format(detail.replace('"', "'"), Config.RULE_TOKEN_WEIGHT)
            sql = "INSERT INTO {} (name, bracket_body, category) VALUES (%s, %s, %s);".format(Config.RULE_TOKENS_TABLE)
            plan = {"name": name, "body": body, "category": category, "sql": sql,
                    "sql_params": [name, body, category], "dedup_closest": close["name"] if close else None,
                    "dedup_score": round(close_score, 2), "blocked_as_duplicate": blocked}
            self.state["last_plan"] = plan
            return (1, plan, None)
        except Exception as e:
            return (0, None, ("PROPOSE_ERROR", str(e), 0))

    def create(self, params):
        try:
            commit = params.get("commit", False)
            prop = self.propose(params)
            if not prop[0]:
                return prop
            plan = prop[1]
            if plan["blocked_as_duplicate"]:
                return (0, None, ("BLOCKED_DUPLICATE",
                    "concept overlaps {} ({:.2f}); refuse per [@MetaOneConcept]".format(
                        plan["dedup_closest"], plan["dedup_score"]), 0))
            if not commit:
                return (1, {"dry_run": True, "would_execute": plan["sql"], "params": plan["sql_params"], "plan": plan}, None)
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute(plan["sql"], tuple(plan["sql_params"]))
            self.state["conn"].commit()
            self.refresh_tokens()
            return (1, {"created": plan["name"], "committed": True}, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

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
            sql = "UPDATE {} SET {} WHERE name = %s;".format(Config.RULE_TOKENS_TABLE, ", ".join(set_parts))
            values.append(name)
            if not commit:
                return (1, {"dry_run": True, "would_execute": sql, "params": values}, None)
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            cur.execute(sql, tuple(values))
            self.state["conn"].commit()
            self.refresh_tokens()
            return (1, {"edited": name, "committed": True}, None)
        except Exception as e:
            return (0, None, ("EDIT_ERROR", str(e), 0))

    def fix(self, params):
        try:
            keep = params.get("keep", "")
            drop = params.get("drop", [])
            commit = params.get("commit", False)
            if not keep or not drop:
                return (0, None, ("MISSING_PARAMS", "keep and drop required", 0))
            statements = []
            for name in drop:
                sql = "UPDATE {} SET category = 'Other', bracket_body = CONCAT('SUPERSEDED by ', %s, ' :: ', bracket_body) WHERE name = %s;".format(Config.RULE_TOKENS_TABLE)
                statements.append((sql, [keep, name]))
            if not commit:
                return (1, {"dry_run": True, "keep": keep, "drop": drop,
                            "would_execute": [s for s, _ in statements]}, None)
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            for sql, vals in statements:
                cur.execute(sql, tuple(vals))
            self.state["conn"].commit()
            self.refresh_tokens()
            return (1, {"kept": keep, "superseded": drop, "committed": True}, None)
        except Exception as e:
            return (0, None, ("FIX_ERROR", str(e), 0))

    def sync(self, params=None):
        try:
            commit = params.get("commit", False) if params else False
            reader = self.state["reader"]
            if not reader:
                return (0, None, ("NO_READER", "Database not open", 0))
            analysis = reader.Run("analyze", {})
            if not analysis[0]:
                return (0, None, ("ANALYZE_ERROR", analysis[2], 0))
            gaps = analysis[1]["weak"] + analysis[1]["missing"]
            results = []
            for gap in gaps:
                token_name = self.derive_name(gap)
                if not token_name:
                    results.append({"rid": gap["rid"], "status": "SKIP", "reason": "could not derive name"})
                    continue
                category = self.derive_category(gap)
                cr = self.create({"name": token_name, "detail": gap["text"], "category": category, "commit": commit})
                if cr[0]:
                    results.append({"rid": gap["rid"], "token": token_name, "status": "CREATED" if commit else "DRY_RUN",
                                    "sql": cr[1].get("would_execute", "")})
                else:
                    results.append({"rid": gap["rid"], "token": token_name, "status": "BLOCKED",
                                    "reason": cr[2][1] if cr[2] else str(cr[2])})
            self.state["sync_log"] = results
            summary = {"total_gaps": len(gaps), "created": sum(1 for r in results if r["status"] in ("CREATED", "DRY_RUN")),
                       "blocked": sum(1 for r in results if r["status"] == "BLOCKED"),
                       "skipped": sum(1 for r in results if r["status"] == "SKIP"),
                       "committed": commit, "results": results}
            return (1, summary, None)
        except Exception as e:
            return (0, None, ("SYNC_ERROR", str(e), 0))

    def derive_name(self, gap):
        rid = gap["rid"]
        if rid.startswith("@"):
            rid = rid[1:]
        rid = rid.replace("_", "").replace("-", "")
        if rid and not rid[0].isupper():
            rid = rid[0].upper() + rid[1:]
        if len(rid) < 3:
            words = re.findall(r"[A-Za-z]{4,}", gap["text"])
            if words:
                rid = "".join(w[0].upper() + w[1:3].lower() for w in words[:3])
            else:
                return None
        return "[@{}]".format(rid)

    def derive_category(self, gap):
        text = gap["text"].lower()
        cat_map = [
            (["print", "decorator", "tab", "whitespace", "trailing", "semicolon", "bracket", "format"], "Format"),
            (["class", "file", "one class", "domain", "monolith"], "Architecture"),
            (["method", "run", "dispatch", "return", "tuple"], "Method"),
            (["forbidden", "must not", "no ", "never"], "Forbidden"),
            (["pascal", "uppercase", "naming", "camel"], "Naming"),
            (["path", "file path", "hardcoded"], "Paths"),
            (["mysql", "sql", "database", "query", "table"], "Database"),
            (["delete", "write", "insert", "update", "file ops"], "FileOps"),
            (["workflow", "process", "gate", "precode", "postcode"], "Workflow"),
            (["state", "self.state", "dict"], "State"),
        ]
        for keywords, cat in cat_map:
            for kw in keywords:
                if kw in text:
                    return cat
        return "Other"

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k not in ("conn", "cur", "reader")}, None)

    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))
