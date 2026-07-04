# BookmarkAI AI Assets

AI agents write import batches only. The IDE plugin imports those batches, resolves real source locations, and writes staged bookmark entries into the current BookmarkAI branch data itself.

After a batch is validated and promoted to `.json`, the IDE may automatically claim it, move it through `drop-zone/processing`, and show the candidates in Staged Bookmarks. If the result is not useful, use the IDE's `Undo Last Import` / `Revert Last Import` action instead of restoring the `.json` to the inbox.

## Entry Points

Use the skills under `.bookmarkai/ai/skill/`:

- `bookmarkai-full`: scan the full codebase.
- `bookmarkai-changes`: scan current uncommitted git changes.
- `bookmarkai-workflow`: scan a user-specified workflow or logic area.

## Hard Rules

- Do not write BookmarkAI repository JSON files.
- Do not write `.bookmarkai/staged-bookmarks.json`.
- Do not write `.bookmarkai/key-notes.json` or legacy `.bookmarkai/staged-bookmarks.json`.
- Treat existing bookmarks as the current project navigation map, not as a separate project-map document.
- Output a concise plan and wait for user confirmation before writing import batches.
- If bookmark language is ambiguous, ask exactly `请选择书签语言：中文 / English`; group names and bookmark titles must use the same chosen language.
- When a group represents a code reading path with branches, put outline numbering in `title` only, for example `1 Entry`, `2 Parse input`, `3.1 Cache hit`, `3.2 Cache miss`.
- Write import batches to `.bookmarkai/drop-zone/inbox/*.tmp`.
- Import batch `.tmp` and `.json` files must be UTF-8.
- Include `expectedLineText` only when the source line was read with the correct project encoding; omit it if encoding is uncertain.
- Validate and promote each batch with `.bookmarkai/ai/scripts/validate-import-batch.js`.
- If the validator is missing, stop and tell the user to run the BookmarkAI AI assets repair command.

## Validation

```bash
node .bookmarkai/ai/scripts/validate-import-batch.js --promote .bookmarkai/drop-zone/inbox/<batch-file>.tmp
```

On success, the validator renames `.tmp` to `.json`. On failure, it exits non-zero, prints `ERROR:` and `Next:` guidance, and removes the invalid `.tmp` in `--promote` mode. `WARN:` output is a soft quality signal for unsupported fields: prefer removing unsupported fields when straightforward, but do not block an importable batch solely for warn-only output.

Once promotion succeeds, do not write staged bookmark state yourself. Open Staged Bookmarks to review the automatically imported candidates, or use manual import only as a fallback if auto import is disabled.

## Bookmark Context Analysis

The IDE owns `.bookmarkai/cache/bookmark-context-index.json`. Skills may read it, but must not treat it as the source of truth or write it directly.

Use the read-only analyzer when it exists:

```bash
node .bookmarkai/ai/scripts/analyze-bookmark-context.js --mode=summary
node .bookmarkai/ai/scripts/analyze-bookmark-context.js --mode=changes
node .bookmarkai/ai/scripts/analyze-bookmark-context.js --workflow "<workflow name>"
```

The analyzer reports the current branch bookmark source, index freshness, changed files, affected bookmarks, and workflow matches. If it reports missing current branch data, ask the user to run BookmarkAI Initialize Project. If the index is missing or stale, continue conservatively from analyzer bookmark states and current source, or ask the user to run the IDE rebuild command.

## Import Batch Shape

```json
{
  "targetGroupName": "Architecture",
  "items": [
    {
      "title": "1 Repository boundary",
      "filePath": "src/data/repositoryStore.ts",
      "line": 20,
      "expectedLineText": "static readonly sidecarDirectoryName = '.bookmarkai';"
    }
  ]
}
```

Allowed field hierarchy: root `targetGroupName`, `items`; each item `title`, `filePath`, `line`, `expectedLineText`, `placement`; placement `afterTitle`.
