---
trigger: model_decision
description: How to design, author, and maintain Cascade workflows, plus the rest of the Cascade customization surface (rules, AGENTS.md, skills, memories, web/docs search, worktrees, MCP, hooks, context engine, fast context). Read when planning or editing workflows, skills, rules, hooks, or MCP configs.
---

# Cascade Workflows & Features — Authoritative Reference

This file is the single source of truth for *how to design, author, and maintain* Cascade workflows, and the surrounding customization surface (rules, AGENTS.md, skills, memories, web/docs search, worktrees, MCP, hooks, context engine, fast context). Both the user and the AI should consult it before creating or modifying any of these.

Sources (fetched 2026-06-22):
- https://docs.windsurf.com/windsurf/cascade/workflows
- https://docs.devin.ai/desktop/cascade/agents-md
- https://docs.devin.ai/desktop/cascade/skills
- https://docs.devin.ai/desktop/cascade/memories
- https://docs.devin.ai/desktop/cascade/web-search
- https://docs.devin.ai/desktop/cascade/worktrees
- https://docs.devin.ai/desktop/cascade/mcp
- https://docs.devin.ai/desktop/cascade/hooks
- https://docs.devin.ai/desktop/context-awareness/windsurf-overview
- https://docs.devin.ai/desktop/context-awareness/fast-context

---

## 0. Decision tree — which feature to use

| Need | Use |
|------|-----|
| One-shot runbook I trigger myself (deploy, PR review, release) | **Workflow** (`/name`) |
| Multi-step procedure Cascade should pick up automatically, with supporting files (scripts, templates, checklists) | **Skill** (progressive disclosure) |
| Short behavioral constraint ("use bun, not npm", "no print") | **Rule** (`.devin/rules/*.md`) |
| Directory-scoped convention with zero config | **AGENTS.md** in that directory |
| Let Cascade remember one-off facts across sessions | **Memory** (auto-generated, local only) |
| Run a shell command on every file read / write / command exec / prompt | **Hook** (`.windsurf/hooks.json`) |
| Give Cascade access to an external tool (GitHub, Postgres, Slack, custom API) | **MCP server** (`mcp_config.json`) |
| Run Cascade tasks in parallel without touching main workspace | **Worktree** |
| Pull real-time info from the Internet | **Web search** (`@web`) or **Docs search** (`@docs`) |
| Fast codebase retrieval for large repos | **Fast Context** (SWE-grep, automatic) |

**Rule of thumb:** if Cascade should pick it up automatically *and* it needs supporting files → Skill. If it's a short behavioral constraint → Rule. If you always want to trigger it yourself → Workflow.

---

## 1. Workflows

### 1.1 What they are
Workflows are markdown files that define a series of steps Cascade runs in order. They are invoked manually via `/[name-of-workflow]` slash commands.

**Workflows are manual-only.** Cascade will *never* invoke a workflow automatically. If you want automatic pickup, use a Skill instead.

### 1.2 Storage locations and precedence

| Scope | Path | Notes |
|-------|------|-------|
| Workspace | `.windsurf/workflows/*.md` | Committed with the repo. Searched in workspace + subdirs + parent dirs up to git root. |
| Global | `~/.codeium/windsurf/global_workflows/*.md` | Available in every workspace. Not committed. |
| Built-in | Managed by Devin Desktop | e.g. `/plan`. |
| System (Enterprise) | macOS: `/Library/Application Support/Windsurf/workflows/*.md` · Linux/WSL: `/etc/windsurf/workflows/*.md` · Windows: `C:\ProgramData\Windsurf\workflows\` | Deployed by IT, read-only. |

**Precedence (highest first):** System → Workspace → Global → Built-in. A higher-precedence workflow with the same name overrides lower ones.

**Hard limit:** 12,000 characters per workflow file.

### 1.3 How to create a workflow

**Via UI:** Cascade panel → top-right `Customizations` icon → `Workflows` panel → `+ Workflow` (workspace) or `+ Global`.

**Via Cascade:** Ask Cascade to generate one. Works especially well for CLI-driven procedures.

**Manually:** Create `.windsurf/workflows/<name>.md` (or `~/.codeium/windsurf/global_workflows/<name>.md` for global).

### 1.4 Optimal workflow structure

A workflow file is plain markdown. The most reliable structure is:

```markdown
# <workflow-name>

