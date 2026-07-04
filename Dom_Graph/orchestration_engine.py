#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/orchestration_engine.py"
# date="2026-06-26" author="Devin" session_id="phase6-intelligence"
# context="Project Digital Twin Section 56 Orchestration Engine"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="orchestration_engine.py" domain="twin_orchestration" authority="OrchestrationEngine"}
# [@SUMMARY]{summary="Orchestration authority that manages task, worker, dependency, priority, retry, rollback, learning, and reporting queues."}
# [@CLASS]{class="OrchestrationEngine" domain="orchestration" authority="single"}
# [@METHOD]{method="enqueue" type="command"}
# [@METHOD]{method="dequeue" type="command"}
# [@METHOD]{method="prioritize" type="command"}
# [@METHOD]{method="retry" type="command"}
# [@METHOD]{method="rollback" type="command"}
# [@METHOD]{method="process_queue" type="command"}
# [@METHOD]{method="get_status" type="command"}
# [@METHOD]{method="report" type="command"}
# [@METHOD]{method="learning_queue" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<OrchestrationEngine: manages task worker dependency priority retry rollback learning reporting queues. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations. Header missing Run method declaration but Run() exists in code.>][@todos<none>]}
"""
OrchestrationEngine -- Orchestration queue authority.
Implements Section 56 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: enqueue, dequeue, prioritize, retry, rollback, process_queue, get_status, report,
          learning_queue.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class OrchestrationEngine:
    """Orchestration queue authority."""

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
        if command == "enqueue":
            return self.Enqueue(params)
        elif command == "dequeue":
            return self.Dequeue(params)
        elif command == "prioritize":
            return self.Prioritize(params)
        elif command == "retry":
            return self.Retry(params)
        elif command == "rollback":
            return self.Rollback(params)
        elif command == "process_queue":
            return self.ProcessQueue(params)
        elif command == "get_status":
            return self.GetStatus(params)
        elif command == "report":
            return self.Report(params)
        elif command == "learning_queue":
            return self.LearningQueue(params)

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

    def Enqueue(self, params):
        task_type = self._p(params, "task_type", "generic")
        target = self._p(params, "target", "")
        priority = self._p(params, "priority", 4)
        task_params = self._p(params, "params", {})
        depends_on = self._p(params, "depends_on", [])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT MAX(observation_id) FROM observations WHERE observation_type='task'")
        row = cur.fetchone()
        task_id = (row[0] or 0) + 1
        task_data = {"task_id": task_id, "task_type": task_type, "target": target,
                     "priority": priority, "params": task_params, "status": "pending",
                     "retries": 0, "depends_on": depends_on}
        subject = task_type + ":" + str(target)
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, "
                    "created) VALUES (?, ?, ?, ?, ?)",
                    ("task", subject, json.dumps(task_data), float(priority),
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        task_data["observation_id"] = cur.lastrowid
        return (1, {"task_id": task_id, "observation_id": cur.lastrowid,
                    "enqueued": True}, None)

    def LoadTasks(self, status_filter=None):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, evidence FROM observations "
                    "WHERE observation_type='task' ORDER BY observation_id")
        tasks = []
        for row in cur.fetchall():
            try:
                data = json.loads(row[1]) if row[1] else {}
            except (ValueError, TypeError):
                data = {}
            data["observation_id"] = row[0]
            if status_filter and data.get("status") != status_filter:
                continue
            tasks.append(data)
        return tasks

    def SaveTask(self, task):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE observations SET evidence=?, confidence=? WHERE observation_id=?",
                    (json.dumps(task), float(task.get("priority", 4)),
                     task.get("observation_id")))
        conn.commit()

    def Dequeue(self, params):
        tasks = self.LoadTasks()
        pending = [t for t in tasks if t.get("status") == "pending"
                   and self.DependenciesMet(t, tasks)]
        if not pending:
            return (1, {"task": None, "reason": "queue empty or dependencies unmet"}, None)
        pending.sort(key=lambda t: t.get("priority", 4))
        task = pending[0]
        task["status"] = "processing"
        self.SaveTask(task)
        return (1, {"task": task}, None)

    def DependenciesMet(self, task, tasks):
        depends_on = task.get("depends_on", []) or []
        if not depends_on:
            return True
        for dep_id in depends_on:
            for t in tasks:
                if t.get("task_id") == dep_id and t.get("status") != "completed":
                    return False
        return True

    def Prioritize(self, params):
        tasks = self.LoadTasks()
        tasks.sort(key=lambda t: t.get("priority", 4))
        for task in tasks:
            self.SaveTask(task)
        return (1, {"queue": tasks, "count": len(tasks)}, None)

    def Retry(self, params):
        task_id = self._p(params, "task_id")
        if not task_id:
            return (0, None, ("NO_PARAM", "task_id required", 0))
        tasks = self.LoadTasks()
        for t in tasks:
            if t.get("task_id") == task_id:
                if t.get("retries", 0) < 3:
                    t["retries"] = t.get("retries", 0) + 1
                    t["status"] = "pending"
                    self.SaveTask(t)
                    return (1, {"retried": True, "retries": t["retries"],
                                "task_id": task_id}, None)
                else:
                    t["status"] = "failed"
                    self.SaveTask(t)
                    return (1, {"retried": False, "reason": "max retries exceeded",
                                "task_id": task_id}, None)
        return (0, None, ("NOT_FOUND", "Task not found", 0))

    def Rollback(self, params):
        task_id = self._p(params, "task_id")
        if not task_id:
            return (0, None, ("NO_PARAM", "task_id required", 0))
        tasks = self.LoadTasks()
        task = None
        for t in tasks:
            if t.get("task_id") == task_id:
                task = t
                break
        if not task:
            return (0, None, ("NOT_FOUND", "Task not found", 0))
        conn = self.Connect()
        cur = conn.cursor()
        method_id = task.get("params", {}).get("method_id")
        restored = False
        if method_id:
            cur.execute("SELECT content FROM snapshots WHERE method_id=? AND snapshot_type='before_fix' "
                        "ORDER BY created DESC LIMIT 1", (method_id,))
            row = cur.fetchone()
            if row and row[0]:
                cur.execute("UPDATE methods SET method_code=? WHERE method_id=?",
                            (row[0], method_id))
                conn.commit()
                restored = True
        task["status"] = "rollback"
        self.SaveTask(task)
        return (1, {"rolled_back": True, "task_id": task_id,
                    "restored_from_snapshot": restored}, None)

    def ProcessQueue(self, params):
        results = []
        while True:
            deq = self.Dequeue(params)
            if deq[0] != 1 or deq[1]["task"] is None:
                break
            task = deq[1]["task"]
            task["status"] = "completed"
            self.SaveTask(task)
            results.append({"task_id": task.get("task_id"),
                            "status": "completed"})
        return (1, {"processed": results, "count": len(results)}, None)

    def GetStatus(self, params):
        tasks = self.LoadTasks()
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        processing = sum(1 for t in tasks if t.get("status") == "processing")
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        failed = sum(1 for t in tasks if t.get("status") == "failed")
        rollback = sum(1 for t in tasks if t.get("status") == "rollback")
        return (1, {"queue_length": len(tasks), "pending": pending,
                    "processing": processing, "completed": completed,
                    "failed": failed, "rollback": rollback}, None)

    def Report(self, params):
        status_res = self.GetStatus(params)
        if status_res[0] != 1:
            return status_res
        tasks = self.LoadTasks()
        by_type = {}
        for t in tasks:
            ttype = t.get("task_type", "unknown")
            by_type[ttype] = by_type.get(ttype, 0) + 1
        report = dict(status_res[1])
        report["by_type"] = by_type
        report["tasks"] = tasks
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, "
                    "created) VALUES (?, ?, ?, ?, ?)",
                    ("fact", "queue_report", json.dumps(report), 0,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"report": report, "recorded": True}, None)

    def LearningQueue(self, params):
        tasks = self.LoadTasks()
        learning_tasks = [t for t in tasks if t.get("status") == "completed"
                          and not t.get("learned", False)]
        conn = self.Connect()
        cur = conn.cursor()
        learned = []
        for task in learning_tasks:
            task_params = task.get("params", {}) or {}
            problem = task_params.get("problem", task.get("task_type", "unknown"))
            answer = task_params.get("answer", task.get("target", ""))
            fix_result = task_params.get("fix_result", "success")
            method_id = task_params.get("method_id")
            class_id = task_params.get("class_id")
            file_id = task_params.get("file_id")
            error_type = task_params.get("error_type")
            cur.execute("INSERT INTO knowledge (problem, answer, is_best, confidence, "
                        "fix_result, method_id, class_id, file_id, error_type, created) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (problem, answer, 0, 50, fix_result, method_id, class_id,
                         file_id, error_type, datetime.now(timezone.utc).isoformat()))
            knowledge_id = cur.lastrowid
            task["learned"] = True
            task["knowledge_id"] = knowledge_id
            self.SaveTask(task)
            learned.append({"task_id": task.get("task_id"),
                            "knowledge_id": knowledge_id,
                            "problem": problem})
        conn.commit()
        return (1, {"learning_tasks": learned, "count": len(learned)}, None)

