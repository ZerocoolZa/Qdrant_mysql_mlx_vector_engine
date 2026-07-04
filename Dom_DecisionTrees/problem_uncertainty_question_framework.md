#[@GHOST]{file_path="Dom_DecisionTrees/problem_uncertainty_question_framework.md" date="2026-08-18" author="Devin" session_id="question-framework" context="Systematic framework for generating questions that narrow uncertainty around any problem — every category, every angle"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE BCL-in BCL-out Run dispatch no-print"}
#[@FILEID]{id="problem_uncertainty_question_framework.md" domain="Dom_DecisionTrees" authority="QuestionFramework"}
#[@SUMMARY]{summary="Comprehensive question-generation framework — 15 categories, 200+ question templates that can be thrown at any problem to collapse uncertainty"}
#[@CLASS]{class="QuestionFramework" domain="Dom_DecisionTrees" authority="single"}
#[@METHOD]{method="Generate" type="framework"}

# Problem Uncertainty Question Framework

## Purpose
Every problem has a cloud of uncertainty around it. Each question collapses part of that cloud.
This framework generates questions systematically — by category, by angle, by depth.
The goal: leave no assumption unchecked, no source unverified, no path unexplored.

## How to use
1. Identify the problem
2. Walk through each category
3. Ask every question in the category
4. Each YES answer → investigate (read, check, verify)
5. Each NO answer → assumption confirmed, move on
6. After all categories → uncertainty is collapsed to its minimum

---

## CATEGORY 1: EXISTENCE (does it exist?)

### 1.1 Does the file exist right now?
- Check: `ls -la <path>`
- YES → read it, it is real
- NO → it was deleted, moved, or never existed

### 1.2 Did it ever exist?
- Check: git log, backups, .Trash, time machine
- YES → find where it went
- NO → it was never created, the memory is wrong

### 1.3 Does a version of it exist elsewhere?
- Check: `find / -name "<filename>" 2>/dev/null`
- YES → compare versions, one may be newer or older
- NO → only one copy exists

### 1.4 Does a similar file exist with a different name?
- Check: `find . -name "*<keyword>*"`
- YES → it may have been renamed, read it
- NO → no similar files

### 1.5 Does a partial version exist?
- Check: `find . -name "*<keyword>*.bak" -o -name "*<keyword>*.tmp" -o -name "*<keyword>*.draft"`
- YES → someone started but did not finish, read the partial
- NO → no partial versions

### 1.6 Does the opposite/inverse exist?
- Check: if looking for a builder, is there a destroyer? if looking for a reader, is there a writer?
- YES → the pair may define the contract, read both
- NO → only one direction exists

### 1.7 Does a test for it exist?
- Check: `find . -name "test_*<keyword>*" -o -name "*<keyword>*_test*"`
- YES → the test defines expected behavior, read it
- NO → no tests, behavior is undefined

### 1.8 Does documentation for it exist?
- Check: `grep -rl "<keyword>" --include="*.md"`
- YES → read the docs, they may answer other questions
- NO → no documentation, code is the only source of truth

### 1.9 Does a configuration for it exist?
- Check: `grep -rl "<keyword>" --include="*.json" --include="*.yaml" --include="*.ini" --include="*.cfg"`
- YES → read the config, it defines parameters
- NO → no config, uses defaults or hardcoded values

### 1.10 Does a reference to it exist in other files?
- Check: `grep -rl "<filename>" .`
- YES → those files depend on it, read how they use it
- NO → nothing references it, it is standalone

---

## CATEGORY 2: TIME (when?)

### 2.1 When was it created?
- Check: `stat -f "%SB" <file>` (birth time)
- YES → narrows to sessions active at that time
- NO → no birth time, use modification time

### 2.2 When was it last modified?
- Check: `stat -f "%Sm" <file>`
- YES → narrows to sessions active at that time
- NO → no modification time recorded

### 2.3 Was it modified multiple times?
- Check: `git log --follow <file>` or `stat` timestamps
- YES → each modification is a separate event, find each one
- NO → created once, never touched

### 2.4 Was it created before or after a known event?
- Check: compare timestamp to known events (other file creations, chat exports, etc.)
- YES → narrows the window
- NO → no reference events to compare

