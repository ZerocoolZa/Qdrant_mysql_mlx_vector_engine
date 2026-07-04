#!/usr/bin/env python3

#[@GHOST]{[@file<Extract_qa_pairs.py>][@state<active>][@date<2026-06-22>][@ver<1.0>][@auth<Devin>]}
#[@VBSTYLE]{[@auth<system>][@role<extractor>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}

"""
Extract question→answer pairs from MySQL vb_shared chat tables into a
tree-structured SQLite table for autocomplete + future model training.

Sources:
  - vb_shared.chat_ingestions (content column, split by ### User Input / ### Planner Response)
  - vb_shared.json_ingestions (content column, ChatGPT JSON mapping)

Output:
  - autocomplete.db table qa_pairs (question, answer, style_mode, source,
    session_id, parent_question_id, branch_index, question_hash, created_at)

Tree structure:
  - branch_index: multiple answers to the same question (ChatGPT regen or cross-session)
  - parent_question_id: follow-up chain (question references previous via "that/this/it/those")
  - question_hash: MD5 of normalized question, for cross-session dedup

Uses DetectStyleMode from Engine_smart_search.py.
"""

import os
import re
import sys
import json
import sqlite3
import hashlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Config_smart_system import (
    DB_USER_ROOT,
    DB_NAME_VB_SHARED,
    DB_HOST_LOCALHOST,
    DB_CHARSET_UTF8MB4,
    MYSQL_AUTOCOMMIT,
)
from Engine_smart_search import DetectStyleMode
import mysql.connector as _mysql

# --- UPPERCASE CONSTANTS ------------------------------------------------------

TABLE_QA_PAIRS = 'qa_pairs'
SOURCE_CASCADE = 'cascade'
SOURCE_CHATGPT = 'chatgpt'

MARKER_USER_INPUT = '### User Input'
MARKER_PLANNER_RESPONSE = '### Planner Response'
MARKER_SECTION = '### '

QUESTION_MARK = '?'
MIN_ANSWER_LEN = 5
MAX_ANSWER_LEN = 2000
MIN_QUESTION_LEN = 5

FOLLOWUP_WORDS = ('that', 'this', 'it', 'those', 'these', 'them', 'the above', 'the previous')

SQL_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_QA_PAIRS} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT,
    style_mode TEXT DEFAULT 'neutral',
    source TEXT,
    session_id TEXT,
    parent_question_id INTEGER,
    branch_index INTEGER DEFAULT 1,
    question_hash TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_question_id) REFERENCES {TABLE_QA_PAIRS}(id)
)
"""

SQL_INSERT_PAIR = f"""
INSERT INTO {TABLE_QA_PAIRS}
    (question, answer, style_mode, source, session_id, parent_question_id, branch_index, question_hash, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_INDEX_HASH = f"CREATE INDEX IF NOT EXISTS idx_qa_question_hash ON {TABLE_QA_PAIRS}(question_hash)"
SQL_INDEX_STYLE = f"CREATE INDEX IF NOT EXISTS idx_qa_style_mode ON {TABLE_QA_PAIRS}(style_mode)"

MYSQL_CFG = dict(
    user=DB_USER_ROOT,
    database=DB_NAME_VB_SHARED,
    host=DB_HOST_LOCALHOST,
    charset=DB_CHARSET_UTF8MB4,
    autocommit=MYSQL_AUTOCOMMIT,
)

AC_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'autocomplete.db')

# --- Noise stripping (lightweight — keep answer content) ----------------------

