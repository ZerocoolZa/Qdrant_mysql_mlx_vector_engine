# BCL Units Full Structural Analysis v2

Generated: 2026-07-03 11:40:38.619219

## Overview

| Metric | Value |
|---|---|
| Files | 22 |
| Total lines | 5126 |
| Code lines | 4088 |
| Comment lines | 1038 |
| Functions | 137 |
| Dead functions | 6 |
| Complexity | 647 |
| TODOs/FIXMEs | 0 |
| SQL queries | 83 |
| Circular deps (cross-file) | 0 |
| Circular deps (intra-file) | 0 |
| Global vars | 125 |
| BCL packet patterns | 327 |
| IMPLEMENTED | 8 |
| PARTIAL | 1 |
| SHELL | 13 |

## Summary Table

| File | Lines | Code | Funcs | Dead | CX | Nest | Risk | Status | Domain | SQL | TODO | GV | Pkt | Cyc | Cmds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bcl_msearch.c | 1214 | 995 | 14 | 0 | 178 | 10 | HIGH | IMPLEMENTED | mysql, filesystem, search | 28 | 0 | 10 | 91 | 0 | search, where, count, stats (+7) |
| bcl_msearch_magnetic.c | 667 | 560 | 10 | 0 | 76 | 8 | MEDIUM | IMPLEMENTED | mysql | 11 | 0 | 8 | 50 | 0 | magnetic, chat_radius, graph_radius, read_state (+1) |
| bcl_pb_reader.c | 667 | 546 | 14 | 0 | 95 | 6 | HIGH | IMPLEMENTED | crypto, filesystem, search | 23 | 0 | 16 | 24 | 0 | scan, load-all, search, stats (+2) |
| bcl_msearch_qdrant.c | 647 | 550 | 7 | 0 | 77 | 3 | MEDIUM | IMPLEMENTED | mysql | 12 | 0 | 5 | 56 | 0 | semantic, multi, full, qstats (+2) |
| bcl_msearch_ranking.c | 455 | 359 | 8 | 0 | 81 | 5 | HIGH | IMPLEMENTED | mysql | 4 | 0 | 6 | 31 | 0 | rank, update_route, understandings, where_to_store (+2) |
| bcl_msearch_registry.c | 380 | 303 | 9 | 0 | 46 | 7 | MEDIUM | IMPLEMENTED | mysql | 5 | 0 | 8 | 21 | 0 | load_registry, detect_route, schema, read_state (+1) |
| bcl_tool_main.c | 322 | 257 | 15 | 6 | 40 | 5 | MEDIUM | IMPLEMENTED | unknown | 0 | 0 | 12 | 9 | 0 |  |
| bcl_msearch_help.c | 158 | 112 | 4 | 0 | 12 | 3 | LOW | IMPLEMENTED | unknown | 0 | 0 | 4 | 14 | 0 | help, rules, usage, read_state (+1) |
| bcl_chat_ingest.c | 57 | 42 | 4 | 0 | 3 | 3 | LOW | PARTIAL | unknown | 0 | 0 | 4 | 5 | 0 | read_state, set_config |
| bcl_cleaner.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_codeingest.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_cognitive_core.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_discovery.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_error_fix.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_ghostctl.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_magnetic.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_mdmerge.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_schemalint.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_smartcli.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_vbcheck.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_wcmd.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
| bcl_windir.c | 43 | 28 | 4 | 0 | 3 | 3 | LOW | SHELL | unknown | 0 | 0 | 4 | 2 | 0 | read_state, set_config |
## Cross-File Call Graph

| Caller | -> | Target File | Function |
|---|---|---|---|
| bcl_msearch.c | -> | bcl_msearch_qdrant.c | MsearchQdrant_Run |
| bcl_msearch.c | -> | bcl_msearch_registry.c | MsearchRegistry_Run |

---

## bcl_msearch.c

| Property | Value |
|---|---|
| Lines | 1214 (code: 995, comments: 219) |
| Functions | 14 |
| Dead functions | 0 |
| External calls | 7 |
| Complexity | 178 |
| Risk | HIGH |
| Status | **IMPLEMENTED** |
| Domain | mysql, filesystem, search |
| SHA | c16117c0ef4b |
| Includes | 4 |
| Defines | 13 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 28 |
| Table refs | vb_shared, vb_code_test, devin, INFORMATION_SCHEMA |
| BCL commands | 11 |
| BCL packets | 46 |
| Global vars | 10 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** MySQL keyword search across all knowledge databases. Commands: search, where, count, stats, read_state, set_config. Connects to localhost root no-password. Searches 12+ tables in 3 databases. Returns BCL packets with match results.

**Class:** Msearch

**Declared methods:** Init, Run, Close, State, Connect, SearchKeyword, SearchTable, DiscoverTables, CountKeyword, Stats, EscapeString, ReadState, SetConfig

### BCL Commands
- `search`
- `where`
- `count`
- `stats`
- `search_files`
- `search_schema`
- `search_all_db`
- `search_all_mysql`
- `hybrid`
- `read_state`
- `set_config`

### Functions (14)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `build_match` | static void | `const char *col, const char *keyword,
  ` | 5 | static | 93 | 19 | 2 |  |
| `ensure_connected` | static int | `void` | 0 | static | 117 | 29 | 3 |  |
| `escape_like` | static void | `MYSQL *conn, const char *in, char *out, ` | 4 | static | 150 | 10 | 3 |  |
| `escape_sql` | static void | `MYSQL *conn, const char *in, char *out, ` | 4 | static | 162 | 2 | 1 |  |
| `truncate_text` | static void | `const char *in, char *out, int out_sz` | 3 | static | 168 | 17 | 3 |  |
| `search_one_table` | static int | `const SearchTarget *t, const char *keywo` | 6 | static | 189 | 39 | 4 | LEFT, ensure_connected, escape_like, truncate_text |
| `discover_tables` | static int | `const char *db_filter, char *out, size_t` | 4 | static | 233 | 40 | 4 | IN, ensure_connected, escape_sql |
| `count_keyword` | static int | `const char *keyword, char *out, size_t o` | 3 | static | 277 | 52 | 7 | COUNT, ensure_connected, escape_like |
| `stats_all` | static int | `char *out, size_t out_sz` | 2 | static | 333 | 42 | 6 | COUNT, ensure_connected |
| `search_files` | static int | `const char *root_dir, const char *ext_fi` | 6 | static | 379 | 0 | 0 |  |
| `Msearch_Init` | int | `void` | 0 | exported | 518 | 9 | 1 |  |
| `Msearch_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 529 | 412 | 10 | MsearchRegistry_Run, Msearch_Init, build_match, count_keyword, discover_tables (+5) |
| `Msearch_Close` | int | `void` | 0 | exported | 1186 | 8 | 2 |  |
| `Msearch_State` | const char | `void` | 0 | exported | 1196 | 7 | 1 |  |

### External Calls (7)
- `COUNT`
- `IN`
- `LEFT`
- `MsearchQdrant_Run`  -> bcl_msearch_qdrant.c
- `MsearchRegistry_Run`  -> bcl_msearch_registry.c
- `S_ISDIR`
- `mysql_fetch_lengths`

### Includes
- `"bcl_toolstack.h"`
- `<mysql.h>`
- `<dirent.h>`
- `<sys/stat.h>`

