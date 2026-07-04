#!/usr/bin/env python3
# [@GHOST]{[@file<SilenceDetector.py>][@domain<voice>][@role<silence_detector>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<silence_detector>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{SilenceDetector — measures RMS audio levels from AVAudioPCMBuffer to detect speech vs silence. Class-based for better control. VBStyle Run() dispatch, Tuple3, self.state. Thread-safe.}
# [@CLASS]{SilenceDetector}
# [@METHOD]{Run,measure,is_silent,reset,get_level,set_threshold,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Audio-level silence detection for STT. Measures RMS from AVAudioPCMBuffer. VBStyle: Run dispatch, Tuple3, self.state. Has hardcoded fallback values (STT_SILENCE_THRESHOLD=0.01, STT_SILENCE_TIMEOUT=2.5) when imports fail.>][@todos<Move fallback constants to config or make configurable via param.>]}
"""
SilenceDetector — Audio-level silence detection for STT.

WHAT IT DOES:
  - measure     — feed an AVAudioPCMBuffer, computes RMS, tracks speech
  - is_silent   — check if audio has been silent for timeout seconds
  - reset       — clear state for a new listening session
  - get_level   — get current RMS audio level (for UI meters)
  - set_threshold — adjust silence threshold at runtime

WHY CLASS-BASED:
  - Better control: adjust threshold/timeout independently
  - UI can query audio level for mic meter display
  - Clean separation from SttWorker
  - Reusable across different audio sources

USAGE:
  from SilenceDetector import SilenceDetector

  sd = SilenceDetector(param={"silence_threshold": 0.01, "silence_timeout": 2.5})

  # In audio tap callback:
  ok, data, err = sd.Run("measure", {"buffer": avaudio_buffer})

  # In listen loop:
  ok, data, err = sd.Run("is_silent")
  if data and data["silent"]:
      # user stopped talking
"""

import time
import threading

try:
    from core.Dom_Unified.Config import STT_SILENCE_THRESHOLD, STT_SILENCE_TIMEOUT
except ImportError:
    try:
        from Config_ChatGui import STT_SILENCE_THRESHOLD, STT_SILENCE_TIMEOUT
    except ImportError:
        STT_SILENCE_THRESHOLD = 0.01
        STT_SILENCE_TIMEOUT = 2.5


class SilenceDetector:
    """
    Audio-level silence detector — measures RMS from AVAudioPCMBuffer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Thread-safe via lock.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.lock = threading.Lock()
        self.state = {
            "config": {
                "silence_threshold": param.get("silence_threshold", STT_SILENCE_THRESHOLD) if param else STT_SILENCE_THRESHOLD,
                "silence_timeout": param.get("silence_timeout", STT_SILENCE_TIMEOUT) if param else STT_SILENCE_TIMEOUT,
            },
            "audio_level": 0.0,
            "peak_level": 0.0,
            "last_audio_time": 0,
            "has_speech": False,
            "speech_count": 0,
            "silence_count": 0,
            "started_at": 0,
        }

    def Run(self, command, params=None):
        dispatch = {
            "measure": self.cmd_measure,
            "is_silent": self.cmd_is_silent,
            "reset": self.cmd_reset,
            "get_level": self.cmd_get_level,
            "set_threshold": self.cmd_set_threshold,
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
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_measure(self, params):
        """Measure RMS of an AVAudioPCMBuffer. Updates audio level + speech tracking."""
        buffer = self.p(params, "buffer")
        if buffer is None:
            return (0, None, ("ERR_PARAMS", "buffer required", 0))
        try:
            n = buffer.frameLength()
            if n == 0:
                return (1, {"level": 0.0, "has_speech": False}, None)

            data = buffer.floatChannelData()
            if data is None:
                return (1, {"level": 0.0, "has_speech": False}, None)

            ch0 = data[0]
            sum_sq = 0.0
            for i in range(n):
                sample = ch0[i]
                sum_sq += sample * sample
            rms = (sum_sq / n) ** 0.5

            with self.lock:
                threshold = self.state["config"]["silence_threshold"]
                self.state["audio_level"] = rms
                if rms > self.state["peak_level"]:
                    self.state["peak_level"] = rms

                if rms > threshold:
                    self.state["last_audio_time"] = time.time()
                    if not self.state["has_speech"]:
                        self.state["has_speech"] = True
                    self.state["speech_count"] += 1
                else:
                    self.state["silence_count"] += 1

                return (1, {
                    "level": rms,
                    "has_speech": self.state["has_speech"],
                    "is_above_threshold": rms > threshold,
                }, None)
        except Exception as e:
            return (0, None, ("ERR_MEASURE", str(e), 0))

    def cmd_is_silent(self, params):
        """Check if audio has been silent for silence_timeout seconds."""
        with self.lock:
            now = time.time()
            timeout = self.state["config"]["silence_timeout"]
            last_audio = self.state["last_audio_time"]
            has_speech = self.state["has_speech"]

            if not has_speech or last_audio == 0:
                return (1, {"silent": False, "reason": "no_speech_detected"}, None)

            silence_duration = now - last_audio
            is_silent = silence_duration > timeout
            return (1, {
                "silent": is_silent,
                "silence_duration": round(silence_duration, 2),
                "timeout": timeout,
                "audio_level": self.state["audio_level"],
            }, None)

    def cmd_reset(self, params):
        """Reset state for a new listening session."""
        with self.lock:
            self.state["audio_level"] = 0.0
            self.state["peak_level"] = 0.0
            self.state["last_audio_time"] = 0
            self.state["has_speech"] = False
            self.state["speech_count"] = 0
            self.state["silence_count"] = 0
            self.state["started_at"] = time.time()
            return (1, {"reset": True}, None)

    def cmd_get_level(self, params):
        """Get current audio level — for UI mic meter display."""
        with self.lock:
            return (1, {
                "level": self.state["audio_level"],
                "peak": self.state["peak_level"],
                "has_speech": self.state["has_speech"],
                "speech_count": self.state["speech_count"],
                "silence_count": self.state["silence_count"],
            }, None)

    def cmd_set_threshold(self, params):
        """Set silence threshold at runtime."""
        threshold = self.p(params, "threshold")
        if threshold is None:
            return (0, None, ("ERR_PARAMS", "threshold required", 0))
        with self.lock:
            self.state["config"]["silence_threshold"] = threshold
            return (1, {"threshold": threshold}, None)
