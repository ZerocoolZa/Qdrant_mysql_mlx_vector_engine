# Dom_MCP — Unified Native MCP Server System

> **Status:** Plan — inventory complete, ready for agent dispatch
> **Date:** 2026-06-28
> **Author:** wws + Devin
> **Domain:** `Dom_Mcp` (new domain)
> **Goal:** Replace all Node.js/npx MCP servers with one unified native binary. No Node. No npx. No Docker-for-MCP. One binary, one protocol, one authority.

---

## 1. The Problem

**Every Node.js MCP server is a separate process that eats RAM and spawns children.**

The IDE (Cascade/Windsurf) spawns one process per MCP server. For the active Cascade session alone, that's **3 Node.js processes** running simultaneously, each with its own V8 isolate, event loop, and 30-80 MB RAM. On a low-RAM machine, this causes noticeable slowdown.

Worse: `npx -y @modelcontextprotocol/server-*` downloads and caches packages on every start, adding 2-5 seconds of startup latency per server.

---

## 2. Complete MCP Inventory (verified 2026-06-28)

### 2.1 Cascade/Windsurf — `~/.codeium/windsurf/mcp_config.json` (7 servers)

| # | Server | Command | Language | Status | What It Does |
|---|--------|---------|----------|--------|--------------|
| 1 | `contextram` | `node /Users/wws/contestsystem/ContextRAMSwift/mcp-server/index.js` | **Node.js** | ACTIVE | Wraps Swift `ctx` CLI — 22 tools for context nodes |
| 2 | `devin/pinecone-mcp-server` | `npx -y @pinecone-database/mcp` | **Node.js (npx)** | ACTIVE | HTTP client to Pinecone vector DB API |
| 3 | `filesystem` | `/Users/wws/go/bin/mcp-filesystem-server` | **Go** | ACTIVE | File read/write/list/search |
| 4 | `gmail` | `npx @gongrzhe/server-gmail-autoauth-mcp` | Node.js (npx) | DISABLED | Gmail access |
| 5 | `taskplanner` | `node .../taskplanner-1.5.2.../mcp-server.js` | **Node.js** | ACTIVE | Task board CRUD (markdown files in `.tasks/`) |
| 6 | `yahoo-mail` | `node /Users/wws/yahoo-mail-mcp-server/server.js` | Node.js | DISABLED | Yahoo Mail IMAP read |
| 7 | `yahoo-mail-go` | `/Users/wws/.../mcp-server-email/mcp-server-email` | **Go** | DISABLED | Multi-account email (IMAP/SMTP) |

**Active Node.js processes: 3** (contextram, pinecone, taskplanner)
**Active Go processes: 1** (filesystem — already native!)

### 2.2 Devin CLI — `~/.config/devin/config.json` (1 server)

| # | Server | Command | Language | Status | What It Does |
|---|--------|---------|----------|--------|--------------|
| 1 | `msearch` | `python3 .../msearch_mcp_server.py` | **Python** | ACTIVE | Wraps C `msearch` binary — searches 215K+ messages in MySQL+SQLite |

### 2.3 Kilo — `~/.config/kilo/kilo.json` (5 servers)

| # | Server | Command | Language | Status | What It Does |
|---|--------|---------|----------|--------|--------------|
| 1 | `memory` | `npx -y @modelcontextprotocol/server-memory` | **Node.js (npx)** | ACTIVE | JSON file memory store |
| 2 | `contextram` | `node .../ContextRAMSwift/mcp-server/index.js` | **Node.js** | ACTIVE | Same as Cascade |
| 3 | `devin-sqlite` | `docker run -i --rm mcp/sqlite` | **Docker** | ACTIVE | SQLite queries via Docker container |
| 4 | `filesystem` | `npx -y @modelcontextprotocol/server-filesystem` | **Node.js (npx)** | ACTIVE | File operations |
| 5 | `taskplanner` | `node .../mcp-server.js` | **Node.js** | ACTIVE | Same as Cascade |

### 2.4 Rapid-MLX — `~/.config/rapid-mlx/mcp.json` (1 server)

| # | Server | Command | Language | Status |
|---|--------|---------|----------|--------|
| 1 | `msearch` | `python3 .../msearch_mcp_server.py` | Python | ACTIVE |

