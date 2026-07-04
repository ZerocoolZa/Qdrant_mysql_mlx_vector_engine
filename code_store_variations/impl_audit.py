class DomAudit:
    """Audit operations: baselines, checks, compliance, diffs, drift, violations, reports."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._baselines = {}
        self._history = []

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "baseline": self.baseline,
            "check": self.check,
            "compliance": self.compliance,
            "diff": self.diff,
            "drift": self.drift,
            "escalate": self.escalate,
            "fix": self.fix,
            "flag": self.flag,
            "history": self.history,
            "report": self.report,
            "trace": self.trace,
            "violation": self.violation,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _record(self, entry):
        self._history.append(entry)
        return entry

    def baseline(self, params=None):
        params = params or {}
        try:
            import hashlib, json
            name = params.get("name", "default")
            data = params.get("data")
            payload = json.dumps(data, sort_keys=True).encode("utf-8") if data is not None else b""
            digest = hashlib.sha256(payload).hexdigest()
            self._baselines[name] = {"name": name, "data": data, "hash": digest}
            self._record({"action": "baseline", "name": name, "hash": digest})
            result = {"domain": "audit", "method": "baseline", "data": {"name": name, "hash": digest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BASELINE_ERROR", str(e), 0))

    def check(self, params=None):
        params = params or {}
        try:
            import hashlib, json
            name = params.get("name", "default")
            data = params.get("data")
            baseline = self._baselines.get(name)
            if not baseline:
                return (0, None, ("CHECK_ERROR", "no baseline", 0))
            payload = json.dumps(data, sort_keys=True).encode("utf-8") if data is not None else b""
            digest = hashlib.sha256(payload).hexdigest()
            passed = digest == baseline["hash"]
            self._record({"action": "check", "name": name, "passed": passed})
            result = {"domain": "audit", "method": "check", "data": {"name": name, "passed": passed, "current": digest, "baseline": baseline["hash"]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_ERROR", str(e), 0))

    def compliance(self, params=None):
        params = params or {}
        try:
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
            self._record({"action": "compliance", "passed": len(passed), "failed": len(failed)})
            result = {"domain": "audit", "method": "compliance", "data": {"passed": passed, "failed": failed, "compliant": len(failed) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPLIANCE_ERROR", str(e), 0))

    def diff(self, params=None):
        params = params or {}
        try:
            import difflib
            a = params.get("a", "")
            b = params.get("b", "")
            a_lines = a.splitlines() if isinstance(a, str) else [str(x) for x in a]
            b_lines = b.splitlines() if isinstance(b, str) else [str(x) for x in b]
            changes = list(difflib.unified_diff(a_lines, b_lines, lineterm=""))
            self._record({"action": "diff", "changes": len(changes)})
            result = {"domain": "audit", "method": "diff", "data": {"changes": changes, "count": len(changes)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIFF_ERROR", str(e), 0))

    def drift(self, params=None):
        params = params or {}
        try:
            import hashlib, json
            name = params.get("name", "default")
            data = params.get("data")
            baseline = self._baselines.get(name)
            if not baseline:
                return (0, None, ("DRIFT_ERROR", "no baseline", 0))
            payload = json.dumps(data, sort_keys=True).encode("utf-8") if data is not None else b""
            digest = hashlib.sha256(payload).hexdigest()
            drifted = digest != baseline["hash"]
            self._record({"action": "drift", "name": name, "drifted": drifted})
            result = {"domain": "audit", "method": "drift", "data": {"name": name, "drifted": drifted, "current": digest, "baseline": baseline["hash"]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DRIFT_ERROR", str(e), 0))

    def escalate(self, params=None):
        params = params or {}
        try:
            issue = params.get("issue", "")
            level = int(params.get("level", 1))
            to = params.get("to", "admin")
            self._record({"action": "escalate", "issue": issue, "level": level, "to": to})
            result = {"domain": "audit", "method": "escalate", "data": {"issue": issue, "level": level, "to": to, "escalated": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ESCALATE_ERROR", str(e), 0))

    def fix(self, params=None):
        params = params or {}
        try:
            issue = params.get("issue", "")
            action = params.get("action", "")
            self._record({"action": "fix", "issue": issue, "fix": action})
            result = {"domain": "audit", "method": "fix", "data": {"issue": issue, "action": action, "applied": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FIX_ERROR", str(e), 0))

    def flag(self, params=None):
        params = params or {}
        try:
            target = params.get("target", "")
            reason = params.get("reason", "")
            severity = params.get("severity", "low")
            self._record({"action": "flag", "target": target, "reason": reason, "severity": severity})
            result = {"domain": "audit", "method": "flag", "data": {"target": target, "reason": reason, "severity": severity, "flagged": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FLAG_ERROR", str(e), 0))

    def history(self, params=None):
        params = params or {}
        try:
            limit = int(params.get("limit", len(self._history)))
            entries = self._history[-limit:]
            result = {"domain": "audit", "method": "history", "data": {"entries": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HISTORY_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            import json
            summary = {
                "baselines": list(self._baselines.keys()),
                "history_count": len(self._history),
                "history": self._history,
            }
            fmt = params.get("format", "dict")
            if fmt == "json":
                output = json.dumps(summary, indent=2)
            else:
                output = summary
            result = {"domain": "audit", "method": "report", "data": {"format": fmt, "report": output}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def trace(self, params=None):
        params = params or {}
        try:
            target = params.get("target", "")
            entries = [h for h in self._history if h.get("action") in ("check", "drift", "flag", "fix") or target in str(h)]
            result = {"domain": "audit", "method": "trace", "data": {"target": target, "trace": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRACE_ERROR", str(e), 0))

    def violation(self, params=None):
        params = params or {}
        try:
            rule = params.get("rule", "")
            target = params.get("target", "")
            detail = params.get("detail", "")
            entry = {"action": "violation", "rule": rule, "target": target, "detail": detail}
            self._record(entry)
            result = {"domain": "audit", "method": "violation", "data": {"rule": rule, "target": target, "detail": detail, "recorded": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VIOLATION_ERROR", str(e), 0))
