#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/CACASE The Clevere/main_entry_engine.py"
# date="2026-06-26" author="Cascade" session_id="twin-rewrite"
# context="Section 50: Main Entry -- 10 sub-sections"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="main_entry_engine.py" domain="twin_main" authority="MainEntryEngine"}
# [@SUMMARY]{summary="Main entry authority: initialize system, run pipeline, run single engine, get system status, shutdown system, list engines, get engine info, run health check, run full diagnostic, system report."}
# [@CLASS]{class="MainEntryEngine" domain="main_entry" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="initialize_system" type="command"}
# [@METHOD]{method="run_pipeline" type="command"}
# [@METHOD]{method="run_single_engine" type="command"}
# [@METHOD]{method="system_status" type="command"}
# [@METHOD]{method="shutdown_system" type="command"}
# [@METHOD]{method="list_engines" type="command"}
# [@METHOD]{method="engine_info" type="command"}
# [@METHOD]{method="health_check" type="command"}
# [@METHOD]{method="full_diagnostic" type="command"}
# [@METHOD]{method="system_report" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

import importlib
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_twin.db"

ENGINE_REGISTRY = [
    ("backup_engine", "BackupEngine"),
    ("sandbox_engine", "SandboxEngine"),
    ("knowledge_engine", "KnowledgeEngine"),
    ("knowledge_storage_engine", "KnowledgeStorageEngine"),
    ("graph_builder", "GraphBuilder"),
    ("ingestion_engine", "IngestionEngine"),
    ("file_split_engine", "FileSplitEngine"),
    ("class_split_engine", "ClassSplitEngine"),
    ("method_split_engine", "MethodSplitEngine"),
    ("static_analysis_engine", "StaticAnalysisEngine"),
    ("vbstyle_validator_engine", "VbstyleValidatorEngine"),
    ("refactor_engine", "RefactorEngine"),
    ("fix_engine", "FixEngine"),
    ("validation_engine", "ValidationEngine"),
    ("semantic_search_engine", "SemanticSearchEngine"),
    ("prediction_engine", "PredictionEngine"),
    ("fingerprint_engine", "FingerprintEngine"),
    ("version_snapshot_engine", "VersionSnapshotEngine"),
    ("reporting_engine", "ReportingEngine"),
    ("observation_engine", "ObservationEngine"),
    ("ai_memory_engine", "AiMemoryEngine"),
    ("confidence_engine", "ConfidenceEngine"),
    ("learning_engine", "LearningEngine"),
    ("experiment_engine", "ExperimentEngine"),
    ("pattern_detection_engine", "PatternDetectionEngine"),
    ("dependency_tracker_engine", "DependencyTrackerEngine"),
    ("impact_analysis_engine", "ImpactAnalysisEngine"),
    ("lifecycle_engine", "LifecycleEngine"),
    ("anomaly_detection_engine", "AnomalyDetectionEngine"),
    ("comparison_engine", "ComparisonEngine"),
    ("health_monitor_engine", "HealthMonitorEngine"),
    ("metrics_engine", "MetricsEngine"),
    ("traceability_engine", "TraceabilityEngine"),
    ("gap_analysis_engine", "GapAnalysisEngine"),
    ("regression_engine", "RegressionEngine"),
    ("root_cause_engine", "RootCauseEngine"),
    ("optimization_engine", "OptimizationEngine"),
    ("evolution_engine", "EvolutionEngine"),
    ("audit_trail_engine", "AuditTrailEngine"),
    ("knowledge_graph_engine", "KnowledgeGraphEngine"),
    ("context_engine", "ContextEngine"),
    ("intelligence_engine", "IntelligenceEngine"),
    ("orchestration_engine", "OrchestrationEngine"),
    ("auto_fix_pipeline_engine", "AutoFixPipelineEngine"),
    ("feedback_loop_engine", "FeedbackLoopEngine"),
    ("deduplication_engine", "DeduplicationEngine"),
    ("priority_engine", "PriorityEngine"),
    ("signal_engine", "SignalEngine"),
]


