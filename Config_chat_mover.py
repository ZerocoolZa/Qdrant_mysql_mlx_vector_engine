#!/usr/bin/env python3
#[@GHOST]{("file_path=Config_chat_mover.py";"identity=Config_chat_mover.py";"purpose=";"date=2026-06-29";"version=1.0";"author=Cascade";"chat_link=")}
#[@VBSTYLE]{[@pass]{"return=Tuple3";"dispatch=Run";"no=no_decorators|no_print|no_hardcoded";"model=one_class_one_domain_one_authority_complete"}[@fail]{"decorators_found";"print_found";"hardcoded_values";"self._used"}}
#[@FILEID]{("session_id=auto";"context=Auto-stamped by header watcher";"purpose=")}
#[@SUMMARY]{("Created on 2026-06-29";"auto_stamped=true")}


# ═════════════════════════════════════════════════════════════
# BCL CHAT STORE — Full Schema SQL (from bcl_chat_store.py)
# ═════════════════════════════════════════════════════════════

BCL_CHAT_STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS original_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_name TEXT NOT NULL,
    md5_hash TEXT NOT NULL,
    line_count INTEGER NOT NULL,
    file_size INTEGER NOT NULL,
    date_ingested TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bcl_stage1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    compression_ratio REAL NOT NULL,
    output_lines INTEGER NOT NULL,
    output_text TEXT NOT NULL,
    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    stat    statT,
    chat_id INTEGER NOT NULL,
    stage1_id INTEGER NOT NULL,
    problems_count INTEGER DEFAULT 0,
    unresolved_count INTEGER DEFAULT 0,
    decisions_count INTEGER DEFAULT 0,
    successes_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    lessons_count INTEGER DEFAULT 0,
    output_text TEXT NOT NULL,
    date_created TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES original_chats(id),
    FOREIGN KEY (stage1_id) REFERENCES bc    FOREIGN KEY (stage1_id) REIF NOT EXISTS chat_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    stage2_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    line_number INTEGER,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    keyword TEXT,
    date_created TEXT NOT NULL,
    FOREIGN KEY (chat_    FOREIGN KEY (chat_    FOR(i    FOREIGN KEY (chat_    FOREIGN KEY (chat_    FOR(i    FOREIGN KEY (chat_    FOREIGN KEY (chat_    FOR(i    FOREIGN KEY (chat_    FOREIGN KEY (chat_    FOR(i    FOREIGN KEY (chat_    FOREIGN l_    FOREIGN KEY (chat_    DEX     FOREIGN KEY (chat_    FORcha    FOREIGN KEY (chat_    FOREIGN KEEX    FOREIGN KEY (chat_    FOREIGN KEY ch    FOREIGN KEY (chat_    FOREDEX IF NOT EXISTS idx_chat_items_status ON chat_items(status);
"""
