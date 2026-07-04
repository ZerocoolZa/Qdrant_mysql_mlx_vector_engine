# ChatMover Pipeline — Chats → MySQL → BCL → SQLite → Query

> **Core thesis:** Chat conversations from all sources (ChatGPT, Cascade, Devin, disk)
> are ingested into MySQL, compressed into BCL tokens, stored in SQLite with
> unresolved/resolved item tracking, and made queryable for future AI sessions.
>
> **Two phases:**
> 1. **Ingestion** — raw chats from all sources → unified MySQL database
> 2. **Compression** — MySQL chats → BCL tokens → SQLite store with item tracking
>
> **Think of it as a library:**
> - MySQL is the bookshelf (all raw chats, full text, searchable)
> - BCL tokens are the table of contents (compressed, queryable, fits in AI context)
> - SQLite is the card catalog (index of problems, decisions, unresolved items)
> - `[@CHATSOURCE]` is the page number (links back to the original)

---

## Pipeline Overview (End-to-End)

```
PHASE 1: INGESTION (chat_mover.py → MySQL)
  Sources → Classify → Filter → Parse → Import → Embed → Verify

PHASE 2: COMPRESSION (bcl_chat_compressor.py → BCL → bcl_chat_store.db)
  Find Chat → Store Original → Stage 1 (Code) → Store S1 → Stage 2 (AI) → Store S2 → Query
```

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CHATMOVER PIPELINE                              │
│                                                                         │
│  PHASE 1: INGESTION                PHASE 2: COMPRESSION                 │
│  ─────────────────                ──────────────────                    │
│  ChatGPT JSON  ─┐                 ┌─ Find .md chat exports              │
│  Cascade .pb   ─┤                 │  Store original in SQLite           │
│  Devin JSON    ─┼─→ MySQL ───────→├─ Stage 1: Regex/dict extraction    │
│  SQLite DBs    ─┤   (Chat_History)│  Store Stage 1 in SQLite            │
│  Disk .md      ─┘                 ├─ Stage 2: AI semantic pass          │
│                                  │  Store Stage 2 + items in SQLite    │
│                                  └─ Query unresolved → todo list       │
│                                                                         │
│  MySQL = full text storage     SQLite = BCL + item tracking             │
│  BCL = compressed index        [@CHATSOURCE] = link back to original    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## PHASE 1: Chat Ingestion (Sources → MySQL)

### Sources (4 chat systems, 3 formats)

| Source | Format | Location | Ingester |
|---|---|---|---|
| **ChatGPT** | JSON export files | `~/Downloads/chatgpt_chats/` | `chatgpt_mysql_ingest.py` |
| **Cascade (Windsurf)** | Encrypted .pb files | `~/.codeium/windsurf/cascade/` | `cascade_mysql.py` / `CascadeIngester.py` |
| **Devin CLI** | JSON transcripts (ATIF-v1.7) | `~/.local/share/devin/cli/transcripts/` | `Devin_Chat_msql.py` |
| **SQLite chat DBs** | Various schemas | `efl_brain.db`, `autocomplete.db`, `book.db` | `chat_mover.py` (auto-detect) |
| **MySQL sources** | Various tables | Config-defined `SOURCE_TABLES` | `chat_mover.py` |
| **Disk markdown** | .md chat exports | Config-defined `DISK_FOLDERS` | `chat_mover.py` |

### Destination Databases

| Database | Tables | Purpose |
|---|---|---|
| **`Chat_History`** | `sessions`, `messages`, `prompts`, `pipeline_state`, `error_knowledge` | Unified chat store (main destination) |
| **`cascade_chats`** | `trajectories`, `rounds`, `messages` | Cascade-specific (decrypted .pb files) |
| **`chatgpt_chats`** | `conversations`, `messages` | ChatGPT-specific (JSON exports) |
| **`devin`** | `devin_sessions`, `devin_messages`, `devin_tool_calls` | Devin CLI transcripts |

### Ingestion Steps (chat_mover.py, 8 steps)

