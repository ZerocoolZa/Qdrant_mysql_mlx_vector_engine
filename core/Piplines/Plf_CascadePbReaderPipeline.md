# Cascade PB Reader Pipeline — Encrypted Windsurf/Cascade Chat Search and Recall

> **Core thesis:** Cascade should never lose context due to language server restarts.
> Instead of relying on lossy checkpoints (~65% recall), Cascade can search the actual
> encrypted .pb chat files directly — decrypt in RAM, parse protobuf wire-format, query
> with SQLite, and return exact conversation history with 100% recall.

---

## Pipeline Overview

```
.pb files on disk → Scan → Decrypt (AES-256-GCM) → Parse (protobuf wire-format)
       ↓                                          ↓
  145 files found                          Trajectory + Steps
  (cascade, implicit, memories)            (user msgs, AI msgs, commands, checkpoints)
       ↓                                          ↓
  Load to RAM SQLite (:memory:)           Search / Read / Export
       ↓                                          ↓
  6 tables:                                CLI commands:
  trajectories                             scan, load-all, read, search, export, stats
  steps
  user_messages
  assistant_messages
  commands
  checkpoints
```

---

## State Machine (Formal Lifecycle)

```
SCAN → FOUND (.pb files enumerated)
  ↓
LOAD → DECRYPT (AES-256-GCM, key from language_server binary)
  ↓
PARSE (protobuf wire-format, no .proto schema needed)
  ↓
STORE (in-RAM SQLite :memory:, 6 tables)
  ↓
┌────────────┬────────────┬────────────┐
│            │            │            │
READ       SEARCH       EXPORT       STATS
(show       (query       (markdown    (RAM DB
conversation) all chats)  + index)     summary)
│            │            │            │
└────────────┴────────────┴────────────┘
                   ↓
              CLOSE (RAM DB destroyed, no plaintext on disk)
```

---

## Encryption Details

| Property | Value |
|---|---|
| Algorithm | AES-256-GCM |
| Key | 32-byte ASCII string (extracted from language_server_macos_arm binary) |
| Key source | Hardcoded in Windsurf/Codeium language server |
| File layout | `[12-byte nonce][ciphertext][16-byte GCM tag]` |
| Plaintext | Raw protobuf-encoded CortexTrajectory / ImplicitTrajectory / CortexMemory |
| Security | Decrypt only in RAM — no plaintext ever written to disk |

---

## Protobuf Wire-Format Parsing

No `.proto` schema is needed. The parser reads raw protobuf wire-format:

| Wire type | ID | Handling |
|---|---|---|
| VARINT | 0 | Read variable-length integer |
| 64BIT | 1 | Read 8 bytes |
| LENGTH | 2 | Read length-prefixed bytes |
| 32BIT | 5 | Read 4 bytes |
| GROUP_START | 3 | Recurse until GROUP_END |
| GROUP_END | 4 | End group |

### CortexTrajectoryStep variant fields (empirically discovered):

| Field number | Variant | Content |
|---|---|---|
| 19 | VARIANT_USER_INPUT | User message (prompt at field 2) |
| 20 | VARIANT_PLANNER_RESPONSE | AI response (user_facing at field 1, internal at field 3) |
| 28 | VARIANT_RUN_COMMAND | Shell command (cmd at field 23/25, output at field 24) |
| 30 | VARIANT_CHECKPOINT | Checkpoint (summary, intent, files, plan) |
| 15 | VARIANT_FILE_CONTEXT | File context |
| 37 | VARIANT_COMMAND_RESULT | Command result |

### CortexStepCheckpoint fields:

| Field | Content |
|---|---|
| 1 | checkpoint_index |
| 3 | included_step_indices (packed repeated) |
| 4 | user_intent |
| 5 | session_summary |
| 6 | code_change_summary |
| 7 | edited_files (repeated, file_path at field 1) |
| 8 | memory_summary |
| 9 | intent_only (bool) |
| 10 | conversation_title |
| 11 | included_step_index_start |
| 12 | included_step_index_end |
| 13 | plan_snapshot |

---

## In-RAM SQLite Schema (6 tables)

### trajectories
```sql
CREATE TABLE trajectories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_id TEXT,
    cascade_id TEXT,
    file_path TEXT UNIQUE,
    file_category TEXT,        -- cascade, implicit, memories
    trajectory_type INTEGER,
    source INTEGER,
    steps_count INTEGER,
    decrypted_size INTEGER,
    loaded_at TEXT DEFAULT (datetime('now'))
);
```

### steps
```sql
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_fk INTEGER,
    step_index INTEGER,
    step_type INTEGER,
    step_type_name TEXT,       -- UNSPECIFIED, PLAN_INPUT, MQUERY, CHECKPOINT, etc.
    status INTEGER,
    variant_field INTEGER,
    variant_data BLOB,
    FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
);
```

### user_messages
```sql
CREATE TABLE user_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_fk INTEGER,
    step_index INTEGER,
    prompt TEXT,
    FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
);
```

### assistant_messages
```sql
CREATE TABLE assistant_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_fk INTEGER,
    step_index INTEGER,
    user_facing TEXT,
    internal_planning TEXT,
    FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
);
```

