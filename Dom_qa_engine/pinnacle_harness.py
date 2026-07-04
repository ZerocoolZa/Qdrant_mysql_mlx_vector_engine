#!/usr/bin/env python3
"""
PinnacleHarness — Full Pipeline QA Test Harness

Tests the complete GhostQA architecture with per-stage failure tracking:

  Question
     |
  [EMBED]     <- latency_embed measured
     |
  [SEARCH]    <- latency_search, retrieved_chunk_ids, retrieval_scores, R@K measured
     |
  [QA EXTRACT] <- latency_qa, extracted_answer, qa_confidence measured
     |
  [CLASSIFY]  <- actual_mode (TRUE/FALSE/UNKNOWN), failure_stage determined

Every result row records:
  question, expected_answer, expected_mode, expected_chunk_ids
  retrieved_chunk_ids, retrieval_scores, retrieved_rank, retrieval_correct
  qa_answer, qa_confidence, answer_correct
  final_mode, mode_correct
  latency_embed, latency_search, latency_qa
  failure_stage (RETRIEVAL | CHUNKING | QA | THRESHOLD | NONE)

Usage:
  python3 pinnacle_harness.py --setup    # create DB + curated data + embed into Qdrant
  python3 pinnacle_harness.py --run      # run full pipeline tests
  python3 pinnacle_harness.py --report   # show analysis
  python3 pinnacle_harness.py --clean    # delete Qdrant collection + DB
  python3 pinnacle_harness.py --all      # setup + run + report
"""

import sqlite3
import json
import os
import sys
import time
import urllib.request
import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config_qa_engine import (
    PINNACLE_DB_PATH, TEST_COLLECTION as QA_TEST_COLLECTION,
    QDRANT_URL as QA_QDRANT_URL, EMBEDDING_BGE_SMALL,
    RETRIEVAL_CHUNK_SIZE, RETRIEVAL_CHUNK_OVERLAP,
)

DB_PATH = PINNACLE_DB_PATH
QDRANT_URL = QA_QDRANT_URL
TEST_COLLECTION = QA_TEST_COLLECTION
EMBED_MODEL = EMBEDDING_BGE_SMALL['name']
CHUNK_SIZE = RETRIEVAL_CHUNK_SIZE
CHUNK_OVERLAP = RETRIEVAL_CHUNK_OVERLAP

# ═══════════════════════════════════════════════════════════════════════════
# CURATED CHAT DOCUMENTS
# Each document is a realistic conversation. We control chunking so we know
# exactly which chunk contains each answer.
# ═══════════════════════════════════════════════════════════════════════════

CHAT_DOC_1 = """=== MESSAGE 0 - User ===
Can you explain VBStyle architecture? Start with MemUnit.

=== MESSAGE 1 - Assistant ===
MemUnit is the core execution authority in VBStyle. It is the only place where execution runs. It acts as a dispatcher, not a selector. The orchestrator loads a precomputed path and MemUnit executes it deterministically. Every class receives mem as a parameter and communicates through memunit.get and memunit.put. No direct imports between classes. MemUnit is the shared memory bus — CORE_MEMUNIT connects everything. Config values like db_user, db_name, sqlite_db_path, and embed_dim all flow through CORE_MEMUNIT.

=== MESSAGE 2 - User ===
What about the boot sequence?

=== MESSAGE 3 - Assistant ===
The boot spine is fixed and deterministic. The order is Config, then MemDB, then AST, then Brackets, then ClassDB, then Orchestration, then MemUnit, then Report, then Output. This order cannot break. Config loads from BCL brackets. MemDB creates in-memory SQLite runtime state. AST validates syntax. Brackets parse BCL. ClassDB maps classes to domains. Orchestration resolves dependencies. MemUnit dispatches. Report handles output. Output delivers results.

=== MESSAGE 4 - User ===
What is BCL?

=== MESSAGE 5 - Assistant ===
BCL stands for Bracket Configuration Language. It uses syntax [@name]{...} for both passive configuration and active commands. BCL-Config is passive state read by dom_config. BCL-Command is active execution run through MemUnit. Same syntax, different consumer. Config is read. Command is executed.

=== MESSAGE 6 - User ===
What are the main rules?

=== MESSAGE 7 - Assistant ===
Rule 7: NO print statements. Use the Report class or logging instead. Rule 8: NO hardcoded paths. Nothing is allowed to be hardcoded. Database names and users must come from config or memunit. All methods must return Tuple3 format: (ok, data, error). On success return (1, data, None). On error return (0, None, error_tuple). The constructor signature is def __init__(self, mem=None, db=None, param=None). No self._ variables — use self.state dictionary. No decorators. No enums. Class names PascalCase. Constants UPPERCASE at class level.

=== MESSAGE 8 - User ===
What database does the system use?

=== MESSAGE 9 - Assistant ===
MemDB is an in-memory SQLite database serving as runtime state substrate. It operates in RAM with SQLite tables as channels. MemDB uses port 7011 for its operations. The persistent storage is MySQL, specifically the vb_shared database containing rules, learned_rules, know_lessons, code_classes, and class_understandings. Never hardcode the database name — always read from memunit config.

=== MESSAGE 10 - User ===
Tell me about the GUI engine.

=== MESSAGE 11 - Assistant ===
The GUI engine is a declarative system. Components are assembled from rules based on context, not generated from scratch. It uses .gengui bundle format with write and render modes. The Swift-facing API uses EngineHostDelegate. Control aspects map to SwiftUI. Context-driven assembly looks at data shape, data size, field count, user intent, and interaction type. If data_shape is tabular and data_size is greater than 5 and field_count is greater than 3, it renders a grid. If user_intent is search and interaction_type is input, it renders a search field.

=== MESSAGE 12 - User ===
How does error handling work?

=== MESSAGE 13 - Assistant ===
ErrorCapture standardizes all errors. Error becomes data, not control flow interruption. Every method returns uniform Tuple3: (status, data, error). Error tuple format is (code, description, 0). The system never raises exceptions — it captures them and returns as data. Reporter handles central output with no print statements allowed. All output goes through Reporter which returns strings.

=== MESSAGE 14 - User ===
What about the book?

=== MESSAGE 15 - Assistant ===
The VBStyle book has 56 chapters, 111 sections, 185 content blocks, and 31,344 words. The longest chapter is Wayne's Container Laws at 1,688 words. The shortest is The Constructor Pattern at 237 words. Zero chapters under 200 words. The book covers boot spine, MemUnit, BCL, Tuple3, state dictionary, prohibition rules, ghost headers, domain collapse law, magnetic trajectory engine, and zero-drift philosophy.

=== MESSAGE 16 - User ===
What is Zero-Drift?

=== MESSAGE 17 - Assistant ===
The Zero-Drift Philosophy states that code should be written so the problem never occurs. Prevention over correction. Do not write code where you go back and fix it. Always use core classes. No raw open(), no raw mysql.connect(), no json.load(). Write code so the problem NEVER occurs. This is the opposite of defensive programming. In Zero-Drift, you structure the code so the error path is impossible.
"""