```
Step 0:   Connect — acquire lock, connect to MySQL, test connection
Step 0.5: Create Schema — sessions, messages, prompts, pipeline_state, error_knowledge
Step 1:   Read & Classify — read all sources, classify_content() → chat/doc/other
Step 2:   Filter — keep only "chat" items, sort by date
Step 3:   Exclude Self — remove items from destination DB (prevent re-import)
Step 4:   Parse & Import — parse_md_chat()/parse_json_chat(), extract prompts, hash, import
Step 5:   Embed (optional) — Qdrant vector embeddings for semantic search
Step 7:   Verify — count rows, compare to source counts
Step 8:   Final — log summary, save state, release lock
```

### MySQL Schema (Chat_History)

```sql
CREATE TABLE sessions (
  row_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_name     VARCHAR(300) NOT NULL,
  source_db        VARCHAR(100),
  source_table     VARCHAR(100),
  source_format    VARCHAR(10),       -- 'md' or 'json'
  message_count    INT DEFAULT 0,
  content_hash     VARCHAR(64),       -- SHA-256 for dedup
  status           VARCHAR(50) DEFAULT 'imported',
  created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
  row_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id       BIGINT NOT NULL,
  role             VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
  content          LONGTEXT,
  sequence         INT NOT NULL,
  embedded         BOOLEAN DEFAULT FALSE,
  FOREIGN KEY (session_id) REFERENCES sessions(row_id) ON DELETE CASCADE
);

CREATE TABLE prompts (
  row_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id       BIGINT NOT NULL,
  prompt_text      TEXT NOT NULL,
  prompt_type      VARCHAR(50),
  FOREIGN KEY (session_id) REFERENCES sessions(row_id) ON DELETE CASCADE
);

CREATE TABLE error_knowledge (
  error_text       TEXT,
  error_type       VARCHAR(100),
  lesson           TEXT,
  solution         TEXT
);
```

### Ingestion CLI

```bash
# Full pipeline: MySQL sources → Chat_History
python3 chat_mover/chat_mover.py --source mysql

# Disk + SQLite sources
python3 chat_mover/chat_mover.py --source disk,sqlite

# With Qdrant embeddings
python3 chat_mover/chat_mover.py --source mysql --embed

# Dry run (validate only)
python3 chat_mover/chat_mover.py --source mysql --dry-run

# ChatGPT standalone
python3 chat_mover/chatgpt_mysql_ingest.py ~/Downloads/chatgpt_chats

# Cascade standalone (decrypt + ingest)
python3 chat_mover/cascade_mysql.py
python3 chat_mover/cascade_mysql.py --decrypt-only
python3 chat_mover/cascade_mysql.py --status

# Devin transcripts
python3 chat_mover/Devin_Chat_msql.py
```

---

## PHASE 2: BCL Chat Compression (Chats → BCL → SQLite)

### The Attachment Concept

```
┌─────────────────────────────────┐        ┌──────────────────────────────────┐
│  Compressed BCL File (.md)      │        │  Source Chat File (.md)          │
│  ~200 tokens, ~350 lines        │        │  4,304 lines, raw conversation   │
│                                 │        │                                  │
│  [@CHATSOURCE]{                 │───────►│  /Users/wws/Downloads/           │
│    path=".../CLI Error...md";   │  link  │    CLI Error Prevention.md       │
│    lines=4304;                  │        │                                  │
│    md5=63ff77a27e57;            │        │  Full user/AI dialogue,          │
│  }                              │        │  commands, errors, code blocks,  │
│                                 │        │  reasoning, debugging journey    │
│  [@USER_SAYS] "fix this issue"  │        │  ↑ AI reads this ONLY when       │
│  [@AI_SAYS]   "shell is zsh"    │        │    BCL tokens don't have enough  │
│  [@ERROR]     TypeError at 456  │        │    detail for the task           │
│  [@FILE]      cascade_cli.c     │        │                                  │
│  [@LESSON]    check before fix  │        │                                  │
└─────────────────────────────────┘        └──────────────────────────────────┘
```

**The BCL file is small enough to fit in an AI context window.**
**The source chat is too big, but it's always findable via `[@CHATSOURCE]`.**

