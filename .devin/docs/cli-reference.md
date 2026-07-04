# Devin CLI Reference

Source pages (fetched 2026-06-22 from docs.devin.ai):
- /cli/index.md, /cli/essential-commands.md, /cli/models.md
- /cli/extensibility/index.md, /cli/extensibility/rules.md, /cli/extensibility/configuration.md
- /cli/extensibility/hooks/overview.md, /cli/extensibility/hooks/lifecycle-hooks.md
- /cli/extensibility/mcp/overview.md, /cli/extensibility/mcp/configuration.md
- /cli/extensibility/skills/overview.md, /cli/extensibility/skills/creating-skills.md
- /cli/subagents.md, /cli/reference/permissions.md, /cli/handoff.md

---

## 1. Quickstart

```bash
devin                            # Start interactive REPL (no prompt)
devin -- your prompt here        # Start REPL with initial prompt
devin -p "prompt"                # Single-turn, print to stdout, exit
```

- Use `--` before prompt so it's interpreted as a prompt, not a subcommand.
- Type `@` in prompt input for autocomplete of local files/directories.
- Paste images with **Ctrl+V**. Navigate with Left/Right, remove with Backspace.
- `-p` mode is great for scripts and automations.

---

## 2. Essential Commands

### Modes (permission modes)

| Mode | Behavior | Command |
|------|----------|---------|
| **Normal** (default) | Auto-approves read-only tools, asks for write/exec | `/normal` |
| **Accept Edits** | Auto-approves file edits in workspace, prompts for shell commands | `/accept-edits` |
| **Bypass** | Auto-approves ALL tool calls (aliases: `/yolo`, `/dangerous`) | `/bypass` |
| **Autonomous** | Accept Edits + any shell command in OS-level sandbox | `devin --sandbox --permission-mode autonomous` |

**Bypass vs Autonomous:**
- Bypass: no sandbox, unrestricted. Pick when you trust the agent with your whole machine.
- Autonomous: requires `--sandbox`, OS-enforced limits on files and network. Pick for unattended execution with isolation.

**Agent modes:** Normal, Plan (`/plan`), Ask (`/ask <question>`).

### Session Management

| Command | Description |
|---------|-------------|
| `devin -c` / `--continue` | Continue most recent session in current directory |
| `devin -r` / `--resume` | Pick from recent sessions |
| `devin -r <id>` | Resume specific session by ID |
| `/resume` | Interactive session picker |
| `/ls` | List recent sessions in current directory |
| `/ls --all` | List all sessions across all directories |
| `/rm-session <id>` | Irreversibly delete a session |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | See all available commands |
| `/exit` / `/quit` | Exit |
| `/clear` / `/new` | Clear conversation history |
| `/mode [name]` | Show/switch mode |
| `/model [name]` | Show/switch model |
| `/workspace` | List workspace directories |
| `/add-dir <path>` | Add workspace directory |
| `/loop <prompt>` | Run prompt + auto-review diff in loop (requires clean git state) |
| `/hooks` | List all loaded hooks with IDs, event types, source paths |

---

## 3. Configuration

### Config File Locations

| Level | Path | Shared? |
|-------|------|---------|
| User config | `~/.config/devin/config.json` (Windows: `%APPDATA%\devin\config.json`) | No (personal) |
| Project config | `.devin/config.json` | Yes (committed) |
| Local override | `.devin/config.local.json` | No (gitignored) |

### Precedence (highest first)
1. Organization / Team settings (enterprise, cannot be overridden)
2. Session grants (interactive approvals, in-memory)
3. Project local (`.devin/config.local.json`)
4. Project (`.devin/config.json`)
5. User (`~/.config/devin/config.json`)

### What goes where
- **Project configs**: `permissions`, `mcpServers`, `read_config_from`, `hooks`
- **User configs only**: `agent` (model), `theme_mode`, `unicode_mode`, `show_path`, `sandbox`, display/behavior options

### Importing from other tools
```json
{
  "read_config_from": {
    "cursor": true,
    "windsurf": true,
    "claude": true
  }
}
```
`AGENTS.md` is always read and cannot be disabled.

### `.devin/` directory structure
```
my-project/
├── .devin/
│   ├── config.json          # Project config (MCP, permissions)
│   ├── config.local.json    # Personal overrides (gitignored)
│   ├── hooks.v1.json        # Lifecycle hooks
│   ├── skills/
│   │   └── review/
│   │       └── SKILL.md
│   └── agents/
│       └── reviewer/
│           └── AGENT.md     # Custom subagent profile
├── AGENTS.md                # Project rules
```

