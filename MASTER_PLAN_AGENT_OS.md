# MASTER PLAN — Database-Native Agent Operating System

> "The database is the truth graph. The agent proposes. The orchestrator dispatches. Execution reports back. Nothing bypasses the ledger."

---

## 0. WHAT WE ARE BUILDING

Not an IDE. Not a chat app. Not a file editor.

A **database-native agent operating system for coding cognition** where:

- **Database** = truth graph (artifact store + event ledger + agent state)
- **Agent** = proposer (reads DB context, writes `tool_call` rows, never executes)
- **Orchestrator** = policy gate (sole dispatcher, sole writer of results)
- **Execution** = pure runtime (runs tools, returns results, never touches DB)
- **GUI** = projection (reads DB state, renders it, sends user input to DB)

Everything flows through: **DB → orchestration → DB**. Nothing bypasses.

---

## 1. ARCHITECTURE LAYERS

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1 — PERSISTENCE (Database = Source of Truth)         │
│   MySQL: artifact, event_log, agent_state                   │
│   + existing: code_store.db, efl_brain.db, vb_code_test     │
│   + Qdrant: vector embeddings for semantic retrieval        │
├─────────────────────────────────────────────────────────────┤
│ LAYER 2 — SYNC (Virtual File System)                        │
│   DB row = "file" | DB structure = "folder"                 │
│   Editor tab = view of DB content                           │
│   Files are projections of database rows, not real storage  │
├─────────────────────────────────────────────────────────────┤
│ LAYER 3 — AGENT (ACP / Devin / Multi-model)                 │
│   Reads context from DB → produces action plan              │
│   Writes tool_call rows (status=pending) → never executes   │
│   Models: Devin (ACP), Claude Opus, Claude Sonnet, Ollama   │
│   MCP servers: contextram, pinecone, filesystem, gmail, etc │
├─────────────────────────────────────────────────────────────┤
│ LAYER 4 — EXECUTION (Runtime / Tools)                       │
│   Python execution, shell commands, code eval, API calls    │
│   VBStyle domain dispatch (Run/Tuple3)                      │
│   NEVER writes directly to DB — reports results to orchestr │
├─────────────────────────────────────────────────────────────┤
│ LAYER 5 — GUI (Dynamic, Config-Driven, DB-Backed)           │
│   Reads layout from DB config → renders PyQt6 widgets       │
│   Editor reads/writes artifact table                        │
│   Chat writes to event_log, renders event_log rows          │
│   Terminal runs commands, logs to event_log                 │
│   Powered by: clipboard_monitor_v2 widget builder pattern   │
│   + Unit_GuiLayoutEngine declarative layout                 │
│   + Book.py VBStyle CRUD pattern                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. CORE DATABASE SCHEMA (MySQL — new `agent_os` database)

### 2.1 artifact — Virtual File System

```sql
CREATE TABLE artifact (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    parent_id     BIGINT NULL,
    project_id    BIGINT NULL,
    kind          VARCHAR(32) NOT NULL,     -- project|folder|file|note|config
    name          VARCHAR(255) NOT NULL,
    virtual_path  TEXT NOT NULL,
    content       LONGTEXT NULL,
    content_hash  VARCHAR(64) NULL,
    language      VARCHAR(32) NULL,         -- python|c|swift|markdown|sql|yaml
    source        VARCHAR(64) NULL,         -- mysql_import|agent_created|user_upload|vbstyle
    status        VARCHAR(32) DEFAULT 'active',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_parent (parent_id),
    INDEX idx_path (virtual_path(255)),
    INDEX idx_status (status)
);
```

### 2.2 event_log — Semantic Event Store

```sql
CREATE TABLE event_log (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp       TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3),
    session_id      VARCHAR(128) NOT NULL,
    sequence        INT NOT NULL,
    event_type      VARCHAR(48) NOT NULL,
    agent_id        VARCHAR(64) NULL,
    artifact_id     BIGINT NULL,
    parent_event_id BIGINT NULL,
    message_id      VARCHAR(128) NULL,
    payload         JSON NULL,
    status          VARCHAR(32) DEFAULT 'recorded',
    INDEX idx_session_seq (session_id, sequence),
    INDEX idx_type (event_type),
    INDEX idx_parent (parent_event_id),
    INDEX idx_status (status)
);
```

