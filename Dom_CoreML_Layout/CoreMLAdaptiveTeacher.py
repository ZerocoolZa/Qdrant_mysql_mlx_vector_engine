#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLAdaptiveTeacher.py
#[@SUMMARY] Adaptive teacher with feedback loop: fail -> diagnose -> simplify -> retrain -> retest -> advance. Retries failed question types with easier variations until mastery.
#[@CLASS] CoreMLAdaptiveTeacher
#[@METHOD] teach_rule, teach_all, diagnose_failures, generate_focused, retry_until_mastered, track_progress
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import random
import time
import struct
import subprocess
import sqlite3
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

SURVIVOR_DB = "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/db_survivors.sqlite"

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_adaptive"
PROGRESS_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/adaptive_mastery.sqlite"

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]

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

DOMAIN_PROFILES = {
    "vscode": {"func_density": 0.8, "class_density": 0.6, "import_density": 0.9, "if_density": 0.7, "for_density": 0.5, "try_density": 0.4, "decorator_density": 0.3, "lambda_density": 0.2, "comprehension_density": 0.4, "async_density": 0.1, "with_density": 0.3, "nesting": 0.6, "return_density": 0.64, "assign_density": 0.5, "call_density": 0.56, "attribute_density": 0.48, "name_density": 0.8, "constant_density": 0.6, "annassign_density": 0.09, "raise_density": 0.2, "except_density": 0.36, "yield_density": 0.05},
    "browser": {"func_density": 0.6, "class_density": 0.7, "import_density": 0.7, "if_density": 0.6, "for_density": 0.6, "try_density": 0.3, "decorator_density": 0.1, "lambda_density": 0.3, "comprehension_density": 0.5, "async_density": 0.0, "with_density": 0.2, "nesting": 0.7, "return_density": 0.48, "assign_density": 0.5, "call_density": 0.42, "attribute_density": 0.56, "name_density": 0.8, "constant_density": 0.6, "annassign_density": 0.03, "raise_density": 0.15, "except_density": 0.27, "yield_density": 0.0},
    "dashboard": {"func_density": 0.5, "class_density": 0.8, "import_density": 0.6, "if_density": 0.8, "for_density": 0.7, "try_density": 0.5, "decorator_density": 0.2, "lambda_density": 0.1, "comprehension_density": 0.3, "async_density": 0.0, "with_density": 0.4, "nesting": 0.8, "return_density": 0.4, "assign_density": 0.5, "call_density": 0.35, "attribute_density": 0.64, "name_density": 0.8, "constant_density": 0.6, "annassign_density": 0.06, "raise_density": 0.25, "except_density": 0.45, "yield_density": 0.0},
    "mobile": {"func_density": 0.7, "class_density": 0.5, "import_density": 0.8, "if_density": 0.5, "for_density": 0.4, "try_density": 0.6, "decorator_density": 0.4, "lambda_density": 0.2, "comprehension_density": 0.3, "async_density": 0.3, "with_density": 0.3, "nesting": 0.5, "return_density": 0.56, "assign_density": 0.5, "call_density": 0.49, "attribute_density": 0.4, "name_density": 0.8, "constant_density": 0.6, "annassign_density": 0.12, "raise_density": 0.3, "except_density": 0.54, "yield_density": 0.15},
    "tablet": {"func_density": 0.6, "class_density": 0.6, "import_density": 0.7, "if_density": 0.5, "for_density": 0.5, "try_density": 0.3, "decorator_density": 0.5, "lambda_density": 0.2, "comprehension_density": 0.4, "async_density": 0.0, "with_density": 0.2, "nesting": 0.6, "return_density": 0.48, "assign_density": 0.5, "call_density": 0.42, "attribute_density": 0.48, "name_density": 0.8, "constant_density": 0.6, "annassign_density": 0.15, "raise_density": 0.15, "except_density": 0.27, "yield_density": 0.0},
}

RULES = [
    {"id": 0, "name": "function_definition", "category": "grammar", "feature_idx": 0, "feature_name": "func_density", "difficulty": 1, "prerequisites": [], "output_idx": 0},
    {"id": 1, "name": "class_definition", "category": "grammar", "feature_idx": 1, "feature_name": "class_density", "difficulty": 1, "prerequisites": [0], "output_idx": 1},
    {"id": 2, "name": "control_flow_branching", "category": "grammar", "feature_idx": 3, "feature_name": "if_density", "difficulty": 1, "prerequisites": [0], "output_idx": 2},
    {"id": 3, "name": "loop_iteration", "category": "grammar", "feature_idx": 4, "feature_name": "for_density", "difficulty": 2, "prerequisites": [2], "output_idx": 3},
    {"id": 4, "name": "comprehension", "category": "grammar", "feature_idx": 9, "feature_name": "comprehension_density", "difficulty": 2, "prerequisites": [3], "output_idx": 4},
    {"id": 5, "name": "exception_handling", "category": "grammar", "feature_idx": 6, "feature_name": "try_density", "difficulty": 2, "prerequisites": [2], "output_idx": 5},
    {"id": 6, "name": "scope_and_naming", "category": "semantic", "feature_idx": 39, "feature_name": "nesting", "difficulty": 3, "prerequisites": [0, 1], "output_idx": 6},
    {"id": 7, "name": "decorators", "category": "grammar", "feature_idx": 10, "feature_name": "decorator_density", "difficulty": 3, "prerequisites": [0, 6], "output_idx": 7},
    {"id": 8, "name": "async_await", "category": "semantic", "feature_idx": 12, "feature_name": "async_density", "difficulty": 4, "prerequisites": [0, 6], "output_idx": 8},
    {"id": 9, "name": "type_annotations", "category": "semantic", "feature_idx": 17, "feature_name": "annassign_density", "difficulty": 3, "prerequisites": [0, 1], "output_idx": 9},
    {"id": 10, "name": "context_managers", "category": "grammar", "feature_idx": 8, "feature_name": "with_density", "difficulty": 3, "prerequisites": [5], "output_idx": 0},
    {"id": 11, "name": "generators", "category": "semantic", "feature_idx": 13, "feature_name": "yield_density", "difficulty": 4, "prerequisites": [3, 6], "output_idx": 1},
    {"id": 12, "name": "inheritance", "category": "semantic", "feature_idx": 1, "feature_name": "class_density", "difficulty": 4, "prerequisites": [1, 6], "output_idx": 2},
    {"id": 13, "name": "metaprogramming", "category": "semantic", "feature_idx": 10, "feature_name": "decorator_density", "difficulty": 5, "prerequisites": [7, 12, 9], "output_idx": 3},
    {"id": 14, "name": "optimization_refactor", "category": "optimization", "feature_idx": 39, "feature_name": "nesting", "difficulty": 5, "prerequisites": [4, 6, 11], "output_idx": 4},
]

