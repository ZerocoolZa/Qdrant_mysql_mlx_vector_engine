#[@GHOST]{file_path="Dom_DecisionTrees/refactor_investigation_questions.md" date="2026-08-18" author="Devin" session_id="investigation-questions" context="Self-checking investigation questions for DecisionTreeGui refactor — each question forces verification before action"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE BCL-in BCL-out Run dispatch no-print"}
#[@FILEID]{id="refactor_investigation_questions.md" domain="Dom_DecisionTrees" authority="InvestigationCheck"}
#[@SUMMARY]{summary="Investigation questions that force verification — each has a yes/no check, an action if yes, and a next step if no"}
#[@CLASS]{class="InvestigationCheck" domain="Dom_DecisionTrees" authority="single"}
#[@METHOD]{method="Generate" type="investigation"}

# DecisionTreeGui Refactor — Investigation Questions

## How to use these questions
Each question is a **check**. Answer yes or no. The answer determines what I do next.
- **YES** → I found something → I must read/compare/use it before proceeding
- **NO** → I did not find it → I move to the next question
- Every YES answer changes the plan. Every NO answer confirms an assumption.

---

## FILE HISTORY CHECKS

### Q1. Is there an older version of DecisionTreeGui?
**Check:** `ls -la Dom_DecisionTrees/DecisionTreeGui*.py`
- **YES (found older version)** → Read it. Compare what changed between old and v1. The diff tells me what was intentionally added vs what was always there. Do not refactor away something that was deliberately added.
- **NO (only v1 exists)** → v1 is the original. Everything in it is intentional. Proceed with refactor as planned.

### Q2. Is there a v2 or v3 already started?
**Check:** `ls Dom_DecisionTrees/DecisionTreeGui_v*.py Dom_DecisionTrees/app.py Dom_DecisionTrees/canvas.py Dom_DecisionTrees/tree_builder.py`
- **YES (v2 or partial refactor exists)** → Read it. Someone already started this work. Do not redo it — continue from where they left off. Compare their structure to my plan.
- **NO (nothing exists)** → Greenfield refactor. Proceed with my plan.

### Q3. Is there a backup or .bak version?
**Check:** `find Dom_DecisionTrees/ -name "*.bak" -o -name "*.orig" -o -name "*backup*"`
- **YES (backup exists)** → Read it. It may contain code that was removed from v1 for a reason. Do not add that code back.
- **NO (no backups)** → No hidden history. v1 is the only source of truth.

### Q4. Does DecisionTreeGui_v1.py have git history?
**Check:** `git log --oneline --follow Dom_DecisionTrees/DecisionTreeGui_v1.py`
- **YES (has git history)** → Read the commit messages. They tell me WHY changes were made. Each commit is a decision someone made. Do not undo a decision without understanding why it was made.
- **NO (no git history or not tracked)** → No commit history to learn from. v1 is a snapshot with no context.

### Q5. Is there a Config.py already in Dom_DecisionTrees?
**Check:** `ls Dom_DecisionTrees/Config.py Dom_DecisionTrees/config.py`
- **YES (Config.py exists)** → Read it. It may already define constants I was going to create. Use existing names. Do not duplicate.
- **NO (no Config.py)** → I create it fresh. I define the constants.

---

## REFERENCE IMPLEMENTATION CHECKS

### Q6. Does BookSystem have a multi-file PyQt6 structure I should follow?
**Check:** `ls BookSystem/*.py` and read `BookSystem/BookViewer.py` header
- **YES (BookSystem has the pattern)** → Read `BookSystem/app.py`, `BookSystem/Config.py`, `BookSystem/canvas.py` (or equivalent). Copy the file structure and naming convention. This is the template.
- **NO (BookSystem is also single-file)** → No reference implementation exists. I design the structure from scratch using VBStyle rules.

### Q7. Does core/Dom_Gui/ have a GUI base class or pattern?
**Check:** `ls core/Dom_Gui/*.py` and read any app/window class
- **YES (Dom_Gui has a pattern)** → Read it. It may define how PyQt6 classes should be structured (Run dispatch, state dict, etc.). Follow that pattern.
- **NO (Dom_Gui is empty or unrelated)** → No GUI base class. I structure PyQt6 classes myself.

### Q8. Is there another GUI in this workspace that was already refactored to multi-file?
**Check:** `find . -name "app.py" -path "*/Dom_*"` and `find . -name "canvas.py"`
- **YES (found refactored GUI)** → Read it as the template. It shows the proven structure. Match it.
- **NO (no refactored GUI exists)** → This is the first refactor. I set the pattern that future refactors will follow.

### Q9. Does the BCL engine (core/Dom_Bcl/) have a WCL file for this GUI?
**Check:** `find . -name "*.wcl" | grep -i decision` and `find . -name "*.wcl" | grep -i tree`
- **YES (WCL file exists)** → Read it. The GUI may already be partially defined in WCL. I need to integrate with it, not replace it.
- **NO (no WCL file)** → No WCL definition exists. I build the GUI in Python directly.

---

## DATABASE CHECKS

### Q10. Does the SQLite database file already exist?
**Check:** `find Dom_DecisionTrees/ -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3"`
- **YES (DB file exists)** → Check its schema. The tables and columns are the contract. Do not change column names in my queries.
- **NO (no DB file)** → Find where the DB path is configured. The DB may be in a different location. Check Config or v1 code for the path.

### Q11. Does TreeBuilder need to create tables, or do they already exist?
**Check:** Open the DB and run `SELECT name FROM sqlite_master WHERE type='table'`
- **YES (tables exist)** → TreeBuilder only queries. No CREATE TABLE statements needed.
- **NO (tables do not exist)** → TreeBuilder needs a `init_db()` method that creates tables. Add that to the plan.

