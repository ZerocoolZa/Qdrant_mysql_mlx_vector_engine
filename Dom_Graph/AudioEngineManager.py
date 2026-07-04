#!/usr/bin/env python3
# [@GHOST]{[@file<AudioEngineManager.py>][@domain<voice>][@role<audio_engine>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<audio_engine>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{AudioEngineManager — persistent AVAudioEngine lifecycle. Start, pause, resume, stop, install/remove tap. Keeps engine warm between sessions. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{AudioEngineManager}
# [@METHOD]{Run,start,pause,resume,stop,install_tap,remove_tap,is_running,get_format,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Persistent AVAudioEngine lifecycle manager with start/pause/resume/stop/tap. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded buffer_size default 4096 in __init__.>][@todos<Move hardcoded 4096 to Config.py constant>]}
"""
AudioEngineManager — Persistent AVAudioEngine lifecycle manager.

WHAT IT MANAGES:
  - AVAudioEngine instance (persistent — no cold start)
  - Input node + recording format
  - Audio tap installation/removal
  - Engine state: stopped, running, paused

WHY CLASS-BASED:
  - Persistent engine — no 200-700ms cold start per session
  - pause() not stop() — keeps resources warm
  - Centralized tap management — no leaked taps
  - State tracking — know if engine is running/paused/stopped

USAGE:
  from AudioEngineManager import AudioEngineManager

  aem = AudioEngineManager()
  ok, data, err = aem.Run("start")
  ok, data, err = aem.Run("install_tap", {"buffer_size": 4096, "callback": my_func})
  # ... listen ...
  ok, data, err = aem.Run("pause")  # keep warm during TTS
  ok, data, err = aem.Run("resume")  # instant resume
  ok, data, err = aem.Run("remove_tap")
  ok, data, err = aem.Run("stop")  # full shutdown
"""

import threading


