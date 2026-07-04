---
auto_execution_mode: 2
description: Ban Cascade built-in tools — use MCP server tools only
---

# BAN LIST — Cascade Built-in Tools

## Banned (DO NOT USE)

| Cascade Tool | Use Instead (MCP) |
|---|---|
| `write_to_file` | `mcp1_write_file` |
| `read_file` | `mcp1_read_file` |
| `edit` | `mcp1_modify_file` |
| `multi_edit` | `mcp1_modify_file` |
| `run_command` | `mcp0_invoke_shell` |
| `grep_search` | `mcp1_search_within_files` |
| `find_by_name` | `mcp1_search_files` |
| `list_dir` | `mcp1_list_directory` |
| `code_search` | `mcp1_msearch` |

## Allowed MCP Tools (150)

### Filesystem
`mcp1_read_file` `mcp1_read_multiple_files` `mcp1_write_file` `mcp1_modify_file` `mcp1_copy_file` `mcp1_move_file` `mcp1_delete_file` `mcp1_list_directory` `mcp1_tree` `mcp1_search_files` `mcp1_search_within_files` `mcp1_get_file_info` `mcp1_create_directory` `mcp1_list_allowed_directories`

### Shell + Agents
`mcp0_invoke_shell` `mcp0_invoke_devin` `mcp0_list_agents`

### MySQL
`mcp1_mysql_read_query` `mcp1_mysql_write_query` `mcp1_mysql_select` `mcp1_mysql_insert` `mcp1_mysql_update` `mcp1_mysql_delete` `mcp1_mysql_count_rows` `mcp1_mysql_show_databases` `mcp1_mysql_show_tables` `mcp1_mysql_describe_table` `mcp1_mysql_table_info`

### SQLite
`mcp1_read_query` `mcp1_write_query` `mcp1_create_table` `mcp1_list_tables` `mcp1_describe_table`

### Search
`mcp1_msearch` `mcp1_search_nodes` `mcp1_open_nodes` `mcp1_read_graph`

### Pinecone
`mcp1_pinecone_search_records` `mcp1_pinecone_cascading_search` `mcp1_pinecone_upsert_records` `mcp1_pinecone_rerank_documents` `mcp1_pinecone_search_docs` `mcp1_pinecone_list_indexes` `mcp1_pinecone_describe_index` `mcp1_pinecone_describe_index_stats` `mcp1_pinecone_create_index_for_model`

### Graph DB
`mcp1_graph_query_nodes` `mcp1_graph_get_node` `mcp1_graph_add_node` `mcp1_graph_update_node` `mcp1_graph_delete_node` `mcp1_graph_get_edges` `mcp1_graph_add_edge` `mcp1_graph_delete_edge` `mcp1_graph_get_neighbors` `mcp1_graph_get_paths` `mcp1_graph_get_candidates` `mcp1_graph_decide` `mcp1_graph_trace` `mcp1_graph_simulate` `mcp1_graph_validate` `mcp1_graph_stats` `mcp1_graph_export` `mcp1_graph_gc` `mcp1_graph_graph_confidence` `mcp1_graph_overall_confidence` `mcp1_graph_repair_confidence` `mcp1_graph_runtime_confidence` `mcp1_graph_rank_fixes` `mcp1_graph_analyze_benefit` `mcp1_graph_analyze_cost` `mcp1_graph_analyze_risk` `mcp1_graph_add_rule` `mcp1_graph_get_rules` `mcp1_graph_add_snapshot` `mcp1_graph_get_snapshot` `mcp1_graph_query_decisions` `mcp1_graph_get_decision` `mcp1_graph_migrate_codefix` `mcp1_graph_migrate_session` `mcp1_graph_to_context_assembly`

### ContextRAM
`mcp1_ctx_semantic` `mcp1_ctx_query` `mcp1_ctx_list` `mcp1_ctx_get` `mcp1_ctx_put` `mcp1_ctx_update` `mcp1_ctx_delete` `mcp1_ctx_ingest` `mcp1_ctx_ingest_chat` `mcp1_ctx_link` `mcp1_ctx_assemble` `mcp1_ctx_auto` `mcp1_ctx_suggest` `mcp1_ctx_recent` `mcp1_ctx_stats` `mcp1_ctx_embed` `mcp1_ctx_embed_stats` `mcp1_ctx_events` `mcp1_ctx_snapshot` `mcp1_ctx_restore` `mcp1_ctx_lock` `mcp1_ctx_unlock` `mcp1_ctx_promote` `mcp1_ctx_demote` `mcp1_ctx_clear_expired` `mcp1_ctx_config` `mcp1_ctx_path`

