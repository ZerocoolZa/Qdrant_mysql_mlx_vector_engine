# Chat to Our Final DB — Pipeline

## Prerequisites

- Python 3.10+
- MySQL server running and accessible
- Qdrant running on `localhost:6333`
- Embedding model installed (SentenceTransformer or MLX)
- `dom_system`, `dom_db`, and `Kernel` modules available
- Destination database `Chat_History` created (or pipeline creates it in Step 0.5)
- Existing script `import_md_files.py` will be replaced by this pipeline

## Configuration

Pipeline reads connection details from a JSON config file (`pipeline_config.json`) or environment variables:

- **MySQL host** — e.g. `localhost`
- **MySQL port** — e.g. `3306`
- **MySQL user** — credentials
- **MySQL password** — **env var only** (`MYSQL_PASSWORD`), never in CLI args or config file (visible in `ps aux`)
- **MySQL source tables** — list of `{database, table, filename_col, content_col, date_col}` mappings (different tables may have different column names)
- **Qdrant host** — `localhost`
- **Qdrant port** — `6333`
- **Embedding model** — e.g. `all-MiniLM-L6-v2` (384 dimensions)
- **Batch size** — e.g. `500` messages per batch
- **Log file path** — e.g. `./pipeline.log`
- **Log rotation** — max 10MB per file, keep 5 rotated files

Example `pipeline_config.json`:
```json
{
  "mysql": {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "source_tables": [
      {"database": "vbstyle_documents", "table": "markdown_files", "filename_col": "filename", "content_col": "content", "date_col": "created_at"},
      {"database": "vb_shared", "table": "chat_ingestions", "filename_col": "session_name", "content_col": "content", "date_col": "ingested_at"}
    ]
  },
  "qdrant": {"host": "localhost", "port": 6333},
  "embedding": {"model": "all-MiniLM-L6-v2", "dimensions": 384},
  "batch_size": 500,
  "log_file": "./pipeline.log"
}
```

## Destination Schema

Three tables in the `Chat_History` database:

### sessions
| Column | Type | Description |
|--------|------|-------------|
| `row_id` | INT AUTO_INCREMENT | Primary key |
| `session_name` | VARCHAR(255) | Name/title of the conversation |
| `source_db` | VARCHAR(100) | Which database it came from |
| `source_table` | VARCHAR(100) | Which table it came from |
| `source_format` | VARCHAR(10) | `.md` or `.json` |
| `source_created_at` | TIMESTAMP NULL | File creation date (disk source) or row insert date (MySQL) |
| `source_modified_at` | TIMESTAMP NULL | File modification date (disk) or row update date (MySQL) |
| `message_count` | INT | Number of messages in session |
| `created_at` | TIMESTAMP | When imported |
| `status` | VARCHAR(50) | `imported`, `processed`, `error` |
| `content_hash` | VARCHAR(64) | SHA-256 of all message content — for dedup |
| `metadata` | JSON NULL | Extracted metadata (timestamps, model names, etc.) |

### messages
| Column | Type | Description |
|--------|------|-------------|
| `row_id` | INT AUTO_INCREMENT | Primary key |
| `session_id` | INT | FK to sessions.row_id |
| `role` | VARCHAR(20) | `user`, `assistant`, `system` |
| `content` | TEXT | Message content |
| `sequence` | INT | Order within session (0, 1, 2...) |
| `source_row_id` | INT | Original row ID from source table |
| `embedded` | BOOLEAN | Whether embedding was created |
| `created_at` | TIMESTAMP | When imported |

### prompts
| Column | Type | Description |
|--------|------|-------------|
| `row_id` | INT AUTO_INCREMENT | Primary key |
| `session_id` | INT | FK to sessions.row_id |
| `prompt_text` | TEXT | The prompt that started the conversation |
| `prompt_type` | VARCHAR(50) | `initial`, `follow_up`, `system` |
| `created_at` | TIMESTAMP | When imported |

---

## Step 0: Select Source

Choose where to read `.md` and `.json` chat files from. We're looking for chat conversations (user/assistant exchanges) stored as `.md` or `.json` content.

### Source Options

- **MySQL** — `SELECT` from tables, content stored as rows/columns
  - Known tables: `vbstyle_documents.markdown_files`, `vb_shared` databases
  - Connection: host, port, user, password from config
  - Query: `SELECT id, filename, content FROM <table> WHERE filename LIKE '%.md' OR filename LIKE '%.json'`
  - **Source table schema:** column names defined in config (`filename_col`, `content_col`, `date_col`) — not hardcoded, different tables may have different column names
  - **Date columns:** use `date_col` from config per source table for `source_created_at` and `source_modified_at`

- **SQLite** — `SELECT` from tables, same as MySQL but different driver
  - Connection: file path to `.db` or `.sqlite` file
  - Query: same as MySQL

- **Disk** — `os.listdir()` + `open()`, read files directly from folders
  - Path: specific folder path(s) to scan
  - Recursive: scan subdirectories
  - Read: `open(filepath, 'r', encoding='utf-8', errors='replace')`
  - **File metadata:** extract `os.stat()` — `st_mtime` (modified), `st_birthtime` (created) on macOS
  - Store as `source_created_at` and `source_modified_at` on the session row
  - Used for chronological ordering and prioritization (new vs old)
  - **Timezone:** all dates normalized to UTC before storage — disk dates are local, MySQL may be UTC, normalize everything to avoid ordering issues

- **Multiple sources** — `--source mysql,disk` imports from both at the same time
  - Each source is processed independently through Steps 1-4
  - Results are merged into the same `Chat_History` tables
  - `source_db` and `source_table` columns track origin per session

### How to Select

- CLI argument: `--source mysql|sqlite|disk`
- If MySQL: `--host`, `--port`, `--user`, `--password`, `--database`
- If SQLite: `--db-path`
- If Disk: `--folder`
- Or read from config file

### What Happens After Selection

- Connect to the source
- Verify connection works
- If connection fails → log error and exit
- Move to Step 0.5

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| MySQL reachable | `ping` host:port | Exit — don't proceed without source |
| MySQL credentials valid | `SELECT 1` test query | Exit — don't retry wrong credentials |
| Disk folder exists | `os.path.isdir()` | Exit |
| Disk folder readable | `os.access(folder, os.R_OK)` | Exit — fix permissions first |
| Disk has free space (>1GB) | `shutil.disk_usage()` | Exit — embeddings need disk for Qdrant |
| Qdrant reachable | `GET /collections` | Warn — can proceed without embeddings, do them later |
| Embedding model installed | `import sentence_transformers` | Warn — can proceed without embeddings |
| MySQL `max_allowed_packet` >= 16MB | `SHOW VARIABLES` | Warn — will auto-reduce batch size if needed |
| Lock file exists | `.pipeline.lock` not present | Exit — another run in progress |
| `MYSQL_PASSWORD` env var set | `os.environ.get()` | Exit — password required |

### Failure Branches

