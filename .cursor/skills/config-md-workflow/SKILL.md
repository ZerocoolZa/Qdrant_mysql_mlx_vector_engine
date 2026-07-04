---
name: config-md-workflow
description: Guides config.md authoring and maintenance for Lua/JSON/Excel linked workflows. Use when the user edits config.md, wants preview/wizard/probe behavior, or needs consistent config document generation.
---
# config.md Workflow

## Scope
- Use for `*.config.md` and markdown docs that contain config blocks, wizard blocks, code blocks, mermaid, and table sections.
- Keep output plain-text first, designer-friendly, and source-of-truth in markdown.

## Core workflow
1. Discover target files
   - Prefer workspace `*.config.md` files.
   - If a source file is provided (`.lua/.json/.jsonc/.xlsx`), find mapped config markdown first.
2. Edit with structure safety
   - Preserve headings and anchor ids.
   - Keep config block key/path stable unless explicitly requested.
   - Keep wizard step order stable unless explicitly requested.
3. Sync-aware changes
   - For config blocks, ensure new default/value types still match linked source format.
   - For code blocks, keep language tag accurate for syntax highlight and save-back.
   - For tables, keep header semantics and row alignment stable.
4. Verify
   - Re-open preview and check: code highlight, table render, probe links, wizard actions.

## Feature checklist
- Config preview + inline editing
- Lua/JSON/JSONC/Excel linked config blocks
- Wizard prompt generation and execution
- Mermaid rendering with probe navigation
- Code block editing and save-back
- Config manager tree view and focus mode

## Minimal syntax quick reference
- Config block (YAML in fenced block):
  ````markdown
  ```lua-config
  file: ./path/to/source.lua
  key: Game.Config.Value
  type: number
  label: Display Name
  ```
  ````
- Mermaid block:
  ````markdown
  ```mermaid
  flowchart TD
    A --> B
  ```
  ````
- Probe link:
  `[Jump](probe://./game.lua#GameConfig.onInit)`

## Syntax authority
- If syntax is unclear, always consult:
  https://github.com/liubai01/IntelligentMarkdown/blob/master/docs/lua-config-reference.md
- Do not invent new config block keys or custom grammar.

## Command hints
- `Open Config Preview`
- `Open Config Window Manager`
- `Toggle Config Focus Mode`
- `Quick Access: config.md`

## Response style
- Give concise change notes.
- Mention touched files and quick validation steps.
