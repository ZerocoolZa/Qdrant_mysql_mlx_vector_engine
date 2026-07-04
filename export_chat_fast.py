#!/usr/bin/env python3
"""
export_chat_fast.py — Fast chat history → Qdrant embeddings.

Uses a MySQL temp table to track progress instead of scrolling Qdrant.
Embeds in batches of 512 with no resume-scan overhead.

Sources:
  1. Chat_History MySQL messages (141K rows)
  2. Devin CLI session transcripts on disk (82 .md files)

Target: Qdrant collection "chat_history" (384-dim BGE)
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

import mysql.connector

QDRANT_URL = "http://localhost:6333"
COLLECTION = "chat_history"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
HISTORY_DIR = "/Users/wws/.local/share/devin/cli/summaries"

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


def qdrant_put(path, payload, timeout=120):
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ensure_collection():
    try:
        info = qdrant_get(f"/collections/{COLLECTION}")
        count = info.get("result", {}).get("points_count", 0)
        print(f"Collection '{COLLECTION}' exists: {count} points")
        return count
    except urllib.error.HTTPError:
        pass
    print(f"Creating collection '{COLLECTION}' (384-dim, cosine)...")
    qdrant_put(f"/collections/{COLLECTION}", {
        "vectors": {"size": 384, "distance": "Cosine"},
        "optimizers_config": {"default_segment_number": 4}
    })
    print("Collection created.")
    return 0


def embed_texts(texts):
    model = get_model()
    # BGE-small is fast with batch_size=32, slow with 64+
    vectors = model.encode(texts, show_progress_bar=False, batch_size=32)
    return [v.tolist() for v in vectors]


def upsert_points(points):
    qdrant_put(f"/collections/{COLLECTION}/points?wait=true", {"points": points})


def stable_id(text, sid=None, nid=None):
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="replace")[:500])
    if sid: h.update(str(sid).encode())
    if nid: h.update(str(nid).encode())
    return int.from_bytes(h.digest()[:8], "big") % (2**62)


def export_mysql_fast(batch_size=512):
    """Export MySQL messages using a progress table — no Qdrant scroll."""
    conn = mysql.connector.connect(user="root", database="Chat_History")
    cur = conn.cursor(dictionary=True)

    # Create progress tracking table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _embed_progress (
            row_id BIGINT PRIMARY KEY,
            point_id BIGINT NOT NULL,
            embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    conn.commit()

    # Get total
    cur.execute("SELECT COUNT(*) as cnt FROM messages WHERE content IS NOT NULL AND LENGTH(content) > 10")
    total = cur.fetchone()["cnt"]

    # Get already done
    cur.execute("SELECT COUNT(*) as cnt FROM _embed_progress")
    done = cur.fetchone()["cnt"]
    remaining = total - done

    print(f"\n{'='*60}")
    print(f"MySQL Messages → Qdrant")
    print(f"  Total: {total}")
    print(f"  Already embedded: {done}")
    print(f"  Remaining: {remaining}")
    print(f"  Batch size: {batch_size}")
    print(f"{'='*60}")

    if remaining == 0:
        print("Nothing to do.")
        conn.close()
        return 0

    # Use NOT IN subquery — fast with index on _embed_progress.row_id
    # Process in chunks using row_id ranges to avoid huge result sets
    cur.execute("SELECT MIN(row_id) as min_id, MAX(row_id) as max_id FROM messages WHERE content IS NOT NULL AND LENGTH(content) > 10")
    id_range = cur.fetchone()
    min_id = id_range["min_id"] or 0
    max_id = id_range["max_id"] or 0

    exported = 0
    start_time = time.time()
    current_id = min_id

    while current_id <= max_id:
        # Fetch next batch by row_id range — fast, uses primary key
        # Skip NOT IN check if progress table is small (first run)
        if done < 1000:
            cur.execute(f"""
                SELECT m.row_id, m.session_id, m.node_id, m.role, m.content, m.created_at
                FROM messages m
                WHERE m.row_id >= %s
                  AND m.content IS NOT NULL AND LENGTH(m.content) > 10
                ORDER BY m.row_id
                LIMIT %s
            """, (current_id, batch_size))
        else:
            cur.execute(f"""
                SELECT m.row_id, m.session_id, m.node_id, m.role, m.content, m.created_at
                FROM messages m
                WHERE m.row_id >= %s
                  AND m.content IS NOT NULL AND LENGTH(m.content) > 10
                  AND m.row_id NOT IN (SELECT row_id FROM _embed_progress)
                ORDER BY m.row_id
                LIMIT %s
            """, (current_id, batch_size))
        rows = cur.fetchall()

        if not rows:
            current_id += batch_size
            continue

        texts = []
        metadata = []
        row_ids = []

        for row in rows:
            content = row["content"][:8000]
            text = f"[{row['role']}] {content}"
            pid = stable_id(text, row["session_id"], row["node_id"])
            texts.append(text)
            row_ids.append(row["row_id"])
            metadata.append({
                "id": pid,
                "source": "mysql",
                "row_id": row["row_id"],
                "session_id": row["session_id"],
                "node_id": row["node_id"],
                "role": row["role"],
                "created_at": row["created_at"],
                "content_preview": content[:200],
            })

        # Embed
        vectors = embed_texts(texts)

        # Build points
        points = [{"id": m["id"], "vector": v, "payload": m} for m, v in zip(metadata, vectors)]

        # Upsert to Qdrant
        upsert_points(points)

        # Mark as done in MySQL
        for rid, m in zip(row_ids, metadata):
            cur.execute("INSERT IGNORE INTO _embed_progress (row_id, point_id) VALUES (%s, %s)", (rid, m["id"]))
        conn.commit()

        exported += len(points)
        current_id = rows[-1]["row_id"] + 1
        elapsed = time.time() - start_time
        rate = exported / elapsed if elapsed > 0 else 0
        eta = (remaining - exported) / rate if rate > 0 else 0
        print(f"  [{done+exported}/{total}] batch={len(points)} rate={rate:.0f}/s eta={eta:.0f}s")

    conn.close()
    print(f"\nMySQL done: {exported} new embeddings (total now: {done+exported})")
    return exported


def parse_history_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    messages = []
    pattern = re.compile(r"^=== MESSAGE (\d+) - (\w+) ===$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        pattern2 = re.compile(r"^## (User|Assistant|System)\s*$", re.MULTILINE)
        matches2 = list(pattern2.finditer(content))
        for i, m in enumerate(matches2):
            start = m.end()
            end = matches2[i + 1].start() if i + 1 < len(matches2) else len(content)
            role = m.group(1).lower()
            text = content[start:end].strip()
            if text and len(text) > 10:
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


def export_disk_fast():
    """Export disk history files to Qdrant."""
    conn = mysql.connector.connect(user="root", database="Chat_History")
    cur = conn.cursor(dictionary=True)

    # Track disk files too
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _embed_disk_progress (
            file_hash VARCHAR(64) PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            msg_count INT NOT NULL,
            embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    conn.commit()

    files = sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("history_") and f.endswith(".md")])

    # Filter out already-done files
    cur.execute("SELECT filename FROM _embed_disk_progress")
    done_files = set(r["filename"] for r in cur.fetchall())
    todo = [f for f in files if f not in done_files]

    print(f"\n{'='*60}")
    print(f"Disk History Files → Qdrant")
    print(f"  Total files: {len(files)}")
    print(f"  Already done: {len(done_files)}")
    print(f"  To process: {len(todo)}")
    print(f"{'='*60}")

    if not todo:
        print("Nothing to do.")
        conn.close()
        return 0

    total_exported = 0

    for fi, filename in enumerate(todo):
        filepath = os.path.join(HISTORY_DIR, filename)
        messages = parse_history_file(filepath)

        if not messages:
            file_hash = hashlib.md5(filepath.encode()).hexdigest()
            cur.execute("INSERT IGNORE INTO _embed_disk_progress (file_hash, filename, msg_count) VALUES (%s, %s, 0)",
                       (file_hash, filename))
            conn.commit()
            print(f"  [{fi+1}/{len(todo)}] {filename}: no messages")
            continue

        session_id = hashlib.md5(filename.encode()).hexdigest()[:8]
        texts = []
        metadata = []

        for msg in messages:
            content = msg["content"][:8000]
            text = f"[{msg['role']}] {content}"
            pid = stable_id(text, session_id, msg["node_id"])
            texts.append(text)
            metadata.append({
                "id": pid,
                "source": "disk",
                "filename": filename,
                "session_id": session_id,
                "node_id": msg["node_id"],
                "role": msg["role"],
                "content_preview": content[:200],
            })

        # Embed in sub-batches of 128
        all_vectors = []
        for j in range(0, len(texts), 128):
            all_vectors.extend(embed_texts(texts[j:j+128]))

        points = [{"id": m["id"], "vector": v, "payload": m} for m, v in zip(metadata, all_vectors)]
        upsert_points(points)
        total_exported += len(points)

        file_hash = hashlib.md5(filepath.encode()).hexdigest()
        cur.execute("INSERT IGNORE INTO _embed_disk_progress (file_hash, filename, msg_count) VALUES (%s, %s, %s)",
                   (file_hash, filename, len(messages)))
        conn.commit()

        print(f"  [{fi+1}/{len(todo)}] {filename}: {len(messages)} msgs embedded")

    conn.close()
    print(f"\nDisk done: {total_exported} embeddings from {len(todo)} files")
    return total_exported


def main():
    print("Chat History → Qdrant Embeddings (Fast Mode)")
    print(f"  Collection: {COLLECTION}")
    print(f"  Model: {MODEL_NAME}")

    ensure_collection()

    mysql_count = export_mysql_fast(batch_size=32)
    disk_count = export_disk_fast()

    info = qdrant_get(f"/collections/{COLLECTION}")
    final = info.get("result", {}).get("points_count", 0)
    print(f"\n{'='*60}")
    print(f"EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  MySQL messages embedded: {mysql_count}")
    print(f"  Disk messages embedded:  {disk_count}")
    print(f"  Collection '{COLLECTION}': {final} total points")
    print(f"  Vector dim: 384 (BGE-small), Distance: Cosine")


if __name__ == "__main__":
    main()
