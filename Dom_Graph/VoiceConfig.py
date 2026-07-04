#!/usr/bin/env python3
# [@GHOST]{[@file<VoiceConfig.py>][@domain<voice>][@role<config>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<config>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{VoiceConfig — central config for all voice classes. Loads from Dom_Unified/Config.py, falls back to Config_ChatGui.py. Runtime updates via Run(). Persists to JSON. No hardcoded values.}
# [@CLASS]{VoiceConfig}
# [@METHOD]{Run,load,save,get,set,reset,defaults,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Central config manager for voice system. Loads from Dom_Unified/Config.py with fallback. Runtime updates via Run(). Persists to JSON. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
VoiceConfig — Central config manager for the voice system.

WHAT IT MANAGES:
  - TTS config: enabled, voice, rate, tts_engine
  - STT config: language, on_device, buffer_size, silence_timeout,
                min_listen, max_timeout, runloop_interval, silence_threshold
  - Voices list: available macOS voices
  - Persistence: load/save to JSON file

WHY CLASS-BASED:
  - Single source of truth — all voice classes read from this
  - Runtime updates — change any setting without restart
  - Persistence — save/load user preferences
  - Defaults — fall back to Config.py constants

USAGE:
  from VoiceConfig import VoiceConfig

  cfg = VoiceConfig()
  ok, data, err = cfg.Run("get", {"key": "voice"})  # → "Samantha"
  ok, data, err = cfg.Run("set", {"voice": "Alex", "rate": 200})
  ok, data, err = cfg.Run("save", {"path": "/path/to/settings.json"})
  ok, data, err = cfg.Run("load", {"path": "/path/to/settings.json"})
  ok, data, err = cfg.Run("defaults")  # reset to Config.py values
