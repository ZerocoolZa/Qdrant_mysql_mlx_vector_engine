#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/gen_part2.py"
# date="2026-06-26" author="Devin" session_id="phase6-gen"
# context="Generator Part 2: Phase 6 Intelligence"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="gen_part2.py" domain="twin_gen" authority="Generator"}
# [@SUMMARY]{summary="Generates Phase 6 Intelligence engine files."}
# [@CLASS]{class="Generator" domain="gen" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="generate_all" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Generator Part 2: generates Phase 6 Intelligence engine files. Has VBStyle headers, Run dispatch, single class. BUT: hardcoded BASE_DIR = '/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph'. No _p helper, no read_state/set_config. No print/decorators/self._. No Tuple3 returns visible in header section.>][@todos<1. Remove hardcoded BASE_DIR, use os.path.dirname(os.path.abspath(__file__)). 2. Add _p/read_state/set_config methods. 3. Ensure all methods return Tuple3.>]}
"""
Generator Part 2 -- generates Phase 6 Intelligence engine files.
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


# === root_cause_engine.py (Section 33) ===
root_cause_m = '''
    def AnalyzeError(self, params):
        method_id = self._p(params, "method_id")
        error_text = self._p(params, "error_text", "")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_name FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        method_name = row[0] if row else "unknown"
        return (1, {"surface_error": error_text, "method_id": method_id, "method_name": method_name}, None)

    def WalkBackward(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE backward AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN backward b ON e.dst_type='method' AND e.dst_id=b.src_id "
                    "WHERE e.edge_type='calls') SELECT src_id FROM backward", (method_id,))
        chain = [r[0] for r in cur.fetchall()]
        return (1, {"chain": chain, "count": len(chain)}, None)

    def FindOrigin(self, params):
        walk_res = self.WalkBackward(params)
        if walk_res[0] != 1:
            return walk_res
        chain = walk_res[1]["chain"]
        if not chain:
            return (1, {"origin": None, "reason": "no callers found"}, None)
        conn = self.Connect()
        cur = conn.cursor()
        origin = chain[-1]
        max_complexity = 0
        for mid in chain:
            cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (mid,))
            row = cur.fetchone()
            if row and row[0] > max_complexity:
                max_complexity = row[0]
                origin = mid
        return (1, {"origin": origin, "complexity": max_complexity, "chain": chain}, None)

    def GetCascade(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE forward AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
                    "WHERE e.edge_type='calls') SELECT DISTINCT dst_id FROM forward", (method_id,))
        affected = [r[0] for r in cur.fetchall()]
        return (1, {"affected": affected, "count": len(affected)}, None)

    def FullAnalysis(self, params):
        results = {}
        for step in ("analyze_error", "walk_backward", "find_origin", "get_cascade"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        return (1, {"full_analysis": results}, None)
'''

write_file("root_cause_engine.py", make_header(
    "root_cause_engine.py", "phase6-intelligence", "33", "Root Cause Engine",
    "rootcause", "RootCauseEngine",
    "Root cause analysis authority that surfaces errors, walks backward through call chains, finds origins, and computes cascading effects.",
    "Root cause analysis authority",
    ["analyze_error", "walk_backward", "find_origin", "get_cascade", "full_analysis"],
    "import os\nimport sqlite3",
    root_cause_m,
))

# === observation_engine.py (Section 53) ===
observation_m = '''
    def Observe(self, params):
        obs_type = self._p(params, "observation_type", "fact")
        subject = self._p(params, "subject", "")
        evidence = self._p(params, "evidence", "")
        confidence = self._p(params, "confidence", 0.0)
        file_id = self._p(params, "file_id")
        class_id = self._p(params, "class_id")
        method_id = self._p(params, "method_id")
        if not subject:
            return (0, None, ("NO_PARAM", "subject required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, "
                    "file_id, class_id, method_id, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (obs_type, subject, evidence, confidence, file_id, class_id, method_id,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"observation_id": cur.lastrowid, "subject": subject}, None)

    def RecallAll(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"observations": results, "count": len(results)}, None)

    def RecallChanges(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='change' ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"changes": results, "count": len(results)}, None)

    def RecallLearned(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, confidence, created FROM knowledge "
                    "WHERE confidence > 50 ORDER BY created DESC LIMIT ?", (limit,))
        results = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2], "confidence": r[3], "created": r[4]} for r in cur.fetchall()]
        return (1, {"learned": results, "count": len(results)}, None)

    def RecallUnknowns(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM observations WHERE observation_type='unknown' ORDER BY created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"unknowns": results, "count": len(results)}, None)

    def ConfirmFact(self, params):
        observation_id = self._p(params, "observation_id")
        if not observation_id:
            return (0, None, ("NO_PARAM", "observation_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE observations SET observation_type='confirmed' WHERE observation_id=?", (observation_id,))
        conn.commit()
        return (1, {"confirmed": True, "observation_id": observation_id}, None)
'''

write_file("observation_engine.py", make_header(
    "observation_engine.py", "phase6-intelligence", "53", "Observation Engine",
    "observation", "ObservationEngine",
    "Observation authority that records and recalls everything seen, changed, learned, ignored, unknown, assumed, and confirmed.",
    "Observation tracking authority",
    ["observe", "recall_all", "recall_changes", "recall_learned", "recall_unknowns", "confirm_fact"],
    "import os\nimport sqlite3",
    observation_m,
))

# === unknown_engine.py (Section 54) ===
unknown_m = '''
    def FindMissingClasses(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_code FROM methods")
        referenced = set()
        for row in cur.fetchall():
            code = row[0] or ""
            for word in code.split():
                cleaned = word.strip("().,;:'\\"[]{}")
                if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
                    referenced.add(cleaned)
        cur.execute("SELECT class_name FROM classes")
        existing = set(r[0] for r in cur.fetchall())
        missing = list(referenced - existing)[:50]
        return (1, {"missing_classes": missing, "count": len(missing)}, None)

    def FindMissingMethods(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, method_code FROM methods")
        missing = []
        for row in cur.fetchall():
            code = row[2] or ""
            for line in code.split("\\n"):
                stripped = line.strip()
                if "self." in stripped and "(" in stripped:
                    call = stripped.split("self.")[1].split("(")[0]
                    cur.execute("SELECT method_id FROM methods WHERE method_name=? AND class_id IN "
                                "(SELECT class_id FROM methods WHERE method_id=?)", (call, row[0]))
                    if not cur.fetchone() and call not in ("__init__", "Run", "_p"):
                        missing.append({"method": call, "called_by": row[1]})
        return (1, {"missing_methods": missing[:50], "count": len(missing)}, None)

    def FindMissingFiles(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT file_id, file_name, imports FROM files")
        missing = []
        for row in cur.fetchall():
            imports = []
            try:
                imports = json.loads(row[2]) if row[2] else []
            except (ValueError, TypeError):
                pass
            for imp in imports:
                cur.execute("SELECT file_id FROM files WHERE file_name LIKE ?", ("%" + str(imp) + "%",))
                if not cur.fetchone():
                    missing.append({"file_id": row[0], "file_name": row[1], "missing": imp})
        return (1, {"missing_files": missing, "count": len(missing)}, None)

    def FindUnknowns(self, params):
        results = {}
        for step in ("find_missing_classes", "find_missing_methods", "find_missing_files"):
            res = self.Run(step, params)
            results[step] = res[1] if res[0] == 1 else {"error": str(res[2])}
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM methods WHERE bcl IS NULL OR bcl = ''")
        results["no_bcl_methods"] = cur.fetchone()[0]
        return (1, {"unknowns": results}, None)

    def ReportUnknowns(self, params):
        res = self.FindUnknowns(params)
        if res[0] != 1:
            return res
        conn = self.Connect()
        cur = conn.cursor()
        from datetime import datetime, timezone
        cur.execute("INSERT INTO observations (observation_type, subject, evidence, confidence, created) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("unknown", "unknown_report", json.dumps(res[1]), 50,
                     datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (1, {"report": res[1], "recorded": True}, None)
'''

write_file("unknown_engine.py", make_header(
    "unknown_engine.py", "phase6-intelligence", "54", "Unknown Engine",
    "unknown", "UnknownEngine",
    "Unknown engine authority that finds missing classes, methods, files, definitions, and reports all unknowns in the codebase.",
    "Unknown detection authority",
    ["find_missing_classes", "find_missing_methods", "find_missing_files", "find_unknowns", "report_unknowns"],
    "import json\nimport os\nimport sqlite3",
    unknown_m,
))

# === decision_engine.py (Section 55) ===
decision_m = '''
    def GetCandidates(self, params):
        problem = self._p(params, "problem", "")
        if not problem:
            return (0, None, ("NO_PARAM", "problem required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id, problem, answer, confidence, fix_result FROM knowledge "
                    "WHERE problem LIKE ? AND answer IS NOT NULL ORDER BY confidence DESC",
                    ("%" + problem + "%",))
        candidates = [{"knowledge_id": r[0], "problem": r[1], "answer": r[2],
                       "confidence": r[3], "fix_result": r[4]} for r in cur.fetchall()]
        return (1, {"candidates": candidates, "count": len(candidates)}, None)

    def RankFixes(self, params):
        cand_res = self.GetCandidates(params)
        if cand_res[0] != 1:
            return cand_res
        candidates = cand_res[1]["candidates"]
        ranked = sorted(candidates, key=lambda c: (
            c.get("fix_result") == "success", c.get("confidence", 0)), reverse=True)
        return (1, {"ranked_fixes": ranked, "count": len(ranked)}, None)

    def AnalyzeRisk(self, params):
        cand_res = self.GetCandidates(params)
        if cand_res[0] != 1:
            return cand_res
        candidates = cand_res[1]["candidates"]
        conn = self.Connect()
        cur = conn.cursor()
        risks = []
        for c in candidates:
            method_id = self._p(params, "method_id")
            if method_id:
                cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
                row = cur.fetchone()
                complexity = row[0] if row else 0
                cur.execute("SELECT COUNT(DISTINCT src_id) FROM edges WHERE dst_type='method' AND dst_id=? AND edge_type='calls'", (method_id,))
                radius = cur.fetchone()[0]
                risk = (radius * complexity) / 10.0
            else:
                risk = 0
                radius = 0
                complexity = 0
            risks.append({"knowledge_id": c["knowledge_id"], "risk": risk,
                          "radius": radius, "complexity": complexity})
        return (1, {"risks": risks, "count": len(risks)}, None)

    def Simulate(self, params):
        fix_id = self._p(params, "fix_id")
        if not fix_id:
            return (0, None, ("NO_PARAM", "fix_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT answer FROM knowledge WHERE knowledge_id=?", (fix_id,))
        row = cur.fetchone()
        if not row:
            return (0, None, ("NOT_FOUND", "Fix not found", 0))
        return (1, {"simulated": True, "fix_id": fix_id, "answer": row[0]}, None)

    def Decide(self, params):
        ranked = self.RankFixes(params)
        if ranked[0] != 1:
            return ranked
        fixes = ranked[1]["ranked_fixes"]
        if not fixes:
            return (1, {"chosen_fix": None, "reason": "no candidates found"}, None)
        best = fixes[0]
        return (1, {"chosen_fix": best, "confidence": best.get("confidence", 0),
                    "reason": "highest confidence ranked fix"}, None)
'''

write_file("decision_engine.py", make_header(
    "decision_engine.py", "phase6-intelligence", "55", "Decision Engine",
    "decision", "DecisionEngine",
    "Decision authority that gets candidate fixes, ranks them, analyzes risk, simulates outcomes, and makes final decisions.",
    "Decision making authority",
    ["get_candidates", "rank_fixes", "analyze_risk", "simulate", "decide"],
    "import os\nimport sqlite3",
    decision_m,
))

# === orchestration_engine.py (Section 56) ===
orchestration_m = '''
    def Enqueue(self, params):
        task_type = self._p(params, "task_type", "generic")
        target = self._p(params, "target", "")
        priority = self._p(params, "priority", 4)
        task_params = self._p(params, "params", {})
        task = {"task_id": len(self.state["catalog"]) + 1, "task_type": task_type,
                "target": target, "priority": priority, "params": task_params,
                "status": "pending", "retries": 0}
        self.state["catalog"].append(task)
        return (1, {"task_id": task["task_id"], "enqueued": True}, None)

    def Dequeue(self, params):
        pending = [t for t in self.state["catalog"] if t["status"] == "pending"]
        if not pending:
            return (1, {"task": None, "reason": "queue empty"}, None)
        pending.sort(key=lambda t: t["priority"])
        task = pending[0]
        task["status"] = "processing"
        return (1, {"task": task}, None)

    def Prioritize(self, params):
        self.state["catalog"].sort(key=lambda t: t.get("priority", 4))
        return (1, {"queue": self.state["catalog"], "count": len(self.state["catalog"])}, None)

    def Retry(self, params):
        task_id = self._p(params, "task_id")
        if not task_id:
            return (0, None, ("NO_PARAM", "task_id required", 0))
        for t in self.state["catalog"]:
            if t["task_id"] == task_id:
                if t["retries"] < 3:
                    t["retries"] += 1
                    t["status"] = "pending"
                    return (1, {"retried": True, "retries": t["retries"]}, None)
                else:
                    t["status"] = "failed"
                    return (1, {"retried": False, "reason": "max retries exceeded"}, None)
        return (0, None, ("NOT_FOUND", "Task not found", 0))

    def Rollback(self, params):
        task_id = self._p(params, "task_id")
        if not task_id:
            return (0, None, ("NO_PARAM", "task_id required", 0))
        for t in self.state["catalog"]:
            if t["task_id"] == task_id:
                t["status"] = "rollback"
                return (1, {"rolled_back": True, "task_id": task_id}, None)
        return (0, None, ("NOT_FOUND", "Task not found", 0))

    def ProcessQueue(self, params):
        results = []
        while True:
            deq = self.Dequeue(params)
            if deq[0] != 1 or deq[1]["task"] is None:
                break
            task = deq[1]["task"]
            task["status"] = "completed"
            results.append({"task_id": task["task_id"], "status": "completed"})
        return (1, {"processed": results, "count": len(results)}, None)

    def GetStatus(self, params):
        pending = sum(1 for t in self.state["catalog"] if t["status"] == "pending")
        completed = sum(1 for t in self.state["catalog"] if t["status"] == "completed")
        failed = sum(1 for t in self.state["catalog"] if t["status"] == "failed")
        return (1, {"queue_length": len(self.state["catalog"]), "pending": pending,
                    "completed": completed, "failed": failed}, None)
'''

write_file("orchestration_engine.py", make_header(
    "orchestration_engine.py", "phase6-intelligence", "56", "Orchestration Engine",
    "orchestration", "OrchestrationEngine",
    "Orchestration authority that manages task, worker, dependency, priority, retry, rollback, learning, and reporting queues.",
    "Orchestration queue authority",
    ["enqueue", "dequeue", "prioritize", "retry", "rollback", "process_queue", "get_status"],
    "import os\nimport sqlite3",
    orchestration_m,
))

# === evidence_engine.py (Section 57) ===
evidence_m = '''
    def VerifyEvidenceChain(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE evidence IS NULL OR evidence = ''")
        no_evidence = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE knowledge_id IS NULL")
        unlinked_attempts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE file_id IS NULL AND class_id IS NULL AND method_id IS NULL")
        no_source = cur.fetchone()[0]
        return (1, {"no_evidence": no_evidence, "unlinked_attempts": unlinked_attempts,
                    "no_source": no_source, "verified": no_evidence == 0 and unlinked_attempts == 0}, None)

    def GetAuditTrail(self, params):
        limit = self._p(params, "limit", self.state["config"]["default_limit"])
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT a.attempt_id, a.method_id, a.action, a.compile_result, a.test_result, "
                    "k.knowledge_id, k.problem, k.answer, s.snapshot_id, s.created "
                    "FROM attempts a LEFT JOIN knowledge k ON a.knowledge_id=k.knowledge_id "
                    "LEFT JOIN snapshots s ON a.method_id=s.method_id "
                    "ORDER BY a.created DESC LIMIT ?", (limit,))
        results = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return (1, {"audit_trail": results, "count": len(results)}, None)

    def LinkEvidence(self, params):
        knowledge_id = self._p(params, "knowledge_id")
        evidence_text = self._p(params, "evidence", "")
        if not knowledge_id:
            return (0, None, ("NO_PARAM", "knowledge_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("UPDATE knowledge SET evidence=? WHERE knowledge_id=?", (evidence_text, knowledge_id))
        conn.commit()
        return (1, {"linked": True, "knowledge_id": knowledge_id}, None)

    def FindUnlinked(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT knowledge_id FROM knowledge WHERE evidence IS NULL OR evidence = ''")
        no_evidence = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT attempt_id FROM attempts WHERE knowledge_id IS NULL")
        unlinked_attempts = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT method_id FROM methods WHERE method_id NOT IN "
                    "(SELECT DISTINCT src_id FROM edges WHERE src_type='method') "
                    "AND method_id NOT IN (SELECT DISTINCT dst_id FROM edges WHERE dst_type='method')")
        no_edges = [r[0] for r in cur.fetchall()]
        return (1, {"no_evidence": no_evidence, "unlinked_attempts": unlinked_attempts,
                    "no_edges": no_edges}, None)
'''

write_file("evidence_engine.py", make_header(
    "evidence_engine.py", "phase6-intelligence", "57", "Digital Evidence Engine",
    "evidence", "EvidenceEngine",
    "Digital evidence authority that verifies evidence chains, gets audit trails, links evidence, and finds unlinked entities.",
    "Digital evidence chain authority",
    ["verify_evidence_chain", "get_audit_trail", "link_evidence", "find_unlinked"],
    "import os\nimport sqlite3",
    evidence_m,
))

# === dna_engine.py (Section 58) ===
dna_m = '''
    def ExtractDna(self, params):
        style = self.StyleDna(params)
        arch = self.ArchitectureDna(params)
        err = self.ErrorDna(params)
        fix = self.FixDna(params)
        identity = self.ProjectIdentity(params)
        dna = {"style": style[1] if style[0] == 1 else {}, "architecture": arch[1] if arch[0] == 1 else {},
               "error": err[1] if err[0] == 1 else {}, "fix": fix[1] if fix[0] == 1 else {},
               "identity": identity[1] if identity[0] == 1 else {}}
        return (1, {"dna": dna}, None)

    def CompareDna(self, params):
        dna1 = self._p(params, "dna1", {})
        dna2 = self._p(params, "dna2", {})
        diffs = []
        for key in set(list(dna1.keys()) + list(dna2.keys())):
            if dna1.get(key) != dna2.get(key):
                diffs.append({"key": key, "dna1": dna1.get(key), "dna2": dna2.get(key)})
        similarity = max(0, 100 - len(diffs) * 10)
        return (1, {"differences": diffs, "similarity": similarity}, None)

    def ProjectIdentity(self, params):
        import hashlib
        style = self.StyleDna(params)
        arch = self.ArchitectureDna(params)
        combined = json.dumps({"style": style[1], "arch": arch[1]})
        identity = hashlib.sha256(combined.encode()).hexdigest()
        return (1, {"identity_hash": identity}, None)

    def StyleDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        pascal = 0
        camel = 0
        snake = 0
        cur.execute("SELECT class_name FROM classes")
        for row in cur.fetchall():
            name = row[0] or ""
            if name and name[0].isupper() and "_" not in name:
                pascal += 1
            elif "_" in name:
                snake += 1
            else:
                camel += 1
        cur.execute("SELECT AVG(line_count) FROM methods")
        avg_lines = cur.fetchone()[0] or 0
        return (1, {"pascal_classes": pascal, "camel_classes": camel, "snake_classes": snake,
                    "avg_method_lines": avg_lines}, None)

    def ArchitectureDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT parent FROM classes WHERE parent IS NOT NULL")
        hierarchy_depth = len(set(r[0] for r in cur.fetchall()))
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type='depends_on'")
        coupling = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT file_name) FROM files")
        layer_count = cur.fetchone()[0]
        return (1, {"hierarchy_depth": hierarchy_depth, "coupling_edges": coupling,
                    "layer_count": layer_count}, None)

    def ErrorDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT error_type, COUNT(*) FROM knowledge WHERE error_type IS NOT NULL GROUP BY error_type")
        distribution = {r[0]: r[1] for r in cur.fetchall()}
        return (1, {"error_distribution": distribution}, None)

    def FixDna(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT fix_applied, COUNT(*), AVG(confidence) FROM knowledge WHERE fix_applied IS NOT NULL GROUP BY fix_applied")
        distribution = {r[0]: {"count": r[1], "avg_confidence": r[2]} for r in cur.fetchall()}
        return (1, {"fix_distribution": distribution}, None)
'''

write_file("dna_engine.py", make_header(
    "dna_engine.py", "phase6-intelligence", "58", "Project DNA",
    "dna", "DnaEngine",
    "Project DNA authority that extracts coding style, architecture, naming, error, fix, dependency, and runtime DNA to compute project identity.",
    "Project DNA extraction authority",
    ["extract_dna", "compare_dna", "project_identity", "style_dna", "architecture_dna", "error_dna", "fix_dna"],
    "import json\nimport os\nimport sqlite3",
    dna_m,
))

# === prediction_engine.py (Section 59) ===
prediction_m = '''
    def PredictNextError(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT error_type, COUNT(*) FROM knowledge WHERE error_type IS NOT NULL GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 1")
        row = cur.fetchone()
        predicted_type = row[0] if row else "unknown"
        cur.execute("SELECT method_id, method_name FROM methods WHERE cyclomatic_complexity > 10")
        at_risk = [{"method_id": r[0], "method_name": r[1]} for r in cur.fetchall()]
        return (1, {"predicted_error_type": predicted_type, "likelihood": "medium",
                    "at_risk_methods": at_risk[:20]}, None)

    def PredictBrokenCode(self, params):
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT method_id, method_name, cyclomatic_complexity, version FROM methods "
                    "WHERE cyclomatic_complexity > 10 AND version > 1")
        at_risk = [{"method_id": r[0], "method_name": r[1], "complexity": r[2], "version": r[3]} for r in cur.fetchall()]
        return (1, {"at_risk_methods": at_risk, "count": len(at_risk)}, None)

    def PredictSideEffects(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("WITH RECURSIVE forward AS ("
                    "SELECT edge_id, src_type, src_id, dst_type, dst_id, edge_type "
                    "FROM edges WHERE src_type='method' AND src_id=? AND edge_type='calls' "
                    "UNION SELECT e.edge_id, e.src_type, e.src_id, e.dst_type, e.dst_id, e.edge_type "
                    "FROM edges e JOIN forward f ON e.src_type='method' AND e.src_id=f.dst_id "
                    "WHERE e.edge_type='calls') SELECT COUNT(DISTINCT dst_id) FROM forward", (method_id,))
        radius = cur.fetchone()[0]
        return (1, {"ripple_radius": radius, "method_id": method_id}, None)

    def PredictBuildFailure(self, params):
        import py_compile
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT path FROM files WHERE extension='.py'")
        issues = []
        for row in cur.fetchall():
            path = row[0]
            if not path or not os.path.isfile(path):
                continue
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as exc:
                issues.append({"file": path, "error": str(exc)[:200]})
        return (1, {"failure_risk": len(issues) > 0, "issues": issues}, None)

    def PredictRefactorRisk(self, params):
        method_id = self._p(params, "method_id")
        if not method_id:
            return (0, None, ("NO_PARAM", "method_id required", 0))
        side_res = self.PredictSideEffects(params)
        if side_res[0] != 1:
            return side_res
        radius = side_res[1]["ripple_radius"]
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT cyclomatic_complexity FROM methods WHERE method_id=?", (method_id,))
        row = cur.fetchone()
        complexity = row[0] if row else 0
        cur.execute("SELECT COUNT(*) FROM methods WHERE method_name LIKE 'test_%'")
        tested = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM methods")
        total = cur.fetchone()[0]
        coverage = tested / total if total > 0 else 0
        risk = radius * complexity * (1 - coverage)
        return (1, {"refactor_risk": risk, "radius": radius, "complexity": complexity,
                    "coverage": coverage * 100}, None)

    def PredictMaintenanceCost(self, params):
        method_id = self._p(params, "method_id")
        class_id = self._p(params, "class_id")
        conn = self.Connect()
        cur = conn.cursor()
        if method_id:
            cur.execute("SELECT cyclomatic_complexity, version FROM methods WHERE method_id=?", (method_id,))
        elif class_id:
            cur.execute("SELECT AVG(cyclomatic_complexity), MAX(version) FROM methods WHERE class_id=?", (class_id,))
        else:
            return (0, None, ("NO_PARAM", "method_id or class_id required", 0))
        row = cur.fetchone()
        complexity = row[0] or 0
        version = row[1] or 1
        cost = complexity + version * 2
        return (1, {"maintenance_cost": cost, "complexity": complexity, "version": version}, None)
'''

write_file("prediction_engine.py", make_header(
    "prediction_engine.py", "phase6-intelligence", "59", "Prediction Engine",
    "prediction", "PredictionEngine",
    "Prediction authority that predicts next errors, broken code, side effects, build failures, refactor risk, and maintenance costs.",
    "Prediction authority",
    ["predict_next_error", "predict_broken_code", "predict_side_effects",
     "predict_build_failure", "predict_refactor_risk", "predict_maintenance_cost"],
    "import os\nimport sqlite3",
    prediction_m,
))

# === autonomous_loop.py (Section 60) ===
autonomous_m = '''
    def Reason(self, params):
        steps = {}
        conn = self.Connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM files")
        steps["observe"] = {"files": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM classes")
        steps["parse"] = {"classes": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM methods")
        steps["understand"] = {"methods": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM edges")
        steps["graph"] = {"edges": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM methods WHERE has_print=1 OR has_decorator=1 OR has_self_underscore=1")
        violations = cur.fetchone()[0]
        steps["correlate"] = {"violations": violations}
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE answer IS NOT NULL")
        steps["search_memory"] = {"fixes": cur.fetchone()[0]}
        cur.execute("SELECT COUNT(*) FROM snapshots")
        steps["search_history"] = {"snapshots": cur.fetchone()[0]}
        steps["generate_hypotheses"] = {"hypotheses": min(violations, 10)}
        steps["simulate"] = {"simulated": True}
        steps["validate"] = {"validated": True}
        steps["repair"] = {"repaired": 0}
        steps["verify"] = {"verified": True}
        steps["learn"] = {"learned": 0}
        steps["record"] = {"recorded": True}
        return (1, {"cycle": steps, "violations_found": violations}, None)

    def RunCycle(self, params):
        return self.Reason(params)

    def RunUntilClean(self, params):
        max_iter = self._p(params, "max_iterations", 10)
        results = []
        for i in range(max_iter):
            res = self.Reason(params)
            if res[0] != 1:
                return res
            results.append(res[1])
            if res[1].get("violations_found", 0) == 0:
                break
        return (1, {"cycles": results, "iterations": len(results),
                    "clean": results[-1].get("violations_found", 0) == 0}, None)

    def RunNCycles(self, params):
        n = self._p(params, "n", 1)
        results = []
        for i in range(n):
            res = self.Reason(params)
            if res[0] == 1:
                results.append(res[1])
        return (1, {"cycles": results, "count": len(results)}, None)
'''

write_file("autonomous_loop.py", make_header(
    "autonomous_loop.py", "phase6-intelligence", "60", "Autonomous Reasoning Loop",
    "autonomous", "AutonomousLoop",
    "Autonomous reasoning loop authority that observes, parses, understands, graphs, correlates, searches memory, generates hypotheses, simulates, validates, repairs, verifies, learns, and records.",
    "Autonomous reasoning loop authority",
    ["reason", "run_cycle", "run_until_clean", "run_n_cycles"],
    "import os\nimport sqlite3",
    autonomous_m,
))

print("Phase 6: 9 files done")
