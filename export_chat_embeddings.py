#!/usr/bin/env python3
"""
export_chat_embeddings.py — Export ALL chat history → Qdrant embeddings.

Sources:
  1. Chat_History MySQL database (messages table)
  2. Devin CLI session transcripts on disk (82 history_*.md files)

Target: Qdrant collection "chat_history" (384-dim BGE embeddings)

Usage:
    python3 export_chat_embeddings.py                    # full export
    python3 export_chat_embeddings.py --mysql-only       # just MySQL messages
    python3 export_chat_embeddings.py --disk-only        # just disk history files
    python3 export_chat_embeddings.py --batch-size 256   # custom batch size
    python3 export_chat_embeddings.py --resume           # skip already embedded
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.request
import urllib.error

import mysql.connector

logger = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
COLLECTION = "chat_history"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
HISTORY_DIR = os.environ.get('DEVIN_SUMMARIES_DIR', os.path.expanduser('~/.local/share/devin/cli/summaries'))

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading model: {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        print("Model loaded.")
    return _model


def qdrant_get(path):
    url = f"{QDRANT_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def qdrant_post(path, payload, timeout=60):
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def qdrant_put(path, payload, timeout=60):
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ensure_collection():
    """Create Qdrant collection if it doesn't exist."""
    try:
        info = qdrant_get(f"/collections/{COLLECTION}")
        count = info.get("result", {}).get("points_count", 0)
        print(f"Collection '{COLLECTION}' exists: {count} points")
        return count
    except urllib.error.HTTPError:
        pass

    print(f"Creating collection '{COLLECTION}' (384-dim, cosine)...")
    payload = {
        "vectors": {
            "size": 384,
            "distance": "Cosine"
        },
        "optimizers_config": {
            "default_segment_number": 4
        }
    }
    qdrant_put(f"/collections/{COLLECTION}", payload)
    print("Collection created.")
    return 0


def embed_texts(texts):
    """Embed a batch of texts using BGE model. Returns list of 384-dim vectors."""
    model = get_model()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=64)
    return [v.tolist() for v in vectors]


def upsert_points(points, timeout=120):
    """Upsert points to Qdrant. points = list of {id, vector, payload}."""
    payload = {"points": points}
    qdrant_put(f"/collections/{COLLECTION}/points?wait=true", payload, timeout=timeout)


def stable_id(text, session_id=None, node_id=None):
    """Generate a stable integer ID from content hash."""
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="replace")[:500])
    if session_id is not None:
        h.update(str(session_id).encode())
    if node_id is not None:
        h.update(str(node_id).encode())
    return int.from_bytes(h.digest()[:8], "big") % (2**62)


