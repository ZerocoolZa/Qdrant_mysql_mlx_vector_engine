#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLGenerativeRules.py
#[@SUMMARY] Teaches generative rules of Python: each rule has statement, rationale, applicability, counter-conditions. Prerequisite chain: counting -> addition -> algebra. Progressive rule mastery, not example memorization.
#[@CLASS] CoreMLGenerativeRules
#[@METHOD] define_rules, gen_rule_lesson, verify_rule, run_rule_lesson, run_rule_curriculum, track_mastery, list_rules, show_prerequisites
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

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_rules"
PROGRESS_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/rule_mastery.sqlite"

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

RULES = [
    {
        "id": 0,
        "name": "function_definition",
        "category": "grammar",
        "statement": "A function is defined with def name(params): body",
        "rationale": "Functions encapsulate reusable logic. They are the basic unit of abstraction.",
        "applies_when": "You need to group statements into a reusable unit",
        "does_not_apply": "When the logic is used exactly once and is trivially short",
        "prerequisites": [],
        "feature_idx": 0,
        "feature_name": "func_density",
        "difficulty": 1,
    },
    {
        "id": 1,
        "name": "class_definition",
        "category": "grammar",
        "statement": "A class is defined with class Name: body. It groups data and behavior.",
        "rationale": "Classes model entities. They bundle state (attributes) and operations (methods).",
        "applies_when": "You have related data and operations that share lifecycle",
        "does_not_apply": "When you only need pure functions with no shared state",
        "prerequisites": [0],
        "feature_idx": 1,
        "feature_name": "class_density",
        "difficulty": 1,
    },
    {
        "id": 2,
        "name": "control_flow_branching",
        "category": "grammar",
        "statement": "if/elif/else branches execution based on conditions",
        "rationale": "Programs must make decisions. Branching is the fundamental control flow primitive.",
        "applies_when": "Different actions are needed for different conditions",
        "does_not_apply": "When the same action applies regardless of condition",
        "prerequisites": [0],
        "feature_idx": 3,
        "feature_name": "if_density",
        "difficulty": 1,
    },
    {
        "id": 3,
        "name": "loop_iteration",
        "category": "grammar",
        "statement": "for loops iterate over sequences. while loops repeat until a condition changes.",
        "rationale": "Repetition is fundamental. Loops avoid code duplication for repeated operations.",
        "applies_when": "You need to perform the same operation on multiple items",
        "does_not_apply": "When the number of repetitions is exactly 1 or when comprehension is clearer",
        "prerequisites": [2],
        "feature_idx": 4,
        "feature_name": "for_density",
        "difficulty": 2,
    },
    {
        "id": 4,
        "name": "comprehension",
        "category": "grammar",
        "statement": "List/dict/set comprehensions express transformations compactly: [expr for x in seq if cond]",
        "rationale": "Comprehensions combine mapping and filtering into a single declarative expression.",
        "applies_when": "You are building a collection from another collection with simple transforms",
        "does_not_apply": "When the transformation logic is complex or has side effects",
        "prerequisites": [3],
        "feature_idx": 9,
        "feature_name": "comprehension_density",
        "difficulty": 2,
    },
    {
        "id": 5,
        "name": "exception_handling",
        "category": "grammar",
        "statement": "try/except/finally handles errors. try runs code, except catches failures, finally always executes.",
        "rationale": "Programs must handle failures gracefully. Exceptions separate error handling from normal logic.",
        "applies_when": "An operation may fail and the program must recover or report gracefully",
        "does_not_apply": "When failure means the program should crash immediately (e.g., invariant violation)",
        "prerequisites": [2],
        "feature_idx": 6,
        "feature_name": "try_density",
        "difficulty": 2,
    },
    {
        "id": 6,
        "name": "scope_and_naming",
        "category": "semantic",
        "statement": "Names have scope: local (inside function), enclosing (closure), global (module), builtin.",
        "rationale": "Scope prevents name collisions and controls visibility. LEGB rule resolves names.",
        "applies_when": "Variables are defined inside functions or modules and need controlled visibility",
        "does_not_apply": "When all names are unique and visibility is not a concern",
        "prerequisites": [0, 1],
        "feature_idx": 39,
        "feature_name": "nesting",
        "difficulty": 3,
    },
    {
        "id": 7,
        "name": "decorators",
        "category": "grammar",
        "statement": "Decorators modify function behavior: @decorator def func(): ... wraps func with additional logic.",
        "rationale": "Decorators separate cross-cutting concerns (logging, caching, validation) from core logic.",
        "applies_when": "You need to add behavior to functions without modifying their body",
        "does_not_apply": "When the behavior is specific to one function and not reusable",
        "prerequisites": [0, 6],
        "feature_idx": 10,
        "feature_name": "decorator_density",
        "difficulty": 3,
    },
    {
        "id": 8,
        "name": "async_await",
        "category": "semantic",
        "statement": "async def defines a coroutine. await suspends execution until an awaitable completes.",
        "rationale": "Async enables concurrent I/O without threads. Coroutines yield control cooperatively.",
        "applies_when": "You have I/O-bound work (network, disk) that should not block other operations",
        "does_not_apply": "When work is CPU-bound or when simplicity matters more than concurrency",
        "prerequisites": [0, 6],
        "feature_idx": 12,
        "feature_name": "async_density",
        "difficulty": 4,
    },
    {
        "id": 9,
        "name": "type_annotations",
        "category": "semantic",
        "statement": "Type annotations specify expected types: def add(a: int, b: int) -> int",
        "rationale": "Annotations enable static type checking, documentation, and IDE support.",
        "applies_when": "You want type safety, better documentation, or IDE autocompletion",
        "does_not_apply": "When types are dynamic by design or when prototyping rapidly",
        "prerequisites": [0, 1],
        "feature_idx": 17,
        "feature_name": "annassign_density",
        "difficulty": 3,
    },
    {
        "id": 10,
        "name": "context_managers",
        "category": "grammar",
        "statement": "with statement manages resources: with open(f) as fh: ... guarantees cleanup.",
        "rationale": "Context managers ensure resources are released even on exceptions.",
        "applies_when": "You acquire a resource (file, lock, connection) that must be released",
        "does_not_apply": "When the resource does not need explicit cleanup",
        "prerequisites": [5],
        "feature_idx": 8,
        "feature_name": "with_density",
        "difficulty": 3,
    },
    {
        "id": 11,
        "name": "generators",
        "category": "semantic",
        "statement": "Generators produce values lazily: yield pauses execution, next() resumes it.",
        "rationale": "Generators enable streaming computation without materializing entire sequences in memory.",
        "applies_when": "You produce a sequence of values and want lazy evaluation or memory efficiency",
        "does_not_apply": "When you need random access to all values simultaneously",
        "prerequisites": [3, 6],
        "feature_idx": 13,
        "feature_name": "yield_density",
        "difficulty": 4,
    },
    {
        "id": 12,
        "name": "inheritance",
        "category": "semantic",
        "statement": "A class can inherit from another: class Child(Parent): ... Child gets Parent's methods.",
        "rationale": "Inheritance enables code reuse and polymorphism. Subclasses specialize parent behavior.",
        "applies_when": "You have an is-a relationship between types and want to share implementation",
        "does_not_apply": "When the relationship is has-a (use composition) or when types are unrelated",
        "prerequisites": [1, 6],
        "feature_idx": 1,
        "feature_name": "class_density",
        "difficulty": 4,
    },
    {
        "id": 13,
        "name": "metaprogramming",
        "category": "semantic",
        "statement": "Metaclasses and dynamic attributes modify class behavior at creation time.",
        "rationale": "Metaprogramming enables frameworks that shape class definitions automatically.",
        "applies_when": "You are building a framework that needs to intercept or modify class creation",
        "does_not_apply": "In application code where simplicity and readability matter more than flexibility",
        "prerequisites": [7, 12, 9],
        "feature_idx": 10,
        "feature_name": "decorator_density",
        "difficulty": 5,
    },
    {
        "id": 14,
        "name": "optimization_refactor",
        "category": "optimization",
        "statement": "Refactoring transforms code to improve performance while preserving behavior.",
        "rationale": "Optimization trades readability for speed. Only optimize where profiling shows bottlenecks.",
        "applies_when": "Profiling identifies a bottleneck and the optimization preserves correctness",
        "does_not_apply": "When the code is already fast enough or when optimization breaks readability",
        "prerequisites": [4, 6, 11],
        "feature_idx": 39,
        "feature_name": "nesting",
        "difficulty": 5,
    },
]


