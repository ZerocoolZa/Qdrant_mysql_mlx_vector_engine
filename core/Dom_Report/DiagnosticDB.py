#!/usr/bin/env python3
# [@GHOST]{[@file<DiagnosticDB.py>][@domain<Dom_Report>][@role<database>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<database>][@return<tuple3>][@orch<Investigator>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{DiagnosticDB — MySQL connector for the diagnostic_kb database. Stores incidents, facts, answers, causes, fixes, prevention rules, evidence, problems, solutions, and learned rules. Centered on INCIDENT as the anchor.}
# [@CLASS]{DiagnosticDB}
# [@METHOD]{Run,StoreIncident,StoreDiagnosis,StoreFact,StoreCause,StoreFix,StorePrevention,StoreEvidence,FindProblem,CreateProblem,AddSolution,AddRule,LinkIncidentProblem,GetIncident,GetDiagnosis,SearchProblems,SearchRules,SearchSolutions,read_state,set_config}
# [@FILEID]{core/Dom_Report/DiagnosticDB.py

import mysql.connector
import datetime

from . import Config


class DiagnosticDB:
    """MySQL connector for the diagnostic_kb database.

    The INCIDENT table is the anchor. Everything else hangs off it.
    This class stores and retrieves diagnostic data.

    self.state:
        state['host']:       MySQL host
        state['user']:       MySQL user
        state['password']:   MySQL password
        state['database']:   database name
        state['connected']:  whether the DB is accessible
        state['last_incident_id']: ID of the last stored incident
        state['stats']:      operation counters
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "diagnostic_kb",
            "connected": False,
            "last_incident_id": 0,
            "stats": {"incidents": 0, "facts": 0, "answers": 0, "problems": 0, "rules": 0},
        }
        if param:
            self.set_config(param)
        self._check_connection()

    def Run(self, command, params=None):
        dispatch = {
            "store_incident": self.StoreIncident,
            "store_diagnosis": self.StoreDiagnosis,
            "store_fact": self.StoreFact,
            "store_cause": self.StoreCause,
            "store_fix": self.StoreFix,
            "store_prevention": self.StorePrevention,
            "store_evidence": self.StoreEvidence,
            "find_problem": self.FindProblem,
            "create_problem": self.CreateProblem,
            "add_solution": self.AddSolution,
            "add_rule": self.AddRule,
            "add_learned_rule": self.AddRule,
            "link_incident_problem": self.LinkIncidentProblem,
            "get_incident": self.GetIncident,
            "get_diagnosis": self.GetDiagnosis,
            "search_problems": self.SearchProblems,
            "search_rules": self.SearchRules,
            "search_learned_rules": self.SearchRules,
            "search_solutions": self.SearchSolutions,
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
        try:
            conn = self._connect()
            conn.close()
            self.state["connected"] = True
        except Exception:
            self.state["connected"] = False

    def _connect(self):
        return mysql.connector.connect(
            host=self.state["host"],
            user=self.state["user"],
            password=self.state["password"],
            database=self.state["database"],
            unix_socket="/tmp/mysql.sock",
        )

    def _safe_execute(self, query, params=None, fetch=False, fetchone=False, commit=False):
        try:
            conn = self._connect()
            cur = conn.cursor(dictionary=True)
            cur.execute(query, params or ())
            result = None
            if fetchone:
                result = cur.fetchone()
            elif fetch:
                result = cur.fetchall()
            lastrowid = None
            if commit:
                conn.commit()
                lastrowid = cur.lastrowid
            cur.close()
            conn.close()
            if fetchone or fetch:
                return (1, result, None)
            if commit:
                return (1, lastrowid, None)
            return (1, True, None)
        except Exception as e:
            return (0, None, ("ERR_DB", str(e), 0))

    # ================================================================
    # STORE — write operations
    # ================================================================

    def StoreIncident(self, params):
        operation = self._p(params, "operation", "")
        source = self._p(params, "source", "")
        result = self._p(params, "result", "")
        reason = self._p(params, "reason", "")
        fact_count = self._p(params, "fact_count", 0)
        if not operation or not result:
            return (0, None, ("ERR_PARAMS", "operation and result required", 0))
        ok, existing, _ = self._safe_execute(
            "SELECT id FROM incident WHERE operation=%s AND result=%s AND reason=%s ORDER BY id DESC LIMIT 1",
            (operation, result, reason), fetchone=True
        )
        if ok and existing:
            self.state["last_incident_id"] = existing["id"]
            self.state["stats"]["incidents"] += 1
            return (1, existing["id"], None)
        ok, insert_id, err = self._safe_execute(
            "INSERT INTO incident (operation, source, result, reason, fact_count, finalized_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (operation, source, result, reason, fact_count, datetime.datetime.now()),
            commit=True
        )
        if not ok:
            return (ok, None, err)
        incident_id = insert_id if isinstance(insert_id, int) and insert_id > 0 else 0
        self.state["last_incident_id"] = incident_id
        self.state["stats"]["incidents"] += 1
        return (1, incident_id, None)

    def StoreFact(self, params):
        incident_id = self._p(params, "incident_id", 0)
        slot = self._p(params, "slot", "")
        kind = self._p(params, "kind", "")
        name = self._p(params, "name", "")
        value = self._p(params, "value", "")
        severity = self._p(params, "severity", "")
        unit = self._p(params, "unit", "")
        detail = self._p(params, "detail", "")
        source = self._p(params, "source", "")
        if not incident_id or not kind or not name:
            return (0, None, ("ERR_PARAMS", "incident_id, kind, name required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO fact (incident_id, slot, kind, name, value, severity, unit, detail, source) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (incident_id, slot, kind, name, str(value), severity, unit, detail, source),
            commit=True
        )
        if not ok:
            return (ok, None, err)
        self.state["stats"]["facts"] += 1
        return (1, True, None)

    def StoreDiagnosis(self, params):
        incident_id = self._p(params, "incident_id", 0)
        diagnosis = self._p(params, "diagnosis", {})
        if not incident_id or not diagnosis:
            return (0, None, ("ERR_PARAMS", "incident_id and diagnosis required", 0))
        stored = 0
        for category, questions in diagnosis.items():
            for question, answer_data in questions.items():
                status = answer_data.get("status", Config.ANSWER_UNKNOWN)
                answer = answer_data.get("answer", "")
                source_type = "report" if status == Config.ANSWER_KNOWN else "pending"
                ok, _, err = self._safe_execute(
                    "INSERT INTO answer (incident_id, category, question, status, answer, source_type) VALUES (%s, %s, %s, %s, %s, %s)",
                    (incident_id, category, question, status, answer, source_type),
                    commit=True
                )
                if ok:
                    stored += 1
        self.state["stats"]["answers"] += stored
        return (1, stored, None)

    def StoreCause(self, params):
        incident_id = self._p(params, "incident_id", 0)
        cause_type = self._p(params, "cause_type", "root")
        cause_text = self._p(params, "cause_text", "")
        severity = self._p(params, "severity", 0)
        evidence = self._p(params, "evidence", "")
        if not incident_id or not cause_text:
            return (0, None, ("ERR_PARAMS", "incident_id and cause_text required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO cause (incident_id, cause_type, cause_text, severity, evidence) VALUES (%s, %s, %s, %s, %s)",
            (incident_id, cause_type, cause_text, severity, evidence),
            commit=True
        )
        return (ok, True if ok else None, err)

    def StoreFix(self, params):
        incident_id = self._p(params, "incident_id", 0)
        fix_type = self._p(params, "fix_type", "recommended")
        fix_action = self._p(params, "fix_action", "")
        result = self._p(params, "result", "untried")
        confidence = self._p(params, "confidence", 0.0)
        if not incident_id or not fix_action:
            return (0, None, ("ERR_PARAMS", "incident_id and fix_action required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO fix (incident_id, fix_type, fix_action, result, confidence) VALUES (%s, %s, %s, %s, %s)",
            (incident_id, fix_type, fix_action, result, confidence),
            commit=True
        )
        return (ok, True if ok else None, err)

    def StorePrevention(self, params):
        incident_id = self._p(params, "incident_id", 0)
        prevention_type = self._p(params, "prevention_type", "guard")
        rule_text = self._p(params, "rule_text", "")
        description = self._p(params, "description", "")
        if not incident_id or not rule_text:
            return (0, None, ("ERR_PARAMS", "incident_id and rule_text required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO prevention (incident_id, prevention_type, rule_text, description) VALUES (%s, %s, %s, %s)",
            (incident_id, prevention_type, rule_text, description),
            commit=True
        )
        return (ok, True if ok else None, err)

    def StoreEvidence(self, params):
        incident_id = self._p(params, "incident_id", 0)
        evidence_type = self._p(params, "evidence_type", "")
        content = self._p(params, "content", "")
        source_file = self._p(params, "source_file", "")
        source_line = self._p(params, "source_line", 0)
        if not incident_id or not content:
            return (0, None, ("ERR_PARAMS", "incident_id and content required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO evidence (incident_id, evidence_type, source_file, source_line, content) VALUES (%s, %s, %s, %s, %s)",
            (incident_id, evidence_type, source_file, source_line, content),
            commit=True
        )
        return (ok, True if ok else None, err)

    # ================================================================
    # PROBLEM — type-level operations
    # ================================================================

    def FindProblem(self, params):
        search = self._p(params, "search", "")
        if not search:
            return (0, None, ("ERR_PARAMS", "search required", 0))
        ok, results, err = self._safe_execute(
            "SELECT * FROM problem WHERE problem LIKE %s ORDER BY occurrence_count DESC LIMIT 10",
            ("%" + search + "%",), fetch=True
        )
        return (ok, results, err)

    def CreateProblem(self, params):
        problem = self._p(params, "problem", "")
        description = self._p(params, "description", "")
        problem_type = self._p(params, "problem_type", "")
        category = self._p(params, "category", "")
        if not problem:
            return (0, None, ("ERR_PARAMS", "problem required", 0))
        ok, existing, _ = self._safe_execute(
            "SELECT id FROM problem WHERE problem=%s", (problem,), fetchone=True
        )
        if ok and existing:
            self._safe_execute(
                "UPDATE problem SET occurrence_count=occurrence_count+1, last_seen=NOW() WHERE id=%s",
                (existing["id"],), commit=True
            )
            return (1, existing["id"], None)
        ok, insert_id, err = self._safe_execute(
            "INSERT INTO problem (problem, description, problem_type, category) VALUES (%s, %s, %s, %s)",
            (problem, description, problem_type, category),
            commit=True
        )
        if not ok:
            return (ok, None, err)
        problem_id = insert_id if isinstance(insert_id, int) and insert_id > 0 else 0
        self.state["stats"]["problems"] += 1
        return (1, problem_id, None)

    def AddSolution(self, params):
        problem_id = self._p(params, "problem_id", 0)
        solution = self._p(params, "solution", "")
        weight = self._p(params, "weight", 0.5)
        auto_apply = self._p(params, "auto_apply", 0)
        if not problem_id or not solution:
            return (0, None, ("ERR_PARAMS", "problem_id and solution required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO problem_solution (problem_id, solution, weight, auto_apply) VALUES (%s, %s, %s, %s)",
            (problem_id, solution, weight, auto_apply),
            commit=True
        )
        return (ok, True if ok else None, err)

    def AddRule(self, params):
        pattern = self._p(params, "pattern", "")
        fix_action = self._p(params, "fix_action", "")
        category = self._p(params, "category", "")
        confidence = self._p(params, "confidence", 0.0)
        problem_id = self._p(params, "problem_id", None)
        if not pattern or not fix_action:
            return (0, None, ("ERR_PARAMS", "pattern and fix_action required", 0))
        ok, _, err = self._safe_execute(
            "INSERT INTO rule (pattern, fix_action, category, confidence, problem_id) VALUES (%s, %s, %s, %s, %s)",
            (pattern, fix_action, category, confidence, problem_id),
            commit=True
        )
        if ok:
            self.state["stats"]["rules"] += 1
        return (ok, True if ok else None, err)

    def LinkIncidentProblem(self, params):
        incident_id = self._p(params, "incident_id", 0)
        problem_id = self._p(params, "problem_id", 0)
        if not incident_id or not problem_id:
            return (0, None, ("ERR_PARAMS", "incident_id and problem_id required", 0))
        ok, _, err = self._safe_execute(
            "INSERT IGNORE INTO incident_problem (incident_id, problem_id) VALUES (%s, %s)",
            (incident_id, problem_id),
            commit=True
        )
        return (ok, True if ok else None, err)

    # ================================================================
    # RETRIEVE — read operations
    # ================================================================

    def GetIncident(self, params):
        incident_id = self._p(params, "incident_id", 0)
        if not incident_id:
            return (0, None, ("ERR_PARAMS", "incident_id required", 0))
        ok, incident, err = self._safe_execute(
            "SELECT * FROM incident WHERE id=%s", (incident_id,), fetchone=True
        )
        if not ok or not incident:
            return (ok, None, err)
        ok2, facts, _ = self._safe_execute(
            "SELECT * FROM fact WHERE incident_id=%s ORDER BY id", (incident_id,), fetch=True
        )
        incident["facts"] = facts if facts else []
        return (1, incident, None)

    def GetDiagnosis(self, params):
        incident_id = self._p(params, "incident_id", 0)
        if not incident_id:
            return (0, None, ("ERR_PARAMS", "incident_id required", 0))
        ok, answers, err = self._safe_execute(
            "SELECT * FROM answer WHERE incident_id=%s ORDER BY category, id", (incident_id,), fetch=True
        )
        return (ok, answers, err)

    def SearchProblems(self, params):
        search = self._p(params, "search", "")
        if not search:
            return (0, None, ("ERR_PARAMS", "search required", 0))
        ok, results, err = self._safe_execute(
            "SELECT p.*, COUNT(ps.id) as solution_count FROM problem p LEFT JOIN problem_solution ps ON p.id=ps.problem_id WHERE p.problem LIKE %s GROUP BY p.id ORDER BY p.occurrence_count DESC LIMIT 20",
            ("%" + search + "%",), fetch=True
        )
        return (ok, results, err)

    def SearchRules(self, params):
        search = self._p(params, "search", "")
        if not search:
            return (0, None, ("ERR_PARAMS", "search required", 0))
        ok, results, err = self._safe_execute(
            "SELECT * FROM rule WHERE pattern LIKE %s OR fix_action LIKE %s ORDER BY confidence DESC LIMIT 20",
            ("%" + search + "%", "%" + search + "%"), fetch=True
        )
        return (ok, results, err)

    def SearchSolutions(self, params):
        search = self._p(params, "search", "")
        if not search:
            return (0, None, ("ERR_PARAMS", "search required", 0))
        ok, results, err = self._safe_execute(
            "SELECT ps.*, p.problem FROM problem_solution ps JOIN problem p ON ps.problem_id=p.id WHERE ps.solution LIKE %s OR p.problem LIKE %s ORDER BY ps.weight DESC LIMIT 20",
            ("%" + search + "%", "%" + search + "%"), fetch=True
        )
        return (ok, results, err)