# Chat doc 2: Hierarchy, temporal, contradictions, near-misses
CHAT_DOC_2 = """=== MESSAGE 0 - User ===
How is the class hierarchy organized? What owns what?

=== MESSAGE 1 - Assistant ===
The hierarchy is strict. MemUnit is the top-level execution authority. Under MemUnit, there are three subsystems. Brackets handles BCL parsing and validation. AST handles syntax tree structure and validation. Config handles configuration loading from BCL brackets. Each subsystem owns its domain completely. Brackets owns the bracket parsing domain. AST owns the syntax validation domain. Config owns the configuration domain. No class crosses domain boundaries. This is the Domain Collapse Law — one class, one domain, one authority.

=== MESSAGE 2 - User ===
Was there a change in how the authority was named? I remember MainUnit.

=== MESSAGE 3 - Assistant ===
Yes. In Rule version 1, the authority was called MainUnit. In Rule version 2, it was renamed to MemUnit. The current authority is MemUnit. The rename happened because MemUnit better reflects that it is a memory bus, not just a main unit. All new code must use MemUnit. Legacy code referencing MainUnit should be updated. The current version is Rule version 2.

=== MESSAGE 4 - User ===
I see conflicting port numbers in different docs. Which is correct?

=== MESSAGE 5 - Assistant ===
There is a known conflict. Document A states MemDB uses port 7011. Document B states MemDB uses port 7012. The correct port is 7011. Document B is outdated and contains an error. Port 7012 was a typo that propagated through copied documentation. The authoritative source is the MemDB configuration in code_classes which confirms port 7011. When conflicts arise, always defer to code_classes as the source of truth.

=== MESSAGE 6 - User ===
Are there similar port numbers I should be aware of?

=== MESSAGE 7 - Assistant ===
Yes. Port 7011 is MemDB. Port 7012 is a typo and should not be used. Port 7013 is the Qdrant vector database REST API. Port 6333 is the alternative Qdrant port used in some configurations. Port 8080 is the GUI engine web interface. Port 3306 is MySQL. Each port serves a specific purpose and must not be confused with others.
"""

# Chat doc 3: Conversation transcript with decisions
CHAT_DOC_3 = """=== MESSAGE 0 - User ===
I want to change the constructor naming convention. Currently we use __init__. Should we rename it?

=== MESSAGE 1 - Assistant ===
After discussion, the decision was made to keep the constructor name as __init__. This is because __init__ is the Python standard and renaming it would break compatibility with the language itself. However, the signature was standardized. The constructor signature must be def __init__(self, mem=None, db=None, param=None). The mem parameter is the shared memory bus. The db parameter is the database connection. The param parameter is optional configuration. All three default to None. The state dictionary is initialized inside the constructor with keys: config, catalog, results, errors, and meta.

=== MESSAGE 2 - User ===
What about the return type? Should we use dict or tuple?

=== MESSAGE 3 - Assistant ===
The decision was made to use Tuple3 for all method returns: (ok, data, error). On success: (1, data, None). On error: (0, None, (code, description, 0)). This was chosen over dict returns because tuples are immutable, faster, and enforce a consistent contract. The ok field is 1 for success and 0 for failure. The data field contains the result. The error field contains None on success or an error tuple on failure.
"""

