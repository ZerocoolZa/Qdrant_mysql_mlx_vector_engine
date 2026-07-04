#!/usr/bin/env python3
# [@GHOST]{[@file<PasteHear.py>][@domain<utility>][@role<tts_gui>][@auth<cascade>][@date<2026-07-02>][@ver<3.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<tts_gui>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{PasteHear — PyQt6 GUI for pasting text and hearing it spoken. Uses edge-tts (Azure Neural) with speech chunking, pause injection, and prosody variation for natural speech. macOS say as fallback.}
# [@CLASS]{PasteHear}
# [@METHOD]{__init__,build_ui,on_speak,on_stop,on_clear,on_voice_change,on_rate_change,on_pitch_change,on_engine_change,populate_voices,get_macos_voices,split_into_speech_chunks,compute_chunk_prosody}

import sys
import os
import re
import subprocess
import asyncio
import tempfile
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QComboBox, QSlider, QLabel, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    pass


class NeuralSpeakThread(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, voice, chunks, base_rate, base_pitch):
        super().__init__()
        self.voice = voice
        self.chunks = chunks
        self.base_rate = base_rate
        self.base_pitch = base_pitch
        self.cancelled = False
        self.proc = None

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            total = len(self.chunks)
            for i, chunk in enumerate(self.chunks):
                if self.cancelled:
                    break
                chunk_text, pause_ms, rate_adj, pitch_adj = chunk
                if not chunk_text.strip():
                    if pause_ms > 0:
                        time.sleep(pause_ms / 1000.0)
                    continue
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp_path = tmp.name
                tmp.close()
                rate_str = "%+d%%" % (self.base_rate + rate_adj)
                pitch_str = "%+dHz" % (self.base_pitch + pitch_adj)
                comm = edge_tts.Communicate(chunk_text, self.voice, rate=rate_str, pitch=pitch_str)
                loop.run_until_complete(comm.save(tmp_path))
                if self.cancelled:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    break
                self.proc = subprocess.Popen(["/usr/bin/afplay", tmp_path])
                self.proc.wait()
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                self.progress.emit(i + 1, total)
                if self.cancelled:
                    break
                if pause_ms > 0 and i < total - 1:
                    time.sleep(pause_ms / 1000.0)
            loop.close()
            if self.cancelled:
                self.finished.emit("cancelled")
            else:
                self.finished.emit("done")
        except Exception as e:
            self.finished.emit("error: %s" % str(e))

    def cancel(self):
        self.cancelled = True
        if self.proc:
            self.proc.kill()


class MacSpeakThread(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, voice, chunks, base_rate):
        super().__init__()
        self.voice = voice
        self.chunks = chunks
        self.base_rate = base_rate
        self.proc = None
        self.cancelled = False

    def run(self):
        try:
            total = len(self.chunks)
            for i, chunk in enumerate(self.chunks):
                if self.cancelled:
                    break
                chunk_text, pause_ms, rate_adj, _ = chunk
                if not chunk_text.strip():
                    if pause_ms > 0:
                        time.sleep(pause_ms / 1000.0)
                    continue
                chunk_rate = self.base_rate + int(rate_adj * 0.5)
                cmd = ["/usr/bin/say", "-v", self.voice, "-r", str(chunk_rate), chunk_text]
                self.proc = subprocess.Popen(cmd)
                self.proc.wait()
                self.progress.emit(i + 1, total)
                if self.cancelled:
                    break
                if pause_ms > 0 and i < total - 1:
                    time.sleep(pause_ms / 1000.0)
            if self.cancelled:
                self.finished.emit("cancelled")
            else:
                self.finished.emit("done")
        except Exception as e:
            self.finished.emit("error: %s" % str(e))

    def cancel(self):
        self.cancelled = True
        if self.proc:
            self.proc.kill()


NEURAL_VOICES = [
    ("Ava (Natural, Female)", "en-US-AvaNeural"),
    ("Andrew (Natural, Male)", "en-US-AndrewNeural"),
    ("Emma (Natural, Female)", "en-US-EmmaNeural"),
    ("Brian (Natural, Male)", "en-US-BrianNeural"),
    ("Aria (Confident, Female)", "en-US-AriaNeural"),
    ("Jenny (Friendly, Female)", "en-US-JennyNeural"),
    ("Christopher (Authoritative, Male)", "en-US-ChristopherNeural"),
    ("Michelle (Pleasant, Female)", "en-US-MichelleNeural"),
    ("Eric (Rational, Male)", "en-US-EricNeural"),
    ("Guy (Passionate, Male)", "en-US-GuyNeural"),
    ("Roger (Lively, Male)", "en-US-RogerNeural"),
    ("Steffan (Rational, Male)", "en-US-SteffanNeural"),
    ("Ana (Cute, Female)", "en-US-AnaNeural"),
]


