# [@GHOST]{[@file<Plf_McpHooksPipeline.md>][@state<active>][@date<2026-07-04>][@ver<1.0>][@auth<Cascade>]}
# [@VBSTYLE]{[@auth<system>][@role<pipeline_doc>][@orch<McpHooks>][@no<decorators|print|hardcoded>]}
# [@FILEID]{[@path<core/Piplines/Plf_McpHooksPipeline.md>][@hash<placeholder>]}
# [@SUMMARY]{MCP Hooks Pipeline — Windsurf Cascade lifecycle hooks integrated with Dom_MCP tools, MySQL KB, and VBStyle enforcement}
# [@CLASS]{McpHooksPipeline}
# [@METHOD]{track}

# MCP Hooks Pipeline — Cascade Lifecycle Hooks + Dom_MCP Tool Integration

> **Core thesis:** Every Cascade action (command execution, file read, file write, MCP call, prompt processing) passes through pre-hooks and post-hooks that query the MySQL knowledge base (10,540 learned rules, 218 known problems, 336 solutions), enforce VBStyle compliance, and log all activity — creating a self-governing, self-learning development loop.
>
> **Authority:** This pipeline is the sole authority for Cascade hook configuration. No other file configures `.windsurf/hooks.json`.
>
> **Started:** 2026-07-04
> **Status:** DESIGN — Ready for implementation

---

## Pipeline Overview

```
User Prompt → pre_user_prompt (sanitize/inject context)
    ↓
Cascade Plans → pre_read_code (security check on file access)
    ↓
Cascade Reads → post_read_code (log access, update index)
    ↓
Cascade Writes → pre_write_code (VBStyle compliance check)
    ↓               ↓ if violations found
    ↓          BLOCK (exit 2) → Cascade sees error message
    ↓
File Written → post_write_code (py_compile + update codebase index)
    ↓
Cascade Executes → pre_run_command (MySQL KB lookup: learned_rules + know_problems)
    ↓                  ↓ if known failure pattern matches
    ↓             BLOCK (exit 2) → Cascade sees fix suggestion
    ↓
Command Done → post_run_command (log result, query know_solutions if error)
    ↓
MCP Tool Call → pre_mcp_tool_use (validate tool + arguments)
    ↓
MCP Done → post_mcp_tool_use (log result)
    ↓
Cascade Responds → post_cascade_response (log session to MySQL)
    ↓
Full Transcript → post_cascade_response_with_transcript (BCL tokens + context store)
    ↓
Worktree Created → post_setup_worktree (index new worktree)
```

---

## Phase 1: MCP FIRST RULE — Tool Priority Order

> **Core principle:** Before performing any task, always determine whether an MCP tool already exists that can perform the work. Never recreate functionality that already exists inside an MCP server.

### Priority Order (Mandatory)

| Priority | Source | When to Use |
|----------|--------|-------------|
| **1** | MCP DOM tools (`mcp1_*`) | Always check first. File ops, MySQL, SQLite, graph, context, taskplanner, Pinecone, config, Gmail, Drive, memory search |
| **2** | Other MCP tools (`mcp0_*`) | Shell execution (`mcp0_invoke_shell`), Devin delegation (`mcp0_invoke_devin`) |
| **3** | Built-in Cascade tools | Only if no suitable MCP tool exists. `read_file`, `write_to_file`, `edit`, `grep_search`, `find_by_name`, `code_search` |

### Decision Flow

```
Task received
    ↓
Does an mcp1_* tool do this?
    ├── YES → use it
    └── NO → Does an mcp0_* tool do this?
              ├── YES → use it
              └── NO → Use built-in Cascade tool
                         └── Log to taskplanner: "No MCP tool for <task>"
```

### Forbidden Actions

- **NEVER** use `run_command` for shell operations — use `mcp0_invoke_shell` (it never blocks)
- **NEVER** use `run_command` for MySQL queries — use `mcp1_mysql_read_query` / `mcp1_mysql_write_query`
- **NEVER** manually edit `.tasks/*.md` files — use `mcp1_taskplanner_*` tools
- **NEVER** recreate a parser/indexer/searcher that already exists as an MCP tool

---

## Phase 2: MCP TOOL DISCOVERY — Complete Capability Catalogue

The Dom_MCP server (mcp1_*) provides all tools needed for hook scripts. No external dependencies required.

### 2.1 Shell Execution Tools (mcp0 — agents MCP server)

| Tool | Purpose | Replaces |
|------|---------|----------|
| `mcp0_invoke_shell` | Execute shell commands, return stdout+stderr | `run_command` (which gets blocked by IDE) |
| `mcp0_invoke_devin` | Delegate tasks to Devin agent | N/A |
| `mcp0_list_agents` | List available agent backends | N/A |

### 2.2 File Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose | Key Parameter |
|------|---------|---------------|
| `mcp1_read_file` | Read complete file contents | `path` |
| `mcp1_read_multiple_files` | Read multiple files at once | `paths[]` |
| `mcp1_write_file` | Create or overwrite a file | `path`, `content` |
| `mcp1_modify_file` | Replace text in a file | `path`, `old_string`, `new_string`, `replace_all` |
| `mcp1_copy_file` | Copy file/directory | `src`, `dst` |
| `mcp1_move_file` | Move/rename file | `src`, `dst` |
| `mcp1_delete_file` | Delete file or empty dir | `path` |
| `mcp1_get_file_info` | File metadata (size, modified) | `path` |
| `mcp1_search_files` | Find files by glob pattern | `path`, `pattern` |
| `mcp1_list_directory` | List directory contents | `path` |
| `mcp1_tree` | Recursive tree view | `path`, `depth` |
| `mcp1_search_within_files` | Grep within files | `path`, `pattern` |

### 2.3 MySQL Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `mcp1_mysql_show_databases` | List all MySQL databases | — |
| `mcp1_mysql_show_tables` | List tables in a database | `database` |
| `mcp1_mysql_describe_table` | Show column structure | `table`, `database` |
| `mcp1_mysql_table_info` | Full table analysis | `table`, `database` |
| `mcp1_mysql_select` | Smart SELECT builder | `table`, `columns`, `where`, `limit`, `order_by` |
| `mcp1_mysql_read_query` | Raw SELECT query → JSON | `query`, `database` |
| `mcp1_mysql_write_query` | INSERT/UPDATE/DELETE/DDL | `query`, `database` |
| `mcp1_mysql_insert` | Safe parameterized insert | `table`, `data{}` |
| `mcp1_mysql_update` | Safe parameterized update | `table`, `data{}`, `where` |
| `mcp1_mysql_delete` | Safe parameterized delete | `table`, `where` |
| `mcp1_mysql_count_rows` | Count rows with WHERE | `table`, `where` |

### 2.4 SQLite Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `mcp1_list_tables` | List all SQLite tables | — |
| `mcp1_describe_table` | Show SQLite table schema | `table` |
| `mcp1_create_table` | CREATE TABLE from DDL | `query` |
| `mcp1_read_query` | SELECT → JSON rows | `query` |
| `mcp1_write_query` | INSERT/UPDATE/DELETE | `query` |

### 2.5 Knowledge Graph Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_create_entities` | Create entities in knowledge graph |
| `mcp1_create_relations` | Create relations between entities |
| `mcp1_search_nodes` | Search knowledge graph by query |
| `mcp1_open_nodes` | Retrieve specific nodes by name |
| `mcp1_read_graph` | Read entire knowledge graph |
| `mcp1_add_observations` | Add observations to existing entities |
| `mcp1_delete_entities` | Delete entities + relations |

### 2.6 Context Store Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_ctx_put` | Store a context node |
| `mcp1_ctx_get` | Retrieve a context node by ID |
| `mcp1_ctx_query` | Full-text query of context nodes |
| `mcp1_ctx_semantic` | Semantic search of context nodes |
| `mcp1_ctx_list` | List context nodes (filtered) |
| `mcp1_ctx_recent` | Get recent context nodes |
| `mcp1_ctx_ingest` | Ingest a file into context store |
| `mcp1_ctx_assemble` | Assemble context for a query |
| `mcp1_ctx_stats` | Context store statistics |

### 2.7 Graph DB Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_graph_add_node` | Add node to unified graph DB |
| `mcp1_graph_add_edge` | Add edge between nodes |
| `mcp1_graph_get_node` | Get single node by ID |
| `mcp1_graph_get_neighbors` | Get neighbors of a node |
| `mcp1_graph_get_paths` | Find paths between two nodes |
| `mcp1_graph_query_nodes` | Query nodes by domain/type/name |
| `mcp1_graph_query_decisions` | Query past decisions |
| `mcp1_graph_decide` | Run full 8-step decision pipeline |
| `mcp1_graph_stats` | Unified DB statistics |

### 2.8 Task Planner Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_taskplanner_board` | List all tasks across all states |
| `mcp1_taskplanner_list` | List tasks in a specific state |
| `mcp1_taskplanner_get` | Get task details by ID |
| `mcp1_taskplanner_create` | Create new task in BACKLOG |
| `mcp1_taskplanner_move` | Move task between states |
| `mcp1_taskplanner_update` | Update task fields |
| `mcp1_taskplanner_delete` | Delete a task |

