#!/usr/bin/env python3
# [@GHOST]{[@file<KnowledgeBase.py>][@domain<Dom_Report>][@role<knowledge>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<knowledge>][@return<tuple3>][@orch<Investigator>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{KnowledgeBase — Layer 2+. Queries local SQLite (question_store.db) for known problems, solutions, and learned mistakes. Fills pending diagnosis answers with evidence.}
# [@CLASS]{KnowledgeBase}
# [@METHOD]{Run,Lookup,SearchMistakes,SearchSolutions,SearchProblems,RecordFinding,read_state,set_config}
# [@FILEID]{core/Dom_Report/KnowledgeBase.py

import os
import sqlite3
import datetime

from . import Config


class KnowledgeBase:
    """Queries the knowledge base to fill pending diagnosis answers.

    Searches for:
        - Known problems matching the operation + reason
        - Learned mistakes matching the failure pattern
        - Known solutions matching the problem

    Fills History, Repair, and Prevention categories where matches found.
    Does NOT modify the report. Only enriches the diagnosis.

    self.state:
        state['db_path']:     path to the SQLite knowledge base
        state['connected']:   whether the DB is accessible
        state['findings']:    list of findings from the last lookup
        state['stats']:       lookup counters
    """

    def __init__(self, mem=None, db=None, param=None):
        default_db = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "utility", "question_store.db"
        )
        self.state = {
            "db_path": default_db,
            "connected": False,
            "findings": [],
            "stats": {"lookups": 0, "matches": 0, "solutions_found": 0},
        }
        if param:
            self.set_config(param)
        self._check_connection()

    def Run(self, command, params=None):
        dispatch = {
            "lookup": self.Lookup,
            "search_mistakes": self.SearchMistakes,
            "search_solutions": self.SearchSolutions,
            "search_problems": self.SearchProblems,
            "record_finding": self.RecordFinding,
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
        self._check_connection()
        return (1, dict(self.state), None)

    def _check_connection(self):
        self.state["connected"] = os.path.isfile(self.state["db_path"])

    def _connect(self):
        if not self.state["connected"]:
            return (0, None, ("ERR_DB", "knowledge base not found: %s" % self.state["db_path"], 0))
        try:
            conn = sqlite3.connect(self.state["db_path"])
            conn.row_factory = sqlite3.Row
            return (1, conn, None)
        except Exception as e:
            return (0, None, ("ERR_CONNECT", str(e), 0))

    def Lookup(self, params):
        """Main entry point — takes a diagnosis dict, fills pending answers.

        params:
            diagnosis: the diagnosis dict from Investigator
            operation: the operation name
            reason: the failure reason
        Returns:
            (1, enriched_diagnosis, None) — diagnosis with pending answers filled
        """
        diagnosis = self._p(params, "diagnosis", {})
        operation = self._p(params, "operation", "")
        reason = self._p(params, "reason", "")
        self.state["findings"] = []
        self.state["stats"]["lookups"] += 1
        if not self.state["connected"]:
            return (1, diagnosis, None)
        ok, conn, err = self._connect()
        if not ok:
            return (1, diagnosis, None)
        search_term = reason if reason else operation
        ok_m, mistakes, _ = self._search_mistakes(conn, search_term)
        ok_s, solutions, _ = self._search_solutions(conn, search_term)
        ok_p, problems, _ = self._search_problems(conn, operation)
        conn.close()
        enriched = dict(diagnosis)
        if mistakes:
            self.state["stats"]["matches"] += len(mistakes)
            self._fill_history(enriched, mistakes, problems)
            self._fill_repair(enriched, mistakes, solutions)
            self._fill_prevention(enriched, mistakes)
        elif problems:
            self._fill_history_from_problems(enriched, problems)
        if solutions:
            self.state["stats"]["solutions_found"] += len(solutions)
            self._fill_repair_from_solutions(enriched, solutions)
        return (1, enriched, None)

    def _search_mistakes(self, conn, search_term):
        if not search_term:
            return (1, [], None)
        cur = conn.cursor()
        words = search_term.split()
        conditions = " OR ".join(["pattern LIKE ?" for _ in words])
        params = ["%" + w + "%" for w in words]
        try:
            cur.execute(
                "SELECT id, pattern, fix_action, confidence FROM mistakes WHERE %s ORDER BY confidence DESC LIMIT 10" % conditions,
                params
            )
            rows = [dict(r) for r in cur.fetchall()]
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("ERR_QUERY", str(e), 0))

    def _search_solutions(self, conn, search_term):
        if not search_term:
            return (1, [], None)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, question_id, suggested_solution, source FROM solutions WHERE suggested_solution LIKE ? ORDER BY id DESC LIMIT 10",
                ["%" + search_term + "%"]
            )
            rows = [dict(r) for r in cur.fetchall()]
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("ERR_QUERY", str(e), 0))

    def _search_problems(self, conn, search_term):
        if not search_term:
            return (1, [], None)
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, status FROM problems WHERE name LIKE ? ORDER BY id DESC LIMIT 10",
                ["%" + search_term + "%"]
            )
            rows = [dict(r) for r in cur.fetchall()]
            return (1, rows, None)
        except Exception as e:
            return (0, None, ("ERR_QUERY", str(e), 0))

    def SearchMistakes(self, params):
        search_term = self._p(params, "term", "")
        if not search_term:
            return (0, None, ("ERR_PARAMS", "term required", 0))
        if not self.state["connected"]:
            return (1, [], None)
        ok, conn, err = self._connect()
        if not ok:
            return (1, [], None)
        ok, results, err = self._search_mistakes(conn, search_term)
        conn.close()
        return (ok, results, err)

    def SearchSolutions(self, params):
        search_term = self._p(params, "term", "")
        if not search_term:
            return (0, None, ("ERR_PARAMS", "term required", 0))
        if not self.state["connected"]:
            return (1, [], None)
        ok, conn, err = self._connect()
        if not ok:
            return (1, [], None)
        ok, results, err = self._search_solutions(conn, search_term)
        conn.close()
        return (ok, results, err)

    def SearchProblems(self, params):
        search_term = self._p(params, "term", "")
        if not search_term:
            return (0, None, ("ERR_PARAMS", "term required", 0))
        if not self.state["connected"]:
            return (1, [], None)
        ok, conn, err = self._connect()
        if not ok:
            return (1, [], None)
        ok, results, err = self._search_problems(conn, search_term)
        conn.close()
        return (ok, results, err)

    def RecordFinding(self, params):
        finding = {
            "operation": self._p(params, "operation", ""),
            "reason": self._p(params, "reason", ""),
            "category": self._p(params, "category", ""),
            "question": self._p(params, "question", ""),
            "finding": self._p(params, "finding", ""),
            "source": self._p(params, "source", "knowledge_base"),
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self.state["findings"].append(finding)
        return (1, finding, None)

    # ── fill helpers ────────────────────────────────────────────────────────

    def _fill_history(self, diagnosis, mistakes, problems):
        if Config.CATEGORY_HISTORY not in diagnosis:
            diagnosis[Config.CATEGORY_HISTORY] = {}
        hist = diagnosis[Config.CATEGORY_HISTORY]
        hist["seen_before"] = {"status": Config.ANSWER_KNOWN, "answer": "yes — %d matching patterns found" % len(mistakes)}
        hist["known_problem"] = {"status": Config.ANSWER_KNOWN, "answer": "yes — pattern: %s" % mistakes[0]["pattern"]}
        hist["is_new"] = {"status": Config.ANSWER_KNOWN, "answer": "no — this pattern is in the knowledge base"}
        self.RecordFinding({"category": Config.CATEGORY_HISTORY, "finding": "matched %d mistakes" % len(mistakes)})

    def _fill_history_from_problems(self, diagnosis, problems):
        if Config.CATEGORY_HISTORY not in diagnosis:
            diagnosis[Config.CATEGORY_HISTORY] = {}
        hist = diagnosis[Config.CATEGORY_HISTORY]
        hist["seen_before"] = {"status": Config.ANSWER_KNOWN, "answer": "yes — %d related problems found" % len(problems)}
        hist["known_problem"] = {"status": Config.ANSWER_KNOWN, "answer": "yes — problem: %s" % problems[0]["name"]}
        hist["is_new"] = {"status": Config.ANSWER_KNOWN, "answer": "no — related problem exists"}
        self.RecordFinding({"category": Config.CATEGORY_HISTORY, "finding": "matched %d problems" % len(problems)})

    def _fill_repair(self, diagnosis, mistakes, solutions):
        if Config.CATEGORY_REPAIR not in diagnosis:
            diagnosis[Config.CATEGORY_REPAIR] = {}
        rep = diagnosis[Config.CATEGORY_REPAIR]
        top = mistakes[0]
        rep["is_fixable"] = {"status": Config.ANSWER_KNOWN, "answer": "yes — fix action recorded (confidence: %.0f%%)" % (top.get("confidence", 0) * 100)}
        rep["known_fix"] = {"status": Config.ANSWER_KNOWN, "answer": top.get("fix_action", "fix action recorded")}
        rep["which_fix_worked"] = {"status": Config.ANSWER_KNOWN, "answer": "pattern: %s → %s" % (top.get("pattern", ""), top.get("fix_action", ""))}
        rep["can_auto_apply"] = {"status": Config.ANSWER_UNKNOWN, "answer": "unknown — needs manual review"}
        self.RecordFinding({"category": Config.CATEGORY_REPAIR, "finding": "fix: %s" % top.get("fix_action", "")})

    def _fill_repair_from_solutions(self, diagnosis, solutions):
        if Config.CATEGORY_REPAIR not in diagnosis:
            diagnosis[Config.CATEGORY_REPAIR] = {}
        rep = diagnosis[Config.CATEGORY_REPAIR]
        top = solutions[0]
        if rep.get("known_fix", {}).get("status") != Config.ANSWER_KNOWN:
            rep["known_fix"] = {"status": Config.ANSWER_KNOWN, "answer": top.get("suggested_solution", "solution recorded")}
        if rep.get("which_fix_worked", {}).get("status") != Config.ANSWER_KNOWN:
            rep["which_fix_worked"] = {"status": Config.ANSWER_KNOWN, "answer": "solution: %s (source: %s)" % (top.get("suggested_solution", ""), top.get("source", ""))}
        self.RecordFinding({"category": Config.CATEGORY_REPAIR, "finding": "solution: %s" % top.get("suggested_solution", "")})

    def _fill_prevention(self, diagnosis, mistakes):
        if Config.CATEGORY_PREVENTION not in diagnosis:
            diagnosis[Config.CATEGORY_PREVENTION] = {}
        prev = diagnosis[Config.CATEGORY_PREVENTION]
        top = mistakes[0]
        prev["how_prevent"] = {"status": Config.ANSWER_KNOWN, "answer": "avoid pattern: %s" % top.get("pattern", "")}
        prev["missing_guard"] = {"status": Config.ANSWER_KNOWN, "answer": "guard against: %s" % top.get("pattern", "")}
        prev["detect_earlier"] = {"status": Config.ANSWER_UNKNOWN, "answer": "unknown — needs analysis of when pattern first appears"}
        self.RecordFinding({"category": Config.CATEGORY_PREVENTION, "finding": "prevent: avoid %s" % top.get("pattern", "")})
