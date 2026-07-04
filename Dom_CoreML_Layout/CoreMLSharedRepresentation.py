#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLSharedRepresentation.py
#[@SUMMARY] Shared representation layer: all experts speak the same 40D language. Converts raw code, AST, features into a common intermediate representation that any expert can consume. Enables expert-to-expert communication.
#[@CLASS] CoreMLSharedRepresentation
#[@METHOD] encode, decode, compare, align, shared_space, list_representations
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import struct
import subprocess
import time
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
SHARED_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/shared_representation.sqlite"

FEATURE_KEYS = [
    "func_density", "class_density", "import_density", "if_density",
    "for_density", "while_density", "try_density", "except_density",
    "with_density", "comprehension_density", "decorator_density",
    "lambda_density", "async_density", "yield_density", "return_density",
    "assign_density", "augassign_density", "annassign_density",
    "raise_density", "assert_density", "global_density", "nonlocal_density",
    "pass_density", "break_density", "continue_density", "boolop_density",
    "binop_density", "unaryop_density", "ifexp_density", "dict_density",
    "set_density", "list_density", "tuple_density", "call_density",
    "attribute_density", "subscript_density", "compare_density",
    "constant_density", "name_density", "nesting",
]

EXPERT_TYPES = [
    {"id": "layout", "prefix": "", "description": "Base layout domain expert"},
    {"id": "python", "prefix": "py_", "description": "Python code classification expert"},
    {"id": "ast", "prefix": "ast_", "description": "AST layer expert"},
    {"id": "generated", "prefix": "gen_", "description": "Generated grammar expert"},
    {"id": "transform", "prefix": "transform_transform_", "description": "AST transformation expert"},
    {"id": "invariant", "prefix": "transform_invariant_", "description": "Safety invariant expert"},
    {"id": "curriculum", "prefix": "curriculum_", "description": "Curriculum teacher expert"},
    {"id": "rule", "prefix": "rule_", "description": "Generative rule expert"},
]

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]


