# Core VBStyle Class Registry

> **Generated**: 2026-06-26T16:44:49 by core_class_extractor.py
> **Sources**: (1) SQLite v20_hybrid_best.db (2) vb_shared.code_classes (3) vb_shared.code_registry (4) vb_shared.designrationale (5) vb_shared.learned_rules (6) vb_code_test.vb_classes+vb_methods (7) on-disk VBSTYLE_*.py (8) MD files
> **Location**: `/Core/`

---

## Source Summary

| Source | Entries Found |
|--------|--------------|
| SQLite v20_hybrid_best.db | 41 |
| vb_shared.code_classes | 49 |
| vb_shared.code_registry | 17 |
| vb_code_test.vb_classes | 103 |
| on-disk VBSTYLE_*.py | 8 |
| MD file references | 56 |
| designrationale | 17 |
| learned_rules | 30 |

---

## Domain Registry

```
Dom_Vector, accessibility, ai, analysis, analytics, arch, archive, asm, audit, automation, bytecode, caching, cli, codec, codegraph, compass, compression, concurrency, config, convert, cryptography, csplit, cu, db, db_inv, db_studio, deployment, documentation, errorhandling, factory, featureflags, fileops, folder, general, governance, graph, graph_engine, graphs, gui, http, index, ingest, ingest_cli, ingest_gui, io, knowledge, localization, log, logging, memory, messaging, network, observability, orchestration, package, parse, process, project_indexer, qa, qt, ratelimiting, reporting, rescue, resilience, runtime, schedule, search, security, serialization, storage, style, system, testing, text, transform, unify, validate, validation, vcs, workflow, wws_index, yaml
```

---

## Boot Spine

```
Bootstrap -> Config -> MemDB -> AST -> Brackets -> ClassDB -> Orchestration -> MemUnit -> Report -> Output
                                                              |
                                                         +----+----+
                                                         | MemBus  |
                                                         |Executor |
                                                         | Runtime |
                                                         +---------+
```

---

## Truth Separation

| Layer | Truth Type | Role |
|-------|-----------|------|
| **AST** | Structural Truth | Validates code structure |
| **Brackets** | Semantic Truth | Extracts contracts, metadata from bracket syntax |
| **ClassDB** | Capability Truth | Maps class names to domains and capabilities |
| **Orchestration** | Dependency Truth | Resolves dependencies, builds execution graph |
| **MemUnit** | Execution Truth | The only place where execution runs |
| **MemDB** | Runtime Truth | In-RAM state substrate, registry, shared state |

---

## Class Entries

### 1 (MemUnit/orchestration)

THE execution authority. Bus + Authority + Dispatcher + Coordinator + Runtime Context + Graph Owner. Only place where execution runs. Dispatches to Executor, routes through MemBus, queues through MemDB. No class executes itself.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_shared.code_classes` `vb_code_test.vb_classes` `disk:VBSTYLE_MemUnit.py` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@MemUnit]{
("class_name";"MemUnit")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_code_test.vb_classes;disk:VBSTYLE_MemUnit.py;md:VBSTYLE_CORE_ARCHITECTURE.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle Core: VBSTYLE_MemUnit.py")
("mysql_description";"VBStyle core class: MemUnit — linked to real implementation: dom_memory (id=56)")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"no")
("run_commands";"connect_core;connect_lib;execute")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"connect_core";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"connect_lib";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 2 (MemDb/storage)

Runtime Truth Substrate. In-RAM SQLite database with command_queue, state_cache, and routing_map tables. NOT just SQLite — includes Runtime Registry, Shared State, Execution Context, Class Registry Cache, Config Cache.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@MemDb]{
("class_name";"MemDb")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle domain: dom_db")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_create_schema;_get_next_command;_queue_command;_update_command_result")
("method_count";"8")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_create_schema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_next_command";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_queue_command";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_update_command_result";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 3 (MemBus/storage)

Message routing bus. Routes communication between classes. Subscribe callbacks to action patterns, publish actions to matching subscribers. Pattern matching with wildcard support.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `disk:VBSTYLE_MemUnit.py` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:vbstyle_core_classes_map.md`

```
[@MemBus]{
("class_name";"MemBus")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;disk:VBSTYLE_MemUnit.py;md:VBSTYLE_CORE_ARCHITECTURE.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle Core: VBSTYLE_MemUnit.py")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"publish;subscribe")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"publish";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"subscribe";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 4 (Executor/orchestration)

Performs execution. Distinct from MemUnit — MemUnit dispatches, Executor performs. Holds core_instances and lib_instances dicts. Finds target by name and calls its Run() method.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `disk:VBSTYLE_MemUnit.py` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@Executor]{
("class_name";"Executor")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;disk:VBSTYLE_MemUnit.py;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle domain: dom_runtime")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_call;_execute")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_call";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_execute";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 5 (Orchestration/orchestration)

Dependency resolver. Builds execution graph, reduces to one active execution target. Applies ordering rules: boot_priority, stage, dependency graph.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@Orchestration]{
("class_name";"Orchestration")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle domain: dom_orchestration")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 6 (AST/analysis)

Structural truth extraction. Syntax gate — validates structure, checks if code is well-formed. Parses Python files using ast module. Validates one-class-per-file rule. No execution role, no selection role.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `disk:VBSTYLE_AST.py` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@AST]{
("class_name";"AST")
("domain";"analysis")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;disk:VBSTYLE_AST.py;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle Core: VBSTYLE_AST.py")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"parse_python_file;validate_one_class_rule")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"parse_python_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_one_class_rule";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 7 (ClassAST/analysis)

Class-level AST analysis. Detects classes in source files, finds classes with Run() methods, parses source code into class structures, extracts parameters from function nodes.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@ClassAST]{
("class_name";"ClassAST")
("domain";"analysis")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_params;detect;find_run_classes;parse_file;parse_source")
("method_count";"9")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_params";"params";"self, func_node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"detect";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"find_run_classes";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"parse_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"parse_source";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 8 (VBAnnotate/storage)

Semantic truth. Safe contract annotation authority. Parses Python safely using AST, injects missing VBSTYLE method annotations. Creates backups, supports dry-run, validates syntax before overwrite.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `disk:VBSTYLE_BRAKETS.py` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:vbstyle_core_classes_map.md`