### Defines (13)
- `MSEARCH_MAX_QUERY` = `4096`
- `MSEARCH_MAX_SNIPPET` = `512`
- `MSEARCH_MAX_TABLES` = `32`
- `MSEARCH_MAX_DB` = `64`
- `MSEARCH_DEFAULT_LIMIT` = `50`
- `MSEARCH_HOST_LEN` = `256`
- `MSEARCH_USER_LEN` = `64`
- `MSEARCH_PASS_LEN` = `128`
- `MSEARCH_SOCKET_LEN` = `256`
- `MSEARCH_BUF` = `8192`
- `MSEARCH_MAX_DB_S` = `32`
- `MSEARCH_MAX_COLS` = `32`
- `TARGET_COUNT` = `14`

### Static Arrays
- `buf`

### SQL Queries (28)
- `SELECT `%s`, LEFT(`%s`, 300) FROM `%s`.`%s` WHERE `%s` LIKE '%%%s%%' LIMIT %d`
- `SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS `
- `SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS `
- `SELECT COUNT(*) FROM `%s`.`%s` WHERE `%s` LIKE '%%%s%%'`
- `SELECT 'learned_rules', COUNT(*) FROM vb_shared.learned_rules`
- `SELECT 'know_problems', COUNT(*) FROM vb_shared.know_problems`
- `SELECT 'know_solutions', COUNT(*) FROM vb_shared.know_solutions`
- `SELECT 'know_questions', COUNT(*) FROM vb_shared.know_questions`
- `SELECT 'know_answers', COUNT(*) FROM vb_shared.know_answers`
- `SELECT 'code_classes', COUNT(*) FROM vb_shared.code_classes`
- `SELECT 'instructions', COUNT(*) FROM vb_shared.instructions`
- `SELECT 'rule_tokens', COUNT(*) FROM vb_shared.rule_tokens`
- `SELECT 'vb_classes', COUNT(*) FROM vb_code_test.vb_classes`
- `SELECT 'vb_methods', COUNT(*) FROM vb_code_test.vb_methods`
- `SELECT 'devin_messages', COUNT(*) FROM devin.devin_messages`
- ... (13 more)

### BCL Packet Patterns (91)
- `[@MATCH]` — `[@TABLE]{%s.%s`
- `[@LABEL]` — `%s`
- `[@ID]` — `%s`
- `[@TEXT]` — `%.400s`
- `[@TABLE]` — `[@DB]{%s`
- `[@NAME]` — `%s`
- `[@ROWS]` — `%s`
- `[@OK]` — `[@KEYWORD]{%s`
- `[@COUNT]` — `[@TABLE]{%s.%s`
- `[@HITS]` — `%d`
- `[@TOTAL]` — `%d`
- `[@KEYWORD]` — `%s`
- `[@OK]` — `");

    
    const char *count_queries[] = {
        "SELEC`
- `[@TABLE]` — `[@NAME]{%s`
- `[@ROWS]` — `%s`
- ... (76 more)

### Global Variables (10)
- `static int ensure_connected`
- `static int search_one_table`
- `static int discover_tables`
- `static int count_keyword`
- `static int stats_all`
- `static int search_files`
- `int Msearch_Init`
- `int Msearch_Run`
- `int Msearch_Close`
- `const char * Msearch_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Msearch_Run` | Msearch_Init, build_match, count_keyword, discover_tables, ensure_connected, search_files, search_one_table, stats_all |
| `count_keyword` | ensure_connected, escape_like |
| `discover_tables` | ensure_connected, escape_sql |
| `search_one_table` | ensure_connected, escape_like, truncate_text |
| `stats_all` | ensure_connected |

### String Literals (first 30)
- `bcl_toolstack.h`
- `vb_shared`
- `learned_rules`
- `pattern`
- `id`
- `pattern`
- `learned_rule`
- `vb_shared`
- `learned_rules`
- `fix_action`
- `id`
- `fix_action`
- `rule_fix`
- `vb_shared`
- `know_problems`
- `problem`
- `id`
- `description`
- `problem`
- `vb_shared`
- `know_solutions`
- `solution`
- `id`
- `solution`
- `solution`
- `vb_shared`
- `know_questions`
- `question`
- `id`
- `question`


---

## bcl_msearch_magnetic.c

| Property | Value |
|---|---|
| Lines | 667 (code: 560, comments: 107) |
| Functions | 10 |
| Dead functions | 0 |
| External calls | 3 |
| Complexity | 76 |
| Risk | MEDIUM |
| Status | **IMPLEMENTED** |
| Domain | mysql |
| SHA | 665a1304fe30 |
| Includes | 2 |
| Defines | 8 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 11 |
| Table refs | devin_messages, code_classes, learned_rules, execution_log, error_knowledge |
| BCL commands | 5 |
| BCL packets | 15 |
| Global vars | 8 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Magnetic radius search and context reconstruction for msearch. Commands: magnetic, chat_radius, graph_radius, read_state, set_config. Expands search results with context neighborhood using radius expansion.

**Class:** MsearchMagnetic

**Declared methods:** Init, Run, Close, State, MagneticSearch, ChatRadius, GraphRadius

### BCL Commands
- `magnetic`
- `chat_radius`
- `graph_radius`
- `read_state`
- `set_config`

### Functions (10)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `ensure_connected` | static int | `void` | 0 | static | 50 | 27 | 3 |  |
| `mag_escape_like` | static void | `const char *in, char *out, size_t out_sz` | 3 | static | 81 | 8 | 2 |  |
| `mag_clean_snippet` | static void | `const char *in, char *out, size_t out_sz` | 3 | static | 91 | 9 | 3 |  |
| `chat_radius_search` | static int | `const char *keyword, int radius,
       ` | 4 | static | 104 | 83 | 5 | LEFT, ensure_connected, mag_clean_snippet, mag_escape_like |
| `graph_radius_search` | static int | `const char *keyword, int radius,
       ` | 4 | static | 192 | 73 | 7 | IN, WHERE, ensure_connected, mag_clean_snippet, mag_escape_like |
| `magnetic_search` | static int | `const char *keyword, int radius,
       ` | 4 | static | 270 | 217 | 8 | chat_radius_search, ensure_connected, graph_radius_search, mag_clean_snippet, mag_escape_like |