### Gmail
`mcp1_gmail_send_email` `mcp1_gmail_create_draft` `mcp1_gmail_update_draft` `mcp1_gmail_delete_draft` `mcp1_gmail_send_draft` `mcp1_gmail_send_all_drafts` `mcp1_gmail_list_drafts` `mcp1_gmail_get_draft` `mcp1_gmail_fetch_email_headers` `mcp1_gmail_fetch_email` `mcp1_gmail_read_email_body` `mcp1_gmail_fetch_email_attachment` `mcp1_gmail_mark_as_read` `mcp1_gmail_delete_email` `mcp1_gmail_list_folders` `mcp1_gmail_get_label` `mcp1_gmail_create_label` `mcp1_gmail_list_accounts`

### Google Drive
`mcp1_gdrive_list` `mcp1_gdrive_read` `mcp1_gdrive_write` `mcp1_gdrive_search` `mcp1_gdrive_info` `mcp1_gdrive_create_folder` `mcp1_gdrive_move` `mcp1_gdrive_delete`

### Task Planner
`mcp1_taskplanner_board` `mcp1_taskplanner_board_data` `mcp1_taskplanner_board_visual` `mcp1_taskplanner_list` `mcp1_taskplanner_get` `mcp1_taskplanner_create` `mcp1_taskplanner_update` `mcp1_taskplanner_move` `mcp1_taskplanner_delete`

### Knowledge Graph
`mcp1_create_entities` `mcp1_add_observations` `mcp1_delete_entities` `mcp1_delete_observations` `mcp1_create_relations` `mcp1_delete_relations`

### Config
`mcp1_config_get` `mcp1_config_set` `mcp1_config_list` `mcp1_config_reload`

### Encrypted Chat Search (pb_reader)
`pb_reader.py scan` `pb_reader.py load-all` `pb_reader.py search "query"` `pb_reader.py read <file.pb>` `pb_reader.py list` `pb_reader.py stats` `pb_reader.py export <file.pb> <outdir>`
- **Path:** `/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/pb_reader.py`
- **Decrypts:** Windsurf Cascade `.pb` files (AES-256-GCM)
- **Searches:** 166 `.pb` files across `cascade/`, `implicit/`, `memories/`
- **Usage:** `python3 chat_mover/pb_reader.py search "diagnostic_kb"`

## Rules

1. ALL file operations → MCP filesystem tools, never Cascade built-in
2. ALL shell commands → `mcp0_invoke_shell`, never `run_command`
3. ALL searches → `mcp1_msearch` or `mcp1_search_within_files`, never `grep_search` or `code_search`
4. ALL MySQL → `mcp1_mysql_*`, never `run_command` with mysql CLI
5. ALL SQLite → `mcp1_read_query` / `mcp1_write_query`, never `run_command` with sqlite3
6. If a tool is not in the allowed list above, it is banned by default

## Examples

### Read a file
```
mcp1_read_file(path="/Users/wws/project/file.py")
```

### Write a file
```
mcp1_write_file(path="/Users/wws/project/file.py", content="...")
```

### Edit a file
```
mcp1_modify_file(path="/Users/wws/project/file.py", old_string="old", new_string="new")
```

### Run a shell command
```
mcp0_invoke_shell(command="ls -la /Users/wws/project/")
```

### Search MySQL
```
mcp1_mysql_read_query(query="SELECT * FROM laws.law LIMIT 10")
```

### Search knowledge base
```
mcp1_msearch(query="BND best next direction", limit=10)
```

### Search file contents
```
mcp1_search_within_files(path="/Users/wws/project", pattern="BndEngine")
```

### Find files by name
```
mcp1_search_files(path="/Users/wws/project", pattern="*.py")
```

## More Examples — Every Banned Tool vs MCP Alternative

### List directory
```
# BANNED: list_dir
# USE:
mcp1_list_directory(path="/Users/wws/Qdrant_mysql_mlx_vector_engine")
```

### Tree view
```
# BANNED: list_dir recursive
# USE:
mcp1_tree(path="/Users/wws/Qdrant_mysql_mlx_vector_engine", depth=3)
```

### Get file info
```
# BANNED: run_command("stat file.py")
# USE:
mcp1_get_file_info(path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BndEngine.py")
```

### Create directory
```
# BANNED: run_command("mkdir -p new_dir")
# USE:
mcp1_create_directory(path="/Users/wws/Qdrant_mysql_mlx_vector_engine/new_dir")
```

### Copy file
```
# BANNED: run_command("cp a.py b.py")
# USE:
mcp1_copy_file(src="/path/a.py", dst="/path/b.py")
```

### Move file
```
# BANNED: run_command("mv a.py b.py")
# USE:
mcp1_move_file(src="/path/a.py", dst="/path/b.py")
```

