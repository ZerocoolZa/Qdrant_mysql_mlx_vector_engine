# Word Index Search Pipeline — Index Files → Search Word → Get ±N Words of Context

> **Core thesis:** You have 36+ `.md` pipeline docs and hundreds of source files.
> You need to find where a word appears and read the content around it — fast.
> No embeddings, no semantic search, no AI. Just: word in → file + context out.
>
> **The Garmin Principle:** This is a utility road. Short, direct, always green.
> Index once, search instantly. The simplest pipeline — but the one you use every day.

---

## Pipeline Overview

```
Files (.md, .py, .txt, ...) → Split into words → Store [word, file, line, word_pos] in SQLite
                                                                          ↓
Search word → Query SQLite → Get word_pos → Collect ±N words → Return clean table + chunks
```

---

## What Pipeline to Read to Do the Job

**Read this file.** That's it. This is the only pipeline you need for word-based search.

**The tool:** `core/Piplines/make.py` — class `WordIndexer`

**The database:** `core/Piplines/word_index.db` (SQLite, auto-created on first index)

---

## Stages

### Stage 1: INDEX — Read Files, Split Into Words, Store Positions

```bash
python3 core/Piplines/make.py --index-dir /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Piplines
```

What happens:
1. Walk the directory tree (skip `.git`, `__pycache__`, etc.)
2. For each file with a supported extension (`.md`, `.py`, `.txt`, `.sql`, `.sh`, `.c`, `.h`, `.json`, `.yaml`, `.bcl`)
3. Read every line
4. Split each line into words (regex: `[A-Za-z_][A-Za-z0-9_]*`)
5. Store `[word, word_lower, file_path, file_name, line_number, word_pos]` in SQLite
   - `word_pos` = global word position in file (0, 1, 2, 3, ...)

**Output:** `word_index.db` with table `words` — one row per word occurrence.

**Time:** ~2 seconds for 36 files, 189K words.

### Stage 2: SEARCH — Word In, ±N Words of Context Out

```bash
# Default: ±50 words around each match
python3 core/Piplines/make.py --search "Garmin"

# Small chunk: ±50 words
python3 core/Piplines/make.py --search "Garmin" --radius 50

# Big chunk: ±1000 words (like reading a whole section)
python3 core/Piplines/make.py --search "Config" --radius 1000

# Show table + full chunk text
python3 core/Piplines/make.py --search "Garmin" --radius 50 --full
```

What happens:
1. Query SQLite: `SELECT DISTINCT file_path, line_number, word_pos FROM words WHERE word_lower = 'garmin'`
2. If exact match fails, try prefix match: `word_lower LIKE 'garmin%'`
3. For each match, query: `SELECT word FROM words WHERE file_path = ? AND word_pos BETWEEN match_pos - radius AND match_pos + radius`
4. Join the words back into a chunk of text
5. Print a **clean table** with: #, File, Line, WordPos, Context Preview

**Output (table):**
```
  SEARCH: Garmin  |  matches: 5  |  files: 1  |  radius: +50/-50 words
  FILES: Plf_BclCodeGraphPipeline.md

+----+------------------------------+--------+----------+--------------------------------------------------+
|  # | File                         |   Line |  WordPos | Context Preview (101 words)                      |
+----+------------------------------+--------+----------+--------------------------------------------------+
|  1 | Plf_BclCodeGraphPipeline.md  |      8 |       55 | Computational Units BCL Identity MySQL Core t... |
|  2 | Plf_BclCodeGraphPipeline.md  |      8 |       63 | is not just text Every py file is parsed into... |
+----+------------------------------+--------+----------+--------------------------------------------------+
```

**Output (with `--full`):** Table + full chunk text for each match, 100 chars per line.

### Stage 3: STATS — What's Indexed

```bash
python3 core/Piplines/make.py --stats
```

**Output:**
```
WORD INDEX STATS:
  Total words:    189911
  Unique words:   16437
  Files indexed:  37
```

---

## CLI Reference

| Command | What it does |
|---------|-------------|
| `--index-dir PATH` | Index all files in a directory tree |
| `--index-file PATH` | Index a single file |
| `--search WORD` | Search for a word, get ±N words of context per match |
| `--radius N` | Words above and below each match (default 50) |
| `--limit N` | Max matches to return (default 50) |
| `--full` | Print full chunk text in addition to the table |
| `--stats` | Show index statistics |
| `--db PATH` | Use a different SQLite database path |

