#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/experiment_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 25: Experiment Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="experiment_engine.py" domain="twin_experiment" authority="ExperimentEngine"}
# [@SUMMARY]{summary="Experiment authority: create experiment, run experiment, compare results, rollback experiment, record outcome, learn from experiment, rank experiments, list experiments, abort experiment, archive experiment."}
# [@CLASS]{class="ExperimentEngine" domain="experiment" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="create_experiment" type="command"}
# [@METHOD]{method="run_experiment" type="command"}
# [@METHOD]{method="compare_results" type="command"}
# [@METHOD]{method="rollback_experiment" type="command"}
# [@METHOD]{method="record_outcome" type="command"}
# [@METHOD]{method="learn_from_experiment" type="command"}
# [@METHOD]{method="rank_experiments" type="command"}
# [@METHOD]{method="list_experiments" type="command"}
# [@METHOD]{method="abort_experiment" type="command"}
# [@METHOD]{method="archive_experiment" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class ExperimentEngine:
    """Authority for creating and running code experiments."""

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
            "experiments": {},
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "create_experiment":
            return self.CreateExperiment(params)
        elif command == "run_experiment":
            return self.RunExperiment(params)
        elif command == "compare_results":
            return self.CompareResults(params)
        elif command == "rollback_experiment":
            return self.RollbackExperiment(params)
        elif command == "record_outcome":
            return self.RecordOutcome(params)
        elif command == "learn_from_experiment":
            return self.LearnFromExperiment(params)
        elif command == "rank_experiments":
            return self.RankExperiments(params)
        elif command == "list_experiments":
            return self.ListExperiments(params)
        elif command == "abort_experiment":
            return self.AbortExperiment(params)
        elif command == "archive_experiment":
            return self.ArchiveExperiment(params)
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

    def CreateExperiment(self, params):
        name = self._p(params, "name")
        method_id = self._p(params, "method_id")
        original_code = self._p(params, "original_code")
        experimental_code = self._p(params, "experimental_code")
        if name is None or method_id is None:
            return (0, None, ("MISSING_PARAM",
                              "name and method_id required", 0))
        experiment = {
            "name": name,
            "method_id": method_id,
            "original_code": original_code,
            "experimental_code": experimental_code,
            "status": "created",
            "created": self.Now()[1],
        }
        self.state["experiments"][name] = experiment
        return (1, experiment, None)

    def RunExperiment(self, params):
        name = self._p(params, "name")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        method_id = exp["method_id"]
        experimental_code = exp["experimental_code"]
        if experimental_code is None:
            return (0, None, ("NO_CODE", "experimental_code is None", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        cur.execute("SELECT method_code FROM methods WHERE method_id=?",
                    (method_id,))
        row = cur.fetchone()
        if row is None:
            return (0, None, ("METHOD_NOT_FOUND", str(method_id), 0))
        exp["original_code"] = row[0]
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (experimental_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("UPDATE_FAILED", str(exc), 0))
        exp["status"] = "running"
        exp["started"] = self.Now()[1]
        return (1, {"name": name, "status": "running"}, None)

    def CompareResults(self, params):
        name = self._p(params, "name")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        original = exp.get("original_code", "")
        experimental = exp.get("experimental_code", "")
        changed = original != experimental
        return (1, {"name": name, "changed": changed,
                    "original_length": len(original),
                    "experimental_length": len(experimental)}, None)

    def RollbackExperiment(self, params):
        name = self._p(params, "name")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        original_code = exp.get("original_code")
        method_id = exp.get("method_id")
        if original_code is None or method_id is None:
            return (0, None, ("NO_ORIGINAL", "No original code to restore", 0))
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                        (original_code, method_id))
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("ROLLBACK_FAILED", str(exc), 0))
        exp["status"] = "rolled_back"
        return (1, {"name": name, "status": "rolled_back"}, None)

    def RecordOutcome(self, params):
        name = self._p(params, "name")
        success = self._p(params, "success", False)
        notes = self._p(params, "notes", "")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        exp["status"] = "success" if success else "failed"
        exp["notes"] = notes
        exp["completed"] = self.Now()[1]
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO attempts (method_id, action, before_code, after_code, "
                "compile_result, test_result, created) VALUES (?,?,?,?,?,?,?)",
                (exp["method_id"], "experiment:" + name,
                 exp.get("original_code"), exp.get("experimental_code"),
                 1 if success else 0, 1 if success else 0, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"name": name, "attempt_id": cur.lastrowid,
                    "success": success}, None)

    def LearnFromExperiment(self, params):
        name = self._p(params, "name")
        lesson = self._p(params, "lesson", "")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES ('experiment_lesson', ?, ?, ?, ?)",
                (name, lesson or exp.get("notes", ""),
                 80.0 if exp.get("status") == "success" else 70.0,
                 self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid, "learned": True}, None)

    def RankExperiments(self, params):
        experiments = list(self.state["experiments"].values())
        status_order = {"success": 0, "running": 1, "failed": 2,
                        "rolled_back": 3, "created": 4, "aborted": 5}
        ranked = sorted(experiments,
                        key=lambda e: status_order.get(e.get("status", "created"), 99))
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    def ListExperiments(self, params):
        experiments = list(self.state["experiments"].values())
        summary = [{"name": e["name"], "status": e.get("status", "created"),
                    "method_id": e.get("method_id"),
                    "created": e.get("created")}
                   for e in experiments]
        return (1, {"experiments": summary, "count": len(summary)}, None)

    def AbortExperiment(self, params):
        name = self._p(params, "name")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        if exp.get("status") == "running":
            original_code = exp.get("original_code")
            method_id = exp.get("method_id")
            if original_code and method_id:
                conn = self.Connect()[1]
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                                (original_code, method_id))
                    conn.commit()
                except sqlite3.Error:
                    pass
        exp["status"] = "aborted"
        return (1, {"name": name, "status": "aborted"}, None)

    def ArchiveExperiment(self, params):
        name = self._p(params, "name")
        if name is None or name not in self.state["experiments"]:
            return (0, None, ("NOT_FOUND", "experiment not found: " + str(name), 0))
        exp = self.state["experiments"][name]
        exp["status"] = "archived"
        exp["archived"] = self.Now()[1]
        return (1, {"name": name, "status": "archived"}, None)
