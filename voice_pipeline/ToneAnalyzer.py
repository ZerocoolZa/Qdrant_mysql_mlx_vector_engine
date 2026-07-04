#!/usr/bin/env python3
# [@GHOST]{[@file<ToneAnalyzer.py>][@domain<voice_pipeline>][@role<analyzer>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Extracts VoicePacket tone data from audio — uses voice_engine.py VoiceDNA for 200+ features>]}
# [@VBSTYLE]{[@auth<devin>][@role<analyzer>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{ToneAnalyzer — extracts the tone packet from audio. Wraps voice_engine.py VoiceDNA (parselmouth+librosa, 200+ features, emotion extraction). Outputs a VoicePacket with emotion, energy, pitch, stress, prosody.}
# [@FILEID]{ToneAnalyzer.py}
# [@CLASS]{ToneAnalyzer}
# [@METHOD]{Run, Analyze, AnalyzeFile, AnalyzeArray, BuildPacket, GetFeatures}

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from voice_engine import VoiceDNA, VoiceAnalyzer, HAS_PARSELMOUTH, HAS_LIBROSA

from VoicePacket import VoicePacket
from Config import SAMPLE_RATE


class ToneAnalyzer:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "engine": None,
            "features": {},
            "emotion": {},
            "packet": None,
            "useFullDna": HAS_PARSELMOUTH and HAS_LIBROSA,
        }
        self.packet = VoicePacket()
        if self.state["useFullDna"]:
            self.state["engine"] = VoiceDNA()
        else:
            self.state["engine"] = VoiceAnalyzer()

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "analyze": self.Analyze,
            "analyzeFile": self.AnalyzeFile,
            "analyzeArray": self.AnalyzeArray,
            "buildPacket": self.BuildPacket,
            "getFeatures": self.GetFeatures,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Analyze(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        path = params.get("path")
        if path:
            return self.AnalyzeFile(params)
        audio = params.get("audio")
        if audio is not None:
            return self.AnalyzeArray(params)
        return (0, None, (1, "Need path or audio", 0))

    def AnalyzeFile(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (1, "Missing path", 0))
        text = params.get("text", "")
        engine = self.state["engine"]
        ok, _, err = engine.Run("load", {"path": path})
        if not ok:
            return (0, None, err)
        ok, features, err = engine.Run("analyze", None)
        if not ok:
            return (0, None, err)
        self.state["features"] = features
        emotion = {k: v for k, v in features.items() if k in ("excitement", "calmness", "stress", "confidence")}
        self.state["emotion"] = emotion
        ok, packet, err = self.packet.Run("fromFeatures", {"text": text, "features": features, "emotion": emotion})
        if not ok:
            return (0, None, err)
        self.state["packet"] = packet
        return (1, packet, None)

    def AnalyzeArray(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        audio = params.get("audio")
        if audio is None:
            return (0, None, (1, "Missing audio", 0))
        sr = params.get("sampleRate", SAMPLE_RATE)
        text = params.get("text", "")
        engine = self.state["engine"]

        try:
            import soundfile as sf
            import tempfile
            tmp = tempfile.mktemp(suffix=".wav")
            sf.write(tmp, audio, sr)
            ok, _, err = engine.Run("load", {"path": tmp})
            os.unlink(tmp)
            if not ok:
                return (0, None, err)
        except Exception as e:
            return (0, None, (1, "Failed to write temp wav: " + str(e), 0))

        ok, features, err = engine.Run("analyze", None)
        if not ok:
            return (0, None, err)
        self.state["features"] = features
        emotion = {k: v for k, v in features.items() if k in ("excitement", "calmness", "stress", "confidence")}
        self.state["emotion"] = emotion
        ok, packet, err = self.packet.Run("fromFeatures", {"text": text, "features": features, "emotion": emotion})
        if not ok:
            return (0, None, err)
        self.state["packet"] = packet
        return (1, packet, None)

    def BuildPacket(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        features = params.get("features", self.state.get("features", {}))
        emotion = params.get("emotion", self.state.get("emotion", {}))
        ok, packet, err = self.packet.Run("fromFeatures", {"text": text, "features": features, "emotion": emotion})
        if not ok:
            return (0, None, err)
        self.state["packet"] = packet
        return (1, packet, None)

    def GetFeatures(self, params):
        return (1, {
            "features": self.state.get("features", {}),
            "emotion": self.state.get("emotion", {}),
            "packet": self.state.get("packet", {}),
        }, None)