Files with `.local.` in the name are automatically gitignored.

---

## 4. Rules & AGENTS.md

### AGENTS.md (recommended for project rules)
- At project root → always-on rules.
- In subdirectories → discovered lazily when agent accesses files in that directory.
- Supported names: `AGENTS.md`, `AGENT.md`, `CLAUDE.md` (all treated identically).

### Global Rules
`~/.config/devin/AGENTS.md` (or `AGENT.md`) — applies to every project.
Also reads `~/.claude/CLAUDE.md` as global rule.

### Rules from other tools
- **Cursor**: `.cursor/rules/*.md` and `.mdc` files. Frontmatter: `alwaysApply`, `globs`, `description`.
- **Windsurf**: `.windsurf/rules/*.md` and `.windsurf/global_rules.md`. Frontmatter `trigger`: `always_on`, `manual`, `model_decision`, `agent`, `glob`.
- **Claude Code**: `.claude/` directory.

### Rule Activation Types
| Type | Behavior |
|------|----------|
| Always-on | Active in every session |
| Glob-activated | Active when agent works with matching files |
| Agent-decided | Agent chooses based on rule's description |
| User-invocable | Only when explicitly triggered by user |

### Best Practices
- **Keep rules concise** — long rules dilute attention. Use Skills instead when possible.
- Be specific: "Use pnpm" > "use the right package manager".
- Include examples.
- Version control them.
- **Recommended pattern**: use a rule to reference skills the model should use in particular scenarios.

---

## 5. Skills (CLI)

Self-contained units of functionality: prompts + tool access + permissions + workflows.

### SKILL.md Format
```yaml
---
name: my-skill
description: What this skill does (shown in completions)
argument-hint: "[file] [options]"
model: sonnet
subagent: true
agent: reviewer
allowed-tools:
  - read
  - grep
  - glob
  - exec
permissions:
  allow:
    - Read(src/**)
  deny:
    - exec
  ask:
    - Write(**)
triggers:
  - user
  - model
---

Your prompt content goes here...
```

### All Frontmatter Fields
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | directory name | Display name |
| `description` | string | none | Shown in completions |
| `argument-hint` | string | none | Hint after command name |
| `model` | string | current model | Override model for this skill |
| `subagent` | boolean | false | Run as subagent (own context window) |
| `agent` | string | none | Run as specific custom subagent profile |
| `allowed-tools` | list | all tools | Restrict which tools skill can use |
| `permissions` | object | inherit | Permission overrides |
| `triggers` | list | `[user, model]` | How skill can be invoked |

### Dynamic Content in Prompt Body
- **Arguments**: `$1`, `$2`, etc. — individual positional args. `$ARGUMENTS` — all args as single string.
- **File inclusion**: `@style-guide.md` — include file contents (relative to config dir).
- **Command output**: `` !`git diff --staged` `` — execute shell command, include output.

### Skill Locations
| Location | Scope | Committed? |
|----------|-------|------------|
| `.agents/skills/<name>/SKILL.md` | Project | Yes |
| `.devin/skills/<name>/SKILL.md` | Project | Yes |
| `.windsurf/skills/<name>/SKILL.md` | Project | Yes |
| `~/.agents/skills/<name>/SKILL.md` | Global | No |
| `~/.config/devin/skills/<name>/SKILL.md` | Global | No |
| `~/.codeium/<channel>/skills/<name>/SKILL.md` | Global | No |

### Subagent Skills
- `subagent: true` → runs as subagent with `subagent_general` profile.
- `agent: <profile>` → runs as specific custom subagent profile.
- Skills running as subagents do NOT spawn nested subagents (run inline instead).
- **Orchestration pattern**: define subagent skills for focused tasks, then a regular skill that calls them. One level deep.

### Third-party Skills
Supports `.agents` skills standards. **Third-party skills can execute arbitrary code — install at your own risk.**

---

## 6. Hooks (CLI)

Claude Code-compatible hook format. Run custom logic at lifecycle events.

### Hook Events
| Event | When | Can block? |
|-------|------|-----------|
| `PreToolUse` | Before tool executes | Yes (exit 2 or `{"decision":"block"}`) |
| `PostToolUse` | After tool finishes | No |
| `PermissionRequest` | When permission decision needed | Yes (return `{"decision":"approve"}`) |
| `UserPromptSubmit` | When user submits message | Can add context |
| `Stop` | When agent wants to stop | Can block to prevent premature stop |
| `PostCompaction` | After context compaction | No |
| `SessionStart` | When session begins | No |
| `SessionEnd` | When session ends | No |

