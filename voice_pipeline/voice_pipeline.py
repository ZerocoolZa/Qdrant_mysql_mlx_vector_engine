#!/usr/bin/env python3
# [@GHOST]{[@file<voice_pipeline.py>][@domain<voice_pipeline>][@role<cli>][@auth<devin>][@date<2026-07-04>][@ver<1.0>][@context<CLI entry point for the tone-aware voice pipeline>]}
# [@VBSTYLE]{[@auth<devin>][@role<cli>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Voice Pipeline CLI — tone-aware voice interaction. Mic → STT + tone → VoicePacket → AI → tone-matched TTS reply. The AI hears BOTH what you said AND how you said it.}
# [@FILEID]{voice_pipeline.py}
# [@CLASS]{VoicePipelineCLI}
# [@METHOD]{Run, CmdListen, CmdSpeak, CmdStream, CmdTest, CmdAnalyze, CmdPacket}

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from VoicePipeline import VoicePipeline
from ToneAnalyzer import ToneAnalyzer
from ToneSynthesizer import ToneSynthesizer
from VoicePacket import VoicePacket


class VoicePipelineCLI:

    def __init__(self):
        self.pipeline = VoicePipeline()

    def Run(self):
        parser = argparse.ArgumentParser(
            description="Voice Pipeline — tone-aware voice interaction (STT + emotion + TTS)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
  listen     Record from mic → extract tone + transcript → print VoicePacket
  speak      Text → TTS with tone-matched voice (Kokoro 82M FP16)
  stream     Continuous listen-and-reply loop (N rounds)
  test       Run full pipeline self-test
  analyze    Analyze a WAV file → extract tone packet
  packet     Build a VoicePacket from text + tone scores
  voices     List available Kokoro voices and emotion→voice mapping

Examples:
  python3 voice_pipeline.py listen
  python3 voice_pipeline.py speak --text "Hello Wayne" --voice af_bella
  python3 voice_pipeline.py speak --text "Amazing!" --emotion excited
  python3 voice_pipeline.py stream --rounds 3 --auto-reply
  python3 voice_pipeline.py analyze --file recording.wav
  python3 voice_pipeline.py test
            """,
        )
        sub = parser.add_subparsers(dest="command", required=True)

        p_listen = sub.add_parser("listen", help="Record from mic, extract tone + transcript")
        p_listen.add_argument("--max-duration", type=float, default=30, help="Max recording seconds")
        p_listen.add_argument("--reply", type=str, default="", help="Reply text to speak back")
        p_listen.add_argument("--auto-reply", action="store_true", help="Auto-generate reply based on tone")
        p_listen.add_argument("--json", action="store_true", help="Output as JSON")

        p_speak = sub.add_parser("speak", help="Text → TTS with tone-matched voice")
        p_speak.add_argument("--text", required=True, help="Text to speak")
        p_speak.add_argument("--voice", default=None, help="Kokoro voice name")
        p_speak.add_argument("--emotion", default=None, help="Emotion: excited/happy/calm/confident/serious/sad/angry/neutral")
        p_speak.add_argument("--no-play", action="store_true", help="Don't play audio, just save")

        p_stream = sub.add_parser("stream", help="Continuous listen-and-reply loop")
        p_stream.add_argument("--rounds", type=int, default=3, help="Number of rounds")
        p_stream.add_argument("--auto-reply", action="store_true", help="Auto-generate replies")
        p_stream.add_argument("--max-duration", type=float, default=30)

        p_test = sub.add_parser("test", help="Run full pipeline self-test")

        p_analyze = sub.add_parser("analyze", help="Analyze a WAV file → extract tone packet")
        p_analyze.add_argument("--file", required=True, help="WAV file path")
        p_analyze.add_argument("--text", default="", help="Associated text (optional)")
        p_analyze.add_argument("--bcl", action="store_true", help="Output as BCL packet")

        p_packet = sub.add_parser("packet", help="Build a VoicePacket from text + tone scores")
        p_packet.add_argument("--text", required=True)
        p_packet.add_argument("--excitement", type=float, default=0.5)
        p_packet.add_argument("--stress", type=float, default=0.3)
        p_packet.add_argument("--calmness", type=float, default=0.5)
        p_packet.add_argument("--confidence", type=float, default=0.5)
        p_packet.add_argument("--bcl", action="store_true", help="Output as BCL")

        sub.add_parser("voices", help="List available voices and emotion mapping")

        args = parser.parse_args()

        if args.command == "listen":
            return self.CmdListen(args)
        elif args.command == "speak":
            return self.CmdSpeak(args)
        elif args.command == "stream":
            return self.CmdStream(args)
        elif args.command == "test":
            return self.CmdTest(args)
        elif args.command == "analyze":
            return self.CmdAnalyze(args)
        elif args.command == "packet":
            return self.CmdPacket(args)
        elif args.command == "voices":
            return self.CmdVoices(args)

    def CmdListen(self, args):
        params = {"maxDuration": args.max_duration}
        if args.reply:
            params["reply"] = args.reply
        if args.auto_reply:
            params["autoReply"] = True

        if args.reply or args.auto_reply:
            ok, result, err = self.pipeline.Run("listenAndReply", params)
        else:
            ok, result, err = self.pipeline.Run("listen", params)

        if not ok:
            sys.stderr.write("Error: " + str(err) + "\n")
            return 1

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print("\n=== VOICE PACKET ===")
            print("Transcript: " + result.get("transcript", ""))
            print("Duration: %.2fs" % result.get("duration", 0))
            tone = result.get("tone", {})
            print("\n--- TONE ---")
            for k, v in tone.items():
                print("  %s: %s" % (k, v))
            if result.get("reply"):
                print("\n--- REPLY ---")
                print("  Text: " + result["reply"])
                print("  Voice: " + str(result.get("replyVoice", "")))
            if result.get("wavPath"):
                print("\nWAV: " + result["wavPath"])
        return 0

    def CmdSpeak(self, args):
        if args.emotion:
            synth = ToneSynthesizer()
            ok, mapping, err = synth.Run("mapEmotionToVoice", {"emotion": args.emotion})
            voice = mapping.get("voice", "af_bella") if ok else "af_bella"
        else:
            voice = args.voice or "af_bella"

        ok, result, err = self.pipeline.Run("speak", {
            "text": args.text,
            "voice": voice,
            "play": not args.no_play,
        })
        if not ok:
            sys.stderr.write("Error: " + str(err) + "\n")
            return 1
        print("Spoke: " + args.text)
        print("Voice: " + str(result.get("voice", voice)))
        print("WAV: " + str(result.get("path", "")))
        return 0

    def CmdStream(self, args):
        params = {"rounds": args.rounds, "maxDuration": args.max_duration}
        if args.auto_reply:
            params["autoReply"] = True
        ok, result, err = self.pipeline.Run("stream", params)
        if not ok:
            sys.stderr.write("Error: " + str(err) + "\n")
            return 1
        print("\n=== STREAM COMPLETE ===")
        print("Rounds: %d" % result.get("count", 0))
        for i, r in enumerate(result.get("rounds", [])):
            print("\n--- Round %d ---" % (i + 1))
            print("  You: " + r.get("transcript", ""))
            if r.get("reply"):
                print("  AI:  " + r["reply"])
            tone = r.get("tone", {})
            print("  Mood: " + str(tone.get("mood", "?")) + "  Excitement: %.2f" % tone.get("excitement", 0))
        return 0

    def CmdTest(self, args):
        print("Running voice pipeline self-test...")
        print("  [1/4] Recording 3 seconds from mic...")
        ok, result, err = self.pipeline.Run("test", None)
        if not ok:
            sys.stderr.write("Test failed: " + str(err) + "\n")
            return 1

        print("\n=== TEST RESULTS ===")
        for component, data in result.items():
            status = "PASS" if data.get("ok") else "FAIL"
            detail = ""
            if data.get("ok"):
                if component == "capture":
                    detail = "duration=%.2fs" % data["data"].get("duration", 0)
                elif component == "saveWav":
                    detail = data.get("path", "")
                elif component == "toneAnalysis":
                    tone = data.get("tone", {})
                    detail = "mood=%s excitement=%.2f" % (tone.get("mood", "?"), tone.get("excitement", 0))
                elif component == "transcription":
                    detail = '"' + str(data.get("text", ""))[:60] + '"'
                elif component == "synthesis":
                    detail = data.get("path", "")
            else:
                detail = str(data.get("error"))
            print("  [%s] %s: %s" % (status, component, detail))
        return 0

    def CmdAnalyze(self, args):
        analyzer = ToneAnalyzer()
        ok, packet, err = analyzer.Run("analyzeFile", {"path": args.file, "text": args.text})
        if not ok:
            sys.stderr.write("Error: " + str(err) + "\n")
            return 1
        if args.bcl:
            vp = VoicePacket()
            vp.state["packet"] = packet
            ok, bcl, err = vp.Run("toBCL", None)
            print(bcl)
        else:
            print(json.dumps(packet, indent=2, default=str))
        return 0

    def CmdPacket(self, args):
        vp = VoicePacket()
        features = {
            "pitchMean": 150,
            "pitchStd": 30,
            "rmsMean": 0.06,
            "speechRate": 3.0,
            "silenceRatio": 0.3,
        }
        emotion = {
            "excitement": args.excitement,
            "calmness": args.calmness,
            "stress": args.stress,
            "confidence": args.confidence,
        }
        ok, packet, err = vp.Run("fromFeatures", {"text": args.text, "features": features, "emotion": emotion})
        if not ok:
            sys.stderr.write("Error: " + str(err) + "\n")
            return 1
        if args.bcl:
            ok, bcl, err = vp.Run("toBCL", None)
            print(bcl)
        else:
            ok, jsn, err = vp.Run("toJSON", None)
            print(jsn)
        return 0

    def CmdVoices(self, args):
        synth = ToneSynthesizer()
        ok, data, err = synth.Run("listVoices", None)
        from Config import EMOTION_VOICE_MAP
        print("=== EMOTION → VOICE MAPPING ===")
        for emotion, voice in EMOTION_VOICE_MAP.items():
            print("  %-15s → %s" % (emotion, voice))
        print("\n=== KOKORO VOICES (28) ===")
        kokoro_voices = [
            "af", "af_alloy", "af_aoede", "af_bella", "af_heart",
            "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
            "af_sarah", "af_sky",
            "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
            "am_michael", "am_onyx", "am_puck", "am_santa",
            "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
            "bm_daniel", "bm_fable", "bm_george",
        ]
        for v in kokoro_voices:
            print("  " + v)
        print("\nModel: /Users/wws/KokoroModels/onnx/model_fp16.onnx (82M FP16)")
        return 0


def main():
    cli = VoicePipelineCLI()
    sys.exit(cli.Run())


if __name__ == "__main__":
    main()