### 2.5 Was it created in the same session as another known file?
- Check: compare birth times of files in the same directory
- YES → same session, same chat, search for the other file's chat
- NO → different sessions

### 2.6 Has it been stable or actively changing?
- Check: `git log --oneline --follow <file> | wc -l`
- YES (many commits) → actively changing, recent commits are most relevant
- NO (few commits) → stable, original creation is most relevant

### 2.7 Is there a time gap between creation and first use?
- Check: compare creation time to first reference in other files
- YES → it sat unused for a period, why?
- NO → used immediately after creation

### 2.8 Was it created on a weekend or weekday?
- Check: `date -j -f "%s" <timestamp> "+%A"`
- YES → narrows to personal vs work sessions
- NO → does not help narrow

### 2.9 Was it created during a known work session?
- Check: compare to session timestamps in devin_sessions or .pb files
- YES → found the session
- NO → no matching session, may be from another tool

### 2.10 Is the timestamp reliable?
- Check: was the file copied? `cp` preserves mtime but not birth time
- YES → timestamp is original
- NO → timestamp is from the copy, not the creation

---

## CATEGORY 3: VERSIONS (which version?)

### 3.1 Is there a v1, v2, v3 naming pattern?
- Check: `ls <base>*_v*.py <base>*_v*.c`
- YES → each version is a separate iteration, compare them
- NO → no versioning, single file

### 3.2 Is there a "new" or "old" variant?
- Check: `ls <base>*new* <base>*old*`
- YES → naming convention used instead of versioning
- NO → no new/old variants

### 3.3 Is there a git branch with a different version?
- Check: `git branch -a | grep -i <keyword>`
- YES → check the branch, it may have a different version
- NO → no branches

### 3.4 Is there a version in a different directory?
- Check: `find / -name "<filename>" 2>/dev/null`
- YES → compare versions across directories
- NO → only one location

### 3.5 Is there a version with a different extension?
- Check: `ls <base>*.py <base>*.c <base>*.sh <base>*.md`
- YES → may be a port or rewrite in another language
- NO → only one language

### 3.6 Is there a commented-out version inside another file?
- Check: `grep -n "#.*<filename>" <other_files>`
- YES → someone embedded it as a comment, read the commented version
- NO → no embedded versions

### 3.7 Is there a version in a database?
- Check: `SELECT * FROM code_classes WHERE class_name LIKE '%<keyword>%'`
- YES → the DB version may be different from the file version
- NO → not in database

### 3.8 Is there a version in chat history?
- Check: `grep -rl "<keyword>" chat_mover/ Downloads/`
- YES → a chat may contain the original or a different version
- NO → not in chat history

### 3.9 Is there a version in a zip/archive?
- Check: `find . -name "*.zip" -exec unzip -l {} \; | grep <keyword>`
- YES → extract and compare
- NO → no archived versions

### 3.10 Is the current version the final version?
- Check: compare to any TODO comments, FIXME, or incomplete sections
- YES → it is complete
- NO → it is a work in progress, there may be a newer version elsewhere

---

## CATEGORY 4: LOCATION (where?)

### 4.1 Is it in the expected directory?
- Check: `ls <expected_path>`
- YES → correct location
- NO → it moved, find it

### 4.2 Was it ever in a different directory?
- Check: `git log --follow --name-only <file>`
- YES → it was moved, the old location may have references
- NO → always in this location

### 4.3 Is there a copy in /tmp or a build directory?
- Check: `find /tmp -name "<filename>" 2>/dev/null`
- YES → may be a build artifact or test copy
- NO → no temp copies

### 4.4 Is there a copy in a backup directory?
- Check: `find . -path "*backup*" -name "<filename>" -o -path "*bak*" -name "<filename>"`
- YES → backup copy exists, compare to current
- NO → no backups

### 4.5 Is there a copy on another machine or volume?
- Check: `find /Volumes -name "<filename>" 2>/dev/null`
- YES → external copy exists
- NO → no external copies

### 4.6 Is there a symlink pointing to it?
- Check: `find . -type l -lname "*<filename>*"`
- YES → something references it via symlink
- NO → no symlinks

