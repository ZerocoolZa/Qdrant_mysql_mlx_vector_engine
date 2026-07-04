#!/usr/bin/env python3
# [@GHOST]{[@file<VoiceEngine.py>][@domain<voice>][@role<voice_orchestrator>][@auth<devin>][@date<2026-06-27>][@ver<4.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<voice_orchestrator>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{VoiceEngine v4 — Orchestrator. Uses VoiceConfig, TtsController, SttController, AudioEngineManager, SilenceDetector. Thin dispatch layer. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{VoiceEngine}
# [@METHOD]{Run,speak,stop_speaking,is_speaking,listen,stop_listening,mute,unmute,list_voices,get_audio_level,warmup,save_settings,load_settings,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Voice orchestrator v4. Thin dispatch layer wiring VoiceConfig, TtsController, SttController, AudioEngineManager, SilenceDetector. VBStyle: Run dispatch, Tuple3, self.state. Inherits QObject, uses pyqtSignal. No violations visible.>][@todos<none>]}

"""
VoiceEngine v4 — Voice orchestrator for ChatGui.

ARCHITECTURE (class-based, all dynamic):
  VoiceConfig.py        → config management (load/save/persist)
  AudioEngineManager.py → AVAudioEngine lifecycle (persistent)
  TtsController.py      → TTS via NSSpeechSynthesizer (50ms)
  SttController.py      → STT via SFSpeechRecognizer (persistent)
  SilenceDetector.py    → audio-level silence detection
  VoiceEngine.py        → THIS FILE — thin orchestrator

WHAT IT DOES:
  - Creates and wires all voice classes
  - Dispatches commands to appropriate class
  - Manages TTS/STT feedback loop (mute/unmute)
  - Provides unified Run() interface for ChatGui

USAGE:
  from VoiceEngine import VoiceEngine

  ve = VoiceEngine()
  ve.Run("warmup")  # pre-initialize everything

  ok, data, err = ve.Run("speak", {"text": "Hello"})
  ok, data, err = ve.Run("listen", {"on_partial": h1, "on_finished": h2})
  ok, data, err = ve.Run("mute")    # during TTS
  ok, data, err = ve.Run("unmute")  # after TTS
  ok, data, err = ve.Run("get_audio_level")  # for UI meter
  ok, data, err = ve.Run("save_settings", {"path": "..."})
"""

import threading
from PyQt6.QtCore import QObject, pyqtSignal

from VoiceConfig import VoiceConfig
from TtsController import TtsController
from SttController import SttController
from AudioEngineManager import AudioEngineManager
from SilenceDetector import SilenceDetector