| What fails | Action |
|------------|--------|
| MySQL connection refused | Retry 3× (1s, 5s, 15s backoff), then exit with error |
| MySQL auth failed | Log error, exit — don't retry (wrong credentials) |
| SQLite file not found | Log error, exit |
| Disk folder not found | Log error, exit |
| Disk folder empty | Log warning, exit — nothing to import |
| Multiple sources, one fails | Log error for failed source, continue with remaining sources |

---

## Step 0.5: Create Destination Tables

Create the `Chat_History` database and its three tables if they don't exist.

- Run DDL statements:
  - `CREATE DATABASE IF NOT EXISTS Chat_History`
  - `CREATE TABLE IF NOT EXISTS sessions (...)`
  - `CREATE TABLE IF NOT EXISTS messages (...)`
  - `CREATE TABLE IF NOT EXISTS prompts (...)`
  - `CREATE TABLE IF NOT EXISTS pipeline_state (...)` for resume support
- **Indexes (create after tables):**
  - `CREATE UNIQUE INDEX idx_session_unique ON sessions(source_db, source_table, session_name)` — for idempotency
  - `CREATE INDEX idx_session_status ON sessions(status)` — for filtering
  - `CREATE INDEX idx_session_dates ON sessions(source_modified_at)` — for date range queries
  - `CREATE INDEX idx_message_session ON messages(session_id)` — for joins
  - `CREATE INDEX idx_message_embedded ON messages(embedded)` — for embedding resume
  - `CREATE INDEX idx_message_seq ON messages(session_id, sequence)` — for ordered retrieval
  - `CREATE INDEX idx_prompt_session ON prompts(session_id)` — for joins
  - `CREATE UNIQUE INDEX idx_session_hash ON sessions(content_hash)` — for content dedup
- **`pipeline_state` table schema:**
  | Column | Type | Description |
  |--------|------|-------------|
  | `id` | INT | Primary key (always 1) |
  | `current_step` | VARCHAR(20) | Which step we're on (0-8) |
  | `last_processed_id` | INT | Last source row/file ID processed |
  | `batch_number` | INT | Current batch number |
  | `started_at` | TIMESTAMP | When pipeline started |
  | `updated_at` | TIMESTAMP | Last update time |
  | `status` | VARCHAR(50) | `running`, `paused`, `complete`, `failed` |
- If tables already exist → verify schema matches, skip creation
- If schema mismatch → log error, ask user to migrate or drop
- This step is idempotent — safe to run multiple times

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| MySQL user has CREATE privilege | `SHOW GRANTS` | Exit — need DB admin |
| Database name not already used by source | Check `source_tables` config | Exit — destination can't be same as source |
| Disk has space for new tables (>500MB) | `shutil.disk_usage()` | Warn — may fail for large imports |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| `CREATE DATABASE` permission denied | A: retry with `CREATE SCHEMA` → B: try creating in existing DB → C: prompt user for admin credentials |
| `CREATE TABLE` fails | A: retry once → B: check if table exists with different schema → C: prompt user to `--force` drop and recreate |
| Tables exist but schema mismatch | A: log diff → B: prompt user: `--force` to drop, or `--migrate` to add missing columns → C: exit |
| Index creation fails | A: retry without `UNIQUE` constraint → B: skip index, log → C: continue (indexes are optimization) |
| MySQL connection drops during DDL | A: reconnect + retry → B: wait 5s + retry → C: prompt user to check MySQL |

---

## Step 1: Count and Classify All Files

Count all `.md` and `.json` content from the selected source, and classify each item while counting — so we know what's a chat, what's a doc, and what's other.

### Filename Pre-Filter

Before reading content, filter by filename. Skip files that are clearly not chats:

- **Pass 1 — Name pattern filter:**
  - **Skip:** `README.md`, `CHANGELOG.md`, `LICENSE.md`, `CONTRIBUTING.md`
  - **Skip:** `schema.json`, `package.json`, `config.json`, `tsconfig.json`
  - **Skip:** `.min.json`, `.lock.json`
  - **Skip:** `PLAN*.md`, `TODO*.md`, `NOTES*.md`
  - **Skip:** any file starting with `.` (hidden files)
  - **Keep:** `chat_*.md`, `conversation_*.md`, `session_*.md`
  - **Keep:** `*_chat.json`, `*_export.json`, `conversations.json`
  - **Keep:** files with `ChatGPT` or `Claude` in the name
  - Log all skipped files with reason

- **Pass 2 — Size filter (dynamic, calculated from Pass 1 survivors):**
  - From Pass 1 survivors, sample up to 1000 files
  - Read their content, classify as chat/doc/other
  - `avg_chat_size` = mean byte size of files classified as chat in sample
  - `min_threshold` = `avg_chat_size * 0.1` (10% of average)
  - `max_threshold` = `avg_chat_size * 10` (10x average)
  - Files < `min_threshold` → skip as `other` (too small to be a real conversation)
  - Files > `max_threshold` → log as oversized, flag for manual review
  - Empty files (0 bytes) → skip as `other`
  - Example: if average chat is 15KB → min = 1.5KB, max = 150KB
  - Thresholds are calculated at runtime, not hardcoded

- **Pass 3 — Path filter (disk source only):**
  - Skip: `node_modules/`, `.git/`, `__pycache__/`, `venv/`, `.venv/`
  - Skip: any path containing `/vendor/` or `/dist/`

- Files that pass all three filters proceed to content-based classification below

### Counting

- If MySQL/SQLite: `SELECT COUNT(*)` per table, then iterate rows
- If Disk: `os.walk()` and count `.md`/`.json` files
- Exclude: `Chat_History` database (the destination, not a source)
- If `Chat_History` doesn't exist yet (first run), skip exclusion
- **Large table strategy:** if a table has >50,000 rows, use sampling:
  - Read first 1000 chars of each row to classify (not full content)
  - For confirmed chat files, full content is read in Step 4
  - This avoids loading millions of full documents into memory just to classify

### Classification

For each file/row, read its content and classify:

- **Chat** — contains conversation data with alternating user/assistant messages
- **Documentation** — technical docs, schema files, plans (no user/assistant pattern)
- **Other** — anything that doesn't fit the above (empty, binary, code-only, etc.)

### Classification Method

**For `.md` files:**
- Look for patterns like:
  - `**User:**` / `**Assistant:**` blocks
  - `## User` / `## Assistant` headers
  - `> User:` / `> Assistant:` quote blocks
  - `Human:` / `Assistant:` labels
- Threshold: at least 2 alternating messages (1 user + 1 assistant) to be classified as chat
- If only one message or no alternation → documentation or other

**For `.json` files:**
- Parse JSON, look for:
  - `messages` array with `role` and `content` fields
  - `mapping` object with message nodes (ChatGPT export format)
  - `conversation` array with `sender` and `text` fields
- Threshold: at least 2 messages with different roles to be classified as chat
- If JSON parse fails → other
- If JSON has no message structure → documentation or other

### Edge Cases

