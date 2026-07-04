#!/usr/bin/env python3
"""
3-Experiment Comparison Harness

Runs the same 28 PinnacleHarness questions through three different QA layers:
  Experiment A: Retrieval Only (return chunks, no extraction)
  Experiment B: Retrieval + BERT QA (CoreML span extraction)
  Experiment C: Retrieval + Qwen 1.5B (evidence-locked synthesis)

All three use the SAME:
  - BGE embeddings
  - Qdrant collection (pinnacle_test)
  - Chunk corpus
  - Test questions
  - Expected answers

The ONLY difference is the QA extraction layer.
"""

import sqlite3
import json
import os
import sys
import time
import urllib.request
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import BertTokenizer
import coremltools as ct
from mlx_lm import load as mlx_load, generate as mlx_generate

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config_qa_engine import (
    PINNACLE_DB_PATH, TEST_COLLECTION as QA_TEST_COLLECTION,
    QDRANT_URL, EMBEDDING_BGE_SMALL, BERT_SQUAD_MODEL_PATH,
    QA_BERT_SQUAD_FP16, LLM_QWEN25_CODER_4BIT,
    RETRIEVAL_SIMILARITY_THRESHOLD, CLASSIFY_TRUE_THRESHOLD,
)

DB_PATH = PINNACLE_DB_PATH
QDRANT_URL = QDRANT_URL
TEST_COLLECTION = QA_TEST_COLLECTION
EMBED_MODEL = EMBEDDING_BGE_SMALL['name']
BERT_QA_PATH = BERT_SQUAD_MODEL_PATH
BERT_TOKENIZER = QA_BERT_SQUAD_FP16['tokenizer']
QWEN_MODEL = LLM_QWEN25_CODER_4BIT['name']
RETRIEVAL_THRESHOLD = RETRIEVAL_SIMILARITY_THRESHOLD
TRUE_THRESHOLD = CLASSIFY_TRUE_THRESHOLD
UNKNOWN_THRESHOLD = 0.0


def qdrant_search(vector, top_k=5, threshold=RETRIEVAL_THRESHOLD):
    payload = {"vector": vector, "limit": top_k, "with_payload": True, "with_vector": False}
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{TEST_COLLECTION}/points/search",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode())
    hits = result.get("result", [])
    chunks = []
    for hit in hits:
        if hit.get("score", 0) >= threshold:
            pd = hit.get("payload", {})
            chunks.append({
                "id": hit.get("id"),
                "score": hit.get("score", 0),
                "text": pd.get("text", ""),
            })
    return chunks


def bert_qa_extract(question, context, tokenizer, qa_model, max_length=384):
    """BERT SQuAD span extraction."""
    encoded = tokenizer(
        question, context,
        add_special_tokens=True, return_tensors="np",
        max_length=max_length, truncation=True, padding="max_length",
    )
    word_ids = encoded["input_ids"].astype(np.float32)
    word_types = encoded["token_type_ids"].astype(np.float32)
    output = qa_model.predict({"wordIDs": word_ids, "wordTypes": word_types})
    start_logits = output["startLogits"][0]
    end_logits = output["endLogits"][0]
    start_idx = int(np.argmax(start_logits))
    end_idx = int(np.argmax(end_logits)) + 1
    if end_idx <= start_idx:
        end_idx = start_idx + 1
    answer_tokens = encoded["input_ids"][0][start_idx:end_idx]
    answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()
    start_score = float(np.max(start_logits))
    end_score = float(np.max(end_logits))
    confidence = (start_score + end_score) / 2
    return answer, confidence


