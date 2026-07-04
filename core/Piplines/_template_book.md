#[@GHOST]{file_path="core/Piplines/_template_book.md" date="2026-07-03" author="cascade" session_id="pipeline-templates" context="Reusable template for PLF book structure. Each PLF file follows this pattern: index, chapters with mini-indexes, cross-references."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="_template_book.md" domain="pipelines" authority="Cascade"}
#[@SUMMARY]{summary="Book template. Copy this file, rename to PLF_<Name>.md, fill in chapters. Each chapter must have a mini-index."}

---

# PLF_<Name> — <Title>

> **Core thesis:** <One sentence describing what this pipeline does.>
> **Status:** <ACTIVE | DESIGN | ARCHIVE>
> **SQLite backend:** <path or table name, if applicable>

---

# Book Index

| Chapter | Name | Purpose |
|---|---|---|
| 1 | <Name> | <One line> |
| 2 | <Name> | <One line> |
| 3 | <Name> | <One line> |
| 4 | <Name> | <One line> |
| 5 | <Name> | <One line> |

---

## Chapter 1: <Name>

### Chapter Mini-Index
- 1.1 Purpose
- 1.2 Inputs
- 1.3 Core Steps
- 1.4 Internal Breakdown
- 1.5 Edge Cases
- 1.6 Outputs
- 1.7 Cross-References

### 1.1 Purpose
<What this chapter accomplishes within the pipeline.>

### 1.2 Inputs
<What comes in — file types, DB tables, parameters.>

### 1.3 Core Steps
<Numbered list of the main actions.>

### 1.4 Internal Breakdown
<Subsections detailing each step. Use ### 1.4.1, ### 1.4.2, etc.>

### 1.5 Edge Cases
<What can go wrong. How to handle it.>

### 1.6 Outputs
<What comes out — files written, DB rows updated, results returned.>

### 1.7 Cross-References
- **Related books:** PLF_X Chapter Y
- **Glossary terms:** [term1], [term2]
- **SQLite tables:** table_name

---

## Chapter 2: <Name>

### Chapter Mini-Index
- 2.1 Purpose
- 2.2 Inputs
- 2.3 Core Steps
- 2.4 Internal Breakdown
- 2.5 Edge Cases
- 2.6 Outputs
- 2.7 Cross-References

### 2.1 Purpose
...

(Repeat for each chapter)

---

## Pipeline Summary

| Input | Transformation | Output |
|---|---|---|
| <what> | <how> | <result> |

---

## See Also
- `index.md` — Library index
- `glossary.md` — Global glossary