### Compression Steps (7 steps)

```
Step 1: FIND        → Scan ~/Downloads/ for .md chat exports
Step 2: STORE       → Store original chat in bcl_chat_store.db (original_chats table)
Step 3: STAGE 1     → Run BclChatCompressor.Run("compress") — regex/dict extraction
Step 4: STORE S1    → Store Stage 1 output in bcl_chat_store.db (bcl_stage1 table)
Step 5: STAGE 2     → AI semantic pass over Stage 1 tokens
Step 6: STORE S2    → Store Stage 2 output + items in bcl_chat_store.db (bcl_stage2 + chat_items)
Step 7: QUERY       → Query unresolved items → todo list for next session
```

### Two-Stage Architecture

#### Stage 1: Code (deterministic, milliseconds)

| Extraction | Method | Token Output |
|---|---|---|
| User messages | Match `### User Input` headers | `[@USER_SAYS]` |
| AI messages | Match `### Planner Response` headers | `[@AI_SAYS]` |
| Errors | Regex: `Error`, `TypeError`, `Traceback`, `FAILED` | `[@ERROR]` |
| File paths | Regex: `[\w/]+\.py`, `[\w/]+\.c`, `[\w/]+\.md` | `[@FILE]` |
| Commands run | Match `*User accepted command*` blocks | `[@COMMAND_RAN]` |
| User approval | Match `accepted` / `rejected` | `[@USER_APPROVED]` / `[@USER_REJECTED]` |
| Frustration signals | Keyword dict: "stuck", "frozen", "why", "weird", "shit" | `[@FRUSTRATION_SIGNAL]` |
| Code blocks | Match ` ``` ` fenced blocks | `[@CODE_BLOCK]` |
| Topic boundaries | Heading changes, keyword shifts | `[@TOPIC]` |
| Questions | Regex `?` in user messages | `[@QUESTION]` |

#### Stage 2: AI (semantic, focused pass)

| Extraction | Method | Token Output |
|---|---|---|
| User intent | AI reads `[@USER_SAYS]` + context | `[@INTENT]` |
| User mood | AI infers from word choice, punctuation | `[@MOOD]` |
| Root cause | AI connects symptoms to causes | `[@ROOT_CAUSE]` |
| Problem → Solution pairing | AI matches problems to their fixes | `[@PROBLEM]` + `[@SOLUTION]` |
| Lesson extraction | AI generalizes from incident to rule | `[@LESSON]` |
| Success/Failed | AI judges if approach worked | `[@SUCCESS]` / `[@FAILED]` |
| AI correctness | AI evaluates if its response was right | `[@AI_CORRECT]` / `[@AI_WRONG]` |
| Decision rationale | AI explains why a choice was made | `[@DECISION]` |
| Unresolved items | AI identifies open/incomplete tasks | `[@UNRESOLVED]` |

### Token Types (BCL Chat Vocabulary)

#### Dialogue Tokens
| Token | Purpose | Stage |
|---|---|---|
| `[@USER_SAYS]` | What the user said, in order | Code |
| `[@AI_SAYS]` | What the AI responded, in order | Code |
| `[@QUESTION]` | User questions extracted from messages | Code (regex `?`) |
| `[@ANSWER]` | AI answers to those questions | AI |

#### Problem/Solution Tokens
| Token | Purpose | Stage |
|---|---|---|
| `[@PROBLEM]` | Issue identified | AI |
| `[@SOLUTION]` | How it was fixed | AI |
| `[@ROOT_CAUSE]` | Why it happened | AI |
| `[@ERROR]` | Technical error (TypeError, etc.) | Code |
| `[@FIX]` | Specific code fix applied | AI |

#### Outcome Tokens
| Token | Purpose | Stage |
|---|---|---|
| `[@SUCCESS]` | Approach that worked | AI |
| `[@FAILED]` | Approach that didn't work | AI |
| `[@LESSON]` | Cumulative takeaway, inline under problem | AI |
| `[@DECISION]` | Key decision point | AI |
| `[@UNRESOLVED]` | Open/incomplete item | AI |

#### Context Tokens
| Token | Purpose | Stage |
|---|---|---|
| `[@FILE]` | File path mentioned/modified | Code |
| `[@COMMAND_RAN]` | Command executed | Code |
| `[@USER_APPROVED]` | User accepted a command | Code |
| `[@USER_REJECTED]` | User rejected a command | Code |
| `[@FRUSTRATION_SIGNAL]` | Frustration keywords detected | Code |
| `[@MOOD]` | Inferred user mood | AI |
| `[@INTENT]` | Inferred user intent | AI |
| `[@TOPIC]` | Topic boundary | Code |

#### Meta Tokens
| Token | Purpose | Stage |
|---|---|---|
| `[@CHAT]` | Chat session metadata | Code |
| `[@CHATSOURCE]` | Link to original chat (path, md5, lines, date) | Code |
| `[@CHATFULLIDEARS]` | Compression metadata (tokens, ratio, stage) | Code |
| `[@USER_PREF]` | User preference extracted | AI |
| `[@STATS]` | Compression statistics | Code |
| `[@PENDING]` | Outstanding tasks | AI |
| `[@FUTURE]` | Future work identified | AI |

### Chronological Output Format

Tokens are output in **chronological order** with lessons inline:

```
# ─── T5: Decision Tree Audit (lines 1400-1700) ───
#[@USER_SAYS] "the JSON output is broken"
#[@AI_SAYS]   "found trailing comma in JSON array — fixing"
#[@PROBLEM]   JSON output has trailing comma — invalid JSON
#[@SOLUTION]  removed trailing comma, proper array formatting
#[@SUCCESS]   JSON output validates
#[@LESSON]    test JSON output with a validator — trailing commas are invalid JSON
```

Each timeline entry shows the full chain:
**user says → AI says → problem → root cause → solution → success/failed → lesson**

---

## SQLite Storage (bcl_chat_store.db)

**Location:** `chat_mover/ProceesChatDatabase/bcl_chat_store.db`

### Schema

```sql
-- Original chat files (full text stored)
CREATE TABLE original_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_name TEXT NOT NULL,
    md5_hash TEXT NOT NULL,
    line_count INTEGER NOT NULL,
    file_size INTEGER NOT NULL,
    date_ingested TEXT NOT NULL,
    content TEXT NOT NULL
);