- File is partially chat and partially doc → classify as chat (has conversation data)
- File is empty → other
- File has only system messages, no user/assistant → other
- File has only one user message, no response → other
- Encoding issues → use `errors='replace'`, classify as other if unreadable
- Non-English chats → still classify as chat, log detected language for embedding model awareness
- File with null bytes or invalid UTF-8 → sanitize with `errors='replace'`, classify normally
- File with extremely long lines (>100KB single line) → still classify, but flag for Step 4 chunking
- Duplicate content: two files with different names but identical content → classify both as chat, dedup in Step 4

### Output

Counts per category, per source table/folder:
```
vbstyle_documents.markdown_files: 500 chat, 200 doc, 50 other
vb_shared.chat_ingestions:        0 chat, 300 doc, 10 other
Total: 500 chat, 500 doc, 60 other
```

Also output date range per source:
```
vbstyle_documents.markdown_files: 2023-06-01 to 2024-12-15
disk /Users/wws/chats:              2024-01-01 to 2025-06-22
```

Store classification results in a temp table `_pipeline_classification` or a JSON file `./pipeline_classification.json` for Step 2 to use.
Classification results include: filename, source location, category, file size, created_at, modified_at.

### Cleanup

- Temp classification table/file is deleted at the end of the pipeline (Step 8)
- If pipeline crashes, temp file remains for debugging — cleaned on next run start

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| RAM available > 2GB | `dom_system` monitor | Wait 10s for GC → if still low, reduce sample size to 100 |
| Source table row count queryable | `SELECT COUNT(*)` works | If timeout → use `LIMIT 10000` sampling mode |
| Source table has content column | Check config `content_col` exists in `INFORMATION_SCHEMA` | Exit — fix config |
| Disk folder has `.md`/`.json` files | `os.walk()` finds at least 1 | Exit — nothing to classify |
| Temp file location writable | `os.access(dirname, os.W_OK)` | Fall back to in-memory classification |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| Source table has no `filename` column | A: use config `filename_col` → B: use `id` as filename → C: skip table, log |
| Source table has no `content` column | A: use config `content_col` → B: skip table, log → C: prompt user for correct column name |
| Row content is NULL or empty | A: count as `other` → B: skip row → C: continue (non-blocking) |
| Row content is binary (BLOB) | A: skip, log → B: continue (non-blocking) |
| JSON parse fails during classification | A: classify as `other` → B: continue |
| File read permission denied (disk) | A: skip, log → B: continue → C: prompt user to fix permissions |
| Sampling fails (table too large, query timeout) | A: `LIMIT 10000` → B: `LIMIT 1000` → C: prompt user to specify `WHERE` filter |
| All files classified as `other` | A: log warning → B: show sample of filenames for user review → C: exit |
| Temp file write fails | A: retry once → B: continue in-memory → C: log warning (Step 2 handles both modes) |

---

## Step 2: Filter to Chat Files Only

From Step 1's classification, keep only files classified as **chat**.

- Input: classification results from Step 1
- Filter: keep only items where category = `chat`
- Output: list of confirmed chat files with their source location, size, created_at, modified_at
- **Sort by modified_at descending** — newest chats first
  - Newer chats are more likely to be relevant and reflect current work
  - Older chats may contain outdated information
  - Processing newest first means if pipeline crashes, the most relevant data is already imported
- This is a filter step — no re-reading or re-parsing needed
- If no chat files found → log and exit

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| Classification results exist | Temp file or in-memory list present | Re-run Step 1 |
| At least 1 chat file in results | `count(category == 'chat') > 0` | Exit — nothing to import |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| Classification temp file missing | A: check in-memory results → B: re-run Step 1 → C: prompt user |
| Classification temp file corrupted | A: delete + re-run Step 1 → B: prompt user |
| All files filtered out (zero chat) | A: log warning → B: show classification summary for review → C: exit |
| Sort by date fails (missing dates) | A: fall back to filename sort → B: fall back to unsorted → C: continue (order is optimization) |

---

## Step 3: Exclude Chat_History

Remove any files that belong to the `Chat_History` table.

- `Chat_History` is the destination table, not a source
- Prevents self-import loops (importing previously imported chats)
- If `Chat_History` doesn't exist yet (first run) → skip this step
- Check: compare source table/folder name against `Chat_History`
- If source is MySQL: exclude any rows where `source_db = 'Chat_History'`

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| `Chat_History.sessions` table exists | `SHOW TABLES` | Skip exclusion (first run) |
| Source list is not empty | `len(chat_files) > 0` | Exit |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| `Chat_History` table doesn't exist | A: skip exclusion (first run) → B: continue |
| `Chat_History` query fails | A: retry once → B: continue without exclusion (idempotency in Step 4 catches duplicates) → C: prompt user |
| All files are from `Chat_History` | A: log warning → B: exit — nothing new to import |

---

## Step 4: Parse and Import by Format

Parse each chat file based on its format. Both paths normalize into the same `Chat_History` schema (sessions, messages, prompts).

### .md Path

