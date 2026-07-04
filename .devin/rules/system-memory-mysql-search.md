# System Memory: MySQL Knowledge Base Search Enforcement

## MANDATORY RULE — AI MUST SEARCH BEFORE CODING

Before writing, modifying, or generating ANY code in this workspace, the AI MUST first search the MySQL knowledge base (`vb_shared` database) for existing patterns, solutions, problems, causes, fixes, and learned rules that match the task.

### Enforcement

This rule is **always-on** and **non-negotiable**. No exceptions.

### What must be searched

The MySQL `vb_shared` database (localhost:3306, user=root) contains the accumulated knowledge of the VBStyle runtime system:

| Table | Purpose | Rows |
|-------|---------|------|
| `know_problems` | Known problems (218) | What went wrong before |
| `know_causes` | Root causes (4) | Why it went wrong |
| `know_fixes` | Applied fixes (2) | How it was fixed |
| `know_solutions` | Solutions with weight (336) | Ranked solutions |
| `know_questions` | Diagnostic questions (137) | What to ask |
| `know_answers` | Answers with confidence (123) | What was learned |
| `know_reasoning` | Reasoning patterns (9) | How to think about it |
| `know_memory_units` | MemUnit registry (16) | Compressed memory blocks |
| `learned_rules` | Fix rules with success/failure counts (10540) | The big one — accumulated fixes |
| `rule_patterns` | Pattern matching rules | How to detect problems |
| `component_ontology` | Component catalog | What components exist |
| `decision_principles` | Decision rules | How to choose |

The `vb_code_test` database contains the code corpus:

| Table | Purpose | Rows |
|-------|---------|------|
| `vb_classes` | All VBStyle classes | 1394 |
| `vb_methods` | All methods | 13818 |

### Search procedure

Before writing code, run this search:

```python
import mysql.connector

# 1. Search learned_rules for matching patterns
conn = mysql.connector.connect(user='root', host='localhost', port=3306, database='vb_shared')
cur = conn.cursor(dictionary=True)
cur.execute("SELECT * FROM learned_rules WHERE pattern LIKE %s OR trigger_condition LIKE %s OR fix_action LIKE %s ORDER BY confidence DESC, success_count DESC LIMIT 10", (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
rules = cur.fetchall()

# 2. Search know_problems + know_solutions
cur.execute("SELECT p.problem, s.solution, s.weight FROM know_problems p LEFT JOIN know_solutions s ON s.problem_id = p.id WHERE p.problem LIKE %s ORDER BY s.weight DESC", (f'%{keyword}%',))

# 3. Search know_questions + know_answers
cur.execute("SELECT q.question, a.answer, a.confidence FROM know_questions q LEFT JOIN know_answers a ON a.question_id = q.id WHERE q.question LIKE %s OR a.answer LIKE %s", (f'%{keyword}%', f'%{keyword}%'))

# 4. Search vb_code_test for existing classes/methods
conn2 = mysql.connector.connect(user='root', host='localhost', port=3306, database='vb_code_test')
cur2 = conn2.cursor(dictionary=True)
cur2.execute("SELECT class_name, class_code FROM vb_classes WHERE class_name LIKE %s", (f'%{keyword}%',))
```

### Why this matters

From the architecture document (`najma_email_gpt.md`):

> "The value becomes: problem history, cause history, fix history, success history, rejection history. Eventually the database becomes smarter than any individual repair attempt because it contains the accumulated outcomes."

> "Every solved problem narrows future search. Every promoted survivor strengthens the system's understanding. Every failed candidate teaches where not to search."

The MySQL database IS the system memory. It contains 10,540 learned rules with confidence scores. Writing code without checking it first is like ignoring 10,540 past lessons.

### Violation

If code is written without first searching the MySQL knowledge base, the Report Class must log this as a violation:

```
VIOLATION: Code written without MySQL knowledge base search
  - File: <path>
  - Task: <description>
  - Learned rules bypassed: 10540
  - Known problems bypassed: 218
  - Known solutions bypassed: 336
```

### Connection details

```
Host: localhost
Port: 3306
User: root
Databases: vb_shared (knowledge), vb_code_test (code corpus)
```
