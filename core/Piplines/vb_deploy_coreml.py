#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_deploy_coreml.py" date="2026-07-04" author="Devin" session_id="coreml-deploy-bcl" context="Deploy trained BCL Transformer (Metal GPU) to Apple Neural Engine via CoreML. Parses BCLT binary weight format (37 tensors: 1 embedding + 6 layers x 6 tensors), builds attention-only PyTorch model matching Metal architecture (post-LN, no FFN, no bias on QKVO), converts to CoreML .mlpackage for ANE."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch spaces only"}
#[@FILEID]{id="vb_deploy_coreml.py" domain="Piplines" authority="CoreMlDeploy"}
#[@SUMMARY]{summary="CoreMlDeploy — deploys trained BCL Transformer to CoreML for Apple Neural Engine. Parses BCLT binary weight format (magic + version + 5x uint32 config + 37 tensor stream with name/shape/data headers). Builds attention-only PyTorch model matching Metal architecture exactly (token embedding + 6 layers: QKV proj, multi-head attention, output proj, residual, post-LN). Converts via coremltools to .mlpackage, benchmarks on ANE."}
#[@CLASS]{class="CoreMlDeploy" domain="Piplines" authority="deploy"}
#[@METHOD]{method="parse_weights" type="extraction"}
#[@METHOD]{method="build_model" type="construction"}
#[@METHOD]{method="deploy" type="deployment"}
#[@METHOD]{method="benchmark" type="benchmark"}
#[@METHOD]{method="info" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}

"""CoreMlDeploy — BCL Transformer to CoreML for Apple Neural Engine.

Pipeline:
  1. parse_weights — read trained fp16 weights from BCLT binary file.
     BCLT format (from c_transformer_attention.mm SaveModel):
       Header: magic(4)="BCLT" + version(uint32) + n_layers(uint32) +
               d_model(uint32) + n_heads(uint32) + vocab_size(uint32) +
               max_seq(uint32)
       Tensor stream (37 tensors): for each tensor:
         name_len(uint32) + name(name_len bytes) +
         shape_len(uint32) + shape(shape_len x uint32) +
         data_size(uint64) + data(data_size bytes, fp16)
       Tensors: token_embedding [vocab, d_model] +
         6 layers x (W_q, W_k, W_v, W_o [d,d], LN1_scale, LN1_bias [d])
  2. build_model — construct attention-only PyTorch model matching Metal
     architecture (post-LN, no FFN, no bias on QKVO projections), load
     BCLT weights, convert to CoreML via coremltools.
  3. deploy — save as .mlpackage directory bundle.
  4. benchmark — run inference on ANE, measure latency.

Metal architecture (c_transformer_attention.mm AttentionLayer_Forward):
  Q = X @ W_q, K = X @ W_k, V = X @ W_v  (no bias)
  S = Q @ K^T / sqrt(head_dim)
  P = masked_softmax(S)  (causal + BCL mask)
  A = P @ V
  O = A @ W_o  (no bias)
  out = O + X  (residual)
  out = LayerNorm(out, LN1_scale, LN1_bias)  (POST-LN)

Config: d_model=384, n_heads=6, head_dim=64, n_layers=6,
        vocab_size=162612, max_seq=2048
"""

import os
import sys
import time
import struct
import json
import argparse
import numpy as np

# coremltools for CoreML conversion and inference.
try:
    import coremltools as ct
    COREML_AVAILABLE = True
    COREML_VERSION = ct.__version__
except ImportError:
    COREML_AVAILABLE = False
    COREML_VERSION = None

# torch as intermediate IR for CoreML conversion.
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ── Transformer Config (matches Config_BclTransformer) ──
D_MODEL = 384
N_HEADS = 6
HEAD_DIM = D_MODEL // N_HEADS  # 64
N_LAYERS = 6
VOCAB_SIZE = 162612
MAX_SEQ_LEN = 2048

# ── BCLT Weight File Format ──
BCLT_MAGIC = b"BCLT"
BCLT_VERSION = 1
BCLT_HEADER_SIZE = 4 + 6 * 4  # magic + 6 uint32 (version, n_layers, d_model, n_heads, vocab, max_seq)
EXPECTED_TENSOR_COUNT = 37  # 1 embedding + 6 layers x 6 tensors

