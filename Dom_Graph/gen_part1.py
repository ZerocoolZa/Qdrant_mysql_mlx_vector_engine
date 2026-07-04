#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/gen_part1.py"
# date="2026-06-26" author="Devin" session_id="phase4-7-gen"
# context="Generator Part 1: Phase 4 remaining + Phase 6"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="gen_part1.py" domain="twin_gen" authority="Generator"}
# [@SUMMARY]{summary="Generates remaining VBStyle engine files Part 1."}
# [@CLASS]{class="Generator" domain="gen" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="generate_all" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Generator Part 1: generates Phase 4 remaining + Phase 6 engine files. Has VBStyle headers, Run dispatch, single class. BUT: hardcoded BASE_DIR = '/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph'. No _p helper, no read_state/set_config. No print/decorators/self._. No Tuple3 returns visible in header section.>][@todos<1. Remove hardcoded BASE_DIR, use os.path.dirname(os.path.abspath(__file__)). 2. Add _p/read_state/set_config methods. 3. Ensure all methods return Tuple3.>]}
"""
Generator Part 1 -- generates Phase 4 remaining + Phase 6 engine files.
"""
import os

BASE_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph"


def make_header(fname, session, section, title, domain, cls, summary,
                summary_short, commands, imports, methods_body):
    method_lines = "".join(
        '# [@METHOD]{method="%s" type="command"}\n' % c for c in commands
    ).rstrip("\n")
    cmds_str = ", ".join(commands)
    dispatch_body = ""
    for i, cmd in enumerate(commands):
        method_name = "".join(p.capitalize() for p in cmd.split("_"))
        kw = "if" if i == 0 else "elif"
        dispatch_body += '        %s command == "%s":\n' % (kw, cmd)
        dispatch_body += "            return self.%s(params)\n" % method_name
    tpl = '''#!/usr/bin/env python3
# [@GHOST]{{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/{fname}"
# date="2026-06-26" author="Devin" session_id="{session}"
# context="Project Digital Twin Section {section} {title}"}}
# [@VBSTYLE]{{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}}
# [@FILEID]{{id="{fname}" domain="twin_{domain}" authority="{cls}"}}
# [@SUMMARY]{{summary="{summary}"}}
# [@CLASS]{{class="{cls}" domain="{domain}" authority="single"}}
{method_lines}
# [@METHOD]{{method="_p" type="helper"}}
# [@METHOD]{{method="read_state" type="command"}}
# [@METHOD]{{method="set_config" type="command"}}
# [@METHOD]{{method="__init__" type="ctor"}}
"""
{cls} -- {summary_short}.
Implements Section {section} of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: {cmds_str}.
"""
{imports}

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50


class {cls}:
    """{summary_short}."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {{
            "config": {{
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
            }},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }}
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {{}}
{dispatch_body}
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {{}}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]
{methods_body}
'''
    return tpl.format(
        fname=fname, session=session, section=section, title=title,
        domain=domain, cls=cls, summary=summary, summary_short=summary_short,
        method_lines=method_lines, cmds_str=cmds_str, imports=imports,
        dispatch_body=dispatch_body, methods_body=methods_body,
    )


def write_file(fname, content):
    path = os.path.join(BASE_DIR, fname)
    with open(path, "w") as f:
        f.write(content)
    print("Wrote: " + fname)


