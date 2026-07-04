---
trigger: manual
auto_execution_mode: 3
description: vbstyle
---
# VBStyle Coding Rules for AI

Source: `book.db` (VBStyle rule book, 84 rules).
These rules govern how the AI must write code in this workspace.

## Enforcement priority

- Blocker: `@immutable`, `@noedit`, `@nofiles`, `@noexec`, `@scope`, `@askdel` — never violate.
- Hard: all `@header`, `@dispatch`, `@contract`, `@naming`, `@prohibition` rules.
- Architecture: `@modes`, `@boot`, `@col`, `@drift`, `@domain` — design-time rules.

## Quick reference

| #   | Tag                 | Category   | Short                                                                                                                                                                                          |
| --- | ------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `@cascade_lesson` | meta       | Multi-Pass Iterative Refinement Pattern: When code fails validation automatic...                                                                                                               |
| 2   | `@dontknow`       | meta       | dont assume                                                                                                                                                                                    |
| 3   | `@unsure`         | meta       | if unsure ask                                                                                                                                                                                  |
| 4   | `@noexec`         | meta       | do not execute code or scripts without explicit user instruction                                                                                                                               |
| 5   | `@useremotion`    | meta       | before any action consider user emotional impact                                                                                                                                               |
| 6   | `@collab`         | meta       | pair programming driver navigator pattern                                                                                                                                                      |
| 7   | `@noRESTORbackup` | meta       | do not restore database backups without explicit user permission                                                                                                                               |
| 8   | `@noedit`         | meta       | do not edit any file unless told to edit that specific file                                                                                                                                    |
| 9   | `@nofiles`        | meta       | do not create files                                                                                                                                                                            |
| 10  | `@exact`          | meta       | do exactly as told                                                                                                                                                                             |
| 11  | `@consent`        | meta       | detection authority is not execution authority                                                                                                                                                 |
| 12  | `@scope`          | meta       | all edits restricted to explicitly approved files and approved scope only                                                                                                                      |
| 13  | `@askdel`         | meta       | ask before delete replace restore migration overwrite or refactor                                                                                                                              |
| 14  | `@noauto`         | meta       | discussion analysis diagnostics summaries and questions never imply edit auth...                                                                                                               |
| 15  | `@modes`          | meta       | separate analysis mode proposal mode execution mode autonomous repair mode                                                                                                                     |
| 16  | `@gate`           | meta       | if unsure stop and ask                                                                                                                                                                         |
| 17  | `@noarch`         | meta       | do not invent architecture                                                                                                                                                                     |
| 18  | `@norule`         | meta       | do not invent rules and code style                                                                                                                                                             |
| 19  | `@underscore`     | syntax     | _ not allowed in class names                                                                                                                                                                   |
| 20  | `@decorators`     | syntax     | @property                                                                                                                                                                                      |
| 21  | `@enums`          | syntax     | do not use enums                                                                                                                                                                               |
| 22  | `@print`          | syntax     | do not use print statements                                                                                                                                                                    |
| 23  | `@hidden`         | syntax     | no hidden or implicit behavior                                                                                                                                                                 |
| 24  | `@hardcode`       | syntax     | no hardcoded NOTHING IS ALOWED TO BE HARD CODED                                                                                                                                                |
| 25  | `@tabs`           | syntax     | no tabs                                                                                                                                                                                        |
| 26  | `@whitespace`     | syntax     | no trailing whitespace at end of lines                                                                                                                                                         |
| 27  | `@intstate`       | syntax     | no self                                                                                                                                                                                        |
| 28  | `@params`         | syntax     | all methods must accept all data as parameters                                                                                                                                                 |
| 29  | `@tuples`         | syntax     | all methods must return Tuple3 ok data error                                                                                                                                                   |
| 30  | `@domain`         | syntax     | each class must own exactly one domain                                                                                                                                                         |
| 31  | `@dismap`         | syntax     | every dispatch key must map to exactly one method                                                                                                                                              |
| 32  | `@memunit`        | syntax     | all code exeute only in memunit                                                                                                                                                                |
| 33  | `@ghost`          | header     | all code must have Ghost Header                                                                                                                                                                |
| 34  | `@vbsty`          | header     | all code must have VBStyle Header                                                                                                                                                              |
| 35  | `@cstyle`         | header     | one class domain authority complete                                                                                                                                                            |
| 36  | `@clshdr`         | header     | all classes must have Classes Header                                                                                                                                                           |
| 37  | `@mthdr`          | header     | all methods must have Method Header                                                                                                                                                            |
| 38  | `@pascal`         | header     | class names PascalCase no underscores                                                                                                                                                          |
| 39  | `@upper`          | header     | constants UPPERCASE at class level                                                                                                                                                             |
| 40  | `@ctor`           | header     | def__init__ self mem None db None param None                                                                                                                                             |
| 41  | `@state`          | header     | self                                                                                                                                                                                           |
| 42  | `@noself`         | header     | no self                                                                                                                                                                                        |
| 43  | `@run`            | dispatch   | Run command params dispatch entry point                                                                                                                                                        |
| 44  | `@rdst`           | dispatch   | read_state returns config snapshot                                                                                                                                                             |
| 45  | `@cfg`            | dispatch   | set_config updates config                                                                                                                                                                      |
| 46  | `@phelp`          | dispatch   | _p params key default param helper                                                                                                                                                             |
| 47  | `@disp`           | dispatch   | dispatch command params internal                                                                                                                                                               |
| 48  | `@succ`           | dispatch   | success return 1 data                                                                                                                                                                          |
| 49  | `@err`            | dispatch   | error return 0 None error tuple                                                                                                                                                                |
| 50  | `@t3`             | dispatch   | Tuple3 return ok data error                                                                                                                                                                    |
| 51  | `@errfmt`         | dispatch   | error tuple format code desc 0                                                                                                                                                                 |
| 52  | `@auth`           | authority  | authority pattern one class one domain                                                                                                                                                         |
| 53  | `@ram`            | authority  | RAM mirror memory reads backup writes                                                                                                                                                          |
| 54  | `@rpt`            | authority  | report isolation returns strings no print                                                                                                                                                      |
| 55  | `@selfdb`         | db         | self documenting db code registry                                                                                                                                                              |
| 56  | `@authdb`         | db         | authorities table schema                                                                                                                                                                       |
| 57  | `@dep`            | db         | authority deps table schema                                                                                                                                                                    |
| 58  | `@mdep`           | db         | method deps table schema                                                                                                                                                                       |
| 59  | `@runst`          | db         | runtime state table schema                                                                                                                                                                     |
| 60  | `@exec`           | db         | execution log table schema                                                                                                                                                                     |
| 61  | `@know`           | db         | knowledge table schema                                                                                                                                                                         |
| 62  | `@conf`           | db         | config table schema                                                                                                                                                                            |
| 63  | `@meth`           | db         | methods table schema                                                                                                                                                                           |
| 64  | `@dcon`           | db         | dispatch contract table schema                                                                                                                                                                 |
| 65  | `@reg`            | db         | code registry table schema                                                                                                                                                                     |
| 66  | `@exp`            | analysis   | EXPAND search everything no assumptions                                                                                                                                                        |
| 67  | `@clu`            | analysis   | CLUSTER group by repetition similarity                                                                                                                                                         |
| 68  | `@map`            | analysis   | MAP align meaning to context test system                                                                                                                                                       |
| 69  | `@col`            | analysis   | COLLAPSE extract stable invariant jewel                                                                                                                                                        |
| 70  | `@hrt`            | validation | HRT header violation naming structure                                                                                                                                                          |
| 71  | `@hst`            | validation | HST style violation formatting                                                                                                                                                                 |
| 86  | `@mysql_86`       | general    | no rule: do not invent rules and code style                                                                                                                                                    |
| 101 | `@mysql_101`      | general    | code_operations: For code operations: A) Check governance table, B) Use database for structure, C) Populate methods table, D) Generate code from database, E) Validate against VBStyle rules   |
| 117 | `@mysql_117`      | general    | Classify rules databases as non_chat: Databases with rules, validation tables are governance systems, not chat data. Should be classified as non_chat.                                         |
| 121 | `@mysql_121`      | general    | Handle unknown classification: When no filename, table, or column evidence matches known migration rules, classify as unknown with confidence 0. Do not force classification without evidence. |
| 227 | `@mysql_227`      | general    | these rules apply to all Unit python files by default: Must: these rules apply to all Unit python files by default                                                                             |
| 228 | `@mysql_228`      | general    | these rules apply to all test python files by default: Must: these rules apply to all test python files by default                                                                             |
| 229 | `@mysql_229`      | general    | these rules apply to all python code by default: Must: these rules apply to all python code by default                                                                                         |
| 233 | `@mysql_233`      | general    | result row shape is Result File Lang Rule if Fail Correction Line or Ranges or Class: Must: result row shape is Result File Lang Rule if Fail Correction Line or Ranges or Class               |
| 234 | `@mysql_234`      | general    | all code below the protected block obeys the protected rules: Must: all code below the protected block obeys the protected rules                                                               |
| 235 | `@mysql_235`      | general    | all classes in this file obey the protected rules unless explicitly exempted: Must: all classes in this file obey the protected rules unless explicitly exempted                               |
| 236 | `@mysql_236`      | general    | any class that breaks a protected rule must fail validation: Must: any class that breaks a protected rule must fail validation                                                                 |
| 238 | `@mysql_238`      | general    | any unfixable violation must be stamped in file with rule line and required correction: Must: any unfixable violation must be stamped in file with rule line and required correction           |
| 250 | `@mysql_250`      | general    | no class in this file may break the protected rules below the protected line: Must: no class in this file may break the protected rules below the protected line                               |

