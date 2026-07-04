#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/audit_trail_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 40: Audit Trail -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="audit_trail_engine.py" domain="twin_audit" authority="AuditTrailEngine"}
# [@SUMMARY]{summary="Audit trail authority: log action, log change, log fix, log observation, log experiment, log learning, log rollback, log verification, query audit trail, audit report."}
# [@CLASS]{class="AuditTrailEngine" domain="audit_trail" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="log_action" type="command"}
# [@METHOD]{method="log_change" type="command"}
# [@METHOD]{method="log_fix" type="command"}
# [@METHOD]{method="log_observation" type="command"}
# [@METHOD]{method="log_experiment" type="command"}
# [@METHOD]{method="log_learning" type="command"}
# [@METHOD]{method="log_rollback" type="command"}
# [@METHOD]{method="log_verification" type="command"}
# [@METHOD]{method="query_audit_trail" type="command"}
# [@METHOD]{method="audit_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class AuditTrailEngine:
    """Authority for logging and querying audit trails."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "log_action":
            return self.LogAction(params)
        elif command == "log_change":
            return self.LogChange(params)
        elif command == "log_fix":
            return self.LogFix(params)
        elif command == "log_observation":
            return self.LogObservation(params)
        elif command == "log_experiment":
            return self.LogExperiment(params)
        elif command == "log_learning":
            return self.LogLearning(params)
        elif command == "log_rollback":
            return self.LogRollback(params)
        elif command == "log_verification":
            return self.LogVerification(params)
        elif command == "query_audit_trail":
            return self.QueryAuditTrail(params)
        elif command == "audit_report":
            return self.AuditReport(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def InsertLog(self, log_type, subject, evidence, confidence):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES (?, ?, ?, ?, ?)",
                (log_type, subject, evidence, confidence, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid, "log_type": log_type}, None)

    def LogAction(self, params):
        action = self._p(params, "action")
        details = self._p(params, "details", "")
        if action is None:
            return (0, None, ("MISSING_PARAM", "action required", 0))
        return self.InsertLog("audit_action", action, details, 50.0)

    def LogChange(self, params):
        entity_type = self._p(params, "entity_type")
        entity_id = self._p(params, "entity_id")
        change = self._p(params, "change", "")
        if entity_type is None or entity_id is None:
            return (0, None, ("MISSING_PARAM",
                              "entity_type and entity_id required", 0))
        subject = entity_type + ":" + str(entity_id)
        return self.InsertLog("audit_change", subject, change, 70.0)

    def LogFix(self, params):
        attempt_id = self._p(params, "attempt_id")
        method_id = self._p(params, "method_id")
        result = self._p(params, "result", "")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        subject = "attempt:" + str(attempt_id)
        evidence = "method:" + str(method_id) + " result:" + str(result)
        return self.InsertLog("audit_fix", subject, evidence, 80.0)

    def LogObservation(self, params):
        observation_id = self._p(params, "observation_id")
        obs_type = self._p(params, "observation_type", "")
        if observation_id is None:
            return (0, None, ("MISSING_PARAM", "observation_id required", 0))
        return self.InsertLog("audit_observation", str(observation_id), obs_type, 60.0)

    def LogExperiment(self, params):
        experiment_name = self._p(params, "experiment_name")
        outcome = self._p(params, "outcome", "")
        if experiment_name is None:
            return (0, None, ("MISSING_PARAM", "experiment_name required", 0))
        return self.InsertLog("audit_experiment", experiment_name, outcome, 75.0)

    def LogLearning(self, params):
        lesson = self._p(params, "lesson")
        source = self._p(params, "source", "")
        if lesson is None:
            return (0, None, ("MISSING_PARAM", "lesson required", 0))
        return self.InsertLog("audit_learning", lesson, source, 85.0)

    def LogRollback(self, params):
        attempt_id = self._p(params, "attempt_id")
        reason = self._p(params, "reason", "")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        return self.InsertLog("audit_rollback", str(attempt_id), reason, 90.0)

    def LogVerification(self, params):
        target = self._p(params, "target")
        result = self._p(params, "result", "")
        if target is None:
            return (0, None, ("MISSING_PARAM", "target required", 0))
        return self.InsertLog("audit_verification", target, result, 80.0)

    def QueryAuditTrail(self, params):
        log_type = self._p(params, "log_type")
        limit = self._p(params, "limit", 50)
        conn = self.Connect()[1]
        cur = conn.cursor()
        if log_type:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, created FROM observations WHERE observation_type=? "
                "ORDER BY created DESC LIMIT ?",
                (log_type, limit),
            )
        else:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, created FROM observations WHERE observation_type LIKE 'audit_%' "
                "ORDER BY created DESC LIMIT ?",
                (limit,),
            )
        entries = [{"observation_id": r[0], "type": r[1], "subject": r[2],
                    "evidence": r[3], "confidence": r[4], "created": r[5]}
                   for r in cur.fetchall()]
        return (1, {"entries": entries, "count": len(entries)}, None)

    def AuditReport(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT observation_type, COUNT(*) FROM observations WHERE observation_type LIKE 'audit_%' GROUP BY observation_type")
        by_type = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM observations WHERE observation_type LIKE 'audit_%'")
        total = cur.fetchone()[0]
        return (1, {"total_audit_entries": total, "by_type": by_type,
                    "generated": self.Now()[1]}, None)