class PasteHear(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paste & Hear — Neural TTS")
        self.resize(750, 550)
        self.speak_thread = None
        self.current_engine = "neural" if EDGE_TTS_AVAILABLE else "macos"
        self.neural_rate = 0
        self.neural_pitch = 0
        self.macos_rate = 180
        self.build_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()

        engine_label = QLabel("Engine:")
        toolbar.addWidget(engine_label)

        self.engine_combo = QComboBox()
        if EDGE_TTS_AVAILABLE:
            self.engine_combo.addItem("Neural (ChatGPT quality)")
        self.engine_combo.addItem("macOS Voices")
        self.engine_combo.currentIndexChanged.connect(self.on_engine_change)
        toolbar.addWidget(self.engine_combo)

        toolbar.addSpacing(15)

        toolbar.addWidget(QLabel("Voice:"))
        self.voice_combo = QComboBox()
        self.populate_voices()
        self.voice_combo.currentTextChanged.connect(self.on_voice_change)
        toolbar.addWidget(self.voice_combo)

        toolbar.addSpacing(15)

        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(-50, 50)
        self.rate_slider.setValue(0)
        self.rate_slider.valueChanged.connect(self.on_rate_change)
        self.rate_label = QLabel("0%")
        toolbar.addWidget(QLabel("Rate:"))
        toolbar.addWidget(self.rate_slider)
        toolbar.addWidget(self.rate_label)

        toolbar.addSpacing(10)

        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-20, 20)
        self.pitch_slider.setValue(0)
        self.pitch_slider.valueChanged.connect(self.on_pitch_change)
        self.pitch_label = QLabel("0Hz")
        toolbar.addWidget(QLabel("Pitch:"))
        toolbar.addWidget(self.pitch_slider)
        toolbar.addWidget(self.pitch_label)

        toolbar.addStretch()

        self.btn_speak = QPushButton("Hear It")
        self.btn_speak.setFixedSize(120, 40)
        self.btn_speak.setStyleSheet("QPushButton { background-color: #2D7DD2; color: white; font-size: 16px; font-weight: bold; border-radius: 6px; }"
                                     "QPushButton:hover { background-color: #1A5FA8; }"
                                     "QPushButton:disabled { background-color: #555; }")
        self.btn_speak.clicked.connect(self.on_speak)
        toolbar.addWidget(self.btn_speak)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedSize(80, 40)
        self.btn_stop.setStyleSheet("QPushButton { background-color: #E74C3C; color: white; font-size: 14px; font-weight: bold; border-radius: 6px; }"
                                    "QPushButton:hover { background-color: #C0392B; }")
        self.btn_stop.clicked.connect(self.on_stop)
        toolbar.addWidget(self.btn_stop)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedSize(80, 40)
        self.btn_clear.clicked.connect(self.on_clear)
        toolbar.addWidget(self.btn_clear)

        layout.addLayout(toolbar)

        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Paste text here, then click Hear It...")
        self.text_area.setStyleSheet("QTextEdit { font-size: 15px; padding: 10px; }")
        layout.addWidget(self.text_area)

        hint = QLabel("Neural engine uses Microsoft Azure Neural TTS (same quality as ChatGPT voice). Requires internet.")
        hint.setStyleSheet("QLabel { color: #888; font-size: 11px; padding: 4px; }")
        layout.addWidget(hint)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        if EDGE_TTS_AVAILABLE:
            self.status.showMessage("Ready — Neural engine active (ChatGPT quality)")
        else:
            self.status.showMessage("Ready — edge-tts not installed, using macOS voices. Run: pip3 install edge-tts")

    def on_speak(self):
        text = self.text_area.toPlainText().strip()
        if not text:
            self.status.showMessage("Nothing to speak — paste text first")
            return
        self.btn_speak.setEnabled(False)
        chunks = self.split_into_speech_chunks(text)
        if not chunks:
            self.status.showMessage("No speakable text found")
            self.btn_speak.setEnabled(True)
            return
        self.status.showMessage("Speaking... (%d chunks)" % len(chunks))
        if self.current_engine == "neural":
            voice_id = self.voice_combo.currentData()
            self.speak_thread = NeuralSpeakThread(voice_id, chunks, self.neural_rate, self.neural_pitch)
        else:
            voice_name = self.voice_combo.currentText()
            if voice_name.startswith("---"):
                self.status.showMessage("Select a voice first")
                self.btn_speak.setEnabled(True)
                return
            self.speak_thread = MacSpeakThread(voice_name, chunks, self.macos_rate)
        self.speak_thread.finished.connect(self.on_speak_done)
        self.speak_thread.progress.connect(self.on_speak_progress)
        self.speak_thread.start()

    def on_speak_progress(self, current, total):
        self.status.showMessage("Speaking... chunk %d of %d" % (current, total))

    def on_speak_done(self, result):
        self.btn_speak.setEnabled(True)
        if result == "done":
            self.status.showMessage("Done")
        elif result == "cancelled":
            self.status.showMessage("Stopped")
        else:
            self.status.showMessage(result)

    def on_stop(self):
        if self.speak_thread and hasattr(self.speak_thread, "cancel"):
            self.speak_thread.cancel()
        self.status.showMessage("Stopped")

    def on_clear(self):
        self.text_area.clear()
        self.status.showMessage("Cleared")

    def populate_voices(self):
        self.voice_combo.clear()
        if self.current_engine == "neural":
            for label, voice_id in NEURAL_VOICES:
                self.voice_combo.addItem(label, userData=voice_id)
        else:
            advanced = self.get_macos_voices()
            if advanced:
                for group_label, voices in advanced:
                    self.voice_combo.addItem(group_label)
                    item = self.voice_combo.model().item(self.voice_combo.count() - 1)
                    item.setEnabled(False)
                    for v in voices:
                        self.voice_combo.addItem(v)
                preferred = "Ava (Premium)"
                idx = self.voice_combo.findText(preferred)
                if idx >= 0:
                    self.voice_combo.setCurrentIndex(idx)
            else:
                self.voice_combo.addItem("Samantha (Enhanced)")

    def on_engine_change(self, idx):
        if EDGE_TTS_AVAILABLE:
            self.current_engine = "neural" if idx == 0 else "macos"
        else:
            self.current_engine = "macos"
        if self.current_engine == "neural":
            self.rate_slider.setRange(-50, 50)
            self.rate_slider.setValue(0)
            self.rate_label.setText("0%")
            self.pitch_slider.setEnabled(True)
            self.pitch_label.setEnabled(True)
        else:
            self.rate_slider.setRange(80, 400)
            self.rate_slider.setValue(180)
            self.rate_label.setText("180 wpm")
            self.pitch_slider.setEnabled(False)
            self.pitch_label.setEnabled(False)
        self.populate_voices()
        engine_name = "Neural" if self.current_engine == "neural" else "macOS"
        self.status.showMessage("Engine: %s — %s" % (engine_name, self.voice_combo.currentText()))

    def get_macos_voices(self):
        try:
            proc = subprocess.run(
                ["/usr/bin/say", "-v", "?"],
                capture_output=True, text=True, timeout=5
            )
        except Exception:
            return [("--- Premium ---", ["Ava (Premium)", "Zoe (Premium)"]),
                    ("--- Enhanced ---", ["Samantha (Enhanced)", "Tom (Enhanced)", "Evan (Enhanced)",
                                   "Nathan (Enhanced)", "Susan (Enhanced)"])]
        premium = []
        enhanced = []
        for line in proc.stdout.strip().split("\n"):
            parts = line.strip().split(None, 2)
            if not parts:
                continue
            name = parts[0]
            if "(Premium)" in line:
                premium.append(name)
            elif "(Enhanced)" in line:
                enhanced.append(name)
        result = []
        if premium:
            result.append(("--- Premium (Neural) ---", premium))
        if enhanced:
            result.append(("--- Enhanced (High Quality) ---", enhanced))
        return result

    def split_into_speech_chunks(self, text):
        """Split text into natural speech phrases with pause and prosody metadata.
        Returns list of (text, pause_ms, rate_adj, pitch_adj) tuples."""
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?]) +", text)
        raw_chunks = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 120:
                parts = re.split(r"([,;:—–]+)", s)
                merged = []
                buf = ""
                for p in parts:
                    buf += p
                    if p in [",", ";", ":", "—", "–"] or any(c in p for c in ",;:—–"):
                        merged.append(buf.strip())
                        buf = ""
                if buf.strip():
                    merged.append(buf.strip())
                raw_chunks.extend([m for m in merged if m])
            else:
                raw_chunks.append(s)
        chunks = []
        for i, c in enumerate(raw_chunks):
            c = c.strip()
            if not c:
                continue
            pause_ms = 0
            rate_adj = 0
            pitch_adj = 0
            ends_with = c[-1] if c else "."
            if ends_with in ".!":
                pause_ms = 350
            elif ends_with == "?":
                pause_ms = 400
                rate_adj = -5
            elif ends_with == ",":
                pause_ms = 150
            elif ends_with == ";":
                pause_ms = 200
            elif ends_with == ":":
                pause_ms = 250
            else:
                pause_ms = 100
            if ends_with == "!":
                rate_adj = 5
                pitch_adj = 3
            if c.endswith("..."):
                pause_ms = 500
                rate_adj = -8
            if len(c) > 80:
                rate_adj -= 3
            elif len(c) < 30:
                rate_adj += 2
            if i > 0 and i % 5 == 0:
                pause_ms += 200
            chunks.append((c, pause_ms, rate_adj, pitch_adj))
        return chunks

    def on_voice_change(self, voice):
        if voice.startswith("---"):
            return
        self.status.showMessage("Voice: %s" % voice)

    def on_rate_change(self, value):
        if self.current_engine == "neural":
            self.neural_rate = value
            self.rate_label.setText("%+d%%" % value)
        else:
            self.macos_rate = value
            self.rate_label.setText("%d wpm" % value)

    def on_pitch_change(self, value):
        self.neural_pitch = value
        self.pitch_label.setText("%+dHz" % value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PasteHear()
    window.show()
    sys.exit(app.exec())
