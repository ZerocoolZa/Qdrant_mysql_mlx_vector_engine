import numpy as np
import json
import sys
import time

#[@GHOST]
#[@VBSTYLE]
#[@FILEID] voice_engine.py
#[@SUMMARY] Unified voice analysis engine — merges VoiceDNA (parselmouth/librosa 200+ features), VoiceAnalyzer (numpy-only fallback), and VoiceMatrixMapper (Kokoro voice matrix correlation)
#[@CLASS] VoiceDNA, VoiceAnalyzer, VoiceMatrixMapper
#[@METHOD] Run, Load, Analyze, Compare, ExtractPitch, ExtractSpectral, ExtractQuality, ExtractEnergy, ExtractTiming, ExtractEmotion, LoadMatrix, AddVoice, Correlate, Construct

# Optional deps — VoiceDNA needs these, VoiceAnalyzer does not
try:
    import parselmouth
    HAS_PARSELMOUTH = True
except ImportError:
    HAS_PARSELMOUTH = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import scipy.signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

import wave


# =============================================================================
# VoiceDNA — 200+ features via parselmouth + librosa (primary analyzer)
# =============================================================================

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


# =============================================================================
# VoiceAnalyzer — numpy-only fallback (no parselmouth/librosa needed)
# =============================================================================

