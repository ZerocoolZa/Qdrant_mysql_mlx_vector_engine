#!/usr/bin/env python3
"""
Voice Learner GUI — Record your voice, extract features, correlate to Kokoro
voice matrix, and construct a custom voice. Then test it with TTS.

Usage: python3 voice_learner_gui.py
"""
import sys
import os
import json
import time
import numpy as np
import soundfile as sf
import sounddevice as sd
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QComboBox,
    QSlider, QGroupBox, QTabWidget, QSpinBox, QDoubleSpinBox,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

# Voice engine imports
sys.path.insert(0, str(Path(__file__).parent))
from voice_engine import VoiceDNA, VoiceAnalyzer, VoiceMatrixMapper

# Config
KOKORO_VOICES_PATH = "/Users/wws/KokoroModels/voices.npy"
KOKORO_MODEL_PATH = "/Users/wws/KokoroModels/onnx/model_fp16.onnx"
KOKORO_SCRIPT = "/Users/wws/Downloads/VoiceTyper/Services/kokoro_tts.py"
PYTHON3 = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
SAMPLE_RATE = 22050
RECORDINGS_DIR = Path.home() / ".voice_learner" / "recordings"
PROFILES_DIR = Path.home() / ".voice_learner" / "profiles"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

KOKORO_VOICES = [
    "af", "af_alloy", "af_aoede", "af_bella", "af_heart",
    "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george",
]


# =============================================================================
# Worker threads
# =============================================================================

class RecordingWorker(QThread):
    """Records audio in a background thread."""
    level_update = pyqtSignal(float)  # RMS level 0-1
    finished_recording = pyqtSignal(str, object)  # path, np.array
    error = pyqtSignal(str)

    def __init__(self, duration, sr=SAMPLE_RATE):
        super().__init__()
        self.duration = duration
        self.sr = sr
        self.cancelled = False

    def run(self):
        try:
            total_samples = int(self.duration * self.sr)
            self.recording = sd.rec(total_samples, samplerate=self.sr,
                                    channels=1, dtype=np.float32)
            # Monitor levels
            elapsed = 0
            while elapsed < self.duration and not self.cancelled:
                pos = int(elapsed * self.sr)
                chunk = self.recording[pos:min(pos + int(0.05 * self.sr), total_samples)]
                if len(chunk) > 0:
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    self.level_update.emit(min(rms * 5, 1.0))
                time.sleep(0.05)
                elapsed += 0.05

            sd.wait()

            if self.cancelled:
                return

            audio = self.recording.flatten()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(RECORDINGS_DIR / f"rec_{timestamp}.wav")
            sf.write(path, audio, self.sr)
            self.finished_recording.emit(path, audio)

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.cancelled = True
        sd.stop()


class AnalysisWorker(QThread):
    """Analyzes audio in background."""
    progress = pyqtSignal(str)
    finished_analysis = pyqtSignal(dict, dict)  # features, emotion
    error = pyqtSignal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        try:
            self.progress.emit("Loading audio...")
            dna = VoiceDNA()
            ok, data, err = dna.Run("load", {"path": self.audio_path})
            if not ok:
                # Fallback to numpy-only analyzer
                self.progress.emit("VoiceDNA failed, using VoiceAnalyzer fallback...")
                analyzer = VoiceAnalyzer()
                ok, data, err = analyzer.Run("load", {"path": self.audio_path})
                if not ok:
                    self.error.emit(f"Load failed: {err}")
                    return
                self.progress.emit("Analyzing (numpy-only mode)...")
                ok, features, err = analyzer.Run("analyze", None)
            else:
                self.progress.emit("Extracting 200+ features (parselmouth + librosa)...")
                ok, features, err = dna.Run("analyze", None)

            if not ok:
                self.error.emit(f"Analysis failed: {err}")
                return

            emotion = {}
            for k in ["excitement", "calmness", "stress", "confidence"]:
                if k in features:
                    emotion[k] = features[k]

            self.finished_analysis.emit(features, emotion)

        except Exception as e:
            self.error.emit(str(e))