def export_mysql_messages(batch_size=256, resume=False):
    """Export all messages from Chat_History.messages to Qdrant."""
    conn = mysql.connector.connect(user="root", database="Chat_History")
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) as cnt FROM messages WHERE content IS NOT NULL AND LENGTH(content) > 10")
    total = cur.fetchone()["cnt"]
    print(f"\n{'='*60}")
    print(f"Exporting {total} MySQL messages to Qdrant...")
    print(f"{'='*60}")

    # Get already-embedded IDs if resuming
    embedded_ids = set()
    if resume:
        try:
            info = qdrant_get(f"/collections/{COLLECTION}")
            existing = info.get("result", {}).get("points_count", 0)
            if existing > 0:
                print(f"Resume mode: checking {existing} existing points...")
                # Scroll through existing points to get IDs
                offset = None
                while True:
                    scroll_payload = {"limit": 256, "with_payload": False, "with_vector": False}
                    if offset:
                        scroll_payload["offset"] = offset
                    try:
                        result = qdrant_post(f"/collections/{COLLECTION}/points/scroll", scroll_payload)
                        points = result.get("result", {}).get("points", [])
                        for p in points:
                            embedded_ids.add(p["id"])
                        offset = result.get("result", {}).get("next_page_offset")
                        if not offset:
                            break
                    except Exception as e:
                        logger.error(f"Error scrolling existing points: {e}")
                        break
                print(f"  Already embedded: {len(embedded_ids)} messages")
        except Exception as e:
            logger.error(f"Error fetching existing points for resume: {e}")

    # Process in batches
    cur.execute("""
        SELECT row_id, session_id, node_id, role, content, created_at
        FROM messages
        WHERE content IS NOT NULL AND LENGTH(content) > 10
        ORDER BY row_id
    """)

    batch = []
    exported = 0
    skipped = 0
    start_time = time.time()

    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break

        texts = []
        metadata = []
        for row in rows:
            content = row["content"][:8000]  # truncate very long messages
            text = f"[{row['role']}] {content}"
            point_id = stable_id(text, row["session_id"], row["node_id"])

            if resume and point_id in embedded_ids:
                skipped += 1
                continue

            texts.append(text)
            metadata.append({
                "id": point_id,
                "source": "mysql",
                "row_id": row["row_id"],
                "session_id": row["session_id"],
                "node_id": row["node_id"],
                "role": row["role"],
                "created_at": row["created_at"],
                "content_preview": content[:200],
            })

        if not texts:
            continue

        vectors = embed_texts(texts)

        points = []
        for i, (vec, meta) in enumerate(zip(vectors, metadata)):
            points.append({
                "id": meta["id"],
                "vector": vec,
                "payload": meta,
            })

        upsert_points(points)
        exported += len(points)

        elapsed = time.time() - start_time
        rate = exported / elapsed if elapsed > 0 else 0
        eta = (total - exported - skipped) / rate if rate > 0 else 0
        print(f"  [{exported+skipped}/{total}] exported={exported} skipped={skipped} "
              f"rate={rate:.0f}/s eta={eta:.0f}s")

    conn.close()
    print(f"\nMySQL export done: {exported} embedded, {skipped} skipped")
    return exported


