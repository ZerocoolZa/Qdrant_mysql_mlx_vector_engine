#!/usr/bin/env python3
"""
Build Kokoro Voice Reference Database
Generates a sample sentence with each of the 28 Kokoro voices,
analyzes each with VoiceDNA, and saves the feature profiles.
Run once (takes ~5 min for all 28 voices).
"""
import sys
import os
import json
import time
import subprocess
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from voice_engine import VoiceDNA, VoiceAnalyzer

PYTHON3 = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
KOKORO_SCRIPT = "/Users/wws/Downloads/VoiceTyper/Services/kokoro_tts.py"
KOKORO_VOICES_PATH = "/Users/wws/KokoroModels/voices.npy"
REF_DIR = Path.home() / ".voice_learner" / "reference"
REF_DIR.mkdir(parents=True, exist_ok=True)
REF_AUDIO_DIR = REF_DIR / "audio"
REF_AUDIO_DIR.mkdir(exist_ok=True)
REF_DB_PATH = REF_DIR / "kokoro_reference_db.json"

SAMPLE_TEXT = "The quick brown fox jumps over the lazy dog. This is a test of voice characteristics."

KOKORO_VOICES = [
    "af", "af_alloy", "af_aoede", "af_bella", "af_heart",
    "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george",
]


def generate_voice_sample(voice, output_path):
    """Generate TTS sample with a specific voice."""
    result = subprocess.run(
        [PYTHON3, KOKORO_SCRIPT, SAMPLE_TEXT, voice, output_path],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0 and os.path.exists(output_path)


def analyze_voice(audio_path):
    """Analyze a voice sample and return features."""
    dna = VoiceDNA()
    ok, _, err = dna.Run("load", {"path": audio_path})
    if not ok:
        # Fallback to numpy-only analyzer
        analyzer = VoiceAnalyzer()
        ok, _, err = analyzer.Run("load", {"path": audio_path})
        if not ok:
            return None
        ok, features, err = analyzer.Run("analyze", None)
    else:
        ok, features, err = dna.Run("analyze", None)

    if not ok:
        return None
    return features


def build_reference_db(force_rebuild=False):
    """Generate + analyze all 28 Kokoro voices."""
    if REF_DB_PATH.exists() and not force_rebuild:
        with open(REF_DB_PATH) as f:
            db = json.load(f)
        if len(db.get("voices", {})) >= 28:
            print(f"Reference DB already exists ({len(db['voices'])} voices). Use --force to rebuild.")
            return db

    db = {"voices": {}, "sample_text": SAMPLE_TEXT, "built_at": time.strftime("%Y-%m-%d %H:%M")}
    total = len(KOKORO_VOICES)

    for i, voice in enumerate(KOKORO_VOICES):
        audio_path = str(REF_AUDIO_DIR / f"{voice}.wav")

        # Skip if audio already exists and we have features
        if os.path.exists(audio_path) and voice in db.get("voices", {}):
            print(f"  [{i+1}/{total}] {voice} — cached")
            continue

        print(f"  [{i+1}/{total}] Generating {voice}...", end=" ", flush=True)
        t0 = time.time()

        if not generate_voice_sample(voice, audio_path):
            print("FAILED (TTS)")
            continue

        features = analyze_voice(audio_path)
        if features is None:
            print("FAILED (analysis)")
            continue

        db["voices"][voice] = {
            "features": features,
            "audio_path": audio_path,
            "feature_count": len(features),
        }
        elapsed = time.time() - t0
        pitch = features.get("pitchMean", 0)
        print(f"OK ({elapsed:.1f}s, pitch={pitch:.0f}Hz, {len(features)} features)")

        # Save incrementally
        with open(REF_DB_PATH, "w") as f:
            json.dump(db, f, indent=2, default=str)

    print(f"\nReference DB built: {len(db['voices'])} voices")
    print(f"Saved to: {REF_DB_PATH}")
    return db


def load_reference_db():
    """Load the reference database."""
    if not REF_DB_PATH.exists():
        return None
    with open(REF_DB_PATH) as f:
        return json.load(f)


def match_voice(user_features, ref_db, top_n=5):
    """Match user features to reference database. Returns ranked list."""
    if not ref_db or "voices" not in ref_db:
        return []

    # Features to compare (weighted by importance)
    FEATURE_WEIGHTS = {
        "pitchMean": 3.0,
        "pitchStd": 1.5,
        "pitchRange": 1.0,
        "pitchMedian": 2.0,
        "spectralCentroidMean": 2.0,
        "spectralCentroid": 2.0,
        "spectralBandwidthMean": 1.0,
        "spectralRolloffMean": 1.0,
        "spectralFlatnessMean": 1.0,
        "rmsMean": 0.5,
        "breathiness": 1.5,
        "roughness": 1.0,
        "harmonicityMean": 1.0,
        "jitterLocal": 0.8,
        "shimmerLocal": 0.8,
        "zeroCrossingRate": 1.0,
        "speechRate": 0.5,
        "tempo": 0.5,
    }

    results = []

    for voice_name, voice_data in ref_db["voices"].items():
        ref_features = voice_data["features"]

        total_score = 0
        total_weight = 0
        feature_diffs = {}

        for feat_name, weight in FEATURE_WEIGHTS.items():
            user_val = user_features.get(feat_name)
            ref_val = ref_features.get(feat_name)

            if user_val is None or ref_val is None:
                continue

            # Normalize difference (relative)
            if abs(ref_val) > 1e-10:
                rel_diff = abs(user_val - ref_val) / abs(ref_val)
            else:
                rel_diff = abs(user_val - ref_val)

            # Convert to similarity score (0-1, where 1 = identical)
            similarity = max(0, 1 - min(rel_diff, 1))
            total_score += similarity * weight
            total_weight += weight
            feature_diffs[feat_name] = {
                "user": user_val,
                "ref": ref_val,
                "similarity": similarity,
            }

        if total_weight > 0:
            overall = total_score / total_weight
            results.append({
                "voice": voice_name,
                "score": overall,
                "diffs": feature_diffs,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


if __name__ == "__main__":
    force = "--force" in sys.argv
    print("=" * 60)
    print("Building Kokoro Voice Reference Database")
    print("=" * 60)
    print(f"Sample text: {SAMPLE_TEXT}")
    print(f"Voices: {len(KOKORO_VOICES)}")
    print()

    db = build_reference_db(force_rebuild=force)

    print()
    print("=" * 60)
    print("Reference DB Summary")
    print("=" * 60)
    for name, data in sorted(db["voices"].items(), key=lambda x: x[1]["features"].get("pitchMean", 0)):
        feats = data["features"]
        pitch = feats.get("pitchMean", 0)
        centroid = feats.get("spectralCentroidMean", feats.get("spectralCentroid", 0))
        breath = feats.get("breathiness", 0)
        print(f"  {name:16s}  pitch={pitch:6.1f}Hz  centroid={centroid:6.0f}Hz  breath={breath:.3f}")