## Category: meta

### 1. `@cascade_lesson` — Multi-Pass Iterative Refinement Pattern: When code fails validation automatic...

---

### 2. `@dontknow` — dont assume

---

### 3. `@unsure` — if unsure ask

---

### 4. `@noexec` — do not execute code or scripts without explicit user instruction

---

### 5. `@useremotion` — before any action consider user emotional impact

---

### 6. `@collab` — pair programming driver navigator pattern

---

### 7. `@noRESTORbackup` — do not restore database backups without explicit user permission

---

### 8. `@noedit` — do not edit any file unless told to edit that specific file

---

### 9. `@nofiles` — do not create files

---

### 10. `@exact` — do exactly as told

---

### 11. `@consent` — detection authority is not execution authority

---

### 12. `@scope` — all edits restricted to explicitly approved files and approved scope only

---

### 13. `@askdel` — ask before delete replace restore migration overwrite or refactor

---

### 14. `@noauto` — discussion analysis diagnostics summaries and questions never imply edit auth...

---

### 15. `@modes` — separate analysis mode proposal mode execution mode autonomous repair mode

---

### 16. `@gate` — if unsure stop and ask

---

### 17. `@noarch` — do not invent architecture

---

### 18. `@norule` — do not invent rules and code style

---

## Category: syntax

