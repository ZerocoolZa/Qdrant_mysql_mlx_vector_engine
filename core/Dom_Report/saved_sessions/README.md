# Saved Sessions — Architecture Work + GUI Session Recovery

**Saved:** 2026-07-03
**Reason:** Chat pollution from another Devin session running cascade_cli.py was leaking database dumps into our terminal output. This directory preserves all the work we did together so it doesn't get lost.

## What's In Here

### Our Architecture Work (this session)

| File | What |
|---|---|
| `diagnostic_kb_schema_dump.sql` | Schema-only dump of all 46 tables |
| `diagnostic_kb_full_dump.sql` | Full dump (schema + data) of diagnostic_kb |
| `diagnostic_kb_schema.sql` | The schema SQL file we've been editing |
| `AGENTS.md` | The architecture documentation we updated |
| `SCHEMA_REPORT.md` | The complete schema audit report |
| `law_data.txt` | All 7 laws (LAW1-LAW6 + PRINCIPLE) |
| `pattern_data.txt` | All 16 patterns (ENU, SVU, NCC, DEC, etc.) |
| `pattern_law_data.txt` | The reasoning graph (which patterns violate which laws) |
| `decision_data.txt` | All 5 decisions (DEC001-DEC005) |
| `table_registry_data.txt` | All 46 registered tables |
| `table_rule_data.txt` | All 94 table-law/pattern applications |

### GUI Session (fortune-poetry) — was supposed to be editing GUI

| File | What |
|---|---|
| `fortune-poetry_gui_brain.txt` | The "gui brain" Devin session — launched BrainRenderer.py |
| `about_text_gui_content.txt` | The about_text table — PyQt6 GUI About dialog content |
| `gui_classes.txt` | List of GUI-related classes in code_classes table |

### Pollution Source

| File | What |
|---|---|
| `execution_log_last100.txt` | Last 100 commands run by cascade_cli.py |
| `right-mailman_punishing_cascade.txt` | The "Punishing Cascade" session |

## The Pollution Problem

A background Devin session (PID 50362 or 11808) was running `cascade_cli.py` which dumps MySQL table contents to stdout. This output leaked into our terminal session, appearing after almost every command.

The pollution included:
- `code_classes` table dumps (Python class code)
- `about_text` table dumps (PyQt6 GUI About dialog content)
- `execution_log` table dumps (command history)
- `code_co_occurrence` and `code_identifier_frequency` dumps
- `c_classes` table dumps (C class code)

This content was meant for a GUI editing session, not for our database architecture discussion.

## What We Built (Summary)

1. **Self-describing schema** — 4 meta-tables (table_registry, table_column, table_relationship, table_rule)
2. **Code structure** — 5 PascalCase tables (Method, ComputationUnit, Class, ComputationUnitMethod, ClassComputationUnit)
3. **LAW6** — "Never Create a Specialized Version of a Universal Concept"
4. **2 new patterns** — SVU (No Specialized Version of Universal), NCC (No Compound Concept Names)
5. **DEC005** — Use Type not MethodType, ClassType, ErrorType
6. **Full audit** — 7 categories of violations identified

## 46 Tables Total

- 7 authority tables (type, category, domain, status, severity, priority, group)
- 15 entity tables (error, question, answer, incident, cause, fix, prevention, problem, rule, fact, evidence, report, Method, ComputationUnit, Class)
- 12 join tables (10 report_* + ComputationUnitMethod + ClassComputationUnit)
- 4 governance tables (law, pattern, pattern_law, decision)
- 4 meta tables (table_registry, table_column, table_relationship, table_rule)
- 2 legacy join tables (incident_problem, problem_solution)
- 1 legacy table (question_type — to be dropped)
- 1 deprecated table (foundation_law — to be dropped)
