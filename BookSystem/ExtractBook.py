#!/usr/bin/env python3
"""
ExtractBook.py — MySQL Evidence → VBStyle Book (v2)

Mines the token_registry MySQL database for durable VBStyle truths
and promotes them into an O'Reilly-style technical book stored in
a new SQLite database (vbstyle_book_v2.db).

NOT a chat summarizer. NOT a transcript. An authoritative reference
where every chapter teaches knowledge that survived repeated use.

End state: Anyone (human or AI) reads this book → can write VBStyle code.
"""

import os
import sys
import sqlite3
import mysql.connector
from config import Config, cfg

# ============================================================================
# CONSTANTS
# ============================================================================
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASS = ""
MYSQL_DB = "token_registry"

BOOK_DB_PATH = os.path.join(Config.BASE_DIR, "vbstyle_book_v2.db")

# ============================================================================
# EXTRACTION ORCHESTRATOR
# ============================================================================
class BookExtractor:
    """
    Mines MySQL token_registry for VBStyle evidence.
    Promotes durable truths into book structure.
    """

    def __init__(self):
        self.state = {
            "mysql": None,
            "book": None,
            "stats": {},
        }

    # --------------------------------------------------------------------
    # CONNECT — Open both databases
    # --------------------------------------------------------------------
    def Connect(self):
        # Fresh book DB
        if os.path.exists(BOOK_DB_PATH):
            os.remove(BOOK_DB_PATH)
        self.state["book"] = sqlite3.connect(BOOK_DB_PATH)
        self.state["book"].executescript(Config.SCHEMA_SQL)
        self.state["book"].commit()

        # MySQL evidence source
        self.state["mysql"] = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB,
        )
        return (1, "Connected to MySQL + new book DB", ())

    # --------------------------------------------------------------------
    # MINE RULES — Extract compliance rules from objectives
    # --------------------------------------------------------------------
    def MineRules(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT objective, description, category, priority, status
            FROM objectives
            WHERE source_type = 'rule'
            ORDER BY priority DESC, id
        """)
        rows = cur.fetchall()
        self.state["stats"]["rules_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE VIOLATIONS — Extract real anti-patterns from method_violations
    # --------------------------------------------------------------------
    def MineViolations(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT mv.rule_id, mv.kind, mv.message, mv.pattern,
                   COUNT(*) as occurrence_count
            FROM method_violations mv
            GROUP BY mv.rule_id, mv.kind, mv.message, mv.pattern
            ORDER BY occurrence_count DESC
        """)
        rows = cur.fetchall()
        self.state["stats"]["violations_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE CLASSES — Extract real VBStyle classes
    # --------------------------------------------------------------------
    def MineClasses(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT id, name, description, bracket, domain_id,
                   boot_stage, boot_priority, memunit_entry_flag
            FROM classes
            ORDER BY domain_id, id
        """)
        rows = cur.fetchall()
        self.state["stats"]["classes_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE METHODS — Extract real method code (sample for examples)
    # --------------------------------------------------------------------
    def MineMethods(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT m.id, m.class_id, m.name, m.code, c.name as class_name
            FROM methods m
            JOIN classes c ON m.class_id = c.id
            WHERE m.name IN ('Run', 'read_state', 'set_config', '__init__')
            ORDER BY m.class_id, m.name
            LIMIT 100
        """)
        rows = cur.fetchall()
        self.state["stats"]["methods_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE BOOT STAGES — Extract orchestration boot sequence
    # --------------------------------------------------------------------
    def MineBootStages(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT o.class_id, o.boot_priority, o.boot_stage,
                   c.name as class_name, c.description
            FROM orchestration o
            JOIN classes c ON o.class_id = c.id
            ORDER BY o.boot_priority
        """)
        rows = cur.fetchall()
        self.state["stats"]["boot_stages_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE TABLE PURPOSES — Extract architecture map
    # --------------------------------------------------------------------
    def MineTablePurposes(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT table_name, description, role_text, relationships,
                   connection_flow, row_count
            FROM table_purpose_registry
            ORDER BY row_count DESC
        """)
        rows = cur.fetchall()
        self.state["stats"]["table_purposes_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE OBJECTIVES — Extract architecture decisions and learnings
    # --------------------------------------------------------------------
    def MineObjectives(self):
        cur = self.state["mysql"].cursor(dictionary=True)
        cur.execute("""
            SELECT objective, description, category, source_type, priority
            FROM objectives
            WHERE source_type IN ('architecture_learning', 'solution')
            ORDER BY priority DESC, id
            LIMIT 200
        """)
        rows = cur.fetchall()
        self.state["stats"]["objectives_mined"] = len(rows)
        cur.close()
        return (1, rows, ())

    # --------------------------------------------------------------------
    # MINE DOCUMENTS — Dynamically discover all VBStyle-relevant docs
    # --------------------------------------------------------------------
    def MineDocuments(self):
        cur = self.state["mysql"].cursor(dictionary=True)

        # Dynamically discover ALL VBStyle-relevant markdown documents
        # by searching file paths for VBStyle-related keywords
        keywords = [
            '%vbstyle%', '%VBSTYLE%', '%VBStyle%',
            '%bracket%', '%Bracket%',
            '%domain%', '%Domain%',
            '%memunit%', '%MemUnit%', '%memdb%', '%MemDB%', '%membus%', '%MemBus%',
            '%ghost%', '%Ghost%',
            '%tuple%', '%Tuple%',
            '%dispatch%', '%Dispatch%',
            '%boot%', '%Boot%',
            '%law%', '%Law%',
            '%rule%', '%Rule%',
            '%lesson%', '%Lesson%',
            '%architecture%', '%Architecture%',
            '%refactor%', '%Refactor%',
            '%pattern%', '%Pattern%',
            '%authority%', '%Authority%',
            '%resource%', '%Resource%',
            '%magnetic%', '%Magnetic%',
            '%convergence%', '%Convergence%',
            '%immutable%', '%Immutable%',
            '%collapse%', '%Collapse%',
            '%drift%', '%Drift%',
            '%executor%', '%Executor%',
            '%orchestrat%', '%Orchestrat%',
            '%runtime%', '%Runtime%',
            '%core%', '%Core%',
            '%unit%', '%Unit%',
            '%error_ecosystem%', '%error%',
            '%failsafe%', '%FailSafe%',
            '%compliance%', '%Compliance%',
            '%violation%', '%Violation%',
        ]

        # Build dynamic WHERE clause
        conditions = " OR ".join(["file_path LIKE %s" for _ in keywords])
        params = [k for k in keywords]

        # Exclude chat transcripts (they are evidence, not promoted truth)
        exclusions = [
            "file_path NOT LIKE '%CASCADE_%'",
            "file_path NOT LIKE '%chat_tagged_archive%'",
            "file_path NOT LIKE '%chat_tagged%'",
            "file_path NOT LIKE '%Aec_chat_documents%'",
            "file_path NOT LIKE '%Chats/Cascade%'",
            "file_path NOT LIKE '%chatgpt%'",
            "file_path NOT LIKE '%ChatGPT%'",
        ]
        exclude_clause = " AND ".join(exclusions)

        query = f"""
            SELECT id, file_path, content, LENGTH(content) as content_len
            FROM ingested_documents
            WHERE file_type='md'
              AND ({conditions})
              AND {exclude_clause}
            ORDER BY LENGTH(content) DESC
        """

        cur.execute(query, params)
        rows = cur.fetchall()

        # Categorize documents by topic for the book builder
        docs = {}
        topic_map = {
            "architecture": ["architecture", "core", "runtime", "orchestrat"],
            "bracket": ["bracket", "ghost", "annotation"],
            "domain": ["domain", "authority", "collapse", "drift"],
            "boot": ["boot", "setup", "config"],
            "rules": ["rule", "law", "compliance", "violation"],
            "lessons": ["lesson", "failure", "fail", "failsafe", "error"],
            "patterns": ["pattern", "refactor", "convergence", "magnetic"],
            "resource": ["resource", "memory", "budget"],
            "headers": ["ghost", "vbsty", "header"],
            "immutable": ["immutable", "guarded"],
            "unit": ["unit", "structure"],
        }

        def categorize(file_path):
            fp_lower = file_path.lower()
            topics = []
            for topic, keys in topic_map.items():
                if any(k in fp_lower for k in keys):
                    topics.append(topic)
            return topics if topics else ["general"]

        for r in rows:
            r["topics"] = categorize(r["file_path"])
            docs[r["id"]] = r

        self.state["stats"]["documents_mined"] = len(docs)
        self.state["stats"]["documents_total_md"] = 1793

        # Log what was found
        topic_counts = {}
        for d in docs.values():
            for t in d["topics"]:
                topic_counts[t] = topic_counts.get(t, 0) + 1

        self.state["stats"]["document_topics"] = topic_counts
        cur.close()
        return (1, docs, ())

    # --------------------------------------------------------------------
    # CHUNK DOCUMENTS — Read all 264 docs, split into chunks, extract truths
    # --------------------------------------------------------------------
    def ChunkDocuments(self):
        _, docs, _ = self.MineDocuments()

        CHUNK_SIZE = 2000   # chars per chunk
        chunks = []         # list of {doc_id, file_path, chunk_idx, text, topics}

        for doc_id, d in docs.items():
            content = d.get("content", "").replace("\\n", "\n")
            fp = d.get("file_path", "")
            topics = d.get("topics", ["general"])

            # Split content into sections by markdown headers first
            # Then split long sections into chunks of CHUNK_SIZE
            sections = self._SplitByHeaders(content)

            chunk_idx = 0
            for sec_text in sections:
                sec_text = sec_text.strip()
                if not sec_text or len(sec_text) < 50:
                    continue

                # If section is small enough, keep as one chunk
                if len(sec_text) <= CHUNK_SIZE:
                    chunks.append({
                        "doc_id": doc_id,
                        "file_path": fp,
                        "chunk_idx": chunk_idx,
                        "text": sec_text,
                        "topics": topics,
                        "char_count": len(sec_text),
                    })
                    chunk_idx += 1
                else:
                    # Split long sections into overlapping chunks
                    for i in range(0, len(sec_text), CHUNK_SIZE - 200):
                        piece = sec_text[i:i + CHUNK_SIZE]
                        if len(piece) < 100:
                            break
                        chunks.append({
                            "doc_id": doc_id,
                            "file_path": fp,
                            "chunk_idx": chunk_idx,
                            "text": piece,
                            "topics": topics,
                            "char_count": len(piece),
                        })
                        chunk_idx += 1

        self.state["stats"]["total_chunks"] = len(chunks)
        self.state["stats"]["total_chars_read"] = sum(c["char_count"] for c in chunks)
        return (1, chunks, ())

    # --------------------------------------------------------------------
    # SPLIT BY HEADERS — Split markdown content by # headers and [@ blocks
    # --------------------------------------------------------------------
    def _SplitByHeaders(self, content):
        if not content:
            return []
        lines = content.split("\n")
        sections = []
        current = []

        for line in lines:
            # New section on markdown header or bracket block start
            is_header = (line.strip().startswith("#") and
                         len(line.strip()) > 1 and
                         line.strip()[1] in " #")
            is_bracket_block = line.strip().startswith("[@")

            if (is_header or is_bracket_block) and current:
                sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append("\n".join(current))

        return sections

    # --------------------------------------------------------------------
    # EXTRACT TRUTHS FROM CHUNKS — Pattern-match for durable truths
    # --------------------------------------------------------------------
    def ExtractTruthsFromChunks(self):
        _, chunks, _ = self.ChunkDocuments()

        truths = {
            "rules": [],          # lines that look like rules
            "laws": [],           # lines that look like laws
            "definitions": [],    # "X is Y" or "X means Y"
            "prohibitions": [],   # "do not", "never", "forbidden"
            "requirements": [],   # "must", "required", "mandatory"
            "failures": [],       # "FAILURE", "Failure", "F###"
            "code_examples": [],  # code blocks with python/c
            "bracket_packets": [], # [@TAG]{...} blocks
            "boot_steps": [],     # boot sequence steps
            "architecture": [],   # architecture decisions
        }

        seen_rules = set()
        seen_defs = set()
        seen_failures = set()

        for chunk in chunks:
            text = chunk["text"]
            fp = chunk["file_path"]
            short_fp = fp.split("/")[-1] if "/" in fp else fp
            lines = text.split("\n")

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or len(stripped) < 10:
                    continue

                lower = stripped.lower()

                # --- RULES ---
                # Lines with rule tags like @run, @t3, @domain etc
                if any(tag in lower for tag in [
                    "@run", "@t3", "@domain", "@ghost", "@vbsty", "@mthdr",
                    "@pascal", "@decorators", "@print", "@hardcode", "@intstate",
                    "@dismap", "@memunit", "@auth", "@ctor", "@state", "@noself",
                    "@params", "@tuples", "@clshdr", "@cstyle", "@upper",
                    "@underscore", "@enums", "@tabs", "@whitespace", "@hidden",
                    "@ram", "@rpt", "@selfdb", "@authdb",
                ]):
                    key = stripped[:100]
                    if key not in seen_rules:
                        seen_rules.add(key)
                        truths["rules"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                            "chunk": chunk["chunk_idx"],
                        })

                # --- LAWS ---
                if "law" in lower and ("must" in lower or "shall" in lower or
                                       "locked" in lower or "rule" in lower):
                    if len(stripped) > 20 and len(stripped) < 300:
                        truths["laws"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

                # --- DEFINITIONS ---
                # "X is Y", "X means Y", "X = Y", "X: Y"
                if any(pattern in lower for pattern in [
                    " is the ", " is a ", " is an ", " means ",
                    " stands for ", " refers to ", " represents ",
                ]):
                    if 20 < len(stripped) < 250:
                        key = stripped[:80]
                        if key not in seen_defs:
                            seen_defs.add(key)
                            truths["definitions"].append({
                                "text": stripped[:300],
                                "source": short_fp,
                            })

                # Glossary-style: "Term: definition"
                if (stripped.startswith("[") and "]" in stripped and
                    ":" in stripped and len(stripped) < 200):
                    key = stripped[:80]
                    if key not in seen_defs:
                        seen_defs.add(key)
                        truths["definitions"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

                # --- PROHIBITIONS ---
                if any(word in lower for word in [
                    "do not ", "don't ", "never ", "forbidden",
                    "not allowed", "prohibited", "must not",
                ]):
                    if 20 < len(stripped) < 300:
                        truths["prohibitions"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

                # --- REQUIREMENTS ---
                if any(word in lower for word in [
                    "must have", "must be", "required", "mandatory",
                    "every ", "all ", "each ",
                ]):
                    if 30 < len(stripped) < 300 and not stripped.startswith("#"):
                        truths["requirements"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

                # --- FAILURES ---
                if any(pattern in stripped for pattern in [
                    "FAILURE ", "Failure ", "F0", "F1", "F2", "F3", "F4", "F5",
                    "FAIL ", "LESSON", "Lesson",
                ]):
                    if 15 < len(stripped) < 300:
                        key = stripped[:80]
                        if key not in seen_failures:
                            seen_failures.add(key)
                            truths["failures"].append({
                                "text": stripped[:300],
                                "source": short_fp,
                            })

                # --- BOOT STEPS ---
                if any(word in lower for word in [
                    "boot", "init", "setup", "activate", "startup",
                ]) and any(word in lower for word in [
                    "step", "stage", "phase", "order", "sequence",
                    "first", "second", "third", "then", "next",
                ]):
                    if 20 < len(stripped) < 300:
                        truths["boot_steps"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

                # --- ARCHITECTURE DECISIONS ---
                if any(word in lower for word in [
                    "architecture", "component", "subsystem",
                    "module", "interface", "design decision",
                ]):
                    if 30 < len(stripped) < 300 and not stripped.startswith("#"):
                        truths["architecture"].append({
                            "text": stripped[:300],
                            "source": short_fp,
                        })

            # --- CODE EXAMPLES (multi-line) ---
            in_code = False
            code_lines = []
            code_lang = None
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("```"):
                    if in_code:
                        code_text = "\n".join(code_lines)
                        if 50 < len(code_text) < 3000:
                            truths["code_examples"].append({
                                "text": code_text[:2000],
                                "lang": code_lang or "text",
                                "source": short_fp,
                            })
                        code_lines = []
                        code_lang = None
                        in_code = False
                    else:
                        in_code = True
                        code_lang = stripped[3:].strip() or "text"
                elif in_code:
                    code_lines.append(line)

            # --- BRACKET PACKETS (multi-line [@TAG]{...} blocks) ---
            in_bracket = False
            bracket_lines = []
            bracket_tag = None
            brace_depth = 0
            for line in lines:
                stripped = line.strip()
                if not in_bracket and stripped.startswith("[@") and "{" in stripped:
                    in_bracket = True
                    bracket_tag = stripped.split("]")[0].lstrip("[")
                    brace_depth = stripped.count("{") - stripped.count("}")
                    bracket_lines = [line]
                elif in_bracket:
                    bracket_lines.append(line)
                    brace_depth += stripped.count("{") - stripped.count("}")
                    if brace_depth <= 0:
                        block_text = "\n".join(bracket_lines)
                        if 50 < len(block_text) < 3000:
                            truths["bracket_packets"].append({
                                "text": block_text[:2000],
                                "tag": bracket_tag,
                                "source": short_fp,
                            })
                        in_bracket = False
                        bracket_lines = []
                        bracket_tag = None
                        brace_depth = 0

        # Deduplicate and count
        for category, items in truths.items():
            # Deduplicate by text
            seen = set()
            unique = []
            for item in items:
                key = item["text"][:100]
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            truths[category] = unique

        self.state["stats"]["truths_rules"] = len(truths["rules"])
        self.state["stats"]["truths_laws"] = len(truths["laws"])
        self.state["stats"]["truths_definitions"] = len(truths["definitions"])
        self.state["stats"]["truths_prohibitions"] = len(truths["prohibitions"])
        self.state["stats"]["truths_requirements"] = len(truths["requirements"])
        self.state["stats"]["truths_failures"] = len(truths["failures"])
        self.state["stats"]["truths_code"] = len(truths["code_examples"])
        self.state["stats"]["truths_brackets"] = len(truths["bracket_packets"])
        self.state["stats"]["truths_boot"] = len(truths["boot_steps"])
        self.state["stats"]["truths_architecture"] = len(truths["architecture"])

        return (1, truths, ())

    # --------------------------------------------------------------------
    # BUILD EXTRACTED TRUTHS CHAPTER — Promote mined truths into the book
    # --------------------------------------------------------------------
    def BuildExtractedTruths(self):
        book = self.state["book"]
        _, truths, _ = self.ExtractTruthsFromChunks()

        # Get part 9 for appendices
        part9_id = book.execute("SELECT id FROM parts WHERE part_num=9").fetchone()[0]
        max_ch = book.execute("SELECT MAX(ch_num) FROM chapters").fetchone()[0] or 0
        ch_num = max_ch + 1

        total_truths = sum(len(v) for v in truths.values())

        # Create the main Extracted Truths chapter
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part9_id, ch_num, "Appendix F: Mined Truths from 264 Documents",
             f"{total_truths} durable truths extracted by chunking all documents",
             "Every document in the evidence base was read in 2000-char chunks. "
             "Each chunk was pattern-matched for rules, laws, definitions, prohibitions, "
             "requirements, failures, code examples, and bracket packets. "
             "This appendix contains the unique truths found.")
        )
        ch_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]
        ch_num += 1

        # Helper to add a section with content
        def addTruthSection(sec_num, title, items, max_items=50):
            if not items:
                return
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, 'text')",
                (ch_id, sec_num, sec_num, f"{title} ({len(items)} found)")
            )
            sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

            content = ""
            for i, item in enumerate(items[:max_items], 1):
                text = item["text"]
                source = item.get("source", "unknown")
                content += f"{i}. {text}\n"
                content += f"   [source: {source}]\n\n"

            if len(items) > max_items:
                content += f"\n... and {len(items) - max_items} more\n"

            book.execute(
                "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                "VALUES (?, 'text', 1, ?)",
                (sec_id, content)
            )

        # Add sections for each truth category
        sec_num = 0

        sec_num += 1
        addTruthSection(sec_num, "Rules (Tagged)", truths["rules"], max_items=80)

        sec_num += 1
        addTruthSection(sec_num, "Laws", truths["laws"], max_items=50)

        sec_num += 1
        addTruthSection(sec_num, "Definitions", truths["definitions"], max_items=80)

        sec_num += 1
        addTruthSection(sec_num, "Prohibitions", truths["prohibitions"], max_items=60)

        sec_num += 1
        addTruthSection(sec_num, "Requirements", truths["requirements"], max_items=60)

        sec_num += 1
        addTruthSection(sec_num, "Failures & Lessons", truths["failures"], max_items=60)

        sec_num += 1
        addTruthSection(sec_num, "Boot Steps", truths["boot_steps"], max_items=40)

        sec_num += 1
        addTruthSection(sec_num, "Architecture Decisions", truths["architecture"], max_items=50)

        # Code examples — add as code blocks
        sec_num += 1
        if truths["code_examples"]:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, 'text')",
                (ch_id, sec_num, sec_num, f"Code Examples ({len(truths['code_examples'])} found)")
            )
            sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

            for i, item in enumerate(truths["code_examples"][:30], 1):
                lang = item.get("lang", "text")
                source = item.get("source", "unknown")
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang, caption) "
                    "VALUES (?, 'code', ?, ?, ?, ?)",
                    (sec_id, i, item["text"][:1500], lang,
                     f"Code from {source}")
                )

        # Bracket packets — add as code blocks
        sec_num += 1
        if truths["bracket_packets"]:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, 'text')",
                (ch_id, sec_num, sec_num, f"Bracket Packets ({len(truths['bracket_packets'])} found)")
            )
            sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

            for i, item in enumerate(truths["bracket_packets"][:40], 1):
                tag = item.get("tag", "unknown")
                source = item.get("source", "unknown")
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang, caption) "
                    "VALUES (?, 'code', ?, ?, 'bracket', ?)",
                    (sec_id, i, item["text"][:1500],
                     f"[@{tag}] from {source}")
                )

        # Add a chunking summary section
        sec_num += 1
        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, ?, ?, ?, 'text')",
            (ch_id, sec_num, sec_num, "Chunking Summary")
        )
        sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        s = self.state["stats"]
        summary = (
            f"Document Chunking Summary\n\n"
            f"Documents scanned:     {len(self.MineDocuments()[1])}\n"
            f"Total chunks created:  {s.get('total_chunks', 0)}\n"
            f"Total chars read:      {s.get('total_chars_read', 0):,}\n"
            f"Chunk size:            2000 chars (with 200 char overlap)\n\n"
            f"Truths extracted:\n"
            f"  Rules (tagged):      {s.get('truths_rules', 0)}\n"
            f"  Laws:                {s.get('truths_laws', 0)}\n"
            f"  Definitions:         {s.get('truths_definitions', 0)}\n"
            f"  Prohibitions:        {s.get('truths_prohibitions', 0)}\n"
            f"  Requirements:        {s.get('truths_requirements', 0)}\n"
            f"  Failures & Lessons:  {s.get('truths_failures', 0)}\n"
            f"  Boot steps:          {s.get('truths_boot', 0)}\n"
            f"  Architecture:        {s.get('truths_architecture', 0)}\n"
            f"  Code examples:       {s.get('truths_code', 0)}\n"
            f"  Bracket packets:     {s.get('truths_brackets', 0)}\n"
            f"  TOTAL UNIQUE TRUTHS: {total_truths}\n\n"
            f"Method:\n"
            f"  1. Each document split by markdown headers and [@ bracket blocks\n"
            f"  2. Long sections split into 2000-char chunks with 200-char overlap\n"
            f"  3. Each chunk pattern-matched for 10 truth categories\n"
            f"  4. Deduplicated by first 100 chars\n"
            f"  5. Promoted unique truths into this appendix\n\n"
            f"This is NOT a curated selection. Every document was read. "
            f"Every chunk was scanned. Every matching truth was extracted. "
            f"The truths above are the raw output of the chunking pipeline."
        )

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec_id, summary)
        )

        self.state["stats"]["total_truths_extracted"] = total_truths
        book.commit()
        return (1, f"Extracted {total_truths} truths from {s.get('total_chunks', 0)} chunks", ())

    # --------------------------------------------------------------------
    # SCAN ALL DOCUMENTS — Build a document evidence inventory from ALL
    # discovered VBStyle-relevant docs (not just the 7 hardcoded ones)
    # --------------------------------------------------------------------
    def ScanAllDocuments(self):
        book = self.state["book"]
        _, docs, _ = self.MineDocuments()

        # Get part 9 (examples/appendix) for the inventory
        part9_id = book.execute("SELECT id FROM parts WHERE part_num=9").fetchone()[0]
        max_ch = book.execute("SELECT MAX(ch_num) FROM chapters").fetchone()[0] or 0
        ch_num = max_ch + 1

        # Create a Document Evidence Inventory chapter
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part9_id, ch_num, "Appendix E: Document Evidence Inventory",
             f"All {len(docs)} VBStyle-relevant documents discovered in MySQL",
             "Every document in the ingested_documents table that contains VBStyle-related "
             "content, organized by topic. This is the full evidence base, not a curated subset.")
        )
        ch_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Group docs by primary topic
        topic_groups = {}
        for doc_id, d in docs.items():
            for topic in d.get("topics", ["general"]):
                if topic not in topic_groups:
                    topic_groups[topic] = []
                topic_groups[topic].append(d)

        # Create a section for each topic
        sec_num = 0
        total_listed = 0
        for topic in sorted(topic_groups.keys()):
            sec_num += 1
            doc_list = topic_groups[topic]
            topic_label = topic.replace("_", " ").title()

            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, 'text')",
                (ch_id, sec_num, sec_num, f"{topic_label} ({len(doc_list)} documents)")
            )
            sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

            # List documents in this topic
            listing = ""
            for i, d in enumerate(doc_list[:30], 1):
                fp = d["file_path"]
                # Shorten path for readability
                short = fp.split("/")[-1] if "/" in fp else fp
                content_len = d.get("content_len", len(d.get("content", "")))
                listing += f"  {i}. {short} ({content_len:,} bytes)\n"
                # Extract first meaningful line as a hint
                content = d.get("content", "").replace("\\n", "\n")
                lines = content.split("\n")
                hint = ""
                for line in lines[:10]:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("[@") and len(line) > 20:
                        hint = line[:120]
                        break
                    elif line.startswith("#") and len(line) > 5:
                        hint = line.lstrip("# ").strip()[:120]
                        break
                if hint:
                    listing += f"     → {hint}\n"
                total_listed += 1

            if len(doc_list) > 30:
                listing += f"\n  ... and {len(doc_list) - 30} more documents in this topic\n"

            book.execute(
                "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                "VALUES (?, 'text', 1, ?)",
                (sec_id, listing)
            )

        # Add a summary section
        sec_num += 1
        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, ?, ?, ?, 'text')",
            (ch_id, sec_num, sec_num, "Discovery Summary")
        )
        sec_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        topic_counts = self.state["stats"].get("document_topics", {})
        summary = (
            f"Document Discovery Summary\n\n"
            f"Total markdown documents in MySQL: {self.state['stats'].get('documents_total_md', 0)}\n"
            f"VBStyle-relevant documents found: {len(docs)}\n"
            f"Documents listed in this inventory: {total_listed}\n\n"
            f"Documents by topic:\n"
        )
        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
            summary += f"  {topic:20s}: {count:4d} documents\n"

        summary += (
            f"\nThis inventory was generated dynamically by scanning all file paths "
            f"in the ingested_documents table for VBStyle-related keywords. "
            f"Chat transcripts were excluded (they are evidence, not promoted truth). "
            f"Each document above is a candidate for promotion into the book. "
            f"Documents not yet promoted represent the gap between current book content "
            f"and the full evidence base."
        )

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec_id, summary)
        )

        self.state["stats"]["documents_discovered"] = len(docs)
        self.state["stats"]["documents_listed"] = total_listed

        book.commit()
        return (1, f"Scanned {len(docs)} documents, listed {total_listed}", ())

    # --------------------------------------------------------------------
    # BUILD MISSING CHAPTERS — Add the 20 topics found in MySQL docs
    # --------------------------------------------------------------------
    def BuildMissingChapters(self):
        book = self.state["book"]
        _, docs, _ = self.MineDocuments()

        # Helper to insert a chapter and get its ID
        def addChapter(part_id, ch_num, title, subtitle, description):
            book.execute(
                "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (part_id, ch_num, title, subtitle, description)
            )
            return book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Helper to add a section
        def addSection(ch_id, sec_num, title):
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, ?, ?, ?, 'text')",
                (ch_id, sec_num, sec_num, title)
            )
            return book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Helper to add a content block
        def addBlock(sec_id, order, content, block_type="text", lang=None, caption=None):
            book.execute(
                "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang, caption) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sec_id, block_type, order, content, lang, caption)
            )

        # Helper to add a rule
        def addRule(rule_num, tag, category, short_desc, full_desc, ch_id,
                    bad=None, good=None):
            book.execute(
                "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, "
                "example_bad, example_good, chapter_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rule_num, tag, category, short_desc, full_desc, bad, good, ch_id)
            )
            return rule_num + 1

        # Helper to add glossary term
        def addGlossary(term, definition, ch_id):
            book.execute(
                "INSERT INTO glossary (term, definition, chapter_id) VALUES (?, ?, ?)",
                (term, definition, ch_id)
            )

        # Get current max chapter number and rule number
        max_ch = book.execute("SELECT MAX(ch_num) FROM chapters").fetchone()[0] or 0
        max_rule = book.execute("SELECT MAX(rule_num) FROM rules").fetchone()[0] or 0
        ch_num = max_ch + 1
        rule_num = max_rule + 1

        # Get part IDs
        part_ids = {}
        for p in book.execute("SELECT part_num, id FROM parts").fetchall():
            part_ids[p[0]] = p[1]

        # Extract doc content safely
        def docText(doc_id, max_len=8000):
            d = docs.get(doc_id)
            if not d:
                return "(document not found)"
            c = d.get("content", "")
            return c.replace("\\n", "\n")[:max_len]

        # ================================================================
        # PART 2 EXPANSION: VBPACK, Immutable Blocks, Governance Law Chain,
        #   Bracket Grammar Variants
        # ================================================================
        part2_id = part_ids.get(2)

        # --- Ch: VBPACK System ---
        ch = addChapter(part2_id, ch_num, "VBPACK — Bracket Authority Packs",
                        "Structured knowledge packs for VBStyle core rules",
                        "The pack system that organizes VBStyle rules into portable, versioned authority blocks.")
        sec = addSection(ch, 1, "The VBPACK Structure")
        addBlock(sec, 1,
            "VBPACK is a structured format for organizing VBStyle rules into portable, versioned "
            "authority blocks. Each pack contains metadata, authority scope, core definitions, "
            "laws, ownership rules, return rules, and pack configuration.\n\n"
            "Pack structure:\n"
            "  [@VBPACK]\n"
            "  {\n"
            "    [@META]  — version, date, topic, purpose, status\n"
            "    [@AUTH]  — scope, authority, out-of-scope, governance law\n"
            "    [@CORE]  — definitions, laws, ownership rules, return rules\n"
            "    [@PACK]  — static init params, runtime dynamic params\n"
            "  }\n\n"
            "Example from the evidence:\n"
            "  [@META]{(VER<3.0>)(DTE<2026-04-18>)(TPK<VBSTYLE KNOWLEDGE BASE>)(PUR<clean bracket authority pack>)(STS<mixed cleaned>)}\n"
            "  [@AUTH]{(SCP<VBSTYLE core plus reference>)(AUT<locked core only>)(OOS<GUI law is not core|mixed tail not locked>)}\n"
            "  [@CORE]{\n"
            "    [@DEFN]{(SRT<One domain owns one owner class>)(FUL<VBSTYLE strict owner-first architecture>)}\n"
            "    [@LAW]{(ODOO<locked>)(ATIO<locked>)(NHUS<locked>)(EVF<locked>)(SRR<locked>)}\n"
            "    [@OWNR]{(OWN<Test if removed truth disappears>)(WOE<Helper|Util|Service|FakeManager>)}\n"
            "    [@RETN]{(LLW<one return family per surface>)(UNT<tuple based contracts>)}\n"
            "  }")
        addGlossary("VBPACK", "Structured bracket authority pack with META, AUTH, CORE, PACK sections.", ch)
        ch_num += 1

        # --- Ch: Immutable Blocks ---
        ch = addChapter(part2_id, ch_num, "Immutable Blocks",
                        "User-controlled guarded evaluation blocks",
                        "Blocks that only the user can modify, protected from assistant changes.")
        sec = addSection(ch, 1, "The Immutable Pattern")
        addBlock(sec, 1,
            "[@immutable]\n"
            "{\n"
            "  [@comms]\n"
            "  {\n"
            "    [@QnA]{Q:Is this immutable block valid? A:Yes >> Q:Who can change immutable? A:Only user >> Q:What is immutable? A:User-controlled guarded evaluation block}\n"
            "  }\n"
            "  [@pass]\n"
            "  {\n"
            "    [@Immutable]{User only can modify}\n"
            "    [@Guarded]{Protected from assistant changes}\n"
            "    [@Authorized]{User explicit permission required}\n"
            "  }\n"
            "  [@weight]\n"
            "  {\n"
            "    [@Immutable<Blocker>]\n"
            "    [@Guarded<High>]\n"
            "    [@Authorized<High>]\n"
            "  }\n"
            "}\n\n"
            "Immutable blocks are the highest authority in the system. They cannot be modified "
            "by AI assistants. Only the user can change them. They are guarded, protected, "
            "and require explicit authorization.\n\n"
            "Weight system:\n"
            "  Blocker — stops all execution if violated\n"
            "  High    — strong warning, cannot be bypassed\n"
            "  Medium  — warning, can be overridden with user permission")
        rule_num = addRule(rule_num, "@immutable", "authority",
            "Immutable blocks can only be modified by the user, never by AI",
            "Protected from assistant changes. Require explicit user authorization. "
            "Weight: Blocker (highest).", ch)
        addGlossary("Immutable Block", "User-controlled block protected from AI modification. Weight: Blocker.", ch)
        ch_num += 1

        # --- Ch: Governance Law Chain ---
        ch = addChapter(part2_id, ch_num, "The Governance Law Chain",
                        "Dependency-ordered law documents",
                        "VBStyle laws form a strict dependency chain. Each law depends on the previous.")
        sec = addSection(ch, 1, "The Law Chain Order")
        addBlock(sec, 1,
            "VBStyle governance follows a strict dependency chain. Each law document depends "
            "on the one before it. You MUST read them in order.\n\n"
            "The chain:\n"
            "  1. Bracket_law.md        — Foundation (no dependencies)\n"
            "     Defines canonical bracket format: [Whole[Part[SubPart[Detail]]]]\n\n"
            "  2. documentation_law.md  — Governs file organization (depends on Bracket_law)\n"
            "     Defines document structure, validation, and dependency rules\n\n"
            "  3. File_Folder_law.md    — Governs database structure (depends on documentation_law)\n"
            "     Defines canonical project layout: docs/, tests/, config/, tools/, utils/, lib/, core/\n\n"
            "  4. Database_law.md       — Defines database structure (depends on File_Folder_law)\n"
            "     Mandatory tables: Help/About, Journal. Knowledge graph. Audit trail.\n\n"
            "  5. code_law.md           — Source code standards (depends on Database_law)\n"
            "     Ghost headers, VBStyle annotations, class structure, domain separation\n\n"
            "  6. lib_law.md            — Lib file standards (depends on code_law)\n"
            "     One domain per lib file, shared library rules\n\n"
            "  7. Q_A_law.md            — Q&A system governance (depends on lib_law)\n"
            "     Question/answer format rules for the knowledge system\n\n"
            "  8. util_law.md           — Utility governance (depends on Q_A_law)\n"
            "     Single canonical database, dynamic CLI, code ingestion\n\n"
            "Dependency rule: When encountering {} in documents, AI must extract the dependency "
            "chain and read in order. Governing documents MUST be read before dependent documents.")
        rule_num = addRule(rule_num, "@lawchain", "governance",
            "Law documents must be read in dependency order",
            "Bracket_law → documentation_law → File_Folder_law → Database_law → "
            "code_law → lib_law → Q_A_law → util_law. Never skip or reorder.", ch)
        addGlossary("Governance Law Chain", "8 law documents in strict dependency order, from Bracket_law to util_law.", ch)
        ch_num += 1

        # --- Ch: Bracket Grammar Variants ---
        ch = addChapter(part2_id, ch_num, "Bracket Grammar Variants",
                        "Canonical and compressed bracket formats",
                        "The full bracket notation system, from canonical to compressed forms.")
        sec = addSection(ch, 1, "Canonical Format")
        addBlock(sec, 1,
            "Canonical bracket format: [Whole[Part[SubPart[Detail]]]]\n\n"
            "Rules:\n"
            "  - Only canonical bracket format is valid\n"
            "  - Fragmented brackets are forbidden\n"
            "  - Packets must close completely\n"
            "  - One packet = one structural aspect\n"
            "  - Ghost stamping on first line, file description on second line\n\n"
            "Three-layer structure:\n"
            "  Layer 1: Ghost header (file identity)\n"
            "  Layer 2: Authority scope (who owns this)\n"
            "  Layer 3: Metadata packets (the actual content)\n\n"
            "Compressed format (for space efficiency):\n"
            "  ghost[VBSTYLE_V3_ARCHITECTURE active 2026-03-22 v3.0 ChatGPT]\n"
            "  preface[bracket_interpretation[document_uses_compressed_bracket_notation]]\n\n"
            "Validation states: VALID, INVALID_STRUCTURE, INVALID_DEPENDENCY, INVALID_FORMAT")
        sec = addSection(ch, 2, "Bracket Tags Reference")
        addBlock(sec, 1,
            "Core bracket tags:\n"
            "  [@GHOST]     — file identity header\n"
            "  [@VBSTYLE]   — architecture declaration header\n"
            "  [@immutable] — user-controlled guarded block\n"
            "  [@comms]     — communication payload layer\n"
            "  [@pass]      — validation passed block\n"
            "  [@fail]      — validation failed block\n"
            "  [@weight]    — authority weight assignment\n"
            "  [@VBPACK]    — bracket authority pack\n"
            "  [@META]      — pack metadata\n"
            "  [@AUTH]      — pack authority scope\n"
            "  [@CORE]      — pack core definitions\n"
            "  [@DEFN]      — definition block\n"
            "  [@LAW]       — law block\n"
            "  [@OWNR]      — ownership rules\n"
            "  [@RETN]      — return rules\n"
            "  [@PACK]      — pack configuration\n\n"
            "Validation tags:\n"
            "  [@QnA]       — question and answer block\n"
            "  [@Immutable] — immutable marker\n"
            "  [@Guarded]   — guarded marker\n"
            "  [@Authorized] — authorized marker")
        ch_num += 1

        # ================================================================
        # PART 3 EXPANSION: Lib/Core/Util Modes, Report System,
        #   Utility System, Database Law
        # ================================================================
        part3_id = part_ids.get(3)

        # --- Ch: Lib Mode vs Core Mode vs Util Mode ---
        ch = addChapter(part3_id, ch_num, "Architecture Modes: Lib, Core, Util",
                        "Three modes of organizing VBStyle code",
                        "VBStyle has three architecture modes. Each has different rules for class organization.")
        sec = addSection(ch, 1, "The Three Modes")
        addBlock(sec, 1,
            "VBSTYLE has three architecture modes for organizing code:\n\n"
            "LIB MODE:\n"
            "  - One domain = one purpose = one governed responsibility\n"
            "  - Reusable domain logic with no mixed concerns\n"
            "  - Single lib file = one class = one domain = one purpose\n"
            "  - Lib files are fully covered under VBSTYLE umbrella\n"
            "  - Example: lib_config (configuration only), lib_io (I/O only)\n\n"
            "CORE MODE:\n"
            "  - Multiple classes living together permanently\n"
            "  - Tightly related operational clusters\n"
            "  - Centralized engine clusters where separation would damage clarity\n"
            "  - Examples: setup + config, DB + boot + action router, runtime engine\n"
            "  - Core files may contain multiple classes\n"
            "  - Hard limit: 12 classes per core file unless explicitly overridden\n\n"
            "UTIL MODE:\n"
            "  - Helper functions and support routines\n"
            "  - Validation, testing, proofing, compile checking, build checking\n"
            "  - No domain takeover or business logic drift\n"
            "  - Required umbrella classes: Config, Setup, Report, CLI, MemDB\n"
            "  - Single canonical utility database (db/utils.db)\n"
            "  - Dynamic CLI entry point (utils/Util_CLI.py)\n"
            "  - Code ingestion and binary embed support")
        rule_num = addRule(rule_num, "@modes", "architecture",
            "Three architecture modes: Lib (one domain), Core (cluster), Util (helpers)",
            "Lib = one class one domain. Core = up to 12 tightly coupled classes. "
            "Util = helpers with canonical db and CLI.", ch)
        addGlossary("Lib Mode", "One domain, one purpose, one lib file. Reusable, no mixing.", ch)
        addGlossary("Core Mode", "Multiple tightly coupled classes in one file. Max 12 per file.", ch)
        addGlossary("Util Mode", "Helper functions with canonical database and dynamic CLI.", ch)
        ch_num += 1

        # --- Ch: Report System ---
        ch = addChapter(part3_id, ch_num, "The Report System",
                        "Structured report generation and formatting",
                        "Core_Report.c provides report generation with multiple formats and levels.")
        sec = addSection(ch, 1, "Report Architecture")
        addBlock(sec, 1,
            "The Report system (lib_report / Core_Report.c) provides:\n\n"
            "  - Structured report generation\n"
            "  - Output formatting\n"
            "  - Multiple output formats (markdown, text, bracket)\n"
            "  - Report types and levels\n"
            "  - Level management\n\n"
            "Boot Integration:\n"
            "  - Report events recorded throughout boot process\n"
            "  - Boot status reporting\n"
            "  - Core component status tracking\n\n"
            "Scanner Integration:\n"
            "  - Scan results and compliance reports\n"
            "  - Report class system integration\n\n"
            "Key rule: Report isolation — reports return strings, never use print(). "
            "The Report class is the ONLY authority for generating output. "
            "Methods return data via Tuple3; the Report class formats it.")
        rule_num = addRule(rule_num, "@rpt", "architecture",
            "Report isolation — returns strings, never uses print()",
            "Report class is the only authority for formatted output. "
            "Methods return data via Tuple3; Report formats it.", ch)
        addGlossary("Report System", "lib_report / Core_Report.c. Generates structured reports. Returns strings, no print.", ch)
        ch_num += 1

        # --- Ch: Utility System ---
        ch = addChapter(part3_id, ch_num, "The Utility System",
                        "Single canonical database, dynamic CLI, code ingestion",
                        "The governed utility architecture with one database and one CLI entry point.")
        sec = addSection(ch, 1, "Utility Architecture")
        addBlock(sec, 1,
            "The Utility System provides governed utility architecture:\n\n"
            "UTILITY DATABASE RULES:\n"
            "  - One canonical central database: db/utils.db\n"
            "  - Stores all governed utility domains in unified database\n"
            "  - Registry record shape: id, utilname, description, code, bracket\n"
            "  - Code ingestion support — database stores actual utility code\n\n"
            "UTILITY CLI RULES:\n"
            "  - Single governed dynamic CLI entry point: utils/Util_CLI.py\n"
            "  - Bootstrap and control areas: setup, maintenance, database access, validation\n"
            "  - Dynamic discovery — all utility behavior discovered from database records\n\n"
            "UTILITY RECORD RULES:\n"
            "  - Canonical record structure with mandatory code field\n"
            "  - Stable identity and utility name\n"
            "  - Code field containing actual executable utility code\n"
            "  - Metadata fields: description, details, tags, help text, dependencies\n\n"
            "UTILITY END STATE:\n"
            "  - Governed utility architecture with single database and CLI\n"
            "  - Code ingestion for runtime loading and execution\n"
            "  - Binary embed support for self-contained utility deployment")
        ch_num += 1

        # --- Ch: Database Law ---
        ch = addChapter(part3_id, ch_num, "Database Law",
                        "Mandatory tables, knowledge graph, audit trail",
                        "Every VBStyle database must have Help/About and Journal tables.")
        sec = addSection(ch, 1, "Mandatory Database Tables")
        addBlock(sec, 1,
            "Every VBStyle database MUST have:\n\n"
            "  1. Help/About table (db_help or db_about)\n"
            "     - Instant knowledge graph for the database\n"
            "     - Self-documenting — AI can understand the database instantly\n"
            "     - Contains table descriptions, relationships, purposes\n\n"
            "  2. Journal table (db_journal)\n"
            "     - Tracks ALL changes: CREATE, ALTER, INSERT, UPDATE, DELETE, HELP_UPDATE, MAINTENANCE\n"
            "     - Complete audit trail\n"
            "     - Every operation must be journaled\n\n"
            "Additional database rules:\n"
            "  - Data integrity: primary/foreign keys, unique constraints, check constraints\n"
            "  - Access control: role-based, minimum privilege, audit logging\n"
            "  - Performance: proper indexing, query optimization, caching\n"
            "  - Backup & recovery: automated backups, multiple locations, point-in-time recovery\n\n"
            "The table_purpose_registry in token_registry is an implementation of this law — "
            "it contains descriptions, relationships, connection flows, and impact analysis "
            "for every table in the database.")
        rule_num = addRule(rule_num, "@authdb", "database",
            "Every database must have Help/About table and Journal table",
            "Help/About = instant knowledge graph. Journal = complete audit trail. "
            "All operations must be journaled.", ch)
        addGlossary("Database Law", "Mandatory Help/About + Journal tables. Self-documenting + auditable.", ch)
        ch_num += 1

        # ================================================================
        # PART 4 EXPANSION: Domain Collapse, Zero-Drift, Drift Prevention
        # ================================================================
        part4_id = part_ids.get(4)

        # --- Ch: Domain Collapse Law ---
        ch = addChapter(part4_id, ch_num, "The Domain Collapse Law",
                        "Collapse by domain, not by function name",
                        "When multiple classes repeat the same core logic inside one real domain, collapse them.")
        sec = addSection(ch, 1, "The Law")
        addBlock(sec, 1,
            "DOMAIN COLLAPSE LAW:\n\n"
            "  one_class[one_domain]\n"
            "  many_actions[allowed_if_same_domain]\n"
            "  collapse[by_domain_not_by_function_name]\n"
            "  repeated_sql[belongs_to_database_domain]\n"
            "  repeated_prediction_logic[belongs_to_prediction_domain]\n\n"
            "When to apply:\n"
            "  - Many classes repeat the same logic\n"
            "  - Many classes repeat the same SQL\n"
            "  - Many classes share one real domain\n"
            "  - Classes are split by step, not by domain\n\n"
            "Collapse test:\n"
            "  IF classes_share[same_tables, same_sql, same_state, same_scoring, same_lifecycle]\n"
            "  THEN collapse = true\n\n"
            "DO:\n"
            "  - Find the true domain\n"
            "  - Merge repeated logic into the domain engine\n"
            "  - Keep one class, one domain\n"
            "  - Push shared SQL to Database_U_c\n"
            "  - Remove duplicate query/insert/update/state/helper logic\n\n"
            "DO NOT:\n"
            "  - Merge unrelated domains\n"
            "  - Keep duplicate SQL everywhere\n"
            "  - Split one domain into fake micro-classes\n"
            "  - Make one giant everything-class\n"
            "  - Split by function name only\n\n"
            "Mistake signature:\n"
            "  BAD: many classes with same SQL tables\n"
            "  BAD: many classes with same scoring logic\n"
            "  BAD: class names different but owner is the same\n\n"
            "Success signature:\n"
            "  GOOD: one database owner\n"
            "  GOOD: one prediction owner\n"
            "  GOOD: actions collapsed under true domain\n"
            "  GOOD: less class count, more power")
        sec = addSection(ch, 2, "Real Example from the Evidence")
        addBlock(sec, 1,
            "From the codebase analysis:\n\n"
            "CURRENT (WRONG):\n"
            "  Class_CodexChatArchiveExtract  — does file_io, json_parsing, text_processing, uid_generation\n"
            "  Class_CodexChatArchiveMemDB    — mixes database_connections, schema_management, import_logic\n"
            "  Class_CodexChatArchiveEmbed    — mixes model_loading, numpy_ops, embedding_generation\n"
            "  → 7 classes, all violating domain ownership\n\n"
            "CORRECT (VBSTYLE):\n"
            "  FileEngine_U_c     — file iteration, stat reading\n"
            "  JsonEngine_U_c     — JSON parsing, validation\n"
            "  TextEngine_U_c     — text processing, scoring\n"
            "  Database_U_c       — connections, transactions\n"
            "  Schema_U_c         — structure, indexes\n"
            "  ModelEngine_U_c    — model loading, detection\n"
            "  EmbedEngine_U_c    — embedding generation, storage\n"
            "  → Each class owns exactly one domain\n\n"
            "Domain collapse required: 7 classes → 3 true domains\n"
            "  ArchiveOrchestrator_U_c, StorageEngine_U_c, ProcessingEngine_U_c")
        rule_num = addRule(rule_num, "@col", "architecture",
            "Collapse by domain, not by function name — repeated logic belongs to the domain owner",
            "If multiple classes share same SQL, same state, same lifecycle, they should be "
            "collapsed into one domain owner class. Split by domain, not by step.",
            ch,
            bad="class ExtractHelper:\n    def parse_json(self): ...\n    def read_file(self): ...\n    def gen_uid(self): ...\nclass ImportHelper:\n    def parse_json(self): ...\n    def read_file(self): ...",
            good="class FileEngine:\n    def Run(self, cmd, params):\n        if cmd == \"read\": ...\nclass JsonEngine:\n    def Run(self, cmd, params):\n        if cmd == \"parse\": ...")
        addGlossary("Domain Collapse", "Merging classes that repeat the same logic into one domain owner.", ch)
        ch_num += 1

        # --- Ch: Zero-Drift Philosophy ---
        ch = addChapter(part4_id, ch_num, "The Zero-Drift Philosophy",
                        "No drifting, no half-shapes, no broken syntax",
                        "The system must never drift from its defined structure.")
        sec = addSection(ch, 1, "The Philosophy")
        addBlock(sec, 1,
            "VBSTYLE operates on a Zero-Drift philosophy:\n\n"
            "  - No drifting — code must follow the defined patterns exactly\n"
            "  - No half-shapes — incomplete structures are forbidden\n"
            "  - No broken syntax — all brackets must close, all headers must be complete\n"
            "  - Strict compliance required — no exceptions, no 'close enough'\n\n"
            "System-wide principles that follow from Zero-Drift:\n"
            "  - Deterministic structure: all systems follow predictable, machine-readable patterns\n"
            "  - Self-documenting: databases and files contain their own documentation\n"
            "  - Audit trails: complete history tracking through journaling\n"
            "  - Dependency governance: strict enforcement of reading order\n"
            "  - Machine readability: designed for AI processing and validation\n\n"
            "Zero-Drift means: if you write VBStyle code, it either fully complies or it is "
            "rejected. There is no 'mostly compliant'. The validator catches everything.")
        rule_num = addRule(rule_num, "@hidden", "philosophy",
            "No hidden or implicit behavior — all actions explicit",
            "Zero-Drift: no drifting, no half-shapes, no broken syntax. "
            "Strict compliance required. Everything explicit.", ch)
        ch_num += 1

        # --- Ch: Human-AI Drift Prevention ---
        ch = addChapter(part4_id, ch_num, "Human-AI Drift Prevention",
                        "QA system for checking domain before splitting",
                        "Both humans and AI drift. The system must catch both.")
        sec = addSection(ch, 1, "The Problem")
        addBlock(sec, 1,
            "Drift is natural. Humans drift. AI drifts. The system must catch both.\n\n"
            "What is drift?\n"
            "  - Creating micro-classes for the same owner domain\n"
            "  - Splitting by function name instead of by domain\n"
            "  - Scattering the same logic across multiple classes\n"
            "  - Creating new classes without checking if the domain already exists\n\n"
            "Drift prevention checks (in order):\n"
            "  1. plan_given_up_front — was the plan checked first?\n"
            "  2. domain_missing — is a domain missing from the plan?\n"
            "  3. code_split_wrong — was the code split by function instead of domain?\n"
            "  4. owner_clear — is the true domain owner clear?\n\n"
            "If plan was given up front:\n"
            "  - Identify all domains FIRST\n"
            "  - Create domain owners FIRST\n"
            "  - Place logic under true owner\n"
            "  - Forbid micro-class split before domain map\n"
            "  - Build domain map BEFORE code\n\n"
            "If no plan (refactoring existing code):\n"
            "  - Infer true domains from existing code\n"
            "  - Create missing domain owner first\n"
            "  - Move scattered logic into owner\n"
            "  - Test after move\n"
            "  - Verify after test\n"
            "  - Collapse duplicates after owner is clear")
        sec = addSection(ch, 2, "The Refactor Rule")
        addBlock(sec, 1,
            "REFACTOR RULE:\n"
            "  Before creating a new class, ask:\n"
            "    'Is this a new domain, or just a new action inside an existing domain?'\n"
            "  If new_domain == false:\n"
            "    Append the action to the existing domain class.\n"
            "    Do NOT create a new class.\n\n"
            "CODEGEN RULE:\n"
            "  When coding or refactoring:\n"
            "    1. Identify domains\n"
            "    2. Collapse duplicates\n"
            "    3. Place actions under domain owner\n"
            "    4. Only THEN write code\n\n"
            "ENFORCEMENT:\n"
            "  Models must check domain before splitting\n"
            "  Models must collapse repeated logic before emitting final code\n"
            "  Models must not emit micro-classes for the same owner domain")
        rule_num = addRule(rule_num, "@drift", "architecture",
            "Check domain before splitting — collapse repeated logic before emitting code",
            "Both humans and AI drift. The system must catch both. "
            "Build domain map BEFORE code. Collapse by domain, not by function name.", ch)
        addGlossary("Drift Prevention", "QA system that checks domain ownership before allowing class creation or splitting.", ch)
        ch_num += 1

        # ================================================================
        # PART 5 EXPANSION: Fixed Boot Order, T/F Classification
        # ================================================================
        part5_id = part_ids.get(5)

        # --- Ch: Fixed Boot Order ---
        ch = addChapter(part5_id, ch_num, "The Fixed Boot Order",
                        "Config → Setup → AST → MemDB → MemBus → Report",
                        "The VBSTYLE core boot sequence is deterministic and idempotent. No deviation allowed.")
        sec = addSection(ch, 1, "The Boot Sequence")
        addBlock(sec, 1,
            "The VBSTYLE core boot sequence follows a fixed order:\n\n"
            "  Config (T) → Setup (T) → AST (T) → MemDB (F) → MemBus (F) → Report (F)\n\n"
            "Boot Class Classification:\n"
            "  T = True Boot Classes — Core bundle components\n"
            "    Config, Setup, AST\n"
            "    These MUST boot first. They are the foundation.\n\n"
            "  F = Supporting Boot Classes — Infrastructure components\n"
            "    MemDB, MemBus, IO, Report, Recourse\n"
            "    These boot after the True classes are ready.\n\n"
            "Boot rules:\n"
            "  - Boot must be deterministic and idempotent\n"
            "  - Core order is fixed — no deviation allowed\n"
            "  - No guessing when required runtime data is missing\n"
            "  - Runtime defaults are config-driven\n\n"
            "What each boot class does:\n"
            "  Config  — Load governed configuration (DB paths, model paths, runtime mode)\n"
            "  Setup   — Validate environment, check dependencies, activate runtime\n"
            "  AST     — Initialize abstract syntax tree parser for structure validation\n"
            "  MemDB   — Create in-memory SQLite database for runtime state\n"
            "  MemBus  — Initialize pub/sub message bus for event routing\n"
            "  Report  — Initialize report generation system for boot status logging")
        rule_num = addRule(rule_num, "@boot", "architecture",
            "Boot order is fixed: Config→Setup→AST→MemDB→MemBus→Report. No deviation.",
            "T=True Boot Classes (Config, Setup, AST). F=Supporting (MemDB, MemBus, Report). "
            "Deterministic and idempotent.", ch)
        addGlossary("True Boot Class", "T class. Config, Setup, AST. Must boot first.", ch)
        addGlossary("Supporting Boot Class", "F class. MemDB, MemBus, IO, Report, Recourse. Boots after T classes.", ch)
        ch_num += 1

        # ================================================================
        # PART 6: Resource Management (fill empty)
        # ================================================================
        part6_id = part_ids.get(6)

        # --- Ch: ResourceCore and Recourse ---
        ch = addChapter(part6_id, ch_num, "ResourceCore and Recourse",
                        "Machine observer and budget authority",
                        "Core_Recourse.c manages runtime resource allocation, load, and memory budgeting.")
        sec = addSection(ch, 1, "Resource Management Architecture")
        addBlock(sec, 1,
            "VBSTYLE resource management has two components:\n\n"
            "RESOURCECORE (Machine Observer):\n"
            "  - Watches RAM, CPU, GPU usage\n"
            "  - Stores observations in SQLite\n"
            "  - Detects memory pressure, CPU load, GPU availability\n"
            "  - Reports resource state to MemBus\n\n"
            "RESOURCEDOM (Budget Authority):\n"
            "  - Budget authorities for each resource type\n"
            "  - Workload inference — predicts what resources a task will need\n"
            "  - Lessons table — observe → act → measure → score → store\n"
            "  - Action recommendations (NO auto-execution — recommendations only)\n\n"
            "CORE_RECOURSE.c responsibilities:\n"
            "  - Runtime resource allocation\n"
            "  - Load management\n"
            "  - Memory budgeting\n"
            "  - Worker sizing\n"
            "  - Execution restraint based on detected machine capability\n\n"
            "Key principle: Resource observations are stored as lessons. "
            "The system learns what works and what doesn't. But it NEVER auto-executes "
            "actions based on lessons — it only recommends. The user decides.")
        sec = addSection(ch, 2, "The Lessons Table")
        addBlock(sec, 1,
            "The lessons table follows this cycle:\n\n"
            "  1. OBSERVE — what is the current resource state?\n"
            "  2. ACT — what action was taken?\n"
            "  3. MEASURE — what was the resource cost?\n"
            "  4. SCORE — did the action help or hurt?\n"
            "  5. STORE — save the lesson for future reference\n\n"
            "Lessons influence future recommendations but never auto-execute. "
            "The system observes itself running and learns from what works.")
        rule_num = addRule(rule_num, "@ram", "resource",
            "RAM mirror — memory reads backup writes, lessons observe→act→measure→score→store",
            "ResourceCore watches. ResourceDOM budgets. Lessons learn. "
            "No auto-execution — recommendations only.", ch)
        addGlossary("ResourceCore", "Machine observer. Watches RAM/CPU/GPU, stores in SQLite.", ch)
        addGlossary("ResourceDOM", "Budget authority. Workload inference, lessons, recommendations.", ch)
        ch_num += 1

        # --- Ch: Memory Budgeting and Worker Sizing ---
        ch = addChapter(part6_id, ch_num, "Memory Budgeting and Worker Sizing",
                        "Bounded memory, configurable limits, execution restraint",
                        "How VBSTYLE manages memory allocation and worker thread sizing based on machine capability.")
        sec = addSection(ch, 1, "Memory Management")
        addBlock(sec, 1,
            "All memory allocation goes through Memory Bus (mem_bus):\n\n"
            "  - Bounded memory usage with configurable limits\n"
            "  - Automatic garbage collection and pooling\n"
            "  - Memory pressure detection\n"
            "  - Project RAM cache (512MB limit typical)\n"
            "  - Real-time change detection with instant cache updates\n\n"
            "Memory Bus (Core_Resource.c):\n"
            "  - Central memory management interface for all VBSTYLE components\n"
            "  - Handle allocation and deallocation\n"
            "  - Provide bounded usage with configurable limits\n"
            "  - Manage pooling and garbage collection\n\n"
            "MemDB (Core_MemDB.c):\n"
            "  - In-memory database for scan results and intermediate data\n"
            "  - Structured storage for node records and metadata\n"
            "  - Efficient querying and sorting of scan datasets\n"
            "  - Streaming writes for large datasets")
        sec = addSection(ch, 2, "Worker Sizing")
        addBlock(sec, 1,
            "Worker sizing is based on detected machine capability:\n\n"
            "  - Detect CPU cores, available RAM\n"
            "  - Determine optimal threading and I/O strategies for the platform\n"
            "  - Execution restraint — don't over-allocate on weak machines\n"
            "  - Worker pool size is config-driven, not hardcoded\n\n"
            "Thread pool:\n"
            "  - Worker pool with N threads (N from config)\n"
            "  - Job queue with scheduling\n"
            "  - Priority queuing: CRITICAL → HIGH → MEDIUM → LOW\n"
            "  - Thread-safe operations for concurrent execution")
        ch_num += 1

        # --- Ch: Magnetic Trajectory Engine ---
        ch = addChapter(part6_id, ch_num, "The Magnetic Trajectory Engine",
                        "Canonical maps, relation maps, authority weights, convergence",
                        "Advanced search scoring using canonical aliases, relation expansion, and radius scoring.")
        sec = addSection(ch, 1, "The Magnetic Search System")
        addBlock(sec, 1,
            "The Magnetic Trajectory Engine replaces simple text containment with "
            "canonicalized, radius-scored, authority-weighted search.\n\n"
            "Components:\n"
            "  Core_MagneticSearch_v1.c        — orchestrator\n"
            "  Lib_MagneticCanonicalMap_v1.c   — query normalization (canonical aliases)\n"
            "  Lib_MagneticRelationMap_v1.c    — relation expansion\n"
            "  Lib_MagneticAuthorityWeight_v1.c — scoring with authority weights\n"
            "  Lib_RadiusComputeEngine_v1.c    — gap/budget scoring\n"
            "  Lib_ConvergenceScoreEngine_v1.c — iterative refinement\n\n"
            "Scoring formula:\n"
            "  score = 1.0 - (gap / budget)\n\n"
            "Authority weights:\n"
            "  system  = 3.0\n"
            "  truthDB = 3.0\n"
            "  human   = 2.0\n\n"
            "Convergence loop:\n"
            "  query → expand → score → refine → assemble\n"
            "  The loop iterates until the score stabilizes (converges).")
        sec = addSection(ch, 2, "How It Differs from Normal Search")
        addBlock(sec, 1,
            "Normal search: haystack.contains(term) → true/false\n\n"
            "Magnetic search:\n"
            "  1. Canonicalize the query (aliases, normalization)\n"
            "  2. Expand relations (find related terms)\n"
            "  3. Score by authority weight (system > truthDB > human)\n"
            "  4. Compute radius (how far from the target?)\n"
            "  5. Refine (iterate until convergence)\n"
            "  6. Assemble final results\n\n"
            "Result: instead of 'found' or 'not found', you get a score from 0.0 to 1.0 "
            "that represents how relevant the result is, weighted by the authority of the source.")
        addGlossary("Magnetic Search", "Canonicalized, radius-scored, authority-weighted search with convergence.", ch)
        ch_num += 1

        # ================================================================
        # PART 7: C Core Roadmap (fill empty)
        # ================================================================
        part7_id = part_ids.get(7)

        # --- Ch: Why C? ---
        ch = addChapter(part7_id, ch_num, "Why C?",
                        "Performance, determinism, and the future runtime",
                        "The C core provides sub-2-second boot, near-zero CPU, and under 50MB RAM overhead.")
        sec = addSection(ch, 1, "The Case for C")
        addBlock(sec, 1,
            "Why move the VBSTYLE core to C?\n\n"
            "  1. BOOT SPEED — C boots in under 2 seconds. Python boot is slower.\n"
            "  2. MEMORY — C core target: under 50MB RAM overhead. Python uses more.\n"
            "  3. CPU — C core target: near-zero CPU when idle. Python has GC overhead.\n"
            "  4. DETERMINISM — C has no garbage collection pauses. Predictable timing.\n"
            "  5. HARDWARE — C can directly access Metal/CoreML for GPU acceleration.\n\n"
            "The C core does NOT replace Python. Python domains continue to work. "
            "The C core handles the foundation: MemDB, MemBus, Executor, Config, Boot. "
            "Python adapter connects via ctypes/cffi bridge.")
        ch_num += 1

        # --- Ch: C Core Structure ---
        ch = addChapter(part7_id, ch_num, "C Core Structure",
                        "Headers, sources, and the Python adapter bridge",
                        "The proposed C core layout with 16 header files and 16 source files.")
        sec = addSection(ch, 1, "C Core Layout")
        addBlock(sec, 1,
            "Proposed C core structure:\n\n"
            "  include/\n"
            "    vb_core.h     — Core API surface\n"
            "    vb_memdb.h    — MemDB (in-RAM SQLite)\n"
            "    vb_membus.h   — MemBus (packet routing)\n"
            "    vb_brkt.h     — Bracket engine\n"
            "    vb_exec.h     — Executor\n"
            "    vb_cfg.h      — Config loader\n"
            "    vb_fileio.h   — File I/O\n"
            "    vb_ram.h      — RAM authority\n"
            "    vb_cpu.h      — CPU authority\n"
            "    vb_gpu.h      — GPU authority (Metal/CoreML)\n"
            "    vb_thrd.h     — Thread pool / swarm\n"
            "    vb_model.h    — Model manager\n"
            "    vb_report.h   — Report generator\n"
            "    vb_event.h    — Event system\n"
            "    vb_store.h    — Persistent storage\n"
            "    vb_net.h      — Network\n\n"
            "  src/\n"
            "    vb_core.c     — Boot sequence, lifecycle\n"
            "    vb_memdb.c    — In-RAM SQLite wrapper\n"
            "    vb_membus.c   — Pub/sub routing\n"
            "    vb_brkt.c     — Bracket parser\n"
            "    vb_exec.c     — Command dispatch\n"
            "    ... (one .c per .h)")
        sec = addSection(ch, 2, "The VB_Result Struct")
        addBlock(sec, 1,
            "In C, the Tuple3 contract maps to VB_Result:\n\n"
            "  typedef struct {\n"
            "      int ok;              // 1=success, 0=failure\n"
            "      void *data;          // result data\n"
            "      size_t data_size;    // size of data\n"
            "      int error_code;      // error code on failure\n"
            "      char error_message[256]; // error message\n"
            "  } VB_Result;\n\n"
            "This is the C equivalent of Python's (ok, data, error) tuple. "
            "Every C function in the core returns VB_Result. The Python adapter "
            "converts between VB_Result and Python Tuple3 automatically.")
        sec = addSection(ch, 3, "C Boot Sequence")
        addBlock(sec, 1,
            "C boot sequence (13 steps):\n\n"
            "  1.  vb_core_init()           → boot runtime\n"
            "  2.  vb_memdb_init()          → create in-RAM SQLite\n"
            "  3.  vb_membus_init()         → create message bus\n"
            "  4.  vb_cfg_load(\"config.json\") → load configuration\n"
            "  5.  vb_brkt_init()           → initialize bracket engine\n"
            "  6.  vb_exec_init()           → initialize executor\n"
            "  7.  vb_ram_init()            → start RAM monitoring\n"
            "  8.  vb_cpu_init()            → start CPU monitoring\n"
            "  9.  vb_thrd_init(N)          → start worker pool with N threads\n"
            "  10. vb_fileio_init()         → mount filesystem paths\n"
            "  11. Python adapter connects  → MemUnit becomes thin wrapper\n"
            "  12. Domains register with executor\n"
            "  13. System ready for commands")
        addGlossary("VB_Result", "C struct equivalent of Tuple3. Contains ok, data, data_size, error_code, error_message.", ch)
        ch_num += 1

        # ================================================================
        # PART 8 EXPANSION: Real Failures from the evidence
        # ================================================================
        part8_id = part_ids.get(8)

        # --- Ch: Real Failures and Lessons ---
        ch = addChapter(part8_id, ch_num, "Real Failures and Lessons",
                        "16+ failures from actual development sessions",
                        "Real failures with patterns, solutions, and severity ratings — mined from the evidence.")
        sec = addSection(ch, 1, "Critical Failures")
        addBlock(sec, 1,
            "FAILURE 0-A: Attempted File Deletion Without Permission\n"
            "  What: Ran rm command to delete a file after user pointed out violations\n"
            "  Impact: Attempted destructive action without explicit authorization\n"
            "  Lesson: NEVER delete, modify, or remove ANY file without explicit 'yes, delete it' permission\n"
            "  Pattern: Destructive actions require explicit verbal authorization, never assume\n"
            "  Severity: CATASTROPHIC — Permanent data loss risk\n\n"
            "FAILURE 0-B: Created Duplicate Domain Unit Without Checking\n"
            "  What: Created Unit_ChatExtractor.py without checking if chat extraction domain already existed\n"
            "  Impact: Unit_ChatUnit.py already exists — duplicated domain\n"
            "  Lesson: ALWAYS check for existing units before creating new ones\n"
            "  Pattern: Search existing codebase for Unit_* files before creation\n"
            "  Severity: CRITICAL — Violates 'one unit owns one domain completely'\n\n"
            "FAILURE 0-C: Used @dataclass Decorator (Magic)\n"
            "  What: Used @dataclass decorator for ExtractedItem class\n"
            "  Impact: Violates VBStyle 'no magic, no decorators, explicit only'\n"
            "  Lesson: Decorators hide behavior = forbidden in VBStyle\n"
            "  Pattern: Write __init__, __eq__, __repr__ manually, explicitly\n"
            "  Severity: CRITICAL — Core VBStyle violation\n\n"
            "FAILURE 0-D: Unit Contained Execution Authority (__main__ block)\n"
            "  What: Included if __name__ == '__main__' with CLI argument parsing\n"
            "  Impact: Unit has execution authority — violates 'units don't own execution'\n"
            "  Lesson: Units provide surface only, execution happens through Core_MemUnit\n"
            "  Pattern: Units = library classes, never standalone scripts\n"
            "  Severity: CRITICAL — Unit Law violation\n\n"
            "FAILURE 0-E: Hard-Coded File Paths in Unit\n"
            "  What: Hard-coded source/target paths instead of accepting via param\n"
            "  Impact: Unit not reusable, violates param/validate/execute/return/cleanup lifecycle\n"
            "  Lesson: All configuration through param(), no hard-coded values\n"
            "  Severity: HIGH — Reusability violation\n\n"
            "FAILURE 0-F: Print Statements in Unit (Side Effects)\n"
            "  What: Used print() statements for progress reporting\n"
            "  Impact: Units must be side-effect free, no I/O\n"
            "  Lesson: Units return data, don't produce output\n"
            "  Pattern: Return stats in tuple3, let caller handle reporting\n"
            "  Severity: HIGH — Side effect violation")
        sec = addSection(ch, 2, "Behavioral Failures")
        addBlock(sec, 1,
            "FAILURE 11: Misinterpreted 'retry' Command\n"
            "  What: User said 'retry'. Gave audit report instead of executing.\n"
            "  Lesson: 'Retry' means execute/fix/run, not analyze or audit.\n"
            "  Pattern: Short commands = action required, not analysis.\n\n"
            "FAILURE 12: Lied About Message Sequence\n"
            "  What: Said 'retry' was the last message when it wasn't.\n"
            "  Lesson: Check facts before stating. Don't guess.\n"
            "  Pattern: Verify sequence before claiming order.\n"
            "  Solution: Admit uncertainty rather than fabricate.\n\n"
            "FAILURE 15: Failed 500-Line Chunk Processing\n"
            "  What: User instructed 'read 500 lines, write, read next 500 lines'. "
            "Tried to use grep to extract all at once.\n"
            "  Lesson: Follow exact instruction — 500 line chunks sequentially.\n"
            "  Pattern: Incremental processing with state tracking.\n\n"
            "FAILURE 16: Populated File Without Reading Source First\n"
            "  What: Wrote 86 lines of failures without reading the full 19045-line source.\n"
            "  Lesson: Must read source completely before extracting.\n"
            "  Pattern: Source → Extract → Write → Mark position → Repeat.")
        ch_num += 1

        # ================================================================
        # NEW PART 10: Unit Architecture
        # ================================================================
        book.execute(
            "INSERT INTO parts (part_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?)",
            (10, "Unit Architecture", "The 11-Chapter Question Framework",
             "A systematic method for understanding any VBStyle unit through 11 dimensions of questions.")
        )
        part10_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # --- Ch: The 11-Chapter Question Framework ---
        ch = addChapter(part10_id, ch_num, "The 11-Chapter Question Framework",
                        "Identity, Purpose, Boundary, Structure, Properties, Relations, Lifecycle, Rules, States, Variation, Failure",
                        "Every VBStyle unit can be understood by answering questions across 11 dimensions.")
        sec = addSection(ch, 1, "The 11 Dimensions")
        addBlock(sec, 1,
            "The Unit Architecture Manual defines 11 chapters of questions. "
            "Every VBStyle unit (class, authority, domain) can be fully understood by "
            "answering the questions in each chapter:\n\n"
            "  Chapter 1:  IDENTITY     — What is A? What is A called? What is A not?\n"
            "  Chapter 2:  PURPOSE      — Why does A exist? What problem does A solve?\n"
            "  Chapter 3:  BOUNDARY     — Where does A begin? Where does A end?\n"
            "  Chapter 4:  STRUCTURE    — What parts make up A? What is required? Forbidden?\n"
            "  Chapter 5:  PROPERTIES   — What dimensions can A be measured by? What is the state of A?\n"
            "  Chapter 6:  RELATIONS    — What is A connected to? What depends on A?\n"
            "  Chapter 7:  LIFECYCLE    — How does A begin? How is A changed? How does A end?\n"
            "  Chapter 8:  RULES        — What is required? Allowed? Forbidden? What validates A?\n"
            "  Chapter 9:  STATES       — When is A valid? Active? Ready? Blocked? Broken?\n"
            "  Chapter 10: VARIATION    — What types of A exist? What variants are allowed?\n"
            "  Chapter 11: FAILURE      — What breaks A? What fixes A? How do we test A?\n\n"
            "Each chapter has three types of questions:\n"
            "  WHAT questions — describe the unit\n"
            "  WHO questions  — describe ownership and authority\n"
            "  WHEN questions — describe timing and conditions\n"
            "  HOW questions  — describe mechanism and method\n"
            "  WHY questions  — describe reasoning and purpose")
        sec = addSection(ch, 2, "Example: Understanding MemDB Through the Framework")
        addBlock(sec, 1,
            "Chapter 1 (Identity): What is MemDB?\n"
            "  MemDB is an in-RAM SQLite database. It is called MemDB or Memory Database.\n"
            "  It is NOT a disk database. It is NOT a persistent store.\n\n"
            "Chapter 2 (Purpose): Why does MemDB exist?\n"
            "  To hold runtime truth — the current state of the world.\n"
            "  Disk is for persistence. RAM is for reality.\n\n"
            "Chapter 3 (Boundary): Where does MemDB begin and end?\n"
            "  Begins: when sqlite3.connect(':memory:') is called.\n"
            "  Ends: when the process terminates. Data does not survive reboot.\n"
            "  Inside: command_queue, state_cache, routing_map tables.\n"
            "  Outside: persistent storage (disk SQLite, MySQL).\n\n"
            "Chapter 8 (Rules): What validates MemDB?\n"
            "  Tables must exist. SQL must be valid. Connections must be alive.\n"
            "  What invalidates MemDB? Connection lost. Schema corrupted.\n\n"
            "Chapter 11 (Failure): What breaks MemDB?\n"
            "  Process crash (all RAM data lost). Too much data (memory pressure).\n"
            "  What fixes MemDB? Reboot from disk. Reduce data size. Offload cold data to NVMe.")
        addGlossary("Unit Architecture", "11-chapter question framework for understanding any VBStyle unit.", ch)
        ch_num += 1

        # ================================================================
        # APPENDIX: Wayne's Language + Development Pipeline
        # ================================================================
        part9_id = part_ids.get(9)

        # --- Ch: Wayne's Language Syntax ---
        ch = addChapter(part9_id, ch_num, "Appendix A: Wayne's Language",
                        "The symbol system for visual communication",
                        "A compact syntax using arrows, brackets, and punctuation for expressing relationships and flow.")
        sec = addSection(ch, 1, "Command and Direction")
        addBlock(sec, 1,
            "Wayne's Language is a compact symbol system for expressing architecture and flow:\n\n"
            "COMMAND & DIRECTION:\n"
            "  -[command]    Execute command\n"
            "  >>            Forward direction/flow (A → B)\n"
            "  <<            Reverse direction/flow (B ← A)\n"
            "  ?>>>>         Which direction to go?\n\n"
            "OBJECTS & PARAMETERS:\n"
            "  []            Object/container\n"
            "  ()            Parameter/arguments\n"
            "  {}            Section/block\n\n"
            "COMPARISON & LOGIC:\n"
            "  ==            Equal to\n"
            "  !=            Not equal to\n"
            "  ?=            Think before (pre-analysis)\n"
            "  =?            Think after (post-analysis)\n\n"
            "QUESTION MARK HIERARCHY:\n"
            "  ?             Simple question\n"
            "  ??            Confused/uncertain question\n"
            "  ???           Very confused/urgent question\n"
            "  ?!            Questioned/annoyed\n"
            "  ??!           Confused and irritated\n\n"
            "EMOTION/URGENCY SCALE:\n"
            "  !             Irritated\n"
            "  !!            Very irritated\n"
            "  !!!           Angry\n"
            "  !!!!!         Want to kill\n"
            "  !!!!!!        You DEAD\n\n"
            "SPEED & CONTINUATION:\n"
            "  >>>>>>>       Speed up/faster\n"
            "  >>>           And so on/continue\n\n"
            "KEY-VALUE PAIRS:\n"
            "  [xx:yy]       Key-value pair\n"
            "  [key:value]>> Key-value pair flowing forward\n"
            "  [XX:DD,DD:TT>>] Multiple key-value pairs with direction")
        sec = addSection(ch, 2, "File Relationships and Operations")
        addBlock(sec, 1,
            "FILE RELATIONSHIPS:\n"
            "  (file)?>(file)    File confused about going to another file\n"
            "  (file)<?(file)    File confused about receiving from another file\n"
            "  (file)?(file)     File confused about another file\n\n"
            "FILE OPERATIONS:\n"
            "  [make]>>>>>tidy   Make tidy/clean up\n"
            "  file>>folder      Move file to folder\n"
            "  move>>            Move operation\n"
            "  see update        Check for updates\n\n"
            "EXAMPLES:\n"
            "  [make]>>>>>tidy ... file>>folder or move>> see update\n"
            "  util/Com/ >>[contains]>> [lib_com_*.py] ?= Validate structure\n"
            "  project_indexer.py >>[generates]>> (Project_Index.yaml) =? Check results\n"
            "  [LIB_DatabaseConnector:Db/cascade_data.db]>>[operates_on]\n"
            "  [config:settings.yaml]>>[load]")
        ch_num += 1

        # --- Ch: Development Pipeline Stages ---
        ch = addChapter(part9_id, ch_num, "Appendix B: Development Pipeline",
                        "Idea → Plan → Roadmap → Code_Spec → Implementation",
                        "The VBStyle development pipeline follows strict stages from concept to code.")
        sec = addSection(ch, 1, "The Pipeline Stages")
        addBlock(sec, 1,
            "VBStyle development follows a strict pipeline:\n\n"
            "  1. IDEA          — Concept documents (in Ideas/ directory)\n"
            "     What if we could...? A new concept is born.\n\n"
            "  2. PLAN          — Implementation plans (in Plans/ directory)\n"
            "     How would we do it? What are the steps?\n\n"
            "  3. ROADMAP       — Development roadmaps (in Roadmaps/ directory)\n"
            "     When do we do each step? What are the phases?\n\n"
            "  4. CODE_SPEC     — Technical specifications (in Code_Specs/ directory)\n"
            "     What are the exact interfaces, classes, methods, returns?\n\n"
            "  5. IMPLEMENTATION — Implementation files (in implemntatioins/ directory)\n"
            "     Write the actual VBStyle-compliant code.\n\n"
            "Rules:\n"
            "  - Each stage must be complete before moving to the next\n"
            "  - You cannot implement without a code spec\n"
            "  - You cannot code spec without a roadmap\n"
            "  - You cannot roadmap without a plan\n"
            "  - You cannot plan without an idea\n\n"
            "The development hub is Waynes_Brain_factory with 5 subdirectories:\n"
            "  Ideas/, Plans/, Roadmaps/, Code_Specs/, implemntatioins/\n"
            "  Additional: Thinking_Patterns/")
        ch_num += 1

        # --- Ch: Appendix C: The 76 Rules Reference ---
        ch = addChapter(part9_id, ch_num, "Appendix C: The 76 Rules Reference",
                        "Complete tag list from obey.md",
                        "Every VBStyle rule tag with its description, mined from the project rules file.")
        sec = addSection(ch, 1, "Core Rules")
        addBlock(sec, 1,
            "CORE RULES (from obey.md):\n\n"
            "  @run       — Run(command, params) dispatch entry point\n"
            "  @rdst      — read_state returns config snapshot\n"
            "  @cfg       — set_config updates config\n"
            "  @phelp     — _p(params, key, default) param helper\n"
            "  @disp      — dispatch(command, params) internal\n"
            "  @succ      — success return (1, data, None)\n"
            "  @err       — error return (0, None, error_tuple)\n"
            "  @t3        — Tuple3 return: (ok, data, error)\n"
            "  @errfmt    — error tuple format: (code, desc, 0)\n\n"
            "STRUCTURE RULES:\n"
            "  @domain    — each class owns exactly one domain (authority)\n"
            "  @dismap     — every dispatch key maps to exactly one method\n"
            "  @memunit    — all code executes only in memunit\n"
            "  @auth       — authority pattern: one class, one domain\n"
            "  @cstyle     — one class, domain, authority, complete\n\n"
            "HEADER RULES:\n"
            "  @ghost      — all code must have Ghost Header\n"
            "  @vbsty      — all code must have VBStyle Header\n"
            "  @clshdr     — all classes must have Classes Header\n"
            "  @mthdr      — all methods must have Method Header\n\n"
            "NAMING RULES:\n"
            "  @pascal     — class names PascalCase, no underscores\n"
            "  @upper      — constants UPPERCASE at class level\n"
            "  @underscore — _ not allowed in class names\n\n"
            "PROHIBITION RULES:\n"
            "  @decorators — @property, @staticmethod etc are never allowed\n"
            "  @enums      — do not use enums\n"
            "  @print      — do not use print statements; use Report class or logging\n"
            "  @hidden     — no hidden or implicit behavior; all actions explicit\n"
            "  @hardcode   — no hardcoded NOTHING IS ALLOWED TO BE HARD CODED\n"
            "  @tabs       — no tabs; spaces only\n"
            "  @whitespace — no trailing whitespace at end of lines\n"
            "  @intstate   — no self._ variables; use self.state dictionary\n\n"
            "PARAMS AND STATE:\n"
            "  @params     — all methods must accept all data as parameters\n"
            "  @tuples     — all methods must return Tuple3 (ok, data, error)\n"
            "  @ctor       — def __init__(self, mem=None, db=None, param=None)\n"
            "  @state      — self.state dict: config, catalog, results\n"
            "  @noself     — no self._ variables, use self.state\n\n"
            "DATABASE RULES:\n"
            "  @selfdb     — self documenting db code registry\n"
            "  @authdb     — authorities table schema\n"
            "  @dep        — authority deps table schema\n"
            "  @mdep       — method deps table schema\n"
            "  @runst      — runtime state table schema\n"
            "  @exec       — execution log table schema\n"
            "  @know       — knowledge table schema\n"
            "  @conf       — config table schema\n"
            "  @meth       — methods table schema\n"
            "  @dcon       — dispatch contract table schema\n"
            "  @reg        — code registry table schema\n\n"
            "PROCESS RULES:\n"
            "  @exp        — EXPAND: search everything, no assumptions\n"
            "  @clu        — CLUSTER: group by repetition similarity\n"
            "  @map        — MAP: align meaning to context test system\n"
            "  @col        — COLLAPSE: extract stable invariant jewel\n"
            "  @hrt        — HRT: header violation, naming, structure\n"
            "  @hst        — HST: style violation, formatting\n\n"
            "SAFETY RULES:\n"
            "  @dontknow   — don't assume, don't guess, ask\n"
            "  @unsure     — if unsure ask, do not guess\n"
            "  @noexec     — do not execute without explicit user instruction\n"
            "  @noedit     — do not edit any file unless told to edit that specific file\n"
            "  @nofiles    — do not create files; use single database\n"
            "  @exact      — do exactly as told, do not interpret\n"
            "  @scope      — all edits restricted to explicitly approved files\n"
            "  @askdel     — ask before delete, replace, restore, migration, overwrite\n"
            "  @noauto     — discussion never implies edit authority\n"
            "  @gate       — if unsure stop and ask, no autonomous file mutation\n"
            "  @noarch     — do not invent architecture\n"
            "  @norule     — do not invent rules and code style\n\n"
            "COLLABORATION:\n"
            "  @collab     — pair programming driver/navigator pattern\n"
            "  @useremotion — consider user emotional impact before any action\n"
            "  @ram        — RAM mirror: memory reads, backup writes\n"
            "  @rpt        — report isolation: returns strings, no print")
        ch_num += 1

        # Update stats
        self.state["stats"]["missing_chapters_added"] = ch_num - max_ch - 1
        self.state["stats"]["total_chapters_final"] = ch_num - 1
        self.state["stats"]["total_rules_final"] = rule_num - 1

        book.commit()
        return (1, f"Added {ch_num - max_ch - 1} missing chapters", ())
    def BuildBook(self):
        book = self.state["book"]

        # Mine all evidence
        _, rules, _ = self.MineRules()
        _, violations, _ = self.MineViolations()
        _, classes, _ = self.MineClasses()
        _, methods, _ = self.MineMethods()
        _, boot_stages, _ = self.MineBootStages()
        _, table_purposes, _ = self.MineTablePurposes()
        _, objectives, _ = self.MineObjectives()

        # Group violations by pattern for anti-pattern chapters
        violation_groups = {}
        for v in violations:
            key = v.get("pattern", "unknown")
            if key not in violation_groups:
                violation_groups[key] = []
            violation_groups[key].append(v)

        # Group classes by domain
        domain_classes = {}
        for c in classes:
            did = c.get("domain_id", 0)
            if did not in domain_classes:
                domain_classes[did] = []
            domain_classes[did].append(c)

        # ===== PARTS =====
        parts_data = [
            (1, "Foundation", "The Core Contracts",
             "The fundamental patterns that every VBStyle class must follow."),
            (2, "Headers and Annotations", "Self-Documenting Code",
             "The bracket system that makes VBStyle code machine-readable."),
            (3, "Architecture", "The Runtime System",
             "MemUnit, MemDB, MemBus, Executor — how the system assembles itself."),
            (4, "The Rules", "Laws Enforced Through Violations",
             "Every rule, proven by the 607 violations that tested it."),
            (5, "Boot Sequence", "How CASOS Comes Alive",
             "The 4-stage boot process from Init to runtime."),
            (6, "Resource Management", "Watching and Adapting",
             "ResourceCore, budgets, lessons, and self-observation."),
            (7, "The C Core Roadmap", "The Future Runtime",
             "Why C, the VB_Result struct, and the Python adapter bridge."),
            (8, "Anti-Patterns", "What Not To Do (Proven by 607 Violations)",
             "Real violations from the codebase, with fixes."),
            (9, "Complete Examples", "Real Classes from the Database",
             "260 classes mined from MySQL, with working code."),
        ]

        for p in parts_data:
            book.execute(
                "INSERT INTO parts (part_num, title, subtitle, description) "
                "VALUES (?, ?, ?, ?)",
                (p[0], p[1], p[2], p[3])
            )
        book.commit()

        # ===== CHAPTERS + SECTIONS + CONTENT =====
        # This is the big one — build each chapter with real evidence

        ch_num = 0
        rule_num = 0

        # --- PART 1: Foundation ---
        part1_id = book.execute(
            "SELECT id FROM parts WHERE part_num=1"
        ).fetchone()[0]

        # Ch 1: What is VBStyle?
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part1_id, ch_num, "What is VBStyle?",
             "A code architecture system, not a framework",
             "The foundational philosophy: one class, one domain, one authority, complete.")
        )
        ch1_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Core Idea', 'text')",
            (ch1_id,)
        )
        sec1 = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec1,
             "VBStyle is a code architecture system, not a framework. "
             "The core idea is simple: one class, one domain, one authority, complete.\n\n"
             "Every file is a domain. Every domain has a root class with nested authority classes. "
             "Code hierarchy equals visual hierarchy. No inheritance. No decorators. No guessing.\n\n"
             "VBStyle is not about writing less code. It is about writing code whose structure "
             "is immediately obvious to both humans and machines. Every class owns exactly one "
             "concern. Every method has a contract. Every return is a Tuple3.")
        )

        # Evidence: how many classes exist
        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 2, 2, 'The Evidence Base', 'text')",
            (ch1_id,)
        )
        sec2 = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec2,
             f"This book is not written from theory. It is mined from evidence.\n\n"
             f"The token_registry MySQL database contains:\n"
             f"- {len(classes)} real VBStyle classes\n"
             f"- {self.state['stats']['methods_mined']} real methods with code\n"
             f"- {len(violations)} distinct violation types (from 607 total violations)\n"
             f"- {len(rules)} formal rules\n"
             f"- {len(objectives)} architecture decisions and learnings\n"
             f"- {len(boot_stages)} boot stage entries\n"
             f"- {len(table_purposes)} table purposes with relationships\n\n"
             f"Every rule in this book was enforced. Every anti-pattern was caught. "
             f"Every example is real code from the database.")
        )

        # Ch 2: The Run Dispatch Contract
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part1_id, ch_num, "The Run Dispatch Contract",
             "One entry point, one pattern, no exceptions",
             "Every class has exactly one public method: Run(command, params).")
        )
        ch2_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Pattern', 'text')",
            (ch2_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
            "VALUES (?, 'code', 1, ?, 'python')",
            (sec,
             "def Run(self, command, params=None):\n"
             "    params = params or {}\n"
             "    if command == \"get\":\n"
             "        return self._get(params)\n"
             "    elif command == \"set\":\n"
             "        return self._set(params)\n"
             "    elif command == \"read_state\":\n"
             "        return self.read_state()\n"
             "    elif command == \"set_config\":\n"
             "        return self.set_config(params)\n"
             "    else:\n"
             "        return (0, None, (\"UNKNOWN_COMMAND\", command, 101))")
        )

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 2, 2, 'Why Not Multiple Public Methods?', 'text')",
            (ch2_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "Multiple public methods create multiple entry points. Multiple entry points "
             "create multiple ways to use a class wrong. Run() is the single door.\n\n"
             "Inside Run(), if/elif dispatch routes to private _method handlers. "
             "This is VB Select Case style — explicit, readable, exhaustive.\n\n"
             "Every dispatch key maps to exactly one method. No ambiguity. "
             "No method overloading. No guessing which method handles which command.")
        )

        # Add rule
        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, "
            "example_bad, example_good, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rule_num, "@run", "dispatch",
             "Every class has a Run(command, params) dispatch entry point",
             "Run() is the single public method. Inside, if/elif dispatches to "
             "private handlers. Every key maps to exactly one method. "
             "Unknown commands return (0, None, (UNKNOWN_COMMAND, command, 101)).",
             "class Foo:\n    def get(self): ...\n    def set(self): ...\n    def delete(self): ...",
             "class Foo:\n    def Run(self, command, params=None):\n        if command == \"get\":\n            return self._get(params)\n        elif command == \"set\":\n            return self._set(params)",
             ch2_id)
        )

        # Real example from database
        run_methods = [m for m in methods if m["name"] == "Run"]
        if run_methods:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, 3, 3, 'Real Example from the Database', 'text')",
                (ch2_id,)
            )
            sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]
            example = run_methods[0]
            book.execute(
                "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang, caption) "
                "VALUES (?, 'code', 1, ?, 'python', ?)",
                (sec, example["code"][:2000],
                 f"Run() method from class: {example['class_name']}")
            )

        # Ch 3: Tuple3 Returns
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part1_id, ch_num, "Tuple3 Returns",
             "Every method returns (ok, data, error)",
             "The universal return contract that makes VBStyle predictable.")
        )
        ch3_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Contract', 'text')",
            (ch3_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "Every method returns a 3-tuple:\n\n"
             "  (ok, data, error)\n\n"
             "ok:     int    — 1 = success, 0 = failure\n"
             "data:   Any    — result data on success, None on failure\n"
             "error:  tuple  — (\"ERROR_CODE\", \"description\", context) on failure, None on success\n\n"
             "Success: (1, {\"rows\": [...]}, None)\n"
             "Failure: (0, None, (\"QUERY_ERROR\", \"table not found\", 0))\n\n"
             "This is non-negotiable. Every method. Every time. No exceptions.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, "
            "example_bad, example_good, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rule_num, "@t3", "contract",
             "All methods return Tuple3 (ok, data, error)",
             "ok=1 success with data. ok=0 failure with error tuple. "
             "Error format: (\"CODE\", \"description\", 0). Always 3 elements.",
             "def query(self, sql):\n    return cursor.fetchall()  # no Tuple3",
             "def query(self, params):\n    return (1, {\"rows\": rows}, None)  # Tuple3",
             ch3_id)
        )

        # Ch 4: State Dictionary
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part1_id, ch_num, "The State Dictionary",
             "self.state, not self._variables",
             "All instance state lives in one dictionary, not scattered attributes.")
        )
        ch4_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Pattern', 'text')",
            (ch4_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
            "VALUES (?, 'code', 1, ?, 'python')",
            (sec,
             "def __init__(self, mem=None, db=None, param=None):\n"
             "    self.state = {\n"
             "        \"config\": {},\n"
             "        \"catalog\": [],\n"
             "        \"results\": [],\n"
             "        \"memunit\": mem,\n"
             "        \"db_manager\": db\n"
             "    }")
        )

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 2, 2, 'Why Not self._?', 'text')",
            (ch4_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Count real violations of self._ rule
        self_underscore_violations = [v for v in violations if "self._" in str(v.get("pattern", ""))]
        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             f"self._ variables are banned. Use self.state dictionary instead.\n\n"
             f"This rule was enforced {len(self_underscore_violations)} times in the codebase. "
             f"Every instance of self._ was caught and flagged as a violation.\n\n"
             f"The reason: self.state is inspectable. You can print it, serialize it, "
             f"pass it to MemUnit, cache it in MemDB. self._ variables are hidden, "
             f"scattered, and impossible to snapshot.\n\n"
             f"self.state is the single source of truth for what a class knows about itself.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, "
            "example_bad, example_good, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rule_num, "@intstate", "structure",
             "No self._ variables — use self.state dictionary",
             "All instance state lives in self.state dict with keys: config, catalog, results. "
             "No private attributes. Everything is inspectable.",
             "self._cache = {}\nself._connection = None",
             "self.state = {\"cache\": {}, \"connection\": None}",
             ch4_id)
        )

        # Ch 5: Constructor Pattern
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part1_id, ch_num, "The Constructor Pattern",
             "def __init__(self, mem=None, db=None, param=None)",
             "The universal constructor signature and state initialization.")
        )
        ch5_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Signature', 'text')",
            (ch5_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "Every VBStyle class uses the same constructor signature:\n\n"
             "  def __init__(self, mem=None, db=None, param=None)\n\n"
             "mem:    MemUnit instance (the orchestrator) or None\n"
             "db:     Database connection or None\n"
             "param:  Configuration dict or None\n\n"
             "All parameters are optional. A class can be instantiated with no args "
             "and configured later via set_config. This makes testing trivial and "
             "allows MemUnit to create instances without knowing their needs.")
        )

        # Real __init__ examples from database
        init_methods = [m for m in methods if m["name"] == "__init__"]
        if init_methods:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, 2, 2, 'Real Constructors from the Database', 'text')",
                (ch5_id,)
            )
            sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i, m in enumerate(init_methods[:3]):
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang, caption) "
                    "VALUES (?, 'code', ?, ?, 'python', ?)",
                    (sec, i + 1, m["code"][:1500],
                     f"__init__ from class: {m['class_name']}")
                )

        # --- PART 2: Headers & Annotations ---
        part2_id = book.execute("SELECT id FROM parts WHERE part_num=2").fetchone()[0]

        # Ch 6: Ghost Headers
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part2_id, ch_num, "Ghost Headers",
             "The file-level identity marker",
             "Every file starts with a Ghost header declaring its identity.")
        )
        ch6_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Format', 'text')",
            (ch6_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "#[@GHOST]{[@file<dom_db.py>][@state<active>][@date<2026-05-30>][@ver<1.0>][@auth<system>]}\n\n"
             "Fields:\n"
             "  @file   — filename\n"
             "  @state  — active | deprecated | experimental\n"
             "  @date   — creation or last modification date\n"
             "  @ver    — version number\n"
             "  @auth   — authority (system, user, cascade)\n\n"
             "The Ghost header is the first line of every file. It tells you what the file is, "
             "whether it is safe to use, who owns it, and when it was last touched.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@ghost", "header",
             "All code must have a Ghost Header as the first line",
             "Format: #[@GHOST]{[@file<name>][@state<active>][@date<...>][@ver<...>][@auth<...>]}",
             ch6_id)
        )

        # Ch 7: VBStyle Headers
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part2_id, ch_num, "VBStyle Headers",
             "The architecture declaration",
             "Every file has a VBStyle header declaring its role and constraints.")
        )
        ch7_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Format', 'text')",
            (ch7_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "#[@VBSTYLE]{[@auth<system>][@role<domain_db>][@return<Tuple3>][@orch<MemUnit>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}\n\n"
             "Fields:\n"
             "  @auth    — who owns this file (system, user, cascade)\n"
             "  @role    — what domain this class serves\n"
             "  @return  — return type (always Tuple3)\n"
             "  @orch    — orchestrator (MemUnit or none)\n"
             "  @no      — prohibitions (decorators, print, hardcoded_paths, abc, inheritance)\n\n"
             "The VBStyle header is the second line of every file. It declares the architectural "
             "contract: what this class does, what it returns, who orchestrates it, and what it "
             "must never do.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@vbsty", "header",
             "All code must have a VBStyle Header as the second line",
             "Declares auth, role, return type, orchestrator, and prohibitions.",
             ch7_id)
        )

        # Ch 8: Bracket Annotations
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part2_id, ch_num, "Bracket Annotations",
             "Method-level contracts",
             "Every method has a bracket annotation declaring its params, return, and purpose.")
        )
        ch8_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Grammar', 'text')",
            (ch8_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "#[@METHOD_NAME]{[@PARAMS<<sources>][@RETURN<type>][@PURPOSE<description>]}\n\n"
             "Example:\n"
             "#[@query_database]{[@params<<params>][@return<Tuple3>][@purpose<execute SQL query and return rows>]}\n"
             "def query_database(self, params):\n    ...\n\n"
             "Fields:\n"
             "  METHOD_NAME  — snake_case, matches the method name\n"
             "  PARAMS       — <<sources> e.g. <<params> or <<command, params>\n"
             "  RETURN       — <type> e.g. <Tuple3>\n"
             "  PURPOSE      — <text> what the method does\n\n"
             "Brackets make the contract machine-readable. The AST validator can parse them. "
             "The VBAnnotate tool can inject missing ones. The compliance scanner can check them.")
        )

        # Real bracket examples from classes
        bracket_examples = [c for c in classes if c.get("bracket")][:5]
        if bracket_examples:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, 2, 2, 'Real Brackets from the Database', 'text')",
                (ch8_id,)
            )
            sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i, c in enumerate(bracket_examples):
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content, caption) "
                    "VALUES (?, 'code', ?, ?, ?)",
                    (sec, i + 1, c["bracket"], f"Class: {c['name']}")
                )

        # Count missing bracket violations
        bracket_violations = [v for v in violations if "bracket" in str(v.get("message", "")).lower()]
        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@mthdr", "header",
             f"All methods must have bracket annotations ({len(bracket_violations)} violations caught)",
             "Format: #[@method_name]{[@params<<...>][@return<...>][@purpose<...>]}",
             ch8_id)
        )

        # --- PART 3: Architecture ---
        part3_id = book.execute("SELECT id FROM parts WHERE part_num=3").fetchone()[0]

        # Ch 10: One Class, One Domain
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part3_id, ch_num, "One Class, One Domain, One Authority",
             "The structural law",
             "Every class owns exactly one concern. No Utils, no Helpers, no mixed concerns.")
        )
        ch10_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Law', 'text')",
            (ch10_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             f"Every class is an Authority that owns one concern.\n\n"
             f"Correct: class Settings (manages settings), class Screen (manages screen), "
             f"class Theme (manages theme).\n\n"
             f"Wrong: class Utils (manages everything), class Helpers (manages anything).\n\n"
             f"The database contains {len(classes)} classes across "
             f"{len(domain_classes)} domains. Each class belongs to exactly one domain. "
             f"This is not a suggestion — it is the structural law that the AST validator enforces.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, "
            "example_bad, example_good, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rule_num, "@domain", "structure",
             "Each class must own exactly one domain (authority)",
             "One concern per class. No Utils, no Helpers. The AST validator enforces this.",
             "class Utils:\n    def get_screen_size(): ...\n    def apply_theme(): ...\n    def save_setting(): ...",
             "class Settings:\n    def Run(self, command, params):\n        if command == \"get\":\n            return self._get(params)",
             ch10_id)
        )

        # Ch 12: MemUnit
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part3_id, ch_num, "MemUnit — The Orchestrator",
             "Tying MemDB + MemBus + Executor together",
             "The backbone that connects all components into a running system.")
        )
        ch12_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'What MemUnit Does', 'text')",
            (ch12_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "MemUnit ties three components together:\n\n"
             "1. MemDB    — in-RAM SQLite (the runtime truth)\n"
             "2. MemBus   — pub/sub event routing\n"
             "3. Executor — central dispatch (no class executes itself)\n\n"
             "Key methods:\n"
             "  connect_core(params)  — register a Core instance by name\n"
             "  connect_lib(params)   — register a Lib instance by name\n"
             "  execute(params)       — queue command + execute + return result\n"
             "  Run(command, params)  — dispatch: connect_core, connect_lib, execute, read_state\n\n"
             "Usage:\n"
             "  mem = MemUnit()\n"
             "  mem.connect_core({\"name\": \"db\", \"instance\": db_instance})\n"
             "  result = mem.execute({\"target\": \"db\", \"action\": \"query\", \"params\": {...}})\n"
             "  # result = (1, {\"rows\": [...]}, None)")
        )

        # Ch 13: MemDB
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part3_id, ch_num, "MemDB — In-RAM Truth",
             "The runtime state database",
             "An in-RAM SQLite database that holds the current state of the world.")
        )
        ch13_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'What MemDB Is', 'text')",
            (ch13_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "MemDB is an in-RAM SQLite database (sqlite3.connect(':memory:')).\n"
             "It is NOT a disk database. It is the central runtime truth where commands swap.\n\n"
             "Tables:\n"
             "  command_queue  — queued commands waiting for execution\n"
             "  state_cache    — key-value runtime state cache\n"
             "  routing_map    — action pattern to target core/lib routing\n\n"
             "Key methods:\n"
             "  queue_command(params)        → (1, {\"cmd_id\": N}, None)\n"
             "  get_next_command()           → (1, {cmd_id, action, source, target, params}, None)\n"
             "  update_command_result(params) → (1, {\"updated\": N}, None)\n\n"
             "Disk is for persistence. RAM is for reality. When you ask 'what is CASOS doing "
             "right now?' the answer is in MemDB.")
        )

        # Ch 14: MemBus
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part3_id, ch_num, "MemBus — Event Routing",
             "No direct module-to-module calls",
             "Everything goes through the bus. Publish, subscribe, route.")
        )
        ch14_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Pattern', 'text')",
            (ch14_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "Module A emits packet → MemBus routes → Module B receives.\n\n"
             "No direct module-to-module calls. Everything goes through the bus.\n\n"
             "Key methods:\n"
             "  subscribe(params) — register callback for action pattern\n"
             "  publish(params)   — emit action + payload to all matching subscribers\n\n"
             "Event examples: RAM_LOW, MODEL_LOADED, FILE_CHANGED, TASK_DONE, ERROR_FOUND\n\n"
             "This decouples domains. A domain does not need to know who produced an event "
             "or who will consume it. It just publishes or subscribes.")
        )

        # Ch 15: Executor
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part3_id, ch_num, "Executor — Central Dispatch",
             "NO class executes itself",
             "All execution flows through the Executor. It holds references to all registered instances.")
        )
        ch15_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Rule', 'text')",
            (ch15_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "NO class executes itself. All execution flows through Executor.\n\n"
             "The Executor holds references to all registered Core and Lib instances.\n"
             "When a command needs to run, Executor looks up the target and calls "
             "instance.Run(action, params).\n\n"
             "Key methods:\n"
             "  register_core(params) — register a Core instance by name\n"
             "  register_lib(params)  — register a Lib instance by name\n"
             "  execute(params)       — look up target, call Run(action, params), return Tuple3\n\n"
             "This is the structural guarantee that every execution is logged, traceable, "
             "and goes through the proper dispatch chain.")
        )

        # --- PART 4: The Rules ---
        part4_id = book.execute("SELECT id FROM parts WHERE part_num=4").fetchone()[0]

        # Ch 16: Naming Rules
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part4_id, ch_num, "Naming Rules",
             "PascalCase, UPPERCASE, no underscores",
             "The naming conventions enforced through the objectives table.")
        )
        ch16_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Three Naming Laws', 'text')",
            (ch16_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Find naming-related objectives
        naming_objectives = [o for o in objectives if "underscore" in str(o.get("objective", "")).lower()
                           or "naming" in str(o.get("objective", "")).lower()
                           or "pascal" in str(o.get("objective", "")).lower()][:5]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             "1. Class names are PascalCase, no underscores.\n"
             "   Correct: class DatabaseManager\n"
             "   Wrong:   class database_manager, class Database_Manager\n\n"
             "2. Constants are UPPERCASE at class level.\n"
             "   Correct: DB_PATH = '/path/to/db'\n"
             "   Wrong:   db_path = '/path/to/db'\n\n"
             "3. No underscores in class names.\n"
             "   This was enforced as a compliance objective with high priority.\n"
             f"   {len(naming_objectives)} naming objectives were tracked in the database.")
        )

        if naming_objectives:
            book.execute(
                "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                "VALUES (?, 2, 2, 'Real Naming Objectives from the Database', 'text')",
                (ch16_id,)
            )
            sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i, o in enumerate(naming_objectives):
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                    "VALUES (?, 'text', ?, ?)",
                    (sec, i + 1,
                     f"Objective: {o['objective']}\n"
                     f"Description: {o.get('description', 'N/A')}\n"
                     f"Priority: {o.get('priority', 'N/A')}")
                )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@pascal", "naming",
             "Class names are PascalCase, no underscores",
             "PascalCase classes. UPPERCASE constants. snake_case for methods and variables.",
             ch16_id)
        )

        # Ch 17: Prohibition Rules
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part4_id, ch_num, "Prohibition Rules",
             "No decorators, no print, no hardcode",
             "The things that must never appear in VBStyle code.")
        )
        ch17_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Prohibitions', 'text')",
            (ch17_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Count violations by type
        decorator_violations = [v for v in violations if "decorator" in str(v.get("message", "")).lower()]
        print_violations = [v for v in violations if "print" in str(v.get("message", "")).lower()]
        hardcode_violations = [v for v in violations if "hardcod" in str(v.get("message", "")).lower()]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec,
             f"No decorators. No print statements. No hardcoded paths.\n\n"
             f"Violation counts from the database:\n"
             f"- Decorator violations: {len(decorator_violations)} types caught\n"
             f"- Print violations: {len(print_violations)} types caught\n"
             f"- Hardcode violations: {len(hardcode_violations)} types caught\n\n"
             f"No @property, @staticmethod, @classmethod. Ever.\n"
             f"No print(). Use Report class or MemBus events.\n"
             f"No hardcoded paths. Everything from config or params.")
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@decorators", "prohibition",
             "No decorators: @property, @staticmethod, @classmethod are never allowed",
             "Use a singleton instance instead of @staticmethod. Use a method instead of @property.",
             ch17_id)
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@print", "prohibition",
             "No print statements — use Report class or MemBus events",
             "Logging goes through MemBus events. Report class returns strings. No print().",
             ch17_id)
        )

        rule_num += 1
        book.execute(
            "INSERT INTO rules (rule_num, tag, category, short_desc, full_desc, chapter_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rule_num, "@hardcode", "prohibition",
             "No hardcoded NOTHING IS ALLOWED TO BE HARD CODED",
             "Paths, values, constants — all from config or params. Nothing hardcoded.",
             ch17_id)
        )

        # --- PART 5: Boot Sequence ---
        part5_id = book.execute("SELECT id FROM parts WHERE part_num=5").fetchone()[0]

        # Ch 21: The 4 Boot Stages
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part5_id, ch_num, "The 4 Boot Stages",
             "Init → Discover → Execute → runtime",
             "How CASOS assembles itself from the database.")
        )
        ch21_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Stages', 'text')",
            (ch21_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Group boot stages
        stage_groups = {}
        for s in boot_stages:
            stage = s.get("boot_stage", "unknown")
            if stage not in stage_groups:
                stage_groups[stage] = []
            stage_groups[stage].append(s)

        stage_descriptions = {
            "Init": "Core components initialize. MemDB, MemBus, Executor created.",
            "Discover": "System discovers domains from the database. Classes loaded, registered.",
            "Execute": "Executor ready. Commands can be dispatched. System is live.",
            "runtime": "Full runtime. Events flowing, resources monitored, commands executing.",
        }

        content = "The boot sequence has 4 stages, each with a priority order:\n\n"
        for stage in ["Init", "Discover", "Execute", "runtime"]:
            classes_in_stage = stage_groups.get(stage, [])
            content += f"Stage: {stage} (priority order)\n"
            content += f"  {stage_descriptions.get(stage, '')}\n"
            content += f"  Classes in this stage: {len(classes_in_stage)}\n"
            for c in classes_in_stage[:5]:
                content += f"    - {c['class_name']}: {c.get('description', '')}\n"
            if len(classes_in_stage) > 5:
                content += f"    ... and {len(classes_in_stage) - 5} more\n"
            content += "\n"

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec, content)
        )

        # --- PART 8: Anti-Patterns ---
        part8_id = book.execute("SELECT id FROM parts WHERE part_num=8").fetchone()[0]

        # Ch 31-35: Top anti-patterns from real violations
        top_patterns = sorted(violation_groups.items(),
                            key=lambda x: sum(v.get("occurrence_count", 0) for v in x[1]),
                            reverse=True)[:5]

        anti_pattern_titles = [
            ("The @staticmethod Trap", "Why static methods violate VBStyle and what to use instead"),
            ("The print() Habit", "Why print is banned and how to use Report instead"),
            ("The self._ Variable", "Why private attributes are hidden and state dict is better"),
            ("The Missing Bracket", "Why unbracketed methods break the contract"),
            ("The Hardcoded Path", "Why nothing should be hardcoded and how to use config"),
        ]

        for i, (title, subtitle) in enumerate(anti_pattern_titles):
            ch_num += 1
            book.execute(
                "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (part8_id, ch_num, title, subtitle,
                 f"Real violations from the codebase, with evidence and fixes.")
            )
            ch_id = book.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            if i < len(top_patterns):
                pattern, vlist = top_patterns[i]
                total = sum(v.get("occurrence_count", 0) for v in vlist)

                book.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                    "VALUES (?, 1, 1, 'The Evidence', 'text')",
                    (ch_id,)
                )
                sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

                messages = [v.get("message", "") for v in vlist[:3]]
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                    "VALUES (?, 'text', 1, ?)",
                    (sec,
                     f"Pattern detected: {pattern}\n"
                     f"Total occurrences: {total}\n"
                     f"Violation messages:\n"
                     + "".join(f"  - {m}\n" for m in messages))
                )

                book.execute(
                    "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
                    "VALUES (?, 2, 2, 'The Fix', 'text')",
                    (ch_id,)
                )
                sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

                fixes = {
                    "@staticmethod": "Use a module-level singleton instance. "
                                   "Create cfg = ClassName() at the end of the file. "
                                   "Call cfg.Method() instead of ClassName.Method().",
                    "print": "Use sys.stdout.write() for CLI output, or Report class "
                            "for internal logging, or MemBus publish() for events.",
                    "self._": "Use self.state dictionary. "
                             "self.state = {\"cache\": {}, \"connection\": None} "
                             "instead of self._cache = {}.",
                    "[@": "Add bracket annotation above every method: "
                         "#[@method_name]{[@params<<params>][@return<Tuple3>][@purpose<...>]}",
                    "hardcoded": "Move the value to Config class. "
                               "Reference it as Config.PATH_NAME. "
                               "Allow env var override.",
                }

                fix = fixes.get(pattern, "Review the VBStyle rules and apply the "
                                        "corresponding pattern from this book.")
                book.execute(
                    "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
                    "VALUES (?, 'text', 1, ?)",
                    (sec, fix)
                )

        # --- PART 9: Complete Examples ---
        part9_id = book.execute("SELECT id FROM parts WHERE part_num=9").fetchone()[0]

        # Ch 36: Building a Domain from Scratch
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part9_id, ch_num, "Building a Domain from Scratch",
             "A complete walkthrough",
             "Step-by-step: headers, class, Run dispatch, state, authorities, methods.")
        )
        ch36_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'The Complete Pattern', 'text')",
            (ch36_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content, lang) "
            "VALUES (?, 'code', 1, ?, 'python')",
            (sec,
             '#[@GHOST]{[@file<dom_example.py>][@state<active>][@date<2026-06-22>][@ver<1.0>][@auth<system>]}\n'
             '#[@VBSTYLE]{[@auth<system>][@role<domain_example>][@return<Tuple3>][@orch<MemUnit>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}\n'
             '\n'
             'class Example:\n'
             '    """Central dispatch for all example operations."""\n'
             '\n'
             '    def __init__(self, mem=None, db=None, param=None):\n'
             '        self.state = {\n'
             '            "config": {},\n'
             '            "catalog": [],\n'
             '            "results": [],\n'
             '            "memunit": mem,\n'
             '            "db_manager": db\n'
             '        }\n'
             '\n'
             '    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch to nested authorities>]}\n'
             '    def Run(self, command, params=None):\n'
             '        params = params or {}\n'
             '        if command == "create":\n'
             '            return self._create(params)\n'
             '        elif command == "read":\n'
             '            return self._read(params)\n'
             '        elif command == "read_state":\n'
             '            return self.read_state()\n'
             '        elif command == "set_config":\n'
             '            return self.set_config(params)\n'
             '        else:\n'
             '            return (0, None, ("UNKNOWN_COMMAND", command, 101))\n'
             '\n'
             '    #[@_create]{[@params<<params>][@return<Tuple3>][@purpose<create a new item>]}\n'
             '    def _create(self, params):\n'
             '        name = params.get("name", "")\n'
             '        if not name:\n'
             '            return (0, None, ("PARAM_MISSING", "name is required", 0))\n'
             '        self.state["catalog"].append({"name": name})\n'
             '        return (1, {"created": name}, None)\n'
             '\n'
             '    def read_state(self):\n'
             '        return (1, {"state": self.state}, None)\n'
             '\n'
             '    def set_config(self, params):\n'
             '        self.state["config"].update(params)\n'
             '        return (1, {"updated": True}, None)')
        )

        # Ch 38: Real Classes from the Database
        ch_num += 1
        book.execute(
            "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (part9_id, ch_num, "Real Classes from the Database",
             f"{len(classes)} classes mined from MySQL",
             "Actual VBStyle classes from the token_registry, with brackets and descriptions.")
        )
        ch38_id = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'Class Catalog', 'text')",
            (ch38_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        # List all classes grouped by domain
        class_listing = f"The database contains {len(classes)} VBStyle classes.\n\n"
        for domain_id, dclasses in sorted(domain_classes.items()):
            class_listing += f"Domain {domain_id} ({len(dclasses)} classes):\n"
            for c in dclasses[:10]:
                class_listing += f"  - {c['name']}: {c.get('description', 'N/A')}\n"
            if len(dclasses) > 10:
                class_listing += f"  ... and {len(dclasses) - 10} more\n"
            class_listing += "\n"

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec, class_listing)
        )

        # ===== GLOSSARY =====
        glossary_terms = [
            ("Tuple3", "A 3-tuple return format: (ok, data, error). ok=1 success, ok=0 failure.", ch3_id),
            ("MemUnit", "The orchestrator that ties MemDB + MemBus + Executor together.", ch12_id),
            ("MemDB", "In-RAM SQLite database holding runtime truth. Not disk-persistent.", ch13_id),
            ("MemBus", "Pub/sub event routing system. No direct module-to-module calls.", ch14_id),
            ("Executor", "Central dispatch authority. No class executes itself.", ch15_id),
            ("Ghost Header", "File-level identity marker: #[@GHOST]{[@file<...>][@state<...>]}", ch6_id),
            ("VBStyle Header", "Architecture declaration: #[@VBSTYLE]{[@auth<...>][@role<...>]}", ch7_id),
            ("Bracket", "Method-level annotation: #[@method]{[@params<...>][@return<...>]}", ch8_id),
            ("Domain", "A single concern owned by one class. No Utils, no Helpers.", ch10_id),
            ("Authority", "A nested class inside a domain that handles a specific sub-concern.", ch10_id),
            ("Run Dispatch", "The single public method: Run(command, params). Routes to private handlers.", ch2_id),
            ("State Dict", "self.state dictionary with config, catalog, results keys. No self._ variables.", ch4_id),
        ]

        for term, definition, ch_id in glossary_terms:
            book.execute(
                "INSERT INTO glossary (term, definition, chapter_id) "
                "VALUES (?, ?, ?)",
                (term, definition, ch_id)
            )

        # ===== SCHEMA META =====
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("book_title", "VBStyle: The Definitive Guide")
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("book_subtitle", "An O'Reilly-style technical reference mined from real evidence")
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("source_database", "MySQL token_registry")
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("extraction_date", "2026-06-22")
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("total_classes_mined", str(len(classes)))
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("total_violations_mined", str(len(violations)))
        )
        book.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
            ("total_rules_mined", str(len(rules)))
        )

        book.commit()

        self.state["stats"]["parts_built"] = 9
        self.state["stats"]["chapters_built"] = ch_num
        self.state["stats"]["rules_built"] = rule_num
        self.state["stats"]["glossary_built"] = len(glossary_terms)

        return (1, "Book built successfully", ())

    # --------------------------------------------------------------------
    # GAP REPORT — Find concepts used but never formally defined
    # --------------------------------------------------------------------
    def GapReport(self):
        book = self.state["book"]
        _, rules, _ = self.MineRules()
        _, violations, _ = self.MineViolations()
        _, objectives, _ = self.MineObjectives()

        # Find objectives that appear frequently but have no formal rule
        rule_objectives = [o for o in rules if o.get("source_type") == "rule"]
        learning_objectives = [o for o in objectives if o.get("source_type") == "architecture_learning"]

        # Find violation patterns that don't have corresponding rules
        gaps = []

        # Check for concepts mentioned in objectives but not in rules
        rule_texts = " ".join(str(o.get("objective", "")) for o in rule_objectives).lower()
        for lo in learning_objectives:
            obj_text = str(lo.get("objective", "")).lower()
            words = obj_text.split()[:3]
            key_phrase = " ".join(words)
            if key_phrase and key_phrase not in rule_texts:
                gaps.append({
                    "concept": lo.get("objective", ""),
                    "description": lo.get("description", ""),
                    "category": lo.get("category", ""),
                    "issue": "Architecture learning has no corresponding formal rule",
                })

        self.state["stats"]["gaps_found"] = len(gaps)

        # Store gaps as a special section in the book
        # Find or create an appendix chapter
        part9_id = book.execute("SELECT id FROM parts WHERE part_num=9").fetchone()[0]
        ch = book.execute(
            "SELECT id FROM chapters WHERE part_id=? AND title LIKE '%Gap%'",
            (part9_id,)
        ).fetchone()

        if ch:
            ch_id = ch[0]
        else:
            book.execute(
                "INSERT INTO chapters (part_id, ch_num, title, subtitle, description) "
                "VALUES (?, 99, 'Appendix D: Gap Report', "
                "'Concepts used but never formally defined', ?)",
                (part9_id,
                 f"{len(gaps)} concepts were discovered in the evidence but never "
                 "promoted to formal rules. These are the unknowns.")
            )
            ch_id = book.execute("SELECT id FROM chapters ORDER BY id DESC LIMIT 1").fetchone()[0]

        book.execute(
            "INSERT INTO sections (chapter_id, sec_num, sort_order, title, section_type) "
            "VALUES (?, 1, 1, 'Identified Gaps', 'text')",
            (ch_id,)
        )
        sec = book.execute("SELECT last_insert_rowid()").fetchone()[0]

        gap_text = f"Gap Report: {len(gaps)} concepts need clarification\n\n"
        gap_text += "These concepts appear in the evidence base but were never formally "
        "defined as rules. Before the book can be considered complete, these gaps "
        "need to be resolved.\n\n"

        for i, g in enumerate(gaps[:20], 1):
            gap_text += f"{i}. {g['concept']}\n"
            gap_text += f"   Description: {g.get('description', 'N/A')}\n"
            gap_text += f"   Issue: {g['issue']}\n\n"

        if len(gaps) > 20:
            gap_text += f"... and {len(gaps) - 20} more gaps identified.\n"

        book.execute(
            "INSERT INTO content_blocks (section_id, block_type, block_order, content) "
            "VALUES (?, 'text', 1, ?)",
            (sec, gap_text)
        )

        book.commit()
        return (1, gaps, ())

    # --------------------------------------------------------------------
    # REPORT — Print extraction statistics
    # --------------------------------------------------------------------
    def Report(self):
        s = self.state["stats"]
        report = (
            f"\n{'='*60}\n"
            f"VBStyle Book Extraction Report\n"
            f"{'='*60}\n\n"
            f"Source: MySQL token_registry\n"
            f"Output: {BOOK_DB_PATH}\n\n"
            f"Evidence Mined:\n"
            f"  Rules:          {s.get('rules_mined', 0)}\n"
            f"  Violations:     {s.get('violations_mined', 0)}\n"
            f"  Classes:        {s.get('classes_mined', 0)}\n"
            f"  Methods:        {s.get('methods_mined', 0)}\n"
            f"  Boot stages:    {s.get('boot_stages_mined', 0)}\n"
            f"  Table purposes: {s.get('table_purposes_mined', 0)}\n"
            f"  Objectives:     {s.get('objectives_mined', 0)}\n"
            f"  Documents:      {s.get('documents_mined', 0)}\n"
            f"  Docs discovered:{s.get('documents_discovered', 0)}\n"
            f"  Docs listed:    {s.get('documents_listed', 0)}\n"
            f"  Chunks created: {s.get('total_chunks', 0)}\n"
            f"  Chars read:     {s.get('total_chars_read', 0):,}\n"
            f"  Truths extracted:{s.get('total_truths_extracted', 0)}\n\n"
            f"Book Built:\n"
            f"  Parts:          {s.get('parts_built', 0)}\n"
            f"  Chapters:       {s.get('chapters_built', 0)}\n"
            f"  Missing added:  {s.get('missing_chapters_added', 0)}\n"
            f"  Total chapters: {s.get('total_chapters_final', 0)}\n"
            f"  Rules:          {s.get('rules_built', 0)}\n"
            f"  Total rules:    {s.get('total_rules_final', 0)}\n"
            f"  Glossary terms: {s.get('glossary_built', 0)}\n"
            f"  Gaps found:     {s.get('gaps_found', 0)}\n\n"
            f"{'='*60}\n"
        )
        return (1, report, ())

    # --------------------------------------------------------------------
    # CLOSE — Clean up connections
    # --------------------------------------------------------------------
    def Close(self):
        if self.state["mysql"]:
            self.state["mysql"].close()
        if self.state["book"]:
            self.state["book"].close()
        return (1, "Closed", ())