### 2.9 Pinecone Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_pinecone_search_records` | Vector search in Pinecone index |
| `mcp1_pinecone_cascading_search` | Search with cascading reranking |
| `mcp1_pinecone_upsert_records` | Upsert vectors with metadata |
| `mcp1_pinecone_rerank_documents` | Rerank documents against query |

### 2.10 Config Operations (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_config_list` | List all config sections |
| `mcp1_config_get` | Read a config value |
| `mcp1_config_set` | Set a config value |
| `mcp1_config_reload` | Reload and display config |

### 2.11 Gmail + Google Drive (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_gmail_send_email` | Send email |
| `mcp1_gmail_fetch_email_headers` | Fetch email metadata |
| `mcp1_gdrive_list` | List Google Drive files |
| `mcp1_gdrive_read` | Read Google Drive file |
| `mcp1_gdrive_write` | Write to Google Drive |
| `mcp1_gdrive_search` | Search Google Drive by pattern |

### 2.12 Memory Search (mcp1 — dom_mcp MCP server)

| Tool | Purpose |
|------|---------|
| `mcp1_msearch` | Search local knowledge base (215K+ messages) |

---

## Phase 3: INITIAL WORKSPACE INDEX — First-Run Code Inventory

### 3.1 Concept

On first invocation, the hook system builds a complete index of every Python file in the workspace. This index is stored in SQLite and queried by all subsequent hooks.

**Pattern source:** `core/utility/content_extract.py` (ContentExtract class, 124 lines) — regex-based extraction of classes, methods, imports, BCL tags, violations.

**AST source:** `core/Dom_Bcl/ingest_bcl.py` (329 lines) — full AST-based extraction with method details, complexity scores, call graphs, violation tracking.

### 3.2 What Gets Indexed

For each `.py` file:

| Field | Source | Example |
|-------|--------|---------|
| `file_path` | Full absolute path | `/Users/wws/.../Dom_Web/Dom_Web.py` |
| `file_name` | Basename | `Dom_Web.py` |
| `line_count` | Line count | 1207 |
| `classes` | All class names | `DomainEngine, Browser, Request, Response` |
| `methods` | All method names per class | `Run, __init__, _p, read_state` |
| `imports` | All import statements | `os, sys, json, re, sqlite3` |
| `has_ghost` | BCL header present | `True/False` |
| `has_vbs` | VBStyle header present | `True/False` |
| `has_run` | Run() dispatch exists | `True/False` |
| `has_state` | self.state dict exists | `True/False` |
| `has_tuple3` | Tuple3 returns found | `True/False` |
| `print_count` | print() calls | 0 (should be 0) |
| `decorators` | @property/@staticmethod/@classmethod | `[]` (should be empty) |
| `self_underscore` | self._ usages | `[]` (should be empty) |
| `path_literals` | Hardcoded paths | `["/Users/wws/..."]` |
| `sql_tables` | SQL table references | `["learned_rules", "know_problems"]` |
| `file_io_calls` | open/read/write calls | 3 |
| `violations` | List of VBStyle violations | `[{"rule": "print_call", "count": 2}]` |
| `violation_count` | Total violations | 0 (compliant) |

### 3.3 SQLite Schema for Index

```sql
CREATE TABLE codebase_index (
    id TEXT PRIMARY KEY,
    file_path TEXT,
    file_name TEXT,
    line_count INTEGER,
    classes TEXT,          -- JSON array
    methods TEXT,          -- JSON array
    imports TEXT,          -- JSON array
    has_ghost INTEGER,
    has_vbs INTEGER,
    has_run INTEGER,
    has_state INTEGER,
    has_tuple3 INTEGER,
    print_count INTEGER,
    decorators TEXT,       -- JSON array
    self_underscore TEXT,  -- JSON array
    path_literals TEXT,    -- JSON array
    sql_tables TEXT,       -- JSON array
    file_io_calls INTEGER,
    violations TEXT,       -- JSON array
    violation_count INTEGER,
    indexed_at TEXT,
    -- Extended fields (Phase 3 spec)
    exports TEXT,             -- JSON array of __all__ or exported names
    global_variables TEXT,    -- JSON array of module-level variables
    type_hints TEXT,          -- JSON array of type-annotated symbols
    decorators_used TEXT,     -- JSON array of all decorators found
    docstring TEXT,           -- Module-level docstring
    module_summary TEXT,      -- AI-generated one-line summary
    dependencies TEXT,        -- JSON array of internal module dependencies
    relationships TEXT        -- JSON array of class inheritance relationships
);

CREATE TABLE codebase_classes (
    id TEXT PRIMARY KEY,
    file_id TEXT,
    class_name TEXT,
    bases TEXT,
    has_init INTEGER,
    has_run INTEGER,
    has_state INTEGER,
    method_count INTEGER,
    line_start INTEGER,
    line_end INTEGER,
    docstring TEXT,
    -- Extended fields (Phase 3 spec)
    type_hints TEXT,          -- JSON: method signature type hints
    decorators TEXT,          -- JSON: decorators on this class
    bases_detail TEXT,        -- JSON: base classes with full names
    nested_classes TEXT,      -- JSON: nested class names
    class_constants TEXT      -- JSON: class-level constants
);

CREATE TABLE codebase_methods (
    id TEXT PRIMARY KEY,
    file_id TEXT,
    class_id TEXT,
    class_name TEXT,
    method_name TEXT,
    params TEXT,
    has_tuple3 INTEGER,
    decorator_names TEXT,
    line_start INTEGER,
    line_end INTEGER,
    complexity INTEGER,
    has_print INTEGER,
    calls TEXT,
    self_attrs TEXT,
    -- Extended fields (Phase 3 spec)
    type_hints TEXT,          -- JSON: parameter and return type hints
    docstring TEXT,           -- Method docstring
    is_async INTEGER,         -- Async method
    params_detail TEXT,       -- JSON: parameter details with defaults
    return_type TEXT          -- Return type annotation if present
);

CREATE TABLE codebase_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    module TEXT,
    name TEXT,
    alias TEXT,
    is_wildcard INTEGER,
    is_local INTEGER          -- 1 if importing from within workspace
);

CREATE TABLE codebase_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    source_class TEXT,
    target_class TEXT,
    relationship_type TEXT,   -- 'inherits', 'composes', 'calls', 'imports'
    detail TEXT
);

CREATE TABLE codebase_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    class_name TEXT,
    method_name TEXT,
    rule TEXT,
    severity TEXT,
    description TEXT
);
```

### 3.4 Index Build Process

```
Step 1: mcp1_search_files(workspace_root, "*.py") → list of all .py files
Step 2: For each file:
    a. mcp1_read_file(path) → content
    b. Run ContentExtract.extract(content) → classes, methods, imports, violations
    c. Parse with AST (like ingest_bcl.py) → detailed method info
    d. mcp1_write_query(INSERT INTO codebase_index ...)
Step 3: mcp1_read_query(SELECT COUNT(*) FROM codebase_index) → verify
Step 4: mcp1_read_query(SELECT file_name, violation_count FROM codebase_index WHERE violation_count > 0) → compliance report
```

### 3.5 Index Refresh Strategy

- **Full rebuild:** Delete all rows, re-index all files (first run or major refactor)
- **Incremental:** `post_write_code` hook updates only the file that was just edited
- **Stale detection:** Compare file modification time vs `indexed_at` timestamp

---

## Phase 4: REUSE EXISTING TECHNOLOGY — Before Building New

> **Core principle:** Before implementing a new indexer, inspect the existing project for prior work. Reuse and extend existing implementations whenever practical instead of rebuilding them.

### 4.1 Existing Indexing Tools in the Codebase

| Tool | Location | Lines | What It Does | Reuse Potential |
|------|----------|-------|-------------|-----------------|
| **ContentExtract** | `core/utility/content_extract.py` | 124 | Regex-based extraction of classes, methods, imports, BCL tags, violations, SQL calls, file I/O | **HIGH** — Already VBStyle compliant, returns Tuple3, has `Run()` dispatch. Use as VBStyle checker in hooks. |
| **ingest_bcl.py** | `core/Dom_Bcl/ingest_bcl.py` | 329 | Full AST-based extraction: classes, methods, imports, constants, violations into SQLite. Extracts method complexity, calls, self_attrs, branch/loop counts | **HIGH** — Already has SQLite schema, AST walker, method detail extraction. Use as codebase index builder. |
| **Engine_smart_search** | `Dom_Smart_system_seach/Engine_smart_search.py` | 779 | MySQL vb_shared search across all text columns, tokenization, autocomplete, bigram/wordfreq | **MEDIUM** — MySQL search patterns reusable for hook KB queries. |
| **ast_def_store** | `core/Dom_Db/ast_def_store.py` | 687 | AST NodeVisitor that extracts every function/method definition as a flat row. Counts branches, loops, calls, assigns, local vars, max nesting | **MEDIUM** — More detailed AST extraction than ingest_bcl.py. Consider merging capabilities. |
| **Dom_Mcp Go binaries** | `Dom_Mcp/` | 42,784 lines | 9 Go MCP servers in SQLite store, unified dom_mcp binary with 30 tools | **HIGH** — These ARE the MCP tools. Hook scripts call them. |

### 4.2 Reuse Decision Matrix

