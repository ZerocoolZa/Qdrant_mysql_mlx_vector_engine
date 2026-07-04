#[@GHOST] file=/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Bloodhound/common.py date=2026-07-04
#[@VBSTYLE] version=1 shape=VBStyleCore
#[@FILEID] id=COMMON_001 domain=Bloodhound
#[@SUMMARY] Shared classes BCL ErrorHandler Law for v4/v5 debugger and error AI
#[@CLASS] BCL ErrorHandler Law
#[@METHOD] read_all write_container rewrite_all find_by_key capture test_fix report get_stats create read update delete check_all list_laws Run

import os, time
from datetime import datetime


class BCL:
    """Reads/writes BCL (Bracket Command Language) format."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.state = {}
        if param and "file_path" in param:
            self.state["file_path"] = param["file_path"]
        else:
            self.state["file_path"] = "knowledge.bcl"
        if not os.path.exists(self.state["file_path"]):
            with open(self.state["file_path"], "w") as f:
                f.write("# BCL Knowledge Store\n\n")

    def Run(self, command, params=None):
        dispatch = {
            "read_all": lambda: self.read_all(),
            "write_container": lambda: self.write_container(params.get("bcl_type"), params.get("data")),
            "rewrite_all": lambda: self.rewrite_all(params.get("containers")),
            "find_by_key": lambda: self.find_by_key(params.get("bcl_type"), params.get("key"), params.get("value")),
        }
        if command in dispatch:
            result = dispatch[command]()
            return (1, result, None)
        return (0, None, (404, f"Unknown command: {command}", 0))

    def read_all(self):
        results = []
        if not os.path.exists(self.state["file_path"]):
            return results
        with open(self.state["file_path"], "r") as f:
            content = f.read()
        ct = None
        cd = None
        for line in content.split("\n"):
            s = line.strip()
            if s.startswith("[@") and "]" in s:
                if cd:
                    results.append((ct, cd))
                ct = s[2:s.index("]")]
                cd = {}
            elif cd is not None and "}" in s:
                if cd:
                    results.append((ct, cd))
                cd = None
                ct = None
            elif cd is not None and "(" in s and ";" in s:
                parts = s.strip("()").split(";")
                if len(parts) >= 2:
                    cd[parts[0].strip().strip('"')] = parts[1].strip().strip('"')
        if cd:
            results.append((ct, cd))
        return results

    def write_container(self, bcl_type, data):
        lines = [f"[@{bcl_type}]", "{"]
        for k, v in data.items():
            lines.append(f'    ("{k}";"{v}")')
        lines.append("}\n")
        with open(self.state["file_path"], "a") as f:
            f.write("\n".join(lines) + "\n")
        return (1, {"written": True}, None)

    def rewrite_all(self, containers):
        with open(self.state["file_path"], "w") as f:
            f.write("# BCL Knowledge Store\n")
            f.write(f"# Updated: {datetime.now().isoformat()}\n\n")
            for ct, d in containers:
                f.write(f"[@{ct}]\n{{\n")
                for k, v in d.items():
                    f.write(f'    ("{k}";"{v}")\n')
                f.write("}\n\n")
        return (1, {"rewritten": len(containers)}, None)

    def find_by_key(self, bcl_type, key, value):
        return [d for ct, d in self.read_all() if ct == bcl_type and d.get(key) == value]


class ErrorHandler:
    """Self-learning error handler. Error -> compare -> fix -> test -> promote.
    All errors and fixes stored as BCL in a .bcl file.

    Loop:
      1. capture(producer, entity, pattern, description, severity, payload)
      2. Search BCL store for matching pattern
      3. If found: return known fix, increment occurrences, update confidence
      4. If new: record as BCL, suggest auto-fix
      5. test_fix(pattern, success) -> promote or demote
      6. Promoted fixes have high confidence on next encounter
    """

    STATUS_NEW = "new"
    STATUS_TESTING = "testing"
    STATUS_PROMOTED = "promoted"
    STATUS_FAILED = "failed"

    AUTO_FIXES = {
        "SyntaxError": "fix syntax error in source code",
        "IndentationError": "fix indentation to be consistent (use only spaces)",
        "TabError": "use only spaces or only tabs, do not mix",
        "NameError": "define the variable before using it",
        "UnboundLocalError": "assign local variable before reading it",
        "TypeError": "check types before operation or convert types",
        "ValueError": "validate input value before conversion or operation",
        "KeyError": "check key exists with .get() or 'in' before access",
        "IndexError": "check len() before indexing into list",
        "AttributeError": "check object type before calling method",
        "ImportError": "check module name or install missing package",
        "ModuleNotFoundError": "install the module with pip or check path",
        "FileNotFoundError": "check file path exists or create file first",
        "FileExistsError": "check if file exists before creating, or use different name",
        "ZeroDivisionError": "check divisor is not zero before dividing",
        "OverflowError": "use smaller values or catch overflow",
        "FloatingPointError": "check for NaN or infinity in float operations",
        "RecursionError": "add base case to recursive function",
        "StopIteration": "use for loop or catch StopIteration explicitly",
        "StopAsyncIteration": "add StopAsyncIteration handling in async generator",
        "RuntimeError": "handle the specific error condition that triggered this",
        "NotImplementedError": "implement the method or feature that was called",
        "AssertionError": "fix the condition that failed the assert",
        "MemoryError": "reduce data size or free memory before allocating",
        "BufferError": "check buffer size and alignment before buffer operation",
        "EOFError": "check for end of input before reading",
        "KeyError": "check key exists with .get() or 'in' before access",
        "LookupError": "check key or index exists before lookup",
        "ArithmeticError": "validate operands before arithmetic operation",
        "ReferenceError": "keep a reference to the object before accessing weakref",
        "OSError": "check OS resource availability and permissions",
        "IOError": "check file permissions, disk space, and path validity",
        "EnvironmentError": "check environment variables and OS resources",
        "PermissionError": "check file permissions or run with appropriate privileges",
        "IsADirectoryError": "check path is a file not a directory before file operations",
        "NotADirectoryError": "check path is a directory before directory operations",
        "TimeoutError": "increase timeout or optimize the operation",
        "InterruptedError": "retry the operation or handle the interrupt signal",
        "BlockingIOError": "use non-blocking I/O or wait for resource",
        "ChildProcessError": "check child process status and exit code",
        "BrokenPipeError": "check pipe is connected before writing",
        "ConnectionError": "check network connection and retry",
        "ConnectionAbortedError": "check connection stability and reconnect",
        "ConnectionRefusedError": "check if server is running and port is open",
        "ConnectionResetError": "handle network reset and reconnect",
        "ProcessLookupError": "check process ID exists before signaling",
        "UnicodeError": "check encoding is correct for the data",
        "UnicodeDecodeError": "specify correct encoding or use errors='replace'",
        "UnicodeEncodeError": "specify correct encoding or use errors='replace'",
        "UnicodeTranslateError": "check character exists in target encoding",
        "SystemError": "report as Python interpreter bug, try different approach",
        "SystemExit": "handle sys.exit() call gracefully",
        "KeyboardInterrupt": "handle Ctrl+C signal gracefully",
        "GeneratorExit": "handle generator close properly",
        "ExceptionGroup": "unwrap and handle each exception in the group",
        "BaseExceptionGroup": "unwrap and handle each exception in the group",
        "PythonFinalizationError": "avoid calling during interpreter shutdown",
        "BytesWarning": "check for bytes vs str comparison",
        "DeprecationWarning": "update code to use new API instead of deprecated one",
        "FutureWarning": "update code to handle future behavior change",
        "ImportWarning": "check import path and module compatibility",
        "PendingDeprecationWarning": "plan migration before deprecation",
        "ResourceWarning": "close resources properly with context managers",
        "RuntimeWarning": "investigate runtime condition that triggered warning",
        "SyntaxWarning": "fix suspicious syntax that Python warns about",
        "UnicodeWarning": "check for unicode vs bytes comparison",
        "UserWarning": "review user-defined warning condition",
        "Warning": "review the warning message and address root cause",
    }

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.state = {"errors": [], "known": {}}
        if param and "bcl_file_path" in param:
            self.state["bcl_file_path"] = param["bcl_file_path"]
        else:
            self.state["bcl_file_path"] = "error_knowledge.bcl"
        self.bcl = BCL(param={"file_path": self.state["bcl_file_path"]})
        self._load_known()

    def Run(self, command, params=None):
        dispatch = {
            "capture": lambda: self.capture(
                params.get("producer", ""), params.get("entity", ""),
                params.get("pattern", ""), params.get("description", ""),
                params.get("severity", 1), params.get("payload")),
            "test_fix": lambda: self.test_fix(params.get("pattern", ""), params.get("success", False)),
            "report": lambda: self.report(),
            "get_stats": lambda: self.get_stats(),
        }
        if command in dispatch:
            result = dispatch[command]()
            return (1, result, None)
        return (0, None, (404, f"Unknown command: {command}", 0))

    def _load_known(self):
        for ct, d in self.bcl.read_all():
            if ct == "ERROR":
                p = d.get("pattern", "")
                if p:
                    self.state["known"][p] = d

    def capture(self, producer, entity, pattern, description, severity=1, payload=None):
        """Capture an error. Compare to known. Return fix suggestion."""
        record = {
            "producer": producer, "entity": entity, "pattern": pattern,
            "description": description, "severity": severity,
            "payload": payload, "timestamp": datetime.now().isoformat(),
        }
        self.state["errors"].append(record)

        if pattern in self.state["known"]:
            known = self.state["known"][pattern]
            occ = int(known.get("occurrences", "0")) + 1
            conf = float(known.get("confidence", "0.5"))
            status = known.get("status", self.STATUS_NEW)
            fix = known.get("fix", "unknown")

            if status == self.STATUS_PROMOTED:
                conf = min(1.0, conf + 0.05)
            elif status == self.STATUS_TESTING:
                conf = min(0.9, conf + 0.02)

            self._update_known(pattern, occ, conf, status, known)
            return {"found": True, "fix": fix, "confidence": conf,
                    "status": status, "occurrences": occ,
                    "message": f"Known error (seen {occ}x): {fix}"}
        else:
            auto_fix = self.AUTO_FIXES.get(pattern, "investigate manually")
            self._record_new(producer, entity, pattern, description, auto_fix, severity)

            return {"found": False, "fix": auto_fix, "confidence": 0.3,
                    "status": self.STATUS_NEW, "occurrences": 1,
                    "message": f"NEW error: {pattern}. Suggested: {auto_fix}"}

    def _record_new(self, producer, entity, pattern, description, fix, severity):
        data = {
            "producer": producer, "entity": entity, "pattern": pattern,
            "description": description, "fix": fix, "confidence": "0.30",
            "status": self.STATUS_NEW, "occurrences": "1",
            "last_seen": datetime.now().isoformat(),
        }
        self.bcl.write_container("ERROR", data)
        self.state["known"][pattern] = data

    def _update_known(self, pattern, occurrences, confidence, status, existing):
        existing["occurrences"] = str(occurrences)
        existing["confidence"] = f"{confidence:.2f}"
        existing["status"] = status
        existing["last_seen"] = datetime.now().isoformat()
        self._rewrite_all_known()
    def _rewrite_all_known(self):
        containers = []
        for pattern, d in self.state["known"].items():
            containers.append(("ERROR", d))
        self.bcl.rewrite_all(containers)

    def test_fix(self, pattern, success):
        """Report whether a fix worked. Promote or demote accordingly."""
        if pattern not in self.state["known"]:
            return {"message": "Unknown pattern, nothing to test",
                    "status": "unknown", "confidence": "0.00"}

        known = self.state["known"][pattern]
        status = known.get("status", self.STATUS_NEW)
        conf = float(known.get("confidence", "0.3"))

        if success:
            if status == self.STATUS_NEW:
                known["status"] = self.STATUS_TESTING
                known["confidence"] = f"{min(0.7, conf + 0.2):.2f}"
            elif status == self.STATUS_TESTING:
                known["status"] = self.STATUS_PROMOTED
                known["confidence"] = f"{min(1.0, conf + 0.2):.2f}"
            elif status == self.STATUS_PROMOTED:
                known["confidence"] = f"{min(1.0, conf + 0.05):.2f}"
            result = f"Fix for {pattern}: SUCCESS -> {known['status']} (conf={known['confidence']})"
        else:
            if status == self.STATUS_PROMOTED:
                known["status"] = self.STATUS_TESTING
                known["confidence"] = f"{max(0.3, conf - 0.2):.2f}"
            elif status == self.STATUS_TESTING:
                known["status"] = self.STATUS_FAILED
                known["confidence"] = f"{max(0.1, conf - 0.3):.2f}"
            elif status == self.STATUS_NEW:
                known["status"] = self.STATUS_FAILED
                known["confidence"] = f"{max(0.1, conf - 0.1):.2f}"
            result = f"Fix for {pattern}: FAILED -> {known['status']} (conf={known['confidence']})"

        self._rewrite_all_known()
        return {"message": result, "status": known["status"], "confidence": known["confidence"]}

    def report(self):
        """Summary of all known errors and their fix status."""
        lines = []
        lines.append(f"Known error patterns: {len(self.state['known'])}")
        lines.append(f"Errors captured this run: {len(self.state['errors'])}")
        lines.append("")
        for pattern, d in sorted(self.state["known"].items()):
            lines.append(f"  {d.get('status', '?'):8s} conf={d.get('confidence', '?'):5s} "
                         f"occ={d.get('occurrences', '?'):3s} {pattern}")
            lines.append(f"    fix: {d.get('fix', 'none')}")
        lines.append("")
        if self.state["errors"]:
            lines.append("This run's errors:")
            for e in self.state["errors"]:
                lines.append(f"  [{e['producer']}/{e['entity']}] {e['pattern']}: {e['description']}")
        return "\n".join(lines)

    def get_stats(self):
        promoted = sum(1 for d in self.state["known"].values() if d.get("status") == self.STATUS_PROMOTED)
        testing = sum(1 for d in self.state["known"].values() if d.get("status") == self.STATUS_TESTING)
        failed = sum(1 for d in self.state["known"].values() if d.get("status") == self.STATUS_FAILED)
        new = sum(1 for d in self.state["known"].values() if d.get("status") == self.STATUS_NEW)
        return {"total_known": len(self.state["known"]), "captured_this_run": len(self.state["errors"]),
                "promoted": promoted, "testing": testing, "failed": failed, "new": new}


class Law:
    """Rule/law checker. CRUD for system laws stored as BCL.
    Laws are statements that must be true about the system.

    BCL format:
      [@LAW]
      {
          ("id";"LAW001")
          ("name";"No unsupported language crashes")
          ("statement";"Scanner must handle all file types gracefully")
          ("enforcement";"error")
          ("authority";"scanner")
          ("status";"active")
      }

    Methods: create, read, update, delete, check_all, list_laws
    """

    ENFORCEMENT_INFO = "info"
    ENFORCEMENT_WARN = "warning"
    ENFORCEMENT_ERROR = "error"
    ENFORCEMENT_BLOCK = "block"

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.state = {"laws": {}}
        if param and "bcl_file_path" in param:
            self.state["bcl_file_path"] = param["bcl_file_path"]
        else:
            self.state["bcl_file_path"] = "error_knowledge.bcl"
        self.bcl = BCL(param={"file_path": self.state["bcl_file_path"]})
        self._load_laws()

    def Run(self, command, params=None):
        dispatch = {
            "create": lambda: self.create(params.get("law_id"), params.get("name"),
                                          params.get("statement"), params.get("enforcement", "error"),
                                          params.get("authority", "system")),
            "read": lambda: self.read(params.get("law_id")),
            "update": lambda: self.update(params.get("law_id"), **params.get("fields", {})),
            "delete": lambda: self.delete(params.get("law_id")),
            "check_all": lambda: self.check_all(params.get("fact_checker")),
            "list_laws": lambda: self.list_laws(),
            "get_stats": lambda: self.get_stats(),
        }
        if command in dispatch:
            result = dispatch[command]()
            return (1, result, None)
        return (0, None, (404, f"Unknown command: {command}", 0))

    def _load_laws(self):
        for ct, d in self.bcl.read_all():
            if ct == "LAW":
                lid = d.get("id", "")
                if lid:
                    self.state["laws"][lid] = d

    def create(self, law_id, name, statement, enforcement=ENFORCEMENT_ERROR, authority="system"):
        if law_id in self.state["laws"]:
            return {"message": f"Law {law_id} already exists"}
        data = {
            "id": law_id, "name": name, "statement": statement,
            "enforcement": enforcement, "authority": authority, "status": "active",
            "created": datetime.now().isoformat(),
        }
        self.bcl.write_container("LAW", data)
        self.state["laws"][law_id] = data
        return {"message": f"Law {law_id} created", "law": data}

    def read(self, law_id):
        return self.state["laws"].get(law_id)

    def update(self, law_id, **fields):
        if law_id not in self.state["laws"]:
            return {"message": f"Law {law_id} not found"}
        law = self.state["laws"][law_id]
        for k, v in fields.items():
            law[k] = v
        law["updated"] = datetime.now().isoformat()
        self._rewrite_all()
        return {"message": f"Law {law_id} updated", "law": law}

    def delete(self, law_id):
        if law_id not in self.state["laws"]:
            return {"message": f"Law {law_id} not found"}
        del self.state["laws"][law_id]
        self._rewrite_all()
        return {"message": f"Law {law_id} deleted"}

    def _rewrite_all(self):
        containers = []
        for lid, d in self.state["laws"].items():
            containers.append(("LAW", d))
        error_containers = []
        for ct, d in self.bcl.read_all():
            if ct == "ERROR":
                error_containers.append((ct, d))
        self.bcl.rewrite_all(error_containers + containers)

    def list_laws(self):
        lines = [f"Total laws: {len(self.state['laws'])}", ""]
        for lid, d in sorted(self.state["laws"].items()):
            lines.append(f"  [{d.get('enforcement', '?'):8s}] {lid}: {d.get('name', '?')}")
            lines.append(f"    {d.get('statement', '?')}")
            lines.append(f"    authority={d.get('authority', '?')} status={d.get('status', '?')}")
            lines.append("")
        return "\n".join(lines)

    def check_all(self, fact_checker=None):
        """Check all active laws. If fact_checker provided, call it per law.
        fact_checker(law_dict) -> (passed: bool, detail: str)"""
        results = []
        for lid, law in sorted(self.state["laws"].items()):
            if law.get("status") != "active":
                continue
            if fact_checker:
                passed, detail = fact_checker(law)
            else:
                passed, detail = True, "no checker provided"
            results.append({
                "law_id": lid, "name": law.get("name", ""),
                "passed": passed, "detail": detail,
                "enforcement": law.get("enforcement", "error"),
            })
        return results

    def get_stats(self):
        active = sum(1 for d in self.state["laws"].values() if d.get("status") == "active")
        inactive = sum(1 for d in self.state["laws"].values() if d.get("status") != "active")
        by_enforcement = {}
        for d in self.state["laws"].values():
            e = d.get("enforcement", "unknown")
            by_enforcement[e] = by_enforcement.get(e, 0) + 1
        return {"total": len(self.state["laws"]), "active": active, "inactive": inactive,
                "by_enforcement": by_enforcement}


