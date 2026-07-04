#!/usr/bin/env python3
# [@GHOST]{[@file<LocalAgent.py>][@domain<Dom_LocalAgent>][@role<local_llm_agent>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<local_llm_agent>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Local LLM agent — mlx-lm + msearch, no server, minimal RAM, step-by-step verification}
# [@CLASS]{LocalAgent}
# [@METHOD]{Run,LoadModel,Generate,ParseToolCall,ExecuteMsearch,FeedResult,FinalAnswer,Cleanup,CheckStep}

"""
LocalAgent — Minimal RAM local LLM agent for M1 8GB.

Flow:
    LoadModel → Generate → ParseToolCall → ExecuteMsearch → FeedResult → FinalAnswer → Cleanup

Every step returns Tuple3. Every step is checked. You see exactly what fails.

Usage:
    agent = LocalAgent()
    agent.Run("load", {"model": "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"})
    result = agent.Run("ask", {"question": "What is MemUnit?"})
    # result = (1, {"answer": "...", "steps": [...]}, None) or (0, None, (code, desc, 0))
"""

import os
import gc
import json
import time
import subprocess

MSEARCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"
DEFAULT_MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
MAX_TOOL_TOKENS = 80
MAX_ANSWER_TOKENS = 300
MAX_STEPS = 4
MSEARCH_MAX_CHARS = 3000

TOOL_MARKER_START = "[[msearch:"
TOOL_MARKER_END = "]]"


