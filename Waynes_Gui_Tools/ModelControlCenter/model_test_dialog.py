#!/usr/bin/env python3
# [@GHOST]{[@file<model_test_dialog.py>][@domain<ModelControlCenter>][@role<test_dialog>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<TTS model test dialog — type text, pick voice, make model speak. Chat-style test for any TTS model.>]}
# [@VBSTYLE]{[@auth<devin>][@role<test_dialog>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{ModelTestDialog — PyQt6 dialog for testing TTS models. Type text, pick voice, adjust speed, click Speak. Plays the generated audio. Supports Kokoro ONNX, macOS say, and edge-tts. Chat-style history.}
# [@FILEID]{model_test_dialog.py}
# [@CLASS]{ModelTestDialog, TTSSynthThread, AudioPlayThread}
# [@METHOD]{Run, Speak, Stop, PopulateVoices, AddHistory, OnSynthDone, OnPlayDone, Close}

import os
import sys
import subprocess
import tempfile
import wave
import time

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QTextEdit, QGroupBox,
    QProgressBar, QCheckBox, QMessageBox, QSplitter, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

KOKORO_MODEL_FP16 = "/Users/wws/KokoroModels/onnx/model_fp16.onnx"
KOKORO_MODEL_Q8 = "/Users/wws/KokoroModels/onnx/model_quantized.onnx"
KOKORO_VOICES = "/Users/wws/KokoroModels/voices.npy"
KOKORO_SCRIPT = "/Users/wws/Downloads/VoiceTyper/Services/kokoro_tts.py"

KOKORO_VOICES_LIST = [
    "af", "af_alloy", "af_aoede", "af_bella", "af_heart",
    "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george",
]

MACOS_SAY_VOICES = [
    "Samantha", "Alex", "Daniel", "Karen", "Moira", "Tessa",
    "Fiona", "Veena", "Allison", "Ava", "Evan", "Nicky",
    "Zoe", "Rishi", "Sara", "Anna", "Helena", "Thomas",
]

QUICK_TEST_PHRASES = [
    "Hello, this is a test of the voice system.",
    "The system is currently running and operational.",
    "Amazing! We found the root cause of the problem!",
    "Warning. Three critical issues detected.",
    "This is important. The database must never be modified without authorization.",
    "Done. All tests passed. The enforcement layer is fully operational.",
    "Here is how the architecture works. The domain must exist first.",
    "Perfect! All tests passed. The system is complete.",
]


class TTSSynthThread(QThread):
    """Background thread — synthesizes TTS audio via the selected backend."""
    finished_synth = pyqtSignal(bool, str, str)  # success, wav_path, message
    progress = pyqtSignal(int)

    def __init__(self, text, backend, voice, speed, model_path=None):
        super().__init__()
        self.text = text
        self.backend = backend
        self.voice = voice
        self.speed = speed
        self.model_path = model_path
        self.cancelled = False

    def run(self):
        try:
            self.progress.emit(10)
            if self.backend == "kokoro":
                wav_path = self._synth_kokoro()
            elif self.backend == "macos_say":
                wav_path = self._synth_macos_say()
            elif self.backend == "edge_tts":
                wav_path = self._synth_edge_tts()
            else:
                self.finished_synth.emit(False, "", "Unknown backend: " + str(self.backend))
                return
            self.progress.emit(90)
            if wav_path and os.path.exists(wav_path):
                self.finished_synth.emit(True, wav_path, "OK")
            else:
                self.finished_synth.emit(False, "", "No audio file produced")
        except Exception as e:
            self.finished_synth.emit(False, "", str(e))

    def _synth_kokoro(self):
        tmp_wav = tempfile.mktemp(suffix=".wav", prefix="tts_test_")
        cmd = [
            sys.executable, KOKORO_SCRIPT,
            self.text, self.voice, tmp_wav
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError("Kokoro failed: " + proc.stderr[:300])
        return tmp_wav

    def _synth_macos_say(self):
        tmp_aiff = tempfile.mktemp(suffix=".aiff", prefix="tts_say_")
        tmp_wav = tempfile.mktemp(suffix=".wav", prefix="tts_say_")
        cmd = ["say", "-v", self.voice, "-o", tmp_aiff, self.text]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError("say failed: " + proc.stderr[:300])
        conv = subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", tmp_aiff, tmp_wav],
            capture_output=True, text=True, timeout=30
        )
        if conv.returncode != 0:
            return tmp_aiff
        return tmp_wav

    def _synth_edge_tts(self):
        tmp_mp3 = tempfile.mktemp(suffix=".mp3", prefix="tts_edge_")
        tmp_wav = tempfile.mktemp(suffix=".wav", prefix="tts_edge_")
        import edge_tts
        communicate = edge_tts.Communicate(self.text, self.voice)
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(communicate.save(tmp_mp3))
        loop.close()
        try:
            import soundfile as sf
            data, sr = sf.read(tmp_mp3)
            sf.write(tmp_wav, data, sr)
            return tmp_wav
        except Exception:
            return tmp_mp3


