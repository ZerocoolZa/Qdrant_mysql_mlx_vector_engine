#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/error_resistance.py"
# date="2026-06-26" author="Devin" session_id="phase7-meta"
# context="Project Digital Twin Phase 7 Section 73 Error Resistance"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="error_resistance.py" domain="twin_resistance" authority="ErrorResistance"}
# [@SUMMARY]{summary="Error resistance authority that validates instructions, resolves rule conflicts, provides safe fallbacks and recovers partial results."}
# [@CLASS]{class="ErrorResistance" domain="resistance" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="validate_instruction" type="command"}
# [@METHOD]{method="invalid_instruction_detection" type="command"}
# [@METHOD]{method="resolve_conflict" type="command"}
# [@METHOD]{method="conflicting_constraint_resolver" type="command"}
# [@METHOD]{method="safe_fallback" type="command"}
# [@METHOD]{method="recover_partial" type="command"}
# [@METHOD]{method="partial_recovery" type="command"}
# [@METHOD]{method="ambiguity_isolation" type="command"}
# [@METHOD]{method="deterministic_recovery" type="command"}
# [@METHOD]{method="error_classification" type="command"}
# [@METHOD]{method="retry_with_backoff" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ErrorResistance: validates instructions, resolves rule conflicts, provides safe fallbacks, recovers partial results. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
ErrorResistance -- authority for instruction validation and error resilience.
Implements Section 73 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: validate_instruction, resolve_conflict, safe_fallback,
          recover_partial.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
DEFAULT_PRIORITY = 0


