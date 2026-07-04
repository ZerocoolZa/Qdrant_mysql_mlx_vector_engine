#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLModelBank.py
#[@SUMMARY] Versioned model bank with routing and ensemble support — the backpack
#[@CLASS] CoreMLModelBank
#[@METHOD] deposit, withdraw, route, ensemble, list_versions, prune
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
import time
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

BANK_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/model_bank"
BANK_MANIFEST = os.path.join(BANK_DIR, "bank_manifest.json")

BANK_SCHEMA = {
    "interface": {
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "input_format": "float32[1][40]",
        "output_format": "float32[1][10]",
        "normalization": "minmax_0_1",
        "weight_layout": "w0(128x40) b0(128) w2(128x128) b2(128) w4(10x128) b4(10)",
        "total_params": 23050,
    },
    "compatibility": "all models must share the same interface contract",
    "operations": ["route", "ensemble", "version", "prune"],
}


class CoreMLModelBank:
    """Versioned model bank — the backpack.

    Stores multiple versioned expert models.
    At runtime: route to one expert OR ensemble multiple.
    Only loaded models consume RAM.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "manifest": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.ensureDirs()

    def Run(self, command, params=None):
        params = params or {}
        if command == "deposit":
            return self.cmdDeposit(params)
        if command == "withdraw":
            return self.cmdWithdraw(params)
        if command == "route":
            return self.cmdRoute(params)
        if command == "ensemble":
            return self.cmdEnsemble(params)
        if command == "list_versions":
            return self.cmdListVersions(params)
        if command == "prune":
            return self.cmdPrune(params)
        if command == "load_manifest":
            return self.cmdLoadManifest(params)
        if command == "save_manifest":
            return self.cmdSaveManifest(params)
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
        if not os.path.exists(BANK_DIR):
            os.makedirs(BANK_DIR, exist_ok=True)

    def cmdLoadManifest(self, params):
        try:
            if os.path.exists(BANK_MANIFEST):
                with open(BANK_MANIFEST, "r") as f:
                    self.state["manifest"] = json.load(f)
                return (1, {"loaded": True, "models": len(self.state["manifest"].get("models", {}))}, None)
            self.state["manifest"] = {
                "schema": BANK_SCHEMA,
                "models": {},
                "routes": {},
                "next_version": {},
            }
            return (1, {"loaded": False, "created": True, "models": 0}, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def cmdSaveManifest(self, params):
        try:
            with open(BANK_MANIFEST, "w") as f:
                json.dump(self.state["manifest"], f, indent=2)
            return (1, {"saved": True, "path": BANK_MANIFEST}, None)
        except Exception as e:
            return (0, None, ("SAVE_ERROR", str(e), 0))

    def cmdDeposit(self, params):
        """Deposit a new model version into the bank."""
        try:
            name = self.p(params, "name")
            weightsPath = self.p(params, "weights_path")
            domain = self.p(params, "domain", "general")
            description = self.p(params, "description", "")
            if not name or not weightsPath:
                return (0, None, ("PARAMS_ERROR", "name and weights_path required", 0))
            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", weightsPath, 0))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            nextVer = self.state["manifest"].get("next_version", {})
            version = nextVer.get(name, 1)
            bankPath = os.path.join(BANK_DIR, name + "_v" + str(version) + ".weights.bin")
            import shutil
            if os.path.abspath(weightsPath) != os.path.abspath(bankPath):
                shutil.copy2(weightsPath, bankPath)
            if name not in models:
                models[name] = {
                    "domain": domain,
                    "description": description,
                    "versions": {},
                }
            models[name]["versions"][str(version)] = {
                "version": version,
                "weights_path": bankPath,
                "deposited": time.time(),
                "active": True,
            }
            for vKey in models[name]["versions"]:
                if vKey != str(version):
                    models[name]["versions"][vKey]["active"] = False
            nextVer[name] = version + 1
            self.state["manifest"]["models"] = models
            self.state["manifest"]["next_version"] = nextVer
            self.cmdSaveManifest({})
            return (1, {
                "deposited": name,
                "version": version,
                "path": bankPath,
                "total_versions": len(models[name]["versions"]),
            }, None)
        except Exception as e:
            return (0, None, ("DEPOSIT_ERROR", str(e), 0))

    def cmdWithdraw(self, params):
        """Get the path to a specific model version."""
        try:
            name = self.p(params, "name")
            version = str(self.p(params, "version", "latest"))
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            if name not in models:
                return (0, None, ("MODEL_NOT_FOUND", name, 0))
            versions = models[name]["versions"]
            if version == "latest":
                activeVersion = None
                for vKey, vData in versions.items():
                    if vData.get("active", False):
                        activeVersion = vKey
                        break
                if not activeVersion:
                    activeVersion = str(max(int(v) for v in versions))
                version = activeVersion
            if version not in versions:
                return (0, None, ("VERSION_NOT_FOUND", "v" + version, 0))
            return (1, {
                "name": name,
                "version": int(version),
                "weights_path": versions[version]["weights_path"],
                "domain": models[name]["domain"],
            }, None)
        except Exception as e:
            return (0, None, ("WITHDRAW_ERROR", str(e), 0))

    def cmdRoute(self, params):
        """Route input to the best expert based on domain tag."""
        try:
            domain = self.p(params, "domain")
            if not domain:
                return (0, None, ("PARAMS_ERROR", "domain required", 0))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            bestName = None
            bestVersion = None
            bestPath = None
            for name, info in models.items():
                if info["domain"] == domain:
                    versions = info["versions"]
                    activeV = None
                    for vKey, vData in versions.items():
                        if vData.get("active", False):
                            activeV = vKey
                            break
                    if not activeV:
                        activeV = str(max(int(v) for v in versions))
                    bestName = name
                    bestVersion = activeV
                    bestPath = versions[activeV]["weights_path"]
                    break
            if not bestPath:
                return (0, None, ("NO_EXPERT", "No expert for domain: " + domain, 0))
            routes = self.state["manifest"].get("routes", {})
            routes[domain] = {"name": bestName, "version": bestVersion}
            self.state["manifest"]["routes"] = routes
            self.cmdSaveManifest({})
            return (1, {
                "domain": domain,
                "expert": bestName,
                "version": int(bestVersion),
                "weights_path": bestPath,
                "ram_usage": "1 model (23KB weights only)",
            }, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def cmdEnsemble(self, params):
        """Combine multiple experts with weighted outputs."""
        try:
            experts = self.p(params, "experts", [])
            weights = self.p(params, "weights", [])
            if not experts or not isinstance(experts, list):
                return (0, None, ("PARAMS_ERROR", "experts list required", 0))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            if not weights:
                weights = [1.0 / len(experts)] * len(experts)
            if len(weights) != len(experts):
                return (0, None, ("MISMATCH", "experts and weights length differ", 0))
            ensembleConfig = []
            totalWeight = sum(weights)
            for i, name in enumerate(experts):
                if name not in models:
                    return (0, None, ("MODEL_NOT_FOUND", name, 0))
                versions = models[name]["versions"]
                activeV = None
                for vKey, vData in versions.items():
                    if vData.get("active", False):
                        activeV = vKey
                        break
                if not activeV:
                    activeV = str(max(int(v) for v in versions))
                ensembleConfig.append({
                    "name": name,
                    "version": int(activeV),
                    "weight": weights[i] / totalWeight,
                    "weights_path": versions[activeV]["weights_path"],
                })
            ensemblePath = os.path.join(BANK_DIR, "ensemble_config.json")
            with open(ensemblePath, "w") as f:
                json.dump(ensembleConfig, f, indent=2)
            return (1, {
                "ensemble": ensembleConfig,
                "config_path": ensemblePath,
                "ram_usage": str(len(experts)) + " models (" + str(len(experts) * 23) + "KB weights)",
                "note": "C runtime loads all listed weights, averages forward passes",
            }, None)
        except Exception as e:
            return (0, None, ("ENSEMBLE_ERROR", str(e), 0))

    def cmdListVersions(self, params):
        """List all models and their versions in the bank."""
        try:
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            result = []
            for name, info in models.items():
                versions = []
                for vKey, vData in sorted(info["versions"].items(), key=lambda x: int(x[0])):
                    versions.append({
                        "version": vData["version"],
                        "active": vData.get("active", False),
                        "path": vData["weights_path"],
                    })
                result.append({
                    "name": name,
                    "domain": info["domain"],
                    "description": info["description"],
                    "versions": versions,
                })
            return (1, {
                "total_models": len(result),
                "total_versions": sum(len(m["versions"]) for m in result),
                "models": result,
            }, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def cmdPrune(self, params):
        """Remove old inactive versions, keep only latest N."""
        try:
            keepN = int(self.p(params, "keep", 2))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            models = self.state["manifest"].get("models", {})
            removed = 0
            for name, info in models.items():
                versions = info["versions"]
                sortedVersions = sorted(versions.items(), key=lambda x: int(x[0]), reverse=True)
                for i, (vKey, vData) in enumerate(sortedVersions):
                    if i >= keepN:
                        path = vData["weights_path"]
                        if os.path.exists(path):
                            os.remove(path)
                        del versions[vKey]
                        removed += 1
            self.cmdSaveManifest({})
            return (1, {"pruned": removed, "kept_per_model": keepN}, None)
        except Exception as e:
            return (0, None, ("PRUNE_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "manifest_loaded": bool(self.state["manifest"]),
            "total_models": len(self.state["manifest"].get("models", {})),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