class LocalAgent:
    """Local LLM agent with step-by-step verification."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "model": DEFAULT_MODEL,
                "msearch_bin": MSEARCH_BIN,
                "max_tool_tokens": MAX_TOOL_TOKENS,
                "max_answer_tokens": MAX_ANSWER_TOKENS,
                "max_steps": MAX_STEPS,
                "msearch_max_chars": MSEARCH_MAX_CHARS,
                "temperature": 0.0,
            },
            "model": None,
            "tokenizer": None,
            "messages": [],
            "steps": [],
            "stats": {
                "load_time": 0,
                "generate_time": 0,
                "msearch_time": 0,
                "total_time": 0,
                "tool_calls": 0,
                "tokens_generated": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "load": self._cmd_load,
            "ask": self._cmd_ask,
            "status": self._cmd_status,
            "unload": self._cmd_unload,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", f"Unknown command: {command}", 0))
        return handler(params or {})

    def read_state(self):
        return (1, dict(self.state), None)

    def set_config(self, values):
        for key, val in values.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    # ════════════════════════════════════════════
    # VERIFICATION
    # ════════════════════════════════════════════

    def _check_step(self, step_name, ok, data=None, error=None):
        """Record a step check. Returns Tuple3 passthrough."""
        entry = {
            "step": step_name,
            "ok": ok,
            "time": time.strftime("%H:%M:%S"),
            "error": error,
        }
        self.state["steps"].append(entry)
        if ok:
            return (1, data, None)
        else:
            code = error[0] if error and isinstance(error, tuple) else "ERR_CHECK"
            desc = error[1] if error and isinstance(error, tuple) else str(error)
            return (0, None, (code, desc, 0))

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def _cmd_load(self, params):
        """Load MLX model into memory."""
        model_name = params.get("model", self.state["config"]["model"])
        t0 = time.time()

        ok, data, err = self._step_import_mlx()
        if not ok:
            return self._check_step("import_mlx", False, error=err)

        ok, data, err = self._step_load_model(model_name)
        if not ok:
            return self._check_step("load_model", False, error=err)

        elapsed = time.time() - t0
        self.state["stats"]["load_time"] = elapsed
        self._check_step("load_complete", True, {"model": model_name, "time": elapsed})
        return (1, {"model": model_name, "load_time": elapsed, "steps": self.state["steps"]}, None)

    def _cmd_ask(self, params):
        """Ask a question. Model decides if it needs msearch."""
        question = params.get("question", "")
        if not question:
            return (0, None, ("ERR_NO_QUESTION", "No question provided", 0))

        if not self.state["model"] or not self.state["tokenizer"]:
            return (0, None, ("ERR_NOT_LOADED", "Model not loaded. Run load first.", 0))

        t0 = time.time()
        self.state["messages"] = [
            {"role": "system", "content": "You are a coding assistant. To search the local knowledge base, output [[msearch: query]]. Then answer based on the results."},
            {"role": "user", "content": question},
        ]
        self.state["steps"] = []

        for step_num in range(self.state["config"]["max_steps"]):
            ok, data, err = self._step_generate(step_num)
            if not ok:
                return self._check_step(f"generate_{step_num}", False, error=err)

            ok, data, err = self._step_parse_tool_call(data["response"])
            if not ok:
                self._check_step(f"parse_{step_num}", False, error=err)
                final = data.get("answer", "") if isinstance(data, dict) else ""
                if not final:
                    final = self.state["messages"][-1].get("content", "") if self.state["messages"] else ""
                elapsed = time.time() - t0
                self.state["stats"]["total_time"] = elapsed
                self._check_step("done", True, {"answer": final, "steps": len(self.state["steps"])})
                return (1, {"answer": final, "steps": self.state["steps"], "stats": self.state["stats"]}, None)

            ok, data, err = self._step_execute_msearch(data["query"])
            if not ok:
                return self._check_step(f"msearch_{step_num}", False, error=err)

            ok, data, err = self._step_feed_result(data["result"])
            if not ok:
                return self._check_step(f"feed_{step_num}", False, error=err)

            ok, data, err = self._step_cleanup_memory()
            if not ok:
                self._check_step(f"cleanup_{step_num}", False, error=err)

        elapsed = time.time() - t0
        self.state["stats"]["total_time"] = elapsed
        return (1, {"answer": "Max steps reached", "steps": self.state["steps"], "stats": self.state["stats"]}, None)

    def _cmd_status(self, params):
        """Return current state and stats."""
        return (1, {
            "loaded": self.state["model"] is not None,
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
            "steps": list(self.state["steps"]),
            "messages": len(self.state["messages"]),
        }, None)

    def _cmd_unload(self, params):
        """Unload model and free memory."""
        ok, data, err = self._step_cleanup_memory()
        self.state["model"] = None
        self.state["tokenizer"] = None
        self.state["messages"] = []
        if ok:
            return (1, {"unloaded": True, "steps": self.state["steps"]}, None)
        return (0, None, err)

    # ════════════════════════════════════════════
    # STEPS — each returns Tuple3, each is checked
    # ════════════════════════════════════════════

    def _step_import_mlx(self):
        try:
            from mlx_lm import load, stream_generate
            import mlx.core as mx
            self._mlx = mx
            self._generate_step = stream_generate
            self._load_fn = load
            return (1, {"imported": True}, None)
        except ImportError as e:
            return (0, None, ("ERR_IMPORT", f"mlx-lm import failed: {e}", 0))

    def _step_load_model(self, model_name):
        try:
            model, tokenizer = self._load_fn(model_name)
            self.state["model"] = model
            self.state["tokenizer"] = tokenizer
            return (1, {"model_loaded": True}, None)
        except Exception as e:
            return (0, None, ("ERR_LOAD", f"Model load failed: {e}", 0))

    def _step_generate(self, step_num):
        try:
            tokenizer = self.state["tokenizer"]
            model = self.state["model"]
            messages = self.state["messages"]

            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            output = ""
            t0 = time.time()
            max_tok = self.state["config"]["max_tool_tokens"]

            for response in self._generate_step(
                model, tokenizer, prompt,
                max_tokens=max_tok,
                temp=self.state["config"]["temperature"],
            ):
                token_text = response.text
                output += token_text
                if TOOL_MARKER_END in output and TOOL_MARKER_START in output:
                    break
                if response.finish_reason is not None:
                    break

            elapsed = time.time() - t0
            self.state["stats"]["generate_time"] += elapsed
            self.state["stats"]["tokens_generated"] += len(output)
            self.state["messages"].append({"role": "assistant", "content": output})

            return (1, {"response": output, "time": elapsed, "chars": len(output)}, None)
        except Exception as e:
            return (0, None, ("ERR_GENERATE", f"Generation failed: {e}", 0))

    def _step_parse_tool_call(self, response):
        if TOOL_MARKER_START not in response:
            return (1, {"has_tool_call": False, "answer": response}, None)

        try:
            start_idx = response.find(TOOL_MARKER_START) + len(TOOL_MARKER_START)
            end_idx = response.find(TOOL_MARKER_END, start_idx)
            if end_idx == -1:
                return (0, None, ("ERR_PARSE", "Tool marker start found but no end marker", 0))
            query = response[start_idx:end_idx].strip()
            if not query:
                return (0, None, ("ERR_PARSE", "Empty query in tool call", 0))
            self.state["stats"]["tool_calls"] += 1
            return (1, {"has_tool_call": True, "query": query}, None)
        except Exception as e:
            return (0, None, ("ERR_PARSE", f"Parse failed: {e}", 0))

    def _step_execute_msearch(self, query):
        msearch_bin = self.state["config"]["msearch_bin"]
        max_chars = self.state["config"]["msearch_max_chars"]

        if not os.path.isfile(msearch_bin):
            return (0, None, ("ERR_MSEARCH_BIN", f"msearch binary not found: {msearch_bin}", 0))

        try:
            t0 = time.time()
            result = subprocess.run(
                [msearch_bin, query],
                capture_output=True,
                text=True,
                timeout=10,
            )
            elapsed = time.time() - t0
            self.state["stats"]["msearch_time"] += elapsed

            if result.returncode != 0:
                return (0, None, ("ERR_MSEARCH_RC", f"msearch exit code {result.returncode}: {result.stderr[:200]}", 0))

            output = result.stdout.strip()
            if not output:
                return (0, None, ("ERR_MSEARCH_EMPTY", "msearch returned no output", 0))

            if len(output) > max_chars:
                output = output[:max_chars] + "\n... (truncated)"

            return (1, {"result": output, "chars": len(output), "time": elapsed}, None)
        except subprocess.TimeoutExpired:
            return (0, None, ("ERR_MSEARCH_TIMEOUT", "msearch timed out (10s)", 0))
        except Exception as e:
            return (0, None, ("ERR_MSEARCH", f"msearch failed: {e}", 0))

    def _step_feed_result(self, result):
        try:
            self.state["messages"].append({
                "role": "user",
                "content": f"Search results:\n{result}\n\nNow answer the question based on these results.",
            })
            return (1, {"fed": True, "chars": len(result)}, None)
        except Exception as e:
            return (0, None, ("ERR_FEED", f"Feed result failed: {e}", 0))

    def _step_cleanup_memory(self):
        try:
            gc.collect()
            self._mlx.metal.clear_cache()
            return (1, {"cleaned": True}, None)
        except Exception as e:
            return (0, None, ("ERR_CLEANUP", f"Cleanup failed: {e}", 0))


if __name__ == "__main__":
    import sys

    agent = LocalAgent()

    ok, data, err = agent.Run("load", {})
    if not ok:
        sys.stderr.write(f"Load failed: {err}\n")
        sys.exit(1)
    sys.stderr.write(f"Model loaded in {data['load_time']:.1f}s\n")

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is MemUnit?"
    sys.stderr.write(f"Question: {question}\n\n")

    ok, data, err = agent.Run("ask", {"question": question})
    if not ok:
        sys.stderr.write(f"Ask failed: {err}\n")
        sys.exit(1)

    sys.stdout.write(data["answer"] + "\n")
    sys.stderr.write(f"\n--- {len(data['steps'])} steps, {data['stats']['total_time']:.1f}s total ---\n")
    for s in data["steps"]:
        status = "OK" if s["ok"] else "FAIL"
        sys.stderr.write(f"  [{status}] {s['step']}")
        if not s["ok"] and s.get("error"):
            sys.stderr.write(f" — {s['error']}")
        sys.stderr.write("\n")

    agent.Run("unload", {})
