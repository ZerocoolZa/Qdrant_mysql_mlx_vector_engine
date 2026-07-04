# Bloodhound — Persistent Perception Engine

A persistent background perception engine written in C that scans workspaces, extracts "scent" fingerprints, stores them in SQLite, builds relationship graphs, records discovery trails, tracks confidence over time, and syncs memory to Google Drive.

## Philosophy

The Bloodhound does NOT reason. It only:

**Observe. Smell. Remember. Connect. Track. Report.**

## Build

```bash
make
```

Requirements:
- C compiler (cc/clang/gcc)
- SQLite3 development headers (`sqlite3.h`)
- macOS: SQLite is available as a system library. CommonCrypto is used for SHA256.

Install to `/usr/local/bin/`:

```bash
make install
```

Clean:

```bash
make clean
```

## Usage

```
bloodhound scan <workspace_path> [name]   Scan a workspace, extract scents, update memory
bloodhound query <text>                   Search scents by text
bloodhound query-similar <scent_id>       Find similar scents
bloodhound query-rel <scent_id>           Get relationships for a scent
bloodhound query-trails                   List all trails
bloodhound query-trail <trail_id>         Get trail details with steps
bloodhound query-workspace                Get workspace summary
bloodhound query-stats                    Get overall statistics
bloodhound query-recent [N]               Get N most recent observations (default 10)
bloodhound sync [workspace]               Compress + sync DB to Google Drive
bloodhound restore [drive_path]           Restore DB from Google Drive
bloodhound status                         Show DB status, file count, scent count
bloodhound add-trail <origin> <dest> [reason]  Manually add a trail
bloodhound confirm <scent_id>             Increase confidence (AI confirmed)
bloodhound ignore <scent_id>              Decrease confidence (AI ignored)
bloodhound forget <scent_id>              Set confidence to 0 (don't delete)
bloodhound decay [factor]                 Decay all confidence (default 0.95)
```

## How It Works

### 1. Scanning
The scanner walks directory trees recursively, skipping `.git`, `node_modules`, `build/`, `__pycache__`, binary files, etc. For each file it computes a content hash (SHA256 on macOS) and compares with the last scan to detect new, modified, or unchanged files.

### 2. Scent Extraction
The nose tokenizes files by type and extracts scents:

| Language   | Scent Types |
|------------|-------------|
| Python     | functions, classes, imports, decorators, comments, bracket patterns |
| C/C++      | function signatures, structs, typedefs, #include, #define macros, comments |
| Swift      | func, struct/class/enum/protocol, import |
| Markdown   | headings, links, bracket patterns, words |
| JSON       | keys |
| SQL        | CREATE TABLE, INSERT INTO, SELECT FROM (table names) |
| Text       | words longer than 4 characters |

Each scent is normalized (lowercased, whitespace-stripped), fingerprinted (SHA256 of `file:line:normalized`), and stored with 3 lines of context before and after.

### 3. Storage
All scents, observations, relationships, trails, and learning events are stored in SQLite at `~/.bloodhound/memory.db`.

### 4. Relationships
The Bloodhound builds a graph connecting scents:
- `same_file` — scents found in the same source file
- `imports` — import statements linked to functions/classes they may reference
- `same_folder`, `similar`, `calls`, `references`, `mentions`

### 5. Trails
Trails record discovery paths — how the AI got from one scent to another. Trails can be added manually or will be built automatically during future exploration.

### 6. Confidence Tracking
Each scent starts at confidence 0.5. Repeated observation increases it (+0.05 per sighting). The AI can `confirm` (+0.15) or `ignore` (-0.10) scents. `forget` sets confidence to 0 without deleting. `decay` multiplies all confidence by a factor (default 0.95) for time-based decay.

### 7. Sync
`bloodhound sync` compresses the SQLite DB with gzip and copies it to the Google Drive mount path:
```
/Users/wws/Library/CloudStorage/GoogleDrive-kautharlodewyk9@gmail.com/My Drive/Bloodhound/
```
Two files are written:
- `bloodhound_memory_<workspace>_<timestamp>.db.gz` — timestamped snapshot
- `bloodhound_memory_latest.db.gz` — latest snapshot

`bloodhound restore` decompresses the latest snapshot and replaces the local DB (with a `.bak` backup).

### 8. Query Interface
All query commands output JSON to stdout for easy parsing by the AI. Errors go to stderr.

## Output Format

All output is JSON. Example:

```json
{"query":"test","results":[{"scent_id":42,"fingerprint":"a1b2c3...","type":"function",...}]}
```

## Database Schema

See `bh_db.c` for the full schema. Key tables:
- `scents` — scent packets (the core identity)
- `observations` — every encounter logged
- `relationships` — graph connections
- `trails` / `trail_steps` — discovery paths
- `workspaces` — one row per workspace
- `learning` — confidence adjustments over time

## File Structure

```
core/Dom_Bloodhound/
├── bloodhound.h     — Types, structs, declarations, constants
├── bh_db.c          — SQLite database layer
├── bh_scanner.c     — Workspace scanner
├── bh_nose.c        — Scent extractor
├── bh_query.c       — Query engine
├── bh_sync.c        — Google Drive sync
├── bh_main.c        — CLI entry point
├── Makefile         — Build
└── README.md        — This file
```

## Version

1.0
