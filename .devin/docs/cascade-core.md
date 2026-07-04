# Cascade Core Features

Source pages (fetched 2026-06-22 from docs.devin.ai):
- /desktop/cascade/cascade.md, /desktop/cascade/modes.md, /desktop/cascade/arena.md
- /desktop/cascade/app-deploys.md, /desktop/terminal.md, /desktop/previews.md
- /desktop/quick-review.md, /desktop/vibe-and-replace.md, /desktop/codemaps.md
- /desktop/deepwiki.md, /desktop/ai-commit-message.md
- /desktop/agent-command-center.md, /desktop/spaces.md, /desktop/advanced.md
- /desktop/devin-local.md

---

## 1. Cascade Overview

Cascade is Devin Desktop's agentic AI assistant. Open with `Cmd/Ctrl+L` or click the Cascade icon top-right. Selected text in editor/terminal is auto-included.

### Code vs Chat mode
- **Code mode**: create/modify/delete files, run terminal commands, search, install deps, multi-step autonomous tasks. Default.
- **Chat mode**: read-only Q&A about codebase or general coding. May propose code you can accept and insert.

### Plans and Todo Lists
A specialized planning agent continuously refines a long-term plan in the background while the selected model takes short-term actions. Cascade creates Todo lists for complex tasks — ask Cascade to update the list to change the plan. May auto-update from new info (e.g. Memories).

### Queued Messages
Type while Cascade is working → message is queued. Press Enter on empty box to send immediately. Delete queued messages before they're sent.

### Tool Calling
Tools: Search, Analyze, Web Search, MCP, terminal. Can detect/install packages. **Max 20 tool calls per prompt.** If trajectory stops, press `continue` (counts as new prompt credit). `Auto-Continue` setting auto-resumes.

### Voice Input
Transcribes speech to text in the Cascade input.

### Named Checkpoints and Reverts
Hover over original prompt → click revert arrow to revert all code changes to that step. **Reverts are irreversible.** Can create named snapshots/checkpoints and revert to them anytime.

### Real-time Awareness
Cascade is aware of your real-time actions (edits, terminal commands, cursor position). Just say "Continue".

### Send Problems to Cascade
Problems panel → `Send to Cascade` button brings errors in as @mention.

### Explain and Fix
Highlight an error → `Explain and Fix` → Cascade fixes it.

### Ignoring Files
`.codeiumignore` at workspace root (gitignore syntax) prevents Cascade from viewing/editing/creating files in those paths. Global: `~/.codeium/.codeiumignore` for all workspaces.

### Linter Integration
Auto-fixes linting errors on generated code (on by default). Disable via `Auto-fix` on the tool call. Lint-fix edits may be free of credit charge.

### Sharing Conversations (Teams/Enterprise)
`...` menu → `Share Conversation`.

### @-mention Previous Conversations
Reference past conversations via @mention. Cascade retrieves summaries, checkpoints, and relevant parts (not full conversation).

---

## 2. Cascade Modes

| Mode | Use case | Tools | Shortcut |
|------|----------|-------|----------|
| **Code** | Complex features, refactoring | All tools enabled | Default |
| **Plan** | Complex features requiring planning | All tools enabled | `⌘+.` / `Ctrl+.` |
| **Ask** | Learning, planning, questions | Search tools only | `⌘+.` / `Ctrl+.` |

### Plan Mode
- Explores codebase, asks clarifying questions (multiple choice UI), presents options.
- Writes a detailed plan to an external Markdown file in `~/.windsurf/plans/`.
- Click "Implement" on the plan file → switches to Code mode automatically.
- Plans are available in @mentions menu for continuing work across sessions.
- To exit: click "Implement", switch to Code mode, or let agent auto-switch.

### Ask Mode
Read-only. Can search and analyze codebase but cannot make changes.

---

## 3. Arena Mode

Run multiple Cascade instances in parallel to compare different models on the same prompt.

- **Single**: one chosen model (default).
- **Arena**: select multiple models → each runs independently in its own worktree.