| Need | Existing Tool | Action |
|------|---------------|--------|
| VBStyle violation checking | `ContentExtract` class | **REUSE** — import and call `Run("extract", {"content": code})` |
| AST-based codebase indexing | `ingest_bcl.py` `Main()` | **ADAPT** — extract the AST walker into a reusable function, add extended fields |
| MySQL KB queries | `Engine_smart_search` patterns | **ADAPT** — extract the MySQL query patterns into hook_common.py |
| Detailed method extraction | `ast_def_store.py` `DefExtractor` | **ADAPT** — merge the `BodyCounter` class into the index builder for richer method metadata |
| MCP tool calls | `Dom_Mcp` Go binaries | **USE** — hook scripts call mcp1_* tools which are backed by these binaries |
| SQLite schema for index | `ingest_bcl.py` schema | **EXTEND** — add Phase 3 fields (type_hints, exports, relationships) to existing schema |

### 4.3 What NOT to Rebuild

- **MySQL connector logic** — already in `hook_common.py` shared library
- **Regex patterns for VBStyle** — already in `ContentExtract` class constants
- **AST walker for classes/methods** — already in `ingest_bcl.py`
- **SQLite schema design** — already in `ingest_bcl.py`, extend it
- **MCP protocol** — already handled by Dom_Mcp Go binaries

---

## Phase 5: CONVERT DISCOVERY INTO MCP TOOLS — Reusable Building Blocks

> **Core principle:** Refactor the indexing functionality into reusable MCP tools that become building blocks available to Cascade.

### 5.1 New MCP Tools to Build

| # | Tool Name | Purpose | Input | Output | Source |
|---|-----------|---------|-------|--------|--------|
| 1 | `mcp1_workspace_index` | Build/rebuild full workspace index | `path` (workspace root) | `{files_indexed, classes, methods, violations, duration}` | Adapted from `ingest_bcl.py` |
| 2 | `mcp1_symbol_search` | Search for symbols by name | `query`, `symbol_type` (class/method/function/constant) | `[{file, class, method, line, type}]` | New — queries codebase_index SQLite |
| 3 | `mcp1_class_search` | Find classes by name pattern | `query` | `[{file, class, bases, methods, line_start, line_end}]` | New — queries codebase_classes |
| 4 | `mcp1_function_search` | Find functions/methods by name | `query` | `[{file, class, method, params, line, complexity}]` | New — queries codebase_methods |
| 5 | `mcp1_dependency_graph` | Get import dependencies for a file | `file_path` | `{imports: [], imported_by: [], internal: [], external: []}` | New — queries codebase_imports |
| 6 | `mcp1_import_graph` | Get full import graph | `--` | `[{file, module, is_local, is_wildcard}]` | New — queries codebase_imports |
| 7 | `mcp1_call_graph` | Get call graph for a class/method | `class_name`, `method_name` | `{calls: [], called_by: [], self_attrs: []}` | New — queries codebase_methods.calls |
| 8 | `mcp1_reference_search` | Find all references to a symbol | `symbol_name` | `[{file, class, method, line, context}]` | New — searches codebase_methods.calls |
| 9 | `mcp1_definition_lookup` | Find definition of a symbol | `symbol_name`, `symbol_type` | `{file, class, method, line, params, return_type}` | New — queries codebase_classes + codebase_methods |
| 10 | `mcp1_module_summary` | Get summary of a module | `file_path` | `{classes, methods, imports, violations, dependencies, summary}` | New — aggregates from all index tables |

### 5.2 MCP Tool Architecture

```
Hook Script (pre_*.py / post_*.py)
    ↓
MCP Tool Call (mcp1_workspace_index / mcp1_symbol_search / ...)
    ↓
Dom_Mcp Go Binary (dom_mcp unified, 30 tools)
    ↓
SQLite (codebase_index.db) / MySQL (vb_shared)
```

### 5.3 Implementation Priority

| Priority | Tool | Reason |
|----------|------|--------|
| P0 | `mcp1_workspace_index` | Required for first-run index build |
| P0 | `mcp1_symbol_search` | Required for all subsequent lookups |
| P1 | `mcp1_class_search` | Used by pre_write_code to find class being edited |
| P1 | `mcp1_function_search` | Used by pre_write_code to find method being edited |
| P1 | `mcp1_definition_lookup` | Used by pre_read_code to resolve symbols |
| P2 | `mcp1_dependency_graph` | Used for impact analysis before modifications |
| P2 | `mcp1_reference_search` | Used to find all callers before modifying a function |
| P2 | `mcp1_module_summary` | Used by post_write_code to update module summary |
| P3 | `mcp1_import_graph` | Used for dependency visualization |
| P3 | `mcp1_call_graph` | Used for call tree visualization |

---

## Phase 7: WINDSURF HOOKS DOCUMENTATION — Pre-Hooks (Block Before Damage)

### 7.1 pre_run_command — MySQL KB Lookup

**Config:**
```json
{
  "hooks": {
    "pre_run_command": [
      {
        "command": "python3 .windsurf/hooks/pre_run_command.py",
        "show_output": true
      }
    ]
  }
}
```

**Input (stdin JSON):**
```json
{
  "agent_action_name": "pre_run_command",
  "tool_info": {
    "command_line": "python3 some_script.py",
    "cwd": "/Users/wws/Qdrant_mysql_mlx_vector_engine"
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract command_line
3. Connect to MySQL vb_shared
4. Query learned_rules:
   SELECT pattern, fix_action, confidence
   FROM learned_rules
   WHERE pattern LIKE '%<command_keyword>%'
   ORDER BY confidence DESC LIMIT 5
5. Query know_problems:
   SELECT problem, description
   FROM know_problems
   WHERE problem LIKE '%<command_keyword>%' LIMIT 5
6. If high-confidence known failure → exit 2 (block) with fix suggestion to stderr
7. If safe → exit 0 (proceed)
8. If uncertain → exit 0 but print warning to stdout (show_output: true)
```

**Exit codes:**
- `0` = command safe, proceed
- `2` = command blocked, known failure pattern, stderr has fix suggestion
- `1` = hook error (MySQL unavailable), proceed anyway

### 7.2 pre_write_code — VBStyle Compliance Check

**Config:**
```json
{
  "hooks": {
    "pre_write_code": [
      {
        "command": "python3 .windsurf/hooks/pre_write_code.py",
        "show_output": true
      }
    ]
  }
}
```

**Input (stdin JSON):**
```json
{
  "agent_action_name": "pre_write_code",
  "tool_info": {
    "file_path": "/path/to/file.py",
    "edits": [
      {"old_string": "old code", "new_string": "new code"}
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract file_path and edits
3. For each edit, check new_string for VBStyle violations:
   a. print() calls → BLOCK
   b. @property / @staticmethod / @classmethod → BLOCK
   c. self._ usage (except self._p) → BLOCK
   d. Hardcoded paths (/Users/wws/...) → WARN
   e. Tab characters → BLOCK
   f. Enum usage → BLOCK
4. If file is .py and has no BCL headers after edit → WARN (not block)
5. If violations found → exit 2 with violation list to stderr
6. If clean → exit 0
```

**Exit codes:**
- `0` = code is VBStyle compliant, proceed
- `2` = VBStyle violations found, blocked, stderr has violation list
- `1` = hook error, proceed anyway

### 7.3 pre_read_code — Security Access Control (Optional)

**Config:**
```json
{
  "hooks": {
    "pre_read_code": [
      {
        "command": "python3 .windsurf/hooks/pre_read_code.py",
        "show_output": false
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract file_path
3. Check if file is within allowed workspace boundaries
4. Check if file contains sensitive patterns (.env, credentials, API keys)
5. If outside workspace → exit 2 (block)
6. If sensitive file → exit 2 (block) with warning
7. If safe → exit 0
```

### 7.4 pre_user_prompt — Prompt Sanitization (Optional)

**Config:**
```json
{
  "hooks": {
    "pre_user_prompt": [
      {
        "command": "python3 .windsurf/hooks/pre_user_prompt.py",
        "show_output": true
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract user_prompt
3. Check for blocked patterns:
   a. "ignore previous instructions" → BLOCK
   b. "bypass security" → BLOCK
   c. Embedded shell injection patterns → BLOCK
4. If safe → exit 0
5. Inject context: print codebase index summary to stdout (show_output: true)
```

### 7.5 pre_mcp_tool_use — MCP Tool Validation

**Config:**
```json
{
  "hooks": {
    "pre_mcp_tool_use": [
      {
        "command": "python3 .windsurf/hooks/pre_mcp_tool_use.py",
        "show_output": false
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract mcp_server_name, mcp_tool_name, mcp_tool_arguments
3. Check if tool is in allowed list
4. Check if arguments contain dangerous patterns (DROP TABLE, DELETE FROM without WHERE)
5. If dangerous → exit 2 (block)
6. If safe → exit 0
```

---

## Phase 7 (continued): POST-HOOKS — Log and Learn After Actions

### 7.6 post_run_command — Result Logging + Error Learning

**Config:**
```json
{
  "hooks": {
    "post_run_command": [
      {
        "command": "python3 .windsurf/hooks/post_run_command.py",
        "show_output": false
      }
    ]
  }
}
```