- **Parser:** markdown parser reads content line by line
- **Session name:** derived from filename (strip `.md` extension), or first `# Heading` if present, or first 50 chars of first user message as fallback
- **Session boundary:** each `.md` file = one session (unless file contains multiple conversations separated by clear delimiters)
- **Message extraction:**
  - Detect role labels: `**User:**`, `## User`, `> User:`, `Human:`, etc.
  - Content is everything between one role label and the next
  - `role` = `user`, `assistant`, or `system`
  - `sequence` = incrementing counter (0, 1, 2...)
  - **Code block handling:** ignore role labels inside ` ``` ` fenced code blocks — track fence state, only detect role labels outside code fences
  - **Nested quote handling:** ignore role labels inside `> ` block quotes that are part of an assistant response — track quote depth, only detect role labels at depth 0
  - **Message ordering validation:** if two consecutive messages have the same role (e.g. user, user), log as `unusual_ordering` but still import — some chats legitimately have consecutive same-role messages
- **Prompt extraction:**
  - First user message = `initial` prompt
  - Subsequent user messages = `follow_up` prompts
  - System messages at the start = `system` prompt
- **Metadata:** extract timestamps, model names if present in the text
  - Timestamp patterns: `[2024-01-15 10:30:00]`, `2024-01-15T10:30:00Z`, `Jan 15, 2024`
  - Model patterns: `model: gpt-4`, `Model: claude-3-opus`, `using GPT-4`
  - Store in a `metadata` JSON column on sessions table if available
- **Encoding:** `utf-8` with `errors='replace'`
- **Multi-session files:** if a file contains multiple conversations separated by `---` or similar, split into multiple sessions
- **Large files:** if file >10MB, stream line by line instead of loading entire file into memory

### .json Path

- **Parser:** `json.loads()` the content
- **Session name:** from JSON `title` field, or `filename` field, or first user message (first 50 chars) as fallback
- **Session boundary:** each `.json` file = one session (unless file contains an array of conversations)
- **Message extraction:**
  - ChatGPT export: traverse `mapping` object, extract nodes with `role` and `content`
  - Simple format: iterate `messages` array, extract `role` and `content`
  - `role` = `user`, `assistant`, or `system`
  - `sequence` = incrementing counter (0, 1, 2...)
  - **Attachments:** skip images, files, and non-text content — log as skipped attachment
- **Prompt extraction:**
  - First user message = `initial` prompt
  - Subsequent user messages = `follow_up` prompts
  - System messages at the start = `system` prompt
- **Metadata:** extract from JSON fields (`model`, `created_at`, `title`)
  - Store in a `metadata` JSON column on sessions table if available
- **Malformed JSON:** log error, skip file, continue
- **Large files:** if JSON >50MB, use `ijson` streaming parser instead of `json.loads()`

### Normalization

Both paths produce the same output:
- Insert into `sessions` table → get `session_id`
- Insert messages into `messages` table with `session_id` FK
- Insert prompts into `prompts` table with `session_id` FK
- Set `source_db`, `source_table`, `source_format` on session row

### Import Rules

- Check for existing session before inserting (idempotency)
- Use source + session_name as uniqueness key
  - `source` = `source_db + source_table` (both, not just one) — prevents collision when two tables have same session name
- If session already exists → skip, log as duplicate
- **Content hash dedup:** calculate SHA-256 of all message content per session. If hash matches an existing session → skip as duplicate content, log both session names
- **Content sanitization:** remove null bytes, normalize line endings to `\n`, strip invalid UTF-8 sequences before insert
- **Date priority:** process sessions sorted by `source_modified_at` descending (newest first) — most relevant chats imported first
- **Source file locking (disk only):** if file is being modified while we read it (detected via `st_mtime` change between open and read), skip and log as `file_changing` — retry on next run
- Insert in batches (e.g. 500 messages per transaction)
- On insert failure → log error, rollback batch, continue with next

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| MySQL connection alive | `SELECT 1` | Reconnect before starting |
| RAM available > 1GB | `dom_system` | Wait 10s → reduce batch size to 100 |
| MySQL `max_allowed_packet` >= 4MB | `SHOW VARIABLES` | Set batch size to 100 (smaller batches) |
| Destination tables exist | `SHOW TABLES` | Run Step 0.5 first |
| File is not being modified (disk) | `st_mtime` stable for 2s | Skip file, log as `file_changing` |
| File size < `max_threshold` from Step 1 | Compare against stored threshold | Log as oversized, flag for review |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| `.md` file has no role labels | A: try alternate patterns (`Human:`, `User :`) → B: log as `no_messages_found`, skip → C: continue |
| `.md` file has only code blocks | A: check for role labels outside fences → B: log as `code_only`, skip → C: continue |
| `.md` role labels but no content between | A: import with empty content → B: log as `empty_message` → C: continue |
| `.json` valid but not chat format | A: try alternate JSON structures → B: log as `not_chat_json`, skip → C: continue |
| `.json` ChatGPT `mapping` empty | A: try `messages` array instead → B: log as `empty_mapping`, skip → C: continue |
| `.json` content is array (tool calls) | A: extract text parts → B: skip non-text, log as `partial_content` → C: continue |
| Session name extraction fails | A: try filename → B: try `unnamed_session_<row_id>` → C: continue |
| Batch insert — packet too large | A: halve batch (500→250) → B: halve again (250→125) → C: insert one by one |
| Batch insert — duplicate key | A: skip duplicate → B: continue with rest of batch → C: log |
| Batch insert — connection lost | A: reconnect + retry → B: wait 5s + retry → C: prompt user to check MySQL |
| Content hash matches existing | A: skip, log both names → B: continue |
| File being modified (disk) | A: skip, log → B: retry on next run → C: continue |
| Multi-session split gives 50+ sessions | A: import first 10 → B: flag rest for manual review → C: prompt user |

---

## Step 5: Embed All Messages into Qdrant

Embed every imported message into Qdrant for vector search.

### Setup

- Connect to Qdrant at `localhost:6333`
- Collection name: `chat_messages`
- Vector dimensions: depends on model (e.g. 384 for `all-MiniLM-L6-v2`)
- Distance metric: `Cosine`
- HNSW index config: `m=16`, `ef_construct=100` (default, good for 100k+ points)
- Optimizers config: `default_segment_number=4` (parallel indexing)
- On-disk: enabled for large collections (>100k points)
- **Payload indexes:** create index on `session_id` payload field — enables fast session-level vector searches
- Create collection if it doesn't exist
- If collection exists with wrong dimensions → log error, ask user to recreate
- **Model warmup:** run a dummy embedding before first batch to load model into memory — first batch ETA is calculated after warmup, not before

### Embedding

- Model: SentenceTransformer or MLX (from config)
- Embed `content` field of each message
- Store vector in Qdrant with payload:
  - `message_id` = MySQL `messages.row_id`
  - `session_id` = MySQL `sessions.row_id`
  - `role` = message role
  - `source` = source database
- Point ID = MySQL `messages.row_id` (direct mapping)

### Batch Processing

- Batch size: from config (e.g. 500)
- **Rate limiting:** if GPU/CPU usage > 90% (via dom_system), pause 2 seconds between batches
- For each batch:
  - Read messages from MySQL where `embedded = FALSE`
  - Generate embeddings
  - Upsert into Qdrant
  - Update MySQL: set `embedded = TRUE` for those messages
- This makes embedding resumable — if it crashes, only re-embed un-embedded messages

### Token Limits

- Some messages may be too long for the embedding model
- `all-MiniLM-L6-v2`: max 256 tokens (~500 words)
- Strategy: if message > token limit, truncate to max tokens and log as truncated
- Alternative: chunk long messages into multiple vectors with same `message_id` but different chunk index
- Default: truncate, log, continue

### Empty Messages

- Skip embedding for empty or whitespace-only messages
- Set `embedded = TRUE` anyway (nothing to embed)
- Log as skipped empty

### Failure Handling

- If Qdrant not running → log error, stop embedding, continue with rest of pipeline
- If embedding fails for a message → log error, skip, continue
- If model not available → log error, skip entire embedding step

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| Qdrant running | `GET /collections` | Skip embedding, continue pipeline, do later |
| Qdrant has enough disk for vectors | Check Qdrant disk usage | Warn — may fail mid-batch |
| GPU available and has >1GB free | `dom_system` GPU monitor | Fall back to CPU embedding |
| GPU not already at 100% | `dom_system` | Wait 5s → if still full, use CPU |
| RAM available > 2GB (model loading) | `dom_system` | Wait 10s for GC → if still low, reduce batch to 50 |
| Embedding model installed | `import` test | Skip embedding, continue |
| Model matches collection dimensions | Compare model dim vs Qdrant collection dim | Exit — dimension mismatch, recreate collection |
| Messages to embed count > 0 | `SELECT COUNT(*) WHERE embedded = FALSE` | Skip step, log `already_done` |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| Qdrant connection refused | A: retry 3× (1s, 5s, 15s) → B: skip embedding, continue pipeline → C: prompt user to start Qdrant |
| Qdrant collection creation fails | A: retry once → B: skip embedding, continue → C: prompt user |
| Qdrant upsert fails (batch) | A: retry batch → B: split in half, retry each → C: insert one by one, log failures |
| Qdrant upsert fails (single point) | A: retry once → B: skip point, log `message_id` → C: continue |
| Embedding model OOM | A: reduce batch to 50 → B: reduce to 10 → C: fall back to CPU, if still OOM skip step |
| Embedding model not installed | A: try `pip install` → B: skip embedding, continue → C: prompt user |
| Message content is only whitespace | A: skip embedding, set `embedded = TRUE` → B: log as `empty` → C: continue |
| Message content is only code | A: still embed (code is searchable) → B: continue |
| `embedded = TRUE` update fails | A: retry once → B: log — will re-embed on next run (idempotent) → C: continue |
| All messages already embedded | A: log `already_done` → B: skip step → C: continue |

---

## Step 6: Build Knowledge Graph (OPTIONAL)

> **WARNING:** Lessons learned says "graph from markdown is just a straight line, not a real graph" and "we dropped the graph, then I added it back, then dropped it again."
>
> This step is **optional and disabled by default**. Enable with `--with-graph` flag.
> Only useful for JSON sources with structured metadata. For markdown sources, produces minimal results.

Extract concepts and link them to sessions.

### Concept Extraction

- Method: keyword extraction from message content
- Tools: TF-IDF, keyword extraction, or simple frequency analysis
- A concept = a significant word or phrase that appears across multiple sessions
- Filter: ignore common words (stopwords), keep terms that appear in 2+ sessions

### Tables

- `concepts` — unique concepts with frequency
- `concept_links` — relationships between concepts (co-occurrence in same session)
- `session_concepts` — links sessions to concepts found in them

### Process

- For each session: extract keywords from all messages
- Insert unique keywords into `concepts` table
- If two concepts appear in the same session → create `concept_links` row
- Insert session-concept mappings into `session_concepts`

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| `--with-graph` flag set | CLI arg check | Skip step entirely |
| Sessions exist in `Chat_History` | `SELECT COUNT(*) FROM sessions` | Skip — nothing to extract from |
| RAM available > 1GB | `dom_system` | Reduce sessions per batch |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| `--with-graph` not set | A: skip step → B: continue to Step 7 |
| Concept extraction finds zero concepts | A: try lower frequency threshold → B: log warning, skip graph → C: continue |
| `concepts` table creation fails | A: retry once → B: skip step, continue → C: prompt user |
| Concept extraction too slow (>5 min/session) | A: skip remaining sessions → B: continue with partial results → C: prompt user to reduce scope |
| All concepts are stopwords | A: try expanded stopword list → B: log warning, skip graph → C: continue |

---

## Step 7: Verify Imported Chats

Cross-check imported data against other MySQL tables.

### What to Compare

- Compare session names in `Chat_History.sessions` against session names in source tables:
  - `vbstyle_documents.markdown_files` — by `filename` column
  - `vb_shared.chat_ingestions` — by `session_name` column
  - Any other source table specified in config
- Compare message counts: source file message count vs `Chat_History.messages` count per session
- Compare content hashes: hash of source content vs hash of imported content
- **Cross-source note:** if importing from disk, can only compare against MySQL tables if MySQL is also configured. If MySQL not available → skip cross-source verification, log as skipped
- **Orphaned embeddings:** check Qdrant for point IDs that have no matching `messages.row_id` in MySQL. Log orphans for cleanup

### What Constitutes a Match

- Same session name (case-insensitive) in source and destination
- Same message count
- Content hash matches (or close match for encoding differences)

### Actions

- Matched sessions → prefix session name with `Processed_` in `Chat_History`
- Mismatches → log with details (which session, what differs)
- Missing sessions → log as "imported but not found in source" (possible deletion in source)
- Extra sessions in source → log as "found in source but not imported" (possible import failure)

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| `Chat_History.sessions` has rows | `SELECT COUNT(*) > 0` | Skip verification — nothing to verify |
| Source tables still accessible | Connection test | Skip verification, log |
| Qdrant running (for orphan check) | `GET /collections` | Skip orphan check, log |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| Source table not accessible | A: retry connection → B: skip verification, log → C: prompt user |
| Zero session name matches | A: try case-insensitive match → B: try partial match → C: log as `no_matches`, continue |
| Content hash comparison fails | A: try re-hash with different algorithm → B: skip hash, use name + count only → C: continue |
| Qdrant orphan check fails | A: retry Qdrant connection → B: skip orphan check, log → C: continue |
| Orphans found in Qdrant | A: log count + IDs → B: do NOT auto-delete → C: prompt user to confirm cleanup |
| `Processed_` prefix already exists | A: skip prefixing → B: log as `already_processed` → C: continue |

---

## Step 8: Final Validation

Check session names for duplicates and errors before marking import complete.

### Duplicate Detection

- Find sessions with identical names in `Chat_History.sessions`
- Options: rename with suffix (`_2`, `_3`), merge, or flag for manual review
- Default: rename with suffix, log original and new name

### Malformed Session Names

- Empty session name → generate from first message (first 50 chars)
- Session name with special characters → sanitize (remove control chars)
- Session name too long (>255 chars) → truncate
- Session name is just a file path → extract filename only

### Final Checks

- All sessions have at least 1 message
- All messages have a valid `session_id` FK
- All `embedded` flags are TRUE (or logged as failed)
- No orphaned prompts (prompts with no matching session)
- No orphaned embeddings (Qdrant points with no MySQL row — clean up or log)
- No duplicate content hashes across sessions
- **Date coverage report:** show oldest and newest session by `source_modified_at`, identify gaps in timeline
- Log all issues for review

### Completion

- Write summary report: total sessions, messages, prompts imported
- Write error report: all failures, skips, duplicates
- Mark pipeline as complete in log
- Delete temp classification table/file from Step 1
- Write `pipeline_state` status as `complete`

### Dry-Run Mode

- `--dry-run` flag: run all steps but skip actual DB inserts and Qdrant upserts
- Output: what would be imported, classification results, estimated counts
- Useful for testing before real import

### Prevention Checks (run before step starts)

| Check | Condition | If check fails |
|-------|-----------|----------------|
| All previous steps completed | `pipeline_state.current_step >= 7` | Go back to correct step |
| No active transactions | MySQL `SHOW PROCESSLIST` | Wait for transactions to finish |
| Log file writable | `os.access(log_path, os.W_OK)` | Print to stdout instead |

### Failure Branches

| What fails | Escalation chain (try A → B → C → prompt) |
|------------|------------------------------------------|
| Duplicate session names found | A: auto-rename with `_2`, `_3` → B: log original + new → C: continue |
| Duplicate content hashes found | A: keep first, mark rest `duplicate_content` → B: log → C: continue |
| Orphaned messages (no session) | A: delete orphans → B: log count → C: continue |
| Orphaned prompts (no session) | A: delete orphans → B: log count → C: continue |
| Orphaned embeddings (Qdrant) | A: log count + IDs → B: do NOT auto-delete → C: prompt user to confirm cleanup |
| Temp file deletion fails | A: retry once → B: log warning, continue → C: will clean on next run |
| `pipeline_state` update fails | A: retry once → B: log warning, continue → C: state is for resume only, not critical |
| Summary report write fails | A: retry with different path → B: print to stdout → C: continue |
| Date coverage shows gap >6 months | A: log as `timeline_gap` → B: flag for user review → C: continue |

---

# Operational Requirements

## Error Handling

When a file fails to parse or an insert fails, log it and continue with the next file. Do not stop the entire pipeline.

- Log: file/row ID, error type, error message, timestamp
- Categories: `parse_error`, `insert_error`, `embedding_error`, `connection_error`
- On `connection_error`: retry 3 times with backoff (1s, 5s, 15s), then skip
- **MySQL connection drop:** detect via `mysql.connector.errors.OperationalError`, reconnect automatically, retry last batch
- **MySQL `max_allowed_packet`:** if batch insert fails with packet too large, halve batch size and retry automatically
- **SQL injection prevention:** all queries use parameterized inputs (`%s` placeholders), never string concatenation
- **Lock file:** create `.pipeline.lock` at start; if it exists, refuse to start (prevents concurrent runs); delete on completion or crash

## Error Knowledge Base (Self-Healing Loop)

Every error that occurs is saved. Next run, pre-flight checks query the knowledge base. If same conditions are detected, the known fix is applied proactively — the error never happens again.

### How It Works

```
Run 1: Error X occurs → escalation tries A (fail), B (success)
  → Save to error_knowledge: {conditions, error, fix_attempted=A, fix_result=failed, fix_attempted=B, fix_result=success}
  → Next pre-flight adds check for X's conditions