# === static_analyzer.py (Section 10) ===
static_analyzer_m = '''
    def AnalyzeFile(self, params):
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file_id not found", 0))
            path = row[0]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found: " + str(path), 0))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            return (1, {"parsed": False, "error": str(exc)}, None)
        symbols = []
        imports = []
        constants = []
        globals_list = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        symbols.append(tgt.id)
                        if tgt.id.isupper():
                            constants.append(tgt.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.Global):
                globals_list.extend(node.names)
        complexity = sum(1 for node in ast.walk(tree)
                         if isinstance(node, (ast.If, ast.For, ast.While,
                                              ast.ExceptHandler, ast.With, ast.BoolOp)))
        return (1, {"parsed": True, "symbols": symbols, "imports": imports,
                    "constants": constants, "globals": globals_list,
                    "complexity": complexity}, None)

    def AnalyzeAll(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        results = []
        for row in cur.fetchall():
            res = self.AnalyzeFile({"file_id": row[0]})
            if res[0] == 1:
                results.append({"file_id": row[0], "path": row[1], "analysis": res[1]})
        return (1, {"files_analyzed": len(results), "results": results}, None)

    def GetComplexity(self, params):
        method_id = self._p(params, "method_id")
        method_name = self._p(params, "method_name")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        elif method_name:
            cur.execute("SELECT method_id, method_code FROM methods WHERE method_name=?", (method_name,))
        else:
            return (0, None, ("NO_PARAM", "method_id or method_name required", 0))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        code = row[-1]
        try:
            tree = ast.parse(code)
            complexity = sum(1 for node in ast.walk(tree)
                             if isinstance(node, (ast.If, ast.For, ast.While,
                                                  ast.ExceptHandler, ast.With, ast.BoolOp)))
        except SyntaxError:
            complexity = 0
        if method_id:
            cur.execute("UPDATE methods SET cyclomatic_complexity=? WHERE method_id=?",
                        (complexity, method_id))
            conn.commit()
        return (1, {"method_id": method_id or row[0], "complexity": complexity}, None)

    def FindDeadCode(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, class_id FROM methods")
        all_methods = cur.fetchall()
        cur.execute("SELECT DISTINCT dst_id FROM edges WHERE dst_type='method' AND edge_type='calls'")
        called = set(r[0] for r in cur.fetchall())
        dead = [{"method_id": m[0], "method_name": m[1], "class_id": m[2]}
                for m in all_methods if m[0] not in called]
        return (1, {"dead_code": dead, "count": len(dead)}, None)

    def FindDuplicates(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, hash, COUNT(*) FROM methods "
                    "WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*)>1")
        dupes = [{"method_name": r[0], "hash": r[1], "count": r[2]} for r in cur.fetchall()]
        return (1, {"duplicates": dupes, "count": len(dupes)}, None)
'''

write_file("static_analyzer.py", make_header(
    "static_analyzer.py", "phase4-analysis", "10", "Static Analysis",
    "static", "StaticAnalyzer",
    "Static analysis authority that AST-parses files, builds symbol tables, resolves imports, detects dead code and duplicates, and computes complexity.",
    "Static analysis authority for AST parsing and complexity analysis",
    ["analyze_file", "analyze_all", "get_complexity", "find_dead_code", "find_duplicates"],
    "import ast\nimport json\nimport os\nimport sqlite3",
    static_analyzer_m,
))

