#!/usr/bin/env python3
"""
QA Test Harness v2 — Full Pipeline Test

Tests the REAL GhostQA pipeline:
  1. Curated chat document stored in SQLite (curated_chat table)
  2. Chat is chunked and embedded into Qdrant test collection (real retrieval)
  3. GhostQA.ask() runs the full pipeline: embed question → search Qdrant → BERT QA extract
  4. Results stored in qa_results table with TRUE/FALSE/UNKNOWN classification

Usage:
  python3 qa_test_harness_v2.py --setup    # create DB + curated chat + embed into Qdrant
  python3 qa_test_harness_v2.py --run      # run GhostQA full pipeline against test questions
  python3 qa_test_harness_v2.py --report   # show results summary
  python3 qa_test_harness_v2.py --clean    # delete Qdrant test collection + DB
  python3 qa_test_harness_v2.py --all      # setup + run + report
"""

import sqlite3
import json
import os
import sys
import time
import urllib.request
import numpy as np
from sentence_transformers import SentenceTransformer

DB_PATH = os.path.join(os.path.dirname(__file__), "qa_test.db")
QDRANT_URL = "http://localhost:6333"
TEST_COLLECTION = "qa_test_chat"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# ─── Curated Chat Document ───────────────────────────────────────────────
# A realistic conversation about VBStyle — like a session transcript.
# This is the ONLY source the system will search. Test questions must be
# answerable from THIS text (TRUE) or not (FALSE/UNKNOWN).