### 2.5 Standalone (not configured in any IDE)

| # | Server | Path | Language | What It Does |
|---|--------|------|----------|--------------|
| 1 | `chatgpt_mcp_server.py` | `/Users/wws/Downloads/chatgpt_mcp_server.py` | Python | ChatGPT conversation search (5 tools) |
| 2 | `Pindrop MCP` | `/Users/wws/contestsystem/ContextRAMSwift/Sources/pindrop/...` | Swift | HTTP MCP server for Pindrop macOS app (internal, not IDE-facing) |
| 3 | `hermes-agent mcp_tool.py` | `/Users/wws/hermes-agent/tools/mcp_tool.py` | Python | MCP **client** (not a server) — connects to external MCP servers |

### 2.6 Summary by Language

| Language | Server Count | Active in Cascade | Needs Rewrite? |
|----------|-------------|-------------------|----------------|
| **Node.js** | 5 (contextram, pinecone, taskplanner, memory, devin-sqlite-via-Docker) | 3 | **YES** — primary target |
| **Python** | 2 (msearch, chatgpt) | 0 (Devin only) | Optional — Python is acceptable, but wrapper can be native |
| **Go** | 2 (filesystem, email) | 1 (filesystem) | **NO** — already native, just integrate |
| **Swift** | 1 (Pindrop) | 0 | NO — app-internal, leave alone |
| **Docker** | 1 (devin-sqlite) | 0 | YES — replace with native SQLite |

---

## 3. The Solution: Dom_Mcp

**One native binary. All MCP tools. No Node. No npx. No Docker.**

```
                    IDE (Cascade / Devin / Kilo)
                            |
                            | spawns: dom_mcp --config <path>
                            |
                    ┌───────┴───────┐
                    │   Dom_Mcp     │  ← single Rust binary (~5 MB)
                    │   (Rust)      │
                    ├───────────────┤
                    │ tool: msearch       │ → subprocess to C binary
                    │ tool: contextram    │ → subprocess to Swift `ctx` binary
                    │ tool: filesystem    │ → native std::fs
                    │ tool: taskplanner   │ → native markdown CRUD
                    │ tool: pinecone      │ → native HTTP client (reqwest)
                    │ tool: memory        │ → native JSON file store
                    │ tool: sqlite        │ → native rusqlite
                    │ tool: email         │ → native IMAP/SMTP (or call Go binary)
                    │ tool: chatgpt       │ → native JSON file search
                    └───────────────┘
                            |
                    ┌───────┴───────┐
                    │  DomSystem    │  ← manages backing services
                    │  (acquire/    │
                    │   release)    │
                    └───────────────┘
```

### 3.1 Why Go (updated from Rust — Go already installed)

- **Single binary** — no runtime, no V8, no node_modules, no Docker image
- **~5 MB RAM** per process vs 50 MB for Node
- **Sub-millisecond startup** vs 1-3 seconds for Node (npx is even worse: 2-5s)
- **Native SQLite** via `modernc.org/sqlite` (pure Go, no CGO) or `mattn/go-sqlite3`
- **Native HTTP** via `net/http` (stdlib)
- **Native filesystem** via `os` + `path/filepath` (stdlib)
- **Memory safe** — garbage collected, no segfaults like C
- **Official MCP SDK exists** — `github.com/modelcontextprotocol/go-sdk` (maintained with Google)
- **Go 1.26.4 already installed** on this machine — zero setup needed
- **Cross-platform** — compiles to macOS arm64, Linux, Windows
- **Existing reference**: `mcp-filesystem-server` Go binary already running in production

### 3.2 Key Insight: Most Node.js MCP servers are thin wrappers

| Server | Node.js does | Real logic lives in | Rewrite effort |
|--------|-------------|---------------------|----------------|
| `contextram` | MCP protocol wrapper | Swift `ctx` binary (subprocess per call) | **Low** — just replace the wrapper |
| `pinecone` | HTTP client to Pinecone API | Pinecone cloud service | **Low** — HTTP client in Rust |
| `taskplanner` | Markdown file CRUD | `.tasks/*.md` files | **Medium** — reimpl CRUD logic |
| `memory` | JSON file read/write | `knowalag.json` file | **Low** — JSON file ops |
| `devin-sqlite` | Docker container | SQLite file | **Low** — rusqlite directly |
| `msearch` (Python) | MCP protocol wrapper | C `msearch` binary | **Low** — just replace the wrapper |

