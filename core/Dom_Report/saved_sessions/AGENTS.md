# AGENTS.md — Architectural Rules

## Law 1: One Concept. One Authority. One Table.

Every reusable concept has exactly one authoritative table in `diagnostic_kb`.
Every other table references that authority via PK/FK.
No duplicate lookup tables for the same concept are allowed.

## Law 2: The Entity Is The Thing.

Entity names describe WHAT something is, never HOW it was created or WHO owns it.

- `rule` — not `learned_rule` ("learned" is how it was obtained)
- `fact` — not `incident_fact` ("incident" is who owns it)
- `error` — not `python_error` ("python" is where it came from)

How it was obtained is an attribute (`source_origin`, `discovered_by`, `verified`).
Who owns it is a relationship (`incident_id`, `error_id`, `problem_id`).

### The Complete Sentence

The entity is the thing. The authorities describe the thing. The attributes record its history. Together they tell the whole story.

> "A python exception attribute error named 'AttributeError'. Status: active. Severity: error. Priority: p3."

Each word comes from a different authority table. The entity holds the name and the FKs. No repeated strings.

## Law 3: Tables Store Pieces of Truth. The Story Is Assembled When You Read Them.

No table stores a sentence. No table stores a narrative. Every table stores one piece of truth — one noun, one row at a time.

The story exists only at the moment of reading. It is assembled by following the PK/FK relationships across the entity and authority tables.

- The database stores facts.
- The report stores references (FKs to entities).
- The report engine follows the references and writes the story.

A report does not contain text. A report is the index to the story graph. The report engine walks the graph and reconstructs the narrative.

## Law 4: A Report Is a Container of Relationships.

A report is never 1:1. A report has many errors, many problems, many causes, many fixes, many facts, many answers, many evidence, many rules.

The report table holds only:
- `incident_id` — the root entity (the event this report is about)
- Authority FKs — how the report itself is classified (type, status, severity, etc.)

Everything else is linked via join tables (1:N):

```
report_error       → report has many errors
report_problem     → report has many problems
report_cause       → report has many causes
report_fix         → report has many fixes
report_prevention  → report has many preventions
report_fact        → report has many facts
report_answer      → report has many answers
report_evidence    → report has many evidence
report_rule        → report has many rules
report_question    → report has many questions
```

No comma-separated ID lists. No denormalized arrays. Every link is a row in a join table — queryable, indexable, normalizable.

```
Report #2
 ├── Incident #1    (root)
 ├── Errors (3)     → #21, #40, #43
 ├── Problems (3)   → #1, #3, #5
 ├── Causes (5)     → #1, #2, #3, #5, #6
 ├── Fixes (5)      → #1, #2, #3, #5, #6
 ├── Preventions (5)→ #1, #2, #3, #5, #6
 ├── Facts (10)     → #1-6, #13-16
 ├── Answers (15)   → #1-9, #29-34
 ├── Evidence (5)   → #1-5
 └── Rules (3)      → #7, #8, #10
```

55 pieces. 0 stored as text. The entities contain the facts. The authorities provide the vocabulary. When resolved together, they produce the complete story.

### The 7 Authority Tables

| Authority | Table | Entries | Answers |
|---|---|---|---|
| Type | `type` | 118 | "What kind of thing is this?" |
| Category | `category` | 257 | "What family does it belong to?" |
| Domain | `domain` | 234 | "Which area of the system?" |
| Status | `status` | 21 | "What state is it in?" |
| Severity | `severity` | 12 | "How bad is it?" |
| Priority | `priority` | 5 | "How urgent is it?" |
| Group | `group` | 15 | "Which logical collection?" |

### The Rule

Before adding a lookup table, ask: "Do we already have an authority for this concept?"

- If yes, reuse it (FK to the authority).
- If no, create one authoritative table that the entire system will share.

### No `kind` Column

Authority tables do NOT have a `kind` column. Each entry has one universal meaning.

- "Failed" means "Failed" — whether it's an incident, a fix, or a test.
- "Critical" means "Critical" — whether it's an incident, a problem, or a lesson.
- "Database" means "Database" — whether it's a question category, a rule category, or a file category.

The entity provides the context, not the authority. An incident with `status_id` pointing to "fail" means the incident failed. A fix with `status_id` pointing to "fail" means the fix failed. The status is the same — the entity tells you what failed.

