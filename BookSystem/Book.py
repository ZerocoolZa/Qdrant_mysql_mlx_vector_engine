#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Book.py
# Domain:   Book database management
# Authority: Book content CRUD + export
# DB:       SQLite (vbstyle_book_schema.sql v2)
# Binary:   python3 Book.py <command> [params...]
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @clshdr   — Class Header present
#   @mthdr    — Method Header present on every method
#   @run      — Run(command, params) dispatch entry point
#   @disp     — dispatch internal, maps keys to methods
#   @tuples   — all methods return (ok, data, error)
#   @errfmt   — error tuple (code, desc, 0)
#   @state    — self.state dict (config, catalog, results)
#   @noself   — no self._ variables
#   @pascal   — PascalCase class name
#   @upper    — UPPERCASE constants at class level
#   @ctor     — __init__(self, mem=None, db=None, param=None)
#   @rpt      — Report returns strings, no print
#   @print    — no print statements (only main prints)
#   @decorators — no decorators
#   @enums    — no enums
#   @domain   — one class, one domain (Book = book DB management)
#   @dismap   — every dispatch key maps to exactly one method
#   @rdst     — ReadState returns config snapshot
#   @phelp    — _p helper extracts params by key
#   @hardcode — DB path from BOOK_DB env var, not hardcoded
#   @params   — all methods accept data as parameters
#   @succ     — success return (1, data, ())
#   @err      — error return (0, None, (code, desc, 0))
# ============================================================================

import sqlite3
import sys
import os
import json
import subprocess

from config import Config, cfg


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  Book
# Domain: Book database management
# Authority: CRUD operations on book content + markdown export
# Dependencies: sqlite3 (built-in), os, sys, json
# DB: SQLite file (vbstyle_book_schema.sql v2)
# ============================================================================