**The Node.js servers don't contain real logic.** They're protocol adapters. The actual work happens in:
- Swift binaries (contextram)
- C binaries (msearch)
- Cloud APIs (pinecone)
- Files on disk (taskplanner, memory)
- SQLite databases (devin-sqlite)

Replacing the Node.js wrapper with a Rust wrapper is straightforward.

---

## 4. Architecture

### 4.1 Single binary, modular tools

```
dom_mcp  (single Go binary, ~5 MB compiled)
├── main.go                   — entry point, reads config, starts stdio loop
├── mcp_protocol.go           — MCP JSON-RPC 2.0 protocol handler (stdio)
├── mcp_registry.go           — tool registry (name → handler fn)
├── config.go                 — TOML config reader
├── dom_system.go             — DomSystem acquire/release bridge
├── tools/
│   ├── tools.go              — tool interface definition
│   ├── msearch.go            — subprocess to C msearch binary
│   ├── contextram.go         — subprocess to Swift ctx binary
│   ├── filesystem.go         — native os/path/filepath operations
│   ├── taskplanner.go        — native markdown file CRUD
│   ├── pinecone.go           — HTTP client to Pinecone API (net/http)
│   ├── memory.go             — JSON file store (encoding/json)
│   ├── sqlite.go             — SQLite queries (modernc.org/sqlite)
│   ├── email.go              — IMAP/SMTP (or call Go binary)
│   └── chatgpt.go            — ChatGPT JSON file search
├── go.mod
└── dom_mcp.toml              — example config
```

### 4.2 MCP protocol — the IDE doesn't know it's not Node

```
IDE spawns:     dom_mcp --config ~/.config/devin/dom_mcp.toml
                ↓
Dom_Mcp reads:  TOML config — which tools are enabled, their settings
                ↓
Dom_Mcp listens: stdin for JSON-RPC requests (MCP protocol)
                ↓
Dom_Mcp routes: request → tool handler → response
                ↓
Dom_Mcp writes: JSON-RPC response to stdout
```

The MCP protocol is just stdio JSON-RPC. The IDE spawns `dom_mcp` instead of `node server.js`. **Same protocol, different binary. Zero IDE changes needed beyond the config.**

### 4.3 Configuration

```toml
# ~/.config/devin/dom_mcp.toml
[server]
name = "dom_mcp"
version = "1.0.0"

[tools]
# Enable only the tools you need — unused tools add zero overhead
enabled = [
    "msearch",
    "contextram",
    "filesystem",
    "taskplanner",
    "pinecone",
]

# --- Tool configurations ---

[tools.msearch]
binary = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"
timeout_ms = 30000

[tools.contextram]
ctx_binary = "/Users/wws/contestsystem/ContextRAMSwift/.build/release/ctx"
store_path = "~/.contextram/context.json"
timeout_ms = 10000

[tools.filesystem]
allowed_dirs = [
    "/Users/wws/Qdrant_mysql_mlx_vector_engine",
    "/Users/wws/contestsystem",
    "/Users/wws/Downloads",
]

[tools.taskplanner]
tasks_dir = "/Users/wws/Qdrant_mysql_mlx_vector_engine/.tasks"

[tools.pinecone]
api_key_env = "PINECONE_API_KEY"  # read from environment
index = "devin-memory"
timeout_ms = 30000

[tools.sqlite]
db_path = "/Users/wws/sqlit.db"

[tools.memory]
memory_file = "/Users/wws/contestsystem/workspace/Casade_Libary/Lessons/knowalag.json"

# --- DomSystem integration ---

[dom_system]
enabled = true
# Dom_Mcp will call DomSystem.acquire("mysql") before msearch queries
# and DomSystem.release("mysql") after
acquire_services = ["mysql"]  # services that MCP tools depend on
```

### 4.4 IDE config changes