**Event types:**
`user_input`, `agent_message_chunk`, `agent_plan`, `tool_call`, `tool_result`,
`artifact_write`, `artifact_read`, `execution_log`, `error`, `config_change`,
`session_start`, `session_end`, `agent_message_complete`

### 2.3 agent_state — Current Reasoning + Plan

```sql
CREATE TABLE agent_state (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(128) UNIQUE NOT NULL,
    mode            VARCHAR(32) DEFAULT 'ask',  -- plan|code|ask|bypass
    model           VARCHAR(64) NULL,
    current_plan    JSON NULL,
    current_step    INT DEFAULT 0,
    pending_actions JSON NULL,
    last_event_id   BIGINT NULL,
    status          VARCHAR(32) DEFAULT 'idle',
    context_summary TEXT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 2.4 gui_config — Dynamic GUI Layout (NEW — config-driven UI)

```sql
CREATE TABLE gui_config (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    panel_id    VARCHAR(64) NOT NULL,       -- left|center|right|bottom|activity_bar
    widget_type VARCHAR(64) NOT NULL,       -- tree|editor|chat|terminal|tab_bar|toolbar
    layout_kind VARCHAR(32) NULL,           -- horizontal|vertical|split|grid|form
    config_json JSON NOT NULL,              -- widget properties, styles, bindings
    sort_order  INT DEFAULT 0,
    visible     TINYINT DEFAULT 1,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_panel (panel_id),
    INDEX idx_sort (panel_id, sort_order)
);
```

### 2.5 agent_registry — Multi-Agent Assignment

```sql
CREATE TABLE agent_registry (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name  VARCHAR(64) NOT NULL,
    model       VARCHAR(64) NOT NULL,       -- devin|claude-opus|claude-sonnet|ollama-xxx
    role        VARCHAR(64) NULL,           -- planner|coder|reviewer|tester|architect
    task_id     BIGINT NULL,
    status      VARCHAR(32) DEFAULT 'idle', -- idle|assigned|working|done|failed
    assigned_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    result_json JSON NULL,
    INDEX idx_task (task_id),
    INDEX idx_status (status)
);
```

---

## 3. END-TO-END FLOW (Execution Order)

```
1. USER INPUT → INSERT event_log (user_input) → UPDATE agent_state (thinking)
2. CONTEXT ASSEMBLY → SELECT from event_log + artifact → build prompt → ACP session/prompt
3. STREAM INGEST → INSERT event_log (agent_message_chunk) per token group
4. PLAN UPDATE → INSERT event_log (agent_plan) → UPDATE agent_state (current_plan)
5. ACTION CAPTURE → INSERT event_log (tool_call, status=pending) → UPDATE agent_state (executing)
6. POLICY GATE → orchestrator checks mode (plan/ask/code/bypass) → allow/deny
7. EXECUTION → runtime runs tool → returns result (never writes DB)
8. RESULT PERSIST → UPDATE artifact + INSERT event_log (tool_result, artifact_write)
9. TURN COMPLETE → INSERT event_log (agent_message_complete) → UPDATE agent_state (idle)
10. UI RENDER → SELECT from event_log (id > last_seen) → render chat/plan/diff/terminal
```

---

## 4. VBSTYLE ARCHITECTURE (Existing Foundation)

### 4.1 Core Patterns (from code_store_variations + vbstyle_adapter)

| Pattern | Rule |
|---------|------|
| **Run() dispatch** | `Run(command, params)` routes to methods via if/elif |
| **Tuple3 return** | `(1, data, None)` success / `(0, None, (code, msg, 0))` failure |
| **self.state dict** | All mutable state in `self.state`, never `self._var` |
| **No decorators** | No `@property`, `@staticmethod`, `@classmethod` |
| **No print** | All output via Report class / Tuple3 data |
| **No hardcoded paths** | Paths from `self.state["config"]` |
| **PascalCase** | Classes PascalCase, constants UPPERCASE |
| **Constructor** | `__init__(self, mem=None, db=None, param=None)` |
| **Ghost header** | `[@GHOST]{...}` comment block on every file |
| **VBStyle header** | `[@VBSTYLE]{...}` annotation block |

### 4.2 Existing Infrastructure (LEVERAGE, don't rebuild)

| Component | Location | Status |
|-----------|----------|--------|
| code_store.db | code_store_variations/ | 57 domains, 873 methods, classes+methods tables |
| efl_brain.db | efl_brain/ | execution_log, unit_rankings, learned_fixes, expectation_graph |
| v20_hybrid_best.db | code_store_variations/ | closure_methods, closure_status, closure_tests |
| vb_code_test (MySQL) | localhost:3306 | 1,394 classes, 13,818 methods |
| vb_shared (MySQL) | localhost:3306 | 10,540 learned rules, code_index (23,483 facts) |
| Qdrant | localhost | 15 collections, vector search |
| test_runner.py | code_store_variations/ | ExecutionSandbox, 336/403 passing |
| vbstyle_adapter.py | code_store_variations/ | Auto-transforms to VBStyle compliance |
| vbstyle_dom_scanner.py | Vbs_Code_Verifiation/ | 9 compliance checks |

### 4.3 57 Domains (existing)

AI, Analytics, Archive, ASM, Audit, Automation, Bytecode, CLI, Codec, CodeGraph,
Compass, Config, Convert, CSplit, CU, DB, DB_Inv, DB_Studio, Documentation,
Factory, FileOps, Folder, Governance, Graph, GUI, Index, Ingest, Ingest_CLI,
Ingest_GUI, IO, Knowledge, Log, Memory, Messaging, Network, Orchestration,
Package, Parse, Process, QA, Qt, Rescue, Runtime, Schedule, Search, Security,
Storage, Style, System, Testing, Text, Transform, Unify, Validate, WWSIndex, YAML

### 4.4 Computational Core ("Teddy Bear")

Largest VBStyle domain classes:
1. **dom_ingest_gui.py** — Ingest_GuiDomain (44,513 lines) — GUI data ingestion
2. **dom_yaml.py** — YamlDomain (41,157 lines) — YAML processing, schema management
3. **dom_factory.py** — FactoryConfig (21,330 lines) — VBStyle code generation factory
4. **dom_cli.py** — CliDomain (20,480 lines) — CLI dispatch, reporting

---

## 5. DYNAMIC GUI ENGINE (Config-Driven UI)

### 5.1 Existing Implementations (choose best, merge)

| Version | Location | Lines | Language | Strength |
|---------|----------|-------|----------|----------|
| **clipboard_monitor_v2.py** | contestsystem/gui/ | 1,831 | Python/PyQt6 | Widget builder, bracket notation `[Type]{prop:val}`, config-driven |
| **Unit_GuiLayoutEngine.py** | .../TOKAI/.../ | 1,370 | Python/PyQt6 | Declarative YAML/JSON layout, signal/slot, in-memory SQLite state |
| **Unit_GuiKernel.c** | .../TOKAI/.../ | 690 | C | Table-driven kernel, draw commands, hit zones, no framework |
| **Lib_LayoutEngine.swift** | .../APP_Dynamic_Gui/ | 327 | Swift | VB-style layout semantics, size constraints |
| **Dynamic_Gui_Engine_Master.md** | .../Master_Data/docs/ | 966 | Markdown | Master architecture doc: property inheritance, container laws, theming |
| **Book.py** | bin/BookSystem/ | 4,931 | Python | VBStyle CRUD, Run/Tuple3, full book management |

### 5.2 Strategy: DB-Driven GUI

```
gui_config table (MySQL)
    ↓ (config_json per panel/widget)