<one-sentence purpose>

## Steps

1. <step 1 — concrete, imperative, with the exact command or action>
2. <step 2 — include the literal bash/CLI command in a fenced block>
3. For EACH <item>, do the following. Address one at a time.
   a. <sub-step>
   b. <sub-step — include the "if you don't understand, ask" guard>
   c. <sub-step>
4. After all items processed, summarize what you did and what needs USER attention.
```

### 1.5 What to put in a workflow

- **Concrete commands**, not abstractions. Put the literal `gh …`, `npm …`, `git …` command in a fenced code block.
- **One-at-a-time guards** when iterating over a list (PR comments, test failures, files). Force Cascade to finish one before starting the next.
- **"If you don't understand, ask"** clauses — prevent Cascade from guessing on ambiguous items.
- **A final summary step** — what was done, what needs the user's attention.
- **Calls to other workflows** when useful: `Call /other-workflow` is supported.

### 1.6 What NOT to put in a workflow

- Generic behavioral rules ("write good code") — those belong in Rules.
- Multi-step procedures with supporting files (templates, scripts, checklists) — those belong in Skills.
- Anything you want Cascade to run automatically — workflows are manual-only.

### 1.7 Canonical example — `/address-pr-comments`

```
1. Check out the PR branch: `gh pr checkout [id]`

2. Get comments on PR
   gh api --paginate repos/[owner]/[repo]/pulls/[id]/comments | jq '.[] | {user, body, path, line, original_line, created_at, in_reply_to_id, pull_request_review_id, commit_id}'

3. For EACH comment, do the following. Remember to address one comment at a time.
   a. Print out: "(index). From [user] on [file]:[lines] — [body]"
   b. Analyze the file and the line range.
   c. If you don't understand the comment, do not make a change. Just ask me for clarification.
   d. If you think you can make the change, make the change BEFORE moving onto the next comment.

4. After all comments are processed, summarize what you did, and which comments need the USER's attention.
```

### 1.8 Common workflow use cases

- `/git-workflows` — commit + PR with standardized titles and descriptions.
- `/dependency-management` — install/update deps from `requirements.txt` / `package.json`.
- `/code-formatting` — run Prettier/Black/ESLint/Flake8 before commit.
- `/run-tests-and-fix` — run tests, fix failures, repeat.
- `/deployment` — deploy to dev/staging/prod with pre-deploy checks and post-deploy verifications.
- `/security-scan` — trigger vulnerability scans on demand or in CI.

### 1.9 When the AI should automatically update a workflow

Workflows are **manual-only** by design, so "automatic update" here means: the AI should propose edits to a workflow file (and ask before applying) when *any* of these are true:

1. **A repeated task has been done manually ≥ 3 times in the same session** and the steps are stable — propose extracting it into a new workflow.
2. **A workflow step fails consistently** because a command, path, or flag changed — propose updating that step with the new command. Verify the new command works first.
3. **A workflow references a file/path/CLI that no longer exists** in the repo (detected during normal work) — flag it and propose the fix.
4. **The user explicitly asks** "update the /x workflow to also do Y" — apply directly.
5. **A new tool replaces an existing one** in the project (e.g. `npm` → `bun`, `flake8` → `ruff`) — propose updating every workflow that calls the old tool.

**Never** auto-apply workflow edits silently. Always show the diff and confirm, because workflows are version-controlled and shared with the team.

**Never** invent a workflow for a one-off task. Workflows are for *repeated* processes.

---

## 2. Rules (`.devin/rules/`)

### 2.1 Storage and limits

| Scope | Location | Limit |
|-------|----------|-------|
| Global | `~/.codeium/windsurf/memories/global_rules.md` | 6,000 chars, single file, always on |
| Workspace | `.devin/rules/*.md` (preferred) or `.windsurf/rules/*.md` (fallback) | 12,000 chars per file |
| AGENTS.md | Any directory in the workspace | — |
| System (Enterprise) | macOS: `/Library/Application Support/Devin/rules/*.md` (preferred) or `/Library/Application Support/Windsurf/rules/*.md` (legacy) · Linux/WSL: `/etc/devin/rules/` or `/etc/windsurf/rules/` · Windows: `C:\ProgramData\Devin\rules\` or `C:\ProgramData\Windsurf\rules\` | — |

`.devin/` is preferred and takes precedence over `.windsurf/`. The legacy single-file `.windsurfrules` at the workspace root is still read.

### 2.2 Activation modes (frontmatter `trigger:`)

| Mode | `trigger:` | How it reaches Cascade | Context cost |
|------|-----------|------------------------|--------------|
| Always On | `always_on` | Full content in system prompt every message | Every message |
| Model Decision | `model_decision` | Only `description` shown; full file loaded on demand | Description always; full content on demand |
| Glob | `glob` | Applied when Cascade reads/edits a file matching `globs:` | Only when matching files are touched |
| Manual | `manual` | Not in system prompt; activated by `@rule-name` | Only when @mentioned |

Global rules file and root-level `AGENTS.md` files don't use frontmatter — they are always on.

### 2.3 Example workspace rule

```markdown
---
trigger: glob
globs: **/*.test.ts
---

