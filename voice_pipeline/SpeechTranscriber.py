#!/usr/bin/env python3
# [@GHOST]{[@file<SpeechTranscriber.py>][@domain<voice_pipeline>][@role<transcriber>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<STT — converts audio to text. Uses macOS SFSpeechRecognizer via Swift bridge, falls back to whisper if available.>]}
# [@VBSTYLE]{[@auth<devin>][@role<transcriber>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{SpeechTranscriber — Speech-to-Text. Primary: macOS SFSpeechRecognizer (fast, on-device, no model download). Fallback: openai-whisper if installed. Input: WAV file. Output: transcript text.}
# [@FILEID]{SpeechTranscriber.py}
# [@CLASS]{SpeechTranscriber}
# [@METHOD]{Run, Transcribe, TranscribeFile, TranscribeArray, SetConfig, ListBackends}

import sys
import os
import subprocess
import tempfile
import wave
import numpy as np

from Config import SAMPLE_RATE

SWIFT_STT_SCRIPT = """
import Speech
import Foundation

let audioPath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: audioPath)

let sem = DispatchSemaphore(value: 0)
var resultText = ""
var errorMsg = ""

SFSpeechRecognizer.requestAuthorization { status in
    if status != .authorized {
        errorMsg = "Speech recognition not authorized"
        sem.signal()
        return
    }

    guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")) else {
        errorMsg = "Speech recognizer not available for en-US"
        sem.signal()
        return
    }

    let request = SFSpeechURLRecognitionRequest(url: url)
    request.shouldReportPartialResults = false

    recognizer.recognitionTask(with: request) { result, error in
        if let error = error {
            errorMsg = error.localizedDescription
            sem.signal()
            return
        }
        if let result = result, result.isFinal {
            resultText = result.bestTranscription.formattedString
            sem.signal()
        }
    }
}

sem.wait()

if !errorMsg.isEmpty {
    FileHandle.standardError.write(errorMsg.data(using: .utf8)!)
    exit(1)
}
print(resultText)
"""


class SpeechTranscriber:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "backend": "macos_sfspeech",
            "whisperModel": "base.en",
            "lastTranscript": "",
            "swiftScriptPath": None,
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "transcribe": self.Transcribe,
            "transcribeFile": self.TranscribeFile,
            "transcribeArray": self.TranscribeArray,
            "setConfig": self.SetConfig,
            "listBackends": self.ListBackends,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Transcribe(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        path = params.get("path")
        if path:
            return self.TranscribeFile(params)
        audio = params.get("audio")
        if audio is not None:
            return self.TranscribeArray(params)
        return (0, None, (1, "Need path or audio", 0))

    def TranscribeFile(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        path = params.get("path")
        if path is None:
            return (0, None, (1, "Missing path", 0))
        backend = params.get("backend", self.state["backend"])

        if backend == "macos_sfspeech":
            return self._transcribe_swift(path)
        elif backend == "whisper":
            return self._transcribe_whisper(path)
        else:
            return (0, None, (1, "Unknown backend: " + str(backend), 0))

    def TranscribeArray(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        audio = params.get("audio")
        if audio is None:
            return (0, None, (1, "Missing audio", 0))
        sr = params.get("sampleRate", SAMPLE_RATE)
        try:
            tmp = tempfile.mktemp(suffix=".wav")
            audioInt16 = (audio * 32767).astype(np.int16)
            with wave.open(tmp, "w") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(audioInt16.tobytes())
            result = self.TranscribeFile({"path": tmp, "backend": params.get("backend", self.state["backend"])})
            os.unlink(tmp)
            return result
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def _transcribe_swift(self, wav_path):
        scriptPath = self.state.get("swiftScriptPath")
        if not scriptPath or not os.path.exists(scriptPath):
            scriptPath = os.path.join(tempfile.gettempdir(), "voice_pipeline_stt.swift")
            with open(scriptPath, "w") as f:
                f.write(SWIFT_STT_SCRIPT)
            self.state["swiftScriptPath"] = scriptPath

        try:
            proc = subprocess.run(
                ["swift", scriptPath, wav_path],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode != 0:
                return (0, None, (1, "SFSpeechRecognizer failed: " + proc.stderr.strip()[:200], 0))
            transcript = proc.stdout.strip()
            self.state["lastTranscript"] = transcript
            return (1, {"text": transcript, "backend": "macos_sfspeech"}, None)
        except subprocess.TimeoutExpired:
            return (0, None, (1, "SFSpeechRecognizer timed out", 0))
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def _transcribe_whisper(self, wav_path):
        try:
            import whisper
            model = whisper.load_model(self.state["whisperModel"])
            result = model.transcribe(wav_path)
            transcript = result.get("text", "").strip()
            self.state["lastTranscript"] = transcript
            return (1, {"text": transcript, "backend": "whisper", "model": self.state["whisperModel"]}, None)
        except ImportError:
            return (0, None, (1, "openai-whisper not installed. Run: pip install openai-whisper", 0))
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def SetConfig(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        for k, v in params.items():
            if k in self.state:
                self.state[k] = v
        return (1, dict(self.state), None)

    def ListBackends(self, params):
        backends = ["macos_sfspeech"]
        try:
            import whisper
            backends.append("whisper")
        except ImportError:
            pass
        return (1, {"backends": backends, "current": self.state["backend"]}, None)