### Forbidden Patterns

- `question_type` table → use `type` FK
- `file_type` table → use `type` FK
- `error_type` table → use `type` FK
- `report_status` column with enum → use `status` FK
- `kind` column in any authority table → removed, entity provides context

### Two-Layer Architecture

```
Layer 1: Authorities (7 tables) — the dictionary
    ↑ FK
Layer 2: Entities (10+ tables) — the books that use the dictionary
```

Entities: question, error, incident, answer, cause, fix, prevention, problem, rule, fact, evidence, report

Each entity has `_id` FK columns (type_id, status_id, severity_id, priority_id, domain_id, category_id, group_id) pointing to the authority tables. No entity has its own lookup table.

The `report` entity is the root node — the index to the story graph. It stores FK references to other entities, not text. Join tables (report_fact, report_answer, report_evidence, report_rule, report_question) connect the report to its 1:N relationships.

## Law 5: Context Gives Meaning.

The container provides the context. The array provides the members. The values have no meaning until you know which container they're inside.

This is the same principle at every level of the architecture:

| Level | Where meaning lives | Where values live |
|---|---|---|
| Database authority | `type` table (one row = one type) | Entity FK references it |
| Database entity | `error` table (one row = one error) | Report join table references it |
| BCL container | `[@ERRORS]` (name = the concept) | `(21;40;43)` array holds members |
| BCL field | `[@VAR]{("name";"a")}` (key = the meaning) | `"a"` is the value |

At every level: **store the meaning once, reference it everywhere else.**

- In the database: `type(id=5, name='attribute')` — store "attribute" once, every error references type_id=5
- In BCL: `[@ERRORS]` — say "errors" once, every ID inside is an error by context

Never write:
- `error_type='attribute'` on every row (repeated string)
- `("error";91)("error";94)` in every tuple (repeated word)

The context carries the meaning. The value is just a member.

### The Universal Principle

All five laws are the same law, expressed at different levels:

- Laws 1-2 govern the database (authorities and entities)
- Laws 3-4 govern the relationship between database and report (pieces and containers)
- Law 5 governs BCL (context and arrays)

**Store the meaning once. Reference it everywhere else.**

## BCL — Bracket Command Language

### The 4 Symbols

BCL is a hierarchical semantic language where every bracket has a structural role:

| Symbol | Name | Role |
|---|---|---|
| `[@NAME]` | Container | The thing that owns everything inside it. A report, a window, a folder, an equation. Can contain more containers (recursion). |
| `{}` | Hands | Gathers related records together. Like hands holding a set of pots. |
| `()` | Array | A variable-length ordered array of values. Not a fixed-length tuple. Can hold 1, 3, or 100 items. The parser reads until `)`. |
| `;` | Separator | Separates items within an array. |

### Hierarchy

```
Container → Hands → Arrays → Values
Container → Container → Container → ... (recursive)
```

### Variable-Length Arrays

`()` is NOT a tuple with predefined fields. It is a variable-length ordered array.

```
(91)                          — 1 item
(91;94;97)                    — 3 items
(91;94;97;102;145;201)        — 6 items
```

The parser doesn't care about length. It reads until `)`.

### No Repeated Meaning

If you're inside `[@ERRORS]`, everything inside is an error. Don't repeat the concept inside the concept.

**Wrong** (repeated "id" key):
```
[@ERRORS]
{
    ("id";91)
    ("id";94)
    ("id";97)
}
```

**Right** (context carries meaning):
```
[@ERRORS]
{
    (91;94;97)
}
```

### The Three-Layer Pipeline

```
Layer 1: Database     → stores canonical truth (32 tables)
Layer 2: BCL packet   → transports references (IDs only, no data)
Layer 3: Report engine → resolves references into story
```

Each layer has one responsibility:
- **Database**: store the pieces
- **BCL packet**: carry the references
- **Report engine**: assemble the story

None of them duplicate the role of the others.

### BCL Is a Transport Packet, Not a Report

`[@REPORT]` is just one use of BCL. The same grammar works for any domain:

| Domain | Container | Proven |
|---|---|---|
| Report | `[@REPORT]` | Yes — 54 references, 534 bytes |
| Math | `[@EQUATION]` | Yes — quadratic formula |
| Tree | `[@NODE]` | Yes — 4-level recursion |
| Filesystem | `[@FOLDER]` | Yes — nested folders/files |
| GUI | `[@WINDOW]` | Yes — toolbar/menu/panel |
| Knowledge | `[@KNOWLEDGE]` | Yes — problem/cause/fix |
| Config | `[@CONFIG]` | Yes — database/logging/bcl |