-- Stage 1 BCL compression output
CREATE TABLE bcl_stage1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    compression_ratio REAL NOT NULL,
    output_lines INTEGER NOT NULL,
    output_text TEXT NOT NULL,
    stats_json TEXT,
    date_created TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES original_chats(id)
);

-- Stage 2 AI semantic pass output
CREATE TABLE bcl_stage2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    FOREIGN KEY (stage1_id) REFERENCES bcl_stage1(id)
);

-- Individual extracted items (problems, decisions, unresolved, etc.)
CREATE TABLE chat_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    stage2_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,       -- PROBLEM, UNRESOLVED, DECISION, SUCCESS, FAILED, LESSON
    line_number INTEGER,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'open',    -- open, resolved
    keyword TEXT,
    date_created TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES original_chats(id),
    FOREIGN KEY (stage2_id) REFERENCES bcl_stage2(id)
);
```

### SQLite CLI

```bash
# Database stats
python3 chat_mover/bcl_chat_store.py --stats

# List all stored chats
python3 chat_mover/bcl_chat_store.py --list

# List unresolved items (your todo list)
python3 chat_mover/bcl_chat_store.py --unresolved
```

### Python API (BclChatStore)

```python
import sys; sys.path.insert(0, "chat_mover")
from bcl_chat_store import BclChatStore

