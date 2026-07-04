#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] ErrorFixTrainer.py
#[@SUMMARY] Trains a neural network to classify errors and suggest fixes. Replaces keyword lookup with learned patterns.
#[@CLASS] ErrorFixTrainer
#[@METHOD] extract_features, generate_training_data, train, infer, save_weights, load_weights
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] cli_ai_fix

import os
import sys
import json
import struct
import random
import math
import time
import numpy as np

INPUT_DIM = 40
HIDDEN_DIM = 64
OUTPUT_DIM = 16
WEIGHTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cascade_fix_weights.bin")

ERROR_TYPES = [
    "ModuleNotFoundError", "ImportError", "FileNotFoundError", "AttributeError",
    "KeyError", "IndexError", "IndentationError", "NameError", "ValueError",
    "TypeError", "SyntaxError", "RuntimeError", "ConnectionError",
    "PermissionError", "RecursionError", "UnicodeDecodeError",
]

FIX_ACTIONS = [
    "check_import", "check_import_name", "check_path", "check_attribute",
    "use_get_or_check", "check_length", "fix_indentation", "check_name",
    "validate_input", "check_type", "fix_syntax", "check_permissions",
    "check_connection", "add_base_case", "specify_encoding", "custom",
]

FIX_ACTION_INDEX = {name: i for i, name in enumerate(FIX_ACTIONS)}

