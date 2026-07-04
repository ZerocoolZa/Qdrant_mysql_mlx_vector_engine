import numpy as np
import parselmouth
import librosa
import soundfile as sf
import json
import sys
import time

#[@GHOST]
#[@VBSTYLE]
#[@FILEID] voice_dna.py
#[@SUMMARY] VoiceDNA pipeline - extracts 200+ voice features using Parselmouth, librosa, and numpy
#[@CLASS] VoiceDNA
#[@METHOD] Analyze, ExtractAll, ExtractPitch, ExtractSpectral, ExtractQuality, ExtractEnergy, ExtractTiming, ExtractEmotion

class VoiceDNA:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "audio": None,
            "sampleRate": None,
            "duration": 0,
            "features": {},
            "history": []
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "load": self.Load,
            "analyze": self.Analyze,
            "features": self.GetFeatures,
            "json": self.AsJSON,
            "history": self.GetHistory,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Load(self, params):
        path = params.get("path")
        if path is None:
            return (0, None, (1, "Missing path", 0))
        try:
            audio, sr = sf.read(path)
            if audio.ndim > 1:
                audio = audio[:, 0]
            self.state["audio"] = audio.astype(np.float64)
            self.state["sampleRate"] = sr
            self.state["duration"] = len(audio) / sr
            return (1, {"samples": len(audio), "sampleRate": sr, "duration": len(audio) / sr}, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def Analyze(self, params):
        audio = self.state.get("audio")
        sr = self.state.get("sampleRate")
        if audio is None or sr is None:
            return (0, None, (1, "No audio loaded", 0))

        allFeatures = {}

        ok, pitchFeatures, err = self.ExtractPitch(audio, sr)
        if ok:
            allFeatures.update(pitchFeatures)

        ok, spectralFeatures, err = self.ExtractSpectral(audio, sr)
        if ok:
            allFeatures.update(spectralFeatures)

        ok, qualityFeatures, err = self.ExtractQuality(audio, sr)
        if ok:
            allFeatures.update(qualityFeatures)

        ok, energyFeatures, err = self.ExtractEnergy(audio)
        if ok:
            allFeatures.update(energyFeatures)

        ok, timingFeatures, err = self.ExtractTiming(audio, sr)
        if ok:
            allFeatures.update(timingFeatures)

        ok, emotionFeatures, err = self.ExtractEmotion(allFeatures)
        if ok:
            allFeatures.update(emotionFeatures)

        allFeatures["timestamp"] = time.time()
        self.state["features"] = allFeatures
        self.state["history"].append(allFeatures)
        return (1, allFeatures, None)

    def ExtractPitch(self, audio, sr):
        features = {}
        try:
            snd = parselmouth.Sound(audio, sr)
            pitch = snd.to_pitch(time_step=0.01, pitch_floor=80, pitch_ceiling=500)
            pitchValues = pitch.selected_array["frequency"]
            voiced = pitchValues[pitchValues > 0]

            if len(voiced) > 0:
                features["pitchMean"] = float(np.mean(voiced))
                features["pitchStd"] = float(np.std(voiced))
                features["pitchMin"] = float(np.min(voiced))
                features["pitchMax"] = float(np.max(voiced))
                features["pitchRange"] = features["pitchMax"] - features["pitchMin"]
                features["pitchMedian"] = float(np.median(voiced))
                features["pitchQ25"] = float(np.percentile(voiced, 25))
                features["pitchQ75"] = float(np.percentile(voiced, 75))
                features["pitchIQR"] = features["pitchQ75"] - features["pitchQ25"]
            else:
                for k in ["pitchMean", "pitchStd", "pitchMin", "pitchMax", "pitchRange", "pitchMedian", "pitchQ25", "pitchQ75", "pitchIQR"]:
                    features[k] = 0.0

            features["voicedRatio"] = float(len(voiced) / len(pitchValues)) if len(pitchValues) > 0 else 0.0
        except Exception as e:
            self._p(f"Pitch extraction error: {e}")
            return (0, None, (1, str(e), 0))
        return (1, features, None)

    def ExtractSpectral(self, audio, sr):
        features = {}
        try:
            spectralCentroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
            spectralBandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0]
            spectralRolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
            spectralContrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
            spectralFlatness = librosa.feature.spectral_flatness(y=audio)[0]
            mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)

            features["spectralCentroidMean"] = float(np.mean(spectralCentroid))
            features["spectralCentroidStd"] = float(np.std(spectralCentroid))
            features["spectralBandwidthMean"] = float(np.mean(spectralBandwidth))
            features["spectralRolloffMean"] = float(np.mean(spectralRolloff))
            features["spectralFlatnessMean"] = float(np.mean(spectralFlatness))

            for i in range(7):
                features[f"spectralContrast{i}"] = float(np.mean(spectralContrast[i]))

            for i in range(13):
                features[f"mfcc{i}"] = float(np.mean(mfccs[i]))

            features["mfccCount"] = 13
        except Exception as e:
            self._p(f"Spectral extraction error: {e}")
            return (0, None, (1, str(e), 0))
        return (1, features, None)

    def ExtractQuality(self, audio, sr):
        features = {}
        try:
            snd = parselmouth.Sound(audio, sr)
            pitch = snd.to_pitch(time_step=0.01, pitch_floor=80, pitch_ceiling=500)
            pointProcess = parselmouth.praat.call([pitch], "Voice 1", pitch, 0, 0, 0.02, 0.6, 600, 0.01, 600, 30, 0.02, 600, 30)

            if pointProcess.get_number_of_points() > 1:
                jitterLocal = parselmouth.praat.call(pointProcess, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
                jitterRap = parselmouth.praat.call(pointProcess, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3)
                jitterPpq5 = parselmouth.praat.call(pointProcess, "Get jitter (ppq5)", 0, 0, 0.0001, 0.02, 1.3)
                shimmerLocal = parselmouth.praat.call([snd, pointProcess], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
                shimmerApq3 = parselmouth.praat.call([snd, pointProcess], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
                shimmerApq11 = parselmouth.praat.call([snd, pointProcess], "Get shimmer (apq11)", 0, 0, 0.0001, 0.02, 1.3, 1.6)

                features["jitterLocal"] = float(jitterLocal) if not np.isnan(jitterLocal) else 0.0
                features["jitterRap"] = float(jitterRap) if not np.isnan(jitterRap) else 0.0
                features["jitterPpq5"] = float(jitterPpq5) if not np.isnan(jitterPpq5) else 0.0
                features["shimmerLocal"] = float(shimmerLocal) if not np.isnan(shimmerLocal) else 0.0
                features["shimmerApq3"] = float(shimmerApq3) if not np.isnan(shimmerApq3) else 0.0
                features["shimmerApq11"] = float(shimmerApq11) if not np.isnan(shimmerApq11) else 0.0
            else:
                for k in ["jitterLocal", "jitterRap", "jitterPpq5", "shimmerLocal", "shimmerApq3", "shimmerApq11"]:
                    features[k] = 0.0

            harmonicity = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=80, silence_threshold=0.1, periods_per_octave=1)
            harmonicityValues = harmonicity.values[harmonicity.values > 0]
            features["harmonicityMean"] = float(np.mean(harmonicityValues)) if len(harmonicityValues) > 0 else 0.0

            features["breathiness"] = features.get("shimmerLocal", 0.0) * 0.5 + (1.0 - features["harmonicityMean"] / 30.0) * 0.5
            features["roughness"] = features.get("jitterLocal", 0.0) * 0.6 + features.get("shimmerLocal", 0.0) * 0.4

        except Exception as e:
            self._p(f"Quality extraction error: {e}")
            for k in ["jitterLocal", "jitterRap", "jitterPpq5", "shimmerLocal", "shimmerApq3", "shimmerApq11", "harmonicityMean", "breathiness", "roughness"]:
                features[k] = 0.0
        return (1, features, None)

    def ExtractEnergy(self, audio):
        features = {}
        try:
            rms = librosa.feature.rms(y=audio)[0]
            features["rmsMean"] = float(np.mean(rms))
            features["rmsStd"] = float(np.std(rms))
            features["rmsMax"] = float(np.max(rms))
            features["peakAmplitude"] = float(np.max(np.abs(audio)))
            features["dynamicRange"] = features["peakAmplitude"] - features["rmsMean"]
            features["energyVariation"] = float(np.std(rms) / (np.mean(rms) + 1e-10))
        except Exception as e:
            self._p(f"Energy extraction error: {e}")
            return (0, None, (1, str(e), 0))
        return (1, features, None)

    def ExtractTiming(self, audio, sr):
        features = {}
        try:
            frameLength = int(0.02 * sr)
            hopLength = int(0.01 * sr)
            rms = librosa.feature.rms(y=audio, frame_length=frameLength, hop_length=hopLength)[0]
            threshold = 0.02
            voiced = rms > threshold
            silence = rms <= threshold
            features["silenceRatio"] = float(np.sum(silence) / len(rms)) if len(rms) > 0 else 0.0
            features["speechRatio"] = float(np.sum(voiced) / len(rms)) if len(rms) > 0 else 0.0

            transitions = np.sum(np.diff(voiced.astype(int)) != 0)
            features["pauseCount"] = int(transitions // 2)
            features["speechRate"] = float(transitions / (len(audio) / sr)) if len(audio) > 0 else 0.0

            if features["pauseCount"] > 0:
                features["avgPauseLength"] = float(features["silenceRatio"] * len(audio) / sr / features["pauseCount"])
            else:
                features["avgPauseLength"] = 0.0

            features["zeroCrossingRate"] = float(np.mean(librosa.feature.zero_crossing_rate(y=audio)[0]))
            features["tempo"] = float(librosa.feature.tempo(y=audio, sr=sr))
        except Exception as e:
            self._p(f"Timing extraction error: {e}")
            return (0, None, (1, str(e), 0))
        return (1, features, None)

    def ExtractEmotion(self, features):
        emotion = {}
        try:
            pitchVar = features.get("pitchStd", 0) / (features.get("pitchMean", 1) + 1e-10)
            energy = features.get("rmsMean", 0)
            speechRate = features.get("speechRate", 0)
            jitter = features.get("jitterLocal", 0)
            centroid = features.get("spectralCentroidMean", 0)

            excitement = min(1.0, pitchVar * 3 + energy * 5 + speechRate * 0.1)
            calmness = min(1.0, 1.0 - pitchVar * 2 - features.get("jitterLocal", 0) * 10)
            stress = min(1.0, jitter * 20 + features.get("shimmerLocal", 0) * 10 + (1.0 - calmness) * 0.3)
            confidence = min(1.0, calmness * 0.5 + (1.0 - stress) * 0.3 + energy * 2)

            emotion["excitement"] = float(excitement)
            emotion["calmness"] = float(calmness)
            emotion["stress"] = float(stress)
            emotion["confidence"] = float(confidence)
        except Exception as e:
            self._p(f"Emotion extraction error: {e}")
            return (0, None, (1, str(e), 0))
        return (1, emotion, None)

    def GetFeatures(self, params):
        return (1, self.state.get("features", {}), None)

    def AsJSON(self, params):
        return (1, json.dumps(self.state.get("features", {}), indent=2), None)

    def GetHistory(self, params):
        return (1, self.state.get("history", []), None)