GUI Engine reads config
    ↓
Builds PyQt6 widgets dynamically
    ↓
User interacts → writes to event_log
    ↓
GUI re-renders from DB state
```

**Key principle:** Changing a `gui_config` row changes the UI without restarting.
The GUI is a **projection of database configuration**, not hardcoded Python.

### 5.3 Bracket Notation (from clipboard_monitor)

```python
# Widget spec format:
[QPushButton]{text:"Send"; class:"primary"; onclick:"send_message"}
[QTextEdit]{id:"chat_display"; readonly:true; placeholder:"Chat with Devin..."}
[QSplitter]{orientation:"horizontal"; sizes:[280,820,420]}
```

The GUI engine parses these → builds PyQt6 widgets → applies properties → connects signals.

### 5.4 Layout Engine (from Unit_GuiLayoutEngine)

```yaml
# Declarative layout (stored in gui_config.config_json)
layout:
  root: main_splitter
  kind: horizontal
  children:
    - id: sidebar
      kind: vertical
      children:
        - {type: activity_bar, width: 50}
        - {type: tree, source: "SELECT * FROM artifact WHERE parent_id IS NULL"}
    - id: editor
      kind: stacked
      children:
        - {type: code_editor, source: "SELECT content FROM artifact WHERE id=?"}
    - id: right_panel
      kind: vertical
      children:
        - {type: chat, source: "SELECT * FROM event_log WHERE session_id=? ORDER BY sequence"}