class VoiceAnalyzer:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "sampleRate": None,
            "audio": None,
            "duration": 0,
            "features": {}
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "load": self.Load,
            "analyze": self.Analyze,
            "compare": self.Compare,
            "features": self.GetFeatures,
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
            self.state["audio"] = audio
            self.state["sampleRate"] = sr
            self.state["duration"] = len(audio) / sr
            return (1, {"samples": len(audio), "sampleRate": sr, "duration": len(audio) / sr}, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def Analyze(self, params):
        audio = self.state.get("audio")
        sr = self.state.get("sampleRate")
        if audio is None or sr is None:
            return (0, None, (1, "No audio loaded. Run Load first.", 0))

        features = {}

        features["pitchMean"] = self.ExtractPitchMean(audio, sr)
        features["pitchStd"] = self.ExtractPitchStd(audio, sr)
        features["pitchRange"] = features["pitchMean"] + features["pitchStd"]
        features["spectralCentroid"] = self.ExtractSpectralCentroid(audio, sr)
        features["zeroCrossingRate"] = self.ExtractZeroCrossingRate(audio)
        features["rmsEnergy"] = self.ExtractRMSEnergy(audio)
        features["spectralRolloff"] = self.ExtractSpectralRolloff(audio, sr)
        features["spectralFlux"] = self.ExtractSpectralFlux(audio, sr)
        features["formant1"], features["formant2"] = self.ExtractFormants(audio, sr)
        features["breathiness"] = self.ExtractBreathiness(audio, sr)
        features["speechRate"] = self.ExtractSpeechRate(audio, sr)

        self.state["features"] = features
        return (1, features, None)

    def Compare(self, params):
        otherFeatures = params.get("other")
        if otherFeatures is None:
            return (0, None, (1, "Missing other features", 0))
        myFeatures = self.state.get("features", {})
        if not myFeatures:
            return (0, None, (1, "No features. Run Analyze first.", 0))

        diffs = {}
        for key in myFeatures:
            if key in otherFeatures:
                mine = myFeatures[key]
                theirs = otherFeatures[key]
                if theirs != 0:
                    diffs[key] = abs(mine - theirs) / abs(theirs)
                else:
                    diffs[key] = abs(mine - theirs)

        totalDiff = sum(diffs.values()) / len(diffs) if diffs else 0
        return (1, {"diffs": diffs, "totalDiff": totalDiff}, None)

    def GetFeatures(self, params):
        return (1, self.state.get("features", {}), None)

    def ExtractPitchMean(self, audio, sr):
        frameLength = int(0.04 * sr)
        hopLength = int(0.02 * sr)
        pitches = []
        for i in range(0, len(audio) - frameLength, hopLength):
            frame = audio[i:i + frameLength]
            if np.max(np.abs(frame)) < 0.01:
                continue
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(corr)//2:]
            minLag = int(sr / 500)
            maxLag = int(sr / 80)
            if maxLag >= len(corr):
                maxLag = len(corr) - 1
            if minLag >= maxLag:
                continue
            peak = np.argmax(corr[minLag:maxLag]) + minLag
            if corr[peak] > 0.3 * corr[0]:
                pitches.append(sr / peak)
        return float(np.mean(pitches)) if pitches else 0.0

    def ExtractPitchStd(self, audio, sr):
        frameLength = int(0.04 * sr)
        hopLength = int(0.02 * sr)
        pitches = []
        for i in range(0, len(audio) - frameLength, hopLength):
            frame = audio[i:i + frameLength]
            if np.max(np.abs(frame)) < 0.01:
                continue
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(corr)//2:]
            minLag = int(sr / 500)
            maxLag = int(sr / 80)
            if maxLag >= len(corr):
                maxLag = len(corr) - 1
            if minLag >= maxLag:
                continue
            peak = np.argmax(corr[minLag:maxLag]) + minLag
            if corr[peak] > 0.3 * corr[0]:
                pitches.append(sr / peak)
        return float(np.std(pitches)) if pitches else 0.0

    def ExtractSpectralCentroid(self, audio, sr):
        fftSize = 2048
        if len(audio) < fftSize:
            audio = np.pad(audio, (0, fftSize - len(audio)))
        spectrum = np.abs(np.fft.rfft(audio[:fftSize]))
        freqs = np.fft.rfftfreq(fftSize, 1 / sr)
        if spectrum.sum() == 0:
            return 0.0
        return float(np.sum(freqs * spectrum) / np.sum(spectrum))

    def ExtractZeroCrossingRate(self, audio):
        if len(audio) < 2:
            return 0.0
        signs = np.sign(audio)
        diff = np.diff(signs)
        crossings = np.sum(np.abs(diff) > 0)
        return float(crossings / len(audio))

    def ExtractRMSEnergy(self, audio):
        return float(np.sqrt(np.mean(audio ** 2)))

    def ExtractSpectralRolloff(self, audio, sr):
        fftSize = 2048
        if len(audio) < fftSize:
            audio = np.pad(audio, (0, fftSize - len(audio)))
        spectrum = np.abs(np.fft.rfft(audio[:fftSize]))
        total = np.sum(spectrum)
        if total == 0:
            return 0.0
        cumulative = np.cumsum(spectrum)
        rolloffIdx = np.searchsorted(cumulative, 0.85 * total)
        freqs = np.fft.rfftfreq(fftSize, 1 / sr)
        return float(freqs[min(rolloffIdx, len(freqs) - 1)])

    def ExtractSpectralFlux(self, audio, sr):
        fftSize = 1024
        hopSize = 512
        if len(audio) < fftSize + hopSize:
            return 0.0
        prevSpectrum = None
        fluxValues = []
        for i in range(0, len(audio) - fftSize, hopSize):
            frame = audio[i:i + fftSize]
            spectrum = np.abs(np.fft.rfft(frame))
            if prevSpectrum is not None:
                diff = spectrum - prevSpectrum
                flux = np.sum(np.maximum(diff, 0) ** 2)
                fluxValues.append(flux)
            prevSpectrum = spectrum
        return float(np.mean(fluxValues)) if fluxValues else 0.0

    def ExtractFormants(self, audio, sr):
        frameLength = int(0.04 * sr)
        if len(audio) < frameLength:
            return 0.0, 0.0
        frame = audio[:frameLength]
        frame = frame * np.hamming(frameLength)
        lpcOrder = 2 + int(sr / 1000)
        try:
            lpc = self.LPC(frame, lpcOrder)
            roots = np.roots(lpc)
            roots = roots[np.imag(roots) >= 0]
            angles = np.arctan2(np.imag(roots), np.real(roots))
            freqs = angles * sr / (2 * np.pi)
            freqs = np.sort(freqs[freqs > 90])
            f1 = float(freqs[0]) if len(freqs) > 0 else 0.0
            f2 = float(freqs[1]) if len(freqs) > 1 else 0.0
            return f1, f2
        except Exception:
            return 0.0, 0.0

    def LPC(self, signal, order):
        acf = np.correlate(signal, signal, mode='full')
        acf = acf[len(acf)//2:]
        R = acf[:order + 1]
        A = np.zeros(order + 1)
        A[0] = 1.0
        E = R[0]
        for i in range(order):
            if E == 0:
                break
            k = -np.sum(A[:i+1] * R[i+1:0:-1]) / E
            A[i+1] = k
            for j in range(i):
                A[j+1] = A[j+1] + k * A[i-j-1]
            E = E * (1 - k * k)
        return A

    def ExtractBreathiness(self, audio, sr):
        fftSize = 2048
        if len(audio) < fftSize:
            audio = np.pad(audio, (0, fftSize - len(audio)))
        spectrum = np.abs(np.fft.rfft(audio[:fftSize]))
        spectrum = spectrum + 1e-10
        geoMean = np.exp(np.mean(np.log(spectrum)))
        arithMean = np.mean(spectrum)
        if arithMean == 0:
            return 0.0
        return float(geoMean / arithMean)

    def ExtractSpeechRate(self, audio, sr):
        frameLength = int(0.02 * sr)
        hopLength = int(0.01 * sr)
        voiced = []
        for i in range(0, len(audio) - frameLength, hopLength):
            frame = audio[i:i + frameLength]
            rms = np.sqrt(np.mean(frame ** 2))
            voiced.append(1 if rms > 0.05 else 0)
        transitions = sum(1 for i in range(1, len(voiced)) if voiced[i] != voiced[i-1])
        return float(transitions / (len(audio) / sr)) if len(audio) > 0 else 0.0


# =============================================================================
# VoiceMatrixMapper — correlates voice features to Kokoro voice matrix
# =============================================================================

class VoiceMatrixMapper:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "voiceFeatures": {},
            "matrixData": None,
            "correlations": {}
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "loadMatrix": self.LoadMatrix,
            "addVoice": self.AddVoice,
            "correlate": self.Correlate,
            "construct": self.Construct,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def LoadMatrix(self, params):
        path = params.get("path", "/Users/wws/KokoroModels/voices.npy")
        raw = np.load(path, allow_pickle=True)
        data = raw.item()
        self.state["matrixData"] = data
        return (1, {"voices": len(data)}, None)

    def AddVoice(self, params):
        name = params.get("name")
        features = params.get("features")
        if name is None or features is None:
            return (0, None, (1, "Missing name or features", 0))
        self.state["voiceFeatures"][name] = features
        return (1, True, None)

    def Correlate(self, params):
        matrixData = self.state.get("matrixData")
        voiceFeatures = self.state.get("voiceFeatures", {})
        if matrixData is None or not voiceFeatures:
            return (0, None, (1, "Need matrix and voice features", 0))

        featureNames = list(list(voiceFeatures.values())[0].keys())
        correlations = {}

        for featName in featureNames:
            featValues = []
            matrixValues = []
            for voiceName, feats in voiceFeatures.items():
                if voiceName in matrixData and featName in feats:
                    featValues.append(feats[featName])
                    matrixValues.append(matrixData[voiceName].flatten())

            if len(featValues) < 3:
                continue

            featValues = np.array(featValues)
            matrixValues = np.array(matrixValues)

            colCorr = []
            for col in range(matrixValues.shape[1]):
                if np.std(matrixValues[:, col]) > 0 and np.std(featValues) > 0:
                    c = np.corrcoef(featValues, matrixValues[:, col])[0, 1]
                    colCorr.append((col, abs(c)))
                else:
                    colCorr.append((col, 0.0))

            colCorr.sort(key=lambda x: x[1], reverse=True)
            correlations[featName] = colCorr[:10]

        self.state["correlations"] = correlations
        return (1, correlations, None)

    def Construct(self, params):
        targetFeatures = params.get("target")
        if targetFeatures is None:
            return (0, None, (1, "Missing target features", 0))

        matrixData = self.state.get("matrixData")
        correlations = self.state.get("correlations")
        if matrixData is None or not correlations:
            return (0, None, (1, "Need matrix and correlations", 0))

        baseVoice = params.get("base", "am_michael")
        if baseVoice not in matrixData:
            return (0, None, (1, "Base voice not found: " + baseVoice, 0))

        newMatrix = matrixData[baseVoice].copy().astype(np.float32)
        voiceFeatures = self.state.get("voiceFeatures", {})

        for featName, targetVal in targetFeatures.items():
            if featName not in correlations:
                continue

            baseVal = voiceFeatures.get(baseVoice, {}).get(featName, 0)
            if baseVal == 0:
                continue

            ratio = targetVal / baseVal

            for col, corr in correlations[featName][:5]:
                if corr > 0.3:
                    baseCol = matrixData[baseVoice].flatten()[col]
                    newMatrix.flatten()[col] = baseCol * ratio

        return (1, {"matrix": newMatrix, "shape": newMatrix.shape}, None)


# =============================================================================
# Auto-select: use VoiceDNA if deps available, else VoiceAnalyzer
# =============================================================================

def AutoAnalyze(path):
    """One-shot helper: load + analyze a WAV. Returns (ok, features, err)."""
    if HAS_PARSELMOUTH and HAS_LIBROSA:
        engine = VoiceDNA()
    else:
        engine = VoiceAnalyzer()
    ok, _, err = engine.Run("load", {"path": path})
    if not ok:
        return (0, None, err)
    return engine.Run("analyze", None)
