#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLTrainingGenerator.py
#[@SUMMARY] Generates synthetic training data from Python's formal grammar, AST rules, semantic rules, error categories, and library specs — no GitHub scraping needed
#[@CLASS] CoreMLTrainingGenerator
#[@METHOD] gen_grammar, gen_ast, gen_semantic, gen_error, gen_library, gen_all, train_generated, train_all_generated
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
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_generated"

DOMAINS = ["vscode", "browser", "dashboard", "mobile", "tablet"]
DOMAIN_INDICES = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}
DOMAIN_PROFILES = {
    "vscode": {
        "func_density": 0.8, "class_density": 0.6, "import_density": 0.9,
        "if_density": 0.7, "for_density": 0.5, "try_density": 0.4,
        "decorator_density": 0.3, "lambda_density": 0.2, "comprehension_density": 0.4,
        "async_density": 0.1, "with_density": 0.3, "nesting": 0.6,
        "run_method": 1.0, "tuple3": 0.9, "self_state": 0.8, "bcl_header": 0.9,
        "no_print": 1.0, "no_self_underscore": 1.0, "config_import": 0.8,
        "stdlib": ["os", "sys", "json", "re", "sqlite3", "subprocess", "struct", "time"],
        "third_party": ["coremltools"],
    },
    "browser": {
        "func_density": 0.6, "class_density": 0.7, "import_density": 0.7,
        "if_density": 0.6, "for_density": 0.6, "try_density": 0.3,
        "decorator_density": 0.1, "lambda_density": 0.3, "comprehension_density": 0.5,
        "async_density": 0.0, "with_density": 0.2, "nesting": 0.7,
        "run_method": 0.8, "tuple3": 0.7, "self_state": 0.7, "bcl_header": 0.7,
        "no_print": 0.9, "no_self_underscore": 0.9, "config_import": 0.6,
        "stdlib": ["os", "sys", "json", "math", "collections", "itertools"],
        "third_party": [],
    },
    "dashboard": {
        "func_density": 0.5, "class_density": 0.8, "import_density": 0.6,
        "if_density": 0.8, "for_density": 0.7, "try_density": 0.5,
        "decorator_density": 0.2, "lambda_density": 0.1, "comprehension_density": 0.3,
        "async_density": 0.0, "with_density": 0.4, "nesting": 0.8,
        "run_method": 0.7, "tuple3": 0.6, "self_state": 0.6, "bcl_header": 0.6,
        "no_print": 0.8, "no_self_underscore": 0.8, "config_import": 0.5,
        "stdlib": ["os", "sys", "json", "datetime", "collections"],
        "third_party": [],
    },
    "mobile": {
        "func_density": 0.7, "class_density": 0.5, "import_density": 0.8,
        "if_density": 0.5, "for_density": 0.4, "try_density": 0.6,
        "decorator_density": 0.4, "lambda_density": 0.2, "comprehension_density": 0.3,
        "async_density": 0.3, "with_density": 0.3, "nesting": 0.5,
        "run_method": 0.6, "tuple3": 0.5, "self_state": 0.5, "bcl_header": 0.5,
        "no_print": 0.7, "no_self_underscore": 0.7, "config_import": 0.4,
        "stdlib": ["os", "sys", "json", "time", "struct", "subprocess"],
        "third_party": ["coremltools", "numpy"],
    },
    "tablet": {
        "func_density": 0.6, "class_density": 0.6, "import_density": 0.7,
        "if_density": 0.5, "for_density": 0.5, "try_density": 0.3,
        "decorator_density": 0.5, "lambda_density": 0.2, "comprehension_density": 0.4,
        "async_density": 0.0, "with_density": 0.2, "nesting": 0.6,
        "run_method": 0.5, "tuple3": 0.4, "self_state": 0.4, "bcl_header": 0.4,
        "no_print": 0.6, "no_self_underscore": 0.6, "config_import": 0.3,
        "stdlib": ["os", "sys", "json", "math"],
        "third_party": ["PyQt6"],
    },
}