# ═══════════════════════════════════════════════════════════════════════════
# TEST QUESTIONS
# Each question is tagged with:
#   aspect: which test aspect this covers (1-15 from the plan)
#   expected_chunk_ids: which chunks (by 1-based Qdrant ID) contain the answer
#   expected_answer: the answer text we expect BERT QA to extract
#   expected_mode: TRUE / FALSE / UNKNOWN
# ═══════════════════════════════════════════════════════════════════════════

# Chunk IDs are assigned sequentially per document.
# Doc 1: chunks 1-N (15 chunks at size=400, overlap=80)
# Doc 2: chunks (N+1)-M
# Doc 3: chunks (M+1)-K
# We'll compute exact chunk IDs after chunking.

# For now, we define questions with expected_chunk_keywords — text that should
# appear in the correct chunk. The harness will match chunks to questions
# after chunking by searching for these keywords.

TEST_QUESTIONS = [
    # ─── Aspect 1: Retrieval Accuracy ───
    {"id": "R01", "aspect": "retrieval", "question": "What is MemUnit?",
     "expected_answer": "the core execution authority", "expected_mode": "TRUE",
     "chunk_keyword": "core execution authority"},
    {"id": "R02", "aspect": "retrieval", "question": "What does BCL stand for?",
     "expected_answer": "bracket configuration language", "expected_mode": "TRUE",
     "chunk_keyword": "bracket configuration language"},
    {"id": "R03", "aspect": "retrieval", "question": "What port does MemDB use?",
     "expected_answer": "7011", "expected_mode": "TRUE",
     "chunk_keyword": "port 7011 for its operations"},

    # ─── Aspect 2: Chunk Boundary Failure ───
    # The boot spine order may span a chunk boundary depending on chunking
    {"id": "C01", "aspect": "chunking", "question": "What is the boot spine order?",
     "expected_answer": "config", "expected_mode": "TRUE",
     "chunk_keyword": "config, then memdb, then ast"},

    # ─── Aspect 3: Code Extraction ───
    {"id": "CO01", "aspect": "code", "question": "What is the constructor signature in VBStyle?",
     "expected_answer": "def __init__(self, mem=None, db=None, param=None)", "expected_mode": "TRUE",
     "chunk_keyword": "def __init__(self, mem=None, db=None, param=None)"},
    {"id": "CO02", "aspect": "code", "question": "What is the default value of the mem parameter?",
     "expected_answer": "none", "expected_mode": "TRUE",
     "chunk_keyword": "def __init__(self, mem=None, db=None, param=None)"},

    # ─── Aspect 4: Semantic Retrieval (synonyms) ───
    {"id": "S01", "aspect": "synonyms", "question": "What controls execution?",
     "expected_answer": "memunit", "expected_mode": "TRUE",
     "chunk_keyword": "core execution authority"},
    {"id": "S02", "aspect": "synonyms", "question": "What governs the runtime?",
     "expected_answer": "memunit", "expected_mode": "TRUE",
     "chunk_keyword": "core execution authority"},
    {"id": "S03", "aspect": "synonyms", "question": "What is the execution authority?",
     "expected_answer": "memunit", "expected_mode": "TRUE",
     "chunk_keyword": "core execution authority"},

    # ─── Aspect 5: Negation ───
    {"id": "N01", "aspect": "negation", "question": "Are print statements allowed in VBStyle?",
     "expected_answer": "no", "expected_mode": "TRUE",
     "chunk_keyword": "no print statements"},
    {"id": "N02", "aspect": "negation", "question": "Is it okay to hardcode database names?",
     "expected_answer": "no", "expected_mode": "TRUE",
     "chunk_keyword": "no hardcoded paths"},

    # ─── Aspect 6: Adversarial Unknowns ───
    {"id": "U01", "aspect": "unknowns", "question": "What is the capital of Japan?",
     "expected_answer": None, "expected_mode": "UNKNOWN", "chunk_keyword": None},
    {"id": "U02", "aspect": "unknowns", "question": "How do I configure nginx for load balancing?",
     "expected_answer": None, "expected_mode": "UNKNOWN", "chunk_keyword": None},
    {"id": "U03", "aspect": "unknowns", "question": "What is the airspeed of an unladen swallow?",
     "expected_answer": None, "expected_mode": "UNKNOWN", "chunk_keyword": None},
    {"id": "U04", "aspect": "unknowns", "question": "How tall is the Eiffel Tower?",
     "expected_answer": None, "expected_mode": "UNKNOWN", "chunk_keyword": None},

    # ─── Aspect 7: Near Misses ───
    {"id": "NM01", "aspect": "near_miss", "question": "What port does MemDB use?",
     "expected_answer": "7011", "expected_mode": "TRUE",
     "chunk_keyword": "port 7011 is memdb"},
    {"id": "NM02", "aspect": "near_miss", "question": "What is port 7012 used for?",
     "expected_answer": "a typo", "expected_mode": "TRUE",
     "chunk_keyword": "port 7012 is a typo"},

    # ─── Aspect 8: Multi Evidence ───
    # MemDB is described in both doc 1 (port, in-memory SQLite) and doc 2 (hierarchy)
    {"id": "ME01", "aspect": "multi_evidence", "question": "What is MemDB?",
     "expected_answer": "in-memory sqlite", "expected_mode": "TRUE",
     "chunk_keyword": "in-memory sqlite database"},

    # ─── Aspect 9: Hierarchy ───
    {"id": "H01", "aspect": "hierarchy", "question": "What belongs under MemUnit?",
     "expected_answer": "brackets", "expected_mode": "TRUE",
     "chunk_keyword": "under memunit, there are three subsystems"},
    {"id": "H02", "aspect": "hierarchy", "question": "Who owns AST?",
     "expected_answer": "memunit", "expected_mode": "TRUE",
     "chunk_keyword": "ast handles syntax tree structure"},

    # ─── Aspect 10: Conversation Recovery ───
    {"id": "CV01", "aspect": "conversation", "question": "What decision was made about constructor naming?",
     "expected_answer": "keep the constructor name as __init__", "expected_mode": "TRUE",
     "chunk_keyword": "keep the constructor name as __init__"},
    {"id": "CV02", "aspect": "conversation", "question": "Was Tuple3 or dict chosen for return type?",
     "expected_answer": "tuple3", "expected_mode": "TRUE",
     "chunk_keyword": "use tuple3 for all method returns"},

    # ─── Aspect 11: Temporal / Authority Resolution ───
    {"id": "T01", "aspect": "temporal", "question": "What is the current authority name?",
     "expected_answer": "memunit", "expected_mode": "TRUE",
     "chunk_keyword": "the current authority is memunit"},
    {"id": "T02", "aspect": "temporal", "question": "What was the old authority name?",
     "expected_answer": "mainunit", "expected_mode": "TRUE",
     "chunk_keyword": "the authority was called mainunit"},

    # ─── Aspect 15: Contradictions ───
    {"id": "CT01", "aspect": "contradiction", "question": "What is the correct MemDB port?",
     "expected_answer": "7011", "expected_mode": "TRUE",
     "chunk_keyword": "the correct port is 7011"},

    # ─── Aspect FALSE: VBStyle questions not in the chat ───
    {"id": "F01", "aspect": "false_positive", "question": "What is the Magnetic Trajectory Engine?",
     "expected_answer": None, "expected_mode": "FALSE", "chunk_keyword": None},
    {"id": "F02", "aspect": "false_positive", "question": "How does the 12-layer tokenized search work?",
     "expected_answer": None, "expected_mode": "FALSE", "chunk_keyword": None},
    {"id": "F03", "aspect": "false_positive", "question": "What is the Qdrant collection for bracket patterns?",
     "expected_answer": None, "expected_mode": "FALSE", "chunk_keyword": None},
]


