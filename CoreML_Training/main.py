#!/usr/bin/env python3
#[@GHOST]{[@file<main.py>][@domain<coreml_training>][@role<entry_point>][@return<Tuple3>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<devin>][@role<entry>][@return<Tuple3>][@state<config,builders,results>]}
#[@FILEID]{[@path</Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training/main.py>][@date<2026-06-28>][@session<coreml_training>]}
#[@SUMMARY]{Entry point: orchestrates UpdatableBuilder -> SyntheticDataGen -> CoreMLTrainer to prove MLUpdateTask works end-to-end}
#[@CLASS]{Main — owns dispatch and orchestration of the CoreML training proof}
#[@METHOD]{Run dispatch: build, gendata, train, verify, all}

import os
import sys
import logging

import Config
from UpdatableBuilder import UpdatableBuilder
from SyntheticDataGen import SyntheticDataGen
from CoreMLTrainer import CoreMLTrainer

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("CoreMLTraining")


class Main:
    """Entry point orchestrating the CoreML MLUpdateTask proof-of-concept."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"python_bin": Config.PYTHON_BIN},
            "builders": {
                "updatable": UpdatableBuilder(),
                "datagen": SyntheticDataGen(),
                "trainer": CoreMLTrainer(),
            },
            "results": {},
            "errors": [],
            "meta": {"class": "Main", "ver": "1.0"},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "build": self.build,
            "gendata": self.gendata,
            "train": self.train,
            "verify": self.verify,
            "all": self.run_all,
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

    def build(self, params):
        ub = self.state["builders"]["updatable"]
        ok, data, err = ub.Run("build_base", params)
        if not ok:
            return (0, None, err)
        log.info("Base model built: %s", data["base_path"])
        ok, data, err = ub.Run("build_updatable", params)
        if not ok:
            return (0, None, err)
        log.info("Updatable model built: %s is_updatable=%s", data["updatable_path"], data["is_updatable"])
        ok, info, err = ub.Run("inspect", {"path": data["updatable_path"]})
        if not ok:
            return (0, None, err)
        log.info("Inspect: is_updatable=%s training_inputs=%s updatable_layers=%s optimizer=%s",
                 info["is_updatable"], info.get("training_inputs"), info.get("updatable_layers"), info.get("optimizer"))
        self.state["results"]["build"] = info
        return (1, info, None)

    def gendata(self, params):
        dg = self.state["builders"]["datagen"]
        ok, data, err = dg.Run("generate", params)
        if not ok:
            return (0, None, err)
        log.info("Synthetic data: %d samples class_counts=%s", data["count"], data["class_counts"])
        ok, info, err = dg.Run("summary", params)
        if not ok:
            return (0, None, err)
        log.info("Data summary: mean=%.4f std=%.4f batch_ready=%s",
                 info["feature_mean"], info["feature_std"], info["batch_ready"])
        self.state["results"]["gendata"] = info
        return (1, info, None)

    def train(self, params):
        dg = self.state["builders"]["datagen"]
        ok, info, err = dg.Run("summary", params)
        if not ok or not info.get("batch_ready"):
            return (0, None, ("no_data", "Generate data first (call 'gendata')", 0))
        data_path = dg.state["results"].get("data_path")
        trainer = self.state["builders"]["trainer"]
        ok, data, err = trainer.Run("capture_baseline", params)
        if not ok:
            return (0, None, err)
        log.info("Baseline weights captured: %s", data["layers"])
        ok, train_data, err = trainer.Run("train", {"data_path": data_path})
        if not ok:
            return (0, None, err)
        log.info("Training complete: epochs_run=%d", train_data["epochs_run"])
        for entry in train_data["history"]:
            log.info("  epoch %s loss=%s", entry.get("epoch", "?"), entry.get("loss", "?"))
        ok, data, err = trainer.Run("capture_trained", params)
        if not ok:
            return (0, None, err)
        log.info("Trained model saved: %s", data["trained_path"])
        self.state["results"]["train"] = train_data
        return (1, train_data, None)

    def verify(self, params):
        trainer = self.state["builders"]["trainer"]
        ok, data, err = trainer.Run("verify_weights", params)
        if not ok:
            return (0, None, err)
        log.info("Weights changed: %s", data["any_changed"])
        for layer, d in data["diffs"].items():
            log.info("  %s: w_sum_delta=%.6f w_norm_delta=%.6f changed=%s",
                     layer, d["w_sum_delta"], d["w_norm_delta"], d["changed"])
        ok, report_text, err = trainer.Run("report", params)
        if not ok:
            return (0, None, err)
        log.info("Report:\n%s", report_text)
        self.state["results"]["verify"] = data
        return (1, {"weights_changed": data["any_changed"], "report": report_text}, None)

    def run_all(self, params):
        steps = ["build", "gendata", "train", "verify"]
        results = {}
        for step in steps:
            method = getattr(self, step)
            ok, data, err = method(params)
            if not ok:
                return (0, None, err)
            results[step] = data
        return (1, results, None)


def cli_entry():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    m = Main()
    ok, data, err = m.Run(cmd)
    if not ok:
        log.error("FAILED: %s", err)
        sys.exit(1)
    log.info("DONE: %s", cmd)
    sys.exit(0)


if __name__ == "__main__":
    cli_entry()