### 4.7 Is it in a directory that was recently reorganized?
- Check: `git log --oneline -- <directory>`
- YES → it may have been moved during reorganization, check old paths
- NO → directory is stable

### 4.8 Is the path hardcoded in other files?
- Check: `grep -rl "<full_path>" .`
- YES → those files will break if this file moves, note them
- NO → no hardcoded paths

### 4.9 Is the path in a config file?
- Check: `grep -rl "<filename>" --include="*.json" --include="*.yaml" --include="*.ini"`
- YES → config-driven path, check the config
- NO → path is not configured

### 4.10 Is the directory structure meaningful?
- Check: does the directory name tell you the domain? (e.g., `Dom_Gui/`, `bin_tools/`)
- YES → the directory defines the purpose, the file belongs there
- NO → directory name is generic, file could be anywhere

---

## CATEGORY 5: DEPENDENCIES (what does it touch?)

### 5.1 What does it import?
- Check: read the import section
- YES → each import is a dependency, trace each one
- NO → no imports, it is self-contained

### 5.2 What imports it?
- Check: `grep -rl "import <module>" --include="*.py"`
- YES → those files depend on it, changing it affects them
- NO → nothing imports it, it is a leaf

### 5.3 Does it depend on a database?
- Check: `grep -n "sqlite\|mysql\|postgres\|connect" <file>`
- YES → database is a dependency, check schema
- NO → no database dependency

### 5.4 Does it depend on an external binary?
- Check: `grep -n "subprocess\|os.system\|exec\|popen" <file>`
- YES → external binary is a dependency, check it exists
- NO → no external binary dependency

### 5.5 Does it depend on a specific Python/library version?
- Check: `grep -n "version\|__version__\|min_version" <file>` or check imports
- YES → version constraint exists, verify the version
- NO → no version constraint

### 5.6 Does it depend on environment variables?
- Check: `grep -n "os.environ\|getenv\|HOME\|PATH" <file>`
- YES → env vars are dependencies, check they are set
- NO → no env var dependency

### 5.7 Does it depend on a network service?
- Check: `grep -n "socket\|http\|url\|api\|request" <file>`
- YES → network service is a dependency, check availability
- NO → no network dependency

### 5.8 Does it depend on file system structure?
- Check: `grep -n "os.path\|Path(\|open(\|exists(" <file>`
- YES → file system is a dependency, check paths exist
- NO → no file system dependency

### 5.9 Does it depend on another file at runtime?
- Check: `grep -n "open(\|read_file\|load_file" <file>`
- YES → runtime file dependency, check the file exists
- NO → no runtime file dependency

### 5.10 Does anything depend on its output?
- Check: `grep -rl "<filename>" --include="*.py" | xargs grep -l "output\|result\|return"`
- YES → consumers exist, changing output format breaks them
- NO → no consumers, output format is free to change

---

## CATEGORY 6: AUTHORSHIP (who made it?)

### 6.1 Is there an author in the file header?
- Check: read `#[@GHOST]` header
- YES → author is known, check their other work
- NO → no author recorded

### 6.2 Was it created by Cascade?
- Check: header says `author="Cascade"` or `author="BclGenerator_v2"`
- YES → search Cascade .pb files and markdown exports
- NO → not Cascade

### 6.3 Was it created by Devin?
- Check: header says `author="Devin"` or search devin_transcripts
- YES → search devin_transcripts and devin_messages
- NO → not Devin

