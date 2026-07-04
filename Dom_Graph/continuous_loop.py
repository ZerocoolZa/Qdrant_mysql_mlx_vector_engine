#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/continuous_loop.py"
# date="2026-06-26" author="Devin" session_id="phase-orchestration"
# context="Project Digital Twin Section 16 Continuous Loop"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="continuous_loop.py" domain="twin_continuous" authority="ContinuousLoop"}
# [@SUMMARY]{summary="Continuous loop authority that orchestrates scan, ingest, index, graph, detect, search, repair, validate, and learn in a repeating cycle."}
# [@CLASS]{class="ContinuousLoop" domain="continuous" authority="single"}
# [@METHOD]{method="run_full_cycle" type="command"}
# [@METHOD]{method="run_n_cycles" type="command"}
# [@METHOD]{method="detect_and_fix" type="command"}
# [@METHOD]{method="run_until_clean" type="command"}
# [@METHOD]{method="scan" type="command"}
# [@METHOD]{method="ingest" type="command"}
# [@METHOD]{method="index" type="command"}
# [@METHOD]{method="graph" type="command"}
# [@METHOD]{method="detect" type="command"}
# [@METHOD]{method="search" type="command"}
# [@METHOD]{method="repair" type="command"}
# [@METHOD]{method="validate" type="command"}
# [@METHOD]{method="learn" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<ContinuousLoop: orchestrates scan/ingest/index/graph/detect/search/repair/validate/learn in repeating cycle. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
ContinuousLoop -- Continuous loop orchestrator.
Implements Section 16 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: run_full_cycle, run_n_cycles, detect_and_fix, run_until_clean,
          scan, ingest, index, graph, detect, search, repair, validate, learn.
