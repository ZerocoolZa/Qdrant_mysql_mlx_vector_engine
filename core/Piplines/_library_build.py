#!/usr/bin/env python3
"""
Pipelines Library Builder
=========================
Ingests all PLF_*.md files into SQLite as a fractal index system.
Handles: books, chapters, sections, glossary terms, glossary links,
         methods, nodes, links, provenance, binary artifacts, checks.

Does NOT delete or modify any .md files. Read-only on markdown.
SQLite is the execution truth layer. Markdown is the navigation layer.
"""

import os
import re
import sqlite3
import hashlib
import json
from datetime import datetime

LIBRARY_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(LIBRARY_PATH, "pipelines_library.db")


SCHEMA_SQL = """
-- ============================================================
-- TIER 1: LIBRARY STRUCTURE (navigation layer mirror)
-- ============================================================

CREATE TABLE IF NOT EXISTS books (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    title TEXT,
    core_thesis TEXT,
    status TEXT DEFAULT 'ACTIVE',
    sqlite_backend TEXT,
    line_count INTEGER DEFAULT 0,
    char_count INTEGER DEFAULT 0,
    file_hash TEXT,
    ingested_at TEXT DEFAULT (datetime('now')),
    raw_content TEXT
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_number TEXT,
    chapter_title TEXT,
    chapter_level INTEGER DEFAULT 2,
    line_start INTEGER,
    line_end INTEGER,
    body_text TEXT,
    has_mini_index INTEGER DEFAULT 0,
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

CREATE TABLE IF NOT EXISTS sections (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    section_number TEXT,
    section_title TEXT,
    section_level INTEGER DEFAULT 3,
    line_start INTEGER,
    line_end INTEGER,
    body_text TEXT,
    section_type TEXT,
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

-- ============================================================
-- TIER 2: GLOSSARY (global semantic layer)
-- ============================================================

CREATE TABLE IF NOT EXISTS glossary_terms (
    term_id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL UNIQUE,
    definition TEXT,
    category TEXT,
    sqlite_mapping TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS glossary_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id INTEGER NOT NULL,
    book_id INTEGER,
    chapter_id INTEGER,
    section_id INTEGER,
    link_type TEXT,
    FOREIGN KEY (term_id) REFERENCES glossary_terms(term_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id),
    FOREIGN KEY (section_id) REFERENCES sections(section_id)
);

-- ============================================================
-- TIER 3: CODE EXECUTION LAYER (methods, nodes, links)
-- ============================================================

CREATE TABLE IF NOT EXISTS methods (
    method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    class_name TEXT,
    method_name TEXT,
    signature TEXT,
    body TEXT,
    file_origin TEXT,
    line_start INTEGER,
    line_end INTEGER,
    source_hash TEXT,
    domain TEXT,
    is_vbstyle INTEGER DEFAULT 0,
    has_run_method INTEGER DEFAULT 0,
    returns_tuple3 INTEGER DEFAULT 0,
    has_print INTEGER DEFAULT 0,
    has_decorators INTEGER DEFAULT 0,
    has_self_underscore_attr INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_type TEXT NOT NULL,
    node_name TEXT NOT NULL,
    node_value TEXT,
    domain TEXT,
    importance_score REAL DEFAULT 0.5,
    mention_count INTEGER DEFAULT 1,
    source_book_id INTEGER,
    source_chapter_id INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_book_id) REFERENCES books(book_id),
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(chapter_id)
);

CREATE TABLE IF NOT EXISTS links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id INTEGER NOT NULL,
    to_node_id INTEGER NOT NULL,
    link_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    evidence TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (from_node_id) REFERENCES nodes(node_id),
    FOREIGN KEY (to_node_id) REFERENCES nodes(node_id)
);

-- ============================================================
-- TIER 4: PROVENANCE (source tracking, lineage)
-- ============================================================

CREATE TABLE IF NOT EXISTS provenance (
    provenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    dest_path TEXT,
    dest_type TEXT,
    source_hash TEXT,
    dest_hash TEXT,
    file_size INTEGER,
    book_id INTEGER,
    copied_at TEXT DEFAULT (datetime('now')),
    notes TEXT,
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

-- ============================================================
-- TIER 5: BINARY ARTIFACTS (compiled pipeline code)
-- ============================================================
-- Some PLF markdowns contain code that compiles to a binary.
-- This table stores those binaries with full provenance.

CREATE TABLE IF NOT EXISTS binary_artifacts (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    chapter_id INTEGER,
    artifact_name TEXT NOT NULL,
    artifact_type TEXT,
    source_language TEXT,
    source_code TEXT,
    compiled_binary BLOB,
    binary_hash TEXT,
    compile_command TEXT,
    compile_status TEXT,
    compile_output TEXT,
    file_size_bytes INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id)
);

-- ============================================================
-- TIER 6: CHECKS (downloaded/saved verification checks)
-- ============================================================
-- Checks are downloaded or generated verification artifacts
-- attached to a pipeline as evidence of correctness.

CREATE TABLE IF NOT EXISTS checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    chapter_id INTEGER,
    check_name TEXT NOT NULL,
    check_type TEXT,
    check_status TEXT DEFAULT 'PENDING',
    check_url TEXT,
    check_content TEXT,
    check_hash TEXT,
    check_result TEXT,
    check_metadata TEXT,
    attached_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id)
);

-- ============================================================
-- TIER 7: CROSS-PIPELINE MAP (which pipeline connects to which)
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_connections (
    connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_book_id INTEGER NOT NULL,
    to_book_id INTEGER NOT NULL,
    connection_type TEXT,
    description TEXT,
    status TEXT,
    FOREIGN KEY (from_book_id) REFERENCES books(book_id),
    FOREIGN KEY (to_book_id) REFERENCES books(book_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_books_file ON books(file_name);
CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_sections_chapter ON sections(chapter_id);
CREATE INDEX IF NOT EXISTS idx_sections_book ON sections(book_id);
CREATE INDEX IF NOT EXISTS idx_glossary_term ON glossary_terms(term);
CREATE INDEX IF NOT EXISTS idx_glossary_links_term ON glossary_links(term_id);
CREATE INDEX IF NOT EXISTS idx_methods_class ON methods(class_name);
CREATE INDEX IF NOT EXISTS idx_methods_book ON methods(book_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_node_id);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_node_id);
CREATE INDEX IF NOT EXISTS idx_binary_book ON binary_artifacts(book_id);
CREATE INDEX IF NOT EXISTS idx_checks_book ON checks(book_id);
"""


