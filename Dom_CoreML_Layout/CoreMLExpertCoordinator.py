#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLExpertCoordinator.py
#[@SUMMARY] Coordinates multiple experts on a single task. Routes input to relevant experts, collects outputs, translates to shared semantic space, fuses into ensemble answer. This is the glue that turns 84 experts into a coherent system.
#[@CLASS] CoreMLExpertCoordinator
#[@METHOD] route, consult, ensemble, coordinate, list_strategies, show_pipeline
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import struct
import subprocess
import time
import sqlite3
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
COORDINATION_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coordination.sqlite"

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]

TASK_TYPES = [
    {
        "id": "classify_domain",
        "name": "Classify Domain",
        "description": "Which domain does this code belong to?",
        "experts_needed": ["layout", "python", "generated"],
        "fusion_strategy": "voting",
    },
    {
        "id": "detect_errors",
        "name": "Detect Errors",
        "description": "Does this code have errors? What type?",
        "experts_needed": ["rule", "generated", "curriculum"],
        "fusion_strategy": "max_confidence",
    },
    {
        "id": "analyze_structure",
        "name": "Analyze Structure",
        "description": "What is the AST structure of this code?",
        "experts_needed": ["ast", "generated", "rule"],
        "fusion_strategy": "weighted_average",
    },
    {
        "id": "check_safety",
        "name": "Check Safety",
        "description": "Is this code safe? Are transformations safe?",
        "experts_needed": ["invariant", "transform", "rule"],
        "fusion_strategy": "min_risk",
    },
    {
        "id": "suggest_optimization",
        "name": "Suggest Optimization",
        "description": "Can this code be optimized? How?",
        "experts_needed": ["rule", "ast", "transform"],
        "fusion_strategy": "weighted_average",
    },
    {
        "id": "verify_style",
        "name": "Verify Style",
        "description": "Does this code follow VBStyle conventions?",
        "experts_needed": ["curriculum", "rule", "generated"],
        "fusion_strategy": "voting",
    },
    {
        "id": "full_analysis",
        "name": "Full Analysis",
        "description": "Complete analysis: domain, structure, safety, style, errors, optimization",
        "experts_needed": ["layout", "python", "ast", "generated", "transform", "invariant", "curriculum", "rule"],
        "fusion_strategy": "ensemble_all",
    },
]

EXPERT_TYPE_WEIGHTS = {
    "layout": 0.8,
    "python": 0.9,
    "ast": 0.85,
    "generated": 0.7,
    "transform": 0.85,
    "invariant": 0.9,
    "curriculum": 0.75,
    "rule": 0.8,
}

SHARED_SEMANTIC_KEYS = [
    "structure", "complexity", "safety", "style", "domain",
    "error_risk", "optimization", "semantic_richness", "grammar", "confidence",
]