class CoreMLGenerativeRules:
    """Teaches generative rules of Python, not examples.

    Philosophy:
      Rules -> Principles -> Reasoning -> Examples -> Experience

    NOT:
      Millions of examples -> Hope the rules emerge

    Each rule has:
      - statement: what the rule is
      - rationale: why it exists
      - applies_when: when to use it
      - does_not_apply: when NOT to use it
      - prerequisites: which rules must be mastered first
      - difficulty: 1 (simple) to 5 (advanced)

    Prerequisite chain (like math education):
      function_definition (1) -> class_definition (1) -> control_flow (1)
        -> loop_iteration (2) -> comprehension (2)
        -> exception_handling (2) -> context_managers (3)
        -> scope_and_naming (3) -> decorators (3)
        -> async_await (4) -> generators (4) -> inheritance (4)
        -> metaprogramming (5) -> optimization_refactor (5)

    You cannot learn async before functions.
    You cannot learn generators before loops.
    You cannot learn metaprogramming before decorators, inheritance, and type annotations.

    Each lesson tests RULE UNDERSTANDING, not pattern matching:
      1. "Does this code use rule X?" (recognition)
      2. "Which rule is dominant here?" (discrimination)
      3. "Is rule X applicable here?" (applicability)
      4. "What happens if we apply rule X?" (transformation)
      5. "Which rule is missing?" (diagnosis)

    Mastery tracking:
      - Each rule has a mastery score (0.0 to 1.0)
      - A rule is 'mastered' when accuracy > 80% across all question types
      - Prerequisites must be mastered before advancing
      - Progress is persistent (SQLite)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "progress_db": PROGRESS_DB,
                "lessons_per_rule": 200,
                "epochs": 300,
                "learning_rate": 0.01,
                "mastery_threshold": 0.8,
            },
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()
        self.initMasteryDb()

    def Run(self, command, params=None):
        params = params or {}
        if command == "list_rules":
            return self.cmdListRules(params)
        if command == "show_prerequisites":
            return self.cmdShowPrerequisites(params)
        if command == "gen_rule_lesson":
            return self.cmdGenRuleLesson(params)
        if command == "run_rule_lesson":
            return self.cmdRunRuleLesson(params)
        if command == "run_rule_curriculum":
            return self.cmdRunRuleCurriculum(params)
        if command == "train_rule":
            return self.cmdTrainRule(params)
        if command == "train_all_rules":
            return self.cmdTrainAllRules(params)
        if command == "track_mastery":
            return self.cmdTrackMastery(params)
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

    def initMasteryDb(self):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rule_mastery (
                rule_id INTEGER PRIMARY KEY,
                rule_name TEXT,
                category TEXT,
                difficulty INTEGER,
                mastery_score REAL DEFAULT 0.0,
                lessons_total INTEGER DEFAULT 0,
                lessons_correct INTEGER DEFAULT 0,
                is_mastered INTEGER DEFAULT 0,
                last_practiced REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS rule_lesson_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                question_type TEXT,
                domain TEXT,
                difficulty INTEGER,
                correct INTEGER,
                model_answer TEXT,
                expected_answer TEXT,
                explanation TEXT,
                timestamp REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS prerequisite_status (
                rule_id INTEGER,
                prerequisite_id INTEGER,
                prerequisite_mastered INTEGER DEFAULT 0,
                PRIMARY KEY (rule_id, prerequisite_id)
            );
        """)
        for rule in RULES:
            conn.execute(
                "INSERT OR IGNORE INTO rule_mastery (rule_id, rule_name, category, difficulty) VALUES (?,?,?,?)",
                (rule["id"], rule["name"], rule["category"], rule["difficulty"])
            )
            for prereqId in rule["prerequisites"]:
                conn.execute(
                    "INSERT OR IGNORE INTO prerequisite_status (rule_id, prerequisite_id) VALUES (?,?)",
                    (rule["id"], prereqId)
                )
        conn.commit()
        conn.close()

    def clamp(self, value, lo=0.0, hi=1.0):
        return max(lo, min(hi, value))

    def noiseForDifficulty(self, difficulty):
        return {1: 0.02, 2: 0.05, 3: 0.08, 4: 0.12, 5: 0.18}.get(difficulty, 0.08)

    def deltaForDifficulty(self, difficulty):
        return {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.3, 5: 0.15}.get(difficulty, 0.5)

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
            row = conn.execute(
                "SELECT is_mastered FROM rule_mastery WHERE rule_id=?", (prereqId,)
            ).fetchone()
            if not row or row[0] == 0:
                conn.close()
                return False
        conn.close()
        return True

    def createRuleLesson(self, ruleId, domain=None):
        """Create a lesson that tests understanding of a specific rule.

        Question types (progressive):
          1. recognition: "Does this code use rule X?"
          2. discrimination: "Which rule is dominant here?"
          3. applicability: "Is rule X applicable here?"
          4. transformation: "What happens if we apply rule X?"
          5. diagnosis: "Which rule is missing?"
        """
        rule = self.getRuleById(ruleId)
        if rule is None:
            return None
        if domain is None:
            domain = random.choice(DOMAINS)
        profile = DOMAIN_PROFILES[domain]
        noise = self.noiseForDifficulty(rule["difficulty"])
        deltaScale = self.deltaForDifficulty(rule["difficulty"])
        baseVector = self.profileToVector(profile, noise)
        questionType = random.choice([
            "recognition", "discrimination", "applicability",
            "transformation", "diagnosis"
        ])

        if questionType == "recognition":
            usesRule = random.random() > 0.4
            features = list(baseVector)
            if usesRule:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.3 * deltaScale)
            else:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] - 0.2 * deltaScale)
            expected = 0 if usesRule else 1
            explanation = "recognition: " + rule["name"] + " is " + ("present" if usesRule else "absent") + " (feature=" + rule["feature_name"] + ")"

        elif questionType == "discrimination":
            features = list(baseVector)
            ruleIds = [r["id"] for r in RULES if r["difficulty"] <= rule["difficulty"]]
            dominantId = random.choice(ruleIds)
            dominantRule = self.getRuleById(dominantId)
            features[dominantRule["feature_idx"]] = self.clamp(features[dominantRule["feature_idx"]] + 0.4 * deltaScale)
            expected = dominantId
            explanation = "discrimination: dominant rule is " + dominantRule["name"]

        elif questionType == "applicability":
            applicable = random.random() > 0.3
            features = list(baseVector)
            if applicable:
                features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.2 * deltaScale)
            expected = 0 if applicable else 1
            explanation = "applicability: " + rule["name"] + " " + ("applies" if applicable else "does not apply") + " — " + (rule["applies_when"] if applicable else rule["does_not_apply"])

        elif questionType == "transformation":
            features = list(baseVector)
            features[rule["feature_idx"]] = self.clamp(features[rule["feature_idx"]] + 0.25 * deltaScale)
            expected = ruleId
            explanation = "transformation: applying " + rule["name"] + " increases " + rule["feature_name"]

        else:
            missingId = random.choice([r["id"] for r in RULES if r["difficulty"] <= rule["difficulty"]])
            missingRule = self.getRuleById(missingId)
            features = list(baseVector)
            features[missingRule["feature_idx"]] = self.clamp(0.05)
            expected = missingId
            explanation = "diagnosis: " + missingRule["name"] + " is missing (near-zero " + missingRule["feature_name"] + ")"

        return {
            "rule_id": ruleId,
            "rule_name": rule["name"],
            "category": rule["category"],
            "difficulty": rule["difficulty"],
            "domain": domain,
            "question_type": questionType,
            "features": features,
            "expected_answer": expected,
            "explanation": explanation,
            "statement": rule["statement"],
            "rationale": rule["rationale"],
            "applies_when": rule["applies_when"],
            "does_not_apply": rule["does_not_apply"],
        }

    def generateRuleTrainingData(self, ruleId, samplesPerDomain=None):
        if samplesPerDomain is None:
            samplesPerDomain = self.state["config"]["lessons_per_rule"]
        episodes = []
        sampleIdx = 0
        for domain in DOMAINS:
            for _ in range(samplesPerDomain):
                lesson = self.createRuleLesson(ruleId, domain)
                if lesson is None:
                    continue
                target = self.makeTarget(lesson["expected_answer"])
                episodes.append({
                    "episode": sampleIdx,
                    "num_nodes": 1,
                    "steps": [{"state": lesson["features"], "action": target, "reward": 1.0}],
                })
                sampleIdx += 1
        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "rule_id": ruleId,
                "samples": sampleIdx,
                "source": "generative_rule_lesson",
            },
        }

    def runInference(self, weightsPath, features):
        if not os.path.exists(weightsPath):
            return None
        statePath = os.path.join(TRAINING_DIR, "rule_inference.bin")
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

    def logRuleLesson(self, lesson, correct, modelAnswer):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        conn.execute(
            "INSERT INTO rule_lesson_log (rule_id, question_type, domain, difficulty, correct, model_answer, expected_answer, explanation, timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
            (lesson["rule_id"], lesson["question_type"], lesson["domain"], lesson["difficulty"],
             1 if correct else 0, str(modelAnswer), str(lesson["expected_answer"]),
             lesson["explanation"], time.time())
        )
        conn.execute(
            "UPDATE rule_mastery SET lessons_total=lessons_total+1, lessons_correct=lessons_correct+?, mastery_score=CAST(lessons_correct+? AS REAL)/CAST(lessons_total+1 AS REAL), is_mastered=CASE WHEN CAST(lessons_correct+? AS REAL)/CAST(lessons_total+1 AS REAL) >= ? THEN 1 ELSE 0 END, last_practiced=? WHERE rule_id=?",
            (1 if correct else 0, 1 if correct else 0, 1 if correct else 0, self.state["config"]["mastery_threshold"], time.time(), lesson["rule_id"])
        )
        conn.commit()
        conn.close()

    def cmdListRules(self, params):
        rules = []
        for rule in RULES:
            rules.append({
                "id": rule["id"],
                "name": rule["name"],
                "category": rule["category"],
                "difficulty": rule["difficulty"],
                "statement": rule["statement"],
                "rationale": rule["rationale"],
                "applies_when": rule["applies_when"],
                "does_not_apply": rule["does_not_apply"],
                "prerequisites": rule["prerequisites"],
                "prerequisite_names": [self.getRuleById(p)["name"] for p in rule["prerequisites"] if self.getRuleById(p)],
            })
        return (1, {"rules": rules, "total": len(rules)}, None)

    def cmdShowPrerequisites(self, params):
        ruleId = int(self.p(params, "rule_id", 0))
        rule = self.getRuleById(ruleId)
        if rule is None:
            return (0, None, ("NOT_FOUND", "Rule not found: " + str(ruleId), 0))
        chain = []
        visited = set()
        def buildChain(rid, depth):
            if rid in visited:
                return
            visited.add(rid)
            r = self.getRuleById(rid)
            if r and r["prerequisites"]:
                for prereqId in r["prerequisites"]:
                    prereq = self.getRuleById(prereqId)
                    if prereq:
                        chain.append({
                            "rule": prereq["name"],
                            "difficulty": prereq["difficulty"],
                            "depth": depth,
                            "needed_for": r["name"],
                        })
                        buildChain(prereqId, depth + 1)
        buildChain(ruleId, 1)
        return (1, {
            "rule": rule["name"],
            "difficulty": rule["difficulty"],
            "prerequisite_chain": chain,
            "can_study": self.prerequisitesMastered(ruleId),
        }, None)

    def cmdGenRuleLesson(self, params):
        ruleId = int(self.p(params, "rule_id", 0))
        domain = self.p(params, "domain")
        lesson = self.createRuleLesson(ruleId, domain)
        if lesson is None:
            return (0, None, ("GEN_ERROR", "Failed to create lesson", 0))
        return (1, lesson, None)

    def cmdRunRuleLesson(self, params):
        try:
            ruleId = int(self.p(params, "rule_id", 0))
            domain = self.p(params, "domain")
            lesson = self.createRuleLesson(ruleId, domain)
            if lesson is None:
                return (0, None, ("LESSON_ERROR", "Failed", 0))
            weightsPath = os.path.join(EXPERTS_DIR, "rule_" + str(ruleId) + "_" + lesson["domain"] + ".weights.bin")
            if not os.path.exists(weightsPath):
                weightsPath = os.path.join(EXPERTS_DIR, lesson["domain"] + ".weights.bin")
            modelOutput = self.runInference(weightsPath, lesson["features"])
            if modelOutput is None:
                return (1, {
                    "lesson": lesson,
                    "model_answer": None,
                    "correct": False,
                    "explanation": "No expert weights found",
                }, None)
            modelAnswer = modelOutput.index(max(modelOutput))
            correct = modelAnswer == lesson["expected_answer"]
            self.logRuleLesson(lesson, correct, modelAnswer)
            return (1, {
                "rule_id": lesson["rule_id"],
                "rule_name": lesson["rule_name"],
                "difficulty": lesson["difficulty"],
                "domain": lesson["domain"],
                "question_type": lesson["question_type"],
                "expected_answer": lesson["expected_answer"],
                "model_answer": modelAnswer,
                "correct": correct,
                "explanation": lesson["explanation"],
                "statement": lesson["statement"],
                "rationale": lesson["rationale"],
                "model_output": [round(v, 4) for v in modelOutput],
            }, None)
        except Exception as e:
            return (0, None, ("RUN_ERROR", str(e), 0))

    def cmdRunRuleCurriculum(self, params):
        try:
            lessonsPerRule = int(self.p(params, "lessons", 10))
            rulesFilter = self.p(params, "rules")
            results = []
            totalCorrect = 0
            totalLessons = 0
            for rule in RULES:
                if rulesFilter and rule["id"] not in rulesFilter:
                    continue
                ruleCorrect = 0
                ruleTotal = 0
                for _ in range(lessonsPerRule):
                    ok, data, err = self.cmdRunRuleLesson({"rule_id": rule["id"]})
                    if ok and data.get("model_answer") is not None:
                        ruleTotal += 1
                        if data["correct"]:
                            ruleCorrect += 1
                if ruleTotal > 0:
                    results.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "difficulty": rule["difficulty"],
                        "lessons": ruleTotal,
                        "correct": ruleCorrect,
                        "accuracy": round(ruleCorrect / ruleTotal, 4),
                    })
                    totalCorrect += ruleCorrect
                    totalLessons += ruleTotal
            return (1, {
                "total_lessons": totalLessons,
                "total_correct": totalCorrect,
                "overall_accuracy": round(totalCorrect / totalLessons, 4) if totalLessons > 0 else 0,
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("CURRICULUM_ERROR", str(e), 0))

    def cmdTrainRule(self, params):
        try:
            ruleId = int(self.p(params, "rule_id", 0))
            domain = self.p(params, "domain", "vscode")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            samples = int(self.p(params, "samples", self.state["config"]["lessons_per_rule"]))
            rule = self.getRuleById(ruleId)
            if rule is None:
                return (0, None, ("NOT_FOUND", "Rule not found", 0))
            data = self.generateRuleTrainingData(ruleId, samples)
            trainingPath = os.path.join(TRAINING_DIR, "rule_" + str(ruleId) + "_" + domain + "_training.json")
            with open(trainingPath, "w") as f:
                json.dump(data, f)
            weightsOut = os.path.join(EXPERTS_DIR, "rule_" + str(ruleId) + "_" + domain + ".weights.bin")
            initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if not os.path.exists(initWeights):
                initWeights = None
            coretotch = self.state["config"]["coretotch_bin"]
            cmdArgs = [coretotch, "train", trainingPath, weightsOut, str(epochs), str(0.01)]
            if initWeights:
                cmdArgs.append(initWeights)
            proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
            output = proc.stderr + proc.stdout
            lossLines = [l for l in output.split("\n") if "Loss:" in l]
            firstLoss = lossLines[0].strip() if lossLines else ""
            lastLoss = lossLines[-1].strip() if lossLines else ""
            testCorrect = 0
            testTotal = min(20, samples)
            for _ in range(testTotal):
                lesson = self.createRuleLesson(ruleId, domain)
                if lesson is None:
                    continue
                modelOutput = self.runInference(weightsOut, lesson["features"])
                if modelOutput is None:
                    continue
                if modelOutput.index(max(modelOutput)) == lesson["expected_answer"]:
                    testCorrect += 1
            accuracy = testCorrect / testTotal if testTotal > 0 else 0
            isMastered = accuracy >= self.state["config"]["mastery_threshold"]
            conn = sqlite3.connect(self.state["config"]["progress_db"])
            conn.execute(
                "UPDATE rule_mastery SET mastery_score=?, lessons_total=lessons_total+?, lessons_correct=lessons_correct+?, is_mastered=?, last_practiced=? WHERE rule_id=?",
                (round(accuracy, 4), testTotal, testCorrect, 1 if isMastered else 0, time.time(), ruleId)
            )
            conn.commit()
            conn.close()
            return (1, {
                "rule_id": ruleId,
                "rule_name": rule["name"],
                "domain": domain,
                "weights": weightsOut,
                "epochs": epochs,
                "samples": data["config"]["samples"],
                "first_loss": firstLoss,
                "last_loss": lastLoss,
                "accuracy": round(accuracy, 4),
                "mastered": isMastered,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ERROR", str(e), 0))

    def cmdTrainAllRules(self, params):
        try:
            domain = self.p(params, "domain", "vscode")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            samples = int(self.p(params, "samples", self.state["config"]["lessons_per_rule"]))
            results = []
            for rule in RULES:
                if not self.prerequisitesMastered(rule["id"]):
                    results.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "skipped": True,
                        "reason": "Prerequisites not mastered",
                    })
                    continue
                ok, data, err = self.cmdTrainRule({
                    "rule_id": rule["id"], "domain": domain,
                    "epochs": epochs, "samples": samples
                })
                if ok:
                    results.append({
                        "rule_id": data["rule_id"],
                        "rule_name": data["rule_name"],
                        "first_loss": data["first_loss"],
                        "last_loss": data["last_loss"],
                        "accuracy": data["accuracy"],
                        "mastered": data["mastered"],
                        "skipped": False,
                    })
                else:
                    results.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "error": str(err),
                        "skipped": False,
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
            return (0, None, ("TRAIN_ALL_ERROR", str(e), 0))

    def cmdTrackMastery(self, params):
        conn = sqlite3.connect(self.state["config"]["progress_db"])
        rows = conn.execute(
            "SELECT rule_id, rule_name, category, difficulty, mastery_score, lessons_total, lessons_correct, is_mastered, last_practiced FROM rule_mastery ORDER BY difficulty, rule_id"
        ).fetchall()
        conn.close()
        mastery = []
        for row in rows:
            mastery.append({
                "rule_id": row[0],
                "rule_name": row[1],
                "category": row[2],
                "difficulty": row[3],
                "mastery_score": round(row[4], 4),
                "lessons_total": row[5],
                "lessons_correct": row[6],
                "is_mastered": row[7] == 1,
            })
        return (1, {"mastery": mastery, "total": len(mastery)}, None)

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "rules": len(RULES),
            "categories": list(set(r["category"] for r in RULES)),
            "difficulty_range": [1, 5],
            "question_types": ["recognition", "discrimination", "applicability", "transformation", "diagnosis"],
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