```

---

## 6. BOOK SYSTEM (VBStyle Rules Database)

### 6.1 Existing

- **Book.py** (4,931 lines) — full VBStyle CRUD with Run/Tuple3
- **vbstyle-book/** — SQLite with 71 VBStyle rules, parts, chapters, sections
- **populate_book.py** — ingests from obey.md (71 rules) + Binary_congf_intenaldb_gui.md

### 6.2 Integration

The Book system becomes the **architectural rules authority** for the agent OS:
- Agent reads Book rules before writing code → enforces VBStyle compliance
- Orchestrator checks Book rules before promoting artifacts
- GUI can display Book rules as documentation/reference

---

## 7. MULTI-AGENT SYSTEM

### 7.1 Models

| Model | Role | Access |
|-------|------|--------|
| Devin (ACP) | Primary agent — chat, code, plan | MCP servers, filesystem |
| Claude Opus | Deep reasoning, architecture | API |
| Claude Sonnet | Fast coding, implementation | API |
| Ollama (local) | Offline fallback, quick tasks | localhost:11434 |

### 7.2 Task Assignment Flow

```
1. User defines plan (via chat or manual)
2. Plan broken into tasks → INSERT agent_registry (status=assigned)
3. Each task assigned to best model:
   - Architecture → Claude Opus
   - Implementation → Claude Sonnet / Devin
   - Review → Claude Opus
   - Testing → Devin (sandbox execution)