class AudioPlayThread(QThread):
    """Background thread — plays a WAV file via sounddevice."""
    play_done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, wav_path):
        super().__init__()
        self.wav_path = wav_path
        self.cancelled = False

    def run(self):
        try:
            import soundfile as sf
            import sounddevice as sd
            data, sr = sf.read(self.wav_path)
            if data.ndim > 1:
                data = data[:, 0]
            sd.play(data, sr)
            sd.wait()
            self.play_done.emit()
        except Exception as e:
            self.error.emit(str(e))


class ModelTestDialog(QDialog):
    """Test TTS models — type text, pick voice, click Speak. Chat-style history."""

    def __init__(self, parent=None, model_id=None, model_info=None):
        super().__init__(parent)
        self.setWindowTitle("Test Model — Say Something")
        self.resize(700, 600)
        self.model_id = model_id
        self.model_info = model_info or {}
        self.synth_thread = None
        self.play_thread = None
        self.last_wav = None
        self.history = []
        self.build_ui()
        self.populate_voices()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Test Model: " + self.model_info.get("name", self.model_id or "Unknown"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        if self.model_info.get("description"):
            desc = QLabel(self.model_info["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #a6adc8; font-size: 12px;")
            layout.addWidget(desc)

        config_group = QGroupBox("Voice Settings")
        config_layout = QHBoxLayout(config_group)
        config_layout.setContentsMargins(8, 16, 8, 8)

        config_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["kokoro", "macos_say", "edge_tts"])
        self.backend_combo.currentTextChanged.connect(self.on_backend_changed)
        config_layout.addWidget(self.backend_combo)

        config_layout.addWidget(QLabel("Voice:"))
        self.voice_combo = QComboBox()
        self.voice_combo.setEditable(True)
        config_layout.addWidget(self.voice_combo, 1)

        config_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_label = QLabel("1.0x")
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        config_layout.addWidget(self.speed_slider)
        config_layout.addWidget(self.speed_label)

        layout.addWidget(config_group)

        text_group = QGroupBox("Text to Speak")
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(8, 16, 8, 8)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type something for the model to say...")
        self.text_input.returnPressed.connect(self.on_speak)
        text_layout.addWidget(self.text_input)

        quick_row = QHBoxLayout()
        quick_lbl = QLabel("Quick test:")
        self.quick_combo = QComboBox()
        self.quick_combo.addItems(["(pick a phrase)"] + QUICK_TEST_PHRASES)
        self.quick_combo.currentTextChanged.connect(self.on_quick_pick)
        quick_row.addWidget(quick_lbl)
        quick_row.addWidget(self.quick_combo, 1)
        text_layout.addLayout(quick_row)

        layout.addWidget(text_group)

        btn_row = QHBoxLayout()
        self.btn_speak = QPushButton("Speak")
        self.btn_speak.setStyleSheet("background-color: #89b4fa; font-weight: bold; padding: 8px 20px;")
        self.btn_speak.clicked.connect(self.on_speak)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.on_stop)

        self.btn_replay = QPushButton("Replay Last")
        self.btn_replay.setEnabled(False)
        self.btn_replay.clicked.connect(self.on_replay)

        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.clicked.connect(self.on_clear)

        btn_row.addWidget(self.btn_speak)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_replay)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        layout.addWidget(self.progress_bar)

        history_group = QGroupBox("History")
        history_layout = QVBoxLayout(history_group)
        history_layout.setContentsMargins(8, 16, 8, 8)
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setStyleSheet("font-family: monospace; font-size: 12px;")
        history_layout.addWidget(self.history_text)
        layout.addWidget(history_group, 1)

        info_row = QHBoxLayout()
        self.info_label = QLabel("Ready")
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        info_row.addWidget(self.info_label)
        info_row.addStretch()
        self.wav_label = QLabel("")
        self.wav_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        info_row.addWidget(self.wav_label)
        layout.addLayout(info_row)

    def populate_voices(self):
        self.voice_combo.clear()
        backend = self.backend_combo.currentText()
        if backend == "kokoro":
            self.voice_combo.addItems(KOKORO_VOICES_LIST)
            self.voice_combo.setCurrentText("af_bella")
        elif backend == "macos_say":
            self.voice_combo.addItems(MACOS_SAY_VOICES)
            self.voice_combo.setCurrentText("Samantha")
        elif backend == "edge_tts":
            self.voice_combo.addItems([
                "en-US-AriaNeural", "en-US-GuyNeural", "en-US-JennyNeural",
                "en-US-DavisNeural", "en-US-AmberNeural", "en-GB-SoniaNeural",
                "en-AU-NatashaNeural", "en-AU-WilliamNeural",
            ])
            self.voice_combo.setCurrentText("en-US-AriaNeural")

    def on_backend_changed(self):
        self.populate_voices()

    def on_speed_changed(self, value):
        self.speed_label.setText("%.1fx" % (value / 100.0))

    def on_quick_pick(self, text):
        if text and text != "(pick a phrase)":
            self.text_input.setText(text)

    def on_speak(self):
        text = self.text_input.text().strip()
        if not text:
            self.info_label.setText("Type something to say first")
            return
        backend = self.backend_combo.currentText()
        voice = self.voice_combo.currentText()
        speed = self.speed_slider.value() / 100.0

        self.btn_speak.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.info_label.setText("Synthesizing with %s (%s)..." % (backend, voice))

        self.synth_thread = TTSSynthThread(text, backend, voice, speed)
        self.synth_thread.finished_synth.connect(self.on_synth_done)
        self.synth_thread.progress.connect(self.progress_bar.setValue)
        self.synth_thread.start()

    def on_synth_done(self, success, wav_path, message):
        self.progress_bar.setVisible(False)
        self.btn_speak.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not success:
            self.info_label.setText("Error: " + message)
            self.add_history("ERROR", self.text_input.text(), message)
            return
        self.last_wav = wav_path
        self.wav_label.setText("WAV: " + os.path.basename(wav_path))
        self.btn_replay.setEnabled(True)
        self.info_label.setText("Playing audio...")
        self.add_history("SPOKE", self.text_input.text(), wav_path)
        self.play_audio(wav_path)

    def play_audio(self, wav_path):
        self.play_thread = AudioPlayThread(wav_path)
        self.play_thread.play_done.connect(self.on_play_done)
        self.play_thread.error.connect(self.on_play_error)
        self.play_thread.start()

    def on_play_done(self):
        self.info_label.setText("Ready")

    def on_play_error(self, msg):
        self.info_label.setText("Playback error: " + msg + " (file saved at " + str(self.last_wav) + ")")

    def on_stop(self):
        if self.synth_thread and self.synth_thread.isRunning():
            self.synth_thread.cancelled = True
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self.progress_bar.setVisible(False)
        self.btn_speak.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.info_label.setText("Stopped")

    def on_replay(self):
        if self.last_wav and os.path.exists(self.last_wav):
            self.info_label.setText("Replaying...")
            self.play_audio(self.last_wav)

    def on_clear(self):
        self.history = []
        self.history_text.clear()

    def add_history(self, tag, text, detail):
        ts = time.strftime("%H:%M:%S")
        line = "[%s] %s: %s\n  -> %s\n\n" % (ts, tag, text[:100], os.path.basename(detail) if detail else "")
        self.history.append(line)
        self.history_text.append(line.rstrip())

    def closeEvent(self, event):
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        super().closeEvent(event)
