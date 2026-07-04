#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/understanding_engine.py" date="2026-08-18" author="Devin" session_id="understanding-engine" context="Iterative understanding engine — observes codebase, generates typed questions per object, searches for answers, scores confidence, detects gaps, measures understanding"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self-_ no-print"}
#[@FILEID]{id="understanding_engine.py" domain="utility" authority="UnderstandingEngine"}
#[@SUMMARY]{summary="Iterative understanding engine — scans codebase, generates questions per object type, searches for answers, scores confidence, detects gaps, measures understanding coverage"}
#[@CLASS]{class="UnderstandingEngine" domain="utility" authority="single"}
#[@METHOD]{methods="Run,Observe,Generate,SearchAnswers,ScoreConfidence,DetectGaps,MeasureUnderstanding,FullCycle"}

"""
UnderstandingEngine — an iterative understanding engine.

Instead of answering questions a human asks, this engine INVENTS questions
about every object it finds, then searches for answers, scores confidence,
detects gaps, and keeps working until understanding reaches a target level.

6 Phases:
  1. Observe    — scan everything, extract all objects
  2. Generate   — typed questions per object type
  3. Search     — find answers in code, markdown, db, config, git
  4. Confidence — score each answer (known/verified/likely/weak/unknown)
  5. Gap        — re-ask weak answers, escalate unknowns
  6. Measure    — understanding % per category

Object Taxonomy:
  - file          — a source file (.py, .md, .sql, .yaml, .json, .c, .h)
  - class         — a Python class
  - method        — a function/method
  - config        — a configuration key/value
  - db_table      — a database table
  - bcl_rule      — a BCL rule token
  - md_section    — a markdown heading section
  - constant      — an UPPERCASE constant
  - import        — an imported module
  - state_key     — a self.state dict key
  - dispatch_key  — a Run() command key
  - variable      — a module-level variable
  - db            — a database
  - service       — a runtime service/process

Each object type has its own question template (see QUESTION_TEMPLATES).
"""

import os
import re
import json
import sqlite3
from datetime import datetime

# ════════════════════════════════════════════════════════════════
# OBJECT TAXONOMY — every type of object the engine can discover
# ════════════════════════════════════════════════════════════════

OBJECT_TYPES = [
    "file", "class", "method", "config", "db_table", "bcl_rule",
    "md_section", "constant", "import", "state_key", "dispatch_key",
    "variable", "db", "service",
]

# ════════════════════════════════════════════════════════════════
# QUESTION TEMPLATES — typed questions per object type
# Each template: (question_text, question_type, search_sources)
# search_sources: where to look for the answer
#   "code"     — search .py files
#   "markdown" — search .md files
#   "db"       — search MySQL databases
#   "config"   — search config files
#   "index"    — search the codebase index
#   "git"      — search git history
#   "self"     — the object itself (name, location, etc.)
# ════════════════════════════════════════════════════════════════

