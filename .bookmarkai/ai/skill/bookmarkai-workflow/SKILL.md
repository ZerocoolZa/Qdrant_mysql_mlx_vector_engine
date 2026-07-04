---
name: bookmarkai-workflow
description: "Generate exactly one validated BookmarkAI bookmark candidate import JSON file in .bookmarkai/drop-zone/inbox/ for one user-specified workflow by default. The only final artifact is the promoted .json file; never create Markdown docs, workflow directories, project maps, staged-bookmarks.json, or repository bookmark JSON files. Create multiple groups/files only when the user explicitly asks for multiple workflows or explicitly approves multiple proposed groups."
---

# Stage Bookmarks - Workflow Import

Use this skill when the user names a specific workflow or logic area.

## One-Screen Contract

- Output only a bookmark candidate import list: strict JSON saved first as `.bookmarkai/drop-zone/inbox/<workflow-slug>.tmp`, then promoted to `.json`.
- After validation promotion, the IDE may auto-import the stable `.json` into Staged Bookmarks and move the batch out of the inbox; do not restore or rewrite it.
- One user-named workflow means exactly one `targetGroupName` and one final `.json` file by default.
- Generate exactly one import batch per confirmed workflow group.
- Do not split one workflow by layer, package, UI/backend/test, or architecture area unless the user explicitly approves multiple groups.
- Before confirmation, respond only in chat. Do not write files.
- Do not write `.bookmarkai/staged-bookmarks.json`.
- Never create workflow folders, Markdown notes, analysis reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
- Use only the project-local validator: `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Hard Rules

1. Wait for user confirmation before writing any `.tmp` or `.json` file.
2. Create only `.bookmarkai/drop-zone/inbox/*.tmp` as validator input and only `.bookmarkai/drop-zone/inbox/*.json` as final output.
3. Keep one named workflow as one group by default; propose multiple groups only when explicitly requested or approved.
4. Do not create directories, Markdown files, reports, project maps, staged-bookmarks.json, or repository bookmark JSON files.
5. Do not generate Related Groups, cross-group links, `linkedGroupIds`, relationship metadata, or navigation edges.
6. Do not generate group links.
7. Use only this JSON field hierarchy: root `targetGroupName`, `items`; each item `title`, `filePath`, `line`, `expectedLineText`, `placement`; placement `afterTitle`. Do not put `afterTitle` at the root or item level.
8. Do not generate IDs, colors, order keys, anchors, status, source, confidence, reasons, or links.
9. `.tmp` file content must be strict JSON only: no Markdown fences, comments, prose, or trailing commas.
10. `.tmp` and `.json` import batch files must be UTF-8.

## Language

- Infer bookmark language from the user's latest explicit request.
- If the user explicitly asks for Chinese or English bookmarks, obey that choice.
- Otherwise, use the dominant natural language of the user's request.
- If the bookmark language is ambiguous, stop before the Workflow Bookmark Plan. Ask the user exactly: `请选择书签语言：中文 / English`.
- Once the language is selected or inferred, use that single language for both `targetGroupName` and every item `title`.
- Group names and bookmark titles must use the same chosen language.
- Do not mix Chinese group names with English bookmark titles, or English group names with Chinese bookmark titles.
- Keep code identifiers, file paths, class names, method names, API names, and `expectedLineText` unchanged.
- Include `Bookmark language: 中文` or `Bookmark language: English` in the Workflow Bookmark Plan.

## Outline Numbering

- Treat each import group as an ordered code reading path when the code has a clear sequence.
- Put outline numbering in `title` only; do not add `outlinePath`, parent, child, edge, or mind-map fields.
- Start numbering at `1` inside each `targetGroupName`. Use `2`, `3`, etc. for mainline steps; use `3.1`, `3.2` for branches; use `3.2.1` for sub-branches.
- Keep every title readable after the prefix: `<outline> <bookmark title>`, for example `3.1 Validate cache hit branch`.
- Prefer maximum depth of three numeric levels. Use deeper levels only when the source code has an important nested branch.
- Do not invent branches for flat or tiny groups; simple sequential numbering is enough.
- Keep item order consistent with the outline numbers. If `placement.afterTitle` is needed, reference the full numbered title.

## Phase 1: Workflow Scan

Read existing bookmarks from the current BookmarkAI branch as the current project navigation map.

Inspect only enough context to understand the requested workflow:

- `.bookmarkai/ai/scripts/analyze-bookmark-context.js --workflow "<requested workflow>"` output, if the script exists
- README, docs index, or project overview if present
- relevant routes, actions, controllers, services, repositories, clients, adapters, models, validators, UI panels, and tests
- targeted `rg` results for the workflow name, domain words, API names, or class names from the request

Do not scan the whole codebase by default. Do not read unrelated files to build a complete project map.

If `.bookmarkai/ai/scripts/analyze-bookmark-context.js` exists, run it with the user's workflow words:

```bash
node .bookmarkai/ai/scripts/analyze-bookmark-context.js --workflow "<requested workflow>"
```

Use its output only as a read-only hint for the current branch bookmark source, existing workflow coverage, likely related groups, moved bookmarks, or stale index state. Do not write `.bookmarkai/cache/bookmark-context-index.json`; the IDE owns that cache. If the analyzer reports missing current branch data, stop and ask the user to run BookmarkAI Initialize Project. If the analyzer is missing or stale, continue with targeted source inspection.

Use existing bookmarks and analyzer results to avoid duplicate candidates. If a current bookmark already covers the same workflow entrypoint or key implementation point, skip it unless the user explicitly asked to refresh stale coverage or the new candidate is materially better.

## Phase 2: Workflow Interpretation

Before planning groups, decide what kind of flow the user asked for. This controls bookmark focus.

Use these categories:

- `技术实现流程`: entrypoints, lifecycle, schedulers, orchestrators, state machines, node execution, extension points, persistence boundaries, rollback/retry/diagnostics, and executable tests.
- `业务查询流程`: API/UI/message entrypoints, request parsing, parameter validation, business rules, permissions, filters, data sources, remote interfaces, caches, fallback, result assembly, error mapping, and business tests.
- `数据处理流程`: input reading, parsing, schema validation, transformation, normalization, aggregation, output, persistence, downstream sending, failure handling, skip policy, idempotency, and batch tests.
- `UI 操作流程`: actions, buttons, menus, shortcuts, UI state reading, service calls, background tasks, EDT transitions, refresh, notifications, error messages, and presentation/helper tests.
- `集成流程`: clients, adapters, gateways, auth, signatures, headers, request construction, response parsing, field mapping, timeouts, retries, throttling, circuit breaking, error-code mapping, mocks, contract tests, and integration tests.
- `混合`: use only when the request explicitly asks for multiple perspectives or cannot be safely interpreted as one category.

If both a technical implementation path and a business request/rule path are plausible, ask exactly: `你更想看技术实现路径，还是业务请求/规则路径？`

If the requested workflow is too broad for one useful group or would exceed the quantity guidance, choose a narrow default scope and state it in the plan, or ask one concise boundary question before planning when no reasonable default exists.

## Phase 3: Workflow Bookmark Plan

Before writing any file, output a concise Workflow Bookmark Plan in chat only and stop for confirmation.

The plan must be at most 60 lines.

Format:

```text
Workflow Bookmark Plan
1. Bookmark language: <中文|English>
2. Requested workflow/process: <user-specified workflow>
3. Workflow interpretation: <技术实现流程|业务查询流程|数据处理流程|UI 操作流程|集成流程|混合>
4. Bookmark focus: <the location types this run will prioritize>
5. Scope boundary: included <scope>; excluded <scope>
6. Proposed group by default:
   - <Exact targetGroupName>: <why this single group exists>; expected <N> bookmarks; sample targets: <file/class/function names>
7. Estimated total bookmarks: <N>
8. Skipped or intentionally low-value areas: <short list>
9. Confirm this workflow bookmark plan? By default I will generate exactly one final bookmark candidate import JSON file for exactly one group, with no Related Groups, cross-group links, Markdown files, staged-bookmarks.json, or bookmarks.json.
```

Group by the user's workflow, not by package names or file tree.

Default to one proposed group. If proposing multiple groups, label section 6 as `Proposed groups, only because the user requested or approved multiple workflows:` and explain why a single workflow group would be wrong.
Propose multiple groups only when the user requested or approved multiple workflows.

Quantity guidance:

- Narrow workflow: 5-8 bookmarks
- Typical workflow: 8-12 bookmarks
- Broad workflow with confirmed split: 4-8 bookmarks per group

## Phase 4: Generate Confirmed JSON Files

After the user confirms the Workflow Bookmark Plan:

1. For the default one confirmed group, create only `.bookmarkai/drop-zone/inbox/<workflow-slug>.tmp`.
2. For multiple confirmed groups only after explicit user approval, create `.bookmarkai/drop-zone/inbox/<sequence>-<workflow-slug>-<group-slug>.tmp`.
3. Validate and promote each batch with the project-local validator:

```bash
node .bookmarkai/ai/scripts/validate-import-batch.js --promote .bookmarkai/drop-zone/inbox/<batch-file>.tmp
```

If `.bookmarkai/ai/scripts/validate-import-batch.js` is missing, stop and tell the user to run the BookmarkAI AI assets repair command. Do not infer global skill paths.

4. If validation exits non-zero, read the `ERROR:` lines, fix the batch, recreate the `.tmp`, and rerun validation. In `--promote` mode the validator removes the invalid `.tmp`; do not leave failed `.tmp` files in the inbox.
5. If validation exits zero but reports `WARN:`, treat warnings as soft quality signals: prefer to remove unsupported fields and rerun when straightforward, but do not block a promoted or otherwise importable batch solely because of warn-only output; report any remaining warnings briefly.
6. Report generated `.json` files and candidate counts, and tell the user the candidates should appear in Staged Bookmarks automatically after the IDE imports them.
7. Your final filesystem output must be only the promoted `.json` import file(s); the IDE may then move them from `.bookmarkai/drop-zone/inbox/` to processing/processed as part of auto import.

This skill is a project-local instruction file. The shared validator lives at `.bookmarkai/ai/scripts/validate-import-batch.js`.

## Candidate Quality

Each bookmark must answer at least one maintenance question:

- Where does this workflow start?
- Where is input parsed or validated?
- Where is the core rule or decision made?
- Where does state change or persist?
- Where does external integration happen?
- Where is the result assembled or displayed?
- Where are failures, fallback, retry, rollback, or diagnostics handled?
- Which tests explain the expected behavior?

Avoid passive data-only classes, trivial wrappers, constants-only files, generated code, unrelated same-name files, and guessed locations that the code does not support.

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
