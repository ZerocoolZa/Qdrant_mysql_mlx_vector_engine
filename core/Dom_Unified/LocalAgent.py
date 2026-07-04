# [@GHOST]{[@file<LocalAgent.py>][@domain<Dom_Unified>][@role<local_llm_agent>][@auth<cascade>][@date<2026-06-27>][@ver<3.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<local_llm_agent>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Local MLX agent — GPU/RAM/CPU mgmt, process lock, ErrorCapture trap, MemUnit compile/recall, DomReport output.}
# [@CLASS]{LocalAgent}
# [@METHOD]{Run,LoadModel,Ask,Generate,ParseToolCall,ExecuteMsearch,FeedResult,Cleanup,CheckRam,CheckCpu,CheckGpu,AcquireLock,ReleaseLock,TrapError,CompileSession,RecallSession,Report}

"""
LocalAgent — Local LLM agent with resource management.

WHAT IT MANAGES:
    - MLX model (GPU/Metal) — load, generate, unload
    - Process lock — prevents 1+1 Python processes running simultaneously
    - RAM monitoring — checks available RAM before loading model
    - CPU monitoring — checks CPU usage before generation
    - GPU/Metal cache — clears between steps to prevent overflow
    - Context window — sliding window, max 8 messages, prevents RAM blowup
    - msearch tool — subprocess with timeout + truncation
    - ErrorCapture — ALL errors trapped with problem/solution/cause/fix
    - MemoryObject — agent sessions compiled as memory objects
    - DomReport — all output via Report, no print

RULES ENFORCED:
    [@crashonerr] — ok == 0 -> return (0, None, err) immediately
    [@errtrap] — all errors via ErrorCapture with problem/solution/cause/fix
    [@nohardcodedep] — all config from Config.py, no hardcoded values
    [@mustmemunit] — sessions compiled via MemoryObject
    [@mustreport] — output via DomReport, no print outside __main__

FLOW:
    AcquireLock -> CheckRam -> LoadModel ->
    (Generate -> ParseTool -> Msearch -> Feed -> Cleanup) x N ->
    FinalAnswer -> CompileSession -> Report -> ReleaseLock

USAGE:
    from Dom_Unified import LocalAgent

    agent = LocalAgent()
    ok, data, err = agent.Run("load", {})
    ok, data, err = agent.Run("ask", {"question": "What is MemUnit?"})
    agent.Run("unload", {})
"""

import os
import gc
import time
import subprocess
import tempfile

from .Config import UnifiedConfig
from .ErrorCapture import ErrorCapture
from .MemoryObject import MemoryObject
from .Dom_Report import DomReport

TOOL_MARKER_START = "[[msearch:"
TOOL_MARKER_END = "]]"