store = BclChatStore()
store.Run("open", {})
store.Run("store_chat", {"source_path": "/path/to/chat.md", "content": chat_text})
store.Run("store_stage1", {"chat_id": 1, "output_text": bcl_text, "token_count": 1999})
store.Run("store_stage2", {"chat_id": 1, "stage1_id": 1, "output_text": stage2_text, "items": items})
store.Run("get_unresolved", {})
store.Run("resolve_item", {"item_id": 5})
store.Run("get_stats", {})
store.Run("close", {})
```

---

## Compression CLI

### Stage 1 only (code extraction, no AI)

```bash
python3 chat_mover/bcl_chat_compressor.py --input "chat.md" --output "chat_BCL.md"
```

### Stage 1 + Stage 2 (code + AI)

```bash
# Stage 1 produces preliminary tokens
python3 chat_mover/bcl_chat_compressor.py --input "chat.md" --output "preliminary.md"

# Stage 2: feed preliminary.md to AI model
python3 chat_mover/bcl_chat_ai_prompt.py --input "preliminary.md" --source "chat.md"
```

### Full end-to-end ingestion (all 7 steps)

```bash
python3 chat_mover/ingest_bcl_chat.py
```

### Dry run (see what would be extracted)

```bash
python3 chat_mover/bcl_chat_compressor.py --input "chat.md" --dry-run
```

### Pipeline as Code (Python)

```python
import sys; sys.path.insert(0, "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover")
from bcl_chat_compressor import BclChatCompressor

compressor = BclChatCompressor()
rv = compressor.Run("compress", {
    "input_path": "/path/to/chat.md",
    "output_path": "/path/to/chat_BCL.md",
})
# rv = (1, {"output_path": "...", "tokens": [...], "stats": {...}}, None) on success
```

---

## Executable Pipeline (copy-paste to run)

```bash
#!/bin/bash
# ─── ChatMover Full Pipeline — Executable ───────────────────────
# Usage: Set CHAT_INPUT to your source chat .md file, then run.

CHAT_INPUT="${1:-}"
CHAT_MOVER_DIR="/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover"

if [ -z "$CHAT_INPUT" ]; then
  echo "ERROR: Set CHAT_INPUT or pass as argument"
  exit 1
fi

BASENAME=$(basename "$CHAT_INPUT" .md)
OUTPUT_STAGE1="${CHAT_MOVER_DIR}/${BASENAME}_BCL_stage1.md"
OUTPUT_PROMPT="${CHAT_MOVER_DIR}/${BASENAME}_AI_PROMPT.md"

echo "─── Stage 1: Code extraction ───"
python3 "${CHAT_MOVER_DIR}/bcl_chat_compressor.py" \
  --input "$CHAT_INPUT" \
  --output "$OUTPUT_STAGE1"

echo "─── Stage 2: AI prompt builder ───"
python3 "${CHAT_MOVER_DIR}/bcl_chat_ai_prompt.py" \
  --input "$OUTPUT_STAGE1" \
  --source "$CHAT_INPUT" \
  --output "$OUTPUT_PROMPT"

echo "─── Store in SQLite ───"
python3 "${CHAT_MOVER_DIR}/ingest_bcl_chat.py"

echo "─── Pipeline complete ───"
echo "  Stage 1: $OUTPUT_STAGE1"
echo "  AI prompt: $OUTPUT_PROMPT"
echo "  SQLite: ${CHAT_MOVER_DIR}/ProceesChatDatabase/bcl_chat_store.db"
```

---

## The Drill-Down Flow

```
AI needs context about "TypeError fix"
    ↓