GRAMMAR_NODE_TYPES = [
    "FunctionDef", "AsyncFunctionDef", "ClassDef", "Return", "Delete",
    "Assign", "AugAssign", "AnnAssign", "For", "AsyncFor", "While",
    "If", "With", "AsyncWith", "Raise", "Try", "Assert", "Import",
    "ImportFrom", "Global", "Nonlocal", "Expr", "Pass", "Break",
    "Continue", "BoolOp", "BinOp", "UnaryOp", "Lambda", "IfExp",
    "Dict", "Set", "ListComp", "SetComp", "DictComp", "GeneratorExp",
    "Await", "Yield", "YieldFrom", "Compare", "Call", "FormattedValue",
    "JoinedStr", "Constant", "Attribute", "Subscript", "Starred",
    "Name", "List", "Tuple", "Slice",
]

IDIOM_NAMES = [
    "context_manager", "try_except_finally", "list_comprehension",
    "dict_comprehension", "generator_expression", "decorator_property",
    "decorator_staticmethod", "decorator_classmethod", "decorator_custom",
    "lambda_inline", "ternary", "walrus", "fstring", "star_args",
    "kwargs_unpack", "isinstance_check", "type_hint", "enum_pattern",
    "singleton_init", "factory_method", "builder_pattern", "observer_pattern",
    "strategy_pattern", "iterator_protocol", "context_manager_protocol",
    "descriptor_protocol", "metaclass_usage", "abstract_base", "dataclass",
    "namedtuple", "typing_generic", "async_def", "await_call", "async_for",
    "async_with",
]

LIBRARY_SLOTS = [
    "os", "sys", "json", "re", "sqlite3", "struct", "time", "datetime",
    "subprocess", "ast", "collections", "itertools", "functools", "typing",
    "pathlib", "shutil", "threading", "multiprocessing", "asyncio", "logging",
    "unittest", "pytest", "numpy", "pandas", "torch", "tensorflow", "sklearn",
    "coremltools", "PyQt6", "PyQt5", "tkinter", "flask", "django", "fastapi",
    "requests", "urllib", "socket", "http", "email", "hashlib",
]

STYLE_NAMES = [
    "run_method", "tuple3_return", "self_state", "self_config", "p_method",
    "pascal_case_class", "uppercase_const", "no_print", "no_self_underscore",
    "no_decorator", "bcl_header", "config_import", "init_signature",
    "read_state_method", "set_config_method", "dispatch_run", "no_tabs",
    "no_enum", "no_trailing_ws",
]

ERROR_CATEGORIES = [
    "missing_colon", "indentation_error", "undefined_variable",
    "wrong_arg_count", "circular_import", "recursion_error",
    "type_mismatch", "attribute_error", "key_error", "index_error",
    "name_error", "syntax_error", "value_error", "import_error",
    "annotation_error", "scope_leak", "mutable_default", "shadow_builtin",
]