**Cascade/Windsurf** — `~/.codeium/windsurf/mcp_config.json`:
```json
{
  "mcpServers": {
    "dom_mcp": {
      "command": "/Users/wws/.local/bin/dom_mcp",
      "args": ["--config", "/Users/wws/.config/devin/dom_mcp.toml"],
      "disabled": false
    }
  }
}
```

**Devin** — `~/.config/devin/config.json`:
```json
{
  "mcpServers": {
    "dom_mcp": {
      "command": "/Users/wws/.local/bin/dom_mcp",
      "args": ["--config", "/Users/wws/.config/devin/dom_mcp.toml"],
      "transport": "stdio"
    }
  }
}
```

**Kilo** — `~/.config/kilo/kilo.json`:
```json
{
  "mcpServers": {
    "dom_mcp": {
      "type": "local",
      "command": ["/Users/wws/.local/bin/dom_mcp", "--config", "/Users/wws/.config/devin/dom_mcp.toml"]
    }
  }
}
```

**One process instead of 3-5.** Each IDE spawns one `dom_mcp` binary. Dom_Mcp handles all tool routing internally.

---

## 5. Migration Plan

### Phase 1: Inventory ✅ COMPLETE
- [x] Found all MCP servers across all IDEs (Cascade, Devin, Kilo, Rapid-MLX)
- [x] Documented language, tools, transport, dependencies
- [x] Identified which are thin wrappers vs real logic

### Phase 2: Rust scaffold
- [ ] Create `Dom_Mcp/` domain directory under `Qdrant_mysql_mlx_vector_engine/`
- [ ] Set up Cargo project with dependencies:
  - `rmcp` — Rust MCP SDK (stdio JSON-RPC)
  - `serde` + `serde_json` — JSON serialization
  - `toml` — config file parsing
  - `rusqlite` — SQLite (for sqlite tool)
  - `reqwest` — HTTP client (for pinecone tool)
  - `tokio` — async runtime
- [ ] Implement `mcp_protocol.rs` — stdio JSON-RPC handler
- [ ] Implement `mcp_registry.rs` — tool registration and dispatch
- [ ] Implement `config.rs` — TOML reader
- [ ] Build and verify: `dom_mcp --version` works, `dom_mcp --list-tools` shows empty list

### Phase 3: Port tools (priority order — easiest first)

| Priority | Tool | Effort | Why This Order |
|----------|------|--------|----------------|
| 1 | `filesystem` | Low | Already have Go reference. Native `std::fs`. No external deps. |
| 2 | `memory` | Low | JSON file read/write. `serde_json`. Trivial. |
| 3 | `pinecone` | Low | HTTP client to cloud API. `reqwest`. No local state. |
| 4 | `msearch` | Low | Subprocess to C binary. `std::process`. Just protocol wrapper. |
| 5 | `contextram` | Low | Subprocess to Swift `ctx` binary. `std::process`. Just protocol wrapper. |
| 6 | `sqlite` | Low | `rusqlite` directly. Replaces Docker container. |
| 7 | `taskplanner` | Medium | Markdown file CRUD logic needs reimplementation. |
| 8 | `chatgpt` | Low | JSON file search. Optional (not currently configured). |
| 9 | `email` | Medium | IMAP/SMTP. Can either reimplement in Rust or call existing Go binary. |

For each tool:
1. Read the existing source (Node.js/Python) to understand tool definitions and I/O schemas
2. Reimplement in Rust as `tools/<name>.rs`
3. Test: `dom_mcp --tool <name> --test` runs the tool in isolation
4. Verify: IDE can call the tool through Dom_Mcp and gets the same result as before

### Phase 4: IDE cutover (one IDE at a time)
1. **Kilo first** (lowest risk — not the primary dev IDE)
   - Update `~/.config/kilo/kilo.json` to use `dom_mcp`
   - Test each tool through Kilo
   - Verify no Node/npx processes spawn
2. **Devin second** (only uses msearch — simplest cutover)
   - Update `~/.config/devin/config.json`
   - Test msearch through Dom_Mcp
3. **Cascade last** (primary IDE — highest risk)
   - Update `~/.codeium/windsurf/mcp_config.json`
   - Test all 5 active tools (contextram, pinecone, filesystem, taskplanner, msearch)
   - Monitor RAM: should drop from ~150 MB (3 Node processes) to ~5 MB (1 Rust process)