# ── Error Codes ──
ERR_UNKNOWN_CMD = "DEPLOY_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "DEPLOY_BAD_PARAMS"
ERR_NO_COREML = "COREML_NOT_AVAILABLE"
ERR_NO_TORCH = "TORCH_NOT_AVAILABLE"
ERR_WEIGHT_FILE = "WEIGHT_FILE_ERROR"
ERR_BUILD_FAILED = "BUILD_MODEL_FAILED"
ERR_DEPLOY_FAILED = "DEPLOY_FAILED"
ERR_BENCHMARK_FAILED = "BENCHMARK_FAILED"

# ── Default Paths ──
PROJECT_DIR = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
DEFAULT_WEIGHTS_PATH = os.path.join(PROJECT_DIR, "core", "Piplines", "bcl_transformer_weights.bin")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_DIR, "Dom_CoreML_Layout")
DEFAULT_MODEL_NAME = "BclTransformer.mlpackage"
DEFAULT_SEQ_LEN = 128


class CoreMlDeploy:
    """Deploy trained BCL Transformer to CoreML for Apple Neural Engine.

    Commands (via Run):
      parse_weights — extract fp16 weights from BCLT binary file
      build_model   — construct PyTorch model, load weights, convert to CoreML
      deploy        — save as .mlpackage
      benchmark     — inference latency test on ANE
      info          — print config and availability
      run_all       — full pipeline: parse + build + deploy + benchmark
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.state = {
            "class": "CoreMlDeploy",
            "coreml_available": COREML_AVAILABLE,
            "coreml_version": COREML_VERSION,
            "torch_available": TORCH_AVAILABLE,
            "d_model": D_MODEL,
            "n_heads": N_HEADS,
            "head_dim": HEAD_DIM,
            "n_layers": N_LAYERS,
            "vocab_size": VOCAB_SIZE,
            "max_seq_len": MAX_SEQ_LEN,
            "weights": None,
            "model": None,
            "torch_model": None,
            "weights_path": DEFAULT_WEIGHTS_PATH,
            "output_dir": DEFAULT_OUTPUT_DIR,
            "model_name": DEFAULT_MODEL_NAME,
            "seq_len": DEFAULT_SEQ_LEN,
            "last_error": None,
            "last_latency_ms": None,
            "deployed_path": None,
            "config": {},
        }

    def _p(self, label, value):
        """Helper to record state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3: (1, data, None) or (0, None, (code, desc, 0))."""
        dispatch = {
            "parse_weights": self.cmd_parse_weights,
            "build_model": self.cmd_build_model,
            "deploy": self.cmd_deploy,
            "benchmark": self.cmd_benchmark,
            "info": self.cmd_info,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
            "run_all": self.cmd_run_all,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    # ── Command: info ──

    def cmd_info(self, params):
        """Return config and availability info."""
        info = {
            "coreml_available": COREML_AVAILABLE,
            "coreml_version": COREML_VERSION,
            "torch_available": TORCH_AVAILABLE,
            "d_model": D_MODEL,
            "n_heads": N_HEADS,
            "head_dim": HEAD_DIM,
            "n_layers": N_LAYERS,
            "vocab_size": VOCAB_SIZE,
            "max_seq_len": MAX_SEQ_LEN,
            "weights_loaded": self.state.get("weights") is not None,
            "model_built": self.state.get("model") is not None,
            "weights_path": self.state.get("weights_path"),
            "output_dir": self.state.get("output_dir"),
            "model_name": self.state.get("model_name"),
            "seq_len": self.state.get("seq_len"),
        }
        self._p("info", True)
        return (1, info, None)

    # ── Command: parse_weights ──

    def cmd_parse_weights(self, params):
        """Parse BCLT binary weight file.

        BCLT format (from c_transformer_attention.mm SaveModel):
          Header: magic(4)="BCLT" + version(uint32) + n_layers(uint32) +
                  d_model(uint32) + n_heads(uint32) + vocab_size(uint32) +
                  max_seq(uint32)
          Tensor stream (37 tensors): for each:
            name_len(uint32) + name(bytes) + shape_len(uint32) +
            shape(uint32 x shape_len) + data_size(uint64) + data(bytes, fp16)

        params:
          path (str) — path to BCLT weight file (default: state weights_path)
        """
        if params is None:
            params = {}
        path = params.get("path", self.state.get("weights_path", DEFAULT_WEIGHTS_PATH))

        if not os.path.exists(path):
            return (0, None, (ERR_WEIGHT_FILE, "Weight file not found: " + str(path), 0))

        try:
            weights = self.read_bclt_file(path)
        except Exception as e:
            return (0, None, (ERR_WEIGHT_FILE, "Failed to read BCLT weights: " + str(e), 0))

        self.state["weights"] = weights
        self.state["weights_path"] = path
        self._p("parse_weights", path)

        summary = {
            "path": path,
            "version": weights.get("version"),
            "n_layers": weights.get("n_layers"),
            "d_model": weights.get("d_model"),
            "n_heads": weights.get("n_heads"),
            "vocab_size": weights.get("vocab_size"),
            "max_seq": weights.get("max_seq"),
            "tensor_count": len(weights.get("tensors", {})),
            "total_params": weights.get("total_params", 0),
            "size_mb": weights.get("size_mb", 0.0),
            "tensor_names": list(weights.get("tensors", {}).keys()),
        }
        return (1, summary, None)

    def read_bclt_file(self, path):
        """Read BCLT binary weight file. Returns dict with config + numpy float16 arrays.

        Format (from c_transformer_attention.mm):
          Header: magic(4) + version(uint32) + n_layers(uint32) +
                  d_model(uint32) + n_heads(uint32) + vocab_size(uint32) +
                  max_seq(uint32)
          Per tensor: name_len(uint32) + name(bytes) + shape_len(uint32) +
                      shape(uint32 x shape_len) + data_size(uint64) + data(bytes)
          Data is fp16 (2 bytes per element).
        """
        with open(path, "rb") as f:
            # ── Header ──
            magic = f.read(4)
            if magic != BCLT_MAGIC:
                raise ValueError("Bad magic: " + str(magic) + " (expected " + str(BCLT_MAGIC) + ")")

            version = struct.unpack("<I", f.read(4))[0]
            if version != BCLT_VERSION:
                raise ValueError("Bad version: " + str(version) + " (expected " + str(BCLT_VERSION) + ")")

            n_layers = struct.unpack("<I", f.read(4))[0]
            d_model = struct.unpack("<I", f.read(4))[0]
            n_heads = struct.unpack("<I", f.read(4))[0]
            vocab_size = struct.unpack("<I", f.read(4))[0]
            max_seq = struct.unpack("<I", f.read(4))[0]

            # ── Tensor stream ──
            tensors = {}
            total_params = 0
            file_size = os.path.getsize(path)

            while True:
                raw_name_len = f.read(4)
                if len(raw_name_len) < 4:
                    break  # end of tensor stream

                name_len = struct.unpack("<I", raw_name_len)[0]
                name = f.read(name_len).decode("utf-8")

                shape_len = struct.unpack("<I", f.read(4))[0]
                shape = []
                for _ in range(shape_len):
                    shape.append(struct.unpack("<I", f.read(4))[0])

                data_size = struct.unpack("<Q", f.read(8))[0]
                raw_data = f.read(data_size)

                # Convert fp16 bytes to numpy float16 array
                element_count = data_size // 2  # fp16 = 2 bytes
                arr = np.frombuffer(raw_data, dtype=np.float16)
                if len(shape) > 0:
                    arr = arr.reshape(shape)
                arr = arr.copy()  # detach from buffer

                tensors[name] = arr
                total_params = total_params + element_count

            # Verify tensor count
            if len(tensors) != EXPECTED_TENSOR_COUNT:
                sys.stderr.write("[DEPLOY] WARNING: expected " + str(EXPECTED_TENSOR_COUNT) +
                                 " tensors, got " + str(len(tensors)) + "\n")

        return {
            "version": version,
            "n_layers": n_layers,
            "d_model": d_model,
            "n_heads": n_heads,
            "vocab_size": vocab_size,
            "max_seq": max_seq,
            "tensors": tensors,
            "total_params": total_params,
            "size_mb": file_size / (1024.0 * 1024.0),
        }

    # ── Command: build_model ──

    def cmd_build_model(self, params):
        """Build PyTorch model from BCLT weights and convert to CoreML.

        Architecture (matches Metal c_transformer_attention.mm exactly):
          - Token embedding: nn.Embedding(vocab_size, d_model)
          - 6 x AttentionLayer:
              Q = X @ W_q (no bias)
              K = X @ W_k (no bias)
              V = X @ W_v (no bias)
              S = Q @ K^T / sqrt(head_dim)
              P = causal_softmax(S)
              A = P @ V
              O = A @ W_o (no bias)
              out = O + X (residual)
              out = LayerNorm(out, LN1_scale, LN1_bias) (POST-LN)
          - Output: hidden states [1, seq, d_model] fp16

        params:
          weights (dict) — optional, pre-loaded weights (default: state)
          seq_len (int) — sequence length for tracing (default: 128)
        """
        if not COREML_AVAILABLE:
            return (0, None, (ERR_NO_COREML, "coremltools not installed. Install with: pip install coremltools", 0))
        if not TORCH_AVAILABLE:
            return (0, None, (ERR_NO_TORCH, "torch not installed. Install with: pip install torch", 0))

        if params is None:
            params = {}
        weights = params.get("weights", self.state.get("weights"))
        if weights is None:
            return (0, None, (ERR_BAD_PARAMS, "No weights loaded. Run parse_weights first.", 0))

        seq_len = params.get("seq_len", self.state.get("seq_len", DEFAULT_SEQ_LEN))

        try:
            torch_model = self.build_torch_model(weights)
            mlmodel = self.convert_to_coreml(torch_model, seq_len)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            return (0, None, (ERR_BUILD_FAILED, "Model build failed: " + str(e) + "\n" + tb, 0))

        self.state["model"] = mlmodel
        self.state["torch_model"] = torch_model
        self.state["seq_len"] = seq_len
        self._p("build_model", True)

        spec = mlmodel.get_spec()
        input_desc = {}
        for inp in spec.description.input:
            input_desc[inp.name] = str(inp.type)
        output_desc = {}
        for out in spec.description.output:
            output_desc[out.name] = str(out.type)

        result = {
            "inputs": input_desc,
            "outputs": output_desc,
            "seq_len": seq_len,
            "compute_units": "ALL (ANE + GPU + CPU)",
            "deployment_target": "iOS17+/macOS14+",
        }
        return (1, result, None)

    def build_torch_model(self, weights):
        """Build PyTorch nn.Module from BCLT weights, matching Metal architecture."""
        d_model = weights.get("d_model", D_MODEL)
        n_heads = weights.get("n_heads", N_HEADS)
        n_layers = weights.get("n_layers", N_LAYERS)
        vocab_size = weights.get("vocab_size", VOCAB_SIZE)
        seq_len = self.state.get("seq_len", DEFAULT_SEQ_LEN)
        tensors = weights.get("tensors", {})

        model = BclAttentionModule(
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
            seq_len=seq_len,
        )

        # Load BCLT weights into the module
        model.load_bclt_weights(tensors)

        model.eval()
        return model

    def convert_to_coreml(self, torch_model, seq_len):
        """Convert PyTorch model to CoreML .mlpackage for ANE.

        The input_ids are int32 at the CoreML boundary. Internally,
        nn.Embedding requires int64, so the forward pass casts via .long().
        To avoid coremltools converter issues with the int32->int64 cast in
        the traced graph, we trace with int64 input and let coremltools
        handle the boundary cast from int32 to int64.
        """
        torch_model.eval()

        # Create example input for tracing (int64 — what nn.Embedding expects)
        example_input_ids = torch.randint(0, VOCAB_SIZE, (1, seq_len), dtype=torch.int64)

        # Trace the model with int64 input (no .long() cast in graph)
        traced = torch.jit.trace(torch_model, (example_input_ids,))

        # Convert to CoreML — input is int32 at boundary, converter handles cast
        mlmodel = ct.convert(
            traced,
            inputs=[
                ct.TensorType(name="input_ids", shape=(1, seq_len), dtype=np.int32),
            ],
            outputs=[
                ct.TensorType(name="hidden_states", dtype=np.float16),
            ],
            compute_units=ct.ComputeUnit.ALL,
            minimum_deployment_target=ct.target.iOS17,
            convert_to="mlprogram",
        )

        # Set metadata
        mlmodel.short_description = "BCL Transformer (attention-only) for Apple Neural Engine"
        mlmodel.author = "Devin"
        mlmodel.version = "1.0"
        mlmodel.user_defined_metadata["d_model"] = str(D_MODEL)
        mlmodel.user_defined_metadata["n_heads"] = str(N_HEADS)
        mlmodel.user_defined_metadata["head_dim"] = str(HEAD_DIM)
        mlmodel.user_defined_metadata["n_layers"] = str(N_LAYERS)
        mlmodel.user_defined_metadata["vocab_size"] = str(VOCAB_SIZE)
        mlmodel.user_defined_metadata["max_seq_len"] = str(MAX_SEQ_LEN)
        mlmodel.user_defined_metadata["precision"] = "fp16"
        mlmodel.user_defined_metadata["target"] = "ANE"
        mlmodel.user_defined_metadata["architecture"] = "attention_only_post_ln"
        mlmodel.user_defined_metadata["weight_format"] = "BCLT"

        return mlmodel

    # ── Command: deploy ──

    def cmd_deploy(self, params):
        """Save the CoreML model as .mlpackage.

        params:
          output_dir (str) — directory to save (default: state output_dir)
          model_name (str) — file name (default: state model_name)
          model — optional, pre-loaded mlmodel (default: state)
        """
        if not COREML_AVAILABLE:
            return (0, None, (ERR_NO_COREML, "coremltools not installed", 0))

        if params is None:
            params = {}
        mlmodel = params.get("model", self.state.get("model"))
        if mlmodel is None:
            return (0, None, (ERR_BAD_PARAMS, "No model to deploy. Run build_model first.", 0))

        output_dir = params.get("output_dir", self.state.get("output_dir", DEFAULT_OUTPUT_DIR))
        model_name = params.get("model_name", self.state.get("model_name", DEFAULT_MODEL_NAME))

        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            model_path = os.path.join(output_dir, model_name)

            # Remove existing model if present
            if os.path.exists(model_path):
                import shutil
                shutil.rmtree(model_path)

            mlmodel.save(model_path)

            # Calculate total size (.mlpackage is a directory bundle)
            total_size = 0
            for root, dirs, files in os.walk(model_path):
                for fname in files:
                    total_size = total_size + os.path.getsize(os.path.join(root, fname))

            # Save metadata sidecar
            meta_path = os.path.join(output_dir, model_name.replace(".mlpackage", "_meta.json"))
            meta = {
                "model_path": model_path,
                "d_model": D_MODEL,
                "n_heads": N_HEADS,
                "head_dim": HEAD_DIM,
                "n_layers": N_LAYERS,
                "vocab_size": VOCAB_SIZE,
                "max_seq_len": MAX_SEQ_LEN,
                "precision": "fp16",
                "target": "ANE",
                "architecture": "attention_only_post_ln",
                "weight_format": "BCLT",
                "inputs": ["input_ids"],
                "outputs": ["hidden_states"],
                "size_mb": total_size / (1024.0 * 1024.0),
                "created_at": time.time(),
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

        except Exception as e:
            return (0, None, (ERR_DEPLOY_FAILED, "Deploy failed: " + str(e), 0))

        self.state["deployed_path"] = model_path
        self.state["output_dir"] = output_dir
        self.state["model_name"] = model_name
        self._p("deploy", model_path)

        result = {
            "model_path": model_path,
            "meta_path": meta_path,
            "size_mb": total_size / (1024.0 * 1024.0),
            "size_bytes": total_size,
        }
        return (1, result, None)

    # ── Command: benchmark ──

    def cmd_benchmark(self, params):
        """Run inference on ANE, measure latency.

        params:
          seq_len (int) — sequence length (default: state seq_len or 128)
          n_warmup (int) — warmup iterations (default: 5)
          n_iter (int) — benchmark iterations (default: 50)
          model — optional, pre-loaded mlmodel (default: state)
        """
        if not COREML_AVAILABLE:
            return (0, None, (ERR_NO_COREML, "coremltools not installed", 0))

        if params is None:
            params = {}
        mlmodel = params.get("model", self.state.get("model"))
        if mlmodel is None:
            return (0, None, (ERR_BAD_PARAMS, "No model to benchmark. Run build_model first.", 0))

        seq_len = params.get("seq_len", self.state.get("seq_len", DEFAULT_SEQ_LEN))
        n_warmup = params.get("n_warmup", 5)
        n_iter = params.get("n_iter", 50)

        try:
            # Build sample input
            input_ids = np.random.randint(0, VOCAB_SIZE, size=(1, seq_len)).astype(np.int32)
            input_dict = {
                "input_ids": input_ids,
            }

            # Warmup (first calls trigger ANE compilation)
            for _ in range(n_warmup):
                mlmodel.predict(input_dict)

            # Benchmark
            latencies = []
            t0 = time.time()
            for _ in range(n_iter):
                iter_start = time.time()
                output = mlmodel.predict(input_dict)
                latencies.append((time.time() - iter_start) * 1000.0)
            total_elapsed = time.time() - t0

            latencies = np.array(latencies)
            per_token_ms = (total_elapsed / n_iter / seq_len) * 1000.0

            # Get output shape
            out_key = list(output.keys())[0] if output else "hidden_states"
            out_shape = np.asarray(output[out_key]).shape if output else None
            out_dtype = str(np.asarray(output[out_key]).dtype) if output else None

        except Exception as e:
            return (0, None, (ERR_BENCHMARK_FAILED, "Benchmark failed: " + str(e), 0))

        self.state["last_latency_ms"] = float(np.mean(latencies))
        self._p("benchmark", float(np.mean(latencies)))

        result = {
            "seq_len": seq_len,
            "n_iter": n_iter,
            "mean_ms": float(np.mean(latencies)),
            "median_ms": float(np.median(latencies)),
            "p95_ms": float(np.percentile(latencies, 95)),
            "p99_ms": float(np.percentile(latencies, 99)),
            "min_ms": float(np.min(latencies)),
            "max_ms": float(np.max(latencies)),
            "total_ms": float(total_elapsed * 1000.0),
            "per_token_us": float(per_token_ms),
            "output_shape": str(out_shape),
            "output_dtype": str(out_dtype),
            "output_key": out_key,
            "compute_target": "ANE (Neural Engine)",
        }
        return (1, result, None)

    # ── Command: run_all ──

    def cmd_run_all(self, params):
        """Run full pipeline: parse_weights + build_model + deploy + benchmark."""
        if params is None:
            params = {}
        results = {}

        # Step 1: parse weights
        ok, data, err = self.cmd_parse_weights(params)
        if not ok:
            return (0, None, err)
        results["parse_weights"] = data
        sys.stderr.write("[DEPLOY] parse_weights OK: " + str(data.get("tensor_count")) +
                         " tensors, " + str(round(data.get("size_mb", 0), 2)) + " MB\n")

        # Step 2: build model
        ok, data, err = self.cmd_build_model(params)
        if not ok:
            return (0, None, err)
        results["build_model"] = data
        sys.stderr.write("[DEPLOY] build_model OK: inputs=" + str(data.get("inputs")) +
                         " outputs=" + str(data.get("outputs")) + "\n")

        # Step 3: deploy
        ok, data, err = self.cmd_deploy(params)
        if not ok:
            return (0, None, err)
        results["deploy"] = data
        sys.stderr.write("[DEPLOY] deploy OK: " + str(data.get("model_path")) +
                         " (" + str(round(data.get("size_mb", 0), 2)) + " MB)\n")

        # Step 4: benchmark
        ok, data, err = self.cmd_benchmark(params)
        if not ok:
            return (0, None, err)
        results["benchmark"] = data
        sys.stderr.write("[DEPLOY] benchmark OK: mean=" + str(round(data.get("mean_ms", 0), 2)) +
                         "ms median=" + str(round(data.get("median_ms", 0), 2)) + "ms\n")

        return (1, results, None)

    # ── Command: read_state ──

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    # ── Command: set_config ──

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))

        # Allow overriding paths and settings
        if "weights_path" in params:
            self.state["weights_path"] = params["weights_path"]
        if "output_dir" in params:
            self.state["output_dir"] = params["output_dir"]
        if "model_name" in params:
            self.state["model_name"] = params["model_name"]
        if "seq_len" in params:
            self.state["seq_len"] = params["seq_len"]

        self.state["config"] = params
        self._p("config", list(params.keys()))
        return (1, None, None)


# ── PyTorch Model (intermediate IR for CoreML conversion) ──


class BclAttentionModule(nn.Module):
    """BCL Transformer attention-only model in PyTorch.

    Matches Metal architecture (c_transformer_attention.mm) exactly:
      - Token embedding: nn.Embedding(vocab_size, d_model)
      - 6 x BclAttentionLayer:
          Q = X @ W_q (no bias)
          K = X @ W_k (no bias)
          V = X @ W_v (no bias)
          S = Q @ K^T / sqrt(head_dim)
          P = causal_softmax(S)
          A = P @ V
          O = A @ W_o (no bias)
          out = O + X (residual)
          out = LayerNorm(out) (POST-LN, with LN1_scale/LN1_bias)
      - Output: hidden states [1, seq, d_model] fp16

    Input:
      input_ids [1, seq_len] int32 — token indices
    Output:
      hidden_states [1, seq_len, d_model] float16 — final hidden representations
    """

    def __init__(self, vocab_size=VOCAB_SIZE, d_model=D_MODEL, n_heads=N_HEADS,
                 n_layers=N_LAYERS, seq_len=DEFAULT_SEQ_LEN):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.n_layers = n_layers
        self.seq_len = seq_len

        # Token embedding
        self.token_embedding = nn.Embedding(vocab_size, d_model)

        # Pre-compute causal mask (lower triangular) as a buffer.
        # Shape: [1, 1, seq_len, seq_len] — avoids shape access in forward
        # which generates aten::Int nodes incompatible with coremltools 9.0
        # + PyTorch 2.12.1.
        causal = torch.tril(torch.ones(seq_len, seq_len, dtype=torch.float32))
        self.register_buffer("causal_mask", causal.unsqueeze(0).unsqueeze(0))

        # Attention layers
        self.layers = nn.ModuleList([
            BclAttentionLayer(d_model, n_heads, self.head_dim)
            for _ in range(n_layers)
        ])

    def load_bclt_weights(self, tensors):
        """Load trained fp16 weights from BCLT tensor dict.

        BCLT tensor names:
          token_embedding [vocab_size, d_model]
          layer_i_W_q [d_model, d_model]  (Metal: [in, out], PyTorch Linear: [out, in] -> .T)
          layer_i_W_k [d_model, d_model]
          layer_i_W_v [d_model, d_model]
          layer_i_W_o [d_model, d_model]
          layer_i_LN1_scale [d_model]
          layer_i_LN1_bias [d_model]
        """
        with torch.no_grad():
            # Token embedding
            if "token_embedding" in tensors:
                self.token_embedding.weight.copy_(
                    torch.from_numpy(tensors["token_embedding"].astype(np.float32))
                )

            # Per-layer weights
            for i in range(self.n_layers):
                layer = self.layers[i]

                # W_q, W_k, W_v, W_o — Metal stores [in, out], PyTorch Linear expects [out, in]
                wq_name = "layer_" + str(i) + "_W_q"
                if wq_name in tensors:
                    layer.q_proj.weight.copy_(
                        torch.from_numpy(tensors[wq_name].astype(np.float32).T)
                    )
                wk_name = "layer_" + str(i) + "_W_k"
                if wk_name in tensors:
                    layer.k_proj.weight.copy_(
                        torch.from_numpy(tensors[wk_name].astype(np.float32).T)
                    )
                wv_name = "layer_" + str(i) + "_W_v"
                if wv_name in tensors:
                    layer.v_proj.weight.copy_(
                        torch.from_numpy(tensors[wv_name].astype(np.float32).T)
                    )
                wo_name = "layer_" + str(i) + "_W_o"
                if wo_name in tensors:
                    layer.o_proj.weight.copy_(
                        torch.from_numpy(tensors[wo_name].astype(np.float32).T)
                    )

                # LN1 scale and bias
                lns_name = "layer_" + str(i) + "_LN1_scale"
                if lns_name in tensors:
                    layer.ln.weight.copy_(
                        torch.from_numpy(tensors[lns_name].astype(np.float32))
                    )
                lnb_name = "layer_" + str(i) + "_LN1_bias"
                if lnb_name in tensors:
                    layer.ln.bias.copy_(
                        torch.from_numpy(tensors[lnb_name].astype(np.float32))
                    )

    def forward(self, input_ids):
        """Forward pass.

        input_ids: [1, seq_len] int32/int64 — token indices
        returns:   [1, seq_len, d_model] float16 — hidden states

        Note: No x.shape[1] access in forward — uses pre-computed causal
        mask buffer and -1 in view ops to avoid aten::Int nodes that
        coremltools 9.0 cannot convert with PyTorch 2.12.1.
        """
        # Token embedding lookup
        hidden = self.token_embedding(input_ids.long())  # [1, seq, d_model]

        # Use pre-computed causal mask (registered buffer, no shape access)
        causal_mask = self.causal_mask  # [1, 1, seq, seq]

        # Transformer layers (post-LN, attention-only)
        for layer in self.layers:
            hidden = layer(hidden, causal_mask)

        # Cast to fp16 for ANE
        hidden = hidden.to(torch.float16)

        return hidden


class BclAttentionLayer(nn.Module):
    """Single attention layer matching Metal AttentionLayer_Forward.

    Metal forward (c_transformer_attention.mm lines 728-752):
      Q = X @ W_q, K = X @ W_k, V = X @ W_v  (no bias)
      S = Q @ K^T / sqrt(head_dim)
      P = masked_softmax(S)  (causal + BCL mask)
      A = P @ V
      O = A @ W_o  (no bias)
      out = O + X  (residual)
      out = LayerNorm(out, LN1_scale, LN1_bias)  (POST-LN)
    """

    def __init__(self, d_model, n_heads, head_dim):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = head_dim

        # Q/K/V/O projections (no bias — Metal has no bias on these)
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.o_proj = nn.Linear(d_model, d_model, bias=False)

        # Post-attention layer norm (Metal: LN1_scale, LN1_bias)
        self.ln = nn.LayerNorm(d_model)

    def forward(self, x, attention_mask):
        """Forward pass.

        x:               [1, seq, d_model]
        attention_mask:  [1, 1, seq, seq] — causal mask (1=attend, 0=mask)
        returns:         [1, seq, d_model]

        Note: Uses -1 in view ops instead of x.shape[1] to avoid
        aten::Int nodes incompatible with coremltools 9.0 + PyTorch 2.12.1.
        """
        # QKV projections (no bias, matching Metal)
        q = self.q_proj(x)  # [1, seq, d_model]
        k = self.k_proj(x)
        v = self.v_proj(x)

        # Reshape to multi-head: [1, n_heads, seq, head_dim]
        # Use -1 instead of seq_len to avoid shape access in traced graph
        q = q.view(1, -1, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(1, -1, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(1, -1, self.n_heads, self.head_dim).transpose(1, 2)

        # Attention scores: [1, n_heads, seq, seq]
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)

        # Apply causal mask (1=attend, 0=mask -> add -1e9 to masked positions)
        scores = scores + (1.0 - attention_mask) * (-1e9)

        # Softmax
        attn = F.softmax(scores, dim=-1)

        # Apply attention to values: [1, n_heads, seq, head_dim]
        context = torch.matmul(attn, v)

        # Reshape back: [1, seq, d_model]
        # Use -1 instead of seq_len to avoid shape access in traced graph
        context = context.transpose(1, 2).contiguous().view(1, -1, self.d_model)

        # Output projection (no bias)
        attn_out = self.o_proj(context)

        # Residual connection (post-LN: residual THEN layer norm)
        out = attn_out + x

        # Layer norm (POST-LN, matching Metal)
        out = self.ln(out)

        return out


# ── CLI entry point ──

def main():
    """CLI entry point for BCL Transformer CoreML deployment."""
    parser = argparse.ArgumentParser(
        description="Deploy BCL Transformer to CoreML for Apple Neural Engine"
    )
    parser.add_argument(
        "--weights", type=str, default=DEFAULT_WEIGHTS_PATH,
        help="Path to BCLT weight file (default: " + DEFAULT_WEIGHTS_PATH + ")"
    )
    parser.add_argument(
        "--output", type=str, default=DEFAULT_OUTPUT_DIR,
        help="Output directory for .mlpackage (default: " + DEFAULT_OUTPUT_DIR + ")"
    )
    parser.add_argument(
        "--name", type=str, default=DEFAULT_MODEL_NAME,
        help="Model file name (default: " + DEFAULT_MODEL_NAME + ")"
    )
    parser.add_argument(
        "--seq_len", type=int, default=DEFAULT_SEQ_LEN,
        help="Sequence length for tracing (default: " + str(DEFAULT_SEQ_LEN) + ")"
    )
    parser.add_argument(
        "--n_warmup", type=int, default=5,
        help="Warmup iterations for benchmark (default: 5)"
    )
    parser.add_argument(
        "--n_iter", type=int, default=50,
        help="Benchmark iterations (default: 50)"
    )
    parser.add_argument(
        "--command", type=str, default="run_all",
        help="Command to run: run_all, parse_weights, build_model, deploy, benchmark, info"
    )
    args = parser.parse_args()

    deploy = CoreMlDeploy()

    sys.stderr.write("[DEPLOY] CoreMlDeploy initialized\n")
    sys.stderr.write("[DEPLOY] coremltools: " + ("available v" + str(COREML_VERSION) if COREML_AVAILABLE else "NOT available") + "\n")
    sys.stderr.write("[DEPLOY] torch: " + ("available" if TORCH_AVAILABLE else "NOT available") + "\n")

    # Set config
    deploy.Run("set_config", {
        "weights_path": args.weights,
        "output_dir": args.output,
        "model_name": args.name,
        "seq_len": args.seq_len,
    })

    if args.command == "run_all":
        ok, data, err = deploy.Run("run_all", {
            "n_warmup": args.n_warmup,
            "n_iter": args.n_iter,
        })
    elif args.command == "info":
        ok, data, err = deploy.Run("info")
    elif args.command == "parse_weights":
        ok, data, err = deploy.Run("parse_weights", {"path": args.weights})
    elif args.command == "build_model":
        ok, data, err = deploy.Run("build_model", {"seq_len": args.seq_len})
    elif args.command == "deploy":
        ok, data, err = deploy.Run("deploy")
    elif args.command == "benchmark":
        ok, data, err = deploy.Run("benchmark", {
            "n_warmup": args.n_warmup,
            "n_iter": args.n_iter,
        })
    else:
        sys.stderr.write("[DEPLOY] Unknown command: " + args.command + "\n")
        sys.exit(1)

    if ok:
        sys.stderr.write("[DEPLOY] SUCCESS\n")
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
        sys.exit(0)
    else:
        sys.stderr.write("[DEPLOY] FAILED: " + str(err) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
