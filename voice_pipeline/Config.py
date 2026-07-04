#!/usr/bin/env python3
# [@GHOST]{[@file<Config.py>][@domain<voice_pipeline>][@role<config>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Tone-aware voice pipeline config — paths, model locations, emotion→voice map>]}
# [@VBSTYLE]{[@auth<devin>][@role<config>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Config — all paths, model locations, emotion→voice mapping, and tunable thresholds for the voice pipeline.}
# [@FILEID]{Config.py}
# [@CLASS]{Config}
# [@METHOD]{Load, Save, Defaults}

import os
import json

KOKORO_MODEL_FP16 = "/Users/wws/KokoroModels/onnx/model_fp16.onnx"
KOKORO_MODEL_Q8 = "/Users/wws/KokoroModels/onnx/model_quantized.onnx"
KOKORO_VOICES = "/Users/wws/KokoroModels/voices.npy"
KOKORO_SCRIPT = "/Users/wws/Downloads/VoiceTyper/Services/kokoro_tts.py"

VOICE_ENGINE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_engine.py")

SAMPLE_RATE = 22050
CHUNK_DURATION = 0.5
SILENCE_THRESHOLD = 0.02
MAX_RECORD_SECONDS = 30
MIN_SPEECH_SECONDS = 0.3

EMOTION_VOICE_MAP = {
    "excited": "af_sky",
    "happy": "af_bella",
    "calm": "af_heart",
    "confident": "am_michael",
    "serious": "am_onyx",
    "sad": "af_sarah",
    "angry": "am_adam",
    "neutral": "af_alloy",
    "teaching": "am_eric",
    "celebrating": "af_nova",
}

MACOS_SAY_VOICE_MAP = {
    "excited": "Samantha",
    "happy": "Samantha",
    "calm": "Samantha",
    "confident": "Alex",
    "serious": "Daniel",
    "sad": "Samantha",
    "angry": "Daniel",
    "neutral": "Samantha",
    "teaching": "Alex",
    "celebrating": "Samantha",
}

EDGE_TTS_VOICE_MAP = {
    "excited": "en-US-AriaNeural",
    "happy": "en-US-JennyNeural",
    "calm": "en-US-AriaNeural",
    "confident": "en-US-GuyNeural",
    "serious": "en-US-DavisNeural",
    "sad": "en-US-AriaNeural",
    "angry": "en-US-GuyNeural",
    "neutral": "en-US-AriaNeural",
    "teaching": "en-US-DavisNeural",
    "celebrating": "en-US-JennyNeural",
}

TTS_BACKEND_CHAIN = ["kokoro", "macos_say", "edge_tts"]

EMOTION_THRESHOLDS = {
    "excitement_high": 0.7,
    "excitement_low": 0.3,
    "stress_high": 0.6,
    "calmness_high": 0.7,
    "confidence_high": 0.7,
}

VAD_CONFIG = {
    "frame_ms": 20,
    "silence_ratio": 0.02,
    "hangover_frames": 8,
    "min_speech_frames": 6,
}

TONE_PACKET_FIELDS = [
    "text", "excitement", "happiness", "confidence", "stress",
    "calmness", "energy", "speaking_rate", "pitch_level",
    "pitch_variation", "volume", "emphasis", "mood",
    "prosody", "urgency", "engagement", "certainty",
    "analysis_confidence",
]

PIPELINE_DIR = os.path.dirname(__file__)
STATE_DIR = os.path.expanduser("~/.voice_pipeline")
RECORDINGS_DIR = os.path.join(STATE_DIR, "recordings")
PACKETS_DIR = os.path.join(STATE_DIR, "packets")
TTS_DIR = os.path.join(STATE_DIR, "tts_output")

for d in [STATE_DIR, RECORDINGS_DIR, PACKETS_DIR, TTS_DIR]:
    os.makedirs(d, exist_ok=True)


class Config:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "kokoro_model": KOKORO_MODEL_FP16,
            "kokoro_voices": KOKORO_VOICES,
            "sample_rate": SAMPLE_RATE,
            "emotion_voice_map": dict(EMOTION_VOICE_MAP),
            "thresholds": dict(EMOTION_THRESHOLDS),
            "vad": dict(VAD_CONFIG),
        }

    def _p(self, msg):
        import sys
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "load": self.Load,
            "save": self.Save,
            "defaults": self.Defaults,
            "set": self.Set,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Load(self, params):
        path = os.path.join(STATE_DIR, "config.json")
        if not os.path.exists(path):
            return (1, dict(self.state), None)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.state.update(data)
            return (1, dict(self.state), None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def Save(self, params):
        path = os.path.join(STATE_DIR, "config.json")
        try:
            with open(path, "w") as f:
                json.dump(self.state, f, indent=2)
            return (1, True, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def Defaults(self, params):
        self.state = {
            "kokoro_model": KOKORO_MODEL_FP16,
            "kokoro_voices": KOKORO_VOICES,
            "sample_rate": SAMPLE_RATE,
            "emotion_voice_map": dict(EMOTION_VOICE_MAP),
            "thresholds": dict(EMOTION_THRESHOLDS),
            "vad": dict(VAD_CONFIG),
        }
        return (1, dict(self.state), None)

    def Set(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        for k, v in params.items():
            self.state[k] = v
        return (1, dict(self.state), None)
