---
name: bookmarkai-changes
description: "Inspect current uncommitted git changes, propose a concise changed-workflow bookmark plan for confirmation, then generate validated BookmarkAI bookmark candidate import JSON files in .bookmarkai/drop-zone/inbox/. The only final artifacts are promoted .json files; never create Markdown docs, workflow directories, project maps, staged-bookmarks.json, or repository bookmark JSON files. Use only when the user explicitly asks to mark recent changes."
---

# Stage Bookmarks — Changes Import

Use this skill for uncommitted git changes.

## One-Screen Contract

- Output only bookmark candidate import lists: strict JSON files saved first as `.bookmarkai/drop-zone/inbox/<group-slug>-changes.tmp`, then promoted to `.json`.
- After validation promotion, the IDE may auto-import the stable `.json` into Staged Bookmarks and move the batch out of the inbox; do not restore or rewrite it.
- Create one final `.json` file per confirmed changed-workflow group.
- Wait for user confirmation before writing import batches.
- Group by changed workflow, not by file path.
- Before confirmation, respond only in chat. Do not write files.
- Bookmark only changed locations or nearby definitions needed to understand changed symbols.
- Do not write `.bookmarkai/staged-bookmarks.json`.
- Only propose bookmarks for locations directly touched, plus nearby definitions only when needed.
- Never create workflow folders, Markdown notes, analysis reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
- Use only the project-local validator: `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Hard Rules

1. Wait for user confirmation before writing any `.tmp` or `.json` file.
2. Create only `.bookmarkai/drop-zone/inbox/*.tmp` as validator input and only `.bookmarkai/drop-zone/inbox/*.json` as final output.
3. Create one final `.json` file per confirmed changed-workflow group.
4. Do not create directories, Markdown files, reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
5. Only propose bookmarks for touched locations or immediately necessary nearby definitions.
6. Use only this JSON field hierarchy: root `targetGroupName`, `items`; each item `title`, `filePath`, `line`, `expectedLineText`, `placement`; placement `afterTitle`. Do not put `afterTitle` at the root or item level.
7. Do not generate IDs, colors, order keys, anchors, status, source, confidence, reasons, links, or related groups.
8. `.tmp` file content must be strict JSON only: no Markdown fences, comments, prose, or trailing commas.
9. `.tmp` and `.json` import batch files must be UTF-8.

## Language

- Infer bookmark language from the user's latest explicit request.
- If the user explicitly asks for Chinese or English bookmarks, obey that choice.
- Otherwise, use the dominant natural language of the user's request.
- If the bookmark language is ambiguous, stop before the Changes Bookmark Plan. Ask the user exactly: `请选择书签语言：中文 / English`.
- Once the language is selected or inferred, use that single language for both `targetGroupName` and every item `title`.
- Group names and bookmark titles must use the same chosen language.
- Do not mix Chinese group names with English bookmark titles, or English group names with Chinese bookmark titles.
- Keep code identifiers, file paths, class names, method names, API names, and `expectedLineText` unchanged.
- Include `Bookmark language: 中文` or `Bookmark language: English` in the Changes Bookmark Plan.

## Outline Numbering

- Treat each import group as an ordered code reading path when the code has a clear sequence.
- Put outline numbering in `title` only; do not add `outlinePath`, parent, child, edge, or mind-map fields.
- Start numbering at `1` inside each `targetGroupName`. Use `2`, `3`, etc. for mainline steps; use `3.1`, `3.2` for branches; use `3.2.1` for sub-branches.
- Keep every title readable after the prefix: `<outline> <bookmark title>`, for example `3.1 Validate cache hit branch`.
- Prefer maximum depth of three numeric levels. Use deeper levels only when the source code has an important nested branch.
- Do not invent branches for flat or tiny groups; simple sequential numbering is enough.
- Keep item order consistent with the outline numbers. If `placement.afterTitle` is needed, reference the full numbered title.

## Phase 1: Diff Scan

Read existing bookmarks from the current BookmarkAI branch as the current project navigation map.

Inspect:

- `.bookmarkai/ai/scripts/analyze-bookmark-context.js --mode=changes` output, if the script exists
- `git status --short`
- `git diff --stat`
- relevant `git diff <file>` and `git diff --cached <file>` hunks
- nearby definitions only when needed to understand a changed symbol

Use the analyzer output only as a read-only hint for the current branch bookmark source, changed files, affected bookmarks, moved anchors, and index freshness. Do not write `.bookmarkai/cache/bookmark-context-index.json`; the IDE owns that cache. If the analyzer reports missing current branch data, stop and ask the user to run BookmarkAI Initialize Project. If the analyzer is missing or stale, continue with the normal diff scan.

Use existing bookmarks and analyzer results to avoid duplicate candidates. If a current bookmark already covers the same changed entrypoint or key implementation point, skip it unless the user explicitly asked to refresh stale coverage or the changed location materially improves the bookmark.

For `??` untracked files from `git status --short` or analyzer `changedFiles`, read the file directly before proposing bookmarks. Deleted files cannot provide jump targets; list them under Skipped changes unless nearby changed definitions are needed to understand the behavior. Skip pure renames without behavior changes; for renames with behavior changes, use the new project-relative path.

Do not scan unrelated project files. If there are no uncommitted git changes, stop and tell the user there is nothing to bookmark.

## Phase 2: Changes Bookmark Plan

Before writing any file, output a concise Changes Bookmark Plan in chat only and stop for confirmation.

The plan must be at most 50 lines.

Format:

```text
Changes Bookmark Plan
1. Bookmark language: <中文|English>
2. Change shape: <one sentence>
3. Proposed groups:
   - <Group name>: <changed workflow>; expected <N> bookmarks; touched files: <short list>
4. Skipped changes:
   - <file/pattern>: <reason>
5. Estimated total bookmarks: <N>
6. Confirm this changes bookmark plan? I will generate one final bookmark candidate import JSON file per confirmed changed-workflow group, with no Markdown files, staged-bookmarks.json, or bookmarks.json.
```

Group by changed workflow, not by file path.

Typical groups:

- Feature entrypoints
- Changed domain logic
- Persistence/schema changes
- UI/API/CLI changes
- Background jobs/schedulers
- Integration/protocol changes
- Tests and executable specifications

If the diff is small, one group is fine. If unrelated areas changed, create multiple groups.

Quantity guidance:

- Tiny diff: 1-3 bookmarks
- Small diff: 3-6 bookmarks
- Medium diff: 6-12 bookmarks
- Large feature diff: 12-20 bookmarks

## Phase 3: Generate Confirmed JSON Files

After the user confirms the Changes Bookmark Plan:

1. Create one `.bookmarkai/drop-zone/inbox/<group-slug>-changes.tmp` strict JSON file per confirmed group.
2. Validate and promote each batch with the project-local validator:

```bash
node .bookmarkai/ai/scripts/validate-import-batch.js --promote .bookmarkai/drop-zone/inbox/<group-slug>-changes.tmp
```

If `.bookmarkai/ai/scripts/validate-import-batch.js` is missing, stop and tell the user to run the BookmarkAI AI assets repair command. Do not infer global skill paths.

3. If validation exits non-zero, read the `ERROR:` lines, fix the batch, recreate the `.tmp`, and rerun validation. In `--promote` mode the validator removes the invalid `.tmp`; do not leave failed `.tmp` files in the inbox.
4. If validation exits zero but reports `WARN:`, treat warnings as soft quality signals: prefer to remove unsupported fields and rerun when straightforward, but do not block a promoted or otherwise importable batch solely because of warn-only output; report any remaining warnings briefly.
5. Report generated `.json` files, candidate counts, and skipped changed files, and tell the user the candidates should appear in Staged Bookmarks automatically after the IDE imports them.
6. Your final filesystem output must be only the promoted `.json` import file(s); the IDE may then move them from `.bookmarkai/drop-zone/inbox/` to processing/processed as part of auto import.

This skill is a project-local instruction file. The shared validator lives at `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Candidate Quality

Bookmark changed locations that answer:

- Where does the new or changed behavior start?
- Where is the important decision made?
- Where is state changed or persisted?
- Where does UI/API/CLI output change?
- Which test explains the behavior?

Skip formatting-only files, generated files, renames without behavior change, comments-only edits, trivial strings, and resource-only changes unless they define important UI behavior.

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