# === search_engine.py (Section 20) ===
search_engine_m = '''
    def SearchName(self, params):
        name = self._p(params, "name", "")
        entity_type = self._p(params, "entity_type", "method")
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        pattern = "%" + name + "%"
        if entity_type in ("method", "all"):
            cur.execute("SELECT method_id, method_name, class_id FROM methods WHERE method_name LIKE ?", (pattern,))
            results.extend({"entity_type": "method", "id": r[0], "name": r[1], "class_id": r[2]} for r in cur.fetchall())
        if entity_type in ("class", "all"):
            cur.execute("SELECT class_id, class_name FROM classes WHERE class_name LIKE ?", (pattern,))
            results.extend({"entity_type": "class", "id": r[0], "name": r[1]} for r in cur.fetchall())
        if entity_type in ("file", "all"):
            cur.execute("SELECT file_id, file_name FROM files WHERE file_name LIKE ?", (pattern,))
            results.extend({"entity_type": "file", "id": r[0], "name": r[1]} for r in cur.fetchall())
        return (1, {"results": results, "count": len(results)}, None)

    def SearchBcl(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        results = []
        cur.execute("SELECT file_id, file_name, bcl FROM files WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "file", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        cur.execute("SELECT class_id, class_name, bcl FROM classes WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "class", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        cur.execute("SELECT method_id, method_name, bcl FROM methods WHERE bcl LIKE ?", (pattern,))
        results.extend({"entity_type": "method", "id": r[0], "name": r[1], "bcl": r[2]} for r in cur.fetchall())
        return (1, {"results": results, "count": len(results)}, None)

    def SearchSignature(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, signature FROM methods WHERE signature LIKE ?", (pattern,))
        results = [{"method_id": r[0], "method_name": r[1], "signature": r[2]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchError(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, error_type, error_text FROM knowledge "
                    "WHERE error_type IS NOT NULL AND problem LIKE ?", (pattern,))
        results = [{"knowledge_id": r[0], "problem": r[1], "error_type": r[2], "error_text": r[3]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchFix(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, confidence FROM knowledge "
                    "WHERE answer IS NOT NULL AND answer LIKE ?", (pattern,))
        results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2], "confidence": r[3]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchDependency(self, params):
        edge_type = self._p(params, "edge_type", "depends_on")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE edge_type=? AND (src_id=? OR dst_id=?)", (edge_type, entity_id, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchCallChain(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE chain AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE edge_type='calls' AND dst_type='method' AND dst_id=? "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN chain c ON e.dst_type='method' AND e.dst_id=c.src_id "
                    "WHERE e.edge_type='calls') SELECT * FROM chain", (method_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"call_chain": results, "count": len(results)}, None)

    def SearchVariable(self, params):
        var_name = self._p(params, "name", "")
        if not var_name:
            return (0, None, ("NO_PARAM", "name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_code LIKE ?", ("%" + var_name + "%",))
        results = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchComment(self, params):
        query = self._p(params, "query", "")
        pattern = "%" + query + "%"
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_code LIKE ?", ("%" + pattern + "%",))
        results = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchBehavior(self, params):
        query = self._p(params, "query", "")
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("SELECT knowledge_id, problem, answer FROM knowledge_fts WHERE knowledge_fts MATCH ?", (query + "*",))
            results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2]} for r in cur.fetchall()]
        except Exception:
            pattern = "%" + query + "%"
            cur.execute("SELECT method_id, method_name FROM methods WHERE method_code LIKE ?", (pattern,))
            results = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        return (1, {"results": results, "count": len(results)}, None)

    def SearchAll(self, params):
        results = {}
        for step in ("search_name", "search_bcl", "search_signature", "search_error", "search_fix"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, results, None)
'''

write_file("search_engine.py", make_header(
    "search_engine.py", "phase4-analysis", "20", "Semantic Search",
    "search", "SearchEngine",
    "Search authority that queries files, classes, methods, knowledge by name, BCL, signature, error, fix, dependency, call chain, variable, comment, and behavior.",
    "Semantic search authority for the digital twin",
    ["search_name", "search_bcl", "search_signature", "search_error", "search_fix",
     "search_dependency", "search_call_chain", "search_variable", "search_comment",
     "search_behavior", "search_all"],
    "import json\nimport os\nimport sqlite3",
    search_engine_m,
))

# === trace_engine.py (Section 21) ===
trace_engine_m = '''
    def FindEntryPoints(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        entry_points = []
        cur.execute("SELECT file_id, path FROM files WHERE extension='.py'")
        for row in cur.fetchall():
            path = row[1]
            if not path or not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                tree = ast.parse(content, filename=path)
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    test = ast.dump(node.test)
                    if "__name__" in test and "__main__" in test:
                        entry_points.append({"file_id": row[0], "path": path, "type": "main_block"})
        cur.execute("SELECT method_id, method_name FROM methods WHERE method_name IN ('main','Run','run')")
        for row in cur.fetchall():
            entry_points.append({"method_id": row[0], "method_name": row[1], "type": "named_entry"})
        return (1, {"entry_points": entry_points, "count": len(entry_points)}, None)

    def TraceCalls(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        visited = set()
        queue = [method_id]
        order = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            order.append(current)
            cur.execute("SELECT dst_id FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls'", (current,))
            for row in cur.fetchall():
                if row[0] not in visited:
                    queue.append(row[0])
        return (1, {"call_order": order, "count": len(order)}, None)

    def TraceSql(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        sql_methods = []
        for row in cur.fetchall():
            code = row[2] or ""
            if any(kw in code for kw in ("execute", "executemany", "commit", "rollback")):
                sql_methods.append({"method_id": row[0], "method_name": row[1]})
        return (1, {"sql_methods": sql_methods, "count": len(sql_methods)}, None)

    def TraceIo(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        io_methods = []
        for row in cur.fetchall():
            code = row[2] or ""
            if any(kw in code for kw in ("open(", ".read(", ".write(", ".close(")):
                io_methods.append({"method_id": row[0], "method_name": row[1]})
        return (1, {"io_methods": io_methods, "count": len(io_methods)}, None)

    def TraceThreads(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        thread_methods = []
        for row in cur.fetchall():
            code = row[2] or ""
            if any(kw in code for kw in ("Thread", "Lock", "Queue", "asyncio")):
                thread_methods.append({"method_id": row[0], "method_name": row[1]})
        return (1, {"thread_methods": thread_methods, "count": len(thread_methods)}, None)

    def TraceExitPaths(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        results = []
        for row in cur.fetchall():
            code = row[2] or ""
            exits = code.count("return") + code.count("raise") + code.count("sys.exit")
            results.append({"method_id": row[0], "method_name": row[1], "exit_paths": exits})
        return (1, {"exit_paths": results, "count": len(results)}, None)
'''

