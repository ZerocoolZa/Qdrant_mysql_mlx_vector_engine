#!/usr/bin/env python3
# [@GHOST]{[@file<ToneSynthesizer.py>][@domain<voice_pipeline>][@role<synthesizer>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<TTS with emotion-voice mapping — Kokoro ONNX 82M FP16. Maps tone packet mood to voice, generates speech, plays it.>]}
# [@VBSTYLE]{[@auth<devin>][@role<synthesizer>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{ToneSynthesizer — Text-to-Speech with tone-matched voice selection. Uses Kokoro 82M FP16 ONNX. Maps VoicePacket mood (happy/sad/excited/calm/angry) to the best Kokoro voice. Generates WAV, optionally plays it.}
# [@FILEID]{ToneSynthesizer.py}
# [@CLASS]{ToneSynthesizer}
# [@METHOD]{Run, Speak, SpeakWithTone, Synthesize, Play, Stop, MapEmotionToVoice, ListVoices}

import sys
import os
import subprocess
import tempfile
import wave
import time

from Config import KOKORO_MODEL_FP16, KOKORO_SCRIPT, EMOTION_VOICE_MAP, TTS_DIR

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False


class ToneSynthesizer:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "modelPath": KOKORO_MODEL_FP16,
            "kokoroScript": KOKORO_SCRIPT,
            "emotionVoiceMap": dict(EMOTION_VOICE_MAP),
            "defaultVoice": "af_bella",
            "speed": 1.0,
            "lastWav": None,
            "playing": False,
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "speak": self.Speak,
            "speakWithTone": self.SpeakWithTone,
            "synthesize": self.Synthesize,
            "play": self.Play,
            "stop": self.Stop,
            "mapEmotionToVoice": self.MapEmotionToVoice,
            "listVoices": self.ListVoices,
            "setConfig": self.SetConfig,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Speak(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        if not text:
            return (0, None, (1, "Missing text", 0))
        voice = params.get("voice", self.state["defaultVoice"])
        play = params.get("play", True)
        return self._generate(text, voice, play)

    def SpeakWithTone(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        tone = params.get("tone", {})
        if not text:
            return (0, None, (1, "Missing text", 0))
        mood = tone.get("mood", "neutral")
        voice = self.MapEmotionToVoiceInternal(mood)
        play = params.get("play", True)
        speed = self._speedFromTone(tone)
        self.state["speed"] = speed
        ok, data, err = self._generate(text, voice, play)
        if not ok:
            return (0, None, err)
        data["mood"] = mood
        data["voice"] = voice
        data["speed"] = speed
        return (1, data, None)

    def Synthesize(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        if not text:
            return (0, None, (1, "Missing text", 0))
        voice = params.get("voice", self.state["defaultVoice"])
        return self._generate(text, voice, False)

    def Play(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        path = params.get("path", self.state.get("lastWav"))
        if not path or not os.path.exists(path):
            return (0, None, (1, "No audio file to play", 0))
        return self._play_wav(path)

    def Stop(self, params):
        self.state["playing"] = False
        try:
            if HAS_SD:
                sd.stop()
        except Exception:
            pass
        return (1, True, None)

    def MapEmotionToVoice(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        emotion = params.get("emotion", "neutral")
        voice = self.MapEmotionToVoiceInternal(emotion)
        return (1, {"emotion": emotion, "voice": voice}, None)

    def MapEmotionToVoiceInternal(self, emotion):
        voiceMap = self.state["emotionVoiceMap"]
        return voiceMap.get(emotion, voiceMap.get("neutral", self.state["defaultVoice"]))

    def ListVoices(self, params):
        return (1, {"voices": list(self.state["emotionVoiceMap"].keys())}, None)

    def SetConfig(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        for k, v in params.items():
            if k in self.state:
                self.state[k] = v
        return (1, dict(self.state), None)

    def _speedFromTone(self, tone):
        excitement = tone.get("excitement", 0.5)
        urgency = tone.get("urgency", 0.5)
        if urgency > 0.7 or excitement > 0.7:
            return 1.15
        if excitement < 0.2:
            return 0.9
        return 1.0

    def _generate(self, text, voice, play):
        ts = time.strftime("%Y%m%d_%H%M%S")
        outPath = os.path.join(TTS_DIR, "tts_%s.wav" % ts)
        try:
            cmd = [sys.executable, self.state["kokoroScript"], text, voice, outPath]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return (0, None, (1, "Kokoro failed: " + proc.stderr[:300], 0))
            self.state["lastWav"] = outPath
            result = {"path": outPath, "voice": voice, "text": text}
            if play:
                self._play_wav(outPath)
            return (1, result, None)
        except subprocess.TimeoutExpired:
            return (0, None, (1, "Kokoro timed out", 0))
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def _play_wav(self, path):
        if not HAS_SD or not HAS_SF:
            try:
                subprocess.run(["afplay", path], timeout=30)
            except Exception:
                pass
            return (1, {"played": True, "method": "afplay"}, None)
        try:
            data, sr = sf.read(path)
            if data.ndim > 1:
                data = data[:, 0]
            self.state["playing"] = True
            sd.play(data, sr)
            sd.wait()
            self.state["playing"] = False
            return (1, {"played": True, "method": "sounddevice", "duration": len(data) / sr}, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))
