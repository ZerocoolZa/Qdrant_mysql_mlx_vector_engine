#!/usr/bin/env python3

#[@GHOST]{[@file<Extract_user_questions.py>][@state<active>][@date<2026-06-22>][@ver<1.0>][@auth<Devin>]}
#[@VBSTYLE]{[@auth<system>][@role<extractor>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}

"""
Extract and classify all user questions from MySQL vb_shared chat tables
into a structured SQLite table for autocomplete training.

Sources:
  - vb_shared.chat_ingestions (content column, split by ### User Input)
  - vb_shared.json_ingestions (content column, ChatGPT JSON mapping)
  - vb_shared.graph_conversations (user_msg column)

Output:
  - autocomplete.db table user_questions (question, style_mode, source, original_text, created_at)

Uses DetectStyleMode and _tokenize from Engine_smart_search.py.
"""

import os
import re
import sys
import json
import sqlite3
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Config_smart_system import (
    DB_USER_ROOT,
    DB_NAME_VB_SHARED,
    DB_HOST_LOCALHOST,
    DB_CHARSET_UTF8MB4,
    MYSQL_AUTOCOMMIT,
)
from Engine_smart_search import DetectStyleMode, _tokenize
import mysql.connector as _mysql

# --- UPPERCASE CONSTANTS ------------------------------------------------------

TABLE_USER_QUESTIONS = 'user_questions'
SOURCE_CHAT_INGESTIONS = 'chat_ingestions'
SOURCE_JSON_INGESTIONS = 'json_ingestions'
SOURCE_GRAPH_CONVERSATIONS = 'graph_conversations'

MARKER_USER_INPUT = '### User Input'
MARKER_SECTION = '### '

QUESTION_WORDS = (
    'how', 'what', 'why', 'when', 'where', 'who',
    'can', 'could', 'would', 'should',
    'is', 'are', 'do', 'does',
    'what about', 'what if',
)

FILLER_WORDS = ('like', 'um', 'uh', 'you know', 'so', 'well', 'hmm', 'huh')

BATCH_SIZE = 500

SQL_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_USER_QUESTIONS} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,
    style_mode TEXT,
    source TEXT,
    original_text TEXT,
    created_at TEXT
)
"""

SQL_INSERT_QUESTION = f"""
INSERT OR IGNORE INTO {TABLE_USER_QUESTIONS}
    (question, style_mode, source, original_text, created_at)
