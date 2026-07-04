import numpy as np
import scipy.signal
import soundfile as sf
import wave
import os
import sys

#[@GHOST]
#[@VBSTYLE]
#[@FILEID] voice_analyzer.py
#[@SUMMARY] Analyzes voice audio to extract acoustic features for Kokoro voice matrix reverse-engineering
#[@CLASS] VoiceAnalyzer
#[@METHOD] Analyze, Compare, ExtractFeatures

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

        # 1. Pitch (F0) via autocorrelation
        features["pitchMean"] = self.ExtractPitchMean(audio, sr)
        features["pitchStd"] = self.ExtractPitchStd(audio, sr)
        features["pitchRange"] = features["pitchMean"] + features["pitchStd"]

        # 2. Spectral centroid (brightness)
        features["spectralCentroid"] = self.ExtractSpectralCentroid(audio, sr)

        # 3. Zero-crossing rate (noisiness/voicing)
        features["zeroCrossingRate"] = self.ExtractZeroCrossingRate(audio)

        # 4. RMS energy
        features["rmsEnergy"] = self.ExtractRMSEnergy(audio)

        # 5. Spectral rolloff (high frequency content)
        features["spectralRolloff"] = self.ExtractSpectralRolloff(audio, sr)

        # 6. Spectral flux (spectral change rate)
        features["spectralFlux"] = self.ExtractSpectralFlux(audio, sr)

        # 7. Formant estimates via LPC
        features["formant1"], features["formant2"] = self.ExtractFormants(audio, sr)

        # 8. Breathiness (spectral flatness)
        features["breathiness"] = self.ExtractBreathiness(audio, sr)

        # 9. Speech rate estimate (voiced segment count)
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