"""

import json
import os

# ════════════════════════════════════════════
# CONFIG LOADING — from Dom_Unified/Config.py
# ════════════════════════════════════════════

try:
    from core.Dom_Unified.Config import (
        VOICE_ENABLED, VOICE_NAME, VOICE_RATE, VOICE_TTS_ENGINE,
        STT_ENABLED, STT_LANGUAGE, STT_ON_DEVICE, STT_BUFFER_SIZE,
        STT_SILENCE_TIMEOUT, STT_MIN_LISTEN, STT_MAX_TIMEOUT,
        STT_RUNLOOP_INTERVAL, STT_SILENCE_THRESHOLD, MACOS_VOICES,
    )
    CONFIG_SOURCE = "Dom_Unified"
except ImportError:
    try:
        from Config_ChatGui import (
            VOICE_ENABLED, VOICE_NAME, VOICE_RATE, VOICE_TTS_ENGINE,
            STT_ENABLED, STT_LANGUAGE, STT_ON_DEVICE, STT_BUFFER_SIZE,
            STT_SILENCE_TIMEOUT, STT_MIN_LISTEN, STT_MAX_TIMEOUT,
            STT_RUNLOOP_INTERVAL, STT_SILENCE_THRESHOLD, MACOS_VOICES,
        )
        CONFIG_SOURCE = "Config_ChatGui"
    except ImportError:
        VOICE_ENABLED = False
        VOICE_NAME = "Samantha"
        VOICE_RATE = 180
        VOICE_TTS_ENGINE = "say"
        STT_ENABLED = False
        STT_LANGUAGE = "en-US"
        STT_ON_DEVICE = True
        STT_BUFFER_SIZE = 4096
        STT_SILENCE_TIMEOUT = 2.5
        STT_MIN_LISTEN = 1.0
        STT_MAX_TIMEOUT = 60
        STT_RUNLOOP_INTERVAL = 0.05
        STT_SILENCE_THRESHOLD = 0.01
        MACOS_VOICES = ["Samantha", "Alex", "Daniel", "Karen"]
        CONFIG_SOURCE = "fallback"

# Keys that map to voice config
CONFIG_KEYS = [
    "enabled", "voice", "rate", "tts_engine",
    "stt_enabled", "stt_language", "stt_on_device", "stt_buffer_size",
    "stt_silence_timeout", "stt_min_listen", "stt_max_timeout",
    "stt_runloop_interval", "stt_silence_threshold",
]

# JSON key mapping (settings file uses different names than internal)
JSON_MAP = {
    "voice_enabled": "enabled",
    "voice_name": "voice",
    "voice_rate": "rate",
    "stt_on_device": "stt_on_device",
    "stt_language": "stt_language",
    "stt_buffer_size": "stt_buffer_size",
    "stt_silence_timeout": "stt_silence_timeout",
    "stt_min_listen": "stt_min_listen",
    "stt_max_timeout": "stt_max_timeout",
    "stt_runloop_interval": "stt_runloop_interval",
    "stt_silence_threshold": "stt_silence_threshold",
}


class VoiceConfig:
    """
    Central config manager for the voice system.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    All config is dynamic — change at runtime via Run("set").
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": self.defaults_dict(),
            "voices": list(MACOS_VOICES),
            "config_source": CONFIG_SOURCE,
            "persist_path": param.get("persist_path", "") if param else "",
        }

    def defaults_dict(self):
        return {
            "enabled": VOICE_ENABLED,
            "voice": VOICE_NAME,
            "rate": VOICE_RATE,
            "tts_engine": VOICE_TTS_ENGINE,
            "stt_enabled": STT_ENABLED,
            "stt_language": STT_LANGUAGE,
            "stt_on_device": STT_ON_DEVICE,
            "stt_buffer_size": STT_BUFFER_SIZE,
            "stt_silence_timeout": STT_SILENCE_TIMEOUT,
            "stt_min_listen": STT_MIN_LISTEN,
            "stt_max_timeout": STT_MAX_TIMEOUT,
            "stt_runloop_interval": STT_RUNLOOP_INTERVAL,
            "stt_silence_threshold": STT_SILENCE_THRESHOLD,
        }

    def Run(self, command, params=None):
        dispatch = {
            "get": self.cmd_get,
            "set": self.cmd_set,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "defaults": self.cmd_defaults,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_get(self, params):
        key = self.p(params, "key")
        if key:
            val = self.state["config"].get(key)
            if val is None:
                return (0, None, ("ERR_NOT_FOUND", "key not found: %s" % key, 0))
            return (1, val, None)
        return (1, dict(self.state["config"]), None)

    def cmd_set(self, params):
        changed = {}
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
                changed[key] = val
        if not changed:
            return (0, None, ("ERR_NO_KEYS", "no valid config keys in params", 0))
        return (1, changed, None)

    def cmd_save(self, params):
        path = self.p(params, "path", self.state["persist_path"])
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        try:
            data = {}
            for json_key, internal_key in JSON_MAP.items():
                if internal_key in self.state["config"]:
                    data[json_key] = self.state["config"][internal_key]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.state["persist_path"] = path
            return (1, {"saved": True, "path": path, "keys": len(data)}, None)
        except Exception as e:
            return (0, None, ("ERR_SAVE", str(e), 0))

    def cmd_load(self, params):
        path = self.p(params, "path", self.state["persist_path"])
        if not path or not os.path.exists(path):
            return (0, None, ("ERR_PARAMS", "path required or not found", 0))
        try:
            with open(path, "r") as f:
                data = json.load(f)
            loaded = {}
            for json_key, internal_key in JSON_MAP.items():
                if json_key in data:
                    self.state["config"][internal_key] = data[json_key]
                    loaded[internal_key] = data[json_key]
            self.state["persist_path"] = path
            return (1, {"loaded": True, "path": path, "keys": len(loaded)}, None)
        except Exception as e:
            return (0, None, ("ERR_LOAD", str(e), 0))

    def cmd_defaults(self, params):
        self.state["config"] = self.defaults_dict()
        return (1, {"reset": True, "config": dict(self.state["config"])}, None)
