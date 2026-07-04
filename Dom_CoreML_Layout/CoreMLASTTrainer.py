#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLASTTrainer.py
#[@SUMMARY] AST-structured training: grammar, idioms, libraries, style as separate expert modules
#[@CLASS] CoreMLASTTrainer
#[@METHOD] extract_ast_features, extract_grammar_vector, extract_idiom_vector, extract_library_vector, extract_style_vector, train_layer, train_all_layers, classify
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import re
import ast
import json
import time
import struct
import subprocess
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_ast"
CODEBASE_ROOT = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

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

IDIOM_PATTERNS = {
    "context_manager": r"^\s+with\s+open\s*\(",
    "try_except_finally": r"^\s+try\s*:.*\n.*except.*\n.*finally",
    "list_comprehension": r"\[.+for\s+\w+\s+in\s+.+\]",
    "dict_comprehension": r"\{.+for\s+\w+\s+in\s+.+\}",
    "generator_expression": r"\(.+for\s+\w+\s+in\s+.+\)",
    "decorator_property": r"@property",
    "decorator_staticmethod": r"@staticmethod",
    "decorator_classmethod": r"@classmethod",
    "decorator_custom": r"@(?!property|staticmethod|classmethod)\w+",
    "lambda_inline": r"lambda\s+\w+\s*:",
    "ternary": r"\w+\s+if\s+\w+\s+else\s+\w+",
    "walrus": r":=",
    "fstring": r"f['\"]",
    "star_args": r"\*\w+",
    "kwargs_unpack": r"\*\*\w+",
    "isinstance_check": r"isinstance\s*\(",
    "type_hint": r"def\s+\w+\s*\(.*:\s*\w+",
    "enum_pattern": r"class\s+\w+\(.*Enum",
    "singleton_init": r"def\s+__init__\s*\(self\)\s*:",
    "factory_method": r"def\s+create_\w+\s*\(",
    "builder_pattern": r"def\s+build_\w+\s*\(",
    "observer_pattern": r"def\s+(add|remove)_listener\s*\(",
    "strategy_pattern": r"def\s+set_strategy\s*\(",
    "iterator_protocol": r"def\s+__iter__\s*\(",
    "context_manager_protocol": r"def\s+__enter__\s*\(",
    "descriptor_protocol": r"def\s+__get__\s*\(",
    "metaclass_usage": r"metaclass\s*=",
    "abstract_base": r"import\s+abc\b|from\s+abc\b",
    "dataclass": r"@dataclass",
    "namedtuple": r"namedtuple\s*\(",
    "typing_generic": r"from\s+typing\s+import",
    "async_def": r"^\s+async\s+def\s+",
    "await_call": r"await\s+\w+",
    "async_for": r"^\s+async\s+for\s+",
    "async_with": r"^\s+async\s+with\s+",
}

LIBRARY_IMPORTS = {
    "os": 0, "sys": 1, "json": 2, "re": 3, "sqlite3": 4,
    "struct": 5, "time": 6, "datetime": 7, "subprocess": 8,
    "ast": 9, "collections": 10, "itertools": 11, "functools": 12,
    "typing": 13, "pathlib": 14, "shutil": 15, "threading": 16,
    "multiprocessing": 17, "asyncio": 18, "logging": 19,
    "unittest": 20, "pytest": 21, "numpy": 22, "pandas": 23,
    "torch": 24, "tensorflow": 25, "sklearn": 26, "coremltools": 27,
    "PyQt6": 28, "PyQt5": 29, "tkinter": 30, "flask": 31,
    "django": 32, "fastapi": 33, "requests": 34, "urllib": 35,
    "socket": 36, "http": 37, "email": 38, "hashlib": 39,
}

STYLE_FEATURES = {
    "run_method": r"def\s+Run\s*\(",
    "tuple3_return": r"return\s*\(\s*[01]\s*,",
    "self_state": r"self\.state\b",
    "self_config": r"self\.state\[.config.\]",
    "p_method": r"def\s+P\s*\(",
    "pascal_case_class": r"^class\s+[A-Z]\w*",
    "uppercase_const": r"^[A-Z][A-Z_0-9]+\s*=",
    "no_print": None,
    "no_self_underscore": None,
    "no_decorator": None,
    "bcl_header": r"#\[@\w+\]",
    "config_import": r"from\s+Config",
    "init_signature": r"def\s+__init__\s*\(self,\s*mem\s*=",
    "read_state_method": r"def\s+readState\s*\(",
    "set_config_method": r"def\s+setConfig\s*\(",
    "dispatch_run": r"if\s+command\s*==",
    "no_tabs": None,
    "no_enum": None,
    "no_trailing_ws": None,
}