RE_ACTION_MARKER = re.compile(r'\*[^*]{2,}\*')
RE_FILE_REF = re.compile(r'@\[[^\]]+\]')
RE_URL = re.compile(r'https?://\S+')
RE_MARKDOWN_BOLD = re.compile(r'\*\*([^*]+)\*\*')
RE_MULTI_PUNCT = re.compile(r'([!?])\1{2,}')
RE_CODE_BLOCK = re.compile(r'```[^`]*```', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`[^`]+`')


def _strip_noise_light(text):
    """Strip action markers, file refs, URLs from text. Keep code blocks (part of answer)."""
    if not text:
        return ""
    text = RE_ACTION_MARKER.sub('', text)
    text = RE_FILE_REF.sub('', text)
    text = RE_URL.sub('', text)
    text = RE_MARKDOWN_BOLD.sub(r'\1', text)
    text = RE_MULTI_PUNCT.sub(r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _strip_noise_question(text):
    """Heavier strip for questions — also remove code blocks and inline code."""
    if not text:
        return ""
    text = RE_CODE_BLOCK.sub('', text)
    text = RE_INLINE_CODE.sub('', text)
    text = RE_ACTION_MARKER.sub('', text)
    text = RE_FILE_REF.sub('', text)
    text = RE_URL.sub('', text)
    text = RE_MARKDOWN_BOLD.sub(r'\1', text)
    text = RE_MULTI_PUNCT.sub(r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_for_hash(text):
    """Normalize question text for hashing: lowercase, strip punctuation, collapse spaces."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _compute_hash(text):
    """MD5 of normalized text."""
    norm = _normalize_for_hash(text)
    if not norm:
        return None
    return hashlib.md5(norm.encode('utf-8')).hexdigest()


def _is_followup(question_text):
    """Check if question references a previous one (contains followup words)."""
    if not question_text:
        return False
    low = question_text.lower()
    for word in FOLLOWUP_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', low):
            return True
    return False


def _split_sentences(text):
    """Split text into sentences by . ! ? boundaries, keeping the punctuation."""
    if not text:
        return []
    raw = re.split(r'([.!?]+)', text)
    sentences = []
    for i in range(0, len(raw) - 1, 2):
        sentence = (raw[i] + raw[i + 1]).strip()
        if sentence:
            sentences.append(sentence)
    if len(raw) % 2 == 1 and raw[-1].strip():
        sentences.append(raw[-1].strip())
    return sentences


def _extract_questions(text):
    """Extract individual question sentences from text. Must contain '?'."""
    if not text or not text.strip():
        return []
    clean_text = _strip_noise_question(text)
    if not clean_text:
        return []
    if QUESTION_MARK not in clean_text:
        return []
    sentences = _split_sentences(clean_text)
    questions = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < MIN_QUESTION_LEN:
            continue
        if not s.endswith(QUESTION_MARK):
            continue
        alpha_count = sum(1 for c in s if c.isalpha())
        if alpha_count < 3:
            continue
        questions.append(s)
    return questions


# --- Cascade chat parsing ----------------------------------------------------

def _split_cascade_blocks(content):
    """Split chat_ingestions content into (user_input, planner_response) pairs.
    Returns list of (user_text, answer_text) tuples."""
    if not content:
        return []
    pairs = []
    parts = content.split(MARKER_USER_INPUT)
    for part in parts[1:]:
        # Find the next ### Planner Response within this part
        pr_idx = part.find(MARKER_PLANNER_RESPONSE)
        if pr_idx < 0:
            continue
        user_text = part[:pr_idx].strip()
        # Answer = from after Planner Response marker to next ### section or end
        after_pr = part[pr_idx + len(MARKER_PLANNER_RESPONSE):]
        next_section = after_pr.find(MARKER_SECTION)
        if next_section >= 0:
            answer_text = after_pr[:next_section].strip()
        else:
            answer_text = after_pr.strip()
        if user_text and answer_text:
            pairs.append((user_text, answer_text))
    return pairs


# --- ChatGPT JSON parsing ----------------------------------------------------

def _extract_chatgpt_pairs(content):
    """Parse ChatGPT JSON, extract (question, answer) pairs with branch info.
    Returns list of (question_text, answer_text, branch_index) tuples.
    branch_index > 1 when a user message has multiple assistant responses (regen).
    ChatGPT tree: user → system/tool → assistant. Walk through intermediate nodes."""
    if not content:
        return []
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []

    conversations = data if isinstance(data, list) else [data]
    pairs = []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get('mapping', {})
        if not isinstance(mapping, dict):
            continue
        # Build children map: parent_id -> [child_node_ids]
        children_map = {}
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            parent = node.get('parent')
            if parent:
                children_map.setdefault(parent, []).append(node_id)
        # Find user nodes with question marks
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            msg = node.get('message')
            if not isinstance(msg, dict):
                continue
            author = msg.get('author', {})
            if not isinstance(author, dict) or author.get('role') != 'user':
                continue
            content_obj = msg.get('content', {})
            if not isinstance(content_obj, dict):
                continue
            parts = content_obj.get('parts', [])
            if not isinstance(parts, list):
                continue
            text_parts = [p for p in parts if isinstance(p, str)]
            user_text = ' '.join(text_parts).strip()
            if not user_text or QUESTION_MARK not in user_text:
                continue
            # Find assistant responses by walking through intermediate nodes
            assistant_answers = _find_assistant_responses(mapping, children_map, node_id)
            if not assistant_answers:
                continue
            for idx, answer in enumerate(assistant_answers, 1):
                pairs.append((user_text, answer, idx))
    return pairs


def _find_assistant_responses(mapping, children_map, start_node_id, max_depth=5):
    """Walk the ChatGPT tree from a user node, collect assistant responses.
    ChatGPT regen structure: user → system → assistant(original) → assistant(regen)
    Regen branches are assistant CHILDREN of the first assistant, not siblings.
    Returns list of answer strings: [original, regen1, regen2, ...]"""
    answers = []
    visited = set()

    def collect_assistant_text(nid):
        """Extract text from an assistant node."""
        cnode = mapping.get(nid, {})
        if not isinstance(cnode, dict):
            return None
        cmsg = cnode.get('message')
        if not isinstance(cmsg, dict):
            return None
        ccontent = cmsg.get('content', {})
        if not isinstance(ccontent, dict):
            return None
        cparts = ccontent.get('parts', [])
        if not isinstance(cparts, list):
            return None
        ctext = ' '.join(p for p in cparts if isinstance(p, str)).strip()
        return ctext if ctext else None

    def find_first_assistant(nid, depth):
        """Walk through system/tool nodes to find the first assistant response."""
        if depth > max_depth or nid in visited:
            return None
        visited.add(nid)
        for cid in children_map.get(nid, []):
            cnode = mapping.get(cid, {})
            if not isinstance(cnode, dict):
                continue
            cmsg = cnode.get('message')
            if not isinstance(cmsg, dict):
                continue
            crole = cmsg.get('author', {}).get('role')
            if crole == 'assistant':
                return cid
            elif crole in ('system', 'tool', 'unknown'):
                result = find_first_assistant(cid, depth + 1)
                if result:
                    return result
        return None

    def collect_regen_branches(asst_nid, depth=0):
        """From an assistant node, collect regen branches (assistant children)."""
        if depth > max_depth or asst_nid in visited:
            return
        visited.add(asst_nid)
        for cid in children_map.get(asst_nid, []):
            cnode = mapping.get(cid, {})
            if not isinstance(cnode, dict):
                continue
            cmsg = cnode.get('message')
            if not isinstance(cmsg, dict):
                continue
            crole = cmsg.get('author', {}).get('role')
            if crole == 'assistant':
                text = collect_assistant_text(cid)
                if text:
                    answers.append(text)
                # Recurse: regen of regen
                collect_regen_branches(cid, depth + 1)

    # Find the first (original) assistant response
    first_asst = find_first_assistant(start_node_id, 0)
    if first_asst:
        text = collect_assistant_text(first_asst)
        if text:
            answers.append(text)
        # Collect regen branches (assistant children of the first assistant)
        collect_regen_branches(first_asst, 0)

    return answers


# --- Main class ---------------------------------------------------------------

class QaPairExtractor:
    """Extract Q&A pairs from MySQL vb_shared chat tables into SQLite tree."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": dict(MYSQL_CFG),
            "ac_db_path": AC_DB_PATH,
            "stats": {
                "pairs_extracted": 0,
                "by_source": Counter(),
                "by_style": Counter(),
                "multi_branch": 0,
                "followups": 0,
                "skipped_no_answer": 0,
                "skipped_no_question": 0,
            },
            "session_last_id": {},  # session_id -> last inserted qa_pair id (for follow-up chains)
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
        """Create autocomplete.db and qa_pairs table if not exists."""
        conn = sqlite3.connect(self.state["ac_db_path"])
        cur = conn.cursor()
        cur.execute(SQL_CREATE_TABLE)
        conn.commit()
        return conn

    def Extract(self, params=None):
        """Main extraction: scan both sources, build Q&A tree, insert into SQLite."""
        stats = self.state["stats"]
        sqlite_conn = None
        mysql_conn = None
        try:
            sqlite_conn = self.InitSqlite()
            mysql_conn = self.MysqlConn()
            mysql_cur = mysql_conn.cursor()

            # Source 1: chat_ingestions (Cascade)
            mysql_cur.execute('SELECT id, file_name, content FROM chat_ingestions WHERE content IS NOT NULL AND content != ""')
            rows = mysql_cur.fetchall()
            for row_id, file_name, content in rows:
                self._process_cascade_doc(sqlite_conn, row_id, file_name, content)

            # Source 2: json_ingestions (ChatGPT)
            mysql_cur.execute('SELECT id, file_name, content FROM json_ingestions WHERE content IS NOT NULL AND content != ""')
            rows = mysql_cur.fetchall()
            for row_id, file_name, content in rows:
                self._process_chatgpt_doc(sqlite_conn, row_id, file_name, content)

            # Create indexes after all inserts
            cur = sqlite_conn.cursor()
            cur.execute(SQL_INDEX_HASH)
            cur.execute(SQL_INDEX_STYLE)
            sqlite_conn.commit()

            mysql_conn.close()
            sqlite_conn.close()

            summary = self._build_summary()
            sys.stderr.write(summary)
            return (1, summary, None)
        except Exception as ex:
            if mysql_conn:
                try:
                    mysql_conn.close()
                except Exception:
                    pass
            if sqlite_conn:
                try:
                    sqlite_conn.close()
                except Exception:
                    pass
            return (0, None, ('EXTRACT_ERROR', str(ex), 0))

    def _process_cascade_doc(self, sqlite_conn, row_id, file_name, content):
        """Process one chat_ingestions document (one Cascade chat file)."""
        stats = self.state["stats"]
        session_id = file_name or str(row_id)
        pairs = _split_cascade_blocks(content)
        for user_text, answer_text in pairs:
            questions = _extract_questions(user_text)
            if not questions:
                stats["skipped_no_question"] += 1
                continue
            answer_clean = _strip_noise_light(answer_text)
            if len(answer_clean) < MIN_ANSWER_LEN:
                stats["skipped_no_answer"] += 1
                continue
            answer_clean = answer_clean[:MAX_ANSWER_LEN]
            mode, _ = DetectStyleMode(user_text)
            for q in questions:
                self._insert_pair(sqlite_conn, q, answer_clean, mode, SOURCE_CASCADE, session_id, 1)

    def _process_chatgpt_doc(self, sqlite_conn, row_id, file_name, content):
        """Process one json_ingestions document (one ChatGPT export)."""
        stats = self.state["stats"]
        session_id = file_name or str(row_id)
        pairs = _extract_chatgpt_pairs(content)
        for user_text, answer_text, branch_idx in pairs:
            questions = _extract_questions(user_text)
            if not questions:
                stats["skipped_no_question"] += 1
                continue
            answer_clean = _strip_noise_light(answer_text)
            if len(answer_clean) < MIN_ANSWER_LEN:
                stats["skipped_no_answer"] += 1
                continue
            answer_clean = answer_clean[:MAX_ANSWER_LEN]
            mode, _ = DetectStyleMode(user_text)
            if branch_idx > 1:
                stats["multi_branch"] += 1
            for q in questions:
                self._insert_pair(sqlite_conn, q, answer_clean, mode, SOURCE_CHATGPT, session_id, branch_idx)

    def _insert_pair(self, sqlite_conn, question, answer, style_mode, source, session_id, branch_index):
        """Insert one Q&A pair, set parent_question_id for follow-up chains."""
        stats = self.state["stats"]
        q_hash = _compute_hash(question)
        # Follow-up chain: if question references previous, link to last pair in same session
        parent_id = None
        if _is_followup(question):
            parent_id = self.state["session_last_id"].get(session_id)
            if parent_id:
                stats["followups"] += 1
        cur = sqlite_conn.cursor()
        cur.execute(SQL_INSERT_PAIR, (
            question, answer, style_mode, source, session_id,
            parent_id, branch_index, q_hash,
            None,  # created_at uses DEFAULT CURRENT_TIMESTAMP
        ))
        new_id = cur.lastrowid
        sqlite_conn.commit()
        # Track last inserted id for this session (for follow-up chains)
        self.state["session_last_id"][session_id] = new_id
        stats["pairs_extracted"] += 1
        stats["by_source"][source] += 1
        stats["by_style"][style_mode] += 1

    def _build_summary(self):
        """Build text summary of extraction stats."""
        s = self.state["stats"]
        lines = [
            "\n[Extract_qa_pairs] Summary",
            "=" * 50,
            f"Total Q&A pairs extracted:  {s['pairs_extracted']}",
            f"Multi-branch (ChatGPT):     {s['multi_branch']}",
            f"Follow-up chains:           {s['followups']}",
            f"Skipped (no question):      {s['skipped_no_question']}",
            f"Skipped (no answer):        {s['skipped_no_answer']}",
            "",
            "By source:",
        ]
        for source, count in s["by_source"].most_common():
            lines.append(f"  {source:20s} {count}")
        lines.append("")
        lines.append("By style_mode:")
        for mode, count in s["by_style"].most_common():
            lines.append(f"  {mode:20s} {count}")
        lines.append("=" * 50 + "\n")
        return "\n".join(lines)


# --- Entry point --------------------------------------------------------------

def main():
    extractor = QaPairExtractor()
    ok, data, err = extractor.Run('extract')
    if not ok:
        sys.stderr.write(f"ERROR: {err}\n")
        sys.exit(1)
    # Final verification
    conn = sqlite3.connect(AC_DB_PATH)
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM {TABLE_QA_PAIRS}')
    total = cur.fetchone()[0]
    cur.execute(f'SELECT source, COUNT(*) FROM {TABLE_QA_PAIRS} GROUP BY source')
    by_source = cur.fetchall()
    cur.execute(f'SELECT style_mode, COUNT(*) FROM {TABLE_QA_PAIRS} GROUP BY style_mode')
    by_style = cur.fetchall()
    cur.execute(f'SELECT COUNT(*) FROM {TABLE_QA_PAIRS} WHERE branch_index > 1')
    branches = cur.fetchone()[0]
    cur.execute(f'SELECT COUNT(*) FROM {TABLE_QA_PAIRS} WHERE parent_question_id IS NOT NULL')
    followups = cur.fetchone()[0]
    conn.close()
    sys.stderr.write(f"\nVerify: {total} qa_pairs\n")
    sys.stderr.write(f"  by_source: {by_source}\n")
    sys.stderr.write(f"  by_style:  {by_style}\n")
    sys.stderr.write(f"  branches>1: {branches}\n")
    sys.stderr.write(f"  followups:  {followups}\n")


if __name__ == '__main__':
    main()
