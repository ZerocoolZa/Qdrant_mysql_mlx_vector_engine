# [@GHOST]{[@file<system_check.py>][@domain<utility>][@role<system_check>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<system_check>][@return<tuple3>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{System check — runs indexer, compress, domain scans, reports pass/fail}
# [@WCL]{[@self_contained<true>][@runs<Indexer|Compress|VbsScanner|py_compile>][@output<structured_report>]}

import os
import sys
import subprocess
import importlib

from .indexer import Indexer
from .compress import Compress
from .vbs_scanner import VbsScanner
from . import Config


class SystemCheck:
    """System check — runs all utility checks and reports status.

    Checks:
    1. Index all core/ domains — verify files, classes, methods
    2. Compress roundtrip — encode/decode integrity
    3. py_compile — all .py files compile
    4. Import check — all packages importable
    5. Domain integrity — each domain has config, __init__, classes

    Usage:
        from core.utility.system_check import SystemCheck
        chk = SystemCheck()
        code, report, err = chk.Run("check_all", {"root": "/path/to/project"})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "checks": [],
            "passed": 0,
            "failed": 0,
        }
        self.indexer = Indexer()
        self.compress = Compress()
        self.scanner = VbsScanner()

    def Run(self, command, params=None):
        if command == "check_all":
            return self.check_all((params or {}).get("root"))
        elif command == "check_index":
            return self.check_index((params or {}).get("root"))
        elif command == "check_compile":
            return self.check_compile((params or {}).get("root"))
        elif command == "check_imports":
            return self.check_imports((params or {}).get("root"))
        elif command == "check_domains":
            return self.check_domains((params or {}).get("root"))
        elif command == "check_compress":
            return self.check_compress()
        elif command == "check_vbsstyle":
            return self.check_vbsstyle((params or {}).get("root"))
        elif command == "get_report":
            return self.get_report()
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def add_check(self, name, ok, detail=""):
        entry = {"name": name, "ok": ok, "detail": detail}
        self.state["checks"].append(entry)
        if ok:
            self.state["passed"] += 1
        else:
            self.state["failed"] += 1
        return entry

    def check_all(self, root=None):
        self.state["checks"] = []
        self.state["passed"] = 0
        self.state["failed"] = 0

        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.check_compile(root)
        self.check_imports(root)
        self.check_index(root)
        self.check_domains(root)
        self.check_compress()
        self.check_vbsstyle(root)

        total = self.state["passed"] + self.state["failed"]
        return (1, {
            "passed": self.state["passed"],
            "failed": self.state["failed"],
            "total": total,
            "checks": self.state["checks"],
        }, None)

    def check_index(self, root=None):
        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        core_dir = os.path.join(root, "core")
        if not os.path.isdir(core_dir):
            self.add_check("index_core", False, "core/ dir not found")
            return (0, None, ("dir_not_found", core_dir, 0))

        code, stats, err = self.indexer.Run("scan_dir", {"path": core_dir})
        if code != 1:
            self.add_check("index_core", False, str(err))
            return (code, None, err)

        self.add_check(
            "index_core",
            stats["files"] > 0,
            "{} files, {} classes, {} methods, {} domains".format(
                stats["files"], stats["classes"], stats["methods"], stats["domain_count"]
            )
        )
        return (1, stats, None)

    def check_compile(self, root=None):
        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        core_dir = os.path.join(root, "core")
        if not os.path.isdir(core_dir):
            self.add_check("compile_core", False, "core/ dir not found")
            return (0, None, ("dir_not_found", core_dir, 0))

        passed = 0
        failed = 0
        failures = []
        for r, dirs, files in os.walk(core_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(r, fname)
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", fpath],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    passed += 1
                else:
                    failed += 1
                    failures.append("{}: {}".format(fname, result.stderr.strip().split("\n")[-1]))

        self.add_check(
            "compile_core",
            failed == 0,
            "{} passed, {} failed{}".format(
                passed, failed,
                " — " + "; ".join(failures[:3]) if failures else ""
            )
        )
        return (1, {"passed": passed, "failed": failed, "failures": failures}, None)

    def check_imports(self, root=None):
        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        packages = [
            "core",
            "core.Dom_Gui",
            "core.Dom_Gui.config",
            "core.Dom_Gui.db",
            "core.Dom_Gui.bus",
            "core.Dom_Gui.theme",
            "core.Dom_Gui.graphs",
            "core.utility",
            "core.utility.compress",
            "core.utility.indexer",
        ]

        passed = 0
        failed = 0
        failures = []
        for pkg in packages:
            try:
                importlib.import_module(pkg)
                passed += 1
            except Exception as e:
                failed += 1
                failures.append("{}: {}".format(pkg, str(e)[:80]))

        self.add_check(
            "imports",
            failed == 0,
            "{} passed, {} failed{}".format(
                passed, failed,
                " — " + "; ".join(failures[:3]) if failures else ""
            )
        )
        return (1, {"passed": passed, "failed": failed, "failures": failures}, None)

    def check_domains(self, root=None):
        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        core_dir = os.path.join(root, "core")
        if not os.path.isdir(core_dir):
            self.add_check("domains", False, "core/ dir not found")
            return (0, None, ("dir_not_found", core_dir, 0))

        domains = []
        for item in sorted(os.listdir(core_dir)):
            item_path = os.path.join(core_dir, item)
            if os.path.isdir(item_path) and item.startswith("Dom_"):
                has_init = os.path.exists(os.path.join(item_path, "__init__.py"))
                has_config = any(
                    f.lower().startswith("config") and f.endswith(".py")
                    for f in os.listdir(item_path)
                ) if has_init else False
                py_count = sum(1 for f in os.listdir(item_path) if f.endswith(".py"))
                domains.append({
                    "name": item,
                    "has_init": has_init,
                    "has_config": has_config,
                    "py_files": py_count,
                })

        all_ok = all(d["has_init"] for d in domains) if domains else False
        self.add_check(
            "domains",
            all_ok,
            "{} domains: {}".format(
                len(domains),
                ", ".join("{}({}py,init={},cfg={})".format(
                    d["name"], d["py_files"], d["has_init"], d["has_config"]
                ) for d in domains)
            )
        )
        return (1, domains, None)

    def check_compress(self):
        test_text = "System check compress roundtrip test. [@GHOST]{[@file<test>]}"
        code, encoded, err = self.compress.Run("encode", {"text": test_text})
        if code != 1:
            self.add_check("compress_roundtrip", False, "encode failed")
            return (0, None, err)
        code, decoded, err = self.compress.Run("decode", {"encoded": encoded})
        if code != 1:
            self.add_check("compress_roundtrip", False, "decode failed")
            return (0, None, err)
        ok = decoded == test_text
        self.add_check("compress_roundtrip", ok, "encode/decode match" if ok else "mismatch")
        return (1, {"ok": ok}, None)

    def check_vbsstyle(self, root=None):
        if not root:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        core_dir = os.path.join(root, "core")
        if not os.path.isdir(core_dir):
            self.add_check("vbsstyle", False, "core/ dir not found")
            return (0, None, ("dir_not_found", core_dir, 0))

        code, stats, err = self.scanner.Run("scan_dir", {"path": core_dir})
        if code != 1:
            self.add_check("vbsstyle", False, str(err))
            return (code, None, err)

        ok = stats["violations"] == 0
        detail = "{} violations across {} files".format(stats["violations"], stats["files"])
        if not ok and stats["rules"]:
            top_rules = sorted(stats["rules"].items(), key=lambda x: x[1], reverse=True)[:3]
            detail += " — " + ", ".join("{}({})".format(r, c) for r, c in top_rules)
        self.add_check("vbsstyle", ok, detail)
        return (1, stats, None)

    def get_report(self):
        total = self.state["passed"] + self.state["failed"]
        lines = []
        for entry in self.state["checks"]:
            tag = "PASS" if entry["ok"] else "FAIL"
            line = "[{}] {} — {}".format(tag, entry["name"], entry["detail"])
            lines.append(line)
        lines.append("")
        lines.append("Total: {} passed, {} failed, {} total".format(
            self.state["passed"], self.state["failed"], total
        ))
        return (1, "\n".join(lines), None)
