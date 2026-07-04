#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_Graph/test_bnd_smol.py" date="2026-07-04" author="Devin" session_id="bnd-smol" context="Standalone test: load SmolLM-135M, run BndEngine with LLM enabled, show RAM + result. Hard 90s timeout."}
# [@VBSTYLE]{standard="VBStyle" version="1"}
# [@FILEID]{id="test_bnd_smol.py" domain="dom_graph" authority="test"}
# [@SUMMARY]{summary="Load SmolLM-135M-Instruct via mlx_lm, run BndEngine BNQ->BND->BND->closure with LLM. Print RAM and result. Hard 90s timeout so never stuck."}

import os
import sys
import signal
import time
import resource

def kill_handler(signum, frame):
    print("\n[TIMEOUT] Killed after 90s")
    sys.exit(1)

signal.signal(signal.SIGALRM, kill_handler)
signal.alarm(90)

def ram_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

print("=" * 60)
print("BND ENGINE + SmolLM-135M (LLM ENABLED)")
print("=" * 60)

print("\n[1] RAM start: {:.0f} MB".format(ram_mb()))

# Load SmolLM
print("\n[2] Loading SmolLM-135M-Instruct...")
try:
    from mlx_lm import load, generate
    model_path = "HuggingFaceTB/SmolLM-135M-Instruct"
    llm_model, llm_tokenizer = load(model_path)
    print("    Loaded. RAM: {:.0f} MB".format(ram_mb()))
except Exception as e:
    print("    FAILED:", e)
    llm_model = None

# Quick test
if llm_model:
    print("\n[3] LLM test...")
    t0 = time.time()
    resp = generate(llm_model, llm_tokenizer, prompt="Concept: graph_engine\nList 3 next steps (one per line, just the step name):\n", max_tokens=50, verbose=False)
    t1 = time.time()
    print("    {}ms: {}".format(int((t1-t0)*1000), repr(resp.strip()[:150])))

# Load BndEngine
print("\n[4] Loading BndEngine...")
import importlib.util
spec = importlib.util.spec_from_file_location("BndEngine", os.path.join(os.path.dirname(__file__), "BndEngine.py"))
bnd_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bnd_module)

# Patch LLM
if llm_model:
    def smol_generate(prompt, system="", max_tokens=60):
        try:
            from mlx_lm import generate as mlx_gen
            full = ""
            if system:
                full += system + "\n\n"
            full += prompt
            return mlx_gen(llm_model, llm_tokenizer, prompt=full, max_tokens=max_tokens, verbose=False).strip()
        except Exception:
            return ""

    bnd_module._llm_generate = smol_generate
    bnd_module._LLM_AVAILABLE = True
    bnd_module._LLM_MODEL = llm_model
    bnd_module._LLM_TOKENIZER = llm_tokenizer
    print("    LLM patched.")

# Run
print("\n[5] Running radiation with LLM...")
bnd = bnd_module.BndEngine()
bnd.Run("set_config", {"cluster_size": 6, "max_bnd_per_layer": 4, "max_nodes": 40, "max_edges": 100, "use_llm": True})

question = "How do I build a graph engine?"
print("    BNQ:", question)

bnd.Run("seed", {"bnq": question})

t0 = time.time()
ok, data, err = bnd.Run("radiate", {"max_depth": 3, "threshold": 0.20, "use_bnq_probe": False})
t1 = time.time()

print("\n" + "=" * 60)
print("RESULT ({}ms)".format(int((t1-t0)*1000)))
print("=" * 60)

if ok:
    print("BNQ:", data["seed"])
    print("Closed:", data["closed"], "|", data["closure_reason"])
    print("Layers:", data["total_layers"])
    print("BND:", data["total_bnd"], "| Traversed:", data["total_traversed"])
    print("Nodes:", data["total_nodes"], "| Edges:", data["total_edges"])
    print()
    for layer in data["layers"]:
        print("L{}: frontier={} bnd={} valid={} traversed={} top={:.4f}".format(
            layer["layer"], layer["frontier_count"], layer["bnd_count"],
            layer["valid_bnd_count"], layer["traversed_count"], layer["top_score"]))

    print()
    print("=== BND PATH (traversed) ===")
    traversed = [e for e in bnd.state["bnd_edges"] if e["traversed"]]
    traversed.sort(key=lambda e: (e["layer"], -e["score"]))
    for e in traversed:
        print("L{}: {} -> {} ({}) {:.4f}".format(
            e["layer"], e["from_node"][:35], e["to_node"][:35], e["direction_type"], e["score"]))
else:
    print("ERROR:", err)

print("\n[6] RAM end: {:.0f} MB".format(ram_mb()))
print("\nDONE.")