class CorrelationWorker(QThread):
    """Correlates user features to Kokoro voice matrix."""
    progress = pyqtSignal(str)
    finished_correlation = pyqtSignal(dict, dict)  # correlations, closest_voice
    error = pyqtSignal(str)

    def __init__(self, user_features, base_voice="am_michael"):
        super().__init__()
        self.user_features = user_features
        self.base_voice = base_voice

    def run(self):
        try:
            self.progress.emit("Loading Kokoro voice matrix...")
            mapper = VoiceMatrixMapper()
            ok, data, err = mapper.Run("loadMatrix", {"path": KOKORO_VOICES_PATH})
            if not ok:
                self.error.emit(f"Matrix load failed: {err}")
                return

            # Add user voice
            self.progress.emit("Adding user voice profile...")
            mapper.Run("addVoice", {"name": "user_voice", "features": self.user_features})

            # Add all Kokoro voices with their features (we need to analyze each)
            # But we don't have audio for each — so we use a different approach:
            # Find closest Kokoro voice by comparing feature similarity
            self.progress.emit("Finding closest Kokoro voice...")

            voice_matrix = mapper.state["matrixData"]
            closest_voice = self.find_closest_voice(self.user_features, voice_matrix)

            # Now correlate
            self.progress.emit("Correlating features to matrix dimensions...")
            ok, correlations, err = mapper.Run("correlate", None)
            if not ok:
                # Correlate needs multiple voices — add the closest as second
                mapper.Run("addVoice", {"name": closest_voice, "features": self.user_features})
                ok, correlations, err = mapper.Run("correlate", None)

            self.finished_correlation.emit(correlations or {}, {"closest": closest_voice})

        except Exception as e:
            self.error.emit(str(e))

    def find_closest_voice(self, user_features, voice_matrix):
        """Find the Kokoro voice whose matrix is closest to user features.
        Uses pitch mean to pick gender-appropriate voice."""
        pitch = user_features.get("pitchMean", 150)
        centroid = user_features.get("spectralCentroidMean", user_features.get("spectralCentroid", 2000))
        breathiness = user_features.get("breathiness", 0.3)

        # Simple heuristic: pitch < 130 = male, > 180 = female, else neutral
        if pitch < 130:
            candidates = ["am_michael", "am_adam", "am_eric", "am_echo", "am_onyx", "am_liam"]
        elif pitch > 180:
            candidates = ["af_bella", "af_sarah", "af_nicole", "af_sky", "af_nova", "af_river"]
        else:
            candidates = ["af_alloy", "am_puck", "af_heart", "am_liam", "bf_emma", "bm_fable"]

        return candidates[0] if candidates else "af_bella"


