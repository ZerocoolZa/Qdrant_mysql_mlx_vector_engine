#!/usr/bin/env python3
"""
Voice Matcher Workers — Backend thread tasks.
All QThread workers for mic monitoring, calibration, recording,
analysis, matching, and TTS playback.

Separated from the GUI to keep backend logic and UI code clean.
"""

# ── Standard library ─────────────────────────────────────────────────────────
import os
import time
import subprocess
from datetime import datetime
from pathlib import Path

# ── Third-party ──────────────────────────────────────────────────────────────
import numpy as np
import soundfile as sf
import sounddevice as sd

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtCore import QThread, pyqtSignal

# ── Local modules ────────────────────────────────────────────────────────────
from voice_engine import VoiceDNA, VoiceAnalyzer
from build_reference_db import load_reference_db, match_voice, KOKORO_VOICES

# ── Config (shared with GUI) ─────────────────────────────────────────────────
PYTHON3 = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
KOKORO_SCRIPT = "/Users/wws/Downloads/VoiceTyper/Services/kokoro_tts.py"
SAMPLE_RATE = 22050
RECORDINGS_DIR = Path.home() / ".voice_learner" / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Mic monitor — continuous level detection + auto-level
# =============================================================================

class MicMonitorWorker(QThread):
    """Continuously monitors mic input level without recording.
    Emits level updates for the live mic detection bar.
    When auto_level is enabled, automatically adjusts gain to target ~50%."""
    level_update = pyqtSignal(float)          # 0..1
    peak_update = pyqtSignal(float)            # 0..1 peak hold
    auto_gain_update = pyqtSignal(float)       # new gain value when auto-adjusting

    def __init__(self, sr=SAMPLE_RATE, device=None):
        super().__init__()
        self.sr = sr
        self.device = device
        self.gain = 1.0
        self.running = True
        self.peak = 0.0
        self.auto_level = False
        self.target_level = 0.5
        self._level_history = []
        self._adjust_cooldown = 0

    def set_gain(self, gain):
        self.gain = gain

    def set_device(self, device):
        self.device = device

    def set_auto_level(self, enabled):
        self.auto_level = enabled
        if enabled:
            self._level_history = []

    def run(self):
        blocksize = int(0.05 * self.sr)
        try:
            stream_kwargs = dict(samplerate=self.sr, channels=1,
                                 dtype=np.float32, blocksize=blocksize)
            if self.device is not None:
                stream_kwargs["device"] = self.device
            with sd.InputStream(**stream_kwargs, callback=self._callback):
                while self.running:
                    time.sleep(0.05)
        except Exception:
            self.level_update.emit(-1.0)

    def _callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        chunk = indata.flatten().astype(np.float64)
        raw_rms = float(np.sqrt(np.mean(chunk ** 2)))
        chunk = np.clip(chunk * self.gain, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        level = min(rms * 5, 1.0)
        self.level_update.emit(level)
        if level > self.peak:
            self.peak = level
        self.peak *= 0.95
        self.peak_update.emit(self.peak)

        if self.auto_level and raw_rms > 1e-6:
            self._level_history.append(raw_rms)
            if len(self._level_history) > 40:
                self._level_history.pop(0)
            self._adjust_cooldown -= 1
            if len(self._level_history) >= 20 and self._adjust_cooldown <= 0:
                median_rms = float(np.median(self._level_history))
                if median_rms > 1e-6:
                    new_gain = self.target_level / (median_rms * 5)
                    new_gain = max(0.1, min(new_gain, 50.0))
                    self.gain = self.gain * 0.8 + new_gain * 0.2
                    self.auto_gain_update.emit(self.gain)
                self._adjust_cooldown = 10

    def stop(self):
        self.running = False


# =============================================================================
# Calibration — two-phase noise floor + voice level measurement
# =============================================================================

class CalibrationWorker(QThread):
    """Two-phase mic calibration:
       Phase 1: measure noise floor (2s of silence)
       Phase 2: measure voice level (3s of speaking)
       Emits progress text and final results."""
    progress = pyqtSignal(str)
    phase_update = pyqtSignal(int)             # 0=idle, 1=noise, 2=voice, 3=done
    level_update = pyqtSignal(float)
    finished_calibration = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, sr=SAMPLE_RATE, device=None):
        super().__init__()
        self.sr = sr
        self.device = device
        self.cancelled = False
        self._noise_rms = []
        self._voice_rms = []

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            blocksize = int(0.05 * self.sr)
            stream_kwargs = dict(samplerate=self.sr, channels=1,
                                 dtype=np.float32, blocksize=blocksize)
            if self.device is not None:
                stream_kwargs["device"] = self.device

            # Phase 1: Noise floor (2 seconds)
            self._noise_rms = []
            self.phase_update.emit(1)
            self.progress.emit("Calibrating: measuring noise floor... (stay quiet!)")
            noise_elapsed = 0.0
            with sd.InputStream(**stream_kwargs, callback=self._noise_callback):
                while noise_elapsed < 2.0 and not self.cancelled:
                    time.sleep(0.05)
                    noise_elapsed += 0.05
            if self.cancelled:
                return
            if not self._noise_rms:
                self.error.emit("No audio data captured")
                return
            noise_floor = float(np.median(self._noise_rms))
            noise_peak = float(np.max(self._noise_rms))

            # Phase 2: Voice level (3 seconds)
            self._voice_rms = []
            self.phase_update.emit(2)
            self.progress.emit("Calibrating: SPEAK NOW! (3 seconds)")
            voice_elapsed = 0.0
            with sd.InputStream(**stream_kwargs, callback=self._voice_callback):
                while voice_elapsed < 3.0 and not self.cancelled:
                    time.sleep(0.05)
                    voice_elapsed += 0.05
            if self.cancelled:
                return
            if not self._voice_rms:
                self.error.emit("No voice detected")
                return
            voice_level = float(np.median(self._voice_rms))
            voice_peak = float(np.max(self._voice_rms))

            # Compute optimal gain and gate
            if voice_level > 1e-6:
                optimal_gain = 0.5 / voice_level
            else:
                optimal_gain = 50.0
            optimal_gain = max(0.1, min(optimal_gain, 50.0))

            if voice_level > noise_peak:
                gate_threshold = (noise_peak * 1.5 + voice_level * 0.3) / 2
                gate_threshold = max(gate_threshold, noise_peak * 1.2)
            else:
                gate_threshold = noise_peak * 1.5
            gate_slider_val = int(min(gate_threshold * 1000, 50))

            self.phase_update.emit(3)
            self.progress.emit("Calibration complete!")
            self.finished_calibration.emit({
                "noise_floor": noise_floor,
                "noise_peak": noise_peak,
                "voice_level": voice_level,
                "voice_peak": voice_peak,
                "gain": optimal_gain,
                "gate": gate_slider_val,
            })
        except Exception as e:
            self.error.emit(str(e))

    def _noise_callback(self, indata, frames, time_info, status):
        if self.cancelled:
            return
        chunk = indata.flatten().astype(np.float64)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self._noise_rms.append(rms)
        self.level_update.emit(min(rms * 5, 1.0))

    def _voice_callback(self, indata, frames, time_info, status):
        if self.cancelled:
            return
        chunk = indata.flatten().astype(np.float64)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self._voice_rms.append(rms)
        self.level_update.emit(min(rms * 5, 1.0))