### Delete file
```
# BANNED: run_command("rm file.py")
# USE:
mcp1_delete_file(path="/path/file.py")
```

### Search file contents
```
# BANNED: grep_search
# USE:
mcp1_search_within_files(path="/Users/wws/Qdrant_mysql_mlx_vector_engine", pattern="BndEngine")
```

### Find files by name
```
# BANNED: find_by_name
# USE:
mcp1_search_files(path="/Users/wws/Qdrant_mysql_mlx_vector_engine", pattern="*.py")
```

### Read multiple files
```
# BANNED: read_file x3
# USE:
mcp1_read_multiple_files(paths=["/path/a.py", "/path/b.py", "/path/c.py"])
```

### MySQL SELECT
```
# BANNED: run_command("mysql -u root laws -e 'SELECT ...'")
# USE:
mcp1_mysql_read_query(query="SELECT * FROM law LIMIT 10")
```

### MySQL SELECT with database
```
# BANNED: run_command("mysql -u root laws -e 'SELECT ...'")
# USE:
mcp1_mysql_read_query(query="SELECT * FROM law LIMIT 10", database="laws")
```

### MySQL smart SELECT
```
# BANNED: run_command with mysql
# USE:
mcp1_mysql_select(table="law", columns=["id","law_code","name"], where="status='locked'", limit=5, order_by="id DESC")
```

### MySQL INSERT
```
# BANNED: run_command with mysql INSERT
# USE:
mcp1_mysql_insert(table="law", data={"law_code":"LAW_BND", "name":"BND Law", "status":"locked"})
```

### MySQL UPDATE
```
# BANNED: run_command with mysql UPDATE
# USE:
mcp1_mysql_update(table="law", data={"status":"locked"}, where="id=34")
```

### MySQL DELETE
```
# BANNED: run_command with mysql DELETE
# USE:
mcp1_mysql_delete(table="law", where="id=99")
```

### MySQL count
```
# BANNED: run_command("mysql -e 'SELECT COUNT(*)...'")
# USE:
mcp1_mysql_count_rows(table="law")
```

### MySQL show databases
```
# BANNED: run_command("mysql -e 'SHOW DATABASES'")
# USE:
mcp1_mysql_show_databases()
```

### MySQL show tables
```
# BANNED: run_command("mysql -e 'SHOW TABLES'")
# USE:
mcp1_mysql_show_tables(database="laws")
```

### MySQL describe table
```
# BANNED: run_command("mysql -e 'DESCRIBE law'")
# USE:
mcp1_mysql_describe_table(table="law", database="laws")
```

### SQLite SELECT
```
# BANNED: run_command("sqlite3 db.sqlite 'SELECT ...'")
# USE:
mcp1_read_query(query="SELECT * FROM extracted_laws LIMIT 10")
```

### SQLite INSERT/UPDATE/DELETE
```
# BANNED: run_command("sqlite3 db.sqlite 'INSERT ...'")
# USE:
mcp1_write_query(query="INSERT INTO extracted_laws (law, reason) VALUES ('BND', 'evaluate before acting')")
```

### SQLite list tables
```
# BANNED: run_command("sqlite3 db.sqlite '.tables'")
# USE:
mcp1_list_tables()
```

### SQLite describe table
```
# BANNED: run_command("sqlite3 db.sqlite '.schema'")
# USE:
mcp1_describe_table(table="extracted_laws")
```

### Knowledge base search (msearch)
```
# BANNED: grep_search across chat history
# USE:
mcp1_msearch(query="BND best next direction", limit=10)
```

### Knowledge base smart search
```
# BANNED: code_search
# USE:
mcp1_msearch(query="BndEngine timeout pattern", limit=10, smart=True)
```

### Pinecone vector search
```
# BANNED: run_command with python pinecone script
# USE:
mcp1_pinecone_search_records(query="graph engine timeout", top_k=10)
```

### Pinecone cascading search
```
# BANNED: run_command with python script
# USE:
mcp1_pinecone_cascading_search(query="BND pattern AI loop", top_k=10, rerank=True)
```

### Graph DB query nodes
```
# BANNED: run_command with python script
# USE:
mcp1_graph_query_nodes(domain="codefix", node_type="method")
```

### Graph DB decision pipeline
```
# BANNED: manual reasoning
# USE:
mcp1_graph_decide(query="Should I run BndEngine.py or debug the timeout first?")
```

### ContextRAM semantic search
```
# BANNED: grep_search
# USE:
mcp1_ctx_semantic(query="AI loop pattern write run wait")
```

### Task planner — create task
```
# BANNED: run_command("cat >> BACKLOG.md")
# USE:
mcp1_taskplanner_create(title="Fix BndEngine timeout", priority="P1", tags="bnd,timeout,graph")
```