4. Agents work in parallel where possible
5. Results written to event_log → orchestrator validates
6. Survivors promoted to artifact table
```

### 7.3 MCP Servers (already configured)

contextram, devin/pinecone-mcp-server, filesystem, gmail, taskplanner,
yahoo-mail, yahoo-mail-go

---

## 8. IMPLEMENTATION PHASES

### Phase 1 — Foundation (DB + Core Tables)
- [ ] Create `agent_os` MySQL database
- [ ] Create `artifact`, `event_log`, `agent_state`, `gui_config`, `agent_registry` tables
- [ ] Import existing VBStyle code from vb_code_test → artifact table
- [ ] Import Book rules → artifact table (kind=note, language=markdown)

### Phase 2 — GUI Shell (DB-Driven)
- [ ] Merge clipboard_monitor_v2 widget builder + Unit_GuiLayoutEngine declarative layout
- [ ] GUI reads layout from `gui_config` table → renders PyQt6
- [ ] Editor reads/writes `artifact` table (not filesystem)
- [ ] Chat panel writes to `event_log`, renders from `event_log`
- [ ] Terminal panel runs commands → logs to `event_log`
- [ ] Activity bar + right panel (from vscode_style_planner.py shell)

### Phase 3 — Agent Integration (ACP + Multi-model)
- [ ] Wire ACP Devin chat → event_log flow (from devindocs_session_viewer.py)
- [ ] Add Claude Opus/Sonnet as alternative agents
- [ ] Agent reads context from event_log + artifact → proposes tool_call rows
- [ ] Orchestrator processes pending tool_calls based on mode (plan/ask/code/bypass)

### Phase 4 — Execution Engine
- [ ] Build orchestrator loop (polls pending tool_calls, dispatches, writes results)
- [ ] Wire VBStyle domain dispatch (Run/Tuple3) as execution tools
- [ ] Sandbox execution (from test_runner.py ExecutionSandbox)
- [ ] Behavioral validation (from PLAN.md — Candidate → Test → Survive → Promote)

### Phase 5 — Dynamic GUI (Config-Driven)
- [ ] Store full layout in `gui_config` table
- [ ] GUI engine reads config → builds widgets dynamically
- [ ] Changing config rows changes UI without restart
- [ ] Bracket notation parser for widget specs
- [ ] Theme system from DB config

### Phase 6 — Multi-Agent Orchestration
- [ ] Task decomposition (plan → tasks → agent_registry)
- [ ] Parallel agent execution
- [ ] Result merging + conflict resolution
- [ ] Survivor ranking for code artifacts

### Phase 7 — Semantic Layer
- [ ] Vector embeddings for artifacts (Qdrant)
- [ ] Semantic search for code retrieval
- [ ] Domain induction from real code ecosystems
- [ ] CodeBERT/GraphCodeBERT for behavior fingerprinting

---

## 9. FILE INVENTORY (Key Sources)

### GUI Engines
| File | Path | Purpose |
|------|------|---------|
| vscode_style_planner.py | /tmp/ | VS Code shell (activity bar, tabs, terminal, right panel) |
| clipboard_monitor_v2.py | ~/contestsystem/gui/ | Widget builder, bracket notation, config-driven |
| Unit_GuiLayoutEngine.py | ~/Documents/.../TOKAI/ | Declarative YAML/JSON layout engine |
| Unit_GuiKernel.c | ~/Documents/.../TOKAI/ | C table-driven GUI kernel |
| Dynamic_Gui_Engine_Master.md | ~/Documents/.../Master_Data/ | Architecture documentation |
| devindocs_session_viewer.py | ~/bin/ | ACP Devin chat + MySQL code editor (working prototype) |

### VBStyle Core
| File | Path | Purpose |
|------|------|---------|
| code_store_variations/ | ~/Qdrant.../ | 57 domain implementations, closure engine |
| CodeStore.py | code_store_variations/ | Code-in-database system |
| vbstyle_adapter.py | code_store_variations/ | Auto-transform to VBStyle |
| vbstyle_dom_scanner.py | Vbs_Code_Verifiation/ | 9 compliance checks |
| PLAN.md | code_store_variations/ | Behavioral validation architecture |

### Book System
| File | Path | Purpose |
|------|------|---------|
| Book.py | ~/bin/BookSystem/ | VBStyle CRUD (4,931 lines) |
| vbstyle-book/ | ~/bin/ | 71 rules database builder |
| obey.md | ~/contestsystem/.devin/rules/ | 71 VBStyle rules source |

### Databases
| Database | Location | Contents |
|----------|----------|----------|
| agent_os (NEW) | MySQL localhost | artifact, event_log, agent_state, gui_config, agent_registry |
| vb_code_test | MySQL localhost | 1,394 VB classes, 13,818 methods |
| vb_shared | MySQL localhost | 10,540 learned rules, code_index (23,483 facts) |
| code_store.db | SQLite | 57 domains, 873 methods, test results |
| efl_brain.db | SQLite | execution_log, learned_fixes, expectation_graph |
| v20_hybrid_best.db | SQLite | closure_methods, closure_status |
| Qdrant | localhost:6333 | 15 collections, vector embeddings |

---

## 10. OPEN QUESTIONS (To Resolve As We Go)

1. **Which GUI engine version is the base?** clipboard_monitor_v2 (widget builder) or Unit_GuiLayoutEngine (declarative YAML) or merge both?
2. **Swift/C ports needed?** Or is Python/PyQt6 sufficient for the GUI kernel?
3. **How much of the existing vscode_style_planner.py shell do we keep?** (activity bar, tabs, terminal, right panel are working)
4. **Agent mode defaults?** Start in `ask` mode (safe) or `code` mode (autonomous)?
5. **Which MCP servers are priority?** All 7 or start with contextram + filesystem?
6. **Claude API integration?** Direct API call or through ACP?
7. **Vector embeddings model?** MLX local or CodeBERT API?

---

## 10.1 ANSWERS (Resolved 2026-06-22)

> Decisions made by investigating the current system state. Each answer includes reasoning grounded in what actually exists today.

### Q1: Which GUI engine version is the base?

**Decision: Merge `clipboard_monitor_v2.py` (widget builder + bracket notation) with the existing `gui_engine/gui_engine.py` (SQLite style/UI DB + PyQt6 renderer).**

**Reasoning:**
- `gui_engine/gui_engine.py` (711 lines) already exists in-repo and consolidates 5 prior modules: `StyleDBV2` (SQLite-backed style store), `StyleEngineV2` (selector engine), `QtStyleRendererV2` (applies DB styles to PyQt6 widgets), `UIDBV4` (UI tree + component library in SQLite), `GUIDecisionEngine` (context-driven component selection). This is the DB-driven style/render foundation the plan calls for.
- `clipboard_monitor_v2.py` (1,831 lines at `~/contestsystem/gui/`) provides the bracket-notation widget builder (`[QPushButton]{text:"Send"; class:"primary"}`) and config-driven widget construction pattern. This is the dynamic widget factory.
- `Unit_GuiLayoutEngine.py` (declarative YAML layout) was referenced in the plan but **does not exist** anywhere in the local filesystem — it cannot be used as a base. The declarative YAML layout concept will be implemented fresh as `gui_config.config_json` rows (the DB already serves this role via `UIDBV4`'s UI tree).
- **Merge strategy:** `gui_engine.py` becomes the style/render/DB layer (already in-repo, already SQLite-backed). Import `clipboard_monitor_v2`'s bracket-notation parser and widget builder as a new module in `gui_engine/`. The `gui_config` MySQL table replaces the SQLite UI tree for the agent OS (Phase 5).

### Q2: Swift/C ports needed?

**Decision: No. Python/PyQt6 is sufficient for the GUI kernel. No Swift or C ports.**

**Reasoning:**
- `Unit_GuiKernel.c` (690-line C table-driven kernel) **does not exist** in the local filesystem — searched all of `/Users/wws` to depth 8.
- `Lib_LayoutEngine.swift` (327 lines) exists only in an archived old-account folder (`~/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/APP_Dynamic_Gui/`) — not in any active project.
- The target platform is macOS on Apple Silicon (MLX is available, PyQt6 runs natively). PyQt6 provides native widget rendering, GPU-accelerated compositing, and sufficient performance for a developer tool GUI.
- Swift/C would add build complexity (separate toolchains, FFI bridges, dual-maintenance) with no measurable benefit for a coding-cognition GUI that renders text, trees, and panels.
- If a performance-critical custom canvas is needed later (e.g., graph visualization), revisit C for that specific component only. Not for the general GUI kernel.

### Q3: How much of vscode_style_planner.py shell do we keep?

**Decision: Keep nothing — rebuild the VS Code-like shell as DB-driven GUI from `gui_config` rows.**

**Reasoning:**
- `vscode_style_planner.py` **does not exist** anywhere in the filesystem (searched `/Users/wws` to depth 8, including `/tmp/`). The plan referenced it at `/tmp/` which is ephemeral and has been cleared.
- There is no existing shell to keep. The activity bar, tabs, terminal, and right panel must be built fresh.
- **Build approach:** Define the shell layout as `gui_config` rows (panel_id = `activity_bar`, `left`, `center`, `right`, `bottom`; widget_type = `tab_bar`, `tree`, `editor`, `chat`, `terminal`). The GUI engine reads these rows and constructs PyQt6 widgets using the bracket-notation builder from Q1. This is the DB-driven approach the plan already describes in Phase 2/Phase 5 — we just start it from scratch since no prior shell survives.

### Q4: Agent mode defaults?

**Decision: Default to `ask` mode (safe). User must explicitly switch to `code` or `bypass`.**

**Reasoning:**
- The `agent_state` table schema already defaults `mode` to `'ask'` (line 119 of the plan). This is the correct default.
- `ask` mode: agent proposes actions, writes `tool_call` rows with `status=pending`, orchestrator presents them to the user, user approves/denies before execution. This is the safest mode and matches the VBStyle `[@noexec]` philosophy ("do not execute code or scripts without explicit user instruction").
- `code` mode (autonomous execution): agent proposes + orchestrator auto-executes without per-action approval. This should require an explicit user action to enable (e.g., a mode toggle in the GUI, confirmed via `event_log`). Never the default.
- `bypass` mode (no policy gate): agent executes directly, orchestrator skipped. This is dangerous and should require explicit confirmation with a warning. Reserved for trusted sandbox environments only.
- `plan` mode: agent only plans, never proposes executable actions. Also safe, but `ask` is more useful as a default since it allows the agent to propose while keeping the human in the loop.
- **Session start:** Every new session begins in `ask` mode. The mode is stored in `agent_state.mode` and can be changed via a GUI control that writes a `config_change` event to `event_log`.

### Q5: Which MCP servers are priority?

**Decision: Phase 3 starts with `contextram` + `filesystem` + `taskplanner`. Email servers and Pinecone are deferred to later phases.**

**Reasoning:**
- 7 MCP servers are configured in `~/.codeium/windsurf/mcp_config.json`: contextram, devin/pinecone-mcp-server, filesystem, gmail, taskplanner, yahoo-mail, yahoo-mail-go.
- **Priority 1 (Phase 3 — Agent Integration):**
  - `contextram` — context assembly is core to the agent reading DB context and building prompts. The agent OS flow (step 2: context assembly) depends on this.
  - `filesystem` — the agent needs to read/write artifact files during execution. Already configured for `/Users/wws`.
  - `taskplanner` — already in active use for task management across the workspace. The agent OS should integrate with it for task decomposition (Phase 6).
- **Priority 2 (Phase 6 — Multi-Agent):**
  - `devin/pinecone-mcp-server` — alternative vector search. Lower priority because Qdrant is already the primary vector store (15 collections, 384-dim BGE). Pinecone is a backup/alternative, not core.
- **Priority 3 (Phase 7+ — Semantic Layer extensions):**
  - `gmail`, `yahoo-mail`, `yahoo-mail-go` — email ingestion. Useful for the broader knowledge base but not core to the agent OS coding-cognition loop. The email ingestion pipeline (`email_ingestion.py`) already exists as a standalone script; MCP integration is a convenience, not a necessity.

### Q6: Claude API integration — direct API call or through ACP?

**Decision: Direct API call for Claude. ACP is used only for Devin.**

**Reasoning:**
- `BookSystem/config.py` (and `BCL/config.py`) already define Claude API configuration: endpoint `https://api.anthropic.com/v1/messages`, model `claude-3-5-sonnet`, env var `ANTHROPIC_API_KEY`. No actual Claude API client code exists yet — only config.
- ACP (Agent Communication Protocol) is Devin's protocol. Routing Claude through ACP would add protocol overhead (serialization, session management) for no benefit — Claude has its own well-documented HTTP API.
- **Architecture:** Each agent model gets its own adapter:
  - `DevinAgent` → ACP session/prompt (from `devindocs_session_viewer.py` pattern)
  - `ClaudeAgent` → direct `anthropic` API calls (HTTP POST to `/v1/messages`)
  - `OllamaAgent` → direct Ollama API (localhost:11434)