write_file("trace_engine.py", make_header(
    "trace_engine.py", "phase4-analysis", "21", "Execution Tracing",
    "trace", "TraceEngine",
    "Trace authority that finds entry points, traces call order, SQL calls, file IO, thread activity, and exit paths through the codebase.",
    "Execution tracing authority",
    ["find_entry_points", "trace_calls", "trace_sql", "trace_io", "trace_threads", "trace_exit_paths"],
    "import ast\nimport os\nimport sqlite3",
    trace_engine_m,
))

# === impact_engine.py (Section 22) ===
impact_engine_m = '''
    def WhatUses(self, params):
        entity_type = self._p(params, "entity_type", "method")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM edges WHERE dst_type=? AND dst_id=?", (entity_type, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"users": results, "count": len(results)}, None)

    def WhatBreaks(self, params):
        entity_type = self._p(params, "entity_type", "method")
        entity_id = self._p(params, "entity_id")
        if not entity_id:
            return (0, None, ("NO_PARAM", "entity_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE breaks AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE dst_type=? AND dst_id=? "
                    "AND edge_type IN ('depends_on','calls','imports') "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN breaks b ON e.dst_type=b.src_type AND e.dst_id=b.src_id "
                    "WHERE e.edge_type IN ('depends_on','calls','imports')) "
                    "SELECT * FROM breaks", (entity_type, entity_id))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"breaks": results, "count": len(results)}, None)

    def ReverseCallGraph(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE reverse_calls AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN reverse_calls r ON e.dst_type='method' AND e.dst_id=r.src_id "
                    "WHERE e.edge_type='calls') SELECT * FROM reverse_calls", (method_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"reverse_call_graph": results, "count": len(results)}, None)

    def ForwardCallGraph(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE forward_calls AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN forward_calls f ON e.src_type='method' AND e.src_id=f.dst_id "
                    "WHERE e.edge_type='calls') SELECT * FROM forward_calls", (method_id,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"forward_call_graph": results, "count": len(results)}, None)

    def RippleRadius(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        res = self.ReverseCallGraph(params)
        if res[0] != 1:
            return res
        nodes = set()
        for edge in res[1]["reverse_call_graph"]:
            nodes.add(edge["src_id"])
            nodes.add(edge["dst_id"])
        return (1, {"ripple_radius": len(nodes), "nodes": list(nodes)}, None)

    def RiskScore(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        ripple = self.RippleRadius(params)
        if ripple[0] != 1:
            return ripple
        radius = ripple[1]["ripple_radius"]
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        complexity = row[0] if row else 0
        risk = (radius * complexity) / 10.0 if radius > 0 else 0
        return (1, {"risk_score": risk, "ripple_radius": radius, "complexity": complexity}, None)
'''

write_file("impact_engine.py", make_header(
    "impact_engine.py", "phase4-analysis", "22", "Impact Analysis",
    "impact", "ImpactEngine",
    "Impact analysis authority that computes what uses an entity, what breaks if it changes, reverse/forward call graphs, ripple radius, and risk scores.",
    "Impact analysis authority",
    ["what_uses", "what_breaks", "reverse_call_graph", "forward_call_graph", "ripple_radius", "risk_score"],
    "import os\nimport sqlite3",
    impact_engine_m,
))

print("Phase 4 remaining: 4 files done")
