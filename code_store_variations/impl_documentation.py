import os
import sys
import json
import re


class DomDocumentation:
    """Documentation generation, rendering, and cross-referencing domain."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "api_doc": self.api_doc,
            "changelog": self.changelog,
            "cross_ref": self.cross_ref,
            "diagram": self.diagram,
            "example": self.example,
            "generate": self.generate,
            "import": self.import_,
            "readme": self.readme,
            "render": self.render,
            "template": self.template,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _read_source(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except Exception:
            return ""

    def api_doc(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            funcs = re.findall(r"def\s+(\w+)\s*\(([^)]*)\)", src)
            classes = re.findall(r"class\s+(\w+)\s*\(([^)]*)\)", src)
            api = {"functions": [{"name": n, "params": a} for n, a in funcs], "classes": [{"name": n, "bases": a} for n, a in classes]}
            result = {"domain": "documentation", "method": "api_doc", "data": {"path": path, "api": api}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("API_DOC_ERROR", str(e), 0))

    def changelog(self, params=None):
        params = params or {}
        try:
            entries = params.get("entries", [])
            version = params.get("version", "1.0.0")
            lines = [f"# Changelog", "", f"## {version}", ""]
            for entry in entries:
                etype = entry.get("type", "changed")
                desc = entry.get("description", "")
                lines.append(f"- [{etype}] {desc}")
            content = "\n".join(lines)
            result = {"domain": "documentation", "method": "changelog", "data": {"version": version, "content": content, "entries": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHANGELOG_ERROR", str(e), 0))

    def cross_ref(self, params=None):
        params = params or {}
        try:
            root = params.get("root", ".")
            files = []
            for dirpath, dirnames, filenames in os.walk(root):
                if "__pycache__" in dirpath:
                    continue
                for name in filenames:
                    if name.endswith(".py"):
                        files.append(os.path.join(dirpath, name))
            refs = {}
            for f in files:
                src = self._read_source(f)
                imports = re.findall(r"from\s+([\w.]+)\s+import\s+(\w+)", src)
                for mod, name in imports:
                    refs.setdefault(name, []).append({"file": f, "module": mod})
            result = {"domain": "documentation", "method": "cross_ref", "data": {"root": root, "references": refs, "total_symbols": len(refs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CROSS_REF_ERROR", str(e), 0))

    def diagram(self, params=None):
        params = params or {}
        try:
            components = params.get("components", [])
            connections = params.get("connections", [])
            lines = ["graph TD"]
            for comp in components:
                lines.append(f'  {comp["id"]}["{comp.get("label", comp["id"])}"]')
            for conn in connections:
                lines.append(f'  {conn["from"]} --> {conn["to"]}')
            content = "\n".join(lines)
            result = {"domain": "documentation", "method": "diagram", "data": {"content": content, "components": len(components), "connections": len(connections)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIAGRAM_ERROR", str(e), 0))

    def example(self, params=None):
        params = params or {}
        try:
            subject = params.get("subject", "")
            code = params.get("code", "")
            language = params.get("language", "python")
            example_text = f"```{language}\n{code}\n```"
            result = {"domain": "documentation", "method": "example", "data": {"subject": subject, "example": example_text}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXAMPLE_ERROR", str(e), 0))

    def generate(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            doc_type = params.get("type", "module")
            src = self._read_source(path)
            docstring = re.search(r'"""(.+?)"""', src, re.DOTALL)
            funcs = re.findall(r"def\s+(\w+)\s*\(([^)]*)\)", src)
            sections = [f"# Documentation: {path}", ""]
            if docstring:
                sections.append(f"## Description\n\n{docstring.group(1).strip()}\n")
            sections.append("## Functions\n")
            for name, args in funcs:
                sections.append(f"- `{name}({args})`")
            content = "\n".join(sections)
            result = {"domain": "documentation", "method": "generate", "data": {"path": path, "type": doc_type, "content": content, "functions": len(funcs)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GENERATE_ERROR", str(e), 0))

    def import_(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            imports = re.findall(r"^(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+(.+))$", src, re.MULTILINE)
            parsed = []
            for m in imports:
                if m[0]:
                    parsed.append({"type": "from", "module": m[0], "names": [n.strip() for n in m[1].split(",")]})
                else:
                    parsed.append({"type": "import", "module": m[2]})
            result = {"domain": "documentation", "method": "import", "data": {"path": path, "imports": parsed, "count": len(parsed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("IMPORT_ERROR", str(e), 0))

    def readme(self, params=None):
        params = params or {}
        try:
            project = params.get("project", "Project")
            description = params.get("description", "")
            sections = params.get("sections", {})
            lines = [f"# {project}", "", description, ""]
            for title, content in sections.items():
                lines.append(f"## {title}")
                lines.append("")
                lines.append(str(content))
                lines.append("")
            content = "\n".join(lines)
            result = {"domain": "documentation", "method": "readme", "data": {"project": project, "content": content}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("README_ERROR", str(e), 0))

    def render(self, params=None):
        params = params or {}
        try:
            template = params.get("template", "")
            variables = params.get("variables", {})
            rendered = template
            for key, val in variables.items():
                rendered = rendered.replace("{" + key + "}", str(val))
            result = {"domain": "documentation", "method": "render", "data": {"rendered": rendered, "variables": len(variables)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RENDER_ERROR", str(e), 0))

    def template(self, params=None):
        params = params or {}
        try:
            name = params.get("name", "default")
            content = params.get("content", "")
            self.state["config"].setdefault("templates", {})[name] = content
            result = {"domain": "documentation", "method": "template", "data": {"name": name, "saved": True, "length": len(content)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEMPLATE_ERROR", str(e), 0))