### Phase 5: Cleanup
- [ ] Retire Node.js MCP server files (mark `[@clean]` → BCL lifecycle retire)
- [ ] Remove `node_modules` directories from MCP server folders
- [ ] Remove `mcp/sqlite` Docker image (replaced by native rusqlite)
- [ ] Uninstall npx packages: `@modelcontextprotocol/server-memory`, `@modelcontextprotocol/server-filesystem`, `@pinecone-database/mcp`
- [ ] Document the new architecture in `.context/` and `AGENTS.md`
- [ ] Add VBStyle rules to `rule_tokens` (see Section 9)

---

## 6. Tool Mapping — Detailed

### 6.1 contextram (Node.js → Rust subprocess wrapper)

**Current:** `node index.js` → spawns `ctx` binary per tool call → parses JSON output → returns via MCP

**New:** `dom_mcp` → spawns `ctx` binary per tool call → parses JSON output → returns via MCP

**Effort:** Low. The Rust code is just a subprocess wrapper + JSON parsing. The 22 tools all map to `ctx <subcommand> <args>`.

| MCP Tool | ctx subcommand |
|----------|---------------|
| `ctx_put` | `ctx put --type <type> --content <content>` |
| `ctx_get` | `ctx get <id>` |
| `ctx_list` | `ctx list --type <type> --status <status>` |
| `ctx_query` | `ctx query "<text>"` |
| `ctx_link` | `ctx link <from> <to> --rel <rel>` |
| ... | (22 total — all map to ctx subcommands) |

### 6.2 pinecone (npx Node.js → Rust HTTP client)

**Current:** `npx -y @pinecone-database/mcp` → HTTP requests to Pinecone API

**New:** `dom_mcp` → `reqwest` HTTP requests to Pinecone API

**Effort:** Low. Read the npm package source to find the API endpoints, reimplement as Rust HTTP client calls.

### 6.3 taskplanner (Node.js → Rust native)

**Current:** `node mcp-server.js` → reads/writes `.tasks/*.md` files

**New:** `dom_mcp` → native Rust markdown file CRUD

**Effort:** Medium. Need to reimplement the markdown parsing and task state machine (BACKLOG → NEXT → IN_PROGRESS → DONE → REJECTED).

### 6.4 filesystem (Go → Rust native OR keep Go)

**Current:** `/Users/wws/go/bin/mcp-filesystem-server` (Go binary — already native!)

**Decision:** Two options:
1. **Keep the Go binary** — it's already native, no need to rewrite. Just leave it as a separate MCP server.
2. **Port to Rust** — for true single-binary unification. `std::fs` + `walkdir` crate.

**Recommendation:** Port to Rust for unification, but this is **lowest priority** since Go is already acceptable (no Node, no RAM bloat).

### 6.5 msearch (Python → Rust subprocess wrapper)

**Current:** `python3 msearch_mcp_server.py` → spawns C `msearch` binary → parses output

**New:** `dom_mcp` → spawns C `msearch` binary → parses output

**Effort:** Low. Same as contextram — just a subprocess wrapper.

---

## 7. Relationship to DomSystem

Dom_Mcp and DomSystem are separate but complementary:

| System | Domain | What It Controls |
|--------|--------|-----------------|
| **DomSystem** | Service lifecycle | MySQL, Neo4j, Qdrant, daemons — start/stop/acquire/release |
| **Dom_Mcp** | Tool protocol | MCP tools — msearch, contextram, filesystem, etc. |

**Dom_Mcp uses DomSystem:**
- If `msearch` needs MySQL, Dom_Mcp calls `DomSystem.acquire("mysql")` before querying
- If `msearch` needs Qdrant, Dom_Mcp calls `DomSystem.acquire("qdrant")`
- When the tool is done, Dom_Mcp calls `DomSystem.release("mysql")`

This means **MCP tools benefit from service modes and adaptive timeout**. If `msearch` is doing a batch search, it can set MySQL to `batch` mode.

**Integration method:** Dom_Mcp calls DomSystem via subprocess:
```rust
// Rust code in dom_mcp
fn acquire_service(name: &str) -> Result<()> {
    std::process::Command::new("python3")
        .arg("/path/to/DomSystem.py")
        .arg("acquire")
        .arg(name)
        .status()?;
}
```