```
[@VBAnnotate]{
("class_name";"VBAnnotate")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;disk:VBSTYLE_BRAKETS.py;md:VBSTYLE_CORE_ARCHITECTURE.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle Core: VBSTYLE_BRAKETS.py")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"Build_annotation;Inject_annotations;_already_annotated;_create_backup;_detect_indent;_generate_diff;_has_self;_infer_purpose;_parse_ast;_read_file;_safe_write;_validate_source;annotate_file;annotate_folder;generate_report;quick_annotate_file")
("method_count";"20")
("weight";"100")
[@methods]{
("method";"Build_annotation";"params";"self, method_name, indent";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Inject_annotations";"params";"self, source, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_already_annotated";"params";"self, lines, line_index";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_create_backup";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_detect_indent";"params";"self, line";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_generate_diff";"params";"self, original, modified";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_has_self";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_infer_purpose";"params";"self, method_name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_parse_ast";"params";"self, source";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_read_file";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_safe_write";"params";"self, path, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_validate_source";"params";"self, source";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"annotate_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"annotate_folder";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"generate_report";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"quick_annotate_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 9 (VBStyle_AST/?)

Structural truth extraction (alias of AST). Parses Python source, validates one-class-per-domain rule.

**Sources**: `vb_shared.code_classes` `md:vbstyle_core_classes_map.md`

```
[@VBStyle_AST]{
("class_name";"VBStyle_AST")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;md:vbstyle_core_classes_map.md")
("description";"")
("mysql_description";"VBStyle Core: VBSTYLE_AST.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 10 (VBStyle_Brackets/?)

Semantic truth (alias of VBAnnotate). Reads/validates BCL bracket syntax, extracts metadata contracts, builds execution intent.

**Sources**: `vb_shared.code_classes` `md:vbstyle_core_classes_map.md`

```
[@VBStyle_Brackets]{
("class_name";"VBStyle_Brackets")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;md:vbstyle_core_classes_map.md")
("description";"")
("mysql_description";"VBStyle Core: VBSTYLE_BRAKETS.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 11 (Report/reporting)

Structured reporting. Builds reports from multiple layers, attaches data layers (OS, hardware), takes system snapshots, builds semantic clusters from keywords, extracts tags from objects.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@Report]{
("class_name";"Report")
("domain";"reporting")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"attach_layer;build;build_semantic_clusters;extract_tags;ingest;set_layers;snapshot")
("method_count";"9")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"attach_layer";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"build";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"build_semantic_clusters";"params";"self, keywords, file_paths";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"extract_tags";"params";"self, obj";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ingest";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_layers";"params";"self, os_layer, hw_layer";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"snapshot";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 12 (ErrorHandler/storage)

Error capture, classification, recovery, suppression. Captures errors with system state, classifies error types, executes recovery strategies, correlates related errors, tracks frequency and trends, manages suppression rules.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@ErrorHandler]{
("class_name";"ErrorHandler")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"Get_connection;_seed_defaults;capture_error;capture_system_state;check_rate_limit;classify_error;clear_error_log;consume_engine_result;correlate_errors;delete_suppression_rule;execute_recovery;get_error_definitions;get_error_frequency;get_error_log;get_error_stats;get_error_trends;get_human_readable_report;get_recovery_policy;get_snapshots;get_suppression_rules;get_unresolved_count;initialize_schema;register_error_definition;resolve_error;set_suppression_rule")
("method_count";"29")
("weight";"100")
[@methods]{
("method";"Get_connection";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_seed_defaults";"params";"self, cursor";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"capture_error";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"capture_system_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_rate_limit";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"classify_error";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"clear_error_log";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"consume_engine_result";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"correlate_errors";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"delete_suppression_rule";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute_recovery";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_error_definitions";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_error_frequency";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_error_log";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_error_stats";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_error_trends";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_human_readable_report";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_recovery_policy";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_snapshots";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_suppression_rules";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_unresolved_count";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"initialize_schema";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"register_error_definition";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"resolve_error";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_suppression_rule";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 13 (ErrorReport/ingest)

Captures exceptions into know_problems/know_causes tables. Bridges error handling and knowledge base.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@ErrorReport]{
("class_name";"ErrorReport")
("domain";"ingest")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"Captures exceptions into know_problems/know_causes tables")
("init";"self, scanner")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_capture;_clear;_report;report")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, scanner";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_capture";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_clear";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_report";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"report";"params";"self, code, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 14 (Hardware/storage)

Hardware detection and resource limits. Detects CPU, RAM, cores. Calculates optimal thread counts and safe memory limits. Adapts to available hardware.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@Hardware]{
("class_name";"Hardware")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_detect;_get_optimal_threads;_get_safe_memory_limit")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_detect";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_optimal_threads";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_safe_memory_limit";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 15 (OSLayer/orchestration)

OS detection, paths, safe file operations. Detects operating system, provides safe file operations, manages OS-specific paths, takes system snapshots.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:vbstyle_core_classes_map.md`

```
[@OSLayer]{
("class_name";"OSLayer")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:vbstyle_core_classes_map.md")
("description";"OS detection: platform, paths, safe file operations")
("mysql_description";"OS detection: platform, paths, safe file operations")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"snapshot")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"snapshot";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 16 (ClassOS/config)

Foundation OS class for DOM operations. Detects OS capabilities, checks if features are supported, provides OS state for domain modules.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@ClassOS]{
("class_name";"ClassOS")
("domain";"config")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_code_test.vb_classes")
("description";"Foundation OS class for DOM operations")
("mysql_description";"Foundation OS class for DOM operations")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"detect;is_supported")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"detect";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"is_supported";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 17 (ClassIndexer/ingest)

Indexes classes from source files. Extracts classes from Python files, parses class names from source lines, parses VBStyle annotations, indexes by name and role.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@ClassIndexer]{
("class_name";"ClassIndexer")
("domain";"ingest")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"Extract_classes;_parse_class_name;_parse_vbstyle;find_by_name;find_by_role;index")
("method_count";"10")
("weight";"100")
[@methods]{
("method";"Extract_classes";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_parse_class_name";"params";"self, line";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_parse_vbstyle";"params";"self, content, class_name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"find_by_name";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"find_by_role";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"index";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 18 (IndexAuthority/storage)

Inverted index generation and validation. Generates inverted index for a directory, creates file bracket entries, validates index integrity.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md`

```
[@IndexAuthority]{
("class_name";"IndexAuthority")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_index")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"Invert_index_directory;_generate_file_bracket;_now_utc;clear_results;generate_index;get_results;validate")
("method_count";"11")
("weight";"100")
[@methods]{
("method";"Invert_index_directory";"params";"self, target_dir";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_generate_file_bracket";"params";"self, path, target_dir";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_now_utc";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"clear_results";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"generate_index";"params";"self, target_dir";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_results";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 19 (BootstrapLoader/orchestration)

System bootstrap — every model runs this first. Loads system architecture, finds correct table for a token, gets instructions by name, explains architecture to new models.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@BootstrapLoader]{
("class_name";"BootstrapLoader")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"Every model runs this first to understand the system")
("mysql_description";"Every model runs this first to understand the system")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_db;explain_architecture;find_table_for_token;get_instruction;load")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_db";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"explain_architecture";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"find_table_for_token";"params";"self, token_name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_instruction";"params";"self, name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 20 (RuntimeGuard/orchestration)

Runtime limits — max RAM, max time, abort on breach. Checks memory usage, runs processes/threads with guardrails, safe execution with mode selection, tracks crashes.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@RuntimeGuard]{
("class_name";"RuntimeGuard")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_code_test.vb_classes")
("description";"Runtime limits: max RAM, max time, abort on breach")
("mysql_description";"Runtime limits: max RAM, max time, abort on breach")
("init";"self, max_ram_mb, max_time_sec")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"add_solution;check_memory;get_crashes;run_process;run_thread;safe_execute")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, max_ram_mb, max_time_sec";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"add_solution";"params";"self, problem_index, solution_text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_memory";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_crashes";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"run_process";"params";"self, func, args, kwargs";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"run_thread";"params";"self, func, args, kwargs";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"safe_execute";"params";"self, func, mode";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 21 (UnitBase/orchestration)

Base class for all units. Provides Dispatch and Run methods, handles bad actions and bad params, tracks unit name, authority, params.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@UnitBase]{
("class_name";"UnitBase")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, name, authority, params")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Dispatch;_bad_action;_bad_params")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"Dispatch";"params";"self, action, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, action, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, name, authority, params";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_bad_action";"params";"self, message";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_bad_params";"params";"self, message";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 22 (VerificationSuite/orchestration)

System verification. Cold boot tests, circular dependency checks, class discovery, Claude bridge, component registry, duplicate public classes, memory centrality, QA engine, runtime integrity, shard compression, shutdown integrity, VBStyle audit.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@VerificationSuite]{
("class_name";"VerificationSuite")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_Verification.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"log;print_results;run_all;test_circular_dependencies;test_class_discovery;test_claude_bridge;test_cold_boot;test_component_registry;test_duplicate_public_classes;test_memory_centrality;test_qa_engine;test_runtime_integrity;test_shard_compression;test_shutdown_integrity;test_vbstyle_audit")
("method_count";"16")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"log";"params";"self, category, test, result, details";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"print_results";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"run_all";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_circular_dependencies";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_class_discovery";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_claude_bridge";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_cold_boot";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_component_registry";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_duplicate_public_classes";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_memory_centrality";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_qa_engine";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_runtime_integrity";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_shard_compression";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_shutdown_integrity";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"test_vbstyle_audit";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 23 (CoreBootV3/orchestration)

Boot initialization. Default stages, action run, declaration text. Core boot sequence controller.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@CoreBootV3]{
("class_name";"CoreBootV3")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Core_Boot.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_default_stages;action_run;declaration_text")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_default_stages";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"action_run";"params";"self, action_name, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"declaration_text";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 24 (CoreUnit/validation)

Core unit definition. Base unit for the core system.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@CoreUnit]{
("class_name";"CoreUnit")
("domain";"validation")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Core_Unit.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"boot_full;get_core_map;validate_workspace")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"boot_full";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_core_map";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_workspace";"params";"self, workspace_path, required_paths";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 25 (CoreState/general)

Core state management. Centralized state tracking for core modules.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@CoreState]{
("class_name";"CoreState")
("domain";"general")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Core_state.py")
("init";"self, state_path, memory_unit")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"LoadState;cleanup;delete;execute;get;get_all;load;param;save;set;validate")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"LoadState";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, state_path, memory_unit";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"cleanup";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"delete";"params";"self, key";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get";"params";"self, key";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_all";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"param";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"save";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set";"params";"self, key, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 26 (CASOSNode/?)

A single code entity in the registry — method, CU, class, domain, or application. Part of MemUnit core CASOS verification system. Status: discovered -> documented -> understood -> tested -> verified -> approved -> canonical.

**Sources**: `disk:VBSTYLE_MemUnit.py` `md:vbstyle_core_classes_map.md`

```
[@CASOSNode]{
("class_name";"CASOSNode")
("domain";"")
("source";"/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/CORE/VBSTYLE_MemUnit.py")
("sources";"sqlite:v20_hybrid_best.db;disk:VBSTYLE_MemUnit.py;md:vbstyle_core_classes_map.md")
("description";"")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"to_dict")
("method_count";"1")
("weight";"100")
[@methods]{
("method";"to_dict";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 27 (CASOSVerification/?)

CASOS Verification Core — trust-gated promotion pipeline. Lives inside MemUnit. 4 parallel truth streams: Structural, Semantic, Execution, Authority. 6 verification engines: SE -> SSE -> MemUnit -> SpecMatcher -> Authority -> Stability.

**Sources**: `disk:VBSTYLE_MemUnit.py` `md:vbstyle_core_classes_map.md`

```
[@CASOSVerification]{
("class_name";"CASOSVerification")
("domain";"")
("source";"/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/CORE/VBSTYLE_MemUnit.py")
("sources";"sqlite:v20_hybrid_best.db;disk:VBSTYLE_MemUnit.py;md:vbstyle_core_classes_map.md")
("description";"")
("init";"self, mem=None, db=None, param=None")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"process_node;invalidate_node;get_status;promote_node;_validate_structure;_apply_semantics;_bcl_is_valid;_run_execution;_execute;_verify;_matches_spec;_apply_authority;_apply_canonical;_is_stable;_dict_to_node")
("method_count";"16")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem=None, db=None, param=None";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"process_node";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"invalidate_node";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_status";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"promote_node";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_validate_structure";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_apply_semantics";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_bcl_is_valid";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_run_execution";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_execute";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_verify";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_matches_spec";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_apply_authority";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_apply_canonical";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_is_stable";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_dict_to_node";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 28 (GuiBus/?)

GUI event bus — pub/sub scoped to GUI events. Publishes GUI events (click, key, mouse, resize, close), subscribes to GUI event channels.

**Sources**: `vb_shared.code_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiBus]{
("class_name";"GuiBus")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;md:vbstyle_core_classes_map.md")
("description";"")
("mysql_description";"VBStyle core class: GuiBus — linked to real implementation: dom_messaging (id=57)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 29 (GuiDB/?)

GUI truth source. Dynamic GUI loads from GuiDB truth, not hardcoded PyQt code. CAR principle: Critical, Available, Reliable.

**Sources**: `vb_shared.code_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiDB]{
("class_name";"GuiDB")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;md:vbstyle_core_classes_map.md")
("description";"")
("mysql_description";"VBStyle core class: GuiDB — linked to real implementation: dom_qt (id=64)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 30 (GuiDBActions/storage)

GUI database actions. Backup, Check, Deduplicate, Export, ImportSQL, Initialize, SQLiteIntegrity, SaveState, Status, Verify. Bridges GUI operations to SQLite.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@GuiDBActions]{
("class_name";"GuiDBActions")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Backup;Check;Deduplicate;Export;ImportSQL;Initialize;SQLiteIntegrity;SaveState;Status;Verify")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"Backup";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Check";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Deduplicate";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Export";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ImportSQL";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Initialize";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SQLiteIntegrity";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SaveState";"params";"self, code, payload";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Status";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Verify";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 31 (GuiDbWriter/storage)

Writes GUI definitions to database. Creates schema, writes app data, classes, layout law, properties, signals, slots. Summarizes and writes domain packets.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiDbWriter]{
("class_name";"GuiDbWriter")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Lib_GuiDbWriter.py")
("init";"self, db_path")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Ensure_db_dir;_create_schema;_write_app_data;_write_classes;_write_layout_law;_write_properties;_write_signals;_write_slots;summarize;write_domain_packet")
("method_count";"11")
("weight";"100")
[@methods]{
("method";"Ensure_db_dir";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, db_path";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_create_schema";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_app_data";"params";"self, conn, app_packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_classes";"params";"self, conn, classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_layout_law";"params";"self, conn, layout_packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_properties";"params";"self, conn, properties";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_signals";"params";"self, conn, signals";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_write_slots";"params";"self, conn, slots";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"summarize";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"write_domain_packet";"params";"self, domain_packet, layout_packet, app_packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 32 (GuiDomainRegistry/gui)

GUI domain registry. Resets, groups by module/role, groups signals/slots, absorbs domain packets. Organizes GUI classes into domains.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiDomainRegistry]{
("class_name";"GuiDomainRegistry")
("domain";"gui")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Lib_GuiDomainRegistry.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Reset;_group_by_module;_group_by_role;_group_signals;_group_slots;absorb_domain_packet")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"Reset";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_group_by_module";"params";"self, classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_group_by_role";"params";"self, classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_group_signals";"params";"self, signals";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_group_slots";"params";"self, slots";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"absorb_domain_packet";"params";"self, domain_packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 33 (GuiDecisionEngine/gui)

GUI decision engine. Makes rendering and layout decisions for the GUI layer.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiDecisionEngine]{
("class_name";"GuiDecisionEngine")
("domain";"gui")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Lib_GuiDecisionEngine.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Annotate_classes;Determine_role;_summarize_roles;annotate_domain")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"Annotate_classes";"params";"self, classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Determine_role";"params";"self, cls";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_summarize_roles";"params";"self, annotated_classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"annotate_domain";"params";"self, domain_packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 34 (GuiLayoutLaw/gui)

GUI layout constraint laws. Enforces layout rules and constraints for GUI widgets.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:vbstyle_core_classes_map.md`

```
[@GuiLayoutLaw]{
("class_name";"GuiLayoutLaw")
("domain";"gui")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:vbstyle_core_classes_map.md")
("description";"From ChatGPT export: Lib_GuiLayoutLaw.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"get_allowed_regions;get_layout_packet;get_preferred_region;validate_placement")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"get_allowed_regions";"params";"self, role";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_layout_packet";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_preferred_region";"params";"self, role";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_placement";"params";"self, role, region";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 35 (EventBus/orchestration)

Event bus for pub/sub messaging. Routes events between subscribers. VBStyle domain: dom_messaging.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md`

```
[@EventBus]{
("class_name";"EventBus")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_messaging")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_publish;_subscribe")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_publish";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_subscribe";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 36 (CommandBus/storage)

Command bus for command routing. Routes commands to handlers. VBStyle domain: dom_messaging.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md`

```
[@CommandBus]{
("class_name";"CommandBus")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_messaging")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_dispatch;_register")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_dispatch";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_register";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 37 (MessageBus/ingest)

Message bus for process-level messaging. VBStyle domain: dom_process.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md`

```
[@MessageBus]{
("class_name";"MessageBus")
("domain";"ingest")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_process")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_publish;_subscribe")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_publish";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_subscribe";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 38 (DomOrchestration/orchestration)

Full orchestration domain. Task dispatch, queue, schedule, parallel, retry, worker, priority, timeout, sequence, dependency, pause, resume, status.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomOrchestration]{
("class_name";"DomOrchestration")
("domain";"orchestration")
("source";"impl_orchestration.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"Task orchestration, dispatch, and worker management domain.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"dependency;dispatch;parallel;pause;priority;queue;resume;retry;schedule;sequence;status;timeout;worker")
("method_count";"15")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"dependency";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"dispatch";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"parallel";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"pause";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"priority";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"queue";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"resume";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"retry";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"schedule";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"sequence";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"status";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"timeout";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"worker";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 39 (DomErrorHandling/errorhandling)

Full error handling domain. Classify, recover, translate, cause_chain, suppress, wrap, is_retryable, log_once, create_context, get_hierarchy.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomErrorHandling]{
("class_name";"DomErrorHandling")
("domain";"errorhandling")
("source";"impl_error_handling.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"Error handling domain: translation, context, retry classification, cause chains.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_exc;cause_chain;classify;create_context;get_hierarchy;is_retryable;log_once;recover;suppress;translate;wrap")
("method_count";"13")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"_exc";"params";"params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"cause_chain";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"classify";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"create_context";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"get_hierarchy";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"is_retryable";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"log_once";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"recover";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"suppress";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"translate";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"wrap";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 40 (DomMemory/memory)

Full memory domain. In-memory key-value store with TTL, compression, and persistence hooks. Store, recall, cache, compress, persist, restore, expire, forget, invalidate, refresh, clear, keys, size.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomMemory]{
("class_name";"DomMemory")
("domain";"memory")
("source";"impl_memory.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"In-memory key-value store with TTL, compression, and persistence hooks.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_purge_expired;cache;clear;compress;expire;forget;invalidate;keys;load;persist;recall;refresh;restore;size;store")
("method_count";"17")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"_purge_expired";"params";"self";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"cache";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"clear";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"compress";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"expire";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"forget";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"invalidate";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"keys";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"load";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"persist";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"recall";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"refresh";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"restore";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"size";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"store";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 41 (DomGui/gui)

Full GUI domain. Widget tree management, layout, drawing, and event handling. 40+ methods: create_window, add_widget, button, label, render, event_click, etc.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomGui]{
("class_name";"DomGui")
("domain";"gui")
("source";"impl_gui.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"GUI domain: widget tree management, layout, drawing, and event handling using stdlib.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_add_widget;_next_id;add_widget;button;checkbox;close_window;combo;create_window;dialog;draw_line;draw_rect;draw_text;event_click;event_close;event_key;event_mouse;event_resize;hide;label;layout;menu;paint;panel;progress;refresh;remove_widget;render;resize;set_style;set_theme;set_title;slider;splitter;tab;table;text;toolbar;tree;update")
("method_count";"41")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"_add_widget";"params";"self, widget";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"_next_id";"params";"self";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"add_widget";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"button";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"checkbox";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"close_window";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"combo";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"create_window";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"dialog";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"draw_line";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"draw_rect";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"draw_text";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"event_click";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"event_close";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"event_key";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"event_mouse";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"event_resize";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"hide";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"label";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"layout";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"menu";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"paint";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"panel";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"progress";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"refresh";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"remove_widget";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"render";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"resize";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"set_style";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"set_theme";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"set_title";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"slider";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"splitter";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"tab";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"table";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"text";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"toolbar";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"tree";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"update";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 42 (DomIndex/index)

Full index domain. Build, merge, split, create, update, delete, optimize, rebuild, stats, import. Searchable index management.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomIndex]{
("class_name";"DomIndex")
("domain";"index")
("source";"impl_index.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"Index domain: build, merge, split and maintain searchable indices.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"build;create;delete;import_;merge;optimize;rebuild;split;stats;update")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"build";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"create";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"delete";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"import_";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"merge";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"optimize";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"rebuild";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"split";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"stats";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"update";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 43 (DomWwsIndex/wws_index)

Wws inverted index domain. Build, create, update, delete, merge, optimize, rebuild, stats, import. Tokenized inverted index with doc management.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@DomWwsIndex]{
("class_name";"DomWwsIndex")
("domain";"wws_index")
("source";"impl_wws_index.py")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"Inverted index operations: build, create, update, delete, merge, optimize, rebuild, stats and import.")
("init";"self, mem, db, param")
("is_vbstyle";"yes")
("has_run";"yes")
("has_tuple3";"yes")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_add_doc_to_index;_import;_remove_doc_from_index;_tokenize;build;create;delete;merge;optimize;rebuild;stats;update")
("method_count";"14")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"yes";"tuple3";"no")
("method";"_add_doc_to_index";"params";"self, doc_id, tokens";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"_import";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"_remove_doc_from_index";"params";"self, doc_id";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"_tokenize";"params";"self, text";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"build";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"create";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"delete";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"merge";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"optimize";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"rebuild";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"stats";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
("method";"update";"params";"self, params";"dunder";"no";"vbstyle";"yes";"tuple3";"yes")
}
}
```

---

### 44 (WwsIndexAuthority/ingest)

File packet builder. Extracts symbols, dependencies, classifies buckets, detects language, builds file packets, reads fingerprints and excerpts.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md`

```
[@WwsIndexAuthority]{
("class_name";"WwsIndexAuthority")
("domain";"ingest")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_wws_index")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"build_file_packet;classify_bucket;excerpt_line_count;extract_dependencies;extract_symbols;is_likely_binary_prefix;iter_candidate_paths;language_for_path;read_file_fingerprint_and_excerpt;safe_rel_path;utc_now_iso")
("method_count";"15")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"build_file_packet";"params";"self, path_text, root_text, excerpt_limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"classify_bucket";"params";"self, language";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"excerpt_line_count";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"extract_dependencies";"params";"self, language, lines";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"extract_symbols";"params";"self, language, lines";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"is_likely_binary_prefix";"params";"self, data";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"iter_candidate_paths";"params";"self, root_path, extensions";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"language_for_path";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_file_fingerprint_and_excerpt";"params";"self, path_text, limit_bytes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"safe_rel_path";"params";"self, resolved_path, resolved_root";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"utc_now_iso";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 45 (UnifyDomain/storage)

Unify domain. Unifies domain access across the system. VBStyle domain: dom_unify.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:DOM_REGISTRY.md`

```
[@UnifyDomain]{
("class_name";"UnifyDomain")
("domain";"storage")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:DOM_REGISTRY.md")
("description";"VBStyle domain: dom_unify")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 46 (SystemDomain/config)

System domain. System-level domain management. VBStyle domain: dom_system.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes`

```
[@SystemDomain]{
("class_name";"SystemDomain")
("domain";"config")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_system")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 47 (Runtime/orchestration)

Execution, scheduling, dispatching, task and pipeline management. VBStyle domain: dom_runtime.

**Sources**: `sqlite:v20_hybrid_best.db` `vb_code_test.vb_classes` `md:VBSTYLE_CORE_ARCHITECTURE.md` `md:AI_MIGRATION_INSTRUCTION.md` `md:DOM_REGISTRY.md` `md:vbstyle_core_classes_map.md`

```
[@Runtime]{
("class_name";"Runtime")
("domain";"orchestration")
("source";"mysql:vb_code_test")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes;md:VBSTYLE_CORE_ARCHITECTURE.md;md:AI_MIGRATION_INSTRUCTION.md;md:DOM_REGISTRY.md;md:vbstyle_core_classes_map.md")
("description";"VBStyle domain: dom_runtime")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"no")
("run_commands";"clear_info;get_info_item;has_info_item;normalize;remove_info_item;set_info;validate")
("method_count";"9")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"clear_info";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_info_item";"params";"self, name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"has_info_item";"params";"self, name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"normalize";"params";"self, data";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"remove_info_item";"params";"self, name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_info";"params";"self, key, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 48 (AdaptiveMemory/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@AdaptiveMemory]{
("class_name";"AdaptiveMemory")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_decay_old_signals;_get_conn;_get_user_preferences;_ignore;_like;_pin;_rank_modules;_record_signal;_set_session;_unpin;_weighted_score")
("method_count";"15")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_decay_old_signals";"params";"self, days";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_conn";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_user_preferences";"params";"self, domain, limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_ignore";"params";"self, module_id, context";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_like";"params";"self, module_id, context";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_pin";"params";"self, module_id, context";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_rank_modules";"params";"self, base_hits, top_k";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_record_signal";"params";"self, signal";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_set_session";"params";"self, session_id";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_unpin";"params";"self, module_id, context";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_weighted_score";"params";"self, module_id, base_score";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, action, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 49 (AgentCore/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@AgentCore]{
("class_name";"AgentCore")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, memunit, config")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Err;InitAgents;Proof;ResearchTopic;RetrieveKnowledge;Status;StoreKnowledge;TapAgent")
("method_count";"10")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, memunit, config";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Err";"params";"self, msg";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InitAgents";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Proof";"params";"self, ok, result, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResearchTopic";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RetrieveKnowledge";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Status";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"StoreKnowledge";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"TapAgent";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 50 (AppGoldMemUnitRegistrar/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@AppGoldMemUnitRegistrar]{
("class_name";"AppGoldMemUnitRegistrar")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Ok")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 51 (Boot_ClassRankCoreModel/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@Boot_ClassRankCoreModel]{
("class_name";"Boot_ClassRankCoreModel")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CharGrams;CoreMLTrainingRows;CorrectResult;CreateModelSchema;CreateReportSchema;EndRun;ExtractFileClasses;Features;FolderRules;HashFeature;Headers;Imports;LearnApproved;LearnedScore;Normalize;OpenStores;RankClass;RuleScore;ScanFiles;StartRun;StoreResult;TopResults")
("method_count";"24")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CharGrams";"params";"self, text, size";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CoreMLTrainingRows";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CorrectResult";"params";"self, class_name, file_path, old_folder, new_folder, reason";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateModelSchema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateReportSchema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EndRun";"params";"self, run_id, classes, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractFileClasses";"params";"self, file_path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Features";"params";"self, packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FolderRules";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HashFeature";"params";"self, feature";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Headers";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Imports";"params";"self, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LearnApproved";"params";"self, packet, correct_folder, approved_by";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LearnedScore";"params";"self, features";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Normalize";"params";"self, scores";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"OpenStores";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RankClass";"params";"self, packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RuleScore";"params";"self, features, packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanFiles";"params";"self, root_path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"StartRun";"params";"self, root, files";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"StoreResult";"params";"self, run_id, result";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"TopResults";"params";"self, limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 52 (BracketMemoryStore/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@BracketMemoryStore]{
("class_name";"BracketMemoryStore")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, Param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CleanField;CleanToken;CreateDraftMeaning;CreateDraftProfile;DefaultTokenMeaning;DefaultTokenRelations;EnsureColumn;EnsureDraftProfiles;EnsureOpen;EnsureTokenMeanings;EnsureTokenRelations;GetAppCommand;GetAppFile;GetRuleProfile;GetRuleProfileAction;GetTokenMeaning;GetTokenMeaningAction;GetTokenRelation;InferRowKeyMode;IsIdentityKey;LearnBlocks;ListAppClasses;ListAppCommands;ListAppFiles;ListAppMethods;ListRuleProfiles;ListTokenMeanings;ListTokenRelations;Open;Profile;Rules;SetRuleProfile;SetRuleProfileAction")
("method_count";"35")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, Param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CleanField";"params";"self, Value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CleanToken";"params";"self, Token";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateDraftMeaning";"params";"self, Token, KeyCounts, Count";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateDraftProfile";"params";"self, Token, Blocks";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DefaultTokenMeaning";"params";"self, Token";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DefaultTokenRelations";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureColumn";"params";"self, Cur, TableName, ColumnName, ColumnType";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureDraftProfiles";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureOpen";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureTokenMeanings";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureTokenRelations";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetAppCommand";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetAppFile";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetRuleProfile";"params";"self, Token";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetRuleProfileAction";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetTokenMeaning";"params";"self, Token";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetTokenMeaningAction";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GetTokenRelation";"params";"self, SourceToken, TargetToken, RelationType";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InferRowKeyMode";"params";"self, Pairs";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"IsIdentityKey";"params";"self, Key";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LearnBlocks";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListAppClasses";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListAppCommands";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListAppFiles";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListAppMethods";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListRuleProfiles";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListTokenMeanings";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListTokenRelations";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Open";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Profile";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Rules";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SetRuleProfile";"params";"self, Profile";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SetRuleProfileAction";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 53 (ChatComplianceScorer/?)

VBStyle domain: dom_db

**Sources**: `vb_code_test.vb_classes`

```
[@ChatComplianceScorer]{
("class_name";"ChatComplianceScorer")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_db")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_build_cli;_init;_populate_test_data;_score_one;_score_pending")
("method_count";"9")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_build_cli";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_init";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_populate_test_data";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_score_one";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_score_pending";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 54 (ChatMemoryStep1/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ChatMemoryStep1]{
("class_name";"ChatMemoryStep1")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_build_message;_conn;_ensure_schema;_extract_entity_candidates;_extract_topic_candidates;_find_chat_files;_parse_chat;extract_concepts;get_stats;ingest")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_build_message";"params";"self, role, body_parts";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_conn";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_ensure_schema";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_extract_entity_candidates";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_extract_topic_candidates";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_find_chat_files";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_parse_chat";"params";"self, filepath";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"extract_concepts";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_stats";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ingest";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 55 (ClassMem/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ClassMem]{
("class_name";"ClassMem")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_page_size;_total_bytes;detect;format_bytes")
("method_count";"8")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_page_size";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_total_bytes";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"detect";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"format_bytes";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 56 (ClaudeMemBus/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ClaudeMemBus]{
("class_name";"ClaudeMemBus")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"publish;subscribe")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"publish";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"subscribe";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 57 (ClaudeMemDB/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ClaudeMemDB]{
("class_name";"ClaudeMemDB")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_create_schema;find_route;get_next_command;get_state;queue_command;register_route;set_state;update_command_result")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_create_schema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"find_route";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_next_command";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"queue_command";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"register_route";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"update_command_result";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 58 (ClaudeMemUnit/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ClaudeMemUnit]{
("class_name";"ClaudeMemUnit")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_register_default_routes;connect_core;connect_lib;execute;get_state;set_state")
("method_count";"10")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_register_default_routes";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"connect_core";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"connect_lib";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 59 (CodeScore/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CodeScore]{
("class_name";"CodeScore")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CloseDb;EnsureSchema;Now;OpenDb;Proof;Proof;RankCandidatesByMemory;ReadCommand;ReadTopFailures;ReadTopStrategies;RecordStrategyMemory;ResolveDbPath;ScoreCandidateV3;ScoreCandidateV4;ScoreCandidateV5;ShapeKey")
("method_count";"18")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CloseDb";"params";"self, db";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureSchema";"params";"self, db";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Now";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"OpenDb";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Proof";"params";"self, stage, state, details";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Proof";"params";"self, stage, state, details";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RankCandidatesByMemory";"params";"self, base, audit, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadCommand";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadTopFailures";"params";"self, db";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadTopStrategies";"params";"self, db";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RecordStrategyMemory";"params";"self, db, audit, strategy, passed, score, error";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResolveDbPath";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScoreCandidateV3";"params";"self, text, audit, compile_ok, smoke_ok, equiv_ok";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScoreCandidateV4";"params";"self, text, audit, compile_ok, smoke_ok, equiv_ok, sandbox_ok, proof_ok, runner_ok";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScoreCandidateV5";"params";"self, text, audit, compile_ok, smoke_ok, equiv_ok, sandbox_ok, proof_ok, runner_ok, pytest_ok";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ShapeKey";"params";"self, audit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 60 (CognitiveMemory/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CognitiveMemory]{
("class_name";"CognitiveMemory")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, memunit, config")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Decay;Err;Experiment;Export;Import;Init;Learn;Promote;Proof;Recall;Reinforce;Status")
("method_count";"14")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, memunit, config";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Decay";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Err";"params";"self, msg";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Experiment";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Export";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Import";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Init";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Learn";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Promote";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Proof";"params";"self, ok, result, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Recall";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Reinforce";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Status";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 61 (CoreAstV3/?)

From ChatGPT export: Core_ConfigSetup.py

**Sources**: `vb_code_test.vb_classes`

```
[@CoreAstV3]{
("class_name";"CoreAstV3")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_ConfigSetup.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_tokenize;action_run;get_declaration")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_tokenize";"params";"self, source_text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"action_run";"params";"self, action_name, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_declaration";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 62 (CoreConfigV3/?)

From ChatGPT export: Core_ConfigSetup.py

**Sources**: `vb_code_test.vb_classes`

```
[@CoreConfigV3]{
("class_name";"CoreConfigV3")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_ConfigSetup.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"action_run;get_declaration")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"action_run";"params";"self, action_name, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_declaration";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 63 (CoreDB/?)



**Sources**: `vb_shared.code_classes`

```
[@CoreDB]{
("class_name";"CoreDB")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: CoreDB — linked to real implementation: dom_storage (id=70)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 64 (CoreMLBracketCliOrchestrator/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CoreMLBracketCliOrchestrator]{
("class_name";"CoreMLBracketCliOrchestrator")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"LoadPacket;Main;Report")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"LoadPacket";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Main";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Report";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 65 (CoreMLModelCollector/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CoreMLModelCollector]{
("class_name";"CoreMLModelCollector")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CopyOne;FindModelFile;ModelRows;Prepare;SafeName;WriteBrk;WriteCLoader;WriteCSharpLoader;WriteDb;WriteLoaders;WritePythonLoader;WriteSwiftLoader")
("method_count";"14")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CopyOne";"params";"self, row";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FindModelFile";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ModelRows";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Prepare";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SafeName";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteBrk";"params";"self, rows";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteCLoader";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteCSharpLoader";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteDb";"params";"self, rows";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteLoaders";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WritePythonLoader";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteSwiftLoader";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 66 (CoreMLModelSQLitePackager/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CoreMLModelSQLitePackager]{
("class_name";"CoreMLModelSQLitePackager")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_Config;_Finish;_FinishTuple;_MergeParam;BuildSSLContext;CheckConfig;Cleanup;Connect;DownloadArchive;EnsureSchema;Extract;Inspect;Now;Pack;PrepareWorkspace;SafeFileNameFromUrl;UnpackArchive;Verify;WriteDatabase")
("method_count";"21")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_Config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_Finish";"params";"self, ok, result, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_FinishTuple";"params";"self, packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_MergeParam";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildSSLContext";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckConfig";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Cleanup";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Connect";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DownloadArchive";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureSchema";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Extract";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Inspect";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Now";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Pack";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrepareWorkspace";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SafeFileNameFromUrl";"params";"self, url";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"UnpackArchive";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Verify";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteDatabase";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 67 (CoreSetup/DB_STUDIO_CORE_SETUP)

From ChatGPT export: Core_setup.py

**Sources**: `vb_code_test.vb_classes`

```
[@CoreSetup]{
("class_name";"CoreSetup")
("domain";"DB_STUDIO_CORE_SETUP")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_setup.py")
("init";"self, base_path, memory_unit")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"cleanup;create_packet;ensure_directories;execute;get_path;param;setup;validate")
("method_count";"9")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, base_path, memory_unit";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"cleanup";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"create_packet";"params";"self, ok, emitter, inputs, outputs, errors, logs, meta";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ensure_directories";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_path";"params";"self, name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"param";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"setup";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 68 (CoreSetupV3/?)

From ChatGPT export: Core_ConfigSetup.py

**Sources**: `vb_code_test.vb_classes`

```
[@CoreSetupV3]{
("class_name";"CoreSetupV3")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_ConfigSetup.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"action_run;get_declaration")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"action_run";"params";"self, action_name, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_declaration";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 69 (CoreUefiBoot/DB_STUDIO_UEFI_BOOT)

From ChatGPT export: Core_UefiBoot.py

**Sources**: `vb_code_test.vb_classes`

```
[@CoreUefiBoot]{
("class_name";"CoreUefiBoot")
("domain";"DB_STUDIO_UEFI_BOOT")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_UefiBoot.py")
("init";"self, memory_unit")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"add_discovery;add_log;cleanup;close;complete;create_packet;create_screen;execute;param;set_hardware;set_phases;show;update_phase;validate")
("method_count";"15")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, memory_unit";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"add_discovery";"params";"self, prefix, module_name, class_count";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"add_log";"params";"self, level, message";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"cleanup";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"close";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"complete";"params";"self, boot_time";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"create_packet";"params";"self, ok, emitter, inputs, outputs, errors, logs, meta";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"create_screen";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"param";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_hardware";"params";"self, items";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_phases";"params";"self, names";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"show";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"update_phase";"params";"self, index, status, progress";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 70 (Core_Boot/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_Boot]{
("class_name";"Core_Boot")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_Boot.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 71 (Core_ConfigSetup/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_ConfigSetup]{
("class_name";"Core_ConfigSetup")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_ConfigSetup.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 72 (Core_FileManager/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_FileManager]{
("class_name";"Core_FileManager")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_FileManager — linked to real implementation: dom_io (id=53)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 73 (Core_Magnetic/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_Magnetic]{
("class_name";"Core_Magnetic")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_Magnetic — linked to real implementation: Core_MagneticSearch_v1 (id=132)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 74 (Core_MagneticSearch_v1/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_MagneticSearch_v1]{
("class_name";"Core_MagneticSearch_v1")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_MagneticSearch_v1.c")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 75 (Core_MainUnit/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_MainUnit]{
("class_name";"Core_MainUnit")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_MainUnit.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 76 (Core_Runtime/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_Runtime]{
("class_name";"Core_Runtime")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_Runtime.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 77 (Core_UefiBoot/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_UefiBoot]{
("class_name";"Core_UefiBoot")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_UefiBoot.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 78 (Core_Unit/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_Unit]{
("class_name";"Core_Unit")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_Unit.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 79 (Core_Verification/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_Verification]{
("class_name";"Core_Verification")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_Verification.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 80 (Core_ai/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_ai]{
("class_name";"Core_ai")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_ai — linked to real implementation: dom_process (id=62)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 81 (Core_ai_fix/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_ai_fix]{
("class_name";"Core_ai_fix")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_ai_fix — linked to real implementation: dom_rescue (id=65)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 82 (Core_ast/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_ast]{
("class_name";"Core_ast")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_ast — linked to real implementation: dom_parse (id=61)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 83 (Core_audioDrive/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_audioDrive]{
("class_name";"Core_audioDrive")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_audioDrive — linked to real implementation: dom_system (id=72)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 84 (Core_backend_health/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_backend_health]{
("class_name";"Core_backend_health")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_backend_health — linked to real implementation: dom_system (id=72)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 85 (Core_brackets/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_brackets]{
("class_name";"Core_brackets")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_brackets — linked to real implementation: dom_parse (id=61)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 86 (Core_code_hunter/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_code_hunter]{
("class_name";"Core_code_hunter")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_code_hunter — linked to real implementation: dom_search (id=68)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 87 (Core_code_library/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_code_library]{
("class_name";"Core_code_library")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_code_library — linked to real implementation: dom_search (id=68)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 88 (Core_compression/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_compression]{
("class_name";"Core_compression")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_compression — linked to real implementation: dom_package (id=60)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 89 (Core_db/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_db]{
("class_name";"Core_db")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_db — linked to real implementation: dom_storage (id=70)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 90 (Core_error/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_error]{
("class_name";"Core_error")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_error — linked to real implementation: dom_security (id=69)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 91 (Core_gpu/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_gpu]{
("class_name";"Core_gpu")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_gpu — linked to real implementation: dom_system (id=72)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 92 (Core_hw/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_hw]{
("class_name";"Core_hw")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_hw — linked to real implementation: dom_system (id=72)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 93 (Core_io/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_io]{
("class_name";"Core_io")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_io — linked to real implementation: dom_io (id=53)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 94 (Core_memory_bank/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_memory_bank]{
("class_name";"Core_memory_bank")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_memory_bank — linked to real implementation: dom_knowledge (id=54)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 95 (Core_network/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_network]{
("class_name";"Core_network")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_network — linked to real implementation: dom_network (id=58)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 96 (Core_online_research/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_online_research]{
("class_name";"Core_online_research")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_online_research — linked to real implementation: dom_search (id=68)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 97 (Core_orchestrator/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_orchestrator]{
("class_name";"Core_orchestrator")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_orchestrator — linked to real implementation: dom_orchestration (id=59)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 98 (Core_os/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_os]{
("class_name";"Core_os")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_os — linked to real implementation: dom_system (id=72)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 99 (Core_output/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_output]{
("class_name";"Core_output")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_output — linked to real implementation: dom_text (id=74)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 100 (Core_report/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_report]{
("class_name";"Core_report")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_report — linked to real implementation: dom_qa (id=63)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 101 (Core_rules/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_rules]{
("class_name";"Core_rules")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_rules — linked to real implementation: Core_Verification (id=215)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 102 (Core_setup/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_setup]{
("class_name";"Core_setup")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_setup.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 103 (Core_state/?)



**Sources**: `vb_shared.code_classes` `vb_shared.code_registry`

```
[@Core_state]{
("class_name";"Core_state")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry")
("description";"")
("mysql_description";"From ChatGPT export: Core_state.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 104 (Core_token_engine/?)



**Sources**: `vb_shared.code_classes`

```
[@Core_token_engine]{
("class_name";"Core_token_engine")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Core_token_engine — linked to real implementation: dom_parse (id=61)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 105 (CorrectionMemoryEngine/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@CorrectionMemoryEngine]{
("class_name";"CorrectionMemoryEngine")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_add_correction;_get_correction;_read_state;_set_config")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_add_correction";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_get_correction";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 106 (DeterministicMathematicalCore/?)

ChatGPT export: file_00000000f9e071fdb9da958bd79cd631.dat

**Sources**: `vb_code_test.vb_classes`

```
[@DeterministicMathematicalCore]{
("class_name";"DeterministicMathematicalCore")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_00000000f9e071fdb9da958bd79cd631.dat")
("init";"self, hidden_dim, known_operations")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_encode_known_behaviors;_initialize_mathematical_weights;forward")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, hidden_dim, known_operations";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_encode_known_behaviors";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_initialize_mathematical_weights";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"forward";"params";"self, x, task_type";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 107 (FormatBucketScorer/?)

ChatGPT export: file_000000008f6071fd8c898700550b53cd.dat

**Sources**: `vb_code_test.vb_classes`

```
[@FormatBucketScorer]{
("class_name";"FormatBucketScorer")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_000000008f6071fd8c898700550b53cd.dat")
("init";"self, config, report")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"coverage_score;duplicate_front_token_penalty;duplicate_label_penalty;roundtrip_score;score_revision;size_score")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, config, report";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"coverage_score";"params";"self, body, model";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"duplicate_front_token_penalty";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"duplicate_label_penalty";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"roundtrip_score";"params";"self, roundtrip";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"score_revision";"params";"self, body, model, roundtrip";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"size_score";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 108 (FormatScorer/?)

ChatGPT export: file_00000000aaa071fdb37da074810b3116.dat

**Sources**: `vb_code_test.vb_classes`

```
[@FormatScorer]{
("class_name";"FormatScorer")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_00000000aaa071fdb37da074810b3116.dat")
("init";"self, config, report")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"coverage_score;front_penalty;label_penalty;roundtrip_score;score;size_score")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, config, report";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"coverage_score";"params";"self, body, model";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"front_penalty";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"label_penalty";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"roundtrip_score";"params";"self, roundtrip";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"score";"params";"self, body, model, roundtrip";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"size_score";"params";"self, body";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 109 (Gui_U_C_ReportMemUnit/?)

From ChatGPT export: Gui_U_C_framework.py

**Sources**: `vb_code_test.vb_classes`

```
[@Gui_U_C_ReportMemUnit]{
("class_name";"Gui_U_C_ReportMemUnit")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Gui_U_C_framework.py")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"fetch_packet;packet_index;store_packet")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"fetch_packet";"params";"self, packet_name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"packet_index";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"store_packet";"params";"self, packet_name, packet";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 110 (IdentityCore/?)

VBStyle domain: dom_knowledge

**Sources**: `vb_code_test.vb_classes`

```
[@IdentityCore]{
("class_name";"IdentityCore")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_knowledge")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_check_goal;_query;_update")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_check_goal";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_query";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_update";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 111 (LongTermMemory/?)

VBStyle domain: dom_memory

**Sources**: `vb_code_test.vb_classes`

```
[@LongTermMemory]{
("class_name";"LongTermMemory")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_memory")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_recall;_search;_store")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_recall";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_search";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_store";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 112 (MemDB/?)



**Sources**: `disk:VBSTYLE_MemUnit.py`

```
[@MemDB]{
("class_name";"MemDB")
("domain";"")
("source";"/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/CORE/VBSTYLE_MemUnit.py")
("sources";"sqlite:v20_hybrid_best.db;disk:VBSTYLE_MemUnit.py")
("description";"")
("init";"self, mem=None, db=None, param=None")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_create_schema;queue_command;get_next_command;update_command_result")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem=None, db=None, param=None";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_create_schema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"queue_command";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_next_command";"params";"self, params=None";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"update_command_result";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 113 (MemDB_Python/?)



**Sources**: `vb_shared.code_classes`

```
[@MemDB_Python]{
("class_name";"MemDB_Python")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle Core: VBSTYLE_MemUnit.py")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 114 (Memory/?)

VBStyle domain: dom_memory

**Sources**: `vb_code_test.vb_classes`

```
[@Memory]{
("class_name";"Memory")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_memory")
("init";"self, location, backend, mmap_mode, compress, verbose, backend_options")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"cache;clear;eval;reduce_size")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__getstate__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"__init__";"params";"self, location, backend, mmap_mode, compress, verbose, backend_options";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"__repr__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"cache";"params";"self, func, ignore, verbose, mmap_mode, cache_validation_callback";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"clear";"params";"self, warn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"eval";"params";"self, func";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"reduce_size";"params";"self, bytes_limit, items_limit, age_limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 115 (MemoryConsolidator/?)

VBStyle domain: dom_knowledge

**Sources**: `vb_code_test.vb_classes`

```
[@MemoryConsolidator]{
("class_name";"MemoryConsolidator")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_knowledge")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_consolidate;_decay;_recall")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_consolidate";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_decay";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_recall";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 116 (MemoryEntry/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@MemoryEntry]{
("class_name";"MemoryEntry")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"no")
("run_commands";"")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 117 (MemoryExtractor/?)

VBStyle domain: dom_search

**Sources**: `vb_code_test.vb_classes`

```
[@MemoryExtractor]{
("class_name";"MemoryExtractor")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_search")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_create_entity;_extract_brackets;_extract_database;_extract_python;_save_json;_summary")
("method_count";"10")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_create_entity";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_extract_brackets";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_extract_database";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_extract_python";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_save_json";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_summary";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 118 (MemoryTraceProbe/?)

From ChatGPT export: Core_Verification.py

**Sources**: `vb_code_test.vb_classes`

```
[@MemoryTraceProbe]{
("class_name";"MemoryTraceProbe")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From ChatGPT export: Core_Verification.py")
("init";"self, memory_unit")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"actions;count;install;uninstall")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, memory_unit";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"actions";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"count";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"install";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"uninstall";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 119 (Name_Equalizer/?)



**Sources**: `vb_shared.code_classes`

```
[@Name_Equalizer]{
("class_name";"Name_Equalizer")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: Name_Equalizer — linked to real implementation: dom_style (id=71)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 120 (OnboardingScore/?)

ChatGPT export: file_000000000c98722fb0639f51ee107ddd.dat

**Sources**: `vb_code_test.vb_classes`

```
[@OnboardingScore]{
("class_name";"OnboardingScore")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_000000000c98722fb0639f51ee107ddd.dat")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"add;decide_permission;percent")
("method_count";"4")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"add";"params";"self, qid, topic, earned, possible, verdict, missing, failed";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"decide_permission";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"percent";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 121 (Scorer/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@Scorer]{
("class_name";"Scorer")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_score")
("method_count";"5")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_score";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 122 (SearchFilenameMode/?)

ChatGPT export: file_000000006f3471fda82ea54d462e5fb5.dat

**Sources**: `vb_code_test.vb_classes`

```
[@SearchFilenameMode]{
("class_name";"SearchFilenameMode")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_000000006f3471fda82ea54d462e5fb5.dat")
("init";"self, config, collect, path_mode, row_build")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_build_filename_row;run")
("method_count";"3")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, config, collect, path_mode, row_build";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_build_filename_row";"params";"self, query";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"run";"params";"self, progress_cb, log_cb";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 123 (SearchMemUnit/?)

ChatGPT export: file_00000000252c71fda1d875193c4fd8ae.dat

**Sources**: `vb_code_test.vb_classes`

```
[@SearchMemUnit]{
("class_name";"SearchMemUnit")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_00000000252c71fda1d875193c4fd8ae.dat")
("init";"self, config_path")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_content_bridge;_safe_stat_bridge;close;execute;load_config")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, config_path";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_content_bridge";"params";"self, query";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_safe_stat_bridge";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"close";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"execute";"params";"self, override, progress_cb, log_cb";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_config";"params";"self, override";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 124 (SessionMemory/?)

VBStyle domain: dom_memory

**Sources**: `vb_code_test.vb_classes`

```
[@SessionMemory]{
("class_name";"SessionMemory")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_memory")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_clear;_recall;_store")
("method_count";"7")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_clear";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_recall";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_store";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 125 (UNIT_CoreMemUnit/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@UNIT_CoreMemUnit]{
("class_name";"UNIT_CoreMemUnit")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_bus_publish;_cache_get;_cache_set;_fail;_init_database;_memdb_get;_memdb_set;_ok;_queue_dequeue;_queue_enqueue;_route_find;_route_register;get_connection;get_stats;Rdstat")
("method_count";"17")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_bus_publish";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_cache_get";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_cache_set";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_fail";"params";"self, code, message, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_init_database";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_memdb_get";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_memdb_set";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_queue_dequeue";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_queue_enqueue";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_route_find";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_route_register";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_connection";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_stats";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Rdstat";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, action, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 126 (VBStyleAutoFix/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleAutoFix]{
("class_name";"VBStyleAutoFix")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Apply;ApplyPlan;Audit;AuditReport;Bootstrap;BuildHeaderInjection;CloseRun;CollectGovernedFiles;HasSnapshot;InsertPoint;Issue;MissingHeaderTags;Now;OpenRun;PlanAll;PlanHeaderInject;PlanReport;Rollback;Sha;Status;TakeSnapshot")
("method_count";"23")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Apply";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ApplyPlan";"params";"self, runId, plan";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Audit";"params";"self, planId, event, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AuditReport";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Bootstrap";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildHeaderInjection";"params";"self, fileName, missing";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CloseRun";"params";"self, stats";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CollectGovernedFiles";"params";"self, scope";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasSnapshot";"params";"self, runId, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertPoint";"params";"self, lines";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Issue";"params";"self, kind, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"MissingHeaderTags";"params";"self, source";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Now";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"OpenRun";"params";"self, fixClass, applyMode";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PlanAll";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PlanHeaderInject";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PlanReport";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Rollback";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Sha";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Status";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"TakeSnapshot";"params";"self, runId, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 127 (VBStyleClusterAuditCLI/?)

ChatGPT export: file_000000002b70720c96caece2cc75d219.dat

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleClusterAuditCLI]{
("class_name";"VBStyleClusterAuditCLI")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_000000002b70720c96caece2cc75d219.dat")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"AddFinding;BuildClusters;BuildRepairPlans;CallAttrBase;CallName;ClusterFixAction;ClusterReplacementStrategy;ClusterWhy;CollectFiles;CompactLines;Esc;LawForViolation;LooksPathLike;PrintClusters;PrintFail;PrintRepairs;PrintReport;PrintSummary;PrintViolations;ReadText;Rel;ResolveRoot;ScanAstShape;ScanCalls;ScanClassInit;ScanClassMethodReturns;ScanDirectCallsWithoutTuple3;ScanFile;ScanFunctionReturn;ScanHardcodedPaths;ScanHeader;ScanImports;ScanInlineSql")
("method_count";"35")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"AddFinding";"params";"self, path, line, violation, evidence, fix, cluster_hint";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildClusters";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildRepairPlans";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallAttrBase";"params";"self, attr";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallName";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ClusterFixAction";"params";"self, cluster_type";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ClusterReplacementStrategy";"params";"self, cluster_type";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ClusterWhy";"params";"self, cluster_type";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CollectFiles";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CompactLines";"params";"self, lines";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Esc";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LawForViolation";"params";"self, violation";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LooksPathLike";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintClusters";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintFail";"params";"self, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintRepairs";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintReport";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintSummary";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintViolations";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadText";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Rel";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResolveRoot";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanAstShape";"params";"self, path, tree, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanCalls";"params";"self, path, tree, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanClassInit";"params";"self, path, cls";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanClassMethodReturns";"params";"self, path, cls";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanDirectCallsWithoutTuple3";"params";"self, path, tree, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanFile";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanFunctionReturn";"params";"self, path, func, label, cluster_hint";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanHardcodedPaths";"params";"self, path, tree, lines, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanHeader";"params";"self, path, lines, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanImports";"params";"self, path, tree, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanInlineSql";"params";"self, path, lines, summary";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 128 (VBStyleCompleteDomainDbPopulator20260505/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleCompleteDomainDbPopulator20260505]{
("class_name";"VBStyleCompleteDomainDbPopulator20260505")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_Fail;_Ok;ActionCode;ActionIdMap;AllParamRows;BackupMasterDb;CleanCode;CleanName;Counts;CountTable;DomainAuthority;DomainCode;DomainIdMap;EnsureSchema;GoldSummary;InsertActions;InsertDomains;InsertParams;InsertSamples;ParamTemplates;Render;SideEffect;Token;Verify")
("method_count";"26")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_Fail";"params";"self, code, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_Ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ActionCode";"params";"self, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ActionIdMap";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AllParamRows";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BackupMasterDb";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CleanCode";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CleanName";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Counts";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CountTable";"params";"self, conn, table";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DomainAuthority";"params";"self, family";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DomainCode";"params";"self, family";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DomainIdMap";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EnsureSchema";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GoldSummary";"params";"self, gold";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertActions";"params";"self, conn, action_rows";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertDomains";"params";"self, conn, families";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertParams";"params";"self, conn, action_tokens";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertSamples";"params";"self, conn, gold, action_tokens";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParamTemplates";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Render";"params";"self, backup, gold_summary, before, inserted, after, verify";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SideEffect";"params";"self, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Token";"params";"self, family, action";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Verify";"params";"self, conn, domain_codes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 129 (VBStyleDBExecutor/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleDBExecutor]{
("class_name";"VBStyleDBExecutor")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_clean_method_code;_close;_compile_method;_connect;instantiate_and_run;load_class_from_db")
("method_count";"8")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_clean_method_code";"params";"self, raw_code, method_name";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_close";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_compile_method";"params";"self, code, name, namespace";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_connect";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"instantiate_and_run";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_class_from_db";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 130 (VBStyleDeprecator/?)

From ChatGPT export: VBStyleDeprecator.py

**Sources**: `vb_shared.code_classes` `vb_shared.code_registry` `vb_code_test.vb_classes`

```
[@VBStyleDeprecator]{
("class_name";"VBStyleDeprecator")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes;vb_shared.code_registry;vb_code_test.vb_classes")
("description";"From ChatGPT export: VBStyleDeprecator.py")
("mysql_description";"From ChatGPT export: VBStyleDeprecator.py")
("init";"self, base_path, dump_path, mode")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"process_file;run;scan_directory;scan_for_deprecated;update_ghost_header_deprecated")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, base_path, dump_path, mode";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"process_file";"params";"self, file_info";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"run";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"scan_directory";"params";"self, extensions";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"scan_for_deprecated";"params";"self, file_path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"update_ghost_header_deprecated";"params";"self, file_path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 131 (VBStyleEnforcer/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleEnforcer]{
("class_name";"VBStyleEnforcer")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, params")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"check_class_structure;check_domain_boundaries;check_hardcoded_values;check_headers;check_memunit_routing;check_print_statements;check_tuple3_returns;close;export_manifest;load_intelligent_fixes;load_rules;load_wayne_preferences;post_check;pre_check;validate_file")
("method_count";"17")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, params";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"check_class_structure";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_domain_boundaries";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_hardcoded_values";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_headers";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_memunit_routing";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_print_statements";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_tuple3_returns";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"close";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"export_manifest";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_intelligent_fixes";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_rules";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_wayne_preferences";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"post_check";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"pre_check";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 132 (VBStyleFaultAppender/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleFaultAppender]{
("class_name";"VBStyleFaultAppender")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Add;AddBodyShapeFaults;AddDomainAuthorityFaults;AddDuplicateMethodFaults;AddExceptionFaults;AddFileClassFaults;AddForbiddenPatternFaults;AddHeaderFaults;AddImportFaults;AddIssueShapeFaults;AddParamShapeFaults;AddReturnFaults;AddRunFaults;ApplyBrkRulePack;ApplyCustomRulePack;AuditAppend;AuditOnly;Backup;BuildBlock;Classes;CodeBody;DispatchActions;FindFaults;HasAuthorityMismatch;HasBareReturn;HasNonTupleReturn")
("method_count";"27")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Add";"params";"self, Faults, Code, Found, Fix, Weight, State";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddBodyShapeFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddDomainAuthorityFaults";"params";"self, Faults, FileBase, Classes, Methods, BodyText";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddDuplicateMethodFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddExceptionFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddFileClassFaults";"params";"self, Faults, FileBase, Classes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddForbiddenPatternFaults";"params";"self, Faults, BodyText";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddHeaderFaults";"params";"self, Faults, Header";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddImportFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddIssueShapeFaults";"params";"self, Faults, BodyText";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddParamShapeFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddReturnFaults";"params";"self, Faults, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AddRunFaults";"params";"self, Faults, Methods, Dispatch";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ApplyBrkRulePack";"params";"self, Faults, PathText, Text, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ApplyCustomRulePack";"params";"self, Faults, PathText, Text, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AuditAppend";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AuditOnly";"params";"self, Param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Backup";"params";"self, PathText";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildBlock";"params";"self, PathText, Text, Faults";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Classes";"params";"self, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CodeBody";"params";"self, Text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DispatchActions";"params";"self, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FindFaults";"params";"self, PathText, Text, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasAuthorityMismatch";"params";"self, PathText, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasBareReturn";"params";"self, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasNonTupleReturn";"params";"self, Tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 133 (VBStyleMethodizer/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleMethodizer]{
("class_name";"VBStyleMethodizer")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"convert;detect;pipeline;validate")
("method_count";"6")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"convert";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"detect";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"pipeline";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 134 (VBStyleRecoveryAuditor20260506/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRecoveryAuditor20260506]{
("class_name";"VBStyleRecoveryAuditor20260506")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CallTargetsTuple3;CheckReturns;Classify;ClassifyCall;CollectUnitFiles;CreateAuditDb;DetectConfigContradictions;ExtractDbLine;ExtractHeaderTags;ExtractRuleMap;ExtractSqlLockMaster;Fail;HasModuleDocstring;IsMainBlock;Ok;ParseDbAuthority;ParseGateRules;ParseMemUnitShape;ParseVBSRuleCodes;ReadText;ScanUnit;WriteAuditBrk;WriteRuleMapBrk")
("method_count";"25")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CallTargetsTuple3";"params";"self, call";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckReturns";"params";"self, fn_node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Classify";"params";"self, violations, info";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ClassifyCall";"params";"self, call, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CollectUnitFiles";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateAuditDb";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DetectConfigContradictions";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractDbLine";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractHeaderTags";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractRuleMap";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractSqlLockMaster";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Fail";"params";"self, code, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasModuleDocstring";"params";"self, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"IsMainBlock";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParseDbAuthority";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParseGateRules";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParseMemUnitShape";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParseVBSRuleCodes";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadText";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanUnit";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteAuditBrk";"params";"self, rulemap, per_file, pass_count, fail_count, unknown_count, total_violations";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"WriteRuleMapBrk";"params";"self, rulemap";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 135 (VBStyleRuleArena/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRuleArena]{
("class_name";"VBStyleRuleArena")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Attack;BadCases;CallName;CheckConformance;CheckDomainAuthority;CheckNoDirectImport;CheckNoSysPath;CheckRequirementSource;CheckSemanticDisguise;CheckSideEffect;CheckTuple3Semantic;CheckUnknownBlock;CreateSchema;Defend;Fight;GenerateCases;GeneratePatchesFromWeaknesses;GoodCases;Issue;LatestRunId;MutateCase;Open;OutcomeMatches;PatchFor;ProposeSolution;Rate;RecordDefenseRound;RecordWeakness;ResolveConfigBrk;ResolveDbPath;RunCase;Score;ScoreOutcomes")
("method_count";"35")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Attack";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BadCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallName";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckConformance";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDomainAuthority";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoDirectImport";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoSysPath";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRequirementSource";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSemanticDisguise";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSideEffect";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckTuple3Semantic";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckUnknownBlock";"params";"self, tree, src";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateSchema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Defend";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Fight";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GenerateCases";"params";"self, count, with_mutations";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GeneratePatchesFromWeaknesses";"params";"self, defend_id, round_index";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GoodCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Issue";"params";"self, kind, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LatestRunId";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"MutateCase";"params";"self, seed, idx";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Open";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"OutcomeMatches";"params";"self, expected, actual";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PatchFor";"params";"self, case, outcome";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ProposeSolution";"params";"self, run_id, weakness_id, case, outcome";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Rate";"params";"self, num, total";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RecordDefenseRound";"params";"self, defend_id, round_index, patch_count, score";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RecordWeakness";"params";"self, run_id, case, outcome";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResolveConfigBrk";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResolveDbPath";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"RunCase";"params";"self, run_id, round_index, case, defend_id";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Score";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScoreOutcomes";"params";"self,";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 136 (VBStyleRuleDbImporter/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRuleDbImporter]{
("class_name";"VBStyleRuleDbImporter")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, db_conn, config")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"ClassifyArtifact;CreateTables;DropTables;Fail;FindLineNumber;FirstDocstring;HashText;ImportCoreMLModelDatabase;ImportFamilies;ImportRules;InsertArchitectureDocs;InsertArchitectureRouteRules;InsertArchitectureRules;InsertAuthorityForUnit;InsertAuthorityMap;InsertAuthorityWorlds;InsertCheckRule;InsertClassesFunctionsFromTree;InsertCodeAuthority;InsertCodeBlock;InsertCodeClass;InsertCodeFunction;InsertCodeGraph;InsertCodeMethod")
("method_count";"25")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, db_conn, config";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"ClassifyArtifact";"params";"self, path, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateTables";"params";"self, cur";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DropTables";"params";"self, cur";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Fail";"params";"self, fault_code, message";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FindLineNumber";"params";"self, text, needle";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FirstDocstring";"params";"self, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HashText";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ImportCoreMLModelDatabase";"params";"self, cur, model_db_path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ImportFamilies";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ImportRules";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertArchitectureDocs";"params";"self, cur";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertArchitectureRouteRules";"params";"self, cur, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertArchitectureRules";"params";"self, cur, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertAuthorityForUnit";"params";"self, cur, unit_id, domain";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertAuthorityMap";"params";"self, cur, family_id, family";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertAuthorityWorlds";"params";"self, cur, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCheckRule";"params";"self, cur, rule_item_id, check_text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertClassesFunctionsFromTree";"params";"self, cur, file_id, unit_id, artifact_type, path, text, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeAuthority";"params";"self, cur, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeBlock";"params";"self, cur, path, content";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeClass";"params";"self, cur, file_id, unit_id, artifact_type, path, text, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeFunction";"params";"self, cur, file_id, unit_id, artifact_type, path, text, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeGraph";"params";"self, cur";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InsertCodeMethod";"params";"self, cur, file";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 137 (VBStyleRuleDefender/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRuleDefender]{
("class_name";"VBStyleRuleDefender")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"BadCases;BlueValidate;BuildOutcome;BuildPatch;CallName;CheckCallerImpact;CheckCandidateIsolation;CheckConformance;CheckDataAuthority;CheckDomainAuthority;CheckDuplicateCapability;CheckNoDirectImport;CheckNoSysPath;CheckProofMinimum;CheckRegistryUpdate;CheckRequirementSource;CheckSemanticDisguise;CheckSideEffect;CheckUnknownBlock;CreateSchema;Decision;EndDefendRun;GenerateCases;GoodCases;LatestDefenseRounds")
("method_count";"26")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"BadCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BlueValidate";"params";"self, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildOutcome";"params";"self, defend_id, round_index, case, verdict";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildPatch";"params";"self, defend_id, round_index, weakness";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallName";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCallerImpact";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCandidateIsolation";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckConformance";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDataAuthority";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDomainAuthority";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDuplicateCapability";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoDirectImport";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoSysPath";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckProofMinimum";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRegistryUpdate";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRequirementSource";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSemanticDisguise";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSideEffect";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckUnknownBlock";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateSchema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Decision";"params";"self, actual, failed, passed, unknown, reason";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EndDefendRun";"params";"self, defend_id, freeze, final_strength, rounds";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GenerateCases";"params";"self, count";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GoodCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LatestDefenseRounds";"params";"self, limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 138 (VBStyleRuleFuzzer/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRuleFuzzer]{
("class_name";"VBStyleRuleFuzzer")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"BadCases;BlueValidate;BuildOutcome;BuildRuleBank;CallName;CheckCallerImpact;CheckCandidateIsolation;CheckConformance;CheckDataAuthority;CheckDomainAuthority;CheckDuplicateCapability;CheckNoDirectImport;CheckNoSysPath;CheckProofMinimum;CheckRegistryUpdate;CheckRequirementSource;CheckSideEffect;CheckUnknownBlock;CreateSchema;Decision;EndRun;ExtractSignals;GenerateCases;GoodCases;LatestSolutions;LatestWeaknesses;LearnSignals;MutateCase")
("method_count";"29")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"BadCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BlueValidate";"params";"self, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildOutcome";"params";"self, run_id, case_id, case, verdict, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"BuildRuleBank";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallName";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCallerImpact";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCandidateIsolation";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckConformance";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDataAuthority";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDomainAuthority";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDuplicateCapability";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoDirectImport";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckNoSysPath";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckProofMinimum";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRegistryUpdate";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRequirementSource";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSideEffect";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckUnknownBlock";"params";"self, tree, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CreateSchema";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Decision";"params";"self, actual, failed, passed, unknown, reason";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"EndRun";"params";"self, run_id, score, outcomes";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ExtractSignals";"params";"self, source_code";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GenerateCases";"params";"self, count";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"GoodCases";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LatestSolutions";"params";"self, limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LatestWeaknesses";"params";"self, limit";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LearnSignals";"params";"self, case, outcome";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"MutateCase";"params";"s";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 139 (VBStyleRuleValidator/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleRuleValidator]{
("class_name";"VBStyleRuleValidator")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"CheckAuthorityCheck;CheckBoundaryViolationCheck;CheckCallerImpactCheck;CheckCapabilityCheck;CheckConformanceCheck;CheckDataAuthorityCheck;CheckDomainResolve;CheckDuplicateCapabilityCheck;CheckExistenceCheck;CheckRequirementCheck;CheckSideEffectCheck;CheckWorksCheck;Decide;Issue;Validate;Verdict")
("method_count";"18")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"CheckAuthorityCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckBoundaryViolationCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCallerImpactCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCapabilityCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckConformanceCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDataAuthorityCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDomainResolve";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckDuplicateCapabilityCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckExistenceCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckRequirementCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckSideEffectCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckWorksCheck";"params";"self, c";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Decide";"params";"self, verdicts, candidate";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Issue";"params";"self, kind, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Validate";"params";"self, candidate";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Verdict";"params";"self, status, reason";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 140 (VBStyleSeedDataMirrorExporter20260506/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleSeedDataMirrorExporter20260506]{
("class_name";"VBStyleSeedDataMirrorExporter20260506")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_Fail;_Ok;ActionBlock;DomainBlock;Header;ParamBlock;Quote;SampleBlock")
("method_count";"10")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_Fail";"params";"self, code, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_Ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ActionBlock";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"DomainBlock";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Header";"params";"self, counts";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ParamBlock";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Quote";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SampleBlock";"params";"self, conn, out_handle";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 141 (VBStyleSeedDataMirrorVerifier20260506/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleSeedDataMirrorVerifier20260506]{
("class_name";"VBStyleSeedDataMirrorVerifier20260506")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"_Fail;_Ok;ApplyMirror;ApplySchema;CountAll;Reset")
("method_count";"8")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_Fail";"params";"self, code, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_Ok";"params";"self, value";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ApplyMirror";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ApplySchema";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CountAll";"params";"self, conn";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Reset";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 142 (VBStyleTagger/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleTagger]{
("class_name";"VBStyleTagger")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"ApplyTag;AuditFile;Issue;LearnRule;ListRules;LoadRules;NextCode;PinFaults;ReadState;ScanFolder;SuggestTags;TagTemplate")
("method_count";"14")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"ApplyTag";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"AuditFile";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Issue";"params";"self, kind, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LearnRule";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ListRules";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LoadRules";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"NextCode";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PinFaults";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadState";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanFolder";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"SuggestTags";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"TagTemplate";"params";"self, key, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 143 (VBStyleValidator/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleValidator]{
("class_name";"VBStyleValidator")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_check_returns_tuple3;check_class_naming;check_no_decorators;check_no_hardcoded;check_run_contract;validate_file;validate_source")
("method_count";"11")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_check_returns_tuple3";"params";"self, func_node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_class_naming";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_no_decorators";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_no_hardcoded";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"check_run_contract";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, config";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"validate_source";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 144 (VBStyleViolationTableCLI/?)

ChatGPT export: file_000000001d9471f59285b68e23801b98.dat

**Sources**: `vb_code_test.vb_classes`

```
[@VBStyleViolationTableCLI]{
("class_name";"VBStyleViolationTableCLI")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"ChatGPT export: file_000000001d9471f59285b68e23801b98.dat")
("init";"self")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Add;CallAttrBase;CallName;CheckAssign;CheckCall;CheckReturnContract;Esc;Law;PrintFail;PrintReport;ReadTarget;ResolvePath;Scan;ScanAst;ScanDirectDb;ScanDirectIo;ScanHardcodedPaths;ScanHeader;ScanInlineSql;ScanMainBlock")
("method_count";"22")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Add";"params";"self, line, violation, evidence, fix";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallAttrBase";"params";"self, attr";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CallName";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckAssign";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckCall";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"CheckReturnContract";"params";"self, node";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Esc";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Law";"params";"self, violation";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintFail";"params";"self, issues";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"PrintReport";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ReadTarget";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ResolvePath";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Scan";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanAst";"params";"self, tree";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanDirectDb";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanDirectIo";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanHardcodedPaths";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanHeader";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanInlineSql";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"ScanMainBlock";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 145 (VbstyleChecker/' not in content:)

VBStyle domain: dom_validate

**Sources**: `vb_code_test.vb_classes`

```
[@VbstyleChecker]{
("class_name";"VbstyleChecker")
("domain";"' not in content:")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"VBStyle domain: dom_validate")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_check;_check_file;_check_folder;_check_method")
("method_count";"8")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_check";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_file";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_folder";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_method";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, values";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 146 (VbstyleGateV2Sweeper/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@VbstyleGateV2Sweeper]{
("class_name";"VbstyleGateV2Sweeper")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"Apply;FindCandidates;HasVbstyleHeader;InspectFile;Issue;LocateHeaderLine;MakeBackupPath;Scan;StampFile")
("method_count";"11")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"Apply";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"FindCandidates";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"HasVbstyleHeader";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"InspectFile";"params";"self, path";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Issue";"params";"self, kind, detail";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"LocateHeaderLine";"params";"self, text";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"MakeBackupPath";"params";"self, src, ts";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Scan";"params";"self, param";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"StampFile";"params";"self, path, ts";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 147 (ZramCoreContract/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ZramCoreContract]{
("class_name";"ZramCoreContract")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_check_i1_authority_truth;_check_i2_cache_derivable;_check_i3_validated_materialization;_check_i4_rollback_backward_only;_check_i5_dag_acyclic;_check_i6_no_silent_mutation;_check_i7_monotonic_authority;_execute;_load;_materialize;_read_state;_rollback;_snapshot;_validate")
("method_count";"18")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_check_i1_authority_truth";"params";"self, auth";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i2_cache_derivable";"params";"self, auth, cached_hash";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i3_validated_materialization";"params";"self, state";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i4_rollback_backward_only";"params";"self, target_index";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i5_dag_acyclic";"params";"self, parent_id, child_id, lineage";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i6_no_silent_mutation";"params";"self, mutation_type, journal_entry";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_check_i7_monotonic_authority";"params";"self, old_state, new_state";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_execute";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_load";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_materialize";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_rollback";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_snapshot";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_validate";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 148 (ZramGuiCoreMemUnit/NULL)

From CODEBASE scan

**Sources**: `vb_code_test.vb_classes`

```
[@ZramGuiCoreMemUnit]{
("class_name";"ZramGuiCoreMemUnit")
("domain";"NULL")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_code_test.vb_classes")
("description";"From CODEBASE scan")
("init";"self, mem, db, param")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"yes")
("has_set_config";"yes")
("run_commands";"_init_registry;_register_file;get_module_by_name;get_module_by_role;get_registry;get_stats;load_module;scan_modules")
("method_count";"12")
("weight";"100")
[@methods]{
("method";"__init__";"params";"self, mem, db, param";"dunder";"yes";"vbstyle";"no";"tuple3";"no")
("method";"_init_registry";"params";"self";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"_register_file";"params";"self, cursor, fpath, fname, folder";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_module_by_name";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_module_by_role";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_registry";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"get_stats";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"load_module";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"read_state";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"Run";"params";"self, command, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"scan_modules";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
("method";"set_config";"params";"self, params";"dunder";"no";"vbstyle";"no";"tuple3";"no")
}
}
```

---

### 149 (core_config/?)



**Sources**: `vb_shared.code_classes`

```
[@core_config]{
("class_name";"core_config")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: core_config — linked to real implementation: Config (id=278)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 150 (errorcodes/?)



**Sources**: `vb_shared.code_classes`

```
[@errorcodes]{
("class_name";"errorcodes")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: errorcodes — linked to real implementation: dom_log (id=55)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 151 (resources/?)



**Sources**: `vb_shared.code_classes`

```
[@resources]{
("class_name";"resources")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: resources — linked to real implementation: dom_schedule (id=67)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 152 (the_Class_Setup/?)



**Sources**: `vb_shared.code_classes`

```
[@the_Class_Setup]{
("class_name";"the_Class_Setup")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: the_Class_Setup — linked to real implementation: Core_Runtime (id=163)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

### 153 (the_Class_Setup_gui/?)



**Sources**: `vb_shared.code_classes`

```
[@the_Class_Setup_gui]{
("class_name";"the_Class_Setup_gui")
("domain";"")
("source";"")
("sources";"sqlite:v20_hybrid_best.db;vb_shared.code_classes")
("description";"")
("mysql_description";"VBStyle core class: the_Class_Setup_gui — linked to real implementation: dom_qt (id=64)")
("init";"")
("is_vbstyle";"no")
("has_run";"no")
("has_tuple3";"no")
("has_read_state";"no")
("has_set_config";"no")
("run_commands";"")
("method_count";"0")
("weight";"100")
}
```

---

## Design Rationale (from vb_shared.designrationale)

### architecture shift - code execution to semantic registry

> After removing code_units, the database architecture shifted from a code execution database to a VBStyle semantic registry. Current purpose: classes define conceptual/runtime authorities, methods define available operations, problems define failure states, solutions define weighted remedies, tokens/

*Category: architecture | Source: vb_shared.designrationale*

---

### Capability Resolution Algorithm (MEMUNIT)

> Step 1: Intent received. MEMUNIT parses intent into structured requirements. Step 2: Select intent schemas (classes) that match the intent category. Step 3: For each selected class, read its declared capability requirements. Step 4: Query method pool for candidates matching each requirement by domai

*Category: architecture | Source: vb_shared.designrationale*

---

### Code Review Execution Methodology

> STEP 1: READ FULL CODE BASELINE. Before any review, read entire file to understand structure. Cannot review what you havent seen. STEP 2: FIRST PASS - SURFACE ISSUES. Check imports, syntax, obvious bugs, style violations. This catches 20% of issues quickly. STEP 3: SECOND PASS - LOGIC ISSUES. Check 

*Category: code_review_methodology | Source: vb_shared.designrationale*

---

### Core Principle: AI Owns Intent, System Owns Geometry

> The deeper fix is not make AI smarter. It is remove layout authority from the AI. AI should not own pixels. AI should own intent. The stack is: CLI/Voice/Model -> Intent Extractor -> Architecture Selector -> Constraint Layer -> Spatial Priority Solver -> Interaction Layer -> Simulation Engine -> Vis

*Category: principle | Source: vb_shared.designrationale*

---

### Core Principle: AI Owns Intent, System Owns Geometry

> The deeper fix is not make AI smarter. It is remove layout authority from the AI. AI should not own pixels. AI should own intent. The stack is: CLI/Voice/Model -> Intent Extractor -> Architecture Selector -> Constraint Layer -> Spatial Priority Solver -> Interaction Layer -> Simulation Engine -> Vis

*Category: principle | Source: vb_shared.designrationale*

---

### Corrected Model: Capability-Driven Execution Kernel

> On 2026-05-22, AI corrected its understanding of the system architecture. Previous assumption: methods are assigned to classes statically (OOP model). Correct model: Methods are stateless capability atoms in a pool with governance metadata. Classes are intent schemas that declare capability requirem

*Category: lesson | Source: vb_shared.designrationale*

---

### Do not duplicate existing CLI/database-driven execution mechanisms

> Assumption is the mother of all fuck-ups. Before taking action, must: (1) Look before you leap - thoroughly examine existing infrastructure (CLI, tables, execution mechanisms), (2) Understand thoroughly - read existing code, patterns, and database schema, (3) Ask when uncertain - do not proceed with

*Category: database_driven_execution | Source: vb_shared.designrationale*

---

### MemUnit deterministic execution path resolution

> System has converged on deterministic execution stack: AST (structural truth extraction), Brackets (semantic contract layer), MemDB (runtime state substrate), Orchestration (dependency resolver), MemUnit (execution authority), Report/Output (verification + surfacing). Key challenge: preserving corre

*Category: architectural_insight | Source: vb_shared.designrationale*

---

### MemUnit deterministic selection for multiple valid candidates

> Domain authority uniqueness is a rule, not a structural guarantee. AST creates multiple candidates (unavoidable in non-trivial systems). Brackets guarantee correctness if selected, not uniqueness of selection. Domain authority reduces the set but does NOT mathematically guarantee a singleton set. Ev

*Category: architectural_insight | Source: vb_shared.designrationale*

---

### MemUnit execution surface

> MemUnit is the central execution authority in VBStyle. All VBStyle code executes only through MemUnit. The execution surface consists of foundational classes: MemUnit (orchestrator), AST (structure discovery), brackets (contract discovery), Config (configuration), Report (reporting), Orch (orchestra

*Category: execution_surface | Source: vb_shared.designrationale*

---

### Methods as self-contained execution units

> Methods are self-describing execution units containing full metadata: brackets (invocation contract), type (execution signature/category), domain/category (semantic grouping), description (intent). This shifts architecture from "class owns methods" to "method is independent unit with class as option

*Category: architectural_insight | Source: vb_shared.designrationale*

---

### rule names no underscores

> Changed rule names from no_underscores, short_names, max_length, bracket_format, no_special_chars to nounderscores, shortnames, maxlength, bracketformat, nospecialchars to remove underscores and be consistent with validation rules.

*Category: field | Source: vb_shared.designrationale*

---

### Schema-Driven Execution Engine Architecture

> CLEAN DEFINITION: A system where the database is not just storage, but the source of truth for code structure, execution rules, and CLI behavior, so that any AI or tool interacting with it can reconstruct behavior from schema + metadata alone. The database defines the program. NOT files define logic

*Category: execution_engine_architecture | Source: vb_shared.designrationale*

---

### Schema-Driven Execution Graph Runtime (SDEGR)

> This is not an OOP system, not MVC, not ECS, not even an AI system. This is a database-compiled execution engine where UI is one queryable projection of a constrained behavioral graph. Core structure: CLASS TABLE is the primary key holding identity, layer, domain, authority level, boot priority, run

*Category: architecture | Source: vb_shared.designrationale*

---

### Terminology Correction: MEMUNIT not MEMUNIT

> On 2026-05-22, AI used incorrect terminology MEMUNIT when referring to the system execution authority. The correct term is MEMUNIT. Evidence: memunit_entry_flag column exists in classes table. MemUnit class exists in classes. MemDB class exists. All stateful classes (Config, Memory, DB, etc.) have m

*Category: lesson | Source: vb_shared.designrationale*

---

### Terminology: Classes and Methods, Not Lib Core Unit

> On 2026-05-25, cleaned up outdated terminology from pre-database architecture. Renamed 48 method entries: register_core to register_class, register_lib to register_method, connect_core to connect_class, connect_lib to connect_method. Removed GUI-related tooltips table and unknown-purpose code_functi

*Category: lesson | Source: vb_shared.designrationale*

---

### token naming no underscores

> Token names must not contain underscores. Changed tokens to follow consistent short format without underscores.

*Category: field | Source: vb_shared.designrationale*

---

## Learned Rules (from vb_shared.learned_rules)

| Pattern | Fix Action | Confidence |
|---------|-----------|------------|
| Pre-Code Reasoning Pipeline: Before writing ANY code for a new VBStyle domain, w | Follow the 8-graph pipeline: 1) plan_graph.py (What are we building?) 2) spec_gr | 1 |
| use dict as core data structures | Follow rule: prohibition | 0.95 |
| generate files outside the vbstyle umbrella | Follow rule: prohibition | 0.95 |
| mix gui logic into unrelated core classes | Follow rule: prohibition | 0.95 |
| own state, only mutate memdb through validated paths | Follow rule: prohibition | 0.95 |
| replace memdb row storage | Follow rule: prohibition | 0.95 |
| become a second memdb | Follow rule: prohibition | 0.95 |
| have core folder structures | Follow rule: prohibition | 0.95 |
| collapse memdb, membus, and memorybus | Follow rule: prohibition | 0.95 |
| consult vbstyle patterns second | Follow rule: requirement | 0.95 |
| use direct core_ imports | Follow rule: prohibition | 0.95 |
| become a second memdb or a second membus | Follow rule: prohibition | 0.95 |
| returns vbstyle dicts | Follow rule: requirement | 0.95 |
| contain underscores - use camelcase or single words | Follow rule: prohibition | 0.95 |
| get to call something maximum if core is broken | Follow rule: prohibition | 0.95 |
| get to call something core if minimum is broken | Follow rule: prohibition | 0.95 |
| token contains underscores | Follow rule: bug | 0.95 |
| use only letters, numbers, and underscores | Follow rule: fix | 0.95 |
| report through vbstylereporter and manage configuration through embedded configm | Follow rule: requirement | 0.95 |
| join scanner thread before db close | Follow rule: fix | 0.95 |
| ingest non-vbstyle code into database | Follow rule: prohibition | 0.95 |
| contain underscores. this is inconsistent | Follow rule: prohibition | 0.95 |
| remove underscores and capitalize words | Follow rule: fix | 0.95 |
| follow vbstyle structure | Follow rule: lesson | 0.95 |
| assumes core_reportconfig_vbs exists | Follow rule: requirement | 0.95 |
| flatten vbstyle into generic software architecture. preserve fixed terms, fixed  | Follow rule: prohibition | 0.95 |
| put using core ast, you understand | Follow rule: prohibition | 0.95 |
| create vbstyle compliant tools | Follow rule: requirement | 0.95 |
| print() directly - use vbstylereporter | Follow rule: prohibition | 0.95 |
| follow your vbstyle strictly enough and cost you a lot to get here. that | Follow rule: prohibition | 0.95 |

---

## MD File References

| Class | MD Files |
|-------|----------|
| AST | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| BootstrapLoader | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| CASOSNode | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| CASOSVerification | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| CommandBus | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md |
| CoreBootV3 | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| CoreState | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| CoreUnit | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| EventBus | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md |
| Executor | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiBus | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiDB | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiDbWriter | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiDecisionEngine | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiDomainRegistry | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| GuiLayoutLaw | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| Hardware | VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| IndexAuthority | VBstyle_Python/Domains/DOM_REGISTRY.md |
| MemBus | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| MemDb | VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| MemUnit | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| MessageBus | VBstyle_Python/Domains/DOM_REGISTRY.md |
| OSLayer | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| Orchestration | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| Report | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| Runtime | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Domains/AI_MIGRATION_INSTRUCTION.md, VBstyle_Python/Domains/DOM_REGISTRY.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| UnifyDomain | VBstyle_Python/Domains/DOM_REGISTRY.md |
| VBAnnotate | VBSTYLE_CORE_ARCHITECTURE.md, VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| VBStyle_AST | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| VBStyle_Brackets | VBstyle_Python/Docs/vbstyle_core_classes_map.md |
| WwsIndexAuthority | VBstyle_Python/Domains/DOM_REGISTRY.md |

---

## Summary

| Metric | Value |
|--------|-------|
| Total classes (all sources) | 153 |
| SQLite classes | 41 |
| MySQL code_classes | 49 |
| MySQL code_registry | 17 |
| vb_code_test classes | 103 |
| on-disk VBSTYLE files | 8 |
| MD file references | 56 |
| design rationale entries | 17 |
| learned rules | 30 |
| Total methods (SQLite) | 401 |
| VBStyle compliant | 6 |
| Has Run() method | 6 |
| Has Tuple3 returns | 6 |

### Classes Needing VBStyle Conversion

| Class | Issue |
|-------|-------|
| **MemUnit** | No Run() method, No Tuple3 returns, No set_config() |
| **MemDb** | No Run() method, No Tuple3 returns |
| **MemBus** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **Executor** | No Run() method, No Tuple3 returns |
| **Orchestration** | No Run() method, No Tuple3 returns |
| **AST** | No Run() method, No Tuple3 returns |
| **ClassAST** | No Run() method, No Tuple3 returns |
| **VBAnnotate** | No Run() method, No Tuple3 returns |
| **Report** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **ErrorHandler** | No Run() method, No Tuple3 returns |
| **ErrorReport** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **Hardware** | No Run() method, No Tuple3 returns |
| **OSLayer** | No Run() method, No Tuple3 returns |
| **ClassOS** | No Run() method, No Tuple3 returns |
| **ClassIndexer** | No Run() method, No Tuple3 returns |
| **IndexAuthority** | No Run() method, No Tuple3 returns |
| **BootstrapLoader** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **RuntimeGuard** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **UnitBase** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **VerificationSuite** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **CoreBootV3** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **CoreUnit** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **CoreState** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **GuiDBActions** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **GuiDbWriter** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **GuiDomainRegistry** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **GuiDecisionEngine** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **GuiLayoutLaw** | No Run() method, No Tuple3 returns, No read_state(), No set_config() |
| **EventBus** | No Run() method, No Tuple3 returns |
| **CommandBus** | No Run() method, No Tuple3 returns |
| **MessageBus** | No Run() method, No Tuple3 returns |
| **DomOrchestration** | No read_state(), No set_config() |
| **DomErrorHandling** | No read_state(), No set_config() |
| **DomMemory** | No read_state(), No set_config() |
| **DomGui** | No read_state(), No set_config() |
| **DomIndex** | No read_state(), No set_config() |
| **DomWwsIndex** | No read_state(), No set_config() |
| **WwsIndexAuthority** | No Run() method, No Tuple3 returns |
| **UnifyDomain** | No Run() method, No Tuple3 returns |
| **SystemDomain** | No Run() method, No Tuple3 returns |
| **Runtime** | No Run() method, No Tuple3 returns, No set_config() |
