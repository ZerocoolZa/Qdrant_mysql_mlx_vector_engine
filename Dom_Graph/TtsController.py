#!/usr/bin/env python3
# [@GHOST]{[@file<TtsController.py>][@domain<voice>][@role<tts>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<tts>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{TtsController — TTS via NSSpeechSynthesizer (50ms) with say fallback. Shared synth instance. Voice/rate control. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{TtsController}
# [@METHOD]{Run,speak,stop,is_speaking,set_voice,set_rate,list_voices,warmup,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<TTS via NSSpeechSynthesizer (50ms) with say fallback. Shared synth instance, voice/rate control. VBStyle: Run dispatch, Tuple3, self.state. No violations visible.>][@todos<none>]}

"""
TtsController — Text-to-Speech control via NSSpeechSynthesizer.

WHAT IT MANAGES:
  - NSSpeechSynthesizer shared instance (50ms latency vs 600ms subprocess)
  - Voice selection (80+ macOS voices)
  - Rate control (80-400 wpm)
  - Stop/cancel speech
  - Fallback to subprocess `say` if PyObjC unavailable

WHY CLASS-BASED:
  - Shared synthesizer — no cold start
  - Dynamic voice/rate changes at runtime
  - Centralized TTS state — know if speaking, what voice, what rate
  - Warmup — pre-initialize synthesizer at app startup

USAGE:
  from TtsController import TtsController

  tts = TtsController()
  ok, data, err = tts.Run("warmup")
  ok, data, err = tts.Run("speak", {"text": "Hello world"})
  ok, data, err = tts.Run("stop")
  ok, data, err = tts.Run("set_voice", {"voice": "Alex"})
  ok, data, err = tts.Run("list_voices")
"""

import subprocess
import re
import time
import threading


