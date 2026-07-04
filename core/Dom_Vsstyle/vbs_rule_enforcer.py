#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_rule_enforcer.py>][@domain<Vbs_Code_Verifiation>][@role<rule_enforcer>][@auth<cascade>][@date<2026-06-26>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<rule_enforcer>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
RuleEnforcer: scans .py files for VBStyle violations and auto-fixes them.
Checks: print(), decorators, self._ tabs, trailing whitespace, missing headers,
Tuple3 returns, Run() dispatch, PascalCase classes, UPPERCASE constants.
Can scan a single file or a folder. Can auto-fix safe violations.
"""

import re
import os
import sys
import subprocess
import py_compile
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from . import Config_Vbs_Code_Verifiation as Config
except ImportError:
    import Config_Vbs_Code_Verifiation as Config


class RuleEnforcer:
    """Enforcement authority: scan, check, auto-fix VBStyle violations in .py files."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "violations": [],
            "fixed": [],
            "scanned": 0,
            "passed": 0,
            "failed": 0,
            "operators": [],
            "attempts": [],
            "survivors": [],
            "stats": {
                "operators_loaded": 0,
                "attempts_made": 0,
                "survivors_promoted": 0,
                "fixes_applied": 0,
            },
        }

    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "scan_file": self.scan_file,
            "scan_folder": self.scan_folder,
            "auto_fix": self.auto_fix,
            "check_vbstyle": self.check_vbstyle,
            "load_operators": self.load_operators,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))

    def check_vbstyle(self, params):
        try:
            path = params.get("path", "")
            if not path or not os.path.isfile(path):
                return (0, None, ("NO_FILE", path, 0))
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            violations = []
            has_ghost = False
            has_vbstyle = False
            has_class = False
            has_run = False
            class_names = []
            for i, line in enumerate(lines, 1):
                stripped = line.rstrip("\n")
                if "[@GHOST]" in stripped:
                    has_ghost = True
                if "[@VBSTYLE]" in stripped:
                    has_vbstyle = True
                if re.match(r"^class\s+([A-Z][A-Za-z0-9_]*)", stripped):
                    has_class = True
                    m = re.match(r"^class\s+([A-Za-z0-9_]*)", stripped)
                    if m:
                        class_names.append(m.group(1))
                if re.match(r"^\s+def\s+Run\s*\(", stripped):
                    has_run = True
                if re.match(r"^\s*print\s*\(", stripped):
                    violations.append({"line": i, "rule": "NoPrint", "text": "print() found", "severity": "ERROR"})
                dec_match = re.match(r"^\s*(@property|@staticmethod|@classmethod)\b", stripped)
                if dec_match:
                    violations.append({"line": i, "rule": "NoDecorators", "text": "%s found" % dec_match.group(1), "severity": "ERROR"})
                if re.search(r"self\._[a-z]", stripped):
                    violations.append({"line": i, "rule": "NoUnderscore", "text": "self._ found", "severity": "ERROR"})
                if "\t" in line:
                    violations.append({"line": i, "rule": "NoTabs", "text": "tab character found", "severity": "ERROR"})
                if stripped != line.rstrip("\n").rstrip():
                    if line.rstrip("\n") != stripped.rstrip():
                        violations.append({"line": i, "rule": "NoTrailingWS", "text": "trailing whitespace", "severity": "WARN"})
            if not has_ghost:
                violations.append({"line": 0, "rule": "GhostHeader", "text": "missing [@GHOST] header", "severity": "ERROR"})
            if not has_vbstyle:
                violations.append({"line": 0, "rule": "VBStyleHeader", "text": "missing [@VBSTYLE] header", "severity": "ERROR"})
            if not has_class:
                violations.append({"line": 0, "rule": "PascalClass", "text": "no class definition found", "severity": "WARN"})
            if not has_run:
                violations.append({"line": 0, "rule": "RunDispatch", "text": "no Run() method found", "severity": "WARN"})
            for cn in class_names:
                if not cn[0].isupper():
                    violations.append({"line": 0, "rule": "PascalCase", "text": "class %s not PascalCase" % cn, "severity": "ERROR"})
            passed = len([v for v in violations if v["severity"] == "ERROR"]) == 0
            return (1, {"path": path, "violations": violations, "count": len(violations),
                        "errors": len([v for v in violations if v["severity"] == "ERROR"]),
                        "warnings": len([v for v in violations if v["severity"] == "WARN"]),
                        "passed": passed}, None)
        except Exception as e:
            return (0, None, ("CHECK_ERROR", str(e), 0))

    def scan_file(self, params):
        try:
            path = params.get("path", "")
            r = self.check_vbstyle({"path": path})
            if not r[0]:
                return r
            self.state["scanned"] += 1
            if r[1]["passed"]:
                self.state["passed"] += 1
            else:
                self.state["failed"] += 1
            self.state["violations"].extend(r[1]["violations"])
            return r
        except Exception as e:
            return (0, None, ("SCAN_FILE_ERROR", str(e), 0))

    def scan_folder(self, params):
        try:
            folder = params.get("folder", "")
            if not folder or not os.path.isdir(folder):
                return (0, None, ("NO_FOLDER", folder, 0))
            results = []
            for root, dirs, files in os.walk(folder):
                for fname in files:
                    if fname.endswith(".py"):
                        fpath = os.path.join(root, fname)
                        r = self.scan_file({"path": fpath})
                        if r[0]:
                            results.append({"path": fpath, "passed": r[1]["passed"],
                                            "errors": r[1]["errors"], "warnings": r[1]["warnings"]})
            return (1, {"scanned": self.state["scanned"], "passed": self.state["passed"],
                        "failed": self.state["failed"], "files": results}, None)
        except Exception as e:
            return (0, None, ("SCAN_FOLDER_ERROR", str(e), 0))

    def load_operators(self, params):
        try:
            result = subprocess.run(
                ["mysql", "-u", "root", "vb_shared", "-N", "-B", "-e",
                 "SELECT id, pattern, fix_action, confidence, success_count FROM learned_rules WHERE pattern LIKE 'fix:%' ORDER BY confidence DESC, success_count DESC LIMIT 50"],
                capture_output=True, text=True, timeout=10,
            )
            operators = []
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) < 5:
                        continue
                    op_id = parts[0]
                    pattern = parts[1]
                    fix_action = parts[2]
                    confidence = float(parts[3]) if parts[3] else 0.0
                    success_count = int(parts[4]) if parts[4] else 0
                    if "fix:" in pattern:
                        after = pattern.split("fix:")[1].strip()
                        name = after.split("(")[0].strip().replace(" ", "_")
                    else:
                        name = pattern.replace(" ", "_")[:50]
                    if name:
                        operators.append({
                            "id": op_id, "name": name, "pattern": pattern,
                            "fix_action": fix_action, "confidence": confidence,
                            "success_count": success_count,
                        })
            self.state["operators"] = operators
            self.state["stats"]["operators_loaded"] = len(operators)
            return (1, {"operators": len(operators)}, None)
        except Exception as e:
            return (0, None, ("ERR_LOAD_OPS", str(e), 0))

    def auto_fix(self, params):
        try:
            path = params.get("path", "")
            commit = params.get("commit", False)
            if not path or not os.path.isfile(path):
                return (0, None, ("NO_FILE", path, 0))
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            original = content
            fixes = []
            lines = content.split("\n")

            # 1. [@print] — print() -> pass
            if re.search(r"^\s*print\s*\(", content, re.MULTILINE):
                content = re.sub(r"^(\s*)print\s*\((.+)\)\s*$", r"\1pass  # TODO: replace with Report", content, flags=re.MULTILINE)
                fixes.append("print() -> pass (NoPrint)")

            # 2. [@decorators] — remove @property/@staticmethod/@classmethod
            for dec in ["@property", "@staticmethod", "@classmethod"]:
                dec_pat = re.compile(r"^\s*" + re.escape(dec) + r"\s*\n", re.MULTILINE)
                if dec_pat.search(content):
                    content = dec_pat.sub("", content)
                    fixes.append("removed %s (NoDecorators)" % dec)

            # 3. [@noself]/[@underscore] — self._x -> self.state["x"]
            if re.search(r"self\._[a-z]", content):
                content = re.sub(r"self\._([a-z][a-zA-Z0-9_]*)", lambda m: "self.state[\"" + m.group(1) + "\"]", content)
                fixes.append("self._ -> self.state (NoUnderscore)")

            # 4. [@tabs] — tabs -> 4 spaces
            if "\t" in content:
                content = content.replace("\t", "    ")
                fixes.append("tabs -> 4 spaces (NoTabs)")

            # 5. [@whitespace] — trailing whitespace
            lines = content.split("\n")
            fixed_lines = [line.rstrip() for line in lines]
            if fixed_lines != lines:
                content = "\n".join(fixed_lines)
                if not content.endswith("\n"):
                    content += "\n"
                fixes.append("trailing whitespace removed (NoTrailingWS)")

            # 6. [@ghost] — missing [@GHOST] header
            if not re.search(r'\[@GHOST\]', content, re.IGNORECASE):
                fname = os.path.basename(path)
                stamp = '# [@GHOST]{[@file<%s>][@domain<unknown>][@auth<auto_fix>][@date<auto>]}\n' % fname
                content = stamp + content
                fixes.append("added [@GHOST] header (GhostHeader)")

            # 7. [@vbsty] — missing [@VBSTYLE] header
            if not re.search(r'\[@VBSTYLE\]', content, re.IGNORECASE):
                stamp = '# [@VBSTYLE]{[@auth<auto_fix>][@return<Tuple3>][@orch<none>]}\n'
                content = self._insert_after_header(content, stamp)
                fixes.append("added [@VBSTYLE] header (VBStyleHeader)")

            # 8. [@cstyle] — missing [@SUMMARY] header
            if not re.search(r'\[@SUMMARY\]', content, re.IGNORECASE):
                fname = os.path.basename(path)
                stamp = '# [@SUMMARY]{%s — auto-generated summary}\n' % fname
                content = self._insert_after_header(content, stamp)
                fixes.append("added [@SUMMARY] header (SummaryHeader)")

            # 9. [@clshdr] — missing [@CLASS] header
            cls_match = re.search(r'^class\s+([A-Za-z0-9_]+)', content, re.MULTILINE)
            if cls_match and not re.search(r'\[@CLASS\]', content, re.IGNORECASE):
                cls_name = cls_match.group(1)
                stamp = '# [@CLASS]{%s}\n' % cls_name
                content = self._insert_after_header(content, stamp)
                fixes.append("added [@CLASS] header (ClassHeader)")

            # 10. [@mthdr] — missing [@METHOD] header
            if not re.search(r'\[@METHOD\]', content, re.IGNORECASE):
                methods = re.findall(r'def\s+([A-Za-z0-9_]+)\s*\(', content)
                if methods:
                    method_list = ",".join(set(methods))
                    stamp = '# [@METHOD]{%s}\n' % method_list
                    content = self._insert_after_header(content, stamp)
                    fixes.append("added [@METHOD] header (MethodHeader)")

            # 11. [@t3]/[@tuples] — bare "return None" -> "return (0, None, None)"
            if re.search(r'^\s*return\s+None\s*$', content, re.MULTILINE):
                content = re.sub(r'^(\s*)return\s+None\s*$', r'\1return (0, None, None)', content, flags=re.MULTILINE)
                fixes.append("bare return None -> Tuple3 (Tuple3Return)")

            # 12. [@pascal] — class not PascalCase (lowercase first letter)
            lower_cls = re.search(r'^class\s+([a-z][A-Za-z0-9_]*)', content, re.MULTILINE)
            if lower_cls:
                old_name = lower_cls.group(1)
                new_name = old_name[0].upper() + old_name[1:]
                content = content.replace("class " + old_name, "class " + new_name)
                content = content.replace(old_name + "(", new_name + "(")
                content = content.replace(" " + old_name + " ", " " + new_name + " ")
                fixes.append("class %s -> %s (PascalCase)" % (old_name, new_name))

            # 13. [@upper] — constants not UPPERCASE (NAME = value at module level)
            const_matches = re.findall(r'^([a-z][a-zA-Z0-9_]*)\s*=\s*["\']', content, re.MULTILINE)
            for const_name in const_matches:
                if const_name not in ("self", "params", "path", "content", "fixes", "lines", "fixed_lines", "fname", "stamp", "cls_name", "cls_match", "old_name", "new_name", "method_list", "methods", "dec", "dec_pat", "const_name"):
                    upper_name = const_name.upper()
                    content = re.sub(r'^' + re.escape(const_name) + r'\s*=', upper_name + " =", content, flags=re.MULTILINE)
                    fixes.append("%s -> %s (UppercaseConstant)" % (const_name, upper_name))

            # 14. [@enums] — enum usage: replace EnumClass.MEMBER with "MEMBER" string
            enum_matches = re.findall(r'\b([A-Z][a-zA-Z]+)\.([A-Z_]+)\b', content)
            for enum_cls, enum_member in enum_matches:
                if enum_cls not in ("True", "False", "None"):
                    old = enum_cls + "." + enum_member
                    new = '"' + enum_member + '"'
                    if old in content:
                        content = content.replace(old, new)
                        fixes.append("%s.%s -> %s (NoEnums)" % (enum_cls, enum_member, new))

            # 15. [@ctor] — bad ctor signature: (self) -> (self, mem=None, db=None, param=None)
            if re.search(r'def\s+__init__\s*\(\s*self\s*\)', content):
                content = re.sub(
                    r'def\s+__init__\s*\(\s*self\s*\)',
                    'def __init__(self, mem=None, db=None, param=None)',
                    content
                )
                fixes.append("ctor (self) -> (self, mem=None, db=None, param=None) (CtorFix)")

            # 16. [@rdst] — missing read_state stub
            if "def read_state" not in content and re.search(r'^class\s+', content, re.MULTILINE):
                stub = '\n    def read_state(self, params=None):\n        return (1, dict(self.state), None)\n'
                insert_pos = content.rfind("    def Run(")
                if insert_pos > 0:
                    content = content[:insert_pos] + stub + "\n" + content[insert_pos:]
                else:
                    content += stub
                fixes.append("added read_state stub (ReadStateStub)")

            # 17. [@cfg] — missing set_config stub
            if "def set_config" not in content and re.search(r'^class\s+', content, re.MULTILINE):
                stub = '\n    def set_config(self, params):\n        if not params or not isinstance(params, dict):\n            return (0, None, ("ERR_PARAMS", "config dict required", 0))\n        for key, val in params.items():\n            if key in self.state["config"]:\n                self.state["config"][key] = val\n        return (1, dict(self.state["config"]), None)\n'
                insert_pos = content.rfind("    def Run(")
                if insert_pos > 0:
                    content = content[:insert_pos] + stub + "\n" + content[insert_pos:]
                else:
                    content += stub
                fixes.append("added set_config stub (SetConfigStub)")

            if content == original:
                return (1, {"path": path, "fixes": [], "message": "no fixes needed"}, None)

            # Compile check before commit — no broken files written
            compile_ok = self._compile_check(content)
            if not compile_ok[0]:
                return (0, None, ("ERR_COMPILE_FAIL", "Candidate failed compile: " + str(compile_ok[1]), 0))

            score = self._score_candidate(original, content)
            self.state["attempts"].append({
                "score": score["score"],
                "fixed_gates": score["fixed_gates"],
                "broken_gates": score["broken_gates"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self.state["stats"]["attempts_made"] += 1

            if not commit:
                return (1, {"dry_run": True, "path": path, "fixes": fixes, "would_write": True, "score": score}, None)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self.state["fixed"].append({"path": path, "fixes": fixes})
            self.state["stats"]["fixes_applied"] += len(fixes)
            self.state["survivors"].append({
                "file_path": path, "fixes": fixes, "fix_count": len(fixes),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self.state["stats"]["survivors_promoted"] += 1
            return (1, {"path": path, "fixes": fixes, "committed": True, "score": score}, None)
        except Exception as e:
            return (0, None, ("AUTOFIX_ERROR", str(e), 0))

    def _compile_check(self, content):
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
            tmp.write(content)
            tmp.close()
            py_compile.compile(tmp.name, doraise=True)
            os.unlink(tmp.name)
            return (1, True, None)
        except py_compile.PyCompileError as e:
            return (0, str(e))
        except Exception as e:
            return (0, str(e))

    def _score_candidate(self, before, after):
        score = 0
        fixed_gates = []
        broken_gates = []

        checks = [
            (r"^\s*print\s*\(", "[@print]"),
            (r"^\s*@(property|staticmethod|classmethod)", "[@decorators]"),
            (r"self\._[a-z]", "[@noself]"),
            (r"^\s*return\s+None\s*$", "[@t3]"),
            (r'def\s+__init__\s*\(\s*self\s*\)', "[@ctor]"),
        ]
        for pattern, gate in checks:
            before_count = len(re.findall(pattern, before, re.MULTILINE))
            after_count = len(re.findall(pattern, after, re.MULTILINE))
            if after_count < before_count:
                score += 10 * (before_count - after_count)
                fixed_gates.append(gate)

        for header, gate in [(r'\[@GHOST\]', "[@ghost]"), (r'\[@VBSTYLE\]', "[@vbsty]"), (r'\[@SUMMARY\]', "[@cstyle]"), (r'\[@CLASS\]', "[@clshdr]"), (r'\[@METHOD\]', "[@mthdr]")]:
            if not re.search(header, before, re.IGNORECASE) and re.search(header, after, re.IGNORECASE):
                score += 10
                fixed_gates.append(gate)

        if "\t" in before and "\t" not in after:
            score += 10
            fixed_gates.append("[@tabs]")

        compile_result = self._compile_check(after)
        if compile_result[0]:
            score += 5
        else:
            score -= 20
            broken_gates.append("[@compile]")

        return {"score": score, "fixed_gates": fixed_gates, "broken_gates": broken_gates, "compile_pass": compile_result[0]}

    def _insert_after_header(self, content, new_line):
        header_end = 0
        for i, line in enumerate(content.split("\n")):
            if line.startswith("#") or line.strip() == "":
                header_end = i + 1
            else:
                break
        lines = content.split("\n")
        lines.insert(header_end, new_line.rstrip())
        return "\n".join(lines)

    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items()}, None)

    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))