### 19. `@underscore` — _ not allowed in class names

---

### 20. `@decorators` — @property

---

### 21. `@enums` — do not use enums

---

### 22. `@print` — do not use print statements

---

### 23. `@hidden` — no hidden or implicit behavior

---

### 24. `@hardcode` — no hardcoded NOTHING IS ALOWED TO BE HARD CODED

---

### 25. `@tabs` — no tabs

---

### 26. `@whitespace` — no trailing whitespace at end of lines

---

### 27. `@intstate` — no self

---

### 28. `@params` — all methods must accept all data as parameters

---

### 29. `@tuples` — all methods must return Tuple3 ok data error

---

### 30. `@domain` — each class must own exactly one domain

---

### 31. `@dismap` — every dispatch key must map to exactly one method

---

### 32. `@memunit` — all code exeute only in memunit

---

## Category: header

### 33. `@ghost` — all code must have Ghost Header

---

### 34. `@vbsty` — all code must have VBStyle Header

---

### 35. `@cstyle` — one class domain authority complete

---

### 36. `@clshdr` — all classes must have Classes Header

---

### 37. `@mthdr` — all methods must have Method Header

---

### 38. `@pascal` — class names PascalCase no underscores

---

### 39. `@upper` — constants UPPERCASE at class level

---

### 40. `@ctor` — def __init__ self mem None db None param None

---

