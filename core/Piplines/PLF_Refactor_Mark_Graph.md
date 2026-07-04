---
description: Mark-Graph-Refactor — mark problem areas in code, build dependency graph from marks, then refactor in dependency order
---

# Refactor Mark-Graph Pipeline

## Purpose

Before rewriting ANY file, mark the problem areas, reason over the marks as a
dependency graph, then execute in safe bottom-up order. Never refactor blind.

## Phase 1: MARK — Leave Stars, Don't Touch Code

For each problem area found in the file, insert a `# * REFACTOR:` comment block
directly above the offending code. The marker contains:

```
# * REFACTOR: <function-name> is <N> lines with <problem>.
#   <detail line 1>
#   <detail line 2>
#   <proposed fix>
```

Rules:
- Do NOT modify any code in this phase. Only add comments.
- One marker per problem, placed directly above the function/section.
- Each marker must state: WHAT is wrong, WHERE it is, HOW to fix it.
- Use `# * REFACTOR:` as the universal marker prefix (grep-able).

Command to place a mark:
```bash
sed -i '<line>i\
# * REFACTOR: <description>' <file>
```

Or use the edit tool to insert comment blocks above functions.

## Phase 2: EXTRACT — Pull All Marks Into A List

```bash
grep -n '# \* REFACTOR' <file>
```

This gives you a numbered list of every problem with its line number.

## Phase 3: GRAPH — Build Dependency Graph From Marks

For each pair of marks, ask:
- Does mark A's fix depend on mark B being done first?
- Does mark A's function call mark B's function?
- Does mark A's fix change the interface mark B relies on?

Build a dependency table:

```
Mark 1: extract_packet (L63) — duplicated bracket loop
    ↓ depends on
Mark 2: classify_content (L224) — duplicated classify logic
    (independent)

Mark 3: classify_packet_context (L291) — duplicated block-end
    ↓ depends on
Mark 4: scan_workspace (L422) — calls classify_packet_context
    ↓ depends on
Mark 5: format_text_report (L611) — formats scan_workspace results
```

## Phase 4: ORDER — Determine Execution Sequence

Bottom-up: dependencies first, dependents last.

| Phase | Mark | What | Lines Saved | Risk |
|-------|------|------|-------------|------|
| 1     | M2   | Merge duplicate functions | ~15 | Low |
| 2     | M1   | Extract shared helper | ~60 | Medium |
| 3     | M3   | Extract internal helpers | ~25 | Low |
| ...   | ...  | ...                  | ...  | ...  |

## Phase 5: EXECUTE — One Phase At A Time

For each phase in order:
1. Make the change (extract helper, merge function, etc.)
2. Remove the `# * REFACTOR:` marker for that phase
3. Run the file — verify it works
4. Compare output to pre-refactor baseline
5. Only proceed to next phase if current phase passes

## Phase 6: VERIFY — All Marks Gone

```bash
grep -c '# \* REFACTOR' <file>
# Expected: 0
```

If any markers remain, those phases are not done. Do not claim completion.

## BCL Representation

The same pipeline as a BCL packet:

```
[@REFACTOR_PIPELINE]
{
    [@MARK]
    {
        ("action";"insert";"marker";"# * REFACTOR:";"target";"<file>")
        ("rule";"do NOT modify code";"phase";1)
    }
    [@EXTRACT]
    {
        ("action";"grep";"pattern";"# * REFACTOR";"target";"<file>")
        ("output";"mark_list")
    }
    [@GRAPH]
    {
        ("action";"build_dependency_graph";"input";"mark_list")
        ("output";"dependency_table")
    }
    [@ORDER]
    {
        ("action";"topological_sort";"input";"dependency_table")
        ("output";"execution_sequence")
    }
    [@EXECUTE]
    {
        ("action";"refactor";"input";"execution_sequence")
        ("rule";"one phase at a time";"verify_after_each";"yes")
        ("rule";"remove marker when done";"verify_all_gone";"yes")
    }
    [@VERIFY]
    {
        ("action";"grep";"pattern";"# * REFACTOR";"expected";0)
    }
}
```

## When To Use This Workflow

- Any file exceeding 500 lines
- Any file with duplicated logic (copy-paste patterns)
- Any file with functions exceeding 50 lines
- Any file mixing multiple responsibilities
- Before any major restructuring

## When NOT To Use

- Single-line fixes
- Adding a new feature to clean code
- Bug fixes (use debugging workflow instead)