---

## Radius = Word Chunking

The radius is in **words**, not lines. This is like chunking:

| Radius | Words above | Words below | Total chunk | Use case |
|--------|-------------|-------------|-------------|----------|
| 10 | 10 | 10 | ~20 words | Quick glance — what's right next to the word |
| 50 | 50 | 50 | ~100 words | Sentence-level context (default) |
| 200 | 200 | 200 | ~400 words | Paragraph-level context |
| 1000 | 1000 | 1000 | ~2000 words | Section-level context — read the whole discussion |
| 5000 | 5000 | 5000 | ~10000 words | Near-file-level — almost the whole document |

**AI can set the radius dynamically:**
- Need a quick scan? `radius=10`
- Need to understand a paragraph? `radius=200`
- Need to read the full discussion? `radius=1000`

---

## API (Python)

```python
from make import WordIndexer

idx = WordIndexer()

# Index a directory
ok, data, err = idx.Run("index_dir", {"dir": "/path/to/files"})

# Search — ±50 words around each match (default)
ok, data, err = idx.Run("search", {"word": "Garmin", "radius": 50})
# data = {
#     "word": "Garmin",
#     "matches": 5,
#     "radius": 50,
#     "files": ["/path/to/Plf_BclCodeGraphPipeline.md"],
#     "results": [
#         {
#             "num": 1,
#             "file": "...",
#             "file_name": "Plf_BclCodeGraphPipeline.md",
#             "match_line": 8,
#             "word_pos": 55,
#             "chunk_start_line": 1,
#             "chunk_end_line": 18,
#             "chunk_word_count": 101,
#             "chunk_text": "Computational Units BCL Identity MySQL ...",
#             "preview": "Computational Units BCL Identity MySQL Core t..."
#         },
#         ...
#     ]
# }

# Big chunk — ±1000 words
ok, data, err = idx.Run("search", {"word": "Config", "radius": 1000})

# Stats
ok, data, err = idx.Run("stats", {})
```

---

## SQLite Schema

```sql
CREATE TABLE words (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT NOT NULL,
    word_lower  TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    word_pos    INTEGER NOT NULL
);

CREATE INDEX idx_word       ON words(word_lower);
CREATE INDEX idx_file       ON words(file_path);
CREATE INDEX idx_pos        ON words(file_path, word_pos);
CREATE INDEX idx_word_file  ON words(word_lower, file_path);
```

**Key column:** `word_pos` — the global position of the word in the file (0, 1, 2, ...).
This enables the chunk query: `WHERE file_path = ? AND word_pos BETWEEN pos - radius AND pos + radius`.

---

## When to Use This Pipeline

- **"Where did we talk about X?"** — Search the `.md` pipeline docs
- **"Which files mention this class/function name?"** — Index `.py` files, search the name
- **"Show me 1000 words of context around every mention of 'Garmin'"** — `--search "Garmin" --radius 1000`
- **"What files reference 'Config'?"** — Search returns file list + table + chunks

## When NOT to Use This Pipeline

- **Semantic search** ("find things related to navigation") → use embeddings (Pinecone/Qdrant)
- **Regex search** → use `grep -rn`
- **Chat history search** → use `msearch3` (Magnetic Search pipeline)

---

## File Locations

| File | Purpose |
|------|---------|
| `core/Piplines/make.py` | The tool — `WordIndexer` class + CLI |
| `core/Piplines/word_index.db` | The database — auto-created on first index |
| `core/Piplines/Plf_WordIndexSearch.md` | This doc — the pipeline description |

---

## Relationship to Other Pipelines

This is the **simplest search pipeline**. It sits before Magnetic Radius Search
(`Plf_MagneticRadiusSearch.md`) and Context Expansion (`Plf_ContextExpansionPipeline.md`)
in the search hierarchy:

```
Word Index Search (this)     — exact word, ±N words, SQLite, instant, clean table
       ↓
Magnetic Radius Search       — exact word across chats, ±200 lines, C binary
       ↓
Context Expansion Pipeline   — word → nodes/edges → graph → domain → BCL identity
       ↓
Semantic Search (Pinecone)   — meaning-based, vector similarity, probabilistic
```

**Use Word Index when:** you know the word, you want the context, you want it in a clean table.
**Use Magnetic Radius when:** you're searching across chat history, not files.
**Use Semantic when:** you don't know the exact word, just the concept.