### 41. `@state` — self

---

### 42. `@noself` — no self

---

## Category: dispatch

### 43. `@run` — Run command params dispatch entry point

---

### 44. `@rdst` — read_state returns config snapshot

---

### 45. `@cfg` — set_config updates config

---

### 46. `@phelp` — _p params key default param helper

---

### 47. `@disp` — dispatch command params internal

---

### 48. `@succ` — success return 1 data

---

### 49. `@err` — error return 0 None error tuple

---

### 50. `@t3` — Tuple3 return ok data error

---

### 51. `@errfmt` — error tuple format code desc 0

---

## Category: authority

### 52. `@auth` — authority pattern one class one domain

---

### 53. `@ram` — RAM mirror memory reads backup writes

---

### 54. `@rpt` — report isolation returns strings no print

---

## Category: db

### 55. `@selfdb` — self documenting db code registry

---

### 56. `@authdb` — authorities table schema

---

### 57. `@dep` — authority deps table schema

---

### 58. `@mdep` — method deps table schema

---

### 59. `@runst` — runtime state table schema

---

### 60. `@exec` — execution log table schema

---

### 61. `@know` — knowledge table schema

---

### 62. `@conf` — config table schema

---

### 63. `@meth` — methods table schema

---

### 64. `@dcon` — dispatch contract table schema

---

### 65. `@reg` — code registry table schema

---

## Category: analysis

### 66. `@exp` — EXPAND search everything no assumptions

---

### 67. `@clu` — CLUSTER group by repetition similarity

---

### 68. `@map` — MAP align meaning to context test system

---

### 69. `@col` — COLLAPSE extract stable invariant jewel

---

## Category: validation

### 70. `@hrt` — HRT header violation naming structure

---

### 71. `@hst` — HST style violation formatting

---

## Category: general

### 86. `@mysql_86` — no rule: do not invent rules and code style

---

### 101. `@mysql_101` — code_operations: For code operations: A) Check governance table, B) Use database for structure, C) Populate methods table, D) Generate code from database, E) Validate against VBStyle rules

---

### 117. `@mysql_117` — Classify rules databases as non_chat: Databases with rules, validation tables are governance systems, not chat data. Should be classified as non_chat.

---

### 121. `@mysql_121` — Handle unknown classification: When no filename, table, or column evidence matches known migration rules, classify as unknown with confidence 0. Do not force classification without evidence.

---

### 227. `@mysql_227` — these rules apply to all Unit python files by default: Must: these rules apply to all Unit python files by default

---

### 228. `@mysql_228` — these rules apply to all test python files by default: Must: these rules apply to all test python files by default

---

### 229. `@mysql_229` — these rules apply to all python code by default: Must: these rules apply to all python code by default

---

### 233. `@mysql_233` — result row shape is Result File Lang Rule if Fail Correction Line or Ranges or Class: Must: result row shape is Result File Lang Rule if Fail Correction Line or Ranges or Class

---

### 234. `@mysql_234` — all code below the protected block obeys the protected rules: Must: all code below the protected block obeys the protected rules

---

### 235. `@mysql_235` — all classes in this file obey the protected rules unless explicitly exempted: Must: all classes in this file obey the protected rules unless explicitly exempted

---

### 236. `@mysql_236` — any class that breaks a protected rule must fail validation: Must: any class that breaks a protected rule must fail validation

---

### 238. `@mysql_238` — any unfixable violation must be stamped in file with rule line and required correction: Must: any unfixable violation must be stamped in file with rule line and required correction

---

### 250. `@mysql_250` — no class in this file may break the protected rules below the protected line: Must: no class in this file may break the protected rules below the protected line

---

## Rule Dependency Graph (all 84 rules)

Edges mean: `A → B` = rule A must pass before rule B is checked. If A fails, skip B.

### Scope levels