### Task planner — move task
```
# BANNED: run_command editing .tasks files
# USE:
mcp1_taskplanner_move(id="TASK-099", toState="in_progress")
```

### Task planner — board
```
# BANNED: run_command("cat .tasks/*.md")
# USE:
mcp1_taskplanner_board()
```

### Send email
```
# BANNED: run_command with python smtp
# USE:
mcp1_gmail_send_email(to=["someone@email.com"], subject="BND Law", body="...")
```

### Google Drive list
```
# BANNED: run_command("ls GoogleDrive")
# USE:
mcp1_gdrive_list(path="/")
```

### Config get
```
# BANNED: run_command("cat config.toml")
# USE:
mcp1_config_get(section="tools.mysql", key="host")
```

### Config set
```
# BANNED: run_command("sed -i config.toml")
# USE:
mcp1_config_set(section="tools.filesystem", key="allowed_dirs", value='["/Users/wws/project"]')
```

## When To Use What — Tool Selection Decision Guide

### Decision Tree

```
What am I doing?
│
├─ Reading a file I know the path to?
│  └─ mcp1_read_file
│
├─ Reading 2+ files at once?
│  └─ mcp1_read_multiple_files
│
├─ I don't know the path — need to find by name?
│  └─ mcp1_search_files (glob pattern)
│
├─ I don't know the path — need to find by content?
│  └─ mcp1_search_within_files (text pattern)
│
├─ I need to understand directory structure?
│  ├─ Flat list? → mcp1_list_directory
│  └─ Recursive tree? → mcp1_tree
│
├─ Writing a new file?
│  └─ mcp1_write_file
│
├─ Editing an existing file (find/replace)?
│  └─ mcp1_modify_file
│
├─ Copy / move / delete a file?
│  ├─ Copy → mcp1_copy_file
│  ├─ Move → mcp1_move_file
│  └─ Delete → mcp1_delete_file
│
├─ Running a shell command (ls, python, cat, pip)?
│  └─ mcp0_invoke_shell
│
├─ Querying MySQL?
│  ├─ SELECT → mcp1_mysql_read_query or mcp1_mysql_select
│  ├─ INSERT → mcp1_mysql_insert
│  ├─ UPDATE → mcp1_mysql_update
│  ├─ DELETE → mcp1_mysql_delete
│  ├─ COUNT → mcp1_mysql_count_rows
│  ├─ SHOW DATABASES → mcp1_mysql_show_databases
│  ├─ SHOW TABLES → mcp1_mysql_show_tables
│  ├─ DESCRIBE → mcp1_mysql_describe_table
│  └─ Table analysis → mcp1_mysql_table_info
│
├─ Querying SQLite?
│  ├─ SELECT → mcp1_read_query
│  ├─ INSERT/UPDATE/DELETE → mcp1_write_query
│  ├─ CREATE TABLE → mcp1_create_table
│  ├─ List tables → mcp1_list_tables
│  └─ Describe → mcp1_describe_table
│
├─ Searching chat history / knowledge base?
│  ├─ Keyword search → mcp1_msearch
│  ├─ Semantic search → mcp1_msearch with smart=True
│  └─ Exact match → mcp1_msearch with mode="exact"
│
├─ Vector search (Pinecone)?
│  ├─ Basic search → mcp1_pinecone_search_records
│  ├─ High precision → mcp1_pinecone_cascading_search (reranked)
│  ├─ Upsert vectors → mcp1_pinecone_upsert_records
│  └─ Rerank documents → mcp1_pinecone_rerank_documents
│
├─ Graph DB (decisions, nodes, edges)?
│  ├─ Find candidates → mcp1_graph_get_candidates
│  ├─ Get a node → mcp1_graph_get_node
│  ├─ Query by type/domain → mcp1_graph_query_nodes
│  ├─ Get neighbors → mcp1_graph_get_neighbors
│  ├─ Find paths → mcp1_graph_get_paths
│  ├─ Run decision pipeline → mcp1_graph_decide
│  ├─ Get trace of last decision → mcp1_graph_trace
│  ├─ Simulate a fix → mcp1_graph_simulate
│  ├─ Validate a fix → mcp1_graph_validate
│  ├─ Analyze risk → mcp1_graph_analyze_risk
│  ├─ Analyze cost → mcp1_graph_analyze_cost
│  ├─ Analyze benefit → mcp1_graph_analyze_benefit
│  ├─ Add node → mcp1_graph_add_node
│  ├─ Add edge → mcp1_graph_add_edge
│  ├─ Update node → mcp1_graph_update_node
│  ├─ Delete node → mcp1_graph_delete_node
│  ├─ Delete edge → mcp1_graph_delete_edge
│  ├─ Get rules → mcp1_graph_get_rules
│  ├─ Add rule → mcp1_graph_add_rule
│  ├─ Stats → mcp1_graph_stats
│  └─ Export → mcp1_graph_export
│
├─ ContextRAM (semantic context store)?
│  ├─ Semantic search → mcp1_ctx_semantic
│  ├─ Full-text search → mcp1_ctx_query
│  ├─ List nodes → mcp1_ctx_list
│  ├─ Get by ID → mcp1_ctx_get
│  ├─ Store a node → mcp1_ctx_put
│  ├─ Update a node → mcp1_ctx_update
│  ├─ Delete a node → mcp1_ctx_delete
│  ├─ Ingest a file → mcp1_ctx_ingest
│  ├─ Ingest chat → mcp1_ctx_ingest_chat
│  ├─ Link nodes → mcp1_ctx_link
│  ├─ Recent nodes → mcp1_ctx_recent
│  ├─ Stats → mcp1_ctx_stats
│  ├─ Suggestions → mcp1_ctx_suggest
│  └─ Snapshot/restore → mcp1_ctx_snapshot / mcp1_ctx_restore
│
├─ Task management?
│  ├─ See all tasks → mcp1_taskplanner_board
│  ├─ List by state → mcp1_taskplanner_list
│  ├─ Get one task → mcp1_taskplanner_get
│  ├─ Create task → mcp1_taskplanner_create
│  ├─ Update task → mcp1_taskplanner_update
│  ├─ Move state → mcp1_taskplanner_move
│  └─ Delete task → mcp1_taskplanner_delete
│
├─ Email?
│  ├─ Send → mcp1_gmail_send_email
│  ├─ Create draft → mcp1_gmail_create_draft
│  ├─ List drafts → mcp1_gmail_list_drafts
│  ├─ Fetch headers → mcp1_gmail_fetch_email_headers
│  ├─ Fetch full email → mcp1_gmail_fetch_email
│  ├─ Read body → mcp1_gmail_read_email_body
│  └─ List folders → mcp1_gmail_list_folders
│
├─ Google Drive?
│  ├─ List files → mcp1_gdrive_list
│  ├─ Read file → mcp1_gdrive_read
│  ├─ Write file → mcp1_gdrive_write
│  ├─ Search → mcp1_gdrive_search
│  └─ File info → mcp1_gdrive_info
│
├─ MCP config?
│  ├─ Read config → mcp1_config_get
│  ├─ Set config → mcp1_config_set
│  ├─ List section → mcp1_config_list
│  └─ Reload config → mcp1_config_reload
│
└─ Delegate to Devin agent?
   └─ mcp0_invoke_devin
```

