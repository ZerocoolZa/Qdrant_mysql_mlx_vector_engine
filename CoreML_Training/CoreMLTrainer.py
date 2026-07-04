#[@GHOST]{[@file<CoreMLTrainer.py>][@domain<coreml_training>][@role<trainer>][@return<Tuple3>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<trainer>][@return<Tuple3>][@state<config,model,history,results>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/CoreMLTrainer.py>][@date<2026-06-28>][@session<coreml_training>]}
#[@SUMMARY]{Orchestrates CoreML MLUpdateTask training via Swift runner (coremltools 9.0 removed Python training APIs); captures baseline/trained weights and verifies change}
#[@CLASS]{CoreMLTrainer — owns execution of MLUpdateTask via Swift + weight verification via Python}
#[@METHOD]{Run dispatch: capture_baseline, train, capture_trained, verify_weights, report}

import os
import sys
import subprocess
import numpy as np
from coremltools.models import MLModel

import Config


class CoreMLTrainer:
    """Executes CoreML MLUpdateTask training via Swift runner; verifies weights in Python."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "updatable_path": Config.UPDATABLE_MODEL_PATH,
                "trained_path": Config.TRAINED_MODEL_PATH,
                "baseline_path": Config.BASELINE_WEIGHTS_PATH,
                "trained_weights_path": Config.TRAINED_WEIGHTS_PATH,
                "swift_script": os.path.join(Config.PROJECT_ROOT, "run_training.swift"),
                "data_path": os.path.join(Config.OUTPUT_DIR, "training_data.json"),
                "swift_bin": Config.SWIFT_BIN,
            },
            "model": None,
            "history": [],
            "results": {},
            "errors": [],
            "meta": {"class": "CoreMLTrainer", "ver": "1.0"},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "capture_baseline": self.capture_baseline,
            "train": self.train,
            "capture_trained": self.capture_trained,
            "verify_weights": self.verify_weights,
            "report": self.report,
        }
        method = dispatch.get(command)
        if method is None:
            return (0, None, ("unknown_command", "Unknown command: " + str(command), 0))
        return method(params)

    def read_state(self):
        return (1, dict(self.state["config"]), None)

    def set_config(self, params):
        if not isinstance(params, dict):
            return (0, None, ("bad_params", "set_config requires dict", 0))
        self.state["config"].update(params)
        return (1, dict(self.state["config"]), None)

    def _extract_weights(self, path):
        m = MLModel(path)
        spec = m.get_spec()
        nn = spec.neuralNetwork
        weights = {}
        for layer in nn.layers:
            if layer.WhichOneof("layer") == "innerProduct":
                ip = layer.innerProduct
                w = np.array(list(ip.weights.floatValue), dtype=np.float32)
                b = np.array(list(ip.bias.floatValue), dtype=np.float32) if ip.HasField("bias") else np.zeros(0, dtype=np.float32)
                weights[layer.name] = {"w": w, "b": b, "w_sum": float(w.sum()), "w_norm": float(np.linalg.norm(w))}
        return weights

    def capture_baseline(self, params):
        path = self.state["config"]["updatable_path"]
        if not os.path.exists(path):
            return (0, None, ("no_model", "Updatable model not found: " + path, 0))
        weights = self._extract_weights(path)
        save_dict = {}
        for k, v in weights.items():
            save_dict[k + "_w"] = v["w"]
            save_dict[k + "_b"] = v["b"]
        np.savez(self.state["config"]["baseline_path"], **save_dict)
        self.state["results"]["baseline"] = {k: {"w_sum": v["w_sum"], "w_norm": v["w_norm"]} for k, v in weights.items()}
        return (1, {"baseline_path": self.state["config"]["baseline_path"], "layers": list(weights.keys())}, None)

    def train(self, params):
        updatable_path = self.state["config"]["updatable_path"]
        data_path = self._p(params, "data_path", self.state["config"]["data_path"])
        swift_script = self.state["config"]["swift_script"]
        if not os.path.exists(updatable_path):
            return (0, None, ("no_model", "Updatable model not found: " + updatable_path, 0))
        if not os.path.exists(data_path):
            return (0, None, ("no_data", "Training data not found: " + data_path, 0))
        if not os.path.exists(swift_script):
            return (0, None, ("no_swift", "Swift script not found: " + swift_script, 0))
        cmd = [self.state["config"]["swift_bin"], swift_script, updatable_path, data_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        history = []
        for line in (proc.stdout or "").splitlines():
            if line.startswith("epochEnd"):
                parts = line.split()
                entry = {"event": "epochEnd", "raw": line}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        entry[k] = v
                history.append(entry)
        self.state["history"] = history
        self.state["results"]["epochs_run"] = len(history)
        self.state["results"]["swift_stdout"] = proc.stdout
        self.state["results"]["swift_stderr"] = proc.stderr
        self.state["results"]["swift_exit"] = proc.returncode
        if proc.returncode != 0:
            return (0, None, ("swift_failed", "Swift training failed: " + proc.stderr, proc.returncode))
        return (1, {"epochs_run": len(history), "history": history, "stdout": proc.stdout}, None)

    def capture_trained(self, params):
        trained_path = self.state["config"]["trained_path"]
        if not os.path.exists(trained_path):
            return (0, None, ("no_model", "Trained model not found: " + trained_path + " — did Swift training run?", 0))
        weights = self._extract_weights(trained_path)
        save_dict = {}
        for k, v in weights.items():
            save_dict[k + "_w"] = v["w"]
            save_dict[k + "_b"] = v["b"]
        np.savez(self.state["config"]["trained_weights_path"], **save_dict)
        self.state["results"]["trained"] = {k: {"w_sum": v["w_sum"], "w_norm": v["w_norm"]} for k, v in weights.items()}
        return (1, {"trained_path": trained_path, "layers": list(weights.keys())}, None)

    def verify_weights(self, params):
        baseline = self.state["results"].get("baseline")
        trained = self.state["results"].get("trained")
        if baseline is None or trained is None:
            return (0, None, ("no_data", "Capture baseline and trained weights first", 0))
        diffs = {}
        any_changed = False
        for layer in baseline:
            if layer not in trained:
                continue
            dw = abs(trained[layer]["w_sum"] - baseline[layer]["w_sum"])
            dn = abs(trained[layer]["w_norm"] - baseline[layer]["w_norm"])
            changed = dw > 1e-6 or dn > 1e-6
            if changed:
                any_changed = True
            diffs[layer] = {
                "w_sum_delta": dw,
                "w_norm_delta": dn,
                "changed": changed,
            }
        self.state["results"]["weight_diffs"] = diffs
        self.state["results"]["weights_changed"] = any_changed
        return (1, {"any_changed": any_changed, "diffs": diffs}, None)

    def report(self, params):
        r = self.state["results"]
        report_lines = [
            "CoreMLTrainer Report",
            "epochs_run: " + str(r.get("epochs_run", 0)),
            "weights_changed: " + str(r.get("weights_changed", False)),
        ]
        for layer, d in r.get("weight_diffs", {}).items():
            report_lines.append(
                "  " + layer + ": w_sum_delta=" + str(d["w_sum_delta"]) + " w_norm_delta=" + str(d["w_norm_delta"]) + " changed=" + str(d["changed"])
            )
        return (1, "\n".join(report_lines), None)
