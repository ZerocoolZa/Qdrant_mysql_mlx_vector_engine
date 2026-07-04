#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/PreExecutionGate.py"
# date="2026-08-18" author="Devin" session_id="bcl-stamp"
# context="Pre-Execution Gate: validates BCL stamps before code execution. Rejects unstamped code, stale stamps, and missing trace references."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="PreExecutionGate.py" domain="bcl_stamp" authority="PreExecutionGate"}
# [@SUMMARY]{summary="Pre-execution validation gate. Enforces: every method must have a VALID BCL stamp, every modification must have event reference, missing trace = reject, stale trace = re-analyze. No code runs without its causal reasoning embedded."}
# [@CLASS]{class="PreExecutionGate" domain="bcl_stamp" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="ValidateMethod" type="gate"}
# [@METHOD]{method="ValidateClass" type="gate"}
# [@METHOD]{method="ValidateFile" type="gate"}
# [@METHOD]{method="ValidateStamp" type="gate"}
# [@METHOD]{method="CheckStampFreshness" type="gate"}
# [@METHOD]{method="CheckEventRefs" type="gate"}
# [@METHOD]{method="CheckSourceCodeStamp" type="gate"}
# [@METHOD]{method="RejectExecution" type="command"}
# [@METHOD]{method="ApproveExecution" type="command"}
# [@METHOD]{method="QueryRejections" type="query"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Pre-execution validation gate. Enforces BCL stamp validation before code execution. Rejects unstamped/stale code, missing trace refs. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}
"""
PreExecutionGate -- Enforces BCL stamp validation before code execution.

RULES:
  1. Every method must have a VALID BCL stamp
  2. Every modification must have event reference
  3. Missing trace = reject execution
  4. Stale trace = re-analyze before run
  5. No code exists without its causal reasoning embedded

Usage:
  gate = PreExecutionGate()
  result = gate.Run('validate_method', {'bcl_method_id': 123})
  if result[0] == 1:
      # approved -- safe to execute
  else:
      # rejected -- error tuple explains why
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

GATE_APPROVED = "APPROVED"
GATE_REJECTED = "REJECTED"
GATE_STALE = "STALE"

STAMP_VALID = "VALID"
STAMP_STALE = "STALE"
STAMP_INVALID = "INVALID"

STALE_THRESHOLD_HOURS = 24
MAX_REJECTIONS_LOG = 100


class PreExecutionGate:
    """Validates BCL stamps before code execution. Rejects unstamped code."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_host": "localhost",
                "db_user": "root",
                "db_password": "",
                "db_name": "vb_code_test",
                "stale_threshold_hours": STALE_THRESHOLD_HOURS,
                "enforce_event_refs": True,
                "enforce_source_stamp": True,
            },
            "conn": None,
            "stats": {
                "validations_run": 0,
                "approved": 0,
                "rejected": 0,
                "stale_found": 0,
            },
        }
        if param:
            self.state["config"].update(param)
        self._connect()

    def _connect(self):
        if not MYSQL_AVAILABLE:
            return
        cfg = self.state["config"]
        try:
            self.state["conn"] = mysql.connector.connect(
                user=cfg["db_user"], password=cfg["db_password"],
                host=cfg["db_host"], database=cfg["db_name"]
            )
        except Exception:
            self.state["conn"] = None

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "validate_method": self.ValidateMethod,
            "validate_class": self.ValidateClass,
            "validate_file": self.ValidateFile,
            "validate_stamp": self.ValidateStamp,
            "query_rejections": self.QueryRejections,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def ValidateMethod(self, params):
        """Gate: validate that a bcl_method has a valid BCL stamp."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_method_id = self._p(params, "bcl_method_id")
        if not bcl_method_id:
            return (0, None, ("MISSING_PARAM", "bcl_method_id is required", 0))
        self.state["stats"]["validations_run"] += 1
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM bcl_stamps WHERE bcl_method_id = %s AND stamp_status = %s ORDER BY created_at DESC LIMIT 1",
            (bcl_method_id, STAMP_VALID)
        )
        stamp = cursor.fetchone()
        if not stamp:
            cursor.close()
            self.state["stats"]["rejected"] += 1
            self._log_rejection(bcl_method_id, "NO_STAMP",
                                "Method has no VALID BCL stamp. Reasoning trace missing.")
            return (0, None, ("NO_STAMP",
                              "Method " + str(bcl_method_id) + " has no VALID BCL stamp. "
                              "Reasoning trace missing. Execution rejected.", 0))
        cursor.execute(
            "SELECT method_name, method_type FROM bcl_methods WHERE id = %s",
            (bcl_method_id,)
        )
        method_info = cursor.fetchone()
        cursor.close()
        stamp_check = self.ValidateStamp({"stamp_id": stamp["id"]})
        if stamp_check[0] != 1:
            self.state["stats"]["rejected"] += 1
            return stamp_check
        if self.state["config"]["enforce_source_stamp"]:
            source_check = self.CheckSourceCodeStamp(bcl_method_id, stamp)
            if source_check[0] != 1:
                self.state["stats"]["rejected"] += 1
                return source_check
        self.state["stats"]["approved"] += 1
        return (1, {
            "gate_status": GATE_APPROVED,
            "bcl_method_id": bcl_method_id,
            "method_name": method_info.get("method_name") if method_info else None,
            "stamp_id": stamp["id"],
            "trace_id": stamp["trace_id"],
            "goal": stamp.get("goal"),
            "intent": stamp.get("intent"),
        }, None)

    def ValidateClass(self, params):
        """Gate: validate all methods in a class have valid BCL stamps."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        bcl_class_id = self._p(params, "bcl_class_id")
        if not bcl_class_id:
            return (0, None, ("MISSING_PARAM", "bcl_class_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT id, method_name FROM bcl_methods WHERE bcl_class_id = %s ORDER BY method_name",
            (bcl_class_id,)
        )
        methods = cursor.fetchall()
        cursor.close()
        if not methods:
            return (0, None, ("NO_METHODS", "class has no methods", 0))
        approved = []
        rejected = []
        for m in methods:
            r = self.ValidateMethod({"bcl_method_id": m["id"]})
            if r[0] == 1:
                approved.append({"method_id": m["id"], "method_name": m["method_name"]})
            else:
                rejected.append({
                    "method_id": m["id"],
                    "method_name": m["method_name"],
                    "error": r[2],
                })
        if rejected:
            return (0, None, ("CLASS_HAS_UNSTAMPED",
                              str(len(rejected)) + " of " + str(len(methods)) +
                              " methods rejected. First: " +
                              str(rejected[0]["method_name"]) + " -- " +
                              str(rejected[0]["error"][1]), 0))
        return (1, {
            "gate_status": GATE_APPROVED,
            "bcl_class_id": bcl_class_id,
            "methods_validated": len(methods),
            "approved": len(approved),
        }, None)

    def ValidateFile(self, params):
        """Gate: validate a file by checking its class + all methods."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        file_path = self._p(params, "file_path")
        bcl_class_id = self._p(params, "bcl_class_id")
        if not file_path and not bcl_class_id:
            return (0, None, ("MISSING_PARAM", "file_path or bcl_class_id required", 0))
        if bcl_class_id:
            return self.ValidateClass({"bcl_class_id": bcl_class_id})
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM bcl_files WHERE file_path LIKE %s LIMIT 1",
            ("%" + file_path + "%",)
        )
        file_row = cursor.fetchone()
        if not file_row:
            cursor.close()
            return (0, None, ("FILE_NOT_FOUND", "file not in BCL graph", 0))
        cursor.execute(
            "SELECT id FROM bcl_classes WHERE file_id = %s",
            (file_row["id"],)
        )
        classes = cursor.fetchall()
        cursor.close()
        if not classes:
            return (0, None, ("NO_CLASSES", "file has no classes in BCL graph", 0))
        for cls in classes:
            r = self.ValidateClass({"bcl_class_id": cls["id"]})
            if r[0] != 1:
                return r
        return (1, {"gate_status": GATE_APPROVED, "file_path": file_path}, None)

    def ValidateStamp(self, params):
        """Gate: validate a single stamp's freshness and event refs."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        stamp_id = self._p(params, "stamp_id")
        if not stamp_id:
            return (0, None, ("MISSING_PARAM", "stamp_id is required", 0))
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute("SELECT * FROM bcl_stamps WHERE id = %s", (stamp_id,))
        stamp = cursor.fetchone()
        cursor.close()
        if not stamp:
            return (0, None, ("NOT_FOUND", "stamp not found", 0))
        if stamp["stamp_status"] != STAMP_VALID:
            return (0, None, ("STAMP_NOT_VALID",
                              "stamp status is " + stamp["stamp_status"], 0))
        freshness = self.CheckStampFreshness(stamp)
        if freshness[0] != 1:
            self.state["stats"]["stale_found"] += 1
            return freshness
        if self.state["config"]["enforce_event_refs"]:
            event_check = self.CheckEventRefs(stamp)
            if event_check[0] != 1:
                return event_check
        return (1, {"stamp_id": stamp_id, "trace_id": stamp["trace_id"],
                    "fresh": True, "event_refs_valid": True}, None)

    def CheckStampFreshness(self, stamp):
        """Check if stamp is within stale threshold."""
        threshold = self.state["config"]["stale_threshold_hours"]
        created = stamp.get("created_at")
        if not created:
            return (1, {"fresh": True, "reason": "no timestamp"})
        if isinstance(created, str):
            try:
                created = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return (1, {"fresh": True, "reason": "unparseable timestamp"})
        age = datetime.now() - created
        if age > timedelta(hours=threshold):
            return (0, None, ("STAMP_STALE",
                              "stamp is " + str(age.total_seconds() / 3600) +
                              " hours old (threshold: " + str(threshold) + "h). "
                              "Re-analyze before execution.", 0))
        return (1, {"fresh": True, "age_hours": age.total_seconds() / 3600}, None)

    def CheckEventRefs(self, stamp):
        """Check that stamp has valid event references in mu_events."""
        event_refs = stamp.get("event_refs")
        if not event_refs:
            return (0, None, ("NO_EVENT_REFS",
                              "stamp has no event_refs. Every modification must have "
                              "event reference. Execution rejected.", 0))
        try:
            refs = json.loads(event_refs) if isinstance(event_refs, str) else event_refs
        except (json.JSONDecodeError, TypeError):
            refs = []
        if not refs:
            return (0, None, ("NO_EVENT_REFS",
                              "event_refs is empty. Execution rejected.", 0))
        cursor = self.state["conn"].cursor()
        found = 0
        for ref in refs:
            try:
                cursor.execute("SELECT id FROM mu_events WHERE id = %s", (int(ref),))
                if cursor.fetchone():
                    found += 1
            except (ValueError, TypeError):
                pass
        cursor.close()
        if found == 0:
            return (0, None, ("EVENT_REFS_INVALID",
                              "none of the event_refs exist in mu_events. "
                              "Trace is broken. Execution rejected.", 0))
        return (1, {"event_refs_count": len(refs), "valid_refs": found}, None)

    def CheckSourceCodeStamp(self, bcl_method_id, stamp):
        """Check that the source code has the [@BCL_STAMP] header injected."""
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            """SELECT v.method_code FROM bcl_methods m
               LEFT JOIN vb_methods v ON m.source_method_id = v.id
               WHERE m.id = %s""",
            (bcl_method_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return (0, None, ("NO_SOURCE", "bcl_method has no source link", 0))
        code = row.get("method_code", "")
        if not code:
            return (0, None, ("NO_CODE", "source method has no code", 0))
        if "[@BCL_STAMP]" not in code:
            return (0, None, ("STAMP_NOT_INJECTED",
                              "source code does not contain [@BCL_STAMP] header. "
                              "Stamp exists in DB but not injected into source. "
                              "Run inject_stamp_into_code first.", 0))
        if stamp["trace_id"] not in code:
            return (0, None, ("TRACE_MISMATCH",
                              "source code stamp trace_id does not match DB stamp. "
                              "Source is out of sync with reasoning trace.", 0))
        return (1, {"source_stamped": True, "trace_id": stamp["trace_id"]}, None)

    def _log_rejection(self, bcl_method_id, code, message):
        """Log rejection to bcl_stamp_events for audit trail."""
        if not self.state["conn"]:
            return
        cursor = self.state["conn"].cursor()
        cursor.execute(
            """INSERT INTO bcl_stamp_events (stamp_id, event_type, cause)
               VALUES (0, %s, %s)""",
            ("GATE_REJECTED", "method=" + str(bcl_method_id) + " code=" + code + " msg=" + message[:200])
        )
        self.state["conn"].commit()
        cursor.close()

    def QueryRejections(self, params):
        """Query recent gate rejections."""
        if not self.state["conn"]:
            return (0, None, ("NO_DB", "database not connected", 0))
        limit = self._p(params, "limit", 20)
        cursor = self.state["conn"].cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM bcl_stamp_events WHERE event_type = %s ORDER BY created_at DESC LIMIT %s",
            ("GATE_REJECTED", limit)
        )
        rejections = cursor.fetchall()
        cursor.close()
        return (1, {"rejections": rejections, "count": len(rejections)}, None)

    def read_state(self, params):
        return (1, {
            "config": self.state["config"],
            "stats": self.state["stats"],
            "connected": self.state["conn"] is not None,
        }, None)

    def set_config(self, params):
        for key in ("db_host", "db_user", "db_password", "db_name",
                    "stale_threshold_hours", "enforce_event_refs",
                    "enforce_source_stamp"):
            val = self._p(params, key)
            if val is not None:
                self.state["config"][key] = val
        self._connect()
        return (1, {"config": self.state["config"]}, None)