### Hook Format
```json
{
  "PreToolUse": [
    {
      "matcher": "exec",
      "hooks": [
        {
          "type": "command",
          "command": "./scripts/validate.sh",
          "timeout": 10
        }
      ]
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `matcher` | Regex matched against `tool_name`. Empty/omitted = all tools. |
| `type` | `"command"` (shell) or `"prompt"` (LLM prompt) |
| `command` | Shell command (for `command` type) |
| `prompt` | LLM prompt (for `prompt` type) |
| `timeout` | Timeout in seconds (optional) |

### Command Hook I/O
**Input (stdin):** JSON with `hook_event_name`, `tool_name`, `tool_input`.
**Output (stdout, optional):** `{"decision": "approve|block|deny", "reason": "explanation"}`

### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success — continues normally |
| 2 | Block — action denied |
| Other | Error — logged, doesn't block |

### Hook Locations
**Project:** `.devin/hooks.v1.json` (standalone, recommended), `.devin/config.json` (`"hooks"` key), `.devin/config.local.json`, `.claude/settings.json`, `.claude/settings.local.json`
**User (global):** `~/.config/devin/config.json`, `~/.claude.json`, `~/.claude/settings.json`, `~/.claude/settings.local.json`

In `.devin/hooks.v1.json`, hooks object is the entire file. In all other locations, nested under `"hooks"` key.

### Matcher Reference
| Matcher | Matches |
|---------|---------|
| `""` or omitted | All tool names |
| `"exec"` | Tool names containing `exec` |
| `"^exec$"` | Only `exec` tool |
| `"^(exec\|edit)$"` | Only `exec` or `edit` |
| `"^mcp__.*"` | All MCP tools |
| `"^mcp__github__.*"` | All tools from `github` MCP server |
| `"^mcp__github__create_issue$"` | Specific tool from specific server |

Core tool names: `read`, `edit`, `grep`, `glob`, `exec`. MCP tools: `mcp__<server>__<tool>`.

---

## 7. MCP (CLI)

### Adding MCP Servers
```bash
# stdio server
devin mcp add <name> -- <command> [args...]

# HTTP server
devin mcp add <name> <URL>
devin mcp add <name> --url <URL>
```
Transport inferred: URL → HTTP (Streamable HTTP), trailing args → stdio. Falls back to SSE on 4xx errors.

**Scopes:** `-s project` (`.devin/config.json`), `-s user` (`~/.config/devin/config.json`), default = local (`.devin/config.local.json`, gitignored).

### Management Commands
```bash
devin mcp list              # List all servers
devin mcp get <name>        # Show details
devin mcp remove <name>     # Remove server
devin mcp login <name>      # OAuth authenticate
devin mcp logout <name>     # Remove OAuth credentials
```

### Config File Format
**stdio:** `command`, `args`, `env`
**HTTP:** `url`, `transport` (`"http"` or `"sse"`), `headers`, `oauthClientId`, `oauthClientSecret`

### Authentication
OAuth-based servers: `devin mcp login <name>` opens browser. Tokens stored locally, refreshed automatically. Each MCP client maintains its own OAuth session (not shared with Windsurf or Claude Code).

Request specific scopes: `devin mcp login notion --scopes read,write`

### Permission Control
MCP tools appear as `mcp__<server>__<tool>`. Subject to same permission system:
```json
{
  "permissions": {
    "allow": ["mcp__github__*"],
    "deny": ["mcp__github__delete_repo"]
  }
}
```

---

## 8. Subagents

Independent workers spawned by the main agent. Share tools and codebase context but operate in own conversation chain (don't inherit parent's history). **Improve performance AND reduce cost.**

### Modes
- **Foreground**: inline, parent waits. You approve/deny tool calls.
- **Background**: parallel, parent continues. Unapproved tools auto-denied. Notified on completion.

### Built-in Profiles
| Profile | Description | Tool Access |
|---------|-------------|-------------|
| `subagent_explore` | Read-only exploration/research | Read-only + web search; no edits, no URL fetch |
| `subagent_general` | General-purpose including code changes | Full (foreground) or pre-approved only (background) |

### Foreground/Background Switching
- Background a foreground subagent: `Ctrl+B`.
- Foreground a background subagent: open subagent panel, press `f`.

### Cancelling
- Subagent panel: press `x`.
- Foreground: `Ctrl+C` or `Esc`.

### Resuming
Cancelled/failed/completed subagents can be resumed with a new prompt. Always run in foreground (so you can approve previously denied tools).

### Nesting Depth
Default: subagents cannot spawn their own subagents. Custom profiles can opt in via `max-nesting` field in frontmatter.

### Custom Subagents
`AGENT.md` files in `.devin/agents/<name>/` (project) or `~/.config/devin/agents/<name>/` (global).

```yaml
---
name: reviewer
description: Reviews code changes for correctness and style
model: sonnet
allowed-tools:
  - read
  - grep
  - glob
  - exec