### commands
```sql
CREATE TABLE commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_fk INTEGER,
    step_index INTEGER,
    command TEXT,
    output TEXT,
    FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
);
```

### checkpoints
```sql
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trajectory_fk INTEGER,
    step_index INTEGER,
    checkpoint_index INTEGER,
    conversation_title TEXT,
    user_intent TEXT,
    session_summary TEXT,
    code_change_summary TEXT,
    memory_summary TEXT,
    plan_snapshot TEXT,
    intent_only INTEGER,
    edited_files TEXT,
    FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id)
);
```

### Indexes:
- `idx_steps_traj` on steps(trajectory_fk)
- `idx_user_traj` on user_messages(trajectory_fk)
- `idx_asst_traj` on assistant_messages(trajectory_fk)
- `idx_cmd_traj` on commands(trajectory_fk)
- `idx_cp_traj` on checkpoints(trajectory_fk)

---

## CLI Commands

```bash
# Discovery
python3 chat_mover/pb_reader.py scan                    # list all .pb files found
python3 chat_mover/pb_reader.py stats                   # RAM DB statistics

# Loading
python3 chat_mover/pb_reader.py load <file.pb>          # load one file into RAM
python3 chat_mover/pb_reader.py load-all                # load all .pb files into RAM
python3 chat_mover/pb_reader.py list                    # list loaded trajectories

# Reading
python3 chat_mover/pb_reader.py read <file.pb>          # show full chat conversation
python3 chat_mover/pb_reader.py read <file.pb> --step 5 # show specific step

# Searching
python3 chat_mover/pb_reader.py search "query"          # search all loaded chats
python3 chat_mover/pb_reader.py search "query" --user   # search only user messages
python3 chat_mover/pb_reader.py search "query" --assistant  # search AI responses

# Export
python3 chat_mover/pb_reader.py export <file.pb> <dir>  # export to markdown
```

---

## VBStyle Compliance

The PbReader class follows VBStyle rules:

- **Run dispatch** — `Run(command, params)` with dispatch table
- **Tuple3 returns** — `(1, data, None)` or `(0, None, (code, desc, 0))`
- **self.state dict** — config, db, loaded_files, scan_results, last_error
- **read_state / set_config** — both implemented
- **_p() helper** — parameter extraction
- **No print()** — CLI output via argparse main block
- **No decorators** — no @property, @staticmethod, @classmethod
- **No self._** — all state in self.state dict
- **UPPERCASE constants** — AES_KEY, NONCE_SIZE, TAG_SIZE, WIRE_*, VARIANT_*

---

## File Locations

| File | Location | Purpose |
|---|---|---|
| pb_reader.py | `chat_mover/pb_reader.py` | Main implementation (1041 lines) |
| .pb files | `~/.codeium/windsurf/cascade/` | Cascade trajectory files |
| .pb files | `~/.codeium/windsurf/implicit/` | Implicit trajectory files |
| .pb files | `~/.codeium/windsurf/memories/` | Memory files |
| Pipeline doc | `core/Piplines/Plf_CascadePbReaderPipeline.md` | This file |

---

## Verified Results

| Test | Result |
|---|---|
| Scan | Found 145 .pb files (1 cascade, 1 implicit, 143 memories) |
| Read | Decrypted a 3507-step Cascade conversation |
| Search | Found 3 matches for "language server" in user messages |
| Export | Produced 238 markdown rounds + index file |
| RAM DB | 6 tables, 5 indexes, all in :memory: |

---

## Integration with Cascade

### Current problem:
- Language server restarts cause context loss
- Checkpoints provide ~65% recall (lossy compression)
- Raw chat is not accessible without manual export

### Solution:
- Cascade runs `pb_reader.py search "keyword"` via run_command
- Gets exact conversation chunks with 100% recall
- No more dependency on checkpoints for context recovery
- Can search across all 145 .pb files (all sessions, all time)

### Future enhancements:
- **BCL token extraction** — search for `[@DECISION]`, `[@ERROR]`, `[@FIX]` across all chats
- **Date filtering** — `search "query" --after "2026-06-28"`
- **Session filtering** — search within a specific cascade_id
- **Bottom-up reading** — return latest matches first
- **Context window** — return N steps before/after match for context
- **BCL packet export** — export chat as BCL packets instead of markdown

---

## Relationship to Other Pipelines

| Pipeline | Relationship |
|---|---|
| Chat Ingestion (Road 4) | PB Reader is a specialized ingestion path for encrypted .pb files |
| Context Expansion (Road 8) | PB Reader provides raw chat data for context expansion |
| Error Capture (Road 5) | PB Reader can search for error patterns in chat history |
| BCL Code Graph (Road 6) | PB Reader can extract BCL stamps from chat conversations |
| CLI Safe Execution (Road 7) | PB Reader uses the same CLI dispatch pattern |

---

## Security Notes

- AES key is extracted from the language_server binary (not invented)
- Decryption happens entirely in RAM (:memory: SQLite)
- No plaintext is ever written to disk
- When the process exits, all decrypted data is destroyed
- The key is stored as a hex constant in the source (same as in the binary)
- Access to chat_mover/ is blocked by .codeiumignore (prevents accidental indexing)