7/7 domains pass with the same `BCLParser`. Zero domain-specific logic.

### BCL Files

- `core/Dom_Bcl/bcl_lexer.py` — tokenizer (character-level, no regex)
- `core/Dom_Bcl/bcl_parser.py` — recursive descent parser (AST out)
- `core/Dom_Bcl/bcl_serializer.py` — AST → BCL text
- `core/Dom_Bcl/bcl_engine.py` — orchestrator (LEX → PARSE → VALIDATE → FIX → SERIALIZE)
- `core/Dom_Bcl/BclReportPacket.py` — generate/resolve [@REPORT] packets
- `core/Dom_Bcl/demo_bcl_stress.py` — 7-domain stress suite
- `core/Dom_Bcl/demo_bcl_report.py` — three-layer pipeline demo
- `core/Dom_Bcl_C_ver/` — C engine (parser, graph builder, static analyzer)

## Diagnostic KB Schema

Database: `diagnostic_kb` (MySQL, localhost, root, no password)

### Architecture Governance — What AI Must Always Know

Four tables govern the architecture. Each table has one responsibility:

| Table | Responsibility | Rows |
|---|---|---|
| `law` | Architectural truths (permanent principles) | 6 |
| `pattern` | Forbidden/recommended implementation patterns | 14 |
| `pattern_law` | Which laws each pattern violates or satisfies | 14 |
| `decision` | Records of why a design choice was made | 4 |

**One table, one thing.** A law is a law. A pattern is a pattern. A decision is a decision. No table carries multiple responsibilities.

All four tables use authority FKs (domain_id, category_id, status_id, priority_id) — they obey the same architecture they govern.

#### The 7 Laws

```sql
SELECT law_code, law_name, d.name as domain, s.name as status
FROM law l
LEFT JOIN domain d ON l.domain_id=d.id
LEFT JOIN status s ON l.status_id=s.id
ORDER BY l.law_code;
```

| Code | Name | Domain | Status |
|---|---|---|---|
| LAW1 | One Concept. One Authority. One Table. | database | locked |
| LAW2 | The Entity Is The Thing. | database | locked |
| LAW3 | Tables Store Pieces. The Story Is Assembled When You Read Them. | database | locked |
| LAW4 | A Report Is a Container of Relationships. | database | locked |
| LAW5 | Context Gives Meaning. | bcl | locked |
| LAW6 | Never Create a Specialized Version of a Universal Concept. | universal | locked |
| PRINCIPLE | Store Meaning Once. Reference It Everywhere Else. | universal | locked |

**LAW6 in detail:**

If a concept already has a name and an authority table, use that name and that table. Do not invent `ErrorType`, `MethodType`, `RepresentationType`, `FoundationLaw`, `LearnedRule`, or `IncidentFact`. The table tells you what the row represents. The Type tells you its classification. Context comes from relationships, not from the name.

- One table = one concept.
- One authority = one vocabulary.
- One column name = one meaning.
- Context comes from relationships, not from inventing new names.

#### The 16 Patterns (VBPACK Forbidden + Architecture)

```sql
SELECT pattern_code, pattern_name, d.name as domain, c.name as category
FROM pattern p
LEFT JOIN domain d ON p.domain_id=d.id
LEFT JOIN category c ON p.category_id=c.id
ORDER BY p.pattern_code;
```

| Code | Name | Domain | Category |
|---|---|---|---|
| DEC | No Decorators | vbstyle | forbidden |
| DTC | No Direct Type Check | vbstyle | forbidden |
| ENU | No Enums | vbstyle | forbidden |
| FMN | No Fake Manager | vbstyle | forbidden |
| FWB | No Forbidden Write Back | vbstyle | forbidden |
| GHOST | Ghost Header Required | code | forbidden |
| HUD | No Hidden Behavior | vbstyle | forbidden |
| IAO | No Implicit Auto Ops | vbstyle | forbidden |
| NHB | No Hidden Behavior (locked) | vbstyle | forbidden |
| NHUS | No Hidden Underscore State | code | forbidden |
| PRT | No Print Statements | vbstyle | forbidden |
| TUPLE3 | Tuple3 Return Required | code | forbidden |
| VBSTYLE | VBStyle Header Required | code | forbidden |
| VFP | No Visible Function Print | vbstyle | forbidden |
| SVU | No Specialized Version of Universal | architecture | forbidden |
| NCC | No Compound Concept Names | architecture | forbidden |