class CoreMLTrainingGenerator:
    """Generates synthetic training data from Python's formal specification.

    Instead of scraping GitHub, we generate training examples directly from:
      - Grammar rules (finite set of valid constructs)
      - AST node types (49 finite types)
      - Semantic rules (scope, closure, async, inheritance)
      - Error categories (18 finite categories)
      - Library specs (40 finite module slots)

    Each generator produces feature vectors that represent valid combinations
    of its domain. The grammar is finite. The combinations are unlimited.
    But the building blocks are finite.

    Pipeline:
      Grammar Generator → Grammar Expert
      AST Generator → AST Expert
      Semantic Generator → Semantic Expert
      Error Generator → Error Expert
      Library Generator → Library Expert

    Each domain (vscode/browser/dashboard/mobile/tablet) has a different
    profile — vscode code has high func_density + run_method + tuple3,
    tablet code has high decorator_density + PyQt6 imports, etc.

    The generator creates N samples per domain by sampling from the domain
    profile with noise. This produces unlimited training data from finite rules.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "samples_per_domain": 200,
                "epochs": 300,
                "learning_rate": 0.01,
                "noise_level": 0.1,
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
        if command == "gen_grammar":
            return self.cmdGenGrammar(params)
        if command == "gen_ast":
            return self.cmdGenAst(params)
        if command == "gen_semantic":
            return self.cmdGenSemantic(params)
        if command == "gen_error":
            return self.cmdGenError(params)
        if command == "gen_library":
            return self.cmdGenLibrary(params)
        if command == "gen_all":
            return self.cmdGenAll(params)
        if command == "train_generated":
            return self.cmdTrainGenerated(params)
        if command == "train_all_generated":
            return self.cmdTrainAllGenerated(params)
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

    def makeTarget(self, domainIndex):
        target = [0.0] * OUTPUT_DIM
        target[domainIndex] = 1.0
        return target

    def genGrammarVector(self, domainProfile):
        """Generate a 40D grammar feature vector from a domain profile."""
        p = domainProfile
        vector = []
        vector.append(self.addNoise(p["func_density"]))
        vector.append(self.addNoise(p["class_density"]))
        vector.append(self.addNoise(p["import_density"]))
        vector.append(self.addNoise(p["if_density"]))
        vector.append(self.addNoise(p["for_density"]))
        vector.append(self.addNoise(p["while_density"] if "while_density" in p else p["for_density"] * 0.3))
        vector.append(self.addNoise(p["try_density"]))
        vector.append(self.addNoise(p.get("except_density", p["try_density"] * 0.9)))
        vector.append(self.addNoise(p["with_density"]))
        vector.append(self.addNoise(p["comprehension_density"]))
        vector.append(self.addNoise(p["decorator_density"]))
        vector.append(self.addNoise(p["lambda_density"]))
        vector.append(self.addNoise(p["async_density"]))
        vector.append(self.addNoise(p.get("yield_density", p["async_density"] * 0.5)))
        vector.append(self.addNoise(p.get("return_density", p["func_density"] * 0.8)))
        vector.append(self.addNoise(p.get("assign_density", 0.5)))
        vector.append(self.addNoise(p.get("augassign_density", 0.2)))
        vector.append(self.addNoise(p.get("annassign_density", p["decorator_density"] * 0.3)))
        vector.append(self.addNoise(p.get("raise_density", p["try_density"] * 0.5)))
        vector.append(self.addNoise(p.get("assert_density", 0.1)))
        vector.append(self.addNoise(p.get("global_density", 0.05)))
        vector.append(self.addNoise(p.get("nonlocal_density", 0.05)))
        vector.append(self.addNoise(p.get("pass_density", 0.1)))
        vector.append(self.addNoise(p.get("break_density", 0.1)))
        vector.append(self.addNoise(p.get("continue_density", 0.05)))
        vector.append(self.addNoise(p.get("boolop_density", 0.2)))
        vector.append(self.addNoise(p.get("binop_density", 0.4)))
        vector.append(self.addNoise(p.get("unaryop_density", 0.15)))
        vector.append(self.addNoise(p.get("ifexp_density", p["lambda_density"] * 0.5)))
        vector.append(self.addNoise(p.get("dict_density", 0.3)))
        vector.append(self.addNoise(p.get("set_density", 0.1)))
        vector.append(self.addNoise(p.get("list_density", 0.3)))
        vector.append(self.addNoise(p.get("tuple_density", 0.2)))
        vector.append(self.addNoise(p.get("call_density", p["func_density"] * 0.7)))
        vector.append(self.addNoise(p.get("attribute_density", p["class_density"] * 0.8)))
        vector.append(self.addNoise(p.get("subscript_density", 0.2)))
        vector.append(self.addNoise(p.get("compare_density", p["if_density"] * 0.5)))
        vector.append(self.addNoise(p.get("constant_density", 0.6)))
        vector.append(self.addNoise(p.get("name_density", 0.8)))
        vector.append(self.addNoise(p["nesting"]))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    def genAstVector(self, domainProfile):
        """Generate a 40D AST node distribution vector."""
        p = domainProfile
        nodeWeights = {
            "FunctionDef": p["func_density"],
            "AsyncFunctionDef": p["async_density"],
            "ClassDef": p["class_density"],
            "Return": p.get("return_density", p["func_density"] * 0.8),
            "Assign": p.get("assign_density", 0.5),
            "AugAssign": p.get("augassign_density", 0.2),
            "For": p["for_density"],
            "AsyncFor": p["async_density"] * 0.5,
            "While": p.get("while_density", p["for_density"] * 0.3),
            "If": p["if_density"],
            "With": p["with_density"],
            "AsyncWith": p["async_density"] * 0.3,
            "Try": p["try_density"],
            "Raise": p.get("raise_density", p["try_density"] * 0.5),
            "Import": p["import_density"],
            "ImportFrom": p["import_density"] * 0.8,
            "Pass": p.get("pass_density", 0.1),
            "Break": p.get("break_density", 0.1),
            "Continue": p.get("continue_density", 0.05),
            "BoolOp": p.get("boolop_density", 0.2),
            "BinOp": p.get("binop_density", 0.4),
            "UnaryOp": p.get("unaryop_density", 0.15),
            "Lambda": p["lambda_density"],
            "IfExp": p.get("ifexp_density", p["lambda_density"] * 0.5),
            "Dict": p.get("dict_density", 0.3),
            "Set": p.get("set_density", 0.1),
            "ListComp": p["comprehension_density"],
            "SetComp": p["comprehension_density"] * 0.3,
            "DictComp": p["comprehension_density"] * 0.4,
            "GeneratorExp": p["comprehension_density"] * 0.5,
            "Await": p["async_density"] * 0.7,
            "Yield": p.get("yield_density", p["async_density"] * 0.5),
            "YieldFrom": p.get("yield_density", p["async_density"] * 0.3),
            "Compare": p.get("compare_density", p["if_density"] * 0.5),
            "Call": p.get("call_density", p["func_density"] * 0.7),
            "Constant": p.get("constant_density", 0.6),
            "Attribute": p.get("attribute_density", p["class_density"] * 0.8),
            "Subscript": p.get("subscript_density", 0.2),
            "Name": p.get("name_density", 0.8),
            "List": p.get("list_density", 0.3),
        }
        vector = []
        for nodeType in GRAMMAR_NODE_TYPES:
            weight = nodeWeights.get(nodeType, 0.05)
            vector.append(self.addNoise(weight))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    def genIdiomVector(self, domainProfile):
        """Generate a 40D idiom pattern vector."""
        p = domainProfile
        idiomWeights = {
            "context_manager": p["with_density"],
            "try_except_finally": p["try_density"] * 0.8,
            "list_comprehension": p["comprehension_density"],
            "dict_comprehension": p["comprehension_density"] * 0.4,
            "generator_expression": p["comprehension_density"] * 0.5,
            "decorator_property": p["decorator_density"] * 0.3,
            "decorator_staticmethod": p["decorator_density"] * 0.2,
            "decorator_classmethod": p["decorator_density"] * 0.2,
            "decorator_custom": p["decorator_density"] * 0.6,
            "lambda_inline": p["lambda_density"],
            "ternary": p["lambda_density"] * 0.5,
            "walrus": 0.05,
            "fstring": 0.3,
            "star_args": 0.15,
            "kwargs_unpack": 0.15,
            "isinstance_check": 0.2,
            "type_hint": p["decorator_density"] * 0.4,
            "enum_pattern": 0.05,
            "singleton_init": p["class_density"] * 0.3,
            "factory_method": p["func_density"] * 0.2,
            "builder_pattern": 0.1,
            "observer_pattern": 0.05,
            "strategy_pattern": 0.05,
            "iterator_protocol": 0.1,
            "context_manager_protocol": p["with_density"] * 0.5,
            "descriptor_protocol": 0.05,
            "metaclass_usage": 0.02,
            "abstract_base": 0.1,
            "dataclass": p["decorator_density"] * 0.3,
            "namedtuple": 0.05,
            "typing_generic": p["decorator_density"] * 0.3,
            "async_def": p["async_density"],
            "await_call": p["async_density"] * 0.7,
            "async_for": p["async_density"] * 0.4,
            "async_with": p["async_density"] * 0.3,
        }
        vector = []
        for name in IDIOM_NAMES:
            weight = idiomWeights.get(name, 0.05)
            vector.append(self.addNoise(weight))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    def genLibraryVector(self, domainProfile):
        """Generate a 40D library import vector."""
        p = domainProfile
        vector = [0.0] * INPUT_DIM
        for i, libName in enumerate(LIBRARY_SLOTS):
            if i >= INPUT_DIM:
                break
            if libName in p["stdlib"]:
                vector[i] = self.addNoise(0.9, 0.15)
            elif libName in p["third_party"]:
                vector[i] = self.addNoise(0.8, 0.15)
            else:
                if random.random() < 0.1:
                    vector[i] = self.addNoise(0.1, 0.1)
        totalImports = len(p["stdlib"]) + len(p["third_party"])
        if 35 < INPUT_DIM:
            vector[35] = self.addNoise(min(totalImports / 20.0, 1.0))
        if 36 < INPUT_DIM:
            vector[36] = self.addNoise(min(len(p["stdlib"]) / 10.0, 1.0))
        if 37 < INPUT_DIM:
            vector[37] = self.addNoise(min(len(p["third_party"]) / 10.0, 1.0))
        if 38 < INPUT_DIM:
            vector[38] = 1.0 if totalImports > 0 else 0.0
        if 39 < INPUT_DIM:
            vector[39] = self.addNoise(min(totalImports / 30.0, 1.0))
        return vector

    def genStyleVector(self, domainProfile):
        """Generate a 40D VBStyle compliance vector."""
        p = domainProfile
        styleWeights = {
            "run_method": p["run_method"],
            "tuple3_return": p["tuple3"],
            "self_state": p["self_state"],
            "self_config": p["self_state"] * 0.8,
            "p_method": p["run_method"] * 0.5,
            "pascal_case_class": p["class_density"] * 0.9,
            "uppercase_const": p["class_density"] * 0.6,
            "no_print": p["no_print"],
            "no_self_underscore": p["no_self_underscore"],
            "no_decorator": 1.0 - p["decorator_density"],
            "bcl_header": p["bcl_header"],
            "config_import": p["config_import"],
            "init_signature": p["class_density"] * 0.7,
            "read_state_method": p["run_method"] * 0.6,
            "set_config_method": p["run_method"] * 0.6,
            "dispatch_run": p["run_method"] * 0.8,
            "no_tabs": 0.95,
            "no_enum": 0.9,
            "no_trailing_ws": 0.95,
        }
        vector = []
        for name in STYLE_NAMES:
            weight = styleWeights.get(name, 0.1)
            vector.append(self.addNoise(weight))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    def genSemanticVector(self, domainProfile):
        """Generate a 40D semantic feature vector (scope, closure, inheritance)."""
        p = domainProfile
        vector = []
        vector.append(self.addNoise(p["class_density"] * 0.8))
        vector.append(self.addNoise(p["func_density"] * 0.7))
        vector.append(self.addNoise(p["nesting"] * 0.6))
        vector.append(self.addNoise(p["async_density"]))
        vector.append(self.addNoise(p["class_density"] * 0.5))
        vector.append(self.addNoise(p["func_density"] * 0.4))
        vector.append(self.addNoise(p["lambda_density"]))
        vector.append(self.addNoise(p["comprehension_density"] * 0.6))
        vector.append(self.addNoise(p["with_density"] * 0.7))
        vector.append(self.addNoise(p["decorator_density"] * 0.5))
        vector.append(self.addNoise(p.get("yield_density", p["async_density"] * 0.5)))
        vector.append(self.addNoise(p["try_density"] * 0.6))
        vector.append(self.addNoise(p["if_density"] * 0.5))
        vector.append(self.addNoise(p["for_density"] * 0.5))
        vector.append(self.addNoise(p.get("global_density", 0.05)))
        vector.append(self.addNoise(p.get("nonlocal_density", 0.05)))
        vector.append(self.addNoise(p["class_density"] * 0.3))
        vector.append(self.addNoise(p["func_density"] * 0.3))
        vector.append(self.addNoise(p["import_density"] * 0.4))
        vector.append(self.addNoise(p.get("annotation_density", p["decorator_density"] * 0.3)))
        for i in range(20):
            vector.append(self.addNoise(0.1 + p["nesting"] * 0.3))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    def genErrorVector(self, domainProfile):
        """Generate a 40D error pattern vector."""
        p = domainProfile
        errorBase = {
            "missing_colon": 0.05,
            "indentation_error": 0.1,
            "undefined_variable": 0.15,
            "wrong_arg_count": 0.1,
            "circular_import": p["import_density"] * 0.1,
            "recursion_error": p["func_density"] * 0.05,
            "type_mismatch": 0.15,
            "attribute_error": p["class_density"] * 0.15,
            "key_error": p.get("dict_density", 0.3) * 0.3,
            "index_error": p.get("list_density", 0.3) * 0.3,
            "name_error": 0.1,
            "syntax_error": 0.05,
            "value_error": p["try_density"] * 0.3,
            "import_error": p["import_density"] * 0.1,
            "annotation_error": p["decorator_density"] * 0.1,
            "scope_leak": p["nesting"] * 0.1,
            "mutable_default": p["func_density"] * 0.1,
            "shadow_builtin": 0.05,
        }
        vector = []
        for errName in ERROR_CATEGORIES:
            weight = errorBase.get(errName, 0.05)
            vector.append(self.addNoise(weight))
        while len(vector) < INPUT_DIM:
            vector.append(0.0)
        return vector[:INPUT_DIM]

    LAYER_GENERATORS = {
        "grammar": "genGrammarVector",
        "ast": "genAstVector",
        "idiom": "genIdiomVector",
        "library": "genLibraryVector",
        "style": "genStyleVector",
        "semantic": "genSemanticVector",
        "error": "genErrorVector",
    }

    def generateLayerData(self, layer, samplesPerDomain=None):
        """Generate training data for one layer across all 5 domains."""
        if samplesPerDomain is None:
            samplesPerDomain = self.state["config"]["samples_per_domain"]
        generatorName = self.LAYER_GENERATORS.get(layer)
        if not generatorName:
            return None
        generator = getattr(self, generatorName)
        episodes = []
        sampleIdx = 0
        for domain in DOMAINS:
            profile = DOMAIN_PROFILES[domain]
            domainIndex = DOMAIN_INDICES[domain]
            for _ in range(samplesPerDomain):
                features = generator(profile)
                target = self.makeTarget(domainIndex)
                episodes.append({
                    "episode": sampleIdx,
                    "num_nodes": 1,
                    "steps": [{"state": features, "action": target, "reward": 1.0}],
                })
                sampleIdx += 1
        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "layer": layer,
                "samples": sampleIdx,
                "samples_per_domain": samplesPerDomain,
                "source": "generated_from_grammar",
            },
        }

    def saveTrainingData(self, layer, data):
        outputPath = os.path.join(TRAINING_DIR, "gen_" + layer + "_training.json")
        with open(outputPath, "w") as f:
            json.dump(data, f)
        return outputPath

    def cmdGenGrammar(self, params):
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData("grammar", samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed to generate grammar data", 0))
        path = self.saveTrainingData("grammar", data)
        return (1, {"layer": "grammar", "path": path, "samples": data["config"]["samples"]}, None)

    def cmdGenAst(self, params):
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData("ast", samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed", 0))
        path = self.saveTrainingData("ast", data)
        return (1, {"layer": "ast", "path": path, "samples": data["config"]["samples"]}, None)

    def cmdGenSemantic(self, params):
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData("semantic", samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed", 0))
        path = self.saveTrainingData("semantic", data)
        return (1, {"layer": "semantic", "path": path, "samples": data["config"]["samples"]}, None)

    def cmdGenError(self, params):
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData("error", samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed", 0))
        path = self.saveTrainingData("error", data)
        return (1, {"layer": "error", "path": path, "samples": data["config"]["samples"]}, None)

    def cmdGenLibrary(self, params):
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData("library", samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed", 0))
        path = self.saveTrainingData("library", data)
        return (1, {"layer": "library", "path": path, "samples": data["config"]["samples"]}, None)

    def cmdGenAll(self, params):
        """Generate training data for all 7 layers."""
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        results = []
        for layer in self.LAYER_GENERATORS:
            data = self.generateLayerData(layer, samples)
            if data:
                path = self.saveTrainingData(layer, data)
                results.append({
                    "layer": layer,
                    "path": path,
                    "samples": data["config"]["samples"],
                })
        return (1, {
            "layers_generated": len(results),
            "total_samples": sum(r["samples"] for r in results),
            "results": results,
        }, None)

    def cmdTrainGenerated(self, params):
        """Train one layer expert on generated data."""
        layer = self.p(params, "layer", "grammar")
        domain = self.p(params, "domain", "vscode")
        epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
        lr = float(self.p(params, "learning_rate", self.state["config"]["learning_rate"]))
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        data = self.generateLayerData(layer, samples)
        if not data:
            return (0, None, ("GEN_ERROR", "Failed to generate " + layer, 0))
        trainingPath = self.saveTrainingData(layer, data)
        weightsOut = os.path.join(EXPERTS_DIR, "gen_" + layer + "_" + domain + ".weights.bin")
        initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
        if not os.path.exists(initWeights):
            initWeights = None
        coretotch = self.state["config"]["coretotch_bin"]
        cmdArgs = [coretotch, "train", trainingPath, weightsOut, str(epochs), str(lr)]
        if initWeights:
            cmdArgs.append(initWeights)
        proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
        output = proc.stderr + proc.stdout
        lossLines = [l for l in output.split("\n") if "Loss:" in l]
        firstLoss = lossLines[0].strip() if lossLines else ""
        lastLoss = lossLines[-1].strip() if lossLines else ""
        return (1, {
            "layer": layer,
            "domain": domain,
            "training_file": trainingPath,
            "output_weights": weightsOut,
            "epochs": epochs,
            "samples": data["config"]["samples"],
            "first_loss": firstLoss,
            "last_loss": lastLoss,
            "success": proc.returncode == 0,
        }, None)

    def cmdTrainAllGenerated(self, params):
        """Train all 7 layers x 5 domains = 35 experts on generated data."""
        epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
        samples = int(self.p(params, "samples", self.state["config"]["samples_per_domain"]))
        results = []
        for layer in self.LAYER_GENERATORS:
            data = self.generateLayerData(layer, samples)
            if not data:
                continue
            trainingPath = self.saveTrainingData(layer, data)
            for domain in DOMAINS:
                weightsOut = os.path.join(EXPERTS_DIR, "gen_" + layer + "_" + domain + ".weights.bin")
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
                results.append({
                    "layer": layer,
                    "domain": domain,
                    "first_loss": firstLoss,
                    "last_loss": lastLoss,
                    "success": proc.returncode == 0,
                })
        successCount = sum(1 for r in results if r.get("success"))
        return (1, {
            "trained": successCount,
            "total": len(results),
            "results": results,
        }, None)

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "layers": list(self.LAYER_GENERATORS.keys()),
            "domains": DOMAINS,
            "grammar_node_types": len(GRAMMAR_NODE_TYPES),
            "idiom_patterns": len(IDIOM_NAMES),
            "library_slots": len(LIBRARY_SLOTS),
            "style_features": len(STYLE_NAMES),
            "error_categories": len(ERROR_CATEGORIES),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
