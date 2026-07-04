#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLCurriculumTeacher.py
#[@SUMMARY] Curriculum learning system: teachers generate lessons at increasing difficulty, verify answers programmatically, track learning progress. Not datasets — lessons.
#[@CLASS] CoreMLCurriculumTeacher
#[@METHOD] create_lesson, verify_answer, run_lesson, run_curriculum, track_progress, list_teachers
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import random
import time
import struct
import subprocess
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_curriculum"
PROGRESS_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/curriculum_progress.sqlite"

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]
DOMAIN_INDICES = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}

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
    "vscode": {
        "func_density": 0.8, "class_density": 0.6, "import_density": 0.9,
        "if_density": 0.7, "for_density": 0.5, "try_density": 0.4,
        "decorator_density": 0.3, "lambda_density": 0.2, "comprehension_density": 0.4,
        "async_density": 0.1, "with_density": 0.3, "nesting": 0.6,
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
        "return_density": 0.48, "assign_density": 0.5, "call_density": 0.42,
        "attribute_density": 0.48, "name_density": 0.8, "constant_density": 0.6,
        "annotation_density": 0.15, "raise_density": 0.15, "except_density": 0.27,
        "await_density": 0.0, "yield_density": 0.0,
    },
}

TEACHERS = [
    {
        "id": "grammar_teacher",
        "name": "Grammar Teacher",
        "description": "Teaches: what is a function, class, loop, branch, comprehension",
        "question_types": ["is_valid_grammar", "which_construct", "count_constructs"],
        "difficulty_levels": 5,
    },
    {
        "id": "ast_teacher",
        "name": "AST Structure Teacher",
        "description": "Teaches: tree depth, branching, node distribution, nesting",
        "question_types": ["estimate_depth", "identify_dominant_node", "tree_shape"],
        "difficulty_levels": 5,
    },
    {
        "id": "semantic_teacher",
        "name": "Semantic Teacher",
        "description": "Teaches: scope, closures, inheritance, async semantics",
        "question_types": ["has_scope", "uses_closure", "is_async_capable"],
        "difficulty_levels": 5,
    },
    {
        "id": "transform_teacher",
        "name": "Transformation Teacher",
        "description": "Teaches: which transformation was applied, is it safe",
        "question_types": ["which_transform", "is_safe_transform"],
        "difficulty_levels": 5,
    },
    {
        "id": "style_teacher",
        "name": "VBStyle Teacher",
        "description": "Teaches: Run() presence, Tuple3, self.state, BCL headers, compliance",
        "question_types": ["has_run_method", "has_tuple3", "is_vbstyle_compliant"],
        "difficulty_levels": 5,
    },
    {
        "id": "error_teacher",
        "name": "Error Detection Teacher",
        "description": "Teaches: find the error, classify error type, predict failure",
        "question_types": ["has_error", "which_error_type", "error_severity"],
        "difficulty_levels": 5,
    },
    {
        "id": "optimization_teacher",
        "name": "Optimization Teacher",
        "description": "Teaches: can this be optimized, which optimization applies",
        "question_types": ["can_optimize", "which_optimization", "complexity_class"],
        "difficulty_levels": 5,
    },
]

TRANSFORMATIONS = [
    {"id": 0, "name": "add_function", "safe": True, "effect": {"func_density": 0.1, "return_density": 0.08}},
    {"id": 1, "name": "add_class", "safe": True, "effect": {"class_density": 0.1, "attribute_density": 0.08}},
    {"id": 2, "name": "add_try_except", "safe": True, "effect": {"try_density": 0.2, "except_density": 0.18, "nesting": 0.1}},
    {"id": 3, "name": "add_decorator", "safe": True, "effect": {"decorator_density": 0.15}},
    {"id": 4, "name": "add_comprehension", "safe": True, "effect": {"comprehension_density": 0.2, "for_density": -0.1}},
    {"id": 5, "name": "add_async", "safe": True, "effect": {"async_density": 0.2, "await_density": 0.15}},
    {"id": 6, "name": "add_type_hints", "safe": True, "effect": {"annotation_density": 0.15}},
    {"id": 7, "name": "flatten_nesting", "safe": True, "effect": {"nesting": -0.15, "func_density": 0.08}},
    {"id": 8, "name": "remove_error_handling", "safe": False, "effect": {"try_density": -0.2, "except_density": -0.18}},
    {"id": 9, "name": "introduce_bug", "safe": False, "effect": {"return_density": -0.1}},
]

