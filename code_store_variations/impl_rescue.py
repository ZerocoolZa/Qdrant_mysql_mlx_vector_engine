import os
import shutil
import json
import re


class DomRescue:
    """Rescue domain: backup, recovery, repair, and diagnostic operations for system state."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "backup": self.backup,
            "clean": self.clean,
            "diagnose": self.diagnose,
            "escalate": self.escalate,
            "quarantine": self.quarantine,
            "recover": self.recover,
            "repair": self.repair,
            "report": self.report,
            "restore": self.restore,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def backup(self, params=None):
        params = params or {}
        try:
            source = str(params.get("source", ""))
            dest = str(params.get("dest", ""))
            if not source or not os.path.exists(source):
                result = {"domain": "rescue", "method": "backup", "data": {"backed_up": False, "reason": "source_not_found"}}
                return (1, result, None)
            if os.path.isdir(source):
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest)
            self.state["results"].append({"action": "backup", "source": source, "dest": dest})
            result = {"domain": "rescue", "method": "backup", "data": {"backed_up": True, "source": source, "dest": dest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BACKUP_ERROR", str(e), 0))

    def clean(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            pattern = params.get("pattern")
            removed = []
            if target and os.path.isdir(target):
                for entry in os.listdir(target):
                    full = os.path.join(target, entry)
                    if pattern is None or re.search(pattern, entry):
                        if os.path.isfile(full):
                            os.remove(full)
                            removed.append(entry)
            self.state["results"].append({"action": "clean", "target": target, "removed": removed})
            result = {"domain": "rescue", "method": "clean", "data": {"removed": removed, "count": len(removed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLEAN_ERROR", str(e), 0))

    def diagnose(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            checks = params.get("checks", ["exists", "readable", "size"])
            if not isinstance(checks, (list, tuple)):
                checks = [checks]
            findings = []
            exists = os.path.exists(target) if target else False
            for check in checks:
                if check == "exists":
                    findings.append({"check": "exists", "ok": exists})
                elif check == "readable":
                    ok = exists and os.access(target, os.R_OK)
                    findings.append({"check": "readable", "ok": ok})
                elif check == "writable":
                    ok = exists and os.access(target, os.W_OK)
                    findings.append({"check": "writable", "ok": ok})
                elif check == "size":
                    size = os.path.getsize(target) if exists and os.path.isfile(target) else 0
                    findings.append({"check": "size", "ok": size > 0, "size": size})
            healthy = all(f.get("ok", False) for f in findings)
            result = {"domain": "rescue", "method": "diagnose", "data": {"target": target, "findings": findings, "healthy": healthy}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIAGNOSE_ERROR", str(e), 0))

    def escalate(self, params=None):
        params = params or {}
        try:
            issue = str(params.get("issue", ""))
            level = str(params.get("level", "warn"))
            self.state["results"].append({"action": "escalate", "issue": issue, "level": level})
            result = {"domain": "rescue", "method": "escalate", "data": {"escalated": True, "issue": issue, "level": level}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ESCALATE_ERROR", str(e), 0))

    def quarantine(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            dest = str(params.get("dest", ""))
            if not target or not os.path.exists(target):
                result = {"domain": "rescue", "method": "quarantine", "data": {"quarantined": False, "reason": "target_not_found"}}
                return (1, result, None)
            if not dest:
                dest = target + ".quarantine"
            shutil.move(target, dest)
            self.state["results"].append({"action": "quarantine", "target": target, "dest": dest})
            result = {"domain": "rescue", "method": "quarantine", "data": {"quarantined": True, "target": target, "dest": dest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("QUARANTINE_ERROR", str(e), 0))

    def recover(self, params=None):
        params = params or {}
        try:
            source = str(params.get("source", ""))
            dest = str(params.get("dest", ""))
            if not source or not os.path.exists(source):
                result = {"domain": "rescue", "method": "recover", "data": {"recovered": False, "reason": "source_not_found"}}
                return (1, result, None)
            if os.path.isdir(source):
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest)
            self.state["results"].append({"action": "recover", "source": source, "dest": dest})
            result = {"domain": "rescue", "method": "recover", "data": {"recovered": True, "source": source, "dest": dest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECOVER_ERROR", str(e), 0))

    def repair(self, params=None):
        params = params or {}
        try:
            target = str(params.get("target", ""))
            strategy = str(params.get("strategy", "recreate"))
            repaired = False
            if target and strategy == "recreate":
                if not os.path.exists(target):
                    os.makedirs(target, exist_ok=True) if params.get("is_dir", False) else open(target, "a").close()
                    repaired = True
            elif target and strategy == "truncate":
                if os.path.exists(target) and os.path.isfile(target):
                    open(target, "w").close()
                    repaired = True
            self.state["results"].append({"action": "repair", "target": target, "strategy": strategy, "repaired": repaired})
            result = {"domain": "rescue", "method": "repair", "data": {"repaired": repaired, "target": target, "strategy": strategy}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPAIR_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            actions = list(self.state.get("results", []))
            result = {"domain": "rescue", "method": "report", "data": {"actions": actions, "count": len(actions)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def restore(self, params=None):
        params = params or {}
        try:
            source = str(params.get("source", ""))
            dest = str(params.get("dest", ""))
            if not source or not os.path.exists(source):
                result = {"domain": "rescue", "method": "restore", "data": {"restored": False, "reason": "source_not_found"}}
                return (1, result, None)
            if os.path.isdir(source):
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest)
            self.state["results"].append({"action": "restore", "source": source, "dest": dest})
            result = {"domain": "rescue", "method": "restore", "data": {"restored": True, "source": source, "dest": dest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESTORE_ERROR", str(e), 0))
