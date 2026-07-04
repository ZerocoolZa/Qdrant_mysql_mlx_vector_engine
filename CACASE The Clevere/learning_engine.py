#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/learning_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 24: Learning Engine -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="learning_engine.py" domain="twin_learning" authority="LearningEngine"}
# [@SUMMARY]{summary="Learning authority: learn from success, learn from failure, learn from observation, learn from pattern, learn from feedback, learn from comparison, learn from regression, learn from improvement, learn from contradiction, learn from repetition."}
# [@CLASS]{class="LearningEngine" domain="learning" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="learn_from_success" type="command"}
# [@METHOD]{method="learn_from_failure" type="command"}
# [@METHOD]{method="learn_from_observation" type="command"}
# [@METHOD]{method="learn_from_pattern" type="command"}
# [@METHOD]{method="learn_from_feedback" type="command"}
# [@METHOD]{method="learn_from_comparison" type="command"}
# [@METHOD]{method="learn_from_regression" type="command"}
# [@METHOD]{method="learn_from_improvement" type="command"}
# [@METHOD]{method="learn_from_contradiction" type="command"}
# [@METHOD]{method="learn_from_repetition" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"


class LearningEngine:
    """Authority for learning from outcomes and patterns."""

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
        if command == "learn_from_success":
            return self.LearnFromSuccess(params)
        elif command == "learn_from_failure":
            return self.LearnFromFailure(params)
        elif command == "learn_from_observation":
            return self.LearnFromObservation(params)
        elif command == "learn_from_pattern":
            return self.LearnFromPattern(params)
        elif command == "learn_from_feedback":
            return self.LearnFromFeedback(params)
        elif command == "learn_from_comparison":
            return self.LearnFromComparison(params)
        elif command == "learn_from_regression":
            return self.LearnFromRegression(params)
        elif command == "learn_from_improvement":
            return self.LearnFromImprovement(params)
        elif command == "learn_from_contradiction":
            return self.LearnFromContradiction(params)
        elif command == "learn_from_repetition":
            return self.LearnFromRepetition(params)
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

    def RecordLearning(self, lesson_type, subject, evidence, confidence):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, evidence, "
                "confidence, created) VALUES (?, ?, ?, ?, ?)",
                (lesson_type, subject, evidence, confidence, self.Now()[1]),
            )
            conn.commit()
        except sqlite3.Error as exc:
            return (0, None, ("INSERT_FAILED", str(exc), 0))
        return (1, {"observation_id": cur.lastrowid,
                    "lesson_type": lesson_type}, None)

    def LearnFromSuccess(self, params):
        attempt_id = self._p(params, "attempt_id")
        lesson = self._p(params, "lesson", "successful fix applied")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        return self.RecordLearning("success_lesson", str(attempt_id), lesson, 90.0)

    def LearnFromFailure(self, params):
        attempt_id = self._p(params, "attempt_id")
        lesson = self._p(params, "lesson", "fix failed and rolled back")
        if attempt_id is None:
            return (0, None, ("MISSING_PARAM", "attempt_id required", 0))
        return self.RecordLearning("failure_lesson", str(attempt_id), lesson, 80.0)

    def LearnFromObservation(self, params):
        observation_id = self._p(params, "observation_id")
        lesson = self._p(params, "lesson", "observed pattern")
        if observation_id is None:
            return (0, None, ("MISSING_PARAM", "observation_id required", 0))
        return self.RecordLearning("observation_lesson", str(observation_id), lesson, 60.0)

    def LearnFromPattern(self, params):
        pattern = self._p(params, "pattern")
        lesson = self._p(params, "lesson", "pattern detected")
        if pattern is None:
            return (0, None, ("MISSING_PARAM", "pattern required", 0))
        return self.RecordLearning("pattern_lesson", pattern, lesson, 70.0)

    def LearnFromFeedback(self, params):
        feedback = self._p(params, "feedback")
        lesson = self._p(params, "lesson", "user feedback received")
        if feedback is None:
            return (0, None, ("MISSING_PARAM", "feedback required", 0))
        return self.RecordLearning("feedback_lesson", feedback, lesson, 85.0)

    def LearnFromComparison(self, params):
        before_id = self._p(params, "before_id")
        after_id = self._p(params, "after_id")
        lesson = self._p(params, "lesson", "comparison revealed difference")
        if before_id is None or after_id is None:
            return (0, None, ("MISSING_PARAM",
                              "before_id and after_id required", 0))
        subject = str(before_id) + " vs " + str(after_id)
        return self.RecordLearning("comparison_lesson", subject, lesson, 75.0)

    def LearnFromRegression(self, params):
        method_id = self._p(params, "method_id")
        lesson = self._p(params, "lesson", "regression detected")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        return self.RecordLearning("regression_lesson", str(method_id), lesson, 85.0)

    def LearnFromImprovement(self, params):
        method_id = self._p(params, "method_id")
        lesson = self._p(params, "lesson", "improvement detected")
        if method_id is None:
            return (0, None, ("MISSING_PARAM", "method_id required", 0))
        return self.RecordLearning("improvement_lesson", str(method_id), lesson, 90.0)

    def LearnFromContradiction(self, params):
        fact1 = self._p(params, "fact1")
        fact2 = self._p(params, "fact2")
        lesson = self._p(params, "lesson", "contradiction found")
        if fact1 is None or fact2 is None:
            return (0, None, ("MISSING_PARAM",
                              "fact1 and fact2 required", 0))
        subject = fact1 + " contradicts " + fact2
        return self.RecordLearning("contradiction_lesson", subject, lesson, 70.0)

    def LearnFromRepetition(self, params):
        pattern = self._p(params, "pattern")
        count = self._p(params, "count", 1)
        lesson = self._p(params, "lesson", "repeated pattern detected")
        if pattern is None:
            return (0, None, ("MISSING_PARAM", "pattern required", 0))
        confidence = min(50 + count * 10, 100)
        return self.RecordLearning("repetition_lesson", pattern, lesson, float(confidence))