QUESTION_TEMPLATES = {
    "file": [
        ("What is the purpose of {name}?", "what", ["markdown", "index", "self"]),
        ("Why does {name} exist?", "why", ["markdown", "index"]),
        ("Who created {name} and when?", "when", ["git", "self"]),
        ("What files depend on {name}?", "where", ["code", "index"]),
        ("Is {name} documented?", "what", ["markdown", "self"]),
        ("Is {name} tested?", "what", ["code", "index"]),
        ("Could {name} be removed?", "what", ["code", "index"]),
        ("What domain does {name} belong to?", "what", ["self", "markdown"]),
        ("What is the line count of {name}?", "what", ["self"]),
        ("Does {name} have VBStyle headers?", "what", ["self"]),
    ],
    "class": [
        ("What is {name}?", "what", ["markdown", "index", "self"]),
        ("Why does {name} exist?", "why", ["markdown", "index"]),
        ("Who creates {name}?", "who", ["code", "index"]),
        ("Who uses {name}?", "who", ["code", "index"]),
        ("What calls {name}?", "what", ["code", "index"]),
        ("What does {name} return?", "what", ["code", "self"]),
        ("What files depend on {name}?", "where", ["code", "index"]),
        ("Is {name} documented?", "what", ["markdown", "self"]),
        ("Is {name} tested?", "what", ["code", "index"]),
        ("Could {name} be removed?", "what", ["code", "index"]),
        ("Does {name} own state? What keys?", "what", ["code", "self"]),
        ("What configuration affects {name}?", "what", ["config", "code"]),
        ("What are the inputs to {name}?", "what", ["code", "self"]),
        ("What are the outputs of {name}?", "what", ["code", "self"]),
        ("What domain does {name} own?", "what", ["self", "markdown"]),
        ("What does {name} depend on?", "what", ["code", "self"]),
        ("What is {name}'s authority?", "what", ["self", "markdown"]),
        ("Does {name} have a Run() dispatch?", "what", ["code", "self"]),
        ("What commands does {name}.Run() dispatch?", "what", ["code", "self"]),
        ("When was {name} created?", "when", ["git", "markdown"]),
    ],
    "method": [
        ("What is the purpose of {name}()?", "what", ["markdown", "index", "self"]),
        ("What are the parameters of {name}()?", "what", ["code", "self"]),
        ("What does {name}() return?", "what", ["code", "self"]),
        ("Does {name}() have side effects?", "what", ["code", "self"]),
        ("Can {name}() raise exceptions?", "what", ["code", "self"]),
        ("Who calls {name}()?", "who", ["code", "index"]),
        ("How often is {name}() called?", "how_many", ["code", "index"]),
        ("Can {name}() fail?", "what", ["code", "self"]),
        ("Are there examples of {name}() usage?", "what", ["code", "markdown"]),
        ("What functions are related to {name}()?", "what", ["code", "index"]),
        ("What is the complexity of {name}()?", "what", ["code", "self"]),
        ("Does {name}() follow Tuple3 return pattern?", "what", ["code", "self"]),
    ],
    "config": [
        ("What reads {name}?", "what", ["code", "index"]),
        ("What is the default value of {name}?", "what", ["config", "self"]),
        ("Can {name} be changed at runtime?", "what", ["code", "config"]),
        ("Is {name} persistent?", "what", ["config", "code"]),
        ("Is {name} required or optional?", "what", ["config", "code"]),
        ("What happens if {name} is wrong?", "what", ["code", "markdown"]),
        ("Where is {name} defined?", "where", ["config", "self"]),
        ("Who depends on {name}?", "who", ["code", "index"]),
    ],
    "db_table": [
        ("What is {name}?", "what", ["markdown", "db", "self"]),
        ("What columns does {name} have?", "what", ["db", "self"]),
        ("What is the primary key of {name}?", "what", ["db", "self"]),
        ("What foreign keys does {name} have?", "what", ["db", "self"]),
        ("What indexes does {name} have?", "what", ["db", "self"]),
        ("How many rows in {name}?", "how_many", ["db"]),
        ("What code writes to {name}?", "what", ["code", "index"]),
        ("What code reads from {name}?", "what", ["code", "index"]),
        ("Is {name} documented?", "what", ["markdown"]),
        ("Could {name} be normalized further?", "what", ["db", "markdown"]),
    ],
    "bcl_rule": [
        ("What does {name} enforce?", "what", ["markdown", "self"]),
        ("Why does {name} exist?", "why", ["markdown"]),
        ("What happens when {name} is violated?", "what", ["markdown", "code"]),
        ("Is {name} documented?", "what", ["markdown", "self"]),
        ("What code checks {name}?", "what", ["code", "index"]),
        ("Is {name} a Pass or Fail rule?", "what", ["self"]),
    ],
    "md_section": [
        ("What is {name} about?", "what", ["markdown", "self"]),
        ("What files does {name} reference?", "what", ["markdown", "self"]),
        ("Is {name} up to date?", "what", ["markdown", "code"]),
        ("Does {name} describe code that exists?", "what", ["code", "index"]),
        ("What is the parent section of {name}?", "what", ["markdown", "self"]),
    ],
    "constant": [
        ("What is {name}?", "what", ["code", "self"]),
        ("What value does {name} hold?", "what", ["code", "self"]),
        ("Why is {name} a constant?", "why", ["code", "markdown"]),
        ("Is {name} configurable?", "what", ["config", "code"]),
        ("Where is {name} used?", "where", ["code", "index"]),
        ("Could {name} be moved to Config.py?", "what", ["code"]),
    ],
    "import": [
        ("What does {name} provide?", "what", ["code", "markdown"]),
        ("Why is {name} imported?", "why", ["code", "self"]),
        ("Where else is {name} used?", "where", ["code", "index"]),
        ("Is {name} a standard library module?", "what", ["self"]),
        ("Is {name} a third-party dependency?", "what", ["self"]),
    ],
    "state_key": [
        ("What does self.state['{name}'] store?", "what", ["code", "self"]),
        ("Who reads self.state['{name}']?", "who", ["code", "index"]),
        ("Who writes self.state['{name}']?", "who", ["code", "index"]),
        ("What is the type of self.state['{name}']?", "what", ["code", "self"]),
        ("Is self.state['{name}'] required?", "what", ["code", "self"]),
    ],
    "dispatch_key": [
        ("What does Run('{name}') do?", "what", ["code", "self"]),
        ("What parameters does Run('{name}') expect?", "what", ["code", "self"]),
        ("What does Run('{name}') return?", "what", ["code", "self"]),
        ("Who calls Run('{name}')?", "who", ["code", "index"]),
        ("Is Run('{name}') tested?", "what", ["code", "index"]),
    ],
    "variable": [
        ("What is {name}?", "what", ["code", "self"]),
        ("What type is {name}?", "what", ["code", "self"]),
        ("Where is {name} used?", "where", ["code", "index"]),
        ("Is {name} initialized correctly?", "what", ["code", "self"]),
    ],
    "db": [
        ("What is the {name} database for?", "what", ["markdown", "db"]),
        ("What tables are in {name}?", "what", ["db"]),
        ("How big is {name}?", "how_much", ["db"]),
        ("What code connects to {name}?", "what", ["code", "index"]),
        ("Is {name} backed up?", "what", ["markdown", "config"]),
    ],
    "service": [
        ("What is {name}?", "what", ["markdown", "code"]),
        ("What does {name} do?", "what", ["code", "markdown"]),
        ("Is {name} running?", "what", ["self"]),
        ("What port does {name} use?", "what", ["config", "code"]),
        ("What depends on {name}?", "what", ["code", "markdown"]),
    ],
}

# ════════════════════════════════════════════════════════════════
# CONFIDENCE LEVELS
# ════════════════════════════════════════════════════════════════

CONFIDENCE_LEVELS = {
    "known": 95,        # Found in multiple sources, verified
    "verified": 85,     # Found in code + documentation
    "likely": 65,       # Found in one source, inferred
    "weak": 35,         # Only guessed from name/context
    "unknown": 0,       # No answer found
    "contradicted": -1, # Sources disagree
}

# Confidence by source weight
SOURCE_WEIGHTS = {
    "code": 55,         # Code is ground truth
    "self": 50,         # The object itself (name, location, headers) — strong source
    "db": 50,           # Database schema is authoritative
    "markdown": 40,     # Documentation can be stale
    "config": 45,       # Config is authoritative
    "index": 35,        # Index is derived
    "git": 25,          # Git history is historical
}

# ════════════════════════════════════════════════════════════════
# SEARCH DIRS
# ════════════════════════════════════════════════════════════════

SCAN_DIRS = [
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/core",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_DecisionTrees",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/BookSystem",
]

SCAN_EXTENSIONS = [".py", ".md", ".txt", ".sql", ".yaml", ".json", ".c", ".h", ".sh"]

# Skip directories
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "treasure_trove_backup",
             ".tasks", ".context", ".devin", ".agents"}

ANSWER_YES = "Y"
ANSWER_NO = "N"
ANSWER_UNKNOWN = "U"