**Input (stdin JSON):**
```json
{
  "agent_action_name": "post_run_command",
  "tool_info": {
    "command_line": "python3 some_script.py",
    "cwd": "/Users/wws/Qdrant_mysql_mlx_vector_engine"
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract command_line
3. Log to MySQL:
   INSERT INTO command_log (command, cwd, timestamp, session_id)
   VALUES (...)
4. If command failed (exit code != 0):
   a. Query know_solutions:
      SELECT solution, description
      FROM know_solutions
      WHERE problem_id IN (
        SELECT id FROM know_problems
        WHERE problem LIKE '%<error_keyword>%'
      ) LIMIT 5
   b. Print fix suggestion to stdout (show_output: false, so only Cascade sees it)
   c. Insert into learned_rules if pattern is new:
      INSERT INTO learned_rules (pattern, fix_action, confidence, source)
      VALUES ('<command_pattern>', '<fix>', 0.5, 'hook_post_run')
```

### 7.7 post_write_code — Compile Check + Index Update

**Config:**
```json
{
  "hooks": {
    "post_write_code": [
      {
        "command": "python3 .windsurf/hooks/post_write_code.py",
        "show_output": true
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract file_path
3. Run py_compile on the file:
   python3 -m py_compile <file_path>
4. If compile fails → print error to stderr (show_output: true so user sees it)
5. Update codebase index:
   a. Read the file content
   b. Run ContentExtract.extract(content)
   c. DELETE FROM codebase_index WHERE file_path = <path>
   d. INSERT new row with updated data
6. If violation count changed → print warning to stdout
```

### 7.8 post_read_code — Access Logging

**Config:**
```json
{
  "hooks": {
    "post_read_code": [
      {
        "command": "python3 .windsurf/hooks/post_read_code.py",
        "show_output": false
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract file_path
3. Log to SQLite:
   INSERT INTO read_log (file_path, timestamp, session_id)
   VALUES (...)
4. If file not in codebase_index → trigger incremental index for this file
5. Exit 0
```

### 7.9 post_cascade_response — Session Logging

**Config:**
```json
{
  "hooks": {
    "post_cascade_response": [
      {
        "command": "python3 .windsurf/hooks/post_cascade_response.py",
        "show_output": false
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract response text
3. Log to MySQL:
   INSERT INTO cascade_sessions (response, timestamp, session_id)
   VALUES (...)
4. Extract any file paths mentioned in response
5. Update knowledge graph if new entities mentioned
6. Exit 0
```

### 7.10 post_mcp_tool_use — MCP Call Logging

**Config:**
```json
{
  "hooks": {
    "post_mcp_tool_use": [
      {
        "command": "python3 .windsurf/hooks/post_mcp_tool_use.py",
        "show_output": false
      }
    ]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract mcp_server_name, mcp_tool_name, mcp_result
3. Log to SQLite:
   INSERT INTO mcp_call_log (server, tool, arguments, result, timestamp)
   VALUES (...)
4. Exit 0
```

### 7.11 post_cascade_response_with_transcript — Full Session Capture

**Config:**
```json
{
  "hooks": {
    "post_cascade_response_with_transcript": [
      {
        "command": "python3 .windsurf/hooks/post_cascade_response_with_transcript.py",
        "show_output": false
      }
    ]
  }
}
```

**Input (stdin JSON):**
```json
{
  "agent_action_name": "post_cascade_response_with_transcript",
  "tool_info": {
    "response": "...",
    "transcript": "...",
    "tool_calls": [...]
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract response + full transcript + tool_calls array
3. Log full transcript to MySQL:
   INSERT INTO cascade_transcripts (session_id, transcript, tool_calls, timestamp)
   VALUES (...)
4. Extract all file paths from transcript
5. Extract all commands from transcript
6. Update knowledge graph with entities mentioned
7. Extract BCL tokens from transcript ([@DECISION], [@ERROR], [@FIX], [@FILE])
8. Store BCL tokens in context store via mcp1_ctx_put
9. Exit 0
```

**Difference from `post_cascade_response`:** This hook receives the **full transcript** including all tool calls, intermediate steps, and reasoning — not just the final response. Use this for complete session archaeology.

### 7.12 post_setup_worktree — Worktree Initialization

**Config:**
```json
{
  "hooks": {
    "post_setup_worktree": [
      {
        "command": "python3 .windsurf/hooks/post_setup_worktree.py",
        "show_output": false
      }
    ]
  }
}
```

**Input (stdin JSON):**
```json
{
  "agent_action_name": "post_setup_worktree",
  "tool_info": {
    "worktree_path": "/path/to/worktree",
    "base_branch": "main"
  }
}
```

**Logic:**
```
1. Read JSON from stdin
2. Extract worktree_path
3. Run codebase index for the new worktree:
   a. mcp1_search_files(worktree_path, "*.py")
   b. Build index for all .py files in worktree
   c. Store in separate SQLite DB for this worktree
4. Log worktree creation to MySQL:
   INSERT INTO worktree_log (path, base_branch, timestamp)
   VALUES (...)
5. Copy hooks.json into worktree if not present
6. Exit 0
```

---

## Phase 6: TRUSTLESS WORKFLOW — Evidence-Based Development

> **Core principle:** Future development should rely on MCP tool outputs instead of assumptions. Every stage should be evidence-based.

### 6.1 Trustless Workflow Definition

```
Workspace
    ↓
MCP Index (mcp1_workspace_index)
    ↓
Symbol Lookup (mcp1_symbol_search / mcp1_class_search)
    ↓
Dependency Analysis (mcp1_dependency_graph / mcp1_reference_search)
    ↓
Validation (pre_write_code VBStyle check / pre_run_command KB lookup)
    ↓
Modification (mcp1_modify_file / mcp1_write_file)
    ↓
Verification (post_write_code compile check / post_run_command result log)
```

### 6.2 Evidence-Based Rules

| Rule | Meaning |
|------|---------|
| **No assumptions** | Every file path, class name, method signature must come from the index, not memory |
| **No ad hoc reasoning** | Use `mcp1_symbol_search` to find symbols, not guess |
| **No blind writes** | `pre_write_code` checks VBStyle before any file modification |
| **No blind commands** | `pre_run_command` checks MySQL KB before any command execution |
| **No blind reads** | `pre_read_code` validates file access before reading |
| **Log everything** | Every action is logged by post-hooks for audit trail |
| **Learn from failures** | `post_run_command` inserts new learned_rules on failures |

### 6.3 Workflow vs. Current Cascade Behavior

| Current (Ad Hoc) | Trustless (MCP-First) |
|---|---|
| Cascade reads file with `read_file` | Cascade uses `mcp1_read_file` |
| Cascade searches with `grep_search` | Cascade uses `mcp1_search_within_files` |
| Cascade runs commands with `run_command` (gets blocked) | Cascade uses `mcp0_invoke_shell` (never blocks) |
| Cascade writes with `write_to_file` | Cascade uses `mcp1_write_file` |
| Cascade edits with `edit` | Cascade uses `mcp1_modify_file` |
| No pre-execution validation | `pre_run_command` queries 10,540 learned_rules |
| No pre-write validation | `pre_write_code` checks VBStyle compliance |
| No post-execution learning | `post_run_command` logs results and learns |
| No post-write verification | `post_write_code` runs py_compile + updates index |

---

## Stage 5: HOOK SCRIPT ARCHITECTURE

### 5.1 Directory Structure

```
.windsurf/
  ├── hooks.json                    # Hook configuration (this pipeline's output)
  ├── settings.json                 # Existing Windsurf settings
  ├── workflows/                    # Existing workflows
  └── hooks/                        # Hook scripts directory
      ├── pre_run_command.py        # MySQL KB lookup before commands
      ├── pre_write_code.py         # VBStyle check before file edits
      ├── pre_read_code.py          # Security check before file reads
      ├── pre_user_prompt.py        # Prompt sanitization + context injection
      ├── pre_mcp_tool_use.py       # MCP tool validation
      ├── post_run_command.py       # Result logging + error learning
      ├── post_write_code.py        # Compile check + index update
      ├── post_read_code.py         # Access logging
      ├── post_cascade_response.py  # Session logging
      ├── post_cascade_response_with_transcript.py  # Full transcript + BCL tokens
      ├── post_mcp_tool_use.py      # MCP call logging
      ├── post_setup_worktree.py    # Worktree initialization + indexing
      └── lib/
          ├── hook_common.py        # Shared utilities (MySQL connect, JSON parse, exit codes)
          ├── vbstyle_checker.py    # VBStyle violation detection (adapted from content_extract.py)
          └── codebase_index.py     # Index builder (adapted from ingest_bcl.py)
```

### 5.2 Shared Library: hook_common.py

```python
#!/usr/bin/env python3
"""Shared utilities for all hook scripts."""

import sys
import json
import mysql.connector

MYSQL_CONFIG = {
    "user": "root",
    "host": "localhost",
    " "port": 3306,
}

def read_stdin_json():
    """Read JSON from stdin. Returns dict or empty dict on error."""
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except json.JSONDecodeError:
        return {}

def get_tool_info(data):
    """Extract tool_info from hook input."""
    return data.get("tool_info", {})

def mysql_query(database, query, params=None):
    """Execute MySQL query, return rows."""
    cfg = dict(MYSQL_CONFIG)
    cfg["database"] = database
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params or ())
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def block(message):
    """Block the action. Exit code 2."""
    print(message, file=sys.stderr)
    sys.exit(2)

def proceed(message=None):
    """Allow the action. Exit code 0."""
    if message:
        print(message)
    sys.exit(0)

def error(message):
    """Hook error. Action proceeds. Exit code 1."""
    print(message, file=sys.stderr)
    sys.exit(1)
```