- All adapters implement the same interface: `read_context(event_log, artifact) → propose_plan() → write_tool_calls()`. The orchestrator doesn't care which model produced the `tool_call` rows.
- **Simplicity wins:** Direct API = fewer moving parts, easier debugging, no ACP server dependency for non-Devin models.

### Q7: Vector embeddings model — MLX local or CodeBERT API?

**Decision: MLX local with BGE-small-en-v1.5 (384-dim). Continue the existing approach. No CodeBERT API.**

**Reasoning:**
- BGE-small-en-v1.5 (384-dim, Cosine) is already the standard across the entire system:
  - `export_chat_embeddings.py` — chat history (MODEL_NAME = "BAAI/bge-small-en-v1.5", 384-dim)
  - `embed_knowledge_base.py` — 11,534 knowledge rows embedded
  - `email_ingestion.py` — email store collection
  - `BookSystem/BgeSearch.py` — book semantic search
  - `qa_engine/GhostQAEngine.py` — QA engine embeddings
  - All Qdrant collections use 384-dim Cosine.
- MLX is already in use for LLM generation in `GhostQAEngine.py` (`mlx_lm` for generation, `mlx_embedding_models` for embeddings). The Apple Silicon MLX framework runs locally with no API costs.
- CodeBERT API would introduce: per-query API costs, network latency, external dependency, and a different vector dimensionality (768-dim) that's incompatible with existing 384-dim Qdrant collections.
- **For code-specific embeddings (Phase 7):** When behavior fingerprinting is needed, evaluate CodeBERT/GraphCodeBERT as a *separate* Qdrant collection (768-dim) for code semantics only. But the primary artifact embeddings stay BGE-small-en-v1.5 via MLX local. This keeps the existing 15 collections compatible and cost-free.

---

## 11. NOTES (Free-form, add as we go)

*(This section is for things you tell me that don't fit neatly into the plan above. I'll organize them as we go.)*

---
*Last updated: 2026-06-22 (Q1-Q7 answered in section 10.1)*
*This is a living document. Update as decisions are made.*