QUESTION_TYPES = ["recognition", "discrimination", "applicability", "transformation", "diagnosis"]
MASTERY_THRESHOLD = 0.8


class CoreMLAdaptiveTeacher:
    """Adaptive teacher with feedback loop.

    Pipeline:
      1. Train rule with initial data (all 5 question types)
      2. Test each question type separately
      3. Diagnose: which types failed below threshold?
      4. Generate FOCUSED data for failed types:
         - Easier: larger signal delta, less noise
         - More examples of the confusing case
      5. Retrain incrementally (from existing weights)
      6. Re-test only failed types
      7. Repeat up to maxRetries
      8. Mastered only when ALL types pass
      9. Advance only when prerequisites mastered
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "progress_db": PROGRESS_DB,
                "initial_epochs": 500,
                "retry_epochs": 300,
                "initial_samples": 400,
                "retry_samples": 250,
                "max_retries": 5,
                "mastery_threshold": MASTERY_THRESHOLD,
                "test_per_type": 20,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()
        self.initDb()

    def Run(self, command, params=None):
        params = params or {}
        if command == "teach_rule":
            return self.cmdTeachRule(params)
        if command == "teach_all":
            return self.cmdTeachAll(params)
        if command == "diagnose":
            return self.cmdDiagnose(params)
        if command == "progress":
            return self.cmdProgress(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        if command == "teach_rule_db":
            return self.cmdTeachRuleDb(params)
        if command == "teach_all_db":
            return self.cmdTeachAllDb(params)
        if command == "db_status":
            return self.cmdDbStatus(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def ensureDirs(self):
        if not os.path.exists(TRAINING_DIR):
            os.makedirs(TRAINING_DIR, exist_ok=True)

    def initDb(self):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS adaptive_mastery (
                rule_id INTEGER PRIMARY KEY,
                rule_name TEXT,
                difficulty INTEGER,
                mastery_score REAL DEFAULT 0.0,
                is_mastered INTEGER DEFAULT 0,
                retries INTEGER DEFAULT 0,
                question_scores TEXT DEFAULT '{}',
                trained_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS adaptive_retry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                retry_num INTEGER,
                failed_types TEXT,
                focused_types TEXT,
                accuracy_before REAL,
                accuracy_after REAL,
                mastered INTEGER DEFAULT 0,
                timestamp REAL DEFAULT 0
            );
        """)
        for rule in RULES:
            conn.execute(
                "INSERT OR IGNORE INTO adaptive_mastery (rule_id, rule_name, difficulty) VALUES (?,?,?)",
                (rule["id"], rule["name"], rule["difficulty"])
            )
        conn.commit()
        conn.close()

    def clamp(self, v, lo=0.0, hi=1.0):
        return max(lo, min(hi, v))

    def profileToVector(self, profile, noiseLevel=0.05):
        vector = []
        for key in FEATURE_KEYS:
            val = profile.get(key, 0.1)
            vector.append(self.clamp(val + random.gauss(0, noiseLevel)))
        return vector[:INPUT_DIM]

    def makeTarget(self, index):
        target = [0.0] * OUTPUT_DIM
        target[index] = 1.0
        return target

    def getRuleById(self, ruleId):
        for rule in RULES:
            if rule["id"] == ruleId:
                return rule
        return None

    def prerequisitesMastered(self, ruleId):
        rule = self.getRuleById(ruleId)
        if not rule or not rule["prerequisites"]:
            return True
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        for prereqId in rule["prerequisites"]:
            row = conn.execute("SELECT is_mastered FROM adaptive_mastery WHERE rule_id=?", (prereqId,)).fetchone()
            if not row or row[0] == 0:
                conn.close()
                return False
        conn.close()
        return True

    SECONDARY_FEATURES = {
        3: {"primary": 4, "secondary_up": {4: 0.3}, "secondary_down": {9: -0.2}},
        4: {"primary": 9, "secondary_up": {9: 0.5}, "secondary_down": {4: -0.3, 14: -0.2}},
        5: {"primary": 6, "secondary_up": {6: 0.4, 7: 0.3}, "secondary_down": {6: -0.3, 7: -0.2}},
        6: {"primary": 39, "secondary_up": {39: 0.4, 0: 0.2, 1: 0.2}, "secondary_down": {39: -0.3, 0: -0.1}},
        7: {"primary": 10, "secondary_up": {10: 0.5, 0: 0.2}, "secondary_down": {10: -0.3, 0: -0.1}},
        8: {"primary": 12, "secondary_up": {12: 0.7, 0: 0.3, 14: 0.3, 33: 0.2}, "secondary_down": {12: -0.5, 0: -0.2}},
        9: {"primary": 17, "secondary_up": {17: 0.6, 0: 0.2, 1: 0.2}, "secondary_down": {17: -0.4, 0: -0.1}},
        10: {"primary": 8, "secondary_up": {8: 0.6, 7: 0.3}, "secondary_down": {8: -0.4, 6: -0.4, 7: -0.3}},
        11: {"primary": 13, "secondary_up": {13: 0.5, 4: 0.2, 14: 0.2}, "secondary_down": {13: -0.3, 4: -0.1}},
        12: {"primary": 1, "secondary_up": {1: 0.4, 39: 0.2, 0: 0.2}, "secondary_down": {1: -0.3, 0: -0.1}},
        13: {"primary": 10, "secondary_up": {10: 0.5, 1: 0.3, 39: 0.2}, "secondary_down": {10: -0.3, 1: -0.2}},
        14: {"primary": 39, "secondary_up": {39: 0.4, 9: 0.2, 4: 0.2}, "secondary_down": {39: -0.3, 9: -0.1}},
    }

    def createLesson(self, ruleId, domain, questionType, noiseLevel=None, deltaScale=None):
        rule = self.getRuleById(ruleId)
        if rule is None:
            return None
        profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["vscode"])
        if noiseLevel is None:
            noiseLevel = {1: 0.02, 2: 0.05, 3: 0.08, 4: 0.12, 5: 0.18}.get(rule["difficulty"], 0.08)
        if deltaScale is None:
            deltaScale = {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.5, 5: 0.3}.get(rule["difficulty"], 0.5)
        baseVector = self.profileToVector(profile, noiseLevel)
        secondary = self.SECONDARY_FEATURES.get(ruleId, {})
        secUp = secondary.get("secondary_up", {})
        secDown = secondary.get("secondary_down", {})

        outIdx = rule.get("output_idx", rule["id"] % OUTPUT_DIM)
        allEligible = [r for r in RULES if r["difficulty"] <= rule["difficulty"] and r.get("output_idx", r["id"] % OUTPUT_DIM) < OUTPUT_DIM]
        sameSlotRules = [r for r in allEligible if r.get("output_idx", r["id"] % OUTPUT_DIM) == outIdx]
        eligibleRules = sameSlotRules if len(sameSlotRules) > 1 else allEligible

        if questionType == "recognition":
            usesRule = random.random() > 0.4
            features = list(baseVector)
            if usesRule:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.5 * deltaScale)
                for secIdx, secVal in secUp.items():
                    features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
            else:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] - 0.35 * deltaScale)
                for secIdx, secVal in secDown.items():
                    features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
            expected = outIdx if usesRule else min(outIdx + 1, OUTPUT_DIM - 1)
            if expected == outIdx:
                expected = (outIdx + 1) % OUTPUT_DIM

        elif questionType == "discrimination":
            features = list(baseVector)
            if len(sameSlotRules) <= 1:
                isThisRule = random.random() > 0.5
                if isThisRule:
                    features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.5 * deltaScale)
                    for secIdx, secVal in secUp.items():
                        features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
                    expected = outIdx
                else:
                    distractor = random.choice([r for r in allEligible if r.get("output_idx", r["id"] % OUTPUT_DIM) != outIdx])
                    features[distractor["feature_idx"]] = self.clamp(features[distractor["feature_idx"]] + 0.4 * deltaScale)
                    domSecondary = self.SECONDARY_FEATURES.get(distractor["id"], {})
                    for secIdx, secVal in domSecondary.get("secondary_up", {}).items():
                        features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
                    expected = distractor.get("output_idx", distractor["id"] % OUTPUT_DIM)
            else:
                dominantRule = random.choice(eligibleRules)
                domOutIdx = dominantRule.get("output_idx", dominantRule["id"] % OUTPUT_DIM)
                features[dominantRule["feature_idx"]] = self.clamp(features[dominantRule["feature_idx"]] + 0.4 * deltaScale)
                domSecondary = self.SECONDARY_FEATURES.get(dominantRule["id"], {})
                for secIdx, secVal in domSecondary.get("secondary_up", {}).items():
                    features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
                expected = domOutIdx

        elif questionType == "applicability":
            applicable = random.random() > 0.3
            features = list(baseVector)
            if applicable:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.35 * deltaScale)
                for secIdx, secVal in secUp.items():
                    features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
            else:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] - 0.2 * deltaScale)
            expected = outIdx if applicable else min(outIdx + 1, OUTPUT_DIM - 1)
            if expected == outIdx:
                expected = (outIdx + 1) % OUTPUT_DIM

        elif questionType == "transformation":
            features = list(baseVector)
            features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.45 * deltaScale)
            for secIdx, secVal in secUp.items():
                features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
            expected = outIdx

        else:
            missingRule = random.choice(eligibleRules)
            missOutIdx = missingRule.get("output_idx", missingRule["id"] % OUTPUT_DIM)
            features = list(baseVector)
            features[missingRule["feature_idx"]] = self.clamp(0.05)
            missSecondary = self.SECONDARY_FEATURES.get(missingRule["id"], {})
            for secIdx, secVal in missSecondary.get("secondary_down", {}).items():
                features[secIdx] = self.clamp(features[secIdx] + secVal * deltaScale)
            expected = missOutIdx

        target = self.makeTarget(expected)
        return {"state": features, "action": target, "reward": 1.0}

    def generateTrainingData(self, ruleId, domain, questionTypes=None, samples=None, noiseLevel=None, deltaScale=None):
        if questionTypes is None:
            questionTypes = QUESTION_TYPES
        if samples is None:
            samples = self.state["config"]["initial_samples"]
        episodes = []
        sampleIdx = 0
        domainsIter = [domain] if domain else DOMAINS
        for domain_ in domainsIter:
            for _ in range(samples):
                qt = random.choice(questionTypes)
                lesson = self.createLesson(ruleId, domain_, qt, noiseLevel, deltaScale)
                if lesson is None:
                    continue
                episodes.append({"episode": sampleIdx, "num_nodes": 1, "steps": [lesson]})
                sampleIdx += 1
        return {"episodes": episodes, "config": {"input_dim": INPUT_DIM, "output_dim": OUTPUT_DIM, "samples": sampleIdx}}

    def runInference(self, weightsPath, features):
        if not os.path.exists(weightsPath):
            return None
        statePath = os.path.join(TRAINING_DIR, "adaptive_inference.bin")
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

    def testQuestionType(self, ruleId, domain, questionType, weightsPath, count=None):
        if count is None:
            count = self.state["config"]["test_per_type"]
        correct = 0
        total = 0
        for _ in range(count):
            lesson = self.createLesson(ruleId, domain, questionType)
            if lesson is None:
                continue
            output = self.runInference(weightsPath, lesson["state"])
            if output is None:
                continue
            total += 1
            if output.index(max(output)) == lesson["action"].index(1.0):
                correct += 1
        return {"correct": correct, "total": total, "accuracy": round(correct / total, 4) if total > 0 else 0}

    def testAllTypes(self, ruleId, domain, weightsPath):
        results = {}
        for qt in QUESTION_TYPES:
            results[qt] = self.testQuestionType(ruleId, domain, qt, weightsPath)
        return results

    def diagnoseFailures(self, typeResults, threshold=None, difficulty=None):
        if threshold is None:
            if difficulty is not None and difficulty >= 5:
                threshold = 0.6
            elif difficulty is not None and difficulty >= 4:
                threshold = 0.65
            elif difficulty is not None and difficulty >= 3:
                threshold = 0.7
            else:
                threshold = self.state["config"]["mastery_threshold"]
        failed = []
        passed = []
        for qt, result in typeResults.items():
            if result["accuracy"] < threshold:
                failed.append(qt)
            else:
                passed.append(qt)
        return {"failed": failed, "passed": passed}

    def trainRule(self, ruleId, domain, epochs=None, samples=None, questionTypes=None, noiseLevel=None, deltaScale=None, initWeights=None):
        if epochs is None:
            epochs = self.state["config"]["initial_epochs"]
        if samples is None:
            samples = self.state["config"]["initial_samples"]
        rule = self.getRuleById(ruleId)
        if rule is None:
            return (0, None, ("NOT_FOUND", "Rule not found", 0))
        data = self.generateTrainingData(ruleId, domain, questionTypes, samples, noiseLevel, deltaScale)
        trainingPath = os.path.join(TRAINING_DIR, "adaptive_rule_" + str(ruleId) + "_" + domain + ".json")
        with open(trainingPath, "w") as f:
            json.dump(data, f)
        weightsOut = os.path.join(EXPERTS_DIR, "adaptive_rule_" + str(ruleId) + "_" + domain + ".weights.bin")
        if initWeights is None:
            baseWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if os.path.exists(baseWeights):
                initWeights = baseWeights
        cmdArgs = [self.state["config"]["coretotch_bin"], "train", trainingPath, weightsOut, str(epochs), str(0.01)]
        if initWeights and os.path.exists(initWeights):
            cmdArgs.append(initWeights)
        proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
        output = proc.stderr + proc.stdout
        lossLines = [l for l in output.split("\n") if "Loss:" in l]
        firstLoss = lossLines[0].strip() if lossLines else ""
        lastLoss = lossLines[-1].strip() if lossLines else ""
        return (1, {"weights": weightsOut, "first_loss": firstLoss, "last_loss": lastLoss, "samples": data["config"]["samples"]}, None)

    def updateMastery(self, ruleId, typeResults, retries):
        rule = self.getRuleById(ruleId)
        if rule is None:
            return
        totalCorrect = sum(r["correct"] for r in typeResults.values())
        totalTotal = sum(r["total"] for r in typeResults.values())
        overall = totalCorrect / totalTotal if totalTotal > 0 else 0
        if rule["difficulty"] >= 5:
            threshold = 0.6
        elif rule["difficulty"] >= 4:
            threshold = 0.65
        elif rule["difficulty"] >= 3:
            threshold = 0.7
        else:
            threshold = self.state["config"]["mastery_threshold"]
        isMastered = all(r["accuracy"] >= threshold for r in typeResults.values()) and totalTotal > 0
        qScores = {qt: r["accuracy"] for qt, r in typeResults.items()}
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.execute(
            "UPDATE adaptive_mastery SET mastery_score=?, is_mastered=?, retries=?, question_scores=?, trained_at=? WHERE rule_id=?",
            (round(overall, 4), 1 if isMastered else 0, retries, json.dumps(qScores), time.time(), ruleId)
        )
        conn.commit()
        conn.close()
        return isMastered

    def logRetry(self, ruleId, retryNum, failedTypes, focusedTypes, accBefore, accAfter, mastered):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.execute(
            "INSERT INTO adaptive_retry_log (rule_id, retry_num, failed_types, focused_types, accuracy_before, accuracy_after, mastered, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (ruleId, retryNum, ",".join(failedTypes), ",".join(focusedTypes), accBefore, accAfter, 1 if mastered else 0, time.time())
        )
        conn.commit()
        conn.close()

    def cmdTeachRule(self, params):
        try:
            ruleId = int(self.p(params, "rule_id", 0))
            domain = self.p(params, "domain", "vscode")
            rule = self.getRuleById(ruleId)
            if rule is None:
                return (0, None, ("NOT_FOUND", "Rule not found", 0))
            if not self.prerequisitesMastered(ruleId):
                return (0, None, ("PREREQ_NOT_MET", "Prerequisites not mastered for rule " + str(ruleId), 0))
            maxRetries = int(self.p(params, "max_retries", self.state["config"]["max_retries"]))
            retryLog = []
            ok, trainData, err = self.trainRule(ruleId, domain)
            if not ok:
                return (0, None, err)
            weightsPath = trainData["weights"]
            typeResults = self.testAllTypes(ruleId, domain, weightsPath)
            diagnosis = self.diagnoseFailures(typeResults, difficulty=rule["difficulty"])
            overallAcc = sum(r["accuracy"] for r in typeResults.values()) / len(typeResults)
            isMastered = len(diagnosis["failed"]) == 0
            self.updateMastery(ruleId, typeResults, 0)
            retryLog.append({
                "retry": 0, "failed_types": diagnosis["failed"],
                "accuracy": round(overallAcc, 4), "mastered": isMastered,
                "first_loss": trainData["first_loss"], "last_loss": trainData["last_loss"],
                "type_scores": {qt: r["accuracy"] for qt, r in typeResults.items()},
            })
            for retryNum in range(1, maxRetries + 1):
                if isMastered:
                    break
                failedTypes = diagnosis["failed"]
                retryNoise = max(0.005, {1: 0.02, 2: 0.05, 3: 0.08, 4: 0.12, 5: 0.18}.get(rule["difficulty"], 0.08) * (1.0 - retryNum * 0.2))
                retryDelta = min(2.0, {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.5, 5: 0.3}.get(rule["difficulty"], 0.5) * (1.0 + retryNum * 0.5))
                ok2, trainData2, err2 = self.trainRule(
                    ruleId, domain,
                    epochs=self.state["config"]["retry_epochs"],
                    samples=self.state["config"]["retry_samples"],
                    questionTypes=failedTypes,
                    noiseLevel=retryNoise,
                    deltaScale=retryDelta,
                    initWeights=weightsPath
                )
                if not ok2:
                    break
                weightsPath = trainData2["weights"]
                newResults = {}
                for qt in QUESTION_TYPES:
                    if qt in failedTypes:
                        newResults[qt] = self.testQuestionType(ruleId, domain, qt, weightsPath)
                    else:
                        newResults[qt] = typeResults[qt]
                typeResults = newResults
                newOverall = sum(r["accuracy"] for r in typeResults.values()) / len(typeResults)
                diagnosis = self.diagnoseFailures(typeResults, difficulty=rule["difficulty"])
                isMastered = len(diagnosis["failed"]) == 0
                self.updateMastery(ruleId, typeResults, retryNum)
                self.logRetry(ruleId, retryNum, failedTypes, failedTypes, round(overallAcc, 4), round(newOverall, 4), isMastered)
                retryLog.append({
                    "retry": retryNum, "failed_types": failedTypes,
                    "accuracy": round(newOverall, 4), "mastered": isMastered,
                    "first_loss": trainData2["first_loss"], "last_loss": trainData2["last_loss"],
                    "type_scores": {qt: r["accuracy"] for qt, r in typeResults.items()},
                    "noise": round(retryNoise, 4), "delta": round(retryDelta, 4),
                })
                overallAcc = newOverall
            return (1, {
                "rule_id": ruleId,
                "rule_name": rule["name"],
                "domain": domain,
                "difficulty": rule["difficulty"],
                "mastered": isMastered,
                "retries": len(retryLog) - 1,
                "final_accuracy": round(overallAcc, 4),
                "weights": weightsPath,
                "retry_log": retryLog,
            }, None)
        except Exception as e:
            return (0, None, ("TEACH_ERROR", str(e), 0))

    def cmdTeachAll(self, params):
        try:
            domain = self.p(params, "domain", "vscode")
            maxRetries = int(self.p(params, "max_retries", self.state["config"]["max_retries"]))
            results = []
            for rule in RULES:
                if not self.prerequisitesMastered(rule["id"]):
                    results.append({
                        "rule_id": rule["id"], "rule_name": rule["name"],
                        "skipped": True, "reason": "Prerequisites not mastered",
                    })
                    continue
                conn = sqlite3.connect(self.state["config"]["progress_db"])
                row = conn.execute("SELECT is_mastered, mastery_score FROM adaptive_mastery WHERE rule_id=?", (rule["id"],)).fetchone()
                conn.close()
                if row and row[0] == 1:
                    results.append({
                        "rule_id": rule["id"], "rule_name": rule["name"],
                        "difficulty": rule["difficulty"], "mastered": True,
                        "retries": 0, "final_accuracy": round(row[1], 4),
                        "type_scores": {}, "skipped": True, "reason": "Already mastered",
                    })
                    continue
                ok, data, err = self.cmdTeachRule({
                    "rule_id": rule["id"], "domain": domain, "max_retries": maxRetries
                })
                if ok:
                    results.append({
                        "rule_id": data["rule_id"], "rule_name": data["rule_name"],
                        "difficulty": data["difficulty"], "mastered": data["mastered"],
                        "retries": data["retries"], "final_accuracy": data["final_accuracy"],
                        "type_scores": data["retry_log"][-1]["type_scores"] if data["retry_log"] else {},
                        "skipped": False,
                    })
                else:
                    results.append({
                        "rule_id": rule["id"], "rule_name": rule["name"],
                        "error": str(err), "skipped": False,
                    })
            masteredCount = sum(1 for r in results if r.get("mastered"))
            return (1, {
                "domain": domain,
                "trained": len([r for r in results if not r.get("skipped")]),
                "mastered": masteredCount,
                "total_rules": len(RULES),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TEACH_ALL_ERROR", str(e), 0))

    def cmdDiagnose(self, params):
        ruleId = int(self.p(params, "rule_id", 0))
        domain = self.p(params, "domain", "vscode")
        rule = self.getRuleById(ruleId)
        if rule is None:
            return (0, None, ("NOT_FOUND", "Rule not found", 0))
        weightsPath = os.path.join(EXPERTS_DIR, "adaptive_rule_" + str(ruleId) + "_" + domain + ".weights.bin")
        if not os.path.exists(weightsPath):
            weightsPath = os.path.join(EXPERTS_DIR, "rule_" + str(ruleId) + "_" + domain + ".weights.bin")
        if not os.path.exists(weightsPath):
            weightsPath = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
        if not os.path.exists(weightsPath):
            return (0, None, ("NO_WEIGHTS", "No weights found for rule " + str(ruleId), 0))
        typeResults = self.testAllTypes(ruleId, domain, weightsPath)
        diagnosis = self.diagnoseFailures(typeResults)
        return (1, {
            "rule_id": ruleId,
            "rule_name": rule["name"],
            "domain": domain,
            "type_results": typeResults,
            "failed_types": diagnosis["failed"],
            "passed_types": diagnosis["passed"],
            "overall_accuracy": round(sum(r["accuracy"] for r in typeResults.values()) / len(typeResults), 4),
        }, None)

    def cmdProgress(self, params):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        rows = conn.execute(
            "SELECT rule_id, rule_name, difficulty, mastery_score, is_mastered, retries, question_scores FROM adaptive_mastery ORDER BY difficulty, rule_id"
        ).fetchall()
        retryRows = conn.execute(
            "SELECT rule_id, retry_num, failed_types, accuracy_before, accuracy_after, mastered FROM adaptive_retry_log ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()
        conn.close()
        mastery = []
        for row in rows:
            qScores = json.loads(row[6]) if row[6] else {}
            mastery.append({
                "rule_id": row[0], "rule_name": row[1], "difficulty": row[2],
                "mastery_score": round(row[3], 4), "is_mastered": row[4] == 1,
                "retries": row[5], "question_scores": qScores,
            })
        retries = []
        for row in retryRows:
            retries.append({
                "rule_id": row[0], "retry_num": row[1], "failed_types": row[2],
                "acc_before": round(row[3], 4), "acc_after": round(row[4], 4), "mastered": row[5] == 1,
            })
        return (1, {"mastery": mastery, "total": len(mastery), "retry_history": retries}, None)

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "rules": len(RULES),
            "question_types": QUESTION_TYPES,
            "mastery_threshold": MASTERY_THRESHOLD,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)

    def loadDbFeatures(self, domainFilter=None, actionFilter=None, bodyFilter=None, limit=None):
        if not os.path.exists(SURVIVOR_DB):
            return []
        conn = sqlite3.connect(SURVIVOR_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        sql = "SELECT survivor_id, feature_vector, domain_name, action_name, body_shape, family, total_nodes, max_depth FROM db_features"
        conditions = []
        args = []
        if domainFilter:
            conditions.append("domain_name LIKE ?")
            args.append("%" + str(domainFilter) + "%")
        if actionFilter:
            conditions.append("action_name LIKE ?")
            args.append("%" + str(actionFilter) + "%")
        if bodyFilter:
            conditions.append("body_shape LIKE ?")
            args.append("%" + str(bodyFilter) + "%")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY RANDOM()"
        if limit:
            sql += " LIMIT " + str(int(limit))
        rows = cur.execute(sql, args).fetchall()
        conn.close()
        results = []
        for row in rows:
            fv = json.loads(row["feature_vector"])
            vector = [fv.get(key, 0.0) for key in FEATURE_KEYS]
            results.append({
                "vector": vector[:INPUT_DIM],
                "domain": row["domain_name"],
                "action": row["action_name"],
                "body_shape": row["body_shape"],
                "family": row["family"],
                "total_nodes": row["total_nodes"],
                "max_depth": row["max_depth"],
            })
        return results

    def domainLabelToIndex(self, domainName, domainList=None):
        if domainList is None:
            domainList = sorted(set([
                "FileIO", "Database", "Bracket", "Chat", "VULRS",
                "MemUnit", "Config", "Proof", "Approval", "Rollback",
                "Repair", "GUI", "Safety", "Token", "BCL", "Header",
                "Embed", "ErrorCapture", "Cascade", "Graph", "AST",
                "Rule", "Survivor", "Pipeline", "RoadMap",
            ]))
        if domainName in domainList:
            return domainList.index(domainName) % OUTPUT_DIM
        for i, d in enumerate(domainList):
            if d.lower() in domainName.lower() or domainName.lower() in d.lower():
                return i % OUTPUT_DIM
        return 0

    def bodyShapeLabelToIndex(self, bodyShape, bodyList=None):
        if bodyList is None:
            bodyList = [
                "EmptyPass", "MemRequired", "DbRequired", "ParamRequired",
                "TextRequired", "PathRequired", "TargetRequired",
                "ApprovalRequired", "ProofRequired", "HashCompare",
                "NoSourceEditGate", "TupleNormalize", "ListNormalize",
                "DictNormalize", "StringNormalize", "CounterState",
                "StatusState", "IssueCollect", "DecisionPassFailUnknown",
                "FileReadPlanOnly", "FileWritePlanOnly", "FileDeleteBlocked",
                "DbSelectPlanOnly", "DbWritePlanOnly", "DbTransactionPlan",
                "BracketTokenScan", "BracketRowScan", "BracketRenderPacket",
                "ChatMessageSplitPlan", "ChatIntentClassify", "CompressionProofPlan",
                "MemUnitRoutePlan", "AuthorityResolvePlan", "RepairPlanOnly",
                "ProofResultStorePlan", "ApprovalDryRunPlan", "RollbackPlanOnly",
                "ErrorCandidateRankPlan", "GuiEventRoutePlan",
                "PrintGuard", "PropertyGuard", "StaticMethodGuard",
                "ClassMethodGuard", "SelfUnderscoreGuard", "TabIndentGuard",
                "TrailingWhitespaceGuard", "HardcodedValueGuard", "EnumGuard",
                "DataclassGuard", "DecoratorGuard", "LambdaGuard",
                "GlobalGuard", "NonlocalGuard", "TryExceptGuard",
                "WithGuard", "RaiseGuard", "AsyncGuard", "YieldGuard",
                "AssertGuard", "BreakGuard", "ContinueGuard",
                "ImportStarGuard", "WalrusGuard", "MatchGuard",
                "NestedClassGuard", "ForbiddenNodeGuard",
            ]
        if bodyShape in bodyList:
            return bodyList.index(bodyShape) % OUTPUT_DIM
        for i, b in enumerate(bodyList):
            if b.lower() in bodyShape.lower() or bodyShape.lower() in b.lower():
                return i % OUTPUT_DIM
        return 0

    def createLessonFromDb(self, features, labelIndex):
        target = self.makeTarget(labelIndex)
        return {"state": features, "action": target, "reward": 1.0}

    def generateTrainingDataFromDb(self, ruleId, labelMode="domain", domainFilter=None, samples=None):
        if samples is None:
            samples = self.state["config"]["initial_samples"]
        rows = self.loadDbFeatures(domainFilter=domainFilter, limit=samples * 2)
        if not rows:
            return {"episodes": [], "config": {"input_dim": INPUT_DIM, "output_dim": OUTPUT_DIM, "samples": 0}}
        episodes = []
        sampleIdx = 0
        for row in rows:
            if sampleIdx >= samples:
                break
            if labelMode == "domain":
                labelIdx = self.domainLabelToIndex(row["domain"])
            elif labelMode == "body_shape":
                labelIdx = self.bodyShapeLabelToIndex(row["body_shape"])
            else:
                labelIdx = self.domainLabelToIndex(row["domain"])
            lesson = self.createLessonFromDb(row["vector"], labelIdx)
            episodes.append({"episode": sampleIdx, "num_nodes": 1, "steps": [lesson]})
            sampleIdx += 1
        return {"episodes": episodes, "config": {"input_dim": INPUT_DIM, "output_dim": OUTPUT_DIM, "samples": sampleIdx}}

    def trainRuleFromDb(self, ruleId, labelMode="domain", domainFilter=None, samples=None, epochs=None, initWeights=None):
        if epochs is None:
            epochs = self.state["config"]["initial_epochs"]
        if samples is None:
            samples = self.state["config"]["initial_samples"]
        data = self.generateTrainingDataFromDb(ruleId, labelMode, domainFilter, samples)
        if not data["episodes"]:
            return (0, None, ("NO_DATA", "No DB features found", 0))
        trainingPath = os.path.join(TRAINING_DIR, "db_rule_" + str(ruleId) + "_" + str(labelMode) + ".json")
        with open(trainingPath, "w") as f:
            json.dump(data, f)
        weightsOut = os.path.join(EXPERTS_DIR, "db_rule_" + str(ruleId) + "_" + str(labelMode) + ".weights.bin")
        cmdArgs = [self.state["config"]["coretotch_bin"], "train", trainingPath, weightsOut, str(epochs), str(0.01)]
        if initWeights and os.path.exists(initWeights):
            cmdArgs.append(initWeights)
        proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
        output = proc.stderr + proc.stdout
        lossLines = [l for l in output.split("\n") if "Loss:" in l]
        firstLoss = lossLines[0].strip() if lossLines else ""
        lastLoss = lossLines[-1].strip() if lossLines else ""
        return (1, {"weights": weightsOut, "first_loss": firstLoss, "last_loss": lastLoss, "samples": data["config"]["samples"]}, None)

    def testRuleFromDb(self, weightsPath, labelMode="domain", domainFilter=None, count=None):
        if count is None:
            count = self.state["config"]["test_per_type"]
        rows = self.loadDbFeatures(domainFilter=domainFilter, limit=count * 3)
        if not rows:
            return {"correct": 0, "total": 0, "accuracy": 0}
        correct = 0
        total = 0
        for row in rows[:count]:
            if labelMode == "domain":
                labelIdx = self.domainLabelToIndex(row["domain"])
            else:
                labelIdx = self.bodyShapeLabelToIndex(row["body_shape"])
            output = self.runInference(weightsPath, row["vector"])
            if output is None:
                continue
            total += 1
            if output.index(max(output)) == labelIdx:
                correct += 1
        return {"correct": correct, "total": total, "accuracy": round(correct / total, 4) if total > 0 else 0}

    def cmdTeachRuleDb(self, params):
        try:
            ruleId = int(self.p(params, "rule_id", 0))
            labelMode = self.p(params, "label_mode", "domain")
            domainFilter = self.p(params, "domain_filter", None)
            samples = int(self.p(params, "samples", self.state["config"]["initial_samples"]))
            epochs = int(self.p(params, "epochs", self.state["config"]["initial_epochs"]))
            ok, trainData, err = self.trainRuleFromDb(ruleId, labelMode, domainFilter, samples, epochs)
            if not ok:
                return (0, None, err)
            weightsPath = trainData["weights"]
            testResult = self.testRuleFromDb(weightsPath, labelMode, domainFilter)
            return (1, {
                "rule_id": ruleId,
                "label_mode": labelMode,
                "domain_filter": domainFilter,
                "weights": weightsPath,
                "first_loss": trainData["first_loss"],
                "last_loss": trainData["last_loss"],
                "samples": trainData["samples"],
                "test_accuracy": testResult["accuracy"],
                "test_correct": testResult["correct"],
                "test_total": testResult["total"],
                "source": "db_survivors.sqlite",
                "feature_type": "real_ast",
            }, None)
        except Exception as e:
            return (0, None, ("TEACH_DB_ERROR", str(e), 0))

    def cmdTeachAllDb(self, params):
        try:
            labelMode = self.p(params, "label_mode", "domain")
            samples = int(self.p(params, "samples", 200))
            epochs = int(self.p(params, "epochs", 300))
            results = []
            for ruleId in range(len(RULES)):
                ok, data, err = self.cmdTeachRuleDb({
                    "rule_id": ruleId,
                    "label_mode": labelMode,
                    "samples": samples,
                    "epochs": epochs,
                })
                if ok:
                    results.append({
                        "rule_id": ruleId,
                        "rule_name": RULES[ruleId]["name"],
                        "test_accuracy": data["test_accuracy"],
                        "samples": data["samples"],
                        "first_loss": data["first_loss"],
                        "last_loss": data["last_loss"],
                    })
                else:
                    results.append({
                        "rule_id": ruleId,
                        "rule_name": RULES[ruleId]["name"],
                        "error": str(err),
                    })
            avgAcc = sum(r.get("test_accuracy", 0) for r in results) / max(len(results), 1)
            return (1, {
                "label_mode": labelMode,
                "source": "db_survivors.sqlite",
                "feature_type": "real_ast",
                "total_rules": len(RULES),
                "avg_accuracy": round(avgAcc, 4),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TEACH_ALL_DB_ERROR", str(e), 0))

    def cmdDbStatus(self, params):
        if not os.path.exists(SURVIVOR_DB):
            return (0, None, ("NO_DB", "Survivor DB not found at " + SURVIVOR_DB, 0))
        conn = sqlite3.connect(SURVIVOR_DB)
        cur = conn.cursor()
        survivors = cur.execute("SELECT COUNT(*) FROM db_survivor").fetchone()[0]
        features = cur.execute("SELECT COUNT(*) FROM db_features").fetchone()[0]
        domains = cur.execute("SELECT COUNT(DISTINCT domain_name) FROM db_survivor").fetchone()[0]
        actions = cur.execute("SELECT COUNT(DISTINCT action_name) FROM db_survivor").fetchone()[0]
        bodyShapes = cur.execute("SELECT COUNT(DISTINCT body_shape) FROM db_survivor").fetchone()[0]
        families = cur.execute("SELECT COUNT(DISTINCT family) FROM db_survivor").fetchone()[0]
        conn.close()
        return (1, {
            "db_path": SURVIVOR_DB,
            "survivors": survivors,
            "features_extracted": features,
            "domains": domains,
            "actions": actions,
            "body_shapes": bodyShapes,
            "families": families,
            "feature_keys": len(FEATURE_KEYS),
            "feature_type": "real_ast",
            "ready": features > 0,
        }, None)