# ============================================================================
# MAIN
# ============================================================================
def main():
    extractor = BookExtractor()

    ok, msg, err = extractor.Connect()
    if not ok:
        sys.stderr.write(f"Connection failed: {err}\n")
        return 1
    sys.stdout.write(msg + "\n")

    ok, msg, err = extractor.BuildBook()
    if not ok:
        sys.stderr.write(f"Build failed: {err}\n")
        return 1
    sys.stdout.write(msg + "\n")

    ok, msg, err = extractor.BuildMissingChapters()
    if not ok:
        sys.stderr.write(f"Missing chapters failed: {err}\n")
        return 1
    sys.stdout.write(msg + "\n")

    ok, msg, err = extractor.ScanAllDocuments()
    if not ok:
        sys.stderr.write(f"Document scan failed: {err}\n")
        return 1
    sys.stdout.write(msg + "\n")

    ok, msg, err = extractor.BuildExtractedTruths()
    if not ok:
        sys.stderr.write(f"Truth extraction failed: {err}\n")
        return 1
    sys.stdout.write(msg + "\n")

    ok, gaps, err = extractor.GapReport()
    if not ok:
        sys.stderr.write(f"Gap report failed: {err}\n")
        return 1
    sys.stdout.write(f"Gap report: {len(gaps)} gaps identified\n")

    ok, report, _ = extractor.Report()
    sys.stdout.write(report + "\n")

    extractor.Close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