Run 2: Pre-flight detects same conditions as error X
  → Query error_knowledge → "we've seen this, fix B works"
  → Apply fix B proactively before step runs
  → Error X never happens

Run 3: New error Y occurs → save → try escalations → find fix C works
  → Now error Y is also in knowledge base
  → Pipeline gets smarter with every run
```

### `error_knowledge` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT AUTO_INCREMENT | Primary key |
| `step` | VARCHAR(20) | Which step (0-8) |
| `error_type` | VARCHAR(100) | Category: `connection`, `parse`, `insert`, `embedding`, etc. |
| `error_message` | TEXT | Exact error text |
| `conditions` | JSON | System state when error occurred (RAM, GPU, batch_size, table, file) |
| `fix_attempted` | JSON | Array of fixes tried: [{"fix": "A", "result": "failed"}, {"fix": "B", "result": "success"}] |
| `successful_fix` | VARCHAR(100) | Which fix worked (A, B, C, or `none` — user intervened) |
| `success_count` | INT DEFAULT 0 | Times this fix succeeded (increments on each successful prevention) |
| `failure_count` | INT DEFAULT 0 | Times this fix failed (increments when fix doesn't work) |
| `confidence` | FLOAT DEFAULT 0.5 | `success_count / (success_count + failure_count)` — ranked 0.0 to 1.0 |
| `occurrence_count` | INT | How many times this error has occurred (increments on repeat) |
| `first_seen` | TIMESTAMP | First time this error occurred |
| `last_seen` | TIMESTAMP | Most recent occurrence |
| `auto_resolved` | BOOLEAN | TRUE if a fix was found automatically, FALSE if user had to intervene |
| `prevention_added` | BOOLEAN | TRUE if pre-flight check has been added for this error |

### Confidence Scoring (from EFL principle)

Inspired by `efl_ram_ai.py` `learned_fixes` table — each fix has a confidence score:

- **New error, fix works** → `success_count = 1`, `failure_count = 0`, `confidence = 1.0`
- **Same error, fix works again** → `success_count = 2`, `confidence = 1.0`
- **Same error, fix fails** → `failure_count = 1`, `confidence = success_count / (success_count + failure_count)`
- **Pre-flight applies fix** → if fix works, `success_count += 1`; if fix doesn't work, `failure_count += 1`
- **Confidence drops below 0.3** → demote fix: stop applying proactively, log for review
- **Confidence = 1.0 after 10+ successes** → promote to `trusted` — always apply without checking conditions
- **Multiple fixes for same error** → pre-flight picks the one with highest confidence first
- **User-provided fix** → starts at `confidence = 0.8` (high trust but not 1.0 — needs verification)

### Error Lifecycle

1. **Error occurs** during any step
2. **Save error** to `error_knowledge` table with conditions + fix attempts
3. **Escalation chain runs** (try A → B → C → prompt user)
4. **Verify fix** — run a test to confirm the fix actually worked (see Fix Verification below)
5. **Record result** — did the fix survive the test?
6. **Update confidence** — `success_count` or `failure_count` based on test result
7. **Mark prevention** — if fix survived, add a pre-flight check for next run
8. **Next run** — pre-flight queries `error_knowledge` for current step's known errors
9. **If conditions match** a known error → apply the highest-confidence surviving fix proactively
10. **Verify prevention** — run the same test to confirm the fix still works
11. **Error never happens again** — the pipeline learned from it AND verified the learning

### Fix Verification (Closing the Loop)

After every fix is applied, the pipeline runs a **verification test** to confirm the fix actually worked. A fix is only "successful" if it passes the test. This is what closes the loop.

#### How Each Step Verifies Fixes

| Step | Fix applied | Verification test | Test passes if |
n|------|-------------|-------------------|----------------|
| Step 0 | Retry connection / switch source | `SELECT 1` or `os.path.exists()` | Connection returns result within 5s |
| Step 0.5 | Recreate table / add missing column | `SHOW COLUMNS FROM <table>` | All expected columns exist with correct types |
| Step 1 | Skip table / use fallback column / reduce sample | `SELECT <content_col> FROM <table> LIMIT 1` | Query returns at least 1 row with content |
| Step 2 | Re-run Step 1 / fall back to filename sort | Check sorted list has `len > 0` and dates are valid | List is non-empty, sort order is correct |
| Step 3 | Skip exclusion / continue without | Check no `source_db = 'Chat_History'` in filter list | No self-import rows in remaining list |
| Step 4 | Halve batch / skip duplicate / reconnect | Re-run the failed batch insert | Insert succeeds with no error, row count matches |
| Step 5 | Reduce batch / fall back to CPU / skip point | Re-run embedding for that batch | Qdrant upsert returns success, `embedded = TRUE` set |
| Step 6 | Lower threshold / skip slow sessions | Check `concepts` table has rows | At least 1 concept extracted and inserted |
| Step 7 | Case-insensitive match / skip hash check | Re-run comparison with new method | At least 1 session match found |
| Step 8 | Auto-rename / delete orphans / print to stdout | Re-run duplicate check / orphan check | Zero duplicates or zero orphans remaining |

#### Test Execution Rules

1. **Every fix gets tested** — no fix is marked "successful" without passing a test
2. **Test is step-specific** — each step has its own verification query (table above)
3. **Test has a timeout** — 30 seconds max. If test hangs → fix failed
4. **Test result is saved** — stored in `fix_attempted` JSON: `{"fix": "A", "result": "failed", "test": "select_1", "test_result": "timeout"}`
5. **Test is idempotent** — running the test multiple times gives the same result
6. **Test runs in isolation** — test query is separate from the main pipeline flow

#### Survival Loop (Promotion / Demotion)

```
Fix applied → Verification test runs
  ├── TEST PASSES → fix SURVIVED
  │     → success_count += 1
  │     → confidence = success_count / (success_count + failure_count)
  │     → if confidence >= 0.8 AND success_count >= 5 → PROMOTE to "verified"
  │     → if confidence = 1.0 AND success_count >= 10 → PROMOTE to "trusted"
  │
  └── TEST FAILS → fix DIED
        → failure_count += 1
        → confidence = success_count / (success_count + failure_count)
        → if confidence < 0.3 → DEMOTE to "disabled" (stop applying)
        → try next fix in escalation chain (B, then C)
        → if all fixes die → prompt user