| `MsearchMagnetic_Init` | int | `void` | 0 | exported | 492 | 9 | 1 |  |
| `MsearchMagnetic_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 503 | 135 | 4 | MsearchMagnetic_Init, chat_radius_search, ensure_connected, graph_radius_search, magnetic_search |
| `MsearchMagnetic_Close` | int | `void` | 0 | exported | 640 | 8 | 2 |  |
| `MsearchMagnetic_State` | const char | `void` | 0 | exported | 650 | 8 | 1 |  |

### External Calls (3)
- `IN`
- `LEFT`
- `WHERE`

### Includes
- `"bcl_toolstack.h"`
- `<mysql.h>`

### Defines (8)
- `MAG_MAX_QUERY` = `4096`
- `MAG_MAX_RADIUS` = `10000`
- `MAG_DEFAULT_RADIUS` = `200`
- `MAG_HOST_LEN` = `256`
- `MAG_USER_LEN` = `64`
- `MAG_PASS_LEN` = `128`
- `MAG_SOCKET_LEN` = `256`
- `MAG_MAX_OUTPUT` = `65536`

### Static Arrays
- `buf`

### SQL Queries (11)
- `SELECT session_id, row_id, role, LEFT(content, 200) `
- `SELECT role, LEFT(content, 300) FROM devin_messages `
- `SELECT DISTINCT source_method_id, target, edge_type, line_number `
- `SELECT DISTINCT source_method_id, target, edge_type `
- `SELECT class_name, cascade_understanding, layer `
- `SELECT class_name, description FROM code_classes `
- `SELECT pattern, fix_action, confidence FROM learned_rules `
- `SELECT entity_name, entity_type, related_entity, relationship `
- `SELECT command, status, timestamp FROM execution_log `
- `SELECT identifier, identifier_type, authority_score `
- `SELECT error_type, cause, solution FROM error_knowledge `

### BCL Packet Patterns (50)
- `[@MATCH]` — `[@SESSION]{%s`
- `[@HIT_ROW]` — `%d`
- `[@WINDOW]` — `pm%d`
- `[@ROLE]` — `%s`
- `[@PREVIEW]` — `%.400s`
- `[@CONTEXT]` — `%.4000s`
- `[@CALLERS]` — `");
    if (mysql_query(bcl_conn, q) == 0) {
        MYSQL_R`
- `[@TARGET]` — `%s`
- `[@LINE]` — `%s`
- `[@DEPENDENCIES]` — `");
    if (mysql_query(bcl_conn, q) == 0) {
        MYSQL_R`
- `[@TARGET]` — `%s`
- `[@TYPE]` — `%s`
- `[@AUTHORITY]` — `");
    {
        char q[MAG_MAX_QUERY];
        snprintf(q,`
- `[@UNDERSTANDING]` — `%.500s`
- `[@LAYER]` — `%s`
- ... (35 more)

### Global Variables (8)
- `static int ensure_connected`
- `static int chat_radius_search`
- `static int graph_radius_search`
- `static int magnetic_search`
- `int MsearchMagnetic_Init`
- `int MsearchMagnetic_Run`
- `int MsearchMagnetic_Close`
- `const char * MsearchMagnetic_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `MsearchMagnetic_Run` | MsearchMagnetic_Init, chat_radius_search, ensure_connected, graph_radius_search, magnetic_search |
| `chat_radius_search` | ensure_connected, mag_clean_snippet, mag_escape_like |
| `graph_radius_search` | ensure_connected, mag_clean_snippet, mag_escape_like |
| `magnetic_search` | chat_radius_search, ensure_connected, graph_radius_search, mag_clean_snippet, mag_escape_like |

### String Literals (first 30)
- `bcl_toolstack.h`
- `mysql_init failed`
- `/tmp/mysql.sock`
- `connect: %s`
- `/tmp/mysql.sock`
- `devin`
- `SELECT session_id, row_id, role, LEFT(content, 200) `
- `FROM devin_messages WHERE content LIKE '%%%s%%' `
- `ORDER BY created_at DESC LIMIT 5`
- ``
- ``
- ``
- `SELECT role, LEFT(content, 300) FROM devin_messages `
- `WHERE session_id = '%s' AND row_id >= %d AND row_id <= %d `
- `ORDER BY row_id LIMIT 20`
- ``
- ``
- `[%s] %.300s  `
- `[@MATCH]{[@SESSION]{%s}[@HIT_ROW]{%d}[@WINDOW]{pm%d}[@ROLE]{%s}[@PREVIEW]{%.4...`
- `/tmp/mysql.sock`
- `bcl_ir`
- `SELECT DISTINCT source_method_id, target, edge_type, line_number `
- `FROM bcl_edges WHERE (source_method_id LIKE '%%%s%%' `
- `OR target LIKE '%%%s%%') AND edge_type = 'CALL' LIMIT 10`
- `[@CALLERS]{`
- ``
- ``
- `[@EDGE]{[@SOURCE]{%s}[@TARGET]{%s}[@LINE]{%s}}`
- `0`
- `}`


---

## bcl_pb_reader.c

| Property | Value |
|---|---|
| Lines | 667 (code: 546, comments: 121) |
| Functions | 14 |
| Dead functions | 0 |
| External calls | 12 |
| Complexity | 95 |
| Risk | HIGH |
| Status | **IMPLEMENTED** |
| Domain | crypto, filesystem, search |
| SHA | 49942c33f158 |
| Includes | 5 |
| Defines | 14 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 4 |
| #ifdef blocks | 0 |
| SQL queries | 23 |
| Table refs | IF, trajectories, steps, user_messages, assistant_messages, commands, checkpoints |
| BCL commands | 6 |
| BCL packets | 10 |
| Global vars | 16 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Decrypts .pb chat files (AES-256-GCM), parses protobuf wire-format, loads into in-RAM SQLite, searches chat history. Commands: scan, load, load-all, read, search, export, stats, read_state, set_config.

**Class:** PbReader

**Declared methods:** Init, Run, Close, State, DecryptFile, ParseTrajectory, LoadToRam, Search, Read, Export

### BCL Commands
- `scan`
- `load-all`
- `search`
- `stats`
- `read_state`
- `set_config`

### Functions (14)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `read_varint` | static int | `const unsigned char *buf, int buf_len, i` | 4 | static | 68 | 14 | 3 |  |
| `parse_tag` | static int | `int tag, int *field_no, int *wire_type` | 3 | static | 84 | 4 | 1 |  |
| `skip_value` | static int | `const unsigned char *buf, int buf_len, i` | 4 | static | 90 | 17 | 3 | read_varint |
| `read_string_field` | static int | `const unsigned char *data, int data_len,` | 5 | static | 109 | 24 | 3 | parse_tag, read_varint, skip_value |
| `decrypt_file` | static int | `const char *path, unsigned char *out, in` | 3 | static | 138 | 49 | 2 |  |
| `init_db` | static int | `void` | 0 | static | 191 | 51 | 1 | DEFAULT, KEY, assistant_messages, checkpoints, commands (+4) |
| `scan_dir` | static int | `const char *dir_path, const char *catego` | 2 | static | 246 | 12 | 2 |  |
| `extract_step_string` | static int | `const unsigned char *data, int data_len,` | 5 | static | 263 | 30 | 4 | parse_tag, read_varint, skip_value |
| `deep_extract_string` | static int | `const unsigned char *data, int data_len,` | 6 | static | 297 | 36 | 4 | deep_extract_string, parse_tag, read_varint, skip_value |
| `load_one` | static int | `const char *pb_path, const char *categor` | 2 | static | 339 | 151 | 5 | VALUES, assistant_messages, checkpoints, commands, decrypt_file (+7) |
| `PbReader_Init` | int | `void` | 0 | exported | 494 | 8 | 2 | getenv |
| `PbReader_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 504 | 142 | 6 | COUNT, PbReader_Init, init_db, load_one, scan_dir |
| `PbReader_Close` | int | `void` | 0 | exported | 648 | 7 | 2 |  |
| `PbReader_State` | const char | `void` | 0 | exported | 657 | 7 | 1 |  |

### External Calls (12)
- `COUNT`
- `DEFAULT`
- `KEY`
- `VALUES`
- `assistant_messages`
- `checkpoints`
- `commands`
- `datetime`
- `getenv`
- `steps`
- `trajectories`
- `user_messages`

### Includes
- `"bcl_toolstack.h"`
- `<openssl/evp.h>`
- `<openssl/aes.h>`
- `<dirent.h>`
- `<sys/stat.h>`

### Defines (14)
- `NONCE_SIZE` = `12`
- `TAG_SIZE` = `16`
- `MAX_PB_SIZE` = `10485760`
- `WIRE_VARINT` = `0`
- `WIRE_64BIT` = `1`
- `WIRE_LENGTH` = `2`
- `WIRE_32BIT` = `5`
- `WIRE_GROUP_END` = `4`
- `VARIANT_USER_INPUT` = `19`
- `VARIANT_PLANNER_RESPONSE` = `20`
- `VARIANT_RUN_COMMAND` = `28`
- `VARIANT_CHECKPOINT` = `30`
- `WINDSURF_ROOT_LEN` = `4096`
- `PB_DIR_COUNT` = `3`

### Static Arrays
- `PB_AES_KEY`
- `WINDSURF_ROOT`
- `plaintext`
- `buf`

### SQL Queries (23)
- `CREATE TABLE IF NOT EXISTS trajectories (`
- `CREATE TABLE IF NOT EXISTS steps (`
- `CREATE TABLE IF NOT EXISTS user_messages (`
- `CREATE TABLE IF NOT EXISTS assistant_messages (`
- `CREATE TABLE IF NOT EXISTS commands (`
- `CREATE TABLE IF NOT EXISTS checkpoints (`
- `CREATE INDEX IF NOT EXISTS idx_steps_traj ON steps(trajectory_fk);`
- `CREATE INDEX IF NOT EXISTS idx_user_traj ON user_messages(trajectory_fk);`
- `CREATE INDEX IF NOT EXISTS idx_asst_traj ON assistant_messages(trajectory_fk);`
- `CREATE INDEX IF NOT EXISTS idx_cmd_traj ON commands(trajectory_fk);`
- `CREATE INDEX IF NOT EXISTS idx_cp_traj ON checkpoints(trajectory_fk);`
- `INSERT OR REPLACE INTO trajectories `
- `INSERT INTO steps (trajectory_fk, step_index, step_type, variant_field) `
- `INSERT INTO user_messages (trajectory_fk, step_index, prompt) `
- `INSERT INTO assistant_messages (trajectory_fk, step_index, user_facing) `
- ... (8 more)

### BCL Packet Patterns (24)
- `[@COUNT]` — `%d`
- `[@ROOT]` — `%s`
- `[@LOADED]` — `%d`
- `[@SCANNED]` — `%d`
- `[@OK]` — `[@COUNT]{0`
- `[@MATCH]` — `[@STEP]{%d`
- `[@FILE]` — `%s`
- `[@TEXT]` — `%.200s`
- `[@COUNT]` — `%d`
- `[@COUNT]` — `0`
- `[@COUNT]` — `0`
- `[@TRAJECTORIES]` — `%d`
- `[@USER_MSGS]` — `%d`
- `[@AI_MSGS]` — `%d`
- `[@COMMANDS]` — `%d`
- ... (9 more)

### Global Variables (16)
- `static const unsigned char PB_AES_KEY[`
- `static char WINDSURF_ROOT[`
- `static int read_varint`
- `static int parse_tag`
- `static int skip_value`
- `static int read_string_field`
- `static int decrypt_file`
- `static int init_db`
- `static int scan_dir`
- `static int extract_step_string`
- `static int deep_extract_string`
- `static int load_one`
- `int PbReader_Init`
- `int PbReader_Run`
- `int PbReader_Close`
- `const char * PbReader_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `PbReader_Run` | PbReader_Init, init_db, load_one, scan_dir |
| `deep_extract_string` | parse_tag, read_varint, skip_value |
| `extract_step_string` | parse_tag, read_varint, skip_value |
| `load_one` | decrypt_file, deep_extract_string, init_db, parse_tag, read_varint, skip_value |
| `read_string_field` | parse_tag, read_varint, skip_value |
| `skip_value` | read_varint |

### String Literals (first 30)
- `bcl_toolstack.h`
- `cascade`
- `implicit`
- `memories`
- `rb`
- `:memory:`
- `CREATE TABLE IF NOT EXISTS trajectories (`
- `  id INTEGER PRIMARY KEY AUTOINCREMENT,`
- `  trajectory_id TEXT, cascade_id TEXT,`
- `  file_path TEXT UNIQUE, file_category TEXT,`
- `  trajectory_type INTEGER, source INTEGER,`
- `  steps_count INTEGER, decrypted_size INTEGER,`
- `  loaded_at TEXT DEFAULT (datetime('now')));`
- `CREATE TABLE IF NOT EXISTS steps (`
- `  id INTEGER PRIMARY KEY AUTOINCREMENT,`
- `  trajectory_fk INTEGER, step_index INTEGER,`
- `  step_type INTEGER, step_type_name TEXT,`
- `  status INTEGER, variant_field INTEGER,`
- `  variant_data BLOB,`
- `  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));`
- `CREATE TABLE IF NOT EXISTS user_messages (`
- `  id INTEGER PRIMARY KEY AUTOINCREMENT,`
- `  trajectory_fk INTEGER, step_index INTEGER,`
- `  prompt TEXT,`
- `  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));`
- `CREATE TABLE IF NOT EXISTS assistant_messages (`
- `  id INTEGER PRIMARY KEY AUTOINCREMENT,`
- `  trajectory_fk INTEGER, step_index INTEGER,`
- `  user_facing TEXT, internal_planning TEXT,`
- `  FOREIGN KEY (trajectory_fk) REFERENCES trajectories(id));`


---

## bcl_msearch_qdrant.c

| Property | Value |
|---|---|
| Lines | 647 (code: 550, comments: 97) |
| Functions | 7 |
| Dead functions | 0 |
| External calls | 5 |
| Complexity | 77 |
| Risk | MEDIUM |
| Status | **IMPLEMENTED** |
| Domain | mysql |
| SHA | 60ffc2d17387 |
| Includes | 2 |
| Defines | 10 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 12 |
| Table refs | class_understandings, code_classes, learned_rules, code_registry, execution_log, error_knowledge, designrationale, know_problems, decision_trees |
| BCL commands | 6 |
| BCL packets | 18 |
| Global vars | 5 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Qdrant vector search and semantic object search for msearch. Commands: semantic, multi, full, qstats, read_state, set_config. Calls Qdrant helper script for vector search, supports multi-dimension and full semantic object search.

**Class:** MsearchQdrant

**Declared methods:** Init, Run, Close, State, SemanticSearch, MultiDimension, FullObjectSearch, QdrantStats

### BCL Commands
- `semantic`
- `multi`
- `full`
- `qstats`
- `read_state`
- `set_config`

### Functions (7)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `qdr_escape_like` | static void | `const char *in, char *out, size_t out_sz` | 3 | static | 53 | 8 | 2 |  |
| `qdr_clean` | static void | `const char *in, char *out, size_t out_sz` | 3 | static | 63 | 9 | 3 |  |
| `run_qdrant` | static int | `const char *query, const char *collectio` | 5 | static | 89 | 25 | 3 | pclose, popen |
| `MsearchQdrant_Init` | int | `void` | 0 | exported | 119 | 10 | 1 |  |
| `MsearchQdrant_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 131 | 0 | 0 |  |
| `MsearchQdrant_Close` | int | `void` | 0 | exported | 625 | 3 | 1 |  |
| `MsearchQdrant_State` | const char | `void` | 0 | exported | 630 | 7 | 1 |  |

### External Calls (5)
- `LEFT`
- `pclose`
- `popen`
- `qdr_connect`
- `strtok`

### Includes
- `"bcl_toolstack.h"`
- `<mysql.h>`

### Defines (10)
- `QDRANT_HELPER` = `"/Users/wws/bin/msearch_qdrant.py"`
- `QDRANT_DEFAULT_COLL` = `"dim_semantic"`
- `QDRANT_DEFAULT_TOP` = `10`
- `QDRANT_MAX_QUERY` = `4096`
- `QDRANT_MAX_DIM` = `128`
- `QDRANT_MAX_OUTPUT` = `65536`
- `QDRANT_HOST_LEN` = `256`
- `QDRANT_USER_LEN` = `64`
- `QDRANT_PASS_LEN` = `128`
- `QDRANT_SOCKET_LEN` = `256`

### Static Arrays
- `buf`

### SQL Queries (12)
- `SELECT class_name, cascade_understanding, layer FROM class_understandings `
- `SELECT class_name, description FROM code_classes `
- `SELECT entity_name, entity_type, related_entity, relationship `
- `SELECT entity_a, entity_b, relationship_type, weight `
- `SELECT pattern, fix_action, confidence FROM learned_rules `
- `SELECT token_name, LEFT(code, 500) FROM code_registry `
- `SELECT command, status, timestamp FROM execution_log `
- `SELECT error_type, cause, solution FROM error_knowledge `
- `SELECT identifier, identifier_type, authority_score `
- `SELECT subject, rationale, category FROM designrationale `
- `SELECT problem, description FROM know_problems `
- `SELECT tree FROM decision_trees WHERE tree LIKE '%%%s%%' LIMIT %d`

### BCL Packet Patterns (56)
- `[@OK]` — `[@QUERY]{%s`
- `[@COLLECTION]` — `%s`
- `[@TOP]` — `%d`
- `[@RESULTS]` — `%.60000s`
- `[@OK]` — `[@QUERY]{%s`
- `[@RESULTS]` — `", query);

        char *dim = strtok(dims, ",");
        i`
- `[@HITS]` — `%.6000s`
- `[@DIM_COUNT]` — `%d`
- `[@OK]` — `[@QUERY]{%s`
- `[@SECTIONS]` — `", query);

        
        offset += snprintf(bcl_out + of`
- `[@UNDERSTANDING]` — `%.500s`
- `[@LAYER]` — `%s`
- `[@FILES]` — `");
        {
            char q[QDRANT_MAX_QUERY];
        `
- `[@DESCRIPTION]` — `%.300s`
- `[@METHODS]` — `");
        {
            char q[QDRANT_MAX_QUERY];
        `
- ... (41 more)

### Global Variables (5)
- `static int run_qdrant`
- `int MsearchQdrant_Init`
- `int MsearchQdrant_Run`
- `int MsearchQdrant_Close`
- `const char * MsearchQdrant_State`

### String Literals (first 30)
- `bcl_toolstack.h`
- `/Users/wws/bin/msearch_qdrant.py`
- `dim_semantic`
- `/tmp/mysql.sock`
- `python3 %s --query '%s' --collection %s --top %d 2>/dev/null`
- `r`
- `popen failed for qdrant helper`
- `localhost`
- `root`
- `/tmp/mysql.sock`
- `semantic`
- `QUERY`
- `DIMENSION`
- `TOP`
- `no QUERY in packet`
- `[@OK]{[@QUERY]{%s}[@COLLECTION]{%s}[@TOP]{%d}[@RESULTS]{%.60000s}}`
- `multi`
- `QUERY`
- `DIMENSIONS`
- `no QUERY in packet`
- `dim_semantic,dim_code,dim_errors`
- `[@OK]{[@QUERY]{%s}[@RESULTS]{`
- `,`
- `[@DIM]{[@NAME]{%s}[@HITS]{%.6000s}}`
- `,`
- `[@DIM_COUNT]{%d}}`
- `full`
- `QUERY`
- `TOP`
- `no QUERY in packet`


---

## bcl_msearch_ranking.c

| Property | Value |
|---|---|
| Lines | 455 (code: 359, comments: 96) |
| Functions | 8 |
| Dead functions | 0 |
| External calls | 1 |
| Complexity | 81 |
| Risk | HIGH |
| Status | **IMPLEMENTED** |
| Domain | mysql |
| SHA | e18df71c9996 |
| Includes | 2 |
| Defines | 9 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 4 |
| Table refs | table_registry, INFORMATION_SCHEMA |
| BCL commands | 6 |
| BCL packets | 9 |
| Global vars | 6 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Context-aware ranking and class understandings for msearch. Commands: rank, update_route, understandings, read_state, set_config. Scores search results by relevance using context keywords and class understanding integration.

**Class:** MsearchRanking

**Declared methods:** Init, Run, Close, State, ScoreRelevance, UpdateRoute, LoadUnderstandings

### BCL Commands
- `rank`
- `update_route`
- `understandings`
- `where_to_store`
- `read_state`
- `set_config`

### Functions (8)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `ensure_connected` | static int | `void` | 0 | static | 51 | 27 | 3 |  |
| `rank_clean` | static void | `const char *in, char *out, size_t out_sz` | 3 | static | 82 | 9 | 3 |  |
| `score_relevance` | static int | `const char *table_name, const char *keyw` | 3 | static | 95 | 57 | 5 | ensure_connected |
| `resolve_update_route` | static const char | `const char *table_name` | 1 | static | 156 | 15 | 1 |  |
| `MsearchRanking_Init` | int | `void` | 0 | exported | 175 | 8 | 1 |  |
| `MsearchRanking_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 185 | 0 | 0 |  |
| `MsearchRanking_Close` | int | `void` | 0 | exported | 429 | 8 | 2 |  |
| `MsearchRanking_State` | const char | `void` | 0 | exported | 439 | 7 | 1 |  |

### External Calls (1)
- `instructions`

### Includes
- `"bcl_toolstack.h"`
- `<mysql.h>`

### Defines (9)
- `RANK_MAX_CONTEXT` = `256`
- `RANK_MAX_TABLE` = `128`
- `RANK_MAX_CLASS` = `128`
- `RANK_MAX_UNDERSTAND` = `512`
- `RANK_HOST_LEN` = `256`
- `RANK_USER_LEN` = `64`
- `RANK_PASS_LEN` = `128`
- `RANK_SOCKET_LEN` = `256`
- `RANK_MAX_QUERY` = `4096`

### Static Arrays
- `buf`

### SQL Queries (4)
- `SELECT purpose, `contains`, notes, table_type FROM table_registry `
- `SELECT class_name, cascade_understanding, layer, code_classes_id `
- `SELECT table_name, table_type, purpose, `contains`, notes `
- `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS `

### BCL Packet Patterns (31)
- `[@TABLE]` — `%s`
- `[@KEYWORD]` — `%s`
- `[@CONTEXT]` — `%s`
- `[@SCORE]` — `%d`
- `[@TABLE]` — `%s`
- `[@ROUTE]` — `%s`
- `[@CLASS]` — `%s`
- `[@STATUS]` — `not_found`
- `[@CLASS]` — `%s`
- `[@UNDERSTANDING]` — `%.500s`
- `[@LAYER]` — `%s`
- `[@CODE_ID]` — `%s`
- `[@OK]` — `[@QUERY]{%s`
- `[@SUGGESTIONS]` — `", keyword);

        MYSQL_ROW row;
        int count = 0;
`
- `[@TYPE]` — `%s`
- ... (16 more)

### Global Variables (6)
- `static int ensure_connected`
- `static int score_relevance`
- `int MsearchRanking_Init`
- `int MsearchRanking_Run`
- `int MsearchRanking_Close`
- `const char * MsearchRanking_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `score_relevance` | ensure_connected |

### String Literals (first 30)
- `bcl_toolstack.h`
- `mysql_init failed`
- `/tmp/mysql.sock`
- `vb_shared`
- `vb_shared`
- `connect: %s`
- `SELECT purpose, `contains`, notes, table_type FROM table_registry `
- `WHERE table_name = '%s'`
- ``
- ``
- ``
- ``
- `meta`
- `code`
- `code`
- `token`
- `database`
- `database`
- `rule`
- `code`
- `class`
- `error`
- `problem`
- `chat`
- `message`
- `learned_rules`
- `know_problems`
- `know_solutions`
- `know_answers`
- `devin_messages`


---

## bcl_msearch_registry.c

| Property | Value |
|---|---|
| Lines | 380 (code: 303, comments: 77) |
| Functions | 9 |
| Dead functions | 0 |
| External calls | 2 |
| Complexity | 46 |
| Risk | MEDIUM |
| Status | **IMPLEMENTED** |
| Domain | mysql |
| SHA | 9b46a800cc44 |
| Includes | 2 |
| Defines | 7 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 5 |
| Table refs | table_registry, information_schema |
| BCL commands | 5 |
| BCL packets | 10 |
| Global vars | 8 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Registry-first routing and schema loading for msearch. Commands: load_registry, detect_route, schema, read_state, set_config. Loads table_registry metadata, detects keyword routing patterns, discovers MySQL schema.

**Class:** MsearchRegistry

**Declared methods:** Init, Run, Close, State, LoadRegistry, DetectRoute, DiscoverSchema

### BCL Commands
- `load_registry`
- `detect_route`
- `schema`
- `read_state`
- `set_config`

### Functions (9)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `ensure_connected` | static int | `void` | 0 | static | 62 | 27 | 3 |  |
| `load_registry` | static int | `char *out, size_t out_sz, int *offset` | 3 | static | 93 | 41 | 4 | COUNT, ensure_connected |
| `detect_route` | static const char | `const char *keyword` | 1 | static | 138 | 12 | 1 |  |
| `is_text_type` | static int | `const char *type` | 1 | static | 154 | 7 | 1 |  |
| `discover_schema` | static int | `const char *db_filter, char *out, size_t` | 4 | static | 165 | 63 | 7 | IN, ensure_connected, is_text_type, load_registry |
| `MsearchRegistry_Init` | int | `void` | 0 | exported | 232 | 8 | 1 |  |
| `MsearchRegistry_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 242 | 110 | 5 | MsearchRegistry_Init, detect_route, discover_schema, ensure_connected, load_registry |
| `MsearchRegistry_Close` | int | `void` | 0 | exported | 354 | 8 | 2 |  |
| `MsearchRegistry_State` | const char | `void` | 0 | exported | 364 | 7 | 1 |  |

### External Calls (2)
- `COUNT`
- `IN`

### Includes
- `"bcl_toolstack.h"`
- `<mysql.h>`

### Defines (7)
- `REG_MAX_TABLES` = `1024`
- `REG_MAX_COLS` = `512`
- `REG_MAX_DB` = `64`
- `REG_HOST_LEN` = `256`
- `REG_USER_LEN` = `64`
- `REG_PASS_LEN` = `128`
- `REG_SOCKET_LEN` = `256`

### Static Arrays
- `buf`

### SQL Queries (5)
- `SELECT COUNT(*) FROM table_registry`
- `SELECT table_name, table_type, purpose, `contains`, notes, related_tables `
- `SHOW TABLES FROM `%s``
- `SELECT TABLE_NAME FROM information_schema.TABLES `
- `SELECT COLUMN_NAME, DATA_TYPE `

### BCL Packet Patterns (21)
- `[@REG]` — `[@TABLE]{%s`
- `[@TYPE]` — `%s`
- `[@PURPOSE]` — `%.200s`
- `[@TABLE]` — `%s`
- `[@OK]` — `");
        int loaded = load_registry(bcl_out, out_sz, &off`
- `[@QUERY]` — `%s`
- `[@ROUTE]` — `%s`
- `[@OK]` — `[@TOTAL]{0`
- `[@TOTAL]` — `%d`
- `[@TOTAL]` — `0`
- `[@TOTAL]` — `0`
- `[@INITIALIZED]` — `%d`
- `[@CONNECTED]` — `%d`
- `[@TABLES]` — `%d`
- `[@REGISTRIES]` — `%d`
- ... (6 more)

### Global Variables (8)
- `static int ensure_connected`
- `static int load_registry`
- `static int is_text_type`
- `static int discover_schema`
- `int MsearchRegistry_Init`
- `int MsearchRegistry_Run`
- `int MsearchRegistry_Close`
- `const char * MsearchRegistry_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `MsearchRegistry_Run` | MsearchRegistry_Init, detect_route, discover_schema, ensure_connected, load_registry |
| `discover_schema` | ensure_connected, is_text_type, load_registry |
| `load_registry` | ensure_connected |

### String Literals (first 30)
- `bcl_toolstack.h`
- `mysql_init failed`
- `/tmp/mysql.sock`
- `connect: %s`
- `SELECT COUNT(*) FROM table_registry`
- `SELECT table_name, table_type, purpose, `contains`, notes, related_tables `
- `FROM table_registry`
- ``
- ``
- ``
- ``
- ``
- ``
- `[@REG]{[@TABLE]{%s}[@TYPE]{%s}[@PURPOSE]{%.200s}}`
- ``
- ``
- `token_table`
- `dom_`
- `code_table`
- `INTENT`
- `PURPOSE`
- `code_table`
- `err`
- `error`
- `fix`
- `token_table`
- `workflow`
- `flow`
- `token_table`
- `char`


---

## bcl_tool_main.c

| Property | Value |
|---|---|
| Lines | 322 (code: 257, comments: 65) |
| Functions | 15 |
| Dead functions | 6 |
| External calls | 3 |
| Complexity | 40 |
| Risk | MEDIUM |
| Status | **IMPLEMENTED** |
| Domain | unknown |
| SHA | eac4b08792df |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 2 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 0 |
| BCL packets | 5 |
| Global vars | 12 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Entry point for BCL tool stack. CLI: bcl_tool list | bcl_tool <unit> <command> [bcl_input] | bcl_tool dispatch <bcl_packet>. Registers 17 units, dispatches BCL packets, returns BCL results.

**Class:** ToolStack

**Declared methods:** Run, Init, Close, RegisterAll, Dispatch, ListUnits, read_state, set_config

### Functions (15)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `BclResult_Ok` | int | `char *out, size_t out_sz, const char *bo` | 3 | exported | 25 | 3 | 2 |  |
| `BclResult_Err` | int | `char *out, size_t out_sz, int code, cons` | 4 | exported | 30 | 3 | 3 |  |
| `BclResult_Data` | int | `char *out, size_t out_sz, const char *ke` | 4 | exported | 35 | 3 | 3 |  |
| `BclParser_Init` | void | `BclParseResult *p` | 1 | exported | 42 | 2 | 1 |  |
| `BclParser_Parse` | int | `BclParseResult *p, const char *bcl_text` | 2 | exported | 46 | 0 | 0 |  |
| `BclParser_Extract` | int | `BclParseResult *p, const char *tag, char` | 4 | exported | 121 | 9 | 3 |  |
| `BclParser_Free` | void | `BclParseResult *p` | 1 | exported | 132 | 2 | 1 |  |
| `ToolStack_Init` | void | `ToolStack *ts, const char *db_path` | 2 | exported | 138 | 4 | 1 |  |
| `ToolStack_Close` | void | `ToolStack *ts` | 1 | exported | 144 | 12 | 3 | close |
| `ToolStack_RegisterUnit` | int | `ToolStack *ts, const char *name,
       ` | 8 | exported | 158 | 12 | 1 |  |
| `ToolStack_Dispatch` | int | `ToolStack *ts, const char *unit_name,
  ` | 6 | exported | 175 | 16 | 5 | init, run |
| `ToolStack_ListUnits` | int | `ToolStack *ts, char *out, size_t out_sz` | 3 | exported | 195 | 13 | 5 |  |
| `ToolStack_Run` | const char | `ToolStack *ts, const char *command, cons` | 3 | exported | 210 | 35 | 3 | ToolStack_Dispatch, ToolStack_ListUnits |
| `RegisterAll` | static void | `ToolStack *ts` | 1 | static | 249 | 22 | 1 | ToolStack_RegisterUnit |
| `main` | int | `int argc, char *argv[]` | 2 | exported | 275 | 47 | 3 | RegisterAll, ToolStack_Close, ToolStack_Dispatch, ToolStack_Init, ToolStack_Run |

### Dead Functions (6)
Defined but never called in this file:

- `BclResult_Ok`
- `BclResult_Err`
- `BclParser_Init`
- `BclParser_Parse`
- `BclParser_Extract`
- `BclParser_Free`

### External Calls (3)
- `close`
- `init`
- `run`

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `RESULT_BUF`
- `INPUT_BUF`

### BCL Packet Patterns (9)
- `[@OK]` — `%s`
- `[@ERR]` — `[@CODE]{%d`
- `[@DESC]` — `%s`
- `[@OK]` — `[@%s]{%s`
- `[@OK]` — `[@COUNT]{%d`
- `[@UNIT]` — `[@NAME]{%s`
- `[@CATEGORY]` — `%s`
- `[@HELP]` — `%s`
- `[@STATUS]` — `%s`

### Global Variables (12)
- `static char RESULT_BUF[`
- `static char INPUT_BUF[`
- `int BclResult_Ok`
- `int BclResult_Err`
- `int BclResult_Data`
- `int BclParser_Parse`
- `int BclParser_Extract`
- `int ToolStack_RegisterUnit`
- `int ToolStack_Dispatch`
- `int ToolStack_ListUnits`
- `const char * ToolStack_Run`
- `int main`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `RegisterAll` | ToolStack_RegisterUnit |
| `ToolStack_Dispatch` | BclResult_Err |
| `ToolStack_Run` | BclParser_Extract, BclParser_Free, BclParser_Init, BclParser_Parse, BclResult_Err, ToolStack_Dispatch, ToolStack_ListUnits |
| `main` | RegisterAll, ToolStack_Close, ToolStack_Dispatch, ToolStack_Init, ToolStack_Run |

### String Literals (first 30)
- `bcl_toolstack.h`
- `[@OK]{%s}`
- ``
- `[@ERR]{[@CODE]{%d}[@DESC]{%s}}`
- ``
- `[@OK]{[@%s]{%s}}`
- `DATA`
- ``
- `empty input`
- `cascade_tools.db`
- `unit init failed`
- `unit has no run function`
- `unit not found`
- `[@OK]{[@COUNT]{%d}`
- `[@UNIT]{[@NAME]{%s}[@CATEGORY]{%s}[@HELP]{%s}[@STATUS]{%s}}`
- `active`
- `pending`
- `}`
- `list`
- `dispatch`
- `invalid BCL packet`
- `UNIT`
- `CMD`
- `no UNIT in packet`
- `no CMD in packet`
- `unknown command`
- `pb_reader`
- `chat`
- `Encrypted .pb chat file reader`
- `chat_ingest`


---

## bcl_msearch_help.c

| Property | Value |
|---|---|
| Lines | 158 (code: 112, comments: 46) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 1 |
| Complexity | 12 |
| Risk | LOW |
| Status | **IMPLEMENTED** |
| Domain | unknown |
| SHA | 358b2a2b79c0 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 5 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Help and AI guidance for msearch. Commands: help, rules, usage, read_state, set_config. Stores the rules about examining all results before reasoning. When the AI runs msearch help it gets back the guidance text.

**Class:** MsearchHelp

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `help`
- `rules`
- `usage`
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `MsearchHelp_Init` | int | `void` | 0 | exported | 95 | 4 | 1 |  |
| `MsearchHelp_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 101 | 35 | 3 | MsearchHelp_Init |
| `MsearchHelp_Close` | int | `void` | 0 | exported | 138 | 3 | 1 |  |
| `MsearchHelp_State` | const char | `void` | 0 | exported | 143 | 6 | 1 |  |

### External Calls (1)
- `table`

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (14)
- `[@RUN]` — `[@CMD]{search`
- `[@QUERY]` — `keyword`
- `[@LIMIT]` — `50`
- `[@RUN]` — `[@CMD]{count`
- `[@QUERY]` — `keyword`
- `[@RUN]` — `[@CMD]{where`
- `[@DB]` — `vb_shared`
- `[@RUN]` — `[@CMD]{stats`
- `[@RUN]` — `[@CMD]{help`
- `[@RUN]` — `[@CMD]{rules`
- `[@INITIALIZED]` — `%d`
- `[@HELP_REQUESTS]` — `%d`
- `[@RULE_REQUESTS]` — `%d`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int MsearchHelp_Init`
- `int MsearchHelp_Run`
- `int MsearchHelp_Close`
- `const char * MsearchHelp_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `MsearchHelp_Run` | MsearchHelp_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `msearch — MySQL keyword search across knowledge databases\n`
- `\n`
- `Commands:\n`
- `  search <keyword>   Search all known tables for keyword\n`
- `  count <keyword>    Count matches per table\n`
- `  where [db]         List tables in database\n`
- `  stats              Show database statistics\n`
- `  help               Show this help text\n`
- `  rules              Show AI usage rules\n`
- `  usage              Show usage examples\n`
- `  read_state         Show current state\n`
- `  set_config         Set connection config\n`
- `\n`
- `Options:\n`
- `  --limit N          Max results per table (default 50)\n`
- `  --mode M           Match mode: exact, prefix, contains, regex\n`
- `  --json             JSON output mode\n`
- `  --all-db           Search across all databases\n`
- `  --semantic         Qdrant vector search\n`
- `  --hybrid           MySQL + Qdrant combined\n`
- `  --magnetic         Context reconstruction with radius\n`
- `  --radius N         Expansion size for magnetic mode\n`
- `  --count            Show match counts only, no rows\n`
- `  --verbose          Verbose output\n`
- `RULE 1: Do not stop on the first result. Collect all results. Reason over all...`
- `  When msearch returns multiple matches, you must examine every match before ...`
- `  Stopping at the first result and missing the answer in result 18 is a failu...`
- `\n`
- `RULE 2: Use the requested tool. Do not substitute.\n`


---

## bcl_chat_ingest.c

| Property | Value |
|---|---|
| Lines | 57 (code: 42, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **PARTIAL** |
| Domain | unknown |
| SHA | 728596f2f9f7 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** AST-based code ingester. Indexes .py files into SQLite with VBStyle compliance flags. Stub — commands: ingest, schema, summary, list_files, read_state, set_config.

**Class:** ChatIngest

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `ChatIngest_Init` | int | `void` | 0 | exported | 21 | 4 | 1 |  |
| `ChatIngest_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 27 | 19 | 3 | ChatIngest_Init |
| `ChatIngest_Close` | int | `void` | 0 | exported | 48 | 3 | 1 |  |
| `ChatIngest_State` | const char | `void` | 0 | exported | 53 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (5)
- `[@INITIALIZED]` — `%d`
- `[@FILES]` — `%d`
- `[@CLASSES]` — `%d`
- `[@METHODS]` — `%d`
- `[@DB_PATH]` — `%s`

### Global Variables (4)
- `int ChatIngest_Init`
- `int ChatIngest_Run`
- `int ChatIngest_Close`
- `const char * ChatIngest_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `ChatIngest_Run` | ChatIngest_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{%d}[@FILES]{%d}[@CLASSES]{%d}[@METHODS]{%d}`
- `set_config`
- `DB_PATH`
- `[@DB_PATH]{%s}`
- `not implemented — stub unit`
- `ChatIngest: initialized=%d files=%d`


---

## bcl_cleaner.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 6e286a6cc0c7 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Cache and junk cleaner. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Cleaner

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Cleaner_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Cleaner_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Cleaner_Init |
| `Cleaner_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Cleaner_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Cleaner_Init`
- `int Cleaner_Run`
- `int Cleaner_Close`
- `const char * Cleaner_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Cleaner_Run` | Cleaner_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Cleaner: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_codeingest.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | b7d920837be0 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Code ingestion engine. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Codeingest

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Codeingest_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Codeingest_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Codeingest_Init |
| `Codeingest_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Codeingest_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Codeingest_Init`
- `int Codeingest_Run`
- `int Codeingest_Close`
- `const char * Codeingest_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Codeingest_Run` | Codeingest_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Codeingest: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_cognitive_core.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | c8016b3699e4 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Cognitive core engine. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** CognitiveCore

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `CognitiveCore_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `CognitiveCore_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | CognitiveCore_Init |
| `CognitiveCore_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `CognitiveCore_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int CognitiveCore_Init`
- `int CognitiveCore_Run`
- `int CognitiveCore_Close`
- `const char * CognitiveCore_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `CognitiveCore_Run` | CognitiveCore_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `CognitiveCore: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_discovery.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 13f4f0c0ef3a |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Code discovery and analysis. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Discovery

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Discovery_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Discovery_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Discovery_Init |
| `Discovery_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Discovery_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Discovery_Init`
- `int Discovery_Run`
- `int Discovery_Close`
- `const char * Discovery_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Discovery_Run` | Discovery_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Discovery: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_error_fix.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 340fbf87b4a9 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Error fix trainer. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** ErrorFix

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `ErrorFix_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `ErrorFix_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | ErrorFix_Init |
| `ErrorFix_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `ErrorFix_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int ErrorFix_Init`
- `int ErrorFix_Run`
- `int ErrorFix_Close`
- `const char * ErrorFix_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `ErrorFix_Run` | ErrorFix_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `ErrorFix: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_ghostctl.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 4b66d9c80799 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** System-wide cleanup control. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Ghostctl

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Ghostctl_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Ghostctl_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Ghostctl_Init |
| `Ghostctl_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Ghostctl_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Ghostctl_Init`
- `int Ghostctl_Run`
- `int Ghostctl_Close`
- `const char * Ghostctl_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Ghostctl_Run` | Ghostctl_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Ghostctl: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_magnetic.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | b00e28934c64 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Magnetic radius search. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Magnetic

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Magnetic_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Magnetic_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Magnetic_Init |
| `Magnetic_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Magnetic_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Magnetic_Init`
- `int Magnetic_Run`
- `int Magnetic_Close`
- `const char * Magnetic_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Magnetic_Run` | Magnetic_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Magnetic: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_mdmerge.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 786052256769 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Markdown file merger. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Mdmerge

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Mdmerge_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Mdmerge_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Mdmerge_Init |
| `Mdmerge_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Mdmerge_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Mdmerge_Init`
- `int Mdmerge_Run`
- `int Mdmerge_Close`
- `const char * Mdmerge_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Mdmerge_Run` | Mdmerge_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Mdmerge: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_schemalint.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 3200781644ed |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Database schema linter. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Schemalint

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Schemalint_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Schemalint_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Schemalint_Init |
| `Schemalint_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Schemalint_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Schemalint_Init`
- `int Schemalint_Run`
- `int Schemalint_Close`
- `const char * Schemalint_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Schemalint_Run` | Schemalint_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Schemalint: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_smartcli.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 6db7188f8998 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Smart CLI executor. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Smartcli

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Smartcli_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Smartcli_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Smartcli_Init |
| `Smartcli_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Smartcli_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Smartcli_Init`
- `int Smartcli_Run`
- `int Smartcli_Close`
- `const char * Smartcli_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Smartcli_Run` | Smartcli_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Smartcli: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_vbcheck.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | cd8d785d81f5 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** VBStyle compliance checker. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Vbcheck

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Vbcheck_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Vbcheck_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Vbcheck_Init |
| `Vbcheck_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Vbcheck_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Vbcheck_Init`
- `int Vbcheck_Run`
- `int Vbcheck_Close`
- `const char * Vbcheck_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Vbcheck_Run` | Vbcheck_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Vbcheck: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_wcmd.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | 215f5181bda8 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Window command processor. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Wcmd

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Wcmd_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Wcmd_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Wcmd_Init |
| `Wcmd_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Wcmd_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Wcmd_Init`
- `int Wcmd_Run`
- `int Wcmd_Close`
- `const char * Wcmd_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Wcmd_Run` | Wcmd_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Wcmd: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.


---

## bcl_windir.c

| Property | Value |
|---|---|
| Lines | 43 (code: 28, comments: 15) |
| Functions | 4 |
| Dead functions | 0 |
| External calls | 0 |
| Complexity | 3 |
| Risk | LOW |
| Status | **SHELL** |
| Domain | unknown |
| SHA | e3ea07bbe699 |
| Includes | 1 |
| Defines | 0 |
| Structs | 0 |
| Enums | 0 |
| Typedefs | 0 |
| Static arrays | 1 |
| #ifdef blocks | 0 |
| SQL queries | 0 |
| Table refs | (none) |
| BCL commands | 2 |
| BCL packets | 2 |
| Global vars | 4 |
| Intra-file cycles | 0 |
| TODOs/FIXMEs | 0 |

**Summary:** Window directory manager. Stub unit - commands: read_state, set_config. Full implementation to follow.

**Class:** Windir

**Declared methods:** Init, Run, Close, State

### BCL Commands
- `read_state`
- `set_config`

### Functions (4)

| Name | Return | Params | Arity | Static | Line | Body | Nest | Calls |
|---|---|---|---|---|---|---|---|---|
| `Windir_Init` | int | `void` | 0 | exported | 17 | 4 | 1 |  |
| `Windir_Run` | int | `const char *cmd, const char *bcl_in, cha` | 4 | exported | 23 | 9 | 3 | Windir_Init |
| `Windir_Close` | int | `void` | 0 | exported | 34 | 3 | 1 |  |
| `Windir_State` | const char | `void` | 0 | exported | 39 | 4 | 1 |  |

### Includes
- `"bcl_toolstack.h"`

### Static Arrays
- `buf`

### BCL Packet Patterns (2)
- `[@INITIALIZED]` — `1`
- `[@STATUS]` — `config_set`

### Global Variables (4)
- `int Windir_Init`
- `int Windir_Run`
- `int Windir_Close`
- `const char * Windir_State`

### Intra-File Call Graph

| Caller | Calls |
|---|---|
| `Windir_Run` | Windir_Init |

### String Literals (first 30)
- `bcl_toolstack.h`
- `read_state`
- `[@INITIALIZED]{1}`
- `set_config`
- `[@STATUS]{config_set}`
- `not implemented - stub unit`
- `Windir: initialized=%d`

> **SHELL STUB** — only `read_state` and `set_config` implemented.