CURATED_CHAT = """=== MESSAGE 0 - User ===
Hey, can you explain the VBStyle architecture to me? I'm trying to understand how MemUnit works.

=== MESSAGE 1 - Assistant ===
Sure. MemUnit is the core execution authority in VBStyle. It is the only place where execution runs. It acts as a dispatcher, not a selector. The orchestrator loads a precomputed path and MemUnit executes it deterministically. Think of it as the bus that connects everything — every class receives mem as a parameter and communicates through memunit.get and memunit.put. No direct imports, no file references between classes.

=== MESSAGE 2 - User ===
What about the boot sequence? How does the system start up?

=== MESSAGE 3 - Assistant ===
The boot spine is fixed and deterministic. The order is: Config, then MemDB, then AST, then Brackets, then ClassDB, then Orchestration, then MemUnit, then Report, then Output. This order cannot break. Config loads configuration from BCL brackets, not JSON. MemDB creates an in-memory SQLite runtime state. AST validates syntax structure. Brackets parse the BCL bracket syntax. ClassDB maps class names to domains. Orchestration resolves dependencies and builds the execution graph. MemUnit dispatches the execution. Report handles output. Output delivers the final result.

=== MESSAGE 4 - User ===
What is BCL exactly? I keep seeing bracket syntax everywhere.

=== MESSAGE 5 - Assistant ===
BCL stands for Bracket Configuration Language. It uses the syntax [@name]{...} for both passive configuration and active commands. There are two forms. BCL-Config is passive state read by dom_config, like [@zoom]{("min"; 0.01; 1.0; 0.10)}. BCL-Command is active execution run through MemUnit, like [@run]{("query"; "SELECT * FROM tokens")}. Same syntax, different consumer. Config is read. Command is executed by MemUnit.

=== MESSAGE 6 - User ===
What are the main rules I need to follow when writing VBStyle code?

=== MESSAGE 7 - Assistant ===
There are several critical rules. Rule 7 states NO print statements — use the Report class or logging instead. Rule 8 states NO hardcoded paths — nothing is allowed to be hardcoded, database names and users must come from config or memunit. All methods must return Tuple3 format: (ok, data, error). On success return (1, data, None). On error return (0, None, error_tuple). The constructor signature must be def __init__(self, mem=None, db=None, param=None). No self._ variables — use self.state dictionary instead. No decorators like @property or @staticmethod. No enums. Class names must be PascalCase. Constants must be UPPERCASE at class level.

=== MESSAGE 8 - User ===
What database does the system use? I saw mentions of MySQL and SQLite.

=== MESSAGE 9 - Assistant ===
The system uses both. MemDB is an in-memory SQLite database that serves as the runtime state substrate. It operates in RAM with SQLite tables as channels for the memory bus. MemDB uses port 7011 for its operations. The persistent storage is MySQL, specifically the vb_shared database which contains rules, learned_rules, know_lessons, code_classes, class_understandings, and more. The key principle is: never hardcode the database name or user — always read from memunit config. The config values db_user, db_name, sqlite_db_path, and embed_dim all flow through CORE_MEMUNIT.

=== MESSAGE 10 - User ===
Can you tell me about the GUI engine? How does that work?

=== MESSAGE 11 - Assistant ===
The GUI engine is a declarative system. GUI components are assembled from rules based on context, not generated from scratch. It uses a .gengui bundle format with write and render modes. The Swift-facing API uses EngineHostDelegate. Control aspects map to SwiftUI platform components. The engine has context-driven assembly — it looks at data shape, data size, field count, user intent, and interaction type to decide which component to render. For example, if data_shape is tabular and data_size is greater than 5 and field_count is greater than 3, it renders a grid. If user_intent is search and interaction_type is input, it renders a search field.

=== MESSAGE 12 - User ===
What about error handling? How does that work in VBStyle?

=== MESSAGE 13 - Assistant ===
ErrorCapture is the class that standardizes all errors. Error becomes data, not control flow interruption. Every method returns a uniform Tuple3 format: (status, data, error). The error tuple format is (code, description, 0). When an error occurs, you return (0, None, (code, description, 0)). The system never raises exceptions — it captures them and returns them as data. This makes errors traceable and deterministic. The Reporter class handles central output with no print statements allowed. All output goes through Reporter which returns strings.

=== MESSAGE 14 - User ===
How many chapters are in the VBStyle book that was written?

=== MESSAGE 15 - Assistant ===
The VBStyle book has 56 chapters, 111 sections, 185 content blocks, and 31,344 words total. The longest chapter is Wayne's Container Laws at 1,688 words. The shortest is The Constructor Pattern at 237 words. Every chapter has substantive content — zero chapters are under 200 words. The book covers the boot spine, MemUnit, BCL, Tuple3 returns, the state dictionary, prohibition rules, ghost headers, VBStyle headers, naming rules, the domain collapse law, the magnetic trajectory engine, the zero-drift philosophy, and more.

=== MESSAGE 16 - User ===
What is the Zero-Drift Philosophy?

=== MESSAGE 17 - Assistant ===
The Zero-Drift Philosophy states that code should be written so the problem never occurs. Prevention over correction. Do not write code where you go back and fix it. Always use core classes. No raw open(), no raw mysql.connect(), no json.load(). The principle is: write code so the problem NEVER occurs in the first place. This is the opposite of defensive programming where you catch errors after they happen. In Zero-Drift, you structure the code so the error path is impossible.
"""

# ─── Test Questions ──────────────────────────────────────────────────────
# Each question is classified by what we EXPECT the system to do:
#   TRUE    — the answer exists in the curated chat, retrieval should find it,
#              BERT QA should extract the right answer
#   FALSE   — the question is about VBStyle but the chat does NOT contain the answer.
#              Retrieval may find related chunks, but BERT QA should not extract
#              a correct answer (or should return low confidence)
#   UNKNOWN — the question is completely unrelated to anything in the chat.
#              Retrieval should find nothing relevant, or BERT QA should return
#              very low confidence