class CoreMLSharedRepresentation:
    """Shared representation layer — the common language for all experts.

    Problem:
      84 expert weight files exist, but they can't cooperate because
      there's no shared language. A grammar expert outputs 10D, a transform
      expert outputs 10D, a rule expert outputs 10D — but these outputs
      mean different things. They can't talk to each other.

    Solution:
      Define a shared representation space:
        1. INPUT space (40D): All experts already share this — the feature vector.
        2. OUTPUT space (10D): Map each expert's output into a shared semantic space.
        3. INTERMEDIATE space: A common "understanding" vector that any expert
           can produce and any expert can consume.

    The shared representation has 3 layers:

    Layer A — Feature Vector (40D input):
      All experts already consume the same 40D feature vector.
      This IS the shared input language.

    Layer B — Semantic Output Vector (10D output):
      Each expert outputs 10D, but the meaning differs:
        - Layout expert: domain probabilities (vscode, browser, ...)
        - Transform expert: transformation IDs (add_function, add_class, ...)
        - Rule expert: rule IDs (function_definition, class_definition, ...)
        - Error expert: error type IDs (no_error, syntax_error, ...)

      We map these into a SHARED semantic space:
        [0] = structure_score    (how structured is this code?)
        [1] = complexity_score   (how complex?)
        [2] = safety_score       (how safe/reliable?)
        [3] = style_score        (how compliant with conventions?)
        [4] = domain_score       (which domain does this belong to?)
        [5] = error_risk_score   (how likely to have errors?)
        [6] = optimization_score (can this be optimized?)
        [7] = semantic_score     (how semantically rich?)
        [8] = grammar_score      (how grammatically correct?)
        [9] = confidence_score   (how confident is the ensemble?)

    Layer C — Expert Communication Protocol:
      When expert A produces output, it's converted to the shared semantic space.
      Expert B can consume expert A's output as additional context.
      This enables cooperation: grammar expert says "high structure" ->
      transform expert uses that to decide "safe to refactor".

    Registry:
      Every expert is registered with its type, domain, input/output mapping.
      The coordinator can look up which experts speak which "dialect" and
      translate between them.
    """

    SHARED_SEMANTIC_KEYS = [
        "structure", "complexity", "safety", "style", "domain",
        "error_risk", "optimization", "semantic_richness", "grammar", "confidence",
    ]

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "shared_db": SHARED_DB,
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
        if command == "register_expert":
            return self.cmdRegisterExpert(params)
        if command == "list_experts":
            return self.cmdListExperts(params)
        if command == "encode_output":
            return self.cmdEncodeOutput(params)
        if command == "decode_output":
            return self.cmdDecodeOutput(params)
        if command == "compare_experts":
            return self.cmdCompareExperts(params)
        if command == "shared_space":
            return self.cmdSharedSpace(params)
        if command == "align_experts":
            return self.cmdAlignExperts(params)
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
        import sqlite3
        conn = sqlite3.connect(self.state["config"]["shared_db"])
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS expert_registry (
                expert_id TEXT PRIMARY KEY,
                expert_type TEXT,
                domain TEXT,
                weights_path TEXT,
                output_mapping TEXT,
                input_dim INTEGER DEFAULT 40,
                output_dim INTEGER DEFAULT 10,
                registered_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS shared_space_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expert_id TEXT,
                input_hash TEXT,
                raw_output TEXT,
                semantic_output TEXT,
                timestamp REAL DEFAULT 0
            );
        """)
        conn.commit()
        conn.close()

    def discoverExperts(self):
        """Scan experts directory and register all weight files."""
        import sqlite3
        expertsDir = self.state["config"]["experts_dir"]
        if not os.path.exists(expertsDir):
            return []
        experts = []
        for fname in os.listdir(expertsDir):
            if not fname.endswith(".weights.bin"):
                continue
            expertId = fname.replace(".weights.bin", "")
            weightsPath = os.path.join(expertsDir, fname)
            expertType = "unknown"
            domain = "unknown"
            for etype in EXPERT_TYPES:
                prefix = etype["prefix"]
                if prefix and expertId.startswith(prefix):
                    expertType = etype["id"]
                    remainder = expertId[len(prefix):]
                    for d in DOMAINS:
                        if remainder == d or remainder.endswith("_" + d):
                            domain = d
                            break
                    break
            if expertType == "unknown":
                for d in DOMAINS:
                    if expertId == d:
                        expertType = "layout"
                        domain = d
                        break
            experts.append({
                "expert_id": expertId,
                "expert_type": expertType,
                "domain": domain,
                "weights_path": weightsPath,
            })
        return experts

    def outputToSemantic(self, rawOutput, expertType):
        """Map an expert's raw 10D output into shared semantic space.

        Different expert types have different output meanings.
        This function translates any expert's output into the common
        10D semantic space that all experts can understand.
        """
        if len(rawOutput) < OUTPUT_DIM:
            rawOutput = rawOutput + [0.0] * (OUTPUT_DIM - len(rawOutput))
        rawOutput = rawOutput[:OUTPUT_DIM]
        semantic = [0.0] * OUTPUT_DIM

        if expertType == "layout":
            maxVal = max(rawOutput) if rawOutput else 0
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[1] = maxVal
            semantic[4] = rawOutput.index(maxVal) if maxVal > 0 else 0
            semantic[9] = maxVal

        elif expertType == "python":
            maxVal = max(rawOutput) if rawOutput else 0
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[4] = rawOutput.index(maxVal) if maxVal > 0 else 0
            semantic[8] = maxVal
            semantic[9] = maxVal

        elif expertType == "ast":
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[1] = max(rawOutput) if rawOutput else 0
            semantic[7] = sum(rawOutput[:5]) / 5 if len(rawOutput) >= 5 else 0
            semantic[8] = max(rawOutput) if rawOutput else 0
            semantic[9] = max(rawOutput) if rawOutput else 0

        elif expertType == "generated":
            semantic[8] = max(rawOutput) if rawOutput else 0
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[9] = max(rawOutput) if rawOutput else 0

        elif expertType == "transform":
            maxIdx = rawOutput.index(max(rawOutput)) if rawOutput else 0
            maxVal = max(rawOutput) if rawOutput else 0
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
            semantic[3] = max(rawOutput) if rawOutput else 0
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[9] = max(rawOutput) if rawOutput else 0

        elif expertType == "rule":
            maxIdx = rawOutput.index(max(rawOutput)) if rawOutput else 0
            maxVal = max(rawOutput) if rawOutput else 0
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
            semantic[0] = sum(rawOutput) / len(rawOutput) if rawOutput else 0
            semantic[9] = max(rawOutput) if rawOutput else 0

        for i in range(OUTPUT_DIM):
            semantic[i] = round(max(0.0, min(1.0, semantic[i])), 4)

        return semantic

    def semanticToDescription(self, semantic):
        """Convert a semantic vector into a human-readable description."""
        descriptions = []
        for i, key in enumerate(self.SHARED_SEMANTIC_KEYS):
            val = semantic[i] if i < len(semantic) else 0
            if val > 0.6:
                descriptions.append(key + "=HIGH(" + str(round(val, 2)) + ")")
            elif val > 0.3:
                descriptions.append(key + "=MED(" + str(round(val, 2)) + ")")
            elif val > 0.1:
                descriptions.append(key + "=LOW(" + str(round(val, 2)) + ")")
        return descriptions

    def runInference(self, weightsPath, features):
        if not os.path.exists(weightsPath):
            return None
        statePath = os.path.join(self.state["config"]["experts_dir"], "..", "shared_inference.bin")
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

    def cmdRegisterExpert(self, params):
        import sqlite3
        expertId = self.p(params, "expert_id")
        expertType = self.p(params, "expert_type", "unknown")
        domain = self.p(params, "domain", "unknown")
        weightsPath = self.p(params, "weights_path", "")
        outputMapping = self.p(params, "output_mapping", "")
        if not expertId:
            return (0, None, ("PARAMS_ERROR", "expert_id required", 0))
        conn = sqlite3.connect(self.state["config"]["shared_db"])
        conn.execute(
            "INSERT OR REPLACE INTO expert_registry (expert_id, expert_type, domain, weights_path, output_mapping, registered_at) VALUES (?,?,?,?,?,?)",
            (expertId, expertType, domain, weightsPath, outputMapping, time.time())
        )
        conn.commit()
        conn.close()
        return (1, {"expert_id": expertId, "registered": True}, None)

    def cmdListExperts(self, params):
        import sqlite3
        autoDiscover = self.p(params, "discover", True)
        if autoDiscover:
            experts = self.discoverExperts()
            conn = sqlite3.connect(self.state["config"]["shared_db"])
            for e in experts:
                conn.execute(
                    "INSERT OR REPLACE INTO expert_registry (expert_id, expert_type, domain, weights_path, registered_at) VALUES (?,?,?,?,?)",
                    (e["expert_id"], e["expert_type"], e["domain"], e["weights_path"], time.time())
                )
            conn.commit()
            conn.close()
        conn = sqlite3.connect(self.state["config"]["shared_db"])
        rows = conn.execute(
            "SELECT expert_id, expert_type, domain, weights_path FROM expert_registry ORDER BY expert_type, domain"
        ).fetchall()
        conn.close()
        expertList = []
        for row in rows:
            expertList.append({
                "expert_id": row[0],
                "expert_type": row[1],
                "domain": row[2],
                "weights_path": row[3],
                "exists": os.path.exists(row[3]) if row[3] else False,
            })
        typeCounts = {}
        for e in expertList:
            t = e["expert_type"]
            typeCounts[t] = typeCounts.get(t, 0) + 1
        return (1, {
            "experts": expertList,
            "total": len(expertList),
            "type_counts": typeCounts,
        }, None)

    def cmdEncodeOutput(self, params):
        expertType = self.p(params, "expert_type", "layout")
        rawOutput = self.p(params, "raw_output", [])
        if not isinstance(rawOutput, list):
            return (0, None, ("PARAMS_ERROR", "raw_output must be list", 0))
        semantic = self.outputToSemantic(rawOutput, expertType)
        description = self.semanticToDescription(semantic)
        return (1, {
            "expert_type": expertType,
            "raw_output": [round(v, 4) for v in rawOutput],
            "semantic_output": semantic,
            "description": description,
        }, None)

    def cmdDecodeOutput(self, params):
        semantic = self.p(params, "semantic_output", [])
        if not isinstance(semantic, list):
            return (0, None, ("PARAMS_ERROR", "semantic_output must be list", 0))
        description = self.semanticToDescription(semantic)
        dominant = []
        for i, key in enumerate(self.SHARED_SEMANTIC_KEYS):
            if i < len(semantic) and semantic[i] > 0.5:
                dominant.append(key)
        return (1, {
            "semantic_output": semantic,
            "description": description,
            "dominant_dimensions": dominant,
        }, None)

    def cmdCompareExperts(self, params):
        features = self.p(params, "features")
        if not isinstance(features, list):
            return (0, None, ("PARAMS_ERROR", "features required", 0))
        expertIds = self.p(params, "expert_ids", [])
        if not expertIds:
            return (0, None, ("PARAMS_ERROR", "expert_ids required", 0))
        results = {}
        for expertId in expertIds:
            weightsPath = os.path.join(self.state["config"]["experts_dir"], expertId + ".weights.bin")
            rawOutput = self.runInference(weightsPath, features)
            if rawOutput is None:
                results[expertId] = {"error": "no weights or inference failed"}
                continue
            expertType = "unknown"
            for etype in EXPERT_TYPES:
                prefix = etype["prefix"]
                if prefix and expertId.startswith(prefix):
                    expertType = etype["id"]
                    break
            if expertType == "unknown":
                for d in DOMAINS:
                    if expertId == d:
                        expertType = "layout"
                        break
            semantic = self.outputToSemantic(rawOutput, expertType)
            results[expertId] = {
                "expert_type": expertType,
                "raw_output": [round(v, 4) for v in rawOutput],
                "semantic_output": semantic,
                "description": self.semanticToDescription(semantic),
            }
        return (1, {"comparison": results, "expert_count": len(results)}, None)

    def cmdSharedSpace(self, params):
        """Run a feature vector through ALL available experts and show the shared semantic space."""
        features = self.p(params, "features")
        if not isinstance(features, list):
            return (0, None, ("PARAMS_ERROR", "features required (40D list)", 0))
        experts = self.discoverExperts()
        semanticVectors = []
        rawVectors = []
        expertTypes = []
        for expert in experts:
            rawOutput = self.runInference(expert["weights_path"], features)
            if rawOutput is None:
                continue
            semantic = self.outputToSemantic(rawOutput, expert["expert_type"])
            semanticVectors.append(semantic)
            rawVectors.append(rawOutput)
            expertTypes.append(expert["expert_type"])
        if not semanticVectors:
            return (1, {"message": "No experts produced output", "experts_tried": len(experts)}, None)
        ensemble = [0.0] * OUTPUT_DIM
        for sv in semanticVectors:
            for i in range(OUTPUT_DIM):
                ensemble[i] += sv[i]
        for i in range(OUTPUT_DIM):
            ensemble[i] = round(ensemble[i] / len(semanticVectors), 4)
        description = self.semanticToDescription(ensemble)
        return (1, {
            "experts_consulted": len(semanticVectors),
            "ensemble_semantic": ensemble,
            "ensemble_description": description,
            "per_expert": [{"expert_type": et, "semantic": sv} for et, sv in zip(expertTypes, semanticVectors)],
        }, None)

    def cmdAlignExperts(self, params):
        """Auto-discover and register all experts in the shared representation DB."""
        import sqlite3
        experts = self.discoverExperts()
        conn = sqlite3.connect(self.state["config"]["shared_db"])
        registered = 0
        for e in experts:
            conn.execute(
                "INSERT OR REPLACE INTO expert_registry (expert_id, expert_type, domain, weights_path, registered_at) VALUES (?,?,?,?,?)",
                (e["expert_id"], e["expert_type"], e["domain"], e["weights_path"], time.time())
            )
            registered += 1
        conn.commit()
        conn.close()
        return (1, {
            "discovered": len(experts),
            "registered": registered,
            "experts": experts,
        }, None)

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "shared_semantic_keys": self.SHARED_SEMANTIC_KEYS,
            "expert_types": [e["id"] for e in EXPERT_TYPES],
            "feature_keys": FEATURE_KEYS,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
