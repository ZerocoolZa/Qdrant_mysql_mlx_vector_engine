#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLASTTransformer.py
#[@SUMMARY] Teaches models AST transformation rules: given code structure + transformation, predict the effect. Learns invariants, safe vs breaking transformations.
#[@CLASS] CoreMLASTTransformer
#[@METHOD] apply_transform, gen_transform_data, train_transform, train_all_transforms, classify_transform, list_transforms
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import random
import time
import subprocess
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_transform"
CODEBASE_ROOT = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]
DOMAIN_INDICES = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}

TRANSFORMATIONS = [
    {
        "id": 0,
        "name": "add_function",
        "description": "Add a new function definition to the AST",
        "safe": True,
        "effect": {"func_density": 0.1, "return_density": 0.08, "name_density": 0.05, "call_density": 0.03},
    },
    {
        "id": 1,
        "name": "add_class",
        "description": "Add a new class definition",
        "safe": True,
        "effect": {"class_density": 0.1, "attribute_density": 0.08, "init_density": 0.05},
    },
    {
        "id": 2,
        "name": "add_try_except",
        "description": "Wrap code in try/except block",
        "safe": True,
        "effect": {"try_density": 0.2, "except_density": 0.18, "nesting": 0.1, "raise_density": 0.05},
    },
    {
        "id": 3,
        "name": "add_decorator",
        "description": "Add a decorator to a function",
        "safe": True,
        "effect": {"decorator_density": 0.15},
    },
    {
        "id": 4,
        "name": "add_comprehension",
        "description": "Replace loop with list comprehension",
        "safe": True,
        "effect": {"comprehension_density": 0.2, "for_density": -0.1, "if_density": -0.05},
    },
    {
        "id": 5,
        "name": "add_async",
        "description": "Convert function to async def",
        "safe": True,
        "effect": {"async_density": 0.2, "await_density": 0.15, "yield_density": 0.05},
    },
    {
        "id": 6,
        "name": "add_type_hints",
        "description": "Add type annotations to function signatures",
        "safe": True,
        "effect": {"annotation_density": 0.15, "decorator_density": 0.05},
    },
    {
        "id": 7,
        "name": "flatten_nesting",
        "description": "Reduce nesting depth by extracting functions",
        "safe": True,
        "effect": {"nesting": -0.15, "func_density": 0.08, "call_density": 0.05},
    },
    {
        "id": 8,
        "name": "remove_error_handling",
        "description": "Remove try/except blocks — introduces fragility",
        "safe": False,
        "effect": {"try_density": -0.2, "except_density": -0.18, "raise_density": -0.1, "nesting": -0.08},
    },
    {
        "id": 9,
        "name": "introduce_bug",
        "description": "Introduce a subtle bug (wrong variable, missing return)",
        "safe": False,
        "effect": {"return_density": -0.1, "name_density": 0.05, "assign_density": 0.03},
    },
]

