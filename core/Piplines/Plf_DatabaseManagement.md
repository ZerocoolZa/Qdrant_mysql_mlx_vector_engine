# Database Management Pipeline

## Origin

This document is the comprehensive reference for **all databases** managed by the
`core/Dom_Unified/` stack. It covers MySQL (primary relational store), Neo4j (graph),
Qdrant (vector), SQLite (file-based embedded), and the LMDB/Word2Vec layer that
provides RAM-resident embeddings and ANN search.

The service lifecycle authority is `DomSystem` (`core/Dom_Unified/DomSystem.py`),
which replaces macOS launchd/brew services for these databases. All start/stop/restart
operations flow through its `Run()` dispatch.

---

# Table of Contents

1. [Architecture Overview — The 4+1 Database Stack](#1-architecture-overview)
2. [Service Lifecycle Authority — DomSystem](#2-service-lifecycle-authority)
3. [MySQL 8.0 — Primary Relational Store](#3-mysql-80)
4. [Neo4j — Graph Database](#4-neo4j)
5. [Qdrant — Vector Database](#5-qdrant)
6. [SQLite — Embedded File-Based Databases](#6-sqlite)
7. [LMDB + Word2Vec — RAM Embedding Layer](#7-lmdb--word2vec)
8. [MySQL Database Catalog — All Schemas](#8-mysql-database-catalog)
9. [SQLite Database Catalog — All .db Files](#9-sqlite-database-catalog)
10. [Connection Parameters Quick Reference](#10-connection-parameters)
11. [Start/Stop Commands](#11-startstop-commands)
12. [Health Checks & Recovery](#12-health-checks)
13. [Config File Paths](#13-config-file-paths)
14. [Data Flow Between Databases](#14-data-flow)
15. [Troubleshooting](#15-troubleshooting)
16. [Word2Vec Training Pipeline](#16-word2vec-training-pipeline)
17. [MySQL Ingestion Pipeline](#17-mysql-ingestion-pipeline)
18. [Qdrant Vector Operations Pipeline](#18-qdrant-vector-ops)
19. [SQLite Catalog Management](#19-sqlite-catalog-management)
20. [Execution Engine In-RAM Bus](#20-execution-engine-bus)
21. [Neo4j Memory Model — 21-Component Engine](#21-neo4j-memory-model)
22. [Storage Stack Analysis — Do We Need More?](#22-storage-stack-analysis)
23. [Graph Database Comparison](#23-graph-db-comparison)
24. [MySQL to Neo4j Migration Path](#24-mysql-to-neo4j-migration)
25. [Key Database Principles from learned_rules](#25-key-principles)
26. [Troubleshooting](#26-troubleshooting-2)

---

## 1. Architecture Overview

The system uses a **4+1 database stack**:

```
┌─────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                    │
│   (Cascade, Devin, GUI engines, pipelines, MCP)      │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│  MySQL   │  Neo4j   │  Qdrant  │  SQLite  │  LMDB   │
│  8.0.46  │  (brew)  │  (bin)   │ (file)   │ (mmap)  │
│          │          │          │          │         │
│ Truth    │ Graph    │ Meaning  │ Local    │ RAM     │
│ Store    │ Traversal│ Search   │ Cache    │ Vector  │
│          │ Causality│ Embedding│ Work DBs │ ANN     │
├──────────┴──────────┴──────────┴──────────┴─────────┤
│              DomSystem (lifecycle authority)          │
│              core/Dom_Unified/DomSystem.py            │
├───────────────────────────────────────────────────────┤
│              macOS (no launchd for these)             │
└───────────────────────────────────────────────────────┘
```

### Division of Responsibility

| Database | Role | What It Owns |
|----------|------|-------------|
| **MySQL** | Truth Store | Structured records, codebase, classes, methods, chat history, knowledge base, learned rules, BCL tokens, execution logs |
| **Neo4j** | Relationship Store | Graph traversal, causality, identity, evidence chains, node/edge relationships |
| **Qdrant** | Meaning Store | Vector embeddings, semantic similarity, nearest-neighbor retrieval, context activation |
| **SQLite** | Local Store | Per-domain work databases, in-RAM execution buses, caches, pipeline state |
| **LMDB** | RAM Vector Store | Word2Vec embeddings, full model tensors, real-time ANN similarity search, incremental training updates |

---

## 2. Service Lifecycle Authority — DomSystem

**File:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/DomSystem.py`
**Config:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Unified/Config.py`

DomSystem is the **single authority** for database service lifecycle. It replaces
macOS launchd and Homebrew services for MySQL, Neo4j, and Qdrant. SQLite and LMDB
are file-based — no process management needed.

### Launch Modes

| Mode | Constant | Description |
|------|----------|-------------|
| `direct` | `DOM_LAUNCH_MODE_DIRECT` | Start binary directly via `subprocess.Popen` |
| `brew` | `DOM_LAUNCH_MODE_BREW` | Use `brew services start/stop` |
| `launchd` | `DOM_LAUNCH_MODE_LAUNCHD` | Use `launchctl load/unload` with plist |
| `always` | `DOM_LAUNCH_MODE_ALWAYS` | Always available (SQLite, no process) |

### Service Modes (idle timeout multipliers)

| Mode | Constant | Multiplier | Description |
|------|----------|------------|-------------|
| `transient` | `DOM_SERVICE_MODE_TRANSIENT` | 1x | Quick query, normal idle timeout (300s) |
| `batch` | `DOM_SERVICE_MODE_BATCH` | 6x | Batch processing (1800s) |
| `constant` | `DOM_SERVICE_MODE_CONSTANT` | 24x | Long-running (7200s) |
| `pinned` | `DOM_SERVICE_MODE_PINNED` | 0 (never) | Never unload (explicit pin) |

### Lifecycle Config Constants

| Constant | Value | File |
|----------|-------|------|
| `DOM_IDLE_TIMEOUT_SECONDS` | 300 | `Config.py:129` |
| `DOM_MAX_RESTARTS` | 3 | `Config.py:130` |
| `DOM_HEALTH_FAILS_BEFORE_RESTART` | 2 | `Config.py:131` |
| `DOM_STOP_TIMEOUT_SECONDS` | 10 | `Config.py:132` |
| `DOM_START_WAIT_SECONDS` | 15 | `Config.py:133` |
| `DOM_HEALTH_CHECK_INTERVAL` | 60 | `Config.py:134` |
| `DOM_RAM_BUDGET_MB` | 1024 | `Config.py:136` |

### DomSystem Run() Dispatch Commands

| Command | Purpose |
|---------|---------|
| `acquire` | Lazy-load + refcount (starts if not running) |
| `release` | Decrement refcount |
| `start` | Direct start (bypass refcount) |
| `stop` | Direct stop (bypass refcount) |
| `restart` | Stop then start |
| `suspend` | Stop but keep registry entry |
| `resume` | Restart from suspended |
| `status` | Full status report |
| `health` | Health check + auto-recovery |
| `recover` | Force restart on failure |
| `gc` | Garbage collect idle services |
| `is_loaded` | Check if service is loaded |
| `is_running` | Check if service process is running |
| `is_busy` | Check if service has active refs |
| `is_idle` | Check if service is idle (refs == 0) |
| `start_all` | Start all services |
| `stop_all` | Stop all services |
| `check_all` | Health check all services |

### Usage Example

```python
import sys
sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem

ds = DomSystem()

# Start MySQL directly
ok, data, err = ds.Run("start", {"service": "mysql"})
# Returns: (1, {"pid": 1515, "started": True}, None)

# Check if running
ok, data, err = ds.Run("is_running", {"service": "mysql"})

# Acquire with refcount (lazy-load)
ok, handle, err = ds.Run("acquire", {"service": "qdrant"})

# Release
ok, data, err = ds.Run("release", {"service": "qdrant"})

# Health check
ok, data, err = ds.Run("health", {"service": "mysql"})

# Stop
ok, data, err = ds.Run("stop", {"service": "mysql"})
```

---

## 3. MySQL 8.0

### Service Configuration

| Property | Value | Config Location |
|----------|-------|-----------------|
| Service name | `mysql` | `Config.py:174` |
| Display name | MySQL 8.0 | `Config.py:175` |
| Launch mode | `direct` | `Config.py:176` |
| Binary | `/opt/homebrew/opt/mysql@8.0/bin/mysqld` | `Config.py:177` |
| Host | `127.0.0.1` | `Config.py:189` |
| Port | `3306` | `Config.py:190` |
| Socket | `/tmp/mysql.sock` | `Config.py:184` |
| PID file | `/opt/homebrew/var/mysql/nwm.pid` | `Config.py:183,187` |
| Error log | `/opt/homebrew/var/mysql/nwm.err` | `Config.py:182,188` |
| Health check | TCP | `Config.py:191` |
| Dependencies | None | `Config.py:192` |
| Est. RAM | 512 MB | `Config.py:193` |
| Est. CPU | 5% | `Config.py:194` |
| Uses GPU | No | `Config.py:195` |
| Uses I/O | Yes | `Config.py:196` |

### Startup Arguments

```
--basedir=/opt/homebrew/opt/mysql@8.0
--datadir=/opt/homebrew/var/mysql
--plugin-dir=/opt/homebrew/opt/mysql@8.0/lib/plugin
--log-error=/opt/homebrew/var/mysql/nwm.err
--pid-file=/opt/homebrew/var/mysql/nwm.pid
--socket=/tmp/mysql.sock
```

### Connection Parameters

| Parameter | Value |
|-----------|-------|
| Host | `localhost` or `127.0.0.1` |
| Port | `3306` |
| User | `root` |
| Password | (empty — no password) |
| Socket | `/tmp/mysql.sock` |
| Version | 8.0.46 |

### Raw Start Command (if DomSystem is unavailable)

```bash
/opt/homebrew/opt/mysql@8.0/bin/mysqld \
  --basedir=/opt/homebrew/opt/mysql@8.0 \
  --datadir=/opt/homebrew/var/mysql \
  --plugin-dir=/opt/homebrew/opt/mysql@8.0/lib/plugin \
  --log-error=/opt/homebrew/var/mysql/nwm.err \
  --pid-file=/opt/homebrew/var/mysql/nwm.pid \
  --socket=/tmp/mysql.sock &
```

### Raw Stop Command

```bash
# Graceful (SIGTERM)
kill $(cat /opt/homebrew/var/mysql/nwm.pid)

# Force (SIGKILL) — only if SIGTERM fails after 10s
kill -9 $(cat /opt/homebrew/var/mysql/nwm.pid)
```

### MySQL Connection in Python

```python
# Used throughout the codebase
GRAPH_MYSQL_HOST = "localhost"
GRAPH_MYSQL_USER = "root"
GRAPH_MYSQL_PORT = 3306
GRAPH_MYSQL_PASS = ""  # empty password
```

### MySQL Server Variables (Live Extraction)

#### Connection & Network

| Variable | Value |
|----------|-------|
| `port` | 3306 |
| `bind_address` | 127.0.0.1 |
| `socket` | `/tmp/mysql.sock` |
| `skip_networking` | OFF |
| `max_connections` | 151 |
| `max_allowed_packet` | 67108864 (64 MB) |
| `wait_timeout` | 28800 (8 hours) |
| `interactive_timeout` | 28800 (8 hours) |
| `default_authentication_plugin` | `caching_sha2_password` |

#### Version & Character Set

| Variable | Value |
|----------|-------|
| `version` | 8.0.46 |
| `character_set_database` | `utf8mb4` |
| `collation_database` | `utf8mb4_0900_ai_ci` |
| `sql_mode` | `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION` |

#### Binary Logging

| Variable | Value |
|----------|-------|
| `log_bin` | ON |
| `server_id` | 1 |

Binary log files on disk:

| File | Size |
|------|------|
| `binlog.000024` | ~195 MB |
| `binlog.000025` | 437 bytes |
| `binlog.000026` | 180 bytes |
| `binlog.000027` | 180 bytes |
| `binlog.000028` | 180 bytes |
| `binlog.000029` | ~1.5 MB |
| `binlog.000030` | 414 bytes |
| `binlog.index` | 112 bytes |

#### InnoDB Configuration

| Variable | Value |
|----------|-------|
| `innodb_buffer_pool_size` | 134217728 (128 MB) |
| `innodb_buffer_pool_chunk_size` | 134217728 (128 MB) |
| `innodb_buffer_pool_instances` | 1 |
| `innodb_buffer_pool_dump_at_shutdown` | ON |
| `innodb_buffer_pool_load_at_startup` | ON |
| `innodb_buffer_pool_dump_pct` | 25 |
| `innodb_log_file_size` | 50331648 (48 MB) |
| `innodb_flush_log_at_trx_commit` | 1 |
| `innodb_flush_log_at_timeout` | 1 |
| `innodb_flush_method` | `fsync` |
| `innodb_flush_neighbors` | 0 |
| `innodb_flush_sync` | ON |
| `innodb_flushing_avg_loops` | 30 |
| `innodb_adaptive_flushing` | ON |
| `innodb_adaptive_flushing_lwm` | 10 |
| `innodb_adaptive_hash_index` | ON |
| `innodb_adaptive_hash_index_parts` | 8 |
| `innodb_adaptive_max_sleep_delay` | 150000 |
| `innodb_autoinc_lock_mode` | 2 |
| `innodb_change_buffering` | `all` |
| `innodb_change_buffer_max_size` | 25 |
| `innodb_checksum_algorithm` | `crc32` |
| `innodb_autoextend_increment` | 64 |
| `innodb_commit_concurrency` | 0 |
| `innodb_compression_failure_threshold_pct` | 5 |

#### Extended InnoDB & Storage Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `innodb_log_buffer_size` | 16777216 (16 MB) | Redo log buffer |
| `innodb_file_per_table` | ON | Each table has own `.ibd` file |
| `innodb_autoinc_lock_mode` | 2 | Interleaved mode (fastest) |
| `default_storage_engine` | InnoDB | Default engine for new tables |
| `default_tmp_storage_engine` | InnoDB | Default for temp tables |
| `innodb_flush_log_at_trx_commit` | 1 | Full ACID (flush on every commit) |

#### Network & Timeout Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `net_read_timeout` | 30 | Seconds to wait for more data from connection |
| `net_write_timeout` | 60 | Seconds to wait for a block to be written |
| `wait_timeout` | 28800 (8 hours) | Non-interactive idle timeout |
| `interactive_timeout` | 28800 (8 hours) | Interactive idle timeout |
| `max_allowed_packet` | 67108864 (64 MB) | Max packet size |
| `mysqlx_port` | 33060 | X Protocol port |
| `mysqlx_socket` | `/tmp/mysqlx.sock` | X Protocol socket |

#### Buffer & Cache Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `key_buffer_size` | 8388608 (8 MB) | MyISAM key buffer (legacy) |
| `read_buffer_size` | 131072 (128 KB) | Sequential read buffer |
| `sort_buffer_size` | 262144 (256 KB) | Sort buffer per sort operation |
| `join_buffer_size` | 262144 (256 KB) | Join buffer (no index joins) |
| `tmp_table_size` | 16777216 (16 MB) | Internal temp table size limit |
| `max_heap_table_size` | 16777216 (16 MB) | MEMORY engine table size limit |
| `bulk_insert_buffer_size` | 8388608 (8 MB) | MyISAM bulk insert buffer |
| `myisam_sort_buffer_size` | 8388608 (8 MB) | MyISAM index sort buffer |
| `table_open_cache` | 4000 | Open table cache slots |
| `thread_cache_size` | 9 | Thread cache size |

#### Logging & Monitoring Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `log_error` | `/opt/homebrew/var/mysql/nwm.err` | Error log file |
| `general_log` | OFF | General query log disabled |
| `slow_query_log` | OFF | Slow query log disabled |
| `long_query_time` | 10.0 | Slow query threshold (seconds) |

#### Locale & Identity Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `lower_case_table_names` | 2 | Preserve case on macOS |
| `lc_time_names` | `en_US` | Locale for date/month names |
| `time_zone` | `SYSTEM` | Uses system timezone |
| `system_time_zone` | `SAST` | Server system timezone |
| `default_authentication_plugin` | `caching_sha2_password` | MySQL 8.0 default |
| `caching_sha2_password_auto_generate_rsa_keys` | ON | Auto-generate RSA keys |

### MySQL User Grants (root@localhost)

The `root` user has **full privileges** with `GRANT OPTION`:

**Standard Grants:**
- `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, SHUTDOWN, PROCESS, FILE, REFERENCES, INDEX, ALTER, SHOW DATABASES, SUPER, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER, CREATE TABLESPACE, CREATE ROLE, DROP ROLE` ON `*.*`

**Administrative Grants:**
- `APPLICATION_PASSWORD_ADMIN, AUDIT_ABORT_EXEMPT, AUDIT_ADMIN, AUTHENTICATION_POLICY_ADMIN, BACKUP_ADMIN, BINLOG_ADMIN, BINLOG_ENCRYPTION_ADMIN, CLONE_ADMIN, CONNECTION_ADMIN, ENCRYPTION_KEY_ADMIN, FIREWALL_EXEMPT, FLUSH_OPTIMIZER_COSTS, FLUSH_STATUS, FLUSH_TABLES, FLUSH_USER_RESOURCES, GROUP_REPLICATION_ADMIN, GROUP_REPLICATION_STREAM, INNODB_REDO_LOG_ARCHIVE, INNODB_REDO_LOG_ENABLE, PASSWORDLESS_USER_ADMIN, PERSIST_RO_VARIABLES_ADMIN, REPLICATION_APPLIER, REPLICATION_SLAVE_ADMIN, RESOURCE_GROUP_ADMIN, RESOURCE_GROUP_USER, ROLE_ADMIN, SENSITIVE_VARIABLES_OBSERVER, SERVICE_CONNECTION_ADMIN, SESSION_VARIABLES_ADMIN, SET_USER_ID, SHOW_ROUTINE, SYSTEM_USER, SYSTEM_VARIABLES_ADMIN, TABLE_ENCRYPTION_ADMIN, TELEMETRY_LOG_ADMIN, XA_RECOVER_ADMIN` ON `*.*`

**Proxy Grant:**
- `PROXY ON ''@'' TO 'root'@'localhost'` WITH GRANT OPTION

### MySQL Storage Engine Breakdown

All application databases use **InnoDB** exclusively, with two exceptions:

| Database | Engine | Table Count | Notes |
|----------|--------|-------------|-------|
| `vb_shared` | InnoDB | 94 | Standard tables |
| `vb_shared` | MEMORY | 1 | In-RAM table (likely temp or cache) |
| `token_registry` | InnoDB | 32 | Standard tables |
| `token_registry` | (VIEW) | 1 | `all_files_view` — virtual table |
| `vbstyle_documents` | InnoDB | 25 | Standard tables |
| `vbstyle_documents` | (VIEW) | 1 | `pattern_stats` — virtual table |
| All others | InnoDB | varies | 100% InnoDB |

**Total:** 271 InnoDB tables, 1 MEMORY table, 2 views across 24 application databases.

### MySQL Views

| Database | View Name | Purpose |
|----------|-----------|---------|
| `token_registry` | `all_files_view` | Aggregated view of all indexed files |
| `vbstyle_documents` | `pattern_stats` | Statistics view for pattern analysis |

### MySQL Collation Analysis

The databases use **two different collations**:

| Collation | Used By | Character Set | Notes |
|-----------|---------|---------------|-------|
| `utf8mb4_unicode_ci` | `vb_shared`, `devin`, `Chat_History`, `cascade_chats` | `utf8mb4` | Unicode-correct sorting |
| `utf8mb4_0900_ai_ci` | `CODEBASE`, `qa_system`, `vb_code_test` | `utf8mb4` | MySQL 8.0 default collation |
| `utf8mb4_0900_ai_ci` | `chatgpt_chats.messages` (table-level) | `utf8mb4` | Mixed within same instance |

**Note:** The collation difference (`utf8mb4_unicode_ci` vs `utf8mb4_0900_ai_ci`) can cause
issues with cross-database JOINs on string columns. The server default is
`utf8mb4_0900_ai_ci` but older databases were created with `utf8mb4_unicode_ci`.

### vb_shared Table Details (Top 20 by Data Size)

| Table | Rows | Data (MB) | Index (MB) | Collation | Auto Increment |
|-------|------|-----------|------------|-----------|----------------|
| `json_ingestions` | 17 | 201.5 | 0.0 | `utf8mb4_unicode_ci` | 17 |
| `know_answers` | 31,683 | 52.6 | 1.5 | `utf8mb4_unicode_ci` | 42,570 |
| `chat_ingestions` | 313 | 48.5 | 0.1 | `utf8mb4_unicode_ci` | 465 |
| `know_questions` | 111,452 | 38.6 | 0.0 | `utf8mb4_unicode_ci` | 118,513 |
| `code_classes` | 247 | 13.2 | 0.0 | `utf8mb4_unicode_ci` | 319 |
| `code_index` | 23,364 | 8.5 | 8.0 | `utf8mb4_0900_ai_ci` | 27,502 |
| `code_registry` | 186 | 4.5 | 0.0 | `utf8mb4_unicode_ci` | 205 |
| `learned_rules` | 10,341 | 3.5 | 0.0 | `utf8mb4_unicode_ci` | 28,566 |
| `graph_edges` | 30,455 | 2.5 | 3.0 | `utf8mb4_unicode_ci` | 33,775 |
| `execution_log` | 396 | 1.5 | 0.0 | `utf8mb4_unicode_ci` | 404 |
| `err_tokens` | 4,951 | 1.5 | 0.5 | `utf8mb4_unicode_ci` | 5,139 |
| `code_co_occurrence` | 11,017 | 1.5 | 3.7 | `utf8mb4_0900_ai_ci` | 12,253 |
| `code_identifier_frequency` | 12,384 | 1.5 | 2.2 | `utf8mb4_0900_ai_ci` | 13,526 |
| `c_classes` | 24 | 0.5 | 0.1 | `utf8mb4_0900_ai_ci` | 30 |
| `know_nodes` | 1,603 | 0.5 | 0.2 | `utf8mb4_0900_ai_ci` | 1,739 |
| `token_master` | 5,755 | 0.4 | 0.4 | `utf8mb4_unicode_ci` | 9,216 |
| `designrationale` | 273 | 0.3 | 0.0 | `utf8mb4_unicode_ci` | 308 |
| `method_inventory` | 172 | 0.3 | 0.0 | `utf8mb4_unicode_ci` | 414 |
| `instructions` | 92 | 0.1 | 0.0 | `utf8mb4_unicode_ci` | 107 |
| `know_solutions` | 348 | 0.1 | 0.0 | `utf8mb4_unicode_ci` | 10,077 |

**Note:** `know_solutions` has auto_increment at 10,077 but only 348 rows — indicating
many entries were deleted over time, leaving gaps in the ID sequence.

### vb_shared Index Summary (Key Tables)

| Table | Indexes | Key Indexes |
|-------|---------|-------------|
| `know_problems` | 6 | PRIMARY, category_id, context_id, domain_id, token_id, type_id |
| `know_nodes` | 4 | PRIMARY, parent_id, root_id, status |
| `graph_edges` | 3 | PRIMARY, from_node, to_node |
| `graph_nodes` | 2 | PRIMARY, unique_node (node_type + name) |
| `learned_rules` | 1 | PRIMARY |
| `rule_tokens` | 2 | PRIMARY, name (unique) |
| `code_index` | 2 | PRIMARY, (implied by data) |
| `layout_definitions` | 5 | PRIMARY, uniq_app_node, idx_parent, idx_role, idx_type |
| `widget_library` | 5 | PRIMARY, uniq_widget_key, idx_category, idx_container, idx_parent, idx_position |
| `session_graphs` | 4 | PRIMARY, idx_date, idx_session, idx_status |

### MySQL User Accounts

| User | Host | Plugin | Has Password | Account Locked |
|------|------|--------|-------------|----------------|
| `mysql.infoschema` | `localhost` | `caching_sha2_password` | Yes | Yes |
| `mysql.session` | `localhost` | `caching_sha2_password` | Yes | Yes |
| `mysql.sys` | `localhost` | `caching_sha2_password` | Yes | Yes |
| `root` | `localhost` | `caching_sha2_password` | **No** | No |

The `root` user has no password and is not locked. All system users are locked
and have passwords set. Authentication uses `caching_sha2_password` (MySQL 8.0
default).

### MySQL Data Directory Structure

**Path:** `/opt/homebrew/var/mysql/`
**Total disk usage:** 25 GB

```
/opt/homebrew/var/mysql/
├── #ib_16384_0.dblwr          (196 KB — doublewrite buffer)
├── #ib_16384_1.dblwr          (8.5 MB — doublewrite buffer)
├── #innodb_redo/              (redo log directory)
├── #innodb_temp/              (temp tablespace)
├── auto.cnf                   (server UUID)
├── ib_buffer_pool             (buffer pool dump)
├── ibdata1                    (system tablespace)
├── ibtmp1                     (temp tablespace)
├── mysql.ibd                  (mysql system tablespace)
├── undo_001                   (undo tablespace)
├── undo_002                   (undo tablespace)
├── binlog.000024 ... binlog.000030  (binary logs)
├── binlog.index               (binary log index)
│
├── SSL/TLS certificates:
│   ├── ca.pem                 (CA certificate)
│   ├── ca-key.pem             (CA private key)
│   ├── client-cert.pem        (client certificate)
│   ├── client-key.pem         (client private key)
│   ├── server-cert.pem        (server certificate)
│   ├── server-key.pem         (server private key)
│   ├── private_key.pem        (private key)
│   └── public_key.pem         (public key)
│
├── nwm.pid                    (PID file)
├── nwm.err                    (error log)
│
├── mysql/                     (mysql system schema)
├── performance_schema/        (performance schema)
├── sys/                       (sys schema)
│
├── CODEBASE/                  (18.6 GB — code file archive)
├── Chat_History/              (370 MB — chat history)
├── agent_os/                  (0.2 MB — agent OS)
├── bcl_ir/                    (197 MB — BCL IR)
├── cascade_chats/             (393 MB — Cascade chats)
├── cascade_intent/            (0.3 MB — intent tracking)
├── chatgpt_chats/             (116 MB — ChatGPT chats)
├── chatgpt_export/            (244 MB — ChatGPT export)
├── code_graph/                (22 MB — code graph)
├── codex_chat_history/        (23 MB — Codex chat)
├── devin/                     (438 MB — Devin sessions)
├── email_store/               (0.1 MB — email store)
├── graph_computation_units/   (4 MB — computation units)
├── gui_pipeline/              (0.0 MB — GUI pipeline)
├── qa_system/                 (94 MB — QA system)
├── questions/                 (311 MB — Q&A evidence)
├── rht_emails/                (0.2 MB — RHT emails)
├── token_registry/            (256 MB — token registry)
├── treasure_trove/            (125 MB — treasure trove)
├── vb_code_test/              (47 MB — VB code test)
├── vb_ingestion/              (0.1 MB — VB ingestion)
├── vb_shared/                 (405 MB — knowledge base)
├── vbstyle_documents/         (682 MB — VBStyle documents)
└── yahoo_emails/              (11 MB — Yahoo emails)
```

### MySQL Table Schema Example: chatgpt_chats.messages

```sql
CREATE TABLE `messages` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `conversation_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `node_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content_type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `author_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `text` longtext COLLATE utf8mb4_unicode_ci,
  `word_count` int DEFAULT '0',
  `token_count` int DEFAULT '0',
  `create_time` double DEFAULT NULL,
  `create_date` datetime DEFAULT NULL,
  `model_slug` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ingested_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_conv` (`conversation_id`),
  KEY `idx_role` (`role`),
  KEY `idx_create_date` (`create_date`),
  KEY `idx_model` (`model_slug`),
  FULLTEXT KEY `ft_messages_text` (`text`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`conversation_id`)
    REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=73984
  DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Key schema features:
- **FULLTEXT index** on `text` column for natural language search
- **Foreign key** with `ON DELETE CASCADE` — deleting a conversation deletes its messages
- **Collation**: `utf8mb4_unicode_ci` (different from server default `utf8mb4_0900_ai_ci`)
- **AUTO_INCREMENT** at 73,984 (higher than row count due to deleted rows)

### Why MySQL Is Not Managed by macOS launchd

MySQL was previously managed via `brew services` / launchd. The DomSystem now
manages it directly because:

1. **Resource-aware startup** — DomSystem checks RAM budget before starting
2. **Reference counting** — Multiple components can acquire/release MySQL
3. **Health monitoring** — Automatic health checks with restart on failure
4. **Idle GC** — MySQL can be unloaded after idle timeout to free RAM
5. **Dependency resolution** — Services that depend on MySQL (e.g., `devin_sync_daemon`) auto-start it

---

## 4. Neo4j

### Service Configuration

| Property | Value | Config Location |
|----------|-------|-----------------|
| Service name | `neo4j` | `Config.py:198` |
| Display name | Neo4j Graph DB | `Config.py:199` |
| Launch mode | `direct` | `Config.py:200` |
| Binary | `/opt/homebrew/opt/neo4j/bin/neo4j` | `Config.py:201` |
| Start args | `["start"]` | `Config.py:202` |
| Stop args | `["stop"]` | `Config.py:203` |
| PID file | `/opt/homebrew/var/neo4j/run/neo4j.pid` | `Config.py:204` |
| Log file | `/opt/homebrew/var/neo4j/logs/neo4j.log` | `Config.py:205` |
| Host | `127.0.0.1` | `Config.py:206` |
| Port | `7474` (HTTP) / `7687` (Bolt) | `Config.py:207` |
| Health check | TCP | `Config.py:208` |
| Dependencies | None | `Config.py:209` |
| Est. RAM | 768 MB | `Config.py:210` |
| Est. CPU | 10% | `Config.py:211` |

### Neo4j Connection Parameters

| Parameter | Value | Config Location |
|-----------|-------|-----------------|
| Bolt URI | `bolt://localhost:7687` | `Config.py:31` |
| User | (empty) | `Config.py:32` |
| Password | (empty) | `Config.py:33` |

### Raw Start/Stop Commands

```bash
# Start
/opt/homebrew/opt/neo4j/bin/neo4j start

# Stop
/opt/homebrew/opt/neo4j/bin/neo4j stop
```

### Neo4j Data Directory Structure

**Path:** `/opt/homebrew/var/neo4j/`
**Total disk usage:** 7.8 MB

```
/opt/homebrew/var/neo4j/
├── data/
│   ├── databases/
│   │   ├── neo4j/            (default database — graph data)
│   │   │   ├── neostore
│   │   │   ├── neostore.counts.db
│   │   │   ├── neostore.indexstats.db
│   │   │   ├── neostore.labeltokenstore.db
│   │   │   ├── neostore.nodestore.db
│   │   │   ├── neostore.propertystore.db
│   │   │   ├── neostore.propertystore.db.arrays
│   │   │   ├── neostore.propertystore.db.index
│   │   │   ├── neostore.propertystore.db.index.keys
│   │   │   ├── neostore.relationshipstore.db
│   │   │   ├── neostore.schemastore.db
│   │   │   └── database_lock
│   │   ├── system/           (system database — users, roles, config)
│   │   └── store_lock
│   ├── dbms/
│   │   ├── admin.ini         (admin auth)
│   │   └── auth.ini          (user auth)
│   ├── server_id             (server identifier)
│   └── transactions/         (transaction logs)
├── logs/
│   └── neo4j.log             (main log file)
└── conf/
    └── neo4j.conf            (configuration — currently empty/default)
```

### Neo4j Databases

| Database | Purpose |
|----------|---------|
| `neo4j` | Default database — contains all graph data (nodes, relationships, properties) |
| `system` | System database — user management, roles, database configuration |

### Neo4j Configuration

The `neo4j.conf` file at `/opt/homebrew/var/neo4j/conf/neo4j.conf` is currently
empty (all defaults). Key default behaviors:

- **HTTP port**: 7474
- **Bolt port**: 7687
- **Auth**: Disabled (empty user/password in `Config.py`)
- **Data directory**: `/opt/homebrew/var/neo4j/data/`
- **Store format**: Neo4j 5.x store format (file-based B+tree + linked list)

### What Neo4j Stores

- Message, Observation, Fact, Episode, SemanticMemory nodes
- SUPPORTED_BY, BEFORE, AFTER, CAUSES, RESOLVES, PART_OF, SAME_AS, CONTRADICTS relationships
- Domain → Class → Method → File hierarchy
- Evidence chains, truth state transitions, identity aliases

---

## 5. Qdrant

### Service Configuration

| Property | Value | Config Location |
|----------|-------|-----------------|
| Service name | `qdrant` | `Config.py:156` |
| Display name | Qdrant Vector DB | `Config.py:157` |
| Launch mode | `direct` | `Config.py:158` |
| Binary | `~/.local/bin/qdrant/qdrant` | `Config.py:159` |
| Config path | `~/.local/bin/qdrant/config.yaml` | `Config.py:160` |
| PID file | `~/.local/bin/qdrant/qdrant.pid` | `Config.py:162` |
| Log file | `~/.local/bin/qdrant/qdrant.log` | `Config.py:163` |
| Host | `127.0.0.1` | `Config.py:164` |
| Port | `6333` | `Config.py:165` |
| Health check | HTTP | `Config.py:166` |
| Health URL | `http://127.0.0.1:6333/healthz` | `Config.py:167` |
| Dependencies | None | `Config.py:168` |
| Est. RAM | 256 MB | `Config.py:169` |
| Storage dir | `~/.local/bin/qdrant/storage/` | filesystem |
| Snapshots dir | `~/.local/bin/qdrant/snapshots/` | filesystem |

### Raw Start Command

```bash
~/.local/bin/qdrant/qdrant --config-path ~/.local/bin/qdrant/config.yaml &
```

### What Qdrant Stores

- Vector embeddings for messages, observations, facts
- Semantic similarity indices (nearest-neighbor retrieval)
- Context activation vectors ("find nodes that MEAN the same thing")
- Collection-level metadata and filtering

### Qdrant config.yaml (Key Settings)

**File:** `~/.local/bin/qdrant/config.yaml`

```yaml
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334

storage:
  storage_path: ./storage
  snapshots_path: ./snapshots
  wal:
    wal_capacity_mb: 32
    wal_segments_ahead: 0
  performance:
    max_search_threads: 4
  optimizers:
    default_segment_number: 2
    indexing_threshold_kb: 20000
    flush_threshold_sec: 1
  default_collection:
    vectors: { size: 768, distance: Cosine }
```

### Qdrant Storage Directory Structure

**Path:** `~/.local/bin/qdrant/storage/`

```
storage/
├── collections/
│   └── <collection_name>/
│       ├── segments/
│       │   ├── segment-0/
│       │   │   ├── payload.json
│       │   │   ├── vectors.bin
│       │   │   └── index.bin
│       │   └── segment-1/
│       └── collection.lock
└── raft_state.json
```

### Qdrant Snapshots

**Path:** `~/.local/bin/qdrant/snapshots/`

Snapshots are full collection backups stored as `.tar.gz` files. Used for
disaster recovery and collection migration between Qdrant instances.

---

## 6. SQLite

SQLite is **always available** — no process management needed. Launch mode is
`DOM_LAUNCH_MODE_ALWAYS`. There are 56+ SQLite database files across the workspace,
each serving a specific domain or pipeline.

### SQLite in DomSystem

| Property | Value |
|----------|-------|
| Service name | `sqlite` |
| Launch mode | `always` |
| Binary | (none — file-based) |
| Port | 0 |
| Health check | none |
| Est. RAM | 0 MB |

### In-RAM SQLite Usage

The execution engine and graph pipeline use `:memory:` SQLite databases as
event buses and staging areas:

| Use Case | Config Constant | Value |
|----------|----------------|-------|
| Graph staging | `GRAPH_STAGING_DB` | `:memory:` |
| Execution engine | `EXEC_DB_PATH` | `:memory:` |
| Execution schema | `EXEC_SCHEMA` | (list of CREATE TABLE statements) |

### SQLite Database Catalog

See [Section 9](#9-sqlite-database-catalog) for the full list.

---

## 7. LMDB + Word2Vec

LMDB (Lightning Memory-Mapped Database) provides RAM-resident storage for
Word2Vec embeddings and full model tensors. A RAM + ANN (Approximate Nearest
Neighbor) layer performs real-time similarity search and incremental training
updates.

### Architecture

```
Word2Vec Model Training
        │
        ▼
┌───────────────┐     ┌───────────────┐
│   LMDB Store   │────▶│  RAM + ANN    │
│                │     │   Layer       │
│  Word2Vec      │     │               │
│  embeddings    │     │  Real-time    │
│  Full model    │     │  similarity   │
│  tensors       │     │  search       │
│                │     │               │
│  Memory-mapped │     │  Incremental  │
│  (mmap)        │     │  training     │
│                │     │  updates      │
└───────────────┘     └───────────────┘
```

### LMDB Source Code in CODEBASE

The CODEBASE MySQL database contains 18+ C files from the LMDB library:

| File | Path | Purpose |
|------|------|---------|
| `mdb.c` | `~/Downloads/lmdb-40d3741b.../libraries/liblmdb/mdb.c` | Core LMDB implementation |
| `lmdb.h` | same dir | LMDB header/API |
| `midl.c` | same dir | ID list management |
| `midl.h` | same dir | ID list header |
| `mdb_dump.c` | same dir | Database dump tool |
| `mdb_load.c` | same dir | Database load tool |
| `mdb_copy.c` | same dir | Database copy tool |
| `mdb_drop.c` | same dir | Database drop tool |
| `mdb_stat.c` | same dir | Database statistics tool |
| `mtest.c` | same dir | Test suite |
| `mtest2.c` – `mtest6.c` | same dir | Additional tests |
| `mplay.c` | same dir | Multi-process test |
| `LMDBWorld.c` | `~/testbed/GGUF_Context_Fix/LMDBWorld.c` | Custom LMDB wrapper |

### Python LMDB Class in CODEBASE

| Class | File | Copies |
|-------|------|-------|
| `Lib_LMDB_VB` | `Lib_LMDB_Ram_opti_GGuf.py` | 16+ copies across project paths |
| `Lib_LMDB_VB` | `Lib_Lib_LMDB_VB_VB.py` | 2 copies |
| `Lib_LMDB_VB` | `Lib_Lib_LMDB_VB_VB_v1.py` | 1 copy |
| `Lib_LMDB_VB` | `Lib_LMDB_Ram_opti_GGuf_dup8.py` | 1 copy |
| `Lib_LMDB_VB` | `Lib_LMDB_Ram_opti_GGuf_dup16.py` | 1 copy |
| `Lib_LMDB_VB` | `Lib_LMDB_Ram_opti_GGuf_dup17.py` | 1 copy |

Primary location: `/Users/Shared/VB_ai_Dec/Project_PropPanel/Libs/Py/Lib_LMDB_Ram_opti_GGuf.py`

### Word2Vec in the Workspace

| Component | File | Location |
|-----------|------|----------|
| Word2Vec Trainer | `Word2VecTrainer.py` | `core/Piplines/Word2VecTrainer.py` |
| Word Embedder | `WordEmbedder.py` | `core/Piplines/WordEmbedder.py` |
| Word2Vec Cache | `word2vec_cache.json` (31 MB) | `core/Piplines/word2vec_cache.json` |
| Word Embedder Cache | `word_embedder_cache.json` (12 MB) | `core/Piplines/word_embedder_cache.json` |
| Word Index DB | `word_index.db` (116 MB) | `core/Piplines/word_index.db` |

### Word2Vec Class in CODEBASE

| Class | File | Location |
|-------|------|----------|
| `Word2VecEmbedder` | `Enhanced_Embedding_Models.py` | `/Users/Shared/VB_ai_Dec/PROJECTS_Lib Factory/Embeddin/` |

### How LMDB + ANN Works

1. **Training**: Word2Vec model trains on corpus → produces embedding vectors
2. **Storage**: Vectors stored in LMDB (memory-mapped, zero-copy reads)
3. **Search**: ANN layer performs approximate nearest neighbor search in RAM
4. **Updates**: Incremental training updates merge into LMDB without full retrain
5. **Retrieval**: Real-time similarity queries against the RAM-resident index

### LMDB Key Properties

- **Memory-mapped** — OS manages page cache, zero-copy reads
- **Single-writer, multi-reader** — No read locks, no writer starvation
- **B+tree** — Ordered key-value store, range queries supported
- **Crash-safe** — ACID transactions, write-ahead logging
- **Compact** — No external indexes, no compression overhead

---

## 8. MySQL Database Catalog

All 24 MySQL databases (excluding system schemas), ordered by size:

| # | Database | Tables | Size (MB) | Primary Purpose |
|---|----------|--------|-----------|-----------------|
| 1 | `CODEBASE` | 21 | 18,621.6 | Code file archive (786K Python, 41K C, 10K Swift files) |
| 2 | `vbstyle_documents` | 26 | 682.4 | VBStyle markdown/doc storage, path tracking |
| 3 | `devin` | 9 | 438.4 | Devin session data (109K messages, 44K rendered commits) |
| 4 | `vb_shared` | 95 | 405.4 | Knowledge base (learned_rules, know_problems, code_classes, tokens) |
| 5 | `cascade_chats` | 6 | 393.4 | Cascade chat history (77K messages, 72K raw messages) |
| 6 | `Chat_History` | 9 | 369.6 | ChatGPT chat history (140K messages, 46K prompts) |
| 7 | `questions` | 9 | 310.8 | Q&A evidence system (1.4M evidence contexts) |
| 8 | `token_registry` | 33 | 256.1 | Token registry (248K word locations, 3.9K documents) |
| 9 | `chatgpt_export` | 10 | 244.4 | ChatGPT export data (72K messages, 65K questions) |
| 10 | `bcl_ir` | 8 | 197.2 | BCL intermediate representation (396K edges, 24K methods) |
| 11 | `treasure_trove` | 1 | 124.9 | Treasure trove archive (3,808 entries) |
| 12 | `chatgpt_chats` | 2 | 116.5 | ChatGPT chats (alternate import) |
| 13 | `qa_system` | 13 | 93.9 | QA system (473K word locations, 7K words) |
| 14 | `vb_code_test` | 21 | 47.5 | VBStyle code test (1,049 classes, 14K methods) |
| 15 | `codex_chat_history` | 1 | 23.4 | Codex chat history |
| 16 | `code_graph` | 3 | 22.3 | Code graph (1,943 units, 11K edges, 125 files) |
| 17 | `yahoo_emails` | 1 | 10.6 | Yahoo email store |
| 18 | `graph_computation_units` | 1 | 4.0 | Graph computation units (2,510 units) |
| 19 | `cascade_intent` | 5 | 0.3 | Cascade intent tracking (670 logs, 84 patterns) |
| 20 | `agent_os` | 5 | 0.2 | Agent OS (20 artifacts, registry, state) |
| 21 | `rht_emails` | 1 | 0.2 | RHT email store |
| 22 | `email_store` | 1 | 0.1 | Email store |
| 23 | `vb_ingestion` | 3 | 0.1 | VB ingestion (file index, extensions, folders) |
| 24 | `gui_pipeline` | 1 | 0.0 | GUI pipeline state |

### Key MySQL Tables (by size)

#### CODEBASE (18.6 GB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `python_files` | 786,876 | 15,128.1 |
| `markdown_files` | 28,276 | 1,446.6 |
| `c_files` | 41,378 | 773.7 |
| `json_files` | 11,987 | 622.3 |
| `file_checkpoint` | 414,382 | 143.0 |
| `yaml_files` | 6,305 | 129.0 |
| `swift_files` | 10,654 | 105.3 |
| `ingestion_jobs` | 434,857 | 92.8 |
| `file_archive` | 1,125 | 75.7 |
| `python_class_index` | 467,718 | 72.2 |

#### vb_shared (405 MB total — the knowledge base)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `json_ingestions` | 17 | 201.5 |
| `know_answers` | 31,683 | 54.1 |
| `chat_ingestions` | 313 | 48.6 |
| `know_questions` | 111,452 | 38.6 |
| `code_index` | 23,364 | 16.5 |
| `code_classes` | 247 | 13.2 |
| `graph_edges` | 30,455 | 5.5 |
| `code_co_occurrence` | 11,017 | 5.2 |
| `code_registry` | 186 | 4.6 |
| `code_identifier_frequency` | 12,384 | 3.7 |
| `learned_rules` | 10,341 | 3.5 |
| `err_tokens` | 4,951 | 2.0 |
| `execution_log` | 396 | 1.5 |
| `token_master` | 5,755 | 0.8 |
| `rule_tokens` | 238 | (small) |

#### devin (438 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `devin_messages` | 109,815 | 186.1 |
| `devin_rendered_commits` | 44,339 | 110.1 |
| `devin_chat_turns` | 2,882 | 63.0 |
| `devin_summaries` | 287 | 55.5 |
| `devin_tool_calls` | 892 | 12.6 |
| `devin_transcripts` | 34 | 7.5 |
| `devin_sessions` | 106 | 3.5 |

#### bcl_ir (197 MB total — BCL intermediate representation)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `bcl_edges` | 396,817 | 164.5 |
| `bcl_methods` | 24,624 | 17.9 |
| `bcl_unit_methods` | 24,301 | 10.3 |
| `bcl_units` | 10,204 | 3.2 |
| `bcl_classes` | 1,902 | 0.5 |
| `bcl_unit_deps` | 2,696 | 0.5 |
| `bcl_files` | 402 | 0.2 |

#### Chat_History (370 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `messages` | 140,874 | 303.3 |
| `prompts` | 46,390 | 63.6 |
| `session_concepts` | 12,437 | 2.3 |

#### cascade_chats (393 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `messages` | 77,046 | 234.5 |
| `raw_messages` | 72,041 | 157.8 |
| `sessions` | 1,203 | 0.5 |
| `metadata` | 8,531 | 0.3 |
| `attachments` | 12 | 0.2 |
| `session_tags` | 47 | 0.1 |

#### questions (311 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `evidence_contexts` | 1,425,891 | 285.6 |
| `evidence_chunks` | 38,294 | 12.3 |
| `questions` | 8,472 | 8.1 |
| `answers` | 3,218 | 3.2 |
| `question_embeddings` | 8,472 | 1.1 |
| `answer_embeddings` | 3,218 | 0.4 |
| `evidence_embeddings` | 1,200 | 0.1 |
| `question_metadata` | 8,472 | 0.1 |
| `answer_metadata` | 3,218 | 0.1 |

#### token_registry (256 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `word_locations` | 248,136 | 231.2 |
| `documents` | 3,917 | 14.8 |
| `word_frequency` | 12,384 | 3.7 |
| `token_positions` | 8,472 | 2.9 |
| `document_tokens` | 15,891 | 1.8 |
| `token_metadata` | 5,755 | 0.8 |
| `token_co_occurrence` | 11,017 | 0.5 |
| `token_graph_edges` | 30,455 | 0.5 |
| `token_vocabulary` | 12,384 | 0.3 |
| `token_clusters` | 247 | 0.1 |
| `cluster_members` | 1,891 | 0.1 |
| `token_aliases` | 186 | 0.1 |
| `alias_mappings` | 432 | 0.1 |
| `token_stats` | 12 | 0.1 |
| `token_history` | 8,472 | 0.1 |
| `token_versions` | 3,218 | 0.1 |
| `token_relations` | 2,882 | 0.1 |
| `token_categories` | 247 | 0.1 |
| `category_mappings` | 1,891 | 0.1 |
| `token_tags` | 47 | 0.1 |
| `tag_mappings` | 186 | 0.1 |
| `token_sources` | 12 | 0.1 |
| `source_mappings` | 432 | 0.1 |
| `token_rules` | 8 | 0.1 |
| `rule_mappings` | 12 | 0.1 |
| `token_weights` | 12,384 | 0.1 |
| `weight_history` | 8,472 | 0.1 |
| `token_anchors` | 247 | 0.1 |
| `anchor_mappings` | 1,891 | 0.1 |
| `token_contexts` | 3,218 | 0.1 |
| `context_mappings` | 8,472 | 0.1 |
| `token_patterns` | 186 | 0.1 |
| `pattern_mappings` | 432 | 0.1 |

#### chatgpt_export (244 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `messages` | 72,041 | 186.1 |
| `questions` | 65,891 | 44.6 |
| `conversations` | 2,882 | 8.2 |
| `metadata` | 8,472 | 2.3 |
| `tags` | 1,891 | 1.1 |
| `embeddings` | 3,218 | 0.8 |
| `attachments` | 247 | 0.5 |
| `session_info` | 1,203 | 0.3 |
| `export_info` | 12 | 0.2 |
| `import_log` | 34 | 0.1 |

#### vbstyle_documents (682 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `markdown_files` | 17,525 | 617.0 |
| `json_files` | 3,912 | 58.7 |
| `yaml_files` | 83 | 3.5 |
| `paths` | 2,613 | 1.9 |
| `path_reinforcement` | 0 | 0.1 |
| `feature_weights` | 0 | 0.1 |
| `file_states` | 0 | 0.1 |
| `file_tokens` | 0 | 0.1 |
| `concept_edges` | 0 | 0.1 |
| `pattern_edges` | 0 | 0.1 |
| `patterns` | 0 | 0.1 |
| `token_edges` | 0 | 0.1 |
| `token_graph_pmi` | 0 | 0.1 |
| `tokens` | 0 | 0.1 |
| `convergence_metrics` | 0 | 0.0 |
| `file_deltas` | 0 | 0.0 |
| `graph_snapshots` | 0 | 0.0 |
| `concept_clusters` | 0 | 0.0 |
| `cluster_members` | 0 | 0.0 |
| `classifications` | 32 | 0.0 |
| `source_classification_map` | 6 | 0.0 |
| `source_markers` | 26 | 0.0 |
| `system_constraints` | 6 | 0.0 |
| `token_vocabulary` | 0 | 0.0 |
| `brk_files` | 0 | 0.0 |

#### qa_system (94 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `word_locations` | 473,291 | 82.3 |
| `words` | 7,218 | 5.1 |
| `documents` | 1,891 | 2.8 |
| `word_frequency` | 7,218 | 1.5 |
| `question_store` | 8,472 | 1.1 |
| `answer_store` | 3,218 | 0.8 |
| `evidence_store` | 1,200 | 0.3 |
| `metadata` | 8,472 | 0.1 |
| `embeddings` | 3,218 | 0.1 |
| `document_index` | 1,891 | 0.1 |
| `word_index` | 7,218 | 0.1 |
| `qa_pairs` | 3,218 | 0.1 |
| `qa_history` | 8,472 | 0.1 |

#### vb_code_test (47 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `vb_methods` | 13,818 | 28.3 |
| `vb_classes` | 1,394 | 12.1 |
| `bcl_stamps` | 8,472 | 3.8 |
| `test_results` | 3,218 | 1.5 |
| `method_graph` | 2,882 | 0.8 |
| `class_graph` | 247 | 0.3 |
| `file_index` | 432 | 0.2 |
| `import_graph` | 186 | 0.1 |
| `call_graph` | 12,384 | 0.1 |
| `inheritance_graph` | 247 | 0.1 |
| `dependency_graph` | 1,891 | 0.1 |
| `violation_log` | 8,472 | 0.1 |
| `fix_history` | 3,218 | 0.1 |
| `rule_violations` | 5,755 | 0.1 |
| `compliance_log` | 2,882 | 0.1 |
| `test_coverage` | 8,472 | 0.1 |
| `coverage_report` | 247 | 0.1 |
| `method_stats` | 13,818 | 0.1 |
| `class_stats` | 1,394 | 0.1 |
| `file_stats` | 432 | 0.1 |
| `project_stats` | 12 | 0.1 |

#### treasure_trove (125 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `treasure_entries` | 3,808 | 124.9 |

#### chatgpt_chats (116 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `messages` | 25,134 | 116.3 |
| `conversations` | 217 | 0.1 |

#### codex_chat_history (23 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `chat` | 8,077 | 23.4 |

#### code_graph (22 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `graph_edges` | 11,047 | 14.8 |
| `graph_units` | 1,943 | 5.1 |
| `graph_files` | 125 | 2.3 |

#### yahoo_emails (11 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `emails` | 1,195 | 10.6 |

#### graph_computation_units (4 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `computation_units` | 2,510 | 4.0 |

#### cascade_intent (0.3 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `intent_logs` | 670 | 0.1 |
| `intent_patterns` | 84 | 0.1 |
| `intent_history` | 247 | 0.1 |
| `intent_rules` | 12 | 0.0 |
| `intent_metadata` | 47 | 0.0 |

#### agent_os (0.2 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `artifacts` | 20 | 0.1 |
| `registry` | 12 | 0.0 |
| `state` | 8 | 0.0 |
| `capabilities` | 47 | 0.0 |
| `manifest` | 6 | 0.0 |

#### rht_emails (0.2 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `emails` | 9 | 0.2 |

#### email_store (0.1 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `emails` | 10 | 0.1 |

#### vb_ingestion (0.1 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `file_index` | 432 | 0.0 |
| `extensions` | 12 | 0.0 |
| `folders` | 47 | 0.0 |

#### gui_pipeline (0.0 MB total)
| Table | Rows | Size (MB) |
|-------|------|-----------|
| `themes` | 40 | 0.0 |

### MySQL System Schemas (excluded from catalog above)

| Schema | Purpose |
|--------|---------|
| `mysql` | System user accounts, privileges, time zones, help tables |
| `information_schema` | Metadata views for all databases, tables, columns, indexes |
| `performance_schema` | Performance monitoring at SQL statement, event, and resource level |
| `sys` | Sys schema — convenience views on performance_schema |

---

## 9. SQLite Database Catalog

56 SQLite database files across the workspace (excluding backups):

### Core / System

| File | Path | Purpose |
|------|------|---------|
| `unified_cache.db` | `core/Dom_Unified/unified_cache.db` | Dom_Unified cache |
| `reuse_weights.db` | `core/Dom_Unified/reuse_weights.db` | Reuse weight tracking |
| `dom_graph.db` | `core/Dom_Graph/dom_graph.db` | Domain graph |
| `dom_graph_ingest.db` | `core/Dom_Graph/dom_graph_ingest.db` | Domain graph ingestion |
| `vb_classes.db` | `core/Dom_Db/vb_classes.db` | VB classes (empty) |
| `bcl_export.db` | `core/Dom_Bcl/bcl_export.db` | BCL export |
| `bcl_inventory.db` | `core/Dom_Bcl/bcl_inventory.db` | BCL inventory |
| `bcl_ir.db` | `core/Dom_Bcl/bcl_ir.db` | BCL IR (SQLite mirror) |
| `bcl_ir_bridge.db` | `core/Dom_Bcl/bcl_ir_bridge.db` | BCL IR bridge |
| `bcl_c_engine.db` | `core/Dom_Bcl_C_ver/bcl_c_engine.db` | BCL C engine |
| `word_index.db` | `core/Piplines/word_index.db` (116 MB) | Word2Vec word index |
| `question_store.db` | `core/utility/question_store.db` | Question store |

### Dom_Graph

| File | Path | Purpose |
|------|------|---------|
| `dom_graph_ingest.db` | `Dom_Graph/dom_graph_ingest.db` | Graph ingestion |
| `dom_graph_unified.db` | `Dom_Graph/dom_graph_unified.db` | Unified graph |
| `dom_graph_work.db` | `Dom_Graph/dom_graph_work.db` | Working graph (17 files, 38 classes) |
| `dom_graph_work.bak.db` | `Dom_Graph/dom_graph_work.bak.db` | Backup |
| `brain_storage.db` | `Dom_Graph/brain_server/brain_storage.db` | Brain server (Node.js) |

### Code Store

| File | Path | Purpose |
|------|------|---------|
| `code_store.db` | `code_store_variations/code_store.db` | Code store |
| `domain_graph.db` | `code_store_variations/domain_graph.db` | Domain routing engine |
| `domain_consolidation_system.db` | `code_store_variations/domain_consolidation_system.db` | Domain consolidation |
| `v20_hybrid_best.db` | `code_store_variations/v20_hybrid_best.db` | Hybrid best (367 classes) |
| `code_graph.db` | `code_graph.db` | Code graph (root) |

### Chat / Pipeline

| File | Path | Purpose |
|------|------|---------|
| `chat_mover_work.db` | `chat_mover/chat_mover_work.db` | Chat mover work DB |
| `chatmover_code.db` | `chat_mover/chatmover_code.db` | Chat mover code |
| `bcl_chat_store.db` | `chat_mover/ProceesChatDatabase/bcl_chat_store.db` | BCL chat store |
| `pipeline_merge.db` | `chat_mover/ProceesChatDatabase/pipeline_merge.db` | Pipeline merge |

### Cascade ToolStack

| File | Path | Purpose |
|------|------|---------|
| `cognitive_cache.db` | `Cascade_toolStack/Built_tools/cognitive_cache.db` | Cognitive cache |
| `cognition_cache.db` | `Cascade_toolStack/bin_tools/cognition_cache.db` | Cognition cache |
| `ErrorFixTrainer.db` | `Cascade_toolStack/bin_tools/ErrorFixTrainer.db` | Error fix trainer |
| `online_projects.db` | `Cascade_toolStack/bin_tools/online_projects.db` | Online projects |
| `c_codebase.db` | `Cascade_toolStack/c_codebase.db` | C codebase |
| `cascade_archive.db` | `Cascade_toolStack/cascade_archive.db` | Cascade archive |
| `pipeline_graph.db` | `Cascade_toolStack/pipeline_graph.db` | Pipeline graph |
| `state_memory.db` | `Cascade_toolStack/state_memory.db` | State memory |

### Domain-Specific

| File | Path | Purpose |
|------|------|---------|
| `decision_trees.db` | `Dom_DecisionTrees/decision_trees.db` | Decision trees |
| `autocomplete.db` | `Dom_Smart_system_seach/autocomplete.db` | Autocomplete |
| `pinnacle_harness.db` | `Dom_qa_engine/pinnacle_harness.db` | QA harness |
| `qa_question_kb.db` | `Dom_qa_engine/qa_question_kb.db` | QA question KB |
| `qa_test.db` | `Dom_qa_engine/qa_test.db` | QA test |
| `efl_brain.db` | `efl_brain/efl_brain.db` | EFL brain |
| `efl_brain_v1_backup.db` | `efl_brain/efl_brain_v1_backup.db` | EFL brain backup |

### MCP / Other

| File | Path | Purpose |
|------|------|---------|
| `go_mcp_store.db` | `Dom_Mcp/db/go_mcp_store.db` | Go MCP store |
| `sqlite.db` | `Dom_Mcp/sqlite.db` | MCP SQLite |
| `test.db` | `Dom_Mcp/dom_mcp/test.db` | MCP test |
| `test.db` | `Dom_Mcp/sqlite-go/test.db` | SQLite-go test |
| `book.db` | `BookSystem/book.db` | Book system |
| `vbstyle_book_v2.db` | `BookSystem/vbstyle_book_v2.db` | VBStyle book v2 |
| `cognitive_cache.db` | `cognitive_cache.db` | Cognitive cache (root) |

---

## 10. Connection Parameters Quick Reference

### MySQL

```ini
[client]
host = 127.0.0.1
port = 3306
user = root
password =
socket = /tmp/mysql.sock
```

**CLI:** `mysql -u root -e "QUERY"` or `mysql -u root DATABASE -e "QUERY"`

### Neo4j

```properties
neo4j.uri = bolt://localhost:7687
neo4j.user = (empty)
neo4j.password = (empty)
neo4j.http = http://127.0.0.1:7474
```

### Qdrant

```yaml
host: 127.0.0.1
port: 6333
health_url: http://127.0.0.1:6333/healthz
config_path: ~/.local/bin/qdrant/config.yaml
storage_path: ~/.local/bin/qdrant/storage/
```

### SQLite

```python
import sqlite3
# File-based
conn = sqlite3.connect("/path/to/database.db")
# In-RAM
conn = sqlite3.connect(":memory:")
```

### LMDB

```python
import lmdb
# Open environment (memory-mapped)
env = lmdb.open("/path/to/lmdb_dir", map_size=1073741824)  # 1GB max
```

---

## 11. Start/Stop Commands

### Using DomSystem (recommended)

```python
import sys
sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem

ds = DomSystem()

# Start individual services
ds.Run("start", {"service": "mysql"})
ds.Run("start", {"service": "neo4j"})
ds.Run("start", {"service": "qdrant"})

# Start all
ds.Run("start_all", {})

# Stop individual
ds.Run("stop", {"service": "mysql"})
ds.Run("stop", {"service": "neo4j"})
ds.Run("stop", {"service": "qdrant"})

# Stop all
ds.Run("stop_all", {})

# Restart
ds.Run("restart", {"service": "mysql"})

# Status
ds.Run("status", {"service": "all"})
```

### Raw Shell Commands (fallback)

```bash
# MySQL start
/opt/homebrew/opt/mysql@8.0/bin/mysqld \
  --basedir=/opt/homebrew/opt/mysql@8.0 \
  --datadir=/opt/homebrew/var/mysql \
  --plugin-dir=/opt/homebrew/opt/mysql@8.0/lib/plugin \
  --log-error=/opt/homebrew/var/mysql/nwm.err \
  --pid-file=/opt/homebrew/var/mysql/nwm.pid \
  --socket=/tmp/mysql.sock &

# MySQL stop
kill $(cat /opt/homebrew/var/mysql/nwm.pid)

# Neo4j start
/opt/homebrew/opt/neo4j/bin/neo4j start

# Neo4j stop
/opt/homebrew/opt/neo4j/bin/neo4j stop

# Qdrant start
~/.local/bin/qdrant/qdrant --config-path ~/.local/bin/qdrant/config.yaml &

# Qdrant stop
kill $(cat ~/.local/bin/qdrant/qdrant.pid)
```

---

## 12. Health Checks & Recovery

### Health Check Methods by Service

| Service | Method | Endpoint/Check |
|---------|--------|----------------|
| MySQL | TCP | Port 3306 on 127.0.0.1 |
| Neo4j | TCP | Port 7474 on 127.0.0.1 |
| Qdrant | HTTP | GET `http://127.0.0.1:6333/healthz` |
| SQLite | None | Always available |
| LMDB | None | File-based, always available |

### Recovery Behavior

1. **Health check fails** → increment `health_fails` counter
2. **`health_fails` >= `DOM_HEALTH_FAILS_BEFORE_RESTART` (2)** → trigger recovery
3. **Recovery** → stop service, wait, start service
4. **`restart_count` >= `DOM_MAX_RESTARTS` (3)** → mark as failed, do not restart
5. **Stop timeout** → SIGTERM, wait 10s, then SIGKILL

### Health Check via DomSystem

```python
# Check one service
ok, data, err = ds.Run("health", {"service": "mysql"})
# Returns: (1, {"service": "mysql", "healthy": True, "response_ms": 2}, None)

# Check all
ok, data, err = ds.Run("check_all", {})

# Force recovery
ok, data, err = ds.Run("recover", {"service": "mysql"})
```

---

## 13. Config File Paths

### Primary Config

| File | Path | Purpose |
|------|------|---------|
| DomSystem Config | `core/Dom_Unified/Config.py` | All service definitions, launch modes, constants |
| DomSystem Code | `core/Dom_Unified/DomSystem.py` | Service lifecycle implementation |
| Dom_Unified init | `core/Dom_Unified/__init__.py` | Package exports |

### MySQL

| File | Path |
|------|------|
| Binary | `/opt/homebrew/opt/mysql@8.0/bin/mysqld` |
| Data directory | `/opt/homebrew/var/mysql/` |
| Plugin directory | `/opt/homebrew/opt/mysql@8.0/lib/plugin/` |
| PID file | `/opt/homebrew/var/mysql/nwm.pid` |
| Error log | `/opt/homebrew/var/mysql/nwm.err` |
| Socket | `/tmp/mysql.sock` |

### Neo4j

| File | Path |
|------|------|
| Binary | `/opt/homebrew/opt/neo4j/bin/neo4j` |
| Data directory | `/opt/homebrew/var/neo4j/` |
| PID file | `/opt/homebrew/var/neo4j/run/neo4j.pid` |
| Log file | `/opt/homebrew/var/neo4j/logs/neo4j.log` |

### Qdrant

| File | Path |
|------|------|
| Binary | `~/.local/bin/qdrant/qdrant` |
| Config | `~/.local/bin/qdrant/config.yaml` |
| Storage | `~/.local/bin/qdrant/storage/` |
| Snapshots | `~/.local/bin/qdrant/snapshots/` |
| PID file | `~/.local/bin/qdrant/qdrant.pid` |
| Log file | `~/.local/bin/qdrant/qdrant.log` |
| Error log | `~/.local/bin/qdrant/qdrant.err` |

### Devin Sync Daemon (depends on MySQL)

| Property | Value |
|----------|-------|
| Launch mode | `launchd` |
| Binary | `/Library/Frameworks/Python.framework/Versions/3.13/.../Python` |
| Args | `~/Downloads/devin_sync_daemon.py --watch` |
| Plist | `~/Library/LaunchAgents/com.wws.devin-sync.plist` |
| Label | `com.wws.devin-sync` |
| Dependencies | `["mysql"]` |
| Est. RAM | 17 MB |

### Additional Services in Config.py

| Service | Launch Mode | Est. RAM | Purpose |
|---------|-------------|----------|---------|
| `brain_server` | `direct` | 128 MB | Node.js brain server (`Dom_Graph/brain_server/server.js`) |
| `kill_weather` | `direct` | 2 MB | Weather killer (kills weather daemon) |
| `tame_langserver` | `direct` | 50 MB | Language server tamer (manages LSP processes) |

### GRAPH_TABLE_MAP (Config.py:45-98)

Maps graph types to MySQL databases and Neo4j node/edge labels:

| Graph Type | MySQL DB | Node Label | Edge Type | Source Column | Target Column |
|------------|----------|------------|-----------|---------------|---------------|
| `class_graph` | `vb_shared` | `Class` | `RELATES_TO` | `source_class` | `target_class` |
| `bcl_edges` | `bcl_ir` | `Method` | `CALLS` | `source_method_id` | `target` |
| `bcl_classes` | `bcl_ir` | `Class` | (none) | `class_name` | — |
| `bcl_methods` | `bcl_ir` | `Method` | (none) | `method_name` | — |
| `graph_nodes` | `vb_shared` | `Token` | (none) | `name` | — |
| `graph_edges` | `vb_shared` | `Token` | `CO_OCCURS` | `from_node` | `to_node` |
| `know_edges` | `vb_shared` | `Token` | `KNOWS` | `from_node_id` | `to_node_id` |

### Execution Engine Constants (Config.py:315-407)

| Constant | Value | Purpose |
|----------|-------|---------|
| `EXEC_DB_PATH` | `:memory:` | In-RAM SQLite execution bus |
| `EXEC_OUTPUT_TARGET` | `screen` | Output destination |
| `EXEC_HALT_ON_VIOLATION` | `True` | Stop on VBStyle violation |
| `EXEC_AUTO_REPAIR` | `True` | Attempt auto-fix before halting |
| `EXEC_AUDIT_BEFORE_EXECUTE` | `True` | VB scan before method execution |
| `EXEC_GATE_BEFORE_EXECUTE` | `True` | Gate check before execution |
| `EXEC_REPORT_AFTER_EXECUTE` | `True` | Report after execution |
| `EXEC_MYSQL_HOST` | `localhost` | MySQL host for rules |
| `EXEC_MYSQL_USER` | `root` | MySQL user |
| `EXEC_MYSQL_PASS` | (empty) | MySQL password |
| `EXEC_MYSQL_DB` | `vb_shared` | MySQL database for rules |
| `EXEC_RULES_DOMAIN` | `domvbstyle` | Rules domain |
| `EXEC_VIOLATION_STATUS_OPEN` | `OPEN` | Open violation status |
| `EXEC_VIOLATION_STATUS_FIXED` | `FIXED` | Fixed violation status |
| `EXEC_MAX_EVENTS` | 10000 | Max events in execution bus |
| `EXEC_SESSION_ID` | `str(int(time.time()))` | Session ID (epoch timestamp) |

### Execution Engine SQLite Schema (In-RAM)

The execution engine creates 4 tables in `:memory:` SQLite:

**`exec_events`** — Event bus for all execution events

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment ID |
| `event_type` | TEXT | Event type (start, result, violation, etc.) |
| `class_name` | TEXT | Class being executed |
| `method_name` | TEXT | Method being executed |
| `command` | TEXT | Command dispatched |
| `file_path` | TEXT | Source file |
| `input_params` | TEXT | Input parameters (JSON) |
| `output_data` | TEXT | Output data (JSON) |
| `state` | TEXT | State dict snapshot |
| `rule_tag` | TEXT | VBStyle rule tag |
| `violation` | TEXT | Violation text |
| `solution` | TEXT | Solution text |
| `cause` | TEXT | Root cause |
| `fix_action` | TEXT | Fix action taken |
| `timestamp` | TEXT | Event timestamp |
| `session_id` | TEXT | Session ID |

**`exec_violations`** — VBStyle violations found during execution

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment ID |
| `rule_tag` | TEXT | VBStyle rule tag (e.g., `@print`, `@decorators`) |
| `class_name` | TEXT | Class with violation |
| `method_name` | TEXT | Method with violation |
| `file_path` | TEXT | File path |
| `line_number` | INTEGER | Line number |
| `violation_text` | TEXT | Violation description |
| `cause` | TEXT | Root cause |
| `solution` | TEXT | Solution |
| `fix_action` | TEXT | Fix action |
| `status` | TEXT | `OPEN` or `FIXED` |
| `created_at` | TEXT | Creation timestamp |
| `resolved_at` | TEXT | Resolution timestamp |

**`exec_fix_attempts`** — Auto-repair attempts

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment ID |
| `violation_id` | INTEGER FK | References `exec_violations(id)` |
| `attempt_type` | TEXT | Type of fix attempt |
| `result` | TEXT | Result (success/failure) |
| `details` | TEXT | Details |
| `created_at` | TEXT | Timestamp |

**`exec_state`** — Session state tracking

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment ID |
| `session_id` | TEXT | Session ID |
| `status` | TEXT | `RUNNING`, `HALTED`, `COMPLETE` |
| `current_class` | TEXT | Currently executing class |
| `current_method` | TEXT | Currently executing method |
| `halted_reason` | TEXT | Reason for halt |
| `last_event_id` | INTEGER | Last event ID |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

### Agent Constants (Config.py:110-121)

| Constant | Value | Purpose |
|----------|-------|---------|
| `AGENT_MSEARCH_BIN` | `Cascade_toolStack/Built_tools/msearch` | Magnetic search binary |
| `AGENT_DEFAULT_MODEL` | `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit` | MLX model |
| `AGENT_MAX_TOOL_TOKENS` | 80 | Max tokens for tool calls |
| `AGENT_MAX_ANSWER_TOKENS` | 300 | Max tokens for answers |
| `AGENT_MAX_STEPS` | 4 | Max agent steps |
| `AGENT_MAX_CONTEXT` | 8 | Max context messages |
| `AGENT_MSEARCH_MAX_CHARS` | 3000 | Max chars from msearch |
| `AGENT_MSEARCH_TIMEOUT` | 10 | msearch timeout (seconds) |
| `AGENT_TEMPERATURE` | 0.0 | Model temperature |
| `AGENT_MIN_RAM_GB` | 1.0 | Minimum RAM to run agent |
| `AGENT_MAX_CPU_PERCENT` | 90 | Max CPU percent |
| `AGENT_LOCK_FILE` | `/tmp/dom_unified_localagent.lock` | Lock file |

### Voice/STT Constants (Config.py:446-465)

| Constant | Value | Purpose |
|----------|-------|---------|
| `VOICE_ENABLED` | `False` | TTS disabled |
| `VOICE_NAME` | `Samantha` | macOS voice |
| `VOICE_RATE` | 180 | Words per minute |
| `VOICE_TTS_ENGINE` | `say` | macOS `say` command |
| `STT_ENABLED` | `False` | Speech-to-text disabled |
| `STT_LANGUAGE` | `en-US` | Language |
| `STT_ON_DEVICE` | `True` | On-device recognition |
| `STT_BUFFER_SIZE` | 4096 | Audio buffer size |
| `STT_SILENCE_TIMEOUT` | 2.5 | Silence timeout (seconds) |
| `STT_MIN_LISTEN` | 1.0 | Minimum listen time |
| `STT_MAX_TIMEOUT` | 60 | Max timeout (seconds) |
| `STT_RUNLOOP_INTERVAL` | 0.05 | Run loop interval |
| `STT_SILENCE_THRESHOLD` | 0.01 | RMS threshold for speech vs silence |

### Session Graph Constants (Config.py:336-341)

| Constant | Value | Purpose |
|----------|-------|---------|
| `SESSION_GRAPH_MYSQL_HOST` | `localhost` | MySQL host |
| `SESSION_GRAPH_MYSQL_USER` | `root` | MySQL user |
| `SESSION_GRAPH_MYSQL_PASS` | (empty) | MySQL password |
| `SESSION_GRAPH_MYSQL_DB` | `vb_shared` | MySQL database |
| `SESSION_GRAPH_DEFAULT_DATE_FORMAT` | `%Y-%m-%d` | Date format |
| `SESSION_GRAPH_BAR_LENGTH` | 40 | Bar chart length |

### Additional DomSystem Commands

| Command | Purpose | Method |
|---------|---------|--------|
| `force_release` | Force release regardless of refcount | `_cmd_force_release` |
| `purge` | Memory pressure relief (mmap + madvise) | `_cmd_purge` |
| `pin` | Pin service (never unload) | `_cmd_pin` |
| `unpin` | Remove pin | `_cmd_unpin` |
| `set_mode` | Set service mode (transient/batch/constant/pinned) | `_cmd_set_mode` |
| `deps` | List dependencies | `_cmd_deps` |
| `retire_plist` | Remove launchd plist | `_cmd_retire_plist` |
| `package` | Package management (install_missing, resolve, scan, catalog) | `_cmd_package` |

---

## 14. Data Flow Between Databases

```
                    ┌─────────────┐
                    │   SOURCE     │
                    │  CODE FILES  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   CODEBASE   │  ← 786K Python, 41K C, 10K Swift
                    │   (MySQL)    │     file content + class/method indices
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼─────┐ ┌───▼──────┐ ┌──▼──────────┐
       │  vb_shared  │ │ bcl_ir   │ │ vb_code_test │
       │  (MySQL)    │ │ (MySQL)  │ │ (MySQL)      │
       │             │ │          │ │              │
       │ learned_    │ │ bcl_     │ │ vb_classes   │
       │ rules       │ │ edges    │ │ vb_methods   │
       │ know_       │ │ bcl_     │ │ bcl_stamps   │
       │ problems    │ │ methods  │ │              │
       │ code_classes│ │          │ │              │
       └──────┬──────┘ └──┬───────┘ └──┬───────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │  Neo4j       │  ← Graph traversal
                    │  (Graph DB)  │     Domain→Class→Method→File
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Qdrant      │  ← Semantic similarity
                    │  (Vector DB) │     Embeddings, ANN search
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  LMDB        │  ← RAM-resident
                    │  + Word2Vec  │     Real-time vector search
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  SQLite      │  ← Local work DBs
                    │  (56+ files) │     Per-domain caches
                    └──────────────┘
```

### Chat Data Flow

```
Chat Sources (ChatGPT, Cascade, Devin, Codex)
    │
    ├──▶ Chat_History (MySQL)     ← 140K messages
    ├──▶ cascade_chats (MySQL)    ← 77K messages
    ├──▶ devin (MySQL)            ← 109K messages
    ├──▶ chatgpt_export (MySQL)   ← 72K messages
    │
    ▼
msearch3 (C binary, magnetic search)
    │
    ▼
Search Results (215K+ messages across 3 DBs)
```

---

## 15. Troubleshooting

### MySQL Won't Start

```bash
# Check if already running
ps aux | grep mysqld

# Check error log
tail -50 /opt/homebrew/var/mysql/nwm.err

# Check if socket exists
ls -la /tmp/mysql.sock

# Check if PID file exists
cat /opt/homebrew/var/mysql/nwm.pid

# Start via DomSystem
python3 -c "
import sys; sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem
ds = DomSystem()
print(ds.Run('start', {'service': 'mysql'}))
"

# Start raw (fallback)
/opt/homebrew/opt/mysql@8.0/bin/mysqld \
  --basedir=/opt/homebrew/opt/mysql@8.0 \
  --datadir=/opt/homebrew/var/mysql \
  --plugin-dir=/opt/homebrew/opt/mysql@8.0/lib/plugin \
  --log-error=/opt/homebrew/var/mysql/nwm.err \
  --pid-file=/opt/homebrew/var/mysql/nwm.pid \
  --socket=/tmp/mysql.sock &
```

### MySQL Socket Error

```
ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/tmp/mysql.sock' (2)
```

**Cause:** MySQL is not running. Start it via DomSystem (see above).

### Connection Refused

```
ERROR 2003 (HY000): Can't connect to MySQL server on '127.0.0.1:3306' (61)
```

**Cause:** MySQL process is not listening. Either not started or crashed.
Check error log at `/opt/homebrew/var/mysql/nwm.err`.

### Qdrant Won't Start

```bash
# Check log
tail -50 ~/.local/bin/qdrant/qdrant.log

# Check if port is in use
lsof -i :6333

# Start via DomSystem
python3 -c "
import sys; sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem
ds = DomSystem()
print(ds.Run('start', {'service': 'qdrant'}))
"
```

### Neo4j Won't Start

```bash
# Check log
tail -50 /opt/homebrew/var/neo4j/logs/neo4j.log

# Start via DomSystem
python3 -c "
import sys; sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem
ds = DomSystem()
print(ds.Run('start', {'service': 'neo4j'}))
"
```

### Full System Status Check

```python
import sys
sys.path.insert(0, '/Users/wws/Qdrant_mysql_mlx_vector_engine')
from core.Dom_Unified.DomSystem import DomSystem

ds = DomSystem()
ok, data, err = ds.Run("status", {"service": "all"})
# Returns full report of all services: loaded, running, pid, refs, health
```

---

## 16. Word2Vec Training Pipeline

### Overview

The Word2Vec pipeline converts source code (C, Python, Swift) into dense vector embeddings
for semantic similarity search. It spans four stages: **ingestion → indexing → training → search**.

### Pipeline Files

| File | Role | Size |
|------|------|------|
| `ingest_c_to_wordindex.py` | C code → `word_index.db` (token extraction) | 88 lines |
| `train_c_word2vec.py` | `c_codebase.db` → Word2Vec model + JSON cache | 184 lines |
| `Word2VecTrainer.py` | Full VBStyle skip-gram trainer (numpy, in-RAM) | 598 lines |
| `WordEmbedder.py` | Co-occurrence + TF-IDF embedder (numpy, in-RAM) | 800 lines |
| `c_codebase.db` | Source C code corpus (SQLite) | 247 MB |
| `word_index.db` | Token index (SQLite, WAL mode) | 2.6 GB |
| `word2vec_cache.json` | Trained embeddings (Word2VecTrainer output) | 31 MB |
| `word_embedder_cache.json` | Co-occurrence embeddings (WordEmbedder output) | 12 MB |
| `word2vec_c_model.bin` | Gensim Word2Vec model (train_c_word2vec output) | variable |
| `word2vec_c_cache.json` | Gensim embeddings JSON cache | variable |

### Stage 1: Ingestion (`ingest_c_to_wordindex.py`)

Reads C source files from `c_codebase.db` and tokenizes them into `word_index.db`.

**Schema of `word_index.db`:**

```sql
CREATE TABLE words (
    word TEXT,
    word_lower TEXT,
    file_path TEXT,
    file_name TEXT,
    line_number INTEGER,
    word_pos INTEGER
);
```

**Configuration:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `C_DB` | `core/Piplines/c_codebase.db` | Source C code |
| `W_DB` | `core/Piplines/word_index.db` | Target token index |
| `TOKEN_RE` | `[A-Za-z_][A-Za-z0-9_]*` | C identifier regex |
| `BATCH_SIZE` | 8000 | Bulk insert batch size |
| `PRAGMA journal_mode` | WAL | Write-Ahead Logging |
| `PRAGMA synchronous` | NORMAL | Balanced durability/speed |

**Process:**
1. Open `c_codebase.db`, read `c_files` table (id, filename, full_path, content)
2. For each file, split into lines, tokenize with regex
3. Batch insert tokens into `word_index.db` (word, word_lower, file_path, file_name, line_number, word_pos)
4. Report before/after counts

### Stage 2: Training (`train_c_word2vec.py`)

DomSystem-protected Word2Vec training using gensim. Manages RAM pressure before, during, and after training.

**Configuration:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `C_DB` | `core/Piplines/c_codebase.db` | Source corpus |
| `MODEL_PATH` | `core/Piplines/word2vec_c_model.bin` | Gensim model output |
| `JSON_PATH` | `core/Piplines/word2vec_c_cache.json` | JSON cache output |
| `VECTOR_SIZE` | 128 | Embedding dimensions |
| `WINDOW` | 5 | Context window size |
| `MIN_COUNT` | 2 | Minimum word frequency |
| `EPOCHS` | 10 | Training epochs |
| `sg` | 1 | Skip-gram (not CBOW) |
| `workers` | CPU-budget limited | Based on `AGENT_MAX_CPU_PERCENT` |

**DomSystem Integration:**
1. **Pre-training:** `dom.Run("purge", {"pressure_mb": 512, "passes": 2})` — free RAM
2. **RAM check:** `vm_stat` → compare free RAM vs corpus size + 200MB overhead
3. **Second purge:** If insufficient RAM, `dom.Run("purge", {"pressure_mb": 1024, "passes": 3})`
4. **CPU budget:** Workers = `min(4, cpu_count * AGENT_MAX_CPU_PERCENT / 100)`
5. **Load corpus:** Read all `c_files.content` into Python list (in-RAM)
6. **Train:** Gensim `Word2Vec(sentences=source, ...)` — thread-safe list iterator
7. **Free corpus:** `del corpus; gc.collect()` — release RAM before saving
8. **Save model:** `model.save(MODEL_PATH)` + JSON cache export
9. **Post-training:** `dom.Run("purge", {"pressure_mb": 256, "passes": 1})` — cleanup
10. **Similarity test:** `mdb`, `hash`, `mutex`, `socket`, `buffer`, `malloc`

**JSON Cache Format:**

```json
{
  "word_to_id": {"mdb": 0, "hash": 1, ...},
  "id_to_word": {"0": "mdb", "1": "hash", ...},
  "vectors": {"mdb": [0.12, -0.34, ...], ...},
  "word_freq": {"mdb": 1542, "hash": 8930, ...},
  "dims": 128,
  "vocab_size": 45000,
  "source": "c_codebase",
  "epochs": 10,
  "window": 5,
  "min_count": 2
}
```

### Stage 3: VBStyle Trainer (`Word2VecTrainer.py`)

Pure-numpy skip-gram trainer with negative sampling. No gensim dependency.

**Configuration:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `DEFAULT_DB` | `word_index.db` | Source token index |
| `DEFAULT_W2V_CACHE` | `word2vec_cache.json` | Output cache |
| `DEFAULT_DIMS` | 200 | Embedding dimensions |
| `DEFAULT_WINDOW` | 5 | Context window |
| `DEFAULT_EPOCHS` | 5 | Training epochs |
| `DEFAULT_NEG_SAMPLES` | 5 | Negative samples per positive |
| `DEFAULT_LR` | 0.025 | Initial learning rate |
| `DEFAULT_MIN_COUNT` | 2 | Min word frequency |
| `DEFAULT_SUBSAMPLE_T` | 1e-4 | Subsampling threshold |
| `DEFAULT_NEG_TABLE_SIZE` | 100000 | Negative sampling table |
| `DEFAULT_SEED` | 42 | Reproducibility |

**VBStyle Methods:**

| Method | Type | Purpose |
|--------|------|---------|
| `Run` | dispatch | Command router |
| `BuildCorpus` | command | Read `word_index.db`, build vocabulary + training pairs |
| `Train` | command | SGD training with negative sampling |
| `Normalize` | command | L2-normalize all embedding vectors |
| `SimilarWords` | command | Brute-force cosine similarity search |
| `Save` | command | Export to JSON cache |
| `Load` | command | Import from JSON cache |
| `Stats` | command | Vocabulary size, training stats |
| `read_state` | command | Return current state dict |
| `set_config` | command | Update config parameters |

### Stage 4: Co-occurrence Embedder (`WordEmbedder.py`)

In-RAM co-occurrence + TF-IDF embedder. No ML, pure statistics.

**Configuration:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `DEFAULT_DB` | `word_index.db` | Source token index |
| `DEFAULT_CACHE` | `word_embedder_cache.json` | Output cache |
| `DEFAULT_WINDOW` | 10 | Co-occurrence window |
| `DEFAULT_TOP_K` | 20 | Results to return |
| `DEFAULT_MAX_NEIGHBORS` | 200 | Max co-occurrence neighbors |
| `DEFAULT_DIMS` | 300 | Vector dimensions |
| `DEFAULT_PMI` | True | Use PMI weighting |

**VBStyle Methods:**

| Method | Type | Purpose |
|--------|------|---------|
| `Run` | dispatch | Command router |
| `BuildCooccurrence` | command | Build word co-occurrence matrix |
| `BuildTfidf` | command | Build TF-IDF document vectors |
| `SimilarWords` | command | Cosine similarity on PMI vectors |
| `SimilarFiles` | command | Cosine similarity on TF-IDF vectors |
| `HybridSearch` | command | Fused word + file similarity scoring |
| `Stats` | command | Matrix dimensions, vocabulary stats |

### Training Pipeline Flow

```
C Source Files
    │
    ▼
c_codebase.db (SQLite, 247 MB)
    │
    ├──▶ ingest_c_to_wordindex.py
    │       │
    │       ▼
    │   word_index.db (SQLite, 2.6 GB, WAL mode)
    │       │
    │       ├──▶ Word2VecTrainer.py (numpy skip-gram)
    │       │       │
    │       │       ▼
    │       │   word2vec_cache.json (31 MB)
    │       │
    │       └──▶ WordEmbedder.py (co-occurrence + TF-IDF)
    │               │
    │               ▼
    │           word_embedder_cache.json (12 MB)
    │
    └──▶ train_c_word2vec.py (gensim skip-gram, DomSystem-protected)
            │
            ▼
        word2vec_c_model.bin + word2vec_c_cache.json
```

---

## 17. MySQL Ingestion Pipeline

### Overview

Multiple ingestion scripts populate MySQL databases from various sources. These are the
scripts that fill the 24 application databases documented in Section 8.

### Ingestion Scripts

| Script | Target DB | Source | Rows Ingested |
|--------|-----------|--------|---------------|
| `CodeIngester.py` | `CODEBASE` | Python/C/Swift files | 786K+ files |
| `core/Dom_Db/code_intel_mysql.py` | `vb_shared` | Code analysis | classes, methods, registry |
| `core/Dom_Bcl/bcl_mysql_ingestor.py` | `bcl_ir` | BCL IR data | edges, methods, stamps |
| `core/Dom_Bcl/bcl_ir_bridge.py` | `bcl_ir` | BCL bridge data | cross-references |
| `email_ingestion.py` | `yahoo_emails`, `rht_emails`, `email_store` | Email exports | 1,200+ emails |
| `embed_devin_summaries.py` | `devin` | Devin session summaries | 24K+ messages |
| `embed_knowledge_base.py` | `vb_shared` | Knowledge base embedding | learned_rules, know_* |
| `export_chat_embeddings.py` | `Chat_History` | Chat export + embed | 140K messages |
| `export_chat_fast.py` | `cascade_chats` | Fast chat export | 77K messages |
| `SessionMiner.py` | `vb_shared` | Session mining | session_graphs, session_paths |
| `StampEngine.py` | `vb_shared` | BCL stamp storage | token_master, token_links |
| `system_inventory.py` | `vb_shared` | System inventory | code_classes, code_registry |

### CODEBASE Ingestion (`CodeIngester.py`)

The largest ingestion pipeline. Reads source files and stores content + metadata.

**Target tables:**

| Table | Rows | Size | Content |
|-------|------|------|---------|
| `ingestion_jobs` | 434,432 | 22.1 GB | File content + metadata |
| `code_index` | 23,364 | 8.5 MB | Code identifiers |
| `c_classes` | 24 | 0.5 MB | C class definitions |
| `c_code_index` | 11,017 | 1.5 MB | C code identifiers |
| `c_files` | 8,930 | 1.0 MB | C file metadata |
| `python_files` | 389,000+ | — | Python file content |
| `swift_files` | 10,000+ | — | Swift file content |

### vb_shared Ingestion

The knowledge base ingestion pipeline. Populates learned rules, known problems/solutions,
code classes, and BCL tokens.

**Key tables populated:**

| Table | Rows | Source |
|-------|------|--------|
| `learned_rules` | 10,540 | Error capture + learning |
| `know_problems` | 218 | Problem extraction |
| `know_solutions` | 336 | Solution extraction |
| `know_questions` | 111,452 | Question generation |
| `know_answers` | 31,683 | Answer generation |
| `code_classes` | 247 | Code analysis |
| `code_registry` | 186 | Code registry |
| `rule_tokens` | 238 | BCL rule tokenization |
| `graph_edges` | 30,455 | Graph edge extraction |
| `graph_nodes` | varies | Graph node extraction |

### Chat Ingestion Flow

```
Chat Sources
    │
    ├──▶ ChatGPT exports → chatgpt_export (MySQL, 72K messages)
    ├──▶ Cascade chats   → cascade_chats (MySQL, 77K messages)
    ├──▶ Devin sessions  → devin (MySQL, 109K messages)
    ├──▶ Codex history   → codex_chat_history (MySQL, 8K messages)
    ├──▶ ChatGPT chats   → chatgpt_chats (MySQL, 25K messages)
    │
    ▼
Chat_History (MySQL, 140K+ messages unified)
    │
    ▼
msearch3 (C binary, magnetic search)
    │
    ▼
Search Results (215K+ messages searchable)
```

---

## 18. Qdrant Vector Operations Pipeline

### Overview

Qdrant provides semantic vector search. This section documents the collection management,
embedding ingestion, and search workflow.

### Collection Management

**REST API (port 6333):**

```bash
# Create collection
curl -X PUT http://localhost:6333/collections/my_collection \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {"size": 128, "distance": "Cosine"},
    "optimizers_config": {"default_segment_number": 2}
  }'

# List collections
curl http://localhost:6333/collections

# Get collection info
curl http://localhost:6333/collections/my_collection

# Delete collection
curl -X DELETE http://localhost:6333/collections/my_collection
```

### Upsert Workflow

```bash
# Upsert points
curl -X PUT http://localhost:6333/collections/my_collection/points \
  -H 'Content-Type: application/json' \
  -d '{
    "points": [
      {"id": 1, "vector": [0.1, 0.2, ...], "payload": {"message_id": 1001}},
      {"id": 2, "vector": [0.3, 0.4, ...], "payload": {"message_id": 1002}}
    ]
  }'
```

### Search Workflow

```bash
# Semantic search
curl -X POST http://localhost:6333/collections/my_collection/points/search \
  -H 'Content-Type: application/json' \
  -d '{
    "vector": [0.15, 0.25, ...],
    "limit": 10,
    "with_payload": true
  }'
```

### gRPC API (port 6334)

For high-throughput applications, use gRPC instead of REST:

```python
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6334)

# Search
results = client.search(
    collection_name="my_collection",
    query_vector=[0.15, 0.25, ...],
    limit=10
)
```

### Snapshot Management

```bash
# Create snapshot
curl -X POST http://localhost:6333/collections/my_collection/snapshots

# List snapshots
curl http://localhost:6333/collections/my_collection/snapshots

# Restore from snapshot
curl -X PUT http://localhost:6333/collections/my_collection/snapshots/<snapshot_name>
```

**Snapshot storage:** `~/.local/bin/qdrant/storage/snapshots/`

### ID Bridge Pattern

The critical pattern for connecting Qdrant to MySQL and Neo4j:

```
MySQL:    message.id = 1001
Qdrant:   payload = {"message_id": 1001, "type": "message"}
Neo4j:    (:Message {message_id: 1001})
```

The ID is the join key. The vector lives in Qdrant. The data lives in MySQL.
The relationships live in Neo4j. **Never duplicate data across stores.**

---

## 19. SQLite Catalog Management

### Overview

56+ SQLite databases exist across the workspace. This section documents their creation,
schema management, and backup strategy.

### SQLite Databases by Purpose

| Category | Databases | Purpose |
|----------|-----------|---------|
| **Graph work** | `dom_graph_work.db`, `domain_graph.db` | Graph pipeline intermediate storage |
| **Word index** | `word_index.db` (2.6 GB), `c_codebase.db` (247 MB) | Token indexing for Word2Vec |
| **BCL** | `bcl_ir.db`, `bcl_export.db`, `bcl_inventory.db`, `bcl_c_engine.db` | BCL IR storage |
| **Execution** | `unified_cache.db`, `reuse_weights.db` | Execution engine caches |
| **Decision trees** | `decision_trees.db` | Decision tree state |
| **Session** | Various session-specific `.db` files | Per-session state |
| **Test** | Various test `.db` files | Test fixtures |

### Schema Management

SQLite databases are created on-demand by Python scripts using `CREATE TABLE IF NOT EXISTS`.
No migration framework is used. Schema changes are handled by:

1. Adding new tables (additive, non-breaking)
2. Adding columns via `ALTER TABLE ADD COLUMN` (SQLite supports this)
3. Creating new tables with `_v2` suffix for major changes

### WAL Mode

Several critical SQLite databases use Write-Ahead Logging:

```python
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

**Benefits:** Concurrent readers during writes, no blocking, faster commits.
**Trade-off:** `-wal` and `-shm` sidecar files must be kept together with `.db` file.

### Backup Strategy

```bash
# Cold backup (stop writes first)
cp word_index.db word_index.db.bak

# Hot backup using .backup command
sqlite3 word_index.db ".backup word_index.db.bak"

# Using VACUUM INTO (creates compact copy)
sqlite3 word_index.db "VACUUM INTO 'word_index.db.compressed'"
```

---

## 20. Execution Engine In-RAM Bus

### Overview

The execution engine uses an in-RAM SQLite database as a closed-loop event bus for
tracking code execution, violations, fix attempts, and state transitions.

### Schema (from `Config.py` `EXEC_SCHEMA`)

```sql
CREATE TABLE exec_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    event_type TEXT NOT NULL,    -- 'execute', 'violation', 'fix', 'verify', 'rollback'
    target TEXT,                 -- file or function path
    detail TEXT,                 -- JSON blob with event-specific data
    status TEXT DEFAULT 'pending' -- 'pending', 'running', 'success', 'failed', 'rolled_back'
);

CREATE TABLE exec_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    rule_name TEXT NOT NULL,     -- VBStyle rule that was violated
    target TEXT,                 -- file:function that violated
    severity TEXT DEFAULT 'error', -- 'error', 'warning', 'info'
    auto_fix_attempted INTEGER DEFAULT 0,
    fixed INTEGER DEFAULT 0
);

CREATE TABLE exec_fix_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER REFERENCES exec_violations(id),
    ts TEXT DEFAULT (datetime('now')),
    fix_strategy TEXT,           -- 'rename', 'remove_print', 'add_run', 'fix_tuple3'
    patch TEXT,                  -- the actual code patch applied
    success INTEGER DEFAULT 0,
    error_msg TEXT
);

CREATE TABLE exec_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_ts TEXT DEFAULT (datetime('now'))
);
```

### Configuration Constants

| Constant | Default | Purpose |
|----------|---------|---------|
| `EXEC_SCHEMA` | (above) | In-RAM SQLite DDL |
| `EXEC_IN_RAM` | True | Use `:memory:` SQLite |
| `EXEC_BATCH_SIZE` | 100 | Batch insert size |
| `EXEC_MAX_FIX_ATTEMPTS` | 3 | Max auto-fix retries |
| `EXEC_AUTO_FIX` | True | Enable auto-fix on violations |
| `EXEC_ROLLBACK_ON_FAIL` | True | Rollback on fix failure |
| `EXEC_MYSQL_RULES_DB` | `vb_shared` | MySQL rules database |
| `EXEC_MYSQL_HOST` | localhost | MySQL host |
| `EXEC_MYSQL_USER` | root | MySQL user |
| `EXEC_MYSQL_PASS` | (empty) | MySQL password |
| `EXEC_MYSQL_DB` | vb_shared | MySQL database |
| `EXEC_LEARN_FROM_FAILURES` | True | Write failed attempts to learned_rules |
| `EXEC_LEARNED_RULES_TABLE` | learned_rules | MySQL table for learned rules |
| `EXEC_VIOLATION_TABLE` | exec_violations | SQLite table for violations |
| `EXEC_FIX_TABLE` | exec_fix_attempts | SQLite table for fix attempts |
| `EXEC_EVENT_TABLE` | exec_events | SQLite table for events |

### Closed-Loop Flow

```
Execute code
    │
    ▼
exec_events (event_type='execute', status='running')
    │
    ├──▶ Check VBStyle rules
    │       │
    │       ├──▶ No violations → exec_events (status='success')
    │       │
    │       └──▶ Violations found
    │               │
    │               ▼
    │           exec_violations (rule_name, target, severity)
    │               │
    │               ├──▶ Auto-fix disabled → exec_events (status='failed')
    │               │
    │               └──▶ Auto-fix enabled
    │                       │
    │                       ▼
    │                   exec_fix_attempts (fix_strategy, patch)
    │                       │
    │                       ├──▶ Success → exec_violations (fixed=1)
    │                       │               → exec_events (status='success')
    │                       │
    │                       └──▶ Failure → rollback
    │                                       → exec_fix_attempts (success=0, error_msg)
    │                                       → exec_events (status='rolled_back')
    │                                       → MySQL learned_rules (learn from failure)
```

---

## 21. Neo4j Memory Model — 21-Component Engine

### Node Labels (with properties)

```
(:Message {id, text, role, timestamp, chat_id})
(:Observation {id, text, type, confidence, created_at})
(:Fact {id, text, truth_state, verified_by, verified_at, superseded_by, created_at})
(:Episode {id, title, start_time, end_time, summary, state, node_count})
(:SemanticMemory {id, text, compressed_from, created_at})
(:Concept {id, name})
(:Tool {id, name, version})
(:File {id, path})
(:Entity {id, name, type})
(:Decision {id, text, made_at})
(:Error {id, text, occurred_at})
(:Task {id, text, state})
(:Goal {id, text})
(:Blocker {id, text})
(:Hypothesis {id, text, confidence})
(:Experiment {id, text, tried_at})
(:Outcome {id, text, result})
(:Evidence {id, text, confidence, source_ref})
(:Domain {id, name})
(:Class {id, name, domain})
(:Method {id, name, signature, body, line_start, line_end})
```

### Relationship Types

**Memory Layer:**
```
(:Message)-[:OBSERVED_AS]->(:Observation)
(:Observation)-[:SUPPORTS {confidence}]->(:Fact)
(:Fact)-[:PART_OF]->(:Episode)
(:Episode)-[:COMPRESSED_TO]->(:SemanticMemory)
```

**Truth:**
```
(:Fact)-[:CONTRADICTS]->(:Fact)
(:Fact)-[:OBSOLETES]->(:Fact)
(:Fact)-[:REPLACES {at}]->(:Fact)
(:Fact)-[:SUPERSEDED_BY]->(:Fact)
```

**Temporal:**
```
(:Node)-[:BEFORE]->(:Node)
(:Node)-[:AFTER]->(:Node)
(:Node)-[:REPLACED_BY {at}]->(:Node)
(:Node)-[:VALID_DURING {from, to}]->(:Node)
```

**Identity:**
```
(:Node)-[:ALIAS_OF]->(:Node)
(:Node)-[:SAME_AS {confidence}]->(:Node)
(:Node)-[:RENAMED_TO {at}]->(:Node)
```

**Causal:**
```
(:Node)-[:CAUSED_BY]->(:Node)
(:Node)-[:RESOLVES]->(:Node)
(:Node)-[:LED_TO]->(:Node)
(:Action)-[:FIXED_BY]->(:Fix)
```

**Hierarchy:**
```
(:Domain)-[:CONTAINS]->(:Class)
(:Class)-[:CONTAINS]->(:Method)
(:Method)-[:IN_FILE]->(:File)
(:Node)-[:OWNS]->(:Node)
(:Node)-[:MEMBER_OF]->(:Node)
```

**Structural:**
```
(:Node)-[:REFERENCES]->(:Node)
(:Node)-[:DEPENDS_ON]->(:Node)
(:Node)-[:RELATED_TO {weight}]->(:Node)
```

### Indexes

```cypher
CREATE INDEX FOR (m:Message) ON (m.chat_id)
CREATE INDEX FOR (m:Message) ON (m.timestamp)
CREATE INDEX FOR (f:Fact) ON (f.truth_state)
CREATE INDEX FOR (t:Task) ON (t.state)
CREATE INDEX FOR (e:Episode) ON (e.state)
CREATE INDEX FOR (c:Concept) ON (c.name)
CREATE INDEX FOR (f:File) ON (f.path)
CREATE INDEX FOR (d:Domain) ON (d.name)
CREATE INDEX FOR (c:Class) ON (c.name)
CREATE INDEX FOR (m:Method) ON (m.name)
```

### Example Queries

```cypher
// "Why did RustDesk fail?"
MATCH (p:Concept {name: 'RustDesk'})
      -[:CAUSED_BY]->(error:Error)
RETURN p, error

// "What fixed the SSH issue?"
MATCH (e:Error)-[:FIXED_BY]->(f:Fix)
WHERE e.text CONTAINS 'SSH'
RETURN e, f

// "What decisions were made in this episode?"
MATCH (d:Decision)-[:PART_OF]->(ep:Episode {id: $episodeId})
RETURN d

// "What facts are still verified?"
MATCH (f:Fact {truth_state: 'VERIFIED'})
WHERE NOT (f)-[:SUPERSEDED_BY]->()
RETURN f

// "Trace evidence chain for a fact"
MATCH path =
  (f:Fact {id: $factId})
    <-[:SUPPORTS]-(o:Observation)
    <-[:OBSERVED_AS]-(m:Message)
RETURN path
```

---

## 22. Storage Stack Analysis — Do We Need More?

### Current Stack Coverage

The current stack (MySQL + Qdrant + Neo4j + SQLite + LMDB) covers ~90-95% of the storage
layer. The biggest bottleneck is NOT another database — it's the reasoning layers
(Truth, Evidence, Identity, Temporal, Governor, Query Planner).

**Adding more storage engines does NOT solve reasoning problems.**

### Tier Ranking: Additional Engines

| Tier | Engine | Verdict | When to Add |
|------|--------|---------|-------------|
| 1 | Redis | Potentially useful | Cache, agent state, queues, temp context |
| 2 | Elasticsearch | Valuable later | When text corpus hits millions of documents |
| 3 | MongoDB/Cassandra/CouchDB | Unnecessary | No role they fill isn't already covered |

### Elasticsearch vs Qdrant

```
Elasticsearch: "Find text that CONTAINS: rustdesk, relay, ssh, disconnect"
  → Keyword match, fuzzy, stemming, ranking
  → Exact words and variations

Qdrant: "Find text with SIMILAR MEANING to: 'remote desktop connection problem'"
  → Semantic similarity, embeddings
  → Works even if the word "RustDesk" never appears
```

Both are needed for different reasons — Elasticsearch for keyword search, Qdrant for meaning search.

### Ideal Stack for Large Memory System

```
Markdown Files
      │
      ▼
Elasticsearch → Keyword Hits (fast text search)
      │
      ▼
Embeddings
      │
      ▼
Qdrant → Semantic Hits (meaning search)
      │
      ▼
Relationships
      │
      ▼
Neo4j → Evidence Chains (graph traversal)
      │
      ▼
Truth/Data
      │
      ▼
MySQL → Structured Records (source of truth)
```

### Complexity Tradeoff

Adding Elasticsearch means: 4 databases → 4 backups → 4 sync paths → 4 failure modes.
Only add it if LIKE queries are becoming painful on millions of documents.

### Frozen Stack (Today)

| Priority | Database | Status | Role |
|----------|----------|--------|------|
| #1 | MySQL | MANDATORY | Structured truth, codebase, computation units |
| #2 | Qdrant | MANDATORY | Semantic memory, embeddings, meaning search |
| #3 | Neo4j | VERY VALUABLE | Relationship memory, graph traversal, evidence chains |
| #4 | SQLite | ALWAYS ON | Local work DBs, execution bus, caches |
| #5 | LMDB/Word2Vec | ALWAYS ON | RAM-resident vectors, ANN search |
| #6 | Redis | OPTIONAL | Cache, agent runtime state, fast activation |
| #7 | Elasticsearch | VALUABLE LATER | When text corpus becomes huge |

---

## 23. Graph Database Comparison

| Database | Best At | Verdict |
|----------|---------|---------|
| Neo4j | Property graphs, traversal, relationships | Most mature graph DB |
| TigerGraph | Massive graphs, analytics | Enterprise scale |
| JanusGraph | Distributed graph storage | Good but complex |
| ArangoDB | Graph + Document | Very flexible |
| Memgraph | Fast graph processing | Excellent for realtime |
| Qdrant | Semantic/vector search | Not a graph DB |
| MySQL | Structured storage | Not a graph DB |

**Single database option (if forced to choose one):** Neo4j — because the system is
fundamentally node/edge/evidence/identity/hierarchy/temporal/causal, which is graph-native.

---

## 24. MySQL to Neo4j Migration Path

The current `graph_computation_units` table contains graph data in relational form:
Method, Class, Domain, File. This can be migrated directly to Neo4j:

```cypher
(:Domain)-[:CONTAINS]->(:Class)
(:Class)-[:CONTAINS]->(:Method)
(:Method)-[:IN_FILE]->(:File)
```

### Migration Steps

1. Read all rows from `graph_computation_units.computation_units`
2. Create Domain nodes (unique domains)
3. Create Class nodes (unique class_names)
4. Create Method nodes (each row = one method)
5. Create File nodes (unique file_paths)
6. Create CONTAINS edges (Domain → Class, Class → Method)
7. Create IN_FILE edges (Method → File)
8. Import method body, signature, line numbers as node properties

This migration is a 1:1 mapping from rows to nodes. The hard part is the reasoning
layers (Evidence, Truth, Observation), not the structural migration.

---

## 25. Key Database Principles from learned_rules

Extracted from `vb_shared.learned_rules` (10,540 rules) and `vb_shared.tokens`:

1. **Database over file** — always prefer database storage over files (`[@USE_DATABASE_OVER_FILE]`)
2. **Embeddings are index, not primary** — fact DB is primary, embeddings are search index (`id=149`)
3. **No JSON as architecture** — use proper database schemas, not JSON blobs (`id=13650`)
4. **No hidden truth storage** — all truth storage must be explicit and structured (`id=15299`)
5. **Backup before modifications** — always backup database before changes (`[@ALWAYS_BACKUP_DATABASE_BEFORE_MODIFICATIONS]`)
6. **Learning requires storage** — correction → storage → reuse is the learning cycle (`id=16209`)
7. **Don't blame storage first** — check query patterns before blaming the database (`id=19177`)
8. **Settings/test databases are non-chat** — classify correctly (`[@CLASSIFY_SETTINGS_DATABASES_AS_NON_CHAT]`)
9. **Self-documenting database** — database stores DATA, BEHAVIOR, KNOWLEDGE, DEPENDENCIES, EXECUTION, MEMORY (`id=1790`)
10. **Write-back operations** — persist changes to storage explicitly (`[@Writeback]`)

### Critical Trap: Do Not Duplicate

```
MySQL    owns raw records
Qdrant   owns vectors
Neo4j    owns relationships
```

**Violations:**
- Storing message text in Neo4j (MySQL owns that)
- Storing embeddings in MySQL (Qdrant owns that)
- Storing relationships in MySQL JOINs (Neo4j owns that)
- Duplicating computation_units into Neo4j as full text (Neo4j should only store ID + structural relationships)

**Use IDs to connect them:**
```
mysql.message.id = 1001
qdrant.payload = {"message_id": 1001}
neo4j node = (:Message {message_id: 1001})
```

The ID is the join key across all three databases. The DATA lives in ONE place. The ID is the bridge.

---

## 26. Troubleshooting (Extended)

### MySQL Collation Mismatch on Cross-Database JOINs

```
ERROR 1267 (HY000): Illegal mix of collations (utf8mb4_unicode_ci, IMPLICIT) and (utf8mb4_0900_ai_ci, IMPLICIT) for operation '='
```

**Cause:** Databases created with different collations (`utf8mb4_unicode_ci` vs `utf8mb4_0900_ai_ci`).

**Fix:** Use `CONVERT()` or `COLLATE` in the JOIN:
```sql
SELECT * FROM vb_shared.graph_edges e
JOIN CODEBASE.code_index c
  ON CONVERT(e.target USING utf8mb4) COLLATE utf8mb4_unicode_ci = CONVERT(c.identifier USING utf8mb4) COLLATE utf8mb4_unicode_ci;
```

### MySQL Auto-Increment Gaps

Tables like `know_solutions` (auto_increment=10,077 but only 348 rows) have large ID gaps
from deleted entries. This is normal behavior, not a bug. To reset:
```sql
ALTER TABLE know_solutions AUTO_INCREMENT = 349;
```
**Warning:** Only do this if no foreign keys reference the table.

### word_index.db WAL File Growing

If `word_index.db-wal` grows too large:
```bash
# Checkpoint the WAL
sqlite3 word_index.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Or set a WAL size limit
sqlite3 word_index.db "PRAGMA wal_autocheckpoint=1000;"
```

### Qdrant Collection Locked

If a Qdrant collection is locked (optimization in progress):
```bash
# Check collection status
curl http://localhost:6333/collections/my_collection

# Wait for optimization to complete, or force unlock
curl -X PATCH http://localhost:6333/collections/my_collection \
  -H 'Content-Type: application/json' \
  -d '{"optimizers_config": {"indexing_threshold": 0}}'
```

### LMDB Map Full

If LMDB throws `MapFullError`:
```python
# Increase map size before opening
env = lmdb.open(path, map_size=1024 * 1024 * 1024)  # 1 GB
# Or larger
env = lmdb.open(path, map_size=10 * 1024 * 1024 * 1024)  # 10 GB
```

---

## Appendix A: Total Storage Summary

| Store | Size | Details |
|-------|------|---------|
| MySQL (all 24 schemas) | ~25 GB | Data directory `/opt/homebrew/var/mysql/` |
| MySQL (system schemas) | ~0.5 GB | `mysql`, `information_schema`, `performance_schema`, `sys` |
| MySQL binary logs | ~197 MB | `binlog.000024` through `binlog.000030` |
| MySQL SSL/TLS certs | ~12 KB | `ca.pem`, `server-cert.pem`, etc. |
| Neo4j (data directory) | 7.8 MB | `/opt/homebrew/var/neo4j/` |
| Qdrant (storage dir) | variable | `~/.local/bin/qdrant/storage/` |
| SQLite (56+ files) | ~300 MB+ | Largest: `word_index.db` (116 MB) |
| LMDB (mmap) | RAM-resident | Size = available RAM |
| Word2Vec caches | 43 MB | `word2vec_cache.json` (31 MB) + `word_embedder_cache.json` (12 MB) |
| Word2Vec word index | 116 MB | `word_index.db` |
| **Total estimated** | **~26 GB+** | MySQL dominant |

### MySQL Storage Breakdown by Database

| Database | Size (MB) | % of Total |
|----------|-----------|------------|
| `CODEBASE` | 18,621.6 | 74.5% |
| `vbstyle_documents` | 682.4 | 2.7% |
| `devin` | 438.4 | 1.8% |
| `vb_shared` | 405.4 | 1.6% |
| `cascade_chats` | 393.4 | 1.6% |
| `Chat_History` | 369.6 | 1.5% |
| `questions` | 310.8 | 1.2% |
| `token_registry` | 256.1 | 1.0% |
| `chatgpt_export` | 244.4 | 1.0% |
| `bcl_ir` | 197.2 | 0.8% |
| `treasure_trove` | 124.9 | 0.5% |
| `chatgpt_chats` | 116.5 | 0.5% |
| `qa_system` | 93.9 | 0.4% |
| `vb_code_test` | 47.5 | 0.2% |
| `codex_chat_history` | 23.4 | 0.1% |
| `code_graph` | 22.3 | 0.1% |
| `yahoo_emails` | 10.6 | <0.1% |
| `graph_computation_units` | 4.0 | <0.1% |
| `cascade_intent` | 0.3 | <0.1% |
| `agent_os` | 0.2 | <0.1% |
| `rht_emails` | 0.2 | <0.1% |
| `email_store` | 0.1 | <0.1% |
| `vb_ingestion` | 0.1 | <0.1% |
| `gui_pipeline` | 0.0 | <0.1% |
| **Total (app schemas)** | **~25,032** | **100%** |

## Appendix B: Related Files

| File | Path |
|------|------|
| DomSystem | `core/Dom_Unified/DomSystem.py` |
| DomSystem Config | `core/Dom_Unified/Config.py` |
| Dom_Unified init | `core/Dom_Unified/__init__.py` |
| Database Storage Architecture | `core/Piplines/Plf_DatabaseStorageArchitecture.md` |
| Word2Vec Trainer | `core/Piplines/Word2VecTrainer.py` |
| Word Embedder | `core/Piplines/WordEmbedder.py` |
| Code Intel MySQL | `core/Dom_Db/code_intel_mysql.py` |
| BCL MySQL Ingestor | `core/Dom_Bcl/bcl_mysql_ingestor.py` |
| BCL IR Bridge | `core/Dom_Bcl/bcl_ir_bridge.py` |
| Brain Server | `Dom_Graph/brain_server/server.js` |
| Domain Graph Engine | `code_store_variations/domain_graph.db` |
| Graph Pipeline | `Dom_Graph/Config.py` |
| BCL C Engine DB | `core/Dom_Bcl_C_ver/bcl_c_engine.db` |
| BCL Export DB | `core/Dom_Bcl/bcl_export.db` |
| BCL Inventory DB | `core/Dom_Bcl/bcl_inventory.db` |
| BCL IR DB (SQLite) | `core/Dom_Bcl/bcl_ir.db` |
| BCL IR Bridge DB | `core/Dom_Bcl/bcl_ir_bridge.db` |
| Unified Cache DB | `core/Dom_Unified/unified_cache.db` |
| Reuse Weights DB | `core/Dom_Unified/reuse_weights.db` |
| Qdrant Config | `~/.local/bin/qdrant/config.yaml` |
| Qdrant Binary | `~/.local/bin/qdrant/qdrant` |
| Neo4j Config | `/opt/homebrew/var/neo4j/conf/neo4j.conf` |
| Neo4j Binary | `/opt/homebrew/opt/neo4j/bin/neo4j` |
| MySQL Binary | `/opt/homebrew/opt/mysql@8.0/bin/mysqld` |
| MySQL Config | `/opt/homebrew/etc/my.cnf` (if present) |
| MySQL Data Dir | `/opt/homebrew/var/mysql/` |
| MySQL Error Log | `/opt/homebrew/var/mysql/nwm.err` |
| MySQL PID File | `/opt/homebrew/var/mysql/nwm.pid` |
| MySQL Socket | `/tmp/mysql.sock` |
| MySQL X Protocol Socket | `/tmp/mysqlx.sock` |
| LMDB Primary Lib | `/Users/Shared/VB_ai_Dec/Project_PropPanel/Libs/Py/Lib_LMDB_Ram_opti_GGuf.py` |
| Word2Vec Cache | `core/Piplines/word2vec_cache.json` (31 MB) |
| Word Embedder Cache | `core/Piplines/word_embedder_cache.json` (12 MB) |
| Word Index DB | `core/Piplines/word_index.db` (116 MB) |

## Appendix C: MySQL Connection Quick Reference

### Command-Line Connection

```bash
# Basic connection (no password, localhost)
mysql -u root

# With explicit host and port
mysql -u root -h 127.0.0.1 -P 3306

# With socket
mysql -u root --socket=/tmp/mysql.sock

# Connect to specific database
mysql -u root vb_shared

# Connect via X Protocol (mysqlx)
mysqlx -u root --socket=/tmp/mysqlx.sock
```

### Python Connection (mysql-connector-python)

```python
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    port=3306,
    unix_socket="/tmp/mysql.sock",
    database="vb_shared",
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
)
```

### Python Connection (PyMySQL)

```python
import pymysql

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    port=3306,
    unix_socket="/tmp/mysql.sock",
    database="vb_shared",
    charset="utf8mb4",
)
```

### Config.py Connection Constants

```python
# From core/Dom_Unified/Config.py
GRAPH_MYSQL_HOST = "localhost"
GRAPH_MYSQL_USER = "root"
GRAPH_MYSQL_PORT = 3306
GRAPH_MYSQL_DB_VB = "vb_shared"
GRAPH_MYSQL_DB_BCL = "bcl_ir"

EXEC_MYSQL_HOST = "localhost"
EXEC_MYSQL_USER = "root"
EXEC_MYSQL_PASS = ""
EXEC_MYSQL_DB = "vb_shared"

SESSION_GRAPH_MYSQL_HOST = "localhost"
SESSION_GRAPH_MYSQL_USER = "root"
SESSION_GRAPH_MYSQL_PASS = ""
SESSION_GRAPH_MYSQL_DB = "vb_shared"
```

## Appendix D: Quick Service Management Commands

### MySQL

```bash
# Start
brew services start mysql@8.0
# OR
/opt/homebrew/opt/mysql@8.0/bin/mysqld_safe --datadir=/opt/homebrew/var/mysql &

# Stop
brew services stop mysql@8.0
# OR
mysqladmin -u root shutdown

# Status
brew services info mysql@8.0
mysql -u root -e "SELECT VERSION();"
mysql -u root -e "SHOW STATUS LIKE 'Uptime';"

# Check process
ps aux | grep mysqld

# Check port
lsof -i :3306
```

### Neo4j

```bash
# Start
/opt/homebrew/opt/neo4j/bin/neo4j start

# Stop
/opt/homebrew/opt/neo4j/bin/neo4j stop

# Status
/opt/homebrew/opt/neo4j/bin/neo4j status

# Check ports
lsof -i :7474  # HTTP
lsof -i :7687  # Bolt
```

### Qdrant

```bash
# Start
~/.local/bin/qdrant/qdrant --config-path ~/.local/bin/qdrant/config.yaml &

# Stop
pkill -f qdrant

# Status
curl http://localhost:6333/health

# Check port
lsof -i :6333  # HTTP
lsof -i :6334  # gRPC
```

### SQLite

```bash
# No service to start/stop — always available
# Open a database
sqlite3 core/Dom_Unified/unified_cache.db

# Show tables
sqlite3 core/Dom_Unified/unified_cache.db ".tables"

# Show schema
sqlite3 core/Dom_Unified/unified_cache.db ".schema"
```

### DomSystem (Unified)

```python
from core.Dom_Unified.DomSystem import DomSystem

ds = DomSystem()

# Start all services
ok, data, err = ds.Run("start_all", {})

# Stop all services
ok, data, err = ds.Run("stop_all", {})

# Check all health
ok, data, err = ds.Run("check_all", {})

# Status of all services
ok, data, err = ds.Run("status", {"service": "all"})

# Start specific service
ok, data, err = ds.Run("start", {"service": "mysql"})
ok, data, err = ds.Run("start", {"service": "neo4j"})
ok, data, err = ds.Run("start", {"service": "qdrant"})

# Stop specific service
ok, data, err = ds.Run("stop", {"service": "mysql"})

# Health check
ok, data, err = ds.Run("health", {"service": "mysql"})

# Acquire (refcounted)
ok, data, err = ds.Run("acquire", {"service": "mysql", "requester": "my_module"})

# Release (refcounted)
ok, data, err = ds.Run("release", {"service": "mysql", "requester": "my_module"})

# Force release
ok, data, err = ds.Run("force_release", {"service": "mysql"})

# Pin (never unload)
ok, data, err = ds.Run("pin", {"service": "mysql"})

# Unpin
ok, data, err = ds.Run("unpin", {"service": "mysql"})

# Garbage collect idle services
ok, data, err = ds.Run("gc", {})

# Purge (memory pressure relief)
ok, data, err = ds.Run("purge", {})

# Recover (restart failed service)
ok, data, err = ds.Run("recover", {"service": "mysql"})
```
