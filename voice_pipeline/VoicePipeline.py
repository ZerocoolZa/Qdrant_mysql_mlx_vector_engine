#!/usr/bin/env python3
# [@GHOST]{[@file<VoicePipeline.py>][@domain<voice_pipeline>][@role<orchestrator>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Full pipeline: mic → STT + tone extraction → VoicePacket → AI → tone-matched TTS reply>]}
# [@VBSTYLE]{[@auth<devin>][@role<orchestrator>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{VoicePipeline — the orchestrator. Mic → VoiceCapture → ToneAnalyzer + SpeechTranscriber → VoicePacket → (AI receives text+tone) → ToneSynthesizer replies with matched voice. The AI hears BOTH what you said AND how you said it.}
# [@FILEID]{VoicePipeline.py}
# [@CLASS]{VoicePipeline}
# [@METHOD]{Run, Listen, ListenAndReply, Speak, Stream, Test, GetState}

import sys
import os
import time
import json

from Config import Config
from VoiceCapture import VoiceCapture
from ToneAnalyzer import ToneAnalyzer
from SpeechTranscriber import SpeechTranscriber
from ToneSynthesizer import ToneSynthesizer
from VoicePacket import VoicePacket


class VoicePipeline:

    def __init__(self, mem=None, db=None, param=None):
        self.config = Config()
        self.config.Run("load", None)
        self.capture = VoiceCapture()
        self.analyzer = ToneAnalyzer()
        self.transcriber = SpeechTranscriber()
        self.synthesizer = ToneSynthesizer()
        self.packet = VoicePacket()
        self.state = {
            "lastPacket": None,
            "lastTranscript": "",
            "lastTone": {},
            "lastReply": "",
            "history": [],
            "listening": False,
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "listen": self.Listen,
            "listenAndReply": self.ListenAndReply,
            "speak": self.Speak,
            "stream": self.Stream,
            "test": self.Test,
            "getState": self.GetState,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Listen(self, params):
        if params is None:
            params = {}
        maxDur = params.get("maxDuration", 30)
        self.state["listening"] = True

        ok, capData, err = self.capture.Run("record", {"maxDuration": maxDur})
        if not ok:
            self.state["listening"] = False
            return (0, None, err)

        audio = capData["audio"]
        sr = capData["sampleRate"]

        ok, saveInfo, err = self.capture.Run("saveWav", {"audio": audio, "sampleRate": sr})
        wavPath = saveInfo.get("path") if ok else None

        ok, tonePacket, err = self.analyzer.Run("analyzeArray", {"audio": audio, "sampleRate": sr, "text": ""})
        tone = tonePacket.get("tone", {}) if ok else {}

        ok, transResult, err = self.transcriber.Run("transcribeArray", {"audio": audio, "sampleRate": sr})
        transcript = transResult.get("text", "") if ok else ""

        ok, packet, err = self.packet.Run("fromFeatures", {
            "text": transcript,
            "features": self.analyzer.state.get("features", {}),
            "emotion": self.analyzer.state.get("emotion", {}),
        })

        self.state["lastPacket"] = packet
        self.state["lastTranscript"] = transcript
        self.state["lastTone"] = packet.get("tone", tone)
        self.state["listening"] = False

        result = {
            "transcript": transcript,
            "tone": packet.get("tone", tone),
            "packet": packet,
            "wavPath": wavPath,
            "duration": capData["duration"],
        }
        self.state["history"].append(result)
        return (1, result, None)

    def ListenAndReply(self, params):
        if params is None:
            params = {}
        replyText = params.get("reply", "")
        autoReply = params.get("autoReply", False)

        ok, listenResult, err = self.Listen(params)
        if not ok:
            return (0, None, err)

        transcript = listenResult["transcript"]
        tone = listenResult["tone"]

        if autoReply and not replyText:
            replyText = self._autoReply(transcript, tone)

        if not replyText:
            return (1, listenResult, None)

        ok, speakResult, err = self.synthesizer.Run("speakWithTone", {
            "text": replyText,
            "tone": tone,
            "play": True,
        })
        if not ok:
            listenResult["replyError"] = err
            return (1, listenResult, None)

        self.state["lastReply"] = replyText
        listenResult["reply"] = replyText
        listenResult["replyVoice"] = speakResult.get("voice")
        listenResult["replyWav"] = speakResult.get("path")
        return (1, listenResult, None)

    def Speak(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        if not text:
            return (0, None, (1, "Missing text", 0))
        tone = params.get("tone")
        if tone:
            return self.synthesizer.Run("speakWithTone", {"text": text, "tone": tone, "play": True})
        voice = params.get("voice")
        if voice:
            return self.synthesizer.Run("speak", {"text": text, "voice": voice, "play": True})
        return self.synthesizer.Run("speak", {"text": text, "play": True})

    def Stream(self, params):
        if params is None:
            params = {}
        rounds = params.get("rounds", 3)
        results = []
        for i in range(rounds):
            self._p("=== Round %d/%d ===" % (i + 1, rounds))
            ok, result, err = self.ListenAndReply(params)
            if not ok:
                self._p("Round %d failed: %s" % (i + 1, str(err)))
                break
            results.append(result)
        return (1, {"rounds": results, "count": len(results)}, None)

    def Test(self, params):
        results = {}

        ok, capData, err = self.capture.Run("recordDuration", {"duration": 3.0})
        results["capture"] = {"ok": ok, "data": {"duration": capData.get("duration")} if ok else None, "error": err}

        if ok:
            ok, saveInfo, err = self.capture.Run("saveWav", {"audio": capData["audio"], "sampleRate": capData["sampleRate"]})
            results["saveWav"] = {"ok": ok, "path": saveInfo.get("path") if ok else None, "error": err}

            ok, tonePacket, err = self.analyzer.Run("analyzeArray", {"audio": capData["audio"], "sampleRate": capData["sampleRate"], "text": "test"})
            results["toneAnalysis"] = {"ok": ok, "tone": tonePacket.get("tone") if ok else None, "error": err}

            ok, transResult, err = self.transcriber.Run("transcribeArray", {"audio": capData["audio"], "sampleRate": capData["sampleRate"]})
            results["transcription"] = {"ok": ok, "text": transResult.get("text") if ok else None, "error": err}

        ok, speakResult, err = self.synthesizer.Run("speak", {"text": "Voice pipeline test complete. All systems operational.", "voice": "af_bella", "play": True})
        results["synthesis"] = {"ok": ok, "path": speakResult.get("path") if ok else None, "error": err}

        return (1, results, None)

    def GetState(self, params):
        return (1, {
            "lastTranscript": self.state.get("lastTranscript"),
            "lastTone": self.state.get("lastTone"),
            "lastReply": self.state.get("lastReply"),
            "historyCount": len(self.state.get("history", [])),
            "listening": self.state.get("listening", False),
        }, None)

    def _autoReply(self, transcript, tone):
        mood = tone.get("mood", "neutral")
        excitement = tone.get("excitement", 0.5)

        if not transcript:
            return "I didn't catch that. Could you repeat it?"

        if mood == "excited" or excitement > 0.7:
            return "I can hear you're excited! You said: " + transcript + ". That's great — let's get it done."
        if mood == "sad":
            return "I hear you. You said: " + transcript + ". I'm here to help with that."
        if mood == "stressed" or mood == "tense":
            return "Sounds like you're under pressure. You said: " + transcript + ". Let's tackle this step by step."
        if mood == "calm":
            return "Got it. You said: " + transcript + ". I'll take care of that for you."
        if mood == "confident":
            return "Understood. You said: " + transcript + ". Let's execute."
        return "I heard you say: " + transcript + ". What would you like me to do with that?"