### 5.3 VBStyle Checker: vbstyle_checker.py

Adapted from `core/utility/content_extract.py` (ContentExtract class).

```python
#!/usr/bin/env python3
"""VBStyle compliance checker for hook scripts."""

import re

PRINT_RE = re.compile(r'print\s*\(')
DECORATOR_RE = re.compile(r'@(property|staticmethod|classmethod)')
SELF_UNDER_RE = re.compile(r'\bself\._(?!p\b)\w+')
TAB_RE = re.compile(r'\t')
ENUM_RE = re.compile(r'class\s+\w+\s*\(\s*Enum\s*\)')
GHOST_RE = re.compile(r'#\[@GHOST\]')
VBSTYLE_RE = re.compile(r'#\[@VBSTYLE\]')
PATH_LITERAL_RE = re.compile(r'["\']/(?:Users|home|var|tmp|opt)/[^"\']+["\']')

def check_vbstyle(code_text):
    """Return list of violations found in code text."""
    violations = []
    if PRINT_RE.search(code_text):
        count = len(PRINT_RE.findall(code_text))
        violations.append({"rule": "print_call", "count": count, "severity": "high"})
    if DECORATOR_RE.search(code_text):
        decorators = DECORATOR_RE.findall(code_text)
        violations.append({"rule": "decorator", "items": decorators, "severity": "high"})
    if SELF_UNDER_RE.search(code_text):
        items = SELF_UNDER_RE.findall(code_text)
        violations.append({"rule": "self_underscore", "items": items, "severity": "high"})
    if TAB_RE.search(code_text):
        violations.append({"rule": "tabs", "severity": "high"})
    if ENUM_RE.search(code_text):
        violations.append({"rule": "enum_usage", "severity": "high"})
    if PATH_LITERAL_RE.search(code_text):
        paths = PATH_LITERAL_RE.findall(code_text)
        violations.append({"rule": "hardcoded_path", "items": paths, "severity": "medium"})
    if not GHOST_RE.search(code_text):
        violations.append({"rule": "missing_ghost", "severity": "medium"})
    if not VBSTYLE_RE.search(code_text):
        violations.append({"rule": "missing_vbs", "severity": "medium"})
    return violations
```

### 5.4 Codebase Index Builder: codebase_index.py

Adapted from `core/Dom_Bcl/ingest_bcl.py` (AST-based extraction) and `core/utility/content_extract.py` (regex-based extraction).

```python
#!/usr/bin/env python3
"""Codebase index builder — extracts classes, methods, imports, violations from .py files."""

import ast
import os
import json
import hashlib
import sqlite3

def stable_id(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]

def extract_file(file_path):
    """Extract all metadata from a Python file."""
    with open(file_path, "r") as f:
        source = f.read()
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    file_id = stable_id(file_path)
    classes = []
    methods = []
    imports = []
    violations = []
    has_print = False
    has_decorators = False
    has_self_underscore = False
    has_run = False
    has_state = False
    has_tuple3 = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                has_print = True
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                if node.attr.startswith("_") and node.attr not in ("_p", "__init__"):
                    has_self_underscore = True
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                try:
                    dec_name = ast.unparse(dec)
                except Exception:
                    dec_name = ""
                if dec_name in ("@property", "@staticmethod", "@classmethod",
                                "property", "staticmethod", "classmethod"):
                    has_decorators = True
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}" if alias.name != "*" else mod)
        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            class_id = stable_id(file_id, class_name, node.lineno)
            class_has_init = False
            class_has_run = False
            class_has_state = False
            class_methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = item.name
                    params = [a.arg for a in item.args.args if a.arg != "self"]
                    has_tuple3_method = False
                    for child in ast.walk(item):
                        if isinstance(child, ast.Return):
                            if isinstance(child.value, ast.Tuple) and len(child.value.elts) == 3:
                                has_tuple3_method = True
                    if method_name == "__init__":
                        class_has_init = True
                    if method_name == "Run":
                        class_has_run = True
                        has_run = True
                    try:
                        if "self.state" in ast.unparse(item):
                            class_has_state = True
                            has_state = True
                    except Exception:
                        pass
                    if has_tuple3_method:
                        has_tuple3 = True
                    class_methods.append({
                        "name": method_name,
                        "params": params,
                        "line_start": item.lineno,
                        "line_end": item.end_lineno,
                        "has_tuple3": has_tuple3_method,
                    })
            classes.append({
                "id": class_id,
                "name": class_name,
                "has_init": class_has_init,
                "has_run": class_has_run,
                "has_state": class_has_state,
                "method_count": len(class_methods),
                "line_start": node.lineno,
                "line_end": node.end_lineno,
            })
            methods.extend(class_methods)
    if has_print:
        violations.append({"rule": "print_call", "severity": "high"})
    if has_decorators:
        violations.append({"rule": "decorator", "severity": "high"})
    if has_self_underscore:
        violations.append({"rule": "self_underscore", "severity": "high"})
    if not has_run and classes:
        violations.append({"rule": "no_run", "severity": "high"})
    if not has_state and classes:
        violations.append({"rule": "no_state", "severity": "high"})
    return {
        "file_id": file_id,
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "line_count": len(lines),
        "classes": [c["name"] for c in classes],
        "methods": [m["name"] for m in methods],
        "imports": imports,
        "has_ghost": "#[@GHOST]" in source,
        "has_vbs": "#[@VBSTYLE]" in source,
        "has_run": has_run,
        "has_state": has_state,
        "has_tuple3": has_tuple3,
        "print_count": len([n for n in ast.walk(tree)
                           if isinstance(n, ast.Call)
                           and isinstance(n.func, ast.Name)
                           and n.func.id == "print"]),
        "decorators": [],
        "self_underscore": [],
        "violations": violations,
        "violation_count": len(violations),
    }
```

---

## Stage 6: CONFIGURATION — hooks.json

### 6.1 Full hooks.json

```json
{
  "hooks": {
    "pre_user_prompt": [
      {
        "command": "python3 .windsurf/hooks/pre_user_prompt.py",
        "show_output": true
      }
    ],
    "pre_read_code": [
      {
        "command": "python3 .windsurf/hooks/pre_read_code.py",
        "show_output": false
      }
    ],
    "pre_write_code": [
      {
        "command": "python3 .windsurf/hooks/pre_write_code.py",
        "show_output": true
      }
    ],
    "pre_run_command": [
      {
        "command": "python3 .windsurf/hooks/pre_run_command.py",
        "show_output": true
      }
    ],
    "pre_mcp_tool_use": [
      {
        "command": "python3 .windsurf/hooks/pre_mcp_tool_use.py",
        "show_output": false
      }
    ],
    "post_read_code": [
      {
        "command": "python3 .windsurf/hooks/post_read_code.py",
        "show_output": false
      }
    ],
    "post_write_code": [
      {
        "command": "python3 .windsurf/hooks/post_write_code.py",
        "show_output": true
      }
    ],
    "post_run_command": [
      {
        "command": "python3 .windsurf/hooks/post_run_command.py",
        "show_output": false
      }
    ],
    "post_mcp_tool_use": [
      {
        "command": "python3 .windsurf/hooks/post_mcp_tool_use.py",
        "show_output": false
      }
    ],
    "post_cascade_response": [
      {
        "command": "python3 .windsurf/hooks/post_cascade_response.py",
        "show_output": false
      }
    ],
    "post_cascade_response_with_transcript": [
      {
        "command": "python3 .windsurf/hooks/post_cascade_response_with_transcript.py",
        "show_output": false
      }
    ],
    "post_setup_worktree": [
      {
        "command": "python3 .windsurf/hooks/post_setup_worktree.py",
        "show_output": false
      }
    ]
  }
}
```

### 6.2 Configuration Locations

Hooks are loaded from three locations, merged in order:

| Priority | Location | Scope |
|----------|----------|-------|
| 1 (system) | `/Library/Application Support/Windsurf/hooks.json` | All users |
| 2 (user) | `~/.codeium/windsurf/hooks.json` | All workspaces for this user |
| 3 (workspace) | `.windsurf/hooks.json` in project root | This project only |

**Recommendation:** Place hooks at workspace level (`.windsurf/hooks.json`) for project-specific behavior. Place shared hooks at user level (`~/.codeium/windsurf/hooks.json`).

### 6.3 Hook Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | string | Shell command (macOS/Linux, run via `bash -c`) |
| `powershell` | string | PowerShell command (Windows, optional) |
| `show_output` | boolean | Show stdout/stderr in Cascade UI |
| `working_directory` | string | Directory to execute from (default: workspace root) |

---

## Stage 7: EXIT CODE SEMANTICS