DOMAIN_FILES = {
    "vscode": [
        "Dom_CoreML_Layout/CoreMLLayoutTrainer.py",
        "Dom_CoreML_Layout/CoreMLExpertRegistry.py",
        "Dom_CoreML_Layout/CoreMLMultiExpertTrainer.py",
        "Dom_CoreML_Layout/CoreMLLayoutConverter.py",
        "Dom_CoreML_Layout/CoreMLLayoutDataGenerator.py",
        "Dom_CoreML_Layout/CoreTotchBridge.py",
        "Dom_CoreML_Layout/CoreMLRouter.py",
        "Dom_CoreML_Layout/CoreMLOrchestrator.py",
    ],
    "browser": [
        "Dom_Graph/GraphPhysics.py",
        "Dom_Graph/GraphSignalMatrix.py",
        "Dom_Graph/Node.py",
        "Dom_Graph/Edge.py",
        "Dom_Graph/SpecGraph.py",
        "Dom_Graph/PlanGraph.py",
    ],
    "dashboard": [
        "Dom_Graph/GapGraph.py",
        "Dom_Graph/OrchGraph.py",
        "Dom_Graph/ErrorGraph.py",
        "Dom_Graph/LifecycleGraph.py",
        "Dom_Graph/DepGraph.py",
        "Dom_Graph/SpecFlow.py",
    ],
    "mobile": [
        "CoreML_Training/CoreMLTrainer.py",
        "CoreML_Training/SyntheticDataGen.py",
        "CoreML_Training/Config.py",
        "Dom_qa_engine/GhostQAEngine.py",
        "Dom_qa_engine/Config_qa_engine.py",
        "efl_brain/Efi_agent_brain.py",
    ],
    "tablet": [
        "Dom_svg_engine/wizard_engine_bridge.py",
        "Dom_svg_engine/wizard_mockup.py",
        "Dom_svg_engine/wizard_animation_engine.py",
        "Dom_svg_engine/Config_svg_engine.py",
        "gui_engine/GuiEmbedder.py",
        "gui_engine/Config_gui_engine.py",
    ],
}

DOMAIN_INDICES = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}
LAYERS = ["grammar", "idiom", "library", "style"]


