class DomGovernance:
    """Governance engine: policies, rules, approvals, reviews, violations and waivers."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "policies": {},
            "rules": {},
            "requests": {},
            "violations": [],
            "exceptions": [],
        }
        self.mem = mem
        self.db = db
        self._next_id = 1

    def _new_id(self):
        cid = self._next_id
        self._next_id += 1
        return cid

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "approve": self.approve,
            "compliance": self.compliance,
            "constraint": self.constraint,
            "enforce": self.enforce,
            "escalate": self.escalate,
            "exception": self.exception,
            "policy": self.policy,
            "reject": self.reject,
            "report": self.report,
            "review": self.review,
            "rule": self.rule,
            "violation": self.violation,
            "waive": self.waive,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def policy(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("MISSING_NAME", "policy name required", 0))
            if name not in self.state["policies"]:
                pid = self._new_id()
                policy = {
                    "id": pid,
                    "name": name,
                    "description": params.get("description", ""),
                    "constraints": params.get("constraints", []),
                    "active": True,
                }
                self.state["policies"][name] = policy
                self.state["catalog"].append({"type": "policy", "id": pid, "name": name})
            data = self.state["policies"][name]
            result = {"domain": "governance", "method": "policy", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("POLICY_ERROR", str(e), 0))

    def rule(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("MISSING_NAME", "rule name required", 0))
            if name not in self.state["rules"]:
                rid = self._new_id()
                rule = {
                    "id": rid,
                    "name": name,
                    "policy": params.get("policy"),
                    "condition": params.get("condition", ""),
                    "action": params.get("action", "deny"),
                    "severity": params.get("severity", "medium"),
                }
                self.state["rules"][name] = rule
            data = self.state["rules"][name]
            result = {"domain": "governance", "method": "rule", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RULE_ERROR", str(e), 0))

    def constraint(self, params=None):
        params = params or {}
        try:
            policy_name = params.get("policy")
            constraint = params.get("constraint")
            if policy_name is None or constraint is None:
                return (0, None, ("MISSING_CONSTRAINT", "policy and constraint required", 0))
            policy = self.state["policies"].get(policy_name)
            if policy is None:
                return (0, None, ("POLICY_NOT_FOUND", f"no policy {policy_name}", 0))
            policy["constraints"].append(constraint)
            result = {"domain": "governance", "method": "constraint", "data": policy}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CONSTRAINT_ERROR", str(e), 0))

    def review(self, params=None):
        params = params or {}
        try:
            request_id = params.get("request_id")
            if request_id is None:
                return (0, None, ("MISSING_REQUEST", "request_id required", 0))
            req = self.state["requests"].get(request_id)
            if req is None:
                req = {"id": request_id, "status": "reviewing", "reviewer": params.get("reviewer")}
                self.state["requests"][request_id] = req
            req["status"] = "reviewing"
            req["notes"] = params.get("notes", "")
            result = {"domain": "governance", "method": "review", "data": req}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REVIEW_ERROR", str(e), 0))

    def approve(self, params=None):
        params = params or {}
        try:
            request_id = params.get("request_id")
            req = self.state["requests"].get(request_id)
            if req is None:
                req = {"id": request_id, "status": "pending"}
                self.state["requests"][request_id] = req
            req["status"] = "approved"
            req["approver"] = params.get("approver")
            result = {"domain": "governance", "method": "approve", "data": req}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("APPROVE_ERROR", str(e), 0))

    def reject(self, params=None):
        params = params or {}
        try:
            request_id = params.get("request_id")
            req = self.state["requests"].get(request_id)
            if req is None:
                req = {"id": request_id, "status": "pending"}
                self.state["requests"][request_id] = req
            req["status"] = "rejected"
            req["reason"] = params.get("reason", "")
            result = {"domain": "governance", "method": "reject", "data": req}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REJECT_ERROR", str(e), 0))

    def enforce(self, params=None):
        params = params or {}
        try:
            action = params.get("action")
            context = params.get("context", {})
            violations = []
            for rule in self.state["rules"].values():
                cond = rule.get("condition", "")
                if cond and cond in str(context):
                    violations.append({"rule": rule["name"], "action": rule["action"], "severity": rule["severity"]})
                    if rule["action"] == "deny":
                        self.state["violations"].append({"rule": rule["name"], "context": context})
            result = {"domain": "governance", "method": "enforce", "data": {"action": action, "violations": violations, "allowed": len(violations) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENFORCE_ERROR", str(e), 0))

    def violation(self, params=None):
        params = params or {}
        try:
            vid = params.get("violation_id")
            if vid is not None:
                data = self.state["violations"][vid] if vid < len(self.state["violations"]) else {}
            else:
                data = list(self.state["violations"])
            result = {"domain": "governance", "method": "violation", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VIOLATION_ERROR", str(e), 0))

    def escalate(self, params=None):
        params = params or {}
        try:
            request_id = params.get("request_id")
            req = self.state["requests"].get(request_id)
            if req is None:
                req = {"id": request_id, "status": "pending"}
                self.state["requests"][request_id] = req
            req["status"] = "escalated"
            req["escalated_to"] = params.get("escalated_to")
            result = {"domain": "governance", "method": "escalate", "data": req}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ESCALATE_ERROR", str(e), 0))

    def exception(self, params=None):
        params = params or {}
        try:
            eid = self._new_id()
            exc = {
                "id": eid,
                "request_id": params.get("request_id"),
                "rule": params.get("rule"),
                "reason": params.get("reason", ""),
                "granted": params.get("granted", False),
            }
            self.state["exceptions"].append(exc)
            result = {"domain": "governance", "method": "exception", "data": exc}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXCEPTION_ERROR", str(e), 0))

    def waive(self, params=None):
        params = params or {}
        try:
            request_id = params.get("request_id")
            req = self.state["requests"].get(request_id)
            if req is None:
                req = {"id": request_id, "status": "pending"}
                self.state["requests"][request_id] = req
            req["status"] = "waived"
            req["waived_by"] = params.get("waived_by")
            result = {"domain": "governance", "method": "waive", "data": req}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WAIVE_ERROR", str(e), 0))

    def compliance(self, params=None):
        params = params or {}
        try:
            policy_name = params.get("policy")
            context = params.get("context", {})
            policy = self.state["policies"].get(policy_name)
            if policy is None:
                return (0, None, ("POLICY_NOT_FOUND", f"no policy {policy_name}", 0))
            constraints = policy.get("constraints", [])
            failed = []
            for c in constraints:
                if isinstance(c, str) and c not in str(context):
                    failed.append(c)
            compliant = len(failed) == 0
            result = {"domain": "governance", "method": "compliance", "data": {"policy": policy_name, "compliant": compliant, "failed": failed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPLIANCE_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            data = {
                "policies": len(self.state["policies"]),
                "rules": len(self.state["rules"]),
                "requests": len(self.state["requests"]),
                "violations": len(self.state["violations"]),
                "exceptions": len(self.state["exceptions"]),
                "request_status": {rid: r.get("status") for rid, r in self.state["requests"].items()},
            }
            result = {"domain": "governance", "method": "report", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
