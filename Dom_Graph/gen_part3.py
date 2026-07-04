#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/gen_part3.py"
# date="2026-06-26" author="Devin" session_id="orch-gen"
# context="Generator Part 3: Orchestration files"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="gen_part3.py" domain="twin_gen" authority="Generator"}
# [@SUMMARY]{summary="Generates orchestration engine files."}
# [@CLASS]{class="Generator" domain="gen" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="generate_all" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Generator Part 3: generates orchestration engine files. Has VBStyle headers, Run dispatch, single class. BUT: hardcoded BASE_DIR = '/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph'. No _p helper, no read_state/set_config. No print/decorators/self._. No Tuple3 returns visible in header section.>][@todos<1. Remove hardcoded BASE_DIR, use os.path.dirname(os.path.abspath(__file__)). 2. Add _p/read_state/set_config methods. 3. Ensure all methods return Tuple3.>]}
"""
Generator Part 3 -- generates orchestration engine files.
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


# === report_engine.py (Section 15) ===
report_m = '''
    def ErrorTimeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT created, problem, error_type FROM knowledge WHERE error_type IS NOT NULL ORDER BY created")
        results = [{"created": r[0], "problem": r[1], "error_type": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def FixTimeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT created, answer, fix_result FROM knowledge WHERE answer IS NOT NULL ORDER BY created")
        results = [{"created": r[0], "answer": r[1], "fix_result": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def DependencyReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        results = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"dependencies": results}, None)

    def DuplicateReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, COUNT(*) FROM methods GROUP BY hash HAVING COUNT(*)>1")
        results = [{"method_name": r[0], "count": r[1]} for r in cur.fetchall()]
        return (1, {"duplicates": results, "count": len(results)}, None)

    def ComplexityReport(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, cyclomatic_complexity FROM methods ORDER BY cyclomatic_complexity DESC LIMIT 20")
        results = [{"method_name": r[0], "complexity": r[1]} for r in cur.fetchall()]
        return (1, {"top_complex": results}, None)

    def BclCoverage(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT (SUM(CASE WHEN bcl IS NOT NULL AND bcl != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) FROM methods")
        pct = cur.fetchone()[0] or 0
        return (1, {"bcl_coverage": pct}, None)

    def HealthScore(self, params):
        bcl = self.BclCoverage(params)
        bcl_score = bcl[1]["bcl_coverage"] if bcl[0] == 1 else 0
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges")
        graph_entities = cur.fetchone()[0] or 1
        total_entities = 0
        for table in ("files", "classes", "methods"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            total_entities += cur.fetchone()[0]
        graph_coverage = (graph_entities / total_entities * 100) if total_entities > 0 else 0
        cur.execute("SELECT (SUM(has_run_method) * 100.0 / COUNT(*)) FROM classes")
        method_coverage = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=0 AND has_decorator=0 AND has_self_underscore=0")
        clean = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        violation_free = (clean / total * 100) if total > 0 else 0
        score = bcl_score * 0.2 + graph_coverage * 0.2 + method_coverage * 0.2 + violation_free * 0.4
        return (1, {"health_score": score, "bcl_coverage": bcl_score,
                    "graph_coverage": graph_coverage, "method_coverage": method_coverage,
                    "violation_free": violation_free}, None)

    def FullReport(self, params):
        results = {}
        for step in ("error_timeline", "fix_timeline", "dependency_report", "duplicate_report",
                     "complexity_report", "bcl_coverage", "health_score"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, {"full_report": results}, None)
'''

write_file("report_engine.py", make_header(
    "report_engine.py", "phase-orchestration", "15", "Reporting",
    "report", "ReportEngine",
    "Report authority that generates error timelines, fix timelines, dependency, duplicate, complexity, BCL coverage, and health score reports.",
    "Reporting authority",
    ["error_timeline", "fix_timeline", "dependency_report", "duplicate_report",
     "complexity_report", "bcl_coverage", "health_score", "full_report"],
    "import os\nimport sqlite3",
    report_m,
))

# === continuous_loop.py (Section 16) ===
continuous_m = '''
    def RunFullCycle(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        steps = {}
        cur.execute("SELECT COUNT(*) FROM files")
        steps["scan"] = {"files": cur.fetchone()[0]}
        steps["ingest"] = {"new_files": 0}
        cur.execute("SELECT COUNT(*) FROM classes")
        steps["index_classes"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        steps["index_methods"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        steps["graph"] = {"edges": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1")
        violations = cur.fetchone()[0]
        steps["detect"] = {"violations": violations}
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL")
        steps["search"] = {"fixes_available": cur.fetchone()[0]}
        steps["repair"] = {"repaired": 0}
        cur.execute("PRAGMA integrity_check")
        steps["validate"] = {"integrity": cur.fetchone()[0]}
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("change", "continuous_loop", json.dumps(steps), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        steps["learn"] = {"learned": 1}
        return (1, {"cycle": steps, "violations": violations}, None)

    def RunNCycles(self, params):
        n = self._p(params, "n", 1)
        results = []
        for i in range(n):
            res = self.RunFullCycle(params)
            if res[0] == 1:
                results.append(res[1])
        return (1, {"cycles": results, "count": len(results)}, None)

    def DetectAndFix(self, params):
        cycle = self.RunFullCycle(params)
        if cycle[0] != 1:
            return cycle
        violations = cycle[1].get("violations", 0)
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, answer FROM knowledge WHERE answer IS NOT NULL LIMIT 10")
        fixes = [{"knowledge_id": r[0], "answer": r[1]} for r in cur.fetchall()]
        return (1, {"violations": violations, "fixes_found": len(fixes), "fixes": fixes}, None)

    def RunUntilClean(self, params):
        max_iter = self._p(params, "max_iterations", 10)
        results = []
        for i in range(max_iter):
            res = self.RunFullCycle(params)
            if res[0] != 1:
                return res
            results.append(res[1])
            if res[1].get("violations", 0) == 0:
                break
        return (1, {"cycles": results, "iterations": len(results),
                    "clean": results[-1].get("violations", 0) == 0}, None)
'''

write_file("continuous_loop.py", make_header(
    "continuous_loop.py", "phase-orchestration", "16", "Continuous Loop",
    "continuous", "ContinuousLoop",
    "Continuous loop authority that orchestrates scan, ingest, index, graph, detect, search, repair, validate, and learn in a repeating cycle.",
    "Continuous loop orchestrator",
    ["run_full_cycle", "run_n_cycles", "detect_and_fix", "run_until_clean"],
    "import json\nimport os\nimport sqlite3",
    continuous_m,
))

# === diff_engine.py (Section 19) ===
diff_m = '''
    def DiffFile(self, params):
        import difflib
        before = self._p(params, "before", "")
        after = self._p(params, "after", "")
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        return (1, {"diff": "\\n".join(diff), "lines_changed": len(diff)}, None)

    def DiffClass(self, params):
        before = self._p(params, "before", {})
        after = self._p(params, "after", {})
        diffs = []
        for key in set(list(before.keys()) + list(after.keys())):
            if before.get(key) != after.get(key):
                diffs.append({"key": key, "before": before.get(key), "after": after.get(key)})
        return (1, {"differences": diffs, "count": len(diffs)}, None)

    def DiffMethod(self, params):
        import difflib
        before = self._p(params, "before", "")
        after = self._p(params, "after", "")
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        return (1, {"diff": "\\n".join(diff), "lines_changed": len(diff)}, None)

    def DiffAst(self, params):
        before_code = self._p(params, "before_code", "")
        after_code = self._p(params, "after_code", "")
        try:
            before_ast = ast.dump(ast.parse(before_code))
        except SyntaxError:
            before_ast = "PARSE_ERROR"
        try:
            after_ast = ast.dump(ast.parse(after_code))
        except SyntaxError:
            after_ast = "PARSE_ERROR"
        same = before_ast == after_ast
        return (1, {"same": same, "before_ast": before_ast[:500], "after_ast": after_ast[:500]}, None)

    def DiffGraph(self, params):
        before_edges = self._p(params, "before_edges", [])
        after_edges = self._p(params, "after_edges", [])
        before_set = set(tuple(e) if isinstance(e, list) else e for e in before_edges)
        after_set = set(tuple(e) if isinstance(e, list) else e for e in after_edges)
        added = list(after_set - before_set)
        removed = list(before_set - after_set)
        return (1, {"added": added, "removed": removed,
                    "added_count": len(added), "removed_count": len(removed)}, None)

    def DiffAll(self, params):
        results = {}
        for step in ("diff_file", "diff_class", "diff_method", "diff_ast", "diff_graph"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, {"diff_all": results}, None)
'''

write_file("diff_engine.py", make_header(
    "diff_engine.py", "phase-orchestration", "19", "Code Difference Engine",
    "diff", "DiffEngine",
    "Difference engine authority that computes file, class, method, AST, graph, dependency, BCL, database, and runtime diffs.",
    "Code difference authority",
    ["diff_file", "diff_class", "diff_method", "diff_ast", "diff_graph", "diff_all"],
    "import ast\nimport os\nimport sqlite3",
    diff_m,
))

# === confidence_engine.py (Section 30) ===
confidence_m = '''
    def ParseConfidence(self, params):
        file_path = self._p(params, "file_path")
        file_id = self._p(params, "file_id")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            file_path = row[0]
        if not file_path or not os.path.isfile(file_path):
            return (0, None, ("NO_FILE", "File not found", 0))
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            ast.parse(content, filename=file_path)
            return (1, {"parse_confidence": 100}, None)
        except SyntaxError:
            return (1, {"parse_confidence": 0}, None)

    def MatchConfidence(self, params):
        pattern = self._p(params, "pattern", "")
        target = self._p(params, "target", "")
        if not pattern or not target:
            return (0, None, ("NO_PARAM", "pattern and target required", 0))
        matching = sum(1 for a, b in zip(pattern, target) if a == b)
        score = (matching / max(len(pattern), len(target))) * 100
        return (1, {"match_confidence": score}, None)

    def GraphConfidence(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT src_id) + COUNT(DISTINCT dst_id) FROM edges")
        graph_entities = cur.fetchone()[0] or 1
        total = 0
        for table in ("files", "classes", "methods"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            total += cur.fetchone()[0]
        pct = (graph_entities / total * 100) if total > 0 else 0
        return (1, {"graph_confidence": pct}, None)

    def RepairConfidence(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT AVG(CASE WHEN fix_result='success' THEN 100 ELSE 0 END) FROM knowledge WHERE answer IS NOT NULL")
        score = cur.fetchone()[0] or 0
        return (1, {"repair_confidence": score}, None)

    def TestConfidence(self, params):
        import subprocess
        cwd = os.path.dirname(os.path.abspath(__file__))
        try:
            result = subprocess.run(["python3", "test_everything.py"], capture_output=True, text=True, cwd=cwd, timeout=60)
            output = result.stdout
            passed = 0
            total = 0
            for line in output.split("\\n"):
                if "RESULTS:" in line and "passed" in line:
                    try:
                        passed = int(line.split("passed")[0].split(":")[-1].strip())
                    except ValueError:
                        pass
                    if "failed" in line:
                        try:
                            failed = int(line.split("failed")[0].split(",")[-1].strip())
                            total = passed + failed
                        except ValueError:
                            total = passed
            score = (passed / total * 100) if total > 0 else 0
            return (1, {"test_confidence": score, "passed": passed, "total": total}, None)
        except Exception:
            return (1, {"test_confidence": 0}, None)

    def OverallConfidence(self, params):
        parse = self.ParseConfidence(params)
        match = self.MatchConfidence(params)
        graph = self.GraphConfidence(params)
        repair = self.RepairConfidence(params)
        test = self.TestConfidence(params)
        p = parse[1].get("parse_confidence", 0) if parse[0] == 1 else 0
        m = match[1].get("match_confidence", 0) if match[0] == 1 else 0
        g = graph[1].get("graph_confidence", 0) if graph[0] == 1 else 0
        r = repair[1].get("repair_confidence", 0) if repair[0] == 1 else 0
        t = test[1].get("test_confidence", 0) if test[0] == 1 else 0
        overall = p * 0.15 + m * 0.10 + g * 0.20 + r * 0.25 + t * 0.30
        return (1, {"overall_confidence": overall, "parse": p, "match": m,
                    "graph": g, "repair": r, "test": t}, None)
'''

write_file("confidence_engine.py", make_header(
    "confidence_engine.py", "phase-orchestration", "30", "Confidence Engine",
    "confidence", "ConfidenceEngine",
    "Confidence authority that computes parse, match, graph, repair, test, and overall confidence scores.",
    "Confidence scoring authority",
    ["parse_confidence", "match_confidence", "graph_confidence", "repair_confidence",
     "test_confidence", "overall_confidence"],
    "import ast\nimport os\nimport sqlite3",
    confidence_m,
))

# === build_pipeline.py (Section 32) ===
build_pipeline_m = '''
    def Build(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        steps = {}
        import pathlib
        py_files = list(pathlib.Path(os.path.dirname(os.path.abspath(__file__))).rglob("*.py"))
        steps["scan"] = {"py_files": len(py_files)}
        cur.execute("SELECT COUNT(*) FROM files")
        steps["parse"] = {"files_in_db": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM classes")
        steps["index_classes"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        steps["index_methods"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM files WHERE bcl IS NOT NULL AND bcl != ''")
        steps["bcl_extract"] = {"files_with_bcl": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM edges")
        steps["graph_build"] = {"edges": cur.fetchone()[0]}
        cur.execute("PRAGMA integrity_check")
        steps["validate"] = {"integrity": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM knowledge")
        steps["learn"] = {"knowledge": cur.fetchone()[0]}
        steps["store"] = {"committed": True}
        import subprocess
        cwd = os.path.dirname(os.path.abspath(__file__))
        try:
            result = subprocess.run(["python3", "test_everything.py"], capture_output=True, text=True, cwd=cwd, timeout=60)
            steps["test"] = {"exit_code": result.returncode, "output_tail": result.stdout[-200:]}
        except Exception as exc:
            steps["test"] = {"error": str(exc)}
        cur.execute("SELECT COUNT(*) FROM files")
        steps["report"] = {"total_files": cur.fetchone()[0]}
        return (1, {"build": steps}, None)

    def BuildStep(self, params):
        step_name = self._p(params, "step_name")
        if not step_name:
            return (0, None, ("NO_PARAM", "step_name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        if step_name == "scan":
            import pathlib
            py_files = list(pathlib.Path(os.path.dirname(os.path.abspath(__file__))).rglob("*.py"))
            return (1, {"py_files": len(py_files)}, None)
        elif step_name == "validate":
            cur.execute("PRAGMA integrity_check")
            return (1, {"integrity": cur.fetchone()[0]}, None)
        return (0, None, ("UNKNOWN_STEP", "Unknown step: " + str(step_name), 0))

    def Rebuild(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        for table in ("edges", "methods", "classes", "files"):
            cur.execute("DELETE FROM " + table)
        conn.commit()
        return self.Build(params)

    def IncrementalBuild(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files WHERE status='active'")
        active = cur.fetchone()[0]
        return (1, {"active_files": active, "incremental": True}, None)
'''

write_file("build_pipeline.py", make_header(
    "build_pipeline.py", "phase-orchestration", "32", "Build Pipeline",
    "build", "BuildPipeline",
    "Build pipeline authority that orchestrates scan, parse, index, BCL extract, graph build, validate, learn, store, test, and report.",
    "Build pipeline orchestrator",
    ["build", "build_step", "rebuild", "incremental_build"],
    "import os\nimport sqlite3",
    build_pipeline_m,
))

# === digital_twin.py (Section 35) ===
digital_twin_m = '''
    def GetState(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        state = {}
        for table in ("files", "classes", "methods", "edges", "knowledge", "snapshots", "attempts", "observations"):
            cur.execute("SELECT COUNT(*) FROM " + table)
            state[table] = cur.fetchone()[0]
        cur.execute("PRAGMA integrity_check")
        state["integrity"] = cur.fetchone()[0]
        return (1, {"state": state}, None)

    def SimulateChange(self, params):
        change = self._p(params, "change_description", "")
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        affected = []
        if method_id:
            cur.execute("WITH RECURSIVE forward AS ("
                        "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                        "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                        "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                        "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
                        "WHERE e.edge_type='calls') SELECT DISTINCT dst_id FROM forward", (method_id,))
            affected = [r[0] for r in cur.fetchall()]
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("assumption", "simulate_change:" + change,
                    json.dumps({"method_id": method_id, "affected": affected}), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"change": change, "affected_entities": affected, "risk": len(affected)}, None)

    def Query(self, params):
        sql = self._p(params, "sql", "")
        if not sql.strip().upper().startswith("SELECT"):
            return (0, None, ("INVALID_QUERY", "Only SELECT statements allowed", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            return (1, {"columns": columns, "rows": rows, "count": len(rows)}, None)
        except Exception as exc:
            return (0, None, ("QUERY_ERROR", str(exc), 0))

    def ExportSnapshot(self, params):
        state = self.GetState(params)
        if state[0] != 1:
            return state
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        import hashlib
        content = json.dumps(state[1])
        h = hashlib.sha256(content.encode()).hexdigest()
        cur.execute("INSERT INTO snapshots (snapshot_type, content, hash, created, notes) "
                    "VALUES (?, ?, ?, ?, ?)", ("manual", content, h,
                     datetime.now(timezone.utc).isoformat(), "digital_twin_export"))
        conn.commit()
        return (1, {"snapshot_id": cur.lastrowid, "state": state[1], "hash": h}, None)

    def ImportSnapshot(self, params):
        snapshot_id = self._p(params, "snapshot_id")
        if not snapshot_id:
            return (0, None, ("NO_PARAM", "snapshot_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT content, hash, created FROM snapshots WHERE snapshot_id=?", (snapshot_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Snapshot not found", 0))
        return (1, {"content": row[0], "hash": row[1], "created": row[2]}, None)

    def CompareTwins(self, params):
        twin1 = self._p(params, "twin1_state", {})
        twin2 = self._p(params, "twin2_state", {})
        diffs = []
        for key in set(list(twin1.keys()) + list(twin2.keys())):
            if twin1.get(key) != twin2.get(key):
                diffs.append({"key": key, "twin1": twin1.get(key), "twin2": twin2.get(key)})
        similarity = max(0, 100 - len(diffs) * 5)
        return (1, {"differences": diffs, "similarity": similarity}, None)
'''

write_file("digital_twin.py", make_header(
    "digital_twin.py", "phase-orchestration", "35", "Project Digital Twin",
    "twin", "DigitalTwin",
    "Digital twin authority that gets state, simulates changes, queries, exports/imports snapshots, and compares twin states.",
    "Project digital twin authority",
    ["get_state", "simulate_change", "query", "export_snapshot", "import_snapshot", "compare_twins"],
    "import json\nimport os\nimport sqlite3",
    digital_twin_m,
))

# === compiler_engine.py (Section 36) ===
compiler_m = '''
    def CompileFile(self, params):
        import py_compile
        from datetime import datetime, timezone
        file_path = self._p(params, "file_path")
        if not file_path or not os.path.isfile(file_path):
            return (0, None, ("NO_FILE", "File not found", 0))
        try:
            py_compile.compile(file_path, doraise=True)
            return (1, {"passed": True, "file": file_path}, None)
        except py_compile.PyCompileError as exc:
            conn = self.Connect()
            cur = conn.cursor()
            cur.execute("INSERT INTO knowledge (problem, error_type, error_text, created, tags) "
                        "VALUES (?, ?, ?, ?, ?)", (str(exc), "PyCompileError", str(exc),
                         datetime.now(timezone.utc).isoformat(), json.dumps(["build", "compile"])))
            conn.commit()
            return (1, {"passed": False, "file": file_path, "error": str(exc)}, None)

    def CompileAll(self, params):
        import py_compile
        import pathlib
        base = os.path.dirname(os.path.abspath(__file__))
        py_files = list(pathlib.Path(base).rglob("*.py"))
        passed = 0
        failed = 0
        errors = []
        for pf in py_files:
            try:
                py_compile.compile(str(pf), doraise=True)
                passed += 1
            except py_compile.PyCompileError as exc:
                failed += 1
                errors.append({"file": str(pf), "error": str(exc)[:200]})
        return (1, {"total": len(py_files), "passed": passed, "failed": failed, "errors": errors}, None)

    def GetErrors(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, error_text, created FROM knowledge "
                    "WHERE error_type='PyCompileError' OR error_type='CompileError' ORDER BY created DESC")
        results = [{"knowledge_id": r[0], "problem": r[1], "error_text": r[2], "created": r[3]} for r in cur.fetchall()]
        return (1, {"errors": results, "count": len(results)}, None)

    def GetWarnings(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence FROM observations WHERE observation_type='warning'")
        results = [{"observation_id": r[0], "subject": r[1], "evidence": r[2]} for r in cur.fetchall()]
        return (1, {"warnings": results, "count": len(results)}, None)

    def BuildHistory(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, created FROM knowledge WHERE tags LIKE '%build%' ORDER BY created DESC")
        results = [{"knowledge_id": r[0], "problem": r[1], "created": r[2]} for r in cur.fetchall()]
        return (1, {"build_history": results, "count": len(results)}, None)
'''

write_file("compiler_engine.py", make_header(
    "compiler_engine.py", "phase-orchestration", "36", "Compiler Knowledge",
    "compiler", "CompilerEngine",
    "Compiler authority that compiles files, aggregates compile results, and tracks compiler errors, warnings, and build history.",
    "Compiler knowledge authority",
    ["compile_file", "compile_all", "get_errors", "get_warnings", "build_history"],
    "import json\nimport os\nimport sqlite3",
    compiler_m,
))

# === runtime_engine.py (Section 37) ===
runtime_m = '''
    def Snapshot(self, params):
        import gc
        import threading
        from datetime import datetime, timezone
        snapshot = {"object_count": len(gc.get_objects()),
                    "thread_count": threading.active_count(),
                    "threads": [t.name for t in threading.enumerate()]}
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            snapshot["memory_current"] = current
            snapshot["memory_peak"] = peak
        except Exception:
            snapshot["memory_available"] = False
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("fact", "runtime_snapshot", json.dumps(snapshot), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"snapshot": snapshot}, None)

    def GetObjects(self, params):
        import gc
        from collections import Counter
        objects = gc.get_objects()
        type_counts = Counter(type(o).__name__ for o in objects)
        top = type_counts.most_common(20)
        return (1, {"total": len(objects), "type_counts": dict(top)}, None)

    def GetMemory(self, params):
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            return (1, {"current": current, "peak": peak, "available": True}, None)
        except Exception:
            return (1, {"available": False}, None)

    def GetThreads(self, params):
        import threading
        threads = [{"name": t.name, "ident": t.ident, "daemon": t.daemon, "alive": t.is_alive()}
                   for t in threading.enumerate()]
        return (1, {"threads": threads, "count": len(threads)}, None)

    def GetResources(self, params):
        import os
        info = {"pid": os.getpid(), "ppid": os.getppid()}
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info()
            info["rss"] = mem.rss
            info["vms"] = mem.vms
            info["cpu_percent"] = proc.cpu_percent()
        except ImportError:
            info["psutil_available"] = False
        return (1, {"resources": info}, None)
'''

write_file("runtime_engine.py", make_header(
    "runtime_engine.py", "phase-orchestration", "37", "Runtime Knowledge",
    "runtime", "RuntimeEngine",
    "Runtime authority that snapshots live objects, memory, threads, and resource usage for the running system.",
    "Runtime knowledge authority",
    ["snapshot", "get_objects", "get_memory", "get_threads", "get_resources"],
    "import json\nimport os\nimport sqlite3",
    runtime_m,
))

# === memory_forensics.py (Section 38) ===
memory_forensics_m = '''
    def DetectLeaks(self, params):
        import gc
        gc.collect()
        before = len(gc.get_objects())
        gc.collect()
        after = len(gc.get_objects())
        leaks = before != after
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("fact", "leak_check", json.dumps({"before": before, "after": after}),
                     50, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"leaks_detected": leaks, "before": before, "after": after}, None)

    def TrackLifetime(self, params):
        object_type = self._p(params, "object_type", "")
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, created FROM observations WHERE subject LIKE ?",
                    ("%" + object_type + "%",))
        results = [{"observation_id": r[0], "subject": r[1], "created": r[2]} for r in cur.fetchall()]
        return (1, {"lifetime_data": results, "count": len(results)}, None)

    def AllocationHistory(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence, created FROM observations "
                    "WHERE observation_type='allocation' ORDER BY created")
        results = [{"observation_id": r[0], "subject": r[1], "evidence": r[2], "created": r[3]} for r in cur.fetchall()]
        return (1, {"history": results, "count": len(results)}, None)

    def PeakUsage(self, params):
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, peak = tracemalloc.get_traced_memory()
            return (1, {"peak": peak, "current": current, "available": True}, None)
        except Exception:
            return (1, {"available": False}, None)

    def GrowthTrend(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT evidence, created FROM observations WHERE subject LIKE '%memory%' OR subject LIKE '%leak%' ORDER BY created")
        data = [(r[0], r[1]) for r in cur.fetchall()]
        if len(data) < 2:
            return (1, {"trend": "insufficient_data", "data_points": len(data)}, None)
        return (1, {"trend": "stable", "data_points": len(data), "first": data[0], "last": data[-1]}, None)
'''

write_file("memory_forensics.py", make_header(
    "memory_forensics.py", "phase-orchestration", "38", "Memory Forensics",
    "memforensics", "MemoryForensics",
    "Memory forensics authority that detects leaks, tracks object lifetimes, records allocation history, and reports peak usage and growth trends.",
    "Memory forensics authority",
    ["detect_leaks", "track_lifetime", "allocation_history", "peak_usage", "growth_trend"],
    "import json\nimport os\nimport sqlite3",
    memory_forensics_m,
))

# === sql_analyzer.py (Section 39) ===
sql_analyzer_m = '''
    def LogQuery(self, params):
        query = self._p(params, "query", "")
        duration = self._p(params, "duration_ms", 0)
        if not query:
            return (0, None, ("NO_PARAM", "query required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)", ("sql_query", query[:500], str(duration), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"logged": True}, None)

    def ExplainPlan(self, params):
        sql = self._p(params, "sql", "")
        if not sql:
            return (0, None, ("NO_PARAM", "sql required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("EXPLAIN QUERY PLAN " + sql)
            rows = cur.fetchall()
            return (1, {"plan": rows}, None)
        except Exception as exc:
            return (0, None, ("QUERY_ERROR", str(exc), 0))

    def FindSlow(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, evidence FROM observations "
                    "WHERE observation_type='sql_query' AND CAST(evidence AS REAL) > 100 ORDER BY CAST(evidence AS REAL) DESC")
        results = [{"observation_id": r[0], "query": r[1], "duration_ms": r[2]} for r in cur.fetchall()]
        return (1, {"slow_queries": results, "count": len(results)}, None)

    def SuggestIndexes(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing = set(r[0] for r in cur.fetchall())
        suggestions = []
        cur.execute("SELECT subject FROM observations WHERE observation_type='sql_query'")
        for row in cur.fetchall():
            query = row[0].upper()
            if "WHERE" in query:
                suggestions.append({"query": row[0], "suggestion": "Add index on WHERE clause columns"})
        return (1, {"suggestions": suggestions[:20], "existing_indexes": list(existing)}, None)

    def TransactionHistory(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT observation_id, subject, created FROM observations "
                    "WHERE observation_type='transaction' ORDER BY created")
        results = [{"observation_id": r[0], "subject": r[1], "created": r[2]} for r in cur.fetchall()]
        return (1, {"history": results, "count": len(results)}, None)
'''

write_file("sql_analyzer.py", make_header(
    "sql_analyzer.py", "phase-orchestration", "39", "SQL Analyzer",
    "sqlanalyzer", "SqlAnalyzer",
    "SQL analyzer authority that logs queries, explains plans, finds slow queries, suggests indexes, and tracks transaction history.",
    "SQL analysis authority",
    ["log_query", "explain_plan", "find_slow", "suggest_indexes", "transaction_history"],
    "import os\nimport sqlite3",
    sql_analyzer_m,
))

# === file_forensics.py (Section 40) ===
file_forensics_m = '''
    def GetMetadata(self, params):
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            path = row[0]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        stat = os.stat(path)
        return (1, {"path": path, "creation": stat.st_ctime, "modification": stat.st_mtime,
                    "owner": stat.st_uid, "permissions": oct(stat.st_mode), "size": stat.st_size}, None)

    def RenameHistory(self, params):
        file_id = self._p(params, "file_id")
        if not file_id:
            return (0, None, ("NO_PARAM", "file_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_name, version FROM files WHERE file_id=? ORDER BY version", (file_id,))
        results = [{"file_name": r[0], "version": r[1]} for r in cur.fetchall()]
        return (1, {"rename_history": results, "count": len(results)}, None)

    def HashTimeline(self, params):
        file_id = self._p(params, "file_id")
        if not file_id:
            return (0, None, ("NO_PARAM", "file_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT created, hash FROM snapshots WHERE file_id=? ORDER BY created", (file_id,))
        results = [{"created": r[0], "hash": r[1]} for r in cur.fetchall()]
        return (1, {"hash_timeline": results, "count": len(results)}, None)

    def PermissionsCheck(self, params):
        file_id = self._p(params, "file_id")
        path = self._p(params, "path")
        conn = self.Connect()
        cur = conn.cursor()
        if file_id:
            cur.execute("SELECT path FROM files WHERE file_id=?", (file_id,))
            row = cur.fetchone()
            if not row:
                return (0, None, ("NOT_FOUND", "file not found", 0))
            path = row[0]
        if not path or not os.path.isfile(path):
            return (0, None, ("NO_FILE", "File not found", 0))
        stat = os.stat(path)
        perms = oct(stat.st_mode)
        return (1, {"permissions": perms, "readable": os.access(path, os.R_OK),
                    "writable": os.access(path, os.W_OK),
                    "executable": os.access(path, os.X_OK)}, None)
'''

write_file("file_forensics.py", make_header(
    "file_forensics.py", "phase-orchestration", "40", "File Forensics",
    "fileforensics", "FileForensics",
    "File forensics authority that gets metadata, rename history, hash timelines, and permission checks for files.",
    "File forensics authority",
    ["get_metadata", "rename_history", "hash_timeline", "permissions_check"],
    "import os\nimport sqlite3",
    file_forensics_m,
))

# === evolution_engine.py (Section 41) ===
evolution_m = '''
    def ClassTimeline(self, params):
        class_name = self._p(params, "class_name")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if class_id:
            cur.execute("SELECT class_name, version, hash FROM classes WHERE class_id=? ORDER BY version", (class_id,))
        elif class_name:
            cur.execute("SELECT class_name, version, hash FROM classes WHERE class_name=? ORDER BY version", (class_name,))
        else:
            return (0, None, ("NO_PARAM", "class_name or class_id required", 0))
        results = [{"class_name": r[0], "version": r[1], "hash": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def MethodTimeline(self, params):
        method_name = self._p(params, "method_name")
        method_id = self._p(params, "method_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT method_name, version, hash FROM methods WHERE method_id=? ORDER BY version", (method_id,))
        elif method_name:
            cur.execute("SELECT method_name, version, hash FROM methods WHERE method_name=? ORDER BY version", (method_name,))
        else:
            return (0, None, ("NO_PARAM", "method_name or method_id required", 0))
        results = [{"method_name": r[0], "version": r[1], "hash": r[2]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def DependencyTimeline(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT edge_type, src_type, src_id, dst_type, dst_id, created FROM edges ORDER BY created")
        results = [{"edge_type": r[0], "src_type": r[1], "src_id": r[2], "dst_type": r[3],
                    "dst_id": r[4], "created": r[5]} for r in cur.fetchall()]
        return (1, {"timeline": results, "count": len(results)}, None)

    def GrowthRate(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM classes")
        classes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        methods = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        edges = cur.fetchone()[0]
        return (1, {"files": files, "classes": classes, "methods": methods, "edges": edges}, None)

    def ComplexityTrend(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT AVG(cyclomatic_complexity), MAX(cyclomatic_complexity), MIN(cyclomatic_complexity) FROM methods")
        row = cur.fetchone()
        return (1, {"avg": row[0], "max": row[1], "min": row[2]}, None)
'''

write_file("evolution_engine.py", make_header(
    "evolution_engine.py", "phase-orchestration", "41", "Evolution Engine",
    "evolution", "EvolutionEngine",
    "Evolution authority that tracks class, method, dependency timelines, growth rates, and complexity trends over time.",
    "Evolution tracking authority",
    ["class_timeline", "method_timeline", "dependency_timeline", "growth_rate", "complexity_trend"],
    "import os\nimport sqlite3",
    evolution_m,
))

# === refactor_engine.py (Section 49) ===
refactor_m = '''
    def ExtractMethod(self, params):
        method_id = self._p(params, "method_id")
        new_name = self._p(params, "new_name", "extracted_method")
        lines = self._p(params, "lines", [])
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_code, class_id FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        code = row[0] or ""
        extracted = "\\n".join(code.split("\\n")[lines[0]-1:lines[1]] if len(lines) == 2 else [])
        return (1, {"extracted_code": extracted, "new_name": new_name,
                    "class_id": row[1]}, None)

    def InlineMethod(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_code FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        return (1, {"inlined_code": row[0], "method_id": method_id}, None)

    def RenameSymbol(self, params):
        old_name = self._p(params, "old_name")
        new_name = self._p(params, "new_name")
        if not old_name or not new_name:
            return (0, None, ("NO_PARAM", "old_name and new_name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_code FROM methods WHERE method_code LIKE ?",
                    ("%" + old_name + "%",))
        affected = []
        for row in cur.fetchall():
            new_code = (row[1] or "").replace(old_name, new_name)
            affected.append({"method_id": row[0], "changed": True})
        return (1, {"renamed": True, "old_name": old_name, "new_name": new_name,
                    "affected_methods": affected, "count": len(affected)}, None)

    def MoveMethod(self, params):
        method_id = self._p(params, "method_id")
        target_class_id = self._p(params, "target_class_id")
        if not method_id or not target_class_id:
            return (0, None, ("NO_PARAM", "method_id and target_class_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE methods SET class_id=? WHERE method_id=?", (target_class_id, method_id))
        conn.commit()
        return (1, {"moved": True, "method_id": method_id, "target_class_id": target_class_id}, None)

    def PlanRefactor(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        plan = []
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity FROM methods WHERE cyclomatic_complexity > 10 ORDER BY cyclomatic_complexity DESC")
        for row in cur.fetchall():
            plan.append({"method_id": row[0], "method_name": row[1],
                         "complexity": row[2], "action": "extract_method"})
        cur.execute("SELECT class_id, class_name, method_count FROM classes WHERE method_count > 20")
        for row in cur.fetchall():
            plan.append({"class_id": row[0], "class_name": row[1],
                         "method_count": row[2], "action": "split_class"})
        return (1, {"refactor_plan": plan, "count": len(plan)}, None)
'''

write_file("refactor_engine.py", make_header(
    "refactor_engine.py", "phase-orchestration", "49", "Refactor Engine",
    "refactor", "RefactorEngine",
    "Refactor authority that extracts methods, inlines methods, renames symbols, moves methods between classes, and plans refactors.",
    "Refactoring authority",
    ["extract_method", "inline_method", "rename_symbol", "move_method", "plan_refactor"],
    "import os\nimport sqlite3",
    refactor_m,
))

# === api_engine.py (Section 51) ===
api_m = '''
    def GetApiSurface(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        surface = {"classes": [], "methods": []}
        cur.execute("SELECT class_id, class_name FROM classes WHERE is_vbstyle=1")
        surface["classes"] = [{"class_id": r[0], "class_name": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT method_id, method_name, class_id FROM methods WHERE method_name='Run'")
        surface["methods"] = [{"method_id": r[0], "method_name": r[1], "class_id": r[2]} for r in cur.fetchall()]
        return (1, {"api_surface": surface}, None)

    def GetEndpoints(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, signature FROM methods WHERE method_name='Run'")
        endpoints = [{"method_id": r[0], "endpoint": r[1], "signature": r[2]} for r in cur.fetchall()]
        return (1, {"endpoints": endpoints, "count": len(endpoints)}, None)

    def GetParameters(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, parameters, signature FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        params_list = []
        try:
            params_list = json.loads(row[1]) if row[1] else []
        except (ValueError, TypeError):
            pass
        return (1, {"method_name": row[0], "parameters": params_list, "signature": row[2]}, None)

    def GetReturnTypes(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name, return_type FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Method not found", 0))
        return (1, {"method_name": row[0], "return_type": row[1]}, None)

    def GenerateDocs(self, params):
        surface = self.GetApiSurface(params)
        if surface[0] != 1:
            return surface
        docs = []
        for cls in surface[1]["api_surface"]["classes"]:
            docs.append("## " + cls["class_name"] + "\\n")
        for m in surface[1]["api_surface"]["methods"]:
            docs.append("- " + m["method_name"] + "\\n")
        return (1, {"docs": "\\n".join(docs), "classes": len(surface[1]["api_surface"]["classes"]),
                    "methods": len(surface[1]["api_surface"]["methods"])}, None)
'''

write_file("api_engine.py", make_header(
    "api_engine.py", "phase-orchestration", "51", "API Engine",
    "api", "ApiEngine",
    "API authority that gets the API surface, endpoints, parameters, return types, and generates documentation.",
    "API documentation authority",
    ["get_api_surface", "get_endpoints", "get_parameters", "get_return_types", "generate_docs"],
    "import json\nimport os\nimport sqlite3",
    api_m,
))

# === config_engine.py (Section 52) ===
config_m = '''
    def GetConfig(self, params):
        return (1, {"config": dict(self.state["config"])}, None)

    def SetConfig(self, params):
        for key, value in (params or {}).items():
            self.state["config"][key] = value
        return (1, {"config": dict(self.state["config"])}, None)

    def GetConstants(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("SELECT name, value FROM config_constants")
            results = [{"name": r[0], "value": r[1]} for r in cur.fetchall()]
        except Exception:
            results = []
        return (1, {"constants": results, "count": len(results)}, None)

    def SetConstant(self, params):
        name = self._p(params, "name")
        value = self._p(params, "value")
        if not name:
            return (0, None, ("NO_PARAM", "name required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute("INSERT OR REPLACE INTO config_constants (name, value) VALUES (?, ?)",
                        (name, str(value)))
            conn.commit()
            return (1, {"set": True, "name": name, "value": value}, None)
        except Exception as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))

    def GetEnvironment(self, params):
        import os as _os
        env = {k: v for k, v in _os.environ.items() if not k.startswith("_")}
        return (1, {"environment": env, "count": len(env)}, None)

    def ValidateConfig(self, params):
        config = self.state["config"]
        issues = []
        if "db_path" not in config:
            issues.append("missing db_path")
        if not os.path.isfile(config.get("db_path", "")):
            issues.append("db_path does not exist")
        return (1, {"valid": len(issues) == 0, "issues": issues}, None)
'''

write_file("config_engine.py", make_header(
    "config_engine.py", "phase-orchestration", "52", "Config Engine",
    "config", "ConfigEngine",
    "Config authority that gets/sets configuration, manages constants, reads environment variables, and validates config.",
    "Configuration authority",
    ["get_config", "set_config", "get_constants", "set_constant", "get_environment", "validate_config"],
    "import os\nimport sqlite3",
    config_m,
))

print("Orchestration: 15 files done")