# =============================================================================
# Live recording — capture audio with gain + noise gate + FFT spectrum
# =============================================================================

class LiveRecordWorker(QThread):
    level_update = pyqtSignal(float)
    waveform_update = pyqtSignal(object)
    spectrum_update = pyqtSignal(object)
    finished_recording = pyqtSignal(str)

    def __init__(self, duration, sr=SAMPLE_RATE, gain=1.0, noise_gate=0.0, device=None):
        super().__init__()
        self.duration = duration
        self.sr = sr
        self.cancelled = False
        self.fft_size = 512
        self.gain = gain
        self.noise_gate = noise_gate
        self.device = device

    def run(self):
        try:
            total = int(self.duration * self.sr)
            rec_kwargs = dict(samplerate=self.sr, channels=1, dtype=np.float32)
            if self.device is not None:
                rec_kwargs["device"] = self.device
            self.recording = sd.rec(total, **rec_kwargs)
            elapsed = 0
            while elapsed < self.duration and not self.cancelled:
                pos = int(elapsed * self.sr)
                chunk = self.recording[pos:min(pos + int(0.05 * self.sr), total)]
                if len(chunk) > 0:
                    chunk_f64 = chunk.astype(np.float64).flatten()
                    chunk_f64 = np.clip(chunk_f64 * self.gain, -1.0, 1.0)
                    rms = float(np.sqrt(np.mean(chunk_f64 ** 2)))
                    if self.noise_gate > 0.0 and rms < self.noise_gate:
                        chunk_f64 = np.zeros_like(chunk_f64)
                        rms = 0.0
                    self.level_update.emit(min(rms * 5, 1.0))
                    self.waveform_update.emit(chunk_f64)

                    n = min(len(chunk_f64), self.fft_size)
                    windowed = chunk_f64[:n] * np.hanning(n)
                    spectrum = np.abs(np.fft.rfft(windowed, n=self.fft_size))
                    peak = float(np.max(spectrum))
                    if peak > 1e-8:
                        spectrum = spectrum / peak
                        spectrum = np.log1p(spectrum * 20) / np.log1p(20)
                    else:
                        spectrum = np.zeros_like(spectrum)
                    spectrum = np.nan_to_num(spectrum, nan=0.0, posinf=1.0, neginf=0.0)
                    spectrum = np.clip(spectrum, 0, 1)
                    self.spectrum_update.emit(spectrum)

                time.sleep(0.05)
                elapsed += 0.05

            sd.wait()
            if self.cancelled:
                return

            audio = self.recording.flatten()
            if self.gain != 1.0:
                audio = np.clip(audio * self.gain, -1.0, 1.0).astype(np.float32)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(RECORDINGS_DIR / f"rec_{ts}.wav")
            sf.write(path, audio, self.sr)
            self.finished_recording.emit(path)
        except Exception:
            self.level_update.emit(-1.0)

    def cancel(self):
        self.cancelled = True
        sd.stop()


