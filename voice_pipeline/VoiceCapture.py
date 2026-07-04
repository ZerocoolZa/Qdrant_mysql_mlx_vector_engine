#!/usr/bin/env python3
# [@GHOST]{[@file<VoiceCapture.py>][@domain<voice_pipeline>][@role<capture>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<Mic recording with VAD — captures speech, stops on silence, returns audio array>]}
# [@VBSTYLE]{[@auth<devin>][@role<capture>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{VoiceCapture — microphone recording with Voice Activity Detection. Records until silence detected or max duration reached. Returns numpy audio array. Uses sounddevice for mic access.}
# [@FILEID]{VoiceCapture.py}
# [@CLASS]{VoiceCapture}
# [@METHOD]{Run, Record, RecordDuration, Stop, GetLevel, SaveWav}

import sys
import os
import wave
import time
import numpy as np

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

from Config import SAMPLE_RATE, SILENCE_THRESHOLD, MAX_RECORD_SECONDS, MIN_SPEECH_SECONDS, VAD_CONFIG, RECORDINGS_DIR


class VoiceCapture:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "sampleRate": SAMPLE_RATE,
            "recording": False,
            "audio": None,
            "duration": 0,
            "lastLevel": 0.0,
            "silenceThreshold": SILENCE_THRESHOLD,
            "maxDuration": MAX_RECORD_SECONDS,
            "minSpeech": MIN_SPEECH_SECONDS,
            "vad": dict(VAD_CONFIG),
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "record": self.Record,
            "recordDuration": self.RecordDuration,
            "stop": self.Stop,
            "getLevel": self.GetLevel,
            "saveWav": self.SaveWav,
            "setConfig": self.SetConfig,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Record(self, params):
        if not HAS_SD:
            return (0, None, (1, "sounddevice not available", 0))
        if params:
            maxDur = params.get("maxDuration", self.state["maxDuration"])
            threshold = params.get("threshold", self.state["silenceThreshold"])
        else:
            maxDur = self.state["maxDuration"]
            threshold = self.state["silenceThreshold"]

        sr = self.state["sampleRate"]
        frameMs = self.state["vad"]["frame_ms"]
        hangover = self.state["vad"]["hangover_frames"]
        minSpeechFrames = self.state["vad"]["min_speech_frames"]

        frameSize = int(sr * frameMs / 1000)
        self.state["recording"] = True

        audioChunks = []
        silenceCount = 0
        speechCount = 0
        totalFrames = 0
        started = False

        def callback(indata, frames, time_info, status):
            if status:
                self._p("SD status: " + str(status))

        try:
            with sd.InputStream(samplerate=sr, channels=1, dtype=np.float32,
                                blocksize=frameSize, callback=None) as stream:
                while self.state["recording"] and totalFrames < (maxDur * 1000 / frameMs):
                    data, overflowed = stream.read(frameSize)
                    if data.ndim > 1:
                        data = data[:, 0]
                    level = float(np.sqrt(np.mean(data ** 2)))
                    self.state["lastLevel"] = level

                    if level > threshold:
                        speechCount += 1
                        silenceCount = 0
                        if speechCount >= minSpeechFrames:
                            started = True
                    else:
                        if started:
                            silenceCount += 1

                    audioChunks.append(data.copy())
                    totalFrames += 1

                    if started and silenceCount >= hangover:
                        break

            if not audioChunks:
                return (0, None, (1, "No audio captured", 0))

            audio = np.concatenate(audioChunks)
            self.state["audio"] = audio
            self.state["duration"] = len(audio) / sr
            self.state["recording"] = False

            if self.state["duration"] < self.state["minSpeech"]:
                return (0, None, (1, "Speech too short (%.2fs < %.2fs)" % (self.state["duration"], self.state["minSpeech"]), 0))

            return (1, {
                "audio": audio,
                "sampleRate": sr,
                "duration": self.state["duration"],
                "frames": len(audio),
            }, None)
        except Exception as e:
            self.state["recording"] = False
            return (0, None, (1, str(e), 0))

    def RecordDuration(self, params):
        if not HAS_SD:
            return (0, None, (1, "sounddevice not available", 0))
        if params is None:
            return (0, None, (1, "Missing params", 0))
        duration = params.get("duration", 3.0)
        sr = self.state["sampleRate"]

        try:
            totalSamples = int(duration * sr)
            self.state["recording"] = True
            audio = sd.rec(totalSamples, samplerate=sr, channels=1, dtype=np.float32)
            sd.wait()
            self.state["recording"] = False
            if audio.ndim > 1:
                audio = audio[:, 0]
            self.state["audio"] = audio
            self.state["duration"] = len(audio) / sr
            return (1, {
                "audio": audio,
                "sampleRate": sr,
                "duration": self.state["duration"],
                "frames": len(audio),
            }, None)
        except Exception as e:
            self.state["recording"] = False
            return (0, None, (1, str(e), 0))

    def Stop(self, params):
        self.state["recording"] = False
        try:
            if HAS_SD:
                sd.stop()
        except Exception:
            pass
        return (1, True, None)

    def GetLevel(self, params):
        return (1, {"level": self.state.get("lastLevel", 0.0)}, None)

    def SaveWav(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        audio = params.get("audio", self.state.get("audio"))
        if audio is None:
            return (0, None, (1, "No audio to save", 0))
        path = params.get("path")
        if path is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(RECORDINGS_DIR, "recording_%s.wav" % ts)
        sr = params.get("sampleRate", self.state["sampleRate"])
        try:
            audioInt16 = (audio * 32767).astype(np.int16)
            with wave.open(path, "w") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(audioInt16.tobytes())
            return (1, {"path": path, "size": os.path.getsize(path)}, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def SetConfig(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        for k, v in params.items():
            if k in self.state:
                self.state[k] = v
        return (1, dict(self.state), None)