### Why — Reasoning Guide For Common Scenarios

| Scenario | Best Tool | Why |
|---|---|---|
| "What does this file contain?" | `mcp1_read_file` | Direct read, no shell overhead |
| "Does this pattern exist anywhere?" | `mcp1_search_within_files` | Searches file contents, returns line numbers |
| "Where is BndEngine.py?" | `mcp1_search_files` | Glob search by filename, fast |
| "What tables are in the laws DB?" | `mcp1_mysql_show_tables` | Direct metadata query, no shell |
| "How many laws have status=locked?" | `mcp1_mysql_count_rows` | Purpose-built counter, no manual SQL |
| "Show me 5 laws ordered by id" | `mcp1_mysql_select` | Smart builder with WHERE, LIMIT, ORDER BY |
| "What did the AI say about BND before?" | `mcp1_msearch` | Searches 215K+ chat messages across 3 DBs |
| "What's semantically related to loops?" | `mcp1_msearch` with `smart=True` | Consolidated 10-section semantic object |
| "Find similar code to this pattern" | `mcp1_pinecone_cascading_search` | Vector search + reranking for precision |
| "Should I fix X or Y first?" | `mcp1_graph_decide` | Full 8-step decision pipeline with trace |
| "What breaks if I change this method?" | `mcp1_graph_analyze_risk` | Risk analysis: complexity, dependencies, depth |
| "How much work to modify this method?" | `mcp1_graph_analyze_cost` | Cost analysis: lines, complexity, affected methods |
| "Is fixing this problem worth it?" | `mcp1_graph_analyze_benefit` | Benefit analysis: fixes resolved, violations addressed |
| "What context is relevant to this query?" | `mcp1_ctx_semantic` | Semantic search over context store |
| "Create a task for this work" | `mcp1_taskplanner_create` | Auto-generates ID, writes to BACKLOG.md |
| "What's the current task state?" | `mcp1_taskplanner_board` | Shows all tasks across all states |
| "Run a Python script" | `mcp0_invoke_shell` | Shell execution with timeout control |
| "Read config value" | `mcp1_config_get` | Direct TOML read, no file parsing needed |
| "Send an email notification" | `mcp1_gmail_send_email` | Full email send with threading support |
| "Read a file from Google Drive" | `mcp1_gdrive_read` | Direct GDrive file access |

