# Context Awareness, Models, and Adaptive

Source pages (fetched 2026-06-22 from docs.devin.ai):
- /desktop/context-awareness/overview.md, /desktop/context-awareness/windsurf-overview.md
- /desktop/context-awareness/fast-context.md, /desktop/context-awareness/remote-indexing.md
- /desktop/context-awareness/windsurf-ignore.md
- /desktop/models.md, /desktop/adaptive.md

---

## 1. Context Awareness Overview

Devin Desktop's RAG-based context engine indexes your codebase for intelligent suggestions.

### Default Context
- Current file + other open files in IDE.
- Entire local codebase indexed (including unopened files) — relevant snippets retrieved by M-Query retrieval engine.
- Pro users: expanded context lengths, higher indexing limits, higher custom/pinned context limits.
- Teams/Enterprise: can index remote repositories.

### Knowledge Base (Beta, Teams/Enterprise)
Pull Google Docs as shared context for the entire team.
- Only Google Docs supported (no images; charts, tables, formatted text OK).
- Admin connects Google Drive via OAuth → add up to 50 Google Docs.
- Docs do NOT obey individual user access controls — all team members see them.

### Context Pinning Best Practices
- Pin module definitions (class/struct files in other modules).
- Pin internal frameworks/libraries directories with code examples.
- Pin specific interface files (`.proto`, abstract classes, config templates).
- Pin the "lowest common denominator" directory for your current session.
- Pin test files when writing unit tests.
- **Pin only what you need** — too much slows down or negatively impacts model performance.

### Chat-Specific Context
@-mentions, custom guidelines, persistent context, pinned files, inline citations.

---

## 2. Fast Context

Specialized subagent using SWE-grep models for code retrieval up to **20× faster** than traditional agentic search. Activates automatically when Cascade receives a query requiring code search.

### How it works
1. Identifies relevant files and code sections using parallel tool calls.
2. Executes multiple searches simultaneously.
3. Returns targeted results in seconds rather than minutes.

### SWE-grep Models
- **SWE-grep**: high-intelligence variant for complex retrieval.
- **SWE-grep-mini**: ultra-fast, **>2,800 tokens/sec**.
- Both trained with RL for parallel tool calling and efficient codebase navigation.
- Up to **8 parallel tool calls per turn**, max **4 turns**.
- Restricted to cross-platform tools: `grep`, `read`, `glob`.
- Prevents context pollution, conserves Cascade's context budget.

---

## 3. Remote Indexing (Teams/Enterprise)

Index remote repositories from GitHub, GitLab, BitBucket without storing code locally.

- Add repos at `https://windsurf.com/indexing`.
- Choose branch + auto re-index interval.
- Indexing/embedding performed on isolated single-tenant instance.
- After embedding, code deleted (if "Store Snippets" unchecked) — only embeddings persisted.
- Index available to all team members.

---

## 4. Devin Desktop Ignore (`.codeiumignore`)

### Default ignore behavior
- Paths in `.gitignore`
- `node_modules`
- Hidden pathnames (starting with ".")

Ignored files: not indexed, don't count against Max Workspace Size, **cannot be edited by Cascade**.

### Custom ignore
`.codeiumignore` at repo root, same syntax as `.gitignore`.

### Global `.codeiumignore`
`~/.codeium/.codeiumignore` — applies to all workspaces on your system. Works in addition to repo-specific files.

### System Requirements
- Initial indexing: 5-10 min, fraction of CPU, one-time per workspace.
- RAM: ~300MB for 5000-file workspace.
- "Max Workspace Size (File Count)" setting — if workspace not indexed, try increasing. For ~10GB RAM, no higher than 10,000 files.

---

## 5. AI Models

Models from Anthropic, OpenAI, Google, and Cognition. Available models change frequently — latest supported within minutes of launch.

### Model Families (short names always resolve to latest version)
- **Anthropic**: Claude Opus 4.1 (20x), Opus 4.5 (6-8x), Sonnet 4 (3-4x)
- **OpenAI**: GPT-5-Codex (0.5x), GPT-5.1-Codex (0.25-1.5x), GPT-5.2-Codex (1-4x), o3 (1x)
- **Google**: Gemini 2.5 Pro (1x), Gemini 3 Flash (0.75-1.75x)
- **Cognition**: SWE-1.6, SWE-1.5

### Credit Multipliers (examples, Teams/Enterprise tier)
| Model | Credit Multiplier |
|-------|-------------------|
| GPT-4o | 1x |
| GPT-5.1-Codex-Mini Low | 0.25x |
| GPT-5-Codex | 0.5x |
| Claude Sonnet 4 | 3x |
| Claude Sonnet 4 Thinking | 4x |
| Claude Opus 4.5 | 6x |
| Claude Opus 4.5 Thinking | 8x |
| Claude Opus 4.1 | 20x |
| Claude Opus 4.1 Thinking | 20x |

### Reasoning / Thinking Levels
Some models support configurable reasoning levels. Cycle with `Alt+T` (macOS: `Opt+T`).

### Model Selection Tips
- **Complex refactoring**: `opus` or `gpt` for multi-file refactors, architecture changes, deep reasoning.
- **Quick edits / cost-sensitive**: `swe` (fast) for straightforward edits, bug fixes, questions.
- **Recommendation**: try `swe`, `gpt`, and `opus` at minimum to find your preference.
- Enterprise teams can restrict available models via Team Settings.

---

## 6. Adaptive (Intelligent Model Router)

Automatically selects the best AI model for each task. Analyzes your prompt and routes to the model that delivers the best result.

### Selecting
Model picker → **Adaptive** at top of list. Used for all subsequent messages until switched.

### How it works
- Simple tasks → fast, efficient models.
- Complex tasks → more capable models.
- Helps usage allowance last longer by avoiding unnecessary expensive model usage.
- **Adaptive is the best default for most users.**

### Enterprise
Disabled by default. Admin must enable: Settings → Devin Desktop → Models → toggle "Adaptive model router".

### Pricing
- **Self-serve**: fixed per-token rate regardless of underlying model. Input $0.50/M, Output $2.00/M, Cache read $0.10/M (promotional rate through July 7, 2026).
- **Enterprise (ACUs)**: metered in ACUs, scales with tokens and model selected.
- **Enterprise (Legacy Credits)**: variable-token credit pricing based on actual model selected.

### Tips
- Be specific with prompts → better routing, fewer tokens.
- Leverage prompt caching (staying on same model across turns).
- Use Adaptive as default; switch to specific model only when you have a particular reason.