#### The Reasoning Graph (pattern_law)

This is the key table. It lets AI reason:

```
"I'm about to use a decorator"
    → DEC is a forbidden pattern
    → DEC violates LAW5 (Context Gives Meaning)
    → Choose another implementation
```

```sql
-- AI reasoning query: what law does a pattern violate?
SELECT p.pattern_code, pl.relationship, l.law_code, l.law_name, pl.note
FROM pattern p
JOIN pattern_law pl ON p.id=pl.pattern_id
JOIN law l ON pl.law_id=l.id
WHERE p.pattern_code='DEC';
```

Full reasoning graph:

| Pattern | Violates | Law | Reasoning |
|---|---|---|---|
| ENU | violates | LAW1 | Enums embed meaning in column type instead of authority table FK |
| SVU | violates | LAW1 | ErrorType, MethodType, etc. are duplicate authority tables for the same concept: Type |
| FMN | violates | LAW2 | Fake manager — name describes WHO, not WHAT |
| FWB | violates | LAW3 | Write back — data flows backward, not assembled when read |
| PRT | violates | LAW3 | Print bypasses report engine, outputs outside the graph |
| TUPLE3 | violates | LAW3 | Non-Tuple3 returns break the report engine |
| VFP | violates | LAW3 | Visible print bypasses report engine |
| DEC | violates | LAW5 | Decorators hide behavior, not visible in dispatch chain |
| DTC | violates | LAW5 | Direct type check embeds meaning in code instead of context |
| GHOST | violates | LAW5 | No identity — meaning not stored once |
| HUD | violates | LAW5 | Hidden behavior — meaning not visible in context |
| IAO | violates | LAW5 | Implicit ops — meaning not in the container |
| NHB | violates | LAW5 | Hidden behavior — locked version of HUD |
| NHUS | violates | LAW5 | Hidden state — meaning not in the container |
| SVU | violates | LAW5 | Specialized names try to provide context through the name instead of through the container |
| VBSTYLE | violates | LAW5 | No identity — meaning not stored once |
| NCC | violates | LAW6 | Compound names encode context into the name instead of using relationships |
| SVU | violates | LAW6 | Specialized versions fragment vocabulary into incompatible mini-authorities |

#### The 5 Decisions

```sql
SELECT decision_code, decision_name, rationale FROM decision ORDER BY decision_code;
```

| Code | Decision |
|---|---|
| DEC001 | Use authority FKs instead of ENUM columns |
| DEC002 | Use join tables instead of 1:1 FK columns in report |
| DEC003 | Use variable-length arrays in BCL packets |
| DEC004 | Split foundation_law into law, pattern, pattern_law, decision |
| DEC005 | Use Type not MethodType, ClassType, ErrorType |

### Self-Describing Schema — The Database Describes Itself

Four meta-tables make the schema discoverable by both humans and AI. Each has one responsibility:

| Table | Responsibility | Rows |
|---|---|---|
| `table_registry` | One row per table — what the table is | 41 |
| `table_column` | One row per column — what each column means | 332 |
| `table_relationship` | One row per FK — how tables connect | 103 |
| `table_rule` | Which laws/patterns apply to which table | 55 |

**AI can ask the database about itself:**