class TtsController:
    """
    TTS controller — NSSpeechSynthesizer with say fallback.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Thread-safe via lock.
    """

    sharedSynth = None
    synthLock = threading.Lock()

    def __init__(self, mem=None, db=None, param=None):
        self.lock = threading.Lock()
        self.state = {
            "config": {
                "voice": param.get("voice", "Samantha") if param else "Samantha",
                "rate": param.get("rate", 180) if param else 180,
                "tts_engine": param.get("tts_engine", "say") if param else "say",
                "max_length": 2000,
            },
            "speaking": False,
            "use_nssynth": False,
            "current_text": "",
            "warmed_up": False,
            "stats": {"speak_count": 0, "stop_count": 0, "errors": 0, "fallback_count": 0},
        }
        self.running = True

    def Run(self, command, params=None):
        dispatch = {
            "speak": self.cmd_speak,
            "stop": self.cmd_stop,
            "is_speaking": self.cmd_is_speaking,
            "set_voice": self.cmd_set_voice,
            "set_rate": self.cmd_set_rate,
            "list_voices": self.cmd_list_voices,
            "warmup": self.cmd_warmup,
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
    # INTERNAL
    # ════════════════════════════════════════════

    def clean_text(self, text):
        clean = re.sub(r'<[^>]+>', '', text)
        clean = clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        clean = clean.replace('<br>', ' ').replace('&nbsp;', ' ')
        clean = clean.strip()
        max_len = self.state["config"]["max_length"]
        if not clean or len(clean) > max_len:
            clean = clean[:max_len] if clean else ""
        return clean

    def init_synth(self):
        try:
            from AppKit import NSSpeechSynthesizer
            with TtsController.synthLock:
                if TtsController.sharedSynth is None:
                    TtsController.sharedSynth = NSSpeechSynthesizer.alloc().initWithVoice_(self.state["config"]["voice"])
                if TtsController.sharedSynth is None:
                    return False
            synth = TtsController.sharedSynth
            synth.setVoice_(self.state["config"]["voice"])
            synth.setRate_(self.state["config"]["rate"])
            with self.lock:
                self.state["use_nssynth"] = True
            return True
        except ImportError:
            return False
        except Exception:
            return False

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_warmup(self, params):
        if self.state["warmed_up"]:
            return (1, {"warmed_up": True, "note": "already warmed"}, None)
        # Warm up speechsynthesisd daemon
        try:
            subprocess.run(["say", " "], capture_output=True, timeout=3)
        except Exception:
            pass
        # Initialize shared synthesizer
        self.init_synth()
        with self.lock:
            self.state["warmed_up"] = True
        return (1, {"warmed_up": True, "use_nssynth": self.state["use_nssynth"]}, None)

    def cmd_speak(self, params):
        text = self.p(params, "text")
        if not text or not text.strip():
            return (0, None, ("ERR_PARAMS", "text required", 0))
        clean = self.clean_text(text)
        if not clean:
            return (1, {"speaking": False, "reason": "empty after clean"}, None)

        with self.lock:
            self.state["speaking"] = True
            self.state["current_text"] = clean
            self.state["stats"]["speak_count"] += 1

        # Stop existing speech
        self.cmd_stop({})

        # Try NSSpeechSynthesizer (50ms) — fallback to subprocess say (600ms)
        if self.init_synth():
            return self.speak_nssynth(clean)
        else:
            return self.speak_say(clean)

    def speak_nssynth(self, clean):
        try:
            with TtsController.synthLock:
                synth = TtsController.sharedSynth
            if synth is None:
                return self.speak_say(clean)
            synth.startSpeakingString_(clean)
            while synth.isSpeaking():
                if not self.running:
                    synth.stopSpeaking()
                    break
                time.sleep(0.05)
            with self.lock:
                self.state["speaking"] = False
            return (1, {"speaking": False, "engine": "NSSpeechSynthesizer", "text_len": len(clean)}, None)
        except Exception as e:
            with self.lock:
                self.state["stats"]["errors"] += 1
                self.state["speaking"] = False
            return self.speak_say(clean)

    def speak_say(self, clean):
        try:
            cmd = [self.state["config"]["tts_engine"], "-v", self.state["config"]["voice"],
                   "-r", str(self.state["config"]["rate"]), clean]
            proc = subprocess.run(cmd, capture_output=True, timeout=30)
            with self.lock:
                self.state["speaking"] = False
                self.state["stats"]["fallback_count"] += 1
            if proc.returncode != 0:
                err = proc.stderr.decode().strip()
                if err:
                    return (0, None, ("ERR_SAY", err, 0))
            return (1, {"speaking": False, "engine": "say", "text_len": len(clean)}, None)
        except subprocess.TimeoutExpired:
            with self.lock:
                self.state["speaking"] = False
                self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_TIMEOUT", "TTS timed out", 0))
        except Exception as e:
            with self.lock:
                self.state["speaking"] = False
                self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_SAY", str(e), 0))

    def cmd_stop(self, params):
        with self.lock:
            speaking = self.state["speaking"]
            use_nssynth = self.state["use_nssynth"]
            self.state["speaking"] = False
            self.state["stats"]["stop_count"] += 1
        self.running = False
        if use_nssynth:
            try:
                with TtsController.synthLock:
                    if TtsController.sharedSynth:
                        TtsController.sharedSynth.stopSpeaking()
            except Exception:
                pass
        else:
            try:
                subprocess.run(["killall", "say"], capture_output=True, timeout=2)
            except Exception:
                pass
        self.running = True
        return (1, {"speaking": False, "was_speaking": speaking}, None)

    def cmd_is_speaking(self, params):
        with self.lock:
            if self.state["use_nssynth"]:
                try:
                    with TtsController.synthLock:
                        speaking = TtsController.sharedSynth and TtsController.sharedSynth.isSpeaking()
                except Exception:
                    speaking = self.state["speaking"]
            else:
                speaking = self.state["speaking"]
            self.state["speaking"] = speaking
            return (1, {"speaking": speaking}, None)

    def cmd_set_voice(self, params):
        voice = self.p(params, "voice")
        if not voice:
            return (0, None, ("ERR_PARAMS", "voice required", 0))
        with self.lock:
            self.state["config"]["voice"] = voice
        if self.state["use_nssynth"]:
            try:
                with TtsController.synthLock:
                    if TtsController.sharedSynth:
                        TtsController.sharedSynth.setVoice_(voice)
            except Exception:
                pass
        return (1, {"voice": voice}, None)

    def cmd_set_rate(self, params):
        rate = self.p(params, "rate")
        if rate is None:
            return (0, None, ("ERR_PARAMS", "rate required", 0))
        with self.lock:
            self.state["config"]["rate"] = rate
        if self.state["use_nssynth"]:
            try:
                with TtsController.synthLock:
                    if TtsController.sharedSynth:
                        TtsController.sharedSynth.setRate_(rate)
            except Exception:
                pass
        return (1, {"rate": rate}, None)

    def cmd_list_voices(self, params):
        try:
            proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5)
            voices = []
            for line in proc.stdout.strip().split("\n"):
                parts = line.strip().split(None, 2)
                if parts:
                    voices.append(parts[0])
            with self.lock:
                self.state["voices"] = voices
            return (1, voices, None)
        except Exception:
            return (1, ["Samantha", "Alex", "Daniel", "Karen"], None)