Or via a future C DomSystem FFI (once DomSystem is ported to C).

---

## 8. The Bridge (transition strategy)

If an IDE can't be reconfigured immediately, a thin bridge works:

```
IDE  →  node bridge.js  →  dom_mcp (Rust binary)
         (20-line shim,     (does all the work)
          just pipes
          stdin/stdout)
```

The bridge is temporary — it lets us test Dom_Mcp without changing IDE config. Once verified, the bridge is deleted and the IDE spawns `dom_mcp` directly.

**But the goal is: no bridge, no Node, direct binary spawn.**

---

## 9. VBStyle Rules for Dom_Mcp

New rules to add to `rule_tokens` and `Config_Vbs_Code_Verifiation.py`:

| Rule | Category | Description |
|------|----------|-------------|
| `[DomMcpUnified]` | Architecture | All MCP tools go through Dom_Mcp, no separate Node servers |
| `[DomMcpNative]` | Architecture | MCP servers must be Rust (or Go), never Node.js |
| `[DomMcpSingleBinary]` | Architecture | One binary, all tools — not one process per tool |
| `[DomMcpConfigToml]` | Architecture | MCP config in TOML, not scattered JSON in IDE configs |
| `[DomMcpDomSystemIntegration]` | Architecture | MCP tools use DomSystem acquire/release for backing services |
| `[DomMcpNoNode]` | Forbidden | No Node.js runtime for MCP servers. No npx. No node_modules. No Docker-for-MCP. |
| `[DomMcpNoNpx]` | Forbidden | No `npx -y @modelcontextprotocol/*` — all official MCP servers must be ported to Rust |
| `[DomMcpSubprocessWrapper]` | Method | For tools wrapping existing binaries (msearch, ctx), Dom_Mcp spawns the binary directly — no intermediate language |

---

## 10. Agent Dispatch Plan

This plan is structured so it can be dispatched to sub-agents in parallel:

### Agent 1: Rust scaffold (Phase 2)
- Create `Dom_Mcp/` directory and Cargo project
- Implement MCP protocol handler, tool registry, config reader
- Verify `dom_mcp --version` and `dom_mcp --list-tools` work

### Agent 2: Port `filesystem` + `memory` (Phase 3, priority 1-2)
- Read Go filesystem server source for tool definitions
- Read `@modelcontextprotocol/server-memory` npm package for tool definitions
- Implement `tools/filesystem.rs` and `tools/memory.rs`
- Test both tools

### Agent 3: Port `pinecone` + `msearch` (Phase 3, priority 3-4)
- Read `@pinecone-database/mcp` npm package for API endpoints
- Read `msearch_mcp_server.py` for C binary interface
- Implement `tools/pinecone.rs` and `tools/msearch.rs`
- Test both tools

### Agent 4: Port `contextram` + `sqlite` (Phase 3, priority 5-6)
- Read `ContextRAMSwift/mcp-server/index.js` for all 22 tool definitions
- Read Docker `mcp/sqlite` for SQLite tool definitions
- Implement `tools/contextram.rs` and `tools/sqlite.rs`
- Test both tools

### Agent 5: Port `taskplanner` (Phase 3, priority 7)
- Read `taskplanner-1.5.2.../mcp-server.js` for task CRUD logic
- Implement `tools/taskplanner.rs` with markdown file parsing
- Test all task operations

**Agents 1-5 can run in parallel** after Agent 1 creates the scaffold (Agents 2-5 depend on the Cargo project existing). Total estimated effort: 5 parallel agent tasks.

---

## 11. RAM Impact Estimate

| Configuration | Processes | Total RAM | Startup Time |
|---------------|-----------|-----------|--------------|
| **Current (Cascade)** | 3 Node + 1 Go + 1 Python (Devin) = 5 processes | ~200 MB | 3-8 seconds |
| **After Dom_Mcp (Cascade)** | 1 Rust (dom_mcp) + 1 Python (Devin's msearch, until Devin also cuts over) = 2 processes | ~10 MB | <100ms |
| **After full cutover** | 1 Rust per IDE | ~5 MB per IDE | <100ms |

**RAM savings: ~190 MB. Startup speedup: 30-80x.**
