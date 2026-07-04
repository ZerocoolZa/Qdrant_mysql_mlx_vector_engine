#!/usr/bin/env python3
"""
5-Mode Experiment Runner

Tests all 5 inference graph modes from QA_ENGINE_SPEC against the same
28 PinnacleHarness questions:

  Mode A: embed -> search (retrieval only)
  Mode B: embed -> search -> qa_extract -> classify (BERT QA)
  Mode C: embed -> search -> qa_extract -> classify -> llm_format (BERT + LLM)
  Mode D: embed -> search -> llm_extract -> classify (LLM only, no BERT)
  Mode E: qa_extract -> classify (direct QA, no embeddings)

Uses GhostQAEngine for all modes. Config is switched per-run.
"""

import sqlite3
import json
import os
import sys
import time
import urllib.request
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from GhostQAEngine import GhostQAEngine, PIPELINE_MODES, MODE_NAMES
from Config_qa_engine import CONFIG_DICT, PINNACLE_DB_PATH, TEST_COLLECTION as QA_TEST_COLLECTION

DB_PATH = PINNACLE_DB_PATH
TEST_COLLECTION = QA_TEST_COLLECTION


def load_base_config():
    import copy
    return copy.deepcopy(CONFIG_DICT)


def run_mode(mode, conn, engine, tests):
    """Run one mode against all test questions."""
    # Switch engine to this mode
    config_update = {"pipeline": {"mode": mode, "stages": PIPELINE_MODES[mode]}}
    engine.Run("set_config", {"config": config_update})

    mode_name = MODE_NAMES[mode]
    table_name = f"exp_mode_{mode.lower()}"

    c = conn.cursor()
    c.execute(f"DROP TABLE IF EXISTS {table_name}")
    c.execute(f"""CREATE TABLE {table_name} (
        test_id TEXT, aspect TEXT, question TEXT,
        expected_answer TEXT, expected_mode TEXT,
        answer TEXT, confidence REAL, actual_mode TEXT,
        mode_correct INTEGER, answer_correct INTEGER,
        chunks_found INTEGER, latency_ms REAL,
        embed_ms REAL, search_ms REAL, qa_ms REAL,
        explained TEXT
    )""")

    print(f"\n{'='*100}")
    print(f"MODE {mode}: {mode_name.upper()}")
    print(f"  Stages: {' -> '.join(PIPELINE_MODES[mode])}")
    print(f"{'='*100}")
    print(f"\n{'ID':5s} {'Aspect':15s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Conf':>8s} {'Lat':>7s} {'Question':40s} {'Answer':35s}")
    print("-" * 125)

    mode_correct = 0
    answer_correct = 0
    total = 0
    latencies = []

    for test_id, aspect, question, expected_answer, expected_mode, expected_chunk_ids_json in tests:
        total += 1

        # Run the engine
        ok, result, err = engine.Run("ask", {"question": question, "collection": TEST_COLLECTION})

        if not ok:
            c.execute(f"""INSERT INTO {table_name}
                (test_id, aspect, question, expected_answer, expected_mode,
                 answer, confidence, actual_mode, mode_correct, answer_correct,
                 chunks_found, latency_ms, embed_ms, search_ms, qa_ms, explained)
                VALUES (?, ?, ?, ?, ?, NULL, -999, 'ERROR', 0, 0, 0, 0, 0, 0, 0, NULL)""",
                (test_id, aspect, question, expected_answer, expected_mode))
            conn.commit()
            print(f"{test_id:5s} {aspect:15s} {expected_mode:5s} {'ERR':5s} {'X':3s} {'N/A':>8s} {'N/A':>7s} {question[:40]:40s} ERROR: {err}")
            continue

        answer = result.get("answer", "") or ""
        confidence = result.get("confidence", -999.0)
        actual_mode = result.get("mode", "UNKNOWN")
        chunks_found = result.get("chunks_searched", 0)
        latency = result.get("latency_ms", 0)
        explained = result.get("explained")
        embed_ms = result.get("latency_embed", 0)
        search_ms = result.get("latency_search", 0)
        qa_ms = result.get("latency_qa", 0)

        # Classify
        mode_ok = 1 if actual_mode == expected_mode else 0
        if expected_answer is not None:
            ans_ok = 1 if expected_answer.lower() in answer.lower() else 0
        else:
            ans_ok = 1 if actual_mode in ("UNKNOWN", "FALSE") else 0

        mode_correct += mode_ok
        answer_correct += ans_ok
        latencies.append(latency)

        c.execute(f"""INSERT INTO {table_name}
            (test_id, aspect, question, expected_answer, expected_mode,
             answer, confidence, actual_mode, mode_correct, answer_correct,
             chunks_found, latency_ms, embed_ms, search_ms, qa_ms, explained)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (test_id, aspect, question, expected_answer, expected_mode,
             answer, confidence, actual_mode, mode_ok, ans_ok,
             chunks_found, latency, embed_ms, search_ms, qa_ms, explained))
        conn.commit()

        status = "Y" if mode_ok else "X"
        # For Mode A, answer is None (retrieval only) — show top chunk score
        if mode == "A":
            confidence_display = f"r={result.get('top_score', 0):.2f}"
        else:
            confidence_display = f"{confidence:8.2f}"
        print(f"{test_id:5s} {aspect:15s} {expected_mode:5s} {actual_mode:5s} {status:3s} {confidence_display} {latency:6.0f}ms {question[:40]:40s} {answer[:35]:35s}")

    print("-" * 125)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    print(f"\n  Mode correct:   {mode_correct}/{total} ({mode_correct/total*100:.0f}%)")
    print(f"  Answer correct: {answer_correct}/{total} ({answer_correct/total*100:.0f}%)")
    print(f"  Avg latency:    {avg_lat:.0f}ms")

    return mode_correct, answer_correct, total, avg_lat


def compare_all_modes(conn):
    """Print side-by-side comparison of all 5 modes."""
    c = conn.cursor()
    print("\n" + "=" * 130)
    print("5-MODE COMPARISON — SWITCHABLE COGNITION GRAPH")
    print("=" * 130)

    modes = [("A", "exp_mode_a"), ("B", "exp_mode_b"), ("C", "exp_mode_c"),
             ("D", "exp_mode_d"), ("E", "exp_mode_e")]

    # Overall
    print("\n--- OVERALL ---")
    print(f"{'Mode':5s} {'Name':20s} {'ModeOK':>10s} {'AnsOK':>10s} {'AvgLat':>8s} {'AvgQA':>8s}")
    print("-" * 65)
    for mode, table in modes:
        try:
            row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct), SUM(answer_correct),
                AVG(latency_ms), AVG(qa_ms) FROM {table}""").fetchone()
            total, m_ok, a_ok, avg_lat, avg_qa = row
            if total and total > 0:
                name = MODE_NAMES.get(mode, "?")
                print(f"{mode:5s} {name:20s} {m_ok}/{total:3d} ({m_ok/total*100:3.0f}%) {a_ok}/{total:3d} ({a_ok/total*100:3.0f}%) {avg_lat:7.0f}ms {avg_qa:7.0f}ms")
        except Exception:
            print(f"{mode:5s} (not run)")

    # Per-aspect
    print("\n--- BY ASPECT ---")
    aspects = c.execute("SELECT DISTINCT aspect FROM qa_tests ORDER BY aspect").fetchall()
    header = f"{'Aspect':20s}"
    for mode, _ in modes:
        header += f" | {mode}Mode {mode}Ans"
    print(header)
    print("-" * 100)

    for (aspect,) in aspects:
        line = f"{aspect:20s}"
        for mode, table in modes:
            try:
                row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct), SUM(answer_correct)
                    FROM {table} WHERE aspect = ?""", (aspect,)).fetchone()
                total, m_ok, a_ok = row
                if total and total > 0:
                    line += f" | {m_ok}/{total:2d} ({m_ok/total*100:3.0f}%) {a_ok}/{total:2d} ({a_ok/total*100:3.0f}%)"
                else:
                    line += f" | {'N/A':>14s}"
            except Exception:
                line += f" | {'N/A':>14s}"
        print(line)

    # Head-to-head: B vs D (the key comparison)
    print("\n--- BERT QA (B) vs LLM (D) — HEAD TO HEAD ---")
    try:
        rows = c.execute("""
            SELECT b.test_id, b.question, b.expected_answer, b.expected_mode,
                   b.answer as b_ans, b.confidence as b_conf, b.actual_mode as b_mode, b.mode_correct as b_ok,
                   d.answer as d_ans, d.confidence as d_conf, d.actual_mode as d_mode, d.mode_correct as d_ok
            FROM exp_mode_b b
            JOIN exp_mode_d d ON b.test_id = d.test_id
            WHERE b.mode_correct != d.mode_correct OR b.answer_correct != d.answer_correct
            ORDER BY b.test_id
        """).fetchall()
        for row in rows:
            tid, q, exp_ans, exp_mode, b_ans, b_conf, b_mode, b_ok, d_ans, d_conf, d_mode, d_ok = row
            print(f"\n  {tid}: {q[:50]}")
            print(f"    Expected: '{(exp_ans or 'None')[:40]}' mode={exp_mode}")
            print(f"    BERT (B): '{(b_ans or 'None')[:40]}' conf={b_conf:.2f} mode={b_mode} {'OK' if b_ok else 'X'}")
            print(f"    LLM  (D): '{(d_ans or 'None')[:40]}' conf={d_conf:.2f} mode={d_mode} {'OK' if d_ok else 'X'}")
    except Exception as e:
        print(f"  (comparison error: {e})")

    # Latency
    print("\n--- LATENCY BY MODE ---")
    print(f"{'Mode':5s} {'Embed':>8s} {'Search':>8s} {'QA/LLM':>8s} {'Total':>8s}")
    print("-" * 40)
    for mode, table in modes:
        try:
            row = c.execute(f"""SELECT AVG(embed_ms), AVG(search_ms), AVG(qa_ms), AVG(latency_ms) FROM {table}""").fetchone()
            e, s, q, t = row
            print(f"{mode:5s} {e:7.0f}ms {s:7.0f}ms {q:7.0f}ms {t:7.0f}ms")
        except Exception:
            print(f"{mode:5s} (not run)")

    # Unknowns detection
    print("\n--- UNKNOWN DETECTION (U01-U04 + F01-F03) ---")
    print(f"{'Mode':5s} {'Unknowns correct':>20s} {'FalsePos correct':>20s}")
    print("-" * 50)
    for mode, table in modes:
        try:
            u_row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct) FROM {table} WHERE aspect = 'unknowns'""").fetchone()
            f_row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct) FROM {table} WHERE aspect = 'false_positive'""").fetchone()
            u_total, u_ok = u_row
            f_total, f_ok = f_row
            print(f"{mode:5s} {u_ok}/{u_total:2d} ({u_ok/u_total*100:3.0f}%)          {f_ok}/{f_total:2d} ({f_ok/f_total*100:3.0f}%)")
        except Exception:
            print(f"{mode:5s} (not run)")


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: pinnacle_harness.db not found. Run pinnacle_harness.py --setup first.")
        sys.exit(1)

    # Check Qdrant
    try:
        req = urllib.request.Request(f"http://localhost:6333/collections/{TEST_COLLECTION}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        print(f"Qdrant collection {TEST_COLLECTION}: {data['result']['points_count']} points")
    except Exception as e:
        print(f"ERROR: Qdrant collection not accessible: {e}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tests = c.execute("""
        SELECT id, aspect, question, expected_answer, expected_mode, expected_chunk_ids
        FROM qa_tests ORDER BY id
    """).fetchall()

    # Initialize engine once — models stay loaded, only mode switches
    print("\nInitializing GhostQAEngine...")
    engine = GhostQAEngine()
    ok, init_result, err = engine.Run("init")
    if not ok:
        print(f"ERROR: Engine init failed: {err}")
        sys.exit(1)
    print(f"  Config loaded: {init_result}")
    print(f"  Models: embedding={init_result['embedding_model']}, qa={init_result['qa_model']}, llm={init_result['llm_model']}")

    # Run all 5 modes
    results = {}
    for mode in ["A", "B", "C", "D", "E"]:
        m_ok, a_ok, total, avg_lat = run_mode(mode, conn, engine, tests)
        results[mode] = {"mode_correct": m_ok, "answer_correct": a_ok, "total": total, "avg_latency": avg_lat}

    # Comparison
    compare_all_modes(conn)
    conn.close()

    print("\n\nDONE. All 5 modes tested on same 28 questions.")


if __name__ == "__main__":
    main()