# ═══════════════════════════════════════════════════════════════════════════
# CHUNKING
# ═══════════════════════════════════════════════════════════════════════════

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


def find_expected_chunks(chunks, keyword):
    """Find which chunk indices contain the expected keyword."""
    if keyword is None:
        return []
    keyword_lower = keyword.lower()
    return [i + 1 for i, chunk in enumerate(chunks) if keyword_lower in chunk.lower()]


# ═══════════════════════════════════════════════════════════════════════════
# QDRANT
# ═══════════════════════════════════════════════════════════════════════════

def qdrant_request(endpoint, payload=None, method="GET"):
    url = f"{QDRANT_URL}{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def create_qdrant_collection(name, vector_size=384):
    try:
        qdrant_request(f"/collections/{name}", method="DELETE")
    except Exception:
        pass
    qdrant_request(f"/collections/{name}", {"vectors": {"size": vector_size, "distance": "Cosine"}}, method="PUT")


def embed_and_upsert(name, chunks, embedder, doc_id):
    vectors = embedder.encode(chunks)
    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        points.append({
            "id": i + 1,
            "vector": vec.tolist(),
            "payload": {
                "text": chunk,
                "chunk_index": i,
                "doc_id": doc_id,
                "source": f"chat_doc_{doc_id}",
            },
        })
    batch_size = 50
    for i in range(0, len(points), batch_size):
        qdrant_request(f"/collections/{name}/points?wait=true", {"points": points[i:i+batch_size]}, method="PUT")
    return len(points)


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════════════════════════