| Scope    | Rules                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| file     | @ghost, @vbsty, @tabs, @whitespace, @noexec, @nofiles, @noedit, @scope, @askdel, @noauto, @mysql_229, @mysql_234, @mysql_250 |
| class    | @pascal, @underscore, @domain, @clshdr, @cstyle, @auth, @upper, @ctor, @mysql_227, @mysql_235      |
| method   | @mthdr, @run, @tuples, @t3, @params, @dismap, @disp, @rdst, @cfg, @phelp, @succ, @err, @errfmt     |
| state    | @intstate, @state, @noself, @memunit                                                               |
| db       | @selfdb, @authdb, @dep, @mdep, @runst, @exec, @know, @conf, @meth, @dcon, @reg                     |
| analysis | @exp, @clu, @map, @col                                                                             |
| validation | @hrt, @hst                                                                                       |
| meta     | @cascade_lesson, @dontknow, @unsure, @useremotion, @collab, @noRESTORbackup, @exact, @consent, @modes, @gate, @noarch, @norule |
| general  | @mysql_86, @mysql_101, @mysql_117, @mysql_121, @mysql_228, @mysql_233, @mysql_236, @mysql_238      |

### Dependency edges

```
# ── Meta chain (behavioral, checked first) ──
@dontknow(2)      → @unsure(3)       → @gate(16)
@nofiles(9)       → @noedit(8)      → @scope(12)    → @askdel(13)
@noauto(14)       → @consent(11)
@exact(10)        → @norule(18)
@noexec(4)        → @memunit(32)
@modes(15)        → @collab(6)
@cascade_lesson(1) → @modes(15)
@useremotion(5)   → @gate(16)
@noRESTORbackup(7) → @askdel(13)

# ── Header chain (file → class → method) ──
@ghost(33)        → @vbsty(34)
@vbsty(34)        → @clshdr(36)     → @mthdr(37)
@cstyle(35)       → @auth(52)
@pascal(38)       → @underscore(19)
@upper(39)        → @hardcode(24)
@ctor(40)         → @state(41)      → @intstate(27)  → @noself(42)
@state(41)        → @rdst(44)       → @cfg(45)
@state(41)        → @ram(53)

# ── Syntax chain (prohibitions) ──
@print(22)        → @rpt(54)
@hardcode(24)     → @params(28)     → @phelp(46)
@decorators(20)   → @hidden(23)
@tabs(25)         → @whitespace(26)
@tuples(29)       → @t3(50)         → @succ(48)
@t3(50)           → @err(49)        → @errfmt(51)
@domain(30)       → @auth(52)       → @cstyle(35)
@dismap(31)       → @run(43)        → @disp(47)
@memunit(32)      → @run(43)
@enums(21)        → @hidden(23)

# ── Dispatch chain (Run is the hub) ──
@run(43)          → @dismap(31)
@run(43)          → @t3(50)
@run(43)          → @disp(47)
@run(43)          → @memunit(32)
@rdst(44)         → @state(41)
@cfg(45)          → @state(41)
@phelp(46)        → @params(28)
@disp(47)         → @dismap(31)
@succ(48)         → @t3(50)
@err(49)          → @t3(50)
@errfmt(51)       → @err(49)

# ── Authority chain ──
@auth(52)         → @domain(30)
@ram(53)          → @state(41)
@rpt(54)          → @print(22)

# ── DB schema chain (selfdb is the root) ──
@selfdb(55)       → @authdb(56)     → @dep(57)      → @mdep(58)
@selfdb(55)       → @runst(59)      → @exec(60)
@selfdb(55)       → @know(61)       → @conf(62)
@selfdb(55)       → @meth(63)       → @dcon(64)     → @reg(65)

# ── Analysis pipeline (sequential) ──
@exp(66)          → @clu(67)        → @map(68)      → @col(69)

# ── Validation chain (checked last, depends on everything) ──
@hrt(70)          → @ghost(33), @vbsty(34), @pascal(38), @clshdr(36), @mthdr(37), @underscore(19)
@hst(71)          → @tabs(25), @whitespace(26), @print(22), @decorators(20), @enums(21)

# ── General rules chain ──
@mysql_86(86)     → @norule(18)
@mysql_101(101)   → @selfdb(55), @hrt(70)
@mysql_229(229)   → @mysql_227(227), @mysql_228(228)
@mysql_234(234)   → @mysql_235(235) → @mysql_236(236) → @mysql_238(238)
@mysql_250(250)   → @mysql_234(234)
@mysql_117(117)   → @mysql_121(121)
@mysql_233(233)   → @hrt(70), @hst(71)
```