class ErrorResistance:
    """Authority for instruction validation, conflict resolution and partial recovery."""

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
        if command == "validate_instruction":
            return self.ValidateInstruction(params)
        elif command == "invalid_instruction_detection":
            return self.InvalidInstructionDetection(params)
        elif command == "resolve_conflict":
            return self.ResolveConflict(params)
        elif command == "conflicting_constraint_resolver":
            return self.ConflictingConstraintResolver(params)
        elif command == "safe_fallback":
            return self.SafeFallback(params)
        elif command == "recover_partial":
            return self.RecoverPartial(params)
        elif command == "partial_recovery":
            return self.PartialRecovery(params)
        elif command == "ambiguity_isolation":
            return self.AmbiguityIsolation(params)
        elif command == "deterministic_recovery":
            return self.DeterministicRecovery(params)
        elif command == "error_classification":
            return self.ErrorClassification(params)
        elif command == "retry_with_backoff":
            return self.RetryWithBackoff(params)
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

    def ValidateInstruction(self, params):
        command = self._p(params, "command")
        instr_params = self._p(params, "params")
        expected_params = self._p(params, "expected_params")
        issues = []
        if command is None:
            issues.append("command_missing")
        elif not isinstance(command, str):
            issues.append("command_not_string")
        elif len(command) == 0:
            issues.append("command_empty")
        elif not command.replace("_", "").isalnum():
            issues.append("command_invalid_chars")
        if instr_params is not None and not isinstance(instr_params, dict):
            issues.append("params_not_dict")
        if expected_params is not None and isinstance(expected_params, list):
            if isinstance(instr_params, dict):
                for ep in expected_params:
                    if ep not in instr_params:
                        issues.append("missing_param: " + str(ep))
        valid = (len(issues) == 0)
        result = {"valid": valid, "issues": issues}
        return (1, result, None)

    def InvalidInstructionDetection(self, params):
        command = self._p(params, "command")
        instr_params = self._p(params, "params")
        detected = []
        if command is None:
            detected.append({"issue": "command_missing", "severity": "critical"})
        elif not isinstance(command, str):
            detected.append({"issue": "command_not_string", "severity": "critical"})
        elif len(command) == 0:
            detected.append({"issue": "command_empty", "severity": "critical"})
        elif len(command) > 200:
            detected.append({"issue": "command_too_long", "severity": "warning"})
        if instr_params is not None and not isinstance(instr_params, dict):
            detected.append({"issue": "params_not_dict", "severity": "high"})
        is_invalid = (len(detected) > 0)
        return (1, {"is_invalid": is_invalid, "detected": detected,
                    "count": len(detected)}, None)

    def ResolveConflict(self, params):
        rules = self._p(params, "rules")
        if rules is None:
            return (0, None, ("MISSING_PARAM", "rules required", 0))
        if not isinstance(rules, list) or len(rules) == 0:
            return (0, None, ("INVALID_RULES",
                              "rules must be a non-empty list", 0))
        chosen = None
        highest_priority = None
        for entry in rules:
            if not isinstance(entry, dict):
                continue
            rule = entry.get("rule")
            priority = entry.get("priority", DEFAULT_PRIORITY)
            if rule is None:
                continue
            if highest_priority is None or priority > highest_priority:
                highest_priority = priority
                chosen = rule
        if chosen is None:
            return (0, None, ("NO_VALID_RULES", "no valid rules found", 0))
        result = {"chosen_rule": chosen, "priority": highest_priority}
        self.state["results"] = result
        return (1, result, None)

    def ConflictingConstraintResolver(self, params):
        constraints = self._p(params, "constraints")
        if constraints is None:
            return (0, None, ("MISSING_PARAM", "constraints required", 0))
        if not isinstance(constraints, list) or len(constraints) < 2:
            return (0, None, ("INVALID_CONSTRAINTS",
                              "constraints must be a list of 2+", 0))
        conflicts = []
        for i in range(len(constraints)):
            for j in range(i + 1, len(constraints)):
                c1 = constraints[i]
                c2 = constraints[j]
                if not isinstance(c1, dict) or not isinstance(c2, dict):
                    continue
                if c1.get("rule") == c2.get("rule") and c1.get("value") != c2.get("value"):
                    conflicts.append({
                        "constraint1": c1,
                        "constraint2": c2,
                        "resolved": c1 if c1.get("priority", 0) >= c2.get("priority", 0) else c2,
                    })
        resolved = [c["resolved"] for c in conflicts]
        return (1, {"conflicts": conflicts, "resolved": resolved,
                    "conflict_count": len(conflicts)}, None)

    def SafeFallback(self, params):
        command = self._p(params, "command")
        if command is None:
            return (0, None, ("MISSING_PARAM", "command required", 0))
        default_value = self._p(params, "default", {})
        return (1, {"fallback_applied": True, "command": command,
                    "default": default_value}, None)

    def RecoverPartial(self, params):
        results = self._p(params, "results")
        if results is None:
            return (0, None, ("MISSING_PARAM", "results required", 0))
        if not isinstance(results, list):
            return (0, None, ("INVALID_RESULTS",
                              "results must be a list", 0))
        recovered_data = []
        failed_steps = []
        for entry in results:
            if not isinstance(entry, dict):
                continue
            step = entry.get("step")
            success = entry.get("success", False)
            data = entry.get("data")
            if success:
                recovered_data.append({"step": step, "data": data})
            else:
                failed_steps.append(step)
        recovered = (len(failed_steps) < len(results))
        result = {
            "recovered": recovered,
            "failed_steps": failed_steps,
            "recovered_data": recovered_data,
        }
        self.state["results"] = result
        return (1, result, None)

    def PartialRecovery(self, params):
        return self.RecoverPartial(params)

    def AmbiguityIsolation(self, params):
        instructions = self._p(params, "instructions")
        if instructions is None:
            return (0, None, ("MISSING_PARAM", "instructions required", 0))
        if not isinstance(instructions, list):
            return (0, None, ("INVALID_INSTRUCTIONS",
                              "instructions must be a list", 0))
        clear = []
        ambiguous = []
        for instr in instructions:
            if not isinstance(instr, dict):
                ambiguous.append({"instruction": instr, "reason": "not_dict"})
                continue
            command = instr.get("command")
            if command is None or not isinstance(command, str) or len(command) == 0:
                ambiguous.append({"instruction": instr, "reason": "invalid_command"})
            else:
                clear.append(instr)
        return (1, {"clear": clear, "ambiguous": ambiguous,
                    "clear_count": len(clear),
                    "ambiguous_count": len(ambiguous)}, None)

    def DeterministicRecovery(self, params):
        error_code = self._p(params, "error_code")
        if error_code is None:
            return (0, None, ("MISSING_PARAM", "error_code required", 0))
        recovery_map = {
            "MISSING_PARAM": "provide_default_param",
            "INVALID_PARAM": "coerce_to_valid_type",
            "QUERY_FAILED": "retry_with_rollback",
            "UNKNOWN_COMMAND": "return_safe_fallback",
            "SCHEMA_INVALID": "restore_last_valid_schema",
        }
        action = recovery_map.get(error_code, "generic_safe_fallback")
        return (1, {"error_code": error_code, "recovery_action": action,
                    "deterministic": True}, None)

    def ErrorClassification(self, params):
        error_text = self._p(params, "error_text")
        if error_text is None:
            return (0, None, ("MISSING_PARAM", "error_text required", 0))
        if not isinstance(error_text, str):
            return (0, None, ("INVALID_ERROR", "error_text must be string", 0))
        lower = error_text.lower()
        classification = "unknown"
        if "syntax" in lower or "parse" in lower:
            classification = "syntax"
        elif "import" in lower or "module" in lower:
            classification = "import"
        elif "type" in lower or "attribute" in lower:
            classification = "type"
        elif "value" in lower:
            classification = "value"
        elif "key" in lower:
            classification = "key"
        elif "index" in lower:
            classification = "index"
        elif "name" in lower:
            classification = "name"
        elif "io" in lower or "file" in lower:
            classification = "io"
        elif "permission" in lower:
            classification = "permission"
        elif "timeout" in lower:
            classification = "timeout"
        severity = "low"
        if "critical" in lower or "fatal" in lower:
            severity = "critical"
        elif "error" in lower or "fail" in lower:
            severity = "high"
        elif "warn" in lower:
            severity = "medium"
        return (1, {"classification": classification, "severity": severity,
                    "error_text": error_text[:200]}, None)

    def RetryWithBackoff(self, params):
        max_retries = self._p(params, "max_retries", 3)
        base_delay = self._p(params, "base_delay", 1)
        if not isinstance(max_retries, int) or max_retries < 1:
            return (0, None, ("INVALID_RETRIES", "max_retries must be >= 1", 0))
        if not isinstance(base_delay, (int, float)) or base_delay < 0:
            return (0, None, ("INVALID_DELAY", "base_delay must be >= 0", 0))
        schedule = []
        delay = base_delay
        for attempt in range(1, max_retries + 1):
            schedule.append({
                "attempt": attempt,
                "delay_seconds": round(delay, 2),
            })
            delay = delay * 2
        return (1, {"schedule": schedule, "max_retries": max_retries,
                    "total_delay": round(sum(s["delay_seconds"] for s in schedule), 2)}, None)
