#!/usr/bin/env python3
"""
Pipelines Library — Pass 2: Semantic Linking + Mini-Index + Book Index
=====================================================================
Completes the 3 missing compilation passes:

  PASS 2a: Book index — chapter order per book (structured, not implicit)
  PASS 2b: Chapter mini-index — parse mini-index lines into navigable rows
  PASS 2c: Glossary linking — scan all content for term occurrences → glossary_links

Run AFTER _library_build.py (Pass 1).
Does NOT modify any .md files. Read-only on markdown, write to SQLite.
"""

import os
import re
import sqlite3

LIBRARY_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(LIBRARY_PATH, "pipelines_library.db")


PASS2_SCHEMA = """
-- Book index: explicit chapter ordering per book
CREATE TABLE IF NOT EXISTS book_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_id INTEGER NOT NULL,
    chapter_order INTEGER NOT NULL,
    chapter_number TEXT,
    chapter_title TEXT,
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id)
);

-- Chapter mini-index: structured navigable entries inside each chapter
CREATE TABLE IF NOT EXISTS chapter_mini_index (
    mini_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    section_number TEXT,
    section_title TEXT,
    pointer_type TEXT,
    pointer_value TEXT,
    FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);
"""


def pass2a_book_index(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM book_index")

    books = cur.execute("SELECT book_id FROM books ORDER BY file_name").fetchall()
    total = 0

    for (book_id,) in books:
        chapters = cur.execute("""
            SELECT chapter_id, chapter_number, chapter_title, line_start
            FROM chapters WHERE book_id = ? ORDER BY line_start
        """, (book_id,)).fetchall()

        for order, (ch_id, ch_num, ch_title, _) in enumerate(chapters, 1):
            cur.execute("""
                INSERT INTO book_index (book_id, chapter_id, chapter_order,
                                        chapter_number, chapter_title)
                VALUES (?, ?, ?, ?, ?)
            """, (book_id, ch_id, order, ch_num, ch_title))
            total += 1

    conn.commit()
    return total


def pass2b_chapter_mini_index(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM chapter_mini_index")

    chapters = cur.execute("""
        SELECT chapter_id, book_id, body_text, chapter_title
        FROM chapters WHERE body_text IS NOT NULL
    """).fetchall()

    total = 0
    mini_pattern = re.compile(
        r'^[-*]\s*(?:(\d+\.\d+)\s+)?(.+)$'
    )

    for ch_id, book_id, body, ch_title in chapters:
        lines = body.split('\n') if body else []
        in_mini_index = False
        order = 0
        found_explicit = False

        for line in lines:
            stripped = line.strip()

            lower = stripped.lower()
            if 'mini-index' in lower or 'mini index' in lower or 'chapter index' in lower:
                in_mini_index = True
                found_explicit = True
                continue

            if in_mini_index:
                if stripped.startswith('---') or stripped.startswith('##') or stripped.startswith('###'):
                    in_mini_index = False
                    continue

                if not stripped:
                    continue

                match = mini_pattern.match(stripped)
                if match:
                    sec_num = match.group(1)
                    label = match.group(2).strip()

                    label_clean = re.sub(r'[*_`]', '', label)

                    pointer_type = 'section'
                    pointer_value = sec_num if sec_num else label_clean

                    cur.execute("""
                        INSERT INTO chapter_mini_index
                        (chapter_id, book_id, label, order_index,
                         section_number, section_title, pointer_type, pointer_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (ch_id, book_id, label_clean, order,
                          sec_num, label_clean, pointer_type, pointer_value))
                    order += 1
                    total += 1
                elif stripped.startswith('#'):
                    in_mini_index = False

        if not found_explicit:
            sections = cur.execute("""
                SELECT section_number, section_title, line_start
                FROM sections WHERE chapter_id = ? ORDER BY line_start
            """, (ch_id,)).fetchall()

            for sec_order, (sec_num, sec_title, sec_line) in enumerate(sections):
                label_clean = re.sub(r'[*_`]', '', sec_title or '')
                pointer_value = sec_num if sec_num else label_clean

                cur.execute("""
                    INSERT INTO chapter_mini_index
                    (chapter_id, book_id, label, order_index,
                     section_number, section_title, pointer_type, pointer_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ch_id, book_id, label_clean, sec_order,
                      sec_num, label_clean, 'section', pointer_value))
                total += 1

    conn.commit()
    return total


def pass2c_glossary_links(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM glossary_links")

    terms = cur.execute("SELECT term_id, term FROM glossary_terms ORDER BY LENGTH(term) DESC").fetchall()
    if not terms:
        return 0

    term_map = {}
    for term_id, term in terms:
        term_lower = term.lower()
        if term_lower not in term_map:
            term_map[term_lower] = (term_id, term)

    total = 0

    chapters = cur.execute("""
        SELECT chapter_id, book_id, body_text, chapter_title
        FROM chapters WHERE body_text IS NOT NULL
    """).fetchall()

    for ch_id, book_id, body, ch_title in chapters:
        if not body:
            continue
        body_lower = body.lower()

        for term_lower, (term_id, term) in term_map.items():
            if term_lower in body_lower:
                cur.execute("""
                    INSERT INTO glossary_links
                    (term_id, book_id, chapter_id, link_type)
                    VALUES (?, ?, ?, ?)
                """, (term_id, book_id, ch_id, 'chapter_mention'))
                total += 1

    sections = cur.execute("""
        SELECT section_id, chapter_id, book_id, body_text, section_title
        FROM sections WHERE body_text IS NOT NULL
    """, ).fetchall()

    for sec_id, ch_id, book_id, body, sec_title in sections:
        if not body:
            continue
        body_lower = body.lower()

        for term_lower, (term_id, term) in term_map.items():
            if term_lower in body_lower:
                cur.execute("""
                    INSERT INTO glossary_links
                    (term_id, book_id, chapter_id, section_id, link_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (term_id, book_id, ch_id, sec_id, 'section_mention'))
                total += 1

    conn.commit()
    return total


def print_stats(conn):
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("PASS 2 — SEMANTIC LINKING + MINI-INDEX + BOOK INDEX")
    print("=" * 60)

    book_idx = cur.execute("SELECT COUNT(*) FROM book_index").fetchone()[0]
    mini_idx = cur.execute("SELECT COUNT(*) FROM chapter_mini_index").fetchone()[0]
    gloss_links = cur.execute("SELECT COUNT(*) FROM glossary_links").fetchone()[0]

    print("  book_index:            %5d rows" % book_idx)
    print("  chapter_mini_index:    %5d rows" % mini_idx)
    print("  glossary_links:        %5d rows" % gloss_links)

    print("\n  Top glossary terms by link count:")
    top = cur.execute("""
        SELECT t.term, COUNT(l.link_id) as cnt
        FROM glossary_terms t
        LEFT JOIN glossary_links l ON t.term_id = l.term_id
        GROUP BY t.term_id
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()
    for term, cnt in top:
        print("    %-25s %5d links" % (term, cnt))

    print("\n  Books with mini-indexes:")
    mini_books = cur.execute("""
        SELECT b.file_name, COUNT(m.mini_id) as entries
        FROM books b
        JOIN chapter_mini_index m ON b.book_id = m.book_id
        GROUP BY b.book_id
        ORDER BY entries DESC
        LIMIT 10
    """).fetchall()
    for fname, entries in mini_books:
        print("    %-45s %3d entries" % (fname, entries))

    print("\n  Sample book index (first book):")
    first_book = cur.execute("""
        SELECT bi.chapter_order, bi.chapter_number, bi.chapter_title
        FROM book_index bi
        JOIN books b ON bi.book_id = b.book_id
        ORDER BY b.file_name, bi.chapter_order
        LIMIT 8
    """).fetchall()
    for order, num, title in first_book:
        num_str = "Ch %s" % num if num else "?"
        print("    %2d. [%s] %s" % (order, num_str, title))

    print("=" * 60)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(PASS2_SCHEMA)
    conn.commit()

    print("Pass 2 schema added (book_index, chapter_mini_index)")

    print("\nPASS 2a: Building book index...")
    book_count = pass2a_book_index(conn)
    print("  -> %d book index entries" % book_count)

    print("\nPASS 2b: Extracting chapter mini-indexes...")
    mini_count = pass2b_chapter_mini_index(conn)
    print("  -> %d mini-index entries" % mini_count)

    print("\nPASS 2c: Linking glossary terms to chapters/sections...")
    link_count = pass2c_glossary_links(conn)
    print("  -> %d glossary links" % link_count)

    print_stats(conn)
    conn.close()


if __name__ == '__main__':
    main()