def setup_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE chat_docs (
        id INTEGER PRIMARY KEY, content TEXT NOT NULL,
        chunk_count INTEGER NOT NULL, created_at TEXT DEFAULT (datetime('now')))""")

    c.execute("""CREATE TABLE chat_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL, chunk_index INTEGER NOT NULL,
        chunk_text TEXT NOT NULL, qdrant_id INTEGER NOT NULL,
        FOREIGN KEY (doc_id) REFERENCES chat_docs(id))""")

    c.execute("""CREATE TABLE qa_tests (
        id TEXT PRIMARY KEY, aspect TEXT NOT NULL,
        question TEXT NOT NULL, expected_answer TEXT,
        expected_mode TEXT NOT NULL, expected_chunk_ids TEXT,
        chunk_keyword TEXT, note TEXT)""")

    c.execute("""CREATE TABLE qa_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id TEXT NOT NULL, question TEXT NOT NULL,
        expected_answer TEXT, expected_mode TEXT NOT NULL,
        expected_chunk_ids TEXT,
        retrieved_chunk_ids TEXT, retrieval_scores TEXT,
        retrieved_rank INTEGER, retrieval_correct INTEGER,
        qa_answer TEXT, qa_confidence REAL, answer_correct INTEGER,
        final_mode TEXT NOT NULL, mode_correct INTEGER NOT NULL,
        latency_embed REAL, latency_search REAL, latency_qa REAL,
        failure_stage TEXT NOT NULL,
        run_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (test_id) REFERENCES qa_tests(id))""")

    # Chunk all documents
    docs = [(1, CHAT_DOC_1), (2, CHAT_DOC_2), (3, CHAT_DOC_3)]
    all_chunks = []
    global_chunk_id = 0

    for doc_id, content in docs:
        chunks = chunk_text(content)
        c.execute("INSERT INTO chat_docs (id, content, chunk_count) VALUES (?, ?, ?)",
                  (doc_id, content, len(chunks)))
        for i, chunk in enumerate(chunks):
            global_chunk_id += 1
            c.execute("INSERT INTO chat_chunks (doc_id, chunk_index, chunk_text, qdrant_id) VALUES (?, ?, ?, ?)",
                      (doc_id, i, chunk, global_chunk_id))
            all_chunks.append((global_chunk_id, chunk))
        print(f"  Doc {doc_id}: {len(chunks)} chunks (Qdrant IDs {global_chunk_id - len(chunks) + 1}-{global_chunk_id})")

    # Match test questions to expected chunks
    for q in TEST_QUESTIONS:
        expected_ids = find_expected_chunks([c[1] for c in all_chunks], q.get("chunk_keyword"))
        expected_ids_str = json.dumps(expected_ids) if expected_ids else "[]"
        c.execute("""INSERT INTO qa_tests (id, aspect, question, expected_answer, expected_mode, expected_chunk_ids, chunk_keyword)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (q["id"], q["aspect"], q["question"], q["expected_answer"],
                   q["expected_mode"], expected_ids_str, q.get("chunk_keyword")))

    conn.commit()

    # Print chunk mapping for verification
    print(f"\n  Total chunks: {len(all_chunks)}")
    print(f"  Test questions: {len(TEST_QUESTIONS)}")

    aspect_counts = {}
    for q in TEST_QUESTIONS:
        aspect_counts[q["aspect"]] = aspect_counts.get(q["aspect"], 0) + 1
    print(f"  Aspects covered: {len(aspect_counts)}")
    for aspect, count in sorted(aspect_counts.items()):
        print(f"    {aspect}: {count}")

    # Show expected chunk mapping
    print(f"\n  Expected chunk mapping:")
    rows = c.execute("SELECT id, aspect, question, expected_chunk_ids FROM qa_tests ORDER BY id").fetchall()
    for tid, aspect, question, chunk_ids in rows:
        print(f"    {tid:5s} [{aspect:15s}] {question[:40]:40s} -> chunks: {chunk_ids}")

    conn.close()

    # Embed into Qdrant
    print(f"\nEmbedding {len(all_chunks)} chunks into Qdrant: {TEST_COLLECTION}")
    create_qdrant_collection(TEST_COLLECTION)
    print("  Loading BGE embedder...")
    embedder = SentenceTransformer(EMBED_MODEL)

    # Embed all chunks as one batch (they share one collection)
    chunk_texts = [c[1] for c in all_chunks]
    vectors = embedder.encode(chunk_texts)
    points = []
    for i, (chunk_id, chunk_txt) in enumerate(all_chunks):
        points.append({
            "id": chunk_id,
            "vector": vectors[i].tolist(),
            "payload": {"text": chunk_txt, "chunk_index": i, "source": "pinnacle_test"},
        })
    for i in range(0, len(points), 50):
        qdrant_request(f"/collections/{TEST_COLLECTION}/points?wait=true",
                       {"points": points[i:i+50]}, method="PUT")
    print(f"  Upserted {len(points)} points")

    info = qdrant_request(f"/collections/{TEST_COLLECTION}")
    print(f"  Collection ready: {info['result']['points_count']} points")


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def run_tests():
    from qa_prototype import GhostQA
    from transformers import BertTokenizer
    import coremltools as ct

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    tests = c.execute("""
        SELECT id, aspect, question, expected_answer, expected_mode, expected_chunk_ids
        FROM qa_tests ORDER BY id
    """).fetchall()

    print(f"\nRunning {len(tests)} tests through full pipeline...")
    print(f"  Stages: EMBED -> SEARCH Qdrant -> BERT QA EXTRACT -> CLASSIFY")
    print()

    # Load models once
    print("  Loading models...")
    qa = GhostQA()
    qa.Run("load_models")
    qa.Run("set_config", {"config": {"qdrant_collections": [TEST_COLLECTION]}})

    # Get the embedder and QA model directly for per-stage latency
    embedder = qa.embedder
    qa_model = qa.qa_model
    tokenizer = qa.tokenizer

    print(f"  Models loaded. Starting tests...\n")

    header = f"{'ID':5s} {'Aspect':15s} {'Exp':5s} {'Act':5s} {'OK':3s} {'Stage':10s} {'Conf':>8s} {'Rank':>5s} {'Retr':>7s} {'eMs':>5s} {'sMs':>5s} {'qMs':>5s} {'Question':35s} {'Extracted':20s}"
    print(header)
    print("-" * len(header))

    total = 0
    mode_correct_count = 0
    answer_correct_count = 0
    retrieval_correct_count = 0
    failure_stages = {}

    for test_id, aspect, question, expected_answer, expected_mode, expected_chunk_ids_json in tests:
        total += 1
        expected_chunk_ids = json.loads(expected_chunk_ids_json) if expected_chunk_ids_json else []

        # ─── STAGE 1: EMBED ───
        t0 = time.time()
        question_vec = embedder.encode([question])[0].tolist()
        latency_embed = (time.time() - t0) * 1000

        # ─── STAGE 2: SEARCH QDRANT ───
        t0 = time.time()
        search_payload = {
            "vector": question_vec,
            "limit": 10,
            "with_payload": True,
            "with_vector": False,
        }
        try:
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/{TEST_COLLECTION}/points/search",
                data=json.dumps(search_payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                search_result = json.loads(resp.read().decode())
        except Exception as e:
            search_result = {"result": []}

        latency_search = (time.time() - t0) * 1000

        hits = search_result.get("result", [])
        retrieved_chunk_ids = [hit.get("id") for hit in hits]
        retrieval_scores = [hit.get("score", 0) for hit in hits]

        # Measure retrieval accuracy
        if expected_chunk_ids:
            # Check if any expected chunk is in retrieved results
            retrieved_rank = None
            for rank, cid in enumerate(retrieved_chunk_ids, 1):
                if cid in expected_chunk_ids:
                    retrieved_rank = rank
                    break
            retrieval_correct = 1 if retrieved_rank is not None else 0
        else:
            retrieved_rank = None
            retrieval_correct = 0  # No expected chunks for FALSE/UNKNOWN

        # Get top chunks for QA
        threshold = qa.state["config"]["retrieval_threshold"]
        top_chunks = []
        for hit in hits[:5]:
            score = hit.get("score", 0)
            if score >= threshold:
                pd = hit.get("payload", {})
                text = pd.get("text", "")
                if text:
                    top_chunks.append({"source": f"qdrant:{TEST_COLLECTION}", "score": score, "text": text, "id": hit.get("id")})

        # ─── STAGE 3: QA EXTRACT ───
        best_answer = ""
        best_confidence = -999.0
        best_chunk = None
        qa_latency_total = 0

        for chunk in top_chunks:
            t0 = time.time()
            encoded = tokenizer(
                question, chunk["text"],
                add_special_tokens=True, return_tensors="np",
                max_length=qa.state["config"]["qa_max_length"],
                truncation=True, padding="max_length",
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
            qa_latency_total += (time.time() - t0) * 1000

            if confidence > best_confidence:
                best_answer = answer
                best_confidence = confidence
                best_chunk = chunk

        latency_qa = qa_latency_total

        # ─── STAGE 4: CLASSIFY ───
        qa_threshold = qa.state["config"]["qa_confidence_threshold"]
        if not top_chunks or best_confidence < qa_threshold:
            final_mode = "UNKNOWN"
        elif expected_answer is not None and expected_answer.lower() in best_answer.lower():
            final_mode = "TRUE"
        else:
            final_mode = "FALSE"

        mode_correct = 1 if final_mode == expected_mode else 0

        # Answer content check
        if expected_answer is not None:
            answer_correct = 1 if expected_answer.lower() in best_answer.lower() else 0
        else:
            answer_correct = 1 if final_mode in ("UNKNOWN", "FALSE") else 0

        # ─── FAILURE STAGE DIAGNOSIS ───
        if mode_correct:
            failure_stage = "NONE"
        elif expected_mode == "TRUE" and final_mode != "TRUE":
            if not top_chunks:
                failure_stage = "RETRIEVAL"
            elif retrieval_correct == 0 and expected_chunk_ids:
                failure_stage = "RETRIEVAL"
            elif best_confidence < qa_threshold:
                failure_stage = "THRESHOLD"
            else:
                failure_stage = "QA"
        elif expected_mode in ("FALSE", "UNKNOWN") and final_mode == "TRUE":
            failure_stage = "THRESHOLD"
        elif expected_mode in ("FALSE", "UNKNOWN") and final_mode == "FALSE":
            failure_stage = "NONE"  # FALSE is acceptable for FALSE/UNKNOWN
        else:
            failure_stage = "UNKNOWN_STAGE"

        # Track stats
        mode_correct_count += mode_correct
        answer_correct_count += answer_correct
        if expected_chunk_ids:
            retrieval_correct_count += retrieval_correct
        failure_stages[failure_stage] = failure_stages.get(failure_stage, 0) + 1

        # Store result
        c.execute("""INSERT INTO qa_results
            (test_id, question, expected_answer, expected_mode, expected_chunk_ids,
             retrieved_chunk_ids, retrieval_scores, retrieved_rank, retrieval_correct,
             qa_answer, qa_confidence, answer_correct, final_mode, mode_correct,
             latency_embed, latency_search, latency_qa, failure_stage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (test_id, question, expected_answer, expected_mode, json.dumps(expected_chunk_ids),
             json.dumps(retrieved_chunk_ids), json.dumps([round(s, 4) for s in retrieval_scores]),
             retrieved_rank, retrieval_correct,
             best_answer, round(best_confidence, 4), answer_correct, final_mode, mode_correct,
             round(latency_embed, 2), round(latency_search, 2), round(latency_qa, 2), failure_stage))
        conn.commit()

        status = "Y" if mode_correct else "X"
        ext_display = (best_answer or "None")[:20]
        rank_display = str(retrieved_rank) if retrieved_rank else "-"
        retr_display = f"{retrieval_scores[0]:.4f}" if retrieval_scores else "-"
        print(f"{test_id:5s} {aspect:15s} {expected_mode:5s} {final_mode:5s} {status:3s} {failure_stage:10s} {best_confidence:8.2f} {rank_display:>5s} {retr_display:>7s} {latency_embed:5.0f} {latency_search:5.0f} {latency_qa:5.0f} {question[:35]:35s} {ext_display:20s}")

    print("-" * len(header))
    print(f"\nSUMMARY:")
    print(f"  Total tests:          {total}")
    print(f"  Mode correct:         {mode_correct_count}/{total} ({mode_correct_count/total*100:.0f}%)")
    print(f"  Answer correct:       {answer_correct_count}/{total} ({answer_correct_count/total*100:.0f}%)")
    retrieval_tests = sum(1 for t in tests if t[5] and json.loads(t[5]))
    if retrieval_tests > 0:
        print(f"  Retrieval correct:    {retrieval_correct_count}/{retrieval_tests} ({retrieval_correct_count/retrieval_tests*100:.0f}%)")
    print(f"  Failure stages: {failure_stages}")

    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════

def report():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("\n" + "=" * 130)
    print("PINNACLE HARNESS — FULL PIPELINE REPORT")
    print("=" * 130)

    # ─── Overall metrics ───
    print("\n--- OVERALL ---")
    row = c.execute("""SELECT
        COUNT(*), SUM(mode_correct), SUM(answer_correct),
        AVG(latency_embed), AVG(latency_search), AVG(latency_qa)
        FROM qa_results""").fetchone()
    total, mode_ok, ans_ok, avg_e, avg_s, avg_q = row
    print(f"  Total: {total} | Mode: {mode_ok}/{total} ({mode_ok/total*100:.0f}%) | Answer: {ans_ok}/{total} ({ans_ok/total*100:.0f}%)")
    print(f"  Latency avg: embed={avg_e:.1f}ms search={avg_s:.1f}ms qa={avg_q:.1f}ms total={avg_e+avg_s+avg_q:.1f}ms")

    # ─── Retrieval metrics (R@1, R@3, R@5, MRR) ───
    print("\n--- RETRIEVAL ACCURACY (only for questions with expected chunks) ---")
    rows = c.execute("""SELECT retrieved_rank FROM qa_results
        WHERE expected_chunk_ids != '[]' AND retrieved_rank IS NOT NULL""").fetchall()
    ranks = [r[0] for r in rows]
    total_retrieval = c.execute("SELECT COUNT(*) FROM qa_results WHERE expected_chunk_ids != '[]'").fetchone()[0]
    r1 = sum(1 for r in ranks if r <= 1)
    r3 = sum(1 for r in ranks if r <= 3)
    r5 = sum(1 for r in ranks if r <= 5)
    mrr = sum(1.0 / r for r in ranks) / total_retrieval if total_retrieval > 0 else 0
    missed = total_retrieval - len(ranks)
    print(f"  Total with expected chunks: {total_retrieval}")
    print(f"  R@1: {r1}/{total_retrieval} ({r1/total_retrieval*100:.0f}%)")
    print(f"  R@3: {r3}/{total_retrieval} ({r3/total_retrieval*100:.0f}%)")
    print(f"  R@5: {r5}/{total_retrieval} ({r5/total_retrieval*100:.0f}%)")
    print(f"  MRR: {mrr:.3f}")
    print(f"  Missed (not in top 10): {missed}")

    # ─── Per-aspect breakdown ───
    print("\n--- BY ASPECT ---")
    rows = c.execute("""SELECT
        t.aspect, COUNT(*), SUM(r.mode_correct), SUM(r.answer_correct),
        AVG(r.qa_confidence), AVG(r.retrieval_correct)
        FROM qa_results r JOIN qa_tests t ON r.test_id = t.id
        GROUP BY t.aspect ORDER BY t.aspect""").fetchall()
    print(f"{'Aspect':20s} {'Total':>6s} {'ModeOK':>7s} {'AnsOK':>6s} {'AvgConf':>9s} {'RetrOK':>7s}")
    print("-" * 60)
    for aspect, tot, m_ok, a_ok, avg_conf, avg_retr in rows:
        print(f"{aspect:20s} {tot:6d} {m_ok:7d} {a_ok:6d} {avg_conf:9.2f} {avg_retr:7.2f}")

    # ─── Failure stage breakdown ───
    print("\n--- FAILURE STAGES ---")
    rows = c.execute("""SELECT failure_stage, COUNT(*) FROM qa_results
        GROUP BY failure_stage ORDER BY COUNT(*) DESC""").fetchall()
    print(f"{'Stage':15s} {'Count':>6s} {'%':>6s}")
    print("-" * 30)
    for stage, count in rows:
        print(f"{stage:15s} {count:6d} {count/total*100:5.0f}%")

    # ─── Confusion matrix ───
    print("\n--- CONFUSION MATRIX ---")
    rows = c.execute("""SELECT expected_mode, final_mode, COUNT(*)
        FROM qa_results GROUP BY expected_mode, final_mode
        ORDER BY expected_mode, final_mode""").fetchall()
    matrix = {}
    for exp, act, count in rows:
        matrix[(exp, act)] = count
    print(f"{'Expected':10s} | {'TRUE':8s} {'FALSE':8s} {'UNKNOWN':8s}")
    print("-" * 40)
    for exp in ["TRUE", "FALSE", "UNKNOWN"]:
        vals = [matrix.get((exp, a), 0) for a in ["TRUE", "FALSE", "UNKNOWN"]]
        print(f"{exp:10s} | {vals[0]:8d} {vals[1]:8d} {vals[2]:8d}")

    # ─── Confidence calibration ───
    print("\n--- CONFIDENCE CALIBRATION ---")
    buckets = [(8.0, 99), (6.0, 90), (4.0, 70), (2.0, 30), (-999.0, 0)]
    for threshold, expected_pct in buckets:
        row = c.execute("""SELECT COUNT(*), SUM(answer_correct) FROM qa_results
            WHERE qa_confidence >= ?""", (threshold,)).fetchone()
        count, correct = row
        if count > 0:
            actual_pct = correct / count * 100
            print(f"  Conf >= {threshold:6.1f}: {count:3d} tests, {correct}/{count} correct ({actual_pct:.0f}%)")

    # ─── Detailed failures ───
    print("\n--- FAILURES (mode_correct = 0) ---")
    rows = c.execute("""SELECT
        r.test_id, t.aspect, r.question, r.qa_answer, r.qa_confidence,
        r.expected_answer, r.expected_mode, r.final_mode, r.failure_stage,
        r.retrieved_rank, r.retrieval_correct, r.expected_chunk_ids, r.retrieved_chunk_ids
        FROM qa_results r JOIN qa_tests t ON r.test_id = t.id
        WHERE r.mode_correct = 0 ORDER BY r.test_id""").fetchall()
    if rows:
        for tid, aspect, q, ans, conf, exp_ans, exp_mode, act_mode, stage, rank, retr_ok, exp_chunks, ret_chunks in rows:
            print(f"\n  {tid} [{aspect}] {q[:50]}")
            print(f"    Extracted: '{(ans or 'None')[:50]}' (conf={conf:.2f})")
            print(f"    Expected: '{(exp_ans or 'None')[:50]}' mode={exp_mode} got={act_mode}")
            print(f"    Failure stage: {stage}")
            print(f"    Retrieval: rank={rank} correct={retr_ok} expected_chunks={exp_chunks} retrieved={ret_chunks[:60]}")
    else:
        print("  None")

    # ─── Latency breakdown ───
    print("\n--- LATENCY BREAKDOWN ---")
    rows = c.execute("""SELECT
        t.aspect, AVG(r.latency_embed), AVG(r.latency_search), AVG(r.latency_qa)
        FROM qa_results r JOIN qa_tests t ON r.test_id = t.id
        GROUP BY t.aspect ORDER BY t.aspect""").fetchall()
    print(f"{'Aspect':20s} {'Embed(ms)':>10s} {'Search(ms)':>11s} {'QA(ms)':>8s} {'Total(ms)':>10s}")
    print("-" * 65)
    for aspect, e, s, q in rows:
        print(f"{aspect:20s} {e:10.1f} {s:11.1f} {q:8.1f} {e+s+q:10.1f}")

    conn.close()


def clean():
    try:
        qdrant_request(f"/collections/{TEST_COLLECTION}", method="DELETE")
        print(f"Deleted Qdrant collection: {TEST_COLLECTION}")
    except Exception:
        pass
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted: {DB_PATH}")


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
        print("Usage: python3 pinnacle_harness.py [--setup|--run|--report|--clean|--all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