```

#### Fix Status Levels

| Status | Confidence | Success count | Behavior |
|--------|------------|---------------|----------|
| `new` | 0.5 | 0 | Just saved, not yet tested |
| `unverified` | 0.5 | < 5 | Applied with caution, tested each time |
| `verified` | >= 0.8 | >= 5 | Applied confidently, still tested |
| `trusted` | = 1.0 | >= 10 | Applied without condition check, tested periodically |
| `disabled` | < 0.3 | any | Not applied, logged for review |
| `user_trusted` | 0.8 | any | User-provided fix, applied with high trust |

#### Periodic Re-Testing (Trusted Fixes)

- `trusted` fixes are re-tested every 10 runs (not every run — they've earned trust)
- If a `trusted` fix fails re-test → demote to `verified`, investigate
- If a `trusted` fix fails 2 re-tests in a row → demote to `disabled`
- This prevents stale fixes from being trusted forever when source data changes

#### The Closed Loop

```
┌─────────────────────────────────────────────────────────┐
│                    PIPELINE RUN                          │
│                                                          │
│  1. Pre-flight checks (static + dynamic)                │
│       │                                                  │
│       ▼                                                  │
│  2. Query error_knowledge (sorted by confidence DESC)   │
│       │                                                  │
│       ▼                                                  │
│  3. Conditions match known error?                        │
│       │ YES                    │ NO                      │
│       ▼                        ▼                         │
│  4. Apply highest-confidence   4. Run step normally     │
│     fix proactively                │                     │
│       │                            ▼                     │
│       ▼                       5. Error occurs?           │
│  5. RUN VERIFICATION TEST           │ YES                │
│       │                              ▼                   │
│       ▼                       6. Save error              │
│  6. Test passes?                    │                    │
│       │ YES      │ NO               ▼                    │
│       ▼          ▼               7. Escalation chain     │
│  7. SURVIVED   7. DIED              (A → B → C)          │
│       │          │                    │                  │
│       ▼          ▼                    ▼                  │
│  8. success++  8. failure++      8. Apply fix + TEST     │
│     confidence   confidence           │                  │
│     recalc       recalc               ▼                  │
│       │          │               9. Test passes?         │
│       ▼          ▼                   │ YES    │ NO       │
│  9. PROMOTE?  9. DEMOTE?              ▼       ▼         │
│     (>=0.8)     (<0.3)           10. SURVIVED  DIED      │
│       │          │                   │         │         │
│       ▼          ▼                   ▼         ▼         │
│  10. Run step  10. Try next     11. success++ failure++ │
│     normally     fix or prompt       confidence  recalc  │
│                         │              │         │       │
│                         ▼              ▼         ▼       │
│                   ┌──────────────────────────────────────┘
│                   │
│                   ▼
│              NEXT RUN (loop repeats)
│                   │
└───────────────────┘
```

Solutions that **survive** verification get promoted. Solutions that **die** get demoted. The loop is closed.

### Pre-Flight Integration

Before each step, the pre-flight checker does TWO things:

1. **Static checks** — the Prevention Checks tables already defined per step (RAM, disk, connection, etc.)
2. **Dynamic checks** — query `error_knowledge` table, **sorted by confidence descending**:
   ```sql
   SELECT * FROM error_knowledge
   WHERE step = <current_step>
     AND auto_resolved = TRUE
     AND prevention_added = TRUE
     AND confidence >= 0.3
   ORDER BY confidence DESC
   ```
   For each result:
   - If `confidence = 1.0` and `success_count >= 10` → **trusted fix**: apply without checking conditions
   - Otherwise: check if current conditions match the saved `conditions` JSON
   - If match → apply `successful_fix` proactively (highest confidence first)
   - Log as `prevention_applied` (not as error — error was prevented)
   - If fix works → `success_count += 1`, recalculate confidence
   - If fix doesn't work → `failure_count += 1`, recalculate confidence, try next fix in list

### Error Deduplication

- Before saving a new error, check if same `error_type` + `conditions` already exists
- If exists → increment `occurrence_count`, update `last_seen`
- If new → insert new row
- This prevents the table from growing unbounded with repeated errors
- If `occurrence_count > 10` for same error → escalate to user: "this keeps happening, manual intervention needed"

### User-Provided Fixes

- If escalation chain exhausts (A, B, C all fail) → prompt user
- User provides a fix → save as `successful_fix = 'user_manual'`
- Next run → pre-flight detects same conditions → applies user's fix automatically
- The pipeline learns from user interventions too

### Error Knowledge Report

At end of pipeline (Step 8), output an error knowledge summary:

```
Error Knowledge Base Summary:
  Total unique errors seen: 23
  Auto-resolved: 18 (78%)
  User-resolved: 5 (22%)
  Prevention checks added: 18
  Errors prevented this run: 15 (would have failed, pre-flight caught them)
  Most frequent error: max_allowed_packet (occurred 8 times, now prevented)
  New errors this run: 2 (both auto-resolved)

  Top trusted fixes (confidence = 1.0, 10+ successes):
    [Step 4] packet_too_large → halve batch size (15 successes)
    [Step 5] qdrant_refused → retry 3× then skip (12 successes)
    [Step 4] duplicate_key → skip duplicate (11 successes)

  Demoted fixes (confidence < 0.3, disabled):
    [Step 1] sampling_timeout → LIMIT 10000 (2 successes, 8 failures, confidence = 0.20)

  Average confidence across all fixes: 0.82