RULES = [
    {"error_name": "ModuleNotFoundError", "error_keyword": "modulenotfounderror", "fix_action": "check_import",
     "variations": [
         "ModuleNotFoundError: No module named 'nonexistent_xyz'",
         "ModuleNotFoundError: No module named 'nump'",
         "ModuleNotFoundError: No module named 'some_package'",
         "ModuleNotFoundError: No module named 'tensorflow'",
         "ModuleNotFoundError: No module named 'requests'",
         "ImportError: No module named nonexistent",
         "ModuleNotFoundError: No module named 'pandas'",
         "ModuleNotFoundError: No module named 'flask'",
     ]},
    {"error_name": "ImportError", "error_keyword": "cannot import name", "fix_action": "check_import_name",
     "variations": [
         "ImportError: cannot import name 'nonexistent' from 'os'",
         "ImportError: cannot import name 'wrong_thing' from 'module'",
         "ImportError: cannot import name 'SomeClass' from 'package'",
         "cannot import name xyz from module",
     ]},
    {"error_name": "FileNotFoundError", "error_keyword": "no such file or directory", "fix_action": "check_path",
     "variations": [
         "FileNotFoundError: [Errno 2] No such file or directory: '/nonexistent/file.txt'",
         "FileNotFoundError: No such file or directory: 'missing.json'",
         "FileNotFoundError: [Errno 2] No such file or directory: '/wrong/path'",
         "No such file or directory: './nonexistent.conf'",
         "FileNotFoundError: '/home/user/missing.txt'",
     ]},
    {"error_name": "AttributeError", "error_keyword": "has no attribute", "fix_action": "check_attribute",
     "variations": [
         "AttributeError: 'NoneType' object has no attribute 'split'",
         "AttributeError: 'str' object has no attribute 'nonexistent'",
         "AttributeError: 'list' object has no attribute 'items'",
         "AttributeError: 'dict' object has no attribute 'append'",
         "has no attribute 'some_method'",
     ]},
    {"error_name": "KeyError", "error_keyword": "keyerror", "fix_action": "use_get_or_check",
     "variations": [
         "KeyError: 'missing_key'",
         "KeyError: 'nonexistent'",
         "KeyError: 42",
         "KeyError: 'some_key'",
         "KeyError: 'user_id'",
     ]},
    {"error_name": "IndexError", "error_keyword": "list index out of range", "fix_action": "check_length",
     "variations": [
         "IndexError: list index out of range",
         "IndexError: string index out of range",
         "IndexError: tuple index out of range",
         "IndexError: list assignment index out of range",
         "list index out of range",
     ]},
    {"error_name": "IndentationError", "error_keyword": "expected an indented block", "fix_action": "fix_indentation",
     "variations": [
         "IndentationError: expected an indented block",
         "IndentationError: unexpected indent",
         "IndentationError: unindent does not match any outer indentation level",
         "IndentationError: expected an indented block after 'if' statement",
         "expected an indented block",
     ]},
    {"error_name": "NameError", "error_keyword": "is not defined", "fix_action": "check_name",
     "variations": [
         "NameError: name 'undefined_var' is not defined",
         "NameError: name 'some_function' is not defined",
         "NameError: name 'x' is not defined",
         "NameError: name 'my_class' is not defined",
         "is not defined",
     ]},
    {"error_name": "ValueError", "error_keyword": "invalid literal for", "fix_action": "validate_input",
     "variations": [
         "ValueError: invalid literal for int() with base 10: 'abc'",
         "ValueError: invalid literal for float(): 'xyz'",
         "ValueError: could not convert string to float: 'hello'",
         "ValueError: invalid literal for int() with base 10: 'not_a_number'",
     ]},
    {"error_name": "TypeError", "error_keyword": "unsupported operand type", "fix_action": "check_type",
     "variations": [
         "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
         "TypeError: unsupported operand type(s) for *: 'str' and 'int'",
         "TypeError: can only concatenate str (not 'int') to str",
         "TypeError: unsupported operand type(s) for /: 'str' and 'int'",
         "TypeError: argument of type 'int' is not iterable",
     ]},
    {"error_name": "SyntaxError", "error_keyword": "invalid syntax", "fix_action": "fix_syntax",
     "variations": [
         "SyntaxError: invalid syntax",
         "SyntaxError: unexpected EOF while parsing",
         "SyntaxError: EOL while scanning string literal",
         "SyntaxError: invalid syntax. Maybe you meant '==' or ':='?",
         "SyntaxError: '(' was never closed",
     ]},
    {"error_name": "PermissionError", "error_keyword": "permission denied", "fix_action": "check_permissions",
     "variations": [
         "PermissionError: [Errno 13] Permission denied: '/etc/passwd'",
         "PermissionError: [Errno 13] Permission denied: '/root/file'",
         "PermissionError: [Errno 13] Permission denied: '/protected'",
         "Permission denied: '/system/file'",
     ]},
    {"error_name": "ConnectionError", "error_keyword": "connection refused", "fix_action": "check_connection",
     "variations": [
         "ConnectionError: [Errno 61] Connection refused",
         "ConnectionRefusedError: [Errno 61] Connection refused",
         "ConnectionError: Failed to establish a connection",
         "Connection refused (Connection refused)",
     ]},
    {"error_name": "RecursionError", "error_keyword": "maximum recursion depth", "fix_action": "add_base_case",
     "variations": [
         "RecursionError: maximum recursion depth exceeded",
         "RecursionError: maximum recursion depth exceeded in comparison",
         "RecursionError: maximum recursion depth exceeded while calling a Python object",
         "maximum recursion depth exceeded",
     ]},
    {"error_name": "UnicodeDecodeError", "error_keyword": "codec can't decode", "fix_action": "specify_encoding",
     "variations": [
         "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff",
         "UnicodeDecodeError: 'ascii' codec can't decode byte 0xc3",
         "UnicodeDecodeError: 'utf-8' codec can't decode bytes in position",
         "codec can't decode byte",
     ]},
]

CATEGORY_KEYWORDS = {
    "import": ["import", "module", "modulenotfound"],
    "syntax": ["syntax", "indent", "eol", "eof", "closed"],
    "runtime": ["runtime", "recursion", "maximum"],
    "type": ["type", "operand", "concatenate", "iterable"],
    "file": ["filenotfounderror", "no such file", "errno 2"],
    "attribute": ["attribute", "object"],
    "key": ["keyerror", "key"],
    "index": ["index", "range"],
    "name": ["name", "defined"],
    "value": ["value", "literal", "convert"],
    "permission": ["permission", "errno 13"],
    "connection": ["connection", "refused", "errno 61"],
    "encoding": ["codec", "decode", "unicode", "byte"],
    "division": ["division", "zero", "divide"],
}