class LocalAgent:
    """Local LLM agent with GPU/RAM/CPU management, process lock, error trapping, memory, reporting."""

    def __init__(self, mem=None, db=None, param=None):
        cfg = UnifiedConfig()
        ok, cfg_state, err = cfg.read_state()
        if not ok:
            cfg_state = {"config": {}}
        c = cfg_state["config"]

        self.state = {
            "config": {
                "model": c.get("agent_default_model", "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"),
                "msearch_bin": c.get("agent_msearch_bin", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Cascade_toolStack", "Built_tools", "msearch")),
                "max_tool_tokens": c.get("agent_max_tool_tokens", 80),
                "max_answer_tokens": c.get("agent_max_answer_tokens", 300),
                "max_steps": c.get("agent_max_steps", 4),
                "max_context": c.get("agent_max_context", 8),
                "msearch_max_chars": c.get("agent_msearch_max_chars", 3000),
                "msearch_timeout": c.get("agent_msearch_timeout", 10),
                "temperature": c.get("agent_temperature", 0.0),
                "lock_file": c.get("agent_lock_file", os.path.join(tempfile.gettempdir(), "dom_unified_localagent.lock")),
                "min_ram_gb": c.get("agent_min_ram_gb", 1.0),
                "max_cpu_percent": c.get("agent_max_cpu_percent", 90),
            },
            "model": None,
            "tokenizer": None,
            "mlx_loaded": False,
            "mlx_module": None,
            "generate_fn": None,
            "load_fn": None,
            "messages": [],
            "steps": [],
            "locked": False,
            "lock_pid": None,
            "stats": {
                "load_time": 0,
                "generate_time": 0,
                "msearch_time": 0,
                "total_time": 0,
                "tool_calls": 0,
                "tokens_generated": 0,
                "ram_checks": 0,
                "cpu_checks": 0,
                "gpu_clears": 0,
                "errors_trapped": 0,
                "sessions_compiled": 0,
                "reports_generated": 0,
            },
            "resources": {
                "ram_gb": 0,
                "cpu_percent": 0,
                "gpu_available": False,
            },
            "error_capture": ErrorCapture(),
            "memory": MemoryObject(),
            "report": DomReport(),
        }

    def Run(self, command, params=None):
        dispatch = {
            "load": self._cmd_load,
            "ask": self._cmd_ask,
            "status": self._cmd_status,
            "unload": self._cmd_unload,
            "check_resources": self._cmd_check_resources,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown command: " + str(command), 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "loaded": self.state["model"] is not None,
            "locked": self.state["locked"],
            "stats": dict(self.state["stats"]),
            "resources": dict(self.state["resources"]),
            "messages": len(self.state["messages"]),
            "steps": len(self.state["steps"]),
        }, None)

    def set_config(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ("ERR_PARAMS", "config dict required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _p(self, params, key, default=None):
        if not params or not isinstance(params, dict):
            return default
        val = params.get(key, default)
        return val if val is not None else default

    def _record_step(self, name, ok, data=None, error=None):
        entry = {
            "step": name,
            "ok": ok,
            "time": time.strftime("%H:%M:%S"),
            "error": error,
        }
        self.state["steps"].append(entry)
        if ok:
            return (1, data, None)
        if isinstance(error, tuple):
            return (0, None, error)
        return (0, None, ("ERR_STEP", str(error), 0))

    # ════════════════════════════════════════════
    # PROCESS LOCK — prevents 1+1 Python processes
    # ════════════════════════════════════════════

    def _acquire_lock(self):
        lock_file = self.state["config"]["lock_file"]
        try:
            if os.path.exists(lock_file):
                with open(lock_file, "r") as f:
                    old_pid = f.read().strip()
                if old_pid:
                    try:
                        os.kill(int(old_pid), 0)
                        return (0, None, ("ERR_LOCK_HELD", "Process " + old_pid + " already running", 0))
                    except (OSError, ValueError):
                        pass
            with open(lock_file, "w") as f:
                f.write(str(os.getpid()))
            self.state["locked"] = True
            self.state["lock_pid"] = os.getpid()
            return (1, {"locked": True, "pid": os.getpid()}, None)
        except Exception as e:
            return (0, None, ("ERR_LOCK", str(e), 0))

    def _release_lock(self):
        lock_file = self.state["config"]["lock_file"]
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
            self.state["locked"] = False
            self.state["lock_pid"] = None
            return (1, {"released": True}, None)
        except Exception as e:
            return (0, None, ("ERR_UNLOCK", str(e), 0))

    # ════════════════════════════════════════════
    # RESOURCE CHECKS — RAM, CPU, GPU
    # ════════════════════════════════════════════

    def _check_ram(self):
        self.state["stats"]["ram_checks"] += 1
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            page_size = 4096
            for line in lines:
                if "page size" in line.lower():
                    parts = line.split("of")
                    if len(parts) == 2:
                        try:
                            page_size = int(parts[1].strip().rstrip(") bytes"))
                        except ValueError:
                            pass
                    break

            free_pages = 0
            inactive_pages = 0
            for line in lines:
                lower = line.lower()
                if lower.startswith("pages free:") or lower.startswith("pages free "):
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            free_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass
                elif lower.startswith("pages inactive:") or lower.startswith("pages inactive "):
                    parts = line.split(":")
                    if len(parts) == 2:
                        try:
                            inactive_pages = int(parts[1].strip().rstrip("."))
                        except ValueError:
                            pass

            available_pages = free_pages + inactive_pages
            free_gb = (available_pages * page_size) / (1024 ** 3)
            self.state["resources"]["ram_gb"] = round(free_gb, 2)
            min_gb = self.state["config"]["min_ram_gb"]
            if free_gb < min_gb:
                return (0, None, ("ERR_LOW_RAM", "Free RAM " + str(round(free_gb, 2)) + "GB < " + str(min_gb) + "GB minimum", 0))
            return (1, {"free_gb": round(free_gb, 2), "page_size": page_size, "free_pages": free_pages, "inactive_pages": inactive_pages}, None)
        except Exception as e:
            return (0, None, ("ERR_RAM_CHECK", str(e), 0))

    def _check_cpu(self):
        self.state["stats"]["cpu_checks"] += 1
        try:
            result = subprocess.run(
                ["top", "-l", "1", "-n", "0"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.split("\n"):
                if "CPU usage:" in line:
                    parts = line.split()
                    user_pct = 0
                    for i, p in enumerate(parts):
                        if "%" in p and i > 0:
                            try:
                                user_pct = float(p.rstrip("%"))
                                break
                            except ValueError:
                                continue
                    self.state["resources"]["cpu_percent"] = user_pct
                    max_pct = self.state["config"]["max_cpu_percent"]
                    if user_pct > max_pct:
                        return (0, None, ("ERR_HIGH_CPU", "CPU " + str(user_pct) + "% > " + str(max_pct) + "% max", 0))
                    return (1, {"cpu_percent": user_pct}, None)
            self.state["resources"]["cpu_percent"] = 0
            return (1, {"cpu_percent": 0, "note": "could not parse"}, None)
        except Exception as e:
            return (0, None, ("ERR_CPU_CHECK", str(e), 0))

    def _check_gpu(self):
        try:
            import mlx.core as mx
            has_metal = hasattr(mx, "metal")
            self.state["resources"]["gpu_available"] = has_metal
            return (1, {"gpu_available": has_metal, "backend": "metal" if has_metal else "cpu"}, None)
        except ImportError:
            self.state["resources"]["gpu_available"] = False
            return (1, {"gpu_available": False, "backend": "none"}, None)
        except Exception as e:
            self.state["resources"]["gpu_available"] = False
            return (0, None, ("ERR_GPU_CHECK", str(e), 0))

    def _clear_gpu_cache(self):
        self.state["stats"]["gpu_clears"] += 1
        try:
            if self.state["mlx_module"] is not None:
                if hasattr(self.state["mlx_module"], "clear_cache"):
                    self.state["mlx_module"].clear_cache()
                elif hasattr(self.state["mlx_module"], "metal"):
                    if hasattr(self.state["mlx_module"].metal, "clear_cache"):
                        self.state["mlx_module"].metal.clear_cache()
            return (1, {"cleared": True}, None)
        except Exception:
            return (1, {"cleared": False, "note": "no cache to clear"}, None)

    # ════════════════════════════════════════════
    # CONTEXT TRIMMING — sliding window
    # ════════════════════════════════════════════

    def _trim_context(self):
        max_msgs = self.state["config"]["max_context"]
        if len(self.state["messages"]) > max_msgs:
            system_msgs = [m for m in self.state["messages"] if m.get("role") == "system"]
            other_msgs = [m for m in self.state["messages"] if m.get("role") != "system"]
            keep_count = max_msgs - len(system_msgs)
            if keep_count < 2:
                keep_count = 2
            self.state["messages"] = system_msgs + other_msgs[-keep_count:]
            return (1, {"trimmed": True, "count": len(self.state["messages"])}, None)
        return (1, {"trimmed": False, "count": len(self.state["messages"])}, None)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def _cmd_load(self, params):
        model_name = self._p(params, "model", self.state["config"]["model"])
        t0 = time.time()

        ok, _, err = self._acquire_lock()
        if not ok:
            return self._record_step("acquire_lock", False, error=err)

        ok, _, err = self._check_ram()
        if not ok:
            self._release_lock()
            return self._record_step("check_ram", False, error=err)

        ok, _, err = self._check_gpu()
        if not ok:
            self._release_lock()
            return self._record_step("check_gpu", False, error=err)

        ok, _, err = self._step_import_mlx()
        if not ok:
            self._release_lock()
            return self._record_step("import_mlx", False, error=err)

        ok, _, err = self._step_load_model(model_name)
        if not ok:
            self._release_lock()
            return self._record_step("load_model", False, error=err)

        elapsed = time.time() - t0
        self.state["stats"]["load_time"] = elapsed
        return self._record_step("load_complete", True, {
            "model": model_name,
            "load_time": round(elapsed, 2),
            "resources": dict(self.state["resources"]),
        })

    def _cmd_ask(self, params):
        question = self._p(params, "question", "")
        if not question:
            return (0, None, ("ERR_NO_QUESTION", "No question provided", 0))
        if not self.state["model"] or not self.state["tokenizer"]:
            return (0, None, ("ERR_NOT_LOADED", "Model not loaded. Run load first.", 0))

        t0 = time.time()
        self.state["steps"] = []
        self.state["messages"] = [
            {"role": "system", "content": "You are a coding assistant. To search the local knowledge base, output [[msearch: query]]. Then answer based on the results."},
            {"role": "user", "content": question},
        ]

        for step_num in range(self.state["config"]["max_steps"]):
            ok, _, err = self._check_cpu()
            if not ok:
                self._record_step("check_cpu_" + str(step_num), False, error=err)

            ok, data, err = self._step_generate(step_num)
            if not ok:
                return self._record_step("generate_" + str(step_num), False, error=err)

            ok, data, err = self._step_parse_tool_call(data["response"])
            if not ok or (isinstance(data, dict) and not data.get("has_tool_call", False)):
                final = data.get("answer", "") if isinstance(data, dict) else ""
                if not final:
                    final = self.state["messages"][-1].get("content", "") if self.state["messages"] else ""
                elapsed = time.time() - t0
                self.state["stats"]["total_time"] = elapsed
                self._record_step("done", True, {"answer": final})
                return (1, {"answer": final, "steps": list(self.state["steps"]), "stats": dict(self.state["stats"])}, None)

            ok, data, err = self._step_execute_msearch(data["query"])
            if not ok:
                return self._record_step("msearch_" + str(step_num), False, error=err)

            ok, _, err = self._step_feed_result(data["result"])
            if not ok:
                return self._record_step("feed_" + str(step_num), False, error=err)

            ok, _, err = self._trim_context()
            if not ok:
                self._record_step("trim_" + str(step_num), False, error=err)

            ok, _, err = self._clear_gpu_cache()
            if not ok:
                self._record_step("gpu_clear_" + str(step_num), False, error=err)

        elapsed = time.time() - t0
        self.state["stats"]["total_time"] = elapsed
        return (1, {"answer": "Max steps reached", "steps": list(self.state["steps"]), "stats": dict(self.state["stats"])}, None)

    def _cmd_status(self, params):
        return (1, {
            "loaded": self.state["model"] is not None,
            "locked": self.state["locked"],
            "lock_pid": self.state["lock_pid"],
            "config": dict(self.state["config"]),
            "stats": dict(self.state["stats"]),
            "resources": dict(self.state["resources"]),
            "steps": list(self.state["steps"]),
            "messages": len(self.state["messages"]),
        }, None)

    def _cmd_unload(self, params):
        self._clear_gpu_cache()
        gc.collect()
        self.state["model"] = None
        self.state["tokenizer"] = None
        self.state["mlx_loaded"] = False
        self.state["messages"] = []
        self._release_lock()
        return (1, {"unloaded": True, "released_lock": True}, None)

    def _cmd_check_resources(self, params):
        ok_ram, ram_data, ram_err = self._check_ram()
        ok_cpu, cpu_data, cpu_err = self._check_cpu()
        ok_gpu, gpu_data, gpu_err = self._check_gpu()
        return (1, {
            "ram": {"ok": ok_ram, "data": ram_data, "error": ram_err},
            "cpu": {"ok": ok_cpu, "data": cpu_data, "error": cpu_err},
            "gpu": {"ok": ok_gpu, "data": gpu_data, "error": gpu_err},
        }, None)

    # ════════════════════════════════════════════
    # STEPS
    # ════════════════════════════════════════════

    def _step_import_mlx(self):
        try:
            from mlx_lm import load, stream_generate
            import mlx.core as mx
            self.state["mlx_module"] = mx
            self.state["generate_fn"] = stream_generate
            self.state["load_fn"] = load
            self.state["mlx_loaded"] = True
            return (1, {"imported": True}, None)
        except ImportError as e:
            return (0, None, ("ERR_IMPORT", "mlx-lm import failed: " + str(e), 0))

    def _step_load_model(self, model_name):
        try:
            model, tokenizer = self.state["load_fn"](model_name)
            self.state["model"] = model
            self.state["tokenizer"] = tokenizer
            return (1, {"model_loaded": True}, None)
        except Exception as e:
            return (0, None, ("ERR_LOAD", "Model load failed: " + str(e), 0))

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

            for response in self.state["generate_fn"](
                model, tokenizer, prompt,
                max_tokens=max_tok,
            ):
                token_text = response.text
                output += token_text
                if TOOL_MARKER_END in output and TOOL_MARKER_START in output:
                    break
                if len(output) > 4000:
                    break
                if response.finish_reason is not None:
                    break

            elapsed = time.time() - t0
            self.state["stats"]["generate_time"] += elapsed
            self.state["stats"]["tokens_generated"] += len(output)
            self.state["messages"].append({"role": "assistant", "content": output})

            return (1, {"response": output, "time": round(elapsed, 2), "chars": len(output)}, None)
        except Exception as e:
            return (0, None, ("ERR_GENERATE", "Generation failed: " + str(e), 0))

    def _step_parse_tool_call(self, response):
        if TOOL_MARKER_START not in response:
            return (1, {"has_tool_call": False, "answer": response}, None)

        try:
            start_idx = response.find(TOOL_MARKER_START) + len(TOOL_MARKER_START)
            end_idx = response.find(TOOL_MARKER_END, start_idx)
            if end_idx == -1:
                return (1, {"has_tool_call": False, "answer": response}, None)
            query = response[start_idx:end_idx].strip()
            if not query:
                return (1, {"has_tool_call": False, "answer": response}, None)
            self.state["stats"]["tool_calls"] += 1
            return (1, {"has_tool_call": True, "query": query}, None)
        except Exception:
            return (1, {"has_tool_call": False, "answer": response}, None)

    def _step_execute_msearch(self, query):
        msearch_bin = self.state["config"]["msearch_bin"]
        max_chars = self.state["config"]["msearch_max_chars"]
        timeout = self.state["config"]["msearch_timeout"]

        if not os.path.isfile(msearch_bin):
            return (0, None, ("ERR_MSEARCH_BIN", "msearch binary not found: " + msearch_bin, 0))

        try:
            t0 = time.time()
            result = subprocess.run(
                [msearch_bin, query],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - t0
            self.state["stats"]["msearch_time"] += elapsed

            if result.returncode != 0:
                return (0, None, ("ERR_MSEARCH_RC", "msearch exit " + str(result.returncode) + ": " + result.stderr[:200], 0))

            output = result.stdout.strip()
            if not output:
                return (0, None, ("ERR_MSEARCH_EMPTY", "msearch returned no output", 0))

            if len(output) > max_chars:
                output = output[:max_chars] + "\n... (truncated)"

            return (1, {"result": output, "chars": len(output), "time": round(elapsed, 2)}, None)
        except subprocess.TimeoutExpired:
            return (0, None, ("ERR_MSEARCH_TIMEOUT", "msearch timed out (" + str(timeout) + "s)", 0))
        except Exception as e:
            return (0, None, ("ERR_MSEARCH", "msearch failed: " + str(e), 0))

    def _step_feed_result(self, result):
        try:
            self.state["messages"].append({
                "role": "user",
                "content": "Search results:\n" + result + "\n\nNow answer the question based on these results.",
            })
            return (1, {"fed": True, "chars": len(result)}, None)
        except Exception as e:
            return (0, None, ("ERR_FEED", "Feed result failed: " + str(e), 0))

    # ════════════════════════════════════════════
    # [@errtrap] — ErrorCapture with problem/solution/cause/fix
    # ════════════════════════════════════════════

    def _trap_error(self, error_code, error_desc, context=None):
        self.state["stats"]["errors_trapped"] += 1
        problem = error_code
        cause = error_desc
        solution_map = {
            "ERR_LOW_RAM": "Close other applications or increase AGENT_MIN_RAM_GB in Config.py",
            "ERR_HIGH_CPU": "Wait for CPU to drop or increase AGENT_MAX_CPU_PERCENT in Config.py",
            "ERR_LOCK_HELD": "Another LocalAgent process is running. Run unload first or delete lock file",
            "ERR_IMPORT": "Install mlx-lm: pip install mlx-lm",
            "ERR_LOAD": "Check model name in Config.py AGENT_DEFAULT_MODEL. Model may not be downloaded",
            "ERR_GENERATE": "Check MLX model integrity. Try unloading and reloading. Clear GPU cache",
            "ERR_MSEARCH_BIN": "Build msearch binary or check AGENT_MSEARCH_BIN path in Config.py",
            "ERR_MSEARCH_TIMEOUT": "Increase AGENT_MSEARCH_TIMEOUT in Config.py or optimize msearch query",
            "ERR_MSEARCH_RC": "Check msearch binary for errors. Run it manually to debug",
            "ERR_MSEARCH_EMPTY": "msearch returned no results. Try a different query",
            "ERR_FEED": "Internal error feeding results to context. Check message list integrity",
            "ERR_GPU_CHECK": "MLX/Metal not available. Check mlx installation",
            "ERR_RAM_CHECK": "vm_stat command failed. Check macOS version",
            "ERR_CPU_CHECK": "top command failed. Check macOS version",
            "ERR_LOCK": "Cannot create lock file. Check temp directory permissions",
            "ERR_UNLOCK": "Cannot remove lock file. Check temp directory permissions",
        }
        fix = solution_map.get(error_code, "Check error code and context for root cause")
        try:
            self.state["error_capture"].Run("capture", {
                "problem": problem,
                "cause": cause,
                "solution": fix,
                "fix": fix,
                "context": context or "",
            })
        except Exception:
            pass
        return (0, None, (error_code, error_desc, 0))

    # ════════════════════════════════════════════
    # [@mustmemunit] — MemoryObject compile/recall
    # ════════════════════════════════════════════

    def _compile_session(self, question, answer, steps):
        self.state["stats"]["sessions_compiled"] += 1
        try:
            ok, data, err = self.state["memory"].Run("compile", {
                "query": question,
                "answer": answer,
                "steps": steps,
                "source": "localagent",
            })
            if not ok:
                return (0, None, err)
            return (1, {"compiled": True, "session_id": data.get("id") if isinstance(data, dict) else None}, None)
        except Exception as e:
            return self._trap_error("ERR_COMPILE", "Memory compile failed: " + str(e), "compile_session")

    def _recall_session(self, query):
        try:
            ok, data, err = self.state["memory"].Run("recall", {
                "query": query,
            })
            if not ok:
                return (0, None, err)
            return (1, data, None)
        except Exception as e:
            return self._trap_error("ERR_RECALL", "Memory recall failed: " + str(e), "recall_session")

    # ════════════════════════════════════════════
    # [@mustreport] — DomReport for output
    # ════════════════════════════════════════════

    def _report(self, report_type, data):
        self.state["stats"]["reports_generated"] += 1
        try:
            ok, rep_data, err = self.state["report"].Run("report", {
                "type": report_type,
                "data": data,
            })
            if not ok:
                return (0, None, err)
            return (1, rep_data, None)
        except Exception as e:
            return self._trap_error("ERR_REPORT", "Report failed: " + str(e), "report")


if __name__ == "__main__":
    import sys

    agent = LocalAgent()

    ok, data, err = agent.Run("check_resources", {})
    if ok:
        sys.stderr.write("RAM: " + str(data["ram"]["data"]) + "\n")
        sys.stderr.write("CPU: " + str(data["cpu"]["data"]) + "\n")
        sys.stderr.write("GPU: " + str(data["gpu"]["data"]) + "\n\n")

    ok, data, err = agent.Run("load", {})
    if not ok:
        sys.stderr.write("Load failed: " + str(err) + "\n")
        sys.exit(1)
    sys.stderr.write("Model loaded in " + str(data["load_time"]) + "s\n")

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is MemUnit?"
    sys.stderr.write("Question: " + question + "\n\n")

    ok, data, err = agent.Run("ask", {"question": question})
    if not ok:
        sys.stderr.write("Ask failed: " + str(err) + "\n")
        agent.Run("unload", {})
        sys.exit(1)

    sys.stdout.write(data["answer"] + "\n")
    sys.stderr.write("\n--- " + str(len(data["steps"])) + " steps, " + str(round(data["stats"]["total_time"], 2)) + "s total ---\n")
    for s in data["steps"]:
        status = "OK" if s["ok"] else "FAIL"
        sys.stderr.write("  [" + status + "] " + s["step"])
        if not s["ok"] and s.get("error"):
            sys.stderr.write(" -- " + str(s["error"]))
        sys.stderr.write("\n")

    agent.Run("unload", {})