All test files must use `describe`/`it` blocks and mock external API calls.
```

### 2.4 Best practices

- Keep rules simple, concise, specific. Long or vague rules confuse Cascade.
- Don't add generic rules ("write good code") — already in training data.
- Use bullet points, numbered lists, markdown — easier to follow than paragraphs.
- XML tags can group related rules: `<coding_guidelines>…</coding_guidelines>`.
- For durable, shareable, version-controlled knowledge → prefer Rules or AGENTS.md over auto-generated Memories.

---

## 3. AGENTS.md (directory-scoped rules, zero config)

### 3.1 How it works
Create `AGENTS.md` or `agents.md` in any directory. Devin Desktop auto-discovers it and feeds it into the same Rules engine as `.devin/rules/`, with the activation mode inferred from location:

- **Workspace root** → treated as **always-on**.
- **Subdirectory** `/foo/` → treated as **glob** rule with pattern `foo/**` — applied only when Cascade reads/edits files inside that directory.

No frontmatter required. Plain markdown.

### 3.2 Discovery
- All `AGENTS.md` files in workspace + subdirs are discovered.
- For git repos, also searches parent dirs up to git root.
- Case insensitive: `AGENTS.md` and `agents.md` both recognized.

### 3.3 When to use AGENTS.md vs Rules

| Feature | AGENTS.md | Rules |
|---------|-----------|-------|
| Location | In project directories | `.devin/rules/` or global |
| Scoping | Automatic, by file location | Manual (glob, always_on, model_decision, manual) |
| Format | Plain markdown | Markdown with frontmatter |
| Best for | Directory-specific conventions | Cross-cutting concerns, complex activation |

### 3.4 Best practices
- Keep each file focused on its directory's purpose.
- Be specific: "Use TypeScript strict mode" beats "write good code".
- Don't repeat global instructions in subdirectory files — they inherit from parents.

---

## 4. Skills (multi-step procedures with supporting files)

### 4.1 What they are
Folders containing a `SKILL.md` plus any supporting files (scripts, templates, checklists, configs). Cascade uses **progressive disclosure**: only `name` and `description` are shown to the model by default. Full `SKILL.md` and supporting files are loaded only when Cascade decides to invoke the skill (or when you `@mention` it). This keeps the context window lean even with many skills.

### 4.2 Storage

| Scope | Location |
|-------|----------|
| Workspace | `.windsurf/skills/<name>/` (committed with repo) |
| Global | `~/.codeium/windsurf/skills/<name>/` (not committed) |
| System (Enterprise) | macOS: `/Library/Application Support/Windsurf/skills/` · Linux/WSL: `/etc/windsurf/skills/` · Windows: `C:\ProgramData\Windsurf\skills\` |

Cross-agent compat: `.agents/skills/` and `~/.agents/skills/` are also discovered. With Claude Code config reading enabled, `.claude/skills/` and `~/.claude/skills/` are scanned too.

### 4.3 SKILL.md format

```markdown
---
name: deploy-to-production
description: Guides the deployment process to production with safety checks
---

## Pre-deployment Checklist
1. Run all tests
2. Check for uncommitted changes
3. Verify environment variables

## Deployment Steps
Follow these steps to deploy safely...

[Reference supporting files in this directory as needed]
```

**Required frontmatter:** `name` (unique, lowercase + hyphens + numbers), `description` (what the skill does and when to use it — this is what Cascade uses to decide automatic invocation).

### 4.4 Supporting files
Place any files alongside `SKILL.md`. They become available to Cascade only when the skill is invoked:

```
.windsurf/skills/deploy-to-production/
├── SKILL.md
├── deployment-checklist.md
├── rollback-procedure.md
└── config-template.yaml
```

### 4.5 Invocation
- **Automatic:** when the user's request matches the skill's `description`. Write descriptions that clearly state what the skill does and when.
- **Manual:** `@skill-name` in the Cascade input.

### 4.6 Skills vs Rules vs Workflows

| | Skills | Rules | Workflows |
|---|-------|-------|-----------|
| Purpose | Multi-step procedures with supporting files | Behavioral guidelines | Prompt templates for repeatable tasks |
| Structure | Folder with `SKILL.md` + resources | Single `.md` with frontmatter | Single `.md` |
| Invocation | Model decides (progressive disclosure) or `@mention` | `always_on` / `glob` / `model_decision` / `manual` | **Manual only** via `/slash-command` |
| In system prompt? | No — only name + description until invoked | Depends on activation mode | No — listed as available commands |
| Best for | Deployments, code review, testing procedures that need scripts/templates | Coding style, project conventions, constraints | One-shot runbooks you trigger explicitly |

---

## 5. Memories

### 5.1 What they are
Context Cascade auto-generates during conversations and stores locally in `~/.codeium/windsurf/memories/`. Retrieved when Cascade believes they're relevant. **Creating and using auto-generated memories does NOT consume credits.**

### 5.2 Key facts
- Workspace-scoped — memories from one workspace are not available in another.
- Local only — not committed to the repo, not shared with the team.
- You can ask Cascade to "create a memory of …" at any time.

### 5.3 When to prefer Rules / AGENTS.md over Memories
For knowledge you want Cascade to **reliably reuse**, write it as a Rule or add it to `AGENTS.md`. Rules are version-controlled, shareable with the team, and give explicit control over activation. Use Memories for one-off facts Cascade should remember within your local machine.

---

## 6. Web and Docs Search

### 6.1 Activation
1. Ask a question that needs the Internet (e.g. "What's new in the latest React?").
2. `@web` — force a web search.
3. `@docs` — query a curated list of docs that Devin Desktop can read with high quality.
4. Paste a URL into the message — Cascade parses it.

### 6.2 Reading pages
Page reads happen **entirely on your device** within your network (VPN-safe). Pages are chunked like a human would read: skim to the section, read the relevant text. Not all pages can be parsed.

### 6.3 Admin control
The **Enable Web Search** admin setting controls whether Cascade can search the open Internet. It does *not* affect Cascade's ability to read specific URLs (which is local).

---

## 7. Worktrees (parallel Cascade tasks)

### 7.1 What they are
Each Cascade conversation can get its own git worktree, so edits/builds/tests don't interfere with the main workspace. Toggle "Worktree" mode in the bottom-right of the Cascade input **at the start of a session** (conversations cannot be moved to a worktree mid-session).

After Cascade makes changes in a worktree, click "merge" to pull them back into the main workspace.

### 7.2 Location
`~/.windsurf/worktrees/<repo_name>/<random-name>`. List with `git worktree list`.

### 7.3 Setup hook — `post_setup_worktree`
Worktrees contain repo files but **not** `.env` files or untracked packages. Use the `post_setup_worktree` hook to copy them in. The hook runs inside the new worktree directory; `$ROOT_WORKSPACE_PATH` points to the original workspace.

**`.windsurf/hooks.json`:**
```json
{
  "hooks": {
    "post_setup_worktree": [
      { "command": "bash $ROOT_WORKSPACE_PATH/hooks/setup_worktree.sh", "show_output": true }
    ]
  }
}
```

**`hooks/setup_worktree.sh`:**
```bash
#!/bin/bash
[ -f "$ROOT_WORKSPACE_PATH/.env" ] && cp "$ROOT_WORKSPACE_PATH/.env" .env
[ -f package.json ] && npm install
exit 0
```

### 7.4 Gotchas and limits
- **Relative paths outside the repo root break** (e.g. `../shared-lib`, symlinked deps, monorepo path-resolved deps). Use `post_setup_worktree` to create symlinks or copy files.
- Max **20 worktrees per workspace**; oldest cleaned up first.
- Deleting a Cascade conversation auto-deletes its worktree.
- Set `git.showWindsurfWorktrees: true` to show worktrees in the SCM panel.

---

## 8. MCP (Model Context Protocol)

### 8.1 What it is
Protocol that lets Cascade call external tools (GitHub, Postgres, Slack, custom APIs, filesystem, Brave search, memory graph, etc.). Three transports: `stdio`, `Streamable HTTP`, `SSE`. OAuth supported for each.

### 8.2 Config file
`~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<token>" }
    }
  }
}
```

Remote HTTP variant uses `serverUrl` (or `url`) and optional `headers`:
```json
{
  "mcpServers": {
    "remote-http-mcp": {
      "serverUrl": "https://<your-server>/mcp",
      "headers": { "API_KEY": "Bearer ${env:AUTH_TOKEN}" }
    }
  }
}
```

### 8.3 Variable interpolation (avoid hardcoding secrets)
Supported in `command`, `args`, `env`, `serverUrl`, `url`, `headers`:
- `${env:VAR_NAME}` — value of env var (empty string if unset).
- `${file:/path/to/file}` — trimmed file contents. Tilde paths (`~/secrets/key.txt`) supported.

### 8.4 Tool limit
**100 total tools** across all MCP servers at any time. Toggle individual tools per server in the MCP settings page.

### 8.5 Common servers
GitHub, Slack, PostgreSQL (read-only by default), Filesystem (path-restricted), Brave Search, Memory (knowledge graph). See `mcp_config.json` examples in the official docs.

### 8.6 Admin controls (Teams/Enterprise)
- Team admins can toggle MCP access and whitelist approved servers.
- Custom MCP registries replace the default marketplace (union of all configured registries).
- Whitelist uses **regex matching**: patterns are auto-anchored (`^(?:pattern)$`); `command` matched exactly, `args` matched element-wise with length match required; `env` is NOT regex-matched (users can set values freely).
- Once any server is whitelisted, **all non-whitelisted servers are blocked**.

### 8.7 Deeplink install
`windsurf://windsurf-mcp-registry?serverName=<server-name>` opens the registry page in Devin Desktop.

### 8.8 Supported capabilities
Tools, resources, and prompts. MCP tool calls invoke arbitrary server code — Devin Desktop does not assume liability for failures.

---

## 9. Hooks

### 9.1 What they are
Shell commands that run automatically at key points in Cascade's workflow. Pre-hooks can **block** an action by exiting with code `2`. Post-hooks cannot block (the action already happened).

### 9.2 Configuration locations (merged in order: system → user → workspace)

| Level | Path |
|-------|------|
| System (Enterprise) | macOS: `/Library/Application Support/Windsurf/hooks.json` · Linux/WSL: `/etc/windsurf/hooks.json` · Windows: `C:\ProgramData\Windsurf\hooks.json` |
| User (Devin Desktop IDE) | `~/.codeium/windsurf/hooks.json` |
| User (JetBrains plugin) | `~/.codeium/hooks.json` |
| Workspace | `.windsurf/hooks.json` in workspace root |

### 9.3 Per-hook options

| Parameter | Type | Description |
|-----------|------|-------------|
| `command` | string | macOS/Linux command (run via `bash -c`). At least one of `command`/`powershell` required. |
| `powershell` | string | Windows command (run via `powershell -Command`). If omitted on Windows, `command` is used as fallback. |
| `show_output` | boolean | Show stdout/stderr in Cascade UI (debugging). |
| `working_directory` | string | Optional. Defaults to workspace root (or current repo root in multi-repo). Absolute paths supported. `~` not supported. |

### 9.4 The 12 hook events

| Event | When | Can block? | Key `tool_info` fields |
|-------|------|-----------|------------------------|
| `pre_read_code` | Before reading a code file | Yes (exit 2) | `file_path` (may be a directory) |
| `post_read_code` | After successful read | No | `file_path` |
| `pre_write_code` | Before write/modify | Yes (exit 2) | `file_path`, `edits[]` (`old_string`, `new_string`) |
| `post_write_code` | After write/modify | No | `file_path`, `edits[]` |
| `pre_run_command` | Before terminal command | Yes (exit 2) | `command_line`, `cwd` |
| `post_run_command` | After terminal command | No | `command_line`, `cwd` |
| `pre_mcp_tool_use` | Before MCP tool call | Yes (exit 2) | `mcp_server_name`, `mcp_tool_name`, `mcp_tool_arguments` |
| `post_mcp_tool_use` | After MCP tool call | No | `mcp_server_name`, `mcp_tool_name`, `mcp_tool_arguments`, `mcp_result` |
| `pre_user_prompt` | Before processing user prompt text | Yes (exit 2) | `user_prompt` (`show_output` does not apply) |
| `post_cascade_response` | Async, after Cascade responds (since last user input) | No | `response` (markdown summary incl. tool actions and rules triggered) (`show_output` does not apply) |
| `post_cascade_response_with_transcript` | Async, after response; writes full transcript to JSONL | No | `transcript_path` → `~/.windsurf/transcripts/{trajectory_id}.jsonl` (`show_output` does not apply) |
| `post_setup_worktree` | After a new worktree is created; runs inside the worktree dir | No | `worktree_path`, `root_workspace_path`; env `$ROOT_WORKSPACE_PATH` |

### 9.5 Common input fields (all hooks)
`agent_action_name`, `trajectory_id`, `execution_id`, `timestamp`, `model_name`, `tool_info`.

### 9.6 Exit codes

| Code | Meaning | Effect |
|------|---------|--------|
| `0` | Success | Action proceeds normally |
| `2` | Blocking error | Cascade sees stderr; **pre-hooks block the action** |
| any other | Error | Action proceeds normally |

### 9.7 Transcript files
`~/.windsurf/transcripts/{trajectory_id}.jsonl`, `0600` perms, max 100 files (oldest pruned). Each line is a JSON object with `type`, `status`, and step-specific data. Structure may change between versions — build consumers to be resilient. **Contains sensitive data** (file contents, command outputs, conversation history) — handle per org security policy.

### 9.8 Canonical patterns
- **Logging all actions:** register `post_read_code`, `post_write_code`, `post_run_command`, `post_mcp_tool_use`, `post_cascade_response` → script that appends JSON to a log file.
- **Restricting file access:** `pre_read_code` script that exits 2 if `file_path` doesn't start with the allowed prefix.
- **Blocking dangerous commands:** `pre_run_command` script that exits 2 if `command_line` contains `rm -rf`, `sudo rm`, `format`, `del /f`, etc.

---

## 10. Context engine (RAG) and Fast Context

### 10.1 Default context
- Current file + other open files in the IDE.
- Entire local codebase indexed; relevant snippets retrieved by Devin Desktop's RAG engine (uses M-Query techniques).
- Pro users: expanded context lengths, higher indexing limits, higher custom/pinned context limits.
- Teams/Enterprise: can index remote repositories.

### 10.2 Fast Context
Specialized subagent using `SWE-grep` and `SWE-grep-mini` models for code retrieval up to **20× faster** than traditional agentic search. Activates automatically when Cascade receives a query that requires code search.

- Up to **8 parallel tool calls per turn**, max **4 turns**.
- Restricted to cross-platform tools: `grep`, `read`, `glob`.
- `SWE-grep-mini` serves at **>2,800 tokens/sec**.
- Prevents context pollution and conserves Cascade's context budget for the actual task.

### 10.3 Chat-specific context features
`@-mentions`, custom guidelines — see Chat docs.

---

## 11. File-path cheat sheet (this machine)

| Feature | Path |
|---------|------|
| Workspace rules (preferred) | `/Users/wws/Qdrant_mysql_mlx_vector_engine/.devin/rules/*.md` |
| Workspace rules (legacy) | `/Users/wws/Qdrant_mysql_mlx_vector_engine/.windsurf/rules/*.md` |
| Workspace workflows | `/Users/wws/Qdrant_mysql_mlx_vector_engine/.windsurf/workflows/*.md` |
| Workspace skills | `/Users/wws/Qdrant_mysql_mlx_vector_engine/.windsurf/skills/<name>/` |
| Workspace hooks | `/Users/wws/Qdrant_mysql_mlx_vector_engine/.windsurf/hooks.json` |
| AGENTS.md (root = always-on) | `/Users/wws/Qdrant_mysql_mlx_vector_engine/AGENTS.md` |
| Global rules | `~/.codeium/windsurf/memories/global_rules.md` |
| Global workflows | `~/.codeium/windsurf/global_workflows/*.md` |
| Global skills | `~/.codeium/windsurf/skills/<name>/` |
| User hooks (IDE) | `~/.codeium/windsurf/hooks.json` |
| MCP config | `~/.codeium/windsurf/mcp_config.json` |
| Auto memories | `~/.codeium/windsurf/memories/` |
| Worktrees | `~/.windsurf/worktrees/<repo_name>/` |
| Transcripts | `~/.windsurf/transcripts/{trajectory_id}.jsonl` |
| System rules (macOS) | `/Library/Application Support/Devin/rules/*.md` (preferred) or `/Library/Application Support/Windsurf/rules/*.md` (legacy) |
| System workflows (macOS) | `/Library/Application Support/Windsurf/workflows/*.md` |
| System skills (macOS) | `/Library/Application Support/Windsurf/skills/` |
| System hooks (macOS) | `/Library/Application Support/Windsurf/hooks.json` |

---

## 12. AI operating rules for this file

When the AI is working in this workspace and encounters any of the following, it MUST consult this file and follow its guidance:

1. **Creating or editing a workflow** → follow §1.3–§1.7. Use the optimal structure. Never auto-invoke workflows (they are manual-only).
2. **Deciding workflow vs skill vs rule vs AGENTS.md vs memory** → use the §0 decision tree.
3. **Auto-updating a workflow** → only per §1.9. Always show the diff and confirm before applying. Never silently edit a workflow.
4. **Creating a skill** → follow §4.2–§4.5. Write a precise `description` (it drives automatic invocation). Bundle supporting files in the skill folder.
5. **Creating a rule** → follow §2.1–§2.4. Pick the right `trigger:`. Stay under 12,000 chars (workspace) or 6,000 chars (global).
6. **Creating an AGENTS.md** → follow §3. Put it in the directory it scopes to. Root = always-on, subdir = auto-glob.
7. **Setting up a worktree** → follow §7. Configure `post_setup_worktree` if the project uses `.env` files, relative-path deps, or symlinked packages.
8. **Adding an MCP server** → follow §8. Use `${env:…}` / `${file:…}` interpolation, never hardcode secrets. Stay under the 100-tool limit.
9. **Writing a hook** → follow §9. Use exit code 2 to block in pre-hooks. Use `show_output: true` for debugging. Be careful with `post_cascade_response_with_transcript` (sensitive data).
10. **Needing real-time info** → use `@web` / `@docs` or paste a URL (§6).
11. **Searching a large codebase** → Fast Context (§10.2) handles this automatically; don't fight it with manual `grep` loops unless targeted.