### Battle Groups (curated random model groups)
- **Frontier**: GPT 5.2, Claude Opus/Sonnet 4.5, Gemini 3 Pro — optimized for intelligence.
- **Fast**: SWE 1.5, Claude Haiku, GPT-5.3-Codex-Spark — optimized for speed.
- **Hybrid**: mix of frontier and fast.
- Model names hidden until you click "X is better" to converge.

### Credit Cost
Same as running each model separately. Battle groups: double the displayed cost (two models run).

### When to Use
Compare code quality across models, explore different approaches, test new models, access frontier models at reduced cost via battle groups.

### Limitations
- Only for git-initialized workspaces.
- Only Git-tracked files copied into worktrees (configure `post_setup_worktree` hook for additional files).

---

## 4. App Deploys (Beta)

Deploy web apps directly from Cascade to Netlify. Public URL: `<subdomain>.windsurf.build`.

- Supported: Next.js, React, Vue, Svelte, static HTML/CSS/JS.
- Creates `windsurf_deployment.yaml` at project root for redeployment.
- Ask Cascade: "Deploy this project to Netlify" or "Update my deployment".
- **Team Deploys**: connect Netlify account for team deployments (admin toggle).
- **Claim**: claim URL gives full control on your personal Netlify account.
- **Rate limits**: Free = 1 deploy/day, 1 unclaimed site. Pro = 10/day, 5 unclaimed.
- **Security**: code uploaded to servers. Only deploy code you're comfortable sharing publicly.

---

## 5. Terminal

### Command in terminal
`Cmd/Ctrl+I` in terminal → natural language → CLI syntax.

### Send terminal selection to Cascade
Highlight stack trace → `Cmd/Ctrl+L` → sends to Cascade as @mention.

### @-mention your terminal
Chat with Cascade about active terminals.

### Auto-Execution Levels

| Level | Description |
|-------|-------------|
| **Disabled** | All commands require manual approval |
| **Allowlist Only** | Only allowlisted commands auto-execute |
| **Auto** | Cascade judges safety; risky commands still prompt. Premium models only. |
| **Turbo** | All commands auto-execute except denylisted ones |

Admin-controlled maximum level (Teams/Enterprise): restricts which levels users can select.

### Team-Wide Command Lists (Teams/Enterprise)
- **Allowlist**: auto-execute without confirmation.
- **Denylist**: always require approval. **Denylist takes precedence over allowlist.**
- Team and user configs merged.

### Allow/Deny lists
- Allow: `windsurf.cascadeCommandsAllowList` setting. e.g. `git` → auto-accepts `git add -A`.
- Deny: `windsurf.cascadeCommandsDenyList` setting. e.g. `rm` → always asks for `rm index.py`.

### Dedicated Terminal (macOS, Wave 13+)
Separate terminal for Cascade, always uses `zsh`. Uses your `.zshrc` config. Legacy terminal available as fallback.

---

## 6. Devin Desktop Previews

Preview web app locally in IDE or browser (optimized for Chrome, Arc, Chromium).

- Opened via Cascade tool call — ask Cascade to preview your site.
- **Send Elements to Cascade**: click "Send element" button → select element → inserted as @mention.
- **In-IDE Preview**: opens as new tab in editor. Can also open in system browser.
- Disable via Devin Settings.

---

## 7. Quick Review (Devin Local only)

Agentic code review on local changes by a separate agent.

### Models
| Model | Description | Pricing |
|-------|-------------|---------|
| SWE-check | Fast, lightweight review | Free for all tiers |
| GPT 5.5 | Latest OpenAI frontier | Token-based |
| Opus 4.7 | Latest Anthropic frontier | Token-based |

### Enterprise
Admin must enable from team settings. Can choose which review models to allow.

---

## 8. Vibe and Replace

AI-powered find and replace. Search for exact text matches → apply natural language prompt to each replacement.

- **Smart mode**: slower model, careful changes.
- **Fast mode**: faster model, quick transformations.

---

## 9. Codemaps

Shareable hierarchical maps of codebase showing execution flow and component relationships.

