#!/usr/bin/env python3
"""Import chat files from vbstyle_documents.markdown_files into Chat_History.

Parses markdown chat files that contain '### User Input' and '### Planner Response'
sections, splits them into user/assistant messages, and inserts them as sessions
+ messages + prompts into the Chat_History database.

Deduplication: skips files whose title already exists in the sessions table,
so the script is safe to re-run.
"""
import sys
import mysql.connector

conn = mysql.connector.connect(user='root', host='localhost', port=3306)

# Read source rows with a server-side cursor to avoid loading everything at once
cur_read = conn.cursor(dictionary=True, buffered=True)
cur_read.execute('USE vbstyle_documents')
cur_read.execute("""
    SELECT id, file_name, content
    FROM markdown_files
    WHERE content LIKE '%%### User Input%%'
      AND content LIKE '%%### Planner Response%%'
""")
print('Query started, fetching results...')

# Use regular cursor for inserts
cur = conn.cursor()
cur.execute('USE Chat_History')

# Build a set of already-imported titles for deduplication
cur.execute("SELECT title FROM sessions WHERE model = 'unknown'")
existing_titles = {row[0] for row in cur.fetchall()}
print(f'Already imported: {len(existing_titles)} sessions')

USER_PATTERNS = ['### User Input', '## User', '### User', '### Human']
ASSISTANT_PATTERNS = ['### Planner Response', '## Assistant', '### Assistant', '### AI']

def parse_messages(content):
    lines = content.split('\n')
    messages = []
    current_role = None
    current_content = []
    for line in lines:
        stripped = line.strip()
        is_user = any(stripped.startswith(p) for p in USER_PATTERNS)
        is_assistant = any(stripped.startswith(p) for p in ASSISTANT_PATTERNS)
        if is_user:
            if current_role and current_content:
                text = '\n'.join(current_content).strip()
                if text:
                    messages.append((current_role, text))
            current_role = 'user'
            current_content = []
        elif is_assistant:
            if current_role and current_content:
                text = '\n'.join(current_content).strip()
                if text:
                    messages.append((current_role, text))
            current_role = 'assistant'
            current_content = []
        else:
            if current_role:
                current_content.append(line)
    if current_role and current_content:
        text = '\n'.join(current_content).strip()
        if text:
            messages.append((current_role, text))
    return messages

total_sessions = 0
total_messages = 0
total_prompts = 0
skipped = 0
deduped = 0

rows = cur_read.fetchall()
cur_read.close()
print(f'Found {len(rows)} chat files matching pattern')

BATCH_SIZE = 50
batch_count = 0

for row in rows:
    fname = row['file_name']
    content = row['content']

    # Deduplication: skip if a session with this title already exists
    if fname in existing_titles:
        deduped += 1
        continue

    if not content:
        skipped += 1
        continue
    # Clean content of null bytes that break SQL
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='ignore')
    content = content.replace('\x00', '')

    msgs = parse_messages(content)
    if not msgs:
        skipped += 1
        continue

    try:
        cur.execute(
            "INSERT INTO sessions (title, model, created_at) VALUES (%s, %s, %s)",
            (fname, 'unknown', None)
        )
        sid = cur.lastrowid

        for idx, (role, text) in enumerate(msgs):
            try:
                cur.execute(
                    "INSERT INTO messages (session_id, node_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (sid, idx, role, text, None)
                )
                if role == 'user':
                    cur.execute(
                        "INSERT INTO prompts (session_id, content, timestamp) VALUES (%s, %s, %s)",
                        (sid, text[:5000], None)
                    )
                    total_prompts += 1
            except Exception as e:
                print(f'  SKIP msg {idx} in {fname}: {str(e)[:80]}')
                continue

        total_sessions += 1
        total_messages += len(msgs)
        existing_titles.add(fname)
        batch_count += 1

        # Commit in batches to avoid one giant transaction
        if batch_count % BATCH_SIZE == 0:
            conn.commit()
            print(f'  Progress: {total_sessions} imported, {deduped} deduped, {skipped} skipped')
    except Exception as e:
        print(f'  SKIP file {fname}: {str(e)[:80]}')
        conn.rollback()
        skipped += 1
        continue

conn.commit()

cur.execute('SELECT COUNT(*) FROM sessions')
print(f'Total sessions in DB: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM messages')
print(f'Total messages in DB: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM prompts')
print(f'Total prompts in DB: {cur.fetchone()[0]}')
print(f'Imported this run: {total_sessions} sessions, {total_messages} messages, {total_prompts} prompts')
print(f'Skipped: {skipped}, Deduped (already existed): {deduped}')
cur.close()
conn.close()
