import os
import sys
import json
import re


class DomCsplit:
    """Code splitting, extraction, merging, and analysis domain."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "count_classes": self.count_classes,
            "count_methods": self.count_methods,
            "extract_class": self.extract_class,
            "extract_header": self.extract_header,
            "extract_method": self.extract_method,
            "merge": self.merge,
            "report": self.report,
            "split": self.split,
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

    def count_classes(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            classes = re.findall(r"^class\s+\w+", src, re.MULTILINE)
            result = {"domain": "csplit", "method": "count_classes", "data": {"path": path, "count": len(classes)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUNT_CLASSES_ERROR", str(e), 0))

    def count_methods(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            methods = re.findall(r"^\s*def\s+\w+", src, re.MULTILINE)
            result = {"domain": "csplit", "method": "count_methods", "data": {"path": path, "count": len(methods)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUNT_METHODS_ERROR", str(e), 0))

    def extract_class(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            class_name = params.get("class_name", "")
            src = self._read_source(path)
            lines = src.split("\n")
            extracted = []
            capturing = False
            base_indent = 0
            for line in lines:
                if re.match(rf"^class\s+{re.escape(class_name)}\b", line):
                    capturing = True
                    base_indent = len(line) - len(line.lstrip())
                    extracted.append(line)
                    continue
                if capturing:
                    if line.strip() == "":
                        extracted.append(line)
                        continue
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent > base_indent or line.strip() == "":
                        extracted.append(line)
                    else:
                        break
            content = "\n".join(extracted).rstrip()
            result = {"domain": "csplit", "method": "extract_class", "data": {"path": path, "class_name": class_name, "content": content, "found": len(extracted) > 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_CLASS_ERROR", str(e), 0))

    def extract_header(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            lines = src.split("\n")
            header = []
            for line in lines:
                if line.strip().startswith("#") or line.strip().startswith('"""') or line.strip() == "" or line.startswith("import ") or line.startswith("from "):
                    header.append(line)
                else:
                    break
            content = "\n".join(header)
            result = {"domain": "csplit", "method": "extract_header", "data": {"path": path, "content": content, "lines": len(header)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_HEADER_ERROR", str(e), 0))

    def extract_method(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            method_name = params.get("method_name", "")
            src = self._read_source(path)
            lines = src.split("\n")
            extracted = []
            capturing = False
            base_indent = 0
            for line in lines:
                if re.match(rf"^(\s*)def\s+{re.escape(method_name)}\b", line):
                    capturing = True
                    base_indent = len(line) - len(line.lstrip())
                    extracted.append(line)
                    continue
                if capturing:
                    if line.strip() == "":
                        extracted.append(line)
                        continue
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent > base_indent:
                        extracted.append(line)
                    else:
                        break
            content = "\n".join(extracted).rstrip()
            result = {"domain": "csplit", "method": "extract_method", "data": {"path": path, "method_name": method_name, "content": content, "found": len(extracted) > 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_METHOD_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            paths = params.get("paths", [])
            separator = params.get("separator", "\n\n")
            contents = []
            for p in paths:
                contents.append(self._read_source(p))
            merged = separator.join(contents)
            result = {"domain": "csplit", "method": "merge", "data": {"paths": paths, "merged_length": len(merged), "content": merged}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            lines = src.split("\n")
            classes = re.findall(r"^class\s+(\w+)", src, re.MULTILINE)
            methods = re.findall(r"^\s*def\s+(\w+)", src, re.MULTILINE)
            imports = re.findall(r"^(?:import|from)\s+.+", src, re.MULTILINE)
            report = {
                "path": path,
                "total_lines": len(lines),
                "classes": classes,
                "class_count": len(classes),
                "methods": methods,
                "method_count": len(methods),
                "import_count": len(imports),
            }
            result = {"domain": "csplit", "method": "report", "data": report}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            path = params.get("path", "")
            src = self._read_source(path)
            lines = src.split("\n")
            chunks = []
            current = []
            base_indent = 0
            in_block = False
            for line in lines:
                if re.match(r"^(class\s+\w+|def\s+\w+)", line):
                    if current:
                        chunks.append("\n".join(current))
                    current = [line]
                    in_block = True
                    base_indent = len(line) - len(line.lstrip())
                elif in_block:
                    if line.strip() == "":
                        current.append(line)
                    else:
                        indent = len(line) - len(line.lstrip())
                        if indent > base_indent:
                            current.append(line)
                        else:
                            if current:
                                chunks.append("\n".join(current))
                            current = [line]
                            in_block = False
                else:
                    current.append(line)
            if current:
                chunks.append("\n".join(current))
            result = {"domain": "csplit", "method": "split", "data": {"path": path, "chunks": chunks, "count": len(chunks)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))