TEST_QUESTIONS = [
    # ─── TRUE: answer is in the chat ───
    {
        "id": "T01",
        "question": "What is MemUnit?",
        "expected_answer": "the core execution authority",
        "expected_mode": "TRUE",
        "note": "Directly stated in message 1",
    },
    {
        "id": "T02",
        "question": "What is the boot spine order?",
        "expected_answer": "config",
        "expected_mode": "TRUE",
        "note": "Listed in message 3 — testing if BERT can extract a sequence",
    },
    {
        "id": "T03",
        "question": "What does BCL stand for?",
        "expected_answer": "bracket configuration language",
        "expected_mode": "TRUE",
        "note": "Stated in message 5",
    },
    {
        "id": "T04",
        "question": "What is Rule 7 in VBStyle?",
        "expected_answer": "no print statements",
        "expected_mode": "TRUE",
        "note": "Stated in message 7",
    },
    {
        "id": "T05",
        "question": "What port does MemDB use?",
        "expected_answer": "7011",
        "expected_mode": "TRUE",
        "note": "Stated in message 9",
    },
    {
        "id": "T06",
        "question": "How many chapters are in the VBStyle book?",
        "expected_answer": "56",
        "expected_mode": "TRUE",
        "note": "Stated in message 15",
    },
    {
        "id": "T07",
        "question": "What return format do all VBStyle methods use?",
        "expected_answer": "tuple3",
        "expected_mode": "TRUE",
        "note": "Stated in messages 7 and 13",
    },
    {
        "id": "T08",
        "question": "What is the Zero-Drift Philosophy?",
        "expected_answer": "code should be written so the problem never occurs",
        "expected_mode": "TRUE",
        "note": "Stated in message 17",
    },
    {
        "id": "T09",
        "question": "What does the Reporter class handle?",
        "expected_answer": "central output",
        "expected_mode": "TRUE",
        "note": "Stated in message 13",
    },
    {
        "id": "T10",
        "question": "What is the longest chapter in the VBStyle book?",
        "expected_answer": "wayne's container laws",
        "expected_mode": "TRUE",
        "note": "Stated in message 15",
    },

    # ─── FALSE: VBStyle question but answer NOT in the chat ───
    {
        "id": "F01",
        "question": "What is the Domain Collapse Law?",
        "expected_answer": None,
        "expected_mode": "FALSE",
        "note": "VBStyle topic but NOT discussed in this chat",
    },
    {
        "id": "F02",
        "question": "What is the Magnetic Trajectory Engine?",
        "expected_answer": None,
        "expected_mode": "FALSE",
        "note": "Mentioned only as a book topic name, not explained in chat",
    },
    {
        "id": "F03",
        "question": "How does the 12-layer tokenized search system work?",
        "expected_answer": None,
        "expected_mode": "FALSE",
        "note": "Not discussed in this chat at all",
    },
    {
        "id": "F04",
        "question": "What is the Qdrant collection for bracket patterns called?",
        "expected_answer": None,
        "expected_mode": "FALSE",
        "note": "Qdrant not discussed in this chat",
    },

    # ─── UNKNOWN: completely unrelated questions ───
    {
        "id": "U01",
        "question": "What is the capital of Japan?",
        "expected_answer": None,
        "expected_mode": "UNKNOWN",
        "note": "Geography — nothing to do with VBStyle",
    },
    {
        "id": "U02",
        "question": "How do I configure nginx for load balancing?",
        "expected_answer": None,
        "expected_mode": "UNKNOWN",
        "note": "DevOps — nothing to do with VBStyle",
    },
    {
        "id": "U03",
        "question": "What is the airspeed of an unladen swallow?",
        "expected_answer": None,
        "expected_mode": "UNKNOWN",
        "note": "Monty Python — nothing to do with anything",
    },
    {
        "id": "U04",
        "question": "How tall is the Eiffel Tower?",
        "expected_answer": None,
        "expected_mode": "UNKNOWN",
        "note": "Trivia — nothing to do with VBStyle",
    },
]


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def qdrant_request(endpoint, payload=None, method="GET"):
    """Make a Qdrant REST API request."""
    url = f"{QDRANT_URL}{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def create_qdrant_collection(collection_name, vector_size=384):
    """Create a Qdrant collection for testing."""
    # Delete if exists
    try:
        qdrant_request(f"/collections/{collection_name}", method="DELETE")
        print(f"  Deleted existing collection: {collection_name}")
    except Exception:
        pass

    # Create new collection
    payload = {
        "vectors": {"size": vector_size, "distance": "Cosine"},
    }
    qdrant_request(f"/collections/{collection_name}", payload, method="PUT")
    print(f"  Created Qdrant collection: {collection_name} (vector_size={vector_size})")