- Click any node → jump to that file/function.
- Access: Activity Bar or Command Palette → "Focus on Codemaps View".
- Create: select suggested topic, type custom prompt, or generate from Cascade conversation.
- **Share**: send as links viewable in browser. Enterprise: requires opt-in (stored on servers, auth required).
- **Use with Cascade**: @mention a Codemap to include as context.

---

## 10. DeepWiki

AI-powered explanations of code symbols. Hover over function/variable/class → `Cmd+Shift+Click` → detailed explanation.

- Find in Primary Side Bar / Activity Bar.
- Send to Cascade: click `⋮` → `Add to Cascade` (inserts as @mention).

---

## 11. AI Commit Messages

Generate git commit messages with one click. Sparkle (✨) icon next to commit message field.

- Analyzes staged code changes.
- Available to all paid users, no limits.
- Best with small, meaningful commit scopes.
- Privacy: code and messages not stored or used for training.

---

## 12. Agent Command Center (Devin Desktop 2.0)

Kanban-style view of all agents (local + cloud) grouped by status.

- **Local agents**: Cascade sessions.
- **Cloud agents**: Devin sessions on VMs.
- Integrated with editor — jump back to any session for manual edits.
- Work organized into **Spaces**.

---

## 13. Spaces

Group all agent sessions, PRs, files, and context for a task/project into a single view.

- Every session is its own Space by default.
- **Context is shared**: new sessions in a Space inherit project context.
- **Create a Space**: drag session onto another, split pane (`Cmd/Ctrl+\`) + New Session, or `Cmd/Ctrl+T`.
- Switching between Spaces = switching between tasks.

---

## 14. Advanced Configuration

### Cascade Gitignore Access
Toggle in Devin Settings to give Cascade access to .gitignore-matched files (off by default).

### Agent Diff Zones
Inline highlighted regions showing what changed, with accept/reject per hunk. All agents use diff zones by default. Can disable for non-Cascade agents.

### SSH Support
Devin Desktop's own SSH implementation (not Microsoft's). Linux hosts only. SSH agent-forwarding on by default. Don't install Microsoft "Remote - SSH" or open-remote-ssh (conflicts).

### Dev Containers
Supported on Mac/Windows/Linux, local and remote (via SSH). Requires Docker. Commands: Open Folder in Container, Reopen in Container, Attach to Running Container, Reopen Folder Locally.

### WSL (Beta)
Available since v1.1.0. Must have WSL set up. Access via `Open a Remote Window` or `Remote-WSL` in Command Palette.

### Extension Marketplace
Change marketplace URL in Devin Settings → General.

---

## 15. Devin Local Agent

Next-generation agent harness shared with Devin CLI. Meant to eventually replace Cascade.

### Key improvements over Cascade
- **Token efficiency**: up to 30% fewer tokens via better prompt caching.
- **Subagents**: spawn independent workers (foreground/background) with own context windows.
- **Sandboxing**: OS-level filesystem isolation + network filtering (domain allow/deny lists).
- **Quick Review**: dedicated subagent for rapid feedback on changes.

### Switching
Agent selector in bottom-right of Devin Desktop (for new conversations). Enable in Settings → Agents → toggle "Devin Local".

### Permissions model (replaces auto-execution levels)
- **Deny** rules: block entirely (highest priority).
- **Ask** rules: always prompt.
- **Allow** rules: auto-approve.
- Scoped to file reads, writes, command exec, HTTP fetches, MCP tools.
- Configurable at project, user, or org level.

### MCP
- Default: prompts for approval before any MCP tool call.
- Can allow specific tool or entire server, for session or permanently.
- Configured via `.devin/config.json`, `.devin/config.local.json`, `~/.config/devin/config.json`.

### Skills
Same format as Devin CLI skills. **Recommended way to migrate Cascade memories and workflows** (which aren't supported by Devin Local).

### Limitations (not supported by Devin Local)
- Memories (migrate to skills)
- Workflows (migrate to skills)
- Codemaps
- Code Lenses
- Fast Context (uses subagents instead)
- App Deploys
- Conversation Sharing

### Supported
- Rules and AGENTS.md files
- Skills
- Hooks
- Permissions
- Subagents
- Sandboxing
