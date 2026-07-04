<!--
  File: cleanup_list.md
  Created: June 23, 2026
  Reason: User wanted to identify and remove unnecessary temp/cache files to free disk space.
  Idea: Catalog every temp/junk file type on the system (codex backups, pycache, build dirs,
        pytest cache, temp dirs, qdrant snapshots) with path, size, and status.
        Track what's been deleted vs what's still pending approval.
        Updated as deletions happen so there's a permanent record.
-->

# Cleanup List — Temp/Junk Files

Updated: June 23, 2026

## DELETED — Codex Backups (2,086 MB) ✅

Chat history explored, compared (3-way), imported into `codex_chat_history` MySQL database (10,569 messages), then backups deleted.

| Path                                               | Size   | Status      | What Happened                          |
| -------------------------------------------------- | ------ | ----------- | -------------------------------------- |
| /Users/wws/.codex.backup.20260416_101328           | 458 MB | DELETED ✅  | 1 session file, subset of backups 2&3  |
| /Users/wws/.codex.backup.deepmerge.20260416_101843 | 814 MB | DELETED ✅  | 41 session files, 831 lines (shared)   |
| /Users/wws/.codex.backup.deepmerge.20260416_101911 | 814 MB | DELETED ✅  | 41 session files, 843 lines (most complete) |

**Import details:**
- 83 JSONL session files found across all 3 backups
- 16,790 raw messages extracted
- 3,181 noise messages removed (IDE context, environment, AGENTS.md)
- 3,520 duplicates removed (dual-logging + overlapping backups)
- **10,569 unique messages** in `codex_chat_history.chat` (970 user, 9,599 assistant)
- Chronological order verified (March 5 → April 16, 2026)
- 0 duplicates remaining, 0 noise remaining

## DELETED — Python Pycache (232 MB) ✅

| Path                               | Size   | Status      |
| ---------------------------------- | ------ | ----------- |
| /Users/wws/.python_pycache/Library | 183 MB | DELETED ✅  |
| /Users/wws/.python_pycache/opt     | 23 MB  | DELETED ✅  |
| /Users/wws/.python_pycache/private | 15 MB  | DELETED ✅  |
| /Users/wws/.python_pycache/Users   | 10 MB  | DELETED ✅  |
| /Users/wws/.python_pycache/tmp     | 436 KB | DELETED ✅  |

## STILL HERE — Build Directories (270 MB)

| Path                                                                                 | Size   | Status       |
| ------------------------------------------------------------------------------------ | ------ | ------------ |
| /Users/wws/contestsystem/GhostEmbedder/build                                         | 270 MB | NOT DELETED  |
| /Users/wws/contestsystem/Database/SEED_FOR_SQL/build                                 | 92 KB  | NOT DELETED  |
| /Users/wws/contestsystem/Database/SEED_FOR_SQL/SEED_FOR_SQL/build                    | 92 KB  | NOT DELETED  |
| /Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/GGUF_Context_Fix/build | 128 KB | NOT DELETED  |

## STILL HERE — Python Cache Directories (152 KB)

| Path                                                         | Size   | Status       |
| ------------------------------------------------------------ | ------ | ------------ |
| /Users/wws/contestsystem/gui/__pycache__               | 128 KB | NOT DELETED  |
| /Users/wws/contestsystem/models/ModelForge/__pycache__ | 4 KB   | NOT DELETED  |
| /Users/wws/contestsystem/my_new_repo/.pytest_cache           | 20 KB  | NOT DELETED  |

## STILL HERE — Temp Directories (308 KB)

| Path                                                                               | Size   | Status       |
| ---------------------------------------------------------------------------------- | ------ | ------------ |
| /Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/App_Chat_Memory/temp | 308 KB | NOT DELETED  |

## STILL HERE — Qdrant Snapshots Temp

| Path                                       | Size    | Status       |
| ------------------------------------------ | ------- | ------------ |
| /Users/wws/.local/bin/qdrant/snapshots/tmp | unknown | NOT DELETED  |

---

## Summary

| Category | Original Size | Status |
|----------|--------------|--------|
| Codex Backups | 2,086 MB | ✅ DELETED — chats saved to MySQL |
| Python Pycache | 232 MB | ✅ DELETED — auto-regenerates |
| Build Directories | 270 MB | ⏳ Still here — awaiting approval |
| Python Cache | 152 KB | ⏳ Still here — awaiting approval |
| Temp Directories | 308 KB | ⏳ Still here — awaiting approval |
| Qdrant Snapshots | unknown | ⏳ Still here — awaiting approval |

**Freed so far: ~2,318 MB (2.3 GB)**
**Remaining to delete: ~270 MB**