# =============================================================================
# Analysis — extract voice DNA features from recorded audio
# =============================================================================

class AnalysisWorker(QThread):
    progress = pyqtSignal(str)
    finished_analysis = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        try:
            self.progress.emit("Loading audio...")
            dna = VoiceDNA()
            ok, _, err = dna.Run("load", {"path": self.audio_path})
            if not ok:
                self.progress.emit("Using numpy-only analyzer...")
                analyzer = VoiceAnalyzer()
                ok, _, err = analyzer.Run("load", {"path": self.audio_path})
                if not ok:
                    self.error.emit(f"Load failed: {err}")
                    return
                self.progress.emit("Analyzing...")
                ok, features, err = analyzer.Run("analyze", None)
            else:
                self.progress.emit("Extracting features...")
                ok, features, err = dna.Run("analyze", None)

            if not ok:
                self.error.emit(f"Analysis failed: {err}")
                return
            self.finished_analysis.emit(features)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Match — compare user features to Kokoro reference DB
# =============================================================================

class MatchWorker(QThread):
    progress = pyqtSignal(str)
    finished_match = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, user_features, ref_db, top_n=10):
        super().__init__()
        self.user_features = user_features
        self.ref_db = ref_db
        self.top_n = top_n

    def run(self):
        try:
            self.progress.emit("Matching to 28 Kokoro voices...")
            results = match_voice(self.user_features, self.ref_db, top_n=self.top_n)
            self.finished_match.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# TTS — generate + play Kokoro voice samples
# =============================================================================

class TTSWorker(QThread):
    progress = pyqtSignal(str)
    finished_tts = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, text, voice, output_path):
        super().__init__()
        self.text = text
        self.voice = voice
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(f"Generating '{self.voice}'...")
            result = subprocess.run(
                [PYTHON3, KOKORO_SCRIPT, self.text, self.voice, self.output_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0 or not os.path.exists(self.output_path):
                self.error.emit(f"TTS failed: {result.stderr[:200]}")
                return
            self.progress.emit("Playing...")
            subprocess.run(["/usr/bin/afplay", self.output_path], timeout=60)
            self.finished_tts.emit()
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Helper functions — audio utilities for the GUI
# =============================================================================

def list_input_devices():
    """Return list of (index, name, is_default) for all input devices."""
    devices = sd.query_devices()
    default_in = sd.default.device[0]
    result = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            result.append((i, d["name"], i == default_in))
    return result


def list_recordings():
    """Return list of (filename, full_path) for saved recordings, newest first."""
    return [(r.name, str(r)) for r in sorted(RECORDINGS_DIR.glob("rec_*.wav"), reverse=True)]


def play_audio_file(path):
    """Play a WAV file asynchronously via afplay. Returns True if started."""
    if not path or not os.path.exists(path):
        return False
    subprocess.Popen(["/usr/bin/afplay", path])
    return True