### Anti-Patterns — What NOT To Do

| Wrong | Right | Why Wrong |
|---|---|---|
| `run_command("mysql -e 'SELECT...'")` | `mcp1_mysql_read_query` | Shell wrapping SQL = fragile, no type safety |
| `run_command("sqlite3 db 'SELECT...'")` | `mcp1_read_query` | Shell wrapping SQL = escaping nightmares |
| `grep_search("pattern", path)` | `mcp1_search_within_files` | Banned tool, use MCP equivalent |
| `find_by_name("*.py")` | `mcp1_search_files` | Banned tool, use MCP equivalent |
| `read_file("/path")` | `mcp1_read_file` | Banned tool, use MCP equivalent |
| `write_to_file(path, content)` | `mcp1_write_file` | Banned tool, use MCP equivalent |
| `edit(path, old, new)` | `mcp1_modify_file` | Banned tool, use MCP equivalent |
| `list_dir(path)` | `mcp1_list_directory` | Banned tool, use MCP equivalent |
| `code_search("query")` | `mcp1_msearch` | Banned tool, use MCP equivalent |
| `run_command("ls -la")` | `mcp0_invoke_shell` or `mcp1_list_directory` | `run_command` banned, use MCP shell |
| `run_command("cat file.py")` | `mcp1_read_file` | Reading files via shell = wasteful |
| `run_command("echo '...' > file")` | `mcp1_write_file` | Writing files via shell = no validation |
| `run_command("sed -i 's/old/new/' file")` | `mcp1_modify_file` | Editing via sed = fragile, no safety |

## Strategic Guide — When, Where, Why Each Tool Category Helps

### Filesystem Tools

**When to use:** Before reading or writing any file. First step of any task.

**Where to use:** Any path under `/Users/wws/Qdrant_mysql_mlx_vector_engine`.

**How they help:** You don't shell out to `cat`, `ls`, `find`, `sed`. The MCP filesystem tools give you structured responses — file content with metadata, directory listings with sizes, search results with line numbers. No shell escaping issues. No pipe chains that break. No `find` wrapper that dumps database tables instead of searching files (this happened — the custom `find` in PATH intercepted the command).

**Reasoning:** If you need to understand a file, `mcp1_read_file` gives you the content directly. If you need to know what files exist, `mcp1_search_files` or `mcp1_list_directory` gives you structured results. If you need to edit, `mcp1_modify_file` does find-and-replace safely. The filesystem tools are your eyes and hands — use them before anything else.

---

### Shell Tools (`mcp0_invoke_shell`)

**When to use:** When no MCP tool covers the operation — running Python scripts, compiling code, installing packages, checking process status, network calls.

**Where to use:** Any directory. Set `cwd` to control working directory.

**How they help:** Gives you full shell power with timeout control. You can run `python3 -m py_compile`, `pip install`, `git log`, `curl`, anything that needs a real shell. Returns stdout + stderr as text.

**Reasoning:** Shell is the escape hatch. Use it when MCP tools don't have an equivalent. But ALWAYS check if an MCP tool exists first — `mcp1_mysql_read_query` is better than `mcp0_invoke_shell("mysql -e ...")` because the MCP tool handles connections, escaping, and returns structured data. Shell is for things only shell can do: running scripts, compiling, git, process management.

**When NOT to use:** Don't use shell for file reads (`mcp1_read_file`), file writes (`mcp1_write_file`), file searches (`mcp1_search_files`), MySQL queries (`mcp1_mysql_*`), SQLite queries (`mcp1_read_query`). Those have dedicated MCP tools that are safer and more structured.

---

### MySQL Tools

**When to use:** Any time you need data from MySQL — querying laws, searching learned_rules, checking vb_classes, reading chat history, counting rows.

**Where to use:** Databases: `laws`, `vb_shared`, `vb_code_test`, `chatgpt_export`, `devin`, `diagnostic_kb`, `Chat_History`.

**How they help:** Direct structured queries. No shell wrapping. No escaping single quotes in SQL strings. `mcp1_mysql_select` builds the query for you with WHERE, LIMIT, ORDER BY. `mcp1_mysql_count_rows` is purpose-built for counting. `mcp1_mysql_table_info` gives you schema + indexes + row count + constraints in one call.

