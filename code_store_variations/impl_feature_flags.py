"""VBStyle domain implementation: feature_flags.

Feature toggles: rollout, A/B testing, kill switches, targeting rules.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import hashlib


class DomFeatureFlags:
    """Feature toggles: rollout, A/B testing, kill switches, targeting rules."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._flags = {}
        self._evaluations = []

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "is_enabled": self.is_enabled,
            "get_flag": self.get_flag,
            "create_flag": self.create_flag,
            "set_targeting": self.set_targeting,
            "rollout": self.rollout,
            "track_evaluation": self.track_evaluation,
            "kill_switch": self.kill_switch,
            "get_variants": self.get_variants,
            "list_flags": self.list_flags,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def is_enabled(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("IS_ENABLED_ERROR", "missing name", 0))
            flag = self._flags.get(name)
            if flag is None:
                result = {"domain": "feature_flags", "method": "is_enabled", "data": {"name": name, "enabled": False, "reason": "not_found"}}
                return (1, result, None)
            if flag.get("killed"):
                result = {"domain": "feature_flags", "method": "is_enabled", "data": {"name": name, "enabled": False, "reason": "killed"}}
                return (1, result, None)
            user_id = params.get("user_id")
            rollout_pct = flag.get("rollout_pct", 0)
            if rollout_pct >= 100:
                enabled = True
                reason = "full_rollout"
            elif rollout_pct <= 0:
                enabled = False
                reason = "no_rollout"
            else:
                if user_id is None:
                    enabled = False
                    reason = "no_user_id"
                else:
                    bucket = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 100
                    enabled = bucket < rollout_pct
                    reason = "in_rollout" if enabled else "out_of_rollout"
            targeting = flag.get("targeting") or {}
            if enabled and targeting:
                ctx = params.get("context") or {}
                for key, allowed in targeting.items():
                    if key in ctx and ctx[key] not in allowed:
                        enabled = False
                        reason = "targeting_excluded"
                        break
            self._evaluations.append({"name": name, "user_id": user_id, "enabled": enabled, "reason": reason, "ts": time.time()})
            result = {"domain": "feature_flags", "method": "is_enabled", "data": {"name": name, "enabled": enabled, "reason": reason}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IS_ENABLED_ERROR", str(e), 0))

    def get_flag(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("GET_FLAG_ERROR", "missing name", 0))
            flag = self._flags.get(name)
            if flag is None:
                result = {"domain": "feature_flags", "method": "get_flag", "data": {"name": name, "found": False}}
            else:
                result = {"domain": "feature_flags", "method": "get_flag", "data": {"name": name, "found": True, "flag": flag}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_FLAG_ERROR", str(e), 0))

    def create_flag(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("CREATE_FLAG_ERROR", "missing name", 0))
            flag = {
                "name": name,
                "enabled": bool(params.get("enabled", False)),
                "rollout_pct": int(params.get("rollout_pct", 0)),
                "variants": params.get("variants") or ["off", "on"],
                "targeting": params.get("targeting") or {},
                "killed": False,
                "created_at": time.time(),
                "description": params.get("description", ""),
            }
            self._flags[name] = flag
            result = {"domain": "feature_flags", "method": "create_flag", "data": {"name": name, "created": True, "flag": flag}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_FLAG_ERROR", str(e), 0))

    def set_targeting(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            targeting = params.get("targeting")
            if not name:
                return (0, None, ("SET_TARGETING_ERROR", "missing name", 0))
            if targeting is None:
                return (0, None, ("SET_TARGETING_ERROR", "missing targeting", 0))
            flag = self._flags.get(name)
            if flag is None:
                return (0, None, ("SET_TARGETING_ERROR", "flag not found", 0))
            flag["targeting"] = targeting
            result = {"domain": "feature_flags", "method": "set_targeting", "data": {"name": name, "targeting": targeting}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_TARGETING_ERROR", str(e), 0))

    def rollout(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            pct = params.get("percentage")
            if not name or pct is None:
                return (0, None, ("ROLLOUT_ERROR", "missing name or percentage", 0))
            pct = int(pct)
            if pct < 0 or pct > 100:
                return (0, None, ("ROLLOUT_ERROR", "percentage must be 0-100", 0))
            flag = self._flags.get(name)
            if flag is None:
                return (0, None, ("ROLLOUT_ERROR", "flag not found", 0))
            previous = flag.get("rollout_pct", 0)
            flag["rollout_pct"] = pct
            flag["enabled"] = pct > 0
            result = {"domain": "feature_flags", "method": "rollout", "data": {"name": name, "percentage": pct, "previous": previous}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROLLOUT_ERROR", str(e), 0))

    def track_evaluation(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("TRACK_EVALUATION_ERROR", "missing name", 0))
            evals = [e for e in self._evaluations if e.get("name") == name]
            enabled_count = sum(1 for e in evals if e.get("enabled"))
            result = {"domain": "feature_flags", "method": "track_evaluation", "data": {"name": name, "total": len(evals), "enabled": enabled_count, "disabled": len(evals) - enabled_count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRACK_EVALUATION_ERROR", str(e), 0))

    def kill_switch(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("KILL_SWITCH_ERROR", "missing name", 0))
            flag = self._flags.get(name)
            if flag is None:
                return (0, None, ("KILL_SWITCH_ERROR", "flag not found", 0))
            previous = flag.get("killed", False)
            flag["killed"] = True
            flag["enabled"] = False
            flag["rollout_pct"] = 0
            result = {"domain": "feature_flags", "method": "kill_switch", "data": {"name": name, "killed": True, "previous": previous}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("KILL_SWITCH_ERROR", str(e), 0))

    def get_variants(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("GET_VARIANTS_ERROR", "missing name", 0))
            flag = self._flags.get(name)
            if flag is None:
                return (0, None, ("GET_VARIANTS_ERROR", "flag not found", 0))
            variants = flag.get("variants", [])
            result = {"domain": "feature_flags", "method": "get_variants", "data": {"name": name, "variants": variants, "count": len(variants)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_VARIANTS_ERROR", str(e), 0))

    def list_flags(self, params=None):
        params = params or {}
        try:
            flags = []
            for name, flag in self._flags.items():
                flags.append({
                    "name": name,
                    "enabled": flag.get("enabled", False),
                    "rollout_pct": flag.get("rollout_pct", 0),
                    "killed": flag.get("killed", False),
                })
            result = {"domain": "feature_flags", "method": "list_flags", "data": {"flags": flags, "count": len(flags)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LIST_FLAGS_ERROR", str(e), 0))