def qwen_qa_extract(question, evidence_chunks, llm_model, llm_tokenizer, max_tokens=150):
    """Qwen 1.5B evidence-locked synthesis."""
    evidence = " ".join(chunk["text"] for chunk in evidence_chunks[:3])
    if len(evidence) > 3000:
        evidence = evidence[:3000]

    messages = [
        {
            "role": "system",
            "content": "You are a precise question answering system. Answer using ONLY information from the provided evidence. Be concise. If the answer is not in the evidence, respond with exactly: NOT FOUND"
        },
        {
            "role": "user",
            "content": f"Evidence: {evidence}\n\nQuestion: {question}\n\nAnswer (from evidence only):"
        }
    ]
    prompt = llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    response = mlx_generate(llm_model, llm_tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
    answer = response.strip().replace("<|im_end|>", "").strip()

    # Qwen doesn't give us a numeric confidence, so we use a heuristic:
    # NOT FOUND = low confidence (-1.0)
    # Short answer from evidence = high confidence (7.0)
    # Long answer = medium confidence (5.0)
    if "NOT FOUND" in answer.upper():
        return "NOT FOUND", -1.0
    if len(answer) < 20:
        return answer, 7.0
    if len(answer) < 100:
        return answer, 6.0
    return answer, 5.0


def classify_mode(answer, confidence, expected_answer):
    """Classify result as TRUE/FALSE/UNKNOWN."""
    if confidence < UNKNOWN_THRESHOLD:
        return "UNKNOWN"
    if "NOT FOUND" in answer.upper():
        return "UNKNOWN"
    if expected_answer is not None and expected_answer.lower() in answer.lower():
        return "TRUE"
    if expected_answer is None:
        return "FALSE"
    return "FALSE"


def run_experiment(experiment_name, qa_function, conn, embedder, extra_models=None):
    """Run one experiment and store results."""
    c = conn.cursor()

    tests = c.execute("""
        SELECT id, aspect, question, expected_answer, expected_mode, expected_chunk_ids
        FROM qa_tests ORDER BY id
    """).fetchall()

    print(f"\n{'='*80}")
    print(f"EXPERIMENT {experiment_name}")
    print(f"{'='*80}")
    print(f"\n{'ID':5s} {'Aspect':15s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Conf':>8s} {'Latency':>8s} {'Question':40s} {'Answer':30s}")
    print("-" * 120)

    results = []
    mode_correct = 0
    answer_correct = 0
    total = 0

    for test_id, aspect, question, expected_answer, expected_mode, expected_chunk_ids_json in tests:
        total += 1

        # STAGE: EMBED
        t0 = time.time()
        vec = embedder.encode([question])[0].tolist()
        embed_ms = (time.time() - t0) * 1000

        # STAGE: SEARCH
        t0 = time.time()
        chunks = qdrant_search(vec)
        search_ms = (time.time() - t0) * 1000

        if not chunks:
            actual_mode = "UNKNOWN"
            answer = "Not Found"
            confidence = -999.0
            qa_ms = 0.0
        else:
            # STAGE: QA EXTRACT (experiment-specific)
            t0 = time.time()
            if qa_function is None:
                # Experiment A: retrieval only — return top chunk text as "answer"
                answer = chunks[0]["text"][:200]
                confidence = chunks[0]["score"] * 10  # scale retrieval score to confidence range
            else:
                answer, confidence = qa_function(question, chunks, extra_models)
            qa_ms = (time.time() - t0) * 1000

        # CLASSIFY
        actual_mode = classify_mode(answer, confidence, expected_answer)
        mode_ok = 1 if actual_mode == expected_mode else 0

        if expected_answer is not None:
            ans_ok = 1 if expected_answer.lower() in answer.lower() else 0
        else:
            ans_ok = 1 if actual_mode in ("UNKNOWN", "FALSE") else 0

        mode_correct += mode_ok
        answer_correct += ans_ok
        total_ms = embed_ms + search_ms + qa_ms

        results.append({
            "test_id": test_id, "aspect": aspect, "question": question,
            "expected_answer": expected_answer, "expected_mode": expected_mode,
            "answer": answer, "confidence": confidence, "actual_mode": actual_mode,
            "mode_correct": mode_ok, "answer_correct": ans_ok,
            "chunks_found": len(chunks), "latency_ms": total_ms,
            "embed_ms": embed_ms, "search_ms": search_ms, "qa_ms": qa_ms,
        })

        status = "Y" if mode_ok else "X"
        print(f"{test_id:5s} {aspect:15s} {expected_mode:5s} {actual_mode:5s} {status:3s} {confidence:8.2f} {total_ms:7.0f}ms {question[:40]:40s} {answer[:30]:30s}")

    print("-" * 120)
    print(f"\n  Mode correct:   {mode_correct}/{total} ({mode_correct/total*100:.0f}%)")
    print(f"  Answer correct: {answer_correct}/{total} ({answer_correct/total*100:.0f}%)")

    # Store results in experiment-specific table
    table_name = f"exp_{experiment_name.lower().replace(' ', '_').replace('.', '_').replace('1_5b', '1_5b')}"
    c.execute(f"DROP TABLE IF EXISTS {table_name}")
    c.execute(f"""CREATE TABLE {table_name} (
        test_id TEXT, aspect TEXT, question TEXT,
        expected_answer TEXT, expected_mode TEXT,
        answer TEXT, confidence REAL, actual_mode TEXT,
        mode_correct INTEGER, answer_correct INTEGER,
        chunks_found INTEGER, latency_ms REAL,
        embed_ms REAL, search_ms REAL, qa_ms REAL
    )""")
    for r in results:
        c.execute(f"""INSERT INTO {table_name}
            (test_id, aspect, question, expected_answer, expected_mode,
             answer, confidence, actual_mode, mode_correct, answer_correct,
             chunks_found, latency_ms, embed_ms, search_ms, qa_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["test_id"], r["aspect"], r["question"], r["expected_answer"], r["expected_mode"],
             r["answer"], r["confidence"], r["actual_mode"], r["mode_correct"], r["answer_correct"],
             r["chunks_found"], r["latency_ms"], r["embed_ms"], r["search_ms"], r["qa_ms"]))
    conn.commit()

    return results, mode_correct, answer_correct, total


def bert_qa_wrapper(question, chunks, models):
    """Wrapper for BERT QA extraction."""
    tokenizer = models["bert_tokenizer"]
    qa_model = models["bert_qa_model"]
    best_answer = ""
    best_conf = -999.0
    for chunk in chunks:
        answer, conf = bert_qa_extract(question, chunk["text"], tokenizer, qa_model)
        if conf > best_conf:
            best_answer = answer
            best_conf = conf
    return best_answer, best_conf


def qwen_qa_wrapper(question, chunks, models):
    """Wrapper for Qwen 1.5B evidence-locked synthesis."""
    return qwen_qa_extract(question, chunks, models["llm_model"], models["llm_tokenizer"])


def compare_results(conn):
    """Print side-by-side comparison of all 3 experiments."""
    c = conn.cursor()
    print("\n" + "=" * 130)
    print("3-EXPERIMENT COMPARISON")
    print("=" * 130)

    experiments = [("A", "exp_a_retrieval_only"), ("B", "exp_b_bert_qa"), ("C", "exp_c_qwen_1_5b")]

    # Overall comparison
    print("\n--- OVERALL ---")
    print(f"{'Experiment':25s} {'ModeOK':>8s} {'AnsOK':>8s} {'AvgLat':>8s} {'AvgQA':>8s}")
    print("-" * 60)
    for exp_name, table in experiments:
        try:
            row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct), SUM(answer_correct),
                AVG(latency_ms), AVG(qa_ms) FROM {table}""").fetchone()
            total, m_ok, a_ok, avg_lat, avg_qa = row
            print(f"{exp_name:25s} {m_ok}/{total:3d} ({m_ok/total*100:3.0f}%) {a_ok}/{total:3d} ({a_ok/total*100:3.0f}%) {avg_lat:7.0f}ms {avg_qa:7.0f}ms")
        except Exception:
            print(f"{exp_name:25s} (not run)")

    # Per-aspect comparison
    print("\n--- BY ASPECT ---")
    aspects = c.execute("SELECT DISTINCT aspect FROM qa_tests ORDER BY aspect").fetchall()
    print(f"{'Aspect':20s}", end="")
    for exp_name, _ in experiments:
        print(f" | {exp_name} Mode  {exp_name} Ans", end="")
    print()
    print("-" * 80)

    for (aspect,) in aspects:
        print(f"{aspect:20s}", end="")
        for exp_name, table in experiments:
            try:
                row = c.execute(f"""SELECT COUNT(*), SUM(mode_correct), SUM(answer_correct)
                    FROM {table} WHERE aspect = ?""", (aspect,)).fetchone()
                total, m_ok, a_ok = row
                if total > 0:
                    print(f" | {m_ok}/{total:2d} ({m_ok/total*100:3.0f}%) {a_ok}/{total:2d} ({a_ok/total*100:3.0f}%)", end="")
                else:
                    print(f" | {'N/A':>14s}", end="")
            except Exception:
                print(f" | {'N/A':>14s}", end="")
        print()

    # Side-by-side answers for questions where experiments disagreed
    print("\n--- DISAGREEMENTS (where BERT and Qwen gave different results) ---")
    try:
        rows = c.execute("""
            SELECT b.test_id, b.question, b.expected_answer, b.expected_mode,
                   b.answer as bert_answer, b.confidence as bert_conf, b.actual_mode as bert_mode, b.mode_correct as bert_ok,
                   c.answer as qwen_answer, c.confidence as qwen_conf, c.actual_mode as qwen_mode, c.mode_correct as qwen_ok
            FROM exp_b_bert_qa b
            JOIN exp_c_qwen_1_5b c ON b.test_id = c.test_id
            WHERE b.mode_correct != c.mode_correct
               OR b.answer_correct != c.answer_correct
            ORDER BY b.test_id
        """).fetchall()
        for row in rows:
            tid, q, exp_ans, exp_mode, b_ans, b_conf, b_mode, b_ok, q_ans, q_conf, q_mode, q_ok = row
            print(f"\n  {tid}: {q[:50]}")
            print(f"    Expected: '{(exp_ans or 'None')[:40]}' mode={exp_mode}")
            print(f"    BERT:     '{b_ans[:40]}' conf={b_conf:.2f} mode={b_mode} {'OK' if b_ok else 'X'}")
            print(f"    Qwen:     '{q_ans[:40]}' conf={q_conf:.2f} mode={q_mode} {'OK' if q_ok else 'X'}")
    except Exception as e:
        print(f"  (comparison error: {e})")

    # Latency comparison
    print("\n--- LATENCY COMPARISON ---")
    print(f"{'Experiment':25s} {'Embed':>8s} {'Search':>8s} {'QA':>8s} {'Total':>8s}")
    print("-" * 60)
    for exp_name, table in experiments:
        try:
            row = c.execute(f"""SELECT AVG(embed_ms), AVG(search_ms), AVG(qa_ms), AVG(latency_ms) FROM {table}""").fetchone()
            e, s, q, t = row
            print(f"{exp_name:25s} {e:7.0f}ms {s:7.0f}ms {q:7.0f}ms {t:7.0f}ms")
        except Exception:
            print(f"{exp_name:25s} (not run)")


def main():
    conn = sqlite3.connect(DB_PATH)

    if not os.path.exists(DB_PATH):
        print("ERROR: pinnacle_harness.db not found. Run pinnacle_harness.py --setup first.")
        sys.exit(1)

    # Check Qdrant collection exists
    try:
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{TEST_COLLECTION}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        count = data["result"]["points_count"]
        print(f"Qdrant collection {TEST_COLLECTION}: {count} points")
    except Exception as e:
        print(f"ERROR: Qdrant collection {TEST_COLLECTION} not accessible: {e}")
        print("Run pinnacle_harness.py --setup first.")
        sys.exit(1)

    # Load embedder (shared by all experiments)
    print("\nLoading BGE embedder...")
    embedder = SentenceTransformer(EMBED_MODEL)

    # Load BERT QA model
    print("Loading BERT SQuAD CoreML model...")
    bert_tokenizer = BertTokenizer.from_pretrained(BERT_TOKENIZER)
    bert_qa_model = ct.models.MLModel(BERT_QA_PATH)

    # Load Qwen 1.5B
    print("Loading Qwen 1.5B Instruct 4bit...")
    llm_model, llm_tokenizer = mlx_load(QWEN_MODEL)

    models = {
        "bert_tokenizer": bert_tokenizer,
        "bert_qa_model": bert_qa_model,
        "llm_model": llm_model,
        "llm_tokenizer": llm_tokenizer,
    }

    # ─── EXPERIMENT A: Retrieval Only ───
    run_experiment("A retrieval only", None, conn, embedder)

    # ─── EXPERIMENT B: Retrieval + BERT QA ───
    run_experiment("B bert qa", bert_qa_wrapper, conn, embedder, models)

    # ─── EXPERIMENT C: Retrieval + Qwen 1.5B ───
    run_experiment("C qwen 1.5b", qwen_qa_wrapper, conn, embedder, models)

    # ─── COMPARISON ───
    compare_results(conn)

    conn.close()


if __name__ == "__main__":
    main()
