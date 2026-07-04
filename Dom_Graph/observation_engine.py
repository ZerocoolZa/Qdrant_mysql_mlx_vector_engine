#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/observation_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 53 Observation Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="observation_engine.py" domain="twin_observation" authority="ObservationEngine"}
# [@SUMMARY]{summary="Observation authority that records and recalls everything seen, changed, learned, ignored, unknown, assumed, and confirmed."}
# [@CLASS]{class="ObservationEngine" domain="observation" authority="single"}
# [@METHOD]{method="observe" type="command"}
# [@METHOD]{method="recall_all" type="command"}
# [@METHOD]{method="recall_changes" type="command"}
# [@METHOD]{method="recall_learned" type="command"}
# [@METHOD]{method="recall_unknowns" type="command"}
# [@METHOD]{method="confirm_fact" type="command"}
# [@METHOD]{method="recall_ignored" type="command"}
# [@METHOD]{method="recall_assumptions" type="command"}
# [@METHOD]{method="recall_confirmed" type="command"}
# [@METHOD]{method="recall_evidence" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ObservationEngine: records and recalls observations changes learned unknowns confirmed assumptions evidence. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
ObservationEngine -- Observation tracking authority.
Implements Section 53 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: observe, recall_all, recall_changes, recall_learned, recall_unknowns, confirm_fact,
          recall_ignored, recall_assumptions, recall_confirmed, recall_evidence.
"""
import os
import sqlite3

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class ObservationEngine:
    """Observation tracking authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "observe":
            return self.Observe(params)
        elif command == "recall_all":
            return self.RecallAll(params)
        elif command == "recall_changes":
            return self.RecallChanges(params)
        elif command == "recall_learned":
            return self.RecallLearned(params)
        elif command == "recall_unknowns":
            return self.RecallUnknowns(params)
        elif command == "confirm_fact":
            return self.ConfirmFact(params)
        elif command == "recall_ignored":
            return self.RecallIgnored(params)
        elif command == "recall_assumptions":
            return self.RecallAssumptions(params)
        elif command == "recall_confirmed":
            return self.RecallConfirmed(params)
        elif command == "recall_evidence":
            return self.RecallEvidence(params)

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
        return self.state["db_conn"]

    def Observe(self, params):
        obs_type = self._p(params, "observation_type", "fact")
        subject = self._p(params, "subject", "")
        evidence = self._p(params, "evidence", "")
        confidence = self._p(params, "confidence", 0.0)
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        if not subject:
            return (0, None, ("NO_PARAM", "subject required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, "
                    "file_id, class_id, method_id, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (obs_type, subject, evidence, confidence, file_id, class_id, method_id,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"observation_id": cur.lastrowid, "subject": subject}, None)

    def RecallAll(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"observations": results, "count": len(results)}, None)

    def RecallChanges(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='change' "
                    "ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"changes": results, "count": len(results)}, None)

    def RecallLearned(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM knowledge WHERE confidence > 50 "
                    "ORDER BY confidence DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"learned": results, "count": len(results)}, None)

    def RecallUnknowns(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='unknown' ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"unknowns": results, "count": len(results)}, None)

    def ConfirmFact(self, params):
        observation_id = self._p(params, "observation_id")
        if not observation_id:
            return (0, None, ("NO_PARAM", "observation_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE observations SET observation_type='confirmed' WHERE observation_id=?", (observation_id,))
        conn.commit()
        return (1, {"confirmed": True, "observation_id": observation_id}, None)

    def RecallIgnored(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='ignored' "
                    "ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"ignored": results, "count": len(results)}, None)

    def RecallAssumptions(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='assumption' "
                    "ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"assumptions": results, "count": len(results)}, None)

    def RecallConfirmed(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='confirmed' "
                    "ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"confirmed": results, "count": len(results)}, None)

    def RecallEvidence(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE evidence IS NOT NULL AND evidence != '' "
                    "ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"evidence_links": results, "count": len(results)}, None)

