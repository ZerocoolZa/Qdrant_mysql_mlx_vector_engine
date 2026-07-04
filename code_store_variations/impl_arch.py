import os
import sys
import json
import re


class DomArch:
    """Architecture analysis and governance domain."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "approve": self.approve,
            "baseline": self.baseline,
            "cohesion": self.cohesion,
            "complexity": self.complexity,
            "coupling": self.coupling,
            "dependency": self.dependency,
            "design": self.design,
            "document": self.document,
            "enforce": self.enforce,
            "layer": self.layer,
            "pattern": self.pattern,
            "report": self.report,
            "review": self.review,
            "technical_debt": self.technical_debt,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _scan_files(self, root, exts=None):
        exts = exts or [".py", ".js", ".ts", ".java", ".go", ".rs", ".rb"]
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            if "__pycache__" in dirpath or ".git" in dirpath:
                continue
            for name in filenames:
                if any(name.endswith(ext) for ext in exts):
                    files.append(os.path.join(dirpath, name))
        return files

    def _read_source(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except Exception:
            return ""

    def approve(self, params=None):
        params = params or {}
        try:
            component = params.get("component", "")
            decision = params.get("decision", "approved")
            checks = params.get("checks", [])
            passed = all(c.get("passed", False) for c in checks) if checks else True
            status = "approved" if passed and decision == "approved" else "rejected"
            self.state["results"].append({"component": component, "status": status})
            result = {"domain": "arch", "method": "approve", "data": {"component": component, "status": status, "passed": passed}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("APPROVE_ERROR", str(e), 0))

    def baseline(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = self._scan_files(root)
            metrics = {"file_count": len(files), "total_lines": 0, "total_size": 0}
            for f in files:
                src = self._read_source(f)
                metrics["total_lines"] += src.count("\n") + 1
                metrics["total_size"] += len(src)
            self.state["config"]["baseline"] = metrics
            result = {"domain": "arch", "method": "baseline", "data": {"root": root, "metrics": metrics}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BASELINE_ERROR", str(e), 0))

    def cohesion(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            classes = re.findall(r"class\s+\w+", src)
            funcs = re.findall(r"def\s+\w+", src)
            cohesion_ratio = len(classes) / max(len(funcs), 1)
            result = {"domain": "arch", "method": "cohesion", "data": {"path": path, "classes": len(classes), "functions": len(funcs), "cohesion_ratio": round(cohesion_ratio, 4)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COHESION_ERROR", str(e), 0))

    def complexity(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            branches = len(re.findall(r"\bif\b|\belif\b|\bfor\b|\bwhile\b|\bexcept\b|\band\b|\bor\b", src))
            funcs = len(re.findall(r"def\s+\w+", src))
            avg = branches / max(funcs, 1)
            level = "low" if avg < 3 else "medium" if avg < 7 else "high"
            result = {"domain": "arch", "method": "complexity", "data": {"path": path, "branches": branches, "functions": funcs, "avg_complexity": round(avg, 2), "level": level}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPLEXITY_ERROR", str(e), 0))

    def coupling(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            imports = re.findall(r"^(?:import|from)\s+.+", src, re.MULTILINE)
            calls = re.findall(r"\w+\.\w+\(", src)
            coupling_score = len(imports) + len(calls)
            level = "low" if coupling_score < 10 else "medium" if coupling_score < 25 else "high"
            result = {"domain": "arch", "method": "coupling", "data": {"path": path, "imports": len(imports), "external_calls": len(calls), "coupling_score": coupling_score, "level": level}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUPLING_ERROR", str(e), 0))

    def dependency(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = self._scan_files(root)
            graph = {}
            for f in files:
                src = self._read_source(f)
                imports = re.findall(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", src, re.MULTILINE)
                deps = [m[0] or m[1] for m in imports]
                graph[f] = deps
            result = {"domain": "arch", "method": "dependency", "data": {"root": root, "graph": graph}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DEPENDENCY_ERROR", str(e), 0))

    def design(self, params=None):
        params = params or {}
        try:
            spec = params.get("spec", {})
            name = spec.get("name", "unnamed")
            layers = spec.get("layers", [])
            principles = spec.get("principles", [])
            design_doc = {
                "name": name,
                "layers": layers,
                "principles": principles,
                "valid": len(layers) > 0,
            }
            self.state["config"]["design"] = design_doc
            result = {"domain": "arch", "method": "design", "data": design_doc}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESIGN_ERROR", str(e), 0))

    def document(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = self._scan_files(root)
            doc = {"components": [], "summary": ""}
            for f in files:
                src = self._read_source(f)
                classes = re.findall(r"class\s+(\w+)", src)
                docstring = re.search(r'"""(.+?)"""', src, re.DOTALL)
                doc["components"].append({
                    "file": f,
                    "classes": classes,
                    "description": docstring.group(1).strip() if docstring else "",
                })
            doc["summary"] = f"{len(files)} files, {len(doc['components'])} components"
            result = {"domain": "arch", "method": "document", "data": doc}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DOCUMENT_ERROR", str(e), 0))

    def enforce(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            rules = params.get("rules", [])
            files = self._scan_files(root)
            violations = []
            for f in files:
                src = self._read_source(f)
                for rule in rules:
                    pattern = rule.get("pattern", "")
                    desc = rule.get("description", "")
                    if pattern and re.search(pattern, src):
                        violations.append({"file": f, "rule": desc or pattern, "pattern": pattern})
            result = {"domain": "arch", "method": "enforce", "data": {"root": root, "rules_checked": len(rules), "violations": violations, "passed": len(violations) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENFORCE_ERROR", str(e), 0))

    def layer(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            layer_map = params.get("layer_map", {})
            files = self._scan_files(root)
            layers = {}
            for f in files:
                assigned = None
                for layer_name, patterns in layer_map.items():
                    if any(p in f for p in patterns):
                        assigned = layer_name
                        break
                if not assigned:
                    assigned = "unclassified"
                layers.setdefault(assigned, []).append(f)
            result = {"domain": "arch", "method": "layer", "data": {"root": root, "layers": layers}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LAYER_ERROR", str(e), 0))

    def pattern(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            patterns_found = []
            pattern_defs = {
                "singleton": r"class\s+\w+.*?:.*?_instance",
                "factory": r"def\s+create\w*\(",
                "observer": r"def\s+(?:subscribe|notify|listen)\w*\(",
                "strategy": r"def\s+execute\w*\(",
                "adapter": r"class\s+\w*Adapter\b",
                "decorator": r"def\s+\w+\(self,\s*func\)",
            }
            for pname, pat in pattern_defs.items():
                if re.search(pat, src, re.DOTALL):
                    patterns_found.append(pname)
            result = {"domain": "arch", "method": "pattern", "data": {"path": path, "patterns": patterns_found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PATTERN_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = self._scan_files(root)
            total_lines = 0
            total_classes = 0
            total_funcs = 0
            for f in files:
                src = self._read_source(f)
                total_lines += src.count("\n") + 1
                total_classes += len(re.findall(r"class\s+\w+", src))
                total_funcs += len(re.findall(r"def\s+\w+", src))
            report = {
                "root": root,
                "files": len(files),
                "total_lines": total_lines,
                "total_classes": total_classes,
                "total_functions": total_funcs,
            }
            result = {"domain": "arch", "method": "report", "data": report}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def review(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            issues = []
            if len(re.findall(r"def\s+\w+", src)) > 50:
                issues.append("too many functions in single file")
            if src.count("\n") > 500:
                issues.append("file too long")
            if len(re.findall(r"^\s*print\(", src, re.MULTILINE)) > 0:
                issues.append("print statements found")
            if not re.search(r'""".+?"""', src, re.DOTALL):
                issues.append("missing module docstring")
            result = {"domain": "arch", "method": "review", "data": {"path": path, "issues": issues, "passed": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REVIEW_ERROR", str(e), 0))

    def technical_debt(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = self._scan_files(root)
            debt_items = []
            for f in files:
                src = self._read_source(f)
                todos = len(re.findall(r"#\s*TODO|#\s*FIXME|#\s*HACK", src))
                if todos > 0:
                    debt_items.append({"file": f, "todos": todos})
            total_debt = sum(d["todos"] for d in debt_items)
            result = {"domain": "arch", "method": "technical_debt", "data": {"root": root, "items": debt_items, "total_debt": total_debt}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TECHNICAL_DEBT_ERROR", str(e), 0))
