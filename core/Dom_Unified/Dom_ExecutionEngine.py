# [@GHOST]{[@file<ExecutionEngine.py>][@domain<Dom_Unified>][@role<execution_orchestrator>][@auth<cascade>][@date<2026-06-27>][@ver<2.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<execution_orchestrator>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{ExecutionEngine — closed-loop execution substrate. Index + Verify + Gate + Execute + Report. No bypass paths.}
# [@CLASS]{ExecutionEngine}
# [@METHOD]{Run,Execute,Audit,GateCheck,WriteEvent,ReadEvents,ReportStream,Halt,Resume,ScanFile,ScanClass,ScanMethod,LoadRules,Setup,Shutdown,Index,Verify}


import os
import sys
import time
import json
import sqlite3
import subprocess
import traceback

from .Config import UnifiedConfig, EXEC_SCHEMA, EXEC_DOC
from .ErrorCapture import ErrorCapture
from .MemoryObject import MemoryObject
from .Dom_Report import DomReport
from .Dom_Indexer import DomIndexer
from .ConfigCascade import ConfigCascade




class ExecutionEngine:
    """Closed-loop execution substrate. No bypass paths."""

    def __init__(self, mem=None, db=None, param=None):
        cfg = UnifiedConfig()
        ok, cfg_state, err = cfg.read_state()
        if not ok:
            cfg_state = {"config": {}}
        c = cfg_state["config"]

        self.state = {
            "config": {
                "db_path": c.get("exec_db_path", ":memory:"),
                "output_target": c.get("exec_output_target", "screen"),
                "halt_on_violation": c.get("exec_halt_on_violation", True),
                "auto_repair": c.get("exec_auto_repair", True),
                "audit_before_execute": c.get("exec_audit_before_execute", True),
                "gate_before_execute": c.get("exec_gate_before_execute", True),
                "report_after_execute": c.get("exec_report_after_execute", True),
                "session_id": c.get("exec_session_id", str(int(time.time()))),
                "mysql_host": c.get("exec_mysql_host", "localhost"),
                "mysql_user": c.get("exec_mysql_user", "root"),
                "mysql_pass": c.get("exec_mysql_pass", ""),
                "mysql_db": c.get("exec_mysql_db", "vb_shared"),
                "rules_domain": c.get("exec_rules_domain", "domvbstyle"),
            },
            "conn": None,
            "halted": False,
            "halt_reason": None,
            "current_class": None,
            "current_method": None,
            "current_file": None,
            "stats": {
                "executions": 0,
                "violations_found": 0,
                "halts_triggered": 0,
                "fixes_applied": 0,
                "events_written": 0,
                "reports_streamed": 0,
            },
            "rules": [],
            "error_capture": ErrorCapture(),
            "memory": MemoryObject(),
            "report": DomReport(),
            "indexer": DomIndexer(),
            "config_cascade": ConfigCascade(),
        }
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params or not isinstance(params, dict):
            return default
        val = params.get(key, default)
        return val if val is not None else default

    def Run(self, command, params=None):
        dispatch = {
            "setup": self._cmd_setup,
            "execute": self._cmd_execute,
            "audit": self._cmd_audit,
            "gate_check": self._cmd_gate_check,
            "index": self._cmd_index,
            "index_dir": self._cmd_index_dir,
            "verify": self._cmd_verify,
            "read_events": self._cmd_read_events,
            "report_stream": self._cmd_report_stream,
            "halt": self._cmd_halt,
            "resume": self._cmd_resume,
            "repair": self._cmd_repair,
            "load_rules": self._cmd_load_rules,
            "shutdown": self._cmd_shutdown,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: " + str(command), 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "halted": self.state["halted"],
            "halt_reason": self.state["halt_reason"],
            "current_class": self.state["current_class"],
            "current_method": self.state["current_method"],
            "stats": dict(self.state["stats"]),
            "rules_loaded": len(self.state["rules"]),
            "db_open": self.state["conn"] is not None,
        }, None)

    def set_config(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ("ERR_PARAMS", "config dict required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    # ════════════════════════════════════════════
    # SETUP — opens InRamDb, loads rules, sets up shop
    # ════════════════════════════════════════════

    def _cmd_setup(self, params):
        ok, _, err = self._open_db()
        if not ok:
            return (0, None, err)

        ok, _, err = self._init_schema()
        if not ok:
            return (0, None, err)

        ok, _, err = self._cmd_load_rules({})
        if not ok:
            return (0, None, err)

        ok, _, err = self._write_event("EVENT_ENGINE_STARTED", {
            "class_name": "ExecutionEngine",
            "method_name": "setup",
            "state": "RUNNING",
        })
        if not ok:
            return (0, None, err)

        return (1, {
            "setup": True,
            "db_open": self.state["conn"] is not None,
            "rules_loaded": len(self.state["rules"]),
            "session_id": self.state["config"]["session_id"],
            "indexer_ready": self.state["indexer"] is not None,
            "config_cascade_ready": self.state["config_cascade"] is not None,
        }, None)

    def _open_db(self):
        try:
            self.state["conn"] = sqlite3.connect(self.state["config"]["db_path"])
            self.state["conn"].row_factory = sqlite3.Row
            self.state["conn"].execute("PRAGMA journal_mode=MEMORY")
            self.state["conn"].execute("PRAGMA synchronous=OFF")
            return (1, {"open": True}, None)
        except Exception as e:
            return self._trap_error("ERR_DB_OPEN", "Failed to open InRamDb: " + str(e), "open_db")

    def _init_schema(self):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_DB", "Database not open", 0))
        try:
            cur = self.state["conn"].cursor()
            for stmt in EXEC_SCHEMA:
                cur.execute(stmt)
            self.state["conn"].commit()
            cur.close()
            return (1, {"tables_created": len(EXEC_SCHEMA)}, None)
        except Exception as e:
            return self._trap_error("ERR_SCHEMA", "Schema init failed: " + str(e), "init_schema")

    def _cmd_load_rules(self, params):
        rules_domain = self.state["config"]["rules_domain"]
        try:
            result = subprocess.run(
                ["mysql", "-u", "root", "vb_shared", "-N", "-B", "-e",
                 "SELECT bcl_tag, question_text, section FROM graph_config WHERE domain='" + rules_domain + "' ORDER BY sort_order"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return self._trap_error("ERR_RULES_LOAD", "MySQL query failed: " + result.stderr[:200], "load_rules")

            rules = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    rules.append({
                        "tag": parts[0],
                        "text": parts[1],
                        "section": parts[2] if len(parts) > 2 else "",
                    })
            self.state["rules"] = rules
            return (1, {"rules_loaded": len(rules)}, None)
        except Exception as e:
            return self._trap_error("ERR_RULES_LOAD", "Failed to load rules: " + str(e), "load_rules")

    # ════════════════════════════════════════════
    # EXECUTE — the main pipeline, no bypass
    # ════════════════════════════════════════════

    def _cmd_execute(self, params):
        if self.state["halted"]:
            return (0, None, ("ERR_HALTED", "Engine is HALTED. Run resume first. Reason: " + str(self.state["halt_reason"]), 0))

        if not self.state["conn"]:
            ok, _, err = self._cmd_setup({})
            if not ok:
                return (0, None, err)

        target = self._p(params, "target")
        command = self._p(params, "command")
        method_params = self._p(params, "params", {})
        file_path = self._p(params, "file_path")

        if not target or not command:
            return (0, None, ("ERR_PARAMS", "target and command required", 0))

        self.state["current_class"] = target
        self.state["current_method"] = command
        self.state["current_file"] = file_path
        self.state["stats"]["executions"] += 1

        ok, _, err = self._write_event("EVENT_TASK_STARTED", {
            "class_name": target,
            "method_name": command,
            "command": command,
            "file_path": file_path or "",
            "input_params": json.dumps(method_params, default=str),
            "state": "EXECUTING",
        })
        if not ok:
            return (0, None, err)

        # STEP 1: INDEX — DomIndexer indexes the target file into in-RAM SQLite
        if file_path and os.path.isfile(file_path):
            ok, idx_data, err = self._cmd_index({"file": file_path})
            if not ok:
                ok2, _, _ = self._write_event("EVENT_INDEX_FAILED", {
                    "class_name": target,
                    "method_name": command,
                    "state": "INDEX_FAILED",
                    "violation": str(err),
                })
                if self.state["config"]["halt_on_violation"]:
                    self._cmd_halt({"reason": "Index failed: " + str(err)})
                return (0, None, err)

        # STEP 2: VERIFY — ConfigCascade verifies VBStyle compliance of the file
        if file_path and os.path.isfile(file_path):
            ok, ver_data, err = self._cmd_verify({"file": file_path})
            if not ok:
                ok2, _, _ = self._write_event("EVENT_VERIFY_FAILED", {
                    "class_name": target,
                    "method_name": command,
                    "state": "VERIFY_FAILED",
                    "violation": str(err),
                })
                if self.state["config"]["halt_on_violation"]:
                    self._cmd_halt({"reason": "VBStyle verify failed: " + str(err)})
                return (0, None, err)

        # STEP 3: AUDIT — VB scanner checks for rule violations (print, decorators, tabs, self._)
        if self.state["config"]["audit_before_execute"]:
            ok, audit_data, err = self._cmd_audit({
                "target": target,
                "file_path": file_path,
            })
            if not ok:
                ok2, _, _ = self._write_event("EVENT_VIOLATION_FOUND", {
                    "class_name": target,
                    "method_name": command,
                    "state": "VIOLATION",
                    "violation": str(err),
                })
                if self.state["config"].get("auto_repair", True):
                    ok3, repair_data, repair_err = self._cmd_repair({
                        "file_path": file_path,
                        "commit": True,
                    })
                    if ok3:
                        ok2, _, _ = self._write_event("EVENT_AUTO_REPAIRED", {
                            "class_name": target,
                            "method_name": command,
                            "state": "REPAIRED",
                            "output_data": json.dumps(repair_data.get("fixes", [])),
                        })
                        ok = True
                    else:
                        ok2, _, _ = self._write_event("EVENT_REPAIR_FAILED", {
                            "class_name": target,
                            "method_name": command,
                            "state": "REPAIR_FAILED",
                            "violation": str(repair_err),
                        })
                if not ok:
                    if self.state["config"]["halt_on_violation"]:
                        self._cmd_halt({"reason": "VB violation: " + str(err)})
                    return (0, None, err)

        # STEP 4: GATE — PreExecutionGate checks headers, Run() method, BCL stamps
        if self.state["config"]["gate_before_execute"]:
            ok, gate_data, err = self._cmd_gate_check({
                "target": target,
                "file_path": file_path,
            })
            if not ok:
                ok2, _, _ = self._write_event("EVENT_GATE_REJECTED", {
                    "class_name": target,
                    "method_name": command,
                    "state": "REJECTED",
                    "violation": str(err),
                })
                if self.state["config"]["halt_on_violation"]:
                    self._cmd_halt({"reason": "Gate rejected: " + str(err)})
                return (0, None, err)

        # STEP 5: EXECUTE — invoke the target method
        ok, result, err = self._invoke_method(target, command, method_params)

        if not ok:
            ok2, _, _ = self._write_event("EVENT_ERROR_RAISED", {
                "class_name": target,
                "method_name": command,
                "state": "ERROR",
                "violation": str(err),
            })
            return (0, None, err)

        # STEP 6: WRITE RESULT — record outcome in InRamDb
        ok2, _, _ = self._write_event("EVENT_TASK_COMPLETED", {
            "class_name": target,
            "method_name": command,
            "command": command,
            "output_data": json.dumps(result, default=str) if result else "",
            "state": "OK",
        })

        if self.state["config"]["report_after_execute"]:
            self._cmd_report_stream({
                "event_type": "EVENT_TASK_COMPLETED",
                "class_name": target,
                "method_name": command,
                "result": result,
            })

        return (1, result, None)

    def _invoke_method(self, target, command, params):
        try:
            if target == "ExecutionEngine":
                return (0, None, ("ERR_RECURSION", "Cannot execute self", 0))

            cls = None

            try:
                module = __import__("Dom_Unified", fromlist=[target])
                cls = getattr(module, target, None)
            except (ImportError, AttributeError):
                pass

            if cls is None:
                try:
                    module = __import__(target, fromlist=[target])
                    cls = getattr(module, target, None)
                except (ImportError, AttributeError):
                    pass

            if cls is None and self.state.get("current_file"):
                file_path = self.state["current_file"]
                if os.path.isfile(file_path):
                    import importlib.util
                    mod_name = "exec_target_" + target
                    spec = importlib.util.spec_from_file_location(mod_name, file_path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        cls = getattr(mod, target, None)

            if cls is None:
                return (0, None, ("ERR_NO_CLASS", "Class " + target + " not found", 0))

            instance = cls()
            if not hasattr(instance, "Run"):
                return (0, None, ("ERR_NO_RUN", target + " has no Run() method", 0))

            ok, data, err = instance.Run(command, params)
            return (ok, data, err)
        except Exception as e:
            tb = traceback.format_exc()
            return self._trap_error("ERR_INVOKE", target + "." + command + " failed: " + str(e) + "\n" + tb, "invoke")

    # ════════════════════════════════════════════
    # AUDIT — VB style scanner
    # ════════════════════════════════════════════

    def _cmd_audit(self, params):
        target = self._p(params, "target")
        file_path = self._p(params, "file_path")

        if not file_path and target:
            file_path = self._find_file_for_class(target)

        if not file_path:
            return (1, {"audited": False, "reason": "no file path"}, None)

        if not os.path.isfile(file_path):
            return (1, {"audited": False, "reason": "file not found: " + file_path}, None)

        violations = []
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
        except Exception as e:
            return self._trap_error("ERR_READ", "Cannot read " + file_path + ": " + str(e), "audit")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if "print(" in stripped and not stripped.startswith("#") and "__main__" not in lines[max(0, i-5):i+1].__str__():
                violations.append({
                    "rule": "[@print]",
                    "line": i,
                    "text": stripped[:80],
                    "cause": "print() used instead of DomReport",
                    "solution": "Replace print() with DomReport.Run('report', {...})",
                    "fix": "Replace print(x) with self.state['report'].Run('report', {'type': 'msg', 'data': x})",
                })

            if "@property" in stripped or "@staticmethod" in stripped or "@classmethod" in stripped:
                violations.append({
                    "rule": "[@decorators]",
                    "line": i,
                    "text": stripped[:80],
                    "cause": "Decorator used — VBStyle forbids decorators",
                    "solution": "Remove decorator, use plain method",
                    "fix": "Remove " + stripped.strip() + " and make method plain",
                })

            if "\t" in line:
                violations.append({
                    "rule": "[@tabs]",
                    "line": i,
                    "text": "tab character found",
                    "cause": "Tab used instead of spaces",
                    "solution": "Replace tab with 4 spaces",
                    "fix": "Replace tab with spaces on line " + str(i),
                })

            if "self._" in stripped and not stripped.startswith("#"):
                is_method_call = ("self._" in stripped and
                    any(stripped.startswith("self._" + name) or ("= self._" + name) in stripped
                        for name in ["cmd_", "step_", "check_", "record_", "trap_", "compile_",
                                     "recall_", "report", "write_", "open_", "init_", "find_",
                                     "invoke_", "acquire_", "release_", "clear_", "trim_",
                                     "step_", "p(", "query_provenance", "hash_file",
                                     "connect", "cmd_search", "cmd_report", "cmd_copy"]))
                is_param_helper = "self._p(" in stripped
                if not is_method_call and not is_param_helper:
                    if "= self._" in stripped or "self._mlx" in stripped or "self._generate" in stripped or "self._load_fn" in stripped:
                        violations.append({
                            "rule": "[@intstate]",
                            "line": i,
                            "text": stripped[:80],
                            "cause": "self._ variable assignment — use self.state dict",
                            "solution": "Replace self._x = val with self.state['x'] = val",
                            "fix": "Move self._" + stripped.split("self._")[1].split()[0].split("=")[0].split(".")[0] + " to self.state dict",
                        })

        for v in violations:
            rule_info = self._lookup_rule(v["rule"])
            if rule_info:
                v["cause"] = rule_info.get("text", v["cause"])
            self.state["stats"]["violations_found"] += 1
            self._record_violation(target, v, file_path)
            self._report_violation(target, v, file_path)

        if violations:
            first = violations[0]
            return (0, None, ("ERR_VB_VIOLATION",
                first["rule"] + " at " + file_path + ":" + str(first["line"]) + " — " + first["cause"] + " — FIX: " + first["fix"], 0))

        return (1, {"audited": True, "violations": 0, "file": file_path}, None)

    def _find_file_for_class(self, class_name):
        candidates = [
            os.path.join(os.path.dirname(__file__), class_name + ".py"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dom_Graph", class_name + ".py"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _lookup_rule(self, rule_tag):
        for rule in self.state["rules"]:
            if rule.get("tag", "") == rule_tag:
                return rule
        return None

    def _record_violation(self, class_name, violation, file_path):
        try:
            cur = self.state["conn"].cursor()
            cur.execute(
                "INSERT INTO exec_violations (rule_tag, class_name, method_name, file_path, line_number, violation_text, cause, solution, fix_action, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (violation["rule"], class_name, "", file_path, violation["line"],
                 violation["text"], violation["cause"], violation["solution"], violation["fix"],
                 "OPEN", time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self.state["conn"].commit()
            cur.close()
        except Exception:
            pass

    def _report_violation(self, class_name, violation, file_path):
        msg = (
            "\n[VIOLATION] Rule=" + violation["rule"] + "\n" +
            "[CLASS] " + class_name + "\n" +
            "[LOCATION] " + file_path + ":" + str(violation["line"]) + "\n" +
            "[CODE] " + violation["text"] + "\n" +
            "[CAUSE] " + violation["cause"] + "\n" +
            "[SOLUTION] " + violation["solution"] + "\n" +
            "[FIX] " + violation["fix"] + "\n" +
            "[ACTION REQUIRED] AI must fix this before execution can proceed\n"
        )
        target = self.state["config"]["output_target"]
        if target in ("screen", "both"):
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        if target in ("db", "both"):
            try:
                self.state["report"].Run("report", {
                    "type": "violation",
                    "data": {
                        "rule": violation["rule"],
                        "class": class_name,
                        "file": file_path,
                        "line": violation["line"],
                        "cause": violation["cause"],
                        "solution": violation["solution"],
                        "fix": violation["fix"],
                    },
                })
            except Exception:
                pass

    # ════════════════════════════════════════════
    # GATE CHECK — PreExecutionGate
    # ════════════════════════════════════════════

    def _cmd_gate_check(self, params):
        target = self._p(params, "target")
        file_path = self._p(params, "file_path")

        if not file_path:
            return (1, {"gate": "SKIP", "reason": "no file path, gate not applicable"}, None)

        if not os.path.isfile(file_path):
            return (1, {"gate": "SKIP", "reason": "file not found"}, None)

        has_ghost = False
        has_vbstyle = False
        has_run = False
        try:
            with open(file_path, "r") as f:
                content = f.read()
            if "[@GHOST]" in content:
                has_ghost = True
            if "[@VBSTYLE]" in content:
                has_vbstyle = True
            if "def Run(" in content:
                has_run = True
        except Exception as e:
            return self._trap_error("ERR_GATE_READ", "Cannot read " + file_path + ": " + str(e), "gate_check")

        missing = []
        if not has_ghost:
            missing.append("[@GHOST] header missing")
        if not has_vbstyle:
            missing.append("[@VBSTYLE] header missing")
        if not has_run:
            missing.append("Run() method missing")

        if missing:
            return (0, None, ("ERR_GATE", "Gate REJECTED: " + "; ".join(missing) + " in " + file_path, 0))

        return (1, {"gate": "PASS", "file": file_path}, None)

    # ════════════════════════════════════════════
    # INDEX — DomIndexer: index files/classes/methods/BCL into in-RAM SQLite
    # ════════════════════════════════════════════

    def _cmd_index(self, params):
        file_path = self._p(params, "file")
        if not file_path:
            return (0, None, ("ERR_PARAMS", "file required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("ERR_NO_FILE", "file not found: " + file_path, 0))

        ok, data, err = self.state["indexer"].Run("index", {"file": file_path})
        if not ok:
            return self._trap_error("ERR_INDEX", "Index failed: " + str(err), "index")

        self._write_event("EVENT_FILE_INDEXED", {
            "class_name": "",
            "method_name": "index",
            "command": "index",
            "file_path": file_path,
            "output_data": json.dumps(data, default=str) if data else "",
            "state": "INDEXED",
        })

        self._cmd_report_stream({
            "event_type": "EVENT_FILE_INDEXED",
            "class_name": "DomIndexer",
            "method_name": "index",
            "result": data,
        })

        return (1, data, None)

    def _cmd_index_dir(self, params):
        dir_path = self._p(params, "path")
        if not dir_path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        if not os.path.isdir(dir_path):
            return (0, None, ("ERR_NO_DIR", "directory not found: " + dir_path, 0))

        ok, data, err = self.state["indexer"].Run("index_dir", {"path": dir_path})
        if not ok:
            return self._trap_error("ERR_INDEX_DIR", "Index dir failed: " + str(err), "index_dir")

        self._write_event("EVENT_DIR_INDEXED", {
            "class_name": "DomIndexer",
            "method_name": "index_dir",
            "command": "index_dir",
            "file_path": dir_path,
            "output_data": json.dumps(data, default=str) if data else "",
            "state": "INDEXED",
        })

        self._cmd_report_stream({
            "event_type": "EVENT_DIR_INDEXED",
            "class_name": "DomIndexer",
            "method_name": "index_dir",
            "result": data,
        })

        return (1, data, None)

    # ════════════════════════════════════════════
    # VERIFY — ConfigCascade: verify VBStyle compliance of a file
    # ════════════════════════════════════════════

    def _cmd_verify(self, params):
        file_path = self._p(params, "file")
        if not file_path:
            return (0, None, ("ERR_PARAMS", "file required", 0))
        if not os.path.isfile(file_path):
            return (0, None, ("ERR_NO_FILE", "file not found: " + file_path, 0))

        ok, data, err = self.state["config_cascade"].Run("verify", {"file": file_path})
        if not ok:
            self._write_event("EVENT_VERIFY_FAILED", {
                "class_name": "ConfigCascade",
                "method_name": "verify",
                "command": "verify",
                "file_path": file_path,
                "state": "FAILED",
                "violation": str(err),
            })
            self._cmd_report_stream({
                "event_type": "EVENT_VERIFY_FAILED",
                "class_name": "ConfigCascade",
                "method_name": "verify",
                "result": {"file": file_path, "error": str(err)},
            })
            return (0, None, err)

        self._write_event("EVENT_VERIFY_PASSED", {
            "class_name": "ConfigCascade",
            "method_name": "verify",
            "command": "verify",
            "file_path": file_path,
            "output_data": json.dumps(data, default=str) if data else "",
            "state": "VERIFIED",
        })

        self._cmd_report_stream({
            "event_type": "EVENT_VERIFY_PASSED",
            "class_name": "ConfigCascade",
            "method_name": "verify",
            "result": data,
        })

        return (1, data, None)

    # ════════════════════════════════════════════
    # EVENT BUS — write/read to InRamDb
    # ════════════════════════════════════════════

    def _write_event(self, event_type, data):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_DB", "Database not open", 0))
        try:
            cur = self.state["conn"].cursor()
            cur.execute(
                "INSERT INTO exec_events (event_type, class_name, method_name, command, file_path, input_params, output_data, state, rule_tag, violation, solution, cause, fix_action, timestamp, session_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_type,
                    data.get("class_name", ""),
                    data.get("method_name", ""),
                    data.get("command", ""),
                    data.get("file_path", ""),
                    data.get("input_params", ""),
                    data.get("output_data", ""),
                    data.get("state", ""),
                    data.get("rule_tag", ""),
                    data.get("violation", ""),
                    data.get("solution", ""),
                    data.get("cause", ""),
                    data.get("fix_action", ""),
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    self.state["config"]["session_id"],
                )
            )
            self.state["conn"].commit()
            self.state["stats"]["events_written"] += 1
            cur.close()
            return (1, {"written": True}, None)
        except Exception as e:
            return self._trap_error("ERR_WRITE_EVENT", "Failed to write event: " + str(e), "write_event")

    def _cmd_read_events(self, params):
        if not self.state["conn"]:
            return (0, None, ("ERR_NO_DB", "Database not open", 0))
        event_type = self._p(params, "event_type")
        class_name = self._p(params, "class_name")
        limit = self._p(params, "limit", 100)

        sql = "SELECT * FROM exec_events"
        conditions = []
        sql_params = []
        if event_type:
            conditions.append("event_type = ?")
            sql_params.append(event_type)
        if class_name:
            conditions.append("class_name = ?")
            sql_params.append(class_name)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY id DESC LIMIT ?"
        sql_params.append(limit)

        try:
            cur = self.state["conn"].cursor()
            cur.execute(sql, sql_params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return (1, {"events": rows, "count": len(rows)}, None)
        except Exception as e:
            return self._trap_error("ERR_READ_EVENTS", "Failed to read events: " + str(e), "read_events")

    # ════════════════════════════════════════════
    # REPORT STREAM — output to terminal/db
    # ════════════════════════════════════════════

    def _cmd_report_stream(self, params):
        self.state["stats"]["reports_streamed"] += 1
        event_type = self._p(params, "event_type", "EVENT")
        class_name = self._p(params, "class_name", "")
        method_name = self._p(params, "method_name", "")
        result = self._p(params, "result")

        msg = (
            "\n[EVENT] " + event_type + "\n" +
            "[CLASS] " + class_name + "\n" +
            "[METHOD] " + method_name + "\n"
        )
        if result is not None:
            try:
                result_str = json.dumps(result, default=str, indent=2)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "... (truncated)"
                msg += "[OUTPUT] " + result_str + "\n"
            except Exception:
                msg += "[OUTPUT] " + str(result)[:500] + "\n"
        msg += "[STATE] OK\n"

        target = self.state["config"]["output_target"]
        if target in ("screen", "both"):
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        if target in ("db", "both"):
            try:
                self.state["report"].Run("report", {
                    "type": "execution",
                    "data": {
                        "event": event_type,
                        "class": class_name,
                        "method": method_name,
                        "result": result,
                    },
                })
            except Exception:
                pass

        return (1, {"streamed": True}, None)

    # ════════════════════════════════════════════
    # REPAIR — auto-fix VBStyle violations via RuleEnforcer
    # ════════════════════════════════════════════

    def _cmd_repair(self, params):
        file_path = self._p(params, "file_path")
        commit = self._p(params, "commit", True)
        if not file_path or not os.path.isfile(file_path):
            return (0, None, ("ERR_NO_FILE", "file_path required and must exist", 0))

        enforcer_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "core", "Dom_Vsstyle"
        )
        if not os.path.isdir(enforcer_dir):
            enforcer_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "Dom_Vsstyle"
            )
        if not os.path.isdir(enforcer_dir):
            return (0, None, ("ERR_NO_ENFORCER", "Dom_Vsstyle directory not found", 0))

        try:
            if enforcer_dir not in sys.path:
                sys.path.insert(0, enforcer_dir)
            import importlib
            mod = importlib.import_module("vbs_rule_enforcer")
            enforcer = mod.RuleEnforcer()
        except Exception as e:
            return self._trap_error("ERR_REPAIR_IMPORT", "Failed to load RuleEnforcer: " + str(e), "repair")

        ok, fix_data, fix_err = enforcer.Run("auto_fix", {"path": file_path, "commit": commit})
        if not ok:
            self._write_event("EVENT_REPAIR_FAILED", {
                "class_name": self.state["current_class"] or "",
                "method_name": self.state["current_method"] or "",
                "state": "REPAIR_FAILED",
                "violation": str(fix_err),
            })
            return (0, None, fix_err)

        fixes = fix_data.get("fixes", [])
        self.state["stats"]["fixes_applied"] += len(fixes)

        self._write_event("EVENT_REPAIR_APPLIED", {
            "class_name": self.state["current_class"] or "",
            "method_name": self.state["current_method"] or "",
            "state": "REPAIRED",
            "output_data": json.dumps(fixes),
        })

        ok2, reaudit_data, reaudit_err = self._cmd_audit({
            "target": self.state["current_class"] or "",
            "file_path": file_path,
        })
        if ok2:
            self._write_event("EVENT_REPAIR_VERIFIED", {
                "class_name": self.state["current_class"] or "",
                "method_name": self.state["current_method"] or "",
                "state": "VERIFIED",
            })
            return (1, {"repaired": True, "fixes": fixes, "reaudit": reaudit_data}, None)

        self._write_event("EVENT_REPAIR_INCOMPLETE", {
            "class_name": self.state["current_class"] or "",
            "method_name": self.state["current_method"] or "",
            "state": "REPAIR_INCOMPLETE",
            "violation": str(reaudit_err),
        })
        return (0, None, ("ERR_REPAIR_INCOMPLETE", "Auto-fix applied but violations remain: " + str(reaudit_err), 0))

    # ════════════════════════════════════════════
    # HALT / RESUME
    # ════════════════════════════════════════════

    def _cmd_halt(self, params):
        reason = self._p(params, "reason", "Manual halt")
        self.state["halted"] = True
        self.state["halt_reason"] = reason
        self.state["stats"]["halts_triggered"] += 1

        self._write_event("EVENT_ENGINE_HALTED", {
            "class_name": self.state["current_class"] or "",
            "method_name": self.state["current_method"] or "",
            "state": "HALTED",
            "violation": reason,
        })

        msg = (
            "\n[HALT] Execution engine HALTED\n" +
            "[REASON] " + reason + "\n" +
            "[ACTION] AI must fix the violation and run resume\n"
        )
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

        return (1, {"halted": True, "reason": reason}, None)

    def _cmd_resume(self, params):
        if not self.state["halted"]:
            return (1, {"resumed": False, "reason": "not halted"}, None)

        self.state["halted"] = False
        old_reason = self.state["halt_reason"]
        self.state["halt_reason"] = None

        self._write_event("EVENT_ENGINE_RESUMED", {
            "class_name": "ExecutionEngine",
            "method_name": "resume",
            "state": "RUNNING",
            "violation": "Resumed from: " + str(old_reason),
        })

        return (1, {"resumed": True, "was_reason": old_reason}, None)

    # ════════════════════════════════════════════
    # SHUTDOWN
    # ════════════════════════════════════════════

    def _cmd_shutdown(self, params):
        self._write_event("EVENT_ENGINE_STOPPED", {
            "class_name": "ExecutionEngine",
            "method_name": "shutdown",
            "state": "STOPPED",
        })
        if self.state["conn"]:
            self.state["conn"].close()
            self.state["conn"] = None
        self.state["halted"] = False
        return (1, {"shutdown": True}, None)

    # ════════════════════════════════════════════
    # [@errtrap] — ErrorCapture full cycle
    # ════════════════════════════════════════════

    def _trap_error(self, error_code, error_desc, context=None):
        self.state["stats"]["violations_found"] += 1
        problem = error_code
        cause = error_desc
        solution_map = {
            "ERR_DB_OPEN": "Check sqlite3 installation and db_path in Config.py",
            "ERR_SCHEMA": "Check schema SQL syntax and sqlite version",
            "ERR_RULES_LOAD": "Check MySQL connection and graph_config table for domvbstyle domain",
            "ERR_INVOKE": "Check target class exists, has Run() method, and params are correct",
            "ERR_GATE_READ": "Check file permissions and path",
            "ERR_WRITE_EVENT": "Check InRamDb is open and schema is initialized",
            "ERR_READ_EVENTS": "Check InRamDb is open and exec_events table exists",
            "ERR_READ": "Check file permissions",
        }
        fix = solution_map.get(error_code, "Check error code and context for root cause")
        try:
            self.state["error_capture"].Run("capture", {
                "problem": problem,
                "cause": cause,
                "solution": fix,
                "fix": fix,
                "context": context or "",
            })
        except Exception:
            pass
        return (0, None, (error_code, error_desc, 0))


if __name__ == "__main__":
    engine = ExecutionEngine()

    ok, data, err = engine.Run("setup", {})
    if not ok:
        sys.stderr.write("Setup failed: " + str(err) + "\n")
        sys.exit(1)
    sys.stderr.write("Engine setup: " + str(data) + "\n")

    ok, data, err = engine.Run("execute", {
        "target": "DomReport",
        "command": "read_state",
        "params": {},
        "file_path": os.path.join(os.path.dirname(__file__), "DomReport.py"),
    })
    if ok:
        sys.stderr.write("Execute OK: " + str(data)[:200] + "\n")
    else:
        sys.stderr.write("Execute FAILED: " + str(err) + "\n")

    ok, data, err = engine.Run("read_events", {"limit": 10})
    if ok:
        sys.stderr.write("Events: " + str(data["count"]) + " found\n")

    engine.Run("shutdown", {})
    sys.stderr.write("Engine shutdown\n")