class CoreMLASTTrainer:
    """AST-structured trainer with 4 independent knowledge layers.

    Layer 1 — GRAMMAR: AST node type distribution, tree depth, branching.
              Captures structural shape of code. Language-level, not project-level.
    Layer 2 — IDIOMS: Python design patterns (context managers, comprehensions,
              decorators, async, type hints, dataclasses). Reusable across projects.
    Layer 3 — LIBRARIES: Import profile — which stdlib/third-party modules are used.
              Captures ecosystem dependency, not code structure.
    Layer 4 — STYLE: VBStyle compliance features (Run(), Tuple3, self.state, BCL headers,
              no print, no self._). Project-specific conventions.

    Each layer produces a 40D vector. Each layer trains its own expert.
    At inference, all 4 layers vote → combined classification.

    This separates "what is valid Python" from "what patterns are used"
    from "what libraries are imported" from "what style conventions are followed".
    Each layer evolves independently.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "coretotch_bin": CORETOTCH_BIN,
                "experts_dir": EXPERTS_DIR,
                "training_dir": TRAINING_DIR,
                "codebase_root": CODEBASE_ROOT,
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

    def Run(self, command, params=None):
        params = params or {}
        if command == "extract_ast_features":
            return self.cmdExtractAstFeatures(params)
        if command == "train_layer":
            return self.cmdTrainLayer(params)
        if command == "train_all_layers":
            return self.cmdTrainAllLayers(params)
        if command == "classify":
            return self.cmdClassify(params)
        if command == "list_layers":
            return self.cmdListLayers(params)
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

    def extractGrammarVector(self, filepath):
        """Layer 1: AST node type distribution + tree structure metrics."""
        try:
            with open(filepath, "r", errors="replace") as f:
                source = f.read()
            tree = ast.parse(source)
            nodeCounts = {}
            totalNodes = 0
            maxDepth = 0

            def walk(node, depth):
                nonlocal totalNodes, maxDepth
                totalNodes += 1
                if depth > maxDepth:
                    maxDepth = depth
                nodeType = type(node).__name__
                nodeCounts[nodeType] = nodeCounts.get(nodeType, 0) + 1
                for child in ast.iter_child_nodes(node):
                    walk(child, depth + 1)

            walk(tree, 0)

            vector = []
            for nodeType in GRAMMAR_NODE_TYPES:
                count = nodeCounts.get(nodeType, 0)
                vector.append(min(count / 50.0, 1.0))

            vector.append(min(totalNodes / 500.0, 1.0))
            vector.append(min(maxDepth / 15.0, 1.0))
            vector.append(min(len(nodeCounts) / 30.0, 1.0))
            vector.append(1.0 if totalNodes > 0 else 0.0)

            funcDefs = nodeCounts.get("FunctionDef", 0) + nodeCounts.get("AsyncFunctionDef", 0)
            classDefs = nodeCounts.get("ClassDef", 0)
            vector.append(min(funcDefs / 20.0, 1.0))
            vector.append(min(classDefs / 5.0, 1.0))
            if classDefs > 0:
                vector.append(min(funcDefs / (classDefs * 10.0), 1.0))
            else:
                vector.append(0.0)

            while len(vector) < INPUT_DIM:
                vector.append(0.0)
            return vector[:INPUT_DIM]
        except Exception:
            return [0.0] * INPUT_DIM

    def extractIdiomVector(self, filepath):
        """Layer 2: Python design patterns and idioms."""
        try:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            vector = []
            for patternName, pattern in IDIOM_PATTERNS.items():
                count = len(re.findall(pattern, content, re.MULTILINE))
                vector.append(min(count / 5.0, 1.0))
            while len(vector) < INPUT_DIM:
                vector.append(0.0)
            return vector[:INPUT_DIM]
        except Exception:
            return [0.0] * INPUT_DIM

    def extractLibraryVector(self, filepath):
        """Layer 3: Import profile — which libraries are used."""
        try:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            imports = re.findall(r"^\s*(?:import\s+(\w+)|from\s+(\w+)\s+import)", content, re.MULTILINE)
            importedModules = set()
            for imp in imports:
                mod = imp[0] if imp[0] else imp[1]
                rootMod = mod.split(".")[0]
                importedModules.add(rootMod)

            vector = [0.0] * INPUT_DIM
            for mod, idx in LIBRARY_IMPORTS.items():
                if mod in importedModules:
                    vector[idx] = 1.0

            totalImports = len(importedModules)
            vector[35] = min(totalImports / 20.0, 1.0)
            stdlibCount = sum(1 for m in importedModules if m in LIBRARY_IMPORTS and LIBRARY_IMPORTS[m] < 22)
            thirdPartyCount = totalImports - stdlibCount
            vector[36] = min(stdlibCount / 10.0, 1.0)
            vector[37] = min(thirdPartyCount / 10.0, 1.0)
            vector[38] = 1.0 if totalImports > 0 else 0.0
            vector[39] = min(totalImports / 30.0, 1.0)
            return vector
        except Exception:
            return [0.0] * INPUT_DIM

    def extractStyleVector(self, filepath):
        """Layer 4: VBStyle compliance and project conventions."""
        try:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            vector = []
            for featName, pattern in STYLE_FEATURES.items():
                if pattern is None:
                    if featName == "no_print":
                        count = len(re.findall(r"^\s*print\s*\(", content, re.MULTILINE))
                        vector.append(1.0 if count == 0 else 0.0)
                    elif featName == "no_self_underscore":
                        count = len(re.findall(r"\bself\._", content))
                        vector.append(1.0 if count == 0 else 0.0)
                    elif featName == "no_decorator":
                        count = len(re.findall(r"^\s*@\w+", content, re.MULTILINE))
                        vector.append(1.0 if count == 0 else 0.0)
                    elif featName == "no_tabs":
                        hasTabs = any("\t" in line for line in lines)
                        vector.append(1.0 if not hasTabs else 0.0)
                    elif featName == "no_enum":
                        hasEnum = bool(re.search(r"\bEnum\b", content))
                        vector.append(1.0 if not hasEnum else 0.0)
                    elif featName == "no_trailing_ws":
                        hasTrailing = any(line != line.rstrip() for line in lines)
                        vector.append(1.0 if not hasTrailing else 0.0)
                else:
                    count = len(re.findall(pattern, content, re.MULTILINE))
                    vector.append(min(count / 10.0, 1.0))

            while len(vector) < INPUT_DIM:
                vector.append(0.0)
            return vector[:INPUT_DIM]
        except Exception:
            return [0.0] * INPUT_DIM

    def extractAllLayers(self, filepath):
        """Extract all 4 layer vectors from a file."""
        return {
            "grammar": self.extractGrammarVector(filepath),
            "idiom": self.extractIdiomVector(filepath),
            "library": self.extractLibraryVector(filepath),
            "style": self.extractStyleVector(filepath),
        }

    def makeTarget(self, domainIndex):
        target = [0.0] * OUTPUT_DIM
        target[domainIndex] = 1.0
        return target

    def generateLayerTrainingData(self, layer, domain):
        """Generate training data for one layer + one domain."""
        files = DOMAIN_FILES.get(domain, [])
        if not files:
            return None
        root = self.state["config"]["codebase_root"]
        domainIndex = DOMAIN_INDICES[domain]
        extractorMap = {
            "grammar": self.extractGrammarVector,
            "idiom": self.extractIdiomVector,
            "library": self.extractLibraryVector,
            "style": self.extractStyleVector,
        }
        extractor = extractorMap[layer]
        episodes = []
        sampleCount = 0

        for relPath in files:
            filepath = os.path.join(root, relPath) if not os.path.isabs(relPath) else relPath
            if not os.path.exists(filepath):
                continue
            features = extractor(filepath)
            target = self.makeTarget(domainIndex)
            episodes.append({
                "episode": sampleCount,
                "num_nodes": 1,
                "steps": [{"state": features, "action": target, "reward": 1.0}],
            })
            sampleCount += 1

        otherDomains = [d for d in DOMAIN_FILES if d != domain]
        for otherDomain in otherDomains:
            otherIndex = DOMAIN_INDICES[otherDomain]
            otherFiles = DOMAIN_FILES[otherDomain]
            for relPath in otherFiles[:2]:
                filepath = os.path.join(root, relPath) if not os.path.isabs(relPath) else relPath
                if not os.path.exists(filepath):
                    continue
                features = extractor(filepath)
                target = self.makeTarget(domainIndex)
                episodes.append({
                    "episode": sampleCount,
                    "num_nodes": 1,
                    "steps": [{"state": features, "action": target, "reward": 0.5}],
                })
                sampleCount += 1

        return {
            "episodes": episodes,
            "config": {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "layer": layer,
                "domain": domain,
                "samples": sampleCount,
                "source": "ast_structured",
            },
        }

    def cmdExtractAstFeatures(self, params):
        """Extract all 4 layer features from a file."""
        try:
            filepath = self.p(params, "filepath")
            if not filepath:
                return (0, None, ("PARAMS_ERROR", "filepath required", 0))
            root = self.state["config"]["codebase_root"]
            if not os.path.isabs(filepath):
                filepath = os.path.join(root, filepath)
            if not os.path.exists(filepath):
                return (0, None, ("FILE_NOT_FOUND", filepath, 0))
            features = self.extractAllLayers(filepath)
            return (1, {
                "filepath": filepath,
                "layers": features,
                "layer_count": len(features),
            }, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ERROR", str(e), 0))

    def cmdTrainLayer(self, params):
        """Train one layer expert for one domain."""
        try:
            layer = self.p(params, "layer")
            domain = self.p(params, "domain")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            lr = float(self.p(params, "learning_rate", self.state["config"]["learning_rate"]))
            if layer not in LAYERS:
                return (0, None, ("PARAMS_ERROR", "layer must be: " + str(LAYERS), 0))
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            trainingData = self.generateLayerTrainingData(layer, domain)
            if not trainingData:
                return (0, None, ("NO_DATA", "No training data for " + layer + "/" + domain, 0))
            outputPath = os.path.join(TRAINING_DIR, layer + "_" + domain + "_training.json")
            with open(outputPath, "w") as f:
                json.dump(trainingData, f)
            initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if not os.path.exists(initWeights):
                initWeights = None
            weightsOut = os.path.join(EXPERTS_DIR, "ast_" + layer + "_" + domain + ".weights.bin")
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
                "layer": layer,
                "domain": domain,
                "training_file": outputPath,
                "output_weights": weightsOut,
                "epochs": epochs,
                "samples": trainingData["config"]["samples"],
                "first_loss": firstLoss,
                "last_loss": lastLoss,
                "success": proc.returncode == 0,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_LAYER_ERROR", str(e), 0))

    def cmdTrainAllLayers(self, params):
        """Train all 4 layers x 5 domains = 20 experts."""
        try:
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            results = []
            for layer in LAYERS:
                for domain in DOMAIN_FILES:
                    ok, data, err = self.cmdTrainLayer({
                        "layer": layer, "domain": domain, "epochs": epochs
                    })
                    if ok:
                        results.append({
                            "layer": data["layer"],
                            "domain": data["domain"],
                            "first_loss": data["first_loss"],
                            "last_loss": data["last_loss"],
                            "success": data["success"],
                        })
                    else:
                        results.append({
                            "layer": layer, "domain": domain,
                            "error": str(err), "success": False,
                        })
            successCount = sum(1 for r in results if r.get("success"))
            return (1, {
                "trained": successCount,
                "total": len(results),
                "layers": LAYERS,
                "domains": list(DOMAIN_FILES.keys()),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ALL_ERROR", str(e), 0))

    def cmdClassify(self, params):
        """Classify a file using all 4 layers — ensemble vote."""
        try:
            filepath = self.p(params, "filepath")
            if not filepath:
                return (0, None, ("PARAMS_ERROR", "filepath required", 0))
            root = self.state["config"]["codebase_root"]
            if not os.path.isabs(filepath):
                filepath = os.path.join(root, filepath)
            if not os.path.exists(filepath):
                return (0, None, ("FILE_NOT_FOUND", filepath, 0))
            features = self.extractAllLayers(filepath)
            coretotch = self.state["config"]["coretotch_bin"]
            layerVotes = {}
            for layer in LAYERS:
                statePath = os.path.join(TRAINING_DIR, "classify_" + layer + ".bin")
                with open(statePath, "wb") as f:
                    for v in features[layer]:
                        f.write(struct.pack("<f", v))
                domainScores = {}
                for domain in DOMAIN_FILES:
                    wpath = os.path.join(EXPERTS_DIR, "ast_" + layer + "_" + domain + ".weights.bin")
                    if not os.path.exists(wpath):
                        continue
                    proc = subprocess.run(
                        [coretotch, "select", wpath, statePath],
                        capture_output=True, text=True
                    )
                    for line in (proc.stderr + proc.stdout).split("\n"):
                        if "output:" in line:
                            vals = [float(x) for x in line.split("output:")[1].strip().split()]
                            idx = DOMAIN_INDICES[domain]
                            domainScores[domain] = vals[idx]
                            break
                if domainScores:
                    winner = max(domainScores, key=domainScores.get)
                    layerVotes[layer] = {
                        "winner": winner,
                        "scores": domainScores,
                    }

            voteCounts = {}
            for layer, vote in layerVotes.items():
                w = vote["winner"]
                voteCounts[w] = voteCounts.get(w, 0) + 1
            finalWinner = max(voteCounts, key=voteCounts.get) if voteCounts else "unknown"

            return (1, {
                "filepath": filepath,
                "final_classification": finalWinner,
                "vote_counts": voteCounts,
                "layer_votes": layerVotes,
                "layers_used": list(layerVotes.keys()),
            }, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def cmdListLayers(self, params):
        """List all trained AST layer experts."""
        try:
            experts = []
            if os.path.exists(EXPERTS_DIR):
                for fname in sorted(os.listdir(EXPERTS_DIR)):
                    if fname.startswith("ast_") and fname.endswith(".weights.bin"):
                        parts = fname.replace("ast_", "").replace(".weights.bin", "").split("_", 1)
                        if len(parts) == 2:
                            layer, domain = parts
                            fpath = os.path.join(EXPERTS_DIR, fname)
                            experts.append({
                                "layer": layer,
                                "domain": domain,
                                "file": fname,
                                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                            })
            byLayer = {}
            for e in experts:
                byLayer.setdefault(e["layer"], []).append(e)
            return (1, {
                "experts": experts,
                "total": len(experts),
                "by_layer": byLayer,
                "layers": LAYERS,
            }, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "layers": LAYERS,
            "domains": list(DOMAIN_FILES.keys()),
            "domain_files": {k: len(v) for k, v in DOMAIN_FILES.items()},
            "grammar_node_types": len(GRAMMAR_NODE_TYPES),
            "idiom_patterns": len(IDIOM_PATTERNS),
            "library_imports": len(LIBRARY_IMPORTS),
            "style_features": len(STYLE_FEATURES),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