def parse_history_file(filepath):
    """Parse a Devin CLI history .md file into messages."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    messages = []
    # Pattern: === MESSAGE N - Role ===
    pattern = re.compile(r"^=== MESSAGE (\d+) - (\w+) ===$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        # Try alternate patterns
        pattern2 = re.compile(r"^## (User|Assistant|System)\s*$", re.MULTILINE)
        matches2 = list(pattern2.finditer(content))
        if matches2:
            for i, m in enumerate(matches2):
                start = m.end()
                end = matches2[i + 1].start() if i + 1 < len(matches2) else len(content)
                role = m.group(1).lower()
                text = content[start:end].strip()
                if text:
                    messages.append({"node_id": i, "role": role, "content": text})
        return messages

    for i, m in enumerate(matches):
        node_id = int(m.group(1))
        role = m.group(2).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[start:end].strip()
        if text and len(text) > 10:
            messages.append({"node_id": node_id, "role": role, "content": text})

    return messages


def export_disk_history(resume=False):
    """Export all history .md files from disk to Qdrant."""
    files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("history_") and f.endswith(".md")])
    print(f"\n{'='*60}")
    print(f"Exporting {len(files)} disk history files to Qdrant...")
    print(f"{'='*60}")

    # Get already-embedded IDs if resuming
    embedded_ids = set()
    if resume:
        try:
            info = qdrant_get(f"/collections/{COLLECTION}")
            existing = info.get("result", {}).get("points_count", 0)
            if existing > 0:
                offset = None
                while True:
                    scroll_payload = {"limit": 256, "with_payload": False, "with_vector": False}
                    if offset:
                        scroll_payload["offset"] = offset
                    try:
                        result = qdrant_post(f"/collections/{COLLECTION}/points/scroll", scroll_payload)
                        points = result.get("result", {}).get("points", [])
                        for p in points:
                            embedded_ids.add(p["id"])
                        offset = result.get("result", {}).get("next_page_offset")
                        if not offset:
                            break
                    except Exception as e:
                        logger.error(f"Error scrolling existing points: {e}")
                        break
                print(f"  Resume: {len(embedded_ids)} already embedded")
        except Exception as e:
            logger.error(f"Error fetching existing points for resume: {e}")

    total_exported = 0
    total_messages = 0
    total_skipped = 0

    for fi, filename in enumerate(files):
        filepath = os.path.join(HISTORY_DIR, filename)
        messages = parse_history_file(filepath)

        if not messages:
            print(f"  [{fi+1}/{len(files)}] {filename}: no messages parsed")
            continue

        total_messages += len(messages)
        session_id = hashlib.md5(filename.encode()).hexdigest()[:8]

        texts = []
        metadata = []
        for msg in messages:
            content = msg["content"][:8000]
            text = f"[{msg['role']}] {content}"
            point_id = stable_id(text, session_id, msg["node_id"])

            if resume and point_id in embedded_ids:
                total_skipped += 1
                continue

            texts.append(text)
            metadata.append({
                "id": point_id,
                "source": "disk",
                "filename": filename,
                "session_id": session_id,
                "node_id": msg["node_id"],
                "role": msg["role"],
                "content_preview": content[:200],
            })

        if not texts:
            continue

        # Embed in sub-batches of 64
        all_vectors = []
        for j in range(0, len(texts), 64):
            batch_texts = texts[j:j+64]
            vectors = embed_texts(batch_texts)
            all_vectors.extend(vectors)

        points = []
        for vec, meta in zip(all_vectors, metadata):
            points.append({
                "id": meta["id"],
                "vector": vec,
                "payload": meta,
            })

        upsert_points(points)
        total_exported += len(points)
        print(f"  [{fi+1}/{len(files)}] {filename}: {len(messages)} msgs, "
              f"exported={len(points)}, skipped={len(messages)-len(points)}")

    print(f"\nDisk export done: {total_exported} embedded, {total_skipped} skipped, "
          f"{total_messages} total messages in {len(files)} files")
    return total_exported


def main():
    parser = argparse.ArgumentParser(description="Export chat history → Qdrant embeddings")
    parser.add_argument("--mysql-only", action="store_true", help="Only export MySQL messages")
    parser.add_argument("--disk-only", action="store_true", help="Only export disk history files")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size for MySQL export")
    parser.add_argument("--resume", action="store_true", help="Skip already-embedded messages")
    parser.add_argument("--history-dir", type=str, default=None, help="Directory containing history_*.md files (default: $DEVIN_SUMMARIES_DIR or ~/.local/share/devin/cli/summaries)")
    args = parser.parse_args()

    global HISTORY_DIR
    if args.history_dir:
        HISTORY_DIR = args.history_dir

    do_mysql = not args.disk_only
    do_disk = not args.mysql_only

    print(f"Chat History → Qdrant Embeddings Export")
    print(f"  Collection: {COLLECTION}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  MySQL: {'yes' if do_mysql else 'no'}")
    print(f"  Disk:  {'yes' if do_disk else 'no'}")
    print(f"  Resume: {args.resume}")
    print(f"  Batch size: {args.batch_size}")

    # Ensure Qdrant collection exists
    existing = ensure_collection()

    total = 0
    if do_mysql:
        total += export_mysql_messages(batch_size=args.batch_size, resume=args.resume)
    if do_disk:
        total += export_disk_history(resume=args.resume)

    # Final stats
    info = qdrant_get(f"/collections/{COLLECTION}")
    final_count = info.get("result", {}).get("points_count", 0)
    print(f"\n{'='*60}")
    print(f"EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Total embedded this run: {total}")
    print(f"  Collection '{COLLECTION}' now has: {final_count} points")
    print(f"  Vector dimension: 384 (BGE-small)")
    print(f"  Distance: Cosine")


if __name__ == "__main__":
    main()