"""
import importlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
DEFAULT_DIR = os.path.dirname(os.path.abspath(__file__))

# Maps step name -> (module, class, command)
STEP_ENGINES = {
    "scan": ("ingestion_engine", "IngestionEngine", "scan"),
    "ingest": ("ingestion_engine", "IngestionEngine", "ingest_directory"),
    "index": ("static_analyzer", "StaticAnalyzer", "analyze_all"),
    "graph": ("graph_builder", "GraphBuilder", "build_all"),
    "detect": ("pattern_engine", "PatternEngine", "detect_violations"),
    "search": ("knowledge_engine", "KnowledgeEngine", "search_similar"),
    "repair": ("fix_engine", "FixEngine", "apply_fix"),
    "validate": ("validation_engine", "ValidationEngine", "validate_all"),
    "learn": ("knowledge_engine", "KnowledgeEngine", "learn"),
}


class ContinuousLoop:
    """Continuous loop orchestrator."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "target_dir": DEFAULT_DIR,
            },
            "catalog": [],
            "results": [],
            "engines": {},
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "run_full_cycle":
            return self.RunFullCycle(params)
        elif command == "run_n_cycles":
            return self.RunNCycles(params)
        elif command == "detect_and_fix":
            return self.DetectAndFix(params)
        elif command == "run_until_clean":
            return self.RunUntilClean(params)
        elif command == "scan":
            return self.Scan(params)
        elif command == "ingest":
            return self.Ingest(params)
        elif command == "index":
            return self.Index(params)
        elif command == "graph":
            return self.Graph(params)
        elif command == "detect":
            return self.Detect(params)
        elif command == "search":
            return self.Search(params)
        elif command == "repair":
            return self.Repair(params)
        elif command == "validate":
            return self.Validate(params)
        elif command == "learn":
            return self.Learn(params)

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
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def GetEngine(self, module_name, class_name):
        # Lazy import + cache engine instances so the loop reuses them.
        cache_key = module_name + "." + class_name
        if cache_key in self.state["engines"]:
            return self.state["engines"][cache_key]
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            return (0, None, ("IMPORT_FAILED", str(exc), 0))
        cls = getattr(module, class_name, None)
        if cls is None:
            return (0, None, ("CLASS_MISSING", class_name, 0))
        param = {"db_path": self.state["config"]["db_path"],
                 "target_dir": self.state["config"]["target_dir"]}
        try:
            engine = cls(param=param)
        except Exception as exc:
            return (0, None, ("ENGINE_INIT_FAILED", str(exc), 0))
        self.state["engines"][cache_key] = engine
        return (1, engine, None)

    def RunStep(self, step, params):
        # 16.1-16.9: dispatch one step to its configured engine
        spec = STEP_ENGINES.get(step)
        if spec is None:
            return (0, None, ("UNKNOWN_STEP", "Unknown step: " + str(step), 0))
        module_name, class_name, command = spec
        got = self.GetEngine(module_name, class_name)
        if got[0] != 1:
            return got
        engine = got[1]
        step_params = dict(params)
        step_params.setdefault("db_path", self.state["config"]["db_path"])
        step_params.setdefault("directory", self.state["config"]["target_dir"])
        step_params.setdefault("target_dir", self.state["config"]["target_dir"])
        try:
            res = engine.Run(command, step_params)
        except Exception as exc:
            return (0, None, ("STEP_EXCEPTION", str(exc), 0))
        return res

    def Scan(self, params):
        # 16.1 scan: IngestionEngine.Run("scan", ...)
        return self.RunStep("scan", params)

    def Ingest(self, params):
        # 16.2 ingest: IngestionEngine.Run("ingest_directory", ...)
        return self.RunStep("ingest", params)

    def Index(self, params):
        # 16.3 index: StaticAnalyzer.Run("analyze_all", ...)
        return self.RunStep("index", params)

    def Graph(self, params):
        # 16.4 graph: GraphBuilder.Run("build_all", ...) + RelationshipExtractor
        res = self.RunStep("graph", params)
        if res[0] != 1:
            return res
        rel_got = self.GetEngine("relationship_extractor",
                                 "RelationshipExtractor")
        if rel_got[0] == 1:
            rel_params = dict(params)
            rel_params.setdefault("db_path", self.state["config"]["db_path"])
            try:
                rel_res = rel_got[1].Run("extract_all", rel_params)
            except Exception as exc:
                return (1, {"graph": res[1],
                            "relationships": {"error": str(exc)}}, None)
            return (1, {"graph": res[1],
                        "relationships": rel_res[1] if rel_res[0] == 1
                        else {"error": str(rel_res[2])}}, None)
        return res

    def Detect(self, params):
        # 16.5 detect: PatternEngine.Run("detect_violations", ...)
        return self.RunStep("detect", params)

    def Search(self, params):
        # 16.6 search: KnowledgeEngine.Run("search_similar", ...)
        return self.RunStep("search", params)

    def Repair(self, params):
        # 16.7 repair: FixEngine.Run("apply_fix", ...)
        return self.RunStep("repair", params)

    def Validate(self, params):
        # 16.8 validate: ValidationEngine.Run("validate_all", ...)
        return self.RunStep("validate", params)

    def Learn(self, params):
        # 16.9 learn: KnowledgeEngine.Run("learn", ...)
        return self.RunStep("learn", params)

    def RunFullCycle(self, params):
        # 16.1-16.10: run all 9 steps in sequence, then repeat-check
        steps = ["scan", "ingest", "index", "graph", "detect",
                 "search", "repair", "validate", "learn"]
        cycle = {}
        violations = 0
        for step in steps:
            res = self.RunStep(step, params)
            if res[0] == 1:
                cycle[step] = res[1]
                if step == "detect" and isinstance(res[1], dict):
                    violations = res[1].get("count",
                                            res[1].get("violations", 0))
            else:
                cycle[step] = {"error": str(res[2])}
        # 16.10 repeat: record cycle outcome as an observation
        conn = self.Connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO observations (observation_type, subject, "
                "evidence, confidence, created) VALUES (?,?,?,?,?)",
                ("change", "continuous_loop_cycle",
                 json.dumps(cycle), 50.0,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except sqlite3.Error:
            pass
        self.state["catalog"].append(cycle)
        return (1, {"cycle": cycle, "violations": violations}, None)

    def RunNCycles(self, params):
        n = self._p(params, "n", 1)
        results = []
        for i in range(n):
            res = self.RunFullCycle(params)
            if res[0] == 1:
                results.append(res[1])
        return (1, {"cycles": results, "count": len(results)}, None)

    def DetectAndFix(self, params):
        # detect -> search -> repair in one pass
        det = self.Detect(params)
        violations = 0
        if det[0] == 1 and isinstance(det[1], dict):
            violations = det[1].get("count", det[1].get("violations", 0))
        search = self.Search(params)
        fixes = []
        if search[0] == 1 and isinstance(search[1], dict):
            fixes = search[1].get("matches", search[1].get("results", []))
        repair = self.Repair(params)
        return (1, {
            "violations": violations,
            "fixes_found": len(fixes) if isinstance(fixes, list) else 0,
            "fixes": fixes,
            "repair": repair[1] if repair[0] == 1 else {"error": str(repair[2])},
        }, None)

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