### Topological validation order

Rules must be checked in this order. If a rule fails, all downstream rules are skipped (marked `BLOCKED` not `FAIL`).

```
Phase 1 — Blocker (meta):
  @noedit(8) → @nofiles(9) → @noexec(4) → @scope(12) → @askdel(13) → @noauto(14) → @consent(11)

Phase 2 — Uncertainty (meta):
  @dontknow(2) → @unsure(3) → @gate(16) → @useremotion(5)

Phase 3 — Intent (meta):
  @exact(10) → @norule(18) → @noarch(17) → @cascade_lesson(1) → @modes(15) → @collab(6) → @noRESTORbackup(7)

Phase 4 — File structure (header):
  @ghost(33) → @vbsty(34) → @tabs(25) → @whitespace(26)

Phase 5 — Class structure (header):
  @clshdr(36) → @pascal(38) → @underscore(19) → @upper(39) → @cstyle(35) → @domain(30)

Phase 6 — Method structure (header):
  @mthdr(37) → @ctor(40) → @state(41) → @intstate(27) → @noself(42)

Phase 7 — Prohibitions (syntax):
  @print(22) → @decorators(20) → @enums(21) → @hidden(23) → @hardcode(24) → @params(28)

Phase 8 — Returns (syntax → dispatch):
  @tuples(29) → @t3(50) → @succ(48) → @err(49) → @errfmt(51)

Phase 9 — Dispatch (dispatch):
  @run(43) → @dismap(31) → @disp(47) → @memunit(32) → @rdst(44) → @cfg(45) → @phelp(46)

Phase 10 — Authority (authority):
  @auth(52) → @ram(53) → @rpt(54)

Phase 11 — DB schemas (db):
  @selfdb(55) → @authdb(56) → @dep(57) → @mdep(58) → @runst(59) → @exec(60) → @know(61) → @conf(62) → @meth(63) → @dcon(64) → @reg(65)

Phase 12 — Analysis (analysis):
  @exp(66) → @clu(67) → @map(68) → @col(69)

Phase 13 — Validation (validation):
  @hrt(70) → @hst(71)

Phase 14 — General (general):
  @mysql_86(86) → @mysql_101(101) → @mysql_117(117) → @mysql_121(121) → @mysql_229(229) → @mysql_227(227) → @mysql_228(228) → @mysql_233(233) → @mysql_234(234) → @mysql_235(235) → @mysql_236(236) → @mysql_238(238) → @mysql_250(250)
```

### Adjacency list (for programmatic use)

```python
RULE_GRAPH = {
    # Meta chain
    2: [3], 3: [16], 16: [],
    9: [8], 8: [12], 12: [13], 13: [],
    14: [11], 11: [],
    10: [18], 18: [],
    4: [32], 32: [43],
    15: [6], 6: [],
    1: [15],
    5: [16],
    7: [13],
    # Header chain
    33: [34], 34: [36], 36: [37], 37: [],
    35: [52], 52: [30], 30: [],
    38: [19], 19: [],
    39: [24], 24: [28], 28: [46], 46: [],
    40: [41], 41: [27, 44, 45, 53], 27: [42], 42: [],
    44: [], 45: [], 53: [],
    # Syntax chain
    22: [54], 54: [],
    20: [23], 23: [], 21: [23],
    25: [26], 26: [],
    29: [50], 50: [48, 49], 48: [], 49: [51], 51: [],
    31: [43], 43: [31, 50, 47, 32], 47: [31],
    # DB chain
    55: [56, 59, 61, 63], 56: [57], 57: [58], 58: [],
    59: [60], 60: [], 61: [62], 62: [], 63: [64], 64: [65], 65: [],
    # Analysis chain
    66: [67], 67: [68], 68: [69], 69: [],
    # Validation chain
    70: [33, 34, 38, 36, 37, 19], 71: [25, 26, 22, 20, 21],
    # General chain
    86: [18], 101: [55, 70], 117: [121], 121: [],
    229: [227, 228], 227: [], 228: [],
    233: [70, 71], 234: [235], 235: [236], 236: [238], 238: [],
    250: [234],
}
```

---