def compute_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def parse_markdown_to_books(db_path, library_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    md_files = sorted([
        f for f in os.listdir(library_path)
        if f.endswith('.md') and f != 'index.md' and f != 'glossary.md'
        and not f.startswith('_template')
    ])

    for md_file in md_files:
        file_path = os.path.join(library_path, md_file)
        with open(file_path, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()

        lines = content.split('\n')
        file_hash = compute_hash(content)
        line_count = len(lines)
        char_count = len(content)

        title = md_file.replace('.md', '')
        core_thesis = None
        status = 'ACTIVE'
        sqlite_backend = None

        for line in lines[:30]:
            if line.startswith('# ') and not line.startswith('#[@'):
                title = line[2:].strip()
            if 'Core thesis:' in line:
                core_thesis = line.split('Core thesis:')[1].strip().strip('"').strip("'")
            if 'Status:' in line:
                status = line.split('Status:')[1].strip()
            if 'DB:' in line or 'SQLite' in line or 'sqlite' in line:
                if 'DB:' in line:
                    sqlite_backend = line.split('DB:')[1].strip()
                elif 'DB:' in line:
                    sqlite_backend = line.split('DB:')[1].strip()

        cur.execute("""
            INSERT OR REPLACE INTO books
            (file_name, file_path, title, core_thesis, status, sqlite_backend,
             line_count, char_count, file_hash, raw_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (md_file, file_path, title, core_thesis, status, sqlite_backend,
              line_count, char_count, file_hash, content))

        book_id = cur.execute(
            "SELECT book_id FROM books WHERE file_name = ?", (md_file,)
        ).fetchone()[0]

        current_chapter_id = None
        current_chapter_num = None
        current_chapter_start = None
        current_chapter_lines = []

        current_section_id = None
        current_section_num = None
        current_section_start = None
        current_section_lines = []

        def flush_chapter():
            nonlocal current_chapter_id, current_chapter_num, current_chapter_start, current_chapter_lines
            if current_chapter_id is not None and current_chapter_lines:
                body = '\n'.join(current_chapter_lines)
                has_mini = 1 if 'mini-index' in body.lower() or 'mini index' in body.lower() else 0
                cur.execute("""
                    UPDATE chapters SET body_text = ?, has_mini_index = ?, line_end = ?
                    WHERE chapter_id = ?
                """, (body, has_mini, current_chapter_start + len(current_chapter_lines),
                      current_chapter_id))

        def flush_section():
            nonlocal current_section_id, current_section_lines, current_section_start
            if current_section_id is not None and current_section_lines:
                body = '\n'.join(current_section_lines)
                sec_type = 'unknown'
                lower_title = (current_section_num or '').lower()
                if 'purpose' in lower_title:
                    sec_type = 'purpose'
                elif 'input' in lower_title:
                    sec_type = 'inputs'
                elif 'step' in lower_title:
                    sec_type = 'steps'
                elif 'edge' in lower_title:
                    sec_type = 'edge_cases'
                elif 'output' in lower_title:
                    sec_type = 'outputs'
                elif 'cross' in lower_title or 'reference' in lower_title:
                    sec_type = 'cross_references'
                elif 'index' in lower_title:
                    sec_type = 'mini_index'
                elif 'breakdown' in lower_title:
                    sec_type = 'breakdown'

                cur.execute("""
                    UPDATE sections SET body_text = ?, section_type = ?, line_end = ?
                    WHERE section_id = ?
                """, (body, sec_type, current_section_start + len(current_section_lines),
                      current_section_id))

        for i, line in enumerate(lines):
            if line.startswith('#[@'):
                continue

            if line.startswith('## ') and not line.startswith('### '):
                flush_section()
                flush_chapter()

                chapter_title = line[3:].strip()
                chapter_num = None
                match = re.match(r'Chapter\s+(\d+)\s*:', chapter_title, re.IGNORECASE)
                if match:
                    chapter_num = match.group(1)
                else:
                    match = re.match(r'(\d+)\.\s', chapter_title)
                    if match:
                        chapter_num = match.group(1)

                cur.execute("""
                    INSERT INTO chapters (book_id, chapter_number, chapter_title,
                                          chapter_level, line_start)
                    VALUES (?, ?, ?, 2, ?)
                """, (book_id, chapter_num, chapter_title, i + 1))
                current_chapter_id = cur.lastrowid
                current_chapter_num = chapter_num
                current_chapter_start = i + 1
                current_chapter_lines = [line]
                current_section_id = None

            elif line.startswith('### '):
                flush_section()

                section_title = line[4:].strip()
                section_num = None
                match = re.match(r'(\d+\.\d+)\s', section_title)
                if match:
                    section_num = match.group(1)

                cur.execute("""
                    INSERT INTO sections (chapter_id, book_id, section_number,
                                          section_title, section_level, line_start)
                    VALUES (?, ?, ?, ?, 3, ?)
                """, (current_chapter_id, book_id, section_num, section_title, i + 1))
                current_section_id = cur.lastrowid
                current_section_num = section_num
                current_section_start = i + 1
                current_section_lines = [line]

            else:
                if current_section_id is not None:
                    current_section_lines.append(line)
                elif current_chapter_id is not None:
                    current_chapter_lines.append(line)

        flush_section()
        flush_chapter()

    conn.commit()
    return conn, len(md_files)


def ingest_glossary(conn, library_path):
    glossary_path = os.path.join(library_path, 'glossary.md')
    if not os.path.exists(glossary_path):
        return 0

    with open(glossary_path, 'r', encoding='utf-8') as fh:
        content = fh.read()

    cur = conn.cursor()
    count = 0

    current_term = None
    current_def = []
    current_sqlite_mapping = None

    for line in content.split('\n'):
        if line.startswith('### ') and not line.startswith('####'):
            if current_term and current_def:
                cur.execute("""
                    INSERT OR REPLACE INTO glossary_terms (term, definition, sqlite_mapping)
                    VALUES (?, ?, ?)
                """, (current_term, '\n'.join(current_def).strip(), current_sqlite_mapping))
                count += 1

            current_term = line[4:].strip()
            current_def = []
            current_sqlite_mapping = None

        elif line.startswith('- **SQLite:**') or line.startswith('- **SQLite '):
            current_sqlite_mapping = line.split('**SQLite:**')[-1].strip() if '**SQLite:**' in line else line.split('**SQLite')[-1].strip()

        elif current_term and not line.startswith('---') and not line.startswith('#'):
            if line.strip():
                current_def.append(line)

    if current_term and current_def:
        cur.execute("""
            INSERT OR REPLACE INTO glossary_terms (term, definition, sqlite_mapping)
            VALUES (?, ?, ?)
        """, (current_term, '\n'.join(current_def).strip(), current_sqlite_mapping))
        count += 1

    conn.commit()
    return count


def detect_binary_artifacts(conn):
    cur = conn.cursor()
    books = cur.execute("SELECT book_id, file_name, raw_content FROM books").fetchall()

    for book_id, file_name, content in books:
        has_c_code = bool(re.search(r'```c\n', content))
        has_makefile = bool(re.search(r'Makefile|makefile|\.c\b.*compile|gcc|clang', content))
        has_compile = bool(re.search(r'compile|build.*binary|\.o\b|\.bin\b', content, re.IGNORECASE))
        has_swift = bool(re.search(r'```swift\n', content))

        if has_c_code or has_makefile or has_compile or has_swift:
            lang = 'C' if has_c_code else ('Swift' if has_swift else 'unknown')
            cur.execute("""
                INSERT INTO binary_artifacts
                (book_id, artifact_name, artifact_type, source_language,
                 source_code, compile_status, file_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (book_id, file_name.replace('.md', '_binary'),
                  'detected_from_markdown', lang,
                  'Source code detected in markdown — extract and compile separately',
                  'DETECTED_NOT_COMPILED', 0))

    conn.commit()


def detect_checks(conn):
    cur = conn.cursor()
    books = cur.execute("SELECT book_id, file_name, raw_content FROM books").fetchall()

    check_keywords = [
        'verify', 'verification', 'check', 'py_compile',
        'VBStyle compliance', 'test', 'validation',
        'pass', 'fail', 'verify_lineage', 'integrity'
    ]

    for book_id, file_name, content in books:
        content_lower = content.lower()
        found_checks = []

        for kw in check_keywords:
            if kw in content_lower:
                found_checks.append(kw)

        if found_checks:
            cur.execute("""
                INSERT INTO checks
                (book_id, check_name, check_type, check_status, check_metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (book_id, file_name.replace('.md', '_checks'),
                  'detected_from_markdown', 'DETECTED',
                  json.dumps({'keywords_found': found_checks})))

    conn.commit()


def build_pipeline_connections(conn):
    cur = conn.cursor()
    books = cur.execute("SELECT book_id, file_name, title, raw_content FROM books").fetchall()

    for from_id, from_file, from_title, from_content in books:
        for to_id, to_file, to_title, to_content in books:
            if from_id == to_id:
                continue
            from_title_lower = from_title.lower() if from_title else ''
            to_title_lower = to_title.lower() if to_title else ''
            to_file_lower = to_file.lower()

            if to_file in from_content or to_title_lower in from_content.lower():
                conn_type = 'references'
                desc = "%s mentions %s" % (from_file, to_file)
                cur.execute("""
                    INSERT INTO pipeline_connections
                    (from_book_id, to_book_id, connection_type, description, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (from_id, to_id, conn_type, desc, 'DETECTED'))

    conn.commit()


def print_stats(conn):
    cur = conn.cursor()
    tables = [
        'books', 'chapters', 'sections', 'glossary_terms', 'glossary_links',
        'methods', 'nodes', 'links', 'provenance',
        'binary_artifacts', 'checks', 'pipeline_connections'
    ]

    print("\n" + "=" * 60)
    print("PIPELINES LIBRARY DATABASE — STATS")
    print("=" * 60)

    for table in tables:
        count = cur.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        if count > 0:
            print("  %-25s %5d rows" % (table, count))

    print("\n  DB path: %s" % DB_PATH)
    print("=" * 60)


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

    print("Schema created: %s" % DB_PATH)

    conn, book_count = parse_markdown_to_books(DB_PATH, LIBRARY_PATH)
    print("Ingested %d books" % book_count)

    glossary_count = ingest_glossary(conn, LIBRARY_PATH)
    print("Ingested %d glossary terms" % glossary_count)

    detect_binary_artifacts(conn)
    binary_count = conn.execute("SELECT COUNT(*) FROM binary_artifacts").fetchone()[0]
    print("Detected %d binary artifact candidates" % binary_count)

    detect_checks(conn)
    check_count = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    print("Detected %d check candidates" % check_count)

    build_pipeline_connections(conn)
    conn_count = conn.execute("SELECT COUNT(*) FROM pipeline_connections").fetchone()[0]
    print("Built %d cross-pipeline connections" % conn_count)

    print_stats(conn)
    conn.close()


if __name__ == '__main__':
    main()