class CoreMLExpertCoordinator:
    """Coordinates multiple experts on a single task.

    This is the orchestration layer that turns 84 independent experts
    into a coherent AI system.

    Pipeline:
      1. ROUTE: Determine which task type this is and which experts are needed.
      2. CONSULT: Run inference on each needed expert with the same input.
      3. TRANSLATE: Convert each expert's raw output into shared semantic space.
      4. FUSE: Combine semantic outputs using the task's fusion strategy.
      5. DECIDE: Produce final answer with confidence and explanation.

    Fusion Strategies:
      voting:           Each expert votes, majority wins.
      max_confidence:   Use the expert with highest confidence.
      weighted_average: Weight each expert by its type weight.
      min_risk:         For safety tasks, use the most conservative answer.
      ensemble_all:     All experts contribute, weighted by type and confidence.

    Coordination Log:
      Every coordination event is logged with:
        - task type, experts consulted, raw outputs, semantic outputs,
        - fusion result, final answer, confidence, timestamp
      This creates an audit trail of how the system reached its conclusions.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "coordination_db": COORDINATION_DB,
                "max_experts_per_task": 10,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.initDb()

    def Run(self, command, params=None):
        params = params or {}
        if command == "list_strategies":
            return self.cmdListStrategies(params)
        if command == "route":
            return self.cmdRoute(params)
        if command == "consult":
            return self.cmdConsult(params)
        if command == "ensemble":
            return self.cmdEnsemble(params)
        if command == "coordinate":
            return self.cmdCoordinate(params)
        if command == "show_pipeline":
            return self.cmdShowPipeline(params)
        if command == "coordination_log":
            return self.cmdCoordinationLog(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def initDb(self):
        conn = sqlite3.connect(self.state["config"]["coordination_db"])
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS coordination_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT,
                task_description TEXT,
                experts_consulted TEXT,
                fusion_strategy TEXT,
                final_answer TEXT,
                confidence REAL,
                semantic_ensemble TEXT,
                timestamp REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS expert_performance (
                expert_id TEXT,
                task_type TEXT,
                consultations INTEGER DEFAULT 0,
                agreements INTEGER DEFAULT 0,
                avg_confidence REAL DEFAULT 0,
                PRIMARY KEY (expert_id, task_type)
            );
        """)
        conn.commit()
        conn.close()

    def discoverExpertsByType(self, expertType):
        """Find all expert weight files matching a type."""
        expertsDir = self.state["config"]["experts_dir"]
        if not os.path.exists(expertsDir):
            return []
        results = []
        typePrefixes = {
            "layout": "",
            "python": "py_",
            "ast": "ast_",
            "generated": "gen_",
            "transform": "transform_transform_",
            "invariant": "transform_invariant_",
            "curriculum": "curriculum_",
            "rule": "rule_",
        }
        prefix = typePrefixes.get(expertType, "")
        for fname in os.listdir(expertsDir):
            if not fname.endswith(".weights.bin"):
                continue
            expertId = fname.replace(".weights.bin", "")
            if expertType == "layout":
                if expertId in DOMAINS:
                    results.append({
                        "expert_id": expertId,
                        "expert_type": "layout",
                        "domain": expertId,
                        "weights_path": os.path.join(expertsDir, fname),
                    })
            elif prefix and expertId.startswith(prefix):
                remainder = expertId[len(prefix):]
                domain = "unknown"
                for d in DOMAINS:
                    if remainder == d or remainder.endswith("_" + d):
                        domain = d
                        break
                results.append({
                    "expert_id": expertId,
                    "expert_type": expertType,
                    "domain": domain,
                    "weights_path": os.path.join(expertsDir, fname),
                })
        return results

    def runInference(self, weightsPath, features):
        if not os.path.exists(weightsPath):
            return None
        statePath = os.path.join(self.state["config"]["experts_dir"], "..", "coord_inference.bin")
        with open(statePath, "wb") as f:
            for v in features:
                f.write(struct.pack("<f", v))
        proc = subprocess.run(
            [self.state["config"]["coretotch_bin"], "select", weightsPath, statePath],
            capture_output=True, text=True
        )
        for line in (proc.stderr + proc.stdout).split("\n"):
            if "output:" in line:
                vals = [float(x) for x in line.split("output:")[1].strip().split()]
                return vals
        return None

    def outputToSemantic(self, rawOutput, expertType):
        """Translate raw expert output to shared 10D semantic space."""
        if len(rawOutput) < OUTPUT_DIM:
            rawOutput = rawOutput + [0.0] * (OUTPUT_DIM - len(rawOutput))
        rawOutput = rawOutput[:OUTPUT_DIM]
        semantic = [0.0] * OUTPUT_DIM
        maxVal = max(rawOutput) if rawOutput else 0
        maxIdx = rawOutput.index(maxVal) if maxVal > 0 else 0
        avgVal = sum(rawOutput) / len(rawOutput) if rawOutput else 0

        if expertType in ("layout", "python"):
            semantic[4] = maxIdx
            semantic[9] = maxVal
            semantic[0] = avgVal
        elif expertType == "ast":
            semantic[0] = avgVal
            semantic[1] = maxVal
            semantic[7] = sum(rawOutput[:5]) / 5
            semantic[8] = maxVal
            semantic[9] = maxVal
        elif expertType == "generated":
            semantic[8] = maxVal
            semantic[0] = avgVal
            semantic[9] = maxVal
        elif expertType == "transform":
            if maxIdx < 8:
                semantic[2] = maxVal
            else:
                semantic[5] = maxVal
            semantic[0] = maxVal
            semantic[9] = maxVal
        elif expertType == "invariant":
            if rawOutput[0] > rawOutput[1]:
                semantic[2] = rawOutput[0]
            else:
                semantic[5] = rawOutput[1]
            semantic[9] = max(rawOutput[0], rawOutput[1])
        elif expertType == "curriculum":
            semantic[3] = maxVal
            semantic[0] = avgVal
            semantic[9] = maxVal
        elif expertType == "rule":
            if maxIdx < 3:
                semantic[8] = maxVal
            elif maxIdx < 6:
                semantic[0] = maxVal
            elif maxIdx < 11:
                semantic[7] = maxVal
            else:
                semantic[6] = maxVal
            semantic[9] = maxVal
        else:
            semantic[0] = avgVal
            semantic[9] = maxVal

        for i in range(OUTPUT_DIM):
            semantic[i] = round(max(0.0, min(1.0, semantic[i])), 4)
        return semantic

    def fuseOutputs(self, semanticOutputs, expertTypes, strategy):
        """Fuse multiple expert semantic outputs into one ensemble answer."""
        if not semanticOutputs:
            return [0.0] * OUTPUT_DIM
        ensemble = [0.0] * OUTPUT_DIM

        if strategy == "voting":
            for i in range(OUTPUT_DIM):
                votes = [1.0 if so[i] > 0.5 else 0.0 for so in semanticOutputs]
                ensemble[i] = round(sum(votes) / len(votes), 4)

        elif strategy == "max_confidence":
            bestIdx = 0
            bestConf = 0
            for idx, so in enumerate(semanticOutputs):
                if so[9] > bestConf:
                    bestConf = so[9]
                    bestIdx = idx
            ensemble = list(semanticOutputs[bestIdx])

        elif strategy == "weighted_average":
            totalWeight = 0
            for idx, so in enumerate(semanticOutputs):
                etype = expertTypes[idx] if idx < len(expertTypes) else "unknown"
                weight = EXPERT_TYPE_WEIGHTS.get(etype, 0.5)
                for i in range(OUTPUT_DIM):
                    ensemble[i] += so[i] * weight
                totalWeight += weight
            if totalWeight > 0:
                for i in range(OUTPUT_DIM):
                    ensemble[i] = round(ensemble[i] / totalWeight, 4)

        elif strategy == "min_risk":
            for i in range(OUTPUT_DIM):
                if i == 2:
                    ensemble[i] = round(min(so[i] for so in semanticOutputs), 4)
                elif i == 5:
                    ensemble[i] = round(max(so[i] for so in semanticOutputs), 4)
                else:
                    ensemble[i] = round(sum(so[i] for so in semanticOutputs) / len(semanticOutputs), 4)

        elif strategy == "ensemble_all":
            totalWeight = 0
            for idx, so in enumerate(semanticOutputs):
                etype = expertTypes[idx] if idx < len(expertTypes) else "unknown"
                weight = EXPERT_TYPE_WEIGHTS.get(etype, 0.5) * so[9]
                for i in range(OUTPUT_DIM):
                    ensemble[i] += so[i] * weight
                totalWeight += weight
            if totalWeight > 0:
                for i in range(OUTPUT_DIM):
                    ensemble[i] = round(ensemble[i] / totalWeight, 4)

        else:
            for i in range(OUTPUT_DIM):
                ensemble[i] = round(sum(so[i] for so in semanticOutputs) / len(semanticOutputs), 4)

        return ensemble

    def semanticToDescription(self, semantic):
        descriptions = []
        for i, key in enumerate(SHARED_SEMANTIC_KEYS):
            val = semantic[i] if i < len(semantic) else 0
            if val > 0.6:
                descriptions.append(key + "=HIGH(" + str(round(val, 2)) + ")")
            elif val > 0.3:
                descriptions.append(key + "=MED(" + str(round(val, 2)) + ")")
            elif val > 0.1:
                descriptions.append(key + "=LOW(" + str(round(val, 2)) + ")")
        return descriptions

    def routeTask(self, taskDescription):
        """Determine which task type and experts are needed based on task description."""
        taskLower = taskDescription.lower()
        bestMatch = None
        bestScore = 0
        for task in TASK_TYPES:
            score = 0
            keywords = task["id"].split("_") + task["name"].lower().split()
            for kw in keywords:
                if kw in taskLower:
                    score += 1
            if score > bestScore:
                bestScore = score
                bestMatch = task
        if bestMatch is None:
            bestMatch = TASK_TYPES[-1]
        return bestMatch

    def cmdListStrategies(self, params):
        return (1, {
            "task_types": [{"id": t["id"], "name": t["name"], "description": t["description"],
                            "experts_needed": t["experts_needed"], "fusion_strategy": t["fusion_strategy"]}
                           for t in TASK_TYPES],
            "fusion_strategies": ["voting", "max_confidence", "weighted_average", "min_risk", "ensemble_all"],
            "expert_type_weights": EXPERT_TYPE_WEIGHTS,
            "total_task_types": len(TASK_TYPES),
        }, None)

    def cmdRoute(self, params):
        taskDesc = self.p(params, "task_description", "")
        if not taskDesc:
            return (0, None, ("PARAMS_ERROR", "task_description required", 0))
        task = self.routeTask(taskDesc)
        expertLists = {}
        for etype in task["experts_needed"]:
            experts = self.discoverExpertsByType(etype)
            expertLists[etype] = len(experts)
        return (1, {
            "task_description": taskDesc,
            "routed_task": task["id"],
            "task_name": task["name"],
            "experts_needed": task["experts_needed"],
            "fusion_strategy": task["fusion_strategy"],
            "experts_available": expertLists,
        }, None)

    def cmdConsult(self, params):
        """Run a feature vector through a specific set of experts."""
        features = self.p(params, "features")
        expertTypes = self.p(params, "expert_types", ["layout"])
        if not isinstance(features, list):
            return (0, None, ("PARAMS_ERROR", "features required", 0))
        results = []
        for etype in expertTypes:
            experts = self.discoverExpertsByType(etype)
            for expert in experts:
                rawOutput = self.runInference(expert["weights_path"], features)
                if rawOutput is None:
                    continue
                semantic = self.outputToSemantic(rawOutput, etype)
                results.append({
                    "expert_id": expert["expert_id"],
                    "expert_type": etype,
                    "domain": expert["domain"],
                    "raw_output": [round(v, 4) for v in rawOutput],
                    "semantic_output": semantic,
                    "confidence": semantic[9],
                })
        return (1, {
            "experts_consulted": len(results),
            "results": results,
        }, None)

    def cmdEnsemble(self, params):
        """Fuse multiple expert outputs into ensemble answer."""
        semanticOutputs = self.p(params, "semantic_outputs", [])
        expertTypes = self.p(params, "expert_types", [])
        strategy = self.p(params, "strategy", "weighted_average")
        if not semanticOutputs:
            return (0, None, ("PARAMS_ERROR", "semantic_outputs required", 0))
        ensemble = self.fuseOutputs(semanticOutputs, expertTypes, strategy)
        description = self.semanticToDescription(ensemble)
        return (1, {
            "strategy": strategy,
            "ensemble_semantic": ensemble,
            "ensemble_description": description,
            "experts_fused": len(semanticOutputs),
        }, None)

    def cmdCoordinate(self, params):
        """Full coordination: route -> consult -> translate -> fuse -> decide."""
        try:
            features = self.p(params, "features")
            taskDesc = self.p(params, "task_description", "full analysis")
            if not isinstance(features, list):
                return (0, None, ("PARAMS_ERROR", "features required (40D list)", 0))
            task = self.routeTask(taskDesc)
            allResults = []
            for etype in task["experts_needed"]:
                experts = self.discoverExpertsByType(etype)
                for expert in experts:
                    rawOutput = self.runInference(expert["weights_path"], features)
                    if rawOutput is None:
                        continue
                    semantic = self.outputToSemantic(rawOutput, etype)
                    allResults.append({
                        "expert_id": expert["expert_id"],
                        "expert_type": etype,
                        "domain": expert["domain"],
                        "raw_output": [round(v, 4) for v in rawOutput],
                        "semantic_output": semantic,
                        "confidence": semantic[9],
                    })
            if not allResults:
                return (1, {
                    "task": task["id"],
                    "message": "No experts available for this task",
                    "experts_found": 0,
                }, None)
            semanticOutputs = [r["semantic_output"] for r in allResults]
            expertTypes = [r["expert_type"] for r in allResults]
            ensemble = self.fuseOutputs(semanticOutputs, expertTypes, task["fusion_strategy"])
            description = self.semanticToDescription(ensemble)
            confidence = ensemble[9]
            maxRawIdx = 0
            maxRawVal = 0
            for r in allResults:
                if r["confidence"] > maxRawVal:
                    maxRawVal = r["confidence"]
                    maxRawIdx = r["expert_id"]
            conn = sqlite3.connect(self.state["config"]["coordination_db"])
            conn.execute(
                "INSERT INTO coordination_log (task_type, task_description, experts_consulted, fusion_strategy, final_answer, confidence, semantic_ensemble, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (task["id"], taskDesc, ",".join(r["expert_id"] for r in allResults),
                 task["fusion_strategy"], str(description), confidence, json.dumps(ensemble), time.time())
            )
            conn.commit()
            conn.close()
            return (1, {
                "task": task["id"],
                "task_name": task["name"],
                "fusion_strategy": task["fusion_strategy"],
                "experts_consulted": len(allResults),
                "expert_details": [{"expert_id": r["expert_id"], "expert_type": r["expert_type"],
                                    "domain": r["domain"], "confidence": r["confidence"]}
                                   for r in allResults],
                "ensemble_semantic": ensemble,
                "ensemble_description": description,
                "confidence": confidence,
                "top_expert": maxRawIdx,
            }, None)
        except Exception as e:
            return (0, None, ("COORD_ERROR", str(e), 0))

    def cmdShowPipeline(self, params):
        """Show the coordination pipeline for a task."""
        taskDesc = self.p(params, "task_description", "full analysis")
        task = self.routeTask(taskDesc)
        pipeline = []
        for step, etype in enumerate(task["experts_needed"]):
            experts = self.discoverExpertsByType(etype)
            pipeline.append({
                "step": step + 1,
                "expert_type": etype,
                "available_experts": len(experts),
                "expert_ids": [e["expert_id"] for e in experts[:5]],
                "weight": EXPERT_TYPE_WEIGHTS.get(etype, 0.5),
            })
        return (1, {
            "task": task["id"],
            "task_name": task["name"],
            "fusion_strategy": task["fusion_strategy"],
            "pipeline": pipeline,
            "total_steps": len(pipeline),
        }, None)

    def cmdCoordinationLog(self, params):
        limit = int(self.p(params, "limit", 20))
        conn = sqlite3.connect(self.state["config"]["coordination_db"])
        rows = conn.execute(
            "SELECT task_type, task_description, experts_consulted, fusion_strategy, final_answer, confidence, timestamp FROM coordination_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        logs = []
        for row in rows:
            logs.append({
                "task_type": row[0],
                "task_description": row[1],
                "experts_consulted": row[2],
                "fusion_strategy": row[3],
                "final_answer": row[4],
                "confidence": round(row[5], 4) if row[5] else 0,
                "timestamp": row[6],
            })
        return (1, {"logs": logs, "total": len(logs)}, None)

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "task_types": len(TASK_TYPES),
            "fusion_strategies": ["voting", "max_confidence", "weighted_average", "min_risk", "ensemble_all"],
            "expert_type_weights": EXPERT_TYPE_WEIGHTS,
            "shared_semantic_keys": SHARED_SEMANTIC_KEYS,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
