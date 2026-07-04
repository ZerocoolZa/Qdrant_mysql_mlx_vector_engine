# Plan — Dom_qa_engine Question Ingest

> **Folder**: `Dom_qa_engine/`
> **Created**: 2026-06-29
> **Goal**: Build a single SQLite database (`qa_question_kb.db`) in this folder that ingests all Python files from this folder using the BCL object model (BCL header + BCL-IR + graph + VBStyle compliance), and also catalogs all question-generator classes discovered in the CODEBASE MySQL database.

---

## BCL Header Format (as found in local files)

Files use the bracket-inline header style:
```
#[@GHOST]{[@file<GhostQAEngine.py>][@domain<ghost_qa_engine>][@role<configurable_qa_pipeline>][@return<Tuple3>][@auth<cascade>][@date<2026-06-21>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<class>][@return<Tuple3>][@state<config,catalog,results,errors,meta,hardware,models>]}
#[@SPEC]{[@ref<QA_ENGINE_SPEC.md>][@sections<15>][@compliance<full>]}
```

The BCL-IR (Intermediate Representation) is the parsed JSON from these headers:
```json
{
  "file": "GhostQAEngine.py",
  "domain": "ghost_qa_engine",
  "role": "configurable_qa_pipeline",
  "return": "Tuple3",
  "auth": "cascade",
  "date": "2026-06-21",
  "ver": "2.0",
  "vbsty": {"auth": "cascade", "role": "class", "return": "Tuple3", "state": "config,catalog,results,errors,meta,hardware,models"}
}
```

Some files have NO BCL headers (script-style files like `pinnacle_harness.py`, `five_mode_runner.py`, etc.). These get `bcl=NULL`, `bcl_ir=NULL`, `vbstyle=0`.

---

## Schema — 7 Tables

Every entity gets the same four-field treatment: **BCL** (raw header), **BCL-IR** (Intermediate Representation — parsed JSON of the `[@IRNODE]` block), **Graph** (JSON nodes/edges), **VBStyle** (pass/fail + violations list).

### Table 1: files

```sql
CREATE TABLE files (
    file_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT NOT NULL,
    bcl              TEXT,          -- raw BCL header lines (#[@GHOST]... #[@VBSTYLE]... etc)
    bcl_ir          TEXT,          -- JSON: parsed {file, domain, role, auth, date, ver, vbsty:{...}}
    graph            TEXT,          -- JSON: {nodes:[{type:"class",name:"..."}], edges:[{from:"file",to:"class",rel:"contains"}]}
    vbstyle          INTEGER,       -- 1=pass, 0=fail, NULL=no BCL header (script file)
    vbstyle_violations TEXT,        -- JSON: [{rule:"@print(22)",severity:"hard",desc:"..."}, ...]
    line_count       INTEGER,
    content_hash     TEXT,          -- MD5 of source
    ingested_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Table 2: classes

```sql
CREATE TABLE classes (
    class_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id          INTEGER NOT NULL,
    class_name       TEXT NOT NULL,
    bcl              TEXT,          -- raw BCL class header (extracted from file-level [@CLASS] or docstring)
    bcl_ir          TEXT,          -- JSON: {class:"GhostQAEngine", domain:"...", methods:["Run","Ask",...]}
    graph            TEXT,          -- JSON: {nodes:[methods+baseclass], edges:[contains/calls/inherits]}
    vbstyle          INTEGER,       -- 1=pass, 0=fail
    vbstyle_violations TEXT,        -- JSON: list of violations from RuleEngine.EvaluateClass
    base_class       TEXT,
    start_line       INTEGER,
    end_line         INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);