### Q12. Is there a schema file (.sql) that defines the tables?
**Check:** `find Dom_DecisionTrees/ -name "*.sql"` and `find . -name "*decision*tree*.sql"`
- **YES (schema file exists)** → Read it. It is the source of truth for table structure. TreeBuilder queries must match it exactly.
- **NO (no schema file)** → Schema is defined in v1 code (inline CREATE TABLE). Extract it to a schema file during refactor.

---

## ERROR HANDLER CHECKS

### Q13. Does ErrorHandler already exist and work?
**Check:** `ls core/utility/error_handler.py` and read the class
- **YES (exists)** → Read its Run() dispatch. What commands does it support? ("consume", "silent", "popup", etc.) Use only supported commands.
- **NO (does not exist)** → I need to create it. Add that to the plan. Check if there is a similar error handler elsewhere to copy from.

### Q14. Has ErrorHandler been used in other GUIs already?
**Check:** `grep -rl "ErrorHandler" --include="*.py" | grep -i gui`
- **YES (used in other GUIs)** → Read how they use it. Copy the pattern. Do not invent a new usage pattern.
- **NO (not used in any GUI)** → I am the first to use it in a GUI. I set the pattern. Check if it has been used in non-GUI code for the API.

---

## BCL ENGINE CHECKS

### Q15. Does the BCL engine already have node colors and radius defined?
**Check:** `grep -r "BCL_NODE_COLORS\|NODE_RADIUS" --include="*.py" --include="*.wcl"`
- **YES (already defined somewhere)** → Find where. Import from there. Do not redefine in Config.py.
- **NO (not defined anywhere)** → Define them in Config.py. These are new constants.

### Q16. Does load_bcl_engine() in v1 reference a specific engine path or module?
**Check:** Read `DecisionTreeGui_v1.py` lines around `load_bcl_engine`
- **YES (references specific path/module)** → Note the path. The refactored code must use the same path. Do not change it.
- **NO (uses dynamic discovery)** → Keep the dynamic discovery approach. Do not hardcode a path.

---

## STYLE CHECKS

### Q17. Does BookSystem/Config.py have a STYLESHEET I should reuse?
**Check:** `grep -r "STYLESHEET\|setStyleSheet" BookSystem/`
- **YES (has shared stylesheet)** → Read it. The DecisionTree GUI should use the same theme. Import or copy the stylesheet.
- **NO (no shared stylesheet)** → DecisionTree GUI gets its own stylesheet in Config.py. Define it fresh.

### Q18. Does v1 have hardcoded colors that are NOT in any Config?
**Check:** `grep -E "#[0-9a-fA-F]{6}" DecisionTreeGui_v1.py | head -20`
- **YES (has hardcoded colors)** → Extract all hex colors. Move them to Config.py as named constants. Replace hardcoded values with Config references.
- **NO (no hardcoded colors)** → Colors are already externalized. Nothing to extract.

---

## IMPORT CHECKS

### Q19. Does v1 import anything that is NOT in the standard refactored file list?
**Check:** Read the import section of `DecisionTreeGui_v1.py`
- **YES (has unusual imports)** → Note them. Each import must go to the correct file. An import like `json` goes to tree_builder.py (for parsing). An import like `QtWidgets` goes to app.py and canvas.py.
- **NO (only standard imports)** → Standard PyQt6 + sqlite3 + json + os. Distribute normally.

### Q20. Are there any circular import risks in the planned structure?
**Check:** Draw the import graph: app.py imports canvas.py + tree_builder.py + Config.py. canvas.py imports Config.py. tree_builder.py imports Config.py. Does any file import app.py?
- **YES (circular import detected)** → Restructure. Move the shared thing to Config.py or a new shared module. Circular imports will crash on launch.
- **NO (no circular imports)** → Import graph is clean. Proceed.

---

## SUMMARY TABLE

| Question | What I check | If YES | If NO |
|----------|-------------|--------|-------|
| Q1 | Older version | Read and compare | v1 is original |
| Q2 | v2 already started | Continue from it | Greenfield |
| Q3 | Backup files | Read for removed code | No hidden history |
| Q4 | Git history | Read commit messages | No context |
| Q5 | Config.py exists | Use existing names | Create fresh |
| Q6 | BookSystem pattern | Copy the template | Design from scratch |
| Q7 | Dom_Gui base class | Follow its pattern | No base class |
| Q8 | Other refactored GUI | Match its structure | Set the pattern |
| Q9 | WCL file for this GUI | Integrate with it | Build in Python |
| Q10 | DB file exists | Check schema | Find DB path |
| Q11 | Tables exist | Query only | Add init_db() |
| Q12 | Schema .sql file | Match it exactly | Extract from v1 |
| Q13 | ErrorHandler exists | Use its API | Create it |
| Q14 | ErrorHandler used in GUIs | Copy the pattern | Set the pattern |
| Q15 | Colors already defined | Import them | Define in Config |
| Q16 | Engine path in v1 | Keep same path | Keep dynamic |
| Q17 | Shared stylesheet | Reuse it | Define fresh |
| Q18 | Hardcoded colors | Extract to Config | Already externalized |
| Q19 | Unusual imports | Distribute correctly | Normal distribution |
| Q20 | Circular imports | Restructure | Proceed |

## Rule
**Answer every question before writing any code.**
If I skip a question, I am guessing. If I guess wrong, I refactor the wrong thing.
Every YES answer changes the plan. Every NO answer confirms an assumption.