permissions:
  allow:
    - Exec(git diff)
  deny:
    - write
    - edit
max-nesting: 3
---

You are a code review subagent...
```

---

## 9. Permissions

### Priority Order
1. **Deny** rules (highest) — blocked immediately.
2. **Ask** rules — always prompted (overrides allow).
3. **Allow** rules — proceeds without prompting.
4. **Default** — prompted for approval.

### Default Behavior by Mode
| Tool type | Normal | Accept Edits | Bypass | Autonomous (sandbox) |
|-----------|--------|-------------|--------|---------------------|
| Read-only | Auto | Auto | Auto | Auto |
| Fetch | Prompt | Prompt | Auto | Auto (sandbox enforces) |
| Bash commands | Prompt | Prompt | Auto | Auto (sandbox enforces) |
| File edits | Prompt | Auto (in workspace) | Auto | Prompt (sandbox can't bound) |

### Scope-Based Permissions
- `Read(glob)`: file read access. e.g. `Read(src/**)`, `Read(~/.config/**)`
- `Write(glob)`: file write access. e.g. `Write(src/**)`, deny `Write(*.lock)`, `Write(.env*)`
- `Exec(prefix)`: shell command execution. e.g. `Exec(git)`, `Exec(npm run)`, deny `Exec(rm)`, `Exec(sudo)`
- `Fetch(pattern)`: HTTP fetch access. e.g. `Fetch(https://api.github.com/*)`, `Fetch(domain:npmjs.org)`

### Tool-Based Permissions
Match by tool name: `read`, `edit`, `grep`, `glob`, `exec`.

### MCP Tool Permissions
- `mcp__server__tool`: specific tool
- `mcp__server__*`: all tools on a server
- `mcp__*`: all MCP tools

### Path Patterns
- `*`: any chars in single path segment
- `**`: any chars across path segments (recursive)
- `~`: home directory expansion

### Autonomous Mode
Only available with `--sandbox`. Shell commands and fetches auto-approve (sandbox enforces limits). Direct file edits via `edit`/`write` still prompt. Granting `Write(...)` scope dynamically expands sandbox.

**Bypass and Autonomous do NOT override org-level permissions.** Admin-enforced deny/ask rules always take priority.

---

## 10. Models (CLI)

Short names always resolve to latest version: `opus`, `sonnet`, `swe`, `codex`, `gemini`.

### Setting Model
```bash
devin --model opus -- refactor this module
/model opus    # during session
```
Config file: `{"agent": {"model": "swe-1-6-fast"}}`

### Reasoning Levels
Configurable for some models. Cycle with `Alt+T` (macOS: `Opt+T`).

### Selection Tips
- Complex refactoring → `opus` or `gpt`
- Quick edits / cost-sensitive → `swe` (fast)
- Try `swe`, `gpt`, and `opus` at minimum
- **Adaptive recommended as default** for most users

---

## 11. Hand off to Cloud Devins

`/handoff` transfers current session to a cloud Devin session with own VM.

```bash
/handoff fix the flaky integration tests in CI
```

### What carries over
- Repo and branch (cloud session clones right repo, checks out your branch)
- Conversation context
- Uncommitted changes (commit or stash anything you don't want sent)

### When to hand off
- VM or server needed (dev server, Docker builds)
- Browser needed (screenshots, OAuth, E2E tests, scraping)
- CI/CD (pipeline debugging, deployments)
- Long-running work (migrations, batch jobs, large refactors)
- Parallel execution (offload to cloud while coding locally)

### From other agents
Not using Devin CLI? Hand off from Claude Code, Codex, Cursor, or any coding agent with the open-source [Devin Handoff](https://github.com/club-cog/devin-handoff) plugin.
