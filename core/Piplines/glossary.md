#[@GHOST]{file_path="core/Piplines/glossary.md" date="2026-07-03" author="cascade" session_id="pipeline-glossary" context="Global glossary for all pipeline books. Shared vocabulary with cross-references to usage locations."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="glossary.md" domain="pipelines" authority="Cascade"}
#[@SUMMARY]{summary="Global glossary. Every shared term defined once. Each entry links back to books and chapters where it is used. Reverse-linked semantic map."}

---

# Global Glossary

> **Purpose:** Shared vocabulary across all PLF books. Every term defined once, referenced everywhere.
> **Structure:** Term → Definition → Used in (book + chapter) → SQLite mapping (if applicable).

---

## A

### AST
Abstract Syntax Tree. The parsed structure of source code. Each .py file is AST-parsed into classes, methods, and functions.
- **Used in:** Code Ingestion Ch2, BCL Code Graph Ch2, Graph Ingest Spec Ch4
- **SQLite:** `code_units` table (one row per method)

### Assemble
The stage where method bodies are selected from SQLite via `SELECT body FROM ...` and concatenated into a new .py file.
- **Used in:** Code Ingestion Ch4, Graph Ingest Spec Ch7
- **SQLite:** `SELECT` query → file write

---

## B

### BCL
Bracket Command Language. A hierarchical semantic language using `[@CONTAINER]`, `{}`, `()`, and `;` symbols.
- **Used in:** BCL Code Graph Ch1, BCL Template Maker Ch1, BCL Chat Compression Ch1, Context Expansion Ch5
- **SQLite:** `bcl_instructions` table, `bcl_classes`, `bcl_methods`

### BCL Identity
The header block every file carries: `[@GHOST]`, `[@VBSTYLE]`, `[@FILEID]`, `[@SUMMARY]`, `[@CLASS]`, `[@METHOD]`.
- **Used in:** BCL Template Maker Ch3, Context Expansion Ch6, Config Cascade Ch4
- **SQLite:** `bcl_classes` table

### Book
A single PLF_*.md file in the pipelines library. Each book is a self-contained pipeline with chapters.
- **Used in:** Library Index (this glossary's parent)

---

## C

### Chapter
A major section within a PLF book. Each chapter has a mini-index, purpose, inputs, steps, edge cases, outputs, and cross-references.
- **Used in:** All PLF books

### Code Unit
A single method extracted from source code and stored as one row in SQLite. The atomic unit of the code graph.
- **Used in:** Code Ingestion Ch2, Code Graph Ch2, BCL Code Graph Ch3
- **SQLite:** `code_units` table (one row = one method)

### Computational Unit
A tightly coupled group of methods that belong together. Multiple methods can form one CU.
- **Used in:** BCL Code Graph Ch3, Graph Engine Codebase Ch2
- **SQLite:** `bcl_units` table

### Config Cascade
The process of scanning .py files for hardcoded values, extracting them, and generating Config.py files.
- **Used in:** Config Cascade Ch1-Ch7
- **SQLite:** Config.py files (file-based, not SQLite)

---

## D

### Domain
A logical grouping of classes and methods. E.g., "graph_engine", "codefix", "gui".
- **Used in:** Graph Ingest Spec Ch1, Context Expansion Ch5, Dom_Graph Pipeline Ch3
- **SQLite:** `domain` column in classes/methods tables

---

## E

### Edge
A typed relationship between two nodes in a graph. Types: CALLS, CONTAINS, INHERITS, REFERENCES, DEPENDS_ON.
- **Used in:** Code Graph Ch2, BCL Code Graph Ch4, Context Expansion Ch2
- **SQLite:** `code_edges` table, `bcl_edges` table

### Error Capture
The process of catching errors with their cause and solution, storing them for future prevention.
- **Used in:** Error Capture Ch1, CLI Safe Execution Ch4
- **SQLite:** `error_knowledge` table, MySQL `learned_rules`

---

## G

### Glossary
This file. The shared semantic layer linking terms to their usage across all books.
- **Used in:** Library Index

---

## I

### Ingest
The process of reading source files and storing their structure (classes, methods, functions) as rows in SQLite.
- **Used in:** Code Ingestion Ch1, BCL Code Graph Ch2, ChatMover Ch1, Context Expansion Ch1
- **SQLite:** `code_files`, `code_units` tables

---

## L

### Library
The `pipelines/` folder. The global container holding all PLF books, the index, and the glossary.
- **Used in:** Library Index

---

## M

### Method
A single function extracted from source code. The atomic unit of the code graph. One method = one row = one SQL UPDATE.
- **Used in:** Code Ingestion Ch2, VBStyle DB Fix Ch1, BCL Code Graph Ch3
- **SQLite:** `code_units` table, `methods` table, `bcl_methods` table

### Mini-Index
A subsection at the top of each chapter listing its internal sections. Enables navigation within a chapter.
- **Used in:** All PLF books (chapter structure)

---

## N

### Node
A stored unit of knowledge in a graph database. Can represent a class, method, concept, file, or entity.
- **Used in:** Context Expansion Ch1, Code Graph Ch2, Graph Ingest Spec Ch4
- **SQLite:** `nodes` table, `decision_nodes` table

---

## P

### Pipeline
A deterministic transformation flow from input to structured output. Each PLF book describes one pipeline.
- **Used in:** All PLF books, Pipeline Gap Analysis Ch1

### Provenance
A complete record of where every copied file came from. Source path, hash, destination, timestamp.
- **Used in:** Provenance Pipeline Ch4
- **SQLite:** `provenance` table, `file_store` table

---

## S

### SQLite
The embedded file-based database used as the execution backend for most pipelines.
- **Used in:** All PLF books
- **See also:** Database Management book for full catalog

### Sync
The process of comparing file hashes on disk against stored hashes in SQLite to detect drift (files edited outside the pipeline).
- **Used in:** Code Graph Ch1, BCL Code Lifecycle Ch6
- **SQLite:** `code_files.file_hash` column

---

## T

### Tuple3
The VBStyle return format: `(ok, data, error)`. `ok` is 1 or 0. `data` is the result or None. `error` is None or `(code, desc, 0)`.
- **Used in:** VBStyle DB Fix Ch2, all VBStyle-compliant code
- **SQLite:** Not stored — runtime convention

---

## V

### VBStyle
The coding standard: PascalCase classes, UPPERCASE constants, `Run()` dispatch, Tuple3 returns, `self.state` dict, no print, no decorators, no `self._` attributes.
- **Used in:** VBStyle DB Fix Ch1, Config Cascade Ch4, all VBStyle-compliant code
- **SQLite:** `violations` table tracks per-method compliance

### Verify
The stage where assembled code is checked: `py_compile` + VBStyle compliance + functional tests.
- **Used in:** Code Ingestion Ch5, VBStyle DB Fix Ch6, Graph Ingest Spec Ch6
- **SQLite:** `violations` table, `run_metrics` table