```

### Table 3: methods

```sql
CREATE TABLE methods (
    method_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id         INTEGER NOT NULL,
    file_id          INTEGER NOT NULL,
    method_name      TEXT NOT NULL,
    bcl              TEXT,          -- raw BCL method header (from [@METHOD] line if present)
    bcl_ir          TEXT,          -- JSON: {method:"Run", type:"dispatch", returns:"Tuple3"}
    graph            TEXT,          -- JSON: {nodes:[called_functions], edges:[calls/imports]}
    vbstyle          INTEGER,       -- 1=pass, 0=fail
    vbstyle_violations TEXT,        -- JSON: from RuleEngine.EvaluateMethod
    start_line       INTEGER,
    end_line         INTEGER,
    returns_tuple3   INTEGER,       -- 1=yes, 0=no
    has_run_dispatch INTEGER,       -- 1=yes, 0=no
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);
```

### Table 4: computational_units

```sql
CREATE TABLE computational_units (
    unit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name        TEXT NOT NULL,
    class_id         INTEGER,
    method_id        INTEGER,
    file_id          INTEGER NOT NULL,
    bcl              TEXT,          -- raw BCL header for this CU (composite of class+method BCL)
    bcl_ir          TEXT,          -- JSON: {unit:"GhostQAEngine.Ask", class:"GhostQAEngine", method:"Ask"}
    graph            TEXT,          -- JSON: graph node for this CU
    vbstyle          INTEGER,
    vbstyle_violations TEXT,
    composite_key    TEXT UNIQUE,   -- "file_id:class_name:method_name"
    status           TEXT DEFAULT 'active',
    description      TEXT,
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    FOREIGN KEY (method_id) REFERENCES methods(method_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);
```

### Table 5: question_generators (from CODEBASE MySQL)

```sql
CREATE TABLE question_generators (
    gen_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name       TEXT NOT NULL,
    source_file_id   INTEGER,       -- CODEBASE MySQL file_id
    source_filename  TEXT,
    source_full_path TEXT,
    source_line_count INTEGER,
    tier             TEXT,          -- 'engine'|'node'|'utility'|'test'
    bcl              TEXT,          -- BCL header extracted from source (if any)
    bcl_ir          TEXT,          -- parsed BCL-IR JSON (if BCL headers present)
    vbstyle          INTEGER,       -- 1=pass, 0=fail, NULL=not checked
    vbstyle_violations TEXT,
    source_code      TEXT,          -- full source from CODEBASE (may be large)
    ingested         INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Table 6: question_dimensions

```sql
CREATE TABLE question_dimensions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dimension        TEXT NOT NULL,   -- existence|time|location|identity|causality|composition|relationship|state|evidence|intent|risk|alternatives
    sector           TEXT NOT NULL,   -- physical|digital|historical|... (12 sectors per dimension)
    description      TEXT,
    aspect_template  TEXT,            -- "Is {sector} known?" etc (10 templates, time gets 10 unique)
    question_template TEXT,           -- rendered question string
    UNIQUE(dimension, sector, aspect_template)
);
```

### Table 7: question_categories

```sql
CREATE TABLE question_categories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    category         TEXT UNIQUE NOT NULL,
    description      TEXT
);
```

---

## VBStyle Compliance Rules (from `bcl_config.py` IR_RULES)

The `RuleEngine` in `core/Dom_Bcl/bcl_rules.py` evaluates these rules against feature dicts extracted by `FeatureExtractor`:

### Method-level rules (hard = must pass, soft = warning)

| Rule ID | Severity | Check |
|---|---|---|
| `@print(22)` | hard | `has_print` — no print() in method |
| `@decorators(20)` | hard | `decorator_count > 0` — no @staticmethod/@property/@classmethod |
| `@underscore(19)` | hard | `has_self_underscore` — no self._xxx |
| `@t3(50)` | hard | `return_count > 0 and not returns_tuple3` — all returns must be Tuple3 |
| `@hardcode(24)` | soft | `hardcoded_count > 3` — more than 3 hardcoded literals |
| `@eval(53)` | hard | `has_eval` — no eval()/exec() |
| `@subprocess(55)` | hard | `has_subprocess` — no os.system()/subprocess |
| `@complexity(56)` | soft | `complexity > 10` — cyclomatic complexity |
| `@nesting(57)` | soft | `max_nesting > 4` — nesting depth |

### Class-level rules

| Rule ID | Severity | Check |
|---|---|---|
| `@pascal(38)` | hard | class name must start uppercase |
| `@run(43)` | hard | class must have Run() method |
| `@ctor(40)` | hard | class must have __init__ |
| `@state(41)` | hard | class must use self.state dict |
| `@tabs(25)` | hard | no tabs, spaces only |
| `@upper(39)` | soft | class constants must be UPPERCASE |

### File-level rules

| Rule ID | Severity | Check |
|---|---|---|
| `@whitespace(26)` | soft | no trailing whitespace |
| `@deadimport(58)` | soft | unused imports |

---

## BCL-IR Node Format (from `bcl_serializer.py`)

The `BCLSerializer` produces IR nodes in this format:
```
[@IRNODE]  type=file id=<md5hash> parent=<parent_id>
  #[@FIELD]   file=GhostQAEngine.py
  #[@FIELD]   path=/Users/wws/.../GhostQAEngine.py
  #[@FIELD]   md5=<8char>
  #[@FIELD]   date=2026-06-29
  #[@FIELD]   lines=1661
  #[@FIELD]   imports=8
  #[@FIELD]   doc=Configurable QA pipeline engine...
  #[@FIELD]   standalone_funcs=0
  #[@FIELD]   trailing_ws=False
[@ENDNODE]
```

Node types: `file`, `class`, `method`, `edge`, `inherit`, `violation`, `metric`

The BCL-IR stored in the database is the JSON-parsed version of these fields, not the raw BCL text.

---

## Phase 1: Build `ingest_qa_engine.py`

### Script structure (VBStyle)

```
ingest_qa_engine.py
  class IngestQaEngine:
    __init__(self, mem=None, db=None, param=None)
    Run(self, command, params=None)          # dispatch
    CmdCreateDb(self, params)                 # create all 7 tables
    CmdIngestLocal(self, params)              # ingest Dom_qa_engine/*.py
    CmdCopyCodebase(self, params)             # copy from CODEBASE MySQL
    CmdPopulateDimensions(self, params)       # from question_dimensions.py
    CmdPopulateCategories(self, params)       # from question_store.py
    CmdReport(self, params)                   # summary counts
    _p(self, params, key, default=None)       # helper
    read_state(self, params=None)             # state snapshot
    set_config(self, params)                  # update config
```

### Step 1: Create database
- Create `qa_question_kb.db` in `Dom_qa_engine/`
- Execute all 7 CREATE TABLE statements

### Step 2: Ingest local `.py` files
For each `.py` file in `Dom_qa_engine/` (excluding `ingest_qa_engine.py` itself):
1. Read file content, compute MD5 hash, count lines
2. Extract BCL headers — regex: `^#\[@(GHOST|VBSTYLE|SPEC|FILEID|SUMMARY|CLASS|METHOD)\]{(.*)}$`
3. Parse BCL key-value pairs `[@key<value>]` into JSON dict -> `bcl_ir`
4. Parse with `ast` module:
   - Extract classes (ClassDef) -> with base_class, start_line, end_line
   - Extract methods (FunctionDef inside classes) -> with start_line, end_line
   - Extract standalone functions (FunctionDef at module level)
   - Extract imports (Import/ImportFrom)
5. Build graph JSON: `{nodes:[{type:"class",name:"GhostQAEngine"},...], edges:[{from:"file",to:"GhostQAEngine",rel:"contains"},...]}`
6. Check VBStyle compliance using `FeatureExtractor` + `RuleEngine` from `core/Dom_Bcl/`
7. Insert into `files` table
8. For each class: extract class-level BCL (from [@CLASS] header or docstring), build class graph, check class VBStyle, insert into `classes`
9. For each method: extract method-level BCL (from [@METHOD] header), build method graph, check method VBStyle, insert into `methods`
10. For each class+method pair: create computational unit, insert into `computational_units`

### Step 3: Copy question generators from CODEBASE MySQL
Connect to CODEBASE MySQL (`mysql -u root CODEBASE`) and for each deduplicated question-generator class:
1. `SELECT content FROM python_files WHERE id = <file_id>` — get source code
2. Extract BCL headers from source (same regex as Step 2)
3. Parse BCL-IR
4. Check VBStyle compliance (if BCL headers present)
5. Insert into `question_generators` table with: class_name, source_file_id, source_filename, source_full_path, source_line_count, tier, bcl, bcl_ir, vbstyle, vbstyle_violations, source_code

### Step 4: Populate question dimensions
Import `DIMENSIONS` dict from `core/utility/question_dimensions.py`.
For each dimension (12) x sector (~12) x aspect_template (10, or 10 TIME_ASPECTS for time dimension):
- Render question_template: `aspect.format(sector=sector_desc.rstrip('?')) + f" re {target}"`
- Insert into `question_dimensions`
- Expected: ~1,440 rows

### Step 5: Populate question categories
Import `CATEGORIES` list from `core/utility/question_store.py`.
Insert all 18 categories: existence, time, versions, location, dependencies, authorship, chat_history, database_state, errors, patterns, environment, naming, state, relationships, assumptions, followup_yes, followup_no, meta

### Step 6: Report
Output summary with counts for all 7 tables.

---

## Local Files to Ingest (verified via AST)

| File | Lines | Classes | Functions | Has BCL? |
|---|---|---|---|---|
| `GhostQAEngine.py` | 1,661 | 6 (HardwareDetector, ModelRegistry, VectorBackend, QueryInterpreter, ModeRouter, GhostQAEngine) | 0 | YES (#[@GHOST] + #[@VBSTYLE] + #[@SPEC]) |
| `Config_qa_engine.py` | 275 | 0 | 1 (_LoadConfigDict) | YES (#[@GHOST] + #[@VBSTYLE]) |
| `qa_prototype.py` | 452 | 1 (GhostQA) | 0 | YES (#[@GHOST] + #[@VBSTYLE]) |
| `Rule_Gui.py` | 679 | 2 (EditRuleDialog, RuleTruthGUI) | 0 | NO (plain docstring) |
| `fact_store_mock.py` | 425 | 1 (FactStoreGUI) | 0 | NO (plain docstring) |
| `pinnacle_harness.py` | 826 | 0 | 10 | NO (plain docstring) |
| `qa_test_harness_v2.py` | 688 | 0 | 9 | NO |
| `qa_test_harness.py` | 456 | 0 | 4 | NO |
| `three_experiment_harness.py` | 402 | 0 | 9 | NO |
| `six_mode_runner.py` | 349 | 0 | 4 | NO |
| `five_mode_runner.py` | 279 | 0 | 4 | NO |
| `run_qa_tests.py` | 186 | 0 | 4 | NO |

**Totals**: 12 files, 10 classes, 49 functions, 3 files with BCL headers, 9 script-style files without BCL

**Note**: Script-style files (no classes) still get ingested into `files` table with `bcl=NULL`, `bcl_ir=NULL`, `vbstyle=0`. Their standalone functions are NOT methods (no parent class) so they don't go into `methods` table. They DO get graph nodes for standalone functions.

---

## Question Generators to Copy from CODEBASE (deduplicated, largest version only)

| Class | CODEBASE file_id | Filename | Lines | Tier |
|---|---|---|---|---|
| QuestionEngine | 45914 | dom_knowledge.py | 3,669 | engine |
| InterrogationAuthority | 40817 | migrate_sqlite_to_mysql.py | 1,877 | engine |
| QuestionEngine (Core_QAEngine) | 306719 | Core_QAEngine.py | 1,431 | engine |
| SmartQuestionTackleApp | 320162 | smart_question_tackle_app.py | 1,232 | engine |
| EnhancedQuestionDB | 79993 | enhanced_question_db.py | 1,213 | engine |
| ChatInterrogationEngine | 111583 | chat_interrogation_engine.py | 1,212 | engine |
| DynamicQuestionGenerator | 111583 | chat_interrogation_engine.py | 1,212 | engine |
| CodeQuestionProofEngine | 61275 | Unit_CodeQuestionProofEngine.py | 1,203 | engine |
| QuestioningEngine | 311293 | maxed_thinking_reasoning_engine.py | 1,155 | engine |
| QuestionLogic | 21429 | maximum_freedom_cognitive_model.py | 1,094 | engine |
| ModelQuestionUnit | 52917 | Reg_gui.py | 1,031 | node |
| UncertaintyQueue | 67053 | fv.py | 1,013 | engine |
| DatabaseQuestionEngine | 79945 | question_gui_db.py | 975 | engine |
| BookQuestionGenerator | 324741 | book_question_generator.py | 954 | engine |
| InvestigationQuestion | 313628 | LIB_INVESTIGATOR.py | 931 | node |
| QuestionToLawClosure_V3 | 70516 | Unit_QuestionToLawClosure_V3.py | 793 | engine |
| QuestionWeigherV2 | 60594 | Unit_QuestionWeigherV2.py | 792 | engine |
| QuestionCascadeEngine | 227893 | Not_in Service_MEMBUS_V3.py | 695 | engine |
| QuestionNode | 358066 | Lib_PredictiveWorldModel_chat169_dup2.py | 715 | node |
| QuestionThinkingAI | 223006 | question_thinking_ai_framework.py | 665 | engine |
| RankedQuestion | 74272 | Question_Engine.py | 619 | engine |
| QuestionWeigher | 60602 | Unit_QuestionWeigher.py | 244 | engine |
| L8_QuestionGate | 70024 | Unit_L8_QuestionGate.py | 194 | engine |
| CuriosityEngine | 65436 | Core_CuriosityEngine.py | 104 | engine |
| OpenAIQuestionGenerator | 46640 | openai_question_generator.py | 103 | engine |
| LLMQuestionGenerator | 175627 | llm_generators.py | 98 | engine |
| Cls_QuestionEngine | 220469 | Cls_QuestionEngine.py | 80 | engine |
| Cls_Question | 229451 | Cls_Question.py | 42 | node |
| ComBookQuestionGenerator | 45475 | lib_com_book_question_generator.py | 40 | engine |
| ComVB2010QuestionGenerator | 45258 | lib_com_v_b2010_question_generator.py | 40 | engine |

**Also from current workspace (already on disk):**

| Class | File | Lines | Tier |
|---|---|---|---|
| QuestionAgent | `core/utility/question_agent.py` | 517 | utility |
| QuestionStore | `core/utility/question_store.py` | 380 | utility |
| QuestionDimensions | `core/utility/question_dimensions.py` | 501 | utility |
| CuriosityController | `Dom_Graph/Dom_Graph_EngineV2.py` | 748 | utility |

**Total**: ~34 unique question-generator classes

---

## Execution Order

1. Write `ingest_qa_engine.py` (VBStyle, one class, Run dispatch, Tuple3)
2. Run: `python3 ingest_qa_engine.py`
3. Verify counts:
   - `SELECT COUNT(*) FROM files` -> 12
   - `SELECT COUNT(*) FROM classes` -> 10
   - `SELECT COUNT(*) FROM methods` -> (count from AST)
   - `SELECT COUNT(*) FROM computational_units` -> (count from AST)
   - `SELECT COUNT(*) FROM question_generators` -> ~34
   - `SELECT COUNT(*) FROM question_dimensions` -> ~1,440
   - `SELECT COUNT(*) FROM question_categories` -> 18
4. Query the database for question generators applicable to DecisionTreeGui refactoring

---

## Existing BCL Infrastructure (reuse, don't reinvent)

| Component | Path | Purpose |
|---|---|---|
| `IRCompiler` | `core/Dom_Bcl/bcl_compiler.py` (237 lines) | Compiles Python AST to BCL IR blocks. Uses FeatureExtractor + RuleEngine + BCLSerializer. |
| `FeatureExtractor` | `core/Dom_Bcl/bcl_extractor.py` (395 lines) | Extracts method/class/file features from AST: has_print, decorator_count, has_self_underscore, returns_tuple3, complexity, max_nesting, etc. |
| `BCLSerializer` | `core/Dom_Bcl/bcl_serializer.py` (250 lines) | Serializes AST nodes to BCL IR node format: `[@IRNODE] type=file id=... parent=...` with `#[@FIELD]` entries. |
| `RuleEngine` | `core/Dom_Bcl/bcl_rules.py` (104 lines) | Evaluates `IR_RULES` (17 rules) against feature dicts. Returns violations list. |
| `bcl_config.py` | `core/Dom_Bcl/bcl_config.py` (151 lines) | Defines `IR_RULES` (17 VBStyle rules), `DOMAIN_KEYWORDS` (20 domains), `SYNTAX`, `BCL_FORMS`. |
| `IRExporter` | `core/Dom_Bcl/bcl_exporter.py` | Exports BCL IR to SQLite (`ir_nodes`, `ir_files` tables). |
| `BCLObjectDatabase` | `core/Dom_Bcl/bcl_object_database.py` (1,794 lines) | Full BCL object DB: `code_objects`, `bcl_metadata`, `object_relationships`, `source_versions`, `ir_nodes`, `ir_files`. |
| `IRQuery` | `core/Dom_Bcl/bcl_query.py` | Query BCL IR from SQLite. |
| `IRValidator` | `core/Dom_Bcl/bcl_validator.py` | Validate BCL IR correctness. |

**Import strategy**: Add `core/Dom_Bcl/` to `sys.path`, then:
```python
from bcl_compiler import IRCompiler
from bcl_extractor import FeatureExtractor
from bcl_serializer import BCLSerializer
from bcl_rules import RuleEngine
from bcl_config import IR_RULES
```

**Important**: The BCL infrastructure uses the comment-style BCL headers (`# [@GHOST]{file_path="..."}`) seen in `core/Dom_Bcl/*.py` files, but the `Dom_qa_engine` files use the bracket-inline style (`#[@GHOST]{[@file<...>]}`). The ingest script must handle BOTH formats.

---

## Key Design Decisions

1. **Script-style files** (no classes, just functions) — `pinnacle_harness.py`, `five_mode_runner.py`, etc. — get ingested into `files` with `vbstyle=0` (they have no BCL headers and no class structure). Their functions appear in the file graph but NOT in `methods` (which requires a parent `class_id`).

2. **BCL header extraction** — regex must handle two formats:
   - Bracket-inline: `#[@GHOST]{[@file<value>][@domain<value>]}`
   - Comment-style: `# [@GHOST]{file_path="value" date="value"}`

3. **BCL-IR parsing** — parse `[@key<value>]` pairs from inside `{...}` into a JSON dict. For comment-style, parse `key="value"` pairs.

4. **Graph format** — JSON with `{nodes:[{type, name, line}], edges:[{from, to, rel}]}`. Relationships: `contains` (file->class, class->method), `calls` (method->function), `inherits` (class->baseclass), `imports` (file->module).

5. **Computational units** — one per (class, method) pair. `composite_key = f"{file_id}:{class_name}:{method_name}"`. `unit_name = f"{class_name}.{method_name}"`.

6. **CODEBASE MySQL access** — `mysql -u root CODEBASE` (localhost, no password). Query `python_files.content` (LONGBLOB) for source code. Query `python_class_index` for class->file mapping.

7. **Question dimensions source** — import `DIMENSIONS` dict directly from `core/utility/question_dimensions.py` (12 dimensions, ~144 sectors total, 10 aspect templates each, time gets 10 unique TIME_ASPECTS).

8. **Question categories source** — import `CATEGORIES` list directly from `core/utility/question_store.py` (18 categories).

---

## File Inventory After Completion

| File | Purpose |
|---|---|
| `qa_question_kb.db` | The single SQLite database with all 7 tables |
| `ingest_qa_engine.py` | VBStyle script that built it |
| `PLAN_Question_Ingest.md` | This plan |
| (existing 12 .py files) | Unchanged |

---

# Appendix: Concept Q&A

This section answers every question about the four pillars stored in the database: BCL, BCL-IR, Graph, and VBStyle. The ingest script does not need to implement any of this — it reuses existing infrastructure. But the plan must explain what each pillar IS so that anyone reading the plan understands what they're looking at in the database.

---

## A1. BCL (Bracket Command Language)

### What is BCL?

BCL is a bracket-based metadata and command language used throughout the codebase to annotate, configure, and reason about code. It is NOT JSON. It is NOT YAML. It is its own syntax with containers, tuples, and weights.

### What is the BCL format?

Two forms exist in the codebase:

**Form 1 — Bracket-inline (used in `Dom_qa_engine/` files):**
```
#[@GHOST]{[@file<GhostQAEngine.py>][@domain<ghost_qa_engine>][@role<configurable_qa_pipeline>][@auth<cascade>][@date<2026-06-21>][@ver<2.0>]}
```
- Container: `[@NAME]{...}` — NAME is the dispatch ID, capital first letter
- Key-value inside: `[@key<value>]` — angle brackets, no quotes
- Multiple key-values packed inside braces: `[@key1<val1>][@key2<val2>]`

**Form 2 — Comment-style (used in `core/Dom_Bcl/` files):**
```
# [@GHOST]{file_path="/Users/wws/.../bcl_compiler.py" date="2026-06-27" author="Cascade" session_id="bcl-vbstyle-fix"}
```
- Container: `[@NAME]{...}` — same
- Key-value inside: `key="value"` — equals sign, quoted strings
- Multiple key-values space-separated inside braces

**Form 3 — Tuple form (used in `vb_shared.rule_tokens` table):**
```
[@ConceptName]{("description text";92)}
```
- Tuple: `("value1";"value2";weight)` — semicolons inside parens
- Weight: ALWAYS the last element, integer 0-100
- Nesting: containers hold other containers

### How do you make BCL?

Three ways:

1. **By hand** — Developers (or Cascade) write BCL headers at the top of `.py` files. This is how `GhostQAEngine.py` got its `#[@GHOST]` header. The file header tool (`/Users/wws/Downloads/file_header_preview.py`) can stamp headers via PyQt6 GUI.

2. **By the BCL Template Maker** — The capsule builder (`/Users/wws/Downloads/capsule_builder.py`) stamps headers + builds self-contained archives. Pipeline 9 (BCL Template Maker): Header Editor -> Template -> Stamp -> Capsule -> Verify.

3. **By the IRCompiler** — The `IRCompiler` class in `core/Dom_Bcl/bcl_compiler.py` reads a `.py` file, parses the AST, and generates BCL IR blocks (see BCL-IR section below). This is automated, not hand-written.

### How do you use BCL?

- **File headers** — `#[@GHOST]{...}` at the top of every file identifies the file's domain, role, author, date, version. This is the identity stamp.
- **Rule tokens** — `vb_shared.rule_tokens` table stores 238 BCL tokens like `[@Print]{("no print() in method scope";92)}`. These are the VBStyle rules.
- **Decision trees** — Nested `[@Pass]{(...)}/[@Fail]{(...)}` blocks encode decision logic with weights.
- **Config forms** — `[@bcl-config]{("key";"value")}` describes passive state read by dom_config.
- **Command forms** — `[@bcl-command]{("action";weight)}` executes actions through MemUnit.
- **Reasoning stamps** — AI-generated BCL containers capture gotchas, failure cascades, change impact, and confidence for every method/class. See `[@RollbackEngine]{("method";"RollbackEngine.RollbackTo");("confidence";"0.85")...}`.

### Where is BCL applied?

| Location | Purpose | Example |
|---|---|---|
| File headers (`#[@GHOST]`) | File identity | Every `.py` file in the codebase |
| `vb_shared.rule_tokens` table | VBStyle rules (238 tokens) | `[@Print]{("no print()";92)}` |
| `vb_shared.tokens` table | BCL token definitions | `[@bcl]`, `[@bcl-config]`, `[@bcl-command]` |
| `vb_shared.rules` table | Prose rules (282 rows) | Rule id=24: "Token must be in format [@Token]" |
| BCL reasoning stamps | AI understanding of code | `[@RollbackEngine]{...[@Gotchas]{...}...}` |
| Config files | Domain configuration | `[@bcl-config]{("theme";"dark")}` |
| Decision trees | Pass/Fail/Unsure logic | `[@QuestionWhat]{[@Pass]{(...)}[@Fail]{(...)}}` |

### Who writes BCL headers?

- **Cascade (AI)** — Writes headers when creating new files. Most files in `Dom_qa_engine/` have `[@auth<cascade>]`.
- **Developers** — Can write headers by hand or use the BCL Header Editor GUI (`/Users/wws/Downloads/file_header_preview.py`).
- **The capsule builder** — Automates stamping for batch file creation.

### If there's a problem with BCL, who fixes it?

- **Missing headers** — The ingest script flags files with `bcl=NULL`. A developer or Cascade adds the header.
- **Malformed BCL** — The `IRCompiler` will fail to parse and return an error tuple. The `IRValidator` (`core/Dom_Bcl/bcl_validator.py`) validates BCL IR correctness.
- **Rule violations** — The `RuleEngine` reports violations. The developer fixes the code to comply.
- **Duplicate tokens** — The `RuleEngine` in `Vbs_Code_Verifiation/vbs_rule_engine.py` dedup-gates token creation (dry_run default, commit=True to execute).

---

## A2. BCL-IR (BCL Intermediate Representation)

### What is BCL-IR?

BCL-IR is the structured, machine-readable output of compiling a Python file through the `IRCompiler`. It is NOT the raw BCL header text. It is a normalized representation of the file's AST as `[@IRNODE]` blocks with typed fields.

### How is BCL-IR made?

The pipeline is:

```
Python file -> ast.parse() -> FeatureExtractor -> BCLSerializer -> [@IRNODE] blocks
                                              -> RuleEngine -> violation nodes
```

Step by step (from `bcl_compiler.py` `CompileFile` method):

1. **Read file** — `open(filepath).read()`
2. **Parse AST** — `ast.parse(source, filename=filepath)`
3. **Extract file features** — `FeatureExtractor.Run("extract_file_features", {tree, source})` returns a feature dict with: `line_count`, `import_count`, `module_docstring`, `standalone_function_count`, `standalone_async`, `has_trailing_ws`, `imports`, `dead_imports`
4. **Generate file ID** — `StableId({filepath, "file", filename, 1})` = MD5 hash of `"filepath:file:name:1"` truncated to 12 chars
5. **Evaluate file rules** — `RuleEngine.Run("evaluate_file", {features: ff})` checks `@whitespace(26)`, `@deadimport(58)`
6. **Serialize file node** — `BCLSerializer.Run("serialize_file", {filepath, source, features, file_id})` produces:
   ```
   [@IRNODE]  type=file id=a1b2c3d4e5f6
     #[@FIELD]   file=GhostQAEngine.py
     #[@FIELD]   path=/Users/wws/.../GhostQAEngine.py
     #[@FIELD]   md5=ab12cd34
     #[@FIELD]   date=2026-06-29
     #[@FIELD]   lines=1661
     #[@FIELD]   imports=8
     #[@FIELD]   doc=Configurable QA pipeline engine...
     #[@FIELD]   standalone_funcs=0
     #[@FIELD]   trailing_ws=False
   [@ENDNODE]
   ```
7. **For each class** — `FeatureExtractor.Run("extract_class_features", {node, source_lines})` returns: `class_name`, `lineno`, `methods` (list of method feature dicts), `has_run`, `has_init`, `has_state`, `class_constants`, `has_tabs`, `bases`
8. **Evaluate class rules** — `RuleEngine.Run("evaluate_class", {features: cf})` checks `@pascal(38)`, `@run(43)`, `@ctor(40)`, `@state(41)`, `@tabs(25)`, `@upper(39)`
9. **Serialize class node** — `BCLSerializer.Run("serialize_class", ...)` produces a `[@IRNODE] type=class` block
10. **For each method** — `FeatureExtractor.Run("extract_method_features", {node, class_name})` returns: `name`, `params`, `param_types`, `decorator_count`, `decorator_names`, `return_count`, `returns_tuple3`, `has_print`, `has_eval`, `has_subprocess`, `has_self_underscore`, `calls`, `call_count`, `branch_count`, `loop_count`, `max_nesting`, `complexity`, `hardcoded_count`, `string_constants`, `nested_funcs`, `local_var_count`, `halstead_volume`, `call_sites`
11. **Evaluate method rules** — `RuleEngine.Run("evaluate_method", {features: mf})` checks `@print(22)`, `@decorators(20)`, `@underscore(19)`, `@t3(50)`, `@hardcode(24)`, `@eval(53)`, `@subprocess(55)`, `@complexity(56)`, `@nesting(57)`
12. **Serialize method node** — `BCLSerializer.Run("serialize_method", ...)` produces a `[@IRNODE] type=method` block
13. **Serialize violation nodes** — For each violation, `BCLSerializer.Run("serialize_violation", ...)` produces a `[@IRNODE] type=violation` block
14. **Serialize edge nodes** — For each call site, `BCLSerializer.Run("serialize_edge", ...)` produces a `[@IRNODE] type=edge` block
15. **Serialize inherit nodes** — For each base class, `BCLSerializer.Run("serialize_inherit", ...)` produces a `[@IRNODE] type=inherit` block

### Does AI generate BCL-IR?

**No.** BCL-IR is generated deterministically by the `IRCompiler` using Python's `ast` module. There is no AI involved in generating BCL-IR. The AI writes the BCL headers (the `#[@GHOST]` lines at the top of files), but the IR is a mechanical compilation of the AST.

### What does BCL-IR look like in the database?

In this plan, `bcl_ir` column stores a JSON dict — the parsed fields from the `[@IRNODE]` block. For example, for a file:

```json
{
  "type": "file",
  "id": "a1b2c3d4e5f6",
  "file": "GhostQAEngine.py",
  "path": "/Users/wws/.../GhostQAEngine.py",
  "md5": "ab12cd34",
  "date": "2026-06-29",
  "lines": 1661,
  "imports": 8,
  "doc": "Configurable QA pipeline engine...",
  "standalone_funcs": 0,
  "trailing_ws": false
}
```

For a method:
```json
{
  "type": "method",
  "id": "f7e8d9c0b1a2",
  "parent": "c3d4e5f6a7b8",
  "name": "Run",
  "class": "GhostQAEngine",
  "params": ["command", "params"],
  "returns_tuple3": true,
  "has_print": false,
  "decorator_count": 0,
  "complexity": 8,
  "max_nesting": 3,
  "call_count": 12,
  "calls": ["_p", "CmdAsk", "CmdSearch", "CmdClassify"]
}
```

### Who fixes BCL-IR problems?

- **Parse errors** — If `ast.parse()` fails (syntax error in the Python file), `IRCompiler` returns `(0, None, ("PARSE_ERROR", str(exc), 0))`. The developer fixes the Python syntax.
- **Missing features** — If `FeatureExtractor` doesn't extract a needed field, the extractor code in `core/Dom_Bcl/bcl_extractor.py` must be updated.
- **Serialization errors** — If `BCLSerializer` produces wrong format, the serializer code in `core/Dom_Bcl/bcl_serializer.py` must be fixed.
- **Export errors** — If `IRExporter` fails to write to SQLite, check the export code in `core/Dom_Bcl/bcl_exporter.py`.

All fixes go to the BCL infrastructure files in `core/Dom_Bcl/`, NOT to the ingest script. The ingest script only calls these tools.

### Where is BCL-IR stored?

| Storage | Location | Schema |
|---|---|---|
| `ir_nodes` table | `core/Dom_Bcl/bcl_exporter.py` creates | `(id TEXT, type TEXT, parent TEXT, filepath TEXT, bcl TEXT)` |
| `ir_files` table | Same | `(filepath, file_id, blocks, classes, methods, violations)` |
| `code_objects` table | `core/Dom_Bcl/bcl_object_database.py` creates | `(object_id, object_type, object_name, parent_id, bcl_header, source_code, ...)` |
| `bcl_metadata` table | Same | `(object_id, bcl_type, bcl_domain, bcl_purpose, bcl_role, bcl_owner, bcl_priority, bcl_stage, bcl_state)` |
| This plan's `bcl_ir` column | `qa_question_kb.db` | JSON text in each table's `bcl_ir` column |

---

## A3. Graph (Code Graph)

### What is the code graph?

The code graph is a JSON representation of the structural relationships between code entities in a file. It captures what contains what, what calls what, what inherits from what, and what imports what.

### How is the graph built?

The `IRCompiler.CompileFile` method builds the graph as it walks the AST:

1. **File -> Class edges** (relationship: `contains`) — For each `ast.ClassDef` in `tree.body`, an edge `{from: file_id, to: class_id, rel: "contains"}` is created.
2. **Class -> Method edges** (relationship: `contains`) — For each `ast.FunctionDef` inside a class, an edge `{from: class_id, to: method_id, rel: "contains"}`.
3. **Method -> Function edges** (relationship: `calls`) — For each `ast.Call` inside a method body, an edge `{from: method_id, to: callee_name, rel: "calls"}` with the call line number.
4. **Class -> Base class edges** (relationship: `inherits`) — For each base in `node.bases`, an edge `{from: class_name, to: base_class_name, rel: "inherits"}`.
5. **File -> Module edges** (relationship: `imports`) — For each `ast.Import`/`ast.ImportFrom`, an edge `{from: file_id, to: module_name, rel: "imports"}`.

The `IRCompiler` returns these in the `symbols` field:
```python
result = {
    "symbols": {
        "classes": [{"name": "GhostQAEngine", "id": "c3d4e5f6a7b8", "methods": [...]}],
        "edges": [{"caller_class": "GhostQAEngine", "caller_method": "Run", "callee": "CmdAsk", "method_id": "..."}],
        "imports": ["json", "os", "re", "sys", ...]
    }
}
```

### What does the graph look like in the database?

In this plan, the `graph` column stores JSON:
```json
{
  "nodes": [
    {"type": "file", "name": "GhostQAEngine.py", "id": "a1b2c3d4e5f6"},
    {"type": "class", "name": "GhostQAEngine", "id": "c3d4e5f6a7b8", "line": 731},
    {"type": "class", "name": "HardwareDetector", "id": "d4e5f6a7b8c9", "line": 48},
    {"type": "method", "name": "GhostQAEngine.Run", "id": "f7e8d9c0b1a2", "line": 754},
    {"type": "method", "name": "GhostQAEngine.Ask", "id": "e8d9c0b1a2f3", "line": 800}
  ],
  "edges": [
    {"from": "a1b2c3d4e5f6", "to": "c3d4e5f6a7b8", "rel": "contains"},
    {"from": "c3d4e5f6a7b8", "to": "f7e8d9c0b1a2", "rel": "contains"},
    {"from": "f7e8d9c0b1a2", "to": "CmdAsk", "rel": "calls", "line": 756},
    {"from": "c3d4e5f6a7b8", "to": "object", "rel": "inherits"}
  ]
}
```

### Does AI generate the graph?

**No.** The graph is built deterministically by walking the Python AST. No AI reasoning is involved. The graph captures structural facts (what contains what, what calls what), not semantic facts (why something depends on something).

### Who fixes graph problems?

- **Missing edges** — If a call site is not captured, the `FeatureExtractor.WalkMethodBody` method in `bcl_extractor.py` needs to be updated to handle the missing AST node type.
- **Wrong node types** — If a node is misclassified, the `IRCompiler.CompileFile` method in `bcl_compiler.py` needs to be fixed.
- **Import detection failures** — If imports are not captured, the file feature extraction in `bcl_extractor.py` needs to handle the import form.

### Graph vs. BCL-IR — what's the difference?

| Aspect | BCL-IR | Graph |
|---|---|---|
| What it captures | Features and metadata of a single entity | Relationships between entities |
| Source | `FeatureExtractor` + `BCLSerializer` | `IRCompiler` walking AST edges |
| Format | `[@IRNODE]` blocks with `#[@FIELD]` entries | JSON `{nodes:[], edges:[]}` |
| Scope | One node at a time (file, class, method) | All nodes + edges in a file |
| AI involvement | None — deterministic AST extraction | None — deterministic AST walking |
| Stored as | `bcl_ir` column (JSON of parsed fields) | `graph` column (JSON of nodes/edges) |

---

## A4. VBStyle Compliance

### What is VBStyle?

VBStyle is the coding standard enforced across the codebase. It defines rules for class structure, method signatures, naming conventions, and forbidden patterns. The rules are stored in `vb_shared.rule_tokens` (238 BCL tokens) and codified as executable predicates in `core/Dom_Bcl/bcl_config.py` (`IR_RULES` list).

### How is VBStyle compliance checked?

The `RuleEngine` class in `core/Dom_Bcl/bcl_rules.py` evaluates rules against feature dicts:

1. **Feature extraction** — `FeatureExtractor` walks the AST and produces a feature dict for each method/class/file. For a method, this includes: `has_print`, `decorator_count`, `has_self_underscore`, `returns_tuple3`, `hardcoded_count`, `has_eval`, `has_subprocess`, `complexity`, `max_nesting`, `return_count`, `branch_count`, `loop_count`, `call_count`.
2. **Rule evaluation** — `RuleEngine.EvaluateMethod` iterates `IR_RULES` where `scope == "method"` and calls each rule's `predicate(feature_dict)`. If the predicate returns `True`, a violation is recorded.
3. **Violation output** — Each violation is a dict: `{"rule": "@print(22)", "scope": "method", "method": "Run", "severity": "hard", "description": "Disallow print() in method scope"}`

### What are the 17 VBStyle rules?

See the "VBStyle Compliance Rules" section above for the complete table. Summary:

- **9 method rules**: @print, @decorators, @underscore, @t3, @hardcode, @eval, @subprocess, @complexity, @nesting
- **6 class rules**: @pascal, @run, @ctor, @state, @tabs, @upper
- **2 file rules**: @whitespace, @deadimport

### Does AI check VBStyle?

**No.** VBStyle checking is fully deterministic. The `RuleEngine` applies predicate functions to feature dicts. There is no AI judgment involved. A method either has `print()` or it doesn't. A class either has `Run()` or it doesn't.

### Who fixes VBStyle violations?

- **The developer or Cascade** — When `RuleEngine` reports a violation (e.g., `@print(22)` — method has `print()`), the developer removes the `print()` call.
- **The Fast Method** — For bulk fixes across many files, the SQLite Fast Method (ingest all files into in-memory SQLite, run SQL queries to find violations, generate patches in one script) is used. See `VBSTYLE_LESSONS.md` in `Dom_Graph/` for the 5-iteration cleanup log.
- **The ingest script** — Only REPORTS violations, does NOT fix them. The `vbstyle` column is 0 or 1, and `vbstyle_violations` column lists the specific violations.

### What does VBStyle compliance look like in the database?

```json
// vbstyle = 0 (fail), vbstyle_violations:
[
  {"rule": "@print(22)", "scope": "method", "method": "Run", "severity": "hard", "description": "Disallow print() in method scope"},
  {"rule": "@t3(50)", "scope": "method", "method": "LoadConfig", "severity": "hard", "description": "All methods must return Tuple3"}
]
```

```json
// vbstyle = 1 (pass), vbstyle_violations:
[]
```

```json
// vbstyle = NULL (no BCL header, script file), vbstyle_violations:
NULL
```

---

## A5. How the four pillars relate

```
Python File
    |
    v
ast.parse()
    |
    +--> FeatureExtractor --> feature dict --> RuleEngine --> VBStyle violations
    |                                         |
    |                                         +--> BCLSerializer --> [@IRNODE] violation blocks
    |
    +--> BCLSerializer --> [@IRNODE] file/class/method/edge/inherit blocks --> BCL-IR
    |
    +--> IRCompiler walks AST edges --> symbols{classes, edges, imports} --> Graph JSON
    |
    +--> Regex on first N lines --> #[@GHOST]{[@file<...>]...} --> BCL header text
```

| Pillar | Source | AI? | Format | Column |
|---|---|---|---|---|
| BCL | Human/AI writes headers at top of file | Yes (AI writes headers) | `#[@GHOST]{[@file<...>][@domain<...>]}` | `bcl` (raw text) |
| BCL-IR | `IRCompiler` compiles AST mechanically | No | `[@IRNODE]` blocks -> parsed JSON | `bcl_ir` (JSON) |
| Graph | `IRCompiler` walks AST edges mechanically | No | `{nodes:[], edges:[]}` JSON | `graph` (JSON) |
| VBStyle | `RuleEngine` applies predicates to features | No | `{rule, severity, description}` list | `vbstyle` (int) + `vbstyle_violations` (JSON) |

---

## A6. Computational Units

### What is a computational unit?

A computational unit (CU) is the **addressable intersection of a class and a method**. It represents the smallest executable code object that can be independently referenced, tested, and reasoned about. While a method is a language-level concept (a function inside a class), a CU is a database-level concept (a row with a composite key that uniquely identifies that method in that class in that file).

### Why do computational units exist?

Because the same method name can appear in multiple classes. `Run()` exists in every VBStyle class. `__init__` exists in every class. Without a composite key, you cannot uniquely address "the `Ask` method of `GhostQAEngine` in `GhostQAEngine.py`" vs "the `Ask` method of `GhostQA` in `qa_prototype.py`". The CU table solves this with `composite_key = "file_id:class_name:method_name"`.

### How do computational units differ from methods?

| Aspect | Method (table 3) | Computational Unit (table 4) |
|---|---|---|
| What it represents | A Python function inside a class | An addressable, queryable code object |
| Key | `method_id` (auto-increment) | `composite_key` (file:class:method, UNIQUE) |
| Has BCL/BCL-IR/Graph/VBStyle? | Yes — all four | Yes — all four (inherited/composite) |
| Extra fields | `start_line`, `end_line`, `returns_tuple3`, `has_run_dispatch` | `status`, `description`, `unit_name` |
| Purpose | Structural representation | Semantic/addressable representation |

### What about standalone functions (no class)?

Standalone functions (like `_LoadConfigDict` in `Config_qa_engine.py`) do NOT get a computational unit. CUs require a `class_id` (which can be NULL in the schema, but the ingest script only creates CUs for class+method pairs). Standalone functions appear in the file graph as nodes but not in the `methods` or `computational_units` tables.

### What is the `status` field?

`status` defaults to `'active'`. It can be updated later to `'deprecated'`, `'refactored'`, `'dead'`, etc. This allows tracking the lifecycle of code objects over time without deleting rows.

### What is the `description` field?

A human-readable description of what this CU does. Initially NULL on ingestion. Can be filled later by AI reasoning stamps or manual annotation.

### Does AI generate computational units?

**No.** CUs are created mechanically by the ingest script: for each class, for each method in that class, create a CU row. No AI judgment involved.

---

## A7. Question Generators

### What is a question generator?

A question generator is a Python class that produces questions — either dynamically from schema/data discovery, or from predefined templates, or from AI reasoning. These classes are the "engines" that drive the QA system's ability to ask meaningful questions about code, databases, or problem spaces.

### Why copy them from CODEBASE?

The CODEBASE MySQL database indexes ~389K Python files across the entire codebase. Within it, ~34 unique classes are related to question generation. Copying them into `qa_question_kb.db` creates a single, self-contained knowledge base of all question-generation approaches in one place — queryable without a MySQL connection.

### What is the tier system?

| Tier | Meaning | Count | Example |
|---|---|---|---|
| `engine` | Full question generation engine — produces, ranks, and manages questions | ~25 | `QuestionEngine`, `CuriosityEngine`, `ChatInterrogationEngine` |
| `node` | Question node/unit — represents a single question or question-like object | ~3 | `QuestionNode`, `Cls_Question`, `InvestigationQuestion` |
| `utility` | Utility class supporting question operations (storage, dimensions, agents) | ~4 | `QuestionAgent`, `QuestionStore`, `QuestionDimensions`, `CuriosityController` |
| `test` | Test class for question generation | ~0 | (none found) |

### How were the question generators selected?

Selected by querying the CODEBASE MySQL database for classes whose names contain "Question", "Interrogation", "Curiosity", "Uncertainty", or "Inquiry". Results were deduplicated by class name, keeping only the largest version (most lines) when the same class name appeared in multiple files.

### What do we do with them after ingestion?

The `question_generators` table serves as a **catalog of approaches**. After ingestion, you can:
- Query: `SELECT * FROM question_generators WHERE tier='engine' ORDER BY source_line_count DESC` — find the biggest engines
- Compare BCL/VBStyle compliance across generators
- Read `source_code` to understand different question-generation strategies
- Use as reference when building new question engines

### What is the `ingested` flag?

The `ingested` column (INTEGER DEFAULT 0) tracks whether the generator's source code has been fully processed (BCL extracted, VBStyle checked). Set to 1 after successful processing. Allows partial ingestion and retry.

### How do question generators relate to the local files?

The 4 utility-tier generators (`QuestionAgent`, `QuestionStore`, `QuestionDimensions`, `CuriosityController`) are already on disk in the current workspace. The ~30 engine/node generators come from CODEBASE MySQL. Together, they represent the complete ecosystem of question-generation approaches available to the QA engine.

---

## A8. Question Dimensions

### What are the 12 dimensions?

The 12 dimensions are inquiry axes that cover all possible questions about any subject:

| # | Dimension | Question it asks |
|---|---|---|
| 1 | existence | Does it exist? |
| 2 | time | When? |
| 3 | location | Where? |
| 4 | identity | What is it? |
| 5 | causality | Why did it happen? |
| 6 | composition | What is it made of? |
| 7 | relationship | How does it connect to other things? |
| 8 | state | What condition is it in? |
| 9 | evidence | How do we know? |
| 10 | intent | What is the goal/purpose? |
| 11 | risk | What could go wrong? |
| 12 | alternatives | What else could it be? |

### What are sectors?

Each dimension has ~12 sectors — the domains where the dimension's question can be applied. For example, the `existence` dimension has sectors like: physical (does the file exist on disk?), digital (does the class exist in the database?), historical (did this method exist in a previous version?), conceptual (does this concept exist in the codebase?).

### What are aspect templates?

Each dimension has 10 aspect templates — phrasings that generate questions about that dimension. For example, for `existence`:
- `"Is {sector} known?"`
- `"Is {sector} present?"`
- `"Has {sector} been verified?"`
- `"Does {sector} exist in the codebase?"`
- ... (10 total)

The `time` dimension is special — it gets 10 unique `TIME_ASPECTS` instead of the generic templates, covering: when created, when modified, when accessed, when deprecated, when deleted, frequency, duration, sequence, concurrency, and timing.

### How is a question rendered?

```python
question = aspect_template.format(sector=sector_description.rstrip('?')) + f" re {target}"
```
For example: `aspect_template = "Is {sector} present?"`, `sector = "the database schema"`, `target = "GhostQAEngine"` → `"Is the database schema present re GhostQAEngine?"`

### Why ~1,440 rows?

12 dimensions x ~12 sectors x 10 aspect templates = ~1,440. The exact count varies because the `time` dimension uses 10 unique TIME_ASPECTS instead of the generic 10, and some dimensions have slightly different sector counts.

### Where does the DIMENSIONS dict come from?

From `core/utility/question_dimensions.py` (501 lines). The `QuestionDimensions` class defines `DIMENSIONS` as a class-level dict. The ingest script imports this dict directly:
```python
from question_dimensions import QuestionDimensions
DIMENSIONS = QuestionDimensions.DIMENSIONS
```

### How do dimensions relate to categories?

Dimensions are the **inquiry axes** (how you ask). Categories are the **subject domains** (what you ask about). A question like "Does the database schema exist?" has dimension=`existence` and category=`database_state`. They are orthogonal — any dimension can be applied to any category.

---

## A9. Question Categories

### What are the 18 categories?

| # | Category | What it covers |
|---|---|---|
| 1 | existence | Does a file/class/method exist? |
| 2 | time | When was it created/modified? |
| 3 | versions | What version are we on? |
| 4 | location | Where is it on disk/in the codebase? |
| 5 | dependencies | What does it depend on? |
| 6 | authorship | Who wrote it? |
| 7 | chat_history | What was discussed about it? |
| 8 | database_state | What's in the database? |
| 9 | errors | What errors has it caused? |
| 10 | patterns | What design patterns does it use? |
| 11 | environment | What environment does it run in? |
| 12 | naming | Is the naming correct? |
| 13 | state | What state is it in? |
| 14 | relationships | How does it relate to other objects? |
| 15 | assumptions | What assumptions does it make? |
| 16 | followup_yes | Yes-branch follow-up questions |
| 17 | followup_no | No-branch follow-up questions |
| 18 | meta | Questions about questions |

### Where do the categories come from?

From `core/utility/question_store.py` (380 lines). The `QuestionStore` class defines `CATEGORIES` as a class-level list. The ingest script imports it directly:
```python
from question_store import QuestionStore
CATEGORIES = QuestionStore.CATEGORIES
```

### How do categories relate to question generators?

Question generators produce questions that are tagged with a category. For example, `QuestionAgent._generate_level1()` produces questions with categories like `existence`, `time`, `location`. The `question_categories` table provides the canonical list of valid categories that generators should use.

### Why 18 categories?

These 18 were defined by the `QuestionStore` class as the complete set of inquiry subjects needed for problem-space collapse. They cover the full range from basic existence checks through error analysis to meta-questions about the questioning process itself.

---

## A10. Schema Design

### Why 7 tables?

Because the plan has 7 distinct entity types:
- 4 entity tables (files, classes, methods, computational_units) — each gets BCL/BCL-IR/Graph/VBStyle
- 1 catalog table (question_generators) — external classes from CODEBASE
- 2 reference tables (question_dimensions, question_categories) — lookup data for the QA system

Fewer tables would merge unrelated entities. More tables would over-normalize simple lookup data.

### Why JSON in TEXT columns (bcl_ir, graph, vbstyle_violations)?

Because these fields are **read-once, write-once** — the ingest script writes them, and consumers read them as complete units. Normalizing them into separate tables would add join complexity without query benefit. The JSON is structured and parseable, but rarely queried at the field level. If field-level querying becomes needed, SQLite's `json_extract()` function can access nested fields.

### Why NULL vs 0 for vbstyle?

- `vbstyle = 1` — VBStyle checks ran and all passed
- `vbstyle = 0` — VBStyle checks ran and at least one failed
- `vbstyle = NULL` — No BCL header present, VBStyle checks were NOT run (script-style files)

This three-state design distinguishes "failed compliance" from "not checked". Using 0 for both would conflate script files with non-compliant class files.

### Why composite_key UNIQUE in computational_units?

Because `(file_id, class_name, method_name)` must be unique. If the same class+method appears twice in the same file (shouldn't happen in valid Python, but could in edge cases), the UNIQUE constraint prevents duplicate CUs. It also enables `INSERT OR REPLACE` for re-ingestion without duplicates.

### Why foreign keys?

To enforce referential integrity: every class belongs to a file, every method belongs to a class and a file, every CU belongs to a file (and optionally a class and method). This prevents orphan rows when files are re-ingested.

### Why not normalize the graph into nodes and edges tables?

Because the graph is always read as a complete unit for one entity. You never query "give me all edges of type 'calls' across all files" — you query "give me the graph for GhostQAEngine.py". A JSON blob in one row is faster for this access pattern than joining across `nodes` and `edges` tables.

---

## A11. CODEBASE MySQL

### What is the CODEBASE database?

CODEBASE is a MySQL database that indexes ~389K Python files, ~41K C files, and ~10K Swift files from the entire codebase. It stores file content, class indexes, method indexes, and metadata for cross-codebase search and analysis.

### How big is it?

- ~389K Python files
- ~41K C files
- ~10K Swift files
- Tables: `python_files` (content + metadata), `python_class_index` (class → file mapping), `c_files`, `swift_files`, and others

### What tables does it have?

| Table | Purpose | Key columns |
|---|---|---|
| `python_files` | Full source code of every Python file | `id`, `filename`, `filepath`, `content` (LONGBLOB), `line_count`, `hash` |
| `python_class_index` | Class → file mapping | `class_name`, `file_id`, `start_line`, `end_line` |
| (others) | C files, Swift files, metadata | — |

### How do we connect?

```python
import mysql.connector
conn = mysql.connector.connect(host="localhost", port=3306, user="root", password="", database="CODEBASE")
```
Or via command line: `mysql -u root CODEBASE` (localhost, no password).

### What is python_files.content?

A LONGBLOB column containing the full source code of the Python file. This is what we retrieve for each question generator to extract BCL headers, parse BCL-IR, and check VBStyle compliance.

### Why localhost with no password?

This is a local development machine setup. The MySQL server runs on localhost:3306 with user `root` and no password. This is not a production configuration — it's a single-user development environment.

---

## A12. The Ingest Script

### Why must the ingest script be VBStyle?

Because every Python file in this codebase must follow VBStyle rules. The ingest script is a new file being added to `Dom_qa_engine/`, so it must comply: `Run()` dispatch, Tuple3 returns, `self.state` dict, no print, no decorators, PascalCase class, UPPERCASE constants, BCL headers.

### Why one class with Run() dispatch?

VBStyle mandates a single class per file with a `Run(self, command, params=None)` method that dispatches to internal methods. This is the standard pattern across the entire codebase. It makes the script callable both as a module (`IngestQaEngine().Run("ingest_local", {})`) and from command line.

### Why Tuple3 returns?

Every method must return `(1, data, None)` on success or `(0, None, (code, desc, 0))` on failure. This is the VBStyle error-handling contract. It allows callers to check `result[0]` for success/failure without try/except.

### Can steps run independently?

Yes. Each command in `Run()` is independently callable:
- `Run("create_db", {})` — just create tables
- `Run("ingest_local", {})` — just ingest local files
- `Run("copy_codebase", {})` — just copy from CODEBASE
- `Run("populate_dimensions", {})` — just populate dimensions
- `Run("populate_categories", {})` — just populate categories
- `Run("report", {})` — just print counts

Running `python3 ingest_qa_engine.py` with no args runs all steps in order.

### What if BCL infrastructure imports fail?

If `sys.path` doesn't include `core/Dom_Bcl/` or the BCL modules have import errors, the script should fall back to basic AST-only mode: extract BCL headers with regex, parse AST for structure, and set `vbstyle=NULL` (not checked) instead of failing. The script should log the import failure but continue.

### Is the script idempotent?

Yes. Re-running the script should:
- `DELETE FROM` all tables before re-inserting (or use `INSERT OR REPLACE`)
- Re-create tables with `CREATE TABLE IF NOT EXISTS`
- Re-compute all BCL-IR, graphs, and VBStyle checks from scratch

This allows safe re-runs after fixing bugs or adding new files.

---

## A13. BCL Header Format — Additional Questions

### Why do two BCL header formats exist?

The bracket-inline format (`#[@GHOST]{[@file<...>]}`) was the original format used in domain files (`Dom_qa_engine/`, `Dom_Graph/`, etc.). The comment-style format (`# [@GHOST]{file_path="..."}`) was introduced later when the BCL infrastructure (`core/Dom_Bcl/`) was built, to make headers more readable with key="value" pairs instead of `[@key<value>]` pairs.

### Which format is canonical?

Neither is officially deprecated. The bracket-inline format is more common in domain files. The comment-style format is used in BCL infrastructure files. The ingest script handles both equally.

### Will they be unified?

Not in this plan. Unification would require updating hundreds of existing files. The ingest script's regex handles both formats, so both can coexist.

### What happens when both formats are present in the same file?

The regex `^#\[@(GHOST|VBSTYLE|SPEC|FILEID|SUMMARY|CLASS|METHOD)\]{(.*)}$` matches bracket-inline. A second regex `^# \[@(GHOST|VBSTYLE|...)\]{(.*)}$` (with space after `#`) matches comment-style. The script tries both and merges results.

### What about files with no BCL headers at all?

9 of 12 local files have no BCL headers. These are script-style files (test harnesses, runners). They get:
- `bcl = NULL`
- `bcl_ir = NULL`
- `vbstyle = NULL` (not 0 — NULL means "not checked", 0 means "checked and failed")
- `vbstyle_violations = NULL`
- They DO get a graph (AST structure is still parsed)
- They DO get a file row with `line_count` and `content_hash`

### Should script-style files get BCL headers?

Ideally yes — every file should have identity headers. But that's a separate cleanup task, not part of this ingestion plan. The ingest script handles the current state: some files have headers, some don't.

---

## A14. Local Files — Additional Questions

### Why are 9 of 12 files script-style (no classes)?

The `Dom_qa_engine/` folder contains a mix of:
- **Engine files** (3 files with classes + BCL headers) — `GhostQAEngine.py`, `Config_qa_engine.py`, `qa_prototype.py`
- **Test harnesses and runners** (9 files, script-style) — `pinnacle_harness.py`, `five_mode_runner.py`, `run_qa_tests.py`, etc.

The test harnesses were written as quick scripts to test the QA engine, not as production VBStyle-compliant modules. They contain standalone functions for running tests, collecting metrics, and printing results.

### What happens to their standalone functions?

Standalone functions (49 total across all script files) appear in:
- **File graph** — as nodes with `type: "function"` and the function name
- **NOT in `methods` table** — methods require a `class_id` (foreign key to `classes`)
- **NOT in `computational_units` table** — CUs require a `class_id`

This is a deliberate design choice: standalone functions are structurally different from class methods. They don't have `self`, don't participate in class inheritance, and don't follow the VBStyle Run() dispatch pattern.

### Should standalone functions be in their own table?

Not in this plan. If needed later, a `functions` table could be added with the same BCL/BCL-IR/Graph/VBStyle columns. For now, their existence is captured in the file graph.

### Why is `Rule_Gui.py` in this folder?

`Rule_Gui.py` defines `EditRuleDialog` and `RuleTruthGUI` — a PyQt6 GUI for viewing and classifying VBStyle rules. It's in `Dom_qa_engine/` because it was built as a tool for the QA engine's rule-checking capabilities. It has classes but no BCL headers (uses a plain docstring instead).

---

## A15. Execution Order — Additional Questions

### Why this specific order?

1. **Create DB** first — tables must exist before any inserts
2. **Ingest local files** second — local files are the core content, no external dependencies
3. **Copy CODEBASE** third — requires MySQL connection, may be slower, can fail independently
4. **Populate dimensions** fourth — imports from local Python file, fast
5. **Populate categories** fifth — imports from local Python file, fast
6. **Report** last — counts all tables, verifies everything worked

### Can steps be skipped?

Yes. If you only want local file ingestion without CODEBASE:
```python
engine = IngestQaEngine()
engine.Run("create_db", {})
engine.Run("ingest_local", {})
engine.Run("report", {})
```

### What if a step fails?

Each step returns Tuple3. If a step fails:
- `(0, None, ("ERROR_CODE", "description", 0))` is returned
- The script logs the error and continues to the next step (for the `python3 ingest_qa_engine.py` all-in-one mode)
- Partial results are preserved in the database
- Re-running the failed step alone fixes the gap

### What if the CODEBASE MySQL connection fails?

The script catches the connection error, logs it, and skips the `copy_codebase` step. The `question_generators` table will be empty, but all other tables (files, classes, methods, CUs, dimensions, categories) will still be populated. The script does NOT fail entirely if MySQL is unavailable.

### Is the script idempotent?

Yes. Each step either:
- Uses `CREATE TABLE IF NOT EXISTS` (create_db)
- Uses `DELETE FROM` before inserting (ingest_local, copy_codebase, populate_dimensions, populate_categories)

Re-running the script produces the same result as running it once. No duplicate rows.
