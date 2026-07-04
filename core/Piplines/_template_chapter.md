#[@GHOST]{file_path="core/Piplines/_template_chapter.md" date="2026-07-03" author="cascade" session_id="pipeline-templates" context="Reusable template for a single chapter within a PLF book. Each chapter is a self-contained module with its own mini-index."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="_template_chapter.md" domain="pipelines" authority="Cascade"}
#[@SUMMARY]{summary="Chapter template. Each chapter = mini-index + purpose + inputs + steps + breakdown + edge cases + outputs + cross-refs."}

---

## Chapter N: <Name>

### Chapter Mini-Index
- N.1 Purpose
- N.2 Inputs
- N.3 Core Steps
- N.4 Internal Breakdown
- N.5 Edge Cases
- N.6 Outputs
- N.7 Cross-References

---

### N.1 Purpose

<One paragraph: what this chapter accomplishes and why it exists in the pipeline.>

**Question this chapter answers:** <e.g., "How do we get .py files into SQLite?">

---

### N.2 Inputs

| Input | Type | Source | Required |
|---|---|---|---|
| <name> | <file/table/param> | <where from> | <yes/no> |

---

### N.3 Core Steps

1. <Step one — short description>
2. <Step two>
3. <Step three>
4. <Step four>

---

### N.4 Internal Breakdown

#### N.4.1 <Step 1 detail>

<How it works. Code examples if needed. SQL if applicable.>

```sql
-- Example SQL for this step
SELECT body FROM code_units WHERE class_name = 'HardwareDetector';
```

#### N.4.2 <Step 2 detail>

<How it works.>

#### N.4.3 <Step 3 detail>

<How it works.>

---

### N.5 Edge Cases

| Case | What Happens | Recovery |
|---|---|---|
| <case 1> | <description> | <how to handle> |
| <case 2> | <description> | <how to handle> |

---

### N.6 Outputs

| Output | Type | Destination | Format |
|---|---|---|---|
| <name> | <file/row/result> | <where to> | <format> |

---

### N.7 Cross-References

- **Related chapters:** Chapter X (this book), PLF_Y Chapter Z (other book)
- **Glossary terms:** [Method], [Ingest], [Assemble]
- **SQLite tables:** `code_units`, `code_files`
- **Tools used:** `CodeIngester.py`, `VbsScanner`

---

## Chapter Checklist

- [ ] Mini-index present
- [ ] Purpose stated
- [ ] Inputs listed
- [ ] Core steps numbered
- [ ] Internal breakdown has subsections
- [ ] Edge cases covered
- [ ] Outputs defined
- [ ] Cross-references linked
