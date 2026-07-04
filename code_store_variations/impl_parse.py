import re
import ast


class DomParse:
    """Source code parsing: lex, split classes/methods, brackets, docstrings."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        handler = getattr(self, command, None)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _code(self, params):
        code = params.get("code") or params.get("source") or ""
        if not code and params.get("path"):
            with open(params.get("path"), "r", encoding="utf-8") as fh:
                code = fh.read()
        return code

    def extract_docstring(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            tree = ast.parse(code)
            docstring = ast.get_docstring(tree) if tree.body else None
            result = {"domain": "parse", "method": "extract_docstring", "data": {"docstring": docstring, "found": docstring is not None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_DOCSTRING_ERROR", str(e), 0))

    def extract_metadata(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            tree = ast.parse(code)
            classes = []
            functions = []
            imports = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    classes.append({"name": node.name, "methods": methods, "method_count": len(methods)})
                elif isinstance(node, ast.FunctionDef):
                    functions.append({"name": node.name, "args": [a.arg for a in node.args.args]})
                elif isinstance(node, ast.Import):
                    imports.append({"module": node.names[0].name})
                elif isinstance(node, ast.ImportFrom):
                    imports.append({"module": node.module, "names": [n.name for n in node.names]})
            result = {"domain": "parse", "method": "extract_metadata", "data": {"classes": classes, "functions": functions, "imports": imports, "class_count": len(classes), "function_count": len(functions)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_METADATA_ERROR", str(e), 0))

    def lex(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            tokens = []
            token_re = re.compile(r"(\s+|#.*|\n|\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"[^\"]*\"|'[^']*'|\w+|[^\w\s]+)")
            pos = 0
            for m in token_re.finditer(code):
                text = m.group(0)
                if text.isspace():
                    ttype = "WS" if text != "\n" else "NEWLINE"
                elif text.startswith("#"):
                    ttype = "COMMENT"
                elif text.startswith(('"""', "'''")):
                    ttype = "DOCSTRING"
                elif text.startswith(('"', "'")):
                    ttype = "STRING"
                elif text.isidentifier():
                    ttype = "NAME"
                elif text.isdigit():
                    ttype = "NUMBER"
                else:
                    ttype = "OP"
                tokens.append({"type": ttype, "value": text, "pos": m.start()})
                pos = m.end()
            result = {"domain": "parse", "method": "lex", "data": {"tokens": tokens, "count": len(tokens)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LEX_ERROR", str(e), 0))

    def read_brackets(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            target = params.get("target") or params.get("name")
            if not target:
                return (0, None, ("READ_BRACKETS_ERROR", "missing target", 0))
            idx = code.find(target)
            if idx < 0:
                return (0, None, ("READ_BRACKETS_ERROR", "target not found", 0))
            start = code.find("(", idx)
            if start < 0:
                return (0, None, ("READ_BRACKETS_ERROR", "no opening bracket", 0))
            depth = 0
            i = start
            while i < len(code):
                c = code[i]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            content = code[start:i + 1]
            result = {"domain": "parse", "method": "read_brackets", "data": {"target": target, "content": content, "start": start, "end": i + 1}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_BRACKETS_ERROR", str(e), 0))

    def read_header(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            lines = code.splitlines()
            header = []
            for line in lines:
                if line.startswith("class ") or line.startswith("def ") or line.startswith("import ") or line.startswith("from "):
                    break
                header.append(line)
            result = {"domain": "parse", "method": "read_header", "data": {"header": "\n".join(header), "lines": len(header)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("READ_HEADER_ERROR", str(e), 0))

    def split_class(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            classes = []
            for m in re.finditer(r"^class\s+(\w+)", code, re.M):
                name = m.group(1)
                start = m.start()
                classes.append({"name": name, "start": start, "line": code[:start].count("\n") + 1})
            result = {"domain": "parse", "method": "split_class", "data": {"classes": classes, "count": len(classes)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_CLASS_ERROR", str(e), 0))

    def split_method(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            methods = []
            for m in re.finditer(r"^[ \t]*def\s+(\w+)\s*\(([^)]*)\)", code, re.M):
                name = m.group(1)
                args = [a.strip().split(":")[0].strip() for a in m.group(2).split(",") if a.strip()]
                methods.append({"name": name, "args": args, "start": m.start(), "line": code[:m.start()].count("\n") + 1})
            result = {"domain": "parse", "method": "split_method", "data": {"methods": methods, "count": len(methods)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_METHOD_ERROR", str(e), 0))

    def transform(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            ops = params.get("ops") or []
            out = code
            for op in ops:
                if op == "strip_comments":
                    out = "\n".join(l for l in out.splitlines() if not l.strip().startswith("#"))
                elif op == "strip_docstrings":
                    out = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', '', out)
                elif op == "normalize_ws":
                    out = re.sub(r"[ \t]+", " ", out)
                    out = re.sub(r"\n{3,}", "\n\n", out)
                elif op == "lowercase_keywords":
                    out = re.sub(r"\b(CLASS|DEF|IMPORT|FROM)\b", lambda m: m.group(0).lower(), out)
            result = {"domain": "parse", "method": "transform", "data": {"code": out, "changed": out != code, "ops": ops}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRANSFORM_ERROR", str(e), 0))

    def validate_brackets(self, params=None):
        params = params or {}
        try:
            code = self._code(params)
            pairs = {")": "(", "]": "[", "}": "{"}
            stack = []
            errors = []
            in_str = None
            i = 0
            while i < len(code):
                c = code[i]
                if in_str:
                    if c == in_str:
                        in_str = None
                    i += 1
                    continue
                if c in ('"', "'"):
                    triple = code[i:i + 3]
                    if triple in ('"""', "'''"):
                        in_str = triple[0]
                        i += 3
                        continue
                    in_str = c
                    i += 1
                    continue
                if c in "([{":
                    stack.append((c, i))
                elif c in ")]}":
                    if not stack or stack[-1][0] != pairs[c]:
                        errors.append({"pos": i, "char": c, "msg": "mismatched"})
                    else:
                        stack.pop()
                i += 1
            for s in stack:
                errors.append({"pos": s[1], "char": s[0], "msg": "unclosed"})
            result = {"domain": "parse", "method": "validate_brackets", "data": {"valid": len(errors) == 0, "errors": errors}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VALIDATE_BRACKETS_ERROR", str(e), 0))
