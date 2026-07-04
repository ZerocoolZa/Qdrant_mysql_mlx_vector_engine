# [@GHOST]{[@file<content_extract.py>][@domain<utility>][@role<extractor>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<content_extractor>][@return<tuple3>][@orch<Indexer>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Content extractor — regex-based extraction of classes, methods, imports, BCL tags, violations from source}
# [@WCL]{[@self_contained<true>][@extracts<classes|methods|imports|ghost|vbs|print|hardcoded|decorators|headers|sql|file_io>][@source<MySQL_vb_code_test>]}

import re


class ContentExtract:
    """Content extractor — regex-based source code analysis.

    Extracts from Python source text:
    - Classes, methods, functions, imports
    - BCL header tokens ([@GHOST], [@VBSTYLE], etc.)
    - VBStyle violations (print, decorators, hardcoded paths, self._)
    - SQL calls, file I/O calls, source mutations
    - Tuple3 mentions, MemUnit mentions, config mentions

    Usage:
        from core.utility.content_extract import ContentExtract
        ce = ContentExtract()
        code, result, err = ce.Run("extract", {"content": source_text})
    """

    CLASS_RE = re.compile(r'class\s+(\w+)\s*[(:]')
    METHOD_RE = re.compile(r'def\s+(\w+)\s*\(')
    IMPORT_RE = re.compile(r'(?:import|from)\s+([\w.]+)')
    HEADER_TOKEN_RE = re.compile(r'#\[[@\w]+\]')
    GHOST_RE = re.compile(r'#\[@GHOST\]')
    VBSTYLE_RE = re.compile(r'#\[@VBSTYLE\]')
    PRINT_RE = re.compile(r'print\s*\(')
    DECORATOR_RE = re.compile(r'@(property|staticmethod|classmethod)')
    SELF_UNDER_RE = re.compile(r'\bself\._\w+')
    PATH_LITERAL_RE = re.compile(r'["\'][/\w]+/\w+["\']')
    SQL_EXEC_RE = re.compile(r'\.execute\s*\(')
    SQL_TABLE_RE = re.compile(r'(?:FROM|INTO|UPDATE|TABLE)\s+(\w+)', re.IGNORECASE)
    FILE_IO_RE = re.compile(r'(?:open|read|write|close)\s*\(')
    RAISE_RE = re.compile(r'raise\s+\w+')
    TRY_EXCEPT_RE = re.compile(r'(?:try:|except\s)')
    TUPLE3_RE = re.compile(r'\(\s*[01]\s*,.*,\s*None\s*\)')
    CONFIG_RE = re.compile(r'[Cc]onfig[\w.]*')
    MAIN_EXEC_RE = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_result": {},
        }

    def Run(self, command, params=None):
        if command == "extract":
            return self.extract((params or {}).get("content", ""))
        elif command == "extract_file":
            return self.extract_file((params or {}).get("path"))
        elif command == "get_result":
            return (1, self.state["last_result"], None)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def extract(self, content):
        if not content:
            return (0, None, ("empty_input", "no content", 0))

        result = {
            "classes": list(self.CLASS_RE.findall(content)),
            "methods": list(self.METHOD_RE.findall(content)),
            "imports": list(self.IMPORT_RE.findall(content)),
            "header_tokens": list(self.HEADER_TOKEN_RE.findall(content)),
            "has_ghost": bool(self.GHOST_RE.search(content)),
            "has_vbs": bool(self.VBSTYLE_RE.search(content)),
            "print_count": len(self.PRINT_RE.findall(content)),
            "decorators": list(self.DECORATOR_RE.findall(content)),
            "self_underscore": list(self.SELF_UNDER_RE.findall(content)),
            "path_literals": list(self.PATH_LITERAL_RE.findall(content)),
            "sql_execute_calls": len(self.SQL_EXEC_RE.findall(content)),
            "sql_tables": list(set(self.SQL_TABLE_RE.findall(content))),
            "file_io_calls": len(self.FILE_IO_RE.findall(content)),
            "raise_count": len(self.RAISE_RE.findall(content)),
            "try_except_count": len(self.TRY_EXCEPT_RE.findall(content)),
            "tuple3_mentions": len(self.TUPLE3_RE.findall(content)),
            "config_mentions": len(self.CONFIG_RE.findall(content)),
            "has_main_exec": bool(self.MAIN_EXEC_RE.search(content)),
            "line_count": content.count("\n") + 1,
        }

        violations = []
        if result["print_count"] > 0:
            violations.append({"rule": "print_call", "count": result["print_count"]})
        if result["decorators"]:
            violations.append({"rule": "decorator", "count": len(result["decorators"])})
        if result["self_underscore"]:
            violations.append({"rule": "self_underscore", "count": len(result["self_underscore"])})
        if not result["has_ghost"]:
            violations.append({"rule": "missing_ghost", "count": 1})
        if not result["has_vbs"]:
            violations.append({"rule": "missing_vbs", "count": 1})
        result["violations"] = violations
        result["violation_count"] = len(violations)

        self.state["last_result"] = result
        return (1, result, None)

    def extract_file(self, path):
        if not path:
            return (0, None, ("missing_param", "path", 0))
        try:
            with open(path, "r") as f:
                content = f.read()
            code, result, err = self.extract(content)
            if code == 1:
                result["file_path"] = path
                result["file_name"] = path.rsplit("/", 1)[-1] if "/" in path else path
            return (code, result, err)
        except Exception as e:
            return (0, None, ("read_failed", str(e), 0))