class Book:
    # ------------------------------------------------------------------------
    # UPPERCASE CONSTANTS
    # ------------------------------------------------------------------------
    DB_DEFAULT = Config.DB_PATH
    MARKDOWN_PATH = Config.MARKDOWN_PATH
    VERSION = Config.CLI_VERSION

    # ------------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------------
    # Method: __init__
    # Purpose: Initialize Book instance with DB connection
    # Params:  mem=None (unused, VBStyle convention), db=None (DB path),
    #          param=None (unused, schema now embedded in config.py)
    # Returns: None (constructor)
    # ------------------------------------------------------------------------
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "db_path": os.environ.get("BOOK_DB", db or self.DB_DEFAULT),
            "db": None,
            "report": "",
            "last_id": None,
        }

    # ------------------------------------------------------------------------
    # PARAM HELPER
    # ------------------------------------------------------------------------
    # Method: _p
    # Purpose: Extract param by key with default value
    # Params:  params (dict), key (str), default (any)
    # Returns: value from params or default
    # Rule:    @phelp
    # ------------------------------------------------------------------------
    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    # ------------------------------------------------------------------------
    # DISPATCH ENTRY POINT
    # ------------------------------------------------------------------------
    # Method: Run
    # Purpose: Dispatch entry point — route command to method
    # Params:  command (str), params (dict)
    # Returns: Tuple3 (ok, data, error)
    # Rule:    @run
    # ------------------------------------------------------------------------
    def Run(self, command, params):
        return self.dispatch(command, params)

    # ------------------------------------------------------------------------
    # INTERNAL DISPATCH
    # ------------------------------------------------------------------------
    # Method: dispatch
    # Purpose: Map command string to method, execute, return Tuple3
    # Params:  command (str), params (dict)
    # Returns: Tuple3 (ok, data, error)
    # Rule:    @disp @dismap
    # ------------------------------------------------------------------------
    def dispatch(self, command, params):
        dispatch_table = {
            "init": self.Init,
            "stats": self.Stats,
            "add-part": self.AddPart,
            "add-chapter": self.AddChapter,
            "add-section": self.AddSection,
            "add-block": self.AddBlock,
            "add-rule": self.AddRule,
            "link-rule": self.LinkRule,
            "add-glossary": self.AddGlossary,
            "add-summary": self.AddSummary,
            "add-xref": self.AddXref,
            "add-table": self.AddTable,
            "update-part": self.UpdatePart,
            "update-chapter": self.UpdateChapter,
            "update-section": self.UpdateSection,
            "update-block": self.UpdateBlock,
            "update-glossary": self.UpdateGlossary,
            "update-rule": self.UpdateRule,
            "remove-section": self.RemoveSection,
            "remove-block": self.RemoveBlock,
            "remove-xref": self.RemoveXref,
            "import-md": self.ImportMd,
            "export-all": self.ExportAll,
            "export-flipbook": self.ExportFlipbook,
            "search": self.Search,
            "check": self.Check,
            "add-annotation": self.AddAnnotation,
            "list-annotations": self.ListAnnotations,
            "remove-annotation": self.RemoveAnnotation,
            "export": self.ExportChapter,
            "outline": self.Outline,
            "list-rules": self.ListRules,
            "list-glossary": self.ListGlossary,
            "list-xrefs": self.ListXrefs,
            "info": self.Info,
            "state": self.ReadState,
            "report": self.Report,
            "search-mysql": self.SearchMysql,
            "populate-mysql": self.PopulateMysql,
            "search-code": self.SearchCode,
            "search-docs": self.SearchDocs,
            "cross-query": self.CrossQuery,
            "link-content": self.LinkContent,
            "fix-summaries": self.FixSummaries,
            "fix-glossary": self.FixGlossary,
            "fix-names": self.FixNames,
            "populate-milestones": self.PopulateMilestones,
            "promote": self.Promote,
            "list-milestones": self.ListMilestones,
            "list-authorities": self.ListAuthorities,
            "check-contradictions": self.CheckContradictions,
            "write-narrative": self.WriteNarrative,
            "discover-relations": self.DiscoverRelations,
            "polish": self.Polish,
        }

        method = dispatch_table.get(command)
        if method is None:
            return (0, None, ("BADCMD", f"Unknown command: {command}", 0))
        return method(params)

    # ------------------------------------------------------------------------
    # DB HELPERS
    # ------------------------------------------------------------------------
    # Method: OpenDB
    # Purpose: Open SQLite connection, enable FK + WAL
    # Params:  None (uses self.state)
    # Returns: Tuple3 (ok, conn, error)
    # ------------------------------------------------------------------------
    def OpenDB(self):
        path = self.state["db_path"]
        if not os.path.exists(path):
            return (
                0,
                None,
                ("NOTFOUND", f"DB not found at {path}. Run 'init' first.", 0),
            )
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        self.state["db"] = conn
        return (1, conn, ())

    # Method: CloseDB
    # Purpose: Close DB connection if open
    # Params:  None
    # Returns: Tuple3 (1, None, ())
    # ------------------------------------------------------------------------
    def CloseDB(self):
        if self.state["db"] is not None:
            self.state["db"].close()
            self.state["db"] = None
        return (1, None, ())

    # ------------------------------------------------------------------------
    # INIT — Create DB from schema SQL
    # ------------------------------------------------------------------------
    # Method: Init
    # Purpose: Create the book database from Config.SCHEMA_SQL (embedded in config.py)
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def Init(self, params):
        db_path = self.state["db_path"]

        # --- Schema is embedded in config.py — single source of truth ---
        schema_sql = Config.SCHEMA_SQL
        if not schema_sql:
            return (
                0,
                None,
                ("NO_SCHEMA", "No schema found in Config.SCHEMA_SQL", 0),
            )

        dir_path = os.path.dirname(db_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        if os.path.exists(db_path):
            self.state["report"] = f"DB already exists: {db_path}"
            return (1, self.state["report"], ())

        conn = sqlite3.connect(db_path)
        conn.executescript(schema_sql)
        conn.close()

        self.state["report"] = f"Created DB: {db_path}"
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # STATS — Row counts per table
    # ------------------------------------------------------------------------
    # Method: Stats
    # Purpose: Show row counts for each table in the DB
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def Stats(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        tables = [
            "parts", "chapters", "sections", "content_blocks",
            "rules", "rule_relations", "section_rules", "chapter_rules",
            "comparison_tables", "cross_refs", "chapter_summaries",
            "glossary", "schema_meta",
        ]

        lines = []
        lines.append(f"{'Table':<25} {'Rows':>6}")
        lines.append("-" * 32)
        for table in tables:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            lines.append(f"{table:<25} {count:>6}")

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # ADD PART
    # ------------------------------------------------------------------------
    # Method: AddPart
    # Purpose: Insert a top-level book part
    # Params:  params = {'part_num': int, 'title': str, 'subtitle': str}
    # Returns: Tuple3 (ok, part_id, error)
    # ------------------------------------------------------------------------
    def AddPart(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        part_num = self._p(params, "part_num")
        title = self._p(params, "title")
        subtitle = self._p(params, "subtitle", "")

        if part_num is None or title is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: part_num, title", 0))

        try:
            cur = conn.execute(
                "INSERT INTO parts (part_num, title, subtitle) VALUES (?, ?, ?)",
                (int(part_num), title, subtitle),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = f"Added part {part_num}: {title} (id={cur.lastrowid})"
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD CHAPTER
    # ------------------------------------------------------------------------
    # Method: AddChapter
    # Purpose: Insert a chapter within a part
    # Params:  params = {'part_id': int, 'ch_num': int, 'title': str, 'subtitle': str}
    # Returns: Tuple3 (ok, chapter_id, error)
    # ------------------------------------------------------------------------
    def AddChapter(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        part_id = self._p(params, "part_id")
        ch_num = self._p(params, "ch_num")
        title = self._p(params, "title")
        subtitle = self._p(params, "subtitle", "")

        if part_id is None or ch_num is None or title is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: part_id, ch_num, title", 0))

        try:
            cur = conn.execute(
                "INSERT INTO chapters (part_id, ch_num, title, subtitle) "
                "VALUES (?, ?, ?, ?)",
                (int(part_id), int(ch_num), title, subtitle),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = (
                f"Added chapter {ch_num}: {title} (id={cur.lastrowid})"
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD SECTION
    # ------------------------------------------------------------------------
    # Method: AddSection
    # Purpose: Insert a section within a chapter
    # Params:  params = {'chapter_id': int, 'sec_num': str, 'sort_order': int,
    #                    'title': str, 'section_type': str}
    # Returns: Tuple3 (ok, section_id, error)
    # ------------------------------------------------------------------------
    def AddSection(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        chapter_id = self._p(params, "chapter_id")
        sec_num = self._p(params, "sec_num")
        sort_order = self._p(params, "sort_order")
        title = self._p(params, "title")
        section_type = self._p(params, "section_type", "content")

        if chapter_id is None or sec_num is None or sort_order is None or title is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: chapter_id, sec_num, sort_order, title", 0))

        try:
            cur = conn.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(chapter_id), sec_num, int(sort_order), title, section_type),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = (
                f"Added section {sec_num}: {title} (id={cur.lastrowid})"
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD BLOCK — Content block (text, code, callout, table)
    # ------------------------------------------------------------------------
    # Method: AddBlock
    # Purpose: Insert an ordered content block within a section
    # Params:  params = {'section_id': int, 'block_type': str, 'block_order': int,
    #                    'content': str, 'lang': str, 'caption': str, 'table_id': int}
    # Returns: Tuple3 (ok, block_id, error)
    # ------------------------------------------------------------------------
    def AddBlock(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")
        block_type = self._p(params, "block_type")
        block_order = self._p(params, "block_order")
        content = self._p(params, "content")
        lang = self._p(params, "lang")
        caption = self._p(params, "caption")
        table_id = self._p(params, "table_id")

        if section_id is None or block_type is None or block_order is None or content is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: section_id, block_type, block_order, content", 0))

        try:
            cur = conn.execute(
                "INSERT INTO content_blocks "
                "(section_id, block_type, block_order, content, lang, caption, table_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(section_id), block_type, int(block_order), content, lang, caption, table_id),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = (
                f"Added {block_type} block #{block_order} to section {section_id} (id={cur.lastrowid})"
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD RULE
    # ------------------------------------------------------------------------
    # Method: AddRule
    # Purpose: Insert a VBStyle rule into the rules reference table
    # Params:  params = {'rule_num': int, 'tag': str, 'category': str,
    #                    'short_desc': str, 'full_desc': str,
    #                    'example_bad': str, 'example_good': str, 'chapter_id': int}
    # Returns: Tuple3 (ok, rule_id, error)
    # ------------------------------------------------------------------------
    def AddRule(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        rule_num = self._p(params, "rule_num")
        tag = self._p(params, "tag")
        category = self._p(params, "category")
        short_desc = self._p(params, "short_desc")
        full_desc = self._p(params, "full_desc")
        example_bad = self._p(params, "example_bad")
        example_good = self._p(params, "example_good")
        chapter_id = self._p(params, "chapter_id")

        if rule_num is None or tag is None or category is None or short_desc is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: rule_num, tag, category, short_desc", 0))

        try:
            cur = conn.execute(
                "INSERT INTO rules "
                "(rule_num, tag, category, short_desc, full_desc, "
                " example_bad, example_good, chapter_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (int(rule_num), tag, category, short_desc, full_desc,
                 example_bad, example_good,
                 int(chapter_id) if chapter_id else None),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = (
                f"Added rule #{rule_num} {tag}: {short_desc} (id={cur.lastrowid})"
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # LINK RULE — Link a rule to a section or chapter
    # ------------------------------------------------------------------------
    # Method: LinkRule
    # Purpose: Create a rule-to-section or rule-to-chapter association
    # Params:  params = {'rule_id': int, 'target_type': 'section'|'chapter',
    #                    'target_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def LinkRule(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        rule_id = self._p(params, "rule_id")
        target_type = self._p(params, "target_type")
        target_id = self._p(params, "target_id")

        if rule_id is None or target_type is None or target_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: rule_id, target_type, target_id", 0))

        try:
            if target_type == "section":
                conn.execute(
                    "INSERT OR IGNORE INTO section_rules (section_id, rule_id) "
                    "VALUES (?, ?)",
                    (int(target_id), int(rule_id)),
                )
            elif target_type == "chapter":
                conn.execute(
                    "INSERT OR IGNORE INTO chapter_rules (chapter_id, rule_id) "
                    "VALUES (?, ?)",
                    (int(target_id), int(rule_id)),
                )
            else:
                self.CloseDB()
                return (0, None, ("BADCMD", "target_type must be 'section' or 'chapter'", 0))

            conn.commit()
            self.state["report"] = (
                f"Linked rule {rule_id} to {target_type} {target_id}"
            )
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD GLOSSARY
    # ------------------------------------------------------------------------
    # Method: AddGlossary
    # Purpose: Insert a glossary term with definition
    # Params:  params = {'term': str, 'definition': str, 'chapter_id': int}
    # Returns: Tuple3 (ok, glossary_id, error)
    # ------------------------------------------------------------------------
    def AddGlossary(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        term = self._p(params, "term")
        definition = self._p(params, "definition")
        chapter_id = self._p(params, "chapter_id")

        if term is None or definition is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: term, definition", 0))

        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO glossary (term, definition, chapter_id) "
                "VALUES (?, ?, ?)",
                (term, definition,
                 int(chapter_id) if chapter_id else None),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = f"Added glossary: {term}"
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD SUMMARY
    # ------------------------------------------------------------------------
    # Method: AddSummary
    # Purpose: Insert or update a chapter summary
    # Params:  params = {'chapter_id': int, 'summary': str}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def AddSummary(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        chapter_id = self._p(params, "chapter_id")
        summary = self._p(params, "summary")

        if chapter_id is None or summary is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: chapter_id, summary", 0))

        try:
            conn.execute(
                "INSERT INTO chapter_summaries (chapter_id, summary) "
                "VALUES (?, ?) "
                "ON CONFLICT(chapter_id) DO UPDATE SET summary=excluded.summary",
                (int(chapter_id), summary),
            )
            conn.commit()
            self.state["report"] = f"Set summary for chapter {chapter_id}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD XREF — Cross-reference between sections/chapters
    # ------------------------------------------------------------------------
    # Method: AddXref
    # Purpose: Insert a cross-reference link
    # Params:  params = {'from_section': int, 'to_chapter': int,
    #                    'to_section': int, 'ref_text': str}
    # Returns: Tuple3 (ok, xref_id, error)
    # ------------------------------------------------------------------------
    def AddXref(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        from_section = self._p(params, "from_section")
        to_chapter = self._p(params, "to_chapter")
        to_section = self._p(params, "to_section")
        ref_text = self._p(params, "ref_text", "")

        if from_section is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: from_section", 0))

        try:
            cur = conn.execute(
                "INSERT INTO cross_refs (from_section, to_section, to_chapter, ref_text) "
                "VALUES (?, ?, ?, ?)",
                (int(from_section),
                 int(to_section) if to_section else None,
                 int(to_chapter) if to_chapter else None,
                 ref_text),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = f"Added xref from section {from_section}"
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # ADD TABLE — Comparison table
    # ------------------------------------------------------------------------
    # Method: AddTable
    # Purpose: Insert a structured comparison table
    # Params:  params = {'section_id': int, 'title': str,
    #                    'headers': list, 'rows': list-of-lists}
    # Returns: Tuple3 (ok, table_id, error)
    # ------------------------------------------------------------------------
    def AddTable(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")
        title = self._p(params, "title")
        headers = self._p(params, "headers", [])
        rows = self._p(params, "rows", [])

        if section_id is None or title is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: section_id, title", 0))

        headers_json = json.dumps(headers) if isinstance(headers, list) else headers
        rows_json = json.dumps(rows) if isinstance(rows, list) else rows

        try:
            cur = conn.execute(
                "INSERT INTO comparison_tables (section_id, title, column_headers, rows) "
                "VALUES (?, ?, ?, ?)",
                (int(section_id), title, headers_json, rows_json),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            self.state["report"] = (
                f"Added comparison table '{title}' to section {section_id} (id={cur.lastrowid})"
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE PART — Change part title/subtitle/description
    # ------------------------------------------------------------------------
    # Method: UpdatePart
    # Purpose: Update a part by part_num. Only changes provided fields.
    #          Cascades automatically: all views JOIN to parts.title.
    # Params:  params = {'part_num': int, 'title': str, 'subtitle': str,
    #                    'description': str}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdatePart(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        part_num = self._p(params, "part_num")
        if part_num is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: part_num", 0))

        fields = []
        values = []
        for col in ("title", "subtitle", "description"):
            val = self._p(params, col)
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide title/subtitle/description", 0))

        values.append(int(part_num))
        try:
            conn.execute(
                f"UPDATE parts SET {', '.join(fields)} WHERE part_num = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated part {part_num}: {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE CHAPTER — Change title/subtitle/description
    # ------------------------------------------------------------------------
    # Method: UpdateChapter
    # Purpose: Update a chapter by ch_num. Only changes provided fields.
    #          Cascades automatically: v_chapter_outline, v_export_chapter,
    #          v_glossary_index, v_cross_ref_graph all JOIN to chapters.title.
    #          Rename a chapter → every view and export shows the new name.
    # Params:  params = {'ch_num': int, 'title': str, 'subtitle': str,
    #                    'description': str}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdateChapter(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        ch_num = self._p(params, "ch_num")
        if ch_num is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: ch_num", 0))

        fields = []
        values = []
        for col in ("title", "subtitle", "description"):
            val = self._p(params, col)
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide title/subtitle/description", 0))

        values.append(int(ch_num))
        try:
            conn.execute(
                f"UPDATE chapters SET {', '.join(fields)} WHERE ch_num = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated chapter {ch_num}: {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE SECTION — Change title/type/word_count/page_num
    # ------------------------------------------------------------------------
    # Method: UpdateSection
    # Purpose: Update a section by id. Only changes provided fields.
    #          Cascades: v_chapter_outline shows new title/page_num instantly.
    #          v_export_chapter shows new section header.
    # Params:  params = {'section_id': int, 'title': str, 'section_type': str,
    #                    'word_count': int, 'page_num': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdateSection(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")
        if section_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: section_id", 0))

        fields = []
        values = []
        for col in ("title", "section_type", "word_count", "page_num"):
            val = self._p(params, col)
            if val is not None and val != "":
                if col in ("word_count", "page_num"):
                    val = int(val)
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide title/section_type/word_count/page_num", 0))

        values.append(int(section_id))
        try:
            conn.execute(
                f"UPDATE sections SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated section {section_id}: {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE BLOCK — Change content/lang/caption/order
    # ------------------------------------------------------------------------
    # Method: UpdateBlock
    # Purpose: Update a content block by id. Only changes provided fields.
    #          Cascades: v_export_chapter shows new content immediately.
    # Params:  params = {'block_id': int, 'content': str, 'lang': str,
    #                    'caption': str, 'block_order': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdateBlock(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        block_id = self._p(params, "block_id")
        if block_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: block_id", 0))

        fields = []
        values = []
        for col in ("content", "lang", "caption", "block_order"):
            val = self._p(params, col)
            if val is not None and val != "":
                if col == "block_order":
                    val = int(val)
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide content/lang/caption/block_order", 0))

        values.append(int(block_id))
        try:
            conn.execute(
                f"UPDATE content_blocks SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated block {block_id}: {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE GLOSSARY — Change term/definition
    # ------------------------------------------------------------------------
    # Method: UpdateGlossary
    # Purpose: Update a glossary entry by term (or by id).
    #          Cascades: v_glossary_index shows new term/definition instantly.
    # Params:  params = {'term': str (current term), 'new_term': str,
    #                    'definition': str, 'chapter_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdateGlossary(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        term = self._p(params, "term")
        if term is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: term (current term to update)", 0))

        fields = []
        values = []
        new_term = self._p(params, "new_term")
        if new_term is not None:
            fields.append("term = ?")
            values.append(new_term)

        definition = self._p(params, "definition")
        if definition is not None:
            fields.append("definition = ?")
            values.append(definition)

        chapter_id = self._p(params, "chapter_id")
        if chapter_id is not None:
            fields.append("chapter_id = ?")
            values.append(int(chapter_id))

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide new_term/definition/chapter_id", 0))

        values.append(term)
        try:
            conn.execute(
                f"UPDATE glossary SET {', '.join(fields)} WHERE term = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated glossary '{term}': {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # UPDATE RULE — Change tag/category/desc/examples
    # ------------------------------------------------------------------------
    # Method: UpdateRule
    # Purpose: Update a rule by rule_num. Only changes provided fields.
    #          Cascades: v_rules_index shows new tag/desc instantly.
    #          All junction tables (section_rules, chapter_rules) reference
    #          rule_id, not tag — so renaming a tag doesn't break links.
    # Params:  params = {'rule_num': int, 'tag': str, 'category': str,
    #                    'short_desc': str, 'full_desc': str,
    #                    'example_bad': str, 'example_good': str, 'chapter_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def UpdateRule(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        rule_num = self._p(params, "rule_num")
        if rule_num is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: rule_num", 0))

        fields = []
        values = []
        for col in ("tag", "category", "short_desc", "full_desc",
                     "example_bad", "example_good"):
            val = self._p(params, col)
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        chapter_id = self._p(params, "chapter_id")
        if chapter_id is not None:
            fields.append("chapter_id = ?")
            values.append(int(chapter_id))

        if not fields:
            self.CloseDB()
            return (0, None, ("BADCMD", "No fields to update. Provide tag/category/short_desc/etc", 0))

        values.append(int(rule_num))
        try:
            conn.execute(
                f"UPDATE rules SET {', '.join(fields)} WHERE rule_num = ?",
                values,
            )
            conn.commit()
            self.state["report"] = f"Updated rule {rule_num}: {', '.join(fields)}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # REMOVE SECTION — Delete section + cascade (blocks, rules, xrefs)
    # ------------------------------------------------------------------------
    # Method: RemoveSection
    # Purpose: Delete a section by id. Cascades automatically via FK:
    #          - content_blocks (ON DELETE CASCADE)
    #          - section_rules (ON DELETE CASCADE)
    #          - comparison_tables (ON DELETE CASCADE)
    #          - cross_refs from_section (ON DELETE CASCADE)
    #          - cross_refs to_section (ON DELETE SET NULL)
    # Params:  params = {'section_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def RemoveSection(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")
        if section_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: section_id", 0))

        try:
            # Get section info for report before delete
            row = conn.execute(
                "SELECT sec_num, title FROM sections WHERE id = ?",
                (int(section_id),),
            ).fetchone()

            if not row:
                self.CloseDB()
                return (0, None, ("NOTFOUND", f"Section {section_id} not found", 0))

            # Delete — FK cascades handle content_blocks, section_rules, etc.
            conn.execute("DELETE FROM sections WHERE id = ?", (int(section_id),))
            conn.commit()

            self.state["report"] = (
                f"Removed section {row[0]}: {row[1]} (id={section_id}) "
                f"+ cascaded blocks, rules, xrefs"
            )
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # REMOVE BLOCK — Delete a single content block
    # ------------------------------------------------------------------------
    # Method: RemoveBlock
    # Purpose: Delete a content block by id. No cascade needed (leaf node).
    # Params:  params = {'block_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def RemoveBlock(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        block_id = self._p(params, "block_id")
        if block_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: block_id", 0))

        try:
            conn.execute("DELETE FROM content_blocks WHERE id = ?", (int(block_id),))
            conn.commit()
            self.state["report"] = f"Removed block {block_id}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # REMOVE XREF — Delete a cross-reference
    # ------------------------------------------------------------------------
    # Method: RemoveXref
    # Purpose: Delete a cross-reference by id
    # Params:  params = {'xref_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def RemoveXref(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        xref_id = self._p(params, "xref_id")
        if xref_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: xref_id", 0))

        try:
            conn.execute("DELETE FROM cross_refs WHERE id = ?", (int(xref_id),))
            conn.commit()
            self.state["report"] = f"Removed xref {xref_id}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # IMPORT MARKDOWN — Parse a .md file into the DB
    # ------------------------------------------------------------------------
    # Method: ImportMd
    # Purpose: Parse an existing markdown file into structured DB rows.
    #          Recognizes:
    #            ## Chapter N: Title       → chapters row
    #            ### N.N Title             → sections row (content type)
    #            ### Chapter N Summary     → sections row (summary type)
    #            ### Who This Is For       → sections row (who_for type)
    #            ### Conventions...        → sections row (conventions type)
    #            ```lang ... ```           → content_blocks row (code type)
    #            text between headers      → content_blocks row (text type)
    #            ## Glossary               → glossary entries parsed from - **Term** — def
    #            ---                       → section separator (ignored)
    #          Auto-creates part 1 if none exists.
    #          Auto-calculates sort_order and block_order.
    #          Auto-calculates word_count from text blocks.
    # Params:  params = {'file': str (path to markdown file)}
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def ImportMd(self, params):
        filepath = self._p(params, "file")
        if filepath is None:
            return (0, None, ("BADCMD", "Need: file (path to markdown file)", 0))

        if not os.path.exists(filepath):
            return (0, None, ("NOTFOUND", f"File not found: {filepath}", 0))

        with open(filepath, "r") as f:
            lines = f.readlines()

        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        # Ensure part 1 exists
        part_row = conn.execute("SELECT id FROM parts WHERE part_num = 1").fetchone()
        if part_row:
            part_id = part_row[0]
        else:
            cur = conn.execute(
                "INSERT INTO parts (part_num, title, subtitle) VALUES (1, 'Main', '')"
            )
            part_id = cur.lastrowid

        stats = {"chapters": 0, "sections": 0, "blocks": 0, "glossary": 0, "summaries": 0}
        current_chapter_id = None
        current_chapter_num = 0
        current_section_id = None
        current_sort_order = 0
        current_block_order = 0
        in_code_block = False
        code_lang = ""
        code_lines = []
        text_lines = []
        in_glossary = False

        def flush_text():
            """Flush accumulated text lines into a content_blocks row."""
            nonlocal current_block_order, text_lines
            if not text_lines or current_section_id is None:
                text_lines = []
                return
            content = "\n".join(text_lines).strip()
            if content:
                current_block_order += 1
                wc = len(content.split())
                conn.execute(
                    "INSERT INTO content_blocks "
                    "(section_id, block_type, block_order, content) "
                    "VALUES (?, 'text', ?, ?)",
                    (current_section_id, current_block_order, content),
                )
                stats["blocks"] += 1
                # Update section word count
                conn.execute(
                    "UPDATE sections SET word_count = word_count + ? WHERE id = ?",
                    (wc, current_section_id),
                )
            text_lines = []

        def flush_code():
            """Flush accumulated code lines into a content_blocks row."""
            nonlocal current_block_order, code_lines, code_lang
            if not code_lines or current_section_id is None:
                code_lines = []
                code_lang = ""
                return
            content = "\n".join(code_lines)
            current_block_order += 1
            conn.execute(
                "INSERT INTO content_blocks "
                "(section_id, block_type, block_order, content, lang) "
                "VALUES (?, 'code', ?, ?, ?)",
                (current_section_id, current_block_order, content, code_lang),
            )
            stats["blocks"] += 1
            code_lines = []
            code_lang = ""

        import re

        for line in lines:
            stripped = line.rstrip("\n")

            # --- Code block handling ---
            if stripped.startswith("```"):
                if in_code_block:
                    # End of code block
                    flush_code()
                    in_code_block = False
                else:
                    # Start of code block — flush text first
                    flush_text()
                    in_code_block = True
                    code_lang = stripped[3:].strip()
                continue

            if in_code_block:
                code_lines.append(stripped)
                continue

            # --- Glossary section ---
            if stripped == "## Glossary":
                flush_text()
                in_glossary = True
                current_section_id = None
                continue

            if in_glossary:
                # Parse: - **Term** — definition
                m = re.match(r"^-\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+)$", stripped)
                if m:
                    term = m.group(1).strip()
                    definition = m.group(2).strip()
                    conn.execute(
                        "INSERT OR REPLACE INTO glossary (term, definition, chapter_id) "
                        "VALUES (?, ?, ?)",
                        (term, definition, current_chapter_id),
                    )
                    stats["glossary"] += 1
                continue

            # --- Chapter heading: ## Chapter N: Title ---
            m = re.match(r"^## Chapter (\d+):\s*(.+)$", stripped)
            if m:
                flush_text()
                current_chapter_num = int(m.group(1))
                ch_title = m.group(2).strip()
                cur = conn.execute(
                    "INSERT INTO chapters (part_id, ch_num, title) VALUES (?, ?, ?)",
                    (part_id, current_chapter_num, ch_title),
                )
                current_chapter_id = cur.lastrowid
                current_sort_order = 0
                stats["chapters"] += 1
                continue

            # --- Chapter summary: ### Chapter N Summary ---
            m = re.match(r"^### Chapter (\d+) Summary\s*$", stripped)
            if m:
                flush_text()
                # Skip summaries that appear before the first chapter
                if current_chapter_id is None:
                    continue
                current_sort_order += 1
                cur = conn.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                    "VALUES (?, ?, ?, 'Chapter Summary', 'summary')",
                    (current_chapter_id, f"summary", current_sort_order),
                )
                current_section_id = cur.lastrowid
                current_block_order = 0
                stats["sections"] += 1
                stats["summaries"] += 1
                continue

            # --- Section heading: ### N.N Title or ### Title ---
            m = re.match(r"^### (\d+\.\d+[a-z]?)\s+(.+)$", stripped)
            if m:
                flush_text()
                sec_num = m.group(1)
                sec_title = m.group(2).strip()
                # Skip sections that appear before the first chapter
                if current_chapter_id is None:
                    continue
                current_sort_order += 1
                cur = conn.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                    "VALUES (?, ?, ?, ?, 'content')",
                    (current_chapter_id, sec_num, current_sort_order, sec_title),
                )
                current_section_id = cur.lastrowid
                current_block_order = 0
                stats["sections"] += 1
                continue

            # --- Named sections: ### Who This Is For, ### Conventions... ---
            m = re.match(r"^### (.+)$", stripped)
            if m:
                flush_text()
                sec_title = m.group(1).strip()
                sec_type = "content"
                if "who" in sec_title.lower():
                    sec_type = "who_for"
                elif "convention" in sec_title.lower():
                    sec_type = "conventions"
                elif "preface" in sec_title.lower():
                    sec_type = "preface"
                # Skip named sections that appear before the first chapter
                if current_chapter_id is None:
                    continue
                current_sort_order += 1
                cur = conn.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (current_chapter_id, f"s{current_sort_order}",
                     current_sort_order, sec_title, sec_type),
                )
                current_section_id = cur.lastrowid
                current_block_order = 0
                stats["sections"] += 1
                continue

            # --- Horizontal rule (section separator) ---
            if stripped == "---":
                flush_text()
                continue

            # --- Skip non-chapter ## headings (Preface, Chapter Index, etc.) ---
            if stripped.startswith("## ") and not stripped.startswith("## Chapter"):
                flush_text()
                current_section_id = None
                continue

            # --- Regular text line ---
            if current_section_id is not None:
                text_lines.append(stripped)

        # Flush any remaining content
        flush_text()
        flush_code()

        conn.commit()
        self.state["report"] = (
            f"Imported: {stats['chapters']} chapters, "
            f"{stats['sections']} sections, "
            f"{stats['blocks']} content blocks, "
            f"{stats['summaries']} summaries, "
            f"{stats['glossary']} glossary terms"
        )
        self.CloseDB()
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # EXPORT ALL — Full book to one markdown string
    # ------------------------------------------------------------------------
    # Method: ExportAll
    # Purpose: Export every chapter into one complete markdown document.
    #          Chapters are ordered by ch_num. Includes glossary at end.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, markdown_string, error)
    # ------------------------------------------------------------------------
    def ExportAll(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        chapters = conn.execute(
            "SELECT ch_num, title FROM chapters ORDER BY ch_num"
        ).fetchall()

        if not chapters:
            self.CloseDB()
            return (0, None, ("NOTFOUND", "No chapters found", 0))

        parts = []
        for ch in chapters:
            ch_num = ch[0]
            ch_title = ch[1]
            parts.append(f"\n## Chapter {ch_num}: {ch_title}\n")

            rows = conn.execute(
                "SELECT line FROM v_export_chapter WHERE ch_num = ? ORDER BY line_order",
                (ch_num,),
            ).fetchall()

            for row in rows:
                parts.append(row[0])
                parts.append("")

        # Append glossary
        glossary = conn.execute(
            "SELECT term, definition FROM glossary ORDER BY term"
        ).fetchall()
        if glossary:
            parts.append("\n## Glossary\n")
            for g in glossary:
                parts.append(f"- **{g[0]}** — {g[1]}\n")

        markdown = "\n".join(parts)
        self.state["report"] = markdown
        self.CloseDB()
        return (1, markdown, ())

    # ------------------------------------------------------------------------
    # EXPORT FLIPBOOK — Generate turn.js HTML book with page-flip effect
    # ------------------------------------------------------------------------
    # Method: ExportFlipbook
    # Purpose: Generate a self-contained HTML file using turn.js that renders
    #          the book as a physical flipbook with page-turn animations.
    #          Each section becomes a page. Code blocks get syntax styling.
    #          Opens in any browser — drag pages to flip, arrow keys to navigate.
    # Params:  params = {'file': str (output path), 'title': str (book title)}
    # Returns: Tuple3 (ok, file_path, error)
    # ------------------------------------------------------------------------
    def ExportFlipbook(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        output_path = self._p(params, "file", "book.html")
        book_title = self._p(params, "title", Config.BOOK_TITLE)
        theme_css = cfg.GetThemeCss()
        turnjs_code = cfg.GetTurnJs()

        # Build pages from DB
        chapters = conn.execute(
            "SELECT id, ch_num, title, subtitle FROM chapters ORDER BY ch_num"
        ).fetchall()

        pages_html = []

        # Cover page
        pages_html.append(
            '<div class="hard" style="background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); '
            'color: white; display: flex; flex-direction: column; '
            'justify-content: center; align-items: center; text-align: center;">'
            f'<h1 style="font-size: 28px; margin: 20px;">{book_title}</h1>'
            '<p style="font-size: 14px; opacity: 0.8;">A Blueprint for Self-Contained C Binaries</p>'
            '<p style="font-size: 12px; opacity: 0.6; margin-top: 30px;">Click or drag to flip →</p>'
            '</div>'
        )

        # Blank inner cover
        pages_html.append(
            '<div class="hard" style="background: #1a365d;"></div>'
        )

        # Table of contents page
        toc_items = []
        for ch in chapters:
            toc_items.append(
                f'<li style="margin: 4px 0;"><b>Chapter {ch["ch_num"]}</b> — {ch["title"]}</li>'
            )
        pages_html.append(
            f'<div class="page-content"><h2>Contents</h2><ul style="list-style: none; padding: 0;">'
            + "".join(toc_items) +
            '</ul></div>'
        )

        # Generate pages for each section
        for ch in chapters:
            sections = conn.execute(
                "SELECT id, sec_num, title, section_type, word_count "
                "FROM sections WHERE chapter_id = ? ORDER BY sort_order",
                (ch["id"],),
            ).fetchall()

            for sec in sections:
                blocks = conn.execute(
                    "SELECT block_type, content, lang, caption "
                    "FROM content_blocks WHERE section_id = ? ORDER BY block_order",
                    (sec["id"],),
                ).fetchall()

                page_content = []
                page_content.append(
                    f'<div class="page-header">Chapter {ch["ch_num"]}</div>'
                )
                page_content.append(
                    f'<h2>{sec["sec_num"]}  {sec["title"]}</h2>'
                )

                for block in blocks:
                    if block["block_type"] == "code":
                        lang_class = f'lang-{block["lang"]}' if block["lang"] else ""
                        escaped = block["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        page_content.append(
                            f'<pre class="code-block {lang_class}"><code>{escaped}</code></pre>'
                        )
                    elif block["block_type"] == "callout":
                        caption = block["caption"] or "Note"
                        page_content.append(
                            f'<div class="callout"><b>{caption}:</b> {block["content"]}</div>'
                        )
                    else:
                        page_content.append(
                            f'<div class="text-block">{self._md_to_flipbook_html(block["content"])}</div>'
                        )

                # Page footer with page number (approximate)
                page_content.append(
                    f'<div class="page-footer">{book_title}</div>'
                )

                pages_html.append(
                    f'<div class="page-content">' + "".join(page_content) + '</div>'
                )

        # Glossary page(s)
        glossary = conn.execute(
            "SELECT term, definition FROM glossary ORDER BY term"
        ).fetchall()
        if glossary:
            gloss_items = []
            for g in glossary:
                gloss_items.append(
                    f'<p><b>{g["term"]}</b> — {g["definition"]}</p>'
                )
            pages_html.append(
                '<div class="page-content"><h2>Glossary</h2>'
                + "".join(gloss_items) +
                '</div>'
            )

        # Back cover
        pages_html.append(
            '<div class="hard" style="background: #1a365d;"></div>'
        )
        pages_html.append(
            '<div class="hard" style="background: linear-gradient(135deg, #2c5282 0%, #1a365d 100%); '
            'color: white; display: flex; justify-content: center; align-items: center; text-align: center;">'
            '<p style="font-size: 14px; opacity: 0.7;">End</p></div>'
        )

        all_pages = "\n".join(
            f'        <div>{page}</div>' for page in pages_html
        )

        # Complete HTML document
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_title}</title>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script>
{turnjs_code}
</script>
<style>
{theme_css}
</style>
</head>
<body>

<div id="flipbook">
{all_pages}
</div>

<div class="nav-hint">← → arrow keys or drag pages to flip</div>

<script>
$(function() {{
    $("#flipbook").turn({{
        width: 900,
        height: 600,
        autoCenter: true,
        display: 'double',
        acceleration: true,
        gradients: true,
        elevation: 50,
        when: {{
            turning: function(e, page, view) {{
                // Update on page turn
            }},
            turned: function(e, page) {{
                // Page turned
            }}
        }}
    }});
}});

$(window).bind('keydown', function(e) {{
    if (e.keyCode == 37)  // left arrow
        $('#flipbook').turn('previous');
    else if (e.keyCode == 39)  // right arrow
        $('#flipbook').turn('next');
}});
</script>

</body>
</html>"""

        with open(output_path, "w") as f:
            f.write(html)

        page_count = len(pages_html)
        self.state["report"] = (
            f"Generated flipbook: {output_path} "
            f"({page_count} pages)"
        )
        self.CloseDB()
        return (1, output_path, ())

    # ------------------------------------------------------------------------
    # MARKDOWN TO FLIPBOOK HTML — Simple inline converter
    # ------------------------------------------------------------------------
    # Method: _md_to_flipbook_html
    # Purpose: Convert markdown text to HTML for flipbook pages.
    #          Handles: bold, italic, inline code, lists, tables, headings.
    # Params:  text (str) — markdown text
    # Returns: str — HTML string
    # ------------------------------------------------------------------------
    def _md_to_flipbook_html(self, text):
        if not text:
            return ""
        import re

        lines = text.split("\n")
        html_lines = []
        in_list = False
        in_table = False
        is_header_row = True

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if in_table:
                    html_lines.append("</table>")
                    in_table = False
                    is_header_row = True
                continue

            # Table row
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if all(re.match(r"^[-:]+$", c) for c in cells):
                    continue  # separator row
                if not in_table:
                    html_lines.append("<table>")
                    in_table = True
                if is_header_row:
                    html_lines.append("<tr>" + "".join(
                        f"<th>{c}</th>" for c in cells
                    ) + "</tr>")
                    is_header_row = False
                else:
                    html_lines.append("<tr>" + "".join(
                        f"<td>{c}</td>" for c in cells
                    ) + "</tr>")
                continue

            # List item
            if stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{self._inline_flipbook(stripped[2:])}</li>")
                continue

            # Headings
            if stripped.startswith("### "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h3>{self._inline_flipbook(stripped[4:])}</h3>")
                continue
            if stripped.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h2>{self._inline_flipbook(stripped[3:])}</h2>")
                continue

            # Blockquote
            if stripped.startswith("> "):
                html_lines.append(f"<blockquote>{self._inline_flipbook(stripped[2:])}</blockquote>")
                continue

            # Regular paragraph
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{self._inline_flipbook(stripped)}</p>")

        if in_list:
            html_lines.append("</ul>")
        if in_table:
            html_lines.append("</table>")

        return "\n".join(html_lines)

    # ------------------------------------------------------------------------
    # INLINE FLIPBOOK — Inline markdown to HTML
    # ------------------------------------------------------------------------
    # Method: _inline_flipbook
    # Purpose: Convert inline markdown (bold, italic, code) to HTML
    # Params:  text (str)
    # Returns: str — HTML string
    # ------------------------------------------------------------------------
    def _inline_flipbook(self, text):
        import re
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        return text

    # ------------------------------------------------------------------------
    # SEARCH — Find sections, blocks, and glossary by term
    # ------------------------------------------------------------------------
    # Method: Search
    # Purpose: Search content_blocks.content, sections.title, glossary.term
    #          and glossary.definition for a keyword. Returns matches with
    #          chapter/section context.
    # Params:  params = {'term': str}
    # Returns: Tuple3 (ok, results_string, error)
    # ------------------------------------------------------------------------
    def Search(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        term = self._p(params, "term")
        if term is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: term", 0))

        pattern = f"%{term}%"
        lines = []
        count = 0

        # Search section titles
        rows = conn.execute(
            "SELECT s.id, s.sec_num, s.title, c.ch_num, c.title "
            "FROM sections s JOIN chapters c ON c.id = s.chapter_id "
            "WHERE s.title LIKE ? ORDER BY c.ch_num, s.sort_order",
            (pattern,),
        ).fetchall()
        for r in rows:
            lines.append(f"  [section] Ch{r[3]} {r[1]} {r[2]}  (in: {r[4]})")
            count += 1

        # Search content blocks
        rows = conn.execute(
            "SELECT cb.id, cb.block_type, cb.content, s.sec_num, s.title, c.ch_num "
            "FROM content_blocks cb "
            "JOIN sections s ON s.id = cb.section_id "
            "JOIN chapters c ON c.id = s.chapter_id "
            "WHERE cb.content LIKE ? "
            "ORDER BY c.ch_num, s.sort_order, cb.block_order "
            "LIMIT 50",
            (pattern,),
        ).fetchall()
        for r in rows:
            snippet = r[2][:80].replace("\n", " ")
            lines.append(f"  [{r[1]}] Ch{r[5]} {r[3]} {r[4]}: {snippet}...")
            count += 1

        # Search glossary
        rows = conn.execute(
            "SELECT term, definition FROM glossary "
            "WHERE term LIKE ? OR definition LIKE ? ORDER BY term",
            (pattern, pattern),
        ).fetchall()
        for r in rows:
            lines.append(f"  [glossary] {r[0]}: {r[1][:80]}")
            count += 1

        if count == 0:
            self.state["report"] = f"No matches for '{term}'"
        else:
            self.state["report"] = f"Found {count} match(es) for '{term}':\n" + "\n".join(lines)

        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # CHECK — Integrity check
    # ------------------------------------------------------------------------
    # Method: Check
    # Purpose: Run integrity checks on the book DB:
    #          1. Broken cross-references (to_chapter/to_section that don't exist)
    #          2. Duplicate sort_order within a chapter
    #          3. Duplicate block_order within a section
    #          4. Chapters without summaries
    #          5. Sections without content blocks
    #          6. Rules not linked to any section or chapter
    #          7. Glossary terms without chapter_id
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def Check(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        issues = []

        # 1. Broken cross-references
        rows = conn.execute(
            "SELECT cr.id, cr.ref_text, cr.to_chapter "
            "FROM cross_refs cr "
            "WHERE cr.to_chapter IS NOT NULL "
            "AND cr.to_chapter NOT IN (SELECT id FROM chapters)"
        ).fetchall()
        for r in rows:
            issues.append(f"BROKEN XREF: xref {r[0]} → chapter id {r[2]} (doesn't exist). Text: {r[1]}")

        rows = conn.execute(
            "SELECT cr.id, cr.ref_text, cr.to_section "
            "FROM cross_refs cr "
            "WHERE cr.to_section IS NOT NULL "
            "AND cr.to_section NOT IN (SELECT id FROM sections)"
        ).fetchall()
        for r in rows:
            issues.append(f"BROKEN XREF: xref {r[0]} → section id {r[2]} (doesn't exist). Text: {r[1]}")

        # 2. Duplicate sort_order within a chapter
        rows = conn.execute(
            "SELECT chapter_id, sort_order, COUNT(*) as cnt "
            "FROM sections GROUP BY chapter_id, sort_order HAVING cnt > 1"
        ).fetchall()
        for r in rows:
            issues.append(f"DUPLICATE SORT_ORDER: chapter {r[0]} has sort_order {r[1]} used {r[2]} times")

        # 3. Duplicate block_order within a section
        rows = conn.execute(
            "SELECT section_id, block_order, COUNT(*) as cnt "
            "FROM content_blocks GROUP BY section_id, block_order HAVING cnt > 1"
        ).fetchall()
        for r in rows:
            issues.append(f"DUPLICATE BLOCK_ORDER: section {r[0]} has block_order {r[1]} used {r[2]} times")

        # 4. Chapters without summaries
        rows = conn.execute(
            "SELECT c.ch_num, c.title FROM chapters c "
            "WHERE c.id NOT IN (SELECT chapter_id FROM chapter_summaries) "
            "ORDER BY c.ch_num"
        ).fetchall()
        for r in rows:
            issues.append(f"MISSING SUMMARY: Chapter {r[0]}: {r[1]}")

        # 5. Sections without content blocks
        rows = conn.execute(
            "SELECT s.id, s.sec_num, s.title, c.ch_num "
            "FROM sections s JOIN chapters c ON c.id = s.chapter_id "
            "WHERE s.id NOT IN (SELECT DISTINCT section_id FROM content_blocks) "
            "ORDER BY c.ch_num, s.sort_order"
        ).fetchall()
        for r in rows:
            issues.append(f"EMPTY SECTION: Ch{r[3]} {r[1]} {r[2]} (id={r[0]}) has no content blocks")

        # 6. Rules not linked to any section or chapter
        rows = conn.execute(
            "SELECT r.rule_num, r.tag FROM rules r "
            "WHERE r.id NOT IN (SELECT rule_id FROM section_rules) "
            "AND r.id NOT IN (SELECT rule_id FROM chapter_rules) "
            "ORDER BY r.rule_num"
        ).fetchall()
        for r in rows:
            issues.append(f"ORPHANED RULE: #{r[0]} {r[1]} not linked to any section or chapter")

        # 7. Glossary terms without chapter_id
        rows = conn.execute(
            "SELECT term FROM glossary WHERE chapter_id IS NULL ORDER BY term"
        ).fetchall()
        for r in rows:
            issues.append(f"GLOSSARY NO CHAPTER: '{r[0]}' has no chapter_id")

        if not issues:
            self.state["report"] = "All checks passed. No issues found."
        else:
            self.state["report"] = f"Found {len(issues)} issue(s):\n" + "\n".join(
                f"  {i+1}. {issue}" for i, issue in enumerate(issues)
            )

        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # ADD ANNOTATION — Highlight or note on a section
    # ------------------------------------------------------------------------
    # Method: AddAnnotation
    # Purpose: Save a user highlight or annotation note anchored to a section.
    #          The selected_text is stored so the highlight can be re-applied
    #          after page re-render. If note_text is provided, it's a note;
    #          if not, it's just a highlight.
    # Params:  params = {'section_id': int, 'selected_text': str,
    #                    'note_text': str, 'color': str}
    # Returns: Tuple3 (ok, annotation_id, error)
    # ------------------------------------------------------------------------
    def AddAnnotation(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")
        selected_text = self._p(params, "selected_text")
        note_text = self._p(params, "note_text", "")
        color = self._p(params, "color", "#fef08a")

        if section_id is None or selected_text is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: section_id, selected_text", 0))

        try:
            cur = conn.execute(
                "INSERT INTO annotations (section_id, selected_text, note_text, color) "
                "VALUES (?, ?, ?, ?)",
                (int(section_id), selected_text, note_text, color),
            )
            conn.commit()
            self.state["last_id"] = cur.lastrowid
            kind = "annotation" if note_text else "highlight"
            self.state["report"] = (
                f"Added {kind} #{cur.lastrowid} to section {section_id}: "
                f"\"{selected_text[:50]}...\""
            )
            self.CloseDB()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # LIST ANNOTATIONS — Show all highlights and notes
    # ------------------------------------------------------------------------
    # Method: ListAnnotations
    # Purpose: List all annotations with section/chapter context.
    #          Optionally filter by section_id.
    # Params:  params = {'section_id': int (optional filter)}
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def ListAnnotations(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        section_id = self._p(params, "section_id")

        if section_id is not None:
            rows = conn.execute(
                "SELECT a.id, a.section_id, a.selected_text, a.note_text, "
                "       a.color, a.created_at, s.sec_num, s.title, c.ch_num "
                "FROM annotations a "
                "JOIN sections s ON s.id = a.section_id "
                "JOIN chapters c ON c.id = s.chapter_id "
                "WHERE a.section_id = ? ORDER BY a.id",
                (int(section_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT a.id, a.section_id, a.selected_text, a.note_text, "
                "       a.color, a.created_at, s.sec_num, s.title, c.ch_num "
                "FROM annotations a "
                "JOIN sections s ON s.id = a.section_id "
                "JOIN chapters c ON c.id = s.chapter_id "
                "ORDER BY c.ch_num, s.sort_order, a.id"
            ).fetchall()

        if not rows:
            self.state["report"] = "No annotations found"
            self.CloseDB()
            return (1, self.state["report"], ())

        lines = []
        lines.append(f"{'ID':>4}  {'Ch':>3}  {'Section':<10}  {'Type':<6}  Text / Note")
        lines.append("-" * 90)
        for r in rows:
            kind = "note" if r[3] else "hl"
            text = r[3] if r[3] else r[2]
            lines.append(
                f"{r[0]:>4}  {r[8]:>3}  {r[6]:<10}  {kind:<6}  {text[:60]}"
            )

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # REMOVE ANNOTATION — Delete a highlight or note
    # ------------------------------------------------------------------------
    # Method: RemoveAnnotation
    # Purpose: Delete an annotation by id
    # Params:  params = {'annotation_id': int}
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def RemoveAnnotation(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        annotation_id = self._p(params, "annotation_id")
        if annotation_id is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: annotation_id", 0))

        try:
            conn.execute("DELETE FROM annotations WHERE id = ?", (int(annotation_id),))
            conn.commit()
            self.state["report"] = f"Removed annotation {annotation_id}"
            self.CloseDB()
            return (1, self.state["report"], ())
        except sqlite3.Error as e:
            self.CloseDB()
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # EXPORT CHAPTER — Markdown export via v_export_chapter view
    # ------------------------------------------------------------------------
    # Method: ExportChapter
    # Purpose: Assemble a chapter's sections + blocks into ordered markdown
    # Params:  params = {'ch_num': int}
    # Returns: Tuple3 (ok, markdown_string, error)
    # ------------------------------------------------------------------------
    def ExportChapter(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        ch_num = self._p(params, "ch_num")
        if ch_num is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: ch_num", 0))

        rows = conn.execute(
            "SELECT line FROM v_export_chapter WHERE ch_num = ? ORDER BY line_order",
            (int(ch_num),),
        ).fetchall()

        if not rows:
            self.CloseDB()
            return (0, None, ("NOTFOUND", f"No content for chapter {ch_num}", 0))

        lines = [row[0] for row in rows]
        markdown = "\n\n".join(lines)
        self.state["report"] = markdown
        self.CloseDB()
        return (1, markdown, ())

    # ------------------------------------------------------------------------
    # OUTLINE — Table of contents via v_chapter_outline view
    # ------------------------------------------------------------------------
    # Method: Outline
    # Purpose: Show chapter/section structure. If ch_num given, show one chapter.
    #          Otherwise show full TOC.
    # Params:  params = {'ch_num': int (optional)}
    # Returns: Tuple3 (ok, outline_string, error)
    # ------------------------------------------------------------------------
    def Outline(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        ch_num = self._p(params, "ch_num")

        if ch_num is not None:
            rows = conn.execute(
                "SELECT part_num, ch_num, sec_num, sec_title, section_type, "
                "       word_count, page_num "
                "FROM v_chapter_outline WHERE ch_num = ? ORDER BY sort_order",
                (int(ch_num),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT part_num, ch_num, sec_num, sec_title, section_type, "
                "       word_count, page_num "
                "FROM v_chapter_outline ORDER BY part_num, ch_num, sort_order"
            ).fetchall()

        if not rows:
            self.CloseDB()
            return (0, None, ("NOTFOUND", "No sections found", 0))

        lines = []
        current_part = None
        current_ch = None
        for r in rows:
            if r[0] != current_part:
                current_part = r[0]
                lines.append(f"\nPart {r[0]}")
                lines.append("=" * 40)
            if r[1] != current_ch:
                current_ch = r[1]
                lines.append(f"\n  Chapter {r[1]}")
                lines.append("-" * 40)
            page = f" p.{r[6]}" if r[6] else ""
            wc = f" ({r[5]}w)" if r[5] else ""
            lines.append(f"    {r[2]:>6}  {r[3]}  [{r[4]}]{wc}{page}")

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LIST RULES — All rules with coverage via v_rules_index
    # ------------------------------------------------------------------------
    # Method: ListRules
    # Purpose: Show all VBStyle rules with section/chapter coverage counts
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, rules_string, error)
    # ------------------------------------------------------------------------
    def ListRules(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        rows = conn.execute(
            "SELECT rule_num, tag, category, short_desc, primary_chapter, "
            "       section_count, chapter_count "
            "FROM v_rules_index ORDER BY rule_num"
        ).fetchall()

        if not rows:
            self.CloseDB()
            return (0, None, ("NOTFOUND", "No rules found", 0))

        lines = []
        lines.append(f"{'#':>3}  {'Tag':<20} {'Cat':<12} {'Ch':>3} {'Sec':>4}  Description")
        lines.append("-" * 90)
        for r in rows:
            ch = str(r[4]) if r[4] else "-"
            lines.append(
                f"{r[0]:>3}  {r[1]:<20} {r[2]:<12} {ch:>3} {r[5]:>4}  {r[3]}"
            )

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LIST GLOSSARY — All terms via v_glossary_index
    # ------------------------------------------------------------------------
    # Method: ListGlossary
    # Purpose: Show all glossary terms with first-appearance chapter
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, glossary_string, error)
    # ------------------------------------------------------------------------
    def ListGlossary(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        rows = conn.execute(
            "SELECT term, definition, first_chapter, chapter_title "
            "FROM v_glossary_index ORDER BY term"
        ).fetchall()

        if not rows:
            self.CloseDB()
            return (0, None, ("NOTFOUND", "No glossary terms found", 0))

        lines = []
        for r in rows:
            ch = f" (Ch {r[2]}: {r[3]})" if r[2] else ""
            lines.append(f"  {r[0]}{ch}")
            lines.append(f"    {r[1]}")
            lines.append("")

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LIST XREFS — All cross-references via v_cross_ref_graph
    # ------------------------------------------------------------------------
    # Method: ListXrefs
    # Purpose: Show all cross-references with resolved titles
    # Params:  params = {'ch_num': int (optional, filter by from-chapter)}
    # Returns: Tuple3 (ok, xrefs_string, error)
    # ------------------------------------------------------------------------
    def ListXrefs(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        ch_num = self._p(params, "ch_num")

        if ch_num is not None:
            rows = conn.execute(
                "SELECT from_ch_num, from_sec, from_section, "
                "       to_ch_num, to_chapter, to_sec, to_section, ref_text "
                "FROM v_cross_ref_graph WHERE from_ch_num = ? "
                "ORDER BY from_ch_num, from_sec",
                (int(ch_num),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT from_ch_num, from_sec, from_section, "
                "       to_ch_num, to_chapter, to_sec, to_section, ref_text "
                "FROM v_cross_ref_graph ORDER BY from_ch_num, from_sec"
            ).fetchall()

        if not rows:
            self.CloseDB()
            return (0, None, ("NOTFOUND", "No cross-references found", 0))

        lines = []
        for r in rows:
            to = f"Ch {r[3]}" if r[3] else "?"
            if r[5]:
                to += f" sec {r[5]}"
            lines.append(f"  Ch{r[0]} {r[1]} → {to}  | {r[7]}")

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # INFO — Chapter details: sections, rules, summary, word count
    # ------------------------------------------------------------------------
    # Method: Info
    # Purpose: Show detailed info about one chapter
    # Params:  params = {'ch_num': int}
    # Returns: Tuple3 (ok, info_string, error)
    # ------------------------------------------------------------------------
    def Info(self, params):
        ok, conn, err = self.OpenDB()
        if not ok:
            return (0, None, err)

        ch_num = self._p(params, "ch_num")
        if ch_num is None:
            self.CloseDB()
            return (0, None, ("BADCMD", "Need: ch_num", 0))

        ch = conn.execute(
            "SELECT c.id, c.title, c.subtitle, c.description, "
            "       (SELECT COUNT(*) FROM sections s WHERE s.chapter_id = c.id) as sec_count, "
            "       (SELECT SUM(word_count) FROM sections s WHERE s.chapter_id = c.id) as total_words, "
            "       (SELECT COUNT(*) FROM chapter_rules cr WHERE cr.chapter_id = c.id) as rule_count, "
            "       (SELECT COUNT(*) FROM content_blocks cb "
            "        JOIN sections s ON s.id = cb.section_id "
            "        WHERE s.chapter_id = c.id) as block_count "
            "FROM chapters c WHERE c.ch_num = ?",
            (int(ch_num),),
        ).fetchone()

        if not ch:
            self.CloseDB()
            return (0, None, ("NOTFOUND", f"Chapter {ch_num} not found", 0))

        summary = conn.execute(
            "SELECT summary FROM chapter_summaries WHERE chapter_id = ?", (ch[0],)
        ).fetchone()

        lines = []
        lines.append(f"Chapter {ch_num}: {ch[1]}")
        if ch[2]:
            lines.append(f"  Subtitle: {ch[2]}")
        lines.append(f"  Sections: {ch[4]}")
        lines.append(f"  Content blocks: {ch[7]}")
        lines.append(f"  Total words: {ch[5] or 0}")
        lines.append(f"  Rules covered: {ch[6]}")
        if summary:
            lines.append(f"  Summary: {summary[0][:100]}...")

        self.state["report"] = "\n".join(lines)
        self.CloseDB()
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # READ STATE — Config snapshot
    # ------------------------------------------------------------------------
    # Method: ReadState
    # Purpose: Return current state dict snapshot
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, state_dict, error)
    # Rule:    @rdst
    # ------------------------------------------------------------------------
    def ReadState(self, params):
        snapshot = {
            "db_path": self.state["db_path"],
            "schema_source": "config.py (Config.SCHEMA_SQL)",
            "db_connected": self.state["db"] is not None,
            "last_id": self.state["last_id"],
            "report_len": len(self.state["report"]),
        }
        self.state["report"] = "\n".join(
            f"  {k}: {v}" for k, v in snapshot.items()
        )
        return (1, snapshot, ())

    # ------------------------------------------------------------------------
    # REPORT — Return report string (no print)
    # ------------------------------------------------------------------------
    # Method: Report
    # Purpose: Return the last report string
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, report_string, error)
    # Rule:    @rpt
    # ------------------------------------------------------------------------
    def Report(self, params):
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # MSEARCH HELPER — Run msearch --json and parse results
    # ------------------------------------------------------------------------
    # Method: MsearchJson
    # Purpose: Run msearch binary with --json flag, return parsed results
    # Params:  term (str), table (str optional), limit (int optional),
    #          extra_args (list optional)
    # Returns: Tuple3 (ok, list_of_dicts, error)
    # ------------------------------------------------------------------------
    def MsearchJson(self, term, table=None, limit=None, extra_args=None):
        msearch = os.path.expanduser("~/bin/msearch")
        if not os.path.exists(msearch):
            return (0, None, ("NOTFOUND", "msearch binary not found at ~/bin/msearch", 0))

        cmd = [msearch, term, "--json"]
        if table:
            cmd.extend(["--table", table])
        if limit:
            cmd.extend(["--limit", str(limit)])
        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            return (0, None, ("TIMEOUT", "msearch timed out", 0))
        except Exception as e:
            return (0, None, ("EXEC", str(e), 0))

        if result.returncode != 0:
            return (0, None, ("MSEARCH", result.stderr.strip() or "msearch failed", 0))

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return (0, None, ("JSON", f"Failed to parse msearch output: {e}", 0))

        return (1, data, ())

    # ------------------------------------------------------------------------
    # SEARCH MYSQL — Search MySQL via msearch
    # ------------------------------------------------------------------------
    # Method: SearchMysql
    # Purpose: Search MySQL databases using msearch --json.
    #          Returns formatted results without touching book DB.
    # Params:  params = {'term': str, 'table': str (optional), 'limit': int (optional)}
    # Returns: Tuple3 (ok, results_string, error)
    # ------------------------------------------------------------------------
    def SearchMysql(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        table = self._p(params, "table")
        limit = self._p(params, "limit", 20)

        ok, data, err = self.MsearchJson(term, table=table, limit=limit)
        if not ok:
            return (0, None, err)

        lines = []
        total = 0
        for table_result in data:
            tname = table_result.get("table", "?")
            what = table_result.get("what", "")
            why = table_result.get("why", "")
            rows = table_result.get("rows", [])
            if not rows:
                continue
            lines.append(f"\n=== TABLE: {tname}")
            if what:
                lines.append(f"  WHAT: {what}")
            if why:
                lines.append(f"  WHY: {why}")
            for row in rows:
                total += 1
                parts = []
                for k, v in row.items():
                    if v and len(str(v)) > 100:
                        parts.append(f"{k}={str(v)[:100]}...")
                    else:
                        parts.append(f"{k}={v}")
                lines.append(f"  [{total}] {' | '.join(parts)}")

        if total == 0:
            self.state["report"] = f"No matches for '{term}' in MySQL."
        else:
            self.state["report"] = f"Found {total} match(es) for '{term}':\n" + "\n".join(lines)

        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # SEARCH CODE — Search code_classes + code_registry via msearch
    # ------------------------------------------------------------------------
    # Method: SearchCode
    # Purpose: Search MySQL code tables for code snippets by keyword.
    #          Returns class_name, description, and truncated code.
    # Params:  params = {'term': str, 'limit': int (optional)}
    # Returns: Tuple3 (ok, results_string, error)
    # ------------------------------------------------------------------------
    def SearchCode(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        limit = self._p(params, "limit", 10)

        ok, data, err = self.MsearchJson(term, table="code_classes", limit=limit, extra_args=["--dump"])
        if not ok:
            return (0, None, err)

        lines = []
        total = 0
        for table_result in data:
            tname = table_result.get("table", "?")
            rows = table_result.get("rows", [])
            if not rows:
                continue
            lines.append(f"\n=== TABLE: {tname}")
            for row in rows:
                total += 1
                name = row.get("class_name", row.get("token_name", "?"))
                desc = row.get("description", "")
                code = row.get("class_code", row.get("code", ""))
                snippet = code[:200].replace("\n", " ") if code else ""
                lines.append(f"  [{total}] {name}")
                if desc:
                    lines.append(f"       desc: {desc}")
                if snippet:
                    lines.append(f"       code: {snippet}...")

        if total == 0:
            self.state["report"] = f"No code matches for '{term}'."
        else:
            self.state["report"] = f"Found {total} code match(es) for '{term}':\n" + "\n".join(lines)

        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # POPULATE MYSQL — Import from MySQL into book DB via msearch
    # ------------------------------------------------------------------------
    # Method: PopulateMysql
    # Purpose: Query MySQL via msearch --json and populate book DB.
    #          Sources: rules, classes, registry, all
    #          - rules:     Import vb_shared.rules as book rules
    #          - classes:   Import vb_shared.code_classes as code blocks in new chapters
    #          - registry:  Import vb_shared.code_registry as code blocks
    #          - all:       Do all three
    # Params:  params = {'source': str, 'limit': int (optional)}
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def PopulateMysql(self, params):
        source = self._p(params, "source", "all")
        limit = self._p(params, "limit", 50)

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        stats = {"rules": 0, "classes": 0, "registry": 0, "sections": 0, "blocks": 0}

        # --- Import rules from vb_shared.rules ---
        if source in ("rules", "all"):
            ok, data, err = self.MsearchJson("rule", table="rules", limit=limit)
            if ok:
                for table_result in data:
                    if table_result.get("table") != "rules":
                        continue
                    for row in table_result.get("rows", []):
                        rule_text = row.get("rule", "")
                        desc = row.get("description", "")
                        cat = row.get("rule_category", "general")
                        sev = row.get("severity", "guideline")
                        rid = row.get("id")
                        if not rule_text:
                            continue
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO rules (rule_num, tag, category, short_desc) "
                                "VALUES (?, ?, ?, ?)",
                                (int(rid) if rid else 0, f"@mysql_{rid}", cat, f"{rule_text}: {desc}")
                            )
                            stats["rules"] += 1
                        except Exception:
                            pass

        # --- Import code_classes as chapters + code blocks ---
        if source in ("classes", "all"):
            ok, data, err = self.MsearchJson("dom_", table="code_classes", limit=limit, extra_args=["--dump"])
            if ok:
                # Find or create a part for code classes
                part_row = conn.execute(
                    "SELECT id FROM parts WHERE part_num = 5"
                ).fetchone()
                if not part_row:
                    cur = conn.execute(
                        "INSERT INTO parts (part_num, title, subtitle) VALUES (5, 'Code Library', 'Classes from MySQL')"
                    )
                    part_id = cur.lastrowid
                else:
                    part_id = part_row[0]

                # Find max ch_num to avoid collisions
                max_ch = conn.execute("SELECT MAX(ch_num) FROM chapters").fetchone()[0] or 0

                ch_num = max_ch + 1
                for table_result in data:
                    if table_result.get("table") != "code_classes":
                        continue
                    for row in table_result.get("rows", []):
                        class_name = row.get("class_name", "")
                        class_code = row.get("class_code", "")
                        desc = row.get("description", "")
                        if not class_name:
                            continue

                        # Create a chapter for each class
                        cur = conn.execute(
                            "INSERT INTO chapters (part_id, ch_num, title, subtitle) "
                            "VALUES (?, ?, ?, ?)",
                            (part_id, ch_num, class_name, desc)
                        )
                        ch_id = cur.lastrowid

                        # Create a section
                        cur = conn.execute(
                            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                            "VALUES (?, '1.1', 1, 'Source Code', 'content')",
                            (ch_id,)
                        )
                        sec_id = cur.lastrowid
                        stats["sections"] += 1

                        # Add code as a code block
                        if class_code:
                            conn.execute(
                                "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
                                "VALUES (?, 'code', 1, ?, 'python')",
                                (sec_id, class_code)
                            )
                            stats["blocks"] += 1

                        # Add description as text block
                        if desc:
                            conn.execute(
                                "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
                                "VALUES (?, 'text', 2, ?, NULL)",
                                (sec_id, desc)
                            )
                            stats["blocks"] += 1

                        stats["classes"] += 1
                        ch_num += 1

        # --- Import code_registry as code blocks ---
        if source in ("registry", "all"):
            ok, data, err = self.MsearchJson("python", table="code_registry", limit=limit)
            if ok:
                # Find or create a part for code registry
                part_row = conn.execute(
                    "SELECT id FROM parts WHERE part_num = 6"
                ).fetchone()
                if not part_row:
                    cur = conn.execute(
                        "INSERT INTO parts (part_num, title, subtitle) VALUES (6, 'Code Snippets', 'Registry from MySQL')"
                    )
                    reg_part_id = cur.lastrowid
                else:
                    reg_part_id = part_row[0]

                max_ch = conn.execute("SELECT MAX(ch_num) FROM chapters").fetchone()[0] or 0
                ch_num = max_ch + 1

                for table_result in data:
                    if table_result.get("table") != "code_registry":
                        continue
                    for row in table_result.get("rows", []):
                        token_name = row.get("token_name", "")
                        code = row.get("code", "")
                        lang = row.get("language", "python")
                        desc = row.get("description", "")
                        if not token_name:
                            continue

                        # Create a chapter for each snippet
                        cur = conn.execute(
                            "INSERT INTO chapters (part_id, ch_num, title, subtitle) "
                            "VALUES (?, ?, ?, ?)",
                            (reg_part_id, ch_num, token_name, desc)
                        )
                        ch_id = cur.lastrowid

                        cur = conn.execute(
                            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                            "VALUES (?, '1.1', 1, 'Source Code', 'content')",
                            (ch_id,)
                        )
                        sec_id = cur.lastrowid
                        stats["sections"] += 1

                        if code:
                            conn.execute(
                                "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
                                "VALUES (?, 'code', 1, ?, ?)",
                                (sec_id, code, lang)
                            )
                            stats["blocks"] += 1

                        stats["registry"] += 1
                        ch_num += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Populated from MySQL: "
            f"{stats['rules']} rules, "
            f"{stats['classes']} classes, "
            f"{stats['registry']} registry items, "
            f"{stats['sections']} sections, "
            f"{stats['blocks']} content blocks"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # SEARCH DOCS — Search vbstyle_documents database via msearch
    # ------------------------------------------------------------------------
    # Method: SearchDocs
    # Purpose: Search the vbstyle_documents MySQL database using msearch
    #          with --db vbstyle_documents --json. This DB contains
    #          markdown_files, json_files, yaml_files, classifications,
    #          patterns, tokens, and more.
    # Params:  params = {'term': str, 'table': str (optional), 'limit': int}
    # Returns: Tuple3 (ok, results_string, error)
    # ------------------------------------------------------------------------
    def SearchDocs(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        table = self._p(params, "table")
        limit = self._p(params, "limit", 20)

        ok, data, err = self.MsearchJson(
            term, table=table, limit=limit,
            extra_args=["--db", "vbstyle_documents"]
        )
        if not ok:
            return (0, None, err)

        lines = []
        total = 0
        for table_result in data:
            tname = table_result.get("table", "?")
            what = table_result.get("what", "")
            why = table_result.get("why", "")
            rows = table_result.get("rows", [])
            if not rows:
                continue
            lines.append(f"\n=== TABLE: {tname}")
            if what:
                lines.append(f"  WHAT: {what}")
            if why:
                lines.append(f"  WHY: {why}")
            for row in rows:
                total += 1
                parts = []
                for k, v in row.items():
                    if v and len(str(v)) > 100:
                        parts.append(f"{k}={str(v)[:100]}...")
                    else:
                        parts.append(f"{k}={v}")
                lines.append(f"  [{total}] {' | '.join(parts)}")

        if total == 0:
            self.state["report"] = f"No doc matches for '{term}' in vbstyle_documents."
        else:
            self.state["report"] = (
                f"Found {total} doc match(es) for '{term}':\n"
                + "\n".join(lines)
            )
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # CROSS QUERY — Search across all databases and present linked results
    # ------------------------------------------------------------------------
    # Method: CrossQuery
    # Purpose: Cross-query multiple MySQL databases for a term via msearch.
    #          Searches:
    #            1. vb_shared.rules        — VBStyle rules
    #            2. vb_shared.code_classes  — Code implementations
    #            3. vb_shared.instructions  — Model instructions
    #            4. vbstyle_documents      — Documentation files
    #            5. Book DB (local)        — Existing book content
    #          Results are grouped by source and cross-referenced.
    # Params:  params = {'term': str, 'limit': int (optional)}
    # Returns: Tuple3 (ok, results_string, error)
    # ------------------------------------------------------------------------
    def CrossQuery(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        limit = self._p(params, "limit", 10)
        sections = []

        # 1. vb_shared.rules
        ok, data, err = self.MsearchJson(term, table="rules", limit=limit)
        if ok:
            rows = []
            for t in data:
                if t.get("table") == "rules":
                    for r in t.get("rows", []):
                        rows.append({
                            "id": r.get("id", ""),
                            "rule": r.get("rule", "")[:80],
                            "desc": r.get("description", "")[:80],
                            "cat": r.get("rule_category", ""),
                        })
            if rows:
                sections.append(("RULES (vb_shared)", rows))

        # 2. vb_shared.code_classes
        ok, data, err = self.MsearchJson(term, table="code_classes", limit=limit)
        if ok:
            rows = []
            for t in data:
                if t.get("table") == "code_classes":
                    for r in t.get("rows", []):
                        rows.append({
                            "class": r.get("class_name", ""),
                            "desc": r.get("description", "")[:80],
                        })
            if rows:
                sections.append(("CODE CLASSES (vb_shared)", rows))

        # 3. vb_shared.instructions
        ok, data, err = self.MsearchJson(term, table="instructions", limit=limit)
        if ok:
            rows = []
            for t in data:
                if t.get("table") == "instructions":
                    for r in t.get("rows", []):
                        rows.append({
                            "name": r.get("instruction_name", ""),
                            "cat": r.get("category", ""),
                            "body": r.get("instruction_body", "")[:100],
                        })
            if rows:
                sections.append(("INSTRUCTIONS (vb_shared)", rows))

        # 4. vbstyle_documents
        ok, data, err = self.MsearchJson(
            term, limit=limit,
            extra_args=["--db", "vbstyle_documents"]
        )
        if ok:
            rows = []
            for t in data:
                tname = t.get("table", "")
                for r in t.get("rows", []):
                    if tname == "markdown_files":
                        rows.append({
                            "file": r.get("file_name", ""),
                            "content": r.get("content", "")[:100],
                        })
                    elif tname == "classifications":
                        rows.append({
                            "name": r.get("name", ""),
                            "desc": r.get("description", ""),
                        })
            if rows:
                sections.append(("DOCUMENTATION (vbstyle_documents)", rows))

        # 5. Book DB (local)
        ok_db, conn, db_err = self.OpenDB()
        if ok_db:
            pattern = f"%{term}%"
            book_rows = []
            for r in conn.execute(
                "SELECT s.title, c.ch_num, c.title FROM sections s "
                "JOIN chapters c ON c.id = s.chapter_id "
                "WHERE s.title LIKE ? LIMIT 5", (pattern,)
            ).fetchall():
                book_rows.append({
                    "type": "section", "ch": r[1],
                    "title": r[0], "in": r[2],
                })
            for r in conn.execute(
                "SELECT cb.content, s.title, c.ch_num FROM content_blocks cb "
                "JOIN sections s ON s.id = cb.section_id "
                "JOIN chapters c ON c.id = s.chapter_id "
                "WHERE cb.content LIKE ? LIMIT 5", (pattern,)
            ).fetchall():
                book_rows.append({
                    "type": "block", "ch": r[2],
                    "in": r[1], "snippet": r[0][:80],
                })
            for r in conn.execute(
                "SELECT term, definition FROM glossary "
                "WHERE term LIKE ? OR definition LIKE ? LIMIT 5",
                (pattern, pattern)
            ).fetchall():
                book_rows.append({
                    "type": "glossary", "term": r[0], "def": r[1][:80],
                })
            for r in conn.execute(
                "SELECT rule_num, tag, short_desc FROM rules "
                "WHERE tag LIKE ? OR short_desc LIKE ? LIMIT 5",
                (pattern, pattern)
            ).fetchall():
                book_rows.append({
                    "type": "rule", "num": r[0],
                    "tag": r[1], "desc": r[2][:80],
                })
            if book_rows:
                sections.append(("BOOK DB (local)", book_rows))
            self.CloseDB()

        # Format output
        lines = [f"CROSS-QUERY RESULTS FOR: '{term}'"]
        lines.append("=" * 60)
        total = 0
        for title, rows in sections:
            lines.append(f"\n--- {title} ({len(rows)} matches) ---")
            for row in rows:
                total += 1
                parts = []
                for k, v in row.items():
                    parts.append(f"{k}={v}")
                lines.append(f"  [{total}] {' | '.join(parts)}")

        if total == 0:
            self.state["report"] = (
                f"No cross-query matches for '{term}' across all sources."
            )
        else:
            lines.append(
                f"\nTOTAL: {total} matches across {len(sections)} source(s)"
            )
            self.state["report"] = "\n".join(lines)
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LINK CONTENT — Find related content across all sources, link into book
    # ------------------------------------------------------------------------
    # Method: LinkContent
    # Purpose: Cross-query MySQL databases for a term via msearch, then
    #          create cross_refs and glossary entries in the book DB.
    #          - Adds missing glossary terms (definition from MySQL sources)
    #          - Creates cross-references between matching book sections
    #          - Links rules to sections that reference the term
    # Params:  params = {'term': str, 'limit': int (optional)}
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def LinkContent(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        limit = self._p(params, "limit", 10)
        stats = {"glossary": 0, "xrefs": 0, "rule_links": 0, "docs_found": 0}

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        pattern = f"%{term}%"

        # 1. Find matching sections in book DB
        book_sections = conn.execute(
            "SELECT s.id, s.title, c.ch_num, c.id FROM sections s "
            "JOIN chapters c ON c.id = s.chapter_id "
            "WHERE s.title LIKE ? OR EXISTS ("
            "  SELECT 1 FROM content_blocks cb "
            "  WHERE cb.section_id = s.id AND cb.content LIKE ?"
            ") LIMIT 20",
            (pattern, pattern)
        ).fetchall()

        # 2. Find matching rules in book DB
        book_rules = conn.execute(
            "SELECT id, rule_num, tag, short_desc FROM rules "
            "WHERE tag LIKE ? OR short_desc LIKE ?",
            (pattern, pattern)
        ).fetchall()

        # 3. Search vb_shared.rules via msearch
        mysql_rules = []
        ok, data, err = self.MsearchJson(term, table="rules", limit=limit)
        if ok:
            for t in data:
                if t.get("table") == "rules":
                    mysql_rules = t.get("rows", [])
                    break

        # 4. Search vbstyle_documents via msearch
        mysql_docs = []
        ok, data, err = self.MsearchJson(
            term, limit=limit,
            extra_args=["--db", "vbstyle_documents"]
        )
        if ok:
            for t in data:
                if t.get("table") == "markdown_files":
                    mysql_docs = t.get("rows", [])
                    break

        # 5. Search vb_shared.code_classes via msearch
        mysql_classes = []
        ok, data, err = self.MsearchJson(term, table="code_classes", limit=limit)
        if ok:
            for t in data:
                if t.get("table") == "code_classes":
                    mysql_classes = t.get("rows", [])
                    break

        # --- Add glossary term if not exists ---
        existing = conn.execute(
            "SELECT id FROM glossary WHERE term = ?", (term,)
        ).fetchone()
        if not existing:
            def_parts = []
            if mysql_rules:
                def_parts.append(
                    f"VBStyle rule: {mysql_rules[0].get('rule', '')}"
                )
            if mysql_classes:
                def_parts.append(
                    f"Code class: {mysql_classes[0].get('class_name', '')}"
                )
            if mysql_docs:
                def_parts.append(
                    f"Documented in: {mysql_docs[0].get('file_name', '')}"
                )
            definition = (
                " | ".join(def_parts) if def_parts else f"Term: {term}"
            )
            ch_id = book_sections[0][3] if book_sections else None
            conn.execute(
                "INSERT INTO glossary (term, definition, chapter_id) "
                "VALUES (?, ?, ?)",
                (term, definition[:500], ch_id)
            )
            stats["glossary"] += 1

        # --- Create cross-references between matching sections ---
        if len(book_sections) >= 2:
            for i in range(len(book_sections) - 1):
                from_sec = book_sections[i][0]
                to_ch = book_sections[i + 1][2]
                ref_text = (
                    f"Related: '{term}' — see Ch{book_sections[i+1][2]} "
                    f"{book_sections[i+1][1]}"
                )
                try:
                    conn.execute(
                        "INSERT INTO cross_refs "
                        "(from_section, to_chapter, ref_text) "
                        "VALUES (?, ?, ?)",
                        (from_sec, to_ch, ref_text)
                    )
                    stats["xrefs"] += 1
                except Exception:
                    pass

        # --- Link rules to matching sections ---
        for rule in book_rules:
            rule_id = rule[0]
            for sec in book_sections:
                sec_id = sec[0]
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO section_rules "
                        "(section_id, rule_id) VALUES (?, ?)",
                        (sec_id, rule_id)
                    )
                    stats["rule_links"] += 1
                except Exception:
                    pass

        stats["docs_found"] = (
            len(mysql_docs) + len(mysql_rules) + len(mysql_classes)
        )

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Linked content for '{term}': "
            f"{stats['glossary']} glossary added, "
            f"{stats['xrefs']} cross-refs created, "
            f"{stats['rule_links']} rule-section links, "
            f"{stats['docs_found']} MySQL sources found"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # FIX SUMMARIES — Auto-generate missing chapter summaries
    # ------------------------------------------------------------------------
    # Method: FixSummaries
    # Purpose: Find chapters without summaries, generate one from the first
    #          content block of the first section in each chapter.
    #          For code class chapters, use the class description from msearch.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def FixSummaries(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        stats = {"fixed": 0, "skipped": 0}

        chapters = conn.execute(
            "SELECT c.id, c.ch_num, c.title "
            "FROM chapters c "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM chapter_summaries cs WHERE cs.chapter_id = c.id"
            ") ORDER BY c.ch_num"
        ).fetchall()

        for ch in chapters:
            ch_id, ch_num, ch_title = ch

            # Get first content block from first section
            block = conn.execute(
                "SELECT cb.content FROM content_blocks cb "
                "JOIN sections s ON s.id = cb.section_id "
                "WHERE s.chapter_id = ? "
                "ORDER BY s.sort_order, cb.block_order LIMIT 1",
                (ch_id,)
            ).fetchone()

            if block and block[0]:
                content = block[0]
                # Generate summary from first 200 chars of content
                clean = content.replace("```", "").replace("#", "").strip()
                summary = clean[:200].rsplit(" ", 0)[0]
                if len(clean) > 200:
                    summary += "..."
            else:
                # No content blocks — use chapter title
                summary = f"{ch_title} — no content available."

            try:
                conn.execute(
                    "INSERT INTO chapter_summaries (chapter_id, summary) "
                    "VALUES (?, ?)",
                    (ch_id, summary)
                )
                stats["fixed"] += 1
            except Exception:
                stats["skipped"] += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Fixed summaries: {stats['fixed']} added, "
            f"{stats['skipped']} skipped"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # FIX GLOSSARY — Assign chapter_id to orphaned glossary terms
    # ------------------------------------------------------------------------
    # Method: FixGlossary
    # Purpose: Find glossary terms with no chapter_id, search the book DB
    #          for sections that mention the term, and assign the chapter.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def FixGlossary(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        stats = {"fixed": 0, "skipped": 0}

        orphans = conn.execute(
            "SELECT id, term, definition FROM glossary "
            "WHERE chapter_id IS NULL"
        ).fetchall()

        for g in orphans:
            g_id, term, definition = g
            pattern = f"%{term}%"

            # Find a section whose content mentions this term
            match = conn.execute(
                "SELECT s.chapter_id FROM sections s "
                "JOIN content_blocks cb ON cb.section_id = s.id "
                "WHERE cb.content LIKE ? "
                "OR s.title LIKE ? LIMIT 1",
                (pattern, pattern)
            ).fetchone()

            if match and match[0]:
                conn.execute(
                    "UPDATE glossary SET chapter_id = ? WHERE id = ?",
                    (match[0], g_id)
                )
                stats["fixed"] += 1
            else:
                # Assign to first chapter as fallback
                first_ch = conn.execute(
                    "SELECT id FROM chapters ORDER BY ch_num LIMIT 1"
                ).fetchone()
                if first_ch:
                    conn.execute(
                        "UPDATE glossary SET chapter_id = ? WHERE id = ?",
                        (first_ch[0], g_id)
                    )
                    stats["fixed"] += 1
                else:
                    stats["skipped"] += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Fixed glossary: {stats['fixed']} assigned, "
            f"{stats['skipped']} skipped"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # FIX NAMES — Rename hash-named chapters to human-readable names
    # ------------------------------------------------------------------------
    # Method: FixNames
    # Purpose: Find chapters with names like 'file_00000000...' and rename
    #          them using the content of their first section/block.
    #          Uses msearch to look up better names when possible.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def FixNames(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        stats = {"fixed": 0, "skipped": 0}

        # Find chapters with hash-like names
        hash_chapters = conn.execute(
            "SELECT id, ch_num, title FROM chapters "
            "WHERE title LIKE 'file_%' OR title LIKE 'Pasted %'"
        ).fetchall()

        for ch in hash_chapters:
            ch_id, ch_num, ch_title = ch

            # Get first content block to find a better name
            block = conn.execute(
                "SELECT cb.content FROM content_blocks cb "
                "JOIN sections s ON s.id = cb.section_id "
                "WHERE s.chapter_id = ? "
                "ORDER BY s.sort_order, cb.block_order LIMIT 1",
                (ch_id,)
            ).fetchone()

            new_name = None
            if block and block[0]:
                content = block[0]
                # Look for class_name or file name in content
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("#[@GHOST]") or line.startswith("#[@VBSTYLE]"):
                        # Extract file name from ghost header
                        if "@file<" in line:
                            start = line.find("@file<") + 6
                            end = line.find(">", start)
                            if end > start:
                                fname = line[start:end]
                                new_name = fname.replace(".py", "").replace(".c", "")
                                break
                    elif line.startswith("class ") and ":" in line:
                        new_name = line.split("class ")[1].split(":")[0].strip()
                        break
                    elif line.startswith("def ") and ":" in line:
                        new_name = line.split("def ")[1].split("(")[0].strip()
                        break

            if new_name and len(new_name) > 2:
                conn.execute(
                    "UPDATE chapters SET title = ? WHERE id = ?",
                    (new_name, ch_id)
                )
                stats["fixed"] += 1
            else:
                stats["skipped"] += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Fixed names: {stats['fixed']} renamed, "
            f"{stats['skipped']} skipped"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # POPULATE MILESTONES — Extract discoveries from MySQL, write as book content
    # ------------------------------------------------------------------------
    # Method: PopulateMilestones
    # Purpose: Search instructions and learned_rules via msearch for
    #          high-signal discoveries — architecture decisions, lessons
    #          mined from failures, constraints that survived discussion.
    #          Write each as a chapter under a new "Milestones & Discoveries"
    #          part, with narrative content explaining the milestone.
    # Params:  params = {'limit': int (optional, default 30)}
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def PopulateMilestones(self, params):
        limit = self._p(params, "limit", 30)
        stats = {"chapters": 0, "sections": 0, "blocks": 0, "skipped": 0, "tiers": 0}

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        # --- Ensure knowledge_tiers table exists ---
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        # --- Evidence table: stores raw data separate from presentation ---
        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_evidence ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  raw_data TEXT,"
            "  evidence_type TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  violation_count INTEGER DEFAULT 0,"
            "  first_seen TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        # --- Relations table: tracks milestone-to-milestone relationships ---
        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_relations ("
            "  from_chapter_id INTEGER,"
            "  to_chapter_id INTEGER,"
            "  relationship TEXT NOT NULL,"
            "  strength REAL DEFAULT 1.0,"
            "  discovered_at TEXT,"
            "  PRIMARY KEY (from_chapter_id, to_chapter_id, relationship),"
            "  FOREIGN KEY(from_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,"
            "  FOREIGN KEY(to_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.commit()

        # --- Ensure Part 7 exists ---
        part = conn.execute(
            "SELECT id FROM parts WHERE part_num = 7"
        ).fetchone()
        if not part:
            conn.execute(
                "INSERT INTO parts (part_num, title, subtitle, description) "
                "VALUES (7, 'Milestones & Discoveries', "
                "'Architecture decisions and lessons that survived discussion', "
                "'Content extracted from MySQL instructions and learned_rules via msearch')"
            )
            conn.commit()
            part = conn.execute(
                "SELECT id FROM parts WHERE part_num = 7"
            ).fetchone()
        part_id = part[0]

        # --- Get next ch_num ---
        max_ch = conn.execute(
            "SELECT MAX(ch_num) FROM chapters"
        ).fetchone()[0] or 0
        ch_num = max_ch + 1

        # --- 1. Search instructions via msearch ---
        # These are architecture decisions — things that became truth
        ok, data, err = self.MsearchJson(
            "architecture", table="instructions", limit=limit,
            extra_args=["--dump"]
        )

        milestones = []
        if ok:
            for t in data:
                if t.get("table") != "instructions":
                    continue
                for r in t.get("rows", []):
                    name = r.get("instruction_name", "")
                    body = r.get("instruction_body", "")
                    cat = r.get("category", "")
                    pri = r.get("priority", "1")
                    if not name or not body:
                        continue
                    # Skip if already exists
                    existing = conn.execute(
                        "SELECT id FROM chapters WHERE title = ? AND part_id = ?",
                        (name, part_id)
                    ).fetchone()
                    if existing:
                        stats["skipped"] += 1
                        continue
                    milestones.append({
                        "type": "instruction",
                        "name": name,
                        "body": body,
                        "category": cat,
                        "priority": pri,
                        "source_id": r.get("id", ""),
                    })

        # --- 2. Search learned_rules via msearch for high-confidence discoveries ---
        for search_term in ["Tuple3", "dispatch", "error", "config", "rule"]:
            ok, data, err = self.MsearchJson(
                search_term, table="learned_rules", limit=limit
            )
            if not ok:
                continue
            for t in data:
                if t.get("table") != "learned_rules":
                    continue
                for r in t.get("rows", []):
                    conf = float(r.get("confidence", "0"))
                    succ = int(r.get("success_count", "0"))
                    if conf < 0.7 or succ < 1:
                        continue
                    pattern = r.get("pattern", "")
                    if not pattern:
                        continue
                    # Create a milestone name from the pattern
                    name = pattern[:60].replace(" ", "_").replace(":", "")
                    # Skip if already exists
                    existing = conn.execute(
                        "SELECT id FROM chapters WHERE title = ? AND part_id = ?",
                        (name, part_id)
                    ).fetchone()
                    if existing:
                        stats["skipped"] += 1
                        continue
                    milestones.append({
                        "type": "learned_rule",
                        "name": name,
                        "pattern": pattern,
                        "trigger": r.get("trigger_condition", ""),
                        "fix": r.get("fix_action", ""),
                        "confidence": conf,
                        "success_count": succ,
                        "source": r.get("source", ""),
                        "source_id": r.get("id", ""),
                        "category": r.get("category", ""),
                    })

        # --- 3. Write milestones into book ---
        for m in milestones:
            if m["type"] == "instruction":
                title = m["name"]
                # Build narrative content
                body = m["body"]
                # Extract the bracket content if present
                if body.startswith("[@"):
                    # Clean up bracket notation for readability
                    clean = body.replace("\"", "").replace(";", "\n")
                    clean = clean.replace("[@", "\n[@").strip()
                else:
                    clean = body

                desc = f"Architecture decision — {m['category']}"
                if m["priority"] == "0":
                    desc += " (core principle)"

                # Create chapter
                conn.execute(
                    "INSERT INTO chapters (part_id, ch_num, title, description) "
                    "VALUES (?, ?, ?, ?)",
                    (part_id, ch_num, title, desc)
                )
                ch_id = conn.execute(
                    "SELECT id FROM chapters WHERE part_id = ? AND ch_num = ?",
                    (part_id, ch_num)
                ).fetchone()[0]
                stats["chapters"] += 1

                # Create section
                sec_num = "1.1"
                conn.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type, word_count) "
                    "VALUES (?, ?, 1, ?, 'content', ?)",
                    (ch_id, sec_num, title, len(clean.split()))
                )
                sec_id = conn.execute(
                    "SELECT id FROM sections WHERE chapter_id = ? AND sec_num = ?",
                    (ch_id, sec_num)
                ).fetchone()[0]
                stats["sections"] += 1

                # Add content block with the cleaned instruction body
                conn.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
                    "VALUES (?, 'text', 1, ?, NULL)",
                    (sec_id, clean[:8000])
                )
                stats["blocks"] += 1

                # Store raw evidence separately for narrative generation
                conn.execute(
                    "INSERT OR REPLACE INTO milestone_evidence "
                    "(chapter_id, raw_data, evidence_type, source_table, source_id) "
                    "VALUES (?, ?, 'instruction', 'instructions', ?)",
                    (ch_id, body, m.get("source_id", ""))
                )

                # Assign tier based on priority
                tier = "promoted" if m["priority"] == "0" else "candidate"
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_tiers "
                    "(chapter_id, tier, source_table, source_id, confidence) "
                    "VALUES (?, ?, 'instructions', ?, NULL)",
                    (ch_id, tier, m.get("source_id", ""))
                )
                stats["tiers"] += 1

            elif m["type"] == "learned_rule":
                title = m["name"]
                # Build narrative
                narrative = (
                    f"**Discovery: {m['pattern']}**\n\n"
                    f"**Trigger:** {m['trigger']}\n\n"
                    f"**Fix:** {m['fix']}\n\n"
                    f"**Confidence:** {m['confidence']}"
                    f" (success count: {m['success_count']})\n\n"
                    f"**Source:** {m['source']}\n\n"
                    f"**Category:** {m['category']}\n"
                )

                desc = f"Learned rule — {m['category']} (conf={m['confidence']})"

                # Create chapter
                conn.execute(
                    "INSERT INTO chapters (part_id, ch_num, title, description) "
                    "VALUES (?, ?, ?, ?)",
                    (part_id, ch_num, title, desc)
                )
                ch_id = conn.execute(
                    "SELECT id FROM chapters WHERE part_id = ? AND ch_num = ?",
                    (part_id, ch_num)
                ).fetchone()[0]
                stats["chapters"] += 1

                # Create section
                conn.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type, word_count) "
                    "VALUES (?, ?, 1, ?, 'content', ?)",
                    (ch_id, "1.1", title, len(narrative.split()))
                )
                sec_id = conn.execute(
                    "SELECT id FROM sections WHERE chapter_id = ? AND sec_num = ?",
                    (ch_id, "1.1")
                ).fetchone()[0]
                stats["sections"] += 1

                # Add content block with clean structured data
                conn.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
                    "VALUES (?, 'text', 1, ?, NULL)",
                    (sec_id, narrative)
                )
                stats["blocks"] += 1

                # Store raw evidence separately for narrative generation
                raw_rule = (
                    f"Pattern: {m['pattern']}\n"
                    f"Trigger: {m['trigger']}\n"
                    f"Fix: {m['fix']}\n"
                    f"Confidence: {m['confidence']}\n"
                    f"Success Count: {m['success_count']}\n"
                    f"Source: {m['source']}\n"
                    f"Category: {m['category']}"
                )
                conn.execute(
                    "INSERT OR REPLACE INTO milestone_evidence "
                    "(chapter_id, raw_data, evidence_type, source_table, source_id, confidence) "
                    "VALUES (?, ?, 'learned_rule', 'learned_rules', ?, ?)",
                    (ch_id, raw_rule, m.get("source_id", ""), m["confidence"])
                )

                # Assign tier based on confidence and success count
                if m["confidence"] >= 0.9 and m["success_count"] >= 5:
                    tier = "promoted"
                elif m["confidence"] >= 0.8:
                    tier = "candidate"
                else:
                    tier = "evidence"
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_tiers "
                    "(chapter_id, tier, source_table, source_id, confidence) "
                    "VALUES (?, ?, 'learned_rules', ?, ?)",
                    (ch_id, tier, m.get("source_id", ""), m["confidence"])
                )
                stats["tiers"] += 1

            ch_num += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Populated milestones: "
            f"{stats['chapters']} chapters, "
            f"{stats['sections']} sections, "
            f"{stats['blocks']} content blocks, "
            f"{stats['tiers']} tiers assigned, "
            f"{stats['skipped']} skipped (already exist)"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # PROMOTE — Move a milestone to a higher knowledge tier
    # ------------------------------------------------------------------------
    # Method: Promote
    # Purpose: Promote a chapter's knowledge tier. When promoting to
    #          'authoritative', also links the milestone to the rules table
    #          and adds key terms to glossary.
    # Params:  params = {'ch_num': int, 'tier': str}
    #          tier: evidence, candidate, promoted, authoritative
    # Returns: Tuple3 (ok, message, error)
    # ------------------------------------------------------------------------
    def Promote(self, params):
        ch_num = self._p(params, "ch_num")
        tier = self._p(params, "tier")
        owner = self._p(params, "owner")
        if ch_num is None or tier is None:
            return (0, None, ("BADCMD", "Need: ch_num, tier", 0))

        valid_tiers = ("evidence", "candidate", "promoted", "authoritative")
        if tier not in valid_tiers:
            return (0, None, ("BADCMD", f"Invalid tier. Use: {', '.join(valid_tiers)}", 0))

        # Authoritative tier requires an owner
        if tier == "authoritative" and not owner:
            return (0, None, ("BADCMD", "Authoritative tier requires an owner domain. Use: promote <ch_num> authoritative <owner>", 0))

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        # Ensure tables exist
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS authority_domains ("
            "  name TEXT PRIMARY KEY,"
            "  description TEXT,"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )

        # Register owner domain if provided
        if owner:
            conn.execute(
                "INSERT OR IGNORE INTO authority_domains (name) VALUES (?)",
                (owner,)
            )

        ch = conn.execute(
            "SELECT id, title, description FROM chapters WHERE ch_num = ?",
            (int(ch_num),)
        ).fetchone()
        if not ch:
            self.CloseDB()
            return (0, None, ("NOTFOUND", f"Chapter {ch_num} not found", 0))

        ch_id, ch_title, ch_desc = ch["id"], ch["title"], ch["description"]

        # Ensure knowledge_tiers table exists
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS authority_domains ("
            "  name TEXT PRIMARY KEY,"
            "  description TEXT,"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )

        # Update tier with owner
        if owner:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_tiers (chapter_id, tier, owner, promoted_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (ch_id, tier, owner)
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_tiers (chapter_id, tier, promoted_at) "
                "VALUES (?, ?, datetime('now'))",
                (ch_id, tier)
            )

        side_effects = []

        # When promoting to authoritative, link to rules and glossary
        if tier == "authoritative":
            # Add to glossary if not exists
            existing = conn.execute(
                "SELECT id FROM glossary WHERE term = ?", (ch_title,)
            ).fetchone()
            if not existing:
                # Get first content block for definition
                block = conn.execute(
                    "SELECT cb.content FROM content_blocks cb "
                    "JOIN sections s ON s.id = cb.section_id "
                    "WHERE s.chapter_id = ? "
                    "ORDER BY s.sort_order, cb.block_order LIMIT 1",
                    (ch_id,)
                ).fetchone()
                definition = block[0][:200] if block and block[0] else ch_desc or ch_title
                conn.execute(
                    "INSERT INTO glossary (term, definition, chapter_id) "
                    "VALUES (?, ?, ?)",
                    (ch_title, definition, ch_id)
                )
                side_effects.append("glossary term added")

            # Link to all sections that mention this title
            pattern = f"%{ch_title}%"
            sections = conn.execute(
                "SELECT s.id FROM sections s "
                "JOIN content_blocks cb ON cb.section_id = s.id "
                "WHERE cb.content LIKE ? AND s.chapter_id != ? "
                "LIMIT 20",
                (pattern, ch_id)
            ).fetchall()
            for sec in sections:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO cross_refs "
                        "(from_section, to_chapter, ref_text) "
                        "VALUES (?, ?, ?)",
                        (sec["id"], ch_id, f"Authoritative: {ch_title}")
                    )
                except Exception:
                    pass
            if sections:
                side_effects.append(f"{len(sections)} cross-refs created")

        conn.commit()
        self.CloseDB()

        extra = f" ({', '.join(side_effects)})" if side_effects else ""
        owner_str = f" owner={owner}" if owner else ""
        self.state["report"] = (
            f"Promoted chapter {ch_num} '{ch_title}' to '{tier}'{owner_str}{extra}"
        )
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LIST AUTHORITIES — Show all authority domains and their milestones
    # ------------------------------------------------------------------------
    # Method: ListAuthorities
    # Purpose: List all registered authority domains with the milestones
    #          they own. Shows which domain governs which truths.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def ListAuthorities(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS authority_domains ("
            "  name TEXT PRIMARY KEY,"
            "  description TEXT,"
            "  created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )

        domains = conn.execute(
            "SELECT name, description FROM authority_domains ORDER BY name"
        ).fetchall()

        if not domains:
            self.CloseDB()
            self.state["report"] = (
                "No authority domains registered.\n"
                "Use: promote <ch_num> authoritative <owner>\n"
                "to create one."
            )
            return (1, self.state["report"], ())

        lines = ["AUTHORITY DOMAINS", "=" * 60]
        for d in domains:
            owned = conn.execute(
                "SELECT ch.ch_num, ch.title, kt.tier "
                "FROM knowledge_tiers kt "
                "JOIN chapters ch ON ch.id = kt.chapter_id "
                "WHERE kt.owner = ? ORDER BY kt.tier, ch.ch_num",
                (d["name"],)
            ).fetchall()
            desc = f" — {d['description']}" if d["description"] else ""
            lines.append(f"\n--- {d['name']}{desc} ({len(owned)} truths) ---")
            for o in owned:
                lines.append(f"  [{o['tier']}] Ch {o['ch_num']:>3}: {o['title'][:50]}")

        self.CloseDB()
        self.state["report"] = "\n".join(lines)
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # CHECK CONTRADICTIONS — Scan content against authoritative truths
    # ------------------------------------------------------------------------
    # Method: CheckContradictions
    # Purpose: For a given term, find all authoritative milestones that
    #          mention it, then scan all other content for potential
    #          contradictions — statements that conflict with the
    #          authoritative truth.
    # Params:  params = {'term': str}
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def CheckContradictions(self, params):
        term = self._p(params, "term")
        if term is None:
            return (0, None, ("BADCMD", "Need: term", 0))

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )

        # Find authoritative truths mentioning this term
        auth_truths = conn.execute(
            "SELECT ch.ch_num, ch.title, cb.content, kt.owner "
            "FROM knowledge_tiers kt "
            "JOIN chapters ch ON ch.id = kt.chapter_id "
            "JOIN sections s ON s.chapter_id = ch.id "
            "JOIN content_blocks cb ON cb.section_id = s.id "
            "WHERE kt.tier = 'authoritative' "
            "AND (ch.title LIKE ? OR cb.content LIKE ?)",
            (f"%{term}%", f"%{term}%")
        ).fetchall()

        if not auth_truths:
            self.CloseDB()
            self.state["report"] = (
                f"No authoritative truths found for '{term}'.\n"
                f"Promote a milestone first: promote <ch_num> authoritative <owner>"
            )
            return (1, self.state["report"], ())

        # Extract key claims from authoritative content
        # Look for constraint patterns: "must", "never", "always", "no ", "not "
        constraint_words = [
            "must", "never", "always", "no ", "not ",
            "required", "forbidden", "prohibited", "mandatory",
            "shall", "cannot", "don't"
        ]

        lines = [f"CONTRADICTION CHECK: '{term}'", "=" * 60]
        lines.append(f"\n{len(auth_truths)} authoritative truth(s) found:")
        for t in auth_truths:
            lines.append(f"  Ch {t['ch_num']}: {t['title']} (owner: {t['owner']})")

        # Extract constraints from authoritative content
        constraints = []
        for t in auth_truths:
            content = t["content"] or ""
            for line in content.split("\n"):
                line_lower = line.lower()
                if any(w in line_lower for w in constraint_words) and term.lower() in line_lower:
                    constraints.append((t["ch_num"], t["title"], t["owner"], line.strip()[:120]))

        if constraints:
            lines.append(f"\n--- CONSTRAINTS ({len(constraints)}) ---")
            for ch_num, title, owner, line in constraints:
                lines.append(f"  [Ch {ch_num} | {owner}] {line}")

        # Scan non-authoritative content for contradictions
        # Look for negation of the same constraints
        contradictions = []
        pattern = f"%{term}%"
        candidates = conn.execute(
            "SELECT ch.ch_num, ch.title, cb.content, kt.tier "
            "FROM content_blocks cb "
            "JOIN sections s ON s.id = cb.section_id "
            "JOIN chapters ch ON ch.id = s.chapter_id "
            "LEFT JOIN knowledge_tiers kt ON kt.chapter_id = ch.id "
            "WHERE cb.content LIKE ? "
            "AND (kt.tier IS NULL OR kt.tier != 'authoritative') "
            "LIMIT 50",
            (pattern,)
        ).fetchall()

        for c in candidates:
            content = c["content"] or ""
            for line in content.split("\n"):
                line_lower = line.lower()
                if term.lower() not in line_lower:
                    continue
                # Check for contradiction patterns
                contradiction_words = [
                    "should not", "don't need", "no need",
                    "not required", "optional", "unnecessary",
                    "can skip", "can ignore", "doesn't matter",
                    "not important", "not mandatory"
                ]
                if any(w in line_lower for w in contradiction_words):
                    contradictions.append(
                        (c["ch_num"], c["title"], c["tier"] or "untracked", line.strip()[:120])
                    )

        if contradictions:
            lines.append(f"\n--- POTENTIAL CONTRADICTIONS ({len(contradictions)}) ---")
            for ch_num, title, tier, line in contradictions:
                lines.append(f"  [Ch {ch_num} | {tier}] {line}")
            lines.append(
                f"\nWARNING: {len(contradictions)} potential contradiction(s) found.\n"
                "These statements may conflict with authoritative truths."
            )
        else:
            lines.append("\nNo contradictions found. All content aligns with authoritative truths.")

        self.CloseDB()
        self.state["report"] = "\n".join(lines)
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # LIST MILESTONES — Show milestones grouped by knowledge tier
    # ------------------------------------------------------------------------
    # Method: ListMilestones
    # Purpose: List milestone chapters with their tiers, optionally filtered.
    # Params:  params = {'tier': str (optional)}
    # Returns: Tuple3 (ok, report_string, error)
    # ------------------------------------------------------------------------
    def ListMilestones(self, params):
        tier_filter = self._p(params, "tier")

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )

        query = (
            "SELECT ch.ch_num, ch.title, ch.description, "
            "kt.tier, kt.confidence, kt.source_table, kt.owner, kt.promoted_at "
            "FROM chapters ch "
            "JOIN parts p ON p.id = ch.part_id "
            "LEFT JOIN knowledge_tiers kt ON kt.chapter_id = ch.id "
            "WHERE p.part_num = 7"
        )
        args = []
        if tier_filter:
            query += " AND kt.tier = ?"
            args.append(tier_filter)
        query += " ORDER BY kt.tier, ch.ch_num"

        rows = conn.execute(query, args).fetchall()
        self.CloseDB()

        if not rows:
            self.state["report"] = "No milestones found."
            return (1, self.state["report"], ())

        tiers = {"authoritative": [], "promoted": [], "candidate": [], "evidence": [], None: []}
        for r in rows:
            t = r["tier"] if r["tier"] else "untracked"
            tiers.setdefault(t, []).append(r)

        lines = ["MILESTONES BY TIER", "=" * 60]
        tier_order = ["authoritative", "promoted", "candidate", "evidence", "untracked"]
        for t in tier_order:
            items = tiers.get(t, [])
            if not items:
                continue
            lines.append(f"\n--- {t.upper()} ({len(items)}) ---")
            for r in items:
                conf = f" conf={r['confidence']}" if r["confidence"] else ""
                src = f" src={r['source_table']}" if r["source_table"] else ""
                owner = f" owner={r['owner']}" if r["owner"] else ""
                lines.append(f"  Ch {r['ch_num']:>3}: {r['title'][:50]}{conf}{src}{owner}")

        lines.append(f"\nTOTAL: {len(rows)} milestones")
        self.state["report"] = "\n".join(lines)
        return (1, self.state["report"], ())

    # ------------------------------------------------------------------------
    # WRITE NARRATIVE — Transform raw milestone data into readable book prose
    # ------------------------------------------------------------------------
    # Method: WriteNarrative
    # Purpose: Go through every Part 7 milestone chapter and replace its
    #          content blocks with proper narrative prose. The style depends
    #          on the tier: authoritative becomes principle/law, promoted
    #          becomes decision narrative, candidate becomes discovery
    #          narrative, evidence becomes observation.
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def WriteNarrative(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_tiers ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  tier TEXT NOT NULL DEFAULT 'candidate',"
            "  owner TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  promoted_at TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_evidence ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  raw_data TEXT,"
            "  evidence_type TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  violation_count INTEGER DEFAULT 0,"
            "  first_seen TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_relations ("
            "  from_chapter_id INTEGER,"
            "  to_chapter_id INTEGER,"
            "  relationship TEXT NOT NULL,"
            "  strength REAL DEFAULT 1.0,"
            "  discovered_at TEXT,"
            "  PRIMARY KEY (from_chapter_id, to_chapter_id, relationship),"
            "  FOREIGN KEY(from_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,"
            "  FOREIGN KEY(to_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )

        stats = {"written": 0, "skipped": 0}

        milestones = conn.execute(
            "SELECT ch.id, ch.ch_num, ch.title, ch.description, "
            "kt.tier, kt.owner, kt.confidence, kt.source_table, "
            "me.raw_data, me.evidence_type "
            "FROM chapters ch "
            "JOIN parts p ON p.id = ch.part_id "
            "LEFT JOIN knowledge_tiers kt ON kt.chapter_id = ch.id "
            "LEFT JOIN milestone_evidence me ON me.chapter_id = ch.id "
            "WHERE p.part_num = 7 "
            "ORDER BY ch.ch_num"
        ).fetchall()

        for m in milestones:
            ch_id = m["id"]
            title = m["title"]
            desc = m["description"] or ""
            tier = m["tier"] or "candidate"
            owner = m["owner"] or ""
            confidence = m["confidence"]
            source_table = m["source_table"] or ""
            raw_evidence = m["raw_data"] or ""

            if not raw_evidence:
                block = conn.execute(
                    "SELECT cb.content FROM content_blocks cb "
                    "JOIN sections s ON s.id = cb.section_id "
                    "WHERE s.chapter_id = ? ORDER BY cb.block_order LIMIT 1",
                    (ch_id,)
                ).fetchone()
                if block and block[0]:
                    raw_evidence = block[0]
                else:
                    stats["skipped"] += 1
                    continue

            narrative = self._GenerateNarrative(
                conn, ch_id, title, desc, tier, owner, confidence,
                source_table, raw_evidence
            )

            if not narrative:
                stats["skipped"] += 1
                continue

            block = conn.execute(
                "SELECT cb.id FROM content_blocks cb "
                "JOIN sections s ON s.id = cb.section_id "
                "WHERE s.chapter_id = ? ORDER BY cb.block_order LIMIT 1",
                (ch_id,)
            ).fetchone()

            if block:
                conn.execute(
                    "UPDATE content_blocks SET content = ? WHERE id = ?",
                    (narrative, block["id"])
                )
            else:
                sec = conn.execute(
                    "SELECT id FROM sections WHERE chapter_id = ? ORDER BY sort_order LIMIT 1",
                    (ch_id,)
                ).fetchone()
                if sec:
                    conn.execute(
                        "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                        "VALUES (?, 'text', 1, ?)",
                        (sec["id"], narrative)
                    )

            summary = narrative[:200].replace("\n", " ").strip()
            if len(narrative) > 200:
                summary += "..."
            conn.execute(
                "INSERT OR REPLACE INTO chapter_summaries (chapter_id, summary) "
                "VALUES (?, ?)",
                (ch_id, summary)
            )

            stats["written"] += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Wrote narrative: {stats['written']} chapters transformed, "
            f"{stats['skipped']} skipped"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # _GENERATE NARRATIVE — Convert raw milestone data into prose
    # ------------------------------------------------------------------------
    # Method: _GenerateNarrative
    # Purpose: Given milestone metadata and raw content, produce readable
    #          book prose. Style depends on tier.
    # Params:  title, desc, tier, owner, confidence, source_table, raw
    # Returns: str (narrative text)
    # ------------------------------------------------------------------------
    def _CleanEvidence(self, raw):
        """Clean raw evidence data for display without adding narrative boilerplate."""
        if not raw:
            return ""
        clean = raw

        # Phase 1: Try to find innermost raw data signatures
        if "[@" in clean and "]{(" in clean:
            idx = clean.rfind("[@")
            if idx >= 0:
                bracket = clean[idx:]
                close = bracket.rfind(")}")
                if close >= 0:
                    clean = bracket[:close + 2]
        elif "**Discovery:" in clean:
            idx = clean.rfind("**Discovery:")
            if idx >= 0:
                block_start = idx
                block_end = len(clean)
                cat_idx = clean.find("**Category:**", idx)
                if cat_idx < 0:
                    cat_idx = clean.find("**Category:", idx)
                if cat_idx >= 0:
                    line_end = clean.find("\n", cat_idx)
                    block_end = line_end if line_end >= 0 else len(clean)
                clean = clean[block_start:block_end].strip()
        elif "Pattern:" in clean and "Fix:" in clean:
            idx = clean.find("Pattern:")
            if idx >= 0:
                clean = clean[idx:].strip()

        # Phase 2: If still looks like narrative (has ## headers), extract bullet points
        if clean.startswith("## ") or clean.startswith("**Status:**"):
            lines = clean.split("\n")
            bullets = []
            in_bullet_section = False
            seen_trail = set()
            narrative_markers = (
                "## ", "**Status:**", "**Source:**", "**Authority:**",
                "**What this means:**", "**Why it matters:**",
                "**The decision:**", "**Details:**", "**Context:**",
                "**Progression:**", "**Evidence Trail:**",
                "This principle has been", "This decision has been",
                "This architecture note", "This pattern was discovered",
                "This observation was mined", "This was not always obvious",
                "It may be promoted", "This truth survived",
                "It is no longer a note", "It graduated from",
                "Any new work that conflicts",
                "Use `promote", "Candidate for promotion",
            )
            for line in lines:
                stripped = line.strip()
                if any(stripped.startswith(m) for m in narrative_markers):
                    in_bullet_section = False
                    continue
                if stripped.startswith("- "):
                    item = stripped[2:]
                    # Deduplicate evidence trail entries from multiple narrative layers
                    # Also skip these since _GenerateNarrative adds them fresh from DB
                    trail_key = None
                    if item.startswith("Mentioned in "):
                        trail_key = "Mentioned in"
                    elif item.startswith("Defines glossary"):
                        trail_key = "Defines glossary"
                    elif item.startswith("Related to "):
                        trail_key = "Related to"
                    if trail_key:
                        continue  # Skip — _GenerateNarrative adds these from real DB queries
                    bullets.append(stripped)
                    in_bullet_section = True
                elif in_bullet_section and stripped and not stripped.startswith("**"):
                    # Continuation line — make it a new bullet, not append
                    bullets.append(f"- {stripped}")
                elif stripped.startswith("**") and ":**" in stripped:
                    # A field like **Confidence:** 0.9 — keep it
                    bullets.append(stripped)
                    in_bullet_section = False
                else:
                    in_bullet_section = False
            if bullets:
                clean = "\n".join(bullets)
            else:
                # No bullets found — strip narrative markers and keep rest
                clean = "\n".join(
                    l for l in lines
                    if l.strip() and not any(l.strip().startswith(m) for m in narrative_markers)
                ).strip()

        # Phase 3: Format the cleaned evidence
        if clean.startswith("[@"):
            if "]{(" in clean:
                start = clean.find("]{(") + 3
                end = clean.rfind(")}")
                if end > start:
                    inner = clean[start:end]
                    # Handle both semicolon and comma-separated items
                    if ";" in inner:
                        items = [s.strip().strip('"') for s in inner.split(";") if s.strip()]
                    else:
                        items = [s.strip().strip('"') for s in inner.split(",") if s.strip()]
                    clean = "\n".join(f"- {item}" for item in items if item)
        elif clean.startswith("Pattern:"):
            lines = clean.split("\n")
            formatted = []
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.replace("', '", " ").replace("'", "").strip()
                    while "  " in val:
                        val = val.replace("  ", " ")
                    formatted.append(f"**{key.strip()}:** {val}")
                else:
                    formatted.append(line)
            clean = "\n".join(formatted)
        elif clean.startswith("**Discovery:"):
            lines = clean.split("\n")
            formatted = []
            for line in lines:
                if line.startswith("**") and ":**" in line:
                    key, val = line.split(":**", 1)
                    val = val.replace("', '", " ").replace("'", "").strip()
                    while "  " in val:
                        val = val.replace("  ", " ")
                    formatted.append(f"**{key.strip()}:** {val}")
                else:
                    formatted.append(line)
            clean = "\n".join(formatted)
        return clean.strip()

    def _GenerateNarrative(self, conn, ch_id, title, desc, tier, owner,
                           confidence, source_table, raw_evidence):
        display_title = title.replace("_", " ").replace("'", "").replace(",", " ")
        while "  " in display_title:
            display_title = display_title.replace("  ", " ")
        display_title = display_title.strip()
        acronyms = {"tuple3", "vbstyle", "mysql", "sqlite", "gui", "db", "fk",
                    "sql", "cli", "api", "json", "xml", "html", "css", "js",
                    "py", "c", "ram", "cpu", "io", "os", "hw", "qa"}
        words = display_title.split()
        titled = []
        for w in words:
            if w.lower() in acronyms:
                titled.append(w.upper())
            else:
                titled.append(w.capitalize())
        display_title = " ".join(titled)

        tier_headers = {
            "authoritative": f"## Principle: {display_title}",
            "promoted": f"## Decision: {display_title}",
            "candidate": f"## Discovery: {display_title}",
            "evidence": f"## Observation: {display_title}",
        }
        header = tier_headers.get(tier, f"## Note: {display_title}")

        xref_count = conn.execute(
            "SELECT COUNT(*) FROM cross_refs WHERE to_chapter = ?",
            (ch_id,)
        ).fetchone()[0]

        title_pattern = f"%{title}%"
        referencing_chapters = conn.execute(
            "SELECT DISTINCT ch.ch_num, ch.title "
            "FROM chapters ch "
            "JOIN sections s ON s.chapter_id = ch.id "
            "JOIN content_blocks cb ON cb.section_id = s.id "
            "WHERE cb.content LIKE ? AND ch.id != ? "
            "LIMIT 10",
            (title_pattern, ch_id)
        ).fetchall()

        related = conn.execute(
            "SELECT mr.relationship, ch.ch_num, ch.title "
            "FROM milestone_relations mr "
            "JOIN chapters ch ON ch.id = mr.to_chapter_id "
            "WHERE mr.from_chapter_id = ? "
            "ORDER BY mr.relationship, ch.ch_num "
            "LIMIT 10",
            (ch_id,)
        ).fetchall()

        rule_count = 0
        try:
            rule_count = conn.execute(
                "SELECT COUNT(*) FROM chapter_rules WHERE chapter_id = ?",
                (ch_id,)
            ).fetchone()[0]
        except Exception:
            pass

        glossary_terms = conn.execute(
            "SELECT term FROM glossary WHERE chapter_id = ?",
            (ch_id,)
        ).fetchall()

        promoted_at = conn.execute(
            "SELECT promoted_at FROM knowledge_tiers WHERE chapter_id = ?",
            (ch_id,)
        ).fetchone()
        promoted_date = promoted_at[0] if promoted_at and promoted_at[0] else None

        parts = [header, ""]

        if tier == "authoritative":
            owner_str = f" Owned by the {owner} domain." if owner else ""
            date_str = f" Promoted on {promoted_date}." if promoted_date else ""
            parts.append(f"**Status:** Authoritative.{owner_str}{date_str}")
        elif tier == "promoted":
            date_str = f" Promoted on {promoted_date}." if promoted_date else ""
            parts.append(f"**Status:** Promoted.{date_str} Eligible for authoritative status with an owner domain.")
        elif tier == "candidate":
            conf_str = f" Confidence: {confidence}." if confidence else ""
            parts.append(f"**Status:** Candidate.{conf_str} Needs validation before promotion.")
        else:
            conf_str = f" Confidence: {confidence}." if confidence else ""
            parts.append(f"**Status:** Evidence.{conf_str} Raw observation awaiting validation.")
        parts.append("")

        if source_table:
            source_desc = {
                "instructions": "Architecture instruction from the VB shared brain",
                "learned_rules": "Learned rule from pattern observation",
            }.get(source_table, f"Mined from {source_table}")
            parts.append(f"**Source:** {source_desc}")
            parts.append("")

        clean_body = self._CleanEvidence(raw_evidence)
        if clean_body:
            parts.append(clean_body)
            parts.append("")

        evidence_items = []
        if xref_count > 0:
            evidence_items.append(f"Referenced by {xref_count} cross-link(s) across the book")
        if referencing_chapters:
            ref_names = [r["title"].replace("_", " ")[:40] for r in referencing_chapters[:5]]
            evidence_items.append(f"Mentioned in {len(referencing_chapters)} chapter(s): {', '.join(ref_names)}")
        if rule_count > 0:
            evidence_items.append(f"Associated with {rule_count} formal rule(s)")
        if glossary_terms:
            term_list = [t["term"] for t in glossary_terms[:5]]
            evidence_items.append(f"Defines glossary terms: {', '.join(term_list)}")

        if related:
            rel_groups = {}
            for r in related:
                rel = r["relationship"]
                name = r["title"].replace("_", " ")[:40]
                rel_groups.setdefault(rel, []).append(name)
            for rel, names in rel_groups.items():
                evidence_items.append(f"{rel.replace('-', ' ').capitalize()}: {', '.join(names)}")

        if evidence_items:
            parts.append("**Evidence Trail:**")
            parts.append("")
            for item in evidence_items:
                parts.append(f"- {item}")
            parts.append("")

        if tier != "evidence":
            path = []
            if source_table == "learned_rules":
                path.append("observed as a pattern")
            elif source_table == "instructions":
                path.append("recorded as an architecture instruction")
            if tier in ("candidate", "promoted", "authoritative"):
                path.append("identified as a candidate")
            if tier in ("promoted", "authoritative"):
                path.append("promoted based on evidence")
            if tier == "authoritative":
                path.append(f"elevated to authoritative status{f' under {owner}' if owner else ''}")
            parts.append(f"**Progression:** {' -> '.join(path)}")
            parts.append("")

        return "\n".join(parts)

    # ------------------------------------------------------------------------
    # DISCOVER RELATIONS — Auto-discover milestone-to-milestone relationships
    # ------------------------------------------------------------------------
    # Method: DiscoverRelations
    # Purpose: Scan all milestone evidence for shared keywords and concepts.
    #          When two milestones share significant keyword overlap, record
    #          a relationship in milestone_relations. Three types detected:
    #          - relates-to: general keyword overlap
    #          - supports: one milestone's fix/action reinforces another's pattern
    #          - contradicts: one milestone's fix conflicts with another's pattern
    # Params:  params = {'min_overlap': int (optional, default 3)}
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def DiscoverRelations(self, params):
        min_overlap = self._p(params, "min_overlap", 3)

        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_evidence ("
            "  chapter_id INTEGER PRIMARY KEY,"
            "  raw_data TEXT,"
            "  evidence_type TEXT,"
            "  source_table TEXT,"
            "  source_id TEXT,"
            "  confidence REAL,"
            "  violation_count INTEGER DEFAULT 0,"
            "  first_seen TEXT,"
            "  FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS milestone_relations ("
            "  from_chapter_id INTEGER,"
            "  to_chapter_id INTEGER,"
            "  relationship TEXT NOT NULL,"
            "  strength REAL DEFAULT 1.0,"
            "  discovered_at TEXT,"
            "  PRIMARY KEY (from_chapter_id, to_chapter_id, relationship),"
            "  FOREIGN KEY(from_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,"
            "  FOREIGN KEY(to_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE"
            ")"
        )

        stats = {"relates_to": 0, "supports": 0, "contradicts": 0, "total": 0}

        milestones = conn.execute(
            "SELECT me.chapter_id, me.raw_data, me.evidence_type, "
            "ch.title, ch.ch_num "
            "FROM milestone_evidence me "
            "JOIN chapters ch ON ch.id = me.chapter_id "
            "JOIN parts p ON p.id = ch.part_id "
            "WHERE p.part_num = 7"
        ).fetchall()

        STOP_WORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "about", "like", "through", "after", "over",
            "between", "out", "against", "during", "without", "before",
            "under", "around", "among", "and", "or", "but", "not", "no",
            "so", "if", "then", "else", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "only", "own", "same", "than",
            "too", "very", "just", "this", "that", "these", "those",
            "it", "its", "they", "them", "their", "we", "us", "our",
            "you", "your", "he", "she", "his", "her", "which", "who",
            "what", "there", "here", "now", "also", "any", "because",
        }

        def extract_keywords(text):
            if not text:
                return set()
            words = text.lower().replace("_", " ").split()
            return {w for w in words if len(w) > 2 and w not in STOP_WORDS}

        def extract_fix(text):
            if not text:
                return ""
            for line in text.split("\n"):
                if line.startswith("Fix:"):
                    return line[4:].strip()
            return ""

        def extract_pattern(text):
            if not text:
                return ""
            for line in text.split("\n"):
                if line.startswith("Pattern:"):
                    return line[8:].strip()
            return ""

        milestone_data = []
        for m in milestones:
            kw = extract_keywords(m["raw_data"])
            fix = extract_fix(m["raw_data"])
            pattern = extract_pattern(m["raw_data"])
            milestone_data.append({
                "ch_id": m["chapter_id"],
                "keywords": kw,
                "fix": fix,
                "pattern": pattern,
                "title": m["title"],
            })

        for i, a in enumerate(milestone_data):
            for j, b in enumerate(milestone_data):
                if i >= j:
                    continue
                overlap = a["keywords"] & b["keywords"]
                if len(overlap) < min_overlap:
                    continue

                strength = len(overlap) / max(
                    len(a["keywords"] | b["keywords"]), 1
                )

                relationship = "relates-to"

                if a["fix"] and b["pattern"]:
                    a_fix_words = set(a["fix"].lower().split())
                    b_pattern_words = set(b["pattern"].lower().split())
                    if a_fix_words & b_pattern_words:
                        relationship = "supports"
                if b["fix"] and a["pattern"]:
                    b_fix_words = set(b["fix"].lower().split())
                    a_pattern_words = set(a["pattern"].lower().split())
                    if b_fix_words & a_pattern_words:
                        relationship = "supports"

                contradiction_words = {
                    "never", "forbidden", "prohibited", "cannot",
                    "don't", "must not", "no ", "not ",
                }
                if a["fix"] and b["fix"]:
                    a_fix_lower = a["fix"].lower()
                    b_fix_lower = b["fix"].lower()
                    a_neg = any(w in a_fix_lower for w in contradiction_words)
                    b_neg = any(w in b_fix_lower for w in contradiction_words)
                    if a_neg != b_neg and len(overlap) >= min_overlap + 2:
                        relationship = "contradicts"

                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO milestone_relations "
                        "(from_chapter_id, to_chapter_id, relationship, strength, discovered_at) "
                        "VALUES (?, ?, ?, ?, datetime('now'))",
                        (a["ch_id"], b["ch_id"], relationship, round(strength, 3))
                    )
                    stats["total"] += 1
                    if relationship == "relates-to":
                        stats["relates_to"] += 1
                    elif relationship == "supports":
                        stats["supports"] += 1
                    elif relationship == "contradicts":
                        stats["contradicts"] += 1
                except Exception:
                    pass

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Discovered {stats['total']} relationships: "
            f"{stats['relates_to']} relates-to, "
            f"{stats['supports']} supports, "
            f"{stats['contradicts']} contradicts"
        )
        return (1, stats, ())

    # ------------------------------------------------------------------------
    # POLISH — Clean up titles, content, and add intros to Parts 3-6
    # ------------------------------------------------------------------------
    # Method: Polish
    # Purpose: Three-pass cleanup:
    #          1. Rename ugly Part 7 chapter titles to human-readable
    #          2. Clean raw pattern text in content blocks (backup —
    #             _CleanEvidence in _GenerateNarrative handles most of this)
    #          3. Add intro paragraphs to Parts 3-6 chapters
    # Params:  params (dict, unused)
    # Returns: Tuple3 (ok, stats_dict, error)
    # ------------------------------------------------------------------------
    def Polish(self, params):
        ok_db, conn, err = self.OpenDB()
        if not ok_db:
            return (0, None, err)

        stats = {"titles": 0, "content": 0, "intros": 0}

        # --- 1. Clean Part 7 chapter titles ---
        part7 = conn.execute(
            "SELECT ch.id, ch.ch_num, ch.title "
            "FROM chapters ch "
            "JOIN parts p ON p.id = ch.part_id "
            "WHERE p.part_num = 7"
        ).fetchall()

        for ch in part7:
            ch_id = ch["id"]
            title = ch["title"]

            # Clean the section title for this chapter (always run)
            sec = conn.execute(
                "SELECT id, title FROM sections WHERE chapter_id = ?",
                (ch_id,)
            ).fetchone()
            if sec:
                sec_title = sec["title"]
                if "_" in sec_title or len(sec_title) > 50:
                    clean_sec = sec_title.replace("'", "").replace(",", " ")
                    clean_sec = clean_sec.replace("(", "").replace(")", "")
                    clean_sec = clean_sec.replace("_", " ")
                    while "  " in clean_sec:
                        clean_sec = clean_sec.replace("  ", " ")
                    clean_sec = clean_sec.strip()
                    acronyms = {"tuple3", "vbstyle", "mysql", "sqlite", "gui", "db",
                                "fk", "sql", "cli", "api", "json", "xml", "html",
                                "css", "js", "py", "c", "ram", "cpu", "io", "os",
                                "hw", "qa"}
                    words = clean_sec.split()
                    titled = []
                    for w in words:
                        if w.lower() in acronyms:
                            titled.append(w.upper())
                        else:
                            titled.append(w.capitalize())
                    clean_sec = " ".join(titled)
                    if len(clean_sec) > 80:
                        clean_sec = clean_sec[:77] + "..."
                    if clean_sec != sec_title and len(clean_sec) > 3:
                        conn.execute(
                            "UPDATE sections SET title = ? WHERE id = ?",
                            (clean_sec, sec["id"])
                        )

            # Skip already-clean chapter titles (no underscores, short)
            if "_" not in title and len(title) <= 50:
                continue

            # Clean the title
            clean_title = title
            # Remove quotes, commas, parentheses content
            clean_title = clean_title.replace("'", "").replace(",", " ")
            clean_title = clean_title.replace("(", "").replace(")", "")
            # Replace underscores with spaces
            clean_title = clean_title.replace("_", " ")
            # Collapse multiple spaces
            while "  " in clean_title:
                clean_title = clean_title.replace("  ", " ")
            # Strip trailing/leading whitespace
            clean_title = clean_title.strip()
            # Title case but keep known acronyms
            acronyms = {"tuple3", "vbstyle", "mysql", "sqlite", "gui", "db", "fk",
                        "sql", "cli", "api", "json", "xml", "html", "css", "js",
                        "py", "c", "ram", "cpu", "io", "os", "hw", "qa"}
            words = clean_title.split()
            titled = []
            for w in words:
                if w.lower() in acronyms:
                    titled.append(w.upper())
                else:
                    titled.append(w.capitalize())
            clean_title = " ".join(titled)

            # Truncate if too long
            if len(clean_title) > 80:
                clean_title = clean_title[:77] + "..."

            if clean_title != title and len(clean_title) > 3:
                conn.execute(
                    "UPDATE chapters SET title = ? WHERE id = ?",
                    (clean_title, ch_id)
                )
                stats["titles"] += 1

        # --- 2. Clean raw pattern text in content blocks ---
        # Fix content blocks that have raw commas, quotes from pattern extraction
        blocks = conn.execute(
            "SELECT cb.id, cb.content "
            "FROM content_blocks cb "
            "JOIN sections s ON s.id = cb.section_id "
            "JOIN chapters ch ON ch.id = s.chapter_id "
            "JOIN parts p ON p.id = ch.part_id "
            "WHERE p.part_num = 7 "
            "AND cb.block_type = 'text'"
        ).fetchall()

        for b in blocks:
            block_id = b["id"]
            content = b["content"]
            if not content:
                continue

            # Check if content has raw pattern artifacts
            needs_clean = False
            if "', '" in content and "**Discovery:" in content:
                needs_clean = True
            if content.count("'") > 10 and "**Trigger:**" in content:
                needs_clean = True

            if not needs_clean:
                continue

            # Clean up the discovery/trigger/fix lines
            lines = content.split("\n")
            cleaned_lines = []
            for line in lines:
                if line.startswith("**Discovery:**"):
                    # Clean the pattern text
                    val = line.replace("**Discovery:**", "").strip()
                    val = val.replace("', '", " ").replace("'", "").replace(",", " ")
                    while "  " in val:
                        val = val.replace("  ", " ")
                    cleaned_lines.append(f"**Discovery:** {val.strip()}")
                elif line.startswith("**Trigger:**"):
                    val = line.replace("**Trigger:**", "").strip()
                    val = val.replace("', '", " ").replace("'", "").replace(",", " ")
                    while "  " in val:
                        val = val.replace("  ", " ")
                    cleaned_lines.append(f"**Trigger:** {val.strip()}")
                elif line.startswith("**Fix:**"):
                    val = line.replace("**Fix:**", "").strip()
                    val = val.replace("', '", " ").replace("'", "").replace(",", " ")
                    while "  " in val:
                        val = val.replace("  ", " ")
                    cleaned_lines.append(f"**Fix:** {val.strip()}")
                elif line.startswith("**Source:**"):
                    val = line.replace("**Source:**", "").strip()
                    val = val.replace("', '", " ").replace("'", "")
                    while "  " in val:
                        val = val.replace("  ", " ")
                    cleaned_lines.append(f"**Source:** {val.strip()}")
                elif line.startswith("**Category:**"):
                    val = line.replace("**Category:**", "").strip()
                    val = val.replace("', '", " ").replace("'", "").replace(",", " ")
                    while "  " in val:
                        val = val.replace("  ", " ")
                    cleaned_lines.append(f"**Category:** {val.strip()}")
                else:
                    cleaned_lines.append(line)

            new_content = "\n".join(cleaned_lines)
            if new_content != content:
                conn.execute(
                    "UPDATE content_blocks SET content = ? WHERE id = ?",
                    (new_content, block_id)
                )
                stats["content"] += 1

        # --- 3. Add intro paragraphs to Parts 3-6 chapters ---
        # These chapters have raw schema/code — add a brief intro
        part_intros = {
            3: "This chapter is part of the VB Common Database section, documenting the schema and structure of the shared MySQL database that serves as the system's brain.",
            4: "This chapter is part of the VB Common Database section, covering table definitions and their roles in the architecture.",
            5: "This chapter is part of the Code Library section, documenting VBStyle domain classes that are stored in the database and loaded at runtime.",
            6: "This chapter is part of the Code Snippets section, containing source code extracted from the VBStyle codebase.",
        }

        for part_num, intro in part_intros.items():
            chapters = conn.execute(
                "SELECT ch.id, ch.title, ch.description "
                "FROM chapters ch "
                "JOIN parts p ON p.id = ch.part_id "
                "WHERE p.part_num = ? "
                "AND ch.description IS NULL",
                (part_num,)
            ).fetchall()

            for ch in chapters:
                ch_id = ch["id"]
                ch_title = ch["title"]

                # Build a chapter-specific intro
                if "Schema" in ch_title or "schema" in ch_title:
                    desc = f"Schema definition for {ch_title}. The VB Common Database uses a self-describing architecture where DDL is stored as data."
                elif "Source Code" in ch_title:
                    desc = f"Complete source code for {ch_title.replace(' Source Code', '')}. This is a VBStyle-compliant domain class loaded from the database at runtime."
                else:
                    desc = intro

                conn.execute(
                    "UPDATE chapters SET description = ? WHERE id = ?",
                    (desc, ch_id)
                )
                stats["intros"] += 1

        conn.commit()
        self.CloseDB()

        self.state["report"] = (
            f"Polished: {stats['titles']} titles cleaned, "
            f"{stats['content']} content blocks cleaned, "
            f"{stats['intros']} chapter intros added"
        )
        return (1, stats, ())


# ============================================================================
# CLI ENTRY POINT — main()
# This is the ONLY place that prints. All methods return Tuple3.
# ============================================================================

def parse_argv(argv):
    """Convert argv into (command, params_dict)."""
    if len(argv) < 2:
        return None, None

    command = argv[1]
    rest = argv[2:]

    # Commands that take positional args → dict
    positional_commands = {
        "add-part": ["part_num", "title", "subtitle"],
        "add-chapter": ["part_id", "ch_num", "title", "subtitle"],
        "add-section": ["chapter_id", "sec_num", "sort_order", "title", "section_type"],
        "add-block": ["section_id", "block_type", "block_order", "content", "lang"],
        "add-rule": ["rule_num", "tag", "category", "short_desc", "chapter_id"],
        "link-rule": ["rule_id", "target_type", "target_id"],
        "add-glossary": ["term", "definition", "chapter_id"],
        "add-summary": ["chapter_id", "summary"],
        "add-xref": ["from_section", "to_chapter", "to_section", "ref_text"],
        "add-table": ["section_id", "title", "headers", "rows"],
        "update-part": ["part_num", "title", "subtitle"],
        "update-chapter": ["ch_num", "title", "subtitle"],
        "update-section": ["section_id", "title", "section_type", "word_count", "page_num"],
        "update-block": ["block_id", "content", "lang", "caption", "block_order"],
        "update-glossary": ["term", "new_term", "definition", "chapter_id"],
        "update-rule": ["rule_num", "tag", "category", "short_desc", "chapter_id"],
        "remove-section": ["section_id"],
        "remove-block": ["block_id"],
        "remove-xref": ["xref_id"],
        "import-md": ["file"],
        "export-all": [],
        "export-flipbook": ["file", "title"],
        "search": ["term"],
        "check": [],
        "add-annotation": ["section_id", "selected_text", "note_text", "color"],
        "list-annotations": ["section_id"],
        "remove-annotation": ["annotation_id"],
        "export": ["ch_num"],
        "outline": ["ch_num"],
        "info": ["ch_num"],
        "list-xrefs": ["ch_num"],
        "search-mysql": ["term", "table", "limit"],
        "populate-mysql": ["source", "limit"],
        "search-code": ["term", "limit"],
        "search-docs": ["term", "table", "limit"],
        "cross-query": ["term", "limit"],
        "link-content": ["term", "limit"],
        "fix-summaries": [],
        "fix-glossary": [],
        "fix-names": [],
        "populate-milestones": ["limit"],
        "promote": ["ch_num", "tier", "owner"],
        "list-milestones": ["tier"],
        "list-authorities": [],
        "check-contradictions": ["term"],
        "write-narrative": [],
        "discover-relations": ["min_overlap"],
        "polish": [],
    }

    if command in positional_commands:
        keys = positional_commands[command]
        params = {}
        for i, key in enumerate(keys):
            if i < len(rest):
                val = rest[i]
                # Try to convert numeric keys
                if key in ("part_num", "part_id", "ch_num", "chapter_id",
                           "sec_id", "section_id", "sort_order", "block_order",
                           "block_id", "xref_id", "annotation_id",
                           "rule_num", "rule_id", "target_id", "from_section",
                           "to_section", "to_chapter", "table_id",
                           "word_count", "page_num"):
                    try:
                        val = int(val)
                    except ValueError:
                        pass
                elif key in ("headers", "rows"):
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
                params[key] = val
        return command, params

    return command, {}


# ============================================================================
# ABOUT / HELP — Output Config documentation via stdout (no print)
# ============================================================================

def write_about():
    """Write the ABOUT string from config.py to stdout."""
    sys.stdout.write(cfg.GetAbout() + "\n")


def write_help():
    """Write the HELP string from config.py to stdout."""
    sys.stdout.write(cfg.GetHelp() + "\n")


def main():
    command, params = parse_argv(sys.argv)

    if command is None:
        sys.stderr.write(
            "Usage: Book.py <command> [params...]\n"
            "Run 'Book.py help' for full command reference.\n"
            "Run 'Book.py about' for system description.\n"
        )
        return 1

    if command == "about":
        write_about()
        return 0

    if command == "help":
        write_help()
        return 0

    book = Book()
    ok, data, error = book.Run(command, params)

    if ok:
        report = book.state["report"]
        if report:
            sys.stdout.write(report + "\n")
        return 0
    else:
        code, desc, _ = error
        sys.stderr.write(f"ERROR: {code} — {desc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
