#!/usr/bin/env python3
# [@GHOST]{[@file<VoicePacket.py>][@domain<voice_pipeline>][@role<protocol>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<BCL tone packet — the protocol that carries transcript + emotional context to AI agents>]}
# [@VBSTYLE]{[@auth<devin>][@role<protocol>][@return<Tuple3>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{VoicePacket — the BCL tone packet format. Carries BOTH transcript (what you said) AND tone (how you said it). Emotion, energy, pitch, stress, prosody, emphasis. The AI receives both.}
# [@FILEID]{VoicePacket.py}
# [@CLASS]{VoicePacket}
# [@METHOD]{Run, Build, FromFeatures, ToBCL, ToJSON, FromBCL, FromJSON, Classify, ResolveVoice}

import json
import time
import sys


class VoicePacket:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "packet": {},
            "history": [],
        }

    def _p(self, msg):
        sys.stderr.write(str(msg) + "\n")

    def Run(self, command, params=None):
        dispatch = {
            "build": self.Build,
            "fromFeatures": self.FromFeatures,
            "toBCL": self.ToBCL,
            "toJSON": self.ToJSON,
            "fromBCL": self.FromBCL,
            "fromJSON": self.FromJSON,
            "classify": self.Classify,
            "resolveVoice": self.ResolveVoice,
            "history": self.GetHistory,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (1, "Unknown command: " + str(command), 0))
        return handler(params)

    def Build(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        tone = params.get("tone", {})
        packet = {
            "text": text,
            "tone": tone,
            "timestamp": time.time(),
        }
        self.state["packet"] = packet
        self.state["history"].append(packet)
        return (1, packet, None)

    def FromFeatures(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        text = params.get("text", "")
        features = params.get("features", {})
        emotion = params.get("emotion", {})

        excitement = emotion.get("excitement", 0.0)
        calmness = emotion.get("calmness", 0.5)
        stress = emotion.get("stress", 0.0)
        confidence = emotion.get("confidence", 0.5)

        pitchMean = features.get("pitchMean", 0)
        pitchStd = features.get("pitchStd", 0)
        rmsMean = features.get("rmsMean", 0)
        speechRate = features.get("speechRate", 0)
        silenceRatio = features.get("silenceRatio", 0)

        if pitchMean > 180:
            pitchLevel = "high"
        elif pitchMean > 120:
            pitchLevel = "medium"
        else:
            pitchLevel = "low"

        if pitchStd > 40:
            pitchVar = "very_high"
        elif pitchStd > 20:
            pitchVar = "high"
        elif pitchStd > 10:
            pitchVar = "medium"
        else:
            pitchVar = "low"

        if rmsMean > 0.1:
            volume = "high"
        elif rmsMean > 0.04:
            volume = "medium"
        else:
            volume = "low"

        if speechRate > 4:
            pace = "fast"
        elif speechRate > 2:
            pace = "medium"
        else:
            pace = "slow"

        happiness = min(1.0, excitement * 0.7 + calmness * 0.3)
        energy = min(1.0, rmsMean * 8 + excitement * 0.3)
        engagement = min(1.0, (1.0 - silenceRatio) * 0.6 + excitement * 0.4)
        urgency = min(1.0, speechRate * 0.15 + stress * 0.4 + excitement * 0.3)
        certainty = min(1.0, confidence * 0.6 + calmness * 0.4)

        mood = self._MoodFromScores(excitement, calmness, stress, confidence)
        prosody = self._ProsodyFromScores(pace, pitchVar, volume, excitement)

        tone = {
            "excitement": round(excitement, 3),
            "happiness": round(happiness, 3),
            "confidence": round(confidence, 3),
            "stress": round(stress, 3),
            "calmness": round(calmness, 3),
            "energy": round(energy, 3),
            "speaking_rate": round(speechRate, 3),
            "pitch_level": pitchLevel,
            "pitch_variation": pitchVar,
            "pitch_mean_hz": round(pitchMean, 2),
            "volume": volume,
            "mood": mood,
            "prosody": prosody,
            "urgency": round(urgency, 3),
            "engagement": round(engagement, 3),
            "certainty": round(certainty, 3),
            "analysis_confidence": 0.85,
        }

        packet = {
            "text": text,
            "tone": tone,
            "timestamp": time.time(),
        }
        self.state["packet"] = packet
        self.state["history"].append(packet)
        return (1, packet, None)

    def _MoodFromScores(self, excitement, calmness, stress, confidence):
        if stress > 0.6 and excitement < 0.3:
            return "stressed"
        if excitement > 0.7 and happiness_score(excitement, calmness) > 0.7:
            return "happy"
        if calmness > 0.7 and stress < 0.2:
            return "calm"
        if confidence > 0.7 and excitement > 0.4:
            return "confident"
        if excitement < 0.2 and calmness < 0.4:
            return "sad"
        if stress > 0.5:
            return "tense"
        return "neutral"

    def _ProsodyFromScores(self, pace, pitchVar, volume, excitement):
        if excitement > 0.6 and pace == "fast":
            return "animated"
        if pace == "slow" and pitchVar == "low":
            return "monotone"
        if volume == "high" and pitchVar in ("high", "very_high"):
            return "expressive"
        if pace == "medium" and pitchVar == "medium":
            return "steady"
        return "neutral"

    def ToBCL(self, params):
        packet = self.state.get("packet", {})
        if not packet:
            return (0, None, (1, "No packet built", 0))
        tone = packet.get("tone", {})
        text = packet.get("text", "")

        lines = []
        lines.append("[@VOICE_PACKET]")
        lines.append("{")
        lines.append('  [@TEXT]{"' + text.replace('"', '\\"') + '"}')
        lines.append("  [@TONE]")
        lines.append("  {")
        for k, v in tone.items():
            if isinstance(v, str):
                lines.append('    [@' + k.upper() + ']{"' + v + '"}')
            else:
                lines.append('    [@' + k.upper() + ']{' + str(v) + '}')
        lines.append("  }")
        lines.append("}")
        return (1, "\n".join(lines), None)

    def ToJSON(self, params):
        packet = self.state.get("packet", {})
        if not packet:
            return (0, None, (1, "No packet built", 0))
        return (1, json.dumps(packet, indent=2), None)

    def FromBCL(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        bcl = params.get("bcl", "")
        import re
        textMatch = re.search(r'\[@TEXT\]\{"(.*?)"\}', bcl)
        text = textMatch.group(1) if textMatch else ""

        tone = {}
        pattern = r'\[@(\w+)\]\{(?:"(.*?)"|([0-9.]+))\}'
        for m in re.finditer(pattern, bcl):
            key = m.group(1).lower()
            if key == "text":
                continue
            if m.group(2) is not None:
                tone[key] = m.group(2)
            else:
                try:
                    tone[key] = float(m.group(3))
                except ValueError:
                    tone[key] = m.group(3)

        packet = {"text": text, "tone": tone, "timestamp": time.time()}
        self.state["packet"] = packet
        return (1, packet, None)

    def FromJSON(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        try:
            data = json.loads(params.get("json", "{}"))
            self.state["packet"] = data
            return (1, data, None)
        except Exception as e:
            return (0, None, (1, str(e), 0))

    def Classify(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        tone = params.get("tone", self.state.get("packet", {}).get("tone", {}))
        if not tone:
            return (0, None, (1, "No tone data", 0))

        excitement = tone.get("excitement", 0)
        stress = tone.get("stress", 0)
        calmness = tone.get("calmness", 0)
        confidence = tone.get("confidence", 0)

        if stress > 0.6 and excitement < 0.3:
            label = "stressed"
        elif excitement > 0.7:
            label = "excited"
        elif calmness > 0.7 and stress < 0.2:
            label = "calm"
        elif confidence > 0.7 and excitement > 0.4:
            label = "confident"
        elif excitement < 0.2 and calmness < 0.4:
            label = "sad"
        elif stress > 0.5:
            label = "tense"
        else:
            label = "neutral"

        return (1, {"label": label, "scores": tone}, None)

    def ResolveVoice(self, params):
        if params is None:
            return (0, None, (1, "Missing params", 0))
        emotion = params.get("emotion", "neutral")
        voiceMap = params.get("voice_map", {})
        if not voiceMap:
            from Config import EMOTION_VOICE_MAP
            voiceMap = EMOTION_VOICE_MAP
        voice = voiceMap.get(emotion, voiceMap.get("neutral", "af_alloy"))
        return (1, {"voice": voice, "emotion": emotion}, None)

    def GetHistory(self, params):
        return (1, self.state.get("history", []), None)


def happiness_score(excitement, calmness):
    return min(1.0, excitement * 0.7 + calmness * 0.3)