| Exit Code | Meaning | Effect |
|-----------|---------|--------|
| `0` | Success | Action proceeds normally |
| `2` | Blocking Error | Pre-hook: action is **blocked**. Cascade sees stderr message. |
| Any other | Error | Action proceeds normally (hook failed, don't block) |

**Critical:** Only pre-hooks can block (exit 2). Post-hooks cannot block — the action has already happened.

---

## Stage 8: DATA FLOW — MySQL KB Integration

### 8.1 Pre-Command Query Flow

```
command_line = "python3 build_c_codebase_db.py"
         ↓
    Extract keywords: ["python3", "build", "c_codebase", "db"]
         ↓
    Query 1: learned_rules
    SELECT pattern, fix_action, confidence
    FROM vb_shared.learned_rules
    WHERE pattern LIKE '%build%' OR pattern LIKE '%c_codebase%'
    ORDER BY confidence DESC LIMIT 5
         ↓
    Query 2: know_problems
    SELECT problem, description
    FROM vb_shared.know_problems
    WHERE problem LIKE '%build%' OR problem LIKE '%c_codebase%'
    LIMIT 5
         ↓
    If high-confidence failure pattern (confidence > 0.8):
         → exit 2, stderr = "Known issue: {pattern}. Fix: {fix_action}"
    Else if warning patterns found:
         → exit 0, stdout = "Warning: {problem}. {description}"
    Else:
         → exit 0 (silent proceed)
```

### 8.2 Post-Command Learning Flow

```
command finished with exit_code = 1
         ↓
    Extract error keywords from output
         ↓
    Query: know_solutions
    SELECT s.solution, s.description
    FROM vb_shared.know_solutions s
    JOIN vb_shared.know_problems p ON s.problem_id = p.id
    WHERE p.problem LIKE '%<error_keyword>%'
    LIMIT 5
         ↓
    If solution found:
         → Print fix to stdout (Cascade sees it)
    If no existing rule:
         → INSERT INTO learned_rules (pattern, fix_action, confidence, source)
           VALUES ('<command_pattern>', '<error_output>', 0.3, 'hook_post_run')
```

### 8.3 MySQL Tables Used

| Table | Database | Rows | Purpose |
|-------|----------|------|---------|
| `learned_rules` | vb_shared | 10,540 | Pattern → fix mapping |
| `know_problems` | vb_shared | 218 | Known failure modes |
| `know_solutions` | vb_shared | 336 | Solutions to known problems |
| `governance` | vb_shared | 58 | Governance rules |
| `rules` | vb_shared | 281 | Legacy rules (use rule_tokens instead) |
| `rule_tokens` | vb_shared | 238 | Canonical VBStyle rules (BCL format) |
| `vb_classes` | vb_code_test | 1,394 | Code class inventory |
| `vb_methods` | vb_code_test | 13,818 | Code method inventory |

---

## Stage 9: CHEAT PROMPT — MCP Tool Usage Instructions

### 9.1 Purpose

A cheat prompt that instructs Cascade to use MCP tools instead of `run_command`. This gets injected via `pre_user_prompt` hook or placed in `.windsurfrules`.

### 9.2 Cheat Prompt Text

```
## MCP TOOL USAGE RULES (MANDATORY)

1. SHELL COMMANDS: Use mcp0_invoke_shell for ALL shell commands. NEVER use run_command — it gets blocked by IDE approval. mcp0_invoke_shell never blocks.

2. FILE OPERATIONS: Use mcp1_read_file, mcp1_write_file, mcp1_modify_file, mcp1_search_files, mcp1_list_directory, mcp1_tree. NEVER use read_file/write_to_file unless mcp1 tools are unavailable.

3. MYSQL QUERIES: Use mcp1_mysql_read_query for SELECT, mcp1_mysql_write_query for INSERT/UPDATE/DELETE/DDL. NEVER use run_command for MySQL.

4. SQLITE QUERIES: Use mcp1_read_query for SELECT, mcp1_write_query for INSERT/UPDATE/DELETE. Use mcp1_create_table for DDL.

5. CODEBASE INDEX: On first run, use mcp1_search_files to find all .py files, then build an index using the ContentExtract pattern. Store in SQLite via mcp1_write_query.

6. KNOWLEDGE GRAPH: Use mcp1_graph_* tools for graph operations. Use mcp1_search_nodes for entity search.

7. TASK MANAGEMENT: Use mcp1_taskplanner_* tools for all task operations. NEVER manually edit .tasks/*.md files.

8. CONTEXT STORE: Use mcp1_ctx_put, mcp1_ctx_get, mcp1_ctx_semantic for context management.

9. CONFIG: Use mcp1_config_get, mcp1_config_set for dom_mcp configuration.

10. MEMORY SEARCH: Use mcp1_msearch to search 215K+ messages in the local knowledge base.

## PRE-EXECUTION CHECKS (MANDATORY)

Before executing ANY command:
1. Query MySQL vb_shared.learned_rules for patterns matching the command
2. Query MySQL vb_shared.know_problems for known failure modes
3. If known failure → do NOT execute, report fix suggestion instead

Before writing ANY code:
1. Check VBStyle compliance (no print, no decorators, no self._, no tabs, no hardcoded paths)
2. Ensure BCL headers present ([@GHOST], [@VBSTYLE])
3. Ensure Run() dispatch exists
4. Ensure Tuple3 returns

## CODEBASE INDEX (FIRST RUN ONLY)

If codebase_index table does not exist in SQLite:
1. mcp1_search_files(workspace_root, "*.py") → list all .py files
2. For each file: mcp1_read_file → extract classes/methods/imports/violations
3. mcp1_create_table(codebase_index schema)
4. mcp1_write_query(INSERT INTO codebase_index ...)
5. Verify: mcp1_read_query(SELECT COUNT(*) FROM codebase_index)
```

---

## Phase 8: PIPELINE ARCHITECTURE — Complete Execution Flow

> **Core principle:** Document every stage of a request as it flows through the system, with inputs, outputs, responsibilities, and interactions.

### 8.1 Full Request Lifecycle

```
User Request
    ↓
[pre_user_prompt] — Sanitize prompt, inject cheat prompt + codebase index summary
    ↓
Workspace Discovery — mcp1_search_files("*.py") if index not built
    ↓
MCP Tool Selection — Phase 1 priority order (mcp1_* → mcp0_* → built-in)
    ↓
Code Index Lookup — mcp1_symbol_search / mcp1_class_search / mcp1_definition_lookup
    ↓
Symbol Resolution — mcp1_definition_lookup(symbol_name) → {file, class, method, line}
    ↓
Dependency Analysis — mcp1_dependency_graph(file_path) → imports, imported_by
    ↓
[pre_read_code] — Security check on files to read
    ↓
Read Operations — mcp1_read_file / mcp1_read_multiple_files
    ↓
[post_read_code] — Log access, trigger incremental index if needed
    ↓
Planning — Cascade plans modifications based on evidence from index
    ↓
[pre_write_code] — VBStyle compliance check on planned code
    ↓ (exit 2 if violations → Cascade sees error, must fix)
Code Modification — mcp1_modify_file / mcp1_write_file
    ↓
[post_write_code] — py_compile + update codebase index
    ↓
[pre_run_command] — MySQL KB lookup (learned_rules + know_problems)
    ↓ (exit 2 if known failure → Cascade sees fix suggestion)
Command Execution — mcp0_invoke_shell (never blocks)
    ↓
[post_run_command] — Log result, query know_solutions if error, insert learned_rules
    ↓
[pre_mcp_tool_use] — Validate MCP tool + arguments
    ↓
MCP Tool Execution — mcp1_* tool call
    ↓
[post_mcp_tool_use] — Log MCP call result
    ↓
Response Generation — Cascade produces response
    ↓
[post_cascade_response] — Log session to MySQL
    ↓
[post_cascade_response_with_transcript] — Full transcript capture + BCL token extraction
    ↓
Learning — New learned_rules inserted, knowledge graph updated, context store populated
```

### 8.2 Stage Details

| Stage | Input | Output | Responsibility | Hooks Involved |
|-------|-------|--------|---------------|----------------|
| User Request | Raw user text | Sanitized prompt + injected context | `pre_user_prompt` | `pre_user_prompt` |
| Workspace Discovery | Workspace root path | List of all .py files | Index builder (first run only) | `post_setup_worktree` (if worktree) |
| MCP Tool Selection | Task type | Selected MCP tool name | Phase 1 priority order | `pre_mcp_tool_use` |
| Code Index Lookup | Symbol name | File, class, method, line info | `mcp1_symbol_search` | — |
| Symbol Resolution | Symbol name + type | Definition location | `mcp1_definition_lookup` | — |
| Dependency Analysis | File path | Import graph, reference list | `mcp1_dependency_graph` | — |
| Read Operations | File paths | File contents | `mcp1_read_file` | `pre_read_code`, `post_read_code` |
| Planning | Index data + file contents | Modification plan | Cascade reasoning | — |
| Write Validation | Planned code content | Pass/Fail | `pre_write_code` | `pre_write_code` |
| Code Modification | File path + new content | Modified file | `mcp1_modify_file` | `post_write_code` |
| Command Validation | Command line | Pass/Fail + fix suggestion | `pre_run_command` | `pre_run_command` |
| Execution | Command line | stdout/stderr/exit code | `mcp0_invoke_shell` | `post_run_command` |
| Response | Cascade output | Formatted response | Cascade | `post_cascade_response` |
| Transcript | Full session | BCL tokens + MySQL log | `post_cascade_response_with_transcript` | `post_cascade_response_with_transcript` |
| Learning | Error/success patterns | New learned_rules rows | `post_run_command` | `post_run_command` |

### 8.3 Hook Execution Order (Single Request)

```
1.  pre_user_prompt        → inject context, sanitize
2.  pre_read_code          → validate file access (per file read)
3.  post_read_code         → log access (per file read)
4.  pre_mcp_tool_use       → validate MCP call (per MCP call)
5.  post_mcp_tool_use      → log MCP call (per MCP call)
6.  pre_write_code         → VBStyle check (per file write)
7.  post_write_code        → compile + index update (per file write)
8.  pre_run_command        → KB lookup (per command)
9.  post_run_command       → log + learn (per command)
10. post_cascade_response  → log session (once per response)
11. post_cascade_response_with_transcript → full capture (once per response)
```

### 8.4 Data Flow Between Stages

```
SQLite (codebase_index)
    ↑↓                    ↑↓
pre_read_code ──→ post_read_code ──→ incremental index update
    ↓                                      ↓
    ↓                              SQLite (read_log)
    ↓
pre_write_code ←── ContentExtract (VBStyle check)
    ↓
post_write_code ──→ py_compile ──→ SQLite (codebase_index update)
    ↓
pre_run_command ←── MySQL (learned_rules, know_problems)
    ↓
post_run_command ──→ MySQL (know_solutions lookup) ──→ MySQL (learned_rules insert)
    ↓
post_cascade_response ──→ MySQL (cascade_sessions)
    ↓
post_cascade_response_with_transcript ──→ MySQL (cascade_transcripts) ──→ Context Store (BCL tokens)
```

---

## Phase 9: SUPPORTING DIAGRAMS — Visual Documentation

> **Core principle:** Generate comprehensive diagrams showing how information moves through the system.

### 9.1 Domain Graph — System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     USER PROMPT                              │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  pre_user_prompt HOOK                        │
│  Sanitize → Inject Cheat Prompt → Inject Index Summary      │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CASCADE ENGINE                            │
│  Plans → Selects MCP Tools → Requests Operations            │
└──────┬───────────┬───────────┬───────────┬─────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
   READ        WRITE        EXECUTE     MCP CALL
       │           │           │           │
       ▼           ▼           ▼           ▼
 pre_read    pre_write   pre_run     pre_mcp
 _code       _code       _command    _tool_use
       │           │           │           │
       ▼           ▼           ▼           ▼
 mcp1_read   mcp1_modify  mcp0_shell  mcp1_* tool
 _file       _file        _invoke
       │           │           │           │
       ▼           ▼           ▼           ▼
 post_read   post_write  post_run    post_mcp
 _code       _code       _command    _tool_use
       │           │           │           │
       └─────┬─────┴─────┬─────┘           │
             ▼           ▼                 ▼
    SQLite:          MySQL:          SQLite:
    codebase_index    learned_rules    mcp_call_log
    read_log          know_problems
                     know_solutions
                     cascade_sessions
             │           │
             ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│              post_cascade_response HOOK                      │
│  Log session → Update knowledge graph                       │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│       post_cascade_response_with_transcript HOOK             │
│  Full transcript → BCL tokens → Context Store               │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Hook Lifecycle Diagram

```
                    ┌─────────────┐
                    │  USER INPUT │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │pre_user_    │ BLOCK (exit 2)
                    │prompt       │──────────────► STOP
                    └──────┬──────┘
                           │ PROCEED (exit 0)
                    ┌──────▼──────┐
                    │ CASCADE     │
                    │ PLANS       │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼───┐   ┌────▼───┐   ┌────▼───┐
         │ READ   │   │ WRITE  │   │ RUN    │
         └────┬───┘   └────┬───┘   └────┬───┘
              │            │            │
         ┌────▼───┐   ┌────▼───┐   ┌────▼───┐
         │pre_    │   │pre_    │   │pre_    │
         │read_   │   │write_  │   │run_    │
         │code    │   │code    │   │command │
         └────┬───┘   └────┬───┘   └────┬───┘
              │            │            │
         ┌────▼───┐   ┌────▼───┐   ┌────▼───┐
         │EXECUTE │   │EXECUTE │   │EXECUTE │
         │READ    │   │WRITE   │   │COMMAND │
         └────┬───┘   └────┬───┘   └────┬───┘
              │            │            │
         ┌────▼───┐   ┌────▼───┐   ┌────▼───┐
         │post_   │   │post_   │   │post_   │
         │read_   │   │write_  │   │run_    │
         │code    │   │code    │   │command │
         └────┬───┘   └────┬───┘   └────┬───┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │post_cascade_│
                    │response     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │post_cascade_│
                    │response_    │
                    │with_        │
                    │transcript   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   LEARNING  │
                    │   LOOP      │
                    └─────────────┘
```

### 9.3 MCP Interaction Diagram

```
┌──────────┐     MCP call      ┌───────────┐     Go binary     ┌────────────┐
│  Hook    │──────────────────►│  dom_mcp  │──────────────────►│  SQLite    │
│  Script  │◄──────────────────│  server   │◄──────────────────│  / MySQL   │
│  (.py)   │     JSON result   │  (Go)     │     rows          │  DB        │
└──────────┘                   └───────────┘                   └────────────┘
     │                                                              │
     │ exit code                                                    │
     ▼                                                              │
┌──────────┐                                                       │
│ Cascade  │◄──────────────────────────────────────────────────────┘
│ IDE      │  (hook output shown in UI if show_output: true)
└──────────┘
```

### 9.4 Code Discovery Flow

```
First Run:
    mcp1_search_files(root, "*.py")
        ↓
    For each .py file:
        mcp1_read_file(path)
            ↓
        ContentExtract.Run("extract", {"content": code})
            ↓                              ↓
        Regex: classes, methods,      AST: imports, constants,
        violations, BCL tags          method details, complexity,
                                       calls, self_attrs, type_hints
            ↓
        Merge results → JSON
            ↓
        mcp1_write_query(INSERT INTO codebase_index ...)
        mcp1_write_query(INSERT INTO codebase_classes ...)
        mcp1_write_query(INSERT INTO codebase_methods ...)
        mcp1_write_query(INSERT INTO codebase_imports ...)
        mcp1_write_query(INSERT INTO codebase_relationships ...)
        mcp1_write_query(INSERT INTO codebase_violations ...)
            ↓
    Verify: mcp1_read_query(SELECT COUNT(*) FROM codebase_index)
    Report: mcp1_read_query(SELECT file_name, violation_count
                             FROM codebase_index
                             WHERE violation_count > 0)

Subsequent Runs (post_write_code hook):
    File modified → DELETE old row → INSERT new row
    (incremental, only touches the file that was edited)
```

### 9.5 Validation Flow

```
                    ┌──────────────────┐
                    │  CODE TO WRITE   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  pre_write_code  │
                    │  HOOK            │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼───┐    ┌────▼───┐    ┌────▼────┐
         │ print? │    │decora- │    │ self._? │
         │ calls? │    │tors?   │    │ (except │
         │        │    │        │    │  _p)?   │
         └────┬───┘    └────┬───┘    └────┬────┘
              │              │              │
         ┌────▼───┐    ┌────▼───┐    ┌────▼────┐
         │ tabs?  │    │BCL     │    │hardcoded│
         │        │    │headers?│    │paths?   │
         └────┬───┘    └────┬───┘    └────┬────┘
              │              │              │
              └──────┬───────┴──────┬──────┘
                     │              │
                ┌────▼────┐   ┌────▼────┐
                │ CLEAN   │   │ VIOLATIONS│
                │ exit 0  │   │ exit 2   │
                └─────────┘   └────┬────┘
                                   │
                            ┌──────▼──────┐
                            │ Cascade sees │
                            │ violation    │
                            │ list in UI   │
                            └─────────────┘
```

### 9.6 Execution Flow — Command Lifecycle

```
┌──────────────────┐
│ COMMAND TO RUN   │
└────────┬─────────┘
         │
┌────────▼─────────┐
│ pre_run_command  │
│ HOOK             │
└────────┬─────────┘
         │
    Extract keywords from command
         │
    ┌────▼─────────────────────────────┐
    │ MySQL: vb_shared.learned_rules   │
    │ SELECT pattern, fix_action       │
    │ WHERE pattern LIKE '%keyword%'   │
    │ ORDER BY confidence DESC LIMIT 5 │
    └────┬─────────────────────────────┘
         │
    ┌────▼─────────────────────────────┐
    │ MySQL: vb_shared.know_problems   │
    │ SELECT problem, description      │
    │ WHERE problem LIKE '%keyword%'   │
    └────┬─────────────────────────────┘
         │
    ┌────▼────────┐    ┌────────────┐
    │ KNOWN FAIL  │    │ SAFE       │
    │ exit 2      │    │ exit 0     │
    │ + fix to    │    │            │
    │   stderr    │    │            │
    └────┬────────┘    └────┬───────┘
         │                  │
    ┌────▼──────┐     ┌────▼───────┐
    │ BLOCKED   │     │ mcp0_invoke│
    │ Cascade   │     │ _shell     │
    │ sees fix  │     │ executes   │
    └───────────┘     └────┬───────┘
                          │
                   ┌──────▼───────┐
                   │post_run_     │
                   │command HOOK  │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │ Result OK?   │
                   └──┬───────┬───┘
                   YES│       │NO
                      │       │
               ┌──────▼──┐ ┌──▼──────────────┐
               │ Log to  │ │ Query           │
               │ SQLite  │ │ know_solutions  │
               │         │ │ Insert          │
               │         │ │ learned_rules   │
               └─────────┘ └─────────────────┘
```

### 9.7 Dependency Graph — Hook to MCP Tool Mapping

```
pre_user_prompt ──────► mcp1_read_query (check if index exists)
    │                    mcp1_search_files (if index needed)
    │
pre_read_code ────────► mcp1_search_within_files (sensitive patterns)
    │
pre_write_code ───────► ContentExtract (local, no MCP needed)
    │                    mcp1_read_query (check existing violations)
    │
pre_run_command ──────► mcp1_mysql_read_query (learned_rules)
    │                    mcp1_mysql_read_query (know_problems)
    │
pre_mcp_tool_use ─────► mcp1_list_tables (validate SQLite tools)
    │
post_read_code ───────► mcp1_write_query (log to read_log)
    │                    mcp1_read_query (check if file in index)
    │
post_write_code ──────► mcp0_invoke_shell (py_compile)
    │                    mcp1_write_query (update index)
    │
post_run_command ─────► mcp1_write_query (log result)
    │                    mcp1_mysql_read_query (know_solutions)
    │                    mcp1_mysql_write_query (learned_rules)
    │
post_mcp_tool_use ────► mcp1_write_query (log to mcp_call_log)
    │
post_cascade_response ► mcp1_mysql_write_query (log session)
    │                    mcp1_graph_add_node (knowledge graph)
    │
post_cascade_response_with_transcript ► mcp1_mysql_write_query (transcript)
    │                                    mcp1_ctx_put (BCL tokens)
    │
post_setup_worktree ──► mcp1_search_files (index new worktree)
                         mcp1_write_query (log worktree)
```

---

## Stage 10: VERIFICATION

### 10.1 Hook Verification Checklist

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | hooks.json valid JSON | `python3 -c "import json; json.load(open('.windsurf/hooks.json'))"` | No error |
| 2 | pre_run_command blocks dangerous | Echo `{"agent_action_name":"pre_run_command","tool_info":{"command_line":"rm -rf /","cwd":"."}}` \| python3 .windsurf/hooks/pre_run_command.py | Exit 2 |
| 3 | pre_run_command allows safe | Echo `{"agent_action_name":"pre_run_command","tool_info":{"command_line":"ls -la","cwd":"."}}` \| python3 .windsurf/hooks/pre_run_command.py | Exit 0 |
| 4 | pre_write_code blocks print() | Echo `{"agent_action_name":"pre_write_code","tool_info":{"file_path":"test.py","edits":[{"old_string":"x=1","new_string":"print('hello')"}]}}` \| python3 .windsurf/hooks/pre_write_code.py | Exit 2 |
| 5 | pre_write_code allows clean | Echo `{"agent_action_name":"pre_write_code","tool_info":{"file_path":"test.py","edits":[{"old_string":"x=1","new_string":"x = 2"}]}}` \| python3 .windsurf/hooks/pre_write_code.py | Exit 0 |
| 6 | post_write_code compiles | Echo `{"agent_action_name":"post_write_code","tool_info":{"file_path":"test.py","edits":[]}}` \| python3 .windsurf/hooks/post_write_code.py | Exit 0 |
| 7 | MySQL KB reachable | `python3 -c "import mysql.connector; c=mysql.connector.connect(user='root',host='localhost'); print('OK'); c.close()"` | OK |
| 8 | codebase_index populated | `sqlite3 .windsurf/hooks.db "SELECT COUNT(*) FROM codebase_index"` | > 0 |

### 10.2 Performance Requirements

| Hook | Max Time | Reason |
|------|----------|--------|
| pre_run_command | 500ms | MySQL query must be fast |
| pre_write_code | 100ms | Regex check only |
| pre_read_code | 50ms | Path check only |
| post_run_command | 1s | MySQL insert + optional query |
| post_write_code | 2s | py_compile + index update |
| post_read_code | 100ms | SQLite insert only |
| post_cascade_response | 1s | MySQL insert |
| post_cascade_response_with_transcript | 2s | MySQL insert + BCL token extraction |
| post_setup_worktree | 5s | Full worktree index build (acceptable, async) |

---

## Stage 11: RELATIONSHIPS TO OTHER PIPELINES

| Pipeline | Relationship |
|----------|-------------|
| `Plf_CliSafeExecutionPipeline.md` | pre_run_command hook replaces/augments cascade_cli.py validation |
| `Plf_DomMcpPipeline.md` | Hook scripts use Dom_MCP tools (mcp1_*) for all operations |
| `Plf_ErrorCapturePipeline.md` | post_run_command hook feeds errors into the error capture pipeline |
| `Plf_BclCodeGraphPipeline.md` | post_write_code hook updates the BCL code graph index |
| `Plf_ConfigCascadePipeline.md` | Hook scripts use config values from dom_mcp config |
| `Plf_Workflow8GraphPipeline.md` | Hooks enforce the gap graph checks (pre_write_code = VBStyle gap) |

---

## Stage 12: IMPLEMENTATION PHASES

### Phase 1: SKELETON (Day 1)
- [ ] Create `.windsurf/hooks/` directory
- [ ] Create `.windsurf/hooks/lib/hook_common.py` (shared utilities)
- [ ] Create `.windsurf/hooks.json` with all 12 hooks configured
- [ ] Create stub scripts for all 12 hooks (exit 0, print "hook fired")
- [ ] Verify hooks fire by watching Cascade UI

### Phase 2: PRE-RUN-COMMAND (Day 2)
- [ ] Implement `pre_run_command.py` with MySQL KB lookup
- [ ] Test with known failure commands
- [ ] Test with safe commands
- [ ] Verify blocking works (exit 2)

### Phase 3: PRE-WRITE-CODE (Day 3)
- [ ] Implement `pre_write_code.py` with VBStyle checker
- [ ] Test with code containing print(), decorators, self._
- [ ] Test with clean VBStyle code
- [ ] Verify blocking works

### Phase 4: POST-HOOKS (Day 4)
- [ ] Implement `post_run_command.py` (logging + error learning)
- [ ] Implement `post_write_code.py` (compile check + index update)
- [ ] Implement `post_read_code.py` (access logging)
- [ ] Implement `post_cascade_response.py` (session logging)
- [ ] Implement `post_cascade_response_with_transcript.py` (full transcript + BCL token extraction)
- [ ] Implement `post_mcp_tool_use.py` (MCP call logging)
- [ ] Implement `post_setup_worktree.py` (worktree indexing)

### Phase 5: CODEBASE INDEX (Day 5)
- [ ] Implement `codebase_index.py` (full AST extraction)
- [ ] Run first full index of workspace
- [ ] Verify index contains all .py files
- [ ] Generate compliance report (violation_count per file)

### Phase 6: PRE-USER-PROMPT + PRE-MCP (Day 6)
- [ ] Implement `pre_user_prompt.py` (sanitization + context injection)
- [ ] Implement `pre_mcp_tool_use.py` (tool validation)
- [ ] Implement `pre_read_code.py` (security check)

### Phase 7: VERIFICATION (Day 7)
- [ ] Run all verification checks from Stage 10
- [ ] Performance test all hooks
- [ ] Test with real Cascade session
- [ ] Document any issues found

---

## Stage 13: RISKS AND MITIGATIONS

| Risk | Severity | Mitigation |
|------|----------|------------|
| MySQL unavailable | Medium | Hook exits 1 (proceed), logs warning |
| Hook script crashes | Medium | Exit 1 (proceed), Cascade sees error in UI |
| Hook too slow | High | Timeout after 2s, exit 0 (proceed) |
| False positive blocking | High | Log all blocks, review weekly, adjust patterns |
| Index grows too large | Low | Prune deleted files, rebuild monthly |
| MySQL connection overhead | Medium | Use connection pooling or persistent connection |
| Hook script has bugs | High | Test thoroughly before enabling show_output |
| pre_write_code blocks legitimate code | High | Start in WARN mode (exit 0 + warning), switch to BLOCK after validation |

---

## Related Documents

- `Plf_CliSafeExecutionPipeline.md` — CLI safe execution state machine (predecessor to pre_run_command hook)
- `Plf_DomMcpPipeline.md` — Dom_MCP Go binary migration (provides the MCP tools)
- `Plf_ErrorCapturePipeline.md` — Error capture pipeline (fed by post_run_command hook)
- `Plf_BclCodeGraphPipeline.md` — BCL code graph (fed by post_write_code hook)
- `core/utility/content_extract.py` — ContentExtract class (pattern source for VBStyle checker)
- `core/Dom_Bcl/ingest_bcl.py` — AST-based ingestion (pattern source for codebase index)
- `Dom_Smart_system_seach/Engine_smart_search.py` — Smart search engine (pattern source for MySQL search)
- [Windsurf Hooks Documentation](https://cognitionai.mintlify.app/desktop/cascade/hooks) — Official hooks reference
