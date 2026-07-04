#[@GHOST]
#[@VBSTYLE]
#[@FILEID] CoreMLExpertRegistry.py
#[@SUMMARY] Multi-expert module registry: train separate experts, select at runtime
#[@CLASS] CoreMLExpertRegistry
#[@METHOD] register, select, list, export_manifest
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import os
import json
from Config_CoreMLLayout import INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM

EXPERT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/experts"
MANIFEST_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_CoreML_Layout/expert_manifest.json"

EXPERT_ARCHITECTURE = {
    "input_dim": INPUT_DIM,
    "hidden_dim": HIDDEN_DIM,
    "output_dim": OUTPUT_DIM,
    "layers": [
        {"name": "fc0", "type": "linear", "in": INPUT_DIM, "out": HIDDEN_DIM, "activation": "relu"},
        {"name": "fc2", "type": "linear", "in": HIDDEN_DIM, "out": HIDDEN_DIM, "activation": "relu"},
        {"name": "fc4", "type": "linear", "in": HIDDEN_DIM, "out": OUTPUT_DIM, "activation": "none"},
    ],
    "total_params": 23050,
    "weight_layout": "w0(128x40) b0(128) w2(128x128) b2(128) w4(10x128) b4(10)",
    "weights_bin_size": 23050 * 4,
}


class CoreMLExpertRegistry:
    """Registry for multi-expert model modules.

    Each expert is a separate weight file trained for a specific domain.
    At runtime, C CoreTotch loads only the needed expert.
    All experts share the same architecture (40->128->128->10).
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
        if command == "register":
            return self.cmdRegister(params)
        if command == "select":
            return self.cmdSelect(params)
        if command == "list":
            return self.cmdList(params)
        if command == "export_manifest":
            return self.cmdExportManifest(params)
        if command == "load_manifest":
            return self.cmdLoadManifest(params)
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
        if not os.path.exists(EXPERT_DIR):
            os.makedirs(EXPERT_DIR, exist_ok=True)

    def cmdRegister(self, params):
        """Register a new expert module."""
        try:
            name = self.p(params, "name")
            weightsPath = self.p(params, "weights_path")
            domain = self.p(params, "domain", "general")
            description = self.p(params, "description", "")
            if not name or not weightsPath:
                return (0, None, ("PARAMS_ERROR", "name and weights_path required", 0))
            if not os.path.exists(weightsPath):
                return (0, None, ("WEIGHTS_NOT_FOUND", "weights file missing: " + weightsPath, 0))
            destPath = os.path.join(EXPERT_DIR, name + ".weights.bin")
            import shutil
            if os.path.abspath(weightsPath) != os.path.abspath(destPath):
                shutil.copy2(weightsPath, destPath)
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            experts = self.state["manifest"].get("experts", {})
            experts[name] = {
                "name": name,
                "domain": domain,
                "description": description,
                "weights_path": destPath,
                "architecture": EXPERT_ARCHITECTURE,
                "active": False,
            }
            self.state["manifest"]["experts"] = experts
            self.state["manifest"]["architecture"] = EXPERT_ARCHITECTURE
            self.cmdExportManifest({})
            return (1, {
                "registered": name,
                "domain": domain,
                "weights_path": destPath,
            }, None)
        except Exception as e:
            return (0, None, ("REGISTER_ERROR", str(e), 0))

    def cmdSelect(self, params):
        """Select which expert to activate at runtime."""
        try:
            name = self.p(params, "name")
            if not name:
                return (0, None, ("PARAMS_ERROR", "name required", 0))
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            experts = self.state["manifest"].get("experts", {})
            if name not in experts:
                return (0, None, ("EXPERT_NOT_FOUND", "No expert: " + name, 0))
            for eName in experts:
                experts[eName]["active"] = (eName == name)
            self.state["manifest"]["active_expert"] = name
            self.cmdExportManifest({})
            return (1, {
                "active_expert": name,
                "weights_path": experts[name]["weights_path"],
                "domain": experts[name]["domain"],
            }, None)
        except Exception as e:
            return (0, None, ("SELECT_ERROR", str(e), 0))

    def cmdList(self, params):
        """List all registered experts."""
        try:
            if not self.state["manifest"]:
                self.cmdLoadManifest({})
            experts = self.state["manifest"].get("experts", {})
            active = self.state["manifest"].get("active_expert", "none")
            return (1, {
                "total_experts": len(experts),
                "active": active,
                "experts": list(experts.keys()),
                "details": experts,
            }, None)
        except Exception as e:
            return (0, None, ("LIST_ERROR", str(e), 0))

    def cmdExportManifest(self, params):
        """Save manifest to disk."""
        try:
            path = self.p(params, "path", MANIFEST_PATH)
            with open(path, "w") as f:
                json.dump(self.state["manifest"], f, indent=2)
            return (1, {"path": path, "experts": len(self.state["manifest"].get("experts", {}))}, None)
        except Exception as e:
            return (0, None, ("EXPORT_ERROR", str(e), 0))

    def cmdLoadManifest(self, params):
        """Load manifest from disk."""
        try:
            path = self.p(params, "path", MANIFEST_PATH)
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.state["manifest"] = json.load(f)
                return (1, {"path": path, "experts": len(self.state["manifest"].get("experts", {}))}, None)
            self.state["manifest"] = {
                "architecture": EXPERT_ARCHITECTURE,
                "experts": {},
                "active_expert": "none",
            }
            return (1, {"path": path, "experts": 0, "created": True}, None)
        except Exception as e:
            return (0, None, ("LOAD_ERROR", str(e), 0))

    def readState(self, params=None):
        return (1, {
            "config": self.state["config"],
            "manifest_loaded": bool(self.state["manifest"]),
            "expert_count": len(self.state["manifest"].get("experts", {})),
        }, None)

    def setConfig(self, params):
        if not isinstance(params, dict):
            return (0, None, ("PARAMS_ERROR", "params must be dict", 0))
        self.state["config"].update(params)
        return (1, self.state["config"].copy(), None)