class MainEntryEngine:
    """Authority for system initialization and orchestration."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
            },
            "catalog": [],
            "results": [],
            "initialized": False,
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
        if command == "initialize_system":
            return self.InitializeSystem(params)
        elif command == "run_pipeline":
            return self.RunPipeline(params)
        elif command == "run_single_engine":
            return self.RunSingleEngine(params)
        elif command == "system_status":
            return self.SystemStatus(params)
        elif command == "shutdown_system":
            return self.ShutdownSystem(params)
        elif command == "list_engines":
            return self.ListEngines(params)
        elif command == "engine_info":
            return self.EngineInfo(params)
        elif command == "health_check":
            return self.HealthCheck(params)
        elif command == "full_diagnostic":
            return self.FullDiagnostic(params)
        elif command == "system_report":
            return self.SystemReport(params)
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
        return (1, self.state["db_conn"], None)

    def Now(self):
        return (1, datetime.now(timezone.utc).isoformat(), None)

    def InitializeSystem(self, params):
        loaded = 0
        failed = 0
        for mod_name, cls_name in ENGINE_REGISTRY:
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
                self.state["engines"][mod_name] = cls
                loaded += 1
            except Exception:
                failed += 1
        self.state["initialized"] = True
        return (1, {"initialized": True, "loaded": loaded,
                    "failed": failed, "total": len(ENGINE_REGISTRY),
                    "time": self.Now()[1]}, None)

    def RunPipeline(self, params):
        if not self.state["initialized"]:
            res = self.InitializeSystem(params)
            if res[0] == 0:
                return res
        results = {}
        for mod_name, cls_name in ENGINE_REGISTRY:
            try:
                cls = self.state["engines"].get(mod_name)
                if cls is None:
                    results[mod_name] = {"status": "not_loaded"}
                    continue
                engine = cls()
                res = engine.Run("read_state", {})
                results[mod_name] = {"status": "ok" if res[0] == 1 else "error"}
            except Exception as exc:
                results[mod_name] = {"status": "error", "error": str(exc)}
        return (1, {"pipeline_results": results,
                    "total": len(results),
                    "time": self.Now()[1]}, None)

    def RunSingleEngine(self, params):
        engine_name = self._p(params, "engine_name")
        command = self._p(params, "command", "read_state")
        if engine_name is None:
            return (0, None, ("MISSING_PARAM", "engine_name required", 0))
        if not self.state["initialized"]:
            self.InitializeSystem(params)
        cls = self.state["engines"].get(engine_name)
        if cls is None:
            return (0, None, ("ENGINE_NOT_FOUND", str(engine_name), 0))
        try:
            engine = cls()
            return engine.Run(command, params)
        except Exception as exc:
            return (0, None, ("ENGINE_ERROR", str(exc), 0))

    def SystemStatus(self, params):
        return (1, {"initialized": self.state["initialized"],
                    "loaded_engines": len(self.state["engines"]),
                    "total_registered": len(ENGINE_REGISTRY),
                    "db_path": self.state["config"]["db_path"],
                    "time": self.Now()[1]}, None)

    def ShutdownSystem(self, params):
        if self.state["db_conn"] is not None:
            self.state["db_conn"].close()
            self.state["db_conn"] = None
        self.state["engines"] = {}
        self.state["initialized"] = False
        return (1, {"shutdown": True, "time": self.Now()[1]}, None)

    def ListEngines(self, params):
        engines = [{"module": mod, "class": cls, "loaded": mod in self.state["engines"]}
                   for mod, cls in ENGINE_REGISTRY]
        return (1, {"engines": engines, "total": len(engines)}, None)

    def EngineInfo(self, params):
        engine_name = self._p(params, "engine_name")
        if engine_name is None:
            return (0, None, ("MISSING_PARAM", "engine_name required", 0))
        for mod, cls in ENGINE_REGISTRY:
            if mod == engine_name:
                return (1, {"module": mod, "class": cls,
                            "loaded": mod in self.state["engines"]}, None)
        return (0, None, ("ENGINE_NOT_FOUND", str(engine_name), 0))

    def HealthCheck(self, params):
        conn = self.Connect()[1]
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
        except sqlite3.Error as exc:
            return (0, None, ("DB_ERROR", str(exc), 0))
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cur.fetchone()[0]
        return (1, {"integrity": integrity, "tables": tables,
                    "loaded_engines": len(self.state["engines"]),
                    "initialized": self.state["initialized"],
                    "time": self.Now()[1]}, None)

    def FullDiagnostic(self, params):
        results = {}
        results["system_status"] = self.SystemStatus(params)[1]
        results["health_check"] = self.HealthCheck(params)[1]
        results["list_engines"] = self.ListEngines(params)[1]
        return (1, results, None)

    def SystemReport(self, params):
        results = {}
        results["system_status"] = self.SystemStatus(params)[1]
        results["health_check"] = self.HealthCheck(params)[1]
        results["list_engines"] = self.ListEngines(params)[1]
        results["generated"] = self.Now()[1]
        return (1, results, None)
