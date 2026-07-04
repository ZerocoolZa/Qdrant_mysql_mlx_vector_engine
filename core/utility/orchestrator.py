# [@GHOST]{[@file<orchestrator.py>][@domain<utility>][@role<orchestrator>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<orchestrator>][@return<tuple3>][@orch<Config.TRIGGERS>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Orchestrator — reads Config.TRIGGERS, executes utilities in order, handles failures per on_fail policy}
# [@WCL]{[@self_contained<true>][@reads<Config.TRIGGERS>][@runs<all_utilities>][@handles<report|continue|escalate|cancel>][@smart<true>]}

import os
import time

from . import Config
from .indexer import Indexer
from .compress import Compress
from .system_check import SystemCheck
from .vbs_scanner import VbsScanner
from .cleaner import Cleaner
from .diff_check import DiffCheck
from .stats_report import StatsReport
from .dom_audit import DomAudit
from .preflight import PreFlight
from .content_extract import ContentExtract
from .error_tracker import ErrorTracker
from .error_handler import ErrorHandler
from .vbs_test import VbsTest
from .backup import Backup


class Orchestrator:
    """Orchestrator — reads Config.TRIGGERS and executes utilities automatically.

    The utilities work for us, not the other way around. Config defines:
    - WHAT runs (which utility + command)
    - WHEN (trigger: startup, error, change, code_change, db_change, scheduled)
    - WHERE (which paths/dirs)
    - WHY (purpose of each step)
    - ORDER (sequence within a trigger)
    - ON_FAIL (report, continue, escalate, cancel)

    Usage:
        from core.utility.orchestrator import Orchestrator
        orch = Orchestrator()
        code, report, err = orch.Run("trigger", {"name": "startup"})
        code, report, err = orch.Run("trigger", {"name": "error", "context": {"result": failed_tuple3}})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_trigger": "",
            "last_results": [],
            "history": [],
            "passed": 0,
            "failed": 0,
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["utils"] = {}
        self.init_utils()

    def init_utils(self):
        self.state["utils"] = {
            "Indexer": Indexer(),
            "Compress": Compress(),
            "SystemCheck": SystemCheck(),
            "VbsScanner": VbsScanner(),
            "Cleaner": Cleaner(),
            "DiffCheck": DiffCheck(),
            "StatsReport": StatsReport(),
            "DomAudit": DomAudit(),
            "PreFlight": PreFlight(),
            "ContentExtract": ContentExtract(),
            "ErrorTracker": ErrorTracker(),
            "ErrorHandler": ErrorHandler(),
            "VbsTest": VbsTest(),
            "Backup": Backup(),
        }

    def Run(self, command, params=None):
        if command == "trigger":
            return self.run_trigger((params or {}).get("name", ""), (params or {}).get("context", {}))
        elif command == "list_triggers":
            return self.list_triggers()
        elif command == "get_history":
            return self.get_history((params or {}).get("limit", 20))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def list_triggers(self):
        triggers = {}
        for name, steps in Config.TRIGGERS.items():
            triggers[name] = {
                "steps": len(steps),
                "utils": [s["util"] for s in sorted(steps, key=lambda x: x["order"])],
                "whys": [s["why"] for s in sorted(steps, key=lambda x: x["order"])],
            }
        return (1, triggers, None)

    def resolve_params(self, step_params, context):
        resolved = {}
        for key, value in step_params.items():
            if value is None:
                if key in context:
                    resolved[key] = context[key]
                elif key == "root" or key == "path" or key == "dirs":
                    resolved[key] = Config.CORE_DIR
                elif key == "db_path":
                    resolved[key] = context.get("db_path", "")
                elif key == "result":
                    resolved[key] = context.get("result")
                elif key == "error_text":
                    resolved[key] = context.get("error_text", "")
                elif key == "error_code":
                    resolved[key] = context.get("error_code", "")
                elif key == "before":
                    resolved[key] = context.get("before")
                elif key == "after":
                    resolved[key] = context.get("after")
                elif key == "data":
                    resolved[key] = context.get("data")
                else:
                    resolved[key] = None
            else:
                resolved[key] = value
        return resolved

    def run_trigger(self, trigger_name, context=None):
        context = context or {}
        if not trigger_name:
            return (0, None, ("missing_param", "trigger name required", 0))
        steps = Config.TRIGGERS.get(trigger_name)
        if not steps:
            return (0, None, ("unknown_trigger", "No trigger: " + trigger_name, 0))

        steps_sorted = sorted(steps, key=lambda x: x["order"])
        results = []
        passed = 0
        failed = 0
        stopped = False

        for step in steps_sorted:
            if stopped:
                break
            util_name = step["util"]
            command = step["command"]
            raw_params = step["params"]
            why = step["why"]
            on_fail = step["on_fail"]
            order = step["order"]

            resolved = self.resolve_params(raw_params, context)
            util = self.state["utils"].get(util_name)
            if not util:
                results.append({
                    "order": order, "util": util_name, "command": command,
                    "why": why, "ok": False, "error": "util not initialized",
                    "on_fail": on_fail, "action_taken": "skip",
                })
                failed += 1
                continue

            start = time.time()
            code, data, err = util.Run(command, resolved)
            elapsed = round(time.time() - start, 4)
            ok = code == 1

            entry = {
                "order": order, "util": util_name, "command": command,
                "why": why, "ok": ok, "elapsed": elapsed,
                "on_fail": on_fail, "action_taken": "none",
            }
            if ok:
                passed += 1
                entry["data"] = data if isinstance(data, (dict, list, str, int, float)) else str(data)
            else:
                failed += 1
                entry["error"] = str(err) if err else "unknown"
                if on_fail == "cancel":
                    entry["action_taken"] = "stopped_pipeline"
                    stopped = True
                elif on_fail == "escalate":
                    entry["action_taken"] = "escalated"
                    self.state["utils"]["ErrorHandler"].Run("capture", {
                        "error_code": str(err[0]) if err else "UNKNOWN",
                        "raw_message": str(err[1]) if err else "",
                        "source_module": util_name,
                        "operation": command,
                    })
                elif on_fail == "report":
                    entry["action_taken"] = "reported"
                elif on_fail == "continue":
                    entry["action_taken"] = "continued"
            results.append(entry)

        self.state["last_trigger"] = trigger_name
        self.state["last_results"] = results
        self.state["passed"] += passed
        self.state["failed"] += failed
        self.state["history"].append({
            "trigger": trigger_name,
            "timestamp": time.time(),
            "passed": passed,
            "failed": failed,
            "steps": len(results),
        })

        all_ok = failed == 0
        summary = self.build_summary(trigger_name, results, passed, failed)
        if all_ok:
            return (1, {"trigger": trigger_name, "passed": passed, "failed": failed, "results": results, "summary": summary}, None)
        return (0, {"trigger": trigger_name, "passed": passed, "failed": failed, "results": results, "summary": summary}, ("TRIGGER_FAILED", "{}: {}/{} steps passed".format(trigger_name, passed, len(results)), 0))

    def build_summary(self, trigger_name, results, passed, failed):
        lines = []
        lines.append("=== TRIGGER: {} ===".format(trigger_name))
        for entry in results:
            tag = "PASS" if entry["ok"] else "FAIL"
            line = "[{}] #{} {}.{} — {} ({})".format(
                tag, entry["order"], entry["util"], entry["command"],
                entry["why"], entry["action_taken"],
            )
            if entry.get("elapsed"):
                line += " {}s".format(entry["elapsed"])
            if entry.get("error"):
                line += " ERR: {}".format(entry["error"][:60])
            lines.append(line)
        lines.append("")
        lines.append("Total: {} passed, {} failed".format(passed, failed))
        return "\n".join(lines)

    def get_history(self, limit=20):
        entries = self.state["history"][-limit:]
        return (1, {"entries": entries, "count": len(entries)}, None)