DOMAIN_PROFILES = {
    "vscode": {
        "func_density": 0.8, "class_density": 0.6, "import_density": 0.9,
        "if_density": 0.7, "for_density": 0.5, "try_density": 0.4,
        "decorator_density": 0.3, "lambda_density": 0.2, "comprehension_density": 0.4,
        "async_density": 0.1, "with_density": 0.3, "nesting": 0.6,
        "run_method": 1.0, "tuple3": 0.9, "self_state": 0.8, "bcl_header": 0.9,
        "no_print": 1.0, "no_self_underscore": 1.0, "config_import": 0.8,
        "return_density": 0.64, "assign_density": 0.5, "call_density": 0.56,
        "attribute_density": 0.48, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.09, "raise_density": 0.2, "except_density": 0.36,
        "await_density": 0.07, "yield_density": 0.05,
    },
    "browser": {
        "func_density": 0.6, "class_density": 0.7, "import_density": 0.7,
        "if_density": 0.6, "for_density": 0.6, "try_density": 0.3,
        "decorator_density": 0.1, "lambda_density": 0.3, "comprehension_density": 0.5,
        "async_density": 0.0, "with_density": 0.2, "nesting": 0.7,
        "run_method": 0.8, "tuple3": 0.7, "self_state": 0.7, "bcl_header": 0.7,
        "no_print": 0.9, "no_self_underscore": 0.9, "config_import": 0.6,
        "return_density": 0.48, "assign_density": 0.5, "call_density": 0.42,
        "attribute_density": 0.56, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.03, "raise_density": 0.15, "except_density": 0.27,
        "await_density": 0.0, "yield_density": 0.0,
    },
    "dashboard": {
        "func_density": 0.5, "class_density": 0.8, "import_density": 0.6,
        "if_density": 0.8, "for_density": 0.7, "try_density": 0.5,
        "decorator_density": 0.2, "lambda_density": 0.1, "comprehension_density": 0.3,
        "async_density": 0.0, "with_density": 0.4, "nesting": 0.8,
        "run_method": 0.7, "tuple3": 0.6, "self_state": 0.6, "bcl_header": 0.6,
        "no_print": 0.8, "no_self_underscore": 0.8, "config_import": 0.5,
        "return_density": 0.4, "assign_density": 0.5, "call_density": 0.35,
        "attribute_density": 0.64, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.06, "raise_density": 0.25, "except_density": 0.45,
        "await_density": 0.0, "yield_density": 0.0,
    },
    "mobile": {
        "func_density": 0.7, "class_density": 0.5, "import_density": 0.8,
        "if_density": 0.5, "for_density": 0.4, "try_density": 0.6,
        "decorator_density": 0.4, "lambda_density": 0.2, "comprehension_density": 0.3,
        "async_density": 0.3, "with_density": 0.3, "nesting": 0.5,
        "run_method": 0.6, "tuple3": 0.5, "self_state": 0.5, "bcl_header": 0.5,
        "no_print": 0.7, "no_self_underscore": 0.7, "config_import": 0.4,
        "return_density": 0.56, "assign_density": 0.5, "call_density": 0.49,
        "attribute_density": 0.4, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.12, "raise_density": 0.3, "except_density": 0.54,
        "await_density": 0.21, "yield_density": 0.15,
    },
    "tablet": {
        "func_density": 0.6, "class_density": 0.6, "import_density": 0.7,
        "if_density": 0.5, "for_density": 0.5, "try_density": 0.3,
        "decorator_density": 0.5, "lambda_density": 0.2, "comprehension_density": 0.4,
        "async_density": 0.0, "with_density": 0.2, "nesting": 0.6,
        "run_method": 0.5, "tuple3": 0.4, "self_state": 0.4, "bcl_header": 0.4,
        "no_print": 0.6, "no_self_underscore": 0.6, "config_import": 0.3,
        "return_density": 0.48, "assign_density": 0.5, "call_density": 0.42,
        "attribute_density": 0.48, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.15, "raise_density": 0.15, "except_density": 0.27,
        "await_density": 0.0, "yield_density": 0.0,
    },
}

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