```

### Example Walkthrough

**Run 1:**
- Step 4: batch insert fails with `max_allowed_packet` error
- Escalation: A (halve batch 500→250) → success
- Save: `{step: 4, error_type: 'packet_too_large', conditions: {batch_size: 500, message_avg_size: '8KB'}, successful_fix: 'A', success_count: 1, failure_count: 0, confidence: 1.0, auto_resolved: TRUE}`
- Mark `prevention_added = TRUE`

**Run 2:**
- Step 4 pre-flight: query `error_knowledge` for step 4, sorted by confidence DESC
- Find: `packet_too_large` with `confidence = 1.0`, `conditions.batch_size = 500`
- Current batch_size is 500 → conditions match
- Apply fix A proactively: set batch_size = 250 before starting
- Log: `prevention_applied: reduced batch_size to 250 (known error: packet_too_large, confidence: 1.0)`
- Step 4 runs with batch_size 250 → no error
- Update: `success_count = 2`, `confidence = 1.0`

**Run 3:**
- New table added to source with much larger messages (50KB avg)
- Step 4: batch insert fails again with `packet_too_large` at batch_size 250
- Pre-flight had applied fix A (batch_size 250) but it wasn't enough this time
- Escalation: A (halve 250→125) → success
- Update existing: `failure_count = 1`, `confidence = 2/3 = 0.67`
- Save new row: `{conditions: {batch_size: 250, message_avg_size: '50KB'}, successful_fix: 'A', confidence: 1.0}`
- Now knowledge base has TWO versions of this error for different conditions

**Run 10:**
- `packet_too_large` fix A has `success_count = 12`, `failure_count = 1`, `confidence = 0.92`
- Not yet `trusted` (needs `confidence = 1.0` and `success_count >= 10` with zero failures)
- But still ranked highest → pre-flight applies it first

**Run 15:**
- After 3 more successes with no failures: `success_count = 15`, `failure_count = 1`, `confidence = 0.94`
- Fix B (halve again) has `success_count = 5`, `confidence = 1.0`
- Pre-flight now picks fix B first (higher confidence)
- System self-corrected: the better fix rose to the top

## Batching

Process in chunks to avoid memory issues.

- DB inserts: 500 messages per transaction
- Embeddings: 500 messages per batch
- Qdrant upserts: 500 points per batch
- If memory pressure detected (via `dom_system`): reduce batch size dynamically

## Logging

Track what was imported, what was skipped, what failed.

- Log file: path from config (e.g. `./pipeline.log`)
- Levels: `INFO` (progress), `WARNING` (skips), `ERROR` (failures)
- Every action produces a log entry
- Log format: `[timestamp] [LEVEL] [step] message`
- **Log rotation:** max 10MB per file, keep 5 rotated files (`pipeline.log.1`, `.log.2`, etc.)
- **Log flush:** flush after every write — if pipeline crashes, log is complete up to crash point

## Idempotency

If the pipeline runs twice, do not duplicate data.

- Check for existing session before inserting (source + session_name as key)
- Check for existing message before inserting (session_id + sequence as key)
- Check for existing embedding before upserting (point ID = row_id, upsert is idempotent)
- Re-running should produce zero new rows if nothing changed

## Resume

If the pipeline crashes mid-import, pick up from where it stopped.

- Resume state stored in a `pipeline_state` table or file:
  - `current_step` — which step we're on (0-8)
  - `last_processed_id` — last source row/file ID processed
  - `batch_number` — current batch number
  - `started_at` — when pipeline started
  - `updated_at` — last update time
- On restart: read state, skip completed steps, resume from last processed ID

## Verification

After import is complete, count matches between source and destination.

- Source count vs destination count (sessions, messages, prompts)
- Embedding count vs message count
- Knowledge graph count vs session count
- Log any discrepancies

## Rollback

If something goes wrong mid-import, undo partial work.

- Transaction-level: each batch is a transaction, failed batch rolls back automatically
- Session-level: if a session fails to import, delete any partial rows for that session
- Full rollback: `DELETE FROM sessions WHERE status = 'imported' AND created_at > <pipeline_start>` — removes everything from this run

## Progress Reporting

Show how far along the pipeline is.

- Format: `[Step 4/8] Processing batch 15/284 — 7500/142000 messages — 5.3%`
- Update: every batch completion
- Output: stdout and log file
- ETA: calculate based on average batch time

## dom_system Import

`dom_system` must be imported. It manages CPU, RAM, GPU, disk space as a thread that handles all hardware resources. Processing 142k messages with embeddings takes real memory and compute — batching and resource management are constraints, not nice-to-haves.

- Monitor: RAM usage, GPU memory, disk space, CPU load
- Action: if RAM > 80%, pause pipeline and wait for GC
- Action: if GPU memory > 90%, reduce embedding batch size
- Action: if disk < 1GB free, stop pipeline and alert

## dom_db Import

`dom_db` must be imported. It is the DOM database manager that manages all database operations: queries, connections, transactions. Handles the database domain for the pipeline.

- Connection pooling
- Transaction management (begin, commit, rollback)
- Query execution with error handling
- Batch insert optimization

## Kernel Import

`Kernel` must be imported. It combines core units into one: `Dom_Main`, `Dom_BCL`, `Dom_AST`, `Dom_Report`, `Dom_DB`, `Dom_System`, `Dom_IO`, `Dom_Network`, `Dom_Rules`, `Dom_State`, `Dom_Error`, `Dom_Orchestrator`. The foundation everything builds on.

---

# Search Interface

## CLI

Basic command-line search of chat history.

- Query by keyword: `python search.py --keyword "vector database"`
- Query by session name: `python search.py --session "Chat about BCL"`
- Query by date range: `python search.py --from 2024-01-01 --to 2024-12-31`
- Semantic search: `python search.py --semantic "how to parse brackets"`
- Output: matching sessions and messages in terminal

## API

Query endpoint for programmatic access.

- `GET /search?q=<query>&type=keyword|semantic` → JSON results
- `GET /sessions?limit=50&offset=0` → paginated session list
- `GET /sessions/<id>/messages` → all messages in a session
- Returns JSON with session metadata and matching messages

## GUI

Possible later, not a priority now.

---

# Lessons Learned

- **Discuss the work first before doing anything** — the biggest lesson
- **Ask what sources before starting work** — confirm MySQL only, not disk files
- **Confirm scope before acting** — user said MySQL, I went to disk files first
- **Implement only what was asked** — user wanted 3 tables, I kept adding more
- **Give short direct answers** — user asked simple questions, I gave long tables
- **Stick to decisions** — we dropped the graph, then I added it back, then dropped it again
- **Listen to the user** — when user said graph isn't needed, just remove it
- **Verify the right table** — user said `vbstyle_documents.markdown_files`, I checked `vb_shared.chat_ingestions` first
- **Confirm before prefixing** — I prefixed with `Processed_` based on the wrong table, had to undo it
- **Keep it simple** — 3 tables was the plan, I kept trying to make it 4-6 tables
- **Discuss what features are possible and not possible before implementing** — e.g. graph from markdown is just a straight line, not a real graph










