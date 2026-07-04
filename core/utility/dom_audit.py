# [@GHOST]{[@file<dom_audit.py>][@domain<utility>][@role<audit>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<domain_audit>][@return<tuple3>][@orch<SystemCheck>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Domain audit — baseline, check, drift, diff, compliance, flag, trace, history, report}
# [@WCL]{[@self_contained<true>][@source<MySQL_vb_code_test_DomAudit>][@tracks<violations|drift|compliance|fixes>]

import hashlib
import json
import difflib


class DomAudit:
    """Domain audit — tracks baselines, drift, compliance, violations, fixes.

    Commands:
    - baseline: set a hash baseline for named data
    - drift: check if data has drifted from baseline
    - compliance: check data against rules (exists, eq, ne, gte, lte)
    - diff: unified diff between two texts
    - flag: record a flagged issue
    - violation: record a violation
    - fix: record a fix applied
    - escalate: escalate an issue
    - trace: filter history by target
    - history: get audit history
    - report: full audit report

    Usage:
        from core.utility.dom_audit import DomAudit
        audit = DomAudit()
        audit.Run("baseline", {"name": "core_index", "data": {...}})
        audit.Run("drift", {"name": "core_index", "data": current_data})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "baselines": {},
            "history": [],
        }

    def Run(self, command, params=None):
        if command == "baseline":
            return self.baseline(params)
        elif command == "drift":
            return self.drift(params)
        elif command == "compliance":
            return self.compliance(params)
        elif command == "diff":
            return self.diff(params)
        elif command == "flag":
            return self.flag(params)
        elif command == "violation":
            return self.violation(params)
        elif command == "fix":
            return self.fix(params)
        elif command == "escalate":
            return self.escalate(params)
        elif command == "trace":
            return self.trace(params)
        elif command == "history":
            return self.history(params)
        elif command == "report":
            return self.report(params)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def record(self, entry):
        self.state["history"].append(entry)

    def read_state(self):
        return (1, dict(self.state), None)

    def baseline(self, params=None):
        params = params or {}
        name = params.get("name", "default")
        data = params.get("data")
        payload = json.dumps(data, sort_keys=True).encode("utf-8") if data is not None else b""
        digest = hashlib.sha256(payload).hexdigest()
        self.state["baselines"][name] = {"hash": digest, "data": data}
        self.record({"action": "baseline", "name": name, "hash": digest})
        return (1, {"name": name, "hash": digest}, None)

    def drift(self, params=None):
        params = params or {}
        name = params.get("name", "default")
        data = params.get("data")
        baseline = self.state["baselines"].get(name)
        if not baseline:
            return (0, None, ("DRIFT_ERROR", "no baseline", 0))
        payload = json.dumps(data, sort_keys=True).encode("utf-8") if data is not None else b""
        digest = hashlib.sha256(payload).hexdigest()
        drifted = digest != baseline["hash"]
        self.record({"action": "drift", "name": name, "drifted": drifted})
        return (1, {"name": name, "drifted": drifted, "current": digest, "baseline": baseline["hash"]}, None)

    def compliance(self, params=None):
        params = params or {}
        rules = params.get("rules", [])
        data = params.get("data", {})
        passed = []
        failed = []
        for rule in rules:
            key = rule.get("key")
            op = rule.get("op", "exists")
            expected = rule.get("value")
            actual = data.get(key) if isinstance(data, dict) else None
            ok = False
            if op == "exists":
                ok = key in data if isinstance(data, dict) else False
            elif op == "eq":
                ok = actual == expected
            elif op == "ne":
                ok = actual != expected
            elif op == "gte":
                ok = actual is not None and expected is not None and actual >= expected
            elif op == "lte":
                ok = actual is not None and expected is not None and actual <= expected
            if ok:
                passed.append(rule)
            else:
                failed.append(rule)
        self.record({"action": "compliance", "passed": len(passed), "failed": len(failed)})
        return (1, {"passed": passed, "failed": failed, "compliant": len(failed) == 0}, None)

    def diff(self, params=None):
        params = params or {}
        a = params.get("a", "")
        b = params.get("b", "")
        a_lines = a.splitlines() if isinstance(a, str) else [str(x) for x in a]
        b_lines = b.splitlines() if isinstance(b, str) else [str(x) for x in b]
        changes = list(difflib.unified_diff(a_lines, b_lines, lineterm=""))
        self.record({"action": "diff", "changes": len(changes)})
        return (1, {"changes": changes, "count": len(changes)}, None)

    def flag(self, params=None):
        params = params or {}
        target = params.get("target", "")
        reason = params.get("reason", "")
        severity = params.get("severity", "low")
        self.record({"action": "flag", "target": target, "reason": reason, "severity": severity})
        return (1, {"target": target, "reason": reason, "severity": severity, "flagged": True}, None)

    def violation(self, params=None):
        params = params or {}
        rule = params.get("rule", "")
        target = params.get("target", "")
        detail = params.get("detail", "")
        self.record({"action": "violation", "rule": rule, "target": target, "detail": detail})
        return (1, {"rule": rule, "target": target, "detail": detail, "recorded": True}, None)

    def fix(self, params=None):
        params = params or {}
        issue = params.get("issue", "")
        action = params.get("action", "")
        self.record({"action": "fix", "issue": issue, "fix": action})
        return (1, {"issue": issue, "action": action, "applied": True}, None)

    def escalate(self, params=None):
        params = params or {}
        issue = params.get("issue", "")
        level = int(params.get("level", 1))
        to = params.get("to", "admin")
        self.record({"action": "escalate", "issue": issue, "level": level, "to": to})
        return (1, {"issue": issue, "level": level, "to": to, "escalated": True}, None)

    def trace(self, params=None):
        params = params or {}
        target = params.get("target", "")
        entries = [h for h in self.state["history"] if target in str(h)]
        return (1, {"target": target, "trace": entries, "count": len(entries)}, None)

    def history(self, params=None):
        params = params or {}
        limit = int(params.get("limit", len(self.state["history"])))
        entries = self.state["history"][-limit:]
        return (1, {"entries": entries, "count": len(entries)}, None)

    def report(self, params=None):
        params = params or {}
        summary = {
            "baselines": list(self.state["baselines"].keys()),
            "history_count": len(self.state["history"]),
            "history": self.state["history"],
        }
        fmt = params.get("format", "dict")
        if fmt == "json":
            output = json.dumps(summary, indent=2)
        else:
            output = summary
        return (1, {"format": fmt, "report": output}, None)