### 6.4 Was it created by ChatGPT?
- Check: search Downloads/*.md for ChatGPT-style exports mentioning the file
- YES → search ChatGPT exports
- NO → not ChatGPT

### 6.5 Was it created by hand?
- Check: no header, no AI authorship markers
- YES → no chat exists, it was manually written
- NO → it was AI-generated, chat exists somewhere

### 6.6 Was it created by a script?
- Check: `grep -rl "generated\|auto-generated\|created by" <file>`
- YES → a script generated it, find the script
- NO → not script-generated

### 6.7 Was it copied from another project?
- Check: `find / -name "<filename>" 2>/dev/null` excluding current dir
- YES → it was copied, the original is elsewhere
- NO → original to this project

### 6.8 Was it modified by multiple authors?
- Check: `git log --format="%an" -- <file> | sort -u`
- YES → multiple authors, each may have different intent
- NO → single author

### 6.9 Was it created in a pair-programming session?
- Check: chat history shows back-and-forth discussion before creation
- YES → the chat has the full reasoning, find it
- NO → no discussion, it was created directly

### 6.10 Is the author still active?
- Check: recent commits or chat activity from the same author
- YES → can ask the author directly
- NO → author is gone, only artifacts remain

---

## CATEGORY 7: CHAT HISTORY (was it discussed?)

### 7.1 Is it mentioned in vb_shared.know_questions?
- Check: `SELECT id, LEFT(question,300) FROM know_questions WHERE question LIKE '%<keyword>%'`
- YES → read the question and its answer
- NO → not in question history

### 7.2 Is it mentioned in vb_shared.know_answers?
- Check: `SELECT question_id, LEFT(answer,300) FROM know_answers WHERE answer LIKE '%<keyword>%'`
- YES → read the answer
- NO → not in answer history

### 7.3 Is it mentioned in devin_messages?
- Check: `SELECT row_id, LEFT(content,300) FROM devin_messages WHERE content LIKE '%<keyword>%'`
- YES → read the message context
- NO → not in Devin messages

### 7.4 Is it mentioned in devin_transcripts?
- Check: `SELECT id, session_id FROM devin_transcripts WHERE raw_json LIKE '%<keyword>%'`
- YES → read the full transcript
- NO → not in Devin transcripts

### 7.5 Is it mentioned in chat_mover markdown files?
- Check: `grep -rl "<keyword>" chat_mover/`
- YES → read the markdown file
- NO → not in chat_mover

### 7.6 Is it mentioned in Downloads markdown exports?
- Check: `grep -rl "<keyword>" Downloads/*.md`
- YES → read the export
- NO → not in Downloads

### 7.7 Is it mentioned in learned_rules?
- Check: `SELECT pattern, fix_action FROM learned_rules WHERE pattern LIKE '%<keyword>%'`
- YES → there is a learned rule about it
- NO → no learned rules

### 7.8 Is it mentioned in know_problems?
- Check: `SELECT problem, description FROM know_problems WHERE problem LIKE '%<keyword>%'`
- YES → there was a problem with it
- NO → no recorded problems

### 7.9 Is it mentioned in know_solutions?
- Check: `SELECT solution, description FROM know_solutions WHERE solution LIKE '%<keyword>%'`
- YES → there is a solution involving it
- NO → no recorded solutions

### 7.10 Is it mentioned in any .pb file?
- Check: decrypt and search .pb files (requires bcl_pb_reader fix)
- YES → found the Cascade chat
- NO → not in any .pb file

### 7.11 Is it mentioned in contestsystem?
- Check: `grep -rl "<keyword>" /Users/wws/contestsystem/`
- YES → it was discussed in the contestsystem workspace
- NO → not in contestsystem

### 7.12 Is it mentioned in any README?
- Check: `find . -name "README*" | xargs grep -l "<keyword>"`
- YES → read the README section about it
- NO → not in any README

---

## CATEGORY 8: DATABASE STATE (what does the DB know?)

### 8.1 Is it in CODEBASE.python_files?
- Check: `SELECT id, full_path, content_hash, line_count FROM python_files WHERE filename LIKE '%<keyword>%'`
- YES → it was ingested, check for duplicates
- NO → not ingested

### 8.2 Is it in vb_code_test.vb_classes?
- Check: `SELECT class_name, class_id FROM vb_classes WHERE class_name LIKE '%<keyword>%'`
- YES → the class was registered
- NO → not registered

### 8.3 Is it in vb_code_test.vb_methods?
- Check: `SELECT method_name FROM vb_methods WHERE method_name LIKE '%<keyword>%'`
- YES → methods were registered
- NO → not registered

### 8.4 Is it in vb_shared.code_classes?
- Check: `SELECT class_name FROM code_classes WHERE class_name LIKE '%<keyword>%'`
- YES → the class code is stored in the DB
- NO → not stored

### 8.5 Is it in vb_shared.learned_rules?
- Check: `SELECT pattern FROM learned_rules WHERE pattern LIKE '%<keyword>%'`
- YES → rules were learned about it
- NO → no rules

### 8.6 Is it in devin.devin_commands?
- Check: `SELECT command_name FROM devin_commands WHERE command_name LIKE '%<keyword>%'`
- YES → it was registered as a command
- NO → not a command

### 8.7 Is it in any SQLite DB?
- Check: `find . -name "*.db" -exec sqlite3 {} ".tables" \; | grep -i <keyword>`
- YES → it has a table in a SQLite DB
- NO → not in any SQLite DB

### 8.8 Does it have a content_hash in CODEBASE?
- Check: `SELECT content_hash, COUNT(*) FROM python_files WHERE filename = '<filename>' GROUP BY content_hash`
- YES → check for duplicates by hash
- NO → no hash

### 8.9 Was it extracted to python_structure?
- Check: `SELECT object_name, object_type FROM python_structure WHERE object_name LIKE '%<keyword>%'`
- YES → it was AST-parsed and stored
- NO → not parsed

### 8.10 Does it have graph edges?
- Check: `SELECT source_id, target_name, edge_type FROM python_graph_edges WHERE source_id IN (SELECT id FROM python_structure WHERE object_name LIKE '%<keyword>%')`
- YES → call graph was extracted
- NO → no graph edges

---

## CATEGORY 9: ERRORS (what went wrong?)

### 9.1 Did it ever crash?
- Check: `grep -rl "<keyword>" --include="*.log"` or search chat history for tracebacks
- YES → read the traceback, it reveals the code path
- NO → no crashes recorded

### 9.2 Did it ever produce wrong output?
- Check: search chat history for "wrong" or "incorrect" near the keyword
- YES → the bug is documented, read the fix
- NO → no wrong output recorded

### 9.3 Did it fail to compile?
- Check: search for compiler errors in chat history
- YES → the error reveals dependencies and syntax
- NO → compiles clean

### 9.4 Did it fail to import?
- Check: search for `ModuleNotFoundError` or `ImportError` near the keyword
- YES → the missing module is a hidden dependency
- NO → imports work

### 9.5 Did it fail to connect to DB?
- Check: search for `sqlite3.OperationalError` or `mysql.connector.Error`
- YES → DB connection issue, check DB path and schema
- NO → DB connection works

### 9.6 Did someone report a bug in it?
- Check: `SELECT problem FROM know_problems WHERE problem LIKE '%<keyword>%'`
- YES → read the problem and solution
- NO → no reported bugs

### 9.7 Did it have a fix applied?
- Check: `SELECT fix_action FROM learned_rules WHERE pattern LIKE '%<keyword>%'`
- YES → the fix tells you what was wrong
- NO → no fixes recorded

### 9.8 Did it have a workaround?
- Check: search chat for "workaround" or "temporary fix" near keyword
- YES → the workaround may still be in place, check if it is still needed
- NO → no workarounds

### 9.9 Is there a known issue that was never fixed?
- Check: search for `TODO` or `FIXME` or `HACK` in the file
- YES → known issue exists, do not refactor without addressing it
- NO → no known issues

### 9.10 Did the error happen during testing or production?
- Check: search chat for context around the error
- YES → the context tells you the severity and urgency
- NO → no error context

---

## CATEGORY 10: PATTERNS (is it like something else?)

### 10.1 Is there a similar file in the same directory?
- Check: `ls <directory>/*.py` and compare structure
- YES → follow the same pattern
- NO → no similar files

### 10.2 Is there a similar file in BookSystem?
- Check: `ls BookSystem/*.py` and compare
- YES → BookSystem is the template, match its structure
- NO → no BookSystem equivalent

### 10.3 Is there a similar file in core/Dom_Gui?
- Check: `ls core/Dom_Gui/*.py` and compare
- YES → Dom_Gui is the template
- NO → no Dom_Gui equivalent

### 10.4 Does it follow a pattern from learned_rules?
- Check: `SELECT pattern FROM learned_rules WHERE pattern LIKE '%structure%' OR pattern LIKE '%format%'`
- YES → the rule defines the pattern, follow it
- NO → no pattern rules

### 10.5 Does it follow VBStyle?
- Check: read `#[@VBSTYLE]` header
- YES → it follows VBStyle, check compliance
- NO → it does not follow VBStyle, it may need to be converted

### 10.6 Is it the only file that does X?
- Check: `grep -rl "<unique_pattern>" .`
- YES → it is unique, no pattern to follow
- NO → there are others, compare them

### 10.7 Is there a canonical version of this pattern?
- Check: `SELECT class_name FROM vb_classes WHERE class_name LIKE '%<pattern>%'`
- YES → the canonical version is in the DB, read it
- NO → no canonical version

### 10.8 Does it match a design pattern from governance?
- Check: `SELECT rule_name, rule_body FROM governance WHERE rule_body LIKE '%<pattern>%'`
- YES → governance defines the pattern, follow it
- NO → not in governance

### 10.9 Is it a one-off or part of a family?
- Check: are there sibling files with similar names?
- YES → it is part of a family, check the others
- NO → it is a one-off

### 10.10 Does it have a corresponding test pattern?
- Check: `find . -name "test_*" | xargs grep -l "<keyword>"`
- YES → the test shows how it should be used
- NO → no tests

---

## CATEGORY 11: ENVIRONMENT (where does it run?)

### 11.1 Does it need a specific Python version?
- Check: `grep -n "python3\." <file>` or check shebang
- YES → version constraint, verify it
- NO → any Python 3

### 11.2 Does it need PyQt6?
- Check: `grep -n "PyQt6" <file>`
- YES → PyQt6 is a dependency, verify it is installed
- NO → no PyQt6

### 11.3 Does it need MySQL?
- Check: `grep -n "mysql" <file>`
- YES → MySQL is a dependency, verify it is running
- NO → no MySQL

### 11.4 Does it need SQLite?
- Check: `grep -n "sqlite" <file>`
- YES → SQLite is a dependency, verify the DB file exists
- NO → no SQLite

### 11.5 Does it need a virtual environment?
- Check: `grep -n "venv\|virtualenv\|activate" <file>` or check shebang
- YES → venv is required, verify it exists
- NO → no venv needed

### 11.6 Does it need specific env vars?
- Check: `grep -n "os.environ\|getenv" <file>`
- YES → env vars required, check they are set
- NO → no env vars needed

### 11.7 Does it need network access?
- Check: `grep -n "socket\|http\|request\|url" <file>`
- YES → network required, verify connectivity
- NO → no network needed

### 11.8 Does it need GUI display?
- Check: `grep -n "QApplication\|QMainWindow\|show()" <file>`
- YES → display required, cannot run headless
- NO → can run headless

### 11.9 Does it need root/sudo?
- Check: `grep -n "sudo\|root\|chmod\|chown" <file>`
- YES → elevated permissions required
- NO → normal permissions

### 11.10 Does it need a specific working directory?
- Check: `grep -n "os.chdir\|chdir\|cwd" <file>`
- YES → specific working directory required
- NO → any working directory

---

## CATEGORY 12: NAMING (what is it called?)

### 12.1 Has the name changed?
- Check: `git log --follow --name-only <file>`
- YES → it was renamed, old name may be referenced elsewhere
- NO → name is stable

### 12.2 Is the name consistent with the directory?
- Check: does `Dom_DecisionTrees/DecisionTreeGui_v1.py` match the `Dom_DecisionTrees` domain?
- YES → naming is consistent
- NO → naming mismatch, it may belong elsewhere

### 12.3 Is the class name consistent with the file name?
- Check: `grep "^class " <file>` and compare to filename
- YES → consistent
- NO → mismatch, one of them is wrong

### 12.4 Are there aliases or abbreviations?
- Check: `grep -rl "DTG\|dtg\|decision_tree_gui\|DecisionTree" .`
- YES → aliases exist, search for all of them
- NO → no aliases

### 12.5 Is the name in the database different from the file?
- Check: `SELECT class_name FROM vb_classes WHERE class_name LIKE '%Decision%'`
- YES → DB name may be different, compare
- NO → not in DB

### 12.6 Does the name follow VBStyle PascalCase?
- Check: no underscores, no lowercase start
- YES → compliant
- NO → non-compliant, may need rename

### 12.7 Is there a naming convention in the directory?
- Check: `ls <directory>` and look at naming patterns
- YES → follow the convention
- NO → no convention

### 12.8 Does the name contain a version suffix?
- Check: `_v1`, `_v2`, `_new`, `_old` in filename
- YES → versioned, check for other versions
- NO → unversioned

### 12.9 Is the name descriptive or generic?
- Check: does the name tell you what it does?
- YES → descriptive, easy to search for
- NO → generic, hard to search for, try alternative keywords

### 12.10 Are there typos in the name?
- Check: compare to standard spelling
- YES → typo exists, search for both correct and incorrect spellings
- NO → spelling is correct

---

## CATEGORY 13: STATE (what state is it in?)

### 13.1 Is it complete or incomplete?
- Check: `grep -n "TODO\|FIXME\|HACK\|XXX\|pass$" <file>`
- YES → incomplete, there may be a newer version
- NO → complete

### 13.2 Is it active or abandoned?
- Check: last modification time, recent references
- YES (recent) → active
- NO (old) → abandoned, may be replaced

### 13.3 Is it tested or untested?
- Check: `find . -name "test_*<keyword>*" -o -name "*<keyword>*_test*"`
- YES → tested
- NO → untested

### 13.4 Is it documented or undocumented?
- Check: `grep -c "^#\|\"\"\"" <file>` (comment/docstring density)
- YES → documented
- NO → undocumented

### 13.5 Is it compliant or non-compliant?
- Check: run VBStyle checker
- YES → compliant
- NO → non-compliant, has violations

### 13.6 Is it production-ready or experimental?
- Check: error handling, edge cases, hardcoded values
- YES → production-ready
- NO → experimental

### 13.7 Is it imported by production code?
- Check: `grep -rl "import <module>" --include="*.py"`
- YES → production dependency, be careful
- NO → not imported, safe to change

### 13.8 Is it wrapped in try/except?
- Check: `grep -c "try:" <file>`
- YES → error handling exists
- NO → no error handling

### 13.9 Does it have a state dict?
- Check: `grep -n "self.state" <file>`
- YES → uses state dict (VBStyle)
- NO → uses self._ attributes (non-VBStyle)

### 13.10 Does it return Tuple3?
- Check: `grep -n "return (1\|return (0\|Tuple3" <file>`
- YES → returns Tuple3 (VBStyle)
- NO → returns raw values (non-VBStyle)

---

## CATEGORY 14: RELATIONSHIPS (what is it connected to?)

### 14.1 Does it call other files?
- Check: `grep -n "import\|from " <file>`
- YES → it calls those files, trace the call chain
- NO → self-contained

### 14.2 Do other files call it?
- Check: `grep -rl "import <module>" --include="*.py"`
- YES → those files call it, they are dependents
- NO → nothing calls it

### 14.3 Does it share data with another file?
- Check: `grep -n "open(\|read(\|write(" <file>` and compare paths
- YES → shares data via files, check the shared files
- NO → no shared data

### 14.4 Does it share a database with another file?
- Check: `grep -n "connect\|cursor" <file>` and compare DB paths
- YES → shares DB, check for concurrent access issues
- NO → no shared DB

### 14.5 Is it part of a pipeline?
- Check: does its output feed into another file's input?
- YES → it is a pipeline stage, check upstream and downstream
- NO → standalone

### 14.6 Is it part of a dependency chain?
- Check: A imports B imports C — where is this file in the chain?
- YES → position in chain matters, changing it affects the whole chain
- NO → not in a chain

### 14.7 Does it have a parent class?
- Check: `grep -n "class.*(" <file>`
- YES → parent class exists, read it
- NO → no parent

### 14.8 Does it have child classes?
- Check: `grep -rl "class.*<ClassName>" --include="*.py"`
- YES → child classes exist, they inherit its behavior
- NO → no children

### 14.9 Does it have siblings?
- Check: files in the same directory with similar imports or patterns
- YES → siblings exist, they may share a base or pattern
- NO → no siblings

### 14.10 Is it connected to a chat session?
- Check: search chat history for the file name
- YES → the chat is the context, read it
- NO → no chat context

---

## CATEGORY 15: ASSUMPTIONS (what am I assuming?)

### 15.1 Am I assuming it was created by a chat?
- Check: is there evidence of AI authorship vs manual creation?
- YES → assumption is valid, search chats
- NO → assumption is wrong, it may be manual

### 15.2 Am I assuming it is the only version?
- Check: `find / -name "<filename>" 2>/dev/null`
- YES → assumption is valid
- NO → assumption is wrong, other versions exist

### 15.3 Am I assuming the file is complete?
- Check: `grep -n "TODO\|FIXME\|pass$" <file>`
- YES → assumption is valid
- NO → assumption is wrong, it is incomplete

### 15.4 Am I assuming it follows VBStyle?
- Check: read the header
- YES → assumption is valid
- NO → assumption is wrong, it does not follow VBStyle

### 15.5 Am I assuming the database schema matches the code?
- Check: compare `CREATE TABLE` in code to `SHOW COLUMNS` in DB
- YES → assumption is valid
- NO → assumption is wrong, schema has drifted

### 15.6 Am I assuming no one else is working on it?
- Check: `git status` and recent commits
- YES → assumption is valid
- NO → assumption is wrong, someone else is modifying it

### 15.7 Am I assuming the imports are correct?
- Check: `python3 -c "import <module>"` for each import
- YES → assumption is valid
- NO → assumption is wrong, an import is broken

### 15.8 Am I assuming the test passes?
- Check: run the test
- YES → assumption is valid
- NO → assumption is wrong, the test fails

### 15.9 Am I assuming the chat is in MySQL?
- Check: query all chat tables
- YES → assumption is valid
- NO → assumption is wrong, the chat is in .pb or .md files

### 15.10 Am I assuming I have read the entire file?
- Check: `wc -l <file>` vs how many lines I actually read
- YES → I read it all
- NO → I only read part of it, read the rest

### 15.11 Am I assuming the file path is correct?
- Check: `ls -la <path>`
- YES → path is correct
- NO → path is wrong, file is elsewhere

### 15.12 Am I assuming the function signature matches the caller?
- Check: compare `def function(` to how it is called
- YES → signatures match
- NO → signatures do not match, there is a bug

### 15.13 Am I assuming the error message tells the truth?
- Check: reproduce the error and read the full traceback
- YES → error is accurate
- NO → error is misleading, the real issue is elsewhere

### 15.14 Am I assuming the user remembers correctly?
- Check: verify user's claim against the evidence
- YES → user is correct
- NO → user is misremembering, trust the evidence

### 15.15 Am I assuming there is only one solution?
- Check: are there alternative approaches I have not considered?
- YES → only one solution
- NO → there are alternatives, evaluate them

---

## SUMMARY

| Category | Questions | What it collapses |
|----------|-----------|-------------------|
| 1. Existence | 10 | Does the thing exist at all? |
| 2. Time | 10 | When did it happen? |
| 3. Versions | 10 | Which version is this? |
| 4. Location | 10 | Where is it? |
| 5. Dependencies | 10 | What does it touch? |
| 6. Authorship | 10 | Who made it? |
| 7. Chat History | 12 | Was it discussed? |
| 8. Database State | 10 | What does the DB know? |
| 9. Errors | 10 | What went wrong? |
| 10. Patterns | 10 | Is it like something else? |
| 11. Environment | 10 | Where does it run? |
| 12. Naming | 10 | What is it called? |
| 13. State | 10 | What state is it in? |
| 14. Relationships | 10 | What is it connected to? |
| 15. Assumptions | 15 | What am I assuming? |
| **TOTAL** | **157** | **Full uncertainty collapse** |

## The principle
Every assumption is a question you have not asked.
Every question you ask collapses an assumption into a fact.
157 questions collapse 157 assumptions.
After 157 questions, the only uncertainty left is the unknown unknowns.
