#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLOrchestrator.py
#[@SUMMARY] Unified AI runtime OS: task input -> detect domain -> route -> load backpack -> C inference -> update score -> result
#[@CLASS] CoreMLOrchestrator
#[@METHOD] execute, execute_ensemble, status, pipeline
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import sys
import time
import json
import subprocess
from CoreMLRouter import CoreMLRouter
from CoreMLModelDB import CoreMLModelDB
from CoreMLBackpack import CoreMLBackpack
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_db.sqlite"
BACKPACK_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/backpacks"
TEMP_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/tmp_runtime"


class CoreMLOrchestrator:
    """Unified AI runtime OS.

    Single execution interface:
      task_input -> detect domain -> route best model -> load backpack
      -> extract weights -> C inference -> update score -> return result

    This is the orchestration layer that ties together:
      - CoreMLRouter (domain detection + scoring + ranking)
      - CoreMLModelDB (model storage as BLOB)
      - CoreMLBackpack (self-contained expert format)
      - coretotch.c (C inference engine)

    One call. Full pipeline. No manual steps.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": DB_PATH,
                "coretotch_bin": CORETOTCH_BIN,
                "backpack_dir": BACKPACK_DIR,
                "temp_dir": TEMP_DIR,
                "max_hot": 2,
            },
            "router": None,
            "modelDB": None,
            "backpack": None,
            "pipeline_log": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()
        self.initComponents()

    def Run(self, command, params=None):
        params = params or {}
        if command == "execute":
            return self.cmdExecute(params)
        if command == "execute_ensemble":
            return self.cmdExecuteEnsemble(params)
        if command == "status":
            return self.cmdStatus(params)
        if command == "pipeline":
            return self.cmdPipeline(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def ensureDirs(self):
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR, exist_ok=True)

    def initComponents(self):
        self.state["router"] = CoreMLRouter()
        self.state["modelDB"] = CoreMLModelDB()
        self.state["backpack"] = CoreMLBackpack()

    def cmdExecute(self, params):
        """Full pipeline: task -> route -> load -> infer -> score -> result."""
        try:
            taskInput = self.p(params, "task_input", "")
            stateInput = self.p(params, "state_input", None)
            if not taskInput:
                return (0, None, ("PARAMS_ERROR", "task_input required", 0))
            pipelineSteps = []
            t0 = time.time()

            # Step 1: Detect domain + route
            router = self.state["router"]
            ok, routeData, routeErr = router.Run("auto_route", {"task_input": taskInput})
            if not ok:
                return (0, None, routeErr)
            domain = routeData["detected_domain"]
            modelName = routeData["selected_model"]
            modelVersion = routeData["selected_version"]
            pipelineSteps.append({
                "step": 1, "name": "detect+route",
                "domain": domain, "model": modelName,
                "confidence": routeData["detection_confidence"],
                "time_ms": round((time.time() - t0) * 1000, 1),
            })

            # Step 2: Load backpack from DB
            t1 = time.time()
            modelDB = self.state["modelDB"]
            ok, loadData, loadErr = modelDB.Run("load", {
                "name": modelName,
                "version": modelVersion,
                "output_path": os.path.join(TEMP_DIR, modelName + ".weights.bin"),
            })
            if not ok:
                return (0, None, loadErr)
            weightsPath = loadData["output_path"]
            pipelineSteps.append({
                "step": 2, "name": "load_from_db",
                "model": modelName, "version": loadData["version"],
                "blob_size": loadData["blob_size"],
                "time_ms": round((time.time() - t1) * 1000, 1),
            })

            # Step 3: Prepare state vector
            t2 = time.time()
            if stateInput is None:
                statePath = os.path.join(TEMP_DIR, "default_state.bin")
                if not os.path.exists(statePath):
                    import struct
                    with open(statePath, "wb") as f:
                        for i in range(INPUT_DIM):
                            f.write(struct.pack("<f", 0.5))
                stateInput = statePath
            pipelineSteps.append({
                "step": 3, "name": "prepare_state",
                "state_path": stateInput,
                "time_ms": round((time.time() - t2) * 1000, 1),
            })

            # Step 4: C inference
            t3 = time.time()
            coretotch = self.state["config"]["coretotch_bin"]
            if not os.path.exists(coretotch):
                return (0, None, ("CORETOTCH_NOT_FOUND", coretotch, 0))
            cmdArgs = [coretotch, "select", weightsPath, stateInput]
            proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=10)
            cOutput = proc.stderr if proc.stderr else proc.stdout
            inferenceMs = round((time.time() - t3) * 1000, 1)
            pipelineSteps.append({
                "step": 4, "name": "c_inference",
                "command": "select",
                "output": cOutput.strip()[:200] if cOutput else "",
                "exit_code": proc.returncode,
                "time_ms": inferenceMs,
            })

            # Step 5: Update score (feedback)
            t4 = time.time()
            success = proc.returncode == 0
            ok, scoreData, scoreErr = router.Run("update_score", {
                "model_name": modelName,
                "version": modelVersion,
                "success": success,
                "latency_ms": inferenceMs,
            })
            pipelineSteps.append({
                "step": 5, "name": "update_score",
                "success": success,
                "new_score": scoreData.get("new_score", 0.0) if ok else 0.0,
                "time_ms": round((time.time() - t4) * 1000, 1),
            })

            totalTime = round((time.time() - t0) * 1000, 1)
            return (1, {
                "task_input": taskInput,
                "domain": domain,
                "model": modelName,
                "version": modelVersion,
                "inference_ms": inferenceMs,
                "total_ms": totalTime,
                "success": success,
                "c_output": cOutput.strip()[:300] if cOutput else "",
                "pipeline": pipelineSteps,
                "ram_kb": 90,
            }, None)
        except Exception as e:
            return (0, None, ("EXECUTE_ERROR", str(e), 0))

    def cmdExecuteEnsemble(self, params):
        """Execute ensemble: load multiple models, average outputs in C."""
        try:
            taskInput = self.p(params, "task_input", "")
            expertNames = self.p(params, "experts", [])
            stateInput = self.p(params, "state_input", None)
            if not taskInput or not expertNames:
                return (0, None, ("PARAMS_ERROR", "task_input and experts list required", 0))
            pipelineSteps = []
            t0 = time.time()

            # Step 1: Detect domain
            router = self.state["router"]
            ok, routeData, _ = router.Run("auto_route", {"task_input": taskInput})
            domain = routeData["detected_domain"] if ok else "unknown"
            pipelineSteps.append({
                "step": 1, "name": "detect",
                "domain": domain,
                "time_ms": round((time.time() - t0) * 1000, 1),
            })

            # Step 2: Load all expert weights from DB
            t1 = time.time()
            modelDB = self.state["modelDB"]
            weightsPaths = []
            for name in expertNames:
                ok, loadData, _ = modelDB.Run("load", {
                    "name": name,
                    "output_path": os.path.join(TEMP_DIR, name + ".weights.bin"),
                })
                if ok:
                    weightsPaths.append(loadData["output_path"])
            if not weightsPaths:
                return (0, None, ("NO_WEIGHTS", "Could not load any expert weights", 0))
            pipelineSteps.append({
                "step": 2, "name": "load_ensemble",
                "experts_loaded": len(weightsPaths),
                "time_ms": round((time.time() - t1) * 1000, 1),
            })

            # Step 3: Prepare state
            if stateInput is None:
                stateInput = os.path.join(TEMP_DIR, "default_state.bin")
                if not os.path.exists(stateInput):
                    import struct
                    with open(stateInput, "wb") as f:
                        for i in range(INPUT_DIM):
                            f.write(struct.pack("<f", 0.5))

            # Step 4: C ensemble inference
            t3 = time.time()
            coretotch = self.state["config"]["coretotch_bin"]
            cmdArgs = [coretotch, "ensemble"] + weightsPaths + [stateInput]
            proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=10)
            cOutput = proc.stderr if proc.stderr else proc.stdout
            inferenceMs = round((time.time() - t3) * 1000, 1)
            pipelineSteps.append({
                "step": 3, "name": "c_ensemble",
                "experts": len(weightsPaths),
                "output": cOutput.strip()[:200] if cOutput else "",
                "exit_code": proc.returncode,
                "time_ms": inferenceMs,
            })

            totalTime = round((time.time() - t0) * 1000, 1)
            return (1, {
                "task_input": taskInput,
                "domain": domain,
                "experts": expertNames,
                "experts_loaded": len(weightsPaths),
                "inference_ms": inferenceMs,
                "total_ms": totalTime,
                "success": proc.returncode == 0,
                "c_output": cOutput.strip()[:300] if cOutput else "",
                "pipeline": pipelineSteps,
                "ram_kb": len(weightsPaths) * 90,
            }, None)
        except Exception as e:
            return (0, None, ("ENSEMBLE_ERROR", str(e), 0))

    def cmdStatus(self, params):
        """Get full system status — DB, router, cache, backpacks."""
        try:
            modelDB = self.state["modelDB"]
            router = self.state["router"]
            backpack = self.state["backpack"]

            okDb, dbStats, _ = modelDB.Run("stats", {})
            okHot, hotStats, _ = modelDB.Run("hot_stats", {})
            okBp, bpList, _ = backpack.Run("list_backpacks", {})

            return (1, {
                "database": {
                    "models": dbStats.get("total_models", 0),
                    "routes": dbStats.get("total_routes", 0),
                    "db_size_kb": dbStats.get("db_size_kb", 0),
                    "hot_cache": dbStats.get("hot_cache_slots", 0),
                    "counters": dbStats.get("counters", {}),
                } if okDb else {},
                "router": {
                    "hot_models": hotStats.get("hot_count", 0),
                    "max_hot": hotStats.get("max_hot", 0),
                    "ram_kb": hotStats.get("ram_kb", 0),
                    "hit_rate": hotStats.get("hit_rate", 0),
                } if okHot else {},
                "backpacks": {
                    "total": bpList.get("total", 0),
                    "list": bpList.get("backpacks", []),
                } if okBp else {},
                "coretotch": {
                    "binary": self.state["config"]["coretotch_bin"],
                    "exists": os.path.exists(self.state["config"]["coretotch_bin"]),
                },
            }, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def cmdPipeline(self, params):
        """Show the full pipeline definition."""
        try:
            return (1, {
                "pipeline": [
                    {"step": 1, "name": "detect_domain", "component": "CoreMLRouter", "input": "task_text", "output": "domain"},
                    {"step": 2, "name": "route_model", "component": "CoreMLRouter", "input": "domain", "output": "model_name+version"},
                    {"step": 3, "name": "load_weights", "component": "CoreMLModelDB", "input": "model_name", "output": "weights_blob"},
                    {"step": 4, "name": "c_inference", "component": "coretotch.c", "input": "weights+state", "output": "prediction"},
                    {"step": 5, "name": "update_score", "component": "CoreMLRouter", "input": "success+latency", "output": "new_score"},
                ],
                "components": [
                    {"name": "CoreMLRouter", "role": "domain detection + scoring + ranking"},
                    {"name": "CoreMLModelDB", "role": "model storage as BLOB in SQLite"},
                    {"name": "CoreMLBackpack", "role": "self-contained expert format"},
                    {"name": "coretotch.c", "role": "C inference engine (train, infer, select, ensemble, hotcache)"},
                    {"name": "CoreMLHotCache", "role": "LRU hot cache for loaded experts"},
                    {"name": "CoreMLOrchestrator", "role": "unified execution interface (this)"},
                ],
                "interface_contract": {
                    "input_dim": INPUT_DIM,
                    "hidden_dim": HIDDEN_DIM,
                    "output_dim": OUTPUT_DIM,
                    "layers": "40->128->128->10",
                    "activation": "relu",
                    "weight_params": 23050,
                    "weight_bytes": 92200,
                    "backpack_size": "~92 KB",
                    "ram_per_expert": "90 KB",
                },
            }, None)
        except Exception as e:
            return (0, None, ("PIPELINE_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "components_initialized": {
                "router": self.state["router"] is not None,
                "modelDB": self.state["modelDB"] is not None,
                "backpack": self.state["backpack"] is not None,
            },
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
