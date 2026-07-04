#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/observation_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 21: Observation Engine -- 10 sub-sections (also covers Section 53)"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="observation_engine.py" domain="twin_observation" authority="ObservationEngine"}
# [@SUMMARY]{summary="Observation authority: observe everything seen, observe everything changed, observe everything learned, observe everything ignored, observe unknowns, observe assumptions, confirm facts, link evidence, query observations, filter observations."}
# [@CLASS]{class="ObservationEngine" domain="observation" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="observe_seen" type="command"}
# [@METHOD]{method="observe_changed" type="command"}
# [@METHOD]{method="observe_learned" type="command"}
# [@METHOD]{method="observe_ignored" type="command"}
# [@METHOD]{method="observe_unknown" type="command"}
# [@METHOD]{method="observe_assumption" type="command"}
# [@METHOD]{method="confirm_fact" type="command"}
# [@METHOD]{method="link_evidence" type="command"}
# [@METHOD]{method="query_observations" type="command"}
# [@METHOD]{method="filter_observations" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ObservationEngine:
    """Authority for recording and querying observations."""

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
        if command == "observe_seen":
            return self.ObserveSeen(params)
        elif command == "observe_changed":
            return self.ObserveChanged(params)
        elif command == "observe_learned":
            return self.ObserveLearned(params)
        elif command == "observe_ignored":
            return self.ObserveIgnored(params)
        elif command == "observe_unknown":
            return self.ObserveUnknown(params)
        elif command == "observe_assumption":
            return self.ObserveAssumption(params)
        elif command == "confirm_fact":
            return self.ConfirmFact(params)
        elif command == "link_evidence":
            return self.LinkEvidence(params)
        elif command == "query_observations":
            return self.QueryObservations(params)
        elif command == "filter_observations":
            return self.FilterObservations(params)
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

    def Insert(self, obs_type, subject, evidence, confidence, file_id, class_id, method_id):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, file_id, class_id, method_id, created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (obs_type, subject, evidence, confidence,
                 file_id, class_id, method_id, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid}, None)

    def ObserveSeen(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("seen", subject, evidence, 50.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ObserveChanged(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("changed", subject, evidence, 80.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ObserveLearned(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("learned", subject, evidence, 90.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ObserveIgnored(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("ignored", subject, evidence, 10.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ObserveUnknown(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("unknown", subject, evidence, 0.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ObserveAssumption(self, params):
        subject = self._p(params, "subject")
        evidence = self._p(params, "evidence", "")
        if subject is None:
            return (0, None, ("MISSING_PARAM", "subject required", 0))
        return self.Insert("assumption", subject, evidence, 25.0,
                           self._p(params, "file_id"),
                           self._p(params, "class_id"),
                           self._p(params, "method_id"))

    def ConfirmFact(self, params):
        observation_id = self._p(params, "observation_id")
        if observation_id is None:
            return (0, None, ("MISSING_PARAM", "observation_id required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE observations SET observation_type='confirmed_fact', "
                "confidence=95.0 WHERE observation_id=?",
                (observation_id,),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"observation_id": observation_id, "confirmed": True}, None)

    def LinkEvidence(self, params):
        observation_id = self._p(params, "observation_id")
        evidence = self._p(params, "evidence")
        if observation_id is None or evidence is None:
            return (0, None, ("MISSING_PARAM",
                              "observation_id and evidence required", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE observations SET evidence=? WHERE observation_id=?",
                        (evidence, observation_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        return (1, {"observation_id": observation_id, "linked": True}, None)

    def QueryObservations(self, params):
        obs_type = self._p(params, "observation_type")
        limit = self._p(params, "limit", 50)
        conn = self.Connect()[1]
        cur = conn.cursor()
        if obs_type:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, created FROM observations WHERE observation_type=? "
                "ORDER BY created DESC LIMIT ?",
                (obs_type, limit),
            )
        else:
            cur.execute(
                "SELECT observation_id, observation_type, subject, evidence, "
                "confidence, created FROM observations ORDER BY created DESC LIMIT ?",
                (limit,),
            )
        results = [{"observation_id": r[0], "type": r[1], "subject": r[2],
                    "evidence": r[3], "confidence": r[4], "created": r[5]}
                   for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def FilterObservations(self, params):
        min_confidence = self._p(params, "min_confidence", 0)
        max_confidence = self._p(params, "max_confidence", 100)
        limit = self._p(params, "limit", 50)
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute(
            "SELECT observation_id, observation_type, subject, confidence "
            "FROM observations WHERE confidence >= ? AND confidence <= ? "
            "ORDER BY confidence DESC LIMIT ?",
            (min_confidence, max_confidence, limit),
        )
        results = [{"observation_id": r[0], "type": r[1],
                    "subject": r[2], "confidence": r[3]}
                   for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)
