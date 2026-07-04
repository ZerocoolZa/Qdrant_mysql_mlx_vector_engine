# =============================================================================
# File: import_codex_chat.py
# Created: June 23, 2026
# Reason: User had 3 Codex backup folders (.codex.backup.*) taking up 2 GB.
#         Chat history inside them needed to be preserved before deletion.
# Idea: Parse Codex .jsonl session files, extract user/assistant messages,
#       dedup by (timestamp, role, first 200 chars), insert into MySQL
#       codex_chat_history.chat table in chronological order.
#       Simple schema: id (auto), turn (user/assistant), message (text).
#       After import, backups were safe to delete.
# =============================================================================

import json
import os
import glob
import mysql.connector

BACKUPS = [
    "/Users/wws/.codex.backup.20260416_101328/sessions",
    "/Users/wws/.codex.backup.deepmerge.20260416_101843/sessions",
    "/Users/wws/.codex.backup.deepmerge.20260416_101911/sessions",
]

def extract_messages(jsonl_path):
    msgs = []
    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp", "")
            typ = obj.get("type", "")
            payload = obj.get("payload", {})

            if typ == "response_item":
                role = payload.get("role", "")
                if role not in ("user", "assistant"):
                    continue
                content_parts = payload.get("content", [])
                text = ""
                for part in content_parts:
                    if isinstance(part, dict):
                        text += part.get("text", "")
                if text.strip():
                    msgs.append((ts, role, text.strip()))

            elif typ == "event_msg":
                evt_type = payload.get("type", "")
                if evt_type == "user_message":
                    text = payload.get("message", "")
                    if text.strip():
                        msgs.append((ts, "user", text.strip()))

    return msgs

def main():
    all_files = []
    for backup in BACKUPS:
        if not os.path.isdir(backup):
            continue
        for f in glob.glob(os.path.join(backup, "**/*.jsonl"), recursive=True):
            all_files.append(f)

    all_files.sort()

    print(f"Found {len(all_files)} session files")

    conn = mysql.connector.connect(host="localhost", user="root", database="codex_chat_history")
    cur = conn.cursor()

    cur.execute("TRUNCATE TABLE chat")
    conn.commit()

    total = 0
    seen = set()

    for fpath in all_files:
        msgs = extract_messages(fpath)
        for ts, role, text in msgs:
            key = (ts, role, text[:200])
            if key in seen:
                continue
            seen.add(key)
            cur.execute(
                "INSERT INTO chat (turn, message) VALUES (%s, %s)",
                (role, text)
            )
            total += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Imported {total} messages into codex_chat_history.chat")

if __name__ == "__main__":
    main()