class TTSTestWorker(QThread):
    """Generates TTS with a voice and plays it."""
    progress = pyqtSignal(str)
    finished_tts = pyqtSignal(str)  # wav path
    error = pyqtSignal(str)

    def __init__(self, text, voice, output_path, custom_matrix=None):
        super().__init__()
        self.text = text
        self.voice = voice
        self.output_path = output_path
        self.custom_matrix = custom_matrix

    def run(self):
        try:
            import subprocess

            if self.custom_matrix is not None:
                # Save custom matrix into a temp voices file
                self.progress.emit("Building custom voice matrix...")
                original = np.load(KOKORO_VOICES_PATH, allow_pickle=True).item()
                custom = dict(original)
                custom["user_voice"] = self.custom_matrix.astype(np.float32)
                temp_voices = "/tmp/voice_learner_custom_voices.npy"
                np.save(temp_voices, custom, allow_pickle=True)

                # Write a temp TTS script that uses the custom voices file
                temp_script = "/tmp/voice_learner_tts.py"
                with open(KOKORO_SCRIPT) as f:
                    script = f.read()
                script = script.replace(
                    'VOICES_PATH = "/Users/wws/KokoroModels/voices.npy"',
                    f'VOICES_PATH = "{temp_voices}"'
                )
                with open(temp_script, "w") as f:
                    f.write(script)

                script_to_run = temp_script
                voice = "user_voice"
            else:
                script_to_run = KOKORO_SCRIPT
                voice = self.voice

            self.progress.emit(f"Generating speech with voice '{voice}'...")
            result = subprocess.run(
                [PYTHON3, script_to_run, self.text, voice, self.output_path],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                self.error.emit(f"TTS failed: {result.stderr[:300]}")
                return

            if not os.path.exists(self.output_path):
                self.error.emit("WAV not created")
                return

            self.progress.emit("Playing audio...")
            subprocess.run(["/usr/bin/afplay", self.output_path], timeout=60)
            self.finished_tts.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Main GUI
# =============================================================================

class VoiceLearnerGUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Learner — Kokoro Voice Cloning")
        self.setMinimumSize(900, 700)
        self.user_features = {}
        self.emotion = {}
        self.correlations = {}
        self.closest_voice = "af_bella"
        self.custom_matrix = None
        self.recording_worker = None
        self.analysis_worker = None
        self.correlation_worker = None
        self.tts_worker = None
        self.saved_profiles = self.load_profiles()

        self.setup_ui()
        self.refresh_profiles()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Record
        tabs.addTab(self.build_record_tab(), "1. Record")
        # Tab 2: Analyze
        tabs.addTab(self.build_analyze_tab(), "2. Analyze")
        # Tab 3: Learn
        tabs.addTab(self.build_learn_tab(), "3. Learn Voice")
        # Tab 4: Test
        tabs.addTab(self.build_test_tab(), "4. Test Voice")
        # Tab 5: Profiles
        tabs.addTab(self.build_profiles_tab(), "Profiles")

        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

    # ---- Tab 1: Record ----

    def build_record_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Record Your Voice")
        glayout = QVBoxLayout(group)

        # Instructions
        info = QLabel(
            "Record 3-5 samples of your voice speaking naturally.\n"
            "Read any text aloud for best results. 5-10 seconds each.\n"
            "More samples = better voice profile."
        )
        info.setWordWrap(True)
        glayout.addWidget(info)

        # Duration slider
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Duration (seconds):"))
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(3, 30)
        self.duration_slider.setValue(8)
        self.duration_slider.valueChanged.connect(
            lambda v: self.duration_label.setText(f"{v}s")
        )
        dur_layout.addWidget(self.duration_slider)
        self.duration_label = QLabel("8s")
        dur_layout.addWidget(self.duration_label)
        glayout.addLayout(dur_layout)

        # Level meter
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setFormat("Mic Level: %v%")
        glayout.addWidget(self.level_bar)

        # Record button
        self.record_btn = QPushButton("● Record")
        self.record_btn.setStyleSheet("QPushButton { font-size: 18px; padding: 12px; background-color: #ff4444; color: white; border-radius: 8px; }")
        self.record_btn.clicked.connect(self.toggle_recording)
        glayout.addWidget(self.record_btn)

        # Recordings list
        glayout.addWidget(QLabel("Recorded samples:"))
        self.recordings_list = QTextEdit()
        self.recordings_list.setReadOnly(True)
        self.recordings_list.setMaximumHeight(150)
        glayout.addWidget(self.recordings_list)

        # Analyze all button
        self.analyze_all_btn = QPushButton("→ Analyze All Samples")
        self.analyze_all_btn.clicked.connect(self.analyze_all_samples)
        glayout.addWidget(self.analyze_all_btn)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def toggle_recording(self):
        if self.recording_worker and self.recording_worker.isRunning():
            self.recording_worker.cancel()
            self.record_btn.setText("● Record")
            self.record_btn.setStyleSheet("QPushButton { font-size: 18px; padding: 12px; background-color: #ff4444; color: white; border-radius: 8px; }")
            self.status_label.setText("Recording cancelled")
        else:
            duration = self.duration_slider.value()
            self.recording_worker = RecordingWorker(duration)
            self.recording_worker.level_update.connect(self.update_level)
            self.recording_worker.finished_recording.connect(self.on_recording_done)
            self.recording_worker.error.connect(self.on_recording_error)
            self.recording_worker.start()
            self.record_btn.setText("■ Stop")
            self.record_btn.setStyleSheet("QPushButton { font-size: 18px; padding: 12px; background-color: #444444; color: white; border-radius: 8px; }")
            self.status_label.setText(f"Recording {duration}s...")

    def update_level(self, level):
        self.level_bar.setValue(int(level * 100))

    def on_recording_done(self, path, audio):
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet("QPushButton { font-size: 18px; padding: 12px; background-color: #ff4444; color: white; border-radius: 8px; }")
        self.level_bar.setValue(0)
        current = self.recordings_list.toPlainText()
        self.recordings_list.setPlainText(current + f"✓ {Path(path).name}\n")
        self.status_label.setText(f"Recorded: {path}")

    def on_recording_error(self, err):
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet("QPushButton { font-size: 18px; padding: 12px; background-color: #ff4444; color: white; border-radius: 8px; }")
        self.level_bar.setValue(0)
        self.status_label.setText(f"Error: {err}")

    def analyze_all_samples(self):
        recordings = list(RECORDINGS_DIR.glob("rec_*.wav"))
        if not recordings:
            QMessageBox.warning(self, "No recordings", "Record some samples first!")
            return
        # Analyze the most recent one for now (merge later)
        self.analyze_single(str(recordings[-1]))

    def analyze_single(self, path):
        self.status_label.setText(f"Analyzing {Path(path).name}...")
        self.analysis_worker = AnalysisWorker(path)
        self.analysis_worker.progress.connect(self.status_label.setText)
        self.analysis_worker.finished_analysis.connect(self.on_analysis_done)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    # ---- Tab 2: Analyze ----

    def build_analyze_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Voice Features (200+)")
        glayout = QVBoxLayout(group)

        self.features_table = QTableWidget(0, 3)
        self.features_table.setHorizontalHeaderLabels(["Feature", "Value", "Description"])
        self.features_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.features_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.features_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        glayout.addWidget(self.features_table)

        layout.addWidget(group)

        # Emotion section
        emo_group = QGroupBox("Emotion Estimates")
        emo_layout = QVBoxLayout(emo_group)
        self.emotion_labels = {}
        for emo in ["excitement", "calmness", "stress", "confidence"]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{emo.capitalize()}:"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            row.addWidget(bar)
            val = QLabel("—")
            row.addWidget(val)
            emo_layout.addLayout(row)
            self.emotion_labels[emo] = (bar, val)
        layout.addWidget(emo_group)

        # Continue button
        self.to_learn_btn = QPushButton("→ Learn Voice (correlate to Kokoro)")
        self.to_learn_btn.clicked.connect(self.start_learning)
        layout.addWidget(self.to_learn_btn)

        return widget

    def on_analysis_done(self, features, emotion):
        self.user_features = features
        self.emotion = emotion
        self.populate_features_table(features)
        self.populate_emotion(emotion)
        self.status_label.setText(f"Analysis complete — {len(features)} features extracted")
        QMessageBox.information(self, "Analysis Complete",
                                f"Extracted {len(features)} features.\n"
                                f"Click 'Learn Voice' to correlate to Kokoro voices.")

    def on_analysis_error(self, err):
        self.status_label.setText(f"Analysis error: {err}")
        QMessageBox.critical(self, "Analysis Error", err)

    FEATURE_DESCRIPTIONS = {
        "pitchMean": "Average fundamental frequency (Hz) — voice gender/tone",
        "pitchStd": "Pitch variation — expressiveness",
        "pitchMin": "Lowest pitch (Hz)",
        "pitchMax": "Highest pitch (Hz)",
        "pitchRange": "Pitch range (max - min)",
        "pitchMedian": "Median pitch (Hz)",
        "spectralCentroidMean": "Brightness — high freq energy center",
        "spectralBandwidthMean": "Spectral spread — tonal width",
        "spectralRolloffMean": "Freq where 85% energy is below",
        "spectralFlatnessMean": "Noise-like vs tonal (0=tonal, 1=noise)",
        "rmsMean": "Average loudness",
        "rmsStd": "Loudness variation",
        "jitterLocal": "Pitch cycle instability — roughness indicator",
        "shimmerLocal": "Amplitude instability — breathiness indicator",
        "harmonicityMean": "Harmonics-to-noise ratio (dB) — voice clarity",
        "breathiness": "Estimated breathiness (0-1)",
        "roughness": "Estimated roughness (0-1)",
        "speechRate": "Syllables/sec estimate",
        "silenceRatio": "Fraction of silence",
        "tempo": "Estimated tempo (BPM)",
        "zeroCrossingRate": "ZCR — voicing/noisiness indicator",
    }

    def populate_features_table(self, features):
        # Sort: important features first
        important = ["pitchMean", "pitchStd", "pitchRange", "spectralCentroidMean",
                     "rmsMean", "breathiness", "roughness", "harmonicityMean",
                     "jitterLocal", "shimmerLocal", "speechRate", "tempo"]
        sorted_keys = [k for k in important if k in features]
        other_keys = sorted([k for k in features if k not in important and k != "timestamp"])
        all_keys = sorted_keys + other_keys

        self.features_table.setRowCount(len(all_keys))
        for i, key in enumerate(all_keys):
            val = features[key]
            if isinstance(val, float):
                val_str = f"{val:.4f}"
            else:
                val_str = str(val)
            self.features_table.setItem(i, 0, QTableWidgetItem(key))
            self.features_table.setItem(i, 1, QTableWidgetItem(val_str))
            desc = self.FEATURE_DESCRIPTIONS.get(key, "")
            self.features_table.setItem(i, 2, QTableWidgetItem(desc))

    def populate_emotion(self, emotion):
        for emo, (bar, label) in self.emotion_labels.items():
            val = emotion.get(emo, 0)
            bar.setValue(int(val * 100))
            label.setText(f"{val:.2f}")

    # ---- Tab 3: Learn ----

    def build_learn_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Voice Learning — Correlate to Kokoro Matrix")
        glayout = QVBoxLayout(group)

        info = QLabel(
            "Your voice features will be correlated to the Kokoro-82M voice matrix.\n"
            "The system finds the closest base voice and constructs a custom voice matrix.\n"
            "Voice matrix shape: (512, 256) per voice — 28 reference voices."
        )
        info.setWordWrap(True)
        glayout.addWidget(info)

        # Base voice selector
        base_layout = QHBoxLayout()
        base_layout.addWidget(QLabel("Base voice to modify:"))
        self.base_voice_combo = QComboBox()
        for v in KOKORO_VOICES:
            self.base_voice_combo.addItem(v)
        self.base_voice_combo.setCurrentText("am_michael")
        base_layout.addWidget(self.base_voice_combo)
        glayout.addLayout(base_layout)

        # Blend strength
        blend_layout = QHBoxLayout()
        blend_layout.addWidget(QLabel("Blend strength (how much to push toward your voice):"))
        self.blend_slider = QSlider(Qt.Orientation.Horizontal)
        self.blend_slider.setRange(0, 100)
        self.blend_slider.setValue(50)
        self.blend_slider.valueChanged.connect(
            lambda v: self.blend_label.setText(f"{v}%")
        )
        blend_layout.addWidget(self.blend_slider)
        self.blend_label = QLabel("50%")
        blend_layout.addWidget(self.blend_label)
        glayout.addLayout(blend_layout)

        # Learn button
        self.learn_btn = QPushButton("🧠 Learn My Voice")
        self.learn_btn.setStyleSheet("QPushButton { font-size: 16px; padding: 10px; }")
        self.learn_btn.clicked.connect(self.start_learning)
        glayout.addWidget(self.learn_btn)

        # Results
        self.learn_results = QTextEdit()
        self.learn_results.setReadOnly(True)
        glayout.addWidget(self.learn_results)

        layout.addWidget(group)

        # Save profile
        save_group = QGroupBox("Save Voice Profile")
        save_layout = QVBoxLayout(save_group)
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("Profile name:"))
        self.profile_name_input = QComboBox()
        self.profile_name_input.setEditable(True)
        self.profile_name_input.addItems(["my_voice", "deep_voice", "high_voice", "calm_voice"])
        save_row.addWidget(self.profile_name_input)
        self.save_profile_btn = QPushButton("Save Profile")
        self.save_profile_btn.clicked.connect(self.save_profile)
        save_row.addWidget(self.save_profile_btn)
        save_layout.addLayout(save_row)
        layout.addWidget(save_group)

        return widget

    def start_learning(self):
        if not self.user_features:
            QMessageBox.warning(self, "No features", "Analyze a recording first!")
            return

        base_voice = self.base_voice_combo.currentText()
        self.learn_btn.setEnabled(False)
        self.learn_btn.setText("Learning...")
        self.status_label.setText("Correlating to Kokoro matrix...")

        self.correlation_worker = CorrelationWorker(self.user_features, base_voice)
        self.correlation_worker.progress.connect(self.status_label.setText)
        self.correlation_worker.finished_correlation.connect(self.on_learning_done)
        self.correlation_worker.error.connect(self.on_learning_error)
        self.correlation_worker.start()

    def on_learning_done(self, correlations, closest_info):
        self.correlations = correlations
        self.closest_voice = closest_info.get("closest", "af_bella")

        # Construct custom matrix
        blend = self.blend_slider.value() / 100.0
        base_voice = self.base_voice_combo.currentText()

        try:
            voice_matrix = np.load(KOKORO_VOICES_PATH, allow_pickle=True).item()
            if base_voice not in voice_matrix:
                base_voice = self.closest_voice

            base_matrix = voice_matrix[base_voice].copy().astype(np.float32)

            # Apply feature-based modifications
            # Pitch shift: if user pitch is higher/lower than base, shift matrix
            user_pitch = self.user_features.get("pitchMean", 150)
            base_pitch_map = {"af": 220, "am_michael": 130, "am_adam": 110, "af_bella": 210}
            base_pitch = base_pitch_map.get(base_voice, 170)
            pitch_ratio = user_pitch / base_pitch if base_pitch > 0 else 1.0

            # Brightness: spectral centroid
            user_centroid = self.user_features.get("spectralCentroidMean",
                                                    self.user_features.get("spectralCentroid", 2000))
            centroid_ratio = user_centroid / 2000.0  # normalize

            # Breathiness
            user_breath = self.user_features.get("breathiness", 0.3)

            # Apply modifications with blend strength
            self.custom_matrix = base_matrix.copy()

            # Pitch: scale the matrix (interpolation across phoneme positions)
            if abs(pitch_ratio - 1.0) > 0.05:
                scale = 1.0 + (pitch_ratio - 1.0) * blend
                self.custom_matrix = self.custom_matrix * scale

            # Brightness: boost high-frequency components
            if abs(centroid_ratio - 1.0) > 0.05:
                boost = 1.0 + (centroid_ratio - 1.0) * blend * 0.3
                # Apply more to later columns (higher freq)
                col_weights = np.linspace(0.9, 1.1, self.custom_matrix.shape[1]).astype(np.float32)
                self.custom_matrix = self.custom_matrix * (col_weights * boost)

            # Breathiness: add noise
            if user_breath > 0.4:
                noise_level = (user_breath - 0.3) * blend * 0.05
                noise = np.random.randn(*self.custom_matrix.shape).astype(np.float32) * noise_level
                self.custom_matrix = self.custom_matrix + noise

            # Roughness: jitter
            user_rough = self.user_features.get("roughness", 0.1)
            if user_rough > 0.05:
                jitter_level = user_rough * blend * 0.03
                jitter = np.random.randn(*self.custom_matrix.shape).astype(np.float32) * jitter_level
                self.custom_matrix = self.custom_matrix + jitter

            # Clamp to reasonable range
            self.custom_matrix = np.clip(self.custom_matrix, -3.0, 3.0).astype(np.float32)

            results_text = (
                f"✓ Voice learning complete!\n\n"
                f"Closest Kokoro voice: {self.closest_voice}\n"
                f"Base voice used: {base_voice}\n"
                f"Blend strength: {self.blend_slider.value()}%\n\n"
                f"Feature adjustments applied:\n"
                f"  Pitch: {user_pitch:.1f}Hz (ratio: {pitch_ratio:.2f})\n"
                f"  Brightness: {user_centroid:.0f}Hz (ratio: {centroid_ratio:.2f})\n"
                f"  Breathiness: {user_breath:.3f}\n"
                f"  Roughness: {user_rough:.3f}\n\n"
                f"Custom matrix shape: {self.custom_matrix.shape}\n"
                f"Value range: [{self.custom_matrix.min():.3f}, {self.custom_matrix.max():.3f}]\n\n"
                f"→ Go to 'Test Voice' tab to hear it!"
            )
            self.learn_results.setPlainText(results_text)
            self.status_label.setText("Voice learned — go to Test tab")

        except Exception as e:
            self.learn_results.setPlainText(f"Error constructing voice: {e}")
            self.status_label.setText(f"Learning error: {e}")

        self.learn_btn.setEnabled(True)
        self.learn_btn.setText("🧠 Learn My Voice")

    def on_learning_error(self, err):
        self.learn_btn.setEnabled(True)
        self.learn_btn.setText("🧠 Learn My Voice")
        self.status_label.setText(f"Learning error: {err}")
        QMessageBox.critical(self, "Learning Error", err)

    # ---- Tab 4: Test ----

    def build_test_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Test Your Custom Voice")
        glayout = QVBoxLayout(group)

        # Text input
        glayout.addWidget(QLabel("Text to speak:"))
        self.tts_text = QTextEdit()
        self.tts_text.setPlainText("Hello, this is my custom voice. How does it sound?")
        self.tts_text.setMaximumHeight(80)
        glayout.addWidget(self.tts_text)

        # Voice selector
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("Voice:"))
        self.test_voice_combo = QComboBox()
        self.test_voice_combo.addItem("★ My Custom Voice")
        for v in KOKORO_VOICES:
            self.test_voice_combo.addItem(v)
        voice_layout.addWidget(self.test_voice_combo)
        glayout.addLayout(voice_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.speak_btn = QPushButton("🔊 Speak")
        self.speak_btn.setStyleSheet("QPushButton { font-size: 16px; padding: 10px; }")
        self.speak_btn.clicked.connect(self.test_speak)
        btn_layout.addWidget(self.speak_btn)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self.stop_speaking)
        btn_layout.addWidget(self.stop_btn)
        glayout.addLayout(btn_layout)

        # Status
        self.tts_status = QLabel("")
        self.tts_status.setWordWrap(True)
        glayout.addWidget(self.tts_status)

        layout.addWidget(group)

        # Comparison section
        comp_group = QGroupBox("A/B Comparison")
        comp_layout = QVBoxLayout(comp_group)
        comp_row = QHBoxLayout()
        comp_row.addWidget(QLabel("Compare to:"))
        self.compare_combo = QComboBox()
        for v in KOKORO_VOICES:
            self.compare_combo.addItem(v)
        self.compare_combo.setCurrentText("am_michael")
        comp_row.addWidget(self.compare_combo)
        self.compare_btn = QPushButton("Play Both (A then B)")
        self.compare_btn.clicked.connect(self.compare_voices)
        comp_row.addWidget(self.compare_btn)
        comp_layout.addLayout(comp_row)
        layout.addWidget(comp_group)

        layout.addStretch()
        return widget

    def test_speak(self):
        text = self.tts_text.toPlainText().strip()
        if not text:
            return

        voice_idx = self.test_voice_combo.currentIndex()
        output = f"/tmp/voice_learner_test_{int(time.time())}.wav"

        if voice_idx == 0:
            # Custom voice
            if self.custom_matrix is None:
                QMessageBox.warning(self, "No custom voice", "Learn your voice first!")
                return
            self.tts_worker = TTSTestWorker(text, "user_voice", output, self.custom_matrix)
        else:
            voice = self.test_voice_combo.currentText()
            self.tts_worker = TTSTestWorker(text, voice, output)

        self.speak_btn.setEnabled(False)
        self.tts_worker.progress.connect(self.tts_status.setText)
        self.tts_worker.finished_tts.connect(self.on_tts_done)
        self.tts_worker.error.connect(self.on_tts_error)
        self.tts_worker.start()

    def stop_speaking(self):
        import subprocess
        subprocess.run(["pkill", "-f", "afplay"], capture_output=True)
        self.tts_status.setText("Stopped")

    def on_tts_done(self, path):
        self.speak_btn.setEnabled(True)
        self.tts_status.setText(f"Done: {path}")

    def on_tts_error(self, err):
        self.speak_btn.setEnabled(True)
        self.tts_status.setText(f"Error: {err}")

    def compare_voices(self):
        text = self.tts_text.toPlainText().strip()
        if not text or self.custom_matrix is None:
            QMessageBox.warning(self, "Not ready", "Need text + learned voice")
            return

        compare_voice = self.compare_combo.currentText()
        self.tts_status.setText(f"Playing A ({compare_voice})...")
        output_a = f"/tmp/voice_learner_compare_a_{int(time.time())}.wav"

        # Play A first, then B
        def play_a_done(path):
            self.tts_status.setText("Playing B (your voice)...")
            output_b = f"/tmp/voice_learner_compare_b_{int(time.time())}.wav"
            self.tts_worker = TTSTestWorker(text, "user_voice", output_b, self.custom_matrix)
            self.tts_worker.progress.connect(self.tts_status.setText)
            self.tts_worker.finished_tts.connect(lambda p: self.tts_status.setText("Comparison done"))
            self.tts_worker.error.connect(self.on_tts_error)
            self.tts_worker.start()

        self.tts_worker = TTSTestWorker(text, compare_voice, output_a)
        self.tts_worker.progress.connect(self.tts_status.setText)
        self.tts_worker.finished_tts.connect(play_a_done)
        self.tts_worker.error.connect(self.on_tts_error)
        self.tts_worker.start()

    # ---- Tab 5: Profiles ----

    def build_profiles_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Saved Voice Profiles")
        glayout = QVBoxLayout(group)

        self.profiles_table = QTableWidget(0, 4)
        self.profiles_table.setHorizontalHeaderLabels(["Name", "Created", "Features", "Base Voice"])
        self.profiles_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.profiles_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        glayout.addWidget(self.profiles_table)

        btn_row = QHBoxLayout()
        self.load_profile_btn = QPushButton("Load Profile")
        self.load_profile_btn.clicked.connect(self.load_profile)
        btn_row.addWidget(self.load_profile_btn)

        self.delete_profile_btn = QPushButton("Delete Profile")
        self.delete_profile_btn.clicked.connect(self.delete_profile)
        btn_row.addWidget(self.delete_profile_btn)

        self.refresh_profiles_btn = QPushButton("Refresh")
        self.refresh_profiles_btn.clicked.connect(self.refresh_profiles)
        btn_row.addWidget(self.refresh_profiles_btn)
        glayout.addLayout(btn_row)

        layout.addWidget(group)
        return widget

    def load_profiles(self):
        profiles = {}
        for p in PROFILES_DIR.glob("*.json"):
            try:
                with open(p) as f:
                    data = json.load(f)
                profiles[p.stem] = data
            except Exception:
                pass
        return profiles

    def refresh_profiles(self):
        self.saved_profiles = self.load_profiles()
        self.profiles_table.setRowCount(len(self.saved_profiles))
        for i, (name, data) in enumerate(self.saved_profiles.items()):
            self.profiles_table.setItem(i, 0, QTableWidgetItem(name))
            self.profiles_table.setItem(i, 1, QTableWidgetItem(data.get("created", "?")))
            self.profiles_table.setItem(i, 2, QTableWidgetItem(str(len(data.get("features", {})))))
            self.profiles_table.setItem(i, 3, QTableWidgetItem(data.get("base_voice", "?")))

    def save_profile(self):
        if not self.user_features:
            QMessageBox.warning(self, "No data", "Analyze your voice first!")
            return

        name = self.profile_name_input.currentText().strip()
        if not name:
            return

        profile = {
            "name": name,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "features": self.user_features,
            "emotion": self.emotion,
            "base_voice": self.base_voice_combo.currentText(),
            "closest_voice": self.closest_voice,
            "blend": self.blend_slider.value(),
        }

        if self.custom_matrix is not None:
            np.save(str(PROFILES_DIR / f"{name}_matrix.npy"), self.custom_matrix)

        path = PROFILES_DIR / f"{name}.json"
        with open(path, "w") as f:
            json.dump(profile, f, indent=2, default=str)

        self.refresh_profiles()
        self.status_label.setText(f"Profile saved: {name}")
        QMessageBox.information(self, "Saved", f"Profile '{name}' saved.")

    def load_profile(self):
        row = self.profiles_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Select a profile to load")
            return
        name = self.profiles_table.item(row, 0).text()
        profile = self.saved_profiles.get(name)
        if not profile:
            return

        self.user_features = profile.get("features", {})
        self.emotion = profile.get("emotion", {})
        self.populate_features_table(self.user_features)
        self.populate_emotion(self.emotion)

        matrix_path = PROFILES_DIR / f"{name}_matrix.npy"
        if matrix_path.exists():
            self.custom_matrix = np.load(str(matrix_path))

        self.status_label.setText(f"Loaded profile: {name}")

    def delete_profile(self):
        row = self.profiles_table.currentRow()
        if row < 0:
            return
        name = self.profiles_table.item(row, 0).text()
        reply = QMessageBox.question(self, "Delete", f"Delete profile '{name}'?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        (PROFILES_DIR / f"{name}.json").unlink(missing_ok=True)
        (PROFILES_DIR / f"{name}_matrix.npy").unlink(missing_ok=True)
        self.refresh_profiles()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark theme
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(55, 55, 55))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(80, 120, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    gui = VoiceLearnerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