ERROR_TYPES = [
    {"id": 0, "name": "no_error", "features": {}},
    {"id": 1, "name": "syntax_error", "features": {"nesting": 0.05}},
    {"id": 2, "name": "indentation_error", "features": {"nesting": -0.05}},
    {"id": 3, "name": "undefined_variable", "features": {"name_density": 0.05}},
    {"id": 4, "name": "type_mismatch", "features": {"assign_density": 0.05}},
    {"id": 5, "name": "missing_return", "features": {"return_density": -0.1}},
    {"id": 6, "name": "scope_leak", "features": {"global_density": 0.1}},
    {"id": 7, "name": "circular_import", "features": {"import_density": 0.1}},
    {"id": 8, "name": "recursion_error", "features": {"func_density": 0.1}},
    {"id": 9, "name": "attribute_error", "features": {"attribute_density": -0.1}},
]


class CoreMLCurriculumTeacher:
    """Curriculum learning system with teachers, not datasets.

    Each teacher generates lessons at increasing difficulty:
      Level 1: Simple — clear features, large deltas, easy to distinguish
      Level 2: Moderate — more features vary, smaller deltas
      Level 3: Standard — realistic noise, mixed signals
      Level 4: Advanced — subtle differences, many confounders
      Level 5: Expert — minimal signal, maximum noise, edge cases

    Lesson structure (not just data — a LESSON):
      1. Build: Generate an AST feature vector (the "code")
      2. Question: Ask a specific question about it
      3. Answer: Model attempts to answer (via coretotch inference)
      4. Verify: Check the answer programmatically (ground truth is known)
      5. Explain: Record why it was right/wrong
      6. Progress: Track accuracy per teacher per difficulty

    The model trains on lessons, not examples. Each lesson has:
      - A clear learning objective
      - A verifiable answer
      - A difficulty level
      - Feedback (correct/incorrect + explanation)

    Teachers:
      grammar_teacher: "Is this valid grammar? Which construct is dominant?"
      ast_teacher: "What's the tree depth? What shape is the AST?"
      semantic_teacher: "Does this use closures? Is it async-capable?"
      transform_teacher: "Which transformation was applied? Is it safe?"
      style_teacher: "Does this have Run()? Is it VBStyle compliant?"
      error_teacher: "Is there an error? What type? How severe?"
      optimization_teacher: "Can this be optimized? Which optimization?"
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "progress_db": PROGRESS_DB,
                "lessons_per_level": 200,
                "epochs": 300,
                "learning_rate": 0.01,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()
        self.initProgressDb()

    def Run(self, command, params=None):
        params = params or {}
        if command == "list_teachers":
            return self.cmdListTeachers(params)
        if command == "create_lesson":
            return self.cmdCreateLesson(params)
        if command == "run_lesson":
            return self.cmdRunLesson(params)
        if command == "run_curriculum":
            return self.cmdRunCurriculum(params)
        if command == "train_curriculum":
            return self.cmdTrainCurriculum(params)
        if command == "track_progress":
            return self.cmdTrackProgress(params)
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

    def initProgressDb(self):
        import sqlite3
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS lesson_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT,
                difficulty INTEGER,
                question_type TEXT,
                domain TEXT,
                correct INTEGER,
                model_answer TEXT,
                expected_answer TEXT,
                explanation TEXT,
                timestamp REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS progress_summary (
                teacher_id TEXT,
                difficulty INTEGER,
                total_lessons INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0,
                last_updated REAL DEFAULT 0,
                PRIMARY KEY (teacher_id, difficulty)
            );
            CREATE TABLE IF NOT EXISTS curriculum_levels (
                teacher_id TEXT,
                domain TEXT,
                current_level INTEGER DEFAULT 1,
                level_passed INTEGER DEFAULT 0,
                PRIMARY KEY (teacher_id, domain)
            );
        """)
        conn.commit()
        conn.close()

    def clamp(self, value, lo=0.0, hi=1.0):
        return max(lo, min(hi, value))

    def noiseForLevel(self, level):
        """Higher difficulty = more noise = harder to distinguish."""
        return {1: 0.02, 2: 0.05, 3: 0.08, 4: 0.12, 5: 0.18}.get(level, 0.08)

    def deltaForLevel(self, level):
        """Higher difficulty = smaller deltas = subtler changes."""
        return {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.3, 5: 0.15}.get(level, 0.5)

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

    def applyTransform(self, vector, transformId, deltaScale=1.0):
        transform = TRANSFORMATIONS[transformId]
        result = list(vector)
        for featName, delta in transform["effect"].items():
            if featName in FEATURE_KEYS:
                idx = FEATURE_KEYS.index(featName)
                result[idx] = self.clamp(result[idx] + delta * deltaScale)
        return result

    def applyError(self, vector, errorId, deltaScale=1.0):
        errorType = ERROR_TYPES[errorId]
        result = list(vector)
        for featName, delta in errorType["features"].items():
            if featName in FEATURE_KEYS:
                idx = FEATURE_KEYS.index(featName)
                result[idx] = self.clamp(result[idx] + delta * deltaScale)
        return result

    def createLesson(self, teacherId, difficulty=1, domain=None):
        """Create a single lesson from a teacher at a given difficulty.

        Returns a lesson dict with:
          - teacher_id, difficulty, domain
          - question_type: what the model is asked
          - features: 40D input vector
          - expected_answer: ground truth (verifiable)
          - explanation: why this is the answer
        """
        if domain is None:
            domain = random.choice(DOMAINS)
        profile = DOMAIN_PROFILES[domain]
        noise = self.noiseForLevel(difficulty)
        deltaScale = self.deltaForLevel(difficulty)
        baseVector = self.profileToVector(profile, noise)

        if teacherId == "grammar_teacher":
            questionType = random.choice(["is_valid_grammar", "which_construct", "count_constructs"])
            if questionType == "is_valid_grammar":
                isValid = random.random() > 0.3
                if not isValid:
                    baseVector[0] = self.clamp(baseVector[0] - 0.5 * deltaScale)
                features = baseVector
                expected = 0 if isValid else 1
                explanation = "Valid grammar has func_density > 0.3; corrupted has near-zero"
            elif questionType == "which_construct":
                constructs = ["function", "class", "loop", "comprehension"]
                constructIdx = random.randint(0, 3)
                featureIdx = {"function": 0, "class": 1, "loop": 4, "comprehension": 9}[constructs[constructIdx]]
                features = list(baseVector)
                features[featureIdx] = self.clamp(features[featureIdx] + 0.3 * deltaScale)
                expected = constructIdx
                explanation = constructs[constructIdx] + " has elevated density at index " + str(featureIdx)
            else:
                countHigh = sum(1 for v in baseVector if v > 0.5)
                features = baseVector
                expected = 0 if countHigh < 10 else (1 if countHigh < 20 else 2)
                explanation = "count_constructs: " + str(countHigh) + " features above 0.5"
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "ast_teacher":
            questionType = random.choice(["estimate_depth", "identify_dominant_node", "tree_shape"])
            if questionType == "estimate_depth":
                depth = baseVector[39]
                features = baseVector
                expected = 0 if depth < 0.4 else (1 if depth < 0.7 else 2)
                explanation = "nesting=" + str(round(depth, 3)) + " -> " + ["shallow", "medium", "deep"][expected]
            elif questionType == "identify_dominant_node":
                maxIdx = baseVector.index(max(baseVector[:20]))
                features = baseVector
                expected = min(maxIdx, 9)
                explanation = "Dominant feature at index " + str(maxIdx) + " = " + FEATURE_KEYS[maxIdx]
            else:
                isBushy = baseVector[0] > 0.6 and baseVector[1] > 0.5
                features = baseVector
                expected = 0 if isBushy else 1
                explanation = "tree_shape: " + ("bushy" if isBushy else "linear")
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "semantic_teacher":
            questionType = random.choice(["has_scope", "uses_closure", "is_async_capable"])
            if questionType == "has_scope":
                hasScope = baseVector[1] > 0.4 and baseVector[0] > 0.4
                features = baseVector
                expected = 0 if hasScope else 1
                explanation = "has_scope: class+func density indicates scoping"
            elif questionType == "uses_closure":
                usesClosure = baseVector[11] > 0.2 and baseVector[39] > 0.5
                features = baseVector
                expected = 0 if usesClosure else 1
                explanation = "uses_closure: lambda + nesting indicates closures"
            else:
                isAsync = baseVector[12] > 0.15
                features = baseVector
                expected = 0 if isAsync else 1
                explanation = "is_async_capable: async_density=" + str(round(baseVector[12], 3))
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "transform_teacher":
            questionType = random.choice(["which_transform", "is_safe_transform"])
            transformId = random.randint(0, len(TRANSFORMATIONS) - 1)
            afterVector = self.applyTransform(baseVector, transformId, deltaScale)
            if questionType == "which_transform":
                features = afterVector
                expected = transformId
                explanation = TRANSFORMATIONS[transformId]["name"] + " was applied"
            else:
                features = afterVector
                expected = 0 if TRANSFORMATIONS[transformId]["safe"] else 1
                explanation = "Transform " + TRANSFORMATIONS[transformId]["name"] + " is " + ("safe" if TRANSFORMATIONS[transformId]["safe"] else "unsafe")
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "style_teacher":
            questionType = random.choice(["has_run_method", "has_tuple3", "is_vbstyle_compliant"])
            if questionType == "has_run_method":
                hasRun = profile.get("run_method", 0.5) > 0.6
                features = baseVector
                expected = 0 if hasRun else 1
                explanation = "run_method profile=" + str(profile.get("run_method", 0.5))
            elif questionType == "has_tuple3":
                hasTuple3 = profile.get("tuple3", 0.5) > 0.5
                features = baseVector
                expected = 0 if hasTuple3 else 1
                explanation = "tuple3 profile=" + str(profile.get("tuple3", 0.5))
            else:
                compliant = profile.get("no_print", 0.8) > 0.8 and profile.get("no_self_underscore", 0.8) > 0.8
                features = baseVector
                expected = 0 if compliant else 1
                explanation = "vbstyle compliant: no_print=" + str(profile.get("no_print", 0.8))
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "error_teacher":
            questionType = random.choice(["has_error", "which_error_type", "error_severity"])
            errorId = random.randint(0, len(ERROR_TYPES) - 1)
            errorVector = self.applyError(baseVector, errorId, deltaScale)
            if questionType == "has_error":
                features = errorVector
                expected = 0 if errorId == 0 else 1
                explanation = "has_error: errorId=" + str(errorId) + " (" + ERROR_TYPES[errorId]["name"] + ")"
            elif questionType == "which_error_type":
                features = errorVector
                expected = errorId
                explanation = "which_error_type: " + ERROR_TYPES[errorId]["name"]
            else:
                severity = 0 if errorId == 0 else (1 if errorId <= 4 else 2)
                features = errorVector
                expected = severity
                explanation = "error_severity: " + ["none", "low", "high"][severity]
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        if teacherId == "optimization_teacher":
            questionType = random.choice(["can_optimize", "which_optimization", "complexity_class"])
            if questionType == "can_optimize":
                canOpt = baseVector[39] > 0.6 or baseVector[4] > 0.6
                features = baseVector
                expected = 0 if canOpt else 1
                explanation = "can_optimize: high nesting or loop density indicates optimization potential"
            elif questionType == "which_optimization":
                opts = ["flatten_nesting", "loop_to_comprehension", "add_caching", "inline_function"]
                optIdx = random.randint(0, 3)
                features = baseVector
                expected = optIdx
                explanation = "which_optimization: " + opts[optIdx]
            else:
                complexity = 0 if baseVector[39] < 0.4 else (1 if baseVector[39] < 0.7 else 2)
                features = baseVector
                expected = complexity
                explanation = "complexity_class: nesting=" + str(round(baseVector[39], 3)) + " -> " + ["O(1)", "O(n)", "O(n^2)"][complexity]
            return {
                "teacher_id": teacherId, "difficulty": difficulty, "domain": domain,
                "question_type": questionType, "features": features,
                "expected_answer": expected, "explanation": explanation,
            }

        return None

    def generateCurriculumData(self, teacherId, difficulty, samplesPerDomain=None):
        """Generate training data for one teacher at one difficulty level."""
        if samplesPerDomain is None:
            samplesPerDomain = self.state["config"]["lessons_per_level"]
        episodes = []
        sampleIdx = 0
        for domain in DOMAINS:
            for _ in range(samplesPerDomain):
                lesson = self.createLesson(teacherId, difficulty, domain)
                if lesson is None:
                    continue
                target = self.makeTarget(lesson["expected_answer"])
                episodes.append({
                    "episode": sampleIdx,
                    "num_nodes": 1,
                    "steps": [{
                        "state": lesson["features"],
                        "action": target,
                        "reward": 1.0,
                    }],
                })
                sampleIdx += 1
        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "teacher_id": teacherId,
                "difficulty": difficulty,
                "samples": sampleIdx,
                "source": "curriculum_lesson",
            },
        }

    def runInference(self, weightsPath, features):
        """Run coretotch inference on a feature vector."""
        if not os.path.exists(weightsPath):
            return None
        statePath = os.path.join(TRAINING_DIR, "lesson_inference.bin")
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

    def logLesson(self, teacherId, difficulty, questionType, domain, correct, modelAnswer, expectedAnswer, explanation):
        import sqlite3
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.execute(
            "INSERT INTO lesson_log (teacher_id, difficulty, question_type, domain, correct, model_answer, expected_answer, explanation, timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
            (teacherId, difficulty, questionType, domain, correct, str(modelAnswer), str(expectedAnswer), explanation, time.time())
        )
        conn.execute(
            "INSERT OR REPLACE INTO progress_summary (teacher_id, difficulty, total_lessons, correct_count, accuracy, last_updated) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(teacher_id, difficulty) DO UPDATE SET total_lessons=total_lessons+1, correct_count=correct_count+?, accuracy=(CAST(correct_count+? AS REAL)/CAST(total_lessons+1 AS REAL)), last_updated=?",
            (teacherId, difficulty, 1, 1 if correct else 0, 1.0 if correct else 0.0, time.time(), 1 if correct else 0, 1 if correct else 0, time.time())
        )
        conn.commit()
        conn.close()

    def cmdListTeachers(self, params):
        return (1, {
            "teachers": [{"id": t["id"], "name": t["name"], "description": t["description"],
                          "question_types": t["question_types"], "difficulty_levels": t["difficulty_levels"]}
                         for t in TEACHERS],
            "total": len(TEACHERS),
        }, None)

    def cmdCreateLesson(self, params):
        teacherId = self.p(params, "teacher_id", "grammar_teacher")
        difficulty = int(self.p(params, "difficulty", 1))
        domain = self.p(params, "domain")
        lesson = self.createLesson(teacherId, difficulty, domain)
        if lesson is None:
            return (0, None, ("CREATE_ERROR", "Failed to create lesson", 0))
        return (1, lesson, None)

    def cmdRunLesson(self, params):
        """Run a single lesson: create, ask model, verify, explain."""
        try:
            teacherId = self.p(params, "teacher_id", "grammar_teacher")
            difficulty = int(self.p(params, "difficulty", 1))
            domain = self.p(params, "domain")
            lesson = self.createLesson(teacherId, difficulty, domain)
            if lesson is None:
                return (0, None, ("LESSON_ERROR", "Failed to create lesson", 0))
            weightsPath = os.path.join(EXPERTS_DIR, "curriculum_" + teacherId + "_" + lesson["domain"] + ".weights.bin")
            if not os.path.exists(weightsPath):
                weightsPath = os.path.join(EXPERTS_DIR, lesson["domain"] + ".weights.bin")
            modelOutput = self.runInference(weightsPath, lesson["features"])
            if modelOutput is None:
                return (1, {
                    "lesson": lesson,
                    "model_answer": None,
                    "correct": False,
                    "explanation": "No expert weights found for this teacher/domain",
                }, None)
            modelAnswer = modelOutput.index(max(modelOutput))
            correct = modelAnswer == lesson["expected_answer"]
            self.logLesson(teacherId, difficulty, lesson["question_type"], lesson["domain"],
                           1 if correct else 0, modelAnswer, lesson["expected_answer"], lesson["explanation"])
            return (1, {
                "teacher_id": teacherId,
                "difficulty": difficulty,
                "domain": lesson["domain"],
                "question_type": lesson["question_type"],
                "expected_answer": lesson["expected_answer"],
                "model_answer": modelAnswer,
                "correct": correct,
                "explanation": lesson["explanation"],
                "model_output": [round(v, 4) for v in modelOutput],
            }, None)
        except Exception as e:
            return (0, None, ("RUN_LESSON_ERROR", str(e), 0))

    def cmdRunCurriculum(self, params):
        """Run a full curriculum session: N lessons per teacher per difficulty."""
        try:
            lessonsPerLevel = int(self.p(params, "lessons", 20))
            maxDifficulty = int(self.p(params, "max_difficulty", 5))
            teacherFilter = self.p(params, "teacher_id")
            teachers = [t for t in TEACHERS if not teacherFilter or t["id"] == teacherFilter]
            results = []
            totalCorrect = 0
            totalLessons = 0
            for teacher in teachers:
                for difficulty in range(1, maxDifficulty + 1):
                    levelCorrect = 0
                    levelTotal = 0
                    for _ in range(lessonsPerLevel):
                        ok, data, err = self.cmdRunLesson({
                            "teacher_id": teacher["id"],
                            "difficulty": difficulty,
                        })
                        if ok and data.get("model_answer") is not None:
                            levelTotal += 1
                            levelTotal += 0
                            if data["correct"]:
                                levelCorrect += 1
                    if levelTotal > 0:
                        accuracy = levelCorrect / levelTotal
                        results.append({
                            "teacher_id": teacher["id"],
                            "difficulty": difficulty,
                            "lessons": levelTotal,
                            "correct": levelCorrect,
                            "accuracy": round(accuracy, 4),
                        })
                        totalCorrect += levelCorrect
                        totalLessons += levelTotal
            return (1, {
                "total_lessons": totalLessons,
                "total_correct": totalCorrect,
                "overall_accuracy": round(totalCorrect / totalLessons, 4) if totalLessons > 0 else 0,
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("CURRICULUM_ERROR", str(e), 0))

    def cmdTrainCurriculum(self, params):
        """Train experts using curriculum: start at level 1, advance when accuracy > 80%."""
        try:
            teacherId = self.p(params, "teacher_id", "grammar_teacher")
            domain = self.p(params, "domain", "vscode")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            lessonsPerLevel = int(self.p(params, "lessons", self.state["config"]["lessons_per_level"]))
            maxDifficulty = int(self.p(params, "max_difficulty", 5))
            advancementThreshold = 0.8
            results = []
            weightsOut = os.path.join(EXPERTS_DIR, "curriculum_" + teacherId + "_" + domain + ".weights.bin")
            initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if not os.path.exists(initWeights):
                initWeights = None
            for difficulty in range(1, maxDifficulty + 1):
                data = self.generateCurriculumData(teacherId, difficulty, lessonsPerLevel)
                trainingPath = os.path.join(TRAINING_DIR, "curriculum_" + teacherId + "_" + domain + "_level" + str(difficulty) + ".json")
                with open(trainingPath, "w") as f:
                    json.dump(data, f)
                coretotch = self.state["config"]["coretotch_bin"]
                cmdArgs = [coretotch, "train", trainingPath, weightsOut, str(epochs), str(0.01)]
                if initWeights:
                    cmdArgs.append(initWeights)
                proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
                output = proc.stderr + proc.stdout
                lossLines = [l for l in output.split("\n") if "Loss:" in l]
                firstLoss = lossLines[0].strip() if lossLines else ""
                lastLoss = lossLines[-1].strip() if lossLines else ""
                initWeights = weightsOut
                testCorrect = 0
                testTotal = min(20, lessonsPerLevel)
                for _ in range(testTotal):
                    lesson = self.createLesson(teacherId, difficulty, domain)
                    if lesson is None:
                        continue
                    modelOutput = self.runInference(weightsOut, lesson["features"])
                    if modelOutput is None:
                        continue
                    modelAnswer = modelOutput.index(max(modelOutput))
                    if modelAnswer == lesson["expected_answer"]:
                        testCorrect += 1
                accuracy = testCorrect / testTotal if testTotal > 0 else 0
                results.append({
                    "difficulty": difficulty,
                    "first_loss": firstLoss,
                    "last_loss": lastLoss,
                    "accuracy": round(accuracy, 4),
                    "passed": accuracy >= advancementThreshold,
                })
                if accuracy < advancementThreshold:
                    break
            return (1, {
                "teacher_id": teacherId,
                "domain": domain,
                "weights": weightsOut,
                "levels_trained": len(results),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_CURRICULUM_ERROR", str(e), 0))

    def cmdTrackProgress(self, params):
        """Show learning progress across all teachers and difficulty levels."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.state["config"]["progress_db"])
            rows = conn.execute(
                "SELECT teacher_id, difficulty, total_lessons, correct_count, accuracy, last_updated FROM progress_summary ORDER BY teacher_id, difficulty"
            ).fetchall()
            conn.close()
            progress = []
            for row in rows:
                progress.append({
                    "teacher_id": row[0],
                    "difficulty": row[1],
                    "total_lessons": row[2],
                    "correct_count": row[3],
                    "accuracy": round(row[4], 4),
                })
            return (1, {"progress": progress, "total_entries": len(progress)}, None)
        except Exception as e:
            return (0, None, ("TRACK_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "teachers": len(TEACHERS),
            "teacher_ids": [t["id"] for t in TEACHERS],
            "domains": DOMAINS,
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