class CoreMLASTTransformer:
    """AST transformation rule learner.

    Instead of classifying code, this teaches the model TRANSFORMATION RULES:
      - "If I add a function, func_density goes up, return_density goes up"
      - "If I remove try/except, the code becomes fragile (unsafe)"
      - "If I convert a loop to a comprehension, for_density goes down"

    Training format:
      Input: 40D = before transformation features
      Output: 10D = which transformation was applied (one-hot)

    The model learns to look at an AST's feature vector and recognize
    what transformation produced it. This is the first step toward
    learning transformation invariants.

    10 transformations:
      0: add_function (safe)
      1: add_class (safe)
      2: add_try_except (safe)
      3: add_decorator (safe)
      4: add_comprehension (safe)
      5: add_async (safe)
      6: add_type_hints (safe)
      7: flatten_nesting (safe)
      8: remove_error_handling (UNSAFE)
      9: introduce_bug (UNSAFE)

    The model learns to distinguish safe from breaking transformations
    by learning the structural signatures of each transformation type.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "codebase_root": CODEBASE_ROOT,
                "samples_per_domain": 200,
                "epochs": 300,
                "learning_rate": 0.01,
                "noise_level": 0.08,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()

    def Run(self, command, params=None):
        params = params or {}
        if command == "apply_transform":
            return self.cmdApplyTransform(params)
        if command == "gen_transform_data":
            return self.cmdGenTransformData(params)
        if command == "train_transform":
            return self.cmdTrainTransform(params)
        if command == "train_all_transforms":
            return self.cmdTrainAllTransforms(params)
        if command == "classify_transform":
            return self.cmdClassifyTransform(params)
        if command == "list_transforms":
            return self.cmdListTransforms(params)
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
        if not os.path.exists(TRAINING_DIR):
            os.makedirs(TRAINING_DIR, exist_ok=True)

    def clamp(self, value, lo=0.0, hi=1.0):
        return max(lo, min(hi, value))

    def addNoise(self, value, noiseLevel=None):
        if noiseLevel is None:
            noiseLevel = self.state["config"]["noise_level"]
        return self.clamp(value + random.gauss(0, noiseLevel))

    def profileToVector(self, profile):
        """Convert a domain profile to a 40D feature vector."""
        vector = []
        for key in FEATURE_KEYS:
            val = profile.get(key, 0.1)
            vector.append(self.addNoise(val))
        return vector[:INPUT_DIM]

    def applyTransformation(self, beforeVector, transformId):
        """Apply a transformation to a feature vector, returning after vector.

        The transformation modifies specific feature dimensions based on
        the transformation's effect map. This simulates how an AST
        transformation changes the structural shape of code.
        """
        transform = TRANSFORMATIONS[transformId]
        afterVector = list(beforeVector)
        for featureName, delta in transform["effect"].items():
            if featureName in FEATURE_KEYS:
                idx = FEATURE_KEYS.index(featureName)
                afterVector[idx] = self.clamp(afterVector[idx] + delta)
        for i in range(len(afterVector)):
            afterVector[i] = self.addNoise(afterVector[i], 0.03)
        return afterVector

    def makeTarget(self, transformId):
        """One-hot 10D target for transformation classification."""
        target = [0.0] * OUTPUT_DIM
        target[transformId] = 1.0
        return target

    def generateTransformData(self, samplesPerDomain=None):
        """Generate (before, after, transformation) training triples.

        For each sample:
          1. Pick a random domain profile
          2. Generate 'before' features from the profile
          3. Pick a random transformation
          4. Apply transformation to get 'after' features
          5. Training input = after features (the model sees the result)
          6. Training target = which transformation was applied

        The model learns: "given this AST shape, which transformation
        produced it?" — recognizing transformation signatures.
        """
        if samplesPerDomain is None:
            samplesPerDomain = self.state["config"]["samples_per_domain"]
        episodes = []
        sampleIdx = 0
        for domain in DOMAINS:
            profile = DOMAIN_PROFILES[domain]
            for _ in range(samplesPerDomain):
                beforeVector = self.profileToVector(profile)
                transformId = random.randint(0, len(TRANSFORMATIONS) - 1)
                afterVector = self.applyTransformation(beforeVector, transformId)
                target = self.makeTarget(transformId)
                episodes.append({
                    "episode": sampleIdx,
                    "num_nodes": 1,
                    "steps": [{
                        "state": afterVector,
                        "action": target,
                        "reward": 1.0 if TRANSFORMATIONS[transformId]["safe"] else 0.5,
                    }],
                })
                sampleIdx += 1
        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "samples": sampleIdx,
                "samples_per_domain": samplesPerDomain,
                "source": "ast_transformations",
                "transformations": len(TRANSFORMATIONS),
            },
        }

    def generateInvariantData(self, samplesPerDomain=None):
        """Generate safe vs unsafe classification data.

        Input: 40D = after transformation features
        Target: 10D = [safe_score, unsafe_score, ...rest zeros]

        The model learns: "is this transformation safe or breaking?"
        """
        if samplesPerDomain is None:
            samplesPerDomain = self.state["config"]["samples_per_domain"]
        episodes = []
        sampleIdx = 0
        for domain in DOMAINS:
            profile = DOMAIN_PROFILES[domain]
            for _ in range(samplesPerDomain):
                beforeVector = self.profileToVector(profile)
                transformId = random.randint(0, len(TRANSFORMATIONS) - 1)
                afterVector = self.applyTransformation(beforeVector, transformId)
                transform = TRANSFORMATIONS[transformId]
                target = [0.0] * OUTPUT_DIM
                if transform["safe"]:
                    target[0] = 1.0
                else:
                    target[1] = 1.0
                episodes.append({
                    "episode": sampleIdx,
                    "num_nodes": 1,
                    "steps": [{
                        "state": afterVector,
                        "action": target,
                        "reward": 1.0 if transform["safe"] else 0.0,
                    }],
                })
                sampleIdx += 1
        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "samples": sampleIdx,
                "source": "ast_invariant_checking",
            },
        }

    def cmdApplyTransform(self, params):
        """Apply a transformation to a feature vector and show the result."""
        try:
            domain = self.p(params, "domain", "vscode")
            transformId = int(self.p(params, "transform_id", 0))
            if domain not in DOMAIN_PROFILES:
                return (0, None, ("PARAMS_ERROR", "Unknown domain: " + domain, 0))
            if transformId < 0 or transformId >= len(TRANSFORMATIONS):
                return (0, None, ("PARAMS_ERROR", "transform_id out of range", 0))
            profile = DOMAIN_PROFILES[domain]
            beforeVector = self.profileToVector(profile)
            afterVector = self.applyTransformation(beforeVector, transformId)
            transform = TRANSFORMATIONS[transformId]
            deltas = []
            for i, key in enumerate(FEATURE_KEYS):
                if abs(afterVector[i] - beforeVector[i]) > 0.01:
                    deltas.append({
                        "feature": key,
                        "before": round(beforeVector[i], 4),
                        "after": round(afterVector[i], 4),
                        "delta": round(afterVector[i] - beforeVector[i], 4),
                    })
            return (1, {
                "domain": domain,
                "transformation": transform["name"],
                "safe": transform["safe"],
                "description": transform["description"],
                "deltas": deltas,
                "before_features": [round(v, 4) for v in beforeVector[:10]],
                "after_features": [round(v, 4) for v in afterVector[:10]],
            }, None)
        except Exception as e:
            return (0, None, ("APPLY_ERROR", str(e), 0))

    def cmdGenTransformData(self, params):
        """Generate transformation training data."""
        try:
            samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
            mode = self.p(params, "mode", "transform")
            if mode == "invariant":
                data = self.generateInvariantData(samples)
            else:
                data = self.generateTransformData(samples)
            outputPath = os.path.join(TRAINING_DIR, "transform_" + mode + "_training.json")
            with open(outputPath, "w") as f:
                json.dump(data, f)
            return (1, {
                "mode": mode,
                "path": outputPath,
                "samples": data["config"]["samples"],
                "transformations": len(TRANSFORMATIONS),
            }, None)
        except Exception as e:
            return (0, None, ("GEN_ERROR", str(e), 0))

    def cmdTrainTransform(self, params):
        """Train a transformation recognition expert."""
        try:
            domain = self.p(params, "domain", "vscode")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            lr = float(self.p(params, "learning_rate", self.state["config"]["learning_rate"]))
            samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
            mode = self.p(params, "mode", "transform")
            if mode == "invariant":
                data = self.generateInvariantData(samples)
            else:
                data = self.generateTransformData(samples)
            outputPath = os.path.join(TRAINING_DIR, "transform_" + mode + "_" + domain + "_training.json")
            with open(outputPath, "w") as f:
                json.dump(data, f)
            weightsOut = os.path.join(EXPERTS_DIR, "transform_" + mode + "_" + domain + ".weights.bin")
            initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if not os.path.exists(initWeights):
                initWeights = None
            coretotch = self.state["config"]["coretotch_bin"]
            cmdArgs = [coretotch, "train", outputPath, weightsOut, str(epochs), str(lr)]
            if initWeights:
                cmdArgs.append(initWeights)
            proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
            output = proc.stderr + proc.stdout
            lossLines = [l for l in output.split("\n") if "Loss:" in l]
            firstLoss = lossLines[0].strip() if lossLines else ""
            lastLoss = lossLines[-1].strip() if lossLines else ""
            return (1, {
                "domain": domain,
                "mode": mode,
                "training_file": outputPath,
                "output_weights": weightsOut,
                "epochs": epochs,
                "samples": data["config"]["samples"],
                "first_loss": firstLoss,
                "last_loss": lastLoss,
                "success": proc.returncode == 0,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ERROR", str(e), 0))

    def cmdTrainAllTransforms(self, params):
        """Train transform recognition + invariant checking for all 5 domains."""
        try:
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
            results = []
            for mode in ["transform", "invariant"]:
                for domain in DOMAINS:
                    ok, data, err = self.cmdTrainTransform({
                        "domain": domain, "epochs": epochs, "samples": samples, "mode": mode
                    })
                    if ok:
                        results.append({
                            "mode": data["mode"],
                            "domain": data["domain"],
                            "first_loss": data["first_loss"],
                            "last_loss": data["last_loss"],
                            "success": data["success"],
                        })
                    else:
                        results.append({
                            "mode": mode, "domain": domain,
                            "error": str(err), "success": False,
                        })
            successCount = sum(1 for r in results if r.get("success"))
            return (1, {
                "trained": successCount,
                "total": len(results),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ALL_ERROR", str(e), 0))

    def cmdClassifyTransform(self, params):
        """Classify which transformation was applied to a feature vector."""
        try:
            domain = self.p(params, "domain", "vscode")
            transformId = int(self.p(params, "transform_id", 0))
            profile = DOMAIN_PROFILES[domain]
            beforeVector = self.profileToVector(profile)
            afterVector = self.applyTransformation(beforeVector, transformId)
            import struct
            statePath = os.path.join(TRAINING_DIR, "classify_transform.bin")
            with open(statePath, "wb") as f:
                for v in afterVector:
                    f.write(struct.pack("<f", v))
            coretotch = self.state["config"]["coretotch_bin"]
            results = {}
            for d in DOMAINS:
                wpath = os.path.join(EXPERTS_DIR, "transform_transform_" + d + ".weights.bin")
                if not os.path.exists(wpath):
                    continue
                proc = subprocess.run(
                    [coretotch, "select", wpath, statePath],
                    capture_output=True, text=True
                )
                for line in (proc.stderr + proc.stdout).split("\n"):
                    if "output:" in line:
                        vals = [float(x) for x in line.split("output:")[1].strip().split()]
                        results[d] = vals
                        break
            actualTransform = TRANSFORMATIONS[transformId]["name"]
            predictions = {}
            for d, vals in results.items():
                maxIdx = vals.index(max(vals))
                predictedTransform = TRANSFORMATIONS[maxIdx]["name"]
                predictions[d] = {
                    "predicted": predictedTransform,
                    "actual": actualTransform,
                    "correct": predictedTransform == actualTransform,
                    "confidence": round(max(vals), 4),
                    "scores": [round(v, 4) for v in vals],
                }
            return (1, {
                "domain": domain,
                "actual_transform": actualTransform,
                "safe": TRANSFORMATIONS[transformId]["safe"],
                "predictions": predictions,
            }, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def cmdListTransforms(self, params):
        """List all available AST transformations."""
        try:
            transforms = []
            for t in TRANSFORMATIONS:
                effects = []
                for feat, delta in t["effect"].items():
                    effects.append(feat + ": " + ("+" if delta > 0 else "") + str(delta))
                transforms.append({
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "safe": t["safe"],
                    "effects": effects,
                })
            return (1, {"transformations": transforms, "total": len(transforms)}, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "transformations": len(TRANSFORMATIONS),
            "domains": DOMAINS,
            "feature_keys": len(FEATURE_KEYS),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
