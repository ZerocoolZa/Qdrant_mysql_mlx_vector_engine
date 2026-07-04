#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_rules.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="BCL IR RuleEngine — evaluates rules against method/class/file features"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_rules.py" domain="BCL" authority="RuleEngine"}
# [@SUMMARY]{summary="BCL RuleEngine: evaluates rule predicates against method/class/file feature dicts."}
# [@CLASS]{class="RuleEngine" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="evaluate_method" type="command"}
# [@METHOD]{method="evaluate_class" type="command"}
# [@METHOD]{method="evaluate_file" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}


class RuleEngine:
    """Evaluate rule predicates against feature dicts."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "rules": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            rules = param.get("rules")
            if rules:
                self.state["rules"] = rules
            for key, value in param.items():
                if key != "rules":
                    self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "evaluate_method":
            return self.EvaluateMethod(params)
        elif command == "evaluate_class":
            return self.EvaluateClass(params)
        elif command == "evaluate_file":
            return self.EvaluateFile(params)
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
            if key == "rules":
                self.state["rules"] = value
            else:
                self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def EvaluateMethod(self, params):
        mf = self._p(params, "features")
        if mf is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        out = []
        for r in self.state["rules"]:
            if r.get("scope") == "method" and r["predicate"](mf):
                out.append({"rule": r["id"], "scope": "method",
                            "method": mf.get("name", ""),
                            "severity": r.get("severity", "high"),
                            "description": r.get("description", "")})
        return (1, {"violations": out, "count": len(out)}, None)

    def EvaluateClass(self, params):
        cf = self._p(params, "features")
        if cf is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        out = []
        for r in self.state["rules"]:
            if r.get("scope") == "class" and r["predicate"](cf):
                out.append({"rule": r["id"], "scope": "class",
                            "severity": r.get("severity", "high"),
                            "description": r.get("description", "")})
        return (1, {"violations": out, "count": len(out)}, None)

    def EvaluateFile(self, params):
        ff = self._p(params, "features")
        if ff is None:
            return (0, None, ("MISSING_PARAM", "features required", 0))
        out = []
        for r in self.state["rules"]:
            if r.get("scope") == "file" and r["predicate"](ff):
                out.append({"rule": r["id"], "scope": "file",
                            "severity": r.get("severity", "high"),
                            "description": r.get("description", "")})
        return (1, {"violations": out, "count": len(out)}, None)