**Reasoning:** MySQL is your long-term memory. `vb_shared.learned_rules` has 10,540 rules — before writing code, query it. `vb_code_test.vb_methods` has 13,818 methods — before creating a method, check if it exists. `laws.law` has 33 laws — before making a decision, check if a law applies. `chatgpt_export.messages` has 72,000+ messages — before asking the user, search if they already answered this question. MySQL is the knowledge base that prevents the ask-tell-do loop.

**Best practice:** Before ANY code change, run:
1. `mcp1_mysql_select(table="learned_rules", where="pattern LIKE '%keyword%'", limit=5)` — check for prior solutions
2. `mcp1_mysql_select(table="know_problems", where="problem LIKE '%keyword%'", limit=5)` — check for known problems
3. `mcp1_mysql_select(table="vb_methods", where="method_name LIKE '%keyword%'", limit=10)` — check for existing methods

---

### SQLite Tools

**When to use:** When working with local SQLite databases — `Devin_Moseimport.db`, `domain_graph.db`, `dom_graph_work.db`, `GuisEngins.db`, `v20_hybrid_best.db`, `rustdesk_analysis.db`.

**Where to use:** Any `.db` or `.sqlite` file in the workspace.

**How they help:** Direct SQL execution against SQLite files. No `sqlite3` CLI needed. `mcp1_read_query` for SELECTs, `mcp1_write_query` for INSERT/UPDATE/DELETE, `mcp1_create_table` for schema, `mcp1_list_tables` to discover what's in a DB, `mcp1_describe_table` to see schema.

**Reasoning:** SQLite is your working memory — temporary analysis, code graphs, domain routing, extracted data. When you need to analyze code structure, ingest files into SQLite, run SQL queries to find patterns, then patch. The Fast Method (from memory) uses SQLite as the editing surface. SQLite tools let you do this without shell commands.

---

### msearch (Magnetic Search)

**When to use:** When you need to find something in chat history, conversation logs, or knowledge base. When the user says "search the chat" or "have I said this before?" or "find where I talked about X".

**Where to use:** Searches across 215K+ messages in 3 databases: `Chat_History`, `chatgpt_export`, `vb_shared`.

**How they help:** Magnetic search finds exact occurrences + surrounding context (blast radius). It's deterministic — returns the exact address, not "somewhere in this neighborhood". With `smart=True`, returns a consolidated 10-section semantic object. With `mode="exact"`, does literal matching. With `mode="regex"`, does pattern matching.

**Reasoning:** This is how you break the ask-tell-do loop. Before asking the user "what did you mean by BND?", search the chat history. The user already explained it — probably multiple times. msearch finds it in milliseconds. Every question you ask the user that they've already answered is a failure. msearch prevents that failure.

**Best practice:** Before asking the user ANY question, run:
```
mcp1_msearch(query="keyword from your question", limit=10)
```
If the answer exists in chat history, you'll find it. Only ask if msearch returns nothing relevant.

---

### Pinecone (Vector Search)

**When to use:** When you need semantic similarity — "find code/concepts that are related to X but may not mention X by name". When exact search fails because the concept is described differently.

**Where to use:** Pinecone index (configured in MCP config).

**How they help:** `mcp1_pinecone_search_records` does basic vector search. `mcp1_pinecone_cascading_search` adds reranking for higher precision — it runs the search, then reranks results with a separate model. `mcp1_pinecone_rerank_documents` lets you rerank any list of documents against a query.

**Reasoning:** Pinecone is for discovery — "I don't know what I'm looking for, but I'll know it when I see it." Use it when msearch (exact) returns nothing but you know the concept exists. For example: searching for "BND" might return nothing if the chat called it "best next direction" — but Pinecone would find semantically related content.

**When NOT to use:** Don't use Pinecone when you know the exact term — msearch is faster and more precise. Don't use Pinecone for MySQL data — use `mcp1_mysql_*` tools. Pinecone is the slow, probabilistic layer. msearch is the fast, deterministic layer. Use Pinecone when msearch fails.

---

### Graph DB Tools

**When to use:** When making decisions about code changes. When you need to understand dependencies, risks, costs, or benefits. When you need to trace why a decision was made.

**Where to use:** The unified graph DB (SQLite-backed, configured in MCP config).

**How they help:**
- `mcp1_graph_decide` — runs the full 8-step decision pipeline: get candidates → filter → when_rules → resolve_conflicts → score → decide. Returns the chosen fix with score and reason trace.
- `mcp1_graph_analyze_risk` — tells you what breaks if you modify a method (complexity, dependencies, depth).
- `mcp1_graph_analyze_cost` — tells you how much work a modification is (lines, complexity, affected methods).
- `mcp1_graph_analyze_benefit` — tells you if fixing a problem is worth it (fixes resolved, violations addressed).
- `mcp1_graph_simulate` — simulates applying a fix in memory, without touching files.
- `mcp1_graph_validate` — simulates + checks compilation.
- `mcp1_graph_trace` — shows the reasoning trace from the last `decide` call.