```sql
-- What is the purpose of the error table?
SELECT purpose FROM table_registry WHERE table_name='error';

-- Which columns are mandatory in the error table?
SELECT column_name FROM table_column tc
JOIN table_registry tr ON tc.table_id=tr.id
WHERE tr.table_name='error' AND is_nullable=0;

-- Which authority FKs does the error table have?
SELECT tc.column_name, auth.table_name as authority, tc.is_nullable
FROM table_column tc
JOIN table_registry tr ON tc.table_id=tr.id
LEFT JOIN table_registry auth ON tc.authority_table_id=auth.id
WHERE tr.table_name='error' AND tc.is_completeness=1;

-- Which laws apply to the error table?
SELECT l.law_code, l.law_name, trule.rule_text
FROM table_rule trule
JOIN table_registry tr ON trule.table_id=tr.id
JOIN law l ON trule.law_id=l.id
WHERE tr.table_name='error';

-- What tables reference the error table?
SELECT child.table_name, tr.fk_column, tr.relationship_type
FROM table_relationship tr
JOIN table_registry parent ON tr.parent_table_id=parent.id
JOIN table_registry child ON tr.child_table_id=child.id
WHERE parent.table_name='error';

-- Which tables still have ENUM columns (violate ENU pattern)?
SELECT DISTINCT tr.table_name, tc.column_name
FROM table_column tc
JOIN table_registry tr ON tc.table_id=tr.id
WHERE tc.data_type='enum';

-- Which authority FKs are nullable (no completeness enforcement)?
SELECT tr.table_name, tc.column_name, auth.table_name as authority
FROM table_column tc
JOIN table_registry tr ON tc.table_id=tr.id
LEFT JOIN table_registry auth ON tc.authority_table_id=auth.id
WHERE tc.is_completeness=1 AND tc.is_nullable=1;
```

The `is_completeness` flag on `table_column` marks which columns are authority FKs that should be part of a completeness contract. Currently all 61 authority FKs are nullable — the database models the architecture but does not enforce it.

45 tables total:
- 7 authority tables (type, category, domain, status, severity, priority, group)
- 15 entity tables (error, question, answer, incident, cause, fix, prevention, problem, rule, fact, evidence, report, Method, ComputationUnit, Class)
- 12 join tables (report_error, report_problem, report_cause, report_fix, report_prevention, report_fact, report_answer, report_evidence, report_rule, report_question, ComputationUnitMethod, ClassComputationUnit)
- 4 governance tables (law, pattern, pattern_law, decision)
- 4 meta tables (table_registry, table_column, table_relationship, table_rule — self-describing schema)
- 2 legacy join tables (incident_problem, problem_solution)
- 1 legacy table (question_type — to be dropped)
- 1 deprecated table (foundation_law — to be dropped, replaced by law/pattern/pattern_law/decision)

### Code Structure — Method, ComputationUnit, Class

Three entities, each with its own table. Each is a separate noun. A class is not a special method. A computation unit is not a special class.

**Composition chain:** Class → ComputationUnit → Method

**Naming convention:** PascalCase, no underscores. Authority FKs are `Type`, `Category`, `Domain`, `Status`, `Priority`, `Severity`, `Group` — never specialized versions like `MethodType` or `ClassType`.

**Each entity has five representations:**

| Representation | Meaning |
|---|---|
| Code | Source code (Python, C, VB6, etc.) |
| BCL | Bracket Command Language representation |
| BCLIR | BCL Intermediate Representation |
| Graph | Dependency/call graph |
| Description | Human explanation |

**Tables:**

| Table | Type | Purpose |
|---|---|---|
| Method | entity | Smallest executable unit — has Code, BCL, BCLIR, Graph, Description |
| ComputationUnit | entity | Composition of methods — joined via ComputationUnitMethod |
| Class | entity | Composition of computation units — joined via ClassComputationUnit |
| ComputationUnitMethod | junction | M:N between ComputationUnit and Method (Sequence, Role) |
| ClassComputationUnit | junction | M:N between Class and ComputationUnit (Sequence) |

**The database stores truth. BCL transports it. The report engine produces the story.**

```
Database → Entity → BCL → BCLIR → Graph → Renderer → Report
```

Every stage is another representation of the same truth. The entity doesn't change. Only the representation changes.

### Incident-Centered Design

The `incident` table is the anchor. Everything else hangs off it:
- `incident_fact` — facts emitted during execution
- `answer` — answers to the 19 diagnostic questions
- `cause` — causes identified
- `fix` — fixes attempted
- `prevention` — prevention rules derived
- `evidence` — supporting data

### Migration Phases

| Phase | Concept | Status |
|---|---|---|
| Phase 1 | Questions | Done — 150,452 migrated, deduplicated, typed, categorized |
| Phase 2 | Answers | Pending |
| Phase 3 | Problems | Pending |
| Phase 4 | Causes | Pending |
| Phase 5 | Solutions | Pending |
| Phase 6 | Fixes | Pending |
| Phase 7 | Prevention | Pending |
| Phase 8 | Links | Pending |
