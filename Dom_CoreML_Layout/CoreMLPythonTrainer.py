#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLPythonTrainer.py
#[@SUMMARY] Extracts 40D features from real Python files, generates training data, trains experts on Python code
#[@CLASS] CoreMLPythonTrainer
#[@METHOD] extract_features, generate_training_data, train_expert, train_all, list_experts
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import re
import json
import time
import subprocess
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

CORETOTCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/coretotch"
EXPERTS_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
TRAINING_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/training_python"
CODEBASE_ROOT = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

DOMAIN_FILES = {
    "vscode": [
        "Dom_CoreML_Layout/CoreMLLayoutTrainer.py",
        "Dom_CoreML_Layout/CoreMLExpertRegistry.py",
        "Dom_CoreML_Layout/CoreMLMultiExpertTrainer.py",
        "Dom_CoreML_Layout/CoreMLLayoutConverter.py",
        "Dom_CoreML_Layout/CoreMLLayoutDataGenerator.py",
        "Dom_CoreML_Layout/CoreTotchBridge.py",
    ],
    "browser": [
        "Dom_Graph/GraphRenderer.py",
        "Dom_Graph/GraphToWizard.py",
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
        "Dom_qa_engine/QaInference.py",
    ],
    "tablet": [
        "Dom_svg_engine/wizard_engine_bridge.py",
        "Dom_svg_engine/wizard_studio.py",
        "Dom_svg_engine/Config_svg_engine.py",
        "Dom_svg_engine/SvgRenderer.py",
        "gui_engine/GuiEmbedder.py",
        "gui_engine/Config_gui_engine.py",
    ],
}