class ErrorFixTrainer:
    """Trains a 40->64->16 MLP to classify errors and suggest fixes.

    Feature extraction: 40D vector from error text.
    - Error type one-hot (16 dims)
    - Category presence (14 dims)
    - Text properties (10 dims: has_traceback, has_file, has_line, length, num_lines, etc.)

    Training: SGD with momentum on cross-entropy loss.
    Inference: Forward pass → softmax → argmax → fix action.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "weights_file": WEIGHTS_FILE,
                "epochs": 300,
                "learning_rate": 0.005,
                "momentum": 0.9,
                "noise_level": 0.1,
            },
            "weights": None,
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
        self.loadWeights()

    def Run(self, command, params=None):
        params = params or {}
        if command == "train":
            return self.cmdTrain(params)
        if command == "infer":
            return self.cmdInfer(params)
        if command == "status":
            return self.cmdStatus(params)
        if command == "read_state":
            return self.readState(params)
        if command == "set_config":
            return self.setConfig(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown: " + str(command), 0))

    def p(self, params, key, fallback=None):
        if not isinstance(params, dict):
            return fallback
        return params.get(key, fallback)

    def extractFeatures(self, errorText):
        text = errorText.lower()

        errorLine = text
        for line in text.split("\n"):
            if "error" in line or "exception" in line or "refused" in line:
                errorLine = line.strip()
                break

        features = [0.0] * INPUT_DIM

        for i, etype in enumerate(ERROR_TYPES):
            if etype.lower() in errorLine:
                features[i] = 1.0

        for j, (cat, keywords) in enumerate(CATEGORY_KEYWORDS.items()):
            for kw in keywords:
                if kw in errorLine:
                    features[16 + j] = 1.0
                    break

        features[30] = 1.0 if "traceback" in text else 0.0
        features[31] = 1.0 if "errno 2" in errorLine or "no such file" in errorLine else 0.0
        features[32] = 1.0 if "line" in text else 0.0
        features[33] = min(len(errorLine) / 500.0, 1.0)
        features[34] = min(text.count("\n") / 20.0, 1.0)
        features[35] = 1.0 if "error" in errorLine else 0.0
        features[36] = 1.0 if "exception" in errorLine else 0.0
        features[37] = 1.0 if "warning" in errorLine else 0.0
        features[38] = 1.0 if any(c.isdigit() for c in errorLine) else 0.0
        features[39] = 1.0

        return features

    def generateTrainingData(self):
        samples = []
        labels = []

        for rule in RULES:
            fixIdx = FIX_ACTION_INDEX.get(rule["fix_action"], 15)
            target = [0.0] * OUTPUT_DIM
            target[fixIdx] = 1.0

            for variation in rule["variations"]:
                features = self.extractFeatures(variation)
                samples.append(features)
                labels.append(target)

                noise = random.gauss(0, self.state["config"]["noise_level"])
                noisy = [min(1.0, max(0.0, f + noise)) for f in features]
                samples.append(noisy)
                labels.append(target)

                for _ in range(5):
                    shuffled = variation.split()
                    if len(shuffled) > 3:
                        random.shuffle(shuffled)
                        shuffledText = " ".join(shuffled)
                        noisyFeat = self.extractFeatures(shuffledText)
                        for k in range(len(noisyFeat)):
                            noisyFeat[k] = min(1.0, max(0.0, noisyFeat[k] + random.gauss(0, 0.05)))
                        samples.append(noisyFeat)
                        labels.append(target)

        return samples, labels

    def forwardPass(self, features, weights):
        w1 = weights["w1"]
        b1 = weights["b1"]
        w2 = weights["w2"]
        b2 = weights["b2"]
        h = np.maximum(0, w1 @ np.array(features) + b1)
        logits = w2 @ h + b2
        logits = logits - np.max(logits)
        exps = np.exp(logits)
        output = exps / np.sum(exps)
        return output, h

    def train(self, samples, labels, epochs, lr, momentum):
        W1 = np.random.randn(HIDDEN_DIM, INPUT_DIM).astype(np.float32) * 0.1
        b1 = np.zeros(HIDDEN_DIM, dtype=np.float32)
        W2 = np.random.randn(OUTPUT_DIM, HIDDEN_DIM).astype(np.float32) * 0.1
        b2 = np.zeros(OUTPUT_DIM, dtype=np.float32)

        vW1 = np.zeros_like(W1)
        vb1 = np.zeros_like(b1)
        vW2 = np.zeros_like(W2)
        vb2 = np.zeros_like(b2)

        X = np.array(samples, dtype=np.float32)
        Y = np.array(labels, dtype=np.float32)
        n = len(samples)

        for epoch in range(epochs):
            totalLoss = 0.0
            indices = np.random.permutation(n)

            for idx in indices:
                x = X[idx]
                y = Y[idx]

                h = np.maximum(0, W1 @ x + b1)
                logits = W2 @ h + b2
                logits = logits - np.max(logits)
                exps = np.exp(logits)
                out = exps / np.sum(exps)

                eps = 1e-7
                totalLoss += -np.sum(y * np.log(out + eps))

                dOut = out - y
                dW2 = np.outer(dOut, h)
                db2 = dOut
                dH = (W2.T @ dOut) * (h > 0).astype(np.float32)
                dW1 = np.outer(dH, x)
                db1 = dH

                vW1 = momentum * vW1 - lr * dW1
                vb1 = momentum * vb1 - lr * db1
                vW2 = momentum * vW2 - lr * dW2
                vb2 = momentum * vb2 - lr * db2
                W1 += vW1
                b1 += vb1
                W2 += vW2
                b2 += vb2

            if (epoch + 1) % 50 == 0:
                avgLoss = totalLoss / n
                sys.stderr.write("Epoch %d/%d  Loss: %.4f\n" % (epoch + 1, epochs, avgLoss))

        return {"w1": W1, "b1": b1, "w2": W2, "b2": b2}

    def saveWeights(self, weights):
        path = self.state["config"]["weights_file"]
        with open(path, "wb") as f:
            f.write(struct.pack("<I", INPUT_DIM))
            f.write(struct.pack("<I", HIDDEN_DIM))
            f.write(struct.pack("<I", OUTPUT_DIM))
            w1 = np.asarray(weights["w1"], dtype=np.float32)
            b1 = np.asarray(weights["b1"], dtype=np.float32)
            w2 = np.asarray(weights["w2"], dtype=np.float32)
            b2 = np.asarray(weights["b2"], dtype=np.float32)
            f.write(w1.tobytes())
            f.write(b1.tobytes())
            f.write(w2.tobytes())
            f.write(b2.tobytes())

    def loadWeights(self):
        path = self.state["config"]["weights_file"]
        if not os.path.exists(path):
            self.state["weights"] = None
            return False
        try:
            with open(path, "rb") as f:
                inDim = struct.unpack("<I", f.read(4))[0]
                hidDim = struct.unpack("<I", f.read(4))[0]
                outDim = struct.unpack("<I", f.read(4))[0]
                if inDim != INPUT_DIM or hidDim != HIDDEN_DIM or outDim != OUTPUT_DIM:
                    self.state["weights"] = None
                    return False
                w1 = np.frombuffer(f.read(HIDDEN_DIM * INPUT_DIM * 4), dtype=np.float32).reshape(HIDDEN_DIM, INPUT_DIM)
                b1 = np.frombuffer(f.read(HIDDEN_DIM * 4), dtype=np.float32)
                w2 = np.frombuffer(f.read(OUTPUT_DIM * HIDDEN_DIM * 4), dtype=np.float32).reshape(OUTPUT_DIM, HIDDEN_DIM)
                b2 = np.frombuffer(f.read(OUTPUT_DIM * 4), dtype=np.float32)
                self.state["weights"] = {"w1": w1, "b1": b1, "w2": w2, "b2": b2}
                return True
        except Exception:
            self.state["weights"] = None
            return False

    def infer(self, errorText):
        if not self.state["weights"]:
            return None, 0.0
        features = self.extractFeatures(errorText)
        output, _ = self.forwardPass(features, self.state["weights"])
        bestIdx = int(np.argmax(output))
        bestVal = float(output[bestIdx])
        return FIX_ACTIONS[bestIdx], bestVal

    def cmdTrain(self, params):
        try:
            epochs = int(self.p(params, "epochs", self.state["config"]["epochs"]))
            lr = float(self.p(params, "learning_rate", self.state["config"]["learning_rate"]))
            momentum = float(self.p(params, "momentum", self.state["config"]["momentum"]))
            samples, labels = self.generateTrainingData()
            t0 = time.time()
            weights = self.train(samples, labels, epochs, lr, momentum)
            elapsed = time.time() - t0
            self.state["weights"] = weights
            self.saveWeights(weights)
            correct = 0
            for i in range(len(samples)):
                output, _ = self.forwardPass(samples[i], weights)
                bestIdx = int(np.argmax(output))
                if labels[i][bestIdx] > 0.5:
                    correct += 1
            accuracy = correct / len(samples) if samples else 0.0
            return (1, {
                "epochs": epochs,
                "samples": len(samples),
                "accuracy": round(accuracy, 4),
                "time_sec": round(elapsed, 2),
                "weights_file": self.state["config"]["weights_file"],
            }, None)
        except Exception as e:
            return (0, None, ("TRAIN_ERROR", str(e), 0))

    def cmdInfer(self, params):
        try:
            errorText = self.p(params, "error_text", "")
            if not errorText:
                return (0, None, ("NO_ERROR_TEXT", "error_text parameter required", 0))
            if not self.state["weights"]:
                return (1, {"found": False, "message": "Model not trained. Using fallback."}, None)
            action, confidence = self.infer(errorText)
            return (1, {
                "found": True,
                "fix_action": action,
                "confidence": round(confidence, 4),
            }, None)
        except Exception as e:
            return (0, None, ("INFER_ERROR", str(e), 0))

    def cmdStatus(self, params):
        hasModel = self.state["weights"] is not None
        weightsSize = 0
        if os.path.exists(self.state["config"]["weights_file"]):
            weightsSize = os.path.getsize(self.state["config"]["weights_file"])
        return (1, {
            "model_loaded": hasModel,
            "weights_file": self.state["config"]["weights_file"],
            "weights_size": weightsSize,
            "input_dim": INPUT_DIM,
            "hidden_dim": HIDDEN_DIM,
            "output_dim": OUTPUT_DIM,
            "fix_actions": FIX_ACTIONS,
            "rules_count": len(RULES),
        }, None)

    def readState(self, params=None):
        return (1, dict(self.state), None)

    def setConfig(self, params=None):
        if not isinstance(params, dict):
            return (0, None, ("NO_PARAMS", "config dict required", 0))
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, {"updated": list(params.keys())}, None)


if __name__ == "__main__":
    trainer = ErrorFixTrainer()
    if len(sys.argv) < 2:
        print("Usage: ErrorFixTrainer.py <command>")
        print("Commands: train, infer <error_text>, status")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "train":
        ok, data, err = trainer.Run("train", {})
        if ok:
            print("Training complete:")
            print("  Epochs: %d" % data["epochs"])
            print("  Samples: %d" % data["samples"])
            print("  Accuracy: %.1f%%" % (data["accuracy"] * 100))
            print("  Time: %.2fs" % data["time_sec"])
            print("  Weights: %s" % data["weights_file"])
        else:
            print("Training failed: %s" % str(err))
        sys.exit(0 if ok else 1)
    if cmd == "status":
        ok, data, err = trainer.Run("status", {})
        if ok:
            print("ErrorFix Model Status:")
            print("  Loaded: %s" % data["model_loaded"])
            print("  Weights: %s (%d bytes)" % (data["weights_file"], data["weights_size"]))
            print("  Architecture: %d->%d->%d" % (data["input_dim"], data["hidden_dim"], data["output_dim"]))
            print("  Fix actions: %d" % data["output_dim"])
            print("  Rules: %d" % data["rules_count"])
            print("  Actions:")
            for i, action in enumerate(data["fix_actions"]):
                print("    [%d] %s" % (i, action))
        sys.exit(0)
    if cmd == "infer":
        if len(sys.argv) < 3:
            print("Usage: ErrorFixTrainer.py infer <error_text>")
            sys.exit(1)
        errorText = " ".join(sys.argv[2:])
        ok, data, err = trainer.Run("infer", {"error_text": errorText})
        if ok and data.get("found"):
            print("PREDICTION:")
            print("  Fix action: %s" % data["fix_action"])
            print("  Confidence: %.1f%%" % (data["confidence"] * 100))
        elif ok:
            print("NO_MODEL: %s" % data.get("message", ""))
        else:
            print("ERROR: %s" % str(err))
        sys.exit(0)
    print("Unknown command: %s" % cmd)
    sys.exit(1)