class UnderstandingEngine:
    """Iterative understanding engine.
    Scans codebase, generates questions per object, searches for answers,
    scores confidence, detects gaps, measures understanding."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "scan_dirs": SCAN_DIRS,
                "scan_extensions": SCAN_EXTENSIONS,
                "skip_dirs": SKIP_DIRS,
                "index_path": os.path.expanduser("~/.codebase_index.db"),
                "store_path": os.path.expanduser("~/.question_store.db"),
                "understanding_path": os.path.expanduser("~/.understanding.db"),
                "target_confidence": 70,
                "max_iterations": 3,
            },
            "catalog": {
                "objects": {},
                "questions": {},
                "answers": {},
                "understanding": {},
            },
            "results": {
                "total_objects": 0,
                "total_questions": 0,
                "total_answered": 0,
                "total_unknown": 0,
            }
        }
        if param and "scan_dirs" in param:
            self.state["config"]["scan_dirs"] = param["scan_dirs"]
        if param and "target_confidence" in param:
            self.state["config"]["target_confidence"] = param["target_confidence"]
        self._store_conn = None
        self._index_conn = None
        self._understanding_conn = None
        self._file_cache = {}       # file_path → file content (string)
        self._file_lines_cache = {} # file_path → list of lines
        self._index_word_cache = {} # word → list of (context, filename, line_num)
        self._cache_lock = None

    # ── VBStyle helpers ──────────────────────────────────────────

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _now(self):
        return datetime.now().isoformat()

    def _read_file_cached(self, file_path):
        """Read file content from cache, or load from disk if not cached."""
        if not file_path or not os.path.exists(file_path):
            return None
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        try:
            with open(file_path, "r", errors="ignore") as fh:
                content = fh.read()
            self._file_cache[file_path] = content
            self._file_lines_cache[file_path] = content.split("\n")
            return content
        except Exception:
            return None

    def _read_lines_cached(self, file_path):
        """Read file lines from cache."""
        if file_path in self._file_lines_cache:
            return self._file_lines_cache[file_path]
        content = self._read_file_cached(file_path)
        if content is not None:
            return self._file_lines_cache[file_path]
        return None

    def _preload_files(self, file_paths):
        """Pre-load multiple files into cache in parallel."""
        from concurrent.futures import ThreadPoolExecutor
        unique_paths = set(file_paths)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(self._read_file_cached, unique_paths))
        return len(unique_paths)

    def _preload_index_words(self, words, index_conn):
        """Pre-load index search results for a batch of words."""
        if not index_conn or not words:
            return
        unique_words = set(words)
        # Batch query: get all word matches in one query
        placeholders = ",".join("?" * len(unique_words))
        try:
            rows = index_conn.execute(
                f"SELECT w.word, w.context, f.filename, w.line_num "
                f"FROM words w JOIN files f ON w.file_id = f.id "
                f"WHERE w.word IN ({placeholders})",
                list(unique_words)
            ).fetchall()
            for row in rows:
                word = row[0]
                if word not in self._index_word_cache:
                    self._index_word_cache[word] = []
                self._index_word_cache[word].append((row[1], row[2], row[3]))
        except Exception:
            pass
        # Also do prefix matches for words not found exactly
        found_words = set(self._index_word_cache.keys())
        missing_words = unique_words - found_words
        for word in missing_words:
            try:
                rows = index_conn.execute(
                    "SELECT w.context, f.filename, w.line_num "
                    "FROM words w JOIN files f ON w.file_id = f.id "
                    "WHERE w.word LIKE ? LIMIT 10",
                    (f"{word}%",)
                ).fetchall()
                if rows:
                    self._index_word_cache[word] = [(r[0], r[1], r[2]) for r in rows]
            except Exception:
                pass

    def _get_store(self):
        if self._store_conn is None:
            self._store_conn = sqlite3.connect(self.state["config"]["store_path"])
        return self._store_conn

    def _get_index(self):
        if self._index_conn is None:
            path = self.state["config"]["index_path"]
            if os.path.exists(path):
                self._index_conn = sqlite3.connect(path)
            else:
                self._index_conn = None
        return self._index_conn

    def _get_understanding_db(self):
        if self._understanding_conn is None:
            path = self.state["config"]["understanding_path"]
            self._understanding_conn = sqlite3.connect(path)
            self._init_understanding_schema()
        return self._understanding_conn

    def _init_understanding_schema(self):
        conn = self._understanding_conn
        conn.execute("""CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_type TEXT NOT NULL,
            object_name TEXT NOT NULL,
            file_path TEXT,
            line_num INTEGER,
            metadata TEXT,
            discovered_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT,
            search_sources TEXT,
            answer_text TEXT,
            answer_source TEXT,
            confidence INTEGER DEFAULT 0,
            confidence_level TEXT DEFAULT 'unknown',
            answered_at TEXT,
            iteration INTEGER DEFAULT 0,
            FOREIGN KEY (object_id) REFERENCES objects(id)
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_q_object ON questions(object_id)""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_q_confidence ON questions(confidence)""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_obj_type ON objects(object_type)""")
        conn.commit()

    # ════════════════════════════════════════════════════════════════
    # RUN DISPATCH
    # ════════════════════════════════════════════════════════════════

    def Run(self, command, params=None):
        if command == "observe":
            return self.Observe(params)
        elif command == "generate":
            return self.Generate(params)
        elif command == "search_answers":
            return self.SearchAnswers(params)
        elif command == "score_confidence":
            return self.ScoreConfidence(params)
        elif command == "detect_gaps":
            return self.DetectGaps(params)
        elif command == "measure":
            return self.MeasureUnderstanding(params)
        elif command == "full_cycle":
            return self.FullCycle(params)
        elif command == "report":
            return self.Report(params)
        else:
            return (0, None, (1, f"unknown_command:{command}", 0))

    # ════════════════════════════════════════════════════════════════
    # PHASE 1: OBSERVE — scan everything, extract all objects
    # ════════════════════════════════════════════════════════════════

    def Observe(self, params=None):
        """Scan all files in scan_dirs, extract every object.
        Returns a catalog of all discovered objects."""
        scan_dirs = self._p(params, "scan_dirs", self.state["config"]["scan_dirs"])
        scan_exts = self._p(params, "scan_extensions", self.state["config"]["scan_extensions"])
        skip_dirs = self.state["config"]["skip_dirs"]
        conn = self._get_understanding_db()
        # Clear old objects
        conn.execute("DELETE FROM objects")
        conn.execute("DELETE FROM questions")
        conn.commit()
        objects = []
        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            for root, dirs_list, files in os.walk(scan_dir):
                dirs_list[:] = [d for d in dirs_list if d not in skip_dirs and not d.startswith(".")]
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in scan_exts:
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        fsize = os.path.getsize(fpath)
                        if fsize > 2 * 1024 * 1024:
                            continue
                        with open(fpath, "r", errors="ignore") as fh:
                            lines = fh.readlines()
                    except Exception:
                        continue
                    # ── Extract FILE object ──
                    objects.append({
                        "type": "file",
                        "name": fname,
                        "file_path": fpath,
                        "line_num": 1,
                        "metadata": json.dumps({
                            "ext": ext, "lines": len(lines),
                            "size": fsize, "dir": os.path.dirname(fpath)
                        })
                    })
                    # ── Extract objects based on file type ──
                    if ext == ".py":
                        objects.extend(self._extract_py_objects(fpath, fname, lines))
                    elif ext == ".md":
                        objects.extend(self._extract_md_objects(fpath, fname, lines))
                    elif ext == ".sql":
                        objects.extend(self._extract_sql_objects(fpath, fname, lines))
                    elif ext in (".yaml", ".json"):
                        objects.extend(self._extract_config_objects(fpath, fname, lines))
        # Save to DB
        for obj in objects:
            conn.execute(
                "INSERT INTO objects (object_type, object_name, file_path, line_num, metadata, discovered_at) VALUES (?, ?, ?, ?, ?, ?)",
                (obj["type"], obj["name"], obj.get("file_path"), obj.get("line_num", 0),
                 obj.get("metadata", ""), self._now())
            )
        conn.commit()
        # Count by type
        type_counts = {}
        for obj in objects:
            t = obj["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        self.state["results"]["total_objects"] = len(objects)
        self.state["catalog"]["objects"] = type_counts
        return (1, {
            "status": "observed",
            "total_objects": len(objects),
            "by_type": type_counts,
            "scan_dirs": len(scan_dirs),
        }, None)

    def _extract_py_objects(self, fpath, fname, lines):
        """Extract objects from a Python file."""
        objects = []
        source = "".join(lines)
        classes = []
        # Classes
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)', stripped)
            if m:
                cn = m.group(1)
                classes.append({"name": cn, "line": i + 1})
                objects.append({
                    "type": "class", "name": cn, "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"file": fname})
                })
        # Methods
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^def\s+([A-Za-z_][A-Za-z0-9_]*)', stripped)
            if m:
                mn = m.group(1)
                if mn.startswith("__") and mn not in ("__init__",):
                    continue
                owning_class = None
                for cls in classes:
                    if cls["line"] < i + 1:
                        owning_class = cls["name"]
                full_name = f"{owning_class}.{mn}" if owning_class else mn
                objects.append({
                    "type": "method", "name": full_name, "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"class": owning_class, "signature": stripped[:200]})
                })
                # Run() dispatch keys
                if mn == "Run" and owning_class:
                    dispatch_keys = self._extract_dispatch_keys(lines, i + 1)
                    for dk in dispatch_keys:
                        objects.append({
                            "type": "dispatch_key", "name": dk,
                            "file_path": fpath, "line_num": i + 1,
                            "metadata": json.dumps({"class": owning_class})
                        })
        # Imports
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                parts = stripped.split()
                module = parts[1] if len(parts) > 1 else ""
                if module:
                    objects.append({
                        "type": "import", "name": module, "file_path": fpath, "line_num": i + 1,
                        "metadata": json.dumps({"statement": stripped[:200]})
                    })
        # Constants
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^([A-Z][A-Z0-9_]{2,})\s*=', stripped)
            if m and not stripped.startswith("#"):
                objects.append({
                    "type": "constant", "name": m.group(1), "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"value_line": stripped[:200]})
                })
        # State keys
        state_keys = self._extract_state_keys(source)
        for key in state_keys:
            owning_class = classes[0]["name"] if classes else "module"
            objects.append({
                "type": "state_key", "name": key, "file_path": fpath, "line_num": 1,
                "metadata": json.dumps({"class": owning_class})
            })
        # BCL rules from headers
        for match in re.finditer(r'#\[@(\w+)\]', source):
            rule = match.group(1)
            objects.append({
                "type": "bcl_rule", "name": f"@{rule}", "file_path": fpath,
                "line_num": source[:match.start()].count("\n") + 1,
                "metadata": json.dumps({"header": True})
            })
        return objects

    def _extract_md_objects(self, fpath, fname, lines):
        """Extract objects from a Markdown file."""
        objects = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^(#{1,6})\s+(.+)', stripped)
            if m:
                heading = m.group(2).strip()
                objects.append({
                    "type": "md_section", "name": heading, "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"level": len(m.group(1)), "file": fname})
                })
        return objects

    def _extract_sql_objects(self, fpath, fname, lines):
        """Extract objects from a SQL file."""
        objects = []
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            m = re.match(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', stripped)
            if m:
                objects.append({
                    "type": "db_table", "name": m.group(1).lower(), "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"file": fname})
                })
        return objects

    def _extract_config_objects(self, fpath, fname, lines):
        """Extract config keys from YAML/JSON files."""
        objects = []
        source = "".join(lines)
        # YAML keys (key: value)
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'^([a-z][a-z0-9_]*)\s*:', stripped)
            if m:
                key = m.group(1)
                objects.append({
                    "type": "config", "name": key, "file_path": fpath, "line_num": i + 1,
                    "metadata": json.dumps({"file": fname, "line_text": stripped[:200]})
                })
        # JSON keys
        for match in re.finditer(r'"([a-z][a-z0-9_]*)"\s*:', source):
            key = match.group(1)
            line_num = source[:match.start()].count("\n") + 1
            objects.append({
                "type": "config", "name": key, "file_path": fpath, "line_num": line_num,
                "metadata": json.dumps({"file": fname})
            })
        return objects

    def _extract_dispatch_keys(self, lines, run_line):
        """Extract dispatch command keys from a Run() method."""
        keys = []
        in_run = False
        for i in range(run_line - 1, min(run_line + 100, len(lines))):
            line = lines[i].strip()
            if "def Run(" in line:
                in_run = True
                continue
            if not in_run:
                continue
            m = re.match(r'(?:elif|if)\s+command\s*==\s*["\']([^"\']+)["\']', line)
            if m:
                keys.append(m.group(1))
            if i > run_line + 1 and line.startswith("def ") and "Run(" not in line:
                break
        return keys

    def _extract_state_keys(self, source):
        """Extract self.state dict keys from source code."""
        keys = []
        m = re.search(r'self\.state\s*=\s*\{([^}]+)\}', source)
        if m:
            state_block = m.group(1)
            key_matches = re.findall(r'["\']([^"\']+)["\']\s*:', state_block)
            keys.extend(key_matches)
        key_matches = re.findall(r'self\.state\[\s*["\']([^"\']+)["\']\s*\]', source)
        for k in key_matches:
            if k not in keys:
                keys.append(k)
        return list(set(keys))

    # ════════════════════════════════════════════════════════════════
    # PHASE 2: GENERATE — typed questions per object
    # ════════════════════════════════════════════════════════════════

    def Generate(self, params=None):
        """Generate questions for all discovered objects using templates."""
        conn = self._get_understanding_db()
        objects = conn.execute("SELECT id, object_type, object_name, file_path, line_num, metadata FROM objects").fetchall()
        total_questions = 0
        questions_by_type = {}
        for obj_row in objects:
            obj_id, obj_type, obj_name, file_path, line_num, metadata = obj_row
            templates = QUESTION_TEMPLATES.get(obj_type, [])
            for template_text, q_type, search_sources in templates:
                question = template_text.format(name=obj_name)
                conn.execute(
                    "INSERT INTO questions (object_id, question_text, question_type, search_sources, confidence, confidence_level, iteration) VALUES (?, ?, ?, ?, 0, 'unknown', 0)",
                    (obj_id, question, q_type, json.dumps(search_sources))
                )
                total_questions += 1
                questions_by_type[obj_type] = questions_by_type.get(obj_type, 0) + 1
        conn.commit()
        self.state["results"]["total_questions"] = total_questions
        return (1, {
            "status": "generated",
            "total_questions": total_questions,
            "by_object_type": questions_by_type,
            "total_objects": len(objects),
        }, None)

    # ════════════════════════════════════════════════════════════════
    # PHASE 3: SEARCH ANSWERS — find answers in all sources
    # ════════════════════════════════════════════════════════════════

    def SearchAnswers(self, params=None):
        """Search for answers to all unanswered questions — CONCURRENT.
        Uses ThreadPoolExecutor to search multiple questions in parallel.
        Pre-loads all file contents and index words into memory first,
        so threads never hit disk — pure in-memory lookups."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        conn = self._get_understanding_db()
        index_path = self.state["config"]["index_path"]
        max_answers = self._p(params, "max_answers", 500)
        workers = self._p(params, "workers", 16)
        questions = conn.execute(
            "SELECT q.id, q.question_text, q.question_type, q.search_sources, o.object_type, o.object_name, o.file_path, o.line_num, o.metadata "
            "FROM questions q JOIN objects o ON q.object_id = o.id "
            "WHERE q.confidence_level = 'unknown' LIMIT ?", (max_answers,)
        ).fetchall()
        # ── PRE-LOAD: collect all unique file paths and object names ──
        file_paths = set()
        obj_names = set()
        for q_row in questions:
            file_paths.add(q_row[6])  # file_path
            obj_names.add(q_row[5])   # object_name
        # Pre-load all files into memory (parallel)
        files_loaded = self._preload_files(file_paths)
        # Pre-load all index word lookups into memory (single batch query)
        index_conn = self._get_index()
        if index_conn:
            self._preload_index_words(obj_names, index_conn)
        # ── Thread-local storage for per-thread DB connections ──
        tls = threading.local()
        def get_thread_index():
            if not hasattr(tls, "index"):
                if os.path.exists(index_path):
                    tls.index = sqlite3.connect(index_path, check_same_thread=False)
                else:
                    tls.index = None
            return tls.index
        # ── Worker function — searches one question across all its sources ──
        def search_one(q_row):
            qid, q_text, q_type, search_sources_json, obj_type, obj_name, file_path, line_num, obj_metadata = q_row
            search_sources = json.loads(search_sources_json) if search_sources_json else []
            obj_meta = json.loads(obj_metadata) if obj_metadata else {}
            thread_index = get_thread_index()
            best_answer = None
            best_confidence = 0
            best_source = None
            for source in search_sources:
                try:
                    answer, confidence = self._search_source(source, q_text, q_type, obj_name, obj_type, file_path, obj_meta, thread_index)
                    if answer and confidence > best_confidence:
                        best_answer = answer
                        best_confidence = confidence
                        best_source = source
                except Exception:
                    continue
            return (qid, best_answer, best_confidence, best_source)
        # ── Run questions concurrently ──
        answered = 0
        still_unknown = 0
        results_buffer = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(search_one, q): q for q in questions}
            for future in as_completed(futures):
                try:
                    qid, best_answer, best_confidence, best_source = future.result()
                    if best_answer:
                        level = self._confidence_to_level(best_confidence)
                        results_buffer.append((best_answer, best_source, best_confidence, level, self._now(), qid))
                        answered += 1
                    else:
                        still_unknown += 1
                except Exception:
                    still_unknown += 1
        # Batch write results to DB (single transaction, much faster)
        if results_buffer:
            conn.executemany(
                "UPDATE questions SET answer_text=?, answer_source=?, confidence=?, confidence_level=?, answered_at=? WHERE id=?",
                results_buffer
            )
        conn.commit()
        self.state["results"]["total_answered"] = answered
        self.state["results"]["total_unknown"] = still_unknown
        return (1, {
            "status": "searched",
            "questions_searched": len(questions),
            "answered": answered,
            "still_unknown": still_unknown,
            "workers": workers,
            "files_preloaded": files_loaded,
            "words_preloaded": len(self._index_word_cache),
        }, None)

    def _search_source(self, source, question, q_type, obj_name, obj_type, file_path, obj_meta, index):
        """Search a specific source for an answer. Returns (answer_text, confidence)."""
        if source == "self":
            return self._answer_from_self(question, q_type, obj_name, obj_type, file_path, obj_meta)
        elif source == "code":
            return self._answer_from_code(question, q_type, obj_name, obj_type, file_path, index)
        elif source == "markdown":
            return self._answer_from_markdown(question, q_type, obj_name, index)
        elif source == "index":
            return self._answer_from_index(question, q_type, obj_name, index)
        elif source == "config":
            return self._answer_from_config(question, q_type, obj_name, obj_meta)
        elif source == "db":
            return self._answer_from_db(question, q_type, obj_name)
        elif source == "git":
            return self._answer_from_git(question, q_type, obj_name, file_path)
        return (None, 0)

    def _answer_from_self(self, question, q_type, obj_name, obj_type, file_path, obj_meta):
        """Answer questions from the object's own metadata — uses file cache."""
        confidence = SOURCE_WEIGHTS["self"]
        text = ""
        if "purpose" in question.lower() or "what is" in question.lower():
            if obj_type == "file":
                ext = obj_meta.get("ext", "")
                lines = obj_meta.get("lines", 0)
                text = f"{obj_name} is a {ext} file with {lines} lines in {obj_meta.get('dir', '')}"
            elif obj_type == "class":
                text = f"{obj_name} is a class defined in {file_path}"
            elif obj_type == "method":
                text = f"{obj_name} is a method. Signature: {obj_meta.get('signature', 'unknown')}"
            elif obj_type == "constant":
                text = f"{obj_name} is a constant. Definition: {obj_meta.get('value_line', '')}"
            elif obj_type == "import":
                text = f"{obj_name} is imported. Statement: {obj_meta.get('statement', '')}"
            elif obj_type == "state_key":
                text = f"self.state['{obj_name}'] is a state key in {obj_meta.get('class', '')}"
            elif obj_type == "dispatch_key":
                text = f"Run('{obj_name}') is a dispatch command in {obj_meta.get('class', '')}"
            elif obj_type == "bcl_rule":
                text = f"{obj_name} is a BCL rule token in the file header"
            elif obj_type == "md_section":
                text = f"{obj_name} is a markdown section (level {obj_meta.get('level', 0)}) in {obj_meta.get('file', '')}"
            elif obj_type == "db_table":
                text = f"{obj_name} is a database table defined in {obj_meta.get('file', '')}"
            elif obj_type == "config":
                text = f"{obj_name} is a config key: {obj_meta.get('line_text', '')}"
        elif "line count" in question.lower():
            text = f"{obj_meta.get('lines', 'unknown')} lines"
        elif "vbstyle" in question.lower() or "header" in question.lower():
            src = self._read_file_cached(file_path)
            if src:
                has_ghost = "#[@GHOST]" in src or "# [@GHOST]" in src
                has_vbstyle = "#[@VBSTYLE]" in src or "# [@VBSTYLE]" in src
                has_fileid = "#[@FILEID]" in src or "# [@FILEID]" in src
                text = f"GHOST={has_ghost}, VBSTYLE={has_vbstyle}, FILEID={has_fileid}"
        elif "domain" in question.lower() and obj_type in ("class", "file"):
            src = self._read_file_cached(file_path)
            if src:
                m = re.search(r'domain\s*=\s*"([^"]+)"', src[:2000])
                if m:
                    text = f"Domain: {m.group(1)}"
        elif "authority" in question.lower() and obj_type == "class":
            src = self._read_file_cached(file_path)
            if src:
                m = re.search(r'authority\s*=\s*"([^"]+)"', src[:2000])
                if m:
                    text = f"Authority: {m.group(1)}"
        elif "dispatch" in question.lower() and obj_type == "class":
            lines = self._read_lines_cached(file_path)
            if lines:
                for i, line in enumerate(lines):
                    if "def Run(" in line:
                        keys = self._extract_dispatch_keys(lines, i + 1)
                        if keys:
                            text = f"Dispatches: {', '.join(keys)}"
                            break
        elif "state" in question.lower() and "keys" in question.lower() and obj_type == "class":
            src = self._read_file_cached(file_path)
            if src:
                keys = self._extract_state_keys(src)
                if keys:
                    text = f"State keys: {', '.join(keys)}"
        elif "parameters" in question.lower() and obj_type == "method":
            sig = obj_meta.get("signature", "")
            if sig:
                text = f"Signature: {sig}"
        elif "return" in question.lower() and obj_type == "method":
            sig = obj_meta.get("signature", "")
            if "Tuple3" in question or "tuple" in question.lower():
                src = self._read_file_cached(file_path)
                if src:
                    if "return (1," in src or "return (0," in src:
                        text = "Returns Tuple3 (ok, data, error)"
        elif "defined" in question.lower() or "where is" in question.lower():
            text = f"Defined at {file_path}:{obj_meta.get('line', 1) if isinstance(obj_meta, dict) else 1}"
        elif "default value" in question.lower():
            text = obj_meta.get("value_line", "") or obj_meta.get("line_text", "")
        if text:
            return (text, confidence)
        return (None, 0)

    def _answer_from_code(self, question, q_type, obj_name, obj_type, file_path, index):
        """Search code files for answers — uses pre-loaded word cache."""
        confidence = SOURCE_WEIGHTS["code"]
        # Use pre-loaded cache if available
        rows = self._index_word_cache.get(obj_name)
        if not rows and index:
            # Fallback: query index directly
            rows = index.execute(
                "SELECT w.context, f.filename, w.line_num FROM words w JOIN files f ON w.file_id = f.id WHERE w.word = ? LIMIT 10",
                (obj_name,)
            ).fetchall()
            if not rows:
                rows = index.execute(
                    "SELECT w.context, f.filename, w.line_num FROM words w JOIN files f ON w.file_id = f.id WHERE w.word LIKE ? LIMIT 10",
                    (f"{obj_name}%",)
                ).fetchall()
                # Convert to tuple format
                rows = [(r[0], r[1], r[2]) for r in rows]
        if not rows:
            return (None, 0)
        # Build answer from found contexts
        files = set()
        for row in rows:
            files.add(row[1])
        if "where" in question.lower() or "who uses" in question.lower() or "who calls" in question.lower():
            return (f"Found in {len(files)} files: {', '.join(list(files)[:5])}", confidence)
        if "depend" in question.lower():
            return (f"Referenced by: {', '.join(list(files)[:5])}", confidence)
        if "tested" in question.lower():
            test_files = [f for f in files if "test" in f.lower()]
            if test_files:
                return (f"Tests found: {', '.join(test_files[:3])}", confidence)
            return (None, 0)
        if "calls" in question.lower() or "called" in question.lower():
            return (f"Called from {len(files)} files", confidence)
        # Generic: return first context
        return (f"Found in code: {rows[0][0][:100]}", confidence - 10)

    def _answer_from_markdown(self, question, q_type, obj_name, index):
        """Search markdown files for answers — uses index if cache miss."""
        confidence = SOURCE_WEIGHTS["markdown"]
        if index is None:
            return (None, 0)
        # Search phrases in markdown files
        rows = index.execute(
            "SELECT p.phrase, p.line_num, f.filename FROM phrases p JOIN files f ON p.file_id = f.id WHERE p.phrase LIKE ? AND f.ext = '.md' LIMIT 10",
            (f"%{obj_name}%",)
        ).fetchall()
        if not rows:
            return (None, 0)
        # Build answer from found phrases
        phrases = [r[0] for r in rows[:3]]
        return (f"Documented in markdown: {'. '.join(phrases)[:200]}", confidence)

    def _answer_from_index(self, question, q_type, obj_name, index):
        """Search the codebase index for answers."""
        if index is None:
            return (None, 0)
        confidence = SOURCE_WEIGHTS["index"]
        # Count occurrences
        rows = index.execute(
            "SELECT COUNT(DISTINCT f.filename) as file_count, COUNT(*) as total FROM words w JOIN files f ON w.file_id = f.id WHERE w.word = ?",
            (obj_name,)
        ).fetchone()
        if rows and rows[0] > 0:
            return (f"Found in {rows[0]} files, {rows[1]} occurrences", confidence)
        return (None, 0)

    def _answer_from_config(self, question, q_type, obj_name, obj_meta):
        """Search config files for answers."""
        confidence = SOURCE_WEIGHTS["config"]
        if obj_meta.get("line_text"):
            return (f"Config: {obj_meta['line_text']}", confidence)
        return (None, 0)

    def _answer_from_db(self, question, q_type, obj_name):
        """Search MySQL for answers (placeholder — requires MySQL)."""
        return (None, 0)

    def _answer_from_git(self, question, q_type, obj_name, file_path):
        """Search git history for answers (placeholder)."""
        return (None, 0)

    # ════════════════════════════════════════════════════════════════
    # PHASE 4: CONFIDENCE — score each answer
    # ════════════════════════════════════════════════════════════════

    def ScoreConfidence(self, params=None):
        """Score confidence for all answered questions.
        Boost confidence if answer found in multiple sources."""
        conn = self._get_understanding_db()
        questions = conn.execute(
            "SELECT id, answer_text, answer_source, confidence FROM questions WHERE answer_text IS NOT NULL"
        ).fetchall()
        boosted = 0
        for qid, answer_text, answer_source, current_conf in questions:
            # If answer found in multiple sources, boost confidence
            # Check if the same object has other answers from different sources
            obj_id = conn.execute("SELECT object_id FROM questions WHERE id=?", (qid,)).fetchone()
            if obj_id:
                other_answers = conn.execute(
                    "SELECT answer_source, confidence FROM questions WHERE object_id = ? AND answer_text IS NOT NULL AND id != ?",
                    (obj_id[0], qid)
                ).fetchall()
                sources = {answer_source}
                for oa in other_answers:
                    sources.add(oa[0])
                if len(sources) > 1:
                    new_conf = min(100, current_conf + 15)
                    level = self._confidence_to_level(new_conf)
                    conn.execute(
                        "UPDATE questions SET confidence=?, confidence_level=? WHERE id=?",
                        (new_conf, level, qid)
                    )
                    boosted += 1
        conn.commit()
        return (1, {
            "status": "scored",
            "total_answered": len(questions),
            "boosted_multi_source": boosted,
        }, None)

    def _confidence_to_level(self, confidence):
        """Convert numeric confidence to level string."""
        if confidence >= 85:
            return "verified"
        elif confidence >= 65:
            return "likely"
        elif confidence >= 35:
            return "weak"
        elif confidence > 0:
            return "weak"
        else:
            return "unknown"

    # ════════════════════════════════════════════════════════════════
    # PHASE 5: GAP DETECTION — re-ask weak answers, escalate unknowns
    # ════════════════════════════════════════════════════════════════

    def DetectGaps(self, params=None):
        """Detect gaps — questions with low confidence or no answer.
        Re-search with broader sources, or escalate."""
        conn = self._get_understanding_db()
        target = self._p(params, "target_confidence", self.state["config"]["target_confidence"])
        # Find gaps
        gaps = conn.execute(
            "SELECT q.id, q.question_text, q.confidence, q.confidence_level, q.search_sources, "
            "o.object_type, o.object_name, o.file_path "
            "FROM questions q JOIN objects o ON q.object_id = o.id "
            "WHERE q.confidence < ? OR q.answer_text IS NULL",
            (target,)
        ).fetchall()
        # Categorize gaps
        unknown = [g for g in gaps if g[3] == "unknown"]
        weak = [g for g in gaps if g[3] == "weak"]
        likely = [g for g in gaps if g[3] == "likely"]
        # For weak answers, try broader search (add all sources)
        re_searched = 0
        for g in weak:
            qid = g[0]
            # Expand search sources to all available
            all_sources = ["self", "code", "markdown", "index", "config", "db", "git"]
            conn.execute(
                "UPDATE questions SET search_sources=?, iteration=iteration+1 WHERE id=?",
                (json.dumps(all_sources), qid)
            )
            re_searched += 1
        conn.commit()
        return (1, {
            "status": "gaps_detected",
            "total_gaps": len(gaps),
            "unknown": len(unknown),
            "weak": len(weak),
            "likely": len(likely),
            "re_searched": re_searched,
            "target_confidence": target,
        }, None)

    # ════════════════════════════════════════════════════════════════
    # PHASE 6: MEASURE UNDERSTANDING — coverage percentages
    # ════════════════════════════════════════════════════════════════

    def MeasureUnderstanding(self, params=None):
        """Measure understanding coverage per object type and overall."""
        conn = self._get_understanding_db()
        target = self._p(params, "target_confidence", self.state["config"]["target_confidence"])
        # Per object type
        type_stats = {}
        for obj_type in OBJECT_TYPES:
            obj_count = conn.execute(
                "SELECT COUNT(DISTINCT o.id) FROM objects o WHERE o.object_type = ?", (obj_type,)
            ).fetchone()[0]
            if obj_count == 0:
                continue
            q_count = conn.execute(
                "SELECT COUNT(*) FROM questions q JOIN objects o ON q.object_id = o.id WHERE o.object_type = ?",
                (obj_type,)
            ).fetchone()[0]
            answered = conn.execute(
                "SELECT COUNT(*) FROM questions q JOIN objects o ON q.object_id = o.id "
                "WHERE o.object_type = ? AND q.confidence >= ?",
                (obj_type, target)
            ).fetchone()[0]
            unknown = conn.execute(
                "SELECT COUNT(*) FROM questions q JOIN objects o ON q.object_id = o.id "
                "WHERE o.object_type = ? AND q.confidence_level = 'unknown'",
                (obj_type,)
            ).fetchone()[0]
            pct = (answered / q_count * 100) if q_count > 0 else 0
            type_stats[obj_type] = {
                "objects": obj_count,
                "questions": q_count,
                "answered": answered,
                "unknown": unknown,
                "understanding_pct": round(pct, 1),
            }
        # Overall
        total_q = sum(s["questions"] for s in type_stats.values())
        total_answered = sum(s["answered"] for s in type_stats.values())
        total_unknown = sum(s["unknown"] for s in type_stats.values())
        overall_pct = (total_answered / total_q * 100) if total_q > 0 else 0
        self.state["catalog"]["understanding"] = type_stats
        return (1, {
            "status": "measured",
            "overall_understanding_pct": round(overall_pct, 1),
            "total_questions": total_q,
            "total_answered": total_answered,
            "total_unknown": total_unknown,
            "by_type": type_stats,
            "target_confidence": target,
        }, None)

    # ════════════════════════════════════════════════════════════════
    # FULL CYCLE — run all 6 phases
    # ════════════════════════════════════════════════════════════════

    def FullCycle(self, params=None):
        """Run all 6 phases in sequence. Optionally iterate."""
        max_iterations = self._p(params, "max_iterations", self.state["config"]["max_iterations"])
        results = {}
        # Phase 1: Observe
        ok1, obs_data, err1 = self.Observe(params)
        results["observe"] = {"ok": ok1, "data": obs_data, "error": err1}
        # Phase 2: Generate
        ok2, gen_data, err2 = self.Generate(params)
        results["generate"] = {"ok": ok2, "data": gen_data, "error": err2}
        # Phase 3-5: Iterate
        for i in range(max_iterations):
            ok3, search_data, err3 = self.SearchAnswers(params)
            results[f"search_iter_{i}"] = {"ok": ok3, "data": search_data, "error": err3}
            ok4, score_data, err4 = self.ScoreConfidence(params)
            results[f"score_iter_{i}"] = {"ok": ok4, "data": score_data, "error": err4}
            ok5, gap_data, err5 = self.DetectGaps(params)
            results[f"gaps_iter_{i}"] = {"ok": ok5, "data": gap_data, "error": err5}
            # If no gaps, stop
            if gap_data and gap_data.get("total_gaps", 0) == 0:
                break
        # Phase 6: Measure
        ok6, measure_data, err6 = self.MeasureUnderstanding(params)
        results["measure"] = {"ok": ok6, "data": measure_data, "error": err6}
        return (1, {
            "status": "full_cycle_complete",
            "iterations": max_iterations,
            "phases": results,
            "final_understanding": measure_data,
        }, None)

    # ════════════════════════════════════════════════════════════════
    # REPORT — human-readable summary
    # ════════════════════════════════════════════════════════════════

    def Report(self, params=None):
        """Generate a human-readable understanding report."""
        ok, data, err = self.MeasureUnderstanding(params)
        if not ok:
            return (0, data, err)
        lines = []
        lines.append("=" * 70)
        lines.append("UNDERSTANDING ENGINE — PROJECT KNOWLEDGE REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Overall Understanding: {data['overall_understanding_pct']}%")
        lines.append(f"  Questions:    {data['total_questions']}")
        lines.append(f"  Answered:     {data['total_answered']}")
        lines.append(f"  Unknown:      {data['total_unknown']}")
        lines.append(f"  Target:       {data['target_confidence']}% confidence")
        lines.append("")
        lines.append(f"{'Object Type':<20} {'Objects':>8} {'Questions':>10} {'Answered':>9} {'Unknown':>8} {'Understanding':>13}")
        lines.append("-" * 70)
        for obj_type, stats in sorted(data["by_type"].items(), key=lambda x: x[1]["understanding_pct"], reverse=True):
            lines.append(f"{obj_type:<20} {stats['objects']:>8} {stats['questions']:>10} {stats['answered']:>9} {stats['unknown']:>8} {stats['understanding_pct']:>12}%")
        lines.append("")
        # Show gaps
        lines.append("TOP GAPS (lowest understanding):")
        sorted_types = sorted(data["by_type"].items(), key=lambda x: x[1]["understanding_pct"])
        for obj_type, stats in sorted_types[:5]:
            if stats["understanding_pct"] < data["target_confidence"]:
                lines.append(f"  {obj_type}: {stats['understanding_pct']}% — {stats['unknown']} unknown questions need answers")
        lines.append("")
        lines.append("=" * 70)
        report_text = "\n".join(lines)
        return (1, {"report": report_text, "data": data}, None)

    def close(self):
        if self._store_conn:
            self._store_conn.close()
        if self._index_conn:
            self._index_conn.close()
        if self._understanding_conn:
            self._understanding_conn.close()


if __name__ == "__main__":
    import sys
    engine = UnderstandingEngine()
    if len(sys.argv) < 2:
        print("Usage: understanding_engine.py <command> [json_params]")
        print("Commands: observe, generate, search_answers, score_confidence,")
        print("          detect_gaps, measure, full_cycle, report")
        sys.exit(1)
    cmd = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ok, data, error = engine.Run(cmd, params)
    if ok:
        if isinstance(data, dict) and "report" in data:
            print(data["report"])
        else:
            print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
    engine.close()