Step 1: grep -r "[@ERROR]" chat_mover/*.md    → finds BCL file
    ↓
Step 2: Read BCL file (350 lines, fits in context)
    ↓
    [@ERROR]     L456 [python_error] TypeError: can only concatenate tuple
    [@PROBLEM]   class_violations was tuple, method_violations was list
    [@SOLUTION]  isinstance(rv, dict) → rv.get("violations", [])
    [@LESSON]    when interface returns may be list OR dict, check isinstance
    ↓
Step 3: Need more detail? Follow [@CHATSOURCE]
    ↓
    [@CHATSOURCE]{path="/Users/wws/Downloads/CLI Error Prevention.md";lines=4304}
    ↓
Step 4: Read lines 440-460 of source chat (the specific area)
    ↓
    Full debugging journey, reasoning, failed attempts, user dialogue
```

Or query the SQLite store:

```
python3 chat_mover/bcl_chat_store.py --unresolved
    ↓
    [28] L9400 (Mapping Dom_Graph Architecture.md) the mode u use must be...
    [29] L9455 (Mapping Dom_Graph Architecture.md) Can you tell me is this...
    [30] L9563 (Mapping Dom_Graph Architecture.md) So, go and look at the GUI...
    ↓
    Mark resolved when done:
    store.Run("resolve_item", {"item_id": 28})
```

---

## Config (chat_mover/Config_chat_mover.py)

| Key | Default | Description |
|---|---|---|
| `BCL_CHAT_DB_PATH` | `chat_mover/ProceesChatDatabase/bcl_chat_store.db` | SQLite database path |
| `stage1_min_lines` | 500 | Min chat lines to trigger compression |
| `stage1_extractors` | errors, files, commands, frustration, dialogue, questions, code_blocks, topic_boundaries | Stage 1 extractors |
| `stage2_extractors` | problems, unresolved, decisions, successes, failed, lessons | Stage 2 extractors |
| `chat_sources_dir` | `~/Downloads` | Where to find .md chat exports |
| `compression_module` | `bcl_chat_compressor` | Stage 1 module |
| `stage2_module` | `bcl_chat_ai_prompt` | Stage 2 module |
| `store_module` | `bcl_chat_store` | SQLite storage module |

### MySQL Config

| Key | Value |
|---|---|
| `user` | root |
| `host` | localhost |
| `port` | 3306 |
| `database` | vb_shared |

---

## File Register

| File | Location | Purpose | Phase |
|---|---|---|---|
| `Config.py` | `chat_mover/` | MySQL config, schema SQL, source definitions | Both |
| `Config_chat_mover.py` | `chat_mover/` | BCL chat store config, pipeline config, DB paths | Both |
| `chat_mover.py` | `chat_mover/` | Main ingestion pipeline orchestrator (1779 lines) | Phase 1 |
| `chatgpt_mysql_ingest.py` | `chat_mover/` | ChatGPT JSON → MySQL (standalone) | Phase 1 |
| `cascade_mysql.py` | `chat_mover/` | Cascade .pb decrypt → MySQL (standalone) | Phase 1 |
| `CascadeIngester.py` | `chat_mover/` | Cascade .pb decrypt → MySQL (VBStyle, Run() dispatch) | Phase 1 |
| `Devin_Chat_msql.py` | `chat_mover/` | Devin transcripts → Chat_History MySQL | Phase 1 |
| `MySQLIngester.py` | `chat_mover/` | ChatGPT fetcher → MySQL (VBStyle) | Phase 1 |
| `decrypt_pb.py` | `chat_mover/` | Protobuf decryption for Cascade .pb files | Phase 1 |
| `scan_trajectory.py` | `chat_mover/` | Trajectory parser for decrypted Cascade files | Phase 1 |
| `export_md.py` | `chat_mover/` | Markdown export utilities for Cascade | Phase 1 |
| `bcl_chat_compressor.py` | `chat_mover/` | Stage 1: code-based BCL extraction | Phase 2 |
| `bcl_chat_ai_prompt.py` | `chat_mover/` | Stage 2: AI prompt builder for semantic pass | Phase 2 |
| `bcl_chat_store.py` | `chat_mover/` | SQLite storage (Run dispatch, Tuple3) | Phase 2 |
| `bcl_state.py` | `chat_mover/` | BCL state serialization (dicts ↔ BCL text) | Phase 2 |
| `ingest_bcl_chat.py` | `chat_mover/` | End-to-end ingestion script (all 7 steps) | Phase 2 |
| `ChatExportTracker.py` | `chat_mover/` | Tracks which chats have been exported | Both |
| `validate.py` | `chat_mover/` | Validation utilities | Both |
| `reason.py` | `chat_mover/` | BCL reasoning stamps for code units | Both |
| `plan.py` | `chat_mover/` | Planning utilities | Both |
| `gap_analysis.py` | `chat_mover/` | Gap analysis for chat coverage | Both |
| `codegps.py` | `chat_mover/` | Code GPS for chat navigation (PyQt6) | Both |
| `codegps_garmin.py` | `chat_mover/` | Garmin-style navigator for chat graph | Both |
| `codegps_map.py` | `chat_mover/` | Map rendering for chat graph (Tkinter) | Both |
| `gen_gps_svg.py` | `chat_mover/` | SVG generation for GPS visualization | Both |
| `pipeline_maker.py` | `chat_mover/` | Pipeline spec validation and creation | Both |
| `ingest.py` | `chat_mover/` | Code ingestion (AST → SQLite, for chat_mover codebase) | Both |

---

## Compression Stats (from test runs)

| Metric | Raw Chat | Checkpoint | BCL v1 (grouped) | BCL v2 (chronological) | Stage 1 + SQLite |
|---|---|---|---|---|---|
| Lines | 4,304 | ~200 | 333 | 348 | 3,340 |
| Compression | 1:1 | 22:1 | 13:1 | 12:1 | 5:1 |
| Info retained | 100% | ~65% | ~90% | ~95% | ~90% |
| Queryable | no | no | yes | yes | yes (SQLite) |
| Chronological | yes | no | no | yes | yes |
| Inline lessons | n/a | no | no | yes | yes |
| Item tracking | no | no | no | no | yes (open/resolved) |
| Drill-down | n/a | no | yes | yes | yes ([@CHATSOURCE]) |

### Mapping Dom_Graph Architecture (test case)

| Metric | Value |
|---|---|
| Source lines | 10,427 |
| Stage 1 tokens | 1,999 |
| Compression ratio | 5.2:1 |
| Stage 2 items | 140 (27 problems, 11 unresolved, 41 decisions, 38 successes, 20 failed, 3 lessons) |
| Open items | 58 |
| Resolved items | 82 |

---

## Integration with Other Pipelines

| Pipeline | Relationship |
|---|---|
| **BCL Code Graph (Road 6)** | BCL formatter/engine reused for token formatting and validation |
| **Error Capture (Road 5)** | `[@ERROR]` and `[@LESSON]` tokens feed into error knowledge base |
| **CLI Safe Execution (Road 7)** | `[@LESSON]` tokens become learned_rules for CLI pattern DB |
| **Context Expansion (Road 8)** | BCL compressed chats are compact context for future sessions |
| **CodeGPS Garmin (Road 10)** | ChatMover pipeline is a road on the Garmin navigator |
| **Magnetic Search (msearch3)** | BCL files are searchable — `msearch3 "TypeError"` finds compressed token |

---

## Current Status

| Component | Status | Phase |
|---|---|---|
| `chat_mover.py` (ingestion pipeline) | **WORKING** | Phase 1 |
| `Config.py` (MySQL config + schema) | **WORKING** | Phase 1 |
| `chatgpt_mysql_ingest.py` | **WORKING** | Phase 1 |
| `cascade_mysql.py` | **WORKING** | Phase 1 |
| `CascadeIngester.py` (VBStyle) | **WORKING** | Phase 1 |
| `Devin_Chat_msql.py` | **WORKING** | Phase 1 |
| Qdrant embeddings | **WORKING** (optional `--embed`) | Phase 1 |
| `bcl_chat_compressor.py` (Stage 1) | **WORKING** | Phase 2 |
| `bcl_chat_ai_prompt.py` (Stage 2) | **WORKING** | Phase 2 |
| `bcl_chat_store.py` (SQLite storage) | **WORKING** | Phase 2 |
| `ingest_bcl_chat.py` (end-to-end) | **WORKING** | Phase 2 |
| `Config_chat_mover.py` (BCL config) | **WORKING** | Phase 2 |
| Pipeline locking | **WORKING** | Both |
| Pipeline state tracking | **WORKING** | Both |
| Validation mode | **WORKING** | Both |
| Error knowledge | **WORKING** | Both |

---

*Merged from `BCL_CHAT_COMPRESSION_PIPELINE.md` + `CHAT_INGESTION_PIPELINE.md` on 2026-06-28.*