**Reasoning:** The graph DB is your reasoning engine. It stores code as nodes and edges — methods, classes, files, dependencies, calls, imports. When you're about to change code, the graph tells you: what depends on this? What breaks? How much work is it? Is it worth it? This prevents blind changes that cause cascading failures.

**Best practice:** Before modifying any method:
1. `mcp1_graph_get_candidates(query="method name")` — find the node
2. `mcp1_graph_analyze_risk(method_id=N)` — what breaks?
3. `mcp1_graph_analyze_cost(method_id=N)` — how much work?
4. `mcp1_graph_simulate(fix_id=N)` — what happens if I do it?

---

### ContextRAM Tools

**When to use:** When you need persistent context across sessions. When you need to store reasoning, notes, facts, or references that should survive between conversations.

**Where to use:** ContextRAM store (configured at `/Users/wws/.config/devin/contextram_store`).

**How they help:**
- `mcp1_ctx_semantic` — semantic search over stored context (find by meaning, not exact words)
- `mcp1_ctx_query` — full-text search (find by exact words)
- `mcp1_ctx_put` — store a node with type and content
- `mcp1_ctx_ingest` — ingest a file into the context store
- `mcp1_ctx_ingest_chat` — ingest chat data
- `mcp1_ctx_link` — create relationships between nodes
- `mcp1_ctx_snapshot` / `mcp1_ctx_restore` — save and restore state

**Reasoning:** ContextRAM is your working context. It's where you store "I learned X about Y" so future sessions can find it. It's different from MySQL (which stores structured data) and msearch (which searches chat history). ContextRAM stores your reasoning — the "why" behind decisions, the notes you took, the facts you discovered.

**When to use vs other tools:**
- MySQL → structured data (laws, rules, methods, errors)
- msearch → chat history (what the user said before)
- Pinecone → semantic similarity (find related concepts)
- ContextRAM → your reasoning (why you decided X, what you learned)
- Graph DB → code structure (what depends on what)

---

### Task Planner Tools

**When to use:** When tracking work across multiple steps. When the user gives a multi-part task. When you need to show progress.

**Where to use:** Tasks stored in `/Users/wws/Qdrant_mysql_mlx_vector_engine/.tasks/`.

**How they help:**
- `mcp1_taskplanner_create` — creates a task in BACKLOG.md with auto-generated ID
- `mcp1_taskplanner_move` — moves task between states (backlog → next → in_progress → done → rejected)
- `mcp1_taskplanner_board` — shows all tasks across all states
- `mcp1_taskplanner_get` — gets full details of one task
- `mcp1_taskplanner_update` — updates title, priority, tags, description, plan

**Reasoning:** Task planner prevents the "what was I doing?" problem. When a task has 10 steps, you need to track where you are. Without task planner, you rely on chat context — which gets lost. With task planner, the state persists in files. Next session, you check the board and know exactly where you left off.

---

### Gmail Tools

**When to use:** When the user asks to send, read, or manage email.

**Where to use:** Configured email accounts (check with `mcp1_gmail_list_accounts`).

**How they help:** Full email lifecycle — send, draft, fetch, read, mark as read, delete, list folders, manage labels. Supports threading (reply_to_message_id), attachments (from cache IDs), HTML body, BCC/CC.

**Reasoning:** Email tools let you handle email-related tasks without shell scripts or Python SMTP code. The user's email architecture is configured in `Config_Email.py` with 5 providers (Yahoo, Gmail, Outlook, Apple, Proton). The MCP Gmail tools connect directly to the mail server.

---

### Google Drive Tools

**When to use:** When the user asks to read, write, or search files on Google Drive.

**Where to use:** Mounted Google Drive at `/Users/wws/Library/CloudStorage/GoogleDrive-kautharlodewyk9@gmail.com/My Drive`.

**How they help:** Direct file operations on Google Drive — list, read, write, search, create folders, move, delete. No Google API scripts needed.

---

### Config Tools

**When to use:** When you need to read or modify the MCP server's own configuration.

**Where to use:** MCP config file (TOML format).

**How they help:** `mcp1_config_get` reads a value, `mcp1_config_set` writes a value, `mcp1_config_list` lists a section, `mcp1_config_reload` reloads the full config. Changes take effect on next server restart.

**Reasoning:** Config tools let you self-heal — if a tool fails because of a missing config value, you can fix it directly. For example: `mcp1_config_set(section="tools.filesystem", key="allowed_dirs", value='["/Users/wws/project"]')` fixes the filesystem tool when it has no allowed directories.