VALUES (?, ?, ?, ?, ?)
"""

SQL_COUNT_QUESTIONS = f"SELECT COUNT(*) FROM {TABLE_USER_QUESTIONS}"
SQL_COUNT_DISTINCT = f"SELECT COUNT(DISTINCT question) FROM {TABLE_USER_QUESTIONS}"

MYSQL_CFG = dict(
    user=DB_USER_ROOT,
    database=DB_NAME_VB_SHARED,
    host=DB_HOST_LOCALHOST,
    charset=DB_CHARSET_UTF8MB4,
    autocommit=MYSQL_AUTOCOMMIT,
)

AC_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'autocomplete.db')


# --- Helpers ------------------------------------------------------------------

# Patterns to strip from user messages before extracting questions
RE_ACTION_MARKER = re.compile(r'\*[^*]{2,}\*')  # *Updated todo list*, *Edited file*, etc.
RE_USER_ACCEPTED = re.compile(r'User accepted the command[^*]*', re.IGNORECASE)
RE_CODE_BLOCK = re.compile(r'```[^`]*```', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`[^`]+`')
RE_FILE_REF = re.compile(r'@\[[^\]]+\]')
RE_URL = re.compile(r'https?://\S+')
RE_MARKDOWN_BOLD = re.compile(r'\*\*([^*]+)\*\*')
RE_TODO_MARKER = re.compile(r'(Updated todo list|Edited relevant file|Created file|Deleted file)', re.IGNORECASE)
RE_MULTI_PUNCT = re.compile(r'([!?])\1{2,}')  # ??? -> ?, !!! -> !
RE_LEADING_NOISE = re.compile(r'^[?.,!;:\s]+')

# Max question length — skip monologues
MAX_QUESTION_LEN = 200
MIN_QUESTION_LEN = 8


def _strip_noise(text):
    """Strip action markers, code blocks, file refs, URLs, and other non-question noise."""
    if not text:
        return ""
    # Remove code blocks first (they may contain * inside)
    text = RE_CODE_BLOCK.sub('', text)
    # Remove inline code
    text = RE_INLINE_CODE.sub('', text)
    # Remove action markers: *Updated todo list*, *Edited relevant file*, etc.
    text = RE_ACTION_MARKER.sub('', text)
    # Remove "User accepted the command ..." remnants
    text = RE_USER_ACCEPTED.sub('', text)
    # Remove file references like @[path:L1-L2]
    text = RE_FILE_REF.sub('', text)
    # Remove URLs
    text = RE_URL.sub('', text)
    # Remove markdown bold markers but keep text
    text = RE_MARKDOWN_BOLD.sub(r'\1', text)
    # Remove standalone todo/file action words
    text = RE_TODO_MARKER.sub('', text)
    # Collapse multiple punctuation (??? -> ?, !!! -> !)
    text = RE_MULTI_PUNCT.sub(r'\1', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _split_sentences(text):
    """Split text into sentences by . ! ? boundaries, keeping the punctuation."""
    if not text:
        return []
    # Split on sentence-ending punctuation, keeping the delimiter
    raw = re.split(r'([.!?]+)', text)
    sentences = []
    for i in range(0, len(raw) - 1, 2):
        sentence = (raw[i] + raw[i + 1]).strip()
        if sentence:
            sentences.append(sentence)
    # Catch trailing text without punctuation
    if len(raw) % 2 == 1 and raw[-1].strip():
        sentences.append(raw[-1].strip())
    return sentences


def _is_question(text):
    """Check if text is a question: ends with ? or starts with a question word."""
    if not text or not text.strip():
        return False
    stripped = text.strip().lower()
    if stripped.endswith('?'):
        return True
    for word in QUESTION_WORDS:
        if stripped.startswith(word + ' ') or stripped.startswith(word + '\t'):
            return True
    return False


def _clean_question(text):
    """Clean a single question sentence: strip filler words, normalize punctuation."""
    if not text:
        return ""
    cleaned = text.strip()
    # Remove filler words (word-boundary, case-insensitive)
    for filler in FILLER_WORDS:
        cleaned = re.sub(r'\b' + re.escape(filler) + r'\b', '', cleaned, flags=re.IGNORECASE)
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Strip leading punctuation noise
    cleaned = RE_LEADING_NOISE.sub('', cleaned)
    # Ensure ends with ?
    if cleaned and not cleaned.endswith('?') and not cleaned.endswith('.'):
        cleaned = cleaned + '?'
    return cleaned


def _extract_questions_from_message(text):
    """Extract individual clean questions from a user message.
    Strips noise, splits into sentences, keeps only question sentences.
    Returns list of clean question strings."""
    if not text or not text.strip():
        return []
    # Strip noise first
    clean_text = _strip_noise(text)
    if not clean_text:
        return []
    # Split into sentences
    sentences = _split_sentences(clean_text)
    questions = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < MIN_QUESTION_LEN:
            continue
        # MUST end with ? — question words alone aren't enough (too many false positives)
        if not sentence.endswith('?'):
            continue
        # Skip if it's just punctuation/numbers/symbols
        alpha_count = sum(1 for c in sentence if c.isalpha())
        if alpha_count < 5:
            continue
        # Skip "Message about ??" and similar fragments
        lower = sentence.lower()
        if lower.startswith('message about'):
            continue
        # Skip pure token references like [@XXXXXX]?
        if re.match(r'^[@\[\]X\s?]+$', sentence):
            continue
        if len(sentence) > MAX_QUESTION_LEN:
            continue
        cleaned = _clean_question(sentence)
        if cleaned and len(cleaned) >= MIN_QUESTION_LEN:
            # Final check: cleaned version must end with ?
            if not cleaned.endswith('?'):
                continue
            questions.append(cleaned)
    return questions


def _split_chat_blocks(content):
    """Split chat_ingestions content by ### User Input markers.
    Returns list of user message strings (text between marker and next ### section)."""
    if not content:
        return []
    blocks = []
    parts = content.split(MARKER_USER_INPUT)
    # First part is preamble (before any user input) — skip
    for part in parts[1:]:
        # Cut at next ### section marker
        next_section = part.find(MARKER_SECTION)
        if next_section >= 0:
            user_text = part[:next_section]
        else:
            user_text = part
        user_text = user_text.strip()
        if user_text:
            # Strip "Input" prefix if present
            if user_text.startswith('Input'):
                user_text = user_text[5:].strip()
            blocks.append(user_text)
    return blocks


def _extract_json_user_messages(content):
    """Parse ChatGPT JSON, walk mapping nodes, extract user messages.
    Returns list of text strings from messages where author.role == 'user'."""
    if not content:
        return []
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []

    messages = []
    # data can be a list of conversations or a single conversation
    conversations = data if isinstance(data, list) else [data]
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get('mapping', {})
        if not isinstance(mapping, dict):
            continue
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            msg = node.get('message')
            if not isinstance(msg, dict):
                continue
            author = msg.get('author', {})
            if not isinstance(author, dict):
                continue
            if author.get('role') != 'user':
                continue
            content_obj = msg.get('content', {})
            if not isinstance(content_obj, dict):
                continue
            parts = content_obj.get('parts', [])
            if not isinstance(parts, list):
                continue
            text_parts = []
            for p in parts:
                if isinstance(p, str):
                    text_parts.append(p)
            full_text = ' '.join(text_parts).strip()
            if full_text:
                messages.append(full_text)
    return messages


# --- Main class ---------------------------------------------------------------

class UserQuestionExtractor:
    """Extract and classify user questions from MySQL chat tables into SQLite."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": dict(MYSQL_CFG),
            "ac_db_path": AC_DB_PATH,
            "stats": {
                "scanned": 0,
                "questions_found": 0,
                "skipped_not_question": 0,
                "skipped_duplicate": 0,
                "skipped_empty": 0,
                "by_source": Counter(),
                "by_style": Counter(),
            },
            "seen_questions": set(),
            "memunit": mem,
            "db_manager": db,
        }
        if param and isinstance(param, dict):
            self.state["config"].update(param)

    def Run(self, command, params=None):
        if command == 'extract':
            return self.Extract(params)
        elif command == 'read_state':
            return self.ReadState()
        elif command == 'set_config':
            return self.SetConfig(params)
        else:
            return (0, None, ('UNKNOWN_COMMAND', f'Unknown: {command}', 0))

    def ReadState(self):
        return (1, dict(self.state), None)

    def SetConfig(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ('MISSING_PARAM', 'config dict required', 0))
        self.state["config"].update(params)
        return (1, {'updated': True}, None)

    def MysqlConn(self):
        return _mysql.connect(**self.state["config"])

    def InitSqlite(self):
        """Create the autocomplete.db and user_questions table if not exists."""
        conn = sqlite3.connect(self.state["ac_db_path"])
        cur = conn.cursor()
        cur.execute(SQL_CREATE_TABLE)
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_question ON user_questions(question)')
        conn.commit()
        return conn

    def Extract(self, params=None):
        """Main extraction: scan all 3 sources, classify, insert into SQLite."""
        stats = self.state["stats"]
        sqlite_conn = None
        try:
            sqlite_conn = self.InitSqlite()
            # Load existing questions to skip duplicates
            cur = sqlite_conn.cursor()
            cur.execute(f'SELECT question FROM {TABLE_USER_QUESTIONS}')
            for row in cur.fetchall():
                self.state["seen_questions"].add(row[0])

            mysql_conn = self.MysqlConn()
            mysql_cur = mysql_conn.cursor()

            # Source 1: chat_ingestions
            mysql_cur.execute('SELECT content FROM chat_ingestions WHERE content IS NOT NULL AND content != ""')
            batch = []
            for (content,) in mysql_cur.fetchall():
                for user_msg in _split_chat_blocks(content):
                    stats["scanned"] += 1
                    results = self._classify_and_prepare(user_msg, SOURCE_CHAT_INGESTIONS)
                    for result in results:
                        batch.append(result)
                        if len(batch) >= BATCH_SIZE:
                            self._insert_batch(sqlite_conn, batch)
                            batch = []
            self._insert_batch(sqlite_conn, batch)
            batch = []

            # Source 2: json_ingestions
            mysql_cur.execute('SELECT content FROM json_ingestions WHERE content IS NOT NULL AND content != ""')
            for (content,) in mysql_cur.fetchall():
                for user_msg in _extract_json_user_messages(content):
                    stats["scanned"] += 1
                    results = self._classify_and_prepare(user_msg, SOURCE_JSON_INGESTIONS)
                    for result in results:
                        batch.append(result)
                        if len(batch) >= BATCH_SIZE:
                            self._insert_batch(sqlite_conn, batch)
                            batch = []
            self._insert_batch(sqlite_conn, batch)
            batch = []

            # Source 3: graph_conversations
            mysql_cur.execute('SELECT user_msg FROM graph_conversations WHERE user_msg IS NOT NULL AND user_msg != ""')
            for (user_msg,) in mysql_cur.fetchall():
                stats["scanned"] += 1
                results = self._classify_and_prepare(user_msg, SOURCE_GRAPH_CONVERSATIONS)
                for result in results:
                    batch.append(result)
                    if len(batch) >= BATCH_SIZE:
                        self._insert_batch(sqlite_conn, batch)
                        batch = []
            self._insert_batch(sqlite_conn, batch)

            mysql_conn.close()
            sqlite_conn.commit()
            sqlite_conn.close()

            summary = self._build_summary()
            sys.stderr.write(summary)
            return (1, summary, None)
        except Exception as ex:
            if sqlite_conn:
                try:
                    sqlite_conn.close()
                except Exception:
                    pass
            return (0, None, ('EXTRACT_ERROR', str(ex), 0))

    def _classify_and_prepare(self, text, source):
        """Classify a user message and extract individual questions.
        Returns list of tuples for insert (can be empty if no questions found).
        Each message can yield multiple questions — splits by sentence."""
        stats = self.state["stats"]
        if not text or not text.strip():
            stats["skipped_empty"] += 1
            return []
        # Extract individual clean questions from the message
        questions = _extract_questions_from_message(text)
        if not questions:
            stats["skipped_not_question"] += 1
            return []
        # Classify style mode on the FULL original message (not just one sentence)
        mode, _scores = DetectStyleMode(text)
        results = []
        created = datetime.now(timezone.utc).isoformat() + 'Z'
        for clean_q in questions:
            if clean_q.lower() in self.state["seen_questions"]:
                stats["skipped_duplicate"] += 1
                continue
            self.state["seen_questions"].add(clean_q.lower())
            stats["questions_found"] += 1
            stats["by_source"][source] += 1
            stats["by_style"][mode] += 1
            results.append((clean_q, mode, source, text[:2000], created))
        return results

    def _insert_batch(self, sqlite_conn, batch):
        """Insert a batch of questions with executemany."""
        if not batch:
            return
        cur = sqlite_conn.cursor()
        cur.executemany(SQL_INSERT_QUESTION, batch)
        sqlite_conn.commit()

    def _build_summary(self):
        """Build a text summary of extraction stats."""
        s = self.state["stats"]
        lines = [
            "\n[Extract_user_questions] Summary",
            "=" * 50,
            f"Total messages scanned:  {s['scanned']}",
            f"Questions found:         {s['questions_found']}",
            f"Skipped (not question):  {s['skipped_not_question']}",
            f"Skipped (duplicate):     {s['skipped_duplicate']}",
            f"Skipped (empty):         {s['skipped_empty']}",
            "",
            "By source:",
        ]
        for source, count in s["by_source"].most_common():
            lines.append(f"  {source:30s} {count}")
        lines.append("")
        lines.append("By style_mode:")
        for mode, count in s["by_style"].most_common():
            lines.append(f"  {mode:30s} {count}")
        lines.append("=" * 50 + "\n")
        return "\n".join(lines)


# --- Entry point --------------------------------------------------------------

def main():
    extractor = UserQuestionExtractor()
    ok, data, err = extractor.Run('extract')
    if not ok:
        sys.stderr.write(f"ERROR: {err}\n")
        sys.exit(1)
    # Final verification
    conn = sqlite3.connect(AC_DB_PATH)
    cur = conn.cursor()
    cur.execute(SQL_COUNT_QUESTIONS)
    total = cur.fetchone()[0]
    cur.execute(f'SELECT question, style_mode FROM {TABLE_USER_QUESTIONS} LIMIT 10')
    sample = cur.fetchall()
    conn.close()
    sys.stderr.write(f"\nVerify: {total} questions in {TABLE_USER_QUESTIONS}\n")
    sys.stderr.write("Sample:\n")
    for q, m in sample:
        sys.stderr.write(f"  [{m:12s}] {q[:80]}\n")


if __name__ == "__main__":
    main()
