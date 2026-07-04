---
name: bookmarkai-full
description: "Scan the full codebase, propose a concise bookmark grouping plan for confirmation, then generate validated BookmarkAI bookmark candidate import JSON files in .bookmarkai/drop-zone/inbox/. The only final artifacts are promoted .json files; never create Markdown docs, workflow directories, project maps, staged-bookmarks.json, or repository bookmark JSON files. Use only when the user explicitly asks to initialize, rebuild, or broadly refresh project bookmarks."
---

# Stage Bookmarks — Full Codebase Import

Use this skill for a full codebase scan.

## One-Screen Contract

- Output only bookmark candidate import lists: strict JSON files saved first as `.bookmarkai/drop-zone/inbox/<group-slug>.tmp`, then promoted to `.json`.
- After validation promotion, the IDE may auto-import the stable `.json` into Staged Bookmarks and move the batch out of the inbox; do not restore or rewrite it.
- Create one final `.json` file per confirmed group.
- Wait for user confirmation before writing import batches.
- Generate one import batch per confirmed group.
- Before confirmation, respond only in chat. Do not write files.
- Group by maintenance workflow, not by package names, file tree, or documentation sections.
- Do not write `.bookmarkai/staged-bookmarks.json`.
- Never create architecture folders, Markdown notes, analysis reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
- Use only the project-local validator: `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Hard Rules

1. Wait for user confirmation before writing any `.tmp` or `.json` file.
2. Create only `.bookmarkai/drop-zone/inbox/*.tmp` as validator input and only `.bookmarkai/drop-zone/inbox/*.json` as final output.
3. Create one final `.json` file per confirmed group.
4. Do not create directories, Markdown files, reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
5. Group by maintenance workflow, not by package names or file tree.
6. Use only this JSON field hierarchy: root `targetGroupName`, `items`; each item `title`, `filePath`, `line`, `expectedLineText`, `placement`; placement `afterTitle`. Do not put `afterTitle` at the root or item level.
7. Do not generate IDs, colors, order keys, anchors, status, source, confidence, reasons, links, or related groups.
8. `.tmp` file content must be strict JSON only: no Markdown fences, comments, prose, or trailing commas.
9. `.tmp` and `.json` import batch files must be UTF-8.

## Language

- Infer bookmark language from the user's latest explicit request.
- If the user explicitly asks for Chinese or English bookmarks, obey that choice.
- Otherwise, use the dominant natural language of the user's request.
- If the bookmark language is ambiguous, stop before the Bookmark Group Plan. Ask the user exactly: `请选择书签语言：中文 / English`.
- Once the language is selected or inferred, use that single language for both `targetGroupName` and every item `title`.
- Group names and bookmark titles must use the same chosen language.
- Do not mix Chinese group names with English bookmark titles, or English group names with Chinese bookmark titles.
- Keep code identifiers, file paths, class names, method names, API names, and `expectedLineText` unchanged.
- Include `Bookmark language: 中文` or `Bookmark language: English` in the Bookmark Group Plan.

## Outline Numbering

- Treat each import group as an ordered code reading path when the code has a clear sequence.
- Put outline numbering in `title` only; do not add `outlinePath`, parent, child, edge, or mind-map fields.
- Start numbering at `1` inside each `targetGroupName`. Use `2`, `3`, etc. for mainline steps; use `3.1`, `3.2` for branches; use `3.2.1` for sub-branches.
- Keep every title readable after the prefix: `<outline> <bookmark title>`, for example `3.1 Validate cache hit branch`.
- Prefer maximum depth of three numeric levels. Use deeper levels only when the source code has an important nested branch.
- Do not invent branches for flat or tiny groups; simple sequential numbering is enough.
- Keep item order consistent with the outline numbers. If `placement.afterTitle` is needed, reference the full numbered title.

## Phase 1: Lightweight Project Scan

Read existing bookmarks from the current BookmarkAI branch as the current project navigation map.

Inspect only enough context to create a grouping plan:

- `.bookmarkai/ai/scripts/analyze-bookmark-context.js --mode=summary` output, if the script exists
- README, docs index, or project overview if present
- build/config files and module structure
- manifests, routes, plugin descriptors, package entrypoints, or equivalent runtime entrypoints
- main source tree file names
- test file names
- selected files that look like entrypoints, core services, repositories, UI/API surfaces, workers, schedulers, integrations, diagnostics, or high-value tests

Do not read every file upfront. Code is truth; existing bookmarks are the current navigation result.

If `.bookmarkai/ai/scripts/analyze-bookmark-context.js` exists, run:

```bash
node .bookmarkai/ai/scripts/analyze-bookmark-context.js --mode=summary
```

Use its output only as a read-only hint for the current branch bookmark source, existing bookmark coverage, and index freshness. Do not write `.bookmarkai/cache/bookmark-context-index.json`; the IDE owns that cache. If the analyzer reports missing current branch data, stop and ask the user to run BookmarkAI Initialize Project. If the index is missing or stale, continue from analyzer bookmark states and current source, and mention the stale index only when it changes the plan.

Use existing bookmarks and analyzer results to avoid duplicate candidates. If a current bookmark already covers the same maintenance entrypoint or key implementation point, skip it unless the user explicitly asked to refresh stale coverage or the new candidate is materially better.

## Phase 2: Bookmark Group Plan

Before writing any file, output a concise Bookmark Group Plan in chat only and stop for confirmation.

The plan must be at most 80 lines.

Format:

```text
Bookmark Group Plan
1. Bookmark language: <中文|English>
2. Project shape: <one sentence>
3. Proposed groups:
   - <Group name>: <why this group exists>; expected <N> bookmarks; sample targets: <file/class names>
4. Estimated total bookmarks: <N>
5. Skipped or intentionally low-value areas: <short list>
6. Confirm this grouping plan? I will generate one final bookmark candidate import JSON file per confirmed group, with no Markdown files, staged-bookmarks.json, or bookmarks.json.
```

Group by maintenance workflow, not by package names or file tree.

Candidate dimensions:

- Entry points and lifecycle
- Core domain workflow
- Data ingestion and parsing
- Business rules and processing
- Persistence and state
- UI/API/CLI surfaces
- Background work and scheduling
- External integrations and protocols
- Configuration and environment
- Error handling, diagnostics, and reliability
- Security and permissions
- Tests and executable specifications

Only create groups that fit the project. Usually create 4-8 groups.

Quantity guidance:

- Tiny project: 8-12 bookmarks
- Small project: 12-20 bookmarks
- Medium project: 20-35 bookmarks
- Large project: 35-60 bookmarks
- Monorepo or multi-module project: 8-15 per major module, capped unless the user asks for exhaustive coverage

Per group, usually target 3-8 bookmarks. Merge groups with fewer than 3 useful candidates; split groups with more than 8 strong candidates.

## Phase 3: Generate Confirmed JSON Files

After the user confirms the Bookmark Group Plan:

1. Create one `.bookmarkai/drop-zone/inbox/<group-slug>.tmp` strict JSON file per confirmed group.
2. Validate and promote each batch with the project-local validator:

```bash
node .bookmarkai/ai/scripts/validate-import-batch.js --promote .bookmarkai/drop-zone/inbox/<group-slug>.tmp
```

If `.bookmarkai/ai/scripts/validate-import-batch.js` is missing, stop and tell the user to run the BookmarkAI AI assets repair command. Do not infer global skill paths.

3. If validation exits non-zero, read the `ERROR:` lines, fix the batch, recreate the `.tmp`, and rerun validation. In `--promote` mode the validator removes the invalid `.tmp`; do not leave failed `.tmp` files in the inbox.
4. If validation exits zero but reports `WARN:`, treat warnings as soft quality signals: prefer to remove unsupported fields and rerun when straightforward, but do not block a promoted or otherwise importable batch solely because of warn-only output; report any remaining warnings briefly.
5. Report generated `.json` files and candidate counts, and tell the user the candidates should appear in Staged Bookmarks automatically after the IDE imports them.
6. Your final filesystem output must be only the promoted `.json` import file(s); the IDE may then move them from `.bookmarkai/drop-zone/inbox/` to processing/processed as part of auto import.

This skill is a project-local instruction file. The shared validator lives at `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Candidate Quality

Each bookmark must answer at least one maintenance question:

- Where does this workflow start?
- Where does input enter the system?
- Where is data parsed, validated, transformed, or persisted?
- Where are core decisions made?
- Where does external integration happen?
- Where does UI/API/CLI output get assembled?
- Where is background work scheduled or executed?
- Where are failures handled or diagnosed?
- Which tests explain the expected behavior?

Avoid passive data-only classes, trivial wrappers, constants-only files, generated code, broad package markers, and duplicate call-through points when a deeper implementation boundary is more useful.

Choose stable jump lines: prefer function, method, class, command registration, route/action entry, event handler, core branch decision, persistence boundary, or executable test assertion lines. Avoid blank lines, comment-only lines, broad file headers, pure pass-through wrappers, and unstable generated or formatting-only locations. `expectedLineText` must match the actual target line that was read.

## Standard Import JSON Shape

The generated file must be one JSON object with this standard BookmarkAI import shape.

Required root fields:

- `targetGroupName`: target bookmark group name for this import file.
- `items`: non-empty bookmark candidate array.

Required item fields:

- `title`: bookmark title shown in the target group.
- `filePath`: project-relative path using `/`.
- `line`: 1-based line number.

Optional item fields:

- `expectedLineText`: expected source text at `line`; include it only when the source line was read with the correct project encoding; omit it if encoding is uncertain.
- `placement.afterTitle`: optional ordering hint inside the target group; `afterTitle` is allowed only inside `placement`, and only when the confirmed plan needs relative placement.

```json
{
  "targetGroupName": "Example Workflow",
  "items": [
    {
      "title": "1 Example entrypoint",
      "filePath": "src/example.ts",
      "line": 10,
      "expectedLineText": "export function example() {"
    }
  ]
}
```