class CoreMLPythonTrainer:
    """Trains experts on real Python code.

    Extracts 40D features from Python files:
      - Structural: lines, classes, methods, imports, functions
      - VBStyle: Run() presence, Tuple3 returns, self._ count, print count
      - Complexity: nesting depth, branch count, loop count
      - Size: total chars, avg line length, comment density
      - Patterns: decorators, try/except, with statements, list comprehensions

    Output 10D = domain classification scores:
      - 0: layout/training (vscode-like)
      - 1: graph/visualization (browser-like)
      - 2: analysis/dashboard (dashboard-like)
      - 3: ml/qa (mobile-like)
      - 4: gui/rendering (tablet-like)
      - 5: config/utility
      - 6: database/storage
      - 7: testing
      - 8: error handling
      - 9: general/other

    The expert learns to recognize code patterns from its domain.
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
        if command == "extract_features":
            return self.cmdExtractFeatures(params)
        if command == "generate_training_data":
            return self.cmdGenerateTrainingData(params)
        if command == "train_expert":
            return self.cmdTrainExpert(params)
        if command == "train_all":
            return self.cmdTrainAll(params)
        if command == "list_experts":
            return self.cmdListExperts(params)
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

    def extractFeatures(self, filepath):
        """Extract 40D feature vector from a Python file."""
        try:
            with open(filepath, "r", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            lineCount = len(lines)
            classCount = len(re.findall(r"^class\s+\w+", content, re.MULTILINE))
            methodCount = len(re.findall(r"^\s+def\s+\w+", content, re.MULTILINE))
            funcCount = len(re.findall(r"^def\s+\w+", content, re.MULTILINE))
            importCount = len(re.findall(r"^(import\s+|from\s+\w+\s+import)", content, re.MULTILINE))
            runCount = len(re.findall(r"def\s+Run\s*\(", content))
            tuple3Count = len(re.findall(r"return\s*\(\s*[01]\s*,", content))
            selfUnderscoreCount = len(re.findall(r"\bself\._", content))
            printCount = len(re.findall(r"^\s*print\s*\(", content, re.MULTILINE))
            decoratorCount = len(re.findall(r"@\w+", content))
            tryCount = len(re.findall(r"^\s+try\s*:", content, re.MULTILINE))
            exceptCount = len(re.findall(r"^\s+except\s", content, re.MULTILINE))
            withCount = len(re.findall(r"^\s+with\s+", content, re.MULTILINE))
            listCompCount = len(re.findall(r"\[.*for\s+\w+\s+in\s+", content))
            ifCount = len(re.findall(r"^\s+if\s+", content, re.MULTILINE))
            forCount = len(re.findall(r"^\s+for\s+", content, re.MULTILINE))
            whileCount = len(re.findall(r"^\s+while\s+", content, re.MULTILINE))
            commentCount = len(re.findall(r"^\s*#", content, re.MULTILINE))
            docstringCount = len(re.findall(r'("""|\'\'\')', content)) // 2
            charCount = len(content)
            avgLineLen = charCount / max(lineCount, 1)
            maxNesting = 0
            currentNesting = 0
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("class ") or stripped.startswith("def ") or stripped.startswith("if ") or stripped.startswith("for ") or stripped.startswith("while ") or stripped.startswith("try:") or stripped.startswith("with "):
                    currentNesting += 1
                    if currentNesting > maxNesting:
                        maxNesting = currentNesting
                if stripped == "" or (not stripped.startswith(" ") and not stripped.startswith("\t")):
                    currentNesting = 0
            passCount = content.count(" pass")
            returnCount = len(re.findall(r"^\s+return\s+", content, re.MULTILINE))
            yieldCount = len(re.findall(r"^\s+yield\s+", content, re.MULTILINE))
            lambdaCount = len(re.findall(r"lambda\s+", content))
            dictLiteralCount = len(re.findall(r"\{.*:", content))
            stringLiteralCount = len(re.findall(r"\"[^\"]*\"", content)) + len(re.findall(r"'[^']*'", content))
            numericCount = len(re.findall(r"\b\d+\b", content))
            boolCount = len(re.findall(r"\b(True|False)\b", content))
            noneCount = len(re.findall(r"\bNone\b", content))
            initCount = len(re.findall(r"def\s+__init__\s*\(", content))
            stateDictCount = len(re.findall(r"self\.state\b", content))
            configCount = len(re.findall(r"self\.state\[.config.\]", content))
            features = [
                min(lineCount / 500.0, 1.0),
                min(classCount / 10.0, 1.0),
                min(methodCount / 30.0, 1.0),
                min(funcCount / 10.0, 1.0),
                min(importCount / 20.0, 1.0),
                min(runCount / 5.0, 1.0),
                min(tuple3Count / 20.0, 1.0),
                min(selfUnderscoreCount / 10.0, 1.0),
                min(printCount / 10.0, 1.0),
                min(decoratorCount / 10.0, 1.0),
                min(tryCount / 10.0, 1.0),
                min(exceptCount / 10.0, 1.0),
                min(withCount / 10.0, 1.0),
                min(listCompCount / 10.0, 1.0),
                min(ifCount / 30.0, 1.0),
                min(forCount / 20.0, 1.0),
                min(whileCount / 5.0, 1.0),
                min(commentCount / 50.0, 1.0),
                min(docstringCount / 10.0, 1.0),
                min(avgLineLen / 80.0, 1.0),
                min(maxNesting / 10.0, 1.0),
                min(passCount / 10.0, 1.0),
                min(returnCount / 30.0, 1.0),
                min(yieldCount / 5.0, 1.0),
                min(lambdaCount / 10.0, 1.0),
                min(dictLiteralCount / 20.0, 1.0),
                min(stringLiteralCount / 100.0, 1.0),
                min(numericCount / 100.0, 1.0),
                min(boolCount / 20.0, 1.0),
                min(noneCount / 20.0, 1.0),
                min(initCount / 5.0, 1.0),
                min(stateDictCount / 20.0, 1.0),
                min(configCount / 20.0, 1.0),
                min(charCount / 50000.0, 1.0),
                1.0 if runCount > 0 else 0.0,
                1.0 if tuple3Count > 0 else 0.0,
                1.0 if selfUnderscoreCount == 0 else 0.0,
                1.0 if printCount == 0 else 0.0,
                1.0 if decoratorCount == 0 else 0.0,
                1.0 if initCount > 0 else 0.0,
            ]
            return features
        except Exception:
            return [0.0] * INPUT_DIM

    def makeTarget(self, domainIndex):
        """Create 10D target vector — 1.0 for the correct domain, 0.0 for others."""
        target = [0.0] * OUTPUT_DIM
        target[domainIndex] = 1.0
        return target

    def getDomainIndex(self, domain):
        indices = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}
        return indices.get(domain, 9)

    def cmdExtractFeatures(self, params):
        """Extract features from a single file."""
        try:
            filepath = self.p(params, "filepath")
            if not filepath:
                return (0, None, ("PARAMS_ERROR", "filepath required", 0))
            root = self.state["config"]["codebase_root"]
            if not os.path.isabs(filepath):
                filepath = os.path.join(root, filepath)
            if not os.path.exists(filepath):
                return (0, None, ("FILE_NOT_FOUND", filepath, 0))
            features = self.extractFeatures(filepath)
            return (1, {
                "filepath": filepath,
                "features": features,
                "feature_count": len(features),
            }, None)
        except Exception as e:
            return (0, None, ("EXTRACT_ERROR", str(e), 0))

    def cmdGenerateTrainingData(self, params):
        """Generate training data JSON from real Python files."""
        try:
            domain = self.p(params, "domain")
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            files = DOMAIN_FILES.get(domain, [])
            if not files:
                return (0, None, ("NO_FILES", "No files for domain: " + domain, 0))
            root = self.state["config"]["codebase_root"]
            domainIndex = self.getDomainIndex(domain)
            episodes = []
            sampleCount = 0
            for relPath in files:
                filepath = os.path.join(root, relPath) if not os.path.isabs(relPath) else relPath
                if not os.path.exists(filepath):
                    continue
                features = self.extractFeatures(filepath)
                target = self.makeTarget(domainIndex)
                episodes.append({
                    "episode": sampleCount,
                    "num_nodes": 1,
                    "steps": [{
                        "state": features,
                        "action": target,
                        "reward": 1.0,
                    }],
                })
                sampleCount += 1
            otherDomains = [d for d in DOMAIN_FILES if d != domain]
            for otherDomain in otherDomains:
                otherIndex = self.getDomainIndex(otherDomain)
                otherFiles = DOMAIN_FILES[otherDomain]
                for relPath in otherFiles[:2]:
                    filepath = os.path.join(root, relPath) if not os.path.isabs(relPath) else relPath
                    if not os.path.exists(filepath):
                        continue
                    features = self.extractFeatures(filepath)
                    target = self.makeTarget(domainIndex)
                    episodes.append({
                        "episode": sampleCount,
                        "num_nodes": 1,
                        "steps": [{
                            "state": features,
                            "action": target,
                            "reward": 0.5,
                        }],
                    })
                    sampleCount += 1
            trainingData = {
                "episodes": episodes,
                "config": {
                    "input_dim": INPUT_DIM,
                    "output_dim": OUTPUT_DIM,
                    "domain": domain,
                    "samples": sampleCount,
                    "source": "real_python_files",
                },
            }
            outputPath = os.path.join(TRAINING_DIR, domain + "_training.json")
            with open(outputPath, "w") as f:
                json.dump(trainingData, f)
            return (1, {
                "domain": domain,
                "output_path": outputPath,
                "samples": sampleCount,
                "positive_samples": len(files),
                "negative_samples": sampleCount - len(files),
            }, None)
        except Exception as e:
            return (0, None, ("GENERATE_ERROR", str(e), 0))

    def cmdTrainExpert(self, params):
        """Train a single expert on real Python code."""
        try:
            domain = self.p(params, "domain")
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            lr = float(self.p(params, "learning_rate", self.state["config"]["learning_rate"]))
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            ok, genData, genErr = self.cmdGenerateTrainingData({"domain": domain})
            if not ok:
                return (0, None, genErr)
            trainingPath = genData["output_path"]
            initWeights = os.path.join(EXPERTS_DIR, domain + ".weights.bin")
            if not os.path.exists(initWeights):
                initWeights = None
            outputPath = os.path.join(EXPERTS_DIR, domain + "_python.weights.bin")
            coretotch = self.state["config"]["coretotch_bin"]
            cmdArgs = [coretotch, "train", trainingPath, outputPath, str(epochs), str(lr)]
            if initWeights:
                cmdArgs.append(initWeights)
            proc = subprocess.run(cmdArgs, capture_output=True, text=True, timeout=120)
            output = proc.stderr + proc.stdout
            lossLines = [l for l in output.split("\n") if "Loss:" in l]
            firstLoss = ""
            lastLoss = ""
            if lossLines:
                firstLoss = lossLines[0].strip()
                lastLoss = lossLines[-1].strip()
            return (1, {
                "domain": domain,
                "training_file": trainingPath,
                "output_weights": outputPath,
                "epochs": epochs,
                "learning_rate": lr,
                "samples": genData["samples"],
                "first_loss": firstLoss,
                "last_loss": lastLoss,
                "exit_code": proc.returncode,
                "success": proc.returncode == 0,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ERROR", str(e), 0))

    def cmdTrainAll(self, params):
        """Train all 5 experts on real Python code."""
        try:
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            results = []
            for domain in DOMAIN_FILES:
                ok, data, err = self.cmdTrainExpert({"domain": domain, "epochs": epochs})
                if ok:
                    results.append({
                        "domain": data["domain"],
                        "samples": data["samples"],
                        "first_loss": data["first_loss"],
                        "last_loss": data["last_loss"],
                        "success": data["success"],
                    })
                else:
                    results.append({
                        "domain": domain,
                        "error": str(err),
                        "success": False,
                    })
            successCount = sum(1 for r in results if r.get("success"))
            return (1, {
                "trained": successCount,
                "total": len(results),
                "results": results,
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ALL_ERROR", str(e), 0))

    def cmdListExperts(self, params):
        """List trained Python experts."""
        try:
            experts = []
            if os.path.exists(EXPERTS_DIR):
                for fname in sorted(os.listdir(EXPERTS_DIR)):
                    if fname.endswith("_python.weights.bin"):
                        name = fname.replace("_python.weights.bin", "")
                        fpath = os.path.join(EXPERTS_DIR, fname)
                        experts.append({
                            "name": name,
                            "file": fname,
                            "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                        })
            return (1, {"experts": experts, "total": len(experts)}, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "domains": list(DOMAIN_FILES.keys()),
            "domain_files": {k: len(v) for k, v in DOMAIN_FILES.items()},
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