class AudioEngineManager:
    """
    Persistent AVAudioEngine lifecycle manager.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Thread-safe via lock.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.lock = threading.Lock()
        self.state = {
            "config": {
                "buffer_size": param.get("buffer_size", 4096) if param else 4096,
            },
            "engine": None,
            "input_node": None,
            "format": None,
            "tap_installed": False,
            "tap_callback": None,
            "running": False,
            "paused": False,
            "stats": {"starts": 0, "pauses": 0, "resumes": 0, "stops": 0, "errors": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "start": self.cmd_start,
            "pause": self.cmd_pause,
            "resume": self.cmd_resume,
            "stop": self.cmd_stop,
            "install_tap": self.cmd_install_tap,
            "remove_tap": self.cmd_remove_tap,
            "is_running": self.cmd_is_running,
            "get_format": self.cmd_get_format,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        with self.lock:
            return (1, dict(self.state), None)

    def set_config(self, params):
        with self.lock:
            for key, val in params.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
            return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # INTERNAL — ensure engine exists
    # ════════════════════════════════════════════

    def ensure_engine(self):
        """Create AVAudioEngine if not exists. Must be called from the audio thread."""
        with self.lock:
            if self.state["engine"] is not None:
                return True
        try:
            from AVFoundation import AVAudioEngine
            engine = AVAudioEngine.alloc().init()
            input_node = engine.inputNode()
            fmt = input_node.outputFormatForBus_(0)
            engine.prepare()
            with self.lock:
                self.state["engine"] = engine
                self.state["input_node"] = input_node
                self.state["format"] = fmt
            return True
        except ImportError:
            return False
        except Exception:
            return False

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_start(self, params):
        if not self.ensure_engine():
            return (0, None, ("ERR_NO_ENGINE", "AVAudioEngine not available", 0))
        with self.lock:
            engine = self.state["engine"]
            if engine is None:
                return (0, None, ("ERR_NO_ENGINE", "engine is None", 0))
            if engine.isRunning():
                self.state["running"] = True
                self.state["paused"] = False
                return (1, {"running": True, "already_running": True}, None)
        try:
            engine.prepare()
            ok = engine.startAndReturnError_(None)
            if not ok:
                with self.lock:
                    self.state["stats"]["errors"] += 1
                return (0, None, ("ERR_START", "engine failed to start", 0))
            with self.lock:
                self.state["running"] = True
                self.state["paused"] = False
                self.state["stats"]["starts"] += 1
            return (1, {"running": True}, None)
        except Exception as e:
            with self.lock:
                self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_START", str(e), 0))

    def cmd_pause(self, params):
        with self.lock:
            engine = self.state["engine"]
            if engine is None or not engine.isRunning():
                return (1, {"paused": False, "was_running": False}, None)
        try:
            engine.pause()
            with self.lock:
                self.state["running"] = False
                self.state["paused"] = True
                self.state["stats"]["pauses"] += 1
            return (1, {"paused": True}, None)
        except Exception as e:
            return (0, None, ("ERR_PAUSE", str(e), 0))

    def cmd_resume(self, params):
        with self.lock:
            engine = self.state["engine"]
            if engine is None:
                return (0, None, ("ERR_NO_ENGINE", "engine is None", 0))
            if engine.isRunning():
                self.state["running"] = True
                self.state["paused"] = False
                return (1, {"running": True, "already_running": True}, None)
        try:
            engine.prepare()
            ok = engine.startAndReturnError_(None)
            if not ok:
                return (0, None, ("ERR_RESUME", "engine failed to resume", 0))
            with self.lock:
                self.state["running"] = True
                self.state["paused"] = False
                self.state["stats"]["resumes"] += 1
            return (1, {"running": True}, None)
        except Exception as e:
            return (0, None, ("ERR_RESUME", str(e), 0))

    def cmd_stop(self, params):
        with self.lock:
            engine = self.state["engine"]
            input_node = self.state["input_node"]
        if input_node and self.state["tap_installed"]:
            try:
                input_node.removeTapOnBus_(0)
            except Exception:
                pass
            with self.lock:
                self.state["tap_installed"] = False
        if engine:
            try:
                engine.stop()
            except Exception:
                pass
        with self.lock:
            self.state["running"] = False
            self.state["paused"] = False
            self.state["stats"]["stops"] += 1
        return (1, {"stopped": True}, None)

    def cmd_install_tap(self, params):
        callback = self.p(params, "callback")
        buffer_size = self.p(params, "buffer_size", self.state["config"]["buffer_size"])
        if callback is None:
            return (0, None, ("ERR_PARAMS", "callback required", 0))
        if not self.ensure_engine():
            return (0, None, ("ERR_NO_ENGINE", "AVAudioEngine not available", 0))
        with self.lock:
            input_node = self.state["input_node"]
            fmt = self.state["format"]
            if input_node is None or fmt is None:
                return (0, None, ("ERR_NO_ENGINE", "input node or format is None", 0))
        try:
            input_node.removeTapOnBus_(0)
            input_node.installTapOnBus_bufferSize_format_block_(
                0, buffer_size, fmt, callback
            )
            with self.lock:
                self.state["tap_installed"] = True
                self.state["tap_callback"] = callback
                self.state["config"]["buffer_size"] = buffer_size
            return (1, {"tap_installed": True, "buffer_size": buffer_size}, None)
        except Exception as e:
            return (0, None, ("ERR_TAP", str(e), 0))

    def cmd_remove_tap(self, params):
        with self.lock:
            input_node = self.state["input_node"]
            if input_node is None or not self.state["tap_installed"]:
                return (1, {"tap_removed": False, "was_installed": False}, None)
        try:
            input_node.removeTapOnBus_(0)
            with self.lock:
                self.state["tap_installed"] = False
                self.state["tap_callback"] = None
            return (1, {"tap_removed": True}, None)
        except Exception as e:
            return (0, None, ("ERR_TAP_REMOVE", str(e), 0))

    def cmd_is_running(self, params):
        with self.lock:
            engine = self.state["engine"]
            running = engine is not None and engine.isRunning()
            self.state["running"] = running
            return (1, {"running": running, "paused": self.state["paused"]}, None)

    def cmd_get_format(self, params):
        with self.lock:
            if self.state["format"] is None:
                return (0, None, ("ERR_NO_ENGINE", "engine not initialized", 0))
            return (1, {"format": self.state["format"], "available": True}, None)