class VoiceEngine(QObject):
    """
    Voice orchestrator — wires all voice classes, dispatches commands.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    All aspects are dynamic via Run("set_config").
    """

    ttsFinished = pyqtSignal()

    def __init__(self, mem=None, db=None, param=None):
        super().__init__()
        # Create all sub-classes
        self.config = VoiceConfig()
        self.audio = AudioEngineManager()
        self.detector = SilenceDetector()
        self.tts = TtsController(param=self.config.state["config"])
        self.stt = SttController(param={
            "audio_engine": self.audio,
            "silence_detector": self.detector,
            **self.config.state["config"],
        })
        self.state = {
            "config": self.config.state["config"],  # reference — stays in sync
            "speaking": False,
            "listening": False,
            "muted": False,
            "stt_was_listening": False,
            "stt_callbacks": None,
            "stats": {"speak_count": 0, "listen_count": 0, "errors": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "speak": self.cmd_speak,
            "stop_speaking": self.cmd_stop_speaking,
            "is_speaking": self.cmd_is_speaking,
            "listen": self.cmd_listen,
            "stop_listening": self.cmd_stop_listening,
            "mute": self.cmd_mute,
            "unmute": self.cmd_unmute,
            "list_voices": self.cmd_list_voices,
            "get_audio_level": self.cmd_get_audio_level,
            "warmup": self.cmd_warmup,
            "save_settings": self.cmd_save_settings,
            "load_settings": self.cmd_load_settings,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        ok, cfg, err = self.config.Run("read_state")
        okTts, ttsState, errTts = self.tts.Run("read_state")
        okStt, sttState, errStt = self.stt.Run("read_state")
        okAud, audState, errAud = self.audio.Run("read_state")
        okDet, detState, errDet = self.detector.Run("read_state")
        return (1, {
            "config": cfg.get("config", {}) if cfg else {},
            "tts": ttsState if ttsState else {},
            "stt": sttState if sttState else {},
            "audio": audState if audState else {},
            "detector": detState if detState else {},
            "engine": dict(self.state),
        }, None)

    def set_config(self, params):
        # Update all sub-classes
        self.config.Run("set_config", params)
        self.tts.Run("set_config", params)
        self.stt.Run("set_config", params)
        self.audio.Run("set_config", params)
        self.detector.Run("set_config", params)
        return (1, dict(self.config.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # WARMUP — pre-initialize everything
    # ════════════════════════════════════════════

    def cmd_warmup(self, params):
        okTts, dataTts, errTts = self.tts.Run("warmup")
        okStt, dataStt, errStt = self.stt.Run("warmup")
        return (1, {"warmed_up": True, "tts": dataTts, "stt": dataStt}, None)

    # ════════════════════════════════════════════
    # TTS COMMANDS
    # ════════════════════════════════════════════

    def cmd_speak(self, params):
        text = self.p(params, "text")
        if not text or not text.strip():
            return (0, None, ("ERR_PARAMS", "text required", 0))
        # Mute STT to prevent feedback loop
        okStt, dataStt, errStt = self.stt.Run("is_listening")
        if okStt and dataStt and dataStt.get("listening"):
            self.state["stt_was_listening"] = True
            self.stt.Run("mute")
        else:
            self.state["stt_was_listening"] = False
        # Speak
        ok, data, err = self.tts.Run("speak", {"text": text})
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        self.state["speaking"] = True
        self.state["stats"]["speak_count"] += 1
        # TTS finished — emit signal + unmute STT
        self.state["speaking"] = False
        self.ttsFinished.emit()
        if self.state["stt_was_listening"]:
            self.stt.Run("unmute")
        return (1, data, None)

    def cmd_stop_speaking(self, params):
        ok, data, err = self.tts.Run("stop")
        self.state["speaking"] = False
        return (ok, data, err)

    def cmd_is_speaking(self, params):
        ok, data, err = self.tts.Run("is_speaking")
        if ok and data:
            self.state["speaking"] = data.get("speaking", False)
        return (ok, data, err)

    # ════════════════════════════════════════════
    # STT COMMANDS
    # ════════════════════════════════════════════

    def cmd_listen(self, params):
        # Don't start if TTS is speaking
        okTts, dataTts, errTts = self.tts.Run("is_speaking")
        if okTts and dataTts and dataTts.get("speaking"):
            self.state["stt_callbacks"] = params
            self.state["listening"] = True
            return (1, {"listening": True, "waiting_for_tts": True}, None)
        ok, data, err = self.stt.Run("listen", params)
        if not ok:
            self.state["stats"]["errors"] += 1
            return (0, None, err)
        self.state["listening"] = True
        self.state["stats"]["listen_count"] += 1
        return (1, data, None)

    def cmd_stop_listening(self, params):
        ok, data, err = self.stt.Run("stop_listening")
        self.state["listening"] = False
        self.state["stt_was_listening"] = False
        self.state["stt_callbacks"] = None
        return (ok, data, err)

    def cmd_mute(self, params):
        ok, data, err = self.stt.Run("mute")
        self.state["muted"] = True
        return (ok, data, err)

    def cmd_unmute(self, params):
        ok, data, err = self.stt.Run("unmute")
        self.state["muted"] = False
        return (ok, data, err)

    # ════════════════════════════════════════════
    # UTILITY COMMANDS
    # ════════════════════════════════════════════

    def cmd_list_voices(self, params):
        ok, data, err = self.tts.Run("list_voices")
        if ok and data:
            self.config.state["voices"] = data
        return (ok, data, err)

    def cmd_get_audio_level(self, params):
        ok, data, err = self.detector.Run("get_level")
        return (ok, data, err)

    def cmd_save_settings(self, params):
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        # Sync config from all classes
        ok, data, err = self.config.Run("save", {"path": path})
        return (ok, data, err)

    def cmd_load_settings(self, params):
        path = self.p(params, "path")
        if not path:
            return (0, None, ("ERR_PARAMS", "path required", 0))
        ok, data, err = self.config.Run("load", {"path": path})
        if not ok:
            return (0, None, err)
        # Propagate loaded config to all sub-classes
        self.set_config(self.config.state["config"])
        return (1, data, None)