def embed_and_upsert(collection_name, chunks, embedder):
    """Embed chunks and upsert into Qdrant."""
    print(f"  Embedding {len(chunks)} chunks...")
    vectors = embedder.encode(chunks)

    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        points.append({
            "id": i + 1,
            "vector": vec.tolist(),
            "payload": {
                "text": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": "curated_chat",
            },
        })

    # Upsert in batches
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        qdrant_request(
            f"/collections/{collection_name}/points?wait=true",
            {"points": batch},
            method="PUT",
        )

    print(f"  Upserted {len(points)} points into {collection_name}")


def setup_database():
    """Create SQLite DB, store curated chat, chunk and embed into Qdrant."""
    # Clean existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table 1: curated_chat — the full chat document
    c.execute("""
        CREATE TABLE curated_chat (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            content       TEXT NOT NULL,
            chunk_count   INTEGER NOT NULL,
            chunk_size    INTEGER NOT NULL,
            chunk_overlap INTEGER NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # Table 2: chat_chunks — individual chunks stored for reference
    c.execute("""
        CREATE TABLE chat_chunks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_index   INTEGER NOT NULL,
            text          TEXT NOT NULL,
            qdrant_id     INTEGER NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # Table 3: test_questions — the questions to ask
    c.execute("""
        CREATE TABLE test_questions (
            id              TEXT PRIMARY KEY,
            question        TEXT NOT NULL,
            expected_answer TEXT,
            expected_mode   TEXT NOT NULL,
            note            TEXT
        )
    """)

    # Table 4: qa_results — results from running GhostQA
    c.execute("""
        CREATE TABLE qa_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id     TEXT NOT NULL,
            question        TEXT NOT NULL,
            chunks_found    INTEGER NOT NULL,
            top_chunk_score REAL,
            top_chunk_text  TEXT,
            extracted       TEXT,
            confidence      REAL,
            expected_answer TEXT,
            expected_mode   TEXT NOT NULL,
            actual_mode     TEXT NOT NULL,
            mode_correct    INTEGER NOT NULL,
            answer_correct  INTEGER NOT NULL,
            source          TEXT,
            run_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (question_id) REFERENCES test_questions(id)
        )
    """)

    # Chunk the chat
    chunks = chunk_text(CURATED_CHAT)
    print(f"Chunked curated chat into {len(chunks)} pieces (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    # Store full chat in DB
    c.execute("""
        INSERT INTO curated_chat (content, chunk_count, chunk_size, chunk_overlap)
        VALUES (?, ?, ?, ?)
    """, (CURATED_CHAT, len(chunks), CHUNK_SIZE, CHUNK_OVERLAP))

    # Store chunks in DB
    for i, chunk in enumerate(chunks):
        c.execute("""
            INSERT INTO chat_chunks (chunk_index, text, qdrant_id)
            VALUES (?, ?, ?)
        """, (i, chunk, i + 1))

    # Store test questions
    for q in TEST_QUESTIONS:
        c.execute("""
            INSERT INTO test_questions (id, question, expected_answer, expected_mode, note)
            VALUES (?, ?, ?, ?, ?)
        """, (q["id"], q["question"], q["expected_answer"], q["expected_mode"], q["note"]))

    conn.commit()
    conn.close()

    print(f"Database created: {DB_PATH}")
    print(f"  curated_chat: 1 document")
    print(f"  chat_chunks: {len(chunks)} chunks")
    print(f"  test_questions: {len(TEST_QUESTIONS)} ({sum(1 for q in TEST_QUESTIONS if q['expected_mode']=='TRUE')} TRUE, {sum(1 for q in TEST_QUESTIONS if q['expected_mode']=='FALSE')} FALSE, {sum(1 for q in TEST_QUESTIONS if q['expected_mode']=='UNKNOWN')} UNKNOWN)")

    # Embed and upsert into Qdrant
    print(f"\nEmbedding chunks into Qdrant collection: {TEST_COLLECTION}")
    create_qdrant_collection(TEST_COLLECTION)

    print("  Loading BGE embedder...")
    embedder = SentenceTransformer(EMBED_MODEL)
    embed_and_upsert(TEST_COLLECTION, chunks, embedder)

    # Verify collection
    info = qdrant_request(f"/collections/{TEST_COLLECTION}")
    count = info["result"]["points_count"]
    print(f"  Qdrant collection ready: {count} points")


def run_tests():
    """Run GhostQA full pipeline (ask) against each test question."""
    from qa_prototype import GhostQA

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    questions = c.execute("""
        SELECT id, question, expected_answer, expected_mode
        FROM test_questions
        ORDER BY id
    """).fetchall()

    print(f"\nRunning {len(questions)} tests through full GhostQA pipeline...")
    print(f"  (embed question -> search Qdrant {TEST_COLLECTION} -> BERT QA extract -> classify)")
    print()
    print(f"{'ID':5s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Conf':>8s} {'Chunks':>7s} {'RetrScore':>10s} {'Question':45s} {'Extracted':30s}")
    print("-" * 130)

    # Initialize GhostQA and configure it to search ONLY our test collection
    qa = GhostQA()
    ok, _, err = qa.Run("load_models")
    if not ok:
        print(f"ERROR loading models: {err}")
        conn.close()
        return

    # Override config to search only our test collection
    qa.Run("set_config", {"config": {"qdrant_collections": [TEST_COLLECTION]}})

    total = 0
    mode_correct_count = 0
    answer_correct_count = 0

    for qid, question, expected_answer, expected_mode in questions:
        total += 1

        # Run the FULL pipeline: ask -> search Qdrant -> BERT QA extract
        ok, result, err = qa.Run("ask", {"question": question})

        if not ok:
            print(f"{qid:5s} {expected_mode:5s} {'ERR':5s} {'X':3s} {'N/A':>8s} {'N/A':>7s} {'N/A':>10s} {question[:45]:45s} ERROR: {err}")
            # Store as UNKNOWN
            actual_mode = "UNKNOWN"
            mode_correct = 1 if expected_mode == "UNKNOWN" else 0
            answer_correct = 0
            c.execute("""
                INSERT INTO qa_results
                    (question_id, question, chunks_found, top_chunk_score, top_chunk_text,
                     extracted, confidence, expected_answer, expected_mode, actual_mode,
                     mode_correct, answer_correct, source)
                VALUES (?, ?, 0, 0, NULL, NULL, -999, ?, ?, ?, ?, ?, 'error')
            """, (qid, question, expected_answer, expected_mode, actual_mode, mode_correct, answer_correct))
            conn.commit()
            mode_correct_count += mode_correct
            answer_correct_count += answer_correct
            continue

        found = result.get("found", False)
        extracted = result.get("answer", "")
        confidence = result.get("confidence", -999.0)
        chunks_searched = result.get("chunks_searched", 0)
        source = result.get("source", "")
        evidence = result.get("evidence", "")
        source_score = result.get("source_score", 0)

        # Determine actual mode
        qa_threshold = qa.state["config"]["qa_confidence_threshold"]
        if not found or confidence < qa_threshold:
            actual_mode = "UNKNOWN"
        elif expected_answer is not None and expected_answer.lower() in extracted.lower():
            actual_mode = "TRUE"
        else:
            actual_mode = "FALSE"

        # Check mode classification
        mode_correct = 1 if actual_mode == expected_mode else 0

        # Check answer content
        if expected_answer is not None:
            answer_correct = 1 if expected_answer.lower() in extracted.lower() else 0
        else:
            # For FALSE/UNKNOWN, correct means we did NOT return a confident wrong answer
            answer_correct = 1 if actual_mode in ("UNKNOWN", "FALSE") else 0

        mode_correct_count += mode_correct
        answer_correct_count += answer_correct

        # Store result
        c.execute("""
            INSERT INTO qa_results
                (question_id, question, chunks_found, top_chunk_score, top_chunk_text,
                 extracted, confidence, expected_answer, expected_mode, actual_mode,
                 mode_correct, answer_correct, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            qid, question, chunks_searched, source_score, (evidence or "")[:300],
            extracted, confidence, expected_answer, expected_mode, actual_mode,
            mode_correct, answer_correct, source,
        ))
        conn.commit()

        status = "Y" if mode_correct else "X"
        ext_display = (extracted or "None")[:30]
        print(f"{qid:5s} {expected_mode:5s} {actual_mode:5s} {status:3s} {confidence:8.2f} {chunks_searched:7d} {source_score:10.4f} {question[:45]:45s} {ext_display:30s}")

    print("-" * 130)
    print(f"\nSUMMARY:")
    print(f"  Total tests:        {total}")
    print(f"  Mode correct:       {mode_correct_count}/{total} ({mode_correct_count/total*100:.0f}%)")
    print(f"  Answer correct:     {answer_correct_count}/{total} ({answer_correct_count/total*100:.0f}%)")

    conn.close()


def report():
    """Show detailed results."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("\n" + "=" * 120)
    print("QA TEST RESULTS REPORT — FULL PIPELINE (Qdrant retrieval + BERT QA extraction)")
    print("=" * 120)

    # Summary by expected mode
    print("\n--- BY EXPECTED MODE ---")
    rows = c.execute("""
        SELECT expected_mode,
               COUNT(*) as total,
               SUM(mode_correct) as mode_ok,
               SUM(answer_correct) as ans_ok,
               AVG(confidence) as avg_conf,
               MIN(confidence) as min_conf,
               MAX(confidence) as max_conf,
               AVG(chunks_found) as avg_chunks,
               AVG(top_chunk_score) as avg_retrieval
        FROM qa_results
        GROUP BY expected_mode
        ORDER BY expected_mode
    """).fetchall()

    print(f"{'Mode':8s} {'Total':>6s} {'ModeOK':>7s} {'AnsOK':>6s} {'AvgConf':>9s} {'MinConf':>9s} {'MaxConf':>9s} {'AvgChunks':>10s} {'AvgRetr':>9s}")
    print("-" * 75)
    for mode, total, mode_ok, ans_ok, avg_conf, min_conf, max_conf, avg_chunks, avg_retr in rows:
        print(f"{mode:8s} {total:6d} {mode_ok:7d} {ans_ok:6d} {avg_conf:9.2f} {min_conf:9.2f} {max_conf:9.2f} {avg_chunks:10.1f} {avg_retr:9.4f}")

    # Confusion matrix
    print("\n--- CONFUSION MATRIX (expected vs actual) ---")
    rows = c.execute("""
        SELECT expected_mode, actual_mode, COUNT(*) as count
        FROM qa_results
        GROUP BY expected_mode, actual_mode
        ORDER BY expected_mode, actual_mode
    """).fetchall()

    print(f"{'Expected':10s} | {'TRUE':8s} {'FALSE':8s} {'UNKNOWN':8s}")
    print("-" * 40)
    matrix = {}
    for exp, act, count in rows:
        matrix[(exp, act)] = count
    for exp in ["TRUE", "FALSE", "UNKNOWN"]:
        vals = [matrix.get((exp, a), 0) for a in ["TRUE", "FALSE", "UNKNOWN"]]
        print(f"{exp:10s} | {vals[0]:8d} {vals[1]:8d} {vals[2]:8d}")

    # False positives
    print("\n--- FALSE POSITIVES (expected UNKNOWN/FALSE, got TRUE) ---")
    rows = c.execute("""
        SELECT question_id, question, extracted, confidence, expected_mode, actual_mode, top_chunk_score
        FROM qa_results
        WHERE expected_mode IN ('UNKNOWN', 'FALSE') AND actual_mode = 'TRUE'
    """).fetchall()
    if rows:
        for qid, q, ext, conf, exp, act, retr in rows:
            print(f"  {qid}: {q[:50]}")
            print(f"       Extracted: '{ext[:50]}' (conf={conf:.2f}, retrieval={retr:.4f})")
            print(f"       Expected: {exp}, Got: {act}")
    else:
        print("  None")

    # False negatives
    print("\n--- FALSE NEGATIVES (expected TRUE, got UNKNOWN/FALSE) ---")
    rows = c.execute("""
        SELECT question_id, question, extracted, confidence, expected_mode, actual_mode,
               top_chunk_score, chunks_found, top_chunk_text
        FROM qa_results
        WHERE expected_mode = 'TRUE' AND actual_mode != 'TRUE'
    """).fetchall()
    if rows:
        for qid, q, ext, conf, exp, act, retr, chunks, chunk_text in rows:
            print(f"  {qid}: {q[:50]}")
            print(f"       Extracted: '{(ext or 'None')[:50]}' (conf={conf:.2f}, retrieval={retr:.4f})")
            print(f"       Chunks found: {chunks}")
            print(f"       Top chunk: {(chunk_text or 'None')[:80]}")
            print(f"       Expected: {exp}, Got: {act}")
    else:
        print("  None")

    # Retrieval analysis
    print("\n--- RETRIEVAL ANALYSIS ---")
    rows = c.execute("""
        SELECT expected_mode,
               AVG(top_chunk_score) as avg_retrieval,
               MIN(top_chunk_score) as min_retrieval,
               MAX(top_chunk_score) as max_retrieval,
               AVG(chunks_found) as avg_chunks
        FROM qa_results
        GROUP BY expected_mode
        ORDER BY expected_mode
    """).fetchall()
    print(f"{'Mode':8s} {'AvgRetr':>9s} {'MinRetr':>9s} {'MaxRetr':>9s} {'AvgChunks':>10s}")
    print("-" * 50)
    for mode, avg_r, min_r, max_r, avg_c in rows:
        print(f"{mode:8s} {avg_r:9.4f} {min_r:9.4f} {max_r:9.4f} {avg_c:10.1f}")

    # All results
    print("\n--- ALL RESULTS ---")
    rows = c.execute("""
        SELECT question_id, question, extracted, confidence, expected_answer,
               expected_mode, actual_mode, mode_correct, chunks_found, top_chunk_score
        FROM qa_results
        ORDER BY question_id
    """).fetchall()

    print(f"{'ID':5s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Conf':>8s} {'Chunks':>6s} {'Retr':>7s} {'Question':40s} {'Extracted':25s} {'Expected':25s}")
    print("-" * 140)
    for qid, q, ext, conf, exp_ans, exp_mode, act_mode, ok, chunks, retr in rows:
        print(f"{qid:5s} {exp_mode:5s} {act_mode:5s} {'Y' if ok else 'X':3s} {conf:8.2f} {chunks:6d} {retr:7.4f} {q[:40]:40s} {(ext or 'None')[:25]:25s} {(exp_ans or 'None')[:25]:25s}")

    conn.close()


def clean():
    """Delete Qdrant test collection and database."""
    try:
        qdrant_request(f"/collections/{TEST_COLLECTION}", method="DELETE")
        print(f"Deleted Qdrant collection: {TEST_COLLECTION}")
    except Exception as e:
        print(f"Could not delete collection: {e}")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted database: {DB_PATH}")


def main():
    args = sys.argv[1:]
    if not args or "--all" in args:
        setup_database()
        run_tests()
        report()
    elif "--setup" in args:
        setup_database()
    elif "--run" in args:
        run_tests()
    elif "--report" in args:
        report()
    elif "--clean" in args:
        clean()
    else:
        print("Usage: python3 qa_test_harness_v2.py [--setup|--run|--report|--clean|--all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
