# Pipeline Graph Engine — File Manipulation AI

## Purpose

Generate all possible file manipulation pipelines from 14 primitive operations, store them in a graph database, classify which are useful, execute them against real files, and learn from success/failure to prune bad pipelines over time.

## Architecture

```
14 Primitives → 221,022 Pipelines → SQLite DB → Classify → Execute → Learn → Prune
```

### Layers

| Layer | File | Responsibility |
|---|---|---|
| Generator | `chat_mover/ai1.py` | Generate all pipeline combinations into SQLite |
| Database | `Cascade_toolStack/pipeline_graph.db` | 221K pipelines with learning stats |
| Planner | `Cascade_toolStack/transform_graph_engine.py` | A* graph search over transformations |
| Executor | `Cascade_toolStack/pipeline_executor.py` | Execute pipelines against real files + learn |

## 14 Primitives

| # | Primitive | Input | Output |
|---|---|---|---|
| 1 | move_lines | file, start, end, target | modified_file, modified_target |
| 2 | copy_lines | file, start, end, target | modified_target |
| 3 | append | file, content | modified_file |
| 4 | insert_at_line | file, line, content | modified_file |
| 5 | insert_after_pat | file, pattern, content | modified_file |
| 6 | insert_before_pat | file, pattern, content | modified_file |
| 7 | replace_range | file, start, end, content | modified_file |
| 8 | delete_lines | file, start, end | modified_file |
| 9 | delete_pattern | file, pattern | modified_file |
| 10 | extract_regex | file, pat1, pat2 | extracted_text (content) |
| 11 | duplicate_within | file, start, end, target_line | modified_file |
| 12 | swap_blocks | file, s1, e1, s2, e2 | modified_file |
| 13 | split_file | file, split_line | file1, file2 |
| 14 | merge_files | file1, file2 | merged_file |

## Pipeline Counts

| Depth | Count |
|---|---|
| 2-step | 174 |
| 3-step | 1,992 |
| 4-step | 20,856 |
| 5-step | 198,000 |
| **Total** | **221,022** |

## Categories (useful pipelines)

| Category | Count | Example Chain |
|---|---|---|
| config_extraction | 11 | extract_regex → append → delete_pattern → insert_after_pat |
| reorder | 9 | move_lines → insert_after_pat |
| monolith_split | 9 | split_file → append |
| refactor | 8 | extract_regex → append → delete_pattern → insert |
| dedup_merge | 6 | merge_files → delete_pattern |
| duplicate | 5 | duplicate_within → insert_after_pat |
| cleanup | 4 | delete_pattern → delete_lines |

## Learning Loop

1. **Execute** pipeline against real files
2. **Verify** with py_compile (for .py files)
3. **Record** success_count++ or fail_count++
4. **Prune** pipelines where fail_count >= 3 → useful=0
5. **Lookup** only returns useful=1 pipelines
6. Over time: bad pipelines pruned, good pipelines rise to top

## CLI Usage

```bash
# Stats
python3 pipeline_executor.py stats

# Auto-classify unclassified pipelines
python3 pipeline_executor.py classify

# List useful pipelines by category
python3 pipeline_executor.py list config_extraction

# Intent-based lookup
python3 pipeline_executor.py lookup "move schema"

# Execute a pipeline
python3 pipeline_executor.py execute "append->delete_pattern" \
  --params '{"step1_params":{"file":"target.py","content":"CONST=1"},"step2_params":{"file":"source.py","pattern":"CONST=1\n"}}' \
  source.py=/path/to/source.py target.py=/path/to/target.py

# Prune failures
python3 pipeline_executor.py prune
```

## Database Schema

```sql
CREATE TABLE pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    depth INTEGER NOT NULL,
    step1 TEXT NOT NULL,
    step2 TEXT NOT NULL,
    step3 TEXT,
    step4 TEXT,
    step5 TEXT,
    chain TEXT NOT NULL,
    useful INTEGER DEFAULT NULL,    -- 1=useful, 0=rejected, NULL=unclassified
    category TEXT DEFAULT NULL,     -- config_extraction, monolith_split, etc.
    tested INTEGER DEFAULT 0,       -- has this pipeline been executed?
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    date_created TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## File Locations

- Generator: `chat_mover/ai1.py`
- Database: `Cascade_toolStack/pipeline_graph.db` (44MB)
- Planner: `Cascade_toolStack/transform_graph_engine.py`
- Executor: `Cascade_toolStack/pipeline_executor.py`

## Next Steps

- Add DB primitives (read_schema, diff_schema, apply_migration) for cross-domain pipelines
- Wire into cascade_cli.c as subprocess for intelligent file operations
- Run real-world tests to populate success/fail stats
- Visualize pipeline graph in CodeGPS Garmin